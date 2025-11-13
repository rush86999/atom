#!/usr/bin/env python3
"""
Enhanced ATOM Integration System Executor
Runs the complete enhanced integration system with monitoring
"""

import os
import sys
import json
import asyncio
import logging
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnhancedIntegrationSystem:
    """Enhanced ATOM Integration System Manager"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.backend_dir = self.project_root / "backend/python-api-service"
        self.frontend_dir = self.project_root / "frontend-nextjs"
        self.processes = {}
        self.running = False
        self.startup_time = None
        
    def setup_environment(self):
        """Setup environment variables for enhanced system"""
        logger.info("🔧 Setting up enhanced integration environment...")
        
        # Set environment variables
        env_vars = {
            'USE_BRIDGE_SYSTEM': 'true',
            'ENHANCED_HEALTH_MONITORING': 'true',
            'FLASK_ENV': 'development',
            'PYTHONPATH': str(self.backend_dir),
            'PYTHON_API_SERVICE_BASE_URL': 'http://localhost:5058',
            'FASTAPI_BASE_URL': 'http://localhost:8001',
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
            logger.info(f"  {key}={value}")
        
        # Create necessary directories
        (self.backend_dir / "logs").mkdir(exist_ok=True)
        (self.backend_dir / "reports").mkdir(exist_ok=True)
        
    def check_dependencies(self) -> bool:
        """Check if all dependencies are available"""
        logger.info("📦 Checking dependencies...")
        
        required_files = [
            "main_api_with_integrations.py",
            "enhanced_health_monitor.py",
            "enhanced_health_endpoints.py", 
            "enhanced_integration_service.py",
            "enhanced_hubspot_service.py",
            "enhanced_hubspot_routes.py",
            "flask_fastapi_bridge.py",
            "enhanced_integration_routes.py",
            "comprehensive_integration_tester.py",
        ]
        
        missing_files = []
        for file_name in required_files:
            file_path = self.backend_dir / file_name
            if not file_path.exists():
                missing_files.append(file_name)
        
        if missing_files:
            logger.error(f"❌ Missing required files: {missing_files}")
            return False
        
        # Check Python packages
        required_packages = [
            "flask", "httpx", "asyncpg", "aiofiles", 
            "python-dotenv", "pydantic", "fastapi"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            logger.error(f"❌ Missing required packages: {missing_packages}")
            logger.info("Install with: pip install " + " ".join(missing_packages))
            return False
        
        logger.info("✅ All dependencies satisfied")
        return True
    
    def start_backend_server(self) -> Optional[subprocess.Popen]:
        """Start the enhanced backend server"""
        logger.info("🚀 Starting enhanced backend server...")
        
        cmd = [
            sys.executable, 
            "-m", 
            "flask", 
            "--app", 
            "main_api_with_integrations:create_app()", 
            "run", 
            "--host=0.0.0.0", 
            "--port=5058", 
            "--debug"
        ]
        
        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.backend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=dict(os.environ)
            )
            
            # Give it time to start
            time.sleep(3)
            
            if process.poll() is None:
                logger.info("✅ Backend server started successfully")
                return process
            else:
                stdout, stderr = process.communicate()
                logger.error(f"❌ Backend server failed to start: {stderr}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to start backend server: {e}")
            return None
    
    def start_frontend_server(self) -> Optional[subprocess.Popen]:
        """Start the frontend server"""
        logger.info("🎨 Starting frontend server...")
        
        cmd = ["npm", "run", "dev"]
        
        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.frontend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=dict(os.environ)
            )
            
            # Give it time to start
            time.sleep(5)
            
            if process.poll() is None:
                logger.info("✅ Frontend server started successfully")
                return process
            else:
                stdout, stderr = process.communicate()
                logger.error(f"❌ Frontend server failed to start: {stderr}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to start frontend server: {e}")
            return None
    
    async def run_health_checks(self) -> Dict[str, Any]:
        """Run comprehensive health checks"""
        logger.info("🏥 Running comprehensive health checks...")
        
        try:
            # Import and run health checker
            sys.path.append(str(self.backend_dir))
            from comprehensive_integration_tester import ComprehensiveIntegrationTester
            
            tester = ComprehensiveIntegrationTester()
            
            # Run system health tests
            system_report = await tester.run_integration_tests('system')
            
            await tester.cleanup()
            
            return {
                "status": "completed",
                "system_health": system_report.__dict__,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def run_integration_tests(self) -> Dict[str, Any]:
        """Run comprehensive integration tests"""
        logger.info("🧪 Running comprehensive integration tests...")
        
        try:
            # Import and run integration tester
            sys.path.append(str(self.backend_dir))
            from comprehensive_integration_tester import ComprehensiveIntegrationTester
            
            tester = ComprehensiveIntegrationTester()
            report = await tester.run_all_tests()
            
            # Generate reports
            json_report = tester.generate_report_json(report)
            html_report = tester.generate_report_html(report)
            
            # Save reports
            reports_dir = self.backend_dir / "reports"
            with open(reports_dir / "integration_test_report.json", "w") as f:
                f.write(json_report)
            
            with open(reports_dir / "integration_test_report.html", "w") as f:
                f.write(html_report)
            
            await tester.cleanup()
            
            return {
                "status": "completed",
                "report": report.__dict__,
                "reports_saved": str(reports_dir),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Integration tests failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def monitor_system(self):
        """Monitor the running system"""
        logger.info("📊 Monitoring system health...")
        
        while self.running:
            try:
                # Check process health
                for name, process in self.processes.items():
                    if process and process.poll() is not None:
                        logger.warning(f"⚠️ Process {name} has stopped")
                        # Restart process if needed
                        if name == "backend":
                            new_process = self.start_backend_server()
                            if new_process:
                                self.processes[name] = new_process
                        elif name == "frontend":
                            new_process = self.start_frontend_server()
                            if new_process:
                                self.processes[name] = new_process
                
                # Log system status
                uptime = time.time() - self.startup_time if self.startup_time else 0
                logger.info(f"📈 System uptime: {uptime:.0f}s, Processes: {list(self.processes.keys())}")
                
                time.sleep(30)  # Check every 30 seconds
                
            except KeyboardInterrupt:
                logger.info("👋 Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}")
                time.sleep(10)
    
    def shutdown(self):
        """Gracefully shutdown the system"""
        logger.info("🛑 Shutting down enhanced integration system...")
        
        self.running = False
        
        # Terminate all processes
        for name, process in self.processes.items():
            if process:
                logger.info(f"🛑 Stopping {name} process...")
                try:
                    process.terminate()
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"⚠️ Force killing {name} process...")
                    process.kill()
                except Exception as e:
                    logger.error(f"❌ Error stopping {name}: {e}")
        
        logger.info("✅ System shutdown complete")
    
    def signal_handler(self, signum, frame):
        """Handle system signals"""
        logger.info(f"📡 Received signal {signum}")
        self.shutdown()
        sys.exit(0)
    
    async def run_complete_system(self):
        """Run the complete enhanced integration system"""
        logger.info("🌟 Starting ATOM Enhanced Integration System")
        self.startup_time = time.time()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Setup environment
            self.setup_environment()
            
            # Check dependencies
            if not self.check_dependencies():
                return False
            
            # Start servers
            backend_process = self.start_backend_server()
            if not backend_process:
                logger.error("❌ Failed to start backend server")
                return False
            
            self.processes["backend"] = backend_process
            
            # Optionally start frontend
            start_frontend = os.getenv("START_FRONTEND", "false").lower() == "true"
            if start_frontend:
                frontend_process = self.start_frontend_server()
                if frontend_process:
                    self.processes["frontend"] = frontend_process
            
            # Wait for servers to be ready
            logger.info("⏳ Waiting for servers to be ready...")
            await asyncio.sleep(5)
            
            # Run health checks
            logger.info("🏥 Running initial health checks...")
            health_results = await self.run_health_checks()
            if health_results["status"] == "completed":
                logger.info("✅ Health checks passed")
            else:
                logger.warning("⚠️ Some health checks failed")
            
            # Run integration tests
            logger.info("🧪 Running integration tests...")
            test_results = await self.run_integration_tests()
            if test_results["status"] == "completed":
                logger.info("✅ Integration tests completed")
                if test_results["reports_saved"]:
                    logger.info(f"📄 Test reports saved to {test_results['reports_saved']}")
            else:
                logger.warning("⚠️ Some integration tests failed")
            
            # Start monitoring
            self.running = True
            logger.info("👀 Starting system monitoring (Ctrl+C to stop)...")
            
            # Print system information
            print(f"\n{'='*60}")
            print("🌟 ATOM ENHANCED INTEGRATION SYSTEM RUNNING")
            print(f"{'='*60}")
            print(f"🚀 Backend Server: http://localhost:5058")
            if start_frontend:
                print(f"🎨 Frontend Server: http://localhost:3000")
            print(f"🔗 Bridge System: http://localhost:5058/api/bridge")
            print(f"🏥 Health Overview: http://localhost:5058/api/enhanced/health/overview")
            print(f"📊 System Status: http://localhost:5058/api/enhanced/management/status")
            print(f"🧪 Test Reports: {self.backend_dir}/reports/")
            print(f"⏰ Uptime: {time.time() - self.startup_time:.0f}s")
            print(f"{'='*60}")
            
            # Monitor system
            self.monitor_system()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ System startup failed: {e}")
            return False
        finally:
            self.shutdown()
    
    async def run_tests_only(self):
        """Run only the integration tests"""
        logger.info("🧪 Running integration tests only...")
        
        if not self.check_dependencies():
            return False
        
        test_results = await self.run_integration_tests()
        
        if test_results["status"] == "completed":
            logger.info("✅ Integration tests completed successfully")
            if test_results["reports_saved"]:
                logger.info(f"📄 Test reports saved to {test_results['reports_saved']}")
            return True
        else:
            logger.error("❌ Integration tests failed")
            return False

async def main():
    """Main entry point"""
    system = EnhancedIntegrationSystem()
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "test":
            success = await system.run_tests_only()
        elif command == "system":
            success = await system.run_complete_system()
        elif command == "health":
            health_results = await system.run_health_checks()
            success = health_results["status"] == "completed"
        else:
            logger.error(f"❌ Unknown command: {command}")
            logger.info("Usage: python enhanced_integration_system.py [test|system|health]")
            sys.exit(1)
    else:
        # Default: run complete system
        success = await system.run_complete_system()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())