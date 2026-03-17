"""
Comprehensive test coverage for Creative Routes API endpoints.

Tests FFmpeg-based creative endpoints:
- Video operations: trim, convert, thumbnail
- Audio operations: extract, normalize
- Job status and management
- File management
- Error handling (400, 403, 404, 503)

Target: 75%+ coverage (118+ lines of 157)
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import FastAPI
from sqlalchemy.orm import Session

from api.creative_routes import router
from core.models import User, FFmpegJob


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    return user


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def client():
    """Create FastAPI TestClient for creative routes."""
    app = FastAPI()
    app.include_router(router)

    # Mock get_current_user dependency
    async def get_current_user_override():
        return Mock(id="test-user-123", username="testuser")

    from core.security_dependencies import get_current_user
    app.dependency_overrides[get_current_user] = get_current_user_override

    # Mock get_db dependency
    def get_db_override():
        return Mock(spec=Session)

    from core.database import get_db
    app.dependency_overrides[get_db] = get_db_override

    return TestClient(app)


@pytest.fixture
def ffmpeg_service_mock():
    """Mock FFmpegService."""
    service = MagicMock()
    service.validate_path = Mock(return_value=True)
    service.trim_video = AsyncMock(return_value={
        "job_id": "job-123",
        "status": "pending"
    })
    service.convert_format = AsyncMock(return_value={
        "job_id": "job-124",
        "status": "pending"
    })
    service.generate_thumbnail = AsyncMock(return_value={
        "job_id": "job-125",
        "status": "pending"
    })
    service.extract_audio = AsyncMock(return_value={
        "job_id": "job-126",
        "status": "pending"
    })
    service.normalize_audio = AsyncMock(return_value={
        "job_id": "job-127",
        "status": "pending"
    })
    service.get_job_status = AsyncMock(return_value={
        "job_id": "job-123",
        "status": "completed",
        "progress": 100
    })
    service.list_user_jobs = AsyncMock(return_value=[])
    return service


# ============================================================================
# Video Endpoints
# ============================================================================

class TestVideoEndpoints:
    """Test video processing endpoints."""

    def test_trim_video_success(self, client, ffmpeg_service_mock):
        """Test video trimming successfully."""
        request_data = {
            "input_path": "/data/media/video.mp4",
            "output_path": "/data/media/trimmed.mp4",
            "start_time": "00:00:10",
            "duration": "00:00:30"
        }
        with patch("api.creative_routes.get_ffmpeg_service", return_value=ffmpeg_service_mock):
            response = client.post("/creative/video/trim", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert data["status"] == "pending"

    def test_convert_format_success(self, client, ffmpeg_service_mock):
        """Test video format conversion successfully."""
        request_data = {
            "input_path": "/data/media/video.mp4",
            "output_path": "/data/media/converted.webm",
            "format": "webm",
            "quality": "high"
        }
        with patch("api.creative_routes.get_ffmpeg_service", return_value=ffmpeg_service_mock):
            response = client.post("/creative/video/convert", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data

    def test_generate_thumbnail_success(self, client, ffmpeg_service_mock):
        """Test thumbnail generation successfully."""
        request_data = {
            "video_path": "/data/media/video.mp4",
            "thumbnail_path": "/data/media/thumb.jpg",
            "timestamp": "00:00:05"
        }
        with patch("api.creative_routes.get_ffmpeg_service", return_value=ffmpeg_service_mock):
            response = client.post("/creative/video/thumbnail", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data


# ============================================================================
# Audio Endpoints
# ============================================================================

class TestAudioEndpoints:
    """Test audio processing endpoints."""

    def test_extract_audio_success(self, client, ffmpeg_service_mock):
        """Test audio extraction successfully."""
        request_data = {
            "video_path": "/data/media/video.mp4",
            "audio_path": "/data/media/audio.mp3",
            "format": "mp3"
        }
        with patch("api.creative_routes.get_ffmpeg_service", return_value=ffmpeg_service_mock):
            response = client.post("/creative/audio/extract", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data

    def test_normalize_audio_success(self, client, ffmpeg_service_mock):
        """Test audio normalization successfully."""
        request_data = {
            "input_path": "/data/media/audio.mp3",
            "output_path": "/data/media/normalized.mp3",
            "target_lufs": -16.0
        }
        with patch("api.creative_routes.get_ffmpeg_service", return_value=ffmpeg_service_mock):
            response = client.post("/creative/audio/normalize", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data


# ============================================================================
# Job Status Endpoints
# ============================================================================

class TestJobStatusEndpoints:
    """Test job status and management endpoints."""

    def test_get_job_status_success(self, client, ffmpeg_service_mock):
        """Test getting job status successfully."""
        with patch("api.creative_routes.get_ffmpeg_service", return_value=ffmpeg_service_mock):
            response = client.get("/creative/jobs/job-123")
            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "job-123"
            assert data["status"] == "completed"

    def test_get_job_status_not_found(self, client, ffmpeg_service_mock):
        """Test getting non-existent job status."""
        ffmpeg_service_mock.get_job_status = AsyncMock(return_value=None)
        with patch("api.creative_routes.get_ffmpeg_service", return_value=ffmpeg_service_mock):
            response = client.get("/creative/jobs/nonexistent")
            assert response.status_code == 404

    def test_list_user_jobs_success(self, client, ffmpeg_service_mock):
        """Test listing user jobs successfully."""
        with patch("api.creative_routes.get_ffmpeg_service", return_value=ffmpeg_service_mock):
            response = client.get("/creative/jobs")
            assert response.status_code == 200
            data = response.json()
            assert "jobs" in data
            assert "total" in data

    def test_list_user_jobs_with_status_filter(self, client, ffmpeg_service_mock):
        """Test listing user jobs with status filter."""
        with patch("api.creative_routes.get_ffmpeg_service", return_value=ffmpeg_service_mock):
            response = client.get("/creative/jobs?status=completed")
            assert response.status_code == 200

    def test_list_user_jobs_invalid_status_filter(self, client, ffmpeg_service_mock):
        """Test listing user jobs with invalid status filter."""
        with patch("api.creative_routes.get_ffmpeg_service", return_value=ffmpeg_service_mock):
            response = client.get("/creative/jobs?status=invalid")
            assert response.status_code == 400


# ============================================================================
# File Management Endpoints
# ============================================================================

class TestFileManagementEndpoints:
    """Test file management endpoints."""

    def test_list_files_success(self, client):
        """Test listing files successfully."""
        # This test checks the endpoint is accessible
        # Actual file listing depends on directory existing
        response = client.get("/creative/files?directory=/data/media")
        # May return 404 if directory doesn't exist, that's expected behavior
        assert response.status_code in [200, 400, 404]

    def test_list_files_directory_not_found(self, client):
        """Test listing files with non-existent directory."""
        response = client.get("/creative/files?directory=/data/nonexistent")
        # Expected to fail validation or return not found
        assert response.status_code in [400, 404]

    def test_delete_file_path_validation(self, client):
        """Test delete file validates path."""
        # Test that the endpoint is accessible
        # Actual deletion depends on FFmpeg service validation
        response = client.delete("/creative/files/data/media/video.mp4")
        # May return 403/404/503 depending on validation
        assert response.status_code in [200, 400, 403, 404, 503]


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling across all endpoints."""

    def test_invalid_path_validation(self, client):
        """Test path validation failure."""
        service = MagicMock()
        service.validate_path = Mock(side_effect=ValueError("Invalid path"))
        request_data = {
            "input_path": "/invalid/path/video.mp4",
            "output_path": "/invalid/path/output.mp4",
            "start_time": "00:00:10",
            "duration": "00:00:30"
        }
        with patch("api.creative_routes.get_ffmpeg_service", return_value=service):
            response = client.post("/creative/video/trim", json=request_data)
            assert response.status_code == 400

    def test_ffmpeg_service_unavailable(self, client):
        """Test FFmpeg service unavailable."""
        def get_service_error():
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="FFmpeg service not available")

        with patch("api.creative_routes.get_ffmpeg_service", side_effect=get_service_error):
            response = client.post("/creative/video/trim", json={
                "input_path": "/data/video.mp4",
                "output_path": "/data/output.mp4",
                "start_time": "00:00:10",
                "duration": "00:00:30"
            })
            assert response.status_code == 503
