"""Role-template registry tests — training Phase 2 (TDD).

{domain → canvas set, default tasks, trusted scope} spawns the typed-canvas
set at training-session start and stamps artifacts into CanvasAudit under the
session id, so /approvals can render trainee work as visual cards.
"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.models import Canvas, CanvasAudit, ChatSession


class TestRoleTemplates:
    def test_get_role_template_known(self):
        from core.role_template_registry import get_role_template

        t = get_role_template("bookkeeper")
        assert t is not None
        assert "sheets" in t["canvas_set"]
        assert "send_payment" in t["trusted_scope"].get("never", [])
        assert t["default_tasks"]

    def test_get_role_template_unknown_returns_none(self):
        from core.role_template_registry import get_role_template

        assert get_role_template("nope") is None

    def test_resolve_template_by_specialty(self):
        from core.role_template_registry import resolve_template_for_agent

        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="a1", specialty="sales", category="Communication"
        )
        t = resolve_template_for_agent(db, "a1")
        assert t is not None
        assert "email" in t["canvas_set"]

    def test_resolve_template_by_category_alias(self):
        """'Finance' category maps to the bookkeeper template (alias)."""
        from core.role_template_registry import resolve_template_for_agent

        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="a2", specialty=None, category="Finance"
        )
        t = resolve_template_for_agent(db, "a2")
        assert t is not None
        assert "sheets" in t["canvas_set"]

    def test_resolve_unknown_agent_returns_none(self):
        from core.role_template_registry import resolve_template_for_agent

        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        assert resolve_template_for_agent(db, "missing") is None


class TestSpawnSessionCanvases:
    def _db(self):
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        return db

    def _captured(self, db):
        chat = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], ChatSession)]
        canvases = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], Canvas)]
        audits = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], CanvasAudit)]
        return chat, canvases, audits

    def test_spawn_creates_canvases_and_stamps_session(self):
        from core.role_template_registry import ROLE_TEMPLATES, spawn_session_canvases

        db = self._db()
        session = SimpleNamespace(id="sess-1", tenant_id="t1", agent_id="a1")
        spawned = spawn_session_canvases(db, session, "supervisor-1", template=ROLE_TEMPLATES["sales"])

        chat, canvases, audits = self._captured(db)
        # FK-safe: a ChatSession row with id == session id makes
        # CanvasAudit.session_id (FK → chat_sessions.id) valid.
        assert chat and chat[0].id == "sess-1"
        assert len(canvases) == len(ROLE_TEMPLATES["sales"]["canvas_set"])
        assert len(audits) == len(canvases)
        for canvas, audit in zip(canvases, audits):
            assert audit.session_id == "sess-1"
            assert audit.canvas_id == canvas.id
            assert audit.action_type == "session_spawn"
            assert canvas.tenant_id == "t1"
            assert canvas.created_by == "supervisor-1"
        assert len(spawned) == len(canvases)
        db.commit.assert_called_once()

    def test_spawn_empty_template_returns_empty(self):
        from core.role_template_registry import spawn_session_canvases

        db = self._db()
        session = SimpleNamespace(id="s1", tenant_id="t1", agent_id="a1")
        assert spawn_session_canvases(db, session, "u1", template={}) == []
        db.add.assert_not_called()

    def test_spawn_resolves_template_from_agent(self):
        from core.role_template_registry import spawn_session_canvases

        db = self._db()
        # resolve_template_for_agent hits db.query → return a bookkeeper agent
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="a1", specialty=None, category="Finance"
        )
        session = SimpleNamespace(id="s2", tenant_id="t1", agent_id="a1")
        spawned = spawn_session_canvases(db, session, "u1")
        assert spawned
        _, canvases, audits = self._captured(db)
        assert all(a.canvas_type in ("sheets", "docs") for a in audits)

    def test_get_session_canvases_returns_spawned(self):
        from core.role_template_registry import get_session_canvases

        db = Mock()
        row1 = SimpleNamespace(canvas_id="c1", canvas_type="email", details_json={"x": 1})
        db.query.return_value.filter.return_value.all.return_value = [row1]
        result = get_session_canvases(db, "sess-1")
        assert result == [{"canvas_id": "c1", "canvas_type": "email", "details": {"x": 1}}]

    def test_get_session_canvases_scopes_to_tenant(self):
        """When tenant_id is given the audit lookup filters by tenant too — a
        caller can never read another tenant's canvas metadata (IDOR guard)."""
        from core.role_template_registry import get_session_canvases

        db = Mock()
        row1 = SimpleNamespace(canvas_id="c1", canvas_type="sheets", details_json={"a": 1})
        db.query.return_value.filter.return_value.all.return_value = [row1]
        result = get_session_canvases(db, "sess-1", tenant_id="t1")
        assert result == [{"canvas_id": "c1", "canvas_type": "sheets", "details": {"a": 1}}]
        # the single filter call carried the tenant condition
        filter_keys = {
            expr.left.key
            for call in db.query.return_value.filter.call_args_list
            for expr in call.args
        }
        assert "tenant_id" in filter_keys


class TestApproveHook:
    @pytest.mark.asyncio
    async def test_approve_training_spawns_role_canvases(self):
        """approve_training (student_training_service) calls spawn after the
        session row is committed (best-effort, never breaks approval)."""
        import core.student_training_service as sts

        svc = sts.StudentTrainingService(db=Mock())
        session = SimpleNamespace(id="sess-9", tenant_id="t1", agent_id="a1")
        with patch(
            "core.role_template_registry.spawn_session_canvases",
            return_value=[{"canvas_id": "c1"}],
        ) as mock_spawn:
            result = svc._spawn_role_canvases(session, "supervisor-1")
        mock_spawn.assert_called_once()
        assert result == [{"canvas_id": "c1"}]

    def test_spawn_failure_is_non_fatal_and_rolls_back(self):
        """A failed spawn returns [] (approval never breaks) AND rolls the
        DB session back so no ghost ChatSession/Canvas/CanvasAudit rows are
        left pending on the caller's session."""
        import core.student_training_service as sts

        db = Mock()
        svc = sts.StudentTrainingService(db=db)
        session = SimpleNamespace(id="sess-10", tenant_id="t1", agent_id="a1")
        with patch(
            "core.role_template_registry.spawn_session_canvases",
            side_effect=RuntimeError("boom"),
        ):
            result = svc._spawn_role_canvases(session, "supervisor-1")
        assert result == []
        db.rollback.assert_called_once()


class TestSessionCanvasesRoute:
    """GET /api/maturity/training/sessions/{id}/canvases — the /approvals
    visual-card surface (supervisor-gated, 404 on missing session)."""

    def _route(self):
        from api.agent_maturity_routes import get_training_session_canvases

        return get_training_session_canvases

    def test_route_returns_spawned_canvases(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="s1", tenant_id="t1", supervisor_id="u1"
        )
        with patch(
            "api.agent_maturity_routes._require_supervisor"
        ), patch(
            "api.agent_maturity_routes.role_template_registry.get_session_canvases",
            return_value=[{"canvas_id": "c1", "canvas_type": "email"}],
        ):
            resp = self._route()("s1", SimpleNamespace(id="u1", tenant_id="t1"), db)
        assert resp == {
            "session_id": "s1",
            "canvases": [{"canvas_id": "c1", "canvas_type": "email"}],
        }

    def test_route_404_when_session_missing(self):
        from fastapi import HTTPException

        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("api.agent_maturity_routes._require_supervisor"):
            with pytest.raises(HTTPException) as exc:
                self._route()("missing", SimpleNamespace(id="u1"), db)
        assert exc.value.status_code == 404

    def test_route_allows_supervisor_with_divergent_tenant(self):
        """Greptile finding 2: a session may be stored under "default" (the
        old hardcoded proposal tenant) while its approving supervisor lives in
        a real tenant — the supervisor must still see their own canvases.
        supervisor_id is the authoritative ownership signal; audit rows are
        read under the SESSION's tenant (where spawn wrote them)."""
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="s1", tenant_id="default", supervisor_id="u1"
        )
        with patch(
            "api.agent_maturity_routes._require_supervisor"
        ), patch(
            "api.agent_maturity_routes.role_template_registry.get_session_canvases",
            return_value=[{"canvas_id": "c1", "canvas_type": "email"}],
        ) as mock_canvases:
            resp = self._route()(
                "s1", SimpleNamespace(id="u1", tenant_id="tenant-x"), db
            )
        assert resp["session_id"] == "s1"
        # audit rows scoped to the session's tenant, not the caller's
        assert mock_canvases.call_args.kwargs.get("tenant_id") == "default"

    def test_route_allows_same_tenant_non_supervisor(self):
        """A supervisor in the session's tenant can review it even when they
        were not the approving supervisor."""
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="s2", tenant_id="t1", supervisor_id="other-user"
        )
        with patch(
            "api.agent_maturity_routes._require_supervisor"
        ), patch(
            "api.agent_maturity_routes.role_template_registry.get_session_canvases",
            return_value=[],
        ):
            resp = self._route()(
                "s2", SimpleNamespace(id="u1", tenant_id="t1"), db
            )
        assert resp["session_id"] == "s2"

    def test_route_blocks_cross_tenant_session(self):
        """Foreign session UUID: neither the approving supervisor nor the
        tenant matches → 404 (no existence leak). Greptile finding 1."""
        from fastapi import HTTPException

        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="s3", tenant_id="tenant-other", supervisor_id="someone-else"
        )
        with patch("api.agent_maturity_routes._require_supervisor"):
            with pytest.raises(HTTPException) as exc:
                self._route()(
                    "s3", SimpleNamespace(id="u1", tenant_id="tenant-mine"), db
                )
        assert exc.value.status_code == 404
