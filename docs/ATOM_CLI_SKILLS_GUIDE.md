# Atom CLI Skills Guide

> **Last Updated:** February 18, 2026

## Table of Contents

- [What are Atom CLI Skills?](#what-are-atom-cli-skills)
- [Why Use CLI Skills?](#why-use-cli-skills)
- [Maturity Requirements](#maturity-requirements)
- [Quick Start](#quick-start)
- [Skill Reference](#skill-reference)
  - [atom-daemon - Start Background Daemon](#atom-daemon---start-background-daemon)
  - [atom-status - Check Daemon Status](#atom-status---check-daemon-status)
  - [atom-start - Start Server (Foreground)](#atom-start---start-server-foreground)
  - [atom-stop - Stop Daemon](#atom-stop---stop-daemon)
  - [atom-execute - Execute On-Demand Command](#atom-execute---execute-on-demand-command)
  - [atom-config - Show Configuration](#atom-config---show-configuration)
- [Import Workflow](#import-workflow)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

## What are Atom CLI Skills?

Atom CLI skills are OpenClaw-compatible skill definitions that enable agents to control the Atom OS CLI through the existing Community Skills framework. Each CLI command is wrapped as a skill with:

- **SKILL.md metadata**: YAML frontmatter with governance requirements
- **Structured execution**: Subprocess wrapper with timeout and error handling
- **Argument parsing**: Natural language to CLI flag conversion
- **Governance integration**: Maturity gates for safe operation

These skills bridge the gap between agent capabilities and system control, allowing agents to:
- Start/stop background daemons
- Check system status
- Execute commands on-demand
- Display configuration

### How It Works

```mermaid
graph LR
    A[Agent Query] --> B[CommunitySkillTool]
    B --> C{skill_id starts with "atom-"}
    C -->|Yes| D[_execute_cli_skill]
    C -->|No| E[Standard skill execution]
    D --> F[Subprocess Wrapper]
    F --> G[atom-os command execution]
    G --> H[Structured Response]
```

## Why Use CLI Skills?

### Agent Automation
- **Daemon Management**: Agents can start, stop, and monitor background services
- **System Control**: Execute CLI commands without direct shell access
- **Status Monitoring**: Check health and performance metrics
- **Configuration Access**: Read runtime configuration safely

### Security Benefits
- **Governance Gates**: AUTONOMOUS requirement for critical operations
- **Command Isolation**: Safe subprocess execution with timeout protection
- **Audit Trail**: All CLI actions logged to ShellSession table
- **Argument Validation**: Safe parsing of user inputs to CLI flags

### Integration Advantages
- **Existing Framework**: Leverages Phase 14 Community Skills infrastructure
- **Skill Registry**: Integrated with security scanning and governance
- **Episodic Memory**: Command executions create learning episodes
- **Cross-Platform**: Works on macOS, Linux, and Windows

## Maturity Requirements

| Skill | Maturity Level | Reason | Access Level |
|-------|----------------|--------|--------------|
| **atom-daemon** | AUTONOMOUS | Daemon control manages background services | ⚠️ Requires AUTONOMOUS |
| **atom-status** | STUDENT | Read-only status check, safe for all levels | ✅ All levels allowed |
| **atom-start** | AUTONOMOUS | Server start manages system resources | ⚠️ Requires AUTONOMOUS |
| **atom-stop** | AUTONOMOUS | Stopping daemon terminates service | ⚠️ Requires AUTONOMOUS |
| **atom-execute** | AUTONOMOUS | On-demand execution requires full autonomy | ⚠️ Requires AUTONOMOUS |
| **atom-config** | STUDENT | Read-only configuration display | ✅ All levels allowed |

### Security Model

- **STUDENT Agents**: Can only read status and configuration
- **INTERN Agents**: Inherited from STUDENT (no additional CLI access)
- **SUPERVISED Agents**: Inherited from STUDENT (no additional CLI access)
- **AUTONOMOUS Agents**: Full access to all CLI operations

This ensures only experienced agents can modify system state while all agents can monitor health.

## Quick Start

### 1. Import CLI Skills

```bash
curl -X POST http://localhost:8000/api/skills/import \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_files": [
      "backend/skills/atom-cli/atom-daemon.md",
      "backend/skills/atom-cli/atom-status.md",
      "backend/skills/atom-cli/atom-start.md",
      "backend/skills/atom-cli/atom-stop.md",
      "backend/skills/atom-cli/atom-execute.md",
      "backend/skills/atom-cli/atom-config.md"
    ]
  }'
```

### 2. Execute CLI Skills

```bash
# Check status (works with STUDENT+)
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "atom-status",
    "query": "show daemon status"
  }'

# Start daemon (requires AUTONOMOUS)
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "atom-daemon",
    "query": "start daemon on port 3000 with dev mode"
  }'
```

### 3. Verify Governance

```bash
# STUDENT agent blocked from daemon control
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "atom-daemon",
    "query": "start daemon"
  }'
# Response: {"success": false, "error": "STUDENT agents cannot execute AUTONOMOUS skills"}
```

## Skill Reference

### atom-daemon - Start Background Daemon

**Purpose:** Start Atom OS as a background daemon process

**Maturity:** AUTONOMOUS (system resource management)

**Usage:**
```python
# Via agent query
"start daemon on port 3000 with 4 workers"

# Via API
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "skill_id": "atom-daemon",
    "query": "start daemon with host 0.0.0.0 port 3000 workers 4 dev mode"
  }'
```

**Options:**
| Flag | Description | Example |
|------|-------------|---------|
| `--port <number>` | Port for web server | "port 8080" |
| `--host <address>` | Host to bind to | "host 0.0.0.0" |
| `--workers <count>` | Number of worker processes | "workers 4" |
| `--host-mount` | Enable host filesystem mount | "host mount" |
| `--dev` | Enable development mode | "dev" or "development" |
| `--foreground` | Run in foreground (not daemon) | "foreground" |

**Examples:**
```bash
# Basic start
atom-os daemon

# With port and workers
atom-os daemon --port 8080 --workers 4

# Development mode with host mount
atom-os daemon --dev --host-mount --port 3000

# Foreground mode (not daemon)
atom-os daemon --foreground
```

**Output Format:**
```json
{
  "success": true,
  "stdout": "Daemon started successfully\nPID: 12345\nDashboard: http://localhost:3000",
  "stderr": "",
  "returncode": 0
}
```

**Security Warnings:**
- ⚠️ Requires AUTONOMOUS maturity
- ⚠️ Background service management
- ⚠️ System resource allocation
- ⚠️ Host mount enables filesystem access

---

### atom-status - Check Daemon Status

**Purpose:** Check if daemon is running and display health metrics

**Maturity:** STUDENT (read-only, safe for all levels)

**Usage:**
```python
# Via agent query
"check daemon status"

# Via API
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "skill_id": "atom-status",
    "query": "show daemon status"
  }'
```

**Output Fields:**
| Field | Description | Example |
|-------|-------------|---------|
| `Status` | RUNNING or NOT_RUNNING | "Status: RUNNING" |
| `PID` | Process ID | "PID: 12345" |
| `Memory` | Memory usage in MB | "Memory: 512 MB" |
| `CPU` | CPU percentage | "CPU: 5.2%" |
| `Uptime` | Runtime in seconds | "Uptime: 3600" |
| `Dashboard` | Web dashboard URL | "Dashboard: http://localhost:8000" |

**Examples:**
```bash
# Check status
atom-os status

# Output example:
Status: RUNNING
PID: 12345
Memory: 512 MB
CPU: 5.2%
Uptime: 3600
Dashboard: http://localhost:8000
```

**Output Format:**
```json
{
  "success": true,
  "stdout": "Status: RUNNING\nPID: 12345\nMemory: 512 MB\nCPU: 5.2%\nUptime: 3600\nDashboard: http://localhost:8000",
  "stderr": "",
  "returncode": 0
}
```

**Note:** Safe for all maturity levels including STUDENT agents.

---

### atom-start - Start Server (Foreground)

**Purpose:** Start Atom OS server in foreground mode (not as daemon)

**Maturity:** AUTONOMOUS (system resource management)

**Usage:**
```python
# Via agent query
"start server on port 8080 with 2 workers"

# Via API
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "skill_id": "atom-start",
    "query": "start server with workers 2 port 8080"
  }'
```

**Options:**
| Flag | Description | Example |
|------|-------------|---------|
| `--port <number>` | Port for web server | "port 8080" |
| `--host <address>` | Host to bind to | "host 0.0.0.0" |
| `--workers <count>` | Number of worker processes | "workers 4" |
| `--dev` | Enable development mode | "dev" |
| `--host-mount` | Enable host filesystem mount | "host mount" |

**Examples:**
```bash
# Basic start (foreground)
atom-os start

# With port and workers
atom-os start --port 8080 --workers 4

# Development mode
atom-os start --dev --port 3000
```

**Output Format:**
```json
{
  "success": true,
  "stdout": "Server started successfully\nDashboard: http://localhost:8080\nAPI: http://localhost:8080/api",
  "stderr": "",
  "returncode": 0
}
```

**Security Warnings:**
- ⚠️ Requires AUTONOMOUS maturity
- ⚠️ Foreground process management
- ⚠️ Port binding and network resources
- ⚠️ Development mode may expose debug information

---

### atom-stop - Stop Daemon

**Purpose:** Gracefully stop the running daemon process

**Maturity:** AUTONOMOUS (system service termination)

**Usage:**
```python
# Via agent query
"stop daemon gracefully"

# Via API
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "skill_id": "atom-stop",
    "query": "stop daemon"
  }'
```

**Behavior:**
- Sends SIGTERM for graceful shutdown
- Waits up to 10 seconds for process to exit
- Force kills with SIGKILL if still running
- Cleans up PID files and resources

**Examples:**
```bash
# Stop daemon gracefully
atom-os stop
```

**Output Format:**
```json
{
  "success": true,
  "stdout": "Daemon stopped successfully\nPID file cleaned up",
  "stderr": "",
  "returncode": 0
}
```

**Security Warnings:**
- ⚠️ Requires AUTONOMOUS maturity
- ⚠️ Terminates running services
- ⚠️ May disrupt ongoing operations
- ⚠️ System service management

---

### atom-execute - Execute On-Demand Command

**Purpose:** Execute a command on-demand via API endpoint

**Maturity:** AUTONOMOUS (system command execution)

**Usage:**
```python
# Via agent query
"execute command on atom"

# Via API
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "skill_id": "atom-execute",
    "query": "run system command"
  }'
```

**Current Implementation:**
- Placeholder for future command routing
- Currently displays available endpoints
- Ready for extended functionality

**Examples:**
```bash
# Show available endpoints (current implementation)
atom-os execute

# Future usage:
atom-os execute "run backup"
```

**Output Format:**
```json
{
  "success": true,
  "stdout": "Available endpoints:\nPOST /api/agents/{id}/execute\nPOST /api/skills/execute",
  "stderr": "",
  "returncode": 0
}
```

**Security Warnings:**
- ⚠️ Requires AUTONOMOUS maturity
- ⚠️ Future command execution capability
- ⚠️ System access through commands
- ⚠️ Placeholder implementation currently

---

### atom-config - Show Configuration

**Purpose:** Display current Atom configuration and environment variables

**Maturity:** STUDENT (read-only, safe for all levels)

**Usage:**
```python
# Via agent query
"show configuration"

# Via API
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "skill_id": "atom-config",
    "query": "show atom configuration"
  }'
```

**Configuration Displayed:**
- **Server Settings**: PORT, HOST, WORKERS
- **Environment**: ATOM_EDITION, ATOM_HOST_MOUNT_ENABLED
- **Database**: DATABASE_URL
- **LLM Providers**: OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY
- **API Endpoints**: Agent execution, skill execution URLs
- **Daemon Settings**: When --show-daemon flag used

**Examples:**
```bash
# Show configuration
atom-os config

# Show daemon configuration
atom-os config --show-daemon
```

**Output Format:**
```json
{
  "success": true,
  "stdout": "=== Atom Configuration ===\nPORT: 8000\nHOST: 0.0.0.0\nWORKERS: 1\nEDITION: Personal\nATOM_HOST_MOUNT_ENABLED: false\n\n=== Database ===\nDATABASE_URL: sqlite:///./atom_dev.db\n\n=== LLM Providers ===\nOPENAI_API_KEY: sk-***\nANTHROPIC_API_KEY: sk-***\nDEEPSEEK_API_KEY: sk-***",
  "stderr": "",
  "returncode": 0
}
```

**Note:** Safe for all maturity levels. Displays sensitive information (API keys) with partial masking.

## Import Workflow

### Prerequisites

1. **Atom Server Running**
```bash
python -m uvicorn main:app --reload --port 8000
```

2. **Authentication Token**
```bash
# Get JWT token
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'
```

### Step-by-Step Import

#### 1. Import Individual Skills

```bash
# Import atom-daemon
curl -X POST http://localhost:8000/api/skills/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_files": ["backend/skills/atom-cli/atom-daemon.md"]
  }'

# Import all CLI skills
curl -X POST http://localhost:8000/api/skills/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_files": [
      "backend/skills/atom-cli/atom-daemon.md",
      "backend/skills/atom-cli/atom-status.md",
      "backend/skills/atom-cli/atom-start.md",
      "backend/skills/atom-cli/atom-stop.md",
      "backend/skills/atom-cli/atom-execute.md",
      "backend/skills/atom-cli/atom-config.md"
    ]
  }'
```

#### 2. Verify Import Status

```bash
# List imported skills
curl -X GET "http://localhost:8000/api/skills?source=local&tags=atom-cli" \
  -H "Authorization: Bearer $TOKEN"
```

#### 3. Test Skill Execution

```bash
# Test status skill (should work with any token)
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "atom-status",
    "query": "show daemon status"
  }'
```

### Bulk Import Script

```bash
#!/bin/bash
# import-cli-skills.sh

API_TOKEN="your-jwt-token"
API_BASE="http://localhost:8000"

# Import all CLI skills
curl -X POST "$API_BASE/api/skills/import" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_files": [
      "backend/skills/atom-cli/atom-daemon.md",
      "backend/skills/atom-cli/atom-status.md",
      "backend/skills/atom-cli/atom-start.md",
      "backend/skills/atom-cli/atom-stop.md",
      "backend/skills/atom-cli/atom-execute.md",
      "backend/skills/atom-cli/atom-config.md"
    ]
  }'

echo "CLI skills imported successfully"
```

## Usage Examples

### Example 1: Agent Workflow - Start and Monitor

```python
# Agent workflow: Start daemon → Wait for ready → Check status

# Step 1: Start daemon
start_result = skill_executor.execute("atom-daemon", "start daemon on port 3000")

# Step 2: Wait for ready (uses polling)
if start_result["success"]:
    from tools.atom_cli_skill_wrapper import wait_for_daemon_ready
    ready = wait_for_daemon_ready(max_wait=15)
    if ready:
        # Step 3: Check status
        status_result = skill_executor.execute("atom-status", "check daemon status")
        print(f"Daemon status: {status_result['stdout']}")
```

### Example 2: Configuration Management

```python
# Check configuration before operations
config_result = skill_executor.execute("atom-config", "show configuration")

# Parse configuration
import json
config_lines = config_result["stdout"].split("\n")
port = next((line.split(": ")[1] for line in config_lines if line.startswith("PORT")), "8000")

# Start with matching port
if port == "8000":
    skill_executor.execute("atom-daemon", "start daemon on port 8000")
```

### Example 3: Error Handling

```python
try:
    # Try to start daemon (may fail if already running)
    result = skill_executor.execute("atom-daemon", "start daemon")

    if not result["success"]:
        if "already running" in result["stderr"]:
            # Daemon already running, check status instead
            status_result = skill_executor.execute("atom-status", "check status")
            print(f"Daemon already running: {status_result['stdout']}")
        else:
            print(f"Failed to start daemon: {result['stderr']}")

except Exception as e:
    print(f"Error executing skill: {e}")
```

### Example 4: Multi-Agent Coordination

```python
# STUDENT agent can monitor but not control
student_agent = Agent(maturity="STUDENT")
status_result = student_agent.execute_skill("atom-status", "show status")
print(f"Status: {status_result['stdout']}")

# AUTONOMOUS agent can start/stop services
autonomous_agent = Agent(maturity="AUTONOMOUS")
autonomous_agent.execute_skill("atom-daemon", "start daemon on port 8080")
```

## Troubleshooting

### Common Issues

#### 1. Command Not Found Error

**Error:** `Command not found: atom-os`

**Solution:**
1. Verify Atom CLI is installed
2. Check PATH environment variable
3. Use absolute path: `/usr/local/bin/atom-os`

```bash
# Check installation
which atom-os

# If not found, install from pip
pip install atom-os
```

#### 2. Permission Denied (AUTONOMOUS Gate)

**Error:** `STUDENT agents cannot execute AUTONOMOUS skills`

**Solution:**
1. **For Development**: Temporarily use AUTONOMOUS agent token
2. **For Production**: Agent must graduate to AUTONOMOUS level
3. **Alternative**: Use STUDENT-safe skills (status, config)

```bash
# Using STUDENT token (limited access)
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -d '{
    "skill_id": "atom-status",
    "query": "show status"
  }'
```

#### 3. Daemon Race Conditions

**Problem:** Daemon start command returns success but daemon isn't ready

**Solution:** Use wait_for_daemon_ready helper

```python
from tools.atom_cli_skill_wrapper import execute_atom_cli_command, wait_for_daemon_ready

# Start daemon
result = execute_atom_cli_command("daemon", ["--port", "3000"])

# Wait for it to be ready
if result["success"] and wait_for_daemon_ready(max_wait=10):
    print("Daemon is ready!")
else:
    print("Daemon failed to start")
```

#### 4. PID File Errors

**Error:** `PID file not found` or `Stale PID file`

**Solution:**
1. Check if process is actually running
2. Clean up stale PID files
3. Use force stop if needed

```bash
# Check if process is running
ps aux | grep atom-os

# Clean up PID files (manual)
rm -f /tmp/atom-os.pid

# Force stop
atom-os stop --force
```

#### 5. Timeout Errors

**Error:** `Command timed out after 30 seconds`

**Solution:**
1. Reduce timeout for quick commands
2. Check for hanging processes
3. Increase timeout for long-running operations

```python
# Custom timeout
from tools.atom_cli_skill_wrapper import execute_atom_cli_command
import subprocess

# Override timeout for long operations
result = execute_atom_cli_command("start", timeout=60)
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Start daemon with debug logging
atom-os daemon --dev --log-level DEBUG

# Or set environment variable
export ATOM_LOG_LEVEL=DEBUG
atom-os daemon
```

### Testing Skills Locally

```bash
# Test skills without API
python -c "
from tools.atom_cli_skill_wrapper import execute_atom_cli_command
result = execute_atom_cli_command('status')
print('Status:', result['success'])
print('Output:', result['stdout'])
"
```

### Health Checks

Verify Atom services are running:

```bash
# Check API health
curl http://localhost:8000/health/live

# Check database connection
curl http://localhost:8000/health/ready

# Check metrics
curl http://localhost:8000/health/metrics
```

## API Reference

### Import Skills

**Endpoint:** `POST /api/skills/import`

**Request Body:**
```json
{
  "skill_files": [
    "path/to/skill1.md",
    "path/to/skill2.md"
  ]
}
```

**Response:**
```json
{
  "success": true,
  "imported": [
    {
      "skill_id": "atom-daemon",
      "name": "Atom Daemon Control",
      "status": "active"
    }
  ],
  "errors": []
}
```

### Execute Skills

**Endpoint:** `POST /api/skills/execute`

**Request Body:**
```json
{
  "skill_id": "atom-status",
  "query": "show daemon status"
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "stdout": "Status: RUNNING\nPID: 12345",
    "stderr": "",
    "returncode": 0
  },
  "execution_time": 0.152
}
```

### List Skills

**Endpoint:** `GET /api/skills?source=local&tags=atom-cli`

**Response:**
```json
{
  "skills": [
    {
      "skill_id": "atom-daemon",
      "name": "Atom Daemon Control",
      "tags": ["atom-cli", "system"],
      "maturity_requirement": "AUTONOMOUS",
      "status": "active"
    }
  ]
}
```

### Error Responses

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 400 | INVALID_REQUEST | Malformed request body |
| 401 | UNAUTHORIZED | Missing or invalid token |
| 403 | FORBIDDEN | Insufficient maturity level |
| 404 | SKILL_NOT_FOUND | Skill not found |
| 500 | EXECUTION_ERROR | Subprocess execution failed |
| 504 | TIMEOUT | Command execution timed out |

## Security Considerations

### Governance Enforcement

- AUTONOMOUS required for daemon control (start/stop/execute)
- STUDENT allowed for read-only operations (status/config)
- All executions logged to ShellSession table
- Command isolation through subprocess execution

### Best Practices

1. **Use Appropriate Maturity**: Only allow AUTONOMOUS agents for critical operations
2. **Monitor Logs**: Review ShellSession for CLI command usage
3. **Rate Limit**: Implement rate limiting for CLI skill usage
4. **Audit Trail**: Keep execution logs for security review

### Risk Mitigation

- **Timeout Protection**: 30-second timeout prevents hanging processes
- **Command Isolation**: Subprocess execution with shell=False
- **Argument Validation**: Safe parsing of user inputs
- **Process Cleanup**: Proper daemon lifecycle management

## Related Documentation

- [Community Skills Guide](./COMMUNITY_SKILLS.md)
- [Personal Edition Guide](./PERSONAL_EDITION.md)
- [CLI Installation](./INSTALLATION.md)
- [Agent Governance](../backend/docs/CODE_QUALITY_STANDARDS.md#governance)

## Support

For issues with CLI skills:
1. Check troubleshooting section above
2. Verify skill import status via API
3. Review execution logs in database
4. Test with manual CLI commands

**GitHub Issues:** Report bugs and request features
**Discussions:** Ask questions and share usage patterns
**Documentation:** Contribute improvements to this guide

---

*This guide covers Phase 25: Atom CLI as OpenClaw Skills. For the latest updates, see the [Atom documentation](./) or check the GitHub repository.*