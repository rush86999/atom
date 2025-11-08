import os
import json
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from asyncpg import Pool
from urllib.parse import parse_qs
import base64
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class SlackTokenManager:
    """Slack OAuth Token Management Database Functions"""
    
    def __init__(self):
        self.fernet = Fernet(os.getenv("ATOM_OAUTH_ENCRYPTION_KEY"))
    
    async def init_slack_oauth_table(self, db_pool: Pool) -> bool:
        """Initialize Slack OAuth table"""
        try:
            # Run the schema if it doesn't exist
            schema_file = "migrations/slack_schema.sql"
            if os.path.exists(schema_file):
                async with db_pool.acquire() as conn:
                    with open(schema_file, 'r') as f:
                        schema_sql = f.read()
                    await conn.execute(schema_sql)
                logger.info("Slack OAuth tables initialized")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Slack OAuth tables: {e}")
            return False
    
    async def store_slack_tokens(self, db_pool: Pool, user_id: str, 
                               team_id: str, team_name: str, tokens: Dict[str, Any]) -> bool:
        """Store Slack OAuth tokens in database"""
        try:
            # Encrypt tokens
            encrypted_tokens = self.fernet.encrypt(json.dumps(tokens).encode())
            
            # Calculate expiration
            expires_at = None
            if tokens.get("expires_in"):
                expires_at = datetime.now(timezone.utc) + timezone.timedelta(seconds=tokens["expires_in"])
            
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO slack_oauth_tokens 
                    (user_id, access_token, refresh_token, bot_token,
                     expires_at, scope, team_id, team_name, bot_user_id, encrypted_tokens)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET
                        access_token = EXCLUDED.access_token,
                        refresh_token = EXCLUDED.refresh_token,
                        bot_token = EXCLUDED.bot_token,
                        expires_at = EXCLUDED.expires_at,
                        scope = EXCLUDED.scope,
                        team_id = EXCLUDED.team_id,
                        team_name = EXCLUDED.team_name,
                        bot_user_id = EXCLUDED.bot_user_id,
                        encrypted_tokens = EXCLUDED.encrypted_tokens,
                        updated_at = CURRENT_TIMESTAMP,
                        is_active = TRUE
                """, user_id, tokens.get("access_token"), tokens.get("refresh_token"),
                     tokens.get("bot_access_token"), expires_at, tokens.get("scope", ""),
                     team_id, team_name, tokens.get("bot_user_id"),
                     encrypted_tokens.decode())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store Slack tokens: {e}")
            return False
    
    async def get_user_slack_tokens(self, db_pool: Pool, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's Slack tokens from database"""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT user_id, access_token, refresh_token, bot_token,
                           expires_at, scope, team_id, team_name, bot_user_id,
                           encrypted_tokens, is_active, updated_at
                    FROM slack_oauth_tokens
                    WHERE user_id = $1 AND is_active = TRUE
                """, user_id)
                
                if not row:
                    return None
                
                # Decrypt tokens
                decrypted_tokens = self.fernet.decrypt(row["encrypted_tokens"].encode())
                token_data = json.loads(decrypted_tokens.decode())
                
                # Combine with database info
                return {
                    "user_id": row["user_id"],
                    "access_token": row["access_token"],
                    "refresh_token": row["refresh_token"],
                    "bot_token": row["bot_token"],
                    "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                    "scope": row["scope"],
                    "team_id": row["team_id"],
                    "team_name": row["team_name"],
                    "bot_user_id": row["bot_user_id"],
                    "token_data": token_data,
                    "is_active": row["is_active"],
                    "updated_at": row["updated_at"].isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get Slack tokens: {e}")
            return None
    
    async def refresh_slack_tokens(self, db_pool: Pool, user_id: str, 
                               new_tokens: Dict[str, Any]) -> bool:
        """Update user's Slack tokens"""
        try:
            # Encrypt new tokens
            encrypted_tokens = self.fernet.encrypt(json.dumps(new_tokens).encode())
            
            # Calculate new expiration
            expires_at = None
            if new_tokens.get("expires_in"):
                expires_at = datetime.now(timezone.utc) + timezone.timedelta(seconds=new_tokens["expires_in"])
            
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE slack_oauth_tokens
                    SET access_token = $2,
                        refresh_token = COALESCE($3, refresh_token),
                        bot_token = COALESCE($4, bot_token),
                        expires_at = $5,
                        scope = COALESCE($6, scope),
                        encrypted_tokens = $7,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id, new_tokens.get("access_token"),
                     new_tokens.get("refresh_token"), new_tokens.get("bot_access_token"),
                     expires_at, new_tokens.get("scope"), encrypted_tokens.decode())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh Slack tokens: {e}")
            return False
    
    async def delete_slack_tokens(self, db_pool: Pool, user_id: str) -> bool:
        """Delete user's Slack tokens (logout)"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE slack_oauth_tokens
                    SET is_active = FALSE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete Slack tokens: {e}")
            return False
    
    async def is_token_expired(self, db_pool: Pool, user_id: str) -> bool:
        """Check if user's Slack token is expired"""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT expires_at FROM slack_oauth_tokens
                    WHERE user_id = $1 AND is_active = TRUE
                """, user_id)
                
                if not row or not row["expires_at"]:
                    return True
                
                # Add 5-minute buffer
                return row["expires_at"] < datetime.now(timezone.utc) - timezone.timedelta(minutes=5)
                
        except Exception as e:
            logger.error(f"Failed to check token expiration: {e}")
            return True
    
    async def cache_user_data(self, db_pool: Pool, user_id: str, 
                          slack_user: Dict[str, Any]) -> bool:
        """Cache user data"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO slack_users_cache 
                    (user_id, slack_user_id, user_data, name, real_name,
                     display_name, email, phone, title, status, status_emoji,
                     is_bot, is_admin, is_owner, presence, tz, tz_label,
                     updated_at, deleted, image, has_image, has_status,
                     has_phone, has_title, has_email)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                            $12, $13, $14, $15, $16, $17, $18, $19, $20,
                            $21, $22, $23, $24, $25, $26, $27)
                    ON CONFLICT (user_id, slack_user_id)
                    DO UPDATE SET
                        user_data = EXCLUDED.user_data,
                        name = EXCLUDED.name,
                        real_name = EXCLUDED.real_name,
                        display_name = EXCLUDED.display_name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        title = EXCLUDED.title,
                        status = EXCLUDED.status,
                        status_emoji = EXCLUDED.status_emoji,
                        is_bot = EXCLUDED.is_bot,
                        is_admin = EXCLUDED.is_admin,
                        is_owner = EXCLUDED.is_owner,
                        presence = EXCLUDED.presence,
                        tz = EXCLUDED.tz,
                        tz_label = EXCLUDED.tz_label,
                        updated_at = EXCLUDED.updated_at,
                        deleted = EXCLUDED.deleted,
                        image = EXCLUDED.image,
                        has_image = EXCLUDED.has_image,
                        has_status = EXCLUDED.has_status,
                        has_phone = EXCLUDED.has_phone,
                        has_title = EXCLUDED.has_title,
                        has_email = EXCLUDED.has_email
                """, user_id, slack_user["id"], json.dumps(slack_user),
                     slack_user.get("name", ""), slack_user.get("real_name", ""),
                     slack_user.get("display_name", ""), slack_user.get("email", ""),
                     slack_user.get("phone", ""), slack_user.get("title", ""),
                     slack_user.get("status", ""), slack_user.get("status_emoji", ""),
                     slack_user.get("is_bot", False), slack_user.get("is_admin", False),
                     slack_user.get("is_owner", False), slack_user.get("presence", "offline"),
                     slack_user.get("tz", ""), slack_user.get("tz_label", ""),
                     slack_user.get("updated", 0), slack_user.get("deleted", False),
                     slack_user.get("image", ""), slack_user.get("hasImage", False),
                     slack_user.get("hasStatus", False), slack_user.get("hasPhone", False),
                     slack_user.get("hasTitle", False), slack_user.get("hasEmail", False))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache user data: {e}")
            return False
    
    async def cache_channel_data(self, db_pool: Pool, user_id: str, 
                             channel: Dict[str, Any]) -> bool:
        """Cache channel data"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO slack_channels_cache 
                    (user_id, channel_id, channel_data, name, name_normalized,
                     topic, purpose, is_archived, is_general, is_private,
                     is_im, is_mpim, created, creator, last_read,
                     unread_count, unread_count_display, num_members,
                     member_count, is_member, user_name, user_image,
                     updated_at, has_topic, has_purpose, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15, $16, $17, $18,
                            $19, $20, $21, $22, $23, $24, $25, $26)
                    ON CONFLICT (user_id, channel_id)
                    DO UPDATE SET
                        channel_data = EXCLUDED.channel_data,
                        name = EXCLUDED.name,
                        name_normalized = EXCLUDED.name_normalized,
                        topic = EXCLUDED.topic,
                        purpose = EXCLUDED.purpose,
                        is_archived = EXCLUDED.is_archived,
                        is_general = EXCLUDED.is_general,
                        is_private = EXCLUDED.is_private,
                        is_im = EXCLUDED.is_im,
                        is_mpim = EXCLUDED.is_mpim,
                        creator = EXCLUDED.creator,
                        last_read = EXCLUDED.last_read,
                        unread_count = EXCLUDED.unread_count,
                        unread_count_display = EXCLUDED.unread_count_display,
                        num_members = EXCLUDED.num_members,
                        member_count = EXCLUDED.member_count,
                        is_member = EXCLUDED.is_member,
                        user_name = EXCLUDED.user_name,
                        user_image = EXCLUDED.user_image,
                        updated_at = EXCLUDED.updated_at,
                        has_topic = EXCLUDED.has_topic,
                        has_purpose = EXCLUDED.has_purpose,
                        is_active = EXCLUDED.is_active
                """, user_id, channel["id"], json.dumps(channel),
                     channel.get("name", ""), channel.get("name_normalized", ""),
                     channel.get("topic", ""), channel.get("purpose", ""),
                     channel.get("is_archived", False), channel.get("is_general", False),
                     channel.get("is_private", True), channel.get("is_im", False),
                     channel.get("is_mpim", False), channel.get("created", 0),
                     channel.get("creator", ""), channel.get("last_read", ""),
                     channel.get("unread_count", 0), channel.get("unread_count_display", 0),
                     channel.get("num_members", 0), channel.get("member_count", 0),
                     channel.get("is_member", True), channel.get("user_name", ""),
                     channel.get("user_image", ""), channel.get("created", 0),
                     channel.get("has_topic", False), channel.get("has_purpose", False),
                     channel.get("is_active", True))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache channel data: {e}")
            return False
    
    async def log_slack_activity(self, db_pool: Pool, user_id: str, 
                              action: str, details: Dict[str, Any] = None,
                              status: str = "success", error_message: str = None,
                              channel_id: str = None, message_id: str = None,
                              file_id: str = None) -> bool:
        """Log Slack activity"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO slack_activity_logs 
                    (user_id, action, action_details, status, error_message,
                     channel_id, message_id, file_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, user_id, action, json.dumps(details or {}), status,
                     error_message, channel_id, message_id, file_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log Slack activity: {e}")
            return False
    
    async def get_slack_stats(self, db_pool: Pool, user_id: str) -> Dict[str, Any]:
        """Get Slack usage statistics"""
        try:
            async with db_pool.acquire() as conn:
                # Execute the stats function
                row = await conn.fetchrow("""
                    SELECT get_slack_stats($1) as stats
                """, user_id)
                
                return row["stats"] if row else {}
                
        except Exception as e:
            logger.error(f"Failed to get Slack stats: {e}")
            return {}
    
    async def cleanup_slack_cache(self, db_pool: Pool, user_id: str, 
                              days_old: int = 30) -> int:
        """Clean up old Slack cache data"""
        try:
            async with db_pool.acquire() as conn:
                # Use the cleanup function
                result = await conn.execute("""
                    SELECT cleanup_slack_cache($1, $2)
                """, user_id, days_old)
                
                # Return deleted count
                if "CLEANUP" in result:
                    return int(result.split()[0])
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to cleanup Slack cache: {e}")
            return 0

# Global token manager instance
slack_token_manager = None

def get_slack_token_manager() -> SlackTokenManager:
    """Get global Slack token manager instance"""
    global slack_token_manager
    if slack_token_manager is None:
        slack_token_manager = SlackTokenManager()
    return slack_token_manager

# Convenience functions
async def init_slack_oauth_table(db_pool: Pool) -> bool:
    """Initialize Slack OAuth tables"""
    manager = get_slack_token_manager()
    return await manager.init_slack_oauth_table(db_pool)

async def get_user_slack_tokens(db_pool: Pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get user's Slack tokens"""
    manager = get_slack_token_manager()
    return await manager.get_user_slack_tokens(db_pool, user_id)

async def store_slack_tokens(db_pool: Pool, user_id: str, team_id: str,
                           team_name: str, tokens: Dict[str, Any]) -> bool:
    """Store Slack tokens"""
    manager = get_slack_token_manager()
    return await manager.store_slack_tokens(db_pool, user_id, team_id, team_name, tokens)

async def refresh_slack_tokens(db_pool: Pool, user_id: str, new_tokens: Dict[str, Any]) -> bool:
    """Refresh Slack tokens"""
    manager = get_slack_token_manager()
    return await manager.refresh_slack_tokens(db_pool, user_id, new_tokens)

async def delete_slack_tokens(db_pool: Pool, user_id: str) -> bool:
    """Delete Slack tokens"""
    manager = get_slack_token_manager()
    return await manager.delete_slack_tokens(db_pool, user_id)

async def is_slack_token_expired(db_pool: Pool, user_id: str) -> bool:
    """Check if Slack token is expired"""
    manager = get_slack_token_manager()
    return await manager.is_token_expired(db_pool, user_id)