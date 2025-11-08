import logging
from fastapi import FastAPI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def register_azure_integration(app: FastAPI):
    """Register Azure integration with FastAPI app"""
    try:
        # Register Azure OAuth routes
        from azure_oauth_api import router as azure_oauth_bp
        app.include_router(azure_oauth_bp)
        
        # Register Azure infrastructure routes
        from azure_infrastructure_handler import router as azure_infra_bp
        app.include_router(azure_infra_bp)
        
        logger.info("Azure integration registered successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to register Azure integration: {e}")
        return False

def initialize_azure_schema(db_pool=None):
    """Initialize Azure database schema"""
    try:
        from db_oauth_azure import create_azure_tokens_table
        
        # Initialize token storage
        if db_pool:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(create_azure_tokens_table(db_pool))
            loop.close()
        
        logger.info("Azure database schema initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize Azure schema: {e}")
        return False

# Azure integration metadata
AZURE_CONFIG = {
    "name": "Microsoft Azure",
    "description": "Cloud computing platform for infrastructure, storage, and development",
    "version": "1.0.0",
    "category": "cloud",
    "oauth": True,
    "scopes": [
        "https://management.azure.com/.default",
        "offline_access"
    ],
    "services": [
        "Virtual Machines",
        "Storage Accounts", 
        "App Services",
        "Azure Functions",
        "Azure SQL",
        "Key Vault",
        "Azure Monitor",
        "Cost Management",
        "Networking",
        "Container Registry",
        "Kubernetes Service"
    ],
    "features": [
        "Infrastructure as Code",
        "Resource Management",
        "Monitoring & Analytics",
        "Cost Management",
        "Security & Compliance",
        "DevOps Integration"
    ],
    "api_endpoints": [
        "/auth/azure/*",
        "/api/azure/*"
    ],
    "dependencies": [
        "azure-identity",
        "azure-mgmt-compute",
        "azure-mgmt-storage", 
        "azure-mgmt-web",
        "azure-mgmt-resource",
        "azure-mgmt-costmanagement",
        "azure-mgmt-monitor",
        "azure-storage-blob",
        "azure-cosmos",
        "azure-mgmt-sql",
        "asyncpg",
        "cryptography",
        "httpx"
    ]
}

def get_azure_config():
    """Get Azure integration configuration"""
    return AZURE_CONFIG