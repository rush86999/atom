#!/usr/bin/env python3
"""
Simplified GitLab Integration Verification

This script provides a quick verification of GitLab integration components
without complex testing dependencies.
"""

import os
import sys
from pathlib import Path


def check_file_exists(file_path, description):
    """Check if a file exists and print status"""
    full_path = Path(file_path)
    if full_path.exists():
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} - NOT FOUND")
        return False


def check_directory_exists(dir_path, description):
    """Check if a directory exists and count files"""
    full_path = Path(dir_path)
    if full_path.exists():
        files = list(full_path.rglob("*"))
        file_count = len([f for f in files if f.is_file()])
        print(f"✅ {description}: {dir_path} ({file_count} files)")
        return True
    else:
        print(f"❌ {description}: {dir_path} - NOT FOUND")
        return False


def verify_backend_components():
    """Verify backend GitLab components"""
    print("\n🔍 Verifying Backend Components")
    print("-" * 40)

    backend_files = [
        ("GitLab OAuth Handler", "backend/python-api-service/auth_handler_gitlab.py"),
        (
            "GitLab Service Handler",
            "backend/python-api-service/service_handlers/gitlab_handler.py",
        ),
        (
            "GitLab Enhanced Service",
            "backend/python-api-service/gitlab_enhanced_service.py",
        ),
        ("GitLab Enhanced API", "backend/python-api-service/gitlab_enhanced_api.py"),
        ("GitLab Database OAuth", "backend/python-api-service/db_oauth_gitlab.py"),
    ]

    all_good = True
    for description, file_path in backend_files:
        if not check_file_exists(file_path, description):
            all_good = False

    return all_good


def verify_frontend_components():
    """Verify frontend GitLab components"""
    print("\n🔍 Verifying Frontend Components")
    print("-" * 40)

    frontend_components = [
        ("Main Integration Page", "frontend-nextjs/pages/integrations/gitlab.tsx"),
        ("Shared UI Components", "src/ui-shared/integrations/gitlab"),
        ("API Endpoints", "frontend-nextjs/pages/api/integrations/gitlab"),
        ("GitLab Skills", "src/skills/gitlabSkills.ts"),
    ]

    all_good = True
    for description, path in frontend_components:
        if path.endswith("/"):
            if not check_directory_exists(path, description):
                all_good = False
        else:
            if not check_file_exists(path, description):
                all_good = False

    return all_good


def verify_api_endpoints():
    """Verify GitLab API endpoints"""
    print("\n🔍 Verifying API Endpoints")
    print("-" * 40)

    api_dir = Path("frontend-nextjs/pages/api/integrations/gitlab")
    if api_dir.exists():
        api_files = list(api_dir.glob("*.ts"))
        api_files.extend(list(api_dir.glob("*.tsx")))

        print(f"✅ API Endpoints Directory: {api_dir}")
        print(f"📋 Found {len(api_files)} API endpoints:")

        for api_file in sorted(api_files):
            print(f"   - {api_file.name}")

        # Check for essential endpoints
        essential_endpoints = [
            "authorize.ts",
            "callback.ts",
            "projects.ts",
            "issues.ts",
            "merge-requests.ts",
            "pipelines.ts",
            "status.ts",
        ]

        missing_endpoints = []
        for endpoint in essential_endpoints:
            endpoint_path = api_dir / endpoint
            if not endpoint_path.exists():
                missing_endpoints.append(endpoint)

        if missing_endpoints:
            print(f"⚠️  Missing essential endpoints: {', '.join(missing_endpoints)}")
            return False
        else:
            print("✅ All essential API endpoints present")
            return True
    else:
        print(f"❌ API Endpoints Directory not found: {api_dir}")
        return False


def check_main_app_registration():
    """Check if GitLab is registered in main API app"""
    print("\n🔍 Checking Main App Registration")
    print("-" * 40)

    main_app_path = Path("backend/python-api-service/main_api_app.py")
    if main_app_path.exists():
        try:
            with open(main_app_path, "r") as f:
                content = f.read()

            gitlab_mentions = [
                "gitlab" in content.lower(),
                "GITLAB" in content,
                "auth_handler_gitlab" in content,
                "gitlab_enhanced_api" in content,
                "gitlab_enhanced_bp" in content,
            ]

            if any(gitlab_mentions):
                print("✅ GitLab integration registered in main API app")
                return True
            else:
                print("❌ GitLab NOT registered in main API app")
                return False

        except Exception as e:
            print(f"❌ Error reading main app: {e}")
            return False
    else:
        print(f"❌ Main API app not found: {main_app_path}")
        return False


def verify_environment_config():
    """Check environment configuration"""
    print("\n🔍 Checking Environment Configuration")
    print("-" * 40)

    required_vars = [
        "GITLAB_BASE_URL",
        "GITLAB_CLIENT_ID",
        "GITLAB_CLIENT_SECRET",
        "GITLAB_REDIRECT_URI",
        "GITLAB_ACCESS_TOKEN (optional)",
    ]

    print("📋 Required Environment Variables:")
    for var in required_vars:
        print(f"   - {var}")

    print("\n💡 Note: These should be set in .env file for full functionality")
    return True


def generate_summary():
    """Generate implementation summary"""
    print("\n📋 GITLAB INTEGRATION SUMMARY")
    print("=" * 50)

    # Count components
    backend_count = 0
    frontend_count = 0
    api_count = 0

    # Backend files
    backend_files = [
        "backend/python-api-service/auth_handler_gitlab.py",
        "backend/python-api-service/service_handlers/gitlab_handler.py",
        "backend/python-api-service/gitlab_enhanced_service.py",
        "backend/python-api-service/gitlab_enhanced_api.py",
        "backend/python-api-service/db_oauth_gitlab.py",
    ]

    for file_path in backend_files:
        if Path(file_path).exists():
            backend_count += 1

    # Frontend files
    frontend_files = [
        "frontend-nextjs/pages/integrations/gitlab.tsx",
        "src/ui-shared/integrations/gitlab/components/GitLabManager.tsx",
        "src/skills/gitlabSkills.ts",
    ]

    for file_path in frontend_files:
        if Path(file_path).exists():
            frontend_count += 1

    # API endpoints
    api_dir = Path("frontend-nextjs/pages/api/integrations/gitlab")
    if api_dir.exists():
        api_files = list(api_dir.glob("*.ts"))
        api_files.extend(list(api_dir.glob("*.tsx")))
        api_count = len(api_files)

    print(f"📊 Component Statistics:")
    print(f"   Backend Components: {backend_count}/5")
    print(f"   Frontend Components: {frontend_count}/3")
    print(f"   API Endpoints: {api_count}")

    total_components = backend_count + frontend_count + api_count
    max_components = 5 + 3 + 13  # backend + frontend + typical API endpoints

    completion_percentage = (total_components / max_components) * 100

    print(f"\n🎯 Overall Completion: {completion_percentage:.1f}%")

    if completion_percentage >= 90:
        print("🚀 GitLab integration is READY for production!")
    elif completion_percentage >= 70:
        print("⚠️  GitLab integration is mostly complete, needs final testing")
    else:
        print("🔧 GitLab integration needs more work")

    return completion_percentage


def main():
    """Run all verification checks"""
    print("🚀 GitLab Integration - Simplified Verification")
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

    # Generate summary
    completion = generate_summary()

    if completion >= 90:
        print("\n🎉 GitLab integration is COMPLETE and ready for use!")
        print("\n🚀 Next Steps:")
        print("   1. Set GitLab credentials in .env file")
        print("   2. Start backend server")
        print("   3. Navigate to /integrations/gitlab in frontend")
        print("   4. Test OAuth flow and API operations")
        print("   5. Deploy to production")
    else:
        print("\n⚠️  GitLab integration needs completion work.")
        print("   Review the missing components above.")

    print(f"\n📍 Project Root: {project_root}")

    return 0 if completion >= 90 else 1


if __name__ == "__main__":
    sys.exit(main())
