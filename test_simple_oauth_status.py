#!/usr/bin/env python3
"""
Simple OAuth Status Test Script for Atom AI Assistant

This script provides a quick test of the OAuth status endpoints
to verify the current state of the OAuth authentication system.
"""

import requests
import json
from datetime import datetime


def test_oauth_status():
    """Test OAuth status endpoints and display results"""

    base_url = "http://localhost:5058"
    test_user = "test_user"

    print("🔍 Testing OAuth Status Endpoints")
    print("=" * 50)

    # Test health endpoint
    print("\n📊 Testing Health Endpoint...")
    try:
        response = requests.get(f"{base_url}/healthz", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Health: {health_data.get('status', 'unknown')}")
            print(f"   Message: {health_data.get('message', 'No message')}")
        else:
            print(f"❌ Health: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Health: {e}")

    # Test comprehensive OAuth status
    print("\n📊 Testing Comprehensive OAuth Status...")
    try:
        response = requests.get(
            f"{base_url}/api/auth/oauth-status?user_id={test_user}", timeout=5
        )
        if response.status_code == 200:
            oauth_data = response.json()
            print(f"✅ OAuth Status: {oauth_data.get('success_rate', 'unknown')}")
            print(
                f"   Connected: {oauth_data.get('connected_services', 0)}/{oauth_data.get('total_services', 0)}"
            )

            # Show individual service status
            print("\n🔐 Individual Service Status:")
            for service, status in oauth_data.get("results", {}).items():
                status_icon = "✅" if status.get("status") == "connected" else "⚠️"
                print(
                    f"   {status_icon} {service.upper()}: {status.get('status', 'unknown')} ({status.get('credentials', 'unknown')})"
                )

            # Services needing credentials
            needs_creds = oauth_data.get("services_needing_credentials", [])
            if needs_creds:
                print(f"\n⚠️  Services needing credentials: {', '.join(needs_creds)}")

        else:
            print(f"❌ OAuth Status: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ OAuth Status: {e}")

    # Test a few individual status endpoints
    print("\n📊 Testing Individual Status Endpoints...")
    test_services = ["gmail", "slack", "trello", "outlook", "github"]

    for service in test_services:
        try:
            response = requests.get(
                f"{base_url}/api/auth/{service}/status?user_id={test_user}", timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                status_icon = "✅" if data.get("status") == "connected" else "⚠️"
                print(
                    f"   {status_icon} {service.upper()}: {data.get('status', 'unknown')}"
                )
            else:
                print(f"   ❌ {service.upper()}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ {service.upper()}: {e}")

    print(f"\n⏰ Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


def main():
    """Main function"""
    try:
        test_oauth_status()
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")


if __name__ == "__main__":
    main()
