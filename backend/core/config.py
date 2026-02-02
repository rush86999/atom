"""
Configuration Management for ATOM Platform
Centralized configuration with environment variables and defaults
"""

import os
import json
import logging
from typing import Any, Dict, Optional, Union
from dataclass  dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str = "sqlite:///atom_data.db"
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    engine_type: str = "sqlite" # sqlite, postgresql
    
    def __post_init__(self):
        env_url = os.getenv('DATABASE_URL')
        if env_url:
            self.url = env_url
            if env_url.startswith('postgresql'):
                self.engine_type = "postgresql"
        elif not self.url:
            self.url = "sqlite:///atom_data.db"

@dataclass
class RedisConfig:
    """Redis configuration for caching and scheduling"""
    enabled: bool = False
    url: str = "redis://localhost:6379/0"
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    
    def __post_init__(self):
        self.url = os.getenv('REDIS_URL', self.url)
        # Parse URL if provided to populate other fields
        if self.url and '://' in self.url:
            self.enabled = True
            # Simple parsing (improvement: use urllib.parse)
            try:
                import urllib.parse as urlparse
                url = urlparse.urlparse(self.url)
                self.host = url.hostname or 'localhost'
                self.port = url.port or 6379
                self.password = url.password
                if url.path:
                    try:
                        self.db = int(url.path.lstrip('/'))
                    except ValueError as e:
                        logger.warning(f"Invalid Redis DB path in URL, using default: {e}")
                self.ssl = url.scheme == 'rediss'
            except Exception as e:
                logger.warning(f"Failed to parse Redis URL, using defaults: {e}")
        
        # Override with specific env vars if present
        if os.getenv('REDIS_HOST'):
            self.host = os.getenv('REDIS_HOST')
            self.enabled = True
        if os.getenv('REDIS_PORT'):
            self.port = int(os.getenv('REDIS_PORT'))
        if os.getenv('REDIS_PASSWORD'):
            self.password = os.getenv('REDIS_PASSWORD')
        if os.getenv('REDIS_DB'):
            self.db = int(os.getenv('REDIS_DB'))

@dataclass
class SchedulerConfig:
    """Workflow scheduler configuration"""
    job_store_type: str = "sqlalchemy" # sqlalchemy, redis
    job_store_url: str = "sqlite:///jobs.sqlite"
    misfire_grace_time: int = 3600
    coalesce: bool = True
    max_instances: int = 3
    
    def __post_init__(self):
        self.job_store_type = os.getenv('SCHEDULER_JOB_STORE_TYPE', self.job_store_type)
        self.job_store_url = os.getenv('SCHEDULER_JOB_STORE_URL', self.job_store_url)
        if os.getenv('SCHEDULER_MISFIRE_GRACE_TIME'):
            self.misfire_grace_time = int(os.getenv('SCHEDULER_MISFIRE_GRACE_TIME'))

@dataclass
class LanceDBConfig:
    """LanceDB configuration"""
    path: str = "./data/atom_memory"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 512
    overlap: int = 50
    
    def __post_init__(self):
        if not self.path:
            self.path = os.getenv('LANCEDB_PATH', './data/atom_memory')

@dataclass
class ServerConfig:
    """Server configuration"""
    host: str = "0.0.0.0"
    port: int = 5058
    debug: bool = False
    workers: int = 1
    reload: bool = False
    
    def __post_init__(self):
        if os.getenv('PORT'):
            self.port = int(os.getenv('PORT'))
        if os.getenv('HOST'):
            self.host = os.getenv('HOST')
        self.debug = os.getenv('DEBUG', 'false').lower() == 'true'
        self.reload = os.getenv('RELOAD', 'false').lower() == 'true'
        if os.getenv('WORKERS'):
            self.workers = int(os.getenv('WORKERS'))

@dataclass
class SecurityConfig:
    """Security configuration"""
    secret_key: str = "atom-secret-key-change-in-production"
    jwt_expiration: int = 86400  # 24 hours
    cors_origins: list = None
    encryption_key: str = None
    
    def __post_init__(self):
        self.secret_key = os.getenv('SECRET_KEY', self.secret_key)
        if os.getenv('JWT_EXPIRATION'):
            self.jwt_expiration = int(os.getenv('JWT_EXPIRATION'))
        if os.getenv('ENCRYPTION_KEY'):
            self.encryption_key = os.getenv('ENCRYPTION_KEY')
        
        if self.cors_origins is None:
            cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:1420')
            self.cors_origins = [origin.strip() for origin in cors_origins.split(',')]

@dataclass
class APIConfig:
    """API configuration"""
    rate_limit: int = 100  # requests per minute
    request_timeout: int = 30  # seconds
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    pagination_size: int = 50
    
    def __post_init__(self):
        if os.getenv('RATE_LIMIT'):
            self.rate_limit = int(os.getenv('RATE_LIMIT'))
        if os.getenv('REQUEST_TIMEOUT'):
            self.request_timeout = int(os.getenv('REQUEST_TIMEOUT'))
        if os.getenv('MAX_REQUEST_SIZE'):
            self.max_request_size = int(os.getenv('MAX_REQUEST_SIZE'))
        if os.getenv('PAGINATION_SIZE'):
            self.pagination_size = int(os.getenv('PAGINATION_SIZE'))

@dataclass
class IntegrationConfig:
    """Integration-specific configuration"""
    google_client_id: str = ""
    google_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    notion_token: str = ""
    jira_base_url: str = ""
    jira_username: str = ""
    jira_api_token: str = ""
    trello_api_key: str = ""
    trello_token: str = ""
    
    def __post_init__(self):
        # Google
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID', '')
        self.google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '')
        
        # Microsoft
        self.microsoft_client_id = os.getenv('MICROSOFT_CLIENT_ID', '')
        self.microsoft_client_secret = os.getenv('MICROSOFT_CLIENT_SECRET', '')
        
        # GitHub
        self.github_client_id = os.getenv('GITHUB_CLIENT_ID', '')
        self.github_client_secret = os.getenv('GITHUB_CLIENT_SECRET', '')
        
        # Notion
        self.notion_token = os.getenv('NOTION_ACCESS_TOKEN', '')
        
        # Jira
        self.jira_base_url = os.getenv('JIRA_BASE_URL', '')
        self.jira_username = os.getenv('JIRA_USERNAME', '')
        self.jira_api_token = os.getenv('JIRA_API_TOKEN', '')
        
        # Trello
        self.trello_api_key = os.getenv('TRELLO_API_KEY', '')
        self.trello_token = os.getenv('TRELLO_ACCESS_TOKEN', '')

@dataclass
class AIConfig:
    """AI/ML configuration"""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    model_name: str = "gpt-3.5-turbo"
    max_tokens: int = 2048
    temperature: float = 0.7
    
    def __post_init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY', '')
        if os.getenv('MODEL_NAME'):
            self.model_name = os.getenv('MODEL_NAME')
        if os.getenv('MAX_TOKENS'):
            self.max_tokens = int(os.getenv('MAX_TOKENS'))
        if os.getenv('TEMPERATURE'):
            self.temperature = float(os.getenv('TEMPERATURE'))

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "./logs/atom.log"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    def __post_init__(self):
        if os.getenv('LOG_LEVEL'):
            self.level = os.getenv('LOG_LEVEL').upper()
        if os.getenv('LOG_FILE'):
            self.file_path = os.getenv('LOG_FILE')
        if os.getenv('LOG_MAX_BYTES'):
            self.max_bytes = int(os.getenv('LOG_MAX_BYTES'))
        if os.getenv('LOG_BACKUP_COUNT'):
            self.backup_count = int(os.getenv('LOG_BACKUP_COUNT'))

@dataclass
class ATOMConfig:
    """Main ATOM configuration class"""
    database: DatabaseConfig = None
    lancedb: LanceDBConfig = None
    redis: RedisConfig = None
    scheduler: SchedulerConfig = None
    server: ServerConfig = None
    security: SecurityConfig = None
    api: APIConfig = None
    integrations: IntegrationConfig = None
    ai: AIConfig = None
    logging: LoggingConfig = None
    
    def __post_init__(self):
        # Initialize sub-configurations if not provided
        if self.database is None:
            self.database = DatabaseConfig()
        if self.lancedb is None:
            self.lancedb = LanceDBConfig()
        if self.redis is None:
            self.redis = RedisConfig()
        if self.scheduler is None:
            self.scheduler = SchedulerConfig()
        if self.server is None:
            self.server = ServerConfig()
        if self.security is None:
            self.security = SecurityConfig()
        if self.api is None:
            self.api = APIConfig()
        if self.integrations is None:
            self.integrations = IntegrationConfig()
        if self.ai is None:
            self.ai = AIConfig()
        if self.logging is None:
            self.logging = LoggingConfig()
    
    @classmethod
    def from_env(cls) -> 'ATOMConfig':
        """Load configuration from environment variables"""
        return cls()
    
    @classmethod
    def from_file(cls, config_path: str) -> 'ATOMConfig':
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Convert dictionaries to config objects
            if 'database' in config_data:
                config_data['database'] = DatabaseConfig(**config_data['database'])
            if 'lancedb' in config_data:
                config_data['lancedb'] = LanceDBConfig(**config_data['lancedb'])
            if 'redis' in config_data:
                config_data['redis'] = RedisConfig(**config_data['redis'])
            if 'scheduler' in config_data:
                config_data['scheduler'] = SchedulerConfig(**config_data['scheduler'])
            if 'server' in config_data:
                config_data['server'] = ServerConfig(**config_data['server'])
            if 'security' in config_data:
                config_data['security'] = SecurityConfig(**config_data['security'])
            if 'api' in config_data:
                config_data['api'] = APIConfig(**config_data['api'])
            if 'integrations' in config_data:
                config_data['integrations'] = IntegrationConfig(**config_data['integrations'])
            if 'ai' in config_data:
                config_data['ai'] = AIConfig(**config_data['ai'])
            if 'logging' in config_data:
                config_data['logging'] = LoggingConfig(**config_data['logging'])
            
            return cls(**config_data)
            
        except Exception as e:
            print(f"Error loading config from {config_path}: {e}")
            return cls.from_env()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self)
    
    def to_file(self, config_path: str) -> bool:
        """Save configuration to JSON file"""
        try:
            # Create directory if it doesn't exist
            Path(config_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving config to {config_path}: {e}")
            return False
    
    def validate(self) -> Dict[str, Any]:
        """Validate configuration and return any issues"""
        issues = []
        
        # Check database config
        if not self.database.url:
            issues.append("Database URL is required")
        
        # Check security config
        if not self.security.secret_key or self.security.secret_key == "atom-secret-key-change-in-production":
            if os.getenv('ENVIRONMENT', 'development') == 'production':
                issues.append("Secret key must be set in production")
        
        # Check integration tokens
        if os.getenv('ENVIRONMENT', 'development') == 'production':
            # Check critical integrations
            if not self.integrations.google_client_id:
                issues.append("Google client ID is recommended for full functionality")
            if not self.integrations.microsoft_client_id:
                issues.append("Microsoft client ID is recommended for full functionality")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    def get_database_url(self) -> str:
        """Get database URL"""
        return self.database.url
    
    def get_lancedb_path(self) -> str:
        """Get LanceDB path"""
        return self.lancedb.path
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return os.getenv('ENVIRONMENT', 'development') == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return os.getenv('ENVIRONMENT', 'development') == 'development'

# Global configuration instance
config = ATOMConfig.from_env()

def get_config() -> ATOMConfig:
    """Get global configuration instance"""
    return config

def load_config(config_path: str = None) -> ATOMConfig:
    """Load configuration from file or environment"""
    global config
    
    if config_path and os.path.exists(config_path):
        config = ATOMConfig.from_file(config_path)
        print(f"Configuration loaded from {config_path}")
    else:
        config = ATOMConfig.from_env()
        print("Configuration loaded from environment variables")
    
    return config

def setup_logging(config: LoggingConfig = None) -> None:
    """Setup logging based on configuration"""
    import logging
    import logging.handlers
    
    if config is None:
        config = get_config().logging
    
    # Create logs directory if it doesn't exist
    log_dir = Path(config.file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.level))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(config.format)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        config.file_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# Initialize configuration when module is imported
load_config()