"""
OAuth Configuration Module

Centralized OAuth credential management for all third-party integrations.
Loads credentials from environment variables and provides validation.

Usage:
    from integrations.oauth_config import OAuthConfig, get_oauth_config

    config = get_oauth_config()

    # Get Outlook credentials
    outlook_creds = config.get_outlook_config()

    # Validate all credentials are set
    validation = config.validate_all()
    if not validation["valid"]:
        print(f"Missing: {validation['missing']}")
"""

import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OAuthService(str, Enum):
    """Supported OAuth services"""
    GOOGLE = "google"
    SLACK = "slack"
    TRELLO = "trello"
    ASANA = "asana"
    NOTION = "notion"
    DROPBOX = "dropbox"
    OUTLOOK = "outlook"
    TEAMS = "teams"
    GITHUB = "github"


@dataclass
class OAuthCredentials:
    """OAuth credentials for a service"""
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: List[str]
    configured: bool = False


class OAuthConfig:
    """
    Centralized OAuth configuration manager.

    Loads all OAuth credentials from environment variables and provides
    validation and helper methods for accessing credentials.
    """

    def __init__(self):
        self.production_domain = os.getenv("PRODUCTION_DOMAIN", "localhost:8000")
        self._credentials_cache: Dict[OAuthService, OAuthCredentials] = {}
        self._load_credentials()

    def _load_credentials(self):
        """Load all OAuth credentials from environment variables"""
        base_protocol = "https" if self.production_domain != "localhost:8000" else "http"

        # Google Workspace
        self._credentials_cache[OAuthService.GOOGLE] = OAuthCredentials(
            client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            redirect_uri=f"{base_protocol}://{self.production_domain}/api/auth/google/oauth2callback",
            scopes=["openid", "profile", "email", "https://www.googleapis.com/auth/calendar"],
            configured=bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
        )

        # Slack
        self._credentials_cache[OAuthService.SLACK] = OAuthCredentials(
            client_id=os.getenv("SLACK_CLIENT_ID", ""),
            client_secret=os.getenv("SLACK_CLIENT_SECRET", ""),
            redirect_uri=f"{base_protocol}://{self.production_domain}/api/auth/slack/oauth2callback",
            scopes=["chat:write", "channels:read", "users:read"],
            configured=bool(os.getenv("SLACK_CLIENT_ID") and os.getenv("SLACK_CLIENT_SECRET"))
        )

        # Trello
        self._credentials_cache[OAuthService.TRELLO] = OAuthCredentials(
            client_id=os.getenv("TRELLO_API_KEY", ""),
            client_secret=os.getenv("TRELLO_API_SECRET", ""),
            redirect_uri=f"{base_protocol}://{self.production_domain}/api/auth/trello/oauth2callback",
            scopes=["read", "write"],
            configured=bool(os.getenv("TRELLO_API_KEY") and os.getenv("TRELLO_API_SECRET"))
        )

        # Asana
        self._credentials_cache[OAuthService.ASANA] = OAuthCredentials(
            client_id=os.getenv("ASANA_CLIENT_ID", ""),
            client_secret=os.getenv("ASANA_CLIENT_SECRET", ""),
            redirect_uri=f"{base_protocol}://{self.production_domain}/api/auth/asana/oauth2callback",
            scopes=["default"],
            configured=bool(os.getenv("ASANA_CLIENT_ID") and os.getenv("ASANA_CLIENT_SECRET"))
        )

        # Notion
        self._credentials_cache[OAuthService.NOTION] = OAuthCredentials(
            client_id=os.getenv("NOTION_CLIENT_ID", ""),
            client_secret=os.getenv("NOTION_CLIENT_SECRET", ""),
            redirect_uri=f"{base_protocol}://{self.production_domain}/api/auth/notion/oauth2callback",
            scopes=[],  # Notion doesn't use scopes
            configured=bool(os.getenv("NOTION_CLIENT_ID") and os.getenv("NOTION_CLIENT_SECRET"))
        )

        # Dropbox
        self._credentials_cache[OAuthService.DROPBOX] = OAuthCredentials(
            client_id=os.getenv("DROPBOX_CLIENT_ID", ""),
            client_secret=os.getenv("DROPBOX_CLIENT_SECRET", ""),
            redirect_uri=f"{base_protocol}://{self.production_domain}/api/auth/dropbox/oauth2callback",
            scopes=["files.metadata.read", "files.content.read"],
            configured=bool(os.getenv("DROPBOX_CLIENT_ID") and os.getenv("DROPBOX_CLIENT_SECRET"))
        )

        # Microsoft Outlook
        self._credentials_cache[OAuthService.OUTLOOK] = OAuthCredentials(
            client_id=os.getenv("OUTLOOK_CLIENT_ID", ""),
            client_secret=os.getenv("OUTLOOK_CLIENT_SECRET", ""),
            redirect_uri=f"{base_protocol}://{self.production_domain}/api/auth/outlook/oauth2callback",
            scopes=["https://graph.microsoft.com/Mail.Read", "https://graph.microsoft.com/Calendars.Read"],
            configured=bool(os.getenv("OUTLOOK_CLIENT_ID") and os.getenv("OUTLOOK_CLIENT_SECRET"))
        )

        # Microsoft Teams
        self._credentials_cache[OAuthService.TEAMS] = OAuthCredentials(
            client_id=os.getenv("TEAMS_CLIENT_ID", ""),
            client_secret=os.getenv("TEAMS_CLIENT_SECRET", ""),
            redirect_uri=f"{base_protocol}://{self.production_domain}/api/auth/teams/oauth2callback",
            scopes=["https://graph.microsoft.com/Team.ReadBasic.All", "https://graph.microsoft.com/Chat.Read"],
            configured=bool(os.getenv("TEAMS_CLIENT_ID") and os.getenv("TEAMS_CLIENT_SECRET"))
        )

        # GitHub
        self._credentials_cache[OAuthService.GITHUB] = OAuthCredentials(
            client_id=os.getenv("GITHUB_CLIENT_ID", ""),
            client_secret=os.getenv("GITHUB_CLIENT_SECRET", ""),
            redirect_uri=f"{base_protocol}://{self.production_domain}/api/auth/github/oauth2callback",
            scopes=["repo", "user", "read:org"],
            configured=bool(os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"))
        )

    def get_credentials(self, service: OAuthService) -> OAuthCredentials:
        """Get OAuth credentials for a specific service"""
        return self._credentials_cache.get(service, OAuthCredentials("", "", "", [], False))

    def get_outlook_config(self) -> OAuthCredentials:
        """Get Microsoft Outlook OAuth credentials"""
        return self.get_credentials(OAuthService.OUTLOOK)

    def get_teams_config(self) -> OAuthCredentials:
        """Get Microsoft Teams OAuth credentials"""
        return self.get_credentials(OAuthService.TEAMS)

    def get_github_config(self) -> OAuthCredentials:
        """Get GitHub OAuth credentials"""
        return self.get_credentials(OAuthService.GITHUB)

    def validate_all(self) -> Dict[str, Any]:
        """
        Validate all OAuth credentials are configured.

        Returns:
            Dict with:
            - valid (bool): True if all services configured
            - total (int): Total number of services
            - configured (int): Number of configured services
            - missing (List[str]): List of missing service names
        """
        total = len(OAuthService)
        configured = sum(1 for creds in self._credentials_cache.values() if creds.configured)
        missing = [
            service.value
            for service, creds in self._credentials_cache.items()
            if not creds.configured
        ]

        return {
            "valid": len(missing) == 0,
            "total": total,
            "configured": configured,
            "missing": missing
        }

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all OAuth services"""
        return {
            service.value: {
                "configured": creds.configured,
                "has_client_id": bool(creds.client_id),
                "has_client_secret": bool(creds.client_secret),
                "redirect_uri": creds.redirect_uri
            }
            for service, creds in self._credentials_cache.items()
        }

    def get_missing_credentials(self) -> List[str]:
        """Get list of environment variables that need to be set"""
        missing = []

        env_var_map = {
            OAuthService.GOOGLE: ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
            OAuthService.SLACK: ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"],
            OAuthService.TRELLO: ["TRELLO_API_KEY", "TRELLO_API_SECRET"],
            OAuthService.ASANA: ["ASANA_CLIENT_ID", "ASANA_CLIENT_SECRET"],
            OAuthService.NOTION: ["NOTION_CLIENT_ID", "NOTION_CLIENT_SECRET"],
            OAuthService.DROPBOX: ["DROPBOX_CLIENT_ID", "DROPBOX_CLIENT_SECRET"],
            OAuthService.OUTLOOK: ["OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET"],
            OAuthService.TEAMS: ["TEAMS_CLIENT_ID", "TEAMS_CLIENT_SECRET"],
            OAuthService.GITHUB: ["GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"]
        }

        for service, vars_list in env_var_map.items():
            creds = self._credentials_cache.get(service)
            if not creds or not creds.configured:
                missing.extend(vars_list)

        return missing


# Singleton instance
_oauth_config: Optional[OAuthConfig] = None


def get_oauth_config() -> OAuthConfig:
    """Get the global OAuth configuration instance"""
    global _oauth_config
    if _oauth_config is None:
        _oauth_config = OAuthConfig()
    return _oauth_config


def validate_oauth_before_deployment() -> bool:
    """
    Validate OAuth credentials before deployment.

    Returns:
        True if all required credentials are configured
    """
    config = get_oauth_config()
    validation = config.validate_all()

    if not validation["valid"]:
        logger.error("OAuth validation failed:")
        for service in validation["missing"]:
            logger.error(f"  - Missing credentials for: {service}")
        return False

    logger.info("OAuth validation passed: All services configured")
    return True
