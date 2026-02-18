---
name: atom-start
description: Start Atom OS server (foreground, not daemon)
version: 1.0.0
author: Atom Team
tags: [atom, cli, start, server]
maturity_level: AUTONOMOUS
governance:
  maturity_requirement: AUTONOMOUS
  reason: "Server start manages system resources, requires full autonomy"
---

# Atom Server Starter

Start Atom OS server in foreground (not daemon mode).

## Usage

Execute this skill to start Atom server:
```
atom-os start [options]
```

## Options

- `--port <number>`: Port for web server (default: 8000)
- `--host <address>`: Host to bind to (default: 0.0.0.0)
- `--workers <count>`: Number of worker processes (default: 1)
- `--host-mount`: Enable host filesystem mount (requires confirmation)
- `--dev`: Enable development mode with auto-reload

## Examples

Start server on default port:
```
atom-os start
```

Start server on custom port with development mode:
```
atom-os start --port 3000 --dev
```

Start server with host mount:
```
atom-os start --host-mount
```

## Output

Server startup information:
- Edition: Personal or Enterprise
- Host: Binding address
- Port: Server port
- Workers: Number of worker processes
- Dev mode: Enabled/disabled
- Host mount: Enabled/disabled
- Dashboard URL: http://localhost:8000 (or custom port)
- API docs: http://localhost:8000/docs

## Notes

⚠️ **AUTONOMOUS maturity required** - This command manages system resources.

**Foreground Mode:** This command runs Atom OS in the foreground (not as daemon). Use `atom-os daemon` for background service.

**Host Mount Warning:** Enabling `--host-mount` gives containers write access to host directories. Governance protections active:
- AUTONOMOUS maturity gate required
- Command whitelist (ls, cat, grep, git, npm, etc.)
- Blocked commands (rm, mv, chmod, kill, sudo, etc.)
- 5-minute timeout enforcement
- Full audit trail to ShellSession table

## Difference from daemon

- `atom-os start`: Runs in foreground (attached to terminal)
- `atom-os daemon`: Runs in background (detached process)

Use `start` for development/testing, use `daemon` for production service.
