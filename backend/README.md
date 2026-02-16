# Atom OS Backend

AI-powered business automation platform with multi-agent governance.

## Quick Start

### Install via pip

```bash
pip install atom-os
```

### Start Atom OS

```bash
# Start on default port (8000)
atom-os start

# Development mode with auto-reload
atom-os start --dev

# Custom port and host
atom-os start --port 3000 --host 127.0.0.1

# With host filesystem mount (requires confirmation)
atom-os start --host-mount
```

### CLI Commands

```bash
# Show help
atom-os --help

# Check system status
atom-os status

# Show configuration
atom-os config
```

## Installation Options

### From PyPI (Recommended)

```bash
pip install atom-os
```

### From Source

```bash
git clone https://github.com/rush86999/atom.git
cd atom/backend
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/rush86999/atom.git
cd atom/backend
pip install -e ".[dev]"
```

## Host Filesystem Mount

**⚠️ SECURITY WARNING**: Host filesystem mount gives containers write access to host directories.

### Governance Protections

When you enable host mount with `--host-mount`, the following protections are in place:

- ✅ **AUTONOMOUS maturity gate** required for shell access
- ✅ **Command whitelist** (ls, cat, grep, git, npm, docker, kubectl, etc.)
- ✅ **Blocked commands** (rm, mv, chmod, kill, sudo, reboot, iptables, etc.)
- ✅ **5-minute timeout** enforcement
- ✅ **Full audit trail** to ShellSession table

### Risks

However, this STILL carries risk:

- Bugs in governance code could bypass protections
- Compromised AUTONOMOUS agent has shell access
- Docker escape vulnerabilities could be exploited

### Enable Host Mount

```bash
atom-os start --host-mount
```

You'll be asked to confirm the risks before proceeding.

## Configuration

### Environment Variables

```bash
# Server
PORT=8000                    # Server port (default: 8000)
HOST=0.0.0.0                # Server host (default: 0.0.0.0)
WORKERS=1                   # Worker processes (default: 1)

# Database
DATABASE_URL=sqlite:///./atom_dev.db    # Database connection string

# LLM Providers
OPENAI_API_KEY=sk-...                    # OpenAI API key
ANTHROPIC_API_KEY=sk-...                # Anthropic API key
DEEPSEEK_API_KEY=sk-...                 # DeepSeek API key

# Host Mount (SECURITY WARNING)
ATOM_HOST_MOUNT_ENABLED=false           # Enable host filesystem mount
ATOM_HOST_MOUNT_DIRS=/tmp:/Users/user/projects  # Allowed directories
```

### Using .env File

Create a `.env` file in the backend directory:

```bash
cp .env.example .env
# Edit .env with your configuration
```

## Development

### Run Tests

```bash
cd backend
pytest tests/ -v
```

### Run with Auto-Reload

```bash
atom-os start --dev
```

## Architecture

- **FastAPI** - Web framework
- **SQLAlchemy 2.0** - ORM
- **PostgreSQL/SQLite** - Database
- **Uvicorn** - ASGI server
- **Click** - CLI framework

## Governance System

Atom OS features a 4-tier maturity system:

1. **STUDENT** - Read-only (charts, markdown)
2. **INTERN** - Streaming, form presentation (proposals only)
3. **SUPERVISED** - Form submissions, state changes (real-time monitoring)
4. **AUTONOMOUS** - Full autonomy, all actions

Agents progress through maturity levels based on performance and constitutional compliance.

## Support

- **Documentation**: https://github.com/rush86999/atom/tree/main/docs
- **Issues**: https://github.com/rush86999/atom/issues
- **License**: MIT

## OpenClaw Integration

Atom OS draws inspiration from OpenClaw's single-command installer approach while maintaining enterprise-grade governance and multi-agent architecture.

**Key differences**:
- Multi-agent system vs single agent
- 4-tier governance maturity levels
- Business automation focus (46+ integrations)
- Real-time operation visibility
- Comprehensive audit trails
