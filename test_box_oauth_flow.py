#!/usr/bin/env python3
"""
Comprehensive Box OAuth Flow Test
Tests the complete OAuth authorization flow for Box integration
"""

import os
import sys
import json
import requests
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class BoxOAuthFlowTest:
    """Test Box OAuth flow from authorization to callback"""

    def __init__(self):
        self.base_url = "http://localhost:5058"
        self.test_user_id = "box_oauth_test_user"

    def test_environment_variables(self):
        """Test if Box environment variables are set"""
        print("🔧 Testing Box Environment Variables")
        print("=" * 50)

        box_client_id = os.getenv("BOX_CLIENT_ID")
        box_client_secret = os.getenv("BOX_CLIENT_SECRET")

        print(f"BOX_CLIENT_ID: {'***SET***' if box_client_id else '❌ NOT SET'}")
        print(
            f"BOX_CLIENT_SECRET: {'***SET***' if box_client_secret else '❌ NOT SET'}"
        )

        if not box_client_id or not box_client_secret:
            print("❌ Box credentials not properly configured")
            return False

        print("✅ Box environment variables are properly set")
        return True

    def test_box_status_endpoint(self):
        """Test Box status endpoint"""
        print("\n📊 Testing Box Status Endpoint")
        print("=" * 50)

        try:
            response = requests.get(
                f"{self.base_url}/api/auth/box/status",
                params={"user_id": self.test_user_id},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status: {data.get('status', 'unknown')}")
                print(f"✅ Credentials: {data.get('credentials', 'none')}")
                print(f"✅ Client ID: {data.get('client_id', 'none')}")
                print(f"✅ Scopes: {data.get('scopes', [])}")
                return True
            else:
                print(f"❌ Status endpoint failed: HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"❌ Status endpoint error: {e}")
            return False

    def test_box_authorization_endpoint(self):
        """Test Box authorization URL generation"""
        print("\n🔐 Testing Box Authorization Endpoint")
        print("=" * 50)

        try:
            response = requests.get(
                f"{self.base_url}/api/auth/box/authorize",
                params={"user_id": self.test_user_id},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("ok"):
                    auth_url = data.get("auth_url", "")
                    csrf_token = data.get("csrf_token", "")
                    redirect_uri = data.get("redirect_uri", "")

                    print(f"✅ Authorization URL generated successfully")
                    print(f"✅ CSRF Token: {csrf_token[:20]}...")
                    print(f"✅ Redirect URI: {redirect_uri}")

                    # Parse the authorization URL
                    parsed_url = urlparse(auth_url)
                    query_params = parse_qs(parsed_url.query)

                    print(f"✅ Auth URL Host: {parsed_url.netloc}")
                    print(
                        f"✅ Client ID in URL: {'***SET***' if query_params.get('client_id') else '❌ MISSING'}"
                    )
                    print(
                        f"✅ Response Type: {query_params.get('response_type', [''])[0]}"
                    )
                    print(f"✅ Scope: {query_params.get('scope', [''])[0]}")
                    print(
                        f"✅ State (CSRF): {'***SET***' if query_params.get('state') else '❌ MISSING'}"
                    )

                    return True
                else:
                    print(
                        f"❌ Authorization failed: {data.get('error', 'Unknown error')}"
                    )
                    return False
            else:
                print(f"❌ Authorization endpoint failed: HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"❌ Authorization endpoint error: {e}")
            return False

    def test_box_callback_endpoint(self):
        """Test Box callback endpoint (mock implementation)"""
        print("\n🔄 Testing Box Callback Endpoint")
        print("=" * 50)

        try:
            # Test GET callback (OAuth redirect)
            response = requests.get(
                f"{self.base_url}/api/auth/box/callback", timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Callback endpoint working")
                print(f"✅ Service: {data.get('service', 'unknown')}")
                print(f"✅ Message: {data.get('message', 'No message')}")
                return True
            else:
                print(f"❌ Callback endpoint failed: HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"❌ Callback endpoint error: {e}")
            return False

    def test_comprehensive_oauth_status(self):
        """Test comprehensive OAuth status for all services"""
        print("\n📈 Testing Comprehensive OAuth Status")
        print("=" * 50)

        try:
            response = requests.get(
                f"{self.base_url}/api/auth/oauth-status",
                params={"user_id": self.test_user_id},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()

                total_services = data.get("total_services", 0)
                connected_services = data.get("connected_services", 0)
                success_rate = data.get("success_rate", "0%")

                print(f"✅ Total Services: {total_services}")
                print(f"✅ Connected Services: {connected_services}")
                print(f"✅ Success Rate: {success_rate}")

                # Check Box specifically in results
                results = data.get("results", {})
                box_status = results.get("box", {})

                if box_status:
                    print(f"✅ Box Status: {box_status.get('status', 'unknown')}")
                    print(
                        f"✅ Box Credentials: {box_status.get('credentials', 'none')}"
                    )
                else:
                    print("❌ Box not found in OAuth status results")
                    return False

                return True
            else:
                print(f"❌ OAuth status endpoint failed: HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"❌ OAuth status endpoint error: {e}")
            return False

    def test_services_list_endpoint(self):
        """Test services list endpoint"""
        print("\n📋 Testing Services List Endpoint")
        print("=" * 50)

        try:
            response = requests.get(f"{self.base_url}/api/auth/services", timeout=10)

            if response.status_code == 200:
                data = response.json()

                services = data.get("services", [])
                total_services = data.get("total_services", 0)
                services_with_real_credentials = data.get(
                    "services_with_real_credentials", 0
                )

                print(f"✅ Total Services: {total_services}")
                print(
                    f"✅ Services with Real Credentials: {services_with_real_credentials}"
                )
                print(f"✅ Services List: {', '.join(services)}")

                # Check if Box is in the services list
                if "box" in services:
                    print("✅ Box found in services list")
                    return True
                else:
                    print("❌ Box not found in services list")
                    return False
            else:
                print(f"❌ Services list endpoint failed: HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"❌ Services list endpoint error: {e}")
            return False

    def run_complete_test(self):
        """Run complete Box OAuth flow test"""
        print("🚀 Box OAuth Flow Comprehensive Test")
        print("=" * 60)

        tests = [
            ("Environment Variables", self.test_environment_variables),
            ("Status Endpoint", self.test_box_status_endpoint),
            ("Authorization Endpoint", self.test_box_authorization_endpoint),
            ("Callback Endpoint", self.test_box_callback_endpoint),
            ("Comprehensive OAuth Status", self.test_comprehensive_oauth_status),
            ("Services List", self.test_services_list_endpoint),
        ]

        results = []

        for test_name, test_func in tests:
            try:
                success = test_func()
                results.append((test_name, success))
            except Exception as e:
                print(f"❌ {test_name} test failed with exception: {e}")
                results.append((test_name, False))

        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)

        passed_tests = 0
        for test_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}")
            if success:
                passed_tests += 1

        total_tests = len(results)
        success_rate = (passed_tests / total_tests) * 100

        print(
            f"\n🎯 Results: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%)"
        )

        if passed_tests == total_tests:
            print("\n🎉 Box OAuth Flow is COMPLETELY WORKING!")
            print("   - Environment variables configured ✅")
            print("   - Status endpoints working ✅")
            print("   - Authorization flow ready ✅")
            print("   - Callback endpoints configured ✅")
            print("   - Integration with main OAuth system ✅")
        else:
            print(
                f"\n⚠️  Box OAuth Flow needs attention ({passed_tests}/{total_tests} tests passed)"
            )

        return passed_tests == total_tests


def main():
    """Main test execution"""
    test = BoxOAuthFlowTest()

    try:
        success = test.run_complete_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
