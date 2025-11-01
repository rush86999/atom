#!/usr/bin/env python3
"""
Direct test of service registry blueprint
"""
import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_service_registry_direct():
    """Test service registry blueprint directly"""
    try:
        # Import the blueprint
        from service_registry_routes import service_registry_bp
        
        print("Service Registry Blueprint Info:")
        print(f"  Name: {service_registry_bp.name}")
        print(f"  URL Prefix: {service_registry_bp.url_prefix}")
        print(f"  Import Name: {service_registry_bp.import_name}")
        
        # Test creating a Flask app with just this blueprint
        from flask import Flask
        
        app = Flask(__name__)
        app.register_blueprint(service_registry_bp)
        
        print("\nRegistered Routes in Flask App:")
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                print(f"  {rule.endpoint}: {rule.rule} ({list(rule.methods)})")
        
        return True
        
    except Exception as e:
        print(f"Error testing service registry: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_service_registry_direct()