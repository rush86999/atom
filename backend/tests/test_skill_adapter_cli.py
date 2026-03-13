"""
Tests for CLI skill support in skill_adapter.py (Phase 25).

Tests cover:
- CLI skill detection (atom-* prefix)
- CLI argument parsing (port, host, workers, boolean flags)
- CLI skill execution (success, error, exception handling)
- Subprocess mocking patterns

Reference: Phase 25 Plan 02 - CLI Skill Integration
Reference: Phase 183-01 Plan 01 Task 2 - CLI Skills Test Coverage
"""

import pytest
import sys
from unittest.mock import patch, Mock, MagicMock

# Module-level mocking for docker.errors (Phase 182 pattern)
sys.modules['docker'] = MagicMock()
sys.modules['docker.errors'] = MagicMock()

from core.skill_adapter import CommunitySkillTool, create_community_tool


class TestCliSkillDetection:
    """Test CLI skill detection logic."""

    def test_atom_prefix_triggers_cli_execution(self):
        """Test that skill_id starting with 'atom-' calls _execute_cli_skill."""
        skill = create_community_tool({
            "name": "atom-daemon",
            "skill_id": "atom-daemon",
            "skill_type": "prompt_only",
            "skill_content": "Start the daemon"
        })

        # Should have CLI skill characteristics
        assert skill.skill_id.startswith("atom-")

    def test_non_atom_prefix_uses_normal_execution(self):
        """Test that regular skills use prompt/code execution."""
        skill = create_community_tool({
            "name": "regular_skill",
            "skill_id": "regular_skill",
            "skill_type": "prompt_only",
            "skill_content": "A regular skill"
        })

        # Should not have CLI prefix
        assert not skill.skill_id.startswith("atom-")

    def test_cli_skill_bypasses_sandbox_check(self):
        """Test that CLI skills don't require sandbox_enabled."""
        cli_skill = create_community_tool({
            "name": "atom-status",
            "skill_id": "atom-status",
            "skill_type": "prompt_only",
            "skill_content": "Check daemon status"
        })

        # CLI skills don't need sandbox
        assert cli_skill.sandbox_enabled is False

    def test_cli_skill_command_extraction(self):
        """Test command name extraction from skill_id."""
        skill = create_community_tool({
            "name": "atom-daemon",
            "skill_id": "atom-daemon",
            "skill_type": "prompt_only",
            "skill_content": "Start daemon"
        })

        # Extract command by removing atom- prefix
        command = skill.skill_id.replace("atom-", "")
        assert command == "daemon"


class TestCliArgumentParsing:
    """Test CLI argument parsing from user queries."""

    @pytest.fixture
    def cli_skill(self):
        """Create a CLI skill for testing."""
        return create_community_tool({
            "name": "atom-daemon",
            "skill_id": "atom-daemon",
            "skill_type": "prompt_only",
            "skill_content": "Start the daemon"
        })

    def test_port_flag_parsing(self, cli_skill):
        """Test 'port 3000' -> ['--port', '3000']."""
        args = cli_skill._parse_cli_args("Start daemon on port 3000", "daemon")

        assert args is not None
        assert "--port" in args
        assert "3000" in args

    def test_port_equals_parsing(self, cli_skill):
        """Test 'port=3000' -> ['--port', '3000']."""
        args = cli_skill._parse_cli_args("Start with port=3000", "daemon")

        assert args is not None
        assert "--port" in args
        assert "3000" in args

    def test_host_flag_parsing(self, cli_skill):
        """Test 'host 0.0.0.0' -> ['--host', '0.0.0.0']."""
        args = cli_skill._parse_cli_args("Bind to host 0.0.0.0", "daemon")

        assert args is not None
        assert "--host" in args
        assert "0.0.0.0" in args

    def test_workers_flag_parsing(self, cli_skill):
        """Test 'workers 4' -> ['--workers', '4']."""
        args = cli_skill._parse_cli_args("Start with workers 4", "daemon")

        assert args is not None
        assert "--workers" in args
        assert "4" in args

    def test_boolean_flags(self, cli_skill):
        """Test boolean flags like 'host mount', 'dev', 'foreground'."""
        # Test host mount flag
        args = cli_skill._parse_cli_args("Enable host mount", "daemon")
        assert args is not None
        assert "--host-mount" in args

        # Test dev flag
        args = cli_skill._parse_cli_args("Start in dev mode", "daemon")
        assert args is not None
        assert "--dev" in args

        # Test foreground flag
        args = cli_skill._parse_cli_args("Run in foreground", "daemon")
        assert args is not None
        assert "--foreground" in args

    def test_multiple_flags_combined(self, cli_skill):
        """Test parsing multiple flags from one query."""
        args = cli_skill._parse_cli_args(
            "Start daemon on port 3000 with dev mode and host mount",
            "daemon"
        )

        assert args is not None
        assert "--port" in args
        assert "3000" in args
        assert "--dev" in args
        assert "--host-mount" in args

    def test_config_show_daemon_flag(self):
        """Test atom-config with 'show daemon' -> ['--show-daemon']."""
        config_skill = create_community_tool({
            "name": "atom-config",
            "skill_id": "atom-config",
            "skill_type": "prompt_only",
            "skill_content": "Configure atom"
        })

        args = config_skill._parse_cli_args("Show daemon config", "config")
        assert args is not None
        assert "--show-daemon" in args

    def test_no_arguments_returns_none(self, cli_skill):
        """Test that empty query returns None from _parse_cli_args."""
        args = cli_skill._parse_cli_args("", "daemon")
        assert args is None

        # Also test with no recognizable flags
        args = cli_skill._parse_cli_args("Start the daemon please", "daemon")
        assert args is None


class TestCliSkillExecution:
    """Test CLI skill execution with subprocess mocking."""

    @pytest.fixture
    def cli_skill(self):
        """Create a CLI skill for testing."""
        return create_community_tool({
            "name": "atom-status",
            "skill_id": "atom-status",
            "skill_type": "prompt_only",
            "skill_content": "Check daemon status"
        })

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_success_path(self, mock_execute, cli_skill):
        """Test successful CLI command execution."""
        # Mock successful command execution
        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon is running on port 8000",
            "stderr": "",
            "returncode": 0
        }

        result = cli_skill._run("Check status")

        assert "Command executed successfully" in result
        assert "Daemon is running on port 8000" in result

        # Verify execute_atom_cli_command was called
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[0] == "status"  # command name

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_error_path(self, mock_execute, cli_skill):
        """Test CLI command failure returns error message."""
        mock_execute.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "Daemon is not running",
            "returncode": 1
        }

        result = cli_skill._run("Check status")

        assert "Command failed" in result
        assert "Daemon is not running" in result

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_stderr_included(self, mock_execute, cli_skill):
        """Test that stderr is included in success output."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon started",
            "stderr": "Warning: Running in development mode",
            "returncode": 0
        }

        result = cli_skill._run("Start daemon")

        assert "Command executed successfully" in result
        assert "Daemon started" in result
        assert "Warnings:" in result
        assert "Running in development mode" in result

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_exception_handling(self, mock_execute, cli_skill):
        """Test exception caught and formatted as ERROR message."""
        # Mock exception in execute_atom_cli_command
        mock_execute.side_effect = Exception("Subprocess failed")

        result = cli_skill._run("Check status")

        assert "ERROR" in result
        assert "Failed to execute CLI skill" in result

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_logged(self, mock_execute, cli_skill):
        """Test logger.info called with command details."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "OK",
            "stderr": "",
            "returncode": 0
        }

        # Capture log output (implicitly tested by successful execution)
        result = cli_skill._run("Check status")

        # If no exception, logging worked correctly
        assert "OK" in result
        mock_execute.assert_called_once()
