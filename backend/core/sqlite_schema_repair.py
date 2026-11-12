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
_TOKEN_USAGE_UPGRADE_FAILURE: str | None = None


def _q(name: Any) -> str:
    """Quote one SQLite identifier from inspected schema."""
    return '"' + str(name).replace('"', '""') + '"'


def token_usage_upgrade_failure_reason() -> str | None:
    """Non-None when the durable ledger upgrade could not complete."""
    return _TOKEN_USAGE_UPGRADE_FAILURE


def _clear_token_usage_upgrade_failure() -> None:
    global _TOKEN_USAGE_UPGRADE_FAILURE
    _TOKEN_USAGE_UPGRADE_FAILURE = None



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
        from sqlalchemy import Integer, inspect, text

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
            if col.nullable:
                nullable = "NULL"
            elif isinstance(col.type, Integer):
                # SQLite stores '' as TEXT even in an INTEGER column. A
                # numeric NOT NULL column must default to a number, or every
                # pre-existing row reads back as '' and integer CAS filters
                # (e.g. goal_runs.material_revision) stop matching.
                nullable = "NOT NULL DEFAULT 0"
            else:
                nullable = "NOT NULL DEFAULT ''"
            ddl = _sqlite_column_ddl(col) or "TEXT"
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE {model.__tablename__} ADD COLUMN {name} {ddl} {nullable}"
                ))
            logger.info(f"schema repair: added {model.__tablename__}.{name}")
    except Exception as e:
        # Best-effort: a failed repair must never block startup.
        logger.warning(f"schema repair skipped for {model.__tablename__}: {e}")


def ensure_token_usage_upgrade(engine: Any) -> None:
    """Idempotent SQLite rebuild for the durable TokenUsage ledger.

    ``ensure_sqlite_columns`` can only ADD COLUMN. The pre-upgrade ledger has
    NOT NULL agent_id/tenant_id/model_name, so non-agent/unknown-scope
    settlement would fail on an upgraded install. SQLite cannot drop NOT NULL
    in place: rebuild the table, copy every existing column (rows/IDs/values,
    including a partially-upgraded ``pricing_status`` and any custom columns),
    preserve explicit indexes and FK clauses, recreate the unique attempt_id
    index, then rename. Runs only inside the existing startup repair hook; no
    separate migration engine. PostgreSQL is left to Alembic.

    The repaired key is recorded only AFTER success, so a failed migration can
    retry in-process. On failure the process-local failure reason makes a hard
    stop refuse (BUDGET_STATUS_UNAVAILABLE) rather than operating on a ledger
    that cannot represent the new contract.
    """
    key = (str(engine.url), "token_usage_rebuild_v1")
    if key in _REPAIRED:
        return
    try:
        if engine.dialect.name != "sqlite":
            _REPAIRED.add(key)
            _clear_token_usage_upgrade_failure()
            return
        from sqlalchemy import inspect

        insp = inspect(engine)
        if not insp.has_table("token_usage"):
            _REPAIRED.add(key)
            _clear_token_usage_upgrade_failure()
            return  # create_all owns missing tables
        columns = {c["name"]: c for c in insp.get_columns("token_usage")}
        needs_nullable = any(
            name in columns and columns[name].get("nullable") is False
            for name in ("agent_id", "tenant_id", "model_name")
        )
        needs_columns = any(
            name not in columns
            for name in ("provider_id", "request_id", "attempt_id",
                         "pricing_status", "reserved_cost_usd",
                         "reservation_status")
        )
        if not needs_nullable and not needs_columns:
            _REPAIRED.add(key)
            _clear_token_usage_upgrade_failure()
            return

        base_columns = [
            ("id", "VARCHAR NOT NULL PRIMARY KEY"),
            ("agent_id", "VARCHAR"),
            ("workspace_id", "VARCHAR"),
            ("tenant_id", "VARCHAR"),
            ("execution_id", "VARCHAR"),
            ("chain_id", "VARCHAR"),
            ("provider_id", "VARCHAR(100)"),
            ("request_id", "VARCHAR(255)"),
            ("attempt_id", "VARCHAR(255)"),
            ("prompt_tokens", "INTEGER"),
            ("completion_tokens", "INTEGER"),
            ("total_tokens", "INTEGER"),
            ("billed", "BOOLEAN"),
            ("cost_usd", "FLOAT"),
            ("pricing_status", "VARCHAR(20) NOT NULL DEFAULT 'priced'"),
            ("reserved_cost_usd", "FLOAT DEFAULT 0.0"),
            ("reservation_status", "VARCHAR(20) NOT NULL DEFAULT 'none'"),
            ("memory_mb", "FLOAT"),
            ("model_name", "VARCHAR"),
            ("timestamp", "DATETIME"),
        ]
        base_names = {name for name, _ddl in base_columns}
        extra_columns = [name for name in columns if name not in base_names]

        # Preserve every existing FK, then add the known model FKs if the
        # legacy table did not declare them. Unknown/custom columns above are
        # carried as TEXT so their indexes and rows survive the rebuild.
        fk_tuples: list[tuple[str, str, str]] = []
        try:
            for fk in insp.get_foreign_keys("token_usage"):
                cols = fk.get("constrained_columns") or []
                ref_table = fk.get("referred_table")
                ref_cols = fk.get("referred_columns") or []
                if len(cols) == 1 and ref_table and len(ref_cols) == 1:
                    fk_tuples.append((cols[0], ref_table, ref_cols[0]))
        except Exception as fk_err:
            logger.warning(
                "token_usage FK inspection failed (%s)",
                type(fk_err).__name__)
        for known_fk in (
            ("agent_id", "agent_registry", "id"),
            ("workspace_id", "workspaces", "id"),
            ("execution_id", "agent_executions", "id"),
            ("chain_id", "delegation_chains", "id"),
        ):
            if known_fk not in fk_tuples:
                fk_tuples.append(known_fk)

        with engine.begin() as conn:
            old_indexes = [
                row[0] for row in conn.exec_driver_sql(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type='index' AND tbl_name='token_usage' "
                    "AND sql IS NOT NULL AND name NOT LIKE 'sqlite_autoindex%'"
                ).fetchall() if row[0]
            ]
            column_defs = [
                f"{_q(name)} {ddl}" for name, ddl in base_columns
            ]
            column_defs += [
                f"{_q(name)} TEXT" for name in extra_columns
            ]
            column_defs += [
                f"FOREIGN KEY({_q(col)}) "
                f"REFERENCES {_q(table)}({_q(ref)})"
                for col, table, ref in fk_tuples
            ]
            conn.exec_driver_sql(
                "CREATE TABLE token_usage_new ("
                + ", ".join(column_defs) + ")"
            )
            common = list(columns)
            select_exprs = [
                (f"COALESCE({_q(name)}, 'priced')"
                 if name == "pricing_status" else _q(name))
                for name in common
            ]
            if common:
                conn.exec_driver_sql(
                    "INSERT INTO token_usage_new ("
                    + ", ".join(_q(name) for name in common) + ") "
                    "SELECT " + ", ".join(select_exprs)
                    + " FROM token_usage")
            conn.exec_driver_sql("DROP TABLE token_usage")
            conn.exec_driver_sql(
                "ALTER TABLE token_usage_new RENAME TO token_usage")
            for sql in old_indexes:
                try:
                    conn.exec_driver_sql(sql)
                except Exception as idx_err:
                    if "already exists" in str(idx_err).lower():
                        continue
                    logger.error(
                        "token_usage upgrade: failed to recreate a "
                        "pre-existing index (%s)", type(idx_err).__name__)
                    # Roll the rebuild back rather than silently losing a
                    # pre-existing index.
                    raise
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_token_usage_attempt_id ON token_usage(attempt_id)")
            for name, column in (
                ("ix_token_usage_agent_id", "agent_id"),
                ("ix_token_usage_workspace_id", "workspace_id"),
                ("ix_token_usage_tenant_id", "tenant_id"),
                ("ix_token_usage_chain_id", "chain_id"),
                ("ix_token_usage_provider_id", "provider_id"),
                ("ix_token_usage_request_id", "request_id"),
                ("ix_token_usage_pricing_status", "pricing_status"),
                ("ix_token_usage_reservation_status", "reservation_status"),
            ):
                conn.exec_driver_sql(
                    f"CREATE INDEX IF NOT EXISTS {name} "
                    f"ON token_usage({_q(column)})")
        _REPAIRED.add(key)
        _clear_token_usage_upgrade_failure()
        logger.info(
            "schema repair: rebuilt token_usage for nullable/unknown settlement")
    except Exception as e:
        # Startup must not be blocked, but the ledger is NOT usable under the
        # new contract. Record a process-local failure so hard-stop refuses;
        # do not mark _REPAIRED, so a later in-process repair can retry.
        global _TOKEN_USAGE_UPGRADE_FAILURE
        _TOKEN_USAGE_UPGRADE_FAILURE = (
            f"upgrade_failed:{type(e).__name__}")
        logger.error(
            "token_usage upgrade failed; hard-stop will refuse until it is "
            "available (%s)", type(e).__name__)



def repair_known_drift() -> None:
    """Repair the known-drifted hot-path tables. Call once at app startup."""
    try:
        from core.database import get_db_session
        from core.models import (
            AgentReasoningStep,
            AgentRegistry,
            AgentTemplate,
            Canvas,
            ExperienceItem,
            GoalRun,
            Playbook,
            TaskOperationRecord,
            TokenUsage,
        )

        with get_db_session() as db:
            engine = db.get_bind()
            # Durable usage ledger: relax legacy NOT NULL agent/tenant/model
            # and add provider/request/attempt/pricing_status before
            # create_all (which cannot alter an existing table).
            ensure_token_usage_upgrade(engine)
            ensure_sqlite_columns(engine, TokenUsage)
            ensure_sqlite_columns(engine, AgentReasoningStep)
            # WikiSkill columns on tables create_all can't alter (W5/W6):
            # playbooks.last_eval_result, experience_items.source_model /
            # validation_state — see 20260902_wikiskill_adaptation.
            ensure_sqlite_columns(engine, Playbook)
            ensure_sqlite_columns(engine, ExperienceItem)
            # Goal-run back-links on the pre-existing canvases table, and the
            # goal_runs table itself (create_all makes the table; this makes
            # its columns safe on drifted files) — see
            # docs/architecture/GOAL_RUN_ORCHESTRATION.md.
            ensure_sqlite_columns(engine, Canvas)
            ensure_sqlite_columns(engine, GoalRun)
            # task_operation_records.result_json: durable exact provider
            # identity/material for a confirmed effect, so a replay can re-read
            # the same resource instead of guessing or permanently downgrading
            # a known success. Local SQLite files predate this column.
            ensure_sqlite_columns(engine, TaskOperationRecord)
            # agent_templates.verified_record (goal-run evidence on sellable
            # listings) — see 20260912_agent_verified_record.
            ensure_sqlite_columns(engine, AgentTemplate)
            # agent_registry.promotion_episode_floor (user-tunable promotion
            # floor added 2026-09-23 with no Alembic migration). A legacy
            # SQLite file lacks the column, and every ORM read of the table —
            # including startup's ensure_admin_user → ensure_demo_agent and
            # GET /api/agents/{id} — fails with "no such column:
            # agent_registry.promotion_episode_floor". The generic model-column
            # repair adds only what the model has and the table lacks.
            ensure_sqlite_columns(engine, AgentRegistry)

            # Marketing intelligence models (marketing/models.py) carry
            # workspace_id, but pre-existing SQLite files were created from
            # the older tenant-scoped shape. Every /api/marketing/dashboard
            # query then died with "no such column:
            # marketing_channels.workspace_id". Repair the three tables the
            # dashboard reads.
            try:
                from marketing.models import (
                    AdSpendEntry,
                    AttributionEvent,
                    MarketingChannel as MarketingChannelModel,
                )

                ensure_sqlite_columns(engine, MarketingChannelModel)
                ensure_sqlite_columns(engine, AdSpendEntry)
                ensure_sqlite_columns(engine, AttributionEvent)
            except Exception as marketing_err:
                logger.warning(
                    "marketing schema repair skipped: %s", marketing_err)
    except Exception as e:
        logger.warning(f"known-drift repair skipped: {e}")
