"""
Local Agent Service - Standalone host process for governed shell/file access.

Communicates with Atom backend via REST API for governance checks and audit logging.
Runs outside Docker container on host machine with controlled shell execution.

Directory Permission Integration:
- Uses directory_permission.check_directory_permission() for path validation
- Returns suggest_only flag for lower maturity levels
- Logs file operations (read/write/blocked) to audit trail
"""

import asyncio
import httpx
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from core.directory_permission import check_directory_permission
from core.command_whitelist import validate_command, get_command_category
from core.models import AgentStatus

logger = logging.getLogger(__name__)


class LocalAgentService:
    """
    Local agent service running on host machine.

    Communicates with Atom backend via REST API for:
    - Agent maturity checks
    - Directory permission validation
    - Audit trail logging

    Key design (from RESEARCH.md):
    - Uses httpx.AsyncClient for HTTP communication (async support)
    - Calls backend /api/agents/{id}/governance for maturity check
    - Uses asyncio.create_subprocess_exec with list args (prevent injection)
    - Timeout enforcement via asyncio.wait_for (5-minute max)
    """

    def __init__(self, backend_url: str = "http://localhost:8000"):
        """
        Initialize local agent service.

        Args:
            backend_url: Atom backend API URL (default: http://localhost:8000)
        """
        self.backend_url = backend_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.backend_url,
            timeout=httpx.Timeout(30.0)  # 30s timeout for API calls
        )
        self.logger = logger

    async def execute_command(
        self,
        agent_id: str,
        command: str,
        working_directory: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute shell command with governance checks.

        Flow:
        1. Check governance (maturity level) - EXISTING
        2. Check directory permission - NEW
        3. If suggest_only: return approval request
        4. Else: execute subprocess
        5. Log to ShellSession

        Args:
            agent_id: Agent requesting execution
            command: Shell command to execute
            working_directory: Host directory for command execution

        Returns:
            Dict with execution result (exit_code, stdout, stderr, session_id)

        Raises:
            PermissionError: If governance check fails
            httpx.HTTPError: If backend unreachable
        """
        # Step 1: Check governance via backend API (maturity level)
        governance_result = await self._check_governance(
            agent_id=agent_id,
            command=command,
            directory=working_directory
        )

        if not governance_result.get("allowed", False):
            # Governance denied - return approval required info
            return {
                "allowed": False,
                "reason": governance_result.get("reason", "Governance check failed"),
                "requires_approval": governance_result.get("requires_approval", False),
                "maturity_level": governance_result.get("maturity_level", "UNKNOWN")
            }

        # Step 1.5: Validate command against whitelist (NEW)
        maturity_level_str = governance_result.get("maturity_level", "STUDENT")
        validation = validate_command(command, maturity_level_str)

        if not validation["valid"]:
            # Command validation failed - blocked or wrong maturity level
            category = get_command_category(command)

            # Log blocked command attempt to audit trail
            await self._log_execution({
                "agent_id": agent_id,
                "command": command,
                "working_directory": working_directory,
                "exit_code": -1,
                "stdout": "",
                "stderr": validation["reason"],
                "timed_out": False,
                "duration_seconds": 0,
                "executed_at": datetime.utcnow().isoformat(),
                "operation_type": "blocked",
                "maturity_level": maturity_level_str,
                "command_whitelist_valid": False,
                "blocked_reason": validation["reason"]
            })

            # Check if command requires higher maturity level
            if validation.get("maturity_required") and validation["maturity_required"] != maturity_level_str:
                # Return approval required for higher maturity commands
                return {
                    "allowed": False,
                    "reason": validation["reason"],
                    "requires_approval": True,
                    "maturity_level": maturity_level_str,
                    "maturity_required": validation["maturity_required"],
                    "suggested_command": command,
                    "category": validation.get("category")
                }

            # Command is blocked for all maturity levels
            return {
                "allowed": False,
                "reason": validation["reason"],
                "blocked": True,
                "maturity_level": maturity_level_str,
                "suggested_command": command,
                "category": validation.get("category")
            }

        # Step 2: Check directory permission (EXISTING)
        maturity_level_str = governance_result.get("maturity_level", "STUDENT")
        try:
            maturity_level = AgentStatus(maturity_level_str)
        except ValueError:
            maturity_level = AgentStatus.STUDENT

        directory_permission = check_directory_permission(
            agent_id=agent_id,
            directory=working_directory or "/tmp",
            maturity_level=maturity_level
        )

        if not directory_permission["allowed"]:
            # Directory access denied - log to audit trail
            await self._log_execution({
                "agent_id": agent_id,
                "command": command,
                "working_directory": working_directory,
                "exit_code": -1,
                "stdout": "",
                "stderr": directory_permission["reason"],
                "timed_out": False,
                "duration_seconds": 0,
                "executed_at": datetime.utcnow().isoformat(),
                "operation_type": "blocked",
                "maturity_level": maturity_level_str,
                "command_whitelist_valid": True,
                "blocked_reason": f"Directory access denied: {directory_permission['reason']}"
            })

            return {
                "allowed": False,
                "reason": directory_permission["reason"],
                "requires_approval": False,
                "maturity_level": maturity_level_str,
                "blocked_directory": directory_permission["resolved_path"]
            }

        # Step 3: Check suggest_only flag
        if directory_permission["suggest_only"]:
            # Lower maturity agent - return approval request
            await self._log_execution({
                "agent_id": agent_id,
                "command": command,
                "working_directory": working_directory,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Approval required for {maturity_level_str} maturity level",
                "timed_out": False,
                "duration_seconds": 0,
                "executed_at": datetime.utcnow().isoformat(),
                "operation_type": "suggest_only",
                "maturity_level": maturity_level_str,
                "command_whitelist_valid": True,
                "requires_approval": True
            })

            return {
                "allowed": False,
                "reason": directory_permission["reason"],
                "requires_approval": True,
                "maturity_level": maturity_level_str,
                "suggested_command": command,
                "suggested_directory": directory_permission["resolved_path"]
            }

        # Step 4: Execute command locally with safe subprocess
        execution_result = await self._execute_locally(
            command=command,
            directory=working_directory,
            operation_type="execute"  # Log as execute operation
        )

        # Step 5: Log execution to backend API
        await self._log_execution({
            "agent_id": agent_id,
            "command": command,
            "working_directory": working_directory,
            "exit_code": execution_result["exit_code"],
            "stdout": execution_result["stdout"],
            "stderr": execution_result["stderr"],
            "timed_out": execution_result.get("timed_out", False),
            "duration_seconds": execution_result.get("duration_seconds", 0),
            "executed_at": datetime.utcnow().isoformat(),
            "operation_type": execution_result.get("operation_type", "execute"),
            "maturity_level": maturity_level_str,
            "command_whitelist_valid": True
        })

        return {
            "allowed": True,
            "exit_code": execution_result["exit_code"],
            "stdout": execution_result["stdout"],
            "stderr": execution_result["stderr"],
            "session_id": execution_result.get("session_id"),
            "duration_seconds": execution_result.get("duration_seconds", 0),
            "timed_out": execution_result.get("timed_out", False),
            "maturity_level": maturity_level_str
        }

    async def _check_governance(
        self,
        agent_id: str,
        command: str,
        directory: Optional[str]
    ) -> Dict[str, Any]:
        """
        Check governance via backend API.

        Calls backend /api/agents/{id}/governance for maturity check.

        Args:
            agent_id: Agent ID to check
            command: Command to validate
            directory: Working directory for permission check

        Returns:
            Dict with governance decision (allowed, reason, requires_approval)

        Raises:
            httpx.HTTPError: If backend unreachable
        """
        try:
            response = await self.client.post(
                f"/api/agents/{agent_id}/governance",
                json={
                    "action_type": "shell_execute",
                    "command": command,
                    "directory": directory
                }
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"Governance check failed: {e}")
            raise

    async def _execute_locally(
        self,
        command: str,
        directory: Optional[str] = None,
        operation_type: str = "execute"
    ) -> Dict[str, Any]:
        """
        Execute command locally using asyncio subprocess.

        Key security (from RESEARCH.md):
        - Uses asyncio.create_subprocess_exec (NOT shell=True)
        - List arguments prevent command injection
        - Timeout enforcement via asyncio.wait_for (5-minute max)
        - Path validation with pathlib before execution

        Args:
            command: Shell command to execute
            directory: Working directory for command
            operation_type: Operation type for logging (read/write/execute/blocked)

        Returns:
            Dict with exit_code, stdout, stderr, duration_seconds, operation_type

        Raises:
            ValueError: If command is empty or directory invalid
            asyncio.TimeoutError: If command exceeds 5-minute timeout
        """
        if not command or not command.strip():
            raise ValueError("Empty command")

        # Parse command into list args (prevents injection)
        command_parts = command.strip().split()
        base_command = command_parts[0]

        # Validate working directory with pathlib
        cwd = None
        if directory:
            cwd_path = Path(directory).expanduser().resolve()
            if not cwd_path.exists():
                raise ValueError(f"Working directory does not exist: {directory}")
            cwd = str(cwd_path)

        # Detect operation type for logging
        detected_operation = self._detect_operation_type(base_command)
        if operation_type == "execute":
            operation_type = detected_operation

        # Start process with shell=False (safe)
        start_time = datetime.utcnow()
        process = await asyncio.create_subprocess_exec(
            *command_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )

        # Wait with timeout (5-minute max)
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300  # 5 minutes
            )
            timed_out = False
        except asyncio.TimeoutError:
            # Kill process on timeout
            process.kill()
            try:
                stdout, stderr = await process.communicate()
            except:
                stdout, stderr = b"", b""
            timed_out = True

        end_time = datetime.utcnow()
        duration_seconds = (end_time - start_time).total_seconds()

        # Decode output
        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

        if timed_out:
            stderr_str = f"Command timed out after 5 minutes\n{stderr_str}"

        return {
            "exit_code": process.returncode if not timed_out else -1,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "timed_out": timed_out,
            "duration_seconds": duration_seconds,
            "operation_type": operation_type
        }

    def _detect_operation_type(self, base_command: str) -> str:
        """
        Detect file operation type from base command.

        Args:
            base_command: Base command (e.g., "ls", "cat", "mkdir")

        Returns:
            Operation type: "read", "write", "execute", or "blocked"
        """
        # Read operations
        read_commands = {"ls", "cat", "head", "tail", "grep", "find", "wc", "pwd", "file"}
        if base_command in read_commands:
            return "read"

        # Write operations
        write_commands = {"cp", "mv", "mkdir", "touch", "echo", "tee", "dd"}
        if base_command in write_commands:
            return "write"

        # Delete operations (blocked for lower maturity)
        delete_commands = {"rm", "rmdir"}
        if base_command in delete_commands:
            return "write"

        # Default to execute
        return "execute"

    async def _log_execution(self, session_data: Dict[str, Any]) -> None:
        """
        Log execution to backend API.

        POST to backend /api/shell/log for audit trail.

        Args:
            session_data: Execution session data (agent_id, command, exit_code, etc.)

        Raises:
            httpx.HTTPError: If backend unreachable
        """
        try:
            response = await self.client.post(
                "/api/shell/log",
                json=session_data
            )
            response.raise_for_status()
            self.logger.info(
                f"Logged execution: agent={session_data['agent_id']}, "
                f"command='{session_data['command'][:50]}...', "
                f"exit_code={session_data['exit_code']}"
            )
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to log execution: {e}")
            # Don't raise - logging failure shouldn't break execution

    async def get_status(self) -> Dict[str, Any]:
        """
        Get local agent status.

        Returns:
            Dict with status information (backend_reachable, etc.)
        """
        try:
            response = await self.client.get("/health/live")
            backend_reachable = response.status_code == 200
        except:
            backend_reachable = False

        return {
            "backend_url": self.backend_url,
            "backend_reachable": backend_reachable,
            "status": "running" if backend_reachable else "backend_unreachable"
        }

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Global service instance
_local_agent_service: Optional[LocalAgentService] = None


def get_local_agent_service(backend_url: str = "http://localhost:8000") -> LocalAgentService:
    """Get global local agent service instance."""
    global _local_agent_service
    if _local_agent_service is None:
        _local_agent_service = LocalAgentService(backend_url=backend_url)
        logger.info(f"Initialized local agent service (backend: {backend_url})")
    return _local_agent_service
