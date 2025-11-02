# GitHub Integration Implementation Plan

## Current State Analysis

### ✅ Available Components
- **Credentials**: Client ID, Secret, and Access Token configured
- **Backend Handlers**: `github_handler.py` and `github_service.py` available
- **Infrastructure**: Established Jira integration pattern to follow

### 🔧 Missing Components
- OAuth API implementation
- Database layer for token storage
- Frontend components
- Skills integration

## Implementation Timeline: 3 Days

## Day 1: Backend OAuth & Database Layer

### Phase 1: GitHub OAuth API (4 hours)
Create `backend/github_oauth_api.py` following Jira pattern:

```python
#!/usr/bin/env python3
"""
GitHub OAuth API Implementation
Follows established Jira integration pattern
"""

import os
import logging
import secrets
from flask import Blueprint, request, jsonify, session, redirect
from urllib.parse import urlencode
import httpx
import json
from datetime import datetime, timedelta
from crypto_utils import encrypt_message, decrypt_message
from db_oauth_github import save_tokens, get_tokens, delete_tokens

logger = logging.getLogger(__name__)

github_oauth_bp = Blueprint("github_oauth_bp", __name__)

# Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:5059/api/auth/github/callback")
GITHUB_SCOPES = "repo,user,read:org,read:project"

@github_oauth_bp.route("/api/auth/github/start")
async def github_auth_start():
    """Start GitHub OAuth flow"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        # Generate state and store in session
        state = secrets.token_urlsafe(32)
        session["github_oauth_state"] = state
        session["github_oauth_user_id"] = user_id

        # Build authorization URL
        auth_params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "scope": GITHUB_SCOPES,
            "state": state,
            "allow_signup": "false"
        }

        auth_url = f"https://github.com/oauth/authorize?{urlencode(auth_params)}"
        
        return jsonify({
            "ok": True,
            "auth_url": auth_url,
            "state": state
        })

    except Exception as e:
        logger.error(f"GitHub OAuth start error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@github_oauth_bp.route("/api/auth/github/callback")
async def github_auth_callback():
    """Handle GitHub OAuth callback"""
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")

        if error:
            logger.error(f"GitHub OAuth callback error: {error}")
            return jsonify({"ok": False, "error": f"OAuth error: {error}"}), 400

        if not code:
            return jsonify({"ok": False, "error": "Authorization code required"}), 400

        # Verify state
        if state != session.get("github_oauth_state"):
            return jsonify({"ok": False, "error": "Invalid state parameter"}), 400

        user_id = session.get("github_oauth_user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "No user_id found in session"}), 400

        # Exchange code for access token
        token_url = "https://github.com/oauth/access_token"
        token_data = {
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_REDIRECT_URI
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, json=token_data, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"GitHub token exchange failed: {response.text}")
                return jsonify({"ok": False, "error": "Token exchange failed"}), 400

            token_response = response.json()
            access_token = token_response.get("access_token")
            
            if not access_token:
                return jsonify({"ok": False, "error": "No access token received"}), 400

            # Get user info to verify connection
            user_info = await get_github_user_info(access_token)
            
            # Encrypt and store tokens
            encrypted_token = encrypt_message(access_token)
            expires_at = datetime.now() + timedelta(days=30)  # GitHub tokens don't expire by default
            
            await save_tokens(
                db_conn_pool=current_app.config["DB_CONNECTION_POOL"],
                user_id=user_id,
                encrypted_access_token=encrypted_token,
                encrypted_refresh_token=None,  # GitHub doesn't use refresh tokens
                expires_at=expires_at,
                scope=GITHUB_SCOPES
            )

            # Clear session
            session.pop("github_oauth_state", None)
            session.pop("github_oauth_user_id", None)

            logger.info(f"GitHub OAuth completed successfully for user {user_id}")
            
            return jsonify({
                "ok": True,
                "message": "GitHub connected successfully",
                "user_info": user_info
            })

    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

async def get_github_user_info(access_token: str):
    """Get GitHub user information"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.github.com/user", headers=headers)
        if response.status_code == 200:
            return response.json()
        return {}

@github_oauth_bp.route("/api/auth/github/status", methods=["POST"])
async def github_auth_status():
    """Check GitHub connection status"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        # Check if tokens exist and are valid
        tokens = await get_tokens(
            db_conn_pool=current_app.config["DB_CONNECTION_POOL"],
            user_id=user_id
        )

        if not tokens:
            return jsonify({
                "ok": True,
                "connected": False,
                "message": "Not connected to GitHub"
            })

        # Verify token is still valid
        encrypted_token, _, expires_at = tokens
        access_token = decrypt_message(encrypted_token)

        if expires_at and expires_at < datetime.now():
            return jsonify({
                "ok": True,
                "connected": False,
                "message": "GitHub token expired"
            })

        # Test token with API call
        user_info = await get_github_user_info(access_token)
        if user_info:
            return jsonify({
                "ok": True,
                "connected": True,
                "user_info": user_info,
                "message": "Connected to GitHub"
            })
        else:
            return jsonify({
                "ok": True,
                "connected": False,
                "message": "GitHub token invalid"
            })

    except Exception as e:
        logger.error(f"GitHub status check error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@github_oauth_bp.route("/api/auth/github/disconnect", methods=["POST"])
async def github_auth_disconnect():
    """Disconnect GitHub integration"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        await delete_tokens(
            db_conn_pool=current_app.config["DB_CONNECTION_POOL"],
            user_id=user_id
        )

        return jsonify({
            "ok": True,
            "message": "GitHub disconnected successfully"
        })

    except Exception as e:
        logger.error(f"GitHub disconnect error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
```

### Phase 2: Database Layer (2 hours)
Create `backend/python-api-service/db_oauth_github.py`:

```python
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def save_tokens(db_conn_pool, user_id: str, encrypted_access_token: bytes, encrypted_refresh_token: bytes, expires_at: datetime, scope: str):
    """Save GitHub OAuth tokens for a user"""
    sql = """
        INSERT INTO user_github_oauth_tokens (user_id, encrypted_access_token, encrypted_refresh_token, expires_at, scope, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            encrypted_access_token = EXCLUDED.encrypted_access_token,
            encrypted_refresh_token = EXCLUDED.encrypted_refresh_token,
            expires_at = EXCLUDED.expires_at,
            scope = EXCLUDED.scope,
            updated_at = %s;
    """
    now = datetime.now(timezone.utc)
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id, encrypted_access_token, encrypted_refresh_token, expires_at, scope, now, now, now))
            conn.commit()
    except Exception as e:
        logger.error(f"Error saving GitHub OAuth tokens for user {user_id}: {e}")
        raise
    finally:
        db_conn_pool.putconn(conn)

async def get_tokens(db_conn_pool, user_id: str):
    """Get GitHub OAuth tokens for a user"""
    sql = "SELECT encrypted_access_token, encrypted_refresh_token, expires_at FROM user_github_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                return cur.fetchone()
    except Exception as e:
        logger.error(f"Error getting GitHub OAuth tokens for user {user_id}: {e}")
        return None
    finally:
        db_conn_pool.putconn(conn)

async def delete_tokens(db_conn_pool, user_id: str):
    """Delete GitHub OAuth tokens for a user"""
    sql = "DELETE FROM user_github_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error deleting GitHub OAuth tokens for user {user_id}: {e}")
        raise
    finally:
        db_conn_pool.putconn(conn)
```

### Phase 3: Environment Configuration (1 hour)
Update `.env` file:
```bash
# GitHub OAuth Configuration
GITHUB_REDIRECT_URI="http://localhost:5059/api/auth/github/callback"
GITHUB_SCOPES="repo,user,read:org,read:project"
```

## Day 2: Enhanced Service Layer

### Phase 1: Extend GitHub Handler (3 hours)
Enhance `github_handler.py` with comprehensive API coverage:

```python
# Add repository operations
- List repositories
- Create repository
- Fork repository
- Get repository details

# Add issue operations
- List issues
- Create issue
- Update issue
- Search issues

# Add pull request operations
- List PRs
- Create PR
- Review PR
- Merge PR

# Add webhook operations
- Create webhook
- List webhooks
- Delete webhook
```

### Phase 2: Advanced Features (3 hours)
- Implement repository search and filtering
- Add code review workflows
- Create issue templates and automation
- Implement branch protection rules

### Phase 3: Error Handling & Rate Limiting (2 hours)
- Add comprehensive error handling
- Implement GitHub API rate limiting
- Add retry mechanisms for failed requests
- Create fallback strategies

## Day 3: Frontend Integration

### Phase 1: GitHub Manager Component (4 hours)
Create `src/ui-shared/integrations/github/components/GitHubManager.tsx`:

```typescript
import React, { useState, useEffect } from 'react';
import { useAuth } from '../../../hooks/useAuth';
import { GitHubRepositoryList } from './GitHubRepositoryList';
import { GitHubIssueTracker } from './GitHubIssueTracker';
import { GitHubPullRequestDashboard } from './GitHubPullRequestDashboard';

export const GitHubManager: React.FC = () => {
  const { user } = useAuth();
  const [connected, setConnected] = useState(false);
  const [activeTab, setActiveTab] = useState('repositories');
  const [userInfo, setUserInfo] = useState<any>(null);

  // Implementation follows JiraManager pattern
  // with GitHub-specific features
};
```

### Phase 2: OAuth Callback Page (2 hours)
Create `frontend-nextjs/pages/oauth/github/callback.tsx`:

```typescript
// Follows Jira callback pattern with GitHub-specific handling
// Success/error states for GitHub OAuth flow
// Token confirmation and user info display
```

### Phase 3: Skills Integration (2 hours)
Create `src/skills/githubSkills.ts`:

```typescript
// Natural language commands for GitHub operations
- "List my GitHub repositories"
- "Create a new issue in project X"
- "Show open pull requests"
- "Search for issues with label bug"
```

## Integration Testing Strategy

### Backend Tests
- OAuth flow completion
- Token storage and retrieval
- API endpoint validation
- Error handling scenarios

### Frontend Tests
- Component rendering and interaction
- OAuth flow in browser
- Real-time data updates
- Error state handling

### End-to-End Tests
- Complete user workflow
- Cross-browser compatibility
- Mobile responsiveness
- Performance benchmarks

## Success Metrics

### Technical Metrics
- OAuth flow completion: 100%
- API response time: < 2 seconds
- Error rate: < 1%
- Token refresh success: 100%

### User Experience Metrics
- Integration setup time: < 2 minutes
- Repository loading: < 3 seconds
- Issue creation: < 5 seconds
- Search performance: < 2 seconds

## Risk Assessment

### High Risk
- GitHub API rate limiting (5000 requests/hour)
- OAuth configuration errors
- Token security and encryption

### Medium Risk
- Frontend performance with large repositories
- Error recovery scenarios
- Cross-browser compatibility

### Low Risk
- UI/UX polish requirements
- Minor feature gaps

## Dependencies

### External Dependencies
- GitHub API availability
- GitHub OAuth app configuration
- Network connectivity

### Internal Dependencies
- Backend blueprint registration (fixed)
- Database connectivity
- Frontend build system

## Next Steps

### Immediate (Day 1)
1. Create GitHub OAuth API file
2. Implement database layer
3. Update environment configuration

### Short-term (Day 2)
1. Extend GitHub handler with full API coverage
2. Implement advanced features
3. Add error handling and rate limiting

### Medium-term (Day 3)
1. Build frontend components
2. Create OAuth callback page
3. Implement skills integration

## Conclusion

The GitHub integration follows the proven Jira implementation pattern and leverages existing infrastructure. With 3 days of focused development, we can deliver a comprehensive GitHub integration that provides significant value to users for code collaboration and project management.

**Ready to begin implementation!**