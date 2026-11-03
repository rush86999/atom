"""SQLite drift repair must add numeric columns with numeric defaults."""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import declarative_base

from core.sqlite_schema_repair import ensure_sqlite_columns


def test_missing_integer_column_gets_a_numeric_default():
    base = declarative_base()

    class Probe(base):
        __tablename__ = "repair_probe"
        id = Column(String, primary_key=True)
        revision = Column(Integer, nullable=False, default=0)

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE repair_probe (id TEXT PRIMARY KEY)"))

    ensure_sqlite_columns(engine, Probe)

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO repair_probe (id) VALUES ('a')"))
        value, kind = conn.execute(text(
            "SELECT revision, typeof(revision) FROM repair_probe")).one()
    assert value == 0
    assert kind == "integer"
