#!/usr/bin/env python3
"""
Atom OS CLI - Command-line interface for Atom AI automation platform.

OpenClaw Integration: Single-command installer for "vibe coder" entry.
Full-featured Atom with optional host mount (governance-first).

Usage:
    pip install atom-os
    atom-os --help
"""

import os
import sys
import click
import logging
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def main_cli():
    """
    Atom OS - AI-powered business automation platform.

    Governance-first architecture with multi-agent system.
    """
    pass


@main_cli.command()
@click.option('--port', default=8000, help='Port for web server')
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--workers', default=1, help='Number of worker processes')
@click.option('--host-mount', is_flag=True, help='Enable host filesystem mount (Docker)')
@click.option('--dev', is_flag=True, help='Enable development mode (auto-reload)')
def start(port: int, host: str, workers: int, host_mount: bool, dev: bool):
    """
    Start Atom OS server.

    Starts FastAPI server with optional host filesystem mount.

    **Host Mount Warning:**
    This gives containers write access to host directories.
    Only enable after reviewing governance protections:
      - AUTONOMOUS maturity gate required for shell access
      - Command whitelist (ls, cat, grep, git, npm, etc.)
      - Blocked commands (rm, mv, chmod, kill, sudo, etc.)
      - 5-minute timeout enforcement
      - Full audit trail to ShellSession table

    **Examples:**
        atom-os                                    # Start on localhost:8000
        atom-os --port 3000 --dev                # Development mode with reload
        atom-os --host-mount                     # With host mount (requires confirmation)
    """
    # Import after CLI to avoid slow startup
    from main_api_app import app

    if host_mount:
        _confirm_host_mount()
        os.environ["ATOM_HOST_MOUNT_ENABLED"] = "true"

        # Configure host mount directories
        current_user = os.getenv("USER", "unknown")
        os.environ.setdefault(
            "ATOM_HOST_MOUNT_DIRS",
            f"/tmp:/Users/{current_user}/projects:/Users/{current_user}/Desktop:/Users/{current_user}/Documents"
        )

        click.echo(click.style("⚠️  Host filesystem mount ENABLED", fg="yellow", bold=True))
        click.echo("Governance protections active:")
        click.echo("  ✓ AUTONOMOUS maturity gate")
        click.echo("  ✓ Command whitelist")
        click.echo("  ✓ Blocked commands")
        click.echo("  ✓ 5-minute timeout")
        click.echo("  ✓ Audit trail")
        click.echo("")

    # Start server
    import uvicorn

    click.echo(click.style("🚀 Starting Atom OS...", fg="green", bold=True))
    click.echo(f"  Host: {host}")
    click.echo(f"  Port: {port}")
    click.echo(f"  Workers: {workers}")
    click.echo(f"  Dev mode: {dev}")
    click.echo(f"  Host mount: {host_mount}")
    click.echo("")
    click.echo(f"  Dashboard: http://{host}:{port}")
    click.echo(f"  API docs: http://{host}:{port}/docs")
    click.echo("")

    if dev:
        # Development mode with auto-reload
        uvicorn.run(
            "main_api_app:app",
            host=host,
            port=port,
            reload=True,
            log_level="info"
        )
    else:
        # Production mode
        uvicorn.run(
            "main_api_app:app",
            host=host,
            port=port,
            workers=workers,
            log_level="info",
            access_log=True
        )


@main_cli.command()
def status():
    """Show Atom OS status and configuration."""
    # Import after CLI to avoid slow startup
    from main_api_app import app

    click.echo(click.style("Atom OS Status", bold=True))
    click.echo("=" * 40)

    # Check host mount
    host_mount_enabled = os.getenv("ATOM_HOST_MOUNT_ENABLED", "false").lower() == "true"
    click.echo(f"Host mount: {click.style('ENABLED' if host_mount_enabled else 'disabled', fg='yellow' if host_mount_enabled else 'dim')}")

    # Check governance cache
    try:
        from core.governance_cache import get_governance_cache
        cache = get_governance_cache()
        click.echo(f"Governance cache: {click.style('connected', fg='green')}")
    except Exception as e:
        click.echo(f"Governance cache: {click.style('disconnected', fg='red')} ({e})")

    # Check database
    try:
        from core.models import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        click.echo(f"Database: {click.style('connected', fg='green')}")
    except Exception as e:
        click.echo(f"Database: {click.style('disconnected', fg='red')} ({e})")

    # Show configuration
    click.echo("")
    click.echo("Environment:")
    port = os.getenv("PORT", "8000")
    click.echo(f"  PORT: {port}")

    if host_mount_enabled:
        mount_dirs = os.getenv("ATOM_HOST_MOUNT_DIRS", "not configured")
        click.echo(f"  Host mount dirs: {mount_dirs}")


@main_cli.command()
def config():
    """Show configuration details and environment variables."""
    click.echo(click.style("Atom OS Configuration", bold=True))
    click.echo("=" * 40)
    click.echo("")
    click.echo("Environment Variables:")
    click.echo("")
    click.echo("Server:")
    click.echo("  PORT              - Server port (default: 8000)")
    click.echo("  HOST             - Server host (default: 0.0.0.0)")
    click.echo("  WORKERS          - Worker processes (default: 1)")
    click.echo("")
    click.echo("Host Mount (SECURITY WARNING):")
    click.echo("  ATOM_HOST_MOUNT_ENABLED  - Enable host filesystem mount")
    click.echo("  ATOM_HOST_MOUNT_DIRS     - Allowed directories (colon-separated)")
    click.echo("")
    click.echo("Database:")
    click.echo("  DATABASE_URL      - Database connection string")
    click.echo("")
    click.echo("LLM Providers:")
    click.echo("  OPENAI_API_KEY    - OpenAI API key")
    click.echo("  ANTHROPIC_API_KEY - Anthropic API key")
    click.echo("  DEEPSEEK_API_KEY  - DeepSeek API key")
    click.echo("")
    click.echo("See .env file for full configuration.")


def _confirm_host_mount():
    """Interactive confirmation for host mount."""
    click.echo(click.style("⚠️  HOST FILESYSTEM MOUNT", fg="yellow", bold=True))
    click.echo("")
    click.echo("You are about to enable host filesystem access for Atom containers.")
    click.echo("")
    click.echo("This gives containers WRITE access to host directories.")
    click.echo("")
    click.echo("Governance protections in place:")
    click.echo("  ✓ AUTONOMOUS maturity gate required for shell access")
    click.echo("  ✓ Command whitelist (ls, cat, grep, git, npm, etc.)")
    click.echo("  ✓ Blocked commands (rm, mv, chmod, kill, sudo, etc.)")
    click.echo("  ✓ 5-minute timeout enforcement")
    click.echo("  ✓ Full audit trail to ShellSession table")
    click.echo("")
    click.echo("However, this STILL carries risk:")
    click.echo("  - Bugs in governance code could bypass protections")
    click.echo("  - Compromised AUTONOMOUS agent has shell access")
    click.echo("  - Docker escape vulnerabilities could be exploited")
    click.echo("")

    if not click.confirm("Do you understand the risks and want to continue?"):
        click.echo("Host mount cancelled.")
        raise SystemExit(1)

    click.echo("")
    click.echo("✓ Host mount confirmed")


if __name__ == "__main__":
    main_cli()
