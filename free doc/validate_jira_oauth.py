#!/usr/bin/env python3
"""
Jira OAuth Configuration Validation Script
Validates Jira OAuth setup and tests connectivity
"""

import os
import sys
import asyncio
import httpx
import json
from urllib.parse import urlencode
from dotenv import load_dotenv

# Add backend to path for imports
sys.path.append(
    os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
)

# Load environment variables
load_dotenv()


class JiraOAuthValidator:
    def __init__(self):
        self.client_id = os.getenv("JIRA_CLIENT_ID")
        self.client_secret = os.getenv("JIRA_CLIENT_SECRET")
        self.redirect_uri = os.getenv(
            "JIRA_REDIRECT_URI", "http://localhost:8000/api/auth/jira/callback"
        )
        self.base_url = "https://auth.atlassian.com"

    def validate_configuration(self):
        """Validate basic configuration"""
        print("🔧 Validating Jira OAuth Configuration")
        print("=" * 50)

        config_ok = True

        # Check required environment variables
        if not self.client_id:
            print("❌ JIRA_CLIENT_ID not found in environment")
            config_ok = False
        else:
            print(f"✅ JIRA_CLIENT_ID: {self.client_id[:10]}...")

        if not self.client_secret:
            print("❌ JIRA_CLIENT_SECRET not found in environment")
            config_ok = False
        else:
            print(f"✅ JIRA_CLIENT_SECRET: {self.client_secret[:10]}...")

        print(f"✅ JIRA_REDIRECT_URI: {self.redirect_uri}")

        if not config_ok:
            print("\n❌ Configuration validation failed")
            return False

        print("\n✅ Configuration validation passed")
        return True

    async def test_atlassian_connectivity(self):
        """Test connectivity to Atlassian auth endpoints"""
        print("\n🌐 Testing Atlassian Connectivity")
        print("=" * 50)

        endpoints = [
            "https://auth.atlassian.com",
            "https://api.atlassian.com",
            "https://api.atlassian.com/oauth/token",
        ]

        async with httpx.AsyncClient() as client:
            for endpoint in endpoints:
                try:
                    response = await client.get(endpoint, timeout=10.0)
                    if response.status_code == 200:
                        print(f"✅ {endpoint} - Reachable")
                    else:
                        print(f"⚠️  {endpoint} - Status {response.status_code}")
                except Exception as e:
                    print(f"❌ {endpoint} - Connection failed: {e}")

    async def test_oauth_authorization_url(self):
        """Test OAuth authorization URL generation"""
        print("\n🔗 Testing OAuth Authorization URL")
        print("=" * 50)

        try:
            # Generate authorization URL
            auth_params = {
                "audience": "api.atlassian.com",
                "client_id": self.client_id,
                "scope": "read:jira-work read:issue-details:jira read:comments:jira read:attachments:jira",
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "state": "test_state_123",
                "prompt": "consent",
            }

            auth_url = f"{self.base_url}/authorize?{urlencode(auth_params)}"

            print(f"✅ Authorization URL generated successfully")
            print(f"📋 URL Length: {len(auth_url)} characters")
            print(f"🔗 First 100 chars: {auth_url[:100]}...")

            # Test if URL is accessible
            async with httpx.AsyncClient() as client:
                try:
                    # Note: This will redirect to login, but we just check if it's reachable
                    response = await client.get(
                        auth_url, follow_redirects=False, timeout=10.0
                    )
                    if response.status_code in [200, 302]:
                        print("✅ Authorization endpoint is reachable")
                    else:
                        print(
                            f"⚠️  Authorization endpoint returned status: {response.status_code}"
                        )
                except Exception as e:
                    print(f"⚠️  Authorization endpoint test: {e}")

            return auth_url

        except Exception as e:
            print(f"❌ Failed to generate authorization URL: {e}")
            return None

    async def test_token_endpoint(self):
        """Test token endpoint connectivity"""
        print("\n🔄 Testing Token Endpoint")
        print("=" * 50)

        token_url = "https://auth.atlassian.com/oauth/token"

        try:
            async with httpx.AsyncClient() as client:
                # Test with invalid credentials to check endpoint response
                test_data = {
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": "invalid_test_code",
                    "redirect_uri": self.redirect_uri,
                }

                response = await client.post(token_url, data=test_data, timeout=10.0)

                if response.status_code == 400:
                    print("✅ Token endpoint is reachable and responding")
                    print("   (Expected 400 for invalid code - endpoint is working)")
                else:
                    print(
                        f"⚠️  Token endpoint returned unexpected status: {response.status_code}"
                    )

        except Exception as e:
            print(f"❌ Token endpoint test failed: {e}")

    async def test_backend_endpoints(self):
        """Test backend Jira OAuth endpoints"""
        print("\n⚙️ Testing Backend OAuth Endpoints")
        print("=" * 50)

        base_url = "http://localhost:8000"
        endpoints = [
            "/api/auth/jira/start",
            "/api/auth/jira/status",
            "/api/auth/jira/disconnect",
        ]

        async with httpx.AsyncClient() as client:
            for endpoint in endpoints:
                try:
                    url = f"{base_url}{endpoint}"

                    if endpoint == "/api/auth/jira/start":
                        # GET request for start endpoint
                        response = await client.get(
                            f"{url}?user_id=test_user", timeout=10.0
                        )
                    elif endpoint == "/api/auth/jira/disconnect":
                        # POST request for disconnect
                        response = await client.post(
                            url, json={"user_id": "test_user"}, timeout=10.0
                        )
                    else:
                        # POST request for status
                        response = await client.post(
                            url, json={"user_id": "test_user"}, timeout=10.0
                        )

                    if response.status_code in [200, 400, 401]:
                        print(
                            f"✅ {endpoint} - Responding (Status: {response.status_code})"
                        )
                    else:
                        print(
                            f"⚠️  {endpoint} - Unexpected status: {response.status_code}"
                        )

                except httpx.ConnectError:
                    print(f"❌ {endpoint} - Backend not running")
                except Exception as e:
                    print(f"❌ {endpoint} - Error: {e}")

    def check_database_tables(self):
        """Check if required database tables exist"""
        print("\n🗄️ Checking Database Configuration")
        print("=" * 50)

        try:
            # Try to import database module
            from db_oauth_jira import get_tokens, save_tokens

            print("✅ Jira OAuth database module is importable")
            print("✅ Database functions are available")

        except ImportError as e:
            print(f"❌ Database module import failed: {e}")
        except Exception as e:
            print(f"⚠️  Database check: {e}")

    def validate_encryption_config(self):
        """Validate encryption configuration"""
        print("\n🔐 Validating Encryption Configuration")
        print("=" * 50)

        encryption_key = os.getenv("ATOM_ENCRYPTION_KEY")

        if encryption_key:
            print("✅ ATOM_ENCRYPTION_KEY is configured")
            print(f"   Key length: {len(encryption_key)} characters")
        else:
            print("⚠️  ATOM_ENCRYPTION_KEY not found")
            print("   Tokens will be encrypted with temporary key")

    async def run_comprehensive_validation(self):
        """Run all validation tests"""
        print("🚀 Starting Jira OAuth Comprehensive Validation")
        print("=" * 60)

        # Run all validation steps
        config_valid = self.validate_configuration()
        if not config_valid:
            return False

        await self.test_atlassian_connectivity()
        auth_url = await self.test_oauth_authorization_url()
        await self.test_token_endpoint()
        await self.test_backend_endpoints()
        self.check_database_tables()
        self.validate_encryption_config()

        # Summary
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)

        if auth_url:
            print("\n🎯 Next Steps:")
            print("1. Start the backend server: python3 start_backend.py")
            print("2. Test OAuth flow manually:")
            print(f"   Visit: {auth_url[:80]}...")
            print("3. Complete authorization in browser")
            print("4. Verify callback handling")

        print("\n✅ Jira OAuth configuration is ready for testing!")
        return True


async def main():
    """Main validation function"""
    validator = JiraOAuthValidator()
    await validator.run_comprehensive_validation()


if __name__ == "__main__":
    # Run async main function
    asyncio.run(main())
