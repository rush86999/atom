---
name: atom-config
description: Show Atom OS configuration and environment variables
version: 1.0.0
author: Atom Team
tags: [atom, cli, config, environment]
maturity_level: STUDENT
governance:
  maturity_requirement: STUDENT
  reason: "Read-only configuration display, safe for all maturity levels"
---

# Atom Configuration Display

Show Atom OS configuration details and environment variables.

## Usage

Execute this skill to display configuration:
```
atom-os config [--show-daemon]
```

## Options

- `--show-daemon`: Include daemon-specific configuration (PID file, log file location)

## Configuration Sections

### Server
- `PORT`: Server port (default: 8000)
- `HOST`: Server host (default: 0.0.0.0)
- `WORKERS`: Worker processes (default: 1)

### Host Mount (SECURITY WARNING)
- `ATOM_HOST_MOUNT_ENABLED`: Enable host filesystem mount
- `ATOM_HOST_MOUNT_DIRS`: Allowed directories (colon-separated)

### Database
- `DATABASE_URL`: Database connection string

### LLM Providers
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `DEEPSEEK_API_KEY`: DeepSeek API key

### Agent-to-Agent Execution
- `POST /api/agent/start` - Start Atom as service
- `POST /api/agent/stop` - Stop Atom service
- `GET /api/agent/status` - Check status
- `POST /api/agent/execute` - Execute command

### Daemon (with --show-daemon flag)
- `PID File`: ~/.atom/pids/atom-os.pid
- `Log File`: ~/.atom/logs/daemon.log
- `Running`: Current daemon status

## Examples

Show basic configuration:
```
atom-os config
```

Expected output:
```
Atom OS Configuration
========================================

Environment Variables:

Server:
  PORT              - Server port (default: 8000)
  HOST              - Server host (default: 0.0.0.0)
  WORKERS           - Worker processes (default: 1)

Database:
  DATABASE_URL      - Database connection string

LLM Providers:
  OPENAI_API_KEY    - OpenAI API key
  ANTHROPIC_API_KEY - Anthropic API key
  DEEPSEEK_API_KEY  - DeepSeek API key

See .env file for full configuration.
```

Show daemon configuration:
```
atom-os config --show-daemon
```

## Notes

✓ **Read-only operation** - Safe for all maturity levels (STUDENT+)

This command displays configuration but does not modify any settings.

## Environment File

Full configuration is stored in `.env` file in Atom project root directory.
