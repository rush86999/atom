#!/usr/bin/env python3
"""
Quick environment check script for pyright/Google API compatibility
Run from project root: python3 check_pyright_env.py
"""

import sys
import os
from pathlib import Path

def setup_and_check_environment():
    """Check and setup Python environment for pyright compatibility"""

    project_root = Path(__file__).parent
    print("🔍 PyRight Environment Check")
    print("=" * 50)

    # Check Python version
    print(f"✏️  Python Executable: {sys.executable}")
    print(f"✏️  Python Version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    # Check for requirements file
    requirements_path = project_root / "atomic-docker" / "project" / "functions" / "python_api_service" / "requirements.txt"
    print(f"\n📋 Requirements file: {requirements_path.exists()}")

    # Test Google API imports
    test_modules = {
        "google.oauth2.credentials": "Google OAuth2",
        "googleapiclient.discovery": "Google API Discovery",
        "googleapiclient.errors": "Google API Errors",
        "google.auth.transport.requests": "Google Auth Transport",
        "googleapiclient.http": "Google API HTTP",
        "PyPDF2": "PDF Processing"
    }

    print("\n🔍 Testing Google API Imports:")
    print("-" * 40)

    missing_deps = []
    all_good = True

    for module, description in test_modules.items():
        try:
            __import__(module)
            print(f"✅ {module} ({description})")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            missing_deps.append(module)
            all_good = False

    print("\n📊 Summary:")
    if missing_deps:
        print("❌ Missing dependencies:")
        for dep in missing_deps:
            print(f"   - {dep}")
        print("\n🔧 Fix with:")
        print("   pip install google-api-python-client google-auth PyPDF2")
    else:
        print("✅ All dependencies installed correctly!")
        print("💡 Restart your IDE for changes to take effect")

    # Check if .venv exists
    venv_path = project_root / ".venv"
    print(f"\n📁 Virtual environment: {venv_path.exists()}")

    # Recommend next steps
    print("\n💡 Next Steps:")
    if not all_good:
        print("1. Run: python3 -m venv .venv")
        print("2. Activate: source .venv/bin/activate")
        print("3. Install: pip install -r requirements.txt")
    else:
        print("✅ Your environment is pyright compatible!")
        print("💡 Restart your IDE for changes to take effect")

    return all_good

if __name__ == "__main__":
    success = setup_and_check_environment()
    sys.exit(0 if success else 1)
