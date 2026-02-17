---
phase: 04-installer
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/cli/main.py
  - backend/cli/init.py
  - backend/cli/enable.py
  - backend/core/__init__.py
  - backend/api/edition_routes.py
  - backend/tests/test_cli_commands.py
autonomous: true

must_haves:
  truths:
    - atom init command creates Personal Edition configuration
    - atom start command starts Atom with detected edition
    - atom enable enterprise command enables Enterprise features
    - Edition routes show current edition and available features
    - CLI respects ATOM_EDITION environment variable
    - Personal Edition uses SQLite by default
    - Enterprise Edition uses PostgreSQL when enabled
  artifacts:
    - path: backend/cli/init.py
      provides: CLI init command for Personal Edition setup
      min_lines: 50
      exports: ["init_command"]
    - path: backend/cli/enable.py
      provides: CLI enable command for Enterprise features
      min_lines: 50
      exports: ["enable_command"]
    - path: backend/api/edition_routes.py
      provides: REST API for edition management
      contains: "GET /api/edition", "POST /api/edition/enable"
  key_links:
    - from: "backend/cli/main.py"
      to: "backend/cli/init.py"
      via: "init command group"
      pattern: "@main_cli.command.*init"
    - from: "backend/cli/main.py"
      to: "backend/cli/enable.py"
      via: "enable command group"
      pattern: "@main_cli.command.*enable"
    - from: "backend/api/edition_routes.py"
      to: "backend/core/package_feature_service.py"
      via: "Feature service import"
      pattern: "from.*package_feature_service.*import"
---

<objective>
Implement CLI commands (init, start, enable) with Personal Edition setup and Enterprise enablement.

Purpose: atom init creates Personal config, atom enable enterprise upgrades to Enterprise
Output: CLI commands for edition management with helpful user guidance
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
@/Users/rushiparikh/.claude/get-shit-done/references/checkpoints.md
</execution_context>

<context>
@.planning/phases/04-installer/04-installer-01-PLAN.md
@.planning/ROADMAP.md
@.planning/STATE.md
@docs/PERSONAL_EDITION.md

# Existing CLI
@backend/cli/main.py
@backend/cli/daemon.py
</context>

<tasks>

<task type="auto">
  <name>Create CLI init command for Personal Edition</name>
  <files>backend/cli/init.py</files>
  <action>
Create backend/cli/init.py (150-200 lines):

```python
"""
Atom CLI - Init command for Personal Edition setup.

Creates initial configuration for Personal Edition:
- .env file with Personal defaults (SQLite)
- data/ directory for local storage
- Database initialization
- First run wizard
"""

import os
import sys
import click
import logging
from pathlib import Path
from datetime import datetime

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@click.command()
@click.option('--force', is_flag=True, help='Overwrite existing configuration')
@click.option('--edition', type=click.Choice(['personal', 'enterprise']), default='personal',
              help='Edition to initialize (default: personal)')
@click.option('--database-url', help='Custom database URL (default: SQLite for personal)')
@click.option('--no-input', is_flag=True, help='Run non-interactively')
def init(force: bool, edition: str, database_url: str, no_input: bool):
    """
    Initialize Atom Personal Edition configuration.

    Creates .env file with Personal Edition defaults:
    - SQLite database (./data/atom.db)
    - Local filesystem storage
    - Minimal feature set

    **Examples:**
        atom init                          # Interactive setup
        atom init --edition personal        # Personal Edition
        atom init --edition enterprise      # Enterprise Edition
        atom init --force                  # Overwrite existing
        atom init --no-input               # Use all defaults

    **Enterprise Edition:**
        atom init --edition enterprise \\
            --database-url "postgresql://user:pass@localhost/atom"
    """
    click.echo(click.style("Atom Initialization", bold=True))
    click.echo("=" * 50)

    # Check if already initialized
    env_file = Path(".env")
    if env_file.exists() and not force:
        click.echo(click.style("⚠️  Configuration already exists!", fg="yellow"))
        click.echo("Use --force to overwrite")

        # Show current status
        from core.package_feature_service import get_package_feature_service
        service = get_package_feature_service()

        click.echo("")
        click.echo(f"Current Edition: {service.edition.value}")
        click.echo(f"Database: {os.getenv('DATABASE_URL', 'Not configured')}")

        raise SystemExit(1)

    # Edition-specific defaults
    if edition == "personal":
        _init_personal_edition(database_url, no_input)
    else:
        _init_enterprise_edition(database_url, no_input, force)

    # Success message
    click.echo("")
    click.echo(click.style("✓ Initialization complete!", fg="green", bold=True))
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Edit .env and add your API keys:")
    click.echo("     OPENAI_API_KEY=sk-...")
    click.echo("     ANTHROPIC_API_KEY=sk-ant-...")
    click.echo("")
    click.echo("  2. Start Atom:")
    click.echo("     atom start")
    click.echo("")
    click.echo(f"  3. Open dashboard:")
    click.echo("     http://localhost:8000")


def _init_personal_edition(database_url: str, no_input: bool) -> None:
    """Initialize Personal Edition configuration."""
    click.echo("")
    click.echo(click.style("Setting up Personal Edition...", fg="blue"))

    # Create data directory
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    click.echo(f"  ✓ Created data directory: {data_dir}")

    # Generate encryption keys
    import secrets
    encryption_key = secrets.token_urlsafe(32)
    jwt_secret = secrets.token_urlsafe(32)

    # Set Personal Edition defaults
    env_content = f"""# Atom Personal Edition Configuration
# Generated: {datetime.now().isoformat()}

# Edition
ATOM_EDITION=personal

# Server
PORT=8000
HOST=0.0.0.0
WORKERS=1

# Database (SQLite - Personal Edition default)
DATABASE_URL=sqlite:///./data/atom.db

# Encryption Keys (auto-generated)
BYOK_ENCRYPTION_KEY={encryption_key}
JWT_SECRET_KEY={jwt_secret}

# LLM Providers (add your keys)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=

# Vector Embeddings (local - Personal Edition)
EMBEDDING_PROVIDER=fastembed
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5
LANCEDB_PATH=./data/lancedb

# Agent Governance
AGENT_MATURITY_DEFAULT=STUDENT
MAX_CONCURRENT_AGENTS=3

# Logging
LOG_LEVEL=INFO
STRUCTLOG_LEVEL=INFO

# Feature Flags (Personal Edition)
ATOM_MULTI_USER_ENABLED=false
ATOM_MONITORING_ENABLED=false
ATOM_SSO_ENABLED=false
"""

    # Use custom database URL if provided
    if database_url:
        env_content = env_content.replace(
            "DATABASE_URL=sqlite:///./data/atom.db",
            f"DATABASE_URL={database_url}"
        )

    # Write .env file
    env_file = Path(".env")
    env_file.write_text(env_content)
    click.echo(f"  ✓ Created .env file (Personal Edition)")

    # Create subdirectories
    (data_dir / "lancedb").mkdir(exist_ok=True)
    (data_dir / "uploads").mkdir(exist_ok=True)
    click.echo(f"  ✓ Created storage directories")

    # Show database info
    db_url = database_url or "sqlite:///./data/atom.db"
    click.echo(f"  ✓ Database: {db_url}")


def _init_enterprise_edition(database_url: str, no_input: bool, force: bool) -> None:
    """Initialize Enterprise Edition configuration."""
    click.echo("")
    click.echo(click.style("Setting up Enterprise Edition...", fg="blue"))

    # Prompt for database URL if not provided
    if not database_url and not no_input:
        click.echo("")
        click.echo("Enterprise Edition requires PostgreSQL.")
        database_url = click.prompt(
            "Enter PostgreSQL database URL",
            default="postgresql://atom:atom@localhost:5432/atom"
        )

    if not database_url:
        click.echo(click.style("Error: Database URL required for Enterprise", fg="red"), err=True)
        raise SystemExit(1)

    # Create data directory
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    click.echo(f"  ✓ Created data directory: {data_dir}")

    # Generate encryption keys
    import secrets
    encryption_key = secrets.token_urlsafe(32)
    jwt_secret = secrets.token_urlsafe(32)

    # Set Enterprise Edition defaults
    env_content = f"""# Atom Enterprise Edition Configuration
# Generated: {datetime.now().isoformat()}

# Edition
ATOM_EDITION=enterprise

# Server
PORT=8000
HOST=0.0.0.0
WORKERS=4

# Database (PostgreSQL - Enterprise Edition required)
DATABASE_URL={database_url}

# Encryption Keys (auto-generated)
BYOK_ENCRYPTION_KEY={encryption_key}
JWT_SECRET_KEY={jwt_secret}

# LLM Providers
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=

# Vector Embeddings (OpenAI for Enterprise)
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
LANCEDB_PATH=./data/lancedb

# Agent Governance
AGENT_MATURITY_DEFAULT=STUDENT
MAX_CONCURRENT_AGENTS=10

# Multi-User (Enterprise)
ATOM_MULTI_USER_ENABLED=true
ATOM_WORKSPACE_ISOLATION=true

# SSO (Enterprise)
ATOM_SSO_ENABLED=false
# SSO_PROVIDER=okta|auth0|saml
# OKTA_DOMAIN=
# OKTA_CLIENT_ID=
# AUTH0_DOMAIN=
# AUTH0_CLIENT_ID=

# Monitoring (Enterprise)
ATOM_MONITORING_ENABLED=true
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# Logging
LOG_LEVEL=INFO
STRUCTLOG_LEVEL=INFO
STRUCTLOG_JSON=true

# Redis (Enterprise - for multi-user pub/sub)
REDIS_URL=redis://localhost:6379/0

# Audit Trail (Enterprise)
ATOM_AUDIT_TRAIL_ENABLED=true
AUDIT_LOG_RETENTION_DAYS=90

# Rate Limiting (Enterprise)
ATOM_RATE_LIMITING_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
"""

    # Write .env file
    env_file = Path(".env")
    env_file.write_text(env_content)
    click.echo(f"  ✓ Created .env file (Enterprise Edition)")

    # Create subdirectories
    (data_dir / "lancedb").mkdir(exist_ok=True)
    (data_dir / "uploads").mkdir(exist_ok=True)
    (data_dir / "audit").mkdir(exist_ok=True)
    click.echo(f"  ✓ Created storage directories")

    # Warning about PostgreSQL
    click.echo("")
    click.echo(click.style("⚠️  PostgreSQL Setup Required:", fg="yellow"))
    click.echo("  1. Ensure PostgreSQL is installed and running")
    click.echo("  2. Create database: createdb atom")
    click.echo("  3. Or use connection string to existing database")
    click.echo("")
    click.echo("Current DATABASE_URL:")
    click.echo(f"  {database_url}")


def register_init_command(cli_group):
    """Register init command with CLI group."""
    cli_group.add_command(init)
```

Follow Atom CLI patterns:
- Click framework for commands
- Colored output for UX
- Helpful error messages
- Edition-specific initialization
  </action>
  <verify>
```bash
# Verify init command created
test -f backend/cli/init.py
grep -n "def init" backend/cli/init.py
grep -n "_init_personal_edition" backend/cli/init.py
grep -n "_init_enterprise_edition" backend/cli/init.py
```
  </verify>
  <done>
init command created with:
- Personal Edition initialization (SQLite, local storage)
- Enterprise Edition initialization (PostgreSQL, monitoring)
- Auto-generated encryption keys
- .env file creation with edition-specific defaults
- Data directory creation
- Helpful next steps
- register_init_command() for CLI integration
  </done>
</task>

<task type="auto">
  <name>Create CLI enable command for Enterprise features</name>
  <files>backend/cli/enable.py</files>
  <action>
Create backend/cli/enable.py (100-150 lines):

```python
"""
Atom CLI - Enable command for upgrading Personal to Enterprise.

Enables Enterprise Edition features:
- Sets ATOM_EDITION=enterprise
- Installs enterprise dependencies
- Updates configuration
- Migrates database if needed
"""

import os
import sys
import click
import logging
import subprocess
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@click.group()
def enable():
    """Enable Enterprise Edition features."""
    pass


@enable.command()
@click.option('--workspace-id', help='Workspace ID for enterprise setup')
@click.option('--database-url', help='PostgreSQL database URL')
@click.option('--skip-deps', is_flag=True, help='Skip installing dependencies')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def enterprise(workspace_id: str, database_url: str, skip_deps: bool, yes: bool):
    """
    Enable Enterprise Edition features.

    Upgrades Personal Edition to Enterprise:
    - Sets ATOM_EDITION=enterprise
    - Installs enterprise dependencies
    - Prompts for PostgreSQL configuration
    - Updates .env with enterprise settings

    **Examples:**
        atom enable enterprise                              # Interactive
        atom enable enterprise --yes                       # Skip confirmation
        atom enable enterprise --workspace-id acme-corp    # With workspace
        atom enable enterprise --database-url "postgresql://..."  # Custom DB

    **Post-Installation:**
        - Set up PostgreSQL database
        - Configure SSO providers (optional)
        - Enable monitoring (optional)
    """
    click.echo(click.style("Enterprise Edition Enable", bold=True))
    click.echo("=" * 50)

    # Check current edition
    from core.package_feature_service import get_package_feature_service

    service = get_package_feature_service()
    if service.is_enterprise:
        click.echo(click.style("✓ Enterprise Edition already enabled!", fg="green"))
        click.echo(f"Current edition: {service.edition.value}")
        return

    # Show what will change
    click.echo("")
    click.echo("This will enable Enterprise Edition features:")
    click.echo("  ✓ Multi-user support")
    click.echo("  ✓ Workspace isolation")
    click.echo("  ✓ SSO (Okta, Auth0, SAML)")
    click.echo("  ✓ Monitoring (Prometheus, Grafana)")
    click.echo("  ✓ Advanced analytics")
    click.echo("  ✓ Audit trail")
    click.echo("  ✓ Rate limiting")
    click.echo("")

    # Confirm if not --yes
    if not yes:
        if not click.confirm("Enable Enterprise Edition?"):
            click.echo("Cancelled.")
            raise SystemExit(0)

    # Install enterprise dependencies
    if not skip_deps:
        click.echo("")
        click.echo("Installing Enterprise dependencies...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", ".[enterprise]"],
                check=True,
                cwd=Path(__file__).parent.parent
            )
            click.echo(click.style("  ✓ Dependencies installed", fg="green"))
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"  ✗ Failed to install: {e}", fg="red"), err=True)
            click.echo("Run manually: pip install atom-os[enterprise]")
            raise SystemExit(1)

    # Update .env file
    env_file = Path(".env")
    if env_file.exists():
        _update_env_for_enterprise(env_file, database_url, workspace_id)
    else:
        click.echo(click.style("⚠️  .env file not found - run 'atom init' first", fg="yellow"))
        raise SystemExit(1)

    # Success
    click.echo("")
    click.echo(click.style("✓ Enterprise Edition enabled!", fg="green", bold=True))

    # Show next steps
    click.echo("")
    click.echo("Next steps:")
    if not database_url:
        click.echo("  1. Set up PostgreSQL database:")
        click.echo("     createdb atom")
        click.echo("     # Or update DATABASE_URL in .env")
    click.echo("  2. Restart Atom:")
    click.echo("     atom stop  # If running")
    click.echo("     atom start")
    click.echo("  3. Configure optional features:")
    click.echo("     - SSO: Update OKTA_* or AUTH0_* variables")
    click.echo("     - Monitoring: Access http://localhost:9090")
    click.echo("     - Redis: Set REDIS_URL for multi-user")


def _update_env_for_enterprise(env_file: Path, database_url: str, workspace_id: str) -> None:
    """Update .env file for Enterprise Edition."""
    content = env_file.read_text()

    # Update edition
    if "ATOM_EDITION=" in content:
        content = content.replace(
            "ATOM_EDITION=personal",
            "ATOM_EDITION=enterprise"
        )
    else:
        content = f"\nATOM_EDITION=enterprise\n{content}"

    # Update database URL if provided
    if database_url:
        if "DATABASE_URL=" in content:
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("DATABASE_URL="):
                    lines[i] = f"DATABASE_URL={database_url}"
                    break
            content = "\n".join(lines)
        else:
            content = f"\nDATABASE_URL={database_url}\n{content}"

    # Enable multi-user
    if "ATOM_MULTI_USER_ENABLED=" in content:
        content = content.replace(
            "ATOM_MULTI_USER_ENABLED=false",
            "ATOM_MULTI_USER_ENABLED=true"
        )
    else:
        content = "\nATOM_MULTI_USER_ENABLED=true\n" + content

    # Enable monitoring
    if "ATOM_MONITORING_ENABLED=" in content:
        content = content.replace(
            "ATOM_MONITORING_ENABLED=false",
            "ATOM_MONITORING_ENABLED=true"
        )
    else:
        content = "\nATOM_MONITORING_ENABLED=true\n" + content

    # Add workspace ID if provided
    if workspace_id:
        if "WORKSPACE_ID=" in content:
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("WORKSPACE_ID="):
                    lines[i] = f"WORKSPACE_ID={workspace_id}"
                    break
            content = "\n".join(lines)
        else:
            content = f"\nWORKSPACE_ID={workspace_id}\n{content}"

    # Write updated content
    env_file.write_text(content)
    click.echo("  ✓ Updated .env file")


@enable.command()
def features():
    """List available features and their edition requirements."""
    from core.package_feature_service import get_package_feature_service

    service = get_package_feature_service()

    click.echo(click.style("Atom Edition Features", bold=True))
    click.echo("=" * 50)
    click.echo(f"Current Edition: {service.edition.value.upper()}")
    click.echo("")

    # List features by edition
    click.echo(click.style("Personal Edition Features:", fg="blue"))
    for feature in service.get_personal_features():
        info = service.get_feature_info(feature)
        available = service.is_feature_enabled(feature)
        status = click.style("✓", fg="green") if available else click.style("✗", fg="red")
        click.echo(f"  {status} {info.name}: {info.description}")

    click.echo("")
    click.echo(click.style("Enterprise Edition Features:", fg="yellow"))
    for feature in service.get_enterprise_features():
        info = service.get_feature_info(feature)
        available = service.is_feature_enabled(feature)
        status = click.style("✓", fg="green") if available else click.style("✗", fg="red")
        click.echo(f"  {status} {info.name}: {info.description}")

    if not service.is_enterprise:
        click.echo("")
        click.echo("Enable Enterprise features:")
        click.echo("  atom enable enterprise")


def register_enable_command(cli_group):
    """Register enable command with CLI group."""
    cli_group.add_command(enable)
```

Follow Atom CLI patterns:
- Click group for subcommands
- Environment variable updates
- Dependency installation
- Helpful next steps
  </action>
  <verify>
```bash
# Verify enable command created
test -f backend/cli/enable.py
grep -n "def enable" backend/cli/enable.py
grep -n "def enterprise" backend/cli/enable.py
grep -n "def features" backend/cli/enable.py
```
  </verify>
  <done>
enable command created with:
- enable enterprise subcommand (upgrade Personal to Enterprise)
- enable features subcommand (list available features)
- .env file updates for edition change
- Enterprise dependency installation
- Workspace ID support
- Helpful next steps
- register_enable_command() for CLI integration
  </done>
</task>

<task type="auto">
  <name>Update CLI main.py to add init and enable commands</name>
  <files>backend/cli/main.py</files>
  <action>
Update backend/cli/main.py to register init and enable commands:

1. Add imports after existing imports:

```python
# Import edition commands
from cli.init import register_init_command
from cli.enable import register_enable_command
```

2. After local_agent command registration (around line 333), add:

```python
# Register edition management commands
register_init_command(main_cli)
register_enable_command(main_cli)
```

3. Update the start command to check edition and show appropriate message.

Add this near the top of the start function (after docstring):

```python
    # Check edition
    from core.package_feature_service import get_package_feature_service
    service = get_package_feature_service()

    edition_display = "Personal Edition" if service.is_personal else "Enterprise Edition"
    click.echo(click.style(f"🎯 {edition_display}", fg="blue" if service.is_personal else "yellow"))
```

These changes integrate init and enable commands into the main CLI.
  </action>
  <verify>
```bash
# Verify main.py updated
grep -n "from cli.init import" backend/cli/main.py
grep -n "from cli.enable import" backend/cli/main.py
grep -n "register_init_command" backend/cli/main.py
grep -n "register_enable_command" backend/cli/main.py
```
  </verify>
  <done>
main.py updated with:
- Imports for init and enable command modules
- Command registration for init and enable
- Edition display in start command
- Integration with PackageFeatureService
  </done>
</task>

<task type="auto">
  <name>Create edition API routes</name>
  <files>backend/api/edition_routes.py</files>
  <action>
Create backend/api/edition_routes.py (150-200 lines):

```python
"""
Edition Routes - REST API for Personal/Enterprise edition management.

Endpoints:
- GET /api/edition - Get current edition and features
- POST /api/edition/enable - Enable Enterprise features
- GET /api/edition/features - List all features with availability
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from core.models import get_db
from core.package_feature_service import (
    get_package_feature_service,
    Feature,
    Edition
)

router = APIRouter(prefix="/api/edition", tags=["Edition"])


class EditionInfo(BaseModel):
    """Current edition information."""
    edition: str  # "personal" or "enterprise"
    is_enterprise: bool
    database_url: Optional[str]
    features_enabled: int
    features_total: int


class FeatureInfo(BaseModel):
    """Feature information."""
    id: str
    name: str
    description: str
    available: bool
    edition: str
    dependencies: List[str]


class FeaturesList(BaseModel):
    """List of features."""
    features: List[FeatureInfo]
    edition: str
    available_count: int
    total_count: int


class EnableEnterpriseRequest(BaseModel):
    """Request to enable Enterprise edition."""
    database_url: Optional[str] = None
    workspace_id: Optional[str] = None
    skip_dependencies: bool = False


class EnableEnterpriseResponse(BaseModel):
    """Response from enabling Enterprise."""
    success: bool
    message: str
    requires_restart: bool
    next_steps: List[str]


@router.get("/info", response_model=EditionInfo)
async def get_edition_info():
    """
    Get current edition information.

    Returns:
    - Current edition (personal/enterprise)
    - Enterprise status
    - Database configuration
    - Feature counts
    """
    import os

    service = get_package_feature_service()

    # Count available features
    available = service.get_available_features()
    all_features = set(Feature)  # All defined features

    return EditionInfo(
        edition=service.edition.value,
        is_enterprise=service.is_enterprise,
        database_url=os.getenv("DATABASE_URL", "Not configured"),
        features_enabled=len(available),
        features_total=len(all_features)
    )


@router.get("/features", response_model=FeaturesList)
async def list_features():
    """
    List all features with availability status.

    Returns all features (Personal and Enterprise) with:
    - Feature ID, name, description
    - Availability in current edition
    - Edition requirement
    - Dependencies
    """
    service = get_package_feature_service()

    features = service.list_features()
    available = [f for f in features if f["available"]]

    return FeaturesList(
        features=features,
        edition=service.edition.value,
        available_count=len(available),
        total_count=len(features)
    )


@router.get("/features/{feature_id}")
async def get_feature_info(feature_id: str):
    """
    Get detailed information about a specific feature.

    Args:
        feature_id: Feature ID (e.g., "multi_user", "sso")

    Returns:
        Feature metadata and availability
    """
    service = get_package_feature_service()

    try:
        feature = Feature(feature_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown feature: {feature_id}"
        )

    info = service.get_feature_info(feature)
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"Feature metadata not found: {feature_id}"
        )

    return {
        "id": feature_id,
        "name": info.name,
        "description": info.description,
        "edition": info.edition.value,
        "dependencies": [d.value for d in info.dependencies],
        "available": service.is_feature_enabled(feature)
    }


@router.post("/enable", response_model=EnableEnterpriseResponse)
async def enable_enterprise(
    request: EnableEnterpriseRequest
):
    """
    Enable Enterprise Edition features.

    This endpoint provides programmatic access to enable Enterprise features.
    Equivalent to running: atom enable enterprise

    **Note:** After enabling, restart the Atom service for changes to take effect.

    Args:
        request: Enterprise enable request with optional database URL

    Returns:
        Success status, message, restart requirement, next steps
    """
    service = get_package_feature_service()

    if service.is_enterprise:
        return EnableEnterpriseResponse(
            success=True,
            message="Enterprise Edition is already enabled",
            requires_restart=False,
            next_steps=["Configure enterprise features in .env"]
        )

    # In a real implementation, this would:
    # 1. Install enterprise dependencies
    # 2. Update .env file
    # 3. Update database schema if needed

    # For now, return instructions
    next_steps = [
        "Run: atom enable enterprise",
        "Or install dependencies: pip install atom-os[enterprise]",
        "Update .env: ATOM_EDITION=enterprise",
        "Restart Atom service"
    ]

    if request.database_url:
        next_steps.insert(0, f"Set DATABASE_URL={request.database_url}")

    return EnableEnterpriseResponse(
        success=False,
        message="Use CLI to enable Enterprise: atom enable enterprise",
        requires_restart=True,
        next_steps=next_steps
    )


@router.get("/check/{feature_id}")
async def check_feature(feature_id: str):
    """
    Check if a specific feature is enabled.

    Args:
        feature_id: Feature ID to check

    Returns:
        Feature availability status
    """
    service = get_package_feature_service()

    try:
        feature = Feature(feature_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown feature: {feature_id}"
        )

    available = service.is_feature_enabled(feature)
    info = service.get_feature_info(feature)

    return {
        "feature": feature_id,
        "name": info.name if info else feature_id,
        "available": available,
        "edition_required": info.edition.value if info else "unknown",
        "enable_command": f"atom enable enterprise" if not available else None
    }


def register_edition_routes(app):
    """Register edition routes with FastAPI app."""
    app.include_router(router)
```

Follow Atom API patterns:
- FastAPI router with tags
- Pydantic models for request/response
- Type hints and docstrings
- Error handling with HTTPException
  </action>
  <verify>
```bash
# Verify edition routes created
test -f backend/api/edition_routes.py
grep -n "GET /api/edition" backend/api/edition_routes.py
grep -n "POST /api/edition/enable" backend/api/edition_routes.py
grep -n "class EditionInfo" backend/api/edition_routes.py
```
  </verify>
  <done>
edition_routes.py created with:
- GET /api/edition/info - Current edition information
- GET /api/edition/features - List all features
- GET /api/edition/features/{id} - Feature details
- POST /api/edition/enable - Enable Enterprise
- GET /api/edition/check/{id} - Check feature availability
- Pydantic models for type safety
- register_edition_routes() for app integration
  </done>
</task>

<task type="auto">
  <name>Register edition routes in main app</name>
  <files>backend/core/__init__.py, backend/main_api_app.py</files>
  <action>
Register edition routes with FastAPI app.

Edit backend/main_api_app.py (or backend/core/__init__.py if that's where app is defined):

1. Add import near top of file:

```python
# Edition management
from api.edition_routes import register_edition_routes
```

2. After app initialization, register routes:

```python
# Register edition routes
register_edition_routes(app)
```

If using a centralized route registration pattern, add edition_routes to the list.

Note: The exact location depends on how main_api_app.py is structured. Look for where other API routes are registered (canvas_routes, browser_routes, etc.) and follow the same pattern.
  </action>
  <verify>
```bash
# Verify routes registered
grep -n "register_edition_routes\|edition_routes" backend/main_api_app.py || grep -n "register_edition_routes\|edition_routes" backend/core/__init__.py
```
  </verify>
  <done>
edition_routes registered with:
- Import of register_edition_routes function
- Route registration in app initialization
- Edition endpoints available at /api/edition/*
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. init.py exists with init command for Personal Edition
2. enable.py exists with enable enterprise command
3. main.py imports and registers init and enable commands
4. edition_routes.py exists with edition API endpoints
5. Edition routes registered in main app
6. atom init works (creates .env with Personal defaults)
7. atom enable enterprise works (upgrades to Enterprise)
8. Edition API returns current edition and features
</verification>

<success_criteria>
- atom init creates .env with ATOM_EDITION=personal
- atom init --edition enterprise creates .env with PostgreSQL
- atom enable enterprise upgrades Personal to Enterprise
- GET /api/edition/info returns current edition
- GET /api/edition/features lists all features with availability
- CLI commands show helpful error messages
- Next steps displayed after init/enable
</success_criteria>

<output>
After completion, create `.planning/phases/04-installer/04-installer-02-SUMMARY.md` with:
- Files created/modified
- CLI commands added (init, enable)
- Edition API endpoints
- User flow for Personal to Enterprise upgrade
</output>
