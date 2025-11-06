#!/usr/bin/env python3
"""
🗃️ Salesforce OAuth Database Handler
Secure token storage and management for Salesforce integrations
"""

import os
import logging
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List

import asyncpg
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class SalesforceOAuthDatabase:
    """Enterprise-grade Salesforce OAuth token management"""
    
    def __init__(self, db_pool: asyncpg.Pool, encryption_key: Optional[str] = None):
        self.db_pool = db_pool
        
        # Initialize encryption for token storage
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            # Use default key for development (should be overridden in production)
            self.fernet = Fernet(os.getenv('ENCRYPTION_KEY', Fernet.generate_key()).encode())
        
        self.encryption_enabled = bool(encryption_key or os.getenv('ENCRYPTION_KEY'))
    
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

async def init_salesforce_oauth_table(db_pool: asyncpg.Pool) -> bool:
    """
    Initialize Salesforce OAuth tokens table with enterprise-grade schema
    
    Args:
        db_pool: Database connection pool
        
    Returns:
        True if initialization successful
    """
    try:
        async with db_pool.acquire() as conn:
            # Create Salesforce OAuth tokens table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS salesforce_oauth_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    email VARCHAR(255),
                    username VARCHAR(255) NOT NULL,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    token_type VARCHAR(50) DEFAULT 'Bearer',
                    scope TEXT,
                    instance_url VARCHAR(500) NOT NULL,
                    organization_id VARCHAR(255),
                    profile_id VARCHAR(255),
                    environment VARCHAR(50) DEFAULT 'production',
                    expires_at TIMESTAMP WITH TIME ZONE,
                    issued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_used_at TIMESTAMP WITH TIME ZONE,
                    is_active BOOLEAN DEFAULT true,
                    access_count INTEGER DEFAULT 0,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    UNIQUE(user_id, username)
                );
                
                -- Create indexes for performance
                CREATE INDEX IF NOT EXISTS idx_salesforce_oauth_user_id 
                ON salesforce_oauth_tokens(user_id);
                
                CREATE INDEX IF NOT EXISTS idx_salesforce_oauth_email 
                ON salesforce_oauth_tokens(email);
                
                CREATE INDEX IF NOT EXISTS idx_salesforce_oauth_username 
                ON salesforce_oauth_tokens(username);
                
                CREATE INDEX IF NOT EXISTS idx_salesforce_oauth_org_id 
                ON salesforce_oauth_tokens(organization_id);
                
                CREATE INDEX IF NOT EXISTS idx_salesforce_oauth_expires_at 
                ON salesforce_oauth_tokens(expires_at);
                
                CREATE INDEX IF NOT EXISTS idx_salesforce_oauth_active 
                ON salesforce_oauth_tokens(is_active);
                
                CREATE INDEX IF NOT EXISTS idx_salesforce_oauth_metadata 
                ON salesforce_oauth_tokens USING GIN(metadata);
            """)
            
            # Create audit log table for OAuth operations
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS salesforce_oauth_audit_log (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    username VARCHAR(255),
                    action VARCHAR(100) NOT NULL,
                    details JSONB DEFAULT '{}'::jsonb,
                    ip_address INET,
                    user_agent TEXT,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    success BOOLEAN DEFAULT true,
                    error_message TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_salesforce_audit_user_id 
                ON salesforce_oauth_audit_log(user_id);
                
                CREATE INDEX IF NOT EXISTS idx_salesforce_audit_action 
                ON salesforce_oauth_audit_log(action);
                
                CREATE INDEX IF NOT EXISTS idx_salesforce_audit_timestamp 
                ON salesforce_oauth_audit_log(timestamp);
            """)
            
            # Create token usage statistics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS salesforce_token_usage (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    username VARCHAR(255),
                    date_YYYYMM VARCHAR(7) NOT NULL, -- YYYY-MM format
                    api_calls INTEGER DEFAULT 0,
                    data_transferred BIGINT DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(user_id, date_YYYYMM)
                );
                
                CREATE INDEX IF NOT EXISTS idx_salesforce_usage_user_date 
                ON salesforce_token_usage(user_id, date_YYYYMM);
            """)
            
            logger.info("✅ Salesforce OAuth tables initialized successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize Salesforce OAuth tables: {e}")
        return False

async def store_salesforce_tokens(
    db_pool: asyncpg.Pool,
    user_id: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    scope: str = "",
    organization_id: str = "",
    profile_id: str = "",
    instance_url: str = "",
    username: str = "",
    environment: str = "production",
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: str = "",
    user_agent: str = ""
) -> Dict[str, Any]:
    """
    Store or update Salesforce OAuth tokens with security and audit logging
    
    Args:
        db_pool: Database connection pool
        user_id: Salesforce user ID
        access_token: OAuth access token
        refresh_token: OAuth refresh token
        expires_at: Token expiration timestamp
        scope: Granted OAuth scopes
        organization_id: Salesforce organization ID
        profile_id: Salesforce profile ID
        instance_url: Salesforce instance URL
        username: Salesforce username
        environment: production or sandbox
        metadata: Additional metadata
        ip_address: Client IP address
        user_agent: Client user agent
        
    Returns:
        Result dictionary with success status
    """
    try:
        async with db_pool.acquire() as conn:
            # Start transaction
            async with conn.transaction():
                # Check if user already has tokens
                existing = await conn.fetchrow("""
                    SELECT id, access_count FROM salesforce_oauth_tokens 
                    WHERE user_id = $1 AND username = $2
                """, user_id, username)
                
                # Prepare metadata
                if metadata is None:
                    metadata = {}
                metadata_json = json.dumps(metadata)
                
                if existing:
                    # Update existing tokens
                    await conn.execute("""
                        UPDATE salesforce_oauth_tokens 
                        SET 
                            access_token = $3,
                            refresh_token = $4,
                            scope = $5,
                            instance_url = $6,
                            organization_id = $7,
                            profile_id = $8,
                            environment = $9,
                            expires_at = $10,
                            updated_at = NOW(),
                            last_used_at = NOW(),
                            is_active = true,
                            access_count = access_count + 1,
                            metadata = $11
                        WHERE user_id = $1 AND username = $2
                    """, user_id, username, access_token, refresh_token, scope,
                        instance_url, organization_id, profile_id, environment,
                        expires_at, metadata_json)
                    
                    action = "token_updated"
                else:
                    # Insert new tokens
                    await conn.execute("""
                        INSERT INTO salesforce_oauth_tokens 
                        (user_id, username, access_token, refresh_token, scope, 
                         instance_url, organization_id, profile_id, environment,
                         expires_at, last_used_at, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), $11)
                    """, user_id, username, access_token, refresh_token, scope,
                        instance_url, organization_id, profile_id, environment,
                        expires_at, metadata_json)
                    
                    action = "token_created"
                
                # Log audit trail
                await conn.execute("""
                    INSERT INTO salesforce_oauth_audit_log 
                    (user_id, username, action, details, ip_address, user_agent)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, user_id, username, action, metadata_json, ip_address, user_agent)
                
                logger.info(f"✅ Successfully stored Salesforce tokens for user: {user_id}")
                
                return {
                    "success": True,
                    "action": action,
                    "user_id": user_id,
                    "username": username,
                    "expires_at": expires_at.isoformat(),
                    "environment": environment,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
    except Exception as e:
        logger.error(f"❌ Failed to store Salesforce tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": "token_storage_failed",
            "message": f"Failed to store tokens: {str(e)}"
        }

async def get_user_salesforce_tokens(
    db_pool: asyncpg.Pool,
    user_id: str,
    username: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Retrieve Salesforce tokens for a user
    
    Args:
        db_pool: Database connection pool
        user_id: Salesforce user ID
        username: Optional username (if multiple accounts)
        
    Returns:
        Token dictionary or None if not found
    """
    try:
        async with db_pool.acquire() as conn:
            if username:
                result = await conn.fetchrow("""
                    SELECT * FROM salesforce_oauth_tokens 
                    WHERE user_id = $1 AND username = $2 AND is_active = true
                """, user_id, username)
            else:
                result = await conn.fetchrow("""
                    SELECT * FROM salesforce_oauth_tokens 
                    WHERE user_id = $1 AND is_active = true
                    ORDER BY updated_at DESC LIMIT 1
                """, user_id)
            
            if not result:
                return None
            
            # Check if token is expired
            if result["expires_at"] < datetime.now(timezone.utc):
                logger.warning(f"⚠️ Salesforce token expired for user: {user_id}")
                return None
            
            # Update last used timestamp
            await conn.execute("""
                UPDATE salesforce_oauth_tokens 
                SET last_used_at = NOW(), access_count = access_count + 1
                WHERE id = $1
            """, result["id"])
            
            # Return token information (without sensitive data in logs)
            logger.info(f"✅ Retrieved Salesforce tokens for user: {user_id}")
            
            return {
                "user_id": result["user_id"],
                "username": result["username"],
                "email": result["email"],
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"],
                "token_type": result["token_type"],
                "scope": result["scope"],
                "instance_url": result["instance_url"],
                "organization_id": result["organization_id"],
                "profile_id": result["profile_id"],
                "environment": result["environment"],
                "expires_at": result["expires_at"].isoformat(),
                "last_used_at": result["last_used_at"].isoformat(),
                "access_count": result["access_count"],
                "metadata": result["metadata"]
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to retrieve Salesforce tokens for {user_id}: {e}")
        return None

async def refresh_user_salesforce_tokens(
    db_pool: asyncpg.Pool,
    user_id: str,
    username: str,
    new_access_token: str,
    new_refresh_token: str,
    new_expires_at: datetime
) -> Dict[str, Any]:
    """
    Update Salesforce tokens after refresh
    
    Args:
        db_pool: Database connection pool
        user_id: Salesforce user ID
        username: Salesforce username
        new_access_token: New access token
        new_refresh_token: New refresh token
        new_expires_at: New expiration timestamp
        
    Returns:
        Result dictionary with success status
    """
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Update tokens
                await conn.execute("""
                    UPDATE salesforce_oauth_tokens 
                    SET 
                        access_token = $3,
                        refresh_token = $4,
                        expires_at = $5,
                        updated_at = NOW(),
                        is_active = true
                    WHERE user_id = $1 AND username = $2
                """, user_id, username, new_access_token, new_refresh_token, new_expires_at)
                
                # Log refresh in audit
                await conn.execute("""
                    INSERT INTO salesforce_oauth_audit_log 
                    (user_id, username, action, details)
                    VALUES ($1, $2, 'token_refreshed', $3)
                """, user_id, username, json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "new_expires_at": new_expires_at.isoformat()
                }))
                
                logger.info(f"✅ Successfully refreshed Salesforce tokens for user: {user_id}")
                
                return {
                    "success": True,
                    "action": "token_refreshed",
                    "user_id": user_id,
                    "username": username,
                    "new_expires_at": new_expires_at.isoformat(),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
    except Exception as e:
        logger.error(f"❌ Failed to refresh Salesforce tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": "token_refresh_failed",
            "message": f"Failed to refresh tokens: {str(e)}"
        }

async def revoke_user_salesforce_tokens(
    db_pool: asyncpg.Pool,
    user_id: str,
    username: Optional[str] = None,
    reason: str = "user_request"
) -> Dict[str, Any]:
    """
    Revoke Salesforce tokens for a user
    
    Args:
        db_pool: Database connection pool
        user_id: Salesforce user ID
        username: Optional username
        reason: Reason for revocation
        
    Returns:
        Result dictionary with success status
    """
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Deactivate tokens (don't delete for audit trail)
                if username:
                    await conn.execute("""
                        UPDATE salesforce_oauth_tokens 
                        SET is_active = false, updated_at = NOW()
                        WHERE user_id = $1 AND username = $2
                    """, user_id, username)
                else:
                    await conn.execute("""
                        UPDATE salesforce_oauth_tokens 
                        SET is_active = false, updated_at = NOW()
                        WHERE user_id = $1
                    """, user_id)
                
                # Log revocation in audit
                await conn.execute("""
                    INSERT INTO salesforce_oauth_audit_log 
                    (user_id, username, action, details)
                    VALUES ($1, $2, 'token_revoked', $3)
                """, user_id, username or "", json.dumps({
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
                
                logger.info(f"✅ Successfully revoked Salesforce tokens for user: {user_id}")
                
                return {
                    "success": True,
                    "action": "token_revoked",
                    "user_id": user_id,
                    "username": username,
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
    except Exception as e:
        logger.error(f"❌ Failed to revoke Salesforce tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": "token_revocation_failed",
            "message": f"Failed to revoke tokens: {str(e)}"
        }

async def list_user_salesforce_integrations(
    db_pool: asyncpg.Pool,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    active_only: bool = True
) -> List[Dict[str, Any]]:
    """
    List Salesforce integrations with filtering options
    
    Args:
        db_pool: Database connection pool
        user_id: Optional user ID filter
        organization_id: Optional organization ID filter
        active_only: Include only active integrations
        
    Returns:
        List of integration dictionaries
    """
    try:
        async with db_pool.acquire() as conn:
            # Build query dynamically
            conditions = []
            params = []
            param_count = 1
            
            if user_id:
                conditions.append(f"user_id = ${param_count}")
                params.append(user_id)
                param_count += 1
            
            if organization_id:
                conditions.append(f"organization_id = ${param_count}")
                params.append(organization_id)
                param_count += 1
            
            if active_only:
                conditions.append(f"is_active = ${param_count}")
                params.append(True)
                param_count += 1
            
            where_clause = ""
            if conditions:
                where_clause = f"WHERE {' AND '.join(conditions)}"
            
            query = f"""
                SELECT 
                    user_id, username, email, organization_id, profile_id,
                    environment, instance_url, created_at, updated_at,
                    last_used_at, is_active, access_count, metadata
                FROM salesforce_oauth_tokens 
                {where_clause}
                ORDER BY created_at DESC
            """
            
            results = await conn.fetch(query, *params)
            
            integrations = []
            for result in results:
                integrations.append({
                    "user_id": result["user_id"],
                    "username": result["username"],
                    "email": result["email"],
                    "organization_id": result["organization_id"],
                    "profile_id": result["profile_id"],
                    "environment": result["environment"],
                    "instance_url": result["instance_url"],
                    "created_at": result["created_at"].isoformat(),
                    "updated_at": result["updated_at"].isoformat(),
                    "last_used_at": result["last_used_at"].isoformat(),
                    "is_active": result["is_active"],
                    "access_count": result["access_count"],
                    "metadata": result["metadata"]
                })
            
            logger.info(f"✅ Listed {len(integrations)} Salesforce integrations")
            return integrations
            
    except Exception as e:
        logger.error(f"❌ Failed to list Salesforce integrations: {e}")
        return []

async def log_api_usage(
    db_pool: asyncpg.Pool,
    user_id: str,
    username: str,
    api_endpoint: str,
    data_transferred: int = 0,
    success: bool = True,
    error_message: str = ""
) -> None:
    """
    Log Salesforce API usage for analytics
    
    Args:
        db_pool: Database connection pool
        user_id: Salesforce user ID
        username: Salesforce username
        api_endpoint: API endpoint called
        data_transferred: Bytes transferred
        success: Whether the API call was successful
        error_message: Error message if failed
    """
    try:
        async with db_pool.acquire() as conn:
            # Update monthly usage statistics
            current_month = datetime.now().strftime("%Y-%m")
            
            await conn.execute("""
                INSERT INTO salesforce_token_usage 
                (user_id, username, date_YYYYMM, api_calls, data_transferred, errors)
                VALUES ($1, $2, $3, 1, $4, $5)
                ON CONFLICT (user_id, date_YYYYMM)
                DO UPDATE SET 
                    api_calls = salesforce_token_usage.api_calls + 1,
                    data_transferred = salesforce_token_usage.data_transferred + $4,
                    errors = salesforce_token_usage.errors + $5,
                    updated_at = NOW()
            """, user_id, username, current_month, 
                data_transferred if success else 0,
                0 if success else 1)
            
            # Log detailed API call in audit
            await conn.execute("""
                INSERT INTO salesforce_oauth_audit_log 
                (user_id, username, action, details, success, error_message)
                VALUES ($1, $2, 'api_call', $3, $4, $5)
            """, user_id, username, json.dumps({
                "endpoint": api_endpoint,
                "data_transferred": data_transferred,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), success, error_message)
            
    except Exception as e:
        logger.error(f"❌ Failed to log Salesforce API usage: {e}")

async def cleanup_expired_tokens(db_pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Clean up expired Salesforce tokens
    
    Args:
        db_pool: Database connection pool
        
    Returns:
        Cleanup result statistics
    """
    try:
        async with db_pool.acquire() as conn:
            # Deactivate expired tokens
            result = await conn.execute("""
                UPDATE salesforce_oauth_tokens 
                SET is_active = false, updated_at = NOW()
                WHERE expires_at < NOW() AND is_active = true
            """)
            
            # Count deactivated tokens
            deactivated_count = result.split()[-1] if result else 0
            
            logger.info(f"✅ Cleaned up {deactivated_count} expired Salesforce tokens")
            
            return {
                "success": True,
                "deactivated_count": int(deactivated_count),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to cleanup expired Salesforce tokens: {e}")
        return {
            "success": False,
            "error": "cleanup_failed",
            "message": f"Cleanup failed: {str(e)}"
        }

async def get_usage_statistics(
    db_pool: asyncpg.Pool,
    user_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get Salesforce API usage statistics
    
    Args:
        db_pool: Database connection pool
        user_id: Optional user ID filter
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        Usage statistics dictionary
    """
    try:
        async with db_pool.acquire() as conn:
            conditions = []
            params = []
            param_count = 1
            
            if user_id:
                conditions.append(f"user_id = ${param_count}")
                params.append(user_id)
                param_count += 1
            
            if start_date:
                conditions.append(f"date_YYYYMM >= ${param_count}")
                params.append(start_date.strftime("%Y-%m"))
                param_count += 1
            
            if end_date:
                conditions.append(f"date_YYYYMM <= ${param_count}")
                params.append(end_date.strftime("%Y-%m"))
                param_count += 1
            
            where_clause = ""
            if conditions:
                where_clause = f"WHERE {' AND '.join(conditions)}"
            
            # Get usage statistics
            result = await conn.fetchrow(f"""
                SELECT 
                    COUNT(*) as total_months,
                    SUM(api_calls) as total_calls,
                    SUM(data_transferred) as total_data,
                    SUM(errors) as total_errors,
                    AVG(api_calls) as avg_calls_per_month,
                    MAX(api_calls) as max_calls_month
                FROM salesforce_token_usage 
                {where_clause}
            """, *params)
            
            # Get monthly breakdown
            monthly_data = await conn.fetch(f"""
                SELECT 
                    date_YYYYMM,
                    api_calls,
                    data_transferred,
                    errors
                FROM salesforce_token_usage 
                {where_clause}
                ORDER BY date_YYYYMM DESC
            """, *params)
            
            monthly_breakdown = []
            for row in monthly_data:
                monthly_breakdown.append({
                    "month": row["date_YYYYMM"],
                    "api_calls": row["api_calls"],
                    "data_transferred": row["data_transferred"],
                    "errors": row["errors"]
                })
            
            return {
                "success": True,
                "total_months": result["total_months"] or 0,
                "total_calls": result["total_calls"] or 0,
                "total_data_transferred": result["total_data"] or 0,
                "total_errors": result["total_errors"] or 0,
                "average_calls_per_month": float(result["avg_calls_per_month"] or 0),
                "max_calls_month": result["max_calls_month"] or 0,
                "monthly_breakdown": monthly_breakdown,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to get Salesforce usage statistics: {e}")
        return {
            "success": False,
            "error": "statistics_failed",
            "message": f"Failed to get statistics: {str(e)}"
        }