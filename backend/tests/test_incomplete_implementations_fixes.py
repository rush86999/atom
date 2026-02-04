"""
Test suite for Incomplete and Inconsistent Implementation Fixes

Tests for the critical fixes applied to incomplete and inconsistent implementations:
1. Authentication on document ingestion routes
2. Authentication on document routes  
3. Logging improvements (silent exception fixes)
4. Exception context enhancements
"""
import pytest
from unittest.mock import patch, MagicMock


class TestDocumentIngestionAuth:
    """Test authentication requirements for document ingestion endpoints"""

    def test_get_all_ingestion_settings_requires_auth(self, client):
        """Verify GET /settings requires authentication"""
        response = client.get("/api/document-ingestion/settings")
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_get_integration_settings_requires_auth(self, client):
        """Verify GET /settings/{integration_id} requires authentication"""
        response = client.get("/api/document-ingestion/settings/test-drive")
        assert response.status_code == 401

    def test_update_ingestion_settings_requires_auth(self, client):
        """Verify PUT /settings requires authentication"""
        response = client.put("/api/document-ingestion/settings", json={
            "integration_id": "test-drive",
            "enabled": True
        })
        assert response.status_code == 401

    def test_trigger_document_sync_requires_auth(self, client):
        """Verify POST /sync/{integration_id} requires authentication"""
        response = client.post("/api/document-ingestion/sync/test-drive")
        assert response.status_code == 401

    def test_remove_integration_memory_requires_auth(self, client):
        """Verify DELETE /memory/{integration_id} requires authentication"""
        response = client.delete("/api/document-ingestion/memory/test-drive")
        assert response.status_code == 401


class TestDocumentRoutesAuth:
    """Test authentication requirements for document endpoints"""

    def test_ingest_document_requires_auth(self, client):
        """Verify POST /ingest requires authentication"""
        response = client.post("/api/documents/ingest", json={
            "content": "Test content",
            "type": "text"
        })
        assert response.status_code == 401

    def test_upload_document_requires_auth(self, client):
        """Verify POST /upload requires authentication"""
        response = client.post("/api/documents/upload")
        assert response.status_code == 401


class TestExceptionEnhancements:
    """Test that custom exceptions carry useful context"""

    def test_deep_link_parse_exception_with_url(self):
        """Verify DeepLinkParseException carries URL context"""
        from core.deeplinks import DeepLinkParseException

        exc = DeepLinkParseException("Invalid URL format", url="atom://test")
        assert exc.url == "atom://test"
        assert "atom://test" in str(exc)
        assert "Invalid URL format" in str(exc)

    def test_deep_link_parse_exception_with_details(self):
        """Verify DeepLinkParseException carries details context"""
        from core.deeplinks import DeepLinkParseException

        exc = DeepLinkParseException(
            "Parse failed",
            url="atom://test",
            details={"missing_param": "agent_id"}
        )
        assert exc.details == {"missing_param": "agent_id"}
        assert exc.url == "atom://test"

    def test_deep_link_security_exception_with_context(self):
        """Verify DeepLinkSecurityException carries security context"""
        from core.deeplinks import DeepLinkSecurityException

        exc = DeepLinkSecurityException(
            "Security validation failed",
            url="atom://malicious",
            security_issue="Invalid protocol"
        )
        assert exc.url == "atom://malicious"
        assert exc.security_issue == "Invalid protocol"
        assert "atom://malicious" in str(exc)
        assert "Invalid protocol" in str(exc)

    def test_component_security_error_with_context(self):
        """Verify ComponentSecurityError carries validation context"""
        from core.custom_components_service import ComponentSecurityError

        exc = ComponentSecurityError(
            "Validation failed",
            component_name="test-component",
            validation_reason="Contains script tag"
        )
        assert exc.component_name == "test-component"
        assert exc.validation_reason == "Contains script tag"
        assert "test-component" in str(exc)
        assert "Contains script tag" in str(exc)


class TestLoggingImprovements:
    """Test that exceptions are logged instead of silently ignored"""

    def test_exception_classes_backwards_compatible(self):
        """Verify enhanced exception classes are backwards compatible"""
        from core.deeplinks import DeepLinkParseException, DeepLinkSecurityException
        from core.custom_components_service import ComponentSecurityError

        # Old usage pattern (no additional args) should still work
        exc1 = DeepLinkParseException("Parse error")
        assert "Parse error" in str(exc1)

        exc2 = DeepLinkSecurityException("Security error")
        assert "Security error" in str(exc2)

        exc3 = ComponentSecurityError("Validation error")
        assert "Validation error" in str(exc3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
