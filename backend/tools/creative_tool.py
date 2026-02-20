"""
Creative Tool - FFmpeg Video/Audio Processing

LangChain BaseTool wrapper for FFmpeg operations with AUTONOMOUS-only governance.

Supports:
- Video trimming, format conversion, thumbnail generation
- Audio extraction, volume normalization
- Async job processing with progress tracking

Governance: AUTONOMOUS maturity level required (file safety)
"""

import os
from typing import Optional
from langchain.tools import BaseTool

from core.creative.ffmpeg_service import FFmpegService
from core.governance_cache import GovernanceCache
from core.structured_logger import get_logger

logger = get_logger(__name__)


class FFmpegTool(BaseTool):
    """
    FFmpeg video/audio editing tool for AI agents.

    **AUTONOMOUS ONLY** - File operations require highest maturity level.

    Operations:
    - trim_video: Cut video to specified start time and duration
    - convert_format: Convert video to different format (MP4, WebM, MOV, AVI)
    - generate_thumbnail: Extract single frame as JPEG thumbnail
    - extract_audio: Extract audio track from video (MP3, M4A, WAV, FLAC)
    - normalize_audio: Normalize audio volume to EBU R128 standard

    Security:
    - All file paths validated against allowed directories
    - AUTONOMOUS maturity required (STUDENT/INTERN/SUPERVISED blocked)
    - Full audit trail via FFmpegJob database model

    Examples:
    - "Trim the screencast from 5:00 to 10:00"
    - "Convert this video to WebM format"
    - "Extract the audio from the meeting recording"
    - "Generate a thumbnail at 30 seconds for each video"
    - "Normalize the audio volume to -16 LUFS"
    """

    name: str = "ffmpeg_edit"
    description: str = """
    Edit video and audio files using FFmpeg. Operations include:
    - trim_video: Cut video to specified time range (start_time, duration)
    - convert_format: Convert video format (MP4, WebM, MOV, AVI)
    - generate_thumbnail: Create thumbnail at timestamp (JPEG)
    - extract_audio: Extract audio from video (MP3, M4A, WAV, FLAC)
    - normalize_audio: Normalize audio volume to -16 LUFS

    **AUTONOMOUS maturity level REQUIRED** (file safety).

    All file paths must be within allowed directories (./data/media, ./data/exports).
    Operations run asynchronously - returns job_id for tracking.

    Example inputs:
    - Action: trim_video, input: /app/data/media/input/video.mp4, output: /app/data/media/output/trimmed.mp4, start_time: 00:00:05, duration: 00:01:00
    - Action: convert_format, input: /app/data/media/input.mov, output: /app/data/media/output/video.mp4, format: mp4
    - Action: extract_audio, input: /app/data/media/input/meeting.mp4, output: /app/data/exports/meeting_audio.mp3, format: mp3
    """
    complexity: int = 3  # HIGH - Modifies user files
    maturity_required: str = "AUTONOMOUS"

    def __init__(self):
        """Initialize FFmpeg tool with service and governance cache."""
        super().__init__()

        # Initialize FFmpeg service
        try:
            self.service = FFmpegService()
            logger.info("FFmpegTool initialized", service_available=True)
        except Exception as e:
            logger.error("Failed to initialize FFmpegService", error=str(e))
            self.service = None

        # Governance cache for permission checks
        self.governance_cache = GovernanceCache()

    def _run(
        self,
        action: str,
        input_path: str,
        output_path: str,
        agent_id: Optional[str] = None,
        maturity_level: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Execute FFmpeg operation with governance enforcement.

        Args:
            action: Operation to perform (trim_video, convert_format, etc.)
            input_path: Source file path (within allowed directories)
            output_path: Destination file path (within allowed directories)
            agent_id: Agent identifier for governance check
            maturity_level: Current agent maturity level
            **kwargs: Additional operation-specific parameters

        Returns:
            JSON string with job_id and status

        Raises:
            PermissionError: If maturity level is below AUTONOMOUS
            ValueError: If file paths are outside allowed directories
            RuntimeError: If FFmpeg binary or service not available
        """
        # Governance check - AUTONOMOUS ONLY
        if not maturity_level or maturity_level != "AUTONOMOUS":
            error_msg = (
                f"FFmpeg editing requires AUTONOMOUS maturity level. "
                f"Your agent is at {maturity_level or 'UNKNOWN'} maturity. "
                f"This restriction ensures file safety - video/audio editing can "
                f"modify or delete user files."
            )
            logger.warning(
                "FFmpeg permission denied",
                agent_id=agent_id,
                maturity_level=maturity_level,
                required="AUTONOMOUS"
            )
            raise PermissionError(error_msg)

        # Check FFmpeg service availability
        if not self.service:
            raise RuntimeError(
                "FFmpeg service not available. "
                "Install FFmpeg: brew install ffmpeg (macOS) or apt install ffmpeg (Ubuntu)"
            )

        # Validate file paths (security boundary)
        try:
            self.service.validate_path(input_path)
            self.service.validate_path(output_path)
        except ValueError as e:
            logger.warning(
                "Path validation failed",
                input_path=input_path,
                output_path=output_path,
                error=str(e)
            )
            raise ValueError(
                f"File path outside allowed directory: {e}. "
                f"Allowed directories: {self.service.allowed_dirs}"
            )

        # Route to appropriate operation
        try:
            result = self._execute_operation(
                action,
                input_path,
                output_path,
                **kwargs
            )

            # Log successful operation for audit trail
            logger.info(
                "FFmpeg operation initiated",
                agent_id=agent_id,
                action=action,
                input_path=input_path,
                output_path=output_path,
                job_id=result.get("job_id")
            )

            return result

        except Exception as e:
            logger.error(
                "FFmpeg operation failed",
                agent_id=agent_id,
                action=action,
                error=str(e)
            )
            raise RuntimeError(f"FFmpeg operation failed: {e}")

    def _execute_operation(
        self,
        action: str,
        input_path: str,
        output_path: str,
        **kwargs
    ) -> dict:
        """
        Execute specific FFmpeg operation.

        Args:
            action: Operation type
            input_path: Source file
            output_path: Destination file
            **kwargs: Operation-specific parameters

        Returns:
            Dict with job_id and status
        """
        # Route to appropriate async method
        operations = {
            "trim_video": self._trim_video,
            "convert_format": self._convert_format,
            "generate_thumbnail": self._generate_thumbnail,
            "extract_audio": self._extract_audio,
            "normalize_audio": self._normalize_audio
        }

        if action not in operations:
            raise ValueError(
                f"Unknown action: {action}. "
                f"Supported: {list(operations.keys())}"
            )

        # Execute operation (async)
        import asyncio
        coro = operations[action](input_path, output_path, **kwargs)

        # Run async operation in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(coro)

    # ========================================================================
    # Video Operations
    # ========================================================================

    async def _trim_video(
        self,
        input_path: str,
        output_path: str,
        start_time: str,
        duration: str
    ) -> dict:
        """Trim video to specified time range."""
        return await self.service.trim_video(
            input_path=input_path,
            output_path=output_path,
            start_time=start_time,
            duration=duration
        )

    async def _convert_format(
        self,
        input_path: str,
        output_path: str,
        format: str,
        quality: str = "medium"
    ) -> dict:
        """Convert video format."""
        return await self.service.convert_format(
            input_path=input_path,
            output_path=output_path,
            format=format,
            quality=quality
        )

    async def _generate_thumbnail(
        self,
        input_path: str,
        output_path: str,
        timestamp: str = "00:00:01"
    ) -> dict:
        """Generate thumbnail from video."""
        return await self.service.generate_thumbnail(
            video_path=input_path,
            thumbnail_path=output_path,
            timestamp=timestamp
        )

    # ========================================================================
    # Audio Operations
    # ========================================================================

    async def _extract_audio(
        self,
        input_path: str,
        output_path: str,
        format: str = "mp3"
    ) -> dict:
        """Extract audio from video."""
        return await self.service.extract_audio(
            video_path=input_path,
            audio_path=output_path,
            format=format
        )

    async def _normalize_audio(
        self,
        input_path: str,
        output_path: str,
        target_lufs: float = -16.0
    ) -> dict:
        """Normalize audio volume."""
        return await self.service.normalize_audio(
            input_path=input_path,
            output_path=output_path,
            target_lufs=target_lufs
        )


# ============================================================================
# Tool Registration
# ============================================================================

def register_creative_tool(registry):
    """
    Register FFmpeg creative tool with tool registry.

    Args:
        registry: ToolRegistry instance
    """
    try:
        tool_instance = FFmpegTool()

        # Register with metadata
        registry.register(
            name="ffmpeg_edit",
            function=tool_instance._run,
            version="1.0.0",
            description="FFmpeg video/audio editing (AUTONOMOUS only)",
            category="creative",
            complexity=3,
            maturity_required="AUTONOMOUS",
            dependencies=["ffmpeg-python", "ffmpeg"],
            tags=["video", "audio", "ffmpeg", "media", "editing", "creative"]
        )

        logger.info("FFmpeg creative tool registered", category="creative")

    except Exception as e:
        logger.error("Failed to register FFmpeg tool", error=str(e))


# Auto-register on import
try:
    from tools.registry import ToolRegistry
    _registry = ToolRegistry()
    register_creative_tool(_registry)
except ImportError:
    logger.warning("Tool registry not available for auto-registration")
