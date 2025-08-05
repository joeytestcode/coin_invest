import os
from dotenv import load_dotenv
import requests
import json
load_dotenv()

target = "ETH"  # Target cryptocurrency
target_name = "Ethereum"
target_kicker = f"KRW-{target}"  # Upbit ticker for the target cryptocurrency

# target = "ETH"  # Target cryptocurrency
# target_name = "Ethereum"
# target_kicker = f"KRW-{target}"  # Upbit ticker for the target cryptocurrency

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

    response = requests.get(api_url, params=params)
    response.raise_for_status() # 기본적인 HTTP 오류는 확인
    results = response.json()

    if "news_results" in results:
        for news_item in results["news_results"][:num_results]:
            news_data.append({
                "title": news_item.get("title"),
                "date": news_item.get("date")
            })
    return news_data

def ai_trade():
    #1. Take upbit chart data
    import pyupbit

    short_term_df = pyupbit.get_ohlcv(target_kicker, interval="minute60", count=24)   # 단기: 1시간봉 24개
    mid_term_df = pyupbit.get_ohlcv(target_kicker, interval="minute240", count=30)     # 중기: 4시간봉 30개
    long_term_df = pyupbit.get_ohlcv(target_kicker, interval="day", count=30)           # 장기: 일봉 30개

    #1-1. Get news data
    news_articles = []
    if os.getenv("SERAPI_API_KEY"): # 키가 있을 때만 호출 시도
        news_articles = get_crypto_news(
            api_key=os.getenv("SERAPI_API_KEY"), query=f"{target_name} news",
            location="us", language="en", num_results=5
        )

    data_payload = {
        "short_term": json.loads(short_term_df.to_json()),
        "mid_term": json.loads(mid_term_df.to_json()),
        "long_term": json.loads(long_term_df.to_json()),
        "news": news_articles
    }

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

    print()
    print()
    print('### AI Decision : ', result['decision'].upper(), result['percentage'], '% ###')
    print('### Reason : ', result['reason'], '###')


    # Auto investment based on the response

    upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
    percentage = result.get("percentage", 0) / 100

    if result["decision"] == "buy":
        my_balance = upbit.get_balance("KRW")
        amount = my_balance * 0.9995 * percentage
        if amount > 5000:
            print(f"Buying ${target} with available KRW")
            print(upbit.buy_market_order(target_kicker, amount))  # Buy with 10% of available KRW
            print("buy : ", result["reason"])
            # Here you would implement the logic to buy cryptocurrency using Upbit API
        else:
            print("Not enough KRW to buy ${target}")
    elif result["decision"] == "sell":
        my_crypto_balance = upbit.get_balance(target_kicker)
        current_price = pyupbit.get_orderbook(target_kicker)['orderbook_units'][0]['ask_price']
        btc_amount = my_crypto_balance * percentage
        value = btc_amount * current_price
        if value > 5000:
            print(f"Selling ${target}")
            print(upbit.sell_market_order(target_kicker, btc_amount))  # Sell all ${target}
            print("sell : ", result["reason"])
            # Here you would implement the logic to sell cryptocurrency using Upbit API
        else:
            print(f"Not enough {target} to sell")
    elif result["decision"] == "hold":
        print(f"Holding {target}")
        print("hold : ", result["reason"])
        # Here you would implement the logic to hold cryptocurrency, maybe do nothing

if __name__ == "__main__":
    while True:
        ai_trade()  # Call the trading function

        import time
        time.sleep(60 * 60)  # Sleep for 1 hour