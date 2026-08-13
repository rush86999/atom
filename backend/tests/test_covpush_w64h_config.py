"""
Coverage wave 64h — core/config.py (standalone, function-level, TDD).

Full contract coverage of every dataclass config:
- DatabaseConfig / RedisConfig / SchedulerConfig / LanceDBConfig
- ServerConfig / SecurityConfig (incl. production fail-closed key rotation)
- APIConfig / IntegrationConfig / AIConfig / LoggingConfig
- ATOMConfig (from_env / from_file / to_dict / to_file / validate / getters)
- get_config / load_config / setup_logging
- MarketplaceConfig (env loading, validate, is_configured)

All tests are env-driven via monkeypatch; no network, no real DB writes, no
LLM spend. The module-level global `config` and the root logger are restored
after tests that mutate them.
"""

import json
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import core.config as cfg


@pytest.fixture(autouse=True)
def _restore_config_global():
    saved = cfg.config
    yield
    cfg.config = saved


@pytest.fixture(autouse=True)
def _restore_root_logger():
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield
    root.handlers.clear()
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)


# ===========================================================================
# DatabaseConfig
# ===========================================================================


class TestDatabaseConfig:
    def test_defaults_no_env(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        c = cfg.DatabaseConfig()
        assert c.url == "sqlite:///atom_data.db"
        assert c.echo is False
        assert c.pool_size == 10
        assert c.max_overflow == 20
        assert c.engine_type == "sqlite"

    def test_env_url_postgres(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
        c = cfg.DatabaseConfig()
        assert c.url == "postgresql://u:p@h:5432/db"
        assert c.engine_type == "postgresql"

    def test_env_url_sqlite(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./dev.db")
        c = cfg.DatabaseConfig()
        assert c.engine_type == "sqlite"

    def test_empty_url_and_no_env_uses_default(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        c = cfg.DatabaseConfig(url="")
        assert c.url == "sqlite:///atom_data.db"

    def test_explicit_url_kept_when_no_env(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        c = cfg.DatabaseConfig(url="postgresql://custom:5432/x")
        assert c.url == "postgresql://custom:5432/x"
        assert c.engine_type == "sqlite"  # no postgres prefix on the env var


# ===========================================================================
# RedisConfig
# ===========================================================================


class TestRedisConfig:
    def test_defaults_no_env(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("REDIS_DB", raising=False)
        c = cfg.RedisConfig()
        # The default URL carries a scheme, so __post_init__ marks it enabled.
        assert c.enabled is True
        assert c.url == "redis://localhost:6379/0"
        assert c.host == "localhost"
        assert c.port == 6379
        assert c.db == 0
        assert c.password is None
        assert c.ssl is False

    def test_url_parsing_full(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://:secret@myhost:6380/3")
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("REDIS_DB", raising=False)
        c = cfg.RedisConfig()
        assert c.enabled is True
        assert c.host == "myhost"
        assert c.port == 6380
        assert c.password == "secret"
        assert c.db == 3
        assert c.ssl is False

    def test_rediss_scheme_enables_ssl(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "rediss://h:6379/0")
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("REDIS_DB", raising=False)
        c = cfg.RedisConfig()
        assert c.ssl is True
        assert c.enabled is True

    def test_invalid_db_path_value_error(self, monkeypatch, caplog):
        monkeypatch.setenv("REDIS_URL", "redis://h:6379/not-a-number")
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("REDIS_DB", raising=False)
        with caplog.at_level(logging.WARNING, logger="core.config"):
            c = cfg.RedisConfig()
        assert c.db == 0
        assert any("Invalid Redis DB path" in r.message for r in caplog.records)

    def test_parse_exception_keeps_defaults(self, monkeypatch, caplog):
        monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("REDIS_DB", raising=False)

        def boom(*a, **k):
            raise RuntimeError("parse exploded")

        with patch("urllib.parse.urlparse", boom):
            with caplog.at_level(logging.WARNING, logger="core.config"):
                c = cfg.RedisConfig()
        assert c.host == "localhost"
        assert c.port == 6379
        assert any("Failed to parse Redis URL" in r.message for r in caplog.records)

    def test_no_scheme_skips_parsing(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "localhost:6379")
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("REDIS_DB", raising=False)
        c = cfg.RedisConfig()
        assert c.enabled is False  # no '://' -> not enabled
        assert c.host == "localhost"

    def test_individual_env_overrides(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
        monkeypatch.setenv("REDIS_HOST", "override-host")
        monkeypatch.setenv("REDIS_PORT", "7000")
        monkeypatch.setenv("REDIS_PASSWORD", "pw")
        monkeypatch.setenv("REDIS_DB", "9")
        c = cfg.RedisConfig()
        assert c.enabled is True
        assert c.host == "override-host"
        assert c.port == 7000
        assert c.password == "pw"
        assert c.db == 9


# ===========================================================================
# SchedulerConfig
# ===========================================================================


class TestSchedulerConfig:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("SCHEDULER_JOB_STORE_TYPE", raising=False)
        monkeypatch.delenv("SCHEDULER_JOB_STORE_URL", raising=False)
        monkeypatch.delenv("SCHEDULER_MISFIRE_GRACE_TIME", raising=False)
        c = cfg.SchedulerConfig()
        assert c.job_store_type == "sqlalchemy"
        assert c.job_store_url == "sqlite:///jobs.sqlite"
        assert c.misfire_grace_time == 3600
        assert c.coalesce is True
        assert c.max_instances == 3

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("SCHEDULER_JOB_STORE_TYPE", "redis")
        monkeypatch.setenv("SCHEDULER_JOB_STORE_URL", "redis://localhost:6379/1")
        monkeypatch.setenv("SCHEDULER_MISFIRE_GRACE_TIME", "120")
        c = cfg.SchedulerConfig()
        assert c.job_store_type == "redis"
        assert c.job_store_url == "redis://localhost:6379/1"
        assert c.misfire_grace_time == 120


# ===========================================================================
# LanceDBConfig
# ===========================================================================


class TestLanceDBConfig:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("LANCEDB_PATH", raising=False)
        c = cfg.LanceDBConfig()
        assert c.path == "./data/atom_memory"
        assert c.chunk_size == 512
        assert c.overlap == 50

    def test_empty_path_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("LANCEDB_PATH", "/custom/lancedb")
        c = cfg.LanceDBConfig(path="")
        assert c.path == "/custom/lancedb"

    def test_env_path_ignored_when_path_set(self, monkeypatch):
        """LANCEDB_PATH is only consulted when the path field is empty; a
        non-empty default path wins."""
        monkeypatch.setenv("LANCEDB_PATH", "/custom/lancedb")
        c = cfg.LanceDBConfig()
        assert c.path == "./data/atom_memory"

    def test_non_empty_path_kept(self, monkeypatch):
        monkeypatch.delenv("LANCEDB_PATH", raising=False)
        c = cfg.LanceDBConfig(path="./data/other")
        assert c.path == "./data/other"


# ===========================================================================
# ServerConfig
# ===========================================================================


class TestServerConfig:
    def test_defaults(self, monkeypatch):
        for var in ("PORT", "HOST", "DEBUG", "RELOAD", "WORKERS", "APP_URL"):
            monkeypatch.delenv(var, raising=False)
        c = cfg.ServerConfig()
        assert c.host == "0.0.0.0"
        assert c.port == 5058
        assert c.debug is False
        assert c.workers == 1
        assert c.reload is False
        assert c.app_url == "http://localhost:3000"

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("HOST", "127.0.0.1")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("RELOAD", "true")
        monkeypatch.setenv("WORKERS", "4")
        monkeypatch.setenv("APP_URL", "https://app.example.com")
        c = cfg.ServerConfig()
        assert c.port == 9000
        assert c.host == "127.0.0.1"
        assert c.debug is True
        assert c.reload is True
        assert c.workers == 4
        assert c.app_url == "https://app.example.com"

    def test_debug_false_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "TRUE")
        monkeypatch.delenv("RELOAD", raising=False)
        c = cfg.ServerConfig()
        assert c.debug is True

    def test_debug_not_true_stays_false(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "1")
        monkeypatch.delenv("RELOAD", raising=False)
        c = cfg.ServerConfig()
        assert c.debug is False


# ===========================================================================
# SecurityConfig
# ===========================================================================


class TestSecurityConfig:
    def test_development_no_secret_generates_key(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        c = cfg.SecurityConfig()
        assert c.secret_key is not None
        assert len(c.secret_key) >= 32

    def test_development_secret_from_env(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("SECRET_KEY", "env-provided-secret")
        c = cfg.SecurityConfig()
        assert c.secret_key == "env-provided-secret"

    def test_production_default_key_replaced(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        c = cfg.SecurityConfig(secret_key="atom-secret-key-change-in-production")
        assert c.secret_key != "atom-secret-key-change-in-production"
        assert len(c.secret_key) == 43  # token_urlsafe(32)

    def test_production_missing_env_key_replaced(self, monkeypatch):
        """Production + secret_key non-default BUT no SECRET_KEY env → the key
        is still replaced (the `or not os.getenv('SECRET_KEY')` clause)."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        c = cfg.SecurityConfig(secret_key="custom-key")
        assert c.secret_key != "custom-key"

    def test_production_with_env_key_kept(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("SECRET_KEY", "prod-stable-key")
        c = cfg.SecurityConfig(secret_key="atom-secret-key-change-in-production")
        assert c.secret_key == "prod-stable-key"

    def test_other_environment_keeps_passed_key(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        c = cfg.SecurityConfig(secret_key="staging-key")
        assert c.secret_key == "staging-key"

    def test_jwt_expiration_env(self, monkeypatch):
        monkeypatch.setenv("JWT_EXPIRATION", "3600")
        c = cfg.SecurityConfig()
        assert c.jwt_expiration == 3600

    def test_encryption_key_env(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", "enc-key-123")
        c = cfg.SecurityConfig()
        assert c.encryption_key == "enc-key-123"

    def test_allow_dev_temp_users(self, monkeypatch):
        monkeypatch.setenv("ALLOW_DEV_TEMP_USERS", "true")
        c = cfg.SecurityConfig()
        assert c.allow_dev_temp_users is True
        monkeypatch.setenv("ALLOW_DEV_TEMP_USERS", "false")
        assert cfg.SecurityConfig().allow_dev_temp_users is False

    def test_cors_origins_default(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        c = cfg.SecurityConfig()
        assert c.cors_origins == ["http://localhost:3000", "http://localhost:1420"]

    def test_cors_origins_env(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://a.com, https://b.com ,https://c.com")
        c = cfg.SecurityConfig()
        assert c.cors_origins == ["https://a.com", "https://b.com", "https://c.com"]

    def test_log_security_event(self, caplog):
        c = cfg.SecurityConfig()
        with caplog.at_level(logging.INFO, logger="core.config"):
            c._log_security_event("test_event", "info", {"k": "v"})
        assert any("Security Audit: test_event - info" in r.message for r in caplog.records)


# ===========================================================================
# APIConfig / IntegrationConfig / AIConfig / LoggingConfig
# ===========================================================================


class TestAPIConfig:
    def test_defaults(self, monkeypatch):
        for var in ("RATE_LIMIT", "REQUEST_TIMEOUT", "MAX_REQUEST_SIZE", "PAGINATION_SIZE"):
            monkeypatch.delenv(var, raising=False)
        c = cfg.APIConfig()
        assert c.rate_limit == 100
        assert c.request_timeout == 30
        assert c.max_request_size == 10 * 1024 * 1024
        assert c.pagination_size == 50

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT", "50")
        monkeypatch.setenv("REQUEST_TIMEOUT", "60")
        monkeypatch.setenv("MAX_REQUEST_SIZE", "1048576")
        monkeypatch.setenv("PAGINATION_SIZE", "25")
        c = cfg.APIConfig()
        assert c.rate_limit == 50
        assert c.request_timeout == 60
        assert c.max_request_size == 1048576
        assert c.pagination_size == 25


class TestIntegrationConfig:
    def test_all_env_vars(self, monkeypatch):
        env = {
            "GOOGLE_CLIENT_ID": "gid", "GOOGLE_CLIENT_SECRET": "gsec",
            "MICROSOFT_CLIENT_ID": "mid", "MICROSOFT_CLIENT_SECRET": "msec",
            "GITHUB_CLIENT_ID": "ghid", "GITHUB_CLIENT_SECRET": "ghsec",
            "NOTION_ACCESS_TOKEN": "ntok",
            "JIRA_BASE_URL": "jurl", "JIRA_USERNAME": "juser", "JIRA_API_TOKEN": "jtok",
            "TRELLO_API_KEY": "tkey", "TRELLO_ACCESS_TOKEN": "ttok",
        }
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        c = cfg.IntegrationConfig()
        assert c.google_client_id == "gid"
        assert c.google_client_secret == "gsec"
        assert c.microsoft_client_id == "mid"
        assert c.microsoft_client_secret == "msec"
        assert c.github_client_id == "ghid"
        assert c.github_client_secret == "ghsec"
        assert c.notion_token == "ntok"
        assert c.jira_base_url == "jurl"
        assert c.jira_username == "juser"
        assert c.jira_api_token == "jtok"
        assert c.trello_api_key == "tkey"
        assert c.trello_token == "ttok"

    def test_empty_defaults(self, monkeypatch):
        for var in ("GOOGLE_CLIENT_ID", "MICROSOFT_CLIENT_ID", "GITHUB_CLIENT_ID"):
            monkeypatch.delenv(var, raising=False)
        c = cfg.IntegrationConfig()
        assert c.google_client_id == ""
        assert c.microsoft_client_id == ""
        assert c.github_client_id == ""


class TestAIConfig:
    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "oai")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant")
        monkeypatch.setenv("MODEL_NAME", "gpt-4o")
        monkeypatch.setenv("MAX_TOKENS", "4096")
        monkeypatch.setenv("TEMPERATURE", "0.2")
        c = cfg.AIConfig()
        assert c.openai_api_key == "oai"
        assert c.anthropic_api_key == "ant"
        assert c.model_name == "gpt-4o"
        assert c.max_tokens == 4096
        assert c.temperature == 0.2

    def test_defaults(self, monkeypatch):
        for var in ("MODEL_NAME", "MAX_TOKENS", "TEMPERATURE"):
            monkeypatch.delenv(var, raising=False)
        c = cfg.AIConfig()
        assert c.model_name == "gpt-3.5-turbo"
        assert c.max_tokens == 2048
        assert c.temperature == 0.7


class TestLoggingConfig:
    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "debug")
        monkeypatch.setenv("LOG_FILE", "/tmp/atom-covpush.log")
        monkeypatch.setenv("LOG_MAX_BYTES", "2097152")
        monkeypatch.setenv("LOG_BACKUP_COUNT", "7")
        c = cfg.LoggingConfig()
        assert c.level == "DEBUG"  # uppercased
        assert c.file_path == "/tmp/atom-covpush.log"
        assert c.max_bytes == 2097152
        assert c.backup_count == 7

    def test_defaults(self, monkeypatch):
        for var in ("LOG_LEVEL", "LOG_FILE", "LOG_MAX_BYTES", "LOG_BACKUP_COUNT"):
            monkeypatch.delenv(var, raising=False)
        c = cfg.LoggingConfig()
        assert c.level == "INFO"
        assert c.file_path == "./logs/atom.log"
        assert c.max_bytes == 10 * 1024 * 1024
        assert c.backup_count == 5


# ===========================================================================
# ATOMConfig
# ===========================================================================


class TestATOMConfig:
    def test_post_init_creates_all_sub_configs(self):
        c = cfg.ATOMConfig()
        assert isinstance(c.database, cfg.DatabaseConfig)
        assert isinstance(c.lancedb, cfg.LanceDBConfig)
        assert isinstance(c.redis, cfg.RedisConfig)
        assert isinstance(c.scheduler, cfg.SchedulerConfig)
        assert isinstance(c.server, cfg.ServerConfig)
        assert isinstance(c.security, cfg.SecurityConfig)
        assert isinstance(c.api, cfg.APIConfig)
        assert isinstance(c.integrations, cfg.IntegrationConfig)
        assert isinstance(c.ai, cfg.AIConfig)
        assert isinstance(c.logging, cfg.LoggingConfig)

    def test_post_init_keeps_provided_configs(self):
        database = cfg.DatabaseConfig(url="sqlite:///custom.db")
        lancedb = cfg.LanceDBConfig(path="/custom")
        redis = cfg.RedisConfig(enabled=True)
        scheduler = cfg.SchedulerConfig(job_store_type="redis")
        server = cfg.ServerConfig(port=1)
        security = cfg.SecurityConfig(secret_key="k")
        api = cfg.APIConfig(rate_limit=1)
        integrations = cfg.IntegrationConfig()
        ai = cfg.AIConfig(model_name="m")
        logging_cfg = cfg.LoggingConfig(level="DEBUG")
        c = cfg.ATOMConfig(
            database=database, lancedb=lancedb, redis=redis, scheduler=scheduler,
            server=server, security=security, api=api, integrations=integrations,
            ai=ai, logging=logging_cfg,
        )
        assert c.database is database
        assert c.lancedb is lancedb
        assert c.redis is redis
        assert c.scheduler is scheduler
        assert c.server is server
        assert c.security is security
        assert c.api is api
        assert c.integrations is integrations
        assert c.ai is ai
        assert c.logging is logging_cfg

    def test_from_env(self):
        c = cfg.ATOMConfig.from_env()
        assert isinstance(c, cfg.ATOMConfig)
        assert isinstance(c.database, cfg.DatabaseConfig)

    def test_from_file_full(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        config_file = tmp_path / "config.json"
        config_data = {
            "database": {"url": "sqlite:///from-file.db", "echo": True},
            "lancedb": {"path": "/file/lancedb"},
            "redis": {"enabled": True, "url": "redis://file:6379/0"},
            "scheduler": {"job_store_type": "file-store"},
            "server": {"port": 1234},
            "security": {"secret_key": "file-key"},
            "api": {"rate_limit": 7},
            "integrations": {"google_client_id": "file-gid"},
            "ai": {"model_name": "file-model"},
            "logging": {"level": "WARNING"},
        }
        config_file.write_text(json.dumps(config_data))
        c = cfg.ATOMConfig.from_file(str(config_file))
        assert isinstance(c.database, cfg.DatabaseConfig)
        assert c.database.url == "sqlite:///from-file.db"
        assert c.database.echo is True
        assert isinstance(c.lancedb, cfg.LanceDBConfig)
        assert c.lancedb.path == "/file/lancedb"
        assert isinstance(c.redis, cfg.RedisConfig)
        assert c.redis.enabled is True
        assert isinstance(c.scheduler, cfg.SchedulerConfig)
        assert c.scheduler.job_store_type == "file-store"
        assert isinstance(c.server, cfg.ServerConfig)
        assert c.server.port == 1234
        assert isinstance(c.security, cfg.SecurityConfig)
        assert isinstance(c.api, cfg.APIConfig)
        assert c.api.rate_limit == 7
        assert isinstance(c.integrations, cfg.IntegrationConfig)
        # IntegrationConfig.__post_init__ always re-reads env (empty here), so
        # the file value is replaced — the contract is "env wins".
        assert c.integrations.google_client_id == ""
        assert isinstance(c.ai, cfg.AIConfig)
        assert c.ai.model_name == "file-model"
        assert isinstance(c.logging, cfg.LoggingConfig)
        assert c.logging.level == "WARNING"

    def test_from_file_missing_falls_back_to_env(self, caplog):
        with caplog.at_level(logging.ERROR, logger="core.config"):
            c = cfg.ATOMConfig.from_file("/nonexistent/atom-config.json")
        assert isinstance(c, cfg.ATOMConfig)
        assert any("Error loading config" in r.message for r in caplog.records)

    def test_from_file_invalid_json_falls_back_to_env(self, tmp_path, caplog):
        config_file = tmp_path / "bad.json"
        config_file.write_text("{not-json")
        with caplog.at_level(logging.ERROR, logger="core.config"):
            c = cfg.ATOMConfig.from_file(str(config_file))
        assert isinstance(c, cfg.ATOMConfig)

    def test_to_dict(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        c = cfg.ATOMConfig(database=cfg.DatabaseConfig(url="sqlite:///x.db"))
        d = c.to_dict()
        assert d["database"]["url"] == "sqlite:///x.db"
        assert set(d.keys()) == {
            "database", "lancedb", "redis", "scheduler", "server",
            "security", "api", "integrations", "ai", "logging",
        }

    def test_to_file_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        target = tmp_path / "nested" / "dir" / "config.json"
        c = cfg.ATOMConfig(database=cfg.DatabaseConfig(url="sqlite:///roundtrip.db"))
        assert c.to_file(str(target)) is True
        assert target.exists()
        loaded = json.loads(target.read_text())
        assert loaded["database"]["url"] == "sqlite:///roundtrip.db"

    def test_to_file_failure_returns_false(self, tmp_path, caplog):
        target = tmp_path / "fail.json"
        c = cfg.ATOMConfig()

        def boom(*a, **k):
            raise OSError("permission denied")

        with patch.object(cfg.Path, "mkdir", boom):
            with caplog.at_level(logging.ERROR, logger="core.config"):
                assert c.to_file(str(target)) is False
        assert not target.exists()
        assert any("Error saving config" in r.message for r in caplog.records)

    def test_validate_valid(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        c = cfg.ATOMConfig(database=cfg.DatabaseConfig(url="sqlite:///x.db"))
        result = c.validate()
        assert result["valid"] is True
        assert result["issues"] == []

    def test_validate_database_url_required(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        c = cfg.ATOMConfig()
        c.database.url = ""
        result = c.validate()
        assert result["valid"] is False
        assert "Database URL is required" in result["issues"]

    def test_validate_default_secret_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "g")
        monkeypatch.setenv("MICROSOFT_CLIENT_ID", "m")
        c = cfg.ATOMConfig()
        c.security.secret_key = "atom-secret-key-change-in-production"
        result = c.validate()
        assert "Secret key must be set in production" in result["issues"]

    def test_validate_production_integrations_warnings(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
        c = cfg.ATOMConfig()
        c.security.secret_key = "non-default-key"
        result = c.validate()
        assert "Google client ID is recommended for full functionality" in result["issues"]
        assert "Microsoft client ID is recommended for full functionality" in result["issues"]

    def test_validate_production_with_integrations_clean(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "g")
        monkeypatch.setenv("MICROSOFT_CLIENT_ID", "m")
        c = cfg.ATOMConfig()
        c.security.secret_key = "non-default-key"
        result = c.validate()
        assert result["valid"] is True

    def test_get_database_url_and_lancedb_path(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        c = cfg.ATOMConfig(
            database=cfg.DatabaseConfig(url="sqlite:///g.db"),
            lancedb=cfg.LanceDBConfig(path="/g/lance"),
        )
        assert c.get_database_url() == "sqlite:///g.db"
        assert c.get_lancedb_path() == "/g/lance"

    def test_is_production_and_development(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        c = cfg.ATOMConfig()
        assert c.is_production() is True
        assert c.is_development() is False
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert c.is_production() is False
        assert c.is_development() is True


# ===========================================================================
# Module-level helpers
# ===========================================================================


class TestModuleHelpers:
    def test_get_config_returns_global(self):
        assert cfg.get_config() is cfg.config
        assert cfg.settings is cfg.config

    def test_load_config_from_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        config_file = tmp_path / "load.json"
        config_file.write_text(json.dumps({"database": {"url": "sqlite:///loaded.db"}}))
        try:
            result = cfg.load_config(str(config_file))
            assert result is cfg.config
            assert isinstance(cfg.config.database, cfg.DatabaseConfig)
            assert cfg.config.database.url == "sqlite:///loaded.db"
            # Regression: the `settings` alias must track a reloaded config.
            assert cfg.settings is cfg.config
            assert cfg.get_config() is cfg.config
        finally:
            cfg.config = cfg.ATOMConfig.from_env()
            cfg.settings = cfg.config

    def test_load_config_missing_path_uses_env(self):
        try:
            result = cfg.load_config("/definitely/not/here.json")
            assert result is cfg.config
            assert isinstance(cfg.config.database, cfg.DatabaseConfig)
        finally:
            cfg.config = cfg.ATOMConfig.from_env()

    def test_load_config_none_path_uses_env(self):
        try:
            result = cfg.load_config()
            assert result is cfg.config
            assert isinstance(cfg.config.database, cfg.DatabaseConfig)
        finally:
            cfg.config = cfg.ATOMConfig.from_env()


class TestSetupLogging:
    def test_setup_with_explicit_config(self, tmp_path):
        log_file = tmp_path / "atom-covpush.log"
        conf = cfg.LoggingConfig(level="DEBUG", file_path=str(log_file))
        cfg.setup_logging(conf)
        assert log_file.exists()
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) == 2
        assert isinstance(root.handlers[0], logging.StreamHandler)
        assert isinstance(root.handlers[1], logging.handlers.RotatingFileHandler)
        assert root.handlers[1].maxBytes == conf.max_bytes
        assert root.handlers[1].backupCount == conf.backup_count

    def test_setup_with_none_uses_global_config(self, tmp_path):
        log_file = tmp_path / "atom-default.log"
        original = cfg.config
        try:
            cfg.config = cfg.ATOMConfig(
                logging=cfg.LoggingConfig(level="WARNING", file_path=str(log_file))
            )
            cfg.setup_logging(None)
            assert log_file.exists()
            assert logging.getLogger().level == logging.WARNING
        finally:
            cfg.config = original


# ===========================================================================
# MarketplaceConfig
# ===========================================================================


class TestMarketplaceConfig:
    def _clear_env(self, monkeypatch):
        for var in (
            "MARKETPLACE_ENABLED", "ATOM_SAAS_API_URL", "ATOM_SAAS_API_TOKEN",
            "ATOM_SAAS_TIMEOUT", "ATOM_SAAS_CACHE_TTL",
        ):
            monkeypatch.delenv(var, raising=False)

    def test_defaults(self, monkeypatch):
        self._clear_env(monkeypatch)
        c = cfg.MarketplaceConfig()
        assert c.enabled is True
        assert c.api_url == "https://atomagentos.com/api/v1/marketplace"
        assert c.api_token is None
        assert c.timeout == 30
        assert c.cache_ttl_seconds == 300

    @pytest.mark.parametrize("value,expected", [
        ("true", True), ("1", True), ("yes", True), ("on", True),
        ("TRUE", True), ("false", False), ("0", False), ("no", False),
        ("off", False), ("disabled", False),
    ])
    def test_enabled_variants(self, monkeypatch, value, expected):
        self._clear_env(monkeypatch)
        monkeypatch.setenv("MARKETPLACE_ENABLED", value)
        assert cfg.MarketplaceConfig().enabled is expected

    def test_env_overrides(self, monkeypatch):
        self._clear_env(monkeypatch)
        monkeypatch.setenv("ATOM_SAAS_API_URL", "https://custom.marketplace/v2")
        monkeypatch.setenv("ATOM_SAAS_API_TOKEN", "tok-123")
        monkeypatch.setenv("ATOM_SAAS_TIMEOUT", "10")
        monkeypatch.setenv("ATOM_SAAS_CACHE_TTL", "60")
        c = cfg.MarketplaceConfig()
        assert c.api_url == "https://custom.marketplace/v2"
        assert c.api_token == "tok-123"
        assert c.timeout == 10
        assert c.cache_ttl_seconds == 60

    def test_validate_disabled_is_valid(self, monkeypatch):
        self._clear_env(monkeypatch)
        monkeypatch.setenv("MARKETPLACE_ENABLED", "false")
        c = cfg.MarketplaceConfig()
        assert c.validate() == (True, None)

    def test_validate_enabled_without_token_warns(self, monkeypatch):
        self._clear_env(monkeypatch)
        c = cfg.MarketplaceConfig()
        is_valid, message = c.validate()
        assert is_valid is True
        assert "ATOM_SAAS_API_TOKEN not set" in message

    def test_validate_short_token_invalid(self, monkeypatch):
        self._clear_env(monkeypatch)
        monkeypatch.setenv("ATOM_SAAS_API_TOKEN", "short")
        c = cfg.MarketplaceConfig()
        is_valid, message = c.validate()
        assert is_valid is False
        assert "too short" in message

    def test_validate_long_token_valid(self, monkeypatch):
        self._clear_env(monkeypatch)
        monkeypatch.setenv("ATOM_SAAS_API_TOKEN", "x" * 20)
        c = cfg.MarketplaceConfig()
        assert c.validate() == (True, None)

    def test_is_configured(self, monkeypatch):
        self._clear_env(monkeypatch)
        assert cfg.MarketplaceConfig().is_configured() is False  # enabled, no token
        monkeypatch.setenv("ATOM_SAAS_API_TOKEN", "x" * 20)
        assert cfg.MarketplaceConfig().is_configured() is True
        monkeypatch.setenv("MARKETPLACE_ENABLED", "false")
        assert cfg.MarketplaceConfig().is_configured() is False
