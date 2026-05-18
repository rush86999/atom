from __future__ import annotations
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.database import SessionLocal
from core.logging_config import get_logger
from core.monitoring import track_http_request

logger = get_logger("audit_middleware")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now(timezone.utc)

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Re-raise to let other handlers (or FastAPI) catch it,
            # but we extract what we can for metrics if needed
            raise e

        end_time = datetime.now(timezone.utc)
        process_time = (end_time - start_time).total_seconds()

        # Extract user_id and tenant_id
        user_id = None
        tenant_id = "global"

        # Try to extract tenant from request state or path if available
        if hasattr(request, "state") and hasattr(request.state, "tenant_id"):
            tenant_id = request.state.tenant_id

        # Extract user_id from request for audit logging (non-blocking)
        try:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                with SessionLocal() as db:
                    try:
                        from core.auth import get_current_user_optional
                        user = await get_current_user_optional(token, db)
                        if user:
                            user_id = str(user.id)
                    except ImportError:
                        try:
                            from core.auth import get_current_user
                            user = await get_current_user(token, db)
                            if user:
                                user_id = str(user.id)
                        except Exception:
                            pass
                    except Exception:
                        pass
        except Exception:
            pass

        # Skip metrics for internal/health endpoints to avoid noise
        if request.url.path in ["/", "/health", "/api/health", "/api/health/metrics"]:
            return response

        # Track metrics in Prometheus
        try:
            track_http_request(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
                duration=process_time,
            )
        except Exception:
            pass

        # Standard structured audit logging
        try:
            logger.info(
                "HTTP_REQUEST_AUDIT",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(process_time * 1000, 2),
                client_ip=request.client.host if request.client else None,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        except Exception:
            pass

        # Add Timing Header
        response.headers["X-Process-Time"] = str(process_time)

        return response
