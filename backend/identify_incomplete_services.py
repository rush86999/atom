#!/usr/bin/env python3
"""
Identify and analyze incomplete services for improvement
Focuses on the 14 most critical services that need enhancement
"""

import os
import sys
import ast
from pathlib import Path
from typing import Dict, List, Any, Set
import json
from datetime import datetime

def analyze_service_file(file_path: str) -> Dict[str, Any]:
    """Analyze a service file for completeness indicators"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse AST for more detailed analysis
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return {
                'file': file_path,
                'error': f"Syntax error: {e}",
                'status': 'unparseable'
            }

        analysis = {
            'file': file_path,
            'name': Path(file_path).stem.replace('_service', '').title(),
            'size': len(content),
            'lines': len(content.splitlines()),
            'has_init': False,
            'methods': [],
            'async_methods': [],
            'error_handling': False,
            'docstrings': False,
            'has_config': False,
            'has_auth': False,
            'has_health_check': False,
            'completeness_score': 0
        }

        # Check for class definition
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        if classes:
            analysis['class_count'] = len(classes)

        # Check for methods
        functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        for func in functions:
            method_name = func.name
            analysis['methods'].append(method_name)

            if method_name.startswith('async_'):
                analysis['async_methods'].append(method_name)

            if 'health' in method_name or 'test' in method_name:
                analysis['has_health_check'] = True

        # Check for initialization
        analysis['has_init'] = any('__init__' in method for method in analysis['methods'])

        # Check for docstrings
        if '"""' in content or "'''" in content:
            analysis['docstrings'] = True

        # Check for error handling patterns
        error_patterns = ['try:', 'except', 'raise HTTPException', 'HTTPException']
        if any(pattern in content for pattern in error_patterns):
            analysis['error_handling'] = True

        # Check for configuration
        config_patterns = ['client_id', 'api_key', 'oauth', 'token']
        if any(pattern in content.lower() for pattern in config_patterns):
            analysis['has_config'] = True

        # Check for authentication
        auth_patterns = ['authorization', 'bearer', 'oauth', 'token']
        if any(pattern in content.lower() for pattern in auth_patterns):
            analysis['has_auth'] = True

        # Calculate completeness score
        score = 0
        if analysis['has_init']: score += 15
        if analysis['docstrings']: score += 10
        if analysis['error_handling']: score += 15
        if analysis['has_config']: score += 10
        if analysis['has_auth']: score += 10
        if analysis['has_health_check']: score += 15
        if len(analysis['methods']) > 0: score += 10
        if len(analysis['async_methods']) > 0: score += 10
        if analysis['lines'] > 50: score += 5
        if analysis['class_count'] > 0: score += 5

        analysis['completeness_score'] = min(100, score)

        return analysis

    except Exception as e:
        return {
            'file': file_path,
            'error': str(e),
            'status': 'error'
        }

def identify_incomplete_services():
    """Identify the 14 most incomplete services"""
    print("🔍 Identifying incomplete services for improvement...")

    integrations_dir = Path('integrations')
    if not integrations_dir.exists():
        print("❌ Integrations directory not found")
        return []

    service_files = list(integrations_dir.glob('*_service.py'))

    analyses = []
    for file_path in service_files:
        analysis = analyze_service_file(str(file_path))
        if 'error' not in analysis and analysis.get('status') != 'unparseable':
            analyses.append(analysis)

    # Sort by completeness score (lowest first)
    analyses.sort(key=lambda x: x['completeness_score'])

    # Get the 14 most incomplete services
    incomplete_services = analyses[:14]

    return incomplete_services

def generate_improvement_plan(service: Dict[str, Any]) -> Dict[str, Any]:
    """Generate improvement plan for a specific service"""
    improvements = []

    if not service['has_init']:
        improvements.append("Add proper __init__ method with configuration")

    if not service['docstrings']:
        improvements.append("Add comprehensive docstrings for classes and methods")

    if not service['error_handling']:
        improvements.append("Implement proper error handling with try/except blocks")

    if not service['has_config']:
        improvements.append("Add configuration management for API keys and settings")

    if not service['has_auth']:
        improvements.append("Implement authentication and authorization")

    if not service['has_health_check']:
        improvements.append("Add health check method for monitoring")

    if len(service['methods']) == 0:
        improvements.append("Add core API methods for integration functionality")

    if len(service['async_methods']) == 0:
        improvements.append("Convert methods to async for better performance")

    if service['lines'] < 100:
        improvements.append("Expand service with more comprehensive functionality")

    return {
        'service': service['name'],
        'file': service['file'],
        'current_score': service['completeness_score'],
        'improvements': improvements,
        'priority': 'high' if service['completeness_score'] < 50 else 'medium'
    }

async def enhance_service_example(service_name: str):
    """Create an enhanced example for a service"""
    print(f"🔧 Creating enhanced example for {service_name}...")

    # This would create an enhanced version of the service
    # For now, return placeholder
    return {
        'service': service_name,
        'enhanced': False,
        'message': 'Enhancement example placeholder'
    }

def generate_implementation_plan(incomplete_services: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a comprehensive implementation plan"""

    # Group services by priority
    high_priority = [s for s in incomplete_services if s.get('completeness_score', 0) < 50]
    medium_priority = [s for s in incomplete_services if 50 <= s.get('completeness_score', 0) < 75]
    low_priority = [s for s in incomplete_services if s.get('completeness_score', 0) >= 75]

    # Common improvement patterns
    common_improvements = {
        'error_handling': len([s for s in incomplete_services if not s['error_handling']]),
        'async_methods': len([s for s in incomplete_services if len(s['async_methods']) == 0]),
        'health_check': len([s for s in incomplete_services if not s['has_health_check']]),
        'documentation': len([s for s in incomplete_services if not s['docstrings']]),
        'configuration': len([s for s in incomplete_services if not s['has_config']]),
        'authentication': len([s for s in incomplete_services if not s['has_auth']])
    }

    plan = {
        'summary': {
            'total_services': len(incomplete_services),
            'high_priority': len(high_priority),
            'medium_priority': len(medium_priority),
            'low_priority': len(low_priority),
            'average_score': sum(s['completeness_score'] for s in incomplete_services) / len(incomplete_services) if incomplete_services else 0
        },
        'common_improvements': common_improvements,
        'implementation_phases': {
            'phase_1': high_priority[:5],  # First 5 highest priority
            'phase_2': high_priority[5:] + medium_priority[:4],  # Next 9
            'phase_3': medium_priority[4:] + low_priority  # Remaining
        },
        'improvement_plans': []
    }

    # Generate improvement plans for each service
    for service in incomplete_services:
        plan['improvement_plans'].append(generate_improvement_plan(service))

    return plan

async def run_incomplete_services_analysis():
    """Run the complete analysis of incomplete services"""
    print("=" * 80)
    print("🔧 INCOMPLETE SERVICES ANALYSIS")
    print("=" * 80)
    print(f"⏰ Analysis started at: {datetime.now().isoformat()}")
    print()

    # Identify incomplete services
    incomplete_services = identify_incomplete_services()

    print(f"📊 Found {len(incomplete_services)} services needing improvement")
    print(f"🎯 Target: Improve the top 14 incomplete services")
    print()

    # Show top 10 most incomplete services
    print("🔍 TOP 10 MOST INCOMPLETE SERVICES:")
    print("-" * 50)

    for i, service in enumerate(incomplete_services[:10], 1):
        score = service['completeness_score']
        name = service['name']
        methods = len(service['methods'])
        lines = service['lines']

        status = "🔴" if score < 50 else "🟡" if score < 75 else "🟢"
        print(f"{i:2d}. {status} {name:20s} (Score: {score:3d}, Methods: {methods:2d}, Lines: {lines:4d})")

    # Generate implementation plan
    print("\n📋 IMPLEMENTATION PLAN:")
    print("-" * 50)

    plan = generate_implementation_plan(incomplete_services)

    summary = plan['summary']
    print(f"📊 Summary: {len(high_priority)} High Priority, {len(medium_priority)} Medium Priority, {len(low_priority)} Low Priority")
    print(f"📈 Average Completeness Score: {summary['average_score']:.1f}/100")
    print()

    # Show common improvement patterns
    common = plan['common_improvements']
    print("🔄 COMMON IMPROVEMENT OPPORTUNITIES:")
    print(f"   Error Handling: {common['error_handling']} services")
    print(f"   Async Methods: {common['async_methods']} services")
    print(f"   Health Checks: {common['health_check']} services")
    print(f"   Documentation: {common['documentation']} services")
    print(f"   Configuration: {common['configuration']} services")
    print(f"   Authentication: {common['authentication']} services")
    print()

    # Show implementation phases
    phases = plan['implementation_phases']
    print("📅 IMPLEMENTATION PHASES:")
    print(f"   Phase 1 (High Priority): {len(phases['phase_1'])} services")
    print(f"   Phase 2 (Medium Priority): {len(phases['phase_2'])} services")
    print(f"   Phase 3 (Low Priority): {len(phases['phase_3'])} services")
    print()

    # Show detailed improvement plans for top 5 services
    print("🎯 TOP 5 IMPROVEMENT PLANS:")
    print("-" * 50)

    for i, improvement_plan in enumerate(plan['improvement_plans'][:5], 1):
        service = improvement_plan['service']
        score = improvement_plan['current_score']
        priority = improvement_plan['priority']
        improvements = improvement_plan['improvements']

        print(f"{i}. {service} (Score: {score}, Priority: {priority.upper()})")
        for j, improvement in enumerate(improvements[:3], 1):
            print(f"   {j}. {improvement}")
        if len(improvements) > 3:
            print(f"   + {len(improvements) - 3} more improvements...")
        print()

    # Create enhancement recommendations
    recommendations = {
        'immediate_actions': [
            'Add error handling to all services',
            'Implement health check methods',
            'Convert synchronous methods to async',
            'Add comprehensive documentation',
            'Standardize configuration patterns'
        ],
        'medium_term_goals': [
            'Create base classes for common patterns',
            'Implement unified authentication flows',
            'Add comprehensive testing',
            'Create service templates'
        ],
        'long_term_objectives': [
            'Automate service generation',
            'Implement service health monitoring',
            'Create dynamic service discovery',
            'Add service auto-scaling'
        ]
    }

    print("💡 RECOMMENDATIONS:")
    print("-" * 50)

    print("🚀 Immediate Actions:")
    for i, action in enumerate(recommendations['immediate_actions'], 1):
        print(f"   {i}. {action}")

    print("\n📈 Medium-Term Goals:")
    for i, goal in enumerate(recommendations['medium_term_goals'], 1):
        print(f"   {i}. {goal}")

    print("\n🎯 Long-Term Objectives:")
    for i, objective in enumerate(recommendations['long_term_objectives'], 1):
        print(f"   {i}. {objective}")

    # Save detailed analysis
    output_file = f"incomplete_services_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    analysis_data = {
        'timestamp': datetime.now().isoformat(),
        'incomplete_services': incomplete_services,
        'implementation_plan': plan,
        'recommendations': recommendations,
        'summary': {
            'total_analyzed': len(incomplete_services),
            'average_score': summary['average_score'],
            'high_priority_count': len(high_priority),
            'common_improvements': common_improvements
        }
    }

    with open(output_file, 'w') as f:
        json.dump(analysis_data, f, indent=2)

    print(f"\n💾 Detailed analysis saved to: {output_file}")
    print("=" * 80)
    print("✅ Incomplete services analysis complete!")
    print("=" * 80)

    return analysis_data

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_incomplete_services_analysis())