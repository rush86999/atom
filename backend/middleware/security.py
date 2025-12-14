"""
Security Middleware
Provides rate limiting, input validation, and security headers
"""

import time
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import hashlib
import secrets
import logging

# Security logger
security_logger = logging.getLogger("atom.security")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with configurable limits"""

    def __init__(self, app, requests_per_minute: int = 60, burst_size: int = 10):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.clients: Dict[str, Dict[str, Any]] = {}

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit
        if self._is_rate_limited(client_ip):
            security_logger.warning(
                f"Rate limit exceeded for IP: {client_ip} - {request.method} {request.url.path}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "type": "rate_limit_exceeded",
                        "message": "Too many requests. Please try again later.",
                        "retry_after": 60
                    }
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + 60)
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        client_data = self.clients.get(client_ip, {})
        remaining = max(0, self.requests_per_minute - client_data.get("count", 0))
        reset_time = int(client_data.get("reset_time", time.time() + 60))

        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request"""
        # Check for forwarded IP
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if client has exceeded rate limit"""
        current_time = time.time()

        # Get or create client data
        if client_ip not in self.clients:
            self.clients[client_ip] = {
                "count": 0,
                "reset_time": current_time + 60,
                "burst_tokens": self.burst_size
            }

        client_data = self.clients[client_ip]

        # Reset if time window has passed
        if current_time > client_data["reset_time"]:
            client_data["count"] = 0
            client_data["reset_time"] = current_time + 60
            client_data["burst_tokens"] = self.burst_size

        # Check burst tokens first
        if client_data["burst_tokens"] > 0:
            client_data["burst_tokens"] -= 1
            client_data["count"] += 1
            return False

        # Check rate limit
        if client_data["count"] >= self.requests_per_minute:
            return True

        # Increment count
        client_data["count"] += 1
        return False


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Input validation middleware for security"""

    def __init__(self, app):
        super().__init__(app)
        # Malicious patterns to block
        self.malicious_patterns = [
            r'<script[^>]*>.*?</script>',  # XSS
            r'javascript:',               # JS protocol
            r'on\w+\s*=',               # Event handlers
            r'union\s+select',          # SQL injection
            r'drop\s+table',            # SQL injection
            r'exec\(',                  # Code execution
            r'eval\(',                  # Code execution
            r'system\(',                # System commands
        ]

    async def dispatch(self, request: Request, call_next):
        # Validate query parameters
        if not self._validate_query_params(request):
            security_logger.warning(
                f"Malicious query params detected: {request.query_params}"
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "type": "invalid_input",
                        "message": "Invalid request parameters"
                    }
                }
            )

        # For POST/PUT requests, validate body
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Get request body
                body = await request.body()
                body_str = body.decode('utf-8', errors='ignore')

                # Validate body content
                if not self._validate_content(body_str):
                    security_logger.warning(
                        f"Malicious content detected in body: {body_str[:200]}..."
                    )
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": {
                                "type": "invalid_input",
                                "message": "Invalid request content"
                            }
                        }
                    )

                # Create new request with body
                # Note: This is simplified for MVP. In production, you'd need
                # to properly reconstruct the request
                request._body = body

            except Exception:
                pass  # If we can't read body, continue

        return await call_next(request)

    def _validate_query_params(self, request: Request) -> bool:
        """Validate query parameters"""
        for param_name, param_value in request.query_params.items():
            # Check for malicious patterns
            if self._contains_malicious_content(str(param_value)):
                return False

            # Check parameter length
            if len(str(param_value)) > 1000:
                return False

        return True

    def _validate_content(self, content: str) -> bool:
        """Validate request content"""
        # Check for malicious patterns
        if self._contains_malicious_content(content):
            return False

        # Check content size
        if len(content) > 10 * 1024 * 1024:  # 10MB limit
            return False

        return True

    def _contains_malicious_content(self, content: str) -> bool:
        """Check if content contains malicious patterns"""
        content_lower = content.lower()
        for pattern in self.malicious_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE | re.MULTILINE):
                return True
        return False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss: https:;"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        return response


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware (simplified for MVP)"""

    def __init__(self, app):
        super().__init__(app)
        self.csrf_tokens = {}
        self.token_expiry = 3600  # 1 hour

    async def dispatch(self, request: Request, call_next):
        # Skip CSRF for GET, HEAD, OPTIONS
        if request.method in ["GET", "HEAD", "OPTIONS"]:
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
                            "message": "Invalid or missing CSRF token"
                        }
                    }
                )

        return await call_next(request)

    def generate_csrf_token(self, session_id: str) -> str:
        """Generate CSRF token for session"""
        token = secrets.token_urlsafe(32)
        expiry = time.time() + self.token_expiry

        self.csrf_tokens[token] = {
            "session_id": session_id,
            "expiry": expiry
        }

        return token

    def _validate_csrf_token(self, token: str) -> bool:
        """Validate CSRF token"""
        if token not in self.csrf_tokens:
            return False

        token_data = self.csrf_tokens[token]

        # Check expiry
        if time.time() > token_data["expiry"]:
            del self.csrf_tokens[token]
            return False

        return True


def setup_security_middleware(app):
    """Setup all security middleware"""
    # Add middleware in order
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFProtectionMiddleware)
    app.add_middleware(InputValidationMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst_size=20)


# Security utilities
def hash_password(password: str) -> str:
    """Hash password (for MVP - use bcrypt in production)"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate secure API key"""
    return secrets.token_urlsafe(32)


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def sanitize_input(input_str: str) -> str:
    """Sanitize user input"""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', input_str)
    # Remove potentially harmful characters
    clean = re.sub(r'[<>"\']', '', clean)
    return clean.strip()