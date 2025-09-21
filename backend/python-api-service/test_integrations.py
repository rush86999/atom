#!/usr/bin/env python3
"""
ATOM Integration Testing Script

This script tests the ATOM backend API integrations with real API keys.
It validates API key formats, tests integration endpoints, and verifies
that services can connect to external APIs.

Usage:
    python test_integrations.py --env .env.production
    python test_integrations.py --keys-only
    python test_integrations.py --test-all
"""

import os
import sys
import json
import logging
import argparse
import requests
from typing import Dict, List, Optional, Any
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/atom_integration_test.log')
    ]
)
logger = logging.getLogger(__name__)

class IntegrationTester:
    """Test ATOM API integrations with real API keys"""

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.api_keys = {}
        self.test_results = {}

    def load_env_file(self, env_file: str) -> bool:
        """Load environment variables from file"""
        try:
            if not Path(env_file).exists():
                logger.error(f"Environment file not found: {env_file}")
                return False

            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Remove quotes if present
                        if value.startswith(('"', "'")) and value.endswith(('"', "'")):
                            value = value[1:-1]
                        os.environ[key] = value
                        logger.info(f"Loaded {key} from environment file")

            return True

        except Exception as e:
            logger.error(f"Error loading environment file: {e}")
            return False

    def collect_api_keys(self) -> Dict[str, str]:
        """Collect API keys from environment variables"""
        keys = {}

        # OpenAI
        keys['openai_api_key'] = os.getenv('OPENAI_API_KEY', '')

        # Google
        keys['google_client_id'] = os.getenv('GOOGLE_CLIENT_ID', '')
        keys['google_client_secret'] = os.getenv('GOOGLE_CLIENT_SECRET', '')

        # Notion
        keys['notion_api_token'] = os.getenv('NOTION_API_TOKEN', '')

        # Dropbox
        keys['dropbox_access_token'] = os.getenv('DROPBOX_ACCESS_TOKEN', '')
        keys['dropbox_app_key'] = os.getenv('DROPBOX_APP_KEY', '')
        keys['dropbox_app_secret'] = os.getenv('DROPBOX_APP_SECRET', '')

        # Trello
        keys['trello_api_key'] = os.getenv('TRELLO_API_KEY', '')
        keys['trello_api_secret'] = os.getenv('TRELLO_API_SECRET', '')

        # Asana
        keys['asana_access_token'] = os.getenv('ASANA_ACCESS_TOKEN', '')
        keys['asana_client_id'] = os.getenv('ASANA_CLIENT_ID', '')
        keys['asana_client_secret'] = os.getenv('ASANA_CLIENT_SECRET', '')

        # Slack
        keys['slack_bot_token'] = os.getenv('SLACK_BOT_TOKEN', '')

        # GitHub
        keys['github_access_token'] = os.getenv('GITHUB_ACCESS_TOKEN', '')

        # LinkedIn
        keys['linkedin_client_id'] = os.getenv('LINKEDIN_CLIENT_ID', '')
        keys['linkedin_client_secret'] = os.getenv('LINKEDIN_CLIENT_SECRET', '')

        # Plaid
        keys['plaid_client_id'] = os.getenv('PLAID_CLIENT_ID', '')
        keys['plaid_secret'] = os.getenv('PLAID_SECRET', '')

        # Deepgram
        keys['deepgram_api_key'] = os.getenv('DEEPGRAM_API_KEY', '')

        self.api_keys = {k: v for k, v in keys.items() if v}
        return self.api_keys

    def validate_key_format(self, key_name: str, key_value: str) -> Dict[str, Any]:
        """Validate API key format"""
        validation = {
            'valid': False,
            'message': '',
            'length': len(key_value)
        }

        try:
            if not key_value:
                validation['message'] = 'Key is empty'
                return validation

            # OpenAI API key validation (starts with sk-)
            if key_name == 'openai_api_key':
                if key_value.startswith('sk-'):
                    validation['valid'] = True
                    validation['message'] = 'Valid OpenAI API key format'
                else:
                    validation['message'] = 'OpenAI API key should start with "sk-"'

            # Notion API token validation (starts with secret_)
            elif key_name == 'notion_api_token':
                if key_value.startswith('secret_'):
                    validation['valid'] = True
                    validation['message'] = 'Valid Notion API token format'
                else:
                    validation['message'] = 'Notion API token should start with "secret_"'

            # GitHub access token validation (starts with ghp_)
            elif key_name == 'github_access_token':
                if key_value.startswith('ghp_'):
                    validation['valid'] = True
                    validation['message'] = 'Valid GitHub access token format'
                else:
                    validation['message'] = 'GitHub access token should start with "ghp_"'

            # Generic validation for other keys
            else:
                if len(key_value) >= 20:  # Minimum reasonable length for API keys
                    validation['valid'] = True
                    validation['message'] = 'Valid API key format'
                else:
                    validation['message'] = f'API key too short (min 20 chars, got {len(key_value)})'

        except Exception as e:
            validation['message'] = f'Validation error: {str(e)}'

        return validation

    def test_key_validation_endpoint(self) -> Dict[str, Any]:
        """Test the API key validation endpoint"""
        headers = {
            'Content-Type': 'application/json',
        }

        # Add all API keys to headers
        for key_name, key_value in self.api_keys.items():
            header_name = self._get_header_name(key_name)
            if header_name:
                headers[header_name] = key_value

        try:
            response = requests.post(
                f"{self.base_url}/api/integrations/validate",
                headers=headers,
                timeout=30
            )

            result = {
                'status_code': response.status_code,
                'success': response.status_code == 200,
                'data': response.json() if response.status_code == 200 else {}
            }

            return result

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': 0
            }

    def test_health_endpoint(self) -> Dict[str, Any]:
        """Test the health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/healthz", timeout=10)
            return {
                'status_code': response.status_code,
                'success': response.status_code == 200,
                'data': response.json() if response.status_code == 200 else {}
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': 0
            }

    def test_dashboard_endpoint(self) -> Dict[str, Any]:
        """Test the dashboard endpoint with API keys"""
        headers = {
            'Content-Type': 'application/json',
        }

        # Add API keys to headers
        for key_name, key_value in self.api_keys.items():
            header_name = self._get_header_name(key_name)
            if header_name:
                headers[header_name] = key_value

        try:
            response = requests.get(
                f"{self.base_url}/api/dashboard?user_id=test_user",
                headers=headers,
                timeout=30
            )

            return {
                'status_code': response.status_code,
                'success': response.status_code == 200,
                'data': response.json() if response.status_code == 200 else {}
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': 0
            }

    def _get_header_name(self, key_name: str) -> Optional[str]:
        """Convert internal key name to HTTP header name"""
        header_map = {
            'openai_api_key': 'X-OpenAI-API-Key',
            'google_client_id': 'X-Google-Client-ID',
            'google_client_secret': 'X-Google-Client-Secret',
            'notion_api_token': 'X-Notion-API-Token',
            'dropbox_access_token': 'X-Dropbox-Access-Token',
            'trello_api_key': 'X-Trello-API-Key',
            'trello_api_secret': 'X-Trello-API-Secret',
            'asana_access_token': 'X-Asana-Access-Token',
            'slack_bot_token': 'X-Slack-Bot-Token',
            'github_access_token': 'X-Github-Access-Token',
            'linkedin_client_id': 'X-LinkedIn-Client-ID',
            'linkedin_client_secret': 'X-LinkedIn-Client-Secret'
        }
        return header_map.get(key_name)

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests"""
        results = {}

        logger.info("=" * 60)
        logger.info("🚀 Starting ATOM Integration Tests")
        logger.info("=" * 60)

        # Test 1: Collect and validate API keys
        logger.info("\n1. 🔑 Validating API Keys...")
        api_keys = self.collect_api_keys()
        results['api_keys'] = {}

        for key_name, key_value in api_keys.items():
            validation = self.validate_key_format(key_name, key_value)
            results['api_keys'][key_name] = validation

            status = "✅" if validation['valid'] else "❌"
            logger.info(f"   {status} {key_name}: {validation['message']}")

        # Test 2: Health endpoint
        logger.info("\n2. 🩺 Testing Health Endpoint...")
        health_result = self.test_health_endpoint()
        results['health'] = health_result

        if health_result['success']:
            logger.info(f"   ✅ Health endpoint: {health_result['status_code']} - {health_result['data']}")
        else:
            logger.info(f"   ❌ Health endpoint failed: {health_result.get('error', 'Unknown error')}")

        # Test 3: API Key validation endpoint
        logger.info("\n3. 🔐 Testing API Key Validation Endpoint...")
        validation_result = self.test_key_validation_endpoint()
        results['key_validation'] = validation_result

        if validation_result['success']:
            logger.info(f"   ✅ Key validation endpoint: {validation_result['status_code']}")
            # Log individual validation results
            if 'validation_results' in validation_result.get('data', {}):
                for key_name, key_result in validation_result['data']['validation_results'].items():
                    status = "✅" if key_result.get('valid', False) else "❌"
                    logger.info(f"      {status} {key_name}: {key_result.get('message', 'No message')}")
        else:
            logger.info(f"   ❌ Key validation failed: {validation_result.get('error', 'Unknown error')}")

        # Test 4: Dashboard endpoint
        logger.info("\n4. 📊 Testing Dashboard Endpoint...")
        dashboard_result = self.test_dashboard_endpoint()
        results['dashboard'] = dashboard_result

        if dashboard_result['success']:
            logger.info(f"   ✅ Dashboard endpoint: {dashboard_result['status_code']}")
            # Check if we got real data or mock data
            data = dashboard_result.get('data', {})
            if data.get('calendar') and len(data['calendar']) > 0:
                if data['calendar'][0].get('provider') == 'mock':
                    logger.info("   ⚠️  Dashboard using mock data (real API keys may not be working)")
                else:
                    logger.info("   ✅ Dashboard returning real integration data!")
        else:
            logger.info(f"   ❌ Dashboard failed: {dashboard_result.get('error', 'Unknown error')}")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 Test Summary")
        logger.info("=" * 60)

        total_tests = 4
        passed_tests = sum([
            1 if health_result['success'] else 0,
            1 if validation_result['success'] else 0,
            1 if dashboard_result['success'] else 0,
            1 if any(v['valid'] for v in results['api_keys'].values()) else 0
        ])

        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {total_tests - passed_tests}")

        if passed_tests == total_tests:
            logger.info("🎉 All integration tests passed! API keys are working correctly.")
        else:
            logger.info("⚠️  Some tests failed. Check the logs above for details.")

        return results

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='ATOM Integration Testing Script')
    parser.add_argument('--env', help='Path to environment file', default='.env.production')
    parser.add_argument('--url', help='Base URL of ATOM API', default='http://localhost:5058')
    parser.add_argument('--keys-only', help='Only validate API keys, don\'t test endpoints', action='store_true')
    parser.add_argument('--test-all', help='Run all tests', action='store_true')

    args = parser.parse_args()

    tester = IntegrationTester(base_url=args.url)

    # Load environment file if specified
    if args.env and args.env != '.env.production':
        if not tester.load_env_file(args.env):
            sys.exit(1)

    # Collect API keys
    api_keys = tester.collect_api_keys()

    if not api_keys:
        logger.warning("No API keys found in environment variables.")
        logger.info("Please set API keys or use --env to specify an environment file.")
        sys.exit(1)

    logger.info(f"Found {len(api_keys)} API keys in environment")

    if args.keys_only:
        # Only validate key formats
        for key_name, key_value in api_keys.items():
            validation = tester.validate_key_format(key_name, key_value)
            status = "✅" if validation['valid'] else "❌"
            print(f"{status} {key_name}: {validation['message']}")
    else:
        # Run all tests
        tester.run_all_tests()

if __name__ == '__main__':
    main()
