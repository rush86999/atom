"""P2 — Org-privilege axis (AGENT_ORG_POLITICS_PLAN.md Phase 2).

Permission ≠ Privilege (R4 "Fluid Structure, Rigid Record"): capabilities +
tier bound what tools an agent may *use*; org privileges bound which
*org-state changes* it may authorize (approve/promote/publish/spawn/grant/
halt). Stored under ``AgentRegistry.configuration["org_privileges"]`` with
optional expiring leases. Default-DENY: an empty config means no privileges
at ANY tier — the tier raises the ceiling, privileges grant rights inside it.

Flag: ATOM_ORG_PRIVILEGES_ENABLED (default FALSE until audited — kill switch
restores tier-only behavior instantly).

Enforcement point: integrations/mcp_service.call_tool, immediately after the
P2 capability gate (same seam), so all dispatch paths are gated identically.

Style: isolated in-memory sqlite, zero LLM spend, no network.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db():
    from core.models import AgentRegistry

    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    AgentRegistry.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def agent_row(db):
    from core.models import AgentRegistry

    row = AgentRegistry(
        id="ag-pub",
        name="Publisher",
        category="Operations",
        role="agent",
        type="personal",
        module_path="ops.pub",
        class_name="Pub",
        status="autonomous",
    )
    db.add(row)
    db.commit()
    return row


# ============================================================================
# Module surface
# ============================================================================


class TestPrivilegeConstants:
    def test_six_canonical_privileges(self):
        from core.org_privileges import ORG_PRIVILEGES

        assert ORG_PRIVILEGES == {
            "approve_proposal",
            "promote_agent",
            "publish_skill",
            "spawn_agent",
            "grant_privilege",
            "halt_run",
        }

    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("ATOM_ORG_PRIVILEGES_ENABLED", raising=False)
        from core.org_privileges import privileges_enabled

        assert privileges_enabled() is False

    def test_kill_switch_off_disables(self, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_PRIVILEGES_ENABLED", "false")
        from core.org_privileges import privileges_enabled

        assert privileges_enabled() is False


# ============================================================================
# Grant / revoke / check
# ============================================================================


class TestGrantRevokeCheck:
    def test_default_deny_without_config(self, db, agent_row):
        from core.org_privileges import has_privilege

        assert has_privilege(db, "ag-pub", "publish_skill") is False

    def test_grant_then_has_then_revoke(self, db, agent_row):
        from core.org_privileges import grant_privilege, has_privilege, revoke_privilege

        assert grant_privilege(db, "ag-pub", "publish_skill") is True
        assert has_privilege(db, "ag-pub", "publish_skill") is True
        assert revoke_privilege(db, "ag-pub", "publish_skill") is True
        assert has_privilege(db, "ag-pub", "publish_skill") is False

    def test_tier_does_not_confer_privilege(self, db, agent_row):
        """AUTONOMOUS status alone must NOT imply org privileges."""
        from core.org_privileges import has_privilege

        assert agent_row.status == "autonomous"
        assert has_privilege(db, "ag-pub", "promote_agent") is False

    def test_unknown_privilege_rejected_on_grant(self, db, agent_row):
        from core.org_privileges import grant_privilege

        assert grant_privilege(db, "ag-pub", "become_admin") is False

    def test_missing_agent_denies(self, db):
        from core.org_privileges import has_privilege

        assert has_privilege(db, "no-such-agent", "spawn_agent") is False

    def test_expiry_lease(self, db, agent_row):
        from datetime import datetime, timedelta, timezone

        from core.org_privileges import grant_privilege, has_privilege

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        assert grant_privilege(db, "ag-pub", "halt_run", expires_at=future) is True
        assert has_privilege(db, "ag-pub", "halt_run") is True
        # Re-grant with an already-expired lease -> privilege gone.
        assert grant_privilege(db, "ag-pub", "halt_run", expires_at=past) is True
        assert has_privilege(db, "ag-pub", "halt_run") is False

    def test_grant_persists_via_flag_modified(self, db, agent_row):
        from core.org_privileges import grant_privilege

        grant_privilege(db, "ag-pub", "publish_skill")
        db.expire_all()
        fresh = db.query(type(agent_row)).filter_by(id="ag-pub").first()
        assert (
            (fresh.configuration or {}).get("org_privileges", {})
            .get("publish_skill")
            is not None
        )


# ============================================================================
# Dispatch-layer enforcement (mcp_service.call_tool)
# ============================================================================


def _ctx(agent_id="ag-pub"):
    return {"agent_id": agent_id, "tier": "autonomous"}


@pytest.fixture
def gate_session_is_test_db(db, monkeypatch):
    """Route the gate's self-opened sessions to this test's sqlite."""
    import contextlib

    @contextlib.contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr("core.database.get_db_session", fake_session)


class TestCallToolPrivilegeGate:
    @pytest.mark.asyncio
    async def test_publish_blocked_without_privilege(
        self, db, agent_row, gate_session_is_test_db, monkeypatch
    ):
        monkeypatch.setenv("ATOM_ORG_PRIVILEGES_ENABLED", "true")
        from integrations.mcp_service import mcp_service

        async def fake_execute(action_name, args, ctx):
            return {"success": True, "via": "action_registry"}

        monkeypatch.setattr(
            "core.action_registry.action_registry.execute_action", fake_execute
        )

        result = await mcp_service.call_tool(
            "mini_app_publish", {"canvas_id": "c1"}, _ctx()
        )
        assert result.get("success") is False
        assert result.get("blocked_by") == "privilege_gate"

    @pytest.mark.asyncio
    async def test_publish_allowed_with_grant(
        self, db, agent_row, gate_session_is_test_db, monkeypatch
    ):
        monkeypatch.setenv("ATOM_ORG_PRIVILEGES_ENABLED", "true")
        from core.org_privileges import grant_privilege
        from integrations.mcp_service import mcp_service

        grant_privilege(db, "ag-pub", "publish_skill")

        seen = {}

        async def fake_execute(action_name, args, ctx):
            seen["name"] = action_name
            return {"success": True, "via": "action_registry"}

        monkeypatch.setattr(
            "core.action_registry.action_registry.execute_action", fake_execute
        )

        result = await mcp_service.call_tool(
            "mini_app_publish", {"canvas_id": "c1"}, _ctx()
        )
        assert seen.get("name") == "mini_app_publish"
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_flag_off_bypasses_gate_entirely(
        self, db, agent_row, monkeypatch
    ):
        monkeypatch.setenv("ATOM_ORG_PRIVILEGES_ENABLED", "false")
        from integrations.mcp_service import mcp_service

        async def fake_execute(action_name, args, ctx):
            return {"success": True, "via": "action_registry"}

        monkeypatch.setattr(
            "core.action_registry.action_registry.execute_action", fake_execute
        )

        result = await mcp_service.call_tool(
            "mini_app_publish", {"canvas_id": "c1"}, _ctx()
        )
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_no_agent_context_skips_gate(self, monkeypatch):
        """Unresolved caller (human/user-driven path) is not agent-gated."""
        monkeypatch.setenv("ATOM_ORG_PRIVILEGES_ENABLED", "true")
        from integrations.mcp_service import mcp_service

        async def fake_execute(action_name, args, ctx):
            return {"success": True, "via": "action_registry"}

        monkeypatch.setattr(
            "core.action_registry.action_registry.execute_action", fake_execute
        )

        result = await mcp_service.call_tool(
            "mini_app_publish", {"canvas_id": "c1"}, {}
        )
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_non_org_action_untouched(self, db, agent_row, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_PRIVILEGES_ENABLED", "true")
        from integrations.mcp_service import mcp_service

        async def fake_execute(action_name, args, ctx):
            return {"success": True, "via": "action_registry"}

        monkeypatch.setattr(
            "core.action_registry.action_registry.execute_action", fake_execute
        )

        result = await mcp_service.call_tool(
            "documents.search", {"query": "x"}, _ctx()
        )
        assert result.get("success") is True
