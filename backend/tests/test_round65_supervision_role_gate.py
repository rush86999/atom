"""
Round 65 — Supervision endpoints: missing role gate (governance integrity)
(Red-Green-Refactor).

api/supervision_routes.py lets ANY authenticated user act as a supervisor:

  A. POST /sessions/{id}/intervene — pause/correct/terminate any agent
     execution session (cross-user execution control).
  B. POST /sessions/{id}/complete — rate sessions and BOOST agent confidence
     (maturity manipulation — repeated 5-star ratings push agents toward
     higher governance tiers).
  C. POST /proposals/{id}/autonomous-approve — trigger autonomous review
     which EXECUTES the proposal's action on approval — any member can
     fast-track governance-gated actions through the reviewer.

The established pattern (agent_governance_routes.approve_workflow, R39)
requires TEAM_LEAD/WORKSPACE_ADMIN/SUPER_ADMIN for approval actions.
Mirror it here.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db
from core.models import UserRole


def make_client(user_role="member"):
    from api.supervision_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
        id="u-65", email="u@example.com"
    )

    db = MagicMock()
    db_user = MagicMock()
    db_user.id = "u-65"
    db_user.role = user_role
    db.query.return_value.filter.return_value.first.return_value = db_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False), db


class TestSupervisionRoleGate:
    def test_intervene_denied_for_member(self):
        client, _ = make_client(user_role="member")

        with patch(
            "api.supervision_routes.SupervisionService"
        ) as svc:
            resp = client.post(
                "/api/supervision/sessions/s1/intervene",
                json={"intervention_type": "pause", "guidance": "stop"},
            )

        assert resp.status_code == 403, (
            f"member could intervene in agent execution (got {resp.status_code})"
        )
        svc.return_value.intervene.assert_not_called()

    def test_complete_denied_for_member(self):
        client, _ = make_client(user_role="member")

        with patch(
            "api.supervision_routes.SupervisionService"
        ) as svc:
            resp = client.post(
                "/api/supervision/sessions/s1/complete?supervisor_rating=5&feedback=great",
            )

        assert resp.status_code == 403, (
            f"member could rate a session and boost agent confidence "
            f"(got {resp.status_code})"
        )
        svc.return_value.complete_supervision.assert_not_called()

    def test_autonomous_approve_denied_for_member(self):
        client, _ = make_client(user_role="member")

        with patch(
            "core.proposal_service.ProposalService"
        ) as svc:
            resp = client.post("/api/supervision/proposals/p1/autonomous-approve")

        assert resp.status_code == 403, (
            f"member could trigger autonomous approval+execution of a proposal "
            f"(got {resp.status_code})"
        )
        svc.return_value.autonomous_approve_or_reject.assert_not_called()

    def test_intervene_allowed_for_team_lead(self):
        client, _ = make_client(user_role=UserRole.TEAM_LEAD.value)

        with patch(
            "api.supervision_routes.SupervisionService"
        ) as svc:
            svc.return_value.intervene = AsyncMock(
                return_value=MagicMock(
                    success=True, message="paused", session_state="paused"
                )
            )
            resp = client.post(
                "/api/supervision/sessions/s1/intervene",
                json={"intervention_type": "pause", "guidance": "stop"},
            )

        assert resp.status_code == 200, resp.text
        svc.return_value.intervene.assert_called_once()

    def test_autonomous_approve_allowed_for_admin(self):
        client, _ = make_client(user_role=UserRole.SUPER_ADMIN.value)

        with patch(
            "core.proposal_service.ProposalService"
        ) as svc:
            svc.return_value.autonomous_approve_or_reject = AsyncMock(
                return_value={
                    "success": False,
                    "message": "Human supervisor available",
                }
            )
            resp = client.post("/api/supervision/proposals/p1/autonomous-approve")

        assert resp.status_code == 200, resp.text
        svc.return_value.autonomous_approve_or_reject.assert_called_once()
