"""
Atom CLI Skill Wrapper - Subprocess execution for CLI commands.

Provides safe subprocess execution wrapper for Atom CLI commands invoked
from community skills. Handles timeouts, error handling, and logging.

Reference: Phase 25 Plan 02 - Subprocess Execution Wrapper
"""

import logging
import re
import subprocess
import time
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def execute_atom_cli_command(command: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Execute Atom CLI command via subprocess.

    Provides safe command execution with timeout enforcement, structured
    output, and comprehensive error handling for skill integration.

    Args:
        command: CLI command name (e.g., "daemon", "status", "stop")
        args: Optional list of command arguments (e.g., ["--port", "3000"])

    Returns:
        Dict with keys:
            - success: bool (True if returncode == 0)
            - stdout: str (captured standard output)
            - stderr: str (captured standard error)
            - returncode: int (process exit code)

    Raises:
        No exceptions raised - all errors captured in return dict

    Examples:
        >>> result = execute_atom_cli_command("status")
        >>> if result["success"]:
        ...     print(result["stdout"])
        ... else:
        ...     print(f"Error: {result['stderr']}")

        >>> result = execute_atom_cli_command("daemon", ["--port", "3000"])
        >>> print(f"PID: {result['returncode']}")

    Notes:
        - 30 second timeout prevents hanging commands
        - subprocess.TimeoutExpired caught and returned as error
        - Generic exceptions caught and returned with stderr message
    """
    try:
        # Build command list
        cmd = ["atom-os", command]
        if args:
            cmd.extend(args)

        logger.info(f"Executing: atom-os {command} {' '.join(args) if args else ''}")

        # Execute with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout per plan requirement
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        logger.error(f"Command 'atom-os {command}' timed out after 30 seconds")
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out after 30 seconds",
            "returncode": -1
        }

    except Exception as e:
        logger.error(f"Failed to execute 'atom-os {command}': {e}")
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }


def is_daemon_running() -> bool:
    """
    Check if Atom daemon is currently running.

    Executes status command and parses output for running state.

    Returns:
        True if daemon is running, False otherwise

    Examples:
        >>> if is_daemon_running():
        ...     print("Daemon is active")
        ... else:
        ...     print("Daemon is stopped")

    Notes:
        - Parses status output for "RUNNING" status string
        - Returns False on command failure or parse errors
    """
    try:
        result = execute_atom_cli_command("status")

        if not result["success"]:
            return False

        # Parse status output for running state
        # Expected format: "Status: RUNNING" or "Status: NOT RUNNING"
        status_match = re.search(r"Status:\s*(\w+)", result["stdout"], re.IGNORECASE)
        if status_match:
            status = status_match.group(1).upper()
            return status == "RUNNING"

        return False

    except Exception as e:
        logger.error(f"Failed to check daemon status: {e}")
        return False


def get_daemon_pid() -> Optional[int]:
    """
    Get daemon process ID from status output.

    Executes status command and extracts PID using regex.

    Returns:
        Daemon PID as int if running, None if not found

    Examples:
        >>> pid = get_daemon_pid()
        >>> if pid:
        ...     print(f"Daemon PID: {pid}")

    Notes:
        - Uses regex pattern: r\"PID:\\\\s+(\\\\d+)\"
        - Returns None if daemon not running or PID not found
    """
    try:
        result = execute_atom_cli_command("status")

        if not result["success"]:
            return None

        # Extract PID from status output
        # Expected format: "PID: 12345"
        pid_match = re.search(r"PID:\s+(\d+)", result["stdout"])
        if pid_match:
            return int(pid_match.group(1))

        return None

    except Exception as e:
        logger.error(f"Failed to get daemon PID: {e}")
        return None


def wait_for_daemon_ready(max_wait: int = 10) -> bool:
    """
    Poll daemon status until running or timeout.

    Prevents race conditions after starting daemon by waiting for
    the daemon to initialize and become ready.

    Args:
        max_wait: Maximum seconds to wait (default: 10)

    Returns:
        True if daemon ready, False if timeout exceeded

    Examples:
        >>> execute_atom_cli_command("daemon", ["--port", "3000"])
        >>> if wait_for_daemon_ready(max_wait=5):
        ...     print("Daemon started successfully")
        ... else:
        ...     print("Daemon failed to start")

    Notes:
        - Polls every 0.5 seconds
        - Logs progress at each attempt
        - Prevents Pitfall 4 from RESEARCH.md (race conditions)
    """
    start_time = time.time()
    poll_interval = 0.5  # seconds

    while True:
        elapsed = time.time() - start_time

        if is_daemon_running():
            logger.info(f"Daemon ready after {elapsed:.1f}s")
            return True

        if elapsed >= max_wait:
            logger.warning(f"Daemon not ready after {max_wait}s timeout")
            return False

        logger.info(f"Waiting for daemon... {elapsed:.1f}s")
        time.sleep(poll_interval)


def mock_daemon_response(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0
) -> Dict[str, Any]:
    """
    Create mock daemon response for testing.

    Helper function for unit tests to simulate command execution
    results without actually running subprocess.

    Args:
        stdout: Mock standard output
        stderr: Mock standard error
        returncode: Mock return code (0 for success)

    Returns:
        Dict matching execute_atom_cli_command format

    Examples:
        >>> mock = mock_daemon_response(
        ...     stdout="Status: RUNNING\\nPID: 12345",
        ...     returncode=0
        ... )
        >>> assert mock["success"] == True
    """
    return {
        "success": returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode
    }


def build_command_args(
    port: Optional[int] = None,
    host: Optional[str] = None,
    workers: Optional[int] = None,
    host_mount: bool = False,
    dev: bool = False,
    foreground: bool = False
) -> List[str]:
    """
    Build command arguments list for daemon/start commands.

    Helper function to construct argument list from keyword parameters.

    Args:
        port: Port number for web server
        host: Host address to bind to
        workers: Number of worker processes
        host_mount: Enable host filesystem mount
        dev: Enable development mode
        foreground: Run in foreground (not daemon mode)

    Returns:
        List of command arguments (e.g., ["--port", "8000", "--dev"])

    Examples:
        >>> args = build_command_args(port=3000, dev=True)
        >>> execute_atom_cli_command("daemon", args)
    """
    args = []

    if port is not None:
        args.extend(["--port", str(port)])

    if host is not None:
        args.extend(["--host", host])

    if workers is not None:
        args.extend(["--workers", str(workers)])

    if host_mount:
        args.append("--host-mount")

    if dev:
        args.append("--dev")

    if foreground:
        args.append("--foreground")

    return args
