
import asyncio
import os
import sys

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.microsoft365_service import microsoft365_service

async def test_service_status():
    print("Testing get_service_status...")
    
    # Set environment for mock bypass
    os.environ["ATOM_ENV"] = "development"
    token = "fake_token"
    
    try:
        result = await microsoft365_service.get_service_status(token)
        print(f"Result: {result}")
        
        if result["status"] == "success" and result["data"]["connectivity"] == "connected":
            print("SUCCESS: Service status check passed.")
        else:
            print("FAILURE: Service status check returned unexpected result.")
            
        print("\nTesting execute_onedrive_action...")
        # Test OneDrive list_files
        od_result = await microsoft365_service.execute_onedrive_action(
            token, 
            "list_files", 
            {"folder": ""}
        )
        print(f"OneDrive Result: {od_result}")
        
        if od_result["status"] == "success":
             print("SUCCESS: OneDrive action passed.")
        else:
             print("FAILURE: OneDrive action failed.")

    except Exception as e:
        print(f"FAILURE: Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_service_status())
