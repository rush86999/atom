---
phase: 02-local-agent
plan: 03
type: execute
wave: 2
depends_on: ["01"]
files_modified:
  - backend/core/command_whitelist.py
  - backend/core/local_agent_service.py
  - backend/core/host_shell_service.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Commands validated against maturity-based whitelist before execution"
    - "STUDENT agents can only use read commands (ls, cat, grep, etc.)"
    - "INTERN agents can use read commands (requires approval)"
    - "SUPERVISED agents can use write commands (cp, mv, mkdir) with approval"
    - "AUTONOMOUS agents can use all whitelisted commands (no rm, sudo, etc.)"
    - "Blocked commands blocked for all maturity levels"
  artifacts:
    - path: "backend/core/command_whitelist.py"
      provides: "Decorator-based command whitelist enforcement"
      min_lines: 150
    - path: "backend/core/local_agent_service.py"
      provides: "Updated with whitelist decorator integration"
      contains: "@whitelisted_command"
  key_links:
    - from: "backend/core/command_whitelist.py"
      to: "backend/core/local_agent_service.py"
      via: "Decorator import and usage"
      pattern: "@whitelisted_command"
    - from: "backend/core/command_whitelist.py"
      to: "backend/core/host_shell_service.py"
      via: "Decorator import and usage"
      pattern: "@whitelisted_command"
---

<objective>
Implement decorator-based command whitelist with maturity-level restrictions, extending HostShellService with all maturity levels (not just AUTONOMOUS), and enforcing security via subprocess shell=False pattern.

Purpose: Provide defense-in-depth security with command validation at multiple layers - decorator enforces whitelist at function entry, subprocess uses safe execution pattern, and maturity levels control which commands are available.

Output: CommandWhitelistService (decorator + validation), updated HostShellService (all maturity levels), whitelist by command category
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/FEATURE_ROADMAP.md
@.planning/phases/02-local-agent/02-RESEARCH.md
@.planning/phases/02-local-agent/02-local-agent-01-SUMMARY.md
@backend/core/host_shell_service.py
@backend/core/models.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create CommandWhitelistService with decorator enforcement</name>
  <files>backend/core/command_whitelist.py</files>
  <action>
Create CommandWhitelistService with:

1. CommandCategory enum:
```python
class CommandCategory(str, Enum):
    FILE_READ = "file_read"        # ls, cat, grep, head, tail, find, wc, pwd
    FILE_WRITE = "file_write"      # cp, mv, mkdir, touch
    FILE_DELETE = "file_delete"    # rm (AUTONOMOUS only)
    BUILD_TOOLS = "build_tools"    # make, npm, pip, python3, node
    DEV_OPS = "dev_ops"            # git, docker, kubectl, terraform
    NETWORK = "network"            # curl, wget, ping (read-only)
    BLOCKED = "blocked"            # chmod, chown, kill, sudo, etc.
```

2. COMMAND_WHITELIST dict by category and maturity:
```python
COMMAND_WHITELIST = {
    CommandCategory.FILE_READ: {
        "commands": ["ls", "pwd", "cat", "head", "tail", "grep", "find", "wc"],
        "maturity_levels": [AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]
    },
    CommandCategory.FILE_WRITE: {
        "commands": ["cp", "mv", "mkdir", "touch"],
        "maturity_levels": [AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]
    },
    CommandCategory.FILE_DELETE: {
        "commands": ["rm"],
        "maturity_levels": [AgentStatus.AUTONOMOUS]  # AUTONOMOUS only
    },
    CommandCategory.BLOCKED: {
        "commands": ["chmod", "chown", "kill", "killall", "pkill", "sudo", "su", "reboot", "shutdown"],
        "maturity_levels": []  # No agent can execute
    },
    # ... additional categories
}
```

3. @whitelisted_command decorator:
```python
def whitelisted_command(category: CommandCategory, maturity_levels: List[AgentStatus]):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract command and agent_id from kwargs
            command = kwargs.get("command", "")
            agent_id = kwargs.get("agent_id", "")

            # Parse base command
            base_command = command.split()[0] if command else ""

            # Check if command is in category whitelist
            category_config = COMMAND_WHITELIST[category]
            if base_command not in category_config["commands"]:
                raise PermissionError(f"Command '{base_command}' not in {category.value} whitelist")

            # Check maturity level
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            if agent.status not in maturity_levels:
                raise PermissionError(f"Agent maturity {agent.status} not permitted for {category.value}")

            # All checks passed - execute
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

4. validate_command() function:
```python
def validate_command(command: str, maturity_level: AgentStatus) -> Dict[str, Any]:
    """Validate command against whitelist without executing."""
    # Returns: {valid: bool, category: str, maturity_required: str, reason: str}
```

DO NOT use shell=True in subprocess (command injection risk).
DO NOT allow blocked commands for any maturity level.
  </action>
  <verify>
grep -q "CommandCategory" backend/core/command_whitelist.py && grep -q "@whitelisted_command" backend/core/command_whitelist.py && grep -q "COMMAND_WHITELIST" backend/core/command_whitelist.py
  </verify>
  <done>
CommandWhitelistService created with:
- CommandCategory enum (7 categories)
- COMMAND_WHITELIST dict with maturity mappings
- @whitelisted_command decorator
- validate_command() function
- Blocked commands for all maturity levels
  </done>
</task>

<task type="auto">
  <name>Task 2: Update HostShellService for all maturity levels</name>
  <files>backend/core/host_shell_service.py</files>
  <action>
Update HostShellService to support all maturity levels (currently AUTONOMOUS-only):

1. Remove AUTONOMOUS-only check in execute_shell_command():
```python
# OLD (delete):
if maturity_level != "AUTONOMOUS":
    raise PermissionError(...)

# NEW (replace with):
# Maturity check handled by @whitelisted_command decorator
```

2. Add @whitelisted_command decorator to execute_shell_command():
```python
from core.command_whitelist import whitelisted_command, CommandCategory

@whitelisted_command(
    category=CommandCategory.FILE_READ,  # Dynamically determined by command
    maturity_levels=[AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]
)
async def execute_shell_command(...):
```

3. Create separate methods for each category:
- execute_read_command() - FILE_READ category (all maturity levels)
- execute_write_command() - FILE_WRITE category (SUPERVISED+, approval)
- execute_delete_command() - FILE_DELETE category (AUTONOMOUS only)

4. Update execute_shell_command() to route to appropriate method:
```python
async def execute_shell_command(self, agent_id, user_id, command, working_directory, timeout, db):
    # Determine category from command
    base_command = command.split()[0]
    category = self._get_command_category(base_command)

    # Route to appropriate method
    if category == CommandCategory.FILE_READ:
        return await self.execute_read_command(...)
    elif category == CommandCategory.FILE_WRITE:
        return await self.execute_write_command(...)
    elif category == CommandCategory.FILE_DELETE:
        return await self.execute_delete_command(...)
    else:
        raise PermissionError(f"Command category {category} not allowed")
```

5. Fix security issue: Change asyncio.create_subprocess_shell to asyncio.create_subprocess_exec:
```python
# OLD (delete):
process = await asyncio.create_subprocess_shell(command, ...)

# NEW (replace with):
process = await asyncio.create_subprocess_exec(
    *command.split(),  # List args prevent injection
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=working_directory
)
```

DO NOT use shell=True in subprocess (command injection risk).
DO NOT allow STUDENT/INTERN agents to execute write/delete commands without approval.
  </action>
  <verify>
grep -q "create_subprocess_exec" backend/core/host_shell_service.py && ! grep -q "create_subprocess_shell" backend/core/host_shell_service.py && grep -q "execute_read_command\|execute_write_command\|execute_delete_command" backend/core/host_shell_service.py
  </verify>
  <done>
HostShellService updated with:
- All maturity levels supported (not just AUTONOMOUS)
- Separate methods for read/write/delete commands
- asyncio.create_subprocess_exec (NOT shell=True)
- @whitelisted_command decorator
- Category-based command routing
  </done>
</task>

<task type="auto">
  <name>Task 3: Integrate whitelist validation into LocalAgentService</name>
  <files>backend/core/local_agent_service.py</files>
  <action>
Update LocalAgentService to use whitelist validation:

1. Import CommandWhitelistService:
```python
from core.command_whitelist import validate_command, CommandCategory
```

2. Add validation before execution:
```python
async def execute_command(self, agent_id, command, working_directory, db):
    # Step 1: Validate command against whitelist
    validation = validate_command(command, maturity_level)
    if not validation["valid"]:
        return {
            "allowed": False,
            "reason": validation["reason"],
            "blocked": True,
            "suggested_command": command
        }

    # Step 2: Check directory permission
    dir_check = await check_directory_permission(...)
    if not dir_check["allowed"]:
        return {"allowed": False, "reason": dir_check["reason"]}

    # Step 3: Execute via HostShellService
    result = await host_shell_service.execute_shell_command(...)

    return result
```

3. Add suggest-only handling for lower maturity:
- If validation["maturity_required"] > current maturity: return requires_approval
- Include suggested_command in response for UI display

4. Log all validation attempts (including blocked):
```python
# Create ShellSession even for blocked commands (audit trail)
session = ShellSession(
    agent_id=agent_id,
    command=command,
    command_whitelist_valid=validation["valid"],
    blocked_reason=validation.get("reason"),
    maturity_level=maturity_level,
    ...
)
```

DO NOT bypass whitelist for any maturity level.
DO NOT execute blocked commands (chmod, chown, kill, sudo, etc.).
  </action>
  <verify>
grep -q "validate_command" backend/core/local_agent_service.py && grep -q "command_whitelist_valid" backend/core/local_agent_service.py && grep -q "requires_approval" backend/core/local_agent_service.py
  </verify>
  <done>
LocalAgentService updated with:
- Whitelist validation before execution
- Suggest-only flow for lower maturity
- Blocked command logging to audit trail
- Integration with HostShellService routing
- Returns requires_approval flag for UI
  </done>
</task>

</tasks>

<verification>
1. STUDENT agent can execute read commands (ls, cat, grep) in /tmp/
2. STUDENT agent blocked from write commands (cp, mv, mkdir) - returns requires_approval
3. STUDENT agent blocked from delete commands (rm) - blocked=True
4. AUTONOMOUS agent can execute read/write commands in ~/Documents/
5. Blocked commands (sudo, chmod, kill) blocked for all maturity levels
6. Subprocess uses shell=False (create_subprocess_exec)
</verification>

<success_criteria>
1. Commands validated against maturity-based whitelist before execution
2. Read commands available to all maturity levels (STUDENT can suggest)
3. Write commands require SUPERVISED+ maturity with approval
4. Delete commands restricted to AUTONOMOUS only
5. Blocked commands blocked for all agents
6. Command injection protection (shell=False, list args)
7. All validation attempts logged to ShellSession
</success_criteria>

<output>
After completion, create `.planning/phases/02-local-agent/02-local-agent-03-SUMMARY.md` with:
- Command whitelist by category and maturity level
- Decorator implementation details
- Subprocess security pattern (shell=False)
- HostShellService routing logic
  </output>
