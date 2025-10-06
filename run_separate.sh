#!/bin/bash

# Crypto Auto Trading Separate Launcher (Individual Bots)
echo "🚀 Starting Individual Crypto Trading Bots in separate terminals..."

# Check if we're in the right directory
if [ ! -f "autotrade.py" ]; then
    echo "❌ Error: autotrade.py not found. Please run this script from the project directory."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found. Please create .env file with your API keys."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment not found. Please run the setup first."
    exit 1
fi

# Get the current directory
CURRENT_DIR=$(pwd)

# Function to start processes in new terminal windows
start_in_terminal() {
    local title="$1"
    local command="$2"
    
    # Try different terminal emulators
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal --title="$title" --working-directory="$CURRENT_DIR" -- bash -c "source .venv/bin/activate && export \$(cat .env | xargs) && $command; echo 'Press Enter to close...'; read"
    elif command -v xterm &> /dev/null; then
        xterm -title "$title" -e "bash -c 'cd $CURRENT_DIR && source .venv/bin/activate && export \$(cat .env | xargs) && $command; echo \"Press Enter to close...\"; read'" &
    elif command -v konsole &> /dev/null; then
        konsole --title "$title" --workdir "$CURRENT_DIR" -e bash -c "source .venv/bin/activate && export \$(cat .env | xargs) && $command; echo 'Press Enter to close...'; read" &
    else
        echo "⚠️  No supported terminal emulator found. Running in background instead..."
        source .venv/bin/activate
        # Load environment variables from .env file
        export $(cat .env | xargs)
        if [ "$title" = "Trading Bot" ]; then
            python autotrade.py > trading_bot.log 2>&1 &
            echo "📈 Trading bot started in background (check trading_bot.log for output)"
        else
            streamlit run autotrade_dashboard.py --server.headless true > dashboard.log 2>&1 &
            echo "📊 Dashboard started in background (check dashboard.log for output)"
        fi
        return
    fi
}

echo "📈 Starting individual trading bots in separate terminals..."
start_in_terminal "ETH Trading Bot" "python autotrade_eth.py"
sleep 1
start_in_terminal "XRP Trading Bot" "python autotrade_xrp.py"

echo "⏳ Waiting 3 seconds for trading bots to initialize..."
sleep 3

echo "📊 Starting dashboard in new terminal..."
start_in_terminal "Trading Dashboard" "streamlit run autotrade_dashboard.py"


echo ""
echo "🎉 All services have been started in separate terminals!"
echo "📈 ETH Trading Bot: Running autotrade_eth.py"
echo "📈 XRP Trading Bot: Running autotrade_xrp.py"
echo "📊 Dashboard: Available at http://localhost:8501"
echo ""
echo "💡 To stop the services:"
echo "   - Close the terminal windows, or"
echo "   - Press Ctrl+C in each terminal"
echo ""
echo "📝 If terminals didn't open, check the log files:"
echo "   - trading_bot.log (for trading bot output)"
echo "   - dashboard.log (for dashboard output)"
