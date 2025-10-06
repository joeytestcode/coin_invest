import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

import os
import glob
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import json

# 페이지 설정
st.set_page_config(
    page_title="Crypto AI Trading Dashboard",
    page_icon="📈",
    layout="wide"
)

# Configuration
STALE_DATA_THRESHOLD_HOURS = 5  # Hours after which data is considered stale
NOTIFICATION_STATE_FILE = "dashboard_state/notification_tracking.json"

# Ensure state directory exists
os.makedirs("dashboard_state", exist_ok=True)

def load_notification_state():
    """Load notification tracking state"""
    try:
        if os.path.exists(NOTIFICATION_STATE_FILE):
            with open(NOTIFICATION_STATE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_notification_state(state):
    """Save notification tracking state"""
    try:
        with open(NOTIFICATION_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        st.error(f"Error saving notification state: {str(e)}")

def get_slack_user_info(client):
    """Get current user info from Slack API"""
    try:
        response = client.auth_test()
        return response.get("user_id"), response.get("user")
    except Exception as e:
        return None, None

def send_stale_data_notification(db_name, last_update_time, hours_stale):
    """Send Slack notification about stale database data"""
    try:
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        slack_user_id = os.getenv("SLACK_USER_ID")
        slack_channel_id = os.getenv("SLACK_CHANNEL_ID")

        if not slack_token or not slack_user_id:
            return False
        
        client = WebClient(token=slack_token)
        
        message = f"""
⚠️ *Trading Bot Alert - Stale Data Detected* ⚠️

*Database:* `{db_name}`
*Last Update:* {last_update_time.strftime('%Y-%m-%d %H:%M:%S')}
*Hours Since Update:* {hours_stale:.1f} hours
*Threshold:* {STALE_DATA_THRESHOLD_HOURS} hours

🚨 **The trading bot may have stopped working!**

*Possible Issues:*
• Trading bot process has crashed
• Database connection problems
• System or network issues
• Bot is in hold-only mode

*Recommended Actions:*
• Check if trading bot is still running
• Review bot logs for errors
• Restart the trading bot if needed
• Verify system resources and connectivity

---
_Crypto Auto Trading Dashboard Alert_ 🤖
        """.strip()
        
        # Try using the user ID directly as a channel
        response = client.chat_postMessage(
            channel=slack_channel_id,
            text=f"⚠️ Trading Bot Alert - No updates in {db_name} for {hours_stale:.1f} hours",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                }
            ]
        )
        
        return True
        
    except SlackApiError as e:
        st.error(f"Slack API error: {e.response['error']}")
        return False
    except Exception as e:
        st.error(f"Error sending Slack notification: {str(e)}")
        return False

def check_database_freshness(db_name, df):
    """Check if database data is stale and send notification if needed"""
    if df.empty:
        return
    
    # Get the most recent trade timestamp
    latest_timestamp = df['timestamp'].max()
    current_time = datetime.now()
    
    # Convert to timezone-naive if needed
    if latest_timestamp.tz is not None:
        latest_timestamp = latest_timestamp.tz_convert(None)
    
    time_diff = current_time - latest_timestamp
    hours_stale = time_diff.total_seconds() / 3600
    
    # Load notification tracking state
    notification_state = load_notification_state()
    
    # Check if data is stale
    if hours_stale > STALE_DATA_THRESHOLD_HOURS:
        # Check if we already sent notification for this database
        last_notification_key = f"{db_name}_last_notification"
        last_notification_str = notification_state.get(last_notification_key)
        
        # Only send notification once per day to avoid spam
        should_notify = True
        if last_notification_str:
            try:
                last_notification = datetime.fromisoformat(last_notification_str)
                time_since_last_notification = current_time - last_notification
                if time_since_last_notification.total_seconds() < 24 * 3600:  # 24 hours
                    should_notify = False
            except:
                pass
        
        if should_notify:
            success = send_stale_data_notification(db_name, latest_timestamp, hours_stale)
            if success:
                # Update notification state
                notification_state[last_notification_key] = current_time.isoformat()
                save_notification_state(notification_state)
                st.warning(f"📱 Sent stale data alert for {db_name} (no updates for {hours_stale:.1f} hours)")
    else:
        # Data is fresh, clear any previous notification tracking
        last_notification_key = f"{db_name}_last_notification"
        if last_notification_key in notification_state:
            del notification_state[last_notification_key]
            save_notification_state(notification_state)

# Get all available database files
def get_available_databases():
    """Get all .db files in the current directory"""
    db_files = glob.glob("*.db")
    if not db_files:
        # If no .db files found, create default
        return ["coin_auto_trade.db"]
    return sorted(db_files)

# Check if database has the required table structure
def validate_database(db_path):
    """Check if the database has the required trades table"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except:
        return False

# 데이터베이스 연결 및 데이터 로드
def load_trade_data(db_name):
    """Load trade data from specified database"""
    if not os.path.exists(db_name):
        st.error(f"Database file '{db_name}' not found!")
        return pd.DataFrame()
    
    if not validate_database(db_name):
        st.error(f"Database '{db_name}' does not have the required 'trades' table!")
        return pd.DataFrame()
    
    try:
        conn = sqlite3.connect(db_name)
        query = "SELECT * FROM trades ORDER BY timestamp DESC"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            st.warning(f"No trading data found in '{db_name}'")
            return df
        
        # 타임스탬프 처리
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 포트폴리오 가치 계산
        df['portfolio_value'] = df['krw_balance'] + (df['crypto_balance'] * df['crypto_price'])

        # 수익률 계산 (첫 거래 기준)
        if len(df) > 0:
            first_trade = df.iloc[-1]
            df['profit_loss'] = df['portfolio_value'] - first_trade['portfolio_value']
            df['profit_loss_pct'] = (df['profit_loss'] / first_trade['portfolio_value']) * 100
        
        # Check data freshness and send notification if needed
        check_database_freshness(db_name, df)
        
        return df
    except Exception as e:
        st.error(f"Error loading data from '{db_name}': {str(e)}")
        return pd.DataFrame()

# 헤더
st.title("Crypto AI Trading Dashboard")

# Database selection sidebar
with st.sidebar:
    st.header("📊 Database Selection")
    
    # Get available databases
    available_dbs = get_available_databases()
    
    # Database selector
    selected_db = st.selectbox(
        "Select Database:",
        available_dbs,
        index=0,
        help="Choose which database file to analyze"
    )
    
    # Display database info
    if os.path.exists(selected_db):
        file_size = os.path.getsize(selected_db)
        st.info(f"**File:** {selected_db}\n**Size:** {file_size:,} bytes")
        
        # Show number of trades
        try:
            conn = sqlite3.connect(selected_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            trade_count = cursor.fetchone()[0]
            
            # Get latest trade timestamp for freshness check
            cursor.execute("SELECT MAX(timestamp) FROM trades")
            latest_timestamp_str = cursor.fetchone()[0]
            conn.close()
            
            st.success(f"**Trades:** {trade_count}")
            
            # Show data freshness
            if latest_timestamp_str:
                latest_timestamp = pd.to_datetime(latest_timestamp_str)
                current_time = datetime.now()
                
                # Convert to timezone-naive if needed
                if latest_timestamp.tz is not None:
                    latest_timestamp = latest_timestamp.tz_convert(None)
                
                time_diff = current_time - latest_timestamp
                hours_since_update = time_diff.total_seconds() / 3600
                
                if hours_since_update > STALE_DATA_THRESHOLD_HOURS:
                    st.error(f"⚠️ **Data Age:** {hours_since_update:.1f} hours (STALE)")
                    st.caption(f"Last update: {latest_timestamp.strftime('%Y-%m-%d %H:%M')}")
                elif hours_since_update > 2:
                    st.warning(f"⏰ **Data Age:** {hours_since_update:.1f} hours")
                    st.caption(f"Last update: {latest_timestamp.strftime('%Y-%m-%d %H:%M')}")
                else:
                    st.success(f"✅ **Data Fresh:** {hours_since_update:.1f} hours ago")
            else:
                st.info("No trade data available")
                
        except Exception as e:
            st.warning(f"Could not read database info: {str(e)}")
    else:
        st.error("Database file not found!")
    
    st.markdown("---")
    
    # Refresh button
    if st.button("🔄 Refresh Database List"):
        st.rerun()
    
    # Notification settings
    st.subheader("📱 Stale Data Notifications")
    
    # Check if Slack is configured
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    slack_user_id = os.getenv("SLACK_USER_ID")
    
    if slack_token:
        client = WebClient(token=slack_token)
        
        # Try to get user info
        user_id, username = get_slack_user_info(client)
        
        if user_id:
            st.success("✅ Slack bot token valid")
            st.info(f"🤖 Bot connected as: {username}")
            st.info(f"👤 Your user ID: `{user_id}`")
                
            st.info(f"🕒 Alert threshold: {STALE_DATA_THRESHOLD_HOURS} hours")
            
            # Show notification status for current database
            notification_state = load_notification_state()
            last_notification_key = f"{selected_db}_last_notification"
            
            if last_notification_key in notification_state:
                last_notification_str = notification_state[last_notification_key]
                try:
                    last_notification = datetime.fromisoformat(last_notification_str)
                    st.caption(f"Last alert sent: {last_notification.strftime('%Y-%m-%d %H:%M')}")
                except:
                    pass
            
            # Test notification button
            if st.button("🧪 Test Slack Notification"):
                success = send_stale_data_notification(
                    f"TEST_{selected_db}", 
                    datetime.now() - timedelta(hours=6), 
                    6.0
                )
                if success:
                    st.success("Test notification sent!")
                else:
                    st.error("Failed to send test notification")
        else:
            st.error("❌ Invalid Slack bot token")
            st.caption("Check your SLACK_BOT_TOKEN in .env file")
    else:
        st.warning("⚠️ Slack not configured")
        st.markdown("""
        **Setup Instructions:**
        1. Create a Slack app at https://api.slack.com/apps
        2. Add Bot Token Scopes: `chat:write`, `users:read`, `conversations:read`
        3. Install app to your workspace
        4. Get Bot User OAuth Token (starts with `xoxb-`)
        5. Add to .env file:
        ```
        SLACK_BOT_TOKEN=xoxb-your-token-here
        SLACK_USER_ID=your-user-id-here
        ```
        """)
        
        if st.button("🔍 Test Bot Token Only"):
            test_token = st.text_input("Enter bot token to test:", type="password")
            if test_token:
                try:
                    test_client = WebClient(token=test_token)
                    user_id, username = get_slack_user_info(test_client)
                    if user_id:
                        st.success(f"✅ Token valid! User: {username}, ID: {user_id}")
                    else:
                        st.error("❌ Invalid token")
                except Exception as e:
                    st.error(f"❌ Token test failed: {str(e)}")

# 데이터 로드
df = load_trade_data(selected_db)

# 최신 거래 정보
if not df.empty:
    latest = df.iloc[0]
    
    # 수익률 계산
    first_trade = df.iloc[-1]
    total_profit_pct = latest['profit_loss_pct']
    
    # Database info header
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.info(f"📊 **Database:** {selected_db}")
    with col_info2:
        st.info(f"📈 **Total Trades:** {len(df)}")
    with col_info3:
        date_range = f"{df['timestamp'].min().strftime('%Y-%m-%d')} to {df['timestamp'].max().strftime('%Y-%m-%d')}"
        st.info(f"📅 **Period:** {date_range}")
    
    # 2개 컬럼으로 주요 정보 표시
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "포트폴리오 가치", 
            f"₩{latest['portfolio_value']:,.0f}",
            delta=f"{total_profit_pct:.2f}%"
        )
    
    with col2:
        st.metric(
            "최근 거래", 
            f"{latest['decision'].upper()} ({latest['percentage']}%)",
            delta=f"{latest['timestamp'].strftime('%Y-%m-%d %H:%M')}"
        )
    
    # Crypto 및 현금 잔고
    st.markdown(f"""
    **Crypto 잔고:** {latest['crypto_balance']:.6f} Crypto (₩{latest['crypto_balance'] * latest['crypto_price']:,.0f})  
    **KRW 잔고:** ₩{latest['krw_balance']:,.0f}
    """)
else:
    st.info(f"📂 Selected database: **{selected_db}**")
    st.warning("No trading data available in the selected database.")
    st.markdown("""
    **Possible reasons:**
    - This is a new database with no trades yet
    - The trading bot hasn't started recording trades
    - The database file is corrupted
    
    **Next steps:**
    - Start the trading bot to generate data
    - Select a different database with existing data
    - Create a new database for fresh trading sessions
    """)

# 수익률 차트 (Plotly)
if not df.empty and len(df) > 1:
    st.subheader("수익률 변화")
    
    # 시간순으로 정렬
    df_sorted = df.sort_values('timestamp')
    
    # 기본 수익률 라인 차트 생성
    fig = go.Figure()
    
    # 0% 라인 추가
    fig.add_hline(y=0, line=dict(color='gray', width=1, dash='dash'))
    
    # 수익률 라인 추가
    fig.add_trace(go.Scatter(
        x=df_sorted['timestamp'], 
        y=df_sorted['profit_loss_pct'],
        mode='lines+markers',
        name='수익률',
        line=dict(color='blue', width=2),
        marker=dict(size=8)
    ))
    
    # 매수/매도 포인트 추가
    for decision, color in [('buy', 'green'), ('sell', 'red'), ('hold', 'orange')]:
        decision_df = df_sorted[df_sorted['decision'] == decision]
        if not decision_df.empty:
            fig.add_trace(go.Scatter(
                x=decision_df['timestamp'],
                y=decision_df['profit_loss_pct'],
                mode='markers',
                name=decision.upper(),
                marker=dict(color=color, size=12, symbol='circle')
            ))
    
    # 차트 레이아웃 설정
    fig.update_layout(
        title='첫 거래 대비 수익률 변화',
        xaxis_title='날짜',
        yaxis_title='수익률 (%)',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        height=500,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    
    # 호버 정보 커스터마이징
    fig.update_traces(
        hovertemplate='%{x}<br>수익률: %{y:.2f}%<br>'
    )
    
    # y축 포맷 설정
    fig.update_yaxes(ticksuffix='%')
    
    st.plotly_chart(fig, use_container_width=True)

# Crypto 가격 차트 (Plotly)
if not df.empty:
    st.subheader("Crypto 가격 변화")
    
    # 시간순으로 정렬
    df_sorted = df.sort_values('timestamp')

    # 기본 Crypto 가격 차트 생성
    fig = go.Figure()

    # Crypto 가격 라인 추가
    fig.add_trace(go.Scatter(
        x=df_sorted['timestamp'], 
        y=df_sorted['crypto_price'],
        mode='lines+markers',
        name='Crypto 가격',
        line=dict(color='orange', width=2),
        marker=dict(size=6)
    ))
    
    # 매수/매도 포인트 추가
    for decision, color, symbol in [('buy', 'green', 'triangle-up'), ('sell', 'red', 'triangle-down')]:
        decision_df = df_sorted[df_sorted['decision'] == decision]
        if not decision_df.empty:
            fig.add_trace(go.Scatter(
                x=decision_df['timestamp'],
                y=decision_df['crypto_price'],
                mode='markers',
                name=decision.upper(),
                marker=dict(color=color, size=14, symbol=symbol)
            ))
    
    # 차트 레이아웃 설정
    fig.update_layout(
        title='Crypto 가격 변화와 거래 결정',
        xaxis_title='날짜',
        yaxis_title='Crypto 가격 (KRW)',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        height=500,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    
    # 호버 정보 커스터마이징
    fig.update_traces(
        hovertemplate='%{x}<br>가격: ₩%{y:,.0f}<br>'
    )
    
    # y축 포맷 설정
    fig.update_yaxes(tickformat=',.0f')
    
    st.plotly_chart(fig, use_container_width=True)

# 매매 내역 테이블
st.subheader("매매 내역")

if not df.empty:
    # 표시할 컬럼 선택 및 새 DataFrame 생성 (복사 대신)
    display_df = pd.DataFrame({
        '시간': df['timestamp'].dt.strftime('%Y-%m-%d %H:%M'),
        '결정': df['decision'].str.upper(),
        '비율(%)': df['percentage'],
        'Crypto 가격(KRW)': df['crypto_price'].apply(lambda x: f"{x:,.0f}"),
        'Crypto 잔고': df['crypto_balance'],
        'KRW 잔고': df['krw_balance'].apply(lambda x: f"{x:,.0f}"),
        '수익률(%)': df['profit_loss_pct'].apply(lambda x: f"{x:.2f}")
    })
    
    # 스타일링된 데이터프레임
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            # "결정": st.column_config.SelectboxColumn(
            #     width="small",
            # ),
            "비율(%)": st.column_config.NumberColumn(
                format="%.1f%%",
                width="small",
            ),
            "수익률(%)": st.column_config.NumberColumn(
                format="%.2f%%",
                width="medium",
            ),
        }
    )

# 거래 상세 정보
st.subheader("최근 거래 상세 정보")

if not df.empty:
        selected_idx = st.selectbox("거래 선택:", 
                                     range(len(df)), 
                                     format_func=lambda i: f"{df.iloc[i]['timestamp'].strftime('%Y-%m-%d %H:%M')} - {df.iloc[i]['decision'].upper()}")
        
        selected_trade = df.iloc[selected_idx]
        
        # 거래 상세 정보
        st.markdown(f"""
        ### {selected_trade['timestamp'].strftime('%Y-%m-%d %H:%M')} 거래 세부사항
        
        **결정:** {selected_trade['decision'].upper()} {selected_trade['percentage']*100}%  
        **Crypto 가격:** ₩{selected_trade['crypto_price']:,.0f}  
        **거래 후 Crypto 잔고:** {selected_trade['crypto_balance']:.8f} Crypto  
        **거래 후 KRW 잔고:** ₩{selected_trade['krw_balance']:,.0f}  
        **포트폴리오 가치:** ₩{selected_trade['portfolio_value']:,.0f}  
        **수익률:** {selected_trade['profit_loss_pct']:.2f}%

        **AI 판단 이유**        
        {selected_trade['reason']}
        """)

# Database Comparison Section
st.markdown("---")
st.subheader("📊 Database Comparison")

# Get available databases again for comparison
available_dbs = get_available_databases()

if len(available_dbs) > 1:
    st.markdown("Compare performance across different trading sessions:")
    
    # Multi-select for databases to compare
    selected_dbs_for_comparison = st.multiselect(
        "Select databases to compare:",
        available_dbs,
        default=[selected_db] if selected_db in available_dbs else [],
        help="Choose multiple databases to compare their performance"
    )
    
    if len(selected_dbs_for_comparison) > 1:
        comparison_data = []
        
        for db in selected_dbs_for_comparison:
            if os.path.exists(db) and validate_database(db):
                try:
                    temp_df = load_trade_data(db)
                    if not temp_df.empty:
                        latest_trade = temp_df.iloc[0]
                        first_trade = temp_df.iloc[-1]
                        
                        comparison_data.append({
                            'Database': db,
                            'Total Trades': len(temp_df),
                            'Start Date': first_trade['timestamp'].strftime('%Y-%m-%d'),
                            'End Date': latest_trade['timestamp'].strftime('%Y-%m-%d'),
                            'Final Portfolio Value': f"₩{latest_trade['portfolio_value']:,.0f}",
                            'Total Return (%)': f"{latest_trade['profit_loss_pct']:.2f}%",
                            'Buy Trades': len(temp_df[temp_df['decision'] == 'buy']),
                            'Sell Trades': len(temp_df[temp_df['decision'] == 'sell']),
                            'Hold Trades': len(temp_df[temp_df['decision'] == 'hold'])
                        })
                except Exception as e:
                    st.warning(f"Could not load data from {db}: {str(e)}")
        
        if comparison_data:
            comparison_df = pd.DataFrame(comparison_data)
            st.dataframe(
                comparison_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total Return (%)": st.column_config.TextColumn(
                        width="medium",
                    ),
                    "Final Portfolio Value": st.column_config.TextColumn(
                        width="large",
                    ),
                }
            )
            
            # Performance comparison chart
            if len(comparison_data) > 1:
                st.subheader("📈 Performance Comparison")
                
                # Extract return percentages for chart
                returns = []
                db_names = []
                for item in comparison_data:
                    try:
                        return_pct = float(item['Total Return (%)'].replace('%', ''))
                        returns.append(return_pct)
                        db_names.append(item['Database'])
                    except:
                        continue
                
                if returns:
                    fig = go.Figure(data=[
                        go.Bar(
                            x=db_names,
                            y=returns,
                            marker_color=['green' if r >= 0 else 'red' for r in returns],
                            text=[f"{r:.2f}%" for r in returns],
                            textposition='auto',
                        )
                    ])
                    
                    fig.update_layout(
                        title='Total Return Comparison Across Databases',
                        xaxis_title='Database',
                        yaxis_title='Total Return (%)',
                        yaxis=dict(ticksuffix='%'),
                        height=400
                    )
                    
                    # Add horizontal line at 0%
                    fig.add_hline(y=0, line=dict(color='gray', width=1, dash='dash'))
                    
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No valid data found in selected databases for comparison.")
    elif len(selected_dbs_for_comparison) == 1:
        st.info("Select at least 2 databases to see comparison.")
else:
    st.info("Only one database available. Create more databases to enable comparison features.")

# Database Monitoring Section
st.markdown("---")
st.subheader("🔍 Database Monitoring")

st.markdown("Monitor data freshness across all databases:")

# Create monitoring table
monitoring_data = []
available_dbs = get_available_databases()

for db in available_dbs:
    if os.path.exists(db) and validate_database(db):
        try:
            conn = sqlite3.connect(db)
            cursor = conn.cursor()
            
            # Get latest timestamp and trade count
            cursor.execute("SELECT MAX(timestamp), COUNT(*) FROM trades")
            result = cursor.fetchone()
            latest_timestamp_str, trade_count = result
            conn.close()
            
            if latest_timestamp_str and trade_count > 0:
                latest_timestamp = pd.to_datetime(latest_timestamp_str)
                current_time = datetime.now()
                
                # Convert to timezone-naive if needed
                if latest_timestamp.tz is not None:
                    latest_timestamp = latest_timestamp.tz_convert(None)
                
                time_diff = current_time - latest_timestamp
                hours_since_update = time_diff.total_seconds() / 3600
                
                # Determine status
                if hours_since_update > STALE_DATA_THRESHOLD_HOURS:
                    status = "🔴 STALE"
                    status_color = "red"
                elif hours_since_update > 2:
                    status = "🟡 OLD"
                    status_color = "orange"
                else:
                    status = "🟢 FRESH"
                    status_color = "green"
                
                monitoring_data.append({
                    'Database': db,
                    'Status': status,
                    'Trades': trade_count,
                    'Last Update': latest_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'Hours Ago': f"{hours_since_update:.1f}",
                    'File Size (KB)': f"{os.path.getsize(db) / 1024:.1f}"
                })
            else:
                monitoring_data.append({
                    'Database': db,
                    'Status': "⚪ EMPTY",
                    'Trades': 0,
                    'Last Update': "No data",
                    'Hours Ago': "N/A",
                    'File Size (KB)': f"{os.path.getsize(db) / 1024:.1f}"
                })
                
        except Exception as e:
            monitoring_data.append({
                'Database': db,
                'Status': "❌ ERROR",
                'Trades': "Error",
                'Last Update': f"Error: {str(e)[:30]}...",
                'Hours Ago': "N/A",
                'File Size (KB)': "N/A"
            })

if monitoring_data:
    monitoring_df = pd.DataFrame(monitoring_data)
    
    # Display monitoring table
    st.dataframe(
        monitoring_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn(
                width="small",
            ),
            "Hours Ago": st.column_config.NumberColumn(
                format="%.1f",
                width="small",
            ),
            "File Size (KB)": st.column_config.TextColumn(
                width="small",
            ),
        }
    )
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    fresh_count = len([d for d in monitoring_data if "🟢" in d['Status']])
    old_count = len([d for d in monitoring_data if "🟡" in d['Status']])
    stale_count = len([d for d in monitoring_data if "🔴" in d['Status']])
    error_count = len([d for d in monitoring_data if "❌" in d['Status']])
    
    with col1:
        st.metric("🟢 Fresh", fresh_count)
    with col2:
        st.metric("🟡 Old", old_count)
    with col3:
        st.metric("🔴 Stale", stale_count)
    with col4:
        st.metric("❌ Errors", error_count)
    
    # Auto-refresh option
    st.markdown("---")
    auto_refresh = st.checkbox("🔄 Auto-refresh every 30 seconds", value=False)
    
    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()
else:
    st.warning("No databases found for monitoring.")