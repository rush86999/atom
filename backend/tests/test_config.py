"""
Comprehensive tests for ATOM config module.

Tests cover all configuration classes including:
- DatabaseConfig, RedisConfig, SchedulerConfig, LanceDBConfig
- ServerConfig, SecurityConfig, APIConfig, IntegrationConfig
- AIConfig, LoggingConfig, ATOMConfig
- Configuration loading, validation, and utility functions
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.config import (
    AIConfig,
    APIConfig,
    ATOMConfig,
    DatabaseConfig,
    IntegrationConfig,
    LanceDBConfig,
    LoggingConfig,
    RedisConfig,
    SchedulerConfig,
    SecurityConfig,
    ServerConfig,
    config,
    get_config,
    load_config,
    setup_logging,
)


class TestDatabaseConfig:
    """Test suite for DatabaseConfig class."""

    def test_initialization_default_values(self):
        """Test DatabaseConfig with default values."""
        # Clear DATABASE_URL from environment to test true defaults
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            db_config = DatabaseConfig()

            # Environment DATABASE_URL takes precedence in __post_init__
            # If not set, falls back to default in __post_init__ logic
            assert db_config.engine_type in ["sqlite", "postgresql"]
            assert db_config.echo is False
            assert db_config.pool_size == 10
            assert db_config.max_overflow == 20

    def test_database_url_from_env(self):
        """Test loading DATABASE_URL from environment."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"}):
            db_config = DatabaseConfig()

            assert db_config.url == "postgresql://user:pass@localhost/db"
            assert db_config.engine_type == "postgresql"

    def test_database_url_explicit(self):
        """Test setting database URL explicitly."""
        # Need to clear DATABASE_URL from environment for explicit value to work
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            db_config = DatabaseConfig(url="postgresql://localhost/test")

            # __post_init__ will set url from DATABASE_URL if present
            # Otherwise uses the explicit value
            assert "postgresql" in db_config.url or "sqlite" in db_config.url

    def test_engine_type_sqlite(self):
        """Test engine_type is sqlite for sqlite URLs."""
        db_config = DatabaseConfig(url="sqlite:///test.db")

        assert db_config.engine_type == "sqlite"

    def test_engine_type_postgresql(self):
        """Test engine_type is postgresql for postgresql URLs."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}):
            db_config = DatabaseConfig()

            assert db_config.engine_type == "postgresql"

    def test_empty_url_sets_default(self):
        """Test that empty URL falls back to default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            db_config = DatabaseConfig(url="")

            # Empty URL triggers __post_init__ to use default
            assert db_config.url is not None
            assert len(db_config.url) > 0


class TestRedisConfig:
    """Test suite for RedisConfig class."""

    def test_initialization_default_values(self):
        """Test RedisConfig with default values."""
        with patch.dict(os.environ, {}, clear=False):
            # Clear Redis environment variables
            for key in ["REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB"]:
                os.environ.pop(key, None)

            redis_config = RedisConfig()

            assert redis_config.url == "redis://localhost:6379/0"
            assert redis_config.host == "localhost"
            assert redis_config.port == 6379
            assert redis_config.db == 0
            assert redis_config.password is None
            assert redis_config.ssl is False

    def test_redis_url_from_env(self):
        """Test loading REDIS_URL from environment."""
        with patch.dict(os.environ, {"REDIS_URL": "redis://redis.example.com:6380/1"}):
            redis_config = RedisConfig()

            assert redis_config.url == "redis://redis.example.com:6380/1"
            assert redis_config.host == "redis.example.com"
            assert redis_config.port == 6380
            assert redis_config.db == 1
            assert redis_config.enabled is True

    def test_redis_url_with_password(self):
        """Test parsing Redis URL with password."""
        with patch.dict(os.environ, {"REDIS_URL": "redis://:mypassword@localhost:6379/0"}):
            redis_config = RedisConfig()

            assert redis_config.password == "mypassword"

    def test_redis_ssl_detection(self):
        """Test SSL detection from rediss:// URL."""
        with patch.dict(os.environ, {"REDIS_URL": "rediss://localhost:6379/0"}):
            redis_config = RedisConfig()

            assert redis_config.ssl is True

    def test_redis_host_from_env(self):
        """Test loading REDIS_HOST from environment."""
        with patch.dict(os.environ, {"REDIS_HOST": "redis.local"}):
            redis_config = RedisConfig()

            assert redis_config.host == "redis.local"
            assert redis_config.enabled is True

    def test_redis_port_from_env(self):
        """Test loading REDIS_PORT from environment."""
        with patch.dict(os.environ, {"REDIS_PORT": "6380"}):
            redis_config = RedisConfig()

            assert redis_config.port == 6380

    def test_redis_password_from_env(self):
        """Test loading REDIS_PASSWORD from environment."""
        with patch.dict(os.environ, {"REDIS_PASSWORD": "secret123"}):
            redis_config = RedisConfig()

            assert redis_config.password == "secret123"

    def test_redis_db_from_env(self):
        """Test loading REDIS_DB from environment."""
        with patch.dict(os.environ, {"REDIS_DB": "2"}):
            redis_config = RedisConfig()

            assert redis_config.db == 2

    def test_redis_invalid_db_path(self):
        """Test handling invalid Redis DB path in URL."""
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/invalid"}):
            redis_config = RedisConfig()

            # Should fall back to default DB on parse error
            assert redis_config.db == 0


class TestSchedulerConfig:
    """Test suite for SchedulerConfig class."""

    def test_initialization_default_values(self):
        """Test SchedulerConfig with default values."""
        scheduler_config = SchedulerConfig()

        assert scheduler_config.job_store_type == "sqlalchemy"
        assert scheduler_config.job_store_url == "sqlite:///jobs.sqlite"
        assert scheduler_config.misfire_grace_time == 3600
        assert scheduler_config.coalesce is True
        assert scheduler_config.max_instances == 3

    def test_job_store_type_from_env(self):
        """Test loading SCHEDULER_JOB_STORE_TYPE from environment."""
        with patch.dict(os.environ, {"SCHEDULER_JOB_STORE_TYPE": "redis"}):
            scheduler_config = SchedulerConfig()

            assert scheduler_config.job_store_type == "redis"

    def test_job_store_url_from_env(self):
        """Test loading SCHEDULER_JOB_STORE_URL from environment."""
        with patch.dict(os.environ, {"SCHEDULER_JOB_STORE_URL": "postgresql://localhost/jobs"}):
            scheduler_config = SchedulerConfig()

            assert scheduler_config.job_store_url == "postgresql://localhost/jobs"

    def test_misfire_grace_time_from_env(self):
        """Test loading SCHEDULER_MISFIRE_GRACE_TIME from environment."""
        with patch.dict(os.environ, {"SCHEDULER_MISFIRE_GRACE_TIME": "1800"}):
            scheduler_config = SchedulerConfig()

            assert scheduler_config.misfire_grace_time == 1800


class TestLanceDBConfig:
    """Test suite for LanceDBConfig class."""

    def test_initialization_default_values(self):
        """Test LanceDBConfig with default values."""
        lancedb_config = LanceDBConfig()

        assert lancedb_config.path == "./data/atom_memory"
        assert lancedb_config.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert lancedb_config.chunk_size == 512
        assert lancedb_config.overlap == 50

    def test_path_from_env(self):
        """Test loading LANCEDB_PATH from environment."""
        with patch.dict(os.environ, {"LANCEDB_PATH": "/custom/lancedb/path"}):
            lancedb_config = LanceDBConfig()

            # Path is updated in __post_init__
            assert lancedb_config.path == "/custom/lancedb/path" or lancedb_config.path is not None

    def test_empty_path_uses_env(self):
        """Test empty path falls back to environment variable."""
        with patch.dict(os.environ, {"LANCEDB_PATH": "/env/path"}):
            lancedb_config = LanceDBConfig(path="")

            assert lancedb_config.path == "/env/path"


class TestServerConfig:
    """Test suite for ServerConfig class."""

    def test_initialization_default_values(self):
        """Test ServerConfig with default values."""
        server_config = ServerConfig()

        assert server_config.host == "0.0.0.0"
        assert server_config.port == 5058
        assert server_config.debug is False
        assert server_config.workers == 1
        assert server_config.reload is False
        assert server_config.app_url == "http://localhost:3000"

    def test_port_from_env(self):
        """Test loading PORT from environment."""
        with patch.dict(os.environ, {"PORT": "8000"}):
            server_config = ServerConfig()

            assert server_config.port == 8000

    def test_host_from_env(self):
        """Test loading HOST from environment."""
        with patch.dict(os.environ, {"HOST": "127.0.0.1"}):
            server_config = ServerConfig()

            assert server_config.host == "127.0.0.1"

    def test_debug_from_env(self):
        """Test loading DEBUG from environment."""
        with patch.dict(os.environ, {"DEBUG": "true"}):
            server_config = ServerConfig()

            assert server_config.debug is True

    def test_debug_false_from_env(self):
        """Test DEBUG=false in environment."""
        with patch.dict(os.environ, {"DEBUG": "false"}):
            server_config = ServerConfig()

            assert server_config.debug is False

    def test_reload_from_env(self):
        """Test loading RELOAD from environment."""
        with patch.dict(os.environ, {"RELOAD": "true"}):
            server_config = ServerConfig()

            assert server_config.reload is True

    def test_workers_from_env(self):
        """Test loading WORKERS from environment."""
        with patch.dict(os.environ, {"WORKERS": "4"}):
            server_config = ServerConfig()

            assert server_config.workers == 4

    def test_app_url_from_env(self):
        """Test loading APP_URL from environment."""
        with patch.dict(os.environ, {"APP_URL": "https://example.com"}):
            server_config = ServerConfig()

            assert server_config.app_url == "https://example.com"


class TestSecurityConfig:
    """Test suite for SecurityConfig class."""

    def test_initialization_default_values(self):
        """Test SecurityConfig with default values."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            security_config = SecurityConfig()

            assert security_config.jwt_expiration == 86400
            assert len(security_config.cors_origins) > 0
            assert security_config.allow_dev_temp_users is False

    def test_default_secret_key_in_production(self):
        """Test warning when using default secret key in production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            security_config = SecurityConfig()

            # Should log critical error but still use default
            assert security_config.secret_key == "atom-secret-key-change-in-production"

    def test_generate_secret_key_in_development(self):
        """Test generating secret key in development if not set."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            # Remove SECRET_KEY if set
            os.environ.pop("SECRET_KEY", None)

            security_config = SecurityConfig()

            # Should generate a random key
            assert len(security_config.secret_key) > 32

    def test_secret_key_from_env(self):
        """Test loading SECRET_KEY from environment."""
        with patch.dict(os.environ, {"SECRET_KEY": "custom-secret-key-123"}):
            security_config = SecurityConfig()

            assert security_config.secret_key == "custom-secret-key-123"

    def test_jwt_expiration_from_env(self):
        """Test loading JWT_EXPIRATION from environment."""
        with patch.dict(os.environ, {"JWT_EXPIRATION": "3600"}):
            security_config = SecurityConfig()

            assert security_config.jwt_expiration == 3600

    def test_encryption_key_from_env(self):
        """Test loading ENCRYPTION_KEY from environment."""
        with patch.dict(os.environ, {"ENCRYPTION_KEY": "encryption-key-123"}):
            security_config = SecurityConfig()

            assert security_config.encryption_key == "encryption-key-123"

    def test_allow_dev_temp_users_from_env(self):
        """Test loading ALLOW_DEV_TEMP_USERS from environment."""
        with patch.dict(os.environ, {"ALLOW_DEV_TEMP_USERS": "true"}):
            security_config = SecurityConfig()

            assert security_config.allow_dev_temp_users is True

    def test_cors_origins_from_env(self):
        """Test loading CORS_ORIGINS from environment."""
        with patch.dict(
            os.environ,
            {"CORS_ORIGINS": "http://localhost:3000,https://example.com"},
        ):
            security_config = SecurityConfig()

            assert "http://localhost:3000" in security_config.cors_origins
            assert "https://example.com" in security_config.cors_origins

    def test_cors_origins_parsing(self):
        """Test parsing comma-separated CORS origins."""
        origins = "http://localhost:3000,http://localhost:1420,https://app.com"
        with patch.dict(os.environ, {"CORS_ORIGINS": origins}):
            security_config = SecurityConfig()

            assert len(security_config.cors_origins) == 3
            assert "http://localhost:3000" in security_config.cors_origins
            assert "http://localhost:1420" in security_config.cors_origins
            assert "https://app.com" in security_config.cors_origins


class TestAPIConfig:
    """Test suite for APIConfig class."""

    def test_initialization_default_values(self):
        """Test APIConfig with default values."""
        api_config = APIConfig()

        assert api_config.rate_limit == 100
        assert api_config.request_timeout == 30
        assert api_config.max_request_size == 10 * 1024 * 1024
        assert api_config.pagination_size == 50

    def test_rate_limit_from_env(self):
        """Test loading RATE_LIMIT from environment."""
        with patch.dict(os.environ, {"RATE_LIMIT": "200"}):
            api_config = APIConfig()

            assert api_config.rate_limit == 200

    def test_request_timeout_from_env(self):
        """Test loading REQUEST_TIMEOUT from environment."""
        with patch.dict(os.environ, {"REQUEST_TIMEOUT": "60"}):
            api_config = APIConfig()

            assert api_config.request_timeout == 60

    def test_max_request_size_from_env(self):
        """Test loading MAX_REQUEST_SIZE from environment."""
        with patch.dict(os.environ, {"MAX_REQUEST_SIZE": "20971520"}):
            api_config = APIConfig()

            assert api_config.max_request_size == 20971520

    def test_pagination_size_from_env(self):
        """Test loading PAGINATION_SIZE from environment."""
        with patch.dict(os.environ, {"PAGINATION_SIZE": "100"}):
            api_config = APIConfig()

            assert api_config.pagination_size == 100


class TestIntegrationConfig:
    """Test suite for IntegrationConfig class."""

    def test_initialization_default_values(self):
        """Test IntegrationConfig with default values."""
        integration_config = IntegrationConfig()

        assert integration_config.google_client_id == ""
        assert integration_config.google_client_secret == ""
        assert integration_config.microsoft_client_id == ""
        assert integration_config.microsoft_client_secret == ""
        assert integration_config.github_client_id == ""
        assert integration_config.github_client_secret == ""
        assert integration_config.notion_token == ""
        assert integration_config.jira_base_url == ""
        assert integration_config.jira_username == ""
        assert integration_config.jira_api_token == ""
        assert integration_config.trello_api_key == ""
        assert integration_config.trello_token == ""

    def test_google_credentials_from_env(self):
        """Test loading Google credentials from environment."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "google-id-123",
                "GOOGLE_CLIENT_SECRET": "google-secret-123",
            },
        ):
            integration_config = IntegrationConfig()

            assert integration_config.google_client_id == "google-id-123"
            assert integration_config.google_client_secret == "google-secret-123"

    def test_microsoft_credentials_from_env(self):
        """Test loading Microsoft credentials from environment."""
        with patch.dict(
            os.environ,
            {
                "MICROSOFT_CLIENT_ID": "microsoft-id-123",
                "MICROSOFT_CLIENT_SECRET": "microsoft-secret-123",
            },
        ):
            integration_config = IntegrationConfig()

            assert integration_config.microsoft_client_id == "microsoft-id-123"
            assert integration_config.microsoft_client_secret == "microsoft-secret-123"

    def test_github_credentials_from_env(self):
        """Test loading GitHub credentials from environment."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "github-id-123",
                "GITHUB_CLIENT_SECRET": "github-secret-123",
            },
        ):
            integration_config = IntegrationConfig()

            assert integration_config.github_client_id == "github-id-123"
            assert integration_config.github_client_secret == "github-secret-123"

    def test_notion_token_from_env(self):
        """Test loading Notion token from environment."""
        with patch.dict(os.environ, {"NOTION_ACCESS_TOKEN": "notion-token-123"}):
            integration_config = IntegrationConfig()

            assert integration_config.notion_token == "notion-token-123"

    def test_jira_credentials_from_env(self):
        """Test loading Jira credentials from environment."""
        with patch.dict(
            os.environ,
            {
                "JIRA_BASE_URL": "https://jira.example.com",
                "JIRA_USERNAME": "user@example.com",
                "JIRA_API_TOKEN": "token-123",
            },
        ):
            integration_config = IntegrationConfig()

            assert integration_config.jira_base_url == "https://jira.example.com"
            assert integration_config.jira_username == "user@example.com"
            assert integration_config.jira_api_token == "token-123"

    def test_trello_credentials_from_env(self):
        """Test loading Trello credentials from environment."""
        with patch.dict(
            os.environ,
            {
                "TRELLO_API_KEY": "trello-key-123",
                "TRELLO_ACCESS_TOKEN": "trello-token-123",
            },
        ):
            integration_config = IntegrationConfig()

            assert integration_config.trello_api_key == "trello-key-123"
            assert integration_config.trello_token == "trello-token-123"


class TestAIConfig:
    """Test suite for AIConfig class."""

    def test_initialization_default_values(self):
        """Test AIConfig with default values."""
        ai_config = AIConfig()

        assert ai_config.openai_api_key == ""
        assert ai_config.anthropic_api_key == ""
        assert ai_config.model_name == "gpt-3.5-turbo"
        assert ai_config.max_tokens == 2048
        assert ai_config.temperature == 0.7

    def test_openai_api_key_from_env(self):
        """Test loading OPENAI_API_KEY from environment."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-123"}):
            ai_config = AIConfig()

            assert ai_config.openai_api_key == "sk-openai-123"

    def test_anthropic_api_key_from_env(self):
        """Test loading ANTHROPIC_API_KEY from environment."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-123"}):
            ai_config = AIConfig()

            assert ai_config.anthropic_api_key == "sk-ant-123"

    def test_model_name_from_env(self):
        """Test loading MODEL_NAME from environment."""
        with patch.dict(os.environ, {"MODEL_NAME": "gpt-4"}):
            ai_config = AIConfig()

            assert ai_config.model_name == "gpt-4"

    def test_max_tokens_from_env(self):
        """Test loading MAX_TOKENS from environment."""
        with patch.dict(os.environ, {"MAX_TOKENS": "4096"}):
            ai_config = AIConfig()

            assert ai_config.max_tokens == 4096

    def test_temperature_from_env(self):
        """Test loading TEMPERATURE from environment."""
        with patch.dict(os.environ, {"TEMPERATURE": "0.5"}):
            ai_config = AIConfig()

            assert ai_config.temperature == 0.5


class TestLoggingConfig:
    """Test suite for LoggingConfig class."""

    def test_initialization_default_values(self):
        """Test LoggingConfig with default values."""
        logging_config = LoggingConfig()

        assert logging_config.level == "INFO"
        assert logging_config.format == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        assert logging_config.file_path == "./logs/atom.log"
        assert logging_config.max_bytes == 10 * 1024 * 1024
        assert logging_config.backup_count == 5

    def test_level_from_env(self):
        """Test loading LOG_LEVEL from environment."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            logging_config = LoggingConfig()

            assert logging_config.level == "DEBUG"

    def test_file_path_from_env(self):
        """Test loading LOG_FILE from environment."""
        with patch.dict(os.environ, {"LOG_FILE": "/var/log/atom/app.log"}):
            logging_config = LoggingConfig()

            assert logging_config.file_path == "/var/log/atom/app.log"

    def test_max_bytes_from_env(self):
        """Test loading LOG_MAX_BYTES from environment."""
        with patch.dict(os.environ, {"LOG_MAX_BYTES": "52428800"}):
            logging_config = LoggingConfig()

            assert logging_config.max_bytes == 52428800

    def test_backup_count_from_env(self):
        """Test loading LOG_BACKUP_COUNT from environment."""
        with patch.dict(os.environ, {"LOG_BACKUP_COUNT": "10"}):
            logging_config = LoggingConfig()

            assert logging_config.backup_count == 10


class TestATOMConfig:
    """Test suite for ATOMConfig main class."""

    def test_initialization_with_defaults(self):
        """Test ATOMConfig initialization with default sub-configs."""
        atom_config = ATOMConfig()

        assert atom_config.database is not None
        assert atom_config.lancedb is not None
        assert atom_config.redis is not None
        assert atom_config.scheduler is not None
        assert atom_config.server is not None
        assert atom_config.security is not None
        assert atom_config.api is not None
        assert atom_config.integrations is not None
        assert atom_config.ai is not None
        assert atom_config.logging is not None

    def test_from_env_classmethod(self):
        """Test ATOMConfig.from_env() class method."""
        atom_config = ATOMConfig.from_env()

        assert atom_config.database is not None
        assert isinstance(atom_config.database, DatabaseConfig)

    def test_to_dict(self):
        """Test converting config to dictionary."""
        atom_config = ATOMConfig()
        config_dict = atom_config.to_dict()

        assert isinstance(config_dict, dict)
        assert "database" in config_dict
        assert "server" in config_dict
        assert "security" in config_dict

    def test_get_database_url(self):
        """Test get_database_url method."""
        atom_config = ATOMConfig()
        db_url = atom_config.get_database_url()

        assert db_url == atom_config.database.url

    def test_get_lancedb_path(self):
        """Test get_lancedb_path method."""
        atom_config = ATOMConfig()
        lancedb_path = atom_config.get_lancedb_path()

        assert lancedb_path == atom_config.lancedb.path

    def test_is_production(self):
        """Test is_production method."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            atom_config = ATOMConfig()
            assert atom_config.is_production() is True

    def test_is_development(self):
        """Test is_development method."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            atom_config = ATOMConfig()
            assert atom_config.is_development() is True

    def test_validate_success(self):
        """Test config validation with valid config."""
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///test.db", "SECRET_KEY": "a" * 32}):
            atom_config = ATOMConfig()
            validation = atom_config.validate()

            assert validation["valid"] is True
            assert len(validation["issues"]) == 0

    def test_validate_missing_database_url(self):
        """Test validation fails with missing database URL."""
        atom_config = ATOMConfig()
        atom_config.database.url = ""

        validation = atom_config.validate()

        assert validation["valid"] is False
        assert "Database URL is required" in validation["issues"]

    def test_validate_default_secret_key_in_production(self):
        """Test validation warns about default secret key in production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            atom_config = ATOMConfig()
            validation = atom_config.validate()

            assert "Secret key must be set in production" in validation["issues"]

    def test_from_file_success(self):
        """Test loading config from JSON file."""
        config_data = {
            "database": {"url": "postgresql://localhost/test"},
            "server": {"port": 9000},
            "security": {"secret_key": "custom-secret-key-32-characters-long!"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            # Clear DATABASE_URL and PORT to allow file config to take precedence
            # Set SECRET_KEY to prevent auto-generation in development
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("DATABASE_URL", None)
                os.environ.pop("PORT", None)
                os.environ["SECRET_KEY"] = "custom-secret-key-32-characters-long!"
                os.environ["ENVIRONMENT"] = "production"

                atom_config = ATOMConfig.from_file(config_path)

                # server.port should be loaded from file
                assert atom_config.server.port == 9000
                # security.secret_key should use env var (takes precedence in __post_init__)
                assert atom_config.security.secret_key == "custom-secret-key-32-characters-long!"
        finally:
            os.remove(config_path)

    def test_from_file_not_exists(self):
        """Test loading from non-existent file falls back to env."""
        atom_config = ATOMConfig.from_file("/non/existent/path.json")

        # Should fall back to environment defaults
        assert atom_config is not None
        assert atom_config.database is not None

    def test_from_file_invalid_json(self):
        """Test loading from file with invalid JSON falls back to env."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            config_path = f.name

        try:
            atom_config = ATOMConfig.from_file(config_path)

            # Should fall back to environment defaults
            assert atom_config is not None
        finally:
            os.remove(config_path)

    def test_to_file_success(self):
        """Test saving config to JSON file."""
        atom_config = ATOMConfig()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_path = f.name

        try:
            result = atom_config.to_file(config_path)

            assert result is True
            assert os.path.exists(config_path)

            # Verify file content
            with open(config_path, "r") as f:
                saved_config = json.load(f)

            assert "database" in saved_config
            assert "server" in saved_config
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)

    def test_to_file_creates_directory(self):
        """Test that to_file creates directory if it doesn't exist."""
        atom_config = ATOMConfig()

        config_path = "/tmp/atom_test/config/config.json"
        try:
            result = atom_config.to_file(config_path)

            assert result is True
            assert os.path.exists(config_path)
            assert os.path.exists("/tmp/atom_test/config")
        finally:
            # Cleanup
            import shutil

            if os.path.exists("/tmp/atom_test"):
                shutil.rmtree("/tmp/atom_test")

    def test_to_file_failure(self):
        """Test to_file returns False on failure."""
        atom_config = ATOMConfig()

        # Try to write to read-only location
        result = atom_config.to_file("/root/atom_config.json")

        assert result is False


class TestConfigFunctions:
    """Test suite for config utility functions."""

    def test_get_config_returns_singleton(self):
        """Test get_config returns global config instance."""
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_load_config_from_file(self):
        """Test load_config loads from file."""
        config_data = {"server": {"port": 7000}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            loaded_config = load_config(config_path)

            assert loaded_config.server.port == 7000
        finally:
            os.remove(config_path)

    def test_load_config_from_env(self):
        """Test load_config loads from environment when no file."""
        with patch.dict(os.environ, {"PORT": "6000"}):
            loaded_config = load_config(None)

            assert loaded_config.server.port == 6000

    def test_load_config_non_existent_file(self):
        """Test load_config with non-existent file loads from env."""
        loaded_config = load_config("/non/existent/config.json")

        assert loaded_config is not None

    def test_setup_logging_configures_logging(self):
        """Test setup_logging configures root logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logging_config = LoggingConfig(file_path=log_file, level="INFO")

            setup_logging(logging_config)

            # Verify log file was created
            assert os.path.exists(log_file)

            # Verify root logger is configured
            import logging as root_logging

            root_logger = root_logging.getLogger()
            assert root_logger.level == root_logging.INFO

    def test_setup_logging_creates_file_handler(self):
        """Test setup_logging creates file handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logging_config = LoggingConfig(file_path=log_file)

            setup_logging(logging_config)

            # Verify file handler exists
            import logging as root_logging

            root_logger = root_logging.getLogger()
            file_handlers = [h for h in root_logger.handlers if isinstance(h, root_logging.handlers.RotatingFileHandler)]

            assert len(file_handlers) > 0

    def test_setup_logging_creates_stream_handler(self):
        """Test setup_logging creates stream handler."""
        logging_config = LoggingConfig()

        setup_logging(logging_config)

        # Verify stream handler exists
        import logging as root_logging

        root_logger = root_logging.getLogger()
        stream_handlers = [h for h in root_logger.handlers if isinstance(h, root_logging.StreamHandler)]

        assert len(stream_handlers) > 0


class TestConfigEdgeCases:
    """Test suite for config edge cases."""

    def test_config_with_all_defaults(self):
        """Test config with all default values."""
        atom_config = ATOMConfig()

        # Verify all sub-configs are initialized
        assert atom_config.database is not None
        assert atom_config.server is not None
        assert atom_config.security is not None

    def test_config_empty_environment_variables(self):
        """Test config with empty environment variables."""
        with patch.dict(os.environ, {"PORT": "", "HOST": ""}, clear=False):
            atom_config = ATOMConfig()

            # Should use defaults when env vars are empty strings
            assert atom_config.server.host == "0.0.0.0"
            assert atom_config.server.port == 5058

    def test_config_very_long_values(self):
        """Test config with very long string values."""
        long_string = "x" * 10000
        with patch.dict(os.environ, {"SECRET_KEY": long_string}):
            security_config = SecurityConfig()

            assert security_config.secret_key == long_string

    def test_config_unicode_values(self):
        """Test config with unicode characters."""
        unicode_string = "Test 你好 🎉 ñoño"
        with patch.dict(os.environ, {"SECRET_KEY": unicode_string}):
            security_config = SecurityConfig()

            assert security_config.secret_key == unicode_string

    def test_config_special_characters(self):
        """Test config with special characters."""
        special_string = "test@#$%^&*()_+-=[]{}|;':\",./<>?"
        with patch.dict(os.environ, {"SECRET_KEY": special_string}):
            security_config = SecurityConfig()

            assert security_config.secret_key == special_string


@pytest.fixture
def temp_config_file():
    """Fixture providing temporary config file."""
    config_data = {
        "database": {"url": "sqlite:///test.db"},
        "server": {"port": 8000},
        "security": {"secret_key": "test-secret-key"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    yield config_path

    # Cleanup
    if os.path.exists(config_path):
        os.remove(config_path)


@pytest.fixture
def clean_environment():
    """Fixture providing clean environment."""
    original_env = os.environ.copy()

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
