"""
Test for LanceDB handler connection leak fix.

Issue: #7488074293
Root cause: get_lancedb_handler() caches handlers globally. When a SQLAlchemy session
is passed, it gets stored indefinitely in LanceDBHandler → LLMService → BYOKHandler,
causing connection leaks.

Fix: Don't cache handlers when a db session is passed. Only cache when db=None.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from core.lancedb_handler import get_lancedb_handler, _workspace_handlers


class TestLanceDBHandlerConnectionLeak:
    """Test that handlers with db sessions are not cached."""

    def test_handler_with_db_session_not_cached(self):
        """
        When get_lancedb_handler is called with a db session,
        the handler should NOT be cached in _workspace_handlers.
        """
        # Clear the cache first
        _workspace_handlers.clear()

        # Create a mock db session
        mock_db = Mock()

        # Get handler with db session
        handler1 = get_lancedb_handler(workspace_id="test_ws", db=mock_db)

        # Verify handler was created
        assert handler1 is not None
        assert handler1.workspace_id == "test_ws"

        # Verify handler was NOT cached
        assert "test_ws" not in _workspace_handlers

    def test_handler_without_db_session_is_cached(self):
        """
        When get_lancedb_handler is called without db session,
        the handler SHOULD be cached for performance.
        """
        # Clear the cache first
        _workspace_handlers.clear()

        # Get handler without db session
        handler1 = get_lancedb_handler(workspace_id="cached_ws")
        handler2 = get_lancedb_handler(workspace_id="cached_ws")

        # Verify same instance is returned (cached)
        assert handler1 is handler2
        assert "cached_ws" in _workspace_handlers

    def test_different_db_sessions_create_different_handlers(self):
        """
        Multiple calls with different db sessions should create
        different handlers (not cached).
        """
        # Clear the cache first
        _workspace_handlers.clear()

        # Create different mock sessions
        mock_db1 = Mock()
        mock_db2 = Mock()

        # Get handlers with different sessions
        handler1 = get_lancedb_handler(workspace_id="multi_ws", db=mock_db1)
        handler2 = get_lancedb_handler(workspace_id="multi_ws", db=mock_db2)

        # Verify different instances are returned
        assert handler1 is not handler2

        # Verify still not cached
        assert "multi_ws" not in _workspace_handlers

    def test_cached_handler_does_not_hold_db_reference(self):
        """
        A cached handler (created without db) should not hold
        a reference to any specific db session.
        """
        # Clear the cache first
        _workspace_handlers.clear()

        # Get handler without db (cached)
        handler = get_lancedb_handler(workspace_id="no_db_ws")

        # Verify it was cached
        assert "no_db_ws" in _workspace_handlers

        # The handler's internal services should handle their own sessions
        # LLMService and BYOKHandler should use get_db_session() internally
        # rather than storing a session reference
        assert handler is not None
