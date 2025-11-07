"""
ATOM QuickBooks Integration Registration
Registration utilities for QuickBooks integration
Following ATOM integration patterns
"""

import os
from typing import Dict, Any, Optional
from loguru import logger
from flask import Flask

from quickbooks_routes import register_quickbooks_routes
from auth_handler_quickbooks import register_quickbooks_auth_routes
from quickbooks_service import create_quickbooks_service
from db_oauth_quickbooks import create_quickbooks_db_handler

# Integration state
QUICKBOOKS_AVAILABLE = True
QUICKBOOKS_CONFIGURED = False
quickbooks_service = None
db_handler = None

def check_quickbooks_availability() -> bool:
    """Check if QuickBooks integration dependencies are available"""
    try:
        # Check required packages
        import aiohttp
        import asyncpg
        return True
    except ImportError as e:
        logger.warning(f"QuickBooks integration not available: {e}")
        return False

def check_quickbooks_configuration() -> bool:
    """Check if QuickBooks integration is properly configured"""
    required_vars = [
        "QUICKBOOKS_CLIENT_ID",
        "QUICKBOOKS_CLIENT_SECRET",
        "QUICKBOOKS_REDIRECT_URI"
    ]
    
    optional_vars = [
        "QUICKBOOKS_ENVIRONMENT",
        "QUICKBOOKS_ACCESS_TOKEN",
        "QUICKBOOKS_REFRESH_TOKEN",
        "QUICKBOOKS_REALM_ID"
    ]
    
    # Check required variables
    missing_required = [var for var in required_vars if not os.getenv(var)]
    if missing_required:
        logger.warning(f"QuickBooks missing required environment variables: {missing_required}")
        return False
    
    # Check optional variables for OAuth
    missing_optional = [var for var in optional_vars if not os.getenv(var)]
    if missing_optional:
        logger.info(f"QuickBooks tokens not configured (missing: {missing_optional}), OAuth flow required")
    
    return True

def init_quickbooks_services(db_pool=None) -> bool:
    """Initialize QuickBooks services"""
    global quickbooks_service, db_handler, QUICKBOOKS_CONFIGURED
    
    try:
        if not QUICKBOOKS_AVAILABLE:
            logger.warning("QuickBooks integration not available")
            return False
        
        if not check_quickbooks_configuration():
            logger.warning("QuickBooks integration not properly configured")
            QUICKBOOKS_CONFIGURED = False
            return False
        
        # Initialize service
        quickbooks_service = create_quickbooks_service()
        if not quickbooks_service:
            logger.error("Failed to create QuickBooks service")
            return False
        
        # Initialize database handler
        db_type = "postgresql" if db_pool else "sqlite"
        db_handler = create_quickbooks_db_handler(db_pool, db_type)
        if not db_handler:
            logger.error("Failed to create QuickBooks database handler")
            return False
        
        QUICKBOOKS_CONFIGURED = True
        logger.info("QuickBooks services initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize QuickBooks services: {e}")
        QUICKBOOKS_CONFIGURED = False
        return False

def register_quickbooks_integration(app: Flask, db_pool=None) -> bool:
    """Register QuickBooks integration with Flask app"""
    try:
        global QUICKBOOKS_AVAILABLE, QUICKBOOKS_CONFIGURED
        
        # Check availability
        if not check_quickbooks_availability():
            QUICKBOOKS_AVAILABLE = False
            logger.warning("QuickBooks integration not available - missing dependencies")
            return False
        
        # Initialize services
        if not init_quickbooks_services(db_pool):
            logger.warning("QuickBooks integration initialization failed")
            return False
        
        # Register API routes
        register_quickbooks_routes(app)
        logger.info("QuickBooks API routes registered")
        
        # Register authentication routes
        register_quickbooks_auth_routes(app)
        logger.info("QuickBooks authentication routes registered")
        
        # Add integration info to app
        if not hasattr(app, 'integrations'):
            app.integrations = {}
        
        app.integrations['quickbooks'] = {
            'name': 'QuickBooks',
            'description': 'Small business accounting and financial management',
            'available': True,
            'configured': QUICKBOOKS_CONFIGURED,
            'features': [
                'invoice_management',
                'customer_management',
                'expense_tracking',
                'account_management',
                'financial_reporting',
                'vendor_management',
                'oauth_authentication',
                'token_authentication'
            ],
            'endpoints': [
                '/api/quickbooks/invoices',
                '/api/quickbooks/customers',
                '/api/quickbooks/expenses',
                '/api/quickbooks/accounts',
                '/api/quickbooks/vendors',
                '/api/quickbooks/reports/profit-loss',
                '/api/quickbooks/reports/balance-sheet',
                '/api/quickbooks/reports/cash-flow',
                '/api/quickbooks/reports/aging',
                '/api/quickbooks/health',
                '/auth/quickbooks',
                '/auth/quickbooks/callback'
            ]
        }
        
        logger.info("QuickBooks integration registered successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to register QuickBooks integration: {e}")
        QUICKBOOKS_AVAILABLE = False
        QUICKBOOKS_CONFIGURED = False
        return False

def get_quickbooks_service():
    """Get QuickBooks service instance"""
    return quickbooks_service

def get_quickbooks_db_handler():
    """Get QuickBooks database handler instance"""
    return db_handler

def is_quickbooks_available() -> bool:
    """Check if QuickBooks integration is available"""
    return QUICKBOOKS_AVAILABLE and QUICKBOOKS_CONFIGURED

def get_quickbooks_info() -> Dict[str, Any]:
    """Get QuickBooks integration information"""
    return {
        'name': 'QuickBooks',
        'available': QUICKBOOKS_AVAILABLE,
        'configured': QUICKBOOKS_CONFIGURED,
        'environment': os.getenv('QUICKBOOKS_ENVIRONMENT', 'sandbox'),
        'has_tokens': bool(os.getenv('QUICKBOOKS_ACCESS_TOKEN')),
        'features': [
            'Invoice CRUD operations',
            'Customer management',
            'Expense tracking and management',
            'Chart of Accounts management',
            'Vendor management',
            'Financial reporting',
            'Profit and Loss statements',
            'Balance Sheet reporting',
            'Cash Flow analysis',
            'Accounts Receivable Aging',
            'OAuth 2.0 authentication',
            'Token authentication',
            'Multi-realm support',
            'Sandbox and production environments'
        ],
        'supported_operations': [
            'list_invoices',
            'get_invoice',
            'create_invoice',
            'update_invoice',
            'delete_invoice',
            'list_customers',
            'get_customer',
            'create_customer',
            'update_customer',
            'delete_customer',
            'list_expenses',
            'get_expense',
            'create_expense',
            'update_expense',
            'delete_expense',
            'list_accounts',
            'get_account',
            'create_account',
            'list_vendors',
            'get_vendor',
            'create_vendor',
            'get_profit_loss',
            'get_balance_sheet',
            'get_cash_flow',
            'get_aging_report',
            'auth_oauth',
            'auth_status',
            'auth_refresh',
            'auth_revoke'
        ]
    }

# Environment configuration helper
def setup_quickbooks_environment():
    """Setup QuickBooks environment variables template"""
    env_template = """
# QuickBooks Integration Configuration
# Required for OAuth 2.0 authentication
QUICKBOOKS_CLIENT_ID=your-oauth-client-id
QUICKBOOKS_CLIENT_SECRET=your-oauth-client-secret
QUICKBOOKS_REDIRECT_URI=http://localhost:5058/auth/quickbooks/callback

# Optional - Environment Selection
QUICKBOOKS_ENVIRONMENT=sandbox  # sandbox or production

# Optional - Token Authentication (for service accounts)
QUICKBOOKS_ACCESS_TOKEN=your-access-token
QUICKBOOKS_REFRESH_TOKEN=your-refresh-token
QUICKBOOKS_REALM_ID=your-realm-id

# Database Configuration (uses ATOM's default settings)
# If not using PostgreSQL, set:
# DB_TYPE=sqlite
# SQLITE_DB_PATH=atom.db
"""
    
    logger.info("QuickBooks environment template:")
    logger.info(env_template)
    
    return env_template

def validate_quickbooks_configuration() -> Dict[str, Any]:
    """Validate QuickBooks configuration and return status"""
    issues = []
    warnings = []
    
    # Check required variables
    required_vars = {
        'QUICKBOOKS_CLIENT_ID': 'QuickBooks OAuth client ID',
        'QUICKBOOKS_CLIENT_SECRET': 'QuickBooks OAuth client secret',
        'QUICKBOOKS_REDIRECT_URI': 'QuickBooks OAuth redirect URI'
    }
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            issues.append(f"{var}: {description} is required")
        elif not value.strip():
            issues.append(f"{var}: {description} cannot be empty")
    
    # Check optional variables
    oauth_vars = {
        'QUICKBOOKS_ACCESS_TOKEN': 'QuickBooks access token',
        'QUICKBOOKS_REFRESH_TOKEN': 'QuickBooks refresh token',
        'QUICKBOOKS_REALM_ID': 'QuickBooks realm ID'
    }
    
    oauth_missing = [var for var in oauth_vars if not os.getenv(var)]
    if oauth_missing:
        warnings.append(f"OAuth tokens not configured (missing: {', '.join(oauth_missing)})")
    
    # Validate environment
    environment = os.getenv('QUICKBOOKS_ENVIRONMENT', 'sandbox')
    if environment not in ['sandbox', 'production']:
        warnings.append("QUICKBOOKS_ENVIRONMENT should be 'sandbox' or 'production'")
    
    # Validate redirect URI format
    redirect_uri = os.getenv('QUICKBOOKS_REDIRECT_URI', '')
    if redirect_uri and not redirect_uri.startswith(('http://', 'https://')):
        warnings.append("QUICKBOOKS_REDIRECT_URI should start with http:// or https://")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'configured': len(issues) == 0,
        'has_oauth_tokens': len(oauth_missing) == 0,
        'environment': environment
    }

# Initialize module
def _init_quickbooks_module():
    """Initialize QuickBooks module"""
    global QUICKBOOKS_AVAILABLE
    
    QUICKBOOKS_AVAILABLE = check_quickbooks_availability()
    
    if QUICKBOOKS_AVAILABLE:
        logger.info("QuickBooks integration module loaded")
    else:
        logger.info("QuickBooks integration module not available (missing dependencies)")

# Auto-initialize
_init_quickbooks_module()