---
phase: 25-atom-cli-openclaw-skill
plan: 02
type: execute
wave: 1
depends_on: [01]
files_modified:
  - backend/tools/atom_cli_skill_wrapper.py
autonomous: true

must_haves:
  truths:
    - "Skills can execute Atom CLI commands via subprocess with proper error handling"
    - "Subprocess wrapper returns structured output (success, stdout, stderr, returncode)"
    - "Commands timeout after 30 seconds to prevent hanging"
    - "Wrapper logs all execution attempts for audit trail"
    - "Skills use subprocess wrapper for CLI invocation"
  artifacts:
    - path: "backend/tools/atom_cli_skill_wrapper.py"
      provides: "Subprocess wrapper for Atom CLI command execution"
      contains: "execute_atom_cli_command function"
      contains: "timeout=30"
      contains: "subprocess.run"
  key_links:
    - from: "backend/tools/atom_cli_skill_wrapper.py"
      to: "cli/main.py"
      via: "subprocess.run with atom-os command"
      pattern: "subprocess.run\\(\\[.*atom-os"
    - from: "backend/core/skill_adapter.py"
      to: "backend/tools/atom_cli_skill_wrapper.py"
      via: "CommunitySkillTool imports wrapper"
      pattern: "from tools.atom_cli_skill_wrapper import"
---

<objective>
Create subprocess wrapper service for executing Atom CLI commands from skills.

Purpose: Enable prompt-only skills to invoke Atom CLI commands via subprocess with structured output, error handling, timeout enforcement, and audit logging.

Output: atom_cli_skill_wrapper.py with execute_atom_cli_command function, integration with CommunitySkillTool.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/25-atom-cli-openclaw-skill/25-RESEARCH.md
@.planning/phases/25-atom-cli-openclaw-skill/25-atom-cli-openclaw-skill-01-SUMMARY.md
@backend/tools/atom_cli_skill_wrapper.py (to be created)
@backend/core/skill_adapter.py
@backend/cli/daemon.py
@backend/core/skill_registry_service.py
</context>

<tasks>

<task type="auto">
  <name>Create atom_cli_skill_wrapper.py with subprocess execution</name>
  <files>backend/tools/atom_cli_skill_wrapper.py</files>
  <action>
    Create backend/tools/atom_cli_skill_wrapper.py with:

    1. execute_atom_cli_command(command, args=None) function:
       - Builds command list: ["atom-os", command] + args
       - Uses subprocess.run with:
         - capture_output=True
         - text=True
         - timeout=30
       - Returns dict with:
         - success: bool (returncode == 0)
         - stdout: str
         - stderr: str
         - returncode: int
       - Handles subprocess.TimeoutExpired (returns success=False, stderr="Command timed out")
       - Handles generic Exception (returns success=False, stderr=str(e))

    2. Logging:
       - Use logging.getLogger(__name__)
       - Log command execution: logger.info(f"Executing: atom-os {command}")
       - Log errors: logger.error(f"Command failed: {e}")

    3. Helper functions:
       - is_daemon_running(): Check if daemon is active (uses status command)
       - get_daemon_pid(): Extract PID from status output
       - wait_for_daemon_ready(max_wait=10): Poll status until running

    4. Docstring examples matching 25-RESEARCH.md Example 2 pattern

    5. Type hints: def execute_atom_cli_command(command: str, args: list = None) -> Dict[str, Any]

    Follow 25-RESEARCH.md Pattern 2: Subprocess Execution Wrapper.
  </action>
  <verify>
    File exists with execute_atom_cli_command function
    Function returns dict with success, stdout, stderr, returncode keys
    Timeout handling includes subprocess.TimeoutExpired exception
    Type hints present on function signature
    Docstring includes usage example
  </verify>
  <done>
    atom_cli_skill_wrapper.py created with subprocess wrapper, timeout handling, structured return value
  </done>
</task>

<task type="auto">
  <name>Integrate wrapper with CommunitySkillTool</name>
  <files>backend/core/skill_adapter.py backend/tools/atom_cli_skill_wrapper.py</files>
  <action>
    Update backend/core/skill_adapter.py:

    1. Import at top:
       from tools.atom_cli_skill_wrapper import execute_atom_cli_command

    2. Add CLI command execution support to CommunitySkillTool._run:
       - Check if skill_name starts with "atom-" (indicates CLI skill)
       - For CLI skills, call execute_atom_cli_command instead of prompt interpolation
       - Parse query for arguments (simple space-based splitting)
       - Return formatted result with stdout/stderr

    3. Add _execute_cli_skill method:
       - Extract command name from skill_id (e.g., "atom-daemon" -> "daemon")
       - Parse args from query (split on spaces, strip quotes)
       - Call execute_atom_cli_command
       - Format output for LLM (success message or error)

    4. Log execution: logger.info(f"Executing CLI skill: {command} with args: {args}")

    5. Handle special case for atom-config with --show-daemon flag

    Integration pattern: Existing skills use _execute_prompt_skill, CLI skills use _execute_cli_skill.
  </action>
  <verify>
    skill_adapter.py imports execute_atom_cli_command
    CommunitySkillTool has _execute_cli_skill method
    CLI skill detection checks skill_id prefix (atom-*)
    Execution logs command and args
  </verify>
  <done>
    CommunitySkillTool updated to invoke CLI commands via wrapper, atom-* skills routed to _execute_cli_skill
  </done>
</task>

<task type="auto">
  <name>Add daemon polling helper functions</name>
  <files>backend/tools/atom_cli_skill_wrapper.py</files>
  <action>
    Add helper functions to atom_cli_skill_wrapper.py for daemon readiness:

    1. is_daemon_running() -> bool:
       - Calls execute_atom_cli_command("status")
       - Parses output for "RUNNING" status
       - Returns True if running, False otherwise

    2. get_daemon_pid() -> Optional[int]:
       - Calls execute_atom_cli_command("status")
       - Uses regex to extract PID: r"PID:\s+(\d+)"
       - Returns int PID or None

    3. wait_for_daemon_ready(max_wait=10) -> bool:
       - Polls is_daemon_running() every 0.5 seconds
       - Times out after max_wait seconds
       - Returns True if daemon ready, False if timeout
       - Logs progress: logger.info(f"Waiting for daemon... {elapsed}s")

    4. Add unit test helpers:
       - mock_daemon_response(stdout, stderr, returncode) for testing
       - Command builder: build_command_args(port, host, workers, etc.)

    Follow 25-RESEARCH.md Pitfall 4: Add polling loop to verify daemon status after start.
  </action>
  <verify>
    is_daemon_running() function exists
    get_daemon_pid() function exists with regex extraction
    wait_for_daemon_ready() function exists with polling loop
    All functions have type hints and docstrings
  </verify>
  <done>
    Daemon helper functions added with polling, PID extraction, and status checking capabilities
  </done>
</task>

</tasks>

<verification>
1. atom_cli_skill_wrapper.py exists with execute_atom_cli_command function
2. Function handles subprocess, timeout, and exceptions correctly
3. CommunitySkillTool updated to use wrapper for atom-* skills
4. Daemon helper functions (is_daemon_running, get_daemon_pid, wait_for_daemon_ready) implemented
5. All functions have type hints and docstrings
6. Wrapper logs all execution attempts
</verification>

<success_criteria>
1. Subprocess wrapper executes atom-os commands successfully
2. Timeout (30s) prevents hanging commands
3. Structured output (success, stdout, stderr, returncode) returned
4. CLI skills (atom-*) routed to wrapper via CommunitySkillTool
5. Daemon polling prevents race conditions after start
</success_criteria>

<output>
After completion, create `.planning/phases/25-atom-cli-openclaw-skill/25-atom-cli-openclaw-skill-02-SUMMARY.md` with:
- Wrapper function signature and return format
- Timeout and exception handling details
- CommunitySkillTool integration changes
- Daemon helper functions
- Test execution examples
- Next steps (Plan 03: skill import and execution tests)
</output>
