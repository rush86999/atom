"""Scratch guard check for the result_json alembic revision.

Creates an existing-style task_operation_records table without result_json,
applies the revision's upgrade twice, downgrades twice, then upgrades again.
No application database or provider is touched.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

scratch = Path(__file__).resolve().parent / "scratch" / "migration.db"
if scratch.exists():
    scratch.unlink()
engine = create_engine(f"sqlite:///{scratch}")
with engine.begin() as conn:
    conn.execute(text(
        "create table task_operation_records ("
        "id varchar primary key, status varchar not null)"))

revision_path = (
    Path(__file__).resolve().parents[4]
    / "backend/alembic/versions/20261107_task_operation_result_json.py")
spec = importlib.util.spec_from_file_location("mig", revision_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def columns(conn):
    return {c["name"] for c in inspect(conn).get_columns(
        "task_operation_records")}


with engine.begin() as conn:
    mod.op = Operations(MigrationContext.configure(conn))
    mod.upgrade()
    mod.upgrade()
    assert "result_json" in columns(conn)
    mod.downgrade()
    mod.downgrade()
    assert "result_json" not in columns(conn)
    mod.upgrade()
    assert "result_json" in columns(conn)
print("migration upgrade/downgrade guards verified on scratch SQLite")
