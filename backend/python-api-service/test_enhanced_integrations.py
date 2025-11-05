#!/usr/bin/env python3
"""
Enhanced Integrations Test Suite
Comprehensive testing for Google, Microsoft, and Dropbox enhanced APIs
"""

import asyncio
import json
import logging
from datetime import datetime
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedIntegrationsTester:
    """Test suite for enhanced integrations"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.test_results = {
            'google': {},
            'microsoft': {},
            'dropbox': {},
            'overall': {'passed': 0, 'failed': 0}
        }
    
    async def test_endpoint(self, method: str, endpoint: str, data: dict = None, 
                          expected_status: int = 200, service: str = None):
        """Test an individual endpoint"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            if method == 'GET':
                response = requests.get(url, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            success = response.status_code == expected_status
            result = {
                'success': success,
                'status_code': response.status_code,
                'response': response.json() if response.content else {},
                'error': None
            }
            
            if not success:
                result['error'] = f"Expected {expected_status}, got {response.status_code}"
                logger.error(f"FAILED {endpoint}: {result['error']}")
            else:
                logger.info(f"PASSED {endpoint}: {response.status_code}")
            
            return result
            
        except Exception as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(f"FAILED {endpoint}: {error_msg}")
            return {
                'success': False,
                'status_code': 0,
                'response': {},
                'error': error_msg
            }
    
    async def test_google_enhanced(self):
        """Test Google enhanced APIs"""
        logger.info("Testing Google Enhanced APIs...")
        
        # Health check
        result = await self.test_endpoint(
            'GET', 
            '/api/google/enhanced/health',
            service='google'
        )
        self.test_results['google']['health'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # User info
        result = await self.test_endpoint(
            'POST',
            '/api/google/enhanced/user/info',
            data={'user_id': 'test_user'},
            service='google'
        )
        self.test_results['google']['user_info'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Calendar list
        result = await self.test_endpoint(
            'POST',
            '/api/google/enhanced/calendar/list',
            data={'user_id': 'test_user'},
            service='google'
        )
        self.test_results['google']['calendar_list'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Calendar create
        result = await self.test_endpoint(
            'POST',
            '/api/google/enhanced/calendar/create',
            data={
                'user_id': 'test_user',
                'summary': 'Test Calendar',
                'timezone': 'America/New_York'
            },
            service='google'
        )
        self.test_results['google']['calendar_create'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Gmail messages list
        result = await self.test_endpoint(
            'POST',
            '/api/google/enhanced/gmail/messages/list',
            data={'user_id': 'test_user'},
            service='google'
        )
        self.test_results['google']['gmail_list'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Gmail send
        result = await self.test_endpoint(
            'POST',
            '/api/google/enhanced/gmail/messages/send',
            data={
                'user_id': 'test_user',
                'to_addresses': ['test@example.com'],
                'subject': 'Test Email',
                'body': 'This is a test email'
            },
            service='google'
        )
        self.test_results['google']['gmail_send'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Drive files list
        result = await self.test_endpoint(
            'POST',
            '/api/google/enhanced/drive/files/list',
            data={'user_id': 'test_user'},
            service='google'
        )
        self.test_results['google']['drive_list'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Drive folder create
        result = await self.test_endpoint(
            'POST',
            '/api/google/enhanced/drive/folders/create',
            data={
                'user_id': 'test_user',
                'name': 'Test Folder'
            },
            service='google'
        )
        self.test_results['google']['drive_folder_create'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Status
        result = await self.test_endpoint(
            'POST',
            '/api/google/enhanced/status',
            data={'user_id': 'test_user'},
            service='google'
        )
        self.test_results['google']['status'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
    
    async def test_microsoft_enhanced(self):
        """Test Microsoft enhanced APIs"""
        logger.info("Testing Microsoft Enhanced APIs...")
        
        # Health check
        result = await self.test_endpoint(
            'GET',
            '/api/microsoft/enhanced/health',
            service='microsoft'
        )
        self.test_results['microsoft']['health'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # User info
        result = await self.test_endpoint(
            'POST',
            '/api/microsoft/enhanced/user/info',
            data={'user_id': 'test_user'},
            service='microsoft'
        )
        self.test_results['microsoft']['user_info'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Calendar list
        result = await self.test_endpoint(
            'POST',
            '/api/microsoft/enhanced/calendar/list',
            data={'user_id': 'test_user'},
            service='microsoft'
        )
        self.test_results['microsoft']['calendar_list'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Calendar create
        result = await self.test_endpoint(
            'POST',
            '/api/microsoft/enhanced/calendar/create',
            data={
                'user_id': 'test_user',
                'name': 'Test Calendar'
            },
            service='microsoft'
        )
        self.test_results['microsoft']['calendar_create'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Email send
        result = await self.test_endpoint(
            'POST',
            '/api/microsoft/enhanced/email/send',
            data={
                'user_id': 'test_user',
                'to_addresses': ['test@example.com'],
                'subject': 'Test Email',
                'body': 'This is a test email'
            },
            service='microsoft'
        )
        self.test_results['microsoft']['email_send'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # OneDrive files list
        result = await self.test_endpoint(
            'POST',
            '/api/microsoft/enhanced/onedrive/files/list',
            data={'user_id': 'test_user'},
            service='microsoft'
        )
        self.test_results['microsoft']['onedrive_list'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # OneDrive folder create
        result = await self.test_endpoint(
            'POST',
            '/api/microsoft/enhanced/onedrive/folders/create',
            data={
                'user_id': 'test_user',
                'name': 'Test Folder'
            },
            service='microsoft'
        )
        self.test_results['microsoft']['onedrive_folder_create'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Teams list
        result = await self.test_endpoint(
            'POST',
            '/api/microsoft/enhanced/teams/list',
            data={'user_id': 'test_user'},
            service='microsoft'
        )
        self.test_results['microsoft']['teams_list'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Status
        result = await self.test_endpoint(
            'POST',
            '/api/microsoft/enhanced/status',
            data={'user_id': 'test_user'},
            service='microsoft'
        )
        self.test_results['microsoft']['status'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
    
    async def test_dropbox_enhanced(self):
        """Test Dropbox enhanced APIs"""
        logger.info("Testing Dropbox Enhanced APIs...")
        
        # Health check
        result = await self.test_endpoint(
            'GET',
            '/api/dropbox/enhanced/health',
            service='dropbox'
        )
        self.test_results['dropbox']['health'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # User info
        result = await self.test_endpoint(
            'POST',
            '/api/dropbox/enhanced/user/info',
            data={'user_id': 'test_user'},
            service='dropbox'
        )
        self.test_results['dropbox']['user_info'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Files list
        result = await self.test_endpoint(
            'POST',
            '/api/dropbox/enhanced/files/list',
            data={'user_id': 'test_user'},
            service='dropbox'
        )
        self.test_results['dropbox']['files_list'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Folders list
        result = await self.test_endpoint(
            'POST',
            '/api/dropbox/enhanced/folders/list',
            data={'user_id': 'test_user'},
            service='dropbox'
        )
        self.test_results['dropbox']['folders_list'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Folder create
        result = await self.test_endpoint(
            'POST',
            '/api/dropbox/enhanced/folders/create',
            data={
                'user_id': 'test_user',
                'folder_path': '/Test Folder'
            },
            service='dropbox'
        )
        self.test_results['dropbox']['folder_create'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # File upload
        result = await self.test_endpoint(
            'POST',
            '/api/dropbox/enhanced/files/upload',
            data={
                'user_id': 'test_user',
                'file_content': '48656c6c6f20576f726c64',  # "Hello World" in hex
                'file_name': 'test.txt'
            },
            service='dropbox'
        )
        self.test_results['dropbox']['file_upload'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Search
        result = await self.test_endpoint(
            'POST',
            '/api/dropbox/enhanced/search',
            data={
                'user_id': 'test_user',
                'query': 'test'
            },
            service='dropbox'
        )
        self.test_results['dropbox']['search'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Shared link create
        result = await self.test_endpoint(
            'POST',
            '/api/dropbox/enhanced/links/create',
            data={
                'user_id': 'test_user',
                'path': '/test.txt'
            },
            service='dropbox'
        )
        self.test_results['dropbox']['shared_link_create'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Metadata
        result = await self.test_endpoint(
            'POST',
            '/api/dropbox/enhanced/metadata',
            data={
                'user_id': 'test_user',
                'path': '/test.txt'
            },
            service='dropbox'
        )
        self.test_results['dropbox']['metadata'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Space usage
        result = await self.test_endpoint(
            'POST',
            '/api/dropbox/enhanced/space',
            data={'user_id': 'test_user'},
            service='dropbox'
        )
        self.test_results['dropbox']['space_usage'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
        
        # Status
        result = await self.test_endpoint(
            'POST',
            '/api/dropbox/enhanced/status',
            data={'user_id': 'test_user'},
            service='dropbox'
        )
        self.test_results['dropbox']['status'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
    
    async def test_integrations_status(self):
        """Test overall integrations status"""
        logger.info("Testing Overall Integrations Status...")
        
        result = await self.test_endpoint(
            'GET',
            '/api/integrations/enhanced/status',
            service='overall'
        )
        self.test_results['overall']['integrations_status'] = result
        self.test_results['overall']['passed' if result['success'] else 'failed'] += 1
    
    async def run_all_tests(self):
        """Run all test suites"""
        logger.info("Starting Enhanced Integrations Test Suite...")
        logger.info(f"Testing against: {self.base_url}")
        
        # Test individual service health
        await self.test_google_enhanced()
        await self.test_microsoft_enhanced()
        await self.test_dropbox_enhanced()
        
        # Test overall status
        await self.test_integrations_status()
        
        # Print results
        self.print_results()
    
    def print_results(self):
        """Print test results"""
        print("\n" + "="*80)
        print("ENHANCED INTEGRATIONS TEST RESULTS")
        print("="*80)
        
        total_tests = self.test_results['overall']['passed'] + self.test_results['overall']['failed']
        pass_rate = (self.test_results['overall']['passed'] / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {self.test_results['overall']['passed']}")
        print(f"Failed: {self.test_results['overall']['failed']}")
        print(f"Pass Rate: {pass_rate:.1f}%")
        
        print("\n" + "-"*40)
        print("GOOGLE ENHANCED")
        print("-"*40)
        for test_name, result in self.test_results['google'].items():
            status = "✓ PASS" if result['success'] else "✗ FAIL"
            error = f" - {result['error']}" if result['error'] else ""
            print(f"{test_name:25} {status}{error}")
        
        print("\n" + "-"*40)
        print("MICROSOFT ENHANCED")
        print("-"*40)
        for test_name, result in self.test_results['microsoft'].items():
            status = "✓ PASS" if result['success'] else "✗ FAIL"
            error = f" - {result['error']}" if result['error'] else ""
            print(f"{test_name:25} {status}{error}")
        
        print("\n" + "-"*40)
        print("DROPBOX ENHANCED")
        print("-"*40)
        for test_name, result in self.test_results['dropbox'].items():
            status = "✓ PASS" if result['success'] else "✗ FAIL"
            error = f" - {result['error']}" if result['error'] else ""
            print(f"{test_name:25} {status}{error}")
        
        print("\n" + "-"*40)
        print("OVERALL STATUS")
        print("-"*40)
        for test_name, result in self.test_results['overall'].items():
            if test_name not in ['passed', 'failed']:
                status = "✓ PASS" if result['success'] else "✗ FAIL"
                error = f" - {result['error']}" if result['error'] else ""
                print(f"{test_name:25} {status}{error}")
        
        print("\n" + "="*80)
        if pass_rate >= 80:
            print("🎉 OVERALL RESULT: EXCELLENT")
        elif pass_rate >= 60:
            print("⚠️  OVERALL RESULT: GOOD")
        else:
            print("❌ OVERALL RESULT: NEEDS IMPROVEMENT")
        print("="*80)
        
        # Save results to file
        with open('enhanced_integrations_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        print(f"\nDetailed results saved to: enhanced_integrations_test_results.json")

async def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Integrations Test Suite')
    parser.add_argument('--url', default='http://localhost:8000', 
                       help='Base URL for the API (default: http://localhost:8000)')
    parser.add_argument('--service', choices=['google', 'microsoft', 'dropbox', 'all'], 
                       default='all', help='Service to test (default: all)')
    
    args = parser.parse_args()
    
    tester = EnhancedIntegrationsTester(base_url=args.url)
    
    if args.service == 'all':
        await tester.run_all_tests()
    elif args.service == 'google':
        await tester.test_google_enhanced()
        tester.print_results()
    elif args.service == 'microsoft':
        await tester.test_microsoft_enhanced()
        tester.print_results()
    elif args.service == 'dropbox':
        await tester.test_dropbox_enhanced()
        tester.print_results()

if __name__ == "__main__":
    asyncio.run(main())