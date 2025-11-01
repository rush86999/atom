#!/usr/bin/env python3
"""
Script to check what blueprints are actually registered in the Flask app
"""
import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_blueprints():
    """Check what blueprints are available"""
    try:
        # Try to import the service registry blueprint directly
        print("\n1. Checking service_registry_routes import:")
        try:
            from service_registry_routes import service_registry_bp
            print("   ✓ service_registry_bp imported successfully")
            print(f"   Name: {service_registry_bp.name}")
            print(f"   URL Prefix: {service_registry_bp.url_prefix}")
        except ImportError as e:
            print(f"   ✗ Failed to import service_registry_bp: {e}")
        
        # Check if we can import the blueprint from the module
        print("\n2. Checking service_registry_routes module:")
        try:
            import service_registry_routes
            print("   ✓ service_registry_routes module imported successfully")
            print(f"   Available attributes: {[attr for attr in dir(service_registry_routes) if not attr.startswith('_')]}")
        except ImportError as e:
            print(f"   ✗ Failed to import service_registry_routes module: {e}")
        
        # Check if we can create the Flask app
        print("\n3. Checking Flask app creation:")
        try:
            from main_api_app import create_app
            app = create_app()
            print("   ✓ Flask app created successfully")
            
            # Check registered blueprints
            print("\n4. Checking registered blueprints:")
            registered_blueprints = []
            for rule in app.url_map.iter_rules():
                if rule.endpoint != 'static':
                    registered_blueprints.append({
                        'endpoint': rule.endpoint,
                        'methods': list(rule.methods),
                        'path': str(rule)
                    })
            
            print(f"   Total registered endpoints: {len(registered_blueprints)}")
            
            # Show service-related endpoints
            service_endpoints = [bp for bp in registered_blueprints if 'service' in bp['endpoint'].lower() or 'service' in bp['path'].lower()]
            print(f"   Service-related endpoints: {len(service_endpoints)}")
            for endpoint in service_endpoints[:10]:  # Show first 10
                print(f"     - {endpoint['endpoint']}: {endpoint['path']} ({endpoint['methods']})")
            
        except Exception as e:
            print(f"   ✗ Failed to create Flask app: {e}")
            
    except Exception as e:
        print(f"Error in check_blueprints: {e}")

if __name__ == "__main__":
    check_blueprints()