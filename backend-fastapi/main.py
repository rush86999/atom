from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uvicorn
from datetime import datetime, timedelta
import uuid
import json

# Import route modules
from routes.search import router as search_router
from routes.tasks import router as tasks_router
from routes.workflows import router as workflows_router
from routes.services import router as services_router

# Create FastAPI application
app = FastAPI(
    title="ATOM Automation Platform API",
    description="Enterprise automation platform for GitHub, Google, and Slack workflows",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route modules
app.include_router(search_router, prefix="/api/v1", tags=["search"])
app.include_router(tasks_router, prefix="/api/v1", tags=["tasks"])
app.include_router(workflows_router, prefix="/api/v1", tags=["workflows"])
app.include_router(services_router, prefix="/api/v1", tags=["services"])

# Health check endpoint
@app.get("/")
async def root():
    return {
        "message": "ATOM Automation Platform API",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

# Health check endpoint for API
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "api_version": "1.0.0"
    }

# Application info endpoint
@app.get("/info")
async def app_info():
    return {
        "name": "ATOM Automation Platform",
        "description": "Enterprise automation platform",
        "version": "1.0.0",
        "endpoints": {
            "search": "/api/v1/search",
            "tasks": "/api/v1/tasks",
            "workflows": "/api/v1/workflows",
            "services": "/api/v1/services"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
