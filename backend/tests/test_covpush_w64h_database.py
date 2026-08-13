"""
Coverage wave 64h — core/database.py (standalone, function-level, TDD).

Covers:
- _clean_postgresql_url (passthrough / parameter strip / exception)
- get_database_url (TESTING mode, prod fail-closed, dev fallback, mock DB,
  SSL append, env sync-back)
- Module-level engine/session configuration branches (in-memory SQLite,
  file SQLite, Postgres prod/dev, other dialects) via in-process
  importlib.reload with restored env + module state
- Async URL rewriting + async engine kwargs (postgresql://, postgres://)
- ASYNC_DB_AVAILABLE ImportError fallback
- get_db dependency generator
- get_db_session / get_db_context context managers (commit + rollback paths)
- get_async_db / get_async_db_session (available/unavailable, commit/rollback)

No real DB writes: all engines created in-process are lazy (never connected),
and session/engine objects are mocked fakes. The real atom_dev.db is never
touched. Every reload test restores the original env and reloads the module
so the session state is identical to what it was before the test.
"""

import asyncio
import importlib
import os
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy.pool import StaticPool

import core.database as db_mod

_ORIG_DB_BINDINGS = {_n: getattr(db_mod, _n) for _n in dir(db_mod)}


def _reload_database():
    """Reload core.database, then restore the original module-level bindings
    (same rationale as _reload_auth in test_covpush_w64h_auth.py — sibling
    suites importing `from core.database import get_db` must keep working)."""
    importlib.reload(db_mod)
    for _n, _o in _ORIG_DB_BINDINGS.items():
        if hasattr(db_mod, _n):
            setattr(db_mod, _n, _o)


@pytest.fixture(autouse=True)
def _restore_module_state():
    """Ensure the module is reloaded with its original env at the end of every
    test that mutates os.environ or reloads the module."""
    saved = {k: os.environ.get(k) for k in (
        "DATABASE_URL", "ENVIRONMENT", "TESTING", "ATOM_MOCK_DATABASE",
        "DB_SSL_CERT", "DB_SSL_KEY", "DB_SSL_ROOT_CERT", "DB_SSL_MODE",
    )}
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ===========================================================================
# _clean_postgresql_url
# ===========================================================================


class TestCleanPostgresqlUrl:
    def test_none_url_passthrough(self):
        assert db_mod._clean_postgresql_url(None) is None

    def test_empty_url_passthrough(self):
        assert db_mod._clean_postgresql_url("") == ""

    def test_sqlite_url_passthrough(self):
        url = "sqlite:///./dev.db"
        assert db_mod._clean_postgresql_url(url) == url

    def test_postgres_without_query_passthrough(self):
        url = "postgresql://user:pass@host:5432/dbname"
        assert db_mod._clean_postgresql_url(url) == url

    def test_strips_ssl_parameters(self):
        url = "postgresql://u:p@h/db?sslmode=require&channel_binding=disable&ssl=true&sslcompression=1&target_session_attrs=read-write&connect_timeout=10"
        cleaned = db_mod._clean_postgresql_url(url)
        assert "sslmode" not in cleaned
        assert "channel_binding" not in cleaned
        assert "sslcompression" not in cleaned
        assert "target_session_attrs" not in cleaned
        assert "connect_timeout=10" in cleaned

    def test_non_removable_params_kept(self):
        url = "postgresql://u:p@h/db?connect_timeout=10"
        assert db_mod._clean_postgresql_url(url) == url

    def test_parse_exception_returns_original(self):
        def boom(*args, **kwargs):
            raise ValueError("bad url")

        with patch("urllib.parse.urlparse", boom):
            url = "postgresql://u:p@h/db?sslmode=require"
            assert db_mod._clean_postgresql_url(url) == url


# ===========================================================================
# get_database_url
# ===========================================================================


class TestGetDatabaseUrl:
    def test_testing_mode_forces_sqlite(self, monkeypatch):
        monkeypatch.setenv("TESTING", "1")
        result = db_mod.get_database_url()
        assert result.startswith("sqlite:///")
        assert result.endswith("test_integration.db")

    def test_production_without_url_raises(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValueError, match="DATABASE_URL"):
            db_mod.get_database_url()

    def test_development_without_url_falls_back_to_dev_db(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        result = db_mod.get_database_url()
        assert result.startswith("sqlite:///")
        assert result.endswith("dev.db")

    def test_mock_database_in_memory(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///whatever.db")
        monkeypatch.setenv("ATOM_MOCK_DATABASE", "true")
        assert db_mod.get_database_url() == "sqlite:///:memory:"

    def test_mock_database_uppercase_value(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///whatever.db")
        monkeypatch.setenv("ATOM_MOCK_DATABASE", "TRUE")
        assert db_mod.get_database_url() == "sqlite:///:memory:"

    def test_production_postgres_adds_sslmode(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
        result = db_mod.get_database_url()
        assert result.endswith("?sslmode=require")

    def test_production_postgres_with_sslmode_not_duplicated(self, monkeypatch):
        """When the URL cleaner FAILS (parse error) the original URL keeps its
        sslmode parameter, so the SSL-append guard must not duplicate it."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db?sslmode=verify-ca")

        def boom(*args, **kwargs):
            raise ValueError("bad url")

        with patch("urllib.parse.urlparse", boom):
            result = db_mod.get_database_url()
        assert result.endswith("?sslmode=verify-ca")
        assert "sslmode=require" not in result

    def test_production_sqlite_no_ssl_append(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./prod.db")
        result = db_mod.get_database_url()
        assert "sslmode" not in result

    def test_syncs_back_to_environment(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
        result = db_mod.get_database_url()
        assert os.environ["DATABASE_URL"] == result


# ===========================================================================
# Module-level session functions (fakes, no real DB)
# ===========================================================================


class TestGetDb:
    def test_yields_session_and_closes(self, monkeypatch):
        fake = MagicMock()
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: fake)
        gen = db_mod.get_db()
        assert next(gen) is fake
        with pytest.raises(StopIteration):
            next(gen)
        fake.close.assert_called_once()

    def test_close_on_generator_gc_path(self, monkeypatch):
        fake = MagicMock()
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: fake)
        gen = db_mod.get_db()
        assert next(gen) is fake
        gen.close()
        fake.close.assert_called_once()


class TestGetDbSession:
    def test_commits_on_success(self, monkeypatch):
        fake = MagicMock()
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: fake)
        with db_mod.get_db_session() as session:
            assert session is fake
        fake.commit.assert_called_once()
        fake.close.assert_called_once()
        fake.rollback.assert_not_called()

    def test_rolls_back_and_reraises(self, monkeypatch):
        fake = MagicMock()
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: fake)
        with pytest.raises(RuntimeError, match="boom"):
            with db_mod.get_db_session() as session:
                raise RuntimeError("boom")
        fake.rollback.assert_called_once()
        fake.close.assert_called_once()
        fake.commit.assert_not_called()

    def test_rollback_when_commit_fails(self, monkeypatch):
        fake = MagicMock()
        fake.commit.side_effect = RuntimeError("commit failed")
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: fake)
        with pytest.raises(RuntimeError, match="commit failed"):
            with db_mod.get_db_session():
                pass
        fake.rollback.assert_called_once()
        fake.close.assert_called_once()


class TestGetDbContext:
    def test_alias_returns_session_context(self, monkeypatch):
        fake = MagicMock()
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: fake)
        with db_mod.get_db_context() as session:
            assert session is fake
        fake.commit.assert_called_once()
        fake.close.assert_called_once()


# ===========================================================================
# Async session support
# ===========================================================================


class FakeAsyncSession:
    """Minimal async-context-manager session fake for get_async_db tests."""

    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def close(self):
        self.closed = True


class TestGetAsyncDb:
    def test_unavailable_raises_runtime_error(self, monkeypatch):
        monkeypatch.setattr(db_mod, "ASYNC_DB_AVAILABLE", False)
        agen = db_mod.get_async_db()

        async def _probe():
            with pytest.raises(RuntimeError, match="not available"):
                await agen.__anext__()

        asyncio.run(_probe())

    def test_success_commits_and_closes(self, monkeypatch):
        fake = FakeAsyncSession()
        monkeypatch.setattr(db_mod, "AsyncSessionLocal", lambda: fake)
        agen = db_mod.get_async_db()

        async def _probe():
            session = await agen.__anext__()
            assert session is fake
            with pytest.raises(StopAsyncIteration):
                await agen.__anext__()
            assert fake.commits == 1
            assert fake.closed is True
            assert fake.rollbacks == 0

        asyncio.run(_probe())

    def test_exception_rolls_back_and_reraises(self, monkeypatch):
        fake = FakeAsyncSession()
        monkeypatch.setattr(db_mod, "AsyncSessionLocal", lambda: fake)
        agen = db_mod.get_async_db()

        async def _probe():
            await agen.__anext__()
            with pytest.raises(RuntimeError, match="boom"):
                await agen.athrow(RuntimeError("boom"))
            assert fake.rollbacks == 1
            assert fake.commits == 0

        asyncio.run(_probe())


class TestGetAsyncDbSession:
    def test_unavailable_raises_runtime_error(self, monkeypatch):
        monkeypatch.setattr(db_mod, "ASYNC_DB_AVAILABLE", False)

        async def _probe():
            with pytest.raises(RuntimeError, match="not available"):
                async with db_mod.get_async_db_session():
                    pass

        asyncio.run(_probe())

    def test_success_commits(self, monkeypatch):
        fake = FakeAsyncSession()
        monkeypatch.setattr(db_mod, "AsyncSessionLocal", lambda: fake)

        async def _probe():
            async with db_mod.get_async_db_session() as session:
                assert session is fake
            assert fake.commits == 1
            assert fake.rollbacks == 0

        asyncio.run(_probe())

    def test_exception_rolls_back_and_reraises(self, monkeypatch):
        fake = FakeAsyncSession()
        monkeypatch.setattr(db_mod, "AsyncSessionLocal", lambda: fake)

        async def _probe():
            with pytest.raises(RuntimeError, match="boom"):
                async with db_mod.get_async_db_session():
                    raise RuntimeError("boom")
            assert fake.rollbacks == 1
            assert fake.commits == 0

        asyncio.run(_probe())


# ===========================================================================
# Module-level engine/session configuration branches (env-driven reloads)
# ===========================================================================


class TestModuleLevelBranches:
    """Re-execute core.database with different env configs to cover the
    module-body configuration branches. Each test restores the original env
    and reloads the module afterwards, leaving the session exactly as found."""

    def _saved_env(self):
        return {k: os.environ.get(k) for k in (
            "DATABASE_URL", "ENVIRONMENT", "ATOM_MOCK_DATABASE", "TESTING",
            "DB_SSL_CERT", "DB_SSL_KEY", "DB_SSL_ROOT_CERT", "DB_SSL_MODE",
        )}

    def _restore_env(self, saved):
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_in_memory_sqlite_static_pool(self):
        saved = self._saved_env()
        try:
            os.environ["DATABASE_URL"] = "sqlite:///:memory:"
            os.environ["ENVIRONMENT"] = "development"
            os.environ.pop("ATOM_MOCK_DATABASE", None)
            os.environ.pop("TESTING", None)
            importlib.reload(db_mod)
            assert db_mod.poolclass is StaticPool
            assert db_mod.pool_size is None
            assert db_mod.max_overflow is None
            assert "pool_size" not in db_mod.engine_kwargs
            assert db_mod.engine.url.database == ":memory:"
        finally:
            self._restore_env(saved)
            _reload_database()

    def test_postgres_production_ssl_certs(self):
        saved = self._saved_env()
        try:
            os.environ["DATABASE_URL"] = "postgresql://u:p@h:5432/db"
            os.environ["ENVIRONMENT"] = "production"
            os.environ["DB_SSL_CERT"] = "/certs/client.pem"
            os.environ.pop("DB_SSL_KEY", None)
            os.environ.pop("DB_SSL_ROOT_CERT", None)
            importlib.reload(db_mod)
            connect_args = db_mod.engine_kwargs["connect_args"]
            assert connect_args["sslmode"] == "require"
            assert connect_args["sslcert"] == "/certs/client.pem"
            assert "sslkey" not in connect_args
            assert "sslrootcert" not in connect_args
            assert db_mod.pool_size == 20
            assert db_mod.max_overflow == 30
            assert db_mod.engine_kwargs["pool_size"] == 20
            assert db_mod.engine_kwargs["max_overflow"] == 30
            assert db_mod.engine_kwargs["pool_timeout"] == 60
            # Async engine mirrors the postgres pooling kwargs.
            assert db_mod.async_engine_kwargs["pool_pre_ping"] is True
            assert db_mod.async_engine_kwargs["pool_recycle"] == 3600
            assert db_mod.async_engine_kwargs["pool_size"] == 20
        finally:
            self._restore_env(saved)
            _reload_database()

    def test_postgres_production_all_ssl_env_set(self):
        saved = self._saved_env()
        try:
            os.environ["DATABASE_URL"] = "postgresql://u:p@h:5432/db"
            os.environ["ENVIRONMENT"] = "production"
            os.environ["DB_SSL_CERT"] = "/certs/c.pem"
            os.environ["DB_SSL_KEY"] = "/certs/k.pem"
            os.environ["DB_SSL_ROOT_CERT"] = "/certs/r.pem"
            importlib.reload(db_mod)
            connect_args = db_mod.engine_kwargs["connect_args"]
            assert connect_args["sslcert"] == "/certs/c.pem"
            assert connect_args["sslkey"] == "/certs/k.pem"
            assert connect_args["sslrootcert"] == "/certs/r.pem"
        finally:
            self._restore_env(saved)
            _reload_database()

    def test_postgres_development_prefer_sslmode(self):
        saved = self._saved_env()
        try:
            os.environ["DATABASE_URL"] = "postgresql://u:p@h:5432/db"
            os.environ["ENVIRONMENT"] = "development"
            os.environ.pop("DB_SSL_MODE", None)
            importlib.reload(db_mod)
            assert db_mod.engine_kwargs["connect_args"] == {"sslmode": "prefer"}
        finally:
            self._restore_env(saved)
            _reload_database()

    def test_postgres_development_custom_ssl_mode(self):
        saved = self._saved_env()
        try:
            os.environ["DATABASE_URL"] = "postgresql://u:p@h:5432/db"
            os.environ["ENVIRONMENT"] = "development"
            os.environ["DB_SSL_MODE"] = "disable"
            importlib.reload(db_mod)
            assert db_mod.engine_kwargs["connect_args"] == {"sslmode": "disable"}
        finally:
            self._restore_env(saved)
            _reload_database()

    def test_other_dialect_defaults(self):
        """'Other' dialect branch (e.g. mysql): empty connect_args, no pool.
        create_engine/create_async_engine are mocked because no MySQL driver
        is installed in the venv — engine creation would otherwise fail at
        dialect resolution, not because of a real connection."""
        saved = self._saved_env()
        try:
            os.environ["DATABASE_URL"] = "mysql://u:p@h:3306/db"
            os.environ["ENVIRONMENT"] = "development"
            with patch("sqlalchemy.create_engine", return_value=MagicMock()), \
                 patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=MagicMock()):
                importlib.reload(db_mod)
            assert db_mod.engine_kwargs["connect_args"] == {}
            assert db_mod.poolclass is None
            assert db_mod.pool_size is None
            assert db_mod.max_overflow is None
            assert "pool_size" not in db_mod.engine_kwargs
        finally:
            self._restore_env(saved)
            _reload_database()

    def test_postgres_shorthand_url_async_rewrite(self):
        """postgres:// shorthand: the async URL is rewritten to
        postgresql+asyncpg://. Both engines are mocked because the bare
        'postgres' scheme is not a real SQLAlchemy dialect and asyncpg is not
        installed — the point here is the URL-rewrite logic itself."""
        saved = self._saved_env()
        captured = {}

        def fake_async_engine(url, **kwargs):
            captured["url"] = url
            return MagicMock()

        try:
            os.environ["DATABASE_URL"] = "postgres://u:p@h:5432/db"
            os.environ["ENVIRONMENT"] = "development"
            with patch("sqlalchemy.create_engine", return_value=MagicMock()), \
                 patch("sqlalchemy.ext.asyncio.create_async_engine", fake_async_engine):
                importlib.reload(db_mod)
            assert captured["url"].startswith("postgresql+asyncpg://")
        finally:
            self._restore_env(saved)
            _reload_database()

    def test_async_sqlite_url_rewrite(self):
        saved = self._saved_env()
        try:
            os.environ["DATABASE_URL"] = "sqlite:///./tmp_something.db"
            os.environ["ENVIRONMENT"] = "development"
            importlib.reload(db_mod)
            assert db_mod.async_engine.url.drivername == "sqlite+aiosqlite"
        finally:
            self._restore_env(saved)
            _reload_database()

    def test_async_unavailable_import_error_fallback(self):
        saved = self._saved_env()
        real_asyncio = sys.modules.get("sqlalchemy.ext.asyncio")
        try:
            sys.modules["sqlalchemy.ext.asyncio"] = None
            importlib.reload(db_mod)
            assert db_mod.ASYNC_DB_AVAILABLE is False
            assert db_mod.async_engine is None
            assert db_mod.AsyncSessionLocal is None
        finally:
            if real_asyncio is not None:
                sys.modules["sqlalchemy.ext.asyncio"] = real_asyncio
            self._restore_env(saved)
            _reload_database()


def test_module_attrs_sane_after_all_reloads():
    """Final state check: after every reload/restore cycle the module is
    functional with a real engine bound to the original config."""
    assert db_mod.ASYNC_DB_AVAILABLE is True
    assert db_mod.async_engine is not None
    assert db_mod.AsyncSessionLocal is not None
    assert isinstance(db_mod.engine.url.database, str)
    assert uuid.uuid4()  # noqa: B018 - trivial statement for module sanity
