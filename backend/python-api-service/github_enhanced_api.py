"""
ATOM Enhanced GitHub API Handler
Complete GitHub integration with comprehensive API operations
"""

import os
import logging
import asyncio
import httpx
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, current_app
from loguru import logger

# Import GitHub service
try:
    from github_service_real import github_service
    GITHUB_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"GitHub service not available: {e}")
    GITHUB_SERVICE_AVAILABLE = False
    github_service = None

# Import database handler
try:
    from db_oauth_github import get_user_github_tokens
    GITHUB_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"GitHub database handler not available: {e}")
    GITHUB_DB_AVAILABLE = False

github_enhanced_bp = Blueprint("github_enhanced_bp", __name__)

# Configuration
GITHUB_API_BASE_URL = "https://api.github.com"
REQUEST_TIMEOUT = 30
RATE_LIMIT_HEADERS = ['X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Reset']

async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get GitHub tokens for user"""
    if not GITHUB_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            'access_token': os.getenv('GITHUB_ACCESS_TOKEN'),
            'token_type': 'bearer',
            'scope': 'repo,user:email',
            'expires_at': (datetime.utcnow() + timedelta(hours=8)).isoformat()
        }
    
    try:
        tokens = await get_user_github_tokens(user_id)
        return tokens
    except Exception as e:
        logger.error(f"Error getting GitHub tokens for user {user_id}: {e}")
        return None

def create_github_client(access_token: str) -> httpx.AsyncClient:
    """Create GitHub API client"""
    headers = {
        'Authorization': f'token {access_token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'ATOM-Platform/1.0'
    }
    
    return httpx.AsyncClient(
        base_url=GITHUB_API_BASE_URL,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )

def format_github_response(data: Any, endpoint: str) -> Dict[str, Any]:
    """Format GitHub API response"""
    return {
        'ok': True,
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'github_api'
    }

def format_error_response(error: Exception, endpoint: str) -> Dict[str, Any]:
    """Format error response"""
    return {
        'ok': False,
        'error': {
            'code': type(error).__name__,
            'message': str(error),
            'endpoint': endpoint
        },
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'github_api'
    }

@github_enhanced_bp.route('/api/integrations/github/repositories', methods=['POST'])
async def list_repositories():
    """List user repositories with filtering"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        organizations = data.get('organizations', [])
        include_forks = data.get('include_forks', False)
        include_archived = data.get('include_archived', False)
        limit = data.get('limit', 100)
        sort = data.get('sort', 'updated')
        order = data.get('order', 'desc')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'GitHub tokens not found'}
            }), 401
        
        # Create GitHub client
        async with create_github_client(tokens['access_token']) as client:
            repositories = []
            
            # Build query parameters
            params = {
                'type': 'owner',
                'sort': sort,
                'direction': order,
                'per_page': min(limit, 100)  # GitHub API limit
            }
            
            # Get repositories
            if organizations:
                # Get repositories from specific organizations
                for org in organizations:
                    url = f'/orgs/{org}/repos'
                    response = await client.get(url, params=params)
                    
                    if response.status_code == 200:
                        repos = response.json()
                        
                        # Filter repos
                        filtered_repos = [
                            {
                                'id': repo['id'],
                                'name': repo['name'],
                                'full_name': repo['full_name'],
                                'description': repo['description'],
                                'private': repo['private'],
                                'fork': repo['fork'],
                                'archived': repo['archived'],
                                'language': repo['language'],
                                'stars': repo['stargazers_count'],
                                'forks': repo['forks_count'],
                                'created_at': repo['created_at'],
                                'updated_at': repo['updated_at'],
                                'pushed_at': repo['pushed_at'],
                                'html_url': repo['html_url'],
                                'clone_url': repo['clone_url'],
                                'ssh_url': repo['ssh_url'],
                                'default_branch': repo['default_branch']
                            }
                            for repo in repos
                            if (include_forks or not repo['fork']) and
                               (include_archived or not repo['archived'])
                        ]
                        repositories.extend(filtered_repos)
            else:
                # Get all user repositories
                url = '/user/repos'
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    repos = response.json()
                    
                    # Filter repos
                    repositories = [
                        {
                            'id': repo['id'],
                            'name': repo['name'],
                            'full_name': repo['full_name'],
                            'description': repo['description'],
                            'private': repo['private'],
                            'fork': repo['fork'],
                            'archived': repo['archived'],
                            'language': repo['language'],
                            'stars': repo['stargazers_count'],
                            'forks': repo['forks_count'],
                            'created_at': repo['created_at'],
                            'updated_at': repo['updated_at'],
                            'pushed_at': repo['pushed_at'],
                            'html_url': repo['html_url'],
                            'clone_url': repo['clone_url'],
                            'ssh_url': repo['ssh_url'],
                            'default_branch': repo['default_branch']
                        }
                        for repo in repos
                        if (include_forks or not repo['fork']) and
                           (include_archived or not repo['archived'])
                    ]
            
            # Sort and limit
            if sort == 'stars':
                repositories.sort(key=lambda x: x['stars'], reverse=(order == 'desc'))
            elif sort == 'name':
                repositories.sort(key=lambda x: x['name'].lower(), reverse=(order == 'desc'))
            
            if limit:
                repositories = repositories[:limit]
            
            return jsonify(format_github_response({
                'repositories': repositories,
                'total_count': len(repositories),
                'filters_applied': {
                    'organizations': organizations,
                    'include_forks': include_forks,
                    'include_archived': include_archived
                }
            }, 'list_repositories'))
    
    except Exception as e:
        logger.error(f"Error listing repositories: {e}")
        return jsonify(format_error_response(e, 'list_repositories')), 500

@github_enhanced_bp.route('/api/integrations/github/organizations', methods=['POST'])
async def list_organizations():
    """List user organizations"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        limit = data.get('limit', 50)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'GitHub tokens not found'}
            }), 401
        
        # Create GitHub client
        async with create_github_client(tokens['access_token']) as client:
            url = '/user/orgs'
            params = {'per_page': min(limit, 100)}
            
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                orgs_data = response.json()
                
                organizations = [
                    {
                        'id': org['id'],
                        'login': org['login'],
                        'name': org.get('name', org['login']),
                        'description': org.get('description'),
                        'avatar_url': org['avatar_url'],
                        'url': org['url'],
                        'html_url': org['html_url'],
                        'public_repos': org['public_repos'],
                        'private_repos': org.get('private_repos', 0),
                        'total_repos': org['public_repos'] + org.get('private_repos', 0),
                        'created_at': org['created_at'],
                        'updated_at': org.get('updated_at'),
                        'location': org.get('location'),
                        'company': org.get('company'),
                        'blog': org.get('blog')
                    }
                    for org in orgs_data
                ]
                
                return jsonify(format_github_response({
                    'organizations': organizations,
                    'total_count': len(organizations)
                }, 'list_organizations'))
            else:
                return jsonify({
                    'ok': False,
                    'error': {'message': f'GitHub API error: {response.status_code}'}
                }), response.status_code
    
    except Exception as e:
        logger.error(f"Error listing organizations: {e}")
        return jsonify(format_error_response(e, 'list_organizations')), 500

@github_enhanced_bp.route('/api/integrations/github/issues', methods=['POST'])
async def list_issues():
    """List issues from selected repositories"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        repositories = data.get('repositories', [])
        filters = data.get('filters', {})
        limit = data.get('limit', 100)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'GitHub tokens not found'}
            }), 401
        
        # Create GitHub client
        async with create_github_client(tokens['access_token']) as client:
            all_issues = []
            
            # Build query parameters
            params = {
                'state': filters.get('state', 'all'),
                'sort': filters.get('sort', 'updated'),
                'direction': filters.get('direction', 'desc'),
                'per_page': min(limit // len(repositories) if repositories else limit, 50)
            }
            
            for repo_full_name in repositories:
                owner, repo = repo_full_name.split('/')
                url = f'/repos/{owner}/{repo}/issues'
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    issues = response.json()
                    
                    for issue in issues:
                        # Skip pull requests (they're handled separately)
                        if 'pull_request' in issue:
                            continue
                        
                        all_issues.append({
                            'id': issue['id'],
                            'number': issue['number'],
                            'title': issue['title'],
                            'body': issue.get('body'),
                            'state': issue['state'],
                            'locked': issue['locked'],
                            'assignees': [
                                {
                                    'login': assignee['login'],
                                    'avatar_url': assignee['avatar_url']
                                }
                                for assignee in issue.get('assignees', [])
                            ],
                            'labels': [
                                {
                                    'name': label['name'],
                                    'color': label['color']
                                }
                                for label in issue.get('labels', [])
                            ],
                            'milestone': issue.get('milestone', {}).get('title') if issue.get('milestone') else None,
                            'comments': issue['comments'],
                            'created_at': issue['created_at'],
                            'updated_at': issue['updated_at'],
                            'closed_at': issue.get('closed_at'),
                            'author': {
                                'login': issue['user']['login'],
                                'avatar_url': issue['user']['avatar_url']
                            },
                            'repository': {
                                'name': repo,
                                'full_name': repo_full_name
                            },
                            'html_url': issue['html_url']
                        })
            
            # Sort and limit
            all_issues.sort(key=lambda x: x['updated_at'], reverse=True)
            if limit:
                all_issues = all_issues[:limit]
            
            return jsonify(format_github_response({
                'issues': all_issues,
                'total_count': len(all_issues),
                'filters_applied': filters
            }, 'list_issues'))
    
    except Exception as e:
        logger.error(f"Error listing issues: {e}")
        return jsonify(format_error_response(e, 'list_issues')), 500

@github_enhanced_bp.route('/api/integrations/github/pull_requests', methods=['POST'])
async def list_pull_requests():
    """List pull requests from selected repositories"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        repositories = data.get('repositories', [])
        filters = data.get('filters', {})
        limit = data.get('limit', 100)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'GitHub tokens not found'}
            }), 401
        
        # Create GitHub client
        async with create_github_client(tokens['access_token']) as client:
            all_prs = []
            
            # Build query parameters
            params = {
                'state': filters.get('state', 'all'),
                'sort': filters.get('sort', 'updated'),
                'direction': filters.get('direction', 'desc'),
                'per_page': min(limit // len(repositories) if repositories else limit, 50)
            }
            
            for repo_full_name in repositories:
                owner, repo = repo_full_name.split('/')
                url = f'/repos/{owner}/{repo}/pulls'
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    prs = response.json()
                    
                    for pr in prs:
                        all_prs.append({
                            'id': pr['id'],
                            'number': pr['number'],
                            'title': pr['title'],
                            'body': pr.get('body'),
                            'state': pr['state'],
                            'locked': pr['locked'],
                            'draft': pr['draft'],
                            'merged': pr['merged'] if pr['state'] == 'closed' else False,
                            'mergeable': pr.get('mergeable'),
                            'additions': pr.get('additions', 0),
                            'deletions': pr.get('deletions', 0),
                            'changed_files': pr.get('changed_files', 0),
                            'comments': pr['comments'],
                            'review_comments': pr.get('review_comments', 0),
                            'commits': pr.get('commits', 0),
                            'assignees': [
                                {
                                    'login': assignee['login'],
                                    'avatar_url': assignee['avatar_url']
                                }
                                for assignee in pr.get('assignees', [])
                            ],
                            'requested_reviewers': [
                                {
                                    'login': reviewer['login'],
                                    'avatar_url': reviewer['avatar_url']
                                }
                                for reviewer in pr.get('requested_reviewers', [])
                            ],
                            'labels': [
                                {
                                    'name': label['name'],
                                    'color': label['color']
                                }
                                for label in pr.get('labels', [])
                            ],
                            'milestone': pr.get('milestone', {}).get('title') if pr.get('milestone') else None,
                            'head': {
                                'ref': pr['head']['ref'],
                                'sha': pr['head']['sha'],
                                'label': pr['head']['label'],
                                'repo': pr['head']['repo']['full_name'] if pr['head'].get('repo') else None
                            },
                            'base': {
                                'ref': pr['base']['ref'],
                                'sha': pr['base']['sha'],
                                'label': pr['base']['label'],
                                'repo': pr['base']['repo']['full_name']
                            },
                            'created_at': pr['created_at'],
                            'updated_at': pr['updated_at'],
                            'closed_at': pr.get('closed_at'),
                            'merged_at': pr.get('merged_at'),
                            'author': {
                                'login': pr['user']['login'],
                                'avatar_url': pr['user']['avatar_url']
                            },
                            'repository': {
                                'name': repo,
                                'full_name': repo_full_name
                            },
                            'html_url': pr['html_url']
                        })
            
            # Sort and limit
            all_prs.sort(key=lambda x: x['updated_at'], reverse=True)
            if limit:
                all_prs = all_prs[:limit]
            
            return jsonify(format_github_response({
                'pull_requests': all_prs,
                'total_count': len(all_prs),
                'filters_applied': filters
            }, 'list_pull_requests'))
    
    except Exception as e:
        logger.error(f"Error listing pull requests: {e}")
        return jsonify(format_error_response(e, 'list_pull_requests')), 500

@github_enhanced_bp.route('/api/integrations/github/search', methods=['POST'])
async def search_github():
    """Search across GitHub (repositories, issues, users)"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        search_type = data.get('type', 'repositories')
        limit = data.get('limit', 50)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if not query:
            return jsonify({
                'ok': False,
                'error': {'message': 'query is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'GitHub tokens not found'}
            }), 401
        
        # Create GitHub client
        async with create_github_client(tokens['access_token']) as client:
            # Build search query based on type
            if search_type == 'repositories':
                search_query = query + ' in:name,description'
                endpoint = '/search/repositories'
            elif search_type == 'issues':
                search_query = query + ' in:title,body'
                endpoint = '/search/issues'
            elif search_type == 'users':
                search_query = query + ' in:login,name'
                endpoint = '/search/users'
            elif search_type == 'code':
                search_query = query
                endpoint = '/search/code'
            else:
                # Global search (repositories by default)
                search_query = query + ' in:name,description'
                endpoint = '/search/repositories'
            
            params = {
                'q': search_query,
                'per_page': min(limit, 100),
                'sort': data.get('sort', 'updated'),
                'order': data.get('order', 'desc')
            }
            
            response = await client.get(endpoint, params=params)
            
            if response.status_code == 200:
                search_results = response.json()
                
                # Format results based on search type
                if 'items' in search_results:
                    if search_type == 'repositories':
                        results = [
                            {
                                'id': item['id'],
                                'name': item['name'],
                                'full_name': item['full_name'],
                                'description': item['description'],
                                'private': item['private'],
                                'language': item['language'],
                                'stars': item['stargazers_count'],
                                'forks': item['forks_count'],
                                'html_url': item['html_url'],
                                'score': item['score']
                            }
                            for item in search_results['items']
                        ]
                    elif search_type == 'issues':
                        results = [
                            {
                                'id': item['id'],
                                'number': item['number'],
                                'title': item['title'],
                                'state': item['state'],
                                'comments': item['comments'],
                                'created_at': item['created_at'],
                                'updated_at': item['updated_at'],
                                'html_url': item['html_url'],
                                'repository': item['repository_url'].split('/')[-2:][0],
                                'score': item['score']
                            }
                            for item in search_results['items']
                        ]
                    elif search_type == 'users':
                        results = [
                            {
                                'id': item['id'],
                                'login': item['login'],
                                'name': item.get('name'),
                                'avatar_url': item['avatar_url'],
                                'type': item['type'],
                                'public_repos': item['public_repos'],
                                'followers': item['followers'],
                                'html_url': item['html_url'],
                                'score': item['score']
                            }
                            for item in search_results['items']
                        ]
                    else:
                        results = search_results['items']
                else:
                    results = []
                
                return jsonify(format_github_response({
                    'results': results,
                    'total_count': search_results['total_count'],
                    'incomplete_results': search_results.get('incomplete_results', False),
                    'query': query,
                    'search_type': search_type
                }, 'search_github'))
            else:
                return jsonify({
                    'ok': False,
                    'error': {'message': f'GitHub API error: {response.status_code}'}
                }), response.status_code
    
    except Exception as e:
        logger.error(f"Error searching GitHub: {e}")
        return jsonify(format_error_response(e, 'search_github')), 500

@github_enhanced_bp.route('/api/integrations/github/user/profile', methods=['POST'])
async def get_user_profile():
    """Get authenticated user profile"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'GitHub tokens not found'}
            }), 401
        
        # Create GitHub client
        async with create_github_client(tokens['access_token']) as client:
            response = await client.get('/user')
            
            if response.status_code == 200:
                user_data = response.json()
                
                profile = {
                    'id': user_data['id'],
                    'login': user_data['login'],
                    'name': user_data.get('name'),
                    'email': user_data.get('email'),
                    'bio': user_data.get('bio'),
                    'location': user_data.get('location'),
                    'company': user_data.get('company'),
                    'blog': user_data.get('blog'),
                    'avatar_url': user_data['avatar_url'],
                    'html_url': user_data['html_url'],
                    'followers': user_data['followers'],
                    'following': user_data['following'],
                    'public_repos': user_data['public_repos'],
                    'private_repos': user_data.get('total_private_repos', 0),
                    'total_gists': user_data['total_private_gists'],
                    'created_at': user_data['created_at'],
                    'updated_at': user_data.get('updated_at'),
                    'two_factor_authentication': user_data.get('two_factor_authentication', False),
                    'site_admin': user_data.get('site_admin', False)
                }
                
                return jsonify(format_github_response(profile, 'get_user_profile'))
            else:
                return jsonify({
                    'ok': False,
                    'error': {'message': f'GitHub API error: {response.status_code}'}
                }), response.status_code
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify(format_error_response(e, 'get_user_profile')), 500

@github_enhanced_bp.route('/api/integrations/github/commits', methods=['POST'])
async def list_commits():
    """List commits from selected repositories"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        repositories = data.get('repositories', [])
        branch = data.get('branch', 'main')
        since = data.get('since')
        until = data.get('until')
        limit = data.get('limit', 100)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'GitHub tokens not found'}
            }), 401
        
        # Create GitHub client
        async with create_github_client(tokens['access_token']) as client:
            all_commits = []
            
            # Build query parameters
            params = {
                'sha': branch,
                'per_page': min(limit // len(repositories) if repositories else limit, 100)
            }
            
            if since:
                params['since'] = since
            if until:
                params['until'] = until
            
            for repo_full_name in repositories:
                owner, repo = repo_full_name.split('/')
                url = f'/repos/{owner}/{repo}/commits'
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    commits = response.json()
                    
                    for commit in commits:
                        all_commits.append({
                            'sha': commit['sha'],
                            'message': commit['commit']['message'],
                            'author': {
                                'name': commit['commit']['author']['name'],
                                'email': commit['commit']['author']['email'],
                                'login': commit['author']['login'] if commit.get('author') else None,
                                'avatar_url': commit['author']['avatar_url'] if commit.get('author') else None
                            },
                            'committer': {
                                'name': commit['commit']['committer']['name'],
                                'email': commit['commit']['committer']['email'],
                                'login': commit['committer']['login'] if commit.get('committer') else None,
                                'avatar_url': commit['committer']['avatar_url'] if commit.get('committer') else None
                            },
                            'date': commit['commit']['author']['date'],
                            'html_url': commit['html_url'],
                            'repository': {
                                'name': repo,
                                'full_name': repo_full_name
                            },
                            'parents': [parent['sha'] for parent in commit.get('parents', [])],
                            'stats': commit.get('stats', {})
                        })
            
            # Sort and limit
            all_commits.sort(key=lambda x: x['date'], reverse=True)
            if limit:
                all_commits = all_commits[:limit]
            
            return jsonify(format_github_response({
                'commits': all_commits,
                'total_count': len(all_commits),
                'filters_applied': {
                    'branch': branch,
                    'since': since,
                    'until': until
                }
            }, 'list_commits'))
    
    except Exception as e:
        logger.error(f"Error listing commits: {e}")
        return jsonify(format_error_response(e, 'list_commits')), 500

# Health check endpoint
@github_enhanced_bp.route('/api/integrations/github/health', methods=['GET'])
async def health_check():
    """GitHub service health check"""
    try:
        if not GITHUB_SERVICE_AVAILABLE:
            return jsonify({
                'status': 'unhealthy',
                'error': 'GitHub service not available',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Test GitHub API connectivity
        async with httpx.AsyncClient() as client:
            response = await client.get(f'{GITHUB_API_BASE_URL}/', timeout=5)
            
            if response.status_code == 200:
                return jsonify({
                    'status': 'healthy',
                    'message': 'GitHub API is accessible',
                    'service_available': GITHUB_SERVICE_AVAILABLE,
                    'database_available': GITHUB_DB_AVAILABLE,
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                return jsonify({
                    'status': 'degraded',
                    'error': f'GitHub API returned {response.status_code}',
                    'timestamp': datetime.utcnow().isoformat()
                })
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

# Error handlers
@github_enhanced_bp.errorhandler(404)
async def not_found(error):
    return jsonify({
        'ok': False,
        'error': {
            'code': 'NOT_FOUND',
            'message': 'Endpoint not found'
        }
    }), 404

@github_enhanced_bp.errorhandler(500)
async def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'ok': False,
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'Internal server error'
        }
    }), 500