#!/usr/bin/env python3
"""
Test Slack Integration
Run comprehensive tests to verify Slack integration functionality
"""

import asyncio
import logging
import json
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_slack_services():
    """Test Slack integration services"""
    test_results = {
        "total_tests": 0,
        "passed_tests": 0,
        "failed_tests": 0,
        "test_details": []
    }
    
    def run_test(test_name: str, test_func):
        """Run a single test and track results"""
        test_results["total_tests"] += 1
        try:
            # Check if test function is async
            if asyncio.iscoroutinefunction(test_func):
                result = test_func()  # Don't run with asyncio.run since we're already in async context
            else:
                result = test_func()
            
            # If it's a coroutine, await it
            if asyncio.iscoroutine(result):
                result = await result
            
            if result:
                logger.info(f"✅ {test_name}: PASSED")
                test_results["passed_tests"] += 1
                test_results["test_details"].append({"name": test_name, "status": "PASSED"})
            else:
                logger.error(f"❌ {test_name}: FAILED")
                test_results["failed_tests"] += 1
                test_results["test_details"].append({"name": test_name, "status": "FAILED"})
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {str(e)}")
            test_results["failed_tests"] += 1
            test_results["test_details"].append({"name": test_name, "status": "ERROR", "error": str(e)})
    
    # Test 1: Import Slack events handler
    def test_import_slack_events():
        try:
            from slack_events_handler import slack_events_bp, init_slack_events_db
            return True
        except ImportError:
            return False
    
    # Test 2: Import enhanced Slack API
    def test_import_enhanced_api():
        try:
            from slack_enhanced_api_complete import slack_enhanced_api_bp
            return True
        except ImportError:
            return False
    
    # Test 3: Import enhanced Slack service
    def test_import_enhanced_service():
        try:
            from slack_enhanced_service_complete import SlackEnhancedService
            return True
        except ImportError:
            return False
    
    # Test 4: Import original Slack service
    def test_import_original_service():
        try:
            from slack_enhanced_service import SlackEnhancedService
            return True
        except ImportError:
            return False
    
    # Test 5: Import Slack OAuth handler
    def test_import_slack_oauth():
        try:
            from slack_oauth_handler import (
                get_authorization_url, 
                exchange_code_for_tokens,
                verify_slack_request
            )
            return True
        except ImportError:
            return False
    
    # Test 6: Import Slack database operations
    def test_import_slack_db():
        try:
            from db_oauth_slack import (
                init_slack_oauth_table,
                save_slack_tokens,
                get_slack_tokens
            )
            return True
        except ImportError:
            return False
    
    # Test 7: Check environment variables
    def test_environment_vars():
        required_vars = ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"]
        optional_vars = ["SLACK_SIGNING_SECRET", "SLACK_BOT_TOKEN"]
        
        missing_required = []
        for var in required_vars:
            if not os.getenv(var):
                missing_required.append(var)
        
        if missing_required:
            logger.warning(f"Missing required env vars: {missing_required}")
            return False
        
        missing_optional = []
        for var in optional_vars:
            if not os.getenv(var):
                missing_optional.append(var)
        
        if missing_optional:
            logger.info(f"Missing optional env vars: {missing_optional}")
        
        return True
    
    # Test 8: Check Flask app structure
    def test_flask_app_structure():
        try:
            from main_api_app import create_app
            app = create_app()
            
            # Check if blueprints are registered
            registered_blueprints = []
            for rule in app.url_map.iter_rules():
                if 'slack' in rule.rule:
                    registered_blueprints.append(rule.rule)
            
            return len(registered_blueprints) > 0
        except Exception:
            return False
    
    # Run all tests
    logger.info("🚀 Starting Slack Integration Tests...")
    logger.info("=" * 50)
    
    run_test("Import Slack Events Handler", test_import_slack_events)
    run_test("Import Enhanced Slack API", test_import_enhanced_api)
    run_test("Import Enhanced Slack Service", test_import_enhanced_service)
    run_test("Import Original Slack Service", test_import_original_service)
    run_test("Import Slack OAuth Handler", test_import_slack_oauth)
    run_test("Import Slack Database Operations", test_import_slack_db)
    run_test("Check Environment Variables", test_environment_vars)
    run_test("Check Flask App Structure", test_flask_app_structure)
    
    # Print results
    logger.info("=" * 50)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info(f"Total Tests: {test_results['total_tests']}")
    logger.info(f"Passed: {test_results['passed_tests']}")
    logger.info(f"Failed: {test_results['failed_tests']}")
    
    success_rate = (test_results['passed_tests'] / test_results['total_tests']) * 100 if test_results['total_tests'] > 0 else 0
    logger.info(f"Success Rate: {success_rate:.1f}%")
    
    if test_results['failed_tests'] > 0:
        logger.info("\n❌ FAILED TESTS:")
        for test in test_results['test_details']:
            if test['status'] in ['FAILED', 'ERROR']:
                logger.info(f"  - {test['name']}: {test.get('error', 'Test failed')}")
    
    # Save results to file
    results_file = "slack_integration_test_results.json"
    try:
        with open(results_file, 'w') as f:
            json.dump(test_results, f, indent=2, default=str)
        logger.info(f"\n📁 Detailed results saved to: {results_file}")
    except Exception as e:
        logger.error(f"Failed to save results: {e}")
    
    return test_results

async def main():
    """Main test runner"""
    try:
        results = await test_slack_services()
        
        # Exit with appropriate code
        if results['failed_tests'] == 0:
            logger.info("\n🎉 All tests passed! Slack integration is ready.")
            sys.exit(0)
        else:
            logger.error(f"\n💥 {results['failed_tests']} tests failed. Please check the issues above.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())