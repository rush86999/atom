---
phase: 13-openclaw-integration
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/models.py
  - backend/core/host_shell_service.py
  - backend/api/shell_routes.py
  - backend/tests/test_host_shell_service.py
  - backend/docker/docker-compose.host-mount.yml
  - backend/docker/host-mount-setup.sh
autonomous: true

must_haves:
  truths:
    - AUTONOMOUS agents can execute shell commands on host filesystem
    - Shell access is gated by governance maturity check
    - All shell commands are logged to audit trail
    - Shell commands execute in container with host directory bind mount
    - Working directory restrictions prevent escaping designated areas
    - Command whitelist prevents dangerous operations (rm, mv, chmod, etc.)
    - Shell timeout enforcement prevents runaway commands
  artifacts:
    - path: backend/core/host_shell_service.py
      provides: Governed shell command execution service
      min_lines: 200
      exports: ["HostShellService", "execute_shell_command", "validate_command"]
    - path: backend/api/shell_routes.py
      provides: REST API endpoints for shell access
      contains: "POST /api/shell/execute"
    - path: backend/core/models.py
      provides: ShellSession database model
      contains: "class ShellSession"
  key_links:
    - from: "backend/core/host_shell_service.py"
      to: "backend/core/agent_governance_service.py"
      via: "Governance maturity check before shell execution"
      pattern: "agent_governance_service.check_maturity"
    - from: "backend/core/host_shell_service.py"
      to: "subprocess"
      via: "Shell command execution with timeout"
      pattern: "subprocess.run.*timeout"
---

<objective>
Implement "God Mode" local agent with controlled host shell access.

OpenClaw's viral feature: Run shell commands on host filesystem. Atom's twist: AUTONOMOUS-only maturity gate, command whitelist, audit trail, Docker bind mounts.

Purpose: Give trusted agents "hands" to touch host files while maintaining governance
Output: HostShellService with AUTONOMOUS gate, whitelist validation, 5-min timeout, audit logging
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
@/Users/rushiparikh/.claude/get-shit-done/references/checkpoints.md
@/Users/rushiparikh/.claude/get-shit-done/references/tdd.md
</execution_context>

<context>
@.planning/phases/13-openclaw-integration/13-RESEARCH.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Existing implementations
@backend/core/agent_governance_service.py
@backend/core/device_tool.py
@backend/core/models.py
</context>

<tasks>

<task type="auto">
  <name>Create ShellSession database model</name>
  <files>backend/core/models.py</files>
  <action>
Add ShellSession model after DeviceSession (around line 4350):

```python
class ShellSession(Base):
    """
    Host shell command execution session with governance controls.

    Purpose:
    - Audit trail for all shell commands executed by agents
    - Security tracking for host filesystem access
    - Timeout enforcement and command validation

    Governance:
    - AUTONOMOUS agents only (maturity_level check)
    - Command whitelist validation (ls, pwd, cat, grep, git, etc.)
    - 5-minute maximum execution timeout
    - Working directory restrictions
    """
    __tablename__ = "shell_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Who
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    maturity_level = Column(String, nullable=False)  # AUTONOMOUS required

    # What
    command = Column(Text, nullable=False)  # Shell command executed
    command_whitelist_valid = Column(Boolean, nullable=False)  # True if in whitelist
    working_directory = Column(String, nullable=True)  # Host directory

    # Result
    exit_code = Column(Integer, nullable=True)  # 0 = success
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    timed_out = Column(Boolean, default=False)  # True if killed by timeout

    # When
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)  # Execution duration

    # Governance
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)  # NULL = auto-approved for AUTONOMOUS
    approval_required = Column(Boolean, default=False)  # True for lower maturity

    # Relationships
    agent = relationship("AgentRegistry", backref="shell_sessions")
    user = relationship("User", foreign_keys=[user_id], backref="shell_sessions_initiated")
    approver = relationship("User", foreign_keys=[approved_by])
```

Add import if uuid not already imported: `import uuid`
  </action>
  <verify>
```bash
# Verify ShellSession model exists
grep -n "class ShellSession" backend/core/models.py
grep -n "__tablename__ = \"shell_sessions\"" backend/core/models.py
grep -n "AUTONOMOUS agents only" backend/core/models.py
```
  </verify>
  <done>
ShellSession model added to models.py:
- Table name: shell_sessions
- Fields: agent_id, command, exit_code, stdout, stderr, timed_out, governance fields
- Relationships: agent, user, approver
- Audit trail for all shell commands
  </done>
</task>

<task type="auto">
  <name>Create HostShellService with governance gates</name>
  <files>backend/core/host_shell_service.py</files>
  <action>
Create backend/core/host_shell_service.py (300-400 lines):

```python
"""
Host Shell Service - Governed shell command execution on host filesystem.

OpenClaw Integration: AUTONOMOUS agents can execute whitelisted shell commands
on host filesystem through Docker bind mounts with full audit trail.
"""

import asyncio
import os
import subprocess
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.agent_governance_service import agent_governance_service
from core.models import ShellSession, AgentRegistry
from core.governance_cache import get_governance_cache

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
    "df", "du", "ps", "top", "htop",
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
        # Step 1: Check maturity using cache for speed
        cache = await get_governance_cache()
        agent_key = f"agent:{agent_id}"
        agent_data = await cache.get(agent_key)

        if not agent_data:
            raise PermissionError(f"Agent {agent_id} not found in governance cache")

        maturity_level = agent_data.get("maturity_level", "STUDENT")

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
            # TODO: Make this configurable via environment variable
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
                stdout, stderr = await process.communicate()
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
```

Follow Atom patterns:
- Service pattern with Session injection
- GovernanceCache for <1ms maturity checks
- Async/await for shell execution
- Type hints and docstrings
  </action>
  <verify>
```bash
# Verify service created
test -f backend/core/host_shell_service.py
grep -n "class HostShellService" backend/core/host_shell_service.py
grep -n "COMMAND_WHITELIST" backend/core/host_shell_service.py
grep -n "AUTONOMOUS required" backend/core/host_shell_service.py
```
  </verify>
  <done>
HostShellService created with:
- AUTONOMOUS maturity gate using GovernanceCache
- Command whitelist (ls, cat, grep, git, npm, etc.)
- Blocked commands (rm, mv, chmod, kill, sudo, etc.)
- 5-minute timeout enforcement
- ShellSession audit logging
- Working directory validation
- Async shell execution with asyncio.create_subprocess_shell
  </done>
</task>

<task type="auto">
  <name>Create shell API routes</name>
  <files>backend/api/shell_routes.py</files>
  <action>
Create backend/api/shell_routes.py (150-200 lines):

```python
"""
Shell Routes - REST API for host shell command execution.

OpenClaw Integration: AUTONOMOUS agents can execute shell commands
on host filesystem through governed API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from core.host_shell_service import host_shell_service
from core.models import get_db, ShellSession
from core.agent_governance_service import agent_governance_service

router = APIRouter(prefix="/api/shell", tags=["Shell"])


class ShellCommandRequest(BaseModel):
    command: str
    working_directory: Optional[str] = None
    timeout: int = 300  # 5 minutes default


class ShellCommandResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    session_id: str
    duration_seconds: float


@router.post("/execute", response_model=ShellCommandResponse)
async def execute_shell_command(
    request: ShellCommandRequest,
    agent_id: str,
    user_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Execute shell command on host filesystem.

    **Governance Requirements:**
    - Agent must be AUTONOMOUS maturity level
    - Command must be in whitelist (ls, cat, grep, git, npm, etc.)
    - Blocked commands are rejected (rm, mv, chmod, kill, sudo, etc.)
    - Working directory must be within allowed mount points
    - 5-minute timeout enforced

    **Audit Trail:**
    - All commands logged to ShellSession table
    - Includes command, exit code, stdout, stderr, duration
    - Traceable by agent_id and user_id

    **OpenClaw Integration:**
    This provides the "God Mode" local agent capability with
    Atom's governance-first approach (AUTONOMOUS gate + whitelist).
    """
    try:
        # Validate command first (fast check)
        validation = host_shell_service.validate_command(request.command)

        if not validation.get("valid"):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Command validation failed",
                    "reason": validation.get("reason"),
                    "allowed_commands": validation.get("allowed_commands")
                }
            )

        # Execute with governance checks
        result = await host_shell_service.execute_shell_command(
            agent_id=agent_id,
            user_id=user_id,
            command=request.command,
            working_directory=request.working_directory,
            timeout=request.timeout,
            db=db
        )

        return ShellCommandResponse(**result)

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shell execution failed: {str(e)}")


@router.get("/sessions")
async def list_shell_sessions(
    agent_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List shell command execution sessions.

    Returns audit trail of shell commands executed by agents.
    """
    query = db.query(ShellSession)

    if agent_id:
        query = query.filter(ShellSession.agent_id == agent_id)

    sessions = query.order_by(ShellSession.started_at.desc()).limit(limit).all()

    return {
        "sessions": [
            {
                "id": s.id,
                "agent_id": s.agent_id,
                "command": s.command,
                "exit_code": s.exit_code,
                "timed_out": s.timed_out,
                "started_at": s.started_at.isoformat(),
                "duration_seconds": s.duration_seconds
            }
            for s in sessions
        ]
    }


@router.get("/validate")
async def validate_command(command: str):
    """
    Validate shell command against whitelist.

    Fast validation without execution.
    """
    result = host_shell_service.validate_command(command)
    return result
```

Follow Atom API patterns:
- BaseAPIRouter for standardized responses
- Pydantic models for request/response
- Dependency injection for database
- Error handling with HTTPException
  </action>
  <verify>
```bash
# Verify routes created
test -f backend/api/shell_routes.py
grep -n "POST /api/shell/execute" backend/api/shell_routes.py
grep -n "AUTONOMOUS maturity" backend/api/shell_routes.py
```
  </verify>
  <done>
Shell routes created with:
- POST /api/shell/execute - Execute command with governance
- GET /api/shell/sessions - List audit trail
- GET /api/shell/validate - Fast command validation
- Pydantic models for type safety
- Error handling for permission failures
  </done>
</task>

<task type="auto">
  <name>Create tests for HostShellService</name>
  <files>backend/tests/test_host_shell_service.py</files>
  <action>
Create backend/tests/test_host_shell_service.py (250-300 lines):

```python
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
        with patch('core.host_shell_service.get_governance_cache') as mock_cache:
            # Mock cache returning AUTONOMOUS agent
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "AUTONOMOUS"
            })
            mock_cache.return_value = mock_cache_instance

            with patch('core.host_shell_service.asyncio.create_subprocess_shell') as mock_subprocess:
                # Mock subprocess
                mock_process = Mock()
                mock_process.returncode = 0
                mock_process.communicate = AsyncMock(return_value=(b"output", b""))

                mock_subprocess.return_value = mock_process

                # Execute
                result = await host_shell_service.execute_shell_command(
                    agent_id="test-agent",
                    user_id="test-user",
                    command="ls -la",
                    db=None
                )

                assert result["exit_code"] == 0
                assert result["stdout"] == "output"
                assert result["timed_out"] is False

    @pytest.mark.asyncio
    async def test_student_agent_blocked(self):
        """STUDENT agents cannot execute shell commands."""
        with patch('core.host_shell_service.get_governance_cache') as mock_cache:
            # Mock cache returning STUDENT agent
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "STUDENT"
            })
            mock_cache.return_value = mock_cache_instance

            # Should raise PermissionError
            with pytest.raises(PermissionError) as exc_info:
                await host_shell_service.execute_shell_command(
                    agent_id="test-agent",
                    user_id="test-user",
                    command="ls -la",
                    db=None
                )

            assert "AUTONOMOUS maturity" in str(exc_info.value)
            assert "STUDENT" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_supervised_agent_blocked(self):
        """SUPERVISED agents cannot execute shell commands."""
        with patch('core.host_shell_service.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "SUPERVISED"
            })
            mock_cache.return_value = mock_cache_instance

            with pytest.raises(PermissionError) as exc_info:
                await host_shell_service.execute_shell_command(
                    agent_id="test-agent",
                    user_id="test-user",
                    command="ls -la",
                    db=None
                )

            assert "AUTONOMOUS maturity" in str(exc_info.value)


class TestAuditTrail:
    """Test ShellSession audit logging."""

    @pytest.mark.asyncio
    async def test_shell_session_created(self):
        """ShellSession record created for each command."""
        with patch('core.host_shell_service.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "AUTONOMOUS"
            })
            mock_cache.return_value = mock_cache_instance

            with patch('core.host_shell_service.asyncio.create_subprocess_shell') as mock_subprocess:
                mock_process = Mock()
                mock_process.returncode = 0
                mock_process.communicate = AsyncMock(return_value=(b"output", b""))
                mock_subprocess.return_value = mock_process

                # Mock database
                mock_db = Mock()
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
        with patch('core.host_shell_service.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "AUTONOMOUS"
            })
            mock_cache.return_value = mock_cache_instance

            with patch('core.host_shell_service.asyncio.create_subprocess_shell') as mock_subprocess:
                # Mock failing command
                mock_process = Mock()
                mock_process.returncode = 1
                mock_process.communicate = AsyncMock(return_value=(b"", b"error"))
                mock_subprocess.return_value = mock_process

                mock_db = Mock()
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
        with patch('core.host_shell_service.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "AUTONOMOUS"
            })
            mock_cache.return_value = mock_cache_instance

            with patch('core.host_shell_service.asyncio.create_subprocess_shell') as mock_subprocess:
                mock_process = Mock()
                mock_process.kill = Mock()
                # Mock timeout
                mock_process.communicate = AsyncMock(
                    side_effect=asyncio.TimeoutError
                )
                mock_subprocess.return_value = mock_process

                mock_db = Mock()
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
        with patch('core.host_shell_service.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "AUTONOMOUS"
            })
            mock_cache.return_value = mock_cache_instance

            with patch('core.host_shell_service.asyncio.create_subprocess_shell') as mock_subprocess:
                mock_process = Mock()
                mock_process.returncode = 0
                mock_process.communicate = AsyncMock(return_value=(b"", b""))
                mock_subprocess.return_value = mock_process

                with patch.dict(os.environ, {"ATOM_HOST_MOUNT_DIRS": "/tmp:/home:/Users"}):
                    result = await host_shell_service.execute_shell_command(
                        agent_id="test-agent",
                        user_id="test-user",
                        command="ls",
                        working_directory="/tmp/project",
                        db=None
                    )

                    assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_blocked_directory_rejected(self):
        """Working directories not in allowed list are rejected."""
        with patch('core.host_shell_service.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "AUTONOMOUS"
            })
            mock_cache.return_value = mock_cache_instance

            with patch.dict(os.environ, {"ATOM_HOST_MOUNT_DIRS": "/tmp:/home:/Users"}):
                with pytest.raises(PermissionError) as exc_info:
                    await host_shell_service.execute_shell_command(
                        agent_id="test-agent",
                        user_id="test-user",
                        command="ls",
                        working_directory="/etc",  # Not allowed
                        db=None
                    )

                assert "not in allowed directories" in str(exc_info.value)
```

Coverage targets:
- Command validation logic (whitelist, blocked, empty)
- Maturity gates (AUTONOMOUS vs STUDENT/SUPERVISED)
- Audit trail logging
- Timeout enforcement
- Working directory restrictions
  </action>
  <verify>
```bash
# Run tests
cd backend && pytest tests/test_host_shell_service.py -v
# Should show 15+ tests passing
```
  </verify>
  <done>
Tests created for HostShellService:
- 5 tests for command validation (whitelist, blocked, empty)
- 3 tests for maturity gate (AUTONOMOUS, STUDENT, SUPERVISED)
- 3 tests for audit trail logging
- 2 tests for timeout enforcement
- 2 tests for working directory restrictions
- Total: 15+ tests with comprehensive coverage
  </done>
</task>

<task type="auto">
  <name>Create Docker host mount configuration</name>
  <files>backend/docker/docker-compose.host-mount.yml, backend/docker/host-mount-setup.sh</files>
  <action>
Create Docker configuration for host filesystem access.

**1. Create backend/docker/docker-compose.host-mount.yml:**

```yaml
# Docker Compose configuration for host filesystem mount
# OpenClaw Integration: AUTONOMOUS agents can access host directories
#
# SECURITY WARNING: This gives container write access to host filesystem.
# Only use with AUTONOMOUS maturity gate + command whitelist + audit trail.
#
# Usage:
#   docker-compose -f docker-compose.yml -f docker-compose.host-mount.yml up

version: '3.8'

services:
  atom-api:
    volumes:
      # Host project directories (read-write)
      - /Users/${USER}/projects:/host/projects:rw
      - /Users/${USER}/Desktop:/host/desktop:rw
      - /Users/${USER}/Documents:/host/documents:rw
      - /tmp:/host/tmp:rw

    environment:
      # Configure allowed mount directories
      - ATOM_HOST_MOUNT_DIRS=/tmp:/Users/${USER}/projects:/Users/${USER}/Desktop:/Users/${USER}/Documents
      - ATOM_HOST_MOUNT_ENABLED=true

    # Capabilities for filesystem access
    cap_add:
      - SYS_ADMIN  # Required for some filesystem operations

    # Security notes
    # - volumes: Explicitly list only required directories
    # - environment: ATOM_HOST_MOUNT_DIRS must match volumes
    # - governance: AUTONOMOUS gate enforced in HostShellService
    # - audit: All commands logged to ShellSession table
```

**2. Create backend/docker/host-mount-setup.sh:**

```bash
#!/bin/bash
# Host mount setup script for Atom OpenClaw integration
#
# This script configures Docker volumes for host filesystem access
# with security warnings and governance verification.

set -e

echo "=================================="
echo "Atom Host Filesystem Mount Setup"
echo "OpenClaw Integration"
echo "=================================="
echo ""

# Security warning
echo "⚠️  SECURITY WARNING ⚠️"
echo ""
echo "This configuration gives Atom containers WRITE access to host directories."
echo ""
echo "Governance protections in place:"
echo "  ✓ AUTONOMOUS maturity gate required"
echo "  ✓ Command whitelist (ls, cat, grep, git, npm, etc.)"
echo "  ✓ Blocked commands (rm, mv, chmod, kill, sudo, etc.)"
echo "  ✓ 5-minute timeout enforcement"
echo "  ✓ Full audit trail to ShellSession table"
echo ""
echo "However, this STILL carries risk:"
echo "  - Bugs in governance code could bypass protections"
echo "  - Compromised AUTONOMOUS agent has shell access"
echo "  - Docker escape vulnerabilities could be exploited"
echo ""

read -p "Do you understand the risks and want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Setup cancelled."
    exit 1
fi

echo ""
echo "Configuring host mounts..."
echo ""

# Detect user
CURRENT_USER=${USER:-$(whoami)}
echo "Detected user: $CURRENT_USER"

# Create .env file for host mount configuration
cat > backend/.env.host-mount <<EOF
# Host filesystem mount configuration
# Generated by host-mount-setup.sh

ATOM_HOST_MOUNT_ENABLED=true
ATOM_HOST_MOUNT_DIRS=/tmp:/Users/$CURRENT_USER/projects:/Users/$CURRENT_USER/Desktop:/Users/$CURRENT_USER/Documents

# Security
ATOM_HOST_MOUNT_GATES=autonomous_only,command_whitelist,timeout_enforcement,audit_trail
EOF

echo "Created backend/.env.host-mount"
echo ""

# Test Docker volume access
echo "Testing Docker volume access..."
if docker run --rm -v /Users/$CURRENT_USER/Desktop:/host/desktop:ro alpine ls /host/desktop > /dev/null 2>&1; then
    echo "✓ Docker volume access working"
else
    echo "✗ Docker volume access failed"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check Docker Desktop: Settings > Resources > File Sharing"
    echo "  2. Add /Users/$CURRENT_USER to shared directories"
    echo "  3. Restart Docker"
    exit 1
fi

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "To start Atom with host mount:"
echo ""
echo "  docker-compose -f docker-compose.yml -f docker-compose.host-mount.yml up"
echo ""
echo "To verify mount is active:"
echo ""
echo "  docker exec \$(docker ps -q -f 'name=atom') ls /host/projects"
echo ""
echo "To disable host mount:"
echo ""
echo "  docker-compose -f docker-compose.yml up  # (omit host-mount file)"
echo ""
```

Make script executable:

```bash
chmod +x backend/docker/host-mount-setup.sh
```

**3. Add to backend/README.md:**

```markdown
## Host Filesystem Access (OpenClaw Integration)

Atom supports AUTONOMOUS agents executing shell commands on host filesystem through Docker bind mounts.

**Governance Protections:**
- AUTONOMOUS maturity gate (STUDENT/SUPERVISED blocked)
- Command whitelist (ls, cat, grep, git, npm, pip, make, etc.)
- Blocked commands (rm, mv, chmod, kill, sudo, reboot, etc.)
- 5-minute timeout enforcement
- Full audit trail to ShellSession table

**Setup:**

1. Run setup script:
   ```bash
   ./backend/docker/host-mount-setup.sh
   ```

2. Start Atom with host mount:
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.host-mount.yml up
   ```

3. Verify mount is active:
   ```bash
   docker exec $(docker ps -q -f 'name=atom') ls /host/projects
   ```

**Security:**
This gives containers write access to host directories. Only enable after:
- Reviewing governance code (host_shell_service.py)
- Understanding audit trail (ShellSession model)
- Testing with non-AUTONOMOUS agents (should be blocked)
```
  </action>
  <verify>
```bash
# Verify files created
test -f backend/docker/docker-compose.host-mount.yml
test -f backend/docker/host-mount-setup.sh
grep -n "AUTONOMOUS maturity" backend/docker/docker-compose.host-mount.yml
grep -n "SECURITY WARNING" backend/docker/host-mount-setup.sh
```
  </verify>
  <done>
Docker host mount configuration created:
- docker-compose.host-mount.yml: Volume mounts + environment vars
- host-mount-setup.sh: Interactive setup script with security warnings
- Documentation in README.md with usage examples
- Governance verification steps before enabling
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. ShellSession model exists with governance fields (maturity_level, command_whitelist_valid)
2. HostShellService implements AUTONOMOUS gate using GovernanceCache
3. Command whitelist includes safe commands (ls, cat, grep, git, npm)
4. Blocked commands rejected (rm, mv, chmod, kill, sudo)
5. Shell API routes exposed (POST /api/shell/execute)
6. Tests cover maturity gates, validation, timeout, audit trail
7. Docker compose configuration for host mount
8. Setup script with security warnings
9. Documentation in README.md
</verification>

<success_criteria>
- AUTONOMOUS agents can execute whitelisted shell commands
- STUDENT/SUPERVISED agents blocked from shell access
- All shell commands logged to ShellSession audit trail
- Docker host mount configuration documented with security warnings
- Test coverage >80% for HostShellService
- Setup script works interactively
</success_criteria>

<output>
After completion, create `.planning/phases/13-openclaw-integration/13-openclaw-integration-01-SUMMARY.md` with:
- Files created/modified
- AUTONOMOUS gate implementation details
- Command whitelist (safe commands)
- Blocked commands (dangerous)
- Docker mount configuration
- Test coverage results
- Security warnings and recommendations
</output>
