import os
import sys
import requests
import json
from dotenv import load_dotenv


def test_box_environment():
    """Test if Box environment variables are set"""
    print("=== Box Environment Variables Test ===")

    # Load environment variables from .env file
    load_dotenv()

    box_client_id = os.getenv("BOX_CLIENT_ID")
    box_client_secret = os.getenv("BOX_CLIENT_SECRET")

    print(f"BOX_CLIENT_ID: {'***SET***' if box_client_id else 'NOT SET'}")
    print(f"BOX_CLIENT_SECRET: {'***SET***' if box_client_secret else 'NOT SET'}")

    if not box_client_id or not box_client_secret:
        print("❌ Box credentials are not properly set in environment")
        return False

    print("✅ Box environment variables are set")
    return True


def test_box_auth_handler():
    """Test if Box auth handler can be imported and configured"""
    print("\n=== Box Auth Handler Test ===")

    try:
        # Add the backend path to Python path
        sys.path.append("backend/python-api-service")

        # Load environment variables first
        load_dotenv()

        # Try to import the Box auth handler
        from auth_handler_box import BOX_CLIENT_ID, BOX_CLIENT_SECRET, box_auth_bp

        print(
            f"BOX_CLIENT_ID in handler: {'***SET***' if BOX_CLIENT_ID else 'NOT SET'}"
        )
        print(
            f"BOX_CLIENT_SECRET in handler: {'***SET***' if BOX_CLIENT_SECRET else 'NOT SET'}"
        )

        if BOX_CLIENT_ID and BOX_CLIENT_SECRET:
            print("✅ Box auth handler is properly configured")
            return True
        else:
            print("❌ Box auth handler credentials not loaded")
            return False

    except ImportError as e:
        print(f"❌ Failed to import Box auth handler: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing Box auth handler: {e}")
        return False


def test_box_sdk_availability():
    """Test if Box SDK is available"""
    print("\n=== Box SDK Availability Test ===")

    try:
        import boxsdk

        print("✅ Box SDK is installed")
        print(
            f"  Version: {boxsdk.__version__ if hasattr(boxsdk, '__version__') else 'Unknown'}"
        )
        return True
    except ImportError:
        print("❌ Box SDK is not installed")
        print("  Install with: pip install boxsdk")
        return False


def test_box_oauth_endpoints():
    """Test Box OAuth endpoints (if server is running)"""
    print("\n=== Box OAuth Endpoints Test ===")

    base_url = "http://localhost:5058"
    test_user_id = "test_user_123"

    endpoints_to_test = [
        f"/api/auth/box/initiate?user_id={test_user_id}",
        "/api/auth/box/status",
        "/api/auth/box/health",
    ]

    for endpoint in endpoints_to_test:
        url = base_url + endpoint
        try:
            response = requests.get(url, timeout=5)
            print(f"{endpoint}: HTTP {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Response: {json.dumps(data, indent=2)[:100]}...")
            else:
                print(f"  ⚠️  Non-200 response")

        except requests.exceptions.ConnectionError:
            print(f"{endpoint}: ❌ Connection failed (server may not be running)")
        except requests.exceptions.Timeout:
            print(f"{endpoint}: ❌ Request timeout")
        except Exception as e:
            print(f"{endpoint}: ❌ Error: {e}")


def test_box_oauth_flow_simulation():
    """Simulate Box OAuth flow without making actual API calls"""
    print("\n=== Box OAuth Flow Simulation ===")

    load_dotenv()

    box_client_id = os.getenv("BOX_CLIENT_ID")
    box_client_secret = os.getenv("BOX_CLIENT_SECRET")

    if not box_client_id or not box_client_secret:
        print("❌ Cannot simulate OAuth flow - credentials missing")
        return False

    # Test OAuth URL construction
    try:
        from urllib.parse import urlencode

        auth_params = {
            "response_type": "code",
            "client_id": box_client_id,
            "redirect_uri": "http://localhost:5058/api/auth/box/callback",
            "state": "test_state_123",
        }

        auth_url = (
            f"https://account.box.com/api/oauth2/authorize?{urlencode(auth_params)}"
        )
        print(f"✅ OAuth URL constructed successfully")
        print(f"  Client ID: {box_client_id[:10]}...")
        print(f"  Redirect URI: {auth_params['redirect_uri']}")
        print(f"  Auth URL length: {len(auth_url)} characters")

        return True

    except Exception as e:
        print(f"❌ Error simulating OAuth flow: {e}")
        return False


def main():
    """Run all Box integration tests"""
    print("🔧 Box Integration Test Suite")
    print("=" * 50)

    # Test environment variables
    env_ok = test_box_environment()

    # Test Box SDK
    sdk_ok = test_box_sdk_availability()

    # Test auth handler
    handler_ok = test_box_auth_handler()

    # Test OAuth flow simulation
    oauth_sim_ok = test_box_oauth_flow_simulation()

    # Test OAuth endpoints (if server running)
    test_box_oauth_endpoints()

    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")

    if env_ok and sdk_ok and handler_ok and oauth_sim_ok:
        print("✅ Box integration is properly configured")
        print("\n🎯 Next steps:")
        print("1. Start the OAuth server: python start_complete_oauth_server.py")
        print("2. Test Box OAuth flow in the frontend")
        print("3. Verify Box file operations work")
    else:
        print("❌ Box integration needs attention")
        if not env_ok:
            print("  - Check BOX_CLIENT_ID and BOX_CLIENT_SECRET in .env file")
        if not sdk_ok:
            print("  - Install Box SDK: pip install boxsdk")
        if not handler_ok:
            print("  - Check auth_handler_box.py configuration")
        if not oauth_sim_ok:
            print("  - Check OAuth flow configuration")


if __name__ == "__main__":
    main()
