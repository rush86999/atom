"""
BambooHR OAuth Database Handler
Database operations for BambooHR OAuth tokens and user data
Following ATOM database patterns
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from loguru import logger
import asyncpg

# BambooHR tokens table schema
BAMBOOHR_TOKENS_TABLE = """
CREATE TABLE IF NOT EXISTS bamboohr_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    subdomain VARCHAR(255),
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bamboohr_tokens_user_id ON bamboohr_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_bamboohr_tokens_expires_at ON bamboohr_tokens(expires_at);
"""

async def create_bamboohr_tables(db_pool):
    """Create BambooHR database tables"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(BAMBOOHR_TOKENS_TABLE)
            logger.info("BambooHR database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create BambooHR tables: {e}")
        return False

async def save_bamboohr_tokens(db_pool, user_id: str, token_data: Dict[str, Any]):
    """Save BambooHR OAuth tokens to database"""
    try:
        async with db_pool.acquire() as conn:
            # Calculate expiration time
            expires_at = None
            if token_data.get("expires_in"):
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])
            
            # Update or insert tokens
            await conn.execute("""
                INSERT INTO bamboohr_tokens 
                (user_id, access_token, refresh_token, token_type, subdomain, expires_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_type = EXCLUDED.token_type,
                    subdomain = EXCLUDED.subdomain,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = CURRENT_TIMESTAMP
            """, 
            user_id,
            token_data.get("access_token"),
            token_data.get("refresh_token"),
            token_data.get("token_type", "Bearer"),
            token_data.get("subdomain"),
            expires_at
            )
            
        logger.info(f"BambooHR tokens saved for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save BambooHR tokens: {e}")
        return False

async def get_user_bamboohr_tokens(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get BambooHR tokens for user"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT access_token, refresh_token, token_type, subdomain, expires_at, created_at, updated_at
                FROM bamboohr_tokens
                WHERE user_id = $1
            """, user_id)
            
            if row:
                return {
                    "access_token": row["access_token"],
                    "refresh_token": row["refresh_token"],
                    "token_type": row["token_type"],
                    "subdomain": row["subdomain"],
                    "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                    "created_at": row["created_at"].isoformat(),
                    "updated_at": row["updated_at"].isoformat()
                }
            return None
    except Exception as e:
        logger.error(f"Failed to get BambooHR tokens: {e}")
        return None

async def clear_bamboohr_tokens(db_pool, user_id: str):
    """Clear BambooHR tokens for user"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM bamboohr_tokens WHERE user_id = $1", user_id)
            logger.info(f"BambooHR tokens cleared for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to clear BambooHR tokens: {e}")
        return False