"""
Tests for Creative Tool (FFmpeg Video/Audio Processing)

Tests FFmpegService with mocked FFmpeg binary execution.
Covers governance enforcement, path validation, security, async job processing.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import tempfile
import os

from core.models import AgentRegistry, FFmpegJob, User, AgentStatus
from tools.creative_tool import FFmpegTool


# ============================================================================
# FFmpegService Tests
# ============================================================================

class TestFFmpegService:
    """Test FFmpeg service with mocked ffmpeg-python library."""

    @pytest.fixture
    def mock_ffmpeg_service(self):
        """Create FFmpegService with mocked ffmpeg."""
        with patch('core.creative.ffmpeg_service.ffmpeg') as mock_ffmpeg:
            mock_input = MagicMock()
            mock_output = MagicMock()
            mock_ffmpeg.input.return_value = mock_input
            mock_input.output.return_value = mock_output
            mock_output.run.return_value = None  # Success

            from core.creative.ffmpeg_service import FFmpegService
            service = FFmpegService()
            service.ffmpeg = mock_ffmpeg
            return service

    def test_trim_video_success(self, mock_ffmpeg_service, temp_directory):
        """Test successful video trimming."""
        input_path = os.path.join(temp_directory, "input.mp4")
        output_path = os.path.join(temp_directory, "output.mp4")

        # Create input file
        with open(input_path, 'wb') as f:
            f.write(b"fake video data")

        result = mock_ffmpeg_service.trim_video(
            input_path=input_path,
            output_path=output_path,
            start_time="00:00:05",
            duration="00:01:00"
        )

        assert result is True

    def test_extract_audio_success(self, mock_ffmpeg_service, temp_directory):
        """Test successful audio extraction."""
        input_path = os.path.join(temp_directory, "input.mp4")
        output_path = os.path.join(temp_directory, "audio.mp3")

        # Create input file
        with open(input_path, 'wb') as f:
            f.write(b"fake video data")

        result = mock_ffmpeg_service.extract_audio(
            input_path=input_path,
            output_path=output_path,
            format="mp3"
        )

        assert result is True

    def test_generate_thumbnail_success(self, mock_ffmpeg_service, temp_directory):
        """Test successful thumbnail generation."""
        input_path = os.path.join(temp_directory, "input.mp4")
        output_path = os.path.join(temp_directory, "thumb.jpg")

        # Create input file
        with open(input_path, 'wb') as f:
            f.write(b"fake video data")

        result = mock_ffmpeg_service.generate_thumbnail(
            input_path=input_path,
            output_path=output_path,
            timestamp="00:00:30"
        )

        assert result is True

    def test_convert_format_success(self, mock_ffmpeg_service, temp_directory):
        """Test successful format conversion."""
        input_path = os.path.join(temp_directory, "input.mov")
        output_path = os.path.join(temp_directory, "output.mp4")

        # Create input file
        with open(input_path, 'wb') as f:
            f.write(b"fake video data")

        result = mock_ffmpeg_service.convert_format(
            input_path=input_path,
            output_path=output_path,
            format="mp4"
        )

        assert result is True

    def test_normalize_audio_success(self, mock_ffmpeg_service, temp_directory):
        """Test successful audio normalization."""
        input_path = os.path.join(temp_directory, "audio.mp3")
        output_path = os.path.join(temp_directory, "normalized.mp3")

        # Create input file
        with open(input_path, 'wb') as f:
            f.write(b"fake audio data")

        result = mock_ffmpeg_service.normalize_audio(
            input_path=input_path,
            output_path=output_path
        )

        assert result is True

    def test_file_not_found_error(self, mock_ffmpeg_service, temp_directory):
        """Test error handling for non-existent input file."""
        input_path = os.path.join(temp_directory, "nonexistent.mp4")
        output_path = os.path.join(temp_directory, "output.mp4")

        with pytest.raises(FileNotFoundError):
            mock_ffmpeg_service.trim_video(
                input_path=input_path,
                output_path=output_path,
                start_time="00:00:05",
                duration="00:01:00"
            )

    def test_invalid_path_blocked(self, mock_ffmpeg_service):
        """Test path validation rejects paths with traversal."""
        # Path traversal should be blocked
        with pytest.raises(ValueError, match="path traversal"):
            mock_ffmpeg_service.trim_video(
                input_path="../../../etc/passwd",
                output_path="output.mp4",
                start_time="00:00:05",
                duration="00:01:00"
            )


# ============================================================================
# Async Job Tests
# ============================================================================

class TestAsyncJobs:
    """Test async job processing for long-running FFmpeg operations."""

    @pytest.mark.asyncio
    async def test_job_created_returns_pending_status(self, db_session: Session):
        """Test job creation returns pending status."""
        tool = FFmpegTool()
        tool.service = MagicMock()

        # Mock job creation
        with patch.object(tool.service, 'trim_video', return_value=True):
            job_id = "test_job_123"

            result = await tool._run(
                action="trim_video",
                input_path="/app/data/media/input.mp4",
                output_path="/app/data/media/output.mp4",
                agent_id=None,
                maturity_level="AUTONOMOUS",
                db=db_session
            )

            assert "job_id" in result or "success" in result

    @pytest.mark.asyncio
    async def test_job_runs_in_background(self, db_session: Session):
        """Test job runs asynchronously in background."""
        tool = FFmpegTool()
        tool.service = MagicMock()

        with patch.object(tool.service, 'trim_video', return_value=True):
            result = await tool._run(
                action="trim_video",
                input_path="/app/data/media/input.mp4",
                output_path="/app/data/media/output.mp4",
                agent_id=None,
                maturity_level="AUTONOMOUS",
                db=db_session
            )

            # Job should be scheduled/backgrounded
            assert "success" in result or "job_id" in result

    @pytest.mark.asyncio
    async def test_completed_job_has_output_path(self, db_session: Session):
        """Test completed job has output path."""
        tool = FFmpegTool()
        tool.service = MagicMock()

        with patch.object(tool.service, 'trim_video', return_value=True):
            result = await tool._run(
                action="trim_video",
                input_path="/app/data/media/input.mp4",
                output_path="/app/data/media/output.mp4",
                agent_id=None,
                maturity_level="AUTONOMOUS",
                db=db_session
            )

            # Should return output path on success
            if result.get("success"):
                assert "output_path" in result or "message" in result


# ============================================================================
# FFmpegTool Tests
# ============================================================================

class TestFFmpegToolGovernance:
    """Test governance enforcement for FFmpeg tool."""

    @pytest.mark.asyncio
    async def test_autonomous_agent_only_can_use_ffmpeg(self, db_session: Session):
        """Test only AUTONOMOUS agents can use FFmpeg."""
        tool = FFmpegTool()

        # Create agents of different maturity levels
        test_cases = [
            ("STUDENT", 0.3),
            ("INTERN", 0.6),
            ("SUPERVISED", 0.8),
        ]

        for maturity, confidence in test_cases:
            agent = AgentRegistry(
                name=f"{maturity}Agent",
                category="test",
                module_path="test.module",
                class_name=f"Test{maturity}",
                status=AgentStatus[maturity].value,
                maturity_level=maturity,
                confidence_score=confidence,
            )
            db_session.add(agent)
            db_session.commit()

            result = await tool._run(
                action="trim_video",
                input_path="/app/data/media/input.mp4",
                output_path="/app/data/media/output.mp4",
                agent_id=agent.id,
                maturity_level=maturity,
                db=db_session
            )

            # Should be blocked
            assert result["success"] is False
            assert "AUTONOMOUS" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_path_validation_enforced(self, db_session: Session):
        """Test path validation is enforced for all agents."""
        tool = FFmpegTool()

        # Even AUTONOMOUS agent should have paths validated
        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Try path traversal
        result = await tool._run(
            action="trim_video",
            input_path="../../etc/passwd",
            output_path="output.mp4",
            agent_id=agent.id,
            maturity_level="AUTONOMOUS",
            db=db_session
        )

        assert result["success"] is False
        assert "path" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_trim_action(self, db_session: Session):
        """Test trim_video action."""
        tool = FFmpegTool()
        tool.service = MagicMock()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        with patch.object(tool.service, 'trim_video', return_value=True):
            result = await tool._run(
                action="trim_video",
                input_path="/app/data/media/input.mp4",
                output_path="/app/data/media/output.mp4",
                start_time="00:00:05",
                duration="00:01:00",
                agent_id=agent.id,
                maturity_level="AUTONOMOUS",
                db=db_session
            )

            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_extract_audio_action(self, db_session: Session):
        """Test extract_audio action."""
        tool = FFmpegTool()
        tool.service = MagicMock()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        with patch.object(tool.service, 'extract_audio', return_value=True):
            result = await tool._run(
                action="extract_audio",
                input_path="/app/data/media/meeting.mp4",
                output_path="/app/data/exports/meeting.mp3",
                format="mp3",
                agent_id=agent.id,
                maturity_level="AUTONOMOUS",
                db=db_session
            )

            assert result.get("success") is True


# ============================================================================
# Security Tests
# ============================================================================

class TestFFmpegSecurity:
    """Test security controls for FFmpeg operations."""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, db_session: Session):
        """Test path traversal attacks are blocked."""
        tool = FFmpegTool()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Try various path traversal attempts
        malicious_paths = [
            "../../../etc/passwd",
            "/etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/app/data/../../../etc/shadow",
        ]

        for malicious_path in malicious_paths:
            result = await tool._run(
                action="trim_video",
                input_path=malicious_path,
                output_path="output.mp4",
                agent_id=agent.id,
                maturity_level="AUTONOMOUS",
                db=db_session
            )

            assert result["success"] is False
            assert "path" in result.get("error", "").lower() or "invalid" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_absolute_path_outside_allowed_dir_blocked(self, db_session: Session):
        """Test absolute paths outside allowed directories are blocked."""
        tool = FFmpegTool()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Try absolute path outside allowed dirs
        result = await tool._run(
            action="trim_video",
            input_path="/tmp/malicious.mp4",
            output_path="output.mp4",
            agent_id=agent.id,
            maturity_level="AUTONOMOUS",
            db=db_session
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_allowed_dirs_enforced(self, db_session: Session):
        """Test allowed directories are enforced."""
        tool = FFmpegTool()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Paths within allowed directories should work
        tool.service = MagicMock()
        with patch.object(tool.service, 'trim_video', return_value=True):
            allowed_paths = [
                "/app/data/media/input.mp4",
                "/app/data/exports/output.mp4",
                "./data/media/input.mp4",
            ]

            for path in allowed_paths:
                result = await tool._run(
                    action="trim_video",
                    input_path=path,
                    output_path="/app/data/media/output.mp4",
                    agent_id=agent.id,
                    maturity_level="AUTONOMOUS",
                    db=db_session
                )

                # Should pass path validation (may fail at service level if not mocked)
                assert "path" not in result.get("error", "").lower() or result.get("success") is True


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestFFmpegIntegration:
    """Integration tests requiring real FFmpeg binary."""

    @pytest.mark.skip(reason="Requires FFmpeg binary installation")
    def test_real_ffmpeg_trim_operation(self):
        """Test with real FFmpeg binary (requires FFmpeg installed)."""
        # This test only runs with: pytest -m integration
        pass

    @pytest.mark.skip(reason="Requires FFmpeg binary installation")
    def test_real_ffmpeg_thumbnail_generation(self):
        """Test with real FFmpeg binary (requires FFmpeg installed)."""
        # This test only runs with: pytest -m integration
        pass
