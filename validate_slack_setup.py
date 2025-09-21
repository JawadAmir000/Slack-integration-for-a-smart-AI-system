#!/usr/bin/env python3
"""
Comprehensive Slack webhook validation script
"""
import requests
import json
import hmac
import hashlib
import time

def test_webhook_url_verification():
    """Test URL verification challenge"""
    print("Testing URL Verification Challenge...")

    # Simulate Slack's URL verification challenge
    challenge_payload = {
        "token": "verification_token",
        "challenge": "test_challenge_12345",
        "type": "url_verification"
    }

    try:
        response = requests.post(
            "https://cd31db931d79.ngrok-free.app/api/slack/events/",
            json=challenge_payload,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Slackbot 1.0 (+https://api.slack.com/robots)'
            }
        )

        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")

        if response.status_code == 200:
            resp_data = response.json()
            if resp_data.get('challenge') == 'test_challenge_12345':
                print("   ✅ URL verification working correctly!")
                return True
            else:
                print("   ❌ Challenge response incorrect")
        else:
            print("   ❌ URL verification failed")

    except Exception as e:
        print(f"   ❌ Error: {e}")

    return False

def test_webhook_with_proper_signature():
    """Test webhook with proper Slack signature"""
    print("\n🔍 Testing Webhook with Proper Signature...")

    signing_secret = "b3c8e8db46a9071979436e78ee8aeb9d"
    timestamp = str(int(time.time()))

    # Real Slack event payload structure
    payload = {
        "token": "verification_token",
        "team_id": "T1234567890",
        "api_app_id": "A1234567890",
        "event": {
            "type": "message",
            "channel": "D1234567890",
            "user": "U1234567890",
            "text": "Test message from validation script",
            "ts": "1234567890.123456"
        },
        "type": "event_callback",
        "event_id": "Ev" + str(int(time.time())),
        "event_time": int(time.time())
    }

    body = json.dumps(payload)

    # Create signature
    sig_basestring = f'v0:{timestamp}:{body}'
    signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        'Content-Type': 'application/json',
        'X-Slack-Request-Timestamp': timestamp,
        'X-Slack-Signature': signature,
        'User-Agent': 'Slackbot 1.0 (+https://api.slack.com/robots)'
    }

    try:
        response = requests.post(
            "https://cd31db931d79.ngrok-free.app/api/slack/events/",
            data=body,
            headers=headers
        )

        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")

        if response.status_code == 200:
            print("   ✅ Webhook signature verification working!")
            return True
        else:
            print("   ❌ Webhook signature verification failed")

    except Exception as e:
        print(f"   ❌ Error: {e}")

    return False

def check_ngrok_status():
    """Check ngrok tunnel status"""
    print("\n🔍 Checking ngrok Tunnel Status...")

    try:
        response = requests.get("http://localhost:4040/api/tunnels")
        tunnels = response.json()['tunnels']

        for tunnel in tunnels:
            if tunnel['proto'] == 'https':
                public_url = tunnel['public_url']
                print(f"   🌐 Public URL: {public_url}")
                print(f"   📊 Connections: {tunnel['metrics']['conns']['count']}")
                print(f"   📈 HTTP Requests: {tunnel['metrics']['http']['count']}")

                # Test accessibility
                test_response = requests.get(f"{public_url}/api/slack/events/")
                if test_response.status_code == 200:
                    print("   ✅ Tunnel accessible from internet")
                    return public_url
                else:
                    print("   ❌ Tunnel not accessible")

    except Exception as e:
        print(f"   ❌ Error checking ngrok: {e}")

    return None

def check_slack_app_requirements():
    """Check what Slack needs for proper setup"""
    print("\n📋 Slack App Requirements Checklist:")
    print("   1. Event Subscriptions:")
    print("      - Enable Events: ON")
    print("      - Request URL: https://cd31db931d79.ngrok-free.app/api/slack/events/")
    print("      - URL should show 'Verified' with green checkmark")
    print("   2. Subscribe to Bot Events:")
    print("      - message.channels")
    print("      - message.groups")
    print("      - message.im")
    print("      - message.mpim")
    print("   3. OAuth & Permissions - Bot Token Scopes:")
    print("      - chat:read")
    print("      - channels:read")
    print("      - groups:read")
    print("      - im:read")
    print("      - mpim:read")
    print("   4. App Installation:")
    print("      - Install app to workspace")
    print("      - Bot user should appear in workspace")
    print("   5. Basic Information:")
    print("      - Signing Secret: b3c8e8db46a9071979436e78ee8aeb9d")

def main():
    print("Slack Integration Validation Script")
    print("=" * 50)

    # Check ngrok
    ngrok_url = check_ngrok_status()

    # Test URL verification
    url_verification_ok = test_webhook_url_verification()

    # Test webhook with signature
    webhook_ok = test_webhook_with_proper_signature()

    # Show requirements
    check_slack_app_requirements()

    print("\n" + "=" * 50)
    print("🏁 VALIDATION SUMMARY:")
    print(f"   ngrok Tunnel: {'✅ Working' if ngrok_url else '❌ Issues'}")
    print(f"   URL Verification: {'✅ Working' if url_verification_ok else '❌ Issues'}")
    print(f"   Webhook Signature: {'✅ Working' if webhook_ok else '❌ Issues'}")

    if all([ngrok_url, url_verification_ok, webhook_ok]):
        print("\n🎉 All webhook components working! Issue is likely in Slack app configuration.")
        print("📝 Please verify the Slack App Requirements above.")
    else:
        print("\n⚠️  Some components need attention.")

if __name__ == "__main__":
    main()