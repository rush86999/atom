"""
🔐 Zoom Token Manager
Enterprise-grade Zoom OAuth token management with automatic refresh
"""

import os
import json
import logging
import asyncio
import httpx
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass, asdict

import asyncpg
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Zoom OAuth configuration
ZOOM_AUTH_URL = "https://zoom.us/oauth/authorize"
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_REVOKE_URL = "https://zoom.us/oauth/revoke"
ZOOM_USER_INFO_URL = "https://api.zoom.us/v2/users/me"

# Required scopes for Zoom integration
ZOOM_SCOPES = [
    "user:read:admin",        # Read user information
    "meeting:write:admin",    # Create and manage meetings
    "meeting:read:admin",     # Read meeting information
    "recording:write:admin",  # Manage recordings
    "recording:read:admin",   # Access recordings
    "webinar:write:admin",    # Manage webinars
    "webinar:read:admin",     # Read webinar information
    "user:write:admin",       # Manage users
    "report:read:admin",       # Access reports
    "dashboard:read:admin",    # Access dashboard data
]

@dataclass
class ZoomToken:
    """Zoom OAuth token information"""
    user_id: str
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_at: datetime
    scope: str
    zoom_user_id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: str
    account_id: str
    created_at: datetime
    last_used_at: Optional[datetime]
    access_count: int = 0
    is_active: bool = True

@dataclass
class ZoomTokenExchangeRequest:
    """Token exchange request"""
    grant_type: str
    code: Optional[str] = None
    refresh_token: Optional[str] = None
    redirect_uri: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

@dataclass
class ZoomTokenExchangeResponse:
    """Token exchange response"""
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_in: int
    scope: str

class ZoomTokenManager:
    """Enterprise-grade Zoom OAuth token manager"""
    
    def __init__(self, db_pool: asyncpg.Pool, encryption_key: Optional[str] = None):
        self.db_pool = db_pool
        self.client_id = os.getenv('ZOOM_CLIENT_ID')
        self.client_secret = os.getenv('ZOOM_CLIENT_SECRET')
        self.redirect_uri = os.getenv('ZOOM_REDIRECT_URI', 'http://localhost:3000/oauth/zoom/callback')
        
        # Initialize encryption for token storage
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            # Use default key for development (should be overridden in production)
            self.fernet = Fernet(os.getenv('ENCRYPTION_KEY', Fernet.generate_key()).encode())
        
        self.encryption_enabled = bool(encryption_key or os.getenv('ENCRYPTION_KEY'))
        
        # HTTP client for OAuth operations
        self.http_client = httpx.AsyncClient(timeout=30)
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate OAuth configuration"""
        if not self.client_id:
            raise ValueError("ZOOM_CLIENT_ID is required")
        
        if not self.client_secret:
            raise ValueError("ZOOM_CLIENT_SECRET is required")
        
        if not self.redirect_uri:
            raise ValueError("ZOOM_REDIRECT_URI is required")
    
    def _encrypt_token(self, token: str) -> str:
        """Encrypt token for secure storage"""
        if not self.encryption_enabled:
            return token
        return self.fernet.encrypt(token.encode()).decode()
    
    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt token from storage"""
        if not self.encryption_enabled:
            return encrypted_token
        return self.fernet.decrypt(encrypted_token.encode()).decode()
    
    def _generate_csrf_token(self, user_id: str) -> str:
        """Generate CSRF token for OAuth flow"""
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        data = f"{user_id}:{timestamp}"
        hash_obj = hashlib.sha256(data.encode())
        return hash_obj.hexdigest()
    
    def _verify_csrf_token(self, csrf_token: str, user_id: str, max_age: int = 3600) -> bool:
        """Verify CSRF token"""
        try:
            timestamp = str(int(datetime.now(timezone.utc).timestamp()))
            data = f"{user_id}:{timestamp}"
            expected_hash = hashlib.sha256(data.encode()).hexdigest()
            
            # Simple hash comparison for demonstration
            # In production, use proper CSRF token verification
            return secrets.compare_digest(csrf_token, expected_hash)
        except Exception:
            return False
    
    async def _exchange_code_for_tokens(self, code: str, redirect_uri: str) -> ZoomTokenExchangeResponse:
        """Exchange authorization code for tokens"""
        request_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        response = await self.http_client.post(ZOOM_TOKEN_URL, data=request_data)
        response.raise_for_status()
        
        token_data = response.json()
        
        return ZoomTokenExchangeResponse(
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            token_type=token_data['token_type'],
            expires_in=token_data['expires_in'],
            scope=token_data['scope']
        )
    
    async def _refresh_access_token(self, refresh_token: str) -> ZoomTokenExchangeResponse:
        """Refresh access token using refresh token"""
        request_data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        response = await self.http_client.post(ZOOM_TOKEN_URL, data=request_data)
        response.raise_for_status()
        
        token_data = response.json()
        
        return ZoomTokenExchangeResponse(
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            token_type=token_data['token_type'],
            expires_in=token_data['expires_in'],
            scope=token_data['scope']
        )
    
    async def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Zoom API"""
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        response = await self.http_client.get(ZOOM_USER_INFO_URL, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    async def init_database(self) -> bool:
        """Initialize Zoom OAuth database table"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create OAuth tokens table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_oauth_tokens (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        zoom_user_id VARCHAR(255) NOT NULL,
                        email VARCHAR(255) UNIQUE,
                        access_token_encrypted TEXT NOT NULL,
                        refresh_token_encrypted TEXT,
                        token_type VARCHAR(50) DEFAULT 'Bearer',
                        scope TEXT,
                        account_id VARCHAR(255),
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        display_name VARCHAR(255),
                        expires_at TIMESTAMP WITH TIME ZONE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        last_used_at TIMESTAMP WITH TIME ZONE,
                        access_count INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT true,
                        created_by VARCHAR(255),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        metadata JSONB DEFAULT '{}'::jsonb,
                        UNIQUE(user_id)
                    );
                """)
                
                # Create indexes for performance
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_user_id 
                    ON zoom_oauth_tokens(user_id);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_zoom_user_id 
                    ON zoom_oauth_tokens(zoom_user_id);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_email 
                    ON zoom_oauth_tokens(email);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_expires_at 
                    ON zoom_oauth_tokens(expires_at);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_active 
                    ON zoom_oauth_tokens(is_active);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_last_used 
                    ON zoom_oauth_tokens(last_used_at);
                """)
                
                logger.info("Zoom OAuth database initialized successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to initialize Zoom OAuth database: {e}")
            return False
    
    async def generate_auth_url(self, user_id: str, state: Optional[str] = None) -> str:
        """Generate OAuth authorization URL"""
        if not state:
            state = self._generate_csrf_token(user_id)
        
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(ZOOM_SCOPES),
            'state': state
        }
        
        auth_url = f"{ZOOM_AUTH_URL}?{httpx.QueryParams(params)}"
        return auth_url
    
    async def exchange_code_for_token(self, code: str, user_id: str) -> Optional[ZoomToken]:
        """Exchange authorization code for access token"""
        try:
            # Exchange code for tokens
            token_response = await self._exchange_code_for_tokens(code, self.redirect_uri)
            
            # Get user information
            user_info = await self._get_user_info(token_response.access_token)
            
            # Create token object
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_response.expires_in)
            
            zoom_token = ZoomToken(
                user_id=user_id,
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                token_type=token_response.token_type,
                expires_at=expires_at,
                scope=token_response.scope,
                zoom_user_id=user_info.get('id'),
                email=user_info.get('email'),
                first_name=user_info.get('first_name'),
                last_name=user_info.get('last_name'),
                display_name=user_info.get('display_name'),
                account_id=user_info.get('account_id'),
                created_at=datetime.now(timezone.utc),
                last_used_at=datetime.now(timezone.utc),
                access_count=1,
                is_active=True
            )
            
            # Store token in database
            await self.store_token(zoom_token)
            
            logger.info(f"Successfully exchanged code for Zoom token for user {user_id}")
            return zoom_token
            
        except Exception as e:
            logger.error(f"Failed to exchange code for Zoom token: {e}")
            return None
    
    async def store_token(self, token: ZoomToken) -> bool:
        """Store OAuth token in database"""
        try:
            async with self.db_pool.acquire() as conn:
                # Encrypt tokens before storage
                encrypted_access_token = self._encrypt_token(token.access_token)
                encrypted_refresh_token = None
                
                if token.refresh_token:
                    encrypted_refresh_token = self._encrypt_token(token.refresh_token)
                
                # Insert or update token
                await conn.execute("""
                    INSERT INTO zoom_oauth_tokens (
                        user_id, zoom_user_id, email, access_token_encrypted,
                        refresh_token_encrypted, token_type, scope, account_id,
                        first_name, last_name, display_name, expires_at,
                        last_used_at, access_count, is_active, created_by
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (user_id) DO UPDATE SET
                        zoom_user_id = EXCLUDED.zoom_user_id,
                        email = EXCLUDED.email,
                        access_token_encrypted = EXCLUDED.access_token_encrypted,
                        refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                        token_type = EXCLUDED.token_type,
                        scope = EXCLUDED.scope,
                        account_id = EXCLUDED.account_id,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        display_name = EXCLUDED.display_name,
                        expires_at = EXCLUDED.expires_at,
                        last_used_at = EXCLUDED.last_used_at,
                        access_count = zoom_oauth_tokens.access_count + EXCLUDED.access_count,
                        is_active = EXCLUDED.is_active,
                        updated_at = NOW(),
                        metadata = EXCLUDED.metadata
                """, 
                token.user_id, token.zoom_user_id, token.email,
                encrypted_access_token, encrypted_refresh_token,
                token.token_type, token.scope, token.account_id,
                token.first_name, token.last_name, token.display_name,
                token.expires_at, token.last_used_at, token.access_count,
                token.is_active, token.user_id
                )
            
            logger.info(f"Stored Zoom OAuth token for user {token.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store Zoom OAuth token: {e}")
            return False
    
    async def get_token(self, user_id: str, include_refresh: bool = False) -> Optional[ZoomToken]:
        """Retrieve OAuth token for user"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT user_id, access_token_encrypted, refresh_token_encrypted,
                           token_type, scope, account_id, first_name, last_name,
                           display_name, expires_at, created_at, last_used_at,
                           access_count, is_active, zoom_user_id, email
                    FROM zoom_oauth_tokens 
                    WHERE user_id = $1 AND is_active = true
                """, user_id)
                
                if row:
                    # Decrypt tokens
                    access_token = self._decrypt_token(row['access_token_encrypted'])
                    refresh_token = None
                    
                    if include_refresh and row['refresh_token_encrypted']:
                        refresh_token = self._decrypt_token(row['refresh_token_encrypted'])
                    
                    return ZoomToken(
                        user_id=row['user_id'],
                        access_token=access_token,
                        refresh_token=refresh_token,
                        token_type=row['token_type'],
                        expires_at=row['expires_at'],
                        scope=row['scope'],
                        zoom_user_id=row['zoom_user_id'],
                        email=row['email'],
                        first_name=row['first_name'],
                        last_name=row['last_name'],
                        display_name=row['display_name'],
                        account_id=row['account_id'],
                        created_at=row['created_at'],
                        last_used_at=row['last_used_at'],
                        access_count=row['access_count'],
                        is_active=row['is_active']
                    )
                else:
                    logger.info(f"No active Zoom OAuth token found for user {user_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to retrieve Zoom OAuth token: {e}")
            return None
    
    async def refresh_token_if_needed(self, user_id: str) -> Optional[ZoomToken]:
        """Refresh token if it's expired or will expire soon"""
        try:
            token = await self.get_token(user_id, include_refresh=True)
            
            if not token:
                logger.warning(f"No token found for user {user_id}")
                return None
            
            # Check if token needs refresh
            now = datetime.now(timezone.utc)
            time_until_expiry = token.expires_at - now
            
            # Refresh if token expires within 5 minutes
            if time_until_expiry.total_seconds() < 300:
                if not token.refresh_token:
                    logger.error(f"Cannot refresh token for user {user_id} - no refresh token")
                    return None
                
                # Refresh token
                token_response = await self._refresh_access_token(token.refresh_token)
                
                # Update token
                token.access_token = token_response.access_token
                token.refresh_token = token_response.refresh_token or token.refresh_token
                token.expires_at = now + timedelta(seconds=token_response.expires_in)
                token.access_count += 1
                
                # Store updated token
                await self.store_token(token)
                
                logger.info(f"Successfully refreshed Zoom token for user {user_id}")
                return token
            else:
                # Token is still valid
                await self.update_last_used(user_id)
                return token
                
        except Exception as e:
            logger.error(f"Failed to refresh Zoom token for user {user_id}: {e}")
            return None
    
    async def update_last_used(self, user_id: str) -> bool:
        """Update last used timestamp for token"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE zoom_oauth_tokens 
                    SET last_used_at = NOW(),
                        access_count = access_count + 1
                    WHERE user_id = $1
                """, user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update last used for user {user_id}: {e}")
            return False
    
    async def revoke_token(self, user_id: str) -> bool:
        """Revoke OAuth token"""
        try:
            token = await self.get_token(user_id)
            
            if not token:
                return False
            
            # Revoke token with Zoom
            revoke_data = {
                'token': token.access_token
            }
            
            response = await self.http_client.post(ZOOM_REVOKE_URL, data=revoke_data)
            
            # Deactivate token in database regardless of revoke response
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE zoom_oauth_tokens 
                    SET is_active = false,
                        updated_at = NOW()
                    WHERE user_id = $1
                """, user_id)
            
            logger.info(f"Revoked Zoom OAuth token for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke Zoom token for user {user_id}: {e}")
            return False
    
    async def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens"""
        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute("""
                    UPDATE zoom_oauth_tokens 
                    SET is_active = false,
                        updated_at = NOW()
                    WHERE expires_at < NOW() - INTERVAL '1 day'
                    AND is_active = true
                """)
                
                # Extract count from result string
                count = 0
                if result:
                    count_str = result.split(' ')[-1]
                    try:
                        count = int(count_str)
                    except ValueError:
                        count = 0
                
                logger.info(f"Cleaned up {count} expired Zoom OAuth tokens")
                return count
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired Zoom tokens: {e}")
            return 0
    
    async def get_all_active_tokens(self) -> List[ZoomToken]:
        """Get all active tokens for monitoring"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT user_id, access_token_encrypted, refresh_token_encrypted,
                           token_type, scope, account_id, first_name, last_name,
                           display_name, expires_at, created_at, last_used_at,
                           access_count, is_active, zoom_user_id, email
                    FROM zoom_oauth_tokens 
                    WHERE is_active = true
                    ORDER BY last_used_at DESC
                """)
                
                tokens = []
                for row in rows:
                    access_token = self._decrypt_token(row['access_token_encrypted'])
                    
                    token = ZoomToken(
                        user_id=row['user_id'],
                        access_token=access_token,
                        refresh_token=None,  # Don't include refresh token for security
                        token_type=row['token_type'],
                        expires_at=row['expires_at'],
                        scope=row['scope'],
                        zoom_user_id=row['zoom_user_id'],
                        email=row['email'],
                        first_name=row['first_name'],
                        last_name=row['last_name'],
                        display_name=row['display_name'],
                        account_id=row['account_id'],
                        created_at=row['created_at'],
                        last_used_at=row['last_used_at'],
                        access_count=row['access_count'],
                        is_active=row['is_active']
                    )
                    
                    tokens.append(token)
                
                return tokens
                
        except Exception as e:
            logger.error(f"Failed to get active Zoom tokens: {e}")
            return []
    
    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()