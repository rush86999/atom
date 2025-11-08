import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import asyncpg
from cryptography.fernet import Fernet

# Database encryption key
ENCRYPTION_KEY = os.getenv("ATOM_OAUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
ENCRYPTOR = Fernet(ENCRYPTION_KEY.encode())

logger = logging.getLogger(__name__)

def encrypt_data(data: str) -> str:
    """Encrypt sensitive data"""
    return ENCRYPTOR.encrypt(data.encode()).decode()

def decrypt_data(data: str) -> str:
    """Decrypt sensitive data"""
    return ENCRYPTOR.decrypt(data.encode()).decode()

async def create_azure_tokens_table(db_pool: asyncpg.Pool):
    """Create Azure OAuth tokens table"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_azure_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL UNIQUE,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    scope TEXT,
                    token_type VARCHAR(50),
                    profile_data JSONB,
                    tenant_id VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_oauth_azure_user_id ON oauth_azure_tokens(user_id);
                CREATE INDEX IF NOT EXISTS idx_oauth_azure_expires_at ON oauth_azure_tokens(expires_at);
                CREATE INDEX IF NOT EXISTS idx_oauth_azure_updated_at ON oauth_azure_tokens(updated_at);
                CREATE INDEX IF NOT EXISTS idx_oauth_azure_tenant_id ON oauth_azure_tokens(tenant_id);
            """)
            
            logger.info("Azure tokens table created successfully")
            return True
    except Exception as e:
        logger.error(f"Failed to create Azure tokens table: {e}")
        return False

async def store_user_azure_tokens(db_pool: asyncpg.Pool, user_id: str, tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Store Azure OAuth tokens for user"""
    try:
        async with db_pool.acquire() as conn:
            # Encrypt sensitive tokens
            encrypted_access = encrypt_data(tokens["access_token"])
            encrypted_refresh = encrypt_data(tokens["refresh_token"])
            
            # Convert expires_at to timestamp
            expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)
            
            # Extract profile data
            profile_data = json.dumps(tokens.get("profile", {}))
            
            # Check if user already has tokens
            existing = await conn.fetchrow(
                "SELECT id FROM oauth_azure_tokens WHERE user_id = $1",
                user_id
            )
            
            if existing:
                # Update existing tokens
                await conn.execute("""
                    UPDATE oauth_azure_tokens 
                    SET access_token = $1, refresh_token = $2, expires_at = $3, 
                        scope = $4, token_type = $5, profile_data = $6, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $7
                """, encrypted_access, encrypted_refresh, expires_at,
                      tokens.get("scope"), tokens.get("token_type"), profile_data, user_id)
            else:
                # Insert new tokens
                await conn.execute("""
                    INSERT INTO oauth_azure_tokens 
                    (user_id, access_token, refresh_token, expires_at, scope, token_type, profile_data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, user_id, encrypted_access, encrypted_refresh, expires_at,
                      tokens.get("scope"), tokens.get("token_type"), profile_data)
            
            return {
                "success": True,
                "message": "Azure tokens stored successfully"
            }
            
    except Exception as e:
        logger.error(f"Failed to store Azure tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def get_user_azure_tokens(db_pool: asyncpg.Pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Azure OAuth tokens for user"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT access_token, refresh_token, expires_at, scope, token_type, 
                       profile_data, tenant_id, updated_at
                FROM oauth_azure_tokens 
                WHERE user_id = $1
            """, user_id)
            
            if row:
                # Decrypt tokens
                return {
                    "access_token": decrypt_data(row["access_token"]),
                    "refresh_token": decrypt_data(row["refresh_token"]),
                    "expires_at": row["expires_at"],
                    "scope": row["scope"],
                    "token_type": row["token_type"],
                    "profile": row["profile_data"],
                    "tenant_id": row["tenant_id"],
                    "updated_at": row["updated_at"]
                }
            return None
            
    except Exception as e:
        logger.error(f"Failed to get Azure tokens for {user_id}: {e}")
        return None

async def update_user_azure_tokens(db_pool: asyncpg.Pool, user_id: str, tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Update Azure OAuth tokens for user"""
    try:
        async with db_pool.acquire() as conn:
            # Encrypt sensitive tokens
            encrypted_access = encrypt_data(tokens["access_token"])
            encrypted_refresh = encrypt_data(tokens["refresh_token"])
            
            # Convert expires_at to timestamp
            expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)
            
            await conn.execute("""
                UPDATE oauth_azure_tokens 
                SET access_token = $1, refresh_token = $2, expires_at = $3, 
                    scope = $4, token_type = $5, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = $6
            """, encrypted_access, encrypted_refresh, expires_at,
                  tokens.get("scope"), tokens.get("token_type"), user_id)
            
            return {
                "success": True,
                "message": "Azure tokens updated successfully"
            }
            
    except Exception as e:
        logger.error(f"Failed to update Azure tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def delete_user_azure_tokens(db_pool: asyncpg.Pool, user_id: str) -> Dict[str, Any]:
    """Delete Azure OAuth tokens for user"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM oauth_azure_tokens WHERE user_id = $1", user_id)
            
            return {
                "success": True,
                "message": "Azure tokens deleted successfully"
            }
            
    except Exception as e:
        logger.error(f"Failed to delete Azure tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def get_expired_tokens(db_pool: asyncpg.Pool) -> list:
    """Get list of users with expired tokens"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, refresh_token
                FROM oauth_azure_tokens 
                WHERE expires_at < CURRENT_TIMESTAMP
            """)
            return rows
            
    except Exception as e:
        logger.error(f"Failed to get expired Azure tokens: {e}")
        return []

async def cache_azure_resource(db_pool: asyncpg.Pool, user_id: str, resource_type: str, 
                             resource_id: str, resource_data: Dict[str, Any],
                             region: str = None, resource_group: str = None, 
                             status: str = None) -> bool:
    """Cache Azure resource data"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO azure_resources_cache 
                (user_id, resource_type, resource_id, resource_data, region, resource_group, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id, resource_id)
                DO UPDATE SET 
                    resource_data = EXCLUDED.resource_data,
                    region = EXCLUDED.region,
                    resource_group = EXCLUDED.resource_group,
                    status = EXCLUDED.status,
                    updated_at = CURRENT_TIMESTAMP
            """, user_id, resource_type, resource_id, json.dumps(resource_data),
                region, resource_group, status)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to cache Azure resource: {e}")
        return False

async def get_cached_azure_resources(db_pool: asyncpg.Pool, user_id: str, resource_type: str = None) -> List[Dict[str, Any]]:
    """Get cached Azure resources for user"""
    try:
        async with db_pool.acquire() as conn:
            if resource_type:
                rows = await conn.fetch("""
                    SELECT resource_id, resource_data, region, resource_group, status, updated_at
                    FROM azure_resources_cache 
                    WHERE user_id = $1 AND resource_type = $2
                    ORDER BY updated_at DESC
                """, user_id, resource_type)
            else:
                rows = await conn.fetch("""
                    SELECT resource_type, resource_id, resource_data, region, resource_group, status, updated_at
                    FROM azure_resources_cache 
                    WHERE user_id = $1
                    ORDER BY resource_type, updated_at DESC
                """, user_id)
            
            return [dict(row) for row in rows]
            
    except Exception as e:
        logger.error(f"Failed to get cached Azure resources: {e}")
        return []

async def store_azure_cost_analysis(db_pool: asyncpg.Pool, user_id: str, cost_data: List[Dict[str, Any]]) -> bool:
    """Store Azure cost analysis data"""
    try:
        async with db_pool.acquire() as conn:
            for cost_item in cost_data:
                await conn.execute("""
                    INSERT INTO azure_cost_analysis 
                    (user_id, resource_group, service_name, cost_amount, currency, cost_date, billing_period)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT DO NOTHING
                """, user_id, cost_item.get("resource_group"), cost_item.get("service_name"),
                    cost_item.get("cost"), cost_item.get("currency", "USD"),
                    cost_item.get("date"), cost_item.get("billing_period", "Monthly"))
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to store Azure cost analysis: {e}")
        return False

async def log_azure_activity(db_pool: asyncpg.Pool, user_id: str, action: str, 
                          resource_type: str = None, resource_id: str = None,
                          action_details: Dict[str, Any] = None, status: str = "success",
                          error_message: str = None, ip_address: str = None, 
                          user_agent: str = None) -> bool:
    """Log Azure activity"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO azure_activity_logs 
                (user_id, action, resource_type, resource_id, action_details, status, error_message, ip_address, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, user_id, action, resource_type, resource_id, json.dumps(action_details or {}),
                status, error_message, ip_address, user_agent)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to log Azure activity: {e}")
        return False

async def get_azure_activity_logs(db_pool: asyncpg.Pool, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get Azure activity logs for user"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT action, resource_type, resource_id, action_details, status, error_message, created_at
                FROM azure_activity_logs 
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, user_id, limit)
            
            return [dict(row) for row in rows]
            
    except Exception as e:
        logger.error(f"Failed to get Azure activity logs: {e}")
        return []

async def cleanup_old_azure_cache(db_pool: asyncpg.Pool, days: int = 90) -> bool:
    """Clean up old cache entries"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM azure_resources_cache 
                WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '{days} days'
            """, days=days)
            
            await conn.execute("""
                DELETE FROM azure_webhook_events 
                WHERE processed = TRUE AND processed_at < CURRENT_TIMESTAMP - INTERVAL '7 days'
            """)
            
            await conn.execute("""
                DELETE FROM azure_activity_logs 
                WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days'
            """)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to cleanup old Azure cache: {e}")
        return False