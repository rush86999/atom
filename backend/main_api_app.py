import os
from pathlib import Path
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.integration_loader import IntegrationLoader

# Load environment variables from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Initialize FastAPI app
app = FastAPI(
    title="ATOM API",
    description="Advanced Task Orchestration & Management API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Integration Loader
loader = IntegrationLoader()

# Core Routes (Always loaded)
try:
    from core.api_routes import router as core_router
    app.include_router(core_router, prefix="/api/v1")

    from core.workflow_endpoints import router as workflow_router
    app.include_router(workflow_router, prefix="/api/v1", tags=["Workflows"])

    # Include OAuth routers
    from oauth_routes import router as oauth_router # Assuming oauth_routes is a top-level module
    app.include_router(oauth_router, prefix="/api/auth", tags=["OAuth"])

except ImportError as e:
    print(f"[CRITICAL] Core API routes failed to load: {e}")

# Define Integrations to Load
# Format: (module_path, router_name, prefix (optional))
integrations = [
    # Core Modules
    ("core.workflow_ui_endpoints", "router", None),
    ("core.atom_agent_endpoints", "router", None),
    ("core.missing_endpoints", "router", None),
    ("core.service_registry", "router", None),
    ("core.byok_endpoints", "router", None),
    ("core.system_status", "router", None),
    ("service_health_endpoints", "router", None),
    ("core.workflow_endpoints", "router", None),
    ("core.analytics_endpoints", "router", None),
    ("core.enterprise_endpoints", "router", None),
    ("core.workflow_marketplace", "router", None),
    ("core.enterprise_user_management", "router", "/api/v1"),
    ("core.enterprise_security", "router", "/api/v1"),
    
    # Unified Endpoints
    ("core.unified_task_endpoints", "router", None),
    ("core.unified_task_endpoints", "project_router", None),
    ("core.unified_calendar_endpoints", "router", None),
    ("core.unified_search_endpoints", "router", None),

    # AI & Workflows
    ("enhanced_ai_workflow_endpoints", "router", None),
    ("advanced_workflow_api", "router", None),
    ("evidence_collection_api", "router", None),
    ("case_studies_api", "router", None),
    ("service_integrations", "router", None),
    ("integration_health_endpoints", "router", None),

    # Integrations - Productivity & PM
    ("integrations.asana_routes", "router", None),
    ("integrations.notion_routes", "router", None),
    ("integrations.linear_routes", "router", None),
    ("integrations.jira_routes", "router", None),
    ("integrations.monday_routes", "router", None),
    ("integrations.trello_routes", "router", None),
    ("integrations.airtable_routes", "router", None),
    ("integrations.clickup_routes", "router", None), # Added if exists
    ("integrations.google_calendar_routes", "router", None),
    ("integrations.calendly_routes", "router", None),

    # Integrations - Communication
    ("integrations.slack_routes", "router", None),
    ("integrations.zoom_routes", "router", None),
    ("integrations.teams_routes", "router", None),
    ("integrations.gmail_routes", "router", None),
    ("integrations.email_routes", "router", None),
    ("integrations.outlook_routes", "router", None),
    ("integrations.twilio_routes", "router", None),
    ("integrations.sendgrid_routes", "router", None),
    
    # Integrations - Storage
    ("integrations.dropbox_routes", "router", None),
    ("integrations.google_drive_routes", "google_drive_router", None),
    ("integrations.onedrive_routes", "onedrive_router", None),
    ("integrations.microsoft365_routes", "microsoft365_router", None),
    ("integrations.box_routes", "router", None),

    # Integrations - CRM & Support
    ("integrations.salesforce_routes", "router", None),
    ("integrations.hubspot_routes", "router", None),
    ("integrations.zendesk_routes", "router", None),
    ("integrations.freshdesk_routes", "router", None),
    ("integrations.intercom_routes", "router", None),

    # Integrations - Finance & Commerce
    ("integrations.stripe_routes", "router", None),
    ("integrations.shopify_routes", "router", None),
    ("integrations.xero_routes", "router", None),
    ("integrations.quickbooks_routes", "router", None),
    ("integrations.plaid_routes", "router", None),

    # Integrations - Dev & Design
    ("integrations.github_routes", "router", None),
    ("integrations.figma_routes", "router", None),

    # Integrations - Marketing & Social
    ("integrations.mailchimp_routes", "router", "/api"),
    ("integrations.linkedin_routes", "router", None),

    # Integrations - Other
    ("integrations.deepgram_routes", "router", None),
    ("integrations.tableau_routes", "router", None),
    
    # PDF Processing
    ("integrations.pdf_processing", "pdf_ocr_router", "/api/v1"),
    ("integrations.pdf_processing", "pdf_memory_router", "/api/v1"),

    # Memory
    ("integrations.atom_communication_memory_api", "atom_memory_router", None),
    ("integrations.atom_communication_memory_production_api", "atom_memory_production_router", None),
    ("integrations.atom_communication_memory_webhooks", "atom_memory_webhooks_router", None),
    ("integrations.atom_communication_apps_lancedb_integration", "communication_ingestion_router", None),
    
    # OAuth Authentication
    ("oauth_routes", "router", None),
    
    # Core Authentication (Password Reset)
    ("core.auth_endpoints", "router", None),
]

# Load and Mount Integrations
for entry in integrations:
    module, router_name, prefix = entry
    router = loader.load_integration(module, router_name)
    if router:
        if prefix:
            app.include_router(router, prefix=prefix)
        else:
            app.include_router(router)

# Special Handling: WhatsApp Business
try:
    from integrations.whatsapp_fastapi_routes import (
        initialize_whatsapp_service,
        register_whatsapp_routes,
    )
    if register_whatsapp_routes(app):
        print("[OK] WhatsApp Business integration routes loaded")
        try:
            if initialize_whatsapp_service():
                print("[OK] WhatsApp Business service initialized")
        except Exception as e:
            print(f"[WARN] WhatsApp Business service initialization error: {e}")
except ImportError as e:
    print(f"[WARN] WhatsApp integration not available: {e}")

# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "ATOM Platform Backend is running",
        "version": "1.0.0",
        "loaded_integrations": len(loader.get_loaded_integrations())
    }

# Root Endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "ATOM Platform",
        "description": "Complete AI-powered automation platform",
        "status": "running",
        "docs": "/docs",
    }

# Scheduler Lifecycle
@app.on_event("startup")
async def start_scheduler():
    from ai.workflow_scheduler import workflow_scheduler
    workflow_scheduler.start()
    print("[OK] Workflow Scheduler started")

@app.on_event("shutdown")
async def stop_scheduler():
    from ai.workflow_scheduler import workflow_scheduler
    workflow_scheduler.shutdown()
    print("[OK] Workflow Scheduler shutdown")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5059)
