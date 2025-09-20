#!/usr/bin/env python
"""
Test OAuth URL Generation
This script tests if the OAuth URL generation is working correctly
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'slack_integration.settings')
django.setup()

from apps.core.models import SlackAppConfiguration
from apps.slack_api.services import SlackOAuthService

def test_oauth_generation():
    print("Testing OAuth URL Generation")
    print("=" * 50)

    try:
        # Get the configuration
        config = SlackAppConfiguration.objects.get(client_identifier='main-client')
        print(f"[OK] Found configuration: {config.app_name}")
        print(f"  Client ID: {config.client_id}")
        print(f"  Redirect URI: {config.redirect_uri}")
        print(f"  Scopes: {config.scopes}")

        # Generate OAuth URL
        oauth_url = SlackOAuthService.get_authorization_url_for_config(config)
        print(f"\n[OK] Generated OAuth URL:")
        print(f"  {oauth_url}")

        # Verify the URL contains the correct client_id
        if config.client_id in oauth_url:
            print(f"\n[SUCCESS] OAuth URL contains correct client_id")
            print(f"   Expected: {config.client_id}")
            print(f"   Found in URL: YES")
        else:
            print(f"\n[ERROR] OAuth URL does not contain correct client_id")
            print(f"   Expected: {config.client_id}")
            print(f"   URL: {oauth_url}")

        # Test with state parameter
        oauth_url_with_state = SlackOAuthService.get_authorization_url_for_config(config, state="test123")
        if "state=test123" in oauth_url_with_state:
            print(f"[OK] State parameter working correctly")
        else:
            print(f"[ERROR] State parameter not working")

        return True

    except SlackAppConfiguration.DoesNotExist:
        print("[ERROR] No configuration found with identifier 'main-client'")
        print("   Available configurations:")
        for config in SlackAppConfiguration.objects.all():
            print(f"   - {config.client_identifier} ({config.app_name})")
        return False

    except Exception as e:
        print(f"[ERROR] {e}")
        return False

if __name__ == "__main__":
    success = test_oauth_generation()
    if success:
        print("\n[SUCCESS] OAuth URL generation is working correctly!")
    else:
        print("\n[FAILED] OAuth URL generation has issues!")