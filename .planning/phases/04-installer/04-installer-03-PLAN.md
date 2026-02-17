---
phase: 04-installer
plan: 03
type: execute
wave: 2
depends_on: ["04-installer-01", "04-installer-02"]
files_modified:
  - docs/INSTALLATION.md
  - docs/FEATURE_MATRIX.md
  - README.md
  - .github/workflows/publish.yml
  - MANIFEST.in
autonomous: true

must_haves:
  truths:
    - INSTALLATION.md documents Personal vs Enterprise installation
    - FEATURE_MATRIX.md lists all features by edition
    - README.md has quick start with pip install atom-os
    - GitHub Actions workflow publishes to PyPI
    - MANIFEST.in includes all necessary package files
    - Documentation covers migration from Personal to Enterprise
  artifacts:
    - path: docs/INSTALLATION.md
      provides: Complete installation guide
      min_lines: 200
      contains: "pip install atom-os", "Personal Edition", "Enterprise Edition"
    - path: docs/FEATURE_MATRIX.md
      provides: Feature comparison by edition
      min_lines: 100
      contains: "Personal", "Enterprise", "Feature"
    - path: .github/workflows/publish.yml
      provides: PyPI publishing workflow
      min_lines: 80
      contains: "pypi", "trusted-publishing", "oidc"
    - path: MANIFEST.in
      provides: Package manifest for data files
      contains: "include", "recursive-include"
  key_links:
    - from: "docs/INSTALLATION.md"
      to: "README.md"
      via: "Quick start section"
      pattern: "pip install atom-os"
    - from: ".github/workflows/publish.yml"
      to: "PyPI"
      via: "Trusted Publishing OIDC"
      pattern: "permissions: id-token: write"
    - from: "docs/FEATURE_MATRIX.md"
      to: "backend/core/package_feature_service.py"
      via: "Feature registry"
      pattern: "FEATURE_REGISTRY"
---

<objective>
Create documentation (installation guide, feature matrix) and PyPI publishing workflow.

Purpose: Complete simplified entry point with comprehensive docs and automated publishing
Output: Installation docs, feature comparison, GitHub Actions for PyPI
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
@/Users/rushiparikh/.claude/get-shit-done/references/checkpoints.md
</execution_context>

<context>
@.planning/phases/04-installer/04-installer-01-PLAN.md
@.planning/phases/04-installer/04-installer-02-PLAN.md
@.planning/ROADMAP.md
@.planning/STATE.md
@docs/PERSONAL_EDITION.md
@README.md
@.github/workflows/deploy.yml

# Existing docs
@backend/docs/API_DOCUMENTATION.md
@backend/docs/DEPLOYMENT_RUNBOOK.md
</context>

<tasks>

<task type="auto">
  <name>Create comprehensive installation guide</name>
  <files>docs/INSTALLATION.md</files>
  <action>
Create docs/INSTALLATION.md (300-400 lines):

```markdown
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

```bash
atom start
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
atom init --edition enterprise \\
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
- [API Documentation](API_DOCUMENTATION.md) - REST API reference
- [Development Guide](DEVELOPMENT.md) - Contributing guide

---

## Getting Help

- **Documentation:** https://github.com/rush86999/atom/tree/main/docs
- **Issues:** https://github.com/rush86999/atom/issues
- **Discussions:** https://github.com/rush86999/atom/discussions
```

Comprehensive installation guide covering all scenarios.
  </action>
  <verify>
```bash
# Verify installation guide created
test -f docs/INSTALLATION.md
grep -n "pip install atom-os" docs/INSTALLATION.md
grep -n "Personal Edition\|Enterprise Edition" docs/INSTALLATION.md
grep -n "atom enable enterprise" docs/INSTALLATION.md
```
  </verify>
  <done>
INSTALLATION.md created with:
- Quick start guide (5 minutes)
- Personal vs Enterprise comparison
- Personal Edition installation
- Enterprise Edition installation
- Upgrading to Enterprise instructions
- CLI command reference
- Environment variables reference
- Troubleshooting section
- Development installation
- Uninstallation guide
  </done>
</task>

<task type="auto">
  <name>Create feature matrix documentation</name>
  <files>docs/FEATURE_MATRIX.md</files>
  <action>
Create docs/FEATURE_MATRIX.md (200-250 lines):

```markdown
# Atom Feature Matrix

> **Compare Personal and Enterprise editions**

| Feature | Personal | Enterprise | Description |
|---------|----------|------------|-------------|
| **Price** | Free | Paid | Licensing |
| **Users** | 1 | Unlimited | User seats |
| **Support** | Community | Priority | Support level |

---

## Core Features

| Feature | Personal | Enterprise |
|---------|----------|------------|
| Local Agent Execution | ✅ | ✅ |
| Workflow Automation | ✅ | ✅ |
| Canvas Presentations | ✅ | ✅ |
| Browser Automation | ✅ | ✅ |
| Episodic Memory | ✅ | ✅ |
| Agent Governance | ✅ | ✅ |
| Agent Graduation | ✅ | ✅ |
| Community Skills | ✅ | ✅ (5,000+ skills) |
| Telegram Connector | ✅ | ✅ |
| Vector Embeddings (Local) | ✅ | ✅ |

---

## Collaboration Features

| Feature | Personal | Enterprise |
|---------|----------|------------|
| Multi-User | ❌ | ✅ |
| Workspace Isolation | ❌ | ✅ |
| Team Sharing | ❌ | ✅ |
| Role-Based Access Control | ❌ | ✅ |
| Agent Collaboration | ✅ | ✅ |
| Social Feed | ✅ | ✅ |

---

## Integration Features

| Feature | Personal | Enterprise |
|---------|----------|------------|
| Gmail Integration | ✅ | ✅ |
| Slack Integration | ✅ | ✅ |
| Telegram Bot | ✅ | ✅ |
| Webhooks | ✅ | ✅ |
| API Access | ✅ | ✅ |
| Custom Integrations | ✅ | ✅ |

---

## Enterprise Features

| Feature | Personal | Enterprise |
|---------|----------|------------|
| PostgreSQL Database | ❌ | ✅ |
| Multi-User Support | ❌ | ✅ |
| Workspace Isolation | ❌ | ✅ |
| SSO (Okta, Auth0, SAML) | ❌ | ✅ |
| Audit Trail | Basic | Full |
| Monitoring | Basic | Prometheus + Grafana |
| Advanced Analytics | ❌ | ✅ |
| BI Dashboard | ❌ | ✅ |
| Rate Limiting | ❌ | ✅ |
| Priority Support | ❌ | ✅ |
| SLA | ❌ | ✅ |

---

## Feature Details

### Local Agent Execution

Run AI agents on your local machine with governance controls.

**Personal:** Single agent, local execution
**Enterprise:** Multiple agents, distributed execution

### Workflow Automation

Create visual workflows with triggers, actions, and conditions.

**Personal:** 10 workflows max
**Enterprise:** Unlimited workflows

### Canvas Presentations

Rich interactive presentations with charts, forms, and sheets.

**Personal:** 5 concurrent canvases
**Enterprise:** Unlimited canvases

### Browser Automation

Web scraping, form filling, screenshots via Playwright CDP.

**Personal:** 1 browser session
**Enterprise:** 10 concurrent sessions

### Episodic Memory

Agents remember and learn from past interactions.

**Personal:** 1000 episodes max
**Enterprise:** Unlimited episodes

### Agent Governance

Maturity levels (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) with permissions.

**Personal:** Manual promotion
**Enterprise:** Auto-graduation with compliance validation

### Community Skills

Import 5,000+ OpenClaw/ClawHub community skills with security sandbox.

**Personal:** Untrusted skills require approval
**Enterprise:** LLM security scanning + governance

### Vector Embeddings

Semantic search and memory retrieval.

**Personal:** FastEmbed (local, 384-dim)
**Enterprise:** OpenAI/Cohere (cloud, higher dim)

### Multi-User Support

Multiple users with separate workspaces.

**Personal:** Not available
**Enterprise:** Unlimited users

### SSO Integration

Single sign-on with Okta, Auth0, or SAML.

**Personal:** Not available
**Enterprise:** All providers

### Monitoring

Application metrics and dashboards.

**Personal:** Basic logging
**Enterprise:** Prometheus metrics + Grafana dashboards

### Audit Trail

Compliance logging for all agent actions.

**Personal:** Local logs only
**Enterprise:** Structured audit logs, 90-day retention

### Advanced Analytics

Workflow performance analytics and BI dashboards.

**Personal:** Not available
**Enterprise:** Full analytics suite

---

## Edition Comparison by Use Case

### Personal Use

**Best for:** Individuals, students, researchers

**Features:**
- Local automation
- Agent experimentation
- Learning AI governance
- Privacy-focused (data stays local)

**Limitations:**
- Single user
- SQLite database (not production-ready)
- No SSO
- Basic monitoring

### Small Teams

**Best for:** Startups, small teams

**Features:**
- Multi-user support
- Workspace isolation
- Team sharing
- PostgreSQL database

**Limitations:**
- No SSO
- No advanced analytics

### Enterprise

**Best for:** Large organizations, regulated industries

**Features:**
- Everything in Small Teams
- SSO integration
- Full monitoring stack
- Compliance audit trail
- Advanced analytics
- Priority support
- SLA guarantees

---

## Feature Flag API

Programmatically check feature availability:

```python
from core.package_feature_service import get_package_feature_service, Feature

service = get_package_feature_service()

# Check edition
if service.is_enterprise:
    print("Enterprise features available")

# Check specific feature
if service.is_feature_enabled(Feature.MULTI_USER):
    print("Multi-user support available")

# Require feature (raises error if not available)
service.require_feature(Feature.SSO)
```

---

## Upgrading Editions

### Personal → Enterprise

```bash
# Via CLI
atom enable enterprise

# Via API
curl -X POST http://localhost:8000/api/edition/enable \\
    -H "Content-Type: application/json" \\
    -d '{"database_url": "postgresql://..."}'
```

**What changes:**
- ATOM_EDITION=personal → ATOM_EDITION=enterprise
- SQLite → PostgreSQL
- Single-user → Multi-user
- Basic → Full monitoring

**Migration required:**
- Export SQLite database
- Import to PostgreSQL
- Update DATABASE_URL in .env
- Restart Atom

---

## See Also

- [Installation Guide](INSTALLATION.md)
- [Personal Edition Guide](PERSONAL_EDITION.md)
- [Package Feature Service API](../backend/core/package_feature_service.py)
```

Feature matrix comparing all Personal vs Enterprise features.
  </action>
  <verify>
```bash
# Verify feature matrix created
test -f docs/FEATURE_MATRIX.md
grep -n "Personal\|Enterprise" docs/FEATURE_MATRIX.md
grep -n "SSO\|Monitoring\|Multi-User" docs/FEATURE_MATRIX.md
```
  </verify>
  <done>
FEATURE_MATRIX.md created with:
- Core features comparison
- Collaboration features
- Integration features
- Enterprise-only features
- Feature details with descriptions
- Use case recommendations
- Feature flag API documentation
- Upgrade instructions
  </done>
</task>

<task type="auto">
  <name>Create PyPI publishing workflow</name>
  <files>.github/workflows/publish.yml</files>
  <action>
Create .github/workflows/publish.yml (150-200 lines):

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*.*.*'
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to publish (e.g., 0.1.0)'
        required: true
        type: string

permissions:
  contents: read
  # Required for Trusted Publishing
  id-token: write

jobs:
  build:
    name: Build distribution packages
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install build twine

      - name: Build package
        run: |
          cd backend
          python -m build

      - name: Check package
        run: |
          twine check backend/dist/*

      - name: Store distribution packages
        uses: actions/upload-artifact@v4
        with:
          name: python-package-distributions
          path: backend/dist/

  publish-test:
    name: Publish to TestPyPI
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'workflow_dispatch'

    steps:
      - name: Download distribution packages
        uses: actions/download-artifact@v4
        with:
          name: python-package-distributions
          path: backend/dist/

      - name: Publish to TestPyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/
          packages-dir: backend/dist/

  publish-production:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    # Only publish tags on main branch
    if: |
      github.event_name == 'push' &&
      github.ref_type == 'tag' &&
      startsWith(github.ref, 'refs/tags/v')

    steps:
      - name: Download distribution packages
        uses: actions/download-artifact@v4
        with:
          name: python-package-distributions
          path: backend/dist/

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: backend/dist/
          skip-existing: true

  verify:
    name: Verify installation
    needs: publish-production
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref_type == 'tag'

    steps:
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install from PyPI
        run: |
          # Wait for package to be available (PyPI can take a few minutes)
          sleep 120
          pip install atom-os

      - name: Verify CLI
        run: |
          atom-os --version
          atom-os --help

      - name: Verify imports
        run: |
          python -c "from core.package_feature_service import get_package_feature_service; print('✓ PackageFeatureService')"
          python -c "from cli.main import main_cli; print('✓ CLI main')"

      - name: Test init command
        run: |
          atom init --no-input
          test -f .env

      - name: Check edition
        run: |
          python -c "
          from core.package_feature_service import get_package_feature_service
          service = get_package_feature_service()
          print(f'Edition: {service.edition.value}')
          print(f'Features: {len(service.get_available_features())}')
          "

  notify:
    name: Notify on success/failure
    needs: [build, publish-production, verify]
    runs-on: ubuntu-latest
    if: always()

    steps:
      - name: Check job statuses
        run: |
          if [ "${{ needs.publish-production.result }}" == "success" ]; then
            echo "✓ Published successfully to PyPI"
          else
            echo "✗ Publishing failed"
            exit 1
          fi
```

Key features:
- Trusted Publishing (OIDC) - no API tokens needed
- Separate TestPyPI workflow for testing
- Tag-based releases (v*)
- Manual workflow dispatch for testing
- Build verification
- Installation verification after publish
  </action>
  <verify>
```bash
# Verify workflow created
test -f .github/workflows/publish.yml
grep -n "pypa/gh-action-pypi-publish" .github/workflows/publish.yml
grep -n "id-token: write" .github/workflows/publish.yml
grep -n "on: push: tags:" .github/workflows/publish.yml
```
  </verify>
  <done>
publish.yml created with:
- Trigger on version tags (v*)
- Manual workflow dispatch for testing
- Trusted Publishing (OIDC) - no API tokens
- TestPyPI publishing for testing
- PyPI production publishing
- Build verification with twine
- Installation verification after publish
- Success/failure notification
  </done>
</task>

<task type="auto">
  <name>Create MANIFEST.in for package data files</name>
  <files>MANIFEST.in</files>
  <action>
Create MANIFEST.in in project root (50-80 lines):

```manifest
# MANIFEST.in for atom-os package
# Specifies which files to include in the distribution

# Include README
include README.md
include LICENSE

# Include documentation
recursive-include docs *.md *.txt

# Include configuration files
include .env.example
include .env.personal
include docker-compose.yml
include docker-compose-personal.yml

# Include Alembic migrations
recursive-include backend/alembic *.py
include backend/alembic.ini

# Include CLI
include backend/cli/*.py

# Include tests (for verification)
recursive-include backend/tests *.py

# Include data files
recursive-include backend/data *

# Exclude development files
exclude .gitignore
exclude .env
exclude .env.*
exclude .coverage
exclude coverage.xml
exclude htmlcov/
exclude .pytest_cache/
exclude .mypy_cache/
exclude __pycache__/
exclude *.pyc
exclude *.pyo
exclude .DS_Store

# Exclude test archives
exclude-also backend/test_archives*

# Exclude venv
exclude-also venv/
exclude-also backend/venv/

# Exclude node_modules
exclude-also node_modules/
exclude-also frontend-nextjs/node_modules/
exclude-also mobile/node_modules/

# Exclude build artifacts
exclude-also build/
exclude-also dist/
exclude-also *.egg-info/
exclude-also .next/
exclude-again *.log
```

This ensures all necessary files are included in the PyPI package while excluding development artifacts.
  </action>
  <verify>
```bash
# Verify MANIFEST.in created
test -f MANIFEST.in
grep -n "include README.md" MANIFEST.in
grep -n "recursive-include" MANIFEST.in
grep -n "exclude" MANIFEST.in
```
  </verify>
  <done>
MANIFEST.in created with:
- README and LICENSE included
- Documentation included
- Configuration files included
- CLI files included
- Alembic migrations included
- Development files excluded
- Test data excluded
- Build artifacts excluded
  </done>
</task>

<task type="auto">
  <name>Update README with quick start</name>
  <files>README.md</files>
  <action>
Update README.md to add quick start with pip install.

Add after the title/badge section:

```markdown
## Quick Start

```bash
# Install Atom
pip install atom-os

# Initialize
atom init

# Add your API keys to .env
# OPENAI_API_KEY=sk-...

# Start Atom
atom start

# Open dashboard
open http://localhost:8000
```

That's it! 🚀

**Choose your edition:**
- **Personal Edition** - Free, single-user, SQLite (default)
- **Enterprise Edition** - Multi-user, PostgreSQL, monitoring → `pip install atom-os[enterprise]`

[Full Installation Guide →](docs/INSTALLATION.md)
```

Also add a "Personal Edition" section before the architecture section:

```markdown
## Personal Edition

Atom offers a **Personal Edition** that's free and perfect for:

- Personal productivity automation
- AI agent experimentation
- Local development
- Privacy-focused automation (data never leaves your machine)

**What's included:**
- Local agent execution
- Workflow automation
- Canvas presentations
- Browser automation
- Episodic memory
- Agent governance
- Community skills (5,000+ OpenClaw/ClawHub)

**What's NOT included** (Enterprise features):
- Multi-user support
- PostgreSQL database
- SSO (Okta, Auth0, SAML)
- Advanced monitoring
- Audit trail
- Rate limiting

[Full Feature Matrix →](docs/FEATURE_MATRIX.md)

### Install Personal Edition

```bash
pip install atom-os
atom init
atom start
```

### Upgrade to Enterprise

```bash
atom enable enterprise
```

[Personal Edition Guide →](docs/PERSONAL_EDITION.md)
```

These additions provide a clear quick start and Personal Edition introduction.
  </action>
  <verify>
```bash
# Verify README updated
grep -n "pip install atom-os" README.md
grep -n "Personal Edition" README.md
grep -n "atom init" README.md
grep -n "atom enable enterprise" README.md
```
  </verify>
  <done>
README.md updated with:
- Quick start section at top
- pip install atom-os command
- Personal Edition overview
- Enterprise upgrade instructions
- Links to full documentation
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. INSTALLATION.md exists with comprehensive installation guide
2. FEATURE_MATRIX.md exists with edition comparison
3. README.md has quick start with pip install
4. publish.yml workflow exists with Trusted Publishing
5. MANIFEST.in includes all necessary files
6. Documentation covers Personal to Enterprise upgrade
7. CLI commands documented (init, start, enable)
8. Environment variables documented
9. Troubleshooting section included
10. Development installation documented
</verification>

<success_criteria>
- INSTALLATION.md covers Personal and Enterprise installation
- FEATURE_MATRIX.md compares all features by edition
- README.md quick start works (pip install atom-os → atom init → atom start)
- GitHub Actions workflow publishes to PyPI on version tags
- Trusted Publishing configured (OIDC, no API tokens)
- MANIFEST.in includes all necessary package files
- Documentation covers upgrade path from Personal to Enterprise
</success_criteria>

<output>
After completion, create `.planning/phases/04-installer/04-installer-03-SUMMARY.md` with:
- Files created/modified
- Installation guide sections
- Feature matrix structure
- PyPI publishing workflow
- Documentation links
</output>
