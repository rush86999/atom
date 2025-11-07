"""
Configuration Management for ATOM Google Drive Integration
Environment-based configuration with validation
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from loguru import logger

@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    name: str = "atom"

@dataclass
class RedisConfig:
    """Redis configuration"""
    url: str = "redis://localhost:6379/0"
    decode_responses: bool = True
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    max_connections: int = 100

@dataclass
class GoogleDriveConfig:
    """Google Drive API configuration"""
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8000/auth/google/callback"
    scopes: List[str] = field(default_factory=lambda: [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file"
    ])
    webhook_secret: str = ""
    api_timeout: int = 30
    max_retries: int = 3
    rate_limit_requests: int = 100
    rate_limit_period: int = 100  # seconds

@dataclass
class LanceDBConfig:
    """LanceDB configuration"""
    path: str = "./lancedb/data"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    batch_size: int = 100
    max_cache_size: int = 1000
    index_type: str = "ivfflat"
    index_partitions: int = 100

@dataclass
class SearchConfig:
    """Search system configuration"""
    enabled: bool = True
    providers: List[str] = field(default_factory=lambda: ["google_drive", "lancedb"])
    default_provider: str = "google_drive"
    max_results: int = 1000
    default_limit: int = 50
    cache_ttl: int = 3600
    enable_semantic_search: bool = True
    enable_faceted_search: bool = True
    enable_real_time_search: bool = True
    enable_suggestions: bool = True
    min_search_length: int = 1
    debounce_time: int = 300

@dataclass
class AutomationConfig:
    """Workflow automation configuration"""
    enabled: bool = True
    max_concurrent_workflows: int = 10
    default_workflow_timeout: int = 300
    max_actions_per_workflow: int = 50
    scheduled_workflows_enabled: bool = True
    webhook_triggers_enabled: bool = True
    file_triggers_enabled: bool = True
    manual_triggers_enabled: bool = True
    workflow_history_days: int = 90

@dataclass
class SyncConfig:
    """Real-time synchronization configuration"""
    enabled: bool = True
    sync_interval: int = 30  # seconds
    max_sync_workers: int = 5
    batch_size: int = 100
    enable_webhooks: bool = True
    webhook_timeout: int = 10
    max_webhook_retries: int = 3
    sync_event_retention_days: int = 30
    incremental_sync_enabled: bool = True

@dataclass
class IngestionConfig:
    """Content ingestion pipeline configuration"""
    enabled: bool = True
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    supported_formats: List[str] = field(default_factory=lambda: [
        "pdf", "doc", "docx", "txt", "rtf", "odt",
        "jpg", "jpeg", "png", "gif", "bmp", "svg",
        "mp4", "avi", "mov", "wmv", "flv", "webm",
        "mp3", "wav", "flac", "aac", "ogg",
        "zip", "rar", "7z", "tar", "gz"
    ])
    max_concurrent_extractions: int = 5
    extraction_timeout: int = 60
    enable_ocr: bool = True
    enable_metadata_extraction: bool = True

@dataclass
class SecurityConfig:
    """Security configuration"""
    secret_key: str = ""
    encryption_key: str = ""
    jwt_expiration: int = 3600
    refresh_token_expiration: int = 86400
    max_login_attempts: int = 5
    lockout_duration: int = 300
    enable_csrf_protection: bool = True
    enable_rate_limiting: bool = True
    allowed_origins: List[str] = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080"
    ])

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file_path: str = "./logs/atom.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    enable_console: bool = True
    enable_file: bool = True
    log_format: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    enable_structured_logging: bool = True

@dataclass
class PerformanceConfig:
    """Performance configuration"""
    enable_caching: bool = True
    cache_default_timeout: int = 300
    enable_compression: bool = True
    compression_level: int = 6
    enable_async_processing: bool = True
    max_async_workers: int = 20
    request_timeout: int = 30
    enable_connection_pooling: bool = True

@dataclass
class MonitoringConfig:
    """Monitoring and analytics configuration"""
    enable_metrics: bool = True
    enable_health_checks: bool = True
    health_check_interval: int = 60
    metrics_retention_days: int = 30
    enable_performance_monitoring: bool = True
    enable_error_tracking: bool = True
    enable_usage_analytics: bool = True
    alert_webhook_url: str = ""

@dataclass
class Config:
    """Main configuration class"""
    # Basic Flask configuration
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    testing: bool = False
    version: str = "1.0.0"
    
    # Sub-configurations
    database: DatabaseConfig = None
    redis: RedisConfig = None
    google_drive: GoogleDriveConfig = None
    lancedb: LanceDBConfig = None
    search: SearchConfig = None
    automation: AutomationConfig = None
    sync: SyncConfig = None
    ingestion: IngestionConfig = None
    security: SecurityConfig = None
    logging: LoggingConfig = None
    performance: PerformanceConfig = None
    monitoring: MonitoringConfig = None
    
    def __post_init__(self):
        """Post-initialization setup"""
        self._validate_configuration()
        self._setup_logging()
        self._create_directories()
    
    def _validate_configuration(self):
        """Validate configuration values"""
        
        errors = []
        
        # Validate database configuration
        if not self.database or not self.database.url:
            errors.append("Database URL is required")
        
        # Validate security configuration
        if not self.security or not self.security.secret_key:
            errors.append("SECRET_KEY is required")
        
        # Validate Google Drive configuration
        if not self.google_drive:
            self.google_drive = GoogleDriveConfig()
        
        if self.google_drive and (not self.google_drive.client_id or not self.google_drive.client_secret):
            logger.warning("Google Drive client credentials not configured")
        
        # Validate paths
        if self.lancedb and self.lancedb.path:
            lancedb_path = Path(self.lancedb.path)
            if not lancedb_path.parent.exists():
                errors.append(f"LanceDB parent directory does not exist: {lancedb_path.parent}")
        
        if self.logging and self.logging.file_path:
            log_path = Path(self.logging.file_path)
            if not log_path.parent.exists():
                errors.append(f"Log file parent directory does not exist: {log_path.parent}")
        
        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors))
    
    def _setup_logging(self):
        """Setup logging based on configuration"""
        
        if not self.logging:
            return
        
        # Remove default loguru handler
        logger.remove()
        
        # Add console handler
        if self.logging.enable_console:
            logger.add(
                sys.stderr,
                format=self.logging.log_format,
                level=self.logging.level,
                colorize=True
            )
        
        # Add file handler
        if self.logging.enable_file:
            logger.add(
                self.logging.file_path,
                format=self.logging.log_format,
                level=self.logging.level,
                rotation=self.logging.max_file_size,
                retention=self.logging.backup_count,
                compression="zip",
                backtrace=True,
                diagnose=True
            )
    
    def _create_directories(self):
        """Create required directories"""
        
        directories = []
        
        # Add log directory
        if self.logging and self.logging.file_path:
            log_path = Path(self.logging.file_path)
            directories.append(log_path.parent)
        
        # Add LanceDB directory
        if self.lancedb and self.lancedb.path:
            lancedb_path = Path(self.lancedb.path)
            directories.append(lancedb_path)
            directories.append(lancedb_path.parent)
        
        # Create directories
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created directory: {directory}")
            except Exception as e:
                logger.error(f"Failed to create directory {directory}: {e}")
    
    @classmethod
    def from_env(cls, env_name: Optional[str] = None) -> 'Config':
        """Create configuration from environment variables"""
        
        env_name = env_name or os.getenv('FLASK_ENV', 'development')
        logger.info(f"Loading configuration for environment: {env_name}")
        
        # Create configuration
        config = Config()
        
        # Basic Flask configuration
        config.debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
        config.host = os.getenv('FLASK_HOST', '0.0.0.0')
        config.port = int(os.getenv('FLASK_PORT', '8000'))
        config.testing = os.getenv('FLASK_TESTING', 'false').lower() == 'true'
        config.version = os.getenv('APP_VERSION', '1.0.0')
        
        # Database configuration
        config.database = DatabaseConfig(
            url=os.getenv('DATABASE_URL', 'postgresql://atom:password@localhost/atom'),
            pool_size=int(os.getenv('DB_POOL_SIZE', '10')),
            max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '20')),
            pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', '30')),
            pool_recycle=int(os.getenv('DB_POOL_RECYCLE', '3600')),
            echo=os.getenv('DB_ECHO', 'false').lower() == 'true',
            name=os.getenv('DB_NAME', 'atom')
        )
        
        # Redis configuration
        config.redis = RedisConfig(
            url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
            decode_responses=os.getenv('REDIS_DECODE_RESPONSES', 'true').lower() == 'true',
            socket_timeout=int(os.getenv('REDIS_SOCKET_TIMEOUT', '5')),
            socket_connect_timeout=int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', '5')),
            retry_on_timeout=os.getenv('REDIS_RETRY_ON_TIMEOUT', 'true').lower() == 'true',
            health_check_interval=int(os.getenv('REDIS_HEALTH_CHECK_INTERVAL', '30')),
            max_connections=int(os.getenv('REDIS_MAX_CONNECTIONS', '100'))
        )
        
        # Google Drive configuration
        config.google_drive = GoogleDriveConfig(
            client_id=os.getenv('GOOGLE_DRIVE_CLIENT_ID', ''),
            client_secret=os.getenv('GOOGLE_DRIVE_CLIENT_SECRET', ''),
            redirect_uri=os.getenv('GOOGLE_DRIVE_REDIRECT_URI', 'http://localhost:8000/auth/google/callback'),
            scopes=os.getenv('GOOGLE_DRIVE_SCOPES', 'https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/drive.file').split(','),
            webhook_secret=os.getenv('GOOGLE_DRIVE_WEBHOOK_SECRET', ''),
            api_timeout=int(os.getenv('GOOGLE_DRIVE_API_TIMEOUT', '30')),
            max_retries=int(os.getenv('GOOGLE_DRIVE_MAX_RETRIES', '3')),
            rate_limit_requests=int(os.getenv('GOOGLE_DRIVE_RATE_LIMIT_REQUESTS', '100')),
            rate_limit_period=int(os.getenv('GOOGLE_DRIVE_RATE_LIMIT_PERIOD', '100'))
        )
        
        # LanceDB configuration
        config.lancedb = LanceDBConfig(
            path=os.getenv('LANCE_DB_PATH', './lancedb/data'),
            embedding_model=os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'),
            embedding_dimension=int(os.getenv('EMBEDDING_DIMENSION', '384')),
            batch_size=int(os.getenv('LANCE_BATCH_SIZE', '100')),
            max_cache_size=int(os.getenv('LANCE_MAX_CACHE_SIZE', '1000')),
            index_type=os.getenv('LANCE_INDEX_TYPE', 'ivfflat'),
            index_partitions=int(os.getenv('LANCE_INDEX_PARTITIONS', '100'))
        )
        
        # Search configuration
        config.search = SearchConfig(
            enabled=os.getenv('SEARCH_ENABLED', 'true').lower() == 'true',
            providers=os.getenv('SEARCH_PROVIDERS', 'google_drive,lancedb').split(','),
            default_provider=os.getenv('SEARCH_DEFAULT_PROVIDER', 'google_drive'),
            max_results=int(os.getenv('SEARCH_MAX_RESULTS', '1000')),
            default_limit=int(os.getenv('SEARCH_DEFAULT_LIMIT', '50')),
            cache_ttl=int(os.getenv('SEARCH_CACHE_TTL', '3600')),
            enable_semantic_search=os.getenv('SEARCH_ENABLE_SEMANTIC', 'true').lower() == 'true',
            enable_faceted_search=os.getenv('SEARCH_ENABLE_FACETED', 'true').lower() == 'true',
            enable_real_time_search=os.getenv('SEARCH_ENABLE_REAL_TIME', 'true').lower() == 'true',
            enable_suggestions=os.getenv('SEARCH_ENABLE_SUGGESTIONS', 'true').lower() == 'true',
            min_search_length=int(os.getenv('SEARCH_MIN_LENGTH', '1')),
            debounce_time=int(os.getenv('SEARCH_DEBOUNCE_TIME', '300'))
        )
        
        # Automation configuration
        config.automation = AutomationConfig(
            enabled=os.getenv('AUTOMATION_ENABLED', 'true').lower() == 'true',
            max_concurrent_workflows=int(os.getenv('MAX_CONCURRENT_WORKFLOWS', '10')),
            default_workflow_timeout=int(os.getenv('DEFAULT_WORKFLOW_TIMEOUT', '300')),
            max_actions_per_workflow=int(os.getenv('MAX_ACTIONS_PER_WORKFLOW', '50')),
            scheduled_workflows_enabled=os.getenv('SCHEDULED_WORKFLOWS_ENABLED', 'true').lower() == 'true',
            webhook_triggers_enabled=os.getenv('WEBHOOK_TRIGGERS_ENABLED', 'true').lower() == 'true',
            file_triggers_enabled=os.getenv('FILE_TRIGGERS_ENABLED', 'true').lower() == 'true',
            manual_triggers_enabled=os.getenv('MANUAL_TRIGGERS_ENABLED', 'true').lower() == 'true',
            workflow_history_days=int(os.getenv('WORKFLOW_HISTORY_DAYS', '90'))
        )
        
        # Sync configuration
        config.sync = SyncConfig(
            enabled=os.getenv('SYNC_ENABLED', 'true').lower() == 'true',
            sync_interval=int(os.getenv('SYNC_INTERVAL', '30')),
            max_sync_workers=int(os.getenv('MAX_SYNC_WORKERS', '5')),
            batch_size=int(os.getenv('SYNC_BATCH_SIZE', '100')),
            enable_webhooks=os.getenv('SYNC_ENABLE_WEBHOOKS', 'true').lower() == 'true',
            webhook_timeout=int(os.getenv('SYNC_WEBHOOK_TIMEOUT', '10')),
            max_webhook_retries=int(os.getenv('SYNC_MAX_WEBHOOK_RETRIES', '3')),
            sync_event_retention_days=int(os.getenv('SYNC_EVENT_RETENTION_DAYS', '30')),
            incremental_sync_enabled=os.getenv('INCREMENTAL_SYNC_ENABLED', 'true').lower() == 'true'
        )
        
        # Ingestion configuration
        config.ingestion = IngestionConfig(
            enabled=os.getenv('INGESTION_ENABLED', 'true').lower() == 'true',
            max_file_size=int(os.getenv('INGESTION_MAX_FILE_SIZE', str(100 * 1024 * 1024))),
            supported_formats=os.getenv('INGESTION_SUPPORTED_FORMATS', 'pdf,doc,docx,txt,rtf,odt,jpg,jpeg,png,gif,bmp,svg,mp4,avi,mov,wmv,flv,webm,mp3,wav,flac,aac,ogg,zip,rar,7z,tar,gz').split(','),
            max_concurrent_extractions=int(os.getenv('MAX_CONCURRENT_EXTRACTIONS', '5')),
            extraction_timeout=int(os.getenv('EXTRACTION_TIMEOUT', '60')),
            enable_ocr=os.getenv('ENABLE_OCR', 'true').lower() == 'true',
            enable_metadata_extraction=os.getenv('ENABLE_METADATA_EXTRACTION', 'true').lower() == 'true'
        )
        
        # Security configuration
        config.security = SecurityConfig(
            secret_key=os.getenv('SECRET_KEY', ''),
            encryption_key=os.getenv('ENCRYPTION_KEY', ''),
            jwt_expiration=int(os.getenv('JWT_EXPIRATION', '3600')),
            refresh_token_expiration=int(os.getenv('REFRESH_TOKEN_EXPIRATION', '86400')),
            max_login_attempts=int(os.getenv('MAX_LOGIN_ATTEMPTS', '5')),
            lockout_duration=int(os.getenv('LOCKOUT_DURATION', '300')),
            enable_csrf_protection=os.getenv('ENABLE_CSRF_PROTECTION', 'true').lower() == 'true',
            enable_rate_limiting=os.getenv('ENABLE_RATE_LIMITING', 'true').lower() == 'true',
            allowed_origins=os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080').split(',')
        )
        
        # Logging configuration
        config.logging = LoggingConfig(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            file_path=os.getenv('LOG_FILE_PATH', './logs/atom.log'),
            max_file_size=int(os.getenv('LOG_MAX_FILE_SIZE', str(10 * 1024 * 1024))),
            backup_count=int(os.getenv('LOG_BACKUP_COUNT', '5')),
            enable_console=os.getenv('LOG_ENABLE_CONSOLE', 'true').lower() == 'true',
            enable_file=os.getenv('LOG_ENABLE_FILE', 'true').lower() == 'true',
            log_format=os.getenv('LOG_FORMAT', "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"),
            enable_structured_logging=os.getenv('LOG_ENABLE_STRUCTURED', 'true').lower() == 'true'
        )
        
        # Performance configuration
        config.performance = PerformanceConfig(
            enable_caching=os.getenv('PERFORMANCE_ENABLE_CACHING', 'true').lower() == 'true',
            cache_default_timeout=int(os.getenv('CACHE_DEFAULT_TIMEOUT', '300')),
            enable_compression=os.getenv('PERFORMANCE_ENABLE_COMPRESSION', 'true').lower() == 'true',
            compression_level=int(os.getenv('COMPRESSION_LEVEL', '6')),
            enable_async_processing=os.getenv('PERFORMANCE_ENABLE_ASYNC', 'true').lower() == 'true',
            max_async_workers=int(os.getenv('MAX_ASYNC_WORKERS', '20')),
            request_timeout=int(os.getenv('REQUEST_TIMEOUT', '30')),
            enable_connection_pooling=os.getenv('ENABLE_CONNECTION_POOLING', 'true').lower() == 'true'
        )
        
        # Monitoring configuration
        config.monitoring = MonitoringConfig(
            enable_metrics=os.getenv('MONITORING_ENABLE_METRICS', 'true').lower() == 'true',
            enable_health_checks=os.getenv('MONITORING_ENABLE_HEALTH_CHECKS', 'true').lower() == 'true',
            health_check_interval=int(os.getenv('MONITORING_HEALTH_CHECK_INTERVAL', '60')),
            metrics_retention_days=int(os.getenv('MONITORING_METRICS_RETENTION_DAYS', '30')),
            enable_performance_monitoring=os.getenv('MONITORING_ENABLE_PERFORMANCE', 'true').lower() == 'true',
            enable_error_tracking=os.getenv('MONITORING_ENABLE_ERROR_TRACKING', 'true').lower() == 'true',
            enable_usage_analytics=os.getenv('MONITORING_ENABLE_USAGE_ANALYTICS', 'true').lower() == 'true',
            alert_webhook_url=os.getenv('MONITORING_ALERT_WEBHOOK_URL', '')
        )
        
        logger.info(f"Configuration loaded successfully for environment: {env_name}")
        return config

# Predefined configurations
class ConfigFactory:
    """Factory for predefined configurations"""
    
    @staticmethod
    def development() -> Config:
        """Development configuration"""
        return Config.from_env('development')
    
    @staticmethod
    def testing() -> Config:
        """Testing configuration"""
        return Config.from_env('testing')
    
    @staticmethod
    def staging() -> Config:
        """Staging configuration"""
        return Config.from_env('staging')
    
    @staticmethod
    def production() -> Config:
        """Production configuration"""
        return Config.from_env('production')

# Configuration mapping
config_map = {
    'development': ConfigFactory.development,
    'testing': ConfigFactory.testing,
    'staging': ConfigFactory.staging,
    'production': ConfigFactory.production
}

def get_config(env_name: Optional[str] = None) -> Config:
    """Get configuration for specified environment"""
    
    env_name = env_name or os.getenv('FLASK_ENV', 'development')
    
    if env_name in config_map:
        return config_map[env_name]()
    else:
        logger.warning(f"Unknown environment: {env_name}, using development")
        return ConfigFactory.development()

# Global configuration instance
_config: Optional[Config] = None

def init_config(env_name: Optional[str] = None) -> Config:
    """Initialize global configuration"""
    
    global _config
    _config = get_config(env_name)
    return _config

def get_config_instance() -> Config:
    """Get global configuration instance"""
    
    global _config
    if _config is None:
        _config = get_config()
    return _config

# Export configuration classes
__all__ = [
    'Config',
    'DatabaseConfig',
    'RedisConfig',
    'GoogleDriveConfig',
    'LanceDBConfig',
    'SearchConfig',
    'AutomationConfig',
    'SyncConfig',
    'IngestionConfig',
    'SecurityConfig',
    'LoggingConfig',
    'PerformanceConfig',
    'MonitoringConfig',
    'ConfigFactory',
    'get_config',
    'init_config',
    'get_config_instance',
    'config_map'
]