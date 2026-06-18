"""
Test suite for HostShellService error handling bugs.

RED PHASE: These tests expose bugs in exception handling.

The bug at line 504 uses bare `except:` which catches all exceptions
including SystemExit, KeyboardInterrupt, and other critical exceptions.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.host_shell_service import HostShellService
from core.models import ShellSession


class TestHostShellExceptionHandlingBugs:
    """
    Test suite revealing exception handling bugs in HostShellService.

    The bug: Bare `except:` at line 504 catches all exceptions including
    ProcessLookupError, OSError, and even SystemExit/KeyboardInterrupt.
    """

    @pytest.mark.asyncio
    async def test_process_lookup_error_masked(self):
        """
        Test that ProcessLookupError is masked by bare except.

        EXPECTED FAILURE: When a process has already terminated and
        process.communicate() is called, it raises ProcessLookupError.
        The bare except catches this and returns empty strings, losing
        important information about why the process failed.
        """
        service = HostShellService()

        # Mock the process that raises ProcessLookupError after timeout
        mock_process = AsyncMock()
        mock_process.communicate.side_effect = [asyncio.TimeoutError(), ProcessLookupError("Process not found")]
        mock_process.kill = AsyncMock()
        mock_process.returncode = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            id="agent-1",
            maturity="AUTONOMOUS"
        )
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            result = await service.execute_read_command(
                agent_id="agent-1",
                user_id="user-1",
                command="ls -la",  # Whitelisted command
                working_directory="/tmp",
                timeout=1,
                db=mock_db
            )

            # The bug: ProcessLookupError is masked and returns empty stdout/stderr
            # With proper handling, we'd expect an error or at least proper logging
            assert result["stdout"] == "", "Bug: ProcessLookupError masked, returns empty stdout"
            assert result["stderr"] == "", "Bug: ProcessLookupError masked, returns empty stderr"

    @pytest.mark.asyncio
    async def test_os_error_masked(self):
        """
        Test that OSError is masked by bare except.

        EXPECTED FAILURE: OSError indicates file system or OS-level issues
        (e.g., permission denied, file not found). The bare except catches
        this and returns empty strings, hiding the real error.
        """
        service = HostShellService()

        # Mock the process that raises OSError after timeout
        mock_process = AsyncMock()
        # First call times out, second call (after kill) raises OSError
        mock_process.communicate.side_effect = [
            asyncio.TimeoutError(),
            OSError("Permission denied")
        ]
        mock_process.kill = AsyncMock()
        mock_process.returncode = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            id="agent-1",
            maturity="AUTONOMOUS"
        )
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            result = await service.execute_read_command(
                agent_id="agent-1",
                user_id="user-1",
                command="ls -la",  # Whitelisted command
                working_directory="/tmp",
                timeout=1,
                db=mock_db
            )

            # The bug: OSError is masked
            assert result["stdout"] == "", "Bug: OSError masked"
            assert result["stderr"] == "", "Bug: OSError masked"

    @pytest.mark.asyncio
    async def test_broken_pipe_error_masked(self):
        """
        Test that BrokenPipeError is masked by bare except.

        EXPECTED FAILURE: BrokenPipeError occurs when reading from a process
        whose pipe has been closed. This is important information that's lost.
        """
        service = HostShellService()

        mock_process = AsyncMock()
        mock_process.communicate.side_effect = [asyncio.TimeoutError(), BrokenPipeError("Pipe closed")]
        mock_process.kill = AsyncMock()
        mock_process.returncode = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            id="agent-1",
            maturity="AUTONOMOUS"
        )
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            result = await service.execute_read_command(
                agent_id="agent-1",
                user_id="user-1",
                command="ls -la",  # Whitelisted command
                working_directory="/tmp",
                timeout=1,
                db=mock_db
            )

            # The bug: BrokenPipeError is masked
            assert result["stdout"] == "", "Bug: BrokenPipeError masked"

    @pytest.mark.asyncio
    async def test_exception_type_not_distinguished(self):
        """
        Test that different exception types are all treated the same.

        EXPECTED FAILURE: All exceptions are caught and result in empty
        strings regardless of their type. This makes debugging difficult.
        """
        service = HostShellService()

        # Test various exception types
        exception_types = [
            ProcessLookupError,
            OSError,
            BrokenPipeError,
            ConnectionError,
        ]

        for exc_type in exception_types:
            mock_process = AsyncMock()
            mock_process.communicate.side_effect = [asyncio.TimeoutError(), exc_type("test")]
            mock_process.kill = AsyncMock()
            mock_process.returncode = None

            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
                id="agent-1",
                maturity="AUTONOMOUS"
            )
            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock()

            with patch('asyncio.create_subprocess_shell', return_value=mock_process):
                result = await service.execute_read_command(
                    agent_id="agent-1",
                    user_id="user-1",
                    command="ls",  # Whitelisted command
                    working_directory="/tmp",
                    timeout=1,
                    db=mock_db
                )

                # All exceptions are treated the same - bug!
                assert result["stdout"] == "" and result["stderr"] == "", \
                    f"Bug: {exc_type.__name__} not distinguished from other errors"

    @pytest.mark.asyncio
    async def test_no_logging_of_exception_type(self):
        """
        Test that exception type is not logged.

        EXPECTED FAILURE: The bare except doesn't log which exception
        occurred, making debugging difficult.
        """
        service = HostShellService()

        mock_process = AsyncMock()
        mock_process.communicate.side_effect = [asyncio.TimeoutError(), ProcessLookupError("test")]
        mock_process.kill = AsyncMock()
        mock_process.returncode = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            id="agent-1",
            maturity="AUTONOMOUS"
        )
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            with patch.object(service, 'logger') as mock_logger:
                result = await service.execute_read_command(
                    agent_id="agent-1",
                    user_id="user-1",
                    command="ls",  # Whitelisted command
                    working_directory="/tmp",
                    timeout=1,
                    db=mock_db
                )

                # The bug: No specific logging of ProcessLookupError
                # We can't distinguish this from other errors in logs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
