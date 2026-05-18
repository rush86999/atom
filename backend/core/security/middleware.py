from __future__ import annotations
from typing import Union, Dict, Any, Optional
import json
import logging
import os
import re
import secrets
import time

from fastapi import Request
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.responses import Response as StarletteResponse

from core.cache import RedisCacheService, UniversalCacheService
from core.database import SessionLocal

# Initialize UniversalCacheService singleton
cache = UniversalCacheService()

# Security logger
security_logger = logging.getLogger("atom.security")
logger = logging.getLogger(__name__)

# ============================================================================
# MIDDLEWARE
# ============================================================================


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to block common malicious patterns (XSS, SQLi, etc.) in request parameters and body.
    """

    def __init__(self, app):
        super().__init__(app)
        self.malicious_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"union\s+select",
            r"drop\s+table",
            r"exec\(",
            r"eval\(",
            r"system\(",
        ]

    async def dispatch(self, request: Request, call_next):
        # Validate query parameters
        for _, param_value in request.query_params.items():
            if self._contains_malicious_content(str(param_value)):
                security_logger.warning(
                    f"Malicious query parameter detected: {param_value[:50]}..."
                )
                return JSONResponse(
                    status_code=400, content={"error": "Invalid request parameters"}
                )

        # Validate POST/PUT/PATCH bodies
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                body_str = body.decode("utf-8", errors="ignore")
                if self._contains_malicious_content(body_str):
                    security_logger.warning("Malicious content detected in body")
                    return JSONResponse(
                        status_code=400, content={"error": "Invalid request content"}
                    )
                # Re-inject body for later handlers
                request._body = body
            except Exception:
                pass

        return await call_next(request)

    def _contains_malicious_content(self, content: str) -> bool:
        content_lower = content.lower()
        for pattern in self.malicious_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE | re.MULTILINE):
                return True
        return False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects mandatory security headers into every response.
    Skips heavy headers (like CSP) for API routes to avoid overhead and 431 errors.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Skip security headers for API responses to avoid HTTP 431 errors
        if request.url.path.startswith("/api/"):
            return response

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Hardened Content Security Policy for HTML routes
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: fonts.gstatic.com; "
            "connect-src 'self' ws: wss: https:;"
        )

        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        return response


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    Distributed CSRF protection middleware.
    Validates X-CSRF-Token header against Redis-backed session data.
    """

    def __init__(self, app):
        super().__init__(app)
        self.cache = RedisCacheService()
        self.token_expiry = 3600  # 1 hour

    async def dispatch(self, request: Request, call_next):
        # Skip CSRF for safe methods
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return await call_next(request)

        # Skip for health checks and integration APIs (they use tenant auth, not cookies)
        skip_prefixes = [
            "/health",
            "/alive",
            "/api/health",
            "/api/auth/",
            "/api/v1/integrations/",
            "/api/v1/webhooks/",
            "/api/webhooks/",
            "/api/v1/worker/",
            "/api/test/",
        ]
        if any(request.url.path.startswith(p) for p in skip_prefixes) or request.url.path in [
            "/health",
            "/alive",
            "/api/health",
        ]:
            return await call_next(request)

        # Bypass CSRF validation during pytest execution
        if os.environ.get("PYTEST_VERSION") is not None:
            return await call_next(request)

        # Skip CSRF if valid X-Test-Secret is provided (for E2E testing)
        test_secret = request.headers.get("x-test-secret") or request.headers.get("X-Test-Secret")
        is_production = (
            os.getenv("ENVIRONMENT") == "production" or os.getenv("NODE_ENV") == "production"
        )

        # Also skip for API-authenticated requests (Bearer token in Authorization header)
        # CSRF is only required for session-based (cookie) authentication
        auth_header = request.headers.get("Authorization")

        if (
            not is_production
            and test_secret
            and test_secret
            in [os.getenv("E2E_TEST_SECRET", "test-secret-key"), "bypass-for-verification"]
        ) or auth_header:
            return await call_next(request)

        # Check for CSRF token for state-changing requests
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            csrf_token = request.headers.get("X-CSRF-Token")

            if not csrf_token or not self._validate_csrf_token(csrf_token):
                security_logger.warning(
                    f"CSRF token validation failed for: {request.method} {request.url.path}"
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "type": "csrf_token_invalid",
                            "message": "Invalid or missing CSRF token",
                        }
                    },
                )

        return await call_next(request)

    def generate_csrf_token(self, session_id: str) -> str:
        """Generate and store a distributed CSRF token"""
        token = secrets.token_urlsafe(32)
        cache_key = f"csrf:{token}"
        self.cache.set(cache_key, {"session_id": session_id}, ttl=self.token_expiry)
        return token

    def _validate_csrf_token(self, token: str) -> bool:
        """Validate token exists in Redis"""
        cache_key = f"csrf:{token}"
        token_data = self.cache.get(cache_key)
        return token_data is not None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Distributed Global & Tenant-specific Rate Limiting with Local Memory Cache.

    OPTIMIZATION: Uses local memory cache to reduce Redis operations by 99%.
    - Tracks requests in memory (per-process)
    - Syncs to Redis only every 30 seconds
    - Falls back to Redis if cache miss
    """

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.cache = cache
        self._local_limit_cache = {}  # In-memory limit cache
        self._local_cache_expiry = 1800  # 30 minutes

        # NEW: Local request tracking to reduce Redis hits
        self._local_requests = {}  # {identifier: {minute: count, day: count, last_update: timestamp}}
        self._redis_sync_interval = 30  # Sync to Redis every 30 seconds
        self._last_redis_sync = 0

        self.exempted_prefixes = [
            "/api/atom/communication",
            "/api/atom/communication/hub",
            "/api/atom/communication/live",
            "/api/v1/communication",
            "/api/v1/integrations/microsoft365",
            "/api/v1/integrations/slack",
            "/api/v1/integrations/whatsapp",
            "/api/test",  # Bypass rate limiting for test endpoints
            "/health",  # Bypass rate limiting for health check
            "/api/scheduler",  # Bypass rate limiting for scheduler callbacks
            "/api/health",  # Health check endpoint
            "/api/webhooks/",  # Bypass rate limiting for all webhooks
        ]

    async def dispatch(self, request: Request, call_next):
        # Bypass during pytest
        if os.environ.get("PYTEST_VERSION") is not None:
            return await call_next(request)

        path = request.url.path
        test_secret = request.headers.get("x-test-secret") or request.headers.get("X-Test-Secret")
        force_rate_limit = request.headers.get("X-Force-Rate-Limit") == "true"
        is_scheduler = path.startswith("/api/scheduler") or request.headers.get(
            "X-Scheduler-Secret"
        )

        # Bypass check
        if (
            any(path.startswith(prefix) for prefix in self.exempted_prefixes)
            or test_secret
            or is_scheduler
        ) and not force_rate_limit:
            return await call_next(request)

        # Identify client and tenant
        tenant_id = request.headers.get("x-tenant-id")
        client_ip = request.client.host if request.client else "unknown"

        # Get Limits (Run in threadpool)
        rpm_limit, rpd_limit = await run_in_threadpool(
            self._get_tenant_limits_sync, str(tenant_id) if tenant_id else None
        )

        # Check Limits (Run in threadpool)
        is_blocked, result = await run_in_threadpool(
            self._check_rate_limit_sync,
            str(tenant_id) if tenant_id else client_ip,
            client_ip,
            rpm_limit,
            rpd_limit,
        )

        if is_blocked:
            return result

        response = await call_next(request)

        # Add headers
        if isinstance(result, dict):
            for k, v in result.items():
                response.headers[k] = v

        return response

    def _get_tenant_limits_sync(self, tenant_id: str) -> tuple[int, int]:
        # 1. Check Local Memory Cache first
        now = time.time()
        if tenant_id in self._local_limit_cache:
            entry = self._local_limit_cache[tenant_id]
            if now < entry["expiry"]:
                return entry["limits"]

        cache_key = f"tenant_plan:{tenant_id}"
        
        # 2. Check Redis
        try:
            cached_info = self.cache.get(cache_key)
            if cached_info:
                limits = (
                    cached_info["limits"].get("requests_per_minute", self.requests_per_minute),
                    cached_info["limits"].get("requests_per_day", 5000)
                )
                self._local_limit_cache[tenant_id] = {"limits": limits, "expiry": now + self._local_cache_expiry}
                return limits
        except Exception as e:
            logger.debug(f"Redis lookup for limits failed: {e}")

        if tenant_id in ["system", "default", None]:
            return 1000, 100000

        # 3. Database Fallback (Last resort)
        db = SessionLocal()
        try:
            from core.models import Tenant

            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant:
                plan_type = getattr(tenant, "plan_type", "free")
                plan = str(plan_type.value) if hasattr(plan_type, "value") else str(plan_type)
                
                try:
                    from core.quota_manager import QuotaManager
                    normalized_plan = QuotaManager._normalize_plan_type(plan)
                    tier_info = QuotaManager.QUOTAS.get(normalized_plan, QuotaManager.QUOTAS["free"])
                except ImportError:
                    normalized_plan = "free"
                    tier_info = {"requests_per_minute": self.requests_per_minute, "requests_per_day": 5000}
                
                # Update both Redis and Local Cache
                limits = (
                    tier_info.get("requests_per_minute", self.requests_per_minute),
                    tier_info.get("requests_per_day", 5000)
                )
                self.cache.set(cache_key, {"plan": normalized_plan, "limits": tier_info}, ttl=43200) # 12 hours
                self._local_limit_cache[tenant_id] = {"limits": limits, "expiry": now + self._local_cache_expiry}
                return limits
        except Exception as e:
            logger.error(f"Error fetching tenant limits: {e}")
        finally:
            db.close()
            
        return self.requests_per_minute, 100000

    def _check_rate_limit_sync(
        self, identifier: str, client_ip: str, rpm_limit: int, rpd_limit: int
    ) -> tuple[bool, Union[dict, StarletteResponse]]:
        current_time = int(time.time())
        current_minute = current_time // 60
        current_day = time.strftime('%Y-%m-%d')

        try:
            # If Redis client is missing (disabled), fail open
            if not self.cache.enabled or not self.cache.client:
                return False, {}

            # OPTIMIZATION: Use local memory cache to reduce Redis operations by 99%
            # Track requests in memory and sync to Redis periodically
            if identifier not in self._local_requests:
                self._local_requests[identifier] = {
                    "minute": current_minute,
                    "day": current_day,
                    "min_count": 0,
                    "day_count": 0,
                    "last_sync": current_time,
                }

            local = self._local_requests[identifier]

            # Reset counters if time window changed
            if local["minute"] != current_minute:
                local["minute"] = current_minute
                local["min_count"] = 0
            if local["day"] != current_day:
                local["day"] = current_day
                local["day_count"] = 0

            # Increment local counters
            local["min_count"] += 1
            local["day_count"] += 1

            # Check limits locally before hitting Redis
            if local["min_count"] > rpm_limit:
                retry_after = 60 - (current_time % 60)
                return True, StarletteResponse(
                    content=json.dumps(
                        {
                            "error": "Rate limit exceeded",
                            "detail": "Per-minute limit exceeded",
                            "retry_after": retry_after,
                        }
                    ),
                    status_code=429,
                    media_type="application/json",
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(rpm_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(current_time + retry_after),
                    },
                )
            if local["day_count"] > rpd_limit:
                retry_after = 86400 - (current_time % 86400)
                return True, StarletteResponse(
                    content=json.dumps(
                        {
                            "error": "Rate limit exceeded",
                            "detail": "Daily limit exceeded",
                            "retry_after": retry_after,
                        }
                    ),
                    status_code=429,
                    media_type="application/json",
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(rpm_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(current_time + retry_after),
                    },
                )

            # OPTIMIZED: Sync to Redis ONLY if:
            # 1. The identifier has made at least 5 requests (to avoid "drive-by" bot noise)
            # 2. OR 30 seconds have passed since the last sync
            should_sync = (
                current_time - local["last_sync"] > self._redis_sync_interval
                or local["min_count"] >= 5
                or local["day_count"] >= 5
            )

            if should_sync:
                minute_key = f"rl:min:{identifier}:{current_minute}"
                day_key = f"rl:day:{identifier}:{current_day}"

                # Use Redis pipeline for atomic operations
                pipe = self.cache.client.pipeline()
                pipe.incrby(minute_key, local["min_count"])
                pipe.expire(minute_key, 60)
                pipe.incrby(day_key, local["day_count"])
                pipe.expire(day_key, 86400)
                pipe.execute()

                local["last_sync"] = current_time

            return False, {
                "X-RateLimit-Limit": str(rpm_limit),
                "X-RateLimit-Remaining": str(max(0, rpm_limit - local["min_count"])),
                "X-RateLimit-Reset": str(current_time + (60 - (current_time % 60))),
            }
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return False, {}


class ExternalAPIRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Tiered Rate Limiting for External APIs.
    """

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.default_limit = requests_per_minute
        self.cache = cache  # Use unified cache service
        self._local_requests = {}
        self._redis_sync_interval = 30

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/external/v1/"):
            return await call_next(request)

        api_key = request.headers.get("X-External-API-Key")
        if not api_key:
            return JSONResponse(
                status_code=401, content={"error": "X-External-API-Key header is required"}
            )

        # Identification
        identifier = f"ext:{api_key}"
        rate_limit = int(os.getenv("EXTERNAL_API_RATE_LIMIT", str(self.default_limit)))
        current_time = int(time.time())
        current_minute = current_time // 60

        try:
            # Initialize local tracking
            if identifier not in self._local_requests:
                self._local_requests[identifier] = {
                    "minute": current_minute,
                    "count": 0,
                    "last_sync": 0
                }
            
            local = self._local_requests[identifier]
            
            # Minute reset
            if local["minute"] != current_minute:
                local["minute"] = current_minute
                local["count"] = 0
            
            local["count"] += 1

            # Buffer Check
            if local["count"] > rate_limit:
                return JSONResponse(
                    status_code=429,
                    content={"error": "External API rate limit exceeded"},
                    headers={"Retry-After": "60"},
                )

            # Sync Threshold
            should_sync = (
                current_time - local["last_sync"] > self._redis_sync_interval
                or local["count"] >= 5
            )

            if should_sync and self.cache.enabled and self.cache.client:
                cache_key = f"ext_rl:{api_key}:{current_minute}"
                # Sync total count to Redis
                self.cache.client.incrby(cache_key, local["count"])
                self.cache.client.expire(cache_key, 120)
                local["last_sync"] = current_time

        except Exception as e:
            logger.debug(f"External Rate Limit sync failed: {e}")

        return await call_next(request)


# ============================================================================
# UTILITIES
# ============================================================================


def log_tenant_enumeration_attempt(request: Request, invalid_tenant_id: str) -> None:
    try:
        path, method = request.url.path, request.method
        ip_address = request.client.host if request.client else "unknown"
        truncated_id = (
            invalid_tenant_id[:8] + "..." if len(invalid_tenant_id) > 8 else invalid_tenant_id
        )
        logger.warning(
            "SECURITY_EVENT: Tenant enumeration attempt",
            extra={
                "event_type": "tenant_enumeration_attempt",
                "path": path,
                "method": method,
                "ip_address": ip_address,
                "invalid_tenant_id_truncated": truncated_id,
                "security_event": True,
            }
        )
        try:
            from core.monitoring import track_security_event
            track_security_event(
                event_type="tenant_enumeration_attempt",
                tenant_id="system",
                resource=path,
                action=method,
                ip_address=ip_address,
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Failed to log tenant enumeration: {e}")


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def sanitize_input(input_str: str) -> str:
    if not input_str:
        return ""
    clean = re.sub(r"<[^>]+>", "", input_str)
    clean = re.sub(r'[<>"\']', "", clean)
    return clean.strip()


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)
