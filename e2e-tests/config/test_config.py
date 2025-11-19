"""
E2E Test Configuration for Atom Platform
Validates required credentials and sets up test environment
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class TestConfig:
    """Configuration for E2E testing with credential validation"""

    # Test environment URLs
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5059")

    # Required credentials for different test categories
    REQUIRED_CREDENTIALS = {
        "core": [
            "OPENAI_API_KEY",  # For LLM-based verification
        ],
        "communication": [
            "SLACK_BOT_TOKEN",
            "DISCORD_BOT_TOKEN",
            "GMAIL_CLIENT_ID",
            "GMAIL_CLIENT_SECRET",
            "OUTLOOK_CLIENT_ID",
            "OUTLOOK_CLIENT_SECRET",
        ],
        "productivity": [
            "ASANA_ACCESS_TOKEN",
            "NOTION_API_KEY",
            "LINEAR_API_KEY",
            "TRELLO_API_KEY",
            "MONDAY_API_KEY",
        ],
        "development": [
            "GITHUB_ACCESS_TOKEN",
            # "GITLAB_ACCESS_TOKEN",
            # "JIRA_API_TOKEN",
        ],
        "crm": [
            "SALESFORCE_CLIENT_ID",
            "SALESFORCE_CLIENT_SECRET",
            # "HUBSPOT_ACCESS_TOKEN",
        ],
        "storage": [
            "GOOGLE_DRIVE_CLIENT_ID",
            "GOOGLE_DRIVE_CLIENT_SECRET",
            # "DROPBOX_ACCESS_TOKEN",
            "ONEDRIVE_CLIENT_ID",
            "ONEDRIVE_CLIENT_SECRET",
            "BOX_CLIENT_ID",
            "BOX_CLIENT_SECRET",
        ],
        "financial": [
            # "STRIPE_SECRET_KEY",
            # "QUICKBOOKS_CLIENT_ID",
            # "QUICKBOOKS_CLIENT_SECRET",
            # "XERO_CLIENT_ID",
            # "XERO_CLIENT_SECRET",
        ],
        "voice": [
            # "ELEVENLABS_API_KEY",
        ],
    }

    # Marketing claims to verify
    MARKETING_CLAIMS = {
        "natural_language_workflow": "Just describe what you want to automate and Atom builds complete workflows",
        "cross_platform_coordination": "Works across all your tools seamlessly",
        "conversational_automation": "Automates complex workflows through natural language chat",
        "ai_memory": "Remembers conversation history and context",
        "voice_integration": "Seamless voice-to-action capabilities",
        "production_ready": "Production-ready architecture with FastAPI backend and Next.js frontend",
        "service_integrations": "33+ service integrations available",
        "byok_support": "Complete BYOK (Bring Your Own Key) system",
        # Functional Claims (Non-marketed but expected features)
        "github_integration": "Integrates with GitHub for issue tracking and repository management",
        "slack_integration": "Sends and receives messages via Slack",
        "google_drive_integration": "Syncs files and manages documents with Google Drive",
        "asana_integration": "Manages tasks and projects in Asana",
        "trello_integration": "Organizes projects and cards in Trello",
        "salesforce_integration": "Connects with Salesforce CRM for customer data",
        "gmail_integration": "Sends and reads emails via Gmail",
        "outlook_integration": "Integrates with Outlook for email and calendar",
        "notion_integration": "Manages pages and databases in Notion",
    }

    @classmethod
    def validate_credentials(cls, test_category: Union[str, List[str]] = "all") -> Dict[str, bool]:
        """
        Validate required credentials for testing

        Args:
            test_category: Specific category to validate, or "all" for all categories

        Returns:
            Dictionary with credential validation results
        """
        validation_results = {}

        if test_category == "all":
            categories = list(cls.REQUIRED_CREDENTIALS.keys())
        elif isinstance(test_category, list):
            categories = test_category
        else:
            categories = [test_category]

        for category in categories:
            if category in cls.REQUIRED_CREDENTIALS:
                for credential in cls.REQUIRED_CREDENTIALS[category]:
                    is_present = bool(os.getenv(credential))
                    validation_results[f"{category}.{credential}"] = is_present

        return validation_results

    @classmethod
    def get_missing_credentials(cls, test_category: str = "all") -> List[str]:
        """
        Get list of missing credentials

        Args:
            test_category: Specific category to check

        Returns:
            List of missing credential names
        """
        validation = cls.validate_credentials(test_category)
        return [cred for cred, present in validation.items() if not present]

    @classmethod
    def check_service_connectivity(cls) -> Dict[str, bool]:
        """
        Check connectivity to required services

        Returns:
            Dictionary with service connectivity status
        """
        connectivity = {}

        # Check frontend
        try:
            response = requests.get(f"{cls.FRONTEND_URL}/api/health", timeout=10)
            connectivity["frontend"] = response.status_code == 200
        except:
            connectivity["frontend"] = False

        # Check backend
        try:
            response = requests.get(f"{cls.BACKEND_URL}/health", timeout=10)
            connectivity["backend"] = response.status_code == 200
        except:
            connectivity["backend"] = False

        return connectivity

    @classmethod
    def is_test_ready(cls, test_category: str = "all") -> bool:
        """
        Check if environment is ready for testing

        Args:
            test_category: Specific category to check

        Returns:
            True if ready for testing
        """
        # Check credentials
        missing_creds = cls.get_missing_credentials(test_category)
        if missing_creds:
            print(f"Missing credentials: {missing_creds}")
            return False

        # Check connectivity
        connectivity = cls.check_service_connectivity()
        if not connectivity.get("backend", False):
            print("Backend service is not accessible")
            return False

        return True

    @classmethod
    def get_test_categories_with_credentials(cls) -> List[str]:
        """
        Get list of test categories that have all required credentials

        Returns:
            List of available test categories
        """
        available_categories = []

        for category in cls.REQUIRED_CREDENTIALS.keys():
            missing = cls.get_missing_credentials(category)
            if not missing:
                available_categories.append(category)

        return available_categories


# Global configuration instance
config = TestConfig()
