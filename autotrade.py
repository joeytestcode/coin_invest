import datetime
import os
import sqlite3
from dotenv import load_dotenv
import pyupbit
import requests
import json
import time
import schedule
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import threading
from concurrent.futures import ThreadPoolExecutor
import feedparser
import google.generativeai as genai

from config_manager import ConfigManager

load_dotenv()

# AI Model Selection
# Options: "gpt-5", "gpt-4.1", "gemini-2.0-flash-exp", "gemini-1.5-pro"
SELECTED_AI_MODEL = "gpt-5"

# Add rate limiting tracking
LAST_NEWS_FETCH = {}
NEWS_FETCH_INTERVAL = 3600  # Fetch news only once per hour (3600 seconds)

config_manager = ConfigManager(config_file="config_coins.json")
config_manager.load_config()

class CryptoTrader:
    def __init__(self, crypto_symbol, config):
        self.crypto_symbol = crypto_symbol
        self.crypto_name = config["name"]
        self.ticker = config["ticker"]
        self.db_name = config["db_name"]
        
        # Initialize database
        self.init_db()
        
        print(f"🚀 {self.crypto_name} ({crypto_symbol}) trader initialized")

    def init_db(self):
        """Initialize SQLite database for this cryptocurrency"""
        conn = sqlite3.connect(self.db_name)
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
        conn.close()

    def log_trade(self, decision, percentage, reason, crypto_balance, krw_balance, crypto_price):
        """Log trade information to database"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        timestamp = datetime.datetime.now().isoformat()
        c.execute("""INSERT INTO trades 
                     (timestamp, decision, percentage, reason, crypto_balance, krw_balance, crypto_price) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (timestamp, decision, percentage, reason, crypto_balance, krw_balance, crypto_price))
        conn.commit()
        conn.close()

    def get_recent_trades(self, limit=5):
        """Get recent trades for this cryptocurrency"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        c.execute("""
        SELECT timestamp, decision, percentage, reason, crypto_balance, krw_balance, crypto_price
        FROM trades
        ORDER BY timestamp DESC
        LIMIT ?
        """, (limit,))
        
        columns = ['timestamp', 'decision', 'percentage', 'reason', 'crypto_balance', 'krw_balance', 'crypto_price']
        trades = []
        
        for row in c.fetchall():
            trade = {columns[i]: row[i] for i in range(len(columns))}
            trades.append(trade)
            
        conn.close()
        return trades

    def get_crypto_news(self, api_key=None, num_results=5):
        """Get news data from reputable crypto news sources using RSS feeds"""
        global LAST_NEWS_FETCH
        
        # Check rate limiting per crypto
        current_time = time.time()
        last_fetch_key = f"{self.crypto_symbol}_last_fetch"
        
        if LAST_NEWS_FETCH.get(last_fetch_key) and (current_time - LAST_NEWS_FETCH[last_fetch_key]) < NEWS_FETCH_INTERVAL:
            remaining_time = NEWS_FETCH_INTERVAL - (current_time - LAST_NEWS_FETCH[last_fetch_key])
            print(f"⏰ {self.crypto_symbol}: Rate limiting - Next news fetch in {remaining_time/60:.1f} minutes")
            return []
        
        # RSS feeds from reputable crypto news sources
        rss_feeds = [
            "https://www.coindesk.com/arc/outboundfeeds/rss/",  # CoinDesk
            "https://cointelegraph.com/rss",  # Cointelegraph
            "https://feeds.bloomberg.com/markets/news.rss",  # Bloomberg (general, but includes crypto)
            "https://www.cnbc.com/id/10001147/device/rss/rss.html",  # CNBC Markets (includes crypto)
        ]
        
        news_data = []
        articles_found = 0

        try:
            print(f"📰 {self.crypto_symbol}: Fetching latest news from crypto news sources...")
            
            for rss_url in rss_feeds:
                if articles_found >= num_results:
                    break
                    
                try:
                    # Parse RSS feed
                    feed = feedparser.parse(rss_url)
                    
                    if not feed.entries:
                        continue
                    
                    # Filter articles related to the specific cryptocurrency
                    crypto_keywords = [self.crypto_name.lower(), self.crypto_symbol.lower()]
                    
                    for entry in feed.entries:
                        if articles_found >= num_results:
                            break
                            
                        title = entry.get('title', '').lower()
                        summary = entry.get('summary', '').lower() if entry.get('summary') else ''
                        
                        # Check if article is relevant to this cryptocurrency
                        is_relevant = any(keyword in title or keyword in summary for keyword in crypto_keywords)
                        
                        # If no specific crypto match, include general crypto articles for major cryptos
                        if not is_relevant and self.crypto_symbol in ['BTC', 'ETH', 'XRP', 'ADA', 'DOT']:
                            general_crypto_terms = ['crypto', 'cryptocurrency', 'bitcoin', 'ethereum', 'blockchain']
                            is_relevant = any(term in title or term in summary for term in general_crypto_terms)
                        
                        if is_relevant:
                            news_data.append({
                                "link": entry.get('link', ''),
                                "title": entry.get('title', ''),
                                "published": entry.get('published', '')
                            })
                            articles_found += 1
                            
                except Exception as e:
                    print(f"⚠️ {self.crypto_symbol}: Error fetching from {rss_url}: {str(e)}")
                    continue
            
            if articles_found > 0:
                print(f"✅ {self.crypto_symbol}: Retrieved {articles_found} relevant news articles")
                LAST_NEWS_FETCH[last_fetch_key] = current_time
            else:
                print(f"⚠️ {self.crypto_symbol}: No relevant news articles found")
                
        except Exception as e:
            print(f"⚠️ {self.crypto_symbol}: Error fetching news: {str(e)}")
            
        return news_data

    def send_slack_notification(self, decision, percentage, reason, crypto_balance, krw_balance, crypto_price, order_executed):
        """Send Slack notification about trade execution"""
        try:
            slack_token = os.getenv("SLACK_BOT_TOKEN")
            slack_channel_id = os.getenv("SLACK_CHANNEL_ID")
            
            if not slack_token or not slack_channel_id:
                print(f"⚠️ {self.crypto_symbol}: Slack credentials not found. Skipping notification.")
                return
            
            client = WebClient(token=slack_token)
            
            # Calculate total portfolio value
            total_value = krw_balance + (crypto_balance * crypto_price)
            
            # Create status emoji based on decision
            decision_emoji = {
                "buy": "🟢",
                "sell": "🔴", 
                "hold": "🟡"
            }
            
            emoji = decision_emoji.get(decision.lower(), "❓")
            status = "EXECUTED" if order_executed else "SKIPPED"
            
            # Format the message
            message = f"""
{emoji} *{self.crypto_name} Trading Alert* {emoji}

*Decision:* {decision.upper()} {percentage:.1f}%
*Status:* {status}
*Timestamp:* {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

*Portfolio Status:*
• {self.crypto_symbol} Balance: `{crypto_balance:.6f}` (₩{crypto_balance * crypto_price:,.0f})
• KRW Balance: `₩{krw_balance:,.0f}`
• Total Value: `₩{total_value:,.0f}`
• Current {self.crypto_symbol} Price: `₩{crypto_price:,.0f}`

*AI Reasoning:*
_{reason}_

---
_Crypto Auto Trading Bot - {self.crypto_symbol}_ 🤖
            """.strip()
            
            # Send notification
            response = client.chat_postMessage(
                channel=slack_channel_id,
                text=f"{emoji} {self.crypto_name} Trading Alert - {decision.upper()} {status}",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message
                        }
                    }
                ]
            )
            
            print(f"✅ {self.crypto_symbol}: Slack notification sent successfully")
            
        except SlackApiError as e:
            print(f"⚠️ {self.crypto_symbol}: Slack API error: {e.response['error']}")
        except Exception as e:
            print(f"⚠️ {self.crypto_symbol}: Error sending Slack notification: {str(e)}")

    def get_market_data(self):
        """Gather market data for analysis without executing trade"""
        print(f"📊 {self.crypto_symbol}: Fetching chart data...")
        
        # Get chart data
        short_term_df = pyupbit.get_ohlcv(self.ticker, interval="minute60", count=24)   # 1h x 24
        mid_term_df = pyupbit.get_ohlcv(self.ticker, interval="minute240", count=30)    # 4h x 30
        long_term_df = pyupbit.get_ohlcv(self.ticker, interval="day", count=30)         # daily x 30

        # Get news data
        news_articles = self.get_crypto_news(num_results=5)

        # Get current balance
        print(f"💰 {self.crypto_symbol}: Fetching current balance...")
        upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
        my_krw = upbit.get_balance("KRW")
        my_crypto = upbit.get_balance(self.crypto_symbol)
        current_price = pyupbit.get_orderbook(self.ticker)['orderbook_units'][0]['ask_price']

        # Get recent trades
        recent_trades = self.get_recent_trades(limit=4)

        data_payload = {
            "symbol": self.crypto_symbol,
            "short_term": json.loads(short_term_df.to_json()) if short_term_df is not None else None,
            "mid_term": json.loads(mid_term_df.to_json()) if mid_term_df is not None else None,
            "long_term": json.loads(long_term_df.to_json()) if long_term_df is not None else None,
            "news": news_articles,
            "current_balance": {
                "krw": my_krw,
                "crypto": my_crypto,
                "crypto_price": current_price,
                "total_value": my_krw + (my_crypto * current_price)
            },
            "recent_trades": recent_trades
        }
        return data_payload

    def execute_decision(self, result):
        """Execute a specific trading decision passed from the multi-trader"""
        print(f"\n{'='*50}")
        print(f"🚀 {self.crypto_symbol} ({self.crypto_name}) Executing Decision")
        print(f"{'='*50}")
        
        try:
            # Auto investment based on the response
            upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
            
            my_krw = upbit.get_balance("KRW")
            my_crypto = upbit.get_balance(self.crypto_symbol)
            current_price = pyupbit.get_current_price(self.ticker)
            percentage = result.get("percentage", 0) / 100

            order_executed = False

            if result["decision"] == "buy":
                amount = my_krw * 0.9995 * percentage
                if amount > 5000:
                    print(f"💰 {self.crypto_symbol}: Buying with ₩{amount:,.0f}")
                    upbit.buy_market_order(self.ticker, amount)
                    print(f"✅ {self.crypto_symbol}: Buy order executed - {result['reason']}")
                    order_executed = True
                else:
                    print(f"❌ {self.crypto_symbol}: Not enough KRW to buy (need >5000 KRW)")
                    
            elif result["decision"] == "sell":
                crypto_amount = my_crypto * percentage
                value = crypto_amount * current_price
                if value > 5000:
                    print(f"💰 {self.crypto_symbol}: Selling {crypto_amount:.6f} {self.crypto_symbol} (₩{value:,.0f})")
                    upbit.sell_market_order(self.ticker, crypto_amount)
                    print(f"✅ {self.crypto_symbol}: Sell order executed - {result['reason']}")
                    order_executed = True
                else:
                    print(f"❌ {self.crypto_symbol}: Not enough {self.crypto_symbol} to sell (need >5000 KRW value)")
                    
            elif result["decision"] == "hold":
                print(f"⏸️ {self.crypto_symbol}: Holding - {result['reason']}")
                order_executed = True

            # Wait for the order to be processed
            time.sleep(1)

            # Get updated balances
            updated_krw = upbit.get_balance("KRW")
            updated_crypto = upbit.get_balance(self.crypto_symbol)
            updated_price = pyupbit.get_orderbook(self.ticker)['orderbook_units'][0]['ask_price']

            # Log trade
            self.log_trade(
                result["decision"],
                percentage if order_executed else 0,
                result["reason"],
                updated_crypto,
                updated_krw, 
                updated_price
            )
            
            # Send Slack notification only for buy/sell operations
            if result["decision"] in ["buy", "sell"]:
                self.send_slack_notification(
                    result["decision"],
                    result.get("percentage", 0),
                    result["reason"],
                    updated_crypto,
                    updated_krw,
                    updated_price,
                    order_executed
                )

            print(f"📈 {self.crypto_symbol}: Trade session completed - {result['decision']} Order executed: {order_executed}")
            
        except Exception as e:
            print(f"❌ {self.crypto_symbol}: Error during trading session: {str(e)}")

    def ai_trade(self):
        """Legacy method - kept for compatibility but not used in multi-mode"""
        data = self.get_market_data()
        # ... (rest of legacy logic if needed, but we are replacing the caller)
        return None 


class MultiCryptoTrader:
    def __init__(self):
        self.traders = {}

    def initialize_traders(self):
        CRYPTO_CONFIGS = config_manager.get_section("coins")

        """Initialize traders for each configured cryptocurrency"""
        for crypto_symbol, config in CRYPTO_CONFIGS.items():
            if config.get("enabled", False):
                self.traders[crypto_symbol] = CryptoTrader(crypto_symbol, config)
        
        print(f"🎯 Multi-Crypto Trader initialized with {len(self.traders)} cryptocurrencies")
        print(f"📈 Trading: {', '.join(CRYPTO_CONFIGS.keys())}")

    def get_combined_decision(self):
        """Gather data from all traders and get a combined AI decision"""
        print(f"\n🧠 Analyzing market for all cryptocurrencies...")
        
        # Gather data from all traders
        market_data = {}
        for symbol, trader in self.traders.items():
            try:
                market_data[symbol] = trader.get_market_data()
            except Exception as e:
                print(f"⚠️ Error gathering data for {symbol}: {e}")
        
        if not market_data:
            print("❌ No market data available")
            return {}

        # Construct prompt for multi-coin analysis
        system_prompt = config_manager.get("trade_message", "error")
        
        # Append instruction for multi-coin output format
        system_prompt += """
        
        IMPORTANT: You are analyzing MULTIPLE cryptocurrencies.
        Return a JSON object where keys are the crypto symbols (e.g. "BTC", "ETH", "XRP") and values are the decision objects.
        Example format:
        {
            "BTC": {"decision": "buy", "percentage": 50, "reason": "..."},
            "ETH": {"decision": "hold", "percentage": 100, "reason": "..."},
            "XRP": {"decision": "sell", "percentage": 20, "reason": "..."}
        }
        Consider the opportunity cost between coins. If one coin has a much better setup, prioritize it.
        """

        print(f"🤖 Sending combined data to AI ({SELECTED_AI_MODEL})...")
        
        result = {}
        try:
            if SELECTED_AI_MODEL.startswith("gpt"):
                from openai import OpenAI
                client = OpenAI()
                client.api_key = os.getenv("OPENAI_API_KEY")
                
                token_param = "max_completion_tokens" if SELECTED_AI_MODEL.startswith(("o1", "o3", "gpt-5")) else "max_tokens"
                
                completion_args = {
                    "model": SELECTED_AI_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": json.dumps(market_data)
                        }
                    ],
                    "temperature": 1,
                    "top_p": 1,
                    "store": True
                }
                completion_args[token_param] = 16384
                
                response = client.chat.completions.create(**completion_args)
                result_text = response.choices[0].message.content
                result = json.loads(result_text)
                
            elif SELECTED_AI_MODEL.startswith("gemini"):
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                model = genai.GenerativeModel(
                    model_name=SELECTED_AI_MODEL,
                    system_instruction=system_prompt
                )
                response = model.generate_content(json.dumps(market_data))
                result_text = response.text
                
                if result_text.strip().startswith("```json"):
                    result_text = result_text.strip()[7:]
                elif result_text.strip().startswith("```"):
                    result_text = result_text.strip()[3:]
                if result_text.strip().endswith("```"):
                    result_text = result_text.strip()[:-3]
                    
                result = json.loads(result_text.strip())
                
        except Exception as e:
            print(f"❌ Error during combined AI analysis: {str(e)}")
            return {}
            
        return result

    def execute_all_trades_centralized(self):
        """Execute trades based on a centralized AI decision"""
        self.initialize_traders()
        print(f"\n🚀 Starting centralized trading session...")
        print(f"⏰ Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get combined decision
        decisions = self.get_combined_decision()
        
        if not decisions:
            print("❌ No decisions received from AI")
            return

        # Execute decisions sequentially
        for symbol, decision in decisions.items():
            if symbol in self.traders:
                try:
                    self.traders[symbol].execute_decision(decision)
                except Exception as e:
                    print(f"❌ Error executing trade for {symbol}: {e}")
            else:
                print(f"⚠️ Received decision for unknown symbol: {symbol}")
        
        print(f"🎉 All trading sessions completed!")

    def run_scheduler(self, parallel=True):
        """Run the trading scheduler"""
        print(f"🔄 Starting Multi-Crypto Auto Trading Scheduler...")
        # Force centralized execution for better portfolio management
        print(f"⚙️ Mode: Centralized Portfolio Analysis")

        def configure_schedule(trade_interval_hours):
            # Execute once immediately
            self.execute_all_trades_centralized()
            schedule.every(trade_interval_hours).hours.do(self.execute_all_trades_centralized)
        
        trade_interval_hours = config_manager.get("trade_interval_hours", 4)
        configure_schedule(trade_interval_hours)

        while True:
            if trade_interval_hours != config_manager.get("trade_interval_hours", 4):
                schedule.clear()
                configure_schedule(trade_interval_hours)
                print(f"🔄 Trade interval updated to every {trade_interval_hours} hours")

            schedule.run_pending()
            time.sleep(60)

def main():
    """Main function to run the multi-crypto trader"""
    print("🚀 Multi-Cryptocurrency Auto Trading Bot Starting...")
    print(f"📅 Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create multi-crypto trader
    multi_trader = MultiCryptoTrader()
    
    # Run with centralized execution
    multi_trader.run_scheduler(parallel=False)

if __name__ == "__main__":
    main()
