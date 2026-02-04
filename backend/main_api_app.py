# -*- coding: utf-8 -*-
import os
import sys
import types
from unittest.mock import MagicMock

# Prevent numpy/pandas from loading real DLLs that crash on Py 3.13
# Setting to None raises ImportError instead of crashing, allowing try-except blocks to work
sys.modules["numpy"] = None
sys.modules["pandas"] = None
sys.modules["lancedb"] = None
sys.modules["pyarrow"] = None

print("WARNING: Numpy/Pandas/LanceDB disabled via sys.modules=None to prevent crash")

import logging
import threading
from datetime import datetime
from pathlib import Path
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html

import core.models
import core.models_registration  # Fixes circular relationship issues
from core.circuit_breaker import circuit_breaker
from core.database import SessionLocal, get_db

# --- V2 IMPORTS (Architecture) ---
from core.lazy_integration_registry import (
    ESSENTIAL_INTEGRATIONS,
    get_integration_list,
    get_loaded_integrations,
    load_integration,
)
from core.resource_guards import MemoryGuard, ResourceGuard
from core.security import RateLimitMiddleware, SecurityHeadersMiddleware

try:
    from core.integration_loader import (
        IntegrationLoader,  # Kept for backward compatibility if needed
    )
except ImportError:
    IntegrationLoader = None
    print("⚠️ WARNING: IntegrationLoader could not be imported (likely numpy/lancedb issue)")

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ATOM_SERVER")

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)
logger.info(f"Configuration loaded from {env_path}")
deepseek_status = os.getenv("DEEPSEEK_API_KEY")
logger.info(f"DEBUG: Startup DEEPSEEK_API_KEY present: {bool(deepseek_status)}")


# Environment settings
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
DISABLE_DOCS = ENVIRONMENT == "production"

# Import config
from core.config import get_config
config = get_config()

# Override with config values
if config.server.host:
    ALLOWED_HOSTS.append(config.server.host)

# --- LIFECYCLE MANAGER ---
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    from core.config import get_config
    config = get_config()

    logger.info("=" * 60)
    logger.info("ATOM Platform Starting (Hybrid Mode)")
    logger.info("=" * 60)
    logger.info(f"Server will start on {config.server.host}:{config.server.port}")
    logger.info(f"Environment: {ENVIRONMENT}")
    
    # 0. Initialize Database (Critical for in-memory DB)
    try:
        from analytics.models import WorkflowExecutionLog  # Force registration
        from sqlalchemy import inspect
        from core.admin_bootstrap import ensure_admin_user
        from core.database import engine
        from core.models import Base
        
        logger.info("Initializing database tables...")
        Base.metadata.create_all(bind=engine)
        
        # Verify tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"✓ Database tables created: {tables}")
        
        logger.info("Bootstrapping admin user...")
        ensure_admin_user()
        logger.info("✓ Admin user ready")
        
    except Exception as e:
        logger.error(f"CRITICAL: Database initialization failed: {e}")

    # 1. Load Essential Integrations (defined in registry)
    if ESSENTIAL_INTEGRATIONS:
        logger.info(f"Loading {len(ESSENTIAL_INTEGRATIONS)} essential plugins...")
        for name in ESSENTIAL_INTEGRATIONS:
            try:
                router = load_integration(name)
                if router:
                    # Don't add prefix - routers already have their own prefixes defined
                    app.include_router(router, tags=[name])
                    _loaded_integrations.add(name)  # Track loaded integration
                    logger.info(f"  ✓ {name}")
            except Exception as e:
                logger.error(f"  ✗ Failed to load essential plugin {name}: {e}")

    # Check if schedulers should run (Default: True for Monolith, False for API-only replicas)
    enable_scheduler = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"
    
    if enable_scheduler:
        # 2. Start Workflow Scheduler (Run in main event loop)
        try:
            from ai.workflow_scheduler import workflow_scheduler
            
            logger.info("Starting Workflow Scheduler...")
            try:
                workflow_scheduler.start()
                logger.info("✓ Workflow Scheduler running")
            except Exception as e:
                logger.error(f"!!! Workflow Scheduler Crashed: {e}")
            
        except ImportError:
            logger.warning("Workflow Scheduler module not found.")

        # 3. Start Agent Scheduler (Upstream compatibility)
        try:
            from core.scheduler import AgentScheduler
            AgentScheduler.get_instance()
            logger.info("✓ Agent Scheduler running")
        except ImportError:
            logger.warning("Agent Scheduler module not found.")

        # 4. Start Intelligence Background Worker
        try:
            from ai.intelligence_background_worker import intelligence_worker
            await intelligence_worker.start()
            logger.info("✓ Intelligence Background Worker running")
        except Exception as e:
            logger.error(f"Failed to start intelligence worker: {e}")
    else:
        logger.info("Skipping Scheduler startup (ENABLE_SCHEDULER=false)")

    # 5. Start Redis Event Bridge (Real-Time Updates)
    # Backported from SaaS for Atom-OpenClaw Bridge
    redis_listener = None
    enable_redis = os.getenv("ENABLE_REDIS", "false").lower() == "true"
    
    if enable_redis:
        try:
            from redis_listener import RedisListener
            redis_listener = RedisListener()
            # Start in background task to not block startup
            import asyncio
            asyncio.create_task(redis_listener.start())
            logger.info("✓ Redis Event Bridge running")
        except ImportError:
            logger.warning("Redis Listener module not found.")
        except Exception as e:
            logger.error(f"Failed to start Redis Bridge: {e}")
    else:
        logger.info("Skipping Redis Bridge (ENABLE_REDIS=false)")
    
    logger.info("=" * 60)
    logger.info("✓ Server Ready")

    yield

    # --- SHUTDOWN ---
    logger.info("Shutting down ATOM Platform...")
    try:
        from ai.workflow_scheduler import workflow_scheduler
        workflow_scheduler.shutdown()
        logger.info("✓ Workflow Scheduler stopped")
    except:
        pass

    try:
        redis_listener.stop()
        logger.info("✓ Redis Event Bridge stopped")
    except:
        pass


# --- APP INITIALIZATION ---
app = FastAPI(
    title="ATOM API",
    description="Advanced Task Orchestration & Management API - Hybrid V2",
    version="2.1.0",
    docs_url=None if DISABLE_DOCS else "/docs",
    redoc_url=None if DISABLE_DOCS else "/redoc",
    openapi_url=None if DISABLE_DOCS else "/openapi.json",
    lifespan=lifespan,
)

# Trusted Host Middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=ALLOWED_HOSTS
)

# CORS Middleware (Standard V1/V2)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Middleware (V2 Enhanced)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# ============================================================================
# GLOBAL EXCEPTION HANDLER
# Standardized error handling for all uncaught exceptions
# ============================================================================
try:
    from core.error_handlers import global_exception_handler, atom_exception_handler
    from core.exceptions import AtomException

    # Register general exception handler (catches all)
    app.add_exception_handler(Exception, global_exception_handler)
    logger.info("✓ Global Exception Handler Registered")

    # Register AtomException handler (more specific, takes precedence)
    app.add_exception_handler(AtomException, atom_exception_handler)
    logger.info("✓ AtomException Handler Registered")
except ImportError as e:
    logger.warning(f"Exception handler not found, skipping... {e}")

# ============================================================================
# AUTO-LOADING MIDDLEWARE (True Lazy Loading)
# Automatically loads integrations on first request instead of returning 404
# ============================================================================

# Track which integrations have been loaded
_loaded_integrations = set()

# Blacklist integrations that crash during loading (Python 3.13 compatibility issues)
_blacklisted_integrations = {
    # "atom_agent",  # Crashes due to numpy/lancedb issues
    "unified_calendar",  # May have similar issues
    "unified_task",  # May have similar issues
    # "unified_search" - NOW USING MOCK, SAFE TO AUTO-LOAD!
}

@app.middleware("http")
async def auto_load_integration_middleware(request, call_next):
    """
    Intercept requests and auto-load integrations on-demand.
    This implements true lazy loading - no more 404s for unloaded integrations!
    """
    # Get the request path
    path = request.url.path
    
    # Check if this is an API request
    if path.startswith("/api/"):
        # Extract the integration name from the path
        # e.g., /api/lancedb-search/... -> lancedb-search
        # e.g., /api/atom-agent/... -> atom-agent
        path_parts = path.split("/")
        if len(path_parts) >= 3:
            potential_integration = path_parts[2]
            
            # Map URL paths to integration names in registry
            integration_map = {
                "lancedb-search": "unified_search",
                "atom-agent": "atom_agent",
                "gdrive": "google_drive",
                "gcal": "google_calendar",
                "ms365": "microsoft365",
                "office365": "microsoft365",
                "v1": None,  # Skip - handled by core routes
                "auth": None,  # Core auth routes
                "nextjs": None, # Core/frontend routes
            }
            
            # Get the actual integration name
            integration_name = integration_map.get(potential_integration, potential_integration.replace("-", "_"))
            
            # Skip blacklisted integrations
            if integration_name in _blacklisted_integrations:
                logger.debug(f"⚠️ Skipping blacklisted integration: {integration_name}")
            # Check if this integration exists in registry and isn't loaded yet
            elif integration_name and integration_name not in _loaded_integrations:
                integration_list = get_integration_list()
                if integration_name in integration_list:
                    try:
                        logger.info(f"🔄 Auto-loading integration on-demand: {integration_name}")
                        router = load_integration(integration_name)
                        if router:
                            app.include_router(router, tags=[integration_name])
                            _loaded_integrations.add(integration_name)
                            logger.info(f"✓ Auto-loaded: {integration_name}")
                    except Exception as e:
                        logger.error(f"✗ Failed to auto-load {integration_name}: {e}")
    
    # Continue with the request
    response = await call_next(request)
    return response

# ============================================================================
# 1. CORE ROUTES (EAGER LOADING)
# Restored from V1 to ensure immediate availability of main features
# ============================================================================
logger.info("Loading Core API Routes...")
try:
    # 1. Main API
    try:
        from core.api_routes import router as core_router
        app.include_router(core_router, prefix="/api/v1")
    except ImportError as e:
        logger.error(f"Failed to load Core API routes: {e}")

    # Skill Builder Routes
    try:
        from api.admin.skill_routes import router as skill_router
        app.include_router(skill_router, prefix="/api/admin/skills", tags=["Skill Management"])
        logger.info("✓ Skill Builder Routes Loaded")
    except ImportError as e:
        logger.warning(f"Skill routes not found: {e}")

    # Satellite Routes
    try:
        from api.satellite_routes import router as satellite_router
        app.include_router(satellite_router, tags=["Satellite"])
        logger.info("✓ Satellite Routes Loaded")
    except ImportError as e:
        logger.warning(f"Satellite routes not found: {e}")

    # 1.5 System Health (Safe Import)
    try:
        from api.admin.system_health_routes import router as health_router
        app.include_router(health_router, prefix="") # Already has valid prefix
    except ImportError as e:
        logger.error(f"Failed to load System Health routes: {e}")

    # 2. Workflow Engine
    try:
        from core.availability_endpoints import router as availability_router
        app.include_router(availability_router, prefix="/api/v1")
    except ImportError as e:
        logger.warning(f"Failed to load availability routes: {e}")
        
    try:
        from core.stakeholder_endpoints import router as stakeholder_router
        app.include_router(stakeholder_router, prefix="/api/v1")
    except ImportError as e:
        logger.warning(f"Failed to load stakeholder routes: {e}")

    try:
        from api.reports import router as reports_router
        app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
    except ImportError as e:
        logger.warning(f"Failed to load reports routes (skipping): {e}")

    # Tool Discovery Routes (NEW)
    try:
        from api.tools import router as tools_router
        app.include_router(tools_router)
        logger.info("✓ Tool Discovery Routes Loaded")
    except ImportError as e:
        logger.warning(f"Failed to load tool discovery routes (skipping): {e}")

    try:
        from api.agent_routes import router as agent_router
        app.include_router(agent_router, prefix="/api/agents", tags=["agents"])
    except ImportError as e:
        logger.warning(f"Failed to load agent routes (skipping): {e}")

    try:
        from api.workflow_template_routes import router as template_router
        app.include_router(template_router, prefix="/api/workflow-templates", tags=["workflow-templates"])
    except ImportError as e:
         logger.warning(f"Failed to load workflow template routes: {e}")

    try:
        from api.notification_settings_routes import router as notification_router
        app.include_router(notification_router, prefix="/api/notification-settings", tags=["notification-settings"])
    except ImportError as e:
        logger.warning(f"Failed to load notification settings routes: {e}")

    try:
        from api.workflow_analytics_routes import router as analytics_router
        app.include_router(analytics_router, prefix="/api/workflows", tags=["workflow-analytics"])
    except ImportError as e:
        logger.warning(f"Failed to load workflow analytics routes: {e}")

    try:
        from api.background_agent_routes import router as background_router
        app.include_router(background_router, prefix="/api/background-agents", tags=["background-agents"])
    except ImportError as e:
        logger.warning(f"Failed to load background agent routes: {e}")
    
    try:
        from api.financial_ops_routes import router as financial_router
        app.include_router(financial_router, prefix="/api/financial", tags=["financial-ops"])
    except ImportError as e:
        logger.warning(f"Failed to load financial ops routes: {e}")

    try:
        from api.ai_accounting_routes import router as accounting_router
        app.include_router(accounting_router, prefix="/api/accounting", tags=["ai-accounting"])
    except ImportError as e:
        logger.warning(f"Failed to load AI accounting routes: {e}")

    try:
        from api.reconciliation_routes import router as reconciliation_router
        app.include_router(reconciliation_router, prefix="/api/reconciliation", tags=["reconciliation"])
    except ImportError as e:
        logger.warning(f"Failed to load reconciliation routes: {e}")

    try:
        from api.apar_routes import router as apar_router
        app.include_router(apar_router, prefix="/api/apar", tags=["ap-ar"])
    except ImportError as e:
        logger.warning(f"Failed to load AP/AR routes: {e}")

    try:
        from api.graphrag_routes import router as graphrag_router
        app.include_router(graphrag_router, prefix="/api/graphrag", tags=["graphrag"])
    except ImportError as e:
        logger.warning(f"Failed to load GraphRAG routes: {e}")

    try:
        from api.project_routes import router as projects_router
        app.include_router(projects_router)
    except ImportError as e:
        logger.warning(f"Failed to load Project routes: {e}")

    try:
        from api.intelligence_routes import router as intelligence_router
        app.include_router(intelligence_router)
    except ImportError as e:
        logger.warning(f"Failed to load Intelligence routes: {e}")

    try:
        from api.sales_routes import router as sales_router
        app.include_router(sales_router)
    except ImportError as e:
        logger.warning(f"Failed to load Sales routes: {e}")

    # Episodic Memory & Graduation Routes (NEW)
    try:
        from api.episode_routes import router as episode_router
        app.include_router(episode_router)  # Prefix defined in router (/api/episodes)
        logger.info("✓ Episodic Memory & Graduation Routes Loaded")
    except ImportError as e:
        logger.warning(f"Failed to load Episodic Memory routes: {e}")

    try:
        from core.workflow_endpoints import router as workflow_router
        app.include_router(workflow_router, prefix="/api/v1", tags=["Workflows"])
    except ImportError as e:
        logger.error(f"Failed to load Core Workflow routes: {e}")

    # 3. Workflow UI (Visual Automations)
    # Eagerly load this to ensure 404s don't happen silently
    try:
        from core.workflow_ui_endpoints import router as workflow_ui_router
        app.include_router(workflow_ui_router, prefix="/api/v1/workflow-ui", tags=["Workflow UI"])
        logger.info("✓ Workflow UI Endpoints Loaded")
    except Exception as e:
        logger.error(f"CRITICAL: Workflow UI endpoints failed to load: {e}")
        # raise e # Uncomment to crash on startup if strict

    try:
        from enhanced_ai_workflow_endpoints import router as ai_router
        app.include_router(ai_router) # Prefix defined in router
    except ImportError as e:
        logger.warning(f"AI endpoints not found: {e}")

    # 3c. Enhanced Workflow Automation (V2)
    try:
        from enhanced_workflow_api import router as enhanced_wf_router
        app.include_router(enhanced_wf_router, prefix="/api/v2/workflows/enhanced")
        logger.info("✓ Enhanced Workflow Automation (V2) routes registered")
    except ImportError as e:
        logger.warning(f"Enhanced Workflow Automation not available: {e}")

    # 3e. Workflow DNA Analytics (Performance & Logs)
    try:
        from analytics.plugin import enable_workflow_dna
        enable_workflow_dna(app)
    except ImportError as e:
        logger.warning(f"Workflow DNA Analytics not available: {e}")

    # 3d. Workflow Automation Routes (Test Step, etc.)
    try:
        from integrations.workflow_automation_routes import router as workflow_automation_router
        app.include_router(workflow_automation_router) # Prefix defined in router (/workflows)
        logger.info("✓ Workflow Automation Routes (Test Step) registered")
    except ImportError as e:
        logger.warning(f"Workflow Automation routes not found: {e}")

    # 4. Auth Routes (Standard Login)
    try:
        from core.auth_endpoints import router as auth_router
        app.include_router(auth_router)  # Already has prefix="/api/auth"

        # 4a. 2FA Routes
        from api.auth_2fa_routes import router as auth_2fa_router
        app.include_router(auth_2fa_router) # Already has prefix="/api/auth/2fa"
        logger.info("✓ 2FA Routes Loaded")
    except ImportError:
        logger.warning("Auth endpoints or 2FA routes not found, skipping.")

    # 4b. Onboarding Routes
    try:
        from api.onboarding_routes import router as onboarding_router
        app.include_router(onboarding_router, prefix="/api/onboarding", tags=["Onboarding"])
    except ImportError as e:
        logger.warning(f"Onboarding routes not found: {e}")

    # 4c. Reasoning & Feedback Routes
    try:
        from api.reasoning_routes import router as reasoning_router
        app.include_router(reasoning_router)
    except ImportError as e:
        logger.warning(f"Reasoning routes not found: {e}")

    # 4d. Time Travel Routes
    try:
        from api.time_travel_routes import router as time_travel_router  # [Lesson 3]
        app.include_router(time_travel_router) # [Lesson 3]
    except ImportError as e:
        logger.warning(f"Time Travel routes not found: {e}")
    # 4. Microsoft 365 Integration
    try:
        from integrations.microsoft365_routes import microsoft365_router

        # Primary Route (New Standard)
        app.include_router(microsoft365_router, prefix="/api/integrations/microsoft365", tags=["Microsoft 365"])
        # Legacy Route (For backward compatibility/caching rewrites)
        app.include_router(microsoft365_router, prefix="/api/v1/integrations/microsoft365", tags=["Microsoft 365 (Legacy)"])
    except ImportError:
        logger.warning("Microsoft 365 routes not found, skipping.")

    # 5. OAuth (Critical for login)
    try:
        from oauth_routes import router as oauth_router
        app.include_router(oauth_router, prefix="/api/auth", tags=["OAuth"])
        logger.info("✓ OAuth Routes Loaded")
    except ImportError:
        logger.warning("OAuth routes not found, skipping.")

    # 5.1. OAuth Status Routes (for OAuth system testing)
    try:
        from oauth_status_routes import router as oauth_status_router
        app.include_router(oauth_status_router, tags=["OAuth Status"])
        logger.info("✓ OAuth Status Routes Loaded")
    except ImportError:
        logger.warning("OAuth status routes not found, skipping.")

    # 4. WebSockets (Real-time features)
    try:
        from websocket_routes import router as ws_router
        app.include_router(ws_router, tags=["WebSockets"])
    except ImportError:
        logger.warning("WebSocket routes not found, skipping.")

    # 6. MCP Routes (Web Search & Web Access for Agents)
    try:
        from integrations.mcp_routes import router as mcp_router
        app.include_router(mcp_router, tags=["MCP"])
        logger.info("✓ MCP Routes Loaded")
    except ImportError as e:
        logger.warning(f"MCP routes not found: {e}")

    try:
        from api.integrations_catalog_routes import router as catalog_router
        app.include_router(catalog_router)
        logger.info("✓ Integrations Catalog Routes Loaded")
    except ImportError as e:
        logger.warning(f"Integrations catalog routes not found: {e}")

    try:
        from api.dynamic_options_routes import router as dynamic_options_router
        app.include_router(dynamic_options_router)
        logger.info("✓ Dynamic Options Routes Loaded")
    except ImportError as e:
        logger.warning(f"Dynamic options routes not found: {e}")

    try:
        from integrations.universal.routes import router as universal_auth_router
        app.include_router(universal_auth_router)
        logger.info("✓ Universal Auth Routes Loaded")
    except ImportError as e:
        logger.warning(f"Universal auth routes not found: {e}")

    try:
        from integrations.bridge.external_integration_routes import router as ext_router
        app.include_router(ext_router)
        logger.info("✓ External Integration Routes Loaded")
    except ImportError as e:
        logger.warning(f"External integration bridge routes not found: {e}")

    # Register Connection routes
    try:
        from api.connection_routes import router as conn_router
        app.include_router(conn_router)
        logger.info("✓ Connection Management Routes Loaded")
    except ImportError as e:
        logger.warning(f"Connection routes not found: {e}")

    # 7. Chat Orchestrator Routes (Critical for chat functionality)
    try:
        from integrations.chat_routes import router as chat_router
        app.include_router(chat_router, prefix="/api", tags=["Chat"])
        logger.info("✓ Chat Routes Loaded")
    except ImportError as e:
        logger.warning(f"Chat routes not found: {e}")

    # 8. Agent Governance Routes
    try:
        from api.agent_governance_routes import router as gov_router
        app.include_router(gov_router)
        logger.info("✓ Agent Governance Routes Loaded")
    except ImportError as e:
        logger.warning(f"Agent Governance routes not found: {e}")

    # 9. Memory/Document Routes
    try:
        from api.memory_routes import router as memory_router
        app.include_router(memory_router, prefix="/api/v1/memory", tags=["Memory"])
        logger.info("✓ Memory Routes Loaded")
    except ImportError as e:
        logger.warning(f"Memory routes not found: {e}")

    # 10. Voice Routes
    try:
        from api.voice_routes import router as voice_router
        app.include_router(voice_router, prefix="/api/voice", tags=["Voice"])
        logger.info("✓ Voice Routes Loaded")
    except ImportError as e:
        logger.warning(f"Voice routes not found: {e}")

    # 11. Document Ingestion Routes
    try:
        from api.document_routes import router as doc_router
        app.include_router(doc_router, prefix="/api/documents", tags=["Documents"])
        logger.info("✓ Document Routes Loaded")
    except ImportError as e:
        logger.warning(f"Document routes not found: {e}")

    # 12. Formula Routes
    try:
        from api.formula_routes import router as formula_router
        app.include_router(formula_router, prefix="/api/formulas", tags=["Formulas"])
        logger.info("✓ Formula Routes Loaded")
    except ImportError as e:
        logger.warning(f"Formula routes not found: {e}")

    # 13. AI Workflows Routes (NLU Parse, Completion)
    try:
        from api.ai_workflows_routes import router as ai_wf_router
        app.include_router(ai_wf_router, tags=["AI Workflows"])
        logger.info("✓ AI Workflows Routes Loaded")
    except ImportError as e:
        logger.warning(f"AI Workflows routes not found: {e}")

    # 13.5 Workflow Templates Routes (Fix for 404s)
    try:
        from api.workflow_template_routes import router as wf_template_router
        app.include_router(wf_template_router, prefix="/api/workflow-templates", tags=["Workflow Templates"])
        logger.info("✓ Workflow Template Routes Loaded")
    except ImportError as e:
        logger.warning(f"Workflow Template routes not found: {e}")

    # 14. Background Agent Routes
    try:
        from api.background_agent_routes import router as bg_agent_router
        app.include_router(bg_agent_router, tags=["Background Agents"])
        logger.info("✓ Background Agent Routes Loaded")
    except ImportError as e:
        logger.warning(f"Background Agent routes not found: {e}")

    # 14.5 Core Agent Routes (The missing piece)
    try:
        from api.agent_routes import router as agent_router
        app.include_router(agent_router, prefix="/api/agents", tags=["Agents"])
        logger.info("✓ Core Agent Routes Loaded")
    except ImportError as e:
        logger.warning(f"Core Agent routes not found: {e}")

    # 14.7 Risk & Protection Routes
    try:
        from api.protection_api import router as protection_router
        app.include_router(protection_router, prefix="/api/risk", tags=["Protection"])
        logger.info("✓ Protection API Loaded at /api/risk")
    except ImportError as e:
        logger.warning(f"Protection API not found: {e}")

    try:
        from api.risk_routes import router as risk_router
        app.include_router(risk_router, tags=["Risk"])
        logger.info("✓ Risk Routes Loaded")
    except ImportError as e:
        logger.warning(f"Risk routes not found: {e}")

    # 14.6 Core Business Routes (Intelligence, Projects, Sales)
    try:
        from api.device_nodes import router as device_node_router
        from api.intelligence_routes import router as intelligence_router
        from api.project_routes import router as project_router
        from api.sales_routes import router as sales_router
        
        app.include_router(intelligence_router) # Prefix defined in router
        app.include_router(project_router)      # Prefix defined in router
        app.include_router(sales_router)        # Prefix defined in router
        app.include_router(device_node_router)  # Prefix defined in router
        logger.info("✓ Core Business Routes Loaded (Intelligence, Projects, Sales, Device Nodes)")
    except ImportError as e:
        logger.warning(f"Core Business routes not found: {e}")

    # 15. Integration Health Stubs (fallback endpoints for missing integrations)
    try:
        from api.integration_health_stubs import router as health_stubs_router
        app.include_router(health_stubs_router, tags=["Integration Stubs"])
        logger.info("✓ Integration Health Stubs Loaded")
    except ImportError as e:
        logger.warning(f"Integration Health Stubs not found: {e}")

    # 15.1 Canvas Routes (Canvas system for charts and forms)
    try:
        from api.canvas_routes import router as canvas_router
        app.include_router(canvas_router, tags=["Canvas"])
        logger.info("✓ Canvas Routes Loaded")
    except ImportError as e:
        logger.warning(f"Canvas routes not found: {e}")

    # 15.1.b Canvas Recording Routes (Session recording for governance)
    try:
        from api.canvas_recording_routes import router as canvas_recording_router
        app.include_router(canvas_recording_router, tags=["Canvas Recording"])
        logger.info("✓ Canvas Recording Routes Loaded")
    except ImportError as e:
        logger.warning(f"Canvas recording routes not found: {e}")

    # 15.1.c Canvas Type Routes (Specialized canvas types: docs, email, sheets, etc.)
    try:
        from api.canvas_type_routes import router as canvas_type_router
        app.include_router(canvas_type_router, tags=["Canvas Types"])
        logger.info("✓ Canvas Type Routes Loaded")
    except ImportError as e:
        logger.warning(f"Canvas type routes not found: {e}")

    # 15.1.d Specialized Canvas Routes (docs, email, sheets, orchestration, terminal, coding)
    try:
        from api.canvas_docs_routes import router as canvas_docs_router
        app.include_router(canvas_docs_router, tags=["Canvas Docs"])
        logger.info("✓ Canvas Docs Routes Loaded")
    except ImportError as e:
        logger.warning(f"Canvas docs routes not found: {e}")

    try:
        from api.canvas_email_routes import router as canvas_email_router
        app.include_router(canvas_email_router, tags=["Canvas Email"])
        logger.info("✓ Canvas Email Routes Loaded")
    except ImportError as e:
        logger.warning(f"Canvas email routes not found: {e}")

    try:
        from api.canvas_sheets_routes import router as canvas_sheets_router
        app.include_router(canvas_sheets_router, tags=["Canvas Sheets"])
        logger.info("✓ Canvas Sheets Routes Loaded")
    except ImportError as e:
        logger.warning(f"Canvas sheets routes not found: {e}")

    try:
        from api.canvas_orchestration_routes import router as canvas_orchestration_router
        app.include_router(canvas_orchestration_router, tags=["Canvas Orchestration"])
        logger.info("✓ Canvas Orchestration Routes Loaded")
    except ImportError as e:
        logger.warning(f"Canvas orchestration routes not found: {e}")

    try:
        from api.canvas_terminal_routes import router as canvas_terminal_router
        app.include_router(canvas_terminal_router, tags=["Canvas Terminal"])
        logger.info("✓ Canvas Terminal Routes Loaded")
    except ImportError as e:
        logger.warning(f"Canvas terminal routes not found: {e}")

    try:
        from api.canvas_coding_routes import router as canvas_coding_router
        app.include_router(canvas_coding_router, tags=["Canvas Coding"])
        logger.info("✓ Canvas Coding Routes Loaded")
    except ImportError as e:
        logger.warning(f"Canvas coding routes not found: {e}")

    # 15.1.e Recording Review Routes (Governance & Learning integration)
    try:
        from api.recording_review_routes import router as recording_review_router
        app.include_router(recording_review_router, tags=["Recording Review"])
        logger.info("✓ Recording Review Routes Loaded")
    except ImportError as e:
        logger.warning(f"Recording review routes not found: {e}")

    # 15.1.d Health Monitoring Routes (System health and alerts)
    try:
        from api.health_monitoring_routes import router as health_monitoring_router
        app.include_router(health_monitoring_router, tags=["Health Monitoring"])
        logger.info("✓ Health Monitoring Routes Loaded")
    except ImportError as e:
        logger.warning(f"Health monitoring routes not found: {e}")

    # 15.1.e Mobile Canvas Routes (Mobile-optimized canvas access and offline sync)
    try:
        from api.mobile_canvas_routes import router as mobile_router
        app.include_router(mobile_router, tags=["Mobile Canvas"])
        logger.info("✓ Mobile Canvas Routes Loaded")
    except ImportError as e:
        logger.warning(f"Mobile canvas routes not found: {e}")

    # 15.1.a Artifact Routes (Persistent Workbench)
    try:
        from api.artifact_routes import router as artifact_router
        app.include_router(artifact_router, tags=["Artifacts"])
        logger.info("✓ Artifact Routes Loaded")
    except ImportError as e:
        logger.warning(f"Artifact routes not found: {e}")

    # 15.2 Browser Automation Routes (CDP via Playwright)
    try:
        from api.browser_routes import router as browser_router
        app.include_router(browser_router, tags=["Browser Automation"])
        logger.info("✓ Browser Automation Routes Loaded")
    except ImportError as e:
        logger.warning(f"Browser automation routes not found: {e}")

    # 15.3 Device Capabilities Routes (Hardware Access)
    try:
        from api.device_capabilities import router as device_router
        app.include_router(device_router, tags=["Device Capabilities"])
        logger.info("✓ Device Capabilities Routes Loaded")
    except ImportError as e:
        logger.warning(f"Device capabilities routes not found: {e}")

    # 15.3.1 Device WebSocket Routes (Real-time Device Communication)
    try:
        from api.device_websocket import websocket_device_endpoint
        app.websocket("/api/devices/ws")(websocket_device_endpoint)
        logger.info("✓ Device WebSocket Routes Loaded")
    except ImportError as e:
        logger.warning(f"Device WebSocket routes not found: {e}")

    # 15.4 Deep Link Routes (atom:// URL Scheme)
    try:
        from api.deeplinks import router as deeplinks_router
        app.include_router(deeplinks_router, prefix="/api/deeplinks", tags=["Deep Links"])
        logger.info("✓ Deep Link Routes Loaded")
    except ImportError as e:
        logger.warning(f"Deep link routes not found: {e}")

    # 15.5 Enhanced Feedback Routes (NEW)
    try:
        from api.feedback_enhanced import router as feedback_enhanced_router
        app.include_router(feedback_enhanced_router, prefix="/api/feedback", tags=["Feedback"])
        logger.info("✓ Enhanced Feedback Routes Loaded")
    except ImportError as e:
        logger.warning(f"Enhanced feedback routes not found: {e}")

    # 15.6 Feedback Analytics Routes (NEW)
    try:
        from api.feedback_analytics import router as feedback_analytics_router
        app.include_router(feedback_analytics_router, prefix="/api/feedback/analytics", tags=["Feedback Analytics"])
        logger.info("✓ Feedback Analytics Routes Loaded")
    except ImportError as e:
        logger.warning(f"Feedback analytics routes not found: {e}")

    # 15.7 Feedback Batch Operations Routes (Phase 2)
    try:
        from api.feedback_batch import router as feedback_batch_router
        app.include_router(feedback_batch_router, prefix="/api/feedback/batch", tags=["Feedback Batch"])
        logger.info("✓ Feedback Batch Operations Routes Loaded")
    except ImportError as e:
        logger.warning(f"Feedback batch operations routes not found: {e}")

    # 15.8 Feedback Phase 2 Routes (Promotions, Export, Advanced Analytics)
    try:
        from api.feedback_phase2 import router as feedback_phase2_router
        app.include_router(feedback_phase2_router, prefix="/api/feedback/phase2", tags=["Feedback Phase 2"])
        logger.info("✓ Feedback Phase 2 Routes Loaded")
    except ImportError as e:
        logger.warning(f"Feedback Phase 2 routes not found: {e}")

    # 15.9 A/B Testing Routes (Phase 3)
    try:
        from api.ab_testing import router as ab_testing_router
        app.include_router(ab_testing_router, prefix="/api/ab-tests", tags=["A/B Testing"])
        logger.info("✓ A/B Testing Routes Loaded")
    except ImportError as e:
        logger.warning(f"A/B testing routes not found: {e}")

    # 15.10 Canvas Collaboration Routes (Multi-Agent Coordination)
    try:
        from api.canvas_collaboration import router as collab_router
        app.include_router(collab_router, prefix="/api/canvas-collab", tags=["Canvas Collaboration"])
        logger.info("✓ Canvas Collaboration Routes Loaded")
    except ImportError as e:
        logger.warning(f"Canvas collaboration routes not found: {e}")

    # 15.11 Custom Canvas Components Routes
    try:
        from api.custom_components import router as components_router
        app.include_router(components_router, prefix="/api/components", tags=["Custom Components"])
        logger.info("✓ Custom Components Routes Loaded")
    except ImportError as e:
        logger.warning(f"Custom components routes not found: {e}")

    # 15.12 Analytics Dashboard Routes (NEW - Phase 1)
    try:
        from api.analytics_dashboard_endpoints import router as analytics_dashboard_router
        app.include_router(analytics_dashboard_router, tags=["Analytics Dashboard"])
        logger.info("✓ Analytics Dashboard Routes Loaded")
    except ImportError as e:
        logger.warning(f"Analytics dashboard routes not found: {e}")

    # 15.13 User Workflow Templates Routes (NEW - Phase 2)
    try:
        from api.user_templates_endpoints import router as user_templates_router
        app.include_router(user_templates_router)
        logger.info("✓ User Workflow Templates Routes Loaded")
    except ImportError as e:
        logger.warning(f"User workflow templates routes not found: {e}")

    # 15.14 Collaboration Routes (NEW - Phase 4)
    try:
        from api.workflow_collaboration import router as collaboration_router
        app.include_router(collaboration_router)
        logger.info("✓ Collaboration Routes Loaded")
    except ImportError as e:
        logger.warning(f"Collaboration routes not found: {e}")

    # 15.15 Mobile Workflows Routes (NEW - Mobile Support)
    try:
        from api.mobile_workflows import router as mobile_workflows_router
        app.include_router(mobile_workflows_router)
        logger.info("✓ Mobile Workflows Routes Loaded")
    except ImportError as e:
        logger.warning(f"Mobile workflows routes not found: {e}")

    # 15.16 Workflow Debugging Routes (NEW - Phase 6)
    try:
        from api.workflow_debugging import router as debugging_router
        app.include_router(debugging_router)
        logger.info("✓ Workflow Debugging Routes Loaded")
    except ImportError as e:
        logger.warning(f"Workflow debugging routes not found: {e}")

    # 15.17 Advanced Workflow Debugging Routes (NEW - Phase 6 Enhanced)
    try:
        from api.workflow_debugging_advanced import router as debugging_advanced_router
        app.include_router(debugging_advanced_router)
        logger.info("✓ Advanced Workflow Debugging Routes Loaded")
    except ImportError as e:
        logger.warning(f"Advanced debugging routes not found: {e}")

    # 15.18 WebSocket Debugging Routes (NEW - Phase 6 Enhanced)
    try:
        from api.websocket_debugging import router as websocket_debugging_router
        app.include_router(websocket_debugging_router)
        logger.info("✓ WebSocket Debugging Routes Loaded")
    except ImportError as e:
        logger.warning(f"WebSocket debugging routes not found: {e}")

    # 16. Live Command Center APIs (Parallel Pipeline)
    try:
        from integrations.atom_communication_live_api import router as comm_live_router
        from integrations.atom_finance_live_api import router as finance_live_router
        from integrations.atom_projects_live_api import router as projects_live_router
        from integrations.atom_sales_live_api import router as sales_live_router
        
        app.include_router(comm_live_router)
        app.include_router(sales_live_router)
        app.include_router(projects_live_router)
        app.include_router(finance_live_router)
        logger.info("✓ Live Command Center APIs Loaded (Comm, Sales, Projects, Finance)")
    except ImportError as e:
        logger.warning(f"Live Command Center APIs not found: {e}")

    # 17. Workflow DNA Plugin (Analytics)
    try:
        from analytics.plugin import enable_workflow_dna
        enable_workflow_dna(app)
        logger.info("✓ Workflow DNA Plugin Enabled")
    except ImportError as e:
        logger.warning(f"Workflow DNA plugin not found: {e}")

    logger.info("✓ Core Routes Loaded Successfully - Reload Triggered")

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
        
        # Don't add prefix - routers already have their own prefixes defined
        app.include_router(router, tags=[integration_name])
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
# USER MANAGEMENT API ROUTES (Frontend to Backend Migration)
# ============================================================================
try:
    from api.user_management_routes import router as user_management_router
    app.include_router(user_management_router)
    logger.info("✓ User Management Routes Loaded")
except ImportError as e:
    logger.warning(f"User Management routes not found: {e}")

try:
    from api.email_verification_routes import router as email_verification_router
    app.include_router(email_verification_router)
    logger.info("✓ Email Verification Routes Loaded")
except ImportError as e:
    logger.warning(f"Email Verification routes not found: {e}")

try:
    from api.tenant_routes import router as tenant_router
    app.include_router(tenant_router)
    logger.info("✓ Tenant Routes Loaded")
except ImportError as e:
    logger.warning(f"Tenant routes not found: {e}")

try:
    from api.admin_routes import router as admin_router
    app.include_router(admin_router)
    logger.info("✓ Admin User Management Routes Loaded")
except ImportError as e:
    logger.warning(f"Admin routes not found: {e}")

try:
    from api.meeting_routes import router as meeting_router
    app.include_router(meeting_router)
    logger.info("✓ Meeting Attendance Routes Loaded")
except ImportError as e:
    logger.warning(f"Meeting routes not found: {e}")

try:
    from api.financial_routes import router as financial_router
    app.include_router(financial_router)
    logger.info("✓ Financial Data Routes Loaded")
except ImportError as e:
    logger.warning(f"Financial routes not found: {e}")

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
        "status": "healthy_check_reload",
        "memory_mb": round(memory_mb, 2),
        "active_integrations": list(_loaded_integrations),
    }

# ============================================================================
# 5. LIFECYCLE & SCHEDULER
# ============================================================================



if __name__ == "__main__":
    # Bootstrap Admin User (Avoids DB locking issues)
    try:
        from core.admin_bootstrap import ensure_admin_user
        ensure_admin_user()
    except Exception as e:
        logger.error(f"Failed to bootstrap admin: {e}")

    # Get configuration
    from core.config import get_config
    config = get_config()

    # Trigger Reload with configured port
    logger.info(f"Starting server on port {config.server.port}")
    uvicorn.run(
        "main_api_app:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.reload
    )