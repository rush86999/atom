"""
TDD regression tests for Round 24 bug hunt - Canvas services auth.

Covers unauthenticated canvas routes across docs, email, terminal, sheets.
"""

from __future__ import annotations

import inspect


def _has_auth_dependency(func) -> bool:
    deps = []
    for p in inspect.signature(func).parameters.values():
        if p.default is inspect.Parameter.empty:
            continue
        if hasattr(p.default, "dependency"):
            name = getattr(p.default.dependency, "__name__", "") or p.default.dependency.__class__.__name__
            deps.append(name)
        elif hasattr(p.default, "__name__"):
            deps.append(p.default.__name__)
    markers = ("get_current_user", "verify_token", "require_user", "require_auth",
               "get_current_active_user", "require_admin", "require_permission",
               "require_governance")
    return any(any(m in d for m in markers) for d in deps)


# ---------------------------------------------------------------------------
# Canvas docs routes — 8 routes with NO auth
# ---------------------------------------------------------------------------


class TestCanvasDocsRoutesRequireAuth:
    def _load(self):
        from api import canvas_docs_routes as mod
        return mod

    def test_create_document_canvas_requires_auth(self):
        assert _has_auth_dependency(self._load().create_document_canvas), (
            "POST create_document_canvas has no auth — unauthenticated document creation"
        )

    def test_get_document_canvas_requires_auth(self):
        assert _has_auth_dependency(self._load().get_document_canvas), (
            "GET get_document_canvas has no auth — IDOR, any user can read any document"
        )

    def test_update_document_content_requires_auth(self):
        assert _has_auth_dependency(self._load().update_document_content), (
            "PUT update_document_content has no auth — anyone can mutate document content"
        )

    def test_restore_version_requires_auth(self):
        assert _has_auth_dependency(self._load().restore_version), (
            "POST restore_version has no auth — anyone can roll back documents"
        )


# ---------------------------------------------------------------------------
# Canvas email routes — 5 routes with NO auth
# ---------------------------------------------------------------------------


class TestCanvasEmailRoutesRequireAuth:
    def _load(self):
        from api import canvas_email_routes as mod
        return mod

    def test_create_email_canvas_requires_auth(self):
        assert _has_auth_dependency(self._load().create_email_canvas), (
            "POST create_email_canvas has no auth"
        )

    def test_save_draft_requires_auth(self):
        assert _has_auth_dependency(self._load().save_draft), (
            "POST save_draft has no auth — anyone can create email drafts"
        )


# ---------------------------------------------------------------------------
# Canvas terminal routes — 3 routes with NO auth
# ---------------------------------------------------------------------------


class TestCanvasTerminalRoutesRequireAuth:
    def _load(self):
        from api import canvas_terminal_routes as mod
        return mod

    def test_create_terminal_canvas_requires_auth(self):
        assert _has_auth_dependency(self._load().create_terminal_canvas), (
            "POST create_terminal_canvas has no auth"
        )

    def test_add_output_requires_auth(self):
        assert _has_auth_dependency(self._load().add_output), (
            "POST add_output has no auth — anyone can inject terminal output"
        )
