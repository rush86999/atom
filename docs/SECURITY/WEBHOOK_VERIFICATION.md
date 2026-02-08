# Webhook Signature Verification Guide

> **Last Updated**: February 6, 2026
> **Purpose**: Complete guide to webhook signature verification for Slack, Teams, and Gmail

---

## Overview

Atom enforces webhook signature verification in **production** to prevent:
- Request forgery attacks
- Unauthorized webhook deliveries
- Data injection attacks
- Replay attacks

### Security Model

| Environment | Signature Verification | Behavior |
|-------------|------------------------|----------|
| **Development** | Optional | Logs warning, bypasses verification if secret not configured |
| **Production** | Required | Rejects webhooks if signature missing/invalid |

### Supported Platforms

1. **Slack**: HMAC-SHA256 signature verification
2. **Microsoft Teams**: Bearer token validation
3. **Gmail**: Pub/Sub verification token

---

## Slack Webhook Verification

### Signature Algorithm

Slack uses HMAC-SHA256 to sign webhook requests:

```
signature = HMAC-SHA256(signing_secret, "v0:" + timestamp + request_body)
```

### Required Headers

- `X-Slack-Request-Timestamp`: Unix timestamp
- `X-Slack-Signature`: HMAC-SHA256 signature (format: `v0=<hex_digest>`)

### Configuration

**Environment Variable**:
```bash
export SLACK_SIGNING_SECRET="your-slack-signing-secret-here"
```

**Get Signing Secret**:
1. Go to [Slack API](https://api.slack.com/apps)
2. Select your app
3. Navigate to **Basic Information**
4. Copy **App Credentials** → **Signing Secret**

### Verification Process

**File**: `backend/core/webhook_handlers.py`

```python
def verify_signature(self, timestamp: str, signature: str, body: bytes) -> bool:
    """Verify Slack webhook signature"""
    environment = os.getenv('ENVIRONMENT', 'development')

    # Check if signing secret is configured
    if not self.signing_secret:
        if environment == 'production':
            logger.error("🚨 SECURITY: Slack signing secret not configured in production. Rejecting webhook.")
            return False
        else:
            logger.warning("⚠️ SECURITY WARNING: No Slack signing secret in development. Webhook signature verification bypassed.")
            return True

    # Verify signature
    try:
        basestring = f"v0:{timestamp}".encode() + body
        expected_signature = "v0=" + hmac.new(
            self.signing_secret.encode(),
            basestring,
            hashlib.sha256
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_signature, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False
```

### Timestamp Validation

**Prevent Replay Attacks**:
```python
from datetime import datetime, timedelta

def validate_timestamp(timestamp: str) -> bool:
    """Validate timestamp to prevent replay attacks"""
    try:
        request_time = datetime.fromtimestamp(int(timestamp))
        current_time = datetime.now()

        # Reject requests older than 5 minutes
        if current_time - request_time > timedelta(minutes=5):
            logger.warning("Webhook request too old")
            return False

        return True
    except Exception as e:
        logger.error(f"Invalid timestamp: {e}")
        return False
```

### Testing

**Valid Signature**:
```bash
# Send test request with signature
python3 -c "
import hmac
import hashlib
import time
import requests

signing_secret = 'your-secret'
timestamp = str(int(time.time()))
body = b'{"type":"url_verification"}'

basestring = f'v0:{timestamp}'.encode() + body
signature = 'v0=' + hmac.new(
    signing_secret.encode(),
    basestring,
    hashlib.sha256
).hexdigest()

requests.post('http://localhost:8000/api/webhooks/slack',
    data=body,
    headers={
        'X-Slack-Request-Timestamp': timestamp,
        'X-Slack-Signature': signature
    }
)
"
```

**Invalid Signature**:
```bash
# Should reject in production
curl -X POST http://localhost:8000/api/webhooks/slack \
  -H "X-Slack-Request-Timestamp: $(date +%s)" \
  -H "X-Slack-Signature: invalid_signature" \
  -d '{"type":"url_verification"}'
```

---

## Microsoft Teams Webhook Verification

### Authentication Method

Teams uses Bearer token authentication:

```
Authorization: Bearer <token>
```

### Configuration

**Environment Variable**:
```bash
export MICROSOFT_WEBHOOK_SECRET="your-microsoft-webhook-secret-here"
```

### Verification Process

**File**: `backend/core/webhook_handlers.py`

```python
def verify_teams_token(self, auth_header: str) -> bool:
    """Verify Microsoft Teams Bearer token"""
    environment = os.getenv('ENVIRONMENT', 'development')

    if not auth_header:
        if environment == 'production':
            logger.error("🚨 SECURITY: Missing Authorization header for Teams webhook in production")
            return False
        else:
            logger.warning("⚠️ SECURITY WARNING: No Authorization header in development")
            return True

    # Extract token
    if not auth_header.startswith('Bearer '):
        logger.warning("Invalid Authorization header format")
        return False

    token = auth_header[7:]  # Remove 'Bearer ' prefix

    # Verify token
    if not self.webhook_secret:
        if environment == 'production':
            logger.error("🚨 SECURITY: Teams webhook secret not configured in production")
            return False
        else:
            logger.warning("⚠️ SECURITY WARNING: No Teams webhook secret in development")
            return True

    is_valid = hmac.compare_digest(token, self.webhook_secret)

    if not is_valid:
        logger.warning("Invalid Teams webhook token")

    return is_valid
```

### Testing

**Valid Token**:
```bash
curl -X POST http://localhost:8000/api/webhooks/teams \
  -H "Authorization: Bearer your-microsoft-webhook-secret-here" \
  -H "Content-Type: application/json" \
  -d '{"type":"message","text":"Hello"}'
```

**Invalid Token**:
```bash
# Should reject in production
curl -X POST http://localhost:8000/api/webhooks/teams \
  -H "Authorization: Bearer invalid_token" \
  -H "Content-Type: application/json" \
  -d '{"type":"message","text":"Hello"}'
```

---

## Gmail Pub/Sub Verification

### Verification Method

Gmail uses Pub/Sub push notifications with verification tokens:

```
?verification_token=challenge_token
```

### Configuration

**Environment Variable**:
```bash
export GMAIL_PUBSUB_VERIFICATION_TOKEN="your-gmail-verification-token"
```

### Verification Process

**File**: `backend/core/webhook_handlers.py`

```python
def verify_gmail_token(self, token: str) -> bool:
    """Verify Gmail Pub/Sub verification token"""
    environment = os.getenv('ENVIRONMENT', 'development')

    if not self.verification_token:
        if environment == 'production':
            logger.error("🚨 SECURITY: Gmail verification token not configured in production")
            return False
        else:
            logger.warning("⚠️ SECURITY WARNING: No Gmail verification token in development")
            return True

    is_valid = hmac.compare_digest(token, self.verification_token)

    if not is_valid:
        logger.warning("Invalid Gmail verification token")

    return is_valid
```

### Testing

**Valid Token**:
```bash
curl -X POST "http://localhost:8000/api/webhooks/gmail?verification_token=your-gmail-verification-token" \
  -H "Content-Type: application/json" \
  -d '{"message":{"data":"base64_encoded_data"}}'
```

**Invalid Token**:
```bash
# Should reject in production
curl -X POST "http://localhost:8000/api/webhooks/gmail?verification_token=invalid_token" \
  -H "Content-Type: application/json" \
  -d '{"message":{"data":"base64_encoded_data"}}'
```

---

## Security Best Practices

### 1. Secret Management

**Use Environment Variables**:
```bash
# Never hardcode secrets in code
export SLACK_SIGNING_SECRET="..."
export MICROSOFT_WEBHOOK_SECRET="..."
export GMAIL_PUBSUB_VERIFICATION_TOKEN="..."
```

**Rotate Secrets Regularly**:
```bash
# Generate new secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update environment variable
export SLACK_SIGNING_SECRET="new_secret"

# Restart workers
systemctl restart atom-backend atom-workers
```

### 2. Secure Transmission

**Use HTTPS in Production**:
```nginx
server {
    listen 443 ssl;
    servername webhook.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /api/webhooks/ {
        proxy_pass http://localhost:8000;
    }
}
```

### 3. Logging

**Log Security Events**:
```python
def _log_security_event(self, event_type: str, severity: str, details: dict):
    """Log security events for audit trail"""
    logger.info(f"Webhook Security Audit: {event_type} - {severity} - {details}")

    # Also write to SecurityAuditLog table
    # (when implemented)
```

**Audit Log Entries**:
- `webhook_signature_missing` - CRITICAL in production
- `webhook_signature_invalid` - WARNING
- `webhook_signature_bypass_dev` - INFO (development only)
- `webhook_timestamp_invalid` - WARNING

### 4. Rate Limiting

**Prevent Abuse**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/webhooks/slack")
@limiter.limit("10/minute")
async def slack_webhook(request: Request):
    ...
```

### 5. IP Whitelisting

**Allow Only Known IPs**:
```python
ALLOWED_SLACK_IPS = [
    '3.235.147.50',    # Slack webhook IP range
    '52.72.107.237',
    # Add more Slack IPs
]

def verify_ip(request: Request) -> bool:
    """Verify request comes from allowed IP"""
    client_ip = request.client.host
    return client_ip in ALLOWED_SLACK_IPS
```

---

## Development vs Production Behavior

### Development Mode

```bash
export ENVIRONMENT=development
```

**Behavior**:
- Logs warnings if secrets not configured
- Bypasses signature verification if secret missing
- Allows testing without real secrets
- Still validates signature if secret provided

### Production Mode

```bash
export ENVIRONMENT=production
```

**Behavior**:
- Logs CRITICAL errors if secrets not configured
- **Rejects** webhooks if signature missing/invalid
- Requires all secrets to be configured
- Enforces timestamp validation (Slack)

---

## Troubleshooting

### Issue: Webhooks Rejected in Production

**Symptoms**: Webhooks returning 401/403 errors

**Diagnosis**:
```bash
# Check security status
curl http://localhost:8000/api/webhooks/security-status

# Check environment variable
echo $SLACK_SIGNING_SECRET
```

**Solutions**:
1. Set environment variable: `export SLACK_SIGNING_SECRET="..."`
2. Restart backend: `systemctl restart atom-backend`
3. Verify secret is correct (copy from Slack app settings)

### Issue: Signature Verification Failing

**Symptoms**: Valid webhooks rejected

**Diagnosis**:
```bash
# Check logs
tail -f logs/atom.log | grep "webhook"

# Verify signature calculation
python3 -c "
import hmac
import hashlib
signing_secret = 'your-secret'
timestamp = '1234567890'
body = b'test'
basestring = f'v0:{timestamp}'.encode() + body
signature = 'v0=' + hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
print(f'Expected signature: {signature}')
"
```

**Solutions**:
1. Verify signing secret matches Slack app settings
2. Check request body isn't modified by middleware
3. Verify timestamp header is included
4. Check for encoding issues (UTF-8)

### Issue: Timestamp Validation Failing

**Symptoms**: Webhooks rejected due to old timestamp

**Diagnosis**:
```bash
# Check server time
date +%s

# Compare with request timestamp
```

**Solutions**:
1. Sync server time: `ntpdate pool.ntp.org`
2. Check for clock skew
3. Increase timestamp tolerance (if needed)

---

## Testing Checklist

### Development Testing

- [ ] Webhook receives requests without secret configured
- [ ] Warning logged when secret missing
- [ ] Signature validated when secret provided
- [ ] Invalid signatures rejected

### Production Testing

- [ ] All secrets configured
- [ ] Valid signatures accepted
- [ ] Invalid signatures rejected
- [ ] Missing signatures rejected
- [ ] Timestamp validation working
- [ ] Security events logged

### Load Testing

```bash
# Test webhook throughput
ab -n 1000 -c 10 -p webhook.json -T application/json \
  -H "X-Slack-Request-Timestamp: $(date +%s)" \
  -H "X-Slack-Signature: valid_signature" \
  http://localhost:8000/api/webhooks/slack
```

---

## References

### Official Documentation
- [Slack: Verifying requests from Slack](https://api.slack.com/authentication/verifying-requests-from-slack)
- [Microsoft: Bot Framework authentication](https://docs.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-authentication)
- [Google: Pub/Sub push authentication](https://cloud.google.com/pubsub/docs/push#authentication_and_authorization)

### Atom Documentation
- [DEVELOPMENT.md](../DEVELOPMENT.md) - Security Configuration section
- [SECURITY/AUTHENTICATION.md](AUTHENTICATION.md) - Authentication system
- [backend/core/webhook_handlers.py](../../backend/core/webhook_handlers.py) - Implementation
- [backend/api/security_routes.py](../../backend/api/security_routes.py) - Security endpoints

### Security Endpoints
- `GET /api/webhooks/security-status` - Check webhook security status
- `GET /api/security/configuration` - Check security configuration
