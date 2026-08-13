# -*- coding: utf-8 -*-
"""Coverage wave 82 — core/governance_engine (ContactGovernance).

Real in-memory SQLite for Workspace / AgentRegistry / HITLAction /
TenantSetting; the communication_service adapter is mocked (no network).

Coverage targets:
- _session_scope: injected session (caller-owned, never closed) vs
  get_db_session fallback.
- is_external_contact: email against workspace metadata internal_domains
  (internal/external), agent_id→workspace resolution, env fallback
  (INTERNAL_EMAIL_DOMAINS), whatsapp/messenger/slack is_internal flag,
  unknown platform default.
- should_require_approval: workspace missing (fail closed), high confidence,
  learning-phase-completed flag, default pause.
- get_confidence_score: no history → 0.0, approved/total ratio, all approved.
- request_approval: MEDIUM default, URGENT (delete_customer/wipe_database/
  send_mass_email), HIGH (update_billing/change_role), notification fired for
  HIGH/URGENT, not for MEDIUM, returns persisted hitl id.
- _notify_governance_channel: no setting, setting with ':' source:channel
  parsing, send success sets notified_channel_id, BUG W82-4 (missing adapter /
  adapter send error must not crash the HITL request flow).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, MagicMock, patch

from core.database import Base, get_db_session
from core.models import (
    AgentRegistry,
    HITLAction,
    HITLActionStatus,
    TenantSetting,
    Workspace,
)  # noqa: F401

from core.governance_engine import ContactGovernance, contact_governance


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_workspace(db, ws_id="ws-1", internal_domains=None,
                    learning_phase_completed=False, metadata_json=None):
    ws = Workspace(
        id=ws_id,
        name=ws_id,
        metadata_json=metadata_json or ({"internal_domains": internal_domains} if internal_domains else None),
        learning_phase_completed=learning_phase_completed,
    )
    db.add(ws)
    db.commit()
    return ws


def _make_agent(db, agent_id="agent-1", workspace_id="ws-1"):
    agent = AgentRegistry(
        id=agent_id,
        name=agent_id,
        workspace_id=workspace_id,
        tenant_id="t1",
        category="Test",
        module_path="test",
        class_name="Test",
    )
    db.add(agent)
    db.commit()
    return agent


def _make_hitl(db, status="approved", action_type="send_message",
               platform="email", ws_id="ws-1"):
    action = HITLAction(
        workspace_id=ws_id,
        tenant_id="t1",
        agent_id="agent-1",
        action_type=action_type,
        platform=platform,
        params={},
        reason="test",
        status=status,
    )
    db.add(action)
    db.commit()
    return action


class TestSessionScope:
    def test_injected_session_kept_open(self, db):
        gov = ContactGovernance(db_session=db)
        with gov._session_scope() as s:
            assert s is db
        assert db.is_active  # caller owns the session; must not be closed

    def test_factory_session_used_when_none_injected(self, db):
        class _CM:
            def __init__(self, obj):
                self.obj = obj

            def __enter__(self):
                return self.obj

            def __exit__(self, *a):
                return False

        fake_session = MagicMock()
        with patch("core.governance_engine.get_db_session", return_value=_CM(fake_session)) as factory:
            gov = ContactGovernance()
            with gov._session_scope() as s:
                assert s is fake_session
            factory.assert_called_once_with()


class TestIsExternalContact:
    def test_email_internal_domain(self, db):
        _make_workspace(db, internal_domains=["atom.ai", "Workspace.local"])
        gov = ContactGovernance(db_session=db)
        assert gov.is_external_contact(
            "email", {"recipient_id": "bob@ATOM.AI", "workspace_id": "ws-1"}
        ) is False

    def test_email_external_domain(self, db):
        _make_workspace(db, internal_domains=["atom.ai"])
        gov = ContactGovernance(db_session=db)
        assert gov.is_external_contact(
            "email", {"recipient_id": "bob@evil.com", "workspace_id": "ws-1"}
        ) is True

    def test_email_workspace_via_agent(self, db):
        _make_workspace(db, internal_domains=["atom.ai"])
        _make_agent(db, agent_id="agent-1", workspace_id="ws-1")
        gov = ContactGovernance(db_session=db)
        assert gov.is_external_contact(
            "email", {"recipient_id": "bob@atom.ai", "agent_id": "agent-1"}
        ) is False

    def test_email_workspace_missing_metadata_falls_back_to_env(self, db):
        _make_workspace(db, metadata_json={})
        gov = ContactGovernance(db_session=db)
        with patch.dict("os.environ", {"INTERNAL_EMAIL_DOMAINS": "corp.io"}):
            assert gov.is_external_contact(
                "email", {"recipient_id": "bob@corp.io", "workspace_id": "ws-1"}
            ) is False
            assert gov.is_external_contact(
                "email", {"recipient_id": "bob@outside.net", "workspace_id": "ws-1"}
            ) is True

    def test_email_no_workspace_no_agent_env_fallback(self, db):
        gov = ContactGovernance(db_session=db)
        with patch.dict("os.environ", {"INTERNAL_EMAIL_DOMAINS": "atom.ai, workspace.local"}):
            assert gov.is_external_contact("email", {"recipient_id": "x@atom.ai"}) is False
            assert gov.is_external_contact("email", {"recipient_id": "x@other.com"}) is True

    def test_phone_platforms(self, db):
        gov = ContactGovernance(db_session=db)
        assert gov.is_external_contact("whatsapp", {"is_internal": True}) is False
        assert gov.is_external_contact("whatsapp", {}) is True
        assert gov.is_external_contact("messenger", {"is_internal": True}) is False
        assert gov.is_external_contact("slack", {"is_internal": False}) is True

    def test_unknown_platform_default_external(self, db):
        gov = ContactGovernance(db_session=db)
        assert gov.is_external_contact("carrier_pigeon", {}) is True


class TestShouldRequireApproval:
    @pytest.mark.asyncio
    async def test_workspace_missing_fails_closed(self, db):
        gov = ContactGovernance(db_session=db)
        assert await gov.should_require_approval("ghost", "send_message", "email", {}) is True

    @pytest.mark.asyncio
    async def test_high_confidence_autonomous(self, db):
        _make_workspace(db, internal_domains=["atom.ai"])
        for _ in range(9):
            _make_hitl(db, status="approved")
        _make_hitl(db, status="pending")
        gov = ContactGovernance(db_session=db)
        assert await gov.should_require_approval("ws-1", "send_message", "email", {}) is False

    @pytest.mark.asyncio
    async def test_workspace_graduation_flag(self, db):
        _make_workspace(db, learning_phase_completed=True)
        gov = ContactGovernance(db_session=db)
        assert await gov.should_require_approval("ws-1", "send_message", "email", {}) is False

    @pytest.mark.asyncio
    async def test_learning_phase_default_pause(self, db):
        _make_workspace(db)
        gov = ContactGovernance(db_session=db)
        assert await gov.should_require_approval("ws-1", "send_message", "email", {}) is True

    @pytest.mark.asyncio
    async def test_confidence_boundary_090(self, db):
        _make_workspace(db)
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved")
        _make_hitl(db, status="pending")
        gov = ContactGovernance(db_session=db)
        assert await gov.should_require_approval("ws-1", "send_message", "email", {}) is False


class TestGetConfidenceScore:
    def test_no_history(self, db):
        _make_workspace(db)
        gov = ContactGovernance(db_session=db)
        assert gov.get_confidence_score("ws-1", "send_message", "email") == 0.0

    def test_ratio(self, db):
        _make_workspace(db)
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved")
        _make_hitl(db, status="pending")
        _make_hitl(db, status="pending")
        gov = ContactGovernance(db_session=db)
        assert gov.get_confidence_score("ws-1", "send_message", "email") == 0.5

    def test_all_approved(self, db):
        _make_workspace(db)
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved")
        gov = ContactGovernance(db_session=db)
        assert gov.get_confidence_score("ws-1", "send_message", "email") == 1.0

    def test_ignores_other_patterns(self, db):
        _make_workspace(db)
        _make_hitl(db, status="approved")
        _make_hitl(db, status="approved", action_type="other_action")
        gov = ContactGovernance(db_session=db)
        assert gov.get_confidence_score("ws-1", "send_message", "email") == 1.0


class TestRequestApproval:
    @pytest.mark.asyncio
    async def test_medium_no_notification(self, db):
        _make_workspace(db)
        gov = ContactGovernance(db_session=db)
        with patch("core.communication_service.communication_service") as comm:
            hitl_id = await gov.request_approval("ws-1", "send_message", "email", {}, "reason")
        assert hitl_id
        saved = db.query(HITLAction).filter(HITLAction.id == hitl_id).first()
        assert saved is not None
        assert saved.priority == "MEDIUM"
        assert saved.status == HITLActionStatus.PENDING.value
        comm.get_adapter.assert_not_called()

    @pytest.mark.asyncio
    async def test_urgent_priority_and_notification(self, db):
        _make_workspace(db)
        db.add(TenantSetting(tenant_id="t1", setting_key="governance_alerts_channel",
                             setting_value="slack:C123"))
        db.commit()
        gov = ContactGovernance(db_session=db)
        adapter = MagicMock()
        adapter.send_approval_request = AsyncMock(return_value=True)
        with patch("core.communication_service.communication_service") as comm:
            comm.get_adapter.return_value = adapter
            hitl_id = await gov.request_approval(
                "ws-1", "delete_customer", "email",
                {"tenant_id": "t1", "agent_id": "agent-1"}, "customer left"
            )
        saved = db.query(HITLAction).filter(HITLAction.id == hitl_id).first()
        assert saved.priority == "URGENT"
        assert saved.notified_channel_id == "slack:C123"
        adapter.send_approval_request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_high_priority(self, db):
        _make_workspace(db)
        gov = ContactGovernance(db_session=db)
        with patch("core.communication_service.communication_service") as comm:
            comm.get_adapter.return_value = MagicMock()
            hitl_id = await gov.request_approval("ws-1", "update_billing", "email", {}, "r")
        assert db.query(HITLAction).filter(HITLAction.id == hitl_id).first().priority == "HIGH"

    @pytest.mark.asyncio
    async def test_mass_email_urgent(self, db):
        _make_workspace(db)
        gov = ContactGovernance(db_session=db)
        hitl_id = await gov.request_approval("ws-1", "send_mass_email", "email", {}, "r")
        assert db.query(HITLAction).filter(HITLAction.id == hitl_id).first().priority == "URGENT"

    @pytest.mark.asyncio
    async def test_change_role_high(self, db):
        _make_workspace(db)
        gov = ContactGovernance(db_session=db)
        hitl_id = await gov.request_approval("ws-1", "change_role", "email", {}, "r")
        assert db.query(HITLAction).filter(HITLAction.id == hitl_id).first().priority == "HIGH"


class TestNotifyGovernanceChannel:
    @pytest.mark.asyncio
    async def test_no_setting(self, db):
        _make_workspace(db)
        _make_hitl(db)
        gov = ContactGovernance(db_session=db)
        hitl = db.query(HITLAction).first()
        with patch("core.communication_service.communication_service") as comm:
            await gov._notify_governance_channel(db, hitl)
        comm.get_adapter.assert_not_called()

    @pytest.mark.asyncio
    async def test_setting_with_source_prefix(self, db):
        _make_workspace(db)
        db.add(TenantSetting(tenant_id="t1", setting_key="governance_alerts_channel",
                             setting_value="discord:channel-99"))
        db.commit()
        _make_hitl(db)
        gov = ContactGovernance(db_session=db)
        hitl = db.query(HITLAction).first()
        adapter = MagicMock()
        adapter.send_approval_request = AsyncMock(return_value=True)
        with patch("core.communication_service.communication_service") as comm:
            comm.get_adapter.return_value = adapter
            await gov._notify_governance_channel(db, hitl)
        comm.get_adapter.assert_called_once_with("discord")
        adapter.send_approval_request.assert_awaited_once_with(
            target_id="channel-99", action_id=hitl.id,
            details={"action_type": hitl.action_type, "reason": hitl.reason, "params": hitl.params},
            priority=hitl.priority,
        )
        assert hitl.notified_channel_id == "discord:channel-99"

    @pytest.mark.asyncio
    async def test_send_failure_does_not_crash(self, db):
        _make_workspace(db)
        db.add(TenantSetting(tenant_id="t1", setting_key="governance_alerts_channel",
                             setting_value="slack:C1"))
        db.commit()
        _make_hitl(db)
        gov = ContactGovernance(db_session=db)
        hitl = db.query(HITLAction).first()
        adapter = MagicMock()
        adapter.send_approval_request = AsyncMock(return_value=False)
        with patch("core.communication_service.communication_service") as comm:
            comm.get_adapter.return_value = adapter
            await gov._notify_governance_channel(db, hitl)
        assert hitl.notified_channel_id is None

    @pytest.mark.asyncio
    async def test_missing_adapter_does_not_crash(self, db):
        """BUG W82-4: get_adapter() returning None crashed request_approval
        with AttributeError AFTER the HITL row was committed — the caller saw
        a 500 even though the approval record exists."""
        _make_workspace(db)
        db.add(TenantSetting(tenant_id="t1", setting_key="governance_alerts_channel",
                             setting_value="slack:C1"))
        db.commit()
        gov = ContactGovernance(db_session=db)
        with patch("core.communication_service.communication_service") as comm:
            comm.get_adapter.return_value = None
            hitl_id = await gov.request_approval(
                "ws-1", "send_message", "email",
                {"tenant_id": "t1", "priority": "HIGH"}, "r"
            )
        assert db.query(HITLAction).filter(HITLAction.id == hitl_id).first() is not None

    @pytest.mark.asyncio
    async def test_adapter_send_raises_does_not_crash(self, db):
        _make_workspace(db)
        db.add(TenantSetting(tenant_id="t1", setting_key="governance_alerts_channel",
                             setting_value="slack:C1"))
        db.commit()
        _make_hitl(db)
        gov = ContactGovernance(db_session=db)
        hitl = db.query(HITLAction).first()
        adapter = MagicMock()
        adapter.send_approval_request = AsyncMock(side_effect=RuntimeError("slack down"))
        with patch("core.communication_service.communication_service") as comm:
            comm.get_adapter.return_value = adapter
            await gov._notify_governance_channel(db, hitl)
        assert hitl.notified_channel_id is None


class TestSingleton:
    def test_module_singleton(self):
        assert isinstance(contact_governance, ContactGovernance)
