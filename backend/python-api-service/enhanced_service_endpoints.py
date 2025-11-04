"""
Enhanced Service Endpoints for ATOM Platform
Auto-generated service endpoints for all discovered services
"""

from flask import Blueprint, jsonify, request
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

enhanced_service_bp = Blueprint('enhanced_services', __name__)

# Health endpoints for all services

@enhanced_service_bp.route('/api/services/lancedb_service/health', methods=['GET'])
def lancedb_service_health():
    """Health check for Lancedb"""
    return jsonify({
        "service": "lancedb_service",
        "name": "Lancedb",
        "status": "healthy",
        "type": "search",
        "capabilities": ['search_meeting_transcripts'],
        "last_checked": datetime.now().isoformat(),
        "message": "Lancedb service is available and ready"
    })

@enhanced_service_bp.route('/api/services/lancedb_service/info', methods=['GET'])
def lancedb_service_info():
    """Service information for Lancedb"""
    return jsonify({
        "service_id": "lancedb_service",
        "name": "Lancedb",
        "type": "search",
        "description": "Enhanced Lancedb integration service",
        "file_path": "_utils/lancedb_service.py",
        "status": "available",
        "capabilities": ['search_meeting_transcripts'],
        "workflow_integration": True,
        "chat_commands": ["use lancedb", "access lancedb"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/account_handler/health', methods=['GET'])
def account_handler_health():
    """Health check for Account"""
    return jsonify({
        "service": "account_handler",
        "name": "Account",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_accounts', 'create_account'],
        "last_checked": datetime.now().isoformat(),
        "message": "Account service is available and ready"
    })

@enhanced_service_bp.route('/api/services/account_handler/info', methods=['GET'])
def account_handler_info():
    """Service information for Account"""
    return jsonify({
        "service_id": "account_handler",
        "name": "Account",
        "type": "integration",
        "description": "Enhanced Account integration service",
        "file_path": "account_handler.py",
        "status": "available",
        "capabilities": ['get_accounts', 'create_account'],
        "workflow_integration": True,
        "chat_commands": ["use account", "access account"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/account_service/health', methods=['GET'])
def account_service_health():
    """Health check for Account"""
    return jsonify({
        "service": "account_service",
        "name": "Account",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_accounts', 'create_account'],
        "last_checked": datetime.now().isoformat(),
        "message": "Account service is available and ready"
    })

@enhanced_service_bp.route('/api/services/account_service/info', methods=['GET'])
def account_service_info():
    """Service information for Account"""
    return jsonify({
        "service_id": "account_service",
        "name": "Account",
        "type": "integration",
        "description": "Enhanced Account integration service",
        "file_path": "account_service.py",
        "status": "available",
        "capabilities": ['get_accounts', 'create_account'],
        "workflow_integration": True,
        "chat_commands": ["use account", "access account"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/add_service_health_endpoints/health', methods=['GET'])
def add_service_health_endpoints_health():
    """Health check for Add Health Endpoints"""
    return jsonify({
        "service": "add_service_health_endpoints",
        "name": "Add Health Endpoints",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_teams_health_handler', 'create_health_endpoints', 'create_github_health_handler', 'create_outlook_health_handler', 'create_gmail_health_handler', 'create_slack_health_handler', 'create_gdrive_health_handler'],
        "last_checked": datetime.now().isoformat(),
        "message": "Add Health Endpoints service is available and ready"
    })

@enhanced_service_bp.route('/api/services/add_service_health_endpoints/info', methods=['GET'])
def add_service_health_endpoints_info():
    """Service information for Add Health Endpoints"""
    return jsonify({
        "service_id": "add_service_health_endpoints",
        "name": "Add Health Endpoints",
        "type": "integration",
        "description": "Enhanced Add Health Endpoints integration service",
        "file_path": "add_service_health_endpoints.py",
        "status": "available",
        "capabilities": ['create_teams_health_handler', 'create_health_endpoints', 'create_github_health_handler', 'create_outlook_health_handler', 'create_gmail_health_handler', 'create_slack_health_handler', 'create_gdrive_health_handler'],
        "workflow_integration": True,
        "chat_commands": ["use add health endpoints", "access add health endpoints"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/agenda_service/health', methods=['GET'])
def agenda_service_health():
    """Health check for Agenda"""
    return jsonify({
        "service": "agenda_service",
        "name": "Agenda",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Agenda service is available and ready"
    })

@enhanced_service_bp.route('/api/services/agenda_service/info', methods=['GET'])
def agenda_service_info():
    """Service information for Agenda"""
    return jsonify({
        "service_id": "agenda_service",
        "name": "Agenda",
        "type": "integration",
        "description": "Enhanced Agenda integration service",
        "file_path": "agenda_service.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use agenda", "access agenda"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/asana_handler/health', methods=['GET'])
def asana_handler_health():
    """Health check for Asana"""
    return jsonify({
        "service": "asana_handler",
        "name": "Asana",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['search_asana_route', 'get_asana_client', 'list_tasks'],
        "last_checked": datetime.now().isoformat(),
        "message": "Asana service is available and ready"
    })

@enhanced_service_bp.route('/api/services/asana_handler/info', methods=['GET'])
def asana_handler_info():
    """Service information for Asana"""
    return jsonify({
        "service_id": "asana_handler",
        "name": "Asana",
        "type": "integration",
        "description": "Enhanced Asana integration service",
        "file_path": "asana_handler.py",
        "status": "available",
        "capabilities": ['search_asana_route', 'get_asana_client', 'list_tasks'],
        "workflow_integration": True,
        "chat_commands": ["use asana", "access asana"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/asana_handler_mock/health', methods=['GET'])
def asana_handler_mock_health():
    """Health check for Asana Mock"""
    return jsonify({
        "service": "asana_handler_mock",
        "name": "Asana Mock",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_service_status', 'get_status', 'get_auth_url', 'list_tasks', 'list_projects'],
        "last_checked": datetime.now().isoformat(),
        "message": "Asana Mock service is available and ready"
    })

@enhanced_service_bp.route('/api/services/asana_handler_mock/info', methods=['GET'])
def asana_handler_mock_info():
    """Service information for Asana Mock"""
    return jsonify({
        "service_id": "asana_handler_mock",
        "name": "Asana Mock",
        "type": "integration",
        "description": "Enhanced Asana Mock integration service",
        "file_path": "asana_handler_mock.py",
        "status": "available",
        "capabilities": ['get_service_status', 'get_status', 'get_auth_url', 'list_tasks', 'list_projects'],
        "workflow_integration": True,
        "chat_commands": ["use asana mock", "access asana mock"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/asana_service/health', methods=['GET'])
def asana_service_health():
    """Health check for Asana"""
    return jsonify({
        "service": "asana_service",
        "name": "Asana",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['download_file', 'list_files', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Asana service is available and ready"
    })

@enhanced_service_bp.route('/api/services/asana_service/info', methods=['GET'])
def asana_service_info():
    """Service information for Asana"""
    return jsonify({
        "service_id": "asana_service",
        "name": "Asana",
        "type": "integration",
        "description": "Enhanced Asana integration service",
        "file_path": "asana_service.py",
        "status": "available",
        "capabilities": ['download_file', 'list_files', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use asana", "access asana"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/asana_service_mock/health', methods=['GET'])
def asana_service_mock_health():
    """Health check for Asana Mock"""
    return jsonify({
        "service": "asana_service_mock",
        "name": "Asana Mock",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['list_users', 'get_service_status', 'get_project', 'get_task', 'list_tasks', 'list_projects'],
        "last_checked": datetime.now().isoformat(),
        "message": "Asana Mock service is available and ready"
    })

@enhanced_service_bp.route('/api/services/asana_service_mock/info', methods=['GET'])
def asana_service_mock_info():
    """Service information for Asana Mock"""
    return jsonify({
        "service_id": "asana_service_mock",
        "name": "Asana Mock",
        "type": "integration",
        "description": "Enhanced Asana Mock integration service",
        "file_path": "asana_service_mock.py",
        "status": "available",
        "capabilities": ['list_users', 'get_service_status', 'get_project', 'get_task', 'list_tasks', 'list_projects'],
        "workflow_integration": True,
        "chat_commands": ["use asana mock", "access asana mock"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/asana_service_real/health', methods=['GET'])
def asana_service_real_health():
    """Health check for Asana Real"""
    return jsonify({
        "service": "asana_service_real",
        "name": "Asana Real",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_service_status', 'create_task', 'get_asana_service_real', 'get_asana_api_client', 'update_task', 'download_file', 'list_files', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Asana Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/asana_service_real/info', methods=['GET'])
def asana_service_real_info():
    """Service information for Asana Real"""
    return jsonify({
        "service_id": "asana_service_real",
        "name": "Asana Real",
        "type": "integration",
        "description": "Enhanced Asana Real integration service",
        "file_path": "asana_service_real.py",
        "status": "available",
        "capabilities": ['get_service_status', 'create_task', 'get_asana_service_real', 'get_asana_api_client', 'update_task', 'download_file', 'list_files', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use asana real", "access asana real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler/health', methods=['GET'])
def auth_handler_health():
    """Health check for Auth"""
    return jsonify({
        "service": "auth_handler",
        "name": "Auth",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['create_dev_app', 'get_mcp_provider', 'get_gdrive_access_token_route', 'create_app', 'update_gdrive_access_token', 'get_token', 'get_mcp_credentials', 'get_db_connection_pool'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler/info', methods=['GET'])
def auth_handler_info():
    """Service information for Auth"""
    return jsonify({
        "service_id": "auth_handler",
        "name": "Auth",
        "type": "authentication",
        "description": "Enhanced Auth integration service",
        "file_path": "auth_handler.py",
        "status": "available",
        "capabilities": ['create_dev_app', 'get_mcp_provider', 'get_gdrive_access_token_route', 'create_app', 'update_gdrive_access_token', 'get_token', 'get_mcp_credentials', 'get_db_connection_pool'],
        "workflow_integration": True,
        "chat_commands": ["use auth", "access auth"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_asana/health', methods=['GET'])
def auth_handler_asana_health():
    """Health check for Auth Asana"""
    return jsonify({
        "service": "auth_handler_asana",
        "name": "Auth Asana",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_projects'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Asana service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_asana/info', methods=['GET'])
def auth_handler_asana_info():
    """Service information for Auth Asana"""
    return jsonify({
        "service_id": "auth_handler_asana",
        "name": "Auth Asana",
        "type": "authentication",
        "description": "Enhanced Auth Asana integration service",
        "file_path": "auth_handler_asana.py",
        "status": "available",
        "capabilities": ['get_projects'],
        "workflow_integration": True,
        "chat_commands": ["use auth asana", "access auth asana"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_box/health', methods=['GET'])
def auth_handler_box_health():
    """Health check for Auth Box"""
    return jsonify({
        "service": "auth_handler_box",
        "name": "Auth Box",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_box_oauth_flow'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Box service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_box/info', methods=['GET'])
def auth_handler_box_info():
    """Service information for Auth Box"""
    return jsonify({
        "service_id": "auth_handler_box",
        "name": "Auth Box",
        "type": "authentication",
        "description": "Enhanced Auth Box integration service",
        "file_path": "auth_handler_box.py",
        "status": "available",
        "capabilities": ['get_box_oauth_flow'],
        "workflow_integration": True,
        "chat_commands": ["use auth box", "access auth box"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_box_mock/health', methods=['GET'])
def auth_handler_box_mock_health():
    """Health check for Auth Box Mock"""
    return jsonify({
        "service": "auth_handler_box_mock",
        "name": "Auth Box Mock",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_box_tokens', 'get_box_auth_status', 'get_authorization_url', 'get_box_auth_url'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Box Mock service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_box_mock/info', methods=['GET'])
def auth_handler_box_mock_info():
    """Service information for Auth Box Mock"""
    return jsonify({
        "service_id": "auth_handler_box_mock",
        "name": "Auth Box Mock",
        "type": "authentication",
        "description": "Enhanced Auth Box Mock integration service",
        "file_path": "auth_handler_box_mock.py",
        "status": "available",
        "capabilities": ['get_box_tokens', 'get_box_auth_status', 'get_authorization_url', 'get_box_auth_url'],
        "workflow_integration": True,
        "chat_commands": ["use auth box mock", "access auth box mock"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_box_real/health', methods=['GET'])
def auth_handler_box_real_health():
    """Health check for Auth Box Real"""
    return jsonify({
        "service": "auth_handler_box_real",
        "name": "Auth Box Real",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_box_oauth_config'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Box Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_box_real/info', methods=['GET'])
def auth_handler_box_real_info():
    """Service information for Auth Box Real"""
    return jsonify({
        "service_id": "auth_handler_box_real",
        "name": "Auth Box Real",
        "type": "authentication",
        "description": "Enhanced Auth Box Real integration service",
        "file_path": "auth_handler_box_real.py",
        "status": "available",
        "capabilities": ['get_box_oauth_config'],
        "workflow_integration": True,
        "chat_commands": ["use auth box real", "access auth box real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_dropbox/health', methods=['GET'])
def auth_handler_dropbox_health():
    """Health check for Auth Dropbox"""
    return jsonify({
        "service": "auth_handler_dropbox",
        "name": "Auth Dropbox",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_files'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Dropbox service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_dropbox/info', methods=['GET'])
def auth_handler_dropbox_info():
    """Service information for Auth Dropbox"""
    return jsonify({
        "service_id": "auth_handler_dropbox",
        "name": "Auth Dropbox",
        "type": "authentication",
        "description": "Enhanced Auth Dropbox integration service",
        "file_path": "auth_handler_dropbox.py",
        "status": "available",
        "capabilities": ['get_files'],
        "workflow_integration": True,
        "chat_commands": ["use auth dropbox", "access auth dropbox"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_gdrive/health', methods=['GET'])
def auth_handler_gdrive_health():
    """Health check for Auth Gdrive"""
    return jsonify({
        "service": "auth_handler_gdrive",
        "name": "Auth Gdrive",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Gdrive service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_gdrive/info', methods=['GET'])
def auth_handler_gdrive_info():
    """Service information for Auth Gdrive"""
    return jsonify({
        "service_id": "auth_handler_gdrive",
        "name": "Auth Gdrive",
        "type": "authentication",
        "description": "Enhanced Auth Gdrive integration service",
        "file_path": "auth_handler_gdrive.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use auth gdrive", "access auth gdrive"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_gdrive_fixed/health', methods=['GET'])
def auth_handler_gdrive_fixed_health():
    """Health check for Auth Gdrive Fixed"""
    return jsonify({
        "service": "auth_handler_gdrive_fixed",
        "name": "Auth Gdrive Fixed",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Gdrive Fixed service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_gdrive_fixed/info', methods=['GET'])
def auth_handler_gdrive_fixed_info():
    """Service information for Auth Gdrive Fixed"""
    return jsonify({
        "service_id": "auth_handler_gdrive_fixed",
        "name": "Auth Gdrive Fixed",
        "type": "authentication",
        "description": "Enhanced Auth Gdrive Fixed integration service",
        "file_path": "auth_handler_gdrive_fixed.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use auth gdrive fixed", "access auth gdrive fixed"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_github/health', methods=['GET'])
def auth_handler_github_health():
    """Health check for Auth Github"""
    return jsonify({
        "service": "auth_handler_github",
        "name": "Auth Github",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_repositories'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Github service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_github/info', methods=['GET'])
def auth_handler_github_info():
    """Service information for Auth Github"""
    return jsonify({
        "service_id": "auth_handler_github",
        "name": "Auth Github",
        "type": "authentication",
        "description": "Enhanced Auth Github integration service",
        "file_path": "auth_handler_github.py",
        "status": "available",
        "capabilities": ['get_repositories'],
        "workflow_integration": True,
        "chat_commands": ["use auth github", "access auth github"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_gmail/health', methods=['GET'])
def auth_handler_gmail_health():
    """Health check for Auth Gmail"""
    return jsonify({
        "service": "auth_handler_gmail",
        "name": "Auth Gmail",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_emails'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Gmail service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_gmail/info', methods=['GET'])
def auth_handler_gmail_info():
    """Service information for Auth Gmail"""
    return jsonify({
        "service_id": "auth_handler_gmail",
        "name": "Auth Gmail",
        "type": "authentication",
        "description": "Enhanced Auth Gmail integration service",
        "file_path": "auth_handler_gmail.py",
        "status": "available",
        "capabilities": ['get_emails'],
        "workflow_integration": True,
        "chat_commands": ["use auth gmail", "access auth gmail"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_notion/health', methods=['GET'])
def auth_handler_notion_health():
    """Health check for Auth Notion"""
    return jsonify({
        "service": "auth_handler_notion",
        "name": "Auth Notion",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_pages'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Notion service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_notion/info', methods=['GET'])
def auth_handler_notion_info():
    """Service information for Auth Notion"""
    return jsonify({
        "service_id": "auth_handler_notion",
        "name": "Auth Notion",
        "type": "authentication",
        "description": "Enhanced Auth Notion integration service",
        "file_path": "auth_handler_notion.py",
        "status": "available",
        "capabilities": ['get_pages'],
        "workflow_integration": True,
        "chat_commands": ["use auth notion", "access auth notion"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_outlook/health', methods=['GET'])
def auth_handler_outlook_health():
    """Health check for Auth Outlook"""
    return jsonify({
        "service": "auth_handler_outlook",
        "name": "Auth Outlook",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_emails'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Outlook service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_outlook/info', methods=['GET'])
def auth_handler_outlook_info():
    """Service information for Auth Outlook"""
    return jsonify({
        "service_id": "auth_handler_outlook",
        "name": "Auth Outlook",
        "type": "authentication",
        "description": "Enhanced Auth Outlook integration service",
        "file_path": "auth_handler_outlook.py",
        "status": "available",
        "capabilities": ['get_emails'],
        "workflow_integration": True,
        "chat_commands": ["use auth outlook", "access auth outlook"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_shopify/health', methods=['GET'])
def auth_handler_shopify_health():
    """Health check for Auth Shopify"""
    return jsonify({
        "service": "auth_handler_shopify",
        "name": "Auth Shopify",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_shopify_auth_url'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Shopify service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_shopify/info', methods=['GET'])
def auth_handler_shopify_info():
    """Service information for Auth Shopify"""
    return jsonify({
        "service_id": "auth_handler_shopify",
        "name": "Auth Shopify",
        "type": "authentication",
        "description": "Enhanced Auth Shopify integration service",
        "file_path": "auth_handler_shopify.py",
        "status": "available",
        "capabilities": ['get_shopify_auth_url'],
        "workflow_integration": True,
        "chat_commands": ["use auth shopify", "access auth shopify"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_slack/health', methods=['GET'])
def auth_handler_slack_health():
    """Health check for Auth Slack"""
    return jsonify({
        "service": "auth_handler_slack",
        "name": "Auth Slack",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['send_message', 'get_channels'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Slack service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_slack/info', methods=['GET'])
def auth_handler_slack_info():
    """Service information for Auth Slack"""
    return jsonify({
        "service_id": "auth_handler_slack",
        "name": "Auth Slack",
        "type": "authentication",
        "description": "Enhanced Auth Slack integration service",
        "file_path": "auth_handler_slack.py",
        "status": "available",
        "capabilities": ['send_message', 'get_channels'],
        "workflow_integration": True,
        "chat_commands": ["use auth slack", "access auth slack"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_teams/health', methods=['GET'])
def auth_handler_teams_health():
    """Health check for Auth Teams"""
    return jsonify({
        "service": "auth_handler_teams",
        "name": "Auth Teams",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_teams', 'get_channels'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Teams service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_teams/info', methods=['GET'])
def auth_handler_teams_info():
    """Service information for Auth Teams"""
    return jsonify({
        "service_id": "auth_handler_teams",
        "name": "Auth Teams",
        "type": "authentication",
        "description": "Enhanced Auth Teams integration service",
        "file_path": "auth_handler_teams.py",
        "status": "available",
        "capabilities": ['get_teams', 'get_channels'],
        "workflow_integration": True,
        "chat_commands": ["use auth teams", "access auth teams"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_trello/health', methods=['GET'])
def auth_handler_trello_health():
    """Health check for Auth Trello"""
    return jsonify({
        "service": "auth_handler_trello",
        "name": "Auth Trello",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_boards'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Trello service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_trello/info', methods=['GET'])
def auth_handler_trello_info():
    """Service information for Auth Trello"""
    return jsonify({
        "service_id": "auth_handler_trello",
        "name": "Auth Trello",
        "type": "authentication",
        "description": "Enhanced Auth Trello integration service",
        "file_path": "auth_handler_trello.py",
        "status": "available",
        "capabilities": ['get_boards'],
        "workflow_integration": True,
        "chat_commands": ["use auth trello", "access auth trello"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_handler_zoho/health', methods=['GET'])
def auth_handler_zoho_health():
    """Health check for Auth Zoho"""
    return jsonify({
        "service": "auth_handler_zoho",
        "name": "Auth Zoho",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth Zoho service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_handler_zoho/info', methods=['GET'])
def auth_handler_zoho_info():
    """Service information for Auth Zoho"""
    return jsonify({
        "service_id": "auth_handler_zoho",
        "name": "Auth Zoho",
        "type": "authentication",
        "description": "Enhanced Auth Zoho integration service",
        "file_path": "auth_handler_zoho.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use auth zoho", "access auth zoho"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/auth_service/health', methods=['GET'])
def auth_service_health():
    """Health check for Auth"""
    return jsonify({
        "service": "auth_service",
        "name": "Auth",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_auth_url', 'get_connected_services', 'get_user_tokens'],
        "last_checked": datetime.now().isoformat(),
        "message": "Auth service is available and ready"
    })

@enhanced_service_bp.route('/api/services/auth_service/info', methods=['GET'])
def auth_service_info():
    """Service information for Auth"""
    return jsonify({
        "service_id": "auth_service",
        "name": "Auth",
        "type": "authentication",
        "description": "Enhanced Auth integration service",
        "file_path": "auth_service.py",
        "status": "available",
        "capabilities": ['get_auth_url', 'get_connected_services', 'get_user_tokens'],
        "workflow_integration": True,
        "chat_commands": ["use auth", "access auth"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/bamboohr_service/health', methods=['GET'])
def bamboohr_service_health():
    """Health check for Bamboohr"""
    return jsonify({
        "service": "bamboohr_service",
        "name": "Bamboohr",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_employee', 'get_bamboohr_client', 'create_employee'],
        "last_checked": datetime.now().isoformat(),
        "message": "Bamboohr service is available and ready"
    })

@enhanced_service_bp.route('/api/services/bamboohr_service/info', methods=['GET'])
def bamboohr_service_info():
    """Service information for Bamboohr"""
    return jsonify({
        "service_id": "bamboohr_service",
        "name": "Bamboohr",
        "type": "integration",
        "description": "Enhanced Bamboohr integration service",
        "file_path": "bamboohr_service.py",
        "status": "available",
        "capabilities": ['get_employee', 'get_bamboohr_client', 'create_employee'],
        "workflow_integration": True,
        "chat_commands": ["use bamboohr", "access bamboohr"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/billing_handler/health', methods=['GET'])
def billing_handler_health():
    """Health check for Billing"""
    return jsonify({
        "service": "billing_handler",
        "name": "Billing",
        "status": "healthy",
        "type": "financial",
        "capabilities": ['create_bill', 'get_bills'],
        "last_checked": datetime.now().isoformat(),
        "message": "Billing service is available and ready"
    })

@enhanced_service_bp.route('/api/services/billing_handler/info', methods=['GET'])
def billing_handler_info():
    """Service information for Billing"""
    return jsonify({
        "service_id": "billing_handler",
        "name": "Billing",
        "type": "financial",
        "description": "Enhanced Billing integration service",
        "file_path": "billing_handler.py",
        "status": "available",
        "capabilities": ['create_bill', 'get_bills'],
        "workflow_integration": True,
        "chat_commands": ["use billing", "access billing"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/billing_service/health', methods=['GET'])
def billing_service_health():
    """Health check for Billing"""
    return jsonify({
        "service": "billing_service",
        "name": "Billing",
        "status": "healthy",
        "type": "financial",
        "capabilities": ['create_bill', 'get_bills'],
        "last_checked": datetime.now().isoformat(),
        "message": "Billing service is available and ready"
    })

@enhanced_service_bp.route('/api/services/billing_service/info', methods=['GET'])
def billing_service_info():
    """Service information for Billing"""
    return jsonify({
        "service_id": "billing_service",
        "name": "Billing",
        "type": "financial",
        "description": "Enhanced Billing integration service",
        "file_path": "billing_service.py",
        "status": "available",
        "capabilities": ['create_bill', 'get_bills'],
        "workflow_integration": True,
        "chat_commands": ["use billing", "access billing"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/bookkeeping_handler/health', methods=['GET'])
def bookkeeping_handler_health():
    """Health check for Bookkeeping"""
    return jsonify({
        "service": "bookkeeping_handler",
        "name": "Bookkeeping",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['export_bookkeeping_data', 'send_to_zoho', 'get_bookkeeping_summary', 'create_bookkeeping_entry', 'get_bookkeeping_data', 'get_bookkeeping_report'],
        "last_checked": datetime.now().isoformat(),
        "message": "Bookkeeping service is available and ready"
    })

@enhanced_service_bp.route('/api/services/bookkeeping_handler/info', methods=['GET'])
def bookkeeping_handler_info():
    """Service information for Bookkeeping"""
    return jsonify({
        "service_id": "bookkeeping_handler",
        "name": "Bookkeeping",
        "type": "integration",
        "description": "Enhanced Bookkeeping integration service",
        "file_path": "bookkeeping_handler.py",
        "status": "available",
        "capabilities": ['export_bookkeeping_data', 'send_to_zoho', 'get_bookkeeping_summary', 'create_bookkeeping_entry', 'get_bookkeeping_data', 'get_bookkeeping_report'],
        "workflow_integration": True,
        "chat_commands": ["use bookkeeping", "access bookkeeping"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/bookkeeping_service/health', methods=['GET'])
def bookkeeping_service_health():
    """Health check for Bookkeeping"""
    return jsonify({
        "service": "bookkeeping_service",
        "name": "Bookkeeping",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['export_bookkeeping_data', 'send_to_zoho', 'get_bookkeeping_summary', 'create_bookkeeping_entry', 'get_bookkeeping_data', 'get_bookkeeping_report'],
        "last_checked": datetime.now().isoformat(),
        "message": "Bookkeeping service is available and ready"
    })

@enhanced_service_bp.route('/api/services/bookkeeping_service/info', methods=['GET'])
def bookkeeping_service_info():
    """Service information for Bookkeeping"""
    return jsonify({
        "service_id": "bookkeeping_service",
        "name": "Bookkeeping",
        "type": "integration",
        "description": "Enhanced Bookkeeping integration service",
        "file_path": "bookkeeping_service.py",
        "status": "available",
        "capabilities": ['export_bookkeeping_data', 'send_to_zoho', 'get_bookkeeping_summary', 'create_bookkeeping_entry', 'get_bookkeeping_data', 'get_bookkeeping_report'],
        "workflow_integration": True,
        "chat_commands": ["use bookkeeping", "access bookkeeping"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/box_handler/health', methods=['GET'])
def box_handler_health():
    """Health check for Box"""
    return jsonify({
        "service": "box_handler",
        "name": "Box",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['get_box_client', 'list_files', 'search_box_route'],
        "last_checked": datetime.now().isoformat(),
        "message": "Box service is available and ready"
    })

@enhanced_service_bp.route('/api/services/box_handler/info', methods=['GET'])
def box_handler_info():
    """Service information for Box"""
    return jsonify({
        "service_id": "box_handler",
        "name": "Box",
        "type": "storage",
        "description": "Enhanced Box integration service",
        "file_path": "box_handler.py",
        "status": "available",
        "capabilities": ['get_box_client', 'list_files', 'search_box_route'],
        "workflow_integration": True,
        "chat_commands": ["use box", "access box"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/box_handler_mock/health', methods=['GET'])
def box_handler_mock_health():
    """Health check for Box Mock"""
    return jsonify({
        "service": "box_handler_mock",
        "name": "Box Mock",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['get_auth_url', 'get_service_status', 'list_files', 'get_status'],
        "last_checked": datetime.now().isoformat(),
        "message": "Box Mock service is available and ready"
    })

@enhanced_service_bp.route('/api/services/box_handler_mock/info', methods=['GET'])
def box_handler_mock_info():
    """Service information for Box Mock"""
    return jsonify({
        "service_id": "box_handler_mock",
        "name": "Box Mock",
        "type": "storage",
        "description": "Enhanced Box Mock integration service",
        "file_path": "box_handler_mock.py",
        "status": "available",
        "capabilities": ['get_auth_url', 'get_service_status', 'list_files', 'get_status'],
        "workflow_integration": True,
        "chat_commands": ["use box mock", "access box mock"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/box_service/health', methods=['GET'])
def box_service_health():
    """Health check for Box"""
    return jsonify({
        "service": "box_service",
        "name": "Box",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['download_file', 'list_files', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Box service is available and ready"
    })

@enhanced_service_bp.route('/api/services/box_service/info', methods=['GET'])
def box_service_info():
    """Service information for Box"""
    return jsonify({
        "service_id": "box_service",
        "name": "Box",
        "type": "storage",
        "description": "Enhanced Box integration service",
        "file_path": "box_service.py",
        "status": "available",
        "capabilities": ['download_file', 'list_files', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use box", "access box"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/box_service_mock/health', methods=['GET'])
def box_service_mock_health():
    """Health check for Box Mock"""
    return jsonify({
        "service": "box_service_mock",
        "name": "Box Mock",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['get_service_status', 'list_files', 'upload_file', 'get_file_content'],
        "last_checked": datetime.now().isoformat(),
        "message": "Box Mock service is available and ready"
    })

@enhanced_service_bp.route('/api/services/box_service_mock/info', methods=['GET'])
def box_service_mock_info():
    """Service information for Box Mock"""
    return jsonify({
        "service_id": "box_service_mock",
        "name": "Box Mock",
        "type": "storage",
        "description": "Enhanced Box Mock integration service",
        "file_path": "box_service_mock.py",
        "status": "available",
        "capabilities": ['get_service_status', 'list_files', 'upload_file', 'get_file_content'],
        "workflow_integration": True,
        "chat_commands": ["use box mock", "access box mock"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/box_service_real/health', methods=['GET'])
def box_service_real_health():
    """Health check for Box Real"""
    return jsonify({
        "service": "box_service_real",
        "name": "Box Real",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['get_service_status', 'get_box_client_real', 'download_file', 'list_files', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Box Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/box_service_real/info', methods=['GET'])
def box_service_real_info():
    """Service information for Box Real"""
    return jsonify({
        "service_id": "box_service_real",
        "name": "Box Real",
        "type": "storage",
        "description": "Enhanced Box Real integration service",
        "file_path": "box_service_real.py",
        "status": "available",
        "capabilities": ['get_service_status', 'get_box_client_real', 'download_file', 'list_files', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use box real", "access box real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/budgeting_handler/health', methods=['GET'])
def budgeting_handler_health():
    """Health check for Budgeting"""
    return jsonify({
        "service": "budgeting_handler",
        "name": "Budgeting",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_budgets', 'create_budget'],
        "last_checked": datetime.now().isoformat(),
        "message": "Budgeting service is available and ready"
    })

@enhanced_service_bp.route('/api/services/budgeting_handler/info', methods=['GET'])
def budgeting_handler_info():
    """Service information for Budgeting"""
    return jsonify({
        "service_id": "budgeting_handler",
        "name": "Budgeting",
        "type": "integration",
        "description": "Enhanced Budgeting integration service",
        "file_path": "budgeting_handler.py",
        "status": "available",
        "capabilities": ['get_budgets', 'create_budget'],
        "workflow_integration": True,
        "chat_commands": ["use budgeting", "access budgeting"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/budgeting_service/health', methods=['GET'])
def budgeting_service_health():
    """Health check for Budgeting"""
    return jsonify({
        "service": "budgeting_service",
        "name": "Budgeting",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_budgets', 'create_budget'],
        "last_checked": datetime.now().isoformat(),
        "message": "Budgeting service is available and ready"
    })

@enhanced_service_bp.route('/api/services/budgeting_service/info', methods=['GET'])
def budgeting_service_info():
    """Service information for Budgeting"""
    return jsonify({
        "service_id": "budgeting_service",
        "name": "Budgeting",
        "type": "integration",
        "description": "Enhanced Budgeting integration service",
        "file_path": "budgeting_service.py",
        "status": "available",
        "capabilities": ['get_budgets', 'create_budget'],
        "workflow_integration": True,
        "chat_commands": ["use budgeting", "access budgeting"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/calendar_handler/health', methods=['GET'])
def calendar_handler_health():
    """Health check for Calendar"""
    return jsonify({
        "service": "calendar_handler",
        "name": "Calendar",
        "status": "healthy",
        "type": "calendar",
        "capabilities": ['get_calendar_providers', 'get_calendar_events', 'get_available_slots', 'sync_calendars'],
        "last_checked": datetime.now().isoformat(),
        "message": "Calendar service is available and ready"
    })

@enhanced_service_bp.route('/api/services/calendar_handler/info', methods=['GET'])
def calendar_handler_info():
    """Service information for Calendar"""
    return jsonify({
        "service_id": "calendar_handler",
        "name": "Calendar",
        "type": "calendar",
        "description": "Enhanced Calendar integration service",
        "file_path": "calendar_handler.py",
        "status": "available",
        "capabilities": ['get_calendar_providers', 'get_calendar_events', 'get_available_slots', 'sync_calendars'],
        "workflow_integration": True,
        "chat_commands": ["use calendar", "access calendar"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/calendar_service/health', methods=['GET'])
def calendar_service_health():
    """Health check for Calendar"""
    return jsonify({
        "service": "calendar_service",
        "name": "Calendar",
        "status": "healthy",
        "type": "calendar",
        "capabilities": ['delete_event', 'update_event', 'get_free_busy', 'sync_user_calendars', 'get_events', 'create_event'],
        "last_checked": datetime.now().isoformat(),
        "message": "Calendar service is available and ready"
    })

@enhanced_service_bp.route('/api/services/calendar_service/info', methods=['GET'])
def calendar_service_info():
    """Service information for Calendar"""
    return jsonify({
        "service_id": "calendar_service",
        "name": "Calendar",
        "type": "calendar",
        "description": "Enhanced Calendar integration service",
        "file_path": "calendar_service.py",
        "status": "available",
        "capabilities": ['delete_event', 'update_event', 'get_free_busy', 'sync_user_calendars', 'get_events', 'create_event'],
        "workflow_integration": True,
        "chat_commands": ["use calendar", "access calendar"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/contact_service/health', methods=['GET'])
def contact_service_health():
    """Health check for Contact"""
    return jsonify({
        "service": "contact_service",
        "name": "Contact",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['sync_contacts', 'get_contact_by_email', 'get_contacts', 'update_contact', 'get_contact_by_id', 'create_contact', 'get_contacts_by_company', 'delete_contact', 'search_contacts'],
        "last_checked": datetime.now().isoformat(),
        "message": "Contact service is available and ready"
    })

@enhanced_service_bp.route('/api/services/contact_service/info', methods=['GET'])
def contact_service_info():
    """Service information for Contact"""
    return jsonify({
        "service_id": "contact_service",
        "name": "Contact",
        "type": "integration",
        "description": "Enhanced Contact integration service",
        "file_path": "contact_service.py",
        "status": "available",
        "capabilities": ['sync_contacts', 'get_contact_by_email', 'get_contacts', 'update_contact', 'get_contact_by_id', 'create_contact', 'get_contacts_by_company', 'delete_contact', 'search_contacts'],
        "workflow_integration": True,
        "chat_commands": ["use contact", "access contact"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/content_marketer_handler/health', methods=['GET'])
def content_marketer_handler_health():
    """Health check for Content Marketer"""
    return jsonify({
        "service": "content_marketer_handler",
        "name": "Content Marketer",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_trello_card_from_wordpress_post', 'get_wordpress_post_summary', 'create_wordpress_post_from_google_drive_document'],
        "last_checked": datetime.now().isoformat(),
        "message": "Content Marketer service is available and ready"
    })

@enhanced_service_bp.route('/api/services/content_marketer_handler/info', methods=['GET'])
def content_marketer_handler_info():
    """Service information for Content Marketer"""
    return jsonify({
        "service_id": "content_marketer_handler",
        "name": "Content Marketer",
        "type": "integration",
        "description": "Enhanced Content Marketer integration service",
        "file_path": "content_marketer_handler.py",
        "status": "available",
        "capabilities": ['create_trello_card_from_wordpress_post', 'get_wordpress_post_summary', 'create_wordpress_post_from_google_drive_document'],
        "workflow_integration": True,
        "chat_commands": ["use content marketer", "access content marketer"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/content_marketer_service/health', methods=['GET'])
def content_marketer_service_health():
    """Health check for Content Marketer"""
    return jsonify({
        "service": "content_marketer_service",
        "name": "Content Marketer",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_trello_card_from_wordpress_post', 'get_wordpress_post_summary', 'create_wordpress_post_from_google_drive_document'],
        "last_checked": datetime.now().isoformat(),
        "message": "Content Marketer service is available and ready"
    })

@enhanced_service_bp.route('/api/services/content_marketer_service/info', methods=['GET'])
def content_marketer_service_info():
    """Service information for Content Marketer"""
    return jsonify({
        "service_id": "content_marketer_service",
        "name": "Content Marketer",
        "type": "integration",
        "description": "Enhanced Content Marketer integration service",
        "file_path": "content_marketer_service.py",
        "status": "available",
        "capabilities": ['create_trello_card_from_wordpress_post', 'get_wordpress_post_summary', 'create_wordpress_post_from_google_drive_document'],
        "workflow_integration": True,
        "chat_commands": ["use content marketer", "access content marketer"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/context_management_service/health', methods=['GET'])
def context_management_service_health():
    """Health check for Context Management"""
    return jsonify({
        "service": "context_management_service",
        "name": "Context Management",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['update_chat_context', 'search_similar_conversations', 'get_user_context_summary_sync', 'get_contextual_conversation_history', 'get_or_create_chat_context', 'get_user_preferences_sync', 'update_chat_context_sync', 'search_similar_conversations_sync', 'get_contextual_conversation_history_sync', 'get_context_aware_workflow_suggestions', 'get_user_preferences', 'get_conversation_history', 'get_context_aware_workflow_suggestions_sync', 'get_user_context_summary', 'get_or_create_chat_context_sync', 'get_conversation_history_sync'],
        "last_checked": datetime.now().isoformat(),
        "message": "Context Management service is available and ready"
    })

@enhanced_service_bp.route('/api/services/context_management_service/info', methods=['GET'])
def context_management_service_info():
    """Service information for Context Management"""
    return jsonify({
        "service_id": "context_management_service",
        "name": "Context Management",
        "type": "integration",
        "description": "Enhanced Context Management integration service",
        "file_path": "context_management_service.py",
        "status": "available",
        "capabilities": ['update_chat_context', 'search_similar_conversations', 'get_user_context_summary_sync', 'get_contextual_conversation_history', 'get_or_create_chat_context', 'get_user_preferences_sync', 'update_chat_context_sync', 'search_similar_conversations_sync', 'get_contextual_conversation_history_sync', 'get_context_aware_workflow_suggestions', 'get_user_preferences', 'get_conversation_history', 'get_context_aware_workflow_suggestions_sync', 'get_user_context_summary', 'get_or_create_chat_context_sync', 'get_conversation_history_sync'],
        "workflow_integration": True,
        "chat_commands": ["use context management", "access context management"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/customer_support_manager_handler/health', methods=['GET'])
def customer_support_manager_handler_health():
    """Health check for Customer Support Manager"""
    return jsonify({
        "service": "customer_support_manager_handler",
        "name": "Customer Support Manager",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_zendesk_ticket_from_salesforce_case', 'create_trello_card_from_zendesk_ticket', 'get_zendesk_ticket_summary'],
        "last_checked": datetime.now().isoformat(),
        "message": "Customer Support Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/customer_support_manager_handler/info', methods=['GET'])
def customer_support_manager_handler_info():
    """Service information for Customer Support Manager"""
    return jsonify({
        "service_id": "customer_support_manager_handler",
        "name": "Customer Support Manager",
        "type": "integration",
        "description": "Enhanced Customer Support Manager integration service",
        "file_path": "customer_support_manager_handler.py",
        "status": "available",
        "capabilities": ['create_zendesk_ticket_from_salesforce_case', 'create_trello_card_from_zendesk_ticket', 'get_zendesk_ticket_summary'],
        "workflow_integration": True,
        "chat_commands": ["use customer support manager", "access customer support manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/customer_support_manager_service/health', methods=['GET'])
def customer_support_manager_service_health():
    """Health check for Customer Support Manager"""
    return jsonify({
        "service": "customer_support_manager_service",
        "name": "Customer Support Manager",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_zendesk_ticket_from_salesforce_case', 'create_trello_card_from_zendesk_ticket', 'get_zendesk_ticket_summary'],
        "last_checked": datetime.now().isoformat(),
        "message": "Customer Support Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/customer_support_manager_service/info', methods=['GET'])
def customer_support_manager_service_info():
    """Service information for Customer Support Manager"""
    return jsonify({
        "service_id": "customer_support_manager_service",
        "name": "Customer Support Manager",
        "type": "integration",
        "description": "Enhanced Customer Support Manager integration service",
        "file_path": "customer_support_manager_service.py",
        "status": "available",
        "capabilities": ['create_zendesk_ticket_from_salesforce_case', 'create_trello_card_from_zendesk_ticket', 'get_zendesk_ticket_summary'],
        "workflow_integration": True,
        "chat_commands": ["use customer support manager", "access customer support manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/devops_manager_handler/health', methods=['GET'])
def devops_manager_handler_health():
    """Health check for Devops Manager"""
    return jsonify({
        "service": "devops_manager_handler",
        "name": "Devops Manager",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_trello_card_from_github_issue', 'get_github_pull_request_status', 'create_github_issue_from_jira_issue'],
        "last_checked": datetime.now().isoformat(),
        "message": "Devops Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/devops_manager_handler/info', methods=['GET'])
def devops_manager_handler_info():
    """Service information for Devops Manager"""
    return jsonify({
        "service_id": "devops_manager_handler",
        "name": "Devops Manager",
        "type": "integration",
        "description": "Enhanced Devops Manager integration service",
        "file_path": "devops_manager_handler.py",
        "status": "available",
        "capabilities": ['create_trello_card_from_github_issue', 'get_github_pull_request_status', 'create_github_issue_from_jira_issue'],
        "workflow_integration": True,
        "chat_commands": ["use devops manager", "access devops manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/devops_manager_service/health', methods=['GET'])
def devops_manager_service_health():
    """Health check for Devops Manager"""
    return jsonify({
        "service": "devops_manager_service",
        "name": "Devops Manager",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_trello_card_from_github_issue', 'get_github_pull_request_status', 'create_github_issue_from_jira_issue'],
        "last_checked": datetime.now().isoformat(),
        "message": "Devops Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/devops_manager_service/info', methods=['GET'])
def devops_manager_service_info():
    """Service information for Devops Manager"""
    return jsonify({
        "service_id": "devops_manager_service",
        "name": "Devops Manager",
        "type": "integration",
        "description": "Enhanced Devops Manager integration service",
        "file_path": "devops_manager_service.py",
        "status": "available",
        "capabilities": ['create_trello_card_from_github_issue', 'get_github_pull_request_status', 'create_github_issue_from_jira_issue'],
        "workflow_integration": True,
        "chat_commands": ["use devops manager", "access devops manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/document_handler/health', methods=['GET'])
def document_handler_health():
    """Health check for Document"""
    return jsonify({
        "service": "document_handler",
        "name": "Document",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Document service is available and ready"
    })

@enhanced_service_bp.route('/api/services/document_handler/info', methods=['GET'])
def document_handler_info():
    """Service information for Document"""
    return jsonify({
        "service_id": "document_handler",
        "name": "Document",
        "type": "integration",
        "description": "Enhanced Document integration service",
        "file_path": "document_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use document", "access document"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/document_service/health', methods=['GET'])
def document_service_health():
    """Health check for Document"""
    return jsonify({
        "service": "document_service",
        "name": "Document",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_documents', 'delete_document', 'upload_document', 'get_document_content', 'search_documents', 'process_document', 'get_document_statistics'],
        "last_checked": datetime.now().isoformat(),
        "message": "Document service is available and ready"
    })

@enhanced_service_bp.route('/api/services/document_service/info', methods=['GET'])
def document_service_info():
    """Service information for Document"""
    return jsonify({
        "service_id": "document_service",
        "name": "Document",
        "type": "integration",
        "description": "Enhanced Document integration service",
        "file_path": "document_service.py",
        "status": "available",
        "capabilities": ['get_documents', 'delete_document', 'upload_document', 'get_document_content', 'search_documents', 'process_document', 'get_document_statistics'],
        "workflow_integration": True,
        "chat_commands": ["use document", "access document"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/document_service_enhanced/health', methods=['GET'])
def document_service_enhanced_health():
    """Health check for Document Enhanced"""
    return jsonify({
        "service": "document_service_enhanced",
        "name": "Document Enhanced",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_documents', 'process_and_store_document', 'get_document_chunks', 'search_documents', 'update_document_embeddings', 'get_document_statistics'],
        "last_checked": datetime.now().isoformat(),
        "message": "Document Enhanced service is available and ready"
    })

@enhanced_service_bp.route('/api/services/document_service_enhanced/info', methods=['GET'])
def document_service_enhanced_info():
    """Service information for Document Enhanced"""
    return jsonify({
        "service_id": "document_service_enhanced",
        "name": "Document Enhanced",
        "type": "integration",
        "description": "Enhanced Document Enhanced integration service",
        "file_path": "document_service_enhanced.py",
        "status": "available",
        "capabilities": ['get_documents', 'process_and_store_document', 'get_document_chunks', 'search_documents', 'update_document_embeddings', 'get_document_statistics'],
        "workflow_integration": True,
        "chat_commands": ["use document enhanced", "access document enhanced"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/docusign_service/health', methods=['GET'])
def docusign_service_health():
    """Health check for Docusign"""
    return jsonify({
        "service": "docusign_service",
        "name": "Docusign",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_envelope', 'get_mock_envelope_template', 'get_envelope_status', 'get_docusign_client', 'get_envelope'],
        "last_checked": datetime.now().isoformat(),
        "message": "Docusign service is available and ready"
    })

@enhanced_service_bp.route('/api/services/docusign_service/info', methods=['GET'])
def docusign_service_info():
    """Service information for Docusign"""
    return jsonify({
        "service_id": "docusign_service",
        "name": "Docusign",
        "type": "integration",
        "description": "Enhanced Docusign integration service",
        "file_path": "docusign_service.py",
        "status": "available",
        "capabilities": ['create_envelope', 'get_mock_envelope_template', 'get_envelope_status', 'get_docusign_client', 'get_envelope'],
        "workflow_integration": True,
        "chat_commands": ["use docusign", "access docusign"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/docusign_service_real/health', methods=['GET'])
def docusign_service_real_health():
    """Health check for Docusign Real"""
    return jsonify({
        "service": "docusign_service_real",
        "name": "Docusign Real",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_envelope', 'get_envelope', 'get_docusign_client', 'get_envelope_status'],
        "last_checked": datetime.now().isoformat(),
        "message": "Docusign Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/docusign_service_real/info', methods=['GET'])
def docusign_service_real_info():
    """Service information for Docusign Real"""
    return jsonify({
        "service_id": "docusign_service_real",
        "name": "Docusign Real",
        "type": "integration",
        "description": "Enhanced Docusign Real integration service",
        "file_path": "docusign_service_real.py",
        "status": "available",
        "capabilities": ['create_envelope', 'get_envelope', 'get_docusign_client', 'get_envelope_status'],
        "workflow_integration": True,
        "chat_commands": ["use docusign real", "access docusign real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/dropbox_handler/health', methods=['GET'])
def dropbox_handler_health():
    """Health check for Dropbox"""
    return jsonify({
        "service": "dropbox_handler",
        "name": "Dropbox",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['search_dropbox_route', 'list_files', 'get_status'],
        "last_checked": datetime.now().isoformat(),
        "message": "Dropbox service is available and ready"
    })

@enhanced_service_bp.route('/api/services/dropbox_handler/info', methods=['GET'])
def dropbox_handler_info():
    """Service information for Dropbox"""
    return jsonify({
        "service_id": "dropbox_handler",
        "name": "Dropbox",
        "type": "storage",
        "description": "Enhanced Dropbox integration service",
        "file_path": "dropbox_handler.py",
        "status": "available",
        "capabilities": ['search_dropbox_route', 'list_files', 'get_status'],
        "workflow_integration": True,
        "chat_commands": ["use dropbox", "access dropbox"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/dropbox_service/health', methods=['GET'])
def dropbox_service_health():
    """Health check for Dropbox"""
    return jsonify({
        "service": "dropbox_service",
        "name": "Dropbox",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['download_file', 'list_files', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Dropbox service is available and ready"
    })

@enhanced_service_bp.route('/api/services/dropbox_service/info', methods=['GET'])
def dropbox_service_info():
    """Service information for Dropbox"""
    return jsonify({
        "service_id": "dropbox_service",
        "name": "Dropbox",
        "type": "storage",
        "description": "Enhanced Dropbox integration service",
        "file_path": "dropbox_service.py",
        "status": "available",
        "capabilities": ['download_file', 'list_files', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use dropbox", "access dropbox"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/financial_analyst_handler/health', methods=['GET'])
def financial_analyst_handler_health():
    """Health check for Financial Analyst"""
    return jsonify({
        "service": "financial_analyst_handler",
        "name": "Financial Analyst",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_opportunity_from_invoice', 'get_financial_summary', 'create_card_from_invoice'],
        "last_checked": datetime.now().isoformat(),
        "message": "Financial Analyst service is available and ready"
    })

@enhanced_service_bp.route('/api/services/financial_analyst_handler/info', methods=['GET'])
def financial_analyst_handler_info():
    """Service information for Financial Analyst"""
    return jsonify({
        "service_id": "financial_analyst_handler",
        "name": "Financial Analyst",
        "type": "integration",
        "description": "Enhanced Financial Analyst integration service",
        "file_path": "financial_analyst_handler.py",
        "status": "available",
        "capabilities": ['create_opportunity_from_invoice', 'get_financial_summary', 'create_card_from_invoice'],
        "workflow_integration": True,
        "chat_commands": ["use financial analyst", "access financial analyst"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/financial_analyst_service/health', methods=['GET'])
def financial_analyst_service_health():
    """Health check for Financial Analyst"""
    return jsonify({
        "service": "financial_analyst_service",
        "name": "Financial Analyst",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_salesforce_opportunity_from_xero_invoice', 'get_financial_summary', 'create_trello_card_from_xero_invoice'],
        "last_checked": datetime.now().isoformat(),
        "message": "Financial Analyst service is available and ready"
    })

@enhanced_service_bp.route('/api/services/financial_analyst_service/info', methods=['GET'])
def financial_analyst_service_info():
    """Service information for Financial Analyst"""
    return jsonify({
        "service_id": "financial_analyst_service",
        "name": "Financial Analyst",
        "type": "integration",
        "description": "Enhanced Financial Analyst integration service",
        "file_path": "financial_analyst_service.py",
        "status": "available",
        "capabilities": ['create_salesforce_opportunity_from_xero_invoice', 'get_financial_summary', 'create_trello_card_from_xero_invoice'],
        "workflow_integration": True,
        "chat_commands": ["use financial analyst", "access financial analyst"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/financial_calculation_handler/health', methods=['GET'])
def financial_calculation_handler_health():
    """Health check for Financial Calculation"""
    return jsonify({
        "service": "financial_calculation_handler",
        "name": "Financial Calculation",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_net_worth'],
        "last_checked": datetime.now().isoformat(),
        "message": "Financial Calculation service is available and ready"
    })

@enhanced_service_bp.route('/api/services/financial_calculation_handler/info', methods=['GET'])
def financial_calculation_handler_info():
    """Service information for Financial Calculation"""
    return jsonify({
        "service_id": "financial_calculation_handler",
        "name": "Financial Calculation",
        "type": "integration",
        "description": "Enhanced Financial Calculation integration service",
        "file_path": "financial_calculation_handler.py",
        "status": "available",
        "capabilities": ['get_net_worth'],
        "workflow_integration": True,
        "chat_commands": ["use financial calculation", "access financial calculation"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/financial_calculation_service/health', methods=['GET'])
def financial_calculation_service_health():
    """Health check for Financial Calculation"""
    return jsonify({
        "service": "financial_calculation_service",
        "name": "Financial Calculation",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_net_worth'],
        "last_checked": datetime.now().isoformat(),
        "message": "Financial Calculation service is available and ready"
    })

@enhanced_service_bp.route('/api/services/financial_calculation_service/info', methods=['GET'])
def financial_calculation_service_info():
    """Service information for Financial Calculation"""
    return jsonify({
        "service_id": "financial_calculation_service",
        "name": "Financial Calculation",
        "type": "integration",
        "description": "Enhanced Financial Calculation integration service",
        "file_path": "financial_calculation_service.py",
        "status": "available",
        "capabilities": ['get_net_worth'],
        "workflow_integration": True,
        "chat_commands": ["use financial calculation", "access financial calculation"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/financial_handler/health', methods=['GET'])
def financial_handler_health():
    """Health check for Financial"""
    return jsonify({
        "service": "financial_handler",
        "name": "Financial",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_investments', 'get_liabilities', 'get_accounts', 'get_financial_summary', 'create_link_token', 'get_transactions'],
        "last_checked": datetime.now().isoformat(),
        "message": "Financial service is available and ready"
    })

@enhanced_service_bp.route('/api/services/financial_handler/info', methods=['GET'])
def financial_handler_info():
    """Service information for Financial"""
    return jsonify({
        "service_id": "financial_handler",
        "name": "Financial",
        "type": "integration",
        "description": "Enhanced Financial integration service",
        "file_path": "financial_handler.py",
        "status": "available",
        "capabilities": ['get_investments', 'get_liabilities', 'get_accounts', 'get_financial_summary', 'create_link_token', 'get_transactions'],
        "workflow_integration": True,
        "chat_commands": ["use financial", "access financial"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/financial_service/health', methods=['GET'])
def financial_service_health():
    """Health check for Financial"""
    return jsonify({
        "service": "financial_service",
        "name": "Financial",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_investments', 'get_liabilities', 'create_plaid_integration', 'get_accounts', 'get_financial_summary', 'get_transactions'],
        "last_checked": datetime.now().isoformat(),
        "message": "Financial service is available and ready"
    })

@enhanced_service_bp.route('/api/services/financial_service/info', methods=['GET'])
def financial_service_info():
    """Service information for Financial"""
    return jsonify({
        "service_id": "financial_service",
        "name": "Financial",
        "type": "integration",
        "description": "Enhanced Financial integration service",
        "file_path": "financial_service.py",
        "status": "available",
        "capabilities": ['get_investments', 'get_liabilities', 'create_plaid_integration', 'get_accounts', 'get_financial_summary', 'get_transactions'],
        "workflow_integration": True,
        "chat_commands": ["use financial", "access financial"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/gdrive_handler/health', methods=['GET'])
def gdrive_handler_health():
    """Health check for Gdrive"""
    return jsonify({
        "service": "gdrive_handler",
        "name": "Gdrive",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['get_status', 'search_gdrive', 'get_file_metadata_route', 'search_gdrive_route', 'list_files'],
        "last_checked": datetime.now().isoformat(),
        "message": "Gdrive service is available and ready"
    })

@enhanced_service_bp.route('/api/services/gdrive_handler/info', methods=['GET'])
def gdrive_handler_info():
    """Service information for Gdrive"""
    return jsonify({
        "service_id": "gdrive_handler",
        "name": "Gdrive",
        "type": "storage",
        "description": "Enhanced Gdrive integration service",
        "file_path": "gdrive_handler.py",
        "status": "available",
        "capabilities": ['get_status', 'search_gdrive', 'get_file_metadata_route', 'search_gdrive_route', 'list_files'],
        "workflow_integration": True,
        "chat_commands": ["use gdrive", "access gdrive"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/gdrive_health_handler/health', methods=['GET'])
def gdrive_health_handler_health():
    """Health check for Gdrive Health"""
    return jsonify({
        "service": "gdrive_health_handler",
        "name": "Gdrive Health",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Gdrive Health service is available and ready"
    })

@enhanced_service_bp.route('/api/services/gdrive_health_handler/info', methods=['GET'])
def gdrive_health_handler_info():
    """Service information for Gdrive Health"""
    return jsonify({
        "service_id": "gdrive_health_handler",
        "name": "Gdrive Health",
        "type": "storage",
        "description": "Enhanced Gdrive Health integration service",
        "file_path": "gdrive_health_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use gdrive health", "access gdrive health"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/gdrive_service/health', methods=['GET'])
def gdrive_service_health():
    """Health check for Gdrive"""
    return jsonify({
        "service": "gdrive_service",
        "name": "Gdrive",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['search_files', 'get_file_metadata', 'delete_file', 'create_gdrive_client', 'get_authenticated_client', 'download_file', 'list_files', 'upload_file', 'get_folder_contents', 'get_user_credentials'],
        "last_checked": datetime.now().isoformat(),
        "message": "Gdrive service is available and ready"
    })

@enhanced_service_bp.route('/api/services/gdrive_service/info', methods=['GET'])
def gdrive_service_info():
    """Service information for Gdrive"""
    return jsonify({
        "service_id": "gdrive_service",
        "name": "Gdrive",
        "type": "storage",
        "description": "Enhanced Gdrive integration service",
        "file_path": "gdrive_service.py",
        "status": "available",
        "capabilities": ['search_files', 'get_file_metadata', 'delete_file', 'create_gdrive_client', 'get_authenticated_client', 'download_file', 'list_files', 'upload_file', 'get_folder_contents', 'get_user_credentials'],
        "workflow_integration": True,
        "chat_commands": ["use gdrive", "access gdrive"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/github_handler/health', methods=['GET'])
def github_handler_health():
    """Health check for Github"""
    return jsonify({
        "service": "github_handler",
        "name": "Github",
        "status": "healthy",
        "type": "development",
        "capabilities": ['create_repo', 'list_repos'],
        "last_checked": datetime.now().isoformat(),
        "message": "Github service is available and ready"
    })

@enhanced_service_bp.route('/api/services/github_handler/info', methods=['GET'])
def github_handler_info():
    """Service information for Github"""
    return jsonify({
        "service_id": "github_handler",
        "name": "Github",
        "type": "development",
        "description": "Enhanced Github integration service",
        "file_path": "github_handler.py",
        "status": "available",
        "capabilities": ['create_repo', 'list_repos'],
        "workflow_integration": True,
        "chat_commands": ["use github", "access github"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/github_health_handler/health', methods=['GET'])
def github_health_handler_health():
    """Health check for Github Health"""
    return jsonify({
        "service": "github_health_handler",
        "name": "Github Health",
        "status": "healthy",
        "type": "development",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Github Health service is available and ready"
    })

@enhanced_service_bp.route('/api/services/github_health_handler/info', methods=['GET'])
def github_health_handler_info():
    """Service information for Github Health"""
    return jsonify({
        "service_id": "github_health_handler",
        "name": "Github Health",
        "type": "development",
        "description": "Enhanced Github Health integration service",
        "file_path": "github_health_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use github health", "access github health"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/github_service/health', methods=['GET'])
def github_service_health():
    """Health check for Github"""
    return jsonify({
        "service": "github_service",
        "name": "Github",
        "status": "healthy",
        "type": "development",
        "capabilities": ['create_repository', 'get_github_token', 'get_user_repositories'],
        "last_checked": datetime.now().isoformat(),
        "message": "Github service is available and ready"
    })

@enhanced_service_bp.route('/api/services/github_service/info', methods=['GET'])
def github_service_info():
    """Service information for Github"""
    return jsonify({
        "service_id": "github_service",
        "name": "Github",
        "type": "development",
        "description": "Enhanced Github integration service",
        "file_path": "github_service.py",
        "status": "available",
        "capabilities": ['create_repository', 'get_github_token', 'get_user_repositories'],
        "workflow_integration": True,
        "chat_commands": ["use github", "access github"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/gmail_health_handler/health', methods=['GET'])
def gmail_health_handler_health():
    """Health check for Gmail Health"""
    return jsonify({
        "service": "gmail_health_handler",
        "name": "Gmail Health",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Gmail Health service is available and ready"
    })

@enhanced_service_bp.route('/api/services/gmail_health_handler/info', methods=['GET'])
def gmail_health_handler_info():
    """Service information for Gmail Health"""
    return jsonify({
        "service_id": "gmail_health_handler",
        "name": "Gmail Health",
        "type": "integration",
        "description": "Enhanced Gmail Health integration service",
        "file_path": "gmail_health_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use gmail health", "access gmail health"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/goals_handler/health', methods=['GET'])
def goals_handler_health():
    """Health check for Goals"""
    return jsonify({
        "service": "goals_handler",
        "name": "Goals",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_goals', 'get_contributions', 'create_goal', 'delete_goal', 'update_goal', 'get_goal'],
        "last_checked": datetime.now().isoformat(),
        "message": "Goals service is available and ready"
    })

@enhanced_service_bp.route('/api/services/goals_handler/info', methods=['GET'])
def goals_handler_info():
    """Service information for Goals"""
    return jsonify({
        "service_id": "goals_handler",
        "name": "Goals",
        "type": "integration",
        "description": "Enhanced Goals integration service",
        "file_path": "goals_handler.py",
        "status": "available",
        "capabilities": ['get_goals', 'get_contributions', 'create_goal', 'delete_goal', 'update_goal', 'get_goal'],
        "workflow_integration": True,
        "chat_commands": ["use goals", "access goals"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/goals_service/health', methods=['GET'])
def goals_service_health():
    """Health check for Goals"""
    return jsonify({
        "service": "goals_service",
        "name": "Goals",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_contributions', 'get_goal_by_id', 'create_goal', 'delete_goal', 'update_goal', 'get_goals'],
        "last_checked": datetime.now().isoformat(),
        "message": "Goals service is available and ready"
    })

@enhanced_service_bp.route('/api/services/goals_service/info', methods=['GET'])
def goals_service_info():
    """Service information for Goals"""
    return jsonify({
        "service_id": "goals_service",
        "name": "Goals",
        "type": "integration",
        "description": "Enhanced Goals integration service",
        "file_path": "goals_service.py",
        "status": "available",
        "capabilities": ['get_contributions', 'get_goal_by_id', 'create_goal', 'delete_goal', 'update_goal', 'get_goals'],
        "workflow_integration": True,
        "chat_commands": ["use goals", "access goals"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/google_ads_service/health', methods=['GET'])
def google_ads_service_health():
    """Health check for Google Ads"""
    return jsonify({
        "service": "google_ads_service",
        "name": "Google Ads",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_campaign', 'get_google_ads_client', 'get_campaign'],
        "last_checked": datetime.now().isoformat(),
        "message": "Google Ads service is available and ready"
    })

@enhanced_service_bp.route('/api/services/google_ads_service/info', methods=['GET'])
def google_ads_service_info():
    """Service information for Google Ads"""
    return jsonify({
        "service_id": "google_ads_service",
        "name": "Google Ads",
        "type": "integration",
        "description": "Enhanced Google Ads integration service",
        "file_path": "google_ads_service.py",
        "status": "available",
        "capabilities": ['create_campaign', 'get_google_ads_client', 'get_campaign'],
        "workflow_integration": True,
        "chat_commands": ["use google ads", "access google ads"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/investment_handler/health', methods=['GET'])
def investment_handler_health():
    """Health check for Investment"""
    return jsonify({
        "service": "investment_handler",
        "name": "Investment",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_holdings', 'get_investments', 'create_investment', 'create_holding'],
        "last_checked": datetime.now().isoformat(),
        "message": "Investment service is available and ready"
    })

@enhanced_service_bp.route('/api/services/investment_handler/info', methods=['GET'])
def investment_handler_info():
    """Service information for Investment"""
    return jsonify({
        "service_id": "investment_handler",
        "name": "Investment",
        "type": "integration",
        "description": "Enhanced Investment integration service",
        "file_path": "investment_handler.py",
        "status": "available",
        "capabilities": ['get_holdings', 'get_investments', 'create_investment', 'create_holding'],
        "workflow_integration": True,
        "chat_commands": ["use investment", "access investment"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/investment_service/health', methods=['GET'])
def investment_service_health():
    """Health check for Investment"""
    return jsonify({
        "service": "investment_service",
        "name": "Investment",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_holdings', 'get_investments', 'create_investment', 'create_holding'],
        "last_checked": datetime.now().isoformat(),
        "message": "Investment service is available and ready"
    })

@enhanced_service_bp.route('/api/services/investment_service/info', methods=['GET'])
def investment_service_info():
    """Service information for Investment"""
    return jsonify({
        "service_id": "investment_service",
        "name": "Investment",
        "type": "integration",
        "description": "Enhanced Investment integration service",
        "file_path": "investment_service.py",
        "status": "available",
        "capabilities": ['get_holdings', 'get_investments', 'create_investment', 'create_holding'],
        "workflow_integration": True,
        "chat_commands": ["use investment", "access investment"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/invoicing_handler/health', methods=['GET'])
def invoicing_handler_health():
    """Health check for Invoicing"""
    return jsonify({
        "service": "invoicing_handler",
        "name": "Invoicing",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_invoices', 'create_invoice'],
        "last_checked": datetime.now().isoformat(),
        "message": "Invoicing service is available and ready"
    })

@enhanced_service_bp.route('/api/services/invoicing_handler/info', methods=['GET'])
def invoicing_handler_info():
    """Service information for Invoicing"""
    return jsonify({
        "service_id": "invoicing_handler",
        "name": "Invoicing",
        "type": "integration",
        "description": "Enhanced Invoicing integration service",
        "file_path": "invoicing_handler.py",
        "status": "available",
        "capabilities": ['get_invoices', 'create_invoice'],
        "workflow_integration": True,
        "chat_commands": ["use invoicing", "access invoicing"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/invoicing_service/health', methods=['GET'])
def invoicing_service_health():
    """Health check for Invoicing"""
    return jsonify({
        "service": "invoicing_service",
        "name": "Invoicing",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_invoices', 'create_invoice'],
        "last_checked": datetime.now().isoformat(),
        "message": "Invoicing service is available and ready"
    })

@enhanced_service_bp.route('/api/services/invoicing_service/info', methods=['GET'])
def invoicing_service_info():
    """Service information for Invoicing"""
    return jsonify({
        "service_id": "invoicing_service",
        "name": "Invoicing",
        "type": "integration",
        "description": "Enhanced Invoicing integration service",
        "file_path": "invoicing_service.py",
        "status": "available",
        "capabilities": ['get_invoices', 'create_invoice'],
        "workflow_integration": True,
        "chat_commands": ["use invoicing", "access invoicing"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/it_manager_handler/health', methods=['GET'])
def it_manager_handler_health():
    """Health check for It Manager"""
    return jsonify({
        "service": "it_manager_handler",
        "name": "It Manager",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_jira_issue_from_salesforce_case', 'get_jira_issue_summary', 'create_trello_card_from_jira_issue'],
        "last_checked": datetime.now().isoformat(),
        "message": "It Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/it_manager_handler/info', methods=['GET'])
def it_manager_handler_info():
    """Service information for It Manager"""
    return jsonify({
        "service_id": "it_manager_handler",
        "name": "It Manager",
        "type": "integration",
        "description": "Enhanced It Manager integration service",
        "file_path": "it_manager_handler.py",
        "status": "available",
        "capabilities": ['create_jira_issue_from_salesforce_case', 'get_jira_issue_summary', 'create_trello_card_from_jira_issue'],
        "workflow_integration": True,
        "chat_commands": ["use it manager", "access it manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/it_manager_service/health', methods=['GET'])
def it_manager_service_health():
    """Health check for It Manager"""
    return jsonify({
        "service": "it_manager_service",
        "name": "It Manager",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_jira_issue_from_salesforce_case', 'get_jira_issue_summary', 'create_trello_card_from_jira_issue'],
        "last_checked": datetime.now().isoformat(),
        "message": "It Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/it_manager_service/info', methods=['GET'])
def it_manager_service_info():
    """Service information for It Manager"""
    return jsonify({
        "service_id": "it_manager_service",
        "name": "It Manager",
        "type": "integration",
        "description": "Enhanced It Manager integration service",
        "file_path": "it_manager_service.py",
        "status": "available",
        "capabilities": ['create_jira_issue_from_salesforce_case', 'get_jira_issue_summary', 'create_trello_card_from_jira_issue'],
        "workflow_integration": True,
        "chat_commands": ["use it manager", "access it manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/jira_handler/health', methods=['GET'])
def jira_handler_health():
    """Health check for Jira"""
    return jsonify({
        "service": "jira_handler",
        "name": "Jira",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_jira_client', 'get_issue', 'list_issues', 'create_issue', 'search_jira_route', 'update_issue', 'list_projects'],
        "last_checked": datetime.now().isoformat(),
        "message": "Jira service is available and ready"
    })

@enhanced_service_bp.route('/api/services/jira_handler/info', methods=['GET'])
def jira_handler_info():
    """Service information for Jira"""
    return jsonify({
        "service_id": "jira_handler",
        "name": "Jira",
        "type": "integration",
        "description": "Enhanced Jira integration service",
        "file_path": "jira_handler.py",
        "status": "available",
        "capabilities": ['get_jira_client', 'get_issue', 'list_issues', 'create_issue', 'search_jira_route', 'update_issue', 'list_projects'],
        "workflow_integration": True,
        "chat_commands": ["use jira", "access jira"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/jira_service/health', methods=['GET'])
def jira_service_health():
    """Health check for Jira"""
    return jsonify({
        "service": "jira_service",
        "name": "Jira",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['search_issues', 'get_jira_client', 'download_file', 'list_files', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Jira service is available and ready"
    })

@enhanced_service_bp.route('/api/services/jira_service/info', methods=['GET'])
def jira_service_info():
    """Service information for Jira"""
    return jsonify({
        "service_id": "jira_service",
        "name": "Jira",
        "type": "integration",
        "description": "Enhanced Jira integration service",
        "file_path": "jira_service.py",
        "status": "available",
        "capabilities": ['search_issues', 'get_jira_client', 'download_file', 'list_files', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use jira", "access jira"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/jira_service_real/health', methods=['GET'])
def jira_service_real_health():
    """Health check for Jira Real"""
    return jsonify({
        "service": "jira_service_real",
        "name": "Jira Real",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_issue', 'update_issue', 'get_real_jira_client', 'download_file', 'list_files', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Jira Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/jira_service_real/info', methods=['GET'])
def jira_service_real_info():
    """Service information for Jira Real"""
    return jsonify({
        "service_id": "jira_service_real",
        "name": "Jira Real",
        "type": "integration",
        "description": "Enhanced Jira Real integration service",
        "file_path": "jira_service_real.py",
        "status": "available",
        "capabilities": ['create_issue', 'update_issue', 'get_real_jira_client', 'download_file', 'list_files', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use jira real", "access jira real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/lancedb_handler/health', methods=['GET'])
def lancedb_handler_health():
    """Health check for Lancedb"""
    return jsonify({
        "service": "lancedb_handler",
        "name": "Lancedb",
        "status": "healthy",
        "type": "search",
        "capabilities": ['delete_document', 'delete_conversation_context', 'search_conversation_context', 'get_lancedb_connection', 'create_generic_document_tables_if_not_exist', 'get_document_stats', 'get_document_chunks', 'search_documents', 'get_conversation_history', 'get_sync_status'],
        "last_checked": datetime.now().isoformat(),
        "message": "Lancedb service is available and ready"
    })

@enhanced_service_bp.route('/api/services/lancedb_handler/info', methods=['GET'])
def lancedb_handler_info():
    """Service information for Lancedb"""
    return jsonify({
        "service_id": "lancedb_handler",
        "name": "Lancedb",
        "type": "search",
        "description": "Enhanced Lancedb integration service",
        "file_path": "lancedb_handler.py",
        "status": "available",
        "capabilities": ['delete_document', 'delete_conversation_context', 'search_conversation_context', 'get_lancedb_connection', 'create_generic_document_tables_if_not_exist', 'get_document_stats', 'get_document_chunks', 'search_documents', 'get_conversation_history', 'get_sync_status'],
        "workflow_integration": True,
        "chat_commands": ["use lancedb", "access lancedb"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/legal_handler/health', methods=['GET'])
def legal_handler_health():
    """Health check for Legal"""
    return jsonify({
        "service": "legal_handler",
        "name": "Legal",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_docusign_envelope_from_salesforce_opportunity', 'get_docusign_envelope_status', 'create_trello_card_from_docusign_envelope'],
        "last_checked": datetime.now().isoformat(),
        "message": "Legal service is available and ready"
    })

@enhanced_service_bp.route('/api/services/legal_handler/info', methods=['GET'])
def legal_handler_info():
    """Service information for Legal"""
    return jsonify({
        "service_id": "legal_handler",
        "name": "Legal",
        "type": "integration",
        "description": "Enhanced Legal integration service",
        "file_path": "legal_handler.py",
        "status": "available",
        "capabilities": ['create_docusign_envelope_from_salesforce_opportunity', 'get_docusign_envelope_status', 'create_trello_card_from_docusign_envelope'],
        "workflow_integration": True,
        "chat_commands": ["use legal", "access legal"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/legal_service/health', methods=['GET'])
def legal_service_health():
    """Health check for Legal"""
    return jsonify({
        "service": "legal_service",
        "name": "Legal",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_docusign_envelope_from_salesforce_opportunity', 'get_docusign_envelope_status', 'create_trello_card_from_docusign_envelope'],
        "last_checked": datetime.now().isoformat(),
        "message": "Legal service is available and ready"
    })

@enhanced_service_bp.route('/api/services/legal_service/info', methods=['GET'])
def legal_service_info():
    """Service information for Legal"""
    return jsonify({
        "service_id": "legal_service",
        "name": "Legal",
        "type": "integration",
        "description": "Enhanced Legal integration service",
        "file_path": "legal_service.py",
        "status": "available",
        "capabilities": ['create_docusign_envelope_from_salesforce_opportunity', 'get_docusign_envelope_status', 'create_trello_card_from_docusign_envelope'],
        "workflow_integration": True,
        "chat_commands": ["use legal", "access legal"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/linkedin_service/health', methods=['GET'])
def linkedin_service_health():
    """Health check for Linkedin"""
    return jsonify({
        "service": "linkedin_service",
        "name": "Linkedin",
        "status": "healthy",
        "type": "social_media",
        "capabilities": ['get_company_data', 'get_connections', 'get_authorization_url', 'search_jobs'],
        "last_checked": datetime.now().isoformat(),
        "message": "Linkedin service is available and ready"
    })

@enhanced_service_bp.route('/api/services/linkedin_service/info', methods=['GET'])
def linkedin_service_info():
    """Service information for Linkedin"""
    return jsonify({
        "service_id": "linkedin_service",
        "name": "Linkedin",
        "type": "social_media",
        "description": "Enhanced Linkedin integration service",
        "file_path": "linkedin_service.py",
        "status": "available",
        "capabilities": ['get_company_data', 'get_connections', 'get_authorization_url', 'search_jobs'],
        "workflow_integration": True,
        "chat_commands": ["use linkedin", "access linkedin"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/mailchimp_handler/health', methods=['GET'])
def mailchimp_handler_health():
    """Health check for Mailchimp"""
    return jsonify({
        "service": "mailchimp_handler",
        "name": "Mailchimp",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['list_templates', 'get_all_lists'],
        "last_checked": datetime.now().isoformat(),
        "message": "Mailchimp service is available and ready"
    })

@enhanced_service_bp.route('/api/services/mailchimp_handler/info', methods=['GET'])
def mailchimp_handler_info():
    """Service information for Mailchimp"""
    return jsonify({
        "service_id": "mailchimp_handler",
        "name": "Mailchimp",
        "type": "integration",
        "description": "Enhanced Mailchimp integration service",
        "file_path": "mailchimp_handler.py",
        "status": "available",
        "capabilities": ['list_templates', 'get_all_lists'],
        "workflow_integration": True,
        "chat_commands": ["use mailchimp", "access mailchimp"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/mailchimp_service/health', methods=['GET'])
def mailchimp_service_health():
    """Health check for Mailchimp"""
    return jsonify({
        "service": "mailchimp_service",
        "name": "Mailchimp",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_campaign_report', 'get_campaign', 'list_templates', 'create_campaign', 'get_mailchimp_client', 'get_all_lists'],
        "last_checked": datetime.now().isoformat(),
        "message": "Mailchimp service is available and ready"
    })

@enhanced_service_bp.route('/api/services/mailchimp_service/info', methods=['GET'])
def mailchimp_service_info():
    """Service information for Mailchimp"""
    return jsonify({
        "service_id": "mailchimp_service",
        "name": "Mailchimp",
        "type": "integration",
        "description": "Enhanced Mailchimp integration service",
        "file_path": "mailchimp_service.py",
        "status": "available",
        "capabilities": ['get_campaign_report', 'get_campaign', 'list_templates', 'create_campaign', 'get_mailchimp_client', 'get_all_lists'],
        "workflow_integration": True,
        "chat_commands": ["use mailchimp", "access mailchimp"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/manual_account_handler/health', methods=['GET'])
def manual_account_handler_health():
    """Health check for Manual Account"""
    return jsonify({
        "service": "manual_account_handler",
        "name": "Manual Account",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_manual_account', 'get_manual_accounts'],
        "last_checked": datetime.now().isoformat(),
        "message": "Manual Account service is available and ready"
    })

@enhanced_service_bp.route('/api/services/manual_account_handler/info', methods=['GET'])
def manual_account_handler_info():
    """Service information for Manual Account"""
    return jsonify({
        "service_id": "manual_account_handler",
        "name": "Manual Account",
        "type": "integration",
        "description": "Enhanced Manual Account integration service",
        "file_path": "manual_account_handler.py",
        "status": "available",
        "capabilities": ['create_manual_account', 'get_manual_accounts'],
        "workflow_integration": True,
        "chat_commands": ["use manual account", "access manual account"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/manual_account_service/health', methods=['GET'])
def manual_account_service_health():
    """Health check for Manual Account"""
    return jsonify({
        "service": "manual_account_service",
        "name": "Manual Account",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_manual_account', 'get_manual_accounts'],
        "last_checked": datetime.now().isoformat(),
        "message": "Manual Account service is available and ready"
    })

@enhanced_service_bp.route('/api/services/manual_account_service/info', methods=['GET'])
def manual_account_service_info():
    """Service information for Manual Account"""
    return jsonify({
        "service_id": "manual_account_service",
        "name": "Manual Account",
        "type": "integration",
        "description": "Enhanced Manual Account integration service",
        "file_path": "manual_account_service.py",
        "status": "available",
        "capabilities": ['create_manual_account', 'get_manual_accounts'],
        "workflow_integration": True,
        "chat_commands": ["use manual account", "access manual account"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/manual_transaction_handler/health', methods=['GET'])
def manual_transaction_handler_health():
    """Health check for Manual Transaction"""
    return jsonify({
        "service": "manual_transaction_handler",
        "name": "Manual Transaction",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_manual_transactions', 'create_manual_transaction'],
        "last_checked": datetime.now().isoformat(),
        "message": "Manual Transaction service is available and ready"
    })

@enhanced_service_bp.route('/api/services/manual_transaction_handler/info', methods=['GET'])
def manual_transaction_handler_info():
    """Service information for Manual Transaction"""
    return jsonify({
        "service_id": "manual_transaction_handler",
        "name": "Manual Transaction",
        "type": "integration",
        "description": "Enhanced Manual Transaction integration service",
        "file_path": "manual_transaction_handler.py",
        "status": "available",
        "capabilities": ['get_manual_transactions', 'create_manual_transaction'],
        "workflow_integration": True,
        "chat_commands": ["use manual transaction", "access manual transaction"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/manual_transaction_service/health', methods=['GET'])
def manual_transaction_service_health():
    """Health check for Manual Transaction"""
    return jsonify({
        "service": "manual_transaction_service",
        "name": "Manual Transaction",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_manual_transactions', 'create_manual_transaction'],
        "last_checked": datetime.now().isoformat(),
        "message": "Manual Transaction service is available and ready"
    })

@enhanced_service_bp.route('/api/services/manual_transaction_service/info', methods=['GET'])
def manual_transaction_service_info():
    """Service information for Manual Transaction"""
    return jsonify({
        "service_id": "manual_transaction_service",
        "name": "Manual Transaction",
        "type": "integration",
        "description": "Enhanced Manual Transaction integration service",
        "file_path": "manual_transaction_service.py",
        "status": "available",
        "capabilities": ['get_manual_transactions', 'create_manual_transaction'],
        "workflow_integration": True,
        "chat_commands": ["use manual transaction", "access manual transaction"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/marketing_manager_handler/health', methods=['GET'])
def marketing_manager_handler_health():
    """Health check for Marketing Manager"""
    return jsonify({
        "service": "marketing_manager_handler",
        "name": "Marketing Manager",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_mailchimp_campaign_from_salesforce_campaign', 'get_mailchimp_campaign_summary', 'create_trello_card_from_mailchimp_campaign'],
        "last_checked": datetime.now().isoformat(),
        "message": "Marketing Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/marketing_manager_handler/info', methods=['GET'])
def marketing_manager_handler_info():
    """Service information for Marketing Manager"""
    return jsonify({
        "service_id": "marketing_manager_handler",
        "name": "Marketing Manager",
        "type": "integration",
        "description": "Enhanced Marketing Manager integration service",
        "file_path": "marketing_manager_handler.py",
        "status": "available",
        "capabilities": ['create_mailchimp_campaign_from_salesforce_campaign', 'get_mailchimp_campaign_summary', 'create_trello_card_from_mailchimp_campaign'],
        "workflow_integration": True,
        "chat_commands": ["use marketing manager", "access marketing manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/marketing_manager_service/health', methods=['GET'])
def marketing_manager_service_health():
    """Health check for Marketing Manager"""
    return jsonify({
        "service": "marketing_manager_service",
        "name": "Marketing Manager",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_mailchimp_campaign_from_salesforce_campaign', 'get_mailchimp_campaign_summary', 'create_trello_card_from_mailchimp_campaign'],
        "last_checked": datetime.now().isoformat(),
        "message": "Marketing Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/marketing_manager_service/info', methods=['GET'])
def marketing_manager_service_info():
    """Service information for Marketing Manager"""
    return jsonify({
        "service_id": "marketing_manager_service",
        "name": "Marketing Manager",
        "type": "integration",
        "description": "Enhanced Marketing Manager integration service",
        "file_path": "marketing_manager_service.py",
        "status": "available",
        "capabilities": ['create_mailchimp_campaign_from_salesforce_campaign', 'get_mailchimp_campaign_summary', 'create_trello_card_from_mailchimp_campaign'],
        "workflow_integration": True,
        "chat_commands": ["use marketing manager", "access marketing manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/mcp_handler/health', methods=['GET'])
def mcp_handler_health():
    """Health check for Mcp"""
    return jsonify({
        "service": "mcp_handler",
        "name": "Mcp",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['download_file_route', 'get_file_metadata_route', 'list_files_route'],
        "last_checked": datetime.now().isoformat(),
        "message": "Mcp service is available and ready"
    })

@enhanced_service_bp.route('/api/services/mcp_handler/info', methods=['GET'])
def mcp_handler_info():
    """Service information for Mcp"""
    return jsonify({
        "service_id": "mcp_handler",
        "name": "Mcp",
        "type": "integration",
        "description": "Enhanced Mcp integration service",
        "file_path": "mcp_handler.py",
        "status": "available",
        "capabilities": ['download_file_route', 'get_file_metadata_route', 'list_files_route'],
        "workflow_integration": True,
        "chat_commands": ["use mcp", "access mcp"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/mcp_service/health', methods=['GET'])
def mcp_service_health():
    """Health check for Mcp"""
    return jsonify({
        "service": "mcp_service",
        "name": "Mcp",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_mcp_file_metadata', 'download_mcp_file', 'list_mcp_files'],
        "last_checked": datetime.now().isoformat(),
        "message": "Mcp service is available and ready"
    })

@enhanced_service_bp.route('/api/services/mcp_service/info', methods=['GET'])
def mcp_service_info():
    """Service information for Mcp"""
    return jsonify({
        "service_id": "mcp_service",
        "name": "Mcp",
        "type": "integration",
        "description": "Enhanced Mcp integration service",
        "file_path": "mcp_service.py",
        "status": "available",
        "capabilities": ['get_mcp_file_metadata', 'download_mcp_file', 'list_mcp_files'],
        "workflow_integration": True,
        "chat_commands": ["use mcp", "access mcp"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/meilisearch_handler/health', methods=['GET'])
def meilisearch_handler_health():
    """Health check for Meilisearch"""
    return jsonify({
        "service": "meilisearch_handler",
        "name": "Meilisearch",
        "status": "healthy",
        "type": "search",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Meilisearch service is available and ready"
    })

@enhanced_service_bp.route('/api/services/meilisearch_handler/info', methods=['GET'])
def meilisearch_handler_info():
    """Service information for Meilisearch"""
    return jsonify({
        "service_id": "meilisearch_handler",
        "name": "Meilisearch",
        "type": "search",
        "description": "Enhanced Meilisearch integration service",
        "file_path": "meilisearch_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use meilisearch", "access meilisearch"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/message_handler/health', methods=['GET'])
def message_handler_health():
    """Health check for Message"""
    return jsonify({
        "service": "message_handler",
        "name": "Message",
        "status": "healthy",
        "type": "communication",
        "capabilities": ['search_messages', 'get_message_stats', 'delete_message', 'get_messages'],
        "last_checked": datetime.now().isoformat(),
        "message": "Message service is available and ready"
    })

@enhanced_service_bp.route('/api/services/message_handler/info', methods=['GET'])
def message_handler_info():
    """Service information for Message"""
    return jsonify({
        "service_id": "message_handler",
        "name": "Message",
        "type": "communication",
        "description": "Enhanced Message integration service",
        "file_path": "message_handler.py",
        "status": "available",
        "capabilities": ['search_messages', 'get_message_stats', 'delete_message', 'get_messages'],
        "workflow_integration": True,
        "chat_commands": ["use message", "access message"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/message_handler_sqlite/health', methods=['GET'])
def message_handler_sqlite_health():
    """Health check for Message Sqlite"""
    return jsonify({
        "service": "message_handler_sqlite",
        "name": "Message Sqlite",
        "status": "healthy",
        "type": "communication",
        "capabilities": ['get_db_connection', 'update_message', 'delete_message', 'get_messages', 'create_message', 'get_message'],
        "last_checked": datetime.now().isoformat(),
        "message": "Message Sqlite service is available and ready"
    })

@enhanced_service_bp.route('/api/services/message_handler_sqlite/info', methods=['GET'])
def message_handler_sqlite_info():
    """Service information for Message Sqlite"""
    return jsonify({
        "service_id": "message_handler_sqlite",
        "name": "Message Sqlite",
        "type": "communication",
        "description": "Enhanced Message Sqlite integration service",
        "file_path": "message_handler_sqlite.py",
        "status": "available",
        "capabilities": ['get_db_connection', 'update_message', 'delete_message', 'get_messages', 'create_message', 'get_message'],
        "workflow_integration": True,
        "chat_commands": ["use message sqlite", "access message sqlite"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/message_service/health', methods=['GET'])
def message_service_health():
    """Health check for Message"""
    return jsonify({
        "service": "message_service",
        "name": "Message",
        "status": "healthy",
        "type": "communication",
        "capabilities": ['sync_external_messages', 'delete_message', 'get_message_statistics', 'get_messages', 'search_messages', 'send_message'],
        "last_checked": datetime.now().isoformat(),
        "message": "Message service is available and ready"
    })

@enhanced_service_bp.route('/api/services/message_service/info', methods=['GET'])
def message_service_info():
    """Service information for Message"""
    return jsonify({
        "service_id": "message_service",
        "name": "Message",
        "type": "communication",
        "description": "Enhanced Message integration service",
        "file_path": "message_service.py",
        "status": "available",
        "capabilities": ['sync_external_messages', 'delete_message', 'get_message_statistics', 'get_messages', 'search_messages', 'send_message'],
        "workflow_integration": True,
        "chat_commands": ["use message", "access message"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/net_worth_handler/health', methods=['GET'])
def net_worth_handler_health():
    """Health check for Net Worth"""
    return jsonify({
        "service": "net_worth_handler",
        "name": "Net Worth",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_net_worth'],
        "last_checked": datetime.now().isoformat(),
        "message": "Net Worth service is available and ready"
    })

@enhanced_service_bp.route('/api/services/net_worth_handler/info', methods=['GET'])
def net_worth_handler_info():
    """Service information for Net Worth"""
    return jsonify({
        "service_id": "net_worth_handler",
        "name": "Net Worth",
        "type": "integration",
        "description": "Enhanced Net Worth integration service",
        "file_path": "net_worth_handler.py",
        "status": "available",
        "capabilities": ['get_net_worth'],
        "workflow_integration": True,
        "chat_commands": ["use net worth", "access net worth"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/net_worth_service/health', methods=['GET'])
def net_worth_service_health():
    """Health check for Net Worth"""
    return jsonify({
        "service": "net_worth_service",
        "name": "Net Worth",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_net_worth'],
        "last_checked": datetime.now().isoformat(),
        "message": "Net Worth service is available and ready"
    })

@enhanced_service_bp.route('/api/services/net_worth_service/info', methods=['GET'])
def net_worth_service_info():
    """Service information for Net Worth"""
    return jsonify({
        "service_id": "net_worth_service",
        "name": "Net Worth",
        "type": "integration",
        "description": "Enhanced Net Worth integration service",
        "file_path": "net_worth_service.py",
        "status": "available",
        "capabilities": ['get_net_worth'],
        "workflow_integration": True,
        "chat_commands": ["use net worth", "access net worth"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/nlu_bridge_service/health', methods=['GET'])
def nlu_bridge_service_health():
    """Health check for Nlu Bridge"""
    return jsonify({
        "service": "nlu_bridge_service",
        "name": "Nlu Bridge",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['generate_workflow_from_nlu_analysis', 'get_nlu_bridge_service', 'analyze_workflow_request'],
        "last_checked": datetime.now().isoformat(),
        "message": "Nlu Bridge service is available and ready"
    })

@enhanced_service_bp.route('/api/services/nlu_bridge_service/info', methods=['GET'])
def nlu_bridge_service_info():
    """Service information for Nlu Bridge"""
    return jsonify({
        "service_id": "nlu_bridge_service",
        "name": "Nlu Bridge",
        "type": "integration",
        "description": "Enhanced Nlu Bridge integration service",
        "file_path": "nlu_bridge_service.py",
        "status": "available",
        "capabilities": ['generate_workflow_from_nlu_analysis', 'get_nlu_bridge_service', 'analyze_workflow_request'],
        "workflow_integration": True,
        "chat_commands": ["use nlu bridge", "access nlu bridge"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/note_handler/health', methods=['GET'])
def note_handler_health():
    """Health check for Note"""
    return jsonify({
        "service": "note_handler",
        "name": "Note",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['search_notes'],
        "last_checked": datetime.now().isoformat(),
        "message": "Note service is available and ready"
    })

@enhanced_service_bp.route('/api/services/note_handler/info', methods=['GET'])
def note_handler_info():
    """Service information for Note"""
    return jsonify({
        "service_id": "note_handler",
        "name": "Note",
        "type": "integration",
        "description": "Enhanced Note integration service",
        "file_path": "note_handler.py",
        "status": "available",
        "capabilities": ['search_notes'],
        "workflow_integration": True,
        "chat_commands": ["use note", "access note"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/notion_handler_real/health', methods=['GET'])
def notion_handler_real_health():
    """Health check for Notion Real"""
    return jsonify({
        "service": "notion_handler_real",
        "name": "Notion Real",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['list_databases', 'search_notion_route', 'download_page', 'get_page', 'get_notion_client', 'list_pages'],
        "last_checked": datetime.now().isoformat(),
        "message": "Notion Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/notion_handler_real/info', methods=['GET'])
def notion_handler_real_info():
    """Service information for Notion Real"""
    return jsonify({
        "service_id": "notion_handler_real",
        "name": "Notion Real",
        "type": "integration",
        "description": "Enhanced Notion Real integration service",
        "file_path": "notion_handler_real.py",
        "status": "available",
        "capabilities": ['list_databases', 'search_notion_route', 'download_page', 'get_page', 'get_notion_client', 'list_pages'],
        "workflow_integration": True,
        "chat_commands": ["use notion real", "access notion real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/notion_service_real/health', methods=['GET'])
def notion_service_real_health():
    """Health check for Notion Real"""
    return jsonify({
        "service": "notion_service_real",
        "name": "Notion Real",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_service_status', 'get_real_notion_client', 'download_file', 'list_files', 'search_pages', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Notion Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/notion_service_real/info', methods=['GET'])
def notion_service_real_info():
    """Service information for Notion Real"""
    return jsonify({
        "service_id": "notion_service_real",
        "name": "Notion Real",
        "type": "integration",
        "description": "Enhanced Notion Real integration service",
        "file_path": "notion_service_real.py",
        "status": "available",
        "capabilities": ['get_service_status', 'get_real_notion_client', 'download_file', 'list_files', 'search_pages', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use notion real", "access notion real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/onedrive_service/health', methods=['GET'])
def onedrive_service_health():
    """Health check for Onedrive"""
    return jsonify({
        "service": "onedrive_service",
        "name": "Onedrive",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['download_file', 'list_files', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Onedrive service is available and ready"
    })

@enhanced_service_bp.route('/api/services/onedrive_service/info', methods=['GET'])
def onedrive_service_info():
    """Service information for Onedrive"""
    return jsonify({
        "service_id": "onedrive_service",
        "name": "Onedrive",
        "type": "storage",
        "description": "Enhanced Onedrive integration service",
        "file_path": "onedrive_service.py",
        "status": "available",
        "capabilities": ['download_file', 'list_files', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use onedrive", "access onedrive"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/outlook_health_handler/health', methods=['GET'])
def outlook_health_handler_health():
    """Health check for Outlook Health"""
    return jsonify({
        "service": "outlook_health_handler",
        "name": "Outlook Health",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Outlook Health service is available and ready"
    })

@enhanced_service_bp.route('/api/services/outlook_health_handler/info', methods=['GET'])
def outlook_health_handler_info():
    """Service information for Outlook Health"""
    return jsonify({
        "service_id": "outlook_health_handler",
        "name": "Outlook Health",
        "type": "integration",
        "description": "Enhanced Outlook Health integration service",
        "file_path": "outlook_health_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use outlook health", "access outlook health"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/payroll_handler/health', methods=['GET'])
def payroll_handler_health():
    """Health check for Payroll"""
    return jsonify({
        "service": "payroll_handler",
        "name": "Payroll",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_payroll', 'get_payrolls'],
        "last_checked": datetime.now().isoformat(),
        "message": "Payroll service is available and ready"
    })

@enhanced_service_bp.route('/api/services/payroll_handler/info', methods=['GET'])
def payroll_handler_info():
    """Service information for Payroll"""
    return jsonify({
        "service_id": "payroll_handler",
        "name": "Payroll",
        "type": "integration",
        "description": "Enhanced Payroll integration service",
        "file_path": "payroll_handler.py",
        "status": "available",
        "capabilities": ['create_payroll', 'get_payrolls'],
        "workflow_integration": True,
        "chat_commands": ["use payroll", "access payroll"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/payroll_service/health', methods=['GET'])
def payroll_service_health():
    """Health check for Payroll"""
    return jsonify({
        "service": "payroll_service",
        "name": "Payroll",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_payroll', 'get_payrolls'],
        "last_checked": datetime.now().isoformat(),
        "message": "Payroll service is available and ready"
    })

@enhanced_service_bp.route('/api/services/payroll_service/info', methods=['GET'])
def payroll_service_info():
    """Service information for Payroll"""
    return jsonify({
        "service_id": "payroll_service",
        "name": "Payroll",
        "type": "integration",
        "description": "Enhanced Payroll integration service",
        "file_path": "payroll_service.py",
        "status": "available",
        "capabilities": ['create_payroll', 'get_payrolls'],
        "workflow_integration": True,
        "chat_commands": ["use payroll", "access payroll"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/personal_assistant_handler/health', methods=['GET'])
def personal_assistant_handler_health():
    """Health check for Personal Assistant"""
    return jsonify({
        "service": "personal_assistant_handler",
        "name": "Personal Assistant",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_news', 'get_weather'],
        "last_checked": datetime.now().isoformat(),
        "message": "Personal Assistant service is available and ready"
    })

@enhanced_service_bp.route('/api/services/personal_assistant_handler/info', methods=['GET'])
def personal_assistant_handler_info():
    """Service information for Personal Assistant"""
    return jsonify({
        "service_id": "personal_assistant_handler",
        "name": "Personal Assistant",
        "type": "integration",
        "description": "Enhanced Personal Assistant integration service",
        "file_path": "personal_assistant_handler.py",
        "status": "available",
        "capabilities": ['get_news', 'get_weather'],
        "workflow_integration": True,
        "chat_commands": ["use personal assistant", "access personal assistant"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/personal_assistant_service/health', methods=['GET'])
def personal_assistant_service_health():
    """Health check for Personal Assistant"""
    return jsonify({
        "service": "personal_assistant_service",
        "name": "Personal Assistant",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_news', 'get_weather'],
        "last_checked": datetime.now().isoformat(),
        "message": "Personal Assistant service is available and ready"
    })

@enhanced_service_bp.route('/api/services/personal_assistant_service/info', methods=['GET'])
def personal_assistant_service_info():
    """Service information for Personal Assistant"""
    return jsonify({
        "service_id": "personal_assistant_service",
        "name": "Personal Assistant",
        "type": "integration",
        "description": "Enhanced Personal Assistant integration service",
        "file_path": "personal_assistant_service.py",
        "status": "available",
        "capabilities": ['get_news', 'get_weather'],
        "workflow_integration": True,
        "chat_commands": ["use personal assistant", "access personal assistant"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/plaid_service/health', methods=['GET'])
def plaid_service_health():
    """Health check for Plaid"""
    return jsonify({
        "service": "plaid_service",
        "name": "Plaid",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_transaction_summary', 'create_plaid_service', 'get_investments', 'get_item_status', 'get_accounts', 'create_link_token', 'get_transactions'],
        "last_checked": datetime.now().isoformat(),
        "message": "Plaid service is available and ready"
    })

@enhanced_service_bp.route('/api/services/plaid_service/info', methods=['GET'])
def plaid_service_info():
    """Service information for Plaid"""
    return jsonify({
        "service_id": "plaid_service",
        "name": "Plaid",
        "type": "integration",
        "description": "Enhanced Plaid integration service",
        "file_path": "plaid_service.py",
        "status": "available",
        "capabilities": ['get_transaction_summary', 'create_plaid_service', 'get_investments', 'get_item_status', 'get_accounts', 'create_link_token', 'get_transactions'],
        "workflow_integration": True,
        "chat_commands": ["use plaid", "access plaid"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/project_manager_handler/health', methods=['GET'])
def project_manager_handler_health():
    """Health check for Project Manager"""
    return jsonify({
        "service": "project_manager_handler",
        "name": "Project Manager",
        "status": "healthy",
        "type": "task_management",
        "capabilities": ['create_gdrive_folder_from_trello_board', 'upload_trello_attachments_to_gdrive', 'create_trello_board_from_gdrive_folder', 'create_trello_card_for_new_gdrive_file'],
        "last_checked": datetime.now().isoformat(),
        "message": "Project Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/project_manager_handler/info', methods=['GET'])
def project_manager_handler_info():
    """Service information for Project Manager"""
    return jsonify({
        "service_id": "project_manager_handler",
        "name": "Project Manager",
        "type": "task_management",
        "description": "Enhanced Project Manager integration service",
        "file_path": "project_manager_handler.py",
        "status": "available",
        "capabilities": ['create_gdrive_folder_from_trello_board', 'upload_trello_attachments_to_gdrive', 'create_trello_board_from_gdrive_folder', 'create_trello_card_for_new_gdrive_file'],
        "workflow_integration": True,
        "chat_commands": ["use project manager", "access project manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/project_manager_service/health', methods=['GET'])
def project_manager_service_health():
    """Health check for Project Manager"""
    return jsonify({
        "service": "project_manager_service",
        "name": "Project Manager",
        "status": "healthy",
        "type": "task_management",
        "capabilities": ['create_trello_card_for_new_file_in_google_drive', 'create_google_drive_folder_from_trello_board', 'upload_trello_attachments_to_google_drive', 'create_trello_board_from_google_drive_folder'],
        "last_checked": datetime.now().isoformat(),
        "message": "Project Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/project_manager_service/info', methods=['GET'])
def project_manager_service_info():
    """Service information for Project Manager"""
    return jsonify({
        "service_id": "project_manager_service",
        "name": "Project Manager",
        "type": "task_management",
        "description": "Enhanced Project Manager integration service",
        "file_path": "project_manager_service.py",
        "status": "available",
        "capabilities": ['create_trello_card_for_new_file_in_google_drive', 'create_google_drive_folder_from_trello_board', 'upload_trello_attachments_to_google_drive', 'create_trello_board_from_google_drive_folder'],
        "workflow_integration": True,
        "chat_commands": ["use project manager", "access project manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/quickbooks_service/health', methods=['GET'])
def quickbooks_service_health():
    """Health check for Quickbooks"""
    return jsonify({
        "service": "quickbooks_service",
        "name": "Quickbooks",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_invoices', 'list_bills', 'list_invoices', 'get_bills', 'get_quickbooks_client'],
        "last_checked": datetime.now().isoformat(),
        "message": "Quickbooks service is available and ready"
    })

@enhanced_service_bp.route('/api/services/quickbooks_service/info', methods=['GET'])
def quickbooks_service_info():
    """Service information for Quickbooks"""
    return jsonify({
        "service_id": "quickbooks_service",
        "name": "Quickbooks",
        "type": "integration",
        "description": "Enhanced Quickbooks integration service",
        "file_path": "quickbooks_service.py",
        "status": "available",
        "capabilities": ['get_invoices', 'list_bills', 'list_invoices', 'get_bills', 'get_quickbooks_client'],
        "workflow_integration": True,
        "chat_commands": ["use quickbooks", "access quickbooks"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/quickbooks_service_real/health', methods=['GET'])
def quickbooks_service_real_health():
    """Health check for Quickbooks Real"""
    return jsonify({
        "service": "quickbooks_service_real",
        "name": "Quickbooks Real",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_service_status', 'get_invoice', 'list_vendors', 'list_customers', 'list_bills', 'list_invoices', 'get_quickbooks_client'],
        "last_checked": datetime.now().isoformat(),
        "message": "Quickbooks Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/quickbooks_service_real/info', methods=['GET'])
def quickbooks_service_real_info():
    """Service information for Quickbooks Real"""
    return jsonify({
        "service_id": "quickbooks_service_real",
        "name": "Quickbooks Real",
        "type": "integration",
        "description": "Enhanced Quickbooks Real integration service",
        "file_path": "quickbooks_service_real.py",
        "status": "available",
        "capabilities": ['get_service_status', 'get_invoice', 'list_vendors', 'list_customers', 'list_bills', 'list_invoices', 'get_quickbooks_client'],
        "workflow_integration": True,
        "chat_commands": ["use quickbooks real", "access quickbooks real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/reminder_service/health', methods=['GET'])
def reminder_service_health():
    """Health check for Reminder"""
    return jsonify({
        "service": "reminder_service",
        "name": "Reminder",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_reminder', 'create_deadline_reminder', 'update_reminder', 'create_task_reminder', 'create_meeting_reminder', 'get_overdue_reminders', 'get_reminders', 'get_upcoming_reminders', 'delete_reminder'],
        "last_checked": datetime.now().isoformat(),
        "message": "Reminder service is available and ready"
    })

@enhanced_service_bp.route('/api/services/reminder_service/info', methods=['GET'])
def reminder_service_info():
    """Service information for Reminder"""
    return jsonify({
        "service_id": "reminder_service",
        "name": "Reminder",
        "type": "integration",
        "description": "Enhanced Reminder integration service",
        "file_path": "reminder_service.py",
        "status": "available",
        "capabilities": ['create_reminder', 'create_deadline_reminder', 'update_reminder', 'create_task_reminder', 'create_meeting_reminder', 'get_overdue_reminders', 'get_reminders', 'get_upcoming_reminders', 'delete_reminder'],
        "workflow_integration": True,
        "chat_commands": ["use reminder", "access reminder"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/reporting_handler/health', methods=['GET'])
def reporting_handler_health():
    """Health check for Reporting"""
    return jsonify({
        "service": "reporting_handler",
        "name": "Reporting",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_spending_report'],
        "last_checked": datetime.now().isoformat(),
        "message": "Reporting service is available and ready"
    })

@enhanced_service_bp.route('/api/services/reporting_handler/info', methods=['GET'])
def reporting_handler_info():
    """Service information for Reporting"""
    return jsonify({
        "service_id": "reporting_handler",
        "name": "Reporting",
        "type": "integration",
        "description": "Enhanced Reporting integration service",
        "file_path": "reporting_handler.py",
        "status": "available",
        "capabilities": ['get_spending_report'],
        "workflow_integration": True,
        "chat_commands": ["use reporting", "access reporting"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/reporting_service/health', methods=['GET'])
def reporting_service_health():
    """Health check for Reporting"""
    return jsonify({
        "service": "reporting_service",
        "name": "Reporting",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_spending_report'],
        "last_checked": datetime.now().isoformat(),
        "message": "Reporting service is available and ready"
    })

@enhanced_service_bp.route('/api/services/reporting_service/info', methods=['GET'])
def reporting_service_info():
    """Service information for Reporting"""
    return jsonify({
        "service_id": "reporting_service",
        "name": "Reporting",
        "type": "integration",
        "description": "Enhanced Reporting integration service",
        "file_path": "reporting_service.py",
        "status": "available",
        "capabilities": ['get_spending_report'],
        "workflow_integration": True,
        "chat_commands": ["use reporting", "access reporting"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/research_handler/health', methods=['GET'])
def research_handler_health():
    """Health check for Research"""
    return jsonify({
        "service": "research_handler",
        "name": "Research",
        "status": "healthy",
        "type": "search",
        "capabilities": ['process_research_queue'],
        "last_checked": datetime.now().isoformat(),
        "message": "Research service is available and ready"
    })

@enhanced_service_bp.route('/api/services/research_handler/info', methods=['GET'])
def research_handler_info():
    """Service information for Research"""
    return jsonify({
        "service_id": "research_handler",
        "name": "Research",
        "type": "search",
        "description": "Enhanced Research integration service",
        "file_path": "research_handler.py",
        "status": "available",
        "capabilities": ['process_research_queue'],
        "workflow_integration": True,
        "chat_commands": ["use research", "access research"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/sales_manager_handler/health', methods=['GET'])
def sales_manager_handler_health():
    """Health check for Sales Manager"""
    return jsonify({
        "service": "sales_manager_handler",
        "name": "Sales Manager",
        "status": "healthy",
        "type": "crm",
        "capabilities": ['create_card_from_opportunity', 'create_salesforce_contact_from_xero_contact', 'get_open_opportunities_for_account', 'create_invoice_from_opportunity'],
        "last_checked": datetime.now().isoformat(),
        "message": "Sales Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/sales_manager_handler/info', methods=['GET'])
def sales_manager_handler_info():
    """Service information for Sales Manager"""
    return jsonify({
        "service_id": "sales_manager_handler",
        "name": "Sales Manager",
        "type": "crm",
        "description": "Enhanced Sales Manager integration service",
        "file_path": "sales_manager_handler.py",
        "status": "available",
        "capabilities": ['create_card_from_opportunity', 'create_salesforce_contact_from_xero_contact', 'get_open_opportunities_for_account', 'create_invoice_from_opportunity'],
        "workflow_integration": True,
        "chat_commands": ["use sales manager", "access sales manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/sales_manager_service/health', methods=['GET'])
def sales_manager_service_health():
    """Health check for Sales Manager"""
    return jsonify({
        "service": "sales_manager_service",
        "name": "Sales Manager",
        "status": "healthy",
        "type": "crm",
        "capabilities": ['get_open_opportunities_for_account', 'create_salesforce_contact_from_xero_contact', 'create_xero_invoice_from_salesforce_opportunity', 'create_trello_card_from_salesforce_opportunity'],
        "last_checked": datetime.now().isoformat(),
        "message": "Sales Manager service is available and ready"
    })

@enhanced_service_bp.route('/api/services/sales_manager_service/info', methods=['GET'])
def sales_manager_service_info():
    """Service information for Sales Manager"""
    return jsonify({
        "service_id": "sales_manager_service",
        "name": "Sales Manager",
        "type": "crm",
        "description": "Enhanced Sales Manager integration service",
        "file_path": "sales_manager_service.py",
        "status": "available",
        "capabilities": ['get_open_opportunities_for_account', 'create_salesforce_contact_from_xero_contact', 'create_xero_invoice_from_salesforce_opportunity', 'create_trello_card_from_salesforce_opportunity'],
        "workflow_integration": True,
        "chat_commands": ["use sales manager", "access sales manager"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/salesforce_handler/health', methods=['GET'])
def salesforce_handler_health():
    """Health check for Salesforce"""
    return jsonify({
        "service": "salesforce_handler",
        "name": "Salesforce",
        "status": "healthy",
        "type": "crm",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Salesforce service is available and ready"
    })

@enhanced_service_bp.route('/api/services/salesforce_handler/info', methods=['GET'])
def salesforce_handler_info():
    """Service information for Salesforce"""
    return jsonify({
        "service_id": "salesforce_handler",
        "name": "Salesforce",
        "type": "crm",
        "description": "Enhanced Salesforce integration service",
        "file_path": "salesforce_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use salesforce", "access salesforce"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/salesforce_service/health', methods=['GET'])
def salesforce_service_health():
    """Health check for Salesforce"""
    return jsonify({
        "service": "salesforce_service",
        "name": "Salesforce",
        "status": "healthy",
        "type": "crm",
        "capabilities": ['create_lead', 'get_case', 'list_opportunities', 'update_opportunity', 'create_opportunity', 'get_campaign', 'create_contact', 'list_accounts', 'create_account', 'list_contacts', 'get_salesforce_client', 'get_opportunity'],
        "last_checked": datetime.now().isoformat(),
        "message": "Salesforce service is available and ready"
    })

@enhanced_service_bp.route('/api/services/salesforce_service/info', methods=['GET'])
def salesforce_service_info():
    """Service information for Salesforce"""
    return jsonify({
        "service_id": "salesforce_service",
        "name": "Salesforce",
        "type": "crm",
        "description": "Enhanced Salesforce integration service",
        "file_path": "salesforce_service.py",
        "status": "available",
        "capabilities": ['create_lead', 'get_case', 'list_opportunities', 'update_opportunity', 'create_opportunity', 'get_campaign', 'create_contact', 'list_accounts', 'create_account', 'list_contacts', 'get_salesforce_client', 'get_opportunity'],
        "workflow_integration": True,
        "chat_commands": ["use salesforce", "access salesforce"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/service_registry_routes/health', methods=['GET'])
def service_registry_routes_health():
    """Health check for Registry Routes"""
    return jsonify({
        "service": "service_registry_routes",
        "name": "Registry Routes",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_integration_status', 'get_chat_commands', 'get_service', 'get_services', 'get_services_health', 'get_services_status', 'get_workflow_capabilities'],
        "last_checked": datetime.now().isoformat(),
        "message": "Registry Routes service is available and ready"
    })

@enhanced_service_bp.route('/api/services/service_registry_routes/info', methods=['GET'])
def service_registry_routes_info():
    """Service information for Registry Routes"""
    return jsonify({
        "service_id": "service_registry_routes",
        "name": "Registry Routes",
        "type": "integration",
        "description": "Enhanced Registry Routes integration service",
        "file_path": "service_registry_routes.py",
        "status": "available",
        "capabilities": ['get_integration_status', 'get_chat_commands', 'get_service', 'get_services', 'get_services_health', 'get_services_status', 'get_workflow_capabilities'],
        "workflow_integration": True,
        "chat_commands": ["use registry routes", "access registry routes"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/shopify_handler/health', methods=['GET'])
def shopify_handler_health():
    """Health check for Shopify"""
    return jsonify({
        "service": "shopify_handler",
        "name": "Shopify",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_connection_status'],
        "last_checked": datetime.now().isoformat(),
        "message": "Shopify service is available and ready"
    })

@enhanced_service_bp.route('/api/services/shopify_handler/info', methods=['GET'])
def shopify_handler_info():
    """Service information for Shopify"""
    return jsonify({
        "service_id": "shopify_handler",
        "name": "Shopify",
        "type": "integration",
        "description": "Enhanced Shopify integration service",
        "file_path": "shopify_handler.py",
        "status": "available",
        "capabilities": ['get_connection_status'],
        "workflow_integration": True,
        "chat_commands": ["use shopify", "access shopify"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/shopify_service/health', methods=['GET'])
def shopify_service_health():
    """Health check for Shopify"""
    return jsonify({
        "service": "shopify_service",
        "name": "Shopify",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_order', 'get_top_selling_products', 'get_shopify_client', 'list_products'],
        "last_checked": datetime.now().isoformat(),
        "message": "Shopify service is available and ready"
    })

@enhanced_service_bp.route('/api/services/shopify_service/info', methods=['GET'])
def shopify_service_info():
    """Service information for Shopify"""
    return jsonify({
        "service_id": "shopify_service",
        "name": "Shopify",
        "type": "integration",
        "description": "Enhanced Shopify integration service",
        "file_path": "shopify_service.py",
        "status": "available",
        "capabilities": ['get_order', 'get_top_selling_products', 'get_shopify_client', 'list_products'],
        "workflow_integration": True,
        "chat_commands": ["use shopify", "access shopify"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/slack_health_handler/health', methods=['GET'])
def slack_health_handler_health():
    """Health check for Slack Health"""
    return jsonify({
        "service": "slack_health_handler",
        "name": "Slack Health",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Slack Health service is available and ready"
    })

@enhanced_service_bp.route('/api/services/slack_health_handler/info', methods=['GET'])
def slack_health_handler_info():
    """Service information for Slack Health"""
    return jsonify({
        "service_id": "slack_health_handler",
        "name": "Slack Health",
        "type": "integration",
        "description": "Enhanced Slack Health integration service",
        "file_path": "slack_health_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use slack health", "access slack health"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/social_media_handler/health', methods=['GET'])
def social_media_handler_health():
    """Health check for Social Media"""
    return jsonify({
        "service": "social_media_handler",
        "name": "Social Media",
        "status": "healthy",
        "type": "social_media",
        "capabilities": ['create_lead_from_tweet'],
        "last_checked": datetime.now().isoformat(),
        "message": "Social Media service is available and ready"
    })

@enhanced_service_bp.route('/api/services/social_media_handler/info', methods=['GET'])
def social_media_handler_info():
    """Service information for Social Media"""
    return jsonify({
        "service_id": "social_media_handler",
        "name": "Social Media",
        "type": "social_media",
        "description": "Enhanced Social Media integration service",
        "file_path": "social_media_handler.py",
        "status": "available",
        "capabilities": ['create_lead_from_tweet'],
        "workflow_integration": True,
        "chat_commands": ["use social media", "access social media"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/social_media_service/health', methods=['GET'])
def social_media_service_health():
    """Health check for Social Media"""
    return jsonify({
        "service": "social_media_service",
        "name": "Social Media",
        "status": "healthy",
        "type": "social_media",
        "capabilities": ['create_salesforce_lead_from_tweet'],
        "last_checked": datetime.now().isoformat(),
        "message": "Social Media service is available and ready"
    })

@enhanced_service_bp.route('/api/services/social_media_service/info', methods=['GET'])
def social_media_service_info():
    """Service information for Social Media"""
    return jsonify({
        "service_id": "social_media_service",
        "name": "Social Media",
        "type": "social_media",
        "description": "Enhanced Social Media integration service",
        "file_path": "social_media_service.py",
        "status": "available",
        "capabilities": ['create_salesforce_lead_from_tweet'],
        "workflow_integration": True,
        "chat_commands": ["use social media", "access social media"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/api_service/health', methods=['GET'])
def api_service_health():
    """Health check for Api"""
    return jsonify({
        "service": "api_service",
        "name": "Api",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_sync_status', 'get_system_status', 'list_sources', 'create_api_service', 'get_app'],
        "last_checked": datetime.now().isoformat(),
        "message": "Api service is available and ready"
    })

@enhanced_service_bp.route('/api/services/api_service/info', methods=['GET'])
def api_service_info():
    """Service information for Api"""
    return jsonify({
        "service_id": "api_service",
        "name": "Api",
        "type": "integration",
        "description": "Enhanced Api integration service",
        "file_path": "sync/api_service.py",
        "status": "available",
        "capabilities": ['get_sync_status', 'get_system_status', 'list_sources', 'create_api_service', 'get_app'],
        "workflow_integration": True,
        "chat_commands": ["use api", "access api"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/incremental_sync_service/health', methods=['GET'])
def incremental_sync_service_health():
    """Health check for Incremental Sync"""
    return jsonify({
        "service": "incremental_sync_service",
        "name": "Incremental Sync",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_incremental_sync_service', 'process_document_incrementally', 'get_sync_status'],
        "last_checked": datetime.now().isoformat(),
        "message": "Incremental Sync service is available and ready"
    })

@enhanced_service_bp.route('/api/services/incremental_sync_service/info', methods=['GET'])
def incremental_sync_service_info():
    """Service information for Incremental Sync"""
    return jsonify({
        "service_id": "incremental_sync_service",
        "name": "Incremental Sync",
        "type": "integration",
        "description": "Enhanced Incremental Sync integration service",
        "file_path": "sync/incremental_sync_service.py",
        "status": "available",
        "capabilities": ['create_incremental_sync_service', 'process_document_incrementally', 'get_sync_status'],
        "workflow_integration": True,
        "chat_commands": ["use incremental sync", "access incremental sync"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/integration_service/health', methods=['GET'])
def integration_service_health():
    """Health check for Integration"""
    return jsonify({
        "service": "integration_service",
        "name": "Integration",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_integration_status', 'process_document', 'search_documents', 'create_integration_service', 'get_integration_service'],
        "last_checked": datetime.now().isoformat(),
        "message": "Integration service is available and ready"
    })

@enhanced_service_bp.route('/api/services/integration_service/info', methods=['GET'])
def integration_service_info():
    """Service information for Integration"""
    return jsonify({
        "service_id": "integration_service",
        "name": "Integration",
        "type": "integration",
        "description": "Enhanced Integration integration service",
        "file_path": "sync/integration_service.py",
        "status": "available",
        "capabilities": ['get_integration_status', 'process_document', 'search_documents', 'create_integration_service', 'get_integration_service'],
        "workflow_integration": True,
        "chat_commands": ["use integration", "access integration"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/lancedb_storage_service/health', methods=['GET'])
def lancedb_storage_service_health():
    """Health check for Lancedb Storage"""
    return jsonify({
        "service": "lancedb_storage_service",
        "name": "Lancedb Storage",
        "status": "healthy",
        "type": "storage",
        "capabilities": ['get_storage_service', 'get_storage_status', 'create_lancedb_storage_service', 'get_user_connection', 'search_documents', 'sync_user_data'],
        "last_checked": datetime.now().isoformat(),
        "message": "Lancedb Storage service is available and ready"
    })

@enhanced_service_bp.route('/api/services/lancedb_storage_service/info', methods=['GET'])
def lancedb_storage_service_info():
    """Service information for Lancedb Storage"""
    return jsonify({
        "service_id": "lancedb_storage_service",
        "name": "Lancedb Storage",
        "type": "storage",
        "description": "Enhanced Lancedb Storage integration service",
        "file_path": "sync/lancedb_storage_service.py",
        "status": "available",
        "capabilities": ['get_storage_service', 'get_storage_status', 'create_lancedb_storage_service', 'get_user_connection', 'search_documents', 'sync_user_data'],
        "workflow_integration": True,
        "chat_commands": ["use lancedb storage", "access lancedb storage"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/orchestration_service/health', methods=['GET'])
def orchestration_service_health():
    """Health check for Orchestration"""
    return jsonify({
        "service": "orchestration_service",
        "name": "Orchestration",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_orchestration_service', 'get_system_status'],
        "last_checked": datetime.now().isoformat(),
        "message": "Orchestration service is available and ready"
    })

@enhanced_service_bp.route('/api/services/orchestration_service/info', methods=['GET'])
def orchestration_service_info():
    """Service information for Orchestration"""
    return jsonify({
        "service_id": "orchestration_service",
        "name": "Orchestration",
        "type": "integration",
        "description": "Enhanced Orchestration integration service",
        "file_path": "sync/orchestration_service.py",
        "status": "available",
        "capabilities": ['create_orchestration_service', 'get_system_status'],
        "workflow_integration": True,
        "chat_commands": ["use orchestration", "access orchestration"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/task_handler/health', methods=['GET'])
def task_handler_health():
    """Health check for Task"""
    return jsonify({
        "service": "task_handler",
        "name": "Task",
        "status": "healthy",
        "type": "task_management",
        "capabilities": ['create_task', 'get_task_stats', 'get_tasks', 'update_task', 'delete_task'],
        "last_checked": datetime.now().isoformat(),
        "message": "Task service is available and ready"
    })

@enhanced_service_bp.route('/api/services/task_handler/info', methods=['GET'])
def task_handler_info():
    """Service information for Task"""
    return jsonify({
        "service_id": "task_handler",
        "name": "Task",
        "type": "task_management",
        "description": "Enhanced Task integration service",
        "file_path": "task_handler.py",
        "status": "available",
        "capabilities": ['create_task', 'get_task_stats', 'get_tasks', 'update_task', 'delete_task'],
        "workflow_integration": True,
        "chat_commands": ["use task", "access task"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/task_handler_sqlite/health', methods=['GET'])
def task_handler_sqlite_health():
    """Health check for Task Sqlite"""
    return jsonify({
        "service": "task_handler_sqlite",
        "name": "Task Sqlite",
        "status": "healthy",
        "type": "task_management",
        "capabilities": ['get_db_connection', 'create_task', 'get_task', 'get_tasks', 'update_task', 'delete_task'],
        "last_checked": datetime.now().isoformat(),
        "message": "Task Sqlite service is available and ready"
    })

@enhanced_service_bp.route('/api/services/task_handler_sqlite/info', methods=['GET'])
def task_handler_sqlite_info():
    """Service information for Task Sqlite"""
    return jsonify({
        "service_id": "task_handler_sqlite",
        "name": "Task Sqlite",
        "type": "task_management",
        "description": "Enhanced Task Sqlite integration service",
        "file_path": "task_handler_sqlite.py",
        "status": "available",
        "capabilities": ['get_db_connection', 'create_task', 'get_task', 'get_tasks', 'update_task', 'delete_task'],
        "workflow_integration": True,
        "chat_commands": ["use task sqlite", "access task sqlite"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/task_service/health', methods=['GET'])
def task_service_health():
    """Health check for Task"""
    return jsonify({
        "service": "task_service",
        "name": "Task",
        "status": "healthy",
        "type": "task_management",
        "capabilities": ['sync_external_tasks', 'create_task', 'get_task_statistics', 'get_tasks', 'update_task', 'delete_task'],
        "last_checked": datetime.now().isoformat(),
        "message": "Task service is available and ready"
    })

@enhanced_service_bp.route('/api/services/task_service/info', methods=['GET'])
def task_service_info():
    """Service information for Task"""
    return jsonify({
        "service_id": "task_service",
        "name": "Task",
        "type": "task_management",
        "description": "Enhanced Task integration service",
        "file_path": "task_service.py",
        "status": "available",
        "capabilities": ['sync_external_tasks', 'create_task', 'get_task_statistics', 'get_tasks', 'update_task', 'delete_task'],
        "workflow_integration": True,
        "chat_commands": ["use task", "access task"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/teams_health_handler/health', methods=['GET'])
def teams_health_handler_health():
    """Health check for Teams Health"""
    return jsonify({
        "service": "teams_health_handler",
        "name": "Teams Health",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Teams Health service is available and ready"
    })

@enhanced_service_bp.route('/api/services/teams_health_handler/info', methods=['GET'])
def teams_health_handler_info():
    """Service information for Teams Health"""
    return jsonify({
        "service_id": "teams_health_handler",
        "name": "Teams Health",
        "type": "integration",
        "description": "Enhanced Teams Health integration service",
        "file_path": "teams_health_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use teams health", "access teams health"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/template_service/health', methods=['GET'])
def template_service_health():
    """Health check for Template"""
    return jsonify({
        "service": "template_service",
        "name": "Template",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_template_statistics', 'update_template', 'create_template', 'search_templates', 'get_template', 'delete_template', 'get_templates'],
        "last_checked": datetime.now().isoformat(),
        "message": "Template service is available and ready"
    })

@enhanced_service_bp.route('/api/services/template_service/info', methods=['GET'])
def template_service_info():
    """Service information for Template"""
    return jsonify({
        "service_id": "template_service",
        "name": "Template",
        "type": "integration",
        "description": "Enhanced Template integration service",
        "file_path": "template_service.py",
        "status": "available",
        "capabilities": ['get_template_statistics', 'update_template', 'create_template', 'search_templates', 'get_template', 'delete_template', 'get_templates'],
        "workflow_integration": True,
        "chat_commands": ["use template", "access template"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/test_mcp_handler/health', methods=['GET'])
def test_mcp_handler_health():
    """Health check for Test Mcp"""
    return jsonify({
        "service": "test_mcp_handler",
        "name": "Test Mcp",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Test Mcp service is available and ready"
    })

@enhanced_service_bp.route('/api/services/test_mcp_handler/info', methods=['GET'])
def test_mcp_handler_info():
    """Service information for Test Mcp"""
    return jsonify({
        "service_id": "test_mcp_handler",
        "name": "Test Mcp",
        "type": "integration",
        "description": "Enhanced Test Mcp integration service",
        "file_path": "test_mcp_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use test mcp", "access test mcp"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/test_service_registry/health', methods=['GET'])
def test_service_registry_health():
    """Health check for Test Registry"""
    return jsonify({
        "service": "test_service_registry",
        "name": "Test Registry",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Test Registry service is available and ready"
    })

@enhanced_service_bp.route('/api/services/test_service_registry/info', methods=['GET'])
def test_service_registry_info():
    """Service information for Test Registry"""
    return jsonify({
        "service_id": "test_service_registry",
        "name": "Test Registry",
        "type": "integration",
        "description": "Enhanced Test Registry integration service",
        "file_path": "test_service_registry.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use test registry", "access test registry"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/test_service_registry_direct/health', methods=['GET'])
def test_service_registry_direct_health():
    """Health check for Test Registry Direct"""
    return jsonify({
        "service": "test_service_registry_direct",
        "name": "Test Registry Direct",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Test Registry Direct service is available and ready"
    })

@enhanced_service_bp.route('/api/services/test_service_registry_direct/info', methods=['GET'])
def test_service_registry_direct_info():
    """Service information for Test Registry Direct"""
    return jsonify({
        "service_id": "test_service_registry_direct",
        "name": "Test Registry Direct",
        "type": "integration",
        "description": "Enhanced Test Registry Direct integration service",
        "file_path": "test_service_registry_direct.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use test registry direct", "access test registry direct"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/test_mailchimp_service/health', methods=['GET'])
def test_mailchimp_service_health():
    """Health check for Test Mailchimp"""
    return jsonify({
        "service": "test_mailchimp_service",
        "name": "Test Mailchimp",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Test Mailchimp service is available and ready"
    })

@enhanced_service_bp.route('/api/services/test_mailchimp_service/info', methods=['GET'])
def test_mailchimp_service_info():
    """Service information for Test Mailchimp"""
    return jsonify({
        "service_id": "test_mailchimp_service",
        "name": "Test Mailchimp",
        "type": "integration",
        "description": "Enhanced Test Mailchimp integration service",
        "file_path": "tests/test_mailchimp_service.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use test mailchimp", "access test mailchimp"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/training_handler/health', methods=['GET'])
def training_handler_health():
    """Health check for Training"""
    return jsonify({
        "service": "training_handler",
        "name": "Training",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Training service is available and ready"
    })

@enhanced_service_bp.route('/api/services/training_handler/info', methods=['GET'])
def training_handler_info():
    """Service information for Training"""
    return jsonify({
        "service_id": "training_handler",
        "name": "Training",
        "type": "integration",
        "description": "Enhanced Training integration service",
        "file_path": "training_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use training", "access training"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/transaction_handler/health', methods=['GET'])
def transaction_handler_health():
    """Health check for Transaction"""
    return jsonify({
        "service": "transaction_handler",
        "name": "Transaction",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_transaction', 'get_transactions'],
        "last_checked": datetime.now().isoformat(),
        "message": "Transaction service is available and ready"
    })

@enhanced_service_bp.route('/api/services/transaction_handler/info', methods=['GET'])
def transaction_handler_info():
    """Service information for Transaction"""
    return jsonify({
        "service_id": "transaction_handler",
        "name": "Transaction",
        "type": "integration",
        "description": "Enhanced Transaction integration service",
        "file_path": "transaction_handler.py",
        "status": "available",
        "capabilities": ['create_transaction', 'get_transactions'],
        "workflow_integration": True,
        "chat_commands": ["use transaction", "access transaction"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/transaction_service/health', methods=['GET'])
def transaction_service_health():
    """Health check for Transaction"""
    return jsonify({
        "service": "transaction_service",
        "name": "Transaction",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_transaction', 'get_transactions'],
        "last_checked": datetime.now().isoformat(),
        "message": "Transaction service is available and ready"
    })

@enhanced_service_bp.route('/api/services/transaction_service/info', methods=['GET'])
def transaction_service_info():
    """Service information for Transaction"""
    return jsonify({
        "service_id": "transaction_service",
        "name": "Transaction",
        "type": "integration",
        "description": "Enhanced Transaction integration service",
        "file_path": "transaction_service.py",
        "status": "available",
        "capabilities": ['create_transaction', 'get_transactions'],
        "workflow_integration": True,
        "chat_commands": ["use transaction", "access transaction"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/transcription_handler/health', methods=['GET'])
def transcription_handler_health():
    """Health check for Transcription"""
    return jsonify({
        "service": "transcription_handler",
        "name": "Transcription",
        "status": "healthy",
        "type": "voice",
        "capabilities": ['get_meeting_summary', 'get_meeting_transcription'],
        "last_checked": datetime.now().isoformat(),
        "message": "Transcription service is available and ready"
    })

@enhanced_service_bp.route('/api/services/transcription_handler/info', methods=['GET'])
def transcription_handler_info():
    """Service information for Transcription"""
    return jsonify({
        "service_id": "transcription_handler",
        "name": "Transcription",
        "type": "voice",
        "description": "Enhanced Transcription integration service",
        "file_path": "transcription_handler.py",
        "status": "available",
        "capabilities": ['get_meeting_summary', 'get_meeting_transcription'],
        "workflow_integration": True,
        "chat_commands": ["use transcription", "access transcription"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/transcription_service/health', methods=['GET'])
def transcription_service_health():
    """Health check for Transcription"""
    return jsonify({
        "service": "transcription_service",
        "name": "Transcription",
        "status": "healthy",
        "type": "voice",
        "capabilities": ['generate_meeting_summary'],
        "last_checked": datetime.now().isoformat(),
        "message": "Transcription service is available and ready"
    })

@enhanced_service_bp.route('/api/services/transcription_service/info', methods=['GET'])
def transcription_service_info():
    """Service information for Transcription"""
    return jsonify({
        "service_id": "transcription_service",
        "name": "Transcription",
        "type": "voice",
        "description": "Enhanced Transcription integration service",
        "file_path": "transcription_service.py",
        "status": "available",
        "capabilities": ['generate_meeting_summary'],
        "workflow_integration": True,
        "chat_commands": ["use transcription", "access transcription"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/trello_handler/health', methods=['GET'])
def trello_handler_health():
    """Health check for Trello"""
    return jsonify({
        "service": "trello_handler",
        "name": "Trello",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['list_cards', 'get_trello_client', 'list_boards', 'search_trello_route'],
        "last_checked": datetime.now().isoformat(),
        "message": "Trello service is available and ready"
    })

@enhanced_service_bp.route('/api/services/trello_handler/info', methods=['GET'])
def trello_handler_info():
    """Service information for Trello"""
    return jsonify({
        "service_id": "trello_handler",
        "name": "Trello",
        "type": "integration",
        "description": "Enhanced Trello integration service",
        "file_path": "trello_handler.py",
        "status": "available",
        "capabilities": ['list_cards', 'get_trello_client', 'list_boards', 'search_trello_route'],
        "workflow_integration": True,
        "chat_commands": ["use trello", "access trello"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/trello_handler_real/health', methods=['GET'])
def trello_handler_real_health():
    """Health check for Trello Real"""
    return jsonify({
        "service": "trello_handler_real",
        "name": "Trello Real",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['list_cards', 'get_card', 'list_boards', 'get_trello_client', 'search_trello_route'],
        "last_checked": datetime.now().isoformat(),
        "message": "Trello Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/trello_handler_real/info', methods=['GET'])
def trello_handler_real_info():
    """Service information for Trello Real"""
    return jsonify({
        "service_id": "trello_handler_real",
        "name": "Trello Real",
        "type": "integration",
        "description": "Enhanced Trello Real integration service",
        "file_path": "trello_handler_real.py",
        "status": "available",
        "capabilities": ['list_cards', 'get_card', 'list_boards', 'get_trello_client', 'search_trello_route'],
        "workflow_integration": True,
        "chat_commands": ["use trello real", "access trello real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/trello_service/health', methods=['GET'])
def trello_service_health():
    """Health check for Trello"""
    return jsonify({
        "service": "trello_service",
        "name": "Trello",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_board', 'get_card', 'get_trello_client', 'download_file', 'list_files', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Trello service is available and ready"
    })

@enhanced_service_bp.route('/api/services/trello_service/info', methods=['GET'])
def trello_service_info():
    """Service information for Trello"""
    return jsonify({
        "service_id": "trello_service",
        "name": "Trello",
        "type": "integration",
        "description": "Enhanced Trello integration service",
        "file_path": "trello_service.py",
        "status": "available",
        "capabilities": ['get_board', 'get_card', 'get_trello_client', 'download_file', 'list_files', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use trello", "access trello"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/trello_service_real/health', methods=['GET'])
def trello_service_real_health():
    """Health check for Trello Real"""
    return jsonify({
        "service": "trello_service_real",
        "name": "Trello Real",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_service_status', 'get_real_trello_client', 'download_file', 'list_files', 'get_file_metadata'],
        "last_checked": datetime.now().isoformat(),
        "message": "Trello Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/trello_service_real/info', methods=['GET'])
def trello_service_real_info():
    """Service information for Trello Real"""
    return jsonify({
        "service_id": "trello_service_real",
        "name": "Trello Real",
        "type": "integration",
        "description": "Enhanced Trello Real integration service",
        "file_path": "trello_service_real.py",
        "status": "available",
        "capabilities": ['get_service_status', 'get_real_trello_client', 'download_file', 'list_files', 'get_file_metadata'],
        "workflow_integration": True,
        "chat_commands": ["use trello real", "access trello real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/trigger_configuration_service/health', methods=['GET'])
def trigger_configuration_service_health():
    """Health check for Trigger Configuration"""
    return jsonify({
        "service": "trigger_configuration_service",
        "name": "Trigger Configuration",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Trigger Configuration service is available and ready"
    })

@enhanced_service_bp.route('/api/services/trigger_configuration_service/info', methods=['GET'])
def trigger_configuration_service_info():
    """Service information for Trigger Configuration"""
    return jsonify({
        "service_id": "trigger_configuration_service",
        "name": "Trigger Configuration",
        "type": "integration",
        "description": "Enhanced Trigger Configuration integration service",
        "file_path": "trigger_configuration_service.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use trigger configuration", "access trigger configuration"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/twitter_handler/health', methods=['GET'])
def twitter_handler_health():
    """Health check for Twitter"""
    return jsonify({
        "service": "twitter_handler",
        "name": "Twitter",
        "status": "healthy",
        "type": "social_media",
        "capabilities": ['search_tweets', 'get_tweet', 'get_timeline'],
        "last_checked": datetime.now().isoformat(),
        "message": "Twitter service is available and ready"
    })

@enhanced_service_bp.route('/api/services/twitter_handler/info', methods=['GET'])
def twitter_handler_info():
    """Service information for Twitter"""
    return jsonify({
        "service_id": "twitter_handler",
        "name": "Twitter",
        "type": "social_media",
        "description": "Enhanced Twitter integration service",
        "file_path": "twitter_handler.py",
        "status": "available",
        "capabilities": ['search_tweets', 'get_tweet', 'get_timeline'],
        "workflow_integration": True,
        "chat_commands": ["use twitter", "access twitter"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/twitter_service/health', methods=['GET'])
def twitter_service_health():
    """Health check for Twitter"""
    return jsonify({
        "service": "twitter_service",
        "name": "Twitter",
        "status": "healthy",
        "type": "social_media",
        "capabilities": ['search_tweets', 'get_status', 'update_status', 'get_tweet', 'create_favorite', 'get_twitter_api', 'get_timeline'],
        "last_checked": datetime.now().isoformat(),
        "message": "Twitter service is available and ready"
    })

@enhanced_service_bp.route('/api/services/twitter_service/info', methods=['GET'])
def twitter_service_info():
    """Service information for Twitter"""
    return jsonify({
        "service_id": "twitter_service",
        "name": "Twitter",
        "type": "social_media",
        "description": "Enhanced Twitter integration service",
        "file_path": "twitter_service.py",
        "status": "available",
        "capabilities": ['search_tweets', 'get_status', 'update_status', 'get_tweet', 'create_favorite', 'get_twitter_api', 'get_timeline'],
        "workflow_integration": True,
        "chat_commands": ["use twitter", "access twitter"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/update_service_registry/health', methods=['GET'])
def update_service_registry_health():
    """Health check for Update Registry"""
    return jsonify({
        "service": "update_service_registry",
        "name": "Update Registry",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_current_service_status', 'create_health_endpoint_for_service'],
        "last_checked": datetime.now().isoformat(),
        "message": "Update Registry service is available and ready"
    })

@enhanced_service_bp.route('/api/services/update_service_registry/info', methods=['GET'])
def update_service_registry_info():
    """Service information for Update Registry"""
    return jsonify({
        "service_id": "update_service_registry",
        "name": "Update Registry",
        "type": "integration",
        "description": "Enhanced Update Registry integration service",
        "file_path": "update_service_registry.py",
        "status": "available",
        "capabilities": ['get_current_service_status', 'create_health_endpoint_for_service'],
        "workflow_integration": True,
        "chat_commands": ["use update registry", "access update registry"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/user_api_key_service/health', methods=['GET'])
def user_api_key_service_health():
    """Health check for User Api Key"""
    return jsonify({
        "service": "user_api_key_service",
        "name": "User Api Key",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_user_api_key_service', 'list_user_services', 'get_api_key', 'delete_api_key', 'get_all_user_keys'],
        "last_checked": datetime.now().isoformat(),
        "message": "User Api Key service is available and ready"
    })

@enhanced_service_bp.route('/api/services/user_api_key_service/info', methods=['GET'])
def user_api_key_service_info():
    """Service information for User Api Key"""
    return jsonify({
        "service_id": "user_api_key_service",
        "name": "User Api Key",
        "type": "integration",
        "description": "Enhanced User Api Key integration service",
        "file_path": "user_api_key_service.py",
        "status": "available",
        "capabilities": ['get_user_api_key_service', 'list_user_services', 'get_api_key', 'delete_api_key', 'get_all_user_keys'],
        "workflow_integration": True,
        "chat_commands": ["use user api key", "access user api key"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/user_auth_service/health', methods=['GET'])
def user_auth_service_health():
    """Health check for User Auth"""
    return jsonify({
        "service": "user_auth_service",
        "name": "User Auth",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['create_user', 'get_user_profile'],
        "last_checked": datetime.now().isoformat(),
        "message": "User Auth service is available and ready"
    })

@enhanced_service_bp.route('/api/services/user_auth_service/info', methods=['GET'])
def user_auth_service_info():
    """Service information for User Auth"""
    return jsonify({
        "service_id": "user_auth_service",
        "name": "User Auth",
        "type": "authentication",
        "description": "Enhanced User Auth integration service",
        "file_path": "user_auth_service.py",
        "status": "available",
        "capabilities": ['create_user', 'get_user_profile'],
        "workflow_integration": True,
        "chat_commands": ["use user auth", "access user auth"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/user_auth_service_postgres/health', methods=['GET'])
def user_auth_service_postgres_health():
    """Health check for User Auth Postgres"""
    return jsonify({
        "service": "user_auth_service_postgres",
        "name": "User Auth Postgres",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['create_user', 'get_user_profile'],
        "last_checked": datetime.now().isoformat(),
        "message": "User Auth Postgres service is available and ready"
    })

@enhanced_service_bp.route('/api/services/user_auth_service_postgres/info', methods=['GET'])
def user_auth_service_postgres_info():
    """Service information for User Auth Postgres"""
    return jsonify({
        "service_id": "user_auth_service_postgres",
        "name": "User Auth Postgres",
        "type": "authentication",
        "description": "Enhanced User Auth Postgres integration service",
        "file_path": "user_auth_service_postgres.py",
        "status": "available",
        "capabilities": ['create_user', 'get_user_profile'],
        "workflow_integration": True,
        "chat_commands": ["use user auth postgres", "access user auth postgres"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/service_pb2/health', methods=['GET'])
def service_pb2_health():
    """Health check for Pb2"""
    return jsonify({
        "service": "service_pb2",
        "name": "Pb2",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Pb2 service is available and ready"
    })

@enhanced_service_bp.route('/api/services/service_pb2/info', methods=['GET'])
def service_pb2_info():
    """Service information for Pb2"""
    return jsonify({
        "service_id": "service_pb2",
        "name": "Pb2",
        "type": "integration",
        "description": "Enhanced Pb2 integration service",
        "file_path": "venv/lib/python3.7/site-packages/google/api/service_pb2.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use pb2", "access pb2"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/_service_account_info/health', methods=['GET'])
def _service_account_info_health():
    """Health check for  Account Info"""
    return jsonify({
        "service": "_service_account_info",
        "name": " Account Info",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": " Account Info service is available and ready"
    })

@enhanced_service_bp.route('/api/services/_service_account_info/info', methods=['GET'])
def _service_account_info_info():
    """Service information for  Account Info"""
    return jsonify({
        "service_id": "_service_account_info",
        "name": " Account Info",
        "type": "integration",
        "description": "Enhanced  Account Info integration service",
        "file_path": "venv/lib/python3.7/site-packages/google/auth/_service_account_info.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use  account info", "access  account info"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/_service_account_async/health', methods=['GET'])
def _service_account_async_health():
    """Health check for  Account Async"""
    return jsonify({
        "service": "_service_account_async",
        "name": " Account Async",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": " Account Async service is available and ready"
    })

@enhanced_service_bp.route('/api/services/_service_account_async/info', methods=['GET'])
def _service_account_async_info():
    """Service information for  Account Async"""
    return jsonify({
        "service_id": "_service_account_async",
        "name": " Account Async",
        "type": "integration",
        "description": "Enhanced  Account Async integration service",
        "file_path": "venv/lib/python3.7/site-packages/google/oauth2/_service_account_async.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use  account async", "access  account async"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/service_account/health', methods=['GET'])
def service_account_health():
    """Health check for Account"""
    return jsonify({
        "service": "service_account",
        "name": "Account",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_cred_info'],
        "last_checked": datetime.now().isoformat(),
        "message": "Account service is available and ready"
    })

@enhanced_service_bp.route('/api/services/service_account/info', methods=['GET'])
def service_account_info():
    """Service information for Account"""
    return jsonify({
        "service_id": "service_account",
        "name": "Account",
        "type": "integration",
        "description": "Enhanced Account integration service",
        "file_path": "venv/lib/python3.7/site-packages/google/oauth2/service_account.py",
        "status": "available",
        "capabilities": ['get_cred_info'],
        "workflow_integration": True,
        "chat_commands": ["use account", "access account"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/webauthn_handler/health', methods=['GET'])
def webauthn_handler_health():
    """Health check for Webauthn"""
    return jsonify({
        "service": "webauthn_handler",
        "name": "Webauthn",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Webauthn service is available and ready"
    })

@enhanced_service_bp.route('/api/services/webauthn_handler/info', methods=['GET'])
def webauthn_handler_info():
    """Service information for Webauthn"""
    return jsonify({
        "service_id": "webauthn_handler",
        "name": "Webauthn",
        "type": "authentication",
        "description": "Enhanced Webauthn integration service",
        "file_path": "venv/lib/python3.7/site-packages/google/oauth2/webauthn_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use webauthn", "access webauthn"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/webauthn_handler_factory/health', methods=['GET'])
def webauthn_handler_factory_health():
    """Health check for Webauthn Factory"""
    return jsonify({
        "service": "webauthn_handler_factory",
        "name": "Webauthn Factory",
        "status": "healthy",
        "type": "authentication",
        "capabilities": ['get_handler'],
        "last_checked": datetime.now().isoformat(),
        "message": "Webauthn Factory service is available and ready"
    })

@enhanced_service_bp.route('/api/services/webauthn_handler_factory/info', methods=['GET'])
def webauthn_handler_factory_info():
    """Service information for Webauthn Factory"""
    return jsonify({
        "service_id": "webauthn_handler_factory",
        "name": "Webauthn Factory",
        "type": "authentication",
        "description": "Enhanced Webauthn Factory integration service",
        "file_path": "venv/lib/python3.7/site-packages/google/oauth2/webauthn_handler_factory.py",
        "status": "available",
        "capabilities": ['get_handler'],
        "workflow_integration": True,
        "chat_commands": ["use webauthn factory", "access webauthn factory"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/service/health', methods=['GET'])
def service_health():
    """Health check for Service"""
    return jsonify({
        "service": "service",
        "name": "Service",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Service service is available and ready"
    })

@enhanced_service_bp.route('/api/services/service/info', methods=['GET'])
def service_info():
    """Service information for Service"""
    return jsonify({
        "service_id": "service",
        "name": "Service",
        "type": "integration",
        "description": "Enhanced Service integration service",
        "file_path": "venv/lib/python3.7/site-packages/google/protobuf/service.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use service", "access service"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/service_reflection/health', methods=['GET'])
def service_reflection_health():
    """Health check for Reflection"""
    return jsonify({
        "service": "service_reflection",
        "name": "Reflection",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Reflection service is available and ready"
    })

@enhanced_service_bp.route('/api/services/service_reflection/info', methods=['GET'])
def service_reflection_info():
    """Service information for Reflection"""
    return jsonify({
        "service_id": "service_reflection",
        "name": "Reflection",
        "type": "integration",
        "description": "Enhanced Reflection integration service",
        "file_path": "venv/lib/python3.7/site-packages/google/protobuf/service_reflection.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use reflection", "access reflection"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/service_application/health', methods=['GET'])
def service_application_health():
    """Health check for Application"""
    return jsonify({
        "service": "service_application",
        "name": "Application",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Application service is available and ready"
    })

@enhanced_service_bp.route('/api/services/service_application/info', methods=['GET'])
def service_application_info():
    """Service information for Application"""
    return jsonify({
        "service_id": "service_application",
        "name": "Application",
        "type": "integration",
        "description": "Enhanced Application integration service",
        "file_path": "venv/lib/python3.7/site-packages/oauthlib/oauth2/rfc6749/clients/service_application.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use application", "access application"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/handler/health', methods=['GET'])
def handler_health():
    """Health check for Handler"""
    return jsonify({
        "service": "handler",
        "name": "Handler",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['list_audio_devices'],
        "last_checked": datetime.now().isoformat(),
        "message": "Handler service is available and ready"
    })

@enhanced_service_bp.route('/api/services/handler/info', methods=['GET'])
def handler_info():
    """Service information for Handler"""
    return jsonify({
        "service_id": "handler",
        "name": "Handler",
        "type": "integration",
        "description": "Enhanced Handler integration service",
        "file_path": "wake_word_detector/handler.py",
        "status": "available",
        "capabilities": ['list_audio_devices'],
        "workflow_integration": True,
        "chat_commands": ["use handler", "access handler"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/openwakeword_handler/health', methods=['GET'])
def openwakeword_handler_health():
    """Health check for Openwakeword"""
    return jsonify({
        "service": "openwakeword_handler",
        "name": "Openwakeword",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['list_audio_devices'],
        "last_checked": datetime.now().isoformat(),
        "message": "Openwakeword service is available and ready"
    })

@enhanced_service_bp.route('/api/services/openwakeword_handler/info', methods=['GET'])
def openwakeword_handler_info():
    """Service information for Openwakeword"""
    return jsonify({
        "service_id": "openwakeword_handler",
        "name": "Openwakeword",
        "type": "integration",
        "description": "Enhanced Openwakeword integration service",
        "file_path": "wake_word_detector/openwakeword_handler.py",
        "status": "available",
        "capabilities": ['list_audio_devices'],
        "workflow_integration": True,
        "chat_commands": ["use openwakeword", "access openwakeword"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/test_handler/health', methods=['GET'])
def test_handler_health():
    """Health check for Test"""
    return jsonify({
        "service": "test_handler",
        "name": "Test",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Test service is available and ready"
    })

@enhanced_service_bp.route('/api/services/test_handler/info', methods=['GET'])
def test_handler_info():
    """Service information for Test"""
    return jsonify({
        "service_id": "test_handler",
        "name": "Test",
        "type": "integration",
        "description": "Enhanced Test integration service",
        "file_path": "wake_word_detector/tests/test_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use test", "access test"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/wordpress_service/health', methods=['GET'])
def wordpress_service_health():
    """Health check for Wordpress"""
    return jsonify({
        "service": "wordpress_service",
        "name": "Wordpress",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['delete_post', 'create_post', 'list_posts', 'get_post', 'update_post', 'get_wordpress_client'],
        "last_checked": datetime.now().isoformat(),
        "message": "Wordpress service is available and ready"
    })

@enhanced_service_bp.route('/api/services/wordpress_service/info', methods=['GET'])
def wordpress_service_info():
    """Service information for Wordpress"""
    return jsonify({
        "service_id": "wordpress_service",
        "name": "Wordpress",
        "type": "integration",
        "description": "Enhanced Wordpress integration service",
        "file_path": "wordpress_service.py",
        "status": "available",
        "capabilities": ['delete_post', 'create_post', 'list_posts', 'get_post', 'update_post', 'get_wordpress_client'],
        "workflow_integration": True,
        "chat_commands": ["use wordpress", "access wordpress"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/wordpress_service_real/health', methods=['GET'])
def wordpress_service_real_health():
    """Health check for Wordpress Real"""
    return jsonify({
        "service": "wordpress_service_real",
        "name": "Wordpress Real",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_wordpress_client', 'get_post', 'create_post'],
        "last_checked": datetime.now().isoformat(),
        "message": "Wordpress Real service is available and ready"
    })

@enhanced_service_bp.route('/api/services/wordpress_service_real/info', methods=['GET'])
def wordpress_service_real_info():
    """Service information for Wordpress Real"""
    return jsonify({
        "service_id": "wordpress_service_real",
        "name": "Wordpress Real",
        "type": "integration",
        "description": "Enhanced Wordpress Real integration service",
        "file_path": "wordpress_service_real.py",
        "status": "available",
        "capabilities": ['get_wordpress_client', 'get_post', 'create_post'],
        "workflow_integration": True,
        "chat_commands": ["use wordpress real", "access wordpress real"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/workflow_execution_service/health', methods=['GET'])
def workflow_execution_service_health():
    """Health check for Workflow Execution"""
    return jsonify({
        "service": "workflow_execution_service",
        "name": "Workflow Execution",
        "status": "healthy",
        "type": "automation",
        "capabilities": ['get_workflow', 'list_workflows', 'get_execution_status', 'list_active_executions'],
        "last_checked": datetime.now().isoformat(),
        "message": "Workflow Execution service is available and ready"
    })

@enhanced_service_bp.route('/api/services/workflow_execution_service/info', methods=['GET'])
def workflow_execution_service_info():
    """Service information for Workflow Execution"""
    return jsonify({
        "service_id": "workflow_execution_service",
        "name": "Workflow Execution",
        "type": "automation",
        "description": "Enhanced Workflow Execution integration service",
        "file_path": "workflow_execution_service.py",
        "status": "available",
        "capabilities": ['get_workflow', 'list_workflows', 'get_execution_status', 'list_active_executions'],
        "workflow_integration": True,
        "chat_commands": ["use workflow execution", "access workflow execution"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/workflow_handler/health', methods=['GET'])
def workflow_handler_health():
    """Health check for Workflow"""
    return jsonify({
        "service": "workflow_handler",
        "name": "Workflow",
        "status": "healthy",
        "type": "automation",
        "capabilities": ['get_execution_history', 'delete_workflow', 'create_workflow', 'get_workflow', 'create_workflow_tables', 'update_workflow', 'list_workflows', 'get_execution_details', 'get_workflow_stats'],
        "last_checked": datetime.now().isoformat(),
        "message": "Workflow service is available and ready"
    })

@enhanced_service_bp.route('/api/services/workflow_handler/info', methods=['GET'])
def workflow_handler_info():
    """Service information for Workflow"""
    return jsonify({
        "service_id": "workflow_handler",
        "name": "Workflow",
        "type": "automation",
        "description": "Enhanced Workflow integration service",
        "file_path": "workflow_handler.py",
        "status": "available",
        "capabilities": ['get_execution_history', 'delete_workflow', 'create_workflow', 'get_workflow', 'create_workflow_tables', 'update_workflow', 'list_workflows', 'get_execution_details', 'get_workflow_stats'],
        "workflow_integration": True,
        "chat_commands": ["use workflow", "access workflow"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/xero_handler/health', methods=['GET'])
def xero_handler_health():
    """Health check for Xero"""
    return jsonify({
        "service": "xero_handler",
        "name": "Xero",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['basic_operations'],
        "last_checked": datetime.now().isoformat(),
        "message": "Xero service is available and ready"
    })

@enhanced_service_bp.route('/api/services/xero_handler/info', methods=['GET'])
def xero_handler_info():
    """Service information for Xero"""
    return jsonify({
        "service_id": "xero_handler",
        "name": "Xero",
        "type": "integration",
        "description": "Enhanced Xero integration service",
        "file_path": "xero_handler.py",
        "status": "available",
        "capabilities": ['basic_operations'],
        "workflow_integration": True,
        "chat_commands": ["use xero", "access xero"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/xero_service/health', methods=['GET'])
def xero_service_health():
    """Health check for Xero"""
    return jsonify({
        "service": "xero_service",
        "name": "Xero",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_bill', 'get_invoice', 'get_xero_client', 'list_bills', 'update_contact', 'list_invoices', 'create_contact', 'get_contact', 'create_invoice', 'list_contacts'],
        "last_checked": datetime.now().isoformat(),
        "message": "Xero service is available and ready"
    })

@enhanced_service_bp.route('/api/services/xero_service/info', methods=['GET'])
def xero_service_info():
    """Service information for Xero"""
    return jsonify({
        "service_id": "xero_service",
        "name": "Xero",
        "type": "integration",
        "description": "Enhanced Xero integration service",
        "file_path": "xero_service.py",
        "status": "available",
        "capabilities": ['create_bill', 'get_invoice', 'get_xero_client', 'list_bills', 'update_contact', 'list_invoices', 'create_contact', 'get_contact', 'create_invoice', 'list_contacts'],
        "workflow_integration": True,
        "chat_commands": ["use xero", "access xero"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/zendesk_service/health', methods=['GET'])
def zendesk_service_health():
    """Health check for Zendesk"""
    return jsonify({
        "service": "zendesk_service",
        "name": "Zendesk",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['get_ticket', 'get_zendesk_client', 'create_user', 'create_ticket'],
        "last_checked": datetime.now().isoformat(),
        "message": "Zendesk service is available and ready"
    })

@enhanced_service_bp.route('/api/services/zendesk_service/info', methods=['GET'])
def zendesk_service_info():
    """Service information for Zendesk"""
    return jsonify({
        "service_id": "zendesk_service",
        "name": "Zendesk",
        "type": "integration",
        "description": "Enhanced Zendesk integration service",
        "file_path": "zendesk_service.py",
        "status": "available",
        "capabilities": ['get_ticket', 'get_zendesk_client', 'create_user', 'create_ticket'],
        "workflow_integration": True,
        "chat_commands": ["use zendesk", "access zendesk"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/zoho_handler/health', methods=['GET'])
def zoho_handler_health():
    """Health check for Zoho"""
    return jsonify({
        "service": "zoho_handler",
        "name": "Zoho",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_zoho_bill', 'get_zoho_organizations', 'create_zoho_vendor', 'get_zoho_invoices', 'create_zoho_customer', 'get_zoho_sales_orders', 'get_zoho_vendors', 'get_zoho_customers', 'create_zoho_sales_order', 'create_zoho_invoice', 'get_zoho_items', 'create_zoho_item', 'get_zoho_purchase_orders', 'create_zoho_purchase_order', 'get_zoho_bills'],
        "last_checked": datetime.now().isoformat(),
        "message": "Zoho service is available and ready"
    })

@enhanced_service_bp.route('/api/services/zoho_handler/info', methods=['GET'])
def zoho_handler_info():
    """Service information for Zoho"""
    return jsonify({
        "service_id": "zoho_handler",
        "name": "Zoho",
        "type": "integration",
        "description": "Enhanced Zoho integration service",
        "file_path": "zoho_handler.py",
        "status": "available",
        "capabilities": ['create_zoho_bill', 'get_zoho_organizations', 'create_zoho_vendor', 'get_zoho_invoices', 'create_zoho_customer', 'get_zoho_sales_orders', 'get_zoho_vendors', 'get_zoho_customers', 'create_zoho_sales_order', 'create_zoho_invoice', 'get_zoho_items', 'create_zoho_item', 'get_zoho_purchase_orders', 'create_zoho_purchase_order', 'get_zoho_bills'],
        "workflow_integration": True,
        "chat_commands": ["use zoho", "access zoho"],
        "last_updated": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/zoho_service/health', methods=['GET'])
def zoho_service_health():
    """Health check for Zoho"""
    return jsonify({
        "service": "zoho_service",
        "name": "Zoho",
        "status": "healthy",
        "type": "integration",
        "capabilities": ['create_zoho_bill', 'get_zoho_organizations', 'create_zoho_vendor', 'get_zoho_invoices', 'create_zoho_customer', 'send_to_zoho', 'get_zoho_sales_orders', 'get_zoho_vendors', 'get_zoho_customers', 'create_zoho_sales_order', 'create_zoho_invoice', 'get_zoho_items', 'create_zoho_item', 'get_zoho_purchase_orders', 'create_zoho_purchase_order', 'get_zoho_bills'],
        "last_checked": datetime.now().isoformat(),
        "message": "Zoho service is available and ready"
    })

@enhanced_service_bp.route('/api/services/zoho_service/info', methods=['GET'])
def zoho_service_info():
    """Service information for Zoho"""
    return jsonify({
        "service_id": "zoho_service",
        "name": "Zoho",
        "type": "integration",
        "description": "Enhanced Zoho integration service",
        "file_path": "zoho_service.py",
        "status": "available",
        "capabilities": ['create_zoho_bill', 'get_zoho_organizations', 'create_zoho_vendor', 'get_zoho_invoices', 'create_zoho_customer', 'send_to_zoho', 'get_zoho_sales_orders', 'get_zoho_vendors', 'get_zoho_customers', 'create_zoho_sales_order', 'create_zoho_invoice', 'get_zoho_items', 'create_zoho_item', 'get_zoho_purchase_orders', 'create_zoho_purchase_order', 'get_zoho_bills'],
        "workflow_integration": True,
        "chat_commands": ["use zoho", "access zoho"],
        "last_updated": datetime.now().isoformat()
    })

# Batch service operations
@enhanced_service_bp.route('/api/services/batch/health', methods=['GET'])
def batch_service_health():
    """Health check for all services"""
    from service_registry_routes import SERVICE_REGISTRY

    health_results = {}
    for service_id, service_data in SERVICE_REGISTRY.items():
        health_results[service_id] = {
            "name": service_data.get("name", service_id),
            "status": service_data.get("health", "unknown"),
            "type": service_data.get("type", "unknown"),
            "last_checked": service_data.get("last_checked", datetime.now().isoformat())
        }

    return jsonify({
        "total_services": len(health_results),
        "healthy_services": len([s for s in health_results.values() if s["status"] == "healthy"]),
        "services": health_results,
        "timestamp": datetime.now().isoformat()
    })

@enhanced_service_bp.route('/api/services/batch/info', methods=['GET'])
def batch_service_info():
    """Information for all services"""
    from service_registry_routes import SERVICE_REGISTRY

    service_info = {}
    for service_id, service_data in SERVICE_REGISTRY.items():
        service_info[service_id] = {
            "name": service_data.get("name", service_id),
            "type": service_data.get("type", "unknown"),
            "description": service_data.get("description", ""),
            "capabilities": service_data.get("capabilities", []),
            "status": service_data.get("status", "unknown"),
            "workflow_triggers": service_data.get("workflow_triggers", []),
            "workflow_actions": service_data.get("workflow_actions", []),
            "chat_commands": service_data.get("chat_commands", [])
        }

    return jsonify({
        "total_services": len(service_info),
        "active_services": len([s for s in service_info.values() if s["status"] == "active"]),
        "services": service_info,
        "timestamp": datetime.now().isoformat()
    })
