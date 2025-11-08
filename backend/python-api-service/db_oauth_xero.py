import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
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

async def create_xero_tokens_table(db_pool: asyncpg.Pool):
    """Create Xero OAuth tokens table"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_xero_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL UNIQUE,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    scope TEXT,
                    token_type VARCHAR(50),
                    tenant_id VARCHAR(255),
                    tenant_name VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_oauth_xero_user_id ON oauth_xero_tokens(user_id);
                CREATE INDEX IF NOT EXISTS idx_oauth_xero_expires_at ON oauth_xero_tokens(expires_at);
                CREATE INDEX IF NOT EXISTS idx_oauth_xero_updated_at ON oauth_xero_tokens(updated_at);
            """)
            
            logger.info("Xero tokens table created successfully")
            return True
    except Exception as e:
        logger.error(f"Failed to create Xero tokens table: {e}")
        return False

async def store_user_xero_tokens(db_pool: asyncpg.Pool, user_id: str, tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Store Xero OAuth tokens for user"""
    try:
        async with db_pool.acquire() as conn:
            # Encrypt sensitive tokens
            encrypted_access = encrypt_data(tokens["access_token"])
            encrypted_refresh = encrypt_data(tokens["refresh_token"])
            
            # Convert expires_at to timestamp
            expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)
            
            # Check if user already has tokens
            existing = await conn.fetchrow(
                "SELECT id FROM oauth_xero_tokens WHERE user_id = $1",
                user_id
            )
            
            if existing:
                # Update existing tokens
                await conn.execute("""
                    UPDATE oauth_xero_tokens 
                    SET access_token = $1, refresh_token = $2, expires_at = $3, 
                        scope = $4, token_type = $5, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $6
                """, encrypted_access, encrypted_refresh, expires_at,
                      tokens.get("scope"), tokens.get("token_type"), user_id)
            else:
                # Insert new tokens
                await conn.execute("""
                    INSERT INTO oauth_xero_tokens 
                    (user_id, access_token, refresh_token, expires_at, scope, token_type)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, user_id, encrypted_access, encrypted_refresh, expires_at,
                      tokens.get("scope"), tokens.get("token_type"))
            
            return {
                "success": True,
                "message": "Xero tokens stored successfully"
            }
            
    except Exception as e:
        logger.error(f"Failed to store Xero tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def get_user_xero_tokens(db_pool: asyncpg.Pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Xero OAuth tokens for user"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT access_token, refresh_token, expires_at, scope, token_type, 
                       tenant_id, tenant_name, updated_at
                FROM oauth_xero_tokens 
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
                    "tenant_id": row["tenant_id"],
                    "tenant_name": row["tenant_name"],
                    "updated_at": row["updated_at"]
                }
            return None
            
    except Exception as e:
        logger.error(f"Failed to get Xero tokens for {user_id}: {e}")
        return None

async def update_user_xero_tokens(db_pool: asyncpg.Pool, user_id: str, tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Update Xero OAuth tokens for user"""
    try:
        async with db_pool.acquire() as conn:
            # Encrypt sensitive tokens
            encrypted_access = encrypt_data(tokens["access_token"])
            encrypted_refresh = encrypt_data(tokens["refresh_token"])
            
            # Convert expires_at to timestamp
            expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)
            
            await conn.execute("""
                UPDATE oauth_xero_tokens 
                SET access_token = $1, refresh_token = $2, expires_at = $3, 
                    scope = $4, token_type = $5, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = $6
            """, encrypted_access, encrypted_refresh, expires_at,
                  tokens.get("scope"), tokens.get("token_type"), user_id)
            
            return {
                "success": True,
                "message": "Xero tokens updated successfully"
            }
            
    except Exception as e:
        logger.error(f"Failed to update Xero tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def delete_user_xero_tokens(db_pool: asyncpg.Pool, user_id: str) -> Dict[str, Any]:
    """Delete Xero OAuth tokens for user"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM oauth_xero_tokens WHERE user_id = $1", user_id)
            
            return {
                "success": True,
                "message": "Xero tokens deleted successfully"
            }
            
    except Exception as e:
        logger.error(f"Failed to delete Xero tokens for {user_id}: {e}")
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
                FROM oauth_xero_tokens 
                WHERE expires_at < CURRENT_TIMESTAMP
            """)
            return rows
            
    except Exception as e:
        logger.error(f"Failed to get expired tokens: {e}")
        return []

async def update_tenant_info(db_pool: asyncpg.Pool, user_id: str, tenant_id: str, tenant_name: str) -> bool:
    """Update tenant information for user"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE oauth_xero_tokens 
                SET tenant_id = $1, tenant_name = $2, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = $3
            """, tenant_id, tenant_name, user_id)
            return True
            
    except Exception as e:
        logger.error(f"Failed to update tenant info for {user_id}: {e}")
        return False

async def cleanup_old_tokens(db_pool: asyncpg.Pool, days: int = 90) -> bool:
    """Clean up tokens older than specified days"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM oauth_xero_tokens 
                WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '{days} days'
            """, days=days)
            return True
            
    except Exception as e:
        logger.error(f"Failed to cleanup old Xero tokens: {e}")
        return False