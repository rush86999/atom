#!/usr/bin/env python3
"""
Next.js/Vercel OAuth Handler
Complete OAuth 2.0 integration for Vercel API
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session
from cryptography.fernet import Fernet
import base64

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Next.js OAuth Blueprint
nextjs_auth_bp = Blueprint('nextjs_auth', __name__)

# Vercel OAuth Configuration
VERCEL_CLIENT_ID = os.getenv('VERCEL_CLIENT_ID')
VERCEL_CLIENT_SECRET = os.getenv('VERCEL_CLIENT_SECRET')
VERCEL_REDIRECT_URI = os.getenv('VERCEL_REDIRECT_URI', 'http://localhost:3000/oauth/nextjs/callback')
NEXTJS_API_BASE_URL = 'https://api.vercel.com'

# Encryption key for token storage (use Fernet from environment)
ENCRYPTION_KEY = os.getenv('FERNET_KEY', Fernet.generate_key())
if isinstance(ENCRYPTION_KEY, str):
    ENCRYPTION_KEY = ENCRYPTION_KEY.encode()
cipher_suite = Fernet(ENCRYPTION_KEY)

# In-memory storage for demo (replace with database in production)
oauth_tokens = {}
user_sessions = {}

class NextjsOAuthHandler:
    """Handles Next.js/Vercel OAuth 2.0 flow"""
    
    def __init__(self):
        self.client_id = VERCEL_CLIENT_ID
        self.client_secret = VERCEL_CLIENT_SECRET
        self.redirect_uri = VERCEL_REDIRECT_URI
        self.api_base_url = NEXTJS_API_BASE_URL
        
    def get_authorization_url(self, state=None, scopes=None):
        """Generate Vercel OAuth authorization URL"""
        if not self.client_id:
            raise ValueError("VERCEL_CLIENT_ID environment variable is required")
            
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
        }
        
        if state:
            params['state'] = state
            
        if scopes:
            params['scope'] = ' '.join(scopes)
        else:
            # Default scopes for Next.js integration
            params['scope'] = 'read write projects deployments builds'
            
        # Vercel OAuth URL
        auth_url = 'https://vercel.com/oauth/authorize'
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        
        return f"{auth_url}?{query_string}"
    
    def exchange_code_for_token(self, code):
        """Exchange authorization code for access token"""
        if not self.client_secret:
            raise ValueError("VERCEL_CLIENT_SECRET environment variable is required")
            
        token_url = f"{self.api_base_url}/v2/oauth/access_token"
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(token_url, data=data, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Store token with metadata
            token_info = {
                'access_token': token_data.get('access_token'),
                'token_type': token_data.get('token_type', 'Bearer'),
                'created_at': datetime.utcnow().isoformat(),
                'expires_in': token_data.get('expires_in', 86400),  # Default 24 hours
            }
            
            # Add refresh token if available
            if 'refresh_token' in token_data:
                token_info['refresh_token'] = token_data['refresh_token']
            
            return token_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Token exchange failed: {str(e)}")
            raise Exception(f"Failed to exchange code for token: {str(e)}")
    
    def encrypt_token(self, token_data):
        """Encrypt sensitive token data"""
        token_json = json.dumps(token_data)
        encrypted_token = cipher_suite.encrypt(token_json.encode())
        return base64.b64encode(encrypted_token).decode()
    
    def decrypt_token(self, encrypted_token):
        """Decrypt sensitive token data"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_token.encode())
            decrypted_bytes = cipher_suite.decrypt(encrypted_bytes)
            return json.loads(decrypted_bytes.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt token: {str(e)}")
            return None
    
    def get_user_info(self, access_token):
        """Get user information from Vercel API"""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(f"{self.api_base_url}/v2/user", headers=headers)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get user info: {str(e)}")
            return None
    
    def get_user_projects(self, access_token, limit=50, status='active'):
        """Get user's Vercel projects"""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'limit': limit
        }
        
        if status != 'all':
            params['status'] = status
        
        try:
            response = requests.get(f"{self.api_base_url}/v9/projects", headers=headers, params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get projects: {str(e)}")
            return {'projects': [], 'error': str(e)}
    
    def get_project_builds(self, access_token, project_id, limit=20):
        """Get builds for a specific project"""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'limit': limit
        }
        
        try:
            response = requests.get(
                f"{self.api_base_url}/v9/projects/{project_id}/builds", 
                headers=headers, 
                params=params
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get builds: {str(e)}")
            return {'builds': [], 'error': str(e)}
    
    def get_project_deployments(self, access_token, project_id, limit=20):
        """Get deployments for a specific project"""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'limit': limit
        }
        
        try:
            response = requests.get(
                f"{self.api_base_url}/v13/deployments", 
                headers=headers, 
                params={'projectId': project_id, 'limit': limit}
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get deployments: {str(e)}")
            return {'deployments': [], 'error': str(e)}
    
    def get_project_analytics(self, access_token, project_id, from_date=None, to_date=None):
        """Get analytics for a specific project"""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        params = {}
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
            
        try:
            response = requests.get(
                f"{self.api_base_url}/v4/projects/{project_id}/analytics", 
                headers=headers, 
                params=params
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get analytics: {str(e)}")
            return {'analytics': {}, 'error': str(e)}
    
    def trigger_deployment(self, access_token, project_id, branch='main'):
        """Trigger a new deployment"""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'name': f'deployment-{datetime.utcnow().isoformat()}',
            'project': project_id,
            'target': {
                'branch': branch
            }
        }
        
        try:
            response = requests.post(
                f"{self.api_base_url}/v13/deployments", 
                headers=headers, 
                json=data
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to trigger deployment: {str(e)}")
            return {'error': str(e)}

# Initialize OAuth handler
oauth_handler = NextjsOAuthHandler()

@nextjs_auth_bp.route('/nextjs/authorize', methods=['POST'])
def authorize_nextjs():
    """Initiate Next.js/Vercel OAuth flow"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        scopes = data.get('scopes', ['read', 'write', 'projects', 'deployments', 'builds'])
        platform = data.get('platform', 'web')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': 'User ID is required'
            }), 400
        
        # Generate state parameter for security
        state = f"{user_id}_{datetime.utcnow().timestamp()}_{platform}"
        
        # Store state in session
        user_sessions[state] = {
            'user_id': user_id,
            'platform': platform,
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Generate authorization URL
        auth_url = oauth_handler.get_authorization_url(state=state, scopes=scopes)
        
        return jsonify({
            'ok': True,
            'authorization_url': auth_url,
            'user_id': user_id,
            'csrf_token': state
        })
        
    except Exception as e:
        logger.error(f"OAuth authorization error: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@nextjs_auth_bp.route('/nextjs/callback', methods=['POST'])
def callback_nextjs():
    """Handle OAuth callback from Vercel"""
    try:
        data = request.get_json()
        code = data.get('code')
        state = data.get('state')
        platform = data.get('platform', 'web')
        
        if not code:
            return jsonify({
                'ok': False,
                'error': 'Authorization code is required'
            }), 400
        
        # Verify state parameter
        if state not in user_sessions:
            return jsonify({
                'ok': False,
                'error': 'Invalid or expired state parameter'
            }), 400
        
        session_data = user_sessions.pop(state)
        user_id = session_data['user_id']
        
        # Exchange code for access token
        token_data = oauth_handler.exchange_code_for_token(code)
        
        # Get user information
        user_info = oauth_handler.get_user_info(token_data['access_token'])
        
        # Get user's projects
        projects_data = oauth_handler.get_user_projects(token_data['access_token'])
        
        # Encrypt and store token
        encrypted_token = oauth_handler.encrypt_token(token_data)
        oauth_tokens[user_id] = {
            'encrypted_token': encrypted_token,
            'user_id': user_id,
            'user_info': user_info,
            'created_at': datetime.utcnow().isoformat(),
            'platform': platform
        }
        
        return jsonify({
            'ok': True,
            'access_token': token_data['access_token'],  # Note: In production, don't return this
            'refresh_token': token_data.get('refresh_token'),
            'expires_at': (datetime.utcnow() + timedelta(seconds=token_data['expires_in'])).isoformat(),
            'user': user_info,
            'projects': projects_data.get('projects', []),
            'team_id': user_info.get('uid') if user_info else None
        })
        
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@nextjs_auth_bp.route('/nextjs/status', methods=['GET'])
def status_nextjs():
    """Check Next.js integration status"""
    try:
        # For demo, return a simple status check
        # In production, check if valid tokens exist for the session/user
        user_id = request.args.get('user_id')
        
        if user_id and user_id in oauth_tokens:
            token_data = oauth_tokens[user_id]
            return jsonify({
                'connected': True,
                'user_id': user_id,
                'user_info': token_data.get('user_info'),
                'last_sync': token_data.get('created_at'),
                'team_id': token_data.get('user_info', {}).get('uid')
            })
        else:
            return jsonify({
                'connected': False,
                'error': 'No active integration found'
            })
            
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        return jsonify({
            'connected': False,
            'error': str(e)
        }), 500

# Integration endpoints
@nextjs_auth_bp.route('/integrations/nextjs/projects', methods=['POST'])
def get_nextjs_projects():
    """Get Next.js projects"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        limit = data.get('limit', 50)
        status = data.get('status', 'active')
        include_builds = data.get('include_builds', False)
        include_deployments = data.get('include_deployments', True)
        
        if not user_id or user_id not in oauth_tokens:
            return jsonify({
                'ok': False,
                'error': 'User not authenticated with Next.js'
            }), 401
        
        token_data = oauth_tokens[user_id]
        decrypted_token = oauth_handler.decrypt_token(token_data['encrypted_token'])
        
        if not decrypted_token:
            return jsonify({
                'ok': False,
                'error': 'Invalid authentication token'
            }), 401
        
        access_token = decrypted_token['access_token']
        
        # Get projects
        projects_data = oauth_handler.get_user_projects(access_token, limit, status)
        projects = projects_data.get('projects', [])
        
        # Optionally get builds and deployments for each project
        builds = []
        deployments = []
        
        if include_builds and projects:
            for project in projects[:5]:  # Limit to avoid rate limiting
                project_builds = oauth_handler.get_project_builds(access_token, project.get('id'))
                builds.extend(project_builds.get('builds', []))
        
        if include_deployments and projects:
            for project in projects[:5]:  # Limit to avoid rate limiting
                project_deployments = oauth_handler.get_project_deployments(access_token, project.get('id'))
                deployments.extend(project_deployments.get('deployments', []))
        
        return jsonify({
            'ok': True,
            'projects': projects,
            'builds': builds,
            'deployments': deployments
        })
        
    except Exception as e:
        logger.error(f"Get projects error: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@nextjs_auth_bp.route('/integrations/nextjs/analytics', methods=['POST'])
def get_nextjs_analytics():
    """Get analytics for a Next.js project"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        date_range = data.get('date_range')
        
        if not user_id or not project_id:
            return jsonify({
                'ok': False,
                'error': 'User ID and Project ID are required'
            }), 400
        
        if user_id not in oauth_tokens:
            return jsonify({
                'ok': False,
                'error': 'User not authenticated with Next.js'
            }), 401
        
        token_data = oauth_tokens[user_id]
        decrypted_token = oauth_handler.decrypt_token(token_data['encrypted_token'])
        
        if not decrypted_token:
            return jsonify({
                'ok': False,
                'error': 'Invalid authentication token'
            }), 401
        
        access_token = decrypted_token['access_token']
        
        # Get analytics
        from_date = date_range.get('start') if date_range else None
        to_date = date_range.get('end') if date_range else None
        
        analytics_data = oauth_handler.get_project_analytics(
            access_token, 
            project_id, 
            from_date, 
            to_date
        )
        
        return jsonify({
            'ok': True,
            'analytics': analytics_data,
            'date_range': date_range
        })
        
    except Exception as e:
        logger.error(f"Get analytics error: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@nextjs_auth_bp.route('/integrations/nextjs/builds', methods=['POST'])
def get_nextjs_builds():
    """Get builds for a Next.js project"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        limit = data.get('limit', 20)
        
        if not user_id or not project_id:
            return jsonify({
                'ok': False,
                'error': 'User ID and Project ID are required'
            }), 400
        
        if user_id not in oauth_tokens:
            return jsonify({
                'ok': False,
                'error': 'User not authenticated with Next.js'
            }), 401
        
        token_data = oauth_tokens[user_id]
        decrypted_token = oauth_handler.decrypt_token(token_data['encrypted_token'])
        
        if not decrypted_token:
            return jsonify({
                'ok': False,
                'error': 'Invalid authentication token'
            }), 401
        
        access_token = decrypted_token['access_token']
        
        # Get builds
        builds_data = oauth_handler.get_project_builds(access_token, project_id, limit)
        
        return jsonify({
            'ok': True,
            'builds': builds_data.get('builds', [])
        })
        
    except Exception as e:
        logger.error(f"Get builds error: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# Health check endpoint
@nextjs_auth_bp.route('/nextjs/health', methods=['GET'])
def health_nextjs():
    """Health check for Next.js integration"""
    try:
        # Check environment variables
        env_status = all([
            VERCEL_CLIENT_ID,
            VERCEL_CLIENT_SECRET,
            ENCRYPTION_KEY
        ])
        
        return jsonify({
            'status': 'healthy' if env_status else 'unhealthy',
            'services': {
                'nextjs': {
                    'status': 'healthy' if env_status else 'unhealthy',
                    'error': None if env_status else 'Missing required environment variables'
                }
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'services': {
                'nextjs': {
                    'status': 'unhealthy',
                    'error': str(e)
                }
            }
        }), 500

@nextjs_auth_bp.route('/integrations/nextjs/project', methods=['POST'])
def get_nextjs_project():
    """Get detailed information about a specific Next.js project"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        include_environment_variables = data.get('include_environment_variables', False)
        
        if not user_id or not project_id:
            return jsonify({
                'ok': False,
                'error': 'User ID and Project ID are required'
            }), 400
        
        if user_id not in oauth_tokens:
            return jsonify({
                'ok': False,
                'error': 'User not authenticated with Next.js'
            }), 401
        
        token_data = oauth_tokens[user_id]
        decrypted_token = oauth_handler.decrypt_token(token_data['encrypted_token'])
        
        if not decrypted_token:
            return jsonify({
                'ok': False,
                'error': 'Invalid authentication token'
            }), 401
        
        access_token = decrypted_token['access_token']
        
        # Get project details
        project_response = requests.get(
            f"{NEXTJS_API_BASE_URL}/v9/projects/{project_id}",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
        )
        project_response.raise_for_status()
        project_data = project_response.json()
        
        # Get recent builds
        builds_response = requests.get(
            f"{NEXTJS_API_BASE_URL}/v9/projects/{project_id}/builds",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            params={'limit': 10}
        )
        builds = []
        if builds_response.status_code == 200:
            builds = builds_response.json().get('builds', [])
        
        # Get recent deployments
        deployments_response = requests.get(
            f"{NEXTJS_API_BASE_URL}/v13/deployments",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            params={'projectId': project_id, 'limit': 10}
        )
        deployments = []
        if deployments_response.status_code == 200:
            deployments = deployments_response.json().get('deployments', [])
        
        # Get environment variables if requested
        env_vars = []
        if include_environment_variables:
            env_vars_response = requests.get(
                f"{NEXTJS_API_BASE_URL}/v9/projects/{project_id}/env",
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }
            )
            if env_vars_response.status_code == 200:
                env_vars = env_vars_response.json().get('envs', [])
        
        return jsonify({
            'ok': True,
            'project': project_data,
            'builds': builds,
            'deployments': deployments,
            'environment_variables': env_vars
        })
        
    except Exception as e:
        logger.error(f"Get project details error: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@nextjs_auth_bp.route('/integrations/nextjs/deploy', methods=['POST'])
def deploy_nextjs():
    """Trigger a new deployment for a Next.js project"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        branch = data.get('branch', 'main')
        force = data.get('force', False)
        
        if not user_id or not project_id:
            return jsonify({
                'ok': False,
                'error': 'User ID and Project ID are required'
            }), 400
        
        if user_id not in oauth_tokens:
            return jsonify({
                'ok': False,
                'error': 'User not authenticated with Next.js'
            }), 401
        
        token_data = oauth_tokens[user_id]
        decrypted_token = oauth_handler.decrypt_token(token_data['encrypted_token'])
        
        if not decrypted_token:
            return jsonify({
                'ok': False,
                'error': 'Invalid authentication token'
            }), 401
        
        access_token = decrypted_token['access_token']
        
        # Trigger deployment
        deployment_data = oauth_handler.trigger_deployment(access_token, project_id, branch)
        
        if 'error' in deployment_data:
            return jsonify({
                'ok': False,
                'error': deployment_data['error']
            }), 500
        
        return jsonify({
            'ok': True,
            'deployment': deployment_data,
            'deployment_url': deployment_data.get('url'),
            'message': f'Deployment triggered for project {project_id} on branch {branch}'
        })
        
    except Exception as e:
        logger.error(f"Trigger deployment error: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@nextjs_auth_bp.route('/integrations/nextjs/env-vars', methods=['POST'])
def manage_env_vars():
    """Manage environment variables for a Next.js project"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        action = data.get('action', 'list')
        key = data.get('key')
        value = data.get('value')
        target = data.get('target', ['production', 'preview'])
        var_type = data.get('type', 'plain')
        
        if not user_id or not project_id:
            return jsonify({
                'ok': False,
                'error': 'User ID and Project ID are required'
            }), 400
        
        if user_id not in oauth_tokens:
            return jsonify({
                'ok': False,
                'error': 'User not authenticated with Next.js'
            }), 401
        
        token_data = oauth_tokens[user_id]
        decrypted_token = oauth_handler.decrypt_token(token_data['encrypted_token'])
        
        if not decrypted_token:
            return jsonify({
                'ok': False,
                'error': 'Invalid authentication token'
            }), 401
        
        access_token = decrypted_token['access_token']
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        result = None
        env_vars = []
        
        if action == 'list':
            # List environment variables
            response = requests.get(
                f"{NEXTJS_API_BASE_URL}/v9/projects/{project_id}/env",
                headers=headers
            )
            if response.status_code == 200:
                env_vars = response.json().get('envs', [])
            result = env_vars
            
        elif action == 'create':
            # Create environment variable
            if not key or not value:
                return jsonify({
                    'ok': False,
                    'error': 'Key and value are required for creating environment variable'
                }), 400
            
            env_data = {
                'key': key,
                'value': value,
                'target': target,
                'type': var_type
            }
            
            response = requests.post(
                f"{NEXTJS_API_BASE_URL}/v9/projects/{project_id}/env",
                headers=headers,
                json=env_data
            )
            response.raise_for_status()
            result = response.json()
            
        elif action == 'update':
            # Update environment variable
            if not key or not value:
                return jsonify({
                    'ok': False,
                    'error': 'Key and value are required for updating environment variable'
                }), 400
            
            env_data = {
                'value': value,
                'target': target,
                'type': var_type
            }
            
            response = requests.patch(
                f"{NEXTJS_API_BASE_URL}/v9/projects/{project_id}/env/{key}",
                headers=headers,
                json=env_data
            )
            response.raise_for_status()
            result = response.json()
            
        elif action == 'delete':
            # Delete environment variable
            if not key:
                return jsonify({
                    'ok': False,
                    'error': 'Key is required for deleting environment variable'
                }), 400
            
            response = requests.delete(
                f"{NEXTJS_API_BASE_URL}/v9/projects/{project_id}/env/{key}",
                headers=headers
            )
            response.raise_for_status()
            result = {'deleted': True}
            
        else:
            return jsonify({
                'ok': False,
                'error': f'Invalid action: {action}'
            }), 400
        
        return jsonify({
            'ok': True,
            'action': action,
            'result': result,
            'environment_variables': env_vars if action == 'list' else None,
            'message': f'Successfully {action}ed environment variable{key if key else "s"}'
        })
        
    except Exception as e:
        logger.error(f"Environment variables management error: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@nextjs_auth_bp.route('/integrations/nextjs/deployment/status', methods=['POST'])
def get_deployment_status():
    """Get the status of a specific deployment"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        deployment_id = data.get('deployment_id')
        include_build_info = data.get('include_build_info', True)
        
        if not user_id or not deployment_id:
            return jsonify({
                'ok': False,
                'error': 'User ID and Deployment ID are required'
            }), 400
        
        if user_id not in oauth_tokens:
            return jsonify({
                'ok': False,
                'error': 'User not authenticated with Next.js'
            }), 401
        
        token_data = oauth_tokens[user_id]
        decrypted_token = oauth_handler.decrypt_token(token_data['encrypted_token'])
        
        if not decrypted_token:
            return jsonify({
                'ok': False,
                'error': 'Invalid authentication token'
            }), 401
        
        access_token = decrypted_token['access_token']
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Get deployment information
        response = requests.get(
            f"{NEXTJS_API_BASE_URL}/v13/deployments/{deployment_id}",
            headers=headers
        )
        response.raise_for_status()
        deployment_data = response.json()
        
        build_data = None
        if include_build_info and 'buildId' in deployment_data:
            build_response = requests.get(
                f"{NEXTJS_API_BASE_URL}/v9/builds/{deployment_data['buildId']}",
                headers=headers
            )
            if build_response.status_code == 200:
                build_data = build_response.json()
        
        return jsonify({
            'ok': True,
            'deployment': deployment_data,
            'build': build_data,
            'status': deployment_data.get('status', 'unknown'),
            'url': deployment_data.get('url'),
            'created_at': deployment_data.get('createdAt'),
            'ready': deployment_data.get('ready', False)
        })
        
    except Exception as e:
        logger.error(f"Get deployment status error: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@nextjs_auth_bp.route('/integrations/nextjs/config', methods=['POST'])
def manage_config():
    """Manage Next.js integration configuration"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        config = data.get('config')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': 'User ID is required'
            }), 400
        
        if config:
            # Save configuration (in a real implementation, save to database)
            if user_id not in oauth_tokens:
                oauth_tokens[user_id] = {}
            
            oauth_tokens[user_id]['config'] = config
            return jsonify({
                'ok': True,
                'message': 'Configuration saved successfully',
                'config': config
            })
        else:
            # Load configuration
            config_data = {}
            if user_id in oauth_tokens:
                config_data = oauth_tokens[user_id].get('config', {})
            
            return jsonify({
                'ok': True,
                'config': config_data
            })
        
    except Exception as e:
        logger.error(f"Configuration management error: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Test the OAuth handler
    handler = NextjsOAuthHandler()
    print("Next.js OAuth Handler initialized successfully")