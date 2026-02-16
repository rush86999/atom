"""
Host Shell Service - Governed shell command execution on host filesystem.

Maturity-based command execution with decorator-based whitelist enforcement:
- STUDENT: Read commands only (ls, cat, grep, etc.)
- INTERN: Read commands (requires approval)
- SUPERVISED: Write commands (cp, mv, mkdir) with approval
- AUTONOMOUS: All whitelisted commands except blocked

Security:
- Decorator-based whitelist enforcement
- Category-based command routing (read/write/delete/build/dev_ops/network)
- Subprocess shell=False pattern (no command injection)
- 5-minute timeout enforcement
- Full audit trail via ShellSession
"""

import asyncio
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.models import ShellSession, AgentRegistry
from core.command_whitelist import (
    whitelisted_command,
    CommandCategory,
    get_command_category
)

logger = logging.getLogger(__name__)

# Maximum execution timeout (5 minutes)
MAX_TIMEOUT_SECONDS = 300

# Maximum execution timeout (5 minutes)
MAX_TIMEOUT_SECONDS = 300


class HostShellService:
    """
    Governed shell command execution service.

    Governance Layers:
    1. Decorator-based whitelist enforcement (@whitelisted_command)
    2. Category-based command routing (read/write/delete/build/dev_ops/network)
    3. Maturity level checks (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
    4. Timeout enforcement: 5-minute maximum
    5. Audit trail: All commands logged to ShellSession
    6. Subprocess shell=False pattern (prevents command injection)

    Command Categories:
    - FILE_READ: ls, cat, grep, head, tail, find, wc, pwd (all maturity levels)
    - FILE_WRITE: cp, mv, mkdir, touch (SUPERVISED+, approval required)
    - FILE_DELETE: rm (AUTONOMOUS only)
    - BUILD_TOOLS: make, npm, pip, python3, node (SUPERVISED+)
    - DEV_OPS: git, docker, kubectl, terraform (SUPERVISED+)
    - NETWORK: curl, wget, ping (all maturity levels)
    - BLOCKED: chmod, chown, kill, sudo, reboot (all maturity levels blocked)
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
        1. Determine command category
        2. Route to appropriate category-specific method
        3. Decorator enforces whitelist and maturity level
        4. Execute with subprocess shell=False (safe)
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

        Raises:
            PermissionError: If command not whitelisted or maturity insufficient
            ValueError: If working directory invalid
        """
        if not db:
            raise ValueError("Database session required for maturity check")

        # Parse base command
        command_parts = command.strip().split()
        if not command_parts:
            raise ValueError("Empty command")

        base_command = command_parts[0]

        # Determine command category
        category = get_command_category(command)
        if not category:
            raise PermissionError(
                f"Command '{base_command}' not found in any whitelist category. "
                f"This command is not available to agents."
            )

        # Validate working directory
        if working_directory:
            allowed_dirs = os.getenv(
                "ATOM_HOST_MOUNT_DIRS",
                "/tmp:/home:/Users"
            ).split(":")

            if not any(working_directory.startswith(d) for d in allowed_dirs):
                raise PermissionError(
                    f"Working directory '{working_directory}' not in allowed directories: {allowed_dirs}"
                )

        # Route to appropriate category-specific method
        if category == CommandCategory.FILE_READ:
            return await self.execute_read_command(
                agent_id=agent_id,
                user_id=user_id,
                command=command,
                working_directory=working_directory,
                timeout=timeout,
                db=db
            )
        elif category == CommandCategory.FILE_WRITE:
            return await self.execute_write_command(
                agent_id=agent_id,
                user_id=user_id,
                command=command,
                working_directory=working_directory,
                timeout=timeout,
                db=db
            )
        elif category == CommandCategory.FILE_DELETE:
            return await self.execute_delete_command(
                agent_id=agent_id,
                user_id=user_id,
                command=command,
                working_directory=working_directory,
                timeout=timeout,
                db=db
            )
        elif category == CommandCategory.BLOCKED:
            raise PermissionError(
                f"Command '{base_command}' is blocked for all maturity levels. "
                f"This command cannot be executed by agents."
            )
        else:
            # Build tools, dev ops, network - use general method
            return await self.execute_general_command(
                agent_id=agent_id,
                user_id=user_id,
                command=command,
                category=category,
                working_directory=working_directory,
                timeout=timeout,
                db=db
            )

    @whitelisted_command(
        category=CommandCategory.FILE_READ,
        maturity_levels=["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
    )
    async def execute_read_command(
        self,
        agent_id: str,
        user_id: str,
        command: str,
        working_directory: Optional[str] = None,
        timeout: int = MAX_TIMEOUT_SECONDS,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Execute read-only command (ls, cat, grep, etc.).

        Decorator validates:
        1. Command is in FILE_READ whitelist
        2. Agent maturity level is allowed
        3. Maturity check via database

        All maturity levels can use read commands, but:
        - STUDENT: Can suggest (requires human approval for execution)
        - INTERN: Can suggest (requires human approval)
        - SUPERVISED: Can execute (with supervision)
        - AUTONOMOUS: Can execute (no supervision)
        """
        return await self._execute_command_internal(
            agent_id=agent_id,
            user_id=user_id,
            command=command,
            working_directory=working_directory,
            timeout=timeout,
            db=db
        )

    @whitelisted_command(
        category=CommandCategory.FILE_WRITE,
        maturity_levels=["SUPERVISED", "AUTONOMOUS"]
    )
    async def execute_write_command(
        self,
        agent_id: str,
        user_id: str,
        command: str,
        working_directory: Optional[str] = None,
        timeout: int = MAX_TIMEOUT_SECONDS,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Execute write command (cp, mv, mkdir, touch).

        Decorator validates:
        1. Command is in FILE_WRITE whitelist
        2. Agent maturity level is SUPERVISED or AUTONOMOUS
        3. STUDENT/INTERN agents automatically blocked by decorator

        Returns requires_approval flag for SUPERVISED agents (human approval needed).
        """
        return await self._execute_command_internal(
            agent_id=agent_id,
            user_id=user_id,
            command=command,
            working_directory=working_directory,
            timeout=timeout,
            db=db
        )

    @whitelisted_command(
        category=CommandCategory.FILE_DELETE,
        maturity_levels=["AUTONOMOUS"]
    )
    async def execute_delete_command(
        self,
        agent_id: str,
        user_id: str,
        command: str,
        working_directory: Optional[str] = None,
        timeout: int = MAX_TIMEOUT_SECONDS,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Execute delete command (rm).

        Decorator validates:
        1. Command is in FILE_DELETE whitelist
        2. Agent maturity level is AUTONOMOUS ONLY
        3. STUDENT/INTERN/SUPERVISED agents automatically blocked

        AUTONOMOUS only - no other maturity level can delete files.
        """
        return await self._execute_command_internal(
            agent_id=agent_id,
            user_id=user_id,
            command=command,
            working_directory=working_directory,
            timeout=timeout,
            db=db
        )

    @whitelisted_command(
        category=CommandCategory.BUILD_TOOLS,
        maturity_levels=["SUPERVISED", "AUTONOMOUS"]
    )
    async def execute_build_command(
        self,
        agent_id: str,
        user_id: str,
        command: str,
        working_directory: Optional[str] = None,
        timeout: int = MAX_TIMEOUT_SECONDS,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Execute build tool command (make, npm, pip, etc.).

        Decorator validates maturity level (SUPERVISED+).
        """
        return await self._execute_command_internal(
            agent_id=agent_id,
            user_id=user_id,
            command=command,
            working_directory=working_directory,
            timeout=timeout,
            db=db
        )

    @whitelisted_command(
        category=CommandCategory.DEV_OPS,
        maturity_levels=["SUPERVISED", "AUTONOMOUS"]
    )
    async def execute_devops_command(
        self,
        agent_id: str,
        user_id: str,
        command: str,
        working_directory: Optional[str] = None,
        timeout: int = MAX_TIMEOUT_SECONDS,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Execute dev ops command (git, docker, kubectl, etc.).

        Decorator validates maturity level (SUPERVISED+).
        """
        return await self._execute_command_internal(
            agent_id=agent_id,
            user_id=user_id,
            command=command,
            working_directory=working_directory,
            timeout=timeout,
            db=db
        )

    @whitelisted_command(
        category=CommandCategory.NETWORK,
        maturity_levels=["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
    )
    async def execute_network_command(
        self,
        agent_id: str,
        user_id: str,
        command: str,
        working_directory: Optional[str] = None,
        timeout: int = MAX_TIMEOUT_SECONDS,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Execute network command (curl, wget, ping, etc.).

        Decorator validates maturity level (all levels allowed).
        Read-only network operations - safe for all maturity levels.
        """
        return await self._execute_command_internal(
            agent_id=agent_id,
            user_id=user_id,
            command=command,
            working_directory=working_directory,
            timeout=timeout,
            db=db
        )

    async def execute_general_command(
        self,
        agent_id: str,
        user_id: str,
        command: str,
        category: CommandCategory,
        working_directory: Optional[str] = None,
        timeout: int = MAX_TIMEOUT_SECONDS,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Execute general command by category.

        Routes to appropriate category-specific method.
        """
        if category == CommandCategory.BUILD_TOOLS:
            return await self.execute_build_command(
                agent_id=agent_id,
                user_id=user_id,
                command=command,
                working_directory=working_directory,
                timeout=timeout,
                db=db
            )
        elif category == CommandCategory.DEV_OPS:
            return await self.execute_devops_command(
                agent_id=agent_id,
                user_id=user_id,
                command=command,
                working_directory=working_directory,
                timeout=timeout,
                db=db
            )
        elif category == CommandCategory.NETWORK:
            return await self.execute_network_command(
                agent_id=agent_id,
                user_id=user_id,
                command=command,
                working_directory=working_directory,
                timeout=timeout,
                db=db
            )
        else:
            raise PermissionError(f"Unsupported command category: {category}")

    async def _execute_command_internal(
        self,
        agent_id: str,
        user_id: str,
        command: str,
        working_directory: Optional[str] = None,
        timeout: int = MAX_TIMEOUT_SECONDS,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Internal command execution with subprocess shell=False pattern.

        Security:
        - Uses asyncio.create_subprocess_exec (NOT shell=True)
        - List arguments prevent command injection
        - 5-minute timeout enforced
        - Full audit trail

        Args:
            agent_id: Agent requesting execution
            user_id: User requesting execution
            command: Shell command to execute
            working_directory: Host directory for command
            timeout: Maximum execution time (default: 300s)
            db: Database session

        Returns:
            Dict with exit_code, stdout, stderr, timed_out, session_id
        """
        # Get agent maturity level for audit
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise PermissionError(f"Agent {agent_id} not found")

        maturity_level = agent.status

        # Create audit session
        session = ShellSession(
            agent_id=agent_id,
            user_id=user_id,
            maturity_level=maturity_level,
            command=command,
            command_whitelist_valid=True,
            working_directory=working_directory,
            started_at=datetime.utcnow()
        )

        db.add(session)
        db.commit()

        try:
            # Parse command into list args (prevents injection)
            command_parts = command.strip().split()

            # Execute with subprocess shell=False (safe)
            process = await asyncio.create_subprocess_exec(
                *command_parts,  # List args prevent injection
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
                # Kill process on timeout
                process.kill()
                try:
                    stdout, stderr = await process.communicate()
                except:
                    stdout, stderr = b"", b""
                timed_out = True

            # Update session with results
            session.exit_code = process.returncode if not timed_out else -1
            session.stdout = stdout.decode("utf-8", errors="replace")
            session.stderr = stderr.decode("utf-8", errors="replace")
            session.timed_out = timed_out
            session.completed_at = datetime.utcnow()
            session.duration_seconds = (
                session.completed_at - session.started_at
            ).total_seconds()

            db.commit()

            self.logger.info(
                f"Shell command executed: agent={agent_id}, "
                f"maturity={maturity_level}, command='{command[:50]}...', "
                f"exit_code={process.returncode}"
            )

            return {
                "exit_code": session.exit_code,
                "stdout": session.stdout,
                "stderr": session.stderr,
                "timed_out": timed_out,
                "session_id": session.id,
                "duration_seconds": session.duration_seconds,
                "maturity_level": maturity_level
            }

        except Exception as e:
            # Log failure
            session.completed_at = datetime.utcnow()
            session.stderr = str(e)
            session.exit_code = -1
            db.commit()

            self.logger.error(f"Shell command failed: {e}")
            raise


# Global service instance
host_shell_service = HostShellService()
