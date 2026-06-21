"""
TDD regression tests for round 4: WebSocket auth, error sanitization,
migration identifier validation, agent_status auth.
"""

from __future__ import annotations

import inspect

import pytest


# ---------------------------------------------------------------------------
# BUG 1: WebSocket endpoints require JWT auth
# ---------------------------------------------------------------------------


class TestWebSocketAuth:
    """Both WS endpoints must verify JWT before accepting connections."""

    def test_main_ws_checks_token(self):
        """The /ws/{workspace_id} endpoint must check query param 'token'."""
        from api.websocket_routes import websocket_endpoint

        src = inspect.getsource(websocket_endpoint)
        assert "query_params" in src and "token" in src, (
            "WebSocket endpoint must extract token from query params"
        )
        assert "1008" in src, (
            "WebSocket must close with code 1008 (policy violation) on auth failure"
        )

    def test_canvas_ws_checks_token(self):
        """The /canvas/ws/{canvas_id} endpoint must check query param 'token'."""
        from api.canvas_routes import canvas_state_websocket

        src = inspect.getsource(canvas_state_websocket)
        assert "query_params" in src and "token" in src
        assert "1008" in src

    def test_ws_auth_helper_reads_user_id_claim(self):
        """get_current_user_ws must use the same sub/id/user_id fallback."""
        from core.auth import get_current_user_ws

        src = inspect.getsource(get_current_user_ws)
        assert "user_id" in src, (
            "get_current_user_ws must check 'user_id' claim (enterprise token format)"
        )


# ---------------------------------------------------------------------------
# BUG 7: Error messages sanitized
# ---------------------------------------------------------------------------


class TestErrorSanitization:
    """Broad except handlers must NOT return str(e) to clients."""

    def test_no_raw_str_e_in_error_returns(self):
        """Static guard: 'error': str(e) must not appear in top-level
        except blocks that catch broad Exception."""
        from core import atom_agent_endpoints as mod

        src = inspect.getsource(mod)
        # The old pattern was: return {"success": False, "error": str(e)}
        # All such instances should now be: "Internal server error"
        # Count remaining raw str(e) in return/error contexts
        import re
        raw_patterns = re.findall(r'"error":\s*str\(e\)', src)
        assert len(raw_patterns) == 0, (
            f"Found {len(raw_patterns)} instances of '\"error\": str(e)' — "
            "internal exception details leaked to clients"
        )


# ---------------------------------------------------------------------------
# BUG 10: Migration scripts validate identifiers
# ---------------------------------------------------------------------------


class TestMigrationIdentifierValidation:
    """Migration scripts must validate SQL identifiers before interpolation."""

    def test_jsonb_migration_validates_identifiers(self):
        from core.migrate_json_to_jsonb import _validate_identifier

        # Valid identifiers pass
        _validate_identifier("graph_nodes")
        _validate_identifier("properties")
        _validate_identifier("json_schema")

        # Invalid identifiers raise
        with pytest.raises(ValueError):
            _validate_identifier("'; DROP TABLE--")
        with pytest.raises(ValueError):
            _validate_identifier("col'; DELETE")
        with pytest.raises(ValueError):
            _validate_identifier("123bad")

    def test_gin_migration_validates_identifiers(self):
        from core.migrate_add_gin_indexes import _validate_ident

        _validate_ident("graph_nodes")
        _validate_ident("ix_index_name")
        with pytest.raises(ValueError):
            _validate_ident("bad; DROP")


# ---------------------------------------------------------------------------
# Agent status endpoints require auth
# ---------------------------------------------------------------------------


class TestAgentStatusEndpointsRequireAuth:
    """All mutating agent_status endpoints must have Depends(get_current_user)."""

    def test_heartbeat_has_auth(self):
        from api.agent_status_endpoints import agent_heartbeat

        sig = inspect.signature(agent_heartbeat)
        assert "current_user" in sig.parameters

    def test_update_task_has_auth(self):
        from api.agent_status_endpoints import update_task_status

        sig = inspect.signature(update_task_status)
        assert "current_user" in sig.parameters

    def test_create_task_has_auth(self):
        from api.agent_status_endpoints import create_task

        sig = inspect.signature(create_task)
        assert "current_user" in sig.parameters

    def test_delete_task_has_auth(self):
        from api.agent_status_endpoints import delete_task

        sig = inspect.signature(delete_task)
        assert "current_user" in sig.parameters


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
