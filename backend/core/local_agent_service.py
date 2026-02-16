"""
Local Agent Service - Standalone host process for governed shell/file access.

Communicates with Atom backend via REST API for governance checks and audit logging.
Runs outside Docker container on host machine with controlled shell execution.
"""

import asyncio
import httpx
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

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
        1. Check maturity via backend API
        2. Check directory permission via backend API
        3. Execute command locally (subprocess with shell=False)
        4. Log result to backend API

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
        # Step 1: Check governance via backend API
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

        # Step 2: Execute command locally with safe subprocess
        execution_result = await self._execute_locally(
            command=command,
            directory=working_directory
        )

        # Step 3: Log execution to backend API
        await self._log_execution({
            "agent_id": agent_id,
            "command": command,
            "working_directory": working_directory,
            "exit_code": execution_result["exit_code"],
            "stdout": execution_result["stdout"],
            "stderr": execution_result["stderr"],
            "timed_out": execution_result.get("timed_out", False),
            "duration_seconds": execution_result.get("duration_seconds", 0),
            "executed_at": datetime.utcnow().isoformat()
        })

        return {
            "allowed": True,
            "exit_code": execution_result["exit_code"],
            "stdout": execution_result["stdout"],
            "stderr": execution_result["stderr"],
            "session_id": execution_result.get("session_id"),
            "duration_seconds": execution_result.get("duration_seconds", 0),
            "timed_out": execution_result.get("timed_out", False)
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
        directory: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute command locally using asyncio subprocess.

        Key security (from RESEARCH.md):
        - Uses asyncio.create_subprocess_exec (NOT shell=True)
        - List arguments prevent command injection
        - Timeout enforcement via asyncio.wait_for (5-minute max)

        Args:
            command: Shell command to execute
            directory: Working directory for command

        Returns:
            Dict with exit_code, stdout, stderr, duration_seconds

        Raises:
            ValueError: If command is empty
            asyncio.TimeoutError: If command exceeds 5-minute timeout
        """
        if not command or not command.strip():
            raise ValueError("Empty command")

        # Parse command into list args (prevents injection)
        command_parts = command.strip().split()
        base_command = command_parts[0]

        # Validate working directory
        cwd = None
        if directory:
            cwd_path = Path(directory).resolve()
            if not cwd_path.exists():
                raise ValueError(f"Working directory does not exist: {directory}")
            cwd = str(cwd_path)

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
            "duration_seconds": duration_seconds
        }

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
