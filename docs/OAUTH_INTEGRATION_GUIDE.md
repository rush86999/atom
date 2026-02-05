# OAuth Integration Guide

**Last Updated**: February 4, 2026

This guide explains how to integrate OAuth authentication for third-party services in Atom.

---

## Overview

Atom supports OAuth 2.0 and OAuth 1.0a authentication for multiple third-party services. Each integration follows a consistent pattern:

1. **Initiation**: Client requests OAuth authorization URL
2. **Authorization**: User approves the application on the provider's site
3. **Callback**: Provider redirects back with authorization code/token
4. **Token Exchange**: Application exchanges authorization for access token
5. **Token Storage**: Token is stored securely for future API calls

---

## Supported Services

### OAuth 2.0 Services

| Service | Scopes | Environment Variables |
|---------|--------|----------------------|
| **Asana** | `openid,email` | `ASANA_CLIENT_ID`, `ASANA_CLIENT_SECRET`, `ASANA_REDIRECT_URI` |
| **Notion** | `openid,userinfo` | `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`, `NOTION_REDIRECT_URI` |
| **GitHub** | `repo,user:email` | `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI` |
| **Dropbox** | `account_info.read,files.metadata.read` | `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REDIRECT_URI` |
| **Google** | `openid,email,profile` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` |

### OAuth 1.0a Services

| Service | Access Level | Environment Variables |
|---------|--------------|----------------------|
| **Trello** | `read,write` | `TRELLO_API_KEY`, `TRELLO_API_SECRET`, `TRELLO_OAUTH_TOKEN`, `TRELLO_OAUTH_TOKEN_SECRET`, `TRELLO_REDIRECT_URI` |

---

## API Endpoints

### 1. Initiate OAuth Flow

**Endpoint**: `GET /api/auth/{service}/initiate`

**Description**: Start the OAuth flow for a specific service. Returns the authorization URL that the user should be redirected to.

**Services**: `trello`, `asana`, `notion`, `github`, `dropbox`, `google`

**Example Request**:
```bash
curl "http://localhost:8000/api/auth/notion/initiate?user_id=user_123&redirect_uri=http://localhost:3000/callback"
```

**Example Response**:
```json
{
  "ok": true,
  "service": "notion",
  "auth_url": "https://api.notion.com/v1/oauth/authorize?client_id=...&response_type=code&redirect_uri=...",
  "state": "notion_oauth_user_123"
}
```

**Query Parameters**:
- `user_id` (required): The user ID initiating the OAuth flow
- `redirect_uri` (optional): Custom redirect URI (overrides default)

---

### 2. OAuth Callback (GET)

**Endpoint**: `GET /api/auth/{service}/callback`

**Description**: Handle the OAuth callback from the provider (for services that use GET callback).

**Services**: `trello`, `notion`, `github`, `google`

**Example Request**:
```bash
curl "http://localhost:8000/api/auth/notion/callback?code=...&state=notion_oauth_user_123"
```

**Example Response**:
```json
{
  "ok": true,
  "service": "notion",
  "access_token": "secret_...",
  "token_type": "bearer",
  "workspace_id": "workspace_123",
  "workspace_name": "My Workspace",
  "user_id": "user_123"
}
```

**Query Parameters**:
- `code` (OAuth 2.0): Authorization code from provider
- `oauth_token` (OAuth 1.0a): Request token from provider
- `oauth_verifier` (OAuth 1.0a): Verification token from provider
- `state`: State parameter for security validation

---

### 3. OAuth Callback (POST)

**Endpoint**: `POST /api/auth/{service}/callback`

**Description**: Handle the OAuth callback from the provider (for services that use POST callback).

**Services**: `asana`, `dropbox`

**Example Request**:
```bash
curl -X POST "http://localhost:8000/api/auth/asana/callback" \
  -H "Content-Type: application/json" \
  -d '{"code": "...", "state": "asana_oauth_user_123"}'
```

**Example Response**:
```json
{
  "ok": true,
  "service": "asana",
  "access_token": "...",
  "token_type": "bearer",
  "data": {
    "gid": "1234567890",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

---

### 4. Check OAuth Status

**Endpoint**: `GET /api/auth/{service}/status`

**Description**: Check the OAuth configuration and authorization status for a service.

**Example Request**:
```bash
curl "http://localhost:8000/api/auth/notion/status?user_id=user_123"
```

**Example Response** (Configured):
```json
{
  "ok": true,
  "service": "notion",
  "configured": true,
  "authorized": true,
  "user_id": "user_123",
  "has_credentials": true,
  "token_present": true,
  "message": "Notion OAuth is configured and authorized",
  "timestamp": "2026-02-04T12:00:00Z"
}
```

**Example Response** (Not Configured):
```json
{
  "ok": false,
  "service": "notion",
  "configured": false,
  "authorized": false,
  "error": "NOTION_CLIENT_ID not set",
  "message": "Notion OAuth is not configured. Set NOTION_CLIENT_ID and NOTION_CLIENT_SECRET environment variables.",
  "timestamp": "2026-02-04T12:00:00Z"
}
```

---

### 5. OAuth Health Check

**Endpoint**: `GET /api/auth/health`

**Description**: Check the health status of all OAuth configurations.

**Example Request**:
```bash
curl "http://localhost:8000/api/auth/health"
```

**Example Response**:
```json
{
  "ok": true,
  "overall_status": "healthy",
  "services": {
    "google": {
      "configured": true,
      "status": "ok",
      "message": "Google OAuth is configured"
    },
    "notion": {
      "configured": true,
      "status": "ok",
      "message": "Notion OAuth is configured"
    },
    "trello": {
      "configured": true,
      "status": "ok",
      "message": "Trello OAuth is configured"
    }
  },
  "total_services": 6,
  "configured_services": 6,
  "unconfigured_services": 0,
  "timestamp": "2026-02-04T12:00:00Z"
}
```

---

### 6. Refresh OAuth Token

**Endpoint**: `POST /api/auth/{service}/refresh`

**Description**: Refresh an expired OAuth access token (if the service supports refresh tokens).

**Services**: `google`, `github`, `asana`

**Example Request**:
```bash
curl -X POST "http://localhost:8000/api/auth/google/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "..."}'
```

**Example Response**:
```json
{
  "ok": true,
  "service": "google",
  "access_token": "ya29...",
  "expires_in": 3600,
  "token_type": "bearer"
}
```

---

## Environment Variables Setup

### Google OAuth

```bash
export GOOGLE_CLIENT_ID="your-google-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-google-client-secret"
export GOOGLE_REDIRECT_URI="http://localhost:8000/api/auth/google/callback"
```

### Notion OAuth

```bash
export NOTION_CLIENT_ID="your-notion-client-id"
export NOTION_CLIENT_SECRET="your-notion-client-secret"
export NOTION_REDIRECT_URI="http://localhost:8000/api/auth/notion/callback"
```

### Trello OAuth (OAuth 1.0a)

```bash
export TRELLO_API_KEY="your-trello-api-key"
export TRELLO_API_SECRET="your-trello-api-secret"
export TRELLO_REDIRECT_URI="http://localhost:8000/api/auth/trello/callback"
```

### GitHub OAuth

```bash
export GITHUB_CLIENT_ID="your-github-client-id"
export GITHUB_CLIENT_SECRET="your-github-client-secret"
export GITHUB_REDIRECT_URI="http://localhost:8000/api/auth/github/callback"
```

### Asana OAuth

```bash
export ASANA_CLIENT_ID="your-asana-client-id"
export ASANA_CLIENT_SECRET="your-asana-client-secret"
export ASANA_REDIRECT_URI="http://localhost:8000/api/auth/asana/callback"
```

### Dropbox OAuth

```bash
export DROPBOX_APP_KEY="your-dropbox-app-key"
export DROPBOX_APP_SECRET="your-dropbox-app-secret"
export DROPBOX_REDIRECT_URI="http://localhost:8000/api/auth/dropbox/callback"
```

---

## OAuth Flow Examples

### Frontend Integration (React)

```typescript
import React, { useEffect, useState } from 'react';

function NotionOAuthButton({ userId }) {
  const [authUrl, setAuthUrl] = useState(null);

  const initiateOAuth = async () => {
    const response = await fetch(
      `http://localhost:8000/api/auth/notion/initiate?user_id=${userId}`
    );
    const data = await response.json();

    if (data.ok) {
      // Redirect user to authorization URL
      window.location.href = data.auth_url;
    }
  };

  const handleCallback = async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');

    if (code) {
      const response = await fetch(
        `http://localhost:8000/api/auth/notion/callback?code=${code}&state=${state}`
      );
      const data = await response.json();

      if (data.ok) {
        console.log('Authorization successful!', data.workspace_name);
      }
    }
  };

  useEffect(() => {
    // Check if we're returning from OAuth callback
    if (window.location.search.includes('code')) {
      handleCallback();
    }
  }, []);

  return (
    <button onClick={initiateOAuth}>
      Connect Notion
    </button>
  );
}
```

### Backend Integration (Python)

```python
import httpx
from core.config import get_config

async def get_notion_oauth_url(user_id: str) -> str:
    """Get Notion OAuth authorization URL"""
    config = get_config()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.api_base_url}/api/auth/notion/initiate",
            params={"user_id": user_id}
        )
        data = response.json()

        if data.get("ok"):
            return data["auth_url"]
        else:
            raise Exception(f"OAuth initiation failed: {data}")

# Usage
auth_url = await get_notion_oauth_url("user_123")
print(f"Redirect user to: {auth_url}")
```

---

## Token Storage

OAuth tokens are stored in the `UserOAuthToken` model in the database:

```python
class UserOAuthToken(Base):
    __tablename__ = "user_oauth_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    service = Column(String(50), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String(20), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    scopes = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

**Security Notes**:
- Access tokens are stored encrypted in the database
- Refresh tokens are only stored if the service provides them
- Tokens are automatically refreshed when expired (if refresh token is available)
- Tokens can be revoked via the API

---

## Troubleshooting

### Common Issues

#### 1. "OAuth not configured" Error

**Problem**: Service returns "not configured" status.

**Solution**:
- Check that all required environment variables are set
- Verify environment variables are loaded in the application
- Restart the application after setting environment variables

```bash
# Check if environment variables are set
echo $NOTION_CLIENT_ID
echo $NOTION_CLIENT_SECRET

# Restart application
python -m uvicorn main:app --reload
```

#### 2. "Invalid redirect URI" Error

**Problem**: Provider rejects the redirect URI.

**Solution**:
- Ensure the redirect URI in your app settings matches exactly
- Include the full URL (http://localhost:8000/api/auth/notion/callback)
- For production, use https:// and the correct domain

#### 3. "Authorization code expired" Error

**Problem**: OAuth callback fails with expired code.

**Solution**:
- Authorization codes expire quickly (usually 5-10 minutes)
- Complete the OAuth flow immediately after initiation
- Ensure the callback endpoint is accessible

#### 4. Trello OAuth 1.0a Issues

**Problem**: Trello OAuth fails with signature errors.

**Solution**:
- Verify TRELLO_API_KEY and TRELLO_API_SECRET are correct
- Ensure the callback URL matches exactly what's in Trello app settings
- OAuth 1.0a requires proper timestamp and nonce generation

---

## Testing

### Test OAuth Configuration

```bash
# Check OAuth health
curl http://localhost:8000/api/auth/health

# Check specific service status
curl http://localhost:8000/api/auth/notion/status

# Test initiation (returns auth URL)
curl "http://localhost:8000/api/auth/notion/initiate?user_id=test_user"
```

### Run OAuth Tests

```bash
# Run OAuth flow tests
pytest backend/tests/test_oauth_flows.py -v

# Test specific service
pytest backend/tests/test_oauth_flows.py::test_notion_oauth_config -v
```

---

## Security Best Practices

1. **Use HTTPS in Production**: All OAuth callbacks should use HTTPS
2. **Validate State Parameter**: Always validate the state parameter to prevent CSRF attacks
3. **Store Tokens Securely**: Encrypt tokens in the database
4. **Implement Token Expiration**: Check token expiration and refresh when needed
5. **Limit Token Scope**: Request only the minimum required scopes
6. **Revoke Unused Tokens**: Provide a way for users to revoke OAuth tokens
7. **Log OAuth Events**: Maintain audit logs for all OAuth operations

---

## Adding New OAuth Services

To add a new OAuth service:

1. **Add OAuth Configuration** to `core/oauth_handler.py`:
   ```python
   NEWSERVICE_OAUTH_CONFIG = OAuthConfig(
       client_id_env="NEWSERVICE_CLIENT_ID",
       client_secret_env="NEWSERVICE_CLIENT_SECRET",
       auth_url="https://api.newservice.com/oauth/authorize",
       token_url="https://api.newservice.com/oauth/token",
       scopes=["read", "write"]
   )
   ```

2. **Add OAuth Routes** to `oauth_routes.py`:
   ```python
   @router.get("/newservice/initiate")
   async def newservice_oauth_initiate(
       user_id: str = Query(...),
       redirect_uri: Optional[str] = None
   ):
       handler = OAuthHandler(NEWSERVICE_OAUTH_CONFIG)
       auth_url = handler.get_authorization_url(state=f"newservice_oauth_{user_id}")
       return {"ok": True, "service": "newservice", "auth_url": auth_url}
   ```

3. **Add Status Endpoint** to `oauth_status_routes.py`:
   ```python
   @router.get("/newservice/status")
   async def newservice_status(user_id: str = Query(...)):
       config = get_oauth_config()
       creds = config.get_credentials("newservice")
       # ... return status
   ```

4. **Add Tests** to `tests/test_oauth_flows.py`:
   ```python
   def test_newservice_oauth_config():
       # Test configuration
       pass
   ```

---

## Additional Resources

- **OAuth 2.0 Spec**: https://oauth.net/2/
- **OAuth 1.0a Spec**: https://oauth.net/core/1.0a/
- **Provider Documentation**:
  - [Notion OAuth](https://developers.notion.com/docs/authorization)
  - [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
  - [GitHub OAuth](https://docs.github.com/en/developers/apps/building-oauth-apps)
  - [Trello API](https://developer.atlassian.com/cloud/trello/rest/api-group-authorization/)
  - [Asana OAuth](https://developers.asana.com/docs/oauth)
  - [Dropbox OAuth](https://developers.dropbox.com/oauth-guide)

---

## Summary

| Feature | Status |
|---------|--------|
| OAuth 2.0 Support | ✅ Complete |
| OAuth 1.0a Support | ✅ Complete (Trello) |
| Token Storage | ✅ Complete |
| Token Refresh | ✅ Complete |
| Health Checks | ✅ Complete |
| Error Handling | ✅ Complete |
| Tests | ✅ Complete |

---

*For questions or issues, please refer to the main documentation or open an issue.*
