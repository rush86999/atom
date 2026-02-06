"""
Unit Tests for Task Queue Manager

Tests the RQ-based task queue functionality including:
- Queue initialization
- Job enqueueing
- Scheduled jobs
- Job status tracking
- Job cancellation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from core.task_queue import TaskQueueManager, get_task_queue


class TestTaskQueueManager:
    """Test cases for TaskQueueManager"""

    def test_init_without_rq(self):
        """Test initialization when RQ is not available"""
        with patch('core.task_queue.RQ_AVAILABLE', False):
            manager = TaskQueueManager()

            assert manager.enabled is False
            assert manager._redis_conn is None
            assert manager._queues == {}

    def test_init_with_redis_unavailable(self):
        """Test initialization when Redis is unavailable"""
        with patch('core.task_queue.RQ_AVAILABLE', True):
            with patch('core.task_queue.redis') as mock_redis:
                mock_redis.Redis.side_effect = Exception("Connection refused")

                manager = TaskQueueManager()

                assert manager.enabled is False

    @pytest.mark.skipif(
        True,  # Skip if Redis not available in test environment
        reason="Requires Redis server"
    )
    def test_init_success(self):
        """Test successful initialization with Redis"""
        manager = TaskQueueManager()

        assert manager.enabled is True
        assert "social_media" in manager._queues
        assert "workflows" in manager._queues
        assert "default" in manager._queues

    def test_get_queue(self):
        """Test getting a specific queue"""
        manager = TaskQueueManager()

        # Test with disabled queue
        if not manager.enabled:
            queue = manager.get_queue("social_media")
            assert queue is None
            return

        # Test with enabled queue
        queue = manager.get_queue("social_media")
        assert queue is not None
        assert queue.name == "social_media"

    def test_enqueue_job_disabled(self):
        """Test enqueuing a job when queue is disabled"""
        manager = TaskQueueManager()

        if not manager.enabled:
            job_id = manager.enqueue_job(lambda: "test")
            assert job_id is None
            return

        # If enabled, this test should be skipped
        pytest.skip("Queue is enabled in this environment")

    @pytest.mark.skipif(
        True,  # Requires Redis and RQ
        reason="Requires Redis and RQ worker"
    )
    def test_enqueue_job_success(self):
        """Test successful job enqueuing"""
        manager = TaskQueueManager()

        if not manager.enabled:
            pytest.skip("Queue not available")

        def test_func():
            return "test_result"

        job_id = manager.enqueue_job(test_func, queue_name="default")

        assert job_id is not None
        assert isinstance(job_id, str)

    @pytest.mark.skipif(
        True,  # Requires Redis and RQ
        reason="Requires Redis and RQ worker"
    )
    def test_enqueue_scheduled_job(self):
        """Test enqueuing a scheduled job"""
        manager = TaskQueueManager()

        if not manager.enabled:
            pytest.skip("Queue not available")

        def test_func():
            return "scheduled_result"

        scheduled_time = datetime.utcnow() + timedelta(minutes=5)

        job_id = manager.enqueue_scheduled_job(
            test_func,
            scheduled_time=scheduled_time,
            queue_name="social_media"
        )

        assert job_id is not None

    def test_get_job_status_disabled(self):
        """Test getting job status when queue is disabled"""
        manager = TaskQueueManager()

        if not manager.enabled:
            status = manager.get_job_status("test-job-id")
            assert "error" in status
            assert status["error"] == "Task queue is disabled"
            return

        pytest.skip("Queue is enabled in this environment")

    def test_cancel_job_disabled(self):
        """Test canceling a job when queue is disabled"""
        manager = TaskQueueManager()

        if not manager.enabled:
            result = manager.cancel_job("test-job-id")
            assert result is False
            return

        pytest.skip("Queue is enabled in this environment")

    def test_get_queue_info_disabled(self):
        """Test getting queue info when queue is disabled"""
        manager = TaskQueueManager()

        if not manager.enabled:
            info = manager.get_queue_info("default")
            assert "error" in info
            assert info["error"] == "Task queue is disabled"
            return

        pytest.skip("Queue is enabled in this environment")

    def test_get_all_queues_info_disabled(self):
        """Test getting all queues info when queue is disabled"""
        manager = TaskQueueManager()

        if not manager.enabled:
            info = manager.get_all_queues_info()
            assert "error" in info
            assert info["error"] == "Task queue is disabled"
            return

        pytest.skip("Queue is enabled in this environment")


class TestGlobalTaskQueue:
    """Test cases for global task queue instance"""

    def test_get_task_queue_singleton(self):
        """Test that get_task_queue returns singleton instance"""
        queue1 = get_task_queue()
        queue2 = get_task_queue()

        assert queue1 is queue2


class TestConvenienceFunctions:
    """Test cases for convenience functions"""

    @patch('core.task_queue.get_task_queue')
    def test_enqueue_scheduled_post(self, mock_get_queue):
        """Test enqueue_scheduled_post convenience function"""
        # Setup mock
        mock_queue = Mock()
        mock_queue.enqueue_scheduled_job.return_value = "test-job-id"
        mock_get_queue.return_value = mock_queue

        # Import after mocking
        from core.task_queue import enqueue_scheduled_post

        # Test
        from datetime import datetime
        scheduled_time = datetime.utcnow() + timedelta(hours=1)

        job_id = enqueue_scheduled_post(
            post_id="test-post",
            platforms=["twitter", "linkedin"],
            text="Test post",
            scheduled_for=scheduled_time,
            user_id="user-123"
        )

        assert job_id == "test-job-id"
        mock_queue.enqueue_scheduled_job.assert_called_once()

        # Verify call arguments
        call_args = mock_queue.enqueue_scheduled_job.call_args
        assert call_args[1]['post_id'] == "test-post"
        assert call_args[1]['platforms'] == ["twitter", "linkedin"]
        assert call_args[1]['text'] == "Test post"
        assert call_args[1]['user_id'] == "user-123"

    @patch('core.task_queue.get_task_queue')
    def test_enqueue_scheduled_post_disabled(self, mock_get_queue):
        """Test enqueue_scheduled_post when queue is disabled"""
        # Setup mock to return None (disabled)
        mock_queue = Mock()
        mock_queue.enqueue_scheduled_job.return_value = None
        mock_get_queue.return_value = mock_queue

        from core.task_queue import enqueue_scheduled_post

        from datetime import datetime
        scheduled_time = datetime.utcnow() + timedelta(hours=1)

        job_id = enqueue_scheduled_post(
            post_id="test-post",
            platforms=["twitter"],
            text="Test post",
            scheduled_for=scheduled_time
        )

        assert job_id is None
