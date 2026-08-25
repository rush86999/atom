"""Round 81b — journey follow-up gap closure (continuation of R81).

- G6: ``atom_main`` was never persisted anywhere — every meta-agent
  ``record_outcome("atom_main")`` was a silent no-op (learning loop dead) and
  governance lookups for the id returned "Agent not found". Fix: idempotent
  get-or-create at execute() start.
- G7: per-turn fact extraction (sync_turn hook) fired only in the meta-agent
  loop + chat orchestrator; specialty agents running via GenericAgent never
  extracted durable facts. Fix: mirror the meta-agent's session-end digest
  pass, flag-gated + fire-and-forget.
- G8: ``_check_hitl_policy`` catch-all swallowed its own security raises
  (missing workspace/tenant ValueError) AND every other DB error into
  ``return None`` = silently ALLOW risky external comms. Fix: fail closed.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus


# ============================================================================
# G6 — atom_main registry persistence
# ============================================================================


class TestAtomMainPersistence:
    def _session(self):
        import sqlalchemy as sa
        from sqlalchemy.orm import sessionmaker

        engine = sa.create_engine("sqlite://")
        AgentRegistry.__table__.create(engine)
        return sessionmaker(bind=engine)()

    def test_creates_row_when_absent(self):
        from core.atom_meta_agent import ensure_atom_registry_persisted

        db = self._session()
        row = ensure_atom_registry_persisted(db)
        assert row.id == "atom_main"
        assert row.status == AgentStatus.AUTONOMOUS.value
        # actually persisted
        assert (
            db.query(AgentRegistry).filter(AgentRegistry.id == "atom_main").first()
            is not None
        )

    def test_returns_existing_row(self):
        from core.atom_meta_agent import ensure_atom_registry_persisted

        db = self._session()
        first = ensure_atom_registry_persisted(db)
        second = ensure_atom_registry_persisted(db)
        assert first.id == second.id == "atom_main"
        assert db.query(AgentRegistry).count() == 1

    def test_execute_wiring_pinned(self):
        """The ReAct body (execute_unaudited; R84 audit bracket wrapper
        delegates to it) must ensure the row exists before governance/outcome
        use."""
        import inspect

        from core import atom_meta_agent

        src = inspect.getsource(atom_meta_agent.AtomMetaAgent.execute_unaudited)
        assert "ensure_atom_registry_persisted" in src


# ============================================================================
# G7 — turn-fact extraction parity in GenericAgent
# ============================================================================


def _harness_patches():
    mock_world_model = AsyncMock()
    mock_world_model.recall_experiences.return_value = {}
    mock_reflection = AsyncMock()
    mock_reflection.generate_critique = AsyncMock(return_value=None)
    mock_reflection.get_relevant_critiques = AsyncMock(return_value=[])

    async def mock_generate(*args, **kwargs):
        resp = MagicMock()
        resp.thought = "thinking"
        resp.action = None
        resp.final_answer = "all done"
        return resp

    mock_llm = AsyncMock()
    mock_llm.generate_structured = mock_generate
    handler = MagicMock()
    handler.analyze_query_complexity.return_value = MagicMock(value="simple")
    mock_llm._get_handler = MagicMock(return_value=handler)
    mock_mcp = AsyncMock()
    mock_mcp.get_all_tools.return_value = []
    return mock_world_model, mock_reflection, mock_llm, mock_mcp


def _make_agent_model():
    return AgentRegistry(
        id="agent-tf-1",
        name="TF Agent",
        type="assistant",
        module_path="agents.assistant",
        class_name="AssistantAgent",
        category="general",
        configuration={"max_steps": 2},
    )


class TestGenericAgentTurnFacts:
    @pytest.mark.asyncio
    async def test_session_end_extraction_fires(self):
        """A completed ReAct run extracts durable facts (sync_turn parity)."""
        from core.generic_agent import GenericAgent

        mw, mr, ml, mmcp = _harness_patches()
        extractor = MagicMock()
        extractor.extract_from_turn = AsyncMock(return_value=None)

        budget_patch = patch.object(
            GenericAgent,
            "_check_budget_before_react",
            new=AsyncMock(return_value={"allowed": True, "reason": "ok"}),
        )
        with patch("core.generic_agent.WorldModelService", return_value=mw), \
             patch("core.generic_agent.ReflectionService", return_value=mr), \
             patch("core.generic_agent.CanvasSummaryService"), \
             patch("core.generic_agent.mcp_service", mmcp), \
             patch("core.generic_agent.LLMService", return_value=ml), \
             patch("core.generic_agent.get_db_session"), \
             patch("core.generic_agent.AgentGovernanceService") as gov_cls, \
             budget_patch, \
             patch("core.turn_fact_extractor.TURN_FACT_EXTRACTION_ENABLED", True), \
             patch(
                 "core.turn_fact_extractor.get_turn_fact_extractor",
                 return_value=extractor,
             ) as get_ext:
            gov_cls.return_value.record_outcome = AsyncMock(return_value=None)
            agent = GenericAgent(_make_agent_model())
            result = await agent.execute(
                "Remember-worthy task", context={"session_id": "s-1"}
            )
            assert result["status"] == "success"
            # extraction dispatched (create_task) — wait for it
            import asyncio as _aio

            pending = list(getattr(GenericAgent, "_pending_extraction_tasks", set()))
            if pending:
                await _aio.gather(*pending, return_exceptions=True)
            get_ext.assert_called_once()

    @pytest.mark.asyncio
    async def test_extraction_disabled_skips(self):
        from core.generic_agent import GenericAgent

        mw, mr, ml, mmcp = _harness_patches()
        extractor = MagicMock()
        extractor.extract_from_turn = AsyncMock(return_value=None)

        budget_patch = patch.object(
            GenericAgent,
            "_check_budget_before_react",
            new=AsyncMock(return_value={"allowed": True, "reason": "ok"}),
        )
        with patch("core.generic_agent.WorldModelService", return_value=mw), \
             patch("core.generic_agent.ReflectionService", return_value=mr), \
             patch("core.generic_agent.CanvasSummaryService"), \
             patch("core.generic_agent.mcp_service", mmcp), \
             patch("core.generic_agent.LLMService", return_value=ml), \
             patch("core.generic_agent.get_db_session"), \
             patch("core.generic_agent.AgentGovernanceService") as gov_cls, \
             budget_patch, \
             patch("core.turn_fact_extractor.TURN_FACT_EXTRACTION_ENABLED", False), \
             patch(
                 "core.turn_fact_extractor.get_turn_fact_extractor",
                 return_value=extractor,
             ) as get_ext:
            gov_cls.return_value.record_outcome = AsyncMock(return_value=None)
            agent = GenericAgent(_make_agent_model())
            await agent.execute("Task")
            get_ext.assert_not_called()


# ============================================================================
# G8 — HITL policy fail-closed
# ============================================================================


class TestHitlPolicyFailClosed:
    def _svc(self):
        from integrations.mcp_service import MCPService

        return MCPService()

    @pytest.mark.asyncio
    async def test_db_failure_blocks_risky_tool(self):
        svc = self._svc()
        with patch(
            "core.database.SessionLocal",
            side_effect=RuntimeError("db down"),
        ):
            result = await svc._check_hitl_policy(
                "ws-1", "send_email", {"to": "x@y.z"}, {"agent_id": "a1"}
            )
        # Previously returned None (= proceed) on ANY exception — fail-open.
        assert result is not None
        assert result.get("blocked_by") == "hitl_policy_error"
        assert result.get("requires_approval") is True

    @pytest.mark.asyncio
    async def test_missing_workspace_blocks_not_allows(self):
        """The security raises (workspace/tenant missing) were swallowed by the
        same catch-all into allow — they must block."""
        svc = self._svc()
        fake_db = MagicMock(spec=Session)
        fake_db.query.return_value.filter.return_value.first = Mock(
            return_value=None
        )
        cm = MagicMock()
        cm.__enter__.return_value = fake_db
        cm.__exit__.return_value = False
        with patch("core.database.SessionLocal", return_value=cm):
            result = await svc._check_hitl_policy(
                "ghost-ws", "send_message", {"target": "c"}, {}
            )
        assert result is not None
        assert result.get("blocked_by") == "hitl_policy_error"

    @pytest.mark.asyncio
    async def test_low_risk_tool_still_allowed_on_error_path_absence(self):
        """Non-risky tool with healthy policy path still returns None (allow).
        Uses a workspace/tenant present with no HITL requirement."""
        from core.models import Tenant as _Tenant, Workspace as _Workspace

        svc = self._svc()
        tenant = Mock()
        tenant.metadata_json = {"governance": {"require_hitl_external": False}}
        workspace = Mock()
        workspace.tenant_id = "t1"

        ws_q, tn_q = MagicMock(), MagicMock()
        ws_q.filter.return_value.first.return_value = workspace
        tn_q.filter.return_value.first.return_value = tenant
        model_map = {_Workspace: ws_q, _Tenant: tn_q}

        fake_db = MagicMock(spec=Session)
        fake_db.query = Mock(side_effect=lambda m, *a, **k: model_map[m])
        cm = MagicMock()
        cm.__enter__.return_value = fake_db
        cm.__exit__.return_value = False
        with patch("core.database.SessionLocal", return_value=cm):
            result = await svc._check_hitl_policy(
                "ws-ok", "search_contacts", {}, {}
            )
        assert result is None


# ============================================================================
# G9 — GenericAgent stamps run identity + tier for P2/P9 gates
# ============================================================================


class TestDispatchContextStamping:
    """Both the P2 capability gate and the P9 sandbox gate return None ("no
    policy in scope") without run_id/execution_id/tier_at_issuance — so every
    specialty-agent tool call previously ran ungated."""

    def _run(self, status="intern", db_broken=False):
        import asyncio as _aio

        from core.generic_agent import GenericAgent

        mw, mr, ml, mmcp = _harness_patches()
        agent_model = _make_agent_model()

        def _gds(*a, **k):
            if db_broken:
                raise RuntimeError("nope")
            db = MagicMock()
            row = MagicMock()
            row.status = status
            db.query.return_value.filter.return_value.first.return_value = row
            cm = MagicMock()
            cm.__enter__.return_value = db
            cm.__exit__.return_value = False
            return cm

        budget_patch = patch.object(
            GenericAgent,
            "_check_budget_before_react",
            new=AsyncMock(return_value={"allowed": True, "reason": "ok"}),
        )
        ctx = {"session_id": "s-9"}
        with patch("core.generic_agent.WorldModelService", return_value=mw), \
             patch("core.generic_agent.ReflectionService", return_value=mr), \
             patch("core.generic_agent.CanvasSummaryService"), \
             patch("core.generic_agent.mcp_service", mmcp), \
             patch("core.generic_agent.LLMService", return_value=ml), \
             patch("core.generic_agent.get_db_session"), \
             patch("core.generic_agent.AgentGovernanceService") as gov_cls, \
             patch("core.generic_agent.trigger_episode_creation"), \
             patch("core.turn_fact_extractor.TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.database.get_db_session", side_effect=_gds), \
             budget_patch:
            gov_cls.return_value.record_outcome = AsyncMock(return_value=None)
            agent = GenericAgent(agent_model)
            result = _aio.run(agent.execute("Task", context=ctx))
        return ctx, result

    def test_stamps_identity_and_tier(self):
        ctx, result = self._run(status="supervised")
        assert result["status"] == "success"
        assert ctx["agent_id"] == "agent-tf-1"
        assert ctx["run_id"]
        assert ctx["run_id"] == ctx["execution_id"]
        assert ctx["tier_at_issuance"] == "supervised"

    def test_tier_falls_back_to_student_on_db_error(self):
        ctx, result = self._run(db_broken=True)
        assert result["status"] == "success"
        assert ctx["tier_at_issuance"] == "student"

    def test_caller_values_authoritative(self):
        import asyncio as _aio

        from core.generic_agent import GenericAgent

        mw, mr, ml, mmcp = _harness_patches()
        agent_model = _make_agent_model()
        budget_patch = patch.object(
            GenericAgent,
            "_check_budget_before_react",
            new=AsyncMock(return_value={"allowed": True, "reason": "ok"}),
        )
        ctx = {
            "session_id": "s-9",
            "run_id": "caller-run",
            "tier_at_issuance": "autonomous",
        }
        with patch("core.generic_agent.WorldModelService", return_value=mw), \
             patch("core.generic_agent.ReflectionService", return_value=mr), \
             patch("core.generic_agent.CanvasSummaryService"), \
             patch("core.generic_agent.mcp_service", mmcp), \
             patch("core.generic_agent.LLMService", return_value=ml), \
             patch("core.generic_agent.get_db_session"), \
             patch("core.generic_agent.AgentGovernanceService") as gov_cls, \
             patch("core.generic_agent.trigger_episode_creation"), \
             patch("core.turn_fact_extractor.TURN_FACT_EXTRACTION_ENABLED", False), \
             budget_patch:
            gov_cls.return_value.record_outcome = AsyncMock(return_value=None)
            agent = GenericAgent(agent_model)
            _aio.run(agent.execute("Task", context=ctx))
        assert ctx["run_id"] == "caller-run"
        assert ctx["tier_at_issuance"] == "autonomous"


# ============================================================================
# G10 - reasoning-step feedback actually reaches the confidence update
# ============================================================================


class TestReasoningFeedbackConfidence:
    """_apply_feedback_to_agent called _update_confidence_score with a
    nonexistent `is_positive` kwarg (and user_id positionally as `positive`)
    - every approve/reject raised TypeError that the except swallowed, so
    step-level user feedback never moved agent confidence."""

    def _feedback(self, fb_type):
        fb = MagicMock()
        fb.feedback_type = fb_type
        fb.user_id = "user-1"
        return fb

    def _step(self):
        step = MagicMock()
        step.agent_id = "agent-1"
        return step

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fb_type,expected_positive", [
        ("APPROVE", True),
        ("REJECT", False),
    ])
    async def test_approve_and_reject_update_confidence(self, fb_type, expected_positive):
        from core.reasoning_chain import FeedbackType as FT, ReasoningTracker

        chain = ReasoningTracker.__new__(ReasoningTracker)
        db_cm = MagicMock()
        db = MagicMock()
        db_cm.__enter__.return_value = db
        db_cm.__exit__.return_value = False

        with patch("core.database.get_db_session", return_value=db_cm), \
             patch("core.agent_governance_service.AgentGovernanceService") as gov_cls:
            gov_cls.return_value._update_confidence_score = Mock()
            await ReasoningTracker._apply_feedback_to_agent(
                chain, self._feedback(getattr(FT, fb_type)), self._step()
            )
            gov_cls.return_value._update_confidence_score.assert_called_once_with(
                "agent-1", positive=expected_positive, impact_level="high"
            )

    @pytest.mark.asyncio
    async def test_no_agent_id_is_noop(self):
        from core.reasoning_chain import FeedbackType as FT, ReasoningTracker

        chain = ReasoningTracker.__new__(ReasoningTracker)
        step = MagicMock()
        step.agent_id = None
        with patch("core.database.get_db_session") as gds:
            await ReasoningTracker._apply_feedback_to_agent(
                chain, self._feedback(FT.APPROVE), step
            )
            gds.assert_not_called()


# ============================================================================
# G11 - HITL auto-approve compares the tier NAME, not a numeric property
# ============================================================================


class TestHitlAutoApprove:
    """AgentRegistry.maturity_level is a property returning the status STRING;
    `agent.maturity_level >= 5` always raised TypeError -> old code silently
    allowed (auto-approve dead), R81b fail-closed turned that into a hard
    block. Autonomous agents in allow-listing tenants must reach the
    auto-approve path, and non-autonomous ones must reach intervention."""

    def _svc(self):
        from integrations.mcp_service import MCPService

        return MCPService()

    def _hitl_env(self, agent_status):
        from core.models import AgentRegistry as _AR, Tenant as _T, \
            User as _U, Workspace as _W

        tenant = MagicMock()
        tenant.metadata_json = {"governance": {
            "require_hitl_external": True,
            "allow_autonomous_external": True,
        }}
        workspace = MagicMock()
        workspace.tenant_id = "t1"
        user = MagicMock()
        user.tenant_id = "t1"
        user.notification_preferences = {}
        agent = MagicMock()
        # Realistic: property returns the STATUS STRING (no numeric attr).
        agent.status = agent_status

        model_map = {
            _W: _q_ret_chaining(workspace),
            _T: _q_ret_chaining(tenant),
            _U: _q_ret_chaining(user),
            _AR: _q_ret_chaining(agent),
        }
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query = MagicMock(side_effect=lambda m, *a, **k: model_map[m])
        return db

    @pytest.mark.asyncio
    async def test_autonomous_agent_auto_approved(self):
        from integrations.mcp_service import MCPService
        from core.models import AgentRegistry as _AR

        svc = self._svc()
        db = self._hitl_env("autonomous")
        with patch("core.database.SessionLocal", return_value=db), \
             patch(
                 "core.intervention_service.intervention_service.request_intervention",
                 new=AsyncMock(side_effect=AssertionError("must not intercept")),
             ):
            result = await svc._check_hitl_policy(
                "ws1", "send_email", {"to": "x@y.z"},
                {"user_id": "u1", "agent_id": "ag1"},
            )
        assert result is None  # auto-approved -> proceed

    @pytest.mark.asyncio
    async def test_supervised_agent_goes_to_intervention(self):
        from integrations.mcp_service import MCPService

        svc = self._svc()
        db = self._hitl_env("supervised")
        intervention = AsyncMock(return_value={"paused": True})
        with patch("core.database.SessionLocal", return_value=db), \
             patch(
                 "core.intervention_service.intervention_service.request_intervention",
                 new=intervention,
             ):
            result = await svc._check_hitl_policy(
                "ws1", "send_email", {"to": "x@y.z"},
                {"user_id": "u1", "agent_id": "ag1"},
            )
        assert result == {"paused": True}
        intervention.assert_awaited_once()


def _q_ret_chaining(value):
    """Query mock surviving the production two-stage filter + first()."""
    f = MagicMock()
    f.first.return_value = value
    f.filter.return_value = f
    q = MagicMock()
    q.filter.return_value = f
    return q


# ============================================================================
# G12 - approved-proposal executions persist as episodes
# ============================================================================


class TestProposalExecutionEpisodes:
    """ProposalService persisted AgentExecution rows for INTERN-approved
    actions but never created episodes — EpisodeService.create_episode_
    _from_execution had zero production callers, so supervised state changes
    starved the episode-based graduation criteria."""

    def _svc(self):
        from core.proposal_service import ProposalService

        return ProposalService(MagicMock(spec=Session))

    def test_helper_maps_completed_to_success(self):
        svc = self._svc()
        execution = MagicMock()
        execution.id = "exec-1"
        execution.status = "completed"
        proposal = MagicMock()
        proposal.id = "pr-1"
        with patch("core.episode_service.EpisodeService") as es_cls:
            svc._record_execution_episode(execution, proposal, "browser_automate")
            es_cls.return_value.create_episode_from_execution.assert_called_once()
            _, kwargs = es_cls.return_value.create_episode_from_execution.call_args
            assert kwargs["execution_id"] == "exec-1"
            assert kwargs["success"] is True
            assert kwargs["outcome"] == "completed"
            assert kwargs["metadata"]["proposal_id"] == "pr-1"

    def test_helper_maps_failed_to_failure(self):
        svc = self._svc()
        execution = MagicMock()
        execution.id = "exec-2"
        execution.status = "failed"
        with patch("core.episode_service.EpisodeService") as es_cls:
            svc._record_execution_episode(execution, MagicMock(id="pr-2"), "send_email")
            _, kwargs = es_cls.return_value.create_episode_from_execution.call_args
            assert kwargs["success"] is False

    def test_helper_never_raises(self):
        svc = self._svc()
        with patch("core.episode_service.EpisodeService", side_effect=RuntimeError("x")):
            svc._record_execution_episode(
                MagicMock(id="e", status="completed"), MagicMock(id="p"), "t"
            )  # must not raise

    def test_all_six_executors_wire_episodes(self):
        import inspect

        from core.proposal_service import ProposalService

        src = inspect.getsource(ProposalService)
        assert src.count("_record_execution_episode(") >= 7  # 6 sites + helper def


# ============================================================================
# G13 - non-session GenericAgent runs persist execution + episode
# ============================================================================


class TestNonSessionExecutionPersistence:
    """Scheduler / direct-execute runs left no AgentExecution row and no
    episode — only chat-linked runs were remembered. Proposal-owned runs must
    NOT double-record (their executors persist their own)."""

    def _run(self, ctx_extra=None):
        import asyncio as _aio

        from core.generic_agent import GenericAgent

        mw, mr, ml, mmcp = _harness_patches()
        agent_model = _make_agent_model()
        budget_patch = patch.object(
            GenericAgent,
            "_check_budget_before_react",
            new=AsyncMock(return_value={"allowed": True, "reason": "ok"}),
        )
        db = MagicMock()

        def _gds(*a, **k):
            cm = MagicMock()
            cm.__enter__.return_value = db
            cm.__exit__.return_value = False
            return cm

        added = []
        db.add.side_effect = added.append
        ctx = dict(ctx_extra or {})
        with patch("core.generic_agent.WorldModelService", return_value=mw), \
             patch("core.generic_agent.ReflectionService", return_value=mr), \
             patch("core.generic_agent.CanvasSummaryService"), \
             patch("core.generic_agent.mcp_service", mmcp), \
             patch("core.generic_agent.LLMService", return_value=ml), \
             patch("core.generic_agent.get_db_session", side_effect=_gds), \
             patch("core.generic_agent.AgentGovernanceService") as gov_cls, \
             patch("core.generic_agent.trigger_episode_creation") as trig, \
             patch("core.episode_service.EpisodeService") as es_cls, \
             budget_patch:
            gov_cls.return_value.record_outcome = AsyncMock(return_value=None)
            agent = GenericAgent(agent_model)
            result = _aio.run(agent.execute("Scheduled task", context=ctx))
        return {
            "result": result,
            "added": added,
            "episode_calls": es_cls.return_value.create_episode_from_execution,
            "trigger": trig,
        }

    def test_non_session_run_persists_execution_and_episode(self):
        out = self._run()
        assert out["result"]["status"] == "success"
        exec_rows = [a for a in out["added"] if type(a).__name__ == "AgentExecution"]
        assert len(exec_rows) == 1
        assert exec_rows[0].status == "success"
        assert exec_rows[0].id  # run_id-based id present
        out["episode_calls"].assert_called_once()
        assert out["episode_calls"].call_args.kwargs["success"] is True

    def test_proposal_owned_run_skips_double_record(self):
        out = self._run({"proposal_id": "pr-9", "execution_id": "exec-9"})
        assert out["result"]["status"] == "success"
        exec_rows = [a for a in out["added"] if type(a).__name__ == "AgentExecution"]
        assert exec_rows == []
        out["episode_calls"].assert_not_called()
