"""
Framework Verification Test for Atom Platform E2E Testing
Validates that the test framework is properly configured and functional
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from config.test_config import TestConfig
    from utils.llm_verifier import LLMVerifier

    FRAMEWORK_IMPORTS_SUCCESSFUL = True
except ImportError as e:
    FRAMEWORK_IMPORTS_SUCCESSFUL = False
    print(f"Framework import failed: {e}")


def verify_framework_structure() -> Dict[str, Any]:
    """Verify that the E2E test framework is properly structured"""
    results = {"framework_verified": False, "checks": {}, "errors": [], "warnings": []}

    # Check directory structure
    required_dirs = ["config", "tests", "utils"]

    for dir_name in required_dirs:
        dir_path = Path(__file__).parent / dir_name
        if dir_path.exists():
            results["checks"][f"directory_{dir_name}"] = True
        else:
            results["checks"][f"directory_{dir_name}"] = False
            results["errors"].append(f"Missing directory: {dir_name}")

    # Check required files
    required_files = [
        "config/test_config.py",
        "utils/llm_verifier.py",
        "test_runner.py",
        "run_tests.py",
        "requirements.txt",
    ]

    for file_path in required_files:
        full_path = Path(__file__).parent / file_path
        if full_path.exists():
            results["checks"][f"file_{file_path.replace('/', '_')}"] = True
        else:
            results["checks"][f"file_{file_path.replace('/', '_')}"] = False
            results["errors"].append(f"Missing file: {file_path}")

    # Check test modules
    test_modules = [
        "test_core.py",
        "test_communication.py",
        "test_productivity.py",
        "test_voice.py",
    ]

    for test_module in test_modules:
        test_path = Path(__file__).parent / "tests" / test_module
        if test_path.exists():
            results["checks"][f"test_module_{test_module}"] = True
        else:
            results["checks"][f"test_module_{test_module}"] = False
            results["warnings"].append(f"Missing test module: {test_module}")

    # Check imports
    if FRAMEWORK_IMPORTS_SUCCESSFUL:
        results["checks"]["framework_imports"] = True
    else:
        results["checks"]["framework_imports"] = False
        results["errors"].append("Framework imports failed")

    # Verify configuration
    if FRAMEWORK_IMPORTS_SUCCESSFUL:
        try:
            config = TestConfig()
            results["checks"]["test_config"] = True

            # Check configuration values
            if config.FRONTEND_URL and config.BACKEND_URL:
                results["checks"]["config_urls"] = True
            else:
                results["checks"]["config_urls"] = False
                results["warnings"].append("Configuration URLs not set")

            if config.REQUIRED_CREDENTIALS:
                results["checks"]["config_credentials"] = True
            else:
                results["checks"]["config_credentials"] = False
                results["errors"].append("Required credentials configuration missing")

            if config.MARKETING_CLAIMS:
                results["checks"]["config_marketing_claims"] = True
            else:
                results["checks"]["config_marketing_claims"] = False
                results["errors"].append("Marketing claims configuration missing")

        except Exception as e:
            results["checks"]["test_config"] = False
            results["errors"].append(f"TestConfig initialization failed: {e}")

    # Verify LLM verifier (if OpenAI key is available)
    if FRAMEWORK_IMPORTS_SUCCESSFUL and os.getenv("OPENAI_API_KEY"):
        try:
            verifier = LLMVerifier()
            results["checks"]["llm_verifier"] = True
        except Exception as e:
            results["checks"]["llm_verifier"] = False
            results["warnings"].append(f"LLM verifier initialization failed: {e}")
    else:
        results["checks"]["llm_verifier"] = None
        results["warnings"].append("LLM verifier check skipped (no OPENAI_API_KEY)")

    # Determine overall verification status
    all_checks_passed = all(
        check is True for check in results["checks"].values() if check is not None
    )

    results["framework_verified"] = all_checks_passed and len(results["errors"]) == 0

    return results


def check_environment_variables() -> Dict[str, Any]:
    """Check for required environment variables"""
    results = {
        "environment_ready": False,
        "missing_variables": [],
        "available_variables": [],
        "recommendations": [],
    }

    # Core variables
    core_vars = ["OPENAI_API_KEY"]

    # Communication variables
    comm_vars = [
        "SLACK_BOT_TOKEN",
        "DISCORD_BOT_TOKEN",
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "OUTLOOK_CLIENT_ID",
        "OUTLOOK_CLIENT_SECRET",
    ]

    # Productivity variables
    prod_vars = [
        "ASANA_ACCESS_TOKEN",
        "NOTION_API_KEY",
        "LINEAR_API_KEY",
        "TRELLO_API_KEY",
        "MONDAY_API_KEY",
    ]

    # Voice variables
    voice_vars = ["ELEVENLABS_API_KEY"]

    all_vars = core_vars + comm_vars + prod_vars + voice_vars

    for var in all_vars:
        if os.getenv(var):
            results["available_variables"].append(var)
        else:
            results["missing_variables"].append(var)

    # Generate recommendations
    if "OPENAI_API_KEY" in results["missing_variables"]:
        results["recommendations"].append(
            "Get OpenAI API key from https://platform.openai.com/ for LLM verification"
        )

    if len(results["missing_variables"]) == 0:
        results["environment_ready"] = True
        results["recommendations"].append("All required environment variables are set!")
    else:
        results["recommendations"].append(
            f"Set {len(results['missing_variables'])} missing environment variables to enable full testing"
        )

    return results


def generate_setup_report() -> Dict[str, Any]:
    """Generate comprehensive setup verification report"""
    framework_results = verify_framework_structure()
    environment_results = check_environment_variables()

    report = {
        "framework_verification": framework_results,
        "environment_check": environment_results,
        "setup_complete": (
            framework_results["framework_verified"]
            and environment_results["environment_ready"]
        ),
        "next_steps": [],
    }

    # Generate next steps
    if not framework_results["framework_verified"]:
        report["next_steps"].append("Fix framework structure issues")

    if not environment_results["environment_ready"]:
        report["next_steps"].append("Set up missing environment variables")

    if (
        framework_results["framework_verified"]
        and environment_results["environment_ready"]
    ):
        report["next_steps"].append("Run full E2E test suite: python run_tests.py")
    elif framework_results["framework_verified"]:
        report["next_steps"].append(
            "Run tests with available credentials: python run_tests.py --list-categories"
        )

    return report


if __name__ == "__main__":
    print("🔧 Atom Platform E2E Test Framework Verification")
    print("=" * 60)

    report = generate_setup_report()

    # Print framework verification results
    print("\n📁 Framework Structure:")
    for check, status in report["framework_verification"]["checks"].items():
        status_icon = "✅" if status is True else "❌" if status is False else "⚠️"
        print(f"   {status_icon} {check}: {status}")

    if report["framework_verification"]["errors"]:
        print("\n❌ Errors:")
        for error in report["framework_verification"]["errors"]:
            print(f"   - {error}")

    if report["framework_verification"]["warnings"]:
        print("\n⚠️  Warnings:")
        for warning in report["framework_verification"]["warnings"]:
            print(f"   - {warning}")

    # Print environment check results
    print(f"\n🔐 Environment Variables:")
    print(f"   ✅ Available: {len(report['environment_check']['available_variables'])}")
    print(f"   ❌ Missing: {len(report['environment_check']['missing_variables'])}")

    if report["environment_check"]["missing_variables"]:
        print("\n   Missing variables:")
        for var in report["environment_check"]["missing_variables"]:
            print(f"     - {var}")

    # Print overall status
    print(f"\n🎯 Overall Status:")
    if report["setup_complete"]:
        print("   ✅ Framework is fully configured and ready for testing!")
    else:
        print("   ⚠️  Framework requires additional configuration")

    # Print next steps
    print(f"\n📋 Next Steps:")
    for step in report["next_steps"]:
        print(f"   • {step}")

    # Exit with appropriate code
    sys.exit(0 if report["setup_complete"] else 1)
