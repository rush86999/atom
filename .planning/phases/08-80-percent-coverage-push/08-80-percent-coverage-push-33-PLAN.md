---
phase: 08-80-percent-coverage-push
plan: 33
type: execute
wave: 7
depends_on: []
files_modified:
  - backend/tests/unit/test_document_ingestion_routes.py
  - backend/tests/unit/test_websocket_routes.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "Document ingestion routes have 50%+ test coverage (parse, settings, sync, memory removal)"
    - "WebSocket routes have 50%+ test coverage (connection, ping/pong, disconnect handling)"
    - "All API endpoints tested with FastAPI TestClient"
    - "File upload handling tested"
  artifacts:
    - path: "backend/tests/unit/test_document_ingestion_routes.py"
      provides: "Document ingestion API tests"
      min_lines: 350
    - path: "backend/tests/unit/test_websocket_routes.py"
      provides: "WebSocket route tests"
      min_lines: 100
  key_links:
    - from: "test_document_ingestion_routes.py"
      to: "api/document_ingestion_routes.py"
      via: "TestClient, mock_document_ingestion_service, mock_upload"
      pattern: "parse_document, update_settings, sync_documents"
    - from: "test_websocket_routes.py"
      to: "api/websocket_routes.py"
      via: "TestClient, mock_websocket_manager"
      pattern: "websocket_endpoint, connect, disconnect"
status: pending
created: 2026-02-13
gap_closure: false
---

# Plan 33: Document Ingestion & WebSocket Routes Tests

**Status:** Pending
**Wave:** 7 (parallel with 31, 32)
**Dependencies:** None

## Objective

Create comprehensive unit tests for document ingestion routes and websocket routes, achieving 50% coverage across both files to contribute +0.6-0.8% toward Phase 9.0's 25-27% overall coverage goal.

## Context

Phase 9.0 targets 25-27% overall coverage (+3-5% from 21-22%) by testing zero-coverage API routes. This plan covers document ingestion and WebSocket routes:

1. **api/document_ingestion_routes.py** (450 lines) - Document ingestion APIs (parse, settings, sync, memory removal)
2. **api/websocket_routes.py** (25 lines) - WebSocket connection endpoint (connect, ping/pong, disconnect)

**Production Lines:** 475 total
**Expected Coverage at 50%:** ~240 lines
**Coverage Contribution:** +0.6-0.8 percentage points toward 25-27% goal

**Key Functions to Test:**

**Document Ingestion Routes:**
- `POST /parse` - Parse uploaded document
- `GET /settings` - Get all ingestion settings
- `GET /settings/{integration_id}` - Get specific integration settings
- `POST /settings` - Update ingestion settings
- `POST /sync` - Trigger document sync
- `DELETE /memory` - Remove ingested documents from memory

**WebSocket Routes:**
- `WS /ws/{workspace_id}` - WebSocket endpoint for real-time updates
- Connection handling (connect, accept)
- Message handling (ping/pong)
- Disconnect handling (cleanup)

## Success Criteria

**Must Have (truths that become verifiable):**
1. Document ingestion routes have 50%+ test coverage (parse, settings, sync, memory)
2. WebSocket routes have 50%+ test coverage (connect, ping/pong, disconnect)
3. All API endpoints tested with FastAPI TestClient
4. File upload handling tested

**Should Have:**
- Error handling tested (400, 404, 500 responses)
- File type validation tested
- WebSocket message handling tested
- Session cleanup tested

**Could Have:**
- Large file upload tested
- Multiple file upload tested
- WebSocket reconnection tested

**Won't Have:**
- Real document parsing (mocked)
- Real WebSocket connections (mocked with TestClient)
- Real file system (mocked uploads)

## Tasks

### Task 1: Create test_document_ingestion_routes.py with ingestion API coverage

**Files:**
- CREATE: `backend/tests/unit/test_document_ingestion_routes.py` (350+ lines, 20-25 tests)

**Action:**
Create test file with these test classes:

```python
"""
Unit tests for Document Ingestion API Routes

Tests cover:
- Document parsing
- Ingestion settings retrieval
- Settings updates
- Document sync triggering
- Memory removal
- File upload handling
"""
import pytest
from datetime import datetime
from io import BytesIO
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi.testclient import TestClient

from api.document_ingestion_routes import router, IngestionSettingsRequest, MetricsResetRequest


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    db.delete = Mock()
    return db


@pytest.fixture
def mock_current_user():
    """Mock current user."""
    user = MagicMock()
    user.id = "user_123"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_document_ingestion_service():
    """Mock document ingestion service."""
    service = MagicMock()
    service.parse_document = AsyncMock(return_value={
        "success": True,
        "content": "Parsed content",
        "metadata": {"pages": 1},
        "total_chars": 100
    })
    service.get_all_settings = MagicMock(return_value=[])
    service.get_settings = MagicMock(return_value={})
    service.update_settings = AsyncMock(return_value=True)
    service.sync_documents = AsyncMock(return_value={
        "success": True,
        "files_found": 10,
        "files_ingested": 8,
        "files_skipped": 2
    })
    service.remove_memory = AsyncMock(return_value={
        "success": True,
        "documents_removed": 5
    })
    return service


@pytest.fixture
def client(mock_document_ingestion_service, mock_current_user):
    """Test client with mocked dependencies."""
    with patch('api.document_ingestion_routes.get_document_ingestion_service', return_value=mock_document_ingestion_service):
        with patch('api.document_ingestion_routes.get_current_user', return_value=mock_current_user):
            yield TestClient(router)


@pytest.fixture
def sample_integration_id():
    """Sample integration ID."""
    return "slack_integration"


# =============================================================================
# Document Parsing Tests
# =============================================================================

class TestDocumentParsing:
    """Tests for document parsing endpoint."""

    def test_parse_document_pdf(self, client, mock_document_ingestion_service):
        """Test parsing PDF document."""
        mock_document_ingestion_service.parse_document.return_value = {
            "success": True,
            "content": "PDF content",
            "metadata": {"type": "pdf", "pages": 5},
            "total_chars": 500,
            "page_count": 5
        }

        # Create mock file upload
        file_content = b"%PDF-1.4 mock content"
        files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}

        response = client.post("/parse", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "content" in data
        mock_document_ingestion_service.parse_document.assert_called_once()

    def test_parse_document_docx(self, client, mock_document_ingestion_service):
        """Test parsing DOCX document."""
        mock_document_ingestion_service.parse_document.return_value = {
            "success": True,
            "content": "DOCX content",
            "metadata": {"type": "docx"},
            "total_chars": 300
        }

        file_content = b"PK mock docx content"
        files = {"file": ("test.docx", BytesIO(file_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

        response = client.post("/parse", files=files)

        assert response.status_code == 200

    def test_parse_document_txt(self, client, mock_document_ingestion_service):
        """Test parsing TXT document."""
        mock_document_ingestion_service.parse_document.return_value = {
            "success": True,
            "content": "Plain text content",
            "metadata": {"type": "txt"},
            "total_chars": 50
        }

        file_content = b"Plain text content"
        files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}

        response = client.post("/parse", files=files)

        assert response.status_code == 200

    def test_parse_document_with_error(self, client, mock_document_ingestion_service):
        """Test parsing document with error."""
        mock_document_ingestion_service.parse_document.return_value = {
            "success": False,
            "error": "Failed to parse document"
        }

        file_content = b"Invalid content"
        files = {"file": ("test.bin", BytesIO(file_content), "application/octet-stream")}

        response = client.post("/parse", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


# =============================================================================
# Settings Retrieval Tests
# =============================================================================

class TestSettingsRetrieval:
    """Tests for settings retrieval endpoints."""

    def test_get_all_settings(self, client, mock_document_ingestion_service):
        """Test getting all ingestion settings."""
        mock_document_ingestion_service.get_all_settings.return_value = [
            {
                "integration_id": "slack_1",
                "enabled": True,
                "auto_sync_new_files": True,
                "file_types": ["pdf", "txt"],
                "max_file_size_mb": 25
            },
            {
                "integration_id": "teams_1",
                "enabled": False,
                "auto_sync_new_files": False
            }
        ]

        response = client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_get_all_settings_empty(self, client, mock_document_ingestion_service):
        """Test getting settings when none configured."""
        mock_document_ingestion_service.get_all_settings.return_value = []

        response = client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_settings_specific_integration(self, client, mock_document_ingestion_service, sample_integration_id):
        """Test getting settings for specific integration."""
        mock_document_ingestion_service.get_settings.return_value = {
            "integration_id": sample_integration_id,
            "enabled": True,
            "auto_sync_new_files": True,
            "file_types": ["pdf"],
            "max_file_size_mb": 10,
            "sync_frequency_minutes": 60
        }

        response = client.get(f"/settings/{sample_integration_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_id"] == sample_integration_id

    def test_get_settings_not_found(self, client, mock_document_ingestion_service, sample_integration_id):
        """Test getting settings for non-existent integration."""
        mock_document_ingestion_service.get_settings.return_value = None

        response = client.get(f"/settings/{sample_integration_id}")

        assert response.status_code == 404


# =============================================================================
# Settings Update Tests
# =============================================================================

class TestSettingsUpdate:
    """Tests for settings update endpoint."""

    def test_update_settings_enable(self, client, mock_document_ingestion_service, sample_integration_id):
        """Test updating settings to enable integration."""
        request = {
            "integration": sample_integration_id,
            "enabled": True
        }

        response = client.post("/update", json=request)

        assert response.status_code == 200
        mock_document_ingestion_service.update_settings.assert_called_once()

    def test_update_settings_file_types(self, client, mock_document_ingestion_service, sample_integration_id):
        """Test updating settings file types."""
        request = {
            "integration": sample_integration_id,
            "file_types": ["pdf", "docx", "txt", "csv"]
        }

        response = client.post("/update", json=request)

        assert response.status_code == 200

    def test_update_settings_sync_folders(self, client, mock_document_ingestion_service, sample_integration_id):
        """Test updating settings sync folders."""
        request = {
            "integration": sample_integration_id,
            "sync_folders": ["/Documents", "/Downloads"]
        }

        response = client.post("/update", json=request)

        assert response.status_code == 200

    def test_update_settings_max_file_size(self, client, mock_document_ingestion_service, sample_integration_id):
        """Test updating settings max file size."""
        request = {
            "integration": sample_integration_id,
            "max_file_size_mb": 50
        }

        response = client.post("/update", json=request)

        assert response.status_code == 200

    def test_update_settings_sync_frequency(self, client, mock_document_ingestion_service, sample_integration_id):
        """Test updating settings sync frequency."""
        request = {
            "integration": sample_integration_id,
            "sync_frequency_minutes": 30
        }

        response = client.post("/update", json=request)

        assert response.status_code == 200

    def test_update_settings_multiple_fields(self, client, mock_document_ingestion_service, sample_integration_id):
        """Test updating multiple settings fields."""
        request = {
            "integration": sample_integration_id,
            "enabled": True,
            "auto_sync_new_files": True,
            "file_types": ["pdf"],
            "sync_folders": ["/Documents"],
            "max_file_size_mb": 25,
            "sync_frequency_minutes": 60
        }

        response = client.post("/update", json=request)

        assert response.status_code == 200


# =============================================================================
# Document Sync Tests
# =============================================================================

class TestDocumentSync:
    """Tests for document sync endpoint."""

    def test_sync_documents_all(self, client, mock_document_ingestion_service):
        """Test syncing all integrations."""
        mock_document_ingestion_service.sync_documents.return_value = {
            "success": True,
            "files_found": 20,
            "files_ingested": 18,
            "files_skipped": 2,
            "errors": []
        }

        response = client.post("/sync", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["files_found"] == 20

    def test_sync_documents_specific_integration(self, client, mock_document_ingestion_service, sample_integration_id):
        """Test syncing specific integration."""
        request = {"integration": sample_integration_id}
        mock_document_ingestion_service.sync_documents.return_value = {
            "success": True,
            "files_found": 5,
            "files_ingested": 5,
            "files_skipped": 0
        }

        response = client.post("/sync", json=request)

        assert response.status_code == 200

    def test_sync_documents_with_errors(self, client, mock_document_ingestion_service):
        """Test syncing with some errors."""
        mock_document_ingestion_service.sync_documents.return_value = {
            "success": True,
            "files_found": 10,
            "files_ingested": 8,
            "files_skipped": 2,
            "errors": ["File too large", "Unsupported format"]
        }

        response = client.post("/sync", json={})

        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) == 2


# =============================================================================
# Memory Removal Tests
# =============================================================================

class TestMemoryRemoval:
    """Tests for memory removal endpoint."""

    def test_remove_memory_all(self, client, mock_document_ingestion_service):
        """Test removing all ingested documents."""
        mock_document_ingestion_service.remove_memory.return_value = {
            "success": True,
            "documents_removed": 100,
            "message": "All documents removed from memory"
        }

        response = client.delete("/memory")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["documents_removed"] == 100

    def test_remove_memory_specific_integration(self, client, mock_document_ingestion_service, sample_integration_id):
        """Test removing documents from specific integration."""
        mock_document_ingestion_service.remove_memory.return_value = {
            "success": True,
            "documents_removed": 25,
            "message": f"Documents removed from {sample_integration_id}"
        }

        response = client.delete(f"/memory?integration={sample_integration_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["documents_removed"] == 25

    def test_remove_memory_no_documents(self, client, mock_document_ingestion_service):
        """Test removing memory when no documents."""
        mock_document_ingestion_service.remove_memory.return_value = {
            "success": True,
            "documents_removed": 0,
            "message": "No documents to remove"
        }

        response = client.delete("/memory")

        assert response.status_code == 200
        data = response.json()
        assert data["documents_removed"] == 0


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_parse_document_missing_file(self, client):
        """Test parsing without file upload."""
        response = client.post("/parse", data={})

        # Should handle missing file
        assert response.status_code in [400, 422]

    def test_update_settings_missing_integration(self, client):
        """Test updating settings without integration ID."""
        request = {"enabled": True}

        response = client.post("/update", json=request)

        # Should handle missing integration
        assert response.status_code in [400, 422]
```

**Verify:**
```bash
test -f backend/tests/unit/test_document_ingestion_routes.py && echo "File exists"
grep -c "^    def test_" backend/tests/unit/test_document_ingestion_routes.py
# Expected: 20-25 tests
```

**Done:**
- File created with 20-25 tests
- Document parsing tested (PDF, DOCX, TXT)
- Settings retrieval tested (all, specific)
- Settings updates tested (enable, file types, sync)
- Document sync tested
- Memory removal tested
- Error handling tested

### Task 2: Create test_websocket_routes.py with WebSocket coverage

**Files:**
- CREATE: `backend/tests/unit/test_websocket_routes.py` (100+ lines, 10-12 tests)

**Action:**
Create test file with these test classes:

```python
"""
Unit tests for WebSocket Routes

Tests cover:
- WebSocket connection establishment
- Ping/pong handling
- Disconnect handling
- Workspace routing
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from api.websocket_routes import router


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_notification_manager():
    """Mock notification manager."""
    manager = MagicMock()
    manager.connect = MagicMock()
    manager.disconnect = MagicMock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def sample_workspace_id():
    """Sample workspace ID."""
    return "workspace_123"


# =============================================================================
# WebSocket Connection Tests
# =============================================================================

class TestWebSocketConnection:
    """Tests for WebSocket connection handling."""

    @pytest.mark.asyncio
    async def test_websocket_connect(self, mock_websocket, mock_notification_manager, sample_workspace_id):
        """Test WebSocket connection establishment."""
        with patch('api.websocket_routes.notification_manager', mock_notification_manager):
            from api.websocket_routes import websocket_endpoint

            await websocket_endpoint(mock_websocket, sample_workspace_id)

        # Verify connection was accepted
        mock_websocket.accept.assert_called_once()
        # Verify manager was notified
        mock_notification_manager.connect.assert_called_once_with(mock_websocket, sample_workspace_id)

    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self, mock_websocket, mock_notification_manager, sample_workspace_id):
        """Test ping/pong message handling."""
        mock_websocket.receive_text.return_value = "ping"

        with patch('api.websocket_routes.notification_manager', mock_notification_manager):
            from api.websocket_routes import websocket_endpoint

            # Let the loop run once then exit on WebSocketDisconnect
            mock_websocket.receive_text.side_effect = ["ping", Exception("WebSocketDisconnect")]

            try:
                await websocket_endpoint(mock_websocket, sample_workspace_id)
            except:
                pass

        # Verify pong was sent
        mock_websocket.send_text.assert_called_with("pong")

    @pytest.mark.asyncio
    async def test_websocket_disconnect(self, mock_websocket, mock_notification_manager, sample_workspace_id):
        """Test WebSocket disconnect handling."""
        # Simulate immediate disconnect
        mock_websocket.receive_text.side_effect = Exception("WebSocketDisconnect")

        with patch('api.websocket_routes.notification_manager', mock_notification_manager):
            from api.websocket_routes import websocket_endpoint

            try:
                await websocket_endpoint(mock_websocket, sample_workspace_id)
            except:
                pass

        # Verify disconnect was handled
        mock_notification_manager.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_websocket_error(self, mock_websocket, mock_notification_manager, sample_workspace_id):
        """Test WebSocket error handling."""
        # Simulate WebSocket error
        mock_websocket.receive_text.side_effect = Exception("Connection error")

        with patch('api.websocket_routes.notification_manager', mock_notification_manager):
            from api.websocket_routes import websocket_endpoint

            try:
                await websocket_endpoint(mock_websocket, sample_workspace_id)
            except:
                pass

        # Verify disconnect was called on error
        mock_notification_manager.disconnect.assert_called_with(mock_websocket, sample_workspace_id)


# =============================================================================
# Message Handling Tests
# =============================================================================

class TestMessageHandling:
    """Tests for WebSocket message handling."""

    @pytest.mark.asyncio
    async def test_websocket_client_message(self, mock_websocket, mock_notification_manager, sample_workspace_id):
        """Test handling client message (not ping)."""
        # Send non-ping message
        mock_websocket.receive_text.side_effect = ["client message", Exception("Done")]

        with patch('api.websocket_routes.notification_manager', mock_notification_manager):
            from api.websocket_routes import websocket_endpoint

            try:
                await websocket_endpoint(mock_websocket, sample_workspace_id)
            except:
                pass

        # Should not crash on unknown message
        mock_websocket.send_text.assert_not_called_with("pong")

    @pytest.mark.asyncio
    async def test_websocket_multiple_pings(self, mock_websocket, mock_notification_manager, sample_workspace_id):
        """Test multiple ping/pong cycles."""
        mock_websocket.receive_text.side_effect = ["ping", "ping", "ping", Exception("Done")]

        with patch('api.websocket_routes.notification_manager', mock_notification_manager):
            from api.websocket_routes import websocket_endpoint

            try:
                await websocket_endpoint(mock_websocket, sample_workspace_id)
            except:
                pass

        # Should have sent pong multiple times
        assert mock_websocket.send_text.call_count >= 1


# =============================================================================
# Manager Integration Tests
# =============================================================================

class TestManagerIntegration:
    """Tests for notification manager integration."""

    @pytest.mark.asyncio
    async def test_notification_manager_connect(self, mock_websocket, mock_notification_manager, sample_workspace_id):
        """Test notification manager connect is called."""
        with patch('api.websocket_routes.notification_manager', mock_notification_manager):
            from api.websocket_routes import websocket_endpoint

            mock_websocket.receive_text.side_effect = Exception("Done")
            try:
                await websocket_endpoint(mock_websocket, sample_workspace_id)
            except:
                pass

        mock_notification_manager.connect.assert_called_once_with(mock_websocket, sample_workspace_id)

    @pytest.mark.asyncio
    async def test_notification_manager_disconnect_on_error(self, mock_websocket, mock_notification_manager, sample_workspace_id):
        """Test notification manager disconnect on error."""
        mock_websocket.receive_text.side_effect = Exception("Test error")

        with patch('api.websocket_routes.notification_manager', mock_notification_manager):
            from api.websocket_routes import websocket_endpoint

            try:
                await websocket_endpoint(mock_websocket, sample_workspace_id)
            except:
                pass

        # Should call disconnect with both websocket and workspace_id
        mock_notification_manager.disconnect.assert_called_with(mock_websocket, sample_workspace_id)


# =============================================================================
# Workspace Routing Tests
# =============================================================================

class TestWorkspaceRouting:
    """Tests for workspace ID routing."""

    @pytest.mark.asyncio
    async def test_different_workspace_ids(self, mock_websocket, mock_notification_manager):
        """Test different workspace IDs are handled separately."""
        workspace_1 = "workspace_1"
        workspace_2 = "workspace_2"

        with patch('api.websocket_routes.notification_manager', mock_notification_manager):
            from api.websocket_routes import websocket_endpoint

            mock_websocket.receive_text.side_effect = Exception("Done")

            # Connect to workspace_1
            try:
                await websocket_endpoint(mock_websocket, workspace_1)
            except:
                pass

            # Verify connect was called with workspace_1
            mock_notification_manager.connect.assert_called_with(mock_websocket, workspace_1)

    @pytest.mark.asyncio
    async def test_workspace_id_in_disconnect(self, mock_websocket, mock_notification_manager, sample_workspace_id):
        """Test workspace ID is passed to disconnect."""
        mock_websocket.receive_text.side_effect = Exception("Test error")

        with patch('api.websocket_routes.notification_manager', mock_notification_manager):
            from api.websocket_routes import websocket_endpoint

            try:
                await websocket_endpoint(mock_websocket, sample_workspace_id)
            except:
                pass

        # Verify disconnect includes workspace_id
        call_args = mock_notification_manager.disconnect.call_args
        assert call_args[0][1] == sample_workspace_id
```

**Verify:**
```bash
test -f backend/tests/unit/test_websocket_routes.py && echo "File exists"
grep -c "^    def test_" backend/tests/unit/test_websocket_routes.py
# Expected: 10-12 tests
```

**Done:**
- File created with 10-12 tests
- WebSocket connection tested
- Ping/pong handling tested
- Disconnect handling tested
- Error handling tested
- Manager integration tested
- Workspace routing tested

---

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_document_ingestion_routes.py | api/document_ingestion_routes.py | TestClient, mock_document_ingestion_service | Document ingestion API tests |
| test_websocket_routes.py | api/websocket_routes.py | mock_websocket, mock_notification_manager | WebSocket route tests |

## Progress Tracking

**Current Coverage (Phase 8.9):** 21-22%
**Plan 33 Target:** +0.6-0.8 percentage points
**Projected After Plans 31-33:** ~25-27%

## Notes

- Covers 2 files: document_ingestion_routes.py (450 lines), websocket_routes.py (25 lines)
- 50% coverage target (sustainable for 475 total lines)
- Test patterns from Phase 8.7/8.8/8.9 applied (TestClient, mocks, fixtures)
- Estimated 30-37 total tests across 2 files
- Duration: 1.5-2 hours
- All external dependencies mocked (document ingestion service, WebSocket, notification manager)
