"""
Tests for HostShellService - governed shell command execution.

OpenClaw Integration Tests:
- AUTONOMOUS maturity gate enforcement
- Command whitelist validation
- Blocked command rejection
- Timeout enforcement
- Audit trail logging
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.host_shell_service import host_shell_service, COMMAND_WHITELIST, BLOCKED_COMMANDS
from core.models import ShellSession, AgentRegistry


class TestCommandValidation:
    """Test command validation logic."""

    def test_whitelisted_command_valid(self):
        """Whitelisted commands (ls, cat, grep) are valid."""
        result = host_shell_service.validate_command("ls -la")
        assert result["valid"] is True
        assert result["command"] == "ls"
        assert result["whitelisted"] is True

    def test_blocked_command_invalid(self):
        """Blocked commands (rm, mv, chmod) are rejected."""
        result = host_shell_service.validate_command("rm -rf /")
        assert result["valid"] is False
        assert result["blocked"] is True
        assert "blocked" in result["reason"]

    def test_non_whitelisted_command_invalid(self):
        """Commands not in whitelist are rejected."""
        result = host_shell_service.validate_command("dangerous-command")
        assert result["valid"] is False
        assert "not in whitelist" in result["reason"]
        assert "allowed_commands" in result

    def test_empty_command_invalid(self):
        """Empty commands are rejected."""
        result = host_shell_service.validate_command("")
        assert result["valid"] is False
        assert "Empty command" in result["reason"]


class TestMaturityGate:
    """Test AUTONOMOUS maturity requirement."""

    @pytest.mark.asyncio
    async def test_autonomous_agent_can_execute(self):
        """AUTONOMOUS agents can execute shell commands."""
        with patch('core.host_shell_service.asyncio.create_subprocess_shell') as mock_subprocess:
            # Mock subprocess
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"output", b""))

            mock_subprocess.return_value = mock_process

            # Mock database with AUTONOMOUS agent
            mock_db = Mock()
            mock_agent = Mock()
            mock_agent.status = "AUTONOMOUS"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
            mock_db.add = Mock()
            mock_db.commit = Mock()

            # Execute
            result = await host_shell_service.execute_shell_command(
                agent_id="test-agent",
                user_id="test-user",
                command="ls -la",
                db=mock_db
            )

            assert result["exit_code"] == 0
            assert result["stdout"] == "output"
            assert result["timed_out"] is False

    @pytest.mark.asyncio
    async def test_student_agent_blocked(self):
        """STUDENT agents cannot execute shell commands."""
        # Mock database with STUDENT agent
        mock_db = Mock()
        mock_agent = Mock()
        mock_agent.status = "STUDENT"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        # Should raise PermissionError
        with pytest.raises(PermissionError) as exc_info:
            await host_shell_service.execute_shell_command(
                agent_id="test-agent",
                user_id="test-user",
                command="ls -la",
                db=mock_db
            )

        assert "AUTONOMOUS maturity" in str(exc_info.value)
        assert "STUDENT" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_supervised_agent_blocked(self):
        """SUPERVISED agents cannot execute shell commands."""
        # Mock database with SUPERVISED agent
        mock_db = Mock()
        mock_agent = Mock()
        mock_agent.status = "SUPERVISED"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        with pytest.raises(PermissionError) as exc_info:
            await host_shell_service.execute_shell_command(
                agent_id="test-agent",
                user_id="test-user",
                command="ls -la",
                db=mock_db
            )

        assert "AUTONOMOUS maturity" in str(exc_info.value)


class TestAuditTrail:
    """Test ShellSession audit logging."""

    @pytest.mark.asyncio
    async def test_shell_session_created(self):
        """ShellSession record created for each command."""
        with patch('core.host_shell_service.asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"output", b""))
            mock_subprocess.return_value = mock_process

            # Mock database with AUTONOMOUS agent
            mock_db = Mock()
            mock_agent = Mock()
            mock_agent.status = "AUTONOMOUS"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
            mock_db.add = Mock()
            mock_db.commit = Mock()

            result = await host_shell_service.execute_shell_command(
                agent_id="test-agent",
                user_id="test-user",
                command="ls -la",
                db=mock_db
            )

            # Verify session created
            assert mock_db.add.called
            assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_failed_command_logged(self):
        """Failed commands are logged to audit trail."""
        with patch('core.host_shell_service.asyncio.create_subprocess_shell') as mock_subprocess:
            # Mock failing command
            mock_process = Mock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_subprocess.return_value = mock_process

            # Mock database with AUTONOMOUS agent
            mock_db = Mock()
            mock_agent = Mock()
            mock_agent.status = "AUTONOMOUS"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
            mock_db.add = Mock()
            mock_db.commit = Mock()

            result = await host_shell_service.execute_shell_command(
                agent_id="test-agent",
                user_id="test-user",
                command="ls /nonexistent",
                db=mock_db
            )

            assert result["exit_code"] == 1
            assert result["stderr"] == "error"


class TestTimeoutEnforcement:
    """Test 5-minute timeout enforcement."""

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self):
        """Commands exceeding timeout are killed."""
        with patch('core.host_shell_service.asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = Mock()
            mock_process.kill = Mock()
            # Mock timeout
            mock_process.communicate = AsyncMock(
                side_effect=asyncio.TimeoutError
            )
            mock_subprocess.return_value = mock_process

            # Mock database with AUTONOMOUS agent
            mock_db = Mock()
            mock_agent = Mock()
            mock_agent.status = "AUTONOMOUS"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
            mock_db.add = Mock()
            mock_db.commit = Mock()

            result = await host_shell_service.execute_shell_command(
                agent_id="test-agent",
                user_id="test-user",
                command="sleep 1000",  # Long command
                timeout=1,  # 1 second timeout
                db=mock_db
            )

            assert result["timed_out"] is True
            assert mock_process.kill.called


class TestWorkingDirectoryRestrictions:
    """Test working directory validation."""

    @pytest.mark.asyncio
    async def test_allowed_directory_accepted(self):
        """Working directories in allowed list are accepted."""
        with patch('core.host_shell_service.asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_subprocess.return_value = mock_process

            # Mock database with AUTONOMOUS agent
            mock_db = Mock()
            mock_agent = Mock()
            mock_agent.status = "AUTONOMOUS"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
            mock_db.add = Mock()
            mock_db.commit = Mock()

            with patch.dict(os.environ, {"ATOM_HOST_MOUNT_DIRS": "/tmp:/home:/Users"}):
                result = await host_shell_service.execute_shell_command(
                    agent_id="test-agent",
                    user_id="test-user",
                    command="ls",
                    working_directory="/tmp/project",
                    db=mock_db
                )

                assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_blocked_directory_rejected(self):
        """Working directories not in allowed list are rejected."""
        # Mock database with AUTONOMOUS agent
        mock_db = Mock()
        mock_agent = Mock()
        mock_agent.status = "AUTONOMOUS"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        with patch.dict(os.environ, {"ATOM_HOST_MOUNT_DIRS": "/tmp:/home:/Users"}):
            with pytest.raises(PermissionError) as exc_info:
                await host_shell_service.execute_shell_command(
                    agent_id="test-agent",
                    user_id="test-user",
                    command="ls",
                    working_directory="/etc",  # Not allowed
                    db=mock_db
                )

            assert "not in allowed directories" in str(exc_info.value)
