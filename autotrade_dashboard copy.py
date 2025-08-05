import os
import sqlite3
from dotenv import load_dotenv
import requests
import json
import sys
import signal
import time
from datetime import datetime

load_dotenv()

target = "ETH"  # Target cryptocurrency
target_name = "Ethereum"
target_kicker = f"KRW-{target}"  # Upbit ticker for the target cryptocurrency
db_name = 'bitcoin_trading.db'

# Global flag for graceful shutdown
running = True

# SQLite 데이터베이스 초기화 함수
def init_db():
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  decision TEXT,
                  percentage INTEGER,
                  reason TEXT,
                  btc_balance REAL,
                  krw_balance REAL,
                  btc_price REAL)''')
    conn.commit()
    return conn

# 거래 정보를 DB에 기록하는 함수
def log_trade(conn, decision, percentage, reason, btc_balance, krw_balance, btc_price):
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute("""INSERT INTO trades 
                 (timestamp, decision, percentage, reason, btc_balance, krw_balance, btc_price) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (timestamp, decision, percentage, reason, btc_balance, krw_balance, btc_price))
    conn.commit()

def signal_handler(signum, frame):
    global running
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Received shutdown signal. Stopping trading...")
    running = False

# Set up signal handler for graceful shutdown
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def log_message(message):
    """Print message with timestamp for better logging"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()  # Force output to be displayed immediately

def get_crypto_news(api_key, query, location="us", language="en", num_results=5):
    """
    SerpAPI를 사용하여 Google News에서 뉴스 기사의 제목과 날짜를 가져옵니다.
    """
    params = {
        "engine": "google_news", "q": query, "gl": location,
        "hl": language, "api_key": api_key
    }
    api_url = "https://serpapi.com/search.json"
    news_data = []

    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status() # 기본적인 HTTP 오류는 확인
        results = response.json()

        if "news_results" in results:
            for news_item in results["news_results"][:num_results]:
                news_data.append({
                    "title": news_item.get("title"),
                    "date": news_item.get("date")
                })
    except Exception as e:
        log_message(f"Error fetching news: {str(e)}")
    
    return news_data

def ai_trade():
    global running
    
    try:
        log_message("Starting AI trade analysis...")
        
        #1. Take upbit chart data
        import pyupbit

        log_message("Fetching market data...")
        short_term_df = pyupbit.get_ohlcv(target_kicker, interval="minute60", count=24)   # 단기: 1시간봉 24개
        mid_term_df = pyupbit.get_ohlcv(target_kicker, interval="minute240", count=30)     # 중기: 4시간봉 30개
        long_term_df = pyupbit.get_ohlcv(target_kicker, interval="day", count=30)           # 장기: 일봉 30개

        #1-1. Get news data
        log_message("Fetching news data...")
        news_articles = []
        if os.getenv("SERAPI_API_KEY"): # 키가 있을 때만 호출 시도
            news_articles = get_crypto_news(
                api_key=os.getenv("SERAPI_API_KEY"), query=f"{target_name} news",
                location="us", language="en", num_results=5
            )
            log_message(f"Found {len(news_articles)} news articles")
        else:
            log_message("No SERAPI_API_KEY found, skipping news analysis")

        data_payload = {
            "short_term": json.loads(short_term_df.to_json()),
            "mid_term": json.loads(mid_term_df.to_json()),
            "long_term": json.loads(long_term_df.to_json()),
            "news": news_articles
        }

        #2. Provide data to ChatGPT
        log_message("Analyzing data with AI...")
        from openai import OpenAI
        client = OpenAI()

        response = client.responses.create(
        model="gpt-4.1",
        input=[
            {
            "role": "system",
            "content": [
                {
                "type": "input_text",
                "text": """
    You're a cryptocurrency investment expert especially.
    You invest according to the following rules:
        1. Analyze the short-term, mid-term, and long-term trends of the cryptocurrency carefully.
        (short-term: 1 hour candles, mid-term: 4 hours candles, long-term: daily candles)
        2. Never miss the opportunity to buy.
        3. Never miss the opportunity to sell.

    Analyze the provided data:
        1.  **Chart Data:** Multi-timeframe OHLCV data ('short_term': 1h, 'mid_term': 4h, 'long_term': daily).
        2.  **News Data:** Recent cryptocurrency news articles with 'title' and 'date'.

    **Task:** Based on technical analysis and news sentiment, decide whether to **buy**, **sell**, or **hold** {0} cryptocurrency.
    For buy decisions, include a percentage (1-100) indicating what portion of available funds to use.
    For sell decisions, include a percentage (1-100) indicating what portion of holdings to sell.
    For hold, the percentage should be 100.

    Sample answer 1:
    {{\"decision\":\"buy\", \"percentage\": 50, \"reason\":\"Some technical reason to buy based on analysis result\"}}
    Sample answer 2:
    {{\"decision\":\"sell\", \"percentage\": 30, \"reason\":\"Some technical reason to sell based on analysis result\"}}
    Sample answer 3:
    {{\"decision\":\"hold\", \"percentage\": 20, \"reason\":\"Some technical reason to hold based on analysis result\"}}
    """.format(target_name)
                
                }
            ]
            },
            {
            "role": "user",
            "content": [
                {
                "type": "input_text",
                "text": json.dumps(data_payload)  # Convert the data payload to JSON string
                }
            ]
            }
        ],
        text={
            "format": {
            "type": "text"
            }
        },
        reasoning={},
        tools=[],
        temperature=1,
        max_output_tokens=16384,
        top_p=1,
        store=True
        )

        result0 = response.output[0].content[0].text
        result = json.loads(result0)

        log_message(f"AI Response: {result0}")
        
        try:
            result = json.loads(result0)
        except json.JSONDecodeError:
            log_message("Error: Could not parse AI response as JSON")
            return

        log_message(f"AI Decision: {result['decision'].upper()} {result['percentage']}%")
        log_message(f"Reason: {result['reason']}")

        # Auto investment based on the response
        log_message("Executing trade decision...")
        
        upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
        percentage = result.get("percentage", 0) / 100

        if result["decision"] == "buy":
            my_balance = upbit.get_balance("KRW")
            amount = my_balance * 0.9995 * percentage
            log_message(f"Available KRW balance: {my_balance:,.0f}")
            log_message(f"Amount to invest: {amount:,.0f} KRW ({result['percentage']}%)")
            
            if amount > 5000:
                log_message(f"Buying {target} with {amount:,.0f} KRW")
                order_result = upbit.buy_market_order(target_kicker, amount)
                log_message(f"Buy order result: {order_result}")
                log_message(f"Buy reason: {result['reason']}")
            else:
                log_message(f"Not enough KRW to buy {target} (minimum 5000 KRW required)")
                
        elif result["decision"] == "sell":
            my_crypto_balance = upbit.get_balance(target)
            current_price = pyupbit.get_orderbook(target_kicker)['orderbook_units'][0]['ask_price']
            btc_amount = my_crypto_balance * percentage
            value = btc_amount * current_price
            
            log_message(f"Available {target} balance: {my_crypto_balance}")
            log_message(f"Amount to sell: {btc_amount} {target} ({result['percentage']}%)")
            log_message(f"Estimated value: {value:,.0f} KRW")
            
            if value > 5000:
                log_message(f"Selling {btc_amount} {target}")
                order_result = upbit.sell_market_order(target_kicker, btc_amount)
                log_message(f"Sell order result: {order_result}")
                log_message(f"Sell reason: {result['reason']}")
            else:
                log_message(f"Not enough {target} to sell (minimum value 5000 KRW required)")
                
        elif result["decision"] == "hold":
            log_message(f"Holding {target}")
            log_message(f"Hold reason: {result['reason']}")

    except Exception as e:
        log_message(f"Error during trading: {str(e)}")
        import traceback
        log_message(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    # Check if interval argument is provided
    trade_interval_minutes = 60  # Default 1 hour
    if len(sys.argv) > 1:
        try:
            trade_interval_minutes = int(sys.argv[1])
        except ValueError:
            log_message("Invalid interval argument, using default 60 minutes")
    
    trade_interval_seconds = trade_interval_minutes * 60
    
    log_message("=== Auto Trading Started ===")
    log_message(f"Target cryptocurrency: {target_name} ({target})")
    log_message(f"Trading interval: {trade_interval_minutes} minutes")
    
    try:
        while running:
            if not running:
                break
                
            ai_trade()  # Call the trading function
            
            if not running:
                break
                
            log_message(f"Waiting {trade_interval_minutes} minutes for next trade cycle...")
            
            # Sleep in smaller intervals to allow for interruption
            for i in range(trade_interval_seconds):
                if not running:
                    break
                time.sleep(1)
                
    except KeyboardInterrupt:
        log_message("Received keyboard interrupt")
    except Exception as e:
        log_message(f"Unexpected error: {str(e)}")
    finally:
        log_message("=== Auto Trading Stopped ===")
