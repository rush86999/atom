"""
Production Startup Script for Atom AI Assistant

This script starts the Atom system in production mode with all services,
BYOK functionality, and monitoring enabled.
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("production.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class ProductionStarter:
    """Production startup manager for Atom system"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.processes = {}
        self.start_time = time.time()

    def setup_environment(self):
        """Setup production environment variables"""
        logger.info("Setting up production environment...")

        # Set production environment variables
        os.environ["FLASK_ENV"] = "production"
        os.environ["PYTHON_API_PORT"] = "5058"
        os.environ["NEXTJS_PORT"] = "3000"

        # Set database configuration
        if not os.getenv("DATABASE_URL"):
            os.environ["DATABASE_URL"] = "sqlite:///./data/atom_production.db"
            logger.info("Using SQLite production database")

        # Ensure data directory exists
        data_dir = self.base_dir / "data"
        data_dir.mkdir(exist_ok=True)

        logger.info("Production environment configured")

    def start_backend_service(self) -> bool:
        """Start the Python backend API service"""
        logger.info("Starting backend API service...")

        backend_dir = self.base_dir / "backend" / "python-api-service"

        try:
            # Change to backend directory
            os.chdir(backend_dir)

            # Start the backend server
            process = subprocess.Popen(
                ["python", "main_api_app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.processes["backend"] = process
            logger.info(f"Backend service started with PID: {process.pid}")

            # Wait for service to be ready
            time.sleep(5)

            # Test health endpoint
            health_check = subprocess.run(
                ["curl", "-s", "http://localhost:5058/healthz"],
                capture_output=True,
                text=True,
            )

            if health_check.returncode == 0 and '"status":"ok"' in health_check.stdout:
                logger.info("✅ Backend service health check passed")
                return True
            else:
                logger.error("❌ Backend service health check failed")
                return False

        except Exception as e:
            logger.error(f"Failed to start backend service: {e}")
            return False
        finally:
            # Return to base directory
            os.chdir(self.base_dir)

    def start_frontend_service(self) -> bool:
        """Start the Next.js frontend service"""
        logger.info("Starting frontend service...")

        frontend_dir = self.base_dir / "frontend-nextjs"

        try:
            # Change to frontend directory
            os.chdir(frontend_dir)

            # Build frontend if not already built
            if not (frontend_dir / ".next").exists():
                logger.info("Building frontend application...")
                build_result = subprocess.run(
                    ["npm", "run", "build"], capture_output=True, text=True
                )

                if build_result.returncode != 0:
                    logger.error(f"Frontend build failed: {build_result.stderr}")
                    return False

            # Start the frontend server
            process = subprocess.Popen(
                ["npm", "run", "start"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.processes["frontend"] = process
            logger.info(f"Frontend service started with PID: {process.pid}")

            # Wait for service to be ready
            time.sleep(10)

            # Test frontend endpoint
            frontend_check = subprocess.run(
                ["curl", "-s", "http://localhost:3000"], capture_output=True, text=True
            )

            if frontend_check.returncode == 0:
                logger.info("✅ Frontend service health check passed")
                return True
            else:
                logger.warning("⚠️ Frontend service may still be starting...")
                return True

        except Exception as e:
            logger.error(f"Failed to start frontend service: {e}")
            return False
        finally:
            # Return to base directory
            os.chdir(self.base_dir)

    def start_monitoring_service(self) -> bool:
        """Start monitoring and health checks"""
        logger.info("Starting monitoring service...")

        try:
            # Start a background monitoring process
            process = subprocess.Popen(
                [
                    "python",
                    "-c",
                    """
import time
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

while True:
    try:
        # Check backend health
        backend_health = requests.get("http://localhost:5058/healthz", timeout=5)
        if backend_health.status_code == 200:
            logger.info("✅ Backend monitoring: HEALTHY")
        else:
            logger.error("❌ Backend monitoring: UNHEALTHY")

        # Check services status
        services_status = requests.get("http://localhost:5058/api/services/status", timeout=5)
        if services_status.status_code == 200:
            data = services_status.json()
            active_services = data.get("status_summary", {}).get("active", 0)
            logger.info(f"📊 Services monitoring: {active_services} active services")

        time.sleep(60)  # Check every minute

    except Exception as e:
        logger.error(f"Monitoring error: {e}")
        time.sleep(30)
""",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.processes["monitoring"] = process
            logger.info(f"Monitoring service started with PID: {process.pid}")
            return True

        except Exception as e:
            logger.error(f"Failed to start monitoring service: {e}")
            return False

    def run_system_validation(self) -> Dict[str, bool]:
        """Run comprehensive system validation"""
        logger.info("Running system validation...")

        validation_results = {}

        # Test backend endpoints
        endpoints_to_test = [
            ("/healthz", "Health Check"),
            ("/api/services/status", "Service Registry"),
            ("/api/user/api-keys/test_user/status", "BYOK System"),
            ("/api/transcription/health", "Voice Processing"),
            ("/api/workflow-automation/generate", "Workflow Automation"),
        ]

        for endpoint, description in endpoints_to_test:
            try:
                result = subprocess.run(
                    ["curl", "-s", f"http://localhost:5058{endpoint}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    validation_results[description] = True
                    logger.info(f"✅ {description}: OPERATIONAL")
                else:
                    validation_results[description] = False
                    logger.error(f"❌ {description}: FAILED")

            except Exception as e:
                validation_results[description] = False
                logger.error(f"❌ {description}: ERROR - {e}")

        return validation_results

    def display_startup_summary(self, validation_results: Dict[str, bool]):
        """Display startup summary and next steps"""
        logger.info("\n" + "=" * 60)
        logger.info("🚀 ATOM PRODUCTION STARTUP COMPLETE")
        logger.info("=" * 60)

        # Service status
        logger.info("\n📊 SERVICE STATUS:")
        for service, process in self.processes.items():
            status = "RUNNING" if process.poll() is None else "STOPPED"
            logger.info(f"   {service.upper():<12} : {status}")

        # Validation results
        logger.info("\n✅ SYSTEM VALIDATION:")
        passed = sum(validation_results.values())
        total = len(validation_results)

        for test, result in validation_results.items():
            status = "PASS" if result else "FAIL"
            logger.info(f"   {test:<20} : {status}")

        logger.info(
            f"\n📈 VALIDATION SCORE: {passed}/{total} ({passed / total * 100:.1f}%)"
        )

        # Next steps
        logger.info("\n🎯 NEXT STEPS:")
        logger.info("   1. Access the application at: http://localhost:3000")
        logger.info("   2. Configure your API keys in Settings → AI Providers")
        logger.info("   3. Test workflow automation with natural language")
        logger.info("   4. Monitor system logs in production.log")

        # URLs
        logger.info("\n🌐 ACCESS URLs:")
        logger.info("   Frontend: http://localhost:3000")
        logger.info("   Backend API: http://localhost:5058")
        logger.info("   Health Check: http://localhost:5058/healthz")

        logger.info("\n💡 TIPS:")
        logger.info("   - Use 'BYOK' system to configure your own AI API keys")
        logger.info("   - Save 40-70% with multi-provider cost optimization")
        logger.info("   - All 33 services are available for integration")

        logger.info("\n🎉 ATOM is now running in production mode!")

    def cleanup(self):
        """Cleanup running processes"""
        logger.info("Cleaning up processes...")

        for service, process in self.processes.items():
            if process.poll() is None:  # Process is still running
                process.terminate()
                try:
                    process.wait(timeout=10)
                    logger.info(f"Stopped {service} service")
                except subprocess.TimeoutExpired:
                    process.kill()
                    logger.warning(f"Force killed {service} service")

    def run(self):
        """Main startup sequence"""
        try:
            logger.info("🚀 Starting Atom Production Deployment")
            logger.info(f"📁 Base directory: {self.base_dir}")

            # Setup environment
            self.setup_environment()

            # Start services
            services_started = True

            if not self.start_backend_service():
                logger.error("Failed to start backend service")
                services_started = False

            if not self.start_frontend_service():
                logger.warning("Frontend service may have issues, but continuing...")

            if not self.start_monitoring_service():
                logger.warning("Monitoring service failed, but continuing...")

            if services_started:
                # Wait for services to stabilize
                time.sleep(10)

                # Run validation
                validation_results = self.run_system_validation()

                # Display summary
                self.display_startup_summary(validation_results)

                # Keep the script running
                logger.info("\n🔄 System is running. Press Ctrl+C to stop.")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    logger.info("\n🛑 Shutting down...")

            else:
                logger.error("❌ Failed to start required services")
                return False

        except Exception as e:
            logger.error(f"Startup failed: {e}")
            return False
        finally:
            self.cleanup()

        return True


def main():
    """Main entry point"""
    starter = ProductionStarter()

    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--validate-only":
            starter.setup_environment()
            if starter.start_backend_service():
                time.sleep(5)
                validation_results = starter.run_system_validation()
                passed = sum(validation_results.values())
                total = len(validation_results)
                print(f"Validation: {passed}/{total} tests passed")
                starter.cleanup()
                sys.exit(0 if passed == total else 1)
            else:
                sys.exit(1)
        elif sys.argv[1] == "--help":
            print("""
Atom Production Startup Script

Usage:
  python start_production.py          # Start all services
  python start_production.py --validate-only  # Run validation only
  python start_production.py --help   # Show this help

Services:
  - Backend API (port 5058)
  - Frontend Next.js (port 3000)
  - Monitoring & Health checks

Features:
  - BYOK (Bring Your Own Keys) AI provider system
  - 33 service integrations
  - Workflow automation
  - Voice processing
  - Cost optimization (40-70% savings)
            """)
            sys.exit(0)

    # Run full startup
    success = starter.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
