import os
from dotenv import load_dotenv
import requests
load_dotenv()

def get_crypto_news(api_key, query="bitcoin", location="us", language="en", num_results=5):
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
    target = "ETH"  # Target cryptocurrency
    target_kicker = "KRW-${target}"  # Upbit ticker for the target cryptocurrency

    #1. Take upbit chart data
    import pyupbit

    df = pyupbit.get_ohlcv(target_kicker, interval="day", count=30)
    # print(df.to_json())

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
            "text": "You're a cryptocurrency investment expert.\nBased on the analysis of the given chart data, let me know whether I should buy, sell or hold at the moment. I have to get an answer in json format like the following sample answers.\n\nSample answer 1:\n{\"decision\":\"buy\", \"reason\":\"Some technical reason to buy based on analysis result\"}\nSample answer 2:\n{\"decision\":\"sell\", \"reason\":\"Some technical reason to sell based on analysis result\"}\nSample answer 3:\n{\"decision\":\"hold\", \"reason\":\"Some technical reason to hold based on analysis result\"}"
            }
        ]
        },
        {
        "role": "user",
        "content": [
            {
            "type": "input_text",
            "text": df.to_json()
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
    import json
    result = json.loads(result0)

    print('### AI Decision : ', result['decision'].upper(), '###')
    print('### Reason : ', result['reason'], '###')


    # Auto investment based on the response

    upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))

    if result["decision"] == "buy":
        my_balance = upbit.get_balance("KRW")
        if my_balance * 0.9995 > 5000:
            print("Buying ${target} with available KRW")
            print(upbit.buy_market_order(target_kicker, my_balance * 0.9995 * 0.1))  # Buy with 10% of available KRW
            print("buy : ", result["reason"])
            # Here you would implement the logic to buy cryptocurrency using Upbit API
        else:
            print("Not enough KRW to buy ${target}")
    elif result["decision"] == "sell":
        my_crypto_balance = upbit.get_balance(target_kicker)
        current_price = pyupbit.get_orderbook(target_kicker)['orderbook_units'][0]['ask_price']
        if my_crypto_balance * current_price > 5000:
            print("Selling ${target}")
            print(upbit.sell_market_order(target_kicker, my_crypto_balance))  # Sell all ${target}
            print("sell : ", result["reason"])
            # Here you would implement the logic to sell cryptocurrency using Upbit API
        else:
            print("Not enough ${target} to sell")
    elif result["decision"] == "hold":
        print("Holding ${target}")
        print("hold : ", result["reason"])
        # Here you would implement the logic to hold cryptocurrency, maybe do nothing

if __name__ == "__main__":
    while True:
        ai_trade()  # Call the trading function

        import time
        time.sleep(60 * 60)  # Sleep for 1 hour