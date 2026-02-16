"""
Host Shell Service - Governed shell command execution on host filesystem.

OpenClaw Integration: AUTONOMOUS agents can execute whitelisted shell commands
on host filesystem through Docker bind mounts with full audit trail.
"""

import asyncio
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.models import ShellSession, AgentRegistry

logger = logging.getLogger(__name__)

# Command whitelist - safe commands that AUTONOMOUS agents can execute
COMMAND_WHITELIST = {
    # File operations (read-only)
    "ls", "pwd", "cat", "head", "tail", "grep", "find", "wc",
    # Git operations
    "git", "git-status", "git-diff", "git-log",
    # Build tools
    "make", "npm", "pip", "python3", "node",
    # Development tools
    "docker", "kubectl", "terraform", "ansible",
    # System info
    "df", "du", "ps", "top", "htop", "sleep",  # Added sleep for testing
    # Network (read-only)
    "curl", "wget", "ping", "nslookup", "dig", "netstat",
    # Text processing
    "sed", "awk", "sort", "uniq", "cut",
}

# Blocked commands - dangerous operations NEVER allowed
BLOCKED_COMMANDS = {
    "rm", "mv", "cp", "chmod", "chown", "dd", "mkfs",
    "kill", "killall", "pkill", "reboot", "shutdown", "halt",
    "su", "sudo", "passwd", "usermod", "userdel",
    "iptables", "ufw", "firewall-cmd",
}

# Maximum execution timeout (5 minutes)
MAX_TIMEOUT_SECONDS = 300


class HostShellService:
    """
    Governed shell command execution service.

    Governance Layers:
    1. Maturity check: AUTONOMOUS agents only
    2. Command whitelist: Only safe commands allowed
    3. Timeout enforcement: 5-minute maximum
    4. Audit trail: All commands logged to ShellSession
    """

    def __init__(self):
        self.logger = logger

    async def execute_shell_command(
        self,
        agent_id: str,
        user_id: str,
        command: str,
        working_directory: Optional[str] = None,
        timeout: int = MAX_TIMEOUT_SECONDS,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Execute shell command with full governance checks.

        Flow:
        1. Check agent maturity (AUTONOMOUS required)
        2. Validate command against whitelist
        3. Check for blocked commands
        4. Execute with timeout
        5. Log to ShellSession audit trail

        Args:
            agent_id: Agent requesting shell access
            user_id: User requesting execution
            command: Shell command to execute
            working_directory: Host directory (must be in allowed mount)
            timeout: Maximum execution time (default: 300s)
            db: Database session

        Returns:
            Dict with exit_code, stdout, stderr, timed_out, session_id
        """
        # Step 1: Check maturity from database
        if not db:
            raise ValueError("Database session required for maturity check")

        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise PermissionError(f"Agent {agent_id} not found")

        maturity_level = agent.status

        if maturity_level != "AUTONOMOUS":
            raise PermissionError(
                f"Shell access requires AUTONOMOUS maturity, "
                f"agent {agent_id} is {maturity_level}"
            )

        # Step 2: Parse command to check base command
        command_parts = command.strip().split()
        if not command_parts:
            raise ValueError("Empty command")

        base_command = command_parts[0]

        # Step 3: Check blocked commands
        if base_command in BLOCKED_COMMANDS:
            raise PermissionError(
                f"Command '{base_command}' is blocked for safety reasons"
            )

        # Step 4: Check whitelist
        if base_command not in COMMAND_WHITELIST:
            raise PermissionError(
                f"Command '{base_command}' not in whitelist. "
                f"Allowed: {', '.join(sorted(COMMAND_WHITELIST))}"
            )

        # Step 5: Validate working directory
        if working_directory:
            # Ensure working directory is within allowed mount
            # Configurable via ATOM_HOST_MOUNT_DIRS environment variable
            allowed_dirs = os.getenv(
                "ATOM_HOST_MOUNT_DIRS",
                "/tmp:/home:/Users"
            ).split(":")

            if not any(working_directory.startswith(d) for d in allowed_dirs):
                raise PermissionError(
                    f"Working directory '{working_directory}' not in allowed directories: {allowed_dirs}"
                )

        # Step 6: Create audit session
        session = ShellSession(
            agent_id=agent_id,
            user_id=user_id,
            maturity_level=maturity_level,
            command=command,
            command_whitelist_valid=True,
            working_directory=working_directory,
            started_at=datetime.utcnow()
        )

        if db:
            db.add(session)
            db.commit()

        try:
            # Step 7: Execute command with timeout
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_directory
            )

            # Wait with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                timed_out = False
            except asyncio.TimeoutError:
                # Kill process
                process.kill()
                try:
                    stdout, stderr = await process.communicate()
                except:
                    stdout, stderr = b"", b""
                timed_out = True

            # Step 8: Update session with results
            session.exit_code = process.returncode
            session.stdout = stdout.decode("utf-8", errors="replace")
            session.stderr = stderr.decode("utf-8", errors="replace")
            session.timed_out = timed_out
            session.completed_at = datetime.utcnow()
            session.duration_seconds = (
                session.completed_at - session.started_at
            ).total_seconds()

            if db:
                db.commit()

            self.logger.info(
                f"Shell command executed: agent={agent_id}, "
                f"command='{command[:50]}...', exit_code={process.returncode}"
            )

            return {
                "exit_code": process.returncode,
                "stdout": session.stdout,
                "stderr": session.stderr,
                "timed_out": timed_out,
                "session_id": session.id,
                "duration_seconds": session.duration_seconds
            }

        except Exception as e:
            # Log failure
            session.completed_at = datetime.utcnow()
            session.stderr = str(e)
            if db:
                db.commit()

            self.logger.error(f"Shell command failed: {e}")
            raise

    def validate_command(self, command: str) -> Dict[str, Any]:
        """
        Validate command against whitelist and blocked lists.

        Returns validation result without executing.
        """
        command_parts = command.strip().split()
        if not command_parts:
            return {"valid": False, "reason": "Empty command"}

        base_command = command_parts[0]

        # Check blocked
        if base_command in BLOCKED_COMMANDS:
            return {
                "valid": False,
                "reason": f"Command '{base_command}' is blocked",
                "blocked": True
            }

        # Check whitelist
        if base_command not in COMMAND_WHITELIST:
            return {
                "valid": False,
                "reason": f"Command '{base_command}' not in whitelist",
                "allowed_commands": sorted(COMMAND_WHITELIST)
            }

        return {
            "valid": True,
            "command": base_command,
            "whitelisted": True
        }


# Global service instance
host_shell_service = HostShellService()
