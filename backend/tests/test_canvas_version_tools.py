"""Canvas version access for agents — list + revert.

The recovery journey this locks in: an agent (or the co-editor on its
behalf) that made a mistake on a canvas can SEE the version history
(list_canvas_versions — the append-only CanvasAudit trail) and revert to an
exact earlier version by audit_id (restore_canvas_version, appended as a new
version so nothing is lost). Exposed to the agent tool surface as
canvas.list_versions / canvas.restore_version in core/action_registry.

Covers tools/canvas_crud_tool.list_canvas_versions, the restore no-op guard,
and the action_registry registrations.
"""
import asyncio
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from core.models import CanvasAudit, Tenant, User


# ============================================================================
# Fixtures (same shape as test_canvas_list_discovery)
# ============================================================================

@pytest.fixture
def version_user(db_session):
    tenant = Tenant(id=f"t-{uuid.uuid4()}", name="Ver Tenant",
                    subdomain=f"ver-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        id=f"u-{uuid.uuid4()}",
        email=f"ver-{uuid.uuid4()}@example.com",
        hashed_password="hashed_password_here",
        first_name="Test",
        last_name="User",
        role="member",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    return {"user": user, "tenant": tenant}


@pytest.fixture
def patched_session(db_session):
    """Route core.database.get_db_session to the test session."""
    import core.database as db_mod

    original = db_mod.get_db_session

    @contextmanager
    def _test_session():
        yield db_session

    db_mod.get_db_session = _test_session
    try:
        yield db_session
    finally:
        db_mod.get_db_session = original


BASE = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)


def _audit(db, canvas_id, tenant_id, user_id, action_type="present",
           canvas_type="docs", details=None, at=None, agent_id=None):
    row = CanvasAudit(
        id=f"a-{uuid.uuid4()}",
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        canvas_type=canvas_type,
        action_type=action_type,
        user_id=user_id,
        agent_id=agent_id,
        details_json=details or {},
        created_at=at or BASE,
    )
    db.add(row)
    return row


def _seed_three_versions(db, canvas_id, tenant_id, user_id):
    _audit(db, canvas_id, tenant_id, user_id, "present", "docs",
           {"title": "v1 title", "content": "draft one"}, at=BASE)
    # A contentless event stamp between versions — not a version.
    _audit(db, canvas_id, tenant_id, user_id, "email_send", "email",
           {"to": "a@b.com"}, at=BASE + timedelta(minutes=1))
    _audit(db, canvas_id, tenant_id, user_id, "update", "docs",
           {"title": "v2 title", "content": "draft two"}, at=BASE + timedelta(minutes=2),
           agent_id="agent-1")
    _audit(db, canvas_id, tenant_id, user_id, "update", "docs",
           {"title": "v3 title", "content": "draft three"}, at=BASE + timedelta(minutes=3))


def _run(user_id, canvas_id, **kwargs):
    from tools.canvas_crud_tool import list_canvas_versions
    return asyncio.run(list_canvas_versions(user_id, canvas_id, **kwargs))


# ============================================================================
# list_canvas_versions
# ============================================================================

class TestListVersions:
    def test_newest_first_skips_event_and_delete_rows(
        self, db_session, version_user, patched_session
    ):
        u, t = version_user["user"], version_user["tenant"]
        _seed_three_versions(db_session, "cv-ver", t.id, u.id)
        _audit(db_session, "cv-ver", t.id, u.id, "delete", "docs",
               {"deleted": True}, at=BASE + timedelta(minutes=4))

        result = _run(str(u.id), "cv-ver")
        assert result["success"] is True
        assert result["count"] == 3  # the email_send stamp and the delete are not versions
        contents = [v["content"] for v in result["versions"]]
        assert contents == ["draft three", "draft two", "draft one"]

    def test_newest_flagged_current_with_actor_and_title(
        self, db_session, version_user, patched_session
    ):
        u, t = version_user["user"], version_user["tenant"]
        _seed_three_versions(db_session, "cv-cur", t.id, u.id)

        result = _run(str(u.id), "cv-cur")
        newest, middle, oldest = result["versions"]
        assert newest["is_current"] is True
        assert middle["is_current"] is False and oldest["is_current"] is False
        assert newest["title"] == "v3 title"
        assert newest["actor"] == "supervisor"  # agent_id is on v2, not v3
        assert middle["actor"] == "agent"

    def test_previews_bounded_full_content_on_flag(
        self, db_session, version_user, patched_session
    ):
        u, t = version_user["user"], version_user["tenant"]
        long_body = "x" * 5000
        _audit(db_session, "cv-long", t.id, u.id, "present", "docs",
               {"title": "Long", "content": long_body}, at=BASE)
        _audit(db_session, "cv-long", t.id, u.id, "update", "docs",
               {"title": "Longer", "content": long_body + "y"}, at=BASE + timedelta(minutes=1))

        preview = _run(str(u.id), "cv-long")
        assert len(preview["versions"][0]["content"]) < 700
        assert preview["versions"][0]["content_truncated"] is True

        full = _run(str(u.id), "cv-long", include_content=True)
        assert full["versions"][0]["content"] == long_body + "y"
        assert full["versions"][0]["content_truncated"] is False

    def test_owner_guard(self, db_session, version_user, patched_session):
        u, t = version_user["user"], version_user["tenant"]
        _seed_three_versions(db_session, "cv-owned", t.id, u.id)
        result = _run("u-stranger", "cv-owned")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_unknown_canvas(self, db_session, version_user, patched_session):
        u = version_user["user"]
        result = _run(str(u.id), "cv-missing")
        assert result["success"] is False


# ============================================================================
# restore_canvas_version — the revert
# ============================================================================

class TestRestoreVersion:
    def test_restore_appends_new_version_with_provenance(
        self, db_session, version_user, patched_session
    ):
        u, t = version_user["user"], version_user["tenant"]
        _seed_three_versions(db_session, "cv-res", t.id, u.id)
        v1 = (
            db_session.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == "cv-res", CanvasAudit.action_type == "present")
            .one()
        )

        from tools.canvas_crud_tool import restore_canvas_version
        result = asyncio.run(restore_canvas_version(str(u.id), "cv-res", v1.id))
        assert result["success"] is True
        assert result["restored_from"] == v1.id

        rows = (
            db_session.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == "cv-res")
            .order_by(CanvasAudit.created_at.desc())
            .all()
        )
        assert rows[0].action_type == "update"  # appended, nothing rewritten
        assert rows[0].details_json["content"] == "draft one"
        assert rows[0].details_json["restored_from"]["audit_id"] == v1.id
        # v1 itself is untouched (append-only trail).
        db_session.refresh(v1)
        assert v1.details_json["content"] == "draft one"

    def test_restore_to_current_content_is_a_noop(
        self, db_session, version_user, patched_session
    ):
        u, t = version_user["user"], version_user["tenant"]
        _seed_three_versions(db_session, "cv-noop", t.id, u.id)
        newest = (
            db_session.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == "cv-noop", CanvasAudit.action_type == "update")
            .order_by(CanvasAudit.created_at.desc())
            .first()
        )

        from tools.canvas_crud_tool import restore_canvas_version
        result = asyncio.run(restore_canvas_version(str(u.id), "cv-noop", newest.id))
        assert result["success"] is True
        assert result["no_change"] is True

        count = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == "cv-noop").count()
        assert count == 4  # no row appended

    def test_restore_unknown_version(self, db_session, version_user, patched_session):
        u, t = version_user["user"], version_user["tenant"]
        _seed_three_versions(db_session, "cv-unknown", t.id, u.id)

        from tools.canvas_crud_tool import restore_canvas_version
        result = asyncio.run(restore_canvas_version(str(u.id), "cv-unknown", "a-nonexistent"))
        assert result["success"] is False
        assert result["error"] == "Version not found"

    def test_restore_same_second_orders_after_the_edit_it_reverts(
        self, db_session, version_user, patched_session
    ):
        """Second-precision timestamps (legacy rows / server default) tie when
        a restore lands in the same second as the edit it reverts — the
        restore must still order AFTER, or reads serve the pre-restore
        content (the delete tombstone's 2026-09-01 incident class)."""
        u, t = version_user["user"], version_user["tenant"]
        # Naive, SECOND-precision timestamps — the legacy row shape.
        at = datetime(2026, 9, 2, 10, 0, 0)
        v1 = _audit(db_session, "cv-tie", t.id, u.id, "present", "docs",
                    {"title": "v1", "content": "good draft"}, at=at)
        v2 = _audit(db_session, "cv-tie", t.id, u.id, "update", "docs",
                    {"title": "v2", "content": "bad edit"}, at=at)

        from tools.canvas_crud_tool import restore_canvas_version, read_canvas
        result = asyncio.run(restore_canvas_version(str(u.id), "cv-tie", v1.id))
        assert result["success"] is True

        current = asyncio.run(read_canvas(str(u.id), "cv-tie"))
        assert current["success"] is True
        assert current["content"] == "good draft"  # the restore, not the bad edit

    def test_restore_owner_guard(self, db_session, version_user, patched_session):
        u, t = version_user["user"], version_user["tenant"]
        _seed_three_versions(db_session, "cv-guard", t.id, u.id)
        v1 = (
            db_session.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == "cv-guard", CanvasAudit.action_type == "present")
            .one()
        )

        from tools.canvas_crud_tool import restore_canvas_version
        result = asyncio.run(restore_canvas_version("u-stranger", "cv-guard", v1.id))
        assert result["success"] is False


# ============================================================================
# The agent tool surface — action_registry registrations
# ============================================================================

class TestRegistryActions:
    @pytest.mark.asyncio
    async def test_list_versions_requires_auth(self):
        from core.action_registry import action_registry
        result = await action_registry.execute_action(
            "canvas.list_versions", {"canvas_id": "cv-1"}, {})
        assert result["success"] is False
        assert "Authenticated user" in result["error"]

    @pytest.mark.asyncio
    async def test_restore_version_requires_audit_id(self):
        from core.action_registry import action_registry
        result = await action_registry.execute_action(
            "canvas.restore_version",
            {"canvas_id": "cv-1"},
            {"user_id": "u-1"},
        )
        assert result["success"] is False
        assert "audit_id" in result["error"]

    @pytest.mark.asyncio
    async def test_restore_version_requires_auth(self):
        from core.action_registry import action_registry
        result = await action_registry.execute_action(
            "canvas.restore_version",
            {"canvas_id": "cv-1", "audit_id": "a-1"},
            {},
        )
        assert result["success"] is False
        assert "Authenticated user" in result["error"]

    @pytest.mark.asyncio
    async def test_both_actions_reach_the_crud_layer(self):
        from unittest.mock import AsyncMock, patch

        from core.action_registry import action_registry

        with patch(
            "tools.canvas_crud_tool.list_canvas_versions",
            new=AsyncMock(return_value={"success": True, "versions": []}),
        ) as mock_list:
            result = await action_registry.execute_action(
                "canvas.list_versions",
                {"canvas_id": "cv-1", "limit": 5, "include_content": True},
                {"user_id": "u-1"},
            )
            assert result["success"] is True
            mock_list.assert_awaited_once_with("u-1", "cv-1", limit=5, include_content=True)

        with patch(
            "tools.canvas_crud_tool.restore_canvas_version",
            new=AsyncMock(return_value={"success": True, "restored_from": "a-9"}),
        ) as mock_restore:
            result = await action_registry.execute_action(
                "canvas.restore_version",
                {"canvas_id": "cv-1", "audit_id": "a-9"},
                {"user_id": "u-1"},
            )
            assert result["success"] is True
            mock_restore.assert_awaited_once_with("u-1", "cv-1", "a-9")
