# Phase 4: Simplified Entry Point (pip install atom-os) - Research

**Researched:** February 16, 2026
**Domain:** Python Packaging, CLI Development, Feature Flags, PyPI Publishing
**Confidence:** HIGH

## Summary

Phase 4 aims to create a single-line installer (`pip install atom-os`) that provides a "Personal Edition" with simplified features (Local Agent + Telegram) while hiding enterprise features (multi-user, SSO, enterprise dashboard) until explicitly enabled. The research confirms that **pyproject.toml with setuptools** is the 2026 standard for Python packaging, **Typer** is the modern choice for CLI development (already uses Click), and **PyPI Trusted Publishing** eliminates API token management. Feature flags should be implemented via environment variables with a centralized PackageFeatureService, and SQLAlchemy's database-agnostic design allows seamless SQLite (Personal) to PostgreSQL (Enterprise) switching via connection URL only.

**Primary recommendation:** Use pyproject.toml with setuptools backend, implement environment-based feature flags with PackageFeatureService, structure package with `atom/` top-level module, publish via PyPI Trusted Publishers using GitHub Actions, and use Click (already in codebase) for CLI commands.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **setuptools** | >=70.0.0 | Build backend for pyproject.toml | Official Python Packaging Authority recommendation for 2026, battle-tested, extensive documentation |
| **build** | >=1.0.0 | Build wheel/sdist from pyproject.toml | Official Python packaging tool, replaces setup.py commands |
| **twine** | >=5.0.0 | Upload packages to PyPI | Official PyPI upload tool, verified for trusted publishing |
| **Click** | >=8.1.0 | CLI framework (already in requirements.txt) | Already used in Atom's CLI, mature, excellent documentation, Typer is built on Click |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **python-dotenv** | >=1.0.0 (already in requirements.txt) | Load .env files for feature flags | Personal Edition configuration |
| **pydantic-settings** | >=2.0.0 (already in requirements.txt) | Typed configuration management | Enterprise Edition validation |
| **sqlalchemy** | >=2.0.0 (already in requirements.txt) | Database abstraction layer | Already supports SQLite and PostgreSQL via connection URL |
| **alembic** | >=1.12.0 (already in requirements.txt) | Database migrations | Handle dialect-specific migrations |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **setuptools** | Poetry, Hatchling, Flit | Poetry adds dependency resolver overhead, Hatchling is newer but less documentation, Flit is simpler but less flexible for complex packages like Atom |
| **Click** | Typer, argparse, docopt | Typer is modern but adds dependency (built on Click anyway), argparse is stdlib but verbose, docopt is deprecated |
| **PyPI** | Private index, DevPI, Artifactory | Private index adds hosting cost, DevPI/Artifactory are overkill for open-source, PyPI has Trusted Publishing (no tokens) |

**Installation:**
```bash
# For package building (already in requirements.txt)
pip install build twine

# For development
pip install --editable .

# For production users
pip install atom-os
```

## Architecture Patterns

### Recommended Project Structure

```
atom-os/
├── pyproject.toml           # Package metadata and build config
├── README.md                # Public-facing README
├── LICENSE                  # MIT or Apache-2.0
├── MANIFEST.in              # Include non-Python files (templates, etc.)
├── atom/                    # Top-level package (renamed from backend/)
│   ├── __init__.py          # Package version and exports
│   ├── cli/                 # CLI commands (Click-based)
│   │   ├── __init__.py
│   │   ├── main.py          # Main CLI entry point
│   │   ├── daemon.py        # Daemon management
│   │   ├── local_agent.py   # Local agent commands
│   │   └── config.py        # Configuration commands
│   ├── core/                # Core services (shared)
│   │   ├── models.py        # SQLAlchemy models (database-agnostic)
│   │   ├── agent_governance_service.py
│   │   └── package_feature_service.py  # Feature flags
│   ├── local_agent/         # Personal + Enterprise
│   ├── im_adapters/         # Personal (Telegram) + Enterprise (WhatsApp)
│   ├── social_feed/         # Personal + Enterprise
│   ├── enterprise/          # Enterprise only (guarded by feature flags)
│   │   ├── multi_user/
│   │   ├── sso/
│   │   └── dashboard/
│   └── governance/          # Shared (always on)
├── tests/                   # Package tests
└── docs/                    # Documentation
```

### Pattern 1: pyproject.toml with setuptools (2026 Standard)

**What:** Use `pyproject.toml` with `[project]` table and `setuptools` build backend for modern Python packaging.

**When to use:** All new Python packages in 2026, replacing `setup.py` and `setup.cfg`.

**Example:**
```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=70.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "atom-os"
version = "1.0.0"
description = "Atom Agent OS - AI-powered business automation"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Atom Team", email = "team@atom.ai"}
]
keywords = ["automation", "ai", "agents", "cli"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "fastapi>=0.104.0,<1.0.0",
    "uvicorn>=0.24.0,<1.0.0",
    "sqlalchemy>=2.0.0,<3.0.0",
    "click>=8.1.0,<9.0.0",
    # ... (minimal dependencies only)
]

[project.optional-dependencies]
# Personal Edition: Local agent + Telegram + SQLite
personal = [
    "python-telegram-bot>=20.0",
    "aiosqlite>=0.19.0",
]

# Enterprise Edition: All features + PostgreSQL + Redis
enterprise = [
    "atom-os[personal]",
    "sqlalchemy>=2.0.0",  # For PostgreSQL dialect
    "psycopg2-binary>=2.9.0",
    "redis>=4.5.0",
    "celery>=5.0",
    "python3-saml>=1.14.0",  # SSO
    "PyWa>=2.0",  # WhatsApp
]

# Development dependencies
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "mypy>=1.8.0",
    "ruff>=0.1.0",
]

# All features (for development/testing)
all = ["atom-os[enterprise,dev]"]

[project.scripts]
atom = "atom.cli.main:main_cli"
atom-os = "atom.cli.main:main_cli"  # Alias

[project.urls]
Homepage = "https://github.com/rush86999/atom"
Documentation = "https://docs.atom.ai"
Repository = "https://github.com/rush86999/atom"
"Bug Tracker" = "https://github.com/rush86999/atom/issues"

[tool.setuptools]
package-dir = {"" = "."}

[tool.setuptools.packages.find]
where = ["."]
include = ["atom*"]
exclude = ["tests*", "docs*"]

[tool.setuptools.package-data]
"atom" = ["templates/*", "static/*"]
```

**Source:** [Python Packaging User Guide - Writing pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)

### Pattern 2: Feature Flags via PackageFeatureService

**What:** Centralized service that controls feature availability based on edition (personal vs. enterprise) and environment variables.

**When to use:** Controlling which features are available in Personal vs. Enterprise editions.

**Example:**
```python
# core/package_feature_service.py
from typing import Dict, Any
import os
from functools import lru_cache

class PackageFeatureService:
    """Centralized feature flag management for Atom OS editions."""

    # Feature definitions
    FEATURES: Dict[str, Dict[str, Any]] = {
        'local_agent': {
            'personal': True,
            'enterprise': True,
            'description': 'Local shell/file access with governance',
            'env_var': 'ATOM_FEATURE_LOCAL_AGENT',
        },
        'im_telegram': {
            'personal': True,
            'enterprise': True,
            'description': 'Telegram integration',
            'env_var': 'ATOM_FEATURE_IM_TELEGRAM',
        },
        'im_whatsapp': {
            'personal': False,  # Business verification required
            'enterprise': True,
            'description': 'WhatsApp integration',
            'env_var': 'ATOM_FEATURE_IM_WHATSAPP',
        },
        'social_feed': {
            'personal': True,
            'enterprise': True,
            'description': 'Agent-to-agent social layer',
            'env_var': 'ATOM_FEATURE_SOCIAL_FEED',
        },
        'multi_user': {
            'personal': False,
            'enterprise': True,
            'description': 'Multiple users per workspace',
            'env_var': 'ATOM_FEATURE_MULTI_USER',
        },
        'sso': {
            'personal': False,
            'enterprise': True,
            'description': 'SAML/Single Sign-On',
            'env_var': 'ATOM_FEATURE_SSO',
        },
        'enterprise_dashboard': {
            'personal': False,
            'enterprise': True,
            'description': 'Admin dashboard',
            'env_var': 'ATOM_FEATURE_ENTERPRISE_DASHBOARD',
        },
    }

    @classmethod
    @lru_cache(maxsize=1)
    def get_edition(cls) -> str:
        """Get current edition (personal or enterprise)."""
        # Check environment variable first
        edition = os.getenv('ATOM_EDITION', '').lower()
        if edition in ('enterprise', 'personal'):
            return edition

        # Auto-detect based on database
        db_url = os.getenv('DATABASE_URL', '')
        if 'postgres' in db_url or 'redis' in os.getenv('REDIS_URL', ''):
            return 'enterprise'

        # Default to personal
        return 'personal'

    @classmethod
    def is_enabled(cls, feature: str) -> bool:
        """Check if feature is enabled in current edition.

        Args:
            feature: Feature name from FEATURES dict

        Returns:
            True if feature is enabled, False otherwise

        Raises:
            ValueError: If feature name is unknown
        """
        if feature not in cls.FEATURES:
            raise ValueError(f"Unknown feature: {feature}")

        # Check environment variable override (force enable/disable)
        env_var = cls.FEATURES[feature]['env_var']
        env_value = os.getenv(env_var, '').lower()
        if env_value == 'true':
            return True
        if env_value == 'false':
            return False

        # Check edition-based availability
        edition = cls.get_edition()
        return cls.FEATURES[feature][edition]

    @classmethod
    def require_feature(cls, feature: str) -> None:
        """Raise exception if feature is not enabled.

        Args:
            feature: Feature name from FEATURES dict

        Raises:
            PermissionError: If feature is not enabled
        """
        if not cls.is_enabled(feature):
            edition = cls.get_edition()
            raise PermissionError(
                f"Feature '{feature}' is not available in {edition} edition. "
                f"Enable with: atom enable {feature} --edition=enterprise"
            )

    @classmethod
    def list_features(cls, edition: str | None = None) -> Dict[str, Dict[str, Any]]:
        """List all features and their availability.

        Args:
            edition: Filter by edition (personal/enterprise), None for all

        Returns:
            Dict of feature definitions with availability
        """
        result = {}
        for name, config in cls.FEATURES.items():
            if edition is None or config.get(edition, False):
                result[name] = {
                    **config,
                    'enabled': cls.is_enabled(name),
                }
        return result


# Usage example in CLI
# cli/main.py
from core.package_feature_service import PackageFeatureService

@click.group()
def main_cli():
    """Atom OS - AI-powered business automation platform."""
    pass

@main_cli.command()
@click.argument('feature')
@click.option('--edition', type=click.Choice(['personal', 'enterprise']))
def enable(feature: str, edition: str):
    """Enable a feature (e.g., 'atom enable enterprise')."""
    # Set environment variable
    os.environ[f'ATOM_FEATURE_{feature.upper()}'] = 'true'
    os.environ['ATOM_EDITION'] = edition or 'enterprise'
    click.echo(f"✓ Feature '{feature}' enabled")
```

### Pattern 3: SQLite ↔ PostgreSQL Compatibility with SQLAlchemy

**What:** Use SQLAlchemy's database-agnostic ORM to support both SQLite (Personal Edition) and PostgreSQL (Enterprise Edition) with identical codebase.

**When to use:** Personal Edition (SQLite) needs to be upgradable to Enterprise Edition (PostgreSQL) without code changes.

**Example:**
```python
# Database configuration (works for both editions)
# .env.personal (Personal Edition)
DATABASE_URL=sqlite:///./atom.db

# .env (Enterprise Edition)
DATABASE_URL=postgresql://user:pass@localhost:5432/atom

# Core code (database-agnostic)
# core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from os import getenv

def get_engine():
    """Create database engine (SQLite or PostgreSQL)."""
    database_url = getenv('DATABASE_URL', 'sqlite:///./atom.db')
    engine = create_engine(
        database_url,
        echo=False,
        # SQLite-specific: connect_args needed for thread safety
        connect_args={'check_same_thread': False} if 'sqlite' in database_url else {}
    )
    return engine

def get_session() -> Session:
    """Get database session (works for both SQLite and PostgreSQL)."""
    SessionLocal = sessionmaker(bind=get_engine())
    return SessionLocal()

# Models work identically for both databases
# core/models.py
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Agent(Base):
    __tablename__ = 'agents'

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    maturity_level = Column(String, default='STUDENT')
    created_at = Column(DateTime, server_default='func.now()')

# Usage (identical for both editions)
def create_agent(name: str):
    with get_session() as db:
        agent = Agent(name=name)
        db.add(agent)
        db.commit()
```

**Key Insight:** SQLAlchemy abstracts database differences. The **only** change needed between Personal and Enterprise is the `DATABASE_URL` environment variable.

**Source:** [StackOverflow - How to use the same code for both sqlite and postgres](https://stackoverflow.com/questions/75087464/how-to-use-the-same-code-for-both-sqlite-and-postgres)

### Pattern 4: PyPI Trusted Publishing with GitHub Actions

**What:** Use PyPI's Trusted Publishing (OIDC) to publish packages without managing API tokens.

**When to use:** Automated PyPI publishing from GitHub Actions CI/CD workflows.

**Example:**
```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*.*.*'  # Trigger on version tags (e.g., v1.0.0)

permissions:
  contents: read
  id-token: write  # Required for Trusted Publishing

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build package
        run: python -m build

      - name: Check distribution
        run: twine check dist/*

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          # NO password/token needed - uses OIDC
          skip-existing: true
          verbose: true
```

**PyPI Setup (One-Time):**
1. Go to https://pypi.org/manage/account/publishing/
2. Add "GitHub Actions" as a trusted publisher
3. Configure:
   - Owner: `rush86999`
   - Repository name: `atom`
   - Workflow name: `publish.yml`
   - Environment name: (leave blank)

**Key Benefit:** No API tokens to manage, no secrets in GitHub, automatic OIDC-based authentication.

**Source:** [PyPI Docs - Publishing with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)

### Anti-Patterns to Avoid

- **Don't use setup.py anymore** - pyproject.toml is the 2026 standard, setup.py is only for special cases (C extensions)
- **Don't hardcode edition checks** - Use PackageFeatureService, avoid `if EDITION == 'enterprise'` scattered throughout code
- **Don't create separate codebases** - Single codebase with feature flags, not `atom-personal` and `atom-enterprise` packages
- **Don't use PyPI API tokens** - Trusted Publishing is more secure, eliminates token rotation
- **Don't ignore database dialect differences** - Use Alembic for migrations, handle SQLite-specific limitations (e.g., no ALTER TABLE DROP COLUMN)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Feature Flags** | Custom environment variable parsing, scattered if/else | PackageFeatureService with centralized FEATURES dict | Single source of truth, easy to test, prevents inconsistency |
| **CLI Framework** | Custom argument parsing, help generation, command routing | Click (already in codebase) | Battle-tested, excellent documentation, auto-generated help |
| **Package Building** | Custom build scripts, manual wheel creation | `python -m build` with pyproject.toml | Official tool, handles wheel/sdist, compatible with all build backends |
| **PyPI Publishing** | Manual uploads, API token management | Trusted Publishing with GitHub Actions | No tokens, OIDC-based, secure by default |
| **Database Abstraction** | Separate SQLite/PostgreSQL code, manual connection handling | SQLAlchemy ORM (already in codebase) | Database-agnostic, mature, handles dialect differences |

**Key insight:** Python packaging has a **standard, well-documented stack** in 2026. Custom solutions introduce maintenance burden and security risks.

## Common Pitfalls

### Pitfall 1: PyPI Naming Conflicts

**What goes wrong:** Attempting to publish `atom-os` to PyPI but the name is already taken by another package.

**Why it happens:** PyPI package names are globally unique, first-come-first-served. "atom" is likely already taken.

**How to avoid:**
1. **Check availability early:** `pip search atom-os` (deprecated) or visit https://pypi.org/pypi/atom-os/json (404 = available)
2. **Have backup names:** `atom-agent-os`, `atom-ai`, `atom-automation`
3. **Use organization prefix:** If you have PyPI organization rights, use `orgname-atom-os`

**Warning signs:** If you get a 400 error during first publish attempt, name might be taken.

### Pitfall 2: Feature Flag Logic Duplication

**What goes wrong:** Multiple places in codebase checking `if os.getenv('ATOM_EDITION') == 'enterprise'`, inconsistent feature availability.

**Why it happens:** Developers add quick checks instead of using centralized service.

**How to avoid:**
1. **Mandate PackageFeatureService.is_enabled()** for all feature checks
2. **Code review rule:** Reject PRs that check EDITION directly
3. **Prevent with decorator:**
```python
# core/feature_guard.py
def require_feature(feature_name: str):
    """Decorator to check feature availability before function execution."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            PackageFeatureService.require_feature(feature_name)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Usage
@require_feature('sso')
def configure_saml_sso():
    # This function will raise PermissionError if SSO not enabled
    pass
```

**Warning signs:** Same feature check appears in multiple files, inconsistent error messages.

### Pitfall 3: SQLite Limitations in Enterprise Edition

**What goes wrong:** Personal Edition (SQLite) works fine, but Enterprise Edition (PostgreSQL) fails due to SQLite-specific code.

**Why it happens:** Using SQLite-specific features (e.g., `ON CONFLICT`, rowid) that don't translate to PostgreSQL.

**How to avoid:**
1. **Use SQLAlchemy ORM abstraction**, not raw SQL
2. **Test with both databases** in CI/CD:
```yaml
# .github/workflows/test.yml
jobs:
  test:
    strategy:
      matrix:
        database: [sqlite, postgresql]
    steps:
      - name: Test with ${{ matrix.database }}
        run: |
          if [ "${{ matrix.database }}" = "postgresql" ]; then
            export DATABASE_URL="postgresql://postgres:postgres@localhost/test"
          else
            export DATABASE_URL="sqlite:///./test.db"
          fi
          pytest tests/
```
3. **Use Alembic for migrations** (handles dialect differences):
```python
# alembic/versions/001_initial.py
def upgrade():
    # Alembic generates correct SQL for both SQLite and PostgreSQL
    op.create_table(
        'agents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
```

**Warning signs:** "sqlite3.OperationalError" or "psycopg2.errors.UndefinedFunction" in Enterprise tests.

### Pitfall 4: Missing Package Data

**What goes wrong:** Package installs successfully, but templates, static files, or config files are missing.

**Why it happens:** pyproject.toml doesn't include non-Python files in wheel.

**How to avoid:**
1. **Use MANIFEST.in** to explicitly include non-Python files:
```ini
# MANIFEST.in
include README.md
include LICENSE
recursive-include atom/templates *
recursive-include atom/static *
recursive-include atom/config *.json *.yaml
```
2. **Configure package-data in pyproject.toml:**
```toml
[tool.setuptools.package-data]
"atom" = ["templates/*", "static/*", "config/*.json"]
```
3. **Test wheel contents:**
```bash
python -m build
tar -tzf dist/atom-os-1.0.0.tar.gz | grep templates
```

**Warning signs:** "FileNotFoundError" when running installed package, but works in development.

### Pitfall 5: Trusted Publishing Misconfiguration

**What goes wrong:** GitHub Actions fails with "OIDC token not found" or "publisher not found".

**Why it happens:** PyPI publisher configuration doesn't match GitHub repository exactly (owner name, workflow name, environment).

**How to avoid:**
1. **Match configuration exactly:**
   - PyPI publisher owner: `rush86999` (exact GitHub username)
   - PyPI repository name: `atom` (exact repo name, not `Atom` or `ATOM`)
   - PyPI workflow name: `publish.yml` (exact filename, not `publish-pypi.yml`)
2. **Permissions in workflow:**
```yaml
permissions:
  id-token: write  # REQUIRED for OIDC
  contents: read
```
3. **Test with TestPyPI first:** https://test.pypi.org/ (same flow, non-production)

**Warning signs:** "OIDC token not found" in GitHub Actions logs.

## Code Examples

Verified patterns from official sources:

### Building and Publishing Package

```bash
# Source: https://packaging.python.org/tutorials/packaging-projects/

# 1. Build wheel and source distribution
python -m build

# 2. Check distributions
twine check dist/*

# 3. Publish to PyPI (with Trusted Publishing, NO password needed)
twine upload dist/* --skip-existing

# 4. Install from PyPI
pip install atom-os
pip install atom-os[enterprise]  # With enterprise dependencies
```

### CLI Command Structure

```python
# cli/main.py
import click
from atom.cli.daemon import daemon
from atom.cli.local_agent import local_agent

@click.group()
@click.version_option(version="1.0.0")
def main_cli():
    """Atom OS - AI-powered business automation platform."""
    pass

# Add command groups
main_cli.add_command(daemon)
main_cli.add_command(local_agent)

@main_cli.command()
@click.option('--edition', type=click.Choice(['personal', 'enterprise']), default='personal')
def init(edition: str):
    """Initialize Atom OS configuration."""
    click.echo(f"Initializing Atom OS ({edition} edition)...")
    # Create ~/.atom/config.json
    # Set ATOM_EDITION environment variable

@main_cli.command()
@click.option('--port', default=8000)
def start(port: int):
    """Start Atom OS server."""
    # Start uvicorn server
    pass

@main_cli.command()
@click.argument('feature')
@click.option('--edition', type=click.Choice(['personal', 'enterprise']))
def enable(feature: str, edition: str):
    """Enable a feature (e.g., 'atom enable enterprise')."""
    from atom.core.package_feature_service import PackageFeatureService
    os.environ[f'ATOM_FEATURE_{feature.upper()}'] = 'true'
    if edition:
        os.environ['ATOM_EDITION'] = edition
    click.echo(f"✓ Feature '{feature}' enabled")

if __name__ == '__main__':
    main_cli()
```

### Feature-Guarded Enterprise Feature

```python
# enterprise/sso.py
from atom.core.package_feature_service import PackageFeatureService
from atom.core.feature_guard import require_feature

@require_feature('sso')
def configure_saml_sso(metadata_url: str, cert_path: str):
    """Configure SAML 2.0 Single Sign-On (Enterprise only)."""
    # This function raises PermissionError if SSO feature not enabled
    from python3_saml import configure
    configure(metadata_url, cert_path)

# Usage in CLI
# cli/main.py
@main_cli.command()
@click.option('--metadata-url', required=True)
@click.option('--cert-path', required=True)
def configure_sso(metadata_url: str, cert_path: str):
    """Configure SAML SSO (Enterprise edition only)."""
    try:
        from atom.enterprise.sso import configure_saml_sso
        configure_saml_sso(metadata_url, cert_path)
        click.echo("✓ SAML SSO configured")
    except PermissionError as e:
        click.echo(click.style(f"✗ {e}", fg="red"))
        click.echo("Enable with: atom enable sso --edition=enterprise")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **setup.py** | **pyproject.toml with [project] table** | 2022 (PEP 621) | Standardized metadata, build backend agnostic |
| **API tokens for PyPI** | **Trusted Publishing (OIDC)** | 2023 | No token management, more secure, GitHub-native |
| **setuptools.setup() calls** | **Static metadata in pyproject.toml** | 2022-2024 | Faster builds, better IDE support, declarative |
| **Manual version management** | **Automated versioning via git tags** | 2023+ | `git tag v1.0.0` triggers publish, no manual edits |
| **Separate packages for editions** | **Single package with feature flags** | 2024+ | Simplified maintenance, unified codebase |

**Deprecated/outdated:**
- **setup.py**: Only for C extensions, dynamic versioning, or legacy support. Use pyproject.toml instead.
- **setup.cfg**: Replaced by pyproject.toml [project] table. Still valid for tool config (mypy, pytest, etc.)
- **PyPI API tokens**: Replaced by Trusted Publishing. Remove all tokens from GitHub Secrets.
- **`python setup.py sdist upload`**: Replaced by `python -m build && twine upload`

## Open Questions

1. **PyPI package name availability**
   - What we know: "atom" is likely taken, need to check "atom-os", "atom-agent-os"
   - What's unclear: Which names are actually available on PyPI
   - Recommendation: Check availability immediately with `curl https://pypi.org/pypi/atom-os/json` (404 = available), have backup names ready

2. **Enterprise feature installation mechanism**
   - What we know: Can use `pip install atom-os[enterprise]` for extra dependencies
   - What's unclear: Should we prompt users to run `atom enable enterprise` after installation, or auto-detect?
   - Recommendation: Auto-detect from DATABASE_URL (PostgreSQL = enterprise), manual `atom enable` for forcing edition

3. **WhatsApp Business Verification for Personal users**
   - What we know: WhatsApp Cloud API requires business verification
   - What's unclear: Can Personal Edition users use WhatsApp without business verification?
   - Recommendation: Personal = Telegram only (no verification), Enterprise = WhatsApp + Telegram (business verification required). This is already documented in FEATURE_ROADMAP.md.

4. **Migration path from Personal to Enterprise**
   - What we know: SQLAlchemy supports both databases, Alembic for migrations
   - What's unclear: How to migrate user data from SQLite to PostgreSQL seamlessly?
   - Recommendation: Provide `atom migrate-to-enterprise` CLI command that:
     1. Dumps SQLite database to JSON
     2. Prompts for PostgreSQL connection string
     3. Loads data into PostgreSQL
     4. Updates DATABASE_URL in config

## Sources

### Primary (HIGH confidence)

- **Python Packaging User Guide** - Writing pyproject.toml, modernizing setup.py projects, setuptools configuration
  - URL: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- **PyPI Official Documentation** - Trusted Publishing with OIDC, creating projects via OIDC
  - URL: https://docs.pypi.org/trusted-publishers/using-a-publisher/
- **SQLAlchemy Documentation** - Engine configuration, SQLite dialect, PostgreSQL dialect
  - URL: https://docs.sqlalchemy.org/en/latest/core/engines.html
- **Click Documentation** - API reference, patterns, examples (already in Atom codebase)
  - URL: https://click.palletsprojects.com/

### Secondary (MEDIUM confidence)

- **Python Packaging Best Practices: setuptools, Poetry, and Hatch in 2026** (dasroot.net, Jan 8 2026) - Compares build backends, emphasizes pyproject.toml
  - URL: https://dasroot.net/posts/2026/01/python-packaging-best-practices-setuptools-poetry-hatch/
- **PyOpenSci Guide: How to Secure Your Python Packages** (March 2025) - PyPI Trusted Publisher setup, sanitizing workflows
  - URL: https://www.pyopensci.org/blog/python-packaging-security-publish-pypi.html
- **StackOverflow: Same code for SQLite and PostgreSQL** - Community discussion on SQLAlchemy compatibility
  - URL: https://stackoverflow.com/questions/75087464/how-to-use-the-same-code-for-both-sqlite-and-postgres
- **Feature Flags Best Practices: Complete Guide (2026)** (designrevision.com, Feb 8 2026) - Implementation patterns, lifecycle management
  - URL: https://designrevision.com/blog/feature-flags-best-practices

### Tertiary (LOW confidence)

- **Medium: Python Packaging pyproject.toml** (Dec 27 2024) - Covers pyproject.toml basics, less comprehensive than official guide
  - URL: https://medium.com/towardsdev/python-packaging-pyproject-toml-50320189a06f
- **Dev.to: Trusted Publishing** (Dec 2024) - Overview of trusted publishing, lacks detailed examples
  - URL: https://dev.to/ldrscke/trusted-publishing-it-has-never-been-easier-to-publish-your-python-packages-3dfn
- **Feature flagging in Python: Best Practices - Statsig** (Oct 2024) - Vendor-specific guide (Statsig platform), biased toward their service
  - URL: https://www.statsig.com/perspectives/feature-flagging-python-best-practices

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Based on official Python Packaging Authority docs, PyPI docs, current 2026 best practices
- Architecture: HIGH - SQLAlchemy database-agnostic design verified via official docs and community discussion, Click already in codebase
- Pitfalls: HIGH - Common packaging pitfalls well-documented in official guides, PyPI docs, community discussions

**Research date:** February 16, 2026
**Valid until:** March 18, 2026 (30 days - Python packaging is stable, but PyPI naming availability changes rapidly)

**Key Recommendations for Planner:**
1. **Check PyPI name availability** immediately (`atom-os` vs. `atom-agent-os`)
2. **Use Click (not Typer)** since it's already in requirements.txt and codebase
3. **Single package with feature flags** (not `atom-personal` and `atom-enterprise` separate packages)
4. **SQLite ↔ PostgreSQL compatibility** requires no code changes, only DATABASE_URL environment variable
5. **PyPI Trusted Publishing** eliminates token management, use GitHub Actions for automated publishing on version tags
6. **PackageFeatureService** should be the single source of truth for feature availability, prevent scattered if/else checks
7. **Provide migration command** (`atom migrate-to-enterprise`) for Personal → Enterprise upgrade with data transfer
