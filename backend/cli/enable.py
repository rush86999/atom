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
        click.echo(click.style("Enterprise Edition already enabled!", fg="green"))
        click.echo(f"Current edition: {service.edition.value}")
        return

    # Show what will change
    click.echo("")
    click.echo("This will enable Enterprise Edition features:")
    click.echo("  Multi-user support")
    click.echo("  Workspace isolation")
    click.echo("  SSO (Okta, Auth0, SAML)")
    click.echo("  Monitoring (Prometheus, Grafana)")
    click.echo("  Advanced analytics")
    click.echo("  Audit trail")
    click.echo("  Rate limiting")
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
            click.echo(click.style("  Dependencies installed", fg="green"))
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"  Failed to install: {e}", fg="red"), err=True)
            click.echo("Run manually: pip install atom-os[enterprise]")
            raise SystemExit(1)

    # Update .env file
    env_file = Path(".env")
    if env_file.exists():
        _update_env_for_enterprise(env_file, database_url, workspace_id)
    else:
        click.echo(click.style(".env file not found - run 'atom init' first", fg="yellow"))
        raise SystemExit(1)

    # Success
    click.echo("")
    click.echo(click.style("Enterprise Edition enabled!", fg="green", bold=True))

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
    click.echo("  Updated .env file")


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
