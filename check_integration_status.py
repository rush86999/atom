#!/usr/bin/env python3
"""
Integration Status Checker
Checks the current status of all ATOM service integrations
"""

import os
import sys
import requests
import json
import logging
from typing import Dict, List, Any, Optional

# Add backend modules to Python path
backend_path = os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IntegrationStatusChecker:
    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.results = {}

    def check_backend_health(self) -> bool:
        """Check if backend is accessible"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Backend is accessible")
                return True
            else:
                logger.error(f"❌ Backend returned status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Backend not accessible: {e}")
            return False

    def check_service_endpoint(
        self, service_name: str, endpoint: str
    ) -> Dict[str, Any]:
        """Check a specific service endpoint"""
        url = f"{self.base_url}{endpoint}"
        try:
            if endpoint.endswith("/health") or endpoint.endswith("/healthz"):
                response = requests.get(url, timeout=5)
            else:
                response = requests.post(url, json={"user_id": "test_user"}, timeout=5)

            result = {
                "status_code": response.status_code,
                "accessible": response.status_code < 500,
                "response": response.text[:200] if response.text else "No response",
            }

            if response.status_code == 200:
                try:
                    data = response.json()
                    result["data"] = data
                    if data.get("ok"):
                        result["status"] = "operational"
                    else:
                        result["status"] = "configured_but_error"
                except:
                    result["status"] = "operational"
            elif response.status_code == 401:
                result["status"] = "needs_authentication"
            elif response.status_code == 404:
                result["status"] = "not_registered"
            else:
                result["status"] = "error"

            return result

        except requests.exceptions.RequestException as e:
            return {"status": "not_accessible", "error": str(e), "accessible": False}

    def check_all_integrations(self) -> Dict[str, Any]:
        """Check status of all service integrations"""
        integrations = {
            "asana": {
                "health": "/api/asana/health",
                "auth": "/api/auth/asana/status",
                "tasks": "/api/asana/list-tasks",
            },
            "github": {
                "health": "/api/github/health",
                "auth": "/api/auth/github/status",
            },
            "notion": {
                "health": "/api/notion/health",
                "auth": "/api/auth/notion/status",
            },
            "slack": {"health": "/api/slack/health", "auth": "/api/auth/slack/status"},
            "trello": {
                "health": "/api/trello/health",
                "auth": "/api/auth/trello/status",
            },
            "jira": {"health": "/api/jira/health", "auth": "/api/auth/jira/status"},
            "gdrive": {
                "health": "/api/gdrive/health",
                "auth": "/api/auth/gdrive/status",
            },
            "outlook": {
                "health": "/api/outlook/health",
                "auth": "/api/auth/outlook/status",
            },
            "dropbox": {
                "health": "/api/dropbox/health",
                "auth": "/api/auth/dropbox/status",
            },
            "box": {"health": "/api/box/health", "auth": "/api/auth/box/status"},
        }

        results = {}

        for service_name, endpoints in integrations.items():
            logger.info(f"🔍 Checking {service_name} integration...")
            service_results = {}

            for endpoint_type, endpoint in endpoints.items():
                result = self.check_service_endpoint(service_name, endpoint)
                service_results[endpoint_type] = result

            # Determine overall service status
            if all(r["accessible"] for r in service_results.values()):
                service_results["overall_status"] = "operational"
            elif any(
                r["status"] == "needs_authentication" for r in service_results.values()
            ):
                service_results["overall_status"] = "needs_authentication"
            elif any(r["status"] == "not_registered" for r in service_results.values()):
                service_results["overall_status"] = "not_registered"
            else:
                service_results["overall_status"] = "error"

            results[service_name] = service_results

        return results

    def check_environment_config(self) -> Dict[str, Any]:
        """Check environment variable configuration"""
        env_vars = {
            "ASANA_CLIENT_ID": os.getenv("ASANA_CLIENT_ID"),
            "ASANA_CLIENT_SECRET": os.getenv("ASANA_CLIENT_SECRET"),
            "GITHUB_CLIENT_ID": os.getenv("GITHUB_CLIENT_ID"),
            "GITHUB_CLIENT_SECRET": os.getenv("GITHUB_CLIENT_SECRET"),
            "NOTION_CLIENT_ID": os.getenv("NOTION_CLIENT_ID"),
            "NOTION_CLIENT_SECRET": os.getenv("NOTION_CLIENT_SECRET"),
            "SLACK_CLIENT_ID": os.getenv("SLACK_CLIENT_ID"),
            "SLACK_CLIENT_SECRET": os.getenv("SLACK_CLIENT_SECRET"),
            "DATABASE_URL": os.getenv("DATABASE_URL"),
            "PYTHON_API_SERVICE_BASE_URL": os.getenv("PYTHON_API_SERVICE_BASE_URL"),
        }

        configured = {k: bool(v) for k, v in env_vars.items()}
        configured_count = sum(configured.values())
        total_count = len(configured)

        return {
            "configured_vars": configured,
            "configured_count": configured_count,
            "total_count": total_count,
            "configuration_rate": configured_count / total_count
            if total_count > 0
            else 0,
        }

    def check_service_imports(self) -> Dict[str, bool]:
        """Check if service modules can be imported"""
        services_to_check = [
            "asana_service_real",
            "asana_handler",
            "auth_handler_asana",
            "db_oauth_asana",
            "github_handler",
            "notion_handler",
            "slack_handler",
        ]

        import_results = {}

        for service_module in services_to_check:
            try:
                if service_module == "asana_service_real":
                    from asana_service_real import AsanaServiceReal
                elif service_module == "asana_handler":
                    from asana_handler import asana_bp
                elif service_module == "auth_handler_asana":
                    from auth_handler_asana import auth_asana_bp
                elif service_module == "db_oauth_asana":
                    from db_oauth_asana import store_tokens
                elif service_module == "github_handler":
                    from github_handler import github_bp
                elif service_module == "notion_handler":
                    from notion_handler import notion_bp
                elif service_module == "slack_handler":
                    from slack_handler import slack_bp

                import_results[service_module] = True
            except ImportError as e:
                import_results[service_module] = False
                logger.warning(f"❌ Failed to import {service_module}: {e}")
            except Exception as e:
                import_results[service_module] = False
                logger.error(f"❌ Error importing {service_module}: {e}")

        return import_results

    def generate_summary(self) -> Dict[str, Any]:
        """Generate comprehensive integration status summary"""
        logger.info("🚀 Starting comprehensive integration status check...")

        summary = {
            "timestamp": None,
            "backend_accessible": False,
            "environment_config": {},
            "service_imports": {},
            "integrations": {},
            "recommendations": [],
        }

        # Check backend
        summary["backend_accessible"] = self.check_backend_health()

        # Check environment
        summary["environment_config"] = self.check_environment_config()

        # Check service imports
        summary["service_imports"] = self.check_service_imports()

        # Check integrations if backend is accessible
        if summary["backend_accessible"]:
            summary["integrations"] = self.check_all_integrations()
        else:
            logger.warning("⚠️  Backend not accessible, skipping integration checks")
            summary["integrations"] = {}

        # Generate recommendations
        summary["recommendations"] = self.generate_recommendations(summary)

        summary["timestamp"] = __import__("datetime").datetime.now().isoformat()

        return summary

    def generate_recommendations(self, summary: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on status"""
        recommendations = []

        # Backend recommendations
        if not summary["backend_accessible"]:
            recommendations.append("🚨 Start the ATOM backend server")
            recommendations.append(
                "🔧 Check if backend is running on correct port (5058)"
            )
            recommendations.append("📋 Verify backend startup logs for errors")

        # Environment recommendations
        env_config = summary["environment_config"]
        if env_config["configuration_rate"] < 0.5:
            recommendations.append("🔑 Configure missing environment variables")
            recommendations.append("📝 Set up OAuth credentials for target services")

        # Service import recommendations
        imports = summary["service_imports"]
        failed_imports = [k for k, v in imports.items() if not v]
        if failed_imports:
            recommendations.append(
                f"🔧 Fix import issues for: {', '.join(failed_imports)}"
            )

        # Integration recommendations
        integrations = summary.get("integrations", {})
        if integrations:
            needs_auth = [
                k
                for k, v in integrations.items()
                if v.get("overall_status") == "needs_authentication"
            ]
            not_registered = [
                k
                for k, v in integrations.items()
                if v.get("overall_status") == "not_registered"
            ]

            if needs_auth:
                recommendations.append(
                    f"🔐 Complete OAuth setup for: {', '.join(needs_auth)}"
                )
            if not_registered:
                recommendations.append(
                    f"📋 Register integration endpoints for: {', '.join(not_registered)}"
                )

        # General recommendations
        if not recommendations:
            recommendations.append(
                "🎉 All systems operational! Proceed with user testing."
            )
        else:
            recommendations.append("📊 Run detailed integration tests after fixes")
            recommendations.append("👥 Test with actual user authentication")

        return recommendations

    def print_summary(self, summary: Dict[str, Any]):
        """Print formatted summary to console"""
        print("\n" + "=" * 80)
        print("🚀 ATOM INTEGRATION STATUS SUMMARY")
        print("=" * 80)

        print(f"\n📅 Timestamp: {summary['timestamp']}")

        # Backend status
        backend_status = (
            "✅ ACCESSIBLE" if summary["backend_accessible"] else "❌ NOT ACCESSIBLE"
        )
        print(f"\n🔧 Backend Status: {backend_status}")

        # Environment configuration
        env_config = summary["environment_config"]
        print(
            f"\n🔑 Environment Configuration: {env_config['configured_count']}/{env_config['total_count']} variables configured"
        )
        for var, configured in env_config["configured_vars"].items():
            status = "✅" if configured else "❌"
            print(f"   {status} {var}")

        # Service imports
        imports = summary["service_imports"]
        successful_imports = sum(imports.values())
        total_imports = len(imports)
        print(f"\n📦 Service Imports: {successful_imports}/{total_imports} successful")
        for service, imported in imports.items():
            status = "✅" if imported else "❌"
            print(f"   {status} {service}")

        # Integration status
        integrations = summary.get("integrations", {})
        if integrations:
            print(f"\n🔗 Service Integrations:")
            operational = [
                k
                for k, v in integrations.items()
                if v.get("overall_status") == "operational"
            ]
            needs_auth = [
                k
                for k, v in integrations.items()
                if v.get("overall_status") == "needs_authentication"
            ]
            not_registered = [
                k
                for k, v in integrations.items()
                if v.get("overall_status") == "not_registered"
            ]
            errors = [
                k for k, v in integrations.items() if v.get("overall_status") == "error"
            ]

            if operational:
                print(f"   ✅ Operational: {', '.join(operational)}")
            if needs_auth:
                print(f"   🔐 Needs Authentication: {', '.join(needs_auth)}")
            if not_registered:
                print(f"   📋 Not Registered: {', '.join(not_registered)}")
            if errors:
                print(f"   ❌ Errors: {', '.join(errors)}")
        else:
            print(f"\n🔗 Service Integrations: Not checked (backend inaccessible)")

        # Recommendations
        print(f"\n🎯 RECOMMENDATIONS:")
        for i, recommendation in enumerate(summary["recommendations"], 1):
            print(f"   {i}. {recommendation}")

        print("\n" + "=" * 80)


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(description="Check ATOM integration status")
    parser.add_argument(
        "--url", default="http://localhost:5058", help="Base URL of ATOM backend"
    )
    parser.add_argument("--output", help="Output file for JSON results")

    args = parser.parse_args()

    checker = IntegrationStatusChecker(base_url=args.url)
    summary = checker.generate_summary()

    # Print to console
    checker.print_summary(summary)

    # Save to file if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\n💾 Results saved to: {args.output}")

    # Exit with appropriate code
    if not summary["backend_accessible"]:
        sys.exit(1)
    elif summary["environment_config"]["configuration_rate"] < 0.3:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
