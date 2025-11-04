"""
Outlook OAuth Handler
Follows GitLab pattern for consistency
"""

import os
import requests
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify

class OutlookOAuthHandler:
    """Handle Outlook OAuth authentication and API calls"""
    
    def __init__(self):
        self.client_id = os.getenv('OUTLOOK_CLIENT_ID')
        self.client_secret = os.getenv('OUTLOOK_CLIENT_SECRET')
        self.tenant_id = os.getenv('OUTLOOK_TENANT_ID', 'common')
        self.redirect_uri = os.getenv('OUTLOOK_REDIRECT_URI', 'http://localhost:3000/oauth/outlook/callback')
        self.api_base_url = 'https://graph.microsoft.com/v1.0'
        self.auth_base_url = 'https://login.microsoftonline.com'
        
        # Microsoft Graph API scopes
        self.scopes = [
            'https://graph.microsoft.com/Mail.Read',
            'https://graph.microsoft.com/Mail.Send',
            'https://graph.microsoft.com/Mail.ReadWrite',
            'https://graph.microsoft.com/Calendars.Read',
            'https://graph.microsoft.com/Calendars.ReadWrite',
            'https://graph.microsoft.com/User.Read',
            'https://graph.microsoft.com/offline_access',
        ]
        
    def get_oauth_url(self, user_id=None, state=None):
        """Generate Outlook OAuth authorization URL"""
        if not self.client_id:
            return {
                'success': False,
                'error': 'Outlook client ID not configured',
                'service': 'outlook'
            }
        
        if not state:
            state = f'outlook_oauth_{datetime.now().timestamp()}'
            if user_id:
                state = f'{state}_{user_id}'
        
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(self.scopes),
            'state': state,
            'prompt': 'consent',
            'response_mode': 'query'
        }
        
        oauth_url = f'{self.auth_base_url}/{self.tenant_id}/oauth2/v2.0/authorize?{requests.compat.urlencode(params)}'
        
        return {
            'success': True,
            'oauth_url': oauth_url,
            'service': 'outlook',
            'state': state,
            'client_id': self.client_id[:10] + '...' if self.client_id else None,
            'tenant_id': self.tenant_id
        }
    
    def exchange_code_for_token(self, code, state=None):
        """Exchange authorization code for access token"""
        if not code:
            return {
                'success': False,
                'error': 'Authorization code required',
                'service': 'outlook'
            }
        
        if not self.client_id or not self.client_secret:
            return {
                'success': False,
                'error': 'Outlook client ID or secret not configured',
                'service': 'outlook'
            }
        
        try:
            token_url = f'{self.auth_base_url}/{self.tenant_id}/oauth2/v2.0/token'
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': self.redirect_uri,
                'scope': ' '.join(self.scopes)
            }
            
            response = requests.post(token_url, data=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                refresh_token = token_data.get('refresh_token')
                
                if not access_token:
                    return {
                        'success': False,
                        'error': 'Access token not found in response',
                        'service': 'outlook',
                        'response': token_data
                    }
                
                # Get user information
                user_info = self.get_user_info(access_token)
                
                if user_info.get('success'):
                    return {
                        'success': True,
                        'service': 'outlook',
                        'tokens': {
                            'access_token': access_token,
                            'refresh_token': refresh_token,
                            'token_type': token_data.get('token_type', 'Bearer'),
                            'scope': token_data.get('scope'),
                            'expires_in': token_data.get('expires_in', 3600)
                        },
                        'user_info': user_info.get('user_info'),
                        'workspace_info': {
                            'tenant_id': self.tenant_id,
                            'api_base_url': self.api_base_url,
                            'auth_base_url': self.auth_base_url,
                            'connected_at': datetime.now(timezone.utc).isoformat()
                        },
                        'state': state
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to get user information',
                        'service': 'outlook',
                        'details': user_info
                    }
            else:
                return {
                    'success': False,
                    'error': 'Failed to exchange authorization code',
                    'service': 'outlook',
                    'status_code': response.status_code,
                    'response': response.text
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Outlook OAuth token exchange error: {str(e)}',
                'service': 'outlook'
            }
    
    def get_user_info(self, access_token):
        """Get Outlook user information using access token"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(f'{self.api_base_url}/me', headers=headers, timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    'success': True,
                    'user_info': {
                        'id': user_data.get('id'),
                        'displayName': user_data.get('displayName'),
                        'givenName': user_data.get('givenName'),
                        'surname': user_data.get('surname'),
                        'userPrincipalName': user_data.get('userPrincipalName'),
                        'jobTitle': user_data.get('jobTitle'),
                        'mail': user_data.get('mail'),
                        'mobilePhone': user_data.get('mobilePhone'),
                        'officeLocation': user_data.get('officeLocation'),
                        'preferredLanguage': user_data.get('preferredLanguage')
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to get Outlook user info',
                    'status_code': response.status_code,
                    'response': response.text
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Outlook user info error: {str(e)}'
            }
    
    def health_check(self):
        """Check Outlook service health and configuration"""
        status = {
            'service': 'outlook',
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'components': {}
        }
        
        # Check OAuth configuration
        if self.client_id and self.client_secret:
            status['components']['oauth'] = {
                'status': 'configured', 
                'message': 'OAuth credentials available',
                'client_id': self.client_id[:10] + '...' if self.client_id else None,
                'tenant_id': self.tenant_id
            }
        else:
            status['components']['oauth'] = {
                'status': 'missing', 
                'message': 'OAuth credentials not found'
            }
            status['status'] = 'unhealthy'
        
        # Check API connectivity
        try:
            response = requests.get(f'{self.api_base_url}/$metadata', timeout=5)
            if response.status_code == 200:
                status['components']['api'] = {
                    'status': 'connected',
                    'message': 'Microsoft Graph API connection successful'
                }
            else:
                status['components']['api'] = {
                    'status': 'error',
                    'message': f'Microsoft Graph API returned status {response.status_code}'
                }
                status['status'] = 'unhealthy'
        except Exception as e:
            status['components']['api'] = {
                'status': 'error',
                'message': f'Microsoft Graph API connection failed: {str(e)}'
            }
            status['status'] = 'unhealthy'
        
        return status


# Export handler for use in existing system
outlook_oauth_handler = OutlookOAuthHandler()