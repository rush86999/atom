#!/usr/bin/env python3
"""
Test importing the service registry blueprint the same way the main app does
"""
import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_main_app_import():
    """Test importing the service registry blueprint like the main app does"""
    try:
        print("Testing main app import method...")
        
        # Try to import the blueprint the same way the main app does
        module_name = "service_registry_routes"
        bp_name = "service_registry_bp"
        
        print(f"\n1. Importing {module_name}...")
        module = __import__(module_name, fromlist=[bp_name])
        print(f"   ✓ Module imported successfully")
        
        print(f"\n2. Getting blueprint {bp_name}...")
        blueprint = getattr(module, bp_name)
        print(f"   ✓ Blueprint retrieved successfully")
        print(f"   Blueprint name: {blueprint.name}")
        print(f"   Blueprint URL prefix: {blueprint.url_prefix}")
        
        # Test registering the blueprint
        print(f"\n3. Registering blueprint in Flask app...")
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        print(f"   ✓ Blueprint registered successfully")
        
        # Test routes
        print(f"\n4. Testing routes...")
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                print(f"   {rule.endpoint}: {rule.rule}")
        
        # Test with test client
        print(f"\n5. Testing with test client...")
        with app.test_client() as client:
            response = client.get('/api/services')
            print(f"   /api/services: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"     Success: {data.get('success', 'N/A')}")
                print(f"     Total Services: {data.get('total_services', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_main_app_import()