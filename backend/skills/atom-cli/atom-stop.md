---
name: atom-stop
description: Stop Atom OS background daemon gracefully
version: 1.0.0
author: Atom Team
tags: [atom, cli, stop, shutdown]
maturity_level: AUTONOMOUS
governance:
  maturity_requirement: AUTONOMOUS
  reason: "Stopping daemon terminates service, requires full autonomy"
---

# Atom Daemon Stopper

Stop Atom OS background daemon gracefully with cleanup.

## Usage

Execute this skill to stop the daemon:
```
atom-os stop
```

## Behavior

1. **Graceful Shutdown:** Sends SIGTERM signal to daemon process
2. **Timeout Waits:** Waits up to 10 seconds for graceful shutdown
3. **Force Kill:** If still running after timeout, sends SIGKILL
4. **Cleanup:** Removes PID file automatically

## Examples

Stop running daemon:
```
atom-os stop
```

Expected output (success):
```
✓ Atom OS stopped (PID: 12345)
```

Expected output (not running):
```
ℹ Atom OS was not running
```

## Output

- Success message with PID (if daemon was running)
- Info message (if daemon was not running)

## Shutdown Process

1. Read PID from ~/.atom/pids/atom-os.pid
2. Send SIGTERM to process
3. Wait up to 10 seconds for process to exit
4. If still alive, send SIGKILL
5. Remove PID file

## Error Handling

- **Stale PID file:** If process died unexpectedly, cleanup happens automatically
- **Permission denied:** Requires same user permissions as daemon startup
- **PID file missing:** Treated as "not running"

## Notes

⚠️ **AUTONOMOUS maturity required** - This command terminates the background service.

**Graceful vs. Force Kill:**
- SIGTERM (graceful): Allows Atom to save state, close connections
- SIGKILL (force): Immediate termination if graceful shutdown fails

## Related Commands

- `atom-os daemon` - Start daemon
- `atom-os status` - Check daemon status
