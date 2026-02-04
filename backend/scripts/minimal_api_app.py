#!/usr/bin/env python3
"""
Minimal Backend API Server for ATOM Platform
Simple FastAPI server that provides core functionality without complex dependencies
"""

import logging
import os
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ATOM Minimal API",
    description="Minimal backend API server for ATOM platform",
    version="1.0.0-minimal",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    services: list
    total_services: int
    timestamp: str


class SearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"


class SearchResponse(BaseModel):
    ok: bool
    query: str
    results: list
    timestamp: str


class ChatRequest(BaseModel):
    message: str
    user_id: str = "test_user"


class ChatResponse(BaseModel):
    ok: bool
    message: str
    response: str
    timestamp: str


# Mock data for demonstration
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
]

MOCK_SEARCH_RESULTS = [
    {
        "title": "Meeting Notes",
        "source": "gmail",
        "snippet": "Discussion about project timelines",
    },
    {
        "title": "Project Plan",
        "source": "notion",
        "snippet": "Complete project roadmap and milestones",
    },
    {
        "title": "Team Updates",
        "source": "slack",
        "snippet": "Weekly team sync meeting notes",
    },
    {
        "title": "Calendar Event",
        "source": "outlook",
        "snippet": "Client meeting scheduled for next week",
    },
    {
        "title": "Task List",
        "source": "asana",
        "snippet": "Pending tasks for current sprint",
    },
]


# API Routes
@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with basic info"""
    return HealthResponse(
        status="ok",
        service="atom-minimal-api",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        message="ATOM Minimal API Server is running",
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="ok",
        service="atom-minimal-api",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        message="API server is healthy and running",
    )


@app.get("/api/oauth/{service}/status", response_model=OAuthStatusResponse)
async def oauth_status(service: str, user_id: str = "test_user"):
    """Check OAuth status for a service"""
    if service not in MOCK_SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service} not found")

    return OAuthStatusResponse(
        ok=True,
        service=service,
        status="connected"
        if service
        in ["gmail", "slack", "trello", "asana", "notion", "dropbox", "gdrive"]
        else "needs_credentials",
        message=f"{service.title()} OAuth is connected"
        if service
        in ["gmail", "slack", "trello", "asana", "notion", "dropbox", "gdrive"]
        else f"{service.title()} OAuth needs credentials",
        timestamp=datetime.now().isoformat(),
    )


@app.get("/api/oauth/services", response_model=ServiceListResponse)
async def list_services():
    """List all available services"""
    return ServiceListResponse(
        ok=True,
        services=MOCK_SERVICES,
        total_services=len(MOCK_SERVICES),
        timestamp=datetime.now().isoformat(),
    )


@app.post("/api/search", response_model=SearchResponse)
async def search_content(request: SearchRequest):
    """Search across all connected services"""
    logger.info(f"Search query: {request.query} from user: {request.user_id}")

    # Filter mock results based on query
    filtered_results = [
        result
        for result in MOCK_SEARCH_RESULTS
        if request.query.lower() in result["title"].lower()
        or request.query.lower() in result["snippet"].lower()
    ]

    return SearchResponse(
        ok=True,
        query=request.query,
        results=filtered_results[:5],  # Limit to 5 results
        timestamp=datetime.now().isoformat(),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_message(request: ChatRequest):
    """Handle chat messages"""
    logger.info(f"Chat message: {request.message} from user: {request.user_id}")

    # Simple response logic
    if "search" in request.message.lower():
        response = "I can help you search across your connected services. Try using the search endpoint or tell me what you're looking for."
    elif "oauth" in request.message.lower() or "connect" in request.message.lower():
        response = "I can help you connect services. Currently available services include Gmail, Slack, Asana, Notion, and more."
    elif "help" in request.message.lower():
        response = "I'm your ATOM assistant. I can help you search across your connected services, manage OAuth connections, and coordinate your workflow."
    else:
        response = f"I received your message: '{request.message}'. I'm here to help you coordinate across your connected services and workflows."

    return ChatResponse(
        ok=True,
        message=request.message,
        response=response,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/api/user/{user_id}/services")
async def get_user_services(user_id: str):
    """Get services connected for a specific user"""
    connected_services = [
        "gmail",
        "slack",
        "trello",
        "asana",
        "notion",
        "dropbox",
        "gdrive",
    ]

    return {
        "ok": True,
        "user_id": user_id,
        "connected_services": connected_services,
        "total_connected": len(connected_services),
        "available_services": MOCK_SERVICES,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/system/status")
async def system_status():
    """Get overall system status"""
    return {
        "ok": True,
        "backend": "running",
        "oauth_server": "running",
        "database": "connected",
        "services_registered": len(MOCK_SERVICES),
        "active_users": 1,
        "timestamp": datetime.now().isoformat(),
        "message": "ATOM system is operational",
    }


def start_minimal_api():
    """Start the minimal API server"""
    print("🚀 ATOM Minimal Backend API Server")
    print("=" * 50)
    print("🌐 Starting server on http://localhost:8000")
    print("📋 Available Endpoints:")
    print("   - GET  /                    - Root endpoint")
    print("   - GET  /health              - Health check")
    print("   - GET  /docs                - API documentation")
    print("   - GET  /api/oauth/services  - List services")
    print("   - GET  /api/oauth/{service}/status - Service OAuth status")
    print("   - POST /api/search          - Search across services")
    print("   - POST /api/chat            - Chat interface")
    print("   - GET  /api/user/{user_id}/services - User services")
    print("   - GET  /api/system/status   - System status")
    print("=" * 50)

    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")


if __name__ == "__main__":
    start_minimal_api()
