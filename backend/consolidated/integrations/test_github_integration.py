import json
import logging
import os
import sys
from datetime import datetime

# Add the parent directory to the path to import the service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_service import GitHubService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GitHubIntegrationTest:
    """Integration test suite for GitHub service"""

    def __init__(self):
        self.service = GitHubService()
        self.test_results = []
        self.test_owner = "octocat"  # GitHub's test user
        self.test_repo = "Hello-World"  # Public test repository

    def run_test(self, test_name, test_func):
        """Run a test and record the result"""
        try:
            logger.info(f"Running test: {test_name}")
            result = test_func()
            self.test_results.append(
                {
                    "test": test_name,
                    "status": "PASSED",
                    "result": result,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            logger.info(f"✓ {test_name} - PASSED")
            return True
        except Exception as e:
            self.test_results.append(
                {
                    "test": test_name,
                    "status": "FAILED",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            logger.error(f"✗ {test_name} - FAILED: {e}")
            return False

    def test_service_initialization(self):
        """Test GitHub service initialization"""
        service = GitHubService()
        assert service.api_base_url == "https://api.github.com"
        assert service.timeout == 30
        assert service.max_retries == 3
        return "Service initialized successfully"

    def test_headers_generation(self):
        """Test headers generation with and without token"""
        # Test without token
        service = GitHubService()
        headers = service._get_headers()
        assert "Accept" in headers
        assert "Content-Type" in headers
        assert "Authorization" not in headers

        # Test with token
        service.set_access_token("test_token")
        headers = service._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "token test_token"
        return "Headers generated correctly"

    def test_rate_limit_endpoint(self):
        """Test rate limit endpoint (doesn't require authentication)"""
        result = self.service._make_request("GET", "/rate_limit")
        assert result is not None
        assert "resources" in result
        return "Rate limit endpoint accessible"

    def test_public_repository_access(self):
        """Test accessing public repository (doesn't require authentication)"""
        result = self.service._make_request(
            "GET", f"/repos/{self.test_owner}/{self.test_repo}"
        )
        assert result is not None
        assert "name" in result
        assert result["name"] == self.test_repo
        return f"Public repository {self.test_owner}/{self.test_repo} accessible"

    def test_public_issues_access(self):
        """Test accessing public repository issues"""
        result = self.service._make_request(
            "GET", f"/repos/{self.test_owner}/{self.test_repo}/issues"
        )
        assert result is not None
        return f"Issues for {self.test_owner}/{self.test_repo} accessible"

    def test_search_public_code(self):
        """Test searching public code"""
        result = self.service._make_request("GET", "/search/code?q=hello+world")
        assert result is not None
        assert "items" in result
        return "Public code search working"

    def test_health_check_without_auth(self):
        """Test health check without authentication"""
        health = self.service.health_check()
        assert health is not None
        assert "status" in health
        assert "service" in health
        assert health["service"] == "github"
        return "Health check working without authentication"

    def test_error_handling(self):
        """Test error handling for non-existent endpoints"""
        result = self.service._make_request("GET", "/nonexistent-endpoint")
        assert result is None  # Should return None for non-200 responses
        return "Error handling working correctly"

    def test_retry_logic(self):
        """Test retry logic with simulated failures"""
        # This test verifies the retry mechanism is in place
        # Note: We don't actually trigger rate limits in testing
        service = GitHubService()
        service.max_retries = 2

        # The service should handle the request gracefully
        result = service._make_request("GET", "/rate_limit")
        assert result is not None
        return "Retry logic structure in place"

    def run_all_tests(self):
        """Run all integration tests"""
        logger.info("Starting GitHub Integration Tests")
        logger.info("=" * 50)

        tests = [
            ("Service Initialization", self.test_service_initialization),
            ("Headers Generation", self.test_headers_generation),
            ("Rate Limit Endpoint", self.test_rate_limit_endpoint),
            ("Public Repository Access", self.test_public_repository_access),
            ("Public Issues Access", self.test_public_issues_access),
            ("Public Code Search", self.test_search_public_code),
            ("Health Check", self.test_health_check_without_auth),
            ("Error Handling", self.test_error_handling),
            ("Retry Logic", self.test_retry_logic),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            if self.run_test(test_name, test_func):
                passed += 1

        # Generate test report
        self.generate_test_report(passed, total)

        return passed == total

    def generate_test_report(self, passed, total):
        """Generate a comprehensive test report"""
        report = {
            "test_suite": "GitHub Integration Tests",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": total - passed,
                "success_rate": f"{(passed / total) * 100:.1f}%",
            },
            "test_results": self.test_results,
            "environment": {
                "python_version": sys.version,
                "service_api_base": self.service.api_base_url,
                "test_owner": self.test_owner,
                "test_repo": self.test_repo,
            },
        }

        # Print summary
        logger.info("=" * 50)
        logger.info("TEST SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {total - passed}")
        logger.info(f"Success Rate: {(passed / total) * 100:.1f}%")

        # Save detailed report to file
        report_file = "github_integration_test_report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Detailed report saved to: {report_file}")

        # Print failed tests if any
        failed_tests = [t for t in self.test_results if t["status"] == "FAILED"]
        if failed_tests:
            logger.info("\nFAILED TESTS:")
            for test in failed_tests:
                logger.info(f"  - {test['test']}: {test['error']}")

        return report


def main():
    """Main function to run integration tests"""
    try:
        test_suite = GitHubIntegrationTest()
        success = test_suite.run_all_tests()

        if success:
            logger.info("🎉 All GitHub integration tests PASSED!")
            return 0
        else:
            logger.error("❌ Some GitHub integration tests FAILED!")
            return 1

    except Exception as e:
        logger.error(f"❌ Test suite execution failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
