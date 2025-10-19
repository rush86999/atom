import os
import sys
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_import(module_name, timeout=5):
    """
    Test importing a module with timeout to detect hangs
    """
    print(f"🔍 Testing import: {module_name}")
    start_time = time.time()

    try:
        # Use subprocess to isolate the import and prevent hangs from affecting main process
        import subprocess
        import textwrap

        test_code = textwrap.dedent(f"""
        import sys
        import time
        start = time.time()
        try:
            import {module_name}
            end = time.time()
            print(f"SUCCESS:{module_name}:{{end - start:.2f}}s")
        except ImportError as e:
            end = time.time()
            print(f"IMPORT_ERROR:{module_name}:{{str(e)}}")
        except Exception as e:
            end = time.time()
            print(f"ERROR:{module_name}:{{str(e)}}")
        """)

        result = subprocess.run(
            [sys.executable, "-c", test_code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            output = result.stdout.strip()
            if output.startswith("SUCCESS:"):
                _, mod, time_taken = output.split(":", 2)
                print(f"✅ {module_name}: Imported successfully in {time_taken}")
                return True, float(time_taken), None
            elif output.startswith("IMPORT_ERROR:"):
                _, mod, error = output.split(":", 2)
                print(f"⚠️  {module_name}: Import error - {error}")
                return False, elapsed, f"ImportError: {error}"
            else:
                _, mod, error = output.split(":", 2)
                print(f"❌ {module_name}: Error - {error}")
                return False, elapsed, error
        else:
            print(f"❌ {module_name}: Process failed or timed out")
            return False, elapsed, "Process failed or timed out"

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"❌ {module_name}: TIMEOUT after {timeout}s")
        return False, elapsed, f"Timeout after {timeout}s"
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ {module_name}: Unexpected error - {e}")
        return False, elapsed, str(e)


def test_main_api_imports():
    """
    Test all imports from main_api_app.py to find problematic ones
    """
    print("🚀 Testing imports from main_api_app.py")
    print("=" * 50)

    # List of imports from main_api_app.py
    imports_to_test = [
        # Core Flask and database
        "flask",
        "psycopg2",
        "psycopg2.pool",
        "logging",
        # Database utilities
        "db_utils",
        "init_database",
        "lancedb_handler",
        # Blueprints from handlers
        "search_routes",
        "auth_handler_dropbox",
        "dropbox_handler",
        "auth_handler_gdrive",
        "gdrive_handler",
        "trello_handler",
        "salesforce_handler",
        "xero_handler",
        "shopify_handler",
        "twitter_handler",
        "social_media_handler",
        "sales_manager_handler",
        "project_manager_handler",
        "personal_assistant_handler",
        "financial_analyst_handler",
        "marketing_manager_handler",
        "mailchimp_handler",
        "customer_support_manager_handler",
        "legal_handler",
        "it_manager_handler",
        "devops_manager_handler",
        "content_marketer_handler",
        "meeting_prep",
        "mcp_handler",
        "account_handler",
        "transaction_handler",
        "investment_handler",
        "financial_calculation_handler",
        "financial_handler",
        "budgeting_handler",
        "bookkeeping_handler",
        "net_worth_handler",
        "invoicing_handler",
        "billing_handler",
        "payroll_handler",
        "manual_account_handler",
        "manual_transaction_handler",
        "reporting_handler",
        "box_handler",
        "asana_handler",
        "jira_handler",
        "auth_handler_box_real",
        "auth_handler_asana",
        "auth_handler_trello",
        "auth_handler_notion",
        "auth_handler_zoho",
        "auth_handler_shopify",
        "zoho_handler",
        "notion_handler_real",
        "calendar_handler",
        "task_handler",
        "message_handler",
        "transcription_handler",
        "github_handler",
    ]

    results = []
    problematic_imports = []

    for module_name in imports_to_test:
        success, elapsed, error = test_import(module_name, timeout=10)
        results.append(
            {
                "module": module_name,
                "success": success,
                "elapsed": elapsed,
                "error": error,
            }
        )

        if not success:
            problematic_imports.append((module_name, error))

        print()  # Empty line for readability

    return results, problematic_imports


def test_specific_problematic_imports():
    """
    Test imports that are known to be problematic based on previous logs
    """
    print("\n🔧 Testing known problematic imports")
    print("=" * 50)

    problematic_modules = [
        "crypto_utils",  # Shows encryption key warnings
        "plaid_service",  # Shows plaid not configured
        "search_routes",  # Shows ingestion_pipeline import error
    ]

    results = []
    for module in problematic_modules:
        success, elapsed, error = test_import(module, timeout=5)
        results.append(
            {"module": module, "success": success, "elapsed": elapsed, "error": error}
        )
        print()

    return results


def analyze_import_dependencies():
    """
    Analyze import dependencies to find circular imports or heavy dependencies
    """
    print("\n📊 Analyzing import dependencies")
    print("=" * 50)

    # Check for common problematic patterns
    heavy_modules = [
        "googleapiclient",
        "dropbox",
        "asana",
        "trello",
        "notion_client",
        "openai",
        "salesforce",
    ]

    print("Checking for heavy external dependencies...")
    for module in heavy_modules:
        success, elapsed, error = test_import(module, timeout=3)
        if success:
            print(f"📦 {module}: Available ({elapsed:.2f}s)")
        else:
            print(f"📦 {module}: Not available or slow")
        print()


def create_minimal_working_app():
    """
    Create a minimal working version that bypasses problematic imports
    """
    print("\n🛠️  Creating minimal working app configuration")
    print("=" * 50)

    # Test basic Flask app creation
    print("Testing basic Flask app creation...")
    try:
        from flask import Flask

        app = Flask(__name__)
        print("✅ Basic Flask app creation: SUCCESS")

        # Test basic endpoints
        @app.route("/healthz")
        def healthz():
            return "OK"

        print("✅ Basic endpoint creation: SUCCESS")
        return True
    except Exception as e:
        print(f"❌ Basic Flask test failed: {e}")
        return False


def main():
    """
    Main diagnostic function
    """
    print("🚀 ATOM Backend Import Diagnostic Tool")
    print("=" * 50)

    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    print(f"Working directory: {backend_dir}")

    # Step 1: Test basic Flask functionality
    print("\n📊 STEP 1: Basic Flask Test")
    print("-" * 30)
    basic_ok = create_minimal_working_app()

    # Step 2: Test main API imports
    print("\n📊 STEP 2: Main API Imports Test")
    print("-" * 30)
    results, problematic = test_main_api_imports()

    # Step 3: Test known problematic imports
    print("\n📊 STEP 3: Known Problematic Imports")
    print("-" * 30)
    problematic_results = test_specific_problematic_imports()

    # Step 4: Analyze dependencies
    print("\n📊 STEP 4: Dependency Analysis")
    print("-" * 30)
    analyze_import_dependencies()

    # Summary
    print("\n📊 DIAGNOSTIC SUMMARY")
    print("=" * 50)

    total_tests = len(results) + len(problematic_results)
    successful_tests = sum(1 for r in results if r["success"]) + sum(
        1 for r in problematic_results if r["success"]
    )

    print(f"Total imports tested: {total_tests}")
    print(f"Successful imports: {successful_tests}")
    print(f"Problematic imports: {len(problematic)}")

    if problematic:
        print("\n❌ PROBLEMATIC IMPORTS FOUND:")
        for module, error in problematic:
            print(f"   - {module}: {error}")

        print("\n💡 RECOMMENDATIONS:")
        print("   1. Create a simplified version that bypasses problematic imports")
        print("   2. Use lazy imports for heavy modules")
        print("   3. Add timeout protection for slow imports")
        print("   4. Consider using mock implementations for development")
    else:
        print("\n✅ All imports are working correctly!")
        print("   The issue might be elsewhere in the application startup.")

    return 0 if not problematic else 1


if __name__ == "__main__":
    sys.exit(main())
