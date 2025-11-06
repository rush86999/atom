"""
🔐 Zoom Speech-to-Text BYOK (Bring Your Own Key) System
Enterprise-grade key management system for speech-to-text services
"""

import os
import json
import logging
import asyncio
import hashlib
import hmac
import base64
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

import asyncpg
import httpx
from pydantic import BaseModel, validator, Field

logger = logging.getLogger(__name__)

class ProviderType(Enum):
    """Supported speech-to-text providers"""
    OPENAI = "openai"
    GOOGLE = "google"
    AZURE = "azure"
    AWS = "aws"
    DEEPGRAM = "deepgram"
    ASSEMBLYAI = "assemblyai"
    WHISPER_API = "whisper_api"
    REV_AI = "rev_ai"
    SPEECHMATICS = "speechmatics"

class KeyStatus(Enum):
    """BYOK key status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"

class KeyRotationStatus(Enum):
    """Key rotation status"""
    NONE = "none"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ProviderKey:
    """Provider key configuration"""
    key_id: str
    provider: ProviderType
    key_name: str
    encrypted_key: str
    key_hash: str
    key_algorithm: str
    account_id: str
    account_name: str
    billing_id: Optional[str]
    key_permissions: List[str]
    key_usage_count: int = 0
    key_last_used: Optional[datetime] = None
    key_expires_at: Optional[datetime] = None
    key_status: KeyStatus = KeyStatus.PENDING
    rotation_status: KeyRotationStatus = KeyRotationStatus.NONE
    rotation_scheduled_at: Optional[datetime] = None
    rotation_frequency_days: int = 90
    usage_quota: Optional[int] = None
    usage_quota_period: str = "monthly"
    cost_per_request: float = 0.0
    rate_limit_per_minute: int = 1000
    metadata: Dict[str, Any] = None
    created_at: datetime = None
    updated_at: datetime = None

@dataclass
class KeyUsageLog:
    """Key usage log entry"""
    log_id: str
    key_id: str
    provider: ProviderType
    usage_type: str  # transcription, analysis, etc.
    audio_duration: float
    cost_incurred: float
    request_id: str
    meeting_id: Optional[str]
    participant_id: Optional[str]
    response_time_ms: float
    success: bool
    error_message: Optional[str]
    user_id: str
    ip_address: str
    user_agent: str
    timestamp: datetime
    metadata: Dict[str, Any] = None

@dataclass
class KeyRotation:
    """Key rotation configuration"""
    rotation_id: str
    key_id: str
    old_key_id: Optional[str]
    new_key_id: Optional[str]
    rotation_type: str  # manual, scheduled, emergency
    rotation_status: KeyRotationStatus
    rotation_started_at: Optional[datetime]
    rotation_completed_at: Optional[datetime]
    fallback_enabled: bool
    grace_period_days: int
    rollback_enabled: bool
    rollback_deadline: Optional[datetime]
    created_by: str
    approved_by: Optional[str]
    rotation_reason: str
    metadata: Dict[str, Any] = None
    created_at: datetime = None
    updated_at: datetime = None

class BYOKKeyRequest(BaseModel):
    """BYOK key request model"""
    provider: str = Field(..., description="Provider name")
    key_name: str = Field(..., description="Display name for the key")
    api_key: str = Field(..., description="API key (will be encrypted)")
    account_id: str = Field(..., description="Provider account ID")
    account_name: str = Field(..., description="Provider account name")
    billing_id: Optional[str] = Field(None, description="Billing account ID")
    key_permissions: List[str] = Field(default_factory=list, description="Key permissions")
    key_expires_at: Optional[datetime] = Field(None, description="Key expiration date")
    rotation_frequency_days: int = Field(default=90, description="Rotation frequency in days")
    usage_quota: Optional[int] = Field(None, description="Usage quota")
    usage_quota_period: str = Field(default="monthly", description="Quota period")
    rate_limit_per_minute: int = Field(default=1000, description="Rate limit per minute")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('provider')
    def validate_provider(cls, v):
        try:
            return ProviderType(v).value
        except ValueError:
            raise ValueError(f"Invalid provider: {v}")

class ZoomSpeechBYOKManager:
    """Zoom Speech-to-Text BYOK Manager"""
    
    def __init__(self, db_pool: asyncpg.Pool, encryption_key: str = None):
        self.db_pool = db_pool
        self.encryption_key = encryption_key or self._generate_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key.encode())
        
        # Key storage
        self.provider_keys: Dict[str, ProviderKey] = {}
        self.key_rotation_config: Dict[str, Any] = {
            'auto_rotation_enabled': True,
            'rotation_check_interval_hours': 24,
            'default_rotation_frequency_days': 90,
            'grace_period_days': 7,
            'fallback_enabled': True,
            'rollback_enabled': True
        }
        
        # Usage tracking
        self.usage_logs: Dict[str, List[KeyUsageLog]] = defaultdict(list)
        self.quota_trackers: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # HTTP clients for each provider
        self.http_clients: Dict[ProviderType, httpx.AsyncClient] = {}
        
        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        # Performance metrics
        self.metrics = {
            'keys_managed': 0,
            'encryption_operations': 0,
            'decryption_operations': 0,
            'key_rotations': 0,
            'usage_logs': 0,
            'quota_violations': 0,
            'security_incidents': 0,
            'average_response_time': 0.0,
            'cost_tracking_enabled': False
        }
        
        # Initialize database
        asyncio.create_task(self._init_database())
    
    async def _init_database(self) -> None:
        """Initialize BYOK database tables"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Create provider keys table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_byok_provider_keys (
                        key_id VARCHAR(255) PRIMARY KEY,
                        provider VARCHAR(50) NOT NULL,
                        key_name VARCHAR(255) NOT NULL,
                        encrypted_key TEXT NOT NULL,
                        key_hash VARCHAR(255) NOT NULL,
                        key_algorithm VARCHAR(50) DEFAULT 'AES-256-GCM',
                        account_id VARCHAR(255) NOT NULL,
                        account_name VARCHAR(255) NOT NULL,
                        billing_id VARCHAR(255),
                        key_permissions JSONB DEFAULT '[]'::jsonb,
                        key_usage_count INTEGER DEFAULT 0,
                        key_last_used TIMESTAMP WITH TIME ZONE,
                        key_expires_at TIMESTAMP WITH TIME ZONE,
                        key_status VARCHAR(20) DEFAULT 'pending',
                        rotation_status VARCHAR(20) DEFAULT 'none',
                        rotation_scheduled_at TIMESTAMP WITH TIME ZONE,
                        rotation_frequency_days INTEGER DEFAULT 90,
                        usage_quota INTEGER,
                        usage_quota_period VARCHAR(20) DEFAULT 'monthly',
                        cost_per_request NUMERIC(10,6) DEFAULT 0,
                        rate_limit_per_minute INTEGER DEFAULT 1000,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create key usage logs table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_byok_usage_logs (
                        log_id VARCHAR(255) PRIMARY KEY,
                        key_id VARCHAR(255) NOT NULL,
                        provider VARCHAR(50) NOT NULL,
                        usage_type VARCHAR(50) NOT NULL,
                        audio_duration NUMERIC(8,2) NOT NULL,
                        cost_incurred NUMERIC(10,6) DEFAULT 0,
                        request_id VARCHAR(255) NOT NULL,
                        meeting_id VARCHAR(255),
                        participant_id VARCHAR(255),
                        response_time_ms INTEGER NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        user_id VARCHAR(255) NOT NULL,
                        ip_address VARCHAR(45) NOT NULL,
                        user_agent TEXT,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        metadata JSONB DEFAULT '{}'::jsonb
                    );
                """)
                
                # Create key rotations table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_byok_key_rotations (
                        rotation_id VARCHAR(255) PRIMARY KEY,
                        key_id VARCHAR(255) NOT NULL,
                        old_key_id VARCHAR(255),
                        new_key_id VARCHAR(255),
                        rotation_type VARCHAR(20) NOT NULL,
                        rotation_status VARCHAR(20) NOT NULL,
                        rotation_started_at TIMESTAMP WITH TIME ZONE,
                        rotation_completed_at TIMESTAMP WITH TIME ZONE,
                        fallback_enabled BOOLEAN DEFAULT TRUE,
                        grace_period_days INTEGER DEFAULT 7,
                        rollback_enabled BOOLEAN DEFAULT TRUE,
                        rollback_deadline TIMESTAMP WITH TIME ZONE,
                        created_by VARCHAR(255) NOT NULL,
                        approved_by VARCHAR(255),
                        rotation_reason TEXT NOT NULL,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create security audit table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_byok_security_audit (
                        audit_id VARCHAR(255) PRIMARY KEY,
                        key_id VARCHAR(255) NOT NULL,
                        event_type VARCHAR(50) NOT NULL,
                        event_description TEXT NOT NULL,
                        user_id VARCHAR(255) NOT NULL,
                        ip_address VARCHAR(45) NOT NULL,
                        user_agent TEXT,
                        success BOOLEAN NOT NULL,
                        risk_level VARCHAR(20) DEFAULT 'low',
                        additional_data JSONB DEFAULT '{}'::jsonb,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create cost tracking table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_byok_cost_tracking (
                        cost_id VARCHAR(255) PRIMARY KEY,
                        key_id VARCHAR(255) NOT NULL,
                        provider VARCHAR(50) NOT NULL,
                        cost_period VARCHAR(20) NOT NULL,
                        period_start TIMESTAMP WITH TIME ZONE NOT NULL,
                        period_end TIMESTAMP WITH TIME ZONE NOT NULL,
                        total_requests INTEGER DEFAULT 0,
                        total_duration_seconds NUMERIC(12,2) DEFAULT 0,
                        total_cost NUMERIC(12,6) DEFAULT 0,
                        cost_per_minute NUMERIC(10,6) DEFAULT 0,
                        forecast_cost NUMERIC(12,6) DEFAULT 0,
                        budget_alert_threshold NUMERIC(12,6),
                        budget_exceeded BOOLEAN DEFAULT FALSE,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create indexes
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_provider_keys_provider ON zoom_byok_provider_keys(provider);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_provider_keys_account ON zoom_byok_provider_keys(account_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_provider_keys_status ON zoom_byok_provider_keys(key_status);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_provider_keys_rotation ON zoom_byok_provider_keys(rotation_status);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_provider_keys_expires ON zoom_byok_provider_keys(key_expires_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_usage_logs_key ON zoom_byok_usage_logs(key_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_usage_logs_provider ON zoom_byok_usage_logs(provider);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_usage_logs_timestamp ON zoom_byok_usage_logs(timestamp);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_usage_logs_request ON zoom_byok_usage_logs(request_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_usage_logs_meeting ON zoom_byok_usage_logs(meeting_id);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_key_rotations_key ON zoom_byok_key_rotations(key_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_key_rotations_status ON zoom_byok_key_rotations(rotation_status);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_key_rotations_timestamp ON zoom_byok_key_rotations(created_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_security_audit_key ON zoom_byok_security_audit(key_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_security_audit_event ON zoom_byok_security_audit(event_type);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_security_audit_timestamp ON zoom_byok_security_audit(timestamp);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_security_audit_risk ON zoom_byok_security_audit(risk_level);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_cost_tracking_key ON zoom_byok_cost_tracking(key_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_cost_tracking_provider ON zoom_byok_cost_tracking(provider);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_cost_tracking_period ON zoom_byok_cost_tracking(cost_period);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_byok_cost_tracking_start ON zoom_byok_cost_tracking(period_start);"
                ]
                
                for index_sql in indexes:
                    await conn.execute(index_sql)
                
                logger.info("BYOK database tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize BYOK database: {e}")
    
    async def start_processing(self) -> None:
        """Start BYOK processing"""
        try:
            self.is_running = True
            
            # Load existing keys from database
            await self._load_existing_keys()
            
            # Start background tasks
            self.background_tasks = [
                asyncio.create_task(self._key_rotation_scheduler()),
                asyncio.create_task(self._quota_monitor()),
                asyncio.create_task(self._cost_tracker()),
                asyncio.create_task(self._security_monitor()),
                asyncio.create_task(self._cleanup_expired_keys()),
                asyncio.create_task(self._metrics_collector())
            ]
            
            logger.info("BYOK processing started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start BYOK processing: {e}")
            raise
    
    async def stop_processing(self) -> None:
        """Stop BYOK processing"""
        try:
            self.is_running = False
            
            # Cancel background tasks
            for task in self.background_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Close HTTP clients
            for client in self.http_clients.values():
                await client.aclose()
            
            logger.info("BYOK processing stopped successfully")
            
        except Exception as e:
            logger.error(f"Failed to stop BYOK processing: {e}")
    
    async def add_provider_key(self, key_request: BYOKKeyRequest, 
                             user_id: str, ip_address: str, user_agent: str) -> Optional[ProviderKey]:
        """Add a new provider key"""
        try:
            # Validate key with provider
            is_valid = await self._validate_provider_key(key_request)
            if not is_valid:
                await self._log_security_event(
                    None, 'key_validation_failed', 
                    f"Invalid key for provider {key_request.provider}",
                    user_id, ip_address, user_agent, False, 'high'
                )
                return None
            
            # Generate key ID and encrypt key
            key_id = f"key_{key_request.provider}_{secrets.token_urlsafe(16)}"
            encrypted_key = self._encrypt_api_key(key_request.api_key)
            key_hash = self._hash_api_key(key_request.api_key)
            
            # Create provider key object
            provider_key = ProviderKey(
                key_id=key_id,
                provider=ProviderType(key_request.provider),
                key_name=key_request.key_name,
                encrypted_key=encrypted_key,
                key_hash=key_hash,
                key_algorithm='AES-256-GCM',
                account_id=key_request.account_id,
                account_name=key_request.account_name,
                billing_id=key_request.billing_id,
                key_permissions=key_request.key_permissions,
                key_expires_at=key_request.key_expires_at,
                rotation_frequency_days=key_request.rotation_frequency_days,
                usage_quota=key_request.usage_quota,
                usage_quota_period=key_request.usage_quota_period,
                rate_limit_per_minute=key_request.rate_limit_per_minute,
                metadata=key_request.metadata,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            # Store in database
            await self._store_provider_key(provider_key)
            
            # Store in memory
            self.provider_keys[key_id] = provider_key
            
            # Initialize usage tracker
            self.quota_trackers[key_id] = {
                'current_usage': 0,
                'quota': key_request.usage_quota,
                'period': key_request.usage_quota_period,
                'period_start': datetime.now(timezone.utc),
                'rate_limiter': asyncio.Semaphore(key_request.rate_limit_per_minute)
            }
            
            # Log security event
            await self._log_security_event(
                key_id, 'key_added', 
                f"New key added for {key_request.provider}",
                user_id, ip_address, user_agent, True, 'low'
            )
            
            # Update metrics
            self.metrics['keys_managed'] += 1
            self.metrics['encryption_operations'] += 1
            
            logger.info(f"Added new provider key: {key_id} for {key_request.provider}")
            return provider_key
            
        except Exception as e:
            logger.error(f"Failed to add provider key: {e}")
            return None
    
    async def get_active_key(self, provider: ProviderType, 
                           account_id: str = None) -> Optional[ProviderKey]:
        """Get active key for provider"""
        try:
            # Filter keys by provider and status
            candidate_keys = [
                key for key in self.provider_keys.values()
                if key.provider == provider and key.key_status == KeyStatus.ACTIVE
            ]
            
            # Filter by account_id if specified
            if account_id:
                candidate_keys = [
                    key for key in candidate_keys
                    if key.account_id == account_id
                ]
            
            if not candidate_keys:
                return None
            
            # Select key based on usage and availability
            selected_key = min(candidate_keys, key=lambda k: k.key_usage_count)
            
            return selected_key
            
        except Exception as e:
            logger.error(f"Failed to get active key: {e}")
            return None
    
    async def get_decrypted_key(self, key_id: str, user_id: str,
                             ip_address: str, user_agent: str) -> Optional[str]:
        """Get decrypted API key with security audit"""
        try:
            # Check if key exists
            if key_id not in self.provider_keys:
                return None
            
            provider_key = self.provider_keys[key_id]
            
            # Check key status and permissions
            if provider_key.key_status != KeyStatus.ACTIVE:
                return None
            
            # Log key access
            await self._log_security_event(
                key_id, 'key_accessed', 
                f"Key accessed for {provider_key.provider}",
                user_id, ip_address, user_agent, True, 'medium'
            )
            
            # Decrypt and return key
            decrypted_key = self._decrypt_api_key(provider_key.encrypted_key)
            
            # Update usage
            provider_key.key_usage_count += 1
            provider_key.key_last_used = datetime.now(timezone.utc)
            provider_key.updated_at = datetime.now(timezone.utc)
            
            # Update metrics
            self.metrics['decryption_operations'] += 1
            
            return decrypted_key
            
        except Exception as e:
            logger.error(f"Failed to get decrypted key: {e}")
            return None
    
    async def update_key_usage(self, key_id: str, usage_type: str,
                             audio_duration: float, cost_incurred: float,
                             request_id: str, meeting_id: str = None,
                             participant_id: str = None, response_time_ms: float = 0,
                             success: bool = True, error_message: str = None,
                             user_id: str = None, ip_address: str = None,
                             user_agent: str = None, metadata: Dict[str, Any] = None) -> None:
        """Update key usage statistics"""
        try:
            # Create usage log
            usage_log = KeyUsageLog(
                log_id=f"log_{secrets.token_urlsafe(16)}",
                key_id=key_id,
                provider=self.provider_keys[key_id].provider,
                usage_type=usage_type,
                audio_duration=audio_duration,
                cost_incurred=cost_incurred,
                request_id=request_id,
                meeting_id=meeting_id,
                participant_id=participant_id,
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.now(timezone.utc),
                metadata=metadata or {}
            )
            
            # Store usage log
            await self._store_usage_log(usage_log)
            
            # Update memory tracking
            self.usage_logs[key_id].append(usage_log)
            
            # Update provider key usage
            if key_id in self.provider_keys:
                self.provider_keys[key_id].key_usage_count += 1
                self.provider_keys[key_id].key_last_used = datetime.now(timezone.utc)
            
            # Check quota
            await self._check_quota(key_id, usage_type)
            
            # Update cost tracking
            await self._update_cost_tracking(key_id, cost_incurred, audio_duration)
            
            # Update metrics
            self.metrics['usage_logs'] += 1
            
            logger.debug(f"Updated usage for key {key_id}: {usage_type}, {audio_duration}s, ${cost_incurred}")
            
        except Exception as e:
            logger.error(f"Failed to update key usage: {e}")
    
    async def rotate_key(self, key_id: str, rotation_type: str = 'manual',
                       new_key_data: BYOKKeyRequest = None,
                       rotation_reason: str = "Manual rotation",
                       created_by: str = None, approved_by: str = None) -> Optional[KeyRotation]:
        """Rotate a provider key"""
        try:
            # Check if key exists and is active
            if key_id not in self.provider_keys:
                return None
            
            old_key = self.provider_keys[key_id]
            if old_key.key_status != KeyStatus.ACTIVE:
                return None
            
            # Create rotation record
            rotation_id = f"rot_{secrets.token_urlsafe(16)}"
            
            rotation = KeyRotation(
                rotation_id=rotation_id,
                key_id=key_id,
                old_key_id=key_id,
                new_key_id=None,
                rotation_type=rotation_type,
                rotation_status=KeyRotationStatus.IN_PROGRESS,
                rotation_started_at=datetime.now(timezone.utc),
                fallback_enabled=self.key_rotation_config['fallback_enabled'],
                grace_period_days=self.key_rotation_config['grace_period_days'],
                rollback_enabled=self.key_rotation_config['rollback_enabled'],
                rollback_deadline=datetime.now(timezone.utc) + timedelta(days=self.key_rotation_config['grace_period_days']),
                created_by=created_by,
                approved_by=approved_by,
                rotation_reason=rotation_reason,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            # Store rotation record
            await self._store_key_rotation(rotation)
            
            # Update old key status
            old_key.key_status = KeyStatus.INACTIVE
            old_key.rotation_status = KeyRotationStatus.IN_PROGRESS
            old_key.updated_at = datetime.now(timezone.utc)
            
            # Add new key if provided
            if new_key_data:
                new_key = await self.add_provider_key(
                    new_key_data, created_by, 
                    "0.0.0.0", "BYOK System"  # System IP and user agent
                )
                
                if new_key:
                    rotation.new_key_id = new_key.key_id
                    old_key.rotation_status = KeyRotationStatus.COMPLETED
                    rotation.rotation_status = KeyRotationStatus.COMPLETED
                    rotation.rotation_completed_at = datetime.now(timezone.utc)
            
            # Update metrics
            self.metrics['key_rotations'] += 1
            
            logger.info(f"Rotated key: {key_id} ({rotation_type})")
            return rotation
            
        except Exception as e:
            logger.error(f"Failed to rotate key: {e}")
            return None
    
    async def revoke_key(self, key_id: str, revoke_reason: str = "Manual revocation",
                       revoked_by: str = None, ip_address: str = None,
                       user_agent: str = None) -> bool:
        """Revoke a provider key"""
        try:
            # Check if key exists
            if key_id not in self.provider_keys:
                return False
            
            provider_key = self.provider_keys[key_id]
            
            # Update key status
            provider_key.key_status = KeyStatus.REVOKED
            provider_key.updated_at = datetime.now(timezone.utc)
            
            # Log security event
            await self._log_security_event(
                key_id, 'key_revoked', 
                f"Key revoked: {revoke_reason}",
                revoked_by, ip_address, user_agent, True, 'high'
            )
            
            # Update database
            await self._update_provider_key(provider_key)
            
            # Clean up usage tracking
            if key_id in self.quota_trackers:
                del self.quota_trackers[key_id]
            
            logger.info(f"Revoked key: {key_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke key: {e}")
            return False
    
    async def get_key_usage_report(self, key_id: str, period_start: datetime,
                                period_end: datetime) -> Dict[str, Any]:
        """Get usage report for a key"""
        try:
            # Query usage logs
            usage_logs = await self._get_usage_logs(key_id, period_start, period_end)
            
            # Calculate statistics
            total_requests = len(usage_logs)
            successful_requests = sum(1 for log in usage_logs if log.success)
            total_duration = sum(log.audio_duration for log in usage_logs)
            total_cost = sum(log.cost_incurred for log in usage_logs)
            average_response_time = sum(log.response_time_ms for log in usage_logs) / total_requests if total_requests > 0 else 0
            
            # Group by usage type
            usage_by_type = {}
            for log in usage_logs:
                if log.usage_type not in usage_by_type:
                    usage_by_type[log.usage_type] = {
                        'count': 0,
                        'duration': 0.0,
                        'cost': 0.0
                    }
                usage_by_type[log.usage_type]['count'] += 1
                usage_by_type[log.usage_type]['duration'] += log.audio_duration
                usage_by_type[log.usage_type]['cost'] += log.cost_incurred
            
            # Generate report
            report = {
                'key_id': key_id,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'success_rate': successful_requests / total_requests if total_requests > 0 else 0,
                'total_duration_seconds': total_duration,
                'total_cost_usd': total_cost,
                'average_cost_per_request': total_cost / total_requests if total_requests > 0 else 0,
                'average_response_time_ms': average_response_time,
                'usage_by_type': usage_by_type,
                'cost_per_minute': total_cost / (total_duration / 60) if total_duration > 0 else 0,
                'daily_usage': self._calculate_daily_usage(usage_logs),
                'top_meetings': self._get_top_meetings(usage_logs),
                'error_analysis': self._analyze_errors(usage_logs),
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to get key usage report: {e}")
            return {}
    
    async def get_cost_report(self, account_id: str = None, provider: ProviderType = None,
                           period_start: datetime = None, period_end: datetime = None) -> Dict[str, Any]:
        """Get cost report"""
        try:
            # Set default period if not provided
            if not period_start:
                period_start = datetime.now(timezone.utc).replace(day=1)  # Start of month
            if not period_end:
                period_end = datetime.now(timezone.utc)  # Now
            
            # Query cost tracking data
            cost_data = await self._get_cost_tracking_data(
                account_id, provider, period_start, period_end
            )
            
            # Calculate totals and averages
            total_cost = sum(data['total_cost'] for data in cost_data)
            total_requests = sum(data['total_requests'] for data in cost_data)
            total_duration = sum(data['total_duration_seconds'] for data in cost_data)
            
            # Group by provider
            cost_by_provider = {}
            for data in cost_data:
                provider_name = data['provider']
                if provider_name not in cost_by_provider:
                    cost_by_provider[provider_name] = {
                        'cost': 0.0,
                        'requests': 0,
                        'duration': 0.0
                    }
                cost_by_provider[provider_name]['cost'] += data['total_cost']
                cost_by_provider[provider_name]['requests'] += data['total_requests']
                cost_by_provider[provider_name]['duration'] += data['total_duration_seconds']
            
            # Generate report
            report = {
                'account_id': account_id,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'total_cost_usd': total_cost,
                'total_requests': total_requests,
                'total_duration_hours': total_duration / 3600,
                'average_cost_per_request': total_cost / total_requests if total_requests > 0 else 0,
                'average_cost_per_minute': total_cost / (total_duration / 60) if total_duration > 0 else 0,
                'cost_by_provider': cost_by_provider,
                'daily_cost_trend': self._calculate_daily_cost_trend(cost_data),
                'forecast_next_month': self._forecast_next_month_cost(cost_data),
                'budget_alerts': [data for data in cost_data if data['budget_exceeded']],
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to get cost report: {e}")
            return {}
    
    # Security and Encryption Methods
    def _encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key"""
        try:
            encrypted_key = self.cipher_suite.encrypt(api_key.encode())
            return base64.b64encode(encrypted_key).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt API key: {e}")
            raise
    
    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt API key"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_key.encode())
            decrypted_key = self.cipher_suite.decrypt(encrypted_bytes)
            return decrypted_key.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            raise
    
    def _hash_api_key(self, api_key: str) -> str:
        """Hash API key for verification"""
        try:
            return hashlib.sha256(api_key.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash API key: {e}")
            raise
    
    def _generate_encryption_key(self) -> str:
        """Generate encryption key"""
        try:
            return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        except Exception as e:
            logger.error(f"Failed to generate encryption key: {e}")
            raise
    
    # Provider Validation Methods
    async def _validate_provider_key(self, key_request: BYOKKeyRequest) -> bool:
        """Validate provider key with the actual provider"""
        try:
            provider = ProviderType(key_request.provider)
            
            # Create HTTP client for provider
            headers = self._get_provider_auth_headers(provider, key_request.api_key)
            
            # Test authentication
            if provider == ProviderType.OPENAI:
                return await self._validate_openai_key(headers, key_request.account_id)
            elif provider == ProviderType.GOOGLE:
                return await self._validate_google_key(headers, key_request.api_key)
            elif provider == ProviderType.AZURE:
                return await self._validate_azure_key(headers, key_request.api_key)
            elif provider == ProviderType.AWS:
                return await self._validate_aws_key(key_request.api_key, key_request.account_id)
            elif provider == ProviderType.DEEPGRAM:
                return await self._validate_deepgram_key(headers, key_request.api_key)
            elif provider == ProviderType.ASSEMBLYAI:
                return await self._validate_assemblyai_key(headers, key_request.api_key)
            else:
                # Default validation for unknown providers
                return True
                
        except Exception as e:
            logger.error(f"Failed to validate provider key: {e}")
            return False
    
    def _get_provider_auth_headers(self, provider: ProviderType, api_key: str) -> Dict[str, str]:
        """Get authentication headers for provider"""
        headers = {}
        
        if provider == ProviderType.OPENAI:
            headers['Authorization'] = f'Bearer {api_key}'
        elif provider == ProviderType.GOOGLE:
            headers['Authorization'] = f'Bearer {api_key}'
        elif provider == ProviderType.AZURE:
            headers['Ocp-Apim-Subscription-Key'] = api_key
        elif provider == ProviderType.DEEPGRAM:
            headers['Authorization'] = f'Token {api_key}'
        elif provider == ProviderType.ASSEMBLYAI:
            headers['Authorization'] = api_key
        
        return headers
    
    async def _validate_openai_key(self, headers: Dict[str, str], account_id: str) -> bool:
        """Validate OpenAI API key"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    'https://api.openai.com/v1/models',
                    headers=headers
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to validate OpenAI key: {e}")
            return False
    
    async def _validate_google_key(self, headers: Dict[str, str], api_key: str) -> bool:
        """Validate Google Speech API key"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f'https://speech.googleapis.com/v1/speech?key={api_key}',
                    json={'config': {'encoding': 'LINEAR16', 'sampleRateHertz': 16000}},
                    headers={'Content-Type': 'application/json'}
                )
                # Google returns 400 for empty request but validates the key
                return response.status_code in [200, 400]
        except Exception as e:
            logger.error(f"Failed to validate Google key: {e}")
            return False
    
    async def _validate_azure_key(self, headers: Dict[str, str], api_key: str) -> bool:
        """Validate Azure Speech API key"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    'https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken',  # Would need region
                    headers=headers
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to validate Azure key: {e}")
            return False
    
    async def _validate_aws_key(self, api_key: str, account_id: str) -> bool:
        """Validate AWS credentials"""
        # AWS validation would require boto3 and IAM validation
        # For now, return True (implementation would go here)
        return True
    
    async def _validate_deepgram_key(self, headers: Dict[str, str], api_key: str) -> bool:
        """Validate Deepgram API key"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    'https://api.deepgram.com/v1/projects',
                    headers=headers
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to validate Deepgram key: {e}")
            return False
    
    async def _validate_assemblyai_key(self, headers: Dict[str, str], api_key: str) -> bool:
        """Validate AssemblyAI API key"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    'https://api.assemblyai.com/v2/account',
                    headers=headers
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to validate AssemblyAI key: {e}")
            return False
    
    # Background Tasks
    async def _key_rotation_scheduler(self) -> None:
        """Schedule and manage key rotations"""
        while self.is_running:
            try:
                await asyncio.sleep(self.key_rotation_config['rotation_check_interval_hours'] * 3600)
                
                # Check for keys that need rotation
                now = datetime.now(timezone.utc)
                for key_id, provider_key in self.provider_keys.items():
                    if provider_key.key_status == KeyStatus.ACTIVE:
                        # Check expiration
                        if provider_key.key_expires_at and provider_key.key_expires_at <= now:
                            await self.rotate_key(
                                key_id, 'scheduled', 
                                rotation_reason="Key expired",
                                created_by="system"
                            )
                        # Check rotation frequency
                        elif (now - provider_key.created_at).days >= provider_key.rotation_frequency_days:
                            await self.rotate_key(
                                key_id, 'scheduled',
                                rotation_reason=f"Scheduled rotation (every {provider_key.rotation_frequency_days} days)",
                                created_by="system"
                            )
                
            except Exception as e:
                logger.error(f"Error in key rotation scheduler: {e}")
    
    async def _quota_monitor(self) -> None:
        """Monitor usage quotas"""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                now = datetime.now(timezone.utc)
                
                for key_id, tracker in self.quota_trackers.items():
                    # Reset quota if period has expired
                    if tracker['period'] == 'daily':
                        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    elif tracker['period'] == 'weekly':
                        period_start = now - timedelta(days=now.weekday())
                        period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)
                    elif tracker['period'] == 'monthly':
                        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    else:
                        continue
                    
                    if tracker['period_start'] < period_start:
                        tracker['current_usage'] = 0
                        tracker['period_start'] = period_start
                    
                    # Check quota
                    if tracker['quota'] and tracker['current_usage'] >= tracker['quota']:
                        self.metrics['quota_violations'] += 1
                        await self._handle_quota_violation(key_id, tracker)
                
            except Exception as e:
                logger.error(f"Error in quota monitor: {e}")
    
    async def _cost_tracker(self) -> None:
        """Track costs and generate reports"""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # Update every hour
                
                # Update cost tracking for all keys
                now = datetime.now(timezone.utc)
                for key_id in self.provider_keys:
                    await self._update_cost_tracking(key_id, 0, 0)  # This would aggregate from usage logs
                
            except Exception as e:
                logger.error(f"Error in cost tracker: {e}")
    
    async def _security_monitor(self) -> None:
        """Monitor security events and detect anomalies"""
        while self.is_running:
            try:
                await asyncio.sleep(600)  # Check every 10 minutes
                
                # Analyze usage patterns for anomalies
                for key_id, logs in self.usage_logs.items():
                    recent_logs = [
                        log for log in logs[-100:]  # Last 100 logs
                        if (now - log.timestamp).total_seconds() < 3600  # Last hour
                    ]
                    
                    # Check for unusual activity patterns
                    if len(recent_logs) > 1000:  # High usage
                        self.metrics['security_incidents'] += 1
                        await self._handle_security_incident(key_id, 'high_usage', recent_logs)
                
            except Exception as e:
                logger.error(f"Error in security monitor: {e}")
    
    async def _cleanup_expired_keys(self) -> None:
        """Clean up expired and revoked keys"""
        while self.is_running:
            try:
                await asyncio.sleep(86400)  # Clean up daily
                
                now = datetime.now(timezone.utc)
                
                # Clean up usage logs older than 90 days
                cutoff_date = now - timedelta(days=90)
                for key_id in self.usage_logs:
                    self.usage_logs[key_id] = [
                        log for log in self.usage_logs[key_id]
                        if log.timestamp > cutoff_date
                    ]
                
                # Clean up memory
                for key_id in list(self.quota_trackers.keys()):
                    if key_id not in self.provider_keys:
                        del self.quota_trackers[key_id]
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collect and report metrics"""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Collect every 5 minutes
                
                # Store metrics in database
                await self._store_metrics(self.metrics)
                
                logger.info(f"BYOK Metrics: {self.metrics}")
                
            except Exception as e:
                logger.error(f"Error in metrics collector: {e}")
    
    # Database Storage Methods
    async def _store_provider_key(self, provider_key: ProviderKey) -> None:
        """Store provider key in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_byok_provider_keys (
                        key_id, provider, key_name, encrypted_key, key_hash, key_algorithm,
                        account_id, account_name, billing_id, key_permissions, key_usage_count,
                        key_last_used, key_expires_at, key_status, rotation_status,
                        rotation_scheduled_at, rotation_frequency_days, usage_quota,
                        usage_quota_period, cost_per_request, rate_limit_per_minute,
                        metadata, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                              $16, $17, $18, $19, $20, $21, $22, $23, $24, $25)
                    ON CONFLICT (key_id) DO UPDATE SET
                        key_name = EXCLUDED.key_name,
                        key_permissions = EXCLUDED.key_permissions,
                        key_usage_count = EXCLUDED.key_usage_count,
                        key_last_used = EXCLUDED.key_last_used,
                        key_status = EXCLUDED.key_status,
                        rotation_status = EXCLUDED.rotation_status,
                        rotation_scheduled_at = EXCLUDED.rotation_scheduled_at,
                        usage_quota = EXCLUDED.usage_quota,
                        usage_quota_period = EXCLUDED.usage_quota_period,
                        rate_limit_per_minute = EXCLUDED.rate_limit_per_minute,
                        metadata = EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                """,
                provider_key.key_id, provider_key.provider.value, provider_key.key_name,
                provider_key.encrypted_key, provider_key.key_hash, provider_key.key_algorithm,
                provider_key.account_id, provider_key.account_name, provider_key.billing_id,
                json.dumps(provider_key.key_permissions), provider_key.key_usage_count,
                provider_key.key_last_used, provider_key.key_expires_at, provider_key.key_status.value,
                provider_key.rotation_status.value, provider_key.rotation_scheduled_at,
                provider_key.rotation_frequency_days, provider_key.usage_quota,
                provider_key.usage_quota_period, provider_key.cost_per_request,
                provider_key.rate_limit_per_minute, json.dumps(provider_key.metadata),
                provider_key.created_at, provider_key.updated_at
                )
                
        except Exception as e:
            logger.error(f"Failed to store provider key: {e}")
    
    async def _store_usage_log(self, usage_log: KeyUsageLog) -> None:
        """Store usage log in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_byok_usage_logs (
                        log_id, key_id, provider, usage_type, audio_duration, cost_incurred,
                        request_id, meeting_id, participant_id, response_time_ms, success,
                        error_message, user_id, ip_address, user_agent, timestamp, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """,
                usage_log.log_id, usage_log.key_id, usage_log.provider.value,
                usage_log.usage_type, usage_log.audio_duration, usage_log.cost_incurred,
                usage_log.request_id, usage_log.meeting_id, usage_log.participant_id,
                usage_log.response_time_ms, usage_log.success, usage_log.error_message,
                usage_log.user_id, usage_log.ip_address, usage_log.user_agent,
                usage_log.timestamp, json.dumps(usage_log.metadata)
                )
                
        except Exception as e:
            logger.error(f"Failed to store usage log: {e}")
    
    async def _store_key_rotation(self, rotation: KeyRotation) -> None:
        """Store key rotation in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_byok_key_rotations (
                        rotation_id, key_id, old_key_id, new_key_id, rotation_type, rotation_status,
                        rotation_started_at, rotation_completed_at, fallback_enabled, grace_period_days,
                        rollback_enabled, rollback_deadline, created_by, approved_by, rotation_reason,
                        metadata, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                """,
                rotation.rotation_id, rotation.key_id, rotation.old_key_id, rotation.new_key_id,
                rotation.rotation_type, rotation.rotation_status.value, rotation.rotation_started_at,
                rotation.rotation_completed_at, rotation.fallback_enabled, rotation.grace_period_days,
                rotation.rollback_enabled, rotation.rollback_deadline, rotation.created_by,
                rotation.approved_by, rotation.rotation_reason, json.dumps(rotation.metadata),
                rotation.created_at, rotation.updated_at
                )
                
        except Exception as e:
            logger.error(f"Failed to store key rotation: {e}")
    
    async def _log_security_event(self, key_id: str, event_type: str, event_description: str,
                               user_id: str, ip_address: str, user_agent: str,
                               success: bool, risk_level: str = 'medium',
                               additional_data: Dict[str, Any] = None) -> None:
        """Log security event"""
        if not self.db_pool:
            return
        
        try:
            audit_id = f"audit_{secrets.token_urlsafe(16)}"
            
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_byok_security_audit (
                        audit_id, key_id, event_type, event_description, user_id, ip_address,
                        user_agent, success, risk_level, additional_data, timestamp
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                audit_id, key_id, event_type, event_description, user_id, ip_address,
                user_agent, success, risk_level, json.dumps(additional_data or {}),
                datetime.now(timezone.utc)
                )
                
            logger.info(f"Security audit logged: {event_type} for key {key_id} by {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
    
    # Utility Methods
    def get_metrics(self) -> Dict[str, Any]:
        """Get BYOK metrics"""
        return self.metrics.copy()
    
    def get_provider_key(self, key_id: str) -> Optional[ProviderKey]:
        """Get provider key by ID"""
        return self.provider_keys.get(key_id)
    
    def get_all_keys(self) -> List[ProviderKey]:
        """Get all provider keys"""
        return list(self.provider_keys.values())
    
    def get_keys_by_provider(self, provider: ProviderType) -> List[ProviderKey]:
        """Get keys by provider"""
        return [key for key in self.provider_keys.values() if key.provider == provider]
    
    def get_active_keys(self) -> List[ProviderKey]:
        """Get all active keys"""
        return [key for key in self.provider_keys.values() if key.key_status == KeyStatus.ACTIVE]
    
    async def _load_existing_keys(self) -> None:
        """Load existing keys from database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM zoom_byok_provider_keys
                """)
                
                for row in rows:
                    provider_key = ProviderKey(
                        key_id=row['key_id'],
                        provider=ProviderType(row['provider']),
                        key_name=row['key_name'],
                        encrypted_key=row['encrypted_key'],
                        key_hash=row['key_hash'],
                        key_algorithm=row['key_algorithm'],
                        account_id=row['account_id'],
                        account_name=row['account_name'],
                        billing_id=row['billing_id'],
                        key_permissions=json.loads(row['key_permissions']),
                        key_usage_count=row['key_usage_count'],
                        key_last_used=row['key_last_used'],
                        key_expires_at=row['key_expires_at'],
                        key_status=KeyStatus(row['key_status']),
                        rotation_status=KeyRotationStatus(row['rotation_status']),
                        rotation_scheduled_at=row['rotation_scheduled_at'],
                        rotation_frequency_days=row['rotation_frequency_days'],
                        usage_quota=row['usage_quota'],
                        usage_quota_period=row['usage_quota_period'],
                        cost_per_request=float(row['cost_per_request']),
                        rate_limit_per_minute=row['rate_limit_per_minute'],
                        metadata=json.loads(row['metadata']),
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    
                    self.provider_keys[provider_key.key_id] = provider_key
                    
                    # Initialize quota tracker
                    if provider_key.key_status == KeyStatus.ACTIVE:
                        self.quota_trackers[provider_key.key_id] = {
                            'current_usage': 0,
                            'quota': provider_key.usage_quota,
                            'period': provider_key.usage_quota_period,
                            'period_start': datetime.now(timezone.utc),
                            'rate_limiter': asyncio.Semaphore(provider_key.rate_limit_per_minute)
                        }
                
                self.metrics['keys_managed'] = len(self.provider_keys)
                logger.info(f"Loaded {len(self.provider_keys)} provider keys from database")
                
        except Exception as e:
            logger.error(f"Failed to load existing keys: {e}")
    
    # Placeholder methods for implementations
    async def _check_quota(self, key_id: str, usage_type: str) -> None:
        """Check quota for key usage"""
        # Implementation would go here
        pass
    
    async def _update_cost_tracking(self, key_id: str, cost: float, duration: float) -> None:
        """Update cost tracking for key"""
        # Implementation would go here
        pass
    
    async def _get_usage_logs(self, key_id: str, period_start: datetime, period_end: datetime) -> List[KeyUsageLog]:
        """Get usage logs for a key"""
        # Implementation would query database
        return []
    
    async def _get_cost_tracking_data(self, account_id: str, provider: ProviderType,
                                    period_start: datetime, period_end: datetime) -> List[Dict[str, Any]]:
        """Get cost tracking data"""
        # Implementation would query database
        return []
    
    def _calculate_daily_usage(self, usage_logs: List[KeyUsageLog]) -> Dict[str, Any]:
        """Calculate daily usage statistics"""
        # Implementation would group by date
        return {}
    
    def _get_top_meetings(self, usage_logs: List[KeyUsageLog]) -> List[Dict[str, Any]]:
        """Get top meetings by usage"""
        # Implementation would sort and limit
        return []
    
    def _analyze_errors(self, usage_logs: List[KeyUsageLog]) -> Dict[str, Any]:
        """Analyze error patterns"""
        # Implementation would categorize errors
        return {}
    
    def _calculate_daily_cost_trend(self, cost_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculate daily cost trend"""
        # Implementation would aggregate by date
        return []
    
    def _forecast_next_month_cost(self, cost_data: List[Dict[str, Any]]) -> float:
        """Forecast next month's cost"""
        # Implementation would use time series forecasting
        return 0.0
    
    async def _update_provider_key(self, provider_key: ProviderKey) -> None:
        """Update provider key in database"""
        # Implementation would update database record
        pass
    
    async def _store_metrics(self, metrics: Dict[str, Any]) -> None:
        """Store metrics in database"""
        # Implementation would store metrics
        pass
    
    async def _handle_quota_violation(self, key_id: str, tracker: Dict[str, Any]) -> None:
        """Handle quota violation"""
        # Implementation would send alerts and possibly suspend key
        pass
    
    async def _handle_security_incident(self, key_id: str, incident_type: str, logs: List[KeyUsageLog]) -> None:
        """Handle security incident"""
        # Implementation would send security alerts and possibly suspend key
        pass