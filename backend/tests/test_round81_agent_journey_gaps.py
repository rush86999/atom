"""Round 81 — Agent journey gap-closure tests.

Verified gaps this round closes:
- G1/G2: the STUDENT training flow and INTERN action-proposal review had NO
  live API surface (``api/maturity_routes.py`` was archived with zero
  replacements), severing STUDENT->INTERN promotion via training and
  proposal approve->execute for INTERN agents.
- G3: ``/api/agent-governance/*`` served hardcoded MOCK_AGENTS instead of
  DB rows, so frontend maturity UI read fake data and /feedback was a no-op.
- G4: ``memory_forget`` (SUPERVISED+ per tools/memory_tool.py complexity=3)
  was absent from ACTION_COMPLEXITY, defaulting to complexity 2 -> an INTERN
  could destroy durable facts at the governance layer.

TDD: these tests failed before the fixes.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, Mock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import (
    AgentRegistry,
    AgentStatus,
    ProposalStatus,
    ProposalType,
    TrainingSession,
    User,
    UserRole,
)


# ============================================================================
# G4 — memory actions must carry explicit complexities
# ============================================================================


class TestMemoryActionComplexity:
    def _svc(self):
        return AgentGovernanceService(MagicMock(spec=Session))

    def test_memory_actions_have_explicit_complexity(self):
        svc = self._svc()
        assert svc.ACTION_COMPLEXITY["memory_search"] == 1
        assert svc.ACTION_COMPLEXITY["memory_remember"] == 2
        assert svc.ACTION_COMPLEXITY["memory_forget"] == 3

    def test_memory_forget_requires_supervised(self):
        """memory_forget resolves to complexity 3, not the level-2 default."""
        svc = self._svc()
        agent = AgentRegistry(
            id="agent_123",
            name="Intern Agent",
            category="testing",
            module_path="t.m",
            class_name="T",
            status=AgentStatus.INTERN.value,
            confidence_score=0.55,
        )
        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.first = Mock(return_value=agent)
        gov = AgentGovernanceService(db)
        result = gov.can_perform_action("agent_123", "memory_forget", _skip_budget=True)
        assert result["allowed"] is False
        assert result["action_complexity"] == 3

    def test_intern_can_remember_and_student_can_search(self):
        agent = AgentRegistry(
            id="agent_123",
            name="Intern Agent",
            category="testing",
            module_path="t.m",
            class_name="T",
            status=AgentStatus.INTERN.value,
            confidence_score=0.55,
        )
        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.first = Mock(return_value=agent)
        gov = AgentGovernanceService(db)
        remember = gov.can_perform_action("agent_123", "memory_remember", _skip_budget=True)
        assert remember["allowed"] is True

        agent.status = AgentStatus.STUDENT.value
        search = gov.can_perform_action("agent_123", "memory_search", _skip_budget=True)
        assert search["allowed"] is True


# ============================================================================
# G1/G2 — /api/maturity/* journey endpoints restored
# ============================================================================


@pytest.fixture
def maturity_app(db_session):
    from api.agent_maturity_routes import router
    from core.auth import get_current_user
    from core.database import get_db as _get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: Mock(
        id="journey-test-user", role="member", status="active"
    )
    app.dependency_overrides[_get_db] = lambda: db_session
    return app


@pytest.fixture
def supervisor_db_session():
    """DB mock whose User lookups resolve to TEAM_LEAD (supervisor gate)."""
    db = Mock(spec=Session)
    supervisor = Mock(spec=User)
    supervisor.id = "journey-test-user"
    supervisor.role = UserRole.TEAM_LEAD.value
    user_filter = Mock()
    user_filter.first = Mock(return_value=supervisor)
    user_query = Mock()
    user_query.filter = Mock(return_value=user_query)

    def query_impl(model, *a, **kw):
        if model is User:
            q = Mock()
            q.filter.return_value = user_filter
            return q
        empty_q = Mock()
        empty_q.filter.return_value = empty_q
        empty_q.order_by.return_value = empty_q
        empty_rows = Mock()
        empty_rows.all.return_value = []
        empty_q.limit.return_value = empty_rows
        empty_q.first.return_value = None
        return empty_q

    db.query = Mock(side_effect=query_impl)
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    return db


@pytest.fixture
def member_db_session():
    db = Mock(spec=Session)
    member = Mock(spec=User)
    member.id = "journey-test-user"
    member.role = UserRole.MEMBER.value
    user_filter = Mock()
    user_filter.first = Mock(return_value=member)
    user_query = Mock()
    user_query.filter.return_value = user_filter

    def query_impl(model, *a, **kw):
        if model is User:
            return user_query
        empty_q = Mock()
        empty_q.filter.return_value = empty_q
        empty_q.order_by.return_value = empty_q
        empty_rows = Mock()
        empty_rows.all.return_value = []
        empty_q.limit.return_value = empty_rows
        empty_q.first.return_value = None
        return empty_q

    db.query = Mock(side_effect=query_impl)
    return db


@pytest.fixture
def supervisor_client(supervisor_db_session):
    from api.agent_maturity_routes import router
    from core.auth import get_current_user
    from core.database import get_db as _get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: Mock(
        id="journey-test-user", role=UserRole.TEAM_LEAD.value, status="active"
    )
    app.dependency_overrides[_get_db] = lambda: supervisor_db_session
    return TestClient(app), supervisor_db_session


@pytest.fixture
def member_client(member_db_session):
    from api.agent_maturity_routes import router
    from core.auth import get_current_user
    from core.database import get_db as _get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: Mock(
        id="journey-test-user", role=UserRole.MEMBER.value, status="active"
    )
    app.dependency_overrides[_get_db] = lambda: member_db_session
    return TestClient(app)


class TestTrainingProposalEndpoints:
    def test_list_training_proposals_returns_rows(self, supervisor_client):
        client, db = supervisor_client
        proposal = Mock(spec=["id", "agent_id", "agent_name", "title", "description",
                              "status", "proposal_data", "created_at",
                              "approved_by", "approved_at"])
        proposal.proposal_data = {
            "capability_gaps": ["email"],
            "learning_objectives": ["obj"],
            "estimated_duration_hours": 12.0,
        }
        proposal.id = "p1"
        proposal.agent_id = "a1"
        proposal.agent_name = "Student Agent"
        proposal.title = "Training: email triage"
        proposal.description = "d"
        proposal.status = ProposalStatus.PENDING_APPROVAL.value
        proposal.created_at = datetime(2026, 8, 21)
        proposal.approved_by = None
        proposal.approved_at = None

        listing_q = Mock()
        listing_q.filter.return_value = listing_q
        listing_q.order_by.return_value = listing_q
        listing_rows = Mock()
        listing_rows.all.return_value = [proposal]
        listing_q.limit.return_value = listing_rows

        def query_impl(model, *a, **kw):
            if model is User:
                q = Mock()
                uf = Mock()
                uf.first.return_value = Mock(id="u", role=UserRole.TEAM_LEAD.value)
                q.filter.return_value = uf
                return q
            return listing_q

        db.query = Mock(side_effect=query_impl)

        resp = client.get("/api/maturity/training/proposals")
        assert resp.status_code == 200
        body = resp.json()
        assert body["proposals"][0]["id"] == "p1"

    def test_approve_training_creates_session(self, supervisor_client):
        client, db = supervisor_client
        session_row = Mock(spec=TrainingSession)
        session_row.id = "sess-1"
        session_row.started_at = datetime(2026, 8, 21)

        with patch(
            "api.agent_maturity_routes.StudentTrainingService"
        ) as svc_cls:
            svc_cls.return_value.approve_training = AsyncMock(return_value=session_row)
            resp = client.post(
                "/api/maturity/training/proposals/p1/approve",
                json={"approve": True},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "sess-1"
        svc_cls.return_value.approve_training.assert_awaited_once()

    def test_approve_training_member_role_forbidden(self, member_client):
        resp = member_client.post(
            "/api/maturity/training/proposals/p1/approve",
            json={"approve": True},
        )
        assert resp.status_code == 403

    def test_complete_training_session_updates_maturity(self, supervisor_client):
        client, db = supervisor_client
        payload = {
            "performance_score": 0.9,
            "supervisor_feedback": "Great",
            "errors_count": 0,
            "tasks_completed": 10,
            "total_tasks": 10,
            "capabilities_developed": ["email"],
            "capability_gaps_remaining": [],
        }
        with patch(
            "api.agent_maturity_routes.StudentTrainingService"
        ) as svc_cls:
            svc_cls.return_value.complete_training_session = AsyncMock(
                return_value={
                    "session_id": "sess-1",
                    "confidence_boost": 0.18,
                    "new_confidence": 0.68,
                    "promoted_to_intern": True,
                }
            )
            resp = client.post(
                "/api/maturity/training/sessions/sess-1/complete", json=payload
            )
        assert resp.status_code == 200
        assert resp.json()["promoted_to_intern"] is True
        svc_cls.return_value.complete_training_session.assert_awaited_once()

    def test_complete_training_invalid_payload_422(self, supervisor_client):
        client, _ = supervisor_client
        resp = client.post(
            "/api/maturity/training/sessions/sess-1/complete",
            json={
                "performance_score": 9.9,  # out of range
                "supervisor_feedback": "x",
                "errors_count": 0,
                "tasks_completed": 1,
                "total_tasks": 1,
            },
        )
        assert resp.status_code == 422

    def test_service_value_error_maps_to_400(self, supervisor_client):
        client, _ = supervisor_client
        with patch(
            "api.agent_maturity_routes.StudentTrainingService"
        ) as svc_cls:
            svc_cls.return_value.approve_training = AsyncMock(
                side_effect=ValueError("Proposal p1 not found")
            )
            resp = client.post(
                "/api/maturity/training/proposals/nope/approve",
                json={"approve": True},
            )
        assert resp.status_code == 400


class TestActionProposalEndpoints:
    def test_approve_action_proposal_executes(self, supervisor_client):
        client, _ = supervisor_client
        with patch("api.agent_maturity_routes.ProposalService") as svc_cls:
            svc_cls.return_value.approve_proposal = AsyncMock(
                return_value={"success": True}
            )
            resp = client.post(
                "/api/maturity/proposals/pr1/approve",
                json={"approve": True},
            )
        assert resp.status_code == 200
        assert resp.json()["execution_result"] == {"success": True}
        svc_cls.return_value.approve_proposal.assert_awaited_once()

    def test_reject_action_proposal(self, supervisor_client):
        client, _ = supervisor_client
        with patch("api.agent_maturity_routes.ProposalService") as svc_cls:
            svc_cls.return_value.reject_proposal = AsyncMock(
                return_value={"proposal_id": "pr1", "status": "REJECTED"}
            )
            resp = client.post(
                "/api/maturity/proposals/pr1/reject", json={"reason": "bad idea"}
            )
        assert resp.status_code == 200
        svc_cls.return_value.reject_proposal.assert_awaited_once()

    def test_proposal_history_endpoint(self, supervisor_client):
        client, db = supervisor_client
        with patch("api.agent_maturity_routes.ProposalService") as svc_cls:
            svc_cls.return_value.get_proposal_history = AsyncMock(
                return_value=[{"id": "pr1"}]
            )
            resp = client.get("/api/maturity/agents/a1/proposal-history")
        assert resp.status_code == 200
        assert resp.json()["proposal_history"] == [{"id": "pr1"}]


# ============================================================================
# G5 — GenericAgent runs linked to a chat session create episodes
# ============================================================================


class TestSessionLinkedEpisodes:
    """Previously only the chat endpoint created episodes; workflow/scheduler
    runs of GenericAgent starved the episode-based graduation criteria."""

    def _make_agent(self):
        from core.generic_agent import GenericAgent

        agent_model = AgentRegistry(
            id="agent-ep-1",
            name="Episode Agent",
            type="assistant",
            module_path="agents.assistant",
            class_name="AssistantAgent",
            category="general",
            configuration={"max_steps": 2},
        )
        return agent_model

    def _harness_patches(self):
        from unittest.mock import AsyncMock as _AsyncMock

        mock_world_model = _AsyncMock()
        mock_world_model.recall_experiences.return_value = {}
        mock_reflection = _AsyncMock()
        mock_reflection.generate_critique = _AsyncMock(return_value=None)
        mock_reflection.get_relevant_critiques = _AsyncMock(return_value=[])
        mock_llm = _AsyncMock()

        async def mock_generate(*args, **kwargs):
            resp = MagicMock()
            resp.thought = "t"
            resp.action = None
            resp.final_answer = "done"
            return resp

        mock_llm.generate_structured = mock_generate
        handler = MagicMock()
        handler.analyze_query_complexity.return_value = MagicMock(value="simple")
        mock_llm._get_handler = MagicMock(return_value=handler)
        mock_mcp = _AsyncMock()
        mock_mcp.get_all_tools.return_value = []
        return mock_world_model, mock_reflection, mock_llm, mock_mcp

    @pytest.mark.asyncio
    async def test_session_linked_run_creates_episode(self):
        from core.generic_agent import GenericAgent

        mw, mr, ml, mmcp = self._harness_patches()
        agent_model = self._make_agent()
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
             patch(
                 "core.generic_agent.AgentGovernanceService"
             ) as gov_cls, \
             budget_patch, \
             patch("core.generic_agent.trigger_episode_creation") as trig:
            gov_cls.return_value.record_outcome = _async_none()
            agent = GenericAgent(agent_model)
            result = await agent.execute("Do thing", context={"session_id": "sess-77"})
            assert result["status"] == "success"
            assert trig.call_count == 1
            _, kwargs = trig.call_args
            assert kwargs["session_id"] == "sess-77"
            assert kwargs["agent_id"] == "agent-ep-1"

    @pytest.mark.asyncio
    async def test_unsessioned_run_skips_episode(self):
        from core.generic_agent import GenericAgent

        mw, mr, ml, mmcp = self._harness_patches()
        agent_model = self._make_agent()
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
             patch("core.generic_agent.trigger_episode_creation") as trig:
            gov_cls.return_value.record_outcome = _async_none()
            agent = GenericAgent(agent_model)
            await agent.execute("Do thing")
            assert trig.call_count == 0


def _async_none():
    from unittest.mock import AsyncMock

    return AsyncMock(return_value=None)


# ============================================================================
# G3 — /api/agent-governance reads real DB rows (no MOCK_AGENTS)
# ============================================================================


@pytest.fixture
def gov_app():
    from api.agent_governance_routes import router as gov_router
    from core.auth import get_current_user
    from core.database import get_db as _get_db

    app = FastAPI()
    app.include_router(gov_router)
    app.dependency_overrides[get_current_user] = lambda: Mock(
        id="gov-test-user", role="member", status="active"
    )
    return app


class TestGovernanceRoutesRealData:
    def test_get_agent_maturity_reads_db_not_mock(self, gov_app):
        db = Mock(spec=Session)
        agent = AgentRegistry(
            id="real-agent",
            name="Real Agent",
            category="ops",
            module_path="t.m",
            class_name="T",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
        )
        db.query.return_value.filter.return_value.first = Mock(return_value=agent)
        from core.database import get_db as _get_db
        gov_app.dependency_overrides[_get_db] = lambda: db
        client = TestClient(gov_app)

        resp = client.get("/api/agent-governance/agents/real-agent")
        assert resp.status_code == 200
        body = resp.json()
        # Real DB row values, not any MOCK_AGENTS entry.
        assert body["agent_id"] == "real-agent"
        assert body["maturity_level"] == "supervised"
        assert body["confidence_score"] == 0.75

    def test_get_agent_maturity_unknown_agent_404(self, gov_app):
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first = Mock(return_value=None)
        from core.database import get_db as _get_db
        gov_app.dependency_overrides[_get_db] = lambda: db
        client = TestClient(gov_app)
        resp = client.get("/api/agent-governance/agents/does-not-exist")
        assert resp.status_code == 404

    def test_feedback_submits_to_governance_service(self, gov_app):
        db = Mock(spec=Session)
        agent = AgentRegistry(
            id="real-agent",
            name="Real Agent",
            category="ops",
            module_path="t.m",
            class_name="T",
            status=AgentStatus.INTERN.value,
            confidence_score=0.55,
        )
        feedback_row = Mock()
        db.query.return_value.filter.return_value.first = Mock(return_value=agent)
        from core.database import get_db as _get_db
        gov_app.dependency_overrides[_get_db] = lambda: db
        client = TestClient(gov_app)

        with patch(
            "api.agent_governance_routes.AgentGovernanceService"
        ) as gov_cls:
            gov_cls.return_value.submit_feedback = AsyncMock(return_value=feedback_row)
            resp = client.post(
                "/api/agent-governance/feedback",
                json={
                    "agent_id": "real-agent",
                    "original_output": "out",
                    "user_correction": "corr",
                },
            )
        assert resp.status_code == 200
        gov_cls.return_value.submit_feedback.assert_awaited_once_with(
            agent_id="real-agent",
            user_id="gov-test-user",
            original_output="out",
            user_correction="corr",
            input_context=None,
        )

    def test_enforce_action_delegates_to_real_governance(self, gov_app):
        """enforce-action must consult the real service, not MOCK_AGENTS."""
        from unittest.mock import MagicMock as _MG
        from contextlib import contextmanager as _cm

        db = Mock(spec=Session)
        agent = AgentRegistry(
            id="real-agent",
            name="Real Agent",
            category="ops",
            module_path="t.m",
            class_name="T",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.30,
        )
        db.query.return_value.filter.return_value.first = Mock(return_value=agent)

        # Hermetic: the handler opens core.database.get_db_session() for the
        # governance call — point BOTH entry points at the mocked session so
        # the test never depends on ambient DATABASE_URL state.
        cm = _cm(lambda: iter([db]))
        from contextlib import nullcontext
        sess_cm = _MG()
        sess_cm.__enter__.return_value = db
        sess_cm.__exit__.return_value = False

        from core.database import get_db as _get_db
        gov_app.dependency_overrides[_get_db] = lambda: db
        client = TestClient(gov_app)

        with patch("api.agent_governance_routes.get_db_session", return_value=sess_cm):
            resp = client.post(
                "/api/agent-governance/enforce-action",
                json={"agent_id": "real-agent", "action_type": "send_email"},
            )
        assert resp.status_code == 200
        body = resp.json()
        # A STUDENT cannot send email — real decision, not a mock lookup.
        assert body["proceed"] is False
        assert body["status"] == "BLOCKED"
