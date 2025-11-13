"""
Simple Backend Test Script for ATOM Platform
Tests basic functionality without complex integrations
"""

import os
import sys
import time
import requests
import json
from pathlib import Path

def test_backend_connection():
    """Test backend API connection"""
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:5058')
    
    print(f"🔍 Testing backend connection to {backend_url}")
    
    try:
        # Test health endpoint
        response = requests.get(f"{backend_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend health check passed")
            return True
        else:
            print(f"❌ Backend health failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Backend not responding - is it running?")
        return False
    except requests.exceptions.Timeout:
        print("❌ Backend request timed out")
        return False
    except Exception as e:
        print(f"❌ Backend test failed: {e}")
        return False

def test_api_endpoints():
    """Test basic API endpoints"""
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:5058')
    
    endpoints = [
        ("/", "Root"),
        ("/health", "Health"),
        ("/docs", "API Documentation"),
        ("/system/status", "System Status")
    ]
    
    print("\n🔍 Testing API endpoints...")
    
    results = []
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{backend_url}{endpoint}", timeout=5)
            if response.status_code < 500:  # Accept client errors for some endpoints
                print(f"✅ {name}: {response.status_code}")
                results.append(True)
            else:
                print(f"❌ {name}: {response.status_code}")
                results.append(False)
        except Exception as e:
            print(f"❌ {name}: {e}")
            results.append(False)
    
    return all(results)

def test_service_discovery():
    """Test service discovery/registry"""
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:5058')
    
    print("\n🔍 Testing service discovery...")
    
    try:
        response = requests.get(f"{backend_url}/system/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ System status retrieved")
            
            if 'services' in data:
                services = data['services']
                print(f"📋 Found {len(services)} services")
                for service in services[:5]:  # Show first 5
                    print(f"   - {service}")
                if len(services) > 5:
                    print(f"   ... and {len(services) - 5} more")
                return True
            else:
                print("⚠️  No services found in status")
                return False
        else:
            print(f"❌ System status failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Service discovery failed: {e}")
        return False

def test_memory_system():
    """Test memory/vector system if available"""
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:5058')
    
    print("\n🔍 Testing memory system...")
    
    try:
        # Test memory health
        response = requests.get(f"{backend_url}/memory/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Memory system available")
            if data.get('connected'):
                print("   Connected to vector database")
            return True
        else:
            print(f"⚠️  Memory system not available: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️  Memory system test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🌟 ATOM Platform Backend Test")
    print("===============================")
    
    # Configuration
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:5058')
    print(f"📍 Backend URL: {backend_url}")
    print(f"📍 Current Directory: {os.getcwd()}")
    print()
    
    # Run tests
    tests = [
        ("Backend Connection", test_backend_connection),
        ("API Endpoints", test_api_endpoints),
        ("Service Discovery", test_service_discovery),
        ("Memory System", test_memory_system)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        print("-" * 40)
        
        try:
            result = test_func()
            results.append(result)
            
            if result:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test_name, _) in enumerate(tests):
        status = "✅ PASSED" if results[i] else "❌ FAILED"
        print(f"{test_name:.<30} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Backend is working correctly.")
        print("\n🚀 Next steps:")
        print("   1. Start frontend: ./start_frontend.sh")
        print("   2. Access at: http://localhost:3000")
        print("   3. Test integrations in the web interface")
        return 0
    else:
        print("⚠️  Some tests failed. Check backend logs.")
        print("\n🔧 Troubleshooting:")
        print("   1. Ensure backend is running: python start_backend.py")
        print("   2. Check logs in ./logs/backend.log")
        print("   3. Verify dependencies: pip install fastapi uvicorn")
        return 1

if __name__ == "__main__":
    sys.exit(main())