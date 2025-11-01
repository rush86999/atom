#!/usr/bin/env python3
"""
Manual Blueprint Registration Test
Tests blueprint registration for Asana, Trello, and Notion auth handlers
"""

import os
import sys
import logging
from flask import Flask

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "backend", "python-api-service")
sys.path.insert(0, backend_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_manual_registration():
    """Test manual blueprint registration"""
    print("🔍 MANUAL BLUEPRINT REGISTRATION TEST")
    print("=" * 60)

    try:
        # Create test Flask app
        app = Flask(__name__)
        app.secret_key = "test-secret-key"

        print("✅ Flask app created")

        # Import blueprints
        try:
            from auth_handler_asana import auth_asana_bp

            print("✅ Imported auth_asana_bp")
        except Exception as e:
            print(f"❌ Failed to import auth_asana_bp: {e}")
            return

        try:
            from auth_handler_trello import auth_trello_bp

            print("✅ Imported auth_trello_bp")
        except Exception as e:
            print(f"❌ Failed to import auth_trello_bp: {e}")
            return

        try:
            from auth_handler_notion import auth_notion_bp

            print("✅ Imported auth_notion_bp")
        except Exception as e:
            print(f"❌ Failed to import auth_notion_bp: {e}")
            return

        # Register blueprints
        try:
            app.register_blueprint(auth_asana_bp)
            print("✅ Registered auth_asana_bp")
        except Exception as e:
            print(f"❌ Failed to register auth_asana_bp: {e}")

        try:
            app.register_blueprint(auth_trello_bp)
            print("✅ Registered auth_trello_bp")
        except Exception as e:
            print(f"❌ Failed to register auth_trello_bp: {e}")

        try:
            app.register_blueprint(auth_notion_bp)
            print("✅ Registered auth_notion_bp")
        except Exception as e:
            print(f"❌ Failed to register auth_notion_bp: {e}")

        # Check registered routes
        print("\n📋 REGISTERED ROUTES:")
        print("-" * 40)

        auth_routes = []
        for rule in app.url_map.iter_rules():
            if "/api/auth/" in str(rule):
                auth_routes.append(
                    {
                        "endpoint": rule.endpoint,
                        "path": str(rule),
                        "methods": list(rule.methods),
                    }
                )

        # Sort by path
        auth_routes.sort(key=lambda x: x["path"])

        for route in auth_routes:
            blueprint_name = (
                route["endpoint"].split(".")[0]
                if "." in route["endpoint"]
                else route["endpoint"]
            )
            print(f"🔐 {blueprint_name}: {route['path']}")

        print(f"\n📊 SUMMARY:")
        print(f"   Total auth routes: {len(auth_routes)}")

        # Check specific services
        services = ["asana", "trello", "notion"]
        for service in services:
            service_routes = [
                r for r in auth_routes if f"/api/auth/{service}/" in r["path"]
            ]
            status = "✅" if service_routes else "❌"
            print(f"   {status} {service}: {len(service_routes)} routes")

        # Check blueprint details
        print(f"\n🔧 BLUEPRINT DETAILS:")
        print("-" * 40)

        blueprints = {}
        for rule in app.url_map.iter_rules():
            endpoint = rule.endpoint
            blueprint_name = endpoint.split(".")[0] if "." in endpoint else "unknown"

            if blueprint_name not in blueprints:
                blueprints[blueprint_name] = {"routes": [], "auth_routes": []}

            blueprints[blueprint_name]["routes"].append(
                {
                    "endpoint": endpoint,
                    "path": str(rule),
                    "methods": list(rule.methods),
                }
            )

            if "/api/auth/" in str(rule):
                blueprints[blueprint_name]["auth_routes"].append(str(rule))

        target_blueprints = ["auth_asana_bp", "auth_trello_bp", "auth_notion_bp"]
        for bp_name in target_blueprints:
            if bp_name in blueprints:
                bp_data = blueprints[bp_name]
                print(
                    f"✅ {bp_name}: {len(bp_data['routes'])} routes ({len(bp_data['auth_routes'])} auth)"
                )
                for auth_route in bp_data["auth_routes"]:
                    print(f"   - {auth_route}")
            else:
                print(f"❌ {bp_name}: NOT REGISTERED")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


def test_endpoint_accessibility():
    """Test if endpoints are accessible via HTTP"""
    print("\n🔍 TESTING ENDPOINT ACCESSIBILITY")
    print("=" * 50)

    import requests

    base_url = "http://localhost:5058"
    services = ["asana", "trello", "notion", "gmail", "slack"]

    for service in services:
        url = f"{base_url}/api/auth/{service}/authorize?user_id=test_user"
        try:
            response = requests.get(url, timeout=5)
            status = "✅" if response.status_code in [200, 302] else "❌"
            print(f"{status} {service}: {response.status_code}")

            if response.status_code == 404:
                # Try to get more info about the 404
                print(f"   🔍 404 Details: {response.text[:100]}...")

        except Exception as e:
            print(f"❌ {service}: Error - {e}")


def main():
    """Run all tests"""
    print("🚀 MANUAL BLUEPRINT REGISTRATION TEST")
    print("=" * 60)

    # Test manual registration
    test_manual_registration()

    # Test endpoint accessibility
    test_endpoint_accessibility()

    print("\n🎯 RECOMMENDATIONS:")
    print("=" * 60)
    print("1. If blueprints import but don't register, check Flask app configuration")
    print("2. If endpoints return 404, verify blueprint URL patterns")
    print("3. Check for blueprint name conflicts in the main application")
    print("4. Verify that blueprints are being registered in the correct order")
    print("5. Check for any middleware or decorators that might interfere")


if __name__ == "__main__":
    main()
