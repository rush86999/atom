---
name: atom-status
description: Check Atom OS daemon status (running state, PID, uptime, memory, CPU)
version: 1.0.0
author: Atom Team
tags: [atom, cli, status, monitoring]
maturity_level: STUDENT
governance:
  maturity_requirement: STUDENT
  reason: "Read-only status check, safe for all maturity levels"
---

# Atom Status Checker

Check the running status of the Atom OS daemon process.

## Usage

Execute this skill to check daemon status:
```
atom-os status
```

## Output

Returns daemon status information:

**If running:**
- Status: RUNNING
- PID: Process identifier
- Memory: Memory usage in MB
- CPU: CPU usage percentage
- Uptime: Time since daemon started (seconds)
- Dashboard URL: http://localhost:8000

**If stopped:**
- Status: STOPPED
- Note: Additional information (if available)

## Examples

Check if daemon is running:
```
atom-os status
```

Expected output:
```
Status: RUNNING
  PID: 12345
  Memory: 256.5 MB
  CPU: 5.2%
  Uptime: 3600s
  Dashboard: http://localhost:8000
```

Check stopped daemon:
```
atom-os status
```

Expected output:
```
Status: STOPPED
```

## Notes

✓ **Read-only operation** - Safe for all maturity levels (STUDENT+)

This command does not modify any system state. It only reads daemon status information from PID file and process table.

## Requirements

- Atom CLI must be installed (`atom-os` command available)
- No special permissions required
