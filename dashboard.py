import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
import json
import requests as http_requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ──────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Crypto AI Trading Dashboard",
    page_icon="📈",
    layout="wide",
)

# ──────────────────────────────────────────────────────────────────────
# Constants & helpers
# ──────────────────────────────────────────────────────────────────────
STALE_DATA_THRESHOLD_HOURS = 7
NOTIFICATION_STATE_FILE = "dashboard_state/notification_tracking.json"
CONFIG_FILE = "config_coins.json"

def get_notification_method():
    """Read notification_method from config_coins.json."""
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        return cfg.get("notification_method", "slack")
    except Exception:
        return "slack"

os.makedirs("dashboard_state", exist_ok=True)

# Coin colour palette (deterministic per symbol)
COIN_COLORS = {
    "BTC": "#F7931A",
    "ETH": "#627EEA",
    "XRP": "#00AAE4",
    "SOL": "#9945FF",
    "ADA": "#0033AD",
    "DOT": "#E6007A",
    "DOGE": "#C2A633",
    "AVAX": "#E84142",
}
DEFAULT_COLORS = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3"]


def coin_color(symbol: str, idx: int = 0) -> str:
    return COIN_COLORS.get(symbol, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)])


# ──────────────────────────────────────────────────────────────────────
# Config loading
# ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_coin_config():
    """Load coin configuration from config_coins.json."""
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        return {
            sym: info
            for sym, info in cfg.get("coins", {}).items()
            if info.get("enabled", False)
        }
    except Exception as e:
        st.error(f"Failed to load config: {e}")
        return {}


# ──────────────────────────────────────────────────────────────────────
# Notification helpers (kept from original)
# ──────────────────────────────────────────────────────────────────────
def load_notification_state():
    try:
        if os.path.exists(NOTIFICATION_STATE_FILE):
            with open(NOTIFICATION_STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_notification_state(state):
    try:
        with open(NOTIFICATION_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def send_stale_data_notification(db_name, last_update_time, hours_stale):
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    slack_channel_id = os.getenv("SLACK_CHANNEL_ID")
    if not slack_token or not slack_channel_id:
        return False
    try:
        client = WebClient(token=slack_token)
        message = (
            f"⚠️ *Trading Bot Alert – Stale Data*\n"
            f"*Database:* `{db_name}`\n"
            f"*Last Update:* {last_update_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"*Hours Since Update:* {hours_stale:.1f}\n"
        )
        client.chat_postMessage(
            channel=slack_channel_id,
            text=message,
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": message}}],
        )
        return True
    except Exception:
        return False


def send_telegram_stale_data_notification(db_name, last_update_time, hours_stale):
    """Send stale data alert to Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return False
    try:
        message = (
            f"⚠️ <b>Trading Bot Alert – Stale Data</b>\n"
            f"<b>Database:</b> <code>{db_name}</code>\n"
            f"<b>Last Update:</b> {last_update_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"<b>Hours Since Update:</b> {hours_stale:.1f}\n"
        )
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = http_requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        resp.raise_for_status()
        return True
    except Exception:
        return False


def check_database_freshness(db_name, df):
    if df.empty:
        return
    latest_ts = df["timestamp"].max()
    if latest_ts.tz is not None:
        latest_ts = latest_ts.tz_convert(None)
    hours_stale = (datetime.now() - latest_ts).total_seconds() / 3600
    if hours_stale <= STALE_DATA_THRESHOLD_HOURS:
        return
    ns = load_notification_state()
    key = f"{db_name}_last_notification"
    should_notify = True
    if ns.get(key):
        try:
            if (datetime.now() - datetime.fromisoformat(ns[key])).total_seconds() < 86400:
                should_notify = False
        except Exception:
            pass
    if should_notify:
        notif_method = get_notification_method()
        sent = send_stale_data_notification(db_name, latest_ts, hours_stale) if notif_method in ("slack", "both") else False
        sent_tg = send_telegram_stale_data_notification(db_name, latest_ts, hours_stale) if notif_method in ("telegram", "both") else False
        if sent or sent_tg:
            ns[key] = datetime.now().isoformat()
            save_notification_state(ns)


# ──────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────
def load_trade_data(db_name: str) -> pd.DataFrame:
    """Load and enrich trade data from a single database."""
    if not os.path.exists(db_name):
        return pd.DataFrame()
    try:
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='trades'"
            )
            if not cursor.fetchone():
                return pd.DataFrame()
            df = pd.read_sql_query("SELECT * FROM trades ORDER BY timestamp", conn)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["portfolio_value"] = df["krw_balance"] + df["crypto_balance"] * df["crypto_price"]
    if len(df) > 0:
        first_val = df.iloc[0]["portfolio_value"]
        df["profit_loss"] = df["portfolio_value"] - first_val
        df["profit_loss_pct"] = (df["profit_loss"] / first_val) * 100 if first_val else 0

    check_database_freshness(db_name, df)
    return df


@st.cache_data(ttl=60)
def load_all_coin_data(_coins_config_json: str) -> dict:
    """Load trade data for every enabled coin.  Returns {symbol: DataFrame}."""
    coins_config = json.loads(_coins_config_json)
    data = {}
    for sym, info in coins_config.items():
        db = info.get("db_name", "")
        df = load_trade_data(db)
        if not df.empty:
            df["symbol"] = sym
            data[sym] = df
    return data


# ──────────────────────────────────────────────────────────────────────
# Aggregate helpers
# ──────────────────────────────────────────────────────────────────────
def build_total_portfolio_series(all_data: dict) -> pd.DataFrame:
    """
    Build a time-series of total portfolio value.

    Each coin records its own (krw_balance + crypto_value).  Since KRW
    balance is shared across coins, we take the latest KRW balance
    reported at each timestamp and add each coin's crypto value.
    """
    if not all_data:
        return pd.DataFrame()

    frames = []
    for sym, df in all_data.items():
        s = df.set_index("timestamp")[["crypto_balance", "crypto_price", "krw_balance"]].copy()
        s[f"crypto_value_{sym}"] = s["crypto_balance"] * s["crypto_price"]
        s = s.rename(columns={"krw_balance": f"krw_{sym}"})
        s = s[[f"crypto_value_{sym}", f"krw_{sym}"]]
        frames.append(s)

    combined = pd.concat(frames, axis=1).sort_index().ffill().dropna()

    if combined.empty:
        return pd.DataFrame()

    crypto_cols = [c for c in combined.columns if c.startswith("crypto_value_")]
    krw_cols = [c for c in combined.columns if c.startswith("krw_")]

    combined["total_crypto"] = combined[crypto_cols].sum(axis=1)
    # KRW is shared – take max (they should be nearly identical at any point)
    combined["krw"] = combined[krw_cols].max(axis=1)
    combined["total_value"] = combined["total_crypto"] + combined["krw"]

    result = combined[["total_value", "krw", "total_crypto"]].reset_index()
    result = result.rename(columns={"index": "timestamp"})
    return result


def filter_by_time(df: pd.DataFrame, hours) -> pd.DataFrame:
    """Filter dataframe to the last N hours.  None = all data."""
    if hours is None or df.empty:
        return df
    cutoff = datetime.now() - timedelta(hours=hours)
    return df[df["timestamp"] >= cutoff]


# ──────────────────────────────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────────────────────────────
coins_config = load_coin_config()
all_data = load_all_coin_data(json.dumps(coins_config))

st.title("📈 Crypto AI Trading Dashboard")

if not all_data:
    st.warning("No trading data found. Start the trading bot to generate data.")
    st.stop()

# ── Sidebar: settings & monitoring ──────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    TIME_OPTIONS = {
        "6h": 6,
        "12h": 12,
        "24h": 24,
        "3d": 72,
        "7d": 168,
        "30d": 720,
        "All": None,
    }
    selected_range_label = st.radio(
        "Time Range (applies to all charts)",
        list(TIME_OPTIONS.keys()),
        index=3,  # default 3d
        horizontal=True,
    )
    selected_hours = TIME_OPTIONS[selected_range_label]

    st.markdown("---")
    st.subheader("📊 Coin Status")
    for sym, info in coins_config.items():
        db = info.get("db_name", "")
        if sym in all_data and not all_data[sym].empty:
            latest_ts = all_data[sym]["timestamp"].max()
            if latest_ts.tz is not None:
                latest_ts = latest_ts.tz_convert(None)
            hrs = (datetime.now() - latest_ts).total_seconds() / 3600
            trades = len(all_data[sym])
            icon = "🟢" if hrs < 2 else ("🟡" if hrs < STALE_DATA_THRESHOLD_HOURS else "🔴")
            st.markdown(f"{icon} **{sym}** — {trades} trades, last {hrs:.1f}h ago")
        else:
            st.markdown(f"⚪ **{sym}** — no data")

    st.markdown("---")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Auto-refresh
    auto_refresh = st.checkbox("Auto-refresh every 60s", value=False)
    if auto_refresh:
        import time as _time
        _time.sleep(60)
        st.rerun()

# ──────────────────────────────────────────────────────────────────────
# SECTION 1 – Portfolio Overview Metrics
# ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("💰 Portfolio Overview")

# Calculate latest values per coin
latest_rows = {}
total_crypto_value = 0
total_krw = 0
for sym, df in all_data.items():
    latest = df.iloc[-1]
    latest_rows[sym] = latest
    total_crypto_value += latest["crypto_balance"] * latest["crypto_price"]

# KRW is shared; take the most recent report
if latest_rows:
    most_recent_sym = max(latest_rows, key=lambda s: latest_rows[s]["timestamp"])
    total_krw = latest_rows[most_recent_sym]["krw_balance"]

total_value = total_krw + total_crypto_value

# Headline metrics
cols = st.columns(2 + len(all_data))
with cols[0]:
    st.metric("Total Portfolio", f"₩{total_value:,.0f}")
with cols[1]:
    st.metric("Cash (KRW)", f"₩{total_krw:,.0f}")

for i, (sym, row) in enumerate(latest_rows.items()):
    cv = row["crypto_balance"] * row["crypto_price"]
    with cols[2 + i]:
        st.metric(
            f"{sym}",
            f"₩{cv:,.0f}",
            delta=f"{row['crypto_balance']:.6f} {sym}",
        )

# ──────────────────────────────────────────────────────────────────────
# SECTION 2 – Total Balance Over Time
# ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📊 Total Portfolio Value Over Time")

portfolio_ts = build_total_portfolio_series(all_data)

if not portfolio_ts.empty:
    pts = filter_by_time(portfolio_ts, selected_hours)

    fig_portfolio = go.Figure()
    fig_portfolio.add_trace(
        go.Scatter(
            x=pts["timestamp"],
            y=pts["total_value"],
            mode="lines",
            name="Total Portfolio",
            line=dict(color="#1f77b4", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(31,119,180,0.10)",
        )
    )
    fig_portfolio.add_trace(
        go.Scatter(
            x=pts["timestamp"],
            y=pts["krw"],
            mode="lines",
            name="Cash (KRW)",
            line=dict(color="#2ca02c", width=1, dash="dot"),
        )
    )
    fig_portfolio.add_trace(
        go.Scatter(
            x=pts["timestamp"],
            y=pts["total_crypto"],
            mode="lines",
            name="Crypto Total",
            line=dict(color="#ff7f0e", width=1, dash="dot"),
        )
    )
    fig_portfolio.update_layout(
        hovermode="x unified",
        yaxis_title="Value (KRW)",
        yaxis_tickformat=",.0f",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420,
        margin=dict(l=40, r=20, t=30, b=40),
    )
    st.plotly_chart(fig_portfolio, use_container_width=True)
else:
    st.info("Not enough data to build portfolio time-series.")

# ──────────────────────────────────────────────────────────────────────
# SECTION 3 – Individual Crypto Price Changes
# ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📈 Crypto Price Changes")

# Let user choose between overlaid (normalised %) or side-by-side
price_mode = st.radio(
    "Display mode",
    ["Normalised % Change", "Absolute Price (subplots)"],
    horizontal=True,
)

if price_mode == "Normalised % Change":
    fig_prices = go.Figure()
    fig_prices.add_hline(y=0, line=dict(color="gray", width=1, dash="dash"))

    for idx, (sym, df) in enumerate(all_data.items()):
        dff = filter_by_time(df, selected_hours)
        if dff.empty:
            continue
        base_price = dff.iloc[0]["crypto_price"]
        if base_price == 0:
            continue
        pct = ((dff["crypto_price"] - base_price) / base_price) * 100

        fig_prices.add_trace(
            go.Scatter(
                x=dff["timestamp"],
                y=pct,
                mode="lines+markers",
                name=sym,
                line=dict(color=coin_color(sym, idx), width=2),
                marker=dict(size=4),
            )
        )

        # Mark buy/sell
        for decision, marker_sym, size in [("buy", "triangle-up", 12), ("sell", "triangle-down", 12)]:
            dec_df = dff[dff["decision"] == decision]
            if dec_df.empty:
                continue
            dec_pct = ((dec_df["crypto_price"] - base_price) / base_price) * 100
            fig_prices.add_trace(
                go.Scatter(
                    x=dec_df["timestamp"],
                    y=dec_pct,
                    mode="markers",
                    name=f"{sym} {decision.upper()}",
                    marker=dict(
                        color="green" if decision == "buy" else "red",
                        size=size,
                        symbol=marker_sym,
                        line=dict(width=1, color="white"),
                    ),
                    showlegend=False,
                )
            )

    fig_prices.update_layout(
        yaxis_title="Price Change (%)",
        yaxis_ticksuffix="%",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=450,
        margin=dict(l=40, r=20, t=30, b=40),
    )
    st.plotly_chart(fig_prices, use_container_width=True)

else:
    # Absolute price sub-plots
    n = len(all_data)
    fig_abs = make_subplots(
        rows=n, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=[f"{sym} (KRW)" for sym in all_data],
    )
    for idx, (sym, df) in enumerate(all_data.items(), start=1):
        dff = filter_by_time(df, selected_hours)
        if dff.empty:
            continue
        fig_abs.add_trace(
            go.Scatter(
                x=dff["timestamp"],
                y=dff["crypto_price"],
                mode="lines",
                name=sym,
                line=dict(color=coin_color(sym, idx - 1), width=2),
            ),
            row=idx, col=1,
        )
        # Buy/sell markers
        for decision, color, marker_sym in [("buy", "green", "triangle-up"), ("sell", "red", "triangle-down")]:
            dec_df = dff[dff["decision"] == decision]
            if dec_df.empty:
                continue
            fig_abs.add_trace(
                go.Scatter(
                    x=dec_df["timestamp"],
                    y=dec_df["crypto_price"],
                    mode="markers",
                    name=f"{sym} {decision.upper()}",
                    marker=dict(color=color, size=10, symbol=marker_sym),
                    showlegend=False,
                ),
                row=idx, col=1,
            )
        fig_abs.update_yaxes(tickformat=",.0f", row=idx, col=1)

    fig_abs.update_layout(
        height=300 * n,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    st.plotly_chart(fig_abs, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────
# SECTION 4 – Trade History
# ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📋 Trade History")

# Combine all trades
all_trades = []
for sym, df in all_data.items():
    dff = filter_by_time(df, selected_hours).copy()
    if dff.empty:
        continue
    dff["symbol"] = sym
    all_trades.append(dff)

if all_trades:
    combined = pd.concat(all_trades, ignore_index=True).sort_values("timestamp", ascending=False)

    # Filter by coin
    filter_coins = st.multiselect(
        "Filter by coin:",
        sorted(all_data.keys()),
        default=sorted(all_data.keys()),
    )
    combined = combined[combined["symbol"].isin(filter_coins)]

    display_df = pd.DataFrame(
        {
            "Time": combined["timestamp"].dt.strftime("%Y-%m-%d %H:%M"),
            "Coin": combined["symbol"],
            "Decision": combined["decision"].str.upper(),
            "Pct (%)": combined["percentage"],
            "Crypto Price": combined["crypto_price"].apply(lambda x: f"₩{x:,.0f}"),
            "Crypto Bal": combined["crypto_balance"],
            "KRW Bal": combined["krw_balance"].apply(lambda x: f"₩{x:,.0f}"),
            "Portfolio": combined["portfolio_value"].apply(lambda x: f"₩{x:,.0f}"),
            "Return (%)": combined["profit_loss_pct"].apply(lambda x: f"{x:.2f}"),
        }
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pct (%)": st.column_config.NumberColumn(format="%.1f%%", width="small"),
            "Return (%)": st.column_config.NumberColumn(format="%.2f%%", width="small"),
        },
    )

    # ── Trade detail expander ────────────────────────────────────────
    st.subheader("🔍 Trade Detail")
    trade_options = [
        f"{row['timestamp'].strftime('%Y-%m-%d %H:%M')} — {row['symbol']} {row['decision'].upper()}"
        for _, row in combined.iterrows()
    ]
    if trade_options:
        selected_idx = st.selectbox("Select a trade:", range(len(trade_options)), format_func=lambda i: trade_options[i])
        sel = combined.iloc[selected_idx]
        st.markdown(
            f"""
**{sel['symbol']}** — {sel['timestamp'].strftime('%Y-%m-%d %H:%M')}

| Field | Value |
|-------|-------|
| Decision | {sel['decision'].upper()} {sel['percentage']}% |
| Crypto Price | ₩{sel['crypto_price']:,.0f} |
| Crypto Balance | {sel['crypto_balance']:.8f} {sel['symbol']} |
| KRW Balance | ₩{sel['krw_balance']:,.0f} |
| Portfolio Value | ₩{sel['portfolio_value']:,.0f} |
| Return | {sel['profit_loss_pct']:.2f}% |

**AI Reasoning**

{sel['reason']}
"""
        )

else:
    st.info("No trades in the selected time range.")
