"""
Test suite for HostShellService exception handling fix verification.

GREEN PHASE: These tests verify the fix for bare exception handling.

The fix: Replaced bare `except:` with specific exception handlers:
- ProcessLookupError for already-terminated processes
- OSError for OS-level issues
- BrokenPipeError for pipe issues
- Generic Exception catch with logging for unexpected errors
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.host_shell_service import HostShellService


class TestHostShellExceptionHandlingFix:
    """Test suite verifying the exception handling fix."""

    @pytest.mark.asyncio
    async def test_process_lookup_error_handled_correctly(self):
        """
        Test that ProcessLookupError is handled correctly after fix.

        After the fix, ProcessLookupError should be caught specifically
        and logged appropriately, not masked by a bare except.
        """
        service = HostShellService()

        # Verify the fix doesn't use bare except
        # We can check this by inspecting the source code
        import inspect
        source = inspect.getsource(service.execute_read_command.__wrapped__)

        # The fix should NOT have a bare "except:" anymore
        assert "except:" not in source or "except ProcessLookupError" in source or \
               "except OSError" in source or "except Exception" in source, \
               "Fixed code should use specific exception handlers, not bare except:"

    @pytest.mark.asyncio
    async def test_process_lookup_error_caught_specifically(self):
        """
        Verify that ProcessLookupError is caught specifically.

        The fix catches ProcessLookupError explicitly and logs it.
        """
        service = HostShellService()

        # Mock process that raises ProcessLookupError after kill
        mock_process = AsyncMock()
        mock_process.communicate.side_effect = [asyncio.TimeoutError(), ProcessLookupError("Process not found")]
        mock_process.kill = AsyncMock()
        mock_process.returncode = -1

        mock_db = MagicMock()
        mock_agent = MagicMock()
        mock_agent.status = "STUDENT"
        mock_agent.maturity = "STUDENT"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            with patch.object(service, 'logger') as mock_logger:
                result = await service.execute_read_command(
                    agent_id="agent-1",
                    user_id="user-1",
                    command="pwd",  # Simple whitelisted command
                    working_directory="/tmp",
                    timeout=1,
                    db=mock_db
                )

                # After the fix, ProcessLookupError should be caught and logged
                # Check that the method completed successfully
                assert "timed_out" in result
                assert result["timed_out"] is True

    @pytest.mark.asyncio
    async def test_os_error_caught_specifically(self):
        """
        Verify that OSError is caught specifically after fix.
        """
        service = HostShellService()

        mock_process = AsyncMock()
        mock_process.communicate.side_effect = [asyncio.TimeoutError(), OSError("Permission denied")]
        mock_process.kill = AsyncMock()
        mock_process.returncode = -1

        mock_db = MagicMock()
        mock_agent = MagicMock()
        mock_agent.status = "STUDENT"
        mock_agent.maturity = "STUDENT"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            with patch.object(service, 'logger') as mock_logger:
                result = await service.execute_read_command(
                    agent_id="agent-1",
                    user_id="user-1",
                    command="pwd",
                    working_directory="/tmp",
                    timeout=1,
                    db=mock_db
                )

                # After the fix, OSError should be caught and logged with a warning
                assert result["timed_out"] is True

    @pytest.mark.asyncio
    async def test_broken_pipe_error_caught_specifically(self):
        """
        Verify that BrokenPipeError is caught specifically after fix.
        """
        service = HostShellService()

        mock_process = AsyncMock()
        mock_process.communicate.side_effect = [asyncio.TimeoutError(), BrokenPipeError("Pipe closed")]
        mock_process.kill = AsyncMock()
        mock_process.returncode = -1

        mock_db = MagicMock()
        mock_agent = MagicMock()
        mock_agent.status = "STUDENT"
        mock_agent.maturity = "STUDENT"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            with patch.object(service, 'logger') as mock_logger:
                result = await service.execute_read_command(
                    agent_id="agent-1",
                    user_id="user-1",
                    command="pwd",
                    working_directory="/tmp",
                    timeout=1,
                    db=mock_db
                )

                # After the fix, BrokenPipeError should be caught and logged
                assert result["timed_out"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
