import datetime
import os
import sqlite3
import json
import time
import schedule
import feedparser
import pyupbit
from google import genai
from google.genai import types
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
from config_manager import ConfigManager

# Load environment variables
load_dotenv()

# Global Configuration
SELECTED_AI_MODEL = "gemini-3-pro-preview"
NEWS_FETCH_INTERVAL = 3600  # 1 hour

# Initialize Config Manager
config_manager = ConfigManager(config_file="config_coins.json")
config_manager.load_config()

class CryptoTrader:
    # Class-level cache for news fetch timestamps to persist across re-initializations
    _last_news_fetch = {}

    def __init__(self, crypto_symbol, config):
        self.crypto_symbol = crypto_symbol
        self.crypto_name = config["name"]
        self.ticker = config["ticker"]
        self.db_name = config["db_name"]
        self.init_db()
        print(f"🚀 {self.crypto_name} ({crypto_symbol}) trader initialized")

    def init_db(self):
        """Initialize SQLite database for this cryptocurrency."""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS trades
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          timestamp TEXT,
                          decision TEXT,
                          percentage INTEGER,
                          reason TEXT,
                          crypto_balance REAL,
                          krw_balance REAL,
                          crypto_price REAL)''')
            conn.commit()

    def log_trade(self, decision, percentage, reason, crypto_balance, krw_balance, crypto_price):
        """Log trade information to database."""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            timestamp = datetime.datetime.now().isoformat()
            c.execute("""INSERT INTO trades 
                         (timestamp, decision, percentage, reason, crypto_balance, krw_balance, crypto_price) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                      (timestamp, decision, percentage, reason, crypto_balance, krw_balance, crypto_price))
            conn.commit()

    def get_recent_trades(self, limit=5):
        """Get recent trades from database."""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("""
            SELECT timestamp, decision, percentage, reason, crypto_balance, krw_balance, crypto_price
            FROM trades
            ORDER BY timestamp DESC
            LIMIT ?
            """, (limit,))
            
            columns = ['timestamp', 'decision', 'percentage', 'reason', 'crypto_balance', 'krw_balance', 'crypto_price']
            return [{columns[i]: row[i] for i in range(len(columns))} for row in c.fetchall()]

    def get_crypto_news(self, num_results=5):
        """Fetch news data from RSS feeds with rate limiting."""
        current_time = time.time()
        last_fetch_key = f"{self.crypto_symbol}_last_fetch"
        
        # Rate Limiting Check
        if CryptoTrader._last_news_fetch.get(last_fetch_key):
            elapsed = current_time - CryptoTrader._last_news_fetch[last_fetch_key]
            if elapsed < NEWS_FETCH_INTERVAL:
                print(f"⏰ {self.crypto_symbol}: Rate limiting - Next news fetch in {(NEWS_FETCH_INTERVAL - elapsed)/60:.1f} minutes")
                return []
        
        rss_feeds = [
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://cointelegraph.com/rss",
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        ]
        
        news_data = []
        articles_found = 0
        crypto_keywords = [self.crypto_name.lower(), self.crypto_symbol.lower()]
        general_crypto_terms = ['crypto', 'cryptocurrency', 'bitcoin', 'ethereum', 'blockchain']

        print(f"📰 {self.crypto_symbol}: Fetching latest news...")
        
        try:
            for rss_url in rss_feeds:
                if articles_found >= num_results:
                    break
                try:
                    feed = feedparser.parse(rss_url)
                    if not feed.entries:
                        continue
                    
                    for entry in feed.entries:
                        if articles_found >= num_results:
                            break
                        
                        title = entry.get('title', '').lower()
                        summary = entry.get('summary', '').lower() if entry.get('summary') else ''
                        content_text = title + " " + summary
                        
                        # Relevance Check
                        is_relevant = any(k in content_text for k in crypto_keywords)
                        if not is_relevant and self.crypto_symbol in ['BTC', 'ETH', 'XRP', 'ADA', 'DOT']:
                            is_relevant = any(t in content_text for t in general_crypto_terms)
                        
                        if is_relevant:
                            news_data.append({
                                "link": entry.get('link', ''),
                                "title": entry.get('title', ''),
                                "published": entry.get('published', '')
                            })
                            articles_found += 1
                except Exception as e:
                    print(f"⚠️ {self.crypto_symbol}: Error fetching from {rss_url}: {e}")

            if articles_found > 0:
                print(f"✅ {self.crypto_symbol}: Retrieved {articles_found} relevant articles")
                CryptoTrader._last_news_fetch[last_fetch_key] = current_time
            else:
                print(f"⚠️ {self.crypto_symbol}: No relevant news found")
                
        except Exception as e:
            print(f"⚠️ {self.crypto_symbol}: Error fetching news: {e}")
            
        return news_data

    def send_slack_notification(self, decision, percentage, reason, crypto_balance, krw_balance, crypto_price, order_executed):
        """Send trade execution notification to Slack."""
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        slack_channel_id = os.getenv("SLACK_CHANNEL_ID")
        
        if not slack_token or not slack_channel_id:
            return
        
        try:
            client = WebClient(token=slack_token)
            total_value = krw_balance + (crypto_balance * crypto_price)
            emoji = {"buy": "🟢", "sell": "🔴", "hold": "🟡"}.get(decision.lower(), "❓")
            status = "EXECUTED" if order_executed else "SKIPPED"
            
            message = f"""
{emoji} *{self.crypto_name} Trading Alert* {emoji}
*Decision:* {decision.upper()} {percentage:.1f}% ({status})
*Timestamp:* {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

*Portfolio:*
• {self.crypto_symbol}: `{crypto_balance:.6f}` (₩{crypto_balance * crypto_price:,.0f})
• KRW: `₩{krw_balance:,.0f}`
• Total: `₩{total_value:,.0f}`
• Price: `₩{crypto_price:,.0f}`

*Reasoning:*
_{reason}_
            """.strip()
            
            client.chat_postMessage(
                channel=slack_channel_id,
                text=f"{emoji} {self.crypto_name} Alert - {decision.upper()}",
                blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": message}}]
            )
            print(f"✅ {self.crypto_symbol}: Slack notification sent")
        except Exception as e:
            print(f"⚠️ {self.crypto_symbol}: Slack Notification Error: {e}")

    def get_market_data(self):
        """Gather market data (charts, news, balance)."""
        print(f"📊 {self.crypto_symbol}: Fetching chart data...")
        
        # safely fetch OHLCV (using PyUpbit)
        try:
            short_term = pyupbit.get_ohlcv(self.ticker, interval="minute60", count=24)
            mid_term = pyupbit.get_ohlcv(self.ticker, interval="minute240", count=30)
            long_term = pyupbit.get_ohlcv(self.ticker, interval="day", count=30)
        except Exception as e:
            print(f"⚠️ Error fetching OHLCV: {e}")
            short_term, mid_term, long_term = None, None, None

        # Fetch News
        news_articles = self.get_crypto_news(num_results=5)

        # Fetch Balance with Safety Checks
        print(f"💰 {self.crypto_symbol}: Fetching current balance...")
        upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
        
        # Verify API connection first
        try:
            balances = upbit.get_balances()
            if isinstance(balances, dict) and 'error' in balances:
                error_msg = balances['error'].get('message', 'Unknown error')
                error_name = balances['error'].get('name', '')
                print(f"⚠️ {self.crypto_symbol}: Upbit API error: {error_msg} ({error_name})")
                my_krw = 0.0
                my_crypto = 0.0
            else:
                my_krw = upbit.get_balance("KRW") or 0.0
                my_crypto = upbit.get_balance(self.crypto_symbol) or 0.0
        except Exception as e:
            print(f"⚠️ {self.crypto_symbol}: Failed to fetch balance: {e}")
            my_krw = 0.0
            my_crypto = 0.0
        
        try:
            current_price = pyupbit.get_orderbook(self.ticker)['orderbook_units'][0]['ask_price']
        except Exception:
            current_price = 0.0

        return {
            "symbol": self.crypto_symbol,
            "short_term": json.loads(short_term.to_json()) if short_term is not None else None,
            "mid_term": json.loads(mid_term.to_json()) if mid_term is not None else None,
            "long_term": json.loads(long_term.to_json()) if long_term is not None else None,
            "news": news_articles,
            "current_balance": {
                "krw": my_krw,
                "crypto": my_crypto,
                "crypto_price": current_price,
                "total_value": my_krw + (my_crypto * current_price)
            },
            "recent_trades": self.get_recent_trades(limit=4)
        }

    def execute_decision(self, result):
        """Execute the AI trade decision."""
        print(f"\n🚀 {self.crypto_symbol} ({self.crypto_name}) Executing: {result['decision'].upper()}")
        
        try:
            upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
            
            # Fetch latest data for execution
            my_krw = upbit.get_balance("KRW") or 0.0
            my_crypto = upbit.get_balance(self.crypto_symbol) or 0.0
            current_price = pyupbit.get_current_price(self.ticker) or 0.0
            percentage = result.get("percentage", 0) / 100
            decision = result.get("decision")
            order_executed = False

            if decision == "buy":
                amount = my_krw * 0.9995 * percentage
                if amount > 5000:
                    print(f"💰 Buying ₩{amount:,.0f}")
                    upbit.buy_market_order(self.ticker, amount)
                    order_executed = True
                else:
                    print(f"❌ Insufficient KRW (>5000 required)")
            
            elif decision == "sell":
                amount = my_crypto * percentage
                value = amount * current_price
                if value > 5000:
                    print(f"💰 Selling {amount:.6f} {self.crypto_symbol} (₩{value:,.0f})")
                    upbit.sell_market_order(self.ticker, amount)
                    order_executed = True
                else:
                    print(f"❌ Insufficient {self.crypto_symbol} (>5000 KRW value required)")
            
            elif decision == "hold":
                print(f"⏸️ Hold Position")

            # Post-trade logging
            if order_executed:
                time.sleep(1) # Wait for order fill
                # Update balances
                my_krw = upbit.get_balance("KRW") or 0.0
                my_crypto = upbit.get_balance(self.crypto_symbol) or 0.0
            
            self.log_trade(decision, percentage*100 if order_executed else 0, result["reason"], my_crypto, my_krw, current_price)
            
            # Notify on active trades
            if decision in ["buy", "sell"]:
                self.send_slack_notification(decision, percentage*100, result["reason"], my_crypto, my_krw, current_price, order_executed)
                
            print(f"✅ Trade Completed: {decision}")

        except Exception as e:
            print(f"❌ Execution Error: {e}")


class MultiCryptoTrader:
    def __init__(self):
        self.traders = {}

    def initialize_traders(self):
        """Re-initialize traders based on current config."""
        configs = config_manager.get_section("coins")
        self.traders = {
            sym: CryptoTrader(sym, cfg) 
            for sym, cfg in configs.items() 
            if cfg.get("enabled", False)
        }
        print(f"🎯 Active Traders: {', '.join(self.traders.keys())}")

    def call_ai_model(self, system_prompt, market_data):
        """Handle AI API calls abstraction."""
        try:
            if SELECTED_AI_MODEL.startswith("gpt") or SELECTED_AI_MODEL.startswith("o"):
                from openai import OpenAI
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                token_param = "max_completion_tokens" if "gpt-4" not in SELECTED_AI_MODEL else "max_tokens"
                
                response = client.chat.completions.create(
                    model=SELECTED_AI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(market_data)}
                    ],
                    temperature=1,
                    # Dynamic token param based on model type if needed, or simple standard
                    **{token_param: 10000} 
                )
                return json.loads(response.choices[0].message.content)
            
            elif SELECTED_AI_MODEL.startswith("gemini"):
                client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

                # Generate a response
                resp = client.models.generate_content(
                    model=SELECTED_AI_MODEL,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt
                    ),
                    contents=json.dumps(market_data)
                )
                text = resp.text.strip()
                # Clean markdown code blocks if present
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text
                    if text.endswith("```"):
                        text = text.rsplit("\n", 1)[0]
                return json.loads(text)
                
        except Exception as e:
            print(f"❌ AI Analysis Failed: {e}")
            return {}

    def run_trading_session(self):
        """Execute one full centralized trading session."""
        self.initialize_traders()
        print(f"\n🚀 Starting Session: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Gather Data
        print("🧠 Analyzing markets...")
        market_data = {}
        for sym, trader in self.traders.items():
            market_data[sym] = trader.get_market_data()
        
        if not market_data:
            print("❌ No market data collected.")
            return

        # Prepare Prompt
        try:
            with open("trade_message.txt", "r", encoding="utf-8") as f:
                core_prompt = f.read()
        except FileNotFoundError:
            core_prompt = config_manager.get("trade_message", "You are a crypto expert.")
            
        system_prompt = core_prompt + """
        \nIMPORTANT: Return a JSON object where keys are crypto symbols (e.g. "BTC") and values are decision objects.
        Example: {"BTC": {"decision": "buy", "percentage": 50, "reason": "..."}}
        """

        # Get Decisions
        decisions = self.call_ai_model(system_prompt, market_data)
        
        if not decisions:
            print("❌ No AI decisions received.")
            return

        # Execute
        for sym, decision in decisions.items():
            if sym in self.traders:
                self.traders[sym].execute_decision(decision)
            else:
                print(f"⚠️ Unknown symbol in decision: {sym}")
        
        print("🎉 Session Completed.")

    def start(self):
        """Start the scheduler loop."""
        print("🔄 Multi-Crypto Auto Trader Started (Centralized Mode)")
        
        def job():
            self.run_trading_session()

        # Run once immediately
        job()
        
        # Schedule
        interval = config_manager.get("trade_interval_hours", 4)
        schedule.every(interval).hours.do(job)
        print(f"📅 Scheduled every {interval} hours.")

        while True:
            # Dynamic rescheduling check
            current_interval = config_manager.get("trade_interval_hours", 4)
            if current_interval != interval:
                schedule.clear()
                interval = current_interval
                schedule.every(interval).hours.do(job)
                print(f"🔄 Interval updated to {interval} hours.")
            
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    try:
        MultiCryptoTrader().start()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
