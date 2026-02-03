"""
WhatsApp Business Production Testing Script
Comprehensive testing suite for WhatsApp Business integration
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)

class WhatsAppProductionTester:
    """Comprehensive testing suite for WhatsApp Business integration"""
    
    def __init__(self, base_url="http://127.0.0.1:5058"):
        self.base_url = base_url
        self.test_results = []
        self.start_time = datetime.now()
    
    def test_api_endpoints(self) -> dict:
        """Test all WhatsApp API endpoints"""
        print("🧪 Testing WhatsApp API Endpoints...")
        
        endpoints = [
            # Health checks
            {"method": "GET", "url": "/api/whatsapp/health", "name": "Basic Health Check"},
            {"method": "GET", "url": "/api/whatsapp/service/health", "name": "Service Health Check"},
            {"method": "GET", "url": "/api/whatsapp/service/metrics", "name": "Service Metrics"},
            
            # Configuration
            {"method": "POST", "url": "/api/whatsapp/service/initialize", "name": "Service Initialization"},
            {"method": "GET", "url": "/api/whatsapp/configuration/business-profile", "name": "Business Profile"},
            
            # Messaging
            {"method": "GET", "url": "/api/whatsapp/conversations?limit=10", "name": "Get Conversations"},
            {"method": "GET", "url": "/api/whatsapp/analytics?start_date=2024-01-01&end_date=2024-12-31", "name": "Get Analytics"},
            {"method": "GET", "url": "/api/whatsapp/analytics/export?format=json", "name": "Export Analytics JSON"},
            
            # Webhook verification
            {"method": "GET", "url": "/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=test&hub.challenge=challenge123", "name": "Webhook Verification"},
        ]
        
        results = []
        success_count = 0
        
        for endpoint in endpoints:
            print(f"  🧪 Testing: {endpoint['name']}")
            
            try:
                url = f"{self.base_url}{endpoint['url']}"
                
                if endpoint['method'] == 'GET':
                    response = requests.get(url, timeout=10)
                elif endpoint['method'] == 'POST':
                    response = requests.post(url, json={}, timeout=10)
                
                success = response.status_code < 400
                result = {
                    'endpoint': endpoint['name'],
                    'url': endpoint['url'],
                    'method': endpoint['method'],
                    'status_code': response.status_code,
                    'success': success,
                    'response_time': response.elapsed.total_seconds(),
                    'response': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text[:200]
                }
                
                if success:
                    success_count += 1
                    print(f"    ✅ {endpoint['name']}: {response.status_code}")
                else:
                    print(f"    ❌ {endpoint['name']}: {response.status_code}")
                    if 'error' in result.get('response', {}):
                        print(f"       Error: {result['response']['error']}")
                
                results.append(result)
                
            except Exception as e:
                error_result = {
                    'endpoint': endpoint['name'],
                    'url': endpoint['url'],
                    'method': endpoint['method'],
                    'status_code': 'error',
                    'success': False,
                    'error': str(e)
                }
                results.append(error_result)
                print(f"    ❌ {endpoint['name']}: {str(e)}")
        
        endpoint_summary = {
            'test_name': 'API Endpoints',
            'total_tests': len(endpoints),
            'successful_tests': success_count,
            'success_rate': (success_count / len(endpoints)) * 100,
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"\\n📊 API Endpoint Results: {success_count}/{len(endpoints)} ({endpoint_summary['success_rate']:.1f}%)")
        return endpoint_summary
    
    def test_message_capabilities(self) -> dict:
        """Test message sending capabilities"""
        print("\\n🧪 Testing Message Capabilities...")
        
        # Test text message
        try:
            message_data = {
                "to": "+1234567890",
                "type": "text", 
                "content": {"body": "Test message from ATOM WhatsApp integration"}
            }
            
            response = requests.post(
                f"{self.base_url}/api/whatsapp/send",
                json=message_data,
                timeout=10
            )
            
            text_result = {
                'message_type': 'text',
                'success': response.status_code < 400,
                'status_code': response.status_code,
                'response': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text[:200]
            }
            
            print(f"  🧪 Text Message: {'✅' if text_result['success'] else '❌'} ({text_result['status_code']})")
            
        except Exception as e:
            text_result = {
                'message_type': 'text',
                'success': False,
                'error': str(e)
            }
            print(f"  🧪 Text Message: ❌ ({str(e)[:50]}...)")
        
        # Test template message
        try:
            template_data = {
                "template_name": "welcome_message",
                "category": "UTILITY",
                "language_code": "en",
                "components": [{"type": "body", "text": "Welcome to ATOM!"}]
            }
            
            response = requests.post(
                f"{self.base_url}/api/whatsapp/templates",
                json=template_data,
                timeout=10
            )
            
            template_result = {
                'message_type': 'template',
                'success': response.status_code < 400,
                'status_code': response.status_code,
                'response': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text[:200]
            }
            
            print(f"  🧪 Template Message: {'✅' if template_result['success'] else '❌'} ({template_result['status_code']})")
            
        except Exception as e:
            template_result = {
                'message_type': 'template',
                'success': False,
                'error': str(e)
            }
            print(f"  🧪 Template Message: ❌ ({str(e)[:50]}...)")
        
        message_summary = {
            'test_name': 'Message Capabilities',
            'total_tests': 2,
            'successful_tests': sum([text_result['success'], template_result['success']]),
            'results': {
                'text_message': text_result,
                'template_message': template_result
            },
            'timestamp': datetime.now().isoformat()
        }
        
        message_summary['success_rate'] = (message_summary['successful_tests'] / message_summary['total_tests']) * 100
        print(f"\\n📊 Message Capabilities Results: {message_summary['successful_tests']}/{message_summary['total_tests']} ({message_summary['success_rate']:.1f}%)")
        
        return message_summary
    
    def test_configuration_status(self) -> dict:
        """Test configuration and service status"""
        print("\\n🧪 Testing Configuration Status...")
        
        config_tests = []
        
        # Test service health
        try:
            response = requests.get(f"{self.base_url}/api/whatsapp/service/health", timeout=10)
            health_data = response.json()
            
            health_result = {
                'test': 'Service Health',
                'success': response.status_code < 400,
                'status': health_data.get('status', 'unknown'),
                'configuration_type': health_data.get('configuration_type', 'unknown'),
                'is_demo': health_data.get('is_demo', False),
                'uptime': health_data.get('uptime_percentage', 0)
            }
            
            config_tests.append(health_result)
            demo_status = "🎭 DEMO" if health_result['is_demo'] else "🏭 PRODUCTION"
            print(f"  🧪 Service Health: {'✅' if health_result['success'] else '❌'} ({health_result.get('status', 'unknown')} - {demo_status})")
            
        except Exception as e:
            health_result = {
                'test': 'Service Health',
                'success': False,
                'error': str(e)
            }
            config_tests.append(health_result)
            print(f"  🧪 Service Health: ❌ ({str(e)[:50]}...)")
        
        # Test configuration access
        try:
            response = requests.get(f"{self.base_url}/api/whatsapp/configuration/business-profile", timeout=10)
            config_data = response.json()
            
            config_result = {
                'test': 'Configuration Access',
                'success': response.status_code < 400,
                'has_business_profile': 'business_profile' in config_data and len(config_data['business_profile']) > 0,
                'profile_fields': list(config_data.get('business_profile', {}).keys())
            }
            
            config_tests.append(config_result)
            profile_status = "✅ Configured" if config_result['has_business_profile'] else "⚠️ Not Configured"
            print(f"  🧪 Configuration Access: {'✅' if config_result['success'] else '❌'} ({profile_status})")
            
        except Exception as e:
            config_result = {
                'test': 'Configuration Access',
                'success': False,
                'error': str(e)
            }
            config_tests.append(config_result)
            print(f"  🧪 Configuration Access: ❌ ({str(e)[:50]}...)")
        
        config_summary = {
            'test_name': 'Configuration Status',
            'total_tests': len(config_tests),
            'successful_tests': sum([test['success'] for test in config_tests]),
            'results': config_tests,
            'timestamp': datetime.now().isoformat()
        }
        
        config_summary['success_rate'] = (config_summary['successful_tests'] / config_summary['total_tests']) * 100
        print(f"\\n📊 Configuration Status Results: {config_summary['successful_tests']}/{config_summary['total_tests']} ({config_summary['success_rate']:.1f}%)")
        
        return config_summary
    
    def test_search_and_analytics(self) -> dict:
        """Test search and analytics capabilities"""
        print("\\n🧪 Testing Search and Analytics...")
        
        search_tests = []
        
        # Test conversation search
        try:
            response = requests.get(
                f"{self.base_url}/api/whatsapp/conversations/search",
                params={
                    "query": "test",
                    "limit": 10,
                    "offset": 0
                },
                timeout=10
            )
            
            search_result = {
                'test': 'Conversation Search',
                'success': response.status_code < 400,
                'status_code': response.status_code,
                'has_results': 'conversations' in response.json()
            }
            
            search_tests.append(search_result)
            print(f"  🧪 Conversation Search: {'✅' if search_result['success'] else '❌'} ({search_result['status_code']})")
            
        except Exception as e:
            search_result = {
                'test': 'Conversation Search',
                'success': False,
                'error': str(e)
            }
            search_tests.append(search_result)
            print(f"  🧪 Conversation Search: ❌ ({str(e)[:50]}...)")
        
        # Test analytics export
        try:
            response = requests.get(
                f"{self.base_url}/api/whatsapp/analytics/export",
                params={
                    "format": "json",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31"
                },
                timeout=10
            )
            
            export_result = {
                'test': 'Analytics Export',
                'success': response.status_code < 400,
                'status_code': response.status_code,
                'is_json': response.headers.get('content-type', '').startswith('application/json')
            }
            
            search_tests.append(export_result)
            print(f"  🧪 Analytics Export: {'✅' if export_result['success'] else '❌'} ({export_result['status_code']})")
            
        except Exception as e:
            export_result = {
                'test': 'Analytics Export',
                'success': False,
                'error': str(e)
            }
            search_tests.append(export_result)
            print(f"  🧪 Analytics Export: ❌ ({str(e)[:50]}...)")
        
        search_summary = {
            'test_name': 'Search and Analytics',
            'total_tests': len(search_tests),
            'successful_tests': sum([test['success'] for test in search_tests]),
            'results': search_tests,
            'timestamp': datetime.now().isoformat()
        }
        
        search_summary['success_rate'] = (search_summary['successful_tests'] / search_summary['total_tests']) * 100
        print(f"\\n📊 Search and Analytics Results: {search_summary['successful_tests']}/{search_summary['total_tests']} ({search_summary['success_rate']:.1f}%)")
        
        return search_summary
    
    def run_comprehensive_test(self) -> dict:
        """Run all tests and generate comprehensive report"""
        print("🚀 Starting WhatsApp Business Production Testing Suite")
        print("=" * 70)
        
        test_results = []
        
        # Run all test suites
        test_results.append(self.test_api_endpoints())
        test_results.append(self.test_message_capabilities())
        test_results.append(self.test_configuration_status())
        test_results.append(self.test_search_and_analytics())
        
        # Calculate overall summary
        total_tests = sum([result['total_tests'] for result in test_results])
        successful_tests = sum([result['successful_tests'] for result in test_results])
        overall_success_rate = (successful_tests / total_tests) * 100
        
        end_time = datetime.now()
        test_duration = (end_time - self.start_time).total_seconds()
        
        comprehensive_report = {
            'test_suite': 'WhatsApp Business Production Testing',
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': test_duration,
            'overall_summary': {
                'total_test_suites': len(test_results),
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'failed_tests': total_tests - successful_tests,
                'overall_success_rate': overall_success_rate,
                'status': 'PASS' if overall_success_rate >= 80 else 'FAIL'
            },
            'test_results': test_results,
            'recommendations': self._generate_recommendations(test_results),
            'production_readiness': self._assess_production_readiness(test_results, overall_success_rate)
        }
        
        # Print final summary
        print("\\n" + "=" * 70)
        print("🎉 COMPREHENSIVE TEST RESULTS")
        print("=" * 70)
        
        print(f"\\n📊 Overall Summary:")
        print(f"  🧪 Total Test Suites: {comprehensive_report['overall_summary']['total_test_suites']}")
        print(f"  📋 Total Tests: {comprehensive_report['overall_summary']['total_tests']}")
        print(f"  ✅ Successful: {comprehensive_report['overall_summary']['successful_tests']}")
        print(f"  ❌ Failed: {comprehensive_report['overall_summary']['failed_tests']}")
        print(f"  📈 Success Rate: {comprehensive_report['overall_summary']['overall_success_rate']:.1f}%")
        print(f"  ⏱️  Duration: {comprehensive_report['duration_seconds']:.1f} seconds")
        print(f"  🎯 Status: {comprehensive_report['overall_summary']['status']}")
        
        print(f"\\n🏭 Production Readiness: {comprehensive_report['production_readiness']['status']}")
        print(f"  📊 Readiness Score: {comprehensive_report['production_readiness']['score']}/100")
        print(f"  💡 Readiness Level: {comprehensive_report['production_readiness']['level']}")
        
        print(f"\\n🔧 Recommendations:")
        for i, recommendation in enumerate(comprehensive_report['recommendations'], 1):
            print(f"  {i}. {recommendation}")
        
        print(f"\\n📁 Detailed report saved to: /tmp/whatsapp_production_test_report.json")
        
        return comprehensive_report
    
    def _generate_recommendations(self, test_results) -> list:
        """Generate recommendations based on test results"""
        recommendations = []
        
        for result in test_results:
            if result['success_rate'] < 100:
                if result['test_name'] == 'API Endpoints':
                    recommendations.append("Fix failing API endpoints - check service configuration and dependencies")
                elif result['test_name'] == 'Message Capabilities':
                    recommendations.append("Resolve message sending issues - verify API credentials and permissions")
                elif result['test_name'] == 'Configuration Status':
                    recommendations.append("Complete service configuration - set up environment variables and database")
                elif result['test_name'] == 'Search and Analytics':
                    recommendations.append("Debug search and analytics - check database connectivity and data models")
        
        # Check for demo mode
        for result in test_results:
            if result['test_name'] == 'Configuration Status':
                for test in result['results']:
                    if test.get('is_demo', False):
                        recommendations.append("Set up production API credentials to exit demo mode")
                        break
        
        # Always include security recommendations
        recommendations.append("Implement webhook signature verification for production security")
        recommendations.append("Set up monitoring and alerting for production deployment")
        recommendations.append("Configure database backups for data protection")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def _assess_production_readiness(self, test_results, overall_success_rate) -> dict:
        """Assess production readiness based on test results"""
        score = overall_success_rate
        
        # Check for demo mode penalty
        is_demo = False
        for result in test_results:
            if result['test_name'] == 'Configuration Status':
                for test in result['results']:
                    if test.get('is_demo', False):
                        is_demo = True
                        score -= 20
                        break
        
        # Check critical failures
        critical_failures = 0
        for result in test_results:
            if result['success_rate'] < 50:
                critical_failures += 1
                score -= 10
        
        score = max(0, min(100, score))
        
        if score >= 90:
            level = "EXCELLENT - Ready for Production"
            status = "PRODUCTION_READY"
        elif score >= 80:
            level = "GOOD - Minor Issues to Address"
            status = "MOSTLY_READY"
        elif score >= 60:
            level = "FAIR - Significant Issues to Fix"
            status = "NEEDS_WORK"
        else:
            level = "POOR - Major Issues to Resolve"
            status = "NOT_READY"
        
        return {
            'score': int(score),
            'level': level,
            'status': status,
            'is_demo_mode': is_demo,
            'critical_failures': critical_failures
        }

def run_production_test():
    """Run production testing suite"""
    tester = WhatsAppProductionTester()
    
    try:
        report = tester.run_comprehensive_test()
        
        # Save report
        with open('/tmp/whatsapp_production_test_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return report
        
    except Exception as e:
        error_report = {
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }
        with open('/tmp/whatsapp_production_test_error.json', 'w') as f:
            json.dump(error_report, f, indent=2, default=str)
        
        return error_report

if __name__ == '__main__':
    report = run_production_test()