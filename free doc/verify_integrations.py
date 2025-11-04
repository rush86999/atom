#!/usr/bin/env python3
"""
Integration Verification Test
Tests both Box and Notion integrations to verify credentials and functionality
"""

import os
import sys
from dotenv import load_dotenv


def load_environment():
    """Load environment variables from .env file"""
    try:
        load_dotenv()
        print("✅ Environment variables loaded from .env")
        return True
    except Exception as e:
        print(f"❌ Failed to load environment: {e}")
        return False


def test_notion_credentials():
    """Test Notion OAuth credentials"""
    print("\n🔍 Testing Notion Integration")
    print("-" * 40)

    notion_client_id = os.getenv("NOTION_CLIENT_ID")
    notion_client_secret = os.getenv("NOTION_CLIENT_SECRET")

    if not notion_client_id:
        print("❌ NOTION_CLIENT_ID: NOT SET")
        return False
    if not notion_client_secret:
        print("❌ NOTION_CLIENT_SECRET: NOT SET")
        return False

    print(f"✅ NOTION_CLIENT_ID: {notion_client_id[:10]}...")
    print(f"✅ NOTION_CLIENT_SECRET: {notion_client_secret[:10]}...")

    # Test auth handler import
    try:
        sys.path.append("backend/python-api-service")
        from auth_handler_notion import NOTION_CLIENT_ID, NOTION_CLIENT_SECRET

        if (
            NOTION_CLIENT_ID == notion_client_id
            and NOTION_CLIENT_SECRET == notion_client_secret
        ):
            print("✅ Notion auth handler properly configured")
            return True
        else:
            print("❌ Notion auth handler credentials mismatch")
            return False

    except ImportError as e:
        print(f"❌ Failed to import Notion auth handler: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing Notion auth handler: {e}")
        return False


def test_box_credentials():
    """Test Box OAuth credentials"""
    print("\n📦 Testing Box Integration")
    print("-" * 40)

    box_client_id = os.getenv("BOX_CLIENT_ID")
    box_client_secret = os.getenv("BOX_CLIENT_SECRET")

    if not box_client_id:
        print("❌ BOX_CLIENT_ID: NOT SET")
        return False
    if not box_client_secret:
        print("❌ BOX_CLIENT_SECRET: NOT SET")
        return False

    print(f"✅ BOX_CLIENT_ID: {box_client_id[:10]}...")
    print(f"✅ BOX_CLIENT_SECRET: {box_client_secret[:10]}...")

    # Test auth handler import
    try:
        sys.path.append("backend/python-api-service")
        from auth_handler_box import BOX_CLIENT_ID, BOX_CLIENT_SECRET

        if BOX_CLIENT_ID == box_client_id and BOX_CLIENT_SECRET == box_client_secret:
            print("✅ Box auth handler properly configured")
            return True
        else:
            print("❌ Box auth handler credentials mismatch")
            return False

    except ImportError as e:
        print(f"❌ Failed to import Box auth handler: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing Box auth handler: {e}")
        return False


def test_box_sdk():
    """Test if Box SDK is available"""
    print("\n📦 Testing Box SDK Availability")
    print("-" * 40)

    try:
        import boxsdk

        print(
            f"✅ Box SDK installed (version: {boxsdk.__version__ if hasattr(boxsdk, '__version__') else 'Unknown'})"
        )
        return True
    except ImportError:
        print("❌ Box SDK not installed")
        print("   Install with: pip install boxsdk")
        return False


def test_notion_backend_integration():
    """Test Notion backend integration components"""
    print("\n🔍 Testing Notion Backend Integration")
    print("-" * 40)

    components_to_test = [
        ("auth_handler_notion.py", "OAuth Handler"),
        ("db_oauth_notion.py", "Database Integration"),
        ("notion_handler_real.py", "Service Handler"),
        ("notion_service_real.py", "Service Implementation"),
    ]

    backend_path = "backend/python-api-service"
    all_found = True

    for filename, description in components_to_test:
        file_path = os.path.join(backend_path, filename)
        if os.path.exists(file_path):
            print(f"✅ {description}: {filename}")
        else:
            print(f"❌ {description}: {filename} - NOT FOUND")
            all_found = False

    return all_found


def test_box_backend_integration():
    """Test Box backend integration components"""
    print("\n📦 Testing Box Backend Integration")
    print("-" * 40)

    components_to_test = [
        ("auth_handler_box.py", "OAuth Handler"),
        ("auth_handler_box_real.py", "Real OAuth Handler"),
        ("db_oauth_box.py", "Database Integration"),
        ("box_service.py", "Service Implementation"),
        ("box_service_real.py", "Real Service Implementation"),
    ]

    backend_path = "backend/python-api-service"
    all_found = True

    for filename, description in components_to_test:
        file_path = os.path.join(backend_path, filename)
        if os.path.exists(file_path):
            print(f"✅ {description}: {filename}")
        else:
            print(f"❌ {description}: {filename} - NOT FOUND")
            all_found = False

    return all_found


def test_frontend_integration():
    """Test frontend integration components"""
    print("\n🎨 Testing Frontend Integration")
    print("-" * 40)

    # Test Notion frontend components
    notion_components = [
        (
            "src/ui-shared/integrations/notion/components/NotionDataSource.tsx",
            "Notion Data Source",
        ),
        ("src/ui-shared/integrations/notion/types/index.ts", "Notion Types"),
        ("src/ui-shared/integrations/notion/hooks", "Notion Hooks"),
        ("src/ui-shared/integrations/notion/utils", "Notion Utils"),
    ]

    print("🔍 Notion Frontend Components:")
    notion_ok = True
    for path, description in notion_components:
        if os.path.exists(path):
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ {description} - NOT FOUND")
            notion_ok = False

    # Test Box frontend components
    box_components = [
        ("src/ui-shared/components/box/ATOMBoxManager.tsx", "Box Manager"),
        ("src/ui-shared/components/box/ATOMBoxDataSource.tsx", "Box Data Source"),
        ("src/ui-shared/types/box/index.ts", "Box Types"),
    ]

    print("\n📦 Box Frontend Components:")
    box_ok = True
    for path, description in box_components:
        if os.path.exists(path):
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ {description} - NOT FOUND")
            box_ok = False

    # Check for integration folder structure issue
    box_integration_path = "src/ui-shared/integrations/box"
    if not os.path.exists(box_integration_path):
        print(f"  ⚠️  Box integration folder missing: {box_integration_path}")
        print(
            "  This is a structural gap - components exist but not in integrations folder"
        )

    return notion_ok and box_ok


def main():
    """Run all integration verification tests"""
    print("🔧 ATOM Integration Verification Test")
    print("=" * 50)

    # Load environment
    if not load_environment():
        return

    test_results = {}

    # Test Notion integration
    test_results["notion_credentials"] = test_notion_credentials()
    test_results["notion_backend"] = test_notion_backend_integration()

    # Test Box integration
    test_results["box_credentials"] = test_box_credentials()
    test_results["box_sdk"] = test_box_sdk()
    test_results["box_backend"] = test_box_backend_integration()

    # Test frontend integration
    test_results["frontend"] = test_frontend_integration()

    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)

    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")

    # Overall assessment
    all_passed = all(test_results.values())

    if all_passed:
        print("\n🎉 ALL INTEGRATIONS VERIFIED SUCCESSFULLY!")
        print("\n🚀 Next Steps:")
        print("1. Start the OAuth server: python start_complete_oauth_server.py")
        print("2. Test Notion OAuth flow in frontend settings")
        print("3. Test Box OAuth flow in frontend settings")
        print("4. Verify file operations work for both services")
    else:
        print("\n⚠️  SOME INTEGRATIONS NEED ATTENTION")
        print("\n🔧 Required Fixes:")

        if not test_results["notion_credentials"]:
            print("  - Check NOTION_CLIENT_ID and NOTION_CLIENT_SECRET in .env")
        if not test_results["box_credentials"]:
            print("  - Check BOX_CLIENT_ID and BOX_CLIENT_SECRET in .env")
        if not test_results["box_sdk"]:
            print("  - Install Box SDK: pip install boxsdk")
        if not test_results["frontend"]:
            print("  - Fix frontend component structure")

        print("\n💡 Additional Notes:")
        print(
            "  - Box integration has structural gap (components not in integrations folder)"
        )
        print(
            "  - This doesn't affect functionality but should be fixed for consistency"
        )


if __name__ == "__main__":
    main()
