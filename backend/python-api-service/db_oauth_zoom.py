#!/usr/bin/env python3
"""
🗃️ Zoom OAuth Database Handler
Secure token storage and meeting metadata management for Zoom integration
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List

import asyncpg
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class ZoomOAuthDatabase:
    """Enterprise-grade Zoom OAuth token and metadata management"""
    
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

async def init_zoom_oauth_table(db_pool: asyncpg.Pool) -> bool:
    """
    Initialize Zoom OAuth tokens table with enterprise-grade schema
    
    Args:
        db_pool: Database connection pool
        
    Returns:
        True if initialization successful
    """
    try:
        async with db_pool.acquire() as conn:
            # Create Zoom OAuth tokens table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_oauth_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    zoom_user_id VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    token_type VARCHAR(50) DEFAULT 'Bearer',
                    scope TEXT,
                    account_id VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    display_name VARCHAR(255),
                    user_type INTEGER,
                    role_name VARCHAR(255),
                    expires_at TIMESTAMP WITH TIME ZONE,
                    issued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_used_at TIMESTAMP WITH TIME ZONE,
                    is_active BOOLEAN DEFAULT true,
                    access_count INTEGER DEFAULT 0,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    UNIQUE(user_id)
                );
                
                -- Create indexes for performance
                CREATE INDEX IF NOT EXISTS idx_zoom_oauth_user_id 
                ON zoom_oauth_tokens(user_id);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_oauth_zoom_user_id 
                ON zoom_oauth_tokens(zoom_user_id);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_oauth_email 
                ON zoom_oauth_tokens(email);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_oauth_expires_at 
                ON zoom_oauth_tokens(expires_at);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_oauth_active 
                ON zoom_oauth_tokens(is_active);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_oauth_metadata 
                ON zoom_oauth_tokens USING GIN(metadata);
            """)
            
            # Create meeting metadata table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_meetings (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    zoom_meeting_id BIGINT NOT NULL,
                    uuid VARCHAR(255) UNIQUE,
                    topic VARCHAR(500) NOT NULL,
                    agenda TEXT,
                    start_time TIMESTAMP WITH TIME ZONE,
                    duration INTEGER,
                    timezone VARCHAR(100),
                    meeting_type INTEGER,
                    status VARCHAR(50) DEFAULT 'waiting',
                    password VARCHAR(50),
                    waiting_room BOOLEAN DEFAULT false,
                    join_before_host BOOLEAN DEFAULT false,
                    host_video BOOLEAN DEFAULT true,
                    participant_video BOOLEAN DEFAULT true,
                    cn_meeting BOOLEAN DEFAULT false,
                    in_meeting BOOLEAN DEFAULT false,
                    approval_type INTEGER,
                    audio VARCHAR(50) DEFAULT 'both',
                    auto_recording VARCHAR(20) DEFAULT 'none',
                    authentication_type VARCHAR(50),
                    break_out_room BOOLEAN DEFAULT false,
                    enable_large_meeting BOOLEAN DEFAULT false,
                    alternative_hosts TEXT,
                    registrants_confirmation_email BOOLEAN DEFAULT true,
                    calendar_type INTEGER DEFAULT 2,
                    recurrence_info JSONB DEFAULT '{}'::jsonb,
                    settings JSONB DEFAULT '{}'::jsonb,
                    participants JSONB DEFAULT '[]'::jsonb,
                    recording_files JSONB DEFAULT '[]'::jsonb,
                    transcript TEXT,
                    ai_summary JSONB DEFAULT '{}'::jsonb,
                    chat_messages JSONB DEFAULT '[]'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(user_id, zoom_meeting_id)
                );
                
                -- Create indexes for meeting table
                CREATE INDEX IF NOT EXISTS idx_zoom_meetings_user_id 
                ON zoom_meetings(user_id);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_meetings_zoom_meeting_id 
                ON zoom_meetings(zoom_meeting_id);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_meetings_uuid 
                ON zoom_meetings(uuid);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_meetings_start_time 
                ON zoom_meetings(start_time);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_meetings_status 
                ON zoom_meetings(status);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_meetings_topic 
                ON zoom_meetings USING GIN(to_tsvector('english', topic));
            """)
            
            # Create meeting analytics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_meeting_analytics (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    meeting_id BIGINT NOT NULL,
                    participant_count INTEGER,
                    average_attendance_time INTEGER,
                    peak_participants INTEGER,
                    engagement_score DECIMAL(3,2),
                    network_quality_score DECIMAL(3,2),
                    audio_quality_score DECIMAL(3,2),
                    video_quality_score DECIMAL(3,2),
                    sentiment_score DECIMAL(3,2),
                    total_messages INTEGER,
                    total_reactions INTEGER,
                    screen_shares INTEGER,
                    breakout_rooms_used INTEGER,
                    recording_duration INTEGER,
                    transcript_accuracy DECIMAL(3,2),
                    analytics_date DATE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(meeting_id, analytics_date)
                );
                
                -- Create indexes for analytics table
                CREATE INDEX IF NOT EXISTS idx_zoom_analytics_user_id 
                ON zoom_meeting_analytics(user_id);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_analytics_meeting_id 
                ON zoom_meeting_analytics(meeting_id);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_analytics_date 
                ON zoom_meeting_analytics(analytics_date);
            """)
            
            # Create audit log table for OAuth operations
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_oauth_audit_log (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    zoom_user_id VARCHAR(255),
                    action VARCHAR(100) NOT NULL,
                    details JSONB DEFAULT '{}'::jsonb,
                    ip_address INET,
                    user_agent TEXT,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    success BOOLEAN DEFAULT true,
                    error_message TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_zoom_audit_user_id 
                ON zoom_oauth_audit_log(user_id);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_audit_action 
                ON zoom_oauth_audit_log(action);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_audit_timestamp 
                ON zoom_oauth_audit_log(timestamp);
            """)
            
            # Create usage statistics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_token_usage (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    date_YYYYMM VARCHAR(7) NOT NULL, -- YYYY-MM format
                    api_calls INTEGER DEFAULT 0,
                    meetings_created INTEGER DEFAULT 0,
                    meetings_hosted INTEGER DEFAULT 0,
                    recordings_downloaded INTEGER DEFAULT 0,
                    transcripts_generated INTEGER DEFAULT 0,
                    data_transferred BIGINT DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(user_id, date_YYYYMM)
                );
                
                CREATE INDEX IF NOT EXISTS idx_zoom_usage_user_date 
                ON zoom_token_usage(user_id, date_YYYYMM);
            """)
            
            # Create webhook events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_webhook_events (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    event_id VARCHAR(255) UNIQUE,
                    event_type VARCHAR(100) NOT NULL,
                    event_timestamp TIMESTAMP WITH TIME ZONE,
                    payload JSONB DEFAULT '{}'::jsonb,
                    processed BOOLEAN DEFAULT false,
                    processing_attempts INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    processed_at TIMESTAMP WITH TIME ZONE
                );
                
                CREATE INDEX IF NOT EXISTS idx_zoom_webhook_event_type 
                ON zoom_webhook_events(event_type);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_webhook_processed 
                ON zoom_webhook_events(processed);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_webhook_created_at 
                ON zoom_webhook_events(created_at);
                
                CREATE INDEX IF NOT EXISTS idx_zoom_webhook_payload 
                ON zoom_webhook_events USING GIN(payload);
            """)
            
            logger.info("✅ Zoom OAuth tables initialized successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize Zoom OAuth tables: {e}")
        return False

async def store_zoom_tokens(
    db_pool: asyncpg.Pool,
    user_id: str,
    zoom_user_id: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    scope: str = "",
    email: str = "",
    first_name: str = "",
    last_name: str = "",
    display_name: str = "",
    user_type: int = 1,
    role_name: str = "",
    account_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: str = "",
    user_agent: str = ""
) -> Dict[str, Any]:
    """
    Store Zoom OAuth tokens with security and audit logging
    
    Args:
        db_pool: Database connection pool
        user_id: Internal user identifier
        zoom_user_id: Zoom user ID
        access_token: OAuth access token
        refresh_token: OAuth refresh token
        expires_at: Token expiration timestamp
        scope: Granted OAuth scopes
        email: User email
        first_name: User first name
        last_name: User last name
        display_name: User display name
        user_type: Zoom user type
        role_name: Zoom role name
        account_id: Zoom account ID
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
                    SELECT id, access_count FROM zoom_oauth_tokens 
                    WHERE user_id = $1
                """, user_id)
                
                # Prepare metadata
                if metadata is None:
                    metadata = {}
                metadata_json = json.dumps(metadata)
                
                if existing:
                    # Update existing tokens
                    await conn.execute("""
                        UPDATE zoom_oauth_tokens 
                        SET 
                            zoom_user_id = $2,
                            email = $3,
                            access_token = $4,
                            refresh_token = $5,
                            scope = $6,
                            account_id = $7,
                            first_name = $8,
                            last_name = $9,
                            display_name = $10,
                            user_type = $11,
                            role_name = $12,
                            expires_at = $13,
                            updated_at = NOW(),
                            last_used_at = NOW(),
                            is_active = true,
                            access_count = access_count + 1,
                            metadata = $14
                        WHERE user_id = $1
                    """, user_id, zoom_user_id, email, access_token, refresh_token, scope,
                        account_id, first_name, last_name, display_name, user_type,
                        role_name, expires_at, metadata_json)
                    
                    action = "token_updated"
                else:
                    # Insert new tokens
                    await conn.execute("""
                        INSERT INTO zoom_oauth_tokens 
                        (user_id, zoom_user_id, email, access_token, refresh_token, 
                         scope, account_id, first_name, last_name, display_name,
                         user_type, role_name, expires_at, last_used_at, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
                                $11, $12, $13, NOW(), $14)
                    """, user_id, zoom_user_id, email, access_token, refresh_token,
                        scope, account_id, first_name, last_name, display_name,
                        user_type, role_name, expires_at, metadata_json)
                    
                    action = "token_created"
                
                # Log audit trail
                await conn.execute("""
                    INSERT INTO zoom_oauth_audit_log 
                    (user_id, zoom_user_id, action, details, ip_address, user_agent)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, user_id, zoom_user_id, action, metadata_json, ip_address, user_agent)
                
                logger.info(f"✅ Successfully stored Zoom tokens for user: {user_id}")
                
                return {
                    "success": True,
                    "action": action,
                    "user_id": user_id,
                    "zoom_user_id": zoom_user_id,
                    "email": email,
                    "expires_at": expires_at.isoformat(),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
    except Exception as e:
        logger.error(f"❌ Failed to store Zoom tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": "token_storage_failed",
            "message": f"Failed to store tokens: {str(e)}"
        }

async def get_user_zoom_tokens(
    db_pool: asyncpg.Pool,
    user_id: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieve Zoom tokens for a user
    
    Args:
        db_pool: Database connection pool
        user_id: Internal user ID
        
    Returns:
        Token dictionary or None if not found
    """
    try:
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT * FROM zoom_oauth_tokens 
                WHERE user_id = $1 AND is_active = true
            """, user_id)
            
            if not result:
                return None
            
            # Check if token is expired
            if result["expires_at"] < datetime.now(timezone.utc):
                logger.warning(f"⚠️ Zoom token expired for user: {user_id}")
                return None
            
            # Update last used timestamp
            await conn.execute("""
                UPDATE zoom_oauth_tokens 
                SET last_used_at = NOW(), access_count = access_count + 1
                WHERE id = $1
            """, result["id"])
            
            # Return token information (without sensitive data in logs)
            logger.info(f"✅ Retrieved Zoom tokens for user: {user_id}")
            
            return {
                "user_id": result["user_id"],
                "zoom_user_id": result["zoom_user_id"],
                "email": result["email"],
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"],
                "token_type": result["token_type"],
                "scope": result["scope"],
                "account_id": result["account_id"],
                "first_name": result["first_name"],
                "last_name": result["last_name"],
                "display_name": result["display_name"],
                "user_type": result["user_type"],
                "role_name": result["role_name"],
                "expires_at": result["expires_at"].isoformat(),
                "last_used_at": result["last_used_at"].isoformat(),
                "access_count": result["access_count"],
                "metadata": result["metadata"]
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to retrieve Zoom tokens for {user_id}: {e}")
        return None

async def refresh_user_zoom_tokens(
    db_pool: asyncpg.Pool,
    user_id: str,
    new_access_token: str,
    new_refresh_token: str,
    new_expires_at: datetime
) -> Dict[str, Any]:
    """
    Update Zoom tokens after refresh
    
    Args:
        db_pool: Database connection pool
        user_id: Internal user ID
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
                    UPDATE zoom_oauth_tokens 
                    SET 
                        access_token = $2,
                        refresh_token = $3,
                        expires_at = $4,
                        updated_at = NOW(),
                        is_active = true
                    WHERE user_id = $1
                """, user_id, new_access_token, new_refresh_token, new_expires_at)
                
                # Log refresh in audit
                await conn.execute("""
                    INSERT INTO zoom_oauth_audit_log 
                    (user_id, action, details)
                    VALUES ($1, 'token_refreshed', $2)
                """, user_id, json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "new_expires_at": new_expires_at.isoformat()
                }))
                
                logger.info(f"✅ Successfully refreshed Zoom tokens for user: {user_id}")
                
                return {
                    "success": True,
                    "action": "token_refreshed",
                    "user_id": user_id,
                    "new_expires_at": new_expires_at.isoformat(),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
    except Exception as e:
        logger.error(f"❌ Failed to refresh Zoom tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": "token_refresh_failed",
            "message": f"Failed to refresh tokens: {str(e)}"
        }

async def revoke_user_zoom_tokens(
    db_pool: asyncpg.Pool,
    user_id: str,
    reason: str = "user_request"
) -> Dict[str, Any]:
    """
    Revoke Zoom tokens for a user
    
    Args:
        db_pool: Database connection pool
        user_id: Internal user ID
        reason: Reason for revocation
        
    Returns:
        Result dictionary with success status
    """
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Deactivate tokens (don't delete for audit trail)
                await conn.execute("""
                    UPDATE zoom_oauth_tokens 
                    SET is_active = false, updated_at = NOW()
                    WHERE user_id = $1
                """, user_id)
                
                # Log revocation in audit
                await conn.execute("""
                    INSERT INTO zoom_oauth_audit_log 
                    (user_id, action, details)
                    VALUES ($1, 'token_revoked', $2)
                """, user_id, json.dumps({
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
                
                logger.info(f"✅ Successfully revoked Zoom tokens for user: {user_id}")
                
                return {
                    "success": True,
                    "action": "token_revoked",
                    "user_id": user_id,
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
    except Exception as e:
        logger.error(f"❌ Failed to revoke Zoom tokens for {user_id}: {e}")
        return {
            "success": False,
            "error": "token_revocation_failed",
            "message": f"Failed to revoke tokens: {str(e)}"
        }

async def store_meeting_metadata(
    db_pool: asyncpg.Pool,
    user_id: str,
    meeting_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Store meeting metadata
    
    Args:
        db_pool: Database connection pool
        user_id: Internal user ID
        meeting_data: Meeting metadata from Zoom API
        
    Returns:
        Result dictionary with success status
    """
    try:
        async with db_pool.acquire() as conn:
            # Extract meeting data
            meeting_id = meeting_data.get("id")
            uuid = meeting_data.get("uuid")
            topic = meeting_data.get("topic", "")
            agenda = meeting_data.get("agenda")
            start_time = meeting_data.get("start_time")
            duration = meeting_data.get("duration")
            timezone_str = meeting_data.get("timezone")
            meeting_type = meeting_data.get("type", 1)
            password = meeting_data.get("password")
            
            # Handle start_time parsing
            if start_time:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            else:
                start_dt = None
            
            # Extract settings
            settings = meeting_data.get("settings", {})
            
            # Insert or update meeting
            await conn.execute("""
                INSERT INTO zoom_meetings 
                (user_id, zoom_meeting_id, uuid, topic, agenda, start_time,
                 duration, timezone, meeting_type, password, status, settings)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (user_id, zoom_meeting_id) 
                DO UPDATE SET 
                    topic = EXCLUDED.topic,
                    agenda = EXCLUDED.agenda,
                    start_time = EXCLUDED.start_time,
                    duration = EXCLUDED.duration,
                    timezone = EXCLUDED.timezone,
                    meeting_type = EXCLUDED.meeting_type,
                    password = EXCLUDED.password,
                    settings = EXCLUDED.settings,
                    updated_at = NOW()
            """, user_id, meeting_id, uuid, topic, agenda, start_dt,
                duration, timezone_str, meeting_type, password, "scheduled", 
                json.dumps(settings))
            
            logger.info(f"✅ Stored Zoom meeting metadata: {meeting_id}")
            
            return {
                "success": True,
                "meeting_id": meeting_id,
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to store Zoom meeting metadata: {e}")
        return {
            "success": False,
            "error": "meeting_storage_failed",
            "message": f"Failed to store meeting metadata: {str(e)}"
        }

async def log_api_usage(
    db_pool: asyncpg.Pool,
    user_id: str,
    api_endpoint: str,
    data_transferred: int = 0,
    success: bool = True,
    error_message: str = "",
    additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log Zoom API usage for analytics
    
    Args:
        db_pool: Database connection pool
        user_id: Internal user ID
        api_endpoint: API endpoint called
        data_transferred: Bytes transferred
        success: Whether the API call was successful
        error_message: Error message if failed
        additional_data: Additional usage data
    """
    try:
        async with db_pool.acquire() as conn:
            # Update monthly usage statistics
            current_month = datetime.now().strftime("%Y-%m")
            
            # Determine which counter to update
            if "meetings" in api_endpoint:
                if "create" in api_endpoint:
                    counter_field = "meetings_created"
                else:
                    counter_field = "meetings_hosted"
            elif "recordings" in api_endpoint:
                counter_field = "recordings_downloaded"
            elif "transcripts" in api_endpoint:
                counter_field = "transcripts_generated"
            else:
                counter_field = "api_calls"
            
            await conn.execute(f"""
                INSERT INTO zoom_token_usage 
                (user_id, date_YYYYMM, {counter_field}, data_transferred, errors)
                VALUES ($1, $2, 1, $3, $4)
                ON CONFLICT (user_id, date_YYYYMM)
                DO UPDATE SET 
                    {counter_field} = zoom_token_usage.{counter_field} + 1,
                    data_transferred = zoom_token_usage.data_transferred + $3,
                    errors = zoom_token_usage.errors + $4,
                    updated_at = NOW()
            """, user_id, current_month, 
                data_transferred if success else 0,
                0 if success else 1)
            
            # Log detailed API call in audit
            details = {
                "endpoint": api_endpoint,
                "data_transferred": data_transferred,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if additional_data:
                details.update(additional_data)
            
            await conn.execute("""
                INSERT INTO zoom_oauth_audit_log 
                (user_id, action, details, success, error_message)
                VALUES ($1, 'api_call', $2, $3, $4)
            """, user_id, json.dumps(details), success, error_message)
            
    except Exception as e:
        logger.error(f"❌ Failed to log Zoom API usage: {e}")

async def cleanup_expired_tokens(db_pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Clean up expired Zoom tokens
    
    Args:
        db_pool: Database connection pool
        
    Returns:
        Cleanup result statistics
    """
    try:
        async with db_pool.acquire() as conn:
            # Deactivate expired tokens
            result = await conn.execute("""
                UPDATE zoom_oauth_tokens 
                SET is_active = false, updated_at = NOW()
                WHERE expires_at < NOW() AND is_active = true
            """)
            
            # Count deactivated tokens
            deactivated_count = result.split()[-1] if result else 0
            
            logger.info(f"✅ Cleaned up {deactivated_count} expired Zoom tokens")
            
            return {
                "success": True,
                "deactivated_count": int(deactivated_count),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to cleanup expired Zoom tokens: {e}")
        return {
            "success": False,
            "error": "cleanup_failed",
            "message": f"Cleanup failed: {str(e)}"
        }

async def get_user_meetings(
    db_pool: asyncpg.Pool,
    user_id: str,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get user's Zoom meetings
    
    Args:
        db_pool: Database connection pool
        user_id: Internal user ID
        status: Filter by meeting status
        start_date: Filter by start date
        end_date: Filter by end date
        limit: Maximum records to return
        
    Returns:
        List of meeting dictionaries
    """
    try:
        async with db_pool.acquire() as conn:
            # Build query dynamically
            conditions = ["user_id = $1"]
            params = [user_id]
            param_count = 2
            
            if status:
                conditions.append(f"status = ${param_count}")
                params.append(status)
                param_count += 1
            
            if start_date:
                conditions.append(f"start_time >= ${param_count}")
                params.append(start_date)
                param_count += 1
            
            if end_date:
                conditions.append(f"start_time <= ${param_count}")
                params.append(end_date)
                param_count += 1
            
            where_clause = " AND ".join(conditions)
            
            query = f"""
                SELECT * FROM zoom_meetings 
                WHERE {where_clause}
                ORDER BY start_time DESC 
                LIMIT ${param_count}
            """
            params.append(limit)
            
            results = await conn.fetch(query, *params)
            
            meetings = []
            for result in results:
                meetings.append({
                    "id": result["id"],
                    "zoom_meeting_id": result["zoom_meeting_id"],
                    "uuid": result["uuid"],
                    "topic": result["topic"],
                    "agenda": result["agenda"],
                    "start_time": result["start_time"].isoformat() if result["start_time"] else None,
                    "duration": result["duration"],
                    "timezone": result["timezone"],
                    "meeting_type": result["meeting_type"],
                    "status": result["status"],
                    "settings": result["settings"],
                    "participants": result["participants"],
                    "recording_files": result["recording_files"],
                    "transcript": result["transcript"],
                    "ai_summary": result["ai_summary"],
                    "created_at": result["created_at"].isoformat(),
                    "updated_at": result["updated_at"].isoformat()
                })
            
            return meetings
            
    except Exception as e:
        logger.error(f"❌ Failed to get user Zoom meetings: {e}")
        return []

async def update_meeting_status(
    db_pool: asyncpg.Pool,
    meeting_id: int,
    status: str,
    additional_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update meeting status
    
    Args:
        db_pool: Database connection pool
        meeting_id: Internal meeting ID
        status: New meeting status
        additional_data: Additional data to update
        
    Returns:
        Result dictionary with success status
    """
    try:
        async with db_pool.acquire() as conn:
            # Build update query
            update_fields = ["status = $2"]
            params = [meeting_id, status]
            param_count = 3
            
            if additional_data:
                for key, value in additional_data.items():
                    if key in ["participants", "recording_files", "transcript", "ai_summary"]:
                        update_fields.append(f"{key} = ${param_count}")
                        params.append(json.dumps(value) if isinstance(value, (dict, list)) else value)
                        param_count += 1
            
            update_fields.append("updated_at = NOW()")
            
            query = f"""
                UPDATE zoom_meetings 
                SET {', '.join(update_fields)}
                WHERE id = $1
            """
            
            await conn.execute(query, *params)
            
            logger.info(f"✅ Updated Zoom meeting {meeting_id} status to: {status}")
            
            return {
                "success": True,
                "meeting_id": meeting_id,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to update Zoom meeting status: {e}")
        return {
            "success": False,
            "error": "status_update_failed",
            "message": f"Failed to update meeting status: {str(e)}"
        }

async def store_webhook_event(
    db_pool: asyncpg.Pool,
    event_id: str,
    event_type: str,
    event_timestamp: datetime,
    payload: Dict[str, Any],
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Store Zoom webhook event
    
    Args:
        db_pool: Database connection pool
        event_id: Unique event identifier
        event_type: Type of Zoom event
        event_timestamp: When the event occurred
        payload: Event payload data
        user_id: Associated user ID (if determinable)
        
    Returns:
        Result dictionary with success status
    """
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO zoom_webhook_events 
                (user_id, event_id, event_type, event_timestamp, payload)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (event_id) DO NOTHING
            """, user_id, event_id, event_type, event_timestamp, json.dumps(payload))
            
            logger.info(f"✅ Stored Zoom webhook event: {event_type} - {event_id}")
            
            return {
                "success": True,
                "event_id": event_id,
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to store Zoom webhook event: {e}")
        return {
            "success": False,
            "error": "webhook_storage_failed",
            "message": f"Failed to store webhook event: {str(e)}"
        }