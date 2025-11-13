import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import websocket
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CHAT_API_URL = "http://localhost:5059"
WEBSOCKET_URL = "ws://localhost:5060"
TEST_USER_ID = "test_user_001"
TEST_ROOM_ID = "test_room_001"


class ChatIntegrationTest:
    """Comprehensive test suite for chat interface integration"""

    def __init__(self):
        self.test_results = []
        self.websocket_connections = {}

    def log_test_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result with timestamp"""
        result = {
            "test_name": test_name,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}: {details}")

    async def test_chat_api_health(self):
        """Test chat API health endpoint"""
        try:
            response = requests.get(f"{CHAT_API_URL}/health")
            if response.status_code == 200:
                data = response.json()
                self.log_test_result(
                    "Chat API Health Check",
                    True,
                    f"Status: {data.get('status', 'unknown')}",
                )
                return True
            else:
                self.log_test_result(
                    "Chat API Health Check",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return False
        except Exception as e:
            self.log_test_result("Chat API Health Check", False, f"Exception: {e}")
            return False

    async def test_websocket_server_health(self):
        """Test WebSocket server health endpoint"""
        try:
            response = requests.get(
                f"{WEBSOCKET_URL.replace('ws://', 'http://')}/health"
            )
            if response.status_code == 200:
                data = response.json()
                self.log_test_result(
                    "WebSocket Server Health Check",
                    True,
                    f"Status: {data.get('status', 'unknown')}",
                )
                return True
            else:
                self.log_test_result(
                    "WebSocket Server Health Check",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return False
        except Exception as e:
            self.log_test_result(
                "WebSocket Server Health Check", False, f"Exception: {e}"
            )
            return False

    async def test_websocket_connection(self):
        """Test WebSocket connection and basic communication"""
        try:
            ws = websocket.create_connection(f"{WEBSOCKET_URL}/ws/{TEST_USER_ID}")

            # Test ping/pong
            ws.send(
                json.dumps({"type": "ping", "timestamp": datetime.now().isoformat()})
            )
            response = json.loads(ws.recv())

            if response.get("type") == "pong":
                self.log_test_result(
                    "WebSocket Connection", True, "Ping/pong successful"
                )
                ws.close()
                return True
            else:
                self.log_test_result(
                    "WebSocket Connection", False, f"Unexpected response: {response}"
                )
                ws.close()
                return False

        except Exception as e:
            self.log_test_result("WebSocket Connection", False, f"Exception: {e}")
            return False

    async def test_chat_message_processing(self):
        """Test sending chat messages via HTTP API"""
        try:
            message_data = {
                "message": "Hello, this is a test message",
                "user_id": TEST_USER_ID,
                "message_type": "text",
                "metadata": {"test": True},
            }

            response = requests.post(
                f"{CHAT_API_URL}/api/v1/chat/message",
                json=message_data,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                self.log_test_result(
                    "Chat Message Processing",
                    True,
                    f"Response: {data.get('response', 'No response')}",
                )
                return True
            else:
                self.log_test_result(
                    "Chat Message Processing",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return False

        except Exception as e:
            self.log_test_result("Chat Message Processing", False, f"Exception: {e}")
            return False

    async def test_user_context_management(self):
        """Test user context retrieval and management"""
        try:
            response = requests.get(
                f"{CHAT_API_URL}/api/v1/chat/users/{TEST_USER_ID}/context"
            )

            if response.status_code == 200:
                data = response.json()
                self.log_test_result(
                    "User Context Management",
                    True,
                    f"Context ID: {data.get('context_id', 'No context')}",
                )
                return True
            elif response.status_code == 404:
                # Context not found is acceptable for new users
                self.log_test_result(
                    "User Context Management",
                    True,
                    "No context found (new user - expected)",
                )
                return True
            else:
                self.log_test_result(
                    "User Context Management",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return False

        except Exception as e:
            self.log_test_result("User Context Management", False, f"Exception: {e}")
            return False

    async def test_room_management(self):
        """Test WebSocket room management functionality"""
        try:
            ws = websocket.create_connection(f"{WEBSOCKET_URL}/ws/{TEST_USER_ID}")

            # Join room
            join_message = {
                "type": "join_room",
                "room_id": TEST_ROOM_ID,
                "timestamp": datetime.now().isoformat(),
            }
            ws.send(json.dumps(join_message))

            # Wait for response
            response = json.loads(ws.recv())
            if response.get("type") == "room_joined":
                self.log_test_result(
                    "Room Management - Join",
                    True,
                    f"Joined room: {TEST_ROOM_ID}",
                )

                # Leave room
                leave_message = {
                    "type": "leave_room",
                    "room_id": TEST_ROOM_ID,
                    "timestamp": datetime.now().isoformat(),
                }
                ws.send(json.dumps(leave_message))

                response = json.loads(ws.recv())
                if response.get("type") == "room_left":
                    self.log_test_result(
                        "Room Management - Leave",
                        True,
                        f"Left room: {TEST_ROOM_ID}",
                    )
                    ws.close()
                    return True
                else:
                    self.log_test_result(
                        "Room Management - Leave",
                        False,
                        f"Unexpected response: {response}",
                    )
                    ws.close()
                    return False
            else:
                self.log_test_result(
                    "Room Management - Join",
                    False,
                    f"Unexpected response: {response}",
                )
                ws.close()
                return False

        except Exception as e:
            self.log_test_result("Room Management", False, f"Exception: {e}")
            return False

    async def test_real_time_chat(self):
        """Test real-time chat functionality"""
        try:
            # Create two WebSocket connections for testing
            ws1 = websocket.create_connection(f"{WEBSOCKET_URL}/ws/user1")
            ws2 = websocket.create_connection(f"{WEBSOCKET_URL}/ws/user2")

            # Both users join the same room
            join_msg = {"type": "join_room", "room_id": TEST_ROOM_ID}
            ws1.send(json.dumps(join_msg))
            ws2.send(json.dumps(join_msg))

            # Wait for join confirmations
            ws1.recv()  # user1 join confirmation
            ws2.recv()  # user2 join confirmation

            # User1 sends a message
            chat_message = {
                "type": "chat_message",
                "room_id": TEST_ROOM_ID,
                "message": "Hello from user1!",
                "timestamp": datetime.now().isoformat(),
            }
            ws1.send(json.dumps(chat_message))

            # User2 should receive the message
            response = json.loads(ws2.recv())
            if (
                response.get("type") == "chat_message"
                and response.get("user_id") == "user1"
                and response.get("message") == "Hello from user1!"
            ):
                self.log_test_result(
                    "Real-time Chat",
                    True,
                    "Message successfully delivered between users",
                )

                # Cleanup
                ws1.close()
                ws2.close()
                return True
            else:
                self.log_test_result(
                    "Real-time Chat",
                    False,
                    f"Message not properly delivered: {response}",
                )
                ws1.close()
                ws2.close()
                return False

        except Exception as e:
            self.log_test_result("Real-time Chat", False, f"Exception: {e}")
            return False

    async def test_connection_stats(self):
        """Test connection statistics endpoint"""
        try:
            response = requests.get(
                f"{WEBSOCKET_URL.replace('ws://', 'http://')}/api/v1/websocket/stats"
            )

            if response.status_code == 200:
                data = response.json()
                self.log_test_result(
                    "Connection Statistics",
                    True,
                    f"Active connections: {data.get('server_stats', {}).get('active_connections', 0)}",
                )
                return True
            else:
                self.log_test_result(
                    "Connection Statistics",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return False

        except Exception as e:
            self.log_test_result("Connection Statistics", False, f"Exception: {e}")
            return False

    async def test_typing_indicators(self):
        """Test typing indicator functionality"""
        try:
            ws1 = websocket.create_connection(f"{WEBSOCKET_URL}/ws/typing_user1")
            ws2 = websocket.create_connection(f"{WEBSOCKET_URL}/ws/typing_user2")

            # Both users join the same room
            join_msg = {"type": "join_room", "room_id": "typing_test_room"}
            ws1.send(json.dumps(join_msg))
            ws2.send(json.dumps(join_msg))

            # Wait for join confirmations
            ws1.recv()
            ws2.recv()

            # User1 starts typing
            typing_msg = {
                "type": "typing_indicator",
                "room_id": "typing_test_room",
                "is_typing": True,
                "timestamp": datetime.now().isoformat(),
            }
            ws1.send(json.dumps(typing_msg))

            # User2 should receive typing indicator
            response = json.loads(ws2.recv())
            if (
                response.get("type") == "typing_indicator"
                and response.get("user_id") == "typing_user1"
                and response.get("is_typing") == True
            ):
                self.log_test_result(
                    "Typing Indicators",
                    True,
                    "Typing indicator successfully delivered",
                )

                # Cleanup
                ws1.close()
                ws2.close()
                return True
            else:
                self.log_test_result(
                    "Typing Indicators",
                    False,
                    f"Typing indicator not properly delivered: {response}",
                )
                ws1.close()
                ws2.close()
                return False

        except Exception as e:
            self.log_test_result("Typing Indicators", False, f"Exception: {e}")
            return False

    async def test_error_handling(self):
        """Test error handling for invalid requests"""
        try:
            # Test invalid chat message
            invalid_message = {"invalid": "data"}
            response = requests.post(
                f"{CHAT_API_URL}/api/v1/chat/message",
                json=invalid_message,
                headers={"Content-Type": "application/json"},
            )

            # Should handle gracefully (either 422 validation error or proper error response)
            if response.status_code in [200, 422, 400]:
                self.log_test_result(
                    "Error Handling",
                    True,
                    f"Handled invalid request with status: {response.status_code}",
                )
                return True
            else:
                self.log_test_result(
                    "Error Handling",
                    False,
                    f"Unexpected status for invalid request: {response.status_code}",
                )
                return False

        except Exception as e:
            self.log_test_result("Error Handling", False, f"Exception: {e}")
            return False

    async def run_all_tests(self):
        """Run all integration tests"""
        logger.info("🚀 Starting Chat Interface Integration Tests")
        logger.info("=" * 50)

        tests = [
            self.test_chat_api_health,
            self.test_websocket_server_health,
            self.test_websocket_connection,
            self.test_chat_message_processing,
            self.test_user_context_management,
            self.test_room_management,
            self.test_real_time_chat,
            self.test_connection_stats,
            self.test_typing_indicators,
            self.test_error_handling,
        ]

        for test in tests:
            await test()
            await asyncio.sleep(0.5)  # Small delay between tests

        # Generate test report
        await self.generate_test_report()

    async def generate_test_report(self):
        """Generate comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        logger.info("=" * 50)
        logger.info("📊 TEST REPORT SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(f"Success Rate: {success_rate:.1f}%")

        if failed_tests > 0:
            logger.info("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    logger.info(f"  - {result['test_name']}: {result['details']}")

        # Save detailed report
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": success_rate,
            },
            "detailed_results": {
                result["test_name"]: result for result in self.test_results
            },
            "recommendations": self._generate_recommendations(),
        }

        with open("chat_integration_test_report.json", "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"\n📄 Detailed report saved to: chat_integration_test_report.json")

        if success_rate == 100:
            logger.info(
                "🎉 All tests passed! Chat interface integration is ready for production."
            )
        else:
            logger.info("⚠️ Some tests failed. Please review and fix the issues.")

    def _generate_recommendations(self):
        """Generate recommendations based on test results"""
        recommendations = []

        failed_tests = [r for r in self.test_results if not r["success"]]

        if any("Health" in r["test_name"] for r in failed_tests):
            recommendations.append("Ensure chat API and WebSocket servers are running")

        if any("WebSocket" in r["test_name"] for r in failed_tests):
            recommendations.append(
                "Check WebSocket server configuration and firewall settings"
            )

        if any("Message" in r["test_name"] for r in failed_tests):
            recommendations.append("Verify chat message processing pipeline")

        if any("Room" in r["test_name"] for r in failed_tests):
            recommendations.append("Review room management functionality")

        if any("Real-time" in r["test_name"] for r in failed_tests):
            recommendations.append(
                "Test real-time communication under network conditions"
            )

        if not recommendations:
            recommendations.append(
                "All systems functioning correctly - ready for production deployment"
            )

        return recommendations


async def main():
    """Main test execution function"""
    test_suite = ChatIntegrationTest()
    await test_suite.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
