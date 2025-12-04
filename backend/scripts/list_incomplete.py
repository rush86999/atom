import json

try:
    with open('backend/integration_health_report.json', 'r') as f:
        data = json.load(f)
    
    incomplete = []
    for service_name, details in data.get('detailed_results', {}).items():
        if details.get('status') == 'INCOMPLETE':
            incomplete.append(service_name)
    
    print(f"Found {len(incomplete)} INCOMPLETE services:")
    for service in sorted(incomplete):
        print(f"- {service}")
        
except Exception as e:
    print(f"Error: {e}")
