# Database Monitoring & Stale Data Alerts

This guide explains the database monitoring and stale data alert features in the trading dashboard.

## 🎯 **Overview**

The dashboard automatically monitors all database files and sends Slack notifications when trading data becomes stale (hasn't been updated for 5+ hours), indicating that your trading bot may have stopped working.

## 📊 **Monitoring Features**

### **Sidebar Data Freshness Indicator**
- **🟢 Fresh**: Data updated within 2 hours
- **🟡 Old**: Data updated 2-5 hours ago  
- **🔴 Stale**: Data older than 5 hours (triggers alert)

### **Database Monitoring Dashboard**
- Monitor all database files at once
- Real-time status for each database
- Trade counts and file sizes
- Last update timestamps
- Summary metrics (Fresh/Old/Stale/Error counts)

### **Auto-Refresh Option**
- Enable auto-refresh every 30 seconds
- Keeps monitoring data current
- Useful for real-time monitoring

## 🚨 **Stale Data Alerts**

### **Alert Conditions**
- Database hasn't been updated for **5+ hours**
- Only one alert per database per 24 hours (prevents spam)
- Automatic alert clearing when data becomes fresh again

### **Slack Notification Content**
```
⚠️ Trading Bot Alert - Stale Data Detected ⚠️

Database: coin_auto_trade.db
Last Update: 2025-10-04 08:30:15
Hours Since Update: 6.2 hours
Threshold: 5 hours

🚨 The trading bot may have stopped working!

Possible Issues:
• Trading bot process has crashed
• Database connection problems  
• System or network issues
• Bot is in hold-only mode

Recommended Actions:
• Check if trading bot is still running
• Review bot logs for errors
• Restart the trading bot if needed
• Verify system resources and connectivity
```

## ⚙️ **Configuration**

### **Environment Variables**
Add to your `.env` file (same as for trading notifications):
```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_USER_ID=U1234567890
```

### **Customizable Settings**
In `autotrade_dashboard.py`:
```python
STALE_DATA_THRESHOLD_HOURS = 5  # Change alert threshold
```

### **Notification Tracking**
- State saved in: `dashboard_state/notification_tracking.json`
- Tracks last notification time per database
- Prevents notification spam

## 🧪 **Testing**

### **Test Slack Integration**
1. Configure Slack credentials in `.env`
2. Open the dashboard
3. Use "🧪 Test Slack Notification" button in sidebar
4. Check your Slack DMs

### **Simulate Stale Data**
1. Stop your trading bot
2. Wait 5+ hours (or modify threshold for testing)
3. Open/refresh the dashboard
4. Check for stale data alerts

## 🔍 **Monitoring Best Practices**

### **Regular Monitoring**
- Check dashboard daily
- Enable auto-refresh during active monitoring
- Monitor multiple databases if running parallel sessions

### **Alert Response**
When you receive a stale data alert:

1. **Check Bot Status**: Verify if trading process is running
2. **Review Logs**: Look for error messages or crashes
3. **System Resources**: Check CPU, memory, disk space
4. **Network Connectivity**: Ensure API access is working
5. **Restart if Needed**: Restart trading bot if issues found

### **Database Comparison**
- Use comparison features to identify consistently performing databases
- Monitor relative performance across different configurations
- Identify databases that may need attention

## 🚀 **Integration with Other Tools**

### **Process Monitoring**
Combine with system monitoring tools:
```bash
# Check if trading bot is running
ps aux | grep autotrade.py

# Monitor system resources
top -p $(pgrep -f autotrade.py)
```

### **Log Monitoring**
Set up log rotation and monitoring:
```bash
# Monitor trading bot logs
tail -f trading_bot.log

# Search for errors
grep -i error trading_bot.log
```

## 📈 **Dashboard Sections**

### **Main Dashboard**
- Current database selection and info
- Data freshness indicators
- Portfolio metrics and charts

### **Database Comparison**
- Multi-database performance comparison
- Return comparison charts
- Trading statistics across databases

### **Database Monitoring**
- All databases status overview
- Health metrics and file information
- Real-time monitoring with auto-refresh

This monitoring system helps ensure your crypto trading bot stays operational and alerts you immediately when issues arise.
