---
name: atom-execute
description: Execute Atom command on-demand (temporary startup)
version: 1.0.0
author: Atom Team
tags: [atom, cli, execute, command]
maturity_level: AUTONOMOUS
governance:
  maturity_requirement: AUTONOMOUS
  reason: "On-demand execution requires full autonomy"
---

# Atom Command Executor

Execute Atom commands on-demand with temporary startup.

## Usage

Execute this skill to run Atom commands:
```
atom-os execute <command>
```

## Arguments

- `command`: Atom command to execute (required)

## Examples

Execute agent chat command:
```
atom-os execute "agent.chat('Hello, create a report')"
```

Execute workflow command:
```
atom-os execute "workflow.run('monthly_report')"
```

## Behavior

This command would:
1. Start Atom temporarily
2. Execute the specified command
3. Return the result
4. Shut down Atom

## Current Implementation Status

⚠️ **Command routing not yet implemented** - Use REST API instead.

## Alternative: REST API

For programmatic control, use these REST API endpoints:

### Start Atom as Service
```http
POST /api/agent/start
Content-Type: application/json

{
  "port": 8000,
  "host": "0.0.0.0"
}
```

### Execute Single Command
```http
POST /api/agent/execute
Content-Type: application/json

{
  "command": "agent.chat('Hello')",
  "agent_id": "agent-123"
}
```

### Stop Service
```http
POST /api/agent/stop
```

### Check Status
```http
GET /api/agent/status
```

## Notes

⚠️ **AUTONOMOUS maturity required** - On-demand execution requires full autonomy.

**Temporary Execution:** This command starts Atom only for the duration of command execution, then shuts down. For long-running service, use `atom-os daemon` instead.

**Future Implementation:** Command routing will be implemented in a future phase, allowing direct command execution via this CLI command.

## Documentation

See `atom-os config` for full API documentation and configuration details.
