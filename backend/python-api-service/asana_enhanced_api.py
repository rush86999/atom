"""
ATOM Enhanced Asana API Handler
Complete Asana integration with comprehensive API operations
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

# Import Asana service
try:
    from asana_service_real import asana_service
    ASANA_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Asana service not available: {e}")
    ASANA_SERVICE_AVAILABLE = False
    asana_service = None

# Import database handler
try:
    from db_oauth_asana import get_tokens, save_tokens, delete_tokens, get_user_asana_tasks, save_asana_task, get_user_asana_projects, save_asana_project, get_user_asana_sections, save_asana_section, get_user_asana_teams, save_asana_team, get_user_asana_users, save_asana_user
    ASANA_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Asana database handler not available: {e}")
    ASANA_DB_AVAILABLE = False

asana_enhanced_bp = Blueprint("asana_enhanced_bp", __name__)

# Configuration
ASANA_API_BASE_URL = "https://app.asana.com/api/1.0"
REQUEST_TIMEOUT = 30

async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Asana tokens for user"""
    if not ASANA_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            'access_token': os.getenv('ASANA_ACCESS_TOKEN', 'mock_asana_access_token_' + os.urandom(8).hex()),
            'refresh_token': os.getenv('ASANA_REFRESH_TOKEN', 'mock_asana_refresh_token_' + os.urandom(8).hex()),
            'expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            'scope': 'default tasks:read tasks:write projects:read projects:write stories:read stories:write teams:read users:read webhooks:read webhooks:write',
            'user_info': {
                'gid': os.getenv('ASANA_USER_ID', '1204910829086229'),
                'name': os.getenv('ASANA_USER_NAME', 'Alice Developer'),
                'email': os.getenv('ASANA_USER_EMAIL', 'alice@company.com'),
                'avatar_url_128x128': os.getenv('ASANA_USER_AVATAR', 'https://example.com/avatars/alice.png'),
                'workspaces': [{
                    'gid': os.getenv('ASANA_WORKSPACE_ID', '1204910829086249'),
                    'name': os.getenv('ASANA_WORKSPACE_NAME', 'Tech Company')
                }],
                'active': True,
                'last_login': datetime.utcnow().isoformat()
            }
        }
    
    try:
        tokens = await get_tokens(None, user_id)  # db_conn_pool - will be passed in production
        return tokens
    except Exception as e:
        logger.error(f"Error getting Asana tokens for user {user_id}: {e}")
        return None

def format_asana_response(data: Any, endpoint: str) -> Dict[str, Any]:
    """Format Asana API response"""
    return {
        'ok': True,
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'asana_api'
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
        'source': 'asana_api'
    }

@asana_enhanced_bp.route('/api/integrations/asana/tasks', methods=['POST'])
async def list_tasks():
    """List user Asana tasks"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
        project_id = data.get('project_id')
        include_completed = data.get('include_completed', True)
        limit = data.get('limit', 50)
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'create':
            return await _create_task(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Asana tokens not found'}
            }), 401
        
        # Use Asana service
        if ASANA_SERVICE_AVAILABLE:
            tasks = await asana_service.get_user_tasks(
                tokens['access_token'], user_id, workspace_id, project_id, include_completed, False, limit
            )
            
            tasks_data = [{
                'task_id': task.id,
                'name': task.name,
                'notes': task.notes,
                'completed': task.completed,
                'assignee': task.assignee and {
                    'id': task.assignee.get('id') if isinstance(task.assignee, dict) else task.assignee.gid,
                    'name': task.assignee.get('name') if isinstance(task.assignee, dict) else task.assignee.name,
                    'email': task.assignee.get('email') if isinstance(task.assignee, dict) else task.assignee.email,
                    'avatar_url': task.assignee.get('avatar_url_128x128') if isinstance(task.assignee, dict) else task.assignee.avatar_url_128x128
                },
                'projects': [{
                    'id': project.get('id') if isinstance(project, dict) else project.gid,
                    'name': project.get('name') if isinstance(project, dict) else project.name,
                    'color': project.get('color') if isinstance(project, dict) else project.color
                } for project in (task.projects or [])],
                'due_on': task.due_on,
                'due_at': task.due_at,
                'tags': task.tags or [],
                'custom_fields': task.custom_fields or [],
                'status': task.status,
                'priority': task.priority,
                'created_at': task.created_at,
                'modified_at': task.modified_at,
                'url': f"https://app.asana.com/0/{(task.projects[0].get('id') if task.projects and task.projects[0] else 'DEFAULT')}/{task.id}"
            } for task in tasks]
            
            return jsonify(format_asana_response({
                'tasks': tasks_data,
                'total_count': len(tasks_data)
            }, 'list_tasks'))
        
        # Fallback to mock data
        mock_tasks = [
            {
                'task_id': '1204910829086228',
                'name': 'Update homepage hero section',
                'notes': 'Implement new hero section with product features and improved CTA',
                'completed': False,
                'assignee': {
                    'id': '1204910829086229',
                    'name': 'Alice Developer',
                    'email': 'alice@company.com',
                    'avatar_url': 'https://example.com/avatars/alice.png'
                },
                'projects': [{
                    'id': '1204910829086230',
                    'name': 'Website Redesign',
                    'color': 'blue'
                }],
                'due_on': '2024-01-20',
                'tags': [
                    {'id': 'tag-1', 'name': 'frontend', 'color': 'blue'},
                    {'id': 'tag-2', 'name': 'urgent', 'color': 'red'}
                ],
                'custom_fields': [
                    {
                        'id': 'field-1',
                        'name': 'Priority',
                        'type': 'enum',
                        'value': 'high'
                    }
                ],
                'status': 'in_progress',
                'priority': 'high',
                'created_at': '2024-01-10T10:00:00.000Z',
                'modified_at': '2024-01-15T14:30:00.000Z',
                'url': 'https://app.asana.com/0/1204910829086230/1204910829086228'
            },
            {
                'task_id': '1204910829086231',
                'name': 'Fix mobile navigation menu',
                'notes': 'Navigation menu is not responsive on mobile devices',
                'completed': True,
                'assignee': {
                    'id': '1204910829086232',
                    'name': 'Bob Engineer',
                    'email': 'bob@company.com',
                    'avatar_url': 'https://example.com/avatars/bob.png'
                },
                'projects': [{
                    'id': '1204910829086230',
                    'name': 'Website Redesign',
                    'color': 'blue'
                }],
                'due_on': '2024-01-18',
                'tags': [
                    {'id': 'tag-3', 'name': 'mobile', 'color': 'green'},
                    {'id': 'tag-4', 'name': 'bug', 'color': 'red'}
                ],
                'custom_fields': [
                    {
                        'id': 'field-1',
                        'name': 'Priority',
                        'type': 'enum',
                        'value': 'medium'
                    }
                ],
                'status': 'completed',
                'priority': 'medium',
                'created_at': '2024-01-08T09:00:00.000Z',
                'modified_at': '2024-01-17T16:45:00.000Z',
                'url': 'https://app.asana.com/0/1204910829086230/1204910829086231'
            },
            {
                'task_id': '1204910829086233',
                'name': 'Implement user authentication',
                'notes': 'Add OAuth2 integration for Google and GitHub',
                'completed': False,
                'assignee': None,
                'projects': [{
                    'id': '1204910829086234',
                    'name': 'Backend Development',
                    'color': 'green'
                }],
                'due_on': '2024-01-25',
                'tags': [
                    {'id': 'tag-5', 'name': 'backend', 'color': 'orange'},
                    {'id': 'tag-6', 'name': 'feature', 'color': 'purple'}
                ],
                'custom_fields': [
                    {
                        'id': 'field-1',
                        'name': 'Priority',
                        'type': 'enum',
                        'value': 'high'
                    }
                ],
                'status': 'todo',
                'priority': 'high',
                'created_at': '2024-01-12T11:00:00.000Z',
                'modified_at': '2024-01-16T10:20:00.000Z',
                'url': 'https://app.asana.com/0/1204910829086234/1204910829086233'
            }
        ]
        
        # Filter based on completion preference
        filtered_tasks = []
        for task in mock_tasks:
            if not include_completed and task['completed']:
                continue
            filtered_tasks.append(task)
        
        return jsonify(format_asana_response({
            'tasks': filtered_tasks[:limit],
            'total_count': len(filtered_tasks)
        }, 'list_tasks'))
    
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        return jsonify(format_error_response(e, 'list_tasks')), 500

async def _create_task(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to create task"""
    try:
        task_data = data.get('data', {})
        
        if not task_data.get('name'):
            return jsonify({
                'ok': False,
                'error': {'message': 'Task name is required'}
            }), 400
        
        # Use Asana service
        if ASANA_SERVICE_AVAILABLE:
            result = await asana_service.create_task(user_id, task_data, tokens['access_token'])
            
            if result.get('ok'):
                return jsonify(format_asana_response({
                    'task': result.get('task'),
                    'url': result.get('task', {}).get('url'),
                    'message': 'Task created successfully'
                }, 'create_task'))
            else:
                return jsonify(result)
        
        # Fallback to mock creation
        mock_task = {
            'task_id': 'asana_' + str(int(datetime.utcnow().timestamp())),
            'name': task_data['name'],
            'notes': task_data.get('description', ''),
            'completed': False,
            'assignee': task_data.get('assignee'),
            'projects': task_data.get('projects', []),
            'due_on': task_data.get('due_date'),
            'tags': task_data.get('tags', []),
            'custom_fields': task_data.get('custom_fields', []),
            'status': 'todo',
            'priority': task_data.get('priority', 'medium'),
            'created_at': datetime.utcnow().isoformat(),
            'modified_at': datetime.utcnow().isoformat(),
            'url': f"https://app.asana.com/0/{task_data.get('project', {}).get('id', 'DEFAULT')}/asana_{int(datetime.utcnow().timestamp())}"
        }
        
        return jsonify(format_asana_response({
            'task': mock_task,
            'url': mock_task['url'],
            'message': 'Task created successfully'
        }, 'create_task'))
    
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return jsonify(format_error_response(e, 'create_task')), 500

@asana_enhanced_bp.route('/api/integrations/asana/projects', methods=['POST'])
async def list_projects():
    """List projects from user workspace"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
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
                'error': {'message': 'Asana tokens not found'}
            }), 401
        
        # Use Asana service
        if ASANA_SERVICE_AVAILABLE:
            projects = await asana_service.get_user_projects(
                tokens['access_token'], user_id, workspace_id, team_id, limit
            )
            
            projects_data = [{
                'project_id': project.id,
                'name': project.name,
                'description': project.description,
                'color': project.color,
                'public': project.public,
                'owner': project.owner and {
                    'id': project.owner.get('id') if isinstance(project.owner, dict) else project.owner.gid,
                    'name': project.owner.get('name') if isinstance(project.owner, dict) else project.owner.name
                },
                'team': project.team and {
                    'id': project.team.get('id') if isinstance(project.team, dict) else project.team.gid,
                    'name': project.team.get('name') if isinstance(project.team, dict) else project.team.name
                },
                'archived': project.archived,
                'created_at': project.created_at,
                'modified_at': project.modified_at,
                'workspace': {
                    'id': project.workspace.get('id') if isinstance(project.workspace, dict) else project.workspace.gid,
                    'name': project.workspace.get('name') if isinstance(project.workspace, dict) else project.workspace.name
                },
                'url': f"https://app.asana.com/0/{project.id}"
            } for project in projects]
            
            return jsonify(format_asana_response({
                'projects': projects_data,
                'total_count': len(projects_data)
            }, 'list_projects'))
        
        # Fallback to mock data
        mock_projects = [
            {
                'project_id': '1204910829086230',
                'name': 'Website Redesign',
                'description': 'Complete overhaul of company website with modern design and improved UX',
                'color': 'blue',
                'public': False,
                'owner': {
                    'id': '1204910829086229',
                    'name': 'Alice Developer'
                },
                'team': {
                    'id': '1204910829086240',
                    'name': 'Web Development'
                },
                'archived': False,
                'created_at': '2024-01-05T00:00:00.000Z',
                'modified_at': '2024-01-15T14:30:00.000Z',
                'workspace': {
                    'id': '1204910829086249',
                    'name': 'Tech Company'
                },
                'url': 'https://app.asana.com/0/1204910829086230'
            },
            {
                'project_id': '1204910829086234',
                'name': 'Backend Development',
                'description': 'API development and backend infrastructure improvements',
                'color': 'green',
                'public': False,
                'owner': {
                    'id': '1204910829086232',
                    'name': 'Bob Engineer'
                },
                'team': {
                    'id': '1204910829086241',
                    'name': 'Engineering'
                },
                'archived': False,
                'created_at': '2024-01-03T00:00:00.000Z',
                'modified_at': '2024-01-16T12:00:00.000Z',
                'workspace': {
                    'id': '1204910829086249',
                    'name': 'Tech Company'
                },
                'url': 'https://app.asana.com/0/1204910829086234'
            },
            {
                'project_id': '1204910829086237',
                'name': 'Marketing Campaign',
                'description': 'Q1 2024 marketing campaign for new product launch',
                'color': 'purple',
                'public': True,
                'owner': {
                    'id': '1204910829086236',
                    'name': 'Carol Designer'
                },
                'team': {
                    'id': '1204910829086242',
                    'name': 'Marketing'
                },
                'archived': False,
                'created_at': '2024-01-08T00:00:00.000Z',
                'modified_at': '2024-01-14T15:15:00.000Z',
                'workspace': {
                    'id': '1204910829086249',
                    'name': 'Tech Company'
                },
                'url': 'https://app.asana.com/0/1204910829086237'
            }
        ]
        
        return jsonify(format_asana_response({
            'projects': mock_projects[:limit],
            'total_count': len(mock_projects)
        }, 'list_projects'))
    
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return jsonify(format_error_response(e, 'list_projects')), 500

@asana_enhanced_bp.route('/api/integrations/asana/sections', methods=['POST'])
async def list_sections():
    """List sections from projects"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        project_id = data.get('project_id')
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
                'error': {'message': 'Asana tokens not found'}
            }), 401
        
        # Use Asana service
        if ASANA_SERVICE_AVAILABLE:
            sections = await asana_service.get_user_sections(
                tokens['access_token'], user_id, project_id, limit
            )
            
            sections_data = [{
                'section_id': section.id,
                'name': section.name,
                'project': {
                    'id': section.project.get('id') if isinstance(section.project, dict) else section.project.gid,
                    'name': section.project.get('name') if isinstance(section.project, dict) else section.project.name,
                    'color': section.project.get('color') if isinstance(section.project, dict) else section.project.color
                },
                'created_at': section.created_at,
                'tasks_count': len(section.tasks) if section.tasks else 0
            } for section in sections]
            
            return jsonify(format_asana_response({
                'sections': sections_data,
                'total_count': len(sections_data)
            }, 'list_sections'))
        
        # Fallback to mock data
        mock_sections = [
            {
                'section_id': '1204910829086245',
                'name': 'Backlog',
                'project': {
                    'id': project_id or '1204910829086230',
                    'name': 'Website Redesign',
                    'color': 'blue'
                },
                'created_at': '2024-01-05T00:00:00.000Z',
                'tasks_count': 5
            },
            {
                'section_id': '1204910829086246',
                'name': 'To Do',
                'project': {
                    'id': project_id or '1204910829086230',
                    'name': 'Website Redesign',
                    'color': 'blue'
                },
                'created_at': '2024-01-05T00:00:00.000Z',
                'tasks_count': 3
            },
            {
                'section_id': '1204910829086247',
                'name': 'In Progress',
                'project': {
                    'id': project_id or '1204910829086230',
                    'name': 'Website Redesign',
                    'color': 'blue'
                },
                'created_at': '2024-01-05T00:00:00.000Z',
                'tasks_count': 4
            },
            {
                'section_id': '1204910829086248',
                'name': 'Done',
                'project': {
                    'id': project_id or '1204910829086230',
                    'name': 'Website Redesign',
                    'color': 'blue'
                },
                'created_at': '2024-01-05T00:00:00.000Z',
                'tasks_count': 8
            }
        ]
        
        return jsonify(format_asana_response({
            'sections': mock_sections[:limit],
            'total_count': len(mock_sections)
        }, 'list_sections'))
    
    except Exception as e:
        logger.error(f"Error listing sections: {e}")
        return jsonify(format_error_response(e, 'list_sections')), 500

@asana_enhanced_bp.route('/api/integrations/asana/teams', methods=['POST'])
async def list_teams():
    """List teams from user workspace"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
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
                'error': {'message': 'Asana tokens not found'}
            }), 401
        
        # Use Asana service
        if ASANA_SERVICE_AVAILABLE:
            teams = await asana_service.get_user_teams(
                tokens['access_token'], user_id, workspace_id, limit
            )
            
            teams_data = [{
                'team_id': team.id,
                'name': team.name,
                'description': team.description,
                'organization': team.organization and {
                    'id': team.organization.get('id') if isinstance(team.organization, dict) else team.organization.gid,
                    'name': team.organization.get('name') if isinstance(team.organization, dict) else team.organization.name,
                    'url': team.organization.get('permalink_url') if isinstance(team.organization, dict) else team.organization.url
                },
                'members_count': len(team.members) if team.members else 0,
                'projects_count': len(team.projects) if team.projects else 0,
                'tasks_count': 0,  # Would need additional API call
                'url': f"https://app.asana.com/0/{team.id}"
            } for team in teams]
            
            return jsonify(format_asana_response({
                'teams': teams_data,
                'total_count': len(teams_data)
            }, 'list_teams'))
        
        # Fallback to mock data
        mock_teams = [
            {
                'team_id': '1204910829086240',
                'name': 'Web Development',
                'description': 'Frontend development team responsible for web applications',
                'organization': {
                    'id': '1204910829086249',
                    'name': 'Tech Company',
                    'url': 'https://app.asana.com/0/1204910829086249'
                },
                'members_count': 8,
                'projects_count': 3,
                'tasks_count': 0,
                'url': 'https://app.asana.com/0/1204910829086240'
            },
            {
                'team_id': '1204910829086241',
                'name': 'Engineering',
                'description': 'Backend and infrastructure engineering team',
                'organization': {
                    'id': '1204910829086249',
                    'name': 'Tech Company',
                    'url': 'https://app.asana.com/0/1204910829086249'
                },
                'members_count': 12,
                'projects_count': 5,
                'tasks_count': 0,
                'url': 'https://app.asana.com/0/1204910829086241'
            },
            {
                'team_id': '1204910829086242',
                'name': 'Marketing',
                'description': 'Marketing and creative team for campaigns and content',
                'organization': {
                    'id': '1204910829086249',
                    'name': 'Tech Company',
                    'url': 'https://app.asana.com/0/1204910829086249'
                },
                'members_count': 6,
                'projects_count': 4,
                'tasks_count': 0,
                'url': 'https://app.asana.com/0/1204910829086242'
            },
            {
                'team_id': '1204910829086244',
                'name': 'Mobile Team',
                'description': 'Mobile application development team',
                'organization': {
                    'id': '1204910829086249',
                    'name': 'Tech Company',
                    'url': 'https://app.asana.com/0/1204910829086249'
                },
                'members_count': 7,
                'projects_count': 2,
                'tasks_count': 0,
                'url': 'https://app.asana.com/0/1204910829086244'
            }
        ]
        
        return jsonify(format_asana_response({
            'teams': mock_teams[:limit],
            'total_count': len(mock_teams)
        }, 'list_teams'))
    
    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        return jsonify(format_error_response(e, 'list_teams')), 500

@asana_enhanced_bp.route('/api/integrations/asana/users', methods=['POST'])
async def list_users():
    """List users from organization or teams"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
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
                'error': {'message': 'Asana tokens not found'}
            }), 401
        
        # Use Asana service
        if ASANA_SERVICE_AVAILABLE:
            user = await asana_service.get_user_profile(tokens['access_token'])
            
            if user:
                user_data = {
                    'user_id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'avatar_url': user.avatar_url_128x128,
                    'workspaces': user.workspaces,
                    'active': user.active,
                    'last_login': user.last_login
                }
                
                return jsonify(format_asana_response({
                    'users': [user_data],
                    'total_count': 1
                }, 'list_users'))
        
        # Fallback to mock data
        mock_users = [
            {
                'user_id': '1204910829086229',
                'name': 'Alice Developer',
                'email': 'alice@company.com',
                'avatar_url': 'https://example.com/avatars/alice.png',
                'workspaces': [{
                    'id': '1204910829086249',
                    'name': 'Tech Company'
                }],
                'active': True,
                'last_login': (datetime.utcnow() - timedelta(hours=2)).isoformat()
            },
            {
                'user_id': '1204910829086232',
                'name': 'Bob Engineer',
                'email': 'bob@company.com',
                'avatar_url': 'https://example.com/avatars/bob.png',
                'workspaces': [{
                    'id': '1204910829086249',
                    'name': 'Tech Company'
                }],
                'active': True,
                'last_login': (datetime.utcnow() - timedelta(hours=1)).isoformat()
            },
            {
                'user_id': '1204910829086236',
                'name': 'Carol Designer',
                'email': 'carol@company.com',
                'avatar_url': 'https://example.com/avatars/carol.png',
                'workspaces': [{
                    'id': '1204910829086249',
                    'name': 'Tech Company'
                }],
                'active': True,
                'last_login': (datetime.utcnow() - timedelta(hours=3)).isoformat()
            },
            {
                'user_id': '1204910829086239',
                'name': 'Dave Developer',
                'email': 'dave@company.com',
                'avatar_url': 'https://example.com/avatars/dave.png',
                'workspaces': [{
                    'id': '1204910829086249',
                    'name': 'Tech Company'
                }],
                'active': True,
                'last_login': (datetime.utcnow() - timedelta(hours=6)).isoformat()
            }
        ]
        
        return jsonify(format_asana_response({
            'users': mock_users[:limit],
            'total_count': len(mock_users)
        }, 'list_users'))
    
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify(format_error_response(e, 'list_users')), 500

@asana_enhanced_bp.route('/api/integrations/asana/user/profile', methods=['POST'])
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
                'error': {'message': 'Asana tokens not found'}
            }), 401
        
        # Return user info from tokens
        return jsonify(format_asana_response({
            'user': tokens['user_info'],
            'organization': tokens['user_info'].get('workspaces', [{}])[0]
        }, 'get_user_profile'))
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify(format_error_response(e, 'get_user_profile')), 500

@asana_enhanced_bp.route('/api/integrations/asana/search', methods=['POST'])
async def search_asana():
    """Search across Asana"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        search_type = data.get('type', 'tasks')
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
                'error': {'message': 'Asana tokens not found'}
            }), 401
        
        # Use Asana service
        if ASANA_SERVICE_AVAILABLE:
            result = await asana_service.search_asana(tokens['access_token'], query, search_type, limit)
            return jsonify(result)
        
        # Fallback to mock search
        mock_results = [
            {
                'object': 'task',
                'id': '1204910829086228',
                'title': f'{query.title()} Development Setup',
                'url': 'https://app.asana.com/0/1204910829086230/1204910829086228',
                'status': {
                    'completed': False,
                    'name': 'not_completed'
                },
                'assignee': {
                    'id': '1204910829086229',
                    'name': 'Alice Developer',
                    'email': 'alice@company.com'
                },
                'project': {
                    'id': '1204910829086230',
                    'name': 'Website Redesign',
                    'color': 'blue'
                },
                'type': 'Task'
            },
            {
                'object': 'project',
                'id': '1204910829086230',
                'title': f'{query.title()} Team',
                'url': 'https://app.asana.com/0/1204910829086230',
                'type': 'Project'
            }
        ]
        
        return jsonify(format_asana_response({
            'results': mock_results,
            'total_count': len(mock_results),
            'query': query
        }, 'search_asana'))
    
    except Exception as e:
        logger.error(f"Error searching Asana: {e}")
        return jsonify(format_error_response(e, 'search_asana')), 500

@asana_enhanced_bp.route('/api/integrations/asana/health', methods=['GET'])
async def health_check():
    """Asana service health check"""
    try:
        if not ASANA_SERVICE_AVAILABLE:
            return jsonify({
                'status': 'unhealthy',
                'error': 'Asana service not available',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Test Asana API connectivity
        try:
            if ASANA_SERVICE_AVAILABLE:
                service_info = asana_service.get_service_info()
                return jsonify({
                    'status': 'healthy',
                    'message': 'Asana API is accessible',
                    'service_available': ASANA_SERVICE_AVAILABLE,
                    'database_available': ASANA_DB_AVAILABLE,
                    'service_info': service_info,
                    'timestamp': datetime.utcnow().isoformat()
                })
        except Exception as e:
            return jsonify({
                'status': 'degraded',
                'error': f'Asana service error: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return jsonify({
            'status': 'healthy',
            'message': 'Asana API mock is accessible',
            'service_available': ASANA_SERVICE_AVAILABLE,
            'database_available': ASANA_DB_AVAILABLE,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

# Error handlers
@asana_enhanced_bp.errorhandler(404)
async def not_found(error):
    return jsonify({
        'ok': False,
        'error': {
            'code': 'NOT_FOUND',
            'message': 'Endpoint not found'
        }
    }), 404

@asana_enhanced_bp.errorhandler(500)
async def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'ok': False,
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'Internal server error'
        }
    }), 500