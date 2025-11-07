"""
ATOM HubSpot Integration Registration
Registration utilities for HubSpot marketing integration
Following ATOM integration patterns
"""

import os
from typing import Dict, Any, Optional
from loguru import logger
from flask import Flask

from hubspot_routes import register_hubspot_routes
from auth_handler_hubspot import register_hubspot_auth_routes
from hubspot_service import create_hubspot_service
from db_oauth_hubspot import create_hubspot_db_handler

# Integration state
HUBSPOT_AVAILABLE = True
HUBSPOT_CONFIGURED = False
hubspot_service = None
db_handler = None

def check_hubspot_availability() -> bool:
    """Check if HubSpot integration dependencies are available"""
    try:
        # Check required packages
        import aiohttp
        import asyncpg
        return True
    except ImportError as e:
        logger.warning(f"HubSpot integration not available: {e}")
        return False

def check_hubspot_configuration() -> bool:
    """Check if HubSpot integration is properly configured"""
    required_vars = [
        "HUBSPOT_CLIENT_ID",
        "HUBSPOT_CLIENT_SECRET",
        "HUBSPOT_REDIRECT_URI"
    ]
    
    optional_vars = [
        "HUBSPOT_ACCESS_TOKEN",
        "HUBSPOT_REFRESH_TOKEN",
        "HUBSPOT_PRIVATE_APP_TOKEN"
    ]
    
    # Check required variables
    missing_required = [var for var in required_vars if not os.getenv(var)]
    if missing_required:
        logger.warning(f"HubSpot missing required environment variables: {missing_required}")
        return False
    
    # Check optional variables for token auth
    missing_optional = [var for var in optional_vars if not os.getenv(var)]
    if missing_optional:
        logger.info(f"HubSpot tokens not configured (missing: {missing_optional}), OAuth flow required")
    
    return True

def init_hubspot_services(db_pool=None) -> bool:
    """Initialize HubSpot services"""
    global hubspot_service, db_handler, HUBSPOT_CONFIGURED
    
    try:
        if not HUBSPOT_AVAILABLE:
            logger.warning("HubSpot integration not available")
            return False
        
        if not check_hubspot_configuration():
            logger.warning("HubSpot integration not properly configured")
            HUBSPOT_CONFIGURED = False
            return False
        
        # Initialize service
        hubspot_service = create_hubspot_service()
        if not hubspot_service:
            logger.error("Failed to create HubSpot service")
            return False
        
        # Initialize database handler
        db_type = "postgresql" if db_pool else "sqlite"
        db_handler = create_hubspot_db_handler(db_pool, db_type)
        if not db_handler:
            logger.error("Failed to create HubSpot database handler")
            return False
        
        HUBSPOT_CONFIGURED = True
        logger.info("HubSpot services initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize HubSpot services: {e}")
        HUBSPOT_CONFIGURED = False
        return False

def register_hubspot_integration(app: Flask, db_pool=None) -> bool:
    """Register HubSpot integration with Flask app"""
    try:
        global HUBSPOT_AVAILABLE, HUBSPOT_CONFIGURED
        
        # Check availability
        if not check_hubspot_availability():
            HUBSPOT_AVAILABLE = False
            logger.warning("HubSpot integration not available - missing dependencies")
            return False
        
        # Initialize services
        if not init_hubspot_services(db_pool):
            logger.warning("HubSpot integration initialization failed")
            return False
        
        # Register API routes - use Flask version
        from hubspot_routes_flask import register_hubspot_routes
        register_hubspot_routes(app)
        logger.info("HubSpot API routes registered")
        
        # Register authentication routes
        register_hubspot_auth_routes(app)
        logger.info("HubSpot authentication routes registered")
        
        # Add integration info to app
        if not hasattr(app, 'integrations'):
            app.integrations = {}
        
        app.integrations['hubspot'] = {
            'name': 'HubSpot',
            'description': 'Marketing automation and lead generation platform',
            'available': True,
            'configured': HUBSPOT_CONFIGURED,
            'features': [
                'contact_management',
                'company_management',
                'deal_pipeline',
                'marketing_campaigns',
                'email_marketing',
                'lead_nurturing',
                'sales_analytics',
                'oauth_authentication',
                'token_authentication',
                'list_management',
                'pipeline_tracking'
            ],
            'endpoints': [
                '/api/hubspot/contacts',
                '/api/hubspot/companies',
                '/api/hubspot/deals',
                '/api/hubspot/campaigns',
                '/api/hubspot/pipelines',
                '/api/hubspot/lead-lists',
                '/api/hubspot/email-templates',
                '/api/hubspot/analytics/deals',
                '/api/hubspot/analytics/contacts',
                '/api/hubspot/analytics/campaigns',
                '/api/hubspot/health',
                '/auth/hubspot',
                '/auth/hubspot/callback'
            ]
        }
        
        logger.info("HubSpot integration registered successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to register HubSpot integration: {e}")
        HUBSPOT_AVAILABLE = False
        HUBSPOT_CONFIGURED = False
        return False

def get_hubspot_service():
    """Get HubSpot service instance"""
    return hubspot_service

def get_hubspot_db_handler():
    """Get HubSpot database handler instance"""
    return db_handler

def is_hubspot_available() -> bool:
    """Check if HubSpot integration is available"""
    return HUBSPOT_AVAILABLE and HUBSPOT_CONFIGURED

def get_hubspot_info() -> Dict[str, Any]:
    """Get HubSpot integration information"""
    return {
        'name': 'HubSpot',
        'available': HUBSPOT_AVAILABLE,
        'configured': HUBSPOT_CONFIGURED,
        'environment': os.getenv('HUBSPOT_ENVIRONMENT', 'production'),
        'has_oauth_tokens': bool(os.getenv('HUBSPOT_ACCESS_TOKEN')),
        'features': [
            'Complete CRM management',
            'Marketing campaign automation',
            'Lead nurturing workflows',
            'Sales pipeline tracking',
            'Email marketing',
            'Contact and company management',
            'Deal management and forecasting',
            'Advanced analytics and reporting',
            'List management and segmentation',
            'OAuth 2.0 authentication',
            'Token authentication',
            'Private app support',
            'Multi-portal support',
            'Real-time sync capabilities'
        ],
        'supported_operations': [
            'list_contacts',
            'get_contact',
            'create_contact',
            'update_contact',
            'delete_contact',
            'list_companies',
            'get_company',
            'create_company',
            'update_company',
            'delete_company',
            'list_deals',
            'get_deal',
            'create_deal',
            'update_deal',
            'delete_deal',
            'get_pipelines',
            'get_pipeline_stages',
            'list_campaigns',
            'get_campaign',
            'create_campaign',
            'get_deal_analytics',
            'get_contact_analytics',
            'get_campaign_analytics',
            'get_lead_lists',
            'create_lead_list',
            'add_contacts_to_list',
            'remove_contacts_from_list',
            'get_email_templates',
            'send_email_to_contacts',
            'auth_oauth',
            'auth_status',
            'auth_refresh',
            'auth_revoke'
        ]
    }

# Environment configuration helper
def setup_hubspot_environment():
    """Setup HubSpot environment variables template"""
    env_template = """
# HubSpot Integration Configuration
# Required for OAuth 2.0 authentication
HUBSPOT_CLIENT_ID=your-oauth-client-id
HUBSPOT_CLIENT_SECRET=your-oauth-client-secret
HUBSPOT_REDIRECT_URI=http://localhost:5058/auth/hubspot/callback

# Optional - Environment Selection
HUBSPOT_ENVIRONMENT=production  # production or qa (for testing)

# Optional - Token Authentication (for private apps)
HUBSPOT_ACCESS_TOKEN=your-access-token
HUBSPOT_REFRESH_TOKEN=your-refresh-token
HUBSPOT_PRIVATE_APP_TOKEN=your-private-app-token

# Database Configuration (uses ATOM's default settings)
# If not using PostgreSQL, set:
# DB_TYPE=sqlite
# SQLITE_DB_PATH=atom.db
"""
    
    logger.info("HubSpot environment template:")
    logger.info(env_template)
    
    return env_template

def validate_hubspot_configuration() -> Dict[str, Any]:
    """Validate HubSpot configuration and return status"""
    issues = []
    warnings = []
    
    # Check required variables
    required_vars = {
        'HUBSPOT_CLIENT_ID': 'HubSpot OAuth client ID',
        'HUBSPOT_CLIENT_SECRET': 'HubSpot OAuth client secret',
        'HUBSPOT_REDIRECT_URI': 'HubSpot OAuth redirect URI'
    }
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            issues.append(f"{var}: {description} is required")
        elif not value.strip():
            issues.append(f"{var}: {description} cannot be empty")
    
    # Check optional variables
    auth_vars = {
        'HUBSPOT_ACCESS_TOKEN': 'HubSpot access token',
        'HUBSPOT_REFRESH_TOKEN': 'HubSpot refresh token'
    }
    
    auth_missing = [var for var in auth_vars if not os.getenv(var)]
    if auth_missing:
        warnings.append(f"HubSpot tokens not configured (missing: {', '.join(auth_missing)})")
    
    # Validate environment
    environment = os.getenv('HUBSPOT_ENVIRONMENT', 'production')
    if environment not in ['production', 'qa', 'sandbox']:
        warnings.append("HUBSPOT_ENVIRONMENT should be 'production', 'qa', or 'sandbox'")
    
    # Validate redirect URI format
    redirect_uri = os.getenv('HUBSPOT_REDIRECT_URI', '')
    if redirect_uri and not redirect_uri.startswith(('http://', 'https://')):
        warnings.append("HUBSPOT_REDIRECT_URI should start with http:// or https://")
    
    # Validate scopes and permissions
    required_scopes = [
        'contacts', 'crm.objects.companies.read', 'crm.objects.companies.write',
        'crm.objects.contacts.read', 'crm.objects.contacts.write',
        'crm.objects.deals.read', 'crm.objects.deals.write'
    ]
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'configured': len(issues) == 0,
        'has_oauth_tokens': len(auth_missing) == 0,
        'environment': environment,
        'required_scopes': required_scopes
    }

# Initialize module
def _init_hubspot_module():
    """Initialize HubSpot module"""
    global HUBSPOT_AVAILABLE
    
    HUBSPOT_AVAILABLE = check_hubspot_availability()
    
    if HUBSPOT_AVAILABLE:
        logger.info("HubSpot integration module loaded")
    else:
        logger.info("HubSpot integration module not available (missing dependencies)")

# Auto-initialize
_init_hubspot_module()