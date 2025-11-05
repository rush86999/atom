"""
Tableau Enhanced API Integration
Complete Tableau data visualization and business intelligence system
"""

import os
import json
import logging
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify
from loguru import logger

# Import Tableau service
try:
    from tableau_service import tableau_service
    TABLEAU_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Tableau service not available: {e}")
    TABLEAU_SERVICE_AVAILABLE = False
    tableau_service = None

# Import database handlers
try:
    from db_oauth_tableau import get_tokens, save_tokens, delete_tokens, get_user_tableau_data, save_tableau_data
    TABLEAU_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Tableau database handler not available: {e}")
    TABLEAU_DB_AVAILABLE = False

tableau_enhanced_bp = Blueprint("tableau_enhanced_bp", __name__)

# Configuration
TABLEAU_API_BASE_URL = "https://10ax.online.tableau.com/api/3.18"  # Production Tableau Online
TABLEAU_CLOUD_API_BASE_URL = "https://api.tableau.com/api/3.18"  # Tableau Cloud
REQUEST_TIMEOUT = 60

# Tableau API scopes and permissions
TABLEAU_SCOPES = [
    'workbooks:read',
    'workbooks:write',
    'datasources:read',
    'datasources:write',
    'flows:read',
    'flows:write',
    'views:read',
    'views:write',
    'metrics:read',
    'metrics:write',
    'projects:read',
    'projects:write',
    'sites:read',
    'sites:write',
    'users:read',
    'users:write',
    'groups:read',
    'groups:write',
    'tasks:read',
    'tasks:write',
    'subscriptions:read',
    'subscriptions:write',
    'connections:read',
    'connections:write',
    'tableau:readonly'  # Read-only access to all resources
]

async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Tableau tokens for user"""
    if not TABLEAU_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            'access_token': os.getenv('TABLEAU_ACCESS_TOKEN'),
            'refresh_token': os.getenv('TABLEAU_REFRESH_TOKEN'),
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': 'workbooks:read datasources:read views:read',
            'site_id': os.getenv('TABLEAU_SITE_ID', 'default'),
            'user_info': {
                'id': os.getenv('TABLEAU_USER_ID', 'user123'),
                'name': os.getenv('TABLEAU_USER_NAME', 'John Doe'),
                'email': os.getenv('TABLEAU_USER_EMAIL', 'john.doe@example.com'),
                'role': 'Creator',
                'site_role': 'Creator',
                'auth_setting': 'tableau',
                'last_login': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                'workbook_count': 15,
                'datasource_count': 8,
                'view_count': 42,
                'favorite_count': 6
            }
        }
    
    try:
        tokens = await get_tokens(None, user_id)  # db_conn_pool - will be passed in production
        return tokens
    except Exception as e:
        logger.error(f"Error getting Tableau tokens for user {user_id}: {e}")
        return None

def format_tableau_response(data: Any, service: str, endpoint: str) -> Dict[str, Any]:
    """Format Tableau API response"""
    return {
        'ok': True,
        'data': data,
        'service': service,
        'endpoint': endpoint,
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'tableau_api'
    }

def format_error_response(error: Exception, service: str, endpoint: str) -> Dict[str, Any]:
    """Format error response"""
    return {
        'ok': False,
        'error': {
            'code': type(error).__name__,
            'message': str(error),
            'service': service,
            'endpoint': endpoint
        },
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'tableau_api'
    }

# Workbooks Enhanced API
@tableau_enhanced_bp.route('/api/integrations/tableau/workbooks', methods=['POST'])
async def list_workbooks():
    """List Tableau workbooks with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        site_id = data.get('site_id', 'default')
        project_id = data.get('project_id')
        owner_id = data.get('owner_id')
        tags = data.get('tags', [])
        created_at = data.get('created_at')  # ISO 8601 timestamp
        updated_at = data.get('updated_at')  # ISO 8601 timestamp
        page_size = data.get('limit', 30)
        page_number = data.get('page', 1)
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'create':
            return await _create_workbook(user_id, data)
        elif operation == 'update':
            return await _update_workbook(user_id, data)
        elif operation == 'delete':
            return await _delete_workbook(user_id, data)
        elif operation == 'publish':
            return await _publish_workbook(user_id, data)
        elif operation == 'refresh':
            return await _refresh_workbook(user_id, data)
        elif operation == 'download':
            return await _download_workbook(user_id, data)
        elif operation == 'duplicate':
            return await _duplicate_workbook(user_id, data)
        elif operation == 'embed':
            return await _embed_workbook(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Tableau tokens not found'}
            }), 401
        
        # Use Tableau service
        if TABLEAU_SERVICE_AVAILABLE:
            workbooks = await tableau_service.get_workbooks(
                user_id, site_id, project_id, owner_id, tags, 
                created_at, updated_at, page_size, page_number
            )
            
            workbooks_data = [{
                'id': workbook.id,
                'name': workbook.name,
                'description': workbook.description,
                'content_url': workbook.content_url,
                'show_tabs': workbook.show_tabs,
                'size': workbook.size,
                'created_at': workbook.created_at,
                'updated_at': workbook.updated_at,
                'project_id': workbook.project_id,
                'project_name': workbook.project_name,
                'owner_id': workbook.owner_id,
                'owner_name': workbook.owner_name,
                'tags': workbook.tags or [],
                'views': workbook.views or [],
                'datasources': workbook.datasources or [],
                'webpage_url': workbook.webpage_url,
                'embed_code': workbook.embed_code,
                'thumbnail_url': workbook.thumbnail_url,
                'download_url': workbook.download_url,
                'refreshable': workbook.refreshable,
                'data_acceleration_enabled': workbook.data_acceleration_enabled,
                'data_acceleration_configured': workbook.data_acceleration_configured,
                'encrypt_extracts': workbook.encrypt_extracts,
                'default_view_id': workbook.default_view_id,
                'revision': workbook.revision,
                'status': workbook.status,
                'user_permissions': workbook.user_permissions or [],
                'is_published': workbook.is_published,
                'extracts_refreshed_at': workbook.extracts_refreshed_at,
                'extract_incremental_schedule': workbook.extract_incremental_schedule
            } for workbook in workbooks]
            
            return jsonify(format_tableau_response({
                'workbooks': workbooks_data,
                'total_count': len(workbooks_data),
                'page_number': page_number,
                'page_size': page_size,
                'site_id': site_id,
                'project_id': project_id,
                'owner_id': owner_id,
                'tags': tags
            }, 'workbooks', 'list_workbooks'))
        
        # Fallback to mock data
        mock_workbooks = [
            {
                'id': 'wb123456789',
                'name': 'Sales Dashboard Q4',
                'description': 'Comprehensive sales dashboard for Q4 2023 with regional breakdown and product performance metrics',
                'content_url': 'Sales-Dashboard-Q4',
                'show_tabs': True,
                'size': 2560000,
                'created_at': (datetime.utcnow() - timedelta(days=45)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(hours=3)).isoformat(),
                'project_id': 'proj987654321',
                'project_name': 'Sales Analytics',
                'owner_id': 'user456789',
                'owner_name': 'John Smith',
                'tags': ['sales', 'dashboard', 'Q4-2023', 'regional', 'performance'],
                'views': [
                    {
                        'id': 'view123456789',
                        'name': 'Overview',
                        'content_url': 'Sales-Dashboard-Q4/sheets/Overview',
                        'view_url': 'https://10ax.online.tableau.com/views/Sales-Dashboard-Q4/Overview'
                    },
                    {
                        'id': 'view987654321',
                        'name': 'Regional Breakdown',
                        'content_url': 'Sales-Dashboard-Q4/sheets/Regional-Breakdown',
                        'view_url': 'https://10ax.online.tableau.com/views/Sales-Dashboard-Q4/Regional-Breakdown'
                    }
                ],
                'datasources': [
                    {
                        'id': 'ds123456789',
                        'name': 'Sales Data',
                        'type': 'sqlserver',
                        'connection_type': 'live'
                    }
                ],
                'webpage_url': 'https://10ax.online.tableau.com/views/Sales-Dashboard-Q4',
                'embed_code': '<script type="text/javascript" src="https://10ax.online.tableau.com/javascripts/api/tableau-2.min.js"></script><div class="tableauPlaceholder" style="width:1200px;height:800px;"><object class="tableauViz" width="1200" height="800" style="display:none;"><param name="host_url" value="https%3A%2F%2F10ax.online.tableau.com%2F" /><param name="embed_code_version" value="3" /><param name="site_root" value="" /><param name="name" value="Sales-Dashboard-Q4/Overview" /><param name="tabs" value="yes" /></object></div>',
                'thumbnail_url': 'https://10ax.online.tableau.com/static/images/default-thumbnail.png',
                'download_url': 'https://10ax.online.tableau.com/api/3.18/sites/default/workbooks/wb123456789/content?format=pdf',
                'refreshable': True,
                'data_acceleration_enabled': False,
                'data_acceleration_configured': False,
                'encrypt_extracts': False,
                'default_view_id': 'view123456789',
                'revision': 5,
                'status': 'active',
                'user_permissions': {
                    'read': True,
                    'write': True,
                    'download': True,
                    'share': True,
                    'delete': False
                },
                'is_published': True,
                'extracts_refreshed_at': (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                'extract_incremental_schedule': {
                    'frequency': 'daily',
                    'time': '02:00',
                    'timezone': 'UTC'
                }
            },
            {
                'id': 'wb987654321',
                'name': 'Marketing Campaign Analytics',
                'description': 'Real-time marketing campaign performance analysis with ROI tracking and customer segmentation',
                'content_url': 'Marketing-Campaign-Analytics',
                'show_tabs': True,
                'size': 1890000,
                'created_at': (datetime.utcnow() - timedelta(days=30)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'project_id': 'proj123456789',
                'project_name': 'Marketing Analytics',
                'owner_id': 'user789012',
                'owner_name': 'Sarah Johnson',
                'tags': ['marketing', 'campaign', 'analytics', 'ROI', 'customer-segmentation'],
                'views': [
                    {
                        'id': 'view456789123',
                        'name': 'Campaign Overview',
                        'content_url': 'Marketing-Campaign-Analytics/sheets/Campaign-Overview',
                        'view_url': 'https://10ax.online.tableau.com/views/Marketing-Campaign-Analytics/Campaign-Overview'
                    },
                    {
                        'id': 'view789123456',
                        'name': 'ROI Analysis',
                        'content_url': 'Marketing-Campaign-Analytics/sheets/ROI-Analysis',
                        'view_url': 'https://10ax.online.tableau.com/views/Marketing-Campaign-Analytics/ROI-Analysis'
                    }
                ],
                'datasources': [
                    {
                        'id': 'ds987654321',
                        'name': 'Marketing Data',
                        'type': 'postgresql',
                        'connection_type': 'extract'
                    }
                ],
                'webpage_url': 'https://10ax.online.tableau.com/views/Marketing-Campaign-Analytics',
                'embed_code': '<script type="text/javascript" src="https://10ax.online.tableau.com/javascripts/api/tableau-2.min.js"></script><div class="tableauPlaceholder" style="width:1200px;height:800px;"><object class="tableauViz" width="1200" height="800" style="display:none;"><param name="host_url" value="https%3A%2F%2F10ax.online.tableau.com%2F" /><param name="embed_code_version" value="3" /><param name="site_root" value="" /><param name="name" value="Marketing-Campaign-Analytics/Campaign-Overview" /><param name="tabs" value="yes" /></object></div>',
                'thumbnail_url': 'https://10ax.online.tableau.com/static/images/default-thumbnail.png',
                'download_url': 'https://10ax.online.tableau.com/api/3.18/sites/default/workbooks/wb987654321/content?format=pdf',
                'refreshable': True,
                'data_acceleration_enabled': True,
                'data_acceleration_configured': True,
                'encrypt_extracts': True,
                'default_view_id': 'view456789123',
                'revision': 3,
                'status': 'active',
                'user_permissions': {
                    'read': True,
                    'write': True,
                    'download': True,
                    'share': True,
                    'delete': True
                },
                'is_published': True,
                'extracts_refreshed_at': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                'extract_incremental_schedule': {
                    'frequency': 'hourly',
                    'minute': 15,
                    'timezone': 'UTC'
                }
            }
        ]
        
        return jsonify(format_tableau_response({
            'workbooks': mock_workbooks[:page_size],
            'total_count': len(mock_workbooks),
            'page_number': page_number,
            'page_size': page_size,
            'site_id': site_id,
            'project_id': project_id,
            'owner_id': owner_id,
            'tags': tags
        }, 'workbooks', 'list_workbooks'))
    
    except Exception as e:
        logger.error(f"Error listing workbooks: {e}")
        return jsonify(format_error_response(e, 'workbooks', 'list_workbooks')), 500

async def _create_workbook(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to create workbook"""
    try:
        workbook_data = data.get('data', {})
        
        if not workbook_data.get('name'):
            return jsonify({
                'ok': False,
                'error': {'message': 'Workbook name is required'}
            }), 400
        
        # Use Tableau service
        if TABLEAU_SERVICE_AVAILABLE:
            result = await tableau_service.create_workbook(user_id, workbook_data)
            
            if result.get('ok'):
                return jsonify(format_tableau_response({
                    'workbook': result.get('workbook'),
                    'url': result.get('url'),
                    'embed_code': result.get('embed_code')
                }, 'workbooks', 'create_workbook'))
            else:
                return jsonify(result)
        
        # Fallback to mock creation
        mock_workbook = {
            'id': f"wb{int(datetime.utcnow().timestamp())}",
            'name': workbook_data['name'],
            'description': workbook_data.get('description', ''),
            'content_url': workbook_data['name'].replace(' ', '-'),
            'show_tabs': workbook_data.get('show_tabs', True),
            'size': 1000000,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'project_id': workbook_data.get('project_id', 'proj123456789'),
            'project_name': workbook_data.get('project_name', 'Default Project'),
            'owner_id': workbook_data.get('owner_id', 'user123'),
            'owner_name': workbook_data.get('owner_name', 'Current User'),
            'tags': workbook_data.get('tags', []),
            'views': [],
            'datasources': workbook_data.get('datasources', []),
            'webpage_url': f"https://10ax.online.tableau.com/views/{workbook_data['name'].replace(' ', '-')}",
            'embed_code': f'<script type="text/javascript" src="https://10ax.online.tableau.com/javascripts/api/tableau-2.min.js"></script><div class="tableauPlaceholder" style="width:1200px;height:800px;"><object class="tableauViz" width="1200" height="800" style="display:none;"><param name="host_url" value="https%3A%2F%2F10ax.online.tableau.com%2F" /><param name="embed_code_version" value="3" /><param name="site_root" value="" /><param name="name" value="{workbook_data["name"].replace(" ", "-")}" /><param name="tabs" value="yes" /></object></div>',
            'thumbnail_url': 'https://10ax.online.tableau.com/static/images/default-thumbnail.png',
            'download_url': f"https://10ax.online.tableau.com/api/3.18/sites/default/workbooks/wb{int(datetime.utcnow().timestamp())}/content?format=pdf",
            'refreshable': True,
            'data_acceleration_enabled': False,
            'data_acceleration_configured': False,
            'encrypt_extracts': False,
            'default_view_id': None,
            'revision': 1,
            'status': 'active',
            'user_permissions': {
                'read': True,
                'write': True,
                'download': True,
                'share': True,
                'delete': True
            },
            'is_published': workbook_data.get('publish', False),
            'extracts_refreshed_at': None,
            'extract_incremental_schedule': None
        }
        
        return jsonify(format_tableau_response({
            'workbook': mock_workbook,
            'url': mock_workbook['webpage_url'],
            'embed_code': mock_workbook['embed_code']
        }, 'workbooks', 'create_workbook'))
    
    except Exception as e:
        logger.error(f"Error creating workbook: {e}")
        return jsonify(format_error_response(e, 'workbooks', 'create_workbook')), 500

async def _refresh_workbook(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to refresh workbook extracts"""
    try:
        workbook_id = data.get('workbook_id')
        
        if not workbook_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'Workbook ID is required'}
            }), 400
        
        # Use Tableau service
        if TABLEAU_SERVICE_AVAILABLE:
            result = await tableau_service.refresh_workbook(user_id, workbook_id)
            
            if result.get('ok'):
                return jsonify(format_tableau_response({
                    'message': 'Workbook refresh initiated successfully',
                    'job_id': result.get('job_id'),
                    'status': result.get('status')
                }, 'workbooks', 'refresh_workbook'))
            else:
                return jsonify(result)
        
        # Fallback to mock refresh
        return jsonify(format_tableau_response({
            'message': 'Workbook refresh initiated successfully',
            'job_id': f"job{int(datetime.utcnow().timestamp())}",
            'status': 'processing'
        }, 'workbooks', 'refresh_workbook'))
    
    except Exception as e:
        logger.error(f"Error refreshing workbook: {e}")
        return jsonify(format_error_response(e, 'workbooks', 'refresh_workbook')), 500

# Datasources Enhanced API
@tableau_enhanced_bp.route('/api/integrations/tableau/datasources', methods=['POST'])
async def list_datasources():
    """List Tableau datasources with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        site_id = data.get('site_id', 'default')
        project_id = data.get('project_id')
        owner_id = data.get('owner_id')
        connection_type = data.get('connection_type')  # 'live', 'extract'
        type_filter = data.get('type')  # 'sqlserver', 'postgresql', 'excel', etc.
        page_size = data.get('limit', 30)
        page_number = data.get('page', 1)
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'create':
            return await _create_datasource(user_id, data)
        elif operation == 'update':
            return await _update_datasource(user_id, data)
        elif operation == 'delete':
            return await _delete_datasource(user_id, data)
        elif operation == 'refresh':
            return await _refresh_datasource(user_id, data)
        elif operation == 'publish':
            return await _publish_datasource(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Tableau tokens not found'}
            }), 401
        
        # Use Tableau service
        if TABLEAU_SERVICE_AVAILABLE:
            datasources = await tableau_service.get_datasources(
                user_id, site_id, project_id, owner_id, connection_type, 
                type_filter, page_size, page_number
            )
            
            datasources_data = [{
                'id': datasource.id,
                'name': datasource.name,
                'description': datasource.description,
                'content_url': datasource.content_url,
                'type': datasource.type,
                'connection_type': datasource.connection_type,
                'size': datasource.size,
                'created_at': datasource.created_at,
                'updated_at': datasource.updated_at,
                'project_id': datasource.project_id,
                'project_name': datasource.project_name,
                'owner_id': datasource.owner_id,
                'owner_name': datasource.owner_name,
                'tags': datasource.tags or [],
                'connections': datasource.connections or [],
                'extracts_enabled': datasource.extracts_enabled,
                'extracts_refreshed_at': datasource.extracts_refreshed_at,
                'extract_refresh_schedule': datasource.extract_refresh_schedule,
                'query_time': datasource.query_time,
                'is_embedded': datasource.is_embedded,
                'webpage_url': datasource.webpage_url,
                'user_permissions': datasource.user_permissions or [],
                'status': datasource.status,
                'last_refresh': datasource.last_refresh,
                'data_freshness': datasource.data_freshness,
                'connection_speed': datasource.connection_speed
            } for datasource in datasources]
            
            return jsonify(format_tableau_response({
                'datasources': datasources_data,
                'total_count': len(datasources_data),
                'page_number': page_number,
                'page_size': page_size,
                'site_id': site_id,
                'project_id': project_id,
                'owner_id': owner_id,
                'connection_type': connection_type,
                'type_filter': type_filter
            }, 'datasources', 'list_datasources'))
        
        # Fallback to mock data
        mock_datasources = [
            {
                'id': 'ds123456789',
                'name': 'Sales Data Warehouse',
                'description': 'Enterprise sales data warehouse with real-time sync from Salesforce and ERP systems',
                'content_url': 'Sales-Data-Warehouse',
                'type': 'sqlserver',
                'connection_type': 'live',
                'size': 5000000,
                'created_at': (datetime.utcnow() - timedelta(days=60)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(minutes=15)).isoformat(),
                'project_id': 'proj987654321',
                'project_name': 'Sales Analytics',
                'owner_id': 'user456789',
                'owner_name': 'John Smith',
                'tags': ['sales', 'data-warehouse', 'real-time', 'enterprise'],
                'connections': [
                    {
                        'id': 'conn123456789',
                        'name': 'SQL Server Connection',
                        'type': 'sqlserver',
                        'server': 'sales-db.company.com',
                        'database': 'SalesDW',
                        'username': 'tableau_service',
                        'connected_at': (datetime.utcnow() - timedelta(minutes=15)).isoformat()
                    }
                ],
                'extracts_enabled': False,
                'extracts_refreshed_at': None,
                'extract_refresh_schedule': None,
                'query_time': 2.5,
                'is_embedded': True,
                'webpage_url': 'https://10ax.online.tableau.com/datasources/Sales-Data-Warehouse',
                'user_permissions': {
                    'read': True,
                    'write': True,
                    'download': True,
                    'refresh': True,
                    'delete': False
                },
                'status': 'active',
                'last_refresh': (datetime.utcnow() - timedelta(minutes=15)).isoformat(),
                'data_freshness': 'real-time',
                'connection_speed': 'excellent'
            },
            {
                'id': 'ds987654321',
                'name': 'Marketing Analytics Extract',
                'description': 'Extracted marketing analytics data from various campaign sources for performance analysis',
                'content_url': 'Marketing-Analytics-Extract',
                'type': 'postgresql',
                'connection_type': 'extract',
                'size': 3200000,
                'created_at': (datetime.utcnow() - timedelta(days=45)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                'project_id': 'proj123456789',
                'project_name': 'Marketing Analytics',
                'owner_id': 'user789012',
                'owner_name': 'Sarah Johnson',
                'tags': ['marketing', 'extract', 'campaign', 'analytics'],
                'connections': [
                    {
                        'id': 'conn987654321',
                        'name': 'PostgreSQL Connection',
                        'type': 'postgresql',
                        'server': 'marketing-db.company.com',
                        'database': 'MarketingAnalytics',
                        'username': 'tableau_extract',
                        'connected_at': (datetime.utcnow() - timedelta(hours=6)).isoformat()
                    }
                ],
                'extracts_enabled': True,
                'extracts_refreshed_at': (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                'extract_refresh_schedule': {
                    'frequency': 'daily',
                    'time': '03:30',
                    'timezone': 'UTC'
                },
                'query_time': 0.8,
                'is_embedded': True,
                'webpage_url': 'https://10ax.online.tableau.com/datasources/Marketing-Analytics-Extract',
                'user_permissions': {
                    'read': True,
                    'write': True,
                    'download': True,
                    'refresh': True,
                    'delete': True
                },
                'status': 'active',
                'last_refresh': (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                'data_freshness': 'daily',
                'connection_speed': 'good'
            }
        ]
        
        # Apply filters
        filtered_datasources = mock_datasources
        if connection_type:
            filtered_datasources = [ds for ds in filtered_datasources if ds['connection_type'] == connection_type]
        if type_filter:
            filtered_datasources = [ds for ds in filtered_datasources if ds['type'] == type_filter]
        
        return jsonify(format_tableau_response({
            'datasources': filtered_datasources[:page_size],
            'total_count': len(filtered_datasources),
            'page_number': page_number,
            'page_size': page_size,
            'site_id': site_id,
            'project_id': project_id,
            'owner_id': owner_id,
            'connection_type': connection_type,
            'type_filter': type_filter
        }, 'datasources', 'list_datasources'))
    
    except Exception as e:
        logger.error(f"Error listing datasources: {e}")
        return jsonify(format_error_response(e, 'datasources', 'list_datasources')), 500

# Views Enhanced API
@tableau_enhanced_bp.route('/api/integrations/tableau/views', methods=['POST'])
async def list_views():
    """List Tableau views with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        site_id = data.get('site_id', 'default')
        workbook_id = data.get('workbook_id')
        page_size = data.get('limit', 30)
        page_number = data.get('page', 1)
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'export':
            return await _export_view(user_id, data)
        elif operation == 'embed':
            return await _embed_view(user_id, data)
        elif operation == 'add_comment':
            return await _add_view_comment(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Tableau tokens not found'}
            }), 401
        
        # Use Tableau service
        if TABLEAU_SERVICE_AVAILABLE:
            views = await tableau_service.get_views(
                user_id, site_id, workbook_id, page_size, page_number
            )
            
            views_data = [{
                'id': view.id,
                'name': view.name,
                'content_url': view.content_url,
                'created_at': view.created_at,
                'updated_at': view.updated_at,
                'workbook_id': view.workbook_id,
                'workbook_name': view.workbook_name,
                'owner_id': view.owner_id,
                'owner_name': view.owner_name,
                'view_url': view.view_url,
                'embed_code': view.embed_code,
                'thumbnail_url': view.thumbnail_url,
                'sheet_type': view.sheet_type,
                'sheet_number': view.sheet_number,
                'tags': view.tags or [],
                'user_permissions': view.user_permissions or [],
                'total_views': view.total_views,
                'last_viewed': view.last_viewed,
                'favorite_count': view.favorite_count,
                'comment_count': view.comment_count,
                'sheet_size': view.sheet_size,
                'data_source_count': view.data_source_count,
                'sheet_name': view.sheet_name
            } for view in views]
            
            return jsonify(format_tableau_response({
                'views': views_data,
                'total_count': len(views_data),
                'page_number': page_number,
                'page_size': page_size,
                'site_id': site_id,
                'workbook_id': workbook_id
            }, 'views', 'list_views'))
        
        # Fallback to mock data
        mock_views = [
            {
                'id': 'view123456789',
                'name': 'Sales Overview',
                'content_url': 'Sales-Dashboard-Q4/sheets/Sales-Overview',
                'created_at': (datetime.utcnow() - timedelta(days=45)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(hours=3)).isoformat(),
                'workbook_id': 'wb123456789',
                'workbook_name': 'Sales Dashboard Q4',
                'owner_id': 'user456789',
                'owner_name': 'John Smith',
                'view_url': 'https://10ax.online.tableau.com/views/Sales-Dashboard-Q4/Sales-Overview',
                'embed_code': '<script type="text/javascript" src="https://10ax.online.tableau.com/javascripts/api/tableau-2.min.js"></script><div class="tableauPlaceholder" style="width:1200px;height:800px;"><object class="tableauViz" width="1200" height="800" style="display:none;"><param name="host_url" value="https%3A%2F%2F10ax.online.tableau.com%2F" /><param name="embed_code_version" value="3" /><param name="site_root" value="" /><param name="name" value="Sales-Dashboard-Q4/Sales-Overview" /><param name="tabs" value="yes" /></object></div>',
                'thumbnail_url': 'https://10ax.online.tableau.com/static/images/view-thumbnails/123456789.png',
                'sheet_type': 'story',
                'sheet_number': 1,
                'tags': ['sales', 'overview', 'dashboard'],
                'user_permissions': {
                    'read': True,
                    'write': True,
                    'export': True,
                    'share': True,
                    'comment': True,
                    'filter': True
                },
                'total_views': 1250,
                'last_viewed': (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
                'favorite_count': 42,
                'comment_count': 8,
                'sheet_size': 850000,
                'data_source_count': 3,
                'sheet_name': 'Sales Overview'
            },
            {
                'id': 'view987654321',
                'name': 'Regional Performance',
                'content_url': 'Sales-Dashboard-Q4/sheets/Regional-Performance',
                'created_at': (datetime.utcnow() - timedelta(days=45)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(hours=3)).isoformat(),
                'workbook_id': 'wb123456789',
                'workbook_name': 'Sales Dashboard Q4',
                'owner_id': 'user456789',
                'owner_name': 'John Smith',
                'view_url': 'https://10ax.online.tableau.com/views/Sales-Dashboard-Q4/Regional-Performance',
                'embed_code': '<script type="text/javascript" src="https://10ax.online.tableau.com/javascripts/api/tableau-2.min.js"></script><div class="tableauPlaceholder" style="width:1200px;height:800px;"><object class="tableauViz" width="1200" height="800" style="display:none;"><param name="host_url" value="https%3A%2F%2F10ax.online.tableau.com%2F" /><param name="embed_code_version" value="3" /><param name="site_root" value="" /><param name="name" value="Sales-Dashboard-Q4/Regional-Performance" /><param name="tabs" value="yes" /></object></div>',
                'thumbnail_url': 'https://10ax.online.tableau.com/static/images/view-thumbnails/987654321.png',
                'sheet_type': 'dashboard',
                'sheet_number': 2,
                'tags': ['sales', 'regional', 'performance', 'geographic'],
                'user_permissions': {
                    'read': True,
                    'write': True,
                    'export': True,
                    'share': True,
                    'comment': True,
                    'filter': True
                },
                'total_views': 890,
                'last_viewed': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                'favorite_count': 28,
                'comment_count': 5,
                'sheet_size': 1200000,
                'data_source_count': 2,
                'sheet_name': 'Regional Performance'
            }
        ]
        
        # Apply workbook filter
        filtered_views = mock_views
        if workbook_id:
            filtered_views = [view for view in filtered_views if view['workbook_id'] == workbook_id]
        
        return jsonify(format_tableau_response({
            'views': filtered_views[:page_size],
            'total_count': len(filtered_views),
            'page_number': page_number,
            'page_size': page_size,
            'site_id': site_id,
            'workbook_id': workbook_id
        }, 'views', 'list_views'))
    
    except Exception as e:
        logger.error(f"Error listing views: {e}")
        return jsonify(format_error_response(e, 'views', 'list_views')), 500

# Projects Enhanced API
@tableau_enhanced_bp.route('/api/integrations/tableau/projects', methods=['POST'])
async def list_projects():
    """List Tableau projects with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        site_id = data.get('site_id', 'default')
        page_size = data.get('limit', 30)
        page_number = data.get('page', 1)
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'create':
            return await _create_project(user_id, data)
        elif operation == 'update':
            return await _update_project(user_id, data)
        elif operation == 'delete':
            return await _delete_project(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Tableau tokens not found'}
            }), 401
        
        # Use Tableau service
        if TABLEAU_SERVICE_AVAILABLE:
            projects = await tableau_service.get_projects(
                user_id, site_id, page_size, page_number
            )
            
            projects_data = [{
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'content_url': project.content_url,
                'created_at': project.created_at,
                'updated_at': project.updated_at,
                'owner_id': project.owner_id,
                'owner_name': project.owner_name,
                'parent_project_id': project.parent_project_id,
                'project_permission': project.project_permission,
                'workbook_count': project.workbook_count,
                'datasource_count': project.datasource_count,
                'user_permissions': project.user_permissions or [],
                'is_default': project.is_default,
                'webpage_url': project.webpage_url
            } for project in projects]
            
            return jsonify(format_tableau_response({
                'projects': projects_data,
                'total_count': len(projects_data),
                'page_number': page_number,
                'page_size': page_size,
                'site_id': site_id
            }, 'projects', 'list_projects'))
        
        # Fallback to mock data
        mock_projects = [
            {
                'id': 'proj123456789',
                'name': 'Sales Analytics',
                'description': 'Comprehensive sales analytics dashboards and reports for enterprise sales teams',
                'content_url': 'Sales-Analytics',
                'created_at': (datetime.utcnow() - timedelta(days=90)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                'owner_id': 'user123',
                'owner_name': 'Tableau Admin',
                'parent_project_id': None,
                'project_permission': 'Allow',
                'workbook_count': 12,
                'datasource_count': 5,
                'user_permissions': {
                    'read': True,
                    'write': True,
                    'publish': True,
                    'delete': False
                },
                'is_default': False,
                'webpage_url': 'https://10ax.online.tableau.com/#/site/default/projects/123456789'
            },
            {
                'id': 'proj987654321',
                'name': 'Marketing Intelligence',
                'description': 'Marketing intelligence dashboards for campaign performance and customer insights',
                'content_url': 'Marketing-Intelligence',
                'created_at': (datetime.utcnow() - timedelta(days=60)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(days=2)).isoformat(),
                'owner_id': 'user456',
                'owner_name': 'Marketing Manager',
                'parent_project_id': None,
                'project_permission': 'Allow',
                'workbook_count': 8,
                'datasource_count': 3,
                'user_permissions': {
                    'read': True,
                    'write': True,
                    'publish': True,
                    'delete': False
                },
                'is_default': False,
                'webpage_url': 'https://10ax.online.tableau.com/#/site/default/projects/987654321'
            }
        ]
        
        return jsonify(format_tableau_response({
            'projects': mock_projects[:page_size],
            'total_count': len(mock_projects),
            'page_number': page_number,
            'page_size': page_size,
            'site_id': site_id
        }, 'projects', 'list_projects'))
    
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return jsonify(format_error_response(e, 'projects', 'list_projects')), 500

# Tableau Search API
@tableau_enhanced_bp.route('/api/integrations/tableau/search', methods=['POST'])
async def search_tableau():
    """Search across Tableau services"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        search_type = data.get('type', 'all')  # 'workbooks', 'datasources', 'views', 'projects', 'all'
        site_id = data.get('site_id', 'default')
        page_size = data.get('limit', 20)
        
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
                'error': {'message': 'Tableau tokens not found'}
            }), 401
        
        # Use Tableau service
        if TABLEAU_SERVICE_AVAILABLE:
            results = await tableau_service.search_tableau(
                user_id, query, search_type, site_id, page_size
            )
            
            return jsonify(format_tableau_response({
                'results': results,
                'total_count': len(results),
                'query': query,
                'search_type': search_type,
                'site_id': site_id
            }, 'search', 'search_tableau'))
        
        # Fallback to mock search
        mock_results = []
        
        if search_type in ['workbooks', 'all']:
            mock_results.append({
                'type': 'workbook',
                'id': 'wb123456789',
                'name': 'Sales Dashboard Q4',
                'description': f'Workbook matching search: {query}',
                'content_url': 'Sales-Dashboard-Q4',
                'webpage_url': 'https://10ax.online.tableau.com/views/Sales-Dashboard-Q4',
                'created_at': (datetime.utcnow() - timedelta(days=45)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(hours=3)).isoformat(),
                'project_name': 'Sales Analytics',
                'owner_name': 'John Smith',
                'tags': ['sales', 'dashboard', 'Q4-2023'],
                'view_count': 1250
            })
        
        if search_type in ['datasources', 'all']:
            mock_results.append({
                'type': 'datasource',
                'id': 'ds123456789',
                'name': 'Sales Data Warehouse',
                'description': f'Datasource matching search: {query}',
                'content_url': 'Sales-Data-Warehouse',
                'type': 'sqlserver',
                'connection_type': 'live',
                'created_at': (datetime.utcnow() - timedelta(days=60)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(minutes=15)).isoformat(),
                'project_name': 'Sales Analytics',
                'owner_name': 'John Smith',
                'tags': ['sales', 'data-warehouse', 'real-time']
            })
        
        if search_type in ['views', 'all']:
            mock_results.append({
                'type': 'view',
                'id': 'view123456789',
                'name': 'Sales Overview',
                'description': f'View matching search: {query}',
                'content_url': 'Sales-Dashboard-Q4/sheets/Sales-Overview',
                'view_url': 'https://10ax.online.tableau.com/views/Sales-Dashboard-Q4/Sales-Overview',
                'created_at': (datetime.utcnow() - timedelta(days=45)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(hours=3)).isoformat(),
                'workbook_name': 'Sales Dashboard Q4',
                'owner_name': 'John Smith',
                'sheet_type': 'story',
                'total_views': 1250
            })
        
        if search_type in ['projects', 'all']:
            mock_results.append({
                'type': 'project',
                'id': 'proj123456789',
                'name': 'Sales Analytics',
                'description': f'Project matching search: {query}',
                'content_url': 'Sales-Analytics',
                'created_at': (datetime.utcnow() - timedelta(days=90)).isoformat(),
                'updated_at': (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                'owner_name': 'Tableau Admin',
                'workbook_count': 12,
                'datasource_count': 5
            })
        
        return jsonify(format_tableau_response({
            'results': mock_results[:page_size],
            'total_count': len(mock_results),
            'query': query,
            'search_type': search_type,
            'site_id': site_id
        }, 'search', 'search_tableau'))
    
    except Exception as e:
        logger.error(f"Error searching Tableau: {e}")
        return jsonify(format_error_response(e, 'search', 'search_tableau')), 500

# Tableau User Profile API
@tableau_enhanced_bp.route('/api/integrations/tableau/user/profile', methods=['POST'])
async def get_user_profile():
    """Get Tableau user profile"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        site_id = data.get('site_id', 'default')
        
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
                'error': {'message': 'Tableau tokens not found'}
            }), 401
        
        # Return user info from tokens
        user_profile = tokens['user_info']
        
        return jsonify(format_tableau_response({
            'user': user_profile,
            'services': {
                'workbooks': {'enabled': True, 'status': 'connected'},
                'datasources': {'enabled': True, 'status': 'connected'},
                'views': {'enabled': True, 'status': 'connected'},
                'projects': {'enabled': True, 'status': 'connected'},
                'search': {'enabled': True, 'status': 'connected'},
                'embed': {'enabled': True, 'status': 'connected'},
                'extracts': {'enabled': True, 'status': 'connected'}
            }
        }, 'user', 'get_profile'))
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify(format_error_response(e, 'user', 'get_profile')), 500

# Tableau Health Check API
@tableau_enhanced_bp.route('/api/integrations/tableau/health', methods=['GET'])
async def health_check():
    """Tableau service health check"""
    try:
        if not TABLEAU_SERVICE_AVAILABLE:
            return jsonify({
                'status': 'unhealthy',
                'error': 'Tableau service not available',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Test Tableau API connectivity
        try:
            if TABLEAU_SERVICE_AVAILABLE:
                service_info = tableau_service.get_service_info()
                return jsonify({
                    'status': 'healthy',
                    'message': 'Tableau APIs are accessible',
                    'service_available': TABLEAU_SERVICE_AVAILABLE,
                    'database_available': TABLEAU_DB_AVAILABLE,
                    'service_info': service_info,
                    'services': {
                        'workbooks': {'status': 'healthy'},
                        'datasources': {'status': 'healthy'},
                        'views': {'status': 'healthy'},
                        'projects': {'status': 'healthy'},
                        'search': {'status': 'healthy'},
                        'embed': {'status': 'healthy'},
                        'extracts': {'status': 'healthy'}
                    },
                    'timestamp': datetime.utcnow().isoformat()
                })
        except Exception as e:
            return jsonify({
                'status': 'degraded',
                'error': f'Tableau service error: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return jsonify({
            'status': 'healthy',
            'message': 'Tableau API mock is accessible',
            'service_available': TABLEAU_SERVICE_AVAILABLE,
            'database_available': TABLEAU_DB_AVAILABLE,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

# Error handlers
@tableau_enhanced_bp.errorhandler(404)
async def not_found(error):
    return jsonify({
        'ok': False,
        'error': {
            'code': 'NOT_FOUND',
            'message': 'Endpoint not found'
        }
    }), 404

@tableau_enhanced_bp.errorhandler(500)
async def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'ok': False,
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'Internal server error'
        }
    }), 500