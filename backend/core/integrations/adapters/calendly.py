"""
Calendly Integration Adapter

Provides OAuth-based integration with Calendly for scheduling and meeting management.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class CalendlyAdapter:
    """
    Adapter for Calendly OAuth integration.

    Supports:
    - OAuth 2.0 authentication
    - Event type and scheduling management
    - Event and invitee operations
    - Webhook and user management
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "calendly"
        self.base_url = "https://api.calendly.com"

        # OAuth credentials from environment
        self.client_id = os.getenv("CALENDLY_CLIENT_ID")
        self.client_secret = os.getenv("CALENDLY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("CALENDLY_REDIRECT_URI")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._user_uri: Optional[str] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Calendly OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Calendly OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("CALENDLY_CLIENT_ID not configured")

        # Calendly OAuth endpoint
        auth_url = "https://auth.calendly.com/oauth/authorize"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "default",
            "state": self.workspace_id,  # Use workspace_id as state
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Calendly OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_in, etc.
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Calendly OAuth credentials not configured")

        token_url = "https://auth.calendly.com/oauth/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, json=data)
                response.raise_for_status()

                token_data = response.json()

                # Store tokens
                self._access_token = token_data.get("access_token")
                _refresh_token = token_data.get("refresh_token")

                # Calculate token expiration (2 hours)
                if "expires_in" in token_data:
                    self._token_expires_at = datetime.now() + timedelta(
                        seconds=token_data["expires_in"]
                    )

                # Get user URI
                await self._get_current_user()

                logger.info(f"Successfully obtained Calendly access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Calendly token exchange failed: {e}")
            raise

    async def _get_current_user(self) -> Optional[str]:
        """Get the current user's URI."""
        if not self._access_token:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/me",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                data = response.json()
                self._user_uri = data.get("resource", {}).get("uri")
                return self._user_uri

        except Exception as e:
            logger.error(f"Failed to get Calendly user: {e}")
            return None

    async def test_connection(self) -> bool:
        """
        Test the Calendly API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token:
            return False

        try:
            user_uri = await self._get_current_user()
            return user_uri is not None

        except Exception as e:
            logger.error(f"Calendly connection test failed: {e}")
            return False

    async def get_event_types(self, user_uri: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve Calendly event types.

        Args:
            user_uri: User URI (empty for current user)

        Returns:
            List of event type objects
        """
        if not self._access_token:
            raise ValueError("Calendly access token not available")

        try:
            params = {}
            if user_uri:
                params["user"] = user_uri
            elif self._user_uri:
                params["user"] = self._user_uri

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/event_types",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                event_types = data.get("collection", [])

                logger.info(f"Retrieved {len(event_types)} Calendly event types for workspace {self.workspace_id}")
                return event_types

        except Exception as e:
            logger.error(f"Failed to retrieve Calendly event types: {e}")
            raise

    async def get_scheduled_events(self, user_uri: str = None, status: str = "active",
                                  start_date: str = None, end_date: str = None,
                                  limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieve scheduled Calendly events.

        Args:
            user_uri: User URI (empty for current user)
            status: Event status ("active", "canceled")
            start_date: Start date filter (ISO 8601)
            end_date: End date filter (ISO 8601)
            limit: Maximum number of results

        Returns:
            List of event objects
        """
        if not self._access_token:
            raise ValueError("Calendly access token not available")

        try:
            params = {
                "status": status,
                "max_results": limit
            }
            if user_uri or self._user_uri:
                params["user"] = user_uri or self._user_uri
            if start_date:
                params["min_start_time"] = start_date
            if end_date:
                params["max_start_time"] = end_date

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/scheduled_events",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                events = data.get("collection", [])

                logger.info(f"Retrieved {len(events)} Calendly events for workspace {self.workspace_id}")
                return events

        except Exception as e:
            logger.error(f"Failed to retrieve Calendly events: {e}")
            raise

    async def get_event(self, event_uuid: str) -> Dict[str, Any]:
        """
        Retrieve a specific Calendly event by UUID.

        Args:
            event_uuid: Event UUID

        Returns:
            Event details with all invitees
        """
        if not self._access_token:
            raise ValueError("Calendly access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/scheduled_events/{event_uuid}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                event = response.json()

                logger.info(f"Retrieved Calendly event {event_uuid} for workspace {self.workspace_id}")
                return event

        except Exception as e:
            logger.error(f"Failed to retrieve Calendly event {event_uuid}: {e}")
            raise

    async def get_event_invitees(self, event_uuid: str) -> List[Dict[str, Any]]:
        """
        Retrieve all invitees for a Calendly event.

        Args:
            event_uuid: Event UUID

        Returns:
            List of invitee objects
        """
        if not self._access_token:
            raise ValueError("Calendly access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/scheduled_events/{event_uuid}/invitees",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                data = response.json()
                invitees = data.get("collection", [])

                logger.info(f"Retrieved {len(invitees)} invitees for event {event_uuid}")
                return invitees

        except Exception as e:
            logger.error(f"Failed to retrieve Calendly event invitees: {e}")
            raise

    async def cancel_event(self, event_uuid: str, cancel_reason: str = None) -> Dict[str, Any]:
        """
        Cancel a scheduled Calendly event.

        Args:
            event_uuid: Event UUID to cancel
            cancel_reason: Reason for cancellation

        Returns:
            Canceled event object
        """
        if not self._access_token:
            raise ValueError("Calendly access token not available")

        try:
            data = {"status": "canceled"}
            if cancel_reason:
                data["cancel_reason"] = cancel_reason

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/scheduled_events/{event_uuid}/cancellation",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json=data
                )
                response.raise_for_status()

                event = response.json()

                logger.info(f"Canceled Calendly event {event_uuid} for workspace {self.workspace_id}")
                return event

        except Exception as e:
            logger.error(f"Failed to cancel Calendly event {event_uuid}: {e}")
            raise

    async def get_webhooks(self, user_uri: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve all Calendly webhooks.

        Args:
            user_uri: User URI (empty for current user)

        Returns:
            List of webhook subscriptions
        """
        if not self._access_token:
            raise ValueError("Calendly access token not available")

        try:
            params = {}
            if user_uri or self._user_uri:
                params["user"] = user_uri or self._user_uri

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/webhook_subscriptions",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                webhooks = data.get("collection", [])

                logger.info(f"Retrieved {len(webhooks)} Calendly webhooks for workspace {self.workspace_id}")
                return webhooks

        except Exception as e:
            logger.error(f"Failed to retrieve Calendly webhooks: {e}")
            raise

    async def create_webhook(self, url: str, events: List[str],
                           organization_uri: str = None, user_uri: str = None) -> Dict[str, Any]:
        """
        Create a Calendly webhook subscription.

        Args:
            url: Webhook callback URL
            events: List of events to subscribe to
            organization_uri: Organization URI
            user_uri: User URI

        Returns:
            Created webhook subscription
        """
        if not self._access_token:
            raise ValueError("Calendly access token not available")

        try:
            data = {
                "url": url,
                "events": events,
                "organization": organization_uri,
                "scope": "organization" if organization_uri else "user"
            }

            if user_uri or self._user_uri:
                data["user"] = user_uri or self._user_uri

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/webhook_subscriptions",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json=data
                )
                response.raise_for_status()

                webhook = response.json()

                logger.info(f"Created Calendly webhook for workspace {self.workspace_id}")
                return webhook

        except Exception as e:
            logger.error(f"Failed to create Calendly webhook: {e}")
            raise

    async def delete_webhook(self, webhook_uuid: str) -> bool:
        """
        Delete a Calendly webhook subscription.

        Args:
            webhook_uuid: Webhook UUID to delete

        Returns:
            True if successful
        """
        if not self._access_token:
            raise ValueError("Calendly access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/webhook_subscriptions/{webhook_uuid}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Deleted Calendly webhook {webhook_uuid} in workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete Calendly webhook {webhook_uuid}: {e}")
            return False
