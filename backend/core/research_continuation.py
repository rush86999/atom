# -*- coding: utf-8 -*-
"""Durable research continuation — finish authorized read jobs after the
interactive turn ends (rounds 52-53).

Substrate: the recurring-task pattern of async_turn_continuation's
terminal-delivery recovery — a lifespan-started loop reading DURABLE
state (the job-work ledger), independent of the scheduler, surviving
restarts.

Round 53 corrections (reviewer):
- PER-ITEM EVIDENCE: a document-level receipt never resolves grouped
  items. Each item is matched individually against structured find_all
  results; only a match carrying the item's own price/value (price-shaped
  column or value) resolves it. Identity-only matches ("located") and
  no-matches leave the question open with the exact next step recorded.
- DURABLE CLAIMS: execution claims live on the questions themselves
  (claim_questions_for_execution, TTL-bounded) — attempt counters are
  retry bounds, not locks. Eligibility is RE-CHECKED against the task
  revision immediately before execution, and jobs whose session ends
  with an unanswered user message are skipped (the interactive lane
  owns them).
- GLOBAL CYCLE BUDGET: at most _CYCLE_MAX_READS document executions per
  CYCLE across all jobs.
- STRUCTURED INPUTS: read actions dispatch from the question's
  structured inputs (item + document) when present; prose is only the
  legacy fallback.
- DELIVERY: the terminal note appends to a FRESHLY re-read session
  history.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_CYCLE_MAX_READS = int(os.getenv("ATOM_RESEARCH_CONTINUATION_MAX_READS",
                                 "4") or 4)
_READ_TIMEOUT_SECONDS = float(
    os.getenv("ATOM_RESEARCH_CONTINUATION_READ_TIMEOUT", "25") or 25)
_INTERVAL_SECONDS = float(
    os.getenv("ATOM_RESEARCH_CONTINUATION_INTERVAL_SECONDS", "45") or 45)
_CLAIM_TTL_SECONDS = float(
    os.getenv("ATOM_RESEARCH_CONTINUATION_CLAIM_TTL", "120") or 120)

_RECOVERY_TASK: "asyncio.Task | None" = None
_WORKER_ID = f"research-worker-{os.getpid()}"

# FIELD SYNONYMS (round 56): requested fields bind to columns by NAME
# meaning — business-neutral. "price" is THIS job's requested field;
# another business passes its own ("lead_time", "labor_rate", ...) and
# adds its synonyms through the same map.
FIELD_SYNONYMS: Dict[str, List[str]] = {
    "price": ["price", "cost", "list", "net", "cad"],
}
# IDENTIFIER COLUMNS (round 56): a header matching these is an
# IDENTIFIER, never a monetary field — "DEALER CODE" contains "dealer"
# but codes people/products, not money. The VALUE must also be
# monetary-shaped; a letter code like "K" can never be a price.
IDENTIFIER_COLUMN_RE = re.compile(
    r"code|no\.?|#|part|model|id\b|serial|sku|ref", re.IGNORECASE)
_MONETARY_VALUE_RE = re.compile(
    r"^[$€£\s]*-?(?:\d{1,3}(?:[,.]\d{3})+|\d+)(?:[.,]\d{1,4})?"
    r"[$€£\s]*$")

_PRICE_COLUMN_RE = re.compile(
    r"price|cost|list|dealer|net\b|cad\b|us\b", re.IGNORECASE)
_PRICE_VALUE_RE = re.compile(
    r"^[$€£\s]*\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{1,2})?[$\s]*$")


def research_continuation_enabled() -> bool:
    return os.getenv(
        "ATOM_RESEARCH_CONTINUATION_DISABLED", "").strip() not in (
        "1", "true", "yes")


def _lifecycle_for_default_tenant():
    from core.database import get_db_session
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle

    return TaskLifecycle(
        GoalRunService(workspace_id="default", tenant_id="default",
                       session_factory=get_db_session),
        GoalService(workspace_id="default", tenant_id="default",
                    session_factory=get_db_session))


def _read_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Eligible read actions, dispatched from STRUCTURED INPUTS when
    present (item + document); prose is the legacy fallback."""
    out = []
    for a in actions or []:
        inputs = a.get("inputs") if isinstance(a.get("inputs"), dict) else {}
        doc = str(inputs.get("file") or "").strip()
        item = str(inputs.get("item") or a.get("item") or "").strip()
        if not doc:
            na = str(a.get("next_action") or "")
            if not na.lower().startswith("read "):
                continue
            doc = na[5:].rsplit(" for ", 1)[0].strip()
            item = item or na[5:].rsplit(" for ", 1)[-1].strip()
        # ROW-READ FIRST (round 54): row successors also carry "file" —
        # the intent must be checked before the document branch consumes
        # them.
        if str(inputs.get("intent") or "") == "row_read" and (
                inputs.get("file") or inputs.get("candidates")):
            if inputs.get("candidates"):
                cands = [
                    {"sheet": str(c.get("sheet") or ""),
                     "row": int(c.get("row") or 0),
                     "identity_column": str(
                         c.get("identity_column") or ""),
                     "identity_cell": str(
                         c.get("identity_cell") or "")}
                    for c in inputs["candidates"] if c.get("row")]
            elif inputs.get("row"):
                cands = [{
                    "sheet": str(inputs.get("sheet") or ""),
                    "row": int(inputs.get("row") or 0),
                    "identity_column": str(
                        inputs.get("identity_column") or ""),
                    "identity_cell": str(
                        inputs.get("identity_cell") or "")}]
            else:
                cands = []
            if cands:
                out.append({
                    "item": item, "file": str(inputs.get("file") or ""),
                    "candidates": cands,
                    "identity_context": str(
                        inputs.get("identity_context") or item),
                    "requested_fields": list(
                        inputs.get("requested_fields") or []),
                    "provenance": dict(
                        inputs.get("provenance") or {}),
                    "intent": "row_read",
                    "question_id": a.get("question_id")})
                continue
        if doc and item:
            out.append({"item": item, "file": doc,
                        "question_id": a.get("question_id")})
    return out


def _classify_match(match: Dict[str, Any]) -> str:
    """"matched" (carries the item's own value), "located" (identity
    only — the price cell was not read), or "" (noise)."""
    column = str(match.get("column") or "")
    value = str(match.get("value") or "")
    if _PRICE_COLUMN_RE.search(column) or (
            value and _PRICE_VALUE_RE.match(value)):
        return "matched"
    return "located"


async def _execute_document_read(
        lifecycle: Any, run_id: str,
        user_id: str, workspace_id: str, file_name: str,
        items: List[str],
        item_identity_context: str = "") -> Dict[str, Any]:
    """One document execution resolving EACH item against its own
    structured find_all matches. Settles on the JOB's run."""
    from core.sheet_dataset_service import find_all_occurrences_sync
    from core.task_lifecycle import (
        finish_retrieval_turn, record_read_outcome)

    statuses: Dict[str, str] = {}
    evidence: List[str] = []
    any_executed = False
    for item in items:
        try:
            scan = await asyncio.wait_for(
                asyncio.to_thread(
                    find_all_occurrences_sync, item, user_id,
                    workspace_id, file_name=file_name, max_matches=8),
                timeout=_READ_TIMEOUT_SECONDS)
            any_executed = True
        except Exception as exc:  # noqa: BLE001 — per-item isolation
            statuses[item] = ""
            evidence.append(f"{item}: lookup failed "
                            f"({type(exc).__name__})")
            continue
        matches = (scan or {}).get("matches") or []
        classified = [(m, _classify_match(m)) for m in matches]
        matched = [m for m, c in classified if c == "matched"]
        if matched:
            statuses[item] = "matched"
            best = matched[0]
            evidence.append(
                f"{item}: price at {best.get('sheet')}/{best.get('cell')}"
                f" = {best.get('value')} (column {best.get('column')})")
        elif classified:
            statuses[item] = "located"
            first = classified[0][0]
            evidence.append(
                f"{item}: located at {first.get('sheet')}/"
                f"{first.get('cell')} (column {first.get('column')}) — "
                "price cell NOT read; question stays open")
        else:
            statuses[item] = ""
            evidence.append(
                f"{item}: no match in this document — question stays open")
        # SUCCESSOR (round 54): a located identity cell spawns the
        # row-context read with complete structured inputs — the next
        # cycle turns the location into evidence instead of repeating
        # the same discovery. Deterministic text dedupes re-location.
        if statuses.get(item) == "located":
            from core.task_lifecycle import add_unresolved_questions

            # ALL candidate locations (round 56, capped at 3): the row
            # read evaluates EVERY candidate under strict identity —
            # the first match is never auto-selected.
            _all_located = [m for m, c in classified if c == "located"]
            cands = _all_located[:3]
            # REQUESTED FIELDS FROM THE JOB (round 56): carried from the
            # task revision — never hardcoded here.
            _job_fields = list(
                ((lifecycle.get_task(run_id) or {}).get(
                    "task_revision") or {}).get("requested_fields")
                or []) or ["price"]
            add_unresolved_questions(lifecycle, run_id, [{
                "item": item,
                "kind": "verification",
                "question": (
                    f"{item}: located at "
                    + ", ".join(
                        f"{m.get('sheet')}/{m.get('cell')}"
                        for m in cands)
                    + " — read the rows' requested fields"),
                "evidence": "identity cells located; fields unread",
                "next_action": (
                    f"read rows "
                    + ", ".join(str(m.get("cell")) for m in cands)
                    + f" of {file_name} for the requested fields"),
                "inputs": {
                    "service": "datasets", "intent": "row_read",
                    "file": file_name,
                    "candidates": [
                        {"sheet": str(m.get("sheet") or ""),
                         "row": int(re.sub(r"\D", "", str(
                             m.get("cell") or "")) or 0),
                         "identity_column": str(m.get("column") or ""),
                         "identity_cell": str(m.get("cell") or "")}
                        for m in cands],
                    "item": item,
                    "identity_context": str(
                        item_identity_context or item),
                    "candidates_total": len(_all_located),
                    "candidates_omitted": max(
                        0, len(_all_located) - len(cands)),
                    "requested_fields": _job_fields,
                },
            }], source_operation=None)

    op = lifecycle.create_operation(
        run_id, op_type="retrieve",
        requested_change=(
            f"research continuation read: {file_name[:120]}"))
    _exec_facts = {
        "invoked": any_executed,
        "outcome": ("read_succeeded" if any(
            s == "matched" for s in statuses.values())
            else "read_returned_no_receipt" if any_executed
            else "read_failed"),
        "served_basis": ("saved_copy" if any_executed else "none"),
        "failure_stage": None,
        "items": statuses,
    }
    finish_retrieval_turn(
        lifecycle, run_id, op["operation_id"], {}, None,
        bool(_exec_facts["outcome"] == "read_succeeded"),
        execution=_exec_facts)
    record_read_outcome(
        lifecycle, run_id, op["operation_id"], structured_result=None,
        freshness=None, execution=_exec_facts)
    return {"file": file_name, "statuses": statuses,
            "evidence": evidence}


def _norm_token(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _item_code_tokens(item: str) -> List[str]:
    """The CODE-SHAPED tokens of an item identity ('No. 381' -> '381';
    'Linmac U-22 bead roller' -> ['linmac', 'u22']). Code-shaped: has a
    digit and length >= 2, or is an alphanumeric-with-hyphen form."""
    toks = re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", str(item))
    return [t for t in toks
            if (any(c.isdigit() for c in t) and len(t) >= 2)
            or re.match(r"^[A-Za-z]+-\d+$", t)]


def _identity_supported(
        row: Dict[str, Any], identity_column: str, item: str,
        identity_context: str) -> bool:
    # CORROBORATION MODE (round 58): a taught-location read carries no
    # identity COLUMN — identity is established when ANY cell equals a
    # code token of the item AND the row's text shares distinctive
    # context tokens (brand/machine-type words) with the item's fuller
    # identity.
    if not str(identity_column or "").strip():
        codes = {_norm_token(t) for t in _item_code_tokens(item)}
        if not codes:
            return False
        row_text = " ".join(str(v) for v in row.values()).lower()
        if not any(
                re.search(r"(?<![0-9a-z])" + re.escape(c)
                          + r"(?![0-9a-z])", row_text)
                for c in codes if c):
            return False
        ctx_toks = {
            _norm_token(t) for t in re.findall(
                r"[A-Za-z]{4,}", str(identity_context or ""))}
        row_toks = {
            _norm_token(t) for t in re.findall(
                r"[A-Za-z]{4,}", row_text)}
        return bool(ctx_toks & row_toks)
    """STRICT identity (round 56): the identity cell must EQUAL a
    code-shaped token of the item — not merely contain it. A BARE
    NUMERIC token ('381') additionally requires CORROBORATION: another
    cell in the row (typically the description) shares a distinctive
    token with the item's fuller identity context. Unrestricted
    substring containment is gone: a parts-number '381' row no longer
    impersonates the No. 381 roll bender."""
    id_val = _norm_token(row.get(identity_column, ""))
    if not id_val:
        return False
    codes = [_norm_token(t) for t in _item_code_tokens(item)]
    if id_val not in codes:
        return False
    if any(c.isdigit() for c in id_val) and not any(
            re.match(r"^[A-Za-z0-9]*[A-Za-z]", c) and len(c) >= 2
            for c in codes if c == id_val):
        # bare-ish numeric: needs corroborating context
        ctx_toks = {
            _norm_token(t) for t in re.findall(
                r"[A-Za-z]{4,}", str(identity_context or ""))}
        row_text = " ".join(str(v) for v in row.values()).lower()
        row_toks = {
            _norm_token(t) for t in re.findall(
                r"[A-Za-z]{4,}", row_text)}
        return bool(ctx_toks & row_toks)
    return True


def apply_taught_policy(
        field: str,
        candidates: List[Any],
        lessons: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply the TAUGHT pricing policy to monetary candidates (round
    58): teaching that names the applicable basis ('the workbook has
    the formulas for list price') SELECTS the matching column. Returns
    {applied, selected, basis_lesson, reason, remaining} — remaining is
    the post-policy candidate set; a decision is asked only when a
    MATERIAL difference survives the policy."""
    if not candidates:
        return {"applied": False, "selected": None, "basis_lesson": None,
                "reason": "no candidates", "remaining": []}
    field_l = str(field).lower()
    for l in lessons or []:
        text = " ".join(str(l.get("lesson") or l.get("summary")
                             or "").split()).lower()
        if field_l not in text:
            continue
        for basis in ("list price", "net price", "cost", "dealer net",
                      "cdn list", "us list"):
            if basis in text:
                sel = [
                    c for c in candidates
                    if basis.replace(" ", "") in
                    re.sub(r"[^a-z0-9]", "", str(c[0]).lower())]
                if len(sel) == 1:
                    return {
                        "applied": True, "selected": sel[0],
                        "basis_lesson": str(
                            l.get("id") or l.get("lesson_id") or "?"),
                        "reason": (
                            f"taught basis '{basis}' selects "
                            f"{sel[0][0]}"),
                        "remaining": candidates}
                if sel:
                    return {
                        "applied": False, "selected": None,
                        "basis_lesson": str(
                            l.get("id") or l.get("lesson_id") or "?"),
                        "reason": (
                            f"taught basis '{basis}' matches "
                            f"{len(sel)} columns — not selective"),
                        "remaining": sel}
    return {"applied": False, "selected": None, "basis_lesson": None,
            "reason": "no taught policy names a selective basis",
            "remaining": candidates}


def _bind_row_fields(
        row_result: Dict[str, Any],
        identity_column: str, item: str,
        requested_fields: List[str],
        identity_context: str = "") -> Dict[str, Any]:
    """Bind the row's values to the requested fields by COLUMN MEANING
    with IDENTIFIER EXCLUSION and MONETARY-VALUE verification. Returns
    {"identity_ok": bool, "bindings": {field: [(col, val, basis)]}} —
    every legitimate MONETARY candidate is preserved with its basis
    (the column name carries currency/basis hints); AMBIGUITY is the
    caller's to surface, never resolved by proximity."""
    row = row_result.get("row") or {}
    headers = row_result.get("headers") or []
    id_ok = _identity_supported(
        row, identity_column, item, identity_context)
    bindings: Dict[str, List[Any]] = {}
    for field in requested_fields or []:
        syns = FIELD_SYNONYMS.get(str(field).lower(), [str(field)])
        cands = []
        for h in headers:
            hl = str(h).lower()
            val = row.get(h)
            sval = str(val if val is not None else "").strip()
            if not sval:
                continue
            if not any(s in hl for s in syns):
                continue
            if IDENTIFIER_COLUMN_RE.search(str(h)):
                continue  # a CODE is never money
            if not _MONETARY_VALUE_RE.match(sval):
                continue  # non-monetary values are never prices
            cands.append((str(h), sval))
        bindings[str(field)] = cands
    return {"identity_ok": id_ok, "bindings": bindings}


async def _execute_row_read(
        lifecycle: Any, run_id: str,
        user_id: str, workspace_id: str,
        act: Dict[str, Any],
        qids: List[str],
        agent_lessons: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Row-context read over EVERY candidate location under STRICT
    identity: corroborated single-support rows bind fields (monetary
    only, identifier columns excluded); multiple supporting rows or
    bare-numeric-without-corroboration stay UNRESOLVED. Settlement is
    FENCED: the resolution mutation itself carries the claim
    requirement, so a takeover between check and write fails the write.
    """
    from core.sheet_dataset_service import read_sheet_row_sync
    from core.task_lifecycle import (
        add_unresolved_questions, finish_retrieval_turn,
        record_read_outcome, resolve_unresolved_questions_fenced)

    item = str(act.get("item") or "")
    fields = list(act.get("requested_fields") or [])
    context = str(act.get("identity_context") or item)
    statuses: Dict[str, str] = {}
    evidence: List[str] = []
    decision_questions: List[Dict[str, Any]] = []
    supporting: List[Dict[str, Any]] = []
    _policy: Dict[str, Any] = {}
    from core.sheet_dataset_service import find_entries_sync

    _act_file = str(act.get("file") or "")
    for cand in act.get("candidates") or []:
        _file = _act_file
        if not _file:
            # TAUGHT LEAD without a file: resolve the sheet against the
            # catalog (freshest copy carrying that sheet name).
            _hits = await asyncio.to_thread(
                find_entries_sync, str(cand.get("sheet") or ""),
                user_id, workspace_id, 6)
            _file = str(
                (_hits[0] or {}).get("file_name") or ""
            ) if _hits else ""
            if not _file:
                evidence.append(
                    f"{item}: taught sheet "
                    f"'{cand.get('sheet')}' not in the catalog — lead "
                    "unresolvable against current copies")
                continue
            cand = {**cand, "_resolved_file": _file}
        row_result = await asyncio.to_thread(
            read_sheet_row_sync, _file, cand.get("sheet") or "",
            cand.get("row") or 0, user_id, workspace_id)
        if row_result is None:
            continue
        bound = _bind_row_fields(
            row_result, cand.get("identity_column") or "", item,
            fields, identity_context=context)
        if not bound["identity_ok"]:
            evidence.append(
                f"{item}: row {cand.get('row')} of "
                f"{cand.get('sheet')} rejected — identity unsupported "
                f"({cand.get('identity_cell')})")
            continue
        supporting.append(
            {"cand": cand, "bound": bound, "_row_result": row_result})
    if len(supporting) == 1:
        bound = supporting[0]["bound"]
        cand = supporting[0]["cand"]
        for field, cands in bound["bindings"].items():
            # POLICY FIRST (round 58): the taught policy selects the
            # basis when it can; the owner is asked ONLY about what
            # materially survives it.
            pol = apply_taught_policy(field, cands, agent_lessons or [])
            _policy[field] = pol
            if pol["applied"]:
                col, val = pol["selected"]
                statuses[item] = "matched"
                evidence.append(
                    f"{item}: {field} = {val} ({col}; policy: "
                    f"{pol['reason']}; lesson {pol['basis_lesson']}; "
                    f"{cand.get('sheet')} row {cand.get('row')})")
                continue
            if pol["remaining"] and len(pol["remaining"]) < len(cands):
                cands = pol["remaining"]
                evidence.append(
                    f"{item}: {field} policy narrowed candidates to "
                    + "; ".join(f"{c}={v}" for c, v in cands)
                    + f" ({pol['reason']})")
            if len(cands) == 1:
                col, val = cands[0]
                statuses[item] = "matched"
                evidence.append(
                    f"{item}: {field} = {val} ({col} — basis/currency "
                    f"as the column names it; {cand.get('sheet')} row "
                    f"{cand.get('row')})")
            elif len(cands) > 1:
                statuses[item] = "matched"
                evidence.append(
                    f"{item}: {field} AMBIGUOUS after policy — "
                    + "; ".join(f"{c}={v}" for c, v in cands))
                decision_questions.append({
                    "item": item,
                    "kind": "business_decision",
                    "question": (
                        f"which {field} basis applies to {item}: "
                        + " vs ".join(f"{c}={v}" for c, v in cands)),
                    "evidence": (
                        f"corroborated row {cand.get('row')} of "
                        f"{cand.get('sheet')} in {act.get('file')}; "
                        f"policy applied ({pol['reason']}); these "
                        "differences survive the policy"),
                    "next_action": (
                        f"owner picks among the policy-surviving bases "
                        f"for {item}"),
                })
            else:
                statuses[item] = "matched"
                evidence.append(
                    f"{item}: corroborated row has NO monetary {field} "
                    f"column — scoped absence in this source")
    elif len(supporting) > 1:
        # DUPLICATE-LISTING COMPARISON (round 57): two supporting rows
        # may be duplicate listings (same machine, same description in
        # two sheets) rather than different machines. Compare workbook
        # version (same file), sheet, description and values; duplicates
        # merge into ONE candidate with per-column differences recorded
        # — a genuine choice survives only where a real difference does.
        def _desc(bound_result):
            row = bound_result.get("row") or {}
            for k in ("Description", "description", "DESC"):
                if str(row.get(k) or "").strip():
                    return " ".join(str(row[k]).lower().split())
            return ""
        descs = [_desc(s["_row_result"]) for s in supporting]
        if descs and all(d == descs[0] and d for d in descs):
            merged = supporting[0]
            cand = merged["cand"]
            col_diffs = []
            for other in supporting[1:]:
                for h, v in (other["_row_result"].get("row")
                             or {}).items():
                    mv = (merged["_row_result"].get("row")
                          or {}).get(h)
                    if str(v) != str(mv) and h != "__sheet_row":
                        col_diffs.append(
                            f"{h}: {cand.get('sheet')}/"
                            f"{cand.get('row')}={mv} vs "
                            f"{other['cand'].get('sheet')}/"
                            f"{other['cand'].get('row')}={v}")
            evidence.append(
                f"{item}: DUPLICATE LISTING — "
                + ", ".join(
                    f"{s['cand'].get('sheet')}/"
                    f"{s['cand'].get('row')}" for s in supporting)
                + " share the same description; merged as one machine"
                + (f"; column differences: {'; '.join(col_diffs)}"
                   if col_diffs else ""))
            bound = merged["bound"]
            for field, cands2 in bound["bindings"].items():
                pol2 = apply_taught_policy(
                    field, cands2, agent_lessons or [])
                _policy[field] = pol2
                if pol2["applied"]:
                    col, val = pol2["selected"]
                    statuses[item] = "matched"
                    evidence.append(
                        f"{item}: {field} = {val} ({col}; policy: "
                        f"{pol2['reason']}; lesson "
                        f"{pol2['basis_lesson']})")
                    continue
                if pol2["remaining"] and len(
                        pol2["remaining"]) < len(cands2):
                    cands2 = pol2["remaining"]
                if len(cands2) == 1:
                    col, val = cands2[0]
                    statuses[item] = "matched"
                    evidence.append(
                        f"{item}: {field} = {val} ({col} — basis as the "
                        "column names it)")
                elif len(cands2) > 1:
                    statuses[item] = "matched"
                    evidence.append(
                        f"{item}: {field} AMBIGUOUS (monetary candidates "
                        "on the merged duplicate) — "
                        + "; ".join(f"{c}={v}" for c, v in cands2))
                    decision_questions.append({
                        "item": item,
                        "kind": "business_decision",
                        "question": (
                            f"which {field} basis applies to {item}: "
                            + " vs ".join(
                                f"{c}={v}" for c, v in cands2)),
                        "evidence": (
                            f"duplicate listings merged (same "
                            "description); bases differ only as named; "
                            + (f"column differences {col_diffs}"
                               if col_diffs else "no column differences")),
                        "next_action": (
                            f"apply taught {field} policy, else owner "
                            f"picks the basis for {item}"),
                    })
                else:
                    statuses[item] = "matched"
                    evidence.append(
                        f"{item}: merged duplicate has NO monetary "
                        f"{field} column — scoped absence")
        else:
            statuses[item] = ""
            evidence.append(
                f"{item}: {len(supporting)} candidate rows pass "
                "identity with DIFFERENT descriptions — UNRESOLVED; "
                "comparison: "
                + " | ".join(
                    f"{s['cand'].get('sheet')}/"
                    f"{s['cand'].get('row')}: {d[:60]}"
                    for s, d in zip(supporting, descs))
                + "; question stays open")
    else:
        statuses[item] = ""
        evidence.append(
            f"{item}: no candidate row's identity is supported — "
            "question stays open (located cells may be parts-number "
            "noise)")

    # TAUGHT-LEAD ABSENCE (round 57): every taught candidate row is
    # absent from the current copies -> the lead was executed and the
    # finding is scoped: resolve with the absence + open the precise
    # owner question (supply the referenced workbook version, or confirm
    # the preserved manual value).
    _taught_prov = (act.get("provenance") or {})
    _true_absence = supporting == [] and any(
        "absent" in e or "not readable" in e or "unresolvable" in e
        for e in evidence)
    if (_taught_prov.get("source") == "lesson" and _true_absence):
        from core.task_lifecycle import add_unresolved_questions

        try:
            resolve_unresolved_questions_fenced(
                lifecycle, run_id, question_ids=qids, by=_WORKER_ID,
                ttl_seconds=_CLAIM_TTL_SECONDS,
                resolution={
                    "how": (
                        "taught location executed — row absent from "
                        "every current saved copy (sheet resolution "
                        "whitespace-insensitive; scan coverage "
                        "recorded)"),
                    "detail": ("; ".join(evidence))[:350],
                })
            add_unresolved_questions(lifecycle, run_id, [{
                "item": item,
                "kind": "business_decision",
                "question": (
                    f"the taught location for {item} is absent from the "
                    "current saved copies — supply the workbook version "
                    "the teaching references, or confirm the preserved "
                    "manual value"),
                "evidence": ("; ".join(evidence))[:400],
                "next_action": (
                    f"owner supplies the referenced workbook version or "
                    f"confirms {item}'s manual price"),
            }], source_operation=None)
            return {"statuses": {item: "matched"},
                    "evidence": evidence + [
                        "taught lead resolved as scoped absence + "
                        "owner question"]}
        except Exception:  # noqa: BLE001 — fence or add failed
            pass
    op = lifecycle.create_operation(
        run_id, op_type="retrieve",
        requested_change=(
            f"row-context read: {act.get('file')} candidates for {item}"))
    _exec_facts = {
        "invoked": bool(act.get("candidates")),
        "outcome": ("read_succeeded" if statuses.get(item) == "matched"
                    else "read_returned_no_receipt"),
        "served_basis": ("saved_copy" if act.get("candidates")
                         else "none"),
        "failure_stage": None,
        "items": statuses,
    }
    # FENCED SETTLEMENT (round 56): ownership validation runs INSIDE the
    # resolution mutation — a takeover between check and write fails it.
    if qids:
        try:
            resolve_unresolved_questions_fenced(
                lifecycle, run_id, question_ids=qids, by=_WORKER_ID,
                ttl_seconds=_CLAIM_TTL_SECONDS,
                resolution={
                    "how": ("row-context read"
                            if statuses.get(item) == "matched"
                            else "row read — identity unresolved"),
                    "basis": _exec_facts["served_basis"],
                    "detail": "; ".join(evidence)[:350],
                } if statuses.get(item) == "matched" else None,
                keep_open_detail="; ".join(evidence)[:350]
                if statuses.get(item) != "matched" else None)
        except Exception as _fenced:  # noqa: BLE001 — takeover: skip
            return {"statuses": {}, "evidence": [
                f"ownership lost during settlement: {_fenced!r}"],
                "lost_ownership": True}
    finish_retrieval_turn(
        lifecycle, run_id, op["operation_id"], {}, None,
        bool(_exec_facts["outcome"] == "read_succeeded"),
        execution=_exec_facts)
    record_read_outcome(
        lifecycle, run_id, op["operation_id"], structured_result=None,
        freshness=None, execution=None)
    if decision_questions:
        add_unresolved_questions(
            lifecycle, run_id, decision_questions, source_operation=None)
    return {"statuses": statuses, "evidence": evidence}


_TAUGHT_LOCATION_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9 &'-]{2,30}?)\s+sheet\b[^.]{0,80}?"
    r"\brow\s+(\d{1,4})\b", re.IGNORECASE)
_SHEET_FILLER = {
    "is", "on", "the", "a", "an", "of", "in", "and", "no", "nos",
    "under", "at", "workbook", "file", "sheet"}


def _clean_sheet_name(raw: str) -> str:
    toks = [t for t in str(raw or "").split()
            if t and not t.isdigit() and t.lower() not in _SHEET_FILLER]
    return " ".join(toks)[-40:]


def _taught_location_successors(
        lifecycle: Any, run_id: str, record: Dict[str, Any],
        agent_lessons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Row-read successors from TAUGHT LOCATIONS (round 57): teaching
    that names a sheet and a row for an item ('no. 381 is on Tennsmith
    sheet ... row 338') is an executable lead with provenance — the
    failed match in another sheet never blocks it. Business-neutral:
    any lesson text, any sheet/row. Returns the successor questions."""
    from core.task_lifecycle import open_unresolved_questions

    out: List[Dict[str, Any]] = []
    open_qs = {str(q.get("item") or ""): q
               for q in open_unresolved_questions(record)
               if str(q.get("item") or "")}
    if not open_qs or not agent_lessons:
        return out
    lesson_texts = [
        (str(l.get("id") or l.get("lesson_id") or idx),
         " ".join(str(l.get("lesson") or l.get("summary")
                      or "").split()))
        for idx, l in enumerate(agent_lessons)]
    for item, q in open_qs.items():
        if (q.get("inputs") or {}).get("intent") == "row_read":
            ev = str(q.get("evidence") or "")
            _exhausted = (
                "identity unsupported" in ev
                or "no candidate row" in ev
                or "not readable" in ev
                or "absent" in ev)
            if not _exhausted:
                continue  # an active row successor exists
            _has_taught = "taught" in str(
                (q.get("inputs") or {}).get("provenance") or {})
            if _has_taught:
                continue  # the taught lead already ran
        codes = _item_code_tokens(item)
        if not codes:
            continue
        for lid, text in lesson_texts:
            tl = text.lower()
            if not any(c.lower() in tl for c in codes):
                continue
            for m in _TAUGHT_LOCATION_RE.finditer(text):
                sheet, row = _clean_sheet_name(
                    m.group(1)), int(m.group(2))
                if not sheet:
                    continue
                out.append({
                    "item": item,
                    "kind": "verification",
                    "question": (
                        f"{item}: taught location {sheet} sheet row "
                        f"{row} — read the row's requested fields"),
                    "evidence": f"taught lead (lesson {lid})",
                    "next_action": (
                        f"read row {row} of {sheet} per the taught "
                        "location"),
                    "inputs": {
                        "service": "datasets", "intent": "row_read",
                        "file": "",  # resolved against every cataloged
                        "candidates": [{
                            "sheet": sheet, "row": row,
                            "identity_column": "",
                            "identity_cell":
                                f"taught:lesson-{lid}:row-{row}"}],
                        "item": item,
                        "identity_context": str(item),
                        "candidates_total": 1,
                        "candidates_omitted": 0,
                        "requested_fields": list(
                            (record.get("task_revision") or {})
                            .get("requested_fields") or []) or ["price"],
                        "provenance": {"source": "lesson", "id": lid,
                                       "text": text[:200]},
                    },
                })
                break
    return out[:4]


def _session_owned_by_interactive(sess: Dict[str, Any]) -> bool:
    """True when the session ends with an UNANSWERED user message — the
    interactive lane owns it; the worker must not race it."""
    hist = sess.get("history") or []
    for entry in reversed(hist):
        if not isinstance(entry, dict):
            continue
        msg = str(entry.get("message") or "").strip()
        resp = str(entry.get("response") or "").strip()
        if msg and not resp:
            return True
        if msg or resp:
            return False
    return False


async def research_continuation_cycle(max_reads: int = _CYCLE_MAX_READS
                                      ) -> Dict[str, int]:
    """One bounded pass. The read budget is GLOBAL across jobs."""
    from core.task_lifecycle import (
        claim_questions_for_execution, next_unfinished_work,
        open_unresolved_questions)

    out = {"jobs": 0, "reads": 0, "items_matched": 0,
           "items_located": 0, "failed_reads": 0}
    if not research_continuation_enabled():
        return out
    try:
        from core.chat_session_manager import chat_session_manager

        lifecycle = _lifecycle_for_default_tenant()
        runs = lifecycle.runs.list_runs(include_terminal=False, limit=100)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[research-continuation] enumerate failed: %r", exc)
        return out
    budget = max_reads
    for run in runs or []:
        if budget <= 0:
            break
        run_id = str(run.get("id"))
        try:
            record = lifecycle.get_task(run_id)
            if record is None:
                continue
            # ROW-SUCCESSOR MIGRATION (round 55, one-time per job): jobs
            # whose located read questions were EXHAUSTED by the pre-
            # successor burn rule get their budgets reset once so the
            # located->successor conversion can run; the marker lives in
            # the task revision (durably one-time).
            try:
                _rev = record.get("task_revision") or {}
                if not _rev.get("row_successor_migrated"):
                    _exh_read = [
                        q for q in (_rev.get("unresolved") or [])
                        if q.get("status") == "open"
                        and str(q.get("next_action") or "").lower()
                        .startswith("read ")
                        and int(q.get("attempts") or 0) >= 3]
                    if _exh_read:
                        lifecycle.apply_transition(run_id, {
                            "kind": "record_unresolved",
                            "requested_change": (
                                "row-successor migration: read questions "
                                "exhausted by the pre-successor burn rule; "
                                "budgets reset once for the located->"
                                "successor conversion"),
                            "attempts": [
                                {"question_id": q.get("question_id"),
                                 "set": 0} for q in _exh_read],
                            "row_successor_migration": True,
                            "source_operation": None,
                        })
            except Exception as _mig_err:  # noqa: BLE001
                logger.debug("row-successor migration skipped: %r",
                             _mig_err)
            work = next_unfinished_work(record)
            acts = _read_actions(work.get("actions") or [])
            if not acts:
                continue
            conv = record.get("conversation_id") or ""
            sess = chat_session_manager.get_session(conv) if conv else None
            if not sess or not str(sess.get("user_id") or "").strip():
                continue
            if _session_owned_by_interactive(sess):
                continue  # the interactive lane owns this job right now
            user_id = str(sess["user_id"])
            workspace_id = str(sess.get("workspace_id") or "default")
            # TAUGHT LEADS (round 57): seed row-read successors from
            # teaching that names sheet+row locations for open items.
            try:
                _lessons: List[Dict[str, Any]] = []
                _agent_id = str(
                    run.get("agent_id")
                    or ((record.get("task_revision") or {})
                        .get("provenance") or {}).get("agent_id")
                    or sess.get("agent_id") or "") or None
                if _agent_id:
                    from core.database import get_db_session as _gs
                    from core.student_learning_service import (
                        get_agent_lessons as _gal)

                    with _gs() as _db:
                        _lessons = _gal(_db, _agent_id, limit=10)
                _taught = _taught_location_successors(
                    lifecycle, run_id, lifecycle.get_task(run_id) or {},
                    _lessons)
                if _taught:
                    from core.task_lifecycle import (
                        add_unresolved_questions)

                    add_unresolved_questions(
                        lifecycle, run_id, _taught, source_operation=None)
                    work = next_unfinished_work(
                        lifecycle.get_task(run_id) or {})
                    acts = _read_actions(work.get("actions") or [])
            except Exception as _taught_err:  # noqa: BLE001 — additive
                logger.debug("taught-lead seeding skipped: %r", _taught_err)
            groups: Dict[str, List[Dict[str, Any]]] = {}
            for a in acts:
                # Row-read successors group SEPARATELY from document
                # reads of the same file (they dispatch differently).
                key = (f"row:{a['file']}:{a.get('item')}"
                       if a.get("intent") == "row_read" else a["file"])
                groups.setdefault(key, []).append(a)
            out["jobs"] += 1
            notes: List[str] = []
            for fname, group in list(groups.items()):
                if budget <= 0:
                    break
                # ELIGIBILITY RE-CHECK + DURABLE CLAIM (exclusive).
                fresh = lifecycle.get_task(run_id)
                still_open = {
                    str(q.get("question_id"))
                    for q in open_unresolved_questions(fresh or {})}
                qids = [g["question_id"] for g in group
                        if g.get("question_id") in still_open]
                if not qids:
                    continue
                claimed = claim_questions_for_execution(
                    lifecycle, run_id, qids, by=_WORKER_ID,
                    ttl_seconds=_CLAIM_TTL_SECONDS)
                if not claimed:
                    continue  # another worker holds a fresh claim
                budget -= 1
                out["reads"] += 1
                if group[0].get("intent") == "row_read":
                    res = await _execute_row_read(
                        lifecycle, run_id, user_id, workspace_id,
                        group[0], qids, agent_lessons=_lessons)
                    out["items_matched"] += sum(
                        1 for s in res["statuses"].values()
                        if s == "matched")
                    notes.append(
                        f"row read ({group[0].get('sheet')} row "
                        f"{group[0].get('row')}): "
                        + "; ".join(res["evidence"]))
                    continue
                res = await _execute_document_read(
                    lifecycle, run_id, user_id, workspace_id, fname,
                    [g["item"] for g in group],
                    item_identity_context=str(
                        (lifecycle.get_task(run_id) or {}).get(
                            "task_revision", {}).get(
                            "objective_text") or ""))
                # LOCATED RESOLVES ITS READ QUESTION (round 55): the
                # location WAS the read's deliverable; the successor
                # row-read carries the remaining work. Only NO-MATCH
                # items consume an attempt (identical-rediscovery bound
                # for fruitless reads).
                from core.task_lifecycle import (
                    bump_question_attempts, resolve_unresolved_questions)

                _located_qids = [
                    g["question_id"] for g, it in zip(
                        group, [g["item"] for g in group])
                    if res["statuses"].get(it) == "located"
                    and g.get("question_id")]
                if _located_qids:
                    resolve_unresolved_questions(
                        lifecycle, run_id, items=None, kinds=None,
                        question_ids=_located_qids,
                        resolution={
                            "how": "located; row-read successor opened",
                            "detail": "; ".join(res["evidence"])[:350]})
                bump_question_attempts(
                    lifecycle, run_id,
                    [g["question_id"] for g, it in zip(
                        group, [g["item"] for g in group])
                        if res["statuses"].get(it) == ""
                        and g.get("question_id")])
                out["items_matched"] += sum(
                    1 for s in res["statuses"].values() if s == "matched")
                out["items_located"] += sum(
                    1 for s in res["statuses"].values() if s == "located")
                notes.append(f"{fname}: " + "; ".join(res["evidence"]))
            if notes:
                try:
                    fresh_sess = chat_session_manager.get_session(conv)
                    if fresh_sess and not _session_owned_by_interactive(
                            fresh_sess):
                        hist = list(fresh_sess.get("history") or [])
                        hist.append({
                            "message": "",
                            "response": (
                                "Background research update — completed "
                                "while you were away: "
                                + " | ".join(notes)
                                + ". Remaining work stays on the job "
                                  "record."),
                            "timestamp": time.time(),
                        })
                        chat_session_manager.update_session_activity(
                            conv, history=hist)
                except Exception:  # noqa: BLE001 — ledger is the record
                    pass
        except Exception as exc:  # noqa: BLE001 — per-job isolation
            out["failed_reads"] += 1
            logger.warning("[research-continuation] job %s failed: %r",
                           str(run_id)[:8], exc)
    if out["reads"]:
        logger.info("[research-continuation] cycle: %s", out)
    return out


async def _research_continuation_loop() -> None:
    logger.info("[research-continuation] durable research worker started "
                "(interval %.0fs, max %d reads/cycle GLOBAL)",
                _INTERVAL_SECONDS, _CYCLE_MAX_READS)
    while True:
        try:
            await research_continuation_cycle()
        except asyncio.CancelledError:
            logger.info("[research-continuation] worker stopped")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("[research-continuation] cycle error: %r", exc)
        await asyncio.sleep(_INTERVAL_SECONDS)


def start_research_continuation() -> bool:
    global _RECOVERY_TASK
    if _RECOVERY_TASK is not None and not _RECOVERY_TASK.done():
        return False
    try:
        _RECOVERY_TASK = asyncio.get_running_loop().create_task(
            _research_continuation_loop())
        return True
    except RuntimeError:
        logger.debug("research continuation not started: no running loop")
        return False


async def stop_research_continuation() -> None:
    global _RECOVERY_TASK
    task = _RECOVERY_TASK
    _RECOVERY_TASK = None
    if task is None:
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        pass
