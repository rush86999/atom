"""
Main E2E Test Runner for Atom Platform
Coordinates end-to-end testing across all features with credential validation
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from colorama import Fore, Style, init

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.test_config import TestConfig
import os
from utils.llm_verifier import LLMVerifier
from utils.glm_verifier import GLMVerifier

# Initialize colorama for colored output
init(autoreset=True)


class E2ETestRunner:
    """Main E2E test runner for Atom platform"""

    def __init__(self):
        self.config = TestConfig()
        self.llm_verifier = None
        self.test_results = {}
        self.start_time = None
        self.end_time = None

    def initialize_llm_verifier(self) -> bool:
        """Initialize LLM verifier if credentials are available"""
        try:
            # Check if we should use DeepSeek
            use_deepseek = os.getenv("USE_DEEPSEEK_VALIDATOR", "false").lower() == "true"
            # Check if we should use GLM instead of OpenAI
            use_glm = os.getenv("USE_GLM_VALIDATOR", "false").lower() == "true"

            if use_deepseek:
                deepseek_key = os.getenv("DEEPSEEK_API_KEY")
                if not deepseek_key:
                    raise ValueError("DEEPSEEK_API_KEY not found")
                
                self.llm_verifier = LLMVerifier(
                    api_key=deepseek_key,
                    base_url="https://api.deepseek.com",
                    model="deepseek-chat"
                )
                print(f"{Fore.CYAN}Using DeepSeek (deepseek-chat) for AI validation{Style.RESET_ALL}")
            elif use_glm:
                self.llm_verifier = GLMVerifier()
                print(f"{Fore.CYAN}Using GLM 4.6 for AI validation{Style.RESET_ALL}")
            else:
                self.llm_verifier = LLMVerifier()
                print(f"{Fore.CYAN}Using OpenAI for AI validation{Style.RESET_ALL}")
            return True
        except ValueError as e:
            print(
                f"{Fore.YELLOW}Warning: {e}. LLM verification will be skipped.{Style.RESET_ALL}"
            )
            return False

    def run_all_tests(self, categories: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run all E2E tests for specified categories

        Args:
            categories: List of test categories to run, or None for all available

        Returns:
            Comprehensive test results
        """
        self.start_time = datetime.now()
        print(f"{Fore.CYAN}[START] Starting Atom Platform E2E Tests{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Start Time: {self.start_time}{Style.RESET_ALL}")
        print("-" * 80)

        # Initialize LLM verifier
        llm_available = self.initialize_llm_verifier()

        # Determine which categories to test
        if categories is None:
            categories = self.config.get_test_categories_with_credentials()

        if not categories:
            print(
                f"{Fore.RED}[ERROR] No test categories have all required credentials{Style.RESET_ALL}"
            )
            return {"error": "No testable categories available"}

        print(
            f"{Fore.GREEN}[TESTING] Testing Categories: {', '.join(categories)}{Style.RESET_ALL}"
        )

        # Run tests for each category
        for category in categories:
            print(
                f"\n{Fore.BLUE}[CAT] Testing Category: {category.upper()}{Style.RESET_ALL}"
            )
            self._run_category_tests(category)

        # Generate final report
        self.end_time = datetime.now()
        return self._generate_final_report(llm_available)

    def _run_category_tests(self, category: str):
        """Run tests for a specific category"""
        category_results = {
            "category": category,
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "test_details": {},
            "marketing_claims_verified": {},
            "start_time": datetime.now().isoformat(),
        }

        try:
            # Import and run category-specific tests
            test_module = self._import_test_module(category)
            if test_module:
                test_results = test_module.run_tests(self.config)
                category_results.update(test_results)
            else:
                category_results["error"] = (
                    f"No test module found for category: {category}"
                )

        except Exception as e:
            category_results["error"] = f"Category test failed: {str(e)}"
            print(f"{Fore.RED}[ERROR] Error in {category} tests: {str(e)}{Style.RESET_ALL}")

        # Verify marketing claims if LLM is available
        if self.llm_verifier and "test_outputs" in category_results:
            category_results["marketing_claims_verified"] = (
                self._verify_category_claims(category, category_results["test_outputs"])
            )

        self.test_results[category] = category_results
        self._print_category_summary(category, category_results)

    def _import_test_module(self, category: str):
        """Dynamically import test module for a category"""
        try:
            import sys
            import os
            # Add current directory to Python path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            module_name = f"tests.test_{category}"
            module = __import__(module_name, fromlist=["run_tests"])
            return module
        except ImportError as e:
            print(
                f"{Fore.YELLOW}[WARN] No specific test module for {category}: {e}{Style.RESET_ALL}"
            )
            return None

    def _verify_category_claims(
        self, category: str, test_outputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify marketing claims for a category using LLM"""
        # Map categories to relevant marketing claims
        claim_mapping = {
            "core": [
                "natural_language_workflow",
                "conversational_automation",
                "ai_memory",
                "production_ready",
            ],
            "communication": [
                "cross_platform_coordination",
                "conversational_automation",
            ],
            "productivity": [
                "cross_platform_coordination",
                "natural_language_workflow",
            ],
            "voice": [
                "voice_integration",
                "conversational_automation",
            ],
        }

        relevant_claims = claim_mapping.get(category, [])
        if not relevant_claims:
            return {}

        claims_to_verify = []
        for claim_key in relevant_claims:
            if claim_key in self.config.MARKETING_CLAIMS:
                claims_to_verify.append(self.config.MARKETING_CLAIMS[claim_key])

        if not claims_to_verify:
            return {}

        print(
            f"{Fore.MAGENTA}[AI] Verifying {len(claims_to_verify)} marketing claims for {category}{Style.RESET_ALL}"
        )

        try:
            return self.llm_verifier.batch_verify_claims(
                claims_to_verify, test_outputs, f"Category: {category}"
            )
        except Exception as e:
            print(
                f"{Fore.RED}[ERROR] LLM verification failed for {category}: {str(e)}{Style.RESET_ALL}"
            )
            return {"error": str(e)}


    def _print_category_summary(self, category: str, results: Dict[str, Any]):
        """Print summary for a test category"""
        tests_run = results.get("tests_run", 0)
        tests_passed = results.get("tests_passed", 0)
        tests_failed = results.get("tests_failed", 0)

        if tests_run == 0:
            status = f"{Fore.YELLOW}SKIPPED{Style.RESET_ALL}"
        elif tests_failed == 0:
            status = f"{Fore.GREEN}PASSED{Style.RESET_ALL}"
        else:
            status = f"{Fore.RED}FAILED{Style.RESET_ALL}"

        print(f"{Fore.CYAN}[SUMMARY] {category.upper()} Summary: {status}{Style.RESET_ALL}")
        print(
            f"   Tests Run: {tests_run}, Passed: {tests_passed}, Failed: {tests_failed}"
        )

        # Print marketing claim verification summary
        if (
            "marketing_claims_verified" in results
            and results["marketing_claims_verified"]
        ):
            verified_claims = sum(
                1
                for r in results["marketing_claims_verified"].values()
                if r.get("verified", False) and not r.get("error", False)
            )
            total_claims = len(results["marketing_claims_verified"])
            print(f"   Marketing Claims Verified: {verified_claims}/{total_claims}")

    def _generate_final_report(self, llm_available: bool) -> Dict[str, Any]:
        """Generate comprehensive final test report"""
        duration = (
            self.end_time - self.start_time
            if self.end_time and self.start_time
            else None
        )

        total_tests = 0
        total_passed = 0
        total_failed = 0
        verified_claims_count = 0
        total_claims_count = 0

        for category, results in self.test_results.items():
            total_tests += results.get("tests_run", 0)
            total_passed += results.get("tests_passed", 0)
            total_failed += results.get("tests_failed", 0)

            if "marketing_claims_verified" in results:
                category_claims = results["marketing_claims_verified"]
                verified_claims_count += sum(
                    1
                    for r in category_claims.values()
                    if r.get("verified", False) and not r.get("error", False)
                )
                total_claims_count += len(category_claims)

        # Calculate overall status
        if total_failed == 0 and total_tests > 0:
            overall_status = "PASSED"
            status_color = Fore.GREEN
        elif total_tests == 0:
            overall_status = "NO_TESTS"
            status_color = Fore.YELLOW
        else:
            overall_status = "FAILED"
            status_color = Fore.RED

        # Print final summary
        print(f"\n{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")
        print(f"{status_color}[COMPLETE] ATOM PLATFORM E2E TEST COMPLETE{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")
        print(f"Overall Status: {status_color}{overall_status}{Style.RESET_ALL}")
        print(f"Duration: {duration}")
        print(f"Total Tests: {total_tests}")
        print(f"Tests Passed: {Fore.GREEN}{total_passed}{Style.RESET_ALL}")
        print(f"Tests Failed: {Fore.RED}{total_failed}{Style.RESET_ALL}")

        if llm_available and total_claims_count > 0:
            print(
                f"Marketing Claims Verified: {Fore.GREEN}{verified_claims_count}/{total_claims_count}{Style.RESET_ALL}"
            )

        # Generate report data
        report = {
            "overall_status": overall_status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration.total_seconds() if duration else None,
            "total_tests": total_tests,
            "tests_passed": total_passed,
            "tests_failed": total_failed,
            "test_categories": list(self.test_results.keys()),
            "category_results": self.test_results,
            "llm_verification_available": llm_available,
            "marketing_claims_verified": {
                "total": total_claims_count,
                "verified": verified_claims_count,
                "verification_rate": verified_claims_count / total_claims_count
                if total_claims_count > 0
                else 0.0,
            },
        }

        # Save report to file
        self._save_report_to_file(report)

        return report

    def _save_report_to_file(self, report: Dict[str, Any]):
        """Save test report to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"e2e_test_report_{timestamp}.json"
        report_path = Path(__file__).parent / "reports" / report_filename

        # Create reports directory if it doesn't exist
        report_path.parent.mkdir(exist_ok=True)

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"{Fore.GREEN}[FILE] Test report saved to: {report_path}{Style.RESET_ALL}")

    def run_specific_test(self, category: str, test_name: str) -> Dict[str, Any]:
        """Run a specific test within a category"""
        print(
            f"{Fore.CYAN}[TEST] Running specific test: {category}.{test_name}{Style.RESET_ALL}"
        )

        try:
            test_module = self._import_test_module(category)
            if test_module and hasattr(test_module, test_name):
                test_function = getattr(test_module, test_name)
                return test_function(self.config)
            else:
                return {"error": f"Test {test_name} not found in category {category}"}
        except Exception as e:
            return {"error": f"Test execution failed: {str(e)}"}


def main():
    """Main entry point for E2E test runner"""
    runner = E2ETestRunner()

    # Check if specific categories are provided as command line arguments
    if len(sys.argv) > 1:
        categories = sys.argv[1:]
        print(
            f"{Fore.YELLOW}Running specific categories: {categories}{Style.RESET_ALL}"
        )
    else:
        categories = None

    # Run tests
    results = runner.run_all_tests(categories)

    # Exit with appropriate code
    if results.get("overall_status") == "PASSED":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
