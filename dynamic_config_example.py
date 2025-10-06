#!/usr/bin/env python3
"""
Example of integrating dynamic configuration into a trading application.
This shows how your existing trading code can benefit from dynamic config.
"""

import time
import threading
from datetime import datetime
from config_manager import config, get_trading_config, is_trading_enabled

class CoinTrader:
    """Example trading class that uses dynamic configuration."""
    
    def __init__(self):
        self.running = False
        self.last_config_check = 0
        
    def start_trading(self):
        """Start the trading loop."""
        self.running = True
        print("🚀 Starting coin trading with dynamic configuration...")
        
        # Start config monitoring in background
        config_thread = threading.Thread(target=self._monitor_config, daemon=True)
        config_thread.start()
        
        while self.running:
            try:
                self._trading_iteration()
                
                # Sleep based on current config
                sleep_interval = config.get('dashboard.refresh_interval', 30)
                time.sleep(sleep_interval)
                
            except KeyboardInterrupt:
                print("\n🛑 Trading stopped by user")
                self.running = False
            except Exception as e:
                print(f"❌ Error in trading loop: {e}")
                time.sleep(5)  # Wait before retrying
    
    def _trading_iteration(self):
        """Single iteration of trading logic."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if not is_trading_enabled():
            print(f"[{timestamp}] 😴 Trading disabled - sleeping...")
            return
        
        # Get current configuration
        trading_config = get_trading_config()
        max_investment = trading_config.get('max_investment_amount', 0)
        currency = trading_config.get('default_currency', 'KRW')
        risk_level = trading_config.get('risk_level', 'medium')
        coins = trading_config.get('coins_to_trade', ['BTC'])
        
        print(f"[{timestamp}] 📊 Trading iteration")
        print(f"  💰 Max investment: {max_investment:,} {currency}")
        print(f"  ⚡ Risk level: {risk_level}")
        print(f"  🪙 Coins to trade: {', '.join(coins)}")
        
        # Simulate trading logic based on current config
        for coin in coins:
            self._analyze_coin(coin, max_investment, risk_level)
    
    def _analyze_coin(self, coin: str, max_investment: float, risk_level: str):
        """Analyze a specific coin for trading opportunities."""
        # Get dynamic configuration for this specific analysis
        stop_loss = config.get('trading.stop_loss_percentage', 5.0)
        take_profit = config.get('trading.take_profit_percentage', 10.0)
        
        print(f"    🔍 Analyzing {coin}")
        print(f"      Stop loss: {stop_loss}%")
        print(f"      Take profit: {take_profit}%")
        
        # Your actual trading logic would go here
        # For demo, just simulate decision making
        if risk_level == "high":
            investment_amount = max_investment * 0.8
        elif risk_level == "medium":
            investment_amount = max_investment * 0.5
        else:  # low risk
            investment_amount = max_investment * 0.2
        
        print(f"      Investment amount: {investment_amount:,.0f}")
    
    def _monitor_config(self):
        """Monitor configuration changes in background."""
        while self.running:
            if config.check_and_reload():
                print("🔄 Configuration updated! Trading parameters refreshed.")
                
                # You could trigger specific actions here
                new_config = get_trading_config()
                print(f"   New max investment: {new_config.get('max_investment_amount', 0):,}")
                print(f"   Trading enabled: {new_config.get('trading_enabled', False)}")
            
            time.sleep(2)  # Check every 2 seconds

class ConfigurableDashboard:
    """Example dashboard that responds to configuration changes."""
    
    def __init__(self):
        self.last_refresh = 0
    
    def run_dashboard(self):
        """Run dashboard with dynamic configuration."""
        print("📊 Starting configurable dashboard...")
        
        while True:
            try:
                self._update_dashboard()
                
                # Get current refresh interval from config
                refresh_interval = config.get('dashboard.refresh_interval', 30)
                time.sleep(refresh_interval)
                
            except KeyboardInterrupt:
                print("\n🛑 Dashboard stopped")
                break
    
    def _update_dashboard(self):
        """Update dashboard display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Get current configuration
        dashboard_config = config.get_section('dashboard')
        trading_config = get_trading_config()
        
        print(f"\n📊 Dashboard Update [{timestamp}]")
        print("=" * 50)
        print(f"Theme: {dashboard_config.get('theme', 'light')}")
        print(f"Auto-refresh: {dashboard_config.get('auto_refresh', True)}")
        print(f"Refresh interval: {dashboard_config.get('refresh_interval', 30)}s")
        print()
        print("Trading Status:")
        print(f"  Enabled: {trading_config.get('trading_enabled', False)}")
        print(f"  Max Investment: {trading_config.get('max_investment_amount', 0):,}")
        print(f"  Risk Level: {trading_config.get('risk_level', 'medium')}")
        print("=" * 50)

def demo_dynamic_config():
    """Demonstrate dynamic configuration in action."""
    print("🎯 Dynamic Configuration Demo")
    print("=" * 60)
    print("This demo shows how your trading app can respond to config changes in real-time.")
    print("Try editing config.json while this is running!")
    print("=" * 60)
    
    # Show current configuration
    print("\n📋 Initial Configuration:")
    trading_config = get_trading_config()
    for key, value in trading_config.items():
        print(f"  {key}: {value}")
    
    print("\n🚀 Starting trader...")
    trader = CoinTrader()
    
    try:
        trader.start_trading()
    except KeyboardInterrupt:
        print("\n✅ Demo completed!")

if __name__ == "__main__":
    demo_dynamic_config()