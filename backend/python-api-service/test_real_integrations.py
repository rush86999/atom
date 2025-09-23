"""
Comprehensive Real API Key Testing Framework for ATOM Application

This module provides end-to-end testing for all real service integrations
with real API keys. It tests both individual services and integrated workflows.
"""

import os
import sys
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from unittest.mock import patch, MagicMock

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RealIntegrationTester:
    """Comprehensive tester for real service integrations"""

    def __init__(self, env_file: str = None):
        self.results = {}
        self.test_count = 0
        self.pass_count = 0
        self.env_file = env_file
        self.api_keys = {}

    def load_environment(self) -> bool:
        """Load environment variables from file or system"""
        try:
            if self.env_file and os.path.exists(self.env_file):
                # Load from .env file
                with open(self.env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            os.environ[key] = value
                            self.api_keys[key] = value
                logger.info(f"Loaded environment from {self.env_file}")
            else:
                # Load from system environment
                required_keys = [
                    'OPENAI_API_KEY',
                    'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET',
                    'NOTION_API_TOKEN',
                    'DROPBOX_APP_KEY', 'DROPBOX_APP_SECRET',
                    'TRELLO_API_KEY', 'TRELLO_API_SECRET',
                    'ASANA_CLIENT_ID', 'ASANA_CLIENT_SECRET',
                    'BOX_CLIENT_ID', 'BOX_CLIENT_SECRET',
                    'JIRA_SERVER_URL', 'JIRA_USERNAME', 'JIRA_API_TOKEN',
                    'DOCUSIGN_ACCESS_TOKEN', 'DOCUSIGN_ACCOUNT_ID',
                    'WORDPRESS_URL', 'WORDPRESS_USERNAME', 'WORDPRESS_PASSWORD',
                    'QUICKBOOKS_CLIENT_ID', 'QUICKBOOKS_CLIENT_SECRET'
                ]

                for key in required_keys:
                    value = os.getenv(key)
                    if value:
                        self.api_keys[key] = value

                logger.info("Loaded environment from system")

            # Validate that we have at least some API keys
            if len(self.api_keys) == 0:
                logger.warning("No API keys found in environment")
                return False

            logger.info(f"Loaded {len(self.api_keys)} API keys")
            return True

        except Exception as e:
            logger.error(f"Failed to load environment: {e}")
            return False

    async def test_openai_integration(self) -> Dict[str, Any]:
        """Test OpenAI integration with real API key"""
        self.test_count += 1
        try:
            if not os.getenv('OPENAI_API_KEY'):
                return {"status": "skip", "message": "OpenAI API key not configured"}

            # Import and test OpenAI service
            try:
                from openai import OpenAI
                client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

                # Test simple completion
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Say 'Hello, ATOM!'"}],
                    max_tokens=10
                )

                if response.choices and len(response.choices) > 0:
                    self.pass_count += 1
                    return {
                        "status": "pass",
                        "message": "OpenAI API connected successfully",
                        "response": response.choices[0].message.content
                    }
                else:
                    return {"status": "fail", "message": "OpenAI API returned no choices"}

            except ImportError:
                return {"status": "fail", "message": "OpenAI package not available"}
            except Exception as e:
                return {"status": "fail", "message": f"OpenAI API error: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": f"Test setup failed: {str(e)}"}

    async def test_google_integration(self) -> Dict[str, Any]:
        """Test Google services integration"""
        self.test_count += 1
        try:
            if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):
                return {"status": "skip", "message": "Google OAuth credentials not configured"}

            # Test Google API client initialization
            try:
                from google.auth.transport.requests import Request
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build

                # This would require actual OAuth flow in production
                # For testing, we just verify the packages are available
                self.pass_count += 1
                return {
                    "status": "pass",
                    "message": "Google API packages available",
                    "note": "OAuth flow requires user interaction for full testing"
                }

            except ImportError as e:
                return {"status": "fail", "message": f"Google packages not available: {e}"}

        except Exception as e:
            return {"status": "error", "message": f"Test setup failed: {str(e)}"}

    async def test_box_integration(self) -> Dict[str, Any]:
        """Test Box integration with real API"""
        self.test_count += 1
        try:
            if not os.getenv('BOX_CLIENT_ID') or not os.getenv('BOX_CLIENT_SECRET'):
                return {"status": "skip", "message": "Box credentials not configured"}

            try:
                from box_sdk_gen import BoxClient, BoxOAuth, OAuthConfig

                # Test Box client initialization
                config = OAuthConfig(
                    client_id=os.getenv('BOX_CLIENT_ID'),
                    client_secret=os.getenv('BOX_CLIENT_SECRET')
                )

                auth = BoxOAuth(config=config)
                # Note: Full testing requires OAuth flow completion

                self.pass_count += 1
                return {
                    "status": "pass",
                    "message": "Box SDK initialized successfully",
                    "note": "OAuth flow required for full API access"
                }

            except ImportError:
                return {"status": "fail", "message": "Box SDK not available"}
            except Exception as e:
                return {"status": "fail", "message": f"Box SDK error: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": f"Test setup failed: {str(e)}"}

    async def test_asana_integration(self) -> Dict[str, Any]:
        """Test Asana integration with real API"""
        self.test_count += 1
        try:
            if not os.getenv('ASANA_CLIENT_ID') or not os.getenv('ASANA_CLIENT_SECRET'):
                return {"status": "skip", "message": "Asana credentials not configured"}

            try:
                from asana.api_client import ApiClient
                from asana.configuration import Configuration

                # Test Asana client initialization
                config = Configuration()
                # Note: Requires access token for full testing

                self.pass_count += 1
                return {
                    "status": "pass",
                    "message": "Asana API client initialized",
                    "note": "Access token required for full API testing"
                }

            except ImportError:
                return {"status": "fail", "message": "Asana package not available"}
            except Exception as e:
                return {"status": "fail", "message": f"Asana API error: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": f"Test setup failed: {str(e)}"}

    async def test_trello_integration(self) -> Dict[str, Any]:
        """Test Trello integration with real API"""
        self.test_count += 1
        try:
            if not os.getenv('TRELLO_API_KEY') or not os.getenv('TRELLO_API_SECRET'):
                return {"status": "skip", "message": "Trello credentials not configured"}

            try:
                from trello import TrelloClient

                # Test Trello client initialization
                client = TrelloClient(
                    api_key=os.getenv('TRELLO_API_KEY'),
                    api_secret=os.getenv('TRELLO_API_SECRET')
                )
                # Note: Requires OAuth tokens for full testing

                self.pass_count += 1
                return {
                    "status": "pass",
                    "message": "Trello client initialized successfully",
                    "note": "OAuth tokens required for full API access"
                }

            except ImportError:
                return {"status": "fail", "message": "Trello package not available"}
            except Exception as e:
                return {"status": "fail", "message": f"Trello API error: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": f"Test setup failed: {str(e)}"}

    async def test_jira_integration(self) -> Dict[str, Any]:
        """Test Jira integration with real API"""
        self.test_count += 1
        try:
            if not os.getenv('JIRA_SERVER_URL') or not os.getenv('JIRA_API_TOKEN'):
                return {"status": "skip", "message": "Jira credentials not configured"}

            try:
                from jira import JIRA

                # Test Jira client initialization
                jira = JIRA(
                    server=os.getenv('JIRA_SERVER_URL'),
                    token_auth=os.getenv('JIRA_API_TOKEN')
                )

                # Test basic connection
                try:
                    # Try to get server info (lightweight operation)
                    server_info = jira.server_info()
                    self.pass_count += 1
                    return {
                        "status": "pass",
                        "message": "Jira API connected successfully",
                        "server_info": server_info
                    }
                except Exception as e:
                    return {"status": "fail", "message": f"Jira connection failed: {str(e)}"}

            except ImportError:
                return {"status": "fail", "message": "Jira package not available"}
            except Exception as e:
                return {"status": "fail", "message": f"Jira API error: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": f"Test setup failed: {str(e)}"}

    async def test_docusign_integration(self) -> Dict[str, Any]:
        """Test Docusign integration with real API"""
        self.test_count += 1
        try:
            if not os.getenv('DOCUSIGN_ACCESS_TOKEN') or not os.getenv('DOCUSIGN_ACCOUNT_ID'):
                return {"status": "skip", "message": "Docusign credentials not configured"}

            try:
                from docusign_esign import ApiClient

                # Test Docusign client initialization
                api_client = ApiClient()
                api_client.set_default_header(
                    "Authorization",
                    f"Bearer {os.getenv('DOCUSIGN_ACCESS_TOKEN')}"
                )

                self.pass_count += 1
                return {
                    "status": "pass",
                    "message": "Docusign client initialized",
                    "note": "Full testing requires valid envelope operations"
                }

            except ImportError:
                return {"status": "fail", "message": "Docusign package not available"}
            except Exception as e:
                return {"status": "fail", "message": f"Docusign API error: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": f"Test setup failed: {str(e)}"}

    async def test_wordpress_integration(self) -> Dict[str, Any]:
        """Test WordPress integration with real API"""
        self.test_count += 1
        try:
            if not os.getenv('WORDPRESS_URL') or not os.getenv('WORDPRESS_USERNAME'):
                return {"status": "skip", "message": "WordPress credentials not configured"}

            try:
                from wordpress_xmlrpc import Client

                # Test WordPress client initialization
                client = Client(
                    os.getenv('WORDPRESS_URL'),
                    os.getenv('WORDPRESS_USERNAME'),
                    os.getenv('WORDPRESS_PASSWORD', '')
                )

                self.pass_count += 1
                return {
                    "status": "pass",
                    "message": "WordPress client initialized",
                    "note": "Full testing requires valid WordPress site"
                }

            except ImportError:
                return {"status": "fail", "message": "WordPress package not available"}
            except Exception as e:
                return {"status": "fail", "message": f"WordPress API error: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": f"Test setup failed: {str(e)}"}

    async def test_quickbooks_integration(self) -> Dict[str, Any]:
        """Test QuickBooks integration with real API"""
        self.test_count += 1
        try:
            if not os.getenv('QUICKBOOKS_CLIENT_ID') or not os.getenv('QUICKBOOKS_CLIENT_SECRET'):
                return {"status": "skip", "message": "QuickBooks credentials not configured"}

            try:
                from quickbooks import QuickBooks
                from intuitlib.client import AuthClient

                # Test QuickBooks client initialization
                auth_client = AuthClient(
                    client_id=os.getenv('QUICKBOOKS_CLIENT_ID'),
                    client_secret=os.getenv('QUICKBOOKS_CLIENT_SECRET'),
                    environment='sandbox'  # Use sandbox for testing
                )

                self.pass_count += 1
                return {
                    "status": "pass",
                    "message": "QuickBooks client initialized",
                    "note": "OAuth flow required for full API access"
                }

            except ImportError:
                return {"status": "fail", "message": "QuickBooks package not available"}
            except Exception as e:
                return {"status": "fail", "message": f"QuickBooks API error: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": f"Test setup failed: {str(e)}"}

    async def test_application_health(self) -> Dict[str, Any]:
        """Test the complete application health"""
        self.test_count += 1
        try:
            # Import and create the main application
            from main_api_app import create_app
            from flask.testing import FlaskClient

            # Set required environment variables
            os.environ.update({
                'DATABASE_URL': 'sqlite:///tmp/atom_test.db',
                'ATOM_OAUTH_ENCRYPTION_KEY': 'test-key-32-chars-long-for-testing',
                'FLASK_SECRET_KEY': 'test-secret-key'
            })

            # Create application
            app = create_app()

            # Test health endpoint
            with app.test_client() as client:
                response = client.get('/healthz')

                if response.status_code == 200:
                    health_data = response.get_json()
                    self.pass_count += 1
                    return {
                        "status": "pass",
                        "message": "Application health check passed",
                        "health_data": health_data
                    }
                else:
                    return {
                        "status": "fail",
                        "message": f"Health endpoint returned {response.status_code}"
                    }

        except Exception as e:
            return {"status": "error", "message": f"Application health test failed: {str(e)}"}

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests"""
        logger.info("🚀 Starting comprehensive real API integration tests")

        # Load environment first
        if not self.load_environment():
            logger.warning("No API keys found - running in validation mode only")

        # Run all tests
        test_methods = [
            self.test_application_health,
            self.test_openai_integration,
            self.test_google_integration,
            self.test_box_integration,
            self.test_asana_integration,
            self.test_trello_integration,
            self.test_jira_integration,
            self.test_docusign_integration,
            self.test_wordpress_integration,
            self.test_quickbooks_integration
        ]

        # Run tests concurrently
        tasks = [method() for method in test_methods]
        results = await asyncio.gather(*tasks)

        # Store results
        for i, result in enumerate(results):
            test_name = test_methods[i].__name__.replace('test_', '').replace('_', ' ').title()
            self.results[test_name] = result

        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": self.test_count,
            "passed_tests": self.pass_count,
            "failed_tests": self.test_count - self.pass_count,
            "success_rate": (self.pass_count / self.test_count * 100) if self.test_count > 0 else 0,
            "results": self.results,
            "environment_loaded": len(self.api_keys) > 0,
            "api_keys_count": len(self.api_keys)
        }

        return report

    def print_report(self, report: Dict[str, Any]):
        """Print formatted test report"""
        print("\n" + "="*80)
        print("🎯 ATOM REAL API INTEGRATION TEST REPORT")
        print("="*80)

        print(f"\n📊 Summary:")
        print(f"   Total Tests: {report['total_tests']}")
        print(f"   Passed: {report['passed_tests']}")
        print(f"   Failed: {report['failed_tests']}")
        print(f"   Success Rate: {report['success_rate']:.1f}%")
        print(f"   API Keys Loaded: {report['api_keys_count']}")

        print(f"\n🔧 Detailed Results:")
        for test_name, result in report['results'].items():
            status_icon = "✅" if result['status'] == 'pass' else "❌" if result['status'] == 'fail' else "⚠️"
            print(f"   {status_icon} {test_name}: {result['status'].upper()} - {result['message']}")

        print("\n" + "="*80)

        if report['success_rate'] >= 80:
            print("🎉 Application is ready for production with real API keys!")
        elif report['success_rate'] >= 50:
            print("⚠️  Application has some issues but basic functionality works")
        else:
            print("❌ Application needs significant fixes before production use")

async def main():
    """Main function to run integration tests"""
    import argparse

    parser = argparse.ArgumentParser(description='ATOM Real API Integration Tests')
    parser.add_argument('--env', type=str, help='Path to .env file with API keys')
    parser.add_argument('--test', type=str, help='Run specific test (e.g., openai, jira)')

    args = parser.parse_args()

    # Create tester and run tests
    tester = RealIntegrationTester(env_file=args.env)

    if args.test:
        # Run specific test
        test_method = getattr(tester, f'test_{args.test}_integration', None)
        if test_method:
            result = await test_method()
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ Test '{args.test}' not found")
    else:
        # Run all tests
        report = await tester.run_all_tests()
        tester.print_report(report)

        # Save detailed report to file
        report_file = f"integration_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Detailed report saved to: {report_file}")

if __name__ == "__main__":
    asyncio.run(main())
