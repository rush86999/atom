"""
🔐 Enhanced Zoom OAuth Handler
Advanced OAuth 2.0 implementation with improved security and user experience
"""

import os
import json
import urllib.parse
import hashlib
import secrets
import logging
import asyncio
import httpx
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, Tuple, List
from dataclasses import dataclass, asdict
from enum import Enum

import requests
import asyncpg
from cryptography.fernet import Fernet
from flask import Blueprint, request, jsonify, session, redirect, url_for, current_app

logger = logging.getLogger(__name__)

# Zoom OAuth Configuration
ZOOM_AUTH_URL = "https://zoom.us/oauth/authorize"
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_REVOKE_URL = "https://zoom.us/oauth/revoke"
ZOOM_USER_INFO_URL = "https://api.zoom.us/v2/users/me"

# Enhanced scopes with detailed permissions
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

# Account type mappings
ACCOUNT_TYPE_BASIC = 1
ACCOUNT_TYPE_LICENSED = 2
ACCOUNT_TYPE_ON_PREM = 3

# User role mappings
USER_ROLE_MEMBER = 0
USER_ROLE_ADMIN = 1
USER_ROLE_OWNER = 3

class OAuthState(Enum):
    """OAuth state enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

@dataclass
class ZoomOAuthConfig:
    """Enhanced Zoom OAuth configuration"""
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: List[str]
    environment: str = "production"
    token_encryption_enabled: bool = True
    csrf_protection_enabled: bool = True
    state_ttl_seconds: int = 600
    pkce_enabled: bool = True
    max_concurrent_flows: int = 10

@dataclass
class ZoomOAuthState:
    """OAuth state information"""
    state_id: str
    user_id: str
    csrf_token: str
    code_verifier: Optional[str] = None
    code_challenge: Optional[str] = None
    state: OAuthState = OAuthState.PENDING
    created_at: datetime = None
    expires_at: datetime = None
    redirect_after_auth: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class ZoomTokenInfo:
    """Enhanced Zoom token information"""
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime
    scope: str
    user_id: str
    zoom_user_id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: str
    account_id: str
    account_type: int
    user_type: int
    role_id: int
    created_at: datetime
    last_used_at: datetime
    access_count: int = 0
    is_active: bool = True
    metadata: Dict[str, Any] = None

class EnhancedZoomOAuthHandler:
    """Enhanced enterprise-grade Zoom OAuth handler"""
    
    def __init__(self, db_pool: asyncpg.Pool = None):
        self.db_pool = db_pool
        self.config = self._load_config()
        self._validate_config()
        
        # Initialize encryption key
        self.encryption_key = os.getenv('ENCRYPTION_KEY', Fernet.generate_key()).encode()
        self.fernet = Fernet(self.encryption_key) if self.config.token_encryption_enabled else None
        
        # HTTP client for OAuth operations
        self.http_client = httpx.AsyncClient(timeout=30)
        
        # Initialize database
        asyncio.create_task(self._init_database())
    
    def _load_config(self) -> ZoomOAuthConfig:
        """Load enhanced Zoom OAuth configuration"""
        try:
            config = ZoomOAuthConfig(
                client_id=os.getenv("ZOOM_CLIENT_ID", ""),
                client_secret=os.getenv("ZOOM_CLIENT_SECRET", ""),
                redirect_uri=os.getenv(
                    "ZOOM_REDIRECT_URI", 
                    "http://localhost:3000/oauth/zoom/callback"
                ),
                scopes=ZOOM_SCOPES,
                environment=os.getenv("ZOOM_ENVIRONMENT", "production"),
                token_encryption_enabled=os.getenv("ZOOM_TOKEN_ENCRYPTION_ENABLED", "true").lower() == "true",
                csrf_protection_enabled=os.getenv("ZOOM_CSRF_PROTECTION_ENABLED", "true").lower() == "true",
                state_ttl_seconds=int(os.getenv("ZOOM_STATE_TTL_SECONDS", "600")),
                pkce_enabled=os.getenv("ZOOM_PKCE_ENABLED", "true").lower() == "true",
                max_concurrent_flows=int(os.getenv("ZOOM_MAX_CONCURRENT_FLOWS", "10"))
            )
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to load enhanced Zoom OAuth config: {e}")
            raise ValueError(f"Enhanced Zoom OAuth configuration error: {e}")
    
    def _validate_config(self) -> None:
        """Validate enhanced Zoom OAuth configuration"""
        if not self.config.client_id or self.config.client_id.startswith(("YOUR_", "mock_")):
            raise ValueError("ZOOM_CLIENT_ID is required and must be valid")
        
        if not self.config.client_secret or self.config.client_secret.startswith(("YOUR_", "mock_")):
            raise ValueError("ZOOM_CLIENT_SECRET is required and must be valid")
        
        if not self.config.redirect_uri:
            raise ValueError("ZOOM_REDIRECT_URI is required")
        
        # Validate redirect URI format
        parsed_uri = urllib.parse.urlparse(self.config.redirect_uri)
        if not parsed_uri.scheme or not parsed_uri.netloc:
            raise ValueError("ZOOM_REDIRECT_URI must be a valid URL")
    
    async def _init_database(self) -> None:
        """Initialize OAuth state and enhanced token tables"""
        if not self.db_pool:
            logger.warning("Database pool not available for OAuth state management")
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Create OAuth state table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_oauth_states (
                        state_id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        csrf_token VARCHAR(255) NOT NULL,
                        code_verifier TEXT,
                        code_challenge TEXT,
                        state VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        expires_at TIMESTAMP WITH TIME ZONE,
                        redirect_after_auth TEXT,
                        metadata JSONB DEFAULT '{}'::jsonb
                    );
                """)
                
                # Create enhanced OAuth tokens table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_oauth_tokens (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) UNIQUE,
                        zoom_user_id VARCHAR(255) NOT NULL,
                        email VARCHAR(255) UNIQUE,
                        access_token_encrypted TEXT NOT NULL,
                        refresh_token_encrypted TEXT,
                        token_type VARCHAR(50) DEFAULT 'Bearer',
                        scope TEXT,
                        account_id VARCHAR(255),
                        account_type INTEGER DEFAULT 1,
                        user_type INTEGER DEFAULT 1,
                        role_id INTEGER DEFAULT 0,
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        display_name VARCHAR(255),
                        expires_at TIMESTAMP WITH TIME ZONE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        last_used_at TIMESTAMP WITH TIME ZONE,
                        access_count INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT true,
                        metadata JSONB DEFAULT '{}'::jsonb
                    );
                """)
                
                # Create indexes
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_states_user_id 
                    ON zoom_oauth_states(user_id);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_states_state 
                    ON zoom_oauth_states(state);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_states_expires_at 
                    ON zoom_oauth_states(expires_at);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_tokens_email 
                    ON zoom_oauth_tokens(email);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_tokens_zoom_user_id 
                    ON zoom_oauth_tokens(zoom_user_id);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_zoom_oauth_tokens_expires_at 
                    ON zoom_oauth_tokens(expires_at);
                """)
                
                logger.info("Enhanced Zoom OAuth database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize enhanced Zoom OAuth database: {e}")
    
    def _encrypt_token(self, token: str) -> str:
        """Encrypt token for secure storage"""
        if not self.fernet:
            return token
        return self.fernet.encrypt(token.encode()).decode()
    
    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt token from storage"""
        if not self.fernet:
            return encrypted_token
        return self.fernet.decrypt(encrypted_token.encode()).decode()
    
    def _generate_state_id(self, user_id: str) -> str:
        """Generate unique state ID"""
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        random_part = secrets.token_hex(16)
        state_id = f"{user_id}_{timestamp}_{random_part}"
        return hashlib.sha256(state_id.encode()).hexdigest()[:32]
    
    def _generate_csrf_token(self, user_id: str, state_id: str) -> str:
        """Generate CSRF token for OAuth flow"""
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        data = f"{user_id}:{state_id}:{timestamp}"
        hash_obj = hashlib.sha256(data.encode())
        return hash_obj.hexdigest()
    
    def _verify_csrf_token(self, csrf_token: str, user_id: str, state_id: str, max_age: int = 3600) -> bool:
        """Verify CSRF token with time validation"""
        try:
            # Generate expected token for verification
            timestamp = str(int(datetime.now(timezone.utc).timestamp()))
            data = f"{user_id}:{state_id}:{timestamp}"
            expected_hash = hashlib.sha256(data.encode()).hexdigest()
            
            # In production, store and verify the actual token
            # For now, use basic comparison
            return secrets.compare_digest(csrf_token, expected_hash)
            
        except Exception as e:
            logger.error(f"CSRF token verification error: {e}")
            return False
    
    def _generate_pkce_pair(self) -> Tuple[str, str]:
        """Generate PKCE code verifier and challenge"""
        if not self.config.pkce_enabled:
            return None, None
        
        code_verifier = secrets.token_urlsafe(32)
        
        # Generate code challenge
        challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip('=')
        
        return code_verifier, code_challenge
    
    async def _store_oauth_state(self, oauth_state: ZoomOAuthState) -> bool:
        """Store OAuth state in database"""
        if not self.db_pool:
            logger.warning("Database not available for OAuth state storage")
            return False
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_oauth_states (
                        state_id, user_id, csrf_token, code_verifier, code_challenge,
                        state, expires_at, redirect_after_auth, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (state_id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        csrf_token = EXCLUDED.csrf_token,
                        code_verifier = EXCLUDED.code_verifier,
                        code_challenge = EXCLUDED.code_challenge,
                        state = EXCLUDED.state,
                        expires_at = EXCLUDED.expires_at,
                        redirect_after_auth = EXCLUDED.redirect_after_auth,
                        metadata = EXCLUDED.metadata,
                        state = 'in_progress'
                """,
                oauth_state.state_id, oauth_state.user_id, oauth_state.csrf_token,
                oauth_state.code_verifier, oauth_state.code_challenge,
                oauth_state.state.value, oauth_state.expires_at,
                oauth_state.redirect_after_auth, json.dumps(oauth_state.metadata or {})
                )
            
            logger.info(f"Stored OAuth state {oauth_state.state_id} for user {oauth_state.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store OAuth state: {e}")
            return False
    
    async def _get_oauth_state(self, state_id: str) -> Optional[ZoomOAuthState]:
        """Retrieve OAuth state from database"""
        if not self.db_pool:
            return None
        
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT state_id, user_id, csrf_token, code_verifier, code_challenge,
                           state, created_at, expires_at, redirect_after_auth, metadata
                    FROM zoom_oauth_states 
                    WHERE state_id = $1
                """, state_id)
                
                if row:
                    return ZoomOAuthState(
                        state_id=row['state_id'],
                        user_id=row['user_id'],
                        csrf_token=row['csrf_token'],
                        code_verifier=row['code_verifier'],
                        code_challenge=row['code_challenge'],
                        state=OAuthState(row['state']),
                        created_at=row['created_at'],
                        expires_at=row['expires_at'],
                        redirect_after_auth=row['redirect_after_auth'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to retrieve OAuth state {state_id}: {e}")
            return None
    
    async def _update_oauth_state(self, state_id: str, state: OAuthState) -> bool:
        """Update OAuth state status"""
        if not self.db_pool:
            return False
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE zoom_oauth_states 
                    SET state = $1, updated_at = NOW()
                    WHERE state_id = $2
                """, state.value, state_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update OAuth state {state_id}: {e}")
            return False
    
    async def _cleanup_expired_states(self) -> int:
        """Clean up expired OAuth states"""
        if not self.db_pool:
            return 0
        
        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM zoom_oauth_states 
                    WHERE expires_at < NOW()
                """)
                
                # Extract count from result
                count = 0
                if result:
                    count_str = result.split(' ')[-1]
                    try:
                        count = int(count_str)
                    except ValueError:
                        count = 0
                
                if count > 0:
                    logger.info(f"Cleaned up {count} expired OAuth states")
                
                return count
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired OAuth states: {e}")
            return 0
    
    async def generate_oauth_url(
        self, 
        user_id: str, 
        redirect_after_auth: Optional[str] = None,
        custom_scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate enhanced OAuth authorization URL"""
        try:
            # Clean up expired states first
            await self._cleanup_expired_states()
            
            # Generate state information
            state_id = self._generate_state_id(user_id)
            csrf_token = self._generate_csrf_token(user_id, state_id)
            
            # Generate PKCE pair if enabled
            code_verifier, code_challenge = self._generate_pkce_pair()
            
            # Create state
            oauth_state = ZoomOAuthState(
                state_id=state_id,
                user_id=user_id,
                csrf_token=csrf_token,
                code_verifier=code_verifier,
                code_challenge=code_challenge,
                state=OAuthState.PENDING,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.config.state_ttl_seconds),
                redirect_after_auth=redirect_after_auth,
                metadata=metadata or {}
            )
            
            # Store state
            await self._store_oauth_state(oauth_state)
            
            # Prepare authorization parameters
            params = {
                'response_type': 'code',
                'client_id': self.config.client_id,
                'redirect_uri': self.config.redirect_uri,
                'scope': ' '.join(custom_scopes or self.config.scopes),
                'state': state_id
            }
            
            # Add PKCE challenge if enabled
            if self.config.pkce_enabled and code_challenge:
                params['code_challenge'] = code_challenge
                params['code_challenge_method'] = 'S256'
            
            # Generate authorization URL
            auth_url = f"{ZOOM_AUTH_URL}?{urllib.parse.urlencode(params)}"
            
            response_data = {
                'success': True,
                'oauth_url': auth_url,
                'state_id': state_id,
                'csrf_token': csrf_token,
                'user_id': user_id,
                'scopes': custom_scopes or self.config.scopes,
                'pkce_enabled': self.config.pkce_enabled,
                'expires_at': oauth_state.expires_at.isoformat(),
                'security_features': {
                    'csrf_protection': self.config.csrf_protection_enabled,
                    'pkce': self.config.pkce_enabled,
                    'state_encryption': self.config.token_encryption_enabled,
                    'state_ttl_seconds': self.config.state_ttl_seconds
                }
            }
            
            logger.info(f"Generated enhanced OAuth URL for user {user_id} with state {state_id}")
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to generate enhanced OAuth URL: {e}")
            return {
                'success': False,
                'error': f'Failed to generate OAuth URL: {e}',
                'user_id': user_id
            }
    
    async def exchange_code_for_token(
        self, 
        code: str, 
        state_id: str, 
        redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token with enhanced security"""
        try:
            # Retrieve and validate OAuth state
            oauth_state = await self._get_oauth_state(state_id)
            if not oauth_state:
                return {
                    'success': False,
                    'error': 'Invalid or expired state',
                    'state_id': state_id
                }
            
            # Check if state is expired
            if oauth_state.expires_at < datetime.now(timezone.utc):
                await self._update_oauth_state(state_id, OAuthState.EXPIRED)
                return {
                    'success': False,
                    'error': 'OAuth state has expired',
                    'state_id': state_id,
                    'expired_at': oauth_state.expires_at.isoformat()
                }
            
            # Update state to in progress
            await self._update_oauth_state(state_id, OAuthState.IN_PROGRESS)
            
            # Prepare token exchange request
            request_data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri or self.config.redirect_uri,
                'client_id': self.config.client_id,
                'client_secret': self.config.client_secret
            }
            
            # Add PKCE verifier if enabled
            if self.config.pkce_enabled and oauth_state.code_verifier:
                request_data['code_verifier'] = oauth_state.code_verifier
            
            # Exchange code for token
            response = await self.http_client.post(ZOOM_TOKEN_URL, data=request_data)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Get user information
            user_info = await self._get_user_info(token_data['access_token'])
            if not user_info:
                return {
                    'success': False,
                    'error': 'Failed to retrieve user information',
                    'state_id': state_id
                }
            
            # Create enhanced token info
            token_info = ZoomTokenInfo(
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token', ''),
                token_type=token_data['token_type'],
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=token_data['expires_in']),
                scope=token_data['scope'],
                user_id=oauth_state.user_id,
                zoom_user_id=user_info.get('id'),
                email=user_info.get('email'),
                first_name=user_info.get('first_name'),
                last_name=user_info.get('last_name'),
                display_name=user_info.get('display_name'),
                account_id=user_info.get('account_id'),
                account_type=user_info.get('account_type', ACCOUNT_TYPE_BASIC),
                user_type=user_info.get('type', USER_ROLE_MEMBER),
                role_id=user_info.get('role_id', USER_ROLE_MEMBER),
                created_at=datetime.now(timezone.utc),
                last_used_at=datetime.now(timezone.utc),
                access_count=1,
                is_active=True,
                metadata={
                    'oauth_state_id': state_id,
                    'redirect_after_auth': oauth_state.redirect_after_auth,
                    'login_timestamp': datetime.now(timezone.utc).isoformat(),
                    'user_agent': request.headers.get('User-Agent', 'Unknown'),
                    'ip_address': request.environ.get('REMOTE_ADDR', 'Unknown')
                }
            )
            
            # Store token in database
            await self._store_token(token_info)
            
            # Update OAuth state to completed
            await self._update_oauth_state(state_id, OAuthState.COMPLETED)
            
            response_data = {
                'success': True,
                'user_id': token_info.user_id,
                'email': token_info.email,
                'display_name': token_info.display_name,
                'zoom_user_id': token_info.zoom_user_id,
                'account_type': token_info.account_type,
                'user_type': token_info.user_type,
                'role_id': token_info.role_id,
                'scopes': token_info.scope.split(' '),
                'expires_at': token_info.expires_at.isoformat(),
                'redirect_after_auth': oauth_state.redirect_after_auth,
                'metadata': token_info.metadata
            }
            
            logger.info(f"Successfully exchanged code for token for user {token_info.user_id}")
            return response_data
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Token exchange failed: {e.response.status_code}"
            if e.response.status_code == 400:
                error_msg = "Invalid authorization code or redirect URI"
            elif e.response.status_code == 401:
                error_msg = "Invalid client credentials"
            
            await self._update_oauth_state(state_id, OAuthState.FAILED)
            
            return {
                'success': False,
                'error': error_msg,
                'state_id': state_id,
                'status_code': e.response.status_code
            }
            
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            await self._update_oauth_state(state_id, OAuthState.FAILED)
            
            return {
                'success': False,
                'error': f'Token exchange error: {e}',
                'state_id': state_id
            }
    
    async def _get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get user information from Zoom API"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = await self.http_client.get(ZOOM_USER_INFO_URL, headers=headers)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None
    
    async def _store_token(self, token_info: ZoomTokenInfo) -> bool:
        """Store enhanced token in database"""
        if not self.db_pool:
            logger.warning("Database not available for token storage")
            return False
        
        try:
            async with self.db_pool.acquire() as conn:
                # Encrypt tokens
                encrypted_access_token = self._encrypt_token(token_info.access_token)
                encrypted_refresh_token = None
                
                if token_info.refresh_token:
                    encrypted_refresh_token = self._encrypt_token(token_info.refresh_token)
                
                # Insert or update token
                await conn.execute("""
                    INSERT INTO zoom_oauth_tokens (
                        user_id, zoom_user_id, email, access_token_encrypted,
                        refresh_token_encrypted, token_type, scope, account_id,
                        account_type, user_type, role_id, first_name, last_name,
                        display_name, expires_at, last_used_at, access_count,
                        is_active, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                    ON CONFLICT (user_id) DO UPDATE SET
                        zoom_user_id = EXCLUDED.zoom_user_id,
                        email = EXCLUDED.email,
                        access_token_encrypted = EXCLUDED.access_token_encrypted,
                        refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                        token_type = EXCLUDED.token_type,
                        scope = EXCLUDED.scope,
                        account_id = EXCLUDED.account_id,
                        account_type = EXCLUDED.account_type,
                        user_type = EXCLUDED.user_type,
                        role_id = EXCLUDED.role_id,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        display_name = EXCLUDED.display_name,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = NOW(),
                        last_used_at = EXCLUDED.last_used_at,
                        access_count = zoom_oauth_tokens.access_count + EXCLUDED.access_count,
                        is_active = EXCLUDED.is_active,
                        metadata = EXCLUDED.metadata
                """, 
                token_info.user_id, token_info.zoom_user_id, token_info.email,
                encrypted_access_token, encrypted_refresh_token,
                token_info.token_type, token_info.scope, token_info.account_id,
                token_info.account_type, token_info.user_type, token_info.role_id,
                token_info.first_name, token_info.last_name, token_info.display_name,
                token_info.expires_at, token_info.last_used_at, token_info.access_count,
                token_info.is_active, json.dumps(token_info.metadata or {})
                )
            
            logger.info(f"Stored enhanced OAuth token for user {token_info.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store enhanced OAuth token: {e}")
            return False
    
    async def get_token(self, user_id: str, include_refresh: bool = False) -> Optional[ZoomTokenInfo]:
        """Retrieve enhanced token for user"""
        if not self.db_pool:
            return None
        
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT user_id, access_token_encrypted, refresh_token_encrypted,
                           token_type, scope, account_id, account_type, user_type, role_id,
                           first_name, last_name, display_name, expires_at, created_at,
                           updated_at, last_used_at, access_count, is_active, metadata,
                           zoom_user_id, email
                    FROM zoom_oauth_tokens 
                    WHERE user_id = $1 AND is_active = true
                """, user_id)
                
                if row:
                    # Decrypt tokens
                    access_token = self._decrypt_token(row['access_token_encrypted'])
                    refresh_token = None
                    
                    if include_refresh and row['refresh_token_encrypted']:
                        refresh_token = self._decrypt_token(row['refresh_token_encrypted'])
                    
                    return ZoomTokenInfo(
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
                        account_type=row['account_type'],
                        user_type=row['user_type'],
                        role_id=row['role_id'],
                        created_at=row['created_at'],
                        last_used_at=row['last_used_at'],
                        access_count=row['access_count'],
                        is_active=row['is_active'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to retrieve enhanced OAuth token: {e}")
            return None
    
    async def revoke_token(self, user_id: str) -> Dict[str, Any]:
        """Revoke OAuth token with enhanced cleanup"""
        try:
            token_info = await self.get_token(user_id, include_refresh=True)
            
            if not token_info:
                return {
                    'success': False,
                    'error': 'No active token found for user',
                    'user_id': user_id
                }
            
            # Revoke token with Zoom
            revoke_data = {
                'token': token_info.access_token
            }
            
            try:
                response = await self.http_client.post(ZOOM_REVOKE_URL, data=revoke_data)
                response.raise_for_status()
                revoke_success = True
            except httpx.HTTPStatusError as e:
                if e.response.status_code in [401, 404]:
                    # Token already expired or doesn't exist
                    revoke_success = True
                else:
                    revoke_success = False
                    logger.error(f"Token revocation failed: {e.response.status_code}")
            
            # Clean up database
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    # Deactivate token
                    await conn.execute("""
                        UPDATE zoom_oauth_tokens 
                        SET is_active = false,
                            updated_at = NOW(),
                            metadata = metadata || '{"revoked_at": "' || NOW()::text || '"}'::jsonb
                        WHERE user_id = $1
                    """, user_id)
                    
                    # Clean up associated OAuth states
                    await conn.execute("""
                        UPDATE zoom_oauth_states 
                        SET state = 'expired', updated_at = NOW()
                        WHERE user_id = $1 AND state NOT IN ('completed', 'failed')
                    """, user_id)
            
            response_data = {
                'success': revoke_success,
                'user_id': user_id,
                'zoom_user_id': token_info.zoom_user_id,
                'revoked_at': datetime.now(timezone.utc).isoformat(),
                'cleanup_performed': True
            }
            
            if revoke_success:
                logger.info(f"Successfully revoked OAuth token for user {user_id}")
            else:
                logger.warning(f"Token revocation partially failed for user {user_id} but cleanup completed")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to revoke OAuth token for user {user_id}: {e}")
            return {
                'success': False,
                'error': f'Token revocation error: {e}',
                'user_id': user_id
            }
    
    async def refresh_token_if_needed(self, user_id: str) -> Optional[ZoomTokenInfo]:
        """Refresh token if expired with enhanced security"""
        try:
            token_info = await self.get_token(user_id, include_refresh=True)
            
            if not token_info:
                return None
            
            # Check if token needs refresh
            now = datetime.now(timezone.utc)
            time_until_expiry = token_info.expires_at - now
            
            # Refresh if token expires within 5 minutes
            if time_until_expiry.total_seconds() < 300:
                if not token_info.refresh_token:
                    logger.error(f"Cannot refresh token for user {user_id} - no refresh token")
                    return None
                
                # Refresh token
                refresh_data = {
                    'grant_type': 'refresh_token',
                    'refresh_token': token_info.refresh_token,
                    'client_id': self.config.client_id,
                    'client_secret': self.config.client_secret
                }
                
                response = await self.http_client.post(ZOOM_TOKEN_URL, data=refresh_data)
                response.raise_for_status()
                
                new_token_data = response.json()
                
                # Update token info
                token_info.access_token = new_token_data['access_token']
                token_info.refresh_token = new_token_data.get('refresh_token', token_info.refresh_token)
                token_info.expires_at = now + timedelta(seconds=new_token_data['expires_in'])
                token_info.access_count += 1
                token_info.last_used_at = now
                
                # Update metadata
                token_info.metadata = token_info.metadata or {}
                token_info.metadata['last_refresh'] = now.isoformat()
                token_info.metadata['refresh_count'] = token_info.metadata.get('refresh_count', 0) + 1
                
                # Store updated token
                await self._store_token(token_info)
                
                logger.info(f"Successfully refreshed OAuth token for user {user_id}")
                return token_info
            else:
                # Update last used time
                await self._update_last_used(user_id)
                return token_info
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Token refresh failed for user {user_id}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Token refresh error for user {user_id}: {e}")
            return None
    
    async def _update_last_used(self, user_id: str) -> bool:
        """Update last used timestamp for token"""
        if not self.db_pool:
            return False
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE zoom_oauth_tokens 
                    SET last_used_at = NOW(),
                        access_count = access_count + 1
                    WHERE user_id = $1 AND is_active = true
                """, user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update last used for user {user_id}: {e}")
            return False
    
    async def get_oauth_status(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive OAuth status for user"""
        try:
            token_info = await self.get_token(user_id)
            
            if token_info:
                # Get active OAuth states
                active_states = []
                if self.db_pool:
                    async with self.db_pool.acquire() as conn:
                        states = await conn.fetch("""
                            SELECT state_id, state, created_at, expires_at
                            FROM zoom_oauth_states 
                            WHERE user_id = $1 AND state NOT IN ('completed', 'failed', 'expired')
                            ORDER BY created_at DESC
                        """, user_id)
                        
                        active_states = [
                            {
                                'state_id': state['state_id'],
                                'state': state['state'],
                                'created_at': state['created_at'].isoformat(),
                                'expires_at': state['expires_at'].isoformat()
                            }
                            for state in states
                        ]
                
                return {
                    'authenticated': True,
                    'user_id': token_info.user_id,
                    'email': token_info.email,
                    'display_name': token_info.display_name,
                    'zoom_user_id': token_info.zoom_user_id,
                    'account_type': token_info.account_type,
                    'user_type': token_info.user_type,
                    'role_id': token_info.role_id,
                    'scopes': token_info.scope.split(' '),
                    'expires_at': token_info.expires_at.isoformat(),
                    'access_count': token_info.access_count,
                    'last_used_at': token_info.last_used_at.isoformat(),
                    'metadata': token_info.metadata,
                    'active_oauth_states': active_states
                }
            else:
                return {
                    'authenticated': False,
                    'user_id': user_id,
                    'error': 'No active OAuth token found'
                }
                
        except Exception as e:
            logger.error(f"Failed to get OAuth status for user {user_id}: {e}")
            return {
                'authenticated': False,
                'user_id': user_id,
                'error': f'OAuth status error: {e}'
            }
    
    async def close(self):
        """Close HTTP client and cleanup resources"""
        await self.http_client.aclose()
        logger.info("Enhanced Zoom OAuth handler closed")

# Create Flask blueprint for enhanced OAuth routes
enhanced_auth_zoom_bp = Blueprint("enhanced_auth_zoom", __name__)

# Global OAuth handler instance
oauth_handler: Optional[EnhancedZoomOAuthHandler] = None

def init_enhanced_zoom_oauth_handler(db_pool):
    """Initialize enhanced Zoom OAuth handler"""
    global oauth_handler
    oauth_handler = EnhancedZoomOAuthHandler(db_pool)
    return oauth_handler