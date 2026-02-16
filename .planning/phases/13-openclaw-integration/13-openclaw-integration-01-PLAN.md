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
      provides: REST API endpoints for shell operations
      exports: ["POST /api/shell/execute", "GET /api/shell/status"]
    - path: backend/docker/docker-compose.host-mount.yml
      provides: Docker Compose configuration for host filesystem mounting
      contains: "volumes:", "${HOME}:/host"
    - path: backend/core/models.py
      provides: ShellSession database model for audit trail
      contains: "class ShellSession"
  key_links:
    - from: backend/api/shell_routes.py
      to: backend/core/host_shell_service.py
      via: Service instantiation and method calls
      pattern: "HostShellService\(db\)"
    - from: backend/core/host_shell_service.py
      to: backend/core/governance_cache.py
      via: Governance check before shell execution
      pattern: "can_perform_action.*shell_execute"
    - from: backend/core/host_shell_service.py
      to: backend/core/models.py
      via: ShellSession creation for audit logging
      pattern: "ShellSession\("
---

<objective>
Implement Governed Host Shell Access (God Mode Local Agent)

Enable AUTONOMOUS agents to execute shell commands on the host filesystem through Docker bind mounts, with strict governance, command whitelisting, and comprehensive audit logging.

Purpose: Provide agents with controlled host filesystem access for file operations, system monitoring, and automation tasks while maintaining Atom's governance-first security model.

Output: HostShellService with governance integration, shell API endpoints, Docker host-mount configuration, and comprehensive test coverage.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/13-openclaw-integration/13-RESEARCH.md

# Docker Bind Mount Patterns
@backend/core/agent_governance_service.py  # Governance pattern reference
@backend/api/agent_governance_routes.py    # API pattern reference
@backend/core/base_routes.py               # BaseAPIRouter pattern
@backend/core/models.py                    # Database model patterns
@backend/tools/device_tool.py              # Command execution pattern reference
</context>

<tasks>

<task type="auto">
  <name>Create ShellSession database model with audit fields</name>
  <files>backend/core/models.py</files>
  <action>
    Add ShellSession model to backend/core/models.py:

    1. Create new model after existing Agent models (around line 1300):
       - id (String, primary key, UUID)
       - agent_id (String, ForeignKey to agent_registry.id)
       - command (Text, the executed shell command)
       - arguments (JSON, command arguments as array)
       - working_directory (String, execution directory)
       - exit_code (Integer, command exit status)
       - stdout (Text, command output)
       - stderr (Text, error output)
       - duration_ms (Integer, execution time)
       - status (String: pending, running, completed, failed, timeout)
       - governance_maturity (String, agent maturity at time of execution)
       - created_at, started_at, completed_at (DateTime timestamps)

    2. Add relationship to AgentRegistry:
       - shell_sessions = relationship("ShellSession", backref="agent")

    3. Add indexes on agent_id, status, created_at for query performance

    4. Include __repr__ method for debugging

    DO NOT modify existing models or migrations (migration will be separate task)
  </action>
  <verify>grep -n "class ShellSession" backend/core/models.py returns the model definition</verify>
  <done>ShellSession model exists with all required fields, indexes, and relationship</done>
</task>

<task type="auto">
  <name>Implement HostShellService with governance and command validation</name>
  <files>backend/core/host_shell_service.py</files>
  <action>
    Create backend/core/host_shell_service.py with:

    1. HostShellService class following existing service patterns:
       - __init__(self, db: Session)
       - Use logging with get_logger(__name__)
       - Type hints on all methods

    2. Command whitelist (class-level constant):
       ALLOWED_COMMANDS = frozenset({
           "ls", "pwd", "cat", "head", "tail", "grep", "find",
           "wc", "du", "df", "date", "echo", "basename", "dirname",
           "file", "stat", "readlink", "realpath", "tree"
       })
       - NO destructive commands: rm, mv, cp, chmod, chown, dd, etc.
       - NO network commands: curl, wget, ssh, etc.

    3. validate_command(self, command: str) -> Dict[str, Any]:
       - Parse command string into parts
       - Check first word against ALLOWED_COMMANDS
       - Check for command chaining (|, ;, &&, ||, >, <) - BLOCKED
       - Check for escape sequences ($, `, $(..)) - BLOCKED
       - Return {"valid": bool, "error": str}

    4. async execute_shell_command(
           self, agent_id: str, command: str, working_dir: str = "/host/workspace"
       ) -> Dict[str, Any]:
       - Governance check: can_perform_action(agent_id, "shell_execute")
       - Must be AUTONOMOUS maturity - raise PermissionError if not
       - Validate command using validate_command()
       - Create ShellSession record with status="pending"
       - Execute using subprocess.run():
         * capture_output=True, timeout=300 (5 min max)
         * shell=False (critical: prevent injection)
         * cwd=working_dir
       - Update ShellSession with results (stdout, stderr, exit_code, duration_ms)
       - Return structured response with output and status

    5. get_shell_history(self, agent_id: str, limit: int = 50) -> List[ShellSession]:
       - Query ShellSession by agent_id
       - Order by created_at DESC
       - Apply limit
       - Return list

    6. get_active_sessions(self) -> List[ShellSession]:
       - Query sessions with status in ["pending", "running"]
       - Return for monitoring

    Import patterns:
    - from core.models import ShellSession, AgentRegistry
    - from core.governance_cache import get_governance_cache
    - from sqlalchemy.orm import Session
    - import subprocess, logging, uuid, asyncio
  </action>
  <verify>grep -n "ALLOWED_COMMANDS\|validate_command\|execute_shell_command" backend/core/host_shell_service.py returns method definitions</verify>
  <done>HostShellService validates commands, checks governance, executes safely, and logs to ShellSession</done>
</task>

<task type="auto">
  <name>Create shell API routes with BaseAPIRouter</name>
  <files>backend/api/shell_routes.py</files>
  <action>
    Create backend/api/shell_routes.py with:

    1. Imports following existing patterns:
       - from core.base_routes import BaseAPIRouter
       - from core.database import get_db
       - from core.host_shell_service import HostShellService
       - from pydantic import BaseModel

    2. Request models:
       - ShellExecuteRequest(command: str, working_dir: Optional[str] = "/host/workspace")
       - ShellStatusResponse(session_id: str, status: str, ...)

    3. router = BaseAPIRouter(prefix="/api/shell", tags=["Shell"])

    4. POST /api/shell/execute:
       - Accept ShellExecuteRequest
       - Get db via Depends(get_db)
       - Instantiate HostShellService(db)
       - Call execute_shell_command(agent_id, command, working_dir)
       - Return router.success_response(data=..., message="Command executed")
       - Handle errors with router.error_response()

    5. GET /api/shell/history/{agent_id}:
       - Return shell execution history for agent
       - Use get_shell_history()

    6. GET /api/shell/status/{session_id}:
       - Return status of specific shell session
       - Include output if completed

    7. GET /api/shell/active:
       - Return all active/pending shell sessions
       - Admin-only endpoint

    Follow error handling pattern from agent_governance_routes.py
    Use router.permission_denied_error() for governance failures
  </action>
  <verify>grep -n "router = BaseAPIRouter\|POST\|GET" backend/api/shell_routes.py returns route definitions</verify>
  <done>Shell API endpoints exist with proper request/response models and error handling</done>
</task>

<task type="auto">
  <name>Create Docker host-mount configuration and setup script</name>
  <files>backend/docker/docker-compose.host-mount.yml backend/docker/host-mount-setup.sh</files>
  <action>
    Create backend/docker/docker-compose.host-mount.yml:

    1. Extend existing docker-compose pattern:
       version: '3.8'
       services:
         atom-backend:
           volumes:
             # Host home directory (read-write for AUTONOMOUS agents)
             - ${HOME}:/host/home:rw
             # Project workspace directory
             - ${PWD}/../:/host/projects:rw
             # Scratch space for temporary files
             - /tmp/atom-workspace:/host/tmp:rw
           environment:
             - HOST_MOUNT_ENABLED=true
             - HOST_MOUNT_PREFIX=/host
             - HOST_HOME=/host/home

    2. Create backend/docker/host-mount-setup.sh:
       #!/bin/bash
       # Host mount setup script
       set -e
       echo "Setting up Atom host filesystem mount..."

       # Create workspace directories
       mkdir -p /tmp/atom-workspace
       mkdir -p "${HOME}/.atom/workspace"

       # Set permissions for container user
       chmod 755 /tmp/atom-workspace
       chmod 755 "${HOME}/.atom/workspace"

       echo "Host mount directories ready."
       echo "WARNING: Host mount allows AUTONOMOUS agents to access your filesystem."
       echo "Only enable for trusted agents in isolated environments."

    3. Make script executable in the task (chmod +x)
  </action>
  <verify>grep -n "volumes:\|HOST_MOUNT_ENABLED" backend/docker/docker-compose.host-mount.yml returns configuration</verify>
  <done>Docker configuration mounts host directories and setup script prepares directories</done>
</task>

<task type="auto">
  <name>Write comprehensive tests for HostShellService</name>
  <files>backend/tests/test_host_shell_service.py</files>
  <action>
    Create backend/tests/test_host_shell_service.py with:

    1. Test class structure following existing test patterns:
       import pytest
       from unittest.mock import Mock, AsyncMock, patch
       from sqlalchemy.orm import Session
       from core.host_shell_service import HostShellService
       from core.models import ShellSession, AgentRegistry

    2. Test fixtures:
       - db_session (in-memory SQLite or mock)
       - mock_agent (AgentRegistry with maturity="autonomous")
       - mock_intern_agent (maturity="intern" - should be blocked)

    3. Test validate_command:
       - test_allowed_commands_pass(): ls, cat, grep, etc.
       - test_blocked_commands_fail(): rm, mv, chmod, curl
       - test_command_chaining_blocked(): |, ;, &&, ||, >, <
       - test_escape_sequences_blocked(): $, `, $(..)

    4. Test governance enforcement:
       - test_autonomous_agent_can_execute(): AUTONOMOUS maturity allowed
       - test_intern_agent_blocked(): INTERN maturity raises PermissionError
       - test_student_agent_blocked(): STUDENT maturity raises PermissionError

    5. Test command execution:
       - test_successful_command_execution(): ls /tmp
       - test_command_timeout(): Command exceeding 300s timeout
       - test_working_directory_respected(): Command runs in specified dir
       - test_audit_log_created(): ShellSession record created

    6. Test history retrieval:
       - test_get_shell_history_returns_ordered_list()
       - test_get_active_sessions_excludes_completed()

    Use AsyncMock for async operations
    Use pytest.mark.asyncio for async tests
  </action>
  <verify>pytest backend/tests/test_host_shell_service.py -v returns passing tests</verify>
  <done>Comprehensive test coverage validates command validation, governance checks, execution, and audit logging</done>
</task>

</tasks>

<verification>
1. Governance Integration:
   - AUTONOMOUS agents can execute shell commands
   - Non-AUTONOMOUS agents are blocked with PermissionError
   - Governance check uses existing get_governance_cache pattern

2. Security Validation:
   - Command whitelist prevents dangerous operations
   - Command chaining (pipes, redirects) is blocked
   - Shell injection vectors (escapes) are blocked
   - subprocess.run(shell=False) prevents injection

3. Audit Trail:
   - All shell commands logged to ShellSession
   - Agent ID, command, output, exit code, duration recorded
   - History endpoint retrieves past executions

4. Docker Integration:
   - Host directories mounted at /host prefix
   - Working directory restricted to mounted paths
   - Setup script creates necessary directories

5. API Contract:
   - POST /api/shell/execute executes commands
   - GET /api/shell/history/{agent_id} retrieves history
   - GET /api/shell/status/{session_id} checks session status
   - All endpoints use BaseAPIRouter success/error patterns

6. Test Coverage:
   - Command validation tests (allowed/blocked/chaining/escapes)
   - Governance tests (AUTONOMOUS vs lower maturity)
   - Execution tests (success/timeout/working_dir)
   - History and active sessions tests
</verification>

<success_criteria>
1. AUTONOMOUS agents can execute whitelisted shell commands on host filesystem
2. Shell access is completely blocked for STUDENT/INTERN/SUPERVISED agents
3. All shell executions are logged to ShellSession with full audit trail
4. Command whitelist prevents destructive and network operations
5. Docker host-mount configuration enables /host filesystem access
6. API endpoints provide shell execution, history, and status querying
7. Comprehensive tests validate security, governance, and functionality
8. Existing governance patterns (GovernanceCache, BaseAPIRouter) are reused
</success_criteria>

<output>
After completion, create `.planning/phases/13-openclaw-integration/13-openclaw-integration-01-SUMMARY.md` with:
- Implemented ShellSession model with full audit fields
- HostShellService with governance-enforced command execution
- Shell API routes with BaseAPIRouter patterns
- Docker host-mount configuration
- Comprehensive test coverage for security validation

Include code snippets for:
- Command whitelist and validation logic
- Governance check pattern
- Shell execution with subprocess safety
- API endpoint examples
</output>
