# Crypto Auto Trading Dashboard

An interactive Streamlit dashboard for controlling and monitoring cryptocurrency auto-trading operations.

## Features

- **Start/Stop Trading**: Easy controls to start and stop the auto trading process
- **Trading Interval Control**: Configurable time intervals (5 minutes to 24 hours)
- **Trading Decisions Board**: Clean display of AI decisions, percentages, reasons, and trade results
- **Full Output Console**: Complete log of all trading activities
- **Trading Statistics**: View decision counts and latest trade information

## Setup

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your environment variables in a `.env` file:
```
UPBIT_ACCESS_KEY=your_upbit_access_key
UPBIT_SECRET_KEY=your_upbit_secret_key
OPENAI_API_KEY=your_openai_api_key
SERAPI_API_KEY=your_serapi_key (optional)
```

## Running the Dashboard

1. Start the Streamlit dashboard:
```bash
streamlit run dashboard.py
```

2. Open your browser to the displayed URL (usually http://localhost:8501)

3. Configure your trading interval in the sidebar (5 minutes to 24 hours)

4. Use the sidebar controls to start/stop trading and monitor the results

## Dashboard Layout

### Sidebar Controls
- **Start/Stop Trading**: Control the auto trading process
- **Trading Interval**: Select from 5 minutes to 24 hours
- **Current Configuration**: View target cryptocurrency
- **Clear All Logs**: Reset both decision board and output console

### Main Dashboard
- **Trading Decisions Tab**: Clean view of AI decisions, percentages, reasons, and trade results
- **Full Output Console Tab**: Complete log output for debugging
- **Trading Summary**: Statistics and latest decision overview

## Features Details

### Trading Decisions Board
- Shows the last 10 trading decisions in an expandable format
- Displays action (BUY/SELL/HOLD), percentage, timestamp
- Includes AI reasoning and actual trade execution details
- Color-coded actions: 🟢 BUY, 🔴 SELL, 🟡 HOLD

### Time Interval Control
- Configurable intervals: 5min, 15min, 30min, 1hr, 2hr, 4hr, 12hr, 24hr
- Can only be changed when trading is stopped
- Default interval is 1 hour

### Auto-Refresh
- Dashboard automatically refreshes every 5 seconds during active trading
- Manual refresh button available when trading is stopped

## Files

- `dashboard.py`: Main Streamlit dashboard application
- `autotrade_dashboard.py`: Modified trading logic optimized for dashboard integration
- `autotrade.py`: Original trading script (unchanged)
- `requirements.txt`: Python dependencies

## Safety Features

- Graceful shutdown handling
- Real-time output capture and parsing
- Error logging and display
- Configurable trading intervals
- Clean separation of decision summary and detailed logs
