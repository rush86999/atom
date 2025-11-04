#!/usr/bin/env python3
"""
Blueprint Debug Script for ATOM Platform
Tests blueprint registration and route availability
"""

import requests
import json
import sys
from typing import Dict, List, Any


class BlueprintDebugger:
    """Debug blueprint registration and route availability"""

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

    def check_auth_endpoints(self) -> Dict[str, Any]:
        """Check all OAuth authorization endpoints"""
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
                response = requests.get(url, timeout=10)
                results[service] = {
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "working": response.status_code in [200, 302],
                    "error": None,
                }
            except Exception as e:
                results[service] = {
                    "status_code": None,
                    "content_type": "",
                    "working": False,
                    "error": str(e),
                }

        return results

    def check_blueprint_registration(self) -> Dict[str, Any]:
        """Check which blueprints are registered and their routes"""
        routes = self.get_all_routes()

        # Group routes by blueprint
        blueprints = {}
        for route in routes:
            endpoint = route.get("endpoint", "")
            blueprint_name = endpoint.split(".")[0] if "." in endpoint else "unknown"

            if blueprint_name not in blueprints:
                blueprints[blueprint_name] = {"routes": [], "auth_routes": []}

            blueprints[blueprint_name]["routes"].append(
                {
                    "endpoint": endpoint,
                    "path": route.get("path", ""),
                    "methods": route.get("methods", []),
                }
            )

            # Check if it's an auth route
            if "/api/auth/" in route.get("path", ""):
                blueprints[blueprint_name]["auth_routes"].append(route.get("path", ""))

        return blueprints

    def print_detailed_report(self):
        """Print detailed blueprint debug report"""
        print("🔍 BLUEPRINT DEBUG REPORT")
        print("=" * 60)
        print(f"Base URL: {self.base_url}")

        # Get all routes
        routes = self.get_all_routes()
        print(f"\n📊 Total routes: {len(routes)}")

        # Check blueprint registration
        blueprints = self.check_blueprint_registration()
        print(f"\n📋 Registered blueprints: {len(blueprints)}")

        # Print blueprint details
        print("\n🔧 BLUEPRINT DETAILS:")
        print("-" * 60)

        auth_blueprints = []
        for bp_name, bp_data in sorted(blueprints.items()):
            route_count = len(bp_data["routes"])
            auth_route_count = len(bp_data["auth_routes"])

            status = "✅" if route_count > 0 else "❌"
            auth_status = "🔐" if auth_route_count > 0 else "  "

            print(
                f"{status} {auth_status} {bp_name}: {route_count} routes ({auth_route_count} auth)"
            )

            if auth_route_count > 0:
                auth_blueprints.append(bp_name)

        # Print auth routes specifically
        print(f"\n🔐 AUTH BLUEPRINTS ({len(auth_blueprints)}):")
        print("-" * 60)
        for bp_name in auth_blueprints:
            bp_data = blueprints[bp_name]
            print(f"\n{bp_name}:")
            for auth_route in bp_data["auth_routes"]:
                print(f"  - {auth_route}")

        # Check auth endpoints
        print(f"\n🎯 AUTH ENDPOINT STATUS:")
        print("-" * 60)

        auth_results = self.check_auth_endpoints()
        working_count = sum(1 for result in auth_results.values() if result["working"])

        print(f"Working: {working_count}/{len(auth_results)}")

        for service, result in auth_results.items():
            status = "✅" if result["working"] else "❌"
            error_info = f" - {result['error']}" if result["error"] else ""
            print(f"{status} {service}: {result['status_code']}{error_info}")

        # Summary
        print(f"\n📈 SUMMARY:")
        print("-" * 60)
        print(f"Total routes: {len(routes)}")
        print(f"Total blueprints: {len(blueprints)}")
        print(f"Auth blueprints: {len(auth_blueprints)}")
        print(f"Working auth endpoints: {working_count}/{len(auth_results)}")

        # Recommendations
        print(f"\n🎯 RECOMMENDATIONS:")
        print("-" * 60)

        missing_auth_services = []
        for service, result in auth_results.items():
            if not result["working"]:
                missing_auth_services.append(service)

        if missing_auth_services:
            print(f"Fix missing auth endpoints ({len(missing_auth_services)}):")
            for service in missing_auth_services:
                print(f"  - {service}")

        # Check for potential blueprint conflicts
        blueprint_names = list(blueprints.keys())
        duplicate_check = {}
        for bp_name in blueprint_names:
            base_name = (
                bp_name.replace("_bp", "").replace("auth_", "").replace("_auth", "")
            )
            if base_name not in duplicate_check:
                duplicate_check[base_name] = []
            duplicate_check[base_name].append(bp_name)

        conflicts = {k: v for k, v in duplicate_check.items() if len(v) > 1}
        if conflicts:
            print(f"\n⚠️  Potential blueprint conflicts:")
            for base_name, bp_list in conflicts.items():
                print(f"  - {base_name}: {', '.join(bp_list)}")


def main():
    """Main function to run blueprint debug"""
    base_url = "http://localhost:5058"

    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    debugger = BlueprintDebugger(base_url)

    try:
        debugger.print_detailed_report()
    except KeyboardInterrupt:
        print("\n\n❌ Debug interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during debug: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
