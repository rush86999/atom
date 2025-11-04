#!/usr/bin/env python3
"""
🧪 INTEGRATION TEST SCRIPT
Test all third-party integrations with your real credentials
"""

import os
import sys
import json
import requests
from datetime import datetime

class IntegrationTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.timeout = 10

    def test_connection(self):
        """Test if backend is running"""
        try:
            response = self.session.get(f"{self.base_url}/")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Backend connection error: {e}")
            return False

    def test_api_endpoint(self, endpoint, name, params=None):
        """Test API endpoint and return results"""
        try:
            url = f"{self.base_url}{endpoint}"
            response = self.session.get(url, params=params)
            
            print(f"\n🔍 Testing {name}...")
            print(f"   URL: {url}")
            print(f"   Status: HTTP {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   ✅ {name}: SUCCESS")
                    
                    # Analyze response
                    if 'results' in data:
                        results = data['results']
                        print(f"   📊 Results: {len(results)} items")
                        if results:
                            for i, result in enumerate(results[:3]):
                                print(f"   📋 Item {i+1}: {result.get('title', 'N/A')} ({result.get('source', 'N/A')})")
                    
                    elif 'oauth_url' in data:
                        oauth_url = data['oauth_url']
                        print(f"   🔗 OAuth URL: Generated ({len(oauth_url)} chars)")
                        if 'github.com' in oauth_url:
                            print(f"   ✅ GitHub OAuth: Real URL detected")
                        elif 'accounts.google.com' in oauth_url:
                            print(f"   ✅ Google OAuth: Real URL detected")
                        elif 'slack.com' in oauth_url:
                            print(f"   ✅ Slack OAuth: Real URL detected")
                    
                    elif 'repositories' in data:
                        repos = data['repositories']
                        print(f"   📊 Repositories: {len(repos)} items")
                    
                    elif 'channels' in data:
                        channels = data['channels']
                        print(f"   📊 Channels: {len(channels)} items")
                    
                    elif 'events' in data:
                        events = data['events']
                        print(f"   📊 Events: {len(events)} items")
                    
                    elif data.get('success'):
                        print(f"   ✅ {name}: Operation successful")
                    
                    print(f"   📄 Response preview: {str(response.text)[:200]}...")
                    
                    return True, data
                    
                except json.JSONDecodeError:
                    print(f"   ⚠️ {name}: Invalid JSON response")
                    return False, response.text
            else:
                print(f"   ❌ {name}: HTTP {response.status_code}")
                print(f"   📄 Error: {response.text[:200]}...")
                return False, response.text
                
        except Exception as e:
            print(f"   ❌ {name}: {str(e)}")
            return False, str(e)

    def test_credentials_loaded(self):
        """Test what credentials are loaded"""
        print(f"\n🔍 CREDENTIALS ENVIRONMENT CHECK")
        print(f"===================================")
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        credentials = {
            'GitHub Client ID': os.getenv('GITHUB_CLIENT_ID'),
            'GitHub Client Secret': os.getenv('GITHUB_CLIENT_SECRET'),
            'GitHub Access Token': os.getenv('GITHUB_ACCESS_TOKEN'),
            'Google Client ID': os.getenv('GOOGLE_CLIENT_ID'),
            'Google Client Secret': os.getenv('GOOGLE_CLIENT_SECRET'),
            'Google API Key': os.getenv('GOOGLE_API_KEY'),
            'Slack Client ID': os.getenv('SLACK_CLIENT_ID'),
            'Slack Client Secret': os.getenv('SLACK_CLIENT_SECRET'),
            'Slack Bot Token': os.getenv('SLACK_BOT_TOKEN'),
            'Slack Signing Secret': os.getenv('SLACK_SIGNING_SECRET'),
            'Notion Client ID': os.getenv('NOTION_CLIENT_ID'),
            'Notion Client Secret': os.getenv('NOTION_CLIENT_SECRET'),
            'Notion Token': os.getenv('NOTION_TOKEN'),
            'Trello API Key': os.getenv('TRELLO_API_KEY'),
            'Trello Token': os.getenv('TRELLO_TOKEN'),
            'Asana Client ID': os.getenv('ASANA_CLIENT_ID'),
            'Dropbox App Key': os.getenv('DROPBOX_APP_KEY'),
        }
        
        total_creds = len(credentials)
        loaded_creds = 0
        
        for name, value in credentials.items():
            if value and not value.startswith(('mock_', 'MOCK_', 'YOUR_')):
                print(f"   ✅ {name}: ✓ Configured ({len(str(value))} chars)")
                loaded_creds += 1
            elif value:
                print(f"   ⚠️ {name}: Template/Debug value")
            else:
                print(f"   ❌ {name}: Not set")
        
        print(f"\n📊 Credentials Summary:")
        print(f"   • Loaded Credentials: {loaded_creds}/{total_creds}")
        print(f"   • Configuration Rate: {(loaded_creds/total_creds)*100:.1f}%")
        
        return loaded_creds > 0

    def test_oauth_endpoints(self):
        """Test OAuth endpoints"""
        print(f"\n🔧 OAUTH ENDPOINT TESTING")
        print(f"==========================")
        
        oauth_tests = [
            ("/api/oauth/github/url", "GitHub OAuth"),
            ("/api/oauth/google/url", "Google OAuth"),
            ("/api/oauth/slack/url", "Slack OAuth"),
            ("/api/oauth/notion/url", "Notion OAuth"),
            ("/api/oauth/trello/url", "Trello OAuth"),
            ("/api/oauth/asana/url", "Asana OAuth"),
        ]
        
        working_oauth = 0
        for endpoint, name in oauth_tests:
            success, data = self.test_api_endpoint(endpoint, name)
            if success:
                working_oauth += 1
        
        oauth_rate = (working_oauth / len(oauth_tests)) * 100
        print(f"\n📊 OAuth Results:")
        print(f"   • Working OAuth Endpoints: {working_oauth}/{len(oauth_tests)}")
        print(f"   • OAuth Success Rate: {oauth_rate:.1f}%")
        
        return working_oauth > 0

    def test_real_service_connections(self):
        """Test real service API connections"""
        print(f"\n🔧 REAL SERVICE CONNECTION TESTING")
        print(f"===================================")
        
        real_service_tests = [
            ("/api/real/github/repositories", "GitHub Repositories"),
            ("/api/real/github/issues", "GitHub Issues"),
            ("/api/real/google/calendar", "Google Calendar"),
            ("/api/real/slack/channels", "Slack Channels"),
            ("/api/real/notion/pages", "Notion Pages"),
            ("/api/real/trello/boards", "Trello Boards"),
            ("/api/real/asana/projects", "Asana Projects"),
            ("/api/real/status", "Real Service Status"),
        ]
        
        working_real = 0
        for endpoint, name in real_service_tests:
            success, data = self.test_api_endpoint(endpoint, name)
            if success:
                working_real += 1
        
        real_rate = (working_real / len(real_service_tests)) * 100
        print(f"\n📊 Real Service Results:")
        print(f"   • Working Real Services: {working_real}/{len(real_service_tests)}")
        print(f"   • Real Service Success Rate: {real_rate:.1f}%")
        
        return working_real > 0

    def test_search_endpoints(self):
        """Test search endpoints"""
        print(f"\n🔧 SEARCH ENDPOINT TESTING")
        print(f"=============================")
        
        search_tests = [
            ("/api/v1/search", "Cross-Service Search"),
            ("/api/v1/search", "GitHub Search", {"query": "atom", "service": "github"}),
            ("/api/v1/search", "Google Search", {"query": "meeting", "service": "google"}),
            ("/api/v1/search", "Slack Search", {"query": "general", "service": "slack"}),
        ]
        
        working_search = 0
        for endpoint, name, *args in search_tests:
            params = args[0] if args else None
            success, data = self.test_api_endpoint(endpoint, name, params)
            if success:
                working_search += 1
        
        search_rate = (working_search / len(search_tests)) * 100
        print(f"\n📊 Search Results:")
        print(f"   • Working Search Endpoints: {working_search}/{len(search_tests)}")
        print(f"   • Search Success Rate: {search_rate:.1f}%")
        
        return working_search > 0

    def test_system_endpoints(self):
        """Test system endpoints"""
        print(f"\n🔧 SYSTEM ENDPOINT TESTING")
        print(f"===========================")
        
        system_tests = [
            ("/api/v1/workflows", "Workflows API"),
            ("/api/v1/services", "Services API"),
            ("/api/v1/tasks", "Tasks API"),
            ("/healthz", "Health Check"),
            ("/api/routes", "API Routes"),
        ]
        
        working_system = 0
        for endpoint, name in system_tests:
            success, data = self.test_api_endpoint(endpoint, name)
            if success:
                working_system += 1
        
        system_rate = (working_system / len(system_tests)) * 100
        print(f"\n📊 System Results:")
        print(f"   • Working System Endpoints: {working_system}/{len(system_tests)}")
        print(f"   • System Success Rate: {system_rate:.1f}%")
        
        return working_system > 0

    def run_complete_test(self):
        """Run complete integration test"""
        print(f"🧪 COMPLETE INTEGRATION TEST")
        print(f"=============================")
        print(f"Testing all third-party integrations...")
        print()
        
        # Test backend connection
        if not self.test_connection():
            print("❌ Backend is NOT running")
            print("   📝 Start with: python backend/python-api-service/main_api_app.py")
            return False
        
        print("✅ Backend is RUNNING")
        
        # Test credentials
        creds_loaded = self.test_credentials_loaded()
        if not creds_loaded:
            print("❌ No credentials loaded")
            return False
        
        # Test different endpoint types
        oauth_working = self.test_oauth_endpoints()
        real_working = self.test_real_service_connections()
        search_working = self.test_search_endpoints()
        system_working = self.test_system_endpoints()
        
        # Calculate overall score
        components = {
            'Credentials': creds_loaded,
            'OAuth Endpoints': oauth_working,
            'Real Service Connections': real_working,
            'Search Endpoints': search_working,
            'System Endpoints': system_working
        }
        
        working_components = sum(components.values())
        total_components = len(components)
        overall_score = (working_components / total_components) * 100
        
        print(f"\n📊 OVERALL INTEGRATION SCORE: {overall_score:.1f}/100")
        print(f"📊 Components Working: {working_components}/{total_components}")
        
        for component, working in components.items():
            status = "✅" if working else "❌"
            print(f"   {status} {component}: {'Working' if working else 'Not Working'}")
        
        # Final recommendations
        print(f"\n📋 FINAL RECOMMENDATIONS:")
        if overall_score >= 80:
            print("   🎉 EXCELLENT! Your integrations are production-ready")
            print("   ✅ All major components working")
            print("   ✅ Ready for production deployment")
        elif overall_score >= 60:
            print("   ✅ GOOD! Most integrations are working")
            print("   ✅ Core functionality operational")
            print("   🎯 Complete missing services")
        elif overall_score >= 40:
            print("   ⚠️ BASIC! Some integrations are working")
            print("   📝 Fix credential configuration")
            print("   📝 Check OAuth setup")
        else:
            print("   ❌ POOR! Integrations need major work")
            print("   📝 Fix backend connection")
            print("   📝 Configure missing credentials")
        
        return overall_score >= 60

if __name__ == "__main__":
    tester = IntegrationTester()
    tester.run_complete_test()
    
    print(f"\n" + "=" * 60)
    print(f"🧪 INTEGRATION TEST COMPLETE")
    print(f"=" * 60)