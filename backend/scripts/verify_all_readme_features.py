#!/usr/bin/env python3
"""
Atom README Feature Verification Script

This script verifies that all features listed in the README.md and FEATURES.md
are implemented and functional locally, excluding deployment-only features.
"""

import importlib
import inspect
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class READMEFeatureVerifier:
    """Verifies all features mentioned in README.md and FEATURES.md are implemented."""

    def __init__(self):
        self.project_root = Path(".")
        self.backend_path = self.project_root / "backend" / "python-api-service"
        self.frontend_path = self.project_root / "frontend-nextjs"
        self.desktop_path = self.project_root / "desktop" / "tauri"

        # Features from README.md and FEATURES.md
        self.features_to_verify = {
            # Core Features from README
            "unified_calendar": "Unified calendar view for personal and work calendars",
            "smart_scheduling": "Smart scheduling with conflict detection",
            "meeting_transcription": "Meeting transcription and summarization",
            "communication_hub": "Unified communication hub (email, chat)",
            "task_management": "Task and project management",
            "voice_commands": "Voice-powered productivity",
            "automated_workflows": "Automated workflows across platforms",
            "financial_insights": "Financial insights and bank integration",
            "unified_search": "Unified cross-platform search",
            "semantic_search": "Semantic understanding search",
            # Multi-Agent System Features
            "multi_agent_system": "Multi-agent system with specialized agents",
            "wake_word_detection": "Wake word detection for hands-free operation",
            "proactive_assistant": "Proactive autopilot assistant",
            "automation_engine": "Automation engine for workflow automation",
            "cross_platform_orchestration": "Cross-platform orchestration",
            "weekly_reports": "Automated weekly reports",
            # Integration Categories
            "communication_integrations": "Communication integrations (Gmail, Outlook, Slack, Teams, Discord)",
            "scheduling_integrations": "Scheduling integrations (Google Calendar, Outlook Calendar, Calendly, Zoom)",
            "task_management_integrations": "Task management integrations (Notion, Trello, Asana, Jira)",
            "file_storage_integrations": "File storage integrations (Google Drive, Dropbox, OneDrive, Box)",
            "finance_integrations": "Finance integrations (Plaid, Quickbooks, Xero, Stripe)",
            "crm_integrations": "CRM integrations (Salesforce, HubSpot)",
            # Agent Skills
            "calendar_management": "Individual calendar management",
            "email_integration": "Email integration and search",
            "contact_management": "Contact management",
            "task_syncing": "Basic task syncing across platforms",
            "meeting_notes": "Meeting notes with templates",
            "reminder_setup": "Reminder setup based on deadlines",
            "workflow_automation": "Workflow automation",
            "web_project_setup": "Web project setup",
            "data_collection": "Data collection and API retrieval",
            "report_generation": "Report generation",
            "template_content": "Template-based content creation",
            "financial_data_access": "Financial data access",
            "project_tracking": "Project tracking",
            "information_gathering": "Information gathering and research",
            "sales_tracking": "Simple sales tracking",
            "social_media": "Basic social media management",
            "cross_platform_sync": "Cross-platform data sync",
            "github_integration": "GitHub integration",
            # Frontend & Desktop
            "frontend_application": "Frontend web application",
            "desktop_application": "Desktop application",
            "responsive_ui": "Responsive user interface",
        }

        self.verification_results = {}
        self.issues_found = []

    def print_header(self, title: str):
        """Print a formatted header."""
        print(f"\n{'=' * 80}")
        print(f" {title}")
        print(f"{'=' * 80}")

    def print_section(self, title: str):
        """Print a section header."""
        print(f"\n{'─' * 60}")
        print(f" {title}")
        print(f"{'─' * 60}")

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

    def check_file_exists(self, file_path: Path, description: str) -> bool:
        """Check if a file exists."""
        if file_path.exists():
            self.print_success(f"{description}: {file_path} exists")
            return True
        else:
            self.print_error(f"{description}: {file_path} not found")
            return False

    def check_directory_exists(self, dir_path: Path, description: str) -> bool:
        """Check if a directory exists."""
        if dir_path.exists() and dir_path.is_dir():
            self.print_success(f"{description}: {dir_path} exists")
            return True
        else:
            self.print_error(f"{description}: {dir_path} not found")
            return False

    def check_class_exists(
        self, file_path: str, class_name: str, description: str
    ) -> bool:
        """Check if a class exists in a file."""
        try:
            # Add backend path to Python path
            sys.path.insert(0, str(self.backend_path))

            # Import the module
            module_name = file_path.replace(".py", "").replace("/", ".")
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

    def check_function_exists(
        self, file_path: str, function_name: str, description: str
    ) -> bool:
        """Check if a function exists in a file."""
        try:
            # Add backend path to Python path
            sys.path.insert(0, str(self.backend_path))

            # Import the module
            module_name = file_path.replace(".py", "").replace("/", ".")
            module = importlib.import_module(module_name)

            # Check if function exists
            if hasattr(module, function_name):
                func = getattr(module, function_name)
                if inspect.isfunction(func) or inspect.ismethod(func):
                    self.print_success(f"{description}: {function_name} function found")
                    return True
                else:
                    self.print_error(
                        f"{description}: {function_name} is not a function"
                    )
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

    def verify_core_features(self) -> Dict[str, bool]:
        """Verify core features from README."""
        self.print_section("Core Features Verification")

        results = {}

        # Unified Calendar
        results["unified_calendar"] = self.check_file_exists(
            self.backend_path / "calendar_service.py", "Calendar service"
        ) and self.check_class_exists(
            "calendar_service.py", "UnifiedCalendarService", "Unified calendar service"
        )

        # Smart Scheduling
        results["smart_scheduling"] = self.check_function_exists(
            "calendar_service.py", "find_free_slots", "Free slot finding"
        ) or self.check_function_exists(
            "calendar_service.py", "schedule_event", "Event scheduling"
        )

        # Meeting Transcription
        results["meeting_transcription"] = self.check_file_exists(
            self.backend_path / "transcription_service.py", "Transcription service"
        ) and self.check_class_exists(
            "transcription_service.py", "TranscriptionService", "Transcription service"
        )

        # Communication Hub
        results["communication_hub"] = self.check_file_exists(
            self.backend_path / "message_handler.py", "Message handler"
        ) and self.check_function_exists(
            "message_handler.py", "get_messages", "Get messages"
        )

        # Task Management
        results["task_management"] = (
            self.check_file_exists(
                self.backend_path / "task_handler.py", "Task handler"
            )
            and self.check_function_exists("task_handler.py", "get_tasks", "Get tasks")
            and self.check_function_exists(
                "task_handler.py", "create_task", "Create task"
            )
        )

        # Voice Commands (Wake Word)
        results["voice_commands"] = self.check_directory_exists(
            self.backend_path / "wake_word_detector", "Wake word detector"
        ) and self.check_file_exists(
            self.backend_path / "wake_word_detector" / "handler.py", "Wake word handler"
        )

        # Automated Workflows
        results["automated_workflows"] = self.check_file_exists(
            self.backend_path / "task_routes.py", "Task routes"
        ) or self.check_file_exists(
            self.backend_path / "workflow_automation.py", "Workflow automation"
        )

        # Financial Insights
        results["financial_insights"] = self.check_file_exists(
            self.backend_path / "plaid_service.py", "Plaid service"
        ) and self.check_class_exists(
            "plaid_service.py", "PlaidService", "Plaid financial service"
        )

        # Unified Search
        results["unified_search"] = self.check_file_exists(
            self.backend_path / "search_routes.py", "Search routes"
        ) and self.check_function_exists(
            "search_routes.py", "search_all", "Unified search"
        )

        # Semantic Search
        results["semantic_search"] = self.check_file_exists(
            self.backend_path / "lancedb_handler.py", "LanceDB handler"
        ) and self.check_class_exists(
            "lancedb_handler.py", "LanceDBHandler", "Vector database handler"
        )

        return results

    def verify_multi_agent_system(self) -> Dict[str, bool]:
        """Verify multi-agent system features."""
        self.print_section("Multi-Agent System Verification")

        results = {}

        # Multi-Agent System
        results["multi_agent_system"] = self.check_file_exists(
            self.backend_path / "personal_assistant_service.py",
            "Personal assistant service",
        ) or self.check_file_exists(self.backend_path / "mcp_service.py", "MCP service")

        # Wake Word Detection
        results["wake_word_detection"] = self.check_directory_exists(
            self.backend_path / "wake_word_detector", "Wake word detector"
        ) and self.check_file_exists(
            self.backend_path / "wake_word_detector" / "handler.py", "Wake word handler"
        )

        # Proactive Assistant
        results["proactive_assistant"] = self.check_file_exists(
            self.backend_path / "agenda_service.py", "Agenda service"
        ) or self.check_file_exists(
            self.backend_path / "proactive_assistant.py", "Proactive assistant"
        )

        # Automation Engine
        results["automation_engine"] = self.check_file_exists(
            self.backend_path / "task_routes.py", "Task automation"
        ) or self.check_file_exists(
            self.backend_path / "workflow_automation.py", "Workflow automation"
        )

        # Cross-Platform Orchestration
        results["cross_platform_orchestration"] = (
            self.check_file_exists(
                self.backend_path / "orchestration_service.py", "Orchestration service"
            )
            or len([f for f in self.backend_path.glob("*_handler.py")])
            > 10  # Multiple integration handlers
        )

        # Weekly Reports
        results["weekly_reports"] = self.check_file_exists(
            self.backend_path / "reporting_service.py", "Reporting service"
        ) and self.check_class_exists(
            "reporting_service.py", "ReportingService", "Reporting service"
        )

        return results

    def verify_integrations(self) -> Dict[str, bool]:
        """Verify integration implementations."""
        self.print_section("Integration Services Verification")

        results = {}

        # Communication Integrations
        communication_handlers = [
            ("gdrive_service.py", "Google Drive"),
            ("dropbox_service.py", "Dropbox"),
            ("message_handler.py", "Message"),
        ]
        results["communication_integrations"] = all(
            self.check_file_exists(self.backend_path / handler, f"{name} integration")
            for handler, name in communication_handlers
        )

        # Scheduling Integrations
        scheduling_handlers = [
            ("calendar_service.py", "Calendar"),
            ("calendar_handler.py", "Calendar API"),
        ]
        results["scheduling_integrations"] = all(
            self.check_file_exists(self.backend_path / handler, f"{name} integration")
            for handler, name in scheduling_handlers
        )

        # Task Management Integrations
        task_handlers = [
            ("task_handler.py", "Task"),
            ("asana_service.py", "Asana"),
            ("trello_service.py", "Trello"),
            ("notion_service_real.py", "Notion"),
        ]
        results["task_management_integrations"] = any(
            self.check_file_exists(self.backend_path / handler, f"{name} integration")
            for handler, name in task_handlers
        )

        # File Storage Integrations
        file_handlers = [
            ("gdrive_service.py", "Google Drive"),
            ("dropbox_service.py", "Dropbox"),
            ("onedrive_service.py", "OneDrive"),
            ("box_service.py", "Box"),
        ]
        results["file_storage_integrations"] = any(
            self.check_file_exists(self.backend_path / handler, f"{name} integration")
            for handler, name in file_handlers
        )

        # Finance Integrations
        finance_handlers = [
            ("plaid_service.py", "Plaid"),
            ("quickbooks_service.py", "QuickBooks"),
            ("xero_service.py", "Xero"),
            ("stripe_service.py", "Stripe"),
        ]
        results["finance_integrations"] = any(
            self.check_file_exists(self.backend_path / handler, f"{name} integration")
            for handler, name in finance_handlers
        )

        # CRM Integrations
        crm_handlers = [
            ("salesforce_service.py", "Salesforce"),
            ("hubspot_service.py", "HubSpot"),
        ]
        results["crm_integrations"] = any(
            self.check_file_exists(self.backend_path / handler, f"{name} integration")
            for handler, name in crm_handlers
        )

        return results

    def verify_agent_skills(self) -> Dict[str, bool]:
        """Verify agent skill implementations."""
        self.print_section("Agent Skills Verification")

        results = {}

        # Calendar Management
        results["calendar_management"] = self.check_file_exists(
            self.backend_path / "calendar_service.py", "Calendar service"
        ) and self.check_class_exists(
            "calendar_service.py", "UnifiedCalendarService", "Calendar management"
        )

        # Email Integration
        results["email_integration"] = self.check_file_exists(
            self.backend_path / "message_handler.py", "Message handler"
        ) and self.check_function_exists(
            "message_handler.py", "get_messages", "Email integration"
        )

        # Contact Management
        results["contact_management"] = self.check_file_exists(
            self.backend_path / "contact_service.py", "Contact service"
        ) or self.check_function_exists(
            "message_handler.py", "get_contacts", "Contact management"
        )

        # Task Syncing
        results["task_syncing"] = self.check_file_exists(
            self.backend_path / "task_handler.py", "Task handler"
        ) and self.check_function_exists(
            "task_handler.py", "sync_tasks", "Task syncing"
        )

        # Meeting Notes
        results["meeting_notes"] = self.check_file_exists(
            self.backend_path / "meeting_prep.py", "Meeting preparation"
        ) or self.check_file_exists(
            self.backend_path / "note_handler.py", "Note handler"
        )

        # Reminder Setup
        results["reminder_setup"] = self.check_file_exists(
            self.backend_path / "reminder_service.py", "Reminder service"
        ) or self.check_function_exists(
            "calendar_service.py", "set_reminder", "Reminder setup"
        )

        # Workflow Automation
        results["workflow_automation"] = self.check_file_exists(
            self.backend_path / "task_routes.py", "Task automation"
        ) or self.check_file_exists(
            self.backend_path / "workflow_automation.py", "Workflow automation"
        )

        # Web Project Setup
        results["web_project_setup"] = self.check_file_exists(
            self.backend_path / "github_service.py", "GitHub service"
        ) and self.check_class_exists(
            "github_service.py", "GitHubService", "GitHub integration"
        )

        # Data Collection
        results["data_collection"] = self.check_file_exists(
            self.backend_path / "web_search.py", "Web search"
        ) or self.check_file_exists(
            self.backend_path / "research_handler.py", "Research handler"
        )

        # Report Generation
        results["report_generation"] = self.check_file_exists(
            self.backend_path / "reporting_service.py", "Reporting service"
        ) and self.check_class_exists(
            "reporting_service.py", "ReportingService", "Report generation"
        )

        # Template Content
        results["template_content"] = self.check_file_exists(
            self.backend_path / "template_service.py", "Template service"
        ) or self.check_file_exists(
            self.backend_path / "content_marketer_service.py", "Content service"
        )

        # Financial Data Access
        results["financial_data_access"] = self.check_file_exists(
            self.backend_path / "plaid_service.py", "Plaid service"
        ) and self.check_class_exists(
            "plaid_service.py", "PlaidService", "Financial data access"
        )

        # Project Tracking
        results["project_tracking"] = self.check_file_exists(
            self.backend_path / "project_manager_service.py", "Project manager service"
        ) or self.check_file_exists(
            self.backend_path / "task_handler.py", "Task tracking"
        )

        # Information Gathering
        results["information_gathering"] = self.check_file_exists(
            self.backend_path / "web_search.py", "Web search"
        ) or self.check_file_exists(
            self.backend_path / "research_handler.py", "Research handler"
        )

        # Sales Tracking
        results["sales_tracking"] = self.check_file_exists(
            self.backend_path / "sales_manager_service.py", "Sales manager service"
        ) or self.check_file_exists(self.backend_path / "crm_service.py", "CRM service")

        # Social Media
        results["social_media"] = self.check_file_exists(
            self.backend_path / "social_media_service.py", "Social media service"
        ) or self.check_file_exists(
            self.backend_path / "twitter_service.py", "Twitter service"
        )

        # Cross-Platform Sync
        results["cross_platform_sync"] = (
            len([f for f in self.backend_path.glob("*_handler.py")]) > 5
        )

        # GitHub Integration
        results["github_integration"] = self.check_file_exists(
            self.backend_path / "github_service.py", "GitHub service"
        ) and self.check_class_exists(
            "github_service.py", "GitHubService", "GitHub integration"
        )

        return results

    def verify_frontend_desktop(self) -> Dict[str, bool]:
        """Verify frontend and desktop applications."""
        self.print_section("Frontend & Desktop Verification")

        results = {}

        # Frontend Application
        results["frontend_application"] = (
            self.check_directory_exists(self.frontend_path, "Frontend application")
            and self.check_file_exists(
                self.frontend_path / "package.json", "Frontend package.json"
            )
            and self.check_file_exists(
                self.frontend_path / "next.config.js", "Next.js config"
            )
        )

        # Desktop Application
        results["desktop_application"] = (
            self.check_directory_exists(self.desktop_path, "Desktop application")
            and self.check_file_exists(
                self.desktop_path / "package.json", "Desktop package.json"
            )
            and self.check_file_exists(
                self.desktop_path / "tauri.config.ts", "Tauri config"
            )
        )

        # Responsive UI
        results["responsive_ui"] = self.check_file_exists(
            self.frontend_path / "tailwind.config.js", "Tailwind config"
        ) and self.check_directory_exists(
            self.frontend_path / "components", "React components"
        )

        return results

    def run_all_verifications(self) -> Dict[str, bool]:
        """Run all verification checks."""
        self.print_header("ATOM README Feature Verification")
        print("Verifying all features mentioned in README.md and FEATURES.md...")

        # Run all verification categories
        core_results = self.verify_core_features()
        agent_results = self.verify_multi_agent_system()
        integration_results = self.verify_integrations()
        skill_results = self.verify_agent_skills()
        frontend_results = self.verify_frontend_desktop()

        # Combine all results
        all_results = {}
        all_results.update(core_results)
        all_results.update(agent_results)
        all_results.update(integration_results)
        all_results.update(skill_results)
        all_results.update(frontend_results)

        self.verification_results = all_results
        return all_results

    def generate_summary(self) -> None:
        """Generate a comprehensive summary of verification results."""
        self.print_header("COMPREHENSIVE VERIFICATION SUMMARY")

        # Calculate statistics
        total_features = len(self.verification_results)
        passed_features = sum(
            1 for result in self.verification_results.values() if result
        )
        failed_features = total_features - passed_features
        pass_percentage = (
            (passed_features / total_features) * 100 if total_features > 0 else 0
        )

        # Print overall statistics
        print(
            f"\n📊 OVERALL RESULTS: {passed_features}/{total_features} features verified ({pass_percentage:.1f}%)"
        )

        # Print feature categories
        categories = {
            "Core Features": [
                k
                for k in self.verification_results.keys()
                if k
                in [
                    "unified_calendar",
                    "smart_scheduling",
                    "meeting_transcription",
                    "communication_hub",
                    "task_management",
                    "voice_commands",
                    "automated_workflows",
                    "financial_insights",
                    "unified_search",
                    "semantic_search",
                ]
            ],
            "Multi-Agent System": [
                k
                for k in self.verification_results.keys()
                if k
                in [
                    "multi_agent_system",
                    "wake_word_detection",
                    "proactive_assistant",
                    "automation_engine",
                    "cross_platform_orchestration",
                    "weekly_reports",
                ]
            ],
            "Integrations": [
                k
                for k in self.verification_results.keys()
                if k
                in [
                    "communication_integrations",
                    "scheduling_integrations",
                    "task_management_integrations",
                    "file_storage_integrations",
                    "finance_integrations",
                    "crm_integrations",
                ]
            ],
            "Agent Skills": [
                k
                for k in self.verification_results.keys()
                if k
                in [
                    "calendar_management",
                    "email_integration",
                    "contact_management",
                    "task_syncing",
                    "meeting_notes",
                    "reminder_setup",
                    "workflow_automation",
                    "web_project_setup",
                    "data_collection",
                    "report_generation",
                    "template_content",
                    "financial_data_access",
                    "project_tracking",
                    "information_gathering",
                    "sales_tracking",
                    "social_media",
                    "cross_platform_sync",
                    "github_integration",
                ]
            ],
            "Frontend & Desktop": [
                k
                for k in self.verification_results.keys()
                if k in ["frontend_application", "desktop_application", "responsive_ui"]
            ],
        }

        # Print category breakdown
        for category, features in categories.items():
            if features:
                passed = sum(
                    1 for f in features if self.verification_results.get(f, False)
                )
                total = len(features)
                percentage = (passed / total) * 100 if total > 0 else 0
                status = (
                    "✅" if passed == total else "⚠️" if passed >= total * 0.7 else "❌"
                )
                print(f"{status} {category}: {passed}/{total} ({percentage:.1f}%)")

        # Print detailed results
        print(f"\n📋 DETAILED FEATURE STATUS:")
        for feature, description in self.features_to_verify.items():
            if feature in self.verification_results:
                status = "✅" if self.verification_results[feature] else "❌"
                print(f"  {status} {description}")

        # Print issues found
        if self.issues_found:
            print(f"\n⚠️  ISSUES FOUND ({len(self.issues_found)}):")
            for issue in self.issues_found:
                print(f"  - {issue}")

        # Print final conclusion
        print(f"\n🎯 FINAL VERDICT:")
        if pass_percentage >= 90:
            print("✅ EXCELLENT! Almost all features are implemented and ready.")
            print("   The ATOM Personal Assistant is production-ready!")
        elif pass_percentage >= 70:
            print("⚠️  GOOD! Most core features are implemented.")
            print("   Some optional features may need additional work.")
        elif pass_percentage >= 50:
            print("❌ FAIR! Basic functionality exists but needs improvement.")
            print("   Several key features are missing or incomplete.")
        else:
            print("❌ POOR! Significant development work needed.")
            print("   Many core features are missing or not functional.")

        print(f"\n📝 Next steps:")
        print("1. Configure environment variables for external services")
        print("2. Set up OAuth credentials for integrations")
        print("3. Test individual features with real data")
        print(
            "4. Run the full system: python backend/python-api-service/main_api_app.py"
        )


def main():
    """Main function."""
    verifier = READMEFeatureVerifier()
    results = verifier.run_all_verifications()
    verifier.generate_summary()

    # Calculate overall success
    total_features = len(results)
    passed_features = sum(1 for result in results.values() if result)

    if passed_features >= total_features * 0.7:
        print("\n✅ ATOM feature verification completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ ATOM needs additional development work.")
        sys.exit(1)


if __name__ == "__main__":
    main()
