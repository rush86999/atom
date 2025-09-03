#!/usr/bin/env python3
"""
Startup Script for Desktop Backend Service
Handles process management and ensures the backend service is running
"""

import os
import sys
import subprocess
import time
import signal
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('desktop-backend-startup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DesktopBackendManager:
    def __init__(self):
        self.backend_process = None
        self.backend_port = 8083
        self.backend_host = '127.0.0.1'
        self.python_executable = sys.executable
        self.backend_script = Path(__file__).parent / 'main.py'

    def is_backend_running(self) -> bool:
        """Check if backend is already running"""
        try:
            import requests
            response = requests.get(f'http://{self.backend_host}:{self.backend_port}/health', timeout=2)
            return response.status_code == 200
        except:
            return False

    def install_dependencies(self) -> bool:
        """Install required Python dependencies"""
        try:
            requirements_file = Path(__file__).parent / 'requirements.txt'
            if requirements_file.exists():
                logger.info("Installing Python dependencies...")
                result = subprocess.run([
                    self.python_executable, '-m', 'pip', 'install', '-r', str(requirements_file)
                ], capture_output=True, text=True, cwd=Path(__file__).parent)

                if result.returncode == 0:
                    logger.info("Dependencies installed successfully")
                    return True
                else:
                    logger.error(f"Failed to install dependencies: {result.stderr}")
                    return False
            else:
                logger.warning("Requirements file not found, skipping dependency installation")
                return True
        except Exception as e:
            logger.error(f"Error installing dependencies: {e}")
            return False

    def start_backend(self) -> bool:
        """Start the backend service"""
        if self.is_backend_running():
            logger.info("Backend service is already running")
            return True

        if not self.install_dependencies():
            logger.error("Failed to install dependencies, cannot start backend")
            return False

        try:
            logger.info("Starting desktop backend service...")
            self.backend_process = subprocess.Popen([
                self.python_executable, str(self.backend_script)
            ], cwd=Path(__file__).parent)

            # Wait for backend to start
            for _ in range(10):
                time.sleep(1)
                if self.is_backend_running():
                    logger.info("Desktop backend service started successfully")
                    return True

            logger.error("Backend service failed to start within timeout")
            self.stop_backend()
            return False

        except Exception as e:
            logger.error(f"Failed to start backend service: {e}")
            return False

    def stop_backend(self):
        """Stop the backend service"""
        if self.backend_process:
            try:
                logger.info("Stopping desktop backend service...")
                self.backend_process.terminate()
                self.backend_process.wait(timeout=10)
                logger.info("Backend service stopped successfully")
            except subprocess.TimeoutExpired:
                logger.warning("Backend process did not terminate gracefully, forcing kill")
                self.backend_process.kill()
            except Exception as e:
                logger.error(f"Error stopping backend process: {e}")
            finally:
                self.backend_process = None

    def restart_backend(self) -> bool:
        """Restart the backend service"""
        self.stop_backend()
        return self.start_backend()

    def signal_handler(self, signum, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop_backend()
        sys.exit(0)

def main():
    """Main entry point"""
    manager = DesktopBackendManager()

    # Set up signal handlers
    signal.signal(signal.SIGINT, manager.signal_handler)
    signal.signal(signal.SIGTERM, manager.signal_handler)

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Desktop Backend Service Manager')
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status'],
                       nargs='?', default='start', help='Action to perform')

    args = parser.parse_args()

    if args.action == 'start':
        success = manager.start_backend()
        if success:
            # Keep the process running to manage the backend
            try:
                while True:
                    time.sleep(1)
                    if not manager.is_backend_running() and manager.backend_process:
                        logger.warning("Backend service stopped unexpectedly")
                        break
            except KeyboardInterrupt:
                logger.info("Shutting down by user request")
                manager.stop_backend()
        else:
            sys.exit(1)

    elif args.action == 'stop':
        manager.stop_backend()

    elif args.action == 'restart':
        success = manager.restart_backend()
        sys.exit(0 if success else 1)

    elif args.action == 'status':
        if manager.is_backend_running():
            print("Backend service is running")
            sys.exit(0)
        else:
            print("Backend service is not running")
            sys.exit(1)

if __name__ == '__main__':
    main()
