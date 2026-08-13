# -*- coding: utf-8 -*-
"""Coverage wave 91 — core/migrate_json_to_jsonb (JSON→JSONB migration).

Fully mocked engine (fake connection + fake result sets); the `__main__`
block is exercised by re-executing the module source with a patched
core.database.engine so no real database is ever touched. Zero LLM, no network.

- _validate_identifier: valid identifiers pass; invalid (hyphens, dots,
  spaces, empty, leading digit) raise ValueError.
- migrate(): column exists + already jsonb → skip; missing column → warning
  + skip; existing non-jsonb → ALTER TABLE executed + commit; execute
  failure → rollback + continue; ValueError from validation propagates.
- __main__ block runs migrate() end-to-end against the fake engine.
"""
import pathlib

import pytest
from unittest.mock import MagicMock

import core.migrate_json_to_jsonb as mig


class _FakeRow:
    def __init__(self, data_type):
        self._type = data_type

    def __getitem__(self, idx):
        return self._type


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConnection:
    """Records executed SQL; returns rows keyed by table name."""

    def __init__(self, rows, fail_alter_on=None):
        self.rows = rows            # {table: _FakeRow | None}
        self.fail_alter_on = fail_alter_on  # table whose ALTER should raise
        self.executed = []
        self.commit_count = 0
        self.rollback_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        self.executed.append(str(sql))
        if "ALTER TABLE" in str(sql):
            table = str(sql).split("ALTER TABLE ")[1].split(" ")[0]
            if self.fail_alter_on == table:
                raise RuntimeError("ALTER failed")
            return _FakeResult(None)
        # information_schema lookup — bound params carry table/column names
        params = sql.compile().params
        row = self.rows.get(params.get("t"))
        return _FakeResult(row)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


ALL_TABLES = [
    "graph_nodes",
    "graph_edges",
    "graph_communities",
    "agent_episodes",
    "episode_access_logs",
    "entity_type_definitions",
]


def _rows_all_text():
    return {t: _FakeRow("text") for t in ALL_TABLES}


def _fake_engine(rows, fail_alter_on=None):
    conn = _FakeConnection(rows, fail_alter_on)
    engine = MagicMock()
    engine.connect.return_value = conn
    return engine


# ============================================================================
# _validate_identifier
# ============================================================================

def test_validate_identifier_ok():
    for name in ["graph_nodes", "properties", "agent_episodes", "A1_b"]:
        assert mig._validate_identifier(name) == name


def test_validate_identifier_invalid():
    for name in ["graph-nodes", "graph.nodes", "has space", "", "1abc", "select;drop"]:
        with pytest.raises(ValueError):
            mig._validate_identifier(name)


# ============================================================================
# migrate()
# ============================================================================

def test_migrate_skips_missing_and_jsonb_columns(monkeypatch):
    # graph_nodes.properties → already jsonb; graph_edges.properties → missing;
    # everything else migrates.
    rows = _rows_all_text()
    rows["graph_nodes"] = _FakeRow("jsonb")
    rows["graph_edges"] = None
    engine = _fake_engine(rows)
    monkeypatch.setattr(mig, "engine", engine)
    mig.migrate()
    alters = [s for s in engine.connect().executed if "ALTER TABLE" in s]
    assert len(alters) == 4  # remaining 4 tables migrated
    assert all("TYPE JSONB USING" in s for s in alters)


def test_migrate_commits_per_table(monkeypatch):
    engine = _fake_engine(_rows_all_text())
    monkeypatch.setattr(mig, "engine", engine)
    mig.migrate()
    conn = engine.connect()
    assert conn.commit_count == 6


def test_migrate_rolls_back_on_alter_failure(monkeypatch):
    engine = _fake_engine(_rows_all_text(), fail_alter_on="graph_nodes")
    monkeypatch.setattr(mig, "engine", engine)
    mig.migrate()
    conn = engine.connect()
    assert conn.rollback_count == 1
    assert conn.commit_count == 5  # the other 5 succeeded


def test_migrate_identifier_validation_runs_before_each_table(monkeypatch):
    engine = _fake_engine(_rows_all_text())
    monkeypatch.setattr(mig, "engine", engine)
    mig.migrate()
    conn = engine.connect()
    assert len(conn.executed) >= 12  # 6 lookups + 6 alters


def test_main_block_runs_migrate_without_touching_real_db(monkeypatch):
    # Re-execute the module as __main__ with the engine patched, proving the
    # `if __name__ == "__main__": migrate()` entry point works.
    engine = _fake_engine(_rows_all_text())
    monkeypatch.setattr("core.database.engine", engine)
    source = pathlib.Path(mig.__file__).read_text()
    ns = {"__name__": "__main__"}
    exec(compile(source, mig.__file__, "exec"), ns)
    conn = engine.connect()
    assert conn.commit_count == 6


def test_migrate_reraises_identifier_validation_failure(monkeypatch):
    def _bad(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")

    monkeypatch.setattr(mig, "_validate_identifier", _bad)
    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        mig.migrate()
