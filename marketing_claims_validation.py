#!/usr/bin/env python3
"""
Marketing Claims Validation for ATOM Platform

This script systematically tests and validates the marketing claims made in the README.md
against the actual system capabilities.
"""

import requests
import json
import sys
from datetime import datetime

class MarketingClaimsValidator:
    def __init__(self, base_url="http://localhost:5058"):
        self.base_url = base_url
        self.results = {}
        self.claims_validation = {}
    
    def test_backend_health(self):
        """Test if backend is operational"""
        try:
            response = requests.get(f"{self.base_url}/healthz")
            data = response.json()
            
            self.results['backend_health'] = {
                'status': data.get('status') == 'ok',
                'blueprints_loaded': data.get('total_blueprints', 0),
                'database_status': data.get('database', {}),
                'message': data.get('message', '')
            }
            return True
        except Exception as e:
            self.results['backend_health'] = {
                'status': False,
                'error': str(e)
            }
            return False
    
    def test_service_registry(self):
        """Test service registry and integration claims"""
        try:
            response = requests.get(f"{self.base_url}/api/services/status")
            data = response.json()
            
            self.results['service_registry'] = {
                'total_services': data.get('total_services', 0),
                'active_services': data.get('status_summary', {}).get('active', 0),
                'connected_services': data.get('status_summary', {}).get('connected', 0),
                'success': data.get('success', False)
            }
            return True
        except Exception as e:
            self.results['service_registry'] = {
                'status': False,
                'error': str(e)
            }
            return False
    
    def test_byok_system(self):
        """Test Bring Your Own Keys system"""
        try:
            response = requests.get(f"{self.base_url}/api/user/api-keys/providers")
            data = response.json()
            
            self.results['byok_system'] = {
                'providers_count': len(data.get('providers', {})),
                'providers': list(data.get('providers', {}).keys()),
                'success': data.get('success', False)
            }
            return True
        except Exception as e:
            self.results['byok_system'] = {
                'status': False,
                'error': str(e)
            }
            return False
    
    def test_workflow_generation(self):
        """Test natural language workflow generation"""
        test_cases = [
            "Schedule a meeting for tomorrow",
            "Send a message to Slack",
            "Create a task in Asana",
            "Search for documents about Q3 planning"
        ]
        
        results = []
        for i, user_input in enumerate(test_cases):
            try:
                response = requests.post(
                    f"{self.base_url}/api/workflow-automation/generate",
                    json={"user_input": user_input, "user_id": "test_user"}
                )
                data = response.json()
                
                results.append({
                    'test_case': user_input,
                    'success': data.get('success', False),
                    'workflow_actions': data.get('workflow', {}).get('actions', []),
                    'services_used': data.get('workflow', {}).get('services', [])
                })
            except Exception as e:
                results.append({
                    'test_case': user_input,
                    'success': False,
                    'error': str(e)
                })
        
        self.results['workflow_generation'] = {
            'test_cases': results,
            'success_rate': sum(1 for r in results if r['success']) / len(results) if results else 0
        }
        return any(r['success'] for r in results)
    
    def test_nlu_bridge(self):
        """Test Natural Language Understanding bridge"""
        try:
            response = requests.post(
                f"{self.base_url}/api/workflow-agent/analyze",
                json={"user_input": "Test natural language understanding", "user_id": "test_user"}
            )
            data = response.json()
            
            self.results['nlu_bridge'] = {
                'success': data.get('success', False),
                'response': data
            }
            return data.get('success', False)
        except Exception as e:
            self.results['nlu_bridge'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_specific_services(self):
        """Test specific service integrations"""
        services_to_test = [
            ('slack', '/api/slack/health'),
            ('notion', '/api/notion/health?user_id=test_user'),
            ('calendar', '/api/calendar/health'),
        ]
        
        service_results = {}
        for service_name, endpoint in services_to_test:
            try:
                response = requests.get(f"{self.base_url}{endpoint}")
                if response.status_code == 200:
                    data = response.json()
                    service_results[service_name] = {
                        'status': data.get('ok', False) or data.get('available', False) or data.get('status') == 'ok',
                        'details': data
                    }
                else:
                    service_results[service_name] = {
                        'status': False,
                        'error': f'HTTP {response.status_code}'
                    }
            except Exception as e:
                service_results[service_name] = {
                    'status': False,
                    'error': str(e)
                }
        
        self.results['specific_services'] = service_results
        return any(s['status'] for s in service_results.values())
    
    def validate_marketing_claims(self):
        """Validate key marketing claims against actual system capabilities"""
        
        # Claim 1: "Production Ready"
        backend_ok = self.results.get('backend_health', {}).get('status', False)
        blueprints_loaded = self.results.get('backend_health', {}).get('blueprints_loaded', 0)
        self.claims_validation['production_ready'] = {
            'claimed': True,
            'actual': backend_ok and blueprints_loaded > 100,
            'evidence': f"Backend: {backend_ok}, Blueprints: {blueprints_loaded}",
            'verdict': "PARTIALLY VALID" if backend_ok else "INVALID"
        }
        
        # Claim 2: "15+ integrated platforms"
        total_services = self.results.get('service_registry', {}).get('total_services', 0)
        self.claims_validation['integrated_platforms'] = {
            'claimed': "15+",
            'actual': total_services,
            'evidence': f"Total services registered: {total_services}",
            'verdict': "VALID" if total_services >= 15 else "INVALID"
        }
        
        # Claim 3: "Natural language workflow generation"
        workflow_success = self.results.get('workflow_generation', {}).get('success_rate', 0)
        self.claims_validation['nl_workflow_generation'] = {
            'claimed': True,
            'actual': workflow_success > 0,
            'evidence': f"Workflow generation success rate: {workflow_success:.1%}",
            'verdict': "VALID" if workflow_success > 0 else "INVALID"
        }
        
        # Claim 4: "BYOK System"
        providers_count = self.results.get('byok_system', {}).get('providers_count', 0)
        self.claims_validation['byok_system'] = {
            'claimed': True,
            'actual': providers_count > 0,
            'evidence': f"AI providers available: {providers_count}",
            'verdict': "VALID" if providers_count > 0 else "INVALID"
        }
        
        # Claim 5: "Advanced NLU System"
        nlu_success = self.results.get('nlu_bridge', {}).get('success', False)
        self.claims_validation['advanced_nlu'] = {
            'claimed': True,
            'actual': nlu_success,
            'evidence': f"NLU bridge operational: {nlu_success}",
            'verdict': "VALID" if nlu_success else "INVALID"
        }
        
        # Claim 6: "Real service integrations"
        active_services = self.results.get('service_registry', {}).get('active_services', 0)
        self.claims_validation['real_integrations'] = {
            'claimed': True,
            'actual': active_services > 0,
            'evidence': f"Active services: {active_services}",
            'verdict': "VALID" if active_services > 0 else "INVALID"
        }
        
        # Claim 7: "Voice integration"
        # This would require testing voice endpoints
        self.claims_validation['voice_integration'] = {
            'claimed': True,
            'actual': False,  # Need to test voice endpoints
            'evidence': "Voice endpoints not tested in this validation",
            'verdict': "UNVERIFIED"
        }
        
        # Claim 8: "Cross-platform coordination"
        workflow_services = []
        for test in self.results.get('workflow_generation', {}).get('test_cases', []):
            workflow_services.extend(test.get('services_used', []))
        unique_services = len(set(workflow_services))
        self.claims_validation['cross_platform_coordination'] = {
            'claimed': True,
            'actual': unique_services > 1,
            'evidence': f"Unique services in workflows: {unique_services}",
            'verdict': "VALID" if unique_services > 1 else "INVALID"
        }
    
    def run_all_tests(self):
        """Run all validation tests"""
        print("🚀 Starting Marketing Claims Validation")
        print("=" * 60)
        
        tests = [
            ("Backend Health", self.test_backend_health),
            ("Service Registry", self.test_service_registry),
            ("BYOK System", self.test_byok_system),
            ("Workflow Generation", self.test_workflow_generation),
            ("NLU Bridge", self.test_nlu_bridge),
            ("Specific Services", self.test_specific_services),
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔍 Testing: {test_name}")
            try:
                result = test_func()
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"   {status}")
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
        
        # Validate claims
        self.validate_marketing_claims()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 MARKETING CLAIMS VALIDATION SUMMARY")
        print("=" * 60)
        
        for claim, validation in self.claims_validation.items():
            claimed = validation['claimed']
            actual = validation['actual']
            verdict = validation['verdict']
            evidence = validation['evidence']
            
            if verdict == "VALID":
                icon = "✅"
            elif verdict == "PARTIALLY VALID":
                icon = "⚠️"
            elif verdict == "UNVERIFIED":
                icon = "❓"
            else:
                icon = "❌"
            
            print(f"\n{icon} {claim.upper().replace('_', ' ')}")
            print(f"   Claimed: {claimed}")
            print(f"   Actual: {actual}")
            print(f"   Evidence: {evidence}")
            print(f"   Verdict: {verdict}")
        
        # Overall assessment
        valid_claims = sum(1 for v in self.claims_validation.values() 
                          if v['verdict'] in ["VALID", "PARTIALLY VALID"])
        total_claims = len(self.claims_validation)
        
        print(f"\n📈 OVERALL ASSESSMENT: {valid_claims}/{total_claims} claims validated")
        
        if valid_claims / total_claims >= 0.7:
            print("🎯 VERDICT: Marketing claims are SUBSTANTIALLY ACCURATE")
        elif valid_claims / total_claims >= 0.5:
            print("⚠️ VERDICT: Marketing claims are PARTIALLY ACCURATE")
        else:
            print("❌ VERDICT: Marketing claims are LARGELY INACCURATE")
        
        return self.results, self.claims_validation

if __name__ == "__main__":
    validator = MarketingClaimsValidator()
    results, claims = validator.run_all_tests()
    
    # Save detailed results
    with open('marketing_validation_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'claims_validation': claims
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: marketing_validation_results.json")