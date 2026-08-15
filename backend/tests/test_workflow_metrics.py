"""
Tests for Workflow Analytics Metrics

NOTE (Session 2026-08-15, wave 120): the old `/api/analytics/workflows/{id}/metrics`
endpoint was removed; the workflow metrics surface is now
`GET /api/analytics/dashboard/workflow/{workflow_id}/performance` (auth-gated,
`core/workflow_analytics_engine.py`), which computes from the `workflow_events`
table in `analytics.db` — NOT from `agent_executions`. Rewritten against the
current contract: seeded `workflow_events` rows + authenticated client.
"""

import pytest
import sqlite3
import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from core.auth import create_access_token, get_password_hash
from core.database import SessionLocal
from core.models import User, UserStatus
from main_api_app import app

ANALYTICS_DB = "analytics.db"
EVENT_ID_PREFIX = "wfmetrics-"


def _seed_event(workflow_id: str, execution_id: str, event_type: str, minutes_ago: int, **kw):
    """Insert one workflow_events row (ISO timestamps; string compare in the engine)."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO workflow_events
                (event_id, workflow_id, execution_id, user_id, event_type, timestamp,
                 duration_ms, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{EVENT_ID_PREFIX}{uuid.uuid4().hex}",
                workflow_id,
                execution_id,
                "wfmetrics-test-user",
                event_type,
                (datetime.now() - timedelta(minutes=minutes_ago)).isoformat(),
                kw.get("duration_ms"),
                kw.get("status"),
                kw.get("error_message"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _cleanup_events():
    """Remove all seeded rows (teardown — keep analytics.db free of test data)."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM workflow_events WHERE event_id LIKE ?", (f"{EVENT_ID_PREFIX}%",))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    _cleanup_events()


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create a real user + JWT so the auth-gated analytics endpoint responds."""
    db = SessionLocal()
    try:
        user = User(
            email=f"wfmetrics-{uuid.uuid4().hex[:10]}@example.com",
            hashed_password=get_password_hash("password123"),
            first_name="Metrics",
            last_name="Test",
            role="member",
            status=UserStatus.ACTIVE.value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(data={"sub": user.id})
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


@pytest.fixture
def sample_workflow_id():
    """Unique workflow id per test (the engine caches metrics per workflow+window)."""
    return f"wfmetrics-wf-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def sample_executions(sample_workflow_id):
    """Seed 5 completed + 1 failed + 1 started-only executions in workflow_events."""
    for i in range(5):
        exec_id = f"exec-success-{i}"
        _seed_event(sample_workflow_id, exec_id, "workflow_started", minutes_ago=120 - i)
        _seed_event(
            sample_workflow_id, exec_id, "workflow_completed",
            minutes_ago=115 - i, duration_ms=300000, status="completed",
        )
    _seed_event(sample_workflow_id, "exec-failed-1", "workflow_started", minutes_ago=60)
    _seed_event(
        sample_workflow_id, "exec-failed-1", "workflow_completed",
        minutes_ago=58, duration_ms=120000, status="failed", error_message="boom",
    )
    # Started but never completed (in-flight at query time)
    _seed_event(sample_workflow_id, "exec-inflight-1", "workflow_started", minutes_ago=30)
    return sample_workflow_id


class TestWorkflowMetrics:
    """Test workflow metrics endpoint returns real data"""

    def test_workflow_metrics_success_response(self, client, auth_headers, sample_executions):
        """Test endpoint returns success response"""
        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_executions}/performance?time_window=24h",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "success" in data
        assert data["success"] is True
        assert "data" in data
        assert "metrics" in data["data"]

    def test_workflow_metrics_contains_summary(self, client, auth_headers, sample_executions):
        """Test metrics contain summary information"""
        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_executions}/performance?time_window=24h",
            headers=auth_headers,
        )
        data = response.json()

        metrics = data["data"]["metrics"]

        # Verify summary section
        for key in [
            "total_executions",
            "successful_executions",
            "failed_executions",
            "success_rate",
            "average_duration_ms",
            "median_duration_ms",
            "p95_duration_ms",
            "p99_duration_ms",
            "error_rate",
        ]:
            assert key in metrics

    def test_workflow_metrics_calculates_correct_counts(self, client, auth_headers, sample_executions):
        """Test metrics calculate correct execution counts"""
        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_executions}/performance?time_window=24h",
            headers=auth_headers,
        )
        data = response.json()

        metrics = data["data"]["metrics"]

        # We created 7 started, 5 completed-ok, 1 completed-failed
        assert metrics["total_executions"] == 7
        assert metrics["successful_executions"] == 5
        assert metrics["failed_executions"] == 1

    def test_workflow_metrics_calculates_success_rate(self, client, auth_headers, sample_executions):
        """Test metrics calculate correct success rate (percentage)"""
        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_executions}/performance?time_window=24h",
            headers=auth_headers,
        )
        data = response.json()

        metrics = data["data"]["metrics"]

        # Success rate = 5/7 as a percentage
        expected_rate = round(5 / 7 * 100, 2)
        assert abs(metrics["success_rate"] - expected_rate) < 0.01

    def test_workflow_metrics_contains_performance(self, client, auth_headers, sample_executions):
        """Test metrics contain duration statistics"""
        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_executions}/performance?time_window=24h",
            headers=auth_headers,
        )
        data = response.json()

        metrics = data["data"]["metrics"]

        # Average duration of completed events: (5 * 300000 + 120000) / 6
        expected_avg = (5 * 300000 + 120000) / 6
        assert abs(metrics["average_duration_ms"] - expected_avg) < 1.0
        assert metrics["median_duration_ms"] > 0

    def test_workflow_metrics_time_window_filter(self, client, auth_headers, sample_executions):
        """Test time window parameter filters correctly"""
        # 4 of the 7 started events are older than 1h (120/119/118/117/116... min)
        # -> the 1h window should exclude them.
        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_executions}/performance?time_window=1h",
            headers=auth_headers,
        )
        data = response.json()

        metrics = data["data"]["metrics"]

        assert metrics["total_executions"] < 7

    def test_workflow_metrics_identifies_workflow(self, client, auth_headers, sample_executions):
        """Test metrics include the workflow identity"""
        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_executions}/performance?time_window=24h",
            headers=auth_headers,
        )
        data = response.json()

        assert data["data"]["workflow_id"] == sample_executions
        assert data["data"]["workflow_name"] == sample_executions

    def test_workflow_metrics_error_breakdown(self, client, auth_headers, sample_executions):
        """Test metrics include the common-errors breakdown"""
        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_executions}/performance?time_window=24h",
            headers=auth_headers,
        )
        data = response.json()

        common_errors = data["data"]["common_errors"]
        assert isinstance(common_errors, list)
        assert any(e.get("error") == "boom" for e in common_errors)

    def test_workflow_metrics_nonexistent_workflow(self, client, auth_headers):
        """Test metrics for non-existent workflow -> 200 with zeroed metrics
        (the engine always returns a populated PerformanceMetrics object)."""
        workflow_id = f"nonexistent-{uuid.uuid4().hex[:8]}"

        response = client.get(
            f"/api/analytics/dashboard/workflow/{workflow_id}/performance?time_window=24h",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        metrics = data["data"]["metrics"]
        assert metrics["total_executions"] == 0
        assert metrics["successful_executions"] == 0
        assert metrics["success_rate"] == 0.0

    def test_workflow_metrics_different_time_windows(self, client, auth_headers, sample_executions):
        """Test different time window options are accepted"""
        for window in ["1h", "24h", "7d", "30d"]:
            response = client.get(
                f"/api/analytics/dashboard/workflow/{sample_executions}/performance?time_window={window}",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["metrics"]["total_executions"] > 0

    def test_workflow_metrics_performance_aggregation(self, client, auth_headers, sample_executions):
        """Test duration aggregation is consistent"""
        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_executions}/performance?time_window=24h",
            headers=auth_headers,
        )
        data = response.json()

        metrics = data["data"]["metrics"]
        avg = metrics["average_duration_ms"]
        median = metrics["median_duration_ms"]

        # Both aggregate measures of the same completed durations must be
        # within the seeded range [120000, 300000].
        assert 120000 <= avg <= 300000
        assert 120000 <= median <= 300000


class TestWorkflowMetricsEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_empty_workflow_metrics(self, client, auth_headers):
        """Test metrics when workflow has no executions -> 200 with zeroed metrics"""
        workflow_id = f"empty-{uuid.uuid4().hex[:8]}"

        response = client.get(
            f"/api/analytics/dashboard/workflow/{workflow_id}/performance?time_window=24h",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        metrics = data["data"]["metrics"]
        assert metrics["total_executions"] == 0
        assert metrics["success_rate"] == 0.0
        assert metrics["average_duration_ms"] == 0

    def test_invalid_time_window(self, client, auth_headers, sample_workflow_id):
        """Test with invalid time window -> defaults to 24h, still 200"""
        _seed_event(sample_workflow_id, "exec-1", "workflow_started", minutes_ago=5)
        _seed_event(
            sample_workflow_id, "exec-1", "workflow_completed",
            minutes_ago=4, duration_ms=1000, status="completed",
        )

        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_workflow_id}/performance?time_window=invalid",
            headers=auth_headers,
        )

        assert response.status_code == 200

    def test_workflow_metrics_requires_auth(self, client, sample_workflow_id):
        """Test metrics endpoint is auth-gated"""
        _seed_event(sample_workflow_id, "exec-1", "workflow_started", minutes_ago=5)

        response = client.get(
            f"/api/analytics/dashboard/workflow/{sample_workflow_id}/performance"
        )

        assert response.status_code in [401, 403]

    def test_workflow_id_with_special_characters(self, client, auth_headers):
        """Test workflow ID with special characters"""
        workflow_id = f"workflow-with-special_chars.{uuid.uuid4().hex[:6]}"

        response = client.get(
            f"/api/analytics/dashboard/workflow/{workflow_id}/performance",
            headers=auth_headers,
        )

        # Should handle without error
        assert response.status_code in [200, 404]
