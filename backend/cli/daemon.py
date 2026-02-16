#!/usr/bin/env python3
"""
Atom OS Daemon Manager - Background service management.

Allows Atom OS to run as background daemon service for agent-to-agent execution.
Supports PID file tracking, graceful shutdown, and status monitoring.

Usage:
    atom-os daemon              # Start as background service
    atom-os status              # Check daemon status
    atom-os stop                # Stop daemon
    atom-os execute <command>   # Run on-demand
"""

import os
import sys
import signal
import subprocess
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None
    print("Warning: psutil not installed. Daemon features limited.")
    print("Install with: pip install psutil>=6.0.0")

# Daemon configuration
PID_DIR = Path.home() / ".atom" / "pids"
PID_FILE = PID_DIR / "atom-os.pid"
LOG_DIR = Path.home() / ".atom" / "logs"
LOG_FILE = LOG_DIR / "daemon.log"


class DaemonManager:
    """Manage Atom OS as background daemon service."""

    @staticmethod
    def get_pid() -> Optional[int]:
        """Get running daemon PID from PID file.

        Returns:
            PID if file exists and contains valid integer, None otherwise
        """
        if PID_FILE.exists():
            try:
                with open(PID_FILE, 'r') as f:
                    return int(f.read().strip())
            except (ValueError, IOError):
                return None
        return None

    @staticmethod
    def is_running() -> bool:
        """Check if daemon process is running.

        Returns:
            True if process is alive, False otherwise
        """
        pid = DaemonManager.get_pid()
        if pid is None:
            return False

        if psutil is None:
            # Fallback: try sending signal 0
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False

        try:
            return psutil.pid_exists(pid)
        except Exception:
            return False

    @staticmethod
    def start_daemon(
        port: int = 8000,
        host: str = "0.0.0.0",
        workers: int = 1,
        host_mount: bool = False,
        dev: bool = False
    ) -> int:
        """Start Atom OS as background daemon.

        Creates background subprocess with PID file tracking.
        Detaches from terminal for long-running service.

        Args:
            port: Port for web server (default: 8000)
            host: Host to bind to (default: 0.0.0.0)
            workers: Number of worker processes (default: 1)
            host_mount: Enable host filesystem mount (default: False)
            dev: Enable development mode (default: False)

        Returns:
            Daemon process PID

        Raises:
            RuntimeError: If daemon is already running
            IOError: If PID file cannot be written
        """
        if DaemonManager.is_running():
            current_pid = DaemonManager.get_pid()
            raise RuntimeError(f"Atom OS is already running (PID: {current_pid})")

        # Ensure directories exist
        PID_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

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

        if dev:
            cmd.append("--reload")

        # Open log file
        try:
            log_file = open(LOG_FILE, 'a')
        except IOError as e:
            raise IOError(f"Cannot open log file {LOG_FILE}: {e}")

        # Start subprocess
        try:
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True  # Detach from parent process
            )
        except Exception as e:
            log_file.close()
            raise RuntimeError(f"Failed to start daemon: {e}")

        # Write PID file
        try:
            with open(PID_FILE, 'w') as f:
                f.write(str(process.pid))
        except IOError as e:
            process.terminate()
            log_file.close()
            raise IOError(f"Cannot write PID file {PID_FILE}: {e}")

        log_file.close()

        return process.pid

    @staticmethod
    def stop_daemon() -> bool:
        """Stop daemon gracefully.

        Attempts graceful shutdown with SIGTERM, then SIGKILL after timeout.

        Returns:
            True if stopped, False if not running

        Raises:
            IOError: If PID file cannot be removed
        """
        pid = DaemonManager.get_pid()
        if pid is None:
            return False

        try:
            # Try graceful shutdown first
            os.kill(pid, signal.SIGTERM)

            # Wait up to 10 seconds for graceful shutdown
            import time
            for _ in range(100):
                time.sleep(0.1)
                if not DaemonManager.is_running():
                    break

            # Force kill if still running
            if DaemonManager.is_running():
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.5)

            # Clean up PID file
            try:
                PID_FILE.unlink(missing_ok=True)
            except IOError as e:
                raise IOError(f"Cannot remove PID file {PID_FILE}: {e}")

            return True

        except ProcessLookupError:
            # Process already dead, clean up PID file
            try:
                PID_FILE.unlink(missing_ok=True)
            except IOError:
                pass
            return True

    @staticmethod
    def get_status() -> dict:
        """Get daemon status information.

        Returns:
            Dict with running status, PID, uptime, memory usage, CPU

            Example:
                {
                    "running": True,
                    "pid": 12345,
                    "uptime_seconds": 3600,
                    "memory_mb": 256.5,
                    "cpu_percent": 5.2,
                    "status": "running"
                }
        """
        pid = DaemonManager.get_pid()
        if pid is None:
            return {
                "running": False,
                "pid": None,
                "uptime_seconds": None,
                "memory_mb": None,
                "cpu_percent": None,
                "status": "not_running"
            }

        if not DaemonManager.is_running():
            return {
                "running": False,
                "pid": pid,
                "uptime_seconds": None,
                "memory_mb": None,
                "cpu_percent": None,
                "status": "stale_pid_file",
                "note": "Stale PID file"
            }

        if psutil is None:
            # Limited status without psutil
            return {
                "running": True,
                "pid": pid,
                "uptime_seconds": None,
                "memory_mb": None,
                "cpu_percent": None,
                "status": "running"
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
                "uptime_seconds": None,
                "memory_mb": None,
                "cpu_percent": None,
                "status": "died_unexpectedly",
                "note": "Process died unexpectedly"
            }
