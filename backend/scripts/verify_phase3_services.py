"""
Phase 3 Services Verification Script
Verifies all Phase 3 AI-powered chat interface services are running properly

Author: Atom Platform Engineering
Date: November 9, 2025
Version: 1.0.0
"""

import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests


class Phase3ServiceVerifier:
    def __init__(self):
        self.services = {
            "phase3_ai_intelligence": {
                "url": "http://localhost:5062",
                "port": 5062,
                "endpoints": [
                    "/health",
                    "/api/v1/ai/analyze",
                    "/api/v1/chat/enhanced/message",
                ],
                "required": True,
            },
            "main_chat_api": {
                "url": "http://localhost:5059",
                "port": 5059,
                "endpoints": ["/health"],
                "required": True,
            },
            "websocket_server": {
                "url": "http://localhost:5060",
                "port": 5060,
                "endpoints": ["/health"],
                "required": True,
            },
            "monitoring_dashboard": {
                "url": "http://localhost:5063",
                "port": 5063,
                "endpoints": ["/health", "/api/health"],
                "required": False,
            },
            "feedback_collection": {
                "url": "http://localhost:5064",
                "port": 5064,
                "endpoints": ["/health"],
                "required": False,
            },
        }

        self.verification_results = []
        self.overall_status = "UNKNOWN"

    def check_service_health(self, service_name: str, service_config: dict) -> Dict:
        """Check health of a specific service"""
        results = {
            "service": service_name,
            "status": "UNKNOWN",
            "response_time": 0,
            "details": {},
            "errors": [],
        }

        start_time = time.time()

        try:
            # Check main health endpoint
            health_url = f"{service_config['url']}/health"
            response = requests.get(health_url, timeout=5)
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                results["status"] = "HEALTHY"
                results["response_time"] = response_time
                results["details"] = response.json()

                # Check additional endpoints
                endpoint_results = []
                for endpoint in service_config["endpoints"][1:]:  # Skip health endpoint
                    try:
                        endpoint_url = f"{service_config['url']}{endpoint}"
                        endpoint_response = requests.get(endpoint_url, timeout=3)
                        endpoint_results.append(
                            {
                                "endpoint": endpoint,
                                "status_code": endpoint_response.status_code,
                                "healthy": endpoint_response.status_code == 200,
                            }
                        )
                    except Exception as e:
                        endpoint_results.append(
                            {
                                "endpoint": endpoint,
                                "status_code": "ERROR",
                                "healthy": False,
                                "error": str(e),
                            }
                        )

                results["endpoint_checks"] = endpoint_results

            else:
                results["status"] = "UNHEALTHY"
                results["errors"].append(
                    f"HTTP {response.status_code}: {response.text}"
                )

        except requests.exceptions.ConnectionError:
            results["status"] = "UNAVAILABLE"
            results["errors"].append("Connection refused - service may not be running")
        except requests.exceptions.Timeout:
            results["status"] = "TIMEOUT"
            results["errors"].append("Request timed out")
        except Exception as e:
            results["status"] = "ERROR"
            results["errors"].append(f"Unexpected error: {str(e)}")

        return results

    def test_ai_analysis(self) -> Dict:
        """Test AI analysis functionality"""
        test_cases = [
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

        results = {
            "total_tests": len(test_cases),
            "passed_tests": 0,
            "failed_tests": 0,
            "test_details": [],
        }

        for test_case in test_cases:
            test_result = {
                "message": test_case["message"],
                "status": "UNKNOWN",
                "response_time": 0,
                "sentiment_score": 0,
                "expected_sentiment": test_case["expected_sentiment"],
                "details": {},
            }

            try:
                start_time = time.time()
                response = requests.post(
                    f"{self.services['phase3_ai_intelligence']['url']}/api/v1/ai/analyze",
                    params={
                        "message": test_case["message"],
                        "user_id": "verification-test-user",
                    },
                    timeout=10,
                )
                response_time = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    sentiment_score = data.get("sentiment_scores", {}).get(
                        "overall_sentiment", 0
                    )

                    # Check if sentiment matches expectation
                    if (
                        (
                            test_case["expected_sentiment"] == "positive"
                            and sentiment_score > 0.3
                        )
                        or (
                            test_case["expected_sentiment"] == "negative"
                            and sentiment_score < -0.3
                        )
                        or (
                            test_case["expected_sentiment"] == "neutral"
                            and -0.3 <= sentiment_score <= 0.3
                        )
                    ):
                        test_result["status"] = "PASSED"
                        results["passed_tests"] += 1
                    else:
                        test_result["status"] = "FAILED"
                        results["failed_tests"] += 1

                    test_result["response_time"] = response_time
                    test_result["sentiment_score"] = sentiment_score
                    test_result["details"] = {
                        "analysis_id": data.get("analysis_id"),
                        "intents": data.get("intents", []),
                        "entities": data.get("entities", []),
                    }

                else:
                    test_result["status"] = "ERROR"
                    test_result["details"] = {"error": f"HTTP {response.status_code}"}
                    results["failed_tests"] += 1

            except Exception as e:
                test_result["status"] = "ERROR"
                test_result["details"] = {"error": str(e)}
                results["failed_tests"] += 1

            results["test_details"].append(test_result)

        return results

    def test_enhanced_chat(self) -> Dict:
        """Test enhanced chat functionality"""
        test_message = "I need help with my account settings and I'm feeling frustrated"

        results = {
            "status": "UNKNOWN",
            "response_time": 0,
            "ai_analysis_applied": False,
            "sentiment_detected": 0,
            "details": {},
        }

        try:
            start_time = time.time()
            response = requests.post(
                f"{self.services['phase3_ai_intelligence']['url']}/api/v1/chat/enhanced/message",
                json={
                    "message": test_message,
                    "user_id": "verification-test-user",
                    "enable_ai_analysis": True,
                    "session_id": f"verification-session-{int(time.time())}",
                },
                timeout=10,
            )
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                results["status"] = "SUCCESS"
                results["response_time"] = response_time
                results["ai_analysis_applied"] = data.get("ai_analysis_applied", False)
                results["sentiment_detected"] = (
                    data.get("ai_analysis", {})
                    .get("sentiment", {})
                    .get("overall_sentiment", 0)
                )
                results["details"] = {
                    "conversation_id": data.get("conversation_id"),
                    "response": data.get("response"),
                    "enhanced_suggestions": data.get("enhanced_suggestions", []),
                }
            else:
                results["status"] = "ERROR"
                results["details"] = {
                    "error": f"HTTP {response.status_code}: {response.text}"
                }

        except Exception as e:
            results["status"] = "ERROR"
            results["details"] = {"error": str(e)}

        return results

    def verify_all_services(self) -> Dict:
        """Verify all Phase 3 services"""
        print("🔍 Verifying Phase 3 Services...")
        print("=" * 60)

        overall_results = {
            "timestamp": datetime.now().isoformat(),
            "services": {},
            "functionality_tests": {},
            "overall_status": "UNKNOWN",
            "summary": {
                "total_services": len(self.services),
                "healthy_services": 0,
                "unhealthy_services": 0,
                "unavailable_services": 0,
            },
        }

        # Check service health
        for service_name, service_config in self.services.items():
            print(f"Checking {service_name}...")
            health_result = self.check_service_health(service_name, service_config)
            overall_results["services"][service_name] = health_result

            # Update summary counts
            if health_result["status"] == "HEALTHY":
                overall_results["summary"]["healthy_services"] += 1
            elif health_result["status"] in ["UNHEALTHY", "ERROR"]:
                overall_results["summary"]["unhealthy_services"] += 1
            elif health_result["status"] in ["UNAVAILABLE", "TIMEOUT"]:
                overall_results["summary"]["unavailable_services"] += 1

            # Print service status
            status_icon = "✅" if health_result["status"] == "HEALTHY" else "❌"
            print(
                f"  {status_icon} {service_name}: {health_result['status']} ({health_result['response_time']:.2f}ms)"
            )

            if health_result["errors"]:
                for error in health_result["errors"]:
                    print(f"    ⚠️  {error}")

        print("\n" + "=" * 60)
        print("🧪 Testing AI Functionality...")

        # Test AI analysis if Phase 3 AI is healthy
        if overall_results["services"]["phase3_ai_intelligence"]["status"] == "HEALTHY":
            ai_test_results = self.test_ai_analysis()
            overall_results["functionality_tests"]["ai_analysis"] = ai_test_results

            print(
                f"  AI Analysis: {ai_test_results['passed_tests']}/{ai_test_results['total_tests']} tests passed"
            )
            for test_detail in ai_test_results["test_details"]:
                icon = "✅" if test_detail["status"] == "PASSED" else "❌"
                print(
                    f"    {icon} '{test_detail['message'][:30]}...': {test_detail['status']} (score: {test_detail['sentiment_score']:.3f})"
                )

            # Test enhanced chat
            chat_results = self.test_enhanced_chat()
            overall_results["functionality_tests"]["enhanced_chat"] = chat_results

            chat_icon = "✅" if chat_results["status"] == "SUCCESS" else "❌"
            print(
                f"  {chat_icon} Enhanced Chat: {chat_results['status']} ({chat_results['response_time']:.2f}ms)"
            )
            if chat_results["ai_analysis_applied"]:
                print(
                    f"    🤖 AI Analysis Applied: Yes (sentiment: {chat_results['sentiment_detected']:.3f})"
                )

        # Determine overall status
        required_services_healthy = all(
            service_result["status"] == "HEALTHY"
            for service_name, service_result in overall_results["services"].items()
            if self.services[service_name]["required"]
        )

        if required_services_healthy:
            overall_results["overall_status"] = "HEALTHY"
            self.overall_status = "HEALTHY"
        else:
            overall_results["overall_status"] = "DEGRADED"
            self.overall_status = "DEGRADED"

        return overall_results

    def generate_report(self, results: Dict):
        """Generate verification report"""
        print("\n" + "=" * 60)
        print("📊 VERIFICATION REPORT")
        print("=" * 60)

        # Service Summary
        print(f"Services Checked: {results['summary']['total_services']}")
        print(f"✅ Healthy: {results['summary']['healthy_services']}")
        print(f"❌ Unhealthy: {results['summary']['unhealthy_services']}")
        print(f"🔴 Unavailable: {results['summary']['unavailable_services']}")

        # Overall Status
        status_icon = "✅" if results["overall_status"] == "HEALTHY" else "⚠️"
        print(f"\n{status_icon} Overall Status: {results['overall_status']}")

        # Performance Summary
        if "functionality_tests" in results:
            ai_tests = results["functionality_tests"].get("ai_analysis", {})
            if ai_tests:
                success_rate = (
                    ai_tests["passed_tests"] / ai_tests["total_tests"]
                ) * 100
                print(f"🧠 AI Analysis Success Rate: {success_rate:.1f}%")

            chat_test = results["functionality_tests"].get("enhanced_chat", {})
            if chat_test.get("status") == "SUCCESS":
                print(
                    f"💬 Enhanced Chat Response Time: {chat_test['response_time']:.2f}ms"
                )

        # Recommendations
        print("\n💡 Recommendations:")
        if results["overall_status"] == "HEALTHY":
            print("  ✅ All systems operational - Phase 3 deployment successful!")
            print("  📈 Monitor performance metrics and user feedback")
            print("  🚀 Proceed with frontend integration and user training")
        else:
            print("  🔧 Check service logs for errors")
            print("  🔄 Restart any unavailable services")
            print("  📋 Review deployment configuration")
            print("  🆘 Contact engineering support if issues persist")

        print(f"\n📅 Report Generated: {results['timestamp']}")
        print("=" * 60)

    def save_results(self, results: Dict):
        """Save verification results to file"""
        filename = (
            f"phase3_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(filename, "w") as f:
            json.dump(results, f, indent=2)
        print(f"📄 Detailed results saved to: {filename}")

    def run_verification(self):
        """Run complete verification process"""
        try:
            results = self.verify_all_services()
            self.generate_report(results)
            self.save_results(results)

            # Return appropriate exit code
            return 0 if self.overall_status == "HEALTHY" else 1

        except KeyboardInterrupt:
            print("\n❌ Verification interrupted by user")
            return 1
        except Exception as e:
            print(f"\n💥 Unexpected error during verification: {e}")
            return 1


def main():
    """Main function"""
    verifier = Phase3ServiceVerifier()
    exit_code = verifier.run_verification()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
