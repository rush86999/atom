"""
ATOM Multi-Modal AI Integration - Updated Main FastAPI App
Enhanced with comprehensive multi-modal AI services integration
"""

import os
import sys
import json
import asyncio
import uuid
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
import uvicorn
from loguru import logger
from pydantic import BaseModel

# Add the current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Existing Services
from advanced_ai_models_service import create_advanced_ai_models_service
from multi_model_ai_orchestration_service import create_multi_model_ai_orchestration_service
from advanced_ai_real_time_intelligence_service import create_advanced_ai_real_time_intelligence_service

# New Multi-Modal Services
from vision_ai_service import create_vision_ai_service
from audio_ai_service import create_audio_ai_service
from cross_modal_ai_service import create_cross_modal_ai_service
from multi_modal_workflow_engine import create_multi_modal_workflow_engine
from multi_modal_business_intelligence import create_multi_modal_business_intelligence

# New Multi-Modal Routes
from multi_modal_routes import router as multimodal_router, include_multimodal_router

# Existing Routes
from advanced_ai_routes import router as advanced_ai_router
from multi_model_orchestration_routes import router as orchestration_router
from real_time_intelligence_routes import router as realtime_router

# Configuration
class ATOMConfig:
    """ATOM Multi-Modal AI Configuration"""
    
    # API Configuration
    API_TITLE = "ATOM Multi-Modal AI Platform"
    API_VERSION = "2.0.0"
    API_DESCRIPTION = """
    ATOM Multi-Modal AI Platform - Comprehensive AI Integration
    
    Features:
    • Advanced Multi-Model AI Orchestration
    • Vision AI (Image & Video Analysis)
    • Audio AI (Speech Recognition & Analysis)
    • Cross-Modal Integration & Correlation
    • Multi-Modal Workflow Automation
    • Business Intelligence & Analytics
    • Real-Time Intelligence & Streaming
    • Enterprise-Grade Performance & Security
    """
    
    # Service Configuration
    PYTHON_API_PORT = int(os.getenv("PYTHON_API_PORT", 8000))
    PYTHON_API_HOST = os.getenv("PYTHON_API_HOST", "0.0.0.0")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
    
    # AI Model Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    # Multi-Modal Configuration
    MULTIMODAL_ENABLED = os.getenv("MULTIMODAL_ENABLED", "true").lower() == "true"
    WORKFLOW_ENGINE_ENABLED = os.getenv("WORKFLOW_ENGINE_ENABLED", "true").lower() == "true"
    BUSINESS_INTELLIGENCE_ENABLED = os.getenv("BUSINESS_INTELLIGENCE_ENABLED", "true").lower() == "true"
    
    # Performance Configuration
    MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 100))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 300))
    CACHE_SIZE = int(os.getenv("CACHE_SIZE", 10000))
    
    # CORS Configuration
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    ALLOWED_HEADERS = ["*"]
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        if not cls.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured - OpenAI features will be limited")
        
        if cls.GOOGLE_APPLICATION_CREDENTIALS and not os.path.exists(cls.GOOGLE_APPLICATION_CREDENTIALS):
            logger.warning(f"Google credentials file not found: {cls.GOOGLE_APPLICATION_CREDENTIALS}")

# Global service instances
config = ATOMConfig()
advanced_ai_service = None
orchestration_service = None
realtime_service = None
vision_ai_service = None
audio_ai_service = None
cross_modal_service = None
workflow_engine_service = None
business_intelligence_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    await startup_services()
    
    yield
    
    # Shutdown
    await shutdown_services()

async def startup_services():
    """Initialize all services"""
    global advanced_ai_service, orchestration_service, realtime_service
    global vision_ai_service, audio_ai_service, cross_modal_service
    global workflow_engine_service, business_intelligence_service
    
    logger.info("🚀 Starting ATOM Multi-Modal AI Platform v2.0.0")
    
    try:
        # Validate configuration
        config.validate()
        
        # Initialize Existing Services
        logger.info("🔧 Initializing Core AI Services...")
        advanced_ai_service = create_advanced_ai_models_service()
        orchestration_service = create_multi_model_ai_orchestration_service()
        realtime_service = create_advanced_ai_real_time_intelligence_service()
        
        # Initialize Multi-Modal Services
        if config.MULTIMODAL_ENABLED:
            logger.info("👁️🎧 Initializing Multi-Modal AI Services...")
            vision_ai_service = create_vision_ai_service()
            audio_ai_service = create_audio_ai_service()
            cross_modal_service = create_cross_modal_ai_service()
            
            # Initialize Workflow Engine
            if config.WORKFLOW_ENGINE_ENABLED:
                logger.info("🔄 Initializing Multi-Modal Workflow Engine...")
                workflow_engine_service = create_multi_modal_workflow_engine()
            
            # Initialize Business Intelligence
            if config.BUSINESS_INTELLIGENCE_ENABLED:
                logger.info("📊 Initializing Multi-Modal Business Intelligence...")
                business_intelligence_service = create_multi_modal_business_intelligence()
        
        # Store services in app state
        app.state.services = {
            "advanced_ai": advanced_ai_service,
            "orchestration": orchestration_service,
            "realtime": realtime_service,
            "vision_ai": vision_ai_service,
            "audio_ai": audio_ai_service,
            "cross_modal": cross_modal_service,
            "workflow_engine": workflow_engine_service,
            "business_intelligence": business_intelligence_service,
        }
        
        logger.info("✅ All ATOM AI Services initialized successfully")
        logger.info(f"🌐 Server running on http://{config.PYTHON_API_HOST}:{config.PYTHON_API_PORT}")
        logger.info(f"📖 API Documentation: http://{config.PYTHON_API_HOST}:{config.PYTHON_API_PORT}/docs")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize ATOM services: {e}")
        raise

async def shutdown_services():
    """Shutdown all services"""
    logger.info("🛑 Shutting down ATOM Multi-Modal AI Platform...")
    
    # Cancel background tasks
    tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    logger.info("✅ ATOM services shutdown complete")

# Create FastAPI app with custom OpenAPI
def create_custom_openapi():
    """Create custom OpenAPI schema"""
    if FastAPI.__openapi__:
        return FastAPI.__openapi__
    
    openapi_schema = get_openapi(
        title=config.API_TITLE,
        version=config.API_VERSION,
        description=config.API_DESCRIPTION,
        routes=app.routes,
    )
    
    # Add custom tags for better organization
    openapi_schema["tags"] = [
        {
            "name": "Multi-Modal AI",
            "description": "Vision, Audio, and Cross-Modal AI Services"
        },
        {
            "name": "Workflow Engine",
            "description": "Multi-Modal Workflow Automation"
        },
        {
            "name": "Business Intelligence",
            "description": "Analytics, Dashboards, and Insights"
        },
        {
            "name": "Advanced AI",
            "description": "Multi-Model AI Orchestration"
        },
        {
            "name": "Real-Time Intelligence",
            "description": "Live Streaming and Real-Time Analysis"
        },
        {
            "name": "System",
            "description": "Health, Status, and Monitoring"
        }
    ]
    
    FastAPI.__openapi__ = openapi_schema
    return openapi_schema

# Initialize FastAPI app
app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description=config.API_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=config.ALLOWED_METHODS,
    allow_headers=config.ALLOWED_HEADERS,
)

# Request/response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log HTTP requests and responses"""
    start_time = datetime.utcnow()
    
    # Log request
    logger.info(f"📤 {request.method} {request.url} - Headers: {dict(request.headers)}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    process_time = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"📥 {response.status_code} {request.method} {request.url} - {process_time:.3f}s")
    
    return response

# Error handling middleware
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"❌ Global error: {exc} - {request.url}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "request_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Comprehensive health check for all services"""
    try:
        services = app.state.services
        
        health_status = {
            "status": "healthy",
            "version": config.API_VERSION,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "advanced_ai": {
                    "status": "healthy" if services.get("advanced_ai") else "disabled",
                    "models": len(services.get("advanced_ai").get_available_models()) if services.get("advanced_ai") else 0
                },
                "orchestration": {
                    "status": "healthy" if services.get("orchestration") else "disabled",
                    "strategies": len(["cost", "performance", "hybrid"]) if services.get("orchestration") else 0
                },
                "realtime": {
                    "status": "healthy" if services.get("realtime") else "disabled",
                    "connected_clients": services.get("realtime").active_connections if services.get("realtime") else 0
                }
            }
        }
        
        # Add multi-modal service status if enabled
        if config.MULTIMODAL_ENABLED:
            health_status["services"].update({
                "vision_ai": {
                    "status": "healthy" if services.get("vision_ai") else "disabled",
                    "models": len(services.get("vision_ai").get_available_models()) if services.get("vision_ai") else 0
                },
                "audio_ai": {
                    "status": "healthy" if services.get("audio_ai") else "disabled",
                    "models": len(services.get("audio_ai").get_available_models()) if services.get("audio_ai") else 0
                },
                "cross_modal": {
                    "status": "healthy" if services.get("cross_modal") else "disabled",
                    "tasks": len(services.get("cross_modal").get_service_capabilities().get("supported_tasks", [])) if services.get("cross_modal") else 0
                }
            })
            
            if config.WORKFLOW_ENGINE_ENABLED:
                health_status["services"]["workflow_engine"] = {
                    "status": services.get("workflow_engine").get_engine_status().get("status", "unknown") if services.get("workflow_engine") else "disabled",
                    "workflows": len(services.get("workflow_engine").get_workflow_list()) if services.get("workflow_engine") else 0
                }
            
            if config.BUSINESS_INTELLIGENCE_ENABLED:
                health_status["services"]["business_intelligence"] = {
                    "status": services.get("business_intelligence").get_service_status().get("status", "unknown") if services.get("business_intelligence") else "disabled",
                    "insights": services.get("business_intelligence").get_service_status().get("insights", 0) if services.get("business_intelligence") else 0
                }
        
        # Calculate overall health
        services_healthy = [
            service["status"] == "healthy" 
            for service in health_status["services"].values()
        ]
        
        if all(services_healthy):
            health_status["status"] = "healthy"
        elif any(services_healthy):
            health_status["status"] = "degraded"
        else:
            health_status["status"] = "unhealthy"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Enhanced dashboard endpoint
@app.get("/api/advanced-ai/dashboard")
async def get_dashboard():
    """Comprehensive dashboard with all service metrics"""
    try:
        services = app.state.services
        
        dashboard = {
            "platform": {
                "name": "ATOM Multi-Modal AI Platform",
                "version": config.API_VERSION,
                "features_enabled": {
                    "multimodal_ai": config.MULTIMODAL_ENABLED,
                    "workflow_engine": config.WORKFLOW_ENGINE_ENABLED,
                    "business_intelligence": config.BUSINESS_INTELLIGENCE_ENABLED
                }
            },
            "services": {
                "advanced_ai": services.get("advanced_ai").get_available_models() if services.get("advanced_ai") else {},
                "orchestration": services.get("orchestration").get_service_status() if services.get("orchestration") else {},
                "realtime": services.get("realtime").get_service_status() if services.get("realtime") else {}
            }
        }
        
        # Add multi-modal services if enabled
        if config.MULTIMODAL_ENABLED:
            dashboard["services"].update({
                "vision_ai": services.get("vision_ai").get_available_models() if services.get("vision_ai") else {},
                "audio_ai": services.get("audio_ai").get_available_models() if services.get("audio_ai") else {},
                "cross_modal": services.get("cross_modal").get_service_capabilities() if services.get("cross_modal") else {}
            })
            
            if config.WORKFLOW_ENGINE_ENABLED:
                dashboard["services"]["workflow_engine"] = services.get("workflow_engine").get_engine_status() if services.get("workflow_engine") else {}
            
            if config.BUSINESS_INTELLIGENCE_ENABLED:
                dashboard["services"]["business_intelligence"] = services.get("business_intelligence").get_service_status() if services.get("business_intelligence") else {}
        
        dashboard["performance"] = {
            "max_concurrent_requests": config.MAX_CONCURRENT_REQUESTS,
            "request_timeout": config.REQUEST_TIMEOUT,
            "cache_size": config.CACHE_SIZE,
            "uptime": (datetime.utcnow() - start_time).total_seconds() if 'start_time' in globals() else 0
        }
        
        dashboard["timestamp"] = datetime.utcnow().isoformat()
        
        return dashboard
        
    except Exception as e:
        logger.error(f"Dashboard generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Dashboard generation failed: {str(e)}")

# Configuration endpoint
@app.get("/api/config")
async def get_configuration():
    """Get public configuration"""
    return {
        "version": config.API_VERSION,
        "features": {
            "multimodal_ai": config.MULTIMODAL_ENABLED,
            "workflow_engine": config.WORKFLOW_ENGINE_ENABLED,
            "business_intelligence": config.BUSINESS_INTELLIGENCE_ENABLED
        },
        "performance": {
            "max_concurrent_requests": config.MAX_CONCURRENT_REQUESTS,
            "request_timeout": config.REQUEST_TIMEOUT
        },
        "endpoints": {
            "api_docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "health": "/api/health",
            "dashboard": "/api/advanced-ai/dashboard"
        }
    }

# Include route routers
app.include_router(advanced_ai_router, prefix="/api/advanced-ai")
app.include_router(orchestration_router, prefix="/api/advanced-ai")
app.include_router(realtime_router, prefix="/api/advanced-ai")

# Include multi-modal routes if enabled
if config.MULTIMODAL_ENABLED:
    logger.info("🔗 Including Multi-Modal AI routes...")
    include_multimodal_router(app)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with platform information"""
    return {
        "message": "Welcome to ATOM Multi-Modal AI Platform",
        "version": config.API_VERSION,
        "description": config.API_DESCRIPTION,
        "features": {
            "multimodal_ai": config.MULTIMODAL_ENABLED,
            "workflow_engine": config.WORKFLOW_ENGINE_ENABLED,
            "business_intelligence": config.BUSINESS_INTELLIGENCE_ENABLED
        },
        "endpoints": {
            "api_docs": "/docs",
            "redoc": "/redoc",
            "health": "/api/health",
            "dashboard": "/api/advanced-ai/dashboard",
            "config": "/api/config"
        },
        "services": {
            "advanced_ai": "/api/advanced-ai/ai-process",
            "orchestration": "/api/advanced-ai/orchestration/ai-process",
            "realtime": "/api/advanced-ai/streaming/events",
            "multimodal": "/api/multimodal" if config.MULTIMODAL_ENABLED else "disabled"
        }
    }

# Custom 404 handler
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"Endpoint {request.url.path} not found",
            "available_endpoints": {
                "health": "/api/health",
                "dashboard": "/api/advanced-ai/dashboard",
                "docs": "/docs",
                "root": "/"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Run server
if __name__ == "__main__":
    # Setup logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=config.LOG_LEVEL.upper()
    )
    
    # Record start time
    start_time = datetime.utcnow()
    
    # Run server
    uvicorn.run(
        app,
        host=config.PYTHON_API_HOST,
        port=config.PYTHON_API_PORT,
        log_level=config.LOG_LEVEL.lower(),
        access_log=True,
        loop="asyncio",
        http="auto",
        reload=False
    )