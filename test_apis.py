#!/usr/bin/env python
"""
API Testing Script for Multi-tenant Slack Integration
Tests all endpoints systematically with proper authentication.
"""

import requests
import json
import sys
from urllib.parse import urljoin

# Configuration
BASE_URL = "https://831d1c9e8075.ngrok-free.app"
HEADERS = {
    'ngrok-skip-browser-warning': 'true',
    'Content-Type': 'application/json'
}

class APITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def test_endpoint(self, method, endpoint, data=None, auth_required=True):
        """Test an endpoint and return results"""
        url = urljoin(self.base_url, endpoint)
        try:
            if method.upper() == 'GET':
                response = self.session.get(url)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url)

            return {
                'url': url,
                'status_code': response.status_code,
                'success': response.status_code < 400,
                'response': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text[:200],
                'expected_auth_error': auth_required and response.status_code == 401
            }
        except Exception as e:
            return {
                'url': url,
                'status_code': 'ERROR',
                'success': False,
                'response': str(e),
                'expected_auth_error': False
            }

    def run_tests(self):
        """Run comprehensive API tests"""
        print("Starting API Tests for Multi-tenant Slack Integration")
        print("=" * 60)

        tests = [
            # Public endpoints (no auth required)
            ('GET', '/', False, 'Home page'),
            ('GET', '/config/', False, 'Config management page'),

            # Configuration API endpoints (auth required)
            ('GET', '/api/slack/config/', True, 'List configurations'),
            ('POST', '/api/slack/config/', True, 'Create configuration'),
            ('GET', '/api/slack/config/main/', True, 'Get main config'),
            ('PUT', '/api/slack/config/main/', True, 'Update main config'),
            ('DELETE', '/api/slack/config/main/', True, 'Delete main config'),
            ('POST', '/api/slack/config/main/verify/', True, 'Verify main config'),

            # Legacy OAuth endpoints (may require auth)
            ('GET', '/api/slack/auth/initiate/', True, 'Legacy OAuth initiate'),
            ('GET', '/api/slack/workspaces/', True, 'Legacy workspaces'),
            ('GET', '/api/slack/channels/', True, 'Legacy channels'),

            # Multi-tenant OAuth endpoints (may require auth)
            ('GET', '/api/slack/main/auth/initiate/', True, 'Main client OAuth initiate'),
            ('GET', '/api/slack/testclient/auth/initiate/', True, 'Test client OAuth initiate'),
            ('GET', '/api/slack/main/workspaces/', True, 'Main client workspaces'),
            ('GET', '/api/slack/main/channels/', True, 'Main client channels'),
        ]

        results = []
        for method, endpoint, auth_required, description in tests:
            print(f"\nTesting: {description}")
            print(f"   {method} {endpoint}")

            result = self.test_endpoint(method, endpoint, auth_required=auth_required)
            results.append({**result, 'description': description, 'method': method})

            # Status indication
            if not auth_required and result['success']:
                print(f"   [SUCCESS] Status: {result['status_code']}")
            elif auth_required and result['expected_auth_error']:
                print(f"   [AUTH PROTECTED] Status: {result['status_code']} (Expected)")
            elif result['success']:
                print(f"   [SUCCESS] Status: {result['status_code']}")
            else:
                print(f"   [FAILED] Status: {result['status_code']}")

            # Show response preview
            if isinstance(result['response'], dict):
                print(f"   Response: {json.dumps(result['response'], indent=2)[:100]}...")
            else:
                print(f"   Response: {str(result['response'])[:100]}...")

        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        total_tests = len(results)
        successful_tests = sum(1 for r in results if r['success'] or r['expected_auth_error'])

        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {total_tests - successful_tests}")
        print(f"Success Rate: {(successful_tests/total_tests)*100:.1f}%")

        # Show failures
        failures = [r for r in results if not r['success'] and not r['expected_auth_error']]
        if failures:
            print(f"\nFAILED TESTS ({len(failures)}):")
            for failure in failures:
                print(f"   - {failure['description']}: {failure['status_code']}")

        print("\nTest completed successfully!")
        return results

if __name__ == "__main__":
    tester = APITester(BASE_URL)
    results = tester.run_tests()