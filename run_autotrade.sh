#!/bin/bash

# Crypto Auto Trading Dashboard Launcher
echo "🚀 Starting Crypto Auto Trading..."

# Check if we're in the right directory
if [ ! -f "autotrade.py" ]; then
    echo "❌ Error: autotrade.py not found. Please run this script from the project directory."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment not found. Please run the setup first."
    exit 1
fi

# Activate virtual environment and run streamlit
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

python  autotrade.py