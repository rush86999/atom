#!/usr/bin/env python3
"""
ATOM Main Application Monitor

This script monitors the main application startup and provides diagnostics
when the application gets stuck during initialization.
"""

import os
import sys
import time
import logging
import requests
import subprocess
import threading
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("main_app_monitor.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class MainAppMonitor:
    """Monitor for ATOM main application startup and health"""

    def __init__(self, port=5058, timeout_seconds=30, check_interval=5):
        self.port = port
        self.timeout_seconds = timeout_seconds
        self.check_interval = check_interval
        self.start_time = None
        self.process = None
        self.is_running = False

    def start_main_app(self):
        """Start the main application"""
        logger.info("🚀 Starting ATOM Main Application...")

        try:
            # Change to backend directory
            backend_dir = os.path.join(
                os.path.dirname(__file__), "backend", "python-api-service"
            )
            os.chdir(backend_dir)

            # Start the main application
            self.process = subprocess.Popen(
                [sys.executable, "main_api_app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.start_time = datetime.now()
            self.is_running = True
            logger.info(f"Main application started with PID: {self.process.pid}")

            # Start output monitoring in separate thread
            output_thread = threading.Thread(target=self._monitor_output)
            output_thread.daemon = True
            output_thread.start()

            return True

        except Exception as e:
            logger.error(f"Failed to start main application: {e}")
            return False

    def _monitor_output(self):
        """Monitor application output in real-time"""
        try:
            while self.process and self.process.poll() is None:
                # Read stdout
                stdout_line = self.process.stdout.readline()
                if stdout_line:
                    logger.info(f"[APP] {stdout_line.strip()}")

                # Read stderr
                stderr_line = self.process.stderr.readline()
                if stderr_line:
                    logger.warning(f"[APP-ERROR] {stderr_line.strip()}")

                time.sleep(0.1)

        except Exception as e:
            logger.error(f"Error monitoring application output: {e}")

    def check_health(self):
        """Check if the application is healthy and responding"""
        try:
            response = requests.get(f"http://localhost:{self.port}/healthz", timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Application healthy: {data}")
                return True
            else:
                logger.warning(
                    f"⚠️  Application responded with status: {response.status_code}"
                )
                return False

        except requests.exceptions.RequestException as e:
            logger.warning(f"❌ Application not responding: {e}")
            return False

    def diagnose_stuck_issue(self):
        """Diagnose why the application might be stuck"""
        logger.info("🔍 Running diagnostics...")

        diagnostics = {
            "port_in_use": self._check_port_in_use(),
            "import_issues": self._check_import_issues(),
            "database_issues": self._check_database_issues(),
            "blueprint_registration": self._check_blueprint_registration(),
            "process_status": self._check_process_status(),
        }

        # Print diagnostic summary
        logger.info("📊 DIAGNOSTIC SUMMARY:")
        for check, result in diagnostics.items():
            status = "✅" if result.get("healthy", False) else "❌"
            logger.info(f"  {status} {check}: {result.get('message', 'Unknown')}")

        return diagnostics

    def _check_port_in_use(self):
        """Check if port is already in use"""
        try:
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                result = s.connect_ex(("localhost", self.port))
                return {
                    "healthy": result != 0,
                    "message": f"Port {self.port} is {'in use' if result == 0 else 'available'}",
                }
        except Exception as e:
            return {"healthy": False, "message": f"Error checking port: {e}"}

    def _check_import_issues(self):
        """Check for common import issues"""
        try:
            # Test basic imports
            import flask
            import sqlite3
            import bcrypt
            import jwt

            return {"healthy": True, "message": "All required imports available"}
        except ImportError as e:
            return {"healthy": False, "message": f"Missing import: {e}"}

    def _check_database_issues(self):
        """Check for database connectivity issues"""
        try:
            import sqlite3

            # Check if SQLite database can be created
            test_db_path = "/tmp/atom_test.db"
            conn = sqlite3.connect(test_db_path)
            conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")
            conn.execute("DROP TABLE IF EXISTS test")
            conn.close()
            os.unlink(test_db_path)

            return {"healthy": True, "message": "SQLite database operations working"}
        except Exception as e:
            return {"healthy": False, "message": f"Database error: {e}"}

    def _check_blueprint_registration(self):
        """Check blueprint registration issues"""
        try:
            # This would require importing the actual app, but we can check file existence
            blueprint_files = [
                "search_routes.py",
                "calendar_handler.py",
                "task_handler.py",
                "message_handler.py",
                "user_auth_api.py",
            ]

            missing_files = []
            for file in blueprint_files:
                if not os.path.exists(file):
                    missing_files.append(file)

            if missing_files:
                return {
                    "healthy": False,
                    "message": f"Missing blueprint files: {', '.join(missing_files)}",
                }
            else:
                return {"healthy": True, "message": "All blueprint files present"}

        except Exception as e:
            return {"healthy": False, "message": f"Error checking blueprints: {e}"}

    def _check_process_status(self):
        """Check the status of the main application process"""
        if not self.process:
            return {"healthy": False, "message": "No process running"}

        return_code = self.process.poll()
        if return_code is None:
            return {"healthy": True, "message": "Process is running"}
        else:
            return {
                "healthy": False,
                "message": f"Process exited with code: {return_code}",
            }

    def wait_for_startup(self):
        """Wait for application to start up successfully"""
        logger.info(
            f"⏳ Waiting for application to start (timeout: {self.timeout_seconds}s)..."
        )

        start_wait = datetime.now()
        while (datetime.now() - start_wait).seconds < self.timeout_seconds:
            if self.check_health():
                logger.info("🎉 Application started successfully!")
                return True

            # Check if process is still running
            if self.process and self.process.poll() is not None:
                logger.error("💥 Application process died during startup")
                # Get any error output
                stdout, stderr = self.process.communicate()
                if stderr:
                    logger.error(f"Application stderr: {stderr}")
                return False

            time.sleep(self.check_interval)

        # If we get here, the application is stuck
        logger.error("⏰ Application startup timeout - application appears stuck")
        self.diagnose_stuck_issue()
        return False

    def stop(self):
        """Stop the monitoring and application"""
        logger.info("🛑 Stopping application and monitor...")
        self.is_running = False

        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
                logger.info("✅ Application stopped gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️  Application didn't stop gracefully, forcing...")
                self.process.kill()

        # Kill any remaining processes on the port
        try:
            subprocess.run(["lsof", "-ti", f":{self.port}"], capture_output=True)
            subprocess.run(["pkill", "-f", "python.*main_api_app"], capture_output=True)
        except:
            pass


def main():
    """Main monitoring function"""
    monitor = MainAppMonitor()

    try:
        # Start the application
        if not monitor.start_main_app():
            logger.error("Failed to start application")
            return 1

        # Wait for startup
        if monitor.wait_for_startup():
            logger.info("🚀 ATOM Main Application is running and healthy!")
            logger.info(f"🌐 Access at: http://localhost:{monitor.port}")
            logger.info("Press Ctrl+C to stop the application")

            # Keep monitoring while running
            while monitor.is_running:
                time.sleep(10)
                if not monitor.check_health():
                    logger.error("Application health check failed!")
                    break

        else:
            logger.error("Application failed to start properly")
            return 1

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Monitor error: {e}")
        return 1
    finally:
        monitor.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
