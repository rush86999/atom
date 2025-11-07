"""
ATOM Zendesk Integration Registration
Registration utilities for Zendesk integration
Following ATOM integration patterns
"""

import os
from typing import Dict, Any, Optional
from loguru import logger
from flask import Flask

from zendesk_routes import register_zendesk_routes
from auth_handler_zendesk import register_zendesk_auth_routes
from zendesk_service import create_zendesk_service
from db_oauth_zendesk import create_zendesk_db_handler

# Integration state
ZENDESK_AVAILABLE = True
ZENDESK_CONFIGURED = False
zendesk_service = None
db_handler = None

def check_zendesk_availability() -> bool:
    """Check if Zendesk integration dependencies are available"""
    try:
        # Check required packages
        import aiohttp
        import zenpy
        import asyncpg
        return True
    except ImportError as e:
        logger.warning(f"Zendesk integration not available: {e}")
        return False

def check_zendesk_configuration() -> bool:
    """Check if Zendesk integration is properly configured"""
    required_vars = [
        "ZENDESK_SUBDOMAIN",
        "ZENDESK_EMAIL", 
        "ZENDESK_TOKEN"
    ]
    
    optional_vars = [
        "ZENDESK_CLIENT_ID",
        "ZENDESK_CLIENT_SECRET",
        "ZENDESK_REDIRECT_URI"
    ]
    
    # Check required variables
    missing_required = [var for var in required_vars if not os.getenv(var)]
    if missing_required:
        logger.warning(f"Zendesk missing required environment variables: {missing_required}")
        return False
    
    # Check optional variables for OAuth
    missing_optional = [var for var in optional_vars if not os.getenv(var)]
    if missing_optional:
        logger.info(f"Zendesk OAuth not configured (missing: {missing_optional}), using token auth")
    
    return True

def init_zendesk_services(db_pool=None) -> bool:
    """Initialize Zendesk services"""
    global zendesk_service, db_handler, ZENDESK_CONFIGURED
    
    try:
        if not ZENDESK_AVAILABLE:
            logger.warning("Zendesk integration not available")
            return False
        
        if not check_zendesk_configuration():
            logger.warning("Zendesk integration not properly configured")
            ZENDESK_CONFIGURED = False
            return False
        
        # Initialize service
        zendesk_service = create_zendesk_service()
        if not zendesk_service:
            logger.error("Failed to create Zendesk service")
            return False
        
        # Initialize database handler
        db_type = "postgresql" if db_pool else "sqlite"
        db_handler = create_zendesk_db_handler(db_pool, db_type)
        if not db_handler:
            logger.error("Failed to create Zendesk database handler")
            return False
        
        ZENDESK_CONFIGURED = True
        logger.info("Zendesk services initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize Zendesk services: {e}")
        ZENDESK_CONFIGURED = False
        return False

def register_zendesk_integration(app: Flask, db_pool=None) -> bool:
    """Register Zendesk integration with Flask app"""
    try:
        global ZENDESK_AVAILABLE, ZENDESK_CONFIGURED
        
        # Check availability
        if not check_zendesk_availability():
            ZENDESK_AVAILABLE = False
            logger.warning("Zendesk integration not available - missing dependencies")
            return False
        
        # Initialize services
        if not init_zendesk_services(db_pool):
            logger.warning("Zendesk integration initialization failed")
            return False
        
        # Register API routes
        register_zendesk_routes(app)
        logger.info("Zendesk API routes registered")
        
        # Register authentication routes
        register_zendesk_auth_routes(app)
        logger.info("Zendesk authentication routes registered")
        
        # Add integration info to app
        if not hasattr(app, 'integrations'):
            app.integrations = {}
        
        app.integrations['zendesk'] = {
            'name': 'Zendesk',
            'description': 'Customer support and ticketing platform',
            'available': True,
            'configured': ZENDESK_CONFIGURED,
            'features': [
                'ticket_management',
                'user_management', 
                'organization_management',
                'ticket_search',
                'analytics',
                'oauth_authentication',
                'token_authentication'
            ],
            'endpoints': [
                '/api/zendesk/tickets',
                '/api/zendesk/users',
                '/api/zendesk/organizations',
                '/api/zendesk/search/tickets',
                '/api/zendesk/analytics/tickets',
                '/api/zendesk/health',
                '/auth/zendesk',
                '/auth/zendesk/callback'
            ]
        }
        
        logger.info("Zendesk integration registered successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to register Zendesk integration: {e}")
        ZENDESK_AVAILABLE = False
        ZENDESK_CONFIGURED = False
        return False

def get_zendesk_service():
    """Get Zendesk service instance"""
    return zendesk_service

def get_zendesk_db_handler():
    """Get Zendesk database handler instance"""
    return db_handler

def is_zendesk_available() -> bool:
    """Check if Zendesk integration is available"""
    return ZENDESK_AVAILABLE and ZENDESK_CONFIGURED

def get_zendesk_info() -> Dict[str, Any]:
    """Get Zendesk integration information"""
    return {
        'name': 'Zendesk',
        'available': ZENDESK_AVAILABLE,
        'configured': ZENDESK_CONFIGURED,
        'subdomain': os.getenv('ZENDESK_SUBDOMAIN', ''),
        'has_oauth': bool(os.getenv('ZENDESK_CLIENT_ID')),
        'features': [
            'Ticket CRUD operations',
            'User management',
            'Organization management',
            'Ticket search and filtering',
            'Analytics and metrics',
            'OAuth 2.0 authentication',
            'Token authentication',
            'Real-time updates',
            'Multi-language support'
        ],
        'supported_operations': [
            'list_tickets',
            'get_ticket',
            'create_ticket',
            'update_ticket',
            'add_comment',
            'list_users',
            'get_user',
            'create_user',
            'list_organizations',
            'get_organization',
            'search_tickets',
            'get_analytics',
            'auth_oauth',
            'auth_status'
        ]
    }

# Environment configuration helper
def setup_zendesk_environment():
    """Setup Zendesk environment variables template"""
    env_template = """
# Zendesk Integration Configuration
# Required for basic authentication
ZENDESK_SUBDOMAIN=your-subdomain
ZENDESK_EMAIL=your-email@example.com
ZENDESK_TOKEN=your-api-token

# Optional - OAuth 2.0 Configuration
ZENDESK_CLIENT_ID=your-oauth-client-id
ZENDESK_CLIENT_SECRET=your-oauth-client-secret
ZENDESK_REDIRECT_URI=http://localhost:5058/auth/zendesk/callback

# Optional - OAuth Scopes (comma-separated)
ZENDESK_SCOPES=tickets:read tickets:write users:read organizations:read

# Database Configuration (uses ATOM's default settings)
# If not using PostgreSQL, set:
# DB_TYPE=sqlite
# SQLITE_DB_PATH=atom.db
"""
    
    logger.info("Zendesk environment template:")
    logger.info(env_template)
    
    return env_template

def validate_zendesk_configuration() -> Dict[str, Any]:
    """Validate Zendesk configuration and return status"""
    issues = []
    warnings = []
    
    # Check required variables
    required_vars = {
        'ZENDESK_SUBDOMAIN': 'Zendesk subdomain (e.g., company)',
        'ZENDESK_EMAIL': 'Zendesk email address',
        'ZENDESK_TOKEN': 'Zendesk API token'
    }
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            issues.append(f"{var}: {description} is required")
        elif not value.strip():
            issues.append(f"{var}: {description} cannot be empty")
    
    # Check optional variables
    oauth_vars = {
        'ZENDESK_CLIENT_ID': 'OAuth client ID',
        'ZENDESK_CLIENT_SECRET': 'OAuth client secret',
        'ZENDESK_REDIRECT_URI': 'OAuth redirect URI'
    }
    
    oauth_missing = [var for var in oauth_vars if not os.getenv(var)]
    if oauth_missing:
        warnings.append(f"OAuth not fully configured (missing: {', '.join(oauth_missing)})")
    
    # Validate subdomain format
    subdomain = os.getenv('ZENDESK_SUBDOMAIN', '')
    if subdomain and '.' in subdomain:
        warnings.append("ZENDESK_SUBDOMAIN should not include .zendesk.com suffix")
    
    # Validate redirect URI format
    redirect_uri = os.getenv('ZENDESK_REDIRECT_URI', '')
    if redirect_uri and not redirect_uri.startswith(('http://', 'https://')):
        warnings.append("ZENDESK_REDIRECT_URI should start with http:// or https://")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'configured': len(issues) == 0,
        'has_oauth': len(oauth_missing) == 0
    }

# Initialize module
def _init_zendesk_module():
    """Initialize Zendesk module"""
    global ZENDESK_AVAILABLE
    
    ZENDESK_AVAILABLE = check_zendesk_availability()
    
    if ZENDESK_AVAILABLE:
        logger.info("Zendesk integration module loaded")
    else:
        logger.info("Zendesk integration module not available (missing dependencies)")

# Auto-initialize
_init_zendesk_module()