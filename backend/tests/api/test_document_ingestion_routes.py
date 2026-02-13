
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.document_ingestion_routes import router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_list_supported_integrations(client):
    response = client.get("/api/document-ingestion/supported-integrations")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    integrations = data["data"]
    assert len(integrations) > 0


def test_list_supported_file_types(client):
    response = client.get("/api/document-ingestion/supported-file-types")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    file_types = data["data"]
    assert len(file_types) > 0


def test_get_ocr_status(client):
    response = client.get("/api/document-ingestion/ocr-status")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    status = data["data"]
    assert "ocr_engines" in status


def test_parse_document(client):
    from io import BytesIO
    # Test that parse endpoint accepts file upload
    # Note: We don't test actual parsing logic here, just endpoint functionality
    file_content = b"Test content"
    files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
    response = client.post("/api/document-ingestion/parse", files=files)
    # Should return 200 (even if docling is unavailable, it falls back gracefully)
    assert response.status_code == 200
    data = response.json()
    # Check response has expected structure
    assert "success" in data
    assert "content" in data
    assert "method" in data


def test_unauthenticated_request(client):
    response = client.get("/api/document-ingestion/settings")
    assert response.status_code == 401
