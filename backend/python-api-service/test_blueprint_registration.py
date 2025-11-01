#!/usr/bin/env python3
"""
Test blueprint registration in the main app
"""
import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_blueprint_registration():
    """Test if service registry blueprint can be registered"""
    try:
        # Import the blueprint
        from service_registry_routes import service_registry_bp
        
        print("Service Registry Blueprint:")
        print(f"  Name: {service_registry_bp.name}")
        print(f"  URL Prefix: {service_registry_bp.url_prefix}")
        
        # Try to create a Flask app and register the blueprint
        from flask import Flask
        
        app = Flask(__name__)
        
        # Register the blueprint
        app.register_blueprint(service_registry_bp)
        
        print("\nRegistered Routes:")
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                print(f"  {rule.endpoint}: {rule.rule} ({list(rule.methods)})")
        
        # Test if the routes work
        print("\nTesting routes with test client:")
        with app.test_client() as client:
            # Test /api/services
            response = client.get('/api/services')
            print(f"  /api/services: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"    Success: {data.get('success', 'N/A')}")
                print(f"    Total Services: {data.get('total_services', 'N/A')}")
            
            # Test /api/services/health
            response = client.get('/api/services/health')
            print(f"  /api/services/health: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"    Success: {data.get('success', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"Error testing blueprint registration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_blueprint_registration()