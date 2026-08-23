"""RED tests — Round 80v2: CLI canvas commands (completes the CLI column).

    atom-os canvas list            GET /api/canvas/
    atom-os canvas view <id>       GET /api/canvas/<id>

Same HTTP seam (_integ._request) and auth resolution as all CLI commands.
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
    with patch.object(integ, "_resolve_token", return_value="jwt-canvas"):
        yield


CANVAS_LIST = [
    {"id": "cv-1", "title": "Q3 Dashboard", "canvas_type": "dashboard"},
    {"id": "cv-2", "title": "Sales Funnel", "canvas_type": "chart"},
]


class TestCanvasList:
    def test_list_prints_canvases(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: CANVAS_LIST)
        result = runner.invoke(main_cli, ["canvas", "list"])
        assert result.exit_code == 0, result.output
        assert "Q3 Dashboard" in result.output
        assert "Sales Funnel" in result.output
        method, path = mock_request.call_args[0][:2]
        assert method == "GET"
        assert path == "/api/canvas/"

    def test_list_empty(self, runner, mock_request, authed):
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: [])
        result = runner.invoke(main_cli, ["canvas", "list"])
        assert result.exit_code == 0
        assert "No canvases" in result.output

    def test_list_requires_token(self, runner, mock_request):
        with patch.object(integ, "_resolve_token", return_value=None):
            result = runner.invoke(main_cli, ["canvas", "list"])
            assert result.exit_code != 0
            assert "login" in result.output.lower()


class TestCanvasView:
    def test_view_prints_canvas_data(self, runner, mock_request, authed):
        detail = {"id": "cv-1", "title": "Q3 Dashboard",
                  "components": [{"type": "chart", "data": [1, 2, 3]}]}
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: detail)
        result = runner.invoke(main_cli, ["canvas", "view", "cv-1"])
        assert result.exit_code == 0, result.output
        assert "Q3 Dashboard" in result.output
        method, path = mock_request.call_args[0][:2]
        assert method == "GET"
        assert path == "/api/canvas/cv-1"

    def test_view_not_found_404(self, runner, mock_request, authed):
        resp = MagicMock(status_code=404)
        resp.json.side_effect = ValueError("no json")
        mock_request.return_value = resp
        result = runner.invoke(main_cli, ["canvas", "view", "ghost"])
        assert result.exit_code != 0
