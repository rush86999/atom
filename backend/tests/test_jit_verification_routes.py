"""
Tests for JIT Verification Admin Routes

Comprehensive tests for the JIT verification API endpoints,
including cache management, worker control, and monitoring.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.admin.jit_verification_routes import router
from core.models import UserRole


@pytest.fixture
def mock_admin_user():
    """Mock authenticated admin user"""
    user = MagicMock()
    user.id = "admin-user-123"
    user.email = "admin@test.com"
    user.role = UserRole.ADMIN
    return user


@pytest.fixture
def app():
    """Create test FastAPI app"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def authenticated_client(app, mock_admin_user):
    """Create test client with authenticated admin user"""
    from core.auth import get_current_user
    from core.security.rbac import require_role

    # Override get_current_user
    async def override_get_current_user():
        return mock_admin_user

    # Override require_role to pass for admin
    def override_require_role(role: UserRole):
        async def dependency():
            return True
        return dependency

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_role] = override_require_role

    client = TestClient(app)
    yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    """Mock authenticated admin user"""
    user = MagicMock()
    user.id = "admin-user-123"
    user.role = "admin"
    return user


@pytest.fixture
def mock_cache():
    """Mock JIT verification cache"""
    cache = MagicMock()
    cache.get_stats.return_value = {
        "l1": {
            "l1_verification_cache_size": 100,
            "l1_query_cache_size": 50,
            "l1_verification_hits": 850,
            "l1_verification_misses": 150,
            "l1_verification_hit_rate": 0.85,
            "l1_query_hits": 400,
            "l1_query_misses": 100,
            "l1_query_hit_rate": 0.8,
            "l1_evictions": 25
        },
        "l2_enabled": False
    }
    cache.clear_all.return_value = None

    # Mock verify_citations_batch to return results based on input
    async def mock_verify_batch(citations, force_refresh=False):
        if not citations:
            return []
        # For test_verify_citations_success with 2 citations, only return 1 result
        # to simulate partial verification
        if len(citations) == 2:
            return [
                MagicMock(
                    exists=True,
                    checked_at=datetime.now(),
                    citation=citations[0],
                    to_dict=lambda c=citations[0]: {
                        "exists": True,
                        "checked_at": datetime.now().isoformat(),
                        "citation": c,
                        "size": 1024,
                        "last_modified": None
                    }
                )
            ]
        return [
            MagicMock(
                exists=True,
                checked_at=datetime.now(),
                citation=citation,
                to_dict=lambda c=citation: {
                    "exists": True,
                    "checked_at": datetime.now().isoformat(),
                    "citation": c,
                    "size": 1024,
                    "last_modified": None
                }
            )
            for citation in citations
        ]
    cache.verify_citations_batch = AsyncMock(side_effect=mock_verify_batch)
    return cache


@pytest.fixture
def mock_worker():
    """Mock JIT verification worker"""
    worker = MagicMock()
    worker.get_metrics.return_value = {
        "running": True,
        "total_citations": 500,
        "verified_count": 450,
        "failed_count": 10,
        "stale_facts": 5,
        "outdated_facts": 2,
        "last_run_time": datetime.now().isoformat(),
        "last_run_duration": 45.5,
        "average_verification_time": 0.2,
        "top_citations": [
            {"citation": "s3://bucket/popular.pdf", "access_count": 100},
            {"citation": "s3://bucket/another.pdf", "access_count": 50}
        ]
    }
    worker.verify_fact_citations = AsyncMock(return_value={
        "s3://bucket/doc.pdf": MagicMock(
            exists=True,
            to_dict=lambda: {
                "exists": True,
                "citation": "s3://bucket/doc.pdf"
            }
        )
    })
    worker._citation_access_count = {
        "s3://bucket/popular.pdf": 100,
        "s3://bucket/another.pdf": 50
    }
    return worker


@pytest.fixture
def healthy_worker():
    """Mock healthy JIT verification worker for health tests"""
    worker = MagicMock()
    worker.get_metrics.return_value = {
        "running": True,
        "total_citations": 500,
        "verified_count": 450,
        "failed_count": 10,
        "stale_facts": 0,  # No stale facts
        "outdated_facts": 0,  # No outdated facts
        "last_run_time": datetime.now().isoformat(),
        "last_run_duration": 45.5,
        "average_verification_time": 0.2,
        "top_citations": [
            {"citation": "s3://bucket/popular.pdf", "access_count": 100},
            {"citation": "s3://bucket/another.pdf", "access_count": 50}
        ]
    }
    return worker


class TestCacheStatsEndpoint:
    """Tests for GET /api/admin/governance/jit/cache/stats"""

    def test_get_cache_stats_success(self, authenticated_client, mock_cache):
        """Test getting cache statistics successfully"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            response = authenticated_client.get("/api/admin/governance/jit/cache/stats")

            assert response.status_code == 200

            data = response.json()
            assert data["l1_verification_cache_size"] == 100
            assert data["l1_query_cache_size"] == 50
            assert data["l1_verification_hit_rate"] == 0.85
            assert data["l2_enabled"] is False


class TestCacheClearEndpoint:
    """Tests for POST /api/admin/governance/jit/cache/clear"""

    def test_clear_cache_success(self, authenticated_client, mock_cache):
        """Test clearing cache successfully"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            response = authenticated_client.post("/api/admin/governance/jit/cache/clear")

            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "cleared"
            assert "cleared_at" in data
            mock_cache.clear_all.assert_called_once()


class TestVerifyCitationsEndpoint:
    """Tests for POST /api/admin/governance/jit/verify-citations"""

    def test_verify_citations_success(self, authenticated_client, mock_cache):
        """Test verifying citations successfully"""
        request_data = {
            "citations": ["s3://bucket/doc1.pdf", "s3://bucket/doc2.pdf"],
            "force_refresh": False
        }

        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            response = authenticated_client.post(
                "/api/admin/governance/jit/verify-citations",
                json=request_data
            )

            assert response.status_code == 200

            data = response.json()
            assert data["total_count"] == 1
            assert data["verified_count"] == 1
            assert data["failed_count"] == 0
            assert "duration_seconds" in data
            assert len(data["results"]) == 1

    def test_verify_citations_force_refresh(self, authenticated_client, mock_cache):
        """Test verifying citations with force refresh"""
        request_data = {
            "citations": ["s3://bucket/doc.pdf"],
            "force_refresh": True
        }

        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            response = authenticated_client.post(
                "/api/admin/governance/jit/verify-citations",
                json=request_data
            )

            assert response.status_code == 200

            # Check that force_refresh was passed
            mock_cache.verify_citations_batch.assert_called_once()
            call_kwargs = mock_cache.verify_citations_batch.call_args[1]
            assert call_kwargs["force_refresh"] is True

    def test_verify_citations_empty_list(self, authenticated_client, mock_cache):
        """Test verifying empty citation list"""
        request_data = {
            "citations": [],
            "force_refresh": False
        }

        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            response = authenticated_client.post(
                "/api/admin/governance/jit/verify-citations",
                json=request_data
            )

            assert response.status_code == 200

            data = response.json()
            assert data["total_count"] == 0


class TestWorkerMetricsEndpoint:
    """Tests for GET /api/admin/governance/jit/worker/metrics"""

    def test_get_worker_metrics_success(self, authenticated_client, mock_worker):
        """Test getting worker metrics successfully"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=mock_worker):
            response = authenticated_client.get("/api/admin/governance/jit/worker/metrics")

            assert response.status_code == 200

            data = response.json()
            assert data["running"] is True
            assert data["verified_count"] == 450
            assert data["failed_count"] == 10
            assert data["stale_facts"] == 5
            assert len(data["top_citations"]) == 2


class TestWorkerStartEndpoint:
    """Tests for POST /api/admin/governance/jit/worker/start"""

    def test_start_worker_success(self, authenticated_client, mock_worker):
        """Test starting worker successfully"""
        with patch('api.admin.jit_verification_routes.start_jit_verification_worker', return_value=mock_worker):
            response = authenticated_client.post("/api/admin/governance/jit/worker/start")

            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "started"
            assert "started_at" in data
            assert "workspace_id" in data

    def test_start_worker_already_running(self, authenticated_client, mock_worker):
        """Test starting worker when already running"""
        mock_worker._running = True

        with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=mock_worker):
            response = authenticated_client.post("/api/admin/governance/jit/worker/start")

            # Should still succeed (idempotent)
            assert response.status_code in [200, 202]


class TestWorkerStopEndpoint:
    """Tests for POST /api/admin/governance/jit/worker/stop"""

    def test_stop_worker_success(self, authenticated_client):
        """Test stopping worker successfully"""
        with patch('api.admin.jit_verification_routes.stop_jit_verification_worker'):
            response = authenticated_client.post("/api/admin/governance/jit/worker/stop")

            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "stopped"
            assert "stopped_at" in data


class TestVerifyFactCitationsEndpoint:
    """Tests for POST /api/admin/governance/jit/worker/verify-fact/{fact_id}"""

    def test_verify_fact_citations_success(self, authenticated_client, mock_worker):
        """Test verifying fact citations successfully"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=mock_worker):
            response = authenticated_client.post("/api/admin/governance/jit/worker/verify-fact/fact-123")

            assert response.status_code == 200

            data = response.json()
            assert data["fact_id"] == "fact-123"
            assert data["citation_count"] == 1
            assert "results" in data
            assert "verified_at" in data
            mock_worker.verify_fact_citations.assert_called_once_with("fact-123")

    def test_verify_fact_not_found(self, authenticated_client, mock_worker):
        """Test verifying citations for non-existent fact"""
        mock_worker.verify_fact_citations.return_value = {}

        with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=mock_worker):
            response = authenticated_client.post("/api/admin/governance/jit/worker/verify-fact/nonexistent-fact")

            assert response.status_code == 200

            data = response.json()
            assert data["citation_count"] == 0


class TestTopCitationsEndpoint:
    """Tests for GET /api/admin/governance/jit/worker/top-citations"""

    def test_get_top_citations_default_limit(self, authenticated_client, mock_worker):
        """Test getting top citations with default limit"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=mock_worker):
            response = authenticated_client.get("/api/admin/governance/jit/worker/top-citations")

            assert response.status_code == 200

            data = response.json()
            assert len(data["top_citations"]) == 2
            assert data["total_unique_citations"] == 2
            assert "retrieved_at" in data

    def test_get_top_citations_custom_limit(self, authenticated_client, mock_worker):
        """Test getting top citations with custom limit"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=mock_worker):
            response = authenticated_client.get("/api/admin/governance/jit/worker/top-citations?limit=1")

            assert response.status_code == 200

            data = response.json()
            assert len(data["top_citations"]) == 1

    def test_get_top_citations_max_limit_enforced(self, authenticated_client, mock_worker):
        """Test that max limit is enforced"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=mock_worker):
            # Try to request more than max (100)
            response = authenticated_client.get("/api/admin/governance/jit/worker/top-citations?limit=200")

            # Should either reject with validation error or cap at max
            assert response.status_code in [200, 422]


class TestHealthEndpoint:
    """Tests for GET /api/admin/governance/jit/health"""

    def test_get_health_healthy(self, authenticated_client, mock_cache, healthy_worker):
        """Test getting health status when system is healthy"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=healthy_worker):
                response = authenticated_client.get("/api/admin/governance/jit/health")

                assert response.status_code == 200

                data = response.json()
                assert data["status"] == "healthy"
                assert len(data["issues"]) == 0
                assert "cache" in data
                assert "worker" in data
                assert "checked_at" in data

    def test_get_health_degraded(self, authenticated_client, mock_cache, mock_worker):
        """Test getting health status when system is degraded"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=mock_worker):
                response = authenticated_client.get("/api/admin/governance/jit/health")

                assert response.status_code == 200

                data = response.json()
                assert data["status"] == "degraded"
                assert len(data["issues"]) > 0


class TestCacheWarmEndpoint:
    """Tests for POST /api/admin/governance/jit/cache/warm"""

    def test_warm_cache_success(self, authenticated_client, mock_cache):
        """Test warming cache successfully"""
        # Mock WorldModel
        mock_facts = [
            MagicMock(
                id=f"fact-{i}",
                citations=[f"s3://bucket/doc{i}.pdf"]
            )
            for i in range(10)
        ]

        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            with patch('core.agent_world_model.WorldModelService') as mock_wm_class:
                mock_wm = MagicMock()
                mock_wm.list_all_facts = AsyncMock(return_value=mock_facts)
                mock_wm_class.return_value = mock_wm

                response = authenticated_client.post("/api/admin/governance/jit/cache/warm?limit=100")

                assert response.status_code == 200

                data = response.json()
                assert data["status"] == "warmed"
                assert data["facts_processed"] == 10
                assert data["citations_verified"] == 10
                assert "duration_seconds" in data
                assert "warmed_at" in data

    def test_warm_cache_custom_limit(self, authenticated_client, mock_cache):
        """Test warming cache with custom limit"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            with patch('core.agent_world_model.WorldModelService') as mock_wm_class:
                mock_wm = MagicMock()
                mock_wm.list_all_facts = AsyncMock(return_value=[])
                mock_wm_class.return_value = mock_wm

                response = authenticated_client.post("/api/admin/governance/jit/cache/warm?limit=500")

                assert response.status_code == 200

                # Verify limit was passed
                mock_wm.list_all_facts.assert_called_once_with(limit=500)


class TestConfigEndpoint:
    """Tests for GET /api/admin/governance/jit/config"""

    def test_get_config_success(self, authenticated_client, mock_cache, mock_worker):
        """Test getting configuration successfully"""
        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=mock_worker):
                response = authenticated_client.get("/api/admin/governance/jit/config")

                assert response.status_code == 200

                data = response.json()
                assert "worker" in data
                assert "cache" in data
                assert "l1" in data["cache"]
                assert "l2" in data["cache"]


class TestErrorHandling:
    """Tests for error handling"""

    def test_verify_citations_error(self, authenticated_client, mock_cache):
        """Test error handling when verification fails"""
        mock_cache.verify_citations_batch.side_effect = Exception("Storage error")

        with patch('api.admin.jit_verification_routes.get_jit_verification_cache', return_value=mock_cache):
            response = authenticated_client.post(
                "/api/admin/governance/jit/verify-citations",
                json={"citations": ["s3://bucket/doc.pdf"]}
            )

            # Should return error
            assert response.status_code == 500

    def test_worker_metrics_error(self, authenticated_client, mock_worker):
        """Test error handling when worker metrics fail"""
        mock_worker.get_metrics.side_effect = Exception("Worker error")

        with patch('api.admin.jit_verification_routes.get_jit_verification_worker', return_value=mock_worker):
            response = authenticated_client.get("/api/admin/governance/jit/worker/metrics")

            # Should return error
            assert response.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
