"""
LanceDB Sync System Configuration with S3 Storage

This module provides configuration management for the LanceDB sync system,
including S3 storage backend support, environment variables, default values, and validation.

Key Assumptions:
- Backend folder might be in cloud or local environment
- Desktop app will always be local for LanceDB sync
- Backend will have cloud default settings for web app
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LanceDBSyncConfig:
    """Configuration for LanceDB sync system"""

    # Frontend-specific storage configuration
    # Web App: Cloud-native by default (S3 primary)
    # Desktop App: Local-first by default (local storage)
    frontend_type: str = "desktop"  # "web" or "desktop"

    # Backend location detection
    # Determines if backend is running in cloud or local environment
    backend_location: str = "local"  # "cloud" or "local"

    # Local storage for desktop app access
    local_db_path: str = "data/lancedb"
    local_db_table_name: str = "processed_documents"
    local_db_chunks_table_name: str = "document_chunks"

    # S3 as primary storage backend for web app
    s3_storage_enabled: bool = False
    s3_bucket: Optional[str] = None
    s3_prefix: str = "lancedb-primary"
    s3_region: str = "us-east-1"
    s3_endpoint: Optional[str] = None

    # S3 backup configuration (for desktop app sync)
    s3_backup_enabled: bool = False
    s3_backup_bucket: Optional[str] = None
    s3_backup_prefix: str = "lancedb-backup"

    # Sync behavior configuration
    sync_interval: int = 300  # seconds
    max_concurrent_processing: int = 5
    chunk_size_mb: int = 50
    max_retries: int = 3

    # Storage behavior - auto-configured based on frontend type and backend location
    use_s3_as_primary: bool = False  # Use S3 as primary storage backend
    local_cache_enabled: bool = True  # Keep local cache for performance
    sync_on_startup: bool = True  # Sync local ↔ S3 on startup

    # Source monitoring configuration
    enable_source_monitoring: bool = True
    sync_state_dir: str = "data/sync_state"
    health_check_interval: int = 60  # seconds

    # Change detection configuration
    default_poll_interval: int = 300  # seconds
    checksum_enabled: bool = True
    file_watch_patterns: list = None

    def __post_init__(self):
        """Initialize default values after dataclass initialization"""
        if self.file_watch_patterns is None:
            self.file_watch_patterns = ["*.pdf", "*.docx", "*.txt", "*.md", "*.json"]

        # Auto-configure based on frontend type if not explicitly set
        if self.frontend_type == "web" and not self.s3_storage_enabled:
            # Web app should have S3 storage enabled by default
            self.s3_storage_enabled = True
            self.use_s3_as_primary = True
        elif self.frontend_type == "desktop" and self.use_s3_as_primary:
            # Desktop app should be local-first by default
            self.use_s3_as_primary = False

        # Auto-detect backend location if not explicitly set
        if self.backend_location == "local":
            # Check if we're running in cloud environment
            if self._is_cloud_environment():
                self.backend_location = "cloud"

    @classmethod
    def from_env(cls) -> "LanceDBSyncConfig":
        """Create configuration from environment variables"""
        # Auto-detect frontend type or use environment variable
        frontend_type = os.environ.get("FRONTEND_TYPE", "desktop")

        # Auto-detect backend location or use environment variable
        backend_location = os.environ.get("BACKEND_LOCATION", "local")

        # Auto-configure based on frontend type
        if frontend_type == "web":
            # Web app: Cloud-native by default
            use_s3_as_primary = (
                os.environ.get("USE_S3_AS_PRIMARY", "true").lower() == "true"
            )
            local_cache_enabled = (
                os.environ.get("LOCAL_CACHE_ENABLED", "true").lower() == "true"
            )
            s3_storage_enabled = (
                os.environ.get("S3_STORAGE_ENABLED", "true").lower() == "true"
            )
        else:
            # Desktop app: Local-first by default
            use_s3_as_primary = (
                os.environ.get("USE_S3_AS_PRIMARY", "false").lower() == "true"
            )
            local_cache_enabled = (
                os.environ.get("LOCAL_CACHE_ENABLED", "true").lower() == "true"
            )
            s3_storage_enabled = (
                os.environ.get("S3_STORAGE_ENABLED", "false").lower() == "true"
            )

        return cls(
            # Frontend configuration
            frontend_type=frontend_type,
            backend_location=backend_location,
            # Local storage
            local_db_path=os.environ.get("LANCEDB_URI", "data/lancedb"),
            local_db_table_name=os.environ.get(
                "LANCEDB_TABLE_NAME", "processed_documents"
            ),
            local_db_chunks_table_name=os.environ.get(
                "LANCEDB_CHUNKS_TABLE_NAME", "document_chunks"
            ),
            # S3 storage configuration
            s3_storage_enabled=s3_storage_enabled,
            s3_bucket=os.environ.get("S3_BUCKET"),
            s3_prefix=os.environ.get("S3_PREFIX", "lancedb-primary"),
            s3_region=os.environ.get("AWS_REGION", "us-east-1"),
            s3_endpoint=os.environ.get("S3_ENDPOINT"),
            # S3 backup configuration
            s3_backup_enabled=os.environ.get("S3_BACKUP_ENABLED", "false").lower()
            == "true",
            s3_backup_bucket=os.environ.get("S3_BACKUP_BUCKET"),
            # Storage behavior
            use_s3_as_primary=use_s3_as_primary,
            local_cache_enabled=local_cache_enabled,
            sync_on_startup=os.environ.get("SYNC_ON_STARTUP", "true").lower() == "true",
            # Sync behavior
            sync_interval=int(os.environ.get("SYNC_INTERVAL", "300")),
            max_concurrent_processing=int(
                os.environ.get("MAX_CONCURRENT_PROCESSING", "5")
            ),
            chunk_size_mb=int(os.environ.get("CHUNK_SIZE_MB", "50")),
            max_retries=int(os.environ.get("MAX_RETRIES", "3")),
            # Source monitoring
            enable_source_monitoring=os.environ.get(
                "ENABLE_SOURCE_MONITORING", "true"
            ).lower()
            == "true",
            sync_state_dir=os.environ.get("SYNC_STATE_DIR", "data/sync_state"),
            health_check_interval=int(os.environ.get("HEALTH_CHECK_INTERVAL", "60")),
            # Change detection
            default_poll_interval=int(os.environ.get("DEFAULT_POLL_INTERVAL", "300")),
            checksum_enabled=os.environ.get("CHECKSUM_ENABLED", "true").lower()
            == "true",
        )

    def validate(self) -> bool:
        """Validate configuration values"""
        errors = []

        # Validate frontend configuration
        if self.frontend_type not in ["web", "desktop"]:
            errors.append(
                f"Invalid frontend_type: {self.frontend_type}. Must be 'web' or 'desktop'"
            )

        # Validate backend location
        if self.backend_location not in ["cloud", "local"]:
            errors.append(
                f"Invalid backend_location: {self.backend_location}. Must be 'cloud' or 'local'"
            )

        # Validate local storage (required for desktop, optional for web with local cache)
        if not self.local_db_path and (
            self.frontend_type == "desktop" or self.local_cache_enabled
        ):
            errors.append("local_db_path cannot be empty")

        # Validate S3 storage configuration if enabled
        if self.s3_storage_enabled:
            if not self.s3_bucket or not self.s3_bucket.strip():
                errors.append("s3_bucket cannot be empty when S3 storage is enabled")
            if not self.s3_prefix.strip():
                errors.append("s3_prefix cannot be empty")

        # Web app should have S3 storage enabled, but only if backend is in cloud
        if (
            self.frontend_type == "web"
            and not self.s3_storage_enabled
            and self.backend_location == "cloud"
        ):
            errors.append(
                "Web app frontend requires S3 storage to be enabled when backend is in cloud"
            )

        # Cloud backend should have S3 storage enabled (but allow testing scenarios)
        if (
            self.backend_location == "cloud"
            and not self.s3_storage_enabled
            and not os.environ.get("TEST_MODE") == "true"
        ):
            errors.append("Cloud backend requires S3 storage to be enabled")

        # Validate S3 backup configuration if enabled
        if self.s3_backup_enabled:
            if not self.s3_backup_bucket or not self.s3_backup_bucket.strip():
                errors.append(
                    "s3_backup_bucket cannot be empty when S3 backup is enabled"
                )

        # Validate storage mode consistency
        if self.use_s3_as_primary and not self.s3_storage_enabled:
            errors.append(
                "Cannot use S3 as primary storage when S3 storage is disabled"
            )

        # Desktop app must have local cache enabled
        if self.frontend_type == "desktop" and not self.local_cache_enabled:
            errors.append("Desktop app frontend requires local cache to be enabled")

        if not self.local_cache_enabled and not self.s3_storage_enabled:
            errors.append("At least one storage backend must be enabled")

        # Validate numeric values
        if self.sync_interval <= 0:
            errors.append("sync_interval must be positive")
        if self.max_concurrent_processing <= 0:
            errors.append("max_concurrent_processing must be positive")
        if self.chunk_size_mb <= 0:
            errors.append("chunk_size_mb must be positive")
        if self.max_retries < 0:
            errors.append("max_retries cannot be negative")
        if self.health_check_interval <= 0:
            errors.append("health_check_interval must be positive")

        if errors:
            for error in errors:
                logger.error(f"Configuration validation error: {error}")
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "frontend_type": self.frontend_type,
            "backend_location": self.backend_location,
            "local_db_path": self.local_db_path,
            "local_db_table_name": self.local_db_table_name,
            "local_db_chunks_table_name": self.local_db_chunks_table_name,
            "s3_storage_enabled": self.s3_storage_enabled,
            "s3_bucket": self.s3_bucket,
            "s3_prefix": self.s3_prefix,
            "s3_region": self.s3_region,
            "s3_endpoint": self.s3_endpoint,
            "s3_backup_enabled": self.s3_backup_enabled,
            "s3_backup_bucket": self.s3_backup_bucket,
            "s3_backup_prefix": self.s3_backup_prefix,
            "use_s3_as_primary": self.use_s3_as_primary,
            "local_cache_enabled": self.local_cache_enabled,
            "sync_on_startup": self.sync_on_startup,
            "sync_interval": self.sync_interval,
            "max_concurrent_processing": self.max_concurrent_processing,
            "chunk_size_mb": self.chunk_size_mb,
            "max_retries": self.max_retries,
            "enable_source_monitoring": self.enable_source_monitoring,
            "sync_state_dir": self.sync_state_dir,
            "health_check_interval": self.health_check_interval,
            "default_poll_interval": self.default_poll_interval,
            "checksum_enabled": self.checksum_enabled,
            "file_watch_patterns": self.file_watch_patterns,
        }

    def get_s3_key_prefix(self, user_id: str = "default") -> str:
        """Get S3 key prefix for a user"""
        return f"{self.s3_prefix}/users/{user_id}"

    def get_s3_backup_key_prefix(self, user_id: str = "default") -> str:
        """Get S3 backup key prefix for a user"""
        return f"{self.s3_backup_prefix}/users/{user_id}"

    def get_lancedb_uri(self, user_id: str = "default") -> str:
        """Get LanceDB URI based on configuration, frontend type, and backend location"""
        if self.use_s3_as_primary and self.s3_storage_enabled:
            # Use S3 as primary storage backend (web app default)
            s3_path = f"s3://{self.s3_bucket}/{self.get_s3_key_prefix(user_id)}"
            if self.s3_endpoint:
                s3_path += f"?endpoint_override={self.s3_endpoint}"
            return s3_path
        else:
            # Use local storage with optional S3 sync (desktop app default)
            return f"{self.local_db_path}/users/{user_id}"

    def should_sync_to_s3(self) -> bool:
        """Check if S3 sync should be performed"""
        return self.s3_backup_enabled and self.s3_backup_bucket

    def should_use_s3_primary(self) -> bool:
        """Check if S3 should be used as primary storage"""
        return self.use_s3_as_primary and self.s3_storage_enabled

    def is_web_frontend(self) -> bool:
        """Check if this is a web frontend configuration"""
        return self.frontend_type == "web"

    def is_desktop_frontend(self) -> bool:
        """Check if this is a desktop frontend configuration"""
        return self.frontend_type == "desktop"

    def get_recommended_storage_mode(self) -> str:
        """Get recommended storage mode based on frontend type and backend location"""
        if self.is_web_frontend():
            if self.backend_location == "cloud":
                return "s3_primary_local_cache"
            else:
                return "local_primary_s3_sync"
        else:
            # Desktop app is always local-first
            return "local_primary_s3_backup"

    def _is_cloud_environment(self) -> bool:
        """Detect if running in cloud environment"""
        # Check for explicit override first
        if os.environ.get("BACKEND_LOCATION") == "local":
            return False
        if os.environ.get("BACKEND_LOCATION") == "cloud":
            return True

        # Check for cloud environment indicators
        cloud_indicators = [
            # AWS Lambda
            "LAMBDA_TASK_ROOT" in os.environ,
            "AWS_LAMBDA_FUNCTION_NAME" in os.environ,
            # Google Cloud Functions
            "FUNCTION_NAME" in os.environ,
            "FUNCTION_TARGET" in os.environ,
            # Azure Functions
            "WEBSITE_SITE_NAME" in os.environ,
            "WEBSITE_INSTANCE_ID" in os.environ,
            # Docker/container environments
            "KUBERNETES_SERVICE_HOST" in os.environ,
            "ECS_CONTAINER_METADATA_URI" in os.environ,
            # Cloud-specific environment variables
            "CLOUD_RUN" in os.environ,
            "VERCEL" in os.environ,
            "RAILWAY_STATIC_URL" in os.environ,
        ]

        return any(cloud_indicators)

    def is_cloud_backend(self) -> bool:
        """Check if backend is running in cloud environment"""
        return self.backend_location == "cloud"

    def is_local_backend(self) -> bool:
        """Check if backend is running in local environment"""
        return self.backend_location == "local"


# Default configuration instance (lazy-loaded)
_default_config = None


def get_config() -> LanceDBSyncConfig:
    """Get the current configuration"""
    global _default_config
    if _default_config is None:
        _default_config = LanceDBSyncConfig.from_env()
    return _default_config


def update_config(**kwargs) -> LanceDBSyncConfig:
    """Update configuration with new values"""
    global _default_config
    current_config = get_config()
    new_config = LanceDBSyncConfig(**{**current_config.to_dict(), **kwargs})

    if new_config.validate():
        _default_config = new_config
        logger.info("Configuration updated successfully")
    else:
        logger.error("Configuration update failed validation")

    return _default_config
