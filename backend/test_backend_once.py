#!/usr/bin/env python3
"""
ONE-TIME BACKEND TEST
Quick test to verify backend is working
"""

import requests
import time
import sys


def test_backend():
    print("🚀 Testing ATOM Backend")
    print("=" * 40)

    # Test basic endpoints
    endpoints = [
        ("/health", "GET"),
        ("/api/asana/health", "GET"),
        ("/api/auth/asana/authorize?user_id=test", "GET"),
        ("/api/services/status", "GET"),
    ]

    for endpoint, method in endpoints:
        try:
            url = f"http://localhost:8000{endpoint}"
            if method == "GET":
                response = requests.get(url, timeout=5)
            else:
                response = requests.post(url, json={}, timeout=5)

            if response.status_code == 200:
                print(f"✅ {endpoint} - WORKING")
                data = response.json()
                if "ok" in data:
                    print(f"   Status: {data.get('ok', 'unknown')}")
                if "service" in data:
                    print(f"   Service: {data.get('service', 'unknown')}")
            else:
                print(f"❌ {endpoint} - Status {response.status_code}")

        except Exception as e:
            print(f"❌ {endpoint} - FAILED: {e}")

    print("\n" + "=" * 40)
    print("🎯 TEST COMPLETE")


if __name__ == "__main__":
    test_backend()
