#!/usr/bin/env python3
"""
Test script to verify Slack webhook signature with manual test
"""
import hmac
import hashlib
import time
import json

def verify_slack_signature(signing_secret, timestamp, body, signature):
    """Test signature verification"""
    # Create the signature string
    sig_basestring = f'v0:{timestamp}:{body}'

    # Create expected signature
    expected_signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    print(f"Timestamp: {timestamp}")
    print(f"Body: {body}")
    print(f"Signature basestring: {sig_basestring}")
    print(f"Received signature: {signature}")
    print(f"Expected signature: {expected_signature}")
    print(f"Match: {hmac.compare_digest(signature, expected_signature)}")

    return hmac.compare_digest(signature, expected_signature)

if __name__ == "__main__":
    # Your signing secret
    signing_secret = "b3c8e8db46a9071979436e78ee8aeb9d"

    # Create a test payload
    current_time = str(int(time.time()))
    test_body = json.dumps({
        "type": "event_callback",
        "team_id": "T12345",
        "event": {
            "type": "message",
            "text": "test message",
            "user": "U12345",
            "channel": "D12345"
        }
    })

    # Create signature
    sig_basestring = f'v0:{current_time}:{test_body}'
    test_signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    print("=== Test Signature Generation ===")
    print(f"Signing Secret: {signing_secret}")
    print(f"Generated signature: {test_signature}")
    print()

    print("=== Test Signature Verification ===")
    verify_slack_signature(signing_secret, current_time, test_body, test_signature)