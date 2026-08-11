"""Coverage wave 27 — core/proposal_service.py (TDD, mocked db + executors).

Drives the INTERN-proposal lifecycle: creation (incl. match-confidence
candidates block), approval (execution + Bug-12 mutation semantics +
learning corrections), rejection, pending/history queries, the six
action executors (browser/canvas/integration/workflow/device/agent),
episode creation from proposals, formatting helpers, and the
autonomous-supervisor review paths — zero LLM, zero spend.
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.proposal_service import ProposalService


class FakeProposal:
    """Mimics AgentProposal's property semantics (proposed_action reads
    proposal_data, reasoning reads proposal_data['reasoning'])."""

    def __init__(self, proposal_data=None, **kw):
        defaults = dict(
            id="p-1", tenant_id="t-1", user_id="u-1", agent_id="ag-1",
            agent_name="Intern Agent", canvas_id=None, session_id=None,
            title="Action Proposal: Intern Agent",
            proposal_type="action", status="pending_approval",
            approved_by=None, approved_at=None, created_at=datetime.now(timezone.utc),
            executed_at=None, execution_result=None, modifications=None,
            proposal_data=proposal_data if proposal_data is not None else {},
        )
        defaults.update(kw)
        for k, v in defaults.items():
            setattr(self, k, v)

    @property
    def proposed_action(self):
        if self.proposal_type == "action":
            return self.proposal_data
        return {}

    @property
    def reasoning(self):
        return self.proposal_data.get("reasoning", "")


def make_agent(status="intern", **kw):
    defaults = dict(id="ag-1", name="Intern Agent", category="general",
                    confidence_score=0.8, status=status,
                    tenant_id="t-1", user_id="u-1")
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_db(**overrides):
    db = MagicMock()
    for k, v in overrides.items():
        setattr(db, k, v)
    return db


def make_proposal(**kw):
    return FakeProposal(**kw)


class TestCreateActionProposal:
    async def test_agent_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = ProposalService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.create_action_proposal("ghost", {}, {"action_type": "x"}, "why")

    async def test_non_intern_blocked(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent(status="supervised")
        svc = ProposalService(db)
        with pytest.raises(PermissionError, match="not an INTERN"):
            await svc.create_action_proposal("ag-1", {}, {"action_type": "x"}, "why")

    async def test_success(self):
        db = make_db()
        agent = make_agent()
        db.query.return_value.filter.return_value.first.return_value = agent
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        svc = ProposalService(db)
        with patch("core.proposal_service.AgentProposal", lambda **kw: make_proposal(**kw)):
            proposal = await svc.create_action_proposal(
                "ag-1", {"page": "x"}, {"action_type": "browser_automate"}, "reasoning here",
                canvas_id="cv-1", session_id="s-1", title="My Proposal")
        assert proposal.title == "My Proposal"
        assert proposal.status == "pending_approval"
        db.add.assert_called_once()
        db.commit.assert_called_once()

    async def test_selector_candidates_block(self):
        db = make_db()
        agent = make_agent()
        db.query.return_value.filter.return_value.first.return_value = agent
        db.commit = MagicMock()
        db.refresh = MagicMock()
        svc = ProposalService(db)
        action = {
            "action_type": "browser_automate",
            "selector_candidates": [
                {"selector": "#btn", "match_count": 3, "is_text_only": False},
                "legacy-candidate",
            ],
            "match_rationale": "best match",
            "match_score": 0.9,
            "chosen_index": 0,
            "per_field_confidence": {"#btn": {"level": "high", "score": 0.95}},
        }
        with patch("core.proposal_service.AgentProposal", lambda **kw: make_proposal(**kw)):
            proposal = await svc.create_action_proposal(
                "ag-1", {}, action, "why")
        assert "Selector candidates (2)" in proposal.description
        assert "Match score" in proposal.description
        assert "Per-field confidence" in proposal.description


class TestSubmitForApproval:
    async def test_wrong_status(self):
        svc = ProposalService(make_db())
        with pytest.raises(ValueError, match="PENDING_APPROVAL"):
            await svc.submit_for_approval(make_proposal(status="executed"))

    async def test_success(self):
        svc = ProposalService(make_db())
        await svc.submit_for_approval(make_proposal())  # no-op, no crash


class TestApproveProposal:
    async def test_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = ProposalService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.approve_proposal("ghost", "u1")

    async def test_wrong_status(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_proposal(status="rejected")
        svc = ProposalService(db)
        with pytest.raises(ValueError, match="PENDING_APPROVAL"):
            await svc.approve_proposal("p-1", "u1")

    async def test_execution_failure_raises_and_marks_failed(self):
        db = make_db()
        proposal = make_proposal()
        db.query.return_value.filter.return_value.first.return_value = proposal
        db.commit = MagicMock()
        svc = ProposalService(db)
        with patch.object(svc, "_execute_proposed_action_with",
                          new=AsyncMock(side_effect=RuntimeError("exec boom"))), \
             patch("core.proposal_service.AgentLearningEnhanced"):
            with pytest.raises(RuntimeError, match="exec boom"):
                await svc.approve_proposal("p-1", "u1")
        assert proposal.status == "execution_failed"
        assert proposal.execution_result["success"] is False

    async def test_success_with_modifications(self):
        db = make_db()
        proposal = make_proposal(proposal_data={"action_type": "device_command", "device_id": "d1"})
        db.query.return_value.filter.return_value.first.return_value = proposal
        db.commit = MagicMock()
        db.refresh = MagicMock()
        svc = ProposalService(db)
        result = {"success": True, "output": "ran"}
        with patch.object(svc, "_execute_proposed_action_with", new=AsyncMock(return_value=result)), \
             patch.object(svc, "_create_proposal_episode", new=AsyncMock()) as episode_mock, \
             patch("core.proposal_service.AgentLearningEnhanced") as learning_cls:
            learning_cls.return_value.record_user_correction = AsyncMock()
            out = await svc.approve_proposal(
                "p-1", "u1", modifications={"device_id": "d2"})
        assert out == result
        assert proposal.status == "executed"
        assert proposal.proposal_data["device_id"] == "d2"
        assert proposal.modifications == {"device_id": "d2"}
        episode_mock.assert_called_once()

    async def test_execution_result_failed_marks_failed(self):
        db = make_db()
        proposal = make_proposal()
        db.query.return_value.filter.return_value.first.return_value = proposal
        db.commit = MagicMock()
        db.refresh = MagicMock()
        svc = ProposalService(db)
        with patch.object(svc, "_execute_proposed_action_with",
                          new=AsyncMock(return_value={"success": False, "error": "nope"})), \
             patch.object(svc, "_create_proposal_episode", new=AsyncMock()), \
             patch("core.proposal_service.AgentLearningEnhanced"):
            await svc.approve_proposal("p-1", "u1")
        assert proposal.status == "execution_failed"


class TestRejectProposal:
    async def test_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = ProposalService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.reject_proposal("ghost", "u1", "bad")

    async def test_wrong_status(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_proposal(status="executed")
        svc = ProposalService(db)
        with pytest.raises(ValueError, match="PENDING_APPROVAL"):
            await svc.reject_proposal("p-1", "u1", "bad")

    async def test_success(self):
        db = make_db()
        proposal = make_proposal(proposal_data={"action_type": "browser_automate"})
        db.query.return_value.filter.return_value.first.return_value = proposal
        db.commit = MagicMock()
        svc = ProposalService(db)
        with patch.object(svc, "_create_proposal_episode", new=AsyncMock()) as episode_mock, \
             patch("core.proposal_service.AgentLearningEnhanced") as learning_cls:
            learning_cls.return_value.record_rejection = AsyncMock()
            await svc.reject_proposal("p-1", "u1", "too risky")
        assert proposal.status == "rejected"
        assert proposal.execution_result["rejected"] is True
        assert proposal.execution_result["reason"] == "too risky"
        episode_mock.assert_called_once()
        learning_cls.return_value.record_rejection.assert_called_once()


class TestQueries:
    async def test_get_pending_all_filters(self):
        db = make_db()
        query = db.query.return_value.filter.return_value
        svc = ProposalService(db)
        result = await svc.get_pending_proposals("ag-1", "cv-1", "t-1", limit=5)
        assert result == query.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value

    async def test_get_pending_no_filters(self):
        db = make_db()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = ["p"]
        svc = ProposalService(db)
        assert await svc.get_pending_proposals() == ["p"]

    async def test_get_proposal_history(self):
        db = make_db()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            make_proposal(id="p1", approved_at=datetime.now(timezone.utc), approved_by="u1",
                          execution_result={"success": True}),
            make_proposal(id="p2", approved_at=None),
        ]
        svc = ProposalService(db)
        history = await svc.get_proposal_history("ag-1")
        assert len(history) == 2
        assert history[0]["approved_at"] is not None
        assert history[1]["approved_at"] is None
        assert history[0]["execution_result"]["success"] is True


class TestExecuteDispatcher:
    async def test_disabled(self):
        svc = ProposalService(make_db())
        with patch("core.proposal_service.PROPOSAL_EXECUTION_ENABLED", False):
            result = await svc._execute_proposed_action(make_proposal())
        assert result["success"] is False
        assert result["skipped"] is True

    @pytest.mark.parametrize("action_type,method", [
        ("browser_automate", "_execute_browser_action"),
        ("canvas_present", "_execute_canvas_action"),
        ("integration_connect", "_execute_integration_action"),
        ("workflow_trigger", "_execute_workflow_action"),
        ("device_command", "_execute_device_action"),
        ("agent_execute", "_execute_agent_action"),
    ])
    async def test_dispatch(self, action_type, method):
        svc = ProposalService(make_db())
        proposal = make_proposal(proposal_data={"action_type": action_type})
        with patch("core.proposal_service.PROPOSAL_EXECUTION_ENABLED", True), \
             patch.object(svc, method, new=AsyncMock(return_value={"success": True})):
            result = await svc._execute_proposed_action(proposal)
        assert result["success"] is True

    async def test_unknown_action_type(self):
        svc = ProposalService(make_db())
        proposal = make_proposal(proposal_data={"action_type": "mystery"})
        with patch("core.proposal_service.PROPOSAL_EXECUTION_ENABLED", True):
            result = await svc._execute_proposed_action(proposal)
        assert result["success"] is False
        assert "Unknown action type" in result["error"]

    async def test_executor_exception_wrapped(self):
        svc = ProposalService(make_db())
        proposal = make_proposal(proposal_data={"action_type": "browser_automate"})
        with patch("core.proposal_service.PROPOSAL_EXECUTION_ENABLED", True), \
             patch.object(svc, "_execute_browser_action",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await svc._execute_proposed_action(proposal)
        assert result["success"] is False
        assert result["error"] == "Action execution failed"

    async def test_execute_with_prepared_action_swaps_back(self):
        db = make_db()
        proposal = make_proposal(proposal_data={"action_type": "device_command"})
        svc = ProposalService(db)
        with patch.object(svc, "_execute_proposed_action", new=AsyncMock(return_value={"success": True})):
            result = await svc._execute_proposed_action_with(
                proposal, {"action_type": "device_command", "device_id": "x"})
        assert result["success"] is True
        assert proposal.proposal_data["action_type"] == "device_command"  # restored


class TestBrowserExecutor:
    async def test_success_with_steps(self):
        db = make_db()
        db.commit = MagicMock()
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "browser_automate",
                                                "url": "https://x", "actions": [
                                                    {"type": "click", "selector": "#b"},
                                                    {"type": "fill", "selector": "#f", "value": "v"},
                                                    {"type": "script", "script": "return 1"},
                                                ]})
        svc = ProposalService(db)
        with patch("tools.browser_tool.browser_create_session",
                   new=AsyncMock(return_value={"session_id": "sess-1"})), \
             patch("tools.browser_tool.browser_navigate", new=AsyncMock()), \
             patch("tools.browser_tool.browser_click", new=AsyncMock()), \
             patch("tools.browser_tool.browser_fill_form", new=AsyncMock()), \
             patch("tools.browser_tool.browser_execute_script", new=AsyncMock()):
            result = await svc._execute_browser_action(proposal, proposal.proposed_action)
        assert result["success"] is True
        assert result["result"]["session_id"] == "sess-1"

    async def test_missing_url_and_session(self):
        db = make_db()
        db.commit = MagicMock()
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "browser_automate"})
        svc = ProposalService(db)
        with pytest.raises(ValueError, match="requires a url or session_id"):
            await svc._execute_browser_action(proposal, proposal.proposed_action)

    async def test_import_error(self):
        svc = ProposalService(make_db())
        db = make_db()
        db.commit = MagicMock()
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "browser_automate",
                                                "url": "https://x"})
        svc = ProposalService(db)
        with patch("tools.browser_tool.browser_create_session",
                   new=AsyncMock(side_effect=ImportError("no playwright"))):
            result = await svc._execute_browser_action(proposal, proposal.proposed_action)
        assert result["success"] is False
        assert "not available" in result["error"]


class TestCanvasExecutor:
    async def test_success(self):
        db = make_db()
        db.commit = MagicMock()
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "canvas_present",
                                                "canvas_type": "chart",
                                                "content": {"data": [1]},
                                                "title": "T", "session_id": "s"})
        svc = ProposalService(db)
        with patch("tools.canvas_tool.present_to_canvas", new=AsyncMock(return_value="cv-1")):
            result = await svc._execute_canvas_action(proposal, proposal.proposed_action)
        assert result["success"] is True
        assert result["canvas_id"] == "cv-1"

    async def test_exception_reraises(self):
        svc = ProposalService(make_db())
        proposal = make_proposal()
        with patch("tools.canvas_tool.present_to_canvas",
                   new=AsyncMock(side_effect=RuntimeError("canvas down"))):
            with pytest.raises(RuntimeError, match="canvas down"):
                await svc._execute_canvas_action(proposal, {})


class TestIntegrationExecutor:
    async def test_success(self):
        db = make_db()
        db.commit = MagicMock()
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "integration_connect",
                                                "integration_type": "gmail",
                                                "operation": "send",
                                                "parameters": {"to": "a@b"}})
        svc = ProposalService(db)
        service_cls = MagicMock()
        service_cls.return_value.execute = AsyncMock(return_value={"success": True})
        with patch("integrations.universal_integration_service.UniversalIntegrationService",
                   service_cls):
            result = await svc._execute_integration_action(proposal, proposal.proposed_action)
        assert result["success"] is True
        assert result["integration_type"] == "gmail"

    async def test_non_dict_result_wrapped(self):
        db = make_db()
        db.commit = MagicMock()
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "integration_connect",
                                                "integration_type": "gmail"})
        svc = ProposalService(db)
        service_cls = MagicMock()
        service_cls.return_value.execute = AsyncMock(return_value={"ok": True})
        with patch("integrations.universal_integration_service.UniversalIntegrationService",
                   service_cls):
            result = await svc._execute_integration_action(proposal, proposal.proposed_action)
        assert result["success"] is True

    async def test_exception_returns_error(self):
        db = make_db()
        proposal = make_proposal()
        svc = ProposalService(db)
        service_cls = MagicMock()
        service_cls.return_value.execute = AsyncMock(side_effect=RuntimeError("int down"))
        with patch("integrations.universal_integration_service.UniversalIntegrationService",
                   service_cls):
            result = await svc._execute_integration_action(proposal, {})
        assert result["success"] is False
        assert result["error"] == "Integration action failed"


class TestWorkflowExecutor:
    async def test_not_found(self):
        db = make_db()
        db.commit = MagicMock()
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "workflow_trigger",
                                                "workflow_id": "missing"})
        svc = ProposalService(db)
        with patch("core.workflow_endpoints.load_workflows", return_value=[]):
            with pytest.raises(ValueError, match="not found"):
                await svc._execute_workflow_action(proposal, proposal.proposed_action)

    async def test_success(self):
        db = make_db()
        db.commit = MagicMock()
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "workflow_trigger",
                                                "workflow_id": "w-1",
                                                "parameters": {"x": 1}})
        svc = ProposalService(db)
        engine_cls = MagicMock()
        engine_cls.return_value.start_workflow = AsyncMock(return_value="ex-1")
        with patch("core.workflow_endpoints.load_workflows",
                   return_value=[{"id": "w-1", "name": "W"}]), \
             patch("core.workflow_engine.WorkflowEngine", engine_cls):
            result = await svc._execute_workflow_action(proposal, proposal.proposed_action)
        assert result["success"] is True
        assert result["result"]["execution_id"] == "ex-1"


class TestDeviceExecutor:
    async def test_success(self):
        db = make_db()
        db.commit = MagicMock()
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "device_command",
                                                "device_id": "d1",
                                                "command_type": "camera",
                                                "parameters": {}})
        svc = ProposalService(db)
        with patch("tools.device_tool.execute_device_command",
                   new=AsyncMock(return_value={"success": True})):
            result = await svc._execute_device_action(proposal, proposal.proposed_action)
        assert result["success"] is True


class TestAgentExecutor:
    async def test_agent_not_found(self):
        db = make_db()
        db.commit = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "agent_execute",
                                                "target_agent_id": "ghost",
                                                "prompt": "do it"})
        svc = ProposalService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc._execute_agent_action(proposal, proposal.proposed_action)

    async def test_success(self):
        db = make_db()
        db.commit = MagicMock()
        registry_agent = make_agent(id="ag-2")
        db.query.return_value.filter.return_value.first.return_value = registry_agent
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "agent_execute",
                                                "target_agent_id": "ag-2",
                                                "prompt": "do it",
                                                "parameters": {}})
        svc = ProposalService(db)
        agent_cls = MagicMock()
        agent_cls.return_value.execute = AsyncMock(return_value={"success": True})
        with patch("core.generic_agent.GenericAgent", agent_cls):
            result = await svc._execute_agent_action(proposal, proposal.proposed_action)
        assert result["success"] is True
        assert result["target_agent_id"] == "ag-2"

    async def test_non_dict_result_wrapped(self):
        db = make_db()
        db.commit = MagicMock()
        registry_agent = make_agent(id="ag-2")
        db.query.return_value.filter.return_value.first.return_value = registry_agent
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "agent_execute",
                                                "target_agent_id": "ag-2",
                                                "prompt": "do it"})
        svc = ProposalService(db)
        agent_cls = MagicMock()
        agent_cls.return_value.execute = AsyncMock(return_value="plain response")
        with patch("core.generic_agent.GenericAgent", agent_cls):
            result = await svc._execute_agent_action(proposal, proposal.proposed_action)
        assert result["success"] is True
        assert result["result"]["response"] == "plain response"


class TestProposalEpisode:
    async def test_episode_created_with_dict_modifications(self):
        db = make_db()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        proposal = make_proposal(
            title="Run report", approved_by="u1",
            approved_at=datetime.now(timezone.utc),
            proposal_data={"action_type": "device_command"})
        svc = ProposalService(db)
        with patch("core.episode_segmentation_service.EpisodeSegmentationService",
                   return_value=MagicMock()), \
             patch("core.proposal_service.Episode", lambda **kw: make_proposal(**kw)), \
             patch("core.proposal_service.EpisodeSegment", lambda **kw: make_proposal(**kw)):
            await svc._create_proposal_episode(
                proposal, "approved", modifications={"device_id": "d2"},
                execution_result={"success": True})
        # dict → list normalization: 1 modification
        assert db.add.call_count == 3  # episode + 2 segments

    async def test_episode_with_none_modifications(self):
        db = make_db()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        proposal = make_proposal(approved_by="u1",
                                 approved_at=datetime.now(timezone.utc))
        svc = ProposalService(db)
        with patch("core.episode_segmentation_service.EpisodeSegmentationService",
                   return_value=MagicMock()), \
             patch("core.proposal_service.Episode", lambda **kw: make_proposal(**kw)), \
             patch("core.proposal_service.EpisodeSegment", lambda **kw: make_proposal(**kw)):
            await svc._create_proposal_episode(proposal, "rejected", rejection_reason="no")
        assert db.add.call_count == 3

    async def test_episode_exception_tolerated(self):
        db = make_db()
        proposal = make_proposal()
        svc = ProposalService(db)
        with patch("core.episode_segmentation_service.EpisodeSegmentationService",
                   side_effect=RuntimeError("seg down")):
            await svc._create_proposal_episode(proposal, "approved")  # no crash


class TestFormattingHelpers:
    def test_format_proposal_content(self):
        svc = ProposalService(make_db())
        proposal = make_proposal(
            title="T", proposal_type="action", agent_name="A",
            created_at=datetime.now(timezone.utc),
            proposal_data={"action_type": "browser_automate", "reasoning": "because"})
        content = svc._format_proposal_content(proposal, "approved")
        assert "Proposal Title: T" in content
        assert "Proposed Action Type: browser_automate" in content

    def test_format_outcome_approved_with_mods(self):
        svc = ProposalService(make_db())
        proposal = make_proposal(approved_by="u1", approved_at=datetime.now(timezone.utc))
        content = svc._format_proposal_outcome(
            proposal, "approved",
            modifications=[{"device_id": "d2"}, {"speed": "fast"}],
            execution_result={"success": True})
        assert "SUCCESS" in content
        assert "Modifications Applied: 2" in content

    def test_format_outcome_approved_dict_mods(self):
        svc = ProposalService(make_db())
        proposal = make_proposal(approved_by="u1", approved_at=datetime.now(timezone.utc))
        content = svc._format_proposal_outcome(proposal, "approved", modifications={"a": 1})
        assert "Modifications Applied: 1" in content

    def test_format_outcome_rejected(self):
        svc = ProposalService(make_db())
        proposal = make_proposal(approved_by="u1")
        content = svc._format_proposal_outcome(proposal, "rejected", rejection_reason="too risky")
        assert "Rejection Reason: too risky" in content

    def test_extract_topics(self):
        svc = ProposalService(make_db())
        proposal = make_proposal(
            title="Quarterly Report Review", proposal_type="action",
            proposal_data={"action_type": "workflow_trigger",
                           "reasoning": "automation pipeline improvement needed"})
        topics = svc._extract_proposal_topics(proposal)
        assert topics[0] == "action"
        assert "workflow_trigger" in topics
        assert len(topics) <= 5

    def test_extract_entities(self):
        svc = ProposalService(make_db())
        proposal = make_proposal(approved_by="u1",
                                 proposal_data={"action_type": "browser_automate",
                                                "url": "https://short.example"})
        entities = svc._extract_proposal_entities(proposal)
        assert "proposal:p-1" in entities
        assert "agent:ag-1" in entities
        assert "reviewer:u1" in entities
        assert "https://short.example" in entities

    def test_importance(self):
        svc = ProposalService(make_db())
        assert svc._calculate_proposal_importance("rejected", make_proposal()) == 0.8
        assert svc._calculate_proposal_importance("approved", make_proposal()) == 0.6
        proposal = make_proposal(modifications={"a": 1})
        assert svc._calculate_proposal_importance("approved", proposal) == 0.7


class TestAutonomousSupervisor:
    async def test_human_available(self):
        db = make_db()
        svc = ProposalService(db)
        uas = MagicMock()
        uas.get_available_supervisors = AsyncMock(
            return_value=[{"user_id": "sup-1"}])
        with patch("core.user_activity_service.UserActivityService", return_value=uas):
            result = await svc.review_with_autonomous_supervisor(make_proposal())
        assert result["supervisor_type"] == "human"
        assert result["supervisor_id"] == "sup-1"

    async def test_no_human_no_intern_agent(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = ProposalService(db)
        uas = MagicMock()
        uas.get_available_supervisors = AsyncMock(return_value=[])
        with patch("core.user_activity_service.UserActivityService", return_value=uas), \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService"):
            result = await svc.review_with_autonomous_supervisor(make_proposal())
        assert result is None

    async def test_no_supervisor_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        svc = ProposalService(db)
        uas = MagicMock()
        uas.get_available_supervisors = AsyncMock(return_value=[])
        auto = MagicMock()
        auto.find_autonomous_supervisor = AsyncMock(return_value=None)
        with patch("core.user_activity_service.UserActivityService", return_value=uas), \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService", return_value=auto):
            result = await svc.review_with_autonomous_supervisor(make_proposal())
        assert result is None

    async def test_autonomous_review(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        svc = ProposalService(db)
        uas = MagicMock()
        uas.get_available_supervisors = AsyncMock(return_value=[])
        auto = MagicMock()
        supervisor = SimpleNamespace(id="sup-9", name="AutoBot")
        auto.find_autonomous_supervisor = AsyncMock(return_value=supervisor)
        review = SimpleNamespace(approved=True, confidence_score=0.9,
                                 risk_level="low", reasoning="ok",
                                 suggested_modifications=[])
        auto.review_proposal = AsyncMock(return_value=review)
        with patch("core.user_activity_service.UserActivityService", return_value=uas), \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService", return_value=auto):
            result = await svc.review_with_autonomous_supervisor(make_proposal())
        assert result["supervisor_type"] == "autonomous"
        assert result["review"]["approved"] is True

    async def test_autonomous_approve_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = ProposalService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.autonomous_approve_or_reject("ghost")

    async def test_autonomous_no_supervisor(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_proposal()
        svc = ProposalService(db)
        with patch.object(svc, "review_with_autonomous_supervisor",
                          new=AsyncMock(return_value=None)):
            result = await svc.autonomous_approve_or_reject("p-1")
        assert result["success"] is False
        assert "No supervisor" in result["message"]

    async def test_autonomous_human_available(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_proposal()
        svc = ProposalService(db)
        with patch.object(svc, "review_with_autonomous_supervisor",
                          new=AsyncMock(return_value={
                              "supervisor_type": "human",
                              "supervisor_id": "sup-1"})):
            result = await svc.autonomous_approve_or_reject("p-1")
        assert result["success"] is False
        assert "awaiting manual approval" in result["message"]

    async def test_autonomous_approved_executed(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_proposal()
        svc = ProposalService(db)
        with patch.object(svc, "review_with_autonomous_supervisor",
                          new=AsyncMock(return_value={
                              "supervisor_type": "autonomous",
                              "supervisor_id": "sup-9",
                              "review": {"approved": True, "confidence_score": 0.9,
                                         "risk_level": "low", "reasoning": "ok",
                                         "suggested_modifications": []}})), \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService") as auto_cls:
            auto_cls.return_value.approve_proposal = AsyncMock(return_value=True)
            result = await svc.autonomous_approve_or_reject("p-1")
        assert result["success"] is True
        assert "approved and executed" in result["message"]

    async def test_autonomous_approval_failed(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_proposal()
        svc = ProposalService(db)
        with patch.object(svc, "review_with_autonomous_supervisor",
                          new=AsyncMock(return_value={
                              "supervisor_type": "autonomous",
                              "supervisor_id": "sup-9",
                              "review": {"approved": True, "confidence_score": 0.9,
                                         "risk_level": "low", "reasoning": "ok",
                                         "suggested_modifications": []}})), \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService") as auto_cls:
            auto_cls.return_value.approve_proposal = AsyncMock(return_value=False)
            result = await svc.autonomous_approve_or_reject("p-1")
        assert result["success"] is False
        assert "Failed to process" in result["message"]

    async def test_autonomous_rejected(self):
        db = make_db()
        proposal = make_proposal()
        db.query.return_value.filter.return_value.first.return_value = proposal
        db.commit = MagicMock()
        svc = ProposalService(db)
        with patch.object(svc, "review_with_autonomous_supervisor",
                          new=AsyncMock(return_value={
                              "supervisor_type": "autonomous",
                              "supervisor_id": "sup-9",
                              "review": {"approved": False, "confidence_score": 0.3,
                                         "risk_level": "high", "reasoning": "risky",
                                         "suggested_modifications": []}})), \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService"):
            result = await svc.autonomous_approve_or_reject("p-1")
        assert result["success"] is False
        assert "rejected by autonomous supervisor" in result["message"]
        assert proposal.status == "rejected"

    async def test_autonomous_reject_wrong_status_raises(self):
        db = make_db()
        proposal = make_proposal(status="executed")
        db.query.return_value.filter.return_value.first.return_value = proposal
        svc = ProposalService(db)
        with patch.object(svc, "review_with_autonomous_supervisor",
                          new=AsyncMock(return_value={
                              "supervisor_type": "autonomous",
                              "supervisor_id": "sup-9",
                              "review": {"approved": False, "confidence_score": 0.3,
                                         "risk_level": "high", "reasoning": "risky",
                                         "suggested_modifications": []}})), \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService"):
            with pytest.raises(ValueError, match="PENDING_APPROVAL"):
                await svc.autonomous_approve_or_reject("p-1")
