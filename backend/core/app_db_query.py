# -*- coding: utf-8 -*-
"""Read-only natural-language SQL over the ATOM application database.

The same NL→SQL primitive the dataset lane uses (answer_from_datasets,
DuckDB over materialized spreadsheets), extended to the app's OWN
operational data (canvases, chat sessions, agents, goals/runs, workflow
runs, approvals/interventions, accounting). The generator half existed
orphaned (core.schema_aware_sql_generator — SELECT-only + workspace
injection, zero callers); this is the completion with the safety envelope
that raw wiring would have lacked:

- TABLE ALLOWLIST: only business-operational tables are describable or
  queryable. Secrets/credential tables (integration_tokens), auth tables
  (users), tenancy/config plumbing — rejected BEFORE the LLM ever sees a
  schema, and again at execution.
- COLUMN STRIPPING: within allowed tables, secret-shaped AND scope-shaped
  columns (tenant_id/workspace_id) are never described, so the LLM cannot
  name them; any reference fails validation.
- SELECT-ONLY + single statement + no DDL/DML verbs, enforced by parse,
  not by prompt.
- NO SQL PREDICATE INJECTION, deliberately. This is a single-tenant app and
  the scope columns are sparsely populated (53/76 canvases have a NULL
  workspace_id), so `WHERE workspace_id = ...` would undercount the
  operator's OWN data rather than isolate anything. Isolation here comes
  from the table allowlist plus withholding the scope columns; every row in
  an allowlisted table belongs to this install.
- Caps: LIMIT injected when absent (default 50), query timeout.
- Read-only session: SQLite opens mode=ro; the executor refuses to run
  on anything but a SELECT plan.
"""
import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Business-operational tables the agent may ask about. Anything not here
# is rejected — by default the app DB is NOT queryable. Keep this list
# SHORT and intentional; adding a table is a reviewable security decision.
APP_DB_ALLOWED_TABLES: Dict[str, Optional[List[str]]] = {
    # value = columns to EXCLUDE (secret-shaped); None = whole table ok
    "canvases": None,
    "canvas_audit": None,
    "chat_sessions": None,
    "chat_messages": None,
    "agent_registry": None,
    "goal_runs": None,
    "workflow_runs": None,
    "action_proposals": None,
    "interventions": None,
    "intervention_outcomes": None,
    "playbooks": None,
    "accounting_invoices": None,
    "accounting_bills": None,
    "accounting_transactions": None,
    "document_ingestions": None,
    "dataset_entries": None,
    "llm_routing_feedback": None,
    "verify_panel_runs": None,
}
# Column-name shapes that never get described or selected, in ANY table.
# Tenant/workspace scoping columns are included on purpose: this is a
# SINGLE-TENANT app (CLAUDE.md — tenant plumbing is a SaaS-parity shim, not the
# deployment model) and the scope columns are NOT reliably populated (53 of 76
# canvases carry a NULL workspace_id, measured live 2026-09-15), so a
# `WHERE workspace_id = 'default'` predicate does not isolate anything — it
# silently DROPS rows and undercounts (76 -> 23). Withholding the columns
# instead keeps every row the operator owns visible (the truthful answer), and
# leaves no scope value for the LLM to filter on.
_FORBIDDEN_COLUMN_RE = re.compile(
    r"(token|secret|password|credential|api_key|private"
    r"|tenant_id|workspace_id)", re.IGNORECASE
)
_SELECT_ONLY_RE = re.compile(r"^\s*select\b", re.IGNORECASE)
_FORBIDDEN_VERBS_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|pragma|"
    r"vacuum|reindex|grant)\b", re.IGNORECASE)
_MAX_ROWS_DEFAULT = int(os.getenv("ATOM_APP_DB_MAX_ROWS", "50") or 50)
_QUERY_TIMEOUT_S = float(os.getenv("ATOM_APP_DB_TIMEOUT_S", "8") or 8)


def _strip_forbidden_columns(table: str, columns: List[str]) -> List[str]:
    kept = [c for c in columns if not _FORBIDDEN_COLUMN_RE.search(c)]
    excluded = [c for c in columns if _FORBIDDEN_COLUMN_RE.search(c)]
    if excluded:
        logger.info(
            f"app-db ask: {len(excluded)} withheld column(s) of "
            f"{table} withheld from the schema prompt")
    return kept


def _referenced_tables(sql: str) -> List[str]:
    return [t.lower() for t in re.findall(
        r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE)]


def validate_app_db_sql(sql: str) -> Optional[str]:
    """Return a rejection reason, or None when the SQL is safe to run:
    SELECT-only single statement, allowlisted tables only, no forbidden
    column references, no forbidden verbs anywhere (comments included)."""
    stripped = (sql or "").strip().rstrip(";").strip()
    if not stripped:
        return "empty sql"
    if ";" in stripped:
        return "multiple statements are not allowed"
    if not _SELECT_ONLY_RE.match(stripped):
        return "only SELECT statements are allowed"
    m = _FORBIDDEN_VERBS_RE.search(stripped)
    if m:
        return f"forbidden verb: {m.group(1)}"
    for t in _referenced_tables(stripped):
        if t not in APP_DB_ALLOWED_TABLES:
            return f"table not in the app-db allowlist: {t}"
    for col in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", stripped):
        if _FORBIDDEN_COLUMN_RE.search(col):
            return f"withheld column reference: {col}"
    return None


def _schema_lines() -> List[str]:
    """Allowlisted tables with secret-shaped columns stripped — the ONLY
    schema the LLM ever sees for app-db asks."""
    from core.database import get_db_session
    from sqlalchemy import inspect as sa_inspect

    lines = []
    with get_db_session() as db:
        insp = sa_inspect(db.get_bind())
        for table in APP_DB_ALLOWED_TABLES:
            try:
                cols = [c["name"] for c in insp.get_columns(table)]
            except Exception:
                continue  # table absent in this install
            kept = _strip_forbidden_columns(table, cols)
            lines.append(f"{table}({', '.join(kept)})")
    return lines


def _extract_sql(value: Any) -> str:
    """Pull the SQL statement out of whatever the structured call handed back.

    ``pinned_structured_call``'s contract is "an instance of response_model, or
    None", but providers differ in how strictly they enforce it: one returns the
    parsed object, another returns the raw JSON STRING it produced, and a third
    nests the envelope inside the field — so ``result.sql`` can literally be
    ``{"sql": "SELECT ..."}``. Unwrapped here, the value is then rejected by
    ``validate_app_db_sql`` for not starting with SELECT, which reads in the logs
    as "the model wrote bad SQL" when the model was fine (observed live
    2026-09-15: the same question answered correctly, then refused as
    "only SELECT statements are allowed"). Normalize at the consumer — this is
    the one place that must accept every provider's shape.
    """
    if value is None:
        return ""
    if isinstance(value, dict):  # a dict result, or the nested envelope
        for key in ("sql", "query", "statement"):
            if key in value:
                return _extract_sql(value[key])
        return ""
    text = str(value).strip()
    if not text:
        return ""
    # Fenced output: ```sql SELECT ... ``` / ```json {"sql": ...} ```
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    # The envelope leaked into the field (valid, malformed, or single-quoted).
    if text.lstrip().startswith("{"):
        try:
            import json

            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return _extract_sql(parsed)
        except Exception:  # noqa: BLE001 — fall through to the tolerant scrape
            m = re.search(
                r'["\']?(?:sql|query|statement)["\']?\s*:\s*["\'](.+?)["\']\s*\}?\s*$',
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if m:
                return m.group(1).strip()
        return ""
    return text


async def answer_from_app_db(
    question: str,
    workspace_id: Optional[str],
    tenant_id: str = "default",
    llm_service: Any = None,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Answer a natural-language question over ALLOWLISTED app tables.

    Flow: schema prompt (allowed tables, permitted columns only, no
    secrets anywhere) → BPC-routed structured call (dataset/nl2sql task
    shaping) → validate (allowlist, SELECT-only, columns) → inject
    workspace/tenant predicates + LIMIT → execute on a READ-ONLY session
    → {sql, columns, rows} or None (refused / empty / any error — the
    caller falls back to other lanes)."""
    if not question or llm_service is None:
        return None
    reason = None
    try:
        import sqlparse

        schema_lines = await asyncio.wait_for(
            asyncio.to_thread(_schema_lines), timeout=5)
        if not schema_lines:
            return None
        prompt = (
            "You generate ONE read-only SQLite SELECT for the user's "
            "question. Schema (ONLY these tables; ONLY the listed "
            "columns; tenant scoping is injected for you — do NOT add "
            "tenant/workspace filters yourself):\n"
            + "\n".join(schema_lines)
            + "\n\nRules: SELECT only; end with no semicolon; use "
            f"LIMIT (max {_MAX_ROWS_DEFAULT}); never invent columns. "
            "Return JSON {\"sql\": \"...\"} only.\n\nQuestion: "
            + question[:400]
        )
        from core.llm.pinned_planning import pinned_structured_call

        class _SQL(BaseModel):
            sql: str = ""

        result = await asyncio.wait_for(
            pinned_structured_call(
                llm_service, prompt=prompt, response_model=_SQL,
                call_kwargs={"task_type": "nl2sql"},
                system_instruction="You return only the requested JSON object.",
            ),
            timeout=12,
        )
        sql = _extract_sql(getattr(result, "sql", None) if result is not None else None)
        if not sql:
            return None
        reason = validate_app_db_sql(sql)
        if reason:
            logger.warning(f"app-db ask refused ({reason}): {sql[:160]}")
            return None
        # Scope columns are withheld from the schema entirely; a model that
        # names one anyway is off-script (or probing), so refuse rather than
        # trust prompt-layer scoping.
        parsed = sqlparse.parse(sql)
        if not parsed:
            return None
        sql = str(parsed[0]).strip().rstrip(";")
        low = sql.lower()
        if "tenant_id" in low or "workspace_id" in low:
            logger.warning("app-db ask refused: model-named scope column")
            return None
        if "limit" not in low:
            sql += f" LIMIT {_MAX_ROWS_DEFAULT}"
        # execute READ-ONLY
        import sqlite3

        from core.database import get_database_url

        def _run():
            path = re.sub(
                r"^sqlite:///", "", str(get_database_url() or ""))
            if not path or not os.path.exists(path):
                return None, "no sqlite database"
            ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            ro.execute("PRAGMA query_only = ON")
            try:
                cur = ro.execute(sql)
                cols = [d[0] for d in cur.description or []]
                rows = cur.fetchmany(_MAX_ROWS_DEFAULT)
                return (cols, rows), None
            finally:
                ro.close()

        outcome, err = await asyncio.wait_for(
            asyncio.to_thread(_run), timeout=_QUERY_TIMEOUT_S)
        if err or not outcome:
            return None
        cols, rows = outcome
        return {
            "question": question[:200],
            "sql": sql,
            "columns": cols,
            "rows": [list(r) for r in (rows or [])],
            "row_count": len(rows or []),
        }
    except Exception as e:  # noqa: BLE001 — refusal/timeout = no answer
        logger.info(f"app-db ask skipped ({reason or 'error'}): {e}")
        return None
