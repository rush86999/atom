"""
ATOM Teams OAuth Token Database Handler
Stores and retrieves Microsoft Teams OAuth tokens from PostgreSQL
"""

import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from loguru import logger

async def get_user_teams_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Teams tokens for a user from database"""
    try:
        # Try to import database functions from existing modules
        try:
            from .db_oauth_gdrive import get_tokens
            # Reuse the generic OAuth token storage
            from flask import current_app
            
            db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
            if not db_conn_pool:
                logger.error("Teams: Database connection pool not available")
                return None
                
            tokens = await get_tokens(db_conn_pool, user_id, "teams")
            return tokens
            
        except ImportError:
            logger.warning("Teams: Using mock token storage (database not available)")
            # Mock implementation for testing
            return {
                'user_id': user_id,
                'access_token': 'mock_access_token',
                'refresh_token': 'mock_refresh_token',
                'expires_in': 3600,
                'scope': 'https://graph.microsoft.com/.default',
                'token_type': 'Bearer',
                'created_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Teams: Error getting tokens for user {user_id}: {e}")
        return None

async def save_user_teams_tokens(user_id: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
    """Save Teams tokens for a user to database"""
    try:
        # Try to import database functions from existing modules
        try:
            from .db_oauth_gdrive import store_tokens
            from flask import current_app
            
            db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
            if not db_conn_pool:
                logger.error("Teams: Database connection pool not available")
                return {"success": False, "error": "Database not available"}
            
            # Calculate expires_at
            expires_in = token_data.get('expires_in', 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            # Store tokens using generic OAuth storage
            await store_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="teams",
                access_token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                expires_at=expires_at,
                scope=token_data.get('scope', '')
            )
            
            logger.info(f"Teams: Tokens saved successfully for user {user_id}")
            return {"success": True, "message": "Tokens saved successfully"}
            
        except ImportError:
            logger.warning("Teams: Using mock token storage (database not available)")
            # Mock implementation for testing
            logger.info(f"Teams: Mock saving tokens for user {user_id}")
            return {"success": True, "message": "Tokens saved (mock)"}
            
    except Exception as e:
        logger.error(f"Teams: Error saving tokens for user {user_id}: {e}")
        return {"success": False, "error": str(e)}

async def update_user_teams_tokens(user_id: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update Teams tokens for a user in database"""
    try:
        # Try to import database functions from existing modules
        try:
            from .db_oauth_gdrive import update_tokens
            from flask import current_app
            
            db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
            if not db_conn_pool:
                logger.error("Teams: Database connection pool not available")
                return {"success": False, "error": "Database not available"}
            
            # Calculate expires_at
            expires_in = token_data.get('expires_in', 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            # Update tokens using generic OAuth storage
            await update_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="teams",
                access_token=token_data.get('access_token'),
                expires_at=expires_at
            )
            
            logger.info(f"Teams: Tokens updated successfully for user {user_id}")
            return {"success": True, "message": "Tokens updated successfully"}
            
        except ImportError:
            logger.warning("Teams: Using mock token storage (database not available)")
            # Mock implementation for testing
            logger.info(f"Teams: Mock updating tokens for user {user_id}")
            return {"success": True, "message": "Tokens updated (mock)"}
            
    except Exception as e:
        logger.error(f"Teams: Error updating tokens for user {user_id}: {e}")
        return {"success": False, "error": str(e)}

async def delete_user_teams_tokens(user_id: str) -> Dict[str, Any]:
    """Delete Teams tokens for a user from database"""
    try:
        # Try to import database functions from existing modules
        try:
            from .db_oauth_gdrive import delete_tokens
            from flask import current_app
            
            db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
            if not db_conn_pool:
                logger.error("Teams: Database connection pool not available")
                return {"success": False, "error": "Database not available"}
            
            # Delete tokens using generic OAuth storage
            await delete_tokens(db_conn_pool, user_id, "teams")
            
            logger.info(f"Teams: Tokens deleted successfully for user {user_id}")
            return {"success": True, "message": "Tokens deleted successfully"}
            
        except ImportError:
            logger.warning("Teams: Using mock token storage (database not available)")
            # Mock implementation for testing
            logger.info(f"Teams: Mock deleting tokens for user {user_id}")
            return {"success": True, "message": "Tokens deleted (mock)"}
            
    except Exception as e:
        logger.error(f"Teams: Error deleting tokens for user {user_id}: {e}")
        return {"success": False, "error": str(e)}

async def is_teams_token_valid(user_id: str) -> bool:
    """Check if Teams token is valid for a user"""
    try:
        tokens = await get_user_teams_tokens(user_id)
        if not tokens:
            return False
        
        # Check if token has expired
        created_at = tokens.get('created_at')
        expires_in = tokens.get('expires_in', 3600)
        
        if created_at and expires_in:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            elif created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
                
            expires_at = created_at + timedelta(seconds=expires_in)
            return datetime.now(timezone.utc) < expires_at
        
        return True  # Assume valid if we can't determine expiry
        
    except Exception as e:
        logger.error(f"Teams: Error checking token validity for user {user_id}: {e}")
        return False

async def refresh_teams_tokens_if_needed(user_id: str, teams_service) -> bool:
    """Refresh Teams tokens if they're expired"""
    try:
        if await is_teams_token_valid(user_id):
            return True  # Token is still valid
        
        # Get current tokens
        tokens = await get_user_teams_tokens(user_id)
        if not tokens or not tokens.get('refresh_token'):
            logger.error(f"Teams: No refresh token available for user {user_id}")
            return False
        
        # Configure service with refresh token
        teams_service._refresh_token = tokens['refresh_token']
        
        # Refresh the token
        refresh_success = await teams_service._refresh_access_token()
        
        if refresh_success:
            # Save new tokens
            token_data = {
                'access_token': teams_service._access_token,
                'refresh_token': teams_service._refresh_token,
                'expires_in': 3600,  # Default 1 hour
                'scope': tokens.get('scope', ''),
                'token_type': 'Bearer'
            }
            
            save_result = await save_user_teams_tokens(user_id, token_data)
            return save_result.get('success', False)
        
        return False
        
    except Exception as e:
        logger.error(f"Teams: Error refreshing tokens for user {user_id}: {e}")
        return False

# Helper function to get tokens (non-async version for compatibility)
def get_user_teams_tokens_sync(user_id: str) -> Optional[Dict[str, Any]]:
    """Synchronous version of get_user_teams_tokens"""
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(get_user_teams_tokens(user_id))
    except Exception as e:
        logger.error(f"Teams: Error getting sync tokens for user {user_id}: {e}")
        return None

# Helper function to save tokens (non-async version for compatibility)
def save_user_teams_tokens_sync(user_id: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous version of save_user_teams_tokens"""
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(save_user_teams_tokens(user_id, token_data))
    except Exception as e:
        logger.error(f"Teams: Error saving sync tokens for user {user_id}: {e}")
        return {"success": False, "error": str(e)}