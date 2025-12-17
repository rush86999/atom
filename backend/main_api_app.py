import os
import threading
import logging
from pathlib import Path
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# --- V2 IMPORTS (Architecture) ---
from core.lazy_integration_registry import (
    load_integration,
    get_integration_list,
    get_loaded_integrations,
    ESSENTIAL_INTEGRATIONS
)
from core.circuit_breaker import circuit_breaker
from core.resource_guards import ResourceGuard, MemoryGuard
from core.security import RateLimitMiddleware, SecurityHeadersMiddleware
from core.integration_loader import IntegrationLoader # Kept for backward compatibility if needed

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ATOM_SERVER")

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)
logger.info(f"Configuration loaded from {env_path}")

# --- APP INITIALIZATION ---
app = FastAPI(
    title="ATOM API",
    description="Advanced Task Orchestration & Management API - Hybrid V2",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware (Standard V1/V2)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Middleware (V2 Enhanced)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# ============================================================================
# 1. CORE ROUTES (EAGER LOADING)
# Restored from V1 to ensure immediate availability of main features
# ============================================================================
logger.info("Loading Core API Routes...")
try:
    # 1. Main API
    from core.api_routes import router as core_router
    app.include_router(core_router, prefix="/api/v1")

    # 2. Workflow Engine
    from core.workflow_endpoints import router as workflow_router
    app.include_router(workflow_router, prefix="/api/v1", tags=["Workflows"])

    # 3. OAuth (Critical for login)
    try:
        from oauth_routes import router as oauth_router
        app.include_router(oauth_router, prefix="/api/auth", tags=["OAuth"])
    except ImportError:
        logger.warning("OAuth routes not found, skipping.")

    # 4. WebSockets (Real-time features)
    try:
        from websocket_routes import router as ws_router
        app.include_router(ws_router, tags=["WebSockets"])
    except ImportError:
        logger.warning("WebSocket routes not found, skipping.")

    logger.info("✓ Core Routes Loaded Successfully")

except ImportError as e:
    logger.critical(f"CRITICAL: Core API routes failed to load: {e}")
    # In production, you might want to raise e here to stop a broken server

# ============================================================================
# 2. LAZY INTEGRATION ENDPOINTS (V2 ARCHITECTURE)
# Keeps the server fast by only loading plugins when needed
# ============================================================================

@app.get("/api/integrations")
async def list_integrations():
    """List all available integrations and their status"""
    return {
        "total": len(get_integration_list()),
        "integrations": list(get_integration_list().keys()),
        "loaded": get_loaded_integrations(),
    }

@app.post("/api/integrations/{integration_name}/load")
async def load_integration_endpoint(integration_name: str):
    """Load an integration on-demand (Solves the startup speed issue)"""
    if not circuit_breaker.is_enabled(integration_name):
        raise HTTPException(
            status_code=503, 
            detail=f"Integration {integration_name} is disabled due to repeated failures"
        )
    
    try:
        logger.info(f"Loading integration: {integration_name}")
        router = load_integration(integration_name)
        
        if router is None:
            circuit_breaker.record_failure(integration_name)
            raise HTTPException(status_code=404, detail="Integration module not found")
        
        # Consistent prefixing
        app.include_router(router, prefix=f"/api/{integration_name}", tags=[integration_name])
        circuit_breaker.record_success(integration_name)
        
        return {"status": "loaded", "integration": integration_name}
        
    except Exception as e:
        circuit_breaker.record_failure(integration_name, e)
        logger.error(f"Failed to load {integration_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/integrations/stats")
async def get_all_integration_stats():
    return circuit_breaker.get_all_stats()

@app.post("/api/integrations/{integration_name}/reset")
async def reset_integration(integration_name: str):
    circuit_breaker.reset(integration_name)
    return {"status": "reset", "integration": integration_name}

# ============================================================================
# 3. SPECIAL HANDLING: WHATSAPP (RESTORED FROM V1)
# ============================================================================
try:
    from integrations.whatsapp_fastapi_routes import (
        initialize_whatsapp_service,
        register_whatsapp_routes,
    )
    # Register routes immediately
    if register_whatsapp_routes(app):
        logger.info("[OK] WhatsApp Business integration routes loaded")
        # Initialize service (Wrapped in try/except to prevent startup crash)
        try:
            if initialize_whatsapp_service():
                logger.info("[OK] WhatsApp Business service initialized")
        except Exception as e:
            logger.warning(f"[WARN] WhatsApp Business service init failed: {e}")
except ImportError:
    logger.info("WhatsApp integration module not present, skipping.")
except Exception as e:
    logger.warning(f"WhatsApp setup error: {e}")

# ============================================================================
# 4. SYSTEM ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    return {
        "name": "ATOM Platform API",
        "version": "2.1.0",
        "status": "running",
        "mode": "Hybrid (Core=Eager, Integrations=Lazy)",
        "docs": "/docs",
    }

@app.get("/health")
async def health_check():
    memory_mb = MemoryGuard.get_memory_usage_mb()
    return {
        "status": "healthy",
        "memory_mb": round(memory_mb, 2),
        "active_integrations": len(get_loaded_integrations()),
    }

# ============================================================================
# 5. LIFECYCLE & SCHEDULER
# ============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("ATOM Platform Starting (Hybrid Mode)")
    logger.info("=" * 60)
    
    # 1. Load Essential Integrations (defined in registry)
    # This bridges the gap - specific plugins you ALWAYS want can be defined there
    if ESSENTIAL_INTEGRATIONS:
        logger.info(f"Loading {len(ESSENTIAL_INTEGRATIONS)} essential plugins...")
        for name in ESSENTIAL_INTEGRATIONS:
            try:
                router = load_integration(name)
                if router:
                    app.include_router(router, prefix=f"/api/{name}", tags=[name])
                    logger.info(f"  ✓ {name}")
            except Exception as e:
                logger.error(f"  ✗ Failed to load essential plugin {name}: {e}")

    # 2. Start Workflow Scheduler (Threaded for Speed, but monitored)
    try:
        from ai.workflow_scheduler import workflow_scheduler
        
        def start_scheduler_thread():
            logger.info("Starting Workflow Scheduler...")
            try:
                workflow_scheduler.start()
                logger.info("✓ Workflow Scheduler running")
            except Exception as e:
                logger.error(f"!!! Workflow Scheduler Crashed: {e}")

        # Daemon thread ensures API starts even if scheduler is slow
        scheduler_thread = threading.Thread(target=start_scheduler_thread, daemon=True)
        scheduler_thread.start()
        
    except ImportError:
        logger.warning("Workflow Scheduler module not found.")
    
    logger.info("=" * 60)
    logger.info("✓ Server Ready")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down ATOM Platform...")
    try:
        from ai.workflow_scheduler import workflow_scheduler
        workflow_scheduler.shutdown()
        logger.info("✓ Workflow Scheduler stopped")
    except:
        pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5059)