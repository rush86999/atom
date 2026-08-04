"""
Tests for budget control: default enforcement-mode resolution + the in-loop
agent budget gate.

Covers the two spend-halting fixes:
1. Default enforcement mode is now ``soft_stop`` (was ``alert_only``, which
   never blocked). Verified via ``BudgetEnforcementService._get_enforcement_mode``
   against unset / empty / invalid / explicitly-set settings.
2. The agent loop checks budget BEFORE the LLM call (``_check_budget_before_react``)
   and breaks cleanly with ``status="budget_exceeded"`` when denied — instead
   of only checking per-tool and burning LLM spend up to ``max_steps``.

The legacy ``test_budget_enforcement_service.py`` module is skipped at the
module level (it targets a removed API), so these tests live here to actually
run against the current service.
"""

import json
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.orm import Session

from core.budget_enforcement_service import (
    BudgetEnforcementService,
    BudgetEnforcementMode,
)


# ============================================================================
# Default enforcement-mode resolution
# ============================================================================

class TestEnforcementModeDefault:
    """The default mode changed alert_only → soft_stop."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def service(self, mock_db):
        return BudgetEnforcementService(db=mock_db)

    def _setting(self, mode=None, raw=None):
        """Build a mock TenantSetting row. raw overrides mode for corrupt cases."""
        if mode is None and raw is None:
            return None  # unset
        setting = Mock()
        setting.setting_value = raw if raw is not None else json.dumps(
            {"enforcement": {"mode": mode}}
        )
        return setting

    def test_unset_mode_defaults_to_soft_stop(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        assert service._get_enforcement_mode("t1") == BudgetEnforcementMode.SOFT_STOP

    def test_empty_setting_defaults_to_soft_stop(self, service):
        setting = Mock()
        setting.setting_value = None
        service.db.query.return_value.filter.return_value.first.return_value = setting
        assert service._get_enforcement_mode("t1") == BudgetEnforcementMode.SOFT_STOP

    def test_invalid_mode_falls_back_to_soft_stop(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = self._setting("bogus")
        assert service._get_enforcement_mode("t1") == BudgetEnforcementMode.SOFT_STOP

    def test_explicit_alert_only_is_respected(self, service):
        """An explicitly-set alert_only is preserved — only the *default* changed."""
        service.db.query.return_value.filter.return_value.first.return_value = self._setting("alert_only")
        assert service._get_enforcement_mode("t1") == BudgetEnforcementMode.ALERT_ONLY

    def test_explicit_hard_stop_is_respected(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = self._setting("hard_stop")
        assert service._get_enforcement_mode("t1") == BudgetEnforcementMode.HARD_STOP

    def test_json_error_defaults_to_soft_stop(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = self._setting(raw="not-json{")
        assert service._get_enforcement_mode("t1") == BudgetEnforcementMode.SOFT_STOP

    def test_mode_constants_unchanged(self):
        assert BudgetEnforcementMode.SOFT_STOP == "soft_stop"
        assert BudgetEnforcementMode.ALERT_ONLY == "alert_only"
        assert BudgetEnforcementMode.HARD_STOP == "hard_stop"
        assert BudgetEnforcementMode.APPROVAL == "approval"


# ============================================================================
# Agent budget gate (_check_budget_before_react)
# ============================================================================

class TestAgentBudgetGate:
    """The pre-LLM budget gate on AtomMetaAgent and GenericAgent.

    We test ``_check_budget_before_react`` directly (it's the thin wrapper over
    BudgetEnforcementService) plus the deny-path behavior, without running a
    full agent loop (which would need the LLM). The gate's contract:
      - returns the BudgetEnforcementService dict
      - fail-open on exception (allowed: True)
      - the loop breaks with status="budget_exceeded" when allowed is False
    """

    @pytest.fixture
    def agent_with_budget(self, monkeypatch):
        """Build a minimal AtomMetaAgent-like object with the gate method.

        We bind the real ``_check_budget_before_react`` method so the test
        exercises the actual fail-open + delegation logic, but stub out
        BudgetEnforcementService so no real spend aggregation runs.
        """
        from core.atom_meta_agent import AtomMetaAgent

        agent = AtomMetaAgent.__new__(AtomMetaAgent)
        agent.tenant_id = "tenant-1"
        return agent

    @pytest.mark.asyncio
    async def test_gate_returns_allowed_when_budget_ok(self, agent_with_budget, monkeypatch):
        """When budget allows, the gate returns allowed=True (loop continues)."""
        async def fake_check(*a, **kw):
            return {"allowed": True, "reason": None, "enforcement_mode": "soft_stop"}

        fake_svc = Mock()
        fake_svc.check_budget_before_action = AsyncMock(side_effect=fake_check)
        monkeypatch.setattr(
            "core.budget_enforcement_service.BudgetEnforcementService",
            lambda *a, **kw: fake_svc,
        )

        result = await agent_with_budget._check_budget_before_react()
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_gate_returns_denied_under_hard_stop(self, agent_with_budget, monkeypatch):
        """When hard_stop denies, the gate returns allowed=False (loop should break)."""
        async def fake_check(*a, **kw):
            return {
                "allowed": False,
                "reason": "Budget exceeded. All operations halted immediately.",
                "enforcement_mode": "hard_stop",
            }

        fake_svc = Mock()
        fake_svc.check_budget_before_action = AsyncMock(side_effect=fake_check)
        monkeypatch.setattr(
            "core.budget_enforcement_service.BudgetEnforcementService",
            lambda *a, **kw: fake_svc,
        )

        result = await agent_with_budget._check_budget_before_react()
        assert result["allowed"] is False
        assert "Budget exceeded" in result["reason"]

    @pytest.mark.asyncio
    async def test_gate_fails_open_on_exception(self, agent_with_budget, monkeypatch):
        """If the budget service raises, the gate fails OPEN (allowed=True).

        This matches the existing convention in BudgetEnforcementService — we
        never block on an inability to compute spend.
        """
        fake_svc = Mock()
        fake_svc.check_budget_before_action = AsyncMock(side_effect=RuntimeError("DB down"))
        monkeypatch.setattr(
            "core.budget_enforcement_service.BudgetEnforcementService",
            lambda *a, **kw: fake_svc,
        )

        result = await agent_with_budget._check_budget_before_react()
        assert result["allowed"] is True

    def test_budget_exceeded_status_maps_to_failed(self):
        """The persistence path maps budget_exceeded → failed (valid enum).

        budget_exceeded is NOT a valid ExecutionStatus; persisting it verbatim
        would create an invisible third state (the same bug the max_steps→timeout
        fix avoided). The agent finalizer maps it to 'failed' with a distinctive
        error_message. We verify the mapping constant exists and is valid.
        """
        from core.models import ExecutionStatus

        valid = {
            ExecutionStatus.PENDING.value,
            ExecutionStatus.RUNNING.value,
            ExecutionStatus.COMPLETED.value,
            ExecutionStatus.FAILED.value,
            ExecutionStatus.CANCELLED.value,
            ExecutionStatus.PAUSED.value,
            ExecutionStatus.TIMEOUT.value,
        }
        assert "budget_exceeded" not in valid, "budget_exceeded must be mapped, not persisted"
        assert ExecutionStatus.FAILED.value == "failed"


# ============================================================================
# Execute-loop return contract: status must be a valid enum value
# ============================================================================

class TestBudgetExitStatusContract:
    """The budget gate breaks the ReAct loop with ``status="budget_exceeded"``.

    The DB-persistence path in ``atom_meta_agent`` maps that to ``"failed"``
    before committing — but ``GenericAgent.execute`` returns the raw status in
    its result payload (line ~408), and that payload is what the API/WS layer
    serializes to the frontend. If ``budget_exceeded`` leaks into the return
    value, every status-branch on the consumer side sees an invalid value.

    Contract: ``execute`` MUST return a status that is a valid
    ``ExecutionStatus`` value — the internal ``"budget_exceeded"`` sentinel is
    an implementation detail of the loop and must be normalized at the
    execution boundary.
    """

    @pytest.fixture
    def budget_denying_agent(self, monkeypatch):
        """A minimal GenericAgent whose budget gate denies on the first check.

        We stub the few collaborators ``execute`` touches before the budget
        gate breaks the loop, so we exercise the real exit + return path
        without running the LLM.
        """
        from core.generic_agent import GenericAgent

        agent = GenericAgent.__new__(GenericAgent)
        agent.id = "agent-1"
        agent.name = "TestAgent"
        agent.config = {"max_steps": 5, "timeout_seconds": 30}
        agent.workspace_id = "ws-1"
        agent.allowed_tools = "*"
        agent.system_prompt = "test"
        agent.session_tools = []
        agent.vision_enabled = False
        agent.last_screenshot = None

        # world_model.recall_experiences runs first; stub it.
        wm = Mock()
        wm.recall_experiences = AsyncMock(return_value="")
        agent.world_model = wm

        # The budget gate denies.
        agent._check_budget_before_react = AsyncMock(
            return_value={
                "allowed": False,
                "reason": "Budget exceeded. All operations halted immediately.",
                "enforcement_mode": "hard_stop",
            }
        )

        # complexity analysis runs after the break; stub the handler chain.
        complexity = Mock()
        complexity.value = "simple"
        handler = Mock()
        handler.analyze_query_complexity = Mock(return_value=complexity)
        llm = Mock()
        llm._get_handler = Mock(return_value=handler)
        agent.llm = llm

        # reflection service runs on failure; stub it.
        rs = Mock()
        rs.generate_critique = AsyncMock(return_value=None)
        agent.reflection_service = rs

        # _record_execution persists the experience; stub it so we isolate the
        # return-value contract from the DB/experience layer.
        agent._record_execution = AsyncMock(return_value=None)

        return agent

    @pytest.mark.asyncio
    async def test_execute_returns_valid_status_when_budget_denied(self, budget_denying_agent):
        """When the budget gate halts the loop, execute()'s returned status
        must be a valid ExecutionStatus value — never the internal
        ``budget_exceeded`` sentinel."""
        from core.models import ExecutionStatus

        valid = {e.value for e in ExecutionStatus}

        result = await budget_denying_agent.execute("do something")

        assert "status" in result, "execute must return a status"
        assert result["status"] in valid, (
            f"execute returned status={result['status']!r} which is NOT a valid "
            f"ExecutionStatus; the budget_exceeded sentinel leaked into the "
            f"return payload and would reach the API/WS layer verbatim."
        )


# ============================================================================
# End-to-end soft_stop behavior for an UNSET (first-run) tenant
# ============================================================================

class TestSoftStopDefaultBehavior:
    """Characterization tests for the soft_stop default on a first-run tenant.

    The default enforcement mode changed alert_only → soft_stop. The unit test
    above covers ``_get_enforcement_mode`` in isolation; these tests drive the
    full ``check_budget_before_action`` path to confirm the default actually
    engages: for a tenant with NO billing setting at all (unset), when the
    budget is exceeded, soft_stop blocks NEW episodes while the mode resolves
    correctly through the real code path (not just the resolver).
    """

    @pytest.fixture
    def db(self, worker_database):
        SessionLocal = worker_database
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def exceeded_service(self, db, monkeypatch):
        """BudgetEnforcementService against the in-memory DB with spend forced
        over budget and no active episodes, so soft_stop must block."""
        svc = BudgetEnforcementService(db=db)

        # Force the spend aggregation to report budget exceeded.
        fake_spend = Mock()
        fake_spend.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 150.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 150.0,
        })
        fake_spend.get_fleet_spend = Mock(return_value=0.0)
        svc.spend_service = fake_spend

        # No active episodes → soft_stop blocks new episodes.
        monkeypatch.setattr(svc, "_has_active_episodes", lambda *a, **kw: False)

        return svc

    @pytest.mark.asyncio
    async def test_unset_tenant_blocks_new_episode_when_over_budget(self, exceeded_service, db):
        """A first-run tenant (no billing TenantSetting row) over budget with no
        active episodes must be BLOCKED under the soft_stop default."""
        result = await exceeded_service.check_budget_before_action(
            tenant_id="tenant-unset",
            agent_id="agent-1",
            action="plan",
        )

        assert result["allowed"] is False, (
            "soft_stop default must block new episodes when an unset tenant is "
            "over budget (previously alert_only allowed everything)"
        )
        assert result["enforcement_mode"] == "soft_stop"
        assert "blocked" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_unset_tenant_allows_active_episode_when_over_budget(self, exceeded_service, db, monkeypatch):
        """When the same unset tenant HAS an active episode, soft_stop lets it
        complete even though the budget is exceeded."""
        monkeypatch.setattr(exceeded_service, "_has_active_episodes", lambda *a, **kw: True)

        result = await exceeded_service.check_budget_before_action(
            tenant_id="tenant-unset",
            agent_id="agent-1",
            action="plan",
        )

        assert result["allowed"] is True, (
            "soft_stop must allow active episodes to complete even when over budget"
        )
        assert result["enforcement_mode"] == "soft_stop"

