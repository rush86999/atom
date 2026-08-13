"""
Coverage-push tests for core.fleet_admiral, core.hitl_service,
and core.agent_orchestrator.

Target: >=95% statement coverage STANDALONE (this file alone) per module.

Covers:
- FleetAdmiral: init wiring, lazy RecruitmentIntelligenceService init
  (idempotent + full lazy import path), task analysis (happy + LLM failure
  fallback), recruit_and_execute (success with roster, empty roster, failed
  recruitment -> complete_chain, custom root agent, blackboard updates).
- HITLService: resolve_action (not found, already resolved, resolver missing,
  rejection, approval, URGENT 2FA gating incl. verified_2fa metadata variants),
  _prompt_for_2fa (no channel, malformed channel, slack send), _resume_workflow
  (no callback, invalid callback blocked, callback post success/failure),
  _validate_url (localhost/private ranges/internal hostnames/invalid scheme/
  malformed URL).
- AgentOrchestrator: init defaults, run loop (final answer, sync/async tool
  exec, missing tool, tool error, no action, None decision, max-loops
  exhaustion, reasoning failure), tool description generation, response model.

No LLM spend, no network, no DB writes: all deps are mocked; HITL actions are
in-memory model instances.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.agent_orchestrator import AgentExecutionResponse, AgentOrchestrator
from core.fleet_admiral import FleetAdmiral, TaskAnalysis
from core.hitl_service import HITLService
from core.models import HITLAction, HITLActionStatus, User


# ============================================================================
# FleetAdmiral
# ============================================================================

def _make_admiral(task_analysis=None):
    """Build a FleetAdmiral with a mocked LLM + fleet service (no DB)."""
    llm = Mock()
    llm.generate_structured_response = AsyncMock(return_value=task_analysis)
    fleet_service = Mock()
    with patch("core.fleet_admiral.AgentFleetService", return_value=fleet_service):
        admiral = FleetAdmiral(db=Mock(), llm=llm)
    return admiral, fleet_service, llm


def _analysis(**overrides):
    kwargs = dict(
        complexity="medium",
        required_capabilities=["data_analysis", "reporting"],
        estimated_duration="30 minutes",
        specialist_count=2,
        reasoning="Test reasoning",
    )
    kwargs.update(overrides)
    return TaskAnalysis(**kwargs)


class TestFleetAdmiralInit:
    def test_init_wires_services(self):
        admiral, fleet_service, llm = _make_admiral()
        assert admiral.db is not None
        assert admiral.llm is llm
        assert admiral.fleet_service is fleet_service
        assert admiral.recruitment_intelligence is None

    def test_init_creates_fleet_service_with_db(self):
        db = Mock()
        with patch("core.fleet_admiral.AgentFleetService") as afs:
            admiral = FleetAdmiral(db=db, llm=Mock())
        afs.assert_called_once_with(db)
        assert admiral.fleet_service is afs.return_value


class TestAnalyzeTaskRequirements:
    @pytest.mark.asyncio
    async def test_success_maps_analysis(self):
        admiral, _, _ = _make_admiral(_analysis(
            complexity="high",
            required_capabilities=["a", "b", "c"],
            estimated_duration="2 hours",
            specialist_count=4,
            reasoning="Needs many specialists",
        ))
        result = await admiral.analyze_task_requirements("Do the task", "user-1")
        assert result == {
            "complexity": "high",
            "required_capabilities": ["a", "b", "c"],
            "estimated_duration": "2 hours",
            "specialist_count": 4,
            "reasoning": "Needs many specialists",
        }
        prompt = admiral.llm.generate_structured_response.await_args.kwargs["prompt"]
        assert "Do the task" in prompt
        assert admiral.llm.generate_structured_response.await_args.kwargs["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self):
        admiral, _, _ = _make_admiral()
        admiral.llm.generate_structured_response = AsyncMock(
            side_effect=Exception("LLM service unavailable"))
        result = await admiral.analyze_task_requirements("Do the task", "user-1")
        assert result["complexity"] == "medium"
        assert result["required_capabilities"] == ["general"]
        assert result["estimated_duration"] == "30 minutes"
        assert result["specialist_count"] == 2
        assert "LLM analysis failed" in result["reasoning"]
        assert "LLM service unavailable" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_empty_task_still_analyzed(self):
        admiral, _, _ = _make_admiral(_analysis())
        result = await admiral.analyze_task_requirements("", "user-1")
        assert result["specialist_count"] == 2


class TestInitializeRecruitmentIntelligence:
    @pytest.fixture
    def lazy_patches(self):
        with patch("core.specialist_matcher.SpecialistMatcher"), \
                patch("core.recruitment_analytics_service.RecruitmentAnalyticsService"), \
                patch("analytics.fleet_optimization_service.FleetOptimizationService"), \
                patch("core.agent_governance_service.AgentGovernanceService"), \
                patch("core.fleet_admiral.RecruitmentIntelligenceService") as ris:
            yield ris

    def test_lazy_init_builds_service(self, lazy_patches):
        admiral, fleet_service, llm = _make_admiral()
        admiral._initialize_recruitment_intelligence()
        ris = lazy_patches
        assert admiral.recruitment_intelligence is ris.return_value
        kwargs = ris.call_args.kwargs
        assert kwargs["db"] is admiral.db
        assert kwargs["llm"] is llm
        assert kwargs["fleet_service"] is fleet_service
        assert isinstance(kwargs["specialist_matcher"], Mock)
        assert isinstance(kwargs["analytics"], Mock)
        assert isinstance(kwargs["optimizer"], Mock)
        assert isinstance(kwargs["governance"], Mock)
        assert "budget" not in kwargs

    def test_lazy_init_idempotent(self, lazy_patches):
        admiral, _, _ = _make_admiral()
        admiral._initialize_recruitment_intelligence()
        ris = lazy_patches
        admiral._initialize_recruitment_intelligence()
        ris.assert_called_once()

    def test_init_after_preset_noop(self):
        admiral, _, _ = _make_admiral()
        preset = Mock()
        admiral.recruitment_intelligence = preset
        with patch("core.fleet_admiral.RecruitmentIntelligenceService") as ris:
            admiral._initialize_recruitment_intelligence()
        ris.assert_not_called()
        assert admiral.recruitment_intelligence is preset


class TestRecruitAndExecute:
    @pytest.mark.asyncio
    async def test_success_full_flow(self):
        admiral, fleet_service, llm = _make_admiral(_analysis(specialist_count=2))
        chain = Mock()
        chain.id = "chain-1"
        chain.status = "active"
        fleet_service.initialize_fleet.return_value = chain
        ri = Mock()
        ri.orchestrate_recruitment = AsyncMock(return_value={
            "success": True,
            "recruitment_roster": [
                {"agent_id": "a1", "agent_name": "Alice", "domain": "data",
                 "capability_score": 0.9, "optimization": {"cheap": True}},
                {"agent_id": "a2", "agent_name": "Bob", "domain": "web",
                 "capability_score": 0.8},
            ],
        })
        admiral.recruitment_intelligence = ri
        fleet_service.recruit_member.side_effect = [
            Mock(), Mock(),
        ]
        result = await admiral.recruit_and_execute("Analyze sales", "user-1")
        assert result["chain_id"] == "chain-1"
        assert result["specialists_count"] == 2
        assert result["fleet_status"] == "active"
        assert result["task_analysis"]["specialist_count"] == 2
        assert result["recruitment_roster"][0]["agent_id"] == "a1"
        assert result["specialists"] == [
            {"agent_id": "a1", "agent_name": "Alice", "domain": "data"},
            {"agent_id": "a2", "agent_name": "Bob", "domain": "web"},
        ]
        fleet_service.initialize_fleet.assert_called_once()
        init_kwargs = fleet_service.initialize_fleet.call_args.kwargs
        assert init_kwargs["user_id"] == "user-1"
        assert init_kwargs["root_agent_id"] == "atom_main"
        assert init_kwargs["root_task"] == "Analyze sales"
        assert init_kwargs["initial_metadata"]["recruitment_phase"] == "in_progress"
        ri.orchestrate_recruitment.assert_awaited_once_with(
            goal="Analyze sales", user_id="user-1",
            context={"chain_id": "chain-1"}, max_specialists=2,
            chain_id="chain-1")
        assert fleet_service.recruit_member.call_count == 2
        first_kwargs = fleet_service.recruit_member.call_args_list[0].kwargs
        assert first_kwargs["chain_id"] == "chain-1"
        assert first_kwargs["parent_agent_id"] == "atom_main"
        assert first_kwargs["child_agent_id"] == "a1"
        assert "data: 0.9" in first_kwargs["task_description"]
        assert first_kwargs["context_json"] == {
            "domain": "data", "optimization": {"cheap": True}}
        assert first_kwargs["link_order"] == 0
        assert fleet_service.recruit_member.call_args_list[1].kwargs["link_order"] == 1
        assert fleet_service.recruit_member.call_args_list[1].kwargs["context_json"] == {
            "domain": "web", "optimization": None}
        expected_updates = {
            "task_analysis": result["task_analysis"],
            "recruitment_phase": "complete",
            "specialists_recruited": [
                {"agent_id": "a1", "agent_name": "Alice", "domain": "data"},
                {"agent_id": "a2", "agent_name": "Bob", "domain": "web"},
            ],
        }
        updates = fleet_service.update_blackboard.call_args.kwargs["updates"]
        assert fleet_service.update_blackboard.call_args.kwargs["chain_id"] == "chain-1"
        assert {k: updates[k] for k in expected_updates} == expected_updates
        completed_at = datetime.fromisoformat(updates["recruitment_completed_at"])
        assert abs((datetime.now(timezone.utc) - completed_at).total_seconds()) < 30

    @pytest.mark.asyncio
    async def test_success_empty_roster(self):
        admiral, fleet_service, llm = _make_admiral(_analysis())
        chain = Mock()
        chain.id = "chain-1"
        chain.status = "active"
        fleet_service.initialize_fleet.return_value = chain
        ri = Mock()
        ri.orchestrate_recruitment = AsyncMock(return_value={"success": True})
        admiral.recruitment_intelligence = ri
        result = await admiral.recruit_and_execute("Analyze sales", "user-1")
        assert result["specialists_count"] == 0
        assert result["fleet_status"] == "active"
        assert result["recruitment_roster"] == []
        fleet_service.recruit_member.assert_not_called()
        fleet_service.update_blackboard.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_marks_chain_failed(self):
        admiral, fleet_service, llm = _make_admiral(_analysis())
        chain = Mock()
        chain.id = "chain-1"
        fleet_service.initialize_fleet.return_value = chain
        ri = Mock()
        ri.orchestrate_recruitment = AsyncMock(
            return_value={"success": False, "error": "no specialists found"})
        admiral.recruitment_intelligence = ri
        result = await admiral.recruit_and_execute("Analyze sales", "user-1")
        fleet_service.complete_chain.assert_called_once_with("chain-1", "failed")
        assert result["chain_id"] == "chain-1"
        assert result["specialists_count"] == 0
        assert result["fleet_status"] == "failed"
        assert result["error"] == "no specialists found"
        fleet_service.recruit_member.assert_not_called()
        fleet_service.update_blackboard.assert_not_called()

    @pytest.mark.asyncio
    async def test_custom_root_agent_id(self):
        admiral, fleet_service, llm = _make_admiral(_analysis())
        chain = Mock()
        chain.id = "chain-1"
        chain.status = "active"
        fleet_service.initialize_fleet.return_value = chain
        ri = Mock()
        ri.orchestrate_recruitment = AsyncMock(
            return_value={"success": True,
                          "recruitment_roster": [
                              {"agent_id": "a1", "agent_name": "Alice",
                               "domain": "data"}]})
        admiral.recruitment_intelligence = ri
        result = await admiral.recruit_and_execute(
            "Analyze sales", "user-1", root_agent_id="custom_root")
        assert fleet_service.initialize_fleet.call_args.kwargs["root_agent_id"] == "custom_root"
        assert fleet_service.recruit_member.call_args.kwargs["parent_agent_id"] == "custom_root"
        assert result["specialists_count"] == 1

    @pytest.mark.asyncio
    async def test_lazy_init_happens_inside_execute(self):
        admiral, fleet_service, llm = _make_admiral(_analysis())
        chain = Mock()
        chain.id = "chain-1"
        chain.status = "active"
        fleet_service.initialize_fleet.return_value = chain
        ri = Mock()
        ri.orchestrate_recruitment = AsyncMock(
            return_value={"success": True,
                          "recruitment_roster": [
                              {"agent_id": "a1", "agent_name": "Alice",
                               "domain": "data"}]})
        with patch("core.specialist_matcher.SpecialistMatcher"), \
                patch("core.recruitment_analytics_service.RecruitmentAnalyticsService"), \
                patch("analytics.fleet_optimization_service.FleetOptimizationService"), \
                patch("core.agent_governance_service.AgentGovernanceService"), \
                patch("core.fleet_admiral.RecruitmentIntelligenceService",
                      return_value=ri):
            result = await admiral.recruit_and_execute("Analyze sales", "user-1")
        assert admiral.recruitment_intelligence is ri
        ri.orchestrate_recruitment.assert_awaited_once()
        assert result["specialists_count"] == 1


class TestTaskAnalysisModel:
    def test_validates_specialist_count_range(self):
        with pytest.raises(Exception):
            TaskAnalysis(
                complexity="low",
                required_capabilities=["x"],
                estimated_duration="1 minute",
                specialist_count=0,
                reasoning="invalid",
            )
        with pytest.raises(Exception):
            TaskAnalysis(
                complexity="low",
                required_capabilities=["x"],
                estimated_duration="1 minute",
                specialist_count=11,
                reasoning="invalid",
            )


# ============================================================================
# HITLService
# ============================================================================

class _FakeQuery:
    """Chained query stub: filter/with_for_update pass through, first() resolves."""

    def __init__(self, result):
        self._result = result

    def filter(self, *a, **k):
        return self

    def with_for_update(self, *a, **k):
        return self

    def first(self):
        return self._result


@pytest.fixture
def hitl():
    return HITLService()


@pytest.fixture
def hitl_session():
    """Mock session whose query() resolves per-model results + patches get_db_session."""
    patcher = None

    def _make(action_result, user_result):
        nonlocal patcher
        session = MagicMock()
        results = {HITLAction: action_result, User: user_result}
        session.query.side_effect = lambda model: _FakeQuery(results[model])
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        patcher = patch("core.hitl_service.get_db_session", return_value=ctx)
        patcher.start()
        return session

    yield _make
    if patcher is not None:
        patcher.stop()


def _action(status="pending", priority="MEDIUM", notified_channel_id=None,
            params=None, action_id="action-1"):
    return HITLAction(
        id=action_id,
        action_type="send_message",
        platform="slack",
        status=status,
        priority=priority,
        notified_channel_id=notified_channel_id,
        params=params,
    )


def _user(email="user@example.com", two_factor_enabled=False):
    return User(
        id="user-1",
        email=email,
        first_name="First",
        last_name="Last",
        role="admin",
        status="active",
        two_factor_enabled=two_factor_enabled,
    )


class TestResolveAction:
    @pytest.mark.asyncio
    async def test_action_not_found_raises(self, hitl, hitl_session):
        hitl_session(None, _user())
        with pytest.raises(ValueError, match="not found"):
            await hitl.resolve_action("missing", "approved", "user-1")

    @pytest.mark.asyncio
    async def test_already_approved_returns_resolved(self, hitl, hitl_session):
        session = hitl_session(_action(status=HITLActionStatus.APPROVED.value), _user())
        result = await hitl.resolve_action("action-1", "approved", "user-1")
        assert result == {"status": "approved", "message": "Action already resolved"}
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_rejected_returns_resolved(self, hitl, hitl_session):
        session = hitl_session(_action(status=HITLActionStatus.REJECTED.value), _user())
        result = await hitl.resolve_action("action-1", "rejected", "user-1")
        assert result == {"status": "rejected", "message": "Action already resolved"}
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolver_not_found_raises(self, hitl, hitl_session):
        hitl_session(_action(), None)
        with pytest.raises(ValueError, match="Resolver user"):
            await hitl.resolve_action("action-1", "approved", "ghost-user")

    @pytest.mark.asyncio
    async def test_rejection_sets_status_and_commit(self, hitl, hitl_session):
        session = hitl_session(_action(), _user())
        result = await hitl.resolve_action("action-1", "rejected", "user-1")
        assert result == {"status": "rejected"}
        session.commit.assert_called_once()
        action = session.query.side_effect(HITLAction).first()
        assert action.status == HITLActionStatus.REJECTED.value
        assert action.resolver_id == "user-1"
        assert action.resolved_at is not None
        assert action.resolved_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_approval_resumes_workflow(self, hitl, hitl_session):
        session = hitl_session(_action(), _user())
        with patch.object(hitl, "_resume_workflow", new=AsyncMock()) as resume:
            result = await hitl.resolve_action("action-1", "approved", "user-1")
        assert result == {"status": "approved"}
        session.commit.assert_called_once()
        action = session.query.side_effect(HITLAction).first()
        assert action.status == HITLActionStatus.APPROVED.value
        assert action.resolver_id == "user-1"
        assert action.resolved_at is not None
        resume.assert_awaited_once_with(action)

    @pytest.mark.asyncio
    async def test_urgent_2fa_unverified_prompts(self, hitl, hitl_session):
        session = hitl_session(
            _action(priority="URGENT"), _user(two_factor_enabled=True))
        with patch.object(hitl, "_prompt_for_2fa", new=AsyncMock()) as prompt:
            result = await hitl.resolve_action(
                "action-1", "approved", "user-1", metadata={"verified_2fa": False})
        assert result == {"status": "pending_2fa", "message": "2FA verification required"}
        action = session.query.side_effect(HITLAction).first()
        assert action.status == HITLActionStatus.PENDING_2FA.value
        session.commit.assert_called_once()
        prompt.assert_awaited_once_with(action, session.query.side_effect(User).first())

    @pytest.mark.asyncio
    async def test_urgent_2fa_no_metadata_prompts(self, hitl, hitl_session):
        session = hitl_session(
            _action(priority="URGENT"), _user(two_factor_enabled=True))
        with patch.object(hitl, "_prompt_for_2fa", new=AsyncMock()) as prompt:
            result = await hitl.resolve_action("action-1", "approved", "user-1")
        assert result["status"] == "pending_2fa"
        prompt.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_urgent_2fa_verified_skips_prompt(self, hitl, hitl_session):
        session = hitl_session(
            _action(priority="URGENT"), _user(two_factor_enabled=True))
        with patch.object(hitl, "_prompt_for_2fa", new=AsyncMock()) as prompt, \
                patch.object(hitl, "_resume_workflow", new=AsyncMock()) as resume:
            result = await hitl.resolve_action(
                "action-1", "approved", "user-1", metadata={"verified_2fa": True})
        assert result == {"status": "approved"}
        prompt.assert_not_called()
        resume.assert_awaited_once()
        assert session.query.side_effect(HITLAction).first().status == \
            HITLActionStatus.APPROVED.value

    @pytest.mark.asyncio
    async def test_urgent_2fa_disabled_skips_prompt(self, hitl, hitl_session):
        session = hitl_session(
            _action(priority="URGENT"), _user(two_factor_enabled=False))
        with patch.object(hitl, "_prompt_for_2fa", new=AsyncMock()) as prompt, \
                patch.object(hitl, "_resume_workflow", new=AsyncMock()) as resume:
            result = await hitl.resolve_action("action-1", "approved", "user-1")
        assert result == {"status": "approved"}
        prompt.assert_not_called()
        resume.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_urgent_2fa_enabled_skips_prompt(self, hitl, hitl_session):
        session = hitl_session(
            _action(priority="HIGH"), _user(two_factor_enabled=True))
        with patch.object(hitl, "_prompt_for_2fa", new=AsyncMock()) as prompt, \
                patch.object(hitl, "_resume_workflow", new=AsyncMock()) as resume:
            result = await hitl.resolve_action("action-1", "approved", "user-1")
        assert result == {"status": "approved"}
        prompt.assert_not_called()
        resume.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejection_skips_2fa(self, hitl, hitl_session):
        session = hitl_session(
            _action(priority="URGENT"), _user(two_factor_enabled=True))
        with patch.object(hitl, "_prompt_for_2fa", new=AsyncMock()) as prompt:
            result = await hitl.resolve_action("action-1", "rejected", "user-1")
        assert result == {"status": "rejected"}
        prompt.assert_not_called()
        assert session.query.side_effect(HITLAction).first().status == \
            HITLActionStatus.REJECTED.value


class TestPromptFor2FA:
    @pytest.mark.asyncio
    async def test_no_channel_returns_early(self, hitl):
        action = _action(notified_channel_id=None)
        with patch("core.hitl_service.communication_service") as comm:
            await hitl._prompt_for_2fa(action, _user())
        comm.get_adapter.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_without_colon_returns_early(self, hitl):
        action = _action(notified_channel_id="plain-channel")
        with patch("core.hitl_service.communication_service") as comm:
            await hitl._prompt_for_2fa(action, _user())
        comm.get_adapter.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_channel_after_colon_returns_early(self, hitl):
        action = _action(notified_channel_id="slack:")
        with patch("core.hitl_service.communication_service") as comm:
            await hitl._prompt_for_2fa(action, _user())
        comm.get_adapter.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_message_to_channel(self, hitl):
        action = _action(notified_channel_id="slack:C1234")
        adapter = AsyncMock()
        with patch("core.hitl_service.communication_service") as comm:
            comm.get_adapter.return_value = adapter
            await hitl._prompt_for_2fa(action, _user())
        comm.get_adapter.assert_called_once_with("slack")
        adapter.send_message.assert_awaited_once()
        channel, msg = adapter.send_message.await_args.args
        assert channel == "C1234"
        assert "2FA" in msg
        assert "send_message" in msg


class TestResumeWorkflow:
    @pytest.mark.asyncio
    async def test_no_callback_url_no_http(self, hitl):
        action = _action()
        with patch("httpx.AsyncClient") as client:
            await hitl._resume_workflow(action)
        client.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_callback_blocked(self, hitl):
        action = _action(params={"callback_url": "http://localhost:9000/hitl"})
        with patch("httpx.AsyncClient") as client:
            await hitl._resume_workflow(action)
        client.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_callback_posted(self, hitl):
        action = _action(params={"callback_url": "https://example.com/hitl"})
        action.resolver_id = "user-1"
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        client.post = AsyncMock()
        with patch("httpx.AsyncClient", return_value=client):
            await hitl._resume_workflow(action)
        client.post.assert_awaited_once()
        payload = client.post.await_args.kwargs["json"]
        assert payload == {"action_id": "action-1", "status": "approved",
                           "resolver_id": "user-1"}

    @pytest.mark.asyncio
    async def test_callback_post_error_swallowed(self, hitl):
        action = _action(params={"callback_url": "https://example.com/hitl"})
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        client.post = AsyncMock(side_effect=RuntimeError("network down"))
        with patch("httpx.AsyncClient", return_value=client):
            await hitl._resume_workflow(action)


class TestValidateUrl:
    @pytest.fixture
    def svc(self):
        return HITLService()

    def test_allows_http(self, svc):
        assert svc._validate_url("http://example.com/cb") is True

    def test_allows_https(self, svc):
        assert svc._validate_url("https://example.com/cb") is True

    def test_blocks_localhost_name(self, svc):
        assert svc._validate_url("http://localhost/cb") is False

    @pytest.mark.parametrize("host", [
        "http://127.0.0.1/cb", "http://[::1]/cb",
        "http://10.0.0.5/cb", "http://10.255.255.255/cb",
        "http://172.16.0.1/cb", "http://172.31.255.255/cb",
        "http://192.168.1.1/cb", "http://169.254.0.1/cb",
    ])
    def test_blocks_private_ip_ranges(self, svc, host):
        assert svc._validate_url(host) is False

    def test_allows_public_172_32(self, svc):
        assert svc._validate_url("http://172.32.0.1/cb") is True

    def test_blocks_internal_hostnames(self, svc):
        for host in ["http://metadata.google.internal/cb",
                     "http://db.internal.example.com/cb",
                     "http://api.compute.internal/cb",
                     "http://fn.cloudfunctions.internal/cb"]:
            assert svc._validate_url(host) is False, host

    def test_blocks_invalid_scheme(self, svc):
        assert svc._validate_url("ftp://example.com/cb") is False
        assert svc._validate_url("file:///etc/passwd") is False

    def test_malformed_url_returns_false(self, svc):
        assert svc._validate_url("http://[::1") is False


# ============================================================================
# AgentOrchestrator
# ============================================================================

@pytest.fixture
def mock_llm():
    llm = Mock()
    llm.generate_structured = AsyncMock()
    return llm


def _step(thought="Think", action=None, final_answer=None):
    return SimpleNamespace(thought=thought, action=action,
                           final_answer=final_answer)


def _tool_call(name, params):
    return SimpleNamespace(tool=name, params=params)


class TestAgentOrchestratorInit:
    def test_defaults(self, mock_llm):
        orch = AgentOrchestrator(llm_service=mock_llm)
        assert orch.llm_service is mock_llm
        assert orch.model == "quality"
        assert orch.max_loops == 10
        assert orch.history == []
        assert "autonomous AI agent" in orch.system_instruction

    def test_system_instruction_none_uses_default(self, mock_llm):
        orch = AgentOrchestrator(llm_service=mock_llm, system_instruction=None)
        assert "autonomous AI agent" in orch.system_instruction

    def test_system_instruction_empty_uses_default(self, mock_llm):
        orch = AgentOrchestrator(llm_service=mock_llm, system_instruction="")
        assert "autonomous AI agent" in orch.system_instruction

    def test_custom_params(self, mock_llm):
        orch = AgentOrchestrator(llm_service=mock_llm, model="fast",
                                 max_loops=3, system_instruction="Custom")
        assert orch.model == "fast"
        assert orch.max_loops == 3
        assert orch.system_instruction == "Custom"


class TestAgentOrchestratorRun:
    @pytest.mark.asyncio
    async def test_immediate_final_answer(self, mock_llm):
        mock_llm.generate_structured.return_value = _step(
            final_answer="2 + 3 = 5")
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=3)
        result = await orch.run("What is 2 + 3?", toolbox={})
        assert result.status == "completed"
        assert result.final_answer == "2 + 3 = 5"
        assert result.total_loops == 1
        assert result.steps[0]["action"] == "final_answer"
        assert result.steps[0]["result"] == "2 + 3 = 5"
        assert result.steps[0]["loop"] == 1
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_context_inserted_as_system_message(self, mock_llm):
        mock_llm.generate_structured.return_value = _step(final_answer="done")
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=1)
        await orch.run("Do it", toolbox={}, context={"user_id": "u1"})
        prompt = mock_llm.generate_structured.await_args.kwargs["prompt"]
        assert prompt.startswith("system: Context: {\"user_id\": \"u1\"}")

    @pytest.mark.asyncio
    async def test_final_answer_beats_action_same_step(self, mock_llm):
        mock_llm.generate_structured.return_value = _step(
            action=_tool_call("add", {"a": 1, "b": 1}),
            final_answer="answer wins")
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=2)
        result = await orch.run("t", toolbox={"add": lambda a, b: a + b})
        assert result.status == "completed"
        assert result.final_answer == "answer wins"
        assert result.total_loops == 1

    @pytest.mark.asyncio
    async def test_sync_tool_execution(self, mock_llm):
        mock_llm.generate_structured.side_effect = [
            _step(action=_tool_call("add", {"a": 2, "b": 3})),
            _step(final_answer="5"),
        ]
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=2)
        result = await orch.run(
            "add", toolbox={"add": lambda a, b: a + b})
        assert result.status == "completed"
        assert result.total_loops == 2
        assert result.steps[0]["result"] == "5"
        assert result.steps[0]["action"] == "add({\"a\": 2, \"b\": 3})"

    @pytest.mark.asyncio
    async def test_async_tool_execution(self, mock_llm):
        async def async_add(a, b):
            return a + b
        mock_llm.generate_structured.side_effect = [
            _step(action=_tool_call("async_add", {"a": 10, "b": 20})),
            _step(final_answer="30"),
        ]
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=2)
        result = await orch.run(
            "add", toolbox={"async_add": async_add})
        assert result.status == "completed"
        assert result.steps[0]["result"] == "30"

    @pytest.mark.asyncio
    async def test_tool_result_none_becomes_string(self, mock_llm):
        mock_llm.generate_structured.side_effect = [
            _step(action=_tool_call("noop", {})),
            _step(final_answer="done"),
        ]
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=2)
        result = await orch.run("t", toolbox={"noop": lambda: None})
        assert result.steps[0]["result"] == "None"

    @pytest.mark.asyncio
    async def test_missing_tool(self, mock_llm):
        mock_llm.generate_structured.side_effect = [
            _step(action=_tool_call("ghost", {})),
            _step(final_answer="done"),
        ]
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=2)
        result = await orch.run("t", toolbox={})
        assert "not found" in result.steps[0]["result"]
        assert result.steps[0]["action"] == "ghost({})"

    @pytest.mark.asyncio
    async def test_tool_error_observed(self, mock_llm):
        def boom():
            raise ValueError("kaboom")
        mock_llm.generate_structured.side_effect = [
            _step(action=_tool_call("boom", {})),
            _step(final_answer="done"),
        ]
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=2)
        result = await orch.run("t", toolbox={"boom": boom})
        assert "Error executing tool boom: kaboom" in result.steps[0]["result"]
        assert result.steps[0]["error"] == "kaboom"

    @pytest.mark.asyncio
    async def test_no_action_no_answer_breaks(self, mock_llm):
        mock_llm.generate_structured.side_effect = [
            _step(action=None, final_answer=None),
            _step(final_answer="never reached"),
        ]
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=3)
        result = await orch.run("t", toolbox={})
        assert result.status == "exhausted"
        assert result.total_loops == 1
        assert result.steps[0]["action"] == "none"
        assert "Maximum reasoning loops" in result.final_answer

    @pytest.mark.asyncio
    async def test_none_decision_breaks(self, mock_llm):
        mock_llm.generate_structured.side_effect = [None, _step(final_answer="x")]
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=2)
        result = await orch.run("t", toolbox={})
        assert result.status == "exhausted"
        assert result.steps == []

    @pytest.mark.asyncio
    async def test_max_loops_exhausted(self, mock_llm):
        mock_llm.generate_structured.return_value = _step(
            action=_tool_call("add", {"a": 1, "b": 1}))
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=2)
        result = await orch.run("t", toolbox={"add": lambda a, b: a + b})
        assert result.status == "exhausted"
        assert result.total_loops == 2
        assert result.final_answer == "Maximum reasoning loops reached without a final answer."

    @pytest.mark.asyncio
    async def test_reasoning_failure_returns_failed(self, mock_llm):
        mock_llm.generate_structured.side_effect = Exception("LLM API error")
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=3)
        result = await orch.run("t", toolbox={})
        assert result.status == "failed"
        assert result.error == "Reasoning error: LLM API error"
        assert result.total_loops == 0
        assert result.steps == []
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_reasoning_failure_after_steps(self, mock_llm):
        mock_llm.generate_structured.side_effect = [
            _step(action=_tool_call("add", {"a": 1, "b": 1})),
            Exception("boom"),
        ]
        orch = AgentOrchestrator(llm_service=mock_llm, max_loops=3)
        result = await orch.run("t", toolbox={"add": lambda a, b: a + b})
        assert result.status == "failed"
        assert result.total_loops == 1
        assert len(result.steps) == 1


class TestGenerateToolDescriptions:
    def test_docstring_first_line_used(self, mock_llm):
        def documented_tool():
            """First line of docs.

            Second line should be dropped.
            """
            pass
        orch = AgentOrchestrator(llm_service=mock_llm)
        desc = orch._generate_tool_descriptions({"doc": documented_tool})
        assert desc == "- doc: First line of docs."

    def test_missing_docstring_placeholder(self, mock_llm):
        orch = AgentOrchestrator(llm_service=mock_llm)
        desc = orch._generate_tool_descriptions({"lam": lambda x: x})
        assert desc == "- lam: No description available."

    def test_empty_toolbox(self, mock_llm):
        orch = AgentOrchestrator(llm_service=mock_llm)
        assert orch._generate_tool_descriptions({}) == ""


class TestAgentExecutionResponse:
    def test_defaults(self):
        resp = AgentExecutionResponse()
        assert resp.status == "completed"
        assert resp.final_answer is None
        assert resp.steps == []
        assert resp.execution_time_ms == 0.0
        assert resp.total_loops == 0
        assert resp.error is None

    def test_custom_values(self):
        resp = AgentExecutionResponse(
            status="failed", final_answer="nope", steps=[{"loop": 1}],
            execution_time_ms=5.5, total_loops=1, error="bad")
        assert resp.status == "failed"
        assert resp.final_answer == "nope"
        assert resp.steps == [{"loop": 1}]
        assert resp.execution_time_ms == 5.5
        assert resp.total_loops == 1
        assert resp.error == "bad"
