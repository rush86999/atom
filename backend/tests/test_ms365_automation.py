
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.microsoft365_service import microsoft365_service

async def test_full_automation():
    print("Testing Full Office 365 Automation Suite...")
    
    # Mock Token
    token = "fake_token"
    
    # Capture requests to verify logic
    captured_requests = []
    
    async def mock_make_request(method, url, token, json_data=None):
        # Store for verification
        captured_requests.append({
            "method": method,
            "url": url,
            "data": json_data
        })
        
        # Return generic success
        return {"status": "success", "data": {"id": "mock_id_123"}}

    # Patch the service method
    original_make_request = microsoft365_service._make_graph_request
    microsoft365_service._make_graph_request = mock_make_request
    
    try:
        # --- EXCEL TESTS ---
        print("\n--- Testing Excel ---")
        await microsoft365_service.execute_excel_action(token, "create_worksheet", {"item_id": "f1", "name": "NewSheet"})
        await microsoft365_service.execute_excel_action(token, "read_range", {"item_id": "f1", "range": "Sheet1!A1:B2"})
        
        # Verify Excel
        assert captured_requests[0]["method"] == "POST"
        assert "worksheets" in captured_requests[0]["url"]
        assert captured_requests[0]["data"]["name"] == "NewSheet"
        
        assert captured_requests[1]["method"] == "GET"
        assert "range(address='A1:B2')" in captured_requests[1]["url"]
        print("PASS: Excel Actions")

        # --- TEAMS TESTS ---
        print("\n--- Testing Teams ---")
        captured_requests.clear()
        await microsoft365_service.execute_teams_action(token, "create_team", {"display_name": "Project X", "description": "Auto Team"})
        await microsoft365_service.execute_teams_action(token, "reply_to_message", {"team_id": "t1", "channel_id": "c1", "message_id": "m1", "message": "Reply"})
        
        # Verify Teams
        assert captured_requests[0]["method"] == "POST"
        assert captured_requests[0]["url"].endswith("/teams")
        assert captured_requests[0]["data"]["displayName"] == "Project X"
        
        assert captured_requests[1]["method"] == "POST"
        assert "replies" in captured_requests[1]["url"]
        assert captured_requests[1]["data"]["body"]["content"] == "Reply"
        print("PASS: Teams Actions")

        # --- OUTLOOK TESTS ---
        print("\n--- Testing Outlook ---")
        captured_requests.clear()
        await microsoft365_service.execute_outlook_action(token, "reply_email", {"message_id": "msg1", "comment": "Got it"})
        await microsoft365_service.execute_outlook_action(token, "move_email", {"message_id": "msg1", "destination_id": "folder2"})
        
        # Verify Outlook
        assert captured_requests[0]["method"] == "POST"
        assert "createReply" not in captured_requests[0]["url"] # Wait, Graph API is /reply
        assert captured_requests[0]["url"].endswith("/reply")
        assert captured_requests[0]["data"]["comment"] == "Got it"
        
        assert captured_requests[1]["method"] == "POST"
        assert captured_requests[1]["url"].endswith("/move")
        assert captured_requests[1]["data"]["destinationId"] == "folder2"
        print("PASS: Outlook Actions")

        # --- ONEDRIVE TESTS ---
        print("\n--- Testing OneDrive ---")
        captured_requests.clear()
        await microsoft365_service.execute_onedrive_action(token, "create_folder", {"name": "NewFolder"})
        await microsoft365_service.execute_onedrive_action(token, "copy_item", {"item_id": "f1", "parent_id": "p1", "name": "CopyOfF1"})
        
        # Verify OneDrive
        assert captured_requests[0]["method"] == "POST"
        assert captured_requests[0]["url"].endswith("/children")
        assert captured_requests[0]["data"]["name"] == "NewFolder"
        
        assert captured_requests[1]["method"] == "POST"
        assert captured_requests[1]["url"].endswith("/copy")
        assert captured_requests[1]["data"]["parentReference"]["id"] == "p1"
        print("PASS: OneDrive Actions")

    except AssertionError as e:
        print(f"FAIL: Assertion failed: {e}")
        # Print captured for debug
        for i, req in enumerate(captured_requests):
            print(f"Request {i}: {req}")
    except Exception as e:
        print(f"FAIL: Exception: {e}")
    finally:
        microsoft365_service._make_graph_request = original_make_request

if __name__ == "__main__":
    asyncio.run(test_full_automation())
