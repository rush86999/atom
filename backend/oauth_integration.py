import os
import requests
import urllib.parse
import secrets
from typing import Dict, Optional

class OAuthIntegration:
    def __init__(self):
        self.oauth_server_url = "http://localhost:5058"
        self.services = {
            'github': {
                'client_id': os.getenv('GITHUB_CLIENT_ID'),
                'client_secret': os.getenv('GITHUB_CLIENT_SECRET'),
                'auth_url': 'https://github.com/login/oauth/authorize'
            },
            'google': {
                'client_id': os.getenv('GOOGLE_CLIENT_ID'),
                'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
                'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth'
            },
            'slack': {
                'client_id': os.getenv('SLACK_CLIENT_ID'),
                'client_secret': os.getenv('SLACK_CLIENT_SECRET'),
                'auth_url': 'https://slack.com/oauth/v2/authorize'
            }
        }
    
    async def initialize(self):
        pass
    
    async def close(self):
        pass
    
    def check_status(self) -> Dict:
        return {"oauth_server": "connected"}
    
    async def get_authorization_url(self, service: str) -> str:
        if service not in self.services:
            raise ValueError(f"Service {service} not supported")
        
        service_config = self.services[service]
        state = secrets.token_urlsafe(32)
        redirect_uri = f"{self.oauth_server_url}/api/auth/{service}/callback"
        
        auth_params = {
            'client_id': service_config['client_id'],
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'state': state
        }
        
        auth_url = f"{service_config['auth_url']}?{urllib.parse.urlencode(auth_params)}"
        return auth_url

# Global instance
oauth_integration = OAuthIntegration()
