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

    # Check edition
    from core.package_feature_service import get_package_feature_service
    service = get_package_feature_service()

    edition_display = "Personal Edition" if service.is_personal else "Enterprise Edition"
    click.echo(click.style(f"{edition_display}", fg="blue" if service.is_personal else "yellow"))

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
@click.option('--port', '-p', default=8000, help='Port for web server')
@click.option('--host', '-h', default='0.0.0.0', help='Host to bind to')
@click.option('--workers', '-w', default=1, help='Number of worker processes')
@click.option('--host-mount', is_flag=True, help='Enable host filesystem mount')
@click.option('--dev', is_flag=True, help='Enable development mode')
@click.option('--foreground', '-f', is_flag=True, help='Run in foreground (not daemon)')
def daemon(port: int, host: str, workers: int, host_mount: bool, dev: bool, foreground: bool):
    """Start Atom OS as background daemon service.

    Starts Atom OS as detached background process with PID file tracking.
    Use with other agents (OpenClaw, Claude, custom) for agent-to-agent execution.

    **Examples:**
        atom-os daemon                           # Start as daemon
        atom-os daemon --port 3000               # Custom port
        atom-os daemon --foreground              # Run in foreground (for debugging)
        atom-os daemon --host-mount              # With host mount
    """
    from cli.daemon import DaemonManager, LOG_FILE

    if foreground:
        # Run in foreground mode (not daemon)
        click.echo(click.style("⚡ Starting Atom OS in foreground mode...", fg="yellow"))
        start(port, host, workers, host_mount, dev)
    else:
        # Run as daemon
        try:
            pid = DaemonManager.start_daemon(port, host, workers, host_mount, dev)
            click.echo(click.style("✓ Atom OS started as daemon", fg="green", bold=True))
            click.echo(f"  PID: {pid}")
            click.echo(f"  Dashboard: http://{host}:{port}")
            click.echo(f"  Logs: {LOG_FILE}")
            click.echo("")
            click.echo("Control commands:")
            click.echo("  atom-os status    - Check status")
            click.echo("  atom-os stop      - Stop daemon")
        except RuntimeError as e:
            click.echo(click.style(f"Error: {e}", fg="red"), err=True)
            raise SystemExit(1)
        except IOError as e:
            click.echo(click.style(f"Error: {e}", fg="red"), err=True)
            raise SystemExit(1)


@main_cli.command()
def stop():
    """Stop Atom OS background daemon.

    Gracefully shuts down daemon process with cleanup.

    **Example:**
        atom-os stop
    """
    from cli.daemon import DaemonManager

    if DaemonManager.stop_daemon():
        pid = DaemonManager.get_pid()
        if pid:
            click.echo(click.style(f"✓ Atom OS stopped (PID: {pid})", fg="green", bold=True))
        else:
            click.echo(click.style("✓ Atom OS stopped", fg="green", bold=True))
    else:
        click.echo(click.style("ℹ Atom OS was not running", fg="yellow"))


@main_cli.command()
def status():
    """Check Atom OS daemon status.

    Shows running state, PID, uptime, memory usage, and CPU.

    **Example:**
        atom-os status
    """
    from cli.daemon import DaemonManager

    status_info = DaemonManager.get_status()

    if not status_info["running"]:
        click.echo("Status: " + click.style("STOPPED", fg="red"))
    else:
        click.echo("Status: " + click.style("RUNNING", fg="green", bold=True))
        click.echo(f"  PID: {status_info['pid']}")

        if status_info.get('memory_mb'):
            click.echo(f"  Memory: {status_info['memory_mb']:.1f} MB")

        if status_info.get('cpu_percent'):
            click.echo(f"  CPU: {status_info['cpu_percent']:.1f}%")

        if status_info.get('uptime_seconds'):
            click.echo(f"  Uptime: {status_info['uptime_seconds']:.0f}s")

        # Show dashboard URL if running
        port = os.getenv("PORT", "8000")
        click.echo(f"  Dashboard: http://localhost:{port}")

    # Show note if present
    if status_info.get("note"):
        click.echo(f"  Note: {status_info['note']}")


@main_cli.command()
@click.argument('command', required=False)
def execute(command: str):
    """Execute Atom command on-demand and return result.

    Starts Atom temporarily, executes a command, and shuts down.
    Useful for one-off agent tasks.

    **Examples:**
        atom-os execute "agent.chat('Hello, create a report')"
        atom-os execute "workflow.run('monthly_report')"

    **Note:** Command routing not yet implemented - use REST API instead.
    """
    if not command:
        click.echo("Error: command required")
        click.echo("Usage: atom-os execute <command>")
        raise SystemExit(1)

    click.echo(click.style("⚡ Executing Atom command...", fg="yellow"))
    click.echo(f"Command: {command}")
    click.echo("")
    click.echo("(Command routing not yet implemented - use REST API instead)")
    click.echo("")
    click.echo("For programmatic control, use:")
    click.echo("  POST /api/agent/start   - Start Atom as service")
    click.echo("  POST /api/agent/execute - Execute single command")
    click.echo("")
    click.echo("See docs: atom-os config")


@main_cli.command()
@click.option('--show-daemon', is_flag=True, help='Show daemon status')
def config(show_daemon: bool):
    """Show configuration details and environment variables."""
    click.echo(click.style("Atom OS Configuration", bold=True))
    click.echo("=" * 40)
    click.echo("")
    click.echo("Environment Variables:")
    click.echo("")
    click.echo("Server:")
    click.echo("  PORT              - Server port (default: 8000)")
    click.echo("  HOST              - Server host (default: 0.0.0.0)")
    click.echo("  WORKERS           - Worker processes (default: 1)")
    click.echo("")
    click.echo("Daemon:")
    click.echo("  ATOM_DAEMON_MODE  - Enable daemon mode (true/false)")
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
    click.echo("Agent-to-Agent Execution:")
    click.echo("  POST /api/agent/start     - Start Atom as service")
    click.echo("  POST /api/agent/stop      - Stop Atom service")
    click.echo("  GET  /api/agent/status    - Check status")
    click.echo("  POST /api/agent/execute   - Execute command")
    click.echo("")
    click.echo("See .env file for full configuration.")

    if show_daemon:
        from cli.daemon import DaemonManager, PID_FILE, LOG_FILE
        click.echo("")
        click.echo("Daemon Configuration:")
        click.echo(f"  PID File: {PID_FILE}")
        click.echo(f"  Log File: {LOG_FILE}")
        click.echo(f"  Running: {DaemonManager.is_running()}")


@main_cli.command()
@click.option('--all', 'preseed_all', is_flag=True, help='Pre-seed all caches')
@click.option('--pricing', is_flag=True, help='Pre-seed pricing cache only')
@click.option('--models', is_flag=True, help='Pre-seed cognitive tier models only')
@click.option('--governance', is_flag=True, help='Pre-seed governance cache only')
@click.option('--workspace', default='default', help='Workspace ID for context')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def preseed_cache(preseed_all: bool, pricing: bool, models: bool, governance: bool, workspace: str, verbose: bool):
    """Pre-seed BYOK caches for deployment or on-demand warming.

    Pre-warms caches to eliminate cold start latency:
    - Pricing cache (LiteLLM + OpenRouter API data)
    - Cognitive tier models (availability validation)
    - Governance cache (common agent permissions)
    - Cache-aware router (baseline probabilities)

    **Examples:**
        atom-os preseed-cache --all           # Pre-seed all caches
        atom-os preseed-cache --pricing       # Pricing cache only
        atom-os preseed-cache --models        # Cognitive models only
        atom-os preseed-cache --governance    # Governance cache only
        atom-os preseed-cache --all -v        # Verbose output

    **Environment Variables:**
        PRESEED_CACHE_ON_STARTUP  - Auto-preseed on server start (true/false)
    """
    import asyncio
    from core.byok_cache_preseeding import (
        preseed_all_caches,
        preseed_pricing_cache,
        preseed_cognitive_models,
        preseed_governance_cache,
        print_preseed_results,
    )

    async def run_preseed():
        # If no specific option selected, default to --all
        if not any([preseed_all, pricing, models, governance]):
            preseed_all = True

        click.echo(click.style("🔄 BYOK Cache Pre-seeding", fg="blue", bold=True))
        click.echo("")

        try:
            if preseed_all:
                results = await preseed_all_caches(
                    workspace_id=workspace,
                    verbose=verbose
                )
            else:
                # Pre-seed specific caches
                results = {
                    "started_at": datetime.now().isoformat(),
                    "workspace_id": workspace,
                }

                if pricing:
                    results["pricing"] = await preseed_pricing_cache(verbose=verbose)

                if models:
                    results["cognitive"] = await preseed_cognitive_models(verbose=verbose)

                if governance:
                    results["governance"] = await preseed_governance_cache(
                        workspace_id=workspace,
                        verbose=verbose
                    )

                results["completed_at"] = datetime.now().isoformat()

            # Print results
            print_preseed_results(results)

            # Exit with error code if any step failed
            if "error" in results:
                raise SystemExit(1)

        except Exception as e:
            click.echo(click.style(f"✗ Pre-seeding failed: {e}", fg="red"), err=True)
            raise SystemExit(1)

    # Run async function
    asyncio.run(run_preseed())


# Import local-agent command group
from cli.local_agent import local_agent
main_cli.add_command(local_agent, name="local-agent")

# Import edition management commands
from cli.init import register_init_command
from cli.enable import register_enable_command

# Register edition management commands
register_init_command(main_cli)
register_enable_command(main_cli)


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


@main_cli.group("office")
def office_group():
    """Office document automation commands (Word, Excel, PPTX)."""
    pass


@office_group.command("excel-read")
@click.argument("file_path")
@click.argument("cell_path", default="")
def cli_excel_read(file_path: str, cell_path: str):
    """Read values from Excel spreadsheet cell or range."""
    from core.office_service import OfficeService
    service = OfficeService()
    res = service.excel.read_range(file_path, cell_path)
    if not res.get("success"):
        click.echo(click.style(f"Error: {res.get('error')}", fg="red"), err=True)
        raise SystemExit(1)
    
    if "cells" in res:
        for row in res["cells"]:
            row_vals = [str(c["value"]) for c in row]
            click.echo("\t".join(row_vals))
    else:
        click.echo(f"Value: {res.get('value')}")
        if res.get("formula"):
            click.echo(f"Formula: {res.get('formula')}")


@office_group.command("excel-write")
@click.argument("file_path")
@click.argument("cell_path")
@click.argument("value")
@click.option("--formula", is_flag=True, help="Treat value as formula")
def cli_excel_write(file_path: str, cell_path: str, value: str, formula: bool):
    """Write value or formula to Excel spreadsheet coordinate."""
    from core.office_service import OfficeService
    service = OfficeService()
    res = service.excel.write_cell(file_path, cell_path, value, formula)
    if not res.get("success"):
        click.echo(click.style(f"Error: {res.get('error')}", fg="red"), err=True)
        raise SystemExit(1)
    click.echo(res.get("message"))


@office_group.command("word-read")
@click.argument("file_path")
def cli_word_read(file_path: str):
    """Read content paragraphs and tables from a Word document."""
    from core.office_service import OfficeService
    service = OfficeService()
    res = service.word.read_document(file_path)
    if not res.get("success"):
        click.echo(click.style(f"Error: {res.get('error')}", fg="red"), err=True)
        raise SystemExit(1)
    
    click.echo(f"--- paragraphs ({len(res['paragraphs'])}) ---")
    for p in res["paragraphs"]:
        click.echo(f"[{p['style']}] {p['text']}")
    
    click.echo(f"\n--- tables ({len(res['tables'])}) ---")
    for t in res["tables"]:
        click.echo(f"Table {t['index']}:")
        for row in t["rows"]:
            click.echo(" | ".join(row))


@office_group.command("word-write")
@click.argument("file_path")
@click.argument("content")
@click.option("--action", default="append", help="Modification action: append or replace")
@click.option("--target", help="Target placeholder to replace")
@click.option("--style", default="Normal", help="Paragraph style name")
def cli_word_write(file_path: str, content: str, action: str, target: str, style: str):
    """Write text content to a Word document."""
    from core.office_service import OfficeService
    service = OfficeService()
    options = {"style": style, "target": target}
    res = service.word.modify_document(file_path, action, content, options)
    if not res.get("success"):
        click.echo(click.style(f"Error: {res.get('error')}", fg="red"), err=True)
        raise SystemExit(1)
    click.echo(res.get("message"))


@office_group.command("pptx-read")
@click.argument("file_path")
def cli_pptx_read(file_path: str):
    """Read layouts and slide content from a PowerPoint presentation."""
    from core.office_service import OfficeService
    service = OfficeService()
    res = service.pptx.read_slides(file_path)
    if not res.get("success"):
        click.echo(click.style(f"Error: {res.get('error')}", fg="red"), err=True)
        raise SystemExit(1)
    
    for slide in res["slides"]:
        click.echo(f"Slide {slide['slide_index'] + 1}:")
        for shape in slide["shapes"]:
            if shape["type"] == "text":
                click.echo(f"  [Text Frame] {shape['text']}")
            elif shape["type"] == "table":
                click.echo(f"  [Table] {len(shape['table'])} rows")


@office_group.command("pptx-write")
@click.argument("file_path")
@click.argument("content")
@click.option("--action", default="add_slide", help="Action: add_slide")
@click.option("--title", help="Slide title")
@click.option("--layout-idx", default=1, type=int, help="Slide layout index")
def cli_pptx_write(file_path: str, content: str, action: str, title: str, layout_idx: int):
    """Modify slides in a PowerPoint presentation."""
    from core.office_service import OfficeService
    service = OfficeService()
    options = {"title": title, "content": content, "layout_idx": layout_idx}
    res = service.pptx.modify_slides(file_path, action, options)
    if not res.get("success"):
        click.echo(click.style(f"Error: {res.get('error')}", fg="red"), err=True)
        raise SystemExit(1)
    click.echo(res.get("message"))


@office_group.command("render")
@click.argument("file_path")
def cli_render(file_path: str):
    """Render Word, Excel, or PPTX into HTML string."""
    from core.office_service import OfficeService
    service = OfficeService()
    res = service.renderer.render_to_html(file_path)
    if not res.get("success"):
        click.echo(click.style(f"Error: {res.get('error')}", fg="red"), err=True)
        raise SystemExit(1)
    click.echo(res.get("html"))


if __name__ == "__main__":
    main_cli()
