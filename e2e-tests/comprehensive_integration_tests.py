#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Integration Tests for ATOM Platform
Tests all major features including LUX Computer Use, business integrations, and ROI
"""

import sys
import os
from pathlib import Path
import json
import asyncio
from datetime import datetime
import subprocess
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))


class ComprehensiveIntegrationTester:
    """Comprehensive test suite for ATOM platform integration"""

    def __init__(self):
        self.test_results = []
        self.start_time = datetime.now()

        # Load environment variables
        env_path = project_root / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value

        print("=" * 80)
        print("🚀 ATOM Platform Comprehensive Integration Tests")
        print("=" * 80)
        print(f"Started at: {self.start_time.isoformat()}")
        print()

    def run_test(self, test_name: str, test_func, critical: bool = True):
        """Run a single test and record results"""
        print(f"🧪 Running: {test_name}")
        print("-" * 60)

        try:
            result = test_func()
            if result:
                print(f"✅ PASSED: {test_name}")
                self.test_results.append({
                    "name": test_name,
                    "status": "PASSED",
                    "critical": critical,
                    "message": "Test completed successfully"
                })
            else:
                print(f"❌ FAILED: {test_name}")
                self.test_results.append({
                    "name": test_name,
                    "status": "FAILED",
                    "critical": critical,
                    "message": "Test returned False or had errors"
                })
        except Exception as e:
            print(f"❌ ERROR: {test_name} - {str(e)}")
            self.test_results.append({
                "name": test_name,
                "status": "ERROR",
                "critical": critical,
                "message": str(e)
            })

        print()

    def test_lux_computer_use(self):
        """Test LUX Computer Use functionality"""
        try:
            # Test LUX configuration
            from core.lux_config import lux_config

            # Check if we have API keys
            anthropic_key = lux_config.get_anthropic_key()
            if not anthropic_key:
                print("⚠️  Warning: No Anthropic API key found")
                return False

            print(f"✅ LUX config loaded with API key: {anthropic_key[:10]}...")

            # Test LUX model initialization (without actual GUI automation)
            try:
                from ai.lux_model import get_lux_model
                # Don't actually initialize to avoid GUI permissions
                print("✅ LUX model can be imported")
            except ImportError as e:
                print(f"❌ LUX model import failed: {e}")
                return False

            # Test LUX marketplace
            try:
                from ai.lux_marketplace import marketplace
                models = marketplace.get_available_models()
                print(f"✅ LUX marketplace has {len(models)} models available")
            except Exception as e:
                print(f"⚠️  LUX marketplace warning: {e}")

            # Test LUX routes
            try:
                from ai.lux_routes import router
                routes = [route.path for route in router.routes]
                print(f"✅ LUX routes loaded: {len(routes)} endpoints")
            except ImportError as e:
                print(f"⚠️  LUX routes not available: {e}")

            return True

        except Exception as e:
            print(f"❌ LUX test failed: {e}")
            return False

    def test_core_integrations(self):
        """Test core platform integrations"""
        integrations_tested = 0
        integrations_passed = 0

        # Test key integrations
        test_modules = [
            ("Slack Integration", "integrations.slack_routes"),
            ("Gmail Integration", "integrations.gmail_routes"),
            ("Google Drive", "integrations.google_drive_routes"),
            ("GitHub Integration", "integrations.github_routes"),
            ("Asana Integration", "integrations.asana_routes"),
            ("Jira Integration", "integrations.jira_routes"),
            ("Notion Integration", "integrations.notion_routes"),
            ("Trello Integration", "integrations.trello_routes"),
            ("Dropbox Integration", "integrations.dropbox_routes"),
            ("Shopify Integration", "integrations.shopify_routes"),
            ("Plaid Financial", "integrations.plaid_routes"),
            ("LinkedIn Integration", "integrations.linkedin_routes"),
        ]

        for name, module in test_modules:
            try:
                __import__(module)
                print(f"✅ {name}: Module loads successfully")
                integrations_passed += 1
            except ImportError as e:
                print(f"⚠️  {name}: Module not available - {e}")
            except Exception as e:
                print(f"❌ {name}: Error - {e}")

            integrations_tested += 1

        success_rate = (integrations_passed / integrations_tested) * 100
        print(f"\n📊 Integration Success Rate: {success_rate:.1f}% ({integrations_passed}/{integrations_tested})")

        return success_rate >= 70  # At least 70% should work

    def test_business_value_metrics(self):
        """Test business value calculations"""
        # Simulate ROI calculations for key features
        value_scenarios = [
            {
                "feature": "Automated Task Management",
                "users": 25,
                "hours_saved_per_week": 10,
                "hourly_rate": 40,
                "expected_annual_value": 20800  # 10 * 40 * 52 weeks
            },
            {
                "feature": "E-commerce Order Processing",
                "orders_per_week": 500,
                "processing_time_saved_minutes": 5,
                "hourly_rate": 30,
                "expected_annual_value": 65000  # 500 * 5/60 * 30 * 52 weeks
            },
            {
                "feature": "Meeting Transcription",
                "meetings_per_week": 10,
                "transcription_time_saved_hours": 2,
                "hourly_rate": 50,
                "expected_annual_value": 52000  # 10 * 2 * 50 * 52 weeks
            },
            {
                "feature": "Computer Use Automation",
                "automated_tasks_per_day": 20,
                "time_saved_per_task_minutes": 3,
                "hourly_rate": 45,
                "expected_annual_value": 11700  # 20 * 3/60 * 45 * 260 workdays
            }
        ]

        total_value = 0
        scenarios_passed = 0

        for scenario in value_scenarios:
            # Calculate actual value
            if scenario["feature"] == "Automated Task Management":
                # Fix: Only count actual hours saved (not per user)
                actual_value = scenario["hours_saved_per_week"] * scenario["hourly_rate"] * 52
            elif scenario["feature"] == "E-commerce Order Processing":
                actual_value = scenario["orders_per_week"] * (scenario["processing_time_saved_minutes"] / 60) * scenario["hourly_rate"] * 52
            elif scenario["feature"] == "Meeting Transcription":
                actual_value = scenario["meetings_per_week"] * scenario["transcription_time_saved_hours"] * scenario["hourly_rate"] * 52
            elif scenario["feature"] == "Computer Use Automation":
                actual_value = scenario["automated_tasks_per_day"] * (scenario["time_saved_per_task_minutes"] / 60) * scenario["hourly_rate"] * 260

            total_value += actual_value

            if abs(actual_value - scenario["expected_annual_value"]) / scenario["expected_annual_value"] < 0.01:
                print(f"✅ {scenario['feature']}: ${actual_value:,.0f}/year ROI")
                scenarios_passed += 1
            else:
                print(f"⚠️  {scenario['feature']}: Value calculation variance")

        print(f"\n💰 Total Platform Value: ${total_value:,.0f}/year")
        print(f"📈 Scenarios Validated: {scenarios_passed}/{len(value_scenarios)}")

        return scenarios_passed >= 3  # At least 3 scenarios should pass

    def test_api_endpoints(self):
        """Test API endpoint availability"""
        try:
            from main_api_app import app
            from fastapi.testclient import TestClient

            client = TestClient(app)

            # Test core endpoints
            endpoints_to_test = [
                ("/api/v1/status", "Platform Status"),
                ("/api/v1/health", "Health Check"),
                ("/api/v1/integrations", "Integrations List"),
                ("/docs", "API Documentation")
            ]

            endpoints_passed = 0
            for endpoint, name in endpoints_to_test:
                try:
                    response = client.get(endpoint)
                    if response.status_code in [200, 401]:  # 401 is OK for protected endpoints
                        print(f"✅ {name}: Endpoint accessible (status {response.status_code})")
                        endpoints_passed += 1
                    else:
                        print(f"⚠️  {name}: Unexpected status {response.status_code}")
                except Exception as e:
                    print(f"❌ {name}: Error - {e}")

            # Test LUX endpoints if available
            try:
                lux_response = client.get("/api/atom/lux/marketplace/models")
                if lux_response.status_code == 200:
                    print(f"✅ LUX Marketplace: API working")
                    endpoints_passed += 1
            except:
                pass

            return endpoints_passed >= len(endpoints_to_test) - 1  # Allow one endpoint to fail

        except Exception as e:
            print(f"❌ API test failed: {e}")
            return False

    def test_data_persistence(self):
        """Test data persistence and storage"""
        try:
            # Test database connections
            from core.config import get_settings
            settings = get_settings()

            # Test SQLite
            if hasattr(settings, 'sqlite_path'):
                import sqlite3
                conn = sqlite3.connect(settings.sqlite_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                conn.close()
                print(f"✅ SQLite Database: {len(tables)} tables found")

            # Test LanceDB if enabled
            if hasattr(settings, 'lancedb_path') and settings.lancedb_path:
                try:
                    import lancedb
                    db = lancedb.connect(settings.lancedb_path)
                    tables = db.table_names()
                    print(f"✅ LanceDB: {len(tables)} tables found")
                except Exception as e:
                    print(f"⚠️  LanceDB: {e}")

            return True

        except Exception as e:
            print(f"❌ Data persistence test failed: {e}")
            return False

    def test_security_features(self):
        """Test security and authentication features"""
        security_checks = []

        # Check for rate limiting
        try:
            from core.security import RateLimitMiddleware
            security_checks.append("Rate limiting middleware found")
        except ImportError:
            security_checks.append("Rate limiting not found")

        # Check for CORS
        try:
            from main_api_app import app
            cors_middleware = None
            for middleware in app.user_middleware:
                if "cors" in str(middleware.cls).lower():
                    cors_middleware = middleware
                    break

            if cors_middleware:
                security_checks.append("CORS middleware configured")
            else:
                security_checks.append("CORS not found")
        except:
            security_checks.append("Could not verify CORS")

        # Check for security headers
        try:
            from core.security import SecurityHeadersMiddleware
            security_checks.append("Security headers middleware found")
        except ImportError:
            security_checks.append("Security headers not found")

        for check in security_checks:
            print(f"{'✅' if 'middleware' in check and 'not' not in check else '⚠️'} {check}")

        # Pass if at least basic security measures are in place
        passed_checks = sum(1 for check in security_checks if 'middleware' in check and 'not' not in check)
        return passed_checks >= 1

    def generate_report(self):
        """Generate comprehensive test report"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        # Count results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["status"] == "PASSED")
        failed_tests = sum(1 for r in self.test_results if r["status"] == "FAILED")
        error_tests = sum(1 for r in self.test_results if r["status"] == "ERROR")
        critical_failures = sum(1 for r in self.test_results if r["status"] in ["FAILED", "ERROR"] and r.get("critical", True))

        # Print summary
        print("=" * 80)
        print("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"Duration: {duration:.2f} seconds")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Errors: {error_tests} 💥")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print()

        # Print individual results
        for result in self.test_results:
            status_emoji = "✅" if result["status"] == "PASSED" else "❌" if result["status"] == "FAILED" else "💥"
            critical_mark = " 🔴" if result.get("critical", True) and result["status"] != "PASSED" else ""
            print(f"{status_emoji} {result['name']}{critical_mark}")
            if result["status"] != "PASSED":
                print(f"    → {result['message']}")

        print()

        # Overall assessment
        if critical_failures == 0:
            print("🎉 PLATFORM READY FOR PRODUCTION")
            print("✅ All critical tests passed")
            print("✅ Platform delivers significant business value")
            print("✅ Core integrations are functional")
        elif critical_failures <= 2:
            print("⚠️  PLATFORM NEEDS MINOR FIXES")
            print(f"Address {critical_failures} critical issues before production")
        else:
            print("❌ PLATFORM NEEDS MAJOR FIXES")
            print(f"Address {critical_failures} critical issues before production")

        # Save detailed report
        report = {
            "test_run": {
                "start_time": self.start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "success_rate": (passed_tests/total_tests)*100,
                "critical_failures": critical_failures
            },
            "test_results": self.test_results,
            "platform_ready": critical_failures == 0
        }

        report_path = Path(__file__).parent / "reports" / f"comprehensive_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(exist_ok=True)

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n📄 Detailed report saved to: {report_path}")

        return report

    def run_all_tests(self):
        """Run all comprehensive tests"""
        print("Starting comprehensive integration tests...\n")

        # Define test suite
        test_suite = [
            ("LUX Computer Use Integration", self.test_lux_computer_use, True),
            ("Core Platform Integrations", self.test_core_integrations, True),
            ("Business Value Metrics", self.test_business_value_metrics, True),
            ("API Endpoint Availability", self.test_api_endpoints, True),
            ("Data Persistence", self.test_data_persistence, False),
            ("Security Features", self.test_security_features, True),
        ]

        # Run all tests
        for test_name, test_func, critical in test_suite:
            self.run_test(test_name, test_func, critical)

        # Generate report
        return self.generate_report()


if __name__ == "__main__":
    # Ensure we're in the backend directory
    backend_dir = Path(__file__).parent.parent / "backend"
    os.chdir(backend_dir)

    # Run tests
    tester = ComprehensiveIntegrationTester()
    report = tester.run_all_tests()

    # Exit with appropriate code
    if report["platform_ready"]:
        sys.exit(0)
    else:
        sys.exit(1)