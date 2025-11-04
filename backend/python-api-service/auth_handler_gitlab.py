"""
GitLab OAuth Handler
Integrates with ATOM's existing OAuth system
"""

import os
import requests
import json
from datetime import datetime
from flask import Flask, request, jsonify

class GitLabOAuthHandler:
    """Handle GitLab OAuth authentication and API calls"""
    
    def __init__(self):
        self.client_id = os.getenv('GITLAB_CLIENT_ID')
        self.client_secret = os.getenv('GITLAB_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GITLAB_REDIRECT_URI', 'http://localhost:3000/oauth/gitlab/callback')
        self.api_base_url = 'https://gitlab.com/api/v4'
        
    def get_oauth_url(self, user_id=None, state=None):
        """Generate GitLab OAuth authorization URL"""
        if not self.client_id:
            return {
                'success': False,
                'error': 'GitLab client ID not configured',
                'service': 'gitlab'
            }
        
        if not state:
            state = f'gitlab_oauth_{datetime.now().timestamp()}'
            if user_id:
                state = f'{state}_{user_id}'
        
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'read_user read_repository api',
            'state': state
        }
        
        oauth_url = f'https://gitlab.com/oauth/authorize?{requests.compat.urlencode(params)}'
        
        return {
            'success': True,
            'oauth_url': oauth_url,
            'service': 'gitlab',
            'state': state,
            'client_id': self.client_id[:10] + '...' if self.client_id else None
        }
    
    def exchange_code_for_token(self, code, state=None):
        """Exchange authorization code for access token"""
        if not code:
            return {
                'success': False,
                'error': 'Authorization code required',
                'service': 'gitlab'
            }
        
        if not self.client_id or not self.client_secret:
            return {
                'success': False,
                'error': 'GitLab client ID or secret not configured',
                'service': 'gitlab'
            }
        
        try:
            token_url = 'https://gitlab.com/oauth/token'
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': self.redirect_uri
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
                        'service': 'gitlab',
                        'response': token_data
                    }
                
                # Get user information
                user_info = self.get_user_info(access_token)
                
                if user_info.get('success'):
                    return {
                        'success': True,
                        'service': 'gitlab',
                        'tokens': {
                            'access_token': access_token,
                            'refresh_token': refresh_token,
                            'token_type': token_data.get('token_type', 'Bearer'),
                            'scope': token_data.get('scope'),
                            'expires_in': token_data.get('expires_in', 7200)
                        },
                        'user_info': user_info.get('user_info'),
                        'workspace_info': {
                            'instance_url': 'https://gitlab.com',
                            'api_base_url': self.api_base_url,
                            'connected_at': datetime.now().isoformat()
                        },
                        'state': state
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to get user information',
                        'service': 'gitlab',
                        'details': user_info
                    }
            else:
                return {
                    'success': False,
                    'error': 'Failed to exchange authorization code',
                    'service': 'gitlab',
                    'status_code': response.status_code,
                    'response': response.text
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'GitLab OAuth token exchange error: {str(e)}',
                'service': 'gitlab'
            }
    
    def get_user_info(self, access_token):
        """Get GitLab user information using access token"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(f'{self.api_base_url}/user', headers=headers, timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    'success': True,
                    'user_info': {
                        'id': user_data.get('id'),
                        'username': user_data.get('username'),
                        'name': user_data.get('name'),
                        'email': user_data.get('email'),
                        'avatar_url': user_data.get('avatar_url'),
                        'web_url': user_data.get('web_url'),
                        'created_at': user_data.get('created_at'),
                        'last_sign_in_at': user_data.get('last_sign_in_at'),
                        'is_admin': user_data.get('is_admin', False)
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to get GitLab user info',
                    'status_code': response.status_code,
                    'response': response.text
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'GitLab user info error: {str(e)}'
            }
    
    def get_user_repositories(self, access_token, user_id=None):
        """Get user's GitLab repositories/projects"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(f'{self.api_base_url}/projects', headers=headers, timeout=10)
            
            if response.status_code == 200:
                projects = response.json()
                return {
                    'success': True,
                    'service': 'gitlab',
                    'repositories': [
                        {
                            'id': project.get('id'),
                            'name': project.get('name'),
                            'path': project.get('path'),
                            'path_with_namespace': project.get('path_with_namespace'),
                            'description': project.get('description'),
                            'web_url': project.get('web_url'),
                            'namespace': project.get('namespace'),
                            'visibility': project.get('visibility'),
                            'star_count': project.get('star_count'),
                            'forks_count': project.get('forks_count'),
                            'open_issues_count': project.get('open_issues_count'),
                            'last_activity_at': project.get('last_activity_at'),
                            'created_at': project.get('created_at'),
                            'updated_at': project.get('updated_at'),
                            'default_branch': project.get('default_branch'),
                            'owner': {
                                'id': project.get('owner', {}).get('id'),
                                'name': project.get('owner', {}).get('name'),
                                'username': project.get('owner', {}).get('username')
                            }
                        } for project in projects[:20]  # Limit to 20 for performance
                    ],
                    'total': len(projects),
                    'access_granted': True
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to get GitLab repositories',
                    'status_code': response.status_code,
                    'response': response.text
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'GitLab repositories error: {str(e)}'
            }
    
    def get_user_commits(self, access_token, project_id, branch='master'):
        """Get commits for a specific project"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(
                f'{self.api_base_url}/projects/{project_id}/repository/commits?ref_name={branch}&per_page=10',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                commits = response.json()
                return {
                    'success': True,
                    'service': 'gitlab',
                    'project_id': project_id,
                    'branch': branch,
                    'commits': [
                        {
                            'id': commit.get('id'),
                            'short_id': commit.get('short_id'),
                            'title': commit.get('title'),
                            'message': commit.get('message'),
                            'author_name': commit.get('author_name'),
                            'author_email': commit.get('author_email'),
                            'authored_date': commit.get('authored_date'),
                            'committed_date': commit.get('committed_date'),
                            'web_url': commit.get('web_url'),
                            'stats': commit.get('stats', {})
                        } for commit in commits
                    ],
                    'total': len(commits),
                    'access_granted': True
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to get GitLab commits',
                    'status_code': response.status_code,
                    'response': response.text
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'GitLab commits error: {str(e)}'
            }
    
    def health_check(self):
        """Check GitLab service health and configuration"""
        status = {
            'service': 'gitlab',
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'components': {}
        }
        
        # Check OAuth configuration
        if self.client_id and self.client_secret:
            status['components']['oauth'] = {'status': 'configured', 'message': 'OAuth credentials available'}
        else:
            status['components']['oauth'] = {'status': 'missing', 'message': 'OAuth credentials not found'}
            status['status'] = 'unhealthy'
        
        # Check API connectivity
        try:
            response = requests.get(f'{self.api_base_url}/version', timeout=5)
            if response.status_code == 200:
                version_info = response.json()
                status['components']['api'] = {
                    'status': 'connected',
                    'message': 'API connection successful',
                    'version': version_info.get('version'),
                    'revision': version_info.get('revision')
                }
            else:
                status['components']['api'] = {
                    'status': 'error',
                    'message': f'API returned status {response.status_code}'
                }
                status['status'] = 'unhealthy'
        except Exception as e:
            status['components']['api'] = {
                'status': 'error',
                'message': f'API connection failed: {str(e)}'
            }
            status['status'] = 'unhealthy'
        
        return status

# Flask route handlers for integration with existing system
def create_gitlab_oauth_routes(app):
    """Create GitLab OAuth routes for Flask app"""
    
    gitlab_handler = GitLabOAuthHandler()
    
    @app.route('/api/auth/gitlab/authorize', methods=['GET'])
    def gitlab_oauth_authorize():
        """Initiate GitLab OAuth flow"""
        user_id = request.args.get('user_id')
        state = request.args.get('state')
        
        result = gitlab_handler.get_oauth_url(user_id, state)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/auth/gitlab/callback', methods=['GET'])
    def gitlab_oauth_callback():
        """Handle GitLab OAuth callback"""
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if error:
            return jsonify({
                'success': False,
                'error': f'GitLab OAuth error: {error}',
                'service': 'gitlab'
            }), 400
        
        result = gitlab_handler.exchange_code_for_token(code, state)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/auth/gitlab/user-info', methods=['GET'])
    def gitlab_user_info():
        """Get GitLab user info"""
        access_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not access_token:
            return jsonify({'error': 'Access token required', 'success': False}), 401
        
        result = gitlab_handler.get_user_info(access_token)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/auth/gitlab/repositories', methods=['GET'])
    def gitlab_repositories():
        """Get GitLab repositories"""
        access_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user_id = request.args.get('user_id')
        
        if not access_token:
            return jsonify({'error': 'Access token required', 'success': False}), 401
        
        result = gitlab_handler.get_user_repositories(access_token, user_id)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/auth/gitlab/commits/<project_id>', methods=['GET'])
    def gitlab_commits(project_id):
        """Get GitLab commits for project"""
        access_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        branch = request.args.get('branch', 'master')
        
        if not access_token:
            return jsonify({'error': 'Access token required', 'success': False}), 401
        
        result = gitlab_handler.get_user_commits(access_token, project_id, branch)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/auth/gitlab/health', methods=['GET'])
    def gitlab_health():
        """GitLab service health check"""
        return jsonify(gitlab_handler.health_check())

# Export handler for use in existing system
gitlab_oauth_handler = GitLabOAuthHandler()