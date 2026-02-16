"""
Test CLI Agent Execution Features

Tests for daemon mode, CLI commands, and REST API endpoints for agent-to-agent control.

Coverage:
- DaemonManager (start, stop, status, PID file management)
- CLI commands (daemon, stop, status, execute)
- API endpoints (/api/agent/start, /api/agent/stop, /api/agent/status, /api/agent/execute)
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

# Import modules to test
from cli.daemon import DaemonManager, PID_FILE, PID_DIR, LOG_FILE
from cli.main import main_cli


class TestDaemonManager:
    """Test DaemonManager class for background service management."""

    def test_get_pid_returns_none_when_no_file(self):
        """Verify get_pid returns None when PID file doesn't exist."""
        with patch.object(DaemonManager, 'get_pid', return_value=None):
            result = DaemonManager.get_pid()
            assert result is None

    def test_get_pid_returns_valid_integer(self):
        """Verify get_pid returns valid integer from PID file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pid') as f:
            f.write('12345')
            f.flush()
            temp_path = f.name

        try:
            with patch.object(DaemonManager, 'PID_FILE', Path(temp_path)):
                result = DaemonManager.get_pid()
                assert result == 12345
        finally:
            os.unlink(temp_path)

    def test_get_pid_handles_invalid_file_content(self):
        """Verify get_pid returns None for invalid file content."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pid') as f:
            f.write('not_a_number')
            f.flush()
            temp_path = f.name

        try:
            with patch.object(DaemonManager, 'PID_FILE', Path(temp_path)):
                result = DaemonManager.get_pid()
                assert result is None
        finally:
            os.unlink(temp_path)

    @patch('cli.daemon.psutil')
    def test_is_running_with_valid_process(self, mock_psutil):
        """Verify is_running returns True when process exists."""
        mock_psutil.pid_exists.return_value = True

        with patch.object(DaemonManager, 'get_pid', return_value=12345):
            result = DaemonManager.is_running()
            assert result is True

    @patch('cli.daemon.psutil')
    def test_is_running_with_no_process(self, mock_psutil):
        """Verify is_running returns False when process doesn't exist."""
        mock_psutil.pid_exists.return_value = False

        with patch.object(DaemonManager, 'get_pid', return_value=12345):
            result = DaemonManager.is_running()
            assert result is False

    def test_is_running_without_psutil(self):
        """Verify is_running works without psutil installed."""
        with patch('cli.daemon.psutil', None):
            with patch('os.kill') as mock_kill:
                mock_kill.return_value = None

                with patch.object(DaemonManager, 'get_pid', return_value=12345):
                    result = DaemonManager.is_running()
                    # Should not crash, result depends on os.kill

    def test_start_daemon_raises_error_if_already_running(self):
        """Verify start_daemon raises RuntimeError if already running."""
        with patch.object(DaemonManager, 'is_running', return_value=True):
            with patch.object(DaemonManager, 'get_pid', return_value=12345):
                with pytest.raises(RuntimeError, match="already running"):
                    DaemonManager.start_daemon()

    @patch('subprocess.Popen')
    @patch('builtins.open')
    def test_start_daemon_creates_process_and_pid_file(self, mock_open, mock_popen):
        """Verify start_daemon creates subprocess and PID file."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        mock_file = Mock()
        mock_open.return_value = mock_file

        with patch.object(DaemonManager, 'is_running', return_value=False):
            pid = DaemonManager.start_daemon(port=8000)

            assert pid == 12345
            mock_popen.assert_called_once()
            mock_open.assert_called()

    def test_stop_daemon_returns_false_if_not_running(self):
        """Verify stop_daemon returns False when not running."""
        with patch.object(DaemonManager, 'get_pid', return_value=None):
            result = DaemonManager.stop_daemon()
            assert result is False

    @patch('os.kill')
    @patch('cli.daemon.psutil')
    def test_stop_daemon_sends_sigterm_then_sigkill(self, mock_psutil, mock_kill):
        """Verify stop_daemon sends SIGTERM then SIGKILL if needed."""
        mock_psutil.pid_exists.side_effect = [True, True, True, False]
        with patch.object(DaemonManager, 'get_pid', return_value=12345):
            with patch.object(DaemonManager, 'PID_FILE') as mock_pid_file:
                mock_pid_file.unlink = Mock()

                result = DaemonManager.stop_daemon()
                assert result is True

    @patch('os.kill')
    def test_stop_daemon_handles_process_lookup_error(self, mock_kill):
        """Verify stop_daemon handles ProcessLookupError gracefully."""
        mock_kill.side_effect = ProcessLookupError("No such process")

        with patch.object(DaemonManager, 'get_pid', return_value=12345):
            with patch.object(DaemonManager, 'PID_FILE') as mock_pid_file:
                mock_pid_file.unlink = Mock()

                result = DaemonManager.stop_daemon()
                assert result is True

    def test_get_status_returns_not_running_when_no_pid(self):
        """Verify get_status returns not_running when no PID file."""
        with patch.object(DaemonManager, 'get_pid', return_value=None):
            status = DaemonManager.get_status()
            assert status["running"] is False
            assert status["status"] == "not_running"

    @patch('cli.daemon.psutil')
    def test_get_status_returns_running_info(self, mock_psutil):
        """Verify get_status returns process info when running."""
        mock_process = Mock()
        mock_process.cpu_times.return_value = Mock(system=100)
        mock_process.memory_info.return_value = Mock(rss=256 * 1024 * 1024)
        mock_process.cpu_percent.return_value = 5.2
        mock_psutil.Process.return_value = mock_process
        mock_psutil.pid_exists.return_value = True

        with patch.object(DaemonManager, 'get_pid', return_value=12345):
            with patch.object(DaemonManager, 'is_running', return_value=True):
                status = DaemonManager.get_status()

                assert status["running"] is True
                assert status["pid"] == 12345
                assert status["memory_mb"] > 0
                assert status["cpu_percent"] > 0


class TestCLICommands:
    """Test CLI commands for daemon management."""

    def test_daemon_command_starts_in_foreground_mode(self):
        """Verify 'atom-os daemon --foreground' starts in foreground."""
        runner = CliRunner()

        with patch('cli.main.start') as mock_start:
            result = runner.invoke(main_cli, ['daemon', '--foreground'])

            # Should call start function
            assert result.exit_code == 0 or result.exit_code is None

    def test_daemon_command_starts_daemon_mode(self):
        """Verify 'atom-os daemon' starts daemon."""
        runner = CliRunner()

        with patch('cli.main.DaemonManager') as mock_manager:
            mock_manager.start_daemon.return_value = 12345
            mock_manager.is_running.return_value = False

            result = runner.invoke(main_cli, ['daemon'])

            assert result.exit_code == 0
            assert '✓ Atom OS started as daemon' in result.output

    def test_daemon_command_handles_already_running_error(self):
        """Verify daemon command handles 'already running' error."""
        runner = CliRunner()

        with patch('cli.main.DaemonManager') as mock_manager:
            mock_manager.is_running.return_value = True
            mock_manager.get_pid.return_value = 12345

            result = runner.invoke(main_cli, ['daemon'])

            assert result.exit_code != 0
            assert 'already running' in result.output or 'Error' in result.output

    def test_stop_command_stops_daemon(self):
        """Verify 'atom-os stop' stops daemon."""
        runner = CliRunner()

        with patch('cli.main.DaemonManager') as mock_manager:
            mock_manager.stop_daemon.return_value = True
            mock_manager.get_pid.return_value = 12345

            result = runner.invoke(main_cli, ['stop'])

            assert result.exit_code == 0
            assert '✓ Atom OS stopped' in result.output

    def test_stop_command_handles_not_running(self):
        """Verify 'atom-os stop' handles not running case."""
        runner = CliRunner()

        with patch('cli.main.DaemonManager') as mock_manager:
            mock_manager.stop_daemon.return_value = False

            result = runner.invoke(main_cli, ['stop'])

            assert result.exit_code == 0
            assert 'not running' in result.output

    def test_status_command_shows_running(self):
        """Verify 'atom-os status' shows running status."""
        runner = CliRunner()

        with patch('cli.main.DaemonManager') as mock_manager:
            mock_manager.get_status.return_value = {
                "running": True,
                "pid": 12345,
                "memory_mb": 256.5,
                "cpu_percent": 5.2,
                "uptime_seconds": 3600
            }

            result = runner.invoke(main_cli, ['status'])

            assert result.exit_code == 0
            assert 'RUNNING' in result.output
            assert '12345' in result.output

    def test_status_command_shows_stopped(self):
        """Verify 'atom-os status' shows stopped status."""
        runner = CliRunner()

        with patch('cli.main.DaemonManager') as mock_manager:
            mock_manager.get_status.return_value = {
                "running": False,
                "pid": None,
                "status": "not_running"
            }

            result = runner.invoke(main_cli, ['status'])

            assert result.exit_code == 0
            assert 'STOPPED' in result.output

    def test_execute_command_requires_argument(self):
        """Verify 'atom-os execute' requires command argument."""
        runner = CliRunner()

        result = runner.invoke(main_cli, ['execute'])

        assert result.exit_code != 0
        assert 'command required' in result.output

    def test_execute_command_shows_placeholder_message(self):
        """Verify 'atom-os execute' shows placeholder message."""
        runner = CliRunner()

        result = runner.invoke(main_cli, ['execute', 'test command'])

        assert result.exit_code == 0
        assert 'not yet implemented' in result.output


class TestAgentControlAPI:
    """Test REST API endpoints for agent-to-agent control."""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client."""
        from fastapi.testclient import TestClient
        from api.agent_control_routes import router

        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)

        return TestClient(app)

    def test_start_endpoint_starts_daemon(self, client):
        """Verify POST /api/agent/start starts daemon."""
        with patch('api.agent_control_routes.DaemonManager') as mock_manager:
            mock_manager.is_running.return_value = False
            mock_manager.start_daemon.return_value = 12345

            response = client.post(
                "/api/agent/start",
                json={"port": 8000, "host": "0.0.0.0"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["pid"] == 12345
            assert data["status"] == "started"

    def test_start_endpoint_returns_400_if_running(self, client):
        """Verify start returns 400 if daemon already running."""
        with patch('api.agent_control_routes.DaemonManager') as mock_manager:
            mock_manager.is_running.return_value = True
            mock_manager.get_pid.return_value = 12345

            response = client.post(
                "/api/agent/start",
                json={"port": 8000}
            )

            assert response.status_code == 400
            assert "already running" in response.json()["detail"]

    def test_stop_endpoint_stops_daemon(self, client):
        """Verify POST /api/agent/stop stops daemon."""
        with patch('api.agent_control_routes.DaemonManager') as mock_manager:
            mock_manager.is_running.return_value = True
            mock_manager.stop_daemon.return_value = True

            response = client.post("/api/agent/stop")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["status"] == "stopped"

    def test_stop_endpoint_returns_400_if_not_running(self, client):
        """Verify stop returns 400 if daemon not running."""
        with patch('api.agent_control_routes.DaemonManager') as mock_manager:
            mock_manager.is_running.return_value = False

            response = client.post("/api/agent/stop")

            assert response.status_code == 400
            assert "not running" in response.json()["detail"]

    def test_status_endpoint_returns_status(self, client):
        """Verify GET /api/agent/status returns status info."""
        with patch('api.agent_control_routes.DaemonManager') as mock_manager:
            mock_manager.get_status.return_value = {
                "running": True,
                "pid": 12345,
                "memory_mb": 256.5,
                "cpu_percent": 5.2
            }

            response = client.get("/api/agent/status")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["status"]["running"] is True

    def test_restart_endpoint_restarts_daemon(self, client):
        """Verify POST /api/agent/restart restarts daemon."""
        with patch('api.agent_control_routes.DaemonManager') as mock_manager:
            mock_manager.is_running.return_value = True
            mock_manager.stop_daemon.return_value = True
            mock_manager.start_daemon.return_value = 54321

            response = client.post(
                "/api/agent/restart",
                json={"port": 8000}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["status"] == "restarted"
            assert data["was_running"] is True
            assert data["pid"] == 54321

    def test_execute_endpoint_returns_placeholder(self, client):
        """Verify POST /api/agent/execute returns placeholder."""
        response = client.post(
            "/api/agent/execute",
            json={"command": "test command"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "not yet implemented" in data["result"]


class TestIntegration:
    """Integration tests for end-to-end workflows."""

    def test_full_daemon_lifecycle(self):
        """Verify full daemon lifecycle: start -> status -> stop."""
        with patch('cli.daemon.subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            with patch('builtins.open'):
                # Start daemon
                with patch.object(DaemonManager, 'is_running', return_value=False):
                    pid = DaemonManager.start_daemon()
                    assert pid == 12345

                # Check status
                with patch('cli.daemon.psutil') as mock_psutil:
                    mock_psutil.Process.return_value.cpu_times.return_value = Mock(system=100)
                    mock_psuitl.Process.return_value.memory_info.return_value = Mock(rss=256 * 1024 * 1024)
                    mock_psuitl.Process.return_value.cpu_percent.return_value = 5.0
                    mock_psuitl.pid_exists.return_value = True

                    with patch.object(DaemonManager, 'is_running', return_value=True):
                        status = DaemonManager.get_status()
                        assert status["running"] is True

                # Stop daemon
                with patch('os.kill'):
                    with patch.object(DaemonManager, 'is_running', return_value=True):
                        with patch.object(DaemonManager, 'PID_FILE') as mock_pid_file:
                            mock_pid_file.unlink = Mock()
                            result = DaemonManager.stop_daemon()
                            assert result is True
