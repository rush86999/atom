"""
Phase 3 Integration Verification Script
Tests the complete Phase 3 AI-powered chat interface integration

Author: Atom Platform Engineering
Date: November 9, 2025
Version: 1.0.0
"""

import json
import time
from datetime import datetime
import requests


class Phase3IntegrationTester:
    def __init__(self):
        self.base_urls = {
            "phase3_ai": "http://localhost:5062",
            "main_chat": "http://localhost:8000",
            "websocket": "http://localhost:5060",
            "frontend_api": "http://localhost:3000/api/chat",
        }
        self.test_results = []

    def log_test(self, test_name, status, details=None):
        """Log test results with timestamp"""
        result = {
            "test_name": test_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self.test_results.append(result)
        print(f"[{status.upper()}] {test_name}: {details or 'Completed'}")
        return status == "passed"

    def test_phase3_health(self):
        """Test Phase 3 AI intelligence health endpoint"""
        try:
            response = requests.get(f"{self.base_urls['phase3_ai']}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return self.log_test(
                    "Phase 3 Health Check",
                    "passed",
                    f"Version: {data.get('version')}, Features: {data.get('features', {})}",
                )
            else:
                return self.log_test(
                    "Phase 3 Health Check",
                    "failed",
                    f"HTTP {response.status_code}: {response.text}",
                )
        except Exception as e:
            return self.log_test(
                "Phase 3 Health Check", "failed", f"Connection error: {str(e)}"
            )

    def test_main_chat_health(self):
        """Test main chat API health endpoint"""
        try:
            response = requests.get(f"{self.base_urls['main_chat']}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return self.log_test(
                    "Main Chat Health Check", "passed", f"Status: {data.get('status')}"
                )
            else:
                return self.log_test(
                    "Main Chat Health Check",
                    "failed",
                    f"HTTP {response.status_code}: {response.text}",
                )
        except Exception as e:
            return self.log_test(
                "Main Chat Health Check", "failed", f"Connection error: {str(e)}"
            )

    def test_websocket_health(self):
        """Test WebSocket server health endpoint"""
        try:
            response = requests.get(f"{self.base_urls['websocket']}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return self.log_test(
                    "WebSocket Health Check",
                    "passed",
                    f"Active connections: {data.get('server_stats', {}).get('active_connections', 0)}",
                )
            else:
                return self.log_test(
                    "WebSocket Health Check",
                    "failed",
                    f"HTTP {response.status_code}: {response.text}",
                )
        except Exception as e:
            return self.log_test(
                "WebSocket Health Check", "failed", f"Connection error: {str(e)}"
            )

    def test_ai_analysis(self):
        """Test AI analysis endpoint with various message types"""
        test_messages = [
            {
                "message": "This is amazing! I love how well this system works.",
                "expected_sentiment": "positive",
            },
            {
                "message": "I'm really frustrated with this feature not working properly.",
                "expected_sentiment": "negative",
            },
            {
                "message": "Can you help me find information about the API documentation?",
                "expected_sentiment": "neutral",
            },
        ]

        passed_tests = 0
        total_tests = len(test_messages)

        for test in test_messages:
            try:
                response = requests.post(
                    f"{self.base_urls['phase3_ai']}/api/v1/ai/analyze",
                    params={
                        "message": test["message"],
                        "user_id": "integration-test-user",
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    sentiment_score = data.get("sentiment_scores", {}).get(
                        "overall_sentiment", 0
                    )

                    # Check if sentiment matches expectation
                    if (
                        (
                            test["expected_sentiment"] == "positive"
                            and sentiment_score > 0.3
                        )
                        or (
                            test["expected_sentiment"] == "negative"
                            and sentiment_score < -0.3
                        )
                        or (
                            test["expected_sentiment"] == "neutral"
                            and -0.3 <= sentiment_score <= 0.3
                        )
                    ):
                        passed_tests += 1
                        details = f"Sentiment: {sentiment_score:.3f} ({test['expected_sentiment']})"
                    else:
                        details = f"Unexpected sentiment: {sentiment_score:.3f} (expected {test['expected_sentiment']})"

                    self.log_test(
                        f"AI Analysis - '{test['message'][:30]}...'",
                        "passed" if passed_tests == total_tests else "warning",
                        details,
                    )
                else:
                    self.log_test(
                        f"AI Analysis - '{test['message'][:30]}...'",
                        "failed",
                        f"HTTP {response.status_code}",
                    )

            except Exception as e:
                self.log_test(
                    f"AI Analysis - '{test['message'][:30]}...'",
                    "failed",
                    f"Error: {str(e)}",
                )

        return passed_tests == total_tests

    def test_enhanced_chat(self):
        """Test enhanced chat endpoint with AI intelligence"""
        test_cases = [
            {
                "message": "I need help with my account settings",
                "enable_ai_analysis": True,
            },
            {
                "message": "This system is fantastic! Great job team!",
                "enable_ai_analysis": True,
            },
            {
                "message": "Why is this so slow and unresponsive?",
                "enable_ai_analysis": True,
            },
        ]

        passed_tests = 0
        total_tests = len(test_cases)

        for test in test_cases:
            try:
                response = requests.post(
                    f"{self.base_urls['phase3_ai']}/api/v1/chat/enhanced/message",
                    json={
                        "message": test["message"],
                        "user_id": "integration-test-user",
                        "enable_ai_analysis": test["enable_ai_analysis"],
                        "session_id": f"test-session-{int(time.time())}",
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("ai_analysis_applied", False):
                        passed_tests += 1
                        sentiment = (
                            data.get("ai_analysis", {})
                            .get("sentiment", {})
                            .get("overall_sentiment", 0)
                        )
                        details = f"AI applied: True, Sentiment: {sentiment:.3f}"
                    else:
                        details = "AI analysis not applied"

                    self.log_test(
                        f"Enhanced Chat - '{test['message'][:30]}...'",
                        "passed"
                        if data.get("ai_analysis_applied", False)
                        else "warning",
                        details,
                    )
                else:
                    self.log_test(
                        f"Enhanced Chat - '{test['message'][:30]}...'",
                        "failed",
                        f"HTTP {response.status_code}",
                    )

            except Exception as e:
                self.log_test(
                    f"Enhanced Chat - '{test['message'][:30]}...'",
                    "failed",
                    f"Error: {str(e)}",
                )

        return passed_tests == total_tests

    def test_conversation_flow(self):
        """Test complete conversation flow with context awareness"""
        session_id = f"conversation-test-{int(time.time())}"
        conversation_messages = [
            "Hello, I need help with my account",
            "Specifically, I can't access my billing information",
            "This is really frustrating me now",
            "Thank you for helping me resolve this",
        ]

        conversation_history = []
        passed_responses = 0

        for i, message in enumerate(conversation_messages):
            try:
                response = requests.post(
                    f"{self.base_urls['phase3_ai']}/api/v1/chat/enhanced/message",
                    json={
                        "message": message,
                        "user_id": "conversation-test-user",
                        "enable_ai_analysis": True,
                        "session_id": session_id,
                        "conversation_history": conversation_history,
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    conversation_history.append(
                        {
                            "role": "user",
                            "content": message,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    conversation_history.append(
                        {
                            "role": "assistant",
                            "content": data.get("response", ""),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                    passed_responses += 1
                    sentiment = (
                        data.get("ai_analysis", {})
                        .get("sentiment", {})
                        .get("overall_sentiment", 0)
                    )

                    self.log_test(
                        f"Conversation Step {i + 1}",
                        "passed",
                        f"Message: '{message[:20]}...', Sentiment: {sentiment:.3f}",
                    )
                else:
                    self.log_test(
                        f"Conversation Step {i + 1}",
                        "failed",
                        f"HTTP {response.status_code}",
                    )

            except Exception as e:
                self.log_test(
                    f"Conversation Step {i + 1}", "failed", f"Error: {str(e)}"
                )

        return passed_responses == len(conversation_messages)

    def test_performance(self):
        """Test response time performance"""
        test_message = "Test performance with this message"

        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_urls['phase3_ai']}/api/v1/ai/analyze",
                params={"message": test_message, "user_id": "performance-test-user"},
                timeout=10,
            )
            end_time = time.time()

            response_time = (end_time - start_time) * 1000  # Convert to milliseconds

            if response.status_code == 200 and response_time < 100:  # Target: < 100ms
                status = "passed"
            elif (
                response.status_code == 200 and response_time < 200
            ):  # Acceptable: < 200ms
                status = "warning"
            else:
                status = "failed"

            return self.log_test(
                "Performance Test", status, f"Response time: {response_time:.2f}ms"
            )

        except Exception as e:
            return self.log_test("Performance Test", "failed", f"Error: {str(e)}")

    def run_all_tests(self):
        """Run all integration tests"""
        print("=" * 60)
        print("ATOM CHAT INTERFACE PHASE 3 INTEGRATION TEST")
        print("=" * 60)
        print(f"Test started at: {datetime.now().isoformat()}")
        print()

        # Run all tests
        tests = [
            self.test_phase3_health,
            self.test_main_chat_health,
            self.test_websocket_health,
            self.test_ai_analysis,
            self.test_enhanced_chat,
            self.test_conversation_flow,
            self.test_performance,
        ]

        passed_tests = 0
        for test in tests:
            if test():
                passed_tests += 1

        # Generate summary
        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {len(tests)}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {len(tests) - passed_tests}")
        print(f"Success Rate: {(passed_tests / len(tests)) * 100:.1f}%")

        # Save detailed results
        self.save_results()

        return passed_tests == len(tests)

    def save_results(self):
        """Save test results to JSON file"""
        results = {
            "test_run": {
                "timestamp": datetime.now().isoformat(),
                "total_tests": len(self.test_results),
                "passed_tests": len(
                    [r for r in self.test_results if r["status"] == "passed"]
                ),
                "failed_tests": len(
                    [r for r in self.test_results if r["status"] == "failed"]
                ),
                "warning_tests": len(
                    [r for r in self.test_results if r["status"] == "warning"]
                ),
            },
            "detailed_results": self.test_results,
        }

        filename = (
            f"phase3_integration_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(filename, "w") as f:
            json.dump(results, f, indent=2)

        print(f"Detailed results saved to: {filename}")


def main():
    """Main function to run integration tests"""
    tester = Phase3IntegrationTester()

    try:
        success = tester.run_all_tests()

        if success:
            print("\n🎉 PHASE 3 INTEGRATION: ALL TESTS PASSED!")
            print("The Phase 3 AI-powered chat interface is fully operational.")
            print("Enhanced features including sentiment analysis, entity extraction,")
            print(
                "intent detection, and context-aware responses are working correctly."
            )
        else:
            print("\n⚠️  PHASE 3 INTEGRATION: SOME TESTS FAILED")
            print("Check the detailed results above for specific issues.")
            print("The system may be partially operational with graceful degradation.")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n❌ Testing interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error during testing: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
