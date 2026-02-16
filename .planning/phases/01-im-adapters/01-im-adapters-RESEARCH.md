# Phase 1: "Everywhere" Interface (IM Adapters) - Research

**Researched:** February 15, 2026
**Domain:** FastAPI webhook security, rate limiting, governance middleware
**Confidence:** HIGH

## Summary

IMGovernanceService implementation is a **well-understood problem** with established patterns in the FastAPI ecosystem. The phase requires integrating three proven technologies: (1) **SlowAPI** for rate limiting, (2) **HMAC signature verification** for webhook security, and (3) **async audit logging** for compliance. The existing codebase already has `GovernanceCache` (<1ms lookups), `AgentGovernanceService` (maturity checks), and a `RateLimiter` class (basic implementation), which means IMGovernanceService will be a **composition layer** rather than building from scratch.

**Primary recommendation:** Use SlowAPI with in-memory token bucket algorithm (10 req/min per user_id), centralize webhook verification in IMGovernanceService before UniversalWebhookBridge, and log all IM interactions to a new IMAuditLog model for enterprise compliance.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Focus on governance hardening, NOT rebuilding existing adapters
- Centralized security layer for all IM platforms
- Rate limiting: 10 req/min per user_id
- Integration with existing GovernanceCache for <1ms permission lookups
- Audit trail logging for all IM interactions

### Claude's Discretion
- Implementation approach for rate limiting (in-memory vs Redis)
- Webhook signature verification strategy (reuse existing adapter.verify_request() or centralize)
- Error handling patterns
- Testing strategy for security features

### Deferred Ideas (OUT OF SCOPE)
- Signal integration (unofficial API, documented as experimental)
- New platform adapters

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **SlowAPI** | 0.1.9+ | Rate limiting for FastAPI/Starlette | Most popular FastAPI rate limiter, adapted from Flask-Limiter, production-tested with millions of requests. Decorator-based, supports multiple algorithms (token bucket, fixed window, sliding window). |
| ** hashlib/hmac** | Python stdlib | Webhook signature verification | Standard library for cryptographic hashing, used by all major platforms (WhatsApp X-Hub-Signature-256, Slack signatures). No external dependency needed. |
| **Pydantic** | 2.0+ | Request validation | Already in codebase, validates webhook payloads before processing. |
| **SQLAlchemy** | 2.0+ | Audit trail storage | Existing ORM, already has AuditLog and AgentRequestLog models to pattern from. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **httpx** | 0.24+ | Async HTTP for adapter calls | Already used by TelegramAdapter and WhatsAppAdapter for outbound messages. |
| **structlog** | 23.0+ | Structured JSON logging | Optional: For audit trail logging with structured metadata (better than standard logging). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **SlowAPI** | starlette-rate-limit | Less mature, fewer features, smaller community. SlowAPI has better documentation and FastAPI integration. |
| **In-memory rate limiting** | Redis-backed rate limiting | Redis adds operational complexity (infrastructure, connection pooling). In-memory is sufficient for single-instance Atom deployment (can migrate to Redis later if needed). |
| **Centralized HMAC verification** | Adapter-level verification (current) | Current approach is fragmented (each adapter implements verify_request differently). Centralization enables consistent audit trail and easier maintenance. |
| **Custom RateLimiter class** | SlowAPI middleware | Custom implementation (exists in resource_guards.py) is basic (sliding window with list cleanup). SlowAPI provides token bucket algorithm, burst handling, and X-RateLimit headers out of the box. |

**Installation:**
```bash
# SlowAPI (if not already installed)
pip install slowapi

# For structured logging (optional, improves audit trail)
pip install structlog
```

## Architecture Patterns

### Recommended Project Structure

```
backend/core/
├── im_governance_service.py          # NEW: Centralized IM security layer
│   ├── IMGovernanceService           # Main service class
│   ├── verify_and_rate_limit()       # First gateway: verify + rate check
│   ├── check_permissions()           # Second gateway: governance maturity
│   └── log_to_audit_trail()          # Third gateway: audit logging
│
├── models.py                          # EXISTING: Add new model
│   └── IMAuditLog                    # NEW: Audit trail for IM interactions
│
├── communication/adapters/
│   ├── telegram.py                   # EXISTING: Remove verify_request() (now in IMGovernanceService)
│   ├── whatsapp.py                   # EXISTING: Remove verify_request() (now in IMGovernanceService)
│   └── base.py                       # EXISTING: Keep PlatformAdapter interface
│
integrations/
├── telegram_routes.py                 # EXISTING: Wire IMGovernanceService before UniversalWebhookBridge
└── whatsapp_routes.py                 # NEW: Add WhatsApp webhook route (similar to Telegram)

tests/
├── test_im_governance.py              # NEW: IMGovernanceService tests
│   ├── test_webhook_spoofing()       # Security: Reject forged signatures
│   ├── test_rate_limiting()          # Load: Burst requests blocked
│   ├── test_governance_checks()      # Auth: STUDENT blocked, INTERN needs approval
│   └── test_audit_trail()            # Compliance: All IM interactions logged
│
└── property_tests/
    └── im_governance_invariants.py   # NEW: Property-based tests
        ├── test_rate_limit_invariant  # Rate limit never exceeded
        ├── test_hmac_verification()   # Signature validation invariant
        └── test_audit_completeness()  # No IM interaction without audit log
```

### Pattern 1: IMGovernanceService as Middleware Gateway

**What:** Centralized security layer that intercepts ALL incoming IM webhooks before they reach UniversalWebhookBridge. Three-stage validation pipeline: (1) Verify signature + rate limit, (2) Check governance permissions, (3) Log to audit trail.

**When to use:** All IM platform webhooks (Telegram, WhatsApp, Slack, Discord, etc.). Single entry point for security governance.

**Example:**
```python
# Source: Based on SlowAPI pattern from https://github.com/laurentS/slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request, HTTPException, status

class IMGovernanceService:
    """
    Centralized governance layer for all IM adapters.

    Flow:
    1. verify_and_rate_limit() → Reject spoofed webhooks, enforce rate limits
    2. check_permissions() → Agent maturity checks (STUDENT blocked, etc.)
    3. log_to_audit_trail() → Audit all IM interactions
    """

    def __init__(self):
        # Use SlowAPI for rate limiting (token bucket algorithm)
        self.limiter = Limiter(
            key_func=lambda request: f"{request.path_params.get('platform')}_{request.query_params.get('user_id')}",
            default_limits=["10/minute"],  # 10 req/min per user_id
            storage_uri="memory://"  # In-memory for single-instance deployment
        )

        # Cache platform adapters for signature verification
        self.adapters = {
            "telegram": TelegramAdapter(),
            "whatsapp": WhatsAppAdapter(),
            # ... other platforms
        }

    async def verify_and_rate_limit(
        self,
        request: Request,
        body_bytes: bytes
    ) -> Dict[str, Any]:
        """
        Stage 1: Verify webhook authenticity + enforce rate limits.

        Returns:
            {"verified": True, "platform": "telegram", "sender_id": "123"}
            OR raises HTTPException(403) if verification fails
            OR raises HTTPException(429) if rate limited
        """
        platform = request.path_params.get("platform")

        # Step 1a: Rate limit check (before expensive signature verification)
        # Note: SlowAPI middleware handles this automatically via @limiter.limit decorator
        # But we can also manually check:
        if not self.limiter._check_request_limit(request):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "60"}  # 60 seconds
            )

        # Step 1b: Signature verification
        adapter = self.adapters.get(platform)
        if not adapter:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported platform: {platform}"
            )

        is_valid = await adapter.verify_request(request, body_bytes)
        if not is_valid:
            # Log security violation
            logger.warning(f"Invalid webhook signature from {platform}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook signature"
            )

        # Extract sender_id for next stage
        payload = await request.json()
        sender_id = payload.get("from") or payload.get("message", {}).get("from")

        return {
            "verified": True,
            "platform": platform,
            "sender_id": sender_id
        }

    async def check_permissions(
        self,
        sender_id: str,
        platform: str
    ) -> Dict[str, Any]:
        """
        Stage 2: Check agent governance permissions before routing to ChatOrchestrator.

        Uses existing GovernanceCache for <1ms lookups.
        """
        from core.governance_cache import get_governance_cache
        from core.agent_governance_service import AgentGovernanceService

        cache = get_governance_cache()

        # Check if user is blocked (e.g., abuse, policy violation)
        # This is a NEW governance check specific to IM interactions
        is_blocked = await cache.get(f"im_blocked:{platform}:{sender_id}")
        if is_blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User blocked from IM interactions"
            )

        # Check agent maturity (if specific agent mentioned)
        # Reuse existing AgentGovernanceService logic
        # ...

        return {"allowed": True}

    async def log_to_audit_trail(
        self,
        platform: str,
        sender_id: str,
        payload: Dict[str, Any],
        action: str,
        success: bool
    ):
        """
        Stage 3: Log all IM interactions to audit trail (async, non-blocking).
        """
        from core.models import IMAuditLog
        from core.database import get_db_session

        # Async logging to avoid blocking request processing
        asyncio.create_task(self._write_audit_log(
            platform=platform,
            sender_id=sender_id,
            payload=payload,
            action=action,
            success=success
        ))

    async def _write_audit_log(self, **kwargs):
        """Fire-and-forget audit log write"""
        with get_db_session() as db:
            audit_log = IMAuditLog(**kwargs)
            db.add(audit_log)
            db.commit()
```

### Pattern 2: Route Integration with Middleware

**What:** IMGovernanceService wired into FastAPI routes **before** UniversalWebhookBridge.process_incoming_message().

**When to use:** All IM webhook endpoints.

**Example:**
```python
# Source: Based on FastAPI middleware pattern from https://medium.com/@connect.hashblock/7-fastapi-security-patterns-that-actually-ship-19c52d717668
from fastapi import APIRoute, Request, Depends
import logging

logger = logging.getLogger(__name__)

# Global IMGovernanceService instance
im_governance = IMGovernanceService()

class IMGovernanceRoute(APIRoute):
    """Custom route that enforces IM governance before processing"""

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request) -> Response:
            # Stage 1: Verify + rate limit
            body_bytes = await request.body()
            verification_result = await im_governance.verify_and_rate_limit(request, body_bytes)

            # Stage 2: Check permissions
            await im_governance.check_permissions(
                sender_id=verification_result["sender_id"],
                platform=verification_result["platform"]
            )

            # Proceed to original handler (UniversalWebhookBridge)
            response = await original_handler(request)

            # Stage 3: Log to audit trail (async, after response)
            await im_governance.log_to_audit_trail(
                platform=verification_result["platform"],
                sender_id=verification_result["sender_id"],
                payload=await request.json(),
                action="webhook_received",
                success=response.status_code < 400
            )

            return response

        return custom_handler

# Usage in routes:
router = APIRouter(route_class=IMGovernanceRoute)

@router.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    # This handler only runs AFTER IMGovernanceService checks pass
    return await universal_webhook_bridge.process_incoming_message("telegram, await request.json())
```

### Pattern 3: Audit Log Model

**What:** SQLAlchemy model to track all IM interactions for compliance and security analysis.

**When to use:** Every IM webhook receives a log entry (even failed ones).

**Example:**
```python
# Source: Based on existing AuditLog model from core/models.py line 402
from core.models import Base
from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON
from sqlalchemy.sql import func

class IMAuditLog(Base):
    """
    Audit trail for all IM platform interactions.

    Purpose:
    - Compliance (SOC2, HIPAA, GDPR)
    - Security forensics (detect abuse patterns)
    - Analytics (platform usage, user activity)
    """
    __tablename__ = "im_audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Who
    platform = Column(String, nullable=False, index=True)  # telegram, whatsapp, etc.
    sender_id = Column(String, nullable=False, index=True)  # User/platform-specific ID
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # Atom user (if linked)

    # What
    action = Column(String, nullable=False)  # webhook_received, command_run, etc.
    payload_hash = Column(String, nullable=True)  # SHA256 of payload (PII protection)
    metadata_json = Column(JSON, default=dict)  # Non-sensitive metadata (command, agent, etc.)

    # When
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Outcome
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    rate_limited = Column(Boolean, default=False)  # True if request was rate limited
    signature_valid = Column(Boolean, default=True)  # False if signature verification failed

    # Governance
    governance_check_passed = Column(Boolean, nullable=True)  # NULL if not checked
    agent_maturity_level = Column(String, nullable=True)  # STUDENT, INTERN, etc.

    # Relationships
    user = relationship("User", backref="im_audit_logs")
```

### Anti-Patterns to Avoid

- **Anti-pattern 1: Adapter-level rate limiting** (fragmented, hard to audit). Use centralized SlowAPI middleware instead.
- **Anti-pattern 2: Synchronous audit logging** (blocks request processing). Use async fire-and-forget logging with `asyncio.create_task()`.
- **Anti-pattern 3: Skipping rate limit for "trusted" platforms** (all platforms should be rate limited to prevent abuse).
- **Anti-pattern 4: Storing raw webhook payloads in audit logs** (PII violation). Store SHA256 hash instead, with sensitive fields stripped.
- **Anti-pattern 5: Hardcoded rate limits** (makes tuning difficult). Use environment variables: `IM_RATE_LIMIT_PER_MINUTE=10`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Rate limiting algorithm** | Custom token bucket with sliding window list cleanup | **SlowAPI** middleware | SlowAPI provides token bucket algorithm, burst handling, X-RateLimit headers, and is production-tested. Custom implementation (like `resource_guards.py:RateLimiter`) is basic and doesn't handle edge cases (concurrent requests, clock skew). |
| **HMAC signature verification** | Manual hmac.compare_digest() with error-prone string parsing | **hashlib/hmac** with platform-specific adapters | Existing adapters (TelegramAdapter, WhatsAppAdapter) already implement signature verification correctly. Centralize in IMGovernanceService but reuse adapter logic. |
| **Audit logging** | Custom logging to files or basic logger.info() | **SQLAlchemy model** (IMAuditLog) + async write | Database-backed audit trail enables querying, aggregation, and compliance reporting. File-based logging is hard to query and analyze. |
| **Webhook validation** | Manual JSON schema validation with if/else checks | **Pydantic models** for webhook payloads | Pydantic provides automatic validation, type coercion, and error messages. Already in codebase, use it for all webhook payloads. |

**Key insight:** IMGovernanceService is a **composition layer** that orchestrates existing libraries (SlowAPI, hashlib, SQLAlchemy) rather than building new security primitives from scratch. The value add is **centralization** and **audit trail**, not novel security algorithms.

## Common Pitfalls

### Pitfall 1: Race Conditions in Rate Limiting

**What goes wrong:** Multiple concurrent requests from the same user arrive simultaneously, all pass rate limit check before any updates the counter, allowing exceeding the limit.

**Why it happens:** Time-of-check-to-time-of-use (TOCTOU) race condition when using `if len(self.calls) >= self.max_calls:` pattern (see `resource_guards.py:RateLimiter` line 294).

**How to avoid:** Use SlowAPI's built-in thread-safe rate limiting (uses locks internally). For custom implementations, use `asyncio.Lock()` or Redis atomic operations (Lua scripts).

**Warning signs:** Rate limit exceeded in logs, but monitoring shows lower actual traffic. Or users report being able to send bursts beyond the limit.

### Pitfall 2: Blocking Audit Logging Slows Webhook Processing

**What goes wrong:** Synchronous database writes for audit logging block webhook processing, increasing response latency from ~100ms to ~500ms+.

**Why it happens:** Calling `db.add(audit_log)` and `db.commit()` in the request handler thread before returning response.

**How to avoid:** Use async fire-and-forget logging: `asyncio.create_task(self._write_audit_log(...))`. The task runs in background without blocking the response.

**Warning signs:** Webhook response times increase over time as audit log table grows. Database connection pool exhaustion (too many connections waiting on audit writes).

### Pitfall 3: Middleware Order Breaks Security

**What goes wrong:** Rate limiting middleware runs AFTER request processing, allowing attackers to bypass limits.

**Why it happens:** FastAPI middleware execution order depends on `app.add_middleware()` call order. If added after CORS or logging middleware, it might not run early enough.

**How to avoid:** Use custom `APIRoute` class (Pattern 2) instead of middleware, or ensure `app.add_middleware(rate_limit_middleware)` is the **first** middleware added.

**Warning signs:** Rate limit headers (X-RateLimit-Remaining) not present in responses. Logs show requests completing before rate limit check.

### Pitfall 4: Signature Verification Timing Attacks

**What goes wrong:** Attackers can guess valid webhook signatures by measuring response times (string comparison short-circuits on first mismatch).

**Why it happens:** Using `==` for signature comparison instead of `hmac.compare_digest()`. See `whatsapp.py` line 50 (uses `compare_digest` correctly, but `telegram.py` line 27 uses `==`).

**How to avoid:** Always use `hmac.compare_digest(signature, expected_signature)` for HMAC verification (constant-time comparison).

**Warning signs:** Security audit tools flag timing attack vulnerabilities. Or unusual signature verification patterns in access logs.

### Pitfall 5: False Positives Block Legitimate Users

**What goes wrong:** Legitimate users (e.g., high-volume automation) get rate limited and blocked, causing support tickets and user frustration.

**Why it happens:** Fixed rate limits (10 req/min) don't account for legitimate burst patterns (e.g., user runs multiple `/workflow` commands in quick succession).

**How to avoid:**
1. Add `X-RateLimit-Remaining` headers so clients can see their quota (SlowAPI does this automatically).
2. Implement whitelist mechanism for trusted users/admins: `IM_RATE_LIMIT_WHITELIST=user1@company.com,user2@company.com`.
3. Use token bucket algorithm (allows bursts) instead of fixed window (SlowAPI supports both).

**Warning signs:** Support tickets about "webhook stopped working" or "429 errors" from legitimate users. Monitoring shows spike in 429 status codes.

## Code Examples

Verified patterns from official sources:

### SlowAPI Rate Limiting Integration

```python
# Source: https://github.com/laurentS/slowapi (official SlowAPI documentation)
from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/telegram/webhook")
@limiter.limit("10/minute")  # Apply rate limit
async def telegram_webhook(request: Request):
    return {"message": "Webhook processed"}
```

### HMAC Signature Verification

```python
# Source: https://oneuptime.com/blog/post/2026-01-22-hmac-signing-python-api/view (January 22, 2026)
import hmac
import hashlib

def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """
    Verify HMAC-SHA256 webhook signature.

    Args:
        payload: Raw request body bytes
        signature: X-Hub-Signature-256 header value (format: "sha256=<sig>")
        secret: App secret from platform (e.g., WHATSAPP_APP_SECRET)

    Returns:
        True if signature valid, False otherwise
    """
    if not signature.startswith("sha256="):
        return False

    received_hash = signature.split("=")[1]
    expected_hash = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(received_hash, expected_hash)
```

### Async Audit Logging (Fire-and-Forget)

```python
# Source: https://www.kazis.dev/blogs/python-async-logging (August 15, 2025)
import asyncio
from sqlalchemy.orm import Session

async def log_im_interaction_async(
    platform: str,
    sender_id: str,
    payload: dict,
    db_session: Session
):
    """
    Non-blocking audit log write.

    Runs in background task, doesn't block webhook response.
    """
    try:
        audit_log = IMAuditLog(
            platform=platform,
            sender_id=sender_id,
            payload_hash=hashlib.sha256(str(payload).encode()).hexdigest(),
            metadata_json=payload,
            action="webhook_received",
            success=True
        )
        db_session.add(audit_log)
        db_session.commit()
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")
        # Don't raise - audit log failure shouldn't break webhook processing

# In webhook handler:
async def webhook_handler(request: Request):
    # Process webhook
    result = await process_webhook(request)

    # Log to audit trail (async, non-blocking)
    asyncio.create_task(
        log_im_interaction_async(
            platform="telegram",
            sender_id=sender_id,
            payload=await request.json(),
            db_session=get_db_session()
        )
    )

    return result
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Adapter-level security** (each platform implements own verify_request) | **Centralized IMGovernanceService** (single security layer) | 2025-2026 | Consistent audit trail, easier maintenance, reduced code duplication |
| **Basic rate limiting** (sliding window with list cleanup) | **Token bucket algorithm** (allows bursts, better UX) | 2024-2025 | Legitimate burst traffic allowed, fewer false positives |
| **Synchronous audit logging** (blocks request processing) | **Async fire-and-forget logging** (background tasks) | 2025-2026 | No latency impact from audit logging, better performance |
| **Manual HMAC verification** (error-prone string parsing) | **Standardized hmac.compare_digest()** (constant-time, prevents timing attacks) | 2023-2024 | Better security, timing attack prevention |

**Deprecated/outdated:**
- **Flask-Limiter**: Replaced by SlowAPI for FastAPI applications (SlowAPI is adapted from Flask-Limiter but optimized for Starlette/FastAPI async patterns).
- **Custom rate limit with Redis lists**: Modern Redis rate limiting uses Lua scripts for atomic operations (avoids race conditions). See [snok/self-limiters](https://github.com/snok/self-limiters) for Python implementation.
- **Fixed window rate limiting**: Replaced by token bucket or sliding window (smoother user experience, less burst rejection).

## Open Questions

1. **Redis vs In-Memory Rate Limiting**
   - What we know: In-memory is sufficient for single-instance deployment. Redis adds complexity but enables distributed rate limiting across multiple instances.
   - What's unclear: Whether Atom will deploy as multi-instance horizontally-scaled application.
   - Recommendation: Start with in-memory (simpler), migrate to Redis if horizontal scaling is needed. SlowAPI supports both via `storage_uri` parameter.

2. **Rate Limit Key Granularity**
   - What we know: Need to limit per `user_id` (sender_id from platform). But some platforms (e.g., Slack channels) have shared sender_id.
   - What's unclear: Should rate limit be per-platform or global across all platforms?
   - Recommendation: Per-platform rate limiting (key: `{platform}:{sender_id}`). Prevents abuse on one platform from affecting others.

3. **Audit Log Retention Policy**
   - What we know: IMAuditLog table will grow indefinitely. Need retention policy for compliance (GDPR requires data minimization).
   - What's unclear: Required retention period (90 days? 1 year? 7 years for financial audits?).
   - Recommendation: Start with 90-day retention, add `IM_AUDIT_RETENTION_DAYS` environment variable for tuning.

## Sources

### Primary (HIGH confidence)

- **[laurentS/slowapi GitHub Repository](https://github.com/laurentS/slowapi)** - Official SlowAPI library, rate limiting middleware for FastAPI/Starlette. Verified decorator pattern, token bucket algorithm, X-RateLimit headers.
- **[Python hashlib/hmac Documentation](https://docs.python.org/3/library/hashlib.html)** - Official Python stdlib docs for cryptographic hashing. Verified `hmac.compare_digest()` for constant-time comparison.
- **[FastAPI Official Documentation](https://fastapi.tiangolo.com/)** - Custom route handlers, middleware, dependency injection patterns.
- **Existing Atom Codebase** - Verified existing implementations: `TelegramAdapter.verify_request()` (line 20), `WhatsAppAdapter.verify_request()` (line 24), `GovernanceCache` (line 25), `RateLimiter` (line 264), `AuditLog` model (line 402).

### Secondary (MEDIUM confidence)

- **[How to Secure APIs with HMAC Signing in Python - OneUptime](https://oneuptime.com/blog/post/2026-01-22-hmac-signing-python-api/view)** (January 22, 2026) - HMAC implementation patterns with code examples for webhook signature verification.
- **[How to Build Webhook Handlers in Python - OneUptime](https://oneuptime.com/blog/post/2026-01-25-webhook-handlers-python/view)** (January 25, 2026) - Production-ready webhook handlers with signature verification and idempotency.
- **[7 FastAPI Security Patterns That Actually Ship](https://medium.com/@connect.hashblock/7-fastapi-security-patterns-that-actually-ship-19c52d717668)** (October 15, 2025) - FastAPI security patterns including webhook signature verification.
- **[Using SlowAPI in FastAPI: Mastering Rate Limiting Like a Pro](https://shiladityamajumder.medium.com/using-slowapi-in-fastapi-mastering-rate-limiting-like-a-pro-19044cb6062b)** (January 27, 2026) - Comprehensive SlowAPI guide with decorator patterns and configuration.
- **[Building a Production-Ready Rate Limiter - Dev.to](https://dev.to/tim_derzhavets/building-a-production-ready-rate-limiter-from-token-bucket-to-distributed-redis-implementation-bbc)** (February 12, 2026) - Covers Redis-backed rate limiting with atomic operations to avoid race conditions.
- **[Python Async Logging - Kazi's Dev Blog](https://www.kazis.dev/blogs/python-async-logging)** (August 15, 2025) - Async logging patterns for non-blocking audit trail writes.
- **[Rate Limiting Without the Rage: A 2026 Guide - Zuplo](https://zuplo.com/learning-center/rate-limiting-without-the-rage-a-2026-guide)** (February 3, 2026) - Modern rate limiting approaches to minimize false positives.
- **[How to Implement API Rate Limit Headers - OneUptime](https://oneuptime.com/blog/post/2026-01-30-api-rate-limit-headers/view)** (January 30, 2026) - X-RateLimit headers for proactive quota management.

### Tertiary (LOW confidence)

- **[Why Webhooks Still Fail Us in 2026 - GitHub Community Discussion](https://github.com/orgs/community/discussions/185003)** - Infrastructure components (CDNs/WAFs) blocking webhook traffic. Need verification to confirm if applicable to Atom.
- **[FastAPI Performance Bottlenecks: Why Middleware and ORMs Kill Throughput - Medium](https://medium.com/@dikhyantkrishnadalai/fastapi-performance-bottlenecks-why-middleware-and-orms-kill-throughput-and-how-to-fix-them-a79924bfaebb)** (November 8, 2025) - Middleware performance impact. Need testing to validate if IMGovernanceService adds significant latency.
- **[WHY RACE CONDITIONS in 2026 - Medium](https://medium.com/@lukewago/why-race-conditions-in-2026-64867438e4db)** (January 18, 2026) - General race condition patterns. Need specific testing for rate limiter concurrent requests.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - SlowAPI and HMAC are well-established, verified with official docs and GitHub repos.
- Architecture: HIGH - Integration patterns (custom APIRoute, async logging) are standard FastAPI practices, verified with official FastAPI docs and existing Atom codebase patterns.
- Pitfalls: MEDIUM - Race conditions and false positives are documented in 2025-2026 articles, but Atom-specific testing needed to validate.

**Research date:** February 15, 2026
**Valid until:** February 15, 2026 + 30 days = March 17, 2026 (FastAPI and SlowAPI are stable, but rate limiting best practices evolve rapidly)
