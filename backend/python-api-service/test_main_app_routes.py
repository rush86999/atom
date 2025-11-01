#!/usr/bin/env python3
"""
Test the main app to see what routes are actually registered
"""
import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_main_app_routes():
    """Test the main app routes"""
    try:
        print("Testing main app routes...")
        
        # Import and create the main app
        from main_api_app import create_app
        
        print("\n1. Creating Flask app...")
        app = create_app()
        print("   ✓ Flask app created")
        
        print("\n2. Checking registered routes...")
        service_routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                if 'service' in rule.endpoint.lower() or 'service' in str(rule).lower():
                    service_routes.append({
                        'endpoint': rule.endpoint,
                        'path': str(rule),
                        'methods': list(rule.methods)
                    })
        
        print(f"   Found {len(service_routes)} service-related routes:")
        for route in service_routes:
            print(f"     {route['endpoint']}: {route['path']} ({route['methods']})")
        
        print("\n3. Testing service registry routes...")
        with app.test_client() as client:
            # Test /api/services
            response = client.get('/api/services')
            print(f"   /api/services: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"     Success: {data.get('success', 'N/A')}")
                print(f"     Total Services: {data.get('total_services', 'N/A')}")
            
            # Test /api/services/health
            response = client.get('/api/services/health')
            print(f"   /api/services/health: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"     Success: {data.get('success', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_main_app_routes()