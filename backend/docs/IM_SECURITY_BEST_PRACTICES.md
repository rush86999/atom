# IM Security Best Practices

Security guidelines for integrating Telegram, WhatsApp, and future IM platforms with Atom Agent OS.

## Overview

All IM interactions go through IMGovernanceService, which provides:
- **Webhook signature verification**: Prevents request spoofing
- **Rate limiting**: Prevents spam and abuse (10 req/min per user)
- **Governance checks**: Ensures agents have appropriate maturity
- **Audit trail**: Logs all interactions for compliance

---

## Webhook Signature Verification

### Why It Matters

Without signature verification, attackers can:
- Spoof webhooks pretending to be from legitimate platforms
- Inject malicious payloads into your system
- Bypass governance and rate limiting
- Trigger unauthorized agent actions

### How It Works

**Telegram**:
- Uses `X-Telegram-Bot-Api-Secret-Token` header
- Secret token set during webhook configuration
- Constant-time comparison via `hmac.compare_digest()`

**WhatsApp**:
- Uses `X-Hub-Signature-256` header (HMAC-SHA256)
- Signature format: `sha256=<hex_hash>`
- Calculated as: `hmac.new(app_secret, payload, sha256).hexdigest()`

### Implementation

```python
# IMGovernanceService verifies signatures before any processing
result = await im_governance.verify_and_rate_limit(request, body_bytes)
```

### Security Rules

1. **ALWAYS** verify signatures before processing webhook payload
2. **NEVER** skip verification in development (use test secrets instead)
3. **USE** `hmac.compare_digest()` for constant-time comparison
4. **NEVER** use `==` for signature comparison (timing attack vulnerability)
5. **ROTATE** secrets periodically (recommended: every 90 days)

### Common Pitfalls

| Pitfall | Risk | Mitigation |
|---------|-------|------------|
| Hardcoded secrets | Secret exposed in code | Use environment variables |
| Skipping verification in dev | Accidental deployment | Use dev-specific secrets |
| Using `==` for comparison | Timing attacks | Use `hmac.compare_digest()` |
| Logging raw payloads | PII exposure | Log SHA256 hash only |

---

## Rate Limiting

### Why It Matters

Rate limiting prevents:
- Spam/abuse from single users
- DoS attacks on webhook endpoints
- Resource exhaustion from rapid requests
- Automated scraping/bot attacks

### Configuration

**Current Settings**:
- Limit: 10 requests per minute per `user_id`
- Algorithm: Token bucket (allows bursts)
- Scope: Per-platform (Telegram and WhatsApp counted separately)

**Rate Limit Key Format**:
```
{platform}:{sender_id}
```

Examples:
- `telegram:123456789` - Telegram user
- `whatsapp:+1234567890` - WhatsApp user

### Implementation

```python
from slowapi import Limiter

limiter = Limiter(
    key_func=lambda request: f"{platform}:{sender_id}",
    default_limits=["10/minute"]
)
```

### Tuning Rate Limits

To adjust rate limits:

1. **For specific users** (whitelist):
```bash
# Add to .env
IM_RATE_LIMIT_WHITELIST=user@example.com,trusted_user
```

2. **For all users** (global):
```python
# In IMGovernanceService.__init__
default_limits=["20/minute"]  # Increase from 10
```

3. **Per-platform**:
```python
platform_limits = {
    "telegram": "10/minute",
    "whatsapp": "5/minute"  # More restrictive for WhatsApp
}
```

### Monitoring

Monitor rate limit violations:

```sql
-- Check rate limit violations
SELECT platform, sender_id, COUNT(*) as violations
FROM im_audit_logs
WHERE rate_limited = true
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY platform, sender_id
HAVING COUNT(*) > 5
ORDER BY violations DESC;
```

---

## Governance Checks

### Maturity Levels

| Level | IM Access | Description |
|-------|-----------|-------------|
| **STUDENT** | BLOCKED | Cannot receive IM triggers |
| **INTERN** | APPROVAL REQUIRED | Admin approval needed |
| **SUPERVISED** | MONITORED | Auto-approved with logging |
| **AUTONOMOUS** | FULL | No restrictions |

### Implementation

Governance checks happen after signature verification:

```python
await im_governance.check_permissions(sender_id, platform)
```

Checks performed:
1. Is user blocked? (check `im_blocked:{platform}:{sender_id}` in GovernanceCache)
2. Is agent mature enough? (check agent maturity level)
3. Is action allowed? (check action complexity)

### Blocking Users

To block a user:

```python
from core.governance_cache import get_governance_cache

cache = get_governance_cache()
cache.set(f"im_blocked:telegram:123456789", True, ttl=86400)  # 1 day
```

---

## Audit Trail

### What Gets Logged

Every IM interaction creates an `IMAuditLog` entry with:
- `platform`: telegram, whatsapp, etc.
- `sender_id`: User's platform-specific ID
- `user_id`: Atom user ID (if linked)
- `action`: webhook_received, command_run, etc.
- `payload_hash`: SHA256 of payload (PII protection)
- `success`: True/False
- `error_message`: Error details if failed
- `rate_limited`: True if rate limited
- `signature_valid`: False if signature invalid
- `governance_check_passed`: True if governance passed
- `agent_maturity_level`: STUDENT, INTERN, SUPERVISED, AUTONOMOUS
- `timestamp`: When the interaction occurred

### Querying Audit Logs

```sql
-- Recent activity
SELECT * FROM im_audit_logs
ORDER BY timestamp DESC
LIMIT 100;

-- Failed attempts
SELECT platform, sender_id, error_message, COUNT(*)
FROM im_audit_logs
WHERE success = false
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY platform, sender_id, error_message
ORDER BY COUNT(*) DESC;

-- Signature failures (security concern)
SELECT sender_id, COUNT(*) as failed_attempts
FROM im_audit_logs
WHERE signature_valid = false
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY sender_id
HAVING COUNT(*) > 3;
```

### Retention Policy

**Recommended**: 90 days (GDPR compliance)

To set up automatic cleanup:

```python
# Add to celery tasks or cron job
from datetime import datetime, timedelta

cutoff = datetime.utcnow() - timedelta(days=90)
session.query(IMAuditLog).filter(IMAuditLog.timestamp < cutoff).delete()
session.commit()
```

---

## Common Security Pitfalls

### 1. Timing Attacks on Signature Verification

**Problem**: Using `==` for HMAC comparison allows attackers to guess valid signatures by measuring response times.

**Wrong**:
```python
if signature == expected_signature:  # VULNERABLE
    return True
```

**Correct**:
```python
if hmac.compare_digest(signature, expected_signature):  # SAFE
    return True
```

### 2. Logging Sensitive Data

**Problem**: Logging raw webhook payloads exposes PII (phone numbers, message content).

**Wrong**:
```python
logger.info(f"Received payload: {payload}")  # EXPOSES PII
```

**Correct**:
```python
payload_hash = hashlib.sha256(str(payload).encode()).hexdigest()
logger.info(f"Received payload hash: {payload_hash}")  # SAFE
```

### 3. Skipping Rate Limiting for "Trusted" Platforms

**Problem**: All platforms should be rate limited, even if "trusted."

**Wrong**:
```python
if platform == "slack":
    return  # Skip rate limiting for Slack  # VULNERABLE
```

**Correct**:
```python
# Apply rate limiting to ALL platforms
# Use whitelist for specific trusted users if needed
```

### 4. Synchronous Audit Logging

**Problem**: Blocking request processing on database writes increases latency.

**Wrong**:
```python
db.add(audit_log)  # BLOCKS
db.commit()  # BLOCKS
return response
```

**Correct**:
```python
asyncio.create_task(write_audit_log(...))  # NON-BLOCKING
return response
```

### 5. Hardcoded Secrets

**Problem**: Secrets in code can be exposed via Git history.

**Wrong**:
```python
SECRET_TOKEN = "abc123"  # EXPOSED IN CODE
```

**Correct**:
```python
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")  # FROM ENV
```

---

## Production Checklist

Before deploying IM adapters to production:

- [ ] All secrets are in environment variables (not code)
- [ ] Secrets are >32 characters with high entropy
- [ ] HTTPS is enforced (no HTTP webhooks)
- [ ] Rate limiting is enabled and tested
- [ ] Signature verification is tested with invalid signatures
- [ ] Audit trail logging is working
- [ ] Governance checks are active
- [ ] Database backup configured (for audit logs)
- [ ] Monitoring configured (webhook failures, rate limits)
- [ ] Alerting configured (signature failures, blocked users)
- [ ] Secrets rotation schedule defined
- [ ] Incident response plan documented

---

## Incident Response

### Signature Failure Surge

**Symptom**: Sudden increase in `signature_valid=false` logs

**Response**:
1. Check if secret was rotated (timing mismatch)
2. Check if platform is under attack
3. Consider temporarily increasing rate limits
4. Investigate source IPs (if available)

### Rate Limit Violations

**Symptom**: Legitimate users getting 429 errors

**Response**:
1. Check if rate limit is too strict
2. Add affected users to whitelist
3. Check for bug in rate limit key generation
4. Consider increasing limit if legitimate use case

### Governance Blocking

**Symptom**: All users getting 403 from governance checks

**Response**:
1. Check GovernanceCache connectivity
2. Check agent maturity levels
3. Check for recent agent demotions
4. Verify IMGovernanceService is healthy

---

## Further Reading

- [Telegram Bot API Security](https://core.telegram.org/bots/api#securing)
- [WhatsApp Webhook Security](https://developers.facebook.com/docs/whatsapp/webhooks/webhook-verify)
- [OWASP Cheat Sheet: API Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html)
