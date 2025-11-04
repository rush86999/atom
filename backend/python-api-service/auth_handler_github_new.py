"""
Enhanced GitHub OAuth and API Handler
Following Outlook pattern for consistency
"""

import os
import json
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import RedirectResponse
import jwt
from cryptography.fernet import Fernet
from urllib.parse import urlencode, parse_qs

logger = logging.getLogger(__name__)

class GitHubOAuthHandler:
    def __init__(self):
        self.client_id = os.getenv('GITHUB_CLIENT_ID')
        self.client_secret = os.getenv('GITHUB_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GITHUB_REDIRECT_URI', 'http://localhost:3000/oauth/github/callback')
        self.scope = [
            'repo',            # Repository access
            'read:org',       # Organization read access
            'read:user',       # User profile read access
            'user:email',     # User email access
            'read:project',   # Project board access
            'issues:write',   # Issue management
            'pullrequest:write', # PR management
            'admin:org',      # Organization administration (optional)
            'workflow'         # GitHub Actions workflow access
        ]
        self.encryption_key = os.getenv('ENCRYPTION_KEY').encode() if os.getenv('ENCRYPTION_KEY') else Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        
        # GitHub API endpoints
        self.auth_url = "https://github.com/login/oauth/authorize"
        self.token_url = "https://github.com/login/oauth/access_token"
        self.api_url = "https://api.github.com"
        self.graphql_url = "https://api.github.com/graphql"
        
        if not self.client_id or not self.client_secret:
            logger.warning("GitHub OAuth credentials not configured")

    async def initiate_oauth(self, user_id: str, state: Optional[str] = None) -> Dict[str, Any]:
        """Initiate GitHub OAuth flow"""
        try:
            if not self.client_id:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="GitHub OAuth not configured"
                )

            # Generate state with user context
            if not state:
                state = f"github_oauth_{user_id}_{datetime.now().timestamp()}"
            
            # Store state for validation
            await self._store_oauth_state(state, user_id)

            # Build authorization URL
            params = {
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'scope': ' '.join(self.scope),
                'state': state,
                'response_type': 'code',
                'allow_signup': 'true'
            }

            auth_url = f"{self.auth_url}?{urlencode(params)}"
            
            logger.info(f"GitHub OAuth initiated for user {user_id}")
            
            return {
                'success': True,
                'auth_url': auth_url,
                'state': state,
                'service': 'github',
                'expires_in': 600,  # 10 minutes
                'message': 'GitHub OAuth URL generated successfully'
            }

        except Exception as e:
            logger.error(f"Failed to initiate GitHub OAuth: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initiate GitHub OAuth: {str(e)}"
            )

    async def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access tokens"""
        try:
            # Validate state
            stored_state = await self._get_oauth_state(state)
            if not stored_state:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired OAuth state"
                )

            user_id = stored_state.get('user_id')
            
            # Exchange code for tokens
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'redirect_uri': self.redirect_uri,
                'grant_type': 'authorization_code'
            }

            headers = {
                'Accept': 'application/json',
                'User-Agent': 'ATOM-Desktop/1.0'
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url,
                    data=data,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"GitHub token exchange failed: {error_text}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Failed to exchange authorization code"
                        )

                    token_data = await response.json()

                    # GitHub returns access_token, token_type, and scope
                    access_token = token_data.get('access_token')
                    token_type = token_data.get('token_type', 'bearer')
                    scope = token_data.get('scope', '')

                    if not access_token:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No access token received from GitHub"
                        )

                    # Get user info
                    user_info = await self._get_user_info(access_token)
                    
                    # Calculate expiration (GitHub tokens don't expire unless revoked)
                    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)  # Default 24 hours for refresh
                    
                    # Store tokens with encryption
                    encrypted_tokens = self._encrypt_tokens({
                        'access_token': access_token,
                        'token_type': token_type,
                        'scope': scope,
                        'expires_at': expires_at.isoformat(),
                        'user_info': user_info
                    })

                    # Update OAuth state
                    await self._update_oauth_state(state, {
                        'status': 'completed',
                        'user_info': user_info,
                        'encrypted_tokens': encrypted_tokens
                    })

                    logger.info(f"GitHub OAuth completed for user {user_id}")

                    return {
                        'success': True,
                        'user_info': user_info,
                        'tokens': {
                            'access_token': '***encrypted***',  # Don't expose actual token
                            'token_type': token_type,
                            'scope': scope,
                            'expires_at': expires_at.isoformat()
                        },
                        'message': 'GitHub OAuth completed successfully'
                    }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GitHub token exchange failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to exchange authorization code: {str(e)}"
            )

    async def get_user_tokens(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get stored user tokens"""
        try:
            # Get OAuth state from database (mock for now)
            # In production, query your database
            return await self._get_user_tokens_from_db(user_id)
        except Exception as e:
            logger.error(f"Failed to get user tokens: {e}")
            return None

    async def get_connection_status(self, user_id: str) -> Dict[str, Any]:
        """Check GitHub connection status"""
        try:
            tokens = await self.get_user_tokens(user_id)
            
            if not tokens:
                return {
                    'connected': False,
                    'error': 'No tokens found'
                }

            # Check if tokens are expired
            expires_at = datetime.fromisoformat(tokens.get('expires_at', ''))
            if datetime.now(timezone.utc) >= expires_at:
                return {
                    'connected': False,
                    'error': 'Tokens expired',
                    'expired': True
                }

            # Test token validity
            user_info = await self._get_user_info(tokens['access_token'])
            if user_info:
                return {
                    'connected': True,
                    'user_info': user_info,
                    'expires_at': tokens.get('expires_at'),
                    'scope': tokens.get('scope', '')
                }
            else:
                return {
                    'connected': False,
                    'error': 'Invalid tokens'
                }

        except Exception as e:
            logger.error(f"Failed to check connection status: {e}")
            return {
                'connected': False,
                'error': str(e)
            }

    async def disconnect_user(self, user_id: str) -> Dict[str, Any]:
        """Disconnect user GitHub integration"""
        try:
            # Revoke tokens (GitHub doesn't have revoke endpoint, so just delete stored tokens)
            await self._delete_user_tokens(user_id)
            
            logger.info(f"GitHub disconnected for user {user_id}")
            
            return {
                'success': True,
                'message': 'GitHub integration disconnected successfully'
            }

        except Exception as e:
            logger.error(f"Failed to disconnect GitHub: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to disconnect GitHub: {str(e)}"
            )

    async def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access tokens (GitHub doesn't have refresh tokens for OAuth apps)"""
        # GitHub OAuth app tokens don't expire unless revoked
        # For GitHub App installations, you can generate new tokens
        # This is a placeholder for future GitHub App implementation
        
        return {
            'success': False,
            'error': 'GitHub OAuth tokens do not expire and cannot be refreshed',
            'message': 'Please re-authenticate if needed'
        }

    async def _get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get user information from GitHub API"""
        try:
            headers = {
                'Authorization': f'token {access_token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'ATOM-Desktop/1.0'
            }

            async with aiohttp.ClientSession() as session:
                # Get user profile
                async with session.get(
                    f"{self.api_url}/user",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        return None
                    
                    user_data = await response.json()

                # Get user emails (primary email)
                async with session.get(
                    f"{self.api_url}/user/emails",
                    headers=headers
                ) as response:
                    emails_data = await response.json() if response.status == 200 else []
                    primary_email = next(
                        (email['email'] for email in emails_data if email['primary']),
                        user_data.get('email')
                    )

                return {
                    'id': user_data.get('id'),
                    'login': user_data.get('login'),
                    'name': user_data.get('name'),
                    'email': primary_email,
                    'avatar_url': user_data.get('avatar_url'),
                    'company': user_data.get('company'),
                    'location': user_data.get('location'),
                    'bio': user_data.get('bio'),
                    'public_repos': user_data.get('public_repos'),
                    'followers': user_data.get('followers'),
                    'following': user_data.get('following'),
                    'created_at': user_data.get('created_at'),
                    'updated_at': user_data.get('updated_at'),
                    'html_url': user_data.get('html_url'),
                    'type': user_data.get('type')
                }

        except Exception as e:
            logger.error(f"Failed to get GitHub user info: {e}")
            return None

    async def _store_oauth_state(self, state: str, user_id: str) -> None:
        """Store OAuth state"""
        # In production, store in Redis or database
        oauth_data = {
            'state': state,
            'user_id': user_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            'status': 'pending'
        }
        
        # Mock storage - replace with actual database
        logger.info(f"OAuth state stored: {oauth_data}")

    async def _get_oauth_state(self, state: str) -> Optional[Dict[str, Any]]:
        """Get OAuth state"""
        # Mock retrieval - replace with actual database
        return {
            'state': state,
            'user_id': 'mock_user',
            'status': 'pending'
        }

    async def _update_oauth_state(self, state: str, data: Dict[str, Any]) -> None:
        """Update OAuth state"""
        # Mock update - replace with actual database
        logger.info(f"OAuth state updated: {data}")

    async def _get_user_tokens_from_db(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user tokens from database"""
        # Mock retrieval - replace with actual database
        return None

    async def _delete_user_tokens(self, user_id: str) -> None:
        """Delete user tokens from database"""
        # Mock deletion - replace with actual database
        logger.info(f"Tokens deleted for user {user_id}")

    def _encrypt_tokens(self, tokens: Dict[str, Any]) -> str:
        """Encrypt tokens for storage"""
        try:
            tokens_json = json.dumps(tokens)
            encrypted = self.cipher.encrypt(tokens_json.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt tokens: {e}")
            raise

    def _decrypt_tokens(self, encrypted_tokens: str) -> Dict[str, Any]:
        """Decrypt tokens from storage"""
        try:
            decrypted = self.cipher.decrypt(encrypted_tokens.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt tokens: {e}")
            raise

# Create global instance
github_oauth_handler = GitHubOAuthHandler()

# FastAPI routes
async def github_oauth_url(user_id: str):
    """Get GitHub OAuth URL"""
    return await github_oauth_handler.initiate_oauth(user_id)

async def github_oauth_callback(request: Request):
    """Handle GitHub OAuth callback"""
    try:
        query_params = parse_qs(str(request.url.query))
        
        code = query_params.get('code', [None])[0]
        state = query_params.get('state', [None])[0]
        error = query_params.get('error', [None])[0]
        
        if error:
            logger.error(f"GitHub OAuth error: {error}")
            return RedirectResponse(
                url=f"/settings?service=github&error={error}"
            )
        
        if not code or not state:
            logger.error("Missing code or state in GitHub OAuth callback")
            return RedirectResponse(
                url="/settings?service=github&error=missing_parameters"
            )
        
        # Exchange code for tokens
        result = await github_oauth_handler.exchange_code_for_tokens(code, state)
        
        if result['success']:
            return RedirectResponse(
                url="/settings?service=github&status=connected"
            )
        else:
            return RedirectResponse(
                url=f"/settings?service=github&error=token_exchange_failed"
            )
            
    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {e}")
        return RedirectResponse(
            url=f"/settings?service=github&error=callback_failed"
        )

async def github_oauth_status(request: Request):
    """Check GitHub OAuth status"""
    try:
        query_params = parse_qs(str(request.url.query))
        user_id = query_params.get('user_id', [''])[0]
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id is required"
            )
        
        status = await github_oauth_handler.get_connection_status(user_id)
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub status check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check GitHub status: {str(e)}"
        )

async def github_oauth_disconnect(request: Request):
    """Disconnect GitHub OAuth"""
    try:
        query_params = parse_qs(str(request.url.query))
        user_id = query_params.get('user_id', [''])[0]
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id is required"
            )
        
        result = await github_oauth_handler.disconnect_user(user_id)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub disconnect failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect GitHub: {str(e)}"
        )

async def github_oauth_refresh():
    """Refresh GitHub OAuth tokens"""
    result = await github_oauth_handler.refresh_tokens('')
    return result

async def github_oauth_health():
    """Check GitHub OAuth health"""
    try:
        # Test basic connectivity to GitHub API
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.github.com/rate_limit",
                headers={'User-Agent': 'ATOM-Desktop/1.0'}
            ) as response:
                if response.status == 200:
                    rate_limit = await response.json()
                    return {
                        'status': 'healthy',
                        'message': 'GitHub API is accessible',
                        'rate_limit': rate_limit
                    }
                else:
                    return {
                        'status': 'unhealthy',
                        'message': 'GitHub API is not accessible',
                        'http_status': response.status
                    }
                    
    except Exception as e:
        logger.error(f"GitHub health check failed: {e}")
        return {
            'status': 'unhealthy',
            'message': f'Failed to connect to GitHub API: {str(e)}'
        }