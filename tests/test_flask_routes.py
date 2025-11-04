#!/usr/bin/env python3
"""
Flask App Route Inspection Test
Tests the actual Flask application to see which routes are registered
"""

import requests
import json
import sys
from typing import Dict, List, Any


class FlaskRouteInspector:
    """Inspect Flask application routes and blueprint registration"""

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url.rstrip("/")

    def get_all_routes(self) -> List[Dict[str, Any]]:
        """Get all registered routes from the application"""
        try:
            response = requests.get(f"{self.base_url}/api/routes", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("routes", [])
            else:
                print(f"❌ Failed to get routes: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error getting routes: {e}")
            return []

    def inspect_auth_blueprints(self):
        """Inspect auth blueprint registration in detail"""
        routes = self.get_all_routes()

        print("🔍 AUTH BLUEPRINT INSPECTION")
        print("=" * 60)

        # Group routes by blueprint
        blueprints = {}
        for route in routes:
            endpoint = route.get("endpoint", "")
            blueprint_name = endpoint.split(".")[0] if "." in endpoint else "unknown"

            if blueprint_name not in blueprints:
                blueprints[blueprint_name] = {
                    "routes": [],
                    "auth_routes": [],
                    "endpoints": [],
                }

            route_info = {
                "endpoint": endpoint,
                "path": route.get("path", ""),
                "methods": list(route.get("methods", [])),
            }

            blueprints[blueprint_name]["routes"].append(route_info)
            blueprints[blueprint_name]["endpoints"].append(endpoint)

            if "/api/auth/" in route.get("path", ""):
                blueprints[blueprint_name]["auth_routes"].append(route_info)

        # Print auth blueprints
        auth_blueprints = {k: v for k, v in blueprints.items() if v["auth_routes"]}

        print(f"\n📋 AUTH BLUEPRINTS ({len(auth_blueprints)}):")
        print("-" * 40)

        for bp_name, bp_data in sorted(auth_blueprints.items()):
            auth_count = len(bp_data["auth_routes"])
            total_count = len(bp_data["routes"])
            print(f"🔐 {bp_name}: {auth_count} auth routes ({total_count} total)")

            for auth_route in bp_data["auth_routes"]:
                print(f"   - {auth_route['path']}")

        # Check for missing auth blueprints
        target_auth_blueprints = ["auth_asana_bp", "auth_trello_bp", "auth_notion_bp"]

        print(f"\n🎯 TARGET AUTH BLUEPRINTS:")
        print("-" * 40)

        missing_blueprints = []
        for target_bp in target_auth_blueprints:
            if target_bp in blueprints:
                bp_data = blueprints[target_bp]
                auth_count = len(bp_data["auth_routes"])
                status = "✅" if auth_count > 0 else "⚠️"
                print(f"{status} {target_bp}: {auth_count} auth routes")

                if auth_count == 0:
                    print(f"   ⚠️  No auth routes found")
                    print(f"   📋 Available endpoints: {bp_data['endpoints']}")
            else:
                print(f"❌ {target_bp}: NOT REGISTERED")
                missing_blueprints.append(target_bp)

        # Check blueprint conflicts
        print(f"\n⚠️  BLUEPRINT CONFLICT CHECK:")
        print("-" * 40)

        blueprint_names = list(blueprints.keys())
        name_conflicts = {}

        for bp_name in blueprint_names:
            # Normalize name for conflict checking
            normalized = (
                bp_name.replace("_bp", "").replace("auth_", "").replace("_auth", "")
            )
            if normalized not in name_conflicts:
                name_conflicts[normalized] = []
            name_conflicts[normalized].append(bp_name)

        conflicts = {k: v for k, v in name_conflicts.items() if len(v) > 1}

        if conflicts:
            for base_name, bp_list in conflicts.items():
                print(f"🔍 {base_name}: {', '.join(bp_list)}")
        else:
            print("✅ No blueprint name conflicts detected")

        # Summary
        print(f"\n📊 SUMMARY:")
        print("-" * 40)
        print(f"Total routes: {len(routes)}")
        print(f"Total blueprints: {len(blueprints)}")
        print(f"Auth blueprints: {len(auth_blueprints)}")
        print(f"Missing target blueprints: {len(missing_blueprints)}")

        if missing_blueprints:
            print(f"\n🎯 RECOMMENDATIONS:")
            print("-" * 40)
            print("Missing auth blueprints:")
            for bp in missing_blueprints:
                print(f"  - {bp}")
            print("\nPossible causes:")
            print("  1. Blueprint not imported correctly")
            print("  2. Import error in blueprint module")
            print("  3. Blueprint name mismatch")
            print("  4. Flask app configuration issue")

    def test_auth_endpoints(self):
        """Test all auth endpoints for accessibility"""
        print(f"\n🔍 AUTH ENDPOINT TESTING")
        print("=" * 60)

        auth_services = [
            "gmail",
            "outlook",
            "slack",
            "teams",
            "trello",
            "asana",
            "notion",
            "github",
            "dropbox",
            "gdrive",
        ]

        results = {}
        for service in auth_services:
            url = f"{self.base_url}/api/auth/{service}/authorize?user_id=test_user"
            try:
                response = requests.get(url, timeout=5)
                results[service] = {
                    "status_code": response.status_code,
                    "working": response.status_code in [200, 302],
                    "content_type": response.headers.get("content-type", ""),
                    "response_type": "JSON"
                    if "application/json" in response.headers.get("content-type", "")
                    else "HTML"
                    if "text/html" in response.headers.get("content-type", "")
                    else "Other",
                }
            except Exception as e:
                results[service] = {
                    "status_code": None,
                    "working": False,
                    "error": str(e),
                    "response_type": "Error",
                }

        # Print results
        working_count = sum(1 for r in results.values() if r["working"])
        print(f"Working endpoints: {working_count}/{len(auth_services)}")
        print("-" * 40)

        for service, result in results.items():
            status = "✅" if result["working"] else "❌"
            error_info = f" - {result['error']}" if "error" in result else ""
            print(
                f"{status} {service}: {result['status_code']} ({result.get('response_type', 'Unknown')}){error_info}"
            )

    def run_comprehensive_inspection(self):
        """Run comprehensive Flask app inspection"""
        print("🚀 FLASK APP ROUTE INSPECTION")
        print("=" * 60)
        print(f"Base URL: {self.base_url}")

        # Test connectivity
        try:
            response = requests.get(f"{self.base_url}/healthz", timeout=5)
            if response.status_code == 200:
                print("✅ App is running and accessible")
            else:
                print(f"⚠️ App returned status: {response.status_code}")
        except Exception as e:
            print(f"❌ App is not accessible: {e}")
            return

        # Run inspections
        self.inspect_auth_blueprints()
        self.test_auth_endpoints()


def main():
    """Main function"""
    base_url = "http://localhost:5058"

    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    inspector = FlaskRouteInspector(base_url)
    inspector.run_comprehensive_inspection()


if __name__ == "__main__":
    main()
