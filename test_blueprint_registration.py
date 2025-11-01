#!/usr/bin/env python3
"""
Manual Blueprint Registration Test
Tests blueprint registration for Asana, Trello, and Notion auth handlers
"""

import os
import sys
import logging

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_blueprint_import():
    """Test importing blueprints directly"""
    print("🔍 TESTING BLUEPRINT IMPORT")
    print("=" * 50)

    # Test Asana
    try:
        from auth_handler_asana import auth_asana_bp

        print("✅ Asana blueprint imported successfully")
        print(f"   Blueprint name: {auth_asana_bp.name}")
        print(f"   Blueprint import name: {auth_asana_bp.import_name}")
        print(f"   Routes: {list(auth_asana_bp.routes.keys())}")
    except Exception as e:
        print(f"❌ Failed to import Asana blueprint: {e}")

    # Test Trello
    try:
        from auth_handler_trello import auth_trello_bp

        print("✅ Trello blueprint imported successfully")
        print(f"   Blueprint name: {auth_trello_bp.name}")
        print(f"   Blueprint import name: {auth_trello_bp.import_name}")
        print(f"   Routes: {list(auth_trello_bp.routes.keys())}")
    except Exception as e:
        print(f"❌ Failed to import Trello blueprint: {e}")

    # Test Notion
    try:
        from auth_handler_notion import auth_notion_bp

        print("✅ Notion blueprint imported successfully")
        print(f"   Blueprint name: {auth_notion_bp.name}")
        print(f"   Blueprint import name: {auth_notion_bp.import_name}")
        print(f"   Routes: {list(auth_notion_bp.routes.keys())}")
    except Exception as e:
        print(f"❌ Failed to import Notion blueprint: {e}")


def test_blueprint_registration():
    """Test blueprint registration with Flask app"""
    print("\n🔍 TESTING BLUEPRINT REGISTRATION")
    print("=" * 50)

    try:
        from flask import Flask

        # Create test Flask app
        app = Flask(__name__)
        app.secret_key = "test-secret-key"

        # Import blueprints
        from auth_handler_asana import auth_asana_bp
        from auth_handler_trello import auth_trello_bp
        from auth_handler_notion import auth_notion_bp

        # Register blueprints
        app.register_blueprint(auth_asana_bp)
        app.register_blueprint(auth_trello_bp)
        app.register_blueprint(auth_notion_bp)

        print("✅ All blueprints registered successfully")

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

    except Exception as e:
        print(f"❌ Blueprint registration test failed: {e}")
        import traceback

        traceback.print_exc()


def test_endpoint_accessibility():
    """Test if endpoints are accessible via HTTP"""
    print("\n🔍 TESTING ENDPOINT ACCESSIBILITY")
    print("=" * 50)

    import requests

    base_url = "http://localhost:5058"
    services = ["asana", "trello", "notion"]

    for service in services:
        url = f"{base_url}/api/auth/{service}/authorize?user_id=test_user"
        try:
            response = requests.get(url, timeout=5)
            status = "✅" if response.status_code in [200, 302] else "❌"
            print(f"{status} {service}: {response.status_code} - {url}")

            if response.status_code == 404:
                # Try to get more info about the 404
                print(f"   🔍 404 Details: {response.text[:200]}")

        except Exception as e:
            print(f"❌ {service}: Error - {e}")


def check_blueprint_conflicts():
    """Check for potential blueprint name conflicts"""
    print("\n🔍 CHECKING FOR BLUEPRINT CONFLICTS")
    print("=" * 50)

    try:
        # Get all registered routes from the running app
        import requests

        response = requests.get("http://localhost:5058/api/routes", timeout=10)

        if response.status_code == 200:
            data = response.json()
            routes = data.get("routes", [])

            # Group by blueprint
            blueprints = {}
            for route in routes:
                endpoint = route.get("endpoint", "")
                blueprint_name = (
                    endpoint.split(".")[0] if "." in endpoint else "unknown"
                )

                if blueprint_name not in blueprints:
                    blueprints[blueprint_name] = []
                blueprints[blueprint_name].append(route)

            # Check for our target blueprints
            target_blueprints = ["auth_asana_bp", "auth_trello_bp", "auth_notion_bp"]
            print("🔍 Target blueprints status:")
            for bp in target_blueprints:
                if bp in blueprints:
                    print(f"✅ {bp}: {len(blueprints[bp])} routes")
                    # Show routes
                    for route in blueprints[bp]:
                        print(f"   - {route.get('path', '')}")
                else:
                    print(f"❌ {bp}: NOT REGISTERED")

            # Check for similar names that might be conflicting
            print("\n🔍 Similar blueprint names:")
            similar_names = [
                name
                for name in blueprints.keys()
                if any(target in name for target in ["asana", "trello", "notion"])
            ]
            for name in similar_names:
                print(f"   - {name}: {len(blueprints[name])} routes")

        else:
            print(f"❌ Failed to get routes: {response.status_code}")

    except Exception as e:
        print(f"❌ Error checking blueprint conflicts: {e}")


def main():
    """Run all tests"""
    print("🚀 MANUAL BLUEPRINT REGISTRATION TEST")
    print("=" * 60)

    # Test blueprint import
    test_blueprint_import()

    # Test blueprint registration
    test_blueprint_registration()

    # Test endpoint accessibility
    test_endpoint_accessibility()

    # Check for conflicts
    check_blueprint_conflicts()

    print("\n🎯 RECOMMENDATIONS:")
    print("=" * 60)
    print("1. If blueprints import but don't register, check Flask app configuration")
    print("2. If endpoints return 404, verify blueprint URL patterns")
    print("3. Check for blueprint name conflicts in the main application")
    print("4. Verify that blueprints are being registered in the correct order")
    print("5. Check for any middleware or decorators that might interfere")


if __name__ == "__main__":
    main()
