"""RED tests — Round 80t: CLI `ask` command (terminal agent-chat journey).

`atom-os execute` has been an admitted placeholder ("Command routing not yet
implemented") since introduction, while the REAL one-shot agent journey on
web/mobile is POST /api/chat/message (ChatOrchestrator). This adds:

    atom-os ask "message" [--session ID]   POST /api/chat/message

and repoints `execute`'s guidance at the working command.

All HTTP goes through cli.integrations._request (single test seam).
"""
from unittest.mock import MagicMock, patch
from pathlib import Path

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


def _chat_response():
    r = MagicMock(status_code=200)
    r.json.return_value = {
        "success": True,
        "message": "Report created.",
        "session_id": "sess-1",
        "intent": "report_generation",
        "confidence": 0.93,
    }
    return r


class TestAsk:
    def test_ask_posts_to_chat_api_and_prints_reply(self, runner, mock_request):
        mock_request.return_value = _chat_response()
        result = runner.invoke(main_cli, ["ask", "create a report"])
        assert result.exit_code == 0, result.output
        assert "Report created." in result.output
        method, path = mock_request.call_args[0][:2]
        assert method == "POST"
        assert path == "/api/chat/message"
        body = mock_request.call_args.kwargs.get("json_body")
        assert body["message"] == "create a report"

    def test_ask_session_flag_reused(self, runner, mock_request):
        mock_request.return_value = _chat_response()
        result = runner.invoke(
            main_cli,
            ["ask", "continue", "--session", "sess-9"],
        )
        assert result.exit_code == 0, result.output
        body = mock_request.call_args.kwargs.get("json_body")
        assert body["session_id"] == "sess-9"
        # response session id echoed for follow-ups when --session omitted is
        # the user's concern; here we pinned it explicitly.

    def test_ask_requires_message(self, runner):
        result = runner.invoke(main_cli, ["ask"])
        assert result.exit_code != 0

    def test_ask_connection_error_fails_cleanly(self, runner, mock_request):
        import requests
        mock_request.side_effect = requests.ConnectionError("refused")
        result = runner.invoke(main_cli, ["ask", "hello"])
        assert result.exit_code != 0
        assert "Cannot reach Atom" in result.output

    def test_ask_uses_stored_token(self, runner, mock_request, tmp_path):
        mock_request.return_value = _chat_response()
        # _require_token resolves via os.environ + CLI_HOME/_token_file()
        import os as _os
        env = {k: v for k, v in _os.environ.items() if k != "ATOM_TOKEN"}
        with patch.dict(_os.environ, env, clear=True), \
             patch.object(integ, "CLI_HOME", tmp_path):
            (tmp_path / "token").write_text("jwt-cli")
            result = runner.invoke(main_cli, ["ask", "hello"])
        assert result.exit_code == 0
        # auth flows through the resolved token kwarg; _request builds headers
        assert mock_request.call_args.kwargs.get("token") == "jwt-cli"


class TestExecuteRepointed:
    def test_execute_guides_to_ask(self, runner):
        result = runner.invoke(main_cli, ["execute", "anything"])
        assert result.exit_code == 0
        assert "ask" in result.output.lower()
