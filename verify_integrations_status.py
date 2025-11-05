#!/usr/bin/env python3
"""
ATOM Integration Status Verification Script
Comprehensive verification of all implemented integrations
"""

import os
import sys
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class IntegrationVerifier:
    """Comprehensive integration verification system"""

    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "total_integrations": 0,
            "verified_integrations": 0,
            "integration_details": {},
        }

    def verify_flask_app_running(self) -> bool:
        """Verify Flask application is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def verify_integration_health(self, service: str) -> Dict[str, Any]:
        """Verify health of a specific integration"""
        health_endpoints = {
            "github": "/api/github/enhanced/health",
            "asana": "/api/asana/enhanced/health",
            "notion": "/api/notion/enhanced/health",
            "linear": "/api/linear/enhanced/health",
            "slack": "/api/slack/enhanced/health",
            "teams": "/api/teams/enhanced/health",
            "jira": "/api/jira/enhanced/health",
            "figma": "/api/figma/enhanced/health",
            "trello": "/api/trello/enhanced/health",
            "outlook": "/api/outlook/enhanced/health",
            "google": "/api/google/enhanced/health",
            "dropbox": "/api/dropbox/enhanced/health",
        }

        if service not in health_endpoints:
            return {"status": "unknown", "error": f"No health endpoint for {service}"}

        try:
            response = requests.get(
                f"{self.base_url}{health_endpoints[service]}", timeout=10
            )
            if response.status_code == 200:
                return {"status": "healthy", "data": response.json()}
            else:
                return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
        except requests.exceptions.RequestException as e:
            return {"status": "unreachable", "error": str(e)}

    def verify_oauth_endpoints(self, service: str) -> Dict[str, Any]:
        """Verify OAuth endpoints for a service"""
        oauth_endpoints = {
            "github": "/api/oauth/github/url",
            "asana": "/api/oauth/asana/url",
            "notion": "/api/oauth/notion/url",
            "linear": "/api/oauth/linear/url",
            "slack": "/api/oauth/slack/url",
            "teams": "/api/oauth/teams/url",
            "jira": "/api/oauth/jira/url",
            "figma": "/api/oauth/figma/url",
            "trello": "/api/oauth/trello/url",
            "outlook": "/api/oauth/outlook/url",
            "google": "/api/oauth/google/url",
            "dropbox": "/api/oauth/dropbox/url",
        }

        if service not in oauth_endpoints:
            return {"status": "unknown", "error": f"No OAuth endpoint for {service}"}

        try:
            response = requests.get(
                f"{self.base_url}{oauth_endpoints[service]}", timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {"status": "available", "oauth_url": data.get("oauth_url")}
            else:
                return {
                    "status": "unavailable",
                    "error": f"HTTP {response.status_code}",
                }
        except requests.exceptions.RequestException as e:
            return {"status": "unreachable", "error": str(e)}

    def verify_enhanced_api(self, service: str) -> Dict[str, Any]:
        """Verify enhanced API endpoints for a service"""
        # Test endpoints that don't require authentication
        test_endpoints = {
            "github": "/api/github/enhanced/info",
            "asana": "/api/asana/enhanced/info",
            "notion": "/api/notion/enhanced/info",
            "linear": "/api/linear/enhanced/info",
            "slack": "/api/slack/enhanced/info",
            "teams": "/api/teams/enhanced/info",
            "jira": "/api/jira/enhanced/info",
            "figma": "/api/figma/enhanced/info",
            "trello": "/api/trello/enhanced/info",
            "outlook": "/api/outlook/enhanced/info",
            "google": "/api/google/enhanced/info",
            "dropbox": "/api/dropbox/enhanced/info",
        }

        if service not in test_endpoints:
            return {
                "status": "unknown",
                "error": f"No enhanced API endpoint for {service}",
            }

        try:
            response = requests.get(
                f"{self.base_url}{test_endpoints[service]}", timeout=10
            )
            if response.status_code == 200:
                return {"status": "available", "data": response.json()}
            else:
                return {
                    "status": "unavailable",
                    "error": f"HTTP {response.status_code}",
                }
        except requests.exceptions.RequestException as e:
            return {"status": "unreachable", "error": str(e)}

    def check_file_implementations(self, service: str) -> Dict[str, Any]:
        """Check if integration files exist"""
        file_paths = {
            "github": [
                "backend/python-api-service/github_enhanced_api.py",
                "backend/python-api-service/auth_handler_github.py",
                "backend/python-api-service/db_oauth_github.py",
            ],
            "asana": [
                "backend/python-api-service/asana_enhanced_api.py",
                "backend/python-api-service/auth_handler_asana.py",
                "backend/python-api-service/db_oauth_asana.py",
            ],
            "notion": [
                "backend/python-api-service/notion_enhanced_api.py",
                "backend/python-api-service/auth_handler_notion.py",
                "backend/python-api-service/db_oauth_notion.py",
            ],
            "linear": [
                "backend/python-api-service/linear_enhanced_api.py",
                "backend/python-api-service/auth_handler_linear.py",
                "backend/python-api-service/db_oauth_linear.py",
            ],
            "slack": [
                "backend/python-api-service/slack_enhanced_api.py",
                "backend/python-api-service/auth_handler_slack.py",
                "backend/python-api-service/db_oauth_slack.py",
            ],
            "teams": [
                "backend/python-api-service/teams_enhanced_api.py",
                "backend/python-api-service/auth_handler_teams.py",
                "backend/python-api-service/db_oauth_teams.py",
            ],
            "jira": [
                "backend/python-api-service/jira_enhanced_api.py",
                "backend/python-api-service/auth_handler_jira.py",
                "backend/python-api-service/db_oauth_jira.py",
            ],
            "figma": [
                "backend/python-api-service/figma_enhanced_api.py",
                "backend/python-api-service/auth_handler_figma.py",
                "backend/python-api-service/db_oauth_figma.py",
            ],
            "trello": [
                "backend/python-api-service/trello_enhanced_api.py",
                "backend/python-api-service/auth_handler_trello.py",
                "backend/python-api-service/db_oauth_trello.py",
            ],
            "outlook": [
                "backend/python-api-service/outlook_enhanced_api.py",
                "backend/python-api-service/auth_handler_outlook.py",
                "backend/python-api-service/db_oauth_outlook.py",
            ],
            "google": [
                "backend/python-api-service/google_enhanced_api.py",
                "backend/python-api-service/auth_handler_gdrive.py",
                "backend/python-api-service/db_oauth_gdrive.py",
            ],
            "dropbox": [
                "backend/python-api-service/dropbox_enhanced_api.py",
                "backend/python-api-service/auth_handler_dropbox.py",
                "backend/python-api-service/db_oauth_dropbox.py",
            ],
        }

        if service not in file_paths:
            return {"status": "unknown", "files": []}

        existing_files = []
        missing_files = []

        for file_path in file_paths[service]:
            if os.path.exists(file_path):
                existing_files.append(file_path)
            else:
                missing_files.append(file_path)

        return {
            "status": "complete" if len(missing_files) == 0 else "partial",
            "existing_files": existing_files,
            "missing_files": missing_files,
            "completion_rate": len(existing_files) / len(file_paths[service]),
        }

    def verify_integration(self, service: str) -> Dict[str, Any]:
        """Comprehensive verification of a single integration"""
        print(f"🔍 Verifying {service.upper()} integration...")

        result = {
            "service": service,
            "health_check": self.verify_integration_health(service),
            "oauth_endpoints": self.verify_oauth_endpoints(service),
            "enhanced_api": self.verify_enhanced_api(service),
            "file_implementation": self.check_file_implementations(service),
        }

        # Calculate overall status
        health_ok = result["health_check"]["status"] in ["healthy", "available"]
        oauth_ok = result["oauth_endpoints"]["status"] in ["available", "healthy"]
        api_ok = result["enhanced_api"]["status"] in ["available", "healthy"]
        files_ok = result["file_implementation"]["status"] == "complete"

        if health_ok and oauth_ok and api_ok and files_ok:
            result["overall_status"] = "fully_operational"
            self.results["verified_integrations"] += 1
        elif files_ok and (health_ok or oauth_ok or api_ok):
            result["overall_status"] = "partially_operational"
        else:
            result["overall_status"] = "not_operational"

        return result

    def run_comprehensive_verification(self) -> Dict[str, Any]:
        """Run comprehensive verification of all integrations"""
        print("🚀 Starting ATOM Integration Verification")
        print("=" * 50)

        # Verify Flask app is running
        if not self.verify_flask_app_running():
            print("❌ Flask application is not running")
            print("Please start the backend server first:")
            print("  cd backend/python-api-service && python main_api_app.py")
            return self.results

        print("✅ Flask application is running")

        # List of integrations to verify
        integrations = [
            "github",
            "asana",
            "notion",
            "linear",
            "slack",
            "teams",
            "jira",
            "figma",
            "trello",
            "outlook",
            "google",
            "dropbox",
        ]

        self.results["total_integrations"] = len(integrations)

        # Verify each integration
        for service in integrations:
            result = self.verify_integration(service)
            self.results["integration_details"][service] = result

            status_emoji = {
                "fully_operational": "✅",
                "partially_operational": "⚠️",
                "not_operational": "❌",
            }

            print(
                f"{status_emoji[result['overall_status']]} {service.upper()}: {result['overall_status'].replace('_', ' ').title()}"
            )

        return self.results

    def generate_report(self) -> str:
        """Generate comprehensive verification report"""
        report = []
        report.append("# ATOM Integration Verification Report")
        report.append(f"**Generated**: {self.results['timestamp']}")
        report.append(f"**Total Integrations**: {self.results['total_integrations']}")
        report.append(
            f"**Verified Integrations**: {self.results['verified_integrations']}"
        )
        report.append(
            f"**Success Rate**: {(self.results['verified_integrations'] / self.results['total_integrations'] * 100):.1f}%"
        )
        report.append("")

        # Summary table
        report.append("## Integration Status Summary")
        report.append("| Service | Overall Status | Health | OAuth | API | Files |")
        report.append("|---------|----------------|--------|-------|-----|-------|")

        for service, details in self.results["integration_details"].items():
            health_status = details["health_check"]["status"]
            oauth_status = details["oauth_endpoints"]["status"]
            api_status = details["enhanced_api"]["status"]
            files_status = details["file_implementation"]["status"]

            report.append(
                f"| {service.upper()} | {details['overall_status'].replace('_', ' ').title()} | {health_status} | {oauth_status} | {api_status} | {files_status} |"
            )

        # Detailed findings
        report.append("")
        report.append("## Detailed Findings")

        for service, details in self.results["integration_details"].items():
            report.append(f"### {service.upper()} Integration")
            report.append(
                f"**Overall Status**: {details['overall_status'].replace('_', ' ').title()}"
            )

            # Health check details
            health = details["health_check"]
            report.append(f"- **Health Check**: {health['status']}")
            if health.get("error"):
                report.append(f"  - Error: {health['error']}")

            # OAuth details
            oauth = details["oauth_endpoints"]
            report.append(f"- **OAuth Endpoints**: {oauth['status']}")
            if oauth.get("error"):
                report.append(f"  - Error: {oauth['error']}")

            # API details
            api = details["enhanced_api"]
            report.append(f"- **Enhanced API**: {api['status']}")
            if api.get("error"):
                report.append(f"  - Error: {api['error']}")

            # File implementation
            files = details["file_implementation"]
            report.append(
                f"- **File Implementation**: {files['status']} ({files['completion_rate']:.0%})"
            )
            if files["missing_files"]:
                report.append(f"  - Missing files: {', '.join(files['missing_files'])}")

            report.append("")

        return "\n".join(report)

    def save_report(self, filename: str = "integration_verification_report.md"):
        """Save verification report to file"""
        report_content = self.generate_report()
        with open(filename, "w") as f:
            f.write(report_content)
        print(f"📄 Report saved to: {filename}")


def main():
    """Main execution function"""
    verifier = IntegrationVerifier()
    results = verifier.run_comprehensive_verification()

    print("\n" + "=" * 50)
    print("📊 Verification Complete")
    print(
        f"✅ Verified: {results['verified_integrations']}/{results['total_integrations']} integrations"
    )

    # Generate and save report
    verifier.save_report()

    # Print summary
    fully_operational = sum(
        1
        for details in results["integration_details"].values()
        if details["overall_status"] == "fully_operational"
    )
    partially_operational = sum(
        1
        for details in results["integration_details"].values()
        if details["overall_status"] == "partially_operational"
    )

    print(f"📈 Fully Operational: {fully_operational}")
    print(f"⚠️  Partially Operational: {partially_operational}")
    print(
        f"❌ Not Operational: {results['total_integrations'] - fully_operational - partially_operational}"
    )

    if fully_operational >= 8:
        print("\n🎉 SUCCESS: Integration ecosystem is production-ready!")
    else:
        print(
            "\n🔧 ATTENTION: Some integrations need attention before production deployment."
        )


if __name__ == "__main__":
    main()
