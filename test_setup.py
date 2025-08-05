#!/usr/bin/env python3
"""
Test script to verify the dashboard setup
"""
import sys
import os

def test_imports():
    """Test if all required packages can be imported"""
    print("Testing imports...")
    
    try:
        import streamlit as st
        print("✅ Streamlit imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import Streamlit: {e}")
        return False
    
    try:
        import pyupbit
        print("✅ PyUpbit imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import PyUpbit: {e}")
        return False
    
    try:
        import openai
        print("✅ OpenAI imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import OpenAI: {e}")
        return False
        
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import python-dotenv: {e}")
        return False
    
    return True

def test_files():
    """Test if required files exist"""
    print("\nTesting files...")
    
    required_files = [
        "dashboard.py",
        "autotrade_dashboard.py", 
        "autotrade.py",
        "requirements.txt"
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} not found")
            all_exist = False
    
    return all_exist

def test_env_file():
    """Test if .env file exists (optional but recommended)"""
    print("\nTesting environment configuration...")
    
    if os.path.exists(".env"):
        print("✅ .env file exists")
        # Load and check for required keys
        from dotenv import load_dotenv
        load_dotenv()
        
        required_vars = ["UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY", "OPENAI_API_KEY"]
        optional_vars = ["SERAPI_API_KEY"]
        
        for var in required_vars:
            if os.getenv(var):
                print(f"✅ {var} is set")
            else:
                print(f"⚠️  {var} is not set (required for trading)")
        
        for var in optional_vars:
            if os.getenv(var):
                print(f"✅ {var} is set")
            else:
                print(f"ℹ️  {var} is not set (optional for news analysis)")
                
    else:
        print("⚠️  .env file not found - you'll need to set environment variables manually")

def main():
    print("🧪 Testing Crypto Auto Trading Dashboard Setup\n")
    
    # Test imports
    imports_ok = test_imports()
    
    # Test files
    files_ok = test_files()
    
    # Test environment
    test_env_file()
    
    print("\n" + "="*50)
    if imports_ok and files_ok:
        print("✅ Setup test PASSED! You can run the dashboard with:")
        print("   streamlit run dashboard.py")
    else:
        print("❌ Setup test FAILED! Please check the errors above.")
        return 1
    
    print("="*50)
    return 0

if __name__ == "__main__":
    sys.exit(main())
