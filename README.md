# Crypto Auto Trading Dashboard

An interactive Streamlit dashboard for controlling and monitoring cryptocurrency auto-trading operations.

## Features

- **Start/Stop Trading**: Easy controls to start and stop the auto trading process
- **Trading Interval Control**: Configurable time intervals (5 minutes to 24 hours)
- **Trading Decisions Board**: Clean display of AI decisions, percentages, reasons, and trade results
- **Full Output Console**: Complete log of all trading activities
- **Trading Statistics**: View decision counts and latest trade information
- **Slack Notifications**: Real-time DM alerts for every trade decision and execution
- **Multi-Database Support**: View and compare data from multiple trading sessions
- **Database Management**: Create, select, and analyze different trading databases
- **Stale Data Monitoring**: Automatic alerts when trading data becomes stale (5+ hours old)
- **Database Health Dashboard**: Monitor freshness across all database files

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

# Slack Notifications (optional)
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_USER_ID=your-slack-user-id
```

3. **Optional: Set up Slack notifications**
   - Follow the guide in `SLACK_SETUP.md` to create a Slack bot
   - Test your setup with: `python test_slack.py`

4. **Optional: Create sample databases for testing**
   - Generate sample trading data: `python create_sample_dbs.py`
   - Test multi-database features in the dashboard

## Running the Applications

You have several options to run the crypto trading system:

### Option 1: Control Dashboard (Recommended)
Use the integrated control dashboard that manages everything:
```bash
streamlit run dashboard.py
```
- ✅ Full control over trading process
- ✅ Live monitoring and decision tracking
- ✅ Built-in process management
- ✅ State persistence across browser sessions

### Option 2: Separate Trading Bot + Data Dashboard
Run the trading bot and data visualization separately:

**Method A: Background Mode**
```bash
./run_autotrade.sh
```
- Runs both `autotrade.py` and `autotrade_dashboard.py` in background
- Press Ctrl+C to stop both services
- Both services run in the same terminal

**Method B: Separate Terminals**
```bash
./run_separate.sh
```
- Opens `autotrade.py` in one terminal window
- Opens `autotrade_dashboard.py` in another terminal window
- Better for monitoring each service separately

### Option 3: Manual Execution
```bash
# Terminal 1: Trading bot
python autotrade.py

# Terminal 2: Data dashboard (different port)
streamlit run autotrade_dashboard.py --server.port 8502

# Terminal 3: Control dashboard (optional)
streamlit run dashboard.py --server.port 8501
```

### Stopping Services
```bash
./stop_all.sh
```
This will stop all running trading and dashboard processes.

## Dashboard Ports
- **Control Dashboard**: http://localhost:8501 (dashboard.py)
- **Data Dashboard**: http://localhost:8501 or 8502 (autotrade_dashboard.py)

## File Descriptions

### Core Trading Files
- `autotrade.py`: Main trading logic with database integration
- `autotrade_dashboard.py`: Multi-database data visualization dashboard (charts, tables, history comparison)

### Control & Management
- `dashboard.py`: Process control dashboard with live monitoring
- `run_autotrade.sh`: Launch script for background mode
- `run_separate.sh`: Launch script for separate terminals
- `stop_all.sh`: Stop all trading processes

### Database & Testing
- `create_sample_dbs.py`: Create sample databases for testing dashboard features
- `test_slack.py`: Test Slack integration setup

### Configuration
- `requirements.txt`: Python dependencies
- `.env`: Environment variables (API keys)

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
