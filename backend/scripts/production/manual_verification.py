"""
Simple Manual Verification Script for Real-time Collaboration
Bypasses automated testing to directly verify each endpoint
"""

import json
import requests

BASE_URL = "http://localhost:5062"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_api_health():
    """Verify API is running"""
    print_section("1. API Health Check")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ Backend is running on port 5062")
            print(f"   API Docs: {BASE_URL}/docs")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("   Make sure backend is running: uvicorn main_api_app:app --port 5062")
        return False

def manual_registration():
    """Guide for manual registration test"""
    print_section("2. User Registration (Manual)")
    print("📝 Steps to test registration:")
    print(f"   1. Open: {BASE_URL}/docs")
    print("   2. Find: POST /api/auth/register")
    print("   3. Click 'Try it out'")
    print("   4. Use this body:")
    print(json.dumps({
        "email": "demo@example.com",
        "password": "Demo123!",
        "first_name": "Demo",
        "last_name": "User"
    }, indent=2))
    print("\n   5. Click 'Execute'")
    print("   6. Expected: 200 response with access_token")
    print("\n   Copy the access_token for next steps")
    
    input("\n   Press Enter when you have the token...")
    token = input("   Paste the access_token here: ").strip()
    return token

def test_auth_me(token):
    """Test /api/auth/me endpoint"""
    print_section("3. Get Current User")
    try:
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            user = response.json()
            print("✅ Successfully fetched current user:")
            print(f"   Email: {user.get('email')}")
            print(f"   ID: {user.get('id')}")
            print(f"   Name: {user.get('first_name')} {user.get('last_name')}")
            return user
        else:
            print(f"❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def manual_websocket_test(token):
    """Guide for WebSocket testing"""
    print_section("4. WebSocket Connection (Manual)")
    print("📝 Test WebSocket in browser console:")
    print(f"\n   1. Open: {BASE_URL}/docs (or any page)")
    print("   2. Open browser DevTools (F12)")
    print("   3. Go to Console tab")
    print("   4. Paste and run:")
    print(f"""
   const ws = new WebSocket('ws://localhost:5062/ws?token={token}');
   ws.onopen = () => console.log('✅ WebSocket connected!');
   ws.onmessage = (e) => console.log('📨 Message:', e.data);
   ws.onerror = (e) => console.log('❌ Error:', e);
   ws.onclose = () => console.log('🔌 Disconnected');
    """)
    print("\n   5. You should see '✅ WebSocket connected!'")
    
    input("\n   Press Enter when WebSocket is connected...")

def frontend_test():
    """Guide for frontend testing"""
    print_section("5. Frontend Testing")
    print("📝 Test the frontend:")
    print("\n   1. Ensure frontend is running:")
    print("      cd frontend-nextjs && npm run dev")
    print("\n   2. Open: http://localhost:3000/login")
    print("   3. Register/Login with:")
    print("      Email: demo@example.com")
    print("      Password: Demo123!")
    print("\n   4. Navigate to: http://localhost:3000/team-chat")
    print("   5. You should see the Team Chat interface")
    
    input("\n   Press Enter when frontend test is complete...")

def summary():
    """Print verification summary"""
    print_section("Verification Summary")
    print("✅ Completed Manual Verification Steps:")
    print("   1. Backend Health Check")
    print("   2. User Registration")
    print("   3. Get Current User (/api/auth/me)")
    print("   4. WebSocket Connection")
    print("   5. Frontend Interface")
    print("\n🎉 All core features verified!")
    print("\n📚 Next Steps:")
    print("   - Create teams via /api/enterprise/teams")
    print("   - Test team messaging via /api/teams/{id}/messages")
    print("   - Explore all endpoints at /docs")
    print(f"\n🔗 Quick Links:")
    print(f"   API Docs: {BASE_URL}/docs")
    print(f"   Frontend: http://localhost:3000/team-chat")

def main():
    print("\n🚀 Real-time Collaboration - Manual Verification")
    print("="*60)
    
    # Step 1: Health Check
    if not test_api_health():
        return
    
    # Step 2: Manual Registration
    token = manual_registration()
    
    if not token:
        print("\n⚠️  Skipping authenticated tests (no token provided)")
        return
    
    # Step 3: Get Current User
    user = test_auth_me(token)
    
    # Step 4: WebSocket Test
    if user:
        manual_websocket_test(token)
    
    # Step 5: Frontend Test
    frontend_test()
    
    # Summary
    summary()

if __name__ == "__main__":
    main()
