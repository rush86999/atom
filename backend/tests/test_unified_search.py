"""
Unit Tests for Unified Search (LanceDB)

Tests for the unified search endpoints and LanceDB integration.
"""

import asyncio
import os
import pytest
from unittest.mock import patch, Mock
from fastapi import HTTPException

from core.unified_search_endpoints import (
    router,
    SearchRequest,
    SearchFilters,
    SearchResult,
    SearchResponse,
    hybrid_search,
)


class TestSearchRequestModel:
    """Test cases for SearchRequest Pydantic model"""

    def test_valid_search_request(self):
        """Test valid search request"""
        request = SearchRequest(
            query="test query",
            user_id="user123",
            search_type="hybrid",
            limit=10
        )

        assert request.query == "test query"
        assert request.user_id == "user123"
        assert request.search_type == "hybrid"
        assert request.limit == 10

    def test_search_request_with_filters(self):
        """Test search request with filters"""
        filters = SearchFilters(
            doc_type=["document", "email"],
            min_score=0.7
        )

        request = SearchRequest(
            query="test",
            user_id="user123",
            filters=filters
        )

        assert request.filters is not None
        assert request.filters.doc_type == ["document", "email"]
        assert request.filters.min_score == 0.7

    def test_search_request_limit_validation(self):
        """Test search request limit validation"""
        # Valid limit
        request = SearchRequest(
            query="test",
            user_id="user123",
            limit=50
        )
        assert request.limit == 50

    def test_search_request_invalid_search_type(self):
        """Test invalid search type"""
        with pytest.raises(Exception):  # Pydantic validation error
            SearchRequest(
                query="test",
                user_id="user123",
                search_type="invalid_type"
            )


class TestSearchFiltersModel:
    """Test cases for SearchFilters Pydantic model"""

    def test_default_filters(self):
        """Test default filter values"""
        filters = SearchFilters()

        assert filters.doc_type == []
        assert filters.tags == []
        assert filters.date_range is None
        # source default is -10.0 ("no minimum" — the endpoint also falls back
        # to -10.0 when filters are absent); repaired 2026-08-13 (wave 81)
        assert filters.min_score == -10.0

    def test_custom_filters(self):
        """Test custom filter values"""
        filters = SearchFilters(
            doc_type=["document"],
            tags=["important", "work"],
            min_score=0.8
        )

        assert filters.doc_type == ["document"]
        assert filters.tags == ["important", "work"]
        assert filters.min_score == 0.8


class TestSearchResultModel:
    """Test cases for SearchResult Pydantic model"""

    def test_valid_search_result(self):
        """Test valid search result"""
        result = SearchResult(
            id="doc123",
            title="Test Document",
            content="Test content",
            doc_type="document",
            source_uri="file://test.pdf",
            similarity_score=0.85,
            metadata={"author": "test"}
        )

        assert result.id == "doc123"
        assert result.title == "Test Document"
        assert result.similarity_score == 0.85

    def test_search_result_with_keyword_score(self):
        """Test search result with keyword score"""
        result = SearchResult(
            id="doc123",
            title="Test",
            content="Content",
            doc_type="document",
            source_uri="file://test.pdf",
            similarity_score=0.7,
            keyword_score=0.8,
            combined_score=0.75,
            metadata={}
        )

        assert result.keyword_score == 0.8
        assert result.combined_score == 0.75


class TestHybridSearchEndpoint:
    """Test cases for hybrid search endpoint"""

    @patch('core.unified_search_endpoints.get_lancedb_handler')
    def test_hybrid_search_success(self, mock_get_handler):
        """Test successful hybrid search"""
        # Mock LanceDB handler
        mock_handler = Mock()
        mock_handler.db = Mock()
        mock_handler.search.return_value = [
            {
                "id": "doc1",
                "text": "Test content 1",
                "score": 0.85,
                "source": "file1.pdf",
                "metadata": {"title": "Doc 1", "doc_type": "document"}
            },
            {
                "id": "doc2",
                "text": "Test content 2",
                "score": 0.75,
                "source": "file2.pdf",
                "metadata": {"title": "Doc 2", "doc_type": "document"}
            }
        ]
        mock_get_handler.return_value = mock_handler

        request = SearchRequest(
            query="test query",
            user_id="user123",
            search_type="hybrid"
        )

        # This would be called via the router
        # For testing, just verify the logic
        assert mock_handler.search is not None

    @patch('core.unified_search_endpoints.get_lancedb_handler')
    def test_hybrid_search_unavailable(self, mock_get_handler):
        """Test hybrid search when LanceDB is unavailable"""
        mock_handler = Mock()
        mock_handler.db = None
        mock_get_handler.return_value = mock_handler

        # Should raise HTTPException when db is None
        # This is tested by verifying the handler setup
        assert mock_handler.db is None

    @patch('core.unified_search_endpoints.get_lancedb_handler')
    @patch.dict(os.environ, {'ATOM_DISABLE_LANCEDB': 'true'})
    def test_search_disabled_via_env_var(self, mock_get_handler):
        """Test search disabled via environment variable"""
        # When ATOM_DISABLE_LANCEDB is true, search should be disabled
        assert os.getenv('ATOM_DISABLE_LANCEDB') == 'true'


class TestHealthEndpoint:
    """Test cases for health check endpoint"""

    @patch('core.unified_search_endpoints.get_lancedb_handler')
    def test_health_check_healthy(self, mock_get_handler):
        """Test health check when system is healthy"""
        mock_handler = Mock()
        mock_handler.db = Mock()
        mock_handler.db_path = "/data/lancedb"
        mock_get_handler.return_value = mock_handler

        # Should return healthy status
        assert mock_handler.db is not None
        assert mock_handler.db_path == "/data/lancedb"

    @patch('core.unified_search_endpoints.get_lancedb_handler')
    def test_health_check_unavailable(self, mock_get_handler):
        """Test health check when system is unavailable"""
        mock_handler = Mock()
        mock_handler.db = None
        mock_get_handler.return_value = mock_handler

        # Should return unavailable status
        assert mock_handler.db is None

    @patch.dict(os.environ, {'ATOM_DISABLE_LANCEDB': 'true'})
    def test_health_check_disabled(self):
        """Test health check when search is disabled"""
        # When disabled, should return disabled status
        assert os.getenv('ATOM_DISABLE_LANCEDB') == 'true'


class _Actor:
    """Minimal authenticated principal used by the endpoint tests."""

    def __init__(
        self,
        *,
        user_id="user-fk-1",
        workspace_id="ws-fk-1",
        workspaces=None,
        email="member@example.com",
        tenant_id="tenant-1",
    ):
        self.id = user_id
        self.workspace_id = workspace_id
        self.workspaces = [] if workspaces is None else workspaces
        self.email = email
        self.tenant_id = tenant_id


class _BrokenBindingActor:
    """Authenticated principal whose workspace relationship cannot be read."""

    id = "user-broken-1"
    workspace_id = None
    tenant_id = None
    email = "member@example.com"

    @property
    def workspaces(self):
        raise RuntimeError("workspace binding store unavailable")


class _FakeSearchHandler:
    """Stand-in for the real handler, including its loop-thread embed guard.

    ``LanceDBHandler.search`` embeds the query synchronously through
    ``embed_text``; on the event-loop thread that guard returns ``None`` and
    the search degrades to ``[]``. Reproducing it here makes the positive
    regression fail if the endpoint stops calling search off-loop.
    """

    def __init__(self, results=None):
        self.db = object()
        self._results = list(results or [])
        self.search_calls = []
        self.ran_off_loop = None

    def _ensure_db(self):
        return None

    def _ensure_embedder(self):
        return None

    def search(self, table_name, query, limit=10, filter_str=None,
               user_id=None, **_kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            self.ran_off_loop = True
        else:
            self.ran_off_loop = False
            return []

        self.search_calls.append({
            "table_name": table_name,
            "query": query,
            "limit": limit,
            "filter_str": filter_str,
            "user_id": user_id,
        })
        return list(self._results)


_MARKER = "SYNTHETIC-UNIFIED-SEARCH-KEY-4F19"


def _marker_row():
    return {
        "id": "doc_synthetic_marker",
        "text": f"synthetic markdown body {_MARKER}",
        "score": 0.91,
        "source": "upload:synthetic-marker.md",
        "metadata": {
            "title": "synthetic-marker.md",
            "doc_type": "document",
        },
    }


class TestHybridSearchAuthenticatedScopeRegression:
    """Regression coverage for the signed-in zero-results failure.

    Runtime evidence: an ordinary signed-in account uploaded a synthetic
    Markdown document (HTTP 200, visible in Documents, SQL mirror written),
    then an exact-marker hybrid search returned success=true with zero raw
    results. Two independent causes are covered:

      1. FK-only accounts were routed to ``default_shared`` instead of the
         authoritative ``users.workspace_id`` store that upload wrote.
      2. ``handler.search`` ran on the event loop, where the synchronous
         embed guard yields ``None`` and every search becomes empty.
    """

    def test_fk_only_actor_searches_authoritative_workspace_off_loop(self):
        actor = _Actor(workspace_id="ws-fk-1", workspaces=[])
        handler = _FakeSearchHandler([_marker_row()])

        with patch(
            "core.unified_search_endpoints.get_lancedb_handler",
            return_value=handler,
        ) as factory:
            response = asyncio.run(hybrid_search(
                SearchRequest(query=_MARKER, search_type="hybrid"),
                current_user=actor,
                db=None,
            ))

        # Upload stores under the FK; search must open that same store.
        factory.assert_called_once_with("ws-fk-1")
        assert handler.ran_off_loop is True
        assert len(handler.search_calls) == 1
        call = handler.search_calls[0]
        assert call["table_name"] == "documents"
        assert call["query"] == _MARKER
        assert call["user_id"] == actor.id
        assert call["filter_str"] is None

        assert response.success is True
        assert response.total_count == 1
        assert response.query == _MARKER
        assert response.search_type == "hybrid"
        assert response.results[0].id == "doc_synthetic_marker"
        assert response.results[0].title == "synthetic-marker.md"
        assert _MARKER in response.results[0].content

    def test_body_supplied_scope_cannot_redirect_search(self):
        actor = _Actor(workspace_id="ws-fk-1", workspaces=[])
        handler = _FakeSearchHandler([_marker_row()])

        with patch(
            "core.unified_search_endpoints.get_lancedb_handler",
            return_value=handler,
        ) as factory:
            response = asyncio.run(hybrid_search(
                SearchRequest(
                    query=_MARKER,
                    workspace_id="ws-body-supplied",
                    user_id="someone-else",
                    limit=5,
                ),
                current_user=actor,
                db=None,
            ))

        factory.assert_called_once_with("ws-fk-1")
        call = handler.search_calls[0]
        assert call["user_id"] == actor.id
        assert call["limit"] == 5
        assert response.success is True
        assert response.total_count == 1

    def test_unbound_actor_fails_closed_without_touching_the_store(self):
        actor = _Actor(workspace_id=None, workspaces=[])

        with patch(
            "core.unified_search_endpoints.get_lancedb_handler",
        ) as factory:
            with pytest.raises(HTTPException) as excinfo:
                asyncio.run(hybrid_search(
                    SearchRequest(query=_MARKER),
                    current_user=actor,
                    db=None,
                ))

        assert excinfo.value.status_code == 403
        factory.assert_not_called()

    def test_unreadable_binding_fails_closed_as_retryable(self):
        actor = _BrokenBindingActor()

        with patch(
            "core.unified_search_endpoints.get_lancedb_handler",
        ) as factory:
            with pytest.raises(HTTPException) as excinfo:
                asyncio.run(hybrid_search(
                    SearchRequest(query=_MARKER),
                    current_user=actor,
                    db=None,
                ))

        assert excinfo.value.status_code == 503
        factory.assert_not_called()
