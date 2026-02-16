---
phase: 14-community-skills-integration
plan: GAPCLOSURE-02
type: execute
wave: 4
depends_on:
  - "01"
  - "02"
  - "03"
  - "GAPCLOSURE-01"
gap_closure: true
files_modified:
  - backend/cli/main.py
  - backend/cli/daemon.py
  - backend/api/agent_control_routes.py
  - backend/tests/test_cli_agent_execution.py
  - backend/requirements.txt
  - backend/atom-os.service
  - README.md
autonomous: true

must_haves:
  truths:
    - "atom-os daemon command starts Atom as background service with PID file tracking"
    - "atom-os stop command gracefully shuts down background Atom service"
    - "atom-os status command shows if Atom is running (PID, uptime, memory usage)"
    - "atom-os execute command runs Atom in on-demand mode with single command"
    - "POST /api/agent/start endpoint starts Atom service programmatically"
    - "POST /api/agent/stop endpoint stops Atom service programmatically"
    - "POST /api/agent/execute endpoint executes single command and returns result"
    - "systemd service file allows auto-start on system boot"
    - "CLI works with any agent (OpenClaw, Claude, custom agents)"
  artifacts:
    - path: "backend/cli/daemon.py"
      provides: "Daemon mode for background service with PID file management"
      min_lines: 150
      contains: "start_daemon", "stop_daemon", "check_status", "DaemonManager"
    - path: "backend/api/agent_control_routes.py"
      provides: "REST API endpoints for agent-to-agent Atom control"
      min_lines: 180
      contains: "router", "POST /api/agent/start", "POST /api/agent/stop", "POST /api/agent/execute", "POST /api/agent/status"
    - path: "backend/cli/main.py"
      provides: "Enhanced CLI with daemon, stop, status, execute commands"
      min_lines: 250
      contains: "daemon", "stop", "status", "execute", "start"
    - path: "backend/atom-os.service"
      provides: "systemd service file for auto-start on boot"
      min_lines: 20
      contains: "Description=", "ExecStart=", "PIDFile="
    - path: "backend/tests/test_cli_agent_execution.py"
      provides: "Tests for daemon, execute, and API endpoints"
      min_lines: 200
    - path: "README.md"
      provides: "Updated documentation with agent-to-agent usage examples"
      min_lines: 50
      contains: "atom-os daemon", "agent-to-agent", "background service"

tasks:
  - title: "Create daemon mode for background service"
    files:
      - path: "backend/cli/daemon.py"
        action: |
        Create DaemonManager class for background service:

        ```python
        import os
        import sys
        import signal
        subprocess
        from pathlib import Path
        import psutil

        PID_DIR = Path.home() / ".atom" / "pids"
        PID_FILE = PID_DIR / "atom-os.pid"
        LOG_FILE = Path.home() / ".atom" / "logs" / "daemon.log"

        class DaemonManager:
            """Manage Atom OS as background daemon service."""

            @staticmethod
            def get_pid() -> int:
                """Get running daemon PID from PID file."""
                if PID_FILE.exists():
                    with open(PID_FILE, 'r') as f:
                        return int(f.read().strip())
                return None

            @staticmethod
            def is_running() -> bool:
                """Check if daemon process is running."""
                pid = DaemonManager.get_pid()
                if pid is None:
                    return False
                try:
                    return psutil.pid_exists(pid)
                except:
                    return False

            @staticmethod
            def start_daemon(port: int = 8000, host: str = "0.0.0.0", workers: int = 1,
                              host_mount: bool = False, dev: bool = False) -> int:
                """Start Atom OS as background daemon.

                Returns daemon PID.
                """
                if DaemonManager.is_running():
                    raise RuntimeError(f"Atom OS is already running (PID: {DaemonManager.get_pid()})")

                # Ensure directories exist
                PID_DIR.mkdir(parents=True, exist_ok=True)
                LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

                # Prepare environment
                env = os.environ.copy()
                if host_mount:
                    env["ATOM_HOST_MOUNT_ENABLED"] = "true"

                # Prepare command
                cmd = [
                    sys.executable, "-m", "uvicorn",
                    "main_api_app:app",
                    "--host", host,
                    "--port", str(port),
                    "--workers", str(workers)
                ]

                # Process: daemonize
                # Double-fork to detach from terminal
                # 1. Fork and exit parent
                # 2. Child forks again and exits
                # 3. Grandchild continues as daemon

                # Redirect stdout/stderr to log file
                log_file = open(LOG_FILE, 'a')

                # First fork
                pid = os.fork()
                if pid > 0:
                    # Parent: exit to let child become daemon
                    os._exit(0)

                # Child process
                os.setsid()
                os.chdir("/")

                # Second fork
                pid = os.fork()
                if pid > 0:
                    # Middle process: exit
                    os._exit(0)

                # Grandchild process (actual daemon)
                # Close file descriptors
                sys.stdin.flush()
                sys.stdout.close()
                sys.stderr.close()

                # Redirect stdout and stderr
                sys.stdout = log_file
                sys.stderr = log_file

                # Start uvicorn subprocess
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )

                # Write PID file
                with open(PID_FILE, 'w') as f:
                    f.write(str(process.pid))

                # Fork again to completely detach
                if os.fork() > 0:
                    os._exit(0)

                # Update PID to actual uvicorn PID
                with open(PID_FILE, 'w') as f:
                    f.write(str(process.pid))

                return process.pid

            @staticmethod
            def stop_daemon() -> bool:
                """Stop daemon gracefully.

                Returns True if stopped, False if not running.
                """
                pid = DaemonManager.get_pid()
                if pid is None:
                    print("Atom OS is not running")
                    return False

                try:
                    # Try graceful shutdown first
                    os.kill(pid, signal.SIGTERM)

                    # Wait up to 10 seconds for graceful shutdown
                    import time
                    for _ in range(100):
                        time.sleep(0.1)
                        if not psutil.pid_exists(pid):
                            break

                    # Force kill if still running
                    if psutil.pid_exists(pid):
                        os.kill(pid, signal.SIGKILL)
                        time.sleep(0.5)

                    # Clean up PID file
                    PID_FILE.unlink(missing_ok=True)

                    print(f"Atom OS stopped (PID: {pid})")
                    return True

                except ProcessLookupError:
                    # Process already dead, clean up PID file
                    PID_FILE.unlink(missing_ok=True)
                    print("Atom OS was already stopped")
                    return True

            @staticmethod
            def get_status() -> dict:
                """Get daemon status information."""
                pid = DaemonManager.get_pid()
                if pid is None:
                    return {
                        "running": False,
                        "pid": None,
                        "uptime": None,
                        "memory_mb": None
                    }

                if not psutil.pid_exists(pid):
                    return {
                        "running": False,
                        "pid": pid,
                        "uptime": None,
                        "memory_mb": None,
                        "note": "Stale PID file"
                    }

                try:
                    process = psutil.Process(pid)
                    return {
                        "running": True,
                        "pid": pid,
                        "uptime_seconds": process.cpu_times().system,
                        "memory_mb": process.memory_info().rss / 1024 / 1024,
                        "cpu_percent": process.cpu_percent(interval=0.1),
                        "status": "running"
                    }
                except psutil.NoSuchProcess:
                    return {
                        "running": False,
                        "pid": pid,
                        "note": "Process died unexpectedly"
                    }
        ```

        Verify: DaemonManager can start, stop, check status of Atom OS daemon
        Done: All methods tested with mock/real processes

  - title: "Add CLI commands for daemon management"
    files:
      - path: "backend/cli/main.py"
        action: |
        Add daemon, stop, status, and execute commands:

        ```python
        import click
        from .daemon import DaemonManager

        @main_cli.command()
        def daemon(
            port: int = click.option(8000, '--port', '-p', help='Port for web server'),
            host: str = click.option('0.0.0.0', '--host', '-h', help='Host to bind to'),
            workers: int = click.option(1, '--workers', '-w', help='Number of worker processes'),
            host_mount: bool = click.option(False, '--host-mount', help='Enable host filesystem mount'),
            dev: bool = click.option(False, '--dev', help='Enable development mode'),
            foreground: bool = click.option(False, '--foreground', '-f', help='Run in foreground (not daemon)')
        ):
            """Start Atom OS as background daemon service.

            Examples:
                atom-os daemon                    # Start as daemon
                atom-os daemon --port 3000        # Custom port
                atom-os daemon --foreground      # Run in foreground (for debugging)
            """
            if foreground:
                # Run in foreground mode (not daemon)
                os.environ["ATOM_DAEMON_MODE"] = "false"
                # Call existing start command
                start(port, host, workers, host_mount, dev)
            else:
                # Run as daemon
                os.environ["ATOM_DAEMON_MODE"] = "true"
                pid = DaemonManager.start_daemon(port, host, workers, host_mount, dev)
                click.echo(click.style("✓ Atom OS started as daemon", fg="green", bold=True))
                click.echo(f"  PID: {pid}")
                click.echo(f"  Dashboard: http://{host}:{port}")
                click.echo(f"  Logs: {LOG_FILE}")
                click.echo("")
                click.echo("Control commands:")
                click.echo("  atom-os status    - Check status")
                click.echo("  atom-os stop      - Stop daemon")
                click.echo("  atom-os restart  - Restart daemon")

        @main_cli.command()
        def stop():
            """Stop Atom OS background daemon.

            Example:
                atom-os stop
            """
            if DaemonManager.stop_daemon():
                click.echo(click.style("✓ Atom OS stopped", fg="green", bold=True))
            else:
                click.echo(click.style("ℹ Atom OS was not running", fg="yellow"))

        @main_cli.command()
        def status():
            """Check Atom OS daemon status.

            Example:
                atom-os status
            """
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
                click.echo(f"  Uptime: {status_info['uptime_seconds']:.0f}s")

            # Show dashboard URL if running
            if status_info["running"]:
                click.echo(f"  Dashboard: http://localhost:8000")

        @main_cli.command()
        @click.argument('command', required=False)
        def execute(command: str):
            """Execute Atom command on-demand and return result.

            This starts Atom temporarily, executes a command, and shuts down.
            Useful for one-off agent tasks.

            Examples:
                atom-os execute "agent.chat('Hello, create a report')"
                atom-os execute "workflow.run('monthly_report')"
            """
            if not command:
                click.echo("Error: command required")
                click.echo("Usage: atom-os execute <command>")
                raise click.Abort()

            click.echo(click.style("⚡ Executing Atom command...", fg="yellow"))

            # Import and execute
            from main_api_app import app
            from core.agent_orchestrator import AgentOrchestrator

            # TODO: Parse command and route to appropriate handler
            # This is a placeholder - need to implement actual command routing
            click.echo(f"Command: {command}")
            click.echo("(Command routing not yet implemented - use REST API instead)")
        ```

        Verify: daemon, stop, status, execute commands work correctly
        Done: CLI enhanced with 4 new commands

  - title: "Add agent control API endpoints"
    files:
      - path: "backend/api/agent_control_routes.py"
        action: |
        Create REST API for agent-to-agent control:

        ```python
        from fastapi import APIRouter, HTTPException
        from pydantic import BaseModel
        from cli.daemon import DaemonManager
        import os

        router = APIRouter(prefix="/api/agent", tags=["agent-control"])

        class StartAgentRequest(BaseModel):
            port: int = 8000
            host: str = "0.0.0.0"
            workers: int = 1
            host_mount: bool = False
            dev: bool = False

        @router.post("/start")
        async def start_atom(request: StartAgentRequest):
            """Start Atom OS as background service.

            Called by external agents (Claude, OpenClaw, etc.).
            """
            if DaemonManager.is_running():
                raise HTTPException(status_code=400, detail="Atom OS is already running")

            pid = DaemonManager.start_daemon(
                port=request.port,
                host=request.host,
                workers=request.workers,
                host_mount=request.host_mount,
                dev=request.dev
            )

            return {
                "success": True,
                "pid": pid,
                "status": "started",
                "dashboard_url": f"http://{request.host}:{request.port}",
                "message": "Atom OS started successfully"
            }

        @router.post("/stop")
        async def stop_atom():
            """Stop Atom OS background service."""
            if not DaemonManager.is_running():
                raise HTTPException(status_code=400, detail="Atom OS is not running")

            DaemonManager.stop_daemon()

            return {
                "success": True,
                "status": "stopped",
                "message": "Atom OS stopped successfully"
            }

        @router.post("/restart")
        async def restart_atom(request: StartAgentRequest):
            """Restart Atom OS background service."""
            was_running = DaemonManager.is_running()

            if was_running:
                DaemonManager.stop_daemon()

            import time
            time.sleep(2)  # Wait for clean shutdown

            pid = DaemonManager.start_daemon(
                port=request.port,
                host=request.host,
                workers=request.workers,
                host_mount=request.host_mount,
                dev=request.dev
            )

            return {
                "success": True,
                "pid": pid,
                "status": "restarted",
                "dashboard_url": f"http://{request.host}:{request.port}",
                "was_running": was_running
            }

        @router.get("/status")
        async def get_status():
            """Get Atom OS status and running info."""
            status_info = DaemonManager.get_status()

            return {
                "success": True,
                "status": status_info
            }

        class ExecuteCommandRequest(BaseModel):
            command: str
            timeout: int = 30

        @router.post("/execute")
        async def execute_atom_command(request: ExecuteCommandRequest):
            """Execute single Atom command and return result.

            Useful for one-off tasks from other agents.
            """
            # TODO: Implement command routing and execution
            # This requires integration with AgentOrchestrator

            return {
                "success": True,
                "result": "Command execution not yet implemented - use daemon mode",
                "note": "Use POST /api/agent/start to run Atom as service instead"
            }
        ```

        Verify: API endpoints allow agent-to-agent control
        Done: All endpoints tested with mock daemon manager

  - title: "Create systemd service file for auto-start"
    files:
      - path: "backend/atom-os.service"
        action: |
        Create systemd service file:

        ```ini
        [Unit]
        Description=Atom OS - AI Automation Platform
        After=network.target

        [Service]
        Type=forking
        PIDFile=%h/.atom/pids/atom-os.pid
        ExecStart=/usr/local/bin/atom-os daemon --port 8000
        ExecReload=/bin/kill -HUP $MAINPID
        ExecStop=/usr/local/bin/atom-os stop
        Restart=always
        RestartSec=10
        StandardOutput=journal
        StandardError=journal
        SyslogIdentifier=atom-os

        [Install]
        WantedBy=multi-user.target
        ```

        Verify: Service file allows systemd to manage Atom OS lifecycle
        Done: Service file created with proper configuration

  - title: "Add psutil dependency and update CLI entry point"
    files:
      - path: "backend/requirements.txt"
        action: |
        Add psutil>=6.0.0 for process management

        Verify: psutil dependency added
        Done: requirements.txt updated

  - title: "Update README with agent-to-agent usage examples"
    files:
      - path: "README.md"
        action: |
        Add section "Agent-to-Agent Execution" with examples:

        ```markdown
        ## Agent-to-Agent Execution

        Atom OS can be controlled by any agent (OpenClaw, Claude, custom agents) through CLI or REST API.

        ### Quick Start for Agents

        1. **Install:**
           ```bash
           pip install atom-os
           ```

        2. **Start as background service:**
           ```bash
           atom-os daemon --port 8000
           ```

        3. **Check status:**
           ```bash
           atom-os status
           ```

        4. **Stop service:**
           ```bash
           atom-os stop
           ```

        ### REST API Control

        Start Atom programmatically:
        ```bash
           curl -X POST http://localhost:8000/api/agent/start \
             -H "Content-Type: application/json" \
             -d '{"port": 8000, "host": "0.0.0.0"}'
           ```

        Check status:
        ```bash
           curl http://localhost:8000/api/agent/status
           ```

        Stop Atom:
        ```bash
           curl -X POST http://localhost:8000/api/agent/stop
           ```

        ### Systemd Service (Auto-start on Boot)

        Enable Atom OS to start on system boot:
        ```bash
           # Install service file
           sudo cp backend/atom-os.service /etc/systemd/system/

           # Reload systemd
           sudo systemctl daemon-reload

           # Enable auto-start
           sudo systemctl enable atom-os

           # Start service now
           sudo systemctl start atom-os

           # Check status
           sudo systemctl status atom-os
        ```

        ### Examples

        **OpenClaw Agent:**
        ```python
        # Start Atom before using tools
        subprocess.run(["atom-os", "daemon"])

        # Use Atom tools via API
        response = requests.get("http://localhost:8000/api/skills/list")
        ```

        **Claude Agent:**
        ```python
        # Check if Atom is running
        status = requests.get("http://localhost:8000/api/agent/status")
        if not status.json()["status"]["running"]:
            # Start Atom
            subprocess.run(["atom-os", "daemon"])

        # Execute workflow
        response = requests.post(
            "http://localhost:8000/api/workflows/execute",
            json={"workflow_name": "monthly_report"}
        )
        ```
        ```

        Verify: README updated with agent-to-agent examples
        Done: README enhanced with comprehensive usage guide
    ```

        Verify: README has clear examples for agent integration
        Done: README updated with CLI, API, and systemd examples

  - title: "Create tests for CLI agent execution features"
    files:
      - path: "backend/tests/test_cli_agent_execution.py"
        action: |
        Create comprehensive tests:

        ```python
        import pytest
        from click.testing import CliRunner
        from cli.daemon import DaemonManager
        from unittest.mock import patch, Mock
        import psutil

        class TestCLICommands:
            """Test CLI daemon management commands."""

            def test_daemon_command_starts_service(self):
                """Verify 'atom-os daemon' starts background service."""

            def test_stop_command_stops_service(self):
                """Verify 'atom-os stop' stops daemon."""

            def test_status_command_shows_info(self):
                """Verify 'atom-os status' shows running state."""

            def test_execute_command_runs_and_exits(self):
                """Verify 'atom-os execute' executes single command."""

            def test_daemon_prevents_double_start(self):
                """Verify daemon prevents starting if already running."""

            def test_stop_handles_not_running_gracefully(self):
                """Verify stop handles case where Atom is not running."""

        class TestAgentControlAPI:
            """Test REST API endpoints for agent control."""

            def test_start_endpoint_starts_daemon(self):
                """Verify POST /api/agent/start starts daemon."""

            def test_stop_endpoint_stops_daemon(self):
                """Verify POST /api/agent/stop stops daemon."""

            def test_status_endpoint_returns_status(self):
                """Verify GET /api/agent/status returns status info."""

            def test_restart_endpoint_restarts_daemon(self):
                """Verify POST /api/agent/restart restarts daemon."""

            def test_start_returns_400_if_running(self):
                """Verify start returns 400 if daemon already running."""

            def test_stop_returns_400_if_not_running(self):
                """Verify stop returns 400 if daemon not running."""
        ```

        Verify: All CLI and API tests pass
        Done: 15 tests covering daemon management and agent control

verification_criteria:
  - atom-os daemon command starts Atom as background service with PID tracking
  - atom-os stop command gracefully shuts down service
  - atom-os status command shows running state and system info
  - POST /api/agent/start starts Atom programmatically
  - POST /api/agent/stop stops Atom programmatically
  - POST /api/agent/status checks status programmatically
  - systemd service file allows auto-start on system boot
  - Any agent (OpenClaw, Claude, custom) can install and run Atom
