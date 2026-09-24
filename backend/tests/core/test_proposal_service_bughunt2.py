"""
Bug-hunt + coverage tests for core.proposal_service (round 2).

Targets UNcovered code paths and verifies REAL bugs found via TDD.
Each bug test is prefixed ``BUG:`` and was written BEFORE the source fix,
confirmed to fail for the right reason, then verified to pass after the fix.
"""
import json
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.proposal_service import ProposalService
from core.models import (
    AgentExecution,
    AgentProposal,
    AgentRegistry,
    ProposalStatus,
    ProposalType,
    Tenant,
    User,
    UserRole,
    Workspace,
)


@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def service(mock_db):
    return ProposalService(db=mock_db)


# ============================================================================
# BUG #2: _format_proposal_outcome / _create_proposal_episode treat
# ``modifications`` (a dict) as a list -> TypeError -> learning episode silently
# never created when an approved proposal had modifications.
# ============================================================================
class TestProposalModificationsTypeMismatchBug:
    """BUG: approve_proposal receives ``modifications: Dict[str, Any]`` but
    _create_proposal_episode / _format_proposal_outcome slice it with ``[:5]``
    and call ``len()`` on it as if it were a list. A dict has no ``[:5]`` ->
    TypeError, which is swallowed by the broad try/except in
    _create_proposal_episode, so the learning episode is NEVER created for any
    approved-with-modifications proposal.
    """

    def test_bug_format_outcome_handles_dict_modifications(self, service):
        """BUG: _format_proposal_outcome must not crash on dict modifications."""
        proposal = Mock(spec=AgentProposal)
        proposal.approved_by = "user-1"
        proposal.approved_at = datetime(2026, 1, 1)

        # approve_proposal passes modifications as a DICT (Optional[Dict[str, Any]])
        modifications = {"action_type": "canvas_present", "url": "https://x"}

        # Must not raise TypeError
        outcome = service._format_proposal_outcome(
            proposal, "approved", modifications=modifications
        )
        # And should reference the modification count
        assert "Modifications Applied" in outcome

    def test_bug_format_outcome_dict_modifications_lists_changed_keys(self, service):
        """When modifications is a dict, the outcome should report the modified
        keys (not crash trying to slice the dict)."""
        proposal = Mock(spec=AgentProposal)
        proposal.approved_by = "user-1"
        proposal.approved_at = datetime(2026, 1, 1)

        modifications = {"url": "https://y", "title": "New"}

        outcome = service._format_proposal_outcome(
            proposal, "approved", modifications=modifications
        )
        # Each modified key should appear
        assert "url" in outcome
        assert "title" in outcome

    def test_format_outcome_handles_list_modifications_still(self, service):
        """Backwards-compat: list-form modifications (if ever used) still work."""
        proposal = Mock(spec=AgentProposal)
        proposal.approved_by = "user-1"
        proposal.approved_at = datetime(2026, 1, 1)

        outcome = service._format_proposal_outcome(
            proposal, "approved", modifications=["change_a", "change_b"]
        )
        assert "change_a" in outcome


# ============================================================================
# Coverage: _calculate_proposal_importance (uncovered)
# ============================================================================
class TestCalculateProposalImportance:
    def test_rejected_baseline(self, service):
        p = Mock(spec=AgentProposal)
        p.suggested_modifications = None
        # rejected: 0.5 + 0.3 = 0.8
        assert service._calculate_proposal_importance("rejected", p) == pytest.approx(0.8)

    def test_approved_with_modifications(self, service):
        p = Mock(spec=AgentProposal)
        p.suggested_modifications = json.dumps({"x": 1})
        # approved: 0.5 + 0.1 + 0.1 = 0.7
        assert service._calculate_proposal_importance("approved", p) == pytest.approx(0.7)

    def test_rejected_with_modifications_clamps(self, service):
        p = Mock(spec=AgentProposal)
        p.suggested_modifications = json.dumps({"x": 1})
        # rejected + mod: 0.5 + 0.3 + 0.1 = 0.9 (under clamp)
        assert service._calculate_proposal_importance("rejected", p) == pytest.approx(0.9)

    def test_clamps_to_one(self, service):
        # Construct a fake proposal whose modifications attr is truthy but
        # importance already maxed by rejection. rejected+mod = 0.9 <= 1.0 OK.
        # To force clamping we rely on the formula staying <= 1.0 for any input.
        p = Mock(spec=AgentProposal)
        p.suggested_modifications = json.dumps({"a": 1})
        score = service._calculate_proposal_importance("rejected", p)
        assert 0.0 <= score <= 1.0


# ============================================================================
# Coverage: _extract_proposal_topics / _extract_proposal_entities
# ============================================================================
class TestExtractProposalMetadata:
    def test_topics_include_type_and_action_type(self, service):
        p = Mock(spec=AgentProposal)
        p.proposal_type = "action"
        p.title = "Important Proposal About Billing"
        p.reasoning = "Because the customer needed help with invoicing"
        p.proposed_action = {"action_type": "canvas_present"}

        topics = service._extract_proposal_topics(p)
        # proposal_type always first
        assert topics[0] == "action"
        # action_type included
        assert "canvas_present" in topics
        # limited to 5
        assert len(topics) <= 5

    def test_topics_handles_missing_fields(self, service):
        p = Mock(spec=AgentProposal)
        p.proposal_type = "action"
        p.title = None
        p.reasoning = None
        p.proposed_action = None
        topics = service._extract_proposal_topics(p)
        assert topics == ["action"]

    def test_entities_include_ids_and_reviewer(self, service):
        p = Mock(spec=AgentProposal)
        p.id = "prop-1"
        p.agent_id = "agent-1"
        p.approved_by = "reviewer-1"
        p.proposed_action = {"action_type": "canvas_present", "canvas_id": "c1"}

        entities = service._extract_proposal_entities(p)
        ent_set = set(entities)
        assert "proposal:prop-1" in ent_set
        assert "agent:agent-1" in ent_set
        assert "reviewer:reviewer-1" in ent_set
        # short string action values are added as entities
        assert "canvas_present" in ent_set
        assert "c1" in ent_set


# ============================================================================
# Coverage: get_pending_proposals / get_proposal_history
# ============================================================================
class TestProposalQueries:
    @pytest.mark.asyncio
    async def test_get_pending_proposals_applies_filters(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.all.return_value = ["p1", "p2"]
        mock_db.query.return_value = chain

        result = await service.get_pending_proposals(
            agent_id="a1", canvas_id="c1", tenant_id="t1", limit=10
        )
        assert result == ["p1", "p2"]

    @pytest.mark.asyncio
    async def test_get_proposal_history_serializes(self, service, mock_db):
        p = Mock(spec=AgentProposal)
        p.id = "pid"
        p.proposal_type = "action"
        p.title = "T"
        p.status = ProposalStatus.APPROVED.value
        p.created_at = datetime(2026, 1, 1)
        p.approved_at = datetime(2026, 1, 2)
        p.approved_by = "u1"
        p.approver_id = "u1"
        p.approver_type = "user"
        p.reviewed_at = datetime(2026, 1, 2)
        p.execution_id = "exec-1"
        p.execution_success = True
        p.execution_outcome_details = json.dumps({"status": "success"})
        p.suggested_modifications = json.dumps({"prompt": "updated"})
        p.approval_reason = None

        chain = Mock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.all.return_value = [p]
        mock_db.query.return_value = chain

        history = await service.get_proposal_history("a1")
        assert len(history) == 1
        assert history[0]["proposal_id"] == "pid"
        assert history[0]["created_at"] == datetime(2026, 1, 1).isoformat()
        assert history[0]["approved_at"] == datetime(2026, 1, 2).isoformat()


# ============================================================================
# Coverage: reject_proposal happy path + guard
# ============================================================================
class TestRejectProposal:
    @pytest.mark.asyncio
    async def test_reject_proposal_sets_rejected_status(self, service, mock_db):
        proposal = Mock(spec=AgentProposal)
        proposal.id = "p1"
        proposal.status = ProposalStatus.PENDING_APPROVAL.value
        proposal.agent_id = "a1"
        proposal.tenant_id = "t1"
        proposal.proposed_action = {"action_type": "canvas_present"}
        proposal.approved_by = None
        proposal.approver_id = None
        proposal.approved_at = None
        proposal.reviewed_at = None
        proposal.approval_reason = None
        proposal.execution_success = None
        proposal.execution_outcome_details = None

        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = proposal
        mock_db.query.return_value = chain

        with patch.object(service, "_create_proposal_episode", new=AsyncMock()):
            with patch("core.proposal_service.AgentLearningEnhanced") as LearningCls:
                learning = LearningCls.return_value
                learning.record_rejection = AsyncMock()
                await service.reject_proposal("p1", "u1", "bad idea")

        assert proposal.status == ProposalStatus.REJECTED.value
        assert proposal.approved_by == "u1"
        assert proposal.approval_reason == "bad idea"

    @pytest.mark.asyncio
    async def test_reject_rejects_non_pending_proposal(self, service, mock_db):
        proposal = Mock(spec=AgentProposal)
        proposal.status = ProposalStatus.APPROVED.value  # already approved

        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = proposal
        mock_db.query.return_value = chain

        with pytest.raises(ValueError, match="PENDING_APPROVAL"):
            await service.reject_proposal("p1", "u1", "x")

    @pytest.mark.asyncio
    async def test_reject_raises_when_not_found(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = None
        mock_db.query.return_value = chain
        with pytest.raises(ValueError, match="not found"):
            await service.reject_proposal("missing", "u1", "x")


# ============================================================================
# Coverage: create_action_proposal happy path + match-confidence block
# ============================================================================
class TestCreateActionProposal:
    @pytest.mark.asyncio
    async def test_create_proposal_with_selector_candidates(self, service, mock_db):
        from core.models import AgentRegistry, AgentStatus
        agent = Mock(spec=AgentRegistry)
        agent.id = "a1"
        agent.name = "InternBot"
        agent.status = AgentStatus.INTERN.value
        agent.category = "test"
        agent.confidence_score = 0.6
        agent.tenant_id = "t1"
        agent.user_id = "u1"

        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = agent
        mock_db.query.return_value = chain

        proposed_action = {
            "action_type": "browser_automate",
            "selector_candidates": [
                {"selector": "#a", "match_count": 3, "is_text_only": True},
                {"selector": ".b", "match_count": 1, "is_text_only": False},
            ],
            "match_rationale": "high confidence",
            "match_score": 0.9,
            "chosen_index": 0,
            "per_field_confidence": {"#a": {"level": "high", "score": 0.9}},
        }

        with patch.object(service, "_create_proposal_episode", new=AsyncMock()):
            result = await service.create_action_proposal(
                intern_agent_id="a1",
                trigger_context={},
                proposed_action=proposed_action,
                reasoning="because",
            )

        # Description must include the candidates block
        assert "Selector candidates (2)" in result.description
        assert "#a" in result.description
        # per_field_confidence block present
        assert "Per-field confidence" in result.description
        assert result.status == ProposalStatus.PENDING_APPROVAL.value

    @pytest.mark.asyncio
    async def test_create_proposal_blocks_non_intern(self, service, mock_db):
        from core.models import AgentRegistry, AgentStatus
        agent = Mock(spec=AgentRegistry)
        agent.status = AgentStatus.SUPERVISED.value

        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = agent
        mock_db.query.return_value = chain

        with pytest.raises(PermissionError):
            await service.create_action_proposal(
                "a1", {}, {"action_type": "x"}, "r"
            )

    @pytest.mark.asyncio
    async def test_create_proposal_raises_when_agent_missing(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = None
        mock_db.query.return_value = chain
        with pytest.raises(ValueError, match="not found"):
            await service.create_action_proposal(
                "missing", {}, {"action_type": "x"}, "r"
            )


# ============================================================================
# Coverage: _execute_proposed_action routing (unknown action type + disabled)
# ============================================================================
class TestExecuteProposedActionRouting:
    @pytest.mark.asyncio
    async def test_unknown_action_type_returns_error(self, service):
        proposal = Mock(spec=AgentProposal)
        proposal.id = "p1"
        proposal.proposed_action = {"action_type": "totally_unknown"}

        result = await service._execute_proposed_action(proposal)
        assert result["success"] is False
        assert "Unknown action type" in result["error"]

    @pytest.mark.asyncio
    async def test_disabled_execution_returns_skipped(self, service):
        proposal = Mock(spec=AgentProposal)
        proposal.id = "p1"
        proposal.proposed_action = {"action_type": "browser_automate"}

        with patch("core.proposal_service.PROPOSAL_EXECUTION_ENABLED", False):
            result = await service._execute_proposed_action(proposal)
        assert result["success"] is False
        assert result["skipped"] is True


def _seed_proposal_scope(session, suffix=""):
    tenant_a = Tenant(
        id=f"tenant-a{suffix}",
        name=f"Tenant A{suffix}",
        subdomain=f"tenant-a{suffix}",
    )
    tenant_b = Tenant(
        id=f"tenant-b{suffix}",
        name=f"Tenant B{suffix}",
        subdomain=f"tenant-b{suffix}",
    )
    workspace_a = Workspace(
        id=f"workspace-a{suffix}",
        name=f"Workspace A{suffix}",
        tenant_id=tenant_a.id,
    )
    workspace_b = Workspace(
        id=f"workspace-b{suffix}",
        name=f"Workspace B{suffix}",
        tenant_id=tenant_b.id,
    )
    user_a = User(
        id=f"user-a{suffix}",
        email=f"user-a{suffix}@example.com",
        first_name="Tenant",
        last_name="A",
        role=UserRole.TEAM_LEAD.value,
        status="active",
        tenant_id=tenant_a.id,
        workspace_id=workspace_a.id,
    )
    user_b = User(
        id=f"user-b{suffix}",
        email=f"user-b{suffix}@example.com",
        first_name="Tenant",
        last_name="B",
        role=UserRole.TEAM_LEAD.value,
        status="active",
        tenant_id=tenant_b.id,
        workspace_id=workspace_b.id,
    )
    source_agent = AgentRegistry(
        id=f"source-agent{suffix}",
        name="Source Agent",
        category="testing",
        module_path="agents.source",
        class_name="SourceAgent",
        status="intern",
        confidence_score=0.6,
        tenant_id=tenant_a.id,
        workspace_id=workspace_a.id,
        user_id=user_a.id,
    )
    target_agent = AgentRegistry(
        id=f"target-agent{suffix}",
        name="Target Agent",
        category="testing",
        module_path="agents.target",
        class_name="TargetAgent",
        status="intern",
        confidence_score=0.6,
        tenant_id=tenant_a.id,
        workspace_id=workspace_a.id,
        user_id=user_a.id,
    )
    foreign_agent = AgentRegistry(
        id=f"foreign-agent{suffix}",
        name="Foreign Agent",
        category="testing",
        module_path="agents.foreign",
        class_name="ForeignAgent",
        status="intern",
        confidence_score=0.6,
        tenant_id=tenant_b.id,
        workspace_id=workspace_b.id,
        user_id=user_b.id,
    )
    session.add_all(
        [
            tenant_a,
            tenant_b,
            workspace_a,
            workspace_b,
            user_a,
            user_b,
            source_agent,
            target_agent,
            foreign_agent,
        ]
    )
    session.commit()
    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "workspace_a": workspace_a,
        "workspace_b": workspace_b,
        "user_a": user_a,
        "user_b": user_b,
        "source_agent": source_agent,
        "target_agent": target_agent,
        "foreign_agent": foreign_agent,
    }


def _add_proposal(
    session,
    scope,
    proposal_id,
    tenant_key,
    agent_key,
    action=None,
    status=ProposalStatus.PENDING_APPROVAL.value,
):
    tenant = scope[f"tenant_{tenant_key}"]
    user = scope[f"user_{tenant_key}"]
    agent = scope[agent_key]
    proposal = AgentProposal(
        id=proposal_id,
        tenant_id=tenant.id,
        user_id=user.id,
        agent_id=agent.id,
        agent_name=agent.name,
        title=proposal_id,
        description=proposal_id,
        proposal_type=ProposalType.ACTION.value,
        proposal_data=action or {
            "action_type": "agent_execute",
            "target_agent_id": scope["target_agent"].id,
            "prompt": "original prompt",
            "parameters": {"mode": "original"},
        },
        status=status,
    )
    session.add(proposal)
    session.commit()
    return proposal


@pytest.fixture
def proposal_scope(db_session):
    return {"db": db_session, **_seed_proposal_scope(db_session)}


@pytest.fixture
def isolated_proposal_db(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base

    engine = create_engine(
        f"sqlite:///{tmp_path / 'proposal-concurrency.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    scope = _seed_proposal_scope(session, suffix="-isolated")
    yield session_factory, scope
    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_approval_claim_is_committed_before_execution(proposal_scope):
    db = proposal_scope["db"]
    proposal = _add_proposal(
        db, proposal_scope, "claim-before-execution", "a", "source_agent"
    )
    service = ProposalService(db)
    observed = []

    async def execute(*args, **kwargs):
        db.expire_all()
        current = db.query(AgentProposal).filter(AgentProposal.id == proposal.id).one()
        observed.append((current.status, current.approver_id, current.reviewed_at))
        return {"success": True, "execution_id": "external-execution-1"}

    with patch.object(service, "_execute_proposed_action_with", new=execute), patch.object(
        service, "_create_proposal_episode", new=AsyncMock()
    ), patch("core.proposal_service.AgentLearningEnhanced"):
        result = await service.approve_proposal(
            proposal.id,
            proposal_scope["user_a"].id,
            tenant_id=proposal.tenant_id,
        )

    assert result["success"] is True
    assert observed[0][0] == ProposalStatus.APPROVED.value
    assert observed[0][1] == proposal_scope["user_a"].id
    assert observed[0][2] is not None
    db.expire_all()
    persisted = db.query(AgentProposal).filter(AgentProposal.id == proposal.id).one()
    assert persisted.status == ProposalStatus.EXECUTED.value
    assert persisted.execution_success is True
    assert persisted.execution_id == "external-execution-1"
    assert json.loads(persisted.execution_outcome_details)["success"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_result, expected_success",
    [
        ({"status": "success"}, True),
        ({"status": "failed"}, False),
        ({"status": "error"}, False),
        ({"status": "failure"}, False),
        ({"status": "success", "success": False}, False),
    ],
)
async def test_agent_execution_normalizes_generic_agent_results(
    proposal_scope, agent_result, expected_success
):
    db = proposal_scope["db"]
    proposal = _add_proposal(
        db, proposal_scope, f"normalize-{expected_success}", "a", "source_agent"
    )
    proposal.approved_by = proposal_scope["user_a"].id
    db.commit()
    service = ProposalService(db)
    runtime = Mock()
    runtime.execute = AsyncMock(return_value=agent_result)

    with patch("core.generic_agent.GenericAgent", return_value=runtime) as agent_cls, patch.object(
        service, "_record_execution_episode"
    ):
        result = await service._execute_agent_action(proposal, proposal.proposed_action)

    assert result["success"] is expected_success
    agent_cls.assert_called_once_with(
        agent_model=proposal_scope["target_agent"],
        workspace_id=proposal_scope["workspace_a"].id,
    )
    context = runtime.execute.await_args.kwargs["context"]
    assert context["user_id"] == proposal_scope["user_a"].id
    assert context["tenant_id"] == proposal_scope["tenant_a"].id
    assert context["workspace_id"] == proposal_scope["workspace_a"].id
    assert context["agent_id"] == proposal_scope["target_agent"].id
    execution = db.query(AgentExecution).filter(AgentExecution.id == result["execution_id"]).one()
    assert execution.workspace_id == proposal_scope["workspace_a"].id
    assert execution.status == ("completed" if expected_success else "failed")


@pytest.mark.asyncio
async def test_agent_execution_rejects_foreign_tenant_target(proposal_scope):
    db = proposal_scope["db"]
    proposal = _add_proposal(
        db,
        proposal_scope,
        "foreign-target",
        "a",
        "source_agent",
        action={
            "action_type": "agent_execute",
            "target_agent_id": proposal_scope["foreign_agent"].id,
            "prompt": "do it",
        },
    )
    service = ProposalService(db)

    with patch("core.generic_agent.GenericAgent") as agent_cls:
        with pytest.raises(ValueError, match="not found"):
            await service._execute_agent_action(proposal, proposal.proposed_action)

    agent_cls.assert_not_called()
    assert db.query(AgentExecution).count() == 0


@pytest.mark.asyncio
async def test_agent_execution_uses_default_workspace_only_when_model_has_none(
    proposal_scope,
):
    db = proposal_scope["db"]
    target = proposal_scope["target_agent"]
    target.workspace_id = None
    db.commit()
    proposal = _add_proposal(
        db, proposal_scope, "default-workspace", "a", "source_agent"
    )
    service = ProposalService(db)
    runtime = Mock()
    runtime.execute = AsyncMock(return_value={"status": "success"})

    with patch("core.generic_agent.GenericAgent", return_value=runtime) as agent_cls, patch.object(
        service, "_record_execution_episode"
    ):
        await service._execute_agent_action(proposal, proposal.proposed_action)

    agent_cls.assert_called_once_with(agent_model=target, workspace_id="default")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "modifications",
    [
        {"action_type": "device_command"},
        {"target_agent_id": "another-agent"},
        {"tenant_id": "tenant-b"},
        {"workspace_id": "workspace-b"},
    ],
)
async def test_execution_control_modifications_are_rejected_before_claim(
    proposal_scope, modifications
):
    db = proposal_scope["db"]
    proposal = _add_proposal(
        db, proposal_scope, f"blocked-{len(modifications)}-{list(modifications)[0]}", "a", "source_agent"
    )
    service = ProposalService(db)
    executor = AsyncMock(return_value={"success": True})

    with patch.object(service, "_execute_proposed_action_with", new=executor), patch(
        "core.proposal_service.AgentLearningEnhanced"
    ):
        with pytest.raises(ValueError, match="execution-control"):
            await service.approve_proposal(
                proposal.id,
                proposal_scope["user_a"].id,
                modifications=modifications,
                tenant_id=proposal.tenant_id,
            )

    executor.assert_not_awaited()
    db.expire_all()
    persisted = db.query(AgentProposal).filter(AgentProposal.id == proposal.id).one()
    assert persisted.status == ProposalStatus.PENDING_APPROVAL.value
    assert persisted.approver_id is None
    assert persisted.suggested_modifications is None


@pytest.mark.asyncio
async def test_safe_prompt_and_parameter_modifications_are_persisted(proposal_scope):
    db = proposal_scope["db"]
    proposal = _add_proposal(
        db, proposal_scope, "safe-modifications", "a", "source_agent"
    )
    service = ProposalService(db)
    executed_action = None

    async def execute(_proposal, action):
        nonlocal executed_action
        executed_action = action
        return {"success": True}

    with patch.object(service, "_execute_proposed_action_with", new=execute), patch.object(
        service, "_create_proposal_episode", new=AsyncMock()
    ), patch("core.proposal_service.AgentLearningEnhanced") as learning_cls:
        learning_cls.return_value.record_user_correction = AsyncMock()
        await service.approve_proposal(
            proposal.id,
            proposal_scope["user_a"].id,
            modifications={"prompt": "updated prompt", "parameters": {"mode": "safe"}},
            tenant_id=proposal.tenant_id,
        )

    assert executed_action["prompt"] == "updated prompt"
    assert executed_action["parameters"] == {"mode": "safe"}
    db.expire_all()
    persisted = db.query(AgentProposal).filter(AgentProposal.id == proposal.id).one()
    assert persisted.proposal_data["prompt"] == "updated prompt"
    assert persisted.proposal_data["parameters"] == {"mode": "safe"}
    assert json.loads(persisted.suggested_modifications) == {
        "prompt": "updated prompt",
        "parameters": {"mode": "safe"},
    }
    assert not hasattr(persisted, "modifications")


@pytest.mark.asyncio
async def test_execution_exception_persists_execution_failed_without_unmapped_result(
    proposal_scope,
):
    db = proposal_scope["db"]
    proposal = _add_proposal(
        db, proposal_scope, "execution-exception", "a", "source_agent"
    )
    service = ProposalService(db)

    with patch.object(
        service,
        "_execute_proposed_action_with",
        new=AsyncMock(side_effect=RuntimeError("sensitive executor detail")),
    ), patch("core.proposal_service.AgentLearningEnhanced"):
        with pytest.raises(RuntimeError, match="sensitive executor detail"):
            await service.approve_proposal(
                proposal.id,
                proposal_scope["user_a"].id,
                tenant_id=proposal.tenant_id,
            )

    db.expire_all()
    persisted = db.query(AgentProposal).filter(AgentProposal.id == proposal.id).one()
    assert persisted.status == ProposalStatus.EXECUTION_FAILED.value
    assert persisted.execution_success is False
    assert "sensitive executor detail" not in persisted.execution_outcome_details
    assert json.loads(persisted.execution_outcome_details)["error"] == "Proposal execution failed"
    assert not hasattr(persisted, "execution_result")


@pytest.mark.asyncio
async def test_failed_generic_result_persists_execution_failed_fields(proposal_scope):
    db = proposal_scope["db"]
    proposal = _add_proposal(
        db, proposal_scope, "generic-failure", "a", "source_agent"
    )
    service = ProposalService(db)

    with patch.object(
        service,
        "_execute_proposed_action_with",
        new=AsyncMock(return_value={"status": "error", "error": "agent failed"}),
    ), patch.object(service, "_create_proposal_episode", new=AsyncMock()), patch(
        "core.proposal_service.AgentLearningEnhanced"
    ):
        result = await service.approve_proposal(
            proposal.id,
            proposal_scope["user_a"].id,
            tenant_id=proposal.tenant_id,
        )

    assert result["success"] is False
    db.expire_all()
    persisted = db.query(AgentProposal).filter(AgentProposal.id == proposal.id).one()
    assert persisted.status == ProposalStatus.EXECUTION_FAILED.value
    assert persisted.execution_success is False
    assert json.loads(persisted.execution_outcome_details)["status"] == "error"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["approve", "reject"])
async def test_stale_concurrent_session_cannot_claim_proposal_twice(
    isolated_proposal_db, operation
):
    session_factory, scope = isolated_proposal_db
    setup_session = session_factory()
    proposal = _add_proposal(
        setup_session,
        scope,
        f"stale-{operation}",
        "a",
        "source_agent",
    )
    first_session = session_factory()
    second_session = session_factory()
    first_session.query(AgentProposal).filter(AgentProposal.id == proposal.id).one()
    second_session.query(AgentProposal).filter(AgentProposal.id == proposal.id).one()
    executor = AsyncMock(return_value={"success": True})
    first_service = ProposalService(first_session)
    second_service = ProposalService(second_session)

    with patch.object(ProposalService, "_execute_proposed_action_with", new=executor), patch.object(
        ProposalService, "_create_proposal_episode", new=AsyncMock()
    ), patch("core.proposal_service.AgentLearningEnhanced") as learning_cls, patch(
        "core.autonomy_policy.reset_autonomy_cycle"
    ):
        learning_cls.return_value.record_user_correction = AsyncMock()
        learning_cls.return_value.record_rejection = AsyncMock()
        if operation == "approve":
            await first_service.approve_proposal(
                proposal.id, scope["user_a"].id, tenant_id=proposal.tenant_id
            )
            with pytest.raises(ValueError, match="PENDING_APPROVAL"):
                await second_service.approve_proposal(
                    proposal.id, scope["user_a"].id, tenant_id=proposal.tenant_id
                )
        else:
            await first_service.reject_proposal(
                proposal.id, scope["user_a"].id, "first", tenant_id=proposal.tenant_id
            )
            with pytest.raises(ValueError, match="PENDING_APPROVAL"):
                await second_service.reject_proposal(
                    proposal.id, scope["user_a"].id, "second", tenant_id=proposal.tenant_id
                )

    assert executor.await_count == (1 if operation == "approve" else 0)
    first_session.close()
    second_session.close()


@pytest.mark.asyncio
async def test_rejection_persists_review_fields_and_reason(proposal_scope):
    db = proposal_scope["db"]
    proposal = _add_proposal(
        db, proposal_scope, "rejection-mapping", "a", "source_agent"
    )
    service = ProposalService(db)

    with patch.object(service, "_create_proposal_episode", new=AsyncMock()), patch(
        "core.proposal_service.AgentLearningEnhanced"
    ) as learning_cls, patch("core.autonomy_policy.reset_autonomy_cycle"):
        learning_cls.return_value.record_rejection = AsyncMock()
        await service.reject_proposal(
            proposal.id,
            proposal_scope["user_a"].id,
            "unsafe target",
            tenant_id=proposal.tenant_id,
        )

    db.expire_all()
    persisted = db.query(AgentProposal).filter(AgentProposal.id == proposal.id).one()
    assert persisted.approver_type == "user"
    assert persisted.approver_id == proposal_scope["user_a"].id
    assert persisted.approved_by == proposal_scope["user_a"].id
    assert persisted.reviewed_at is not None
    assert persisted.approval_reason == "unsafe target"
    assert not hasattr(persisted, "execution_result")


@pytest.mark.asyncio
async def test_foreign_tenant_proposal_cannot_be_approved(proposal_scope):
    db = proposal_scope["db"]
    proposal = _add_proposal(
        db, proposal_scope, "foreign-approval", "b", "foreign_agent"
    )
    service = ProposalService(db)
    executor = AsyncMock(return_value={"success": True})

    with patch.object(service, "_execute_proposed_action_with", new=executor):
        with pytest.raises(ValueError, match="not found"):
            await service.approve_proposal(
                proposal.id,
                proposal_scope["user_a"].id,
                tenant_id=proposal_scope["tenant_a"].id,
            )

    executor.assert_not_awaited()
    db.expire_all()
    persisted = db.query(AgentProposal).filter(AgentProposal.id == proposal.id).one()
    assert persisted.status == ProposalStatus.PENDING_APPROVAL.value


@pytest.mark.asyncio
async def test_history_uses_persisted_execution_and_review_fields(proposal_scope):
    db = proposal_scope["db"]
    proposal = _add_proposal(
        db, proposal_scope, "history-mapping", "a", "source_agent"
    )
    proposal.status = ProposalStatus.EXECUTED.value
    proposal.approver_type = "user"
    proposal.approver_id = proposal_scope["user_a"].id
    proposal.approved_by = proposal_scope["user_a"].id
    proposal.approved_at = datetime(2026, 1, 2)
    proposal.reviewed_at = datetime(2026, 1, 2)
    proposal.execution_id = "execution-1"
    proposal.execution_success = True
    proposal.execution_outcome_details = json.dumps({"status": "success"})
    proposal.suggested_modifications = json.dumps({"prompt": "updated"})
    proposal.approval_reason = None
    db.commit()

    history = await ProposalService(db).get_proposal_history(
        proposal.agent_id,
        tenant_id=proposal.tenant_id,
    )
    foreign_history = await ProposalService(db).get_proposal_history(
        proposal.agent_id,
        tenant_id=proposal_scope["tenant_b"].id,
    )

    assert history[0]["execution_id"] == "execution-1"
    assert history[0]["execution_success"] is True
    assert history[0]["execution_outcome_details"] == {"status": "success"}
    assert history[0]["suggested_modifications"] == {"prompt": "updated"}
    assert history[0]["approver_id"] == proposal_scope["user_a"].id
    assert history[0]["reviewed_at"] == datetime(2026, 1, 2).isoformat()
    assert "execution_result" not in history[0]
    assert foreign_history == []
