import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List
import requests
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CHAT_API_URL = "http://localhost:8000"
TEST_USER_ID = "phase2_test_user_001"
TEST_CONTEXT_ID = "phase2_test_context_001"


# Test data
class Phase2IntegrationTest:
    """Comprehensive test suite for Phase 2 features"""

    def __init__(self):
        self.test_results = []
        self.uploaded_files = []
        self.voice_messages = []

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

    def create_test_file(self, content: str, extension: str = "txt") -> str:
        """Create a temporary test file"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=f".{extension}", delete=False
        ) as f:
            f.write(content)
            return f.name

    async def test_multimodal_file_upload(self):
        """Test file upload functionality"""
        try:
            # Create test files
            test_files = [
                ("test_image.png", b"fake_png_content", "image/png"),
                (
                    "test_document.txt",
                    b"This is a test document content.",
                    "text/plain",
                ),
                ("test_spreadsheet.csv", b"col1,col2,col3\n1,2,3\n4,5,6", "text/csv"),
            ]

            for filename, content, mime_type in test_files:
                # Create temporary file
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=filename.split(".")[-1]
                ) as temp_file:
                    temp_file.write(content)
                    temp_file_path = temp_file.name

                # Upload file
                with open(temp_file_path, "rb") as file:
                    files = {"file": (filename, file, mime_type)}
                    data = {"user_id": TEST_USER_ID, "context_id": TEST_CONTEXT_ID}

                    response = requests.post(
                        f"{CHAT_API_URL}/api/v1/chat/upload", files=files, data=data
                    )

                # Clean up temp file
                os.unlink(temp_file_path)

                if response.status_code == 200:
                    result = response.json()
                    self.uploaded_files.append(result["file_id"])
                    self.log_test_result(
                        f"File Upload - {filename}",
                        True,
                        f"File uploaded successfully: {result['file_id']}",
                    )
                else:
                    self.log_test_result(
                        f"File Upload - {filename}",
                        False,
                        f"HTTP {response.status_code}: {response.text}",
                    )
                    return False

            return True

        except Exception as e:
            self.log_test_result("File Upload", False, f"Exception: {e}")
            return False

    async def test_multimodal_chat_message(self):
        """Test sending multi-modal chat messages with file attachments"""
        try:
            if not self.uploaded_files:
                self.log_test_result(
                    "Multi-modal Chat", False, "No files uploaded for testing"
                )
                return False

            # Send multi-modal message with file attachments
            message_data = {
                "message": "Please analyze these attached files",
                "user_id": TEST_USER_ID,
                "file_ids": self.uploaded_files[:2],  # Use first two uploaded files
                "context_id": TEST_CONTEXT_ID,
                "message_type": "multimodal",
            }

            response = requests.post(
                f"{CHAT_API_URL}/api/v1/chat/multimodal",
                json=message_data,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                result = response.json()
                self.log_test_result(
                    "Multi-modal Chat Message",
                    True,
                    f"Message processed with {len(result.get('attachments', []))} files",
                )
                return True
            else:
                self.log_test_result(
                    "Multi-modal Chat Message",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return False

        except Exception as e:
            self.log_test_result("Multi-modal Chat Message", False, f"Exception: {e}")
            return False

    async def test_file_management(self):
        """Test file management endpoints"""
        try:
            if not self.uploaded_files:
                self.log_test_result(
                    "File Management", False, "No files available for testing"
                )
                return False

            test_file_id = self.uploaded_files[0]

            # Test get file info
            response = requests.get(f"{CHAT_API_URL}/api/v1/chat/files/{test_file_id}")
            if response.status_code == 200:
                self.log_test_result(
                    "Get File Info", True, "File info retrieved successfully"
                )
            else:
                self.log_test_result(
                    "Get File Info", False, f"HTTP {response.status_code}"
                )
                return False

            # Test list user files
            response = requests.get(
                f"{CHAT_API_URL}/api/v1/chat/files?user_id={TEST_USER_ID}"
            )
            if response.status_code == 200:
                result = response.json()
                self.log_test_result(
                    "List User Files", True, f"Found {len(result)} files for user"
                )
            else:
                self.log_test_result(
                    "List User Files", False, f"HTTP {response.status_code}"
                )
                return False

            return True

        except Exception as e:
            self.log_test_result("File Management", False, f"Exception: {e}")
            return False

    async def test_voice_message_upload(self):
        """Test voice message upload and processing"""
        try:
            # Create a mock audio file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                # Write some mock audio data (in real scenario, this would be actual audio)
                temp_audio.write(b"fake_audio_data" * 100)
                temp_audio_path = temp_audio.name

            # Upload voice message
            with open(temp_audio_path, "rb") as audio_file:
                files = {"audio_file": ("test_voice.wav", audio_file, "audio/wav")}
                data = {
                    "user_id": TEST_USER_ID,
                    "context_id": TEST_CONTEXT_ID,
                    "language": "en-US",
                }

                response = requests.post(
                    f"{CHAT_API_URL}/api/v1/voice/upload", files=files, data=data
                )

            # Clean up
            os.unlink(temp_audio_path)

            if response.status_code == 200:
                result = response.json()
                self.voice_messages.append(result["message_id"])
                self.log_test_result(
                    "Voice Message Upload",
                    True,
                    f"Voice message processed: {result.get('transcription', 'No transcription')}",
                )
                return True
            else:
                self.log_test_result(
                    "Voice Message Upload",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return False

        except Exception as e:
            self.log_test_result("Voice Message Upload", False, f"Exception: {e}")
            return False

    async def test_text_to_speech(self):
        """Test text-to-speech functionality"""
        try:
            tts_request = {
                "text": "Hello, this is a test of the text-to-speech system.",
                "user_id": TEST_USER_ID,
                "voice": "en-US-Neural2-F",
                "language": "en-US",
                "speed": 1.0,
            }

            response = requests.post(
                f"{CHAT_API_URL}/api/v1/voice/tts",
                json=tts_request,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                result = response.json()
                self.log_test_result(
                    "Text-to-Speech",
                    True,
                    f"TTS generated: {result.get('audio_id', 'No ID')}",
                )
                return True
            else:
                self.log_test_result(
                    "Text-to-Speech",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return False

        except Exception as e:
            self.log_test_result("Text-to-Speech", False, f"Exception: {e}")
            return False

    async def test_voice_service_health(self):
        """Test voice service health endpoint"""
        try:
            response = requests.get(f"{CHAT_API_URL}/api/v1/voice/health")

            if response.status_code == 200:
                result = response.json()
                self.log_test_result(
                    "Voice Service Health",
                    True,
                    f"Service status: {result.get('status', 'unknown')}",
                )
                return True
            else:
                self.log_test_result(
                    "Voice Service Health",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return False

        except Exception as e:
            self.log_test_result("Voice Service Health", False, f"Exception: {e}")
            return False

    async def test_analytics_dashboard(self):
        """Test analytics dashboard functionality"""
        try:
            # Define time range for analytics
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

            time_range = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "granularity": "daily",
            }

            response = requests.post(
                f"{CHAT_API_URL}/api/v1/analytics/dashboard",
                json=time_range,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                result = response.json()
                self.log_test_result(
                    "Analytics Dashboard",
                    True,
                    f"Dashboard loaded with {len(result.get('user_analytics', []))} users",
                )
                return True
            else:
                self.log_test_result(
                    "Analytics Dashboard",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return False

        except Exception as e:
            self.log_test_result("Analytics Dashboard", False, f"Exception: {e}")
            return False

    async def test_analytics_recording(self):
        """Test analytics data recording"""
        try:
            # Record message analytics
            message_data = {
                "user_id": TEST_USER_ID,
                "conversation_id": TEST_CONTEXT_ID,
                "message_type": "text",
                "response_time": 1.5,
                "has_attachments": False,
                "workflow_triggered": True,
            }

            response = requests.post(
                f"{CHAT_API_URL}/api/v1/analytics/messages",
                json=message_data,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                self.log_test_result(
                    "Message Analytics Recording", True, "Message analytics recorded"
                )
            else:
                self.log_test_result(
                    "Message Analytics Recording", False, f"HTTP {response.status_code}"
                )
                return False

            # Record system metrics
            system_metrics = {
                "active_users": 25,
                "message_throughput": 10.5,
                "avg_response_time": 150.0,
                "error_rate": 0.5,
                "cpu_usage": 45.0,
                "memory_usage": 60.0,
            }

            response = requests.post(
                f"{CHAT_API_URL}/api/v1/analytics/system",
                json=system_metrics,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                self.log_test_result(
                    "System Metrics Recording", True, "System metrics recorded"
                )
                return True
            else:
                self.log_test_result(
                    "System Metrics Recording", False, f"HTTP {response.status_code}"
                )
                return False

        except Exception as e:
            self.log_test_result("Analytics Recording", False, f"Exception: {e}")
            return False

    async def test_error_handling(self):
        """Test error handling for invalid requests"""
        try:
            # Test invalid file upload
            invalid_files = [
                (
                    "test.exe",
                    b"malicious_content",
                    "application/x-msdownload",
                ),  # Executable file
                (
                    "huge_file.bin",
                    b"x" * (100 * 1024 * 1024),
                    "application/octet-stream",
                ),  # Too large
            ]

            for filename, content, mime_type in invalid_files:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=filename.split(".")[-1]
                ) as temp_file:
                    temp_file.write(content)
                    temp_file_path = temp_file.name

                try:
                    with open(temp_file_path, "rb") as file:
                        files = {"file": (filename, file, mime_type)}
                        data = {"user_id": TEST_USER_ID}

                        response = requests.post(
                            f"{CHAT_API_URL}/api/v1/chat/upload", files=files, data=data
                        )

                    # Should return error status
                    if response.status_code in [400, 413]:
                        self.log_test_result(
                            f"Error Handling - {filename}",
                            True,
                            f"Properly rejected with status: {response.status_code}",
                        )
                    else:
                        self.log_test_result(
                            f"Error Handling - {filename}",
                            False,
                            f"Expected error but got: {response.status_code}",
                        )

                finally:
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)

            return True

        except Exception as e:
            self.log_test_result("Error Handling", False, f"Exception: {e}")
            return False

    async def run_all_tests(self):
        """Run all Phase 2 integration tests"""
        logger.info("🚀 Starting Phase 2 Features Integration Tests")
        logger.info("=" * 60)

        tests = [
            self.test_multimodal_file_upload,
            self.test_multimodal_chat_message,
            self.test_file_management,
            self.test_voice_message_upload,
            self.test_text_to_speech,
            self.test_voice_service_health,
            self.test_analytics_dashboard,
            self.test_analytics_recording,
            self.test_error_handling,
        ]

        for test in tests:
            await test()
            await asyncio.sleep(1)  # Small delay between tests

        # Generate test report
        await self.generate_test_report()

    async def generate_test_report(self):
        """Generate comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        logger.info("=" * 60)
        logger.info("📊 PHASE 2 TEST REPORT SUMMARY")
        logger.info("=" * 60)
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
            "phase": "Phase 2 - Advanced Features",
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": success_rate,
            },
            "detailed_results": {
                result["test_name"]: result for result in self.test_results
            },
            "test_artifacts": {
                "uploaded_files": self.uploaded_files,
                "voice_messages": self.voice_messages,
            },
            "recommendations": self._generate_recommendations(),
        }

        with open("phase2_integration_test_report.json", "w") as f:
            json.dump(report, f, indent=2)

        logger.info(
            f"\n📄 Detailed report saved to: phase2_integration_test_report.json"
        )

        if success_rate >= 80:
            logger.info("🎉 Phase 2 features are ready for production deployment!")
        elif success_rate >= 60:
            logger.info("⚠️ Phase 2 features have some issues that need attention.")
        else:
            logger.info(
                "❌ Phase 2 features require significant fixes before deployment."
            )

    def _generate_recommendations(self):
        """Generate recommendations based on test results"""
        recommendations = []
        failed_tests = [r for r in self.test_results if not r["success"]]

        if any("File" in r["test_name"] for r in failed_tests):
            recommendations.append("Review file upload and processing pipeline")

        if any("Voice" in r["test_name"] for r in failed_tests):
            recommendations.append("Check voice service integration and dependencies")

        if any("Analytics" in r["test_name"] for r in failed_tests):
            recommendations.append("Verify analytics data collection and processing")

        if any("Error" in r["test_name"] for r in failed_tests):
            recommendations.append("Improve error handling and validation")

        if not recommendations:
            recommendations.extend(
                [
                    "All Phase 2 features functioning correctly",
                    "Proceed with production deployment",
                    "Monitor performance under load",
                    "Collect user feedback for further improvements",
                ]
            )

        return recommendations


async def main():
    """Main test execution function"""
    test_suite = Phase2IntegrationTest()
    await test_suite.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
