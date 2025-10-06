#!/usr/bin/env python3
"""
Debug script to test Slack API configuration and find the correct way to send DMs
"""

import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

def test_slack_configuration():
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    slack_user_id = os.getenv("SLACK_USER_ID")
    
    print("🔍 Slack Configuration Debug")
    print("=" * 50)
    
    if not slack_token:
        print("❌ SLACK_BOT_TOKEN not found in .env")
        return
    
    if not slack_user_id:
        print("❌ SLACK_USER_ID not found in .env")
        return
    
    print(f"✅ SLACK_BOT_TOKEN: {slack_token[:10]}...")
    print(f"✅ SLACK_USER_ID: {slack_user_id}")
    
    client = WebClient(token=slack_token)
    
    # Test 1: Check bot authentication
    print("\n🧪 Test 1: Bot Authentication")
    try:
        auth_response = client.auth_test()
        print(f"✅ Bot authenticated successfully")
        print(f"   User: {auth_response.get('user')}")
        print(f"   User ID: {auth_response.get('user_id')}")
        print(f"   Team: {auth_response.get('team')}")
        bot_user_id = auth_response.get('user_id')
    except SlackApiError as e:
        print(f"❌ Bot authentication failed: {e.response['error']}")
        return
    
    # Test 2: Check if the provided user ID is valid
    print(f"\n🧪 Test 2: User ID Validation")
    try:
        user_info = client.users_info(user=slack_user_id)
        if user_info['ok']:
            user = user_info['user']
            print(f"✅ User ID is valid")
            print(f"   Name: {user.get('real_name', 'N/A')}")
            print(f"   Username: @{user.get('name', 'N/A')}")
            print(f"   Is Bot: {user.get('is_bot', False)}")
        else:
            print(f"❌ User ID validation failed")
    except SlackApiError as e:
        print(f"❌ User ID validation error: {e.response['error']}")
        if e.response['error'] == 'user_not_found':
            print(f"   The user ID '{slack_user_id}' doesn't exist in this workspace")
        elif e.response['error'] == 'missing_scope':
            print(f"   Bot doesn't have 'users:read' permission")
    
    # Test 3: Try different methods to send a message
    print(f"\n🧪 Test 3: Message Sending Methods")
    
    test_message = "🧪 Slack API Test Message - Please ignore"
    
    methods_to_try = [
        ("Direct User ID", slack_user_id),
        ("@ User ID", f"@{slack_user_id}"),
        ("# User ID", f"#{slack_user_id}"),
    ]
    
    for method_name, channel_format in methods_to_try:
        print(f"\n   Testing {method_name}: '{channel_format}'")
        try:
            response = client.chat_postMessage(
                channel=channel_format,
                text=test_message
            )
            if response['ok']:
                print(f"   ✅ SUCCESS with {method_name}")
                print(f"      Channel ID: {response.get('channel')}")
                print(f"      Message TS: {response.get('ts')}")
            else:
                print(f"   ❌ Failed with {method_name}")
        except SlackApiError as e:
            print(f"   ❌ Error with {method_name}: {e.response['error']}")
    
    # Test 4: Try to open DM conversation
    print(f"\n🧪 Test 4: Open DM Conversation")
    try:
        dm_response = client.conversations_open(users=slack_user_id)
        if dm_response['ok']:
            channel_id = dm_response['channel']['id']
            print(f"✅ DM conversation opened successfully")
            print(f"   Channel ID: {channel_id}")
            
            # Try sending message to the DM channel
            print(f"   Testing message to DM channel...")
            try:
                response = client.chat_postMessage(
                    channel=channel_id,
                    text=test_message + " (via DM channel)"
                )
                if response['ok']:
                    print(f"   ✅ SUCCESS sending to DM channel")
                else:
                    print(f"   ❌ Failed sending to DM channel")
            except SlackApiError as e:
                print(f"   ❌ Error sending to DM channel: {e.response['error']}")
        else:
            print(f"❌ Failed to open DM conversation")
    except SlackApiError as e:
        print(f"❌ DM conversation error: {e.response['error']}")
        if e.response['error'] == 'missing_scope':
            print(f"   Bot doesn't have 'im:write' or 'chat:write' permission")
    
    print(f"\n📋 Summary:")
    print(f"   If any method above worked, use that format in your code.")
    print(f"   If none worked, check bot permissions in your Slack app settings.")
    print(f"   Required scopes: chat:write, users:read, im:write")

if __name__ == "__main__":
    test_slack_configuration()
