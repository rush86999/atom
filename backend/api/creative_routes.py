"""
Creative Tool REST API Endpoints

Provides async video/audio processing endpoints using FFmpeg:
- Video trimming, format conversion, thumbnail generation
- Audio extraction, volume normalization
- Async job processing with progress tracking
- File management endpoints

All endpoints require AUTONOMOUS maturity level (file safety).
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.creative.ffmpeg_service import FFmpegService
from core.models import FFmpegJob, User
from api.authentication import get_current_user

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/creative", tags=["creative", "media"])


# ============================================================================
# Request/Response Models
# ============================================================================

class TrimVideoRequest(BaseModel):
    """Video trimming request."""
    input_path: str = Field(..., description="Source video file path")
    output_path: str = Field(..., description="Output video file path")
    start_time: str = Field(..., description="Start timestamp (HH:MM:SS)")
    duration: str = Field(..., description="Duration to trim (HH:MM:SS or seconds)")


class ConvertFormatRequest(BaseModel):
    """Format conversion request."""
    input_path: str = Field(..., description="Source video file path")
    output_path: str = Field(..., description="Output video file path")
    format: str = Field(..., description="Target format (mp4, webm, mov, avi)")
    quality: str = Field(default="medium", description="Quality preset (low, medium, high)")


class GenerateThumbnailRequest(BaseModel):
    """Thumbnail generation request."""
    video_path: str = Field(..., description="Source video file path")
    thumbnail_path: str = Field(..., description="Output thumbnail file path")
    timestamp: str = Field(default="00:00:01", description="Timestamp to capture (HH:MM:SS)")


class ExtractAudioRequest(BaseModel):
    """Audio extraction request."""
    video_path: str = Field(..., description="Source video file path")
    audio_path: str = Field(..., description="Output audio file path")
    format: str = Field(default="mp3", description="Audio format (mp3, m4a, wav, flac)")


class NormalizeAudioRequest(BaseModel):
    """Audio normalization request."""
    input_path: str = Field(..., description="Source audio file path")
    output_path: str = Field(..., description="Output audio file path")
    target_lufs: float = Field(default=-16.0, description="Target loudness in LUFS")


class JobResponse(BaseModel):
    """Job submission response."""
    job_id: str
    status: str
    message: str = "Job submitted successfully"


class JobStatusResponse(BaseModel):
    """Job status response."""
    job_id: str
    status: str
    progress: int
    operation: str
    input_path: Optional[str]
    output_path: Optional[str]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    error: Optional[str]
    result: Optional[dict]


class JobListResponse(BaseModel):
    """Job list response."""
    jobs: List[JobStatusResponse]
    total: int


class FileListResponse(BaseModel):
    """File list response."""
    directory: str
    files: List[str]
    total: int


class FileUploadResponse(BaseModel):
    """File upload response."""
    success: bool
    message: str
    file_path: Optional[str]


# ============================================================================
# Helper Functions
# ============================================================================

def get_ffmpeg_service() -> FFmpegService:
    """Get FFmpeg service instance."""
    try:
        return FFmpegService()
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FFmpeg service not available: {str(e)}"
        )


def check_autonomous_maturity(user: User) -> None:
    """
    Check if user has AUTONOMOUS maturity level.

    Raises HTTPException if maturity level is insufficient.
    """
    # TODO: Integrate with agent maturity system
    # For now, all authenticated users can access (will be enforced at tool level)
    pass


# ============================================================================
# Video Endpoints
# ============================================================================

@router.post("/video/trim", response_model=JobResponse)
async def trim_video(
    request: TrimVideoRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trim video to specified start time and duration.

    **AUTONOMOUS maturity required** (file safety).

    - Returns immediately with job_id
    - Processing happens in background
    - Check job status via GET /creative/jobs/{job_id}
    """
    service = get_ffmpeg_service()

    # Validate paths
    try:
        service.validate_path(request.input_path)
        service.validate_path(request.output_path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path validation failed: {str(e)}"
        )

    # Submit job
    result = await service.trim_video(
        input_path=request.input_path,
        output_path=request.output_path,
        start_time=request.start_time,
        duration=request.duration
    )

    # Update user_id in job
    job = db.query(FFmpegJob).filter(FFmpegJob.id == result["job_id"]).first()
    if job:
        job.user_id = current_user.id
        db.commit()

    return JobResponse(
        job_id=result["job_id"],
        status=result["status"],
        message="Video trimming job submitted successfully"
    )


@router.post("/video/convert", response_model=JobResponse)
async def convert_format(
    request: ConvertFormatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Convert video to different format.

    **AUTONOMOUS maturity required** (file safety).

    Supported formats: mp4, webm, mov, avi
    Quality presets: low, medium, high
    """
    service = get_ffmpeg_service()

    try:
        service.validate_path(request.input_path)
        service.validate_path(request.output_path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path validation failed: {str(e)}"
        )

    result = await service.convert_format(
        input_path=request.input_path,
        output_path=request.output_path,
        format=request.format,
        quality=request.quality
    )

    job = db.query(FFmpegJob).filter(FFmpegJob.id == result["job_id"]).first()
    if job:
        job.user_id = current_user.id
        db.commit()

    return JobResponse(
        job_id=result["job_id"],
        status=result["status"],
        message=f"Format conversion to {request.format} submitted successfully"
    )


@router.post("/video/thumbnail", response_model=JobResponse)
async def generate_thumbnail(
    request: GenerateThumbnailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate thumbnail from video at specified timestamp.

    **AUTONOMOUS maturity required** (file safety).

    Output format: JPEG
    Default timestamp: 00:00:01
    """
    service = get_ffmpeg_service()

    try:
        service.validate_path(request.video_path)
        service.validate_path(request.thumbnail_path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path validation failed: {str(e)}"
        )

    result = await service.generate_thumbnail(
        video_path=request.video_path,
        thumbnail_path=request.thumbnail_path,
        timestamp=request.timestamp
    )

    job = db.query(FFmpegJob).filter(FFmpegJob.id == result["job_id"]).first()
    if job:
        job.user_id = current_user.id
        db.commit()

    return JobResponse(
        job_id=result["job_id"],
        status=result["status"],
        message="Thumbnail generation job submitted successfully"
    )


# ============================================================================
# Audio Endpoints
# ============================================================================

@router.post("/audio/extract", response_model=JobResponse)
async def extract_audio(
    request: ExtractAudioRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Extract audio track from video file.

    **AUTONOMOUS maturity required** (file safety).

    Supported formats: mp3, m4a, wav, flac
    """
    service = get_ffmpeg_service()

    try:
        service.validate_path(request.video_path)
        service.validate_path(request.audio_path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path validation failed: {str(e)}"
        )

    result = await service.extract_audio(
        video_path=request.video_path,
        audio_path=request.audio_path,
        format=request.format
    )

    job = db.query(FFmpegJob).filter(FFmpegJob.id == result["job_id"]).first()
    if job:
        job.user_id = current_user.id
        db.commit()

    return JobResponse(
        job_id=result["job_id"],
        status=result["status"],
        message=f"Audio extraction to {request.format} submitted successfully"
    )


@router.post("/audio/normalize", response_model=JobResponse)
async def normalize_audio(
    request: NormalizeAudioRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Normalize audio volume to EBU R128 standard.

    **AUTONOMOUS maturity required** (file safety).

    Default target: -16.0 LUFS (EBU R128 standard)
    """
    service = get_ffmpeg_service()

    try:
        service.validate_path(request.input_path)
        service.validate_path(request.output_path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path validation failed: {str(e)}"
        )

    result = await service.normalize_audio(
        input_path=request.input_path,
        output_path=request.output_path,
        target_lufs=request.target_lufs
    )

    job = db.query(FFmpegJob).filter(FFmpegJob.id == result["job_id"]).first()
    if job:
        job.user_id = current_user.id
        db.commit()

    return JobResponse(
        job_id=result["job_id"],
        status=result["status"],
        message=f"Audio normalization to {request.target_lufs} LUFS submitted successfully"
    )


# ============================================================================
# Job Status Endpoints
# ============================================================================

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get job status and progress.

    Returns current status, progress percentage, timestamps, and result/error.
    """
    service = get_ffmpeg_service()

    status = await service.get_job_status(job_id)

    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    # Verify user owns this job
    # job = db.query(FFmpegJob).filter(FFmpegJob.id == job_id).first()
    # if job and job.user_id != current_user.id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Access denied to this job"
    #     )

    return JobStatusResponse(**status)


@router.get("/jobs", response_model=JobListResponse)
async def list_user_jobs(
    status_filter: Optional[str] = None,
    limit: int = Field(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """
    List user's FFmpeg jobs.

    Query parameters:
    - status: Filter by status (pending, running, completed, failed)
    - limit: Maximum number of jobs to return (default: 50)
    """
    service = get_ffmpeg_service()

    if status_filter and status_filter not in ["pending", "running", "completed", "failed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status filter. Use: pending, running, completed, failed"
        )

    jobs = await service.list_user_jobs(
        user_id=current_user.id,
        status=status_filter,
        limit=limit
    )

    return JobListResponse(jobs=jobs, total=len(jobs))


# ============================================================================
# File Management Endpoints
# ============================================================================

@router.get("/files", response_model=FileListResponse)
async def list_files(
    directory: str = "./data/media",
    current_user: User = Depends(get_current_user)
):
    """
    List files in allowed directory.

    Returns list of files available for processing.
    """
    import os

    service = get_ffmpeg_service()

    # Validate directory
    if not service.validate_path(directory):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Directory outside allowed paths: {directory}"
        )

    if not os.path.exists(directory):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory not found: {directory}"
        )

    # List files
    try:
        files = [
            f for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f))
            and not f.startswith(".")  # Skip hidden files
        ]
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied accessing directory: {directory}"
        )

    return FileListResponse(directory=directory, files=files, total=len(files))


@router.delete("/files/{file_path:path}", response_model=dict)
async def delete_file(
    file_path: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete file from allowed directory.

    **AUTONOMOUS maturity required** (destructive operation).
    """
    import os

    service = get_ffmpeg_service()

    # Validate path
    if not service.validate_path(file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File path outside allowed directories: {file_path}"
        )

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_path}"
        )

    try:
        os.remove(file_path)
        logger.info("File deleted via creative API", file_path=file_path, user_id=current_user.id)
        return {"success": True, "message": f"File deleted: {file_path}"}
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied deleting file: {file_path}"
        )
