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

from config_manager import ConfigManager

load_dotenv()

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

    def ai_trade(self):
        """Perform AI-based trading analysis and decision"""
        print(f"📊 {self.crypto_symbol}: Fetching chart data...")
        
        # Get chart data
        short_term_df = pyupbit.get_ohlcv(self.ticker, interval="minute60", count=24)   # 1h x 24
        mid_term_df = pyupbit.get_ohlcv(self.ticker, interval="minute240", count=30)    # 4h x 30
        long_term_df = pyupbit.get_ohlcv(self.ticker, interval="day", count=30)         # daily x 30

        # Get news data
        news_articles = []
        news_articles = self.get_crypto_news(
            num_results=7
        )

        # Get current balance
        print(f"💰 {self.crypto_symbol}: Fetching current balance...")
        upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
        my_krw = upbit.get_balance("KRW")
        my_crypto = upbit.get_balance(self.crypto_symbol)
        current_price = pyupbit.get_orderbook(self.ticker)['orderbook_units'][0]['ask_price']

        # Get recent trades
        recent_trades = self.get_recent_trades(limit=4)

        data_payload = {
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

        print(f"🤖 {self.crypto_symbol}: Sending data to AI for analysis...")
        
        # Call OpenAI API
        from openai import OpenAI
        client = OpenAI()
        client.api_key = os.getenv("OPENAI_API_KEY")

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "system",
                    "content": config_manager.get("trade_message", "error")
                },
                {
                    "role": "user",
                    "content": json.dumps(data_payload)
                }
            ],
            temperature=1,
            max_tokens=16384,
            top_p=1,
            store=True
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        return result

    def execute_trade(self):
        """Execute trading decision"""
        print(f"\n{'='*50}")
        print(f"🚀 {self.crypto_symbol} ({self.crypto_name}) Trading Session")
        print(f"{'='*50}")
        
        try:
            # Call the AI trading function
            result = self.ai_trade()

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

    def execute_all_trades_parallel(self):
        self.initialize_traders()
        """Execute trades for all cryptocurrencies in parallel"""
        print(f"\n🚀 Starting parallel trading session for all cryptocurrencies...")
        print(f"⏰ Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Use ThreadPoolExecutor to run trades in parallel
        with ThreadPoolExecutor(max_workers=len(self.traders)) as executor:
            # Submit all trading tasks
            futures = {
                executor.submit(trader.execute_trade): crypto_symbol 
                for crypto_symbol, trader in self.traders.items()
            }
            
            # Wait for all tasks to complete
            for future in futures:
                crypto_symbol = futures[future]
                try:
                    future.result()  # This will raise an exception if the task failed
                except Exception as e:
                    print(f"❌ {crypto_symbol}: Trading session failed: {str(e)}")
        
        print(f"🎉 All trading sessions completed!")

    def execute_all_trades_sequential(self):
        self.initialize_traders()
        """Execute trades for all cryptocurrencies sequentially"""
        print(f"\n🚀 Starting sequential trading session for all cryptocurrencies...")
        print(f"⏰ Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        for crypto_symbol, trader in self.traders.items():
            trader.execute_trade()
            time.sleep(2)  # Small delay between trades
        
        print(f"🎉 All trading sessions completed!")

    def run_scheduler(self, parallel=True):
        """Run the trading scheduler"""
        print(f"🔄 Starting Multi-Crypto Auto Trading Scheduler...")
        print(f"⚙️ Mode: {'Parallel' if parallel else 'Sequential'} execution")

        def configure_schedule(trade_interval_hours):
            # Execute once immediately
            if parallel:
                self.execute_all_trades_parallel()
                schedule.every(trade_interval_hours).hours.do(self.execute_all_trades_parallel)
            else:
                self.execute_all_trades_sequential()
                schedule.every(trade_interval_hours).hours.do(self.execute_all_trades_sequential)
        
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
    
    # Run with parallel execution (default)
    # Set parallel=False for sequential execution if needed
    multi_trader.run_scheduler(parallel=True)

if __name__ == "__main__":
    main()
