# Slack Integration Setup Guide

This guide will help you set up Slack notifications for your crypto trading bot.

## Step 1: Create a Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App"
3. Choose "From scratch"
4. Give your app a name (e.g., "Crypto Trading Bot")
5. Select your workspace
6. Click "Create App"

## Step 2: Configure Bot Permissions

1. In your app settings, go to "OAuth & Permissions" in the left sidebar
2. Scroll down to "Scopes" section
3. Under "Bot Token Scopes", add these permissions:
   - `chat:write` (Send messages as the bot)
   - `im:write` (Send direct messages)
   - `users:read` (Read user information)

## Step 3: Install App to Workspace

1. Scroll up to "OAuth Tokens for Your Workspace"
2. Click "Install to Workspace"
3. Review permissions and click "Allow"
4. Copy the "Bot User OAuth Token" (starts with `xoxb-`)
xoxb-1612977571328-9448025611828-tg2ulVlP5pJE1xky2pKJaLD6

## Step 4: Get Your User ID

### Method 1: Using Slack App
1. Open Slack in your browser or desktop app
2. Click on your profile picture
3. Select "Profile"
4. Click "More" (three dots)
5. Select "Copy member ID"
U01H81WB669

### Method 2: Using API
1. Go to https://api.slack.com/methods/users.list/test
2. Use your Bot Token
3. Find your user in the response and copy the ID

## Step 5: Add Environment Variables

Add these to your `.env` file:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-1612977571328-9448025611828-tg2ulVlP5pJE1xky2pKJaLD6
SLACK_USER_ID=U01H81WB669  # Your Slack user ID
```

## Step 6: Test the Setup

Run the test script to verify everything works:

```bash
python test_slack.py
```

## Notification Features

The bot will send you DMs with:
- 🟢 Buy decisions with amount and reasoning
- 🔴 Sell decisions with amount and reasoning  
- 🟡 Hold decisions with reasoning
- Current portfolio status (balances, total value)
- Trade execution status
- AI reasoning for each decision

## Troubleshooting

### Common Issues:

1. **"channel_not_found" error**
   - Make sure your User ID is correct
   - Ensure the bot has permission to send DMs

2. **"not_authed" error**
   - Check that your Bot Token is correct
   - Verify the token starts with `xoxb-`

3. **"missing_scope" error**
   - Add the required scopes in OAuth & Permissions
   - Reinstall the app to workspace

### Testing Your Setup:

```python
# Test script content
import os
from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()

client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
response = client.chat_postMessage(
    channel=os.getenv("SLACK_USER_ID"),
    text="🤖 Crypto Trading Bot test message!"
)
print("Test message sent successfully!")
```
