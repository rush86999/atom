---
phase: 01-im-adapters
plan: 02
type: execute
wave: 2
depends_on: ["01-im-adapters-01"]
files_modified:
  - backend/integrations/whatsapp_routes.py
  - backend/integrations/telegram_routes.py
  - backend/core/im_governance_service.py
autonomous: true
user_setup:
  - service: "whatsapp"
    why: "WhatsApp Cloud API requires webhook verification"
    env_vars:
      - name: WHATSAPP_APP_SECRET
        source: "Meta for Developers Dashboard -> WhatsApp -> Configuration"
      - name: WHATSAPP_ACCESS_TOKEN
        source: "Meta for Developers Dashboard -> WhatsApp -> API Setup"
      - name: WHATSAPP_PHONE_NUMBER_ID
        source: "Meta for Developers Dashboard -> WhatsApp -> Phone Numbers"

must_haves:
  truths:
    - "POST /api/whatsapp/webhook endpoint receives WhatsApp messages"
    - "GET /api/whatsapp/webhook endpoint handles verification challenge"
    - "Telegram webhook uses IMGovernanceService before UniversalWebhookBridge"
    - "WhatsApp webhook uses IMGovernanceService before UniversalWebhookBridge"
    - "Both webhooks return 200 OK after processing"
  artifacts:
    - path: "backend/integrations/whatsapp_routes.py"
      provides: "WhatsApp webhook endpoints with governance integration"
      min_lines: 100
      exports: ["POST /api/whatsapp/webhook", "GET /api/whatsapp/webhook"]
    - path: "backend/integrations/telegram_routes.py"
      provides: "Telegram webhook endpoints with governance integration (modified)"
      exports: ["POST /api/telegram/webhook"]
  key_links:
    - from: "backend/integrations/whatsapp_routes.py"
      to: "backend/core/im_governance_service.py"
      via: "IMGovernanceService.verify_and_rate_limit() before processing"
      pattern: "await im_governance.verify_and_rate_limit"
    - from: "backend/integrations/telegram_routes.py"
      to: "backend/core/im_governance_service.py"
      via: "IMGovernanceService.verify_and_rate_limit() before processing"
      pattern: "await im_governance.verify_and_rate_limit"
    - from: "backend/integrations/whatsapp_routes.py"
      to: "backend/integrations/universal_webhook_bridge.py"
      via: "UniversalWebhookBridge.process_incoming_message() after governance"
      pattern: "universal_webhook_bridge.process_incoming_message"
---

<objective>
Add WhatsApp webhook route (missing - adapter exists but no endpoint) and wire IMGovernanceService into both Telegram and WhatsApp webhooks. This completes the missing 10% gap identified in CONTEXT.md where WhatsAppAdapter exists but has no `/api/whatsapp/webhook` endpoint, and integrates the governance layer created in Plan 01.

Purpose: Complete IM adapter infrastructure with governance-first security
Output: Working WhatsApp webhook + governance-integrated Telegram webhook
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-im-adapters/01-im-adapters-CONTEXT.md
@.planning/phases/01-im-adapters/01-im-adapters-RESEARCH.md
@.planning/phases/01-im-adapters/01-im-adapters-01-SUMMARY.md

# Existing implementations
@backend/integrations/telegram_routes.py
@backend/core/communication/adapters/whatsapp.py
@backend/integrations/universal_webhook_bridge.py
@backend/core/im_governance_service.py
</context>

<tasks>

<task type="auto">
  <name>Create whatsapp_routes.py with webhook endpoints</name>
  <files>backend/integrations/whatsapp_routes.py</files>
  <action>
Create backend/integrations/whatsapp_routes.py (150-200 lines) following the pattern from telegram_routes.py:

```python
"""
WhatsApp Routes for ATOM Platform
Exposes WhatsApp webhook endpoints with IMGovernanceService integration
"""

import logging
from typing import Any, Dict
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

from core.im_governance_service import im_governance_service
from integrations.universal_webhook_bridge import universal_webhook_bridge
from core.communication.adapters.whatsapp import WhatsAppAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])

# Global adapter instance
whatsapp_adapter = WhatsAppAdapter()


@router.get("/webhook")
async def whatsapp_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    WhatsApp webhook verification endpoint (GET).

    Meta sends a GET request to verify the webhook URL:
    - hub.mode: "subscribe"
    - hub.challenge: Random string to echo back
    - hub.verify_token: Token you set in Meta dashboard

    Returns the hub.challenge to verify the webhook.
    """
    expected_token = "YOUR_VERIFY_TOKEN"  # TODO: Move to env var

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("WhatsApp webhook verified successfully")
        return int(hub_challenge)

    logger.warning("WhatsApp webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    WhatsApp webhook endpoint for incoming messages (POST).

    Flow:
    1. IMGovernanceService verifies signature + rate limits
    2. IMGovernanceService checks permissions
    3. UniversalWebhookBridge processes message
    4. IMGovernanceService logs to audit trail (background)
    """
    import hashlib
    import hmac

    # Get raw body bytes for signature verification
    body_bytes = await request.body()

    # Stage 1: Verify signature and rate limit
    try:
        verification_result = await im_governance_service.verify_and_rate_limit(
            request, body_bytes
        )
    except HTTPException as e:
        # Rate limited or signature invalid
        logger.warning(f"WhatsApp webhook rejected: {e.detail}")
        raise

    # Stage 2: Check permissions
    await im_governance_service.check_permissions(
        sender_id=verification_result["sender_id"],
        platform="whatsapp"
    )

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse WhatsApp webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Stage 3: Route to Universal Webhook Bridge
    try:
        result = await universal_webhook_bridge.process_incoming_message("whatsapp", payload)

        # Log to audit trail (async, non-blocking)
        background_tasks.add_task(
            im_governance_service.log_to_audit_trail,
            platform="whatsapp",
            sender_id=verification_result["sender_id"],
            payload=payload,
            action="webhook_received",
            success=True
        )

        return result

    except Exception as e:
        logger.error(f"WhatsApp webhook processing failed: {e}")

        # Log failure to audit trail
        background_tasks.add_task(
            im_governance_service.log_to_audit_trail,
            platform="whatsapp",
            sender_id=verification_result["sender_id"],
            payload=payload,
            action="webhook_received",
            success=False
        )

        raise HTTPException(status_code=500, detail="Processing failed")


@router.get("/health")
async def whatsapp_health():
    """WhatsApp health check"""
    return {"status": "healthy", "service": "WhatsApp"}


@router.get("/status")
async def whatsapp_status():
    """Get WhatsApp integration status"""
    return {
        "platform": "whatsapp",
        "adapter": "WhatsAppAdapter",
        "features": {
            "messaging": True,
            "media": True,  # Audio, images
            "governance": True
        }
    }
```

IMPORTANT: Follow telegram_routes.py structure but integrate IMGovernanceService at the beginning of POST handler.
  </action>
  <verify>
```bash
test -f backend/integrations/whatsapp_routes.py
grep -q "POST /webhook" backend/integrations/whatsapp_routes.py
grep -q "GET /webhook" backend/integrations/whatsapp_routes.py
grep -q "im_governance_service" backend/integrations/whatsapp_routes.py
```
  </verify>
  <done>
whatsapp_routes.py created with:
- GET /api/whatsapp/webhook endpoint for verification challenge
- POST /api/whatsapp/webhook endpoint for message processing
- IMGovernanceService integration (verify_and_rate_limit, check_permissions, log_to_audit_trail)
- Health and status endpoints
- Proper error handling and logging
  </done>
</task>

<task type="auto">
  <name>Integrate IMGovernanceService into telegram_routes.py</name>
  <files>backend/integrations/telegram_routes.py</files>
  <action>
Modify the existing POST /webhook endpoint in telegram_routes.py to integrate IMGovernanceService:

1. Import at top of file:
```python
from core.im_governance_service import im_governance_service
from fastapi import Request, BackgroundTasks
```

2. Modify the telegram_webhook function signature:
```python
# BEFORE:
@router.post("/webhook")
async def telegram_webhook(update: Dict[str, Any]):

# AFTER:
@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
```

3. Add governance pipeline at the start of the function (before existing logic):
```python
# Get raw body for signature verification
body_bytes = await request.body()

# Stage 1: Verify signature and rate limit
try:
    verification_result = await im_governance_service.verify_and_rate_limit(
        request, body_bytes
    )
except HTTPException as e:
    logger.warning(f"Telegram webhook rejected: {e.detail}")
    raise

# Stage 2: Check permissions
await im_governance_service.check_permissions(
    sender_id=verification_result.get("sender_id", "unknown"),
    platform="telegram"
)
```

4. Add audit logging after processing (before return):
```python
# Log to audit trail (async, non-blocking)
background_tasks.add_task(
    im_governance_service.log_to_audit_trail,
    platform="telegram",
    sender_id=verification_result.get("sender_id", "unknown"),
    payload=update,
    action="webhook_received",
    success=True
)
```

5. Parse JSON for existing logic:
```python
# Parse update for existing logic
import json
update = json.loads(body_bytes)
```

NOTE: Don't change the existing callback_query, inline_query, and message handling logic - just add governance wrapper.
  </action>
  <verify>
```bash
grep -q "from core.im_governance_service import im_governance_service" backend/integrations/telegram_routes.py
grep -q "verify_and_rate_limit" backend/integrations/telegram_routes.py
grep -q "check_permissions" backend/integrations/telegram_routes.py
grep -q "log_to_audit_trail" backend/integrations/telegram_routes.py
```
  </verify>
  <done>
telegram_routes.py modified with:
- IMGovernanceService imported
- POST /webhook endpoint uses Request and BackgroundTasks
- verify_and_rate_limit() called before processing
- check_permissions() called after verification
- log_to_audit_trail() called after processing
- Existing callback_query, inline_query, and message handling preserved
  </done>
</task>

<task type="auto">
  <name>Register WhatsApp router in main app</name>
  <files>backend/main.py</files>
  <action>
Add WhatsApp router to main FastAPI app:

1. Find where telegram_routes is included (search for `telegram_routes`)
2. Add whatsapp_routes alongside it:
```python
from integrations.whatsapp_routes import router as whatsapp_router

app.include_router(whatsapp_router)
```

3. Also verify IMGovernanceService is initialized as a global singleton (if not already):
```python
from core.im_governance_service import im_governance_service

# Initialize at module level
im_governance_service  # This triggers __init__
```

4. Configure SlowAPI error handler (if not in main.py):
```python
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

app.state.limiter = im_governance_service.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```
  </action>
  <verify>
```bash
grep -q "whatsapp_router" backend/main.py
grep -q "im_governance_service" backend/main.py
curl -s http://localhost:8000/api/whatsapp/health 2>/dev/null || echo "Server not running - check imports manually"
```
  </verify>
  <done>
WhatsApp router registered in main app:
- whatsapp_router imported and included
- IMGovernanceService initialized as global singleton
- SlowAPI error handler configured
- Both /api/telegram and /api/whatsapp endpoints accessible
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. whatsapp_routes.py exists with GET and POST /api/whatsapp/webhook endpoints
2. telegram_routes.py modified to use IMGovernanceService
3. Both routes registered in main.py
4. WhatsApp GET endpoint returns hub.challenge on verification
5. Both POST endpoints use IMGovernanceService before processing
6. Audit logging happens in background (non-blocking)
</verification>

<success_criteria>
- curl GET /api/whatsapp/webhook with correct params returns 200
- curl POST /api/whatsapp/webhook with valid signature processes message
- curl POST /api/telegram/webhook with valid signature processes message
- Both webhooks reject invalid signatures (403)
- Both webhooks reject rate-limited requests (429)
- Both webhooks log to IMAuditLog table
</success_criteria>

<output>
After completion, create `.planning/phases/01-im-adapters/01-im-adapters-02-SUMMARY.md` with:
- Files created/modified
- Endpoints added (GET/POST for WhatsApp, POST modified for Telegram)
- IMGovernanceService integration points
- Verification test results (if server running)
</output>
