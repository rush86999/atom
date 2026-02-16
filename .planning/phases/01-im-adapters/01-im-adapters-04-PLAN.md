---
phase: 01-im-adapters
plan: 04
type: execute
wave: 3
depends_on: ["01-im-adapters-01", "01-im-adapters-02"]
files_modified:
  - backend/docs/IM_ADAPTER_SETUP.md
  - backend/docs/IM_SECURITY_BEST_PRACTICES.md
  - backend/README.md
autonomous: true
user_setup: []

must_haves:
  truths:
    - "IM_ADAPTER_SETUP.md exists with Telegram and WhatsApp setup instructions"
    - "IM_SECURITY_BEST_PRACTICES.md exists with webhook verification and rate limiting guidance"
    - "Environment variables documented (TELEGRAM_SECRET_TOKEN, WHATSAPP_APP_SECRET, etc.)"
    - "README.md updated with IM adapter integration section"
    - "Troubleshooting section covers common issues (verification failures, rate limits)"
  artifacts:
    - path: "backend/docs/IM_ADAPTER_SETUP.md"
      provides: "Step-by-step setup guide for Telegram and WhatsApp integration"
      min_lines: 200
      contains: "Telegram Setup", "WhatsApp Setup", "Environment Variables", "Webhook Configuration"
    - path: "backend/docs/IM_SECURITY_BEST_PRACTICES.md"
      provides: "Security guidelines for IM adapter integration"
      min_lines: 150
      contains: "Webhook Verification", "Rate Limiting", "Audit Trail", "Common Pitfalls"
  key_links:
    - from: "backend/docs/IM_ADAPTER_SETUP.md"
      to: "backend/integrations/telegram_routes.py"
      via: "References webhook endpoint configuration"
      pattern: "/api/telegram/webhook"
    - from: "backend/docs/IM_ADAPTER_SETUP.md"
      to: "backend/integrations/whatsapp_routes.py"
      via: "References webhook endpoint configuration"
      pattern: "/api/whatsapp/webhook"
    - from: "backend/docs/IM_SECURITY_BEST_PRACTICES.md"
      to: "backend/core/im_governance_service.py"
      via: "Explains governance security features"
      pattern: "IMGovernanceService"
---

<objective>
Create comprehensive documentation for IM adapter setup and security best practices. Documentation should enable developers to integrate Telegram and WhatsApp webhooks with proper security configuration, understanding of rate limiting, and troubleshooting guidance.

Purpose: Enable smooth adoption of IM adapters with security-first mindset
Output: Complete setup guide and security best practices documentation
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-im-adapters/01-im-adapters-CONTEXT.md
@.planning/phases/01-im-adapters/01-im-adapters-RESEARCH.md
@.planning/phases/01-im-adapters/01-im-adapters-01-SUMMARY.md
@.planning/phases/01-im-adapters/01-im-adapters-02-SUMMARY.md

# Existing documentation patterns
@backend/docs/README.md
@backend/CLAUDE.md
@backend/README.md
</context>

<tasks>

<task type="auto">
  <name>Create IM_ADAPTER_SETUP.md with step-by-step instructions</name>
  <files>backend/docs/IM_ADAPTER_SETUP.md</files>
  <action>
Create backend/docs/IM_ADAPTER_SETUP.md (300-400 lines):

```markdown
# IM Adapter Setup Guide

Complete guide for integrating Telegram and WhatsApp with Atom Agent OS.

## Overview

Atom supports incoming webhooks from Telegram and WhatsApp, allowing users to interact with agents via IM platforms. All IM interactions are secured with:
- Webhook signature verification (prevents spoofing)
- Rate limiting (10 req/min per user)
- Governance checks (STUDENT agents blocked)
- Comprehensive audit trail

## Prerequisites

- Atom backend running (port 8000)
- Public HTTPS URL for webhook endpoints (use ngrok for development)
- Telegram Bot account (free)
- WhatsApp Business account (Meta Business Suite)

---

## Telegram Setup

### Step 1: Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow prompts to name your bot (e.g., "AtomAgentBot")
4. BotFather will provide a **Bot Token** (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Save this token - you'll need it for environment configuration

### Step 2: Configure Webhook

Set your webhook URL to point to Atom:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-atom-domain.com/api/telegram/webhook",
    "secret_token": "YOUR_SECRET_TOKEN"
  }'
```

Replace:
- `<YOUR_BOT_TOKEN>`: Token from BotFather
- `https://your-atom-domain.com`: Your public Atom URL
- `YOUR_SECRET_TOKEN`: Random string for webhook verification (generate with: `openssl rand -hex 32`)

### Step 3: Configure Environment Variables

Add to your `.env` file:

```bash
# Telegram Configuration
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_SECRET_TOKEN=your_random_secret_token_here
```

### Step 4: Verify Setup

Test your bot:

```bash
# Check webhook status
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"

# Send test message to your bot in Telegram
# Check logs: tail -f logs/atom.log | grep telegram
```

Expected response: `{"ok":true,"result":{"url":"https://...","has_custom_certificate":false,...}}`

---

## WhatsApp Setup

### Step 1: Create WhatsApp Business App

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create a new app (select "Business" type)
3. Add "WhatsApp" product
4. Complete WhatsApp setup (phone number verification)

### Step 2: Get Credentials

From your WhatsApp app settings:
- **Phone Number ID**: Found in WhatsApp > API Setup
- **Access Token**: Generate temporary token (for production, use permanent token)
- **App Secret**: Found in app Settings > Basic
- **Verify Token**: Set your own random string

### Step 3: Configure Webhook

1. In Meta Dashboard, go to WhatsApp > Configuration
2. Click "Edit" next to Webhook
3. Enter: `https://your-atom-domain.com/api/whatsapp/webhook`
4. Enter your **Verify Token** (random string)
5. Click "Verify and Save"

### Step 4: Subscribe to Webhook Events

Subscribe to these events:
- `messages`
- `message_status` (optional, for delivery receipts)

### Step 5: Configure Environment Variables

Add to your `.env` file:

```bash
# WhatsApp Configuration
WHATSAPP_ACCESS_TOKEN=your_access_token_here
WHATSAPP_APP_SECRET=your_app_secret_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
```

### Step 6: Verify Setup

Test your webhook:

```bash
# Send test message via WhatsApp to your configured number
# Check logs: tail -f logs/atom.log | grep whatsapp
```

---

## Development with Ngrok

For local development, use [ngrok](https://ngrok.com/) to expose your local server:

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/download

# Start ngrok tunnel
ngrok http 8000

# Use the HTTPS URL in webhook configuration
# Example: https://abc123.ngrok.io/api/telegram/webhook
```

---

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram Bot API token | `123456789:ABCdef...` |
| `TELEGRAM_SECRET_TOKEN` | Yes | Webhook verification secret | `random_hex_string` |
| `WHATSAPP_ACCESS_TOKEN` | Yes (for WhatsApp) | WhatsApp Cloud API token | `EAAabcdef123...` |
| `WHATSAPP_APP_SECRET` | Yes (for WhatsApp) | App secret for signature verification | `abc123def456` |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes (for WhatsApp) | Phone number ID from Meta | `123456789012345` |

---

## Testing Your Integration

### Telegram Test Commands

Send these messages to your bot:

```
/start - Initialize bot
/agents - List available agents
/run <agent> <task> - Execute agent task
/status - Check bot status
/help - Show available commands
```

### WhatsApp Test Commands

```
/run <agent> <task> - Execute agent task
/agents - List available agents
/status - Check bot status
```

---

## Troubleshooting

### Telegram: Webhook Not Receiving Messages

**Symptom**: Messages sent to bot not appearing in logs

**Solutions**:
1. Verify webhook is set: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
2. Check `TELEGRAM_BOT_TOKEN` is correct
3. Check `TELEGRAM_SECRET_TOKEN` matches what you set
4. Check firewall allows incoming HTTPS traffic

### WhatsApp: Verification Fails

**Symptom**: Webhook verification returns 403

**Solutions**:
1. Verify `WHATSAPP_APP_SECRET` matches Meta dashboard
2. Check verify token matches in both places
3. Ensure webhook URL is publicly accessible (not localhost)
4. Check ngrok is running if using for development

### Rate Limiting Issues

**Symptom**: Legitimate users getting 429 errors

**Solutions**:
1. Current limit: 10 req/min per user_id
2. Increase by modifying `IMGovernanceService` (not recommended for production)
3. Add user to whitelist: `IM_RATE_LIMIT_WHITELIST=user@example.com`

### Governance Blocking

**Symptom**: Commands return 403 Forbidden

**Solutions**:
1. Check agent maturity level (STUDENT agents blocked from IM)
2. Check if user is blocked: `im_blocked:telegram:user_id` in GovernanceCache
3. Verify IMGovernanceService is initialized

---

## Security Checklist

Before deploying to production:

- [ ] All webhook verification secrets are strong (>32 characters)
- [ ] HTTPS is enforced (HTTP rejected)
- [ ] Rate limiting is enabled (10 req/min)
- [ ] Audit trail logging is enabled
- [ ] Governance checks are active
- [ ] Webhook URLs are not guessable
- [ ] Secrets are stored securely (not in code)
- [ ] ngrok is NOT used in production

---

## Next Steps

After setup:
1. Test basic commands (see Testing section)
2. Review security best practices (see `IM_SECURITY_BEST_PRACTICES.md`)
3. Configure agent permissions for IM access
4. Set up monitoring for webhook failures
5. Configure alerting for rate limit violations

---

## Support

For issues or questions:
- Check logs: `tail -f logs/atom.log | grep -E "telegram|whatsapp"`
- Review audit trail: `SELECT * FROM im_audit_logs ORDER BY timestamp DESC LIMIT 100;`
- Check health endpoints: `/api/telegram/health`, `/api/whatsapp/health`
```
  </action>
  <verify>
```bash
test -f backend/docs/IM_ADAPTER_SETUP.md
grep -q "Telegram Setup" backend/docs/IM_ADAPTER_SETUP.md
grep -q "WhatsApp Setup" backend/docs/IM_ADAPTER_SETUP.md
grep -q "Environment Variables" backend/docs/IM_ADAPTER_SETUP.md
grep -q "Troubleshooting" backend/docs/IM_ADAPTER_SETUP.md
```
  </verify>
  <done>
IM_ADAPTER_SETUP.md created with:
- Complete Telegram setup guide (BotFather, webhook, env vars)
- Complete WhatsApp setup guide (Meta app, webhook, env vars)
- Ngrok instructions for local development
- Environment variables reference table
- Testing commands for both platforms
- Troubleshooting section for common issues
- Security checklist for production deployment
  </done>
</task>

<task type="auto">
  <name>Create IM_SECURITY_BEST_PRACTICES.md</name>
  <files>backend/docs/IM_SECURITY_BEST_PRACTICES.md</files>
  <action>
Create backend/docs/IM_SECURITY_BEST_PRACTICES.md (250-350 lines):

```markdown
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
```
  </action>
  <verify>
```bash
test -f backend/docs/IM_SECURITY_BEST_PRACTICES.md
grep -q "Webhook Signature Verification" backend/docs/IM_SECURITY_BEST_PRACTICES.md
grep -q "Rate Limiting" backend/docs/IM_SECURITY_BEST_PRACTICES.md
grep -q "Common Security Pitfalls" backend/docs/IM_SECURITY_BEST_PRACTICES.md
grep -q "Production Checklist" backend/docs/IM_SECURITY_BEST_PRACTICES.md
```
  </verify>
  <done>
IM_SECURITY_BEST_PRACTICES.md created with:
- Webhook signature verification explanation
- Rate limiting configuration and tuning guide
- Governance checks by maturity level
- Audit trail logging details
- 5 common security pitfalls with correct/incorrect examples
- Production deployment checklist
- Incident response procedures
  </done>
</task>

<task type="auto">
  <name>Update README.md with IM adapter section</name>
  <files>backend/README.md</files>
  <action>
Add IM Adapters section to backend/README.md (after existing features):

Find the appropriate location (e.g., after "Features" or "Integrations" section) and add:

```markdown
## IM Adapters

Atom supports integration with Telegram and WhatsApp for agent interactions via IM platforms.

### Quick Start

1. **Telegram**:
   ```bash
   # Set environment variables
   export TELEGRAM_BOT_TOKEN="your_bot_token"
   export TELEGRAM_SECRET_TOKEN="your_secret_token"

   # Set webhook
   curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
     -d '{"url": "https://your-domain.com/api/telegram/webhook", "secret_token": "$TELEGRAM_SECRET_TOKEN"}'
   ```

2. **WhatsApp**:
   ```bash
   # Set environment variables
   export WHATSAPP_ACCESS_TOKEN="your_access_token"
   export WHATSAPP_APP_SECRET="your_app_secret"
   export WHATSAPP_PHONE_NUMBER_ID="your_phone_number_id"

   # Configure webhook in Meta Dashboard
   # URL: https://your-domain.com/api/whatsapp/webhook
   ```

### Features

- **Webhook Signature Verification**: All incoming webhooks verified via HMAC
- **Rate Limiting**: 10 requests/minute per user (configurable)
- **Governance Integration**: STUDENT agents blocked, INTERN+ allowed with checks
- **Audit Trail**: All interactions logged to `im_audit_logs` table

### Documentation

- [Setup Guide](docs/IM_ADAPTER_SETUP.md) - Complete setup instructions
- [Security Best Practices](docs/IM_SECURITY_BEST_PRACTICES.md) - Security guidelines

### Endpoints

| Platform | Webhook | Health |
|----------|---------|--------|
| Telegram | `/api/telegram/webhook` | `/api/telegram/health` |
| WhatsApp | `/api/whatsapp/webhook` | `/api/whatsapp/health` |

### Supported Commands

```
/start - Initialize bot
/agents - List available agents
/run <agent> <task> - Execute agent task
/status - Check bot status
/help - Show available commands
```

### Security

All IM adapters go through `IMGovernanceService` which provides:
- Webhook signature verification (prevents spoofing)
- Rate limiting (prevents abuse)
- Governance checks (ensures appropriate agent maturity)
- Comprehensive audit trail (compliance)
```

Also add a reference in the main README.md at the project root if it exists.
  </action>
  <verify>
```bash
grep -q "IM Adapters" backend/README.md
grep -q "IM_ADAPTER_SETUP.md" backend/README.md
grep -q "IMGovernanceService" backend/README.md
```
  </verify>
  <done>
README.md updated with:
- IM Adapters section with quick start for Telegram and WhatsApp
- Features list (webhook verification, rate limiting, governance, audit trail)
- Documentation links
- Endpoint table
- Supported commands
- Security overview
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. IM_ADAPTER_SETUP.md exists and is complete
2. IM_SECURITY_BEST_PRACTICES.md exists and is complete
3. README.md has IM Adapters section
4. All documentation is internally consistent
5. Setup guide follows actual implementation
6. Security guide covers all critical areas
</verification>

<success_criteria>
- Developer can follow IM_ADAPTER_SETUP.md to set up Telegram integration
- Developer can follow IM_ADAPTER_SETUP.md to set up WhatsApp integration
- Security team can review IM_SECURITY_BEST_PRACTICES.md for compliance
- All documentation links resolve correctly
- README.md provides clear entry point to IM adapter docs
</success_criteria>

<output>
After completion, create `.planning/phases/01-im-adapters/01-im-adapters-04-SUMMARY.md` with:
- Documentation files created
- Sections included in each document
- Word/line counts
- Any diagrams or tables included
</output>
