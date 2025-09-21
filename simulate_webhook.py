#!/usr/bin/env python3
"""
Simulate a real Slack webhook request with proper signature
"""
import requests
import hmac
import hashlib
import time
import json

def send_test_webhook():
    signing_secret = "b3c8e8db46a9071979436e78ee8aeb9d"
    webhook_url = "http://localhost:8000/api/slack/events/"

    # Create test payload
    timestamp = str(int(time.time()))
    payload = {
        "type": "event_callback",
        "team_id": "T12345",
        "event_id": "Ev12345",
        "event": {
            "type": "message",
            "text": "Hello from test webhook!",
            "user": "U12345",
            "channel": "D12345",
            "ts": "1234567890.123456"
        }
    }

    body = json.dumps(payload)

    # Create signature
    sig_basestring = f'v0:{timestamp}:{body}'
    signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Send request
    headers = {
        'Content-Type': 'application/json',
        'X-Slack-Request-Timestamp': timestamp,
        'X-Slack-Signature': signature,
        'User-Agent': 'Slackbot 1.0 (+https://api.slack.com/robots)'
    }

    print(f"Sending webhook to: {webhook_url}")
    print(f"Timestamp: {timestamp}")
    print(f"Signature: {signature}")
    print(f"Payload: {body}")

    try:
        response = requests.post(webhook_url, data=body, headers=headers)
        print(f"Response Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    send_test_webhook()