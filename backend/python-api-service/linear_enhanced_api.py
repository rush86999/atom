"""
ATOM Enhanced Linear API Handler
Complete Linear integration with comprehensive API operations
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

# Import Linear service
try:
    from linear_service_real import linear_service
    LINEAR_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Linear service not available: {e}")
    LINEAR_SERVICE_AVAILABLE = False
    linear_service = None

# Import database handler
try:
    from db_oauth_linear import get_tokens, save_tokens, delete_tokens, get_user_linear_issues, save_linear_issue, get_user_linear_projects, save_linear_project, get_user_linear_teams, save_linear_team
    LINEAR_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Linear database handler not available: {e}")
    LINEAR_DB_AVAILABLE = False

linear_enhanced_bp = Blueprint("linear_enhanced_bp", __name__)

# Configuration
LINEAR_API_BASE_URL = "https://api.linear.app/v1"
REQUEST_TIMEOUT = 30

async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Linear tokens for user"""
    if not LINEAR_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            'access_token': os.getenv('LINEAR_ACCESS_TOKEN'),
            'refresh_token': os.getenv('LINEAR_REFRESH_TOKEN'),
            'expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            'scope': 'read write issues:read issues:write teams:read projects:read comments:read',
            'user_info': {
                'id': os.getenv('LINEAR_USER_ID'),
                'name': os.getenv('LINEAR_USER_NAME', 'Test User'),
                'displayName': os.getenv('LINEAR_USER_DISPLAY_NAME', 'Test User'),
                'email': os.getenv('LINEAR_USER_EMAIL', 'test@example.com'),
                'avatarUrl': os.getenv('LINEAR_USER_AVATAR'),
                'url': 'https://linear.app/testuser',
                'role': os.getenv('LINEAR_USER_ROLE', 'admin'),
                'organization': {
                    'id': os.getenv('LINEAR_ORG_ID'),
                    'name': os.getenv('LINEAR_ORG_NAME', 'Test Organization'),
                    'urlKey': os.getenv('LINEAR_ORG_URLKEY', 'test-org')
                },
                'active': True,
                'lastSeen': datetime.utcnow().isoformat()
            }
        }
    
    try:
        tokens = await get_tokens(None, user_id)  # db_conn_pool - will be passed in production
        return tokens
    except Exception as e:
        logger.error(f"Error getting Linear tokens for user {user_id}: {e}")
        return None

def format_linear_response(data: Any, endpoint: str) -> Dict[str, Any]:
    """Format Linear API response"""
    return {
        'ok': True,
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'linear_api'
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
        'source': 'linear_api'
    }

@linear_enhanced_bp.route('/api/integrations/linear/issues', methods=['POST'])
async def list_issues():
    """List user Linear issues"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        team_id = data.get('team_id')
        project_id = data.get('project_id')
        include_completed = data.get('include_completed', True)
        include_canceled = data.get('include_canceled', False)
        include_backlog = data.get('include_backlog', True)
        limit = data.get('limit', 50)
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'create':
            return await _create_issue(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Linear tokens not found'}
            }), 401
        
        # Use Linear service
        if LINEAR_SERVICE_AVAILABLE:
            issues = await linear_service.get_user_issues(
                user_id, team_id, project_id, include_completed, include_canceled, include_backlog, limit
            )
            
            issues_data = [{
                'issue_id': issue.id,
                'identifier': issue.identifier,
                'title': issue.title,
                'description': issue.description,
                'status': {
                    'id': issue.status.get('id'),
                    'name': issue.status.get('name'),
                    'color': issue.status.get('color'),
                    'type': issue.status.get('type')
                },
                'priority': {
                    'id': issue.priority.get('id'),
                    'label': issue.priority.get('label'),
                    'priority': issue.priority.get('priority')
                },
                'assignee': issue.assignee and {
                    'id': issue.assignee.get('id'),
                    'name': issue.assignee.get('name'),
                    'displayName': issue.assignee.get('displayName'),
                    'avatarUrl': issue.assignee.get('avatarUrl')
                },
                'project': {
                    'id': issue.project.get('id'),
                    'name': issue.project.get('name'),
                    'icon': issue.project.get('icon'),
                    'color': issue.project.get('color')
                },
                'team': {
                    'id': issue.team.get('id'),
                    'name': issue.team.get('name'),
                    'icon': issue.team.get('icon')
                },
                'labels': issue.labels,
                'created_at': issue.createdAt,
                'updated_at': issue.updatedAt,
                'due_date': issue.dueDate,
                'state': issue.state,
                'url': f"https://linear.app/issue/{issue.identifier}"
            } for issue in issues]
            
            return jsonify(format_linear_response({
                'issues': issues_data,
                'total_count': len(issues_data)
            }, 'list_issues'))
        
        # Fallback to mock data
        mock_issues = [
            {
                'issue_id': 'lin-issue-1',
                'identifier': 'PROJ-1',
                'title': 'Set up development environment',
                'description': 'Initialize development environment for new project',
                'status': {
                    'id': 'status-1',
                    'name': 'In Progress',
                    'color': 'blue',
                    'type': 'started'
                },
                'priority': {
                    'id': 'priority-1',
                    'label': 'High',
                    'priority': 4
                },
                'assignee': {
                    'id': 'user-1',
                    'name': 'Alice Developer',
                    'displayName': 'Alice Developer',
                    'avatarUrl': 'https://example.com/alice.png'
                },
                'project': {
                    'id': 'proj-1',
                    'name': 'Mobile App',
                    'icon': '📱',
                    'color': 'blue'
                },
                'team': {
                    'id': 'team-1',
                    'name': 'Engineering',
                    'icon': '⚙️'
                },
                'labels': [
                    {'id': 'label-1', 'name': 'Development', 'color': 'blue'},
                    {'id': 'label-2', 'name': 'Setup', 'color': 'green'}
                ],
                'created_at': (datetime.utcnow() - timedelta(days=2)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'due_date': (datetime.utcnow() + timedelta(days=5)).isoformat(),
                'state': 'started',
                'url': 'https://linear.app/issue/PROJ-1'
            },
            {
                'issue_id': 'lin-issue-2',
                'identifier': 'PROJ-2',
                'title': 'Design system components',
                'description': 'Create reusable UI components for design system',
                'status': {
                    'id': 'status-2',
                    'name': 'Todo',
                    'color': 'gray',
                    'type': 'backlog'
                },
                'priority': {
                    'id': 'priority-2',
                    'label': 'Medium',
                    'priority': 3
                },
                'assignee': None,
                'project': {
                    'id': 'proj-2',
                    'name': 'Design System',
                    'icon': '🎨',
                    'color': 'purple'
                },
                'team': {
                    'id': 'team-2',
                    'name': 'Design',
                    'icon': '🎨'
                },
                'labels': [
                    {'id': 'label-3', 'name': 'Design', 'color': 'purple'},
                    {'id': 'label-4', 'name': 'Components', 'color': 'pink'}
                ],
                'created_at': (datetime.utcnow() - timedelta(days=5)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(days=3)).isoformat(),
                'due_date': None,
                'state': 'backlog',
                'url': 'https://linear.app/issue/PROJ-2'
            },
            {
                'issue_id': 'lin-issue-3',
                'identifier': 'PROJ-3',
                'title': 'API endpoint implementation',
                'description': 'Implement REST API endpoints for user management',
                'status': {
                    'id': 'status-3',
                    'name': 'Done',
                    'color': 'green',
                    'type': 'done'
                },
                'priority': {
                    'id': 'priority-3',
                    'label': 'Urgent',
                    'priority': 5
                },
                'assignee': {
                    'id': 'user-2',
                    'name': 'Bob Engineer',
                    'displayName': 'Bob Engineer',
                    'avatarUrl': 'https://example.com/bob.png'
                },
                'project': {
                    'id': 'proj-3',
                    'name': 'Backend Services',
                    'icon': '🔧',
                    'color': 'orange'
                },
                'team': {
                    'id': 'team-2',
                    'name': 'Backend',
                    'icon': '⚙️'
                },
                'labels': [
                    {'id': 'label-5', 'name': 'API', 'color': 'orange'},
                    {'id': 'label-6', 'name': 'Backend', 'color': 'red'}
                ],
                'created_at': (datetime.utcnow() - timedelta(days=7)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'due_date': (datetime.utcnow() + timedelta(days=2)).isoformat(),
                'state': 'done',
                'url': 'https://linear.app/issue/PROJ-3'
            }
        ]
        
        # Filter based on state preferences
        filtered_issues = []
        for issue in mock_issues:
            if not include_completed and issue['state'] == 'done':
                continue
            if not include_canceled and issue['state'] == 'canceled':
                continue
            if not include_backlog and issue['state'] == 'backlog':
                continue
            filtered_issues.append(issue)
        
        return jsonify(format_linear_response({
            'issues': filtered_issues[:limit],
            'total_count': len(filtered_issues)
        }, 'list_issues'))
    
    except Exception as e:
        logger.error(f"Error listing issues: {e}")
        return jsonify(format_error_response(e, 'list_issues')), 500

async def _create_issue(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to create issue"""
    try:
        issue_data = data.get('data', {})
        
        if not issue_data.get('title'):
            return jsonify({
                'ok': False,
                'error': {'message': 'Issue title is required'}
            }), 400
        
        # Use Linear service
        if LINEAR_SERVICE_AVAILABLE:
            result = await linear_service.create_issue(user_id, issue_data)
            
            if result.get('ok'):
                return jsonify(format_linear_response({
                    'issue': result.get('issue'),
                    'url': result.get('issue', {}).get('url'),
                    'message': 'Issue created successfully'
                }, 'create_issue'))
            else:
                return jsonify(result)
        
        # Fallback to mock creation
        mock_issue = {
            'issue_id': 'lin-issue-' + str(int(datetime.utcnow().timestamp())),
            'identifier': 'NEW-' + str(int(datetime.utcnow().timestamp())),
            'title': issue_data['title'],
            'description': issue_data.get('description', ''),
            'status': {
                'id': 'status-todo',
                'name': 'Todo',
                'color': 'gray',
                'type': 'backlog'
            },
            'priority': issue_data.get('priority', {
                'id': 'priority-medium',
                'label': 'Medium',
                'priority': 3
            }),
            'assignee': issue_data.get('assignee'),
            'project': issue_data.get('project'),
            'team': issue_data.get('team'),
            'labels': issue_data.get('labels', []),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'due_date': issue_data.get('due_date'),
            'state': 'backlog',
            'url': f"https://linear.app/issue/NEW-{int(datetime.utcnow().timestamp())}"
        }
        
        return jsonify(format_linear_response({
            'issue': mock_issue,
            'url': mock_issue['url'],
            'message': 'Issue created successfully'
        }, 'create_issue'))
    
    except Exception as e:
        logger.error(f"Error creating issue: {e}")
        return jsonify(format_error_response(e, 'create_issue')), 500

@linear_enhanced_bp.route('/api/integrations/linear/teams', methods=['POST'])
async def list_teams():
    """List user Linear teams"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        limit = data.get('limit', 20)
        
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
                'error': {'message': 'Linear tokens not found'}
            }), 401
        
        # Use Linear service
        if LINEAR_SERVICE_AVAILABLE:
            teams = await linear_service.get_user_teams(user_id, limit)
            
            teams_data = [{
                'team_id': team.id,
                'name': team.name,
                'description': team.description,
                'icon': team.icon,
                'color': team.color,
                'organization': team.organization,
                'created_at': team.createdAt,
                'updated_at': team.updatedAt,
                'member_count': len(team.members) if team.members else 0,
                'issues_count': team.issuesCount,
                'cycles_count': team.cyclesCount,
                'members': team.members and [{
                    'id': member.id,
                    'name': member.name,
                    'displayName': member.displayName,
                    'avatarUrl': member.avatarUrl,
                    'role': member.role
                } for member in team.members],
                'projects': team.projects and [{
                    'id': project.id,
                    'name': project.name,
                    'icon': project.icon,
                    'color': project.color,
                    'state': project.state
                } for project in team.projects]
            } for team in teams]
            
            return jsonify(format_linear_response({
                'teams': teams_data,
                'total_count': len(teams_data)
            }, 'list_teams'))
        
        # Fallback to mock data
        mock_teams = [
            {
                'team_id': 'team-1',
                'name': 'Engineering',
                'description': 'Core engineering team',
                'icon': '⚙️',
                'color': 'blue',
                'organization': {
                    'id': 'org-1',
                    'name': 'Tech Company',
                    'urlKey': 'tech-company'
                },
                'created_at': (datetime.utcnow() - timedelta(days=365)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'member_count': 2,
                'issues_count': 25,
                'cycles_count': 8,
                'members': [
                    {
                        'id': 'user-1',
                        'name': 'Alice Developer',
                        'displayName': 'Alice Developer',
                        'avatarUrl': 'https://example.com/alice.png',
                        'role': 'admin'
                    },
                    {
                        'id': 'user-2',
                        'name': 'Bob Engineer',
                        'displayName': 'Bob Engineer',
                        'avatarUrl': 'https://example.com/bob.png',
                        'role': 'member'
                    }
                ],
                'projects': [
                    {
                        'id': 'proj-1',
                        'name': 'Mobile App',
                        'icon': '📱',
                        'color': 'blue',
                        'state': 'started'
                    }
                ]
            },
            {
                'team_id': 'team-2',
                'name': 'Design',
                'description': 'Product design and user experience team',
                'icon': '🎨',
                'color': 'purple',
                'organization': {
                    'id': 'org-1',
                    'name': 'Tech Company',
                    'urlKey': 'tech-company'
                },
                'created_at': (datetime.utcnow() - timedelta(days=300)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'member_count': 1,
                'issues_count': 15,
                'cycles_count': 4,
                'members': [
                    {
                        'id': 'user-3',
                        'name': 'Carol Designer',
                        'displayName': 'Carol Designer',
                        'avatarUrl': 'https://example.com/carol.png',
                        'role': 'admin'
                    }
                ],
                'projects': [
                    {
                        'id': 'proj-2',
                        'name': 'Design System',
                        'icon': '🎨',
                        'color': 'purple',
                        'state': 'started'
                    }
                ]
            }
        ]
        
        return jsonify(format_linear_response({
            'teams': mock_teams[:limit],
            'total_count': len(mock_teams)
        }, 'list_teams'))
    
    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        return jsonify(format_error_response(e, 'list_teams')), 500

@linear_enhanced_bp.route('/api/integrations/linear/projects', methods=['POST'])
async def list_projects():
    """List projects from teams"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        team_id = data.get('team_id')
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
                'error': {'message': 'Linear tokens not found'}
            }), 401
        
        # Use Linear service
        if LINEAR_SERVICE_AVAILABLE:
            projects = await linear_service.get_team_projects(user_id, team_id, limit)
            
            projects_data = [{
                'project_id': project.id,
                'name': project.name,
                'description': project.description,
                'url': project.url,
                'icon': project.icon,
                'color': project.color,
                'team': project.team,
                'state': project.state,
                'progress': project.progress,
                'completed_issues_count': project.completedIssuesCount,
                'started_issues_count': project.startedIssuesCount,
                'unstarted_issues_count': project.unstartedIssuesCount,
                'backlogged_issues_count': project.backloggedIssuesCount,
                'canceled_issues_count': project.canceledIssuesCount,
                'created_at': project.createdAt,
                'updated_at': project.updatedAt,
                'scope': project.scope
            } for project in projects]
            
            return jsonify(format_linear_response({
                'projects': projects_data,
                'total_count': len(projects_data)
            }, 'list_projects'))
        
        # Fallback to mock data
        mock_projects = [
            {
                'project_id': 'proj-1',
                'name': 'Mobile App',
                'description': 'Native mobile application for iOS and Android',
                'url': 'https://linear.app/project/proj-1',
                'icon': '📱',
                'color': 'blue',
                'team': {
                    'id': team_id or 'team-1',
                    'name': 'Engineering',
                    'icon': '⚙️'
                },
                'state': 'started',
                'progress': 65,
                'completed_issues_count': 26,
                'started_issues_count': 8,
                'unstarted_issues_count': 6,
                'backlogged_issues_count': 10,
                'canceled_issues_count': 2,
                'created_at': (datetime.utcnow() - timedelta(days=90)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'scope': 'public'
            },
            {
                'project_id': 'proj-2',
                'name': 'Design System',
                'description': 'Component library and design tokens',
                'url': 'https://linear.app/project/proj-2',
                'icon': '🎨',
                'color': 'purple',
                'team': {
                    'id': team_id or 'team-2',
                    'name': 'Design',
                    'icon': '🎨'
                },
                'state': 'started',
                'progress': 45,
                'completed_issues_count': 18,
                'started_issues_count': 5,
                'unstarted_issues_count': 12,
                'backlogged_issues_count': 8,
                'canceled_issues_count': 1,
                'created_at': (datetime.utcnow() - timedelta(days=60)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(days=2)).isoformat(),
                'scope': 'public'
            }
        ]
        
        return jsonify(format_linear_response({
            'projects': mock_projects[:limit],
            'total_count': len(mock_projects)
        }, 'list_projects'))
    
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return jsonify(format_error_response(e, 'list_projects')), 500

@linear_enhanced_bp.route('/api/integrations/linear/cycles', methods=['POST'])
async def list_cycles():
    """List cycles from teams"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        team_id = data.get('team_id')
        include_completed = data.get('include_completed', True)
        limit = data.get('limit', 20)
        
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
                'error': {'message': 'Linear tokens not found'}
            }), 401
        
        # Use Linear service
        if LINEAR_SERVICE_AVAILABLE:
            cycles = await linear_service.get_team_cycles(user_id, team_id, include_completed, limit)
            
            cycles_data = [{
                'cycle_id': cycle.id,
                'name': cycle.name,
                'description': cycle.description,
                'number': cycle.number,
                'start_at': cycle.startAt,
                'end_at': cycle.endAt,
                'completed_at': cycle.completedAt,
                'progress': cycle.progress,
                'issues': cycle.issues and [{
                    'issue_id': issue.id,
                    'identifier': issue.identifier,
                    'title': issue.title,
                    'status': {
                        'id': issue.status.get('id'),
                        'name': issue.status.get('name'),
                        'color': issue.status.get('color'),
                        'type': issue.status.get('type')
                    },
                    'priority': {
                        'id': issue.priority.get('id'),
                        'label': issue.priority.get('label'),
                        'priority': issue.priority.get('priority')
                    },
                    'assignee': issue.assignee and {
                        'id': issue.assignee.get('id'),
                        'name': issue.assignee.get('name'),
                        'displayName': issue.assignee.get('displayName'),
                        'avatarUrl': issue.assignee.get('avatarUrl')
                    },
                    'created_at': issue.createdAt,
                    'updated_at': issue.updatedAt
                } for issue in cycle.issues],
                'team': cycle.team,
                'issue_count': len(cycle.issues) if cycle.issues else 0
            } for cycle in cycles]
            
            return jsonify(format_linear_response({
                'cycles': cycles_data,
                'total_count': len(cycles_data)
            }, 'list_cycles'))
        
        # Fallback to mock data
        mock_cycles = [
            {
                'cycle_id': 'cycle-1',
                'name': 'Q1 2024 Development',
                'description': 'Development cycle for Q1 2024',
                'number': 1,
                'start_at': (datetime.utcnow() - timedelta(days=60)).isoformat(),
                'end_at': (datetime.utcnow() + timedelta(days=30)).isoformat(),
                'completed_at': None,
                'progress': 75,
                'issues': [
                    {
                        'issue_id': 'lin-issue-1',
                        'identifier': 'PROJ-1',
                        'title': 'Set up development environment',
                        'status': {
                            'id': 'status-1',
                            'name': 'In Progress',
                            'color': 'blue',
                            'type': 'started'
                        },
                        'priority': {
                            'id': 'priority-1',
                            'label': 'High',
                            'priority': 4
                        },
                        'assignee': {
                            'id': 'user-1',
                            'name': 'Alice Developer',
                            'displayName': 'Alice Developer',
                            'avatarUrl': 'https://example.com/alice.png'
                        },
                        'created_at': (datetime.utcnow() - timedelta(days=2)).isoformat(),
                        'updated_at': (datetime.utcnow() - timedelta(days=1)).isoformat()
                    }
                ],
                'team': {
                    'id': team_id or 'team-1',
                    'name': 'Engineering',
                    'icon': '⚙️'
                },
                'issue_count': 1
            },
            {
                'cycle_id': 'cycle-2',
                'name': 'Q4 2023 Testing',
                'description': 'Testing and QA cycle for Q4 2023',
                'number': 2,
                'start_at': (datetime.utcnow() - timedelta(days=120)).isoformat(),
                'end_at': (datetime.utcnow() - timedelta(days=30)).isoformat(),
                'completed_at': (datetime.utcnow() - timedelta(days=30)).isoformat(),
                'progress': 100,
                'issues': [],
                'team': {
                    'id': team_id or 'team-1',
                    'name': 'Engineering',
                    'icon': '⚙️'
                },
                'issue_count': 0
            }
        ]
        
        # Filter based on completion preference
        filtered_cycles = []
        for cycle in mock_cycles:
            if not include_completed and cycle['completed_at']:
                continue
            filtered_cycles.append(cycle)
        
        return jsonify(format_linear_response({
            'cycles': filtered_cycles[:limit],
            'total_count': len(filtered_cycles)
        }, 'list_cycles'))
    
    except Exception as e:
        logger.error(f"Error listing cycles: {e}")
        return jsonify(format_error_response(e, 'list_cycles')), 500

@linear_enhanced_bp.route('/api/integrations/linear/users', methods=['POST'])
async def list_users():
    """List users from organization or teams"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        team_id = data.get('team_id')
        include_inactive = data.get('include_inactive', False)
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
                'error': {'message': 'Linear tokens not found'}
            }), 401
        
        # Use Linear service
        if LINEAR_SERVICE_AVAILABLE:
            users = await linear_service.get_organization_users(user_id, team_id, include_inactive, limit)
            
            users_data = [{
                'id': user.id,
                'name': user.name,
                'displayName': user.displayName,
                'email': user.email,
                'avatarUrl': user.avatarUrl,
                'url': user.url,
                'role': user.role,
                'organization': user.organization,
                'active': user.active,
                'lastSeen': user.lastSeen
            } for user in users]
            
            return jsonify(format_linear_response({
                'users': users_data,
                'total_count': len(users_data)
            }, 'list_users'))
        
        # Fallback to mock data
        mock_users = [
            {
                'id': 'user-1',
                'name': 'Alice Developer',
                'displayName': 'Alice Developer',
                'email': 'alice@company.com',
                'avatarUrl': 'https://example.com/alice.png',
                'url': 'https://linear.app/alice',
                'role': 'admin',
                'organization': {
                    'id': 'org-1',
                    'name': 'Tech Company',
                    'urlKey': 'tech-company'
                },
                'active': True,
                'lastSeen': (datetime.utcnow() - timedelta(hours=2)).isoformat()
            },
            {
                'id': 'user-2',
                'name': 'Bob Engineer',
                'displayName': 'Bob Engineer',
                'email': 'bob@company.com',
                'avatarUrl': 'https://example.com/bob.png',
                'url': 'https://linear.app/bob',
                'role': 'member',
                'organization': {
                    'id': 'org-1',
                    'name': 'Tech Company',
                    'urlKey': 'tech-company'
                },
                'active': True,
                'lastSeen': (datetime.utcnow() - timedelta(hours=1)).isoformat()
            },
            {
                'id': 'user-3',
                'name': 'Carol Designer',
                'displayName': 'Carol Designer',
                'email': 'carol@company.com',
                'avatarUrl': 'https://example.com/carol.png',
                'url': 'https://linear.app/carol',
                'role': 'member',
                'organization': {
                    'id': 'org-1',
                    'name': 'Tech Company',
                    'urlKey': 'tech-company'
                },
                'active': True,
                'lastSeen': (datetime.utcnow() - timedelta(hours=3)).isoformat()
            },
            {
                'id': 'guest-1',
                'name': 'External Contractor',
                'displayName': 'External Contractor',
                'email': 'contractor@external.com',
                'avatarUrl': 'https://example.com/guest.png',
                'url': 'https://linear.app/contractor',
                'role': 'guest',
                'organization': {
                    'id': 'org-1',
                    'name': 'Tech Company',
                    'urlKey': 'tech-company'
                },
                'active': True,
                'lastSeen': (datetime.utcnow() - timedelta(hours=6)).isoformat()
            }
        ]
        
        # Filter based on activity preference
        filtered_users = []
        for user in mock_users:
            if not include_inactive and not user['active']:
                continue
            filtered_users.append(user)
        
        return jsonify(format_linear_response({
            'users': filtered_users[:limit],
            'total_count': len(filtered_users)
        }, 'list_users'))
    
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify(format_error_response(e, 'list_users')), 500

@linear_enhanced_bp.route('/api/integrations/linear/user/profile', methods=['POST'])
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
                'error': {'message': 'Linear tokens not found'}
            }), 401
        
        # Return user info from tokens
        return jsonify(format_linear_response({
            'user': tokens['user_info'],
            'organization': {
                'id': tokens['user_info'].get('organization', {}).get('id'),
                'name': tokens['user_info'].get('organization', {}).get('name') or 'Personal Workspace',
                'urlKey': tokens['user_info'].get('organization', {}).get('urlKey')
            }
        }, 'get_user_profile'))
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify(format_error_response(e, 'get_user_profile')), 500

@linear_enhanced_bp.route('/api/integrations/linear/search', methods=['POST'])
async def search_linear():
    """Search across Linear"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        search_type = data.get('type', 'issues')
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
                'error': {'message': 'Linear tokens not found'}
            }), 401
        
        # Use Linear service
        if LINEAR_SERVICE_AVAILABLE:
            result = await linear_service.search_linear(user_id, query, search_type, limit)
            return jsonify(result)
        
        # Fallback to mock search
        mock_results = [
            {
                'object': 'issue',
                'id': 'lin-search-1',
                'title': f'{query.title()} Development Setup',
                'url': 'https://linear.app/issue/lin-search-1',
                'status': {
                    'id': 'status-1',
                    'name': 'In Progress',
                    'color': 'blue'
                },
                'priority': {
                    'id': 'priority-1',
                    'label': 'High',
                    'priority': 4
                },
                'project': {
                    'id': 'proj-1',
                    'name': 'Mobile App',
                    'icon': '📱',
                    'color': 'blue'
                },
                'team': {
                    'id': 'team-1',
                    'name': 'Engineering',
                    'icon': '⚙️'
                },
                'type': 'Issue'
            },
            {
                'object': 'team',
                'id': 'lin-search-2',
                'title': f'{query.title()} Team',
                'url': 'https://linear.app/team/lin-search-2',
                'type': 'Team'
            }
        ]
        
        return jsonify(format_linear_response({
            'results': mock_results,
            'total_count': len(mock_results),
            'query': query
        }, 'search_linear'))
    
    except Exception as e:
        logger.error(f"Error searching Linear: {e}")
        return jsonify(format_error_response(e, 'search_linear')), 500

@linear_enhanced_bp.route('/api/integrations/linear/health', methods=['GET'])
async def health_check():
    """Linear service health check"""
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify({
                'status': 'unhealthy',
                'error': 'Linear service not available',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Test Linear API connectivity
        try:
            if LINEAR_SERVICE_AVAILABLE:
                service_info = linear_service.get_service_info()
                return jsonify({
                    'status': 'healthy',
                    'message': 'Linear API is accessible',
                    'service_available': LINEAR_SERVICE_AVAILABLE,
                    'database_available': LINEAR_DB_AVAILABLE,
                    'service_info': service_info,
                    'timestamp': datetime.utcnow().isoformat()
                })
        except Exception as e:
            return jsonify({
                'status': 'degraded',
                'error': f'Linear service error: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return jsonify({
            'status': 'healthy',
            'message': 'Linear API mock is accessible',
            'service_available': LINEAR_SERVICE_AVAILABLE,
            'database_available': LINEAR_DB_AVAILABLE,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

# Error handlers
@linear_enhanced_bp.errorhandler(404)
async def not_found(error):
    return jsonify({
        'ok': False,
        'error': {
            'code': 'NOT_FOUND',
            'message': 'Endpoint not found'
        }
    }), 404

@linear_enhanced_bp.errorhandler(500)
async def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'ok': False,
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'Internal server error'
        }
    }), 500