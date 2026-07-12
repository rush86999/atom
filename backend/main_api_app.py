from __future__ import annotations

import asyncio

# -*- coding: utf-8 -*-
# Reload trigger
import os
import sys
from typing import ClassVar, Union

from dotenv import load_dotenv

# Load environment variables from .env and .env.local in the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))
load_dotenv(os.path.join(project_root, ".env.local"), override=True)

# Track which integrations have been loaded globally
_loaded_integrations = set()
import traceback

from fastapi import APIRouter, FastAPI

# Configure logging AS EARLY AS POSSIBLE
try:
    from core.logging_config import get_logger, setup_logging

    setup_logging(level=os.getenv("LOG_LEVEL", "INFO"), format_type=os.getenv("LOG_FORMAT", "json"))
    startup_logger = get_logger(__name__)
except (ImportError, TypeError):
    import logging

    logging.basicConfig(level=logging.INFO)
    startup_logger = logging.getLogger(__name__)

# Initialize Sentry for production monitoring
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
                SqlalchemyIntegration(),
            ],
            environment=os.getenv("ENVIRONMENT", "production"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
        )
        startup_logger.info("✓ Sentry initialized")
    except (ImportError, TypeError):
        startup_logger.warning("✗ Sentry SDK not found, skipping initialization")
    except Exception as e:
        startup_logger.error(f"✗ Sentry initialization failed: {e}")

startup_logger.info("=" * 80)
startup_logger.info("ATOM PLATFORM API STARTUP")
startup_logger.info("=" * 80)
startup_logger.info(f"Python version: {sys.version}")
startup_logger.info(f"Working directory: {os.getcwd()}")
startup_logger.info(f"Python path: {sys.path[:3]}...")  # First 3 entries

# Import errors will be caught and logged
try:
    import uvicorn

    startup_logger.info("✓ uvicorn imported")
except Exception as e:
    startup_logger.error(f"✗ Failed to import uvicorn: {e}")
    startup_logger.error(traceback.format_exc())
    sys.exit(1)

try:
    from contextlib import asynccontextmanager
    from datetime import datetime
    from pathlib import Path

    startup_logger.info("✓ Standard library imports successful")
except Exception as e:
    startup_logger.error(f"✗ Failed to import standard library: {e}")
    startup_logger.error(traceback.format_exc())
    sys.exit(1)

try:
    from dotenv import load_dotenv

    startup_logger.info("✓ dotenv imported")
except Exception as e:
    startup_logger.error(f"✗ Failed to import dotenv: {e}")
    startup_logger.error(traceback.format_exc())
    sys.exit(1)
try:
    from sqlalchemy.exc import InterfaceError, OperationalError
    from sqlalchemy.orm import Session

    startup_logger.info("✓ sqlalchemy.orm and exceptions imported")
except Exception as e:
    startup_logger.error(f"✗ Failed to import sqlalchemy.orm: {e}")
    startup_logger.error(traceback.format_exc())
    sys.exit(1)

try:
    from core import models

    startup_logger.info("✓ core.models imported")
except (ImportError, TypeError) as e:
    startup_logger.error(f"✗ Failed to import core.models: {e}")
    startup_logger.error(traceback.format_exc())
    sys.exit(1)

try:
    from core import models_registration

    startup_logger.info("✓ core.models_registration imported")
except (ImportError, TypeError) as e:
    startup_logger.error(f"✗ Failed to import core.models_registration: {e}")
    startup_logger.error(traceback.format_exc())
    sys.exit(1)

try:
    from core.cache import RedisCacheService

    startup_logger.info("✓ core.cache.RedisCacheService imported")
except Exception as e:
    startup_logger.error(f"✗ Failed to import RedisCacheService: {e}")
    startup_logger.error(traceback.format_exc())
    sys.exit(1)

try:
    from core.database import SessionLocal, get_db

    startup_logger.info("✓ core.database imported")
except Exception as e:
    startup_logger.error(f"✗ Failed to import core.database: {e}")
    startup_logger.error(traceback.format_exc())
    sys.exit(1)

try:
    from core.quota_manager import quota_manager

    startup_logger.info("✓ core.quota_manager imported")
except Exception as e:
    startup_logger.warning(f"Failed to import quota_manager: {e}")

# Logging already initialized at the very top
logger = startup_logger

try:
    import time

    print(f"[{time.time()}] Starting imports in main_api_app.py...")
    from fastapi import Depends, FastAPI, HTTPException, Request, Response

    print(f"[{time.time()}] FastAPI imported")
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.openapi.utils import get_openapi
    from fastapi.responses import JSONResponse

    startup_logger.info("✓ FastAPI imports successful")
except Exception as e:
    startup_logger.error(f"✗ Failed to import FastAPI: {e}")
    startup_logger.error(traceback.format_exc())
    sys.exit(1)

# --- V2 IMPORTS (Architecture) ---
from core.circuit_breaker import circuit_breaker
from core.lazy_integration_registry import (
    API_ROUTER_REGISTRY,
    ESSENTIAL_API_ROUTERS,
    ESSENTIAL_BACKGROUND_SERVICES,
    get_integration_list,
    get_loaded_integrations,
    load_integration,
)
from core.resource_guards import MemoryGuard
from core.security import (
    CSRFProtectionMiddleware,
    ExternalAPIRateLimitMiddleware,
    InputValidationMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from core.security_dependencies import get_current_user
from core.models import User

try:
    from core.integration_loader import (
        IntegrationLoader,  # Kept for backward compatibility if needed
    )
except (ImportError, TypeError, Exception) as e:
    IntegrationLoader = None
    logger.warning(f"IntegrationLoader could not be imported (likely numpy/lancedb issue): {e}")

# --- PHASE 21 IMPORTS ---
# --- PHASE 21 IMPORTS (Ported Routes) ---
from datetime import timezone

from core.cache import redis_cache as cache_service
from middleware.audit_middleware import AuditMiddleware


# Helper for fragile imports (e.g. lancedb ClassVar error on Python 3.9)
def safe_import_router(module_path: str, router_name: str = "router"):
    try:
        from fastapi import APIRouter
    except (ImportError, TypeError):

        class APIRouter:
            pass  # Fallback for extremely broken environments

    try:
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, router_name)
    except (ImportError, TypeError, Exception) as e:
        logger.warning(f"Fallback: Could not import {module_path} ({type(e).__name__}): {e}")
        return APIRouter()


analytics_router = safe_import_router("api.routes.analytics_routes")
usage_analytics_router = safe_import_router("api.routes.usage_analytics_routes")
tenant_router = safe_import_router("api.routes.tenant_routes")
tenant_ownership_router = safe_import_router("api.routes.tenant_ownership_routes")
workspace_router = safe_import_router("api.routes.workspace_routes")
tenant_public_router = safe_import_router("api.routes.tenant_routes")
risk_router = safe_import_router("api.routes.risk_routes")
integration_canvas_router = safe_import_router("api.routes.integrations.integration_canvas_routes")
activity_router = safe_import_router("api.routes.activity_routes")
meta_compliance_router = safe_import_router("api.routes.meta_compliance_routes")
template_router = safe_import_router("api.routes.workflow_template_routes")
proposal_router = safe_import_router("api.routes.proposal_routes")
feature_flag_router = safe_import_router("api.routes.feature_flag_routes")
shell_audit_router = safe_import_router("api.routes.shell_audit_routes")
shell_security_router = safe_import_router("api.routes.shell_security_routes")
social_layer_router = safe_import_router("api.routes.social_layer_routes")
social_websocket_router = safe_import_router("api.routes.social_websocket_routes")
sandbox_router = safe_import_router("api.routes.sandbox_execution_routes")
external_api_router = safe_import_router("api.routes.external_api_routes")
package_router = safe_import_router("api.routes.package_management_routes")
platform_oauth_router = safe_import_router("api.routes.platform_oauth_routes")
entity_type_router = safe_import_router("api.routes.entity_type_routes")
agent_capability_router = safe_import_router("api.routes.agent_capability_routes")
capability_schema_router = safe_import_router("api.routes.capability_schema_routes")
ui_components_router = safe_import_router("api.routes.ui_components_routes")
infra_synthesis_router = safe_import_router("api.infra_synthesis_api")
maturity_policy_router = safe_import_router("api.maturity_policy_api")
agent_integration_router = safe_import_router("api.routes.agent_integration_routes")
entity_query_router = safe_import_router("api.routes.entity_query_routes")
entity_skill_router = safe_import_router("api.routes.entity_skill_routes")
multi_entity_extraction_router = safe_import_router("api.routes.multi_entity_extraction_routes")
entity_linking_router = safe_import_router("api.routes.entity_linking_routes")
ingestion_crud_router = safe_import_router("api.routes.ingestion_crud_routes")
meta_agent_router = safe_import_router("api.routes.meta_agent_routes")
alpha_evolve_router = safe_import_router("api.alpha_evolve_api")
custom_integration_router = safe_import_router("api.custom_integration_api")
integration_oauth_router = safe_import_router("api.routes.integrations.integration_oauth_routes")
token_refresh_router = safe_import_router("api.routes.integrations.token_refresh_routes")
webhook_renewal_router = safe_import_router("api.routes.integrations.webhook_renewal_routes")
subscription_management_router = safe_import_router(
    "api.routes.integrations.subscription_management_routes"
)
memory_pipeline_router = safe_import_router("api.routes.integrations.memory_pipeline_routes")
hosting_router = safe_import_router("api.routes.hosting_routes")
sdlc_router = safe_import_router("api.routes.sdlc_routes")
coding_agent_router = safe_import_router("api.routes.coding_agent_routes")
testing_agent_router = safe_import_router("api.routes.testing_agent_routes")
agent_routes_v2_router = safe_import_router("api.routes.agent_routes")
spend_router = safe_import_router("api.routes.spend_routes")
budget_alert_router = safe_import_router("api.routes.budget_alert_routes")
health_router = safe_import_router("api.routes.health_routes")
industrial_router = safe_import_router("api.routes.industrial_routes")
system_admin_router = safe_import_router("api.routes.system_admin_routes")
agent_feed_router = safe_import_router("api.routes.agent_feed_routes")
agent_health_router = safe_import_router("api.routes.agent_health_routes")
external_health_router = safe_import_router("api.routes.external_health_routes")
pricing_router = safe_import_router("api.routes.pricing_routes")
messaging_router = safe_import_router("api.routes.messaging_routes")
platform_webhook_router = safe_import_router("api.routes.webhooks")
ingestion_webhooks_router = safe_import_router("api.routes.webhooks.ingestion_webhooks")
supervision_router = safe_import_router("api.routes.supervision_routes")
supervised_queue_router = safe_import_router("api.routes.supervised_queue_routes")
core_user_activity_router = safe_import_router("api.routes.user_activity_routes")
operational_router = safe_import_router("api.routes.operational_routes")
operations_router = safe_import_router("api.routes.operations_routes")
agent_status_router = safe_import_router("api.routes.agent_status_routes")
user_templates_router = safe_import_router("api.routes.user_templates_routes")
workflow_versioning_router = safe_import_router("api.routes.workflow_versioning_routes")
forensics_router = safe_import_router("api.routes.forensics_routes")
debug_router = safe_import_router("api.routes.debug_routes")
agent_router = safe_import_router("api.routes.agent_routes")
workflow_router = safe_import_router("api.routes.workflow_routes")
workflow_template_router = safe_import_router("api.routes.workflow_template_routes")
delegation_chain_router = safe_import_router("api.routes.delegation_chain_routes")
fleet_batch_router = safe_import_router("api.routes.fleet_batch_routes")
fleet_observability_router = safe_import_router("api.routes.fleet_observability_routes")
scaling_router = safe_import_router("api.routes.scaling_routes")
integration_memory_router = safe_import_router("api.routes.integration_memory_routes")
qstash_router = safe_import_router("core.qstash_worker")
protection_router = safe_import_router("api.routes.protection_routes")
office_router = safe_import_router("api.office_routes")

# --- CONFIGURATION & ENVIRONMENT ---
# Logging already initialized at the top of file


# Load environment variables with fallback search
def load_env():
    # Priority 1: Current directory (common in Docker/Production)
    env_paths = [
        Path.cwd() / ".env",
        # Priority 2: Parent directory (common in Local development)
        Path(__file__).parent.parent / ".env",
        # Priority 3: Explicit /app/.env (Docker standard)
        Path("/app/.env"),
    ]

    loaded = False
    for path in env_paths:
        if path.exists():
            load_dotenv(path, override=True)
            logger.info("Configuration loaded", extra={"env_path": str(path)})
            loaded = True
            break

    if not loaded:
        logger.warning("No .env file found in any expected location. Realizing on system env vars.")

    # Sync Zoho variable names to prevent 'None' during auth
    if os.getenv("ZOHO_CRM_CLIENT_ID") and not os.getenv("ZOHO_CLIENT_ID"):
        os.environ["ZOHO_CLIENT_ID"] = os.getenv("ZOHO_CRM_CLIENT_ID")
    if os.getenv("ZOHO_CRM_CLIENT_SECRET") and not os.getenv("ZOHO_CLIENT_SECRET"):
        os.environ["ZOHO_CLIENT_SECRET"] = os.getenv("ZOHO_CRM_CLIENT_SECRET")


load_env()
deepseek_status = os.getenv("DEEPSEEK_API_KEY")
logger.info("Startup API key check", extra={"deepseek_api_key_present": bool(deepseek_status)})

# Environment settings
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "atomagentos.com,api.atomagentos.com,localhost,127.0.0.1,localhost:8000,127.0.0.1:8000,testserver",
).split(",")

# Ensure custom domain is allowed in CORS
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://atomagentos.com,https://app.atomagentos.com,https://admin.atomagentos.com,https://api.atomagentos.com,http://localhost:3000,http://127.0.0.1:3000",
).split(",")
# Add any extra origins from env
extra_origins = os.getenv("ADDITIONAL_ALLOWED_ORIGINS")
if extra_origins:
    ALLOWED_ORIGINS.extend(extra_origins.split(","))

ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]
logger.info(f"CORS Allowed Origins: {ALLOWED_ORIGINS}")
DISABLE_DOCS = ENVIRONMENT == "production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_listener_instance
    # --- STARTUP ---
    logger.info("=" * 60)
    logger.info("ATOM Platform Starting (Hybrid Mode)")
    logger.info("=" * 60)

    # 0. Initialize Database
    try:
        logger.info("Initializing database tables...")
        from core.admin_bootstrap import ensure_admin_user
        from core.database import engine
        from core.models import Base

        # Base.metadata.create_all is safe to call but can be slow/hang in production with 12k lines
        try:
            # Skip creation if in test mode or production
            is_test_mode = (
                os.getenv("PYTEST_VERSION") is not None
                or os.getenv("PYTEST_CURRENT_TEST") is not None
            )
            if os.getenv("ENVIRONMENT") != "production" and not is_test_mode:
                Base.metadata.create_all(bind=engine)
                logger.info("✓ Database tables initialized")
            elif is_test_mode:
                logger.info("⊘ Skipping table creation in test mode (fixture managed)")
            else:
                logger.info("⏩ Skipping table creation in production (Alembic managed)")
        except (InterfaceError, OperationalError) as e:
            logger.error(f"⚠️ Database connection issues during table creation: {e}")
            logger.error("Will attempt to proceed, but database operations may fail.")
        except Exception as e:
            logger.error(f"⚠️ Unexpected error during table creation: {e}")
            logger.error(traceback.format_exc())

        try:
            is_test_mode = (
                os.getenv("PYTEST_VERSION") is not None
                or os.getenv("PYTEST_CURRENT_TEST") is not None
            )
            if not is_test_mode:
                logger.info("Bootstrapping essential data (admin, tenants)...")
                ensure_admin_user()
                logger.info("✓ Bootstrap complete")
            else:
                logger.info("⊘ Skipping admin bootstrap in test mode (fixture managed)")
        except Exception as e:
            logger.error(f"⚠️ Core bootstrap failed (admin/tenants): {e}")

    except (ImportError, TypeError) as e:
        logger.error(f"CRITICAL: Database module import failed: {e}")
        logger.error("Application will continue in degraded mode")
    except Exception as e:
        logger.error(f"CRITICAL: Overall database initialization failed: {e}")
        logger.error(traceback.format_exc())
        # DO NOT crash - try to continue so health check can report the failure

    # 1. Load Essential Integrations (moved to module level for eager loading)
    # This prevents double-registration and ensures consistent prefixes
    logger.info(f"Loaded integrations so far: {list(_loaded_integrations)}")

    # 2. Start Background Services (Schedulers, Workers)
    # COMPLETELY SKIP DURING TESTS to prevent hangs/deadlocks
    is_test_mode = (
        os.getenv("PYTEST_VERSION") is not None or os.getenv("PYTEST_CURRENT_TEST") is not None
    )
    if os.getenv("ENABLE_SCHEDULER", "true").lower() == "true" and not is_test_mode:
        # Startup Coordinator: Ensure registration tasks run only once per day
        qstash_init_skip = False
        try:
            startup_session_key = (
                f"system:startup:qstash_init:{datetime.now().strftime('%Y-%m-%d')}"
            )
            if cache_service and not os.getenv("FORCE_QSTASH_INIT", "false").lower() == "true":
                if cache_service.get(startup_session_key):
                    qstash_init_skip = True
        except Exception:
            pass

        # 1. Start Workflow Scheduler
        try:
            from ai.workflow_scheduler import workflow_scheduler

            if not qstash_init_skip:
                await workflow_scheduler.start()
        except Exception:
            pass

        # 2. Start Agent Scheduler
        try:
            from core.scheduler import AgentScheduler

            asyncio.create_task(AgentScheduler.get_instance().load_scheduled_agents())
        except Exception:
            pass

        # 3. Start Memory Maintenance
        try:
            from core.memory_maintenance import start_memory_maintenance

            if not qstash_init_skip:
                await start_memory_maintenance()
        except Exception:
            pass

        # 4. Start Intelligence Worker
        try:
            from ai.intelligence_background_worker import intelligence_worker

            await intelligence_worker.start()
        except Exception:
            pass
        # 5. Background Maintenance (Reaper, etc.)
        try:
            from core.startup_tasks import run_startup_maintenance

            await run_startup_maintenance()
        except Exception as e:
            logger.error(f"Failed to start startup maintenance: {e}")

        # 6. Start Hybrid Ingestion scheduled sync loop (pull integrations into memory)
        # Opt-in via env (default off) to avoid surprising existing deployments.
        if os.getenv("ENABLE_INGESTION_SYNC", "false").lower() == "true":
            try:
                from core.hybrid_data_ingestion import get_hybrid_ingestion_service

                ingestion_service = get_hybrid_ingestion_service()
                asyncio.create_task(ingestion_service.run_scheduled_syncs())
                logger.info("✓ Hybrid ingestion scheduled-sync loop started (ENABLE_INGESTION_SYNC=true)")
            except Exception as e:
                logger.error(f"Failed to start hybrid ingestion sync loop: {e}")
    elif is_test_mode:
        logger.info("⊘ Skipping Schedulers and Workers in test mode")

    # 6. Start Postgres Event Bus (SKIP IN TEST MODE - causes hangs)
    if not is_test_mode:
        try:
            from core.agent_event_bus import get_agent_event_bus

            await get_agent_event_bus().start()
            logger.info("✓ Postgres Event Bus listener running")
        except Exception as e:
            logger.error(f"Failed to start Postgres Event Bus: {e}")
    else:
        logger.info("⊘ Skipping Postgres Event Bus in test mode")

    # 1. Main Resource Routes (V1)
    # [REFACTORED] app.include_router calls moved to module level to prevent recursive lifespan loops.

    # 7. Initialize AI Workflow Service
    try:
        from api.routes.enhanced_ai_workflow_routes import ai_service

        await ai_service.initialize_sessions()
        logger.info("✓ AI Workflow Service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize AI Workflow Service: {e}")

    # Start Distributed Debug System Aggregator (event-driven, scale-to-zero compatible)
    try:
        from core.debug_log_aggregator import start_aggregator

        await start_aggregator()
        logger.info("✅ Debug System Aggregator running (event-driven mode)")
    except Exception as e:
        logger.error(f"Failed to start Debug System Aggregator: {e}")

    # QStash Auto-Cleanup (Prevent DLQ buildup from orphaned schedules)
    # Only run if qstash_init_skip is False to avoid redundant LIST calls
    try:
        if not qstash_init_skip:
            from core.schedule_cleanup import cleanup_old_schedules

            await cleanup_old_schedules()
            logger.info("✓ QStash schedule auto-cleanup complete")

            # Registration successful - mark session as complete
            try:
                if cache_service:
                    cache_service.set(startup_session_key, "complete", ttl=86400)
            except Exception:
                pass
        else:
            logger.info("⏩ Skipping redundant QStash schedule cleanup")
    except Exception as e:
        logger.warning(f"QStash schedule cleanup skipped: {e}")

    # 8. Start Supervision System Workers (Ported from Upstream)
    if os.getenv("ENABLE_SCHEDULER", "true").lower() == "true" and not is_test_mode:
        try:
            from workers.activity_state_worker import ActivityStateWorker
            from workers.queue_processing_worker import QueueProcessingWorker

            # Start Activity State Worker (online/away/offline transitions)
            activity_worker = ActivityStateWorker(interval_seconds=60)
            asyncio.create_task(activity_worker.run())
            logger.info("✓ Activity State Worker running")

            # Start Queue Processing Worker (supervised execution)
            queue_worker = QueueProcessingWorker(interval_seconds=60)
            asyncio.create_task(queue_worker.run())
            logger.info("✓ Queue Processing Worker running")

            # 9. Start Webhook Renewal Worker (NEW)
            from core.database import SessionLocal
            from core.scheduled_webhook_renewal import ScheduledWebhookRenewalService

            async def renewal_loop():
                # Initial delay to avoid thundering herd on startup
                await asyncio.sleep(300)
                while True:
                    try:
                        logger.info("Starting scheduled webhook renewal check...")
                        with SessionLocal() as db:
                            service = ScheduledWebhookRenewalService(db)
                            await service.run_renewal_job()
                        logger.info("Scheduled webhook renewal check complete.")
                    except Exception as e:
                        logger.error(f"Error in webhook renewal loop: {e}")

                    # Wait 24 hours
                    await asyncio.sleep(86400)

            asyncio.create_task(renewal_loop())
            logger.info("✓ Webhook Renewal loop started")

        except Exception as e:
            logger.error(f"Failed to start Supervision System or Webhook Renewal workers: {e}")

    # 10. Start Webhook Processing Worker (CRITICAL for real-time ingestion)
    # This is OUTSIDE the supervision try block so it always starts independently
    try:
        from core.webhook_processing_worker import get_webhook_worker

        logger.info("[STARTUP] About to start Webhook Processing Worker...")
        webhook_worker = get_webhook_worker()
        logger.info("[STARTUP] Webhook worker instance created")
        asyncio.create_task(webhook_worker.run())
        logger.info("✓ Webhook Processing Worker running (processes ingestion:webhook:jobs queue)")
    except Exception as e:
        logger.error(f"CRITICAL: Failed to start Webhook Processing Worker: {e}")

    # 11. Start POMDP Memory Consolidation (offline "sleep-inspired" cycle)
    # Runs every CONSOLIDATION_INTERVAL_HOURS (6h). Previously the service
    # existed but nothing ever invoked it — the advertised feature was inert.
    if not is_test_mode:
        try:
            async def _consolidation_loop():
                from core.memory.memory_consolidation_service import MemoryConsolidationService, CONSOLIDATION_INTERVAL_HOURS
                from core.database import SessionLocal
                interval = CONSOLIDATION_INTERVAL_HOURS * 3600
                while True:
                    try:
                        svc = MemoryConsolidationService(db=SessionLocal())
                        await svc.run_consolidation_cycle()
                        logger.info("✓ POMDP memory consolidation cycle complete")
                    except Exception as ce:
                        logger.warning(f"Memory consolidation cycle failed (non-fatal): {ce}")
                    await asyncio.sleep(interval)
            asyncio.create_task(_consolidation_loop())
            logger.info("✓ POMDP Memory Consolidation background task started (6h interval)")
        except Exception as e:
            logger.warning(f"Could not start memory consolidation loop (non-fatal): {e}")

    logger.info("=" * 60)
    logger.info("✓ Server Ready")

    yield

    # --- SHUTDOWN ---
    logger.info("Shutting down ATOM Platform...")

    # Stop Webhook Processing Worker
    try:
        from core.webhook_processing_worker import get_webhook_worker

        get_webhook_worker().stop()
        logger.info("✓ Webhook Processing Worker stopped")
    except:
        pass

    try:
        from ai.workflow_scheduler import workflow_scheduler

        workflow_scheduler.shutdown()
        logger.info("✓ Workflow Scheduler stopped")
    except:
        pass

    # Stop Distributed Debug System Aggregator
    try:
        from core.debug_log_aggregator import stop_aggregator

        await stop_aggregator()
        logger.info("✅ Debug System Aggregator stopped")
    except:
        pass

    # Stop Availability Background Worker (NEW - Supervision System)
    try:
        from core.availability_background_worker import stop_worker

        await stop_worker()
        logger.info("✓ Availability Background Worker stopped")
    except:
        pass

    try:
        from core.memory_maintenance import stop_memory_maintenance

        await stop_memory_maintenance()
        logger.info("✓ Memory Maintenance Scheduler stopped")
    except:
        pass

    try:
        from core.agent_event_bus import get_agent_event_bus

        await get_agent_event_bus().stop()
        logger.info("✓ Postgres Event Bus listener stopped")
    except:
        pass

    try:
        from api.routes.enhanced_ai_workflow_routes import ai_service

        await ai_service.cleanup_sessions()
        logger.info("✓ AI Workflow Service sessions cleaned up")
    except:
        pass

    try:
        from api.routes.learning_routes import shutdown_learning_service

        await shutdown_learning_service()
        logger.info("✓ Learning Service shutdown complete")
    except:
        pass


# --- APP INITIALIZATION ---
startup_logger.info("Creating FastAPI application...")
try:
    app = FastAPI(
        title="ATOM API",
        description="Advanced Task Orchestration & Management API - Multi-tenant AI agent platform",
        version="8.0.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 1,  # Start with models collapsed
            "displayRequestDuration": True,  # Show request duration
            "docExpansion": "list",  # Show all endpoints in list view
            "filter": True,  # Enable search filtering
            "persistAuthorization": True,  # Keep auth across page reloads
            "tryItOutEnabled": True,  # Enable "Try it out" feature
            "syntaxHighlight": {"activate": True, "theme": "monokai"},  # Dark theme for code blocks
        },
    )
    startup_logger.info("✓ FastAPI app instance created")

    # Initialize connection leak detector
    try:
        from core.connection_leak_detector import install_connection_tracking

        install_connection_tracking()
        startup_logger.info("✓ Connection leak detector installed")
    except Exception as e:
        startup_logger.warning(f"✗ Failed to install connection leak detector: {e}")

    # --- CORE HEALTH ENDPOINTS (FIRST PRIORITY) ---
    @app.get("/alive", tags=["System"])
    async def liveness():
        """Simple liveness check for Fly.io."""
        return {
            "status": "alive",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "debug_id": "v2.1.0-final-qa-1",  # Unique ID for this build
        }

    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint."""
        return {"name": "ATOM Platform API", "version": "2.1.0", "status": "running"}

    @app.get("/health", tags=["System"])
    @app.get("/api/health", tags=["System"])
    async def health_check():
        """
        Consolidated health check endpoint that validates core dependencies.
        Uses standardized logic from core.health.
        """
        from core.health import perform_health_checks

        health_data = perform_health_checks()

        # Flatten for E2E test compatibility while maintaining 'services' for legacy
        # Read deployed version from build-time stamp
        try:
            with open("/app/backend-saas/VERSION.txt") as f:
                deployed_sha = f.read().strip()
        except Exception:
            deployed_sha = "unknown"

        health_status = {
            "status": health_data["status"],
            "version": "2.1.0",
            "deployed_sha": deployed_sha,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": health_data["services"]["database"],
            "redis": health_data["services"]["redis"],
            "vector_store": health_data["services"]["vector_store"],
            "services": health_data["services"],
            "memory_mb": round(MemoryGuard.get_memory_usage_mb(), 2)
            if "MemoryGuard" in globals()
            else 0.0,
        }

        # Only return 503 for critical failures (database)
        if health_data["services"]["database"] != "operational":
            return JSONResponse(status_code=503, content=health_status)

        return health_status

    # Global exception handler - ensures all errors return JSON, never HTML
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch all unhandled exceptions and return JSON response."""
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal server error occurred. Please try again.",
                "path": request.url.path,
            },
        )

except Exception as e:
    startup_logger.error(f"✗ CRITICAL: Failed to create FastAPI app: {e}")
    startup_logger.error(traceback.format_exc())

    # Create a minimal fallback app for diagnostics
    startup_logger.info("Creating minimal diagnostic app...")
    try:
        from datetime import datetime

        from fastapi import FastAPI as FastAPIFallback

        app = FastAPIFallback(title="ATOM API - Degraded Mode")

        @app.get("/")
        async def root():
            return {
                "status": "degraded",
                "error": "Application failed to initialize",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": str(e),
            }

        @app.get("/alive")
        async def alive():
            return {"status": "alive", "mode": "degraded"}

        startup_logger.info("✓ Minimal diagnostic app created")
    except Exception as fallback_error:
        startup_logger.error(f"✗ Even fallback app creation failed: {fallback_error}")
        sys.exit(1)


# ============================================================================
# CUSTOM OPENAPI SCHEMA WITH SECURITY SCHEMES
# ============================================================================


def custom_openapi():
    """
    Generate custom OpenAPI schema with security schemes and comprehensive metadata.

    Enhances the default FastAPI OpenAPI schema with:
    - Detailed API description
    - Multiple authentication methods (JWT, API Key, BYOK)
    - Rate limiting information
    - Contact and license information
    - Tags for organizing endpoints
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="ATOM SaaS Platform API",
        version="8.0.0",
        routes=app.routes,
        description="""
# ATOM SaaS Platform API

Multi-tenant AI agent platform with comprehensive brain systems and graduated maturity levels.

## Authentication

The ATOM API supports multiple authentication methods:

### JWT Token Authentication
Use `Authorization: Bearer <token>` header. Tokens are obtained via `/api/auth/login`.

### API Key Authentication
Use `X-API-Key: <key>` header for service accounts. Generate keys from the dashboard.

### BYOK (Bring Your Own OpenAI Key)
Use `X-BYOK-OpenAI-Key: <key>` header to use your own OpenAI account for embeddings.

## Rate Limiting

Rate limits are enforced per tenant based on plan tier:

| Union[Plan, Daily] | Per-Minute |
|------|-------|------------|
| Union[Free, 50] | 60 |
| Union[Solo, 500] | 100 |
| Union[Team, 5],Union[000, 500] |
| Union[Enterprise, Unlimited] | Union[Custom, Rate] limit headers are included in all responses:
- `X-RateLimit-Limit`: Request limit per window
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Multi-Tenancy

All endpoints automatically filter by tenant context from authentication.
The `X-Tenant-ID` header is automatically set based on authentication.

## Agent Maturity Levels

Agents operate at different maturity levels with varying permissions:

- **student**: Read-only (search, browse)
- **intern**: Proposals, autonomous approval required
- **supervised**: Live monitoring, queue if unavailable
- **autonomous**: All actions, can supervise others

## Pagination

List endpoints support pagination with these query parameters:
- `page`: Page number (default: 1, min: 1)
- `limit`: Items per page (default: 20, max: 100)
- `sort`: Sort field (e.g., created_at, name)
- `order`: Sort direction (asc, desc)

Response includes pagination metadata:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "pages": 8
  }
}
```

## Error Handling

All errors return a consistent format:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "details": {}
  },
  "meta": {
    "timestamp": "2026-03-19T10:00:00Z",
    "request_id": "req_abc123"
  }
}
```

## Base URLs

- **Production**: `https://api.atomagentos.com`
- **Development**: `http://localhost:8000`

## Documentation

- [Interactive API Reference](https://atomagentos.com/docs/api/reference)
- [Authentication Guide](https://atomagentos.com/docs/api/authentication)
- [Error Codes](https://atomagentos.com/docs/api/errors)
        """,
        terms_of_service="https://atomagentos.com/terms",
        contact={
            "name": "API Support",
            "email": "support@atomagentos.com",
            "url": "https://atomagentos.com/support",
        },
        license_info={"name": "Proprietary", "url": "https://atomagentos.com/license"},
    )

    # Define tags for organizing endpoints
    tag_descriptions = {
        "agents": "Agent management, execution, and configuration operations",
        "Authentication": "User authentication, authorization, and session management",
        "graduation": "Agent maturity progression, episodic memory, and RLHF feedback",
        "governance": "Agent governance, permission checks, and rule enforcement",
        "Integrations": "Third-party service integrations (OAuth, webhooks)",
        "ai_workflows": "AI workflow creation, execution, and management",
        "billing": "Subscription management, usage tracking, and invoicing",
        "webhooks": "Webhook configuration, event delivery, and signature verification",
        "Canvas": "Canvas skill creation, marketplace, and component management",
        "System": "Health checks, status endpoints, and system information",
    }

    # Add tag descriptions to schema
    if "tags" not in openapi_schema:
        openapi_schema["tags"] = []

    existing_tag_names = {tag.get("name") for tag in openapi_schema["tags"]}
    for tag_name, description in tag_descriptions.items():
        if tag_name not in existing_tag_names:
            openapi_schema["tags"].append(
                {"name": tag_name, "description": description, "x-displayName": tag_name.title()}
            )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "JWTAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token from /api/auth/login. Expires in 15 minutes.",
        },
        "APIKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key from dashboard settings. Format: atom_sk_<uuid>",
        },
        "BYOKAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-BYOK-OpenAI-Key",
            "description": "Optional: Tenant's OpenAI API key for custom embeddings (sk-...)",
        },
    }

    # Apply default security (can be overridden per-route)
    openapi_schema["security"] = [{"JWTAuth": []}]

    # Add servers section
    openapi_schema["servers"] = [
        {"url": "https://api.atomagentos.com", "description": "Production server"},
        {"url": "http://localhost:8000", "description": "Local development server"},
    ]

    # Add extension for logo
    if "info" in openapi_schema:
        openapi_schema["info"]["x-logo"] = {
            "url": "https://atomagentos.com/logo.png",
            "backgroundColor": "#020617",
            "altText": "ATOM Platform Logo",
        }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# --- V2 INTEGRATION LOADING (EAGER) ---
# Track which integrations have been loaded
# (_loaded_integrations is now defined at the top of the file)

# Load essential integrations immediately to ensure they are available in the route table
# before the server starts receiving requests.
# SKIP during test mode to prevent hangs and speed up test initialization
is_test_mode = (
    os.getenv("PYTEST_VERSION") is not None or os.getenv("PYTEST_CURRENT_TEST") is not None
)
if API_ROUTER_REGISTRY and not is_test_mode:
    startup_logger.info(f"🚀 Eagerly loading {len(ESSENTIAL_API_ROUTERS)} essential API plugins...")
    from fastapi import APIRouter

    for name in ESSENTIAL_API_ROUTERS:
        if name in _loaded_integrations:
            continue

        try:
            router = load_integration(name, registry="api_routers")
            if router:
                # Standardize integration prefixes for consistent API routing
                # Skip for core auth/oauth which might have legacy root paths
                prefix = ""
                # Skip core system modules that have their own root paths or specialized prefixes
                is_core_module = name in [
                    "auth",
                    "oauth",
                    "atom_agent",
                    "workflow_ui",
                    "missing_endpoints",
                    "service_registry",
                    "byok",
                    "byok_competitive",
                    "system_status",
                    "service_health",
                    "workflow",
                    "analytics",
                    "enterprise",
                    "workflow_marketplace",
                    "enterprise_user_mgmt",
                    "integration_enhancement",
                    "industry_workflow",
                    "ai_workflow_optimization",
                    "enterprise_security",
                    "auto_healing",
                    "workflow_versioning",
                    "unified_task",
                    "unified_project",
                    "unified_calendar",
                    "unified_search",
                    "activity",
                    "social_layer",
                    "social_websocket",
                    "package",
                    "sdlc",
                    "coding_agent",
                    "testing_agent",
                    "spend",
                    "budget_alert",
                    "industrial",
                    "system_admin",
                    "agent_feed",
                    "tenant",
                    "workspace",
                    "risk",
                    "integration_canvas",
                    "team_messaging",
                    "voice",
                    "integration_health",
                ]

                if not is_core_module:
                    # Apply unified integration prefix
                    prefix = f"/api/v1/integrations/{name.replace('_', '-')}"

                # Robust Type Guard: Only include if it's an actual FastAPI router
                if isinstance(router, APIRouter):
                    app.include_router(router, prefix=prefix, tags=[name])
                    _loaded_integrations.add(name)
                    startup_logger.info(f"  ✓ {name} (prefix: {prefix or 'root'})")
                else:
                    # This should not happen now that we filter by API_ROUTER_REGISTRY
                    # but kept as a safety measure
                    startup_logger.warning(f"  ⚐ {name} (Loaded but is not an APIRouter)")
            else:
                startup_logger.warning(f"  ✗ {name} could not be loaded")
        except Exception as e:
            startup_logger.error(f"  ✗ Failed to load essential plugin {name}: {e}")
            logger.error(traceback.format_exc())

    # Initialize Essential Background Services (e.g., Singletons like MCP)
    if ESSENTIAL_BACKGROUND_SERVICES:
        startup_logger.info(
            f"⚙️ Initializing {len(ESSENTIAL_BACKGROUND_SERVICES)} essential background services..."
        )
        for name in ESSENTIAL_BACKGROUND_SERVICES:
            try:
                service_class = load_integration(name, registry="services")
                if service_class:
                    service_class()  # Initialize singleton/instance
                    startup_logger.info(f"  ✓ {name} initialized")
            except Exception as e:
                startup_logger.error(f"  ✗ Failed to initialize service {name}: {e}")
elif is_test_mode:
    startup_logger.info(
        "⊘ Test mode detected: Loading only critical integrations for security tests"
    )
    # Always load auth/oauth/whatsapp even in test mode for security tests
    critical_integrations = [
        "auth",
        "oauth",
        "whatsapp",
        "microsoft365",
        "outlook",
        "twilio",
        "notion",
        "mailchimp",
        "zoho_crm",
        "zoho_projects",
        "zoho_workdrive",
        "salesforce",
        "pipedrive",
        "freshsales",
        "asana",
        "monday",
        "bigcommerce",
    ]
    for name in critical_integrations:
        startup_logger.info(f"DEBUG: Processing critical integration: {name}")
        if name in _loaded_integrations:
            startup_logger.info(f"DEBUG: {name} already loaded, skipping")
            continue

        try:
            router = load_integration(
                name, registry="api_routers", timeout=10
            )  # Longer timeout for test mode
            if router:
                # Standardize integration prefixes
                prefix = ""
                if name == "whatsapp":
                    prefix = "/api/v1/integrations/whatsapp"
                elif name == "microsoft365":
                    prefix = "/api/v1/integrations/microsoft365"
                elif name == "outlook":
                    prefix = "/api/v1/integrations/outlook"
                elif name == "mailchimp":
                    prefix = "/api/v1/integrations/mailchimp"
                elif name == "zoho_crm":
                    prefix = "/api/v1/integrations/zoho-crm"
                elif name == "salesforce":
                    prefix = "/api/v1/integrations/salesforce"
                elif name == "pipedrive":
                    prefix = "/api/v1/integrations/pipedrive"
                elif name == "freshsales":
                    prefix = "/api/v1/integrations/freshsales"
                elif name == "twilio":
                    prefix = "/api/v1/integrations/twilio"
                elif name == "notion":
                    prefix = "/api/v1/integrations/notion"
                elif name == "asana":
                    prefix = "/api/v1/integrations/asana"
                elif name == "monday":
                    prefix = "/api/v1/integrations/monday"
                elif name == "bigcommerce":
                    prefix = "/api/v1/integrations/bigcommerce"
                elif name == "zoho_projects":
                    prefix = "/api/v1/integrations/zoho-projects"
                elif name == "zoho_workdrive":
                    prefix = "/api/v1/integrations/zoho-workdrive"

                if isinstance(router, APIRouter):
                    app.include_router(router, prefix=prefix, tags=[name])
                    _loaded_integrations.add(name)
                    startup_logger.info(
                        f"  ✓ {name} (critical for tests, prefix: {prefix or 'root'})"
                    )
                else:
                    startup_logger.warning(f"  ⚐ {name} (Loaded but is not an APIRouter)")
            else:
                startup_logger.warning(f"  ✗ {name} could not be loaded")
        except Exception as e:
            startup_logger.error(f"  ✗ Failed to load critical plugin {name}: {e}")
            logger.error(traceback.format_exc())

    startup_logger.info(f"  Other integrations will load on-demand.")

# --- FORCED ZOHO SUITE REGISTRATION (STABILIZATION) ---
# Skip in test mode to prevent hangs
if not is_test_mode:
    for zoho_module in ["zoho_workdrive", "zoho_crm", "zoho_books", "zoho_inventory"]:
        try:
            if zoho_module not in _loaded_integrations:
                router = load_integration(zoho_module, registry="api_routers")
                if router:
                    prefix = f"/api/v1/integrations/{zoho_module.replace('_', '-')}"
                    app.include_router(router, prefix=prefix, tags=[zoho_module])
                    _loaded_integrations.add(zoho_module)
                    logger.info(f"  ✓ {zoho_module} (Forced)")
        except Exception as e:
            logger.error(f"  ✗ Forced registration failed for {zoho_module}: {e}")


@app.get("/api/debug/integrations")
async def debug_integrations(current_user: User = Depends(get_current_user)):
    from core.lazy_integration_registry import ESSENTIAL_API_ROUTERS

    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            routes.append(
                f"{list(route.methods) if hasattr(route, 'methods') else '[]'} {route.path}"
            )

    return {
        "status": "active",
        "main_file": __file__,
        "cwd": os.getcwd(),
        "loaded_integrations": list(_loaded_integrations),
        "essential_integrations": ESSENTIAL_API_ROUTERS,
        "registered_routes": sorted(routes),
        "secret_key_configured": os.getenv("SECRET_KEY") is not None,
        "test_secret_configured": os.getenv("E2E_TEST_SECRET") is not None,
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "timestamp": datetime.now().isoformat(),
    }


# --- ERROR HANDLING ---
from core.error_handler import setup_error_handlers

setup_error_handlers(app)

# --- PHASE 28: ADVANCED ROUTER REGISTRATION ---
# Note: Many routes are already registered in lifespan() for deferred loading.
# Registrations here must use GLOBALLY IMPORTED routers from lines 171-185.

app.include_router(supervision_router)
app.include_router(supervised_queue_router)
app.include_router(core_user_activity_router)
app.include_router(operational_router)
app.include_router(operations_router, prefix="/api/v1/business-health", tags=["operations"])
app.include_router(forensics_router, prefix="/api/v1/forensics", tags=["forensics"])
app.include_router(agent_status_router, prefix="/api/v1", tags=["agents"])
app.include_router(agent_health_router, prefix="/api/admin", tags=["Agent Health"])
app.include_router(external_health_router, prefix="/api/v1", tags=["External Health"])
app.include_router(pricing_router, prefix="/api/v1", tags=["Pricing"])
app.include_router(user_templates_router)
app.include_router(workflow_versioning_router)
app.include_router(protection_router)
app.include_router(platform_webhook_router)
app.include_router(ingestion_webhooks_router, prefix="/api", tags=["webhooks-ingestion"])
app.include_router(office_router, prefix="/api/v1/office", tags=["office"])

# --- V1 RESOURCE ROUTES (Migrated from lifespan) ---
if agent_router:
    app.include_router(agent_router, prefix="/api/v1/agents", tags=["agents"])
if workflow_router:
    app.include_router(workflow_router, prefix="/api/v1/workflows", tags=["workflows"])

# Mount the live workflow endpoints (core/workflow_endpoints.py) at the
# advertised /api/v1/workflows path. The safe_import_router("api.routes.workflow_routes")
# above references a file that doesn't exist; this is the real router that has
# the conductor endpoint (POST /workflows/conductor/execute) + execute/resume.
try:
    from core.workflow_endpoints import router as live_workflow_router
    app.include_router(live_workflow_router, prefix="/api/v1/workflows", tags=["workflows"])
    logger.info("✓ Live Workflow Endpoints mounted at /api/v1/workflows (incl. /conductor/execute)")
except Exception as e:
    logger.warning(f"Could not mount live workflow endpoints: {e}")
if workflow_template_router:
    app.include_router(
        workflow_template_router,
        prefix="/api/v1/workflows/templates",
        tags=["workflow-templates"],
    )
if delegation_chain_router:
    app.include_router(delegation_chain_router, tags=["delegation-chains"])
if fleet_batch_router:
    app.include_router(fleet_batch_router)
if fleet_observability_router:
    app.include_router(fleet_observability_router, prefix="/api/v1", tags=["fleet-observability"])
if scaling_router:
    app.include_router(scaling_router)
if messaging_router:
    app.include_router(messaging_router, prefix="/api/v1/messaging", tags=["messaging"])
if alpha_evolve_router:
    app.include_router(alpha_evolve_router, prefix="/api/v1/alpha-evolve", tags=["alpha-evolve"])
if infra_synthesis_router:
    app.include_router(infra_synthesis_router, prefix="/api/v1", tags=["infrastructure"])
if maturity_policy_router:
    app.include_router(maturity_policy_router, prefix="/api/v1/config", tags=["config"])
if custom_integration_router:
    app.include_router(custom_integration_router, tags=["integrations"])
if token_refresh_router and len(token_refresh_router.routes) > 0:
    app.include_router(token_refresh_router, tags=["token-refresh"])
if webhook_renewal_router and len(webhook_renewal_router.routes) > 0:
    app.include_router(webhook_renewal_router, tags=["webhook-renewal"])
if subscription_management_router and len(subscription_management_router.routes) > 0:
    app.include_router(subscription_management_router, tags=["subscriptions"])
if multi_entity_extraction_router:
    app.include_router(multi_entity_extraction_router)
    app.include_router(memory_pipeline_router)
if hosting_router:
    app.include_router(hosting_router)
if integration_memory_router:
    app.include_router(integration_memory_router)
# qstash_router is optional - only include if sentry_sdk is available
if "qstash_router" in globals() and qstash_router:
    app.include_router(qstash_router, prefix="/api/v1/worker", tags=["worker"])


# Health check consolidated at the end of file


# Core validation handlers managed via setup_error_handlers


# Exception handlers are now consolidated in core.error_handler.setup_error_handlers(app)


# Initialize Cache
# Initialize Cache
cache_service = RedisCacheService()

# Global Redis Listener (initialized on startup)
redis_listener_instance = None

# Security Middleware (V2 Enhanced)
# Must be added BEFORE CORS so that CORS wraps them (UserMiddleware stack is reversed)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFProtectionMiddleware)
app.add_middleware(InputValidationMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
app.add_middleware(ExternalAPIRateLimitMiddleware, requests_per_minute=100)


# HTML to JSON Error Conversion Middleware
class HTMLErrorToJSONMiddleware:
    """
    Middleware to convert FastAPI's default HTML error pages to JSON responses.

    FastAPI's default exception handlers return HTML for validation errors and HTTPExceptions.
    This middleware intercepts those responses and converts them to JSON for API consistency.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Intercept the send function to modify responses
        status_code = None
        headers = None

        async def send_wrapper(message):
            nonlocal status_code, headers

            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = message.get("headers", [])

                # Check if this is an error response (4xx or 5xx)
                if status_code >= 400:
                    # Convert to JSON by modifying Content-Type
                    new_headers = []
                    content_type_is_html = False

                    for name, value in headers:
                        name_lower = name.decode().lower()
                        if name_lower == b"content-type":
                            if b"text/html" in value:
                                content_type_is_html = True
                            # Force JSON content type
                            new_headers.append((name, b"application/json"))
                        else:
                            new_headers.append((name, value))

                    # Update headers
                    message["headers"] = new_headers

                    # If we changed HTML to JSON, we need to intercept the body too
                    if content_type_is_html:
                        message["headers"] = tuple(
                            (name, b"application/json")
                            if name.decode().lower() == "content-type"
                            else (name, value)
                            for name, value in headers
                        )

            await send(message)

        # For response body interception, we'd need a more complex solution
        # For now, we'll rely on our custom exception handlers in the routes
        await self.app(scope, receive, send_wrapper)


# Add HTML-to-JSON conversion middleware (must be early in the stack)
app.add_middleware(HTMLErrorToJSONMiddleware)


# Custom Trusted Host Middleware that supports wildcard domains
class CustomTrustedHostMiddleware:
    """
    Custom middleware that allows wildcard subdomains for local development.

    - Allows any *.localhost subdomain (e.g., tenant.localhost)
    - Allows any *.testserver subdomain (for testing)
    - Otherwise uses exact match like TrustedHostMiddleware
    """

    def __init__(self, app, allowed_hosts):
        self.app = app
        self.allowed_hosts = set(allowed_hosts)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        host = headers.get(b"host", b"").decode()

        # Split host from port
        hostname = host.split(":")[0].lower()

        # Allow specific production domains and their subdomains
        production_suffixes = [
            ".localhost",
            ".testserver",
            ".atomagentos.com",
            ".app.atomagentos.com",
            ".atom-saas.fly.dev",
            ".atom-saas.com",
            ".ngrok-free.app",
        ]

        production_roots = [
            "atomagentos.com",
            "app.atomagentos.com",
            "atom-saas.fly.dev",
            "atom-saas.com",
            "localhost",
            "testserver",
            "127.0.0.1",
        ]

        if (
            hostname in production_roots
            or any(hostname.endswith(s) for s in production_suffixes)
            or hostname.startswith("172.")
        ):  # Allow Fly.io internal health checks
            await self.app(scope, receive, send)
            return

        # Exact match for other hosts
        if host in self.allowed_hosts:
            await self.app(scope, receive, send)
            return

        # Reject invalid host
        logger.warning(
            f"Rejecting request with invalid host header: {hostname} (Full host: {host})"
        )
        response = Response("Invalid host header", status_code=400)
        await response(scope, receive, send)


# Custom Trusted Host Middleware
app.add_middleware(CustomTrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# CORS Middleware (Standard V1/V2)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Retry-After",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    ],
)
app.add_middleware(AuditMiddleware)  # Register Audit Log


@app.middleware("http")
async def ultra_loud_logger(request: Request, call_next):
    from fastapi.responses import JSONResponse

    # DANGER: Only log in development
    is_development = (
        os.getenv("ENVIRONMENT") == "development" or os.getenv("LOUD_LOGGING") == "true"
    )

    if is_development:
        logger.info(f"🚀 [ULTRA LOUD] {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        if is_development:
            logger.info(
                f"🏁 [ULTRA LOUD] {request.method} {request.url.path} -> {response.status_code}"
            )
        return response
    except Exception as e:
        logger.error(f"💥 [ULTRA LOUD] Error processing {request.method} {request.url.path}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "message": "Internal server error",
                    "code": "INTERNAL_ERROR",
                    "details": {"exception": str(e)},
                },
            },
        )


# --- PHASE 74 MIDDLEWARE ---
from middleware.domain_routing_middleware import DomainRoutingMiddleware

app.add_middleware(DomainRoutingMiddleware)

# ============================================================================
# AUTO-LOADING MIDDLEWARE (True Lazy Loading)
# Automatically loads integrations on first request instead of returning 404
# ============================================================================

# Track which integrations have been loaded previously handled at top level

# Blacklist integrations that crash during loading (Python 3.13 compatibility issues)
_blacklisted_integrations = {
    # "atom_agent",  # Crashes due to numpy/lancedb issues
    "unified_calendar",  # May have similar issues
    "unified_task",  # May have similar issues
    # "unified_search" - NOW USING REAL LANCEDB, SAFE TO AUTO-LOAD!
}


@app.middleware("http")
async def auto_load_integration_middleware(request, call_next):
    global _loaded_integrations
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
            }

            if potential_integration == "v1":
                # Handle /api/v1/integrations/{name}
                if len(path_parts) >= 5 and path_parts[3] == "integrations":
                    potential_integration = path_parts[4]
                else:
                    potential_integration = None  # Core v1 route

            if potential_integration:
                # Get the actual integration name
                integration_name = integration_map.get(
                    potential_integration, potential_integration.replace("-", "_")
                )
            else:
                integration_name = None

            # Skip blacklisted integrations
            if integration_name in _blacklisted_integrations:
                logger.debug(f"⚠️ Skipping blacklisted integration: {integration_name}")
            # Check if this integration exists in registry and isn't loaded yet
            elif integration_name and integration_name not in _loaded_integrations:
                integration_list = get_integration_list()
                if integration_name in integration_list:
                    try:
                        logger.info(f"🔄 Auto-loading integration on-demand: {integration_name}")
                        router = load_integration(integration_name, registry="api_routers")
                        if router:
                            # Apply standard prefix based on integration name
                            prefix = f"/api/v1/integrations/{integration_name.replace('_', '-')}"
                            app.include_router(router, prefix=prefix, tags=[integration_name])
                            _loaded_integrations.add(integration_name)
                            logger.info(f"✓ Auto-loaded: {integration_name}")
                    except Exception as e:
                        logger.error(f"✗ Failed to auto-load {integration_name}: {e}")

    # Continue with the request
    # Note: Truly robust gating for the middleware would require identifying
    # the tenant BEFORE loading. We can extract X-Tenant-ID if present.
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id and path.startswith("/api/"):
        # We don't have a DB session here easily in the standard FastAPI middleware pattern
        # if not using a Depends wrapper. We'll use SessionLocal directly.
        with SessionLocal() as db:
            try:
                # Basic check for gated integrations (heuristic based on path)
                for integration_name, required_tier in {
                    "salesforce": "premium",
                    "hubspot": "premium",
                    "zendesk": "premium",
                }.items():
                    if integration_name in path.lower():
                        quota_manager.check_integration_access(tenant_id, integration_name, db)
            except HTTPException as e:
                return JSONResponse(
                    status_code=e.status_code,
                    content={
                        "success": False,
                        "error": {
                            "message": e.detail,
                            "code": "QUOTA_EXCEEDED"
                            if e.status_code == 403
                            else "INTEGRATION_ACCESS_ERROR",
                            "details": {},
                        },
                    },
                )

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
        from api.routes.chat_process_routes import router as chat_process_router
        from api.routes.connected_services_routes import router as connected_services_router
        from api.routes.system_health_routes import router as system_health_router
        from api.routes.user_management_routes import router as user_mgmt_router

        app.include_router(user_mgmt_router, prefix="/api/v1")
        app.include_router(system_health_router, prefix="/api/v1")
        app.include_router(connected_services_router, prefix="/api/v1")
        app.include_router(chat_process_router, prefix="/api/v1")

        # Backward compatibility for the /integrations list
        from api.routes.integrations.integrations_catalog_routes import router as catalog_router

        app.include_router(catalog_router, prefix="")

        # Integration Registry API (Capability Discovery)
        from api.routes.integration_registry_routes import router as integration_registry_router

        app.include_router(integration_registry_router)

        # Capability Schema API
        app.include_router(capability_schema_router)

        # UI Components API (Dynamic Component Resolution)
        app.include_router(ui_components_router)
    except (ImportError, TypeError) as e:
        logger.error(f"Failed to load Core API routes: {e}")

    # 2. Workflow Engine
    try:
        from api.routes.availability_routes import router as availability_router

        app.include_router(availability_router, prefix="/api/v1")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load availability routes: {e}")

    # Unified Chat Routes (Telegram & Slack)
    try:
        from api.routes.integrations.telegram_chat_routes import router as telegram_chat_router

        app.include_router(telegram_chat_router)
        logger.info("✓ Telegram Chat Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Telegram chat routes: {e}")

    try:
        from api.routes.integrations.slack_chat_routes import router as slack_chat_router

        app.include_router(slack_chat_router)
        logger.info("✓ Slack Chat Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Slack chat routes: {e}")

    try:
        from api.routes.stakeholder_routes import router as stakeholder_router

        app.include_router(stakeholder_router, prefix="/api/v1")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load stakeholder routes: {e}")

    try:
        from api.routes.report_routes import router as reports_router

        app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load reports routes (skipping): {e}")

    # External Resource Routes (already consolidated in V1 block above)
    # Keeping block for future extensions
    pass

    # Desktop Authentication (Secure API Keys)
    try:
        from api.routes.desktop_auth_routes import router as desktop_auth_router

        app.include_router(desktop_auth_router, prefix="/api/desktop/keys", tags=["desktop-auth"])
        logger.info("✅ Desktop authentication routes enabled (secure API keys)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load desktop auth routes (skipping): {e}")

    # Public API Key Authentication (External Marketplace)
    try:
        from api.routes.public_api_routes import router as public_api_router

        app.include_router(public_api_router, prefix="/api/public", tags=["public-api"])
        logger.info("✅ Public API key authentication routes enabled")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load public API routes (skipping): {e}")

    # Public Marketplace API (Skill submission, rating)
    try:
        from api.routes.public_marketplace_routes import router as public_marketplace_router

        app.include_router(
            public_marketplace_router, prefix="/api/public/v1", tags=["public-marketplace"]
        )
        logger.info("✅ Public marketplace routes enabled")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load public marketplace routes (skipping): {e}")

    # Public Marketplace v1 API (Read-Only Browsing)
    try:
        from api.routes.public_marketplace_routes import public_v1_router

        app.include_router(public_v1_router, tags=["public-marketplace-v1"])
        logger.info("✅ Public marketplace v1 read-only API routes enabled")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load public marketplace v1 routes (skipping): {e}")

    # Private Marketplace API (Tenant-Specific Skills)
    try:
        from api.routes.private_marketplace_routes import router as private_marketplace_router

        app.include_router(private_marketplace_router)
        logger.info("✅ Private marketplace routes enabled")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load private marketplace routes (skipping): {e}")

    # AI Training Period Configuration
    try:
        from api.routes.training_routes import router as training_router

        app.include_router(training_router, tags=["agent-training"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load training routes (skipping): {e}")

    # Training Analytics & Monitoring
    try:
        from api.routes.training_analytics_routes import router as training_analytics_router

        app.include_router(training_analytics_router, tags=["training-analytics"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load training analytics routes (skipping): {e}")

    # Enhanced Feedback System (from upstream)
    try:
        from api.routes.feedback_enhanced_routes import router as feedback_enhanced_router

        app.include_router(feedback_enhanced_router, tags=["feedback"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load enhanced feedback routes (skipping): {e}")

    try:
        from api.routes.feedback_analytics_routes import router as feedback_analytics_router

        app.include_router(feedback_analytics_router, tags=["feedback-analytics"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load feedback analytics routes (skipping): {e}")

    # Feedback Phase 2: Promotions & Batch Operations
    try:
        from api.routes.feedback_phase2_routes import router as feedback_phase2_router

        app.include_router(feedback_phase2_router, tags=["feedback-phase2"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load feedback phase 2 routes (skipping): {e}")

    try:
        from api.routes.feedback_batch_routes import router as feedback_batch_router

        app.include_router(feedback_batch_router, tags=["feedback-batch"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load feedback batch routes (skipping): {e}")

    # Deep Linking System (Phase 2)
    try:
        from api.routes.deeplink_routes import router as deeplinks_router

        app.include_router(deeplinks_router, prefix="/api/v1/deeplinks", tags=["deeplinks"])
        logger.info("✅ Deep linking system enabled")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load deeplinks routes (skipping): {e}")

    try:
        from api.routes.workflow_template_routes import router as template_router

        app.include_router(
            template_router, prefix="/api/workflow-templates", tags=["workflow-templates"]
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load workflow template routes: {e}")

    # Distributed Debug System (Phase 1)
    try:
        from api.routes.debug_tenant_check import router as debug_tenant_check_router

        app.include_router(debug_tenant_check_router, tags=["debug"])
        logger.info("✅ Debug tenant check system enabled")
    except Exception as e:
        import traceback

        logger.error(f"CRITICAL: Failed to load debug tenant check routes: {e}")
        logger.error(traceback.format_exc())

    try:
        from api.routes.notification_settings_routes import router as notification_router

        app.include_router(
            notification_router, prefix="/api/notification-settings", tags=["notification-settings"]
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load notification settings routes: {e}")

    # Notification Service Routes
    try:
        from api.routes.notification_routes import router as notification_service_router

        app.include_router(
            notification_service_router, prefix="/api/v1/notifications", tags=["Notifications"]
        )
        app.include_router(
            notification_service_router, prefix="/api/notifications", tags=["Notifications"]
        )
        logger.info("✓ Notification Service Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load notification service routes: {e}")

    try:
        from api.routes.analytics_routes import router as analytics_router

        app.include_router(analytics_router, prefix="", tags=["Workflows"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load workflow analytics routes: {e}")

    # New Analytics Engine (Upstream Sync)
    try:
        from analytics.routes import router as analytics_engine_router

        app.include_router(
            analytics_engine_router, prefix="/api/v1/analytics", tags=["Analytics Engine"]
        )
        logger.info("✓ Analytics Engine Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Analytics Engine routes: {e}", exc_info=True)

    # Workflow Import/Export Routes
    try:
        from api.routes.workflow_io_routes import router as workflow_io_router

        app.include_router(workflow_io_router, tags=["workflow-io"])
        logger.info("✓ Workflow Import/Export Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load workflow I/O routes: {e}")

    try:
        from api.routes.background_agent_routes import router as background_router

        app.include_router(
            background_router, prefix="/api/background-agents", tags=["background-agents"]
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load background agent routes: {e}")

    try:
        from api.routes.financial_ops_routes import router as financial_router

        app.include_router(financial_router, prefix="/api/financial", tags=["financial-ops"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load financial ops routes: {e}")

    try:
        from api.routes.intervention_routes import router as intervention_router

        app.include_router(intervention_router, prefix="/api/v1", tags=["Governance"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load intervention routes: {e}")

    try:
        from api.routes.admin.governance_routes import router as admin_governance_router

        app.include_router(admin_governance_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Admin Governance routes: {e}", exc_info=True)

    # Governance Verification Routes (Phase 169-03)
    try:
        from api.routes.admin.governance_verification_routes import (
            router as governance_verification_router,
        )

        app.include_router(governance_verification_router)
        logger.info("✓ Governance Verification Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Governance Verification routes: {e}")

    # Governance Manual Fact Entry Routes (Phase 167-05)
    try:
        from api.routes.governance_routes import router as governance_manual_router

        app.include_router(governance_manual_router, prefix="/api", tags=["Governance"])
        logger.info("✓ Governance Manual Fact Entry Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Governance Manual Fact Entry routes: {e}")

    # Queue Monitoring Routes
    try:
        from api.routes.queue_monitoring_routes import router as queue_monitoring_router

        app.include_router(queue_monitoring_router, tags=["queue"])
        logger.info("✓ Queue Monitoring Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load queue monitoring routes: {e}")

    try:
        from api.routes.evolution_routes import router as evolution_router

        app.include_router(evolution_router, prefix="/api/evolution", tags=["Evolution"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load evolution routes: {e}")

    # Canvas Skill Integration
    try:
        from api.routes.canvas_skill_routes import router as canvas_skill_router

        app.include_router(canvas_skill_router, prefix="/api/v1", tags=["Canvas-Skill Integration"])
        logger.info("✓ Canvas Skill Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load canvas skill routes: {e}")

    try:
        from api.routes.admin.system_health_routes import router as system_health_router

        app.include_router(system_health_router)
        logger.info("✓ Admin System Health Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load system health routes: {e}")
    except Exception as e:
        logger.error(f"Error loading system health routes: {e}")

    try:
        from api.routes.admin.business_facts_routes import router as business_facts_router

        app.include_router(business_facts_router)
        logger.info("✓ Business Facts Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Business Facts routes: {e}")
    except Exception as e:
        logger.error(f"Error loading Business Facts routes: {e}")

    try:
        from api.routes.admin.paused_tasks_routes import router as paused_tasks_router
        from api.routes.admin.paused_tasks_routes import scheduler_router

        app.include_router(paused_tasks_router)
        app.include_router(scheduler_router)
        logger.info("✓ Paused Tasks Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Paused Tasks routes: {e}")
    except Exception as e:
        logger.error(f"Error loading Paused Tasks routes: {e}")

    try:
        from api.routes.admin.migration_routes import router as migration_router

        app.include_router(migration_router)
        logger.info("✓ Migration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Migration routes: {e}")
    except Exception as e:
        logger.error(f"Error loading Migration routes: {e}")

    try:
        from api.routes.embedding_routes import router as embedding_router

        app.include_router(embedding_router)
        logger.info("✓ Embedding Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Embedding routes: {e}")
    except Exception as e:
        logger.error(f"Error loading Embedding routes: {e}")

    try:
        from api.routes.ai_accounting_routes import router as ai_accounting_router

        app.include_router(
            ai_accounting_router, prefix="/api/v1/accounting", tags=["ai-accounting"]
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load AI accounting routes: {e}", exc_info=True)

    try:
        from api.routes.reconciliation_routes import router as reconciliation_router

        app.include_router(
            reconciliation_router, prefix="/api/v1/reconciliation", tags=["reconciliation"]
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load reconciliation routes: {e}")

    try:
        from api.routes.apar_routes import router as apar_router

        app.include_router(apar_router, prefix="/api/v1/apar", tags=["ap-ar"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load AP/AR routes: {e}", exc_info=True)

    try:
        from api.routes.graphrag_routes import router as graphrag_router

        app.include_router(graphrag_router, prefix="/api/graphrag", tags=["graphrag"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load GraphRAG routes: {e}")

    try:
        from api.routes.project_routes import router as projects_router

        app.include_router(projects_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Project routes: {e}")

    try:
        from api.routes.intelligence_routes import router as intelligence_router

        app.include_router(intelligence_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Intelligence routes: {e}")

    try:
        from api.routes.tenant_routes import router as tenant_router

        # Double-mount tenant_router at /api/tenant and /api/v1/tenant
        # to ensure compatibility with all frontend/middleware paths
        app.include_router(tenant_router, prefix="/api/tenant", tags=["Tenant Management"])
        app.include_router(tenant_router, prefix="/api/v1/tenant", tags=["Tenant Management"])
        app.include_router(tenant_ownership_router)

        logger.info("✓ Tenant Management Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load tenant routes: {e}")

    try:
        from api.routes.federation_routes import router as federation_router

        app.include_router(federation_router, prefix="/api")
        logger.info("✓ Federation Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Federation routes: {e}")

    try:
        from sales.routes import router as sales_router

        app.include_router(sales_router)
        from sales.deal_ingestion_routes import router as deal_ingestion_router

        app.include_router(deal_ingestion_router)

        from api.routes.marketing_routes import router as marketing_router

        app.include_router(
            marketing_router, prefix="/api/marketing", tags=["Marketing Intelligence"]
        )

        logger.info("✓ Sales & Marketing Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load business intelligence routes: {e}")

    try:
        from api.routes.workflow_routes import router as workflow_router

        app.include_router(workflow_router, prefix="/api/v1", tags=["Workflows"])
    except (ImportError, TypeError) as e:
        logger.error(f"Failed to load Core Workflow routes: {e}")

    try:
        from api.routes.skill_routes import router as skill_router

        app.include_router(skill_router)
        logger.info("✓ Skill Management & Execution Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load skill routes: {e}")

    try:
        from api.admin_evolution_routes import router as admin_evolution_router
        from api.routes.admin.skill_routes import router as admin_skill_router

        app.include_router(admin_skill_router)
        app.include_router(admin_evolution_router)
        logger.info("✓ Admin Skill & Evolution Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Admin Skill/Evolution routes: {e}", exc_info=True)

    # 3. Workflow UI (Visual Automations)
    # Eagerly load this to ensure 404s don't happen silently
    try:
        # Use consolidated path for visual automations
        from api.routes.workflow_ui_routes import router as workflow_ui_router

        app.include_router(workflow_ui_router, prefix="/api/v1/workflow-ui", tags=["Workflow UI"])
        logger.info("✓ Workflow UI Endpoints Loaded")
    except Exception as e:
        logger.error(f"CRITICAL: Workflow UI endpoints failed to load: {e}")
        # raise e # Uncomment to crash on startup if strict

    # 3b. AI Workflow Endpoints (Real NLU)
    try:
        from api.routes.enhanced_ai_workflow_routes import router as ai_router

        app.include_router(ai_router)

        from api.routes.ai_workflow_routes import router as ai_workflow_simple_router

        app.include_router(ai_workflow_simple_router)

        try:
            from api.routes.test_deployed_routes import main as test_main

            # test_deployed_routes is a script, not a router.
            # If it was intended to be a router, it needs a 'router' object.
        except (ImportError, TypeError) as e:
            logger.warning(f"Test deployed routes not found: {e}")

        from api.routes.advanced_workflow_routes import router as advanced_workflow_router

        app.include_router(advanced_workflow_router)

        from api.routes.case_studies_routes import router as case_studies_router

        app.include_router(case_studies_router)

        from api.routes.evidence_collection_routes import router as evidence_router

        app.include_router(evidence_router)

        from api.routes.enterprise_security_routes import router as security_router

        app.include_router(security_router, prefix="/api/v1/security", tags=["Enterprise Security"])

        from api.routes.team_messaging_routes import router as messaging_router

        app.include_router(messaging_router)

        from api.messaging_oauth_routes import router as messaging_oauth_router

        app.include_router(messaging_oauth_router)
        logger.info("✓ Messaging OAuth (BYOK) Routes Loaded")

        from api.routes.integrations.salesforce_enhanced_routes import router as sf_enhanced_router

        app.include_router(sf_enhanced_router)

        from api.routes.integrations.enterprise_integration_routes import router as ent_router

        app.include_router(ent_router)

        # Outlook and Gmail are now handled via the dynamic registry above
        # from api.routes.integrations.outlook_enhanced_routes import router as outlook_enh_router
        # app.include_router(outlook_enh_router, prefix="/api/v1/integrations/outlook")

        # Legacy messaging routes replaced by batch 3 standardized routes

        from api.routes.integrations.shopify_webhook_routes import router as shopify_wh_router

        app.include_router(shopify_wh_router)

        from api.routes.integrations.atom_communication_memory_webhook_routes import (
            atom_memory_webhooks_router,
        )

        app.include_router(
            atom_memory_webhooks_router,
            prefix="/api/memory/webhooks",
            tags=["Communication Memory Webhooks"],
        )

        from api.routes.integrations.atom_communication_memory_ingestion_routes import (
            communication_ingestion_router,
        )

        app.include_router(communication_ingestion_router)

        from api.routes.integrations.razorpay_routes import razorpay_router

        app.include_router(razorpay_router, prefix="/api/v1/integrations/razorpay")

        from api.routes.integrations.onedrive_routes import onedrive_router

        app.include_router(onedrive_router, prefix="/api/v1/integrations/onedrive")

        from api.routes.integrations.box_routes import box_router

        app.include_router(box_router, prefix="/api/v1/integrations/box", tags=["Box"])

        from api.routes.integrations.google_drive_routes import google_drive_router

        app.include_router(
            google_drive_router, prefix="/api/v1/integrations/google-drive", tags=["Google Drive"]
        )

        from api.routes.integrations.asana_routes import router as asana_router

        app.include_router(asana_router, prefix="/api/v1/integrations/asana")

        from api.routes.integrations.slack_routes import router as slack_router

        app.include_router(slack_router, prefix="/api/v1/integrations/slack")

        from api.routes.integrations.teams_routes import router as teams_router

        app.include_router(teams_router, prefix="/api/v1/integrations/teams")

        from api.routes.integrations.telegram_routes import router as telegram_router

        app.include_router(telegram_router, prefix="/api/v1/integrations/telegram")

        # Legacy WhatsApp router removed - Consolidated into hardened router below

        from api.routes.integrations.zendesk_routes import router as zendesk_router

        app.include_router(zendesk_router, prefix="/api/v1/integrations/zendesk")

        from api.routes.integrations.github_routes import router as github_router

        app.include_router(github_router, prefix="/api/v1/integrations/github")

        from api.routes.integrations.gmail_routes import router as gmail_router

        app.include_router(gmail_router, prefix="/api/v1/integrations/gmail")

        from api.routes.integrations.salesforce_routes import router as salesforce_router

        app.include_router(salesforce_router, prefix="/api/v1/integrations/salesforce")

        from api.routes.integrations.segment_routes import router as segment_router

        app.include_router(segment_router, prefix="/api/v1/integrations/segment")

        from api.routes.integrations.discord_routes import router as discord_router

        app.include_router(discord_router, prefix="/api/v1/integrations/discord")

        from api.routes.integrations.trello_routes import router as trello_router

        app.include_router(trello_router, prefix="/api/v1/integrations/trello")

        from api.routes.integrations.hubspot_routes import router as hubspot_router

        app.include_router(hubspot_router, prefix="/api/v1/integrations/hubspot")

        # Zoho Suite (Standardized)
        from api.routes.integrations.zoho_workdrive_routes import router as zoho_router

        app.include_router(zoho_router, prefix="/api/v1/integrations/zoho-workdrive")

        from api.routes.integrations.zoho_crm_routes import router as zoho_crm_router

        app.include_router(zoho_crm_router, prefix="/api/v1/integrations/zoho-crm")

        from api.routes.integrations.zoho_books_routes import router as zoho_books_router

        app.include_router(zoho_books_router, prefix="/api/v1/integrations/zoho-books")

        from api.routes.integrations.zoho_inventory_routes import router as zoho_inventory_router

        app.include_router(zoho_inventory_router, prefix="/api/v1/integrations/zoho-inventory")

        from api.routes.integrations.zoho_projects_routes import router as zoho_projects_router

        app.include_router(zoho_projects_router, prefix="/api/v1/integrations/zoho-projects")

        from api.routes.integrations.zoho_mail_routes import router as zoho_mail_router

        app.include_router(zoho_mail_router, prefix="/api/v1/integrations/zoho-mail")

        # HR Integrations
        from api.routes.integrations.sagehr_routes import sagehr_router

        app.include_router(sagehr_router, prefix="/api/v1/integrations/sagehr")

        # Batch 2 Integrations
        try:
            from api.routes.integrations.airtable_routes import router as airtable_router

            app.include_router(
                airtable_router, prefix="/api/v1/integrations/airtable", tags=["Airtable"]
            )

            from api.routes.integrations.notion_routes import router as notion_router

            app.include_router(notion_router, prefix="/api/v1/integrations/notion", tags=["Notion"])

            from api.routes.integrations.dropbox_routes import router as dropbox_router

            app.include_router(
                dropbox_router, prefix="/api/v1/integrations/dropbox", tags=["Dropbox"]
            )

            from api.routes.integrations.jira_routes import router as jira_router

            app.include_router(jira_router, prefix="/api/v1/integrations/jira", tags=["Jira"])

            from api.routes.integrations.linear_routes import router as linear_router

            app.include_router(linear_router, prefix="/api/v1/integrations/linear", tags=["Linear"])

            from api.routes.integrations.stripe_routes import router as stripe_router

            app.include_router(stripe_router, prefix="/api/v1/integrations/stripe", tags=["Stripe"])

            from api.routes.integrations.shopify_routes import router as shopify_router

            app.include_router(
                shopify_router, prefix="/api/v1/integrations/shopify", tags=["Shopify"]
            )

            from api.routes.integrations.xero_routes import router as xero_router

            app.include_router(
                xero_router, prefix="/api/v1/integrations/xero", tags=["Xero Accounting"]
            )

            from api.routes.integrations.yodlee_routes import router as yodlee_router

            app.include_router(
                yodlee_router, prefix="/api/v1/integrations/yodlee", tags=["Yodlee Financial"]
            )

            from api.routes.integrations.calendly_routes import router as calendly_router

            app.include_router(
                calendly_router, prefix="/api/v1/integrations/calendly", tags=["Calendly"]
            )

            from api.routes.integrations.clickup_routes import router as clickup_router

            app.include_router(
                clickup_router, prefix="/api/v1/integrations/clickup", tags=["ClickUp"]
            )

            from api.routes.integrations.quickbooks_routes import router as quickbooks_router

            app.include_router(
                quickbooks_router, prefix="/api/v1/integrations/quickbooks", tags=["QuickBooks"]
            )

            from api.routes.integrations.plaid_routes import router as plaid_router

            app.include_router(plaid_router, prefix="/api/v1/integrations/plaid", tags=["Plaid"])

            from api.routes.integrations.twilio_routes import router as twilio_router

            app.include_router(twilio_router, prefix="/api/v1/integrations/twilio", tags=["Twilio"])

            from api.routes.integrations.zoom_routes import router as zoom_router

            app.include_router(zoom_router, prefix="/api/v1/integrations/zoom", tags=["Zoom"])

            from api.routes.integrations.azure_devops_routes import router as azure_devops_router

            app.include_router(
                azure_devops_router,
                prefix="/api/v1/integrations/azure-devops",
                tags=["Azure DevOps"],
            )

            from api.routes.integrations.spotify_routes import router as spotify_router

            app.include_router(
                spotify_router, prefix="/api/v1/integrations/spotify", tags=["Spotify"]
            )

            logger.info("✓ Batch 2 Standardized Integrations Loaded")
        except (ImportError, TypeError) as e:
            logger.warning(f"Batch 2 integration endpoints not found: {e}")

        # 3b. Standardized Webhooks (Phase 12)
        try:
            logger.info("Loading Slack webhooks...")
            from api.routes.webhooks.slack_webhooks import router as slack_webhook_router

            app.include_router(slack_webhook_router, prefix="/api/v1/webhooks")
            logger.info("✓ Slack webhooks loaded")

            # WhatsApp webhooks are consolidated in the hardened flow section below
            pass

            logger.info("Loading Shopify webhooks...")
            from api.routes.webhooks.shopify_webhooks import router as shopify_webhook_router

            app.include_router(shopify_webhook_router, prefix="/api/v1/webhooks")
            logger.info("✓ Shopify webhooks loaded")

            logger.info("Loading Twilio webhooks...")
            from api.routes.webhooks.twilio_webhooks import router as twilio_webhook_router

            app.include_router(twilio_webhook_router, prefix="/api/v1/webhooks")
            logger.info("✓ Twilio webhooks loaded")

            logger.info("✓ Standardized Webhook Endpoints Loaded")
        except (ImportError, TypeError) as e:
            logger.warning(f"Webhook standardized endpoints not found: {e}", exc_info=True)

    except (ImportError, TypeError) as e:
        logger.warning(f"Standardized integration endpoints not found: {e}")

    # 4. Auth Routes (Standard Login)
    try:
        from api.routes.auth_routes import router as auth_router

        app.include_router(auth_router)  # Already has prefix="/api/auth"
    except (ImportError, TypeError) as e:
        logger.warning(f"Auth endpoints not found, skipping: {e}")

    try:
        from api.routes.admin.user_management_routes import router as admin_user_management_router
        from api.routes.admin_routes import router as admin_router

        app.include_router(admin_router)
        app.include_router(admin_user_management_router)
        logger.info("✓ Admin Routes Loaded")
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to load Admin Routes: {e}", exc_info=True)
        # We want to see this error!

    try:
        # 4a. 2FA Routes
        from api.routes.auth_2fa_routes import router as auth_2fa_router

        app.include_router(auth_2fa_router)  # Already has prefix="/api/auth/2fa"
        logger.info("✓ 2FA Routes Loaded")
    except (ImportError, TypeError):
        logger.warning("2FA routes not found, skipping.")

    # 4b. Onboarding Routes
    try:
        from api.routes.onboarding_routes import router as onboarding_router

        app.include_router(onboarding_router, prefix="/api/onboarding", tags=["Onboarding"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Onboarding routes not found: {e}")

    # 4b-notif. Notifications Routes (P2.2 — in-app notification center)
    try:
        from api.notifications_routes import router as notifications_router

        app.include_router(notifications_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Notifications routes not found: {e}")

    # 4b-dash. Dashboard feed (P3.2 — activity feed aggregate endpoint)
    try:
        from api.dashboard_routes import router as dashboard_router

        app.include_router(dashboard_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Dashboard routes not found: {e}")

    # 4c. Reasoning & Feedback Routes
    try:
        from api.routes.reasoning_routes import router as reasoning_router

        app.include_router(reasoning_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Reasoning routes not found: {e}")

    # 5. OAuth (Critical for login)
    try:
        from api.routes.platform_oauth_routes import router as platform_oauth_router

        app.include_router(platform_oauth_router, prefix="/api/v1/auth", tags=["Auth"])
    except (ImportError, TypeError):
        logger.warning("OAuth routes not found, skipping.")

    # 4. WebSockets (Real-time features)
    try:
        from api.routes.websocket_routes import router as ws_router

        app.include_router(ws_router, tags=["WebSockets"])
    except (ImportError, TypeError):
        logger.warning("WebSocket routes not found, skipping.")

    # 6. MCP Routes (Web Search & Web Access for Agents)
    try:
        from api.routes.integrations.mcp_routes import router as mcp_router

        app.include_router(mcp_router, tags=["MCP"])
        logger.info("✓ MCP Routes Loaded")

    except (ImportError, TypeError) as e:
        logger.warning(f"MCP/Zoho routes not found: {e}")

    # 7. Supervision System Routes (NEW)
    try:
        from api.routes.availability_routes import router as availability_router

        app.include_router(availability_router)
        logger.info("✓ Availability Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Availability routes: {e}", exc_info=True)

    try:
        from api.routes.proposal_routes import router as proposal_router

        app.include_router(proposal_router)
        logger.info("✓ Proposal Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Proposal routes: {e}")

    try:
        from api.routes.supervision_learning_routes import router as supervision_learning_router

        app.include_router(supervision_learning_router)
        logger.info("✓ Supervision-Learning Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Supervision-Learning routes: {e}")

    try:
        from api.routes.integrations.integrations_catalog_routes import router as catalog_router

        app.include_router(catalog_router)
        logger.info("✓ Integrations Catalog Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Integrations catalog routes not found: {e}")

    try:
        from api.routes.dynamic_options_routes import router as dynamic_options_router

        app.include_router(dynamic_options_router)
        logger.info("✓ Dynamic Options Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Dynamic options routes not found: {e}")

    # Webhook Routes (New Native Webhooks)
    try:
        from api.routes.webhook_routes import router as webhook_router

        app.include_router(webhook_router)
        logger.info("✓ Webhook Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Webhook routes not found: {e}")

    # Consolidated Stripe Webhook Routes
    try:
        from api.routes.stripe_webhook_routes import router as stripe_webhook_router

        app.include_router(stripe_webhook_router, prefix="/api")

        # Legacy webhook URL support (adds backward compatibility for /api/billing/webhook)
        from api.routes.stripe_webhook_routes import stripe_webhook

        app.add_api_route(
            "/api/billing/webhook",
            stripe_webhook,
            methods=["POST"],
            tags=["Stripe Webhooks (Legacy)"],
        )
        logger.info("✓ Consolidated Stripe Webhook Routes Loaded (with legacy alias)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Consolidated Stripe webhook routes not found: {e}")

    try:
        from api.routes.integrations.universal.routes import router as universal_auth_router

        app.include_router(universal_auth_router)
        logger.info("✓ Universal Auth Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Universal auth routes not found: {e}")

    try:
        from api.routes.meta_compliance_routes import router as meta_compliance_router

        app.include_router(meta_compliance_router)
        logger.info("✓ Meta Compliance Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Meta compliance routes not found: {e}")

    # WhatsApp Handlers (Consolidated Hardened Flow)
    try:
        from api.routes.integrations.whatsapp.router import router as whatsapp_oauth_router
        from api.routes.webhooks.whatsapp_webhooks import router as whatsapp_webhook_router

        app.include_router(
            whatsapp_webhook_router, prefix="/api/v1/webhooks", tags=["whatsapp-webhooks"]
        )
        app.include_router(whatsapp_oauth_router, prefix="/api/v1/integrations/whatsapp")

        logger.info("✓ Consolidated Hardened WhatsApp Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Hardened WhatsApp routes not found: {e}")

    try:
        from api.routes.integrations.bridge.external_integration_routes import router as ext_router

        app.include_router(ext_router)
        logger.info("✓ External Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"External integration bridge routes not found: {e}")

    # Register Connection routes
    try:
        from api.routes.connection_routes import router as conn_router

        app.include_router(conn_router)
        logger.info("✓ Connection Management Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Connection routes not found: {e}")

    # 7. Chat Orchestrator Routes (Critical for chat functionality)
    # The chat router lives at integrations/chat_routes.py (prefix /api/chat
    # already set on the router itself). The old import path
    # (api.routes.integrations.chat_routes) didn't exist and silently failed,
    # leaving /api/chat/feedback and /api/chat/routing-stats unmounted.
    try:
        from integrations.chat_routes import router as chat_router

        app.include_router(chat_router, tags=["Chat"])
        logger.info("✓ Chat Routes Loaded (incl. /api/chat/feedback, /api/chat/routing-stats)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Chat routes not found: {e}")

    # 8. Agent Governance Routes
    try:
        from api.routes.agent_governance_routes import router as gov_router

        app.include_router(gov_router)
        logger.info("✓ Agent Governance Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Agent Governance routes not found: {e}")

    # 8b. HITL Approval Routes (Phase 256-06)
    try:
        from api.routes.hitl_routes import router as hitl_router

        app.include_router(hitl_router)
        logger.info("✓ HITL Approval Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"HITL approval routes not found: {e}")

    # 8c. AWS SES Integration Routes
    try:
        from api.routes.integrations.aws_ses_routes import router as aws_ses_router

        app.include_router(aws_ses_router)
        logger.info("✓ AWS SES Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"AWS SES integration routes not found: {e}")

    # 8b. Graduation Exam Routes (Episodic Memory & Graduation)
    try:
        from api.routes.graduation_routes import router as graduation_router

        app.include_router(graduation_router)
        logger.info("✓ Graduation Exam Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Graduation exam routes not found: {e}")

    # 8c. Protection & Security Routes
    try:
        from api.routes.protection_routes import router as protection_router

        app.include_router(protection_router)
        logger.info("✓ Protection API Routes Loaded (Skill Scanner)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Protection API routes not found: {e}")

    # 8d. User Preferences & Multimodal Chat
    try:
        from api.routes.user_preference_routes import router as user_pref_router

        app.include_router(user_pref_router, prefix="/api/v1/preferences")
        logger.info("✓ User Preference Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"User preference routes failed to load: {e}")

    try:
        from api.routes.multimodal_chat_routes import router as multimodal_router

        app.include_router(multimodal_router, prefix="/api/v1/chat/multimodal")
        logger.info("✓ Multimodal Chat Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Multimodal chat routes failed to load: {e}")
    except (ImportError, TypeError) as e:
        logger.warning(f"Protection API routes not found: {e}")

    # 8b. Universal Canvas Routes (Terminal, Browser, Desktop Automation)
    try:
        from api.routes.canvas_terminal_routes import router as canvas_terminal_router

        app.include_router(canvas_terminal_router)
        logger.info("✓ Canvas Terminal Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas terminal routes not found: {e}")

    try:
        from api.routes.canvas_browser_routes import router as canvas_browser_router

        app.include_router(canvas_browser_router)
        logger.info("✓ Canvas Browser Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas browser routes not found: {e}")

    try:
        from api.routes.canvas_action_routes import router as canvas_action_router

        app.include_router(canvas_action_router)
        logger.info("✓ Canvas Action Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas action routes not found: {e}")

    try:
        from api.routes.canvas_context_routes import router as canvas_context_router

        app.include_router(canvas_context_router)
        logger.info("✓ Canvas Context Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas context routes not found: {e}")

    try:
        from api.routes.canvas_recording_routes import router as canvas_recording_router

        app.include_router(canvas_recording_router)
        logger.info("✓ Canvas Recording Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas recording routes not found: {e}")

    # --- PORTED FEATURES ---
    try:
        from api.routes.canvas_routes import router as canvas_router

        app.include_router(canvas_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas routes not found: {e}")

    try:
        from api.routes.canvas_collaboration_routes import router as canvas_collab_router

        app.include_router(canvas_collab_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas collab routes not found: {e}")

    try:
        from api.routes.collaboration_routes import router as collaboration_router

        app.include_router(collaboration_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Collaboration routes not found: {e}")

    try:
        from api.routes.comment_routes import router as comment_router

        app.include_router(comment_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Comment routes not found: {e}")

    try:
        from api.routes.canvas_coding_routes import router as canvas_coding_router

        app.include_router(canvas_coding_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas coding routes not found: {e}")

    try:
        from api.routes.canvas_docs_routes import router as canvas_docs_router

        app.include_router(canvas_docs_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas docs routes not found: {e}")

    try:
        from api.routes.canvas_sheets_routes import router as canvas_sheets_router

        app.include_router(canvas_sheets_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas sheets routes not found: {e}")

    try:
        from api.routes.agent_control_routes import router as agent_control_router

        app.include_router(agent_control_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Agent control routes not found: {e}")

    try:
        from api.routes.analytics_dashboard_routes import router as analytics_dashboard_router

        # Backward compatibility for analytics/dashboard if moved
        app.include_router(analytics_dashboard_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Analytics dashboard routes not found: {e}")

    try:
        from api.routes.research_analytics_routes import router as research_analytics_router

        # Research analytics dashboard endpoints
        app.include_router(
            research_analytics_router, prefix="/api/research/analytics", tags=["research-analytics"]
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Research analytics routes not found: {e}")

    try:
        # Usage analytics routes already have prefix in router definition
        app.include_router(usage_analytics_router, tags=["research-usage"])
        logger.info("✓ Usage Analytics Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Usage analytics routes not found: {e}")

    try:
        from api.routes.dashboard_data_routes import router as dashboard_router

        app.include_router(dashboard_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Dashboard data routes not found: {e}")

    try:
        from api.routes.agent_guidance_routes import router as agent_guidance_router

        app.include_router(agent_guidance_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Agent guidance routes not found: {e}")

    try:
        from api.routes.health_monitoring_routes import router as health_monitoring_router

        app.include_router(health_monitoring_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Health monitoring routes not found: {e}")

    try:
        from api.routes.health_routes import router as health_router

        app.include_router(health_router)
        logger.info("✓ Health Monitoring Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Health monitoring routes not found: {e}")

    try:
        from api.routes.project_health_routes import router as project_health_router

        app.include_router(project_health_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Project health routes not found: {e}")

    logger.info("✓ Ported Features (Canvas/Agent) Processing Complete")

    # 8b. Governance Analytics & Remediation (Phase 10)
    try:
        from api.routes.governance_analytics_routes import router as gov_analytics_router

        app.include_router(gov_analytics_router)
        logger.info("✓ Governance Analytics & Remediation Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Governance Analytics routes not found: {e}")

    # 9. Memory/Document Routes
    try:
        from api.routes.memory_routes import router as memory_router

        app.include_router(memory_router, prefix="/api/v1/memory", tags=["Memory"])
        logger.info("✓ Memory Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Memory routes not found: {e}")

    # 9b. Memory Management Routes (Consolidation, Archival, Recovery)
    try:
        from api.routes.memory_management_routes import router as memory_management_router

        app.include_router(memory_management_router)
        logger.info("✓ Memory Management Routes Loaded (Consolidation, Archival, Recovery)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Memory Management routes not found: {e}")

    # 9c. Memory Add-on Routes (Stripe Billing)
    try:
        from api.routes.memory_addon_routes import router as memory_addon_router

        app.include_router(memory_addon_router, prefix="/api/v1", tags=["Billing", "Memory"])
        logger.info("✓ Memory Add-on Routes Loaded (Stripe Billing)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Memory Add-on routes not found: {e}")

    # 10. Voice Routes
    try:
        # Voice, Documents, Formulas are loaded via ESSENTIAL_INTEGRATIONS registry
        pass
    except (ImportError, TypeError) as e:
        logger.warning(f"Voice routes not found: {e}")

    # 11. Document Ingestion Routes
    try:
        # Ingestion routes

        from api.routes.document_ingestion_routes import router as doc_ingest_router

        app.include_router(doc_ingest_router)  # Prefix defined in router

        from api.routes.data_ingestion_routes import router as data_ingest_router

        app.include_router(data_ingest_router)  # Prefix defined in router

        logger.info("✓ Document & Data Ingestion Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Ingestion routes not found: {e}")

    # 11b. Document Hub Routes
    try:
        from api.routes.document_hub_routes import router as document_hub_router

        app.include_router(document_hub_router)
        logger.info("✓ Document Hub Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Document Hub routes not found: {e}")

    # 12. Formula Routes
    # Formulas loaded via ESSENTIAL_INTEGRATIONS

    # 13. Test Routes (Internal only, for E2E)
    try:
        from api.routes.backfill_routes import router as backfill_router
        from api.routes.error_test_routes import router as error_test_router
        from api.routes.test_auth_routes import router as test_auth_router
        from api.routes.test_cleanup_routes import router as test_cleanup_router

        try:
            from api.routes.test_social_routes import router as test_social_router

            app.include_router(test_social_router, tags=["Test-Social"])
        except (ImportError, TypeError):
            logger.info("  ! Test social routes not found, skipping registration")

        app.include_router(test_auth_router, prefix="/api/test", tags=["Test-Auth"])
        app.include_router(test_cleanup_router, prefix="/api/test/cleanup", tags=["Test-Cleanup"])
        app.include_router(error_test_router, tags=["Test-Errors"])
        app.include_router(backfill_router, prefix="/api/admin", tags=["Admin-Backfill"])
        logger.info("✓ Test Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.error(f"Test routes NOT available: {e}", exc_info=True)

    # 13. AI Workflows Routes (NLU Parse, Completion)
    try:
        from api.routes.ai_workflows_routes import router as ai_wf_router

        app.include_router(ai_wf_router, tags=["AI Workflows"])
        logger.info("✓ AI Workflows Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"AI Workflows routes not found: {e}")

    # 14. Background Agent Routes
    try:
        from api.routes.background_agent_routes import router as bg_agent_router

        app.include_router(bg_agent_router, tags=["Background Agents"])
        logger.info("✓ Background Agent Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Background Agent routes not found: {e}")

    # 15. Integration Data Routes (production implementations)
    try:
        # PDF Processing
        from api.routes.integrations.pdf_processing.pdf_ocr_routes import router as pdf_ocr_router

        app.include_router(pdf_ocr_router)
        from api.routes.integrations.pdf_processing.pdf_memory_routes import (
            router as pdf_memory_router,
        )

        app.include_router(pdf_memory_router)
        from api.routes.integrations.integration_data_routes import (
            router as integration_data_router,
        )

        app.include_router(integration_data_router, tags=["Integration Data"])
        logger.info("✓ Integration Data Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Integration Data Routes not found: {e}")

    # 15.1. Integration Health Stubs
    try:
        from api.routes.integrations.integration_health_routes import router as health_stubs_router

        app.include_router(health_stubs_router, tags=["Integration Health"])

        from api.routes.service_health_routes import router as service_health_router

        app.include_router(service_health_router, tags=["Service Health"])

        logger.info("✓ Integration & Service Health Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Integration Health routes not found: {e}")

    # 15.2. Historical Sync Routes
    try:
        from api.routes.integrations.historical_sync_routes import router as historical_sync_router

        app.include_router(historical_sync_router, tags=["Historical Sync"])
        logger.info("✓ Historical Sync Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Historical Sync Routes not found: {e}")

    # 15.3. Worker Routes (Background job processing health checks)
    try:
        from api.routes.worker_routes import router as worker_router

        app.include_router(worker_router, tags=["Workers"])
        logger.info("✓ Worker Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Worker Routes not found: {e}")

    # 15.2 Collaborative Canvas Routes (Component marketplace, multi-agent coordination)
    try:
        from api.routes.component_routes import router as component_router

        app.include_router(component_router, prefix="/api/v1", tags=["Component Marketplace"])
        logger.info("✓ Component Marketplace Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Component marketplace routes not found: {e}")

    try:
        from api.routes.agent_coordination_routes import router as agent_coordination_router

        app.include_router(agent_coordination_router, prefix="", tags=["Agent Coordination"])
        logger.info("✓ Agent Coordination Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Agent coordination routes not found: {e}")

    # Canvas Marketplace & Canvas-Skill Integration Routes
    try:
        from api.routes.canvas_marketplace_routes import router as canvas_marketplace_router

        app.include_router(
            canvas_marketplace_router, prefix="/api/canvas-marketplace", tags=["Canvas Marketplace"]
        )
        app.include_router(
            canvas_marketplace_router,
            prefix="/api/v1/canvas-marketplace",
            tags=["Canvas Marketplace"],
        )
        app.include_router(
            canvas_marketplace_router, prefix="/api/marketplace", tags=["Canvas Marketplace"]
        )
        logger.info("✓ Canvas Marketplace Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas marketplace routes not found: {e}")

    try:
        from api.routes.canvas_skill_routes import router as canvas_skill_router

        app.include_router(canvas_skill_router, tags=["Canvas Skills"])
        logger.info("✓ Canvas-Skill Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas skill integration routes not found: {e}")

    # OpenClaw Skill Integration Routes (Phase 42)
    try:
        from api.routes.openclaw_skill_routes import router as openclaw_skill_router

        app.include_router(openclaw_skill_router, tags=["OpenClaw Skills"])
        logger.info("✓ OpenClaw Skill Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"OpenClaw skill integration routes not found: {e}")

    # OpenClaw Scan Integration Routes (Phase 43)
    try:
        from api.routes.openclaw_scan_routes import router as openclaw_scan_router

        app.include_router(openclaw_scan_router, tags=["OpenClaw Scan"])
        logger.info("✓ OpenClaw Scan Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"OpenClaw scan integration routes not found: {e}")

    # OpenClaw Governance Integration Routes (Phase 45)
    try:
        from api.routes.openclaw_governance_routes import router as openclaw_governance_router

        app.include_router(openclaw_governance_router, tags=["OpenClaw Governance"])
        logger.info("✓ OpenClaw Governance Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"OpenClaw governance integration routes not found: {e}")

    # Skill Composition Routes (Phase 60)
    try:
        from api.routes.skill_composition_routes import router as skill_composition_router

        app.include_router(skill_composition_router, tags=["Skill Compositions"])
        logger.info("✓ Skill Composition Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Skill composition routes not found: {e}")

    # 15.3 Atom Agent Streaming Routes
    # NOTE: The real atom-agent endpoints live at core/atom_agent_endpoints.py
    # and are mounted via the lazy integration registry (lazy_integration_registry.py).
    # The old api/routes/atom_agent_routes.py re-export shim never existed and
    # always failed to import, logging a spurious warning on every startup.
    # Removed to avoid the noise; the lazy-registry path is the source of truth.

    # 16. Live Command Center APIs (Parallel Pipeline)
    try:
        from api.routes.integrations.atom_communication_live_routes import (
            router as comm_live_router,
        )
        from api.routes.integrations.atom_finance_live_routes import router as finance_live_router
        from api.routes.integrations.atom_projects_live_routes import router as projects_live_router
        from api.routes.integrations.atom_sales_live_routes import router as sales_live_router

        app.include_router(comm_live_router)
        app.include_router(sales_live_router)
        app.include_router(projects_live_router)
        app.include_router(finance_live_router)
        logger.info("✓ Live Command Center APIs Loaded (Comm, Sales, Projects, Finance)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Live Command Center APIs not found: {e}")

    # 17. External Scheduler Routes (Upstash QStash)
    try:
        from api.routes.scheduler_trigger_routes import router as scheduler_trigger_router

        app.include_router(scheduler_trigger_router, prefix="/api/scheduler", tags=["Scheduler"])
        logger.info("✓ Scheduler Routes Loaded (QStash Ready)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Scheduler routes not found: {e}")

    # 18. Desktop Bridge Routes (Cloud Brain to Local Hands)
    logger.debug("Attempting to import desktop_routes")
    try:
        from api.routes.desktop_routes import router as desktop_router

        logger.debug("Desktop routes imported, including router")
        app.include_router(desktop_router, prefix="/api/v1/desktop", tags=["Desktop Bridge"])
        logger.info("✓ Desktop Bridge Routes Loaded")
        logger.debug("Desktop routes successfully registered")
    except (ImportError, TypeError) as e:
        logger.debug(f"ImportError importing desktop routes: {e}")
        logger.warning(f"Desktop routes not found: {e}")
    except Exception as e:
        logger.debug(f"Unexpected error importing desktop routes: {e}")
        logger.error(f"Desktop routes failed: {e}")

    # 19. Satellite Routes (Local Node Link)
    try:
        from api.routes.satellite_routes import router as satellite_router

        app.include_router(satellite_router)
        logger.info("✓ Satellite Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Satellite routes not found: {e}")

    # 19b. Mobile Routes (Remote Control)
    try:
        from api.routes.mobile_routes import router as mobile_router

        app.include_router(mobile_router)
        logger.info("✓ Mobile Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Mobile routes not found: {e}")

    # 19c. Integration Canvas Routes
    try:
        from api.routes.integrations.integration_canvas_routes import (
            router as integration_canvas_router,
        )

        app.include_router(integration_canvas_router, prefix="/api/v1", tags=["Integration Canvas"])
        logger.info("✓ Integration Canvas Routes Loaded")
    except Exception as e:
        logger.warning(f"Integration Canvas routes failed to load: {e}")

    # 20. User Invitation Routes (Phase 23)
    try:
        from api.routes.invitation_routes import router as invitation_router

        app.include_router(invitation_router, prefix="/api/tenant", tags=["Tenant Management"])
        app.include_router(invitation_router, prefix="/api/v1/tenant", tags=["Tenant Management"])
        logger.info("✓ Invitation Routes Loaded")
    except Exception as e:
        logger.warning(f"Invitation routes failed to load: {e}")

    try:
        from api.routes.support_routes import router as support_router

        app.include_router(support_router)
        logger.info("✓ Support Ticketing Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Support routes not found: {e}")

    try:
        from api.routes.bug_triage_routes import router as bug_triage_router

        app.include_router(bug_triage_router)
        logger.info("✓ Bug Triage Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Bug triage routes not found: {e}")

    # 20c. Communication Hub Routes
    try:
        from api.routes.communication_hub_routes import router as comm_hub_router

        app.include_router(comm_hub_router)
        logger.info("✓ Communication Hub Routes Loaded")
        from api.routes.scim_routes import router as scim_api_router

        app.include_router(scim_api_router, prefix="/api/v1", tags=["SCIM"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Communication Hub routes not found: {e}")

    # 20e. Universal Communication Routes (New)
    try:
        from api.routes.communication_routes import router as universal_comm_router

        app.include_router(universal_comm_router)
        logger.info("✓ Universal Communication Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Universal Communication routes not found: {e}")

    # 20d. Document Hub Routes (Phase 39)
    try:
        from api.routes.document_hub_routes import router as doc_hub_router

        app.include_router(doc_hub_router)
        logger.info("✓ Document Hub Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Document Hub routes not found: {e}")

    # 20b. Admin Retention Routes (Phase 73)
    try:
        from api.routes.admin.retention_routes import router as retention_router

        app.include_router(retention_router)
        logger.info("✓ Admin Retention Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Admin retention routes not found: {e}")

    # 21. Billing Routes (Phase 25)
    try:
        from api.routes.billing_routes import router as billing_router

        app.include_router(billing_router)  # Prefix defined in router as /api/billing
        logger.info("✓ Billing Routes Loaded")
    except Exception as e:
        logger.warning(f"Billing routes failed to load: {e}")

    # 21a. Public Pricing Routes (reads Stripe env vars at runtime)
    try:
        from api.routes.public_pricing_routes import router as public_pricing_router

        app.include_router(public_pricing_router, tags=["Public"])
        logger.info("✓ Public Pricing Routes Loaded")
    except Exception as e:
        logger.warning(f"Public pricing routes failed to load: {e}")

    # 22. Social Media Routes (Week 2-3)
    try:
        from api.routes.social_media_routes import router as social_media_router

        app.include_router(
            social_media_router, prefix="/api/v1/social-media", tags=["Social Media"]
        )
        logger.info("✓ Social Media Routes Loaded")
    except Exception as e:
        logger.warning(f"Social media routes failed to load: {e}")
    except Exception as e:
        logger.warning(f"Public pricing routes failed to load: {e}")

    # 21b. Audit Routes (Phase 75)
    try:
        from api.routes.audit_routes import router as audit_api_router

        app.include_router(audit_api_router)
        from api.routes.admin.audit_routes import router as admin_audit_router

        app.include_router(admin_audit_router)
        logger.info("✓ Audit Log Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Audit routes not found: {e}")

    # 22. Shell Security Routes (Phase 40)
    try:
        from api.routes.shell_audit_routes import router as shell_audit_router
        from api.routes.shell_security_routes import router as shell_security_router

        app.include_router(shell_audit_router)
        app.include_router(shell_security_router)
        logger.info("✓ Shell Security Routes Loaded")
    except Exception as e:
        logger.warning(f"Shell security routes failed to load: {e}")

    # 23. Consolidated Core Routes (Phase 2)
    try:
        # These are already included above, removing duplicates to prevent conflicts
        # from api.routes.project_routes import router as project_routes_router
        from api.routes.intelligence_routes import router as intelligence_routes_router

        # from sales.routes import router as sales_routes_router
        from api.routes.marketing_routes import router as marketing_routes_router
        from api.routes.memory_routes import router as memory_routes_router
        from api.routes.skill_routes import router as skill_routes_router

        # app.include_router(project_routes_router)
        app.include_router(intelligence_routes_router)
        # app.include_router(sales_routes_router)
        app.include_router(marketing_routes_router)
        app.include_router(skill_routes_router)
        app.include_router(memory_routes_router)

        logger.info("✓ Consolidated Core Routes Loaded (Intelligence, Marketing, Skills, Memory)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Some consolidated core routes failed to load: {e}")

    # 24. BYOK API Routes (Phase 51)
    try:
        from api.routes.byok_api_routes import router as byok_router

        app.include_router(byok_router, prefix="/api/v1", tags=["BYOK"])
        logger.info("✓ BYOK API Routes Loaded")
    except Exception as e:
        logger.warning(f"BYOK API routes failed to load: {e}")

    # 25. SSO API Routes (Phase 76)
    try:
        from api.routes.sso_routes import router as sso_api_router

        app.include_router(sso_api_router, prefix="/api/v1", tags=["SSO"])
        logger.info("✓ SSO API Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"SSO routes not found: {e}")

    # 24. Feature Flag Routes (Phase 37)
    try:
        from api.routes.feature_flag_routes import router as feature_flag_router

        app.include_router(feature_flag_router)
        logger.info("✓ Feature Flag Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Feature flag routes not found: {e}")

    # 25. Sandbox Execution Routes (Phase 44)
    try:
        from api.routes.sandbox_execution_routes import router as sandbox_router

        app.include_router(sandbox_router)
        logger.info("✓ Sandbox Execution Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Sandbox execution routes failed to load: {e}")

    # 26. External API Routes (Phase 48)
    try:
        from api.routes.external_api_routes import router as external_api_router

        app.include_router(external_api_router)
        logger.info("✓ External API Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"External API routes failed to load: {e}")

    # 27. Entity Type Routes (Phase 171)
    try:
        from api.routes.entity_type_routes import router as entity_type_router

        app.include_router(entity_type_router)
        logger.info("✓ Entity Type Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Entity type routes failed to load: {e}")

    # 28. Entity Query Routes (Phase 194)
    try:
        from api.routes.entity_query_routes import router as entity_query_router

        app.include_router(entity_query_router)
        logger.info("✓ Entity Query Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Entity query routes failed to load: {e}")

    # 28.5. Entity Linking Routes (Phase 2: Automated Linking Agent)
    try:
        from api.routes.entity_linking_routes import router as entity_linking_router

        app.include_router(entity_linking_router)
        logger.info("✓ Entity Linking Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Entity linking routes failed to load: {e}")

    # 28.6. Ingestion CRUD Routes (Phases 1-4)
    try:
        from api.routes.ingestion_crud_routes import router as ingestion_crud_router

        app.include_router(ingestion_crud_router)
        logger.info("✓ Ingestion CRUD Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Ingestion CRUD routes failed to load: {e}")

    # 29. Entity Skill Routes (Phase 197)
    try:
        from api.routes.entity_skill_routes import router as entity_skill_router

        app.include_router(entity_skill_router)
        logger.info("✓ Entity Skill Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Entity skill routes failed to load: {e}")

    # 30. Agent Integration Routes (Phase 204)
    try:
        from api.routes.agent_integration_routes import router as agent_integration_router

        app.include_router(agent_integration_router)
        logger.info("✓ Agent Integration Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Entity skill routes failed to load: {e}")

    # 30. Meta Agent Routes (Phase 177)
    try:
        from api.routes.meta_agent_routes import router as meta_agent_router

        app.include_router(meta_agent_router)
        logger.info("✓ Meta Agent Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Meta agent routes failed to load: {e}")

    # 31. Admin Integration Catalog Routes (Phase 217)
    try:
        from api.routes.admin_integration_routes import router as admin_integration_router

        app.include_router(admin_integration_router)
        logger.info("✓ Admin Integration Catalog Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Admin integration catalog routes failed to load: {e}")

    # 32. Agent Capability Routes (Phase 222)
    try:
        from api.routes.agent_capability_routes import router as agent_capability_router

        app.include_router(
            agent_capability_router, prefix="/api/v1/agents", tags=["Agent Capabilities"]
        )
        logger.info("✓ Agent Capability Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Agent capability routes failed to load: {e}")

    # --- COMMERCIAL MARKETPLACE CONSOLIDATION (Phase 247) ---
    try:
        from api.agent_marketplace_routes import router as agent_mkt_router
        from api.routes.canvas_marketplace_routes import router as component_mkt_router
        from api.routes.domain_marketplace_routes import router as domain_mkt_router
        from api.routes.public_marketplace_routes import router as skill_mkt_router

        # Unified V1 Commercial Marketplace API (Standardized for satellites)
        # Using a clean prefix structure for the satellite client
        app.include_router(
            skill_mkt_router, prefix="/api/v1/marketplace", tags=["Marketplace (Commercial)"]
        )
        app.include_router(
            agent_mkt_router, prefix="/api/v1/marketplace/agents", tags=["Marketplace (Commercial)"]
        )
        app.include_router(
            domain_mkt_router,
            prefix="/api/v1/marketplace/domains",
            tags=["Marketplace (Commercial)"],
        )
        app.include_router(
            component_mkt_router,
            prefix="/api/v1/marketplace/components",
            tags=["Marketplace (Commercial)"],
        )

        logger.info("✅ Consolidated Commercial Marketplace APIs Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to consolidate marketplace routes: {e}")

    # 33. Domain Marketplace Routes (Phase 247)
    try:
        from api.routes.domain_marketplace_routes import router as domain_marketplace_router

        app.include_router(domain_marketplace_router)
        logger.info("✓ Domain Marketplace Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Domain marketplace routes failed to load: {e}")

    # 34. Agent-Domain Routes (Phase 247-11)
    try:
        from api.routes.agent_domain_routes import router as agent_domain_router

        app.include_router(agent_domain_router)
        logger.info("✓ Agent-Domain Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Agent-domain routes failed to load: {e}")

    # Agent Marketplace & Federation Routes
    try:
        from api.agent_marketplace_routes import router as agent_marketplace_router
        # NOTE: federation routes are loaded at line ~2110 via
        # api.routes.federation_routes (prefix="/api"), not here.
        app.include_router(agent_marketplace_router)
        logger.info("✓ Agent Marketplace Routes Loaded")
    except Exception as e:
        logger.warning(f"Agent Marketplace routes failed to load: {e}")

    # 35. Domain-Aware Graduation Routes (Phase 247-14)
    try:
        from api.routes.domain_aware_graduation_routes import router as domain_graduation_router

        app.include_router(domain_graduation_router)
        logger.info("✓ Domain-Aware Graduation Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Domain-aware graduation routes failed to load: {e}")

    # 36. Capability Matrix Routes (Phase 247-14)
    try:
        from api.routes.capability_matrix_routes import router as capability_matrix_router

        app.include_router(capability_matrix_router)
        logger.info("✓ Capability Matrix Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Capability matrix routes failed to load: {e}")

    # 37. Document Generation Routes (Phase 223)
    try:
        from api.routes.document_generation_routes import router as document_generation_router

        app.include_router(
            document_generation_router, prefix="/api/v1/documents", tags=["Document Generation"]
        )
        logger.info("✓ Document Generation Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Document generation routes failed to load: {e}")

    # 38. Learning & Adaptation Routes (Unified Learning System)
    try:
        from api.routes.learning_routes import router as learning_router

        app.include_router(learning_router)
        logger.info("✓ Learning & Adaptation Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Learning routes failed to load: {e}")

    logger.info("✓ Core Routes Loaded Successfully")

except (ImportError, TypeError) as e:
    logger.critical(f"CRITICAL: Core API routes failed to load: {e}")
    # In production, you might want to raise e here to stop a broken server

# ============================================================================
# MICROSOFT 365 ROUTES - Registered outside the Core Routes try block to ensure
# reliability. The Core Routes block may fail early due to fragile imports,
# silently skipping downstream registrations.
# ============================================================================
try:
    from api.routes.integrations.microsoft365_routes import router as microsoft365_router

    app.include_router(microsoft365_router, prefix="/api/v1/integrations/microsoft365")
    logger.info("✓ Microsoft 365 Routes Loaded (isolated)")
except Exception as e:
    logger.critical(f"MISSING ROUTE: Microsoft 365 integration failed to load: {e}", exc_info=True)

# ============================================================================
# 2. LAZY INTEGRATION ENDPOINTS (V2 ARCHITECTURE)
# Keeps the server fast by only loading plugins when needed
# ============================================================================


@app.get("/api/integrations")
async def list_integrations(current_user: User = Depends(get_current_user)):
    """List all available integrations and their status"""
    return {
        "total": len(get_integration_list()),
        "integrations": list(get_integration_list().keys()),
        "loaded": get_loaded_integrations(),
    }


@app.post("/api/integrations/{integration_name}/load")
async def load_integration_endpoint(
    integration_name: str,
    current_user: User = Depends(get_current_user),
    tenant_id: str | None = None,  # Optional if passed in header or body
    db: Session = Depends(get_db),
):
    def get_role_hierarchy(role: str) -> int:
        hierarchy = {"super_admin": 100, "owner": 50, "admin": 30, "team_lead": 20, "member": 10}
        return hierarchy.get(role.lower(), 0)

    """Load an integration on-demand (Solves the startup speed issue)"""
    # 1. Quota Check (Phase 41)
    if tenant_id:
        quota_manager.check_integration_access(tenant_id, integration_name, db)

    if not circuit_breaker.is_enabled(integration_name):
        raise HTTPException(
            status_code=503,
            detail=f"Integration {integration_name} is disabled due to repeated failures",
        )

    try:
        logger.info(f"Loading integration: {integration_name}")
        router = load_integration(integration_name, registry="api_routers")

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
        raise HTTPException(status_code=500, detail="Internal error")


@app.get("/api/integrations/stats")
async def get_all_integration_stats():
    return circuit_breaker.get_all_stats()


@app.post("/api/integrations/{integration_name}/reset")
async def reset_integration(integration_name: str, current_user: User = Depends(get_current_user)):
    circuit_breaker.reset(integration_name)
    return {"status": "reset", "integration": integration_name}


# ============================================================================
# DEBUG ENDPOINTS (For troubleshooting - remove in production)
# ============================================================================
try:
    from api.routes.debug_password_check import router as debug_password_check_router
    from api.routes.debug_password_reset import router as debug_password_router
    from api.routes.debug_rls_check import router as debug_rls_check_router
    from api.routes.debug_tenant_check import router as debug_tenant_router
    from api.routes.debug_user_check import router as debug_user_router

    app.include_router(debug_tenant_router)
    app.include_router(debug_user_router)
    app.include_router(debug_password_router)
    app.include_router(debug_password_check_router)
    app.include_router(debug_rls_check_router)

    # Debug endpoint for entity type diagnostics
    from api.routes.debug_entity_types import router as debug_entity_types_router

    app.include_router(debug_entity_types_router)

    # Admin endpoint for entity type management
    from api.routes.admin_entity_routes import router as admin_entity_router

    app.include_router(admin_entity_router)
    logger.info("✅ Debug endpoints enabled")
except (ImportError, TypeError) as e:
    logger.warning(f"Debug routes not available: {e}")


# ============================================================================
# 3. SPECIAL HANDLING: WHATSAPP (RESTORED FROM V1)
# ============================================================================
# Native WhatsApp integration is now handled via include_router in the messaging section

# System endpoints moved to top of file to ensure priority

# ============================================================================
# 5. LIFECYCLE & SCHEDULER
# Schedulers and listeners are now handled within the lifespan manager.
# ============================================================================


if __name__ == "__main__":
    startup_logger.info("Starting uvicorn server directly...")
    try:
        uvicorn.run("main_api_app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
    except Exception as e:
        startup_logger.error(f"CRITICAL: Failed to start uvicorn: {e}")
        startup_logger.error(traceback.format_exc())
        sys.exit(1)
else:
    # When run as a module (e.g., python -m uvicorn main_api_app:app)
    # This branch won't execute, but the app object is created below
    pass
