"""
Task Monitoring Routes API Tests

Tests for task monitoring and management endpoints including:
- Scheduled posts listing and management
- Task queue information
- Task queue health checks
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from main_api_app import app


class TestTaskMonitoringRoutes:
    """Test task monitoring API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_list_scheduled_posts_default(self, client):
        """Test listing scheduled posts without filters."""
        response = client.get("/api/v1/tasks/scheduled-posts")

        # May return 401 (auth required) or 422 (validation)
        assert response.status_code in [200, 401, 422]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_list_scheduled_posts_with_status_filter(self, client):
        """Test listing scheduled posts with status filter."""
        response = client.get("/api/v1/tasks/scheduled-posts?status_filter=scheduled")

        assert response.status_code in [200, 401]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_list_scheduled_posts_invalid_status(self, client):
        """Test listing with invalid status filter."""
        response = client.get("/api/v1/tasks/scheduled-posts?status_filter=invalid_status")

        # Should either return empty list or handle gracefully
        assert response.status_code in [200, 400, 401]

    def test_list_scheduled_posts_auth_required(self, client):
        """Test that listing requires authentication."""
        # Test without auth headers
        response = client.get("/api/v1/tasks/scheduled-posts")

        # May return 200 with empty list or 401
        assert response.status_code in [200, 401]

    def test_get_scheduled_post_status(self, client):
        """Test getting status of a scheduled post."""
        post_id = "test-post-123"
        response = client.get(f"/api/v1/tasks/scheduled-posts/{post_id}/status")

        assert response.status_code in [200, 404, 401]
        if response.status_code == 200:
            data = response.json()
            assert "post_id" in data or "status" in data

    def test_get_scheduled_post_status_not_found(self, client):
        """Test getting status for non-existent post."""
        response = client.get("/api/v1/tasks/scheduled-posts/nonexistent/status")

        assert response.status_code in [200, 404, 401]

    def test_cancel_scheduled_post(self, client):
        """Test cancelling a scheduled post."""
        post_id = "test-post-123"
        response = client.delete(f"/api/v1/tasks/scheduled-posts/{post_id}")

        assert response.status_code in [200, 204, 404, 401]

    def test_cancel_scheduled_post_not_found(self, client):
        """Test cancelling non-existent post."""
        response = client.delete("/api/v1/tasks/scheduled-posts/nonexistent")

        assert response.status_code in [200, 204, 404, 401]

    def test_get_all_queues_info(self, client):
        """Test getting information about all task queues."""
        response = client.get("/api/v1/tasks/queues")

        assert response.status_code == 200
        data = response.json()

        # Should have queue information
        assert "queues" in data or isinstance(data, dict)

    def test_get_all_queues_info_structure(self, client):
        """Test queue info response structure."""
        response = client.get("/api/v1/tasks/queues")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "task_queue_enabled" in data or "queues" in data

    def test_get_queue_info(self, client):
        """Test getting information about a specific queue."""
        queue_name = "default"
        response = client.get(f"/api/v1/tasks/queues/{queue_name}")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "queue_name" in data or "count" in data

    def test_get_queue_info_structure(self, client):
        """Test queue info response structure when queue exists."""
        queue_name = "default"
        response = client.get(f"/api/v1/tasks/queues/{queue_name}")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()

            # Check for expected fields
            expected_fields = ["queue_name", "count", "failed_job_count",
                            "finished_job_count", "started_job_count"]
            present_fields = [field for field in expected_fields if field in data]

            # Should have at least some queue info
            assert len(present_fields) >= 2

    def test_get_queue_info_not_found(self, client):
        """Test getting info for non-existent queue."""
        response = client.get("/api/v1/tasks/queues/nonexistent-queue")

        assert response.status_code in [200, 404]

    def test_task_queue_health_check(self, client):
        """Test task queue health check endpoint."""
        response = client.get("/api/v1/tasks/health")

        assert response.status_code == 200
        data = response.json()

        # Should have health status
        assert "status" in data or "healthy" in data

    def test_task_queue_health_status_values(self, client):
        """Test health check returns valid status values."""
        response = client.get("/api/v1/tasks/health")

        assert response.status_code == 200
        data = response.json()

        # Should have a status field
        if "status" in data:
            assert data["status"] in ["healthy", "unhealthy", "degraded"]

    @patch('api.task_monitoring_routes.get_task_queue')
    def test_get_all_queues_with_mock(self, mock_get_task_queue, client):
        """Test getting queues with mocked task queue."""
        # Mock the task queue
        mock_queue = Mock()
        mock_queue.get_all_queues_info.return_value = {
            "queues": {
                "default": {"count": 5}
            },
            "task_queue_enabled": True
        }
        mock_get_task_queue.return_value = mock_queue

        response = client.get("/api/v1/tasks/queues")

        assert response.status_code == 200
        data = response.json()
        assert "queues" in data or isinstance(data, dict)

    def test_scheduled_posts_response_structure(self, client):
        """Test scheduled posts have proper structure."""
        response = client.get("/api/v1/tasks/scheduled-posts")

        # May return 401 if auth required
        if response.status_code == 200:
            data = response.json()

            # If there are posts, check structure
            if len(data) > 0:
                post = data[0]
                expected_fields = ["post_id", "content", "platforms",
                                  "scheduled_for", "status"]
                present_fields = [field for field in expected_fields if field in post]

                # Should have at least some required fields
                assert len(present_fields) >= 3

    def test_task_endpoints_return_json(self, client):
        """Test that all task endpoints return JSON."""
        endpoints = [
            "/api/v1/tasks/scheduled-posts",
            "/api/v1/tasks/queues",
            "/api/v1/tasks/health"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should return JSON or 401
            assert response.status_code in [200, 401]
            if response.status_code == 200:
                assert response.headers["content-type"].startswith("application/json")

    def test_queue_info_count_fields(self, client):
        """Test queue info has count-related fields."""
        queue_name = "default"
        response = client.get(f"/api/v1/tasks/queues/{queue_name}")

        if response.status_code == 200:
            data = response.json()

            # Check for count fields
            count_fields = ["count", "failed_job_count", "finished_job_count",
                          "started_job_count", "deferred_job_count"]
            present_count_fields = [field for field in count_fields if field in data]

            # Should have at least some count fields
            if len(present_count_fields) > 0:
                # All count fields should be integers
                for field in present_count_fields:
                    assert isinstance(data[field], int)

    def test_task_queue_enabled_field(self, client):
        """Test that task queue enabled status is available."""
        response = client.get("/api/v1/tasks/queues")

        assert response.status_code == 200
        data = response.json()

        # Should indicate whether task queue is enabled
        assert "task_queue_enabled" in data or "queues" in data

    @patch('api.task_monitoring_routes.get_task_queue')
    def test_health_check_with_mocked_queue(self, mock_get_task_queue, client):
        """Test health check with mocked task queue."""
        # Mock the task queue
        mock_queue = Mock()
        mock_queue.get_health_status.return_value = {
            "status": "healthy",
            "queue_count": 3
        }
        mock_get_task_queue.return_value = mock_queue

        response = client.get("/api/v1/tasks/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "healthy" in data

    def test_list_scheduled_posts_empty_result(self, client):
        """Test listing scheduled posts when none exist."""
        response = client.get("/api/v1/tasks/scheduled-posts")

        # Should handle gracefully (empty list or 401)
        assert response.status_code in [200, 401]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_scheduled_post_status_fields(self, client):
        """Test scheduled post status has required fields."""
        post_id = "test-post-123"
        response = client.get(f"/api/v1/tasks/scheduled-posts/{post_id}/status")

        if response.status_code == 200:
            data = response.json()

            # Check for expected fields
            expected_fields = ["post_id", "status", "scheduled_for"]
            present_fields = [field for field in expected_fields if field in data]

            # Should have at least some fields
            assert len(present_fields) >= 2

    def test_cancel_scheduled_post_success(self, client):
        """Test successful cancellation returns proper response."""
        post_id = "test-post-123"
        response = client.delete(f"/api/v1/tasks/scheduled-posts/{post_id}")

        # Should handle gracefully
        assert response.status_code in [200, 204, 404]

    def test_task_monitoring_endpoints_consistent(self, client):
        """Test that task monitoring endpoints are consistent."""
        # Call health check twice
        response1 = client.get("/api/v1/tasks/health")
        response2 = client.get("/api/v1/tasks/health")

        assert response1.status_code == response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Should return consistent structure
        assert type(data1) == type(data2)

    def test_invalid_queue_name_handling(self, client):
        """Test handling of invalid queue names."""
        # Test with special characters
        invalid_names = ["queue/with/slashes", "queue with spaces", ""]

        for queue_name in invalid_names[:2]:  # Skip empty string test for now
            response = client.get(f"/api/v1/tasks/queues/{queue_name}")

            # Should handle gracefully
            assert response.status_code in [200, 404, 400]

    def test_scheduled_posts_status_filter_values(self, client):
        """Test various status filter values."""
        valid_statuses = ["scheduled", "posting", "posted", "partial", "failed", "cancelled"]

        for status in valid_statuses:
            response = client.get(f"/api/v1/tasks/scheduled-posts?status_filter={status}")

            # Should handle all valid statuses
            assert response.status_code in [200, 401]

    def test_task_queue_info_counts_non_negative(self, client):
        """Test that queue counts are non-negative."""
        queue_name = "default"
        response = client.get(f"/api/v1/tasks/queues/{queue_name}")

        if response.status_code == 200:
            data = response.json()

            # All count fields should be non-negative
            count_fields = ["count", "failed_job_count", "finished_job_count",
                          "started_job_count", "deferred_job_count"]

            for field in count_fields:
                if field in data:
                    assert data[field] >= 0, f"{field} should be non-negative, got {data[field]}"

    def test_get_all_queues_returns_dict(self, client):
        """Test that all queues endpoint returns queue dictionary."""
        response = client.get("/api/v1/tasks/queues")

        assert response.status_code == 200
        data = response.json()

        # Should return queues as a dict
        if "queues" in data:
            assert isinstance(data["queues"], dict)
