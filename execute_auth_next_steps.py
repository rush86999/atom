#!/usr/bin/env python3
"""
ATOM Platform Authentication - Next Steps Execution Script

This script provides automated execution of the next steps for the ATOM Platform
authentication implementation, including search configuration, OAuth integration,
and frontend testing.

Usage:
    python execute_auth_next_steps.py [step]

Steps:
    all          - Execute all next steps
    search       - Configure search functionality
    oauth        - Set up OAuth integrations
    frontend     - Test frontend authentication
    status       - Check current system status
    health       - Run comprehensive health checks
"""

import os
import sys
import json
import time
import requests
import logging
import subprocess
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("auth_next_steps.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class AuthNextStepsExecutor:
    """Executor for ATOM Platform authentication next steps"""

    def __init__(self):
        self.backend_url = "http://localhost:5058"
        self.frontend_url = "http://localhost:3000"
        self.test_users = {
            "demo": {"email": "demo@atom.com", "password": "demo123"},
            "admin": {"email": "noreply@atom.com", "password": "admin123"},
            "test": {"email": "test@example.com", "password": "test123"},
        }

    def check_backend_health(self) -> bool:
        """Check if backend is running and healthy"""
        try:
            response = requests.get(f"{self.backend_url}/healthz", timeout=10)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Backend health: {data.get('status', 'unknown')}")
                logger.info(
                    f"   Blueprints: {data.get('total_blueprints', 0)} registered"
                )
                return True
            else:
                logger.error(f"❌ Backend health check failed: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Backend connection failed: {e}")
            return False

    def check_frontend_health(self) -> bool:
        """Check if frontend is running"""
        try:
            response = requests.get(
                self.frontend_url, timeout=10, allow_redirects=False
            )
            # Frontend should redirect to signin when not authenticated
            # 307 (Temporary Redirect) and 302 (Found) are expected
            if response.status_code in [200, 302, 307]:
                logger.info("✅ Frontend is running")
                return True
            else:
                logger.error(f"❌ Frontend health check failed: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Frontend connection failed: {e}")
            return False

    def test_authentication_flow(self) -> bool:
        """Test complete authentication flow"""
        logger.info("🔐 Testing authentication flow...")

        # Test registration
        test_user = {
            "email": f"test_{int(time.time())}@example.com",
            "password": "test123456",
            "first_name": "Test",
            "last_name": "User",
        }

        try:
            # Register new user
            response = requests.post(
                f"{self.backend_url}/api/auth/register", json=test_user, timeout=10
            )

            if response.status_code in [200, 201]:
                data = response.json()
                if data.get("success"):
                    logger.info("✅ User registration successful")

                    # Test login
                    login_response = requests.post(
                        f"{self.backend_url}/api/auth/login",
                        json={
                            "email": test_user["email"],
                            "password": test_user["password"],
                        },
                        timeout=10,
                    )

                    if login_response.status_code in [200, 201]:
                        login_data = login_response.json()
                        if login_data.get("success") and login_data.get("user", {}).get(
                            "token"
                        ):
                            logger.info("✅ User login successful")
                            logger.info(
                                f"   Token: {login_data['user']['token'][:50]}..."
                            )
                            return True
                        else:
                            logger.error("❌ Login failed - no token received")
                            return False
                    else:
                        logger.error(f"❌ Login failed: {login_response.status_code}")
                        return False
                else:
                    logger.error(
                        f"❌ Registration failed: {data.get('message', 'Unknown error')}"
                    )
                    return False
            else:
                logger.error(f"❌ Registration failed: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Authentication test failed: {e}")
            return False

    def test_search_functionality(self) -> bool:
        """Test search functionality (requires OpenAI API key)"""
        logger.info("🔍 Testing search functionality...")

        try:
            response = requests.post(
                f"{self.backend_url}/semantic_search_meetings",
                json={"query": "test query", "limit": 5},
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                # Check if search returned results successfully
                if data.get("status") == "success" and "results" in data:
                    results_data = data["results"]
                    # Check if results contain actual data
                    if isinstance(results_data, dict) and "data" in results_data:
                        results_list = results_data["data"]
                        logger.info("✅ Search functionality working")
                        logger.info(f"   Results: {len(results_list)} items")
                        return True
                    else:
                        # Search returned success but no data (empty results)
                        logger.info("✅ Search functionality working (no data found)")
                        return True
                else:
                    error_msg = data.get("message", "Unknown error")
                    if "OpenAI API" in error_msg or "API key" in error_msg:
                        logger.warning(
                            "⚠️  Search requires OpenAI API key configuration"
                        )
                        logger.info(
                            "   See OPENAI_API_KEY_SETUP_GUIDE.md for setup instructions"
                        )
                    else:
                        logger.error(f"❌ Search failed: {error_msg}")
                    return False
            else:
                logger.error(f"❌ Search request failed: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Search test failed: {e}")
            return False

    def check_oauth_services(self) -> Dict[str, bool]:
        """Check status of OAuth services"""
        logger.info("🔄 Checking OAuth service status...")

        services_to_check = [
            "gmail",
            "outlook",
            "notion",
            "gdrive",
            "teams",
            "slack",
            "github",
            "dropbox",
            "trello",
            "asana",
        ]

        service_status = {}

        for service in services_to_check:
            try:
                response = requests.get(
                    f"{self.backend_url}/api/{service}/health", timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    oauth_configured = data.get("oauth_configured", False)
                    api_accessible = data.get("api_accessible", False)

                    service_status[service] = {
                        "healthy": status == "healthy",
                        "oauth_configured": oauth_configured,
                        "api_accessible": api_accessible,
                    }

                    status_icon = "✅" if status == "healthy" else "❌"
                    oauth_icon = "✅" if oauth_configured else "❌"
                    api_icon = "✅" if api_accessible else "❌"

                    logger.info(
                        f"   {service}: {status_icon} Health: {status}, {oauth_icon} OAuth: {oauth_configured}, {api_icon} API: {api_accessible}"
                    )

                else:
                    service_status[service] = {
                        "healthy": False,
                        "oauth_configured": False,
                        "api_accessible": False,
                    }
                    logger.warning(
                        f"   {service}: ❌ Health endpoint unavailable ({response.status_code})"
                    )

            except requests.exceptions.RequestException:
                service_status[service] = {
                    "healthy": False,
                    "oauth_configured": False,
                    "api_accessible": False,
                }
                logger.warning(f"   {service}: ❌ Connection failed")

        return service_status

    def generate_openai_config_guide(self) -> None:
        """Generate OpenAI API key configuration instructions"""
        logger.info("📝 Generating OpenAI API key configuration guide...")

        guide_content = """# OpenAI API Key Configuration

## Current Status
Search functionality requires a valid OpenAI API key. Current error: "Incorrect API key provided: mock_api_key"

## Setup Steps

1. **Get OpenAI API Key**
   - Visit: https://platform.openai.com/account/api-keys
   - Create new secret key
   - Copy the key (won't be shown again)

2. **Configure Environment**
   Add to your .env file:
   ```
   OPENAI_API_KEY=sk-your-actual-key-here
   ```

3. **Restart Backend**
   The backend will automatically pick up the new API key.

4. **Test Search**
   ```bash
   curl -X POST http://localhost:5058/semantic_search_meetings \\
     -H "Content-Type: application/json" \\
     -d '{"query": "test", "limit": 5}'
   ```

## Expected Response
```json
{
  "results": [...],
  "success": true
}
```

## Troubleshooting
- 401 Error: Invalid API key - verify key is correct
- 429 Error: Rate limit exceeded - check usage limits
- Check OpenAI status: https://status.openai.com
"""

        with open("OPENAI_API_KEY_QUICK_SETUP.md", "w") as f:
            f.write(guide_content)

        logger.info(
            "✅ OpenAI configuration guide created: OPENAI_API_KEY_QUICK_SETUP.md"
        )

    def generate_oauth_setup_checklist(self) -> None:
        """Generate OAuth service setup checklist"""
        logger.info("📋 Generating OAuth setup checklist...")

        checklist_content = """# OAuth Service Setup Checklist

## Priority Services (Require OAuth)
- [ ] Gmail - Client ID & Secret needed
- [ ] Outlook - Microsoft App registration needed
- [ ] Notion - Integration setup needed
- [ ] Google Drive - OAuth credentials needed
- [ ] Microsoft Teams - App registration needed

## Environment Variables Needed
```
# Gmail
GMAIL_CLIENT_ID=your-gmail-client-id
GMAIL_CLIENT_SECRET=your-gmail-client-secret

# Outlook
OUTLOOK_CLIENT_ID=your-outlook-client-id
OUTLOOK_CLIENT_SECRET=your-outlook-client-secret
OUTLOOK_TENANT_ID=common

# Notion
NOTION_CLIENT_ID=your-notion-client-id
NOTION_CLIENT_SECRET=your-notion-client-secret

# Google Drive
GDRIVE_CLIENT_ID=your-gdrive-client-id
GDRIVE_CLIENT_SECRET=your-gdrive-client-secret

# Microsoft Teams
TEAMS_CLIENT_ID=your-teams-client-id
TEAMS_CLIENT_SECRET=your-teams-client-secret
TEAMS_TENANT_ID=your-tenant-id
```

## Setup Instructions
1. Register applications in respective developer portals
2. Configure OAuth redirect URIs to: http://localhost:5058/api/{service}/oauth/callback
3. Add credentials to environment variables
4. Restart backend server
5. Test OAuth flow initiation

## Testing Commands
```bash
# Test OAuth initiation
curl http://localhost:5058/api/gmail/oauth/initiate

# Check service health
curl http://localhost:5058/api/gmail/health
```
"""

        with open("OAUTH_SETUP_CHECKLIST.md", "w") as f:
            f.write(checklist_content)

        logger.info("✅ OAuth setup checklist created: OAUTH_SETUP_CHECKLIST.md")

    def run_comprehensive_health_check(self) -> Dict[str, bool]:
        """Run comprehensive health check of all systems"""
        logger.info("🏥 Running comprehensive health check...")

        results = {
            "backend": self.check_backend_health(),
            "frontend": self.check_frontend_health(),
            "authentication": self.test_authentication_flow(),
            "search": self.test_search_functionality(),
        }

        # Add OAuth service status
        oauth_status = self.check_oauth_services()
        oauth_services_healthy = sum(
            1 for status in oauth_status.values() if status["healthy"]
        )
        results["oauth_services"] = oauth_services_healthy > 0

        # Calculate overall health
        healthy_components = sum(results.values())
        total_components = len(results)
        results["overall_health"] = healthy_components / total_components

        # Log summary
        logger.info("📊 Health Check Summary:")
        for component, healthy in results.items():
            status_icon = "✅" if healthy else "❌"
            logger.info(f"   {component}: {status_icon}")

        logger.info(f"   Overall Health: {results['overall_health'] * 100:.1f}%")

        return results

    def execute_search_configuration(self) -> bool:
        """Execute search configuration steps"""
        logger.info("🚀 Executing search configuration steps...")

        self.generate_openai_config_guide()

        # Check current search status
        search_working = self.test_search_functionality()

        if not search_working:
            logger.info("🔧 Search requires OpenAI API key configuration")
            logger.info(
                "   Please follow instructions in OPENAI_API_KEY_QUICK_SETUP.md"
            )
            return False
        else:
            logger.info("✅ Search functionality is working correctly")
            return True

    def execute_oauth_integration(self) -> bool:
        """Execute OAuth integration steps"""
        logger.info("🚀 Executing OAuth integration steps...")

        self.generate_oauth_setup_checklist()

        # Check current OAuth status
        oauth_status = self.check_oauth_services()

        # Count services that need OAuth configuration
        services_needing_oauth = [
            service
            for service, status in oauth_status.items()
            if not status["oauth_configured"]
        ]

        if services_needing_oauth:
            logger.info(
                f"🔧 {len(services_needing_oauth)} services need OAuth configuration:"
            )
            for service in services_needing_oauth:
                logger.info(f"   - {service}")
            logger.info("   Please follow instructions in OAUTH_SETUP_CHECKLIST.md")
            return False
        else:
            logger.info("✅ All OAuth services are configured correctly")
            return True

    def execute_frontend_testing(self) -> bool:
        """Execute frontend testing steps"""
        logger.info("🚀 Executing frontend testing steps...")

        # Check frontend health
        if not self.check_frontend_health():
            logger.error("❌ Frontend is not running")
            return False

        # Test authentication flow
        if not self.test_authentication_flow():
            logger.error("❌ Frontend authentication flow test failed")
            return False

        logger.info("✅ Frontend authentication is working correctly")
        return True

    def show_current_status(self) -> None:
        """Display current system status"""
        logger.info("📈 Current System Status")
        logger.info("=" * 50)

        # Backend status
        backend_healthy = self.check_backend_health()

        # Frontend status
        frontend_healthy = self.check_frontend_health()

        # Authentication status
        auth_working = self.test_authentication_flow()

        # Search status
        search_working = self.test_search_functionality()

        # OAuth status
        oauth_status = self.check_oauth_services()
        oauth_configured = sum(
            1 for status in oauth_status.values() if status["oauth_configured"]
        )

        logger.info("📊 Status Summary:")
        logger.info(
            f"   Backend: {'✅ Healthy' if backend_healthy else '❌ Unhealthy'}"
        )
        logger.info(
            f"   Frontend: {'✅ Running' if frontend_healthy else '❌ Not Running'}"
        )
        logger.info(
            f"   Authentication: {'✅ Working' if auth_working else '❌ Failed'}"
        )
        logger.info(
            f"   Search: {'✅ Working' if search_working else '❌ Needs OpenAI API Key'}"
        )
        logger.info(
            f"   OAuth Services: {oauth_configured}/{len(oauth_status)} configured"
        )

        # Next steps recommendations
        logger.info("\n🎯 Recommended Next Steps:")
        if not search_working:
            logger.info("   1. Configure OpenAI API key for search functionality")
        if oauth_configured < len(oauth_status):
            logger.info("   2. Set up OAuth for remaining services")
        if not auth_working:
            logger.info("   3. Fix authentication flow")
        if not backend_healthy:
            logger.info("   4. Restart backend server")
        if not frontend_healthy:
            logger.info("   5. Start frontend server")

        if all(
            [
                backend_healthy,
                frontend_healthy,
                auth_working,
                search_working,
                oauth_configured == len(oauth_status),
            ]
        ):
            logger.info(
                "   🎉 All systems are operational! No immediate actions needed."
            )


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print(__doc__)
        return

    step = sys.argv[1].lower()
    executor = AuthNextStepsExecutor()

    if step == "all":
        logger.info("🎯 Executing all next steps...")
        executor.execute_search_configuration()
        executor.execute_oauth_integration()
        executor.execute_frontend_testing()
        executor.run_comprehensive_health_check()

    elif step == "search":
        executor.execute_search_configuration()

    elif step == "oauth":
        executor.execute_oauth_integration()

    elif step == "frontend":
        executor.execute_frontend_testing()

    elif step == "status":
        executor.show_current_status()

    elif step == "health":
        executor.run_comprehensive_health_check()

    else:
        print(f"Unknown step: {step}")
        print(__doc__)


if __name__ == "__main__":
    main()
