import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import uvicorn

# Import our modules
from core.api_routes import router
from service_health_endpoints import router as service_health_router
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Import PDF processing routes
try:
    from integrations.pdf_processing import pdf_memory_router, pdf_ocr_router

    PDF_PROCESSING_AVAILABLE = True
except ImportError as e:
    print(f"PDF Processing integration not available: {e}")
    PDF_PROCESSING_AVAILABLE = False
    pdf_ocr_router = None
    pdf_memory_router = None

# Import memory integration routes
try:
    from integrations.atom_communication_memory_api import atom_memory_router

    ATOM_MEMORY_AVAILABLE = True
except ImportError as e:
    print(f"ATOM Communication Memory API not available: {e}")
    ATOM_MEMORY_AVAILABLE = False
    atom_memory_router = None

try:
    from integrations.atom_communication_memory_production_api import (
        atom_memory_production_router,
    )

    ATOM_MEMORY_PRODUCTION_AVAILABLE = True
except ImportError as e:
    print(f"ATOM Communication Memory Production API not available: {e}")
    ATOM_MEMORY_PRODUCTION_AVAILABLE = False
    atom_memory_production_router = None

try:
    from integrations.atom_communication_memory_webhooks import (
        atom_memory_webhooks_router,
    )

    ATOM_MEMORY_WEBHOOKS_AVAILABLE = True
except ImportError as e:
    print(f"ATOM Communication Memory Webhooks not available: {e}")
    ATOM_MEMORY_WEBHOOKS_AVAILABLE = False
    atom_memory_webhooks_router = None

# Import communication ingestion router
try:
    from integrations.atom_communication_apps_lancedb_integration import (
        communication_ingestion_router,
    )

    COMMUNICATION_INGESTION_AVAILABLE = True
except ImportError as e:
    print(f"Communication ingestion router not available: {e}")
    COMMUNICATION_INGESTION_AVAILABLE = False
    communication_ingestion_router = None

# Import enterprise modules
try:
    from core.enterprise_user_management import router as enterprise_user_router

    ENTERPRISE_USER_MGMT_AVAILABLE = True
except ImportError as e:
    print(f"Enterprise user management not available: {e}")
    ENTERPRISE_USER_MGMT_AVAILABLE = False
    enterprise_user_router = None

try:
    from core.enterprise_security import router as enterprise_security_router

    ENTERPRISE_SECURITY_AVAILABLE = True
except ImportError as e:
    print(f"Enterprise security not available: {e}")
    ENTERPRISE_SECURITY_AVAILABLE = False
    enterprise_security_router = None

# Import new endpoint modules
try:
    from core.service_registry import router as service_registry_router

    SERVICE_REGISTRY_AVAILABLE = True
except ImportError as e:
    print(f"Service registry not available: {e}")
    SERVICE_REGISTRY_AVAILABLE = False
    service_registry_router = None

try:
    from core.system_status import router as system_status_router

    SYSTEM_STATUS_AVAILABLE = True
except ImportError as e:
    print(f"System status not available: {e}")
    SYSTEM_STATUS_AVAILABLE = False
    system_status_router = None

try:
    from core.workflow_endpoints import router as workflow_router

    WORKFLOW_AVAILABLE = True
except ImportError as e:
    print(f"Workflow endpoints not available: {e}")
    WORKFLOW_AVAILABLE = False
    workflow_router = None

try:
    from core.analytics_endpoints import router as analytics_router

    ANALYTICS_AVAILABLE = True
except ImportError as e:
    print(f"Analytics endpoints not available: {e}")
    ANALYTICS_AVAILABLE = False
    analytics_router = None

try:
    from core.enterprise_endpoints import router as enterprise_router

    ENTERPRISE_AVAILABLE = True
except ImportError as e:
    print(f"Enterprise endpoints not available: {e}")
    ENTERPRISE_AVAILABLE = False
    enterprise_router = None

try:
    from core.byok_endpoints import router as byok_router

    BYOK_AVAILABLE = True
except ImportError as e:
    print(f"BYOK endpoints not available: {e}")
    BYOK_AVAILABLE = False
    byok_router = None

# Import Asana integration
try:
    from integrations.asana_routes import router as asana_router

    ASANA_AVAILABLE = True
except ImportError as e:
    print(f"Asana integration not available: {e}")
    ASANA_AVAILABLE = False
    asana_router = None

# Import Notion integration
try:
    from integrations.notion_routes import router as notion_router

    NOTION_AVAILABLE = True
except ImportError as e:
    print(f"Notion integration not available: {e}")
    NOTION_AVAILABLE = False
    notion_router = None

# Import Linear integration
try:
    from integrations.linear_routes import router as linear_router

    LINEAR_AVAILABLE = True
except ImportError as e:
    print(f"Linear integration not available: {e}")
    LINEAR_AVAILABLE = False
    linear_router = None

# Import Outlook integration
try:
    from integrations.outlook_routes import router as outlook_router

    OUTLOOK_AVAILABLE = True
except ImportError as e:
    print(f"Outlook integration not available: {e}")
    OUTLOOK_AVAILABLE = False
    outlook_router = None

# Import Dropbox integration
try:
    from integrations.dropbox_routes import router as dropbox_router

    DROPBOX_AVAILABLE = True
except ImportError as e:
    print(f"Dropbox integration not available: {e}")
    DROPBOX_AVAILABLE = False
    dropbox_router = None

# Import Google Drive integration
try:
    from integrations.google_drive_routes import google_drive_router

    GOOGLE_DRIVE_AVAILABLE = True
except ImportError as e:
    print(f"Google Drive integration not available: {e}")
    GOOGLE_DRIVE_AVAILABLE = False
    google_drive_router = None

# Import OneDrive integration
try:
    from integrations.onedrive_routes import onedrive_router

    ONEDRIVE_AVAILABLE = True
except ImportError as e:
    print(f"OneDrive integration not available: {e}")
    ONEDRIVE_AVAILABLE = False
    onedrive_router = None

# Import Microsoft 365 integration
try:
    from integrations.microsoft365_routes import microsoft365_router

    MICROSOFT365_AVAILABLE = True
except ImportError as e:
    print(f"Microsoft 365 integration not available: {e}")
    MICROSOFT365_AVAILABLE = False
    microsoft365_router = None

# Import Box integration
try:
    from integrations.box_routes import router as box_router

    BOX_AVAILABLE = True
except ImportError as e:
    print(f"Box integration not available: {e}")
    BOX_AVAILABLE = False
    box_router = None

# Import Stripe integration
try:
    from integrations.stripe_routes import router as stripe_router

    STRIPE_AVAILABLE = True
except ImportError as e:
    print(f"Stripe integration not available: {e}")
    STRIPE_AVAILABLE = False
    stripe_router = None

# Import Salesforce integration
try:
    from integrations.salesforce_routes import router as salesforce_router

    SALESFORCE_AVAILABLE = True
except ImportError as e:
    print(f"Salesforce integration not available: {e}")
    SALESFORCE_AVAILABLE = False
    salesforce_router = None

# Import Email integration
try:
    from integrations.email_routes import router as email_router
    EMAIL_AVAILABLE = True
except ImportError as e:
    print(f"Email integration not available: {e}")
    EMAIL_AVAILABLE = False
    email_router = None

# Import Slack integration
try:
    from integrations.slack_routes import router as slack_router
    SLACK_AVAILABLE = True
except ImportError as e:
    print(f"Slack integration not available: {e}")
    SLACK_AVAILABLE = False
    slack_router = None

# Import Zoom integration
try:
    from integrations.zoom_routes import router as zoom_router

    ZOOM_AVAILABLE = True
except ImportError as e:
    print(f"Zoom integration not available: {e}")
    ZOOM_AVAILABLE = False
    zoom_router = None

# Import Enhanced AI Workflow endpoints
try:
    from enhanced_ai_workflow_endpoints import router as enhanced_ai_router

    ENHANCED_AI_AVAILABLE = True
except ImportError as e:
    print(f"Enhanced AI workflow endpoints not available: {e}")
    ENHANCED_AI_AVAILABLE = False
    enhanced_ai_router = None

# Import service integrations for unified service endpoints
try:
    from service_integrations import router as service_integrations_router

    SERVICE_INTEGRATIONS_AVAILABLE = True
except ImportError as e:
    print(f"Service integrations not available: {e}")
    SERVICE_INTEGRATIONS_AVAILABLE = False
    service_integrations_router = None

# Import Advanced Workflow Orchestrator
try:
    from advanced_workflow_api import router as advanced_workflow_router

    ADVANCED_WORKFLOW_AVAILABLE = True
except ImportError as e:
    print(f"Advanced workflow orchestrator not available: {e}")
    ADVANCED_WORKFLOW_AVAILABLE = False
    advanced_workflow_router = None

# Import Evidence Collection Framework
try:
    from evidence_collection_api import router as evidence_router

    EVIDENCE_COLLECTION_AVAILABLE = True
except ImportError as e:
    print(f"Evidence collection framework not available: {e}")
    EVIDENCE_COLLECTION_AVAILABLE = False
    evidence_router = None

# Import Case Studies Framework
try:
    from case_studies_api import router as case_studies_router

    CASE_STUDIES_AVAILABLE = True
except ImportError as e:
    print(f"Case studies framework not available: {e}")
    CASE_STUDIES_AVAILABLE = False
    case_studies_router = None

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

# Include API routes
app.include_router(router, prefix="/api/v1")
app.include_router(service_health_router, prefix="")

# Include Asana integration routes if available
if ASANA_AVAILABLE and asana_router:
    app.include_router(asana_router)
    print("✅ Asana integration routes loaded")
else:
    print("⚠️  Asana integration routes not available")

# Include Notion integration routes if available
if NOTION_AVAILABLE and notion_router:
    app.include_router(notion_router)
    print("✅ Notion integration routes loaded")
else:
    print("⚠️  Notion integration routes not available")

# Include Linear integration routes if available
if LINEAR_AVAILABLE and linear_router:
    app.include_router(linear_router)
    print("✅ Linear integration routes loaded")
else:
    print("⚠️  Linear integration routes not available")

# Include Outlook integration routes if available
if OUTLOOK_AVAILABLE and outlook_router:
    app.include_router(outlook_router)
    print("✅ Outlook integration routes loaded")
else:
    print("⚠️  Outlook integration routes not available")

# Include Dropbox integration routes if available
if DROPBOX_AVAILABLE and dropbox_router:
    app.include_router(dropbox_router)
    print("✅ Dropbox integration routes loaded")
else:
    print("⚠️  Dropbox integration routes not available")

# Include Stripe integration routes if available
if STRIPE_AVAILABLE and stripe_router:
    app.include_router(stripe_router)
    print("✅ Stripe integration routes loaded")
else:
    print("⚠️  Stripe integration routes not available")

# Include Google Drive integration routes if available
if GOOGLE_DRIVE_AVAILABLE and google_drive_router:
    app.include_router(google_drive_router)
    print("✅ Google Drive integration routes loaded")
else:
    print("⚠️  Google Drive integration routes not available")

# Include OneDrive integration routes if available
if ONEDRIVE_AVAILABLE and onedrive_router:
    app.include_router(onedrive_router)
    print("✅ OneDrive integration routes loaded")
else:
    print("⚠️  OneDrive integration routes not available")

# Include Microsoft 365 integration routes if available
if MICROSOFT365_AVAILABLE and microsoft365_router:
    app.include_router(microsoft365_router)
    print("✅ Microsoft 365 integration routes loaded")
else:
    print("⚠️  Microsoft 365 integration routes not available")

# Include Box integration routes if available
if BOX_AVAILABLE and box_router:
    app.include_router(box_router)
    print("✅ Box integration routes loaded")
else:
    print("⚠️  Box integration routes not available")

# Include BYOK routes if available
if BYOK_AVAILABLE and byok_router:
    app.include_router(byok_router)
    print("✅ BYOK AI provider management routes loaded")
else:
    print("⚠️  BYOK AI provider management routes not available")

# Include Service Integrations routes if available
if SERVICE_INTEGRATIONS_AVAILABLE and service_integrations_router:
    app.include_router(service_integrations_router)
    print("✅ Comprehensive service integrations routes loaded (16 services)")
else:
    print("⚠️  Service integrations routes not available")

# Import integration health endpoints
try:
    from integration_health_endpoints import router as integration_health_router
    INTEGRATION_HEALTH_AVAILABLE = True
    print("✅ Integration health endpoints imported")
except ImportError as e:
    print(f"⚠️ Integration health endpoints not available: {e}")
    INTEGRATION_HEALTH_AVAILABLE = False
    integration_health_router = None

# Include integration health endpoints
if INTEGRATION_HEALTH_AVAILABLE and integration_health_router:
    app.include_router(integration_health_router)
    print("✅ Integration health endpoints loaded (33+ services)")
else:
    print("⚠️ Integration health endpoints not available")

# Import AI workflow endpoints
try:
    from enhanced_ai_workflow_endpoints import router as ai_workflow_router
    AI_WORKFLOW_AVAILABLE = True
    print("✅ Enhanced AI workflow endpoints with real AI processing imported")
except ImportError as e:
    print(f"⚠️ Enhanced AI workflow endpoints not available: {e}")
    # Fallback to original endpoints if enhanced ones fail
    try:
        from ai_workflow_endpoints import router as ai_workflow_router
        AI_WORKFLOW_AVAILABLE = True
        print("⚠️ Using fallback AI workflow endpoints (simulated)")
    except ImportError as e2:
        print(f"⚠️ All AI workflow endpoints not available: {e2}")
        AI_WORKFLOW_AVAILABLE = False
        ai_workflow_router = None

# Include AI workflow endpoints
if AI_WORKFLOW_AVAILABLE and ai_workflow_router:
    app.include_router(ai_workflow_router)
    print("✅ AI workflow endpoints loaded")
else:
    print("⚠️ AI workflow endpoints not available")

# Include Enhanced AI workflow endpoints if available
if ENHANCED_AI_AVAILABLE and enhanced_ai_router:
    app.include_router(enhanced_ai_router)
    print("✅ Enhanced AI workflow endpoints with real AI processing loaded")
else:
    print("⚠️ Enhanced AI workflow endpoints not available")

# Include Advanced Workflow Orchestrator if available
if ADVANCED_WORKFLOW_AVAILABLE and advanced_workflow_router:
    app.include_router(advanced_workflow_router)
    print("✅ Advanced workflow orchestrator loaded")
else:
    print("⚠️ Advanced workflow orchestrator not available")

# Include Evidence Collection Framework if available
if EVIDENCE_COLLECTION_AVAILABLE and evidence_router:
    app.include_router(evidence_router)
    print("✅ Evidence collection framework loaded")
else:
    print("⚠️ Evidence collection framework not available")

# Include Case Studies Framework if available
if CASE_STUDIES_AVAILABLE and case_studies_router:
    app.include_router(case_studies_router)
    print("✅ Real-world case studies framework loaded")
else:
    print("⚠️ Case studies framework not available")

# Include PDF processing routes if available
if PDF_PROCESSING_AVAILABLE and pdf_ocr_router:
    app.include_router(pdf_ocr_router, prefix="/api/v1")
    print("✅ PDF OCR processing routes loaded")
else:
    print("⚠️  PDF OCR processing routes not available")

# Include PDF memory integration routes if available
if PDF_PROCESSING_AVAILABLE and pdf_memory_router:
    app.include_router(pdf_memory_router, prefix="/api/v1")
    print("✅ PDF memory integration routes loaded")
else:
    print("⚠️  PDF memory integration routes not available")

# Include Salesforce integration routes if available
if SALESFORCE_AVAILABLE and salesforce_router:
    app.include_router(salesforce_router)
    print("✅ Salesforce integration routes loaded")
else:
    print("⚠️  Salesforce integration routes not available")

# Include Email API routes
if EMAIL_AVAILABLE and email_router:
    app.include_router(email_router)
    print("✅ Email integration routes loaded (Gmail/Outlook)")
else:
    print("⚠️  Email integration routes not available")

# Include Slack API routes
if SLACK_AVAILABLE and slack_router:
    app.include_router(slack_router)
    print("✅ Slack integration routes loaded")
else:
    print("⚠️  Slack integration routes not available")

# Include Zoom API routes
if ZOOM_AVAILABLE and zoom_router:
    app.include_router(zoom_router)
    print("✅ Zoom integration routes loaded")
else:
    print("⚠️  Zoom integration routes not available")

# Include GitHub integration routes if available
try:
    from integrations.github_routes import router as github_router

    GITHUB_AVAILABLE = True
except ImportError as e:
    print(f"GitHub integration not available: {e}")
    GITHUB_AVAILABLE = False
    github_router = None

if GITHUB_AVAILABLE and github_router:
    app.include_router(github_router)
    print("✅ GitHub integration routes loaded")
else:
    print("⚠️  GitHub integration routes not available")

# Include Zoom integration routes if available
if ZOOM_AVAILABLE and zoom_router:
    app.include_router(zoom_router)
    print("✅ Zoom integration routes loaded")
else:
    print("⚠️  Zoom integration routes not available")

# Include ATOM Communication Memory API routes if available
if ATOM_MEMORY_AVAILABLE and atom_memory_router:
    app.include_router(atom_memory_router)
    print("✅ ATOM Communication Memory API routes loaded")
else:
    print("⚠️  ATOM Communication Memory API routes not available")

# Include ATOM Communication Memory Production API routes if available
if ATOM_MEMORY_PRODUCTION_AVAILABLE and atom_memory_production_router:
    app.include_router(atom_memory_production_router)
    print("✅ ATOM Communication Memory Production API routes loaded")
else:
    print("⚠️  ATOM Communication Memory Production API routes not available")

# Include ATOM Communication Memory Webhooks routes if available
if ATOM_MEMORY_WEBHOOKS_AVAILABLE and atom_memory_webhooks_router:
    app.include_router(atom_memory_webhooks_router)
    print("✅ ATOM Communication Memory Webhooks routes loaded")
else:
    print("⚠️  ATOM Communication Memory Webhooks routes not available")

# Include Communication Ingestion routes if available
if COMMUNICATION_INGESTION_AVAILABLE and communication_ingestion_router:
    app.include_router(communication_ingestion_router)
    print("✅ Communication Ingestion routes loaded")
else:
    print("⚠️  Communication Ingestion routes not available")

# Include Tableau integration routes if available
try:
    from integrations.tableau_routes import router as tableau_router

    TABLEAU_AVAILABLE = True
except ImportError as e:
    print(f"Tableau integration not available: {e}")
    TABLEAU_AVAILABLE = False
    tableau_router = None

if TABLEAU_AVAILABLE and tableau_router:
    app.include_router(tableau_router)
    print("✅ Tableau integration routes loaded")
else:
    print("⚠️  Tableau integration routes not available")

# Include Box integration routes if available
try:
    from integrations.box_routes import router as box_router

    BOX_AVAILABLE = True
except ImportError as e:
    print(f"Box integration not available: {e}")
    BOX_AVAILABLE = False
    box_router = None

if BOX_AVAILABLE and box_router:
    app.include_router(box_router)
    print("✅ Box integration routes loaded")
else:
    print("⚠️  Box integration routes not available")

# Include WhatsApp Business integration routes if available
try:
    from integrations.whatsapp_fastapi_routes import (
        initialize_whatsapp_service,
        register_whatsapp_routes,
    )
    from integrations.workflow_automation_routes import router as workflow_router

    WHATSAPP_AVAILABLE = True
    print("✅ WhatsApp Business FastAPI routes imported")
except ImportError as e:
    print(f"WhatsApp integration not available: {e}")
    WHATSAPP_AVAILABLE = False

# Register WhatsApp routes and initialize service
if WHATSAPP_AVAILABLE:
    # Register routes with FastAPI app
    try:
        whatsapp_routes_registered = register_whatsapp_routes(app)
        if whatsapp_routes_registered:
            print("✅ WhatsApp Business integration routes loaded")
        else:
            print("⚠️  WhatsApp Business integration routes failed to load")
            WHATSAPP_AVAILABLE = False
    except Exception as e:
        print(f"⚠️  WhatsApp Business routes registration error: {e}")
        WHATSAPP_AVAILABLE = False

    # Initialize WhatsApp service
    try:
        whatsapp_service_initialized = initialize_whatsapp_service()
        if whatsapp_service_initialized:
            print("✅ WhatsApp Business service initialized")
        else:
            print("⚠️  WhatsApp Business service initialization failed")
    except Exception as e:
        print(f"⚠️  WhatsApp Business service initialization error: {e}")

# Register workflow automation routes
if workflow_router:
    app.include_router(workflow_router, prefix="/workflows")
    print("✅ Enhanced workflow automation routes loaded")
else:
    print("⚠️  Workflow automation routes not available")

# Register analytics routes
if ANALYTICS_AVAILABLE and analytics_router:
    app.include_router(analytics_router)
    print("✅ Real-time analytics routes loaded")
else:
    print("⚠️  Real-time analytics routes not available")

# Register enterprise routes
if ENTERPRISE_AVAILABLE and enterprise_router:
    app.include_router(enterprise_router)
    print("✅ Enterprise reliability routes loaded")
else:
    print("⚠️  Enterprise reliability routes not available")

# Register enterprise user management routes
if ENTERPRISE_USER_MGMT_AVAILABLE and enterprise_user_router:
    app.include_router(enterprise_user_router, prefix="/api/v1")
    print("✅ Enterprise user management routes loaded")
else:
    print("⚠️  Enterprise user management routes not available")

# Register enterprise security routes
if ENTERPRISE_SECURITY_AVAILABLE and enterprise_security_router:
    app.include_router(enterprise_security_router, prefix="/api/v1")
    print("✅ Enterprise security routes loaded")
else:
    print("⚠️  Enterprise security routes not available")


# Add health endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "ATOM Platform Backend is running",
        "version": "1.0.0",
    }


# Add root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "ATOM Platform",
        "description": "Complete AI-powered automation platform",
        "status": "running",
        "docs": "/docs",
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5058)
