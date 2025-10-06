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
load_dotenv()

# Add rate limiting tracking
LAST_NEWS_FETCH = None
NEWS_FETCH_INTERVAL = 3600  # Fetch news only once per hour (3600 seconds)

target = "XRP"  # Target cryptocurrency
target_name = "XRP"
target_kicker = f"KRW-{target}"  # Upbit ticker for the target cryptocurrency

# target = "ETH"  # Target cryptocurrency
# target_name = "Ethereum"
# target_kicker = f"KRW-{target}"  # Upbit ticker for the target cryptocurrency

db_name = 'coin_auto_trade_xrp.db'


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
                  crypto_balance REAL,
                  krw_balance REAL,
                  crypto_price REAL)''')
    conn.commit()
    return conn

# 거래 정보를 DB에 기록하는 함수
def log_trade(conn, decision, percentage, reason, crypto_balance, krw_balance, crypto_price):
    c = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    c.execute("""INSERT INTO trades 
                 (timestamp, decision, percentage, reason, crypto_balance, krw_balance, crypto_price) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (timestamp, decision, percentage, reason, crypto_balance, krw_balance, crypto_price))
    conn.commit()
    
# DB 연결 가져오기
def get_db_connection():
    return sqlite3.connect(db_name)

# 최근 거래 내역 가져오기
def get_recent_trades(limit=5):
    conn = get_db_connection()
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

def get_crypto_news(api_key, query, location="us", language="en", num_results=5):
    """
    SerpAPI를 사용하여 Google News에서 뉴스 기사의 제목과 날짜를 가져옵니다.
    Rate limiting과 에러 처리를 포함합니다.
    """
    global LAST_NEWS_FETCH
    
    if not api_key:
        print("SerpAPI key not found, skipping news data")
        return []
    
    # Check rate limiting
    current_time = time.time()
    if LAST_NEWS_FETCH and (current_time - LAST_NEWS_FETCH) < NEWS_FETCH_INTERVAL:
        remaining_time = NEWS_FETCH_INTERVAL - (current_time - LAST_NEWS_FETCH)
        print(f"⏰ Rate limiting: Next news fetch in {remaining_time/60:.1f} minutes")
        return []
    
    params = {
        "engine": "google_news", "q": query, "gl": location,
        "hl": language, "api_key": api_key
    }
    api_url = "https://serpapi.com/search.json"
    news_data = []

    try:
        print("📰 Fetching latest news...")
        response = requests.get(api_url, params=params, timeout=10)
        
        # Handle rate limiting
        if response.status_code == 429:
            print("⚠️ SerpAPI rate limit exceeded. Skipping news data for this cycle.")
            print("Consider upgrading your SerpAPI plan or reducing request frequency.")
            return []
        
        # Handle other HTTP errors
        if response.status_code != 200:
            print(f"⚠️ SerpAPI error {response.status_code}: {response.text}")
            return []
        
        results = response.json()

        if "news_results" in results:
            for news_item in results["news_results"][:num_results]:
                news_data.append({
                    "title": news_item.get("title"),
                    "date": news_item.get("date")
                })
            print(f"✅ Retrieved {len(news_data)} news articles")
            LAST_NEWS_FETCH = current_time  # Update last fetch time only on success
        else:
            print("⚠️ No news results found in SerpAPI response")
            
    except requests.exceptions.Timeout:
        print("⚠️ SerpAPI request timed out. Skipping news data.")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ SerpAPI request failed: {str(e)}")
    except json.JSONDecodeError:
        print("⚠️ Invalid JSON response from SerpAPI")
    except Exception as e:
        print(f"⚠️ Unexpected error fetching news: {str(e)}")
        
    return news_data

def send_slack_notification(decision, percentage, reason, crypto_balance, krw_balance, crypto_price, order_executed):
    """
    Send a Slack DM notification about the trade execution
    """
    try:
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        slack_user_id = os.getenv("SLACK_USER_ID")
        slack_channel_id = os.getenv("SLACK_CHANNEL_ID")
        
        if not slack_token or not slack_channel_id:
            print("⚠️ Slack credentials not found. Skipping notification.")
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
{emoji} *{target_name} Trading Alert* {emoji}

*Decision:* {decision.upper()} {percentage:.1f}%
*Status:* {status}
*Timestamp:* {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

*Portfolio Status:*
• {target} Balance: `{crypto_balance:.6f}` (₩{crypto_balance * crypto_price:,.0f})
• KRW Balance: `₩{krw_balance:,.0f}`
• Total Value: `₩{total_value:,.0f}`
• Current {target} Price: `₩{crypto_price:,.0f}`

*AI Reasoning:*
_{reason}_

---
_Crypto Auto Trading Bot_ 🤖
        """.strip()
        
        # Send DM using channel ID
        response = client.chat_postMessage(
            channel=slack_channel_id,
            text=f"{emoji} {target_name} Trading Alert - {decision.upper()} {status}",
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
        
        print(f"✅ Slack notification sent successfully")
        
    except SlackApiError as e:
        print(f"⚠️ Slack API error: {e.response['error']}")
    except Exception as e:
        print(f"⚠️ Error sending Slack notification: {str(e)}")

def send_slack_message(message):
    """
    Send a simple Slack message
    """
    try:
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        slack_user_id = os.getenv("SLACK_USER_ID")
        slack_channel_id = os.getenv("SLACK_CHANNEL_ID")
        
        if not slack_token or not slack_channel_id:
            print("⚠️ Slack credentials not found. Skipping notification.")
            return
        
        client = WebClient(token=slack_token)
        
        response = client.chat_postMessage(
            channel=slack_channel_id,
            text=message
        )
        
        print(f"✅ Slack message sent successfully")
        
    except SlackApiError as e:
        print(f"⚠️ Slack API error: {e.response['error']}")
    except Exception as e:
        print(f"⚠️ Error sending Slack message: {str(e)}")

def ai_trade():
    #1. Take upbit chart data
    import pyupbit

    print("📊 Fetching chart data...")
    short_term_df = pyupbit.get_ohlcv(target_kicker, interval="minute60", count=24)   # 단기: 1시간봉 24개
    mid_term_df = pyupbit.get_ohlcv(target_kicker, interval="minute240", count=30)     # 중기: 4시간봉 30개
    long_term_df = pyupbit.get_ohlcv(target_kicker, interval="day", count=30)           # 장기: 일봉 30개

    #1-1. Get news data with rate limiting
    news_articles = []
    if os.getenv("SERAPI_API_KEY"): # 키가 있을 때만 호출 시도
        news_articles = get_crypto_news(
            api_key=os.getenv("SERAPI_API_KEY"), query=f"{target_name} news",
            location="us", language="en", num_results=5
        )
    else:
        print("⚠️ SERAPI_API_KEY not found in environment variables")

    #1-2. Get current balance
    print("💰 Fetching current balance...")
    upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
    my_krw = upbit.get_balance("KRW")
    my_crypto = upbit.get_balance(target)
    current_price = pyupbit.get_orderbook(target_kicker)['orderbook_units'][0]['ask_price']


    recent_trades = get_recent_trades(limit=5)

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

    print("🤖 Sending data to AI for analysis...")
    
    #2. Provide data to ChatGPT
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
                            1. Most of all, I want to make a lot of money!
                            2. Never miss the opportunity to buy.
                            3. Never miss the opportunity to sell.

                        Analyze the provided data:
                            1.  **Chart Data:** Multi-timeframe OHLCV data ('short_term': 1h, 'mid_term': 4h, 'long_term': daily).
                            2.  **News Data:** Recent cryptocurrency news articles with 'title' and 'date'.
                            3. **Current Balance:** Your current KRW and cryptocurrency holdings, and Current price of the cryptocurrency.
                            4. **Recent Trades:** Your recent trades with 'date', 'type', 'amount', and 'price'. Deciosions and their outcomes.

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

    return result

def execute_trade():
    # Initialize database connection
    conn = init_db()

    # Call the AI trading function
    result = ai_trade()
    print()
    print('### AI Decision : ', result['decision'].upper(), result['percentage'], '% ###')
    print('### Reason : ', result['reason'], '###')

    # Auto investment based on the response
    upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
    
    my_krw = upbit.get_balance("KRW")
    my_crypto = upbit.get_balance(target)
    current_price = pyupbit.get_current_price(target_kicker)
    percentage = result.get("percentage", 0) / 100

    order_executed = False

    if result["decision"] == "buy":
        amount = my_krw * 0.9995 * percentage
        if amount > 5000:
            print(f"Buying {target} with available KRW")
            upbit.buy_market_order(target_kicker, amount)  # Buy with 10% of available KRW
            # upbit.buy_market_order(target_kicker, 10000)  # Buy with 10% of available KRW
            print("buy : ", result["reason"])
            order_executed = True
        else:
            print(f"Not enough KRW to buy {target}")
    elif result["decision"] == "sell":
        crypto_amount = my_crypto * percentage
        value = crypto_amount * current_price
        if value > 5000:
            print(f"Selling {target}")
            upbit.sell_market_order(target_kicker, crypto_amount)  # Sell all {target}
            # upbit.sell_market_order(target_kicker, 0.0001)  # Sell all {target}
            print("sell : ", result["reason"])
            order_executed = True
        else:
            print(f"Not enough {target} to sell")
    elif result["decision"] == "hold":
        print(f"Holding {target}")
        print("hold : ", result["reason"])
        order_executed = True

    # Wait for the order to be processed
    time.sleep(1)

    # 거래 후 최신 잔고 조회
    updated_krw = upbit.get_balance("KRW")
    updated_crypto = upbit.get_balance(target)
    updated_price = pyupbit.get_orderbook(target_kicker)['orderbook_units'][0]['ask_price']

    # 거래 정보 로깅
    log_trade(
        conn,
        result["decision"],
        percentage if order_executed else 0,
        result["reason"],
        updated_crypto,
        updated_krw, 
        updated_price
    )
    
    # 거래 실행 시 Slack 알림 전송
    if order_executed and result["decision"] in ["buy", "sell"]:
        message = f"🚀 XRP Trade Executed!\n"
        message += f"Decision: {result['decision'].upper()}\n"
        message += f"Percentage: {percentage}%\n"
        message += f"Reason: {result['reason']}\n"
        message += f"Updated XRP: {updated_crypto}\n"
        message += f"Updated KRW: {updated_krw:,.0f}\n"
        message += f"Current Price: {updated_price:,.0f} KRW"
        send_slack_message(message)
    
    # 데이터베이스 연결 종료
    conn.close()

    print()
    print(f"Trade executed: {order_executed}")

def run_scheduler():
    print("Starting auto trading scheduler...")
    execute_trade()
    schedule.every().hour.do(execute_trade)
    
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()