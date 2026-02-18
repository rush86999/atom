# Atom Installation Guide

> **Single-command installation:** `pip install atom-os`

Atom offers two editions:
- **Personal Edition** - Free, local, single-user (default)
- **Enterprise Edition** - Multi-user, monitoring, SSO (paid)

---

## Quick Start (5 minutes)

### 1. Install Atom

```bash
# Install Personal Edition (default)
pip install atom-os

# Or install Enterprise Edition directly
pip install atom-os[enterprise]
```

### 2. Initialize Atom

```bash
# Initialize Personal Edition
atom init

# Or initialize Enterprise Edition
atom init --edition enterprise
```

### 3. Configure API Keys

Edit the generated `.env` file:

```bash
nano .env
```

Add your LLM provider keys:

```bash
# At minimum, set one:
OPENAI_API_KEY=sk-your-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 4. Start Atom

**Foreground (development):**
```bash
atom start
```

**Background (daemon mode):**
```bash
atom daemon          # Start background service
atom status          # Check daemon status
atom stop            # Stop daemon
```

Open http://localhost:8000 in your browser.

---

## Personal Edition vs Enterprise Edition

| Feature | Personal | Enterprise |
|---------|----------|------------|
| **Price** | Free | Paid |
| **Users** | Single user | Multi-user |
| **Database** | SQLite | PostgreSQL |
| **Monitoring** | Basic | Prometheus + Grafana |
| **SSO** | None | Okta, Auth0, SAML |
| **Workspace Isolation** | No | Yes |
| **Audit Trail** | Basic logging | Full compliance |
| **Rate Limiting** | None | Configurable |
| **Support** | Community | Priority |

**Choose Personal if:**
- Personal use and experimentation
- Learning AI agents
- Local automation
- Privacy-focused (data never leaves your machine)

**Choose Enterprise if:**
- Team collaboration
- Production deployment
- Compliance requirements
- SSO integration
- Advanced monitoring

---

## Personal Edition Installation

### Prerequisites

- Python 3.11 or later
- 4GB RAM minimum (8GB recommended)
- 10GB disk space

### Install

```bash
pip install atom-os
```

This installs:
- Core agent system
- Workflow automation
- Canvas presentations
- Browser automation
- Episodic memory
- Agent governance
- Telegram connector
- Community skills (5,000+ OpenClaw/ClawHub)

### Initialize

```bash
atom init
```

This creates:
- `.env` file with Personal defaults
- `data/` directory for SQLite database
- Encryption keys (auto-generated)

### Configure

Edit `.env` and add your API keys:

```bash
# LLM Providers (add at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Vector embeddings (local, no API key needed)
EMBEDDING_PROVIDER=fastembed
```

### Start

```bash
atom start
```

Or run as daemon:

```bash
atom daemon
atom status
```

### Daemon Mode (Background Service)

Atom includes a daemon mode for running as a background service with automatic startup.

**Start daemon:**
```bash
atom daemon
# Runs in background, logs to data/atom-daemon.log
```

**Check status:**
```bash
atom status
# Shows: Running (PID: 12345) or Stopped
```

**Stop daemon:**
```bash
atom stop
# Graceful shutdown, saves state
```

**systemd Service (Linux Auto-Start):**
```bash
# Create systemd service
sudo tee /etc/systemd/system/atom-daemon.service > /dev/null <<EOF
[Unit]
Description=Atom AI Automation Platform
After=network.target

[Service]
Type=forking
User=$USER
WorkingDirectory=$HOME/.atom
ExecStart=$(which atom) daemon
ExecStop=$(which atom) stop
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable atom-daemon
sudo systemctl start atom-daemon
sudo systemctl status atom-daemon
```

See [PERSONAL_EDITION.md](PERSONAL_EDITION.md) for complete Personal Edition setup guide.

### Upgrade to Enterprise

```bash
atom enable enterprise
```

See [Upgrading to Enterprise](#upgrading-to-enterprise) below.

---

## Enterprise Edition Installation

### Prerequisites

- Python 3.11 or later
- PostgreSQL 12 or later
- Redis 6 or later (for multi-user)
- 8GB RAM minimum (16GB recommended)
- 25GB disk space

### Install

```bash
pip install atom-os[enterprise]
```

This installs Personal features plus:
- PostgreSQL driver
- Redis client
- Prometheus metrics
- SSO providers (Okta, Auth0)
- Advanced analytics
- Rate limiting

### Initialize

```bash
atom init --edition enterprise
```

Or with custom database:

```bash
atom init --edition enterprise \
    --database-url "postgresql://atom:password@localhost:5432/atom"
```

### Configure PostgreSQL

Create database:

```bash
createdb atom
```

Or update DATABASE_URL in `.env`:

```bash
DATABASE_URL=postgresql://atom:password@localhost:5432/atom
```

### Optional: Configure Redis

For multi-user pub/sub:

```bash
# Install Redis
brew install redis  # macOS
# OR
apt-get install redis-server  # Ubuntu

# Start Redis
redis-server
```

Update `.env`:

```bash
REDIS_URL=redis://localhost:6379/0
```

### Optional: Configure SSO

For Okta:

```bash
# In .env
ATOM_SSO_ENABLED=true
SSO_PROVIDER=okta
OKTA_DOMAIN=your-domain.okta.com
OKTA_CLIENT_ID=your-client-id
OKTA_CLIENT_SECRET=your-client-secret
```

For Auth0:

```bash
# In .env
ATOM_SSO_ENABLED=true
SSO_PROVIDER=auth0
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
```

### Start

```bash
atom start
```

---

## Upgrading to Enterprise

### From Personal to Enterprise

**Option 1: CLI Command (Recommended)**

```bash
atom enable enterprise
```

This:
- Installs enterprise dependencies
- Updates `.env` with enterprise settings
- Prompts for PostgreSQL configuration

**Option 2: Manual Upgrade**

```bash
# Install enterprise dependencies
pip install atom-os[enterprise]

# Update .env
ATOM_EDITION=enterprise
DATABASE_URL=postgresql://atom:password@localhost:5432/atom

# Restart Atom
atom stop
atom start
```

### Migrate SQLite to PostgreSQL

```bash
# Export from SQLite
atom export-database > backup.sql

# Import to PostgreSQL
psql atom < backup.sql

# Update .env
DATABASE_URL=postgresql://atom:password@localhost:5432/atom
```

---

## CLI Commands

### Basic Commands

```bash
atom --help              # Show help
atom init                # Initialize configuration
atom start               # Start Atom server
atom daemon              # Start as background service
atom stop                # Stop daemon
atom status              # Check status
atom config              # Show configuration
```

### Edition Commands

```bash
atom init --edition personal      # Personal Edition
atom init --edition enterprise    # Enterprise Edition
atom enable enterprise            # Upgrade to Enterprise
atom enable features              # List available features
```

### Daemon Commands

```bash
atom daemon                       # Start daemon
atom daemon --foreground          # Run in foreground
atom daemon --port 3000           # Custom port
atom status                       # Check status
atom stop                         # Stop daemon
```

### Configuration Commands

```bash
atom config                       # Show configuration
atom config --show-daemon         # Show daemon config
```

---

## Environment Variables

### Core Configuration

```bash
# Edition
ATOM_EDITION=personal|enterprise

# Server
PORT=8000
HOST=0.0.0.0
WORKERS=1

# Database
DATABASE_URL=sqlite:///./data/atom.db  # Personal
DATABASE_URL=postgresql://...          # Enterprise
```

### LLM Providers

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=...
```

### Vector Embeddings

```bash
# Personal Edition (local)
EMBEDDING_PROVIDER=fastembed
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5

# Enterprise Edition (cloud)
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### Enterprise Features

```bash
# Multi-User
ATOM_MULTI_USER_ENABLED=true

# Monitoring
ATOM_MONITORING_ENABLED=true
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# SSO
ATOM_SSO_ENABLED=true
SSO_PROVIDER=okta|auth0|saml

# Audit Trail
ATOM_AUDIT_TRAIL_ENABLED=true
AUDIT_LOG_RETENTION_DAYS=90

# Rate Limiting
ATOM_RATE_LIMITING_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
```

---

## Troubleshooting

### Issue: Module not found error

**Error:** `ModuleNotFoundError: No module named 'atom_os'`

**Solution:**
```bash
# Install in development mode
pip install -e .

# Or reinstall
pip uninstall atom-os
pip install atom-os
```

### Issue: Port already in use

**Error:** `Address already in use`

**Solution:**
```bash
# Change port in .env
PORT=3000

# Or specify via CLI
atom start --port 3000
```

### Issue: PostgreSQL connection failed

**Error:** `could not connect to server`

**Solution:**
```bash
# Check PostgreSQL is running
pg_ctl status

# Check connection string
psql "postgresql://atom:password@localhost:5432/atom"

# Create database if missing
createdb atom
```

### Issue: Enterprise features not available

**Error:** `Feature requires Enterprise Edition`

**Solution:**
```bash
# Install enterprise extras
pip install atom-os[enterprise]

# Enable enterprise
atom enable enterprise

# Restart
atom stop
atom start
```

### Issue: Permission denied on data directory

**Error:** `PermissionError: [Errno 13] Permission denied`

**Solution:**
```bash
# Check directory permissions
ls -la data/

# Fix permissions
chmod 755 data/
```

---

## Development Installation

### Install in Development Mode

```bash
# Clone repository
git clone https://github.com/rush86999/atom.git
cd atom/backend

# Install in development mode
pip install -e ".[dev,test]"

# Install pre-commit hooks
pre-commit install
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=api --cov-report=html

# Run specific test
pytest tests/test_package_feature_service.py -v
```

### Development Server

```bash
# Start with auto-reload
atom start --dev

# Or using uvicorn directly
uvicorn main_api_app:app --reload --log-level debug
```

---

## Uninstallation

### Remove Atom

```bash
# Uninstall package
pip uninstall atom-os

# Remove configuration and data
rm -rf .env data/

# Optional: Remove virtual environment
rm -rf venv/
```

### Enterprise Database Cleanup

```bash
# Drop database
dropdb atom

# Remove user (if created)
dropuser atom
```

---

## Next Steps

- [Feature Matrix](FEATURE_MATRIX.md) - Compare editions
- [Personal Edition Guide](PERSONAL_EDITION.md) - Personal setup details
- [API Documentation](backend/docs/API_DOCUMENTATION.md) - REST API reference
- [Development Guide](CONTRIBUTING.md) - Contributing guide

---

## Getting Help

- **Documentation:** https://github.com/rush86999/atom/tree/main/docs
- **Issues:** https://github.com/rush86999/atom/issues
- **Discussions:** https://github.com/rush86999/atom/discussions
