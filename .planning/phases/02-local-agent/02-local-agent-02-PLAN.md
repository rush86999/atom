---
phase: 02-local-agent
plan: 02
type: execute
wave: 2
depends_on: ["01"]
files_modified:
  - backend/core/directory_permission.py
  - backend/core/governance_cache.py
  - backend/core/local_agent_service.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Directory permissions enforced based on agent maturity level"
    - "STUDENT agents limited to /tmp/ and ~/Downloads/ (suggest only)"
    - "INTERN agents can access ~/Documents/ (requires approval)"
    - "SUPERVISED agents can access ~/Desktop/ (requires approval)"
    - "AUTONOMOUS agents auto-execute in /tmp/, ~/Downloads/, ~/Documents/"
    - "Critical directories blocked for all agents (/etc/, /root/, /sys/)"
  artifacts:
    - path: "backend/core/directory_permission.py"
      provides: "Directory-based maturity checks"
      min_lines: 120
    - path: "backend/core/governance_cache.py"
      provides: "Extended cache for directory permissions"
      contains: "get_governance_cache"
  key_links:
    - from: "backend/core/local_agent_service.py"
      to: "backend/core/directory_permission.py"
      via: "Import and function call"
      pattern: "check_directory_permission"
    - from: "backend/core/directory_permission.py"
      to: "backend/core/governance_cache.py"
      via: "Cache lookup"
      pattern: "cache.get.*directory"
---

<objective>
Implement directory-based permission system with maturity-level access controls, using GovernanceCache for sub-millisecond lookups and cross-platform path resolution with pathlib.

Purpose: Enforce "earned trust" model where agents gain directory access as they mature - STUDENT agents can only suggest commands in safe directories, while AUTONOMOUS agents can auto-execute in designated safe directories.

Output: DirectoryPermissionService (maturity-based checks), extended GovernanceCache (directory caching), updated LocalAgentService (path validation)
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/FEATURE_ROADMAP.md
@.planning/phases/02-local-agent/02-RESEARCH.md
@.planning/phases/02-local-agent/02-local-agent-01-SUMMARY.md
@backend/core/governance_cache.py
@backend/core/models.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create DirectoryPermissionService with maturity-based access</name>
  <files>backend/core/directory_permission.py</files>
  <action>
Create DirectoryPermissionService with:
- DIRECTORY_PERMISSIONS dict mapping AgentStatus → allowed_dirs + suggest_only flag
- BLOCKED_DIRECTORIES list (critical system paths)
- check_directory_permission(agent_id, directory, maturity_level, db) - Main validation
- _expand_path(directory) - Resolve ~ to home, handle cross-platform paths
- _is_blocked(directory) - Check against BLOCKED_DIRECTORIES

Directory permissions (from FEATURE_ROADMAP.md):
```python
DIRECTORY_PERMISSIONS = {
    AgentStatus.STUDENT: {
        "allowed": ["/tmp", "~/Downloads"],
        "suggest_only": True  # Can suggest, not execute
    },
    AgentStatus.INTERN: {
        "allowed": ["/tmp", "~/Downloads", "~/Documents"],
        "suggest_only": True  # Requires approval
    },
    AgentStatus.SUPERVISED: {
        "allowed": ["~/Documents", "~/Desktop"],
        "suggest_only": True  # Requires approval
    },
    AgentStatus.AUTONOMOUS: {
        "allowed": ["/tmp", "~/Downloads", "~/Documents"],
        "suggest_only": False  # Auto-execute
    }
}

BLOCKED_DIRECTORIES = [
    "/etc", "/root", "/sys", "/System",
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)"
]
```

Use pathlib.Path for cross-platform path handling:
- Path(directory).expanduser() to resolve ~
- Path(directory).resolve() to canonicalize (handle .., symlinks)
- Path.is_relative_to() for prefix checking (Python 3.12+) or str(path).startswith() for older

Cache results in GovernanceCache with key "{agent_id}:{directory}" for <1ms lookups.

Return dict with:
{
    "allowed": bool,
    "suggest_only": bool,
    "reason": str,
    "maturity_level": str,
    "resolved_path": str
}
  </action>
  <verify>
grep -q "DIRECTORY_PERMISSIONS" backend/core/directory_permission.py && grep -q "BLOCKED_DIRECTORIES" backend/core/directory_permission.py && grep -q "pathlib" backend/core/directory_permission.py
  </verify>
  <done>
DirectoryPermissionService created with:
- Maturity-based directory mappings (STUDENT → AUTONOMOUS)
- Blocked directories (system-critical paths)
- pathlib for cross-platform path resolution
- Cache integration with GovernanceCache
- Returns suggest_only flag for approval flow
  </done>
</task>

<task type="auto">
  <name>Task 2: Extend GovernanceCache for directory permission caching</name>
  <files>backend/core/governance_cache.py</files>
<action>
Add directory-specific cache methods to GovernanceCache:
- check_directory(agent_id, directory) - Wrapper for directory permission cache
- cache_key format: "{agent_id}:dir:{directory}" (avoid collision with action_type keys)

Add statistics tracking:
- _directory_hits - Increment on directory cache hit
- _directory_misses - Increment on directory cache miss

Update get_statistics() to include directory cache metrics:
```python
{
    "total_hits": self._hits,
    "total_misses": self._misses,
    "directory_hits": self._directory_hits,
    "directory_misses": self._directory_misses,
    "hit_rate": ...,
    "directory_hit_rate": ...
}
```

DO NOT change existing cache API (get/set) - maintain backward compatibility.
Use same 60-second TTL for directory cache entries.
  </action>
  <verify>
grep -q "directory_hits" backend/core/governance_cache.py && grep -q ":dir:" backend/core/governance_cache.py
  </verify>
  <done>
GovernanceCache extended with:
- Directory-specific cache key format
- Directory hit/miss statistics
- Updated get_statistics() with directory metrics
- Backward compatible (existing API unchanged)
  </done>
</task>

<task type="auto">
  <name>Task 3: Integrate directory checks into LocalAgentService</name>
  <files>backend/core/local_agent_service.py</files>
  <action>
Update LocalAgentService.execute_command():
- Import DirectoryPermissionService
- Call check_directory_permission() BEFORE subprocess execution
- If not allowed: return {"allowed": False, "reason": "...", "suggest_only": bool}
- If suggest_only=True: return {"allowed": False, "requires_approval": True, "suggested_command": "..."}
- If allowed and not suggest_only: proceed with execution

Flow:
```
execute_command():
  1. Check governance (maturity level) - EXISTING
  2. Check directory permission - NEW
  3. If suggest_only: return approval request
  4. Else: execute subprocess
  5. Log to ShellSession
```

Update _execute_locally() to validate working_directory:
- Resolve path with pathlib before execution
- Check if path is within allowed directories
- Raise PermissionError if not allowed

Add file operation logging:
- Log read operations (cat, grep, head, tail) to ShellSession with operation_type="read"
- Log write operations (mkdir, touch, etc.) with operation_type="write"
- Log blocked attempts with operation_type="blocked"
  </action>
  <verify>
grep -q "check_directory_permission" backend/core/local_agent_service.py && grep -q "suggest_only" backend/core/local_agent_service.py
  </verify>
  <done>
LocalAgentService updated with:
- Directory permission checks before execution
- Suggest-only flow for lower maturity agents
- File operation type logging (read/write/blocked)
- Path resolution with pathlib
- Integration with DirectoryPermissionService
  </done>
</task>

</tasks>

<verification>
1. STUDENT agent blocked from /etc/ (returns allowed=False)
2. STUDENT agent can suggest commands in /tmp/ (suggest_only=True)
3. AUTONOMOUS agent can auto-execute in ~/Documents/ (suggest_only=False)
4. Path traversal blocked: "../../../etc/passwd" resolves to blocked directory
5. Cache statistics show directory hits/misses
</verification>

<success_criteria>
1. Directory permissions enforced by maturity level (4 levels)
2. Cross-platform path resolution (~/Documents works on macOS/Linux/Windows)
3. Critical directories blocked for all agents
4. Suggest-only flow enables user approval for STUDENT/INTERN/SUPERVISED
5. GovernanceCache provides <1ms directory lookups
</success_criteria>

<output>
After completion, create `.planning/phases/02-local-agent/02-local-agent-02-SUMMARY.md` with:
- Directory permission rules matrix
- Cache performance metrics
- Path resolution examples (cross-platform)
- Integration with LocalAgentService
</output>
