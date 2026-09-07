"""Unit tests for the pytest DB guard in core/database.get_database_url().

Contract (INCIDENT 2026-09-04 guard + 2026-09-05 CI fix):
- pytest + unset DATABASE_URL, or one resolving to a LIVE dev DB
  (backend/dev.db, backend/data/atom.db) -> forced onto the isolated
  backend/test_integration.db.
- pytest + an explicit NON-dev DATABASE_URL -> honored (anchored to backend/
  when relative). The e2e journey shares /tmp/atom_e2e.db between the booted
  server and the pytest fixtures; forcing the isolated DB here made the
  fixtures write to a table-less copy ("no such table: users").
- TESTING=0 opts a pytest process out of the guard entirely.
"""

import os

from core.database import get_database_url

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _with_env(monkeypatch, database_url=None, testing=None):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("ATOM_MOCK_DATABASE", raising=False)
    if database_url is not None:
        monkeypatch.setenv("DATABASE_URL", database_url)
    if testing is not None:
        monkeypatch.setenv("TESTING", testing)


class TestPytestGuardForcesIsolatedDb:
    def test_unset_database_url_is_forced_isolated(self, monkeypatch):
        _with_env(monkeypatch)
        url = get_database_url()
        assert url == f"sqlite:///{os.path.join(BACKEND_DIR, 'test_integration.db')}"

    def test_relative_dev_data_db_is_forced_isolated(self, monkeypatch):
        _with_env(monkeypatch, database_url="sqlite:///data/atom.db")
        assert get_database_url().endswith("test_integration.db")

    def test_absolute_dev_data_db_is_forced_isolated(self, monkeypatch):
        _with_env(
            monkeypatch,
            database_url=f"sqlite:///{os.path.join(BACKEND_DIR, 'data', 'atom.db')}",
        )
        assert get_database_url().endswith("test_integration.db")

    def test_dev_db_fallback_file_is_forced_isolated(self, monkeypatch):
        _with_env(monkeypatch, database_url="sqlite:///dev.db")
        assert get_database_url().endswith("test_integration.db")

    def test_anchoring_is_cwd_independent(self, monkeypatch):
        # Whatever the launch CWD, a relative dev-DB path must still be
        # recognized as the live store (AGENTS.md path-anchoring class).
        _with_env(monkeypatch, database_url="sqlite:///./data/atom.db")
        assert get_database_url().endswith("test_integration.db")


class TestPytestGuardHonorsExplicitTestDb:
    def test_absolute_tmp_db_is_honored(self, monkeypatch):
        # The e2e-journey CI shape: absolute shared file with the booted server.
        _with_env(monkeypatch, database_url="sqlite:////tmp/atom_e2e.db")
        assert get_database_url() == "sqlite:////tmp/atom_e2e.db"

    def test_relative_test_db_is_honored_and_anchored_to_backend(self, monkeypatch):
        # CI backend-tests sets sqlite:///test_ci.db; it must land in backend/
        # no matter the CWD, and must NOT be the isolated override's file.
        _with_env(monkeypatch, database_url="sqlite:///test_ci.db")
        url = get_database_url()
        assert url == f"sqlite:///{os.path.join(BACKEND_DIR, 'test_ci.db')}"

    def test_explicit_conftest_db_is_honored(self, monkeypatch):
        # tests/conftest.py sets sqlite:///./test_integration.db — honoring it
        # must resolve to the same file the old forced override produced.
        _with_env(monkeypatch, database_url="sqlite:///./test_integration.db")
        assert get_database_url() == (
            f"sqlite:///{os.path.join(BACKEND_DIR, 'test_integration.db')}"
        )


class TestGuardOptOut:
    def test_testing_zero_opts_out_to_dev_fallback(self, monkeypatch):
        _with_env(monkeypatch, testing="0")
        url = get_database_url()
        assert url == f"sqlite:///{os.path.join(BACKEND_DIR, 'dev.db')}"

    def test_testing_zero_honors_even_dev_db(self, monkeypatch):
        # TESTING=0 is the documented explicit opt-out (real-DB sessions).
        _with_env(
            monkeypatch,
            database_url=f"sqlite:///{os.path.join(BACKEND_DIR, 'data', 'atom.db')}",
            testing="0",
        )
        assert get_database_url() == (
            f"sqlite:///{os.path.join(BACKEND_DIR, 'data', 'atom.db')}"
        )
