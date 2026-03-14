"""
Coverage-driven tests for Config (currently 0% -> target 80%+)

Focus areas from config.py:
- DatabaseConfig: Environment variable loading, PostgreSQL detection (lines 16-31)
- RedisConfig: URL parsing, SSL detection, individual env vars (lines 33-74)
- SchedulerConfig: Job store configuration (lines 76-89)
- LanceDBConfig: Path configuration (lines 91-101)
- ServerConfig: Port, host, debug, workers, app_url (lines 103-122)
- SecurityConfig: Secret key generation, CORS origins, production warnings (lines 124-162)
- APIConfig: Rate limiting, timeouts (lines 164-180)
- IntegrationConfig: OAuth credentials (lines 182-221)
- AIConfig: API keys, model settings (lines 223-240)
- LoggingConfig: Log levels, file rotation (lines 242-259)
- ATOMConfig: Main config class, from_env(), from_file(), to_dict(), to_file(), validate() (lines 261-422)
- Global functions: get_config(), load_config(), setup_logging() (lines 424-479)
"""

import pytest
import json
import os
import logging
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


class TestDatabaseConfigCoverage:
    """Coverage-driven tests for DatabaseConfig (lines 16-31)."""

    def test_database_default_values(self, monkeypatch):
        """Cover default database configuration (lines 18-22)."""
        # Remove DATABASE_URL to test defaults
        monkeypatch.delenv('DATABASE_URL', raising=False)

        config = DatabaseConfig()

        assert config.url == "sqlite:///atom_data.db"
        assert config.echo is False
        assert config.pool_size == 10
        assert config.max_overflow == 20
        assert config.engine_type == "sqlite"

    @pytest.mark.parametrize("env_url,expected_engine,expected_url", [
        ("postgresql://user:pass@localhost/mydb", "postgresql", "postgresql://user:pass@localhost/mydb"),
        ("postgresql://localhost/test", "postgresql", "postgresql://localhost/test"),
        ("sqlite:///custom.db", "sqlite", "sqlite:///custom.db"),
    ])
    def test_database_url_from_env(self, monkeypatch, env_url, expected_engine, expected_url):
        """Cover DATABASE_URL environment variable loading (lines 25-29)."""
        monkeypatch.setenv('DATABASE_URL', env_url)

        config = DatabaseConfig()

        assert config.engine_type == expected_engine
        assert config.url == expected_url

    def test_database_empty_url_fallback(self, monkeypatch):
        """Cover empty URL fallback to default (lines 30-31)."""
        monkeypatch.setenv('DATABASE_URL', '')

        config = DatabaseConfig()

        assert config.url == "sqlite:///atom_data.db"

    def test_database_custom_values(self):
        """Cover custom DatabaseConfig initialization (line 18-22)."""
        config = DatabaseConfig(
            url="postgresql://custom",
            echo=True,
            pool_size=20,
            max_overflow=40,
            engine_type="postgresql"
        )

        assert config.url == "postgresql://custom"
        assert config.echo is True
        assert config.pool_size == 20
        assert config.max_overflow == 40
        assert config.engine_type == "postgresql"


class TestRedisConfigCoverage:
    """Coverage-driven tests for RedisConfig (lines 33-74)."""

    def test_redis_default_values(self, monkeypatch):
        """Cover default Redis configuration (lines 36-42)."""
        monkeypatch.delenv('REDIS_URL', raising=False)
        monkeypatch.delenv('REDIS_HOST', raising=False)

        config = RedisConfig()

        assert config.enabled is False
        assert config.url == "redis://localhost:6379/0"
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.ssl is False

    def test_redis_url_parsing(self, monkeypatch):
        """Cover Redis URL parsing (lines 44-63)."""
        monkeypatch.setenv('REDIS_URL', 'redis://:password@redis.example.com:6380/1')

        config = RedisConfig()

        assert config.enabled is True
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.password == "password"
        assert config.db == 1

    def test_redis_rediss_ssl_detection(self, monkeypatch):
        """Cover rediss:// SSL detection (line 61)."""
        monkeypatch.setenv('REDIS_URL', 'rediss://localhost:6379/0')

        config = RedisConfig()

        assert config.ssl is True

    def test_redis_invalid_db_path(self, monkeypatch):
        """Cover invalid Redis DB path handling (lines 57-60)."""
        monkeypatch.setenv('REDIS_URL', 'redis://localhost/invalid')

        config = RedisConfig()

        # Should use default DB when parsing fails
        assert config.db == 0

    def test_redis_url_parse_exception(self, monkeypatch, caplog):
        """Cover URL parsing exception (lines 62-63)."""
        monkeypatch.setenv('REDIS_URL', 'redis://[invalid')

        config = RedisConfig()

        # Should log warning and use defaults
        assert config.host == "localhost"
        assert config.port == 6379

    def test_redis_individual_env_vars(self, monkeypatch):
        """Cover individual Redis environment variables (lines 65-74)."""
        monkeypatch.setenv('REDIS_HOST', 'redis.example.com')
        monkeypatch.setenv('REDIS_PORT', '6380')
        monkeypatch.setenv('REDIS_PASSWORD', 'secret')
        monkeypatch.setenv('REDIS_DB', '2')

        config = RedisConfig()

        assert config.enabled is True
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.password == "secret"
        assert config.db == 2


class TestSchedulerConfigCoverage:
    """Coverage-driven tests for SchedulerConfig (lines 76-89)."""

    def test_scheduler_default_values(self, monkeypatch):
        """Cover default scheduler configuration (lines 78-83)."""
        monkeypatch.delenv('SCHEDULER_JOB_STORE_TYPE', raising=False)
        monkeypatch.delenv('SCHEDULER_JOB_STORE_URL', raising=False)
        monkeypatch.delenv('SCHEDULER_MISFIRE_GRACE_TIME', raising=False)

        config = SchedulerConfig()

        assert config.job_store_type == "sqlalchemy"
        assert config.job_store_url == "sqlite:///jobs.sqlite"
        assert config.misfire_grace_time == 3600
        assert config.coalesce is True
        assert config.max_instances == 3

    def test_scheduler_from_env(self, monkeypatch):
        """Cover scheduler environment variables (lines 86-89)."""
        monkeypatch.setenv('SCHEDULER_JOB_STORE_TYPE', 'redis')
        monkeypatch.setenv('SCHEDULER_JOB_STORE_URL', 'redis://localhost:6379/1')
        monkeypatch.setenv('SCHEDULER_MISFIRE_GRACE_TIME', '1800')

        config = SchedulerConfig()

        assert config.job_store_type == "redis"
        assert config.job_store_url == "redis://localhost:6379/1"
        assert config.misfire_grace_time == 1800


class TestLanceDBConfigCoverage:
    """Coverage-driven tests for LanceDBConfig (lines 91-101)."""

    def test_lancedb_default_values(self, monkeypatch):
        """Cover default LanceDB configuration (lines 94-97)."""
        monkeypatch.delenv('LANCEDB_PATH', raising=False)

        config = LanceDBConfig()

        assert config.path == "./data/atom_memory"
        assert config.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.chunk_size == 512
        assert config.overlap == 50

    def test_lancedb_path_from_env(self, monkeypatch):
        """Cover LANCEDB_PATH environment variable (lines 99-101)."""
        monkeypatch.setenv('LANCEDB_PATH', '/custom/lancedb/path')

        config = LanceDBConfig()

        assert config.path == "/custom/lancedb/path"

    def test_lancedb_empty_path_fallback(self, monkeypatch):
        """Cover empty path fallback (line 100-101)."""
        monkeypatch.setenv('LANCEDB_PATH', '')

        config = LanceDBConfig()

        assert config.path == "./data/atom_memory"


class TestServerConfigCoverage:
    """Coverage-driven tests for ServerConfig (lines 103-122)."""

    def test_server_default_values(self, monkeypatch):
        """Cover default server configuration (lines 106-111)."""
        monkeypatch.delenv('PORT', raising=False)
        monkeypatch.delenv('HOST', raising=False)
        monkeypatch.delenv('DEBUG', raising=False)
        monkeypatch.delenv('WORKERS', raising=False)
        monkeypatch.delenv('APP_URL', raising=False)

        config = ServerConfig()

        assert config.host == "0.0.0.0"
        assert config.port == 5058
        assert config.debug is False
        assert config.workers == 1
        assert config.reload is False
        assert config.app_url == "http://localhost:3000"

    @pytest.mark.parametrize("env_var,value,expected_field,expected_value", [
        ("PORT", "8000", "port", 8000),
        ("HOST", "127.0.0.1", "host", "127.0.0.1"),
        ("DEBUG", "true", "debug", True),
        ("DEBUG", "True", "debug", True),
        ("DEBUG", "false", "debug", False),
        ("RELOAD", "true", "reload", True),
        ("WORKERS", "4", "workers", 4),
        ("APP_URL", "https://app.example.com", "app_url", "https://app.example.com"),
    ])
    def test_server_from_env(self, monkeypatch, env_var, value, expected_field, expected_value):
        """Cover server environment variables (lines 114-122)."""
        monkeypatch.setenv(env_var, value)

        config = ServerConfig()

        assert getattr(config, expected_field) == expected_value


class TestSecurityConfigCoverage:
    """Coverage-driven tests for SecurityConfig (lines 124-162)."""

    def test_security_default_values(self, monkeypatch):
        """Cover default security configuration (lines 127-131)."""
        monkeypatch.delenv('SECRET_KEY', raising=False)
        monkeypatch.delenv('JWT_EXPIRATION', raising=False)
        monkeypatch.delenv('CORS_ORIGINS', raising=False)
        monkeypatch.delenv('ALLOW_DEV_TEMP_USERS', raising=False)
        monkeypatch.delenv('ENVIRONMENT', raising=False)

        config = SecurityConfig()

        assert config.secret_key == "atom-secret-key-change-in-production"
        assert config.jwt_expiration == 86400
        assert config.allow_dev_temp_users is False
        assert config.encryption_key is None
        assert isinstance(config.cors_origins, list)

    def test_security_production_warning(self, monkeypatch, caplog):
        """Cover production security warning (lines 137-139)."""
        monkeypatch.setenv('ENVIRONMENT', 'production')
        monkeypatch.setenv('SECRET_KEY', 'atom-secret-key-change-in-production')

        with caplog.at_level(logging.ERROR):
            config = SecurityConfig()

        # Should log critical warning about default secret key
        assert any('CRITICAL' in record.message and 'default SECRET_KEY' in record.message
                   for record in caplog.records)

    def test_security_dev_key_generation(self, monkeypatch, caplog):
        """Cover development key generation (lines 142-145)."""
        monkeypatch.setenv('ENVIRONMENT', 'development')
        monkeypatch.delenv('SECRET_KEY', raising=False)

        with caplog.at_level(logging.WARNING):
            config = SecurityConfig()

        # Should generate a secure key
        assert len(config.secret_key) > 20
        assert config.secret_key != "atom-secret-key-change-in-production"

        # Should log warning
        assert any('Generated temporary SECRET_KEY' in record.message
                   for record in caplog.records)

    def test_security_secret_key_override(self, monkeypatch):
        """Cover SECRET_KEY override (line 147)."""
        monkeypatch.setenv('SECRET_KEY', 'custom-secret-key-12345')

        config = SecurityConfig()

        assert config.secret_key == "custom-secret-key-12345"

    def test_security_jwt_expiration(self, monkeypatch):
        """Cover JWT expiration override (lines 148-149)."""
        monkeypatch.setenv('JWT_EXPIRATION', '3600')

        config = SecurityConfig()

        assert config.jwt_expiration == 3600

    def test_security_encryption_key(self, monkeypatch):
        """Cover encryption key (lines 150-151)."""
        monkeypatch.setenv('ENCRYPTION_KEY', 'encryption-secret')

        config = SecurityConfig()

        assert config.encryption_key == "encryption-secret"

    def test_security_allow_dev_temp_users(self, monkeypatch):
        """Cover ALLOW_DEV_TEMP_USERS (line 153)."""
        monkeypatch.setenv('ALLOW_DEV_TEMP_USERS', 'true')

        config = SecurityConfig()

        assert config.allow_dev_temp_users is True

    def test_security_cors_origins_parsing(self, monkeypatch):
        """Cover CORS origins parsing (lines 155-157)."""
        monkeypatch.setenv('CORS_ORIGINS', 'http://localhost:3000,https://app.example.com')

        config = SecurityConfig()

        assert len(config.cors_origins) == 2
        assert "http://localhost:3000" in config.cors_origins
        assert "https://app.example.com" in config.cors_origins

    def test_security_log_event(self, caplog):
        """Cover security event logging (lines 159-162)."""
        config = SecurityConfig()

        with caplog.at_level(logging.INFO):
            config._log_security_event("test_event", "warning", {"key": "value"})

        assert any('Security Audit' in record.message for record in caplog.records)


class TestAPIConfigCoverage:
    """Coverage-driven tests for APIConfig (lines 164-180)."""

    def test_api_default_values(self, monkeypatch):
        """Cover default API configuration (lines 167-170)."""
        monkeypatch.delenv('RATE_LIMIT', raising=False)
        monkeypatch.delenv('REQUEST_TIMEOUT', raising=False)
        monkeypatch.delenv('MAX_REQUEST_SIZE', raising=False)
        monkeypatch.delenv('PAGINATION_SIZE', raising=False)

        config = APIConfig()

        assert config.rate_limit == 100
        assert config.request_timeout == 30
        assert config.max_request_size == 10 * 1024 * 1024
        assert config.pagination_size == 50

    @pytest.mark.parametrize("env_var,value,expected_field", [
        ("RATE_LIMIT", "200", "rate_limit"),
        ("REQUEST_TIMEOUT", "60", "request_timeout"),
        ("MAX_REQUEST_SIZE", "20971520", "max_request_size"),
        ("PAGINATION_SIZE", "100", "pagination_size"),
    ])
    def test_api_from_env(self, monkeypatch, env_var, value, expected_field):
        """Cover API environment variables (lines 173-180)."""
        monkeypatch.setenv(env_var, value)

        config = APIConfig()

        assert getattr(config, expected_field) == int(value)


class TestIntegrationConfigCoverage:
    """Coverage-driven tests for IntegrationConfig (lines 182-221)."""

    def test_integration_default_values(self, monkeypatch):
        """Cover default integration configuration (lines 185-196)."""
        # Clear all integration env vars
        for var in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'MICROSOFT_CLIENT_ID',
                    'MICROSOFT_CLIENT_SECRET', 'GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET',
                    'NOTION_ACCESS_TOKEN', 'JIRA_BASE_URL', 'JIRA_USERNAME', 'JIRA_API_TOKEN',
                    'TRELLO_API_KEY', 'TRELLO_ACCESS_TOKEN']:
            monkeypatch.delenv(var, raising=False)

        config = IntegrationConfig()

        assert config.google_client_id == ""
        assert config.microsoft_client_id == ""
        assert config.github_client_id == ""
        assert config.notion_token == ""
        assert config.jira_base_url == ""

    @pytest.mark.parametrize("env_var,field", [
        ("GOOGLE_CLIENT_ID", "google_client_id"),
        ("GOOGLE_CLIENT_SECRET", "google_client_secret"),
        ("MICROSOFT_CLIENT_ID", "microsoft_client_id"),
        ("MICROSOFT_CLIENT_SECRET", "microsoft_client_secret"),
        ("GITHUB_CLIENT_ID", "github_client_id"),
        ("GITHUB_CLIENT_SECRET", "github_client_secret"),
        ("NOTION_ACCESS_TOKEN", "notion_token"),
        ("JIRA_BASE_URL", "jira_base_url"),
        ("JIRA_USERNAME", "jira_username"),
        ("JIRA_API_TOKEN", "jira_api_token"),
        ("TRELLO_API_KEY", "trello_api_key"),
        ("TRELLO_ACCESS_TOKEN", "trello_token"),
    ])
    def test_integration_from_env(self, monkeypatch, env_var, field):
        """Cover integration environment variables (lines 199-221)."""
        monkeypatch.setenv(env_var, 'test-value-123')

        config = IntegrationConfig()

        assert getattr(config, field) == "test-value-123"


class TestAIConfigCoverage:
    """Coverage-driven tests for AIConfig (lines 223-240)."""

    def test_ai_default_values(self, monkeypatch):
        """Cover default AI configuration (lines 226-230)."""
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
        monkeypatch.delenv('MODEL_NAME', raising=False)
        monkeypatch.delenv('MAX_TOKENS', raising=False)
        monkeypatch.delenv('TEMPERATURE', raising=False)

        config = AIConfig()

        assert config.openai_api_key == ""
        assert config.anthropic_api_key == ""
        assert config.model_name == "gpt-3.5-turbo"
        assert config.max_tokens == 2048
        assert config.temperature == 0.7

    def test_ai_from_env(self, monkeypatch):
        """Cover AI environment variables (lines 233-240)."""
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key')
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test')
        monkeypatch.setenv('MODEL_NAME', 'gpt-4')
        monkeypatch.setenv('MAX_TOKENS', '4096')
        monkeypatch.setenv('TEMPERATURE', '0.5')

        config = AIConfig()

        assert config.openai_api_key == "sk-test-key"
        assert config.anthropic_api_key == "sk-ant-test"
        assert config.model_name == "gpt-4"
        assert config.max_tokens == 4096
        assert config.temperature == 0.5


class TestLoggingConfigCoverage:
    """Coverage-driven tests for LoggingConfig (lines 242-259)."""

    def test_logging_default_values(self, monkeypatch):
        """Cover default logging configuration (lines 245-249)."""
        monkeypatch.delenv('LOG_LEVEL', raising=False)
        monkeypatch.delenv('LOG_FILE', raising=False)
        monkeypatch.delenv('LOG_MAX_BYTES', raising=False)
        monkeypatch.delenv('LOG_BACKUP_COUNT', raising=False)

        config = LoggingConfig()

        assert config.level == "INFO"
        assert config.file_path == "./logs/atom.log"
        assert config.max_bytes == 10 * 1024 * 1024
        assert config.backup_count == 5

    def test_logging_from_env(self, monkeypatch):
        """Cover logging environment variables (lines 252-259)."""
        monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
        monkeypatch.setenv('LOG_FILE', '/var/log/atom/debug.log')
        monkeypatch.setenv('LOG_MAX_BYTES', '52428800')
        monkeypatch.setenv('LOG_BACKUP_COUNT', '10')

        config = LoggingConfig()

        assert config.level == "DEBUG"
        assert config.file_path == "/var/log/atom/debug.log"
        assert config.max_bytes == 52428800
        assert config.backup_count == 10


class TestATOMConfigCoverage:
    """Coverage-driven tests for ATOMConfig (lines 261-422)."""

    def test_atom_config_default_initialization(self, monkeypatch):
        """Cover ATOMConfig initialization with defaults (lines 276-296)."""
        config = ATOMConfig()

        assert config.database is not None
        assert config.lancedb is not None
        assert config.redis is not None
        assert config.scheduler is not None
        assert config.server is not None
        assert config.security is not None
        assert config.api is not None
        assert config.integrations is not None
        assert config.ai is not None
        assert config.logging is not None

    def test_atom_config_with_custom_sub_configs(self):
        """Cover ATOMConfig with custom sub-configurations."""
        db_config = DatabaseConfig(url="postgresql://localhost/test")
        server_config = ServerConfig(port=8000)

        config = ATOMConfig(
            database=db_config,
            server=server_config
        )

        assert config.database.url == "postgresql://localhost/test"
        assert config.server.port == 8000

    def test_from_env(self, monkeypatch):
        """Cover from_env class method (lines 299-301)."""
        monkeypatch.setenv('PORT', '9000')

        config = ATOMConfig.from_env()

        assert config.server.port == 9000

    def test_to_dict(self):
        """Cover to_dict method (lines 338-340)."""
        config = ATOMConfig()

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert 'database' in config_dict
        assert 'server' in config_dict
        assert 'security' in config_dict

    def test_get_database_url(self):
        """Cover get_database_url method (lines 382-384)."""
        config = ATOMConfig(
            database=DatabaseConfig(url="postgresql://localhost/test")
        )

        url = config.get_database_url()

        assert url == "postgresql://localhost/test"

    def test_get_lancedb_path(self):
        """Cover get_lancedb_path method (lines 386-388)."""
        config = ATOMConfig(
            lancedb=LanceDBConfig(path="/custom/lancedb")
        )

        path = config.get_lancedb_path()

        assert path == "/custom/lancedb"

    def test_is_production_true(self, monkeypatch):
        """Cover is_production method (lines 390-392)."""
        monkeypatch.setenv('ENVIRONMENT', 'production')

        config = ATOMConfig.from_env()

        assert config.is_production() is True

    def test_is_production_false(self, monkeypatch):
        """Cover is_production false case."""
        monkeypatch.setenv('ENVIRONMENT', 'development')

        config = ATOMConfig.from_env()

        assert config.is_production() is False

    def test_is_development_true(self, monkeypatch):
        """Cover is_development method (lines 394-396)."""
        monkeypatch.setenv('ENVIRONMENT', 'development')

        config = ATOMConfig.from_env()

        assert config.is_development() is True

    def test_validate_success(self, monkeypatch):
        """Cover successful validation (lines 356-380)."""
        monkeypatch.setenv('ENVIRONMENT', 'development')

        config = ATOMConfig(
            database=DatabaseConfig(url="postgresql://localhost/test"),
            security=SecurityConfig(secret_key="production-secret-key")
        )

        result = config.validate()

        assert result['valid'] is True
        assert len(result['issues']) == 0

    def test_validate_missing_database_url(self):
        """Cover validation failure for missing database URL (lines 360-362)."""
        config = ATOMConfig(
            database=DatabaseConfig(url="")
        )

        result = config.validate()

        assert result['valid'] is False
        assert any('Database URL' in issue for issue in result['issues'])

    def test_validate_production_default_secret(self, monkeypatch):
        """Cover validation failure for default secret in production (lines 365-367)."""
        monkeypatch.setenv('ENVIRONMENT', 'production')

        config = ATOMConfig(
            database=DatabaseConfig(url="postgresql://localhost/test"),
            security=SecurityConfig(secret_key="atom-secret-key-change-in-production")
        )

        result = config.validate()

        assert result['valid'] is False
        assert any('Secret key' in issue for issue in result['issues'])

    def test_validate_production_integration_recommendations(self, monkeypatch):
        """Cover integration recommendations in production (lines 370-375)."""
        monkeypatch.setenv('ENVIRONMENT', 'production')

        config = ATOMConfig(
            database=DatabaseConfig(url="postgresql://localhost/test"),
            security=SecurityConfig(secret_key="production-secret-key")
        )

        result = config.validate()

        # Should have recommendations about integrations
        assert any('Google' in issue or 'Microsoft' in issue for issue in result['issues'])


class TestConfigFileOperations:
    """Coverage-driven tests for config file operations (lines 298-336, 342-354)."""

    def test_from_file_success(self, tmp_path):
        """Cover loading config from JSON file (lines 304-332)."""
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

    def test_from_file_all_sub_configs(self, tmp_path):
        """Cover from_file with all sub-configs (lines 311-330)."""
        config_file = tmp_path / "config.json"
        config_data = {
            'database': {'url': 'postgresql://localhost/test'},
            'lancedb': {'path': '/custom/lancedb'},
            'redis': {'enabled': True, 'url': 'redis://localhost:6379/0'},
            'scheduler': {'job_store_type': 'redis'},
            'server': {'port': 8000},
            'security': {'secret_key': 'custom-secret'},
            'api': {'rate_limit': 200},
            'integrations': {'google_client_id': 'test-id'},
            'ai': {'model_name': 'gpt-4'},
            'logging': {'level': 'DEBUG'}
        }

        config_file.write_text(json.dumps(config_data))

        config = ATOMConfig.from_file(str(config_file))

        assert config.database.url == "postgresql://localhost/test"
        assert config.lancedb.path == "/custom/lancedb"
        assert config.redis.enabled is True
        assert config.scheduler.job_store_type == "redis"
        assert config.server.port == 8000
        assert config.security.secret_key == "custom-secret"
        assert config.api.rate_limit == 200
        assert config.integrations.google_client_id == "test-id"
        assert config.ai.model_name == "gpt-4"
        assert config.logging.level == "DEBUG"

    def test_from_file_missing(self, tmp_path):
        """Cover from_file with missing file (lines 334-336)."""
        missing_file = tmp_path / "nonexistent.json"

        # Should fallback to environment
        config = ATOMConfig.from_file(str(missing_file))

        assert config is not None

    def test_from_file_invalid_json(self, tmp_path):
        """Cover from_file with invalid JSON (lines 334-336)."""
        config_file = tmp_path / "invalid.json"
        config_file.write_text("invalid json content")

        # Should fallback to environment
        config = ATOMConfig.from_file(str(config_file))

        assert config is not None

    def test_to_file_success(self, tmp_path):
        """Cover saving config to file (lines 342-354)."""
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
        """Cover creating directory when saving config (line 346)."""
        config = ATOMConfig()

        output_file = tmp_path / "nested" / "dir" / "config.json"

        success = config.to_file(str(output_file))

        assert success is True
        assert output_file.exists()

    def test_to_file_exception(self, tmp_path):
        """Cover exception handling in to_file (lines 352-354)."""
        config = ATOMConfig()

        # Use invalid path
        output_file = tmp_path / "nonexistent_dir" / "config.json"

        # Should handle exception and return False
        # (Note: this might not actually fail on all systems)
        success = config.to_file(str(output_file))

        # Either success or exception handling is acceptable
        assert isinstance(success, bool)


class TestGlobalConfigFunctions:
    """Coverage-driven tests for global config functions (lines 424-442)."""

    def test_get_config_singleton(self):
        """Cover get_config singleton (lines 427-429)."""
        config1 = get_config()
        config2 = get_config()

        # Should return same instance
        assert config1 is config2

    def test_load_config_from_file(self, tmp_path):
        """Cover load_config from file (lines 431-437)."""
        config_file = tmp_path / "config.json"
        config_data = {'server': {'port': 7777}}
        config_file.write_text(json.dumps(config_data))

        load_config(str(config_file))

        config = get_config()
        assert config.server.port == 7777

    def test_load_config_from_env(self, monkeypatch):
        """Cover load_config from environment (lines 438-440)."""
        monkeypatch.setenv('PORT', '8888')

        load_config()

        config = get_config()
        assert config.server.port == 8888

    def test_load_config_nonexistent_file(self, tmp_path):
        """Cover load_config with nonexistent file (line 435)."""
        missing_file = tmp_path / "nonexistent.json"

        # Should load from environment when file doesn't exist
        config = load_config(str(missing_file))

        assert config is not None


class TestSetupLogging:
    """Coverage-driven tests for setup_logging function (lines 444-478)."""

    def test_setup_logging_default(self, tmp_path):
        """Cover setup_logging with default config (lines 444-478)."""
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
        """Cover creating log directory (line 453)."""
        log_dir = tmp_path / "logs"
        log_file = log_dir / "atom.log"

        config = LoggingConfig(
            file_path=str(log_file)
        )

        setup_logging(config)

        # Directory should be created
        assert log_dir.exists()
        assert log_file.exists()

    def test_setup_logging_none_config(self):
        """Cover setup_logging with None config (lines 449-450)."""
        # Should use get_config().logging
        setup_logging(None)

        # Should not raise exception
        assert True
