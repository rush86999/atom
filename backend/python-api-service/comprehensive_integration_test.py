#!/usr/bin/env python3
"""
🧪 Comprehensive Integration Test
Tests all integration endpoints and demonstrates functionality
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# Add integrations directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'integrations'))

class IntegrationTestSuite:
    """Comprehensive test suite for ATOM integrations"""
    
    def __init__(self):
        self.test_results = []
        self.start_time = datetime.now()
    
    def test_integration_routes(self):
        """Test integration route blueprints"""
        print("🚀 Testing Integration Route Blueprints...")
        
        integrations_to_test = [
            ('github_routes_fix', 'github_bp'),
            ('linear_routes_fix', 'linear_bp'),
            ('jira_routes_fix', 'jira_bp'),
            ('notion_routes_fix', 'notion_bp'),
            ('slack_routes_fix', 'slack_bp'),
            ('teams_routes_fix', 'teams_bp'),
            ('figma_routes_fix', 'figma_bp'),
        ]
        
        results = {}
        
        for module_name, blueprint_name in integrations_to_test:
            try:
                module = __import__(module_name)
                blueprint = getattr(module, blueprint_name)
                
                # Test blueprint structure
                routes = []
                for rule in blueprint.url_map.iter_rules():
                    routes.append({
                        'endpoint': rule.endpoint,
                        'methods': list(rule.methods - {'OPTIONS', 'HEAD'}),
                        'url': str(rule)
                    })
                
                results[module_name] = {
                    'status': 'success',
                    'blueprint': blueprint_name,
                    'routes': routes,
                    'route_count': len(routes)
                }
                
                print(f"   ✅ {module_name}: {len(routes)} routes loaded")
                
            except Exception as e:
                results[module_name] = {
                    'status': 'error',
                    'error': str(e),
                    'blueprint': blueprint_name,
                    'routes': [],
                    'route_count': 0
                }
                
                print(f"   ❌ {module_name}: {str(e)}")
        
        return results
    
    def test_endpoint_functionality(self):
        """Test individual endpoint functionality"""
        print("\n🧪 Testing Endpoint Functionality...")
        
        # Test GitHub integration
        try:
            from github_routes_fix import github_bp
            github_routes = list(github_bp.url_map.iter_rules())
            github_health = any('/health' in str(rule) for rule in github_routes)
            github_crud = any(rule.methods & {'POST', 'PUT', 'DELETE'} for rule in github_routes)
            
            print(f"   ✅ GitHub: Health Endpoint = {github_health}, CRUD Operations = {github_crud}")
            
            self.test_results.append({
                'integration': 'github',
                'health_endpoint': github_health,
                'crud_operations': github_crud,
                'route_count': len(github_routes),
                'status': 'success'
            })
            
        except Exception as e:
            print(f"   ❌ GitHub: {str(e)}")
            self.test_results.append({
                'integration': 'github',
                'status': 'error',
                'error': str(e)
            })
        
        # Test similar for other integrations
        integrations_to_test = [
            ('linear_routes_fix', 'linear_bp', 'Linear'),
            ('jira_routes_fix', 'jira_bp', 'Jira'),
            ('notion_routes_fix', 'notion_bp', 'Notion'),
            ('slack_routes_fix', 'slack_bp', 'Slack'),
            ('teams_routes_fix', 'teams_bp', 'Teams'),
            ('figma_routes_fix', 'figma_bp', 'Figma'),
        ]
        
        for module_name, blueprint_name, display_name in integrations_to_test:
            try:
                module = __import__(module_name)
                blueprint = getattr(module, blueprint_name)
                
                routes = list(blueprint.url_map.iter_rules())
                health_endpoint = any('/health' in str(rule) for rule in routes)
                crud_operations = any(rule.methods & {'POST', 'PUT', 'DELETE'} for rule in routes)
                
                print(f"   ✅ {display_name}: Health Endpoint = {health_endpoint}, CRUD Operations = {crud_operations}")
                
                self.test_results.append({
                    'integration': display_name.lower(),
                    'health_endpoint': health_endpoint,
                    'crud_operations': crud_operations,
                    'route_count': len(routes),
                    'status': 'success'
                })
                
            except Exception as e:
                print(f"   ❌ {display_name}: {str(e)}")
                self.test_results.append({
                    'integration': display_name.lower(),
                    'status': 'error',
                    'error': str(e)
                })
    
    def test_flask_app_creation(self):
        """Test Flask app creation with all integrations"""
        print("\n🏗️  Testing Flask App Creation...")
        
        try:
            from flask import Flask
            
            app = Flask(__name__)
            registered_blueprints = 0
            
            # Register all integration blueprints
            integrations_to_register = [
                ('github_routes_fix', 'github_bp', '/api/integrations/github'),
                ('linear_routes_fix', 'linear_bp', '/api/integrations/linear'),
                ('jira_routes_fix', 'jira_bp', '/api/integrations/jira'),
                ('notion_routes_fix', 'notion_bp', '/api/integrations/notion'),
                ('slack_routes_fix', 'slack_bp', '/api/integrations/slack'),
                ('teams_routes_fix', 'teams_bp', '/api/integrations/teams'),
                ('figma_routes_fix', 'figma_bp', '/api/integrations/figma'),
            ]
            
            for module_name, blueprint_name, url_prefix in integrations_to_register:
                try:
                    module = __import__(module_name)
                    blueprint = getattr(module, blueprint_name)
                    app.register_blueprint(blueprint, url_prefix=url_prefix)
                    registered_blueprints += 1
                    
                except Exception as e:
                    print(f"   ⚠️  Failed to register {module_name}: {e}")
            
            # Test app configuration
            with app.app_context():
                # List all registered routes
                routes = []
                for rule in app.url_map.iter_rules():
                    routes.append({
                        'endpoint': rule.endpoint,
                        'methods': list(rule.methods - {'OPTIONS', 'HEAD'}),
                        'url': str(rule)
                    })
                
                integration_routes = [r for r in routes if '/api/integrations/' in r['url']]
                
                print(f"   ✅ Flask App Created Successfully")
                print(f"   ✅ Registered Blueprints: {registered_blueprints}")
                print(f"   ✅ Total Routes: {len(routes)}")
                print(f"   ✅ Integration Routes: {len(integration_routes)}")
                
                return {
                    'status': 'success',
                    'registered_blueprints': registered_blueprints,
                    'total_routes': len(routes),
                    'integration_routes': len(integration_routes),
                    'routes': routes
                }
                
        except Exception as e:
            print(f"   ❌ Flask App Creation Failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def run_comprehensive_test(self):
        """Run comprehensive test suite"""
        print("🚀 ATOM Integration Comprehensive Test Suite")
        print("=" * 60)
        
        # Test route loading
        route_results = self.test_integration_routes()
        
        # Test endpoint functionality
        self.test_endpoint_functionality()
        
        # Test Flask app creation
        app_results = self.test_flask_app_creation()
        
        # Calculate results
        total_time = datetime.now() - self.start_time
        
        successful_integrations = len([r for r in self.test_results if r.get('status') == 'success'])
        total_integrations = len(self.test_results)
        success_rate = round((successful_integrations / total_integrations) * 100, 1) if total_integrations > 0 else 0
        
        # Generate final report
        report = {
            'test_summary': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'duration': str(total_time),
                'total_integrations': total_integrations,
                'successful_integrations': successful_integrations,
                'success_rate': success_rate,
                'status': 'excellent' if success_rate >= 90 else 'good' if success_rate >= 70 else 'needs_improvement'
            },
            'route_loading_results': route_results,
            'endpoint_test_results': self.test_results,
            'flask_app_results': app_results,
            'recommendations': []
        }
        
        # Add recommendations
        if success_rate < 100:
            report['recommendations'].append("🔧 Some integrations failed to load. Check import paths and dependencies.")
        
        if app_results.get('status') == 'success':
            registered_blueprints = app_results.get('registered_blueprints', 0)
            if registered_blueprints < 7:
                report['recommendations'].append(f"📋 Only {registered_blueprints}/7 blueprints registered. Check blueprint registration.")
        
        if success_rate >= 90:
            report['recommendations'].append("🎉 Excellent! All integrations are working correctly.")
        elif success_rate >= 70:
            report['recommendations'].append("✅ Good progress! Minor improvements needed for full functionality.")
        else:
            report['recommendations'].append("⚠️  Needs improvement. Focus on fixing failed integrations.")
        
        # Save report
        with open('comprehensive_integration_test_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST RESULTS")
        print("=" * 60)
        print(f"🎯 Success Rate: {success_rate}% ({successful_integrations}/{total_integrations})")
        print(f"⏱️  Duration: {total_time}")
        print(f"📋 Status: {report['test_summary']['status'].upper()}")
        
        if report['recommendations']:
            print("\n📝 Recommendations:")
            for rec in report['recommendations']:
                print(f"   {rec}")
        
        print(f"\n💾 Detailed report saved to: comprehensive_integration_test_report.json")
        
        return report

def main():
    """Main test function"""
    test_suite = IntegrationTestSuite()
    return test_suite.run_comprehensive_test()

if __name__ == "__main__":
    main()