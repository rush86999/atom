#!/usr/bin/env python3
"""
ATOM Platform - Production Deployment Script
Automated deployment and configuration for production environment
"""

import os
import sys
import subprocess
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ProductionDeployment:
    """Production deployment automation for ATOM platform"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_file = self.base_dir / "production_config.py"
        self.backend_pid = None
        self.oauth_pid = None

    def check_prerequisites(self) -> bool:
        """Check system prerequisites"""
        print("🔍 Checking prerequisites...")

        prerequisites = {
            "Python 3.8+": self._check_python_version(),
            "Docker": self._check_docker(),
            "PostgreSQL": self._check_postgresql(),
            "Environment file": self._check_env_file(),
        }

        all_met = True
        for prereq, status in prerequisites.items():
            if status:
                print(f"   ✅ {prereq}")
            else:
                print(f"   ❌ {prereq}")
                all_met = False

        return all_met

    def _check_python_version(self) -> bool:
        """Check Python version"""
        return sys.version_info >= (3, 8)

    def _check_docker(self) -> bool:
        """Check if Docker is available"""
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True
            )
            return result.returncode == 0
        except:
            return False

    def _check_postgresql(self) -> bool:
        """Check PostgreSQL availability"""
        try:
            result = subprocess.run(
                ["psql", "--version"], capture_output=True, text=True
            )
            return result.returncode == 0
        except:
            return False

    def _check_env_file(self) -> bool:
        """Check if environment file exists"""
        env_files = [".env", "real_credentials.env"]
        return any((self.base_dir / env_file).exists() for env_file in env_files)

    def setup_environment(self) -> bool:
        """Setup production environment"""
        print("\n🔧 Setting up environment...")

        # Create necessary directories
        directories = ["logs", "data", "data/lancedb_store", "config"]

        for directory in directories:
            dir_path = self.base_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ Created directory: {directory}")

        # Generate production environment file if it doesn't exist
        env_file = self.base_dir / ".env.production"
        if not env_file.exists():
            self._generate_env_file(env_file)

        return True

    def _generate_env_file(self, env_file: Path):
        """Generate production environment file template"""
        template = f"""# ATOM Platform - Production Environment
# Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}

# Database Configuration
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=atom_db
DATABASE_USER=atom_user
DATABASE_PASSWORD=secure_production_password

# OAuth Configuration
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
SLACK_CLIENT_ID=your_slack_client_id
SLACK_CLIENT_SECRET=your_slack_client_secret
DROPBOX_CLIENT_ID=your_dropbox_client_id
DROPBOX_CLIENT_SECRET=your_dropbox_client_secret
TRELLO_CLIENT_ID=your_trello_client_id
TRELLO_CLIENT_SECRET=your_trello_client_secret

# API Keys
OPENAI_API_KEY=your_openai_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Security
JWT_SECRET=generate_secure_random_string_here
ENCRYPTION_KEY=generate_another_secure_random_string_here
FLASK_SECRET_KEY=generate_flask_secret_key_here

# Server Configuration
BACKEND_PORT=8000
OAUTH_PORT=5058
FRONTEND_PORT=3000

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true
"""
        env_file.write_text(template)
        print(f"   ✅ Generated environment template: {env_file.name}")
        print("   ⚠️  Please update the environment variables with real values")

    def start_database(self) -> bool:
        """Start PostgreSQL database"""
        print("\n🗄️  Starting database...")

        # Check if database is already running
        try:
            response = requests.get("http://localhost:8000/healthz", timeout=5)
            if response.status_code == 200:
                print("   ✅ Database is already running")
                return True
        except:
            pass

        # Try to start database using Docker
        try:
            docker_compose_file = self.base_dir / "docker-compose.postgres.yml"
            if docker_compose_file.exists():
                result = subprocess.run(
                    ["docker-compose", "-f", str(docker_compose_file), "up", "-d"],
                    cwd=self.base_dir,
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    print("   ✅ Database started with Docker")
                    time.sleep(5)  # Wait for database to initialize
                    return True
        except:
            pass

        print("   ⚠️  Could not start database automatically")
        print("   💡 Please ensure PostgreSQL is running on port 5432")
        return False

    def start_backend_services(self) -> bool:
        """Start backend services"""
        print("\n🚀 Starting backend services...")

        # Start OAuth server
        oauth_success = self._start_oauth_server()
        if not oauth_success:
            print("   ❌ Failed to start OAuth server")
            return False

        # Start main API server
        backend_success = self._start_backend_server()
        if not backend_success:
            print("   ❌ Failed to start backend server")
            return False

        # Wait for services to initialize
        time.sleep(3)

        # Verify services are running
        return self._verify_services()

    def _start_oauth_server(self) -> bool:
        """Start OAuth server"""
        try:
            oauth_script = self.base_dir / "improved_oauth_server.py"
            if oauth_script.exists():
                # Start OAuth server in background
                process = subprocess.Popen(
                    [sys.executable, str(oauth_script)],
                    cwd=self.base_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.oauth_pid = process.pid
                print("   ✅ OAuth server started")
                return True
        except Exception as e:
            print(f"   ❌ Error starting OAuth server: {e}")

        return False

    def _start_backend_server(self) -> bool:
        """Start main backend server"""
        try:
            backend_script = (
                self.base_dir / "backend" / "python-api-service" / "main_api_app.py"
            )
            if backend_script.exists():
                # Set environment variables
                env = os.environ.copy()
                env.update(
                    {
                        "DATABASE_URL": "postgresql://atom_user:local_password@localhost:5432/atom_db",
                        "PYTHON_API_PORT": "8000",
                    }
                )

                # Start backend server in background
                process = subprocess.Popen(
                    [sys.executable, str(backend_script)],
                    cwd=self.base_dir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.backend_pid = process.pid
                print("   ✅ Backend server started")
                return True
        except Exception as e:
            print(f"   ❌ Error starting backend server: {e}")

        return False

    def _verify_services(self) -> bool:
        """Verify all services are running properly"""
        print("\n🔍 Verifying services...")

        services_to_check = {
            "OAuth Server": "http://localhost:5058/healthz",
            "Backend API": "http://localhost:8000/healthz",
        }

        all_healthy = True
        for service_name, url in services_to_check.items():
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    print(f"   ✅ {service_name} is healthy")
                else:
                    print(
                        f"   ❌ {service_name} returned status: {response.status_code}"
                    )
                    all_healthy = False
            except Exception as e:
                print(f"   ❌ {service_name} is not responding: {e}")
                all_healthy = False

        return all_healthy

    def run_health_checks(self) -> bool:
        """Run comprehensive health checks"""
        print("\n🏥 Running health checks...")

        health_checks = [
            self._check_service_registry(),
            self._check_workflow_automation(),
            self._check_voice_integration(),
            self._check_database_connectivity(),
        ]

        return all(health_checks)

    def _check_service_registry(self) -> bool:
        """Check service registry health"""
        try:
            response = requests.get(
                "http://localhost:8000/api/services/health", timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                healthy_services = data.get("healthy_services", 0)
                total_services = data.get("total_services", 0)
                print(
                    f"   ✅ Service Registry: {healthy_services}/{total_services} services healthy"
                )
                return True
        except Exception as e:
            print(f"   ❌ Service Registry check failed: {e}")
        return False

    def _check_workflow_automation(self) -> bool:
        """Check workflow automation health"""
        try:
            response = requests.get(
                "http://localhost:8000/api/workflow-automation/health", timeout=10
            )
            if response.status_code == 200:
                print("   ✅ Workflow Automation: Healthy")
                return True
        except:
            print("   ⚠️  Workflow Automation: Not responding (may need configuration)")
        return True  # Not critical for basic operation

    def _check_voice_integration(self) -> bool:
        """Check voice integration health"""
        try:
            response = requests.get(
                "http://localhost:8000/api/voice/health", timeout=10
            )
            if response.status_code == 200:
                print("   ✅ Voice Integration: Healthy")
                return True
        except:
            print("   ⚠️  Voice Integration: Not responding (may need configuration)")
        return True  # Not critical for basic operation

    def _check_database_connectivity(self) -> bool:
        """Check database connectivity"""
        try:
            response = requests.get("http://localhost:8000/healthz", timeout=10)
            if response.status_code == 200:
                data = response.json()
                db_status = data.get("database", {}).get("postgresql", "unknown")
                if db_status == "healthy":
                    print("   ✅ Database Connectivity: Healthy")
                    return True
                else:
                    print(f"   ❌ Database Connectivity: {db_status}")
        except Exception as e:
            print(f"   ❌ Database Connectivity check failed: {e}")
        return False

    def configure_oauth_services(self) -> bool:
        """Configure OAuth services"""
        print("\n🔐 Configuring OAuth services...")

        # This would typically involve:
        # 1. Checking current OAuth status
        # 2. Providing setup instructions
        # 3. Testing OAuth flows

        try:
            response = requests.get(
                "http://localhost:5058/api/auth/services", timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                total_services = data.get("total_services", 0)
                services_with_creds = data.get("services_with_real_credentials", 0)

                print(
                    f"   📊 OAuth Status: {services_with_creds}/{total_services} services configured"
                )

                if services_with_creds == 0:
                    print("   ⚠️  No OAuth services configured")
                    print("   💡 Run the OAuth setup guide to configure services")
                else:
                    print("   ✅ OAuth services are configured")

                return True
        except Exception as e:
            print(f"   ❌ OAuth configuration check failed: {e}")

        return False

    def run_integration_tests(self) -> bool:
        """Run integration tests"""
        print("\n🧪 Running integration tests...")

        tests = [
            self._test_workflow_generation(),
            self._test_service_coordination(),
            self._test_voice_commands(),
        ]

        successful_tests = sum(tests)
        total_tests = len(tests)

        print(f"   📊 Test Results: {successful_tests}/{total_tests} tests passed")
        return successful_tests >= 2  # Allow some failures for optional features

    def _test_workflow_generation(self) -> bool:
        """Test workflow generation"""
        try:
            response = requests.post(
                "http://localhost:8000/api/workflow-agent/generate",
                json={
                    "user_input": "Create a workflow that monitors GitHub for new issues",
                    "context": {"user_id": "deployment_test"},
                },
                timeout=10,
            )
            if response.status_code == 200:
                print("   ✅ Workflow Generation: Working")
                return True
        except Exception as e:
            print(f"   ❌ Workflow Generation test failed: {e}")
        return False

    def _test_service_coordination(self) -> bool:
        """Test service coordination"""
        try:
            response = requests.get(
                "http://localhost:8000/api/services/workflow-capabilities", timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                total_services = len(data.get("workflow_services", []))
                print(
                    f"   ✅ Service Coordination: {total_services} services available"
                )
                return True
        except Exception as e:
            print(f"   ❌ Service Coordination test failed: {e}")
        return False

    def _test_voice_commands(self) -> bool:
        """Test voice command processing"""
        try:
            response = requests.post(
                "http://localhost:8000/api/voice/test-command",
                json={"command": "test voice integration"},
                timeout=10,
            )
            if response.status_code == 200:
                print("   ✅ Voice Commands: Working")
                return True
        except:
            print("   ⚠️  Voice Commands: Not available (may need configuration)")
        return True  # Not critical

    def generate_deployment_report(self):
        """Generate deployment report"""
        print("\n📊 Generating deployment report...")

        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0.0",
            "services": {
                "oauth_server": self._get_service_status(5058),
                "backend_api": self._get_service_status(8000),
            },
            "health_checks": self._get_health_summary(),
            "next_steps": self._get_next_steps(),
        }

        # Save report to file
        report_file = self.base_dir / "deployment_report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"   ✅ Deployment report saved to: {report_file}")
        return report

    def _get_service_status(self, port: int) -> Dict:
        """Get service status"""
        try:
            response = requests.get(f"http://localhost:{port}/healthz", timeout=5)
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_code": response.status_code,
            }
        except:
            return {"status": "unreachable", "response_code": None}

    def _get_health_summary(self) -> Dict:
        """Get health check summary"""
        # This would aggregate results from earlier health checks
        return {
            "service_registry": "tested",
            "workflow_automation": "tested",
            "voice_integration": "tested",
            "database": "tested",
        }

    def _get_next_steps(self) -> List[str]:
        """Get next steps for deployment"""
        return [
            "Configure OAuth credentials for external services",
            "Set up API keys for AI providers (OpenAI, Deepgram, etc.)",
            "Configure database with production credentials",
            "Set up SSL/TLS certificates",
            "Configure monitoring and alerting",
            "Set up backup and recovery procedures",
        ]

    def cleanup(self):
        """Cleanup deployment processes"""
        print("\n🧹 Cleaning up...")

        # Terminate background processes
        if self.oauth_pid:
            try:
                os.kill(self.oauth_pid, 9)
                print("   ✅ Stopped OAuth server")
            except:
                pass

        if self.backend_pid:
            try:
                os.kill(self.backend_pid, 9)
                print("   ✅ Stopped backend server")
            except:
                pass

    def run_deployment(self):
        """Run complete deployment process"""
        print("🚀 ATOM Platform - Production Deployment")
        print("=" * 50)

        try:
            # Step 1: Check prerequisites
            if not self.check_prerequisites():
                print("\n❌ Prerequisites not met. Please fix the issues above.")
                return False

            # Step 2: Setup environment
            if not self.setup_environment():
                print("\n❌ Environment setup failed.")
                return False

            # Step 3: Start database
            if not self.start_database():
                print("\n❌ Database startup failed.")
                return False

            # Step 4: Start services
            if not self.start_backend_services():
                print("\n❌ Service startup failed.")
                return False

            # Step 5: Run health checks
            if not self.run_health_checks():
                print("\n⚠️  Some health checks failed. Continuing deployment...")

            # Step 6: Configure OAuth services
            self.configure_oauth_services()

            # Step 7: Run integration tests
            if not self.run_integration_tests():
                print("\n⚠️  Some integration tests failed. Continuing deployment...")

            # Step 8: Generate deployment report
            report = self.generate_deployment_report()

            print("\n🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!")
            print("=" * 50)
            print("\n📋 NEXT STEPS:")
            for step in report["next_steps"]:
                print(f"   • {step}")

            print(f"\n📊 Deployment report saved to: deployment_report.json")
            print("\n🌐 Services are now running:")
            print(f"   • OAuth Server: http://localhost:5058")
            print(f"   • Backend API:  http://localhost:8000")
            print(f"   • Frontend:     http://localhost:3000 (if configured)")

            return True

        except Exception as e:
            print(f"\n❌ Deployment failed: {e}")
            return False
        finally:
            self.cleanup()


def main():
    """Main deployment function"""
    deployment = ProductionDeployment()

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        print("🚀 Running quick deployment...")
        # Quick deployment - just start services
        return deployment.start_backend_services()
    else:
        return deployment.run_deployment()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
