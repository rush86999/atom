---
phase: 02-local-agent
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/local_agent_service.py
  - backend/api/local_agent_routes.py
  - backend/cli/local_agent.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Local agent can start as standalone process on host machine (outside Docker)"
    - "Local agent communicates with backend via REST API for governance checks"
    - "Local agent can execute shell commands with maturity-based permissions"
    - "All shell executions logged to ShellSession audit trail"
  artifacts:
    - path: "backend/core/local_agent_service.py"
      provides: "Local agent orchestration service"
      min_lines: 150
    - path: "backend/api/local_agent_routes.py"
      provides: "REST API for local agent communication"
      exports: ["POST /api/local-agent/execute", "POST /api/local-agent/approve", "GET /api/local-agent/status"]
    - path: "backend/cli/local_agent.py"
      provides: "CLI commands for local agent management"
      min_lines: 100
  key_links:
    - from: "backend/core/local_agent_service.py"
      to: "backend/core/host_shell_service.py"
      via: "Composition (HostShellService instance)"
      pattern: "host_shell_service.execute_shell_command"
    - from: "backend/api/local_agent_routes.py"
      to: "/api/local-agent/execute"
      via: "FastAPI endpoint"
      pattern: "router.post.*execute"
---

<objective>
Implement LocalAgentService as standalone host process that communicates with Atom backend via REST API for governance checks and audit logging.

Purpose: Enable "God Mode" local agent that runs outside Docker container on host machine with controlled shell/file access, using Atom's maturity model to earn trust over time.

Output: LocalAgentService (orchestration), local_agent_routes.py (REST API), CLI commands (start/status/stop)
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/FEATURE_ROADMAP.md
@.planning/phases/02-local-agent/02-RESEARCH.md
@backend/core/host_shell_service.py
@backend/core/governance_cache.py
@backend/core/models.py
@backend/cli/daemon.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create LocalAgentService core orchestration</name>
  <files>backend/core/local_agent_service.py</files>
  <action>
Create LocalAgentService class with:
- __init__(backend_url: str) - Configure backend API URL
- execute_command(agent_id, command, working_directory, db) - Main entry point
- _check_governance(agent_id, command, directory) - Call backend API for maturity check
- _log_execution(session_data) - POST to backend /api/shell/log
- _execute_locally(command, directory) - Use asyncio.create_subprocess_exec (NOT shell=True)

Key design decisions (from RESEARCH.md):
- Use httpx.AsyncClient for HTTP communication (not requests - async support)
- Call backend /api/agents/{id}/governance for maturity check
- Use asyncio.create_subprocess_exec with list args (prevent injection)
- Timeout enforcement via asyncio.wait_for (5-minute max)

DO NOT use shell=True in subprocess (command injection risk).
DO NOT access database directly (use REST API for governance checks).
  </action>
  <verify>
grep -q "asyncio.create_subprocess_exec" backend/core/local_agent_service.py && grep -q "httpx.AsyncClient" backend/core/local_agent_service.py && ! grep -q "shell=True" backend/core/local_agent_service.py
  </verify>
  <done>
LocalAgentService created with:
- Backend API communication via httpx.AsyncClient
- Safe subprocess execution (shell=False, list args)
- Timeout enforcement (5-minute max)
- No direct database access
  </done>
</task>

<task type="auto">
  <name>Task 2: Create REST API routes for local agent communication</name>
  <files>backend/api/local_agent_routes.py</files>
  <action>
Create FastAPI router with:
- POST /api/local-agent/execute - Execute command (returns approval_required if maturity < needed)
- POST /api/local-agent/approve - Approve pending command (for STUDENT/INTERN agents)
- GET /api/local-agent/status - Check local agent status
- POST /api/local-agent/start - Start local agent process
- POST /api/local-agent/stop - Stop local agent process

Use FastAPI dependency injection for database session (db: Session = Depends(get_db)).
Return Pydantic models for responses (not plain dicts).
Include error handling for:
- Agent not found (404)
- Permission denied (403)
- Command not in whitelist (400)
- Backend unreachable (503)

Reuse existing governance patterns from atom_agent_endpoints.py.
  </action>
  <verify>
grep -q "router.post.*execute" backend/api/local_agent_routes.py && grep -q "router.post.*approve" backend/api/local_agent_routes.py && grep -q "router.get.*status" backend/api/local_agent_routes.py
  </verify>
  <done>
REST API routes created with:
- Execute endpoint (governance check + execution)
- Approve endpoint (user approval flow for lower maturity)
- Status endpoint (local agent health check)
- Start/stop endpoints (lifecycle management)
- FastAPI dependency injection for database
- Pydantic response models
  </done>
</task>

<task type="auto">
  <name>Task 3: Create CLI commands for local agent management</name>
  <files>backend/cli/local_agent.py</files>
  <action>
Create Click-based CLI with commands:
- atom-os local-agent start --port 8000 --host localhost - Start local agent as daemon
- atom-os local-agent status - Check if local agent running
- atom-os local-agent stop - Stop local agent daemon
- atom-os local-agent execute "<command>" --directory /tmp - Execute command (for testing)

Reuse existing DaemonManager from cli/daemon.py for PID tracking.
Add --backend-url option for custom backend URL (default: http://localhost:8000).
Display security warnings when starting local agent:
- "Local agent will have access to host filesystem"
- "AUTONOMOUS agents can execute commands without approval"
- "All executions logged to audit trail"

Follow Click framework patterns from cli/main.py (existing atom-os CLI).
  </action>
  <verify>
grep -q "local-agent" backend/cli/main.py && grep -q "@click.command" backend/cli/local_agent.py || grep -q "@click.group" backend/cli/local_agent.py
  </verify>
  <done>
CLI commands created with:
- Click-based interface (start/status/stop/execute)
- DaemonManager integration for PID tracking
- Backend URL configuration
- Security warnings on startup
- Follows existing atom-os CLI patterns
  </done>
</task>

</tasks>

<verification>
1. Local agent can start: `python -m atom.local_agent_main` (or via CLI)
2. Local agent communicates with backend: check logs for HTTP requests
3. Governance check happens before execution: STUDENT agents blocked
4. AUTONOMOUS agents can execute safe commands: try `ls /tmp`
5. Audit trail created: check ShellSession table for new entries
</verification>

<success_criteria>
1. LocalAgentService implements maturity-based command execution (STUDENT blocked, AUTONOMOUS allowed)
2. REST API provides execute/approve/status endpoints
3. CLI commands enable local agent lifecycle management
4. All executions logged to ShellSession with full audit trail
5. Command injection protection (shell=False, list args)
</success_criteria>

<output>
After completion, create `.planning/phases/02-local-agent/02-local-agent-01-SUMMARY.md` with:
- LocalAgentService implementation details
- API endpoints created (with example requests)
- CLI usage examples
- Integration with existing HostShellService
</output>
