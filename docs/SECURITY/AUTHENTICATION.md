# Authentication Guide

> **Last Updated**: February 6, 2026
> **Purpose**: Complete guide to authentication, OAuth 2.0, and session management in Atom

---

## Overview

Atom provides comprehensive authentication with:
- **OAuth 2.0 Integration**: 117+ service integrations (Google, Microsoft, GitHub, Slack, Asana, etc.)
- **Session Management**: Secure session handling with JWT tokens
- **Request Validation**: User ID and email format validation
- **Multi-User Support**: Per-user credential encryption with Fernet
- **Development Mode**: Temporary user creation for testing

### Authentication Flow

```
User → OAuth Provider → Atom Backend → Session Token → Protected Resources
```

---

## OAuth 2.0 Integration

### Supported Providers

| Category | Providers |
|----------|-----------|
| **Cloud Storage** | Google Drive, Dropbox, OneDrive, Box |
| **Communication** | Gmail, Outlook, Slack, Microsoft Teams |
| **Project Management** | Asana, Trello, Jira, GitHub Projects |
| **CRM** | HubSpot, Salesforce, Pipedrive |
| **Productivity** | Notion, Airtable, Monday.com |
| **Social Media** | Twitter, LinkedIn, Facebook, Instagram |
| **Development** | GitHub, GitLab, Bitbucket |

**Total**: 117+ integrations

### OAuth Flow

#### 1. Authorization Code Flow

**Step 1: User Authorization**
```http
GET /oauth/authorize?provider=google&redirect_uri=http://localhost:3000/oauth/callback
```

**Step 2: User Grants Permission**
```
User → Clicks "Authorize" → Redirect to Atom with code
```

**Step 3: Token Exchange**
```python
# backend/api/oauth_routes.py
async def exchange_code_for_token(provider: str, code: str):
    # Exchange authorization code for access token
    token_response = await oauth_client.get_token(
        provider=provider,
        code=code,
        redirect_uri=redirect_uri
    )
    return token_response
```

**Step 4: Store Encrypted Credentials**
```python
# backend/core/credential_manager.py
def store_credential(user_id: str, provider: str, access_token: str):
    # Encrypt token with Fernet
    encrypted_token = encryption_service.encrypt(access_token)

    # Store in database
    credential = UserCredential(
        user_id=user_id,
        provider=provider,
        encrypted_token=encrypted_token
    )
    db.add(credential)
    db.commit()
```

### Configuration

**Environment Variables**:
```bash
# Google OAuth
export GOOGLE_CLIENT_ID="your-google-client-id"
export GOOGLE_CLIENT_SECRET="your-google-client-secret"
export GOOGLE_REDIRECT_URI="http://localhost:3000/oauth/callback/google"

# Microsoft OAuth
export MICROSOFT_CLIENT_ID="your-microsoft-client-id"
export MICROSOFT_CLIENT_SECRET="your-microsoft-client-secret"

# GitHub OAuth
export GITHUB_CLIENT_ID="your-github-client-id"
export GITHUB_CLIENT_SECRET="your-github-client-secret"

# Slack OAuth
export SLACK_CLIENT_ID="your-slack-client-id"
export SLACK_CLIENT_SECRET="your-slack-client-secret"

# ... (add for all 117+ providers)
```

---

## Request Validation

### X-User-ID Header

**Purpose**: Identify the current user for API requests

**Format**:
```http
X-User-ID: user_123abc
```

**Validation Rules**:
- Must match regex: `^[a-zA-Z0-9_\-]+$`
- Must be authenticated user
- Required for protected endpoints

### Email Validation

**Format**: `^[^@]+@[^@]+\.[^@]+$`

**Examples**:
- ✅ Valid: `user@example.com`
- ❌ Invalid: `user@` (missing domain)
- ❌ Invalid: `@example.com` (missing local part)
- ❌ Invalid: `user@example` (missing TLD)

### get_current_user() Function

**File**: `backend/core/auth.py`

```python
from fastapi import Header, HTTPException
import re

async def get_current_user(
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Get current authenticated user from X-User-ID header"""

    # Validate user ID format
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="X-User-ID header required"
        )

    # Validate user ID format (prevent injection)
    if not re.match(r'^[a-zA-Z0-9_\-]+$', x_user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID format"
        )

    # Check if user exists
    user = db.query(User).filter(User.id == x_user_id).first()
    if not user:
        # In development, create temporary user
        if os.getenv('ALLOW_DEV_TEMP_USERS') == 'true':
            user = create_temp_user(x_user_id)
        else:
            raise HTTPException(
                status_code=401,
                detail="User not found"
            )

    return user
```

### Usage in Endpoints

```python
from fastapi import Depends, Header
from core.auth import get_current_user

@app.get("/api/integrations/slack/channels")
async def list_slack_channels(
    current_user: User = Depends(get_current_user)
):
    """List Slack channels for current user"""
    # current_user.id is guaranteed to be valid
    slack_service = get_slack_service(current_user.id)
    return await slack_service.list_channels()
```

---

## Session Management

### JWT Tokens

**Token Structure**:
```json
{
  "user_id": "user_123abc",
  "email": "user@example.com",
  "exp": 1675875200,
  "iat": 1675788800
}
```

**Configuration**:
```bash
# Token expiration (24 hours)
export JWT_EXPIRATION=86400

# Secret key for signing
export SECRET_KEY="your-secret-key-here"
```

### Token Creation

```python
import jwt
from datetime import datetime, timedelta

def create_access_token(user_id: str, email: str):
    """Create JWT access token"""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION),
        "iat": datetime.utcnow()
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token
```

### Token Validation

```python
def verify_access_token(token: str):
    """Verify JWT access token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

## Development Mode

### Temporary User Creation

**Purpose**: Allow testing without full user registration

**Configuration**:
```bash
# Enable temporary user creation (DEVELOPMENT ONLY)
export ALLOW_DEV_TEMP_USERS=true
```

**Behavior**:
- Creates temporary user if X-User-ID not found
- Logs warning for each temporary user creation
- Disabled by default in production

**Auto-Disabled**:
```python
if os.getenv('ENVIRONMENT', 'development') == 'production':
    if os.getenv('ALLOW_DEV_TEMP_USERS') == 'true':
        logger.error("🚨 CRITICAL: ALLOW_DEV_TEMP_USERS is true in production!")
        # This is a security risk
```

### Best Practices

**Development**:
```bash
# Enable for testing
export ENVIRONMENT=development
export ALLOW_DEV_TEMP_USERS=true
```

**Production**:
```bash
# MUST be disabled
export ENVIRONMENT=production
export ALLOW_DEV_TEMP_USERS=false
```

---

## Security Best Practices

### 1. Credential Encryption

**Fernet Encryption**:
```python
from cryptography.fernet import Fernet

# Generate encryption key
encryption_key = Fernet.generate_key()

# Encrypt token
f = Fernet(encryption_key)
encrypted_token = f.encrypt(access_token.encode())

# Decrypt token
decrypted_token = f.decrypt(encrypted_token).decode()
```

### 2. Secret Key Management

**Generate Secure Keys**:
```bash
# Generate SECRET_KEY
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate ENCRYPTION_KEY
python -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
```

**Production Configuration**:
```bash
# Never use default values in production
export SECRET_KEY="atom-secret-key-change-in-production"  # ❌ BAD
export SECRET_KEY="generated-secure-key-here"             # ✅ GOOD

# Always validate configuration
python backend/scripts/validate_config.py
```

### 3. OAuth Token Storage

**Encryption at Rest**:
```python
# Store encrypted tokens
encrypted_token = encrypt(access_token)
credential = UserCredential(
    user_id=user_id,
    provider=provider,
    encrypted_token=encrypted_token  # ✅ Encrypted
)

# Never store plaintext
credential = UserCredential(
    user_id=user_id,
    provider=provider,
    access_token=access_token  # ❌ PLAINTEXT - BAD
)
```

### 4. Token Refresh

**Automatic Refresh**:
```python
async def refresh_access_token(user_id: str, provider: str):
    """Refresh OAuth access token"""
    credential = get_credential(user_id, provider)

    # Check if token needs refresh
    if credential.expires_at < datetime.now():
        # Refresh token
        new_token = await oauth_client.refresh_token(
            provider=provider,
            refresh_token=credential.refresh_token
        )

        # Update encrypted storage
        credential.encrypted_token = encrypt(new_token)
        db.commit()
```

---

## API Endpoints

### OAuth Endpoints

```
GET  /api/oauth/authorize                    - Initiate OAuth flow
GET  /api/oauth/callback/{provider}          - OAuth callback
POST /api/oauth/token/refresh                - Refresh access token
GET  /api/oauth/user                         - Get current user
POST /api/oauth/validate-request             - Validate OAuth request
```

### Authentication Endpoints

```
POST /api/auth/login                         - User login
POST /api/auth/logout                        - User logout
GET  /api/auth/me                            - Get current user profile
POST /api/auth/refresh                       - Refresh session token
```

### Example: Get Current User

```bash
# Get current user with X-User-ID header
curl http://localhost:8000/api/oauth/user \
  -H "X-User-ID: user_123abc"
```

**Response**:
```json
{
  "user_id": "user_123abc",
  "email": "user@example.com",
  "name": "John Doe",
  "integrations": ["google", "slack", "asana"]
}
```

---

## Testing

### Unit Tests

**File**: `backend/tests/test_oauth_validation.py`

```python
def test_user_id_validation():
    """Test user ID format validation"""
    # Valid user IDs
    assert is_valid_user_id("user_123") == True
    assert is_valid_user_id("User-123_abc") == True

    # Invalid user IDs
    assert is_valid_user_id("user@123") == False  # @ not allowed
    assert is_valid_user_id("user.123") == False  # . not allowed
    assert is_valid_user_id("") == False          # Empty

def test_email_validation():
    """Test email format validation"""
    # Valid emails
    assert is_valid_email("user@example.com") == True
    assert is_valid_email("user.name@example.co.uk") == True

    # Invalid emails
    assert is_valid_email("user@") == False
    assert is_valid_email("@example.com") == False
    assert is_valid_email("user@example") == False
```

### Integration Tests

```bash
# Test OAuth flow
pytest tests/test_oauth_validation.py -v

# Test session management
pytest tests/test_session_management.py -v
```

---

## Troubleshooting

### Issue: "Invalid user ID format" Error

**Symptoms**: API requests rejected with 400 error

**Diagnosis**:
```bash
# Check X-User-ID header format
curl -v http://localhost:8000/api/oauth/user \
  -H "X-User-ID: user@123"  # Invalid format
```

**Solutions**:
1. Use only alphanumeric characters, underscore, and hyphen
2. Remove special characters (@, ., spaces)
3. Ensure X-User-ID header is sent

### Issue: "User not found" Error

**Symptoms**: API requests rejected with 401 error

**Diagnosis**:
```bash
# Check if user exists in database
python3 -c "
from backend.core.models import User, SessionLocal
db = SessionLocal()
user = db.query(User).filter(User.id == 'user_123').first()
print(user)
"
```

**Solutions**:
1. Complete OAuth flow to create user
2. Enable temporary user creation in development
3. Check X-User-ID matches database record

### Issue: Token Expired

**Symptoms**: JWT token validation fails

**Diagnosis**:
```bash
# Check token expiration
python3 -c "
import jwt
token = 'your-jwt-token'
payload = jwt.decode(token, options={'verify_signature': False})
print(f'Expires: {payload["exp"]}')
"
```

**Solutions**:
1. Refresh token: `POST /api/auth/refresh`
2. Increase JWT_EXPIRATION if needed
3. Complete login flow again

---

## Configuration Checklist

### Development

- [ ] Set `ENVIRONMENT=development`
- [ ] Set `ALLOW_DEV_TEMP_USERS=true` (optional)
- [ ] Configure OAuth client IDs and secrets
- [ ] Set `SECRET_KEY` (optional, will auto-generate)
- [ ] Set `ENCRYPTION_KEY` (optional, for testing encryption)

### Production

- [ ] Set `ENVIRONMENT=production`
- [ ] Set `ALLOW_DEV_TEMP_USERS=false` (CRITICAL)
- [ ] Generate and set `SECRET_KEY` (CRITICAL)
- [ ] Generate and set `ENCRYPTION_KEY` (recommended)
- [ ] Configure all OAuth client IDs and secrets
- [ ] Set `CORS_ORIGINS` to production domain
- [ ] Enable HTTPS
- [ ] Configure OAuth redirect URIs

---

## References

### Official Documentation
- [OAuth 2.0 Specification](https://oauth.net/2/)
- [JWT Specification](https://jwt.io/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

### Atom Documentation
- [DEVELOPMENT.md](../DEVELOPMENT.md) - Security Configuration section
- [SECURITY/DATA_PROTECTION.md](DATA_PROTECTION.md) - Encryption and secrets
- [SECURITY/WEBHOOK_VERIFICATION.md](WEBHOOK_VERIFICATION.md) - Webhook security
- [missing_credentials_guide.md](../missing_credentials_guide.md) - OAuth setup for 117+ providers

### Implementation Files
- `backend/core/auth.py` - Authentication functions
- `backend/api/oauth_routes.py` - OAuth endpoints
- `backend/core/credential_manager.py` - Credential encryption
- `backend/tests/test_oauth_validation.py` - OAuth tests

