# Atom CLI Skills Guide

**Component**: Atom CLI as OpenClaw Skills
**Files**: `backend/tools/atom_cli_skill_wrapper.py`, `backend/skills/atom-cli/`
**Status**: ✅ Production Ready

## Overview

Atom CLI Skills are built-in OpenClaw skills that provide command-line access to Atom's daemon mode and system control functions. These skills enable agents to manage the Atom service, check status, and execute commands through a governed, subprocess-based execution model.

## Built-in Skills

| Skill | Maturity | Description | Purpose |
|-------|----------|-------------|---------|
| `atom-daemon` | AUTONOMOUS | Daemon control | Start/stop background service |
| `atom-status` | STUDENT | Read-only status | Check system status |
| `atom-start` | AUTONOMOUS | Service startup | Start Atom service |
| `atom-stop` | AUTONOMOUS | Service shutdown | Stop Atom service |
| `atom-execute` | AUTONOMOUS | Command execution | Run arbitrary commands |
| `atom-config` | INTERN | Configuration | Manage settings |

## Architecture

### Core Components

1. **CLI Skill Wrapper** (`backend/tools/atom_cli_skill_wrapper.py`)
   - Subprocess wrapper with 30s timeout
   - Structured output parsing
   - Error handling and logging
   - Security controls

2. **Skill Definitions** (`backend/skills/atom-cli/`)
   - 6 SKILL.md files defining each skill
   - Governance maturity levels
   - Usage documentation
   - Parameter specifications

3. **CLI Implementation** (`backend/cli/`)
   - `daemon.py` - Daemon mode implementation
   - `main.py` - CLI entry point

## Skill Definitions

### atom-daemon

**Maturity**: AUTONOMOUS
**Purpose**: Control the Atom background daemon

```yaml
name: atom-daemon
description: Control Atom background daemon service
maturity: AUTONOMOUS
parameters:
  action:
    type: string
    enum: [start, stop, restart, status]
    required: true
examples:
  - atom-daemon start
  - atom-daemon stop
  - atom-daemon status
```

### atom-status

**Maturity**: STUDENT
**Purpose**: Check system status (read-only)

```yaml
name: atom-status
description: Check Atom system status and health
maturity: STUDENT
parameters: {}
examples:
  - atom-status
output:
  service: running/stopped
  uptime: seconds
  memory: MB
  agents: count
```

### atom-start

**Maturity**: AUTONOMOUS
**Purpose**: Start Atom service

```yaml
name: atom-start
description: Start Atom service
maturity: AUTONOMOUS
parameters:
  mode:
    type: string
    enum: [foreground, background]
    default: background
examples:
  - atom-start
  - atom-start --mode foreground
```

### atom-stop

**Maturity**: AUTONOMOUS
**Purpose**: Stop Atom service

```yaml
name: atom-stop
description: Stop Atom service gracefully
maturity: AUTONOMOUS
parameters:
  force:
    type: boolean
    default: false
examples:
  - atom-stop
  - atom-stop --force
```

### atom-execute

**Maturity**: AUTONOMOUS
**Purpose**: Execute commands in Atom context

```yaml
name: atom-execute
description: Execute command within Atom context
maturity: AUTONOMOUS
parameters:
  command:
    type: string
    required: true
  timeout:
    type: integer
    default: 30
    unit: seconds
examples:
  - atom-execute "python script.py"
  - atom-execute "ls -la" --timeout 10
```

### atom-config

**Maturity**: INTERN
**Purpose**: Manage Atom configuration

```yaml
name: atom-config
description: Get or set Atom configuration
maturity: INTERN
parameters:
  key:
    type: string
    required: false
  value:
    type: string
    required: false
examples:
  - atom-config
  - atom-config log.level INFO
  - atom-config get log.level
```

## Usage Examples

### Python API

```python
from tools.atom_cli_skill_wrapper import AtomCliSkillWrapper

wrapper = AtomCliSkillWrapper()

# Execute daemon status
result = wrapper.execute_skill(
    skill_name="atom-status",
    parameters={}
)

print(result)
# {
#     "success": true,
#     "output": {
#         "service": "running",
#         "uptime": 3600,
#         "memory": 512
#     }
# }

# Start daemon
result = wrapper.execute_skill(
    skill_name="atom-daemon",
    parameters={"action": "start"}
)

# Execute command
result = wrapper.execute_skill(
    skill_name="atom-execute",
    parameters={
        "command": "python --version",
        "timeout": 10
    }
)
```

### Agent Execution

```python
from core.agent_governance_service import AgentGovernanceService

governance = AgentGovernanceService()

# Check if agent can use skill
can_execute = governance.check_skill_permission(
    agent_id="agent-123",
    skill_name="atom-daemon",
    agent_maturity="AUTONOMOUS"
)

if can_execute:
    # Agent can execute daemon control
    result = governance.execute_skill(
        agent_id="agent-123",
        skill_name="atom-daemon",
        parameters={"action": "status"}
    )
```

## Governance Integration

### Maturity-Based Access

| Agent Level | atom-status | atom-config | atom-daemon | atom-start/stop | atom-execute |
|-------------|-------------|-------------|-------------|----------------|--------------|
| **STUDENT** | ✅ Read-only | ❌ Blocked | ❌ Blocked | ❌ Blocked | ❌ Blocked |
| **INTERN** | ✅ Read-only | ✅ Get only | ❌ Blocked | ❌ Blocked | ❌ Blocked |
| **SUPERVISED** | ✅ Read-only | ✅ Get/Set | ❌ Blocked | ❌ Blocked | ❌ Blocked |
| **AUTONOMOUS** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |

### Permission Checks

```python
from core.governance_cache import GovernanceCache

cache = GovernanceCache()

# Check skill permission
permission = cache.check_skill_permission(
    agent_id="agent-123",
    skill_name="atom-daemon",
    agent_maturity="AUTONOMOUS"
)

# Returns: True/False with <1ms lookup
```

## Subprocess Wrapper

### Security Features

1. **Timeout Protection**
   - 30-second default timeout
   - Configurable per command
   - Automatic termination on timeout

2. **Command Whitelist** (Optional)
   - Restrict executable commands
   - Pattern-based matching
   - AUTONOMOUS agents only

3. **Output Sanitization**
   - Remove secrets from output
   - Truncate excessive output
   - Structured error messages

### Error Handling

```python
# Timeout error
{
    "success": false,
    "error": "Command timeout after 30s",
    "command": "python long_running.py",
    "timeout": 30
}

# Permission denied
{
    "success": false,
    "error": "Insufficient maturity for atom-daemon",
    "required_maturity": "AUTONOMOUS",
    "agent_maturity": "INTERN"
}

# Command not found
{
    "success": false,
    "error": "Command not found: invalid-command",
    "exit_code": 127
}
```

## Performance

| Metric | Target | Actual |
|--------|--------|--------|
| Permission check | <1ms | ~0.5ms |
| Skill execution | <50ms | ~40ms |
| Command timeout | 30s | Configurable |
| Output parsing | <10ms | ~8ms |

## API Endpoints

### Skill Execution

```bash
# Execute CLI skill
POST /api/v1/skills/atom-cli/execute
{
  "agent_id": "agent-123",
  "skill_name": "atom-status",
  "parameters": {}
}

# Response
{
  "success": true,
  "output": {
    "service": "running",
    "uptime": 3600,
    "memory": 512
  },
  "execution_time": 0.045
}
```

### Skill List

```bash
# List available CLI skills
GET /api/v1/skills/atom-cli

# Response
{
  "skills": [
    {
      "name": "atom-daemon",
      "maturity": "AUTONOMOUS",
      "description": "Control Atom daemon"
    },
    {
      "name": "atom-status",
      "maturity": "STUDENT",
      "description": "Check system status"
    }
  ]
}
```

### Permission Check

```bash
# Check skill permission
GET /api/v1/skills/atom-cli/{skill_name}/permission?agent_id=agent-123

# Response
{
  "allowed": true,
  "maturity": "AUTONOMOUS",
  "required_maturity": "AUTONOMOUS"
}
```

## Testing

```bash
# Run CLI skill wrapper tests
pytest backend/tests/test_atom_cli_skill_wrapper.py -v

# Run daemon control tests
pytest backend/tests/test_cli_daemon.py -v

# Run permission tests
pytest backend/tests/test_cli_governance.py -v
```

## Best Practices

1. **Timeout Management**
   - Set appropriate timeouts for commands
   - Consider long-running operations
   - Monitor execution time

2. **Error Handling**
   - Always check success flag
   - Handle timeout errors gracefully
   - Log errors for debugging

3. **Security**
   - Respect maturity levels
   - Validate input parameters
   - Sanitize command output

4. **Monitoring**
   - Track command execution
   - Monitor resource usage
   - Audit daemon operations

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Verify agent maturity level
   - Check skill maturity requirements
   - Ensure proper governance setup

2. **Command Timeout**
   - Increase timeout parameter
   - Optimize long-running commands
   - Check system resources

3. **Daemon Not Starting**
   - Check port availability
   - Verify configuration
   - Review daemon logs

4. **Output Parsing Errors**
   - Validate output format
   - Check command exit codes
   - Review error messages

## Integration with Community Skills

CLI skills integrate with the broader Community Skills framework:

```python
from core.skill_adapter import SkillAdapter

adapter = SkillAdapter()

# CLI skills are automatically registered
skills = adapter.list_skills(category="cli")

# Returns:
# [
#     "atom-daemon",
#     "atom-status",
#     "atom-start",
#     "atom-stop",
#     "atom-execute",
#     "atom-config"
# ]
```

## See Also

- **CLI Wrapper**: `backend/tools/atom_cli_skill_wrapper.py`
- **Daemon**: `backend/cli/daemon.py`
- **Main CLI**: `backend/cli/main.py`
- **Skill Definitions**: `backend/skills/atom-cli/`
- **Community Skills**: `backend/core/skill_adapter.py`
- **Governance**: `backend/core/agent_governance_service.py`
