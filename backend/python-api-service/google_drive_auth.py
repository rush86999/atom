"""
Google Drive Authentication Service
Handles OAuth 2.0 flow, token management, and session handling
"""

import os
import json
import secrets
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import aiofiles
import aiohttp
from contextlib import asynccontextmanager

# Local imports
from loguru import logger
from config import get_config_instance
from extensions import db, redis_client

# Try to import Google Drive service
try:
    from google_drive_service import GoogleDriveService, get_google_drive_service
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logger.warning("Google Drive service not available")

@dataclass
class OAuthToken:
    """OAuth token data model"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scope: List[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        """Post-initialization"""
        if self.scope is None:
            self.scope = []
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at
    
    @property
    def expires_in(self) -> int:
        """Get seconds until token expires"""
        if not self.expires_at:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "scope": self.scope,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OAuthToken':
        """Create from dictionary"""
        token = cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope", []),
            created_at=datetime.fromisoformat(data["created_at"])
        )
        
        if data.get("expires_at"):
            token.expires_at = datetime.fromisoformat(data["expires_at"])
        
        return token

@dataclass
class UserSession:
    """User session data model"""
    session_id: str
    user_id: str
    email: str
    name: str
    state: str
    created_at: datetime = None
    expires_at: datetime = None
    tokens: Optional[OAuthToken] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Post-initialization"""
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tokens": self.tokens.to_dict() if self.tokens else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSession':
        """Create from dictionary"""
        session = cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            email=data["email"],
            name=data["name"],
            state=data["state"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            metadata=data.get("metadata", {})
        )
        
        if data.get("tokens"):
            session.tokens = OAuthToken.from_dict(data["tokens"])
        
        return session

class GoogleDriveAuth:
    """Google Drive Authentication Service"""
    
    def __init__(self, config=None):
        self.config = config or get_config_instance()
        self.security_config = self.config.security
        
        # Session management
        self.session_ttl = self.security_config.jwt_expiration
        self.refresh_token_ttl = self.security_config.refresh_token_expiration
        
        # Google Drive service
        self._drive_service: Optional[GoogleDriveService] = None
        
        # Session storage
        self._sessions: Dict[str, UserSession] = {}
        
        logger.info("Google Drive Authentication Service initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_drive_service()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def _ensure_drive_service(self):
        """Ensure Google Drive service is available"""
        
        if self._drive_service is None:
            self._drive_service = await get_google_drive_service()
        
        if not self._drive_service:
            raise ValueError("Google Drive service not available")
    
    async def close(self):
        """Close authentication service"""
        
        # Clear sessions
        self._sessions.clear()
        
        # Close drive service
        if self._drive_service:
            await self._drive_service.close()
            self._drive_service = None
        
        logger.debug("Google Drive Authentication Service closed")
    
    # ==================== AUTHENTICATION FLOW ====================
    
    async def start_auth_flow(self, 
                             redirect_uri: Optional[str] = None,
                             state: Optional[str] = None) -> Dict[str, Any]:
        """Start OAuth authentication flow"""
        
        try:
            await self._ensure_drive_service()
            
            # Generate state if not provided
            if not state:
                state = secrets.token_urlsafe(32)
            
            # Create session
            session_id = secrets.token_urlsafe(32)
            session = UserSession(
                session_id=session_id,
                user_id="",
                email="",
                name="",
                state=state,
                expires_at=datetime.utcnow() + timedelta(minutes=30)  # 30 minute auth window
            )
            
            # Store session
            self._sessions[session_id] = session
            
            # Generate authorization URL
            authorization_url = self._drive_service.create_oauth_flow(
                redirect_uri=redirect_uri,
                state=state
            )
            
            # Store session in Redis for persistence
            await self._store_session(session)
            
            logger.info(f"Started auth flow for session: {session_id}")
            
            return {
                "success": True,
                "session_id": session_id,
                "authorization_url": authorization_url,
                "state": state,
                "expires_at": session.expires_at.isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to start auth flow: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def complete_auth_flow(self, 
                                code: str, 
                                state: str,
                                session_id: str) -> Dict[str, Any]:
        """Complete OAuth authentication flow"""
        
        try:
            # Validate session
            session = await self._get_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "Invalid or expired session"
                }
            
            if session.state != state:
                return {
                    "success": False,
                    "error": "Invalid state parameter"
                }
            
            if session.is_expired:
                return {
                    "success": False,
                    "error": "Authentication session expired"
                }
            
            # Exchange code for tokens
            await self._ensure_drive_service()
            token_result = await self._drive_service.exchange_code_for_tokens(code)
            
            if not token_result["success"]:
                return {
                    "success": False,
                    "error": token_result.get("error", "Failed to exchange code for tokens")
                }
            
            # Update session with user info
            user_data = token_result.get("user", {})
            tokens_data = token_result.get("tokens", {})
            
            session.user_id = user_data.get("id", "")
            session.email = user_data.get("email", "")
            session.name = user_data.get("name", "")
            session.metadata = {
                "avatar_url": user_data.get("avatar_url"),
                "total_quota": user_data.get("total_quota"),
                "used_quota": user_data.get("used_quota")
            }
            
            # Create token object
            tokens = OAuthToken(
                access_token=tokens_data["access_token"],
                refresh_token=tokens_data["refresh_token"],
                token_type=tokens_data.get("token_type", "Bearer"),
                scope=tokens_data.get("scopes", []),
                expires_at=datetime.fromisoformat(tokens_data["expires_at"]) if tokens_data.get("expires_at") else None
            )
            
            session.tokens = tokens
            session.expires_at = datetime.utcnow() + timedelta(seconds=self.session_ttl)
            
            # Store session and tokens
            await self._store_session(session)
            await self._store_tokens(session.user_id, tokens)
            
            logger.info(f"Completed auth flow for user: {session.email}")
            
            return {
                "success": True,
                "session_id": session_id,
                "user": {
                    "id": session.user_id,
                    "email": session.email,
                    "name": session.name,
                    "metadata": session.metadata
                },
                "tokens": {
                    "access_token": tokens.access_token,
                    "expires_at": tokens.expires_at.isoformat() if tokens.expires_at else None,
                    "scope": tokens.scope
                },
                "expires_at": session.expires_at.isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to complete auth flow: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def refresh_tokens(self, user_id: str) -> Dict[str, Any]:
        """Refresh user tokens"""
        
        try:
            # Get stored tokens
            tokens = await self._get_tokens(user_id)
            if not tokens:
                return {
                    "success": False,
                    "error": "No tokens found for user"
                }
            
            if not tokens.refresh_token:
                return {
                    "success": False,
                    "error": "No refresh token available"
                }
            
            await self._ensure_drive_service()
            
            # Refresh tokens
            refresh_result = await self._drive_service.refresh_token(tokens.refresh_token)
            
            if not refresh_result["success"]:
                return {
                    "success": False,
                    "error": refresh_result.get("error", "Failed to refresh tokens")
                }
            
            # Update token object
            tokens.access_token = refresh_result["access_token"]
            tokens.expires_at = datetime.fromisoformat(refresh_result["expires_at"]) if refresh_result.get("expires_at") else None
            tokens.created_at = datetime.utcnow()
            
            # Store updated tokens
            await self._store_tokens(user_id, tokens)
            
            # Update any active sessions
            for session in self._sessions.values():
                if session.user_id == user_id and session.tokens:
                    session.tokens = tokens
                    await self._store_session(session)
            
            logger.info(f"Refreshed tokens for user: {user_id}")
            
            return {
                "success": True,
                "tokens": {
                    "access_token": tokens.access_token,
                    "expires_at": tokens.expires_at.isoformat() if tokens.expires_at else None,
                    "expires_in": tokens.expires_in
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to refresh tokens: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== SESSION MANAGEMENT ====================
    
    async def validate_session(self, session_id: str) -> Dict[str, Any]:
        """Validate user session"""
        
        try:
            session = await self._get_session(session_id)
            
            if not session:
                return {
                    "valid": False,
                    "error": "Session not found"
                }
            
            if session.is_expired:
                # Remove expired session
                await self._remove_session(session_id)
                return {
                    "valid": False,
                    "error": "Session expired"
                }
            
            # Check if tokens need refresh
            if session.tokens and session.tokens.is_expired:
                refresh_result = await self.refresh_tokens(session.user_id)
                
                if refresh_result["success"]:
                    # Update session tokens
                    access_token = refresh_result["tokens"]["access_token"]
                    expires_at = datetime.fromisoformat(refresh_result["tokens"]["expires_at"]) if refresh_result["tokens"].get("expires_at") else None
                    session.tokens.access_token = access_token
                    session.tokens.expires_at = expires_at
                    session.tokens.created_at = datetime.utcnow()
                    
                    # Store updated session
                    await self._store_session(session)
                else:
                    # Failed to refresh tokens, invalidate session
                    await self._remove_session(session_id)
                    return {
                        "valid": False,
                        "error": "Token refresh failed"
                    }
            
            # Extend session expiration
            session.expires_at = datetime.utcnow() + timedelta(seconds=self.session_ttl)
            await self._store_session(session)
            
            return {
                "valid": True,
                "session": session.to_dict(),
                "expires_at": session.expires_at.isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to validate session: {e}")
            return {
                "valid": False,
                "error": str(e)
            }
    
    async def invalidate_session(self, session_id: str) -> Dict[str, Any]:
        """Invalidate user session"""
        
        try:
            session = await self._get_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "Session not found"
                }
            
            # Remove session
            await self._remove_session(session_id)
            
            # Optionally remove tokens if this is the last session
            user_sessions = [s for s in self._sessions.values() if s.user_id == session.user_id]
            if len(user_sessions) <= 1:
                await self._remove_tokens(session.user_id)
            
            logger.info(f"Invalidated session: {session_id}")
            
            return {
                "success": True,
                "message": "Session invalidated successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to invalidate session: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== USER OPERATIONS ====================
    
    async def get_user_info(self, session_id: str) -> Dict[str, Any]:
        """Get user information from session"""
        
        try:
            session_result = await self.validate_session(session_id)
            if not session_result["valid"]:
                return {
                    "success": False,
                    "error": session_result.get("error", "Invalid session")
                }
            
            session = session_result["session"]
            
            return {
                "success": True,
                "user": {
                    "id": session["user_id"],
                    "email": session["email"],
                    "name": session["name"],
                    "metadata": session["metadata"]
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_user_tokens(self, session_id: str) -> Dict[str, Any]:
        """Get user tokens from session"""
        
        try:
            session_result = await self.validate_session(session_id)
            if not session_result["valid"]:
                return {
                    "success": False,
                    "error": session_result.get("error", "Invalid session")
                }
            
            session = session_result["session"]
            tokens = session.get("tokens")
            
            if not tokens:
                return {
                    "success": False,
                    "error": "No tokens found"
                }
            
            return {
                "success": True,
                "tokens": {
                    "access_token": tokens["access_token"],
                    "token_type": tokens["token_type"],
                    "expires_at": tokens["expires_at"],
                    "scope": tokens["scope"]
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to get user tokens: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== STORAGE OPERATIONS ====================
    
    async def _store_session(self, session: UserSession):
        """Store session in memory and Redis"""
        
        # Store in memory
        self._sessions[session.session_id] = session
        
        # Store in Redis
        if redis_client:
            session_key = f"atom:google_drive:session:{session.session_id}"
            session_data = json.dumps(session.to_dict(), default=str)
            await redis_client.setex(
                session_key,
                self.session_ttl + 300,  # 5 minute buffer
                session_data
            )
    
    async def _get_session(self, session_id: str) -> Optional[UserSession]:
        """Get session from memory or Redis"""
        
        # Try memory first
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        # Try Redis
        if redis_client:
            session_key = f"atom:google_drive:session:{session_id}"
            session_data = await redis_client.get(session_key)
            
            if session_data:
                try:
                    session_dict = json.loads(session_data)
                    session = UserSession.from_dict(session_dict)
                    
                    # Cache in memory
                    self._sessions[session_id] = session
                    return session
                except Exception as e:
                    logger.error(f"Failed to parse session data: {e}")
        
        return None
    
    async def _remove_session(self, session_id: str):
        """Remove session from memory and Redis"""
        
        # Remove from memory
        if session_id in self._sessions:
            del self._sessions[session_id]
        
        # Remove from Redis
        if redis_client:
            session_key = f"atom:google_drive:session:{session_id}"
            await redis_client.delete(session_key)
    
    async def _store_tokens(self, user_id: str, tokens: OAuthToken):
        """Store tokens in Redis"""
        
        if redis_client:
            tokens_key = f"atom:google_drive:tokens:{user_id}"
            tokens_data = json.dumps(tokens.to_dict(), default=str)
            
            # Store with long TTL for refresh token persistence
            await redis_client.setex(
                tokens_key,
                self.refresh_token_ttl,
                tokens_data
            )
    
    async def _get_tokens(self, user_id: str) -> Optional[OAuthToken]:
        """Get tokens from Redis"""
        
        if redis_client:
            tokens_key = f"atom:google_drive:tokens:{user_id}"
            tokens_data = await redis_client.get(tokens_key)
            
            if tokens_data:
                try:
                    tokens_dict = json.loads(tokens_data)
                    return OAuthToken.from_dict(tokens_dict)
                except Exception as e:
                    logger.error(f"Failed to parse tokens data: {e}")
        
        return None
    
    async def _remove_tokens(self, user_id: str):
        """Remove tokens from Redis"""
        
        if redis_client:
            tokens_key = f"atom:google_drive:tokens:{user_id}"
            await redis_client.delete(tokens_key)
    
    # ==================== UTILITY METHODS ====================
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        
        try:
            active_sessions = [
                s for s in self._sessions.values() 
                if not s.is_expired
            ]
            
            expired_sessions = [
                s for s in self._sessions.values() 
                if s.is_expired
            ]
            
            return {
                "total_sessions": len(self._sessions),
                "active_sessions": len(active_sessions),
                "expired_sessions": len(expired_sessions),
                "memory_usage": len(self._sessions),
                "unique_users": len(set(s.user_id for s in active_sessions if s.user_id))
            }
        
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {
                "error": str(e)
            }
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        
        try:
            expired_session_ids = [
                session_id for session_id, session in self._sessions.items()
                if session.is_expired
            ]
            
            for session_id in expired_session_ids:
                await self._remove_session(session_id)
            
            logger.info(f"Cleaned up {len(expired_session_ids)} expired sessions")
            
            return {
                "success": True,
                "cleaned_sessions": len(expired_session_ids)
            }
        
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for authentication service"""
        
        try:
            session_stats = await self.get_session_stats()
            
            # Test Redis connection
            redis_healthy = True
            if redis_client:
                try:
                    await redis_client.ping()
                except Exception:
                    redis_healthy = False
            
            # Test Google Drive service
            drive_healthy = False
            if self._drive_service:
                try:
                    drive_status = await self._drive_service.get_connection_status()
                    drive_healthy = drive_status.get("connected", False)
                except Exception:
                    drive_healthy = False
            
            return {
                "status": "healthy" if redis_healthy and drive_healthy else "degraded",
                "session_stats": session_stats,
                "redis_healthy": redis_healthy,
                "google_drive_healthy": drive_healthy,
                "configuration": {
                    "session_ttl": self.session_ttl,
                    "refresh_token_ttl": self.refresh_token_ttl
                }
            }
        
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

# Global authentication instance
_google_drive_auth: Optional[GoogleDriveAuth] = None

async def get_google_drive_auth() -> Optional[GoogleDriveAuth]:
    """Get global Google Drive authentication instance"""
    
    global _google_drive_auth
    
    if _google_drive_auth is None:
        try:
            config = get_config_instance()
            _google_drive_auth = GoogleDriveAuth(config)
            logger.info("Google Drive authentication service created")
        except Exception as e:
            logger.error(f"Failed to create Google Drive authentication service: {e}")
            _google_drive_auth = None
    
    return _google_drive_auth

def clear_google_drive_auth():
    """Clear global authentication instance"""
    
    global _google_drive_auth
    _google_drive_auth = None
    logger.info("Google Drive authentication service cleared")

# Export classes and functions
__all__ = [
    'GoogleDriveAuth',
    'OAuthToken',
    'UserSession',
    'get_google_drive_auth',
    'clear_google_drive_auth'
]