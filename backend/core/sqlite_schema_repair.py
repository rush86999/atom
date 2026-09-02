"""Lightweight SQLite schema drift repair for hot-path tables.

The Personal Edition ships a SQLite file whose schema can lag the SQLAlchemy
models (models gain columns; alembic isn't always run on a local dev DB).
When that happens every ORM INSERT for the drifted table fails — e.g.
``agent_reasoning_steps`` lacked ``requested_model``/``resolved_model``, so
NO reasoning step ever persisted and the Agent Workspace "Tasks" panel was
permanently empty (including the pre-existing meta-agent path).

``ensure_sqlite_columns()`` compares the live table's columns against the
model and ALTERs the missing ones in. Idempotent, best-effort, and safe on
PostgreSQL (no-op — alembic owns schema there).
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_REPAIRED: set = set()


def _sqlite_column_ddl(col: Any) -> str | None:
    """Best-effort DDL type for a model column (SQLite is dynamically typed;
    the declared affinity only matters for new rows)."""
    try:
        from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, JSON
        t = col.type
        if isinstance(t, (String, Text, JSON)):
            return "TEXT"
        if isinstance(t, Boolean):
            return "BOOLEAN"
        if isinstance(t, Integer):
            return "INTEGER"
        if isinstance(t, Float):
            return "REAL"
        if isinstance(t, DateTime):
            return "DATETIME"
        return "TEXT"
    except Exception:
        return "TEXT"


def ensure_sqlite_columns(engine: Any, model: Any) -> None:
    """Add model columns missing from the model's SQLite table."""
    key = (str(engine.url), model.__tablename__)
    if key in _REPAIRED:
        return
    _REPAIRED.add(key)
    try:
        if engine.dialect.name != "sqlite":
            return
        from sqlalchemy import inspect, text

        insp = inspect(engine)
        if not insp.has_table(model.__tablename__):
            return  # Base.metadata.create_all owns missing tables
        existing = {c["name"] for c in insp.get_columns(model.__tablename__)}
        missing = [
            (name, col)
            for name, col in model.__table__.columns.items()
            if name not in existing
        ]
        for name, col in missing:
            nullable = "NULL" if col.nullable else "NOT NULL DEFAULT ''"
            ddl = _sqlite_column_ddl(col) or "TEXT"
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE {model.__tablename__} ADD COLUMN {name} {ddl} {nullable}"
                ))
            logger.info(f"schema repair: added {model.__tablename__}.{name}")
    except Exception as e:
        # Best-effort: a failed repair must never block startup.
        logger.warning(f"schema repair skipped for {model.__tablename__}: {e}")


def repair_known_drift() -> None:
    """Repair the known-drifted hot-path tables. Call once at app startup."""
    try:
        from core.database import get_db_session
        from core.models import (
            AgentReasoningStep,
            ExperienceItem,
            Playbook,
        )

        with get_db_session() as db:
            engine = db.get_bind()
            ensure_sqlite_columns(engine, AgentReasoningStep)
            # WikiSkill columns on tables create_all can't alter (W5/W6):
            # playbooks.last_eval_result, experience_items.source_model /
            # validation_state — see 20260902_wikiskill_adaptation.
            ensure_sqlite_columns(engine, Playbook)
            ensure_sqlite_columns(engine, ExperienceItem)
    except Exception as e:
        logger.warning(f"known-drift repair skipped: {e}")
