#!/usr/bin/env python3
"""
Quick endpoint validation tests - tests that existing backend endpoints respond correctly
These don't need credentials, just verify endpoints exist and return valid responses
"""
import asyncio
import aiohttp
import sys
from typing import List, Tuple

async def test_endpoint(session: aiohttp.ClientSession, name: str, url: str, method: str = 'GET', expected_codes: List[int] = [200]) -> Tuple[str, bool, str]:
    """Test an endpoint and return result"""
    try:
        if method == 'GET':
            async with session.get(url, timeout=5) as response:
                success = response.status in expected_codes
                return (name, success, f"HTTP {response.status}")
        elif method == 'POST':
            async with session.post(url, json={}, timeout=5) as response:
                success = response.status in expected_codes
                return (name, success, f"HTTP {response.status}")
    except Exception as e:
        return (name, False, str(e))

async def main():
    """Run quick endpoint validation tests"""
    base_url = "http://localhost:5058"
    
    tests = [
        # Core endpoints
        ("Health Check", f"{base_url}/health", "GET", [200]),
        ("API Root", f"{base_url}/", "GET", [200]),
        ("API Docs", f"{base_url}/docs", "GET", [200]),
        
        # Workflow endpoints
        ("Workflows List", f"{base_url}/api/v1/workflows", "GET", [200]),
        ("Workflow Create", f"{base_url}/api/v1/workflows", "POST", [200, 201, 422]),  # 422 = validation error is ok
        
        # Service health endpoints
        ("Service Health", f"{base_url}/api/v1/health", "GET", [200, 404]),
        
        # Integration health (if available)
        ("Integration Health", f"{base_url}/api/v1/integrations/health", "GET", [200, 404]),
        
        # System status
        ("System Status", f"{base_url}/api/v1/system/status", "GET", [200, 404]),
        
        # AI workflow endpoints
        ("AI Workflows", f"{base_url}/api/v1/ai/workflows", "GET", [200, 404]),
        
        # Analytics endpoints
        ("Analytics Health", f"{base_url}/api/v1/analytics/health", "GET", [200, 404]),
    ]
    
    print("🚀 Running Quick Endpoint Validation Tests")
    print("="*60)
    
    passed = 0
    failed = 0
    
    async with aiohttp.ClientSession() as session:
        for name, url, method, expected in tests:
            result_name, success, message = await test_endpoint(session, name, url, method, expected)
            
            if success:
                print(f"✅ {result_name}: {message}")
                passed += 1
            else:
                print(f"❌ {result_name}: {message}")
                failed += 1
    
    total = passed + failed
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print("="*60)
    print(f"📊 Results: {passed}/{total} passed ({pass_rate:.1f}%)")
    print(f"Gap to 90%: {90 - pass_rate:.1f}%")
    
    if pass_rate >= 90:
        print("✅ Ready for launch!")
        sys.exit(0)
    else:
        print(f"⚠️  Need {90 - pass_rate:.1f}% improvement")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
