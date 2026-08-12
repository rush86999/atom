"""
E2E tests for agent governance enforcement (AGENT-04, AGENT-05, AGNT-06).

Rewritten 2026-08-12: the chat-approval-dialog UI no longer exists, so
governance is asserted API-first against the real enforcement surface:

- GET  /api/agent-governance/rules           — maturity matrix definitions
- POST /api/agent-governance/enforce-action  — per-tier action decisions
                                              (BLOCKED / PENDING_APPROVAL / APPROVED)
- POST /api/agent-governance/approve/{id}    — approver-role enforcement
- POST /api/agents/{id}/run                  — state gate (paused agents)

Run with: pytest backend/tests/e2e_ui/tests/test_agent_governance.py -v
"""

import uuid
import requests

from core.models import AgentRegistry

API_BASE = "http://localhost:8001"

# Mock-agency matrix backed by /api/agent-governance/enforce-action. The
# endpoint derives maturity from the seeded confidence score per agent:
#   engineering-agent 0.45 -> student
#   productivity-agent 0.55 -> intern
#   sales-agent        0.85 -> supervised
#   finance-agent      0.92 -> autonomous
MATRIX = {
    "student": ("engineering-agent", 0.45),
    "intern": ("productivity-agent", 0.55),
    "supervised": ("sales-agent", 0.85),
    "autonomous": ("finance-agent", 0.92),
}


def enforce_action(token: str, agent_id: str, action_type: str) -> dict:
    """Call the real governance enforcement endpoint."""
    response = requests.post(
        f"{API_BASE}/api/agent-governance/enforce-action",
        headers={"Authorization": f"Bearer {token}"},
        json={"agent_id": agent_id, "action_type": action_type},
        timeout=15,
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestAgentGovernanceEnforcement:
    """API-level governance enforcement tests (AGENT-04/05, AGNT-06)."""

    def test_student_agent_blocked_from_restricted_actions(self, setup_test_user):
        """STUDENT agents are blocked from complexity-2+ actions.

        1. Rules: student max_complexity == 1, requires_approval True
        2. enforce-action(student, "delete") -> BLOCKED
        3. enforce-action(student, "create") -> BLOCKED
        4. enforce-action(student, "search") -> APPROVED (read-only tier)

        Coverage: AGENT-04 (STUDENT read-only enforcement)
        """
        token = setup_test_user["access_token"]
        rules = requests.get(
            f"{API_BASE}/api/agent-governance/rules",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        ).json()["maturity_levels"]
        assert rules["student"]["max_complexity"] == 1
        assert rules["student"]["requires_approval"] is True

        agent_id, _ = MATRIX["student"]
        blocked = enforce_action(token, agent_id, "delete")
        assert blocked["status"] == "BLOCKED"
        assert blocked["proceed"] is False
        assert "cannot perform" in blocked["reason"].lower()
        assert blocked["required_status"] == "autonomous"

        blocked_create = enforce_action(token, agent_id, "create")
        assert blocked_create["status"] == "BLOCKED"
        assert blocked_create["required_status"] == "supervised"

        allowed = enforce_action(token, agent_id, "search")
        assert allowed["status"] == "APPROVED"
        assert allowed["proceed"] is True

    def test_intern_agent_requires_approval(self, setup_test_user):
        """INTERN agents cannot execute without approval.

        1. Rules: intern max_complexity == 2, requires_approval True
        2. enforce-action(intern, "create") -> BLOCKED (needs SUPERVISED)
        3. enforce-action(intern, "analyze") -> APPROVED (tier-2 action)

        Coverage: AGENT-05 / AGNT-06 (INTERN approval requirement)
        """
        token = setup_test_user["access_token"]
        rules = requests.get(
            f"{API_BASE}/api/agent-governance/rules",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        ).json()["maturity_levels"]
        assert rules["intern"]["max_complexity"] == 2
        assert rules["intern"]["requires_approval"] is True

        agent_id, _ = MATRIX["intern"]
        blocked = enforce_action(token, agent_id, "create")
        assert blocked["status"] == "BLOCKED"
        assert blocked["required_status"] == "supervised"

        allowed = enforce_action(token, agent_id, "analyze")
        assert allowed["status"] == "APPROVED"
        assert allowed["proceed"] is True

    def test_supervised_agent_requires_approval_for_complex_actions(self, setup_test_user):
        """SUPERVISED agents execute but complex actions need oversight.

        1. Rules: supervised requires_approval == "for_complex_actions"
        2. enforce-action(supervised, "create", complexity 3)
           -> PENDING_APPROVAL
        3. enforce-action(supervised, "search", complexity 1) -> APPROVED

        Coverage: AGENT-05 / AGNT-06 (SUPERVISED oversight)
        """
        token = setup_test_user["access_token"]
        rules = requests.get(
            f"{API_BASE}/api/agent-governance/rules",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        ).json()["maturity_levels"]
        assert rules["supervised"]["requires_approval"] == "for_complex_actions"

        agent_id, _ = MATRIX["supervised"]
        pending = enforce_action(token, agent_id, "create")
        assert pending["status"] == "PENDING_APPROVAL"
        assert pending["proceed"] is True
        assert pending["action_required"] == "WAIT_FOR_APPROVAL"

        allowed = enforce_action(token, agent_id, "search")
        assert allowed["status"] == "APPROVED"
        assert allowed["proceed"] is True

    def test_autonomous_agent_full_execution(self, setup_test_user):
        """AUTONOMOUS agents execute critical actions immediately.

        1. Rules: autonomous requires_approval False
        2. enforce-action(autonomous, "delete") -> APPROVED

        Coverage: AGNT-06 (AUTONOMOUS full execution)
        """
        token = setup_test_user["access_token"]
        rules = requests.get(
            f"{API_BASE}/api/agent-governance/rules",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        ).json()["maturity_levels"]
        assert rules["autonomous"]["requires_approval"] is False
        assert rules["autonomous"]["max_complexity"] == 4

        agent_id, _ = MATRIX["autonomous"]
        allowed = enforce_action(token, agent_id, "delete")
        assert allowed["status"] == "APPROVED"
        assert allowed["proceed"] is True
        assert allowed["action_required"] is None

    def test_governance_maturity_progression(self, setup_test_user):
        """Verify the enforcement matrix across all four maturity tiers."""
        token = setup_test_user["access_token"]

        expectations = {
            # tier: (action, expected status, expected required tier)
            "student": ("delete", "BLOCKED", "autonomous"),
            "intern": ("create", "BLOCKED", "supervised"),
            "supervised": ("create", "PENDING_APPROVAL", None),
            "autonomous": ("delete", "APPROVED", None),
        }
        for tier, (action, expected_status, required) in expectations.items():
            agent_id, _ = MATRIX[tier]
            result = enforce_action(token, agent_id, action)
            assert result["status"] == expected_status, (
                f"{tier} agent + {action}: expected {expected_status}, "
                f"got {result['status']} ({result['reason']})"
            )
            assert result["agent_status"] == tier, result
            if required:
                assert result["required_status"] == required, result

    def test_approval_workflow_requires_approver_role(self, setup_test_user, admin_user):
        """Approval decisions are restricted to approver roles.

        1. Member POST /api/agent-governance/approve/{id} -> 403
           PERMISSION_DENIED (TEAM_LEAD+ required)
        2. Admin (super_admin) approve of a non-existent approval -> 400
           APPROVAL_FAILED (real service path, no false success)

        Coverage: AGENT-05 (Approval workflow enforcement)
        """
        token = setup_test_user["access_token"]
        _, admin_token = admin_user

        member_attempt = requests.post(
            f"{API_BASE}/api/agent-governance/approve/apr_member_probe",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert member_attempt.status_code == 403, member_attempt.text

        admin_attempt = requests.post(
            f"{API_BASE}/api/agent-governance/approve/apr_missing_approval",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert admin_attempt.status_code == 400, admin_attempt.text
        assert admin_attempt.json()["error"]["code"] == "APPROVAL_FAILED"

    def test_paused_agent_governance_gate(self, db_session, setup_test_user):
        """Paused agents are blocked by the execution state gate.

        1. Seed a paused agent
        2. POST /api/agents/{id}/run -> 400 AGENT_INVALID_STATE
        3. No AgentExecution record created

        Coverage: AGNT-06 (Governance state gate)
        """
        from core.models import AgentExecution
        agent = AgentRegistry(
            name=f"Governance Paused {str(uuid.uuid4())[:8]}",
            status="paused",
            category="testing",
            module_path="core.generic_agent",
            class_name="GenericAgent",
            workspace_id="default",
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        response = requests.post(
            f"{API_BASE}/api/agents/{agent.id}/run",
            headers={"Authorization": f"Bearer {setup_test_user['access_token']}"},
            json={"parameters": {}},
            timeout=15,
        )
        assert response.status_code == 400, response.text
        assert response.json()["error"]["code"] == "AGENT_INVALID_STATE"

        executions = db_session.query(AgentExecution).filter_by(agent_id=agent.id).all()
        assert len(executions) == 0, "Blocked run must not create executions"
