"""
ATOM Enhanced Figma API Handler
Complete Figma integration with comprehensive API operations
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

# Import Figma service
try:
    from figma_service_real import figma_service
    FIGMA_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Figma service not available: {e}")
    FIGMA_SERVICE_AVAILABLE = False
    figma_service = None

# Import database handler
try:
    from db_oauth_figma import get_tokens, save_tokens, delete_tokens, get_user_figma_files, save_figma_file, get_user_figma_components, save_figma_component, get_figma_webhooks, save_figma_webhook
    FIGMA_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Figma database handler not available: {e}")
    FIGMA_DB_AVAILABLE = False

figma_enhanced_bp = Blueprint("figma_enhanced_bp", __name__)

# Configuration
FIGMA_API_BASE_URL = "https://api.figma.com/v1"
REQUEST_TIMEOUT = 30

async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Figma tokens for user"""
    if not FIGMA_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            'access_token': os.getenv('FIGMA_ACCESS_TOKEN'),
            'refresh_token': os.getenv('FIGMA_REFRESH_TOKEN'),
            'expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            'scope': 'file_read file_write user_read user_write',
            'user_info': {
                'id': os.getenv('FIGMA_USER_ID'),
                'name': os.getenv('FIGMA_USER_NAME', 'Test User'),
                'username': os.getenv('FIGMA_USER_USERNAME', 'testuser'),
                'email': os.getenv('FIGMA_USER_EMAIL', 'test@example.com'),
                'profile_picture_url': os.getenv('FIGMA_USER_AVATAR'),
                'department': os.getenv('FIGMA_USER_DEPARTMENT', 'Design'),
                'title': os.getenv('FIGMA_USER_TITLE', 'UI/UX Designer'),
                'organization_id': os.getenv('FIGMA_ORG_ID'),
                'role': 'admin',
                'can_edit': True,
                'has_guests': False,
                'is_active': True
            }
        }
    
    try:
        tokens = await get_tokens(None, user_id)  # db_conn_pool - will be passed in production
        return tokens
    except Exception as e:
        logger.error(f"Error getting Figma tokens for user {user_id}: {e}")
        return None

def format_figma_response(data: Any, endpoint: str) -> Dict[str, Any]:
    """Format Figma API response"""
    return {
        'ok': True,
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'figma_api'
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
        'source': 'figma_api'
    }

@figma_enhanced_bp.route('/api/integrations/figma/files', methods=['POST'])
async def list_files():
    """List user Figma files"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        team_id = data.get('team_id')
        include_archived = data.get('include_archived', False)
        include_deleted = data.get('include_deleted', False)
        limit = data.get('limit', 50)
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'create':
            return await _create_file(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Figma tokens not found'}
            }), 401
        
        # Use Figma service
        if FIGMA_SERVICE_AVAILABLE:
            files = await figma_service.get_user_files(
                user_id, team_id, include_archived, limit
            )
            
            files_data = [{
                'file_id': file.file_id,
                'key': file.key,
                'name': file.name,
                'thumbnail_url': file.thumbnail_url,
                'thumbnail_url_default': file.thumbnail_url_default,
                'content_readonly': file.content_readonly,
                'editor_type': file.editor_type,
                'last_modified': file.last_modified,
                'workspace_id': file.workspace_id,
                'workspace_name': file.workspace_name,
                'branch_id': file.branch_id,
                'url': f"https://www.figma.com/file/{file.key}",
                'share_url': f"https://www.figma.com/file/{file.key}"
            } for file in files]
            
            return jsonify(format_figma_response({
                'files': files_data,
                'total_count': len(files_data)
            }, 'list_files'))
        
        # Fallback to mock data
        mock_files = [
            {
                'file_id': 'fig-file-1',
                'key': 'ABC123',
                'name': 'Mobile App Design',
                'thumbnail_url': 'https://example.com/thumbnail1.png',
                'thumbnail_url_default': 'https://example.com/thumbnail1_default.png',
                'content_readonly': False,
                'editor_type': 'figma',
                'last_modified': (datetime.utcnow() - timedelta(days=1)).isoformat() + 'Z',
                'workspace_id': 'workspace-1',
                'workspace_name': 'Design Team',
                'branch_id': None,
                'url': 'https://www.figma.com/file/ABC123/Mobile-App-Design',
                'share_url': 'https://www.figma.com/file/ABC123/Mobile-App-Design'
            },
            {
                'file_id': 'fig-file-2',
                'key': 'DEF456',
                'name': 'Website Wireframes',
                'thumbnail_url': 'https://example.com/thumbnail2.png',
                'thumbnail_url_default': 'https://example.com/thumbnail2_default.png',
                'content_readonly': True,
                'editor_type': 'figjam',
                'last_modified': (datetime.utcnow() - timedelta(days=3)).isoformat() + 'Z',
                'workspace_id': 'workspace-1',
                'workspace_name': 'Design Team',
                'branch_id': None,
                'url': 'https://www.figma.com/file/DEF456/Website-Wireframes',
                'share_url': 'https://www.figma.com/file/DEF456/Website-Wireframes'
            },
            {
                'file_id': 'fig-file-3',
                'key': 'GHI789',
                'name': 'Design System',
                'thumbnail_url': 'https://example.com/thumbnail3.png',
                'thumbnail_url_default': 'https://example.com/thumbnail3_default.png',
                'content_readonly': False,
                'editor_type': 'figma',
                'last_modified': (datetime.utcnow() - timedelta(days=5)).isoformat() + 'Z',
                'workspace_id': 'workspace-2',
                'workspace_name': 'Product Team',
                'branch_id': None,
                'url': 'https://www.figma.com/file/GHI789/Design-System',
                'share_url': 'https://www.figma.com/file/GHI789/Design-System'
            }
        ]
        
        # Filter based on preferences
        if not include_archived:
            mock_files = [f for f in mock_files if not f.get('content_readonly')]
        
        return jsonify(format_figma_response({
            'files': mock_files[:limit],
            'total_count': len(mock_files)
        }, 'list_files'))
    
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify(format_error_response(e, 'list_files')), 500

async def _create_file(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to create file"""
    try:
        file_data = data.get('data', {})
        
        if not file_data.get('name'):
            return jsonify({
                'ok': False,
                'error': {'message': 'File name is required'}
            }), 400
        
        # Use Figma service
        if FIGMA_SERVICE_AVAILABLE:
            result = await figma_service.create_file(user_id, file_data)
            
            if result.get('ok'):
                return jsonify(format_figma_response({
                    'file': result.get('file'),
                    'url': result.get('file', {}).get('url'),
                    'message': 'File created successfully'
                }, 'create_file'))
            else:
                return jsonify(result)
        
        # Fallback to mock creation
        mock_file = {
            'file_id': 'fig-file-' + str(int(datetime.utcnow().timestamp())),
            'key': 'NEW' + str(int(datetime.utcnow().timestamp())),
            'name': file_data['name'],
            'description': file_data.get('description', ''),
            'thumbnail_url': 'https://example.com/new_thumbnail.png',
            'content_readonly': False,
            'editor_type': 'figma',
            'last_modified': datetime.utcnow().isoformat() + 'Z',
            'workspace_id': file_data.get('workspace_id', 'workspace-1'),
            'workspace_name': file_data.get('workspace_name', 'Design Team'),
            'branch_id': None,
            'url': f"https://www.figma.com/file/NEW{int(datetime.utcnow().timestamp())}/{file_data['name'].replace(' ', '-')}",
            'share_url': f"https://www.figma.com/file/NEW{int(datetime.utcnow().timestamp())}/{file_data['name'].replace(' ', '-')}"
        }
        
        return jsonify(format_figma_response({
            'file': mock_file,
            'url': mock_file['url'],
            'message': 'File created successfully'
        }, 'create_file'))
    
    except Exception as e:
        logger.error(f"Error creating file: {e}")
        return jsonify(format_error_response(e, 'create_file')), 500

@figma_enhanced_bp.route('/api/integrations/figma/teams', methods=['POST'])
async def list_teams():
    """List user Figma teams"""
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
                'error': {'message': 'Figma tokens not found'}
            }), 401
        
        # Use Figma service
        if FIGMA_SERVICE_AVAILABLE:
            teams = await figma_service.get_user_teams(user_id, limit)
            
            teams_data = [{
                'id': team.id,
                'name': team.name,
                'description': team.description,
                'profile_picture_url': team.profile_picture_url,
                'users': [{
                    'id': user.id,
                    'name': user.name,
                    'username': user.username,
                    'email': user.email,
                    'profile_picture_url': user.profile_picture_url,
                    'role': user.role
                } for user in team.users],
                'member_count': len(team.users) if team.users else 0
            } for team in teams]
            
            return jsonify(format_figma_response({
                'teams': teams_data,
                'total_count': len(teams_data)
            }, 'list_teams'))
        
        # Fallback to mock data
        mock_teams = [
            {
                'id': 'team-1',
                'name': 'Design Team',
                'description': 'Main design team for company',
                'profile_picture_url': 'https://example.com/team1.png',
                'users': [
                    {
                        'id': 'user-1',
                        'name': 'Alice Designer',
                        'username': 'alice',
                        'email': 'alice@company.com',
                        'profile_picture_url': 'https://example.com/alice.png',
                        'role': 'admin'
                    },
                    {
                        'id': 'user-2',
                        'name': 'Bob Designer',
                        'username': 'bob',
                        'email': 'bob@company.com',
                        'profile_picture_url': 'https://example.com/bob.png',
                        'role': 'member'
                    }
                ],
                'member_count': 2
            },
            {
                'id': 'team-2',
                'name': 'Product Team',
                'description': 'Product management and design collaboration',
                'profile_picture_url': 'https://example.com/team2.png',
                'users': [
                    {
                        'id': 'user-3',
                        'name': 'Carol Product',
                        'username': 'carol',
                        'email': 'carol@company.com',
                        'profile_picture_url': 'https://example.com/carol.png',
                        'role': 'member'
                    }
                ],
                'member_count': 1
            }
        ]
        
        return jsonify(format_figma_response({
            'teams': mock_teams[:limit],
            'total_count': len(mock_teams)
        }, 'list_teams'))
    
    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        return jsonify(format_error_response(e, 'list_teams')), 500

@figma_enhanced_bp.route('/api/integrations/figma/projects', methods=['POST'])
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
                'error': {'message': 'Figma tokens not found'}
            }), 401
        
        # Use Figma service
        if FIGMA_SERVICE_AVAILABLE:
            projects = await figma_service.get_team_projects(user_id, team_id, limit)
            
            projects_data = [{
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'team_id': project.team_id,
                'team_name': project.team_name,
                'files': [{
                    'file_id': file.file_id,
                    'key': file.key,
                    'name': file.name,
                    'thumbnail_url': file.thumbnail_url,
                    'last_modified': file.last_modified
                } for file in project.files],
                'file_count': len(project.files) if project.files else 0
            } for project in projects]
            
            return jsonify(format_figma_response({
                'projects': projects_data,
                'total_count': len(projects_data)
            }, 'list_projects'))
        
        # Fallback to mock data
        mock_projects = [
            {
                'id': 'proj-1',
                'name': 'Q1 Design Initiatives',
                'description': 'Design projects for Q1 2024',
                'team_id': team_id or 'team-1',
                'team_name': 'Design Team',
                'files': [
                    {
                        'file_id': 'fig-file-1',
                        'key': 'ABC123',
                        'name': 'Mobile App Design',
                        'thumbnail_url': 'https://example.com/thumbnail1.png',
                        'last_modified': (datetime.utcnow() - timedelta(days=1)).isoformat() + 'Z'
                    }
                ],
                'file_count': 1
            },
            {
                'id': 'proj-2',
                'name': 'Website Redesign',
                'description': 'Complete website redesign project',
                'team_id': team_id or 'team-1',
                'team_name': 'Design Team',
                'files': [
                    {
                        'file_id': 'fig-file-2',
                        'key': 'DEF456',
                        'name': 'Website Wireframes',
                        'thumbnail_url': 'https://example.com/thumbnail2.png',
                        'last_modified': (datetime.utcnow() - timedelta(days=3)).isoformat() + 'Z'
                    }
                ],
                'file_count': 1
            }
        ]
        
        return jsonify(format_figma_response({
            'projects': mock_projects[:limit],
            'total_count': len(mock_projects)
        }, 'list_projects'))
    
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return jsonify(format_error_response(e, 'list_projects')), 500

@figma_enhanced_bp.route('/api/integrations/figma/components', methods=['POST'])
async def list_components():
    """List components from files"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        file_key = data.get('file_key')
        limit = data.get('limit', 100)
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'create':
            return await _create_component(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Figma tokens not found'}
            }), 401
        
        # Use Figma service
        if FIGMA_SERVICE_AVAILABLE:
            components = await figma_service.get_file_components(user_id, file_key, limit)
            
            components_data = [{
                'component_key': component.key,
                'file_key': component.file_key,
                'node_id': component.node_id,
                'name': component.name,
                'description': component.description,
                'component_type': component.component_type,
                'thumbnail_url': component.thumbnail_url,
                'created_at': component.created_at,
                'modified_at': component.modified_at,
                'creator_id': component.creator_id,
                'url': f"https://www.figma.com/file/{component.file_key}?node-id={component.node_id}"
            } for component in components]
            
            return jsonify(format_figma_response({
                'components': components_data,
                'total_count': len(components_data)
            }, 'list_components'))
        
        # Fallback to mock data
        mock_components = [
            {
                'component_key': 'comp-1',
                'file_key': file_key or 'ABC123',
                'node_id': '1-2',
                'name': 'Primary Button',
                'description': 'Main call-to-action button component',
                'component_type': 'component',
                'thumbnail_url': 'https://example.com/comp1.png',
                'created_at': (datetime.utcnow() - timedelta(days=10)).isoformat() + 'Z',
                'modified_at': (datetime.utcnow() - timedelta(days=2)).isoformat() + 'Z',
                'creator_id': 'user-1',
                'url': f"https://www.figma.com/file/{file_key or 'ABC123'}?node-id=1-2"
            },
            {
                'component_key': 'comp-2',
                'file_key': file_key or 'ABC123',
                'node_id': '1-3',
                'name': 'Input Field',
                'description': 'Standard text input field component',
                'component_type': 'component',
                'thumbnail_url': 'https://example.com/comp2.png',
                'created_at': (datetime.utcnow() - timedelta(days=15)).isoformat() + 'Z',
                'modified_at': (datetime.utcnow() - timedelta(days=3)).isoformat() + 'Z',
                'creator_id': 'user-1',
                'url': f"https://www.figma.com/file/{file_key or 'ABC123'}?node-id=1-3"
            }
        ]
        
        return jsonify(format_figma_response({
            'components': mock_components[:limit],
            'total_count': len(mock_components)
        }, 'list_components'))
    
    except Exception as e:
        logger.error(f"Error listing components: {e}")
        return jsonify(format_error_response(e, 'list_components')), 500

async def _create_component(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to create component"""
    try:
        component_data = data.get('data', {})
        
        if not component_data.get('name'):
            return jsonify({
                'ok': False,
                'error': {'message': 'Component name is required'}
            }), 400
        
        # Use Figma service
        if FIGMA_SERVICE_AVAILABLE:
            result = await figma_service.create_component(user_id, component_data)
            
            if result.get('ok'):
                return jsonify(format_figma_response({
                    'component': result.get('component'),
                    'message': 'Component created successfully'
                }, 'create_component'))
            else:
                return jsonify(result)
        
        # Fallback to mock creation
        mock_component = {
            'component_key': 'comp-' + str(int(datetime.utcnow().timestamp())),
            'file_key': component_data.get('file_key', 'ABC123'),
            'node_id': '1-' + str(int(datetime.utcnow().timestamp())),
            'name': component_data['name'],
            'description': component_data.get('description', ''),
            'component_type': component_data.get('component_type', 'component'),
            'thumbnail_url': component_data.get('thumbnail_url', 'https://example.com/new_comp.png'),
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'modified_at': datetime.utcnow().isoformat() + 'Z',
            'creator_id': 'user-1',
            'url': f"https://www.figma.com/file/{component_data.get('file_key', 'ABC123')}?node-id=1-{int(datetime.utcnow().timestamp())}"
        }
        
        return jsonify(format_figma_response({
            'component': mock_component,
            'message': 'Component created successfully'
        }, 'create_component'))
    
    except Exception as e:
        logger.error(f"Error creating component: {e}")
        return jsonify(format_error_response(e, 'create_component')), 500

@figma_enhanced_bp.route('/api/integrations/figma/users', methods=['POST'])
async def list_users():
    """List users from workspace or teams"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        team_id = data.get('team_id')
        include_guests = data.get('include_guests', True)
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
                'error': {'message': 'Figma tokens not found'}
            }), 401
        
        # Use Figma service
        if FIGMA_SERVICE_AVAILABLE:
            users = await figma_service.get_workspace_users(user_id, team_id, include_guests, limit)
            
            users_data = [{
                'id': user.id,
                'name': user.name,
                'username': user.username,
                'email': user.email,
                'profile_picture_url': user.profile_picture_url,
                'department': user.department,
                'title': user.title,
                'organization_id': user.organization_id,
                'role': user.role,
                'can_edit': user.can_edit,
                'has_guests': user.has_guests,
                'is_active': user.is_active
            } for user in users]
            
            return jsonify(format_figma_response({
                'users': users_data,
                'total_count': len(users_data)
            }, 'list_users'))
        
        # Fallback to mock data
        mock_users = [
            {
                'id': 'user-1',
                'name': 'Alice Designer',
                'username': 'alice',
                'email': 'alice@company.com',
                'profile_picture_url': 'https://example.com/alice.png',
                'department': 'Design',
                'title': 'UI/UX Designer',
                'organization_id': 'org-1',
                'role': 'admin',
                'can_edit': True,
                'has_guests': False,
                'is_active': True
            },
            {
                'id': 'user-2',
                'name': 'Bob Designer',
                'username': 'bob',
                'email': 'bob@company.com',
                'profile_picture_url': 'https://example.com/bob.png',
                'department': 'Design',
                'title': 'Product Designer',
                'organization_id': 'org-1',
                'role': 'member',
                'can_edit': True,
                'has_guests': False,
                'is_active': True
            },
            {
                'id': 'guest-1',
                'name': 'External Collaborator',
                'username': 'external',
                'email': 'collab@external.com',
                'profile_picture_url': 'https://example.com/guest.png',
                'department': 'External',
                'title': 'Contract Designer',
                'organization_id': None,
                'role': 'guest',
                'can_edit': False,
                'has_guests': True,
                'is_active': True
            }
        ]
        
        # Filter based on preferences
        if not include_guests:
            mock_users = [u for u in mock_users if u['role'] !== 'guest']
        
        return jsonify(format_figma_response({
            'users': mock_users[:limit],
            'total_count': len(mock_users)
        }, 'list_users'))
    
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify(format_error_response(e, 'list_users')), 500

@figma_enhanced_bp.route('/api/integrations/figma/user/profile', methods=['POST'])
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
                'error': {'message': 'Figma tokens not found'}
            }), 401
        
        # Return user info from tokens
        return jsonify(format_figma_response({
            'user': tokens['user_info'],
            'organization': {
                'id': tokens['user_info'].get('organization_id'),
                'name': tokens['user_info'].get('organization_id') || 'Personal Workspace'
            }
        }, 'get_user_profile'))
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify(format_error_response(e, 'get_user_profile')), 500

@figma_enhanced_bp.route('/api/integrations/figma/search', methods=['POST'])
async def search_figma():
    """Search across Figma"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        search_type = data.get('type', 'global')
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
                'error': {'message': 'Figma tokens not found'}
            }), 401
        
        # Use Figma service
        if FIGMA_SERVICE_AVAILABLE:
            result = await figma_service.search_figma(user_id, query, search_type, limit)
            return jsonify(result)
        
        # Fallback to mock search
        mock_results = [
            {
                'object': 'file',
                'id': 'fig-search-1',
                'title': f'{query.title()} Design System',
                'url': 'https://www.figma.com/file/fig-search-1',
                'highlighted_title': f'<b>{query}</b> Design System',
                'snippet': f'This design system contains {query} components and styles...'
            },
            {
                'object': 'component',
                'id': 'comp-search-1',
                'title': f'{query.title()} Button',
                'url': 'https://www.figma.com/component/comp-search-1',
                'highlighted_title': f'<b>{query}</b> Button',
                'snippet': f'Primary {query} button component with hover states...'
            }
        ]
        
        return jsonify(format_figma_response({
            'results': mock_results,
            'total_count': len(mock_results),
            'query': query
        }, 'search_figma'))
    
    except Exception as e:
        logger.error(f"Error searching Figma: {e}")
        return jsonify(format_error_response(e, 'search_figma')), 500

@figma_enhanced_bp.route('/api/integrations/figma/health', methods=['GET'])
async def health_check():
    """Figma service health check"""
    try:
        if not FIGMA_SERVICE_AVAILABLE:
            return jsonify({
                'status': 'unhealthy',
                'error': 'Figma service not available',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Test Figma API connectivity
        try:
            if FIGMA_SERVICE_AVAILABLE:
                service_info = figma_service.get_service_info()
                return jsonify({
                    'status': 'healthy',
                    'message': 'Figma API is accessible',
                    'service_available': FIGMA_SERVICE_AVAILABLE,
                    'database_available': FIGMA_DB_AVAILABLE,
                    'service_info': service_info,
                    'timestamp': datetime.utcnow().isoformat()
                })
        except Exception as e:
            return jsonify({
                'status': 'degraded',
                'error': f'Figma service error: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return jsonify({
            'status': 'healthy',
            'message': 'Figma API mock is accessible',
            'service_available': FIGMA_SERVICE_AVAILABLE,
            'database_available': FIGMA_DB_AVAILABLE,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

# Error handlers
@figma_enhanced_bp.errorhandler(404)
async def not_found(error):
    return jsonify({
        'ok': False,
        'error': {
            'code': 'NOT_FOUND',
            'message': 'Endpoint not found'
        }
    }), 404

@figma_enhanced_bp.errorhandler(500)
async def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'ok': False,
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'Internal server error'
        }
    }), 500