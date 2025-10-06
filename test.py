#!/usr/bin/env python3
"""
Test script demonstrating dynamic configuration reading.
"""

import os
import time
import threading
from config_manager import config, get_trading_config, is_trading_enabled, get_max_investment

# Test environment variable (from remote)
print(os.getenv("OPENAI_API_KEY"))

def simulate_trading_loop():
    """Simulate a trading loop that reads config dynamically."""
    print("Starting trading simulation...")
    
    for i in range(10):
        # Read config values dynamically - they will auto-update if file changes
        if is_trading_enabled():
            max_investment = get_max_investment()
            currency = config.get('trading.default_currency', 'KRW')
            risk_level = config.get('trading.risk_level', 'medium')
            
            print(f"Iteration {i+1}: Trading enabled")
            print(f"  Max investment: {max_investment} {currency}")
            print(f"  Risk level: {risk_level}")
            
            # Simulate some trading logic
            print(f"  Executing trade with current config...")
        else:
            print(f"Iteration {i+1}: Trading disabled - skipping")
        
        print(f"  Config last modified: {time.ctime(config.last_modified)}")
        print("-" * 50)
        
        # Wait 5 seconds - during this time you can modify config.json
        time.sleep(5)
    
    print("Trading simulation completed.")

def config_monitor():
    """Monitor config changes in a separate thread."""
    print("Config monitor started. Watching for changes...")
    
    while True:
        if config.check_and_reload():
            print("🔄 Config file changed! New values loaded.")
            
            # Print current trading config
            trading_config = get_trading_config()
            print(f"Current trading config: {trading_config}")
        
        time.sleep(2)  # Check every 2 seconds

def test_config_operations():
    """Test various configuration operations."""
    print("=== Testing Configuration Operations ===")
    
    # Test reading values
    print("1. Reading configuration values:")
    print(f"   Trading enabled: {config.get('trading.trading_enabled')}")
    print(f"   Max investment: {config.get('trading.max_investment_amount')}")
    print(f"   API key exists: {'Yes' if config.get('api.upbit_access_key') else 'No'}")
    print(f"   Dashboard port: {config.get('dashboard.port')}")
    
    # Test getting sections
    print("\n2. Getting configuration sections:")
    trading_section = config.get_section('trading')
    print(f"   Trading section: {trading_section}")
    
    # Test updating values
    print("\n3. Updating configuration values:")
    original_amount = config.get('trading.max_investment_amount')
    print(f"   Original max investment: {original_amount}")
    
    config.set('trading.max_investment_amount', 200000)
    new_amount = config.get('trading.max_investment_amount')
    print(f"   Updated max investment: {new_amount}")
    
    # Test nested value creation
    config.set('trading.new_feature.enabled', True)
    print(f"   New nested value: {config.get('trading.new_feature.enabled')}")
    
    # Test default values
    print("\n4. Testing default values:")
    non_existent = config.get('non.existent.key', 'default_value')
    print(f"   Non-existent key with default: {non_existent}")

def main():
    """Main function to demonstrate different usage patterns."""
    print("🚀 Dynamic Configuration Demo")
    print("=" * 60)
    
    # Test basic operations
    test_config_operations()
    
    print("\n" + "=" * 60)
    print("📊 Live Configuration Monitoring Demo")
    print("Try editing config.json while this runs...")
    print("=" * 60)
    
    # Start config monitor in background thread
    monitor_thread = threading.Thread(target=config_monitor, daemon=True)
    monitor_thread.start()
    
    # Run trading simulation
    try:
        simulate_trading_loop()
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    
    print("\n✅ Demo completed!")

if __name__ == "__main__":
    main()
