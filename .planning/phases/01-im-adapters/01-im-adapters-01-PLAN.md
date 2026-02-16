---
phase: 01-im-adapters
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/im_governance_service.py
  - backend/core/models.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "All incoming IM webhooks are rate-limited to 10 requests/minute per user_id"
    - "Webhook signature verification rejects forged requests (X-Hub-Signature-256 for WhatsApp, X-Telegram-Bot-Api-Secret-Token for Telegram)"
    - "Governance maturity checks block STUDENT agents from IM triggers"
    - "All IM interactions are logged to IMAuditLog for compliance"
    - "Rate limiting uses SlowAPI with token bucket algorithm (allows bursts)"
  artifacts:
    - path: "backend/core/im_governance_service.py"
      provides: "Centralized IM security layer with rate limiting and governance checks"
      min_lines: 200
      exports: ["IMGovernanceService", "verify_and_rate_limit", "check_permissions", "log_to_audit_trail"]
    - path: "backend/core/models.py"
      provides: "IMAuditLog database model for compliance tracking"
      contains: "class IMAuditLog"
  key_links:
    - from: "backend/core/im_governance_service.py"
      to: "backend/core/governance_cache.py"
      via: "imports get_governance_cache for <1ms permission lookups"
      pattern: "from core.governance_cache import get_governance_cache"
    - from: "backend/core/im_governance_service.py"
      to: "backend/core/models.py"
      via: "IMAuditLog model for audit trail logging"
      pattern: "IMAuditLog.*platform.*sender_id"
    - from: "backend/core/im_governance_service.py"
      to: "slowapi.Limiter"
      via: "SlowAPI rate limiting middleware"
      pattern: "from slowapi import Limiter"
---

<objective>
Create IMGovernanceService - the centralized security layer for all IM platform interactions. This service implements rate limiting (10 req/min per user_id), webhook signature verification, governance maturity checks, and audit trail logging. Per user decision, this is a composition layer that orchestrates existing components (GovernanceCache, AgentGovernanceService) rather than rebuilding adapters.

Purpose: Enterprise-grade security governance for IM interactions (prevent spam, spoofing, and ensure compliance)
Output: IMGovernanceService class with three-stage pipeline (verify_and_rate_limit → check_permissions → log_to_audit_trail)
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-im-adapters/01-im-adapters-CONTEXT.md
@.planning/phases/01-im-adapters/01-im-adapters-RESEARCH.md
@.planning/PROJECT.md
@.planning/ROADMAP.md

# Existing implementations to leverage
@backend/core/governance_cache.py
@backend/core/agent_governance_service.py
@backend/core/communication/adapters/telegram.py
@backend/core/communication/adapters/whatsapp.py
@backend/core/communication/adapters/base.py
@backend/integrations/universal_webhook_bridge.py
</context>

<tasks>

<task type="auto">
  <name>Create IMGovernanceService with SlowAPI rate limiting</name>
  <files>backend/core/im_governance_service.py</files>
  <action>
Create IMGovernanceService class (300-400 lines) with three-stage security pipeline:

1. **__init__()**: Initialize SlowAPI Limiter with per-platform rate limiting
   - Use `slowapi.Limiter` with key_func: `lambda request: f"{request.path_params.get('platform')}_{sender_id}"`
   - Configure: `default_limits=["10/minute"]` (from user decision: 10 req/min)
   - Store platform adapters dict: {"telegram": TelegramAdapter(), "whatsapp": WhatsAppAdapter()}
   - Import: `from slowapi import Limiter, _rate_limit_exceeded_handler`
   - Import: `from slowapi.util import get_remote_address`
   - Import: `from slowapi.errors import RateLimitExceeded`

2. **async verify_and_rate_limit(request: Request, body_bytes: bytes) -> Dict[str, Any]**:
   - Extract platform from request (or route param)
   - Rate limit check FIRST (before expensive signature verification)
   - Get adapter from self.adapters dict
   - Call `adapter.verify_request(request, body_bytes)` for signature validation
   - Extract sender_id from payload for next stage
   - Return: {"verified": True, "platform": platform, "sender_id": sender_id}
   - Raise HTTPException(403) if signature invalid
   - Raise HTTPException(429) if rate limited (with Retry-After header)

3. **async check_permissions(sender_id: str, platform: str) -> Dict[str, Any]**:
   - Import: `from core.governance_cache import get_governance_cache`
   - Check if user blocked: `await cache.get(f"im_blocked:{platform}:{sender_id}")`
   - Check agent maturity (if specific agent in payload)
   - Return: {"allowed": True} or raise HTTPException(403)

4. **async log_to_audit_trail(platform, sender_id, payload, action, success)**:
   - Use `asyncio.create_task()` for fire-and-forget logging (don't block response)
   - Create IMAuditLog record with platform, sender_id, action, success
   - Handle errors gracefully (don't raise - audit log failure shouldn't break webhook)

5. **Add rate limit decorator**:
   - Create `@limiter.limit("10/minute")` decorator factory
   - Support per-user keys: `{platform}:{sender_id}`

IMPORTANT: Reuse existing adapter.verify_request() logic (TelegramAdapter line 20, WhatsAppAdapter line 24) - don't reimplement HMAC verification.
  </action>
  <verify>
```bash
# Check file exists with proper structure
test -f backend/core/im_governance_service.py && grep -q "class IMGovernanceService" backend/core/im_governance_service.py
grep -q "from slowapi import Limiter" backend/core/im_governance_service.py
grep -q "verify_and_rate_limit" backend/core/im_governance_service.py
grep -q "check_permissions" backend/core/im_governance_service.py
grep -q "log_to_audit_trail" backend/core/im_governance_service.py
```
  </verify>
  <done>
IMGovernanceService class exists with:
- SlowAPI Limiter configured for 10 req/min per user_id
- verify_and_rate_limit() method checking signatures and rate limits
- check_permissions() method using GovernanceCache
- log_to_audit_trail() method using async fire-and-forget pattern
- All methods have proper error handling and HTTP status codes
  </done>
</task>

<task type="auto">
  <name>Add IMAuditLog model to models.py</name>
  <files>backend/core/models.py</files>
  <action>
Add IMAuditLog SQLAlchemy model after existing AuditLog models (around line 425):

```python
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

Add import at top if uuid not already imported: `import uuid`

NOTE: This follows the existing pattern from AuditLog (line 402) and GovernanceAuditLog (line 4170).
  </action>
  <verify>
```bash
grep -q "class IMAuditLog" backend/core/models.py
grep -q "__tablename__ = \"im_audit_logs\"" backend/core/models.py
grep -q "platform.*sender_id.*action" backend/core/models.py
```
  </verify>
  <done>
IMAuditLog model added to models.py with:
- Table name: im_audit_logs
- Fields: platform, sender_id, user_id, action, payload_hash, metadata_json, timestamp, success, error_message, rate_limited, signature_valid, governance_check_passed, agent_maturity_level
- Proper indexes on platform, sender_id, timestamp
- User relationship backref to im_audit_logs
  </done>
</task>

<task type="auto">
  <name>Create database migration for IMAuditLog table</name>
  <files>backend/alembic/versions/</files>
  <action>
Generate Alembic migration for IMAuditLog model:

```bash
cd backend
alembic revision -m "add_im_audit_log_table"
```

Edit the generated migration file to include IMAuditLog table creation:
- Add im_audit_logs table with all columns from IMAuditLog model
- Include indexes: platform, sender_id, timestamp
- Include foreign key: user_id references users.id

Apply migration:
```bash
alembic upgrade head
```

Verify table created:
```bash
sqlite3 atom_dev.db ".schema im_audit_logs" | head -20
```
  </action>
  <verify>
```bash
# Check migration file exists and has been applied
ls -la backend/alembic/versions/*im_audit_log*
cd backend && alembic current | grep -v "None"
```
  </verify>
  <done>
Alembic migration created and applied successfully:
- Migration file: *add_im_audit_log_table.py
- im_audit_logs table exists in database
- All columns and indexes created
- Foreign key to users.id established
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. IMGovernanceService exists with all required methods
2. IMAuditLog model exists in models.py
3. Database migration applied successfully
4. SlowAPI properly configured with 10 req/min rate limit
5. verify_and_rate_limit() integrates with existing adapters
6. check_permissions() uses GovernanceCache for <1ms lookups
7. log_to_audit_trail() uses async fire-and-forget pattern
</verification>

<success_criteria>
- IMGovernanceService can verify webhook signatures for Telegram and WhatsApp
- Rate limiting blocks 11th request within 1 minute per user_id
- Governance checks prevent STUDENT agents from IM triggers
- All IM interactions logged to IMAuditLog table
- Zero blocking of request processing (audit logging is async)
- Can import and instantiate IMGovernanceService without errors
</success_criteria>

<output>
After completion, create `.planning/phases/01-im-adapters/01-im-adapters-01-SUMMARY.md` with:
- Files created/modified
- Lines of code added
- Key implementation decisions
- Integration points with existing services
- Known limitations or TODOs
</output>

---

## Gap Closure Note (Plan 06)

Original plan specified SlowAPI with token bucket algorithm. Implementation used
custom sliding window which works correctly but created documentation mismatch.

Resolution (Plan 06): Update documentation to match implementation rather than
replacing working code. Sliding window is:
- Functional: Correctly enforces 10 req/min
- Simple: No external dependency
- Well-tested: Property tests verify invariants

See 01-im-adapters-06-PLAN.md for details.
