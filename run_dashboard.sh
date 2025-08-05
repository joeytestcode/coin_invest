#!/bin/bash

# Crypto Auto Trading Dashboard Launcher
echo "🚀 Starting Crypto Auto Trading..."

# Check if we're in the right directory
if [ ! -f "autotrade_dashboard.py" ]; then
    echo "❌ Error: autotrade_dashboard.py not found. Please run this script from the project directory."
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

echo "🌐 Starting Streamlit dashboard..."
echo "📱 Dashboard will open at: http://localhost:8501"
echo "⏹️  Press Ctrl+C to stop the dashboard"
echo ""

streamlit run autotrade_dashboard.py --server.headless true