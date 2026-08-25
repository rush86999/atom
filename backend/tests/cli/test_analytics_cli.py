"""RED tests — Round 80x: CLI analytics command (completes CLI parity column).

    atom-os analytics [--window 1h|24h|7d|30d]

GET /api/analytics/dashboard/kpis?time_window=… — same endpoint as the
mobile AnalyticsDashboardScreen and desktop AnalyticsPanel.
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
    with patch.object(integ, "_resolve_token", return_value="jwt-an"):
        yield


KPIS = {
    "total_executions": 120,
    "successful_executions": 108,
    "failed_executions": 12,
    "success_rate": 0.9,
    "average_duration_seconds": 14.3,
}


class TestAnalytics:
    def test_kpis_printed(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: KPIS)
        result = runner.invoke(main_cli, ["analytics"])
        assert result.exit_code == 0, result.output
        assert "120" in result.output          # executions
        assert "90%" in result.output          # success rate
        assert "12" in result.output           # failures
        method, path = mock_request.call_args[0][:2]
        assert method == "GET"
        assert path == "/api/analytics/dashboard/kpis?time_window=24h"

    def test_window_option(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(status_code=200, json=lambda: KPIS)
        result = runner.invoke(main_cli,
                               ["analytics", "--window", "7d"])
        assert result.exit_code == 0
        _, path = mock_request.call_args[0][:2]
        assert "time_window=7d" in path

    def test_requires_token(self, runner, mock_request):
        with patch.object(integ, "_resolve_token", return_value=None):
            result = runner.invoke(main_cli, ["analytics"])
            assert result.exit_code != 0
            assert "login" in result.output.lower()

    def test_server_error_fails(self, runner, mock_request):
        resp = MagicMock(status_code=503)
        resp.json.side_effect = ValueError("no json")
        mock_request.return_value = resp
        result = runner.invoke(main_cli, ["analytics"])
        assert result.exit_code != 0
