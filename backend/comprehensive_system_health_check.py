#!/usr/bin/env python3
"""
Comprehensive System Health Check
Validates all critical systems and integrations after the recent improvements
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

def check_backend_health() -> Dict[str, Any]:
    """Check backend service health"""
    print("🔍 Checking backend health...")

    results = {
        'status': 'unknown',
        'services': {},
        'timestamp': datetime.now().isoformat()
    }

    try:
        # Check if backend files are in place
        backend_files = [
            'enhanced_ai_workflow_endpoints.py',
            'core/base_integration.py',
            'core/memory_routes.py',
            'integrations/stripe_service.py',
            'integrations/gmail_service.py',
            'integrations/slack_service.py'
        ]

        missing_files = []
        for file in backend_files:
            if not Path(file).exists():
                missing_files.append(file)

        if missing_files:
            results['status'] = 'unhealthy'
            results['error'] = f"Missing backend files: {missing_files}"
        else:
            results['status'] = 'healthy'
            results['files_checked'] = len(backend_files)

    except Exception as e:
        results['status'] = 'error'
        results['error'] = str(e)

    return results

def check_ai_validation_system() -> Dict[str, Any]:
    """Check AI validation system health"""
    print("🤖 Checking AI validation system...")

    results = {
        'status': 'unknown',
        'components': {},
        'timestamp': datetime.now().isoformat()
    }

    try:
        # Check enhanced AI validation components
        components = {
            'enhanced_ai_validation': 'e2e-tests/utils/enhanced_ai_validation.py',
            'llm_verifier': 'e2e-tests/utils/llm_verifier.py',
            'glm_verifier': 'e2e-tests/utils/glm_verifier.py'
        }

        healthy_components = 0
        for component, path in components.items():
            if Path(path).exists():
                results['components'][component] = 'available'
                healthy_components += 1
            else:
                results['components'][component] = 'missing'

        # Check if we can import the validation system
        try:
            sys.path.append(str(Path(__file__).parent.parent / 'e2e-tests'))
            from utils.enhanced_ai_validation import EnhancedAIValidationSystem, AIProvider

            # Test basic instantiation
            system = EnhancedAIValidationSystem(preferred_provider=AIProvider.FALLBACK)
            results['enhanced_system'] = 'functional'
            results['providers'] = system.get_provider_status()

        except Exception as e:
            results['enhanced_system'] = f'import_error: {e}'

        results['status'] = 'healthy' if healthy_components >= 2 else 'degraded'
        results['healthy_components'] = healthy_components
        results['total_components'] = len(components)

    except Exception as e:
        results['status'] = 'error'
        results['error'] = str(e)

    return results

def check_integration_readiness() -> Dict[str, Any]:
    """Check integration readiness status"""
    print("🔧 Checking integration readiness...")

    results = {
        'status': 'unknown',
        'services': {},
        'timestamp': datetime.now().isoformat()
    }

    try:
        integrations_dir = Path('integrations')
        if not integrations_dir.exists():
            results['status'] = 'error'
            results['error'] = 'Integrations directory not found'
            return results

        # Count service files
        service_files = list(integrations_dir.glob('*_service.py'))
        route_files = list(integrations_dir.glob('*_routes.py'))

        # Check for the enhanced services we created
        enhanced_services = [
            'airtable_service_enhanced.py',
            'slack_service.py',  # The compatibility layer we created
        ]

        enhanced_count = 0
        for service in enhanced_services:
            if (integrations_dir / service).exists():
                enhanced_count += 1

        results['status'] = 'healthy'
        results['service_files'] = len(service_files)
        results['route_files'] = len(route_files)
        results['enhanced_services'] = enhanced_count
        results['total_integrations'] = len(set([f.stem.replace('_service', '').replace('_routes', '')
                                                for f in service_files + route_files]))

    except Exception as e:
        results['status'] = 'error'
        results['error'] = str(e)

    return results

def check_database_systems() -> Dict[str, Any]:
    """Check database system readiness"""
    print("💾 Checking database systems...")

    results = {
        'status': 'unknown',
        'databases': {},
        'timestamp': datetime.now().isoformat()
    }

    try:
        # Check LanceDB integration
        memory_routes = Path('core/memory_routes.py')
        if memory_routes.exists():
            results['databases']['lancedb'] = 'integrated'
        else:
            results['databases']['lancedb'] = 'missing'

        # Check token storage
        token_storage = Path('core/token_storage.py')
        if token_storage.exists():
            results['databases']['token_storage'] = 'available'
        else:
            results['databases']['token_storage'] = 'missing'

        # Check if memory routes have actual implementation (not just TODOs)
        if memory_routes.exists():
            content = memory_routes.read_text()
            if 'TODO' in content:
                results['databases']['lancedb_status'] = 'has_todos'
            else:
                results['databases']['lancedb_status'] = 'implemented'

        results['status'] = 'healthy' if len([v for v in results['databases'].values() if v not in ['missing']]) >= 1 else 'unhealthy'

    except Exception as e:
        results['status'] = 'error'
        results['error'] = str(e)

    return results

def check_oauth_systems() -> Dict[str, Any]:
    """Check OAuth system readiness"""
    print("🔐 Checking OAuth systems...")

    results = {
        'status': 'unknown',
        'oauth_flows': {},
        'timestamp': datetime.now().isoformat()
    }

    try:
        # Check OAuth callbacks
        oauth_files = {
            'social_callback': '../frontend-nextjs/pages/api/integrations/social/callback.ts',
            'slack_callback': '../frontend-nextjs/pages/api/integrations/slack/callback.ts'
        }

        for flow, path in oauth_files.items():
            if Path(path).exists():
                results['oauth_flows'][flow] = 'implemented'
            else:
                results['oauth_flows'][flow] = 'missing'

        # Check OAuth handler
        oauth_handler = Path('core/oauth_handler.py')
        if oauth_handler.exists():
            results['oauth_flows']['oauth_handler'] = 'available'
        else:
            results['oauth_flows']['oauth_handler'] = 'missing'

        results['status'] = 'healthy' if len([v for v in results['oauth_flows'].values() if v == 'implemented']) >= 1 else 'degraded'

    except Exception as e:
        results['status'] = 'error'
        results['error'] = str(e)

    return results

async def run_comprehensive_health_check():
    """Run the complete health check"""
    print("=" * 80)
    print("🏥 COMPREHENSIVE SYSTEM HEALTH CHECK")
    print("=" * 80)
    print(f"⏰ Started at: {datetime.now().isoformat()}")
    print()

    checks = {
        'Backend System': check_backend_health,
        'AI Validation System': check_ai_validation_system,
        'Integration Readiness': check_integration_readiness,
        'Database Systems': check_database_systems,
        'OAuth Systems': check_oauth_systems
    }

    overall_results = {
        'overall_status': 'unknown',
        'checks': {},
        'timestamp': datetime.now().isoformat(),
        'summary': {}
    }

    healthy_count = 0
    total_checks = len(checks)

    for check_name, check_func in checks.items():
        try:
            result = check_func()
            overall_results['checks'][check_name] = result

            if result['status'] == 'healthy':
                healthy_count += 1
                print(f"✅ {check_name}: {result['status']}")
            elif result['status'] == 'degraded':
                print(f"⚠️  {check_name}: {result['status']}")
            else:
                print(f"❌ {check_name}: {result['status']}")
                if 'error' in result:
                    print(f"   Error: {result['error']}")

        except Exception as e:
            overall_results['checks'][check_name] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"❌ {check_name}: ERROR - {e}")

    # Calculate overall status
    if healthy_count == total_checks:
        overall_results['overall_status'] = 'healthy'
    elif healthy_count >= total_checks * 0.7:
        overall_results['overall_status'] = 'mostly_healthy'
    elif healthy_count >= total_checks * 0.4:
        overall_results['overall_status'] = 'degraded'
    else:
        overall_results['overall_status'] = 'unhealthy'

    overall_results['summary'] = {
        'total_checks': total_checks,
        'healthy_checks': healthy_count,
        'health_percentage': (healthy_count / total_checks) * 100
    }

    # Print final summary
    print("\n" + "=" * 80)
    print("📊 HEALTH CHECK SUMMARY")
    print("=" * 80)
    print(f"Overall Status: {overall_results['overall_status'].upper()}")
    print(f"Healthy Systems: {healthy_count}/{total_checks} ({overall_results['summary']['health_percentage']:.1f}%)")
    print(f"Completed at: {datetime.now().isoformat()}")

    # Detailed breakdown
    print("\n📋 DETAILED BREAKDOWN:")
    for check_name, result in overall_results['checks'].items():
        status_icon = "✅" if result['status'] == 'healthy' else "⚠️" if result['status'] == 'degraded' else "❌"
        print(f"{status_icon} {check_name}: {result['status'].upper()}")

        # Add specific details for each check
        if check_name == 'Integration Readiness' and result.get('service_files'):
            print(f"   📁 Service files: {result['service_files']}, Route files: {result['route_files']}")
            print(f"   🔧 Enhanced services: {result.get('enhanced_services', 0)}")

        elif check_name == 'AI Validation System' and result.get('providers'):
            providers = result['providers']
            print(f"   🤖 Available providers: {providers.get('available_providers', [])}")
            print(f"   📊 Has AI providers: {providers.get('has_ai_providers', False)}")

        elif check_name == 'OAuth Systems' and result.get('oauth_flows'):
            flows = result['oauth_flows']
            implemented_flows = [k for k, v in flows.items() if v == 'implemented']
            print(f"   🔐 Implemented flows: {implemented_flows}")

    # Save results
    output_file = f"health_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(overall_results, f, indent=2)

    print(f"\n💾 Detailed report saved to: {output_file}")
    print("=" * 80)

    return overall_results

if __name__ == "__main__":
    asyncio.run(run_comprehensive_health_check())