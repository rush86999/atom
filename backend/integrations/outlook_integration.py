import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote
import requests

from core.memory_integration_mixin import MemoryIntegrationMixin

logger = logging.getLogger(__name__)

class OutlookIntegration(MemoryIntegrationMixin):
    def __init__(self):
        self.client_id = os.getenv('OUTLOOK_CLIENT_ID')
        self.client_secret = os.getenv('OUTLOOK_CLIENT_SECRET')
        self.api_endpoint = 'https://graph.microsoft.com'
        self.access_token = None
        # Initialize memory integration mixin
        super().__init__(integration_id="outlook")
        
    def set_access_token(self, token: str):
        self.access_token = token
        
    def get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            if 'outlook' == 'github':
                headers["Authorization"] = f"token {self.access_token}"
            elif 'outlook' in ['slack', 'teams', 'outlook']:
                headers["Authorization"] = f"Bearer {self.access_token}"
            else:
                headers["Authorization"] = f"Bearer {self.access_token}"
        return headers
    
    async def get_user_info(self) -> Optional[Dict]:
        try:
            endpoint = self._get_user_endpoint()
            response = requests.get(endpoint, headers=self.get_headers())
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get user info: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
    
    async def list_items(self) -> List[Dict]:
        try:
            endpoint = self._get_list_endpoint()
            response = requests.get(endpoint, headers=self.get_headers())
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to list items: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error listing items: {e}")
            return []
    
    async def create_item(self, item_data: Dict) -> Optional[Dict]:
        try:
            endpoint = self._get_create_endpoint()
            response = requests.post(endpoint, json=item_data, headers=self.get_headers())
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"Failed to create item: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error creating item: {e}")
            return None
    
    def _get_user_endpoint(self) -> str:
        endpoints = {
            'github': '/user',
            'google': '/oauth2/v2/userinfo',
            'slack': '/auth.test',
            'outlook': '/me',
            'teams': '/me'
        }
        base_url = self.api_endpoint
        if 'outlook' == 'teams':
            base_url = 'https://graph.microsoft.com'
        return f"{base_url}{endpoints.get('outlook', '/me')}"
    
    def _get_list_endpoint(self) -> str:
        endpoints = {
            'github': '/user/repos',
            'google': '/calendar/v3/calendars/primary/events',
            'slack': '/conversations.list',
            'outlook': '/me/messages',
            'teams': '/chats'
        }
        base_url = self.api_endpoint
        if 'outlook' in ['teams', 'outlook']:
            base_url = 'https://graph.microsoft.com'
        return f"{base_url}{endpoints.get('outlook', '/items')}"
    
    def _get_create_endpoint(self) -> str:
        endpoints = {
            'github': '/user/repos',
            'google': '/calendar/v3/calendars/primary/events',
            'slack': '/chat.postMessage',
            'outlook': '/me/sendMail',
            'teams': '/chats'
        }
        base_url = self.api_endpoint
        if 'outlook' in ['teams', 'outlook']:
            base_url = 'https://graph.microsoft.com'
        return f"{base_url}{endpoints.get('outlook', '/items')}"

    # ==========================================================================
    # Memory Integration Methods
    # ==========================================================================

    async def fetch_records(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from Outlook for memory backfill.

        Args:
            start_date: Fetch emails from this date (default: 30 days ago)
            end_date: Fetch emails until this date (default: now)
            limit: Maximum number of emails to fetch

        Returns:
            List of email records with metadata
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        try:
            # Build Microsoft Graph API filter with proper escaping to prevent OData injection
            start_formatted = quote(start_date.isoformat())
            end_formatted = quote(end_date.isoformat())
            filter_query = f"receivedDateTime ge {start_formatted} and receivedDateTime le {end_formatted}"

            # Build endpoint
            endpoint = f"{self.api_endpoint}/v1.0/me/messages?$filter={filter_query}&$top={limit}&$select=id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,sender"

            response = requests.get(endpoint, headers=self.get_headers())

            if response.status_code == 200:
                data = response.json()
                messages = data.get("value", [])

                # Normalize to standard format
                records = []
                for msg in messages:
                    try:
                        # Extract sender
                        from_email = ""
                        sender = msg.get("sender", {})
                        if sender and "emailAddress" in sender:
                            from_email = sender["emailAddress"].get("address", "")

                        # Extract recipients
                        to_emails = []
                        for recipient in msg.get("toRecipients", []):
                            if "emailAddress" in recipient:
                                to_emails.append(recipient["emailAddress"].get("address", ""))

                        cc_emails = []
                        for recipient in msg.get("ccRecipients", []):
                            if "emailAddress" in recipient:
                                cc_emails.append(recipient["emailAddress"].get("address", ""))

                        # Extract body
                        body = ""
                        body_content = msg.get("body", {})
                        if body_content:
                            body = body_content.get("content", "")

                        record = {
                            "id": msg.get("id", ""),
                            "type": "email",
                            "subject": msg.get("subject", ""),
                            "from": from_email,
                            "to": to_emails,
                            "cc": cc_emails,
                            "date": msg.get("receivedDateTime", ""),
                            "body": body,
                            "url": f"https://outlook.office.com/owa/?ItemID={msg.get('id', '')}",
                            "integration": "outlook"
                        }
                        records.append(record)

                    except Exception as e:
                        logger.warning(f"Error normalizing Outlook message: {e}")
                        continue

                logger.info(f"Fetched {len(records)} emails from Outlook")
                return records

            else:
                logger.error(f"Failed to fetch Outlook emails: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error fetching Outlook records: {e}")
            return []

# Global integration instance
outlook_integration = OutlookIntegration()
