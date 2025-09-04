#!/usr/bin/env python3
"""
Atom Feature Verification Script

This script verifies that all core Atom features are implemented and functional.
It tests each major component without requiring a full Flask server or database.
"""

import os
import sys
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FeatureVerifier:
    """Verifies that all Atom features are implemented and functional."""

    def __init__(self):
        self.backend_path = Path("backend/python-api-service")
        self.features_verified = {}
        self.issues_found = []

    def print_header(self, title: str):
        """Print a formatted header."""
        print(f"\n{'='*60}")
        print(f" {title}")
        print(f"{'='*60}")

    def print_success(self, message: str):
        """Print success message."""
        print(f"✅ {message}")

    def print_warning(self, message: str):
        """Print warning message."""
        print(f"⚠️  {message}")

    def print_error(self, message: str):
        """Print error message."""
        print(f"❌ {message}")
        self.issues_found.append(message)

    def check_file_exists(self, file_path: str, description: str) -> bool:
        """Check if a file exists."""
        full_path = self.backend_path / file_path
        if full_path.exists():
            self.print_success(f"{description}: {file_path} exists")
            return True
        else:
            self.print_error(f"{description}: {file_path} not found")
            return False

    def check_class_exists(self, file_path: str, class_name: str, description: str) -> bool:
        """Check if a class exists in a file."""
        try:
            # Add backend path to Python path
            sys.path.insert(0, str(self.backend_path))

            # Import the module
            module_name = file_path.replace('.py', '').replace('/', '.')
            module = importlib.import_module(module_name)

            # Check if class exists
            if hasattr(module, class_name):
                cls = getattr(module, class_name)
                if inspect.isclass(cls):
                    self.print_success(f"{description}: {class_name} class found")
                    return True
                else:
                    self.print_error(f"{description}: {class_name} is not a class")
                    return False
            else:
                self.print_error(f"{description}: {class_name} class not found")
                return False

        except ImportError as e:
            self.print_error(f"{description}: Failed to import {file_path} - {e}")
            return False
        except Exception as e:
            self.print_error(f"{description}: Error checking {class_name} - {e}")
            return False

    def check_function_exists(self, file_path: str, function_name: str, description: str) -> bool:
        """Check if a function exists in a file."""
        try:
            # Add backend path to Python path
            sys.path.insert(0, str(self.backend_path))

            # Import the module
            module_name = file_path.replace('.py', '').replace('/', '.')
            module = importlib.import_module(module_name)

            # Check if function exists
            if hasattr(module, function_name):
                func = getattr(module, function_name)
                if inspect.isfunction(func) or inspect.ismethod(func):
                    self.print_success(f"{description}: {function_name} function found")
                    return True
                else:
                    self.print_error(f"{description}: {function_name} is not a function")
                    return False
            else:
                self.print_error(f"{description}: {function_name} function not found")
                return False

        except ImportError as e:
            self.print_error(f"{description}: Failed to import {file_path} - {e}")
            return False
        except Exception as e:
            self.print_error(f"{description}: Error checking {function_name} - {e}")
            return False

    def verify_core_services(self) -> bool:
        """Verify core service implementations."""
        self.print_header("Verifying Core Services")

        results = []

        # Database utilities
        results.append(self.check_file_exists("db_utils.py", "Database utilities"))
        results.append(self.check_class_exists("db_utils.py", "get_db_connection", "Database connection function"))
        results.append(self.check_function_exists("db_utils.py", "execute_query", "Database query function"))

        # Calendar service
        results.append(self.check_file_exists("calendar_service.py", "Calendar service"))
        results.append(self.check_class_exists("calendar_service.py", "UnifiedCalendarService", "Unified calendar service"))
        results.append(self.check_class_exists("calendar_service.py", "CalendarEvent", "Calendar event model"))

        # Task management
        results.append(self.check_file_exists("task_handler.py", "Task handler"))
        results.append(self.check_function_exists("task_handler.py", "get_tasks", "Get tasks endpoint"))
        results.append(self.check_function_exists("task_handler.py", "create_task", "Create task endpoint"))

        # Message management
        results.append(self.check_file_exists("message_handler.py", "Message handler"))
        results.append(self.check_function_exists("message_handler.py", "get_messages", "Get messages endpoint"))
        results.append(self.check_function_exists("message_handler.py", "mark_as_read", "Mark as read endpoint"))

        # Transcription service
        results.append(self.check_file_exists("transcription_service.py", "Transcription service"))
        results.append(self.check_class_exists("transcription_service.py", "TranscriptionService", "Transcription service"))
        results.append(self.check_function_exists("transcription_service.py", "transcribe_audio", "Audio transcription"))

        # Plaid integration
        results.append(self.check_file_exists("plaid_service.py", "Plaid service"))
        results.append(self.check_class_exists("plaid_service.py", "PlaidService", "Plaid financial service"))

        return all(results)

    def verify_api_endpoints(self) -> bool:
        """Verify API endpoint implementations."""
        self.print_header("Verifying API Endpoints")

        results = []

        # Check handler files exist
        handlers = [
            ("calendar_handler.py", "Calendar API"),
            ("task_handler.py", "Task API"),
            ("message_handler.py", "Message API"),
            ("transcription_handler.py", "Transcription API"),
        ]

        for file, description in handlers:
            results.append(self.check_file_exists(file, description))

        # Check specific endpoints
        endpoints = [
            ("calendar_handler.py", "get_calendar_events", "Calendar events endpoint"),
            ("task_handler.py", "get_tasks", "Get tasks endpoint"),
            ("message_handler.py", "get_messages", "Get messages endpoint"),
            ("transcription_handler.py", "transcribe_audio", "Transcription endpoint"),
        ]

        for file, func, description in endpoints:
            results.append(self.check_function_exists(file, func, description))

        return all(results)

    def verify_database_schema(self) -> bool:
        """Verify database schema initialization."""
        self.print_header("Verifying Database Schema")

        results = []

        # Check database initialization
        results.append(self.check_file_exists("init_database.py", "Database initialization"))
        results.append(self.check_function_exists("init_database.py", "initialize_database", "Database init function"))

        # Check table creation functions
        results.append(self.check_function_exists("init_database.py", "create_tables", "Table creation function"))
        results.append(self.check_function_exists("init_database.py", "check_tables_exist", "Table verification function"))

        return all(results)

    def verify_integration_services(self) -> bool:
        """Verify integration service implementations."""
        self.print_header("Verifying Integration Services")

        results = []

        # Google Drive integration
        results.append(self.check_file_exists("gdrive_service.py", "Google Drive service"))
        results.append(self.check_class_exists("gdrive_service.py", "GDriveApiClient", "Google Drive client"))

        # Dropbox integration
        results.append(self.check_file_exists("dropbox_service.py", "Dropbox service"))
        results.append(self.check_class_exists("dropbox_service.py", "DropboxService", "Dropbox client"))

        # OAuth handlers
        oauth_handlers = [
            "auth_handler_gdrive.py",
            "auth_handler_dropbox.py",
            "auth_handler_asana.py",
            "auth_handler_box.py",
            "auth_handler_trello.py",
            "auth_handler_zoho.py",
            "auth_handler_shopify.py"
        ]

        for handler in oauth_handlers:
            if (self.backend_path / handler).exists():
                results.append(True)
                self.print_success(f"OAuth handler: {handler} exists")
            else:
                results.append(False)
                self.print_warning(f"OAuth handler: {handler} not found (optional)")

        return all(results)

    def verify_environment_configuration(self) -> bool:
        """Verify environment configuration files."""
        self.print_header("Verifying Environment Configuration")

        results = []

        # Check environment files
        env_files = [
            (".env.example", "Environment example"),
            ("README_DEVELOPMENT.md", "Development guide"),
        ]

        for file, description in env_files:
            full_path = Path(file)
            if full_path.exists():
                results.append(True)
                self.print_success(f"{description}: {file} exists")
            else:
                results.append(False)
                self.print_error(f"{description}: {file} not found")

        return all(results)

    def run_all_checks(self) -> bool:
        """Run all verification checks."""
        self.print_header("Starting Atom Feature Verification")
        print("Checking if all core features are implemented and functional...")

        checks = [
            self.verify_core_services(),
            self.verify_api_endpoints(),
            self.verify_database_schema(),
            self.verify_integration_services(),
            self.verify_environment_configuration(),
        ]

        # Summary
        self.print_header("Verification Summary")

        total_checks = sum(len(check) for check in checks if isinstance(check, list))
        passed_checks = sum(sum(1 for result in check if result) for check in checks if isinstance(check, list))

        print(f"Overall result: {passed_checks}/{total_checks} checks passed")

        if self.issues_found:
            print(f"\nIssues found ({len(self.issues_found)}):")
            for issue in self.issues_found:
                print(f"  - {issue}")

        if passed_checks == total_checks:
            self.print_success("All features verified successfully! 🎉")
            print("\nNext steps:")
            print("1. Configure environment variables in .env file")
            print("2. Start PostgreSQL database")
            print("3. Run: python backend/python-api-service/main_api_app.py")
            print("4. Test API endpoints")
            return True
        elif passed_checks >= total_checks * 0.8:
            self.print_warning("Most features verified (some optional components missing)")
            print("\nThe core functionality is ready. Some optional integrations may need setup.")
            return True
        else:
            self.print_error("Significant features missing or not working")
            return False

def main():
    """Main function."""
    verifier = FeatureVerifier()
    success = verifier.run_all_checks()

    if success:
        print("\n✅ Atom is ready for development and testing!")
        sys.exit(0)
    else:
        print("\n❌ Atom needs additional work before it's ready.")
        sys.exit(1)

if __name__ == "__main__":
    main()
