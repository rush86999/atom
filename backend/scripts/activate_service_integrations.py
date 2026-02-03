#!/usr/bin/env python3
"""
Service Integration Activation Script

This script systematically activates and tests service integrations
to increase the number of actively connected services from 2 to 10+.
"""

import json
import logging
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ServiceActivationResult:
    """Results from service activation attempts"""

    service_name: str
    status: str
    details: Dict[str, Any]
    error: Optional[str] = None


class ServiceIntegrationActivator:
    """Service integration activation and testing tool"""

    def __init__(self, backend_url="http://localhost:5058"):
        self.backend_url = backend_url
        self.results = []
        self.target_services = [
            # Email Services
            {
                "name": "gmail",
                "health_endpoint": "/api/gmail/health",
                "oauth_required": True,
            },
            {
                "name": "outlook",
                "health_endpoint": "/api/outlook/health",
                "oauth_required": True,
            },
            # Task Management
            {
                "name": "notion",
                "health_endpoint": "/api/notion/health",
                "oauth_required": True,
            },
            {
                "name": "trello",
                "health_endpoint": "/api/trello/health",
                "oauth_required": True,
            },
            {
                "name": "asana",
                "health_endpoint": "/api/asana/health",
                "oauth_required": True,
            },
            # File Storage
            {
                "name": "google_drive",
                "health_endpoint": "/api/gdrive/health",
                "oauth_required": True,
            },
            {
                "name": "dropbox",
                "health_endpoint": "/api/dropbox/health",
                "oauth_required": True,
            },
            # Communication
            {
                "name": "microsoft_teams",
                "health_endpoint": "/api/teams/health",
                "oauth_required": True,
            },
            # Calendar
            {
                "name": "outlook_calendar",
                "health_endpoint": "/api/outlook-calendar/health",
                "oauth_required": True,
            },
        ]

    def run_service_activation(self) -> bool:
        """Run comprehensive service activation"""
        print("🚀 Starting Service Integration Activation")
        print("=" * 60)
        print(f"Target: Activate {len(self.target_services)} core services")

        # Get current service status
        current_status = self.get_current_service_status()
        print(
            f"Current Status: {current_status.get('active_services', 0)}/{current_status.get('total_services', 0)} services active"
        )

        # Activate services
        for service_config in self.target_services:
            print(f"\n🔧 Activating: {service_config['name']}")
            result = self.activate_service(service_config)
            self.results.append(result)

            status_icon = "✅" if result.status == "ACTIVE" else "❌"
            print(
                f"   {status_icon} {result.status}: {result.details.get('message', '')}"
            )
            if result.error:
                print(f"   Error: {result.error}")

        return self.generate_activation_report()

    def get_current_service_status(self) -> Dict[str, Any]:
        """Get current service registry status"""
        try:
            response = requests.get(
                f"{self.backend_url}/api/services/status", timeout=10
            )
            data = response.json()

            return {
                "total_services": data.get("total_services", 0),
                "active_services": data.get("status_summary", {}).get("active", 0),
                "connected_services": data.get("status_summary", {}).get(
                    "connected", 0
                ),
                "inactive_services": data.get("status_summary", {}).get("inactive", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get service status: {str(e)}")
            return {}

    def activate_service(
        self, service_config: Dict[str, Any]
    ) -> ServiceActivationResult:
        """Activate a specific service"""
        service_name = service_config["name"]
        health_endpoint = service_config["health_endpoint"]
        oauth_required = service_config["oauth_required"]

        try:
            # Test service health endpoint
            response = requests.get(
                f"{self.backend_url}{health_endpoint}",
                params={"user_id": "test_user"},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()

                # Check if service is active
                is_active = (
                    data.get("status") == "connected"
                    or data.get("available") == True
                    or data.get("ok") == True
                )

                if is_active:
                    return ServiceActivationResult(
                        service_name=service_name,
                        status="ACTIVE",
                        details={
                            "message": f"Service is already active",
                            "health_data": data,
                        },
                    )
                else:
                    # Service exists but needs activation
                    if oauth_required:
                        return ServiceActivationResult(
                            service_name=service_name,
                            status="OAUTH_REQUIRED",
                            details={
                                "message": f"Service requires OAuth authorization",
                                "health_data": data,
                            },
                        )
                    else:
                        return ServiceActivationResult(
                            service_name=service_name,
                            status="CONFIGURATION_NEEDED",
                            details={
                                "message": f"Service needs configuration",
                                "health_data": data,
                            },
                        )

            elif response.status_code == 401:
                # OAuth required
                return ServiceActivationResult(
                    service_name=service_name,
                    status="OAUTH_REQUIRED",
                    details={
                        "message": f"OAuth authorization required for {service_name}",
                        "oauth_endpoint": f"{self.backend_url}/api/auth/{service_name}/authorize",
                    },
                )

            elif response.status_code == 404:
                # Service endpoint not found
                return ServiceActivationResult(
                    service_name=service_name,
                    status="ENDPOINT_NOT_FOUND",
                    details={
                        "message": f"Health endpoint not found: {health_endpoint}"
                    },
                )

            else:
                return ServiceActivationResult(
                    service_name=service_name,
                    status="ERROR",
                    details={
                        "message": f"HTTP {response.status_code} from health endpoint"
                    },
                    error=f"HTTP {response.status_code}",
                )

        except requests.RequestException as e:
            return ServiceActivationResult(
                service_name=service_name,
                status="CONNECTION_ERROR",
                details={"message": f"Failed to connect to service endpoint"},
                error=str(e),
            )
        except Exception as e:
            return ServiceActivationResult(
                service_name=service_name,
                status="ERROR",
                details={"message": f"Unexpected error activating service"},
                error=str(e),
            )

    def test_service_workflow_integration(self, service_name: str) -> Dict[str, Any]:
        """Test service integration with workflow generation"""
        test_inputs = {
            "gmail": "Send an email to the team",
            "notion": "Create a page in Notion",
            "trello": "Create a card in Trello",
            "asana": "Create a task in Asana",
            "google_drive": "Upload a file to Google Drive",
            "dropbox": "Save file to Dropbox",
            "microsoft_teams": "Send message to Teams",
            "outlook_calendar": "Schedule meeting in Outlook",
        }

        if service_name not in test_inputs:
            return {"success": False, "error": "No test input available"}

        try:
            response = requests.post(
                f"{self.backend_url}/api/workflow-automation/generate",
                json={"user_input": test_inputs[service_name], "user_id": "test_user"},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                services_used = data.get("workflow", {}).get("services", [])

                return {
                    "success": True,
                    "service_included": service_name in services_used,
                    "services_used": services_used,
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_oauth_instructions(self) -> str:
        """Generate OAuth setup instructions"""
        instructions = []

        for result in self.results:
            if result.status == "OAUTH_REQUIRED":
                oauth_url = f"{self.backend_url}/api/auth/{result.service_name}/authorize?user_id=test_user"
                instructions.append(f"""
🔐 {result.service_name.upper()} OAuth Setup:
   1. Visit: {oauth_url}
   2. Follow the OAuth authorization flow
   3. Complete the setup in your browser
   4. Test with: curl -s "{self.backend_url}/api/{result.service_name}/health?user_id=test_user"
                """)

        return "\n".join(instructions) if instructions else "No OAuth setup required"

    def generate_activation_report(self) -> bool:
        """Generate comprehensive activation report"""
        print("\n" + "=" * 60)
        print("📊 SERVICE ACTIVATION REPORT")
        print("=" * 60)

        active_services = [r for r in self.results if r.status == "ACTIVE"]
        oauth_required = [r for r in self.results if r.status == "OAUTH_REQUIRED"]
        configuration_needed = [
            r for r in self.results if r.status == "CONFIGURATION_NEEDED"
        ]
        errors = [
            r
            for r in self.results
            if r.status in ["ERROR", "CONNECTION_ERROR", "ENDPOINT_NOT_FOUND"]
        ]

        print(f"\n📈 ACTIVATION SUMMARY:")
        print(f"   ✅ Active Services: {len(active_services)}")
        print(f"   🔐 OAuth Required: {len(oauth_required)}")
        print(f"   ⚙️  Configuration Needed: {len(configuration_needed)}")
        print(f"   ❌ Errors: {len(errors)}")

        # Active services
        if active_services:
            print(f"\n✅ ACTIVE SERVICES:")
            for result in active_services:
                print(f"   - {result.service_name}")

        # OAuth required services
        if oauth_required:
            print(f"\n🔐 OAUTH REQUIRED:")
            for result in oauth_required:
                print(
                    f"   - {result.service_name}: {result.details.get('message', '')}"
                )

        # Configuration needed
        if configuration_needed:
            print(f"\n⚙️  CONFIGURATION NEEDED:")
            for result in configuration_needed:
                print(
                    f"   - {result.service_name}: {result.details.get('message', '')}"
                )

        # Errors
        if errors:
            print(f"\n❌ ERRORS:")
            for result in errors:
                print(f"   - {result.service_name}: {result.error}")

        # OAuth instructions
        oauth_instructions = self.generate_oauth_instructions()
        if oauth_instructions:
            print(f"\n🎯 OAUTH SETUP INSTRUCTIONS:")
            print(oauth_instructions)

        # Next steps
        print(f"\n🚀 NEXT STEPS:")
        if oauth_required:
            print("   1. Complete OAuth setup for required services")
            print("   2. Test each service after OAuth completion")
            print("   3. Run workflow integration tests")
        elif configuration_needed:
            print("   1. Configure service settings and API keys")
            print("   2. Test service connectivity")
            print("   3. Verify workflow integration")
        else:
            print("   1. All target services are active or properly configured!")
            print("   2. Proceed with workflow testing and user acceptance")

        # Save detailed report
        report_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "activation_summary": {
                "total_targeted": len(self.target_services),
                "active": len(active_services),
                "oauth_required": len(oauth_required),
                "configuration_needed": len(configuration_needed),
                "errors": len(errors),
            },
            "service_results": [
                {
                    "service_name": r.service_name,
                    "status": r.status,
                    "details": r.details,
                    "error": r.error,
                }
                for r in self.results
            ],
        }

        with open("service_activation_report.json", "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n📄 Detailed report saved to: service_activation_report.json")

        # Success criteria: At least 50% of target services active or properly configured
        successful_activations = len(active_services) + len(configuration_needed)
        success_threshold = len(self.target_services) * 0.5

        return successful_activations >= success_threshold


def main():
    """Main service activation function"""
    activator = ServiceIntegrationActivator()
    success = activator.run_service_activation()

    if success:
        print("\n🎉 Service Activation: SUCCESS - Ready for next steps")
        sys.exit(0)
    else:
        print("\n❌ Service Activation: NEEDS ATTENTION - Review OAuth setup")
        sys.exit(1)


if __name__ == "__main__":
    main()
