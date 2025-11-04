#!/usr/bin/env python3
"""
Test Linear Integration
"""

import requests
import json
import sys

def test_linear_health():
    """Test Linear health endpoint"""
    try:
        response = requests.get("http://localhost:8000/api/linear/health", timeout=5)
        print(f"✅ Linear Health Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Message: {data.get('message')}")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Linear Health Test Failed: {e}")
        return False

def test_linear_list_issues():
    """Test Linear list issues endpoint"""
    try:
        payload = {
            "user_id": "test_user_123",
            "limit": 5
        }
        response = requests.post("http://localhost:8000/api/linear/issues", 
                               json=payload, timeout=5)
        print(f"✅ Linear List Issues Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            issues = data.get('data', {}).get('issues', [])
            print(f"   Found {len(issues)} issues")
            for issue in issues[:2]:  # Show first 2
                print(f"   - {issue.get('identifier')}: {issue.get('title')}")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Linear List Issues Test Failed: {e}")
        return False

def test_linear_teams():
    """Test Linear teams endpoint"""
    try:
        payload = {
            "user_id": "test_user_123",
            "limit": 5
        }
        response = requests.post("http://localhost:8000/api/linear/teams", 
                               json=payload, timeout=5)
        print(f"✅ Linear Teams Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            teams = data.get('data', {}).get('teams', [])
            print(f"   Found {len(teams)} teams")
            for team in teams[:2]:  # Show first 2
                print(f"   - {team.get('name')} ({team.get('member_count')} members)")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Linear Teams Test Failed: {e}")
        return False

def main():
    print("🚀 Testing Linear Integration")
    print("=" * 40)
    
    tests = [
        test_linear_health,
        test_linear_list_issues,
        test_linear_teams
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Linear integration tests passed!")
        return 0
    else:
        print("⚠️  Some Linear integration tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())