"""
GitLab Service Handler
Integrates with ATOM's existing service_handlers/ directory
"""

import os
import requests
import json
from datetime import datetime

class GitLabHandler:
    """Handle GitLab API calls and data processing"""
    
    def __init__(self):
        self.client_id = os.getenv('GITLAB_CLIENT_ID')
        self.client_secret = os.getenv('GITLAB_CLIENT_SECRET')
        self.api_base_url = 'https://gitlab.com/api/v4'
        
    def get_repository_data(self, access_token, repo_id=None):
        """Get detailed repository data"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            
            if repo_id:
                response = requests.get(f'{self.api_base_url}/projects/{repo_id}', headers=headers, timeout=10)
                if response.status_code == 200:
                    repo_data = response.json()
                    return {
                        'success': True,
                        'service': 'gitlab',
                        'repository': {
                            'id': repo_data.get('id'),
                            'name': repo_data.get('name'),
                            'path': repo_data.get('path'),
                            'path_with_namespace': repo_data.get('path_with_namespace'),
                            'description': repo_data.get('description'),
                            'web_url': repo_data.get('web_url'),
                            'namespace': repo_data.get('namespace'),
                            'visibility': repo_data.get('visibility'),
                            'star_count': repo_data.get('star_count'),
                            'forks_count': repo_data.get('forks_count'),
                            'open_issues_count': repo_data.get('open_issues_count'),
                            'last_activity_at': repo_data.get('last_activity_at'),
                            'created_at': repo_data.get('created_at'),
                            'updated_at': repo_data.get('updated_at'),
                            'default_branch': repo_data.get('default_branch'),
                            'owner': repo_data.get('owner'),
                            'real_data': True,
                            'connected_at': datetime.now().isoformat()
                        }
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Failed to get repository {repo_id}',
                        'status_code': response.status_code
                    }
            else:
                # Get all repositories
                response = requests.get(f'{self.api_base_url}/projects', headers=headers, timeout=10)
                if response.status_code == 200:
                    repos = response.json()
                    return {
                        'success': True,
                        'service': 'gitlab',
                        'repositories': [
                            {
                                'id': repo.get('id'),
                                'name': repo.get('name'),
                                'path': repo.get('path'),
                                'path_with_namespace': repo.get('path_with_namespace'),
                                'description': repo.get('description'),
                                'web_url': repo.get('web_url'),
                                'namespace': repo.get('namespace'),
                                'visibility': repo.get('visibility'),
                                'star_count': repo.get('star_count'),
                                'forks_count': repo.get('forks_count'),
                                'open_issues_count': repo.get('open_issues_count'),
                                'last_activity_at': repo.get('last_activity_at'),
                                'created_at': repo.get('created_at'),
                                'updated_at': repo.get('updated_at'),
                                'default_branch': repo.get('default_branch'),
                                'owner': repo.get('owner'),
                                'real_data': True
                            } for repo in repos[:20]  # Limit to 20 for performance
                        ],
                        'total': len(repos),
                        'real_data': True,
                        'connected_at': datetime.now().isoformat()
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to get GitLab repositories',
                        'status_code': response.status_code
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': f'GitLab repository error: {str(e)}',
                'service': 'gitlab'
            }
    
    def get_issue_data(self, access_token, repo_id=None, state='opened'):
        """Get issue data from repositories"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            
            if repo_id:
                response = requests.get(
                    f'{self.api_base_url}/projects/{repo_id}/issues?state={state}&per_page=20',
                    headers=headers,
                    timeout=10
                )
                if response.status_code == 200:
                    issues = response.json()
                    return {
                        'success': True,
                        'service': 'gitlab',
                        'repository_id': repo_id,
                        'issues': [
                            {
                                'id': issue.get('id'),
                                'iid': issue.get('iid'),
                                'title': issue.get('title'),
                                'description': issue.get('description'),
                                'state': issue.get('state'),
                                'author': issue.get('author'),
                                'assignees': issue.get('assignees', []),
                                'labels': issue.get('labels', []),
                                'milestone': issue.get('milestone'),
                                'created_at': issue.get('created_at'),
                                'updated_at': issue.get('updated_at'),
                                'closed_at': issue.get('closed_at'),
                                'web_url': issue.get('web_url'),
                                'real_data': True
                            } for issue in issues
                        ],
                        'total': len(issues),
                        'real_data': True
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Failed to get issues for repository {repo_id}',
                        'status_code': response.status_code
                    }
            else:
                # Get issues from all user repositories
                response = requests.get(f'{self.api_base_url}/issues?state={state}&per_page=20', headers=headers, timeout=10)
                if response.status_code == 200:
                    issues = response.json()
                    return {
                        'success': True,
                        'service': 'gitlab',
                        'issues': [
                            {
                                'id': issue.get('id'),
                                'iid': issue.get('iid'),
                                'title': issue.get('title'),
                                'description': issue.get('description'),
                                'state': issue.get('state'),
                                'author': issue.get('author'),
                                'assignees': issue.get('assignees', []),
                                'labels': issue.get('labels', []),
                                'milestone': issue.get('milestone'),
                                'created_at': issue.get('created_at'),
                                'updated_at': issue.get('updated_at'),
                                'closed_at': issue.get('closed_at'),
                                'web_url': issue.get('web_url'),
                                'project': issue.get('project'),
                                'real_data': True
                            } for issue in issues
                        ],
                        'total': len(issues),
                        'real_data': True
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to get GitLab issues',
                        'status_code': response.status_code
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': f'GitLab issue error: {str(e)}',
                'service': 'gitlab'
            }
    
    def get_merge_request_data(self, access_token, repo_id=None, state='opened'):
        """Get merge request data"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            
            if repo_id:
                response = requests.get(
                    f'{self.api_base_url}/projects/{repo_id}/merge_requests?state={state}&per_page=20',
                    headers=headers,
                    timeout=10
                )
                if response.status_code == 200:
                    mrs = response.json()
                    return {
                        'success': True,
                        'service': 'gitlab',
                        'repository_id': repo_id,
                        'merge_requests': [
                            {
                                'id': mr.get('id'),
                                'iid': mr.get('iid'),
                                'title': mr.get('title'),
                                'description': mr.get('description'),
                                'state': mr.get('state'),
                                'author': mr.get('author'),
                                'assignees': mr.get('assignees', []),
                                'labels': mr.get('labels', []),
                                'milestone': mr.get('milestone'),
                                'source_branch': mr.get('source_branch'),
                                'target_branch': mr.get('target_branch'),
                                'created_at': mr.get('created_at'),
                                'updated_at': mr.get('updated_at'),
                                'merged_at': mr.get('merged_at'),
                                'web_url': mr.get('web_url'),
                                'real_data': True
                            } for mr in mrs
                        ],
                        'total': len(mrs),
                        'real_data': True
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Failed to get merge requests for repository {repo_id}',
                        'status_code': response.status_code
                    }
            else:
                # Get merge requests from all user repositories
                response = requests.get(
                    f'{self.api_base_url}/merge_requests?state={state}&per_page=20',
                    headers=headers,
                    timeout=10
                )
                if response.status_code == 200:
                    mrs = response.json()
                    return {
                        'success': True,
                        'service': 'gitlab',
                        'merge_requests': [
                            {
                                'id': mr.get('id'),
                                'iid': mr.get('iid'),
                                'title': mr.get('title'),
                                'description': mr.get('description'),
                                'state': mr.get('state'),
                                'author': mr.get('author'),
                                'assignees': mr.get('assignees', []),
                                'labels': mr.get('labels', []),
                                'milestone': mr.get('milestone'),
                                'source_branch': mr.get('source_branch'),
                                'target_branch': mr.get('target_branch'),
                                'created_at': mr.get('created_at'),
                                'updated_at': mr.get('updated_at'),
                                'merged_at': mr.get('merged_at'),
                                'web_url': mr.get('web_url'),
                                'project': mr.get('project'),
                                'real_data': True
                            } for mr in mrs
                        ],
                        'total': len(mrs),
                        'real_data': True
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to get GitLab merge requests',
                        'status_code': response.status_code
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': f'GitLab merge request error: {str(e)}',
                'service': 'gitlab'
            }
    
    def get_pipeline_data(self, access_token, repo_id=None):
        """Get CI/CD pipeline data"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            
            if repo_id:
                response = requests.get(
                    f'{self.api_base_url}/projects/{repo_id}/pipelines?per_page=20',
                    headers=headers,
                    timeout=10
                )
                if response.status_code == 200:
                    pipelines = response.json()
                    return {
                        'success': True,
                        'service': 'gitlab',
                        'repository_id': repo_id,
                        'pipelines': [
                            {
                                'id': pipeline.get('id'),
                                'sha': pipeline.get('sha'),
                                'ref': pipeline.get('ref'),
                                'status': pipeline.get('status'),
                                'source': pipeline.get('source'),
                                'created_at': pipeline.get('created_at'),
                                'updated_at': pipeline.get('updated_at'),
                                'web_url': pipeline.get('web_url'),
                                'real_data': True
                            } for pipeline in pipelines
                        ],
                        'total': len(pipelines),
                        'real_data': True
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Failed to get pipelines for repository {repo_id}',
                        'status_code': response.status_code
                    }
            else:
                return {
                    'success': False,
                    'error': 'Repository ID required for GitLab pipelines',
                    'service': 'gitlab'
                }
                    
        except Exception as e:
            return {
                'success': False,
                'error': f'GitLab pipeline error: {str(e)}',
                'service': 'gitlab'
            }
    
    def get_user_activity(self, access_token, limit=20):
        """Get user's recent activity"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(
                f'{self.api_base_url}/events?per_page={limit}',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                events = response.json()
                return {
                    'success': True,
                    'service': 'gitlab',
                    'events': [
                        {
                            'id': event.get('id'),
                            'action_name': event.get('action_name'),
                            'target_type': event.get('target_type'),
                            'target_id': event.get('target_id'),
                            'target_title': event.get('target_title'),
                            'author': event.get('author'),
                            'project_id': event.get('project_id'),
                            'created_at': event.get('created_at'),
                            'note': event.get('note'),
                            'push_data': event.get('push_data'),
                            'real_data': True
                        } for event in events
                    ],
                    'total': len(events),
                    'real_data': True,
                    'connected_at': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to get GitLab user activity',
                    'status_code': response.status_code
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'GitLab user activity error: {str(e)}',
                'service': 'gitlab'
            }
    
    def health_check(self):
        """Check GitLab service health"""
        try:
            response = requests.get(f'{self.api_base_url}/version', timeout=5)
            
            if response.status_code == 200:
                version_info = response.json()
                return {
                    'service': 'gitlab',
                    'status': 'healthy',
                    'api_connected': True,
                    'version': version_info.get('version'),
                    'revision': version_info.get('revision'),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'service': 'gitlab',
                    'status': 'unhealthy',
                    'api_connected': False,
                    'error': f'API returned status {response.status_code}',
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            return {
                'service': 'gitlab',
                'status': 'unhealthy',
                'api_connected': False,
                'error': f'Health check failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }

# Export handler for use in existing system
gitlab_handler = GitLabHandler()