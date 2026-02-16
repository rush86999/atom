#!/usr/bin/env python3
"""
Local Agent CLI - Manage local agent for host shell/file access.

Provides commands for starting, stopping, and monitoring local agent process.
Local agent runs outside Docker container on host machine with governed shell execution.

Usage:
    atom-os local-agent start --port 8000
    atom-os local-agent status
    atom-os local-agent stop
    atom-os local-agent execute "<command>" --directory /tmp
"""

import asyncio
import os
import sys
import click
import logging
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.daemon import DaemonManager

logger = logging.getLogger(__name__)

# Local agent PID file (separate from main daemon)
LOCAL_AGENT_PID_DIR = Path.home() / ".atom" / "pids"
LOCAL_AGENT_PID_FILE = LOCAL_AGENT_PID_DIR / "local-agent.pid"


@click.group()
def local_agent():
    """Local agent management commands."""
    pass


@local_agent.command()
@click.option('--port', default=8000, help='Backend API port')
@click.option('--host', default='localhost', help='Backend API host')
@click.option('--backend-url', default=None, help='Full backend API URL (overrides --host/--port)')
def start(port: int, host: str, backend_url: str):
    """
    Start local agent as background service.

    Communicates with Atom backend via REST API for governance checks.
    Uses existing DaemonManager for PID tracking.

    **Security Warnings:**
    - Local agent will have access to host filesystem
    - AUTONOMOUS agents can execute commands without approval
    - All executions logged to audit trail
    - Only AUTONOMOUS agents can execute commands
    - Commands validated against whitelist

    **Examples:**
        atom-os local-agent start                          # Default (localhost:8000)
        atom-os local-agent start --port 3000              # Custom port
        atom-os local-agent start --backend-url http://backend:8000  # Full URL
    """
    # Check if already running
    if _is_local_agent_running():
        pid = _get_local_agent_pid()
        click.echo(click.style(f"✗ Local agent already running (PID: {pid})", fg="red"))
        sys.exit(1)

    # Build backend URL
    if backend_url:
        backend_url = backend_url.rstrip("/")
    else:
        backend_url = f"http://{host}:{port}"

    # Display security warnings
    click.echo(click.style("⚠️  SECURITY WARNINGS", fg="yellow", bold=True))
    click.echo("")
    click.echo("Local agent will have access to host filesystem")
    click.echo("AUTONOMOUS agents can execute commands without approval")
    click.echo("All executions logged to audit trail")
    click.echo("")
    click.echo(click.style("Governance protections:", fg="green"))
    click.echo("  ✓ AUTONOMOUS maturity gate")
    click.echo("  ✓ Command whitelist (ls, cat, grep, git, npm, etc.)")
    click.echo("  ✓ Blocked commands (rm, mv, chmod, kill, sudo, etc.)")
    click.echo("  ✓ 5-minute timeout enforcement")
    click.echo("  ✓ Full audit trail (ShellSession table)")
    click.echo("")

    # Confirm startup
    if not click.confirm(click.style("Start local agent?", fg="yellow", bold=True), default=True):
        click.echo("Cancelled")
        sys.exit(0)

    # Ensure PID directory exists
    LOCAL_AGENT_PID_DIR.mkdir(parents=True, exist_ok=True)

    # Set environment variable for backend URL
    env = os.environ.copy()
    env["ATOM_BACKEND_URL"] = backend_url

    # Prepare command to run local agent
    # Note: This would typically run as separate process, but for now we create a placeholder
    # In production, this would start: python -m atom.local_agent_main
    cmd = [
        sys.executable,
        "-c",
        f"""
import os
import sys
import asyncio
sys.path.insert(0, '{str(Path(__file__).parent.parent)}')

from core.local_agent_service import get_local_agent_service

async def run_local_agent():
    service = get_local_agent_service(backend_url="{backend_url}")
    status = await service.get_status()
    print(f"Local agent started: {{status}}")
    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        await service.close()

asyncio.run(run_local_agent())
"""
    ]

    # Start process
    import subprocess
    try:
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )

        # Write PID file
        with open(LOCAL_AGENT_PID_FILE, 'w') as f:
            f.write(str(process.pid))

        click.echo(click.style(f"✓ Local agent started (PID: {process.pid})", fg="green", bold=True))
        click.echo(f"  Backend API: {backend_url}")
        click.echo(f"  PID file: {LOCAL_AGENT_PID_FILE}")
        click.echo("")
        click.echo("Check status: atom-os local-agent status")
        click.echo("Stop agent:  atom-os local-agent stop")

    except Exception as e:
        click.echo(click.style(f"✗ Failed to start local agent: {e}", fg="red"))
        sys.exit(1)


@local_agent.command()
def status():
    """
    Check local agent status.

    Shows whether local agent is running and backend connectivity.

    **Example:**
        atom-os local-agent status
    """
    pid = _get_local_agent_pid()

    if pid is None:
        click.echo(click.style("✗ Local agent not running", fg="red"))
        click.echo("Start with: atom-os local-agent start")
        sys.exit(1)

    if not _is_local_agent_running():
        click.echo(click.style(f"✗ Local agent not running (stale PID file: {pid})", fg="red"))
        click.echo("Clean up stale PID:")
        click.echo(f"  rm {LOCAL_AGENT_PID_FILE}")
        sys.exit(1)

    # Check backend connectivity
    backend_url = os.getenv("ATOM_BACKEND_URL", "http://localhost:8000")

    click.echo(click.style(f"✓ Local agent running", fg="green", bold=True))
    click.echo(f"  PID: {pid}")
    click.echo(f"  Backend URL: {backend_url}")
    click.echo(f"  PID file: {LOCAL_AGENT_PID_FILE}")


@local_agent.command()
def stop():
    """
    Stop local agent.

    Gracefully stops local agent process.

    **Example:**
        atom-os local-agent stop
    """
    pid = _get_local_agent_pid()

    if pid is None:
        click.echo(click.style("✗ Local agent not running", fg="red"))
        sys.exit(1)

    if not _is_local_agent_running():
        click.echo(click.style(f"✗ Local agent not running (stale PID file)", fg="yellow"))
        if click.confirm("Clean up stale PID file?"):
            LOCAL_AGENT_PID_FILE.unlink(missing_ok=True)
            click.echo(click.style("✓ PID file removed", fg="green"))
        sys.exit(1)

    # Stop process
    try:
        import signal
        import time

        # Try graceful shutdown
        os.kill(pid, signal.SIGTERM)

        # Wait up to 10 seconds
        for _ in range(100):
            time.sleep(0.1)
            if not _is_local_agent_running():
                break

        # Force kill if still running
        if _is_local_agent_running():
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)

        # Clean up PID file
        LOCAL_AGENT_PID_FILE.unlink(missing_ok=True)

        click.echo(click.style("✓ Local agent stopped", fg="green", bold=True))

    except ProcessLookupError:
        # Process already dead
        LOCAL_AGENT_PID_FILE.unlink(missing_ok=True)
        click.echo(click.style("✓ Local agent stopped (already dead)", fg="green"))
    except Exception as e:
        click.echo(click.style(f"✗ Failed to stop local agent: {e}", fg="red"))
        sys.exit(1)


@local_agent.command()
@click.argument('command', required=True)
@click.option('--directory', '-d', default=None, help='Working directory for command')
@click.option('--agent-id', '-a', default=None, help='Agent ID (for testing)')
def execute(command: str, directory: str, agent_id: str):
    """
    Execute command (for testing).

    Test command execution through local agent.
    Requires AUTONOMOUS agent maturity.

    **Examples:**
        atom-os local-agent execute "ls -la" --directory /tmp
        atom-os local-agent execute "pwd" --agent-id test-agent-123
    """
    import asyncio

    async def run_execute():
        from core.local_agent_service import get_local_agent_service

        backend_url = os.getenv("ATOM_BACKEND_URL", "http://localhost:8000")
        service = get_local_agent_service(backend_url=backend_url)

        # Use provided agent_id or default test agent
        test_agent_id = agent_id or "test-local-agent"

        try:
            click.echo(f"Executing: {command}")
            if directory:
                click.echo(f"Directory: {directory}")
            click.echo("")

            result = await service.execute_command(
                agent_id=test_agent_id,
                command=command,
                working_directory=directory
            )

            if result.get("allowed"):
                click.echo(click.style("✓ Command executed", fg="green"))
                click.echo(f"  Exit code: {result.get('exit_code')}")
                click.echo(f"  Duration: {result.get('duration_seconds', 0):.2f}s")

                if result.get("stdout"):
                    click.echo(f"\nStdout:\n{result['stdout']}")

                if result.get("stderr"):
                    click.echo(f"\nStderr:\n{result['stderr']}")

                if result.get("timed_out"):
                    click.echo(click.style("\n⚠️  Command timed out after 5 minutes", fg="yellow"))
            else:
                click.echo(click.style("✗ Command not allowed", fg="red"))
                click.echo(f"  Reason: {result.get('reason')}")
                if result.get("requires_approval"):
                    click.echo("  Requires approval: Yes")

        except Exception as e:
            click.echo(click.style(f"✗ Execution failed: {e}", fg="red"))
        finally:
            await service.close()

    asyncio.run(run_execute())


# ============================================================================
# Helper Functions
# ============================================================================

def _get_local_agent_pid() -> int | None:
    """Get local agent PID from PID file."""
    if LOCAL_AGENT_PID_FILE.exists():
        try:
            with open(LOCAL_AGENT_PID_FILE, 'r') as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return None
    return None


def _is_local_agent_running() -> bool:
    """Check if local agent process is running."""
    pid = _get_local_agent_pid()
    if pid is None:
        return False

    try:
        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
        return True
    except OSError:
        return False


if __name__ == "__main__":
    local_agent()
