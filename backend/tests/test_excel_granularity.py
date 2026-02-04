
import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.microsoft365_service import microsoft365_service


async def test_excel_granularity():
    print("Testing Excel Granular Updates (Column Mapping)...")
    
    # Set environment for mock bypass if needed, but we will mock the request method directly
    # to simulate the specific granular responses we need.
    os.environ["ATOM_ENV"] = "development"
    token = "fake_token"
    
    # Mock data
    mock_columns = {
        "value": [
            {"name": "ID"},
            {"name": "Name"},
            {"name": "Status"},
            {"name": "Date"}
        ]
    }
    
    # We need to mock _make_graph_request to handle multiple calls
    # 1. First call: GET columns -> returns mock_columns
    # 2. Second call: POST rows -> returns success
    
    original_make_request = microsoft365_service._make_graph_request
    
    async def mock_make_request(method, url, token, json_data=None):
        print(f"DEBUG: Mock Request: {method} {url}")
        
        if "columns" in url and method == "GET":
            return {"status": "success", "data": mock_columns}
            
        if "rows" in url and method == "POST":
            # Verify the data being sent
            values = json_data.get("values", [])
            print(f"DEBUG: Posted Values: {values}")
            
            # Validation logic
            if len(values) == 1 and len(values[0]) == 4:
                # Check mapping correctness
                # Expected: ID, Name, Status, Date
                row = values[0]
                # We'll assert values in the main block by capturing print output if needed, but here we just return success
                return {"status": "success", "data": {"row": row}}
            else:
                return {"status": "error", "message": "Invalid row structure"}
                
        return {"status": "error", "message": "Unknown mock URL"}

    # Monkey patch the method for this test
    microsoft365_service._make_graph_request = mock_make_request
    
    try:
        # Test Case 1: Full mapping
        print("\nTest 1: Full Column Mapping")
        mapping = {
            "ID": "101",
            "Name": "Project Phoenix",
            "Status": "Active",
            "Date": "2024-01-01"
        }
        
        result = await microsoft365_service.execute_excel_action(
            token,
            "append_row",
            {
                "item_id": "file123",
                "table": "Table1",
                "column_mapping": mapping
            }
        )
        print(f"Result 1: {result}")
        if result["status"] == "success":
             print("PASS: Full mapping executed successfully")
        else:
             print("FAIL: Full mapping failed")

        # Test Case 2: Partial mapping (should fill missing with empty strings)
        print("\nTest 2: Partial Mapping")
        partial_mapping = {
            "ID": "102",
            "Name": "Project Pegasus"
            # Status and Date missing
        }
        
        result = await microsoft365_service.execute_excel_action(
            token,
            "append_row",
            {
                "item_id": "file123",
                "table": "Table1",
                "column_mapping": partial_mapping
            }
        )
        print(f"Result 2: {result}")
        
        # Test Case 3: Extra columns (should be ignored)
        print("\nTest 3: Extra Columns in Mapping")
        extra_mapping = {
            "ID": "103",
            "Name": "Project Chimera",
            "Status": "Draft",
            "Date": "2024-02-01",
            "ExtraField": "ShouldBeIgnored"
        }
        
        result = await microsoft365_service.execute_excel_action(
            token,
            "append_row",
            {
                "item_id": "file123",
                "table": "Table1",
                "column_mapping": extra_mapping
            }
        )
        print(f"Result 3: {result}")

    except Exception as e:
        print(f"FAILURE: Exception occurred: {e}")
    finally:
        # Restore mock
        microsoft365_service._make_graph_request = original_make_request

if __name__ == "__main__":
    asyncio.run(test_excel_granularity())
