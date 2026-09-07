"""
Atom Backend - Full Application Entry Point (canonical)

This is the real application: all 40+ routers (auth, agents, skills, marketplace,
workflows, canvas, integrations, finance, governance, ...), middleware, the
scheduler, and the full feature surface used in production and by the E2E
user-journey suite. Docker and CI build/run this module.

Launch locally:
    cd /Users/rushiparikh/projects/atom
    PYTHONPATH=$PWD:$PWD/backend \
        ./backend/venv/bin/python -m uvicorn main_api_app:app --port 8001

The minimal `minimal_app.py` (renamed from main.py to avoid confusion) exists
as a fast dev bootstrap (~125 routes) for quick smoke checks; new users should
start here (main_api_app) instead.
"""
from __future__ import annotations

import asyncio

# -*- coding: utf-8 -*-
# Reload trigger
import os
from sqlalchemy import text as _sa_text
import sys
from typing import ClassVar, Union

from dotenv import load_dotenv

# Load environment variables: backend/.env is the documented dev location
# (created by `make setup`), then the repo-root .env used by docker compose,
# then .env.local overrides. dotenv never overwrites already-set values, so
# the first file that defines a variable wins.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(backend_dir, ".env"))
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
# Modules that are GENUINELY optional — they may not be installed in every
# environment (third-party integrations behind a feature flag / paid plan).
# A missing optional module degrades gracefully to an empty router. Anything
# NOT in this set that fails to import is treated as a real bug (logged at
# ERROR, and raised in non-production so the test suite catches it).
_OPTIONAL_MODULES = frozenset({
    # External integrations that require credentials/SDKs not always present
    "integrations.awesome_lists_routes",
    "integrations.skyvia_routes",
    "integrations.mssql_service",
    "integrations.googledrive_service",
    "core.media.spotify_service",
})


def _is_optional(module_path: str) -> bool:
    """True if a module is a known-optional integration (graceful on ImportError)."""
    if module_path in _OPTIONAL_MODULES:
        return True
    # Heuristic: third-party integration adapters under core/integrations/adapters/
    # are optional (they wrap external SDKs that may be uninstalled).
    return module_path.startswith("core.integrations.adapters.")


def safe_import_router(module_path: str, router_name: str = "router"):
    try:
        from fastapi import APIRouter
    except (ImportError, TypeError):

        class APIRouter:
            pass  # Fallback for extremely broken environments

    import importlib
    import os as _os

    _is_prod = _os.getenv("ENVIRONMENT", "").lower() == "production"

    try:
        module = importlib.import_module(module_path)
        return getattr(module, router_name)
    except ImportError as e:
        optional = _is_optional(module_path)
        if optional:
            # Genuinely optional integration not installed — degrade gracefully.
            logger.info(f"Optional router not available: {module_path} ({e})")
            return APIRouter()
        # Non-optional module missing = a broken import path or dead reference.
        # Log loudly in ALL environments so it isn't hidden. Raise only when
        # STRICT_ROUTERS is set (opt-in strict mode for CI) — otherwise the app
        # stays bootable while the ERROR logs make every dead import visible.
        msg = f"Missing router (not optional): {module_path} ({e})"
        logger.error(msg)
        if _os.getenv("STRICT_ROUTERS", "").lower() in ("1", "true", "yes"):
            raise
        return APIRouter()
    except Exception as e:
        # Real bug in the module (NameError, AttributeError, SyntaxError, etc.)
        # In production, this must surface — otherwise broken routers vanish
        # silently and produce 404s that are hard to diagnose.
        msg = f"Failed to import {module_path} ({type(e).__name__}): {e}"
        if _is_prod:
            logger.error(msg)
            raise
        logger.warning(f"Fallback: {msg}")
        return APIRouter()


analytics_router = safe_import_router("core.analytics_endpoints")
workspace_router = safe_import_router("api.workspace_routes")
# risk_routes was never included (dead import removed, round 80f) — the
# orphaned router stays unmounted by design; see docs/INTEGRATIONS_JOURNEY_AUDIT.md §4.4
template_router = safe_import_router("api.workflow_template_routes")
entity_type_router = safe_import_router("api.entity_type_routes")
multi_entity_extraction_router = safe_import_router("core.multi_entity_extraction_routes")
ingestion_crud_router = safe_import_router("api.routes.ingestion_crud_routes")
token_refresh_router = safe_import_router("integrations.token_refresh_routes")
webhook_renewal_router = safe_import_router("integrations.webhook_renewal_routes")
agent_routes_v2_router = safe_import_router("api.agent_routes")
health_router = safe_import_router("api.health_routes")
messaging_router = safe_import_router("api.messaging_routes")
platform_webhook_router = safe_import_router("api.routes.webhooks")
ingestion_webhooks_router = safe_import_router("api.routes.webhooks.ingestion_webhooks")
supervision_router = safe_import_router("api.supervision_routes")
supervised_queue_router = safe_import_router("api.supervised_queue_routes")
core_user_activity_router = safe_import_router("api.user_activity_routes")
operational_router = safe_import_router("api.operational_routes")
agent_status_router = safe_import_router("api.agent_status_endpoints")
user_templates_router = safe_import_router("api.user_templates_endpoints")
workflow_versioning_router = safe_import_router("api.workflow_versioning_endpoints")
forensics_router = safe_import_router("api.forensics_api")
debug_router = safe_import_router("api.debug_routes")
agent_router = safe_import_router("api.agent_routes")
workflow_router = safe_import_router("core.workflow_endpoints")
workflow_template_router = safe_import_router("api.workflow_template_routes")
protection_router = safe_import_router("api.protection_api")
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
            # Fallback search: fills variables the process environment did
            # not set. It must NOT override them — explicit process env
            # (docker -e, systemd, scripts/start-backend.sh, the e2e journey
            # harness' fresh DATABASE_URL and mock provider credentials)
            # always wins over .env files. override=True here silently
            # discarded every one of those.
            load_dotenv(path)
            logger.info("Configuration loaded", extra={"env_path": str(path)})
            loaded = True
            break

    if not loaded:
        logger.warning("No .env file found in any expected location. Realizing on system env vars.")

    # Sync Zoho variable names to prevent 'None' during auth
    zoho_crm_id = os.getenv("ZOHO_CRM_CLIENT_ID")
    if zoho_crm_id and not os.getenv("ZOHO_CLIENT_ID"):
        os.environ["ZOHO_CLIENT_ID"] = zoho_crm_id

    zoho_crm_secret = os.getenv("ZOHO_CRM_CLIENT_SECRET")
    if zoho_crm_secret and not os.getenv("ZOHO_CLIENT_SECRET"):
        os.environ["ZOHO_CLIENT_SECRET"] = zoho_crm_secret


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
    "https://atomagentos.com,https://app.atomagentos.com,https://admin.atomagentos.com,https://api.atomagentos.com,http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
).split(",")
# Add any extra origins from env
extra_origins = os.getenv("ADDITIONAL_ALLOWED_ORIGINS")
if extra_origins:
    ALLOWED_ORIGINS.extend(extra_origins.split(","))

ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]
logger.info(f"CORS Allowed Origins: {ALLOWED_ORIGINS}")
DISABLE_DOCS = ENVIRONMENT == "production"


# Strong references for background tasks so the GC doesn't cancel them
# mid-flight (asyncio only holds weak refs; without this, under memory
# pressure workers silently vanish with "Task was destroyed but it is pending!").
_background_tasks: set = set()


def _spawn_background_task(coro) -> None:
    """Create a background task AND retain a strong reference to it."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_listener_instance
    # --- STARTUP ---
    logger.info("=" * 60)
    logger.info("ATOM Platform Starting (Hybrid Mode)")
    logger.info("=" * 60)

    # Wedge forensics: `kill -USR1 <pid>` dumps every thread's Python stack
    # into the log. When the event loop saturates, a C-level `sample` shows
    # only interpreter frames — this names the exact coroutine/lock. Cheap,
    # permanent, never fires on its own.
    try:
        import faulthandler
        import signal as _signal

        faulthandler.register(_signal.SIGUSR1, file=sys.stderr, all_threads=True)
        logger.info("faulthandler: SIGUSR1 dumps thread stacks to stderr")
    except Exception as fh_err:
        logger.debug(f"faulthandler SIGUSR1 registration skipped: {fh_err}")

    # Wipe detector (incident 2026-09-04): a stray script emptied the dev DB
    # and the app re-seeded a blank world without complaint. Best-effort,
    # never blocks startup — see core/db_safety.py.
    try:
        from core.db_safety import check_wipe_at_startup

        check_wipe_at_startup()
    except Exception as e:
        logger.debug(f"startup db wipe check skipped: {e}")

    # 0. Initialize Database
    try:
        logger.info("Initializing database tables...")
        from core.admin_bootstrap import ensure_admin_user
        from core.database import engine
        from core.models import Base

        # SQLite schema-drift repair BEFORE create_all: a local DB whose
        # schema lags the models makes every INSERT for the drifted table
        # fail silently (agent_reasoning_steps lacked requested_model/
        # resolved_model → no reasoning step ever persisted → the Agent
        # Workspace "Tasks" panel was permanently empty).
        try:
            from core.sqlite_schema_repair import repair_known_drift
            repair_known_drift()
        except Exception as drift_err:
            logger.warning(f"schema drift repair skipped: {drift_err}")

        # Base.metadata.create_all is safe to call but can be slow/hang in production with 12k lines
        try:
            # Skip creation if in test mode or production
            is_test_mode = (
                os.getenv("PYTEST_VERSION") is not None
                or os.getenv("PYTEST_CURRENT_TEST") is not None
            )
            if os.getenv("ENVIRONMENT") != "production" and not is_test_mode:
                # Register late-imported model modules FIRST — create_all
                # only covers Base subclasses that have been imported, and
                # the auto-dev tables (skill_candidates, tool_mutations)
                # used to be missing on fresh installs until long after.
                from core.auto_dev import models as _autodev_models  # noqa: F401

                Base.metadata.create_all(bind=engine)
                logger.info("✓ Database tables initialized")

                # Memory-store reconciliation BEFORE any worker touches
                # LanceDB: adopt legacy CWD-relative stores (repo-root
                # data/atom_memory) into the anchored backend store —
                # idempotent, never overwrites an anchored store that
                # already has tables.
                from core.memory_store_bootstrap import reconcile_memory_store

                _store_recon = reconcile_memory_store()
                if _store_recon.get("migrated"):
                    logger.warning(
                        f"✓ Memory store reconciled from legacy location: "
                        f"{[m['workspace'] for m in _store_recon['migrated']]}")
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

                # Personal→Team wedge: surface solo-operator starter templates in
                # the DB-backed template UI (idempotent, fail-soft).
                from core.database import SessionLocal
                from core.personal_template_seeder import seed_personal_templates

                with SessionLocal() as _seed_db:
                    _seeded = seed_personal_templates(_seed_db)
                    if _seeded:
                        logger.info(f"✓ Seeded {_seeded} personal starter template(s)")
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
    # Initialize before the scheduler gate so the QStash cleanup block below
    # (which runs outside the if) doesn't hit NameError when the scheduler is
    # disabled. Previously, enabling ENABLE_SCHEDULER=false caused every
    # startup to raise NameError (silently swallowed by except).
    qstash_init_skip = True
    startup_session_key = None
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
                # workflow_scheduler.start() is synchronous — awaiting None
                # raises TypeError, which was silently swallowed. Call directly.
                workflow_scheduler.start()
        except Exception as exc:
            logger.warning(f"Workflow scheduler failed to start: {exc}")

        # 2. Start Agent Scheduler
        try:
            from core.scheduler import AgentScheduler

            _spawn_background_task(AgentScheduler.get_instance().load_scheduled_agents())
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

        # 4b. Fact-watch poller — proactive re-checking of live facts an
        # agent grounded an artifact on (stock in a quoted email, deal
        # stage, invoice status). Providers self-register from the
        # integrations side; the poll interval is env-tunable and 0
        # disables the loop entirely.
        try:
            from core.fact_watch import get_fact_watch_service
            import integrations.fact_watch_providers  # noqa: F401 — registers checkers/extractors

            _poll_interval = int(
                os.getenv("FACT_WATCH_POLL_INTERVAL_SECONDS", "300"))
            await get_fact_watch_service().start(
                interval_seconds=_poll_interval)
        except Exception as fw_err:
            logger.warning(f"fact watch poller failed to start: {fw_err}")

        # 5. Crash Recovery — reconcile executions orphaned in RUNNING by a
        # process crash. Previously this slot imported core.startup_tasks
        # (run_startup_maintenance), a module that did not exist, so the
        # import failed and was silently swallowed — leaving ghost RUNNING
        # rows forever. Now we run a real, idempotent recovery sweep.
        try:
            from core.execution_recovery import reconcile_orphaned_executions

            recovery = reconcile_orphaned_executions()
            if recovery.get("workflow_recovered") or recovery.get("agent_recovered"):
                logger.info(
                    "Startup recovery summary: %(wf)s workflow(s), %(ag)s agent(s)",
                    {
                        "wf": recovery.get("workflow_recovered", 0),
                        "ag": recovery.get("agent_recovered", 0),
                    },
                )
        except Exception as e:
            logger.error(f"Failed to run execution recovery sweep: {e}")

        # 6. Start Hybrid Ingestion scheduled sync loop (pull integrations into memory)
        # Auto-sync is on by default (integrations should stay fresh without a
        # manual toggle). Disable explicitly with ENABLE_INGESTION_SYNC=false.
        if os.getenv("ENABLE_INGESTION_SYNC", "true").lower() == "true":
            try:
                from core.hybrid_data_ingestion import get_hybrid_ingestion_service

                ingestion_service = get_hybrid_ingestion_service()
                _spawn_background_task(ingestion_service.run_scheduled_syncs())
                logger.info("✓ Hybrid ingestion scheduled-sync loop started")
            except Exception as e:
                logger.error(f"Failed to start hybrid ingestion sync loop: {e}")

        # 6b. Org Ingestion Hub member pull loop (Phase 3) — pulls signed delta
        # bundles from the designated hub on an interval and applies them via
        # the Phase 2 import path. Opt-in: ATOM_ORG_HUB_URL + ATOM_ORG_HUB_API_KEY
        # (and ATOM_ORG_SHARING_ENABLED=true). Killing the hub degrades members
        # to stale-but-functional local data — the loop retries next interval.
        if os.getenv("ATOM_ORG_SHARING_ENABLED", "false").lower() in ("1", "true", "yes") and os.getenv("ATOM_ORG_HUB_URL"):
            try:
                from core.org_hub_service import OrgHubService

                async def _hub_pull_loop():
                    from core.database import get_db_session
                    from core.personal_scope import PERSONAL_TENANT_ID, PERSONAL_WORKSPACE_ID

                    interval_min = float(os.getenv("ATOM_ORG_HUB_PULL_INTERVAL_MIN", "15"))
                    sources = [s.strip() for s in os.getenv("ATOM_ORG_HUB_SOURCES", "").split(",") if s.strip()]
                    ceiling = os.getenv("ATOM_ORG_HUB_SENSITIVITY_CEILING", "internal")
                    hub_url = os.getenv("ATOM_ORG_HUB_URL", "")
                    api_key = os.getenv("ATOM_ORG_HUB_API_KEY", "")
                    while True:
                        try:
                            with get_db_session() as db:
                                await OrgHubService().pull_and_apply(
                                    db,
                                    hub_url=hub_url,
                                    api_key=api_key,
                                    sources=sources,
                                    workspace_id=PERSONAL_WORKSPACE_ID,
                                    tenant_id=PERSONAL_TENANT_ID,
                                    sensitivity_ceiling=ceiling,
                                )
                        except Exception as e:
                            logger.warning(f"Org hub pull failed (will retry in {interval_min} min): {e}")
                        await asyncio.sleep(interval_min * 60)

                _spawn_background_task(_hub_pull_loop())
                logger.info("✓ Org Ingestion Hub member pull loop started (ATOM_ORG_HUB_URL set)")
            except Exception as e:
                logger.error(f"Failed to start org hub pull loop: {e}")

        # 6c. Webhook ingestion queue worker. With Redis configured,
        # enqueue_ingestion_job only LPUSHes to ingestion:webhook:jobs and
        # nothing consumed the queue — pushed records (e.g. zoho_books
        # deliveries) sat in Redis forever while the no-Redis path processed
        # inline. This loop RPOPs each job through the same pipeline.
        try:
            from core.webhook_ingestion_triggers import WebhookIngestionQueue

            _spawn_background_task(WebhookIngestionQueue().run_worker_loop())
            logger.info("✓ Webhook ingestion queue worker started")
        except Exception as e:
            logger.error(f"Failed to start webhook ingestion queue worker: {e}")

        # Outlook: the scripted automation loop is REMOVED — the governed
        # email agent (core.email_agent) handles inbox work through MCP gates
        # instead, triggered by the Outlook webhook (ingestion_webhooks).

        # Integration token reconciliation (all providers): tokens pointing
        # at users that no longer exist (world wipe/re-seed) would keep
        # pollers running against dead owners and stamp ingested data no
        # scoped search can see. Deactivates orphans, reports stale-expired.
        try:
            from core.integration_startup_reconciliation import (
                reconcile_integration_tokens,
            )

            reconcile_integration_tokens()
        except Exception as e:
            logger.error(f"Integration token reconciliation failed: {e}")

        # Start Outlook Memory Poller (recover after restart when Outlook is
        # already connected). Reads tokens from IntegrationToken; skips when no
        # active outlook/microsoft token exists or the stream is already up.
        try:
            from core.database import get_db_session
            from core.models import IntegrationToken

            with get_db_session() as db:
                outlook_token = (
                    db.query(IntegrationToken)
                    .filter(
                        IntegrationToken.provider.in_(["outlook", "microsoft"]),
                        IntegrationToken.status == "active",
                    )
                    .first()
                )
            if outlook_token and outlook_token.user_id:
                from integrations.atom_communication_ingestion_pipeline import (
                    ingestion_pipeline,
                )

                # user_id here only seeds the poller's no-DB fallback: the
                # fetch loop re-enumerates every active token owner per cycle
                # (_outlook_token_owners), so .first() picking one owner does
                # not limit which mailboxes get polled.
                if ingestion_pipeline.start_outlook_poller(user_id=outlook_token.user_id):
                    logger.info("✓ Outlook memory poller recovered (connected account found)")
                    # Real-time channel: Graph subscription lifecycle (no-op
                    # unless ATOM_GRAPH_WEBHOOK_BASE_URL is configured).
                    try:
                        from integrations.outlook_realtime import outlook_realtime

                        outlook_realtime.start_renew_loop()
                        asyncio.get_running_loop().create_task(
                            outlook_realtime.ensure_subscription("default")
                        )
                    except Exception as rt_err:
                        logger.debug(f"outlook realtime channel skipped: {rt_err}")
        except Exception as e:
            logger.error(f"Failed to start Outlook memory poller: {e}")
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
        from enhanced_ai_workflow_endpoints import ai_service

        await ai_service.initialize_sessions()
        logger.info("✓ AI Workflow Service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize AI Workflow Service: {e}")

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

            from core.experiments import is_enabled as _exp

            # Start Activity State Worker (online/away/offline transitions)
            activity_worker = ActivityStateWorker(interval_seconds=60)
            _spawn_background_task(activity_worker.run())
            logger.info("✓ Activity State Worker running")

            # Start Queue Processing Worker (supervised execution)
            queue_worker = QueueProcessingWorker(interval_seconds=60)
            _spawn_background_task(queue_worker.run())
            logger.info("✓ Queue Processing Worker running")

            # 8c. Proactive Zoho token refresh — keeps the suite grant's
            # access token fresh ahead of expiry so a connect that isn't
            # followed by a data sync never degrades into 401s on the
            # record modules (CRM/Books/Inventory).
            try:
                from workers.token_refresh_worker import TokenRefreshWorker

                token_refresh_worker = TokenRefreshWorker(interval_seconds=300)
                _spawn_background_task(token_refresh_worker.run())
                logger.info("✓ Token Refresh Worker running")
            except Exception as e:
                logger.warning(f"Token Refresh Worker skipped: {e}")

            # 8b. Telegram long-polling worker — NAT-friendly IM for the
            # Personal Edition: no public URL, tunnel, or domain required.
            # Mutually exclusive with webhook mode (worker deletes any
            # registered webhook on startup).
            if (
                _exp("telegram_polling")
                and os.getenv("TELEGRAM_BOT_TOKEN")
            ):
                from workers.telegram_polling_worker import TelegramPollingWorker

                telegram_poller = TelegramPollingWorker()
                _spawn_background_task(telegram_poller.run())
                logger.info("✓ Telegram Polling Worker running (webhook mode disabled)")

            # 8c. Warm the memory assembler (P0): preload embedding models and
            # LanceDB tables so the first turn-time retrieval hits warm caches
            # instead of the per-leg timeout.
            if _exp("memory_context_assembly"):
                from core.memory_context_assembler import warm as warm_memory_assembler

                async def _warm_assembler():
                    await warm_memory_assembler()
                    logger.info("✓ Memory assembler warmed")

                _spawn_background_task(_warm_assembler())

            # 8c-ter. Warm LanceDB + FastEmbed UNCONDITIONALLY (the assembler
            # warm above is experiment-gated): the canvas co-editor's
            # semantic learning recall embeds profile texts at turn time, and
            # a cold ONNX model load (multi-second, blocking) inside the
            # planner's 30s budget is a stall. Both are local and lazy — this
            # just pays the init once at startup so every later call is ms.
            async def _warm_lancedb_and_embeddings():
                try:
                    from core.lancedb_handler import get_lancedb_handler

                    get_lancedb_handler()._ensure_db()
                    logger.info("✓ LanceDB connection warmed")
                except Exception as warm_err:
                    logger.warning(f"LanceDB warm skipped: {warm_err}")
                try:
                    from core.embedding_service import EmbeddingService

                    await EmbeddingService(provider="fastembed").create_fastembed_embedding(
                        "startup warmup"
                    )
                    logger.info("✓ FastEmbed model warmed")
                except Exception as warm_err:
                    logger.warning(f"FastEmbed warm skipped: {warm_err}")

            _spawn_background_task(_warm_lancedb_and_embeddings())

            # 8c-bis. Discord Gateway client — real-time MESSAGE_CREATE
            # ingestion (P0.4 §7 follow-up). Gated: requires
            # DISCORD_GATEWAY_ENABLED=true AND DISCORD_BOT_TOKEN; messages
            # flow through ingest_message like every other comm source.
            try:
                from integrations.discord_gateway import maybe_start_from_env

                if maybe_start_from_env():
                    logger.info("✓ Discord Gateway client running (real-time message ingestion)")
            except Exception as dg_err:
                logger.warning(f"Discord Gateway start skipped: {dg_err}")

            # 8c-bis. Episode lifecycle maintenance (R81j G15): opt-in daily
            # hygiene pass — recency decay + similarity consolidation.
            if os.getenv("ATOM_EPISODE_LIFECYCLE_MAINTENANCE_ENABLED", "false").lower() == "true":
                async def _episode_lifecycle_maintenance():
                    from core.database import SessionLocal as _SL
                    from core.episode_lifecycle_service import EpisodeLifecycleService

                    while True:
                        try:
                            await asyncio.sleep(24 * 3600)
                            with _SL() as _db:
                                agent_ids = [
                                    row[0]
                                    for row in _db.execute(
                                        _sa_text("SELECT id FROM agent_registry")
                                    ).fetchall()
                                ]
                                svc = EpisodeLifecycleService(_db)
                                await svc.run_daily_maintenance(agents=agent_ids)
                        except asyncio.CancelledError:
                            raise
                        except Exception as _maint_err:
                            logger.warning(
                                f"Episode lifecycle maintenance pass failed: {_maint_err}"
                            )

                _spawn_background_task(_episode_lifecycle_maintenance())
                logger.info(
                    "✓ Episode lifecycle maintenance enabled "
                    "(ATOM_EPISODE_LIFECYCLE_MAINTENANCE_ENABLED)"
                )

            # 8c-ter. Trust calibration automation loop (R81o P3): consent-
            # gated certify->notify/approve/auto dispatch. Default off.
            if os.getenv("ATOM_TRUST_CALIBRATION_AUTO_ENFORCE", "off").lower() != "off":
                _tc_interval = float(
                    os.getenv("ATOM_TRUST_CALIBRATION_AUTO_INTERVAL_MIN", "60")
                )

                async def _trust_calibration_automation():
                    from core.trust_calibration import automation as _tca
                    from core.database import SessionLocal as _TSL

                    while True:
                        try:
                            await asyncio.sleep(max(_tc_interval, 1.0) * 60)
                            with _TSL() as _tc_db:
                                result = _tca.run_automation_pass(_tc_db)
                            if result.get("ran"):
                                logger.info(
                                    "Trust calibration automation: %s",
                                    {k: v for k, v in result.items() if k != "stats"},
                                )
                        except asyncio.CancelledError:
                            raise
                        except Exception as _tc_err:
                            logger.warning(
                                f"Trust calibration automation failed: {_tc_err}"
                            )

                _spawn_background_task(_trust_calibration_automation())
                logger.info(
                    f"✓ Trust calibration automation enabled "
                    f"(mode={os.getenv('ATOM_TRUST_CALIBRATION_AUTO_ENFORCE')}, "
                    f"interval={_tc_interval}min)"
                )

            # 8c-quater. Ontology draft automation loop: consent-gated
            # promotion of auto-discovered entity types (off|notify|approve|
            # auto). Default auto — runs unless explicitly set to off.
            if os.getenv("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "auto").lower() != "off":
                _od_interval = float(
                    os.getenv("ATOM_ONTOLOGY_DRAFT_AUTO_INTERVAL_MIN", "60")
                )

                async def _ontology_draft_automation():
                    from core.ontology import ontology_draft_automation as _oda
                    from core.database import SessionLocal as _ODSL

                    while True:
                        try:
                            await asyncio.sleep(max(_od_interval, 1.0) * 60)
                            with _ODSL() as _od_db:
                                result = _oda.run_automation_pass(_od_db)
                            if result.get("ran"):
                                logger.info(
                                    "Ontology draft automation: %s",
                                    {k: v for k, v in result.items()
                                     if k not in ("promoted", "queued", "revoked")},
                                )
                        except asyncio.CancelledError:
                            raise
                        except Exception as _od_err:
                            logger.warning(
                                f"Ontology draft automation failed: {_od_err}"
                            )

                _spawn_background_task(_ontology_draft_automation())
                logger.info(
                    f"✓ Ontology draft automation enabled "
                    f"(mode={os.getenv('ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE')}, "
                    f"interval={_od_interval}min)"
                )

            # 8d. Memory consolidation worker (P2.1): nightly rule-based
            # consolidation — contradiction sweeps + supersede — always off
            # the user-facing turn (sleep-time principle).
            if _exp("memory_consolidation"):
                from workers.memory_consolidation_worker import MemoryConsolidationWorker

                interval_h = float(os.getenv("MEMORY_CONSOLIDATION_INTERVAL_HOURS", "24"))
                consolidation_worker = MemoryConsolidationWorker(interval_hours=interval_h)
                _spawn_background_task(consolidation_worker.run())
                logger.info("✓ Memory Consolidation Worker running (%.1fh)", interval_h)

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

            _spawn_background_task(renewal_loop())
            logger.info("✓ Webhook Renewal loop started")

        except Exception as e:
            logger.error(f"Failed to start Supervision System or Webhook Renewal workers: {e}")

    # 10b. Auto-Dev ReflectionEngine — the listener that turns emitted
    # task-fail events into Memento skill / AlphaEvolver tool-mutation
    # candidates. The engine and the event emission both existed, but
    # nothing ever CONSTRUCTED the listener, so failures were emitted into
    # the void and the evolution harness was inert. Idempotent; sessionless
    # listener mode (fresh DB session per event).
    try:
        from core.auto_dev.reflection_engine import register_global

        register_global()
        logger.info("✓ Auto-Dev ReflectionEngine registered on event bus")
    except Exception as e:
        logger.error(f"Failed to register Auto-Dev ReflectionEngine: {e}")

    # 10. Webhook Processing Worker — module does not exist (never created).
    # The old try/except silently swallowed the ImportError on every startup,
    # logging "CRITICAL: Failed to start" while the feature was entirely inert.
    # Removed to stop the misleading startup log. If the worker is needed,
    # implement core/webhook_processing_worker.py and re-add this block.

    # 11. Start POMDP Memory Consolidation (offline "sleep-inspired" cycle)
    # Runs every CONSOLIDATION_INTERVAL_HOURS (6h). Previously the service
    # existed but nothing ever invoked it — the advertised feature was inert.
    if not is_test_mode:
        try:
            async def _consolidation_loop():
                from core.memory.memory_consolidation_service import ConsolidationConfig, MemoryConsolidationService
                from core.database import SessionLocal
                interval = ConsolidationConfig.CONSOLIDATION_INTERVAL_HOURS * 3600
                while True:
                    # Use a context-managed session so the connection is always
                    # returned to the pool (previously SessionLocal() was never
                    # closed — one connection leaked per cycle, exhausting the
                    # 20+30 pool over days).
                    db = SessionLocal()
                    try:
                        svc = MemoryConsolidationService(db=db)
                        await svc.run_consolidation_cycle()
                        logger.info("✓ POMDP memory consolidation cycle complete")
                    except Exception as ce:
                        logger.warning(f"Memory consolidation cycle failed (non-fatal): {ce}")
                    finally:
                        db.close()
                    await asyncio.sleep(interval)
            _spawn_background_task(_consolidation_loop())
            logger.info("✓ POMDP Memory Consolidation background task started (6h interval)")
        except Exception as e:
            logger.warning(f"Could not start memory consolidation loop (non-fatal): {e}")

    # 12. Rated-exchange memory maintenance (Phase 56 learning loop upkeep):
    # backfill missing vectors, distill recurring rejections into pattern
    # lessons via the teaching circuit, opt-in shadow→enforce latch.
    if not is_test_mode:
        try:
            from core.exchange_memory_maintenance import exchange_maintenance_loop

            _spawn_background_task(exchange_maintenance_loop())
            logger.info("✓ Exchange memory maintenance background task started")
        except Exception as e:
            logger.warning(f"Could not start exchange memory maintenance (non-fatal): {e}")

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
    except Exception as e:
        logger.debug(f"Webhook worker shutdown: {e}")

    try:
        from ai.workflow_scheduler import workflow_scheduler

        workflow_scheduler.shutdown()
        logger.info("✓ Workflow Scheduler stopped")
    except Exception as e:
        logger.debug(f"Workflow scheduler shutdown: {e}")

    # Stop Availability Background Worker (NEW - Supervision System)
    try:
        from core.availability_background_worker import stop_worker

        await stop_worker()
        logger.info("✓ Availability Background Worker stopped")
    except Exception as e:
        logger.debug(f"Availability worker shutdown: {e}")

    try:
        from core.memory_maintenance import stop_memory_maintenance

        await stop_memory_maintenance()
        logger.info("✓ Memory Maintenance Scheduler stopped")
    except Exception as e:
        logger.debug(f"Memory maintenance shutdown: {e}")

    try:
        from core.agent_event_bus import get_agent_event_bus

        await get_agent_event_bus().stop()
        logger.info("✓ Postgres Event Bus listener stopped")
    except Exception as e:
        logger.debug(f"Event bus shutdown: {e}")

    try:
        from enhanced_ai_workflow_endpoints import ai_service

        await ai_service.cleanup_sessions()
        logger.info("✓ AI Workflow Service sessions cleaned up")
    except Exception as e:
        logger.debug(f"AI workflow session cleanup: {e}")

    try:
        from api.learning_routes import shutdown_learning_service

        await shutdown_learning_service()
        logger.info("✓ Learning Service shutdown complete")
    except ImportError:
        pass  # shutdown_learning_service doesn't exist — not critical
    except Exception as e:
        logger.debug(f"Learning service shutdown: {e}")


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
    # Some tools (e.g. schemathesis) don't recognize OpenAPI 3.1.0 as valid;
    # emit a 3.0.3 schema since the API avoids 3.1-only features.
    app.openapi_version = "3.0.3"
    startup_logger.info("✓ FastAPI app instance created")

    # Initialize connection leak detector
    try:
        from core.connection_leak_detector import install_connection_tracking

        install_connection_tracking()
        startup_logger.info("✓ Connection leak detector installed")
    except Exception as e:
        startup_logger.warning(f"Connection leak detector not available: {e}")

    try:
        from integrations.outlook_routes import router as outlook_app_router
        app.include_router(outlook_app_router, prefix="/api/integrations/outlook", tags=["outlook"])
        app.include_router(outlook_app_router, prefix="/api/v1/integrations/outlook", tags=["outlook"])
        startup_logger.info("✓ Outlook integration routes registered at /api/integrations/outlook and /api/v1/integrations/outlook")
    except Exception as e:
        startup_logger.error(f"Failed to register Outlook routes: {e}")
        startup_logger.warning(f"✗ Failed to install connection leak detector: {e}")

    # --- CORE HEALTH ENDPOINTS (FIRST PRIORITY) ---
    @app.get("/alive", tags=["System"])
    async def liveness():
        """Simple liveness check for Fly.io."""
        return {
            "status": "alive",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "debug_id": "v8.0.0",
        }

    # API compatibility pin (berd gap #2): clients record the API version
    # they were built against; a mismatch warns instead of failing subtly.
    ATOM_API_VERSION = 1

    @app.get("/api/meta/version", tags=["System"])
    async def api_version():
        return {
            "api_version": ATOM_API_VERSION,
            "product": "atom",
            "commit": os.getenv("GIT_SHA", "dev"),
        }

    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint."""
        return {"name": "ATOM Platform API", "version": "8.0.0", "status": "running"}

    # Process identity for /health: a stale backend (orphaned --reload worker,
    # or a second instance on a different port) answers /health 200 exactly
    # like a fresh one while serving old in-memory state. Surfacing boot time,
    # pid and port makes that mismatch visible at a glance.
    _PROCESS_STARTED_AT = datetime.now(timezone.utc)

    def _process_identity() -> dict:
        """Best-effort process identity for the health payload — never raises."""
        info = {
            "pid": os.getpid(),
            "started_at": _PROCESS_STARTED_AT.isoformat(),
            "cwd": os.getcwd(),
            "git_commit": "unknown",
        }
        try:
            if "--port" in sys.argv:
                info["port"] = int(sys.argv[sys.argv.index("--port") + 1])
        except Exception:
            pass
        try:
            import subprocess as _sp
            info["git_commit"] = _sp.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=2,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            ).stdout.strip() or "unknown"
        except Exception:
            pass
        try:
            from core.database import DATABASE_URL as _db_url
            info["database"] = _db_url.split("///")[-1] if "sqlite" in _db_url else "postgresql"
        except Exception:
            pass
        try:
            from api import byok_routes as _byok
            info["byok_key_store"] = _byok.BYOK_KEYS_FILE
        except Exception:
            pass
        return info

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
            "version": "8.0.0",
            "deployed_sha": deployed_sha,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "identity": _process_identity(),
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
            # NOTE: `except ... as e` unbinds `e` when the handler exits, so this
            # closure must not reference it (NameError). The startup failure
            # detail also stays server-side (logged above) instead of leaking.
            return {
                "status": "degraded",
                "error": "Application failed to initialize",
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
        openapi_version=app.openapi_version,
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

# Core modules whose routers already declare their own root prefixes
# (e.g. /api/atom-agent, /api/auth). They must be mounted at the root —
# NOT under the third-party /api/v1/integrations/{name} prefix. Used by both
# the eager loader and the on-demand auto-load middleware so the two stay
# consistent (fixes /api/atom-agent/* returning 404 after 7cc5582e3
# un-blacklisted atom_agent from the on-demand loader).
CORE_API_MODULES = {
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
    # slack declares its own /api/slack root prefix (slack_routes.py); the
    # frontend proxy pages (pages/api/integrations/slack/*) and generated API
    # types call /api/slack/* directly. Mounting it under the unified
    # /api/v1/integrations/slack prefix double-prefixes every route
    # (/api/v1/integrations/slack/api/slack/...) and 404s all Slack calls.
    "slack",
}

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
                is_core_module = name in CORE_API_MODULES

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
                    prefix = "/api/integrations/outlook"
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
    forced_modules = ["zoho_workdrive", "zoho_crm", "zoho_books", "zoho_inventory", "outlook"]
    for mod in forced_modules:
        try:
            if mod not in _loaded_integrations:
                router = load_integration(mod, registry="api_routers")
                if router:
                    # General rule, not a per-app list: a router that declares
                    # its own prefix (e.g. /api/zoho-workdrive,
                    # /api/integrations/zoho_crm) is mounted bare — adding
                    # /api/v1/integrations/... on top doubled every path and
                    # 404'd the frontend's bare calls. Prefix-less routers get
                    # the standard integration prefix.
                    router_prefix = getattr(router, "prefix", "")
                    if router_prefix:
                        app.include_router(router, tags=[mod])
                        logger.info(f"  ✓ {mod} (router-prefixed bare mount at {router_prefix})")
                    else:
                        prefix = "/api/integrations/outlook" if mod == "outlook" else f"/api/v1/integrations/{mod.replace('_', '-')}"
                        app.include_router(router, prefix=prefix, tags=[mod])
                        logger.info(f"  ✓ {mod} (Forced registration at {prefix})")
                    _loaded_integrations.add(mod)
        except Exception as e:
            logger.error(f"  ✗ Forced registration failed for {mod}: {e}")

# --- FORCED JOURNEY ROUTER REGISTRATION (Round 80b) ---
# dropbox/gitlab/monday/telegram/whatsapp/xero ship hub pages + OAuth flows
# (docs/INTEGRATIONS_JOURNEY_AUDIT.md §3 F1/F2) but were registry-LAZY, so
# their real /api/{app}/* routes were shadowed by the legacy health stub
# (api_legacy_health.py, mounted last) with fake data — and a missing logger
# in that stub's broadcast path turned EVERY /api/{app}/status into a 500.
# Mount them at their DECLARED root prefixes so real endpoints resolve and
# precede the stub (FastAPI matches routes in registration order). The real
# routers win; the legacy stub stays for apps that remain stub-only.
if not is_test_mode:
    journey_modules = ("dropbox", "gitlab", "monday", "telegram", "whatsapp", "xero")
    for mod in journey_modules:
        try:
            if mod not in _loaded_integrations:
                router = load_integration(mod, registry="api_routers")
                if router and isinstance(router, APIRouter):
                    # Router declares its own root prefix (/api/xero, ...): no
                    # additional prefix — mirrors slack's root handling (line 1272).
                    app.include_router(router, tags=[mod])
                    _loaded_integrations.add(mod)
                    logger.info(f"  ✓ {mod} (journey root mount)")
        except Exception as e:
            logger.error(f"  ✗ Journey registration failed for {mod}: {e}")

# --- Round 83: OneDrive / Google Drive journey route repair ---------------
# The integration panels (OneDriveIntegration.tsx / GoogleDriveIntegration.tsx)
# call /api/onedrive/*, /api/gdrive/* and /api/ingest-gdrive-document — paths
# no real router ever served (only a dev-script mock). Mount the real
# journey routers at those exact paths so the panel journeys resolve. Also
# the only HTTP surface that can trigger each provider's full ingestion
# sync (every subfolder, every file type) for OneDrive/GDrive; Box, Dropbox
# and Zoho WorkDrive expose theirs on their own routers.
if not is_test_mode:
    try:
        from integrations.onedrive_journey_routes import (
            auth_router as onedrive_auth_journey_router,
            router as onedrive_journey_router,
        )

        app.include_router(onedrive_journey_router, tags=["onedrive-journey"])
        app.include_router(onedrive_auth_journey_router, tags=["onedrive-journey"])
        logger.info("  ✓ onedrive-journey (/api/onedrive/*, /api/auth/onedrive/*)")
    except Exception as e:
        logger.error(f"  ✗ onedrive-journey registration failed: {e}")

    try:
        from integrations.gdrive_journey_routes import (
            auth_router as gdrive_auth_journey_router,
            ingest_router as gdrive_ingest_router,
            router as gdrive_journey_router,
        )

        app.include_router(gdrive_journey_router, tags=["gdrive-journey"])
        app.include_router(gdrive_ingest_router, tags=["gdrive-journey"])
        app.include_router(gdrive_auth_journey_router, tags=["gdrive-journey"])
        logger.info(
            "  ✓ gdrive-journey (/api/gdrive/*, /api/ingest-gdrive-document, /api/auth/gdrive/*)"
        )
    except Exception as e:
        logger.error(f"  ✗ gdrive-journey registration failed: {e}")


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
app.include_router(forensics_router, prefix="/api/v1/forensics", tags=["forensics"])
app.include_router(debug_router)
# Agent status router: do NOT add a prefix — the router already declares its
# own prefix="/api/agent-status" with internal routes /agent/status/{task_id}.
# The old prefix="/api/v1" produced a doubled path
# /api/v1/api/agent-status/agent/status/{task_id} (404 for every frontend poll).
app.include_router(agent_status_router, tags=["agents"])
app.include_router(user_templates_router)

# Board routes (Kanban) — BUG-054: router existed but was never registered,
# so every /api/boards call from the frontend Kanban page 404'd.
board_router = safe_import_router("api.board_routes")
app.include_router(board_router)

# Audit trail (per-decision agent audit) — api/audit_routes.py declares its
# own /api/audit prefix, so include BARE. Previously never mounted: every
# auditAPI.* call from the /audit-trail frontend page 404'd.
try:
    from api.audit_routes import router as audit_trail_router
    app.include_router(audit_trail_router, tags=["audit"])
    logger.info("✓ Agent audit trail mounted at /api/audit")
except Exception as e:  # pragma: no cover - boot resilience
    logger.error(f"Failed to mount audit trail router: {e}")

# Nav stub routes — endpoints for sidebar nav items that had no backend
# endpoint (tasks, support tickets, communication analytics, integration health).
nav_stub_router = safe_import_router("api.nav_stub_routes")
app.include_router(nav_stub_router)
app.include_router(workflow_versioning_router)
app.include_router(protection_router)
app.include_router(platform_webhook_router)
app.include_router(ingestion_webhooks_router, prefix="/api", tags=["webhooks-ingestion"])
app.include_router(office_router, prefix="/api/v1/office", tags=["office"])

# --- V1 RESOURCE ROUTES (Migrated from lifespan) ---
# agent_routes.py and user_management_routes.py define their own in-router
# prefixes (/api/agents, /api/users) which match what the frontend calls.
# Do NOT add an include prefix here — that would double the path
# (e.g. /api/v1/agents/api/agents/...).
# Onboarding routes FIRST — their concrete paths (/api/agents/automation-suggestions)
# must beat agent_routes' catch-all GET /api/agents/{agent_id}, which otherwise
# swallows them as an agent id (404 "Agent not found: automation-suggestions").
agent_onboarding_router = safe_import_router("api.agent_onboarding_routes")
if agent_onboarding_router:
    app.include_router(agent_onboarding_router, tags=["agent-onboarding"])
if agent_router:
    app.include_router(agent_router, tags=["agents"])
# episode_routes.py declares its own /api/episodes prefix — include BARE.
# (Previously never mounted: the whole episodes API 404'd, incl. feedback submit.)
episode_router = safe_import_router("api.episode_routes")
app.include_router(episode_router, tags=["episodes"])
if workflow_router:
    app.include_router(workflow_router, prefix="/api/v1/workflows", tags=["workflows"])

# Mount the live workflow endpoints (core/workflow_endpoints.py) at the
# advertised /api/v1/workflows path. These provide the conductor endpoint
# (POST /workflows/conductor/execute) + execute/resume.
try:
    from core.workflow_endpoints import router as live_workflow_router
    app.include_router(live_workflow_router, prefix="/api/v1/workflows", tags=["workflows"])
    logger.info("✓ Live Workflow Endpoints mounted at /api/v1/workflows (incl. /conductor/execute)")
except Exception as e:
    logger.warning(f"Could not mount live workflow endpoints: {e}")
if workflow_template_router:
    # workflow_template_routes.py defines its own prefix /api/workflow-templates,
    # which is what marketplace.tsx and workflows/builder.tsx call. Include bare.
    app.include_router(workflow_template_router, tags=["workflow-templates"])
# Unified RPC surface (P1): frontend → POST /api/rpc/{action_name} → action_registry.
# Declares its own /api prefix, so include BARE (mirrors agent_routes.py pattern).
# Direct import (not safe_import_router) so a load failure surfaces loudly — the
# router depends only on stable core modules (action_registry/auth/database).
try:
    from api.rpc_routes import router as rpc_router
    app.include_router(rpc_router, tags=["rpc"])
    logger.info("✓ Unified RPC surface mounted at /api/rpc/{action_name} (P1)")
except Exception as e:  # pragma: no cover - boot resilience
    logger.error(f"Failed to mount RPC router: {e}")
# P3: Gatekeeper config surface (admin) — per-service policy overrides.
try:
    from api.gatekeeper_routes import router as gatekeeper_router
    app.include_router(gatekeeper_router, tags=["gatekeeper"])
    logger.info("✓ Gatekeeper config surface mounted at /api/gatekeeper (P3)")
except Exception as e:  # pragma: no cover - boot resilience
    logger.error(f"Failed to mount gatekeeper router: {e}")
# P6: External MCP server config surface (admin) — register/connect external
# MCP servers (the CLIENT config). Distinct from the /mcp SERVER surface.
try:
    from api.mcp_client_routes import router as mcp_client_router
    app.include_router(mcp_client_router, tags=["mcp-client"])
    logger.info("✓ External MCP client config mounted at /api/mcp/servers (P6)")
except Exception as e:  # pragma: no cover - boot resilience
    logger.error(f"Failed to mount MCP client router: {e}")
# Mini-apps: stateful, resumable canvas-UI apps on Firecracker microVMs.
# Declares its own /api prefix — include BARE (mirrors rpc_routes pattern).
try:
    from api.mini_app_routes import router as mini_app_router
    app.include_router(mini_app_router, tags=["mini-apps"])
    logger.info("✓ Mini-apps router mounted at /api/mini-apps")
except Exception as e:  # pragma: no cover - boot resilience
    logger.error(f"Failed to mount mini-apps router: {e}")
if messaging_router:
    app.include_router(messaging_router, prefix="/api/v1/messaging", tags=["messaging"])
if token_refresh_router and len(token_refresh_router.routes) > 0:
    app.include_router(token_refresh_router, tags=["token-refresh"])
if webhook_renewal_router and len(webhook_renewal_router.routes) > 0:
    app.include_router(webhook_renewal_router, tags=["webhook-renewal"])
if multi_entity_extraction_router:
    app.include_router(multi_entity_extraction_router)

# --- Live dashboard APIs (frontend hooks depend on these) ---
# These were orphaned router files that the frontend fetches from but were
# never mounted — wiring them unbreaks the Command Center dashboards.
try:
    from core.automation_settings_endpoints import router as automation_settings_router
    app.include_router(automation_settings_router)
    logger.info("✓ Automation Settings mounted at /api/v1/settings/automations")
except Exception as e:
    logger.warning(f"Could not mount automation settings: {e}")

try:
    from integrations.atom_finance_live_api import router as atom_finance_live_router
    app.include_router(atom_finance_live_router)
    logger.info("✓ Finance Live API mounted at /api/atom/finance/live")
except Exception as e:
    logger.warning(f"Could not mount finance live API: {e}")

try:
    from integrations.atom_projects_live_api import router as atom_projects_live_router
    app.include_router(atom_projects_live_router)
    logger.info("✓ Projects Live API mounted at /api/atom/projects/live")
except Exception as e:
    logger.warning(f"Could not mount projects live API: {e}")

try:
    from integrations.atom_sales_live_api import router as atom_sales_live_router
    app.include_router(atom_sales_live_router)
    logger.info("✓ Sales Live API mounted at /api/atom/sales/live")
except Exception as e:
    logger.warning(f"Could not mount sales live API: {e}")

try:
    from core.hypothesis_tree_endpoints import router as hypothesis_tree_router
    app.include_router(
        hypothesis_tree_router,
        prefix="/api/v1/hypothesis-tree",
        tags=["arbor"],
    )
    logger.info("✓ Arbor HTR endpoints mounted at /api/v1/hypothesis-tree")
except Exception as e:
    logger.warning(f"Could not mount Arbor HTR endpoints: {e}")


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

    Buffers the response body, and if it's an HTML error (4xx/5xx), replaces
    the body with a JSON error object. Previously the Content-Type was changed
    to application/json but the HTML body was passed through unchanged, so
    clients received Content-Type: JSON with an HTML body — unparseable.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status_code = None
        is_html_error = False
        body_chunks = []

        async def send_wrapper(message):
            nonlocal status_code, is_html_error

            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = message.get("headers", [])
                is_html_error = False

                if status_code >= 400:
                    for name, value in headers:
                        if name.decode().lower() == "content-type" and b"text/html" in value:
                            is_html_error = True
                            break

                if not is_html_error:
                    # Not an HTML error — pass through unchanged.
                    await send(message)
                # If it IS an HTML error, don't send the start yet — we'll
                # send a modified one after buffering the body.

            elif message["type"] == "http.response.body":
                if is_html_error:
                    # Buffer the body; don't send yet.
                    body_chunks.append(message.get("body", b""))
                    if not message.get("more_body"):
                        # Last chunk — reconstruct as JSON.
                        import json as _json
                        original = b"".join(body_chunks).decode("utf-8", errors="replace")
                        # Extract a short message from the HTML (strip tags).
                        import re as _re
                        text = _re.sub(r"<[^>]+>", " ", original).strip()
                        text = _re.sub(r"\s+", " ", text)[:300]
                        json_body = _json.dumps({
                            "detail": text or f"HTTP {status_code}",
                            "status_code": status_code,
                        }).encode("utf-8")

                        # Send the modified start with JSON headers.
                        from starlette.http_messages import _get_cached_headers as _gh
                        # Build headers manually (replace content-type + length).
                        new_headers = []
                        for name, value in headers:
                            nl = name.decode().lower()
                            if nl == "content-type":
                                new_headers.append((name, b"application/json"))
                            elif nl == "content-length":
                                new_headers.append((name, str(len(json_body)).encode()))
                            else:
                                new_headers.append((name, value))

                        await send({
                            "type": "http.response.start",
                            "status": status_code,
                            "headers": new_headers,
                        })
                        await send({
                            "type": "http.response.body",
                            "body": json_body,
                        })
                else:
                    await send(message)
            else:
                await send(message)

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
    "line",  # Mounted statically from api.line_routes (auth-gated); the lazy
    # registry's integrations.line_routes is a legacy no-auth duplicate that
    # would shadow it under a doubled prefix.
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

            if potential_integration in ("v1", "integrations"):
                # Handle /api/integrations/{name} or /api/v1/integrations/{name}
                if path_parts[2] == "integrations" and len(path_parts) >= 4:
                    potential_integration = path_parts[3]
                elif len(path_parts) >= 5 and path_parts[3] == "integrations":
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
                            # Core modules (e.g. atom_agent) declare their own root
                            # prefix (/api/atom-agent); only third-party integrations
                            # get the /api/v1/integrations/{name} prefix. Mirror the
                            # eager loader's CORE_API_MODULES handling here.
                            if integration_name == "outlook":
                                prefix = "/api/integrations/outlook"
                            elif integration_name in CORE_API_MODULES:
                                prefix = ""
                            elif str(getattr(router, "prefix", "")).startswith("/api/"):
                                # Round 80c: routers that declare their own root
                                # prefix (discord /api/discord, telegram
                                # /api/telegram, …) must mount UNPREFIXED — the
                                # unified v1 prefix double-prefixed every route
                                # (/api/v1/integrations/discord/api/discord/…)
                                # and 404'd the real surface. Mirrors slack's
                                # root handling (line ~1272).
                                prefix = ""
                            else:
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
        from api.admin.system_health_routes import router as system_health_router
        from api.user_management_routes import router as user_mgmt_router

        # Both routers define their own in-router prefixes (/api/users,
        # /api/admin/health). Do not add an include prefix — that doubles
        # the path (e.g. /api/v1/api/users/me).
        app.include_router(user_mgmt_router)
        app.include_router(system_health_router)

        # Note: Integrations catalog router is mounted later (L~2492) in its
        # own try/except block with the proper import. It was previously
        # referenced here before import, causing a NameError on boot.

        # OAuth Status and Authorization Endpoints
        try:
            from oauth_status_routes import router as oauth_status_router
            app.include_router(oauth_status_router)
            logger.info("✓ OAuth Status and Authorization Routes Loaded")
        except Exception as e:
            logger.error(f"Failed to load OAuth status routes: {e}")

        # Integration Registry API (Capability Discovery)


        # Capability Schema API

        # UI Components API (Dynamic Component Resolution)
    except (ImportError, TypeError) as e:
        logger.error(f"Failed to load Core API routes: {e}")

    # 2. Workflow Engine
    # Unified Chat Routes (Telegram & Slack)
    try:
        from integrations.telegram_chat_routes import router as telegram_chat_router

        app.include_router(telegram_chat_router)
        logger.info("✓ Telegram Chat Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Telegram chat routes: {e}")

    try:
        from integrations.slack_chat_routes import router as slack_chat_router

        app.include_router(slack_chat_router)
        logger.info("✓ Slack Chat Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Slack chat routes: {e}")

    # Mobile / Operations / Tools / LINE routers. These declare their own
    # /api/* prefixes and real auth deps but were never mounted — every route
    # 404'd in prod while their api-wave tests mounted them manually.
    try:
        from api.mobile_workflows import router as mobile_workflows_router

        app.include_router(mobile_workflows_router)
        logger.info("✓ Mobile Workflows Routes Loaded at /api/mobile/workflows")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load mobile workflows routes: {e}")

    try:
        from api.operations_api import router as operations_router

        app.include_router(operations_router)
        logger.info("✓ Operations Routes Loaded at /api/operations")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load operations routes: {e}")

    try:
        from api.tools import router as tools_router

        app.include_router(tools_router)
        logger.info("✓ Tools Routes Loaded at /api/tools")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load tools routes: {e}")

    try:
        from api.line_routes import router as line_router

        app.include_router(line_router)
        logger.info("✓ LINE Routes Loaded at /api/line (auth-gated)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load LINE routes: {e}")

    # External Resource Routes (already consolidated in V1 block above)
    # Keeping block for future extensions
    pass

    # Desktop Authentication (Secure API Keys)
    try:

        logger.info("✅ Desktop authentication routes enabled (secure API keys)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load desktop auth routes (skipping): {e}")

    # AI Training Period Configuration
    # Training Analytics & Monitoring
    # Enhanced Feedback System (from upstream)
    try:
        from api.feedback_enhanced import router as feedback_enhanced_router

        app.include_router(feedback_enhanced_router, tags=["feedback"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load enhanced feedback routes (skipping): {e}")

    try:
        from api.feedback_analytics import router as feedback_analytics_router

        # Router declares NO in-router prefix (its paths are "/", "/agent/{agent_id}",
        # "/trends"), so the include MUST supply the documented /api/feedback/analytics
        # prefix — otherwise the routes land at bare "/", "/agent/{agent_id}", "/trends"
        # (shadowed by root) and every /api/feedback/analytics/* call 404s.
        app.include_router(
            feedback_analytics_router,
            prefix="/api/feedback/analytics",
            tags=["feedback-analytics"],
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load feedback analytics routes (skipping): {e}")

    # Feedback Phase 2: Promotions & Batch Operations
    try:
        from api.feedback_phase2 import router as feedback_phase2_router

        app.include_router(feedback_phase2_router, tags=["feedback-phase2"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load feedback phase 2 routes (skipping): {e}")

    try:
        from api.feedback_batch import router as feedback_batch_router

        app.include_router(feedback_batch_router, tags=["feedback-batch"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load feedback batch routes (skipping): {e}")

    # Deep Linking System (Phase 2)
    try:

        logger.info("✅ Deep linking system enabled")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load deeplinks routes (skipping): {e}")

    # NOTE: workflow_template_routes is mounted once at module level (see
    # workflow_template_router include above). Previously it was re-mounted
    # here with prefix="/api/workflow-templates", which combined with the
    # router's own in-router prefix to produce /api/workflow-templates/api/workflow-templates.

    # Distributed Debug System (Phase 1)
    try:

        logger.info("✅ Debug tenant check system enabled")
    except Exception as e:
        import traceback

        logger.error(f"CRITICAL: Failed to load debug tenant check routes: {e}")
        logger.error(traceback.format_exc())

    try:
        from api.notification_settings_routes import router as notification_router

        app.include_router(
            notification_router, prefix="/api/notification-settings", tags=["notification-settings"]
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load notification settings routes: {e}")

    # Notification Service Routes
    try:
        from core.analytics_endpoints import router as analytics_router

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

        logger.info("✓ Workflow Import/Export Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load workflow I/O routes: {e}")

    try:
        from api.background_agent_routes import router as background_router

        app.include_router(
            background_router, prefix="/api/background-agents", tags=["background-agents"]
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load background agent routes: {e}")

    try:
        from api.financial_ops_routes import router as financial_router

        app.include_router(financial_router, prefix="/api/financial", tags=["financial-ops"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load financial ops routes: {e}")

    # Governance Verification Routes (Phase 169-03)
    try:
        from api.routes.admin.governance_verification_routes import (
            router as governance_verification_router,
        )

        app.include_router(governance_verification_router)
        logger.info("✓ Governance Verification Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Governance Verification routes: {e}")

    # JIT Verification & Admin Governance Routes
    try:
        from api.admin.jit_verification_routes import router as jit_verification_router
        app.include_router(jit_verification_router)

        from api.admin.business_facts_routes import router as business_facts_router
        app.include_router(business_facts_router)

        from api.admin.skill_routes import router as admin_skill_router
        app.include_router(admin_skill_router)

        from api.admin.system_health_routes import router as admin_health_router
        app.include_router(admin_health_router)
        from api.admin.cache_routes import router as admin_cache_router
        app.include_router(admin_cache_router)

        logger.info("✓ JIT Verification & Admin Governance Routes Loaded")
    except Exception as e:
        logger.warning(f"Failed to load JIT Verification / Admin routes: {e}")

    # Phase P8 — Workspace-Scoped Curated Context (Cloudflare G8), admin-only.
    try:
        from api.workspace_context_routes import router as workspace_context_router

        app.include_router(workspace_context_router)
        logger.info("✓ Workspace Context Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Workspace Context routes: {e}")

    # Governance Manual Fact Entry Routes (Phase 167-05)
    try:

        logger.info("✓ Governance Manual Fact Entry Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Governance Manual Fact Entry routes: {e}")

    # Queue Monitoring Routes
    try:

        logger.info("✓ Queue Monitoring Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load queue monitoring routes: {e}")

    try:
        from api.evolution_routes import router as evolution_router

        app.include_router(evolution_router, prefix="/api/evolution", tags=["Evolution"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load evolution routes: {e}")

    # Auto-Dev review — supervisor surface for pending Memento skill
    # candidates / AlphaEvolver tool mutations and the tool-error patterns
    # that produced them (evolution harness journey, 2026-09-02).
    try:
        from api.autodev_review_routes import router as autodev_review_router

        app.include_router(autodev_review_router, tags=["Auto-Dev Review"])
        logger.info("✓ Auto-Dev Review Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load auto-dev review routes: {e}")

    # Canvas Skill Integration
    try:
        from api.canvas_skill_routes import router as canvas_skill_router

        app.include_router(canvas_skill_router, prefix="/api/v1", tags=["Canvas-Skill Integration"])
        logger.info("✓ Canvas Skill Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load canvas skill routes: {e}")

    # NOTE: api.admin.system_health_routes was already mounted earlier in the
    # main API try-block above. The duplicate mount here is removed.

    try:
        from api.admin.business_facts_routes import router as business_facts_router

        app.include_router(business_facts_router)
        logger.info("✓ Business Facts Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Business Facts routes: {e}")
    except Exception as e:
        logger.error(f"Error loading Business Facts routes: {e}")

    try:
        from api.routes.admin.paused_tasks_routes import scheduler_router

        app.include_router(scheduler_router)
        logger.info("✓ Paused Tasks Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Paused Tasks routes: {e}")
    except Exception as e:
        logger.error(f"Error loading Paused Tasks routes: {e}")

    try:

        logger.info("✓ Migration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Migration routes: {e}")
    except Exception as e:
        logger.error(f"Error loading Migration routes: {e}")

    try:

        logger.info("✓ Embedding Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Embedding routes: {e}")
    except Exception as e:
        logger.error(f"Error loading Embedding routes: {e}")

    try:
        from api.ai_accounting_routes import router as ai_accounting_router

        app.include_router(
            ai_accounting_router, prefix="/api/v1/accounting", tags=["ai-accounting"]
        )
        app.include_router(
            ai_accounting_router, prefix="/api/ai-accounting", tags=["ai-accounting"]
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load AI accounting routes: {e}", exc_info=True)

    try:
        from api.reconciliation_routes import router as reconciliation_router

        app.include_router(
            reconciliation_router, prefix="/api/v1/reconciliation", tags=["reconciliation"]
        )
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load reconciliation routes: {e}")

    try:
        from api.apar_routes import router as apar_router

        app.include_router(apar_router, prefix="/api/v1/apar", tags=["ap-ar"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load AP/AR routes: {e}", exc_info=True)

    try:
        from api.graphrag_routes import router as graphrag_router

        app.include_router(graphrag_router, prefix="/api/graphrag", tags=["graphrag"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load GraphRAG routes: {e}")

    try:
        from api.ontology_routes import router as ontology_router

        app.include_router(ontology_router, prefix="/api/ontology", tags=["ontology"])
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Ontology routes: {e}")

    try:
        from api.project_routes import router as projects_router

        app.include_router(projects_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Project routes: {e}")

    try:
        from api.intelligence_routes import router as intelligence_router

        app.include_router(intelligence_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Intelligence routes: {e}")

    try:

        # Double-mount tenant_router at /api/tenant and /api/v1/tenant
        # to ensure compatibility with all frontend/middleware paths

        logger.info("✓ Tenant Management Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load tenant routes: {e}")

    try:
        from api.routes.federation_routes import router as federation_router

        app.include_router(federation_router, prefix="/api")
        logger.info("✓ Federation Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Federation routes: {e}")

    # Local Model Provider Routes (Ollama, LM Studio, vLLM, custom)
    try:
        from api.routes.local_model_routes import router as local_model_router
        app.include_router(local_model_router)
        logger.info("✓ Local Model Routes Loaded (/api/local-models)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Local Model routes: {e}")

    try:
        from sales.routes import router as sales_router

        app.include_router(sales_router)
        from sales.deal_ingestion_routes import router as deal_ingestion_router

        app.include_router(deal_ingestion_router)

        from api.marketing_routes import router as marketing_router

        app.include_router(
            marketing_router, prefix="/api/marketing", tags=["Marketing Intelligence"]
        )

        logger.info("✓ Sales & Marketing Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load business intelligence routes: {e}")

    # NOTE: core.workflow_endpoints is already mounted at /api/v1/workflows
    # earlier in this module (live_workflow_router). This block previously
    # re-mounted it at /api/v1, duplicating every route. Removed.


    try:
        from api.skill_routes import router as skill_router

        app.include_router(skill_router)
        logger.info("✓ Skill Management & Execution Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load skill routes: {e}")

    try:
        from api.learn_routes import router as learn_router

        app.include_router(learn_router)
        logger.info("✓ Learn Routes Loaded (workflow→skill distillation)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load learn routes: {e}")

    try:
        from api.skill_routes import router as admin_skill_router

        app.include_router(admin_skill_router)
        logger.info("✓ Admin Skill & Evolution Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Admin Skill/Evolution routes: {e}", exc_info=True)

    # 3. Workflow UI (Visual Automations)
    # Eagerly load this to ensure 404s don't happen silently
    try:
        # Use consolidated path for visual automations
        from core.workflow_ui_endpoints import router as workflow_ui_router

        app.include_router(workflow_ui_router, prefix="/api/v1/workflow-ui", tags=["Workflow UI"])
        logger.info("✓ Workflow UI Endpoints Loaded")

        # 3a. Time-Travel fork route (restored; WorkflowAutomation calls it)
        try:
            from api.time_travel_routes import router as time_travel_router

            app.include_router(time_travel_router)
            logger.info("✓ Time-Travel Endpoints Loaded")
        except Exception as e:
            logger.error(f"CRITICAL: Time-Travel endpoints failed to load: {e}")
    except Exception as e:
        logger.error(f"CRITICAL: Workflow UI endpoints failed to load: {e}")
        # raise e # Uncomment to crash on startup if strict

    # 3b. AI Workflow Endpoints (Real NLU)
    try:
        from enhanced_ai_workflow_endpoints import router as ai_router

        app.include_router(ai_router)

        from ai_workflow_endpoints import router as ai_workflow_simple_router

        app.include_router(ai_workflow_simple_router)

        try:
            from api.routes.test_deployed_routes import main as test_main

            # test_deployed_routes is a script, not a router.
            # If it was intended to be a router, it needs a 'router' object.
        except (ImportError, TypeError) as e:
            logger.warning(f"Test deployed routes not found: {e}")

        from advanced_workflow_api import router as advanced_workflow_router

        app.include_router(advanced_workflow_router)


        from evidence_collection_api import router as evidence_router

        app.include_router(evidence_router)

        from core.enterprise_security import router as security_router

        app.include_router(security_router, prefix="/api/v1/security", tags=["Enterprise Security"])

        from core.team_messaging import router as messaging_router

        app.include_router(messaging_router)


        logger.info("✓ Messaging OAuth (BYOK) Routes Loaded")


        from integrations.outlook_routes import router as outlook_app_router
        app.include_router(outlook_app_router, prefix="/api/integrations/outlook", tags=["outlook"])
        logger.info("✓ Explicit Outlook Integration Routes Loaded at /api/integrations/outlook")

        # Legacy messaging routes replaced by batch 3 standardized routes

        from integrations.shopify_webhooks import router as shopify_wh_router

        app.include_router(shopify_wh_router)

        # Shopify REST API (products/blogs/articles/status + OAuth connect).
        # Mounted here (unconditional) so the connect flow and agent tools work
        # even when the webhook batch block below is skipped by a bad import.
        try:
            from integrations.shopify_routes import router as shopify_router

            app.include_router(shopify_router, tags=["Shopify"])
            logger.info("✓ Shopify REST routes loaded")
        except (ImportError, TypeError) as e:
            logger.warning(f"Shopify REST routes not found, skipping: {e}")

        from integrations.atom_communication_memory_webhooks import (
            atom_memory_webhooks_router,
        )

        app.include_router(
            atom_memory_webhooks_router,
            prefix="/api/memory/webhooks",
            tags=["Communication Memory Webhooks"],
        )

        from integrations.atom_communication_apps_lancedb_integration import (
            communication_ingestion_router,
        )

        app.include_router(communication_ingestion_router)

        try:
            from api.routes.integrations.razorpay_routes import razorpay_router

            app.include_router(razorpay_router, prefix="/api/v1/integrations/razorpay")
        except (ImportError, TypeError) as e:
            logger.warning(f"Razorpay routes not found, skipping: {e}")

        from integrations.onedrive_routes import onedrive_router

        app.include_router(onedrive_router, prefix="/api/v1/integrations/onedrive")

        from integrations.box_routes import router as box_router

        app.include_router(box_router, prefix="/api/v1/integrations/box", tags=["Box"])

        from integrations.google_drive_routes import google_drive_router

        app.include_router(
            google_drive_router, prefix="/api/v1/integrations/google-drive", tags=["Google Drive"]
        )

        from integrations.asana_routes import router as asana_router

        app.include_router(asana_router, prefix="/api/v1/integrations/asana")

        from integrations.slack_routes import router as slack_router

        app.include_router(slack_router, prefix="/api/v1/integrations/slack")

        from integrations.teams_routes import router as teams_router

        app.include_router(teams_router, prefix="/api/v1/integrations/teams")

        # telegram_routes declares its own /api/telegram prefix — the unified
        # v1 prefix here double-prefixed every route and shadowed nothing but
        # confusion. Root-mounted by the journey block (round 80b); the bogus
        # duplicate was removed in round 80i (mirrors discord, round 80d).

        # Legacy WhatsApp router removed - Consolidated into hardened router below

        from integrations.zendesk_routes import router as zendesk_router

        app.include_router(zendesk_router, prefix="/api/v1/integrations/zendesk")

        from integrations.github_routes import router as github_router

        app.include_router(github_router, prefix="/api/v1/integrations/github")

        from integrations.gmail_routes import router as gmail_router

        app.include_router(gmail_router, prefix="/api/v1/integrations/gmail")

        from integrations.salesforce_routes import router as salesforce_router

        app.include_router(salesforce_router, prefix="/api/v1/integrations/salesforce")

        # discord_routes declares its own /api/discord prefix — the unified v1
        # prefix here double-prefixed every route
        # (/api/v1/integrations/discord/api/discord/...) and 404'd the real
        # surface. It now auto-loads unprefixed via the middleware (round 80c).

        from integrations.trello_routes import router as trello_router

        app.include_router(trello_router, prefix="/api/v1/integrations/trello")

        from integrations.hubspot_routes import router as hubspot_router

        app.include_router(hubspot_router, prefix="/api/v1/integrations/hubspot")

        # Zoho Suite (Standardized). The router declares its own
        # /api/zoho-workdrive prefix — the Integrations hub probes
        # /api/zoho-workdrive/health through the next.config rewrite, so it
        # must be mounted there. Re-prefixing it under /api/v1/integrations
        # produced a double-prefixed path that nothing could reach.
        from api.zoho_workdrive_routes import router as zoho_router

        app.include_router(zoho_router)

        from integrations.zoho_crm_routes import router as zoho_crm_router

        app.include_router(zoho_crm_router)

        from integrations.zoho_books_routes import router as zoho_books_router

        app.include_router(zoho_books_router)

        from integrations.zoho_inventory_routes import router as zoho_inventory_router

        app.include_router(zoho_inventory_router)

        from integrations.zoho_projects_routes import router as zoho_projects_router

        app.include_router(zoho_projects_router)

        from integrations.zoho_mail_routes import router as zoho_mail_router

        app.include_router(zoho_mail_router)

        # Zoho Forms + Zoho Flow: webhook-push apps (no public read API —
        # see integrations/zoho_forms_service.py). These routers declare no
        # prefix of their own, so the mount path below is the full path:
        # /health, /capabilities, readback, and (Forms) the ingestion
        # webhook under /api/v1/integrations/zoho-forms/webhook.
        from integrations.zoho_forms_routes import router as zoho_forms_router

        app.include_router(zoho_forms_router, prefix="/api/v1/integrations/zoho-forms")

        from integrations.zoho_flow_routes import router as zoho_flow_router

        app.include_router(zoho_flow_router, prefix="/api/v1/integrations/zoho-flow")

        # HR Integrations
        try:
            from api.routes.integrations.sagehr_routes import sagehr_router

            app.include_router(sagehr_router, prefix="/api/v1/integrations/sagehr")
        except (ImportError, TypeError) as e:
            logger.warning(f"SageHR routes not found, skipping: {e}")

        # Batch 2 Integrations
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
        from api.auth_routes import router as auth_router

        app.include_router(auth_router)  # Already has prefix="/api/auth"
    except (ImportError, TypeError) as e:
        logger.warning(f"Auth endpoints not found, skipping: {e}")

    try:
        from api.user_management_routes import router as admin_user_management_router
        from api.admin_routes import router as admin_router
        from api.admin.budget_routes import router as admin_budget_router

        app.include_router(admin_router)
        app.include_router(admin_user_management_router)
        app.include_router(admin_budget_router)
        logger.info("✓ Admin Routes Loaded")
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to load Admin Routes: {e}", exc_info=True)
        # We want to see this error!

    try:
        # 4a. 2FA Routes
        from api.auth_2fa_routes import router as auth_2fa_router

        app.include_router(auth_2fa_router)  # Already has prefix="/api/auth/2fa"
        logger.info("✓ 2FA Routes Loaded")
    except (ImportError, TypeError):
        logger.warning("2FA routes not found, skipping.")

    # 4b. Onboarding Routes
    try:
        from api.onboarding_routes import router as onboarding_router

        # Router already declares prefix="/api/onboarding" — passing the same
        # prefix here double-mounted every route under
        # /api/onboarding/api/onboarding/* (the wizard's fetches 404'd).
        app.include_router(onboarding_router, tags=["Onboarding"])
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
        from api.reasoning_routes import router as reasoning_router

        app.include_router(reasoning_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Reasoning routes not found: {e}")

    # 5. OAuth (Critical for login)
    # 4. WebSockets (Real-time features)
    try:
        from api.websocket_routes import router as ws_router

        app.include_router(ws_router, tags=["WebSockets"])
    except (ImportError, TypeError):
        logger.warning("WebSocket routes not found, skipping.")

    # 4b. ACP bridge — standard Agent Client Protocol v1 endpoint so any
    # ACP-compatible client (Zed, Berd-style shells) can drive Atom agents.
    try:
        from api.acp_routes import router as acp_router

        app.include_router(acp_router, tags=["ACP"])
        logger.info("✓ ACP bridge mounted at /acp/ws")
    except (ImportError, TypeError) as e:
        logger.warning(f"ACP bridge not mounted: {e}")

    # 4c. A2A — Agent Card discovery + JSON-RPC message/send so external
    # agents can discover and delegate to Atom agents (A2A protocol baseline).
    try:
        from api.a2a_routes import router as a2a_router

        app.include_router(a2a_router, tags=["A2A"])
        logger.info("✓ A2A endpoint mounted at /api/a2 (+ /.well-known/agent-card.json)")
    except (ImportError, TypeError) as e:
        logger.warning(f"A2A endpoint not mounted: {e}")

    # 4d. OIDC SSO — authorization-code login against an enterprise IdP.
    try:
        from api.sso_oidc_routes import router as sso_oidc_router

        app.include_router(sso_oidc_router, tags=["SSO"])
        logger.info("✓ OIDC SSO mounted at /api/auth/sso/oidc")
    except (ImportError, TypeError) as e:
        logger.warning(f"OIDC SSO not mounted: {e}")

    # 4d-bis. SCIM v2 — user provisioning for enterprise IdPs (Okta/Entra).
    try:
        from api.scim_routes import install_scim_exception_handlers, router as scim_router

        app.include_router(scim_router, tags=["SCIM"])
        install_scim_exception_handlers(app)
        logger.info("✓ SCIM v2 mounted at /api/scim/v2")
    except (ImportError, TypeError) as e:
        logger.warning(f"SCIM v2 not mounted: {e}")

    # 4d-ter. Observability — span tracing + optional Langfuse export.
    try:
        from api.observability_routes import router as observability_router

        app.include_router(observability_router, tags=["Observability"])
        logger.info("✓ Observability mounted at /api/observability")
    except (ImportError, TypeError) as e:
        logger.warning(f"Observability not mounted: {e}")

    # 4e. BambooHR + Twitter/X integrations.
    try:
        from integrations.bamboohr_routes import router as bamboohr_router

        app.include_router(bamboohr_router, tags=["BambooHR"])
        logger.info("✓ BambooHR integration mounted at /api/bamboohr")
    except (ImportError, TypeError) as e:
        logger.warning(f"BambooHR integration not mounted: {e}")
    try:
        from integrations.twitter_routes import router as twitter_router

        app.include_router(twitter_router, tags=["Twitter"])
        logger.info("✓ Twitter/X integration mounted at /api/twitter")
    except (ImportError, TypeError) as e:
        logger.warning(f"Twitter/X integration not mounted: {e}")

    # 6. MCP Routes (Web Search & Web Access for Agents)
    try:
        from integrations.mcp_routes import router as mcp_router

        app.include_router(mcp_router, tags=["MCP"])
        logger.info("✓ MCP Routes Loaded")

    except (ImportError, TypeError) as e:
        logger.warning(f"MCP/Zoho routes not found: {e}")

    # 7. Supervision System Routes (NEW)
    try:

        logger.info("✓ Availability Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Availability routes: {e}", exc_info=True)

    try:

        logger.info("✓ Proposal Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Proposal routes: {e}")

    try:

        logger.info("✓ Supervision-Learning Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Failed to load Supervision-Learning routes: {e}")

    try:
        from api.integrations_catalog_routes import router as catalog_router

        app.include_router(catalog_router)
        logger.info("✓ Integrations Catalog Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Integrations catalog routes not found: {e}")

    try:
        from api.dynamic_options_routes import router as dynamic_options_router

        app.include_router(dynamic_options_router)
        logger.info("✓ Dynamic Options Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Dynamic options routes not found: {e}")

    # Webhook Routes (New Native Webhooks)
    try:
        from api.webhook_routes import router as webhook_router

        app.include_router(webhook_router)
        logger.info("✓ Webhook Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Webhook routes not found: {e}")

    # Legacy /api/billing/webhook alias — intentionally NOT registered.
    # It referenced api/routes/stripe_webhook_routes.py, which no longer exists:
    # Stripe webhook processing was removed (integrations.stripe_routes is now a
    # health/capabilities stub, see tests/payment_integration/test_webhook_processing.py).
    # The prior import was silently swallowed by except ImportError while still
    # logging "✓ Loaded", implying a live surface that was actually a 404.
    # Leaving it unregistered keeps the endpoint fail-closed (404).

    try:
        from integrations.universal.routes import router as universal_auth_router

        app.include_router(universal_auth_router)
        logger.info("✓ Universal Auth Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Universal auth routes not found: {e}")

    try:

        logger.info("✓ Meta Compliance Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Meta compliance routes not found: {e}")

    # WhatsApp Handlers (Consolidated Hardened Flow)
    try:
        from integrations.whatsapp_fastapi_routes import router as whatsapp_oauth_router
        from api.routes.webhooks.whatsapp_webhooks import router as whatsapp_webhook_router

        app.include_router(
            whatsapp_webhook_router, prefix="/api/v1/webhooks", tags=["whatsapp-webhooks"]
        )
        app.include_router(whatsapp_oauth_router, prefix="/api/v1/integrations/whatsapp")

        logger.info("✓ Consolidated Hardened WhatsApp Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Hardened WhatsApp routes not found: {e}")

    try:
        from integrations.bridge.external_integration_routes import router as ext_router

        app.include_router(ext_router)
        logger.info("✓ External Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"External integration bridge routes not found: {e}")

    # Register Connection routes
    try:
        from api.connection_routes import router as conn_router

        app.include_router(conn_router)
        logger.info("✓ Connection Management Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Connection routes not found: {e}")

    # Register real per-integration connection status (Integrations page —
    # DB connections + tenant connectors + env credentials, no health fakes)
    try:
        from api.integration_status_routes import router as integ_status_router

        app.include_router(integ_status_router)
        logger.info("✓ Integration Status Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Integration status routes not found: {e}")

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
        from api.agent_governance_routes import router as gov_router

        app.include_router(gov_router)
        logger.info("✓ Agent Governance Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Agent Governance routes not found: {e}")

    # 8a. Agent Maturity Journey Routes (R81) — training proposals/sessions
    # (STUDENT→INTERN) + action-proposal review/execute (INTERN HITL). The
    # original /api/maturity surface was archived with zero replacements,
    # severing training approval → confidence boost → promotion.
    try:
        from api.agent_maturity_routes import router as maturity_router

        app.include_router(maturity_router)
        logger.info("✓ Agent Maturity Journey Routes Loaded (/api/maturity)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Agent Maturity Journey routes not found: {e}")

    # 8b. HITL approvals / graduation exams: no dedicated routers exist.
    # R82: these blocks previously logged "✓ ... Loaded" while mounting
    # nothing (empty try bodies) — an audit trap during journey tracing.
    # Real surfaces: HITL approvals live under /api/agents/approvals/* and
    # /api/agent-governance/*; graduation exams under /api/episodes/graduation/*.

    # 8c. Protection & Security Routes
    try:
        from api.protection_api import router as protection_router

        app.include_router(protection_router)
        logger.info("✓ Protection API Routes Loaded (Skill Scanner)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Protection API routes not found: {e}")

    # 8d. User Preferences & Multimodal Chat
    try:
        from core.user_preference_routes import router as user_pref_router

        app.include_router(user_pref_router, prefix="/api/v1/preferences")
        logger.info("✓ User Preference Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"User preference routes failed to load: {e}")

    # Round 83 audit-trap cleanup: the previous empty try-blocks here logged
    # "✓ Multimodal Chat / Canvas Browser / Canvas Action / Canvas Context
    # Routes Loaded" while mounting NOTHING (and the Multimodal block carried
    # a duplicated except clause). Removed — a mount that mounts nothing must
    # not log success. The real surfaces are: chat via /api/chat/*, canvas
    # CRUD/context/history via /api/canvas/*, terminal/coding/docs/sheets via
    # their dedicated routers below.
    # 8b. Universal Canvas Routes (Terminal, Browser, Desktop Automation)
    try:
        from api.canvas_terminal_routes import router as canvas_terminal_router

        app.include_router(canvas_terminal_router)
        logger.info("✓ Canvas Terminal Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas terminal routes not found: {e}")

    try:
        from api.browser_routes import router as browser_router

        app.include_router(browser_router)
        logger.info("✓ Browser Automation Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Browser automation routes not found: {e}")

    # Device Capabilities Routes (Hardware Access) — camera, screen,
    # location, notifications, command execution. Restored after 8e9b2d934
    # removed the mount while the browser router mount was later re-added.
    try:
        from api.device_capabilities import router as device_router

        app.include_router(device_router)
        logger.info("✓ Device Capabilities Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Device capabilities routes not found: {e}")

    # (Canvas Browser/Action/Context audit traps removed — see note above.)

    try:
        from api.canvas_recording_routes import router as canvas_recording_router

        app.include_router(canvas_recording_router)
        logger.info("✓ Canvas Recording Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas recording routes not found: {e}")

    try:
        # Autonomy policy: which action topics always require a human in the
        # loop vs. agent-autonomous-if-mature (canvas page Autonomy panel).
        from api.autonomy_routes import router as autonomy_router

        app.include_router(autonomy_router)
        logger.info("✓ Autonomy Routes Loaded (action HITL policy)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Autonomy routes not found: {e}")

    try:
        # Round 80f: meeting attendance had a real frontend consumer
        # (pages/api/meeting_attendance_status/[taskId].ts proxies
        # /api/meetings/attendance/{taskId}) but the router was never
        # mounted — the journey 404'd end-to-end. Fully auth-gated.
        from api.meeting_routes import router as meeting_router

        app.include_router(meeting_router)
        logger.info("✓ Meeting Routes Loaded (attendance tracking)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Meeting routes not found: {e}")

    # --- PORTED FEATURES ---
    try:
        from api.canvas_routes import router as canvas_router

        app.include_router(canvas_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas routes not found: {e}")

    # Custom Canvas Components (HTML/CSS/JS) with governance + security validation
    try:
        from api.custom_components import router as custom_components_router

        app.include_router(custom_components_router)
        logger.info("✓ Custom Components Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Custom components routes not found: {e}")

    try:
        from api.canvas_coding_routes import router as canvas_coding_router

        app.include_router(canvas_coding_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas coding routes not found: {e}")

    try:
        from api.canvas_docs_routes import router as canvas_docs_router

        app.include_router(canvas_docs_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas docs routes not found: {e}")

    try:
        from api.canvas_sheets_routes import router as canvas_sheets_router

        app.include_router(canvas_sheets_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas sheets routes not found: {e}")

    try:
        from api.canvas_email_routes import router as canvas_email_router

        app.include_router(canvas_email_router)
        logger.info("✓ Canvas Email Routes Loaded (/api/canvas/email)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas email routes not found: {e}")

    try:
        from api.canvas_pdf_routes import router as canvas_pdf_router

        app.include_router(canvas_pdf_router)
        logger.info("✓ Canvas PDF Routes Loaded (/api/canvas/pdf)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Canvas pdf routes not found: {e}")

    try:
        from api.installation_profile_routes import router as installation_profile_router

        app.include_router(installation_profile_router)
        logger.info("✓ Installation Profile Routes Loaded (/api/installation)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Installation profile routes not found: {e}")

    try:
        from api.playbook_routes import router as playbook_router

        app.include_router(playbook_router)
        logger.info("✓ Playbook Routes Loaded (/api/playbooks)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Playbook routes not found: {e}")

    try:
        from api.agent_control_routes import router as agent_control_router

        app.include_router(agent_control_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Agent control routes not found: {e}")

    try:
        from api.analytics_dashboard_routes import router as analytics_dashboard_router

        # Backward compatibility for analytics/dashboard if moved
        app.include_router(analytics_dashboard_router)
    except (ImportError, TypeError) as e:

        logger.warning(f"Analytics dashboard routes not found: {e}")

    # Analytics dashboard endpoints (KPIs, timeline, etc.) — BUG-055: the
    # /api/analytics/dashboard/kpis route lived in analytics_dashboard_endpoints.py
    # which was never registered, so the Analytics page 404'd on load.
    try:
        from api.analytics_dashboard_endpoints import router as analytics_endpoints_router

        app.include_router(analytics_endpoints_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Analytics dashboard endpoints not found: {e}")
        logger.warning(f"Analytics dashboard routes not found: {e}")

    try:
        # Usage analytics routes already have prefix in router definition
        logger.info("✓ Usage Analytics Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Usage analytics routes not found: {e}")

    try:
        from api.dashboard_data_routes import router as dashboard_router

        app.include_router(dashboard_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Dashboard data routes not found: {e}")

    try:
        from api.agent_guidance_routes import router as agent_guidance_router

        app.include_router(agent_guidance_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Agent guidance routes not found: {e}")

    try:
        from api.health_monitoring_routes import router as health_monitoring_router

        app.include_router(health_monitoring_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Health monitoring routes not found: {e}")

    try:
        from api.health_routes import router as health_router

        app.include_router(health_router)
        logger.info("✓ Health Monitoring Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Health monitoring routes not found: {e}")

    try:
        from api.project_health_routes import router as project_health_router

        app.include_router(project_health_router)
    except (ImportError, TypeError) as e:
        logger.warning(f"Project health routes not found: {e}")

    logger.info("✓ Ported Features (Canvas/Agent) Processing Complete")

    # 8b. Governance Analytics & Remediation (Phase 10)
    try:

        logger.info("✓ Governance Analytics & Remediation Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Governance Analytics routes not found: {e}")

    # 9. Memory/Document Routes
    try:
        from api.memory_routes import router as memory_router

        app.include_router(memory_router, prefix="/api/v1/memory", tags=["Memory"])
        logger.info("✓ Memory Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Memory routes not found: {e}")

    # 9b. Memory Management Routes (Consolidation, Archival, Recovery)
    try:

        logger.info("✓ Memory Management Routes Loaded (Consolidation, Archival, Recovery)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Memory Management routes not found: {e}")

    # 9c. Memory Add-on Routes (Stripe Billing)
    try:

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

        from api.document_ingestion_routes import router as doc_ingest_router

        app.include_router(doc_ingest_router)  # Prefix defined in router

        from api.data_ingestion_routes import router as data_ingest_router

        app.include_router(data_ingest_router)  # Prefix defined in router

        logger.info("✓ Document & Data Ingestion Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Ingestion routes not found: {e}")

    # 11b. Document Hub Routes
    try:
        from api.document_routes import router as doc_hub_router
        app.include_router(doc_hub_router)
        logger.info("✓ Document Hub Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Document Hub routes not found: {e}")

    # 11c. Experience Marketplace Routes
    try:
        from api.experience_marketplace_routes import router as experience_marketplace_router

        app.include_router(experience_marketplace_router)  # Prefix defined in router
        logger.info("✓ Experience Marketplace Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Experience Marketplace routes not found: {e}")

    # 12. Formula Routes
    # Formulas loaded via ESSENTIAL_INTEGRATIONS

    # 13. Test Routes (Internal only, for E2E)
    try:

        logger.info("✓ Test Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.error(f"Test routes NOT available: {e}", exc_info=True)

    # 13. AI Workflows Routes (NLU Parse, Completion)
    try:
        from api.ai_workflows_routes import router as ai_wf_router

        app.include_router(ai_wf_router, tags=["AI Workflows"])
        logger.info("✓ AI Workflows Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"AI Workflows routes not found: {e}")

    # 14. Background Agent Routes
    try:
        from api.background_agent_routes import router as bg_agent_router

        app.include_router(bg_agent_router, tags=["Background Agents"])
        logger.info("✓ Background Agent Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Background Agent routes not found: {e}")

    # 15. Integration Data Routes (production implementations)
    try:
        # PDF Processing
        from integrations.pdf_processing.pdf_ocr_routes import router as pdf_ocr_router

        app.include_router(pdf_ocr_router)
        from integrations.pdf_processing.pdf_memory_routes import (
            router as pdf_memory_router,
        )

        app.include_router(pdf_memory_router)

        try:
            from api.routes.integrations.integration_data_routes import (
                router as integration_data_router,
            )

            app.include_router(integration_data_router, tags=["Integration Data"])
        except (ImportError, TypeError) as e:
            logger.warning(f"Integration Data routes not found, skipping: {e}")
        logger.info("✓ Integration Data Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Integration Data Routes not found: {e}")

    # 15.1. Integration Health Stubs
    try:
        from integration_health_endpoints import router as health_stubs_router
        app.include_router(health_stubs_router, tags=["Integration Health"])

        from service_health_endpoints import router as service_health_router
        app.include_router(service_health_router, tags=["Service Health"])

        # Legacy Health stubs
        from api_legacy_health import router as legacy_health_router
        app.include_router(legacy_health_router, prefix="/api", tags=["Legacy Health"])

        logger.info("✓ Integration & Service Health Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Integration Health routes not found: {e}")

    # 15.2. Historical Sync Routes
    try:
        from integrations.historical_sync_routes import router as historical_sync_router

        app.include_router(historical_sync_router, tags=["Historical Sync"])
        logger.info("✓ Historical Sync Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Historical Sync Routes not found: {e}")

    # 15.3. Worker Routes (Background job processing health checks)
    try:

        logger.info("✓ Worker Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Worker Routes not found: {e}")

    # 15.2 Collaborative Canvas Routes (Component marketplace, multi-agent coordination)
    try:

        logger.info("✓ Component Marketplace Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Component marketplace routes not found: {e}")

    try:
        from api.agent_coordination_routes import router as agent_coordination_router

        app.include_router(agent_coordination_router, prefix="", tags=["Agent Coordination"])
        logger.info("✓ Agent Coordination Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Agent coordination routes not found: {e}")

    # Canvas Marketplace & Canvas-Skill Integration Routes
    # NOTE: api.canvas_skill_routes is already mounted at /api/v1/canvas-skills
    # above. Removed the duplicate bare mount here.

    # OpenClaw Skill Integration Routes (Phase 42)
    try:

        logger.info("✓ OpenClaw Skill Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"OpenClaw skill integration routes not found: {e}")

    # OpenClaw Scan Integration Routes (Phase 43)
    try:

        logger.info("✓ OpenClaw Scan Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"OpenClaw scan integration routes not found: {e}")

    # OpenClaw Governance Integration Routes (Phase 45)
    try:

        logger.info("✓ OpenClaw Governance Integration Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"OpenClaw governance integration routes not found: {e}")

    # Skill Composition Routes (Phase 60)
    try:

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
        from integrations.atom_communication_live_api import (
            router as comm_live_router,
        )
        from integrations.atom_finance_live_api import router as finance_live_router
        from integrations.atom_projects_live_api import router as projects_live_router
        from integrations.atom_sales_live_api import router as sales_live_router

        app.include_router(comm_live_router)
        app.include_router(sales_live_router)
        app.include_router(projects_live_router)
        app.include_router(finance_live_router)
        logger.info("✓ Live Command Center APIs Loaded (Comm, Sales, Projects, Finance)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Live Command Center APIs not found: {e}")

    # 17. External Scheduler Routes (Upstash QStash)
    try:

        logger.info("✓ Scheduler Routes Loaded (QStash Ready)")
    except (ImportError, TypeError) as e:
        logger.warning(f"Scheduler routes not found: {e}")

    # 18. Desktop Bridge Routes (Cloud Brain to Local Hands)
    logger.debug("Attempting to import desktop_routes")
    try:

        logger.debug("Desktop routes imported, including router")
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
        from api.satellite_routes import router as satellite_router

        app.include_router(satellite_router)
        logger.info("✓ Satellite Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Satellite routes not found: {e}")

    # 19b. Mobile Routes (Remote Control)
    try:

        logger.info("✓ Mobile Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Mobile routes not found: {e}")

    # 19c. Integration Canvas Routes
    # 20. User Invitation Routes (Phase 23)
    try:

        logger.info("✓ Invitation Routes Loaded")
    except Exception as e:
        logger.warning(f"Invitation routes failed to load: {e}")

    try:

        logger.info("✓ Support Ticketing Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Support routes not found: {e}")

    try:

        logger.info("✓ Bug Triage Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Bug triage routes not found: {e}")

    # 20c. Communication Hub Routes
    try:

        logger.info("✓ Communication Hub Routes Loaded")

    except (ImportError, TypeError) as e:
        logger.warning(f"Communication Hub routes not found: {e}")

    # 20e. Universal Communication Routes (New)
    try:

        logger.info("✓ Universal Communication Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Universal Communication routes not found: {e}")

    # 20d. Document Hub Routes (Phase 39)
    try:

        logger.info("✓ Document Hub Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Document Hub routes not found: {e}")

    # 20b. Admin Retention Routes (Phase 73)
    try:

        logger.info("✓ Admin Retention Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Admin retention routes not found: {e}")

    # 21. Billing Routes (Phase 25)
    try:

        logger.info("✓ Billing Routes Loaded")
    except Exception as e:
        logger.warning(f"Billing routes failed to load: {e}")

    # 21a. Public Pricing Routes (reads Stripe env vars at runtime)
    try:

        logger.info("✓ Public Pricing Routes Loaded")
    except Exception as e:
        logger.warning(f"Public pricing routes failed to load: {e}")

    # 22. Social Media Routes (Week 2-3)
    try:
        from api.social_media_routes import router as social_media_router

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


        logger.info("✓ Audit Log Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Audit routes not found: {e}")

    # 22. Shell Security Routes (Phase 40)
    try:

        logger.info("✓ Shell Security Routes Loaded")
    except Exception as e:
        logger.warning(f"Shell security routes failed to load: {e}")

    # 23. Consolidated Core Routes (Phase 2)
    try:
        # These are already included above, removing duplicates to prevent conflicts
        # from api.project_routes import router as project_routes_router
        from api.intelligence_routes import router as intelligence_routes_router

        # from sales.routes import router as sales_routes_router
        from api.marketing_routes import router as marketing_routes_router
        from api.memory_routes import router as memory_routes_router
        from api.skill_routes import router as skill_routes_router

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
        from api.byok_routes import router as byok_router

        app.include_router(byok_router, tags=["BYOK"])
        logger.info("✓ BYOK API Routes Loaded")
    except Exception as e:
        logger.warning(f"BYOK API routes failed to load: {e}")

    # 24b. LLM Gateway Routes (Phase A — OpenAI/Anthropic-compatible surface).
    # Guarded so a gateway import failure never blocks the whole app.
    try:
        from api.openai_gateway_routes import router as gateway_router
        from api.gateway_key_routes import router as gateway_key_router
        from api.gateway_log_routes import router as gateway_log_router
        from api.llm_oauth_routes import router as llm_oauth_router

        app.include_router(gateway_router, tags=["LLM Gateway"])
        app.include_router(gateway_key_router, tags=["LLM Gateway Keys"])
        app.include_router(gateway_log_router, tags=["LLM Gateway Logs"])
        app.include_router(llm_oauth_router, tags=["LLM OAuth"])
        logger.info("✓ LLM Gateway Routes Loaded")
    except Exception as e:
        logger.warning(f"LLM Gateway routes failed to load: {e}")

    # 24c. MCP Server Routes (Model Context Protocol — exposes routing,
    # compression, governance as MCP tools for external AI agents).
    try:
        from api.mcp_server_routes import router as mcp_router
        app.include_router(mcp_router, tags=["MCP Server"])
        logger.info("✓ MCP Server Routes Loaded")
    except Exception as e:
        logger.warning(f"MCP Server routes failed to load: {e}")

    # 25. SSO API Routes (Phase 76)
    try:

        logger.info("✓ SSO API Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"SSO routes not found: {e}")

    # 24. Feature Flag Routes (Phase 37)
    try:

        logger.info("✓ Feature Flag Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Feature flag routes not found: {e}")

    # 25. Sandbox Execution Routes (Phase 44)
    try:

        logger.info("✓ Sandbox Execution Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"Sandbox execution routes failed to load: {e}")

    # 26. External API Routes (Phase 48)
    try:

        logger.info("✓ External API Routes Loaded")
    except (ImportError, TypeError) as e:
        logger.warning(f"External API routes failed to load: {e}")

    # 27. Entity Type Routes (Phase 171)
    try:
        from api.entity_type_routes import router as entity_type_router

        app.include_router(entity_type_router)
        logger.info("✓ Entity Type Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Entity type routes failed to load: {e}")

    # 28. Entity Query Routes (Phase 194)
    try:

        logger.info("✓ Entity Query Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Entity query routes failed to load: {e}")

    # 28.5. Entity Linking Routes (Phase 2: Automated Linking Agent)
    try:

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

        logger.info("✓ Entity Skill Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Entity skill routes failed to load: {e}")

    # 30. Agent Integration Routes (Phase 204)
    try:

        logger.info("✓ Agent Integration Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Entity skill routes failed to load: {e}")

    # 30. Meta Agent Routes (Phase 177)
    try:

        logger.info("✓ Meta Agent Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Meta agent routes failed to load: {e}")

    # 31. Admin Integration Catalog Routes (Phase 217)
    try:

        logger.info("✓ Admin Integration Catalog Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Admin integration catalog routes failed to load: {e}")

    # 32. Agent Capability Routes (Phase 222)
    # --- COMMERCIAL MARKETPLACE CONSOLIDATION (Phase 247) ---
    # 33. Domain Marketplace Routes (Phase 247)
    try:

        logger.info("✓ Domain Marketplace Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Domain marketplace routes failed to load: {e}")

    # 34. Agent-Domain Routes (Phase 247-11)
    try:

        logger.info("✓ Agent-Domain Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Agent-domain routes failed to load: {e}")

    # Agent Marketplace & Federation Routes
    try:
        # NOTE: federation routes are loaded at line ~2110 via
        # api.routes.federation_routes (prefix="/api"), not here.
        logger.info("✓ Agent Marketplace Routes Loaded")
    except Exception as e:
        logger.warning(f"Agent Marketplace routes failed to load: {e}")

    # 35. Domain-Aware Graduation Routes (Phase 247-14)
    try:

        logger.info("✓ Domain-Aware Graduation Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Domain-aware graduation routes failed to load: {e}")

    # 36. Capability Matrix Routes (Phase 247-14)
    try:

        logger.info("✓ Capability Matrix Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Capability matrix routes failed to load: {e}")

    # 37. Document Generation Routes (Phase 223)
    # 38. Learning & Adaptation Routes (Unified Learning System)
    try:
        from api.learning_routes import router as learning_router

        app.include_router(learning_router)
        logger.info("✓ Learning & Adaptation Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Learning routes failed to load: {e}")

    # 39. Stage Router Management Routes (automation + approval queue)
    try:
        from api.stage_router_routes import router as stage_router_mgmt_router

        app.include_router(stage_router_mgmt_router)
        logger.info("✓ Stage Router Management Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Stage router management routes failed to load: {e}")

    # 38b. Admin Runtime Settings Routes (env vars as UI admin settings)
    try:
        from api.admin_runtime_settings_routes import router as admin_settings_router

        app.include_router(admin_settings_router)
        logger.info("✓ Admin Runtime Settings Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Admin runtime settings routes failed to load: {e}")

    # 38c. BPE Workspace Admin Routes (agent-harness observability + management)
    try:
        from api.bpe_routes import router as bpe_admin_router

        app.include_router(bpe_admin_router)
        logger.info("✓ BPE Workspace Admin Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"BPE workspace admin routes failed to load: {e}")

    # 40. Fleet Router Management Routes (validation + approval queue)
    try:
        from api.fleet_router_routes import router as fleet_router_mgmt_router

        app.include_router(fleet_router_mgmt_router)
        logger.info("✓ Fleet Router Management Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Fleet router management routes failed to load: {e}")

    # 40b. Org-Politics Management Routes (consent-gated lifecycle automation)
    try:
        from api.org_politics_routes import router as org_politics_mgmt_router

        app.include_router(org_politics_mgmt_router)
        logger.info("✓ Org-Politics Management Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Org-politics management routes failed to load: {e}")

    # Start the consent-gated org-politics lifecycle loop (no-op when off).
    try:
        from core.org_politics_automation import ensure_automation_task

        ensure_automation_task()
        logger.info("✓ Org-Politics Automation Loop Scheduled (mode=%s)",
                    os.getenv("ATOM_ORG_AUTO_ENFORCE", "auto"))
    except Exception as e:
        logger.warning(f"Org-politics automation scheduling failed: {e}")

    # 41. Trust Calibration Gateway routes (R81l P0 spike — shadow-only,
    # flag-gated: ATOM_TRUST_CALIBRATION_ENABLED, default false -> 503)
    try:
        from api.trust_calibration_routes import router as trust_cal_router

        app.include_router(trust_cal_router)
        logger.info("✓ Trust Calibration Routes Loaded (shadow, flag-gated)")
    except (ImportError, NameError) as e:
        logger.warning(f"Trust calibration routes failed to load: {e}")

    # 41b. Ontology Draft Automation routes (consent-gated promotion of
    # auto-discovered entity types; mode off|notify|approve|auto, default auto)
    try:
        from api.ontology_draft_routes import router as ontology_draft_router

        app.include_router(ontology_draft_router)
        logger.info("✓ Ontology Draft Automation Routes Loaded")
    except (ImportError, NameError) as e:
        logger.warning(f"Ontology draft automation routes failed to load: {e}")

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
    from integrations.microsoft365_routes import microsoft365_router

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
async def get_all_integration_stats(current_user: User = Depends(get_current_user)):
    return await circuit_breaker.get_all_stats()


@app.post("/api/integrations/{integration_name}/reset")
async def reset_integration(integration_name: str, current_user: User = Depends(get_current_user)):
    circuit_breaker.reset(integration_name)
    return {"status": "reset", "integration": integration_name}


# ============================================================================
# DEBUG ENDPOINTS (For troubleshooting - remove in production)
# ============================================================================
try:


    # Debug endpoint for entity type diagnostics


    # Admin endpoint for entity type management

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
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        reload_enabled = os.getenv("RELOAD", "false").lower() in {"1", "true", "yes", "on"}
        if reload_enabled:
            uvicorn.run("main_api_app:app", host=host, port=port, reload=True, log_level="info")
        else:
            uvicorn.run(app, host=host, port=port, reload=False, log_level="info")
    except Exception as e:
        startup_logger.error(f"CRITICAL: Failed to start uvicorn: {e}")
        startup_logger.error(traceback.format_exc())
        sys.exit(1)
else:
    # When run as a module (e.g., python -m uvicorn main_api_app:app)
    # This branch won't execute, but the app object is created below
    pass
