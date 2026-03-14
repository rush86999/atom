"""
Core security utilities for the Atom platform.

This package provides:
- Rate limiting middleware
- Security headers middleware
- Role-based access control (RBAC)
"""

import logging
import time
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .rbac import require_role

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Identify client by IP
        client_ip = request.client.host
        
        # Clean old requests
        current_time = time.time()
        self.request_counts[client_ip] = [
            t for t in self.request_counts[client_ip] 
            if current_time - t < 60
        ]
        
        # Check limit
        if len(self.request_counts[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return Response("Rate limit exceeded", status_code=429)
            
        # Record request
        self.request_counts[client_ip].append(current_time)
        
        # Process request
        response = await call_next(request)
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net fonts.googleapis.com fonts.gstatic.com; img-src 'self' data: https:;"
        
        return response

__all__ = ["require_role", "RateLimitMiddleware", "SecurityHeadersMiddleware"]

