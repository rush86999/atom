"""RED tests — Round 80t2: CLI approvals commands (HITL parity).

    atom-os approvals list                GET /api/agent-governance/pending-approvals
    atom-os approvals approve <id>        POST /api/agent-governance/approve/{id}
    atom-os approvals reject <id>         POST /api/agent-governance/reject/{id}

Same HTTP seam (_integ._request) and auth resolution as integrations/ask/
workflows. RBAC is enforced server-side (TEAM_LEAD+); the CLI just forwards
the stored JWT.
"""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

pytest.importorskip("cli.main")

from cli.main import main_cli  # noqa: E402
from cli import integrations as integ  # noqa: E402


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_request():
    with patch.object(integ, "_request") as m:
        yield m


@pytest.fixture
def authed():
    with patch.object(integ, "_resolve_token", return_value="jwt-hitl"):
        yield


PENDING = {
    "pending_approvals": [
        {"approval_id": "apr-1", "workflow_name": "CI/CD Pipeline",
         "agent_name": "Engineering Agent", "maturity_level": "student"},
        {"approval_id": "apr-2", "workflow_name": "Invoice Export",
         "maturity_level": "intern"},
    ],
    "count": 2,
}


class TestApprovalsList:
    def test_list_prints_pending(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: PENDING)
        result = runner.invoke(main_cli, ["approvals", "list"])
        assert result.exit_code == 0, result.output
        assert "CI/CD Pipeline" in result.output
        assert "Invoice Export" in result.output
        assert "apr-1" in result.output
        method, path = mock_request.call_args[0][:2]
        assert method == "GET"
        assert path == "/api/agent-governance/pending-approvals"

    def test_list_empty(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"pending_approvals": [], "count": 0},
        )
        result = runner.invoke(main_cli, ["approvals", "list"])
        assert result.exit_code == 0
        assert "No pending" in result.output

    def test_list_requires_token(self, runner, mock_request):
        with patch.object(integ, "_resolve_token", return_value=None):
            result = runner.invoke(main_cli, ["approvals", "list"])
            assert result.exit_code != 0
            assert "login" in result.output.lower()


class TestApproveReject:
    def test_approve_posts(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"success": True, "message": "Approved"},
        )
        result = runner.invoke(main_cli, ["approvals", "approve", "apr-1"])
        assert result.exit_code == 0, result.output
        method, path = mock_request.call_args[0][:2]
        assert method == "POST"
        assert path == "/api/agent-governance/approve/apr-1"

    def test_reject_posts(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"success": True, "message": "Rejected"},
        )
        result = runner.invoke(main_cli, ["approvals", "reject", "apr-2"])
        assert result.exit_code == 0
        method, path = mock_request.call_args[0][:2]
        assert method == "POST"
        assert path == "/api/agent-governance/reject/apr-2"

    def test_approve_uses_stored_jwt(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: {"success": True})
        runner.invoke(main_cli, ["approvals", "approve", "apr-1"])
        # auth flows through the resolved token kwarg; _request builds headers
        assert mock_request.call_args.kwargs.get("token") == "jwt-hitl"
