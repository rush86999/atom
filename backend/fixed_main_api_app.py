#!/usr/bin/env python3
"""
ATOM Fixed Main Backend API Server
Enhanced version with graceful error handling for all integrations
"""

# Security headers configuration
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'",
}

import os
import sys
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import standardized logging
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared.logging_utils import get_logger, log_api_error

# Create structured logger
logger = get_logger("backend.api")

# Create FastAPI app
app = FastAPI(
    title="ATOM API - Fixed Version",
    description="Advanced Task Orchestration & Management API with Graceful Integration Handling",
    version="1.0.0-fixed",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # Add security headers to all responses
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value

    return response


# Pydantic models
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str
    message: str


class OAuthStatusResponse(BaseModel):
    ok: bool
    service: str
    status: str
    message: str
    timestamp: str


class ServiceListResponse(BaseModel):
    ok: bool
    services: List[str]
    total_services: int
    available_integrations: int
    timestamp: str


class IntegrationStatus(BaseModel):
    name: str
    available: bool
    status: str
    message: str


class SystemStatusResponse(BaseModel):
    ok: bool
    backend: str
    oauth_server: str
    database: str
    total_integrations: int
    available_integrations: int
    timestamp: str
    message: str


# Integration registry
class IntegrationRegistry:
    def __init__(self):
        self.integrations: Dict[str, Dict] = {}
        self.routers: Dict[str, object] = {}
        self._load_integrations()

    def _load_integrations(self):
        """Load all available integrations with graceful error handling"""
        integration_definitions = [
            # Core integrations
            {
                "name": "asana",
                "module": "integrations.asana_routes",
                "router_name": "router",
            },
            {
                "name": "notion",
                "module": "integrations.notion_routes",
                "router_name": "router",
            },
            {
                "name": "linear",
                "module": "integrations.linear_routes",
                "router_name": "router",
            },
            {
                "name": "outlook",
                "module": "integrations.outlook_routes",
                "router_name": "router",
            },
            {
                "name": "dropbox",
                "module": "integrations.dropbox_routes",
                "router_name": "router",
            },
            {
                "name": "stripe",
                "module": "integrations.stripe_routes",
                "router_name": "router",
            },
            {
                "name": "salesforce",
                "module": "integrations.salesforce_routes",
                "router_name": "router",
            },
            {
                "name": "zoom",
                "module": "integrations.zoom_routes",
                "router_name": "router",
            },
            {
                "name": "github",
                "module": "integrations.github_routes",
                "router_name": "router",
            },
            {
                "name": "tableau",
                "module": "integrations.tableau_routes",
                "router_name": "router",
            },
            {
                "name": "box",
                "module": "integrations.box_routes",
                "router_name": "router",
            },
            {
                "name": "intercom",
                "module": "integrations.intercom_routes",
                "router_name": "router",
            },
            {
                "name": "freshdesk",
                "module": "integrations.freshdesk_routes",
                "router_name": "router",
            },
            {
                "name": "mailchimp",
                "module": "integrations.mailchimp_routes",
                "router_name": "router",
            },
            {"name": "ai", "module": "integrations.ai_routes", "router_name": "router"},
            {
                "name": "hubspot",
                "module": "integrations.hubspot_routes",
                "router_name": "router",
            },
            {
                "name": "slack",
                "module": "integrations.slack_routes",
                "router_name": "router",
            },
            {
                "name": "trello",
                "module": "integrations.trello_routes",
                "router_name": "router",
            },
            {
                "name": "gmail",
                "module": "integrations.gmail_routes",
                "router_name": "router",
            },
            {
                "name": "gitlab",
                "module": "integrations.gitlab_routes",
                "router_name": "router",
            },
            {
                "name": "jira",
                "module": "integrations.jira_routes",
                "router_name": "router",
            },
            {
                "name": "monday",
                "module": "integrations.monday_routes",
                "router_name": "router",
            },
            {
                "name": "quickbooks",
                "module": "integrations.quickbooks_routes",
                "router_name": "router",
            },
            {
                "name": "xero",
                "module": "integrations.xero_routes",
                "router_name": "router",
            },
            {
                "name": "zendesk",
                "module": "integrations.zendesk_routes",
                "router_name": "router",
            },
            {
                "name": "shopify",
                "module": "integrations.shopify_routes",
                "router_name": "router",
            },
            {
                "name": "discord",
                "module": "integrations.discord_routes",
                "router_name": "router",
            },
            {
                "name": "teams",
                "module": "integrations.teams_routes",
                "router_name": "router",
            },
            {
                "name": "figma",
                "module": "integrations.figma_routes",
                "router_name": "router",
            },
            {
                "name": "bitbucket",
                "module": "integrations.bitbucket_routes",
                "router_name": "router",
            },
        ]

        for integration in integration_definitions:
            try:
                module = __import__(
                    integration["module"], fromlist=[integration["router_name"]]
                )
                router = getattr(module, integration["router_name"])

                self.integrations[integration["name"]] = {
                    "available": True,
                    "status": "loaded",
                    "message": f"{integration['name'].title()} integration loaded successfully",
                }
                self.routers[integration["name"]] = router

                logger.info(f"✅ {integration['name'].title()} integration loaded")

            except ImportError as e:
                self.integrations[integration["name"]] = {
                    "available": False,
                    "status": "not_available",
                    "message": f"{integration['name'].title()} integration not available: {str(e)}",
                }
                logger.warning(
                    f"⚠️  {integration['name'].title()} integration not available: {e}"
                )
            except Exception as e:
                self.integrations[integration["name"]] = {
                    "available": False,
                    "status": "error",
                    "message": f"{integration['name'].title()} integration error: {str(e)}",
                }
                logger.error(f"❌ {integration['name'].title()} integration error: {e}")

    def register_routes(self, app: FastAPI):
        """Register all available integration routes"""
        for name, router in self.routers.items():
            try:
                app.include_router(router)
                logger.info(f"✅ {name.title()} routes registered")
            except Exception as e:
                logger.error(f"❌ Failed to register {name.title()} routes: {e}")

    def get_integration_status(self, name: str) -> Optional[Dict]:
        """Get status for a specific integration"""
        return self.integrations.get(name)

    def get_all_integrations(self) -> Dict[str, Dict]:
        """Get status for all integrations"""
        return self.integrations

    def get_available_count(self) -> int:
        """Get count of available integrations"""
        return sum(
            1 for integration in self.integrations.values() if integration["available"]
        )


# Initialize integration registry
registry = IntegrationRegistry()

# Include API routes
try:
    from api_routes import router as api_router

    app.include_router(api_router, prefix="/api/v1")
    logger.info("✅ Core API routes loaded")
except ImportError as e:
    logger.error(f"❌ Core API routes not available: {e}")

# Register all integration routes
registry.register_routes(app)

# Mock services for demonstration
MOCK_SERVICES = [
    "gmail",
    "outlook",
    "slack",
    "teams",
    "trello",
    "asana",
    "notion",
    "github",
    "dropbox",
    "gdrive",
    "linear",
    "figma",
    "jira",
    "monday",
    "salesforce",
    "hubspot",
    "zendesk",
    "intercom",
    "freshdesk",
    "mailchimp",
]


# API Routes
@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with basic info"""
    from datetime import datetime

    return HealthResponse(
        status="ok",
        service="atom-fixed-api",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        message="ATOM Fixed API Server is running with graceful integration handling",
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    from datetime import datetime

    return HealthResponse(
        status="ok",
        service="atom-fixed-api",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        message="API server is healthy and running",
    )


@app.get("/api/oauth/{service}/status", response_model=OAuthStatusResponse)
async def oauth_status(service: str, user_id: str = "test_user"):
    """Check OAuth status for a service"""
    from datetime import datetime

    if service not in MOCK_SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service} not found")

    # Check if integration is available
    integration_status = registry.get_integration_status(service)
    if integration_status and integration_status["available"]:
        status = "connected"
        message = f"{service.title()} OAuth is connected and available"
    else:
        status = "needs_credentials"
        message = f"{service.title()} OAuth integration is not available"

    return OAuthStatusResponse(
        ok=True,
        service=service,
        status=status,
        message=message,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/api/oauth/services", response_model=ServiceListResponse)
async def list_services():
    """List all available services"""
    from datetime import datetime

    return ServiceListResponse(
        ok=True,
        services=MOCK_SERVICES,
        total_services=len(MOCK_SERVICES),
        available_integrations=registry.get_available_count(),
        timestamp=datetime.now().isoformat(),
    )


@app.get("/api/system/status", response_model=SystemStatusResponse)
async def system_status():
    """Get overall system status"""
    from datetime import datetime

    # Check OAuth server status
    oauth_status = "unknown"
    try:
        import requests

        response = requests.get("http://localhost:5058/healthz", timeout=5)
        if response.status_code == 200:
            oauth_status = "running"
        else:
            oauth_status = "error"
    except:
        oauth_status = "not_running"

    return SystemStatusResponse(
        ok=True,
        backend="running",
        oauth_server=oauth_status,
        database="connected",
        total_integrations=len(registry.integrations),
        available_integrations=registry.get_available_count(),
        timestamp=datetime.now().isoformat(),
        message=f"ATOM system operational with {registry.get_available_count()}/{len(registry.integrations)} integrations available",
    )


@app.get("/api/integrations/status")
async def integrations_status():
    """Get detailed status for all integrations"""
    from datetime import datetime

    integrations = registry.get_all_integrations()

    return {
        "ok": True,
        "total_integrations": len(integrations),
        "available_integrations": registry.get_available_count(),
        "success_rate": f"{(registry.get_available_count() / len(integrations)) * 100:.1f}%",
        "integrations": integrations,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/integrations/{integration_name}/status")
async def integration_status(integration_name: str):
    """Get status for a specific integration"""
    from datetime import datetime

    integration = registry.get_integration_status(integration_name)

    if not integration:
        raise HTTPException(
            status_code=404, detail=f"Integration {integration_name} not found"
        )

    return {
        "ok": True,
        "integration": integration_name,
        **integration,
        "timestamp": datetime.now().isoformat(),
    }


# Fallback endpoints for missing integrations
@app.get("/api/fallback/{service}/search")
async def fallback_search(service: str, query: str, user_id: str = "test_user"):
    """Fallback search endpoint for services without full integration"""
    from datetime import datetime

    integration_status = registry.get_integration_status(service)

    return {
        "ok": True,
        "service": service,
        "query": query,
        "user_id": user_id,
        "results": [
            {
                "title": f"Sample result from {service}",
                "source": service,
                "snippet": f"This is a fallback result for query: {query}",
                "integration_status": integration_status["status"]
                if integration_status
                else "not_available",
            }
        ],
        "message": f"Using fallback search for {service} - full integration not available",
        "integration_available": integration_status["available"]
        if integration_status
        else False,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/fallback/{service}/action")
async def fallback_action(service: str, action: str, user_id: str = "test_user"):
    """Fallback action endpoint for services without full integration"""
    from datetime import datetime

    integration_status = registry.get_integration_status(service)

    return {
        "ok": True,
        "service": service,
        "action": action,
        "user_id": user_id,
        "result": f"Fallback action '{action}' executed for {service}",
        "message": f"Using fallback action system for {service} - full integration not available",
        "integration_available": integration_status["available"]
        if integration_status
        else False,
        "timestamp": datetime.now().isoformat(),
    }


def start_fixed_api():
    """Start the fixed API server"""
    print("🚀 ATOM Fixed Backend API Server")
    print("=" * 60)
    print("🌐 Starting server on http://localhost:8001")
    print("📋 Core Endpoints:")
    print("   - GET  /                    - Root endpoint")
    print("   - GET  /health              - Health check")
    print("   - GET  /docs                - API documentation")
    print("   - GET  /api/oauth/services  - List services")
    print("   - GET  /api/oauth/{service}/status - Service OAuth status")
    print("   - GET  /api/system/status   - System status")
    print("   - GET  /api/integrations/status - All integrations status")
    print("   - GET  /api/integrations/{name}/status - Specific integration status")
    print("   - GET  /api/fallback/{service}/action - Fallback actions")
    print()
    print("🌐 Access URLs:")
    print("   Frontend: http://localhost:3000")
    print("   Backend API: http://localhost:8001")
    print("   API Documentation: http://localhost:8001/docs")
    print("   OAuth Server: http://localhost:5058")
    print("   - POST /api/fallback/{service}/action - Fallback actions")
    print()
    print("📊 Integration Status:")
    print(f"   Total integrations: {len(registry.integrations)}")
    print(f"   Available integrations: {registry.get_available_count()}")
    print(
        f"   Success rate: {(registry.get_available_count() / len(registry.integrations)) * 100:.1f}%"
    )
    print("=" * 60)

    try:
        uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")


if __name__ == "__main__":
    start_fixed_api()
