#!/usr/bin/env python3
"""
Test script to verify Slack integration setup
"""
import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

def test_slack_setup():
    """Test Slack configuration and send a test message"""
    print("🧪 Testing Slack Integration Setup\n")
    
    # Check environment variables
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    slack_user_id = os.getenv("SLACK_USER_ID")
    
    if not slack_token:
        print("❌ SLACK_BOT_TOKEN not found in .env file")
        print("   Please add: SLACK_BOT_TOKEN=xoxb-your-token-here")
        return False
    
    if not slack_user_id:
        print("❌ SLACK_USER_ID not found in .env file") 
        print("   Please add: SLACK_USER_ID=U1234567890")
        return False
    
    print("✅ Environment variables found")
    print(f"   Bot Token: {slack_token[:20]}...")
    print(f"   User ID: {slack_user_id}")
    
    # Test Slack connection
    try:
        client = WebClient(token=slack_token)
        
        # Test API connection
        print("\n🔗 Testing Slack API connection...")
        auth_response = client.auth_test()
        print(f"✅ Connected as: {auth_response['user']}")
        print(f"   Team: {auth_response['team']}")
        
        # Send test message
        print("\n📨 Sending test message...")
        test_message = """
🧪 *Slack Integration Test* 

This is a test message from your Crypto Trading Bot!

*Test Details:*
• Bot Token: ✅ Valid
• User ID: ✅ Valid  
• Permissions: ✅ Working
• Connection: ✅ Established

Your trading notifications are ready! 🚀

---
_Crypto Auto Trading Bot Test_ 🤖
        """.strip()
        
        response = client.chat_postMessage(
            channel=slack_user_id,
            text="🧪 Crypto Trading Bot Test Message",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": test_message
                    }
                }
            ]
        )
        
        print("✅ Test message sent successfully!")
        print(f"   Message timestamp: {response['ts']}")
        
        return True
        
    except SlackApiError as e:
        print(f"❌ Slack API Error: {e.response['error']}")
        
        # Provide specific error guidance
        error_code = e.response['error']
        if error_code == 'invalid_auth':
            print("   → Check your SLACK_BOT_TOKEN")
        elif error_code == 'channel_not_found':
            print("   → Check your SLACK_USER_ID")
        elif error_code == 'not_in_channel':
            print("   → Bot needs permission to send you DMs")
        elif error_code == 'missing_scope':
            print("   → Add required scopes: chat:write, im:write")
        
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def main():
    """Run the test"""
    print("=" * 50)
    success = test_slack_setup()
    print("\n" + "=" * 50)
    
    if success:
        print("🎉 Slack integration test PASSED!")
        print("Your trading bot is ready to send notifications.")
    else:
        print("💔 Slack integration test FAILED!")
        print("Please check the setup guide: SLACK_SETUP.md")
    
    print("=" * 50)
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
