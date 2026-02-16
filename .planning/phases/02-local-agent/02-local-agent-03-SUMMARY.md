---
phase: 02-local-agent
plan: 03
subsystem: [security, shell-execution, governance]
tags: [command-whitelist, maturity-levels, subprocess-security, decorator-pattern, audit-trail]

# Dependency graph
requires:
  - phase: 02-local-agent
    plan: 01
    provides: LocalAgentService, directory_permission, HostShellService
provides:
  - CommandWhitelistService with decorator-based enforcement
  - Maturity-based command categorization (read/write/delete/blocked)
  - HostShellService category-based routing for all maturity levels
  - LocalAgentService whitelist integration with approval flow
affects: [02-local-agent-04, 02-local-agent-05]

# Tech tracking
tech-stack:
  added: [command_whitelist.py, decorator pattern, asyncio.create_subprocess_exec]
  patterns: [decorator-based validation, category-based command routing, shell=False subprocess execution]

key-files:
  created:
    - backend/core/command_whitelist.py
  modified:
    - backend/core/host_shell_service.py
    - backend/core/local_agent_service.py

key-decisions:
  - "Decorator-based whitelist enforcement instead of config-driven (compile-time safety, self-documenting)"
  - "Subprocess shell=False with list args (prevents command injection)"
  - "Category-based command routing (read/write/delete/build/dev_ops/network)"
  - "All maturity levels supported (not just AUTONOMOUS)"
  - "Blocked commands for all maturity levels (chmod, chown, kill, sudo, etc.)"

patterns-established:
  - "Decorator Pattern: @whitelisted_command for runtime validation"
  - "Security Pattern: shell=False + list args for subprocess execution"
  - "Governance Pattern: maturity level checks at decorator layer"
  - "Audit Pattern: command_whitelist_valid field in all ShellSession logs"

# Metrics
duration: 4min
completed: 2026-02-16
---

# Phase 02: Local Agent - Plan 03 Summary

**Decorator-based command whitelist with maturity-level restrictions, category-based routing (read/write/delete/blocked), and subprocess shell=False security pattern for all agent maturity levels**

## Performance

- **Duration:** 4 minutes
- **Started:** 2026-02-16T21:31:23Z
- **Completed:** 2026-02-16T21:35:23Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Created CommandWhitelistService with decorator-based enforcement and 7 command categories
- Updated HostShellService to support all maturity levels (not just AUTONOMOUS) with category-based routing
- Integrated whitelist validation into LocalAgentService with approval flow for lower maturity levels
- Fixed critical security issue: Changed from `create_subprocess_shell` to `create_subprocess_exec` (shell=False)
- Implemented maturity-based command restrictions:
  - STUDENT: Read commands only (ls, cat, grep, etc.)
  - INTERN: Read commands (requires approval)
  - SUPERVISED: Write commands (cp, mv, mkdir) with approval
  - AUTONOMOUS: All whitelisted commands except blocked

## Task Commits

Each task was committed atomically:

1. **Task 1: Create CommandWhitelistService with decorator enforcement** - `b5357ce2` (feat)
2. **Task 2: Update HostShellService for all maturity levels** - `2291feb2` (feat)
3. **Task 3: Integrate whitelist validation into LocalAgentService** - `6aa2b8b0` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified

### Created
- `backend/core/command_whitelist.py` (337 lines)
  - CommandCategory enum (7 categories: file_read, file_write, file_delete, build_tools, dev_ops, network, blocked)
  - COMMAND_WHITELIST dict with maturity mappings
  - @whitelisted_command decorator for runtime validation
  - validate_command() function for static validation
  - get_command_category() for category lookup
  - get_allowed_commands() for maturity-level filtering

### Modified
- `backend/core/host_shell_service.py`
  - Removed AUTONOMOUS-only restriction
  - Added category-based command routing (6 separate methods)
  - execute_read_command() - FILE_READ (all maturity levels)
  - execute_write_command() - FILE_WRITE (SUPERVISED+)
  - execute_delete_command() - FILE_DELETE (AUTONOMOUS only)
  - execute_build_command() - BUILD_TOOLS (SUPERVISED+)
  - execute_devops_command() - DEV_OPS (SUPERVISED+)
  - execute_network_command() - NETWORK (all maturity levels)
  - Fixed security: Changed `create_subprocess_shell` to `create_subprocess_exec` (shell=False)
  - Removed old COMMAND_WHITELIST and BLOCKED_COMMANDS (now in command_whitelist.py)

- `backend/core/local_agent_service.py`
  - Added command_whitelist import (validate_command, get_command_category)
  - Integrated whitelist validation after governance check
  - Returns requires_approval flag for commands needing higher maturity
  - Returns maturity_required for UI display
  - Returns category for UI display
  - Logs all validation attempts (including blocked) with command_whitelist_valid field
  - Blocked command attempts logged with blocked_reason
  - Suggest-only flow logs with requires_approval flag

## Command Whitelist by Category and Maturity Level

### FILE_READ (all maturity levels)
- Commands: `ls`, `pwd`, `cat`, `head`, `tail`, `grep`, `find`, `wc`
- STUDENT: Can suggest (requires approval)
- INTERN: Can suggest (requires approval)
- SUPERVISED: Can execute (with supervision)
- AUTONOMOUS: Can execute (no supervision)

### FILE_WRITE (SUPERVISED+)
- Commands: `cp`, `mv`, `mkdir`, `touch`
- STUDENT/INTERN: Blocked (requires higher maturity)
- SUPERVISED: Can execute (with approval)
- AUTONOMOUS: Can execute (no supervision)

### FILE_DELETE (AUTONOMOUS only)
- Commands: `rm`
- STUDENT/INTERN/SUPERVISED: Blocked (AUTONOMOUS required)
- AUTONOMOUS: Can execute (no supervision)

### BUILD_TOOLS (SUPERVISED+)
- Commands: `make`, `npm`, `pip`, `python3`, `node`, `yarn`, `cargo`
- STUDENT/INTERN: Blocked (requires higher maturity)
- SUPERVISED: Can execute (with approval)
- AUTONOMOUS: Can execute (no supervision)

### DEV_OPS (SUPERVISED+)
- Commands: `git`, `docker`, `kubectl`, `terraform`, `ansible`
- STUDENT/INTERN: Blocked (requires higher maturity)
- SUPERVISED: Can execute (with approval)
- AUTONOMOUS: Can execute (no supervision)

### NETWORK (all maturity levels)
- Commands: `curl`, `wget`, `ping`, `nslookup`, `dig`, `netstat`
- STUDENT: Can suggest (requires approval)
- INTERN: Can suggest (requires approval)
- SUPERVISED: Can execute (with supervision)
- AUTONOMOUS: Can execute (no supervision)

### BLOCKED (all maturity levels)
- Commands: `chmod`, `chown`, `kill`, `killall`, `pkill`, `sudo`, `su`, `reboot`, `shutdown`, `halt`, `iptables`, `ufw`, `firewall-cmd`, `usermod`, `userdel`, `dd`, `mkfs`, `fdisk`, `mount`, `umount`
- ALL MATURITY LEVELS: Blocked (cannot be executed by agents)

## Decorator Implementation Details

The @whitelisted_command decorator enforces security at function entry:

```python
@whitelisted_command(
    category=CommandCategory.FILE_READ,
    maturity_levels=["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
)
async def execute_read_command(
    agent_id: str,
    command: str,
    working_directory: str,
    db: Session
):
    # Decorator validates:
    # 1. Command is in FILE_READ whitelist
    # 2. Agent maturity level is allowed
    # 3. Agent exists in database
    # 4. Command not in blocked category
    # If all checks pass, execution proceeds
    process = await asyncio.create_subprocess_exec(...)
    return result
```

Decorator raises PermissionError if:
- Command not in category whitelist
- Agent maturity level not permitted
- Agent not found in database
- Command in blocked category

## Subprocess Security Pattern (shell=False)

**Old (INSECURE):**
```python
process = await asyncio.create_subprocess_shell(
    command,  # String argument - VULNERABLE TO INJECTION
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=working_directory
)
```

**New (SECURE):**
```python
process = await asyncio.create_subprocess_exec(
    *command.split(),  # List arguments - PREVENTS INJECTION
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=working_directory
)
```

**Why shell=False is secure:**
- List arguments prevent shell metacharacter injection (`;`, `|`, `&`, `$()`)
- No shell interpretation of special characters
- Each argument is passed directly to exec()
- Command separator attacks impossible

## HostShellService Routing Logic

The execute_shell_command() method routes to category-specific methods:

1. Determine command category via get_command_category()
2. Route to appropriate method:
   - FILE_READ → execute_read_command()
   - FILE_WRITE → execute_write_command()
   - FILE_DELETE → execute_delete_command()
   - BUILD_TOOLS → execute_build_command()
   - DEV_OPS → execute_devops_command()
   - NETWORK → execute_network_command()
   - BLOCKED → PermissionError raised
3. Decorator validates whitelist + maturity level
4. Execute with subprocess shell=False
5. Log to ShellSession with command_whitelist_valid=True

## Decisions Made

1. **Decorator-based whitelist instead of config-driven**
   - Rationale: Compile-time enforcement, type-safe, self-documenting
   - Tradeoff: Less flexible than YAML/JSON config, but more secure

2. **Category-based command routing**
   - Rationale: Clear separation of concerns, maturity-level gating
   - Tradeoff: More methods than monolithic execute_shell_command()

3. **Subprocess shell=False with list args**
   - Rationale: Prevents command injection attacks
   - Tradeoff: Cannot use shell features (pipes, wildcards) - acceptable for security

4. **All maturity levels supported (not just AUTONOMOUS)**
   - Rationale: Enables learning progression from STUDENT → AUTONOMOUS
   - Tradeoff: More complex governance logic

5. **Blocked commands for all maturity levels**
   - Rationale: Some commands (sudo, chmod, kill) too dangerous for any agent
   - Tradeoff: Limits agent capabilities, but necessary for safety

## Deviations from Plan

None - plan executed exactly as written.

All three tasks completed according to specification:
- Task 1: CommandWhitelistService created with all required components
- Task 2: HostShellService updated with category-based routing and shell=False
- Task 3: LocalAgentService integrated with whitelist validation

## Verification Checklist

Plan success criteria validated:

- ✅ Commands validated against maturity-based whitelist before execution
- ✅ Read commands available to all maturity levels (STUDENT can suggest)
- ✅ Write commands require SUPERVISED+ maturity with approval
- ✅ Delete commands restricted to AUTONOMOUS only
- ✅ Blocked commands blocked for all agents
- ✅ Command injection protection (shell=False, list args)
- ✅ All validation attempts logged to ShellSession with command_whitelist_valid field

## Next Phase Readiness

**Ready for Phase 02 Plan 04 (Testing):**
- CommandWhitelistService fully implemented with decorator pattern
- HostShellService supports all maturity levels with category routing
- LocalAgentService integrated with whitelist validation
- Security pattern (shell=False) established
- Audit trail logging complete

**Recommended testing focus:**
- Unit tests for decorator validation logic
- Integration tests for category-based routing
- Security tests for command injection prevention
- Maturity-level enforcement tests
- Audit trail verification tests

---
*Phase: 02-local-agent*
*Plan: 03*
*Completed: 2026-02-16*
