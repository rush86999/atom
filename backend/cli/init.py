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
        click.echo(click.style("Configuration already exists!", fg="yellow"))
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
    click.echo(click.style("Initialization complete!", fg="green", bold=True))
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
    click.echo(f"  Created data directory: {data_dir}")

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
    click.echo(f"  Created .env file (Personal Edition)")

    # Create subdirectories
    (data_dir / "lancedb").mkdir(exist_ok=True)
    (data_dir / "uploads").mkdir(exist_ok=True)
    click.echo(f"  Created storage directories")

    # Show database info
    db_url = database_url or "sqlite:///./data/atom.db"
    click.echo(f"  Database: {db_url}")


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
    click.echo(f"  Created data directory: {data_dir}")

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
    click.echo(f"  Created .env file (Enterprise Edition)")

    # Create subdirectories
    (data_dir / "lancedb").mkdir(exist_ok=True)
    (data_dir / "uploads").mkdir(exist_ok=True)
    (data_dir / "audit").mkdir(exist_ok=True)
    click.echo(f"  Created storage directories")

    # Warning about PostgreSQL
    click.echo("")
    click.echo(click.style("PostgreSQL Setup Required:", fg="yellow"))
    click.echo("  1. Ensure PostgreSQL is installed and running")
    click.echo("  2. Create database: createdb atom")
    click.echo("  3. Or use connection string to existing database")
    click.echo("")
    click.echo("Current DATABASE_URL:")
    click.echo(f"  {database_url}")


def register_init_command(cli_group):
    """Register init command with CLI group."""
    cli_group.add_command(init)
