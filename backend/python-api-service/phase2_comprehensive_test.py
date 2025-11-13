#!/usr/bin/env python3
"""
🧪 Phase 2 Comprehensive Testing & Demonstration
Tests all enhanced features of Phase 2 Authentication Unification
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any

class Phase2Tester:
    """Comprehensive tester for Phase 2 features"""
    
    def __init__(self, base_url: str = "http://localhost:10000"):
        self.base_url = base_url
        self.test_results = []
        self.start_time = datetime.now()
    
    def test_endpoint(self, method: str, url: str, test_name: str, expected_status: int = 200, data: Dict = None) -> Dict:
        """Test a specific endpoint"""
        try:
            full_url = f"{self.base_url}{url}"
            
            if method.upper() == 'GET':
                response = requests.get(full_url, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(full_url, json=data or {}, timeout=10)
            
            success = response.status_code == expected_status
            
            try:
                response_data = response.json()
            except:
                response_data = response.text
            
            result = {
                'test_name': test_name,
                'method': method.upper(),
                'url': url,
                'expected_status': expected_status,
                'actual_status': response.status_code,
                'success': success,
                'response_time': response.elapsed.total_seconds(),
                'response_size': len(response.content),
                'response_data': response_data if success else None,
                'error': None if success else f"Status {response.status_code}"
            }
            
            self.test_results.append(result)
            return result
            
        except Exception as e:
            result = {
                'test_name': test_name,
                'method': method.upper(),
                'url': url,
                'expected_status': expected_status,
                'actual_status': None,
                'success': False,
                'response_time': None,
                'response_size': None,
                'response_data': None,
                'error': str(e)
            }
            
            self.test_results.append(result)
            return result
    
    def test_phase1_compatibility(self):
        """Test Phase 1 basic integration compatibility"""
        print("🧪 Testing Phase 1: Basic Integration Compatibility")
        
        basic_tests = [
            ('GET', '/api/integrations/github/health', 'GitHub Basic Health'),
            ('GET', '/api/integrations/linear/health', 'Linear Basic Health'),
            ('GET', '/api/integrations/jira/health', 'Jira Basic Health'),
            ('GET', '/api/integrations/notion/health', 'Notion Basic Health'),
            ('GET', '/api/integrations/slack/health', 'Slack Basic Health'),
            ('GET', '/api/integrations/teams/health', 'Teams Basic Health'),
            ('GET', '/api/integrations/figma/health', 'Figma Basic Health'),
        ]
        
        results = []
        for method, url, test_name in basic_tests:
            result = self.test_endpoint(method, url, test_name)
            results.append(result)
            
            status = "✅" if result['success'] else "❌"
            print(f"   {status} {test_name}: {result.get('error', 'OK')}")
        
        return results
    
    def test_phase2_enhancements(self):
        """Test Phase 2 enhanced features"""
        print("\n🚀 Testing Phase 2: Enhanced Features")
        
        enhanced_tests = [
            ('GET', '/api/v2/health', 'Enhanced System Health'),
            ('GET', '/api/v2/system/status', 'Comprehensive System Status'),
            ('GET', '/api/v2/feature-tour', 'Phase 2 Feature Tour'),
            ('GET', '/api/v2/workflows/status', 'Workflow System Status'),
        ]
        
        results = []
        for method, url, test_name in enhanced_tests:
            result = self.test_endpoint(method, url, test_name)
            results.append(result)
            
            status = "✅" if result['success'] else "❌"
            print(f"   {status} {test_name}: {result.get('error', 'OK')}")
        
        return results
    
    def test_oauth_system(self):
        """Test OAuth authentication system"""
        print("\n🔐 Testing OAuth Authentication System")
        
        oauth_tests = [
            ('GET', '/api/oauth/github/authorize?user_id=test_user', 'GitHub OAuth Authorize'),
            ('GET', '/api/oauth/notion/authorize?user_id=test_user', 'Notion OAuth Authorize'),
            ('GET', '/api/oauth/slack/authorize?user_id=test_user', 'Slack OAuth Authorize'),
        ]
        
        results = []
        for method, url, test_name in oauth_tests:
            result = self.test_endpoint(method, url, test_name)
            results.append(result)
            
            status = "✅" if result['success'] else "⚠️"
            print(f"   {status} {test_name}: {'Configured' if result['success'] else 'Not Configured (Expected)'}")
        
        return results
    
    def test_workflow_system(self):
        """Test cross-integration workflow system"""
        print("\n🔄 Testing Cross-Integration Workflow System")
        
        # Get workflow templates
        result = self.test_endpoint('GET', '/api/v2/workflows/status', 'Workflow System Status')
        status = "✅" if result['success'] else "❌"
        print(f"   {status} Workflow System: {'Available' if result['success'] else 'Not Available'}")
        
        # Test demo workflow execution
        demo_data = {
            'workflow_type': 'github_linear_sync',
            'user_id': 'demo_user'
        }
        result = self.test_endpoint('POST', '/api/v2/workflows/demo/execute', 'Demo Workflow Execution', 200, demo_data)
        status = "✅" if result['success'] else "❌"
        print(f"   {status} Demo Workflow: {'Executed' if result['success'] else 'Failed'}")
        
        return [result]
    
    def test_enhanced_integrations(self):
        """Test enhanced integration endpoints"""
        print("\n🌟 Testing Enhanced Integration Endpoints")
        
        enhanced_tests = [
            ('GET', '/api/integrations/github/repositories?user_id=demo_user', 'GitHub Enhanced Repositories'),
            ('GET', '/api/integrations/notion/pages?user_id=demo_user', 'Notion Enhanced Pages'),
        ]
        
        results = []
        for method, url, test_name in enhanced_tests:
            result = self.test_endpoint(method, url, test_name)
            results.append(result)
            
            status = "✅" if result['success'] else "⚠️"
            print(f"   {status} {test_name}: {'Working' if result['success'] else 'Needs OAuth'}")
        
        return results
    
    def generate_comprehensive_report(self):
        """Generate comprehensive test report"""
        end_time = datetime.now()
        total_duration = end_time - self.start_time
        
        # Calculate statistics
        passed_tests = len([r for r in self.test_results if r['success']])
        total_tests = len(self.test_results)
        success_rate = round((passed_tests / total_tests) * 100, 1) if total_tests > 0 else 0
        
        # Calculate average response time
        response_times = [r['response_time'] for r in self.test_results if r['response_time'] is not None]
        avg_response_time = round(sum(response_times) / len(response_times), 3) if response_times else 0
        
        # Group by category
        categories = {
            'phase1_compatibility': [],
            'phase2_enhancements': [],
            'oauth_system': [],
            'workflow_system': [],
            'enhanced_integrations': []
        }
        
        for result in self.test_results:
            if any(keyword in result['test_name'].lower() for keyword in ['github basic', 'linear basic', 'jira basic', 'notion basic', 'slack basic', 'teams basic', 'figma basic']):
                categories['phase1_compatibility'].append(result)
            elif any(keyword in result['test_name'].lower() for keyword in ['enhanced system', 'comprehensive system', 'feature tour', 'workflow system']):
                categories['phase2_enhancements'].append(result)
            elif 'oauth' in result['test_name'].lower():
                categories['oauth_system'].append(result)
            elif 'workflow' in result['test_name'].lower():
                categories['workflow_system'].append(result)
            else:
                categories['enhanced_integrations'].append(result)
        
        # Generate recommendations
        recommendations = []
        
        if success_rate >= 90:
            recommendations.append("🎉 Excellent! Phase 2 implementation is highly successful")
        elif success_rate >= 75:
            recommendations.append("✅ Good! Phase 2 is working well with minor improvements needed")
        else:
            recommendations.append("⚠️  Needs attention: Several Phase 2 features require improvement")
        
        # Analyze specific categories
        for category, results in categories.items():
            if results:
                category_success = len([r for r in results if r['success']])
                category_rate = round((category_success / len(results)) * 100, 1)
                
                if category_rate < 80:
                    recommendations.append(f"🔧 {category.replace('_', ' ').title()}: {category_rate}% success rate - needs improvement")
                elif category_rate >= 95:
                    recommendations.append(f"🌟 {category.replace('_', ' ').title()}: {category_rate}% success rate - excellent!")
        
        report = {
            'test_summary': {
                'start_time': self.start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration': str(total_duration),
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': total_tests - passed_tests,
                'success_rate': success_rate,
                'average_response_time': avg_response_time,
                'status': 'excellent' if success_rate >= 90 else 'good' if success_rate >= 75 else 'needs_improvement'
            },
            'category_results': {cat: {
                'total': len(results),
                'passed': len([r for r in results if r['success']]),
                'success_rate': round((len([r for r in results if r['success']]) / len(results)) * 100, 1) if results else 0
            } for cat, results in categories.items()},
            'detailed_results': self.test_results,
            'phase_analysis': {
                'phase1_compatibility': {
                    'description': 'Phase 1 basic integration routes compatibility',
                    'status': 'maintained',
                    'success_rate': categories['phase1_compatibility'][0]['success_rate'] if categories['phase1_compatibility'] else 0
                },
                'phase2_enhancements': {
                    'description': 'Phase 2 enhanced features (OAuth, workflows, monitoring)',
                    'status': 'implemented',
                    'success_rate': categories['phase2_enhancements'][0]['success_rate'] if categories['phase2_enhancements'] else 0
                },
                'oauth_system': {
                    'description': 'Unified OAuth authentication system',
                    'status': 'configured',
                    'success_rate': categories['oauth_system'][0]['success_rate'] if categories['oauth_system'] else 0
                },
                'workflow_system': {
                    'description': 'Cross-integration workflow engine',
                    'status': 'functional',
                    'success_rate': categories['workflow_system'][0]['success_rate'] if categories['workflow_system'] else 0
                }
            },
            'recommendations': recommendations,
            'production_readiness': {
                'basic_integrations': success_rate >= 80,
                'oauth_system': len([r for r in categories['oauth_system'] if r['success']]) > 0,
                'workflow_system': len([r for r in categories['workflow_system'] if r['success']]) > 0,
                'monitoring': success_rate >= 75,
                'overall': 'ready' if success_rate >= 75 else 'needs_work'
            }
        }
        
        return report
    
    def run_comprehensive_test(self):
        """Run comprehensive Phase 2 test suite"""
        print("🚀 ATOM Phase 2: Authentication Unification - Comprehensive Testing")
        print("=" * 80)
        
        # Run all test categories
        phase1_results = self.test_phase1_compatibility()
        phase2_results = self.test_phase2_enhancements()
        oauth_results = self.test_oauth_system()
        workflow_results = self.test_workflow_system()
        enhanced_results = self.test_enhanced_integrations()
        
        # Generate comprehensive report
        report = self.generate_comprehensive_report()
        
        # Print summary
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE TEST RESULTS")
        print("=" * 80)
        print(f"🎯 Overall Success Rate: {report['test_summary']['success_rate']}%")
        print(f"📈 Tests Passed: {report['test_summary']['passed_tests']}/{report['test_summary']['total_tests']}")
        print(f"⏱️  Average Response Time: {report['test_summary']['average_response_time']}s")
        print(f"📋 Status: {report['test_summary']['status'].upper()}")
        
        print(f"\n🎯 Category Results:")
        for category, results in report['category_results'].items():
            status = "✅" if results['success_rate'] >= 80 else "⚠️" if results['success_rate'] >= 60 else "❌"
            print(f"   {status} {category.replace('_', ' ').title()}: {results['success_rate']}% ({results['passed']}/{results['total']})")
        
        print(f"\n📈 Phase Analysis:")
        for phase, analysis in report['phase_analysis'].items():
            status = "✅" if analysis['success_rate'] >= 80 else "⚠️" if analysis['success_rate'] >= 60 else "❌"
            print(f"   {status} {analysis['description']}: {analysis['success_rate']}%")
        
        print(f"\n🎭 Production Readiness:")
        readiness = report['production_readiness']
        for feature, status in readiness.items():
            if feature == 'overall':
                continue
            icon = "✅" if status else "❌"
            print(f"   {icon} {feature.replace('_', ' ').title()}: {'Ready' if status else 'Not Ready'}")
        
        overall_icon = "🚀" if readiness['overall'] == 'ready' else "⚠️"
        print(f"   {overall_icon} Overall: {'Production Ready' if readiness['overall'] == 'ready' else 'Needs Work'}")
        
        if report['recommendations']:
            print(f"\n📝 Recommendations:")
            for rec in report['recommendations']:
                print(f"   {rec}")
        
        return report

def main():
    """Main testing function"""
    tester = Phase2Tester()
    report = tester.run_comprehensive_test()
    
    # Save report
    with open('phase2_comprehensive_test_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n💾 Detailed report saved to: phase2_comprehensive_test_report.json")
    
    return report

if __name__ == "__main__":
    main()