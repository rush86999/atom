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

Returns daemon process ID and status information:
- PID: Process identifier for daemon
- Dashboard URL: http://localhost:8000 (or custom port)
- Log file location: ~/.atom/logs/daemon.log

## Notes

⚠️ **AUTONOMOUS maturity required** - This command manages background services.

**Host Mount Warning:** Enabling `--host-mount` gives containers write access to host directories. Governance protections active:
- AUTONOMOUS maturity gate required
- Command whitelist (ls, cat, grep, git, npm, etc.)
- Blocked commands (rm, mv, chmod, kill, sudo, etc.)
- 5-minute timeout enforcement
- Full audit trail to ShellSession table

## Control Commands

After starting daemon, use these commands:
- `atom-os status` - Check daemon status
- `atom-os stop` - Stop daemon
