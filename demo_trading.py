#!/usr/bin/env python3
"""
Demo script to simulate trading decisions for testing the dashboard bulletin board
"""
import time
import random
from datetime import datetime

def simulate_trading_decision():
    """Simulate a trading decision output"""
    decisions = ["BUY", "SELL", "HOLD"]
    decision = random.choice(decisions)
    percentage = random.randint(10, 100)
    
    reasons = [
        "Strong bullish momentum detected with RSI oversold conditions",
        "Bearish divergence observed, recommend taking profits",
        "Market consolidation phase, maintaining current position",
        "Breaking through resistance level with high volume",
        "Support level holding strong, good entry opportunity",
        "Negative news sentiment affecting market confidence"
    ]
    reason = random.choice(reasons)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Simulate the log output format that the dashboard expects
    print(f"[{timestamp}] Starting AI trade analysis...")
    time.sleep(0.5)
    print(f"[{timestamp}] Fetching market data...")
    time.sleep(0.5)
    print(f"[{timestamp}] Fetching news data...")
    time.sleep(0.5)
    print(f"[{timestamp}] Found 3 news articles")
    time.sleep(0.5)
    print(f"[{timestamp}] Analyzing data with AI...")
    time.sleep(1)
    print(f"[{timestamp}] AI Response: {{\"decision\":\"{decision.lower()}\", \"percentage\": {percentage}, \"reason\":\"{reason}\"}}")
    time.sleep(0.5)
    print(f"[{timestamp}] AI Decision: {decision} {percentage}%")
    time.sleep(0.5)
    print(f"[{timestamp}] Reason: {reason}")
    time.sleep(0.5)
    print(f"[{timestamp}] Executing trade decision...")
    
    if decision == "BUY":
        amount = random.randint(50000, 500000)
        print(f"[{timestamp}] Available KRW balance: {amount*2:,.0f}")
        print(f"[{timestamp}] Amount to invest: {amount:,.0f} KRW ({percentage}%)")
        print(f"[{timestamp}] Buying ETH with {amount:,.0f} KRW")
        print(f"[{timestamp}] Buy order result: {{'uuid': 'test-{random.randint(1000,9999)}', 'side': 'bid', 'ord_type': 'market'}}")
    elif decision == "SELL":
        eth_amount = random.uniform(0.01, 0.5)
        krw_value = random.randint(30000, 300000)
        print(f"[{timestamp}] Available ETH balance: {eth_amount:.4f}")
        print(f"[{timestamp}] Amount to sell: {eth_amount*percentage/100:.4f} ETH ({percentage}%)")
        print(f"[{timestamp}] Estimated value: {krw_value:,.0f} KRW")
        print(f"[{timestamp}] Selling {eth_amount*percentage/100:.4f} ETH")
        print(f"[{timestamp}] Sell order result: {{'uuid': 'test-{random.randint(1000,9999)}', 'side': 'ask', 'ord_type': 'market'}}")
    else:
        print(f"[{timestamp}] Holding ETH")
    
    print(f"[{timestamp}] Waiting {random.choice([5, 15, 30, 60])} minutes for next trade cycle...")

def main():
    """Run the demo simulation"""
    print("🎭 Starting Trading Decision Simulation")
    print("This will generate sample trading decisions to test the dashboard bulletin board")
    print("Run this while the dashboard is active to see the bulletin board in action")
    print("-" * 60)
    
    try:
        for i in range(5):  # Generate 5 sample decisions
            print(f"\n=== Trading Cycle {i+1} ===")
            simulate_trading_decision()
            if i < 4:  # Don't sleep after the last iteration
                time.sleep(3)  # Short delay between cycles for demo
        
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Demo simulation completed!")
        print("Check the dashboard to see how the trading decisions appear in the bulletin board.")
        
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Demo simulation stopped by user")

if __name__ == "__main__":
    main()
