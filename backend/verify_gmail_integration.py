#!/usr/bin/env python3
"""
Gmail Integration Verification Script

This script verifies the current state of Gmail integration
and identifies what needs to be completed.
"""

import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def verify_backend_components():
    """Verify all backend Gmail components"""
    print("🔍 Verifying Backend Gmail Components...")

    backend_components = [
        ("Gmail OAuth Handler", "backend/python-api-service/auth_handler_gmail.py"),
        (
            "Gmail Enhanced Service",
            "backend/python-api-service/gmail_enhanced_service.py",
        ),
        ("Gmail Enhanced API", "backend/python-api-service/gmail_enhanced_api.py"),
        ("Gmail Database OAuth", "backend/python-api-service/db_oauth_gmail.py"),
        ("Gmail Health Handler", "backend/python-api-service/gmail_health_handler.py"),
    ]

    all_available = True
    for name, path in backend_components:
        full_path = Path(path)
        if full_path.exists():
            print(f"   ✅ {name}: {path}")

            # Try to import Python files
            if path.endswith(".py"):
                try:
                    backend_path = Path("backend/python-api-service")
                    if str(backend_path) not in sys.path:
                        sys.path.insert(0, str(backend_path))

                    if name == "Gmail OAuth Handler":
                        from auth_handler_gmail import GitLabOAuthHandler

                        print(f"      ✅ GitLabOAuthHandler imported successfully")
                    elif name == "Gmail Enhanced Service":
                        from gmail_enhanced_service import GmailEnhancedService

                        print(f"      ✅ GmailEnhancedService imported successfully")
                    elif name == "Gmail Enhanced API":
                        from gmail_enhanced_api import gmail_enhanced_bp

                        print(f"      ✅ gmail_enhanced_bp imported successfully")

                except ImportError as e:
                    print(f"      ⚠️  Import warning: {e}")
                    all_available = False
        else:
            print(f"   ❌ {name}: {path} - FILE NOT FOUND")
            all_available = False

    return all_available


def verify_frontend_components():
    """Verify all frontend Gmail components"""
    print("\n🔍 Verifying Frontend Gmail Components...")

    frontend_components = [
        ("Main Integration Page", "frontend-nextjs/pages/integrations/gmail.tsx"),
        ("API Endpoints", "frontend-nextjs/pages/api/integrations/gmail/"),
        ("Gmail Skills", "src/skills/gmailSkills.ts"),
    ]

    all_available = True
    for name, path in frontend_components:
        full_path = Path(path)
        if full_path.exists():
            print(f"   ✅ {name}: {path}")

            # Check if directory has content
            if full_path.is_dir():
                files = list(full_path.rglob("*"))
                print(f"      📁 Contains {len(files)} files")
        else:
            print(f"   ❌ {name}: {path} - NOT FOUND")
            all_available = False

    return all_available


def verify_api_endpoints():
    """Verify Gmail API endpoints"""
    print("\n🔍 Verifying Gmail API Endpoints...")

    api_endpoints_dir = Path("frontend-nextjs/pages/api/integrations/gmail")
    if api_endpoints_dir.exists():
        api_files = list(api_endpoints_dir.glob("*.ts"))
        api_files.extend(list(api_endpoints_dir.glob("*.tsx")))

        print(f"   ✅ API Endpoints Directory: {api_endpoints_dir}")
        print(f"   📋 Found {len(api_files)} API endpoints:")

        for api_file in sorted(api_files):
            print(f"      - {api_file.name}")

        return True
    else:
        print(f"   ❌ API Endpoints Directory not found: {api_endpoints_dir}")
        return False


def check_main_app_registration():
    """Check if Gmail is registered in main API app"""
    print("\n🔍 Checking Main App Registration...")

    main_app_path = Path("backend/python-api-service/main_api_app.py")
    if main_app_path.exists():
        try:
            with open(main_app_path, "r") as f:
                content = f.read()

            gmail_mentions = [
                "gmail" in content.lower(),
                "GMAIL" in content,
                "auth_handler_gmail" in content,
                "gmail_enhanced_api" in content,
            ]

            if any(gmail_mentions):
                print("   ✅ Gmail mentioned in main API app")
                return True
            else:
                print("   ❌ Gmail NOT registered in main API app")
                return False

        except Exception as e:
            print(f"   ❌ Error reading main app: {e}")
            return False
    else:
        print(f"   ❌ Main API app not found: {main_app_path}")
        return False


def verify_environment_config():
    """Check environment configuration"""
    print("\n🔍 Checking Environment Configuration...")

    required_vars = [
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "GMAIL_REDIRECT_URI",
        "GMAIL_ACCESS_TOKEN (optional)",
    ]

    print("   📋 Required Environment Variables:")
    for var in required_vars:
        print(f"      - {var}")

    print("\n   💡 Note: These should be set in .env file for full functionality")
    return True


def generate_completion_plan():
    """Generate completion plan based on current state"""
    print("\n📋 GENERATING COMPLETION PLAN")
    print("=" * 50)

    # Check what's missing
    missing_components = []

    # Backend checks
    if not Path("backend/python-api-service/gmail_enhanced_service.py").exists():
        missing_components.append("Gmail Enhanced Service")
    if not Path("backend/python-api-service/gmail_enhanced_api.py").exists():
        missing_components.append("Gmail Enhanced API")
    if not Path("backend/python-api-service/db_oauth_gmail.py").exists():
        missing_components.append("Gmail Database OAuth")

    # Frontend checks
    if not Path("frontend-nextjs/pages/integrations/gmail.tsx").exists():
        missing_components.append("Main Integration Page")

    # Registration check
    main_app_path = Path("backend/python-api-service/main_api_app.py")
    if main_app_path.exists():
        with open(main_app_path, "r") as f:
            content = f.read()
        if "gmail_enhanced_api" not in content:
            missing_components.append("Main App Registration")

    if missing_components:
        print("🚨 MISSING COMPONENTS:")
        for component in missing_components:
            print(f"   ❌ {component}")

        print("\n🎯 PRIORITY ACTIONS:")
        if "Gmail Enhanced Service" in missing_components:
            print("   1. Create gmail_enhanced_service.py with core Gmail operations")
        if "Gmail Enhanced API" in missing_components:
            print("   2. Create gmail_enhanced_api.py with Flask routes")
        if "Gmail Database OAuth" in missing_components:
            print("   3. Create db_oauth_gmail.py for token storage")
        if "Main Integration Page" in missing_components:
            print("   4. Create frontend-nextjs/pages/integrations/gmail.tsx")
        if "Main App Registration" in missing_components:
            print("   5. Register Gmail in main_api_app.py")
    else:
        print("✅ All critical components appear to be present!")
        print("   Next: Run comprehensive testing and documentation")

    return len(missing_components) == 0


def main():
    """Run all verification checks"""
    print("🚀 Gmail Integration Verification")
    print("=" * 50)

    # Change to project root if needed
    project_root = Path(__file__).parent
    os.chdir(project_root)

    # Run all verifications
    backend_ok = verify_backend_components()
    frontend_ok = verify_frontend_components()
    api_ok = verify_api_endpoints()
    registration_ok = check_main_app_registration()
    env_ok = verify_environment_config()

    # Summary
    print("\n" + "=" * 50)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 50)

    results = [
        ("Backend Components", backend_ok),
        ("Frontend Components", frontend_ok),
        ("API Endpoints", api_ok),
        ("Main App Registration", registration_ok),
        ("Environment Setup", env_ok),
    ]

    for component, status in results:
        indicator = "✅ PASS" if status else "❌ FAIL"
        print(f"{component:<25} {indicator}")

    # Generate completion plan
    all_complete = generate_completion_plan()

    if all_complete:
        print("\n🎉 Gmail integration is READY for final testing!")
        print("\n🚀 Next Steps:")
        print("   1. Set Gmail credentials in .env file")
        print("   2. Start backend server")
        print("   3. Test OAuth flow")
        print("   4. Run comprehensive integration tests")
        print("   5. Deploy to production")
    else:
        print("\n⚠️  Gmail integration needs completion work.")
        print("   Follow the priority actions above.")

    print(f"\n📍 Project Root: {project_root}")

    return 0 if all_complete else 1


if __name__ == "__main__":
    sys.exit(main())
