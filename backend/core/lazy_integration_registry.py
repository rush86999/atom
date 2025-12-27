"""
Lazy Integration Registry
Loads integrations on-demand instead of at startup
"""
import importlib
import logging
from functools import lru_cache
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Integration Registry - Maps name to module:attribute path
INTEGRATION_REGISTRY = {
    # Core Modules
    "workflow_ui": "core.workflow_ui_endpoints:router",
    "atom_agent": "core.atom_agent_endpoints:router",
    "agent_routes": "api.agent_routes:router",
    "missing_endpoints": "core.missing_endpoints:router",
    "service_registry": "core.service_registry:router",
    "byok": "core.byok_endpoints:router",
    "byok_competitive": "core.byok_competitive_endpoints:router",
    "system_status": "core.system_status:router",
    "service_health": "service_health_endpoints:router",
    "workflow": "core.workflow_endpoints:router",
    "analytics": "core.analytics_endpoints:router",
    "enterprise": "core.enterprise_endpoints:router",
    "workflow_marketplace": "core.workflow_marketplace:router",
    "enterprise_user_mgmt": "core.enterprise_user_management:router",
    "integration_enhancement": "core.integration_enhancement_endpoints:router",
    "industry_workflow": "core.industry_workflow_endpoints:router",
    "ai_workflow_optimization": "core.ai_workflow_optimization_endpoints:router",
    "enterprise_security": "core.enterprise_security:router",
    "auto_healing": "core.auto_healing_endpoints:router",
    
    # Workflow Versioning
    "workflow_versioning": "api.workflow_versioning_endpoints:router",
    
    # Unified Endpoints
    "unified_task": "core.unified_task_endpoints:router",
    "unified_project": "core.unified_task_endpoints:project_router",
    "unified_calendar": "core.unified_calendar_endpoints:router",
    "unified_search": "core.mock_search_endpoints:router",  # Using mock instead of LanceDB
    
    # AI & Workflows
    "enhanced_ai_workflow": "enhanced_ai_workflow_endpoints:router",
    "advanced_workflow": "advanced_workflow_api:router",
    "evidence_collection": "evidence_collection_api:router",
    "case_studies": "case_studies_api:router",
    "service_integrations": "service_integrations:router",
    "integration_health": "integration_health_endpoints:router",
    
    # Productivity & PM
    "asana": "integrations.asana_routes:router",
    "notion": "integrations.notion_routes:router",
    "linear": "integrations.linear_routes:router",
    "jira": "integrations.jira_routes:router",
    "monday": "integrations.monday_routes:router",
    "trello": "integrations.trello_routes:router",
    "airtable": "integrations.airtable_routes:router",
    "clickup": "integrations.clickup_routes:router",
    "google_calendar": "integrations.google_calendar_routes:router",
    "calendly": "integrations.calendly_routes:router",
    
    # Communication
    "slack": "integrations.slack_routes:router",
    "zoom": "integrations.zoom_routes:router",
    "teams": "integrations.teams_routes:router",
    "gmail": "integrations.gmail_routes:router",
    "email": "integrations.email_routes:router",
    "outlook": "integrations.outlook_routes:router",
    "twilio": "integrations.twilio_routes:router",
    "sendgrid": "integrations.sendgrid_routes:router",
    
    # Storage
    "dropbox": "integrations.dropbox_routes:router",
    "google_drive": "integrations.google_drive_routes:google_drive_router",
    "onedrive": "integrations.onedrive_routes:onedrive_router",
    "microsoft365": "integrations.microsoft365_routes:microsoft365_router",
    "box": "integrations.box_routes:router",
    "zoho_workdrive": "api.zoho_workdrive_routes:router",
    
    # CRM & Support
    "salesforce": "integrations.salesforce_routes:router",
    "hubspot": "integrations.hubspot_routes:router",
    "zendesk": "integrations.zendesk_routes:router",
    "freshdesk": "integrations.freshdesk_routes:router",
    "intercom": "integrations.intercom_routes:router",
    
    # Finance & Commerce
    "stripe": "integrations.stripe_routes:router",
    "shopify": "integrations.shopify_routes:router",
    "xero": "integrations.xero_routes:router",
    "quickbooks": "integrations.quickbooks_routes:router",
    "plaid": "integrations.plaid_routes:router",
    
    # Dev & Design
    "github": "integrations.github_routes:router",
    "figma": "integrations.figma_routes:router",
    
    # Marketing & Social
    "mailchimp": "integrations.mailchimp_routes:router",
    "linkedin": "integrations.linkedin_routes:router",
    
    # Other
    "deepgram": "integrations.deepgram_routes:router",
    "tableau": "integrations.tableau_routes:router",
    
    # PDF Processing
    "pdf_ocr": "integrations.pdf_processing:pdf_ocr_router",
    "pdf_memory": "integrations.pdf_processing:pdf_memory_router",
    
    # Memory
    "atom_memory": "integrations.atom_communication_memory_api:atom_memory_router",
    "atom_memory_production": "integrations.atom_communication_memory_production_api:atom_memory_production_router",
    "atom_memory_webhooks": "integrations.atom_communication_memory_webhooks:atom_memory_webhooks_router",
    "communication_ingestion": "integrations.atom_communication_apps_lancedb_integration:communication_ingestion_router",
    
    # OAuth & Auth
    "oauth": "oauth_routes:router",
    "auth": "core.auth_endpoints:router",
    
    # Team Messaging
    "team_messaging": "core.team_messaging:router",
    
    # Note: formulas, memory, voice, documents are eagerly loaded in main_api_app.py
}

# Essential integrations to load at startup
ESSENTIAL_INTEGRATIONS = [
    "auth",
    "oauth",
    "system_status",
    "service_health",
    # Temporarily disabled - causing backend startup failures
    # "atom_agent",  # Agent chat functionality
    # "unified_calendar",  # Calendar endpoints
    # "unified_task",  # Task management
    # "unified_search",  # Temporarily disabled - LanceDB has Python 3.13 compatibility issues
]


@lru_cache(maxsize=50)
def load_integration(name: str, timeout: int = 5) -> Optional[Any]:
    """
    Dynamically load an integration by name with LRU caching
    
    Args:
        name: Integration name from INTEGRATION_REGISTRY
        timeout: Timeout in seconds (default 5)
        
    Returns:
        Router object or None if failed
    """
    if name not in INTEGRATION_REGISTRY:
        logger.warning(f"Unknown integration: {name}")
        return None
    
    try:
        module_path, attr_name = INTEGRATION_REGISTRY[name].split(":")
        
        # Dynamic import
        logger.info(f"Loading integration: {name} ({module_path})")
        module = importlib.import_module(module_path)
        router = getattr(module, attr_name)
        
        logger.info(f"✓ Loaded {name}")
        return router
        
    except ImportError as e:
        logger.warning(f"✗ {name} not available: {e}")
        return None
    except AttributeError as e:
        logger.error(f"✗ {name} - router not found: {e}")
        return None
    except Exception as e:
        logger.error(f"✗ {name} failed: {e}")
        return None


def get_integration_list() -> Dict[str, str]:
    """Get list of all available integrations"""
    return INTEGRATION_REGISTRY.copy()


def get_loaded_integrations() -> list:
    """Get list of currently loaded integrations from cache"""
    cache_info = load_integration.cache_info()
    return {
        "cached": cache_info.currsize,
        "max_size": cache_info.maxsize,
        "hits": cache_info.hits,
        "misses": cache_info.misses,
    }


def clear_integration_cache():
    """Clear the integration cache"""
    load_integration.cache_clear()
    logger.info("Integration cache cleared")
