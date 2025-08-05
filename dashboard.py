import streamlit as st
import subprocess
import threading
import time
import queue
import os
import signal
from io import StringIO
import sys
from contextlib import redirect_stdout, redirect_stderr
import json
from datetime import datetime
import pickle

# Configure the page
st.set_page_config(
    page_title="Crypto Auto Trading Dashboard",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# State persistence files
STATE_DIR = "dashboard_state"
TRADING_STATE_FILE = os.path.join(STATE_DIR, "trading_state.json")
OUTPUT_BUFFER_FILE = os.path.join(STATE_DIR, "output_buffer.pkl")
DECISIONS_FILE = os.path.join(STATE_DIR, "trading_decisions.pkl")
PROCESS_PID_FILE = os.path.join(STATE_DIR, "process_pid.txt")

# Create state directory if it doesn't exist
os.makedirs(STATE_DIR, exist_ok=True)

def save_state():
    """Save current state to files"""
    try:
        # Save trading state
        state_data = {
            "trading_active": st.session_state.trading_active,
            "trade_interval": st.session_state.trade_interval,
            "last_update": datetime.now().isoformat()
        }
        with open(TRADING_STATE_FILE, 'w') as f:
            json.dump(state_data, f)
        
        # Save output buffer
        with open(OUTPUT_BUFFER_FILE, 'wb') as f:
            pickle.dump(st.session_state.output_buffer, f)
        
        # Save trading decisions
        with open(DECISIONS_FILE, 'wb') as f:
            pickle.dump(st.session_state.trading_decisions, f)
        
        # Save process PID if active
        if st.session_state.process and st.session_state.process.poll() is None:
            with open(PROCESS_PID_FILE, 'w') as f:
                f.write(str(st.session_state.process.pid))
        elif os.path.exists(PROCESS_PID_FILE):
            os.remove(PROCESS_PID_FILE)
            
    except Exception as e:
        st.error(f"Error saving state: {str(e)}")

def load_state():
    """Load state from files"""
    try:
        # Load trading state
        if os.path.exists(TRADING_STATE_FILE):
            with open(TRADING_STATE_FILE, 'r') as f:
                state_data = json.load(f)
                st.session_state.trade_interval = state_data.get("trade_interval", 60)
                
                # Check if process is still running
                if os.path.exists(PROCESS_PID_FILE):
                    with open(PROCESS_PID_FILE, 'r') as pid_file:
                        pid = int(pid_file.read().strip())
                        if is_process_running(pid):
                            st.session_state.trading_active = True
                            # Reconnect to existing process
                            reconnect_to_process(pid)
                        else:
                            st.session_state.trading_active = False
                            if os.path.exists(PROCESS_PID_FILE):
                                os.remove(PROCESS_PID_FILE)
                else:
                    st.session_state.trading_active = False
        
        # Load output buffer
        if os.path.exists(OUTPUT_BUFFER_FILE):
            with open(OUTPUT_BUFFER_FILE, 'rb') as f:
                st.session_state.output_buffer = pickle.load(f)
        
        # Load trading decisions
        if os.path.exists(DECISIONS_FILE):
            with open(DECISIONS_FILE, 'rb') as f:
                st.session_state.trading_decisions = pickle.load(f)
                
    except Exception as e:
        st.error(f"Error loading state: {str(e)}")

def is_process_running(pid):
    """Check if a process with given PID is still running"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def reconnect_to_process(pid):
    """Attempt to reconnect to existing process"""
    try:
        # We can't directly reconnect to subprocess pipes, but we can track that it's running
        st.session_state.process = type('MockProcess', (), {
            'pid': pid,
            'poll': lambda *args, **kwargs: None if is_process_running(pid) else 0,
            'terminate': lambda *args, **kwargs: os.kill(pid, signal.SIGTERM),
            'wait': lambda timeout=None, *args, **kwargs: None,
            'stdout': None  # Explicitly set stdout to None for MockProcess
        })()
        
        # Add reconnection message to output buffer
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.output_buffer.append(f"[{timestamp}] Reconnected to existing trading process (PID: {pid})")
        st.session_state.output_buffer.append(f"[{timestamp}] Note: Cannot capture live output from reconnected process. Check logs for updates.")
        
    except Exception as e:
        st.session_state.trading_active = False
        if os.path.exists(PROCESS_PID_FILE):
            os.remove(PROCESS_PID_FILE)

# Initialize session state with persistence
if 'trading_active' not in st.session_state:
    st.session_state.trading_active = False
if 'output_buffer' not in st.session_state:
    st.session_state.output_buffer = []
if 'process' not in st.session_state:
    st.session_state.process = None
if 'output_queue' not in st.session_state:
    st.session_state.output_queue = queue.Queue()
if 'trading_decisions' not in st.session_state:
    st.session_state.trading_decisions = []
if 'trade_interval' not in st.session_state:
    st.session_state.trade_interval = 60  # Default 60 minutes
if 'state_loaded' not in st.session_state:
    st.session_state.state_loaded = False
    load_state()  # Load state on first run
    st.session_state.state_loaded = True

def capture_output_from_process():
    """Capture output from the trading process"""
    if st.session_state.process and st.session_state.process.poll() is None:
        try:
            # Check if this is a real process with stdout or a mock process
            if hasattr(st.session_state.process, 'stdout') and st.session_state.process.stdout:
                # Read output line by line from real process
                output = st.session_state.process.stdout.readline()
                if output:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    formatted_output = f"[{timestamp}] {output.strip()}"
                    st.session_state.output_buffer.append(formatted_output)
                    
                    # Parse and extract trading decisions
                    parse_trading_decision(output.strip())
                    
                    # Keep only last 100 lines
                    if len(st.session_state.output_buffer) > 100:
                        st.session_state.output_buffer.pop(0)
                        
                    # Save state after new output
                    save_state()
            else:
                # This is a mock process (reconnected), we can't read stdout
                # Just indicate that the process is running but we can't capture output
                pass
                
        except Exception as e:
            error_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error reading output: {str(e)}"
            st.session_state.output_buffer.append(error_msg)

def parse_trading_decision(output):
    """Parse output to extract trading decisions and add to bulletin board"""
    try:
        # Look for AI Decision lines
        if "AI Decision:" in output:
            decision_info = output.split("AI Decision:")[1].strip()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Extract decision and percentage
            if "BUY" in decision_info:
                action = "🟢 BUY"
            elif "SELL" in decision_info:
                action = "🔴 SELL"
            elif "HOLD" in decision_info:
                action = "🟡 HOLD"
            else:
                action = "❓ UNKNOWN"
            
            percentage = decision_info.split("%")[0].split()[-1] if "%" in decision_info else "N/A"
            
            st.session_state.trading_decisions.append({
                "timestamp": timestamp,
                "action": action,
                "percentage": percentage + "%",
                "reason": "",
                "trade_amount": ""
            })
            
        # Look for reason lines
        elif "Reason:" in output:
            reason = output.split("Reason:")[1].strip()
            if st.session_state.trading_decisions:
                st.session_state.trading_decisions[-1]["reason"] = reason
                
        # Look for actual trade executions
        elif any(phrase in output.lower() for phrase in ["buying", "selling", "buy order result", "sell order result"]):
            if st.session_state.trading_decisions:
                current_trade = st.session_state.trading_decisions[-1]["trade_amount"]
                if not current_trade:
                    st.session_state.trading_decisions[-1]["trade_amount"] = output
                else:
                    st.session_state.trading_decisions[-1]["trade_amount"] += f"\n{output}"
        
        # Keep only last 20 decisions
        if len(st.session_state.trading_decisions) > 20:
            st.session_state.trading_decisions.pop(0)
            
        # Save state after parsing decisions
        save_state()
            
    except Exception as e:
        pass  # Silently handle parsing errors

def start_trading():
    """Start the auto trading process"""
    try:
        # Start the process with time interval argument
        st.session_state.process = subprocess.Popen(
            [sys.executable, "autotrade_dashboard.py", str(st.session_state.trade_interval)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        st.session_state.trading_active = True
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.output_buffer.append(f"[{timestamp}] Auto trading started with {st.session_state.trade_interval} minute intervals!")
        
        # Save state immediately after starting
        save_state()
        return True
    except Exception as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.output_buffer.append(f"[{timestamp}] Error starting trading: {str(e)}")
        return False

def stop_trading():
    """Stop the auto trading process"""
    try:
        if st.session_state.process:
            if hasattr(st.session_state.process, 'pid'):
                # If it's a real process, terminate it
                if hasattr(st.session_state.process, 'terminate'):
                    st.session_state.process.terminate()
                    st.session_state.process.wait(timeout=5)
                else:
                    # If it's a mock process from reconnection, kill by PID
                    os.kill(st.session_state.process.pid, signal.SIGTERM)
            st.session_state.process = None
        
        st.session_state.trading_active = False
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.output_buffer.append(f"[{timestamp}] Auto trading stopped!")
        
        # Remove PID file
        if os.path.exists(PROCESS_PID_FILE):
            os.remove(PROCESS_PID_FILE)
        
        # Save state after stopping
        save_state()
        return True
    except Exception as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.output_buffer.append(f"[{timestamp}] Error stopping trading: {str(e)}")
        return False

# Main dashboard layout
st.title("🚀 Crypto Auto Trading Dashboard")
st.markdown("---")

# Sidebar controls
with st.sidebar:
    st.header("🎛️ Trading Controls")
    
    # Status indicator
    if st.session_state.trading_active:
        st.success("🟢 Trading Active")
        if os.path.exists(PROCESS_PID_FILE):
            with open(PROCESS_PID_FILE, 'r') as f:
                pid = f.read().strip()
                st.caption(f"Process PID: {pid}")
    else:
        st.error("🔴 Trading Stopped")
    
    st.markdown("---")
    
    # Control buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("▶️ Start Trading", disabled=st.session_state.trading_active, use_container_width=True):
            if start_trading():
                st.rerun()
    
    with col2:
        if st.button("⏹️ Stop Trading", disabled=not st.session_state.trading_active, use_container_width=True):
            if stop_trading():
                st.rerun()
    
    st.markdown("---")
    
    # Time interval controller
    st.subheader("⏰ Trading Interval")
    interval_options = {
        "5 minutes": 5,
        "15 minutes": 15,
        "30 minutes": 30,
        "1 hour": 60,
        "2 hours": 120,
        "4 hours": 240,
        "12 hours": 720,
        "24 hours": 1440
    }
    
    # Find current selection
    current_key = None
    for key, value in interval_options.items():
        if value == st.session_state.trade_interval:
            current_key = key
            break
    if current_key is None:
        current_key = "1 hour"  # fallback
    
    selected_interval = st.selectbox(
        "Select trading interval:",
        options=list(interval_options.keys()),
        index=list(interval_options.keys()).index(current_key),
        disabled=st.session_state.trading_active,
        help="Trading interval can only be changed when trading is stopped"
    )
    
    # Update interval if changed
    new_interval = interval_options[selected_interval]
    if new_interval != st.session_state.trade_interval:
        st.session_state.trade_interval = new_interval
        save_state()
    
    if st.session_state.trading_active:
        st.info(f"⚡ Current interval: {selected_interval}")
    else:
        st.success(f"✅ Next trading will use: {selected_interval}")
    
    st.markdown("---")
    
    # Configuration info
    st.subheader("📊 Current Configuration")
    try:
        # Read target info from autotrade.py
        with open("autotrade.py", "r") as f:
            content = f.read()
            if 'target = "' in content:
                target_line = [line for line in content.split('\n') if line.strip().startswith('target = "')][0]
                target = target_line.split('"')[1]
                st.info(f"**Target:** {target}")
    except:
        st.warning("Could not read configuration")
    
    # State persistence info
    st.subheader("💾 Session Persistence")
    if os.path.exists(TRADING_STATE_FILE):
        with open(TRADING_STATE_FILE, 'r') as f:
            state_data = json.load(f)
            last_update = state_data.get("last_update", "Unknown")
            st.success(f"✅ State saved")
            st.caption(f"Last update: {last_update[:19]}")
    else:
        st.warning("No saved state")
    
    # Clear all data button
    if st.button("🗑️ Clear All Data", use_container_width=True):
        # Clear session state
        st.session_state.output_buffer = []
        st.session_state.trading_decisions = []
        
        # Clear saved files
        for file_path in [TRADING_STATE_FILE, OUTPUT_BUFFER_FILE, DECISIONS_FILE, PROCESS_PID_FILE]:
            if os.path.exists(file_path):
                os.remove(file_path)
        
        st.success("All data cleared!")
        st.rerun()

# Main content area
col1, col2 = st.columns([3, 2])

with col1:
    # Create tabs for different views
    tab1, tab2 = st.tabs(["📊 Trading Decisions", "📋 Full Output Console"])
    
    with tab1:
        st.header("📊 Trading Decisions & Results")
        
        if st.session_state.trading_decisions:
            # Display trading decisions in a clean format
            for i, decision in enumerate(reversed(st.session_state.trading_decisions[-10:])):  # Show last 10
                with st.expander(f"{decision['action']} - {decision['timestamp']}", expanded=(i==0)):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("Action", decision['action'])
                        st.metric("Percentage", decision['percentage'])
                    with col_b:
                        if decision['reason']:
                            st.markdown(f"**Reason:** {decision['reason']}")
                        if decision['trade_amount']:
                            st.markdown(f"**Trade Details:**\n```\n{decision['trade_amount']}\n```")
        else:
            st.info("No trading decisions yet. Start trading to see AI decisions and results here.")
    
    with tab2:
        st.header("📋 Full Output Console")
        
        # Auto-refresh the output
        if st.session_state.trading_active:
            capture_output_from_process()
            
            # Show warning if connected to mock process
            if (st.session_state.process and 
                not hasattr(st.session_state.process, 'stdout') or 
                st.session_state.process.stdout is None):
                st.warning("⚠️ Connected to existing process - live output capture not available. Process is running but new logs won't appear here.")
        
        # Display output in a container
        output_container = st.container()
        with output_container:
            if st.session_state.output_buffer:
                # Display last 30 lines in reverse order (newest first)
                recent_output = st.session_state.output_buffer[-30:]
                output_text = "\n".join(reversed(recent_output))
                st.code(output_text, language="text", line_numbers=False)
            else:
                st.info("No output yet. Start trading to see live updates.")

with col2:
    st.header("📈 Trading Summary")
    
    # Trading statistics
    total_decisions = len(st.session_state.trading_decisions)
    buy_count = sum(1 for d in st.session_state.trading_decisions if "BUY" in d['action'])
    sell_count = sum(1 for d in st.session_state.trading_decisions if "SELL" in d['action'])
    hold_count = sum(1 for d in st.session_state.trading_decisions if "HOLD" in d['action'])
    
    st.metric("Total Decisions", total_decisions)
    st.metric("Buy Decisions", buy_count)
    st.metric("Sell Decisions", sell_count)
    st.metric("Hold Decisions", hold_count)
    
    st.markdown("---")
    
    # Latest decision summary
    st.subheader("🎯 Latest Decision")
    if st.session_state.trading_decisions:
        latest = st.session_state.trading_decisions[-1]
        st.markdown(f"**Action:** {latest['action']}")
        st.markdown(f"**Percentage:** {latest['percentage']}")
        st.markdown(f"**Time:** {latest['timestamp']}")
        if latest['reason']:
            st.markdown(f"**Reason:** {latest['reason'][:100]}...")
    else:
        st.info("No decisions yet")

# Auto-refresh mechanism
if st.session_state.trading_active:
    # Show a status indicator for active trading
    with st.empty():
        st.info("🔄 Trading is active - Dashboard auto-refreshing every 5 seconds")
    
    # Save state periodically during active trading
    save_state()
    
    # Auto-refresh every 5 seconds when trading is active
    time.sleep(5)
    st.rerun()
else:
    # Manual refresh button when not trading
    if st.button("🔄 Refresh Dashboard"):
        st.rerun()

# Footer
st.markdown("---")
st.markdown("*Dashboard state is automatically saved and restored across browser sessions*")
