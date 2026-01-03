# Crypto Auto Trading System

A streamlined cryptocurrency auto-trading system with a monitoring dashboard.

## Features

- **Multi-Coin Support**: Trade multiple cryptocurrencies (ETH, XRP, etc.) simultaneously.
- **AI-Powered Decisions**: Uses AI to analyze market data and news for trading decisions.
- **Monitoring Dashboard**: Real-time dashboard to view trading status and history.
- **Slack Notifications**: Get alerts for trades and stale data.
- **Robust Architecture**: Decoupled trading bot and dashboard for stability.

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
SLACK_CHANNEL_ID=your-slack-channel-id
```

3. Configure coins in `config_coins.json`.

## Running the System

The easiest way to run the system is using the `run.sh` script, which launches the trading bot and the dashboard in separate terminals.

```bash
./run.sh
```

This will:
1. Start `autotrade.py` (The trading bot) in a new terminal.
2. Start `dashboard.py` (The monitoring dashboard) in a new terminal.
3. Start a Cloudflare tunnel (if configured).

## File Structure

- `autotrade.py`: Main trading bot logic. Handles multiple coins based on configuration.
- `dashboard.py`: Streamlit dashboard for monitoring trading activity and database status.
- `config_coins.json`: Configuration for cryptocurrencies to trade.
- `config_manager.py`: Configuration management utility.
- `run.sh`: Master launch script.
- `tests/`: Unit tests and debug scripts.
- `scripts/`: Utility scripts (e.g., creating sample DBs).

## Monitoring

The dashboard provides:
- **Database Status**: Checks if trading data is fresh.
- **Trade History**: View recent trades for each coin.
- **Stale Data Alerts**: Warns if the bot hasn't updated the database recently.

## Development

- Run tests: `python tests/test_slack.py`
- Create sample data: `python scripts/create_sample_dbs.py`
