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

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_SECRET_TOKEN` | None | Secret token for Telegram webhook verification |
| `TELEGRAM_BOT_TOKEN` | None | Bot API token for sending messages |
| `WHATSAPP_VERIFY_TOKEN` | `default_random_token_change_in_prod` | Verify token for WhatsApp webhook setup |
| `WHATSAPP_APP_SECRET` | None | App secret for HMAC signature verification |
| `IM_RATE_LIMIT_REQUESTS` | 10 | Max requests per window per user |
| `IM_RATE_LIMIT_WINDOW_SECONDS` | 60 | Time window in seconds |

**Security Notes:**
- Generate secrets with: `openssl rand -hex 16` or `openssl rand -base64 32`
- Never commit secrets to Git
- Rotate secrets every 90 days
- Use different secrets for dev/staging/production

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

### Timing Attack Prevention

When comparing secret tokens (webhook signatures, API keys), ALWAYS use constant-time comparison:

**VULNERABLE (timing attack possible):**
```python
if header_token == self.secret_token:  # VULNERABLE
    return True
```

**SECURE (constant-time):**
```python
import hmac
return hmac.compare_digest(header_token, self.secret_token)  # SAFE
```

**Why:** String comparison with `==` short-circuits on first mismatch. Attackers can measure response times to guess valid tokens character-by-character. `hmac.compare_digest()` always compares full strings, preventing this attack vector.

**Required for:**
- Telegram: `X-Telegram-Bot-Api-Secret-Token` header
- WhatsApp: `X-Hub-Signature-256` HMAC verification
- All webhook signature validations

**Implementation in Atom:**
- `backend/core/communication/adapters/telegram.py` - Uses `hmac.compare_digest()`
- `backend/core/communication/adapters/whatsapp.py` - Uses `hmac.compare_digest()`

---

## Rate Limiting

### Why It Matters

Rate limiting prevents:
- Spam/abuse from single users
- DoS attacks on webhook endpoints
- Resource exhaustion from rapid requests
- Automated scraping/bot attacks

### Implementation

IMGovernanceService uses a **sliding window** rate limiting algorithm:

#### Algorithm

For each unique key `{platform}:{sender_id}`:
1. Maintain list of request timestamps
2. Remove timestamps older than window (60s)
3. Reject if >= 10 requests in window
4. Otherwise, add current timestamp and allow

#### Configuration

**Current Settings**:
- Limit: 10 requests per minute per `user_id`
- Algorithm: Sliding window (allows bursts)
- Scope: Per-platform (Telegram and WhatsApp counted separately)

**Rate Limit Key Format**:
```
{platform}:{sender_id}
```

Examples:
- `telegram:123456789` - Telegram user
- `whatsapp:+1234567890` - WhatsApp user

#### Characteristics

- **Burst-tolerant**: All 10 requests can arrive simultaneously
- **Memory-efficient**: Old timestamps automatically cleaned up
- **Single-worker**: In-memory store doesn't share across workers
- **Latency**: <1ms per check (in-memory lookup)

### Tuning Rate Limits

To adjust rate limits:

1. **For specific users** (whitelist):
```bash
# Add to .env
IM_RATE_LIMIT_WHITELIST=user@example.com,trusted_user
```

2. **For all users** (global):
```bash
# Set environment variables
IM_RATE_LIMIT_REQUESTS=20  # Increase from 10
IM_RATE_LIMIT_WINDOW_SECONDS=60
```

3. **Per-platform** (requires code modification):
```python
# In IMGovernanceService.__init__
platform_rate_limits = {
    "telegram": (10, 60),  # 10 requests per 60 seconds
    "whatsapp": (5, 60),   # More restrictive for WhatsApp
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

#### Production Notes

For multi-worker deployments (gunicorn -w 4):
- Each worker has its own rate limit store
- Effective limit = workers * 10 requests/minute
- Solution: Use Redis-backed rate limiting for distributed deployments

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

### 1. Logging Sensitive Data

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

### 2. Skipping Rate Limiting for "Trusted" Platforms

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

### 3. Synchronous Audit Logging

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

### 4. Hardcoded Secrets

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
