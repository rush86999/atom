"""DATABASE_URL & LanceDB path anchoring — launch-CWD independence.

``sqlite:///./data/atom.db`` in .env was resolved by SQLAlchemy against the
process CWD, so launching uvicorn from the repo root vs backend/ silently
pointed at two different databases (users/tenants "disappeared" after a
restart from another directory). Relative paths are now anchored to the
backend/ directory — the documented launch dir — at load time. LanceDB's
local agent-memory store had the same defect.
"""

import os
import subprocess
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from core.database import _anchor_sqlite_url


class TestAnchorSqliteUrl:
    def test_relative_data_path_anchors_to_backend(self):
        anchored = _anchor_sqlite_url("sqlite:///./data/atom.db")
        assert anchored == "sqlite:///" + os.path.join(BACKEND_DIR, "data", "atom.db")

    def test_quickstart_relative_filename_anchors_to_backend(self):
        anchored = _anchor_sqlite_url("sqlite:///./atom_dev.db")
        assert anchored == "sqlite:///" + os.path.join(BACKEND_DIR, "atom_dev.db")

    def test_absolute_path_unchanged(self):
        url = "sqlite:////var/lib/atom/atom.db"
        assert _anchor_sqlite_url(url) == url

    def test_memory_unchanged(self):
        assert _anchor_sqlite_url("sqlite:///:memory:") == "sqlite:///:memory:"

    def test_query_string_preserved(self):
        anchored = _anchor_sqlite_url("sqlite:///./data/atom.db?mode=ro")
        assert anchored == "sqlite:///" + os.path.join(BACKEND_DIR, "data", "atom.db") + "?mode=ro"

    def test_non_sqlite_unchanged(self):
        url = "postgresql://user:pw@host/db"
        assert _anchor_sqlite_url(url) == url

    def test_async_driver_form_anchored(self):
        anchored = _anchor_sqlite_url("sqlite+aiosqlite:///./data/atom.db")
        assert anchored == "sqlite+aiosqlite:///" + os.path.join(BACKEND_DIR, "data", "atom.db")


class TestLanceDbPathAnchoring:
    def test_relative_memory_path_anchors_to_backend(self):
        from core.lancedb_handler import _resolve_local_db_path

        assert _resolve_local_db_path("./data/atom_memory") == os.path.join(
            BACKEND_DIR, "data", "atom_memory"
        )

    def test_absolute_and_object_store_unchanged(self):
        from core.lancedb_handler import _resolve_local_db_path

        assert _resolve_local_db_path("/tmp/atom_memory") == "/tmp/atom_memory"
        assert _resolve_local_db_path("s3://bucket/atom_memory") == "s3://bucket/atom_memory"
        assert _resolve_local_db_path("db://cloud") == "db://cloud"


class TestEffectiveUrlCwdIndependent:
    def test_effective_database_url_is_the_backend_file_from_any_cwd(self, tmp_path):
        """A clean interpreter from a neutral CWD must anchor a .env-style
        relative DATABASE_URL to backend/data, not a CWD-relative file."""
        code = "import core.database as d; print(d.DATABASE_URL)"
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("DATABASE_URL", "TESTING", "ATOM_MOCK_DATABASE")
        }
        env["DATABASE_URL"] = "sqlite:///./data/atom.db"
        env["PYTHONPATH"] = BACKEND_DIR
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "sqlite:///" + os.path.join(
            BACKEND_DIR, "data", "atom.db"
        )
