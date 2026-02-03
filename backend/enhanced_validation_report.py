#!/usr/bin/env python3
"""
Enhanced Validation Report Generator
Shows business value ($/year), working workflows, and total platform value
Implements Implementation Plan Phase 4
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def load_business_cases() -> Dict:
    """Load integration business use cases"""
    business_cases_file = Path('backend/independent_ai_validator/data/integration_business_cases.json')
    if not business_cases_file.exists():
        print(f"Warning: {business_cases_file} not found")
        return {}
    
    with open(business_cases_file, 'r') as f:
        return json.load(f)

def load_validation_results() -> Dict:
    """Load latest AI validator results"""
    validator_report = Path('backend/independent_ai_validator/latest_validation_report.json')
    if not validator_report.exists():
        # Try alternative location
        validator_report = Path('backend/independent_ai_validator/validation_report.json')
        if not validator_report.exists():
            print(f"Warning: {validator_report} not found")
            return {}
    
    with open(validator_report, 'r') as f:
        return json.load(f)

def load_integration_health() -> Dict:
    """Load integration health check results"""
    health_report = Path('backend/integration_health_report.json')
    if not health_report.exists():
        print(f"Warning: {health_report} not found")
        return {}
    
    with open(health_report, 'r') as f:
        return json.load(f)

def calculate_business_value(business_cases: Dict, validation_results: Dict, health_results: Dict) -> Dict:
    """Calculate total business value based on working workflows"""
    
    total_value = 0
    working_workflows = []
    broken_workflows = []
    partial_workflows = []
    
    # Extract the cases from the wrapper
    cases_data = business_cases.get('integration_business_cases', business_cases)
    
    # Iterate through all business cases
    for integration, cases in cases_data.items():
        if not isinstance(cases,list):
            continue
            
        for case in cases:
            if not isinstance(case, dict):
                continue
                
            workflow_name = case.get('name', case.get('use_case_id', 'Unknown'))
            annual_value = case.get('business_value', {}).get('annual_value_usd', 0)
            workflow_integrations = case.get('workflow', [])
            
            # Check if all required integrations are healthy
            all_healthy = True
            health_status = []
            
            for required_integration in workflow_integrations:
                # Check health status
                integration_healthy = False
                if health_results:
                    for service in health_results.get('services', []):
                        if service.get('name', '').lower() == required_integration.lower():
                            integration_healthy = service.get('status') == 'READY'
                            health_status.append({
                                'integration': required_integration,
                                'status': service.get('status', 'UNKNOWN')
                            })
                            break
                
                if not integration_healthy:
                    all_healthy = False
            
            workflow_info = {
                'name': workflow_name,
                'description': case.get('description', ''),
                'annual_value': annual_value,
                'integrations': workflow_integrations,
                'health_status': health_status
            }
            
            if all_healthy:
                working_workflows.append(workflow_info)
                total_value += annual_value
            elif len(health_status) > 0 and any(h['status'] == 'READY' for h in health_status):
                partial_workflows.append(workflow_info)
            else:
                broken_workflows.append(workflow_info)
    
    return {
        'total_validated_value': total_value,
        'working_workflows': sorted(working_workflows, key=lambda x: x['annual_value'], reverse=True),
        'partial_workflows': sorted(partial_workflows, key=lambda x: x['annual_value'], reverse=True),
        'broken_workflows': sorted(broken_workflows, key=lambda x: x['annual_value'], reverse=True),
        'workflow_counts': {
            'working': len(working_workflows),
            'partial': len(partial_workflows),
            'broken': len(broken_workflows),
            'total': len(working_workflows) + len(partial_workflows) + len(broken_workflows)
        }
    }

def format_currency(amount: float) -> str:
    """Format amount as currency"""
    if amount >= 1_000_000:
        return f"${amount/1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"${amount/1_000:.0f}K"
    else:
        return f"${amount:.0f}"

def print_enhanced_report(business_value: Dict):
    """Print enhanced validation report"""
    
    print("\n" + "=" * 80)
    print("ATOM BUSINESS VALUE VALIDATION REPORT")
    print("=" * 80)
    print()
    
    # Overall Summary
    total_value = business_value['total_validated_value']
    counts = business_value['workflow_counts']
    success_rate = (counts['working'] / counts['total'] * 100) if counts['total'] > 0 else 0
    
    print(f"📊 Overall Business Value: {format_currency(total_value)}/year validated")
    print(f"✅ Workflow Success Rate: {success_rate:.1f}% ({counts['working']}/{counts['total']})")
    print()
    
    print(f"Workflow Status:")
    print(f"  ✅ Working:  {counts['working']}")
    print(f"  ⚠️  Partial:  {counts['partial']}")
    print(f"  ❌ Broken:   {counts['broken']}")
    print()
    
    # Top Working Workflows
    if business_value['working_workflows']:
        print("=" * 80)
        print("TOP WORKING WORKFLOWS")
        print("=" * 80)
        print()
        
        for i, workflow in enumerate(business_value['working_workflows'][:10], 1):
            value = format_currency(workflow['annual_value'])
            integrations = " → ".join(workflow['integrations'])
            print(f"{i}. {workflow['name']}")
            print(f"   💰 Value: {value}/year")
            print(f"   🔗 Workflow: {integrations}")
            print(f"   📝 {workflow['description']}")
            print()
    
    # Partial Workflows (need attention)
    if business_value['partial_workflows']:
        print("=" * 80)
        print("PARTIAL WORKFLOWS (Needs Configuration)")
        print("=" * 80)
        print()
        
        for i, workflow in enumerate(business_value['partial_workflows'][:5], 1):
            value = format_currency(workflow['annual_value'])
            integrations = " → ".join(workflow['integrations'])
            
            # Show which integrations are working/broken
            status_str = []
            for h in workflow['health_status']:
                status_icon = "✅" if h['status'] == 'READY' else "❌"
                status_str.append(f"{status_icon} {h['integration']}")
            
            print(f"{i}. {workflow['name']}")
            print(f"   💰 Potential Value: {value}/year")
            print(f"   🔗 Workflow: {integrations}")
            print(f"   📊 Status: {', '.join(status_str)}")
            print()
    
    # Broken Workflows (high value opportunities)
    if business_value['broken_workflows']:
        print("=" * 80)
        print("BROKEN WORKFLOWS (High-Value Opportunities)")
        print("=" * 80)
        print()
        
        for i, workflow in enumerate(business_value['broken_workflows'][:5], 1):
            value = format_currency(workflow['annual_value'])
            integrations = " → ".join(workflow['integrations'])
            print(f"{i}. {workflow['name']}")
            print(f"   💰 Potential Value: {value}/year")
            print(f"   🔗 Workflow: {integrations}")
            print(f"   ❌ Status: Integrations not configured")
            print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"✅ Validated Business Value: {format_currency(total_value)}/year")
    
    potential_value = sum(w['annual_value'] for w in business_value['partial_workflows'])
    if potential_value > 0:
        print(f"⚠️  Partial Value (needs config): {format_currency(potential_value)}/year")
    
    lost_value = sum(w['annual_value'] for w in business_value['broken_workflows'])
    if lost_value > 0:
        print(f"❌ Unrealized Value: {format_currency(lost_value)}/year")
    
    total_potential = total_value + potential_value + lost_value
    print(f"📊 Total Platform Potential: {format_currency(total_potential)}/year")
    print()
    
    print(f"Next Steps:")
    if business_value['partial_workflows']:
        print(f"  1. Configure {counts['partial']} partial workflows → +{format_currency(potential_value)}/year")
    if business_value['broken_workflows']:
        print(f"  2. Set up {counts['broken']} broken workflows → +{format_currency(lost_value)}/year")
    print()

def save_enhanced_report(business_value: Dict):
    """Save enhanced report to JSON"""
    report = {
        'generated_at': datetime.now().isoformat(),
        'total_validated_value_usd': business_value['total_validated_value'],
        'workflow_counts': business_value['workflow_counts'],
        'working_workflows': business_value['working_workflows'],
        'partial_workflows': business_value['partial_workflows'],
        'broken_workflows': business_value['broken_workflows']
    }
    
    output_file = Path('backend/enhanced_validation_report.json')
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"📄 Enhanced report saved to: {output_file}")

def main():
    print("Loading data...")
    business_cases = load_business_cases()
    validation_results = load_validation_results()
    health_results = load_integration_health()
    
    if not business_cases:
        print("ERROR: Cannot generate report without business cases")
        print("Please ensure e2e-tests/integration_business_cases.json exists")
        return
    
    print("Calculating business value...")
    business_value = calculate_business_value(business_cases, validation_results, health_results)
    
    print_enhanced_report(business_value)
    save_enhanced_report(business_value)

if __name__ == '__main__':
    main()
