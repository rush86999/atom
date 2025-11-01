#!/usr/bin/env python3
"""
Simple Service Monitoring Script

Checks health endpoints and logs status.

Usage:
    python monitor_services.py
"""

import requests
import time
import json
from datetime import datetime

BASE_URL = "http://localhost:5058"
ENDPOINTS = [
    "/healthz",
    "/api/services/status",
    "/api/auth/oauth-status"
]

def check_endpoint(endpoint):
    """Check a single endpoint"""
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
        response_time = (time.time() - start) * 1000

        return {
            "endpoint": endpoint,
            "status_code": response.status_code,
            "response_time": response_time,
            "success": response.status_code == 200,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "endpoint": endpoint,
            "status_code": None,
            "response_time": None,
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def main():
    """Main monitoring function"""
    print("🔍 Atom AI Assistant Service Monitor")
    print("=" * 40)

    results = []
    for endpoint in ENDPOINTS:
        result = check_endpoint(endpoint)
        results.append(result)

        if result["success"]:
            print(f"✅ {endpoint}: {result['response_time']:.1f}ms")
        else:
            print(f"❌ {endpoint}: {result.get('error', 'Unknown error')}")

    # Save results
    with open("monitoring_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)

    print(f"📊 Monitoring completed: {sum(1 for r in results if r['success'])}/{len(results)} endpoints OK")

if __name__ == "__main__":
    main()
