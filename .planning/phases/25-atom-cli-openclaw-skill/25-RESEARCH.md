# Phase 25: Atom CLI as OpenClaw Skill - Research

**Researched:** 2026-02-18
**Domain:** CLI command wrapping, OpenClaw skill format, community skills integration, agent governance
**Confidence:** HIGH

## Summary

Phase 25 converts Atom's CLI commands (`daemon`, `status`, `execute`, `start`, `stop`, `config`) into OpenClaw-compatible skills, enabling cross-platform agent usage through Atom's existing Community Skills framework (Phase 14). The implementation leverages existing infrastructure: SkillParser for YAML frontmatter parsing, SkillRegistryService for skill lifecycle management, and CommunitySkillTool for LangChain BaseTool wrapping. Each CLI command becomes a separate skill with appropriate maturity gates (AUTONOMOUS for daemon control) and governance integration.

**Primary recommendation:** Create 6 SKILL.md files (one per CLI command) in a new `backend/skills/atom-cli/` directory, import them via the existing `/api/skills/import` endpoint, and use prompt-only skills (not Python) to invoke CLI commands through subprocess execution with proper error handling and governance validation.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **python-frontmatter** | 1.0+ | Parse YAML frontmatter from SKILL.md files | Already used in Phase 14, handles `---` delimiters and metadata extraction |
| **subprocess** | stdlib | Execute Atom CLI commands from skill wrapper | Standard Python approach for running external commands with error handling |
| **LangChain** | 0.1+ | BaseTool class for skill wrapping | Already integrated in Phase 14, provides LLM tool interface |
| **Pydantic** | 2.0+ | Validate skill inputs | Required for LangChain BaseTool args_schema, already in stack |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **click** | 8.0+ | Atom CLI is built with Click | Understanding CLI command structure for skill wrapper design |
| **psutil** | 6.0+ | Process management for daemon commands | Optional: Already used in `cli/daemon.py` for PID tracking |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Prompt-only skills | Python code skills | Prompt skills are simpler and safer for CLI commands; Python skills would require sandbox execution which adds complexity |
| Separate SKILL.md per command | Single multi-command skill | Separate skills enable fine-grained governance (e.g., AUTONOMOUS for daemon, INTERN for status) vs. all-or-nothing permissions |
| subprocess execution | Direct Python imports | subprocess keeps skills decoupled from Atom internals, enabling cross-platform usage vs. tight coupling |

**Installation:**
```bash
# No new dependencies required - all libraries already in Phase 14 stack
pip install pydantic==2.0 langchain python-frontmatter click
```

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── skills/
│   └── atom-cli/                 # NEW: OpenClaw skill definitions
│       ├── atom-daemon.md        # daemon command skill
│       ├── atom-status.md        # status command skill
│       ├── atom-start.md         # start command skill
│       ├── atom-stop.md          # stop command skill
│       ├── atom-execute.md       # execute command skill
│       └── atom-config.md        # config command skill
├── tools/
│   └── atom_cli_skill_wrapper.py # NEW: Subprocess execution wrapper
├── tests/
│   └── test_atom_cli_skills.py   # NEW: Test CLI skill execution
└── docs/
    └── ATOM_CLI_SKILLS_GUIDE.md  # NEW: User documentation
```

### Pattern 1: Prompt-Only CLI Skill

**What:** SKILL.md file with YAML frontmatter and prompt body that executes CLI command via subprocess

**When to use:** All 6 Atom CLI commands (daemon, status, start, stop, execute, config)

**Example:**
```markdown
---
name: atom-daemon
description: Start Atom OS as background daemon service with PID tracking
version: 1.0.0
author: Atom Team
tags: [atom, cli, daemon, service-management]
maturity_level: AUTONOMOUS
governance:
  maturity_requirement: AUTONOMOUS
  reason: "Daemon control manages background services, requires full autonomy"
---

# Atom Daemon Manager

Start Atom OS as a background daemon service with PID file tracking.

## Usage

Execute this skill to start the Atom daemon:
```
atom-os daemon [options]
```

## Options

- `--port <number>`: Port for web server (default: 8000)
- `--host <address>`: Host to bind to (default: 0.0.0.0)
- `--workers <count>`: Number of worker processes (default: 1)
- `--host-mount`: Enable host filesystem mount (requires confirmation)
- `--dev`: Enable development mode with auto-reload
- `--foreground`: Run in foreground (not daemon mode)

## Examples

Start daemon on default port:
```
atom-os daemon
```

Start daemon on custom port with development mode:
```
atom-os daemon --port 3000 --dev
```

Start daemon with host mount (requires AUTONOMOUS maturity):
```
atom-os daemon --host-mount
```

## Output

Returns daemon process ID and status information.

## Notes

⚠️ **AUTONOMOUS maturity required** - This command manages background services.
```
**Source:** Based on `backend/cli/main.py` CLI command structure and Phase 14 SKILL.md format
```

### Pattern 2: Subprocess Execution Wrapper

**What:** Python wrapper that executes Atom CLI commands via subprocess with error handling

**When to use:** CommunitySkillTool needs to invoke CLI commands from prompt skills

**Example:**
```python
# Source: subprocess documentation + Phase 14 skill_adapter.py pattern
import subprocess
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def execute_atom_cli_command(command: str, args: list = None) -> Dict[str, Any]:
    """
    Execute Atom CLI command via subprocess.

    Args:
        command: CLI command (e.g., "daemon", "status", "stop")
        args: Command arguments (e.g., ["--port", "3000"])

    Returns:
        Dict with:
            - success: bool
            - stdout: str
            - stderr: str
            - returncode: int
    """
    try:
        # Build command
        cmd = ["atom-os", command]
        if args:
            cmd.extend(args)

        # Execute command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        logger.error(f"Command '{command}' timed out after 30 seconds")
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out",
            "returncode": -1
        }
    except Exception as e:
        logger.error(f"Failed to execute command '{command}': {e}")
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }
```

### Pattern 3: Maturity-Based Governance

**What:** Assign maturity requirements based on command risk level

**When to use:** All CLI skills (per Phase 02 Local Agent governance pattern)

**Example:**
```yaml
# atom-daemon.md - AUTONOMOUS required
governance:
  maturity_requirement: AUTONOMOUS
  reason: "Daemon control manages background services"

# atom-status.md - All maturity levels
governance:
  maturity_requirement: STUDENT
  reason: "Read-only status check"

# atom-stop.md - AUTONOMOUS required
governance:
  maturity_requirement: AUTONOMOUS
  reason: "Stopping daemon terminates service"
```

**Source:** Phase 02 Local Agent implementation + Phase 14 Community Skills governance integration

### Anti-Patterns to Avoid

- **Python code skills for CLI commands**: Unnecessary complexity, prompt skills with subprocess wrapper are sufficient
- **Single multi-command skill**: Prevents fine-grained governance (all-or-nothing permissions vs. per-command maturity gates)
- **Direct Python imports**: Tightly couples skills to Atom internals vs. subprocess decoupling enables cross-platform usage
- **Missing maturity requirements**: Security risk - daemon commands should require AUTONOMOUS vs. unrestricted access

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Skill parsing | Custom YAML parser | SkillParser (Phase 14) | Handles lenient parsing, auto-fix, version-agnostic frontmatter |
| Skill lifecycle | Custom import/execute logic | SkillRegistryService (Phase 14) | Provides import workflow, security scanning, episodic memory integration |
| Tool wrapping | Direct function calls | CommunitySkillTool (Phase 14) | LangChain BaseTool integration with Pydantic validation |
| Governance checks | Custom permission logic | AgentGovernanceService (existing) | <1ms cached checks, 4-tier maturity validation |

**Key insight:** Phase 14's Community Skills framework already provides all infrastructure needed. This phase is about creating SKILL.md files and ensuring proper CLI command invocation through subprocess.

## Common Pitfalls

### Pitfall 1: Ignoring Maturity Requirements

**What goes wrong:** STUDENT or INTERN agents can start/stop daemons, causing service disruption

**Why it happens:** SKILL.md files missing `governance.maturity_requirement` field

**How to avoid:** Always specify maturity requirement in YAML frontmatter:
```yaml
governance:
  maturity_requirement: AUTONOMOUS  # for daemon/start/stop
  maturity_requirement: STUDENT     # for status/config
```

**Warning signs:** Skills import successfully but execute without governance checks

### Pitfall 2: Subprocess Command Not Found

**What goes wrong:** Skill execution fails with "command not found: atom-os"

**Why it happens:** Atom CLI not installed in system PATH or using wrong command name

**How to avoid:**
1. Verify Atom CLI installation: `which atom-os`
2. Use full path to CLI if needed: `/usr/local/bin/atom-os`
3. Document CLI installation prerequisite in user guide

**Warning signs:** subprocess returncode = 127 (command not found)

### Pitfall 3: Missing Command Arguments

**What goes wrong:** Skills execute commands but don't pass user-specified flags (e.g., `--port 3000`)

**Why it happens:** Prompt skills don't extract arguments from user query

**How to avoid:** Document expected argument format in skill body, use structured inputs:
```markdown
## Arguments

Specify port in your request: "Start daemon on port 3000"
Specify host mount: "Start daemon with host mount enabled"
```

**Warning signs:** Commands always use default values

### Pitfall 4: Daemon Start Race Conditions

**What goes wrong:** Skill reports success but daemon not actually running yet

**Why it happens:** subprocess returns immediately but daemon takes time to initialize

**How to avoid:** Add polling loop in skill wrapper to verify daemon status:
```python
# Wait for daemon to be ready
for _ in range(10):
    if DaemonManager.is_running():
        break
    time.sleep(0.5)
```

**Warning signs:** `atom-os status` reports "not running" immediately after start

### Pitfall 5: Permission Errors on PID Files

**What goes wrong:** Daemon fails to start due to `.atom/pids/` directory permissions

**Why it happens:** Running Atom as different user than who created directories

**How to avoid:** Document directory setup, ensure proper ownership:
```bash
mkdir -p ~/.atom/pids ~/.atom/logs
chmod 755 ~/.atom/pids ~/.atom/logs
```

**Warning signs:** IOError in daemon logs, permission denied errors

## Code Examples

Verified patterns from existing Atom codebase:

### Example 1: Daemon Status Check (from cli/daemon.py)

```python
# Source: /Users/rushiparikh/projects/atom/backend/cli/daemon.py
@staticmethod
def is_running() -> bool:
    """Check if daemon process is running."""
    pid = DaemonManager.get_pid()
    if pid is None:
        return False

    if psutil is None:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False
```

### Example 2: YAML Frontmatter Format (from test_skill_parser.py)

```python
# Source: /Users/rushiparikh/projects/atom/backend/tests/test_skill_parser.py
content = """---
name: Test Skill
description: A test skill for parsing
version: 1.0.0
author: Test Author
---

# Test Skill

This is a test skill for parsing.

## Instructions

Use this skill to test parsing.
"""
```

### Example 3: Community Skill Import (from skill_registry_service.py)

```python
# Source: /Users/rushiparikh/projects/atom/backend/core/skill_registry_service.py
def import_skill(
    self,
    source: str,
    content: str,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Import a community skill from various sources.

    Args:
        source: Import source - "github_url", "file_upload", or "raw_content"
        content: SKILL.md content or file content
        metadata: Optional metadata (author, tags, etc.)

    Returns:
        Dict with skill_id, scan_result, status, metadata
    """
    # Parse SKILL.md using python-frontmatter
    import frontmatter
    post = frontmatter.loads(content)
    skill_metadata = post.metadata
    skill_body = post.content

    # Security scan
    scan_result = self._scanner.scan_skill(skill_name, skill_body)

    # Store in database
    skill_record = SkillExecution(...)
    self.db.add(skill_record)
    self.db.commit()

    return {...}
```

### Example 4: Skill Execution via API (from skill_routes.py)

```python
# Source: /Users/rushiparikh/projects/atom/backend/api/skill_routes.py
@router.post("/execute")
async def execute_skill(
    request: ExecuteSkillRequest,
    service: SkillRegistryService = Depends(get_skill_service)
) -> Dict[str, Any]:
    """
    Execute a community skill with governance checks.

    Example:
        POST /api/skills/execute
        {
            "skill_id": "abc-123-def",
            "inputs": {"query": "Start daemon on port 3000"},
            "agent_id": "agent-456"
        }
    """
    result = service.execute_skill(
        skill_id=request.skill_id,
        inputs=request.inputs,
        agent_id=request.agent_id
    )
    return result
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual CLI invocation | Skill-based CLI execution | Phase 25 (proposed) | Agents can control Atom via skills |
| Separate CLI tools | Unified Community Skills framework | Phase 14 (Feb 2026) | Single import/execute workflow for all skills |
| No governance for CLI | Maturity-based CLI permissions | Phase 25 (proposed) | AUTONOMOUS gate for daemon commands |
| Shell-only access | Cross-platform agent access | Phase 25 (proposed) | Any agent (OpenClaw, Claude) can use Atom CLI |

**Deprecated/outdated:**
- Direct shell script execution: Use skill-based execution with governance instead
- Manual daemon management: Use `atom-daemon` skill with AUTONOMOUS maturity
- Unrestricted CLI access: Apply maturity gates (STUDENT for status, AUTONOMOUS for daemon control)

## Open Questions

1. **CLI installation prerequisite**
   - What we know: Skills execute `atom-os` command via subprocess
   - What's unclear: How to ensure Atom CLI is installed and in PATH before skill import
   - Recommendation: Document CLI installation in user guide, add skill import validation to check `which atom-os`

2. **Command argument parsing**
   - What we know: Prompt skills need to extract flags from user query
   - What's unclear: Best pattern for argument extraction (regex vs. LLM parsing vs. structured inputs)
   - Recommendation: Use LLM parsing via skill's prompt template, document expected format in skill body

3. **Multi-command workflows**
   - What we know: Each command is a separate skill
   - What's unclear: How to handle workflows like "start daemon, wait 5s, check status"
   - Recommendation: Out of scope for Phase 25 - defer to Phase 26 (Agent Workflows) or manual multi-step execution

## Sources

### Primary (HIGH confidence)

- `/Users/rushiparikh/projects/atom/backend/cli/daemon.py` - DaemonManager implementation, status checking, PID tracking
- `/Users/rushiparikh/projects/atom/backend/cli/main.py` - Click-based CLI structure, all 6 command implementations
- `/Users/rushiparikh/projects/atom/backend/core/skill_parser.py` - Lenient YAML frontmatter parsing, auto-fix logic
- `/Users/rushiparikh/projects/atom/backend/core/skill_adapter.py` - LangChain BaseTool wrapping pattern
- `/Users/rushiparikh/projects/atom/backend/core/skill_registry_service.py` - Skill import, security scanning, execution workflow
- `/Users/rushiparikh/projects/atom/backend/api/skill_routes.py` - REST API endpoints for skill management
- `/Users/rushiparikh/projects/atom/backend/tests/test_skill_parser.py` - SKILL.md format examples, test fixtures
- `/Users/rushiparikh/projects/atom/docs/PERSONAL_EDITION.md` - CLI usage examples, daemon commands
- `/Users/rushiparikh/projects/atom/docs/COMMUNITY_SKILLS.md` - Community Skills framework documentation
- `/Users/rushiparikh/projects/atom/.planning/phases/14-community-skills-integration/14-RESEARCH.md` - Phase 14 research, skill format standards

### Secondary (MEDIUM confidence)

- `/Users/rushiparikh/projects/atom/docs/ATOM_VS_OPENCLAW.md` - OpenClaw comparison, skill ecosystem context
- Click documentation (https://click.palletsprojects.com/) - CLI command structure verification
- subprocess documentation (https://docs.python.org/3/library/subprocess.html) - Command execution patterns

### Tertiary (LOW confidence)

- OpenClaw AgentSkills repository structure (referenced in docs but not directly accessed) - Assuming compatible SKILL.md format based on Phase 14 lenient parsing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in Phase 14 stack, no new dependencies
- Architecture: HIGH - Leveraging existing Phase 14 infrastructure, clear pattern from test files
- Pitfalls: MEDIUM - subprocess execution has known issues (permissions, race conditions) but documented workarounds exist

**Research date:** 2026-02-18
**Valid until:** 2026-04-18 (60 days - stable domain, CLI commands unlikely to change)
