#!/usr/bin/env python3
"""
Test Actual API Connectivity for Available Services
"""

import json
import os
import sys
from datetime import datetime


def test_trello_api():
    """Test Trello API with actual credentials"""
    try:
        from trello import TrelloClient
        
        client = TrelloClient(
            api_key=os.getenv('TRELLO_API_KEY'),
            api_secret=os.getenv('TRELLO_API_TOKEN')
        )
        
        # Try to get boards (lightweight operation)
        boards = client.list_boards()
        
        return {
            "status": "connected",
            "boards_count": len(boards),
            "board_names": [board.name for board in boards[:3]]  # First 3 boards
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_notion_api():
    """Test Notion API with current token"""
    try:
        from notion_client import Client
        
        notion = Client(auth=os.getenv('NOTION_TOKEN'))
        
        # Test user info
        user_info = notion.users.me()
        
        return {
            "status": "connected",
            "user": user_info.get('name', 'Unknown'),
            "bot_id": user_info.get('id', 'Unknown')
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_github_api():
    """Test GitHub API (requires token)"""
    try:
        from github import Github

        # Note: This requires GITHUB_TOKEN environment variable
        token = os.getenv('GITHUB_TOKEN')
        if not token:
            return {"status": "skip", "message": "GITHUB_TOKEN not configured"}
        
        g = Github(token)
        
        # Test getting user info
        user = g.get_user()
        
        return {
            "status": "connected",
            "user": user.login,
            "repos_count": user.public_repos
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_dropbox_api():
    """Test Dropbox API (requires OAuth)"""
    try:
        import dropbox

        # Note: This requires OAuth access token
        access_token = os.getenv('DROPBOX_ACCESS_TOKEN')
        if not access_token:
            return {"status": "skip", "message": "DROPBOX_ACCESS_TOKEN not configured (needs OAuth)"}
        
        dbx = dropbox.Dropbox(access_token)
        
        # Test account info
        account = dbx.users_get_current_account()
        
        return {
            "status": "connected",
            "user": account.name.display_name,
            "email": account.email
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_asana_api():
    """Test Asana API (requires OAuth)"""
    try:
        from asana.api_client import ApiClient
        from asana.configuration import Configuration

        # Note: This requires OAuth access token
        access_token = os.getenv('ASANA_ACCESS_TOKEN')
        if not access_token:
            return {"status": "skip", "message": "ASANA_ACCESS_TOKEN not configured (needs OAuth)"}
        
        configuration = Configuration()
        configuration.access_token = access_token
        
        api_client = ApiClient(configuration)
        
        return {
            "status": "sdk_configured",
            "message": "Asana SDK configured - requires OAuth token for API calls"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    # Add current directory to Python path
    sys.path.insert(0, '.')
    
    print("🔌 Testing Actual API Connectivity")
    print("=" * 60)
    
    tests = {
        "Trello": test_trello_api,
        "Notion": test_notion_api,
        "GitHub": test_github_api,
        "Dropbox": test_dropbox_api,
        "Asana": test_asana_api
    }
    
    results = {}
    for service_name, test_func in tests.items():
        print(f"\n🔍 Testing {service_name} API...")
        result = test_func()
        results[service_name] = result
        
        status_icon = "✅" if result["status"] == "connected" else "⚠️" if result["status"] == "sdk_configured" else "❌"
        print(f"   {status_icon} {service_name}: {result['status']}")
        
        if "message" in result:
            print(f"      {result['message']}")
        elif "user" in result:
            print(f"      User: {result['user']}")
        if "boards_count" in result:
            print(f"      Boards: {result['boards_count']}")
        if "repos_count" in result:
            print(f"      Repos: {result['repos_count']}")
    
    print("\n" + "=" * 60)
    print("📊 API Connectivity Summary:")
    
    connected = sum(1 for r in results.values() if r["status"] == "connected")
    configured = sum(1 for r in results.values() if r["status"] == "sdk_configured")
    skipped = sum(1 for r in results.values() if r["status"] == "skip")
    errors = sum(1 for r in results.values() if r["status"] == "error")
    
    print(f"   ✅ Connected: {connected}")
    print(f"   🔧 SDK Configured: {configured}")
    print(f"   ⏭️  Skipped (needs OAuth): {skipped}")
    print(f"   ❌ Errors: {errors}")
    print(f"   📈 Total Tested: {len(results)}")
    
    # Save results
    report = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "connected": connected,
            "sdk_configured": configured,
            "skipped": skipped,
            "errors": errors,
            "total_tested": len(results)
        }
    }
    
    with open("api_connectivity_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: api_connectivity_report.json")

if __name__ == "__main__":
    main()