import os
import requests
import json
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class SlackIntegration:
    def __init__(self):
        self.client_id = os.getenv('SLACK_CLIENT_ID')
        self.client_secret = os.getenv('SLACK_CLIENT_SECRET')
        self.api_endpoint = 'https://slack.com/api'
        self.access_token = None
        
    def set_access_token(self, token: str):
        self.access_token = token
        
    def get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            if 'slack' == 'github':
                headers["Authorization"] = f"token {self.access_token}"
            elif 'slack' in ['slack', 'teams', 'outlook']:
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
        if 'slack' == 'teams':
            base_url = 'https://graph.microsoft.com'
        return f"{base_url}{endpoints.get('slack', '/me')}"
    
    def _get_list_endpoint(self) -> str:
        endpoints = {
            'github': '/user/repos',
            'google': '/calendar/v3/calendars/primary/events',
            'slack': '/conversations.list',
            'outlook': '/me/messages',
            'teams': '/chats'
        }
        base_url = self.api_endpoint
        if 'slack' in ['teams', 'outlook']:
            base_url = 'https://graph.microsoft.com'
        return f"{base_url}{endpoints.get('slack', '/items')}"
    
    def _get_create_endpoint(self) -> str:
        endpoints = {
            'github': '/user/repos',
            'google': '/calendar/v3/calendars/primary/events',
            'slack': '/chat.postMessage',
            'outlook': '/me/sendMail',
            'teams': '/chats'
        }
        base_url = self.api_endpoint
        if 'slack' in ['teams', 'outlook']:
            base_url = 'https://graph.microsoft.com'
        return f"{base_url}{endpoints.get('slack', '/items')}"

# Global integration instance
slack_integration = SlackIntegration()
