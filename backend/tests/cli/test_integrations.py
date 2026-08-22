"""RED tests — Round 80r: CLI integration parity (desktop/CLI focus).

Web and mobile both have full integration journeys; the `atom-os` CLI had
zero. This adds:

  atom-os login                        POST /api/auth/login, store JWT at
                                       ~/.atom/token (0600)
  atom-os integrations list            GET /api/integrations
  atom-os integrations status          GET /api/v1/integrations/health
  atom-os integrations connect P       GET initiate?format=json, print URL
  atom-os integrations disconnect P    DELETE /api/v1/auth/oauth/tokens/P

All HTTP goes through cli.integrations._request so tests patch one seam.
Token resolution order: --token flag > ATOM_TOKEN env > ~/.atom/token file.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

pytest.importorskip("cli.main")

from click.testing import CliRunner  # noqa: E402

from cli.integrations import integrations_cli, login  # noqa: E402
from cli.main import main_cli  # noqa: E402


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_request():
    """Patch the single HTTP seam used by the module."""
    with patch("cli.integrations._request") as m:
        yield m


class TestLogin:
    def test_login_stores_token_with_restricted_perms(self, runner):
        with runner.isolated_filesystem():
            import os
            os.environ.pop("ATOM_TOKEN", None)
            with patch("cli.integrations._request") as m, \
                 patch("cli.integrations.CLI_HOME", Path(".")):
                m.return_value = MagicMock(status_code=200)
                m.return_value.json.return_value = {"access_token": "jwt-123"}
                result = runner.invoke(login, ["--email", "a@b.com",
                                               "--password", "pw"])
                assert result.exit_code == 0, result.output
                token_file = Path(".") / "token"
                content = token_file.read_text()
                assert content == "jwt-123"
                octal = oct(token_file.stat().st_mode & 0o777)
                assert octal == "0o600", f"token file perms {octal}"

    def test_login_bad_credentials_fails_cleanly(self, runner):
        with runner.isolated_filesystem():
            with patch("cli.integrations._request") as m, \
                 patch("cli.integrations.CLI_HOME", Path(".")):
                m.return_value = MagicMock(status_code=401)
                m.return_value.json.return_value = {"detail": "Incorrect username or password"}
                result = runner.invoke(login, ["--email", "a@b.com", "--password", "bad"])
                assert result.exit_code != 0
                assert "Incorrect username or password" in result.output
                assert not (Path(".") / "token").exists()


class TestIntegrationsList:
    def test_list_prints_catalog(self, runner, mock_request):
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"total": 3, "integrations": ["asana", "slack", "zoho"]},
        )
        result = runner.invoke(main_cli, ["integrations", "list"])
        assert result.exit_code == 0, result.output
        assert "asana" in result.output and "slack" in result.output

    def test_list_requires_token(self, runner, mock_request):
        with patch("cli.integrations._resolve_token", return_value=None):
            result = runner.invoke(main_cli, ["integrations", "list"])
            assert result.exit_code != 0
            assert "login" in result.output.lower()


class TestIntegrationsStatus:
    def test_status_summary(self, runner, mock_request):
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "total_integrations": 30,
                "healthy_integrations": 24,
                "integration_status": [
                    {"service_name": "slack", "status": "healthy"},
                    {"service_name": "zoom", "status": "unhealthy",
                     "error_message": "not configured"},
                ],
            },
        )
        result = runner.invoke(main_cli, ["integrations", "status"])
        assert result.exit_code == 0, result.output
        assert "24 of 30" in result.output
        assert "unhealthy" in result.output


class TestConnect:
    def test_connect_prints_authorization_url(self, runner, mock_request):
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"url": "https://slack.com/oauth?state=x"},
        )
        result = runner.invoke(main_cli, ["integrations", "connect", "slack"])
        assert result.exit_code == 0, result.output
        assert "https://slack.com/oauth?state=x" in result.output

    def test_connect_server_error_fails(self, runner, mock_request):
        resp = MagicMock(status_code=500)
        resp.json.side_effect = ValueError("not json")
        mock_request.return_value = resp
        result = runner.invoke(main_cli, ["integrations", "connect", "slack"])
        assert result.exit_code != 0


class TestDisconnect:
    def test_disconnect_success(self, runner, mock_request):
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": "success",
                          "message": "Revoked slack integration"},
        )
        result = runner.invoke(main_cli, ["integrations", "disconnect", "slack"])
        assert result.exit_code == 0, result.output
        assert "Revoked slack integration" in result.output

    def test_disconnect_not_configured_is_not_fatal(self, runner, mock_request):
        mock_request.return_value = MagicMock(status_code=404)
        mock_request.return_value.json.return_value = {
            "detail": "No integration found for slack"}
        result = runner.invoke(main_cli, ["integrations", "disconnect", "slack"])
        assert result.exit_code == 0, result.output
        assert "not connected" in result.output.lower()

    def test_disconnect_server_error_fails(self, runner, mock_request):
        resp = MagicMock(status_code=502)
        resp.json.side_effect = ValueError("no json")
        mock_request.return_value = resp
        result = runner.invoke(main_cli, ["integrations", "disconnect", "slack"])
        assert result.exit_code != 0
