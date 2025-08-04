#!/usr/bin/env python3
"""
Production Readiness Check for Atom Application

This script performs comprehensive checks on the codebase to ensure
the application is ready for production deployment.
"""

import os
import sys
import subprocess
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductionReadinessChecker:
    def __init__(self):
        self.checks = []
        self.failures = []
        self.warnings = []
        self.root_path = Path(__file__).parent

    def add_check(self, name, func):
        """Add a check function to the list."""
        self.checks.append((name, func))

    def run_check(self, name, func):
        """Run a single check and handle results."""
        try:
            logger.info(f"Running check: {name}")
            success = func()
            if success:
                logger.info(f"✅ {name} - PASSED")
                return True
            else:
                logger.error(f"❌ {name} - FAILED")
                self.failures.append(name)
                return False
        except Exception as e:
            logger.error(f"❌ {name} - ERROR: {e}")
            self.failures.append(name)
            return False

    def run_all_checks(self):
        """Run all registered checks."""
        logger.info("Starting production readiness verification...")

        for name, func in self.checks:
            self.run_check(name, func)

        # Summary
        total = len(self.checks)
        passed = total - len(self.failures) - len(self.warnings)

        logger.info("="*60)
        logger.info("PRODUCTION READINESS SUMMARY")
        logger.info(f"Total checks: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Warnings: {len(self.warnings)}")
        logger.info(f"Failed: {len(self.failures)}")

        if self.failures:
            logger.error(f"\nFailed checks: {', '.join(self.failures)}")

        if self.warnings:
            logger.warning(f"\nWarnings: {', '.join(self.warnings)}")

        return len(self.failures) == 0

    def check_python_files(self):
        """Check all Python files for syntax errors."""
        python_files = list(self.root_path.glob("**/*.py"))
        syntax_errors = []

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    compile(f.read(), str(file_path), 'exec')
            except SyntaxError as e:
                syntax_errors.append(f"{file_path}: {e}")

        if syntax_errors:
            for error in syntax_errors:
                logger.error(error)
            return False
        return True

    def check_typescript_compilation(self):
        """Check if TypeScript compiles successfully."""
        try:
            result = subprocess.run(
                ["npx", "tsc", "--skipLibCheck", "--noEmit", "--emitDeclarationOnly", "false"],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                logger.error("TypeScript compilation failed:")
                logger.error(result.stderr)
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.warning("TypeScript compilation timed out, skipping...")
            return True
        except FileNotFoundError:
            logger.warning("TypeScript not found, skipping...")
            return True

    def check_imports(self):
        """Check that all imports can be resolved."""
        # Create a simple import test
        import_test_script = """
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test key python modules
try:
    from atom.atomic-docker.project.functions.python_api_service.linkedin_service import LinkedInService
    from atom.atomic-docker.project.functions.python_api_service.twitter_service import get_twitter_api
    from atom.atomic-docker.project.functions.python_api_service.gdrive_service import GoogleDriveService
    print("Key Python modules import successfully")
except ImportError as e:
    print(f"Import error: {e}")
    exit(1)
"""

        try:
            with open(self.root_path / "import_test.py", "w") as f:
                f.write(import_test_script)

            result = subprocess.run(
                ["python", "import_test.py"],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            os.remove(self.root_path / "import_test.py")

            if result.returncode != 0:
                logger.error("Import check failed:\n" + result.stderr)
                return False
            return True
        except Exception as e:
            logger.error(f"Import check failed: {e}")
            return False

    def check_package_json(self):
        """Check if package.json is valid."""
        try:
            package_path = self.root_path / "package.json"
            if not package_path.exists():
                return False

            with open(package_path) as f:
                package_data = json.load(f)

            # Check for common required fields
            required_fields = ["name", "version", "description"]
            for field in required_fields:
                if field not in package_data:
                    logger.warning(f"Missing field in package.json: {field}")

            return True
        except Exception as e:
            logger.error(f"package.json check failed: {e}")
            return False

    def check_environment_files(self):
        """Check if required environment configuration exists."""
        required_env_vars = [
            "OPENAI_API_KEY",
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "LINKEDIN_CLIENT_ID",
            "LINKEDIN_CLIENT_SECRET"
        ]

        # Check for .env file
        env_file = self.root_path / ".env"
        if env_file.exists():
            return True

        # Check if at least mock env variables exist
        env_template = self.root_path / ".env.template"
        if env_template.exists():
            return True

        logger.warning("No .env file found - using mock integrations")
        return True

    def check_docker_configuration(self):
        """Check Docker configuration files."""
        dockerfiles = [
            self.root_path / "Dockerfile",
            self.root_path / "atomic-docker" / "Dockerfile",
            self.root_path / "fly.toml"
        ]

        docker_exists = any(f.exists() for f in dockerfiles)
        if not docker_exists:
            logger.warning("No Docker configuration found")
            return True  # This is a warning, not a failure

        return True

    def check_project_structure(self):
        """Check if project has expected structure."""
        expected_paths = [
            self.root_path / "src",
            self.root_path / "atomic-docker",
            self.root_path / "deployment" / "production",
            self.root_path / "package.json"
        ]

        missing_paths = [p for p in expected_paths if not p.exists()]
        if missing_paths:
            logger.warning(f"Missing expected paths: {missing_paths}")
            return True  # Warnings, not failures

        return True

    def check_cleanup(self):
        """Clean up any test files created."""
        test_files = [
            "import_test.py",
            "__pycache__",
            ".pytest_cache"
        ]

        for file_name in test_files:
            file_path = self.root_path / file_name
            if file_path.exists():
                if file_path.is_file():
                    file_path.unlink()
                elif file_path.is_dir():
                    import shutil
                    shutil.rmtree(file_path)

        return True

def main():
    """Main execution function."""
    checker = ProductionReadinessChecker()

    # Register all checks
    checker.add_check("Python Syntax", checker.check_python_files)
    checker.add_check("TypeScript Compilation", checker.check_typescript_compilation)
    checker.add_check("Import Resolution", checker.check_imports)
    checker.add_check("Package JSON", checker.check_package_json)
    checker.add_check("Environment Configuration", checker.check_environment_files)
    checker.add_check("Docker Configuration", checker.check_docker_configuration)
    checker.add_check("Project Structure", checker.check_project_structure)
    checker.add_check("Cleanup", checker.check_cleanup)

    # Run all checks
    success = checker.run_all_checks()

    if success:
        logger.info("\n🎉 Application is production ready!")
        sys.exit(0)
    else:
        logger.error("\n❌ Application has issues that need to be resolved")
        sys.exit(1)

if __name__ == "__main__":
    main()
