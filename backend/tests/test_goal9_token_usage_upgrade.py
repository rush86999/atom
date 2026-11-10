"""Real pre-upgrade SQLite fixtures through the actual startup repair hook.

The app's supported SQLite upgrade path is
``core.sqlite_schema_repair.repair_known_drift()`` (called before
``Base.metadata.create_all`` at startup). These tests create the pre-change
``token_usage`` table with NOT NULL agent/tenant/model and old columns, insert
prior rows IDs/indexes, then run that hook, not a hand-written migration.

The second fixture is the partial-upgrade case: the legacy table still has the
old NOT NULL columns but already gained ``pricing_status``. The rebuild must
preserve existing unknown/free/priced flags, NULL cost, custom columns and
custom indexes instead of defaulting the status to ``priced``.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from core import sqlite_schema_repair as repair
from core.models import TokenUsage

_FK_CLAUSES = """,
    FOREIGN KEY(agent_id) REFERENCES agent_registry(id),
    FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
    FOREIGN KEY(execution_id) REFERENCES agent_executions(id),
    FOREIGN KEY(chain_id) REFERENCES delegation_chains(id)
"""


def _old_schema(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql(f"""
            CREATE TABLE token_usage (
                id VARCHAR NOT NULL PRIMARY KEY,
                agent_id VARCHAR NOT NULL,
                workspace_id VARCHAR,
                tenant_id VARCHAR NOT NULL,
                execution_id VARCHAR,
                chain_id VARCHAR,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                billed BOOLEAN,
                cost_usd FLOAT,
                memory_mb FLOAT,
                model_name VARCHAR NOT NULL,
                timestamp DATETIME
                {_FK_CLAUSES}
            )
        """)
        conn.exec_driver_sql(
            "CREATE INDEX ix_token_usage_agent_id ON token_usage(agent_id)")
        conn.exec_driver_sql(
            "INSERT INTO token_usage (id, agent_id, workspace_id, tenant_id, "
            "prompt_tokens, completion_tokens, total_tokens, billed, cost_usd, "
            "model_name, timestamp) VALUES "
            "('old-1','agent-old','ws-old','tenant-old',10,2,12,1,0.25,"
            "'old-model','2026-11-01 00:00:00'),"
            "('old-2','agent-old','ws-old','tenant-old',20,4,24,1,0.50,"
            "'old-model','2026-11-02 00:00:00')"
        )


def _partial_schema(engine):
    """Legacy NOT NULL table that already has pricing_status + custom data."""
    with engine.begin() as conn:
        conn.exec_driver_sql(f"""
            CREATE TABLE token_usage (
                id VARCHAR NOT NULL PRIMARY KEY,
                agent_id VARCHAR NOT NULL,
                workspace_id VARCHAR,
                tenant_id VARCHAR NOT NULL,
                execution_id VARCHAR,
                chain_id VARCHAR,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                billed BOOLEAN,
                cost_usd FLOAT,
                memory_mb FLOAT,
                model_name VARCHAR NOT NULL,
                timestamp DATETIME,
                pricing_status VARCHAR(20),
                custom_tag TEXT
                {_FK_CLAUSES}
            )
        """)
        conn.exec_driver_sql(
            "CREATE INDEX ix_token_usage_tenant_id ON token_usage(tenant_id)")
        conn.exec_driver_sql(
            "CREATE INDEX ix_token_usage_custom_tag ON token_usage(custom_tag)")
        conn.exec_driver_sql(
            "INSERT INTO token_usage (id, agent_id, workspace_id, tenant_id, "
            "prompt_tokens, completion_tokens, total_tokens, billed, cost_usd, "
            "model_name, timestamp, pricing_status, custom_tag) VALUES "
            "('prior-unknown','agent-old','ws-old','tenant-old',10,0,10,1,"
            "NULL,'old-model','2026-11-01 00:00:00','unknown','keep-unknown'),"
            "('prior-free','agent-old','ws-old','tenant-old',0,0,0,1,"
            "0.0,'old-model','2026-11-02 00:00:00','free','keep-free'),"
            "('prior-priced','agent-old','ws-old','tenant-old',20,0,20,1,"
            "0.25,'old-model','2026-11-03 00:00:00','priced','keep-priced'),"
            "('prior-null','agent-old','ws-old','tenant-old',30,0,30,1,"
            "NULL,'old-model','2026-11-04 00:00:00',NULL,'keep-null')"
        )


def _run_supported_startup_upgrade(engine, monkeypatch):
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session_cm():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("core.database.get_db_session", _session_cm)
    # The hook keys repairs by engine URL; clear it so this is a real run.
    repair._REPAIRED.clear()
    repair._clear_token_usage_upgrade_failure()
    repair.repair_known_drift()
    assert repair.token_usage_upgrade_failure_reason() is None


def test_pre_upgrade_sqlite_token_usage_upgrades_via_startup_hook(
        tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'pre-upgrade.db'}")
    _old_schema(engine)

    # Negative control BEFORE the upgrade: the old NOT NULL contract rejects
    # the legitimate non-agent/unknown-scope row this change must support.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO token_usage (id, agent_id, tenant_id, model_name) "
                "VALUES ('pre-negative', NULL, NULL, NULL)"))

    _run_supported_startup_upgrade(engine, monkeypatch)

    insp = inspect(engine)
    cols = {c["name"]: c for c in insp.get_columns("token_usage")}
    for name in ("provider_id", "request_id", "attempt_id", "pricing_status"):
        assert name in cols
    for name in ("agent_id", "tenant_id", "model_name"):
        assert cols[name]["nullable"] is True, name

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, agent_id, tenant_id, model_name, cost_usd "
            "FROM token_usage ORDER BY id")).fetchall()
        assert rows == [
            ("old-1", "agent-old", "tenant-old", "old-model", 0.25),
            ("old-2", "agent-old", "tenant-old", "old-model", 0.50),
        ]
        assert conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='token_usage' AND name='ix_token_usage_agent_id'"
        )).fetchone()
        idx = {r[1]: r for r in conn.exec_driver_sql(
            "PRAGMA index_list('token_usage')").fetchall()}
        assert idx["uq_token_usage_attempt_id"][2] == 1  # unique
        fks = {r[2] for r in conn.exec_driver_sql(
            "PRAGMA foreign_key_list('token_usage')").fetchall()}
        assert {"agent_registry", "workspaces", "agent_executions",
                "delegation_chains"}.issubset(fks)

    # New contract: legitimate non-agent / unresolved-scope / unknown cost row.
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(TokenUsage(
            id="new-1", agent_id=None, workspace_id=None, tenant_id=None,
            model_name=None, cost_usd=None, pricing_status="unknown",
            attempt_id="new-attempt-1", billed=True))
        db.commit()
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT agent_id, tenant_id, model_name, cost_usd, pricing_status "
            "FROM token_usage WHERE id='new-1'")).fetchone() == (
            None, None, None, None, "unknown")

    # Rerun the same startup hook (process restart) is idempotent.
    repair._REPAIRED.clear()
    repair.repair_known_drift()
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT COUNT(*) FROM token_usage")).scalar() == 3
    engine.dispose()


def test_partial_upgrade_preserves_pricing_status_and_custom_index(
        tmp_path, monkeypatch):
    """Legacy NOT NULL table + existing pricing_status/custom data.

    Reproduces the frozen-75 partial-schema defect: before the fix the rebuild
    dropped the existing pricing_status and defaulted every row to 'priced'.
    This full supported-startup twin keeps unknown/free/priced, NULL cost,
    IDs, custom column data and the custom index across a rerun.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'partial-upgrade.db'}")
    _partial_schema(engine)

    # Negative before upgrade: old NOT NULL still rejects non-agent rows.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO token_usage (id, agent_id, tenant_id, model_name) "
                "VALUES ('pre-negative', NULL, NULL, NULL)"))

    _run_supported_startup_upgrade(engine, monkeypatch)

    insp = inspect(engine)
    cols = {c["name"]: c for c in insp.get_columns("token_usage")}
    for name in ("agent_id", "tenant_id", "model_name"):
        assert cols[name]["nullable"] is True, name

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, agent_id, tenant_id, model_name, cost_usd, "
            "pricing_status, custom_tag FROM token_usage ORDER BY id"
        )).fetchall()
        assert rows == [
            ("prior-free", "agent-old", "tenant-old", "old-model", 0.0,
             "free", "keep-free"),
            ("prior-null", "agent-old", "tenant-old", "old-model", None,
             "priced", "keep-null"),
            ("prior-priced", "agent-old", "tenant-old", "old-model", 0.25,
             "priced", "keep-priced"),
            ("prior-unknown", "agent-old", "tenant-old", "old-model", None,
             "unknown", "keep-unknown"),
        ]
        index_names = {r[1] for r in conn.exec_driver_sql(
            "PRAGMA index_list('token_usage')").fetchall()}
        assert "ix_token_usage_custom_tag" in index_names
        assert "ix_token_usage_tenant_id" in index_names
        fks = {r[2] for r in conn.exec_driver_sql(
            "PRAGMA foreign_key_list('token_usage')").fetchall()}
        assert {"agent_registry", "workspaces", "agent_executions",
                "delegation_chains"}.issubset(fks)

    # New non-agent/unknown row works after the partial upgrade.
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(TokenUsage(
            id="new-partial-1", agent_id=None, workspace_id=None,
            tenant_id=None, model_name=None, cost_usd=None,
            pricing_status="unknown", attempt_id="new-partial-1", billed=True))
        db.commit()

    # Rerun/restart is idempotent and preserves the flags/data.
    repair._REPAIRED.clear()
    repair.repair_known_drift()
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT COUNT(*) FROM token_usage")).scalar() == 5
        assert conn.execute(text(
            "SELECT pricing_status, cost_usd, custom_tag FROM token_usage "
            "WHERE id='prior-unknown'")).fetchone() == (
            "unknown", None, "keep-unknown")
        assert conn.execute(text(
            "SELECT pricing_status FROM token_usage "
            "WHERE id='prior-free'")).fetchone() == ("free",)
    engine.dispose()


def test_failed_upgrade_is_recorded_and_retryable(tmp_path, monkeypatch):
    """A failed rebuild is NOT marked repaired; hard-stop can see the failure."""
    engine = create_engine(f"sqlite:///{tmp_path / 'failed-upgrade.db'}")
    _old_schema(engine)
    monkeypatch.setattr(repair, "_TOKEN_USAGE_UPGRADE_FAILURE", None)
    repair._REPAIRED.clear()

    def _begin_fails():
        raise RuntimeError("ddl unavailable")

    monkeypatch.setattr(engine, "begin", _begin_fails)
    repair.ensure_token_usage_upgrade(engine)
    assert repair.token_usage_upgrade_failure_reason()
    assert (str(engine.url), "token_usage_rebuild_v1") not in repair._REPAIRED
    engine.dispose()
