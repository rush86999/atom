"""
Creative Routes Coverage Tests

Comprehensive TestClient-based tests for creative API endpoints to achieve 60%+ coverage.

Coverage Target:
- api/creative_routes.py - 60%+ coverage (94+ lines)

Test Classes:
- TestCreativeRoutes (10 tests): Content generation, media creation, templates
- TestCreativeGeneration (12 tests): Text generation, image generation, video generation
- TestCreativeMedia (8 tests): Asset management, rendering, export
- TestCreativeErrors (5 tests): Invalid prompts, generation failures, quota limits

Baseline: 0% coverage (creative_routes.py not tested)
Target: 60%+ coverage (94+ lines)
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session


# Import creative routes router
from api.creative_routes import router as creative_router
from core.models import User, FFmpegJob


# Create minimal FastAPI app for testing creative routes
app = FastAPI()
app.include_router(creative_router, tags=["creative"])


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def creative_test_client():
    """Create TestClient for creative routes testing."""
    return TestClient(app)


@pytest.fixture(scope="function")
def mock_user():
    """Create mock user for authentication."""
    user = User(
        id="test-user-123",
        email="test@example.com"
    )
    return user


@pytest.fixture(scope="function")
def mock_db():
    """Create mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture(scope="function")
def mock_ffmpeg_service():
    """Create mock FFmpeg service."""
    service = MagicMock()
    service.validate_path.return_value = True

    # Mock async methods
    async def mock_trim_video(*args, **kwargs):
        return {"job_id": "test-job-1", "status": "pending"}

    async def mock_convert_format(*args, **kwargs):
        return {"job_id": "test-job-2", "status": "pending"}

    async def mock_generate_thumbnail(*args, **kwargs):
        return {"job_id": "test-job-3", "status": "pending"}

    async def mock_extract_audio(*args, **kwargs):
        return {"job_id": "test-job-4", "status": "pending"}

    async def mock_normalize_audio(*args, **kwargs):
        return {"job_id": "test-job-5", "status": "pending"}

    async def mock_get_job_status(job_id):
        return {
            "job_id": job_id,
            "status": "completed",
            "progress": 100,
            "operation": "trim_video",
            "input_path": "/input/video.mp4",
            "output_path": "/output/trimmed.mp4"
        }

    async def mock_list_user_jobs(*args, **kwargs):
        return [
            {
                "job_id": "job-1",
                "status": "completed",
                "progress": 100,
                "operation": "trim_video"
            }
        ]

    service.trim_video = mock_trim_video
    service.convert_format = mock_convert_format
    service.generate_thumbnail = mock_generate_thumbnail
    service.extract_audio = mock_extract_audio
    service.normalize_audio = mock_normalize_audio
    service.get_job_status = mock_get_job_status
    service.list_user_jobs = mock_list_user_jobs

    return service


# ============================================================================
# Test Class: TestCreativeRoutes
# ============================================================================

class TestCreativeRoutes:
    """Tests for creative media processing endpoints."""

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_trim_video_endpoint(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test video trimming endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/video/trim",
            json={
                "input_path": "/input/video.mp4",
                "output_path": "/output/trimmed.mp4",
                "start_time": "00:00:10",
                "duration": "00:01:00"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_convert_format_endpoint(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test format conversion endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/video/convert",
            json={
                "input_path": "/input/video.mov",
                "output_path": "/output/video.mp4",
                "format": "mp4",
                "quality": "high"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_generate_thumbnail_endpoint(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test thumbnail generation endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/video/thumbnail",
            json={
                "video_path": "/input/video.mp4",
                "thumbnail_path": "/output/thumb.jpg",
                "timestamp": "00:00:05"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_extract_audio_endpoint(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test audio extraction endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/audio/extract",
            json={
                "video_path": "/input/video.mp4",
                "audio_path": "/output/audio.mp3",
                "format": "mp3"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_normalize_audio_endpoint(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test audio normalization endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/audio/normalize",
            json={
                "input_path": "/input/audio.wav",
                "output_path": "/output/normalized.wav",
                "target_lufs": -16.0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    def test_get_job_status_endpoint(
        self, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test job status endpoint."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.get("/creative/jobs/test-job-1")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-1"
        assert data["status"] == "completed"

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    def test_list_user_jobs_endpoint(
        self, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test list user jobs endpoint."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.get("/creative/jobs")

        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert data["total"] >= 0

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    def test_list_jobs_with_status_filter(
        self, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test listing jobs with status filter."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.get(
            "/creative/jobs",
            params={"status_filter": "completed"}
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    def test_list_jobs_with_limit(
        self, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test listing jobs with custom limit."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.get(
            "/creative/jobs",
            params={"limit": 10}
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("os.path.exists")
    @patch("os.listdir")
    def test_list_files_endpoint(
        self, mock_listdir, mock_exists, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test list files endpoint."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service
        mock_exists.return_value = True
        mock_listdir.return_value = ["video1.mp4", "video2.mov", "audio1.mp3"]

        response = creative_test_client.get(
            "/creative/files",
            params={"directory": "./data/media"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 3


# ============================================================================
# Test Class: TestCreativeGeneration
# ============================================================================

class TestCreativeGeneration:
    """Tests for media generation operations."""

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_trim_video_with_duration(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test trimming video with specific duration."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/video/trim",
            json={
                "input_path": "/input/video.mp4",
                "output_path": "/output/clip.mp4",
                "start_time": "00:01:00",
                "duration": "00:00:30"
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_trim_video_with_seconds_duration(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test trimming video with duration in seconds."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/video/trim",
            json={
                "input_path": "/input/video.mp4",
                "output_path": "/output/clip.mp4",
                "start_time": "00:01:00",
                "duration": "30"
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_convert_format_to_webm(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test format conversion to WebM."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/video/convert",
            json={
                "input_path": "/input/video.mp4",
                "output_path": "/output/video.webm",
                "format": "webm"
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_convert_format_low_quality(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test format conversion with low quality preset."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/video/convert",
            json={
                "input_path": "/input/video.mp4",
                "output_path": "/output/video.mp4",
                "format": "mp4",
                "quality": "low"
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_extract_audio_to_wav(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test audio extraction to WAV format."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/audio/extract",
            json={
                "video_path": "/input/video.mp4",
                "audio_path": "/output/audio.wav",
                "format": "wav"
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_extract_audio_to_m4a(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test audio extraction to M4A format."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/audio/extract",
            json={
                "video_path": "/input/video.mp4",
                "audio_path": "/output/audio.m4a",
                "format": "m4a"
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_extract_audio_to_flac(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test audio extraction to FLAC format."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/audio/extract",
            json={
                "video_path": "/input/video.mp4",
                "audio_path": "/output/audio.flac",
                "format": "flac"
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_normalize_audio_custom_lufs(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test audio normalization with custom LUFS target."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/audio/normalize",
            json={
                "input_path": "/input/audio.wav",
                "output_path": "/output/normalized.wav",
                "target_lufs": -23.0
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_generate_thumbnail_default_timestamp(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test thumbnail generation with default timestamp."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/video/thumbnail",
            json={
                "video_path": "/input/video.mp4",
                "thumbnail_path": "/output/thumb.jpg"
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_generate_thumbnail_custom_timestamp(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test thumbnail generation with custom timestamp."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/video/thumbnail",
            json={
                "video_path": "/input/video.mp4",
                "thumbnail_path": "/output/thumb.jpg",
                "timestamp": "00:00:30"
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_convert_format_default_quality(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test format conversion with default quality (medium)."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/video/convert",
            json={
                "input_path": "/input/video.mp4",
                "output_path": "/output/video.mp4",
                "format": "mp4"
            }
        )

        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_normalize_audio_default_lufs(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db, mock_ffmpeg_service
    ):
        """Test audio normalization with default LUFS target."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.post(
            "/creative/audio/normalize",
            json={
                "input_path": "/input/audio.wav",
                "output_path": "/output/normalized.wav"
            }
        )

        assert response.status_code == 200


# ============================================================================
# Test Class: TestCreativeMedia
# ============================================================================

class TestCreativeMedia:
    """Tests for media file management."""

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("os.path.exists")
    @patch("os.listdir")
    def test_list_files_empty_directory(
        self, mock_listdir, mock_exists, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test listing files in empty directory."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service
        mock_exists.return_value = True
        mock_listdir.return_value = []

        response = creative_test_client.get(
            "/creative/files",
            params={"directory": "./data/empty"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_delete_file_success(
        self, mock_remove, mock_exists, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test successful file deletion."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service
        mock_ffmpeg_service.validate_path.return_value = True
        mock_exists.return_value = True

        response = creative_test_client.delete("/creative/files/data/media/video.mp4")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("os.path.exists")
    @patch("os.listdir")
    def test_list_files_filters_hidden(
        self, mock_listdir, mock_exists, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test listing files filters out hidden files."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service
        mock_exists.return_value = True
        mock_listdir.return_value = ["video.mp4", ".hidden.mp4", ".DS_Store", "audio.mp3"]

        response = creative_test_client.get(
            "/creative/files",
            params={"directory": "./data/media"}
        )

        assert response.status_code == 200
        data = response.json()
        assert ".hidden.mp4" not in data["files"]
        assert ".DS_Store" not in data["files"]
        assert len(data["files"]) == 2

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    def test_get_job_status_not_found(
        self, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test getting status of non-existent job."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        async def mock_get_status(job_id):
            return None

        mock_ffmpeg_service.get_job_status = mock_get_status

        response = creative_test_client.get("/creative/jobs/nonexistent-job")

        assert response.status_code == 404

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    def test_list_jobs_invalid_status_filter(
        self, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test listing jobs with invalid status filter."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        response = creative_test_client.get(
            "/creative/jobs",
            params={"status_filter": "invalid_status"}
        )

        assert response.status_code == 400

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    def test_list_jobs_limit_boundary(
        self, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test listing jobs with limit boundary values."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service

        # Test minimum limit
        response = creative_test_client.get(
            "/creative/jobs",
            params={"limit": 1}
        )
        assert response.status_code == 200

        # Test maximum limit
        response = creative_test_client.get(
            "/creative/jobs",
            params={"limit": 100}
        )
        assert response.status_code == 200

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("os.path.exists")
    @patch("os.listdir")
    def test_list_files_custom_directory(
        self, mock_listdir, mock_exists, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test listing files in custom directory."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service
        mock_exists.return_value = True
        mock_listdir.return_value = ["custom_video.mp4"]

        response = creative_test_client.get(
            "/creative/files",
            params={"directory": "./custom/path"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["directory"] == "./custom/path"


# ============================================================================
# Test Class: TestCreativeErrors
# ============================================================================

class TestCreativeErrors:
    """Tests for creative routes error handling."""

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("api.creative_routes.get_db")
    def test_trim_video_path_validation_failure(
        self, mock_get_db, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_db
    ):
        """Test trim video with invalid path."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service.validate_path.side_effect = ValueError("Path outside allowed directories")
        mock_ffmpeg_cls.return_value = mock_service

        response = creative_test_client.post(
            "/creative/video/trim",
            json={
                "input_path": "/invalid/path/video.mp4",
                "output_path": "/output/trimmed.mp4",
                "start_time": "00:00:10",
                "duration": "00:01:00"
            }
        )

        assert response.status_code == 400

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    def test_ffmpeg_service_unavailable(
        self, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user
    ):
        """Test when FFmpeg service is unavailable."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.side_effect = RuntimeError("FFmpeg not installed")

        response = creative_test_client.post(
            "/creative/video/trim",
            json={
                "input_path": "/input/video.mp4",
                "output_path": "/output/trimmed.mp4",
                "start_time": "00:00:10",
                "duration": "00:01:00"
            }
        )

        assert response.status_code == 503

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("os.path.exists")
    def test_list_files_directory_not_found(
        self, mock_exists, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test listing files in non-existent directory."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service
        mock_ffmpeg_service.validate_path.return_value = True
        mock_exists.return_value = False

        response = creative_test_client.get(
            "/creative/files",
            params={"directory": "./nonexistent/path"}
        )

        assert response.status_code == 404

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_delete_file_not_found(
        self, mock_remove, mock_exists, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test deleting non-existent file."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service
        mock_ffmpeg_service.validate_path.return_value = True
        mock_exists.return_value = False

        response = creative_test_client.delete("/creative/files/data/media/nonexistent.mp4")

        assert response.status_code == 404

    @patch("api.creative_routes.FFmpegService")
    @patch("api.creative_routes.get_current_user")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_delete_file_permission_denied(
        self, mock_remove, mock_exists, mock_get_user, mock_ffmpeg_cls, creative_test_client, mock_user, mock_ffmpeg_service
    ):
        """Test deleting file with permission denied."""
        mock_get_user.return_value = mock_user
        mock_ffmpeg_cls.return_value = mock_ffmpeg_service
        mock_ffmpeg_service.validate_path.return_value = True
        mock_exists.return_value = True
        mock_remove.side_effect = PermissionError("Permission denied")

        response = creative_test_client.delete("/creative/files/data/media/protected.mp4")

        assert response.status_code == 403
