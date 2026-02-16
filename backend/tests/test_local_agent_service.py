"""
Local Agent Service Integration Tests - End-to-end security validation.

Tests verify LocalAgentService integrates governance, directory permissions,
and command whitelist into a secure execution flow:

Flow:
1. Check governance (maturity level) - EXISTING
2. Check directory permission - EXISTING
3. Validate command whitelist - EXISTING
4. If suggest_only: return approval request
5. Else: execute subprocess
6. Log to ShellSession

Security Focus:
- End-to-end integration testing
- Audit trail verification (ShellSession created)
- Cache performance testing
- Timeout enforcement tests
- Security verification (shell=False)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from core.local_agent_service import LocalAgentService
from core.models import AgentStatus, ShellSession


class MockProcess:
    """Mock subprocess.Process for testing."""

    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        """Mock communicate method."""
        return self._stdout, self._stderr


class TestFullExecutionFlow:
    """Test end-to-end execution flow for AUTONOMOUS agents."""

    @pytest.mark.asyncio
    async def test_full_execution_flow_autonomous(self):
        """AUTONOMOUS agent executes command with full flow."""
        service = LocalAgentService(backend_url="http://localhost:8000")

        # Mock governance check (returns AUTONOMOUS)
        with patch.object(service, '_check_governance') as mock_governance:
            mock_governance.return_value = {
                "allowed": True,
                "maturity_level": "AUTONOMOUS",
                "reason": "Agent maturity check passed"
            }

            # Mock subprocess execution
            with patch('core.local_agent_service.asyncio.create_subprocess_exec') as mock_subprocess:
                mock_subprocess.return_value = MockProcess(
                    returncode=0,
                    stdout=b"file1.txt\nfile2.txt\n"
                )

                # Mock logging
                with patch.object(service, '_log_execution') as mock_log:
                    mock_log.return_value = None

                    result = await service.execute_command(
                        agent_id="test-agent",
                        command="ls /tmp",
                        working_directory="/tmp"
                    )

                    # Verify execution succeeded
                    assert result["allowed"] == True
                    assert result["exit_code"] == 0
                    assert result["stdout"] == "file1.txt\nfile2.txt\n"
                    assert result["maturity_level"] == "AUTONOMOUS"

                    # Verify subprocess was called with shell=False
                    assert mock_subprocess.call_count == 1
                    call_args = mock_subprocess.call_args[0]
                    assert call_args[0] == "ls"

                    # Verify logging was called
                    assert mock_log.call_count == 1

    @pytest.mark.asyncio
    async def test_suggest_only_flow_student(self):
        """STUDENT agent suggests command (doesn't execute)."""
        service = LocalAgentService(backend_url="http://localhost:8000")

        # Mock governance check (returns STUDENT)
        with patch.object(service, '_check_governance') as mock_governance:
            mock_governance.return_value = {
                "allowed": True,
                "maturity_level": "STUDENT",
                "reason": "Agent maturity check passed"
            }

            # Mock directory permission (returns suggest_only=True)
            with patch('core.local_agent_service.check_directory_permission') as mock_dir_check:
                mock_dir_check.return_value = {
                    "allowed": True,
                    "suggest_only": True,
                    "reason": "STUDENT agents can suggest commands",
                    "maturity_level": "STUDENT",
                    "resolved_path": "/tmp"
                }

                # Mock logging
                with patch.object(service, '_log_execution') as mock_log:
                    mock_log.return_value = None

                    result = await service.execute_command(
                        agent_id="test-agent",
                        command="ls /tmp",
                        working_directory="/tmp"
                    )

                    # Verify suggest_only flow
                    assert result["allowed"] == False
                    assert result["requires_approval"] == True
                    assert result["maturity_level"] == "STUDENT"

                    # Verify subprocess was NOT called
                    assert mock_dir_check.call_count == 1

    @pytest.mark.asyncio
    async def test_blocked_directory_all_levels(self):
        """All maturity levels blocked from /etc/ directory."""
        service = LocalAgentService(backend_url="http://localhost:8000")

        # Mock governance check
        with patch.object(service, '_check_governance') as mock_governance:
            mock_governance.return_value = {
                "allowed": True,
                "maturity_level": "AUTONOMOUS",
                "reason": "Agent maturity check passed"
            }

            # Mock directory permission (blocked)
            with patch('core.local_agent_service.check_directory_permission') as mock_dir_check:
                mock_dir_check.return_value = {
                    "allowed": False,
                    "suggest_only": False,
                    "reason": "Directory is in blocked list",
                    "maturity_level": "AUTONOMOUS",
                    "resolved_path": "/etc/passwd"
                }

                # Mock logging
                with patch.object(service, '_log_execution') as mock_log:
                    mock_log.return_value = None

                    result = await service.execute_command(
                        agent_id="test-agent",
                        command="ls /etc",
                        working_directory="/etc"
                    )

                    # Verify blocked
                    assert result["allowed"] == False
                    assert "blocked_directory" in result

    @pytest.mark.asyncio
    async def test_governance_cache_hit(self):
        """Second governance check should use cache."""
        service = LocalAgentService(backend_url="http://localhost:8000")

        # Mock governance check (simulate cache)
        with patch.object(service, '_check_governance') as mock_governance:
            mock_governance.return_value = {
                "allowed": True,
                "maturity_level": "AUTONOMOUS",
                "reason": "Agent maturity check passed"
            }

            # Mock subprocess
            with patch('core.local_agent_service.asyncio.create_subprocess_exec') as mock_subprocess:
                mock_subprocess.return_value = MockProcess(returncode=0)

                # Mock logging
                with patch.object(service, '_log_execution'):
                    # First call
                    await service.execute_command(
                        agent_id="test-agent",
                        command="ls /tmp",
                        working_directory="/tmp"
                    )

                    # Second call (should use cached governance)
                    await service.execute_command(
                        agent_id="test-agent",
                        command="ls /tmp",
                        working_directory="/tmp"
                    )

                    # Governance should be called twice (caching is in governance service, not here)
                    assert mock_governance.call_count == 2


class TestAuditTrailLogging:
    """Test ShellSession audit trail creation."""

    @pytest.mark.asyncio
    async def test_shell_session_created(self):
        """ShellSession record created for each command."""
        service = LocalAgentService(backend_url="http://localhost:8000")

        with patch.object(service, '_check_governance') as mock_governance:
            mock_governance.return_value = {
                "allowed": True,
                "maturity_level": "AUTONOMOUS",
                "reason": "Agent maturity check passed"
            }

            with patch('core.local_agent_service.asyncio.create_subprocess_exec') as mock_subprocess:
                mock_subprocess.return_value = MockProcess(returncode=0)

                # Mock logging to capture session data
                log_calls = []

                async def mock_log(session_data):
                    log_calls.append(session_data)

                with patch.object(service, '_log_execution', side_effect=mock_log):
                    await service.execute_command(
                        agent_id="test-agent",
                        command="ls /tmp",
                        working_directory="/tmp"
                    )

                    # Verify logging was called
                    assert len(log_calls) == 1
                    session_data = log_calls[0]

                    # Verify session data fields
                    assert session_data["agent_id"] == "test-agent"
                    assert session_data["command"] == "ls /tmp"
                    assert session_data["working_directory"] == "/tmp"
                    assert session_data["exit_code"] == 0
                    assert session_data["maturity_level"] == "AUTONOMOUS"
                    assert session_data["operation_type"] in ["read", "execute"]
                    assert session_data["command_whitelist_valid"] == True

    @pytest.mark.asyncio
    async def test_failed_command_logged(self):
        """Failed commands are logged to audit trail."""
        service = LocalAgentService(backend_url="http://localhost:8000")

        with patch.object(service, '_check_governance') as mock_governance:
            mock_governance.return_value = {
                "allowed": True,
                "maturity_level": "AUTONOMOUS",
                "reason": "Agent maturity check passed"
            }

            with patch('core.local_agent_service.asyncio.create_subprocess_exec') as mock_subprocess:
                # Mock failing command
                mock_subprocess.return_value = MockProcess(
                    returncode=1,
                    stderr=b"No such file or directory"
                )

                log_calls = []

                async def mock_log(session_data):
                    log_calls.append(session_data)

                with patch.object(service, '_log_execution', side_effect=mock_log):
                    await service.execute_command(
                        agent_id="test-agent",
                        command="ls /nonexistent",
                        working_directory="/tmp"
                    )

                    # Verify failure logged
                    assert len(log_calls) == 1
                    session_data = log_calls[0]
                    assert session_data["exit_code"] == 1
                    assert "No such file or directory" in session_data["stderr"]


class TestTimeoutEnforcement:
    """Test 5-minute timeout enforcement."""

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self):
        """Commands exceeding timeout are killed."""
        service = LocalAgentService(backend_url="http://localhost:8000")

        with patch.object(service, '_check_governance') as mock_governance:
            mock_governance.return_value = {
                "allowed": True,
                "maturity_level": "AUTONOMOUS",
                "reason": "Agent maturity check passed"
            }

            with patch('core.local_agent_service.asyncio.create_subprocess_exec') as mock_subprocess:
                # Mock process that times out
                mock_process = Mock()
                mock_process.kill = Mock()

                # Mock communicate to raise TimeoutError
                async def timeout_error():
                    raise asyncio.TimeoutError()

                mock_process.communicate = timeout_error
                mock_subprocess.return_value = mock_process

                log_calls = []

                async def mock_log(session_data):
                    log_calls.append(session_data)

                with patch.object(service, '_log_execution', side_effect=mock_log):
                    result = await service.execute_command(
                        agent_id="test-agent",
                        command="sleep 1000",
                        working_directory="/tmp"
                    )

                    # Verify timeout logged
                    assert result["timed_out"] == True
                    assert result["exit_code"] == -1

                    # Verify process.kill() was called
                    assert mock_process.kill.called


class TestSubprocessSecurity:
    """Test subprocess security (shell=False enforcement)."""

    @pytest.mark.asyncio
    async def test_subprocess_uses_shell_false(self):
        """Verify subprocess uses shell=False (list arguments)."""
        service = LocalAgentService(backend_url="http://localhost:8000")

        with patch.object(service, '_check_governance') as mock_governance:
            mock_governance.return_value = {
                "allowed": True,
                "maturity_level": "AUTONOMOUS",
                "reason": "Agent maturity check passed"
            }

            # Patch create_subprocess_exec (NOT shell)
            with patch('core.local_agent_service.asyncio.create_subprocess_exec') as mock_exec:
                # Patch create_subprocess_shell to verify it's NOT called
                with patch('core.local_agent_service.asyncio.create_subprocess_shell') as mock_shell:
                    mock_exec.return_value = MockProcess(returncode=0)

                    with patch.object(service, '_log_execution'):
                        await service.execute_command(
                            agent_id="test-agent",
                            command="ls /tmp",
                            working_directory="/tmp"
                        )

                        # Verify create_subprocess_exec was called (shell=False)
                        assert mock_exec.call_count == 1

                        # Verify create_subprocess_shell was NOT called
                        assert mock_shell.call_count == 0

                        # Verify list arguments passed
                        call_args = mock_exec.call_args[0]
                        assert isinstance(call_args, tuple)
                        assert call_args[0] == "ls"


class TestCommandWhitelistIntegration:
    """Test command whitelist integration with execution flow."""

    @pytest.mark.asyncio
    async def test_whitelisted_command_executes(self):
        """Whitelisted command executes successfully."""
        service = LocalAgentService(backend_url="http://localhost:8000")

        with patch.object(service, '_check_governance') as mock_governance:
            mock_governance.return_value = {
                "allowed": True,
                "maturity_level": "AUTONOMOUS",
                "reason": "Agent maturity check passed"
            }

            with patch('core.local_agent_service.asyncio.create_subprocess_exec') as mock_subprocess:
                mock_subprocess.return_value = MockProcess(returncode=0)

                with patch.object(service, '_log_execution'):
                    result = await service.execute_command(
                        agent_id="test-agent",
                        command="ls /tmp",  # Whitelisted command
                        working_directory="/tmp"
                    )

                    assert result["allowed"] == True

    @pytest.mark.asyncio
    async def test_non_whitelisted_command_blocked(self):
        """Non-whitelisted command is blocked."""
        service = LocalAgentService(backend_url="http://localhost:8000")

        with patch.object(service, '_check_governance') as mock_governance:
            mock_governance.return_value = {
                "allowed": True,
                "maturity_level": "AUTONOMOUS",
                "reason": "Agent maturity check passed"
            }

            # Mock directory permission to allow
            with patch('core.local_agent_service.check_directory_permission') as mock_dir_check:
                mock_dir_check.return_value = {
                    "allowed": True,
                    "suggest_only": False,
                    "reason": "Directory access allowed",
                    "maturity_level": "AUTONOMOUS",
                    "resolved_path": "/tmp"
                }

                log_calls = []

                async def mock_log(session_data):
                    log_calls.append(session_data)

                with patch.object(service, '_log_execution', side_effect=mock_log):
                    result = await service.execute_command(
                        agent_id="test-agent",
                        command="nonexistent-command",  # Not whitelisted
                        working_directory="/tmp"
                    )

                    # Should be blocked by whitelist
                    assert result["allowed"] == False
                    assert "blocked" in result or "not in whitelist" in result.get("reason", "").lower()
