#!/usr/bin/env python3
"""
ATOM Platform - OAuth Setup and Configuration Script
Complete OAuth setup for production deployment
"""

import os
import sys
import json
import requests
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class OAuthSetup:
    """OAuth setup and configuration manager"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.oauth_server_url = "http://localhost:5058"
        self.backend_url = "http://localhost:8000"

        # OAuth service configuration
        self.services = {
            "github": {
                "name": "GitHub",
                "setup_url": "https://github.com/settings/applications/new",
                "callback_url": f"{self.oauth_server_url}/api/auth/github/callback",
                "scopes": ["repo", "user:email", "read:org"],
                "required": True,
                "env_vars": ["GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"],
                "setup_instructions": """
1. Go to GitHub Settings → Developer settings → OAuth Apps
2. Click "New OAuth App"
3. Application name: "ATOM Platform"
4. Homepage URL: http://localhost:3000 (or your domain)
5. Authorization callback URL: {callback_url}
6. Click "Register application"
7. Copy Client ID and Client Secret
                """.strip(),
            },
            "google": {
                "name": "Google",
                "setup_url": "https://console.developers.google.com/apis/credentials",
                "callback_url": f"{self.oauth_server_url}/api/auth/google/callback",
                "scopes": [
                    "email",
                    "profile",
                    "https://www.googleapis.com/auth/calendar",
                    "https://www.googleapis.com/auth/gmail.readonly",
                    "https://www.googleapis.com/auth/drive",
                ],
                "required": True,
                "env_vars": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
                "setup_instructions": """
1. Go to Google Cloud Console
2. Create a new project or select existing
3. Enable APIs: Calendar, Gmail, Drive
4. Go to Credentials → Create Credentials → OAuth 2.0 Client IDs
5. Application type: Web application
6. Name: "ATOM Platform"
7. Authorized redirect URIs: {callback_url}
8. Click "Create"
9. Copy Client ID and Client Secret
                """.strip(),
            },
            "slack": {
                "name": "Slack",
                "setup_url": "https://api.slack.com/apps",
                "callback_url": f"{self.oauth_server_url}/api/auth/slack/callback",
                "scopes": ["chat:write", "channels:read", "groups:read", "users:read"],
                "required": True,
                "env_vars": ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"],
                "setup_instructions": """
1. Go to Slack API: Create New App
2. Choose "From scratch"
3. App name: "ATOM Platform", Workspace: your workspace
4. Go to OAuth & Permissions
5. Add Redirect URLs: {callback_url}
6. Add Bot Token Scopes: chat:write, channels:read, groups:read, users:read
7. Install app to workspace
8. Copy OAuth Credentials: Client ID and Client Secret
                """.strip(),
            },
            "dropbox": {
                "name": "Dropbox",
                "setup_url": "https://www.dropbox.com/developers/apps",
                "callback_url": f"{self.oauth_server_url}/api/auth/dropbox/callback",
                "scopes": [
                    "files.metadata.read",
                    "files.content.read",
                    "files.content.write",
                ],
                "required": False,
                "env_vars": ["DROPBOX_CLIENT_ID", "DROPBOX_CLIENT_SECRET"],
                "setup_instructions": """
1. Go to Dropbox Developer Console
2. Create app → Scoped access
3. Choose access: App folder or Full Dropbox
4. App name: "ATOM Platform"
5. Go to Permissions tab, enable: files.metadata.read, files.content.read, files.content.write
6. Go to Settings tab
7. OAuth 2 → Redirect URIs: {callback_url}
8. Copy App key (Client ID) and App secret (Client Secret)
                """.strip(),
            },
            "trello": {
                "name": "Trello",
                "setup_url": "https://trello.com/power-ups/admin",
                "callback_url": f"{self.oauth_server_url}/api/auth/trello/callback",
                "scopes": ["read", "write"],
                "required": False,
                "env_vars": ["TRELLO_CLIENT_ID", "TRELLO_CLIENT_SECRET"],
                "setup_instructions": """
1. Go to Trello Developer API Keys
2. Click "Generate a new API key"
3. Application name: "ATOM Platform"
4. Description: "Workflow automation platform"
5. Accept terms and generate
6. Copy API Key (Client ID)
7. To get Secret: Click "Token" next to your API key
8. Generate a new token with read, write permissions
9. Copy Token (Client Secret)
                """.strip(),
            },
        }

    def check_current_status(self) -> Dict:
        """Check current OAuth configuration status"""
        print("🔍 Checking current OAuth status...")

        status = {}
        try:
            response = requests.get(
                f"{self.oauth_server_url}/api/auth/services", timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                status["total_services"] = data.get("total_services", 0)
                status["configured_services"] = data.get(
                    "services_with_real_credentials", 0
                )
                status["needs_credentials"] = data.get(
                    "services_needing_credentials", 0
                )

                # Check individual service status
                for service in self.services.keys():
                    try:
                        service_response = requests.get(
                            f"{self.oauth_server_url}/api/auth/{service}/status",
                            timeout=5,
                        )
                        if service_response.status_code == 200:
                            service_data = service_response.json()
                            status[service] = {
                                "configured": service_data.get("status")
                                == "configured",
                                "client_id": service_data.get("client_id", ""),
                                "message": service_data.get("message", ""),
                            }
                    except:
                        status[service] = {
                            "configured": False,
                            "error": "Service not reachable",
                        }
            else:
                print("   ❌ OAuth server not responding")
        except Exception as e:
            print(f"   ❌ Error checking OAuth status: {e}")

        return status

    def print_status_report(self):
        """Print comprehensive OAuth status report"""
        print("\n" + "=" * 60)
        print("📊 ATOM PLATFORM - OAUTH CONFIGURATION STATUS")
        print("=" * 60)

        status = self.check_current_status()

        if not status:
            print("❌ Could not retrieve OAuth status")
            return

        print(f"\n📋 OVERVIEW:")
        print(f"   Total Services: {status.get('total_services', 0)}")
        print(f"   Configured: {status.get('configured_services', 0)}")
        print(f"   Needs Credentials: {status.get('needs_credentials', 0)}")

        print(f"\n🔧 SERVICE STATUS:")
        for service_name, service_config in self.services.items():
            service_status = status.get(service_name, {})
            if service_status.get("configured"):
                print(f"   ✅ {service_config['name']:12} - Configured")
            else:
                requirement = "REQUIRED" if service_config["required"] else "Optional"
                print(
                    f"   ❌ {service_config['name']:12} - Not configured ({requirement})"
                )

    def setup_service(self, service_name: str) -> bool:
        """Setup a specific OAuth service"""
        if service_name not in self.services:
            print(f"❌ Unknown service: {service_name}")
            return False

        service_config = self.services[service_name]

        print(f"\n🔐 Setting up {service_config['name']} OAuth...")
        print("=" * 50)

        # Show setup instructions
        instructions = service_config["setup_instructions"].format(
            callback_url=service_config["callback_url"]
        )
        print(f"\n📚 SETUP INSTRUCTIONS:\n{instructions}")

        # Open setup URL in browser
        print(f"\n🌐 Opening setup page in browser...")
        try:
            webbrowser.open(service_config["setup_url"])
        except:
            print(
                f"   ⚠️  Could not open browser. Please visit: {service_config['setup_url']}"
            )

        # Get credentials from user
        print(f"\n🔑 Please enter your {service_config['name']} credentials:")
        client_id = input(f"   Client ID: ").strip()
        client_secret = input(f"   Client Secret: ").strip()

        if not client_id or not client_secret:
            print("   ❌ Credentials cannot be empty")
            return False

        # Update environment
        env_updated = self._update_environment(service_name, client_id, client_secret)

        if env_updated:
            print(f"   ✅ {service_config['name']} credentials saved")
            print(f"   🔄 Please restart the OAuth server to apply changes")
            return True
        else:
            print(f"   ❌ Failed to save credentials")
            return False

    def _update_environment(
        self, service_name: str, client_id: str, client_secret: str
    ) -> bool:
        """Update environment variables with OAuth credentials"""
        env_vars = self.services[service_name]["env_vars"]

        # Try to update .env file
        env_files = [".env", "real_credentials.env", ".env.production"]

        for env_file in env_files:
            file_path = self.base_dir / env_file
            if file_path.exists():
                return self._update_env_file(
                    file_path, env_vars[0], client_id, env_vars[1], client_secret
                )

        # Create new .env file if none exists
        default_env = self.base_dir / ".env"
        return self._update_env_file(
            default_env, env_vars[0], client_id, env_vars[1], client_secret
        )

    def _update_env_file(
        self,
        file_path: Path,
        client_id_var: str,
        client_id: str,
        client_secret_var: str,
        client_secret: str,
    ) -> bool:
        """Update or create environment file"""
        try:
            if file_path.exists():
                # Read existing content
                content = file_path.read_text()
                lines = content.split("\n")

                # Update existing variables or add new ones
                updated_lines = []
                client_id_found = False
                client_secret_found = False

                for line in lines:
                    if line.startswith(f"{client_id_var}="):
                        updated_lines.append(f"{client_id_var}={client_id}")
                        client_id_found = True
                    elif line.startswith(f"{client_secret_var}="):
                        updated_lines.append(f"{client_secret_var}={client_secret}")
                        client_secret_found = True
                    else:
                        updated_lines.append(line)

                # Add missing variables
                if not client_id_found:
                    updated_lines.append(f"{client_id_var}={client_id}")
                if not client_secret_found:
                    updated_lines.append(f"{client_secret_var}={client_secret}")

                content = "\n".join(updated_lines)
            else:
                # Create new file
                content = f"""# ATOM Platform - OAuth Configuration
{client_id_var}={client_id}
{client_secret_var}={client_secret}
"""

            file_path.write_text(content)
            print(f"   ✅ Updated: {file_path.name}")
            return True

        except Exception as e:
            print(f"   ❌ Error updating {file_path}: {e}")
            return False

    def test_oauth_flow(self, service_name: str) -> bool:
        """Test OAuth flow for a service"""
        if service_name not in self.services:
            print(f"❌ Unknown service: {service_name}")
            return False

        print(f"\n🧪 Testing {self.services[service_name]['name']} OAuth flow...")

        try:
            # Check service status
            response = requests.get(
                f"{self.oauth_server_url}/api/auth/{service_name}/status", timeout=10
            )

            if response.status_code != 200:
                print(f"   ❌ Service status check failed: {response.status_code}")
                return False

            service_data = response.json()

            if service_data.get("status") != "configured":
                print(f"   ❌ Service not configured: {service_data.get('message')}")
                return False

            # Try to generate authorization URL
            auth_response = requests.get(
                f"{self.oauth_server_url}/api/auth/{service_name}/authorize",
                params={"user_id": "test_user"},
                timeout=10,
            )

            if auth_response.status_code == 200:
                auth_data = auth_response.json()
                if auth_data.get("credentials") == "real":
                    print(f"   ✅ OAuth flow working - Authorization URL generated")
                    print(f"   🔗 Auth URL: {auth_data.get('auth_url')}")
                    return True
                else:
                    print(f"   ❌ Using placeholder credentials")
                    return False
            else:
                print(f"   ❌ Authorization failed: {auth_response.status_code}")
                return False

        except Exception as e:
            print(f"   ❌ OAuth test failed: {e}")
            return False

    def setup_all_required(self) -> bool:
        """Setup all required OAuth services"""
        print("\n🚀 Setting up all required OAuth services...")

        required_services = [
            name for name, config in self.services.items() if config["required"]
        ]
        success_count = 0

        for service_name in required_services:
            if self.setup_service(service_name):
                success_count += 1
            else:
                print(f"   ⚠️  Failed to setup {service_name}")

        print(
            f"\n📊 Setup completed: {success_count}/{len(required_services)} required services configured"
        )
        return success_count == len(required_services)

    def generate_setup_guide(self):
        """Generate comprehensive setup guide"""
        guide_file = self.base_dir / "OAUTH_SETUP_GUIDE.md"

        guide_content = f"""# ATOM Platform - OAuth Setup Guide

## Overview
This guide will help you configure OAuth integrations for the ATOM Platform.

## Prerequisites
- Running ATOM Platform services
- Admin access to the services you want to integrate

## Service Configuration

"""

        for service_name, service_config in self.services.items():
            requirement = "**REQUIRED**" if service_config["required"] else "Optional"
            instructions = service_config["setup_instructions"].format(
                callback_url=service_config["callback_url"]
            )

            guide_content += f"""### {service_config["name"]} ({requirement})

{instructions}

**Environment Variables:**
- `{service_config["env_vars"][0]}` = Your Client ID
- `{service_config["env_vars"][1]}` = Your Client Secret

**Callback URL:** `{service_config["callback_url"]}`

---

"""

        guide_content += """
## Verification Steps

1. **Check Current Status:**
   ```bash
   python setup_oauth.py --status
   ```

2. **Setup Individual Service:**
   ```bash
   python setup_oauth.py --setup github
   ```

3. **Setup All Required Services:**
   ```bash
   python setup_oauth.py --setup-all
   ```

4. **Test OAuth Flow:**
   ```bash
   python setup_oauth.py --test github
   ```

## Troubleshooting

### Common Issues

1. **"Service not configured"**
   - Check that environment variables are set
   - Restart OAuth server after setting variables

2. **"Invalid redirect URI"**
   - Ensure callback URL matches exactly
   - Include http:// or https:// prefix

3. **"Invalid client credentials"**
   - Verify Client ID and Client Secret
   - Check for typos or extra spaces

### Support
For additional help, check the ATOM Platform documentation or contact support.
"""

        guide_file.write_text(guide_content)
        print(f"✅ Setup guide generated: {guide_file.name}")

    def run_interactive_setup(self):
        """Run interactive OAuth setup"""
        print("🚀 ATOM Platform - Interactive OAuth Setup")
        print("=" * 50)

        while True:
            print("\n📋 OPTIONS:")
            print("1. Check OAuth status")
            print("2. Setup specific service")
            print("3. Setup all required services")
            print("4. Test OAuth flow")
            print("5. Generate setup guide")
            print("6. Exit")

            choice = input("\nEnter your choice (1-6): ").strip()

            if choice == "1":
                self.print_status_report()
            elif choice == "2":
                print("\nAvailable services:")
                for i, (name, config) in enumerate(self.services.items(), 1):
                    requirement = "REQUIRED" if config["required"] else "Optional"
                    print(f"   {i}. {config['name']} ({requirement})")

                service_choice = input("\nEnter service number or name: ").strip()
                if service_choice.isdigit():
                    service_index = int(service_choice) - 1
                    service_names = list(self.services.keys())
                    if 0 <= service_index < len(service_names):
                        self.setup_service(service_names[service_index])
                    else:
                        print("❌ Invalid service number")
                else:
                    self.setup_service(service_choice.lower())
            elif choice == "3":
                self.setup_all_required()
            elif choice == "4":
                service_name = input("Enter service name to test: ").strip().lower()
                self.test_oauth_flow(service_name)
            elif choice == "5":
                self.generate_setup_guide()
            elif choice == "6":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1-6.")

    def run_cli_setup(self, args):
        """Run CLI-based setup"""
        if "--status" in args:
            self.print_status_report()
        elif "--setup" in args:
            if len(args) > 2:
                self.setup_service(args[2])
            else:
                print("❌ Please specify service: --setup [service_name]")
        elif "--setup-all" in args:
            self.setup_all_required()
        elif "--test" in args:
            if len(args) > 2:
                self.test_oauth_flow(args[2])
            else:
                print("❌ Please specify service: --test [service_name]")
        elif "--guide" in args:
            self.generate_setup_guide()
        else:
            print("Usage: python setup_oauth.py [OPTION]")
            print("Options:")
            print("  --status      Check OAuth configuration status")
            print("  --setup SERVICE  Setup specific OAuth service")
            print("  --setup-all   Setup all required OAuth services")
            print("  --test SERVICE   Test OAuth flow for service")
            print("  --guide       Generate setup guide")
            print("  --interactive Run interactive setup")


def main():
    """Main function"""
    setup = OAuthSetup()

    if len(sys.argv) > 1:
        setup.run_cli_setup(sys.argv)
    else:
        setup.run_interactive_setup()


if __name__ == "__main__":
    main()
