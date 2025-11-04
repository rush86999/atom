#!/usr/bin/env python3
"""
OAuth Configuration Verification Script for ATOM Platform

This script verifies that all OAuth services are properly configured
and accessible through the API endpoints.

Features verified:
- OAuth authorization endpoints
- Environment variable configuration
- Service-specific credential validation
- Endpoint accessibility and response format
"""

import os
import requests
import json
import sys
from typing import Dict, List, Tuple, Optional

# Configuration
BASE_URL = "http://localhost:5058"
TEST_USER_ID = "oauth_test_user"

# OAuth services to verify
OAUTH_SERVICES = [
    {
        "name": "gmail",
        "auth_endpoint": "/api/auth/gmail/authorize",
        "status_endpoint": "/api/auth/gmail/status",
        "description": "Gmail OAuth Integration",
        "env_vars": [
            "GMAIL_CLIENT_ID",
            "GMAIL_CLIENT_SECRET",
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
        ],
        "required_scopes": ["gmail.readonly", "gmail.send"],
    },
    {
        "name": "outlook",
        "auth_endpoint": "/api/auth/outlook/authorize",
        "status_endpoint": "/api/auth/outlook/status",
        "description": "Outlook OAuth Integration",
        "env_vars": ["OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET"],
        "required_scopes": ["Mail.Read", "Mail.Send"],
    },
    {
        "name": "slack",
        "auth_endpoint": "/api/auth/slack/authorize",
        "status_endpoint": "/api/auth/slack/status",
        "description": "Slack OAuth Integration",
        "env_vars": ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"],
        "required_scopes": ["channels:read", "chat:write"],
    },
    {
        "name": "teams",
        "auth_endpoint": "/api/auth/teams/authorize",
        "status_endpoint": "/api/auth/teams/status",
        "description": "Microsoft Teams OAuth Integration",
        "env_vars": ["TEAMS_CLIENT_ID", "TEAMS_CLIENT_SECRET"],
        "required_scopes": ["Team.ReadBasic.All", "Chat.Read"],
    },
    {
        "name": "github",
        "auth_endpoint": "/api/auth/github/authorize",
        "status_endpoint": "/api/auth/github/status",
        "description": "GitHub OAuth Integration",
        "env_vars": ["GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"],
        "required_scopes": ["repo", "read:user"],
    },
    {
        "name": "trello",
        "auth_endpoint": "/api/auth/trello/authorize",
        "status_endpoint": "/api/auth/trello/status",
        "description": "Trello OAuth Integration",
        "env_vars": ["TRELLO_API_KEY", "TRELLO_API_SECRET"],
        "required_scopes": ["read", "write"],
    },
    {
        "name": "asana",
        "auth_endpoint": "/api/auth/asana/authorize",
        "status_endpoint": "/api/auth/asana/status",
        "description": "Asana OAuth Integration",
        "env_vars": ["ASANA_CLIENT_ID", "ASANA_CLIENT_SECRET"],
        "required_scopes": ["default"],
    },
    {
        "name": "notion",
        "auth_endpoint": "/api/auth/notion/authorize",
        "status_endpoint": "/api/auth/notion/status",
        "description": "Notion OAuth Integration",
        "env_vars": ["NOTION_CLIENT_ID", "NOTION_CLIENT_SECRET"],
        "required_scopes": [],
    },
    {
        "name": "dropbox",
        "auth_endpoint": "/api/auth/dropbox/authorize",
        "status_endpoint": "/api/auth/dropbox/status",
        "description": "Dropbox OAuth Integration",
        "env_vars": ["DROPBOX_APP_KEY", "DROPBOX_APP_SECRET"],
        "required_scopes": [],
    },
    {
        "name": "gdrive",
        "auth_endpoint": "/api/auth/gdrive/authorize",
        "status_endpoint": "/api/auth/gdrive/status",
        "description": "Google Drive OAuth Integration",
        "env_vars": [
            "GDRIVE_CLIENT_ID",
            "GDRIVE_CLIENT_SECRET",
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
        ],
        "required_scopes": ["drive.readonly", "drive.file"],
    },
]


class OAuthConfigVerifier:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results = []
        self.verification_summary = {
            "total_services": len(OAUTH_SERVICES),
            "services_with_credentials": 0,
            "endpoints_accessible": 0,
            "services_fully_configured": 0,
        }

    def check_environment_variables(self, service: Dict) -> Tuple[bool, List[str]]:
        """Check if required environment variables are set"""
        missing_vars = []
        configured_vars = []

        for env_var in service["env_vars"]:
            value = os.getenv(env_var)
            if (
                value
                and value not in ["", "your-", "None"]
                and not value.startswith("your-")
            ):
                configured_vars.append(env_var)
            else:
                missing_vars.append(env_var)

        return len(missing_vars) == 0, configured_vars

    def test_auth_endpoint(self, service: Dict) -> Tuple[bool, str, Optional[str]]:
        """Test OAuth authorization endpoint"""
        try:
            endpoint = f"{self.base_url}{service['auth_endpoint']}"
            params = {"user_id": TEST_USER_ID}

            response = requests.get(endpoint, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Check response structure
                if all(key in data for key in ["auth_url", "csrf_token", "user_id"]):
                    auth_url = data["auth_url"]

                    # Check if client ID is properly configured
                    if "client_id=None" in auth_url or "client_id=your-" in auth_url:
                        return (
                            True,
                            f"Endpoint accessible but credentials not configured",
                            auth_url,
                        )
                    else:
                        return True, f"Endpoint working with credentials", auth_url
                else:
                    return False, f"Invalid response structure", None

            elif response.status_code == 404:
                return False, f"Endpoint not found (404)", None
            else:
                return False, f"Unexpected status code {response.status_code}", None

        except requests.exceptions.RequestException as e:
            return False, f"Connection failed: {e}", None

    def test_status_endpoint(self, service: Dict) -> Tuple[bool, str]:
        """Test OAuth status endpoint"""
        try:
            endpoint = f"{self.base_url}{service['status_endpoint']}"
            params = {"user_id": TEST_USER_ID}

            response = requests.get(endpoint, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    return True, f"Status endpoint accessible"
                else:
                    return False, f"Invalid response format"

            elif response.status_code == 404:
                return False, f"Status endpoint not found (404)"
            else:
                return (
                    True,
                    f"Status endpoint accessible (returned {response.status_code})",
                )

        except requests.exceptions.RequestException as e:
            return False, f"Connection failed: {e}"

    def verify_service_configuration(self, service: Dict) -> Dict:
        """Verify complete configuration for a single service"""
        print(f"\n🔍 Verifying {service['description']}...")

        # Check environment variables
        env_configured, configured_vars = self.check_environment_variables(service)

        # Test authorization endpoint
        auth_working, auth_message, auth_url = self.test_auth_endpoint(service)

        # Test status endpoint
        status_working, status_message = self.test_status_endpoint(service)

        # Determine overall status
        fully_configured = env_configured and auth_working and status_working

        result = {
            "service": service["name"],
            "description": service["description"],
            "environment_configured": env_configured,
            "configured_variables": configured_vars,
            "auth_endpoint_working": auth_working,
            "status_endpoint_working": status_working,
            "auth_endpoint_message": auth_message,
            "status_endpoint_message": status_message,
            "auth_url": auth_url,
            "fully_configured": fully_configured,
        }

        # Update summary
        if env_configured:
            self.verification_summary["services_with_credentials"] += 1
        if auth_working:
            self.verification_summary["endpoints_accessible"] += 1
        if fully_configured:
            self.verification_summary["services_fully_configured"] += 1

        return result

    def run_comprehensive_verification(self):
        """Run comprehensive OAuth configuration verification"""
        print("🚀 Starting OAuth Configuration Verification")
        print("=" * 70)

        # Check server health first
        try:
            response = requests.get(f"{self.base_url}/healthz", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                print(
                    f"✅ Server is running (v{health_data.get('version', 'unknown')})"
                )
                print(f"   Total blueprints: {health_data.get('total_blueprints', 0)}")
            else:
                print(f"❌ Server health check failed: {response.status_code}")
                return
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to server: {e}")
            return

        print(f"\n📋 Verifying {len(OAUTH_SERVICES)} OAuth services...")
        print("-" * 70)

        # Verify each service
        for service in OAUTH_SERVICES:
            result = self.verify_service_configuration(service)
            self.results.append(result)

            # Print service status
            status_icon = (
                "✅"
                if result["fully_configured"]
                else "⚠️"
                if result["auth_endpoint_working"]
                else "❌"
            )
            print(f"{status_icon} {service['description']}")

            if result["environment_configured"]:
                print(
                    f"   🔑 Credentials: Configured ({len(result['configured_variables'])} vars)"
                )
            else:
                print(f"   🔑 Credentials: Missing")

            print(f"   🔐 Auth: {result['auth_endpoint_message']}")
            print(f"   📊 Status: {result['status_endpoint_message']}")

        # Generate summary
        self.generate_summary_report()

    def generate_summary_report(self):
        """Generate verification summary report"""
        summary = self.verification_summary

        print("\n" + "=" * 70)
        print("🎯 VERIFICATION SUMMARY")
        print("=" * 70)

        print(
            f"📊 Services with credentials: {summary['services_with_credentials']}/{summary['total_services']}"
        )
        print(
            f"🔐 Accessible endpoints: {summary['endpoints_accessible']}/{summary['total_services']}"
        )
        print(
            f"✅ Fully configured services: {summary['services_fully_configured']}/{summary['total_services']}"
        )

        success_rate = (
            summary["services_fully_configured"] / summary["total_services"]
            if summary["total_services"] > 0
            else 0
        )

        print(f"\n📈 Overall Configuration Rate: {success_rate:.1%}")

        if success_rate >= 0.8:
            print("🎉 OAuth Configuration: EXCELLENT")
        elif success_rate >= 0.5:
            print("⚠️ OAuth Configuration: GOOD (some services need credentials)")
        else:
            print("❌ OAuth Configuration: NEEDS ATTENTION")

        # Save detailed report
        self.save_detailed_report()

    def save_detailed_report(self):
        """Save detailed verification report to file"""
        import time

        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_url": self.base_url,
            "summary": self.verification_summary,
            "services": self.results,
        }

        filename = f"oauth_config_report_{time.strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(filename, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Detailed report saved to: {filename}")
        except Exception as e:
            print(f"\n⚠️ Could not save report: {e}")

    def print_configuration_guide(self):
        """Print configuration guide for missing credentials"""
        print("\n" + "=" * 70)
        print("🔧 CONFIGURATION GUIDE")
        print("=" * 70)

        for service in self.results:
            if not service["environment_configured"]:
                print(f"\n📝 {service['description']}:")
                print(f"   Required environment variables:")
                for env_var in OAUTH_SERVICES[0][
                    "env_vars"
                ]:  # Get from original service definition
                    current_value = os.getenv(env_var, "NOT SET")
                    print(f"   - {env_var}: {current_value}")


def main():
    """Main verification function"""
    verifier = OAuthConfigVerifier()

    try:
        verifier.run_comprehensive_verification()
        verifier.print_configuration_guide()

        # Exit with appropriate code
        success_rate = (
            verifier.verification_summary["services_fully_configured"]
            / verifier.verification_summary["total_services"]
        )
        if success_rate >= 0.5:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️ Verification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
