"""
Stripe OAuth Configuration Helper
Configuration and utilities for Stripe OAuth 2.0 authentication flow
"""

import os
import json
import requests
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import logging
from urllib.parse import urlencode, urljoin

logger = logging.getLogger(__name__)


class StripeOAuthConfig:
    """Configuration and utilities for Stripe OAuth 2.0 authentication"""

    # Stripe OAuth endpoints
    AUTHORIZE_URL = "https://connect.stripe.com/oauth/authorize"
    TOKEN_URL = "https://connect.stripe.com/oauth/token"
    DEAUTHORIZE_URL = "https://connect.stripe.com/oauth/deauthorize"

    # Default OAuth scopes
    DEFAULT_SCOPES = [
        "read_only",  # Read account data
        "payments",  # Process payments
        "customers",  # Manage customers
        "subscriptions",  # Manage subscriptions
        "products",  # Manage products
    ]

    def __init__(self):
        self.client_id = os.getenv("STRIPE_CLIENT_ID")
        self.client_secret = os.getenv("STRIPE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("STRIPE_REDIRECT_URI")
        self.scopes = os.getenv("STRIPE_SCOPES", " ".join(self.DEFAULT_SCOPES))

        # Validate configuration
        self._validate_config()

    def _validate_config(self):
        """Validate that required configuration is present"""
        missing_configs = []

        if not self.client_id:
            missing_configs.append("STRIPE_CLIENT_ID")
        if not self.client_secret:
            missing_configs.append("STRIPE_CLIENT_SECRET")
        if not self.redirect_uri:
            missing_configs.append("STRIPE_REDIRECT_URI")

        if missing_configs:
            logger.warning(
                f"Missing Stripe OAuth configuration: {', '.join(missing_configs)}"
            )

    def get_authorization_url(
        self, state: Optional[str] = None, scopes: Optional[str] = None
    ) -> str:
        """
        Generate Stripe OAuth authorization URL

        Args:
            state: Optional state parameter for security
            scopes: Optional custom scopes (defaults to configured scopes)

        Returns:
            Authorization URL for redirecting users
        """
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": scopes or self.scopes,
            "redirect_uri": self.redirect_uri,
        }

        if state:
            params["state"] = state

        # Add suggested capabilities for better user experience
        params["stripe_landing"] = "login"
        params["always_prompt"] = "true"

        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code_for_token(self, authorization_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token

        Args:
            authorization_code: The code received from Stripe after user authorization

        Returns:
            Dictionary containing access token and related information

        Raises:
            Exception: If token exchange fails
        """
        if not self.client_secret:
            raise ValueError("STRIPE_CLIENT_SECRET is required for token exchange")

        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": authorization_code,
        }

        if self.redirect_uri:
            data["redirect_uri"] = self.redirect_uri

        try:
            response = requests.post(self.TOKEN_URL, data=data, timeout=30)
            response.raise_for_status()

            token_data = response.json()

            # Add expiration timestamp for easier management
            if "expires_in" in token_data:
                expires_in = token_data["expires_in"]
                token_data["expires_at"] = (
                    datetime.utcnow() + timedelta(seconds=expires_in)
                ).isoformat()

            logger.info(
                f"Successfully exchanged code for token: {token_data.get('stripe_user_id')}"
            )
            return token_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Token exchange failed: {str(e)}")
            raise Exception(f"Failed to exchange authorization code: {str(e)}")

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token

        Args:
            refresh_token: The refresh token from previous authorization

        Returns:
            Dictionary containing new access token and related information

        Raises:
            Exception: If token refresh fails
        """
        if not self.client_secret:
            raise ValueError("STRIPE_CLIENT_SECRET is required for token refresh")

        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }

        try:
            response = requests.post(self.TOKEN_URL, data=data, timeout=30)
            response.raise_for_status()

            token_data = response.json()

            # Add expiration timestamp
            if "expires_in" in token_data:
                expires_in = token_data["expires_in"]
                token_data["expires_at"] = (
                    datetime.utcnow() + timedelta(seconds=expires_in)
                ).isoformat()

            logger.info(
                f"Successfully refreshed access token: {token_data.get('stripe_user_id')}"
            )
            return token_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise Exception(f"Failed to refresh access token: {str(e)}")

    def deauthorize_account(self, stripe_user_id: str) -> bool:
        """
        Deauthorize a Stripe account (revoke access)

        Args:
            stripe_user_id: The Stripe account ID to deauthorize

        Returns:
            True if deauthorization was successful

        Raises:
            Exception: If deauthorization fails
        """
        if not self.client_secret:
            raise ValueError("STRIPE_CLIENT_SECRET is required for deauthorization")

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "stripe_user_id": stripe_user_id,
        }

        try:
            response = requests.post(self.DEAUTHORIZE_URL, data=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            success = result.get("stripe_user_id") == stripe_user_id

            if success:
                logger.info(
                    f"Successfully deauthorized Stripe account: {stripe_user_id}"
                )
            else:
                logger.warning(f"Unexpected response during deauthorization: {result}")

            return success

        except requests.exceptions.RequestException as e:
            logger.error(f"Deauthorization failed: {str(e)}")
            raise Exception(f"Failed to deauthorize Stripe account: {str(e)}")

    def get_account_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get Stripe account information using access token

        Args:
            access_token: Valid Stripe access token

        Returns:
            Dictionary containing account information

        Raises:
            Exception: If account info retrieval fails
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            response = requests.get(
                "https://api.stripe.com/v1/account", headers=headers, timeout=30
            )
            response.raise_for_status()

            account_info = response.json()
            logger.info(f"Retrieved account info for: {account_info.get('id')}")
            return account_info

        except requests.exceptions.RequestException as e:
            logger.error(f"Account info retrieval failed: {str(e)}")
            raise Exception(f"Failed to retrieve account information: {str(e)}")

    def is_token_valid(self, access_token: str) -> bool:
        """
        Check if an access token is still valid

        Args:
            access_token: The access token to validate

        Returns:
            True if token is valid, False otherwise
        """
        try:
            # Try to make a simple API call to validate the token
            self.get_account_info(access_token)
            return True
        except Exception:
            return False

    def get_token_expiry(self, expires_at: str) -> datetime:
        """
        Parse token expiry timestamp

        Args:
            expires_at: ISO format timestamp string

        Returns:
            datetime object representing expiry time
        """
        return datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

    def is_token_expired(self, expires_at: str) -> bool:
        """
        Check if token has expired

        Args:
            expires_at: ISO format timestamp string

        Returns:
            True if token has expired, False otherwise
        """
        expiry_time = self.get_token_expiry(expires_at)
        return datetime.utcnow() > expiry_time

    def get_token_remaining_time(self, expires_at: str) -> timedelta:
        """
        Get remaining time until token expiry

        Args:
            expires_at: ISO format timestamp string

        Returns:
            timedelta representing remaining validity
        """
        expiry_time = self.get_token_expiry(expires_at)
        return expiry_time - datetime.utcnow()


# Global configuration instance
stripe_oauth_config = StripeOAuthConfig()


def validate_stripe_environment() -> Dict[str, bool]:
    """
    Validate Stripe environment configuration

    Returns:
        Dictionary with validation results
    """
    validation_results = {
        "client_id": bool(os.getenv("STRIPE_CLIENT_ID")),
        "client_secret": bool(os.getenv("STRIPE_CLIENT_SECRET")),
        "redirect_uri": bool(os.getenv("STRIPE_REDIRECT_URI")),
        "publishable_key": bool(os.getenv("STRIPE_PUBLISHABLE_KEY")),
        "secret_key": bool(os.getenv("STRIPE_SECRET_KEY")),
        "webhook_secret": bool(os.getenv("STRIPE_WEBHOOK_SECRET")),
    }

    all_valid = all(validation_results.values())
    validation_results["all_valid"] = all_valid

    if not all_valid:
        missing = [
            key
            for key, valid in validation_results.items()
            if not valid and key != "all_valid"
        ]
        logger.warning(f"Missing Stripe environment variables: {', '.join(missing)}")

    return validation_results


def get_stripe_oauth_status() -> Dict[str, Any]:
    """
    Get current Stripe OAuth configuration status

    Returns:
        Dictionary with configuration status and details
    """
    config = stripe_oauth_config

    return {
        "configured": bool(
            config.client_id and config.client_secret and config.redirect_uri
        ),
        "client_id": config.client_id or "Not configured",
        "redirect_uri": config.redirect_uri or "Not configured",
        "scopes": config.scopes,
        "validation": validate_stripe_environment(),
        "timestamp": datetime.utcnow().isoformat(),
    }

