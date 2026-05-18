from __future__ import annotations
import logging
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.database import SessionLocal

logger = logging.getLogger(__name__)


class DomainRoutingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """
        Resolves the tenant based on the Host header (Custom Domain).
        If matched, it attaches the tenant_id to the request state.
        """
        # 0. EXEMPT CORE SYSTEM PATHS
        exempt_paths = [
            "/",
            "/health",
            "/alive",
            "/api/health",
            "/api/v1/openapi.json",
            "/api/v1/docs",
            "/api/v1/redoc",
        ]
        if request.url.path in exempt_paths:
            return await call_next(request)

        host = request.headers.get("host", "").split(":")[0]  # Remove port if present

        # We skip local/internal hosts and Fly.io internal domains
        if (
            host == "localhost"
            or host.endswith(".localhost")
            or host == "127.0.0.1"
            or host == "testserver"
            or host.endswith(".fly.dev")
            or host.endswith(".ngrok-free.app")
        ):
            # Skip domain routing for local development or system domains
            request.state.tenant_id = None
            return await call_next(request)

        # Otherwise proceed with DB lookup for custom domain or subdomain
        db = SessionLocal()
        request.scope["db"] = db # Inject into scope for downstream validation
        try:
            from core.models import Tenant
            # 1. Check Custom Domain Mapping
            tenant = None
            try:
                tenant = db.query(Tenant).filter(Tenant.custom_domain == host).first()
            except Exception:
                db.rollback()
                pass

            # 2. Fallback to Subdomain Mapping
            if not tenant:
                subdomain = host.split(".")[0]
                if subdomain not in ["www", "api"]:
                    try:
                        tenant = db.query(Tenant).filter(Tenant.subdomain == subdomain).first()
                    except Exception:
                        db.rollback()
                        pass

                    # Development fallback for 'raj' subdomain
                    if (
                        not tenant
                        and os.getenv("ENVIRONMENT") != "production"
                        and subdomain == "raj"
                    ):
                        request.state.tenant_id = "raj-test-tenant-id"
                        request.state.tenant_name = "Raj Test Tenant"
                        return await call_next(request)

                    # If a subdomain was provided but no tenant found, reject with 404
                    if not tenant:
                        from fastapi.responses import JSONResponse

                        return JSONResponse(
                            status_code=404,
                            content={"detail": f"Tenant with subdomain '{subdomain}' not found"},
                        )

            if tenant:
                request.state.tenant_id = str(tenant.id)
                request.state.tenant_name = tenant.name
                request.state.branding = {
                    "logo_url": getattr(tenant, "logo_url", None),
                    "primary_color": getattr(tenant, "primary_color", None),
                }
                logger.debug(f"Resolved tenant {tenant.name} from host {host}")
            else:
                request.state.tenant_id = None
            
            response = await call_next(request)
            return response
        finally:
            db.close()
