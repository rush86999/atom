"""
FFmpeg Video/Audio Processing Service

Provides async video/audio editing operations using FFmpeg:
- Video trimming, format conversion, thumbnail generation
- Audio extraction, volume normalization
- Async job management with progress tracking
- Security boundaries (path validation, allowed directories)

Requires FFmpeg binary installed on the system.
"""

import asyncio
import os
import shutil
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional
from pathlib import Path

from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import FFmpegJob
from core.structured_logger import get_logger

logger = get_logger(__name__)

# Check if FFmpeg is available
try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
    logger.info("FFmpeg Python library loaded successfully")
except ImportError:
    FFMPEG_AVAILABLE = False
    logger.warning("ffmpeg-python not installed. Run: pip install ffmpeg-python")

# Check if FFmpeg binary is available
def check_ffmpeg_binary() -> bool:
    """Check if FFmpeg binary is available on the system."""
    return shutil.which("ffmpeg") is not None

FFMPEG_BINARY_AVAILABLE = check_ffmpeg_binary()


# ============================================================================
# FFmpeg Service
# ============================================================================

class FFmpegService:
    """
    FFmpeg video/audio processing service with async job management.

    Features:
    - Video operations: trim, convert format, generate thumbnails
    - Audio operations: extract from video, normalize volume
    - Async job processing with progress tracking
    - Security boundaries (allowed directories, path validation)
    - Error handling and recovery

    Governance: AUTONOMOUS maturity level required (file safety)
    """

    def __init__(
        self,
        allowed_dirs: Optional[List[str]] = None,
        job_timeout_seconds: int = 300
    ):
        """
        Initialize FFmpeg service.

        Args:
            allowed_dirs: List of allowed directory paths for file operations
            job_timeout_seconds: Maximum time to wait for job completion
        """
        if not FFMPEG_AVAILABLE:
            raise RuntimeError(
                "ffmpeg-python not installed. Run: pip install ffmpeg-python"
            )

        if not FFMPEG_BINARY_AVAILABLE:
            raise RuntimeError(
                "FFmpeg binary not found. Install with: "
                "brew install ffmpeg (macOS) or apt install ffmpeg (Ubuntu)"
            )

        # Default allowed directories (can be overridden via env)
        default_dirs = [
            "./data/media",
            "./data/exports",
            "/app/data/media",
            "/app/data/exports"
        ]
        env_dirs = os.getenv("FFMPEG_ALLOWED_DIRS", "")
        if env_dirs:
            default_dirs.extend(env_dirs.split(","))

        self.allowed_dirs = allowed_dirs or default_dirs
        self.job_timeout_seconds = job_timeout_seconds

        logger.info(
            "FFmpegService initialized",
            allowed_dirs=self.allowed_dirs,
            job_timeout=job_timeout_seconds
        )

    # =========================================================================
    # Path Validation (Security)
    # =========================================================================

    def validate_path(self, path: str) -> bool:
        """
        Validate that a file path is within allowed directories.

        Security boundary: Prevents directory traversal attacks and
        unauthorized file access.

        Args:
            path: File path to validate

        Returns:
            True if path is allowed, False otherwise
        """
        # Reject paths with directory traversal
        if ".." in path or path.startswith("/"):
            # Absolute paths need special handling
            if not any(path.startswith(allowed_dir) for allowed_dir in self.allowed_dirs):
                logger.warning("Path validation failed", path=path, reason="absolute_or_traversal")
                return False

        # Resolve to absolute path for comparison
        try:
            abs_path = os.path.abspath(path)
            for allowed_dir in self.allowed_dirs:
                allowed_abs = os.path.abspath(allowed_dir)
                if abs_path.startswith(allowed_abs):
                    return True
        except Exception as e:
            logger.error("Path validation error", path=path, error=str(e))
            return False

        logger.warning("Path outside allowed directories", path=path)
        return False

    def _validate_paths(self, **paths) -> None:
        """
        Validate multiple file paths.

        Raises:
            ValueError: If any path is invalid
        """
        for name, path in paths.items():
            if path and not self.validate_path(path):
                raise ValueError(
                    f"File path '{path}' ({name}) is outside allowed directories. "
                    f"Allowed: {self.allowed_dirs}"
                )

    # =========================================================================
    # Video Operations
    # =========================================================================

    async def trim_video(
        self,
        input_path: str,
        output_path: str,
        start_time: str,
        duration: str
    ) -> Dict:
        """
        Trim video to specified start time and duration.

        Args:
            input_path: Source video file
            output_path: Output video file
            start_time: Start timestamp (HH:MM:SS format)
            duration: Duration to trim (HH:MM:SS or seconds)

        Returns:
            Dict with job_id and status
        """
        self._validate_paths(input_path=input_path, output_path=output_path)

        # Create job record
        job_id = str(uuid.uuid4())
        with get_db_session() as db:
            job = FFmpegJob(
                id=job_id,
                user_id="system",  # Will be overridden by API layer
                operation="trim_video",
                status="pending",
                progress=0,
                input_path=input_path,
                output_path=output_path,
                operation_metadata={
                    "start_time": start_time,
                    "duration": duration
                }
            )
            db.add(job)
            db.commit()

        # Run in background
        asyncio.create_task(
            self._run_async_job(
                job_id,
                self._trim_video_sync,
                input_path,
                output_path,
                start_time,
                duration
            )
        )

        return {"job_id": job_id, "status": "pending"}

    def _trim_video_sync(
        self,
        input_path: str,
        output_path: str,
        start_time: str,
        duration: str
    ) -> Dict:
        """Synchronous video trimming using FFmpeg."""
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Build FFmpeg command (stream copy for speed)
            stream = ffmpeg.input(input_path, ss=start_time, t=duration)
            stream = ffmpeg.output(stream, output_path, c='copy')
            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            return {
                "success": True,
                "output_path": output_path,
                "message": f"Video trimmed from {start_time} for {duration}"
            }
        except ffmpeg.Error as e:
            logger.error("FFmpeg trim error", error=str(e))
            raise RuntimeError(f"FFmpeg trim failed: {e}")

    async def convert_format(
        self,
        input_path: str,
        output_path: str,
        format: str,
        quality: str = "medium"
    ) -> Dict:
        """
        Convert video to different format.

        Args:
            input_path: Source video file
            output_path: Output video file
            format: Target format (mp4, webm, mov, avi)
            quality: Quality preset (low, medium, high)

        Returns:
            Dict with job_id and status
        """
        self._validate_paths(input_path=input_path, output_path=output_path)

        job_id = str(uuid.uuid4())
        with get_db_session() as db:
            job = FFmpegJob(
                id=job_id,
                user_id="system",
                operation="convert_format",
                status="pending",
                progress=0,
                input_path=input_path,
                output_path=output_path,
                operation_metadata={"format": format, "quality": quality}
            )
            db.add(job)
            db.commit()

        asyncio.create_task(
            self._run_async_job(
                job_id,
                self._convert_format_sync,
                input_path,
                output_path,
                format,
                quality
            )
        )

        return {"job_id": job_id, "status": "pending"}

    def _convert_format_sync(
        self,
        input_path: str,
        output_path: str,
        format: str,
        quality: str
    ) -> Dict:
        """Synchronous format conversion."""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Quality presets
            crf_values = {"low": 28, "medium": 23, "high": 18}
            crf = crf_values.get(quality, 23)

            # Build FFmpeg command
            input_stream = ffmpeg.input(input_path)
            output_stream = ffmpeg.output(
                input_stream,
                output_path,
                vcodec="libx264",
                acodec="aac",
                crf=crf,
                preset="medium",
                movflags="+faststart"  # For web playback
            )
            ffmpeg.run(output_stream, overwrite_output=True, quiet=True)

            return {
                "success": True,
                "output_path": output_path,
                "message": f"Converted to {format} format ({quality} quality)"
            }
        except ffmpeg.Error as e:
            logger.error("FFmpeg convert error", error=str(e))
            raise RuntimeError(f"FFmpeg conversion failed: {e}")

    async def generate_thumbnail(
        self,
        video_path: str,
        thumbnail_path: str,
        timestamp: str = "00:00:01"
    ) -> Dict:
        """
        Generate thumbnail from video at specified timestamp.

        Args:
            video_path: Source video file
            thumbnail_path: Output thumbnail file (JPEG)
            timestamp: Timestamp to capture (HH:MM:SS)

        Returns:
            Dict with job_id and status
        """
        self._validate_paths(video_path=video_path, thumbnail_path=thumbnail_path)

        job_id = str(uuid.uuid4())
        with get_db_session() as db:
            job = FFmpegJob(
                id=job_id,
                user_id="system",
                operation="generate_thumbnail",
                status="pending",
                progress=0,
                input_path=video_path,
                output_path=thumbnail_path,
                operation_metadata={"timestamp": timestamp}
            )
            db.add(job)
            db.commit()

        asyncio.create_task(
            self._run_async_job(
                job_id,
                self._generate_thumbnail_sync,
                video_path,
                thumbnail_path,
                timestamp
            )
        )

        return {"job_id": job_id, "status": "pending"}

    def _generate_thumbnail_sync(
        self,
        video_path: str,
        thumbnail_path: str,
        timestamp: str
    ) -> Dict:
        """Synchronous thumbnail generation."""
        try:
            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)

            # Capture single frame
            input_stream = ffmpeg.input(video_path, ss=timestamp)
            output_stream = ffmpeg.output(
                input_stream,
                thumbnail_path,
                vframes=1,
                format='image2',
                vcodec='mjpeg'
            )
            ffmpeg.run(output_stream, overwrite_output=True, quiet=True)

            return {
                "success": True,
                "thumbnail_path": thumbnail_path,
                "message": f"Thumbnail generated at {timestamp}"
            }
        except ffmpeg.Error as e:
            logger.error("FFmpeg thumbnail error", error=str(e))
            raise RuntimeError(f"Thumbnail generation failed: {e}")

    # =========================================================================
    # Audio Operations
    # =========================================================================

    async def extract_audio(
        self,
        video_path: str,
        audio_path: str,
        format: str = "mp3"
    ) -> Dict:
        """
        Extract audio track from video file.

        Args:
            video_path: Source video file
            audio_path: Output audio file
            format: Audio format (mp3, m4a, wav, flac)

        Returns:
            Dict with job_id and status
        """
        self._validate_paths(video_path=video_path, audio_path=audio_path)

        job_id = str(uuid.uuid4())
        with get_db_session() as db:
            job = FFmpegJob(
                id=job_id,
                user_id="system",
                operation="extract_audio",
                status="pending",
                progress=0,
                input_path=video_path,
                output_path=audio_path,
                operation_metadata={"format": format}
            )
            db.add(job)
            db.commit()

        asyncio.create_task(
            self._run_async_job(
                job_id,
                self._extract_audio_sync,
                video_path,
                audio_path,
                format
            )
        )

        return {"job_id": job_id, "status": "pending"}

    def _extract_audio_sync(
        self,
        video_path: str,
        audio_path: str,
        format: str
    ) -> Dict:
        """Synchronous audio extraction."""
        try:
            os.makedirs(os.path.dirname(audio_path), exist_ok=True)

            # Audio codec mapping
            codecs = {
                "mp3": "libmp3lame",
                "m4a": "aac",
                "wav": "pcm_s16le",
                "flac": "flac"
            }
            codec = codecs.get(format, "libmp3lame")

            # Extract audio
            input_stream = ffmpeg.input(video_path)
            output_stream = ffmpeg.output(
                input_stream,
                audio_path,
                acodec=codec,
                vn=None  # No video
            )
            ffmpeg.run(output_stream, overwrite_output=True, quiet=True)

            return {
                "success": True,
                "audio_path": audio_path,
                "message": f"Audio extracted to {format} format"
            }
        except ffmpeg.Error as e:
            logger.error("FFmpeg audio extract error", error=str(e))
            raise RuntimeError(f"Audio extraction failed: {e}")

    async def normalize_audio(
        self,
        input_path: str,
        output_path: str,
        target_lufs: float = -16.0
    ) -> Dict:
        """
        Normalize audio volume to EBU R128 standard.

        Args:
            input_path: Source audio file
            output_path: Output audio file
            target_lufs: Target loudness in LUFS (default -16.0)

        Returns:
            Dict with job_id and status
        """
        self._validate_paths(input_path=input_path, output_path=output_path)

        job_id = str(uuid.uuid4())
        with get_db_session() as db:
            job = FFmpegJob(
                id=job_id,
                user_id="system",
                operation="normalize_audio",
                status="pending",
                progress=0,
                input_path=input_path,
                output_path=output_path,
                operation_metadata={"target_lufs": target_lufs}
            )
            db.add(job)
            db.commit()

        asyncio.create_task(
            self._run_async_job(
                job_id,
                self._normalize_audio_sync,
                input_path,
                output_path,
                target_lufs
            )
        )

        return {"job_id": job_id, "status": "pending"}

    def _normalize_audio_sync(
        self,
        input_path: str,
        output_path: str,
        target_lufs: float
    ) -> Dict:
        """Synchronous audio normalization."""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Apply loudnorm filter (EBU R128)
            input_stream = ffmpeg.input(input_path)
            output_stream = ffmpeg.output(
                input_stream,
                output_path,
                af=f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
                acodec="libmp3lame"
            )
            ffmpeg.run(output_stream, overwrite_output=True, quiet=True)

            return {
                "success": True,
                "output_path": output_path,
                "message": f"Audio normalized to {target_lufs} LUFS"
            }
        except ffmpeg.Error as e:
            logger.error("FFmpeg normalize error", error=str(e))
            raise RuntimeError(f"Audio normalization failed: {e}")

    # =========================================================================
    # Async Job Management
    # =========================================================================

    async def _run_async_job(
        self,
        job_id: str,
        operation: Callable,
        *args
    ) -> None:
        """
        Run FFmpeg operation in background thread.

        Updates job status: pending -> running -> completed/failed
        Tracks progress based on file size (estimated).

        Args:
            job_id: Job identifier
            operation: Synchronous FFmpeg function to run
            *args: Arguments to pass to operation
        """
        with get_db_session() as db:
            job = db.query(FFmpegJob).filter(FFmpegJob.id == job_id).first()
            if not job:
                logger.error("Job not found", job_id=job_id)
                return

            # Update status to running
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.progress = 10
            db.commit()

        try:
            # Run FFmpeg operation in thread pool (non-blocking)
            result = await asyncio.to_thread(operation, *args)

            # Update job status to completed
            with get_db_session() as db:
                job = db.query(FFmpegJob).filter(FFmpegJob.id == job_id).first()
                if job:
                    job.status = "completed"
                    job.progress = 100
                    job.completed_at = datetime.utcnow()
                    job.result = result
                    db.commit()

                    logger.info(
                        "FFmpeg job completed",
                        job_id=job_id,
                        operation=job.operation,
                        result=result
                    )

        except Exception as e:
            # Update job status to failed
            with get_db_session() as db:
                job = db.query(FFmpegJob).filter(FFmpegJob.id == job_id).first()
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    job.completed_at = datetime.utcnow()
                    db.commit()

                    logger.error(
                        "FFmpeg job failed",
                        job_id=job_id,
                        operation=job.operation,
                        error=str(e)
                    )

    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """
        Get current job status and progress.

        Args:
            job_id: Job identifier

        Returns:
            Dict with job status or None if not found
        """
        with get_db_session() as db:
            job = db.query(FFmpegJob).filter(FFmpegJob.id == job_id).first()
            if not job:
                return None

            return {
                "job_id": job.id,
                "status": job.status,
                "progress": job.progress,
                "operation": job.operation,
                "input_path": job.input_path,
                "output_path": job.output_path,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error": job.error,
                "result": job.result
            }

    async def list_user_jobs(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        List all jobs for a user.

        Args:
            user_id: User identifier
            status: Filter by status (pending, running, completed, failed)
            limit: Maximum number of jobs to return

        Returns:
            List of job dicts
        """
        with get_db_session() as db:
            query = db.query(FFmpegJob).filter(FFmpegJob.user_id == user_id)

            if status:
                query = query.filter(FFmpegJob.status == status)

            jobs = query.order_by(FFmpegJob.created_at.desc()).limit(limit).all()

            return [
                {
                    "job_id": job.id,
                    "status": job.status,
                    "progress": job.progress,
                    "operation": job.operation,
                    "input_path": job.input_path,
                    "output_path": job.output_path,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None
                }
                for job in jobs
            ]
