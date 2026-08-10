"""
Wave 10c — agents-layer bug tests (TDD RED).

Real bugs targeted:
1. advanced_workflow_api /generate-from-agent passes ``user_id=`` to
   ``QueenAgent.generate_blueprint`` which has no such parameter →
   TypeError → HTTP 500 on every request (the R69 test mocked the whole
   QueenAgent class, hiding it).
2. fleet_scaler ``_execute_expansion``/``_execute_contraction`` call
   ``get_distributed_blackboard(self.db)`` but the function takes zero args
   (``get_fleet_state_notifier()``) → TypeError after a successful DB commit
   → operations wrongly marked FAILED.
3. ``QueenAgent.realize_blueprint`` KeyErrors on LLM blueprints with nodes
   missing ``id``/``type`` → 500 in the /generate-from-agent flow.
4. ``FleetScalerService.check_scaling_constraints`` defined twice (identical
   dead copy shadows nothing but doubles maintenance surface).
"""

import inspect
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _user(role="member"):
    return MagicMock(id="u-10c", email="u@example.com", role=role, tenant_id="tenant-10c")


def _make_client(router_obj, role=None):
    from core.auth import get_current_user as auth_get_current_user
    from core.database import get_db

    app = FastAPI()
    app.include_router(router_obj)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    if role:
        app.dependency_overrides[auth_get_current_user] = lambda: _user(role)
    return TestClient(app, raise_server_exceptions=False)


def _strict_blackboard(*args, **kwargs):
    """The real get_distributed_blackboard() takes zero arguments."""
    assert not args and not kwargs, (
        f"get_distributed_blackboard called with {args} {kwargs}"
    )
    return None


# ============================================================================
# 1. /generate-from-agent passes user_id= to generate_blueprint (TypeError)
# ============================================================================
class TestGenerateFromAgentRealQueen:
    def test_generate_from_agent_200_with_real_queen(self):
        from ai.nlp_engine import RouteCategory
        from advanced_workflow_api import router
        from core.llm_service import LLMService

        blueprint = {
            "architecture_name": "Blue",
            "description": "d",
            "execution_mode": "recurring_automation",
            "nodes": [{"id": "n1", "type": "agent", "name": "A", "dependencies": []}],
            "required_integrations": [],
            "missing_capabilities": [],
        }
        client = _make_client(router, role="member")
        with patch("ai.nlp_engine.NaturalLanguageEngine") as m_nlu, patch.object(
            LLMService, "generate", new_callable=AsyncMock, return_value=json.dumps(blueprint)
        ):
            m_nlu.return_value.classify_route = AsyncMock(
                return_value=MagicMock(category=RouteCategory.AUTOMATION, reasoning="r")
            )
            resp = client.post(
                "/api/v1/workflows/generate-from-agent", json={"prompt": "build a workflow"}
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["workflow_id"].startswith("ai_wf_")


# ============================================================================
# 2. get_distributed_blackboard(self.db) — zero-arg function
# ============================================================================
class TestFleetScalerBlackboardArgs:
    def _service(self, existing=None, registry=None, chain=None):
        from core.fleet_orchestration.fleet_scaler_service import FleetScalerService
        from core.models import AgentRegistry, ChainLink, DelegationChain

        def _query(target, *args, **kwargs):
            q = Mock()
            q.filter.return_value = q
            q.limit.return_value = q
            if target is ChainLink.child_agent_id:
                q.all.return_value = existing or []
            elif target is AgentRegistry:
                q.all.return_value = registry or []
            elif target is DelegationChain:
                q.first.return_value = chain
            else:
                q.first.return_value = None
                q.all.return_value = []
            return q

        db = Mock()
        db.query.side_effect = _query
        db.add = Mock()
        db.flush = Mock()
        db.commit = Mock()
        svc = FleetScalerService(db)
        svc.proposal_service = Mock()
        svc.overage_service = Mock()
        svc.metrics_service = Mock()
        return svc

    def _proposal(self, ptype="expand", fleet_size=2):
        from core.fleet_orchestration.scaling_proposal_service import (
            ScalingProposal,
            ScalingProposalStatus,
            ScalingProposalType,
        )

        return ScalingProposal(
            id="p1",
            chain_id="chain-1",
            proposal_type=(
                ScalingProposalType.EXPANSION if ptype == "expand"
                else ScalingProposalType.CONTRACTION
            ),
            current_fleet_size=1,
            proposed_fleet_size=fleet_size,
            reason="wave10c",
            status=ScalingProposalStatus.APPROVED,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    def _operation(self, proposal):
        from core.fleet_orchestration.fleet_scaler_service import (
            ScalingOperation,
            ScalingOperationStatus,
        )

        return ScalingOperation(
            id="op-1",
            chain_id=proposal.chain_id,
            proposal_id=proposal.id,
            operation_type="expand",
            from_size=proposal.current_fleet_size,
            to_size=proposal.proposed_fleet_size,
            status=ScalingOperationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_expansion_blackboard_called_without_db_arg(self):
        from core.fleet_orchestration.fleet_scaler_service import (
            FleetScalerService,
        )

        svc = self._service(existing=[("agent-1",)], registry=[MagicMock(id="a2")])
        proposal = self._proposal("expand")
        op = self._operation(proposal)
        with patch(
            "core.fleet_orchestration.get_distributed_blackboard",
            new=_strict_blackboard,
        ):
            await svc._execute_expansion(proposal, op)
        assert op.agents_added

    @pytest.mark.asyncio
    async def test_contraction_blackboard_called_without_db_arg(self):
        from core.fleet_orchestration.fleet_scaler_service import (
            FleetScalerService,
        )

        link = MagicMock()
        link.child_agent_id = "agent-1"
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = [link]
        db.query.return_value = q
        db.commit = Mock()
        svc = FleetScalerService(db)
        svc.proposal_service = Mock()
        svc.overage_service = Mock()
        svc.metrics_service = Mock()
        proposal = self._proposal("contract", fleet_size=1)
        op = self._operation(proposal)
        with patch(
            "core.fleet_orchestration.get_distributed_blackboard",
            new=_strict_blackboard,
        ):
            await svc._execute_contraction(proposal, op)
        assert op.agents_removed == ["agent-1"]

    @pytest.mark.asyncio
    async def test_execute_scaling_completed_not_failed_on_blackboard(self):
        """With the args fixed, expansion must end COMPLETED, not FAILED."""
        from core.fleet_orchestration.fleet_scaler_service import (
            ScalingOperationStatus,
        )

        svc = self._service(existing=[("agent-1",)], registry=[MagicMock(id="a2")])
        proposal = self._proposal("expand")
        svc.proposal_service.get_proposal = AsyncMock(return_value=proposal)
        svc.proposal_service._update_proposal_status = AsyncMock()
        svc._persist_operation = AsyncMock()
        with patch(
            "core.fleet_orchestration.get_distributed_blackboard",
            new=_strict_blackboard,
        ):
            op = await svc.execute_scaling("p1")
        assert op.status == ScalingOperationStatus.COMPLETED, op.error_message


# ============================================================================
# 3. realize_blueprint KeyError on malformed LLM blueprint nodes
# ============================================================================
class TestRealizeBlueprintMalformedNodes:
    @pytest.mark.asyncio
    async def test_node_without_id_is_skipped_not_crash(self):
        from core.agents.queen_agent import QueenAgent

        queen = QueenAgent(db=MagicMock(), llm=MagicMock())
        blueprint = {
            "architecture_name": "WF",
            "description": "d",
            "nodes": [
                {"type": "agent", "name": "NoId", "dependencies": []},
                {"id": "a1", "type": "agent", "name": "A", "dependencies": []},
                {"id": "b2", "type": "unknown", "name": "B", "dependencies": ["a1"]},
            ],
        }
        orchestrator = MagicMock()
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orchestrator):
            wf_id = await queen.realize_blueprint(blueprint, tenant_id="t")
        assert wf_id.startswith("ai_wf_")
        wf = orchestrator.register_workflow.call_args.args[0]
        assert [s.step_id for s in wf.steps] == ["a1", "b2"]
        assert wf.steps[1].next_steps == [] or wf.steps[0].next_steps == ["b2"]

    def test_generate_mermaid_skips_node_without_id(self):
        from core.agents.queen_agent import QueenAgent

        queen = QueenAgent(db=MagicMock(), llm=MagicMock())
        blueprint = {
            "nodes": [
                {"type": "agent", "name": "NoId"},
                {"id": "a1", "name": "A", "type": "agent", "dependencies": []},
            ]
        }
        out = queen.generate_mermaid(blueprint, {"a1": "completed"})
        assert 'a1["A\\n(AGENT)"]' in out
        assert "NoId" not in out
        assert "class a1 completed" in out


# ============================================================================
# 4. check_scaling_constraints defined twice (dead duplicate copy)
# ============================================================================
class TestCheckScalingConstraintsSingleDefinition:
    def test_method_defined_once_in_source(self):
        from core.fleet_orchestration import fleet_scaler_service as fss

        src = inspect.getsource(fss)
        assert src.count("def check_scaling_constraints") == 1
