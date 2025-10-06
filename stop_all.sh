#!/bin/bash

# Stop all crypto trading processes
echo "🛑 Stopping all crypto trading processes..."

# Find and kill autotrade.py processes
AUTOTRADE_PIDS=$(pgrep -f "python.*autotrade.py")
if [ ! -z "$AUTOTRADE_PIDS" ]; then
    echo "📈 Stopping trading bot processes..."
    for pid in $AUTOTRADE_PIDS; do
        kill $pid 2>/dev/null && echo "✅ Stopped autotrade.py (PID: $pid)"
    done
else
    echo "ℹ️  No trading bot processes found"
fi

# Find and kill streamlit processes running autotrade_dashboard.py
DASHBOARD_PIDS=$(pgrep -f "streamlit.*autotrade_dashboard.py")
if [ ! -z "$DASHBOARD_PIDS" ]; then
    echo "📊 Stopping dashboard processes..."
    for pid in $DASHBOARD_PIDS; do
        kill $pid 2>/dev/null && echo "✅ Stopped dashboard (PID: $pid)"
    done
else
    echo "ℹ️  No dashboard processes found"
fi

# Also check for the control dashboard
CONTROL_DASHBOARD_PIDS=$(pgrep -f "streamlit.*dashboard.py")
if [ ! -z "$CONTROL_DASHBOARD_PIDS" ]; then
    echo "🎛️  Stopping control dashboard processes..."
    for pid in $CONTROL_DASHBOARD_PIDS; do
        kill $pid 2>/dev/null && echo "✅ Stopped control dashboard (PID: $pid)"
    done
else
    echo "ℹ️  No control dashboard processes found"
fi

echo ""
echo "🏁 All crypto trading processes have been stopped!"
echo "💡 You can restart them using:"
echo "   ./run_autotrade.sh (background mode)"
echo "   ./run_separate.sh (separate terminals)"
