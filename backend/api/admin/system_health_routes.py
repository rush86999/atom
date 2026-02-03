import logging
import time
from fastapi import APIRouter, Depends
from sqlalchemy import text

from core.admin_endpoints import get_super_admin
from core.cache import cache
from core.database import SessionLocal
from core.models import User

# Initialize cache service (use global)
# cache_service = RedisCacheService() # Removed

# Safe import for LanceDB
try:
    from core.lancedb_handler import LanceDBHandler
    HAS_LANCEDB = True
except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import LanceDBHandler: {e}")
    HAS_LANCEDB = False

router = APIRouter(tags=["Admin Health"])
logger = logging.getLogger(__name__)

# Hardcoded path to avoid prefix issues
@router.get("/api/admin/health")
def get_system_health(admin: User = Depends(get_super_admin)):
    """
    Real system health check for Admin Dashboard.
    Verifies connectivity to:
    1. Database (PostgreSQL/Neon)
    2. Cache (Redis/Upstash)
    3. Vector Store (LanceDB/R2)
    """
    
    # 1. Database Check
    db_status = "unknown"
    try:
        start = time.time()
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_time = time.time() - start
            db_status = "operational" if db_time < 2.0 else "degraded"
    except Exception as e:
        logger.error(f"Health Check DB Error: {e}")
        db_status = "degraded"

    # 2. Redis Check
    redis_status = "unknown"
    try:
        # Check if we have a redis client
        if cache.redis_client:
             if cache.redis_client.ping():
                 redis_status = "operational"
             else:
                 redis_status = "degraded"
        else:
             # Just check if it was supposed to be enabled
             if hasattr(cache, 'config') and cache.config.redis.enabled:
                  redis_status = "degraded" # Enabled but no client
             else:
                  redis_status = "unknown" # Not enabled
    except Exception as e:
        logger.error(f"Health Check Redis Error: {e}")
        redis_status = "degraded"

    # 3. Vector Store Check
    vector_status = "unknown"
    if HAS_LANCEDB:
        try:
            # Check default tenant storage
            handler = LanceDBHandler(tenant_id="default")
            res = handler.test_connection()
            if res.get("connected"):
                vector_status = "operational"
            else:
                vector_status = "degraded"
                logger.error(f"Health Check Vector Error: {res.get('message')}")
        except Exception as e:
            logger.error(f"Health Check Vector Exception: {e}")
            vector_status = "degraded"
    else:
        vector_status = "maintenance" # Import failed

    # Determine Overall Status
    overall_status = "healthy"
    if db_status != "operational":
        overall_status = "degraded"
    elif redis_status == "degraded" or vector_status == "degraded":
        overall_status = "degraded"

    return {
        "version": "2.1.0",
        "status": overall_status,
        "services": {
            "database": db_status,
            "redis": redis_status,
            "vector_store": vector_status
        },
        "timestamp": time.time()
    }
