import logging
from fastapi import FastAPI
from xero_oauth_api import router as xero_oauth_router
from xero_service import router as xero_service_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def register_xero_integration(app: FastAPI):
    """Register Xero integration with FastAPI app"""
    try:
        # Register Xero API routes
        app.include_router(xero_oauth_router)
        app.include_router(xero_service_router)
        
        logger.info("Xero integration registered successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to register Xero integration: {e}")
        return False

def initialize_xero_schema(db_pool=None):
    """Initialize Xero database schema"""
    try:
        from db_oauth_xero import create_xero_tokens_table
        from xero_service import initialize_cache_tables
        
        # Initialize token storage
        if db_pool:
            import asyncio
            asyncio.run(create_xero_tokens_table(db_pool))
        
        # Initialize cache tables
        if hasattr(xero_service_router, 'initialize_cache_tables'):
            asyncio.run(xero_service_router.initialize_cache_tables())
        
        logger.info("Xero database schema initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize Xero schema: {e}")
        return False

# Xero integration metadata
XERO_CONFIG = {
    "name": "Xero",
    "description": "Accounting and financial management platform",
    "version": "1.0.0",
    "category": "finance",
    "oauth": True,
    "scopes": [
        "accounting.settings",
        "accounting.transactions", 
        "accounting.contacts",
        "accounting.reports.read",
        "offline_access"
    ],
    "webhooks": True,
    "api_endpoints": [
        "/auth/xero/*",
        "/api/xero/*"
    ],
    "dependencies": [
        "xero-python>=1.5.0,<2.0.0",
        "httpx",
        "cryptography",
        "asyncpg"
    ]
}

def get_xero_config():
    """Get Xero integration configuration"""
    return XERO_CONFIG