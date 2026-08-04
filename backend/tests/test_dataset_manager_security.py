"""RED tests — Round 70 / Plan 315-01: dataset manager file-read / SQL / eval.

Expected to FAIL against the current code; go green in Plans 315-02/315-03.

Findings under test:
  B4 — query_data eval fallback with escapable empty-builtins jail
       (`backend/core/data/dataset_manager.py:229`).
  B5 — load_dataset reads arbitrary server file paths
       (`backend/core/data/dataset_manager.py:123-129`).
  B6 — DuckDB SQL path allows file/URL reads (`read_csv`/`read_blob`/glob)
       (`backend/core/data/dataset_manager.py:209`).
"""
import pytest

from core.data import dataset_manager as dm_mod


@pytest.fixture
def dm():
    mgr = dm_mod.get_dataset_manager()
    # Isolate: use a unique session per test.
    return mgr


@pytest.fixture
def loaded_session(dm):
    """Load a benign inline dataset and return (dm, session_id)."""
    session = "dm-sec-test"
    dm.load(source='[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]', name="t", session_id=session)
    return dm, session


# --- B5: arbitrary file read -------------------------------------------------


def test_load_dataset_reads_arbitrary_file_path(dm):
    """B5: loading a server file (e.g. /etc/passwd) via load_dataset must be
    blocked. Currently pandas happily reads it (no exception)."""
    with pytest.raises(Exception, match="(allowlist|blocked|forbidden|outside)"):
        dm.load(source="/etc/passwd", name="evil", session_id="b5")


# --- B4: escapable eval fallback ---------------------------------------------


def test_query_pandas_eval_fallback_blocks_escape(loaded_session):
    """B4: query_data's eval fallback must not be escapable to reach the
    object model. Currently `eval(sql, {"__builtins__": {}}, ...)` lets a
    payload enumerate object.__subclasses__ → success (jail escaped)."""
    dm, session = loaded_session
    payload = "().__class__.__bases__[0].__subclasses__()"
    result = dm.query("t", payload, session_id=session)
    assert result["success"] is False, (
        f"B4 regression: eval fallback executed object-model payload "
        f"(jail escaped). got: {str(result)[:200]}"
    )


# --- B6: DuckDB SQL file reads -----------------------------------------------


class FakeDuckDB:
    """Stand-in for duckdb: returns a DataFrame as if the read succeeded."""

    def __init__(self):
        self.calls = []

    def sql(self, query):
        self.calls.append(query)
        import pandas as pd
        return pd.DataFrame({"hacked": [1, 2, 3]})


def test_query_duckdb_read_csv_blocked(monkeypatch, dm, loaded_session):
    """B6: with DuckDB available, a query that reads a server file via
    `read_csv` must be rejected before reaching DuckDB. Currently the SQL is
    passed straight through (success=True with file contents)."""
    dm_mgr, session = loaded_session
    fake = FakeDuckDB()
    monkeypatch.setattr(dm_mod, "_HAS_DUCKDB", True)
    # `_duckdb` only exists when duckdb is importable; in this env it is not,
    # so inject the fake with raising=False.
    monkeypatch.setattr(dm_mod, "_duckdb", fake, raising=False)

    result = dm_mgr.query("t", "SELECT * FROM read_csv('/etc/passwd')", session_id=session)
    assert result["success"] is False, (
        f"B6 regression: DuckDB SQL read server file. got: {str(result)[:200]}"
    )
    assert fake.calls == [], f"B6: query reached DuckDB: {fake.calls}"


def test_query_sql_rejects_file_read_cleanly(dm, loaded_session):
    """B6: even without DuckDB (real env), a file-read query must be rejected
    with a policy message, not fall through to a generic eval error."""
    dm_mgr, session = loaded_session
    result = dm_mgr.query("t", "SELECT * FROM read_csv('/etc/passwd')", session_id=session)
    assert result["success"] is False
    error = result.get("error", "").lower()
    assert "block" in error or "not allowed" in error or "denied" in error, (
        f"B6: expected policy-blocked message, got: {error[:200]}"
    )


def test_query_duckdb_url_ssrf_blocked(monkeypatch, dm, loaded_session):
    """B6: a query that reads a remote URL directly (httpfs SSRF — bare
    `FROM 'https://…'`, no read_* function) must be rejected before reaching
    DuckDB. The URL lives in a string literal, so the function-name scan alone
    misses it."""
    dm_mgr, session = loaded_session
    fake = FakeDuckDB()
    monkeypatch.setattr(dm_mod, "_HAS_DUCKDB", True)
    monkeypatch.setattr(dm_mod, "_duckdb", fake, raising=False)

    result = dm_mgr.query(
        "t",
        "SELECT * FROM 'https://evil.example.com/steal.csv'",
        session_id=session,
    )
    assert result["success"] is False, (
        f"B6: URL query reached DuckDB (SSRF). got: {str(result)[:200]}"
    )
    assert fake.calls == [], f"B6: URL query reached DuckDB: {fake.calls}"
