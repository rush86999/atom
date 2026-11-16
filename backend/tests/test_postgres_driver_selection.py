"""PostgreSQL driver selection must match the declared dependency.

SQLAlchemy 2.1 changed the DEFAULT DBAPI for a driver-less ``postgresql://``
URL to psycopg (psycopg3):
https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2

Atom declares ``psycopg2-binary`` (requirements.txt / pyproject) and ships
psycopg2; psycopg3 is absent. A canonical installer pointing at
``postgresql://…`` therefore failed at ``core.database`` import/engine
construction before any schema work. These focused controls pin the policy:

* the shared normalizer rewrites ONLY the scheme token of an implicit URL
  (credentials escaping, IPv6 hosts, ports, database and query strings are
  preserved verbatim);
* explicit driver choices are never rewritten;
* the real engine resolves the DECLARED driver without connecting;
* SQLite anchoring, the pytest live-DB guard and the TESTING force-SQLite
  policy are unchanged.

No network/connect, no provider/model, no live/app DB, no Docker.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url

os.environ.setdefault("TESTING", "1")


def _normalize():
    from core.local_paths import normalize_postgres_driver

    return normalize_postgres_driver


def _asyncpg_url():
    from core.local_paths import postgres_asyncpg_url

    return postgres_asyncpg_url


# ---------------------------------------------------------------------------
# Shared normalizer semantics
# ---------------------------------------------------------------------------
class TestImplicitDriverPinning:
    @pytest.mark.parametrize("url, scheme", [
        ("postgresql://user:p%40ss@[::1]:5432/atom_db"
         "?application_name=atom&options=-csearch_path%3Dpublic",
         "postgresql://"),
        ("postgresql://u:p@db.internal:6543/x", "postgresql://"),
        ("postgres://u:p@host:5432/db?sslmode=require", "postgres://"),
    ])
    def test_only_the_scheme_token_changes(self, url, scheme):
        normalize = _normalize()
        normalized = normalize(url)
        assert normalized == "postgresql+psycopg2://" + url[len(scheme):]

        original_parsed = make_url(url)
        normalized_parsed = make_url(normalized)
        # Same target: only the drivername differs (credentials/IPv6/query
        # survive string surgery exactly).
        assert normalized_parsed.drivername == "postgresql+psycopg2"
        assert (normalized_parsed.username, normalized_parsed.password) == (
            original_parsed.username, original_parsed.password)
        assert (normalized_parsed.host, normalized_parsed.port) == (
            original_parsed.host, original_parsed.port)
        assert normalized_parsed.database == original_parsed.database
        assert normalized_parsed.query == original_parsed.query

    @pytest.mark.parametrize("url", [
        "postgresql+psycopg2://u:p@host/db",
        "postgresql+psycopg://u:p@host/db",
        "postgresql+asyncpg://u:p@host/db",
        "postgresql+pg8000://u:p@host/db",
        "sqlite:////tmp/owned.db",
        "sqlite:///:memory:",
        "redis://localhost:6379/0",
        "",
        None,
    ])
    def test_explicit_and_non_postgres_urls_are_unchanged(self, url):
        assert _normalize()(url) == url

    def test_asyncpg_consumers_get_a_plain_dsn(self):
        asyncpg_url = _asyncpg_url()
        url = "postgresql://u:p%40ss@[::1]:5432/db?application_name=atom"
        pinned = _normalize()(url)
        assert asyncpg_url(pinned) == "postgresql+asyncpg://" + url[len("postgresql://"):]
        assert asyncpg_url(url) == "postgresql+asyncpg://" + url[len("postgresql://"):]
        # Explicit non-default choices are preserved for the caller.
        explicit = "postgresql+psycopg://u:p@host/db"
        assert asyncpg_url(explicit) == explicit
        assert asyncpg_url("postgresql+asyncpg://u:p@host/db") == (
            "postgresql+asyncpg://u:p@host/db")


# ---------------------------------------------------------------------------
# Real resolution + engine construction (no connection)
# ---------------------------------------------------------------------------
class TestEngineUsesDeclaredDriver:
    def test_get_database_url_pins_and_engine_resolves_psycopg2(
            self, monkeypatch):
        from core.database import get_database_url

        url = ("postgresql://atom:pa%40ss@[::1]:5432/atom_db"
               "?application_name=installer_probe")
        monkeypatch.setenv("TESTING", "0")       # pytest guard off
        monkeypatch.setenv("PYTEST_VERSION", "1")
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DATABASE_URL", url)

        resolved = get_database_url()
        assert resolved == "postgresql+psycopg2://" + url[len("postgresql://"):]

        engine = create_engine(resolved)  # lazy: no DBAPI connection
        try:
            assert engine.dialect.driver == "psycopg2"
            assert engine.url.get_backend_name() == "postgresql"
            parsed = make_url(url)
            assert (engine.url.username, engine.url.password) == (
                parsed.username, parsed.password)
            assert (engine.url.host, engine.url.port) == (parsed.host, parsed.port)
            assert engine.url.database == parsed.database
            assert engine.url.query == parsed.query
        finally:
            engine.dispose()

    def test_explicit_driver_survives_resolution(self, monkeypatch):
        from core.database import get_database_url

        monkeypatch.setenv("TESTING", "0")
        monkeypatch.setenv("PYTEST_VERSION", "1")
        monkeypatch.setenv("ENVIRONMENT", "development")
        explicit = "postgresql+asyncpg://u:p@host:5432/db"
        monkeypatch.setenv("DATABASE_URL", explicit)
        assert get_database_url() == explicit


# ---------------------------------------------------------------------------
# Existing SQLite / live-DB / force-SQLite policies
# ---------------------------------------------------------------------------
class TestExistingDatabaseUrlPolicies:
    def test_live_dev_sqlite_is_refused_under_pytest(self, monkeypatch):
        from core.database import get_database_url

        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.setenv("PYTEST_VERSION", "1")
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/atom.db")
        resolved = get_database_url()
        import core.database as database_module

        backend = os.path.dirname(os.path.dirname(
            os.path.abspath(database_module.__file__)))
        assert resolved == f"sqlite:///{backend}/test_integration.db"
        assert "data/atom.db" not in resolved

    def test_relative_sqlite_is_anchored_to_backend(self, monkeypatch):
        from core.database import get_database_url

        monkeypatch.setenv("TESTING", "0")  # explicit opt-in to the URL
        monkeypatch.setenv("PYTEST_VERSION", "1")
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/owned_probe.db")
        resolved = get_database_url()
        import core.database as database_module

        backend = os.path.dirname(os.path.dirname(
            os.path.abspath(database_module.__file__)))
        assert resolved == f"sqlite:///{backend}/data/owned_probe.db"

    def test_explicit_non_dev_test_url_is_honored_and_normalized(
            self, monkeypatch):
        """Existing policy: pytest honors an explicit NON-dev DATABASE_URL
        (the e2e suite points both server and pytest at its scratch file)
        instead of forcing the shared isolated SQLite file."""
        from core.database import get_database_url

        monkeypatch.setenv("TESTING", "1")
        monkeypatch.setenv("PYTEST_VERSION", "1")
        url = "postgresql://u:p@scratch-host:5432/atom_e2e"
        monkeypatch.setenv("DATABASE_URL", url)
        resolved = get_database_url()
        assert resolved == "postgresql+psycopg2://" + url[len("postgresql://"):]


# ---------------------------------------------------------------------------
# Shared scheduler job store consumer
# ---------------------------------------------------------------------------
class TestSchedulerStoreConsumer:
    def test_scheduler_job_store_pins_the_declared_driver(self):
        from core.scheduler_store import resolve_scheduler_job_store_url

        assert resolve_scheduler_job_store_url(
            "postgresql://u:p@host/jobs") == (
            "postgresql+psycopg2://u:p@host/jobs")
        assert resolve_scheduler_job_store_url(
            "postgresql+asyncpg://u:p@host/jobs") == (
            "postgresql+asyncpg://u:p@host/jobs")
        assert resolve_scheduler_job_store_url("redis://host/0") == (
            "redis://host/0")
