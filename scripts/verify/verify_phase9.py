import asyncio
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'backend'))

async def test_phase9():
    print("--- Phase 9 Verification: Stub Replacement ---")
    
    # Test Google Drive mock fallback
    print("\n1. Testing Google Drive mock fallback...")
    from integrations.google_drive_service import google_drive_service
    result = await google_drive_service.list_files("mock")
    if result.get("mode") == "mock" and result.get("status") == "success":
        print("✓ Google Drive mock fallback works")
    else:
        print(f"✗ Google Drive mock fallback failed: {result}")
    
    # Test OneDrive mock fallback
    print("\n2. Testing OneDrive mock fallback...")
    from integrations.onedrive_service import onedrive_service
    result = await onedrive_service.list_files("mock")
    if result.get("mode") == "mock" and result.get("status") == "success":
        print("✓ OneDrive mock fallback works")
    else:
        print(f"✗ OneDrive mock fallback failed: {result}")
    
    # Test Box mock fallback
    print("\n3. Testing Box mock fallback...")
    from integrations.box_service import box_service
    result = await box_service.list_files("mock")
    if result.get("mode") == "mock" and result.get("status") == "success":
        print("✓ Box mock fallback works")
    else:
        print(f"✗ Box mock fallback failed: {result}")
    
    # Test Notion service exists and has real API
    print("\n4. Verifying Notion has real API...")
    from integrations.notion_service import notion_service
    if hasattr(notion_service, 'search') and hasattr(notion_service, 'get_page'):
        print("✓ Notion service has real API methods")
    else:
        print("✗ Notion service missing API methods")
    
    print("\n--- Phase 9 Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(test_phase9())
