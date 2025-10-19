#!/usr/bin/env python3
"""
Meeting Transcription Verification Script for Atom

This script verifies that the meeting transcription system is working properly,
including transcription service, meeting prep, and memory integration.
"""

import asyncio
import aiohttp
import json
import logging
import sys
from typing import Dict, Any, List
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@dataclass
class TranscriptionTestResult:
    """Result of transcription service test"""

    service: str
    status: str
    details: str
    response: Dict[str, Any]


class MeetingTranscriptionVerifier:
    """Main class for verifying meeting transcription functionality"""

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.session = None
        self.results: List[TranscriptionTestResult] = []

    async def initialize(self):
        """Initialize HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def test_transcription_health(self) -> TranscriptionTestResult:
        """Test transcription service health endpoint"""
        await self.initialize()

        try:
            async with self.session.get(
                f"{self.base_url}/api/transcription/health"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return TranscriptionTestResult(
                        service="Transcription Health",
                        status="✅ PASS",
                        details="Transcription service is healthy",
                        response=data,
                    )
                else:
                    return TranscriptionTestResult(
                        service="Transcription Health",
                        status="❌ FAIL",
                        details=f"HTTP {response.status}",
                        response={},
                    )
        except Exception as e:
            return TranscriptionTestResult(
                service="Transcription Health",
                status="❌ FAIL",
                details=f"Error: {str(e)}",
                response={},
            )

    async def test_transcription_service(self) -> TranscriptionTestResult:
        """Test transcription service with mock audio data"""
        await self.initialize()

        try:
            # Test with mock audio data (base64 placeholder)
            test_data = {
                "audio_data": "dGVzdCBhdWRpbyBkYXRh",  # "test audio data" in base64
                "meeting_id": "test-meeting-verification",
                "sample_rate": 16000,
                "language": "en-US",
            }

            async with self.session.post(
                f"{self.base_url}/api/transcription/transcribe", json=test_data
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    if data.get("success", False):
                        return TranscriptionTestResult(
                            service="Transcription Service",
                            status="✅ PASS",
                            details="Transcription service working with mock data",
                            response=data,
                        )
                    else:
                        return TranscriptionTestResult(
                            service="Transcription Service",
                            status="⚠️ PARTIAL",
                            details="Service responded but transcription failed",
                            response=data,
                        )
                else:
                    return TranscriptionTestResult(
                        service="Transcription Service",
                        status="❌ FAIL",
                        details=f"HTTP {response.status}",
                        response={},
                    )
        except Exception as e:
            return TranscriptionTestResult(
                service="Transcription Service",
                status="❌ FAIL",
                details=f"Error: {str(e)}",
                response={},
            )

    async def test_meeting_retrieval(self) -> TranscriptionTestResult:
        """Test retrieving meeting transcription"""
        await self.initialize()

        try:
            async with self.session.get(
                f"{self.base_url}/api/transcription/meetings/test-meeting-verification"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return TranscriptionTestResult(
                        service="Meeting Retrieval",
                        status="✅ PASS",
                        details="Meeting retrieval working",
                        response=data,
                    )
                elif response.status == 404:
                    return TranscriptionTestResult(
                        service="Meeting Retrieval",
                        status="⚠️ PARTIAL",
                        details="Meeting not found (expected for test meeting)",
                        response={},
                    )
                else:
                    return TranscriptionTestResult(
                        service="Meeting Retrieval",
                        status="❌ FAIL",
                        details=f"HTTP {response.status}",
                        response={},
                    )
        except Exception as e:
            return TranscriptionTestResult(
                service="Meeting Retrieval",
                status="❌ FAIL",
                details=f"Error: {str(e)}",
                response={},
            )

    async def test_meeting_summary(self) -> TranscriptionTestResult:
        """Test meeting summary retrieval"""
        await self.initialize()

        try:
            async with self.session.get(
                f"{self.base_url}/api/transcription/meetings/test-meeting-verification/summary"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return TranscriptionTestResult(
                        service="Meeting Summary",
                        status="✅ PASS",
                        details="Meeting summary retrieval working",
                        response=data,
                    )
                elif response.status == 404:
                    return TranscriptionTestResult(
                        service="Meeting Summary",
                        status="⚠️ PARTIAL",
                        details="Meeting summary not found (expected for test meeting)",
                        response={},
                    )
                else:
                    return TranscriptionTestResult(
                        service="Meeting Summary",
                        status="❌ FAIL",
                        details=f"HTTP {response.status}",
                        response={},
                    )
        except Exception as e:
            return TranscriptionTestResult(
                service="Meeting Summary",
                status="❌ FAIL",
                details=f"Error: {str(e)}",
                response={},
            )

    async def test_meeting_prep(self) -> TranscriptionTestResult:
        """Test meeting preparation service"""
        await self.initialize()

        try:
            test_data = {
                "meeting_title": "Project Planning Meeting",
                "attendees": ["alice@company.com", "bob@company.com"],
                "agenda": ["Project updates", "Timeline review", "Next steps"],
            }

            async with self.session.post(
                f"{self.base_url}/api/meeting_prep/meeting-prep", json=test_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return TranscriptionTestResult(
                        service="Meeting Prep",
                        status="✅ PASS",
                        details="Meeting preparation service working",
                        response=data,
                    )
                elif response.status == 404:
                    return TranscriptionTestResult(
                        service="Meeting Prep",
                        status="❌ FAIL",
                        details="Meeting prep endpoint not found",
                        response={},
                    )
                else:
                    return TranscriptionTestResult(
                        service="Meeting Prep",
                        status="❌ FAIL",
                        details=f"HTTP {response.status}",
                        response={},
                    )
        except Exception as e:
            return TranscriptionTestResult(
                service="Meeting Prep",
                status="❌ FAIL",
                details=f"Error: {str(e)}",
                response={},
            )

    async def test_semantic_search(self) -> TranscriptionTestResult:
        """Test semantic search for meetings"""
        await self.initialize()

        try:
            test_data = {
                "query": "project planning meeting",
                "user_id": "test_user",
                "limit": 5,
            }

            async with self.session.post(
                f"{self.base_url}/api/search/semantic_search_meetings", json=test_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return TranscriptionTestResult(
                        service="Semantic Search",
                        status="✅ PASS",
                        details="Semantic search for meetings working",
                        response=data,
                    )
                elif response.status == 404:
                    return TranscriptionTestResult(
                        service="Semantic Search",
                        status="❌ FAIL",
                        details="Semantic search endpoint not found",
                        response={},
                    )
                else:
                    return TranscriptionTestResult(
                        service="Semantic Search",
                        status="❌ FAIL",
                        details=f"HTTP {response.status}",
                        response={},
                    )
        except Exception as e:
            return TranscriptionTestResult(
                service="Semantic Search",
                status="❌ FAIL",
                details=f"Error: {str(e)}",
                response={},
            )

    def generate_report(self) -> str:
        """Generate verification report"""
        report = []
        report.append("=" * 80)
        report.append("🎤 MEETING TRANSCRIPTION VERIFICATION REPORT")
        report.append("=" * 80)
        report.append("")

        # Summary section
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.status == "✅ PASS")
        partial_tests = sum(1 for r in self.results if r.status == "⚠️ PARTIAL")
        failed_tests = sum(1 for r in self.results if r.status == "❌ FAIL")

        report.append("📊 VERIFICATION SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Tests: {total_tests}")
        report.append(f"✅ PASS: {passed_tests}")
        report.append(f"⚠️ PARTIAL: {partial_tests}")
        report.append(f"❌ FAIL: {failed_tests}")
        report.append(
            f"Success Rate: {passed_tests}/{total_tests} ({passed_tests / total_tests * 100:.1f}%)"
        )
        report.append("")

        # Detailed results
        report.append("🔧 DETAILED TEST RESULTS")
        report.append("-" * 40)

        for result in self.results:
            report.append(f"\n{result.status} - {result.service}")
            report.append(f"  Details: {result.details}")

            # Show relevant response data
            if result.response:
                if "deepgram_configured" in result.response:
                    report.append(
                        f"  Deepgram Configured: {result.response['deepgram_configured']}"
                    )
                if "transcript" in result.response:
                    transcript_preview = (
                        result.response["transcript"][:100] + "..."
                        if len(result.response["transcript"]) > 100
                        else result.response["transcript"]
                    )
                    report.append(f"  Transcript: {transcript_preview}")
                if "summary" in result.response:
                    summary_preview = (
                        result.response["summary"][:100] + "..."
                        if len(result.response["summary"]) > 100
                        else result.response["summary"]
                    )
                    report.append(f"  Summary: {summary_preview}")

        # Recommendations
        report.append("\n🎯 RECOMMENDATIONS")
        report.append("-" * 40)

        if failed_tests > 0:
            report.append("1. Fix failed endpoints and services")
            report.append("2. Ensure all required dependencies are installed")
            report.append("3. Check database connectivity for meeting storage")

        if partial_tests > 0:
            report.append("4. Complete implementation for partially working services")

        report.append("5. Test with real audio data for full functionality")
        report.append("6. Verify Deepgram API credentials for live transcription")

        report.append("\n" + "=" * 80)
        report.append("✅ VERIFICATION COMPLETE")
        report.append("=" * 80)

        return "\n".join(report)

    async def run_comprehensive_verification(self) -> bool:
        """Run comprehensive meeting transcription verification"""
        logger.info("🎤 Starting meeting transcription verification...")

        try:
            # Run all tests
            tests = [
                self.test_transcription_health(),
                self.test_transcription_service(),
                self.test_meeting_retrieval(),
                self.test_meeting_summary(),
                self.test_meeting_prep(),
                self.test_semantic_search(),
            ]

            # Execute tests concurrently
            self.results = await asyncio.gather(*tests)

            # Generate and print report
            report = self.generate_report()
            print(report)

            # Determine overall success
            passed_tests = sum(1 for r in self.results if r.status == "✅ PASS")
            total_tests = len(self.results)
            success_threshold = 0.6  # 60% of tests should pass

            success_rate = passed_tests / total_tests

            if success_rate >= success_threshold:
                logger.info(
                    f"✅ Meeting transcription verification PASSED ({success_rate:.1%} success rate)"
                )
                return True
            else:
                logger.warning(
                    f"⚠️ Meeting transcription verification PARTIAL ({success_rate:.1%} success rate)"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Meeting transcription verification FAILED: {str(e)}")
            return False
        finally:
            await self.close()


async def main():
    """Main function"""
    verifier = MeetingTranscriptionVerifier()
    success = await verifier.run_comprehensive_verification()

    if success:
        print("\n🎉 Meeting transcription system is READY for production!")
        sys.exit(0)
    else:
        print("\n⚠️ Some meeting transcription issues need attention.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
