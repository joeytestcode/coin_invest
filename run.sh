#!/bin/bash
cd /home/joeyhwang/Programming/works/pythonWorks/coin_invest/

# Crypto Auto Trading Separate Launcher
echo "🚀 Starting Crypto Auto Trading in separate terminals..."

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
        return
    fi
}

echo "📈 Starting multi-crypto trading bot in new terminal..."
start_in_terminal "Multi-Crypto Trading Bot" "python autotrade.py"

echo "⏳ Waiting 3 seconds for trading bot to initialize..."
sleep 3

echo "📊 Starting dashboard in new terminal..."
start_in_terminal "Trading Dashboard" "streamlit run dashboard.py --server.headless true"


echo ""
echo "🎉 Both services have been started in separate terminals!"
echo "📈 Multi-Crypto Trading Bot: Running autotrade.py (ETH + XRP)"
echo "📊 Dashboard: Available at http://localhost:8501"
echo ""
echo "💡 To stop the services:"
echo "   - Close the terminal windows, or"
echo "   - Press Ctrl+C in each terminal"
echo ""
echo "📝 If terminals didn't open, check the log files:"
echo "   - trading_bot.log (for trading bot output)"
echo "   - dashboard.log (for dashboard output)"

start_in_terminal "cloudflare connection for coin invest" "cloudflared tunnel run --token eyJhIjoiNjZkNmFiZTg5OGQ2ZmEzZmQxMjMzZmIxZWIyZWE0Y2IiLCJ0IjoiOTg0YzcyMzgtMzMwMC00NmU5LTliMTktYjY0ZmMzYzY0MjRkIiwicyI6IllURTJOR1l3TlRFdFptRmxaUzAwWmprM0xUa3pNV0V0TldWaVlUYzNPVFk1WWpFMCJ9"

