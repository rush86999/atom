"""
Tests for Data Ingestion API Routes

Tests data ingestion endpoints including:
- Usage summary retrieval
- Auto-sync enable/disable
- Manual sync triggering
- Sync status checks
- Available integrations listing
"""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from fastapi import FastAPI
from sqlalchemy.orm import Session

from api.data_ingestion_routes import router, EnableSyncRequest
from core.base_routes import BaseAPIRouter


class TestDataIngestionRoutes:
    """Test suite for data ingestion routes"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_service(self):
        """Mock hybrid ingestion service"""
        service = MagicMock()
        service.get_usage_summary = Mock(return_value={
            "workspace_id": "test-workspace",
            "integrations": [
                {
                    "id": "salesforce",
                    "auto_sync_enabled": True,
                    "total_calls": 150,
                    "last_synced": "2026-02-14T10:00:00Z"
                }
            ],
            "total_synced_records": 5000,
            "auto_sync_enabled_count": 1
        })
        service.enable_auto_sync = Mock()
        service.disable_auto_sync = Mock()
        service.sync_integration_data = AsyncMock(return_value={
            "success": True,
            "records_fetched": 100,
            "records_ingested": 95,
            "entities_extracted": 50,
            "relationships_extracted": 25
        })
        service.usage_stats = {
            "salesforce": MagicMock(
                auto_sync_enabled=True,
                total_calls=150,
                successful_calls=145,
                last_used=None,
                last_synced=None,
                sync_frequency_minutes=60
            )
        }
        service.sync_configs = {
            "salesforce": MagicMock(entity_types=["leads", "opportunities"])
        }
        return service

    @pytest.fixture
    def app(self):
        """Create FastAPI app with router"""
        app = FastAPI()
        app.include_router(router)
        return app

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    def test_get_usage_summary_success(self, mock_get_service, app, mock_service):
        """Test GET /api/data-ingestion/usage - successful retrieval"""
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/data-ingestion/usage")

        assert response.status_code == 200
        data = response.json()
        assert "workspace_id" in data
        assert "integrations" in data
        assert "total_synced_records" in data
        assert "auto_sync_enabled_count" in data

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    def test_get_usage_summary_internal_error(self, mock_get_service, app):
        """Test GET /api/data-ingestion/usage - internal error handling"""
        mock_get_service.side_effect = Exception("Service unavailable")

        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/data-ingestion/usage")

        assert response.status_code == 500

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    def test_enable_auto_sync_success(self, mock_get_service, app, mock_service):
        """Test POST /api/data-ingestion/enable-sync - successful enable"""
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)

        request_data = {
            "integration_id": "salesforce",
            "entity_types": ["leads", "opportunities"],
            "sync_frequency_minutes": 30,
            "sync_last_n_days": 60
        }

        with patch("api.data_ingestion_routes.require_governance"):
            response = client.post("/api/data-ingestion/enable-sync", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["integration_id"] == "salesforce"
        mock_service.enable_auto_sync.assert_called_once()

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    def test_enable_auto_sync_minimal_config(self, mock_get_service, app, mock_service):
        """Test POST /api/data-ingestion/enable-sync - minimal configuration"""
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)

        request_data = {
            "integration_id": "hubspot"
        }

        with patch("api.data_ingestion_routes.require_governance"):
            response = client.post("/api/data-ingestion/enable-sync", json=request_data)

        assert response.status_code == 200
        mock_service.enable_auto_sync.assert_called_once()

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    def test_enable_auto_sync_service_error(self, mock_get_service, app):
        """Test POST /api/data-ingestion/enable-sync - service error"""
        mock_service = MagicMock()
        mock_service.enable_auto_sync = Mock(side_effect=Exception("Connection failed"))
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)

        request_data = {
            "integration_id": "salesforce"
        }

        with patch("api.data_ingestion_routes.require_governance"):
            response = client.post("/api/data-ingestion/enable-sync", json=request_data)

        assert response.status_code == 500

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    def test_disable_auto_sync_success(self, mock_get_service, app, mock_service):
        """Test POST /api/data-ingestion/disable-sync/{integration_id} - successful disable"""
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)

        with patch("api.data_ingestion_routes.require_governance"):
            response = client.post("/api/data-ingestion/disable-sync/salesforce")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["integration_id"] == "salesforce"
        mock_service.disable_auto_sync.assert_called_once_with("salesforce")

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    def test_disable_auto_sync_service_error(self, mock_get_service, app):
        """Test POST /api/data-ingestion/disable-sync/{integration_id} - service error"""
        mock_service = MagicMock()
        mock_service.disable_auto_sync = Mock(side_effect=Exception("Service unavailable"))
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)

        with patch("api.data_ingestion_routes.require_governance"):
            response = client.post("/api/data-ingestion/disable-sync/hubspot")

        assert response.status_code == 500

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    @pytest.mark.asyncio
    async def test_trigger_sync_success(self, mock_get_service, app, mock_service):
        """Test POST /api/data-ingestion/sync/{integration_id} - successful sync"""
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)

        with patch("api.data_ingestion_routes.require_governance"):
            response = client.post("/api/data-ingestion/sync/salesforce")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["integration_id"] == "salesforce"
        assert data["records_fetched"] == 100
        assert data["records_ingested"] == 95
        assert data["entities_extracted"] == 50
        assert data["relationships_extracted"] == 25

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    @pytest.mark.asyncio
    async def test_trigger_sync_with_force(self, mock_get_service, app):
        """Test POST /api/data-ingestion/sync/{integration_id} - with force flag"""
        mock_service = MagicMock()
        mock_service.sync_integration_data = AsyncMock(return_value={
            "success": True,
            "records_fetched": 200,
            "records_ingested": 190,
            "entities_extracted": 100,
            "relationships_extracted": 50
        })
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)

        with patch("api.data_ingestion_routes.require_governance"):
            response = client.post("/api/data-ingestion/sync/salesforce?force=true")

        assert response.status_code == 200
        mock_service.sync_integration_data.assert_called_once_with("salesforce", force=True)

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    @pytest.mark.asyncio
    async def test_trigger_sync_service_error(self, mock_get_service, app):
        """Test POST /api/data-ingestion/sync/{integration_id} - service error"""
        mock_service = MagicMock()
        mock_service.sync_integration_data = AsyncMock(side_effect=Exception("Sync failed"))
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)

        with patch("api.data_ingestion_routes.require_governance"):
            response = client.post("/api/data-ingestion/sync/hubspot")

        assert response.status_code == 500

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    def test_get_sync_status_found(self, mock_get_service, app, mock_service):
        """Test GET /api/data-ingestion/sync-status/{integration_id} - status found"""
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)

        response = client.get("/api/data-ingestion/sync-status/salesforce")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_id"] == "salesforce"
        assert data["found"] is True
        assert data["auto_sync_enabled"] is True
        assert data["total_calls"] == 150
        assert data["successful_calls"] == 145
        assert data["sync_frequency_minutes"] == 60
        assert data["entity_types"] == ["leads", "opportunities"]

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    def test_get_sync_status_not_found(self, mock_get_service, app):
        """Test GET /api/data-ingestion/sync-status/{integration_id} - not found"""
        mock_service = MagicMock()
        mock_service.usage_stats = {}  # No stats for this integration
        mock_get_service.return_value = mock_service

        from fastapi.testclient import TestClient
        client = TestClient(app)

        response = client.get("/api/data-ingestion/sync-status/unknown")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_id"] == "unknown"
        assert data["found"] is False
        assert "message" in data

    @patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service")
    def test_get_sync_status_service_error(self, mock_get_service, app):
        """Test GET /api/data-ingestion/sync-status/{integration_id} - service error"""
        mock_get_service.side_effect = Exception("Service unavailable")

        from fastapi.testclient import TestClient
        client = TestClient(app)

        response = client.get("/api/data-ingestion/sync-status/salesforce")

        assert response.status_code == 500

    @patch("api.data_ingestion_routes.DEFAULT_SYNC_CONFIGS")
    def test_list_available_integrations_success(self, mock_configs, app):
        """Test GET /api/data-ingestion/available-integrations - successful list"""
        mock_config_1 = MagicMock()
        mock_config_1.entity_types = ["leads", "opportunities"]
        mock_config_1.sync_last_n_days = 30
        mock_config_1.max_records_per_sync = 1000

        mock_config_2 = MagicMock()
        mock_config_2.entity_types = ["contacts", "companies"]
        mock_config_2.sync_last_n_days = 60
        mock_config_2.max_records_per_sync = 500

        mock_configs.items.return_value = [
            ("salesforce", mock_config_1),
            ("hubspot", mock_config_2)
        ]

        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/data-ingestion/available-integrations")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "metadata" in data
        assert data["metadata"]["count"] == 2
        integrations = data["data"]
        assert len(integrations) == 2
        assert integrations[0]["id"] in ["salesforce", "hubspot"]
        assert "entity_types" in integrations[0]
        assert "default_sync_days" in integrations[0]
        assert "max_records" in integrations[0]

    @patch("api.data_ingestion_routes.DEFAULT_SYNC_CONFIGS")
    def test_list_available_integrations_empty(self, mock_configs, app):
        """Test GET /api/data-ingestion/available-integrations - empty list"""
        mock_configs.items.return_value = []

        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/data-ingestion/available-integrations")

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["count"] == 0
        assert data["data"] == []


class TestEnableSyncRequest:
    """Test EnableSyncRequest validation"""

    def test_valid_request_with_all_fields(self):
        """Test EnableSyncRequest with all fields"""
        request = EnableSyncRequest(
            integration_id="salesforce",
            entity_types=["leads", "opportunities"],
            sync_frequency_minutes=30,
            sync_last_n_days=60
        )
        assert request.integration_id == "salesforce"
        assert request.entity_types == ["leads", "opportunities"]
        assert request.sync_frequency_minutes == 30
        assert request.sync_last_n_days == 60

    def test_valid_request_minimal_fields(self):
        """Test EnableSyncRequest with minimal fields"""
        request = EnableSyncRequest(integration_id="hubspot")
        assert request.integration_id == "hubspot"
        assert request.entity_types is None
        assert request.sync_frequency_minutes == 60  # Default
        assert request.sync_last_n_days == 30  # Default

    def test_request_default_values(self):
        """Test EnableSyncRequest default values"""
        request = EnableSyncRequest(integration_id="test")
        assert request.sync_frequency_minutes == 60
        assert request.sync_last_n_days == 30
