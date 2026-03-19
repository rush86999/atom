"""
Coverage-driven tests for Config (currently 0% -> target 80%+)

Focus areas from config.py:
- ATOMConfig.__init__ (initialization)
- from_env() - configuration from environment variables
- from_file() - configuration from JSON file
- to_dict() - convert to dictionary
- to_file() - save to JSON file
- validate() - configuration validation
- get_database_url() - database URL retrieval
- is_production() - production mode check
- DatabaseConfig, RedisConfig, ServerConfig, SecurityConfig initialization
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from tempfile import TemporaryDirectory

from core.config import (
    ATOMConfig,
    DatabaseConfig,
    RedisConfig,
    SchedulerConfig,
    LanceDBConfig,
    ServerConfig,
    SecurityConfig,
    APIConfig,
    IntegrationConfig,
    AIConfig,
    LoggingConfig,
    get_config,
    load_config,
    setup_logging
)


class TestDatabaseConfig:
    """Test DatabaseConfig initialization and methods."""

    def test_init_default(self):
        """Cover default database configuration."""
        config = DatabaseConfig()

        assert config.url == "sqlite:///atom_data.db"
        assert config.echo is False
        assert config.pool_size == 10
        assert config.max_overflow == 20
        assert config.engine_type == "sqlite"

    def test_init_custom_values(self):
        """Cover custom database configuration."""
        config = DatabaseConfig(
            url="postgresql://user:pass@localhost/db",
            echo=True,
            pool_size=20,
            max_overflow=40
        )

        assert config.url == "postgresql://user:pass@localhost/db"
        assert config.echo is True
        assert config.pool_size == 20
        assert config.max_overflow == 40

    def test_post_init_from_env(self):
        """Cover database URL from environment variable."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test@localhost/testdb'}):
            config = DatabaseConfig()

            assert config.url == "postgresql://test@localhost/testdb"
            assert config.engine_type == "postgresql"

    def test_post_init_postgresql_detection(self):
        """Cover PostgreSQL engine type detection."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user@localhost/db'}):
            config = DatabaseConfig()

            assert config.engine_type == "postgresql"


class TestRedisConfig:
    """Test RedisConfig initialization and URL parsing."""

    def test_init_default(self):
        """Cover default Redis configuration."""
        config = RedisConfig()

        assert config.enabled is False
        assert config.url == "redis://localhost:6379/0"
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None

    def test_post_init_from_url(self):
        """Cover Redis URL parsing."""
        with patch.dict(os.environ, {'REDIS_URL': 'redis://:password@redis.example.com:6380/1'}):
            config = RedisConfig()

            assert config.enabled is True
            assert config.host == "redis.example.com"
            assert config.port == 6380
            assert config.password == "password"
            assert config.db == 1

    def test_post_init_rediss_detection(self):
        """Cover rediss URL SSL detection."""
        with patch.dict(os.environ, {'REDIS_URL': 'rediss://localhost:6379/0'}):
            config = RedisConfig()

            assert config.ssl is True

    def test_post_init_from_individual_env_vars(self):
        """Cover individual Redis environment variables."""
        with patch.dict(os.environ, {
            'REDIS_HOST': 'redis.example.com',
            'REDIS_PORT': '6380',
            'REDIS_PASSWORD': 'secret',
            'REDIS_DB': '2'
        }):
            config = RedisConfig()

            assert config.enabled is True
            assert config.host == "redis.example.com"
            assert config.port == 6380
            assert config.password == "secret"
            assert config.db == 2

    def test_post_init_invalid_db_path(self):
        """Cover invalid Redis DB path handling."""
        with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost/invalid'}):
            config = RedisConfig()

            # Should use default DB when parsing fails
            assert config.db == 0


class TestServerConfig:
    """Test ServerConfig initialization."""

    def test_init_default(self):
        """Cover default server configuration."""
        config = ServerConfig()

        assert config.host == "0.0.0.0"
        assert config.port == 5058
        assert config.debug is False
        assert config.workers == 1

    def test_post_init_from_env(self):
        """Cover server configuration from environment."""
        with patch.dict(os.environ, {
            'PORT': '8000',
            'HOST': '127.0.0.1',
            'DEBUG': 'true',
            'WORKERS': '4'
        }):
            config = ServerConfig()

            assert config.port == 8000
            assert config.host == "127.0.0.1"
            assert config.debug is True
            assert config.workers == 4

    def test_post_init_app_url(self):
        """Cover APP_URL environment variable."""
        with patch.dict(os.environ, {'APP_URL': 'https://app.example.com'}):
            config = ServerConfig()

            assert config.app_url == "https://app.example.com"


class TestSecurityConfig:
    """Test SecurityConfig initialization."""

    def test_init_default(self):
        """Cover default security configuration."""
        config = SecurityConfig()

        assert config.secret_key == "atom-secret-key-change-in-production"
        assert config.jwt_expiration == 86400
        assert config.allow_dev_temp_users is False

    def test_post_init_production_warning(self):
        """Cover production security warning."""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'SECRET_KEY': 'atom-secret-key-change-in-production'
        }):
            config = SecurityConfig()

            # Should have default secret key in production (logs warning)

    def test_post_init_dev_generated_key(self):
        """Cover development key generation."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            # Remove SECRET_KEY if set
            env = os.environ.copy()
            env.pop('SECRET_KEY', None)

            with patch.dict(os.environ, env, clear=True):
                with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
                    config = SecurityConfig()

                    # Should generate a key (different from default)
                    if not os.getenv('SECRET_KEY'):
                        # Key generation happens in __post_init__
                        assert len(config.secret_key) > 0

    def test_post_init_secret_key_override(self):
        """Cover SECRET_KEY environment variable override."""
        with patch.dict(os.environ, {'SECRET_KEY': 'custom-secret-key-12345'}):
            config = SecurityConfig()

            assert config.secret_key == "custom-secret-key-12345"

    def test_post_init_cors_origins(self):
        """Cover CORS origins parsing."""
        with patch.dict(os.environ, {'CORS_ORIGINS': 'http://localhost:3000,https://app.example.com'}):
            config = SecurityConfig()

            assert len(config.cors_origins) == 2
            assert "http://localhost:3000" in config.cors_origins
            assert "https://app.example.com" in config.cors_origins


class TestAPIConfig:
    """Test APIConfig initialization."""

    def test_init_default(self):
        """Cover default API configuration."""
        config = APIConfig()

        assert config.rate_limit == 100
        assert config.request_timeout == 30
        assert config.max_request_size == 10 * 1024 * 1024

    def test_post_init_from_env(self):
        """Cover API configuration from environment."""
        with patch.dict(os.environ, {
            'RATE_LIMIT': '200',
            'REQUEST_TIMEOUT': '60',
            'MAX_REQUEST_SIZE': '20971520'  # 20MB
        }):
            config = APIConfig()

            assert config.rate_limit == 200
            assert config.request_timeout == 60
            assert config.max_request_size == 20971520


class TestIntegrationConfig:
    """Test IntegrationConfig initialization."""

    def test_init_default(self):
        """Cover default integration configuration."""
        config = IntegrationConfig()

        assert config.google_client_id == ""
        assert config.microsoft_client_id == ""
        assert config.github_client_id == ""

    def test_post_init_google_credentials(self):
        """Cover Google integration credentials."""
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'google-id-123',
            'GOOGLE_CLIENT_SECRET': 'google-secret-456'
        }):
            config = IntegrationConfig()

            assert config.google_client_id == "google-id-123"
            assert config.google_client_secret == "google-secret-456"

    def test_post_init_jira_credentials(self):
        """Cover Jira integration credentials."""
        with patch.dict(os.environ, {
            'JIRA_BASE_URL': 'https://jira.example.com',
            'JIRA_USERNAME': 'testuser',
            'JIRA_API_TOKEN': 'token123'
        }):
            config = IntegrationConfig()

            assert config.jira_base_url == "https://jira.example.com"
            assert config.jira_username == "testuser"
            assert config.jira_api_token == "token123"


class TestAIConfig:
    """Test AIConfig initialization."""

    def test_init_default(self):
        """Cover default AI configuration."""
        config = AIConfig()

        assert config.model_name == "gpt-3.5-turbo"
        assert config.max_tokens == 2048
        assert config.temperature == 0.7

    def test_post_init_from_env(self):
        """Cover AI configuration from environment."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-test-key',
            'ANTHROPIC_API_KEY': 'sk-ant-test',
            'MODEL_NAME': 'gpt-4',
            'MAX_TOKENS': '4096',
            'TEMPERATURE': '0.5'
        }):
            config = AIConfig()

            assert config.openai_api_key == "sk-test-key"
            assert config.anthropic_api_key == "sk-ant-test"
            assert config.model_name == "gpt-4"
            assert config.max_tokens == 4096
            assert config.temperature == 0.5


class TestLoggingConfig:
    """Test LoggingConfig initialization."""

    def test_init_default(self):
        """Cover default logging configuration."""
        config = LoggingConfig()

        assert config.level == "INFO"
        assert config.file_path == "./logs/atom.log"
        assert config.max_bytes == 10 * 1024 * 1024
        assert config.backup_count == 5

    def test_post_init_from_env(self):
        """Cover logging configuration from environment."""
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FILE': '/var/log/atom/debug.log',
            'LOG_MAX_BYTES': '52428800',  # 50MB
            'LOG_BACKUP_COUNT': '10'
        }):
            config = LoggingConfig()

            assert config.level == "DEBUG"
            assert config.file_path == "/var/log/atom/debug.log"
            assert config.max_bytes == 52428800
            assert config.backup_count == 10


class TestATOMConfig:
    """Test ATOMConfig main configuration class."""

    def test_init_default(self):
        """Cover default ATOMConfig initialization."""
        config = ATOMConfig()

        assert config.database is not None
        assert config.lancedb is not None
        assert config.redis is not None
        assert config.server is not None
        assert config.security is not None
        assert config.api is not None
        assert config.integrations is not None
        assert config.ai is not None
        assert config.logging is not None

    def test_init_with_sub_configs(self):
        """Cover ATOMConfig with custom sub-configurations."""
        db_config = DatabaseConfig(url="postgresql://localhost/test")
        server_config = ServerConfig(port=8000)

        config = ATOMConfig(
            database=db_config,
            server=server_config
        )

        assert config.database.url == "postgresql://localhost/test"
        assert config.server.port == 8000

    def test_from_env(self):
        """Cover loading configuration from environment."""
        with patch.dict(os.environ, {'PORT': '9000'}):
            config = ATOMConfig.from_env()

            assert config.server.port == 9000

    def test_to_dict(self):
        """Cover converting configuration to dictionary."""
        config = ATOMConfig()

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert 'database' in config_dict
        assert 'server' in config_dict
        assert 'security' in config_dict

    def test_get_database_url(self):
        """Cover getting database URL."""
        config = ATOMConfig(
            database=DatabaseConfig(url="postgresql://localhost/test")
        )

        url = config.get_database_url()

        assert url == "postgresql://localhost/test"

    def test_get_lancedb_path(self):
        """Cover getting LanceDB path."""
        config = ATOMConfig(
            lancedb=LanceDBConfig(path="/custom/lancedb")
        )

        path = config.get_lancedb_path()

        assert path == "/custom/lancedb"

    def test_is_production_true(self):
        """Cover production mode detection."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            config = ATOMConfig.from_env()

            assert config.is_production() is True

    def test_is_production_false(self):
        """Cover development mode detection."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            config = ATOMConfig.from_env()

            assert config.is_development() is True

    def test_validate_success(self):
        """Cover successful configuration validation."""
        config = ATOMConfig(
            database=DatabaseConfig(url="postgresql://localhost/test"),
            security=SecurityConfig(secret_key="production-secret-key")
        )

        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            result = config.validate()

            assert result['valid'] is True
            assert len(result['issues']) == 0

    def test_validate_missing_database_url(self):
        """Cover validation failure for missing database URL."""
        config = ATOMConfig(
            database=DatabaseConfig(url="")
        )

        result = config.validate()

        assert result['valid'] is False
        assert any('Database URL' in issue for issue in result['issues'])

    def test_validate_production_default_secret(self):
        """Cover validation failure for default secret in production."""
        config = ATOMConfig(
            database=DatabaseConfig(url="postgresql://localhost/test"),
            security=SecurityConfig(secret_key="atom-secret-key-change-in-production")
        )

        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            result = config.validate()

            assert result['valid'] is False
            assert any('Secret key' in issue for issue in result['issues'])


class TestConfigFileOperations:
    """Test configuration file loading and saving."""

    def test_from_file_success(self, tmp_path):
        """Cover loading configuration from JSON file."""
        config_file = tmp_path / "config.json"
        config_data = {
            'database': {
                'url': 'postgresql://localhost/test',
                'echo': True
            },
            'server': {
                'port': 8000,
                'debug': True
            }
        }

        config_file.write_text(json.dumps(config_data))

        config = ATOMConfig.from_file(str(config_file))

        assert config.database.url == "postgresql://localhost/test"
        assert config.database.echo is True
        assert config.server.port == 8000
        assert config.server.debug is True

    def test_from_file_missing(self, tmp_path):
        """Cover loading from missing file (fallback to env)."""
        missing_file = tmp_path / "nonexistent.json"

        # Should fallback to environment
        config = ATOMConfig.from_file(str(missing_file))

        assert config is not None

    def test_from_file_invalid_json(self, tmp_path):
        """Cover loading from invalid JSON file."""
        config_file = tmp_path / "invalid.json"
        config_file.write_text("invalid json content")

        # Should fallback to environment
        config = ATOMConfig.from_file(str(config_file))

        assert config is not None

    def test_to_file_success(self, tmp_path):
        """Cover saving configuration to JSON file."""
        config = ATOMConfig(
            server=ServerConfig(port=9000)
        )

        output_file = tmp_path / "output.json"

        success = config.to_file(str(output_file))

        assert success is True
        assert output_file.exists()

        # Verify content
        with open(output_file) as f:
            data = json.load(f)

        assert data['server']['port'] == 9000

    def test_to_file_creates_directory(self, tmp_path):
        """Cover creating directory when saving config."""
        config = ATOMConfig()

        output_file = tmp_path / "nested" / "dir" / "config.json"

        success = config.to_file(str(output_file))

        assert success is True
        assert output_file.exists()


class TestGlobalConfigInstance:
    """Test global configuration instance."""

    def test_get_config_singleton(self):
        """Cover get_config returns singleton instance."""
        config1 = get_config()
        config2 = get_config()

        # Should return same instance
        assert config1 is config2

    def test_load_config_from_file(self, tmp_path):
        """Cover load_config from file."""
        config_file = tmp_path / "config.json"
        config_data = {'server': {'port': 7777}}
        config_file.write_text(json.dumps(config_data))

        load_config(str(config_file))

        config = get_config()
        assert config.server.port == 7777

    def test_load_config_from_env(self):
        """Cover load_config from environment."""
        with patch.dict(os.environ, {'PORT': '8888'}):
            load_config()

            config = get_config()
            assert config.server.port == 8888


class TestSetupLogging:
    """Test logging setup."""

    def test_setup_logging_default(self, tmp_path):
        """Cover logging setup with default config."""
        log_file = tmp_path / "test.log"

        config = LoggingConfig(
            file_path=str(log_file),
            level="DEBUG"
        )

        # Should not raise exception
        setup_logging(config)

        # Log file should be created
        assert log_file.exists()

    def test_setup_logging_creates_directory(self, tmp_path):
        """Cover logging setup creates log directory."""
        log_dir = tmp_path / "logs"
        log_file = log_dir / "atom.log"

        config = LoggingConfig(
            file_path=str(log_file)
        )

        setup_logging(config)

        # Directory should be created
        assert log_dir.exists()
        assert log_file.exists()


class TestLanceDBConfig:
    """Test LanceDBConfig initialization."""

    def test_init_default(self):
        """Cover default LanceDB configuration."""
        config = LanceDBConfig()

        assert config.path == "./data/atom_memory"
        assert config.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.chunk_size == 512
        assert config.overlap == 50

    def test_post_init_from_env(self):
        """Cover LanceDB path from environment."""
        with patch.dict(os.environ, {'LANCEDB_PATH': '/custom/lancedb/path'}):
            config = LanceDBConfig()

            assert config.path == "/custom/lancedb/path"


class TestSchedulerConfig:
    """Test SchedulerConfig initialization."""

    def test_init_default(self):
        """Cover default scheduler configuration."""
        config = SchedulerConfig()

        assert config.job_store_type == "sqlalchemy"
        assert config.job_store_url == "sqlite:///jobs.sqlite"
        assert config.misfire_grace_time == 3600
        assert config.coalesce is True
        assert config.max_instances == 3

    def test_post_init_from_env(self):
        """Cover scheduler configuration from environment."""
        with patch.dict(os.environ, {
            'SCHEDULER_JOB_STORE_TYPE': 'redis',
            'SCHEDULER_JOB_STORE_URL': 'redis://localhost:6379/1',
            'SCHEDULER_MISFIRE_GRACE_TIME': '1800'
        }):
            config = SchedulerConfig()

            assert config.job_store_type == "redis"
            assert config.job_store_url == "redis://localhost:6379/1"
            assert config.misfire_grace_time == 1800
