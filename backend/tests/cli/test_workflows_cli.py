"""RED tests — Round 80w: CLI workflow commands (parity with desktop 80u).

    atom-os workflows list            GET /api/mobile/workflows
    atom-os workflows run <id>        POST /api/mobile/workflows/trigger

Same HTTP seam (cli.integrations._request), same auth resolution.
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
    """Provide a stored token so _require_token passes."""
    with patch.object(integ, "_resolve_token", return_value="jwt-wf"):
        yield


class TestWorkflowsList:
    def test_list_prints_workflows(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"id": "wf-1", "name": "Nightly Report", "status": "active"},
                {"id": "wf-2", "name": "Invoice Sync", "status": "paused"},
            ],
        )
        result = runner.invoke(main_cli, ["workflows", "list"])
        assert result.exit_code == 0, result.output
        assert "Nightly Report" in result.output
        assert "Invoice Sync" in result.output
        method, path = mock_request.call_args[0][:2]
        assert method == "GET"
        assert path == "/api/mobile/workflows"

    def test_list_empty(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: [])
        result = runner.invoke(main_cli, ["workflows", "list"])
        assert result.exit_code == 0
        assert "No workflows" in result.output

    def test_list_requires_token(self, runner, mock_request):
        with patch.object(integ, "_resolve_token", return_value=None):
            result = runner.invoke(main_cli, ["workflows", "list"])
            assert result.exit_code != 0
            assert "login" in result.output.lower()


class TestWorkflowsRun:
    def test_run_posts_trigger(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"execution_id": "exec-77", "status": "running"},
        )
        result = runner.invoke(main_cli, ["workflows", "run", "wf-1"])
        assert result.exit_code == 0, result.output
        method, path = mock_request.call_args[0][:2]
        assert method == "POST"
        assert path == "/api/mobile/workflows/trigger"
        body = mock_request.call_args.kwargs.get("json_body")
        assert body["workflow_id"] == "wf-1"
        assert "exec-77" in result.output

    def test_run_server_error_fails(self, runner, mock_request, authed):
        resp = MagicMock(status_code=503)
        resp.json.side_effect = ValueError("no json")
        mock_request.return_value = resp
        result = runner.invoke(main_cli, ["workflows", "run", "wf-1"])
        assert result.exit_code != 0
