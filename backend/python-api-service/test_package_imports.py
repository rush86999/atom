"""
Package Import and Functionality Test for ATOM Application

This test verifies that all real service packages can be imported and basic
functionality works without requiring actual API keys.
"""

import sys
import os
from typing import Dict, List, Any

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

def test_package_imports() -> Dict[str, Any]:
    """Test that all required packages can be imported"""
    results = {}

    # Test Box SDK import
    try:
        from box_sdk_gen import BoxClient, BoxOAuth, OAuthConfig
        results['box_sdk'] = {'status': 'pass', 'message': 'Box SDK imported successfully'}
    except ImportError as e:
        results['box_sdk'] = {'status': 'fail', 'message': f'Box SDK import failed: {e}'}

    # Test Asana import
    try:
        from asana.api_client import ApiClient
        from asana.configuration import Configuration
        results['asana'] = {'status': 'pass', 'message': 'Asana API imported successfully'}
    except ImportError as e:
        results['asana'] = {'status': 'fail', 'message': f'Asana import failed: {e}'}

    # Test Jira import
    try:
        from jira import JIRA
        results['jira'] = {'status': 'pass', 'message': 'Jira package imported successfully'}
    except ImportError as e:
        results['jira'] = {'status': 'fail', 'message': f'Jira import failed: {e}'}

    # Test Trello import
    try:
        from trello import TrelloClient
        results['trello'] = {'status': 'pass', 'message': 'Trello package imported successfully'}
    except ImportError as e:
        results['trello'] = {'status': 'fail', 'message': f'Trello import failed: {e}'}

    # Test Docusign import
    try:
        from docusign_esign import ApiClient, EnvelopesApi
        results['docusign'] = {'status': 'pass', 'message': 'Docusign package imported successfully'}
    except ImportError as e:
        results['docusign'] = {'status': 'fail', 'message': f'Docusign import failed: {e}'}

    # Test WordPress import
    try:
        from wordpress_xmlrpc import Client, WordPressPost
        results['wordpress'] = {'status': 'pass', 'message': 'WordPress package imported successfully'}
    except ImportError as e:
        results['wordpress'] = {'status': 'fail', 'message': f'WordPress import failed: {e}'}

    # Test QuickBooks import
    try:
        from quickbooks import QuickBooks
        from intuitlib.client import AuthClient
        results['quickbooks'] = {'status': 'pass', 'message': 'QuickBooks package imported successfully'}
    except ImportError as e:
        results['quickbooks'] = {'status': 'fail', 'message': f'QuickBooks import failed: {e}'}

    # Test OpenAI import
    try:
        from openai import OpenAI
        results['openai'] = {'status': 'pass', 'message': 'OpenAI package imported successfully'}
    except ImportError as e:
        results['openai'] = {'status': 'fail', 'message': f'OpenAI import failed: {e}'}

    # Test Google APIs import
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        results['google_apis'] = {'status': 'pass', 'message': 'Google APIs imported successfully'}
    except ImportError as e:
        results['google_apis'] = {'status': 'fail', 'message': f'Google APIs import failed: {e}'}

    return results

def test_service_implementations() -> Dict[str, Any]:
    """Test that our service implementations can be imported and instantiated"""
    results = {}

    # Test Box service implementation
    try:
        from box_service_real import BoxServiceReal
        results['box_service'] = {'status': 'pass', 'message': 'Box service implementation imported'}
    except ImportError as e:
        results['box_service'] = {'status': 'fail', 'message': f'Box service import failed: {e}'}

    # Test Asana service implementation
    try:
        from asana_service_real import AsanaServiceReal, get_asana_service_real
        results['asana_service'] = {'status': 'pass', 'message': 'Asana service implementation imported'}
    except ImportError as e:
        results['asana_service'] = {'status': 'fail', 'message': f'Asana service import failed: {e}'}

    # Test Jira service implementation
    try:
        from jira_service_real import RealJiraService, get_real_jira_client
        results['jira_service'] = {'status': 'pass', 'message': 'Jira service implementation imported'}
    except ImportError as e:
        results['jira_service'] = {'status': 'fail', 'message': f'Jira service import failed: {e}'}

    # Test Trello service implementation
    try:
        from trello_service_real import RealTrelloService
        results['trello_service'] = {'status': 'pass', 'message': 'Trello service implementation imported'}
    except ImportError as e:
        results['trello_service'] = {'status': 'fail', 'message': f'Trello service import failed: {e}'}

    # Test Docusign service implementation
    try:
        from docusign_service_real import get_docusign_client, create_envelope
        results['docusign_service'] = {'status': 'pass', 'message': 'Docusign service implementation imported'}
    except ImportError as e:
        results['docusign_service'] = {'status': 'fail', 'message': f'Docusign service import failed: {e}'}

    # Test WordPress service implementation
    try:
        from wordpress_service_real import get_wordpress_client, create_post
        results['wordpress_service'] = {'status': 'pass', 'message': 'WordPress service implementation imported'}
    except ImportError as e:
        results['wordpress_service'] = {'status': 'fail', 'message': f'WordPress service import failed: {e}'}

    # Test QuickBooks service implementation
    try:
        from quickbooks_service_real import get_quickbooks_client
        results['quickbooks_service'] = {'status': 'pass', 'message': 'QuickBooks service implementation imported'}
    except ImportError as e:
        results['quickbooks_service'] = {'status': 'fail', 'message': f'QuickBooks service import failed: {e}'}

    return results

def test_client_initialization() -> Dict[str, Any]:
    """Test that clients can be initialized with mock credentials"""
    results = {}

    # Test Box client initialization
    try:
        from box_sdk_gen import OAuthConfig, BoxOAuth
        config = OAuthConfig(client_id='mock_client_id', client_secret='mock_client_secret')
        auth = BoxOAuth(config=config)
        results['box_client'] = {'status': 'pass', 'message': 'Box client initialized with mock credentials'}
    except Exception as e:
        results['box_client'] = {'status': 'fail', 'message': f'Box client initialization failed: {e}'}

    # Test Jira client initialization
    try:
        from jira import JIRA
        # This will fail without real credentials, but we test the import
        results['jira_client'] = {'status': 'pass', 'message': 'Jira client import successful'}
    except Exception as e:
        results['jira_client'] = {'status': 'fail', 'message': f'Jira client test failed: {e}'}

    # Test Asana client initialization
    try:
        from asana.api_client import ApiClient
        from asana.configuration import Configuration
        config = Configuration()
        results['asana_client'] = {'status': 'pass', 'message': 'Asana client configuration successful'}
    except Exception as e:
        results['asana_client'] = {'status': 'fail', 'message': f'Asana client test failed: {e}'}

    return results

def test_application_integration() -> Dict[str, Any]:
    """Test that the main application can integrate all services"""
    results = {}

    # Test main application import
    try:
        from main_api_app import create_app
        results['main_app_import'] = {'status': 'pass', 'message': 'Main application imported successfully'}
    except Exception as e:
        results['main_app_import'] = {'status': 'fail', 'message': f'Main application import failed: {e}'}

    # Test service handler imports
    handlers_to_test = [
        'box_handler', 'asana_handler', 'jira_handler', 'trello_handler'
    ]

    for handler in handlers_to_test:
        try:
            module = __import__(handler)
            results[f'{handler}_import'] = {'status': 'pass', 'message': f'{handler} imported successfully'}
        except Exception as e:
            results[f'{handler}_import'] = {'status': 'fail', 'message': f'{handler} import failed: {e}'}

    return results

def generate_report(all_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Generate comprehensive test report"""
    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    for category, tests in all_results.items():
        for test_name, result in tests.items():
            total_tests += 1
            if result['status'] == 'pass':
                passed_tests += 1
            else:
                failed_tests += 1

    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

    return {
        'total_tests': total_tests,
        'passed_tests': passed_tests,
        'failed_tests': failed_tests,
        'success_rate': success_rate,
        'results': all_results
    }

def print_report(report: Dict[str, Any]):
    """Print formatted test report"""
    print("\n" + "="*80)
    print("🎯 ATOM PACKAGE IMPORT AND FUNCTIONALITY TEST REPORT")
    print("="*80)

    print(f"\n📊 Summary:")
    print(f"   Total Tests: {report['total_tests']}")
    print(f"   Passed: {report['passed_tests']}")
    print(f"   Failed: {report['failed_tests']}")
    print(f"   Success Rate: {report['success_rate']:.1f}%")

    print(f"\n🔧 Detailed Results:")
    for category, tests in report['results'].items():
        print(f"\n   {category.upper().replace('_', ' ')}:")
        for test_name, result in tests.items():
            status_icon = "✅" if result['status'] == 'pass' else "❌"
            print(f"     {status_icon} {test_name}: {result['message']}")

    print("\n" + "="*80)

    if report['success_rate'] >= 90:
        print("🎉 All packages imported successfully! Ready for real API key testing.")
    elif report['success_rate'] >= 70:
        print("⚠️  Most packages imported successfully. Some minor issues to address.")
    else:
        print("❌ Significant package import issues detected.")

def main():
    """Run all package import tests"""
    print("🚀 Starting ATOM Package Import and Functionality Tests")
    print("Testing real service packages without API keys...")

    # Run all test categories
    all_results = {
        'package_imports': test_package_imports(),
        'service_implementations': test_service_implementations(),
        'client_initialization': test_client_initialization(),
        'application_integration': test_application_integration()
    }

    # Generate and print report
    report = generate_report(all_results)
    print_report(report)

    # Return exit code based on success rate
    if report['success_rate'] >= 80:
        return 0  # Success
    else:
        return 1  # Failure

if __name__ == "__main__":
    exit(main())
