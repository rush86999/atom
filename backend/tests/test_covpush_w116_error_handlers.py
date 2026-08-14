"""
Backend depth wave 116 (2026-08-13) — coverage push for core/error_handlers.py.

Covers the remaining untested lines: module-import failure path,
global_exception_handler, atom_exception_handler severity mapping, and
Result edge branches. Fully mocked — zero LLM spend.
"""

import asyncio
import os
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

import core.error_handlers as eh
from core.error_handlers import (
    Result,
    ErrorCode,
    api_error,
    handle_not_found,
    handle_permission_denied,
)
from core.exceptions import AtomException, ErrorSeverity
from core.exceptions import ErrorCode as AtomErrorCode


class TestAtomExceptionsAvailability:
    """Cover module-level import fallback (lines 23-25)."""

    def test_fallback_when_exceptions_module_unavailable(self):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        probe = (
            "import sys\n"
            "sys.modules['core.exceptions'] = None\n"
            "import core.error_handlers\n"
            "assert core.error_handlers.ATOM_EXCEPTIONS_AVAILABLE is False\n"
            "assert core.error_handlers.global_exception_handler is not None\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = backend_dir
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            env=env,
            cwd=backend_dir,
        )
        assert result.returncode == 0, result.stderr
        assert "ATOM_EXCEPTIONS_AVAILABLE" not in result.stderr

    def test_atom_exception_handler_falls_back_to_global(self):
        request = Mock()
        request.state.request_id = "req-fallback"
        request.url = "http://test/x"
        exc = ValueError("boom")
        with patch.object(eh, "ATOM_EXCEPTIONS_AVAILABLE", False):
            resp = asyncio.run(eh.atom_exception_handler(request, exc))
        assert resp.status_code == 500


class TestGlobalExceptionHandler:
    """Cover global_exception_handler (lines 257-288)."""

    def _handler_result(self, environment=None, request_id="req-global"):
        request = Mock()
        request.state.request_id = request_id
        request.url = "http://test/boom"
        if environment is not None:
            env_patch = patch.dict(
                os.environ, {"ENVIRONMENT": environment}, clear=False
            )
        else:
            env_patch = patch.dict(
                os.environ, {}, clear=False
            )
            request._env_cleared = True
        with env_patch:
            if environment is None:
                os.environ.pop("ENVIRONMENT", None)
            return asyncio.run(
                eh.global_exception_handler(request, ValueError("boom"))
            )

    def test_production_hides_internal_error(self):
        resp = self._handler_result(environment="production")
        assert resp.status_code == 500
        assert "boom" not in resp.body.decode()

    def test_development_exposes_error_message(self):
        resp = self._handler_result(environment="development")
        body = resp.body.decode()
        assert "ValueError" in body
        assert "boom" in body
        assert "traceback" in body

    def test_no_environment_defaults_to_generic(self):
        resp = self._handler_result()
        assert resp.status_code == 500
        body = resp.body.decode()
        assert "internal server error occurred" in body

    def test_routes_atom_exception_to_specialized_handler(self):
        request = Mock()
        request.state.request_id = "req-atom"
        request.url = "http://test/atom"
        exc = AtomException(
            "custom failure",
            error_code=AtomErrorCode.AGENT_NOT_FOUND,
            severity=ErrorSeverity.HIGH,
        )
        resp = asyncio.run(eh.global_exception_handler(request, exc))
        assert resp.status_code == 500
        assert "custom failure" in resp.body.decode()


class TestAtomExceptionHandler:
    """Cover atom_exception_handler severity mapping (lines 308-349)."""

    @staticmethod
    def _make_exc(severity, code=AtomErrorCode.AGENT_GOVERNANCE_FAILED,
                  details=None, cause=None):
        return AtomException(
            "governance blocked",
            error_code=code,
            severity=severity,
            details=details,
            cause=cause,
        )

    def _handle(self, exc):
        request = Mock()
        request.state.request_id = "req-sev"
        request.url = "http://test/sev"
        return asyncio.run(eh.atom_exception_handler(request, exc))

    def test_critical_maps_to_500(self):
        resp = self._handle(self._make_exc(ErrorSeverity.CRITICAL))
        assert resp.status_code == 500

    def test_high_maps_to_500(self):
        resp = self._handle(self._make_exc(ErrorSeverity.HIGH))
        assert resp.status_code == 500

    def test_medium_maps_to_400(self):
        resp = self._handle(self._make_exc(ErrorSeverity.MEDIUM))
        assert resp.status_code == 400

    def test_low_maps_to_400(self):
        resp = self._handle(self._make_exc(ErrorSeverity.LOW))
        assert resp.status_code == 400

    def test_info_maps_to_200(self):
        resp = self._handle(self._make_exc(ErrorSeverity.INFO))
        assert resp.status_code == 200

    def test_includes_details_and_request_id(self):
        resp = self._handle(
            self._make_exc(ErrorSeverity.MEDIUM, details={"agent_id": "a-1"})
        )
        assert '"a-1"' in resp.body.decode()
        assert "req-sev" in resp.body.decode()

    def test_exc_info_logged_when_cause_present(self):
        exc = self._make_exc(ErrorSeverity.HIGH, cause=RuntimeError("root"))
        resp = self._handle(exc)
        assert resp.status_code == 500


class TestHandleNotFoundMerge:
    """Regression guard for the shallow-merge bug (wave 116)."""

    def test_extra_details_keep_resource_identity(self):
        error = handle_not_found(
            resource_type="Workspace",
            resource_id="workspace-456",
            details={"workspace_name": "Test Workspace"},
        )
        details = error.detail["details"]
        assert details["resource_type"] == "Workspace"
        assert details["resource_id"] == "workspace-456"
        assert details["workspace_name"] == "Test Workspace"

    def test_permission_denied_extra_details_keep_action(self):
        error = handle_permission_denied(
            action="delete",
            resource_type="Agent",
            details={"agent_id": "agent-9"},
        )
        details = error.detail["details"]
        assert details["action"] == "delete"
        assert details["resource_type"] == "Agent"
        assert details["agent_id"] == "agent-9"

    def test_defaults_still_apply_without_details(self):
        error = handle_not_found(resource_type="Agent", resource_id="agent-1")
        details = error.detail["details"]
        assert details["resource_type"] == "Agent"
        assert details["resource_id"] == "agent-1"


class TestResultEdgeBranches:
    """Cover Result unwrap_or/map/from_exception edge branches."""

    def test_unwrap_or_returns_value_on_success(self):
        assert Result.ok(5).unwrap_or(10) == 5

    def test_map_preserves_error_on_failure(self):
        result = Result.error("nope", ErrorCode.VALIDATION_ERROR)
        mapped = result.map(lambda v: v + 1)
        assert mapped.is_ok is False
        assert mapped is result

    def test_from_exception_non_invoice_error_records_type(self):
        result = Result.from_exception(ValueError("bad input"))
        assert result.is_ok is False
        assert result.error.message == "bad input"
        assert result.error.code == ErrorCode.INTERNAL_SERVER_ERROR
        assert result.error.details["original_exception"] == "ValueError"

    def test_map_catches_mapping_exception(self):
        def bad_map(v):
            raise RuntimeError("mapper exploded")

        result = Result.ok(1).map(bad_map)
        assert result.is_ok is False
        assert "mapper exploded" in result.error.message

    def test_api_error_with_request_id(self):
        error = api_error(
            ErrorCode.RESOURCE_NOT_FOUND,
            "missing",
            request_id="req-42",
            status_code=404,
        )
        assert error.detail["request_id"] == "req-42"
        assert error.status_code == 404
