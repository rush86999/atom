"""
Stripe Integration Setup Script
Comprehensive setup and configuration script for Stripe payment processing integration
"""

import os
import sys
import json
import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import subprocess
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("stripe_setup.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class StripeIntegrationSetup:
    """Comprehensive setup class for Stripe integration"""

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.integrations_dir = os.path.join(self.base_dir, "integrations")
        self.python_api_dir = os.path.join(self.base_dir, "python-api-service")
        self.env_file = os.path.join(self.base_dir, ".env")
        self.setup_results = {
            "timestamp": datetime.now().isoformat(),
            "steps": [],
            "success": True,
            "environment_configured": False,
        }

    def log_step(self, step_name: str, success: bool, details: str = ""):
        """Log setup step result"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        step_result = {
            "step": step_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        }
        self.setup_results["steps"].append(step_result)

        print(f"{status} {step_name}")
        if details:
            print(f"   Details: {details}")

        if not success:
            self.setup_results["success"] = False

    def check_prerequisites(self) -> bool:
        """Check system prerequisites"""
        print("\n🔍 Checking Prerequisites...")

        # Check Python version
        try:
            python_version = sys.version_info
            if python_version.major >= 3 and python_version.minor >= 8:
                self.log_step(
                    "Python Version Check",
                    True,
                    f"Python {python_version.major}.{python_version.minor}.{python_version.micro}",
                )
            else:
                self.log_step(
                    "Python Version Check",
                    False,
                    f"Python 3.8+ required, found {python_version.major}.{python_version.minor}",
                )
                return False
        except Exception as e:
            self.log_step("Python Version Check", False, f"Error: {str(e)}")
            return False

        # Check required directories
        required_dirs = [self.integrations_dir, self.python_api_dir]
        for dir_path in required_dirs:
            if os.path.exists(dir_path):
                self.log_step(f"Directory Check: {os.path.basename(dir_path)}", True)
            else:
                self.log_step(
                    f"Directory Check: {os.path.basename(dir_path)}",
                    False,
                    "Directory not found",
                )
                return False

        # Check if Stripe files exist
        stripe_files = [
            os.path.join(self.integrations_dir, "stripe_routes.py"),
            os.path.join(self.python_api_dir, "stripe_service.py"),
            os.path.join(self.integrations_dir, "test_stripe_integration.py"),
        ]

        for file_path in stripe_files:
            if os.path.exists(file_path):
                self.log_step(f"File Check: {os.path.basename(file_path)}", True)
            else:
                self.log_step(
                    f"File Check: {os.path.basename(file_path)}",
                    False,
                    "File not found",
                )
                return False

        return True

    def install_dependencies(self) -> bool:
        """Install required Python dependencies"""
        print("\n📦 Installing Dependencies...")

        dependencies = [
            "stripe>=8.0.0",
            "fastapi>=0.100.0",
            "uvicorn>=0.23.0",
            "requests>=2.31.0",
            "loguru>=0.7.0",
            "pydantic>=2.0.0",
            "python-multipart>=0.0.6",
            "python-jose[cryptography]>=3.3.0",
            "passlib[bcrypt]>=1.7.4",
        ]

        try:
            import importlib
            import pkg_resources

            for dep in dependencies:
                package_name = dep.split(">=")[0].split("[")[0]
                try:
                    importlib.import_module(package_name.replace("-", "_"))
                    self.log_step(
                        f"Dependency: {package_name}", True, "Already installed"
                    )
                except ImportError:
                    self.log_step(f"Dependency: {package_name}", False, "Not installed")
                    return False

            self.log_step(
                "All Dependencies", True, "All required packages are available"
            )
            return True

        except Exception as e:
            self.log_step("Dependency Check", False, f"Error: {str(e)}")
            return False

    def setup_environment(self, stripe_config: Dict[str, str]) -> bool:
        """Setup environment configuration"""
        print("\n⚙️  Setting Up Environment...")

        try:
            # Check if .env file exists
            if os.path.exists(self.env_file):
                self.log_step("Environment File", True, ".env file already exists")
            else:
                # Create .env file from template
                template_path = os.path.join(self.base_dir, ".env.template")
                if os.path.exists(template_path):
                    with open(template_path, "r") as f:
                        template_content = f.read()

                    # Replace template values with actual configuration
                    env_content = template_content
                    for key, value in stripe_config.items():
                        env_content = env_content.replace(f"your_{key}_here", value)

                    with open(self.env_file, "w") as f:
                        f.write(env_content)

                    self.log_step(
                        "Environment File", True, "Created .env file from template"
                    )
                else:
                    self.log_step("Environment File", False, "Template file not found")
                    return False

            # Set environment variables
            for key, value in stripe_config.items():
                os.environ[key] = value

            self.setup_results["environment_configured"] = True
            self.log_step("Environment Variables", True, "Environment variables set")
            return True

        except Exception as e:
            self.log_step("Environment Setup", False, f"Error: {str(e)}")
            return False

    def test_integration(self) -> bool:
        """Test Stripe integration functionality"""
        print("\n🧪 Testing Integration...")

        try:
            # Run the integration tests
            test_script = os.path.join(
                self.integrations_dir, "test_stripe_integration.py"
            )

            if not os.path.exists(test_script):
                self.log_step("Integration Test", False, "Test script not found")
                return False

            # Run the test script
            result = subprocess.run(
                [sys.executable, test_script],
                cwd=self.integrations_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                self.log_step("Integration Test", True, "All tests passed")

                # Parse test results
                try:
                    results_file = os.path.join(
                        self.integrations_dir, "stripe_integration_test_results.json"
                    )
                    if os.path.exists(results_file):
                        with open(results_file, "r") as f:
                            test_results = json.load(f)
                        passed = test_results["test_run"]["passed_tests"]
                        total = test_results["test_run"]["total_tests"]
                        self.log_step(
                            "Test Results", True, f"{passed}/{total} tests passed"
                        )
                except Exception as e:
                    logger.warning(f"Could not parse test results: {e}")

                return True
            else:
                self.log_step(
                    "Integration Test", False, f"Tests failed: {result.stderr}"
                )
                return False

        except subprocess.TimeoutExpired:
            self.log_step("Integration Test", False, "Test execution timed out")
            return False
        except Exception as e:
            self.log_step("Integration Test", False, f"Error: {str(e)}")
            return False

    def verify_api_integration(self) -> bool:
        """Verify API integration with main application"""
        print("\n🔗 Verifying API Integration...")

        try:
            # Check if Stripe routes are imported in main API
            main_api_file = os.path.join(self.base_dir, "main_api_app.py")

            if not os.path.exists(main_api_file):
                self.log_step("API Integration", False, "Main API file not found")
                return False

            with open(main_api_file, "r") as f:
                content = f.read()

            # Check for Stripe integration imports
            if "stripe_routes" in content and "STRIPE_AVAILABLE" in content:
                self.log_step(
                    "API Integration", True, "Stripe routes integrated in main API"
                )
            else:
                self.log_step(
                    "API Integration", False, "Stripe routes not found in main API"
                )
                return False

            # Test API health endpoint
            try:
                # Start the API server in background for testing
                import threading
                import uvicorn

                def run_server():
                    uvicorn.run(
                        "main_api_app:app",
                        host="0.0.0.0",
                        port=8000,
                        log_level="error",
                        access_log=False,
                    )

                server_thread = threading.Thread(target=run_server, daemon=True)
                server_thread.start()

                # Wait for server to start
                time.sleep(3)

                # Test health endpoint
                response = requests.get(
                    "http://localhost:8000/stripe/health", timeout=10
                )
                if response.status_code == 200:
                    self.log_step(
                        "API Health Check", True, "Stripe health endpoint responding"
                    )
                else:
                    self.log_step(
                        "API Health Check",
                        False,
                        f"Health endpoint returned {response.status_code}",
                    )
                    return False

            except Exception as e:
                self.log_step("API Health Check", False, f"Error: {str(e)}")
                # This might be expected if server is already running or can't start

            return True

        except Exception as e:
            self.log_step("API Integration", False, f"Error: {str(e)}")
            return False

    def create_setup_summary(self):
        """Create comprehensive setup summary"""
        print("\n📋 Setup Summary")
        print("=" * 50)

        total_steps = len(self.setup_results["steps"])
        successful_steps = sum(
            1 for step in self.setup_results["steps"] if "SUCCESS" in step["status"]
        )

        print(f"Total Steps: {total_steps}")
        print(f"Successful: {successful_steps}")
        print(f"Failed: {total_steps - successful_steps}")
        print(f"Success Rate: {(successful_steps / total_steps) * 100:.1f}%")

        # Save detailed results
        summary_file = os.path.join(self.base_dir, "stripe_setup_summary.json")
        with open(summary_file, "w") as f:
            json.dump(self.setup_results, f, indent=2)

        print(f"\n📄 Detailed summary saved to: {summary_file}")

        if self.setup_results["success"]:
            print("\n🎉 Stripe Integration Setup Completed Successfully!")
            print("\nNext Steps:")
            print("1. Configure your Stripe account in the Stripe Dashboard")
            print("2. Update the .env file with your production credentials")
            print("3. Run production tests: python test_stripe_production.py")
            print("4. Deploy to your production environment")
        else:
            print(
                "\n⚠️  Setup completed with errors. Please review the failed steps above."
            )

    def run_complete_setup(self, stripe_config: Dict[str, str] = None):
        """Run complete setup process"""
        print("🚀 Starting Stripe Integration Setup")
        print("=" * 60)
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Default configuration for testing
        if stripe_config is None:
            stripe_config = {
                "STRIPE_CLIENT_ID": "ca_test_123456789",
                "STRIPE_CLIENT_SECRET": "sk_test_123456789",
                "STRIPE_REDIRECT_URI": "http://localhost:3000/auth/stripe/callback",
                "STRIPE_PUBLISHABLE_KEY": "pk_test_123456789",
                "STRIPE_SECRET_KEY": "sk_test_123456789",
                "STRIPE_WEBHOOK_SECRET": "whsec_test_123456789",
            }

        # Run all setup steps
        steps = [
            ("Prerequisites Check", self.check_prerequisites),
            ("Dependencies Check", self.install_dependencies),
            ("Environment Setup", lambda: self.setup_environment(stripe_config)),
            ("Integration Testing", self.test_integration),
            ("API Integration", self.verify_api_integration),
        ]

        for step_name, step_function in steps:
            if not step_function():
                print(f"\n❌ Setup failed at: {step_name}")
                break

        # Create final summary
        self.create_setup_summary()

        return self.setup_results["success"]


def main():
    """Main setup execution function"""
    import argparse

    parser = argparse.ArgumentParser(description="Stripe Integration Setup")
    parser.add_argument("--client-id", help="Stripe Client ID")
    parser.add_argument("--client-secret", help="Stripe Client Secret")
    parser.add_argument("--redirect-uri", help="Stripe Redirect URI")
    parser.add_argument("--publishable-key", help="Stripe Publishable Key")
    parser.add_argument("--secret-key", help="Stripe Secret Key")
    parser.add_argument("--webhook-secret", help="Stripe Webhook Secret")

    args = parser.parse_args()

    # Build configuration from command line arguments
    stripe_config = {}
    if args.client_id:
        stripe_config["STRIPE_CLIENT_ID"] = args.client_id
    if args.client_secret:
        stripe_config["STRIPE_CLIENT_SECRET"] = args.client_secret
    if args.redirect_uri:
        stripe_config["STRIPE_REDIRECT_URI"] = args.redirect_uri
    if args.publishable_key:
        stripe_config["STRIPE_PUBLISHABLE_KEY"] = args.publishable_key
    if args.secret_key:
        stripe_config["STRIPE_SECRET_KEY"] = args.secret_key
    if args.webhook_secret:
        stripe_config["STRIPE_WEBHOOK_SECRET"] = args.webhook_secret

    setup = StripeIntegrationSetup()
    success = setup.run_complete_setup(stripe_config)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
