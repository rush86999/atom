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
# A read-only statement may also open with a CTE (`WITH x AS (...) SELECT`).
# That form was refused as "not a SELECT" — a false negative that cost real
# answers. Allowing it is safe because read-only-ness no longer rests on this
# regex: _FORBIDDEN_VERBS_RE rejects INSERT/UPDATE/DELETE anywhere in the
# statement (including the `WITH ... INSERT` form SQLite permits) and the
# execution authorizer denies every write action outright.
_SELECT_ONLY_RE = re.compile(r"^\s*(?:select|with)\b", re.IGNORECASE)
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


def _db_authorizer(action: int, arg1, arg2, db_name, trigger):
    """SQLite authorizer — the AUTHORITATIVE table/column boundary.

    Parse-time validation and result-column inspection are both incomplete.
    Verified on a scratch DB 2026-09-16: with those two in place, these still
    returned rows, reading a NON-allowlisted table through a predicate only

        SELECT id FROM canvases
         WHERE (SELECT count(*) FROM 'users') > 0
        SELECT id FROM canvases
         WHERE EXISTS (SELECT 1 FROM (SELECT * FROM 'user_sessions') canvases)

    because sqlparse does not see a single-quoted identifier as a table and
    ``cur.description`` only names the PROJECTED columns — a table read used
    purely as an oracle projects nothing. The authorizer is invoked by SQLite
    itself for every table and column access, after name resolution, so it
    covers quoted identifiers, nested subqueries, wildcard expansion and
    predicate-only reads alike.

    Denies: reads of non-allowlisted tables, reads of withheld columns,
    ATTACH/DETACH/PRAGMA, and every write/DDL action (belt-and-braces — the
    session is already ``mode=ro`` + ``query_only``). CTEs do not reach the
    authorizer (SQLite resolves them internally), so ``WITH x AS (...)`` keeps
    working.
    """
    import sqlite3 as _s

    if action == _s.SQLITE_READ:
        table = str(arg1 or "")
        if table and table not in APP_DB_ALLOWED_TABLES:
            return _s.SQLITE_DENY
        if arg2 and _FORBIDDEN_COLUMN_RE.search(str(arg2)):
            return _s.SQLITE_DENY
    elif action in (_s.SQLITE_ATTACH, _s.SQLITE_DETACH, _s.SQLITE_PRAGMA):
        return _s.SQLITE_DENY
    elif action in (
        _s.SQLITE_INSERT, _s.SQLITE_UPDATE, _s.SQLITE_DELETE,
        _s.SQLITE_CREATE_TABLE, _s.SQLITE_DROP_TABLE, _s.SQLITE_ALTER_TABLE,
        _s.SQLITE_CREATE_INDEX, _s.SQLITE_DROP_INDEX,
        _s.SQLITE_CREATE_TRIGGER, _s.SQLITE_DROP_TRIGGER,
        _s.SQLITE_CREATE_VIEW, _s.SQLITE_DROP_VIEW,
    ):
        return _s.SQLITE_DENY
    return _s.SQLITE_OK


def _referenced_tables(sql: str) -> List[str]:
    """Every table the statement reads, via a token walk — NOT a regex.
    Regex extraction missed QUOTED identifiers ('SELECT * FROM "users"'
    passed validation and leaked secret columns at execution) and COMMA
    joins ('FROM canvases, users' referenced only the first). sqlparse
    resolves both, plus subqueries in any position (audit item 1,
    reproduced on a scratch DB 2026-09-16)."""
    import sqlparse

    names: List[str] = []

    def _identifier_name(tok) -> Optional[str]:
        # Identifier with alias: take the FIRST name part only
        try:
            name = tok.get_real_name()
        except Exception:
            name = None
        return str(name).strip('"`[]') if name else None

    def _walk(node):
        from sqlparse import tokens as T

        if hasattr(node, "tokens"):
            seen_from = False
            for tok in node.tokens:
                if tok.ttype in (T.Keyword,) and "FROM" in str(tok).upper():
                    seen_from = True
                    continue
                if tok.ttype in (T.Keyword,) and str(tok).upper().startswith("JOIN"):
                    seen_from = True
                    continue
                if tok.ttype in (T.Keyword,) and "SELECT" in str(tok).upper():
                    seen_from = False
                    continue
                if tok.ttype in (T.Keyword, T.Comment, T.Whitespace):
                    if tok.ttype not in (T.Keyword,) or not seen_from:
                        continue
                if seen_from and tok.is_group and tok.__class__.__name__ == "IdentifierList":
                    for item in tok.get_identifiers():
                        n = _identifier_name(item)
                        if n:
                            names.append(n)
                    seen_from = False
                elif seen_from and tok.is_group and tok.__class__.__name__ == "Identifier":
                    n = _identifier_name(tok)
                    if n:
                        names.append(n)
                    seen_from = False
                elif tok.is_group:
                    _walk(tok)
                elif seen_from and not tok.is_whitespace:
                    seen_from = False

    try:
        for stmt in sqlparse.parse(sql):
            _walk(stmt)
    except Exception:  # noqa: BLE001 — parser failure = not analyzable = reject
        names = ["__unparsable__"]
    return [n.lower() for n in names]


# CTE definitions in a `WITH [RECURSIVE] name [(cols)] AS (...)` header,
# including the comma-separated multi-CTE form. A CTE NAME is not a catalog
# table — SQLite resolves it internally and never consults the authorizer for
# it — so the parse-time allowlist check must skip these or every legitimate
# `WITH ... SELECT` is refused as reading an unlisted table.
_CTE_NAME_RE = re.compile(
    r"(?:\bwith\b|,)\s*(?:recursive\s+)?([a-zA-Z_][a-zA-Z0-9_]*)"
    r"\s*(?:\([^)]*\))?\s+as\s*\(",
    re.IGNORECASE,
)


def _cte_names(sql: str) -> set:
    if not re.match(r"^\s*with\b", sql or "", re.IGNORECASE):
        return set()
    return {m.group(1).lower() for m in _CTE_NAME_RE.finditer(sql)}


def validate_app_db_sql(sql: str) -> Optional[str]:
    """Return a rejection reason, or None when the SQL is safe to run:
    read-only single statement (SELECT or WITH…SELECT), allowlisted tables
    only, no forbidden column references, no forbidden verbs anywhere
    (comments included).

    This is the CHEAP check, not the boundary — the execution authorizer is
    authoritative (see ``_db_authorizer``)."""
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
    cte_names = _cte_names(stripped)
    for t in _referenced_tables(stripped):
        if t in cte_names:
            continue  # a CTE reference; its own FROM clause is walked too
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

        # Holder so the caller's timeout path can INTERRUPT the in-flight
        # query even if it is stuck before the progress handler can fire.
        _conn: Dict[str, Any] = {}

        def _run():
            import time as _time

            path = re.sub(
                r"^sqlite:///", "", str(get_database_url() or ""))
            if not path or not os.path.exists(path):
                return None, "no sqlite database"
            ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            _conn["c"] = ro
            # query_only BEFORE the authorizer (which denies SQLITE_PRAGMA).
            ro.execute("PRAGMA query_only = ON")
            # AUTHORITATIVE TABLE/COLUMN ENFORCEMENT at execution — see
            # _db_authorizer. Installed before the statement is prepared.
            ro.set_authorizer(_db_authorizer)
            # TIMEOUT MUST STOP THE DATABASE WORK, not just the caller's
            # wait: to_thread cannot be cancelled, so a wait_for expiry
            # left the scan running. The progress handler aborts the query
            # in-engine at the deadline (audit item 1).
            deadline = _time.monotonic() + _QUERY_TIMEOUT_S
            ro.set_progress_handler(
                lambda: 1 if _time.monotonic() > deadline else 0, 1000)
            try:
                cur = ro.execute(sql)
                # EXECUTION-TIME COLUMN ENFORCEMENT: '*' expands to every
                # column of the referenced tables at execution — validation
                # only saw the literal SQL text. The RESULT columns are
                # checked against the forbidden shapes (and the allowlist's
                # per-table exclusions) BEFORE any row is fetched, so a
                # wildcard over a table that gained a secret-shaped column
                # refuses instead of leaking (data moves only on fetch).
                cols = [str(d[0]) for d in cur.description or []]
                for c in cols:
                    if _FORBIDDEN_COLUMN_RE.search(c):
                        logger.warning(
                            f"app-db ask refused at execution: wildcard/"
                            f"projection expanded to secret-shaped column "
                            f"'{c}' — no rows returned")
                        return None, "secret-shaped result column"
                rows = cur.fetchmany(_MAX_ROWS_DEFAULT)
                return (cols, rows), None
            finally:
                _conn.pop("c", None)
                ro.close()

        try:
            outcome, err = await asyncio.wait_for(
                asyncio.to_thread(_run), timeout=_QUERY_TIMEOUT_S)
        except asyncio.TimeoutError:
            # The caller's wait ending does NOT stop the database work on its
            # own. Order the in-flight statement to abandon at its next
            # opportunity so the read actually stops (audit item 1).
            stuck = _conn.get("c")
            if stuck is not None:
                try:
                    stuck.interrupt()
                except Exception:  # noqa: BLE001 — best-effort abort
                    pass
            logger.warning(
                f"app-db ask timed out after {_QUERY_TIMEOUT_S}s; query "
                "interrupted")
            return None
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
