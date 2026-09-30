# -*- coding: utf-8 -*-
"""The turn program: ONE typed interpretation of a turn, decided once.

Architecture (2026-10-01, owner-approved step 1 of the conversation
migration): the system's long-conversation failures were not any single
regex — they came from re-deriving "what is this turn about?" at every
seam, from carriers different lanes read differently (research-grounded:
dialogue-state-tracking practice decides once against one belief state;
event-sourced agent state makes the decision replayable; see
notes/AGENT_COORDINATION.md 2026-09-30/10-01 entries).

This module composes the EXISTING resolvers — operation classification,
reference recognition, contrastive target-set resolution, sheet-scope
constraints — into one typed program per turn. Lanes EXECUTE programs;
they stop re-deciding. Downstream code that ignores a program field is a
bug the decided-facts invariant (tests/test_turn_program_invariants.py)
exists to catch.

Design constraints, all hard-won this week:

- PURE: no retrieval, no DB, no LLM. Inputs are the message, the
  decision layer's output, and typed candidate sets the CALLER extracts
  from its state (canvas items, stored objective, last served items).
- IDENTICAL-BY-CONSTRUCTION: the program's fields are the SAME fields
  the lanes already consume (requested_targets / revised_targets /
  sheet_scope_hints / inherited_targets / operation). Consolidating
  interpretation must not change behavior; it makes it auditable.
- DECIDED FACTS are enumerable: ``decided_facts`` lists every non-empty
  decision so an invariant can assert each appears in the executed
  action or its rejection. A fact that vanishes between decision and
  execution is the exact defect class this exists to end.
- FAIL-CLOSED: an unresolved target set yields ``clarify`` — never a
  silent inheritance of the previous objective ('related' is not
  'repeat').
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

__all__ = ["build_turn_program", "TURN_PROGRAM_SCHEMA"]

TURN_PROGRAM_SCHEMA = "turn-program-1"

#: The comparison ask ("verify if pricing needs updating from latest
#: data") — a source refresh ALONE is not a comparison; the program
#: records the intent so the answer must carry a comparison outcome or
#: an explicit unable-to-verify.
_COMPARE_RE = re.compile(
    r"\b(?:verify|check|compare|validate|confirm)\b[^.?!]{0,60}"
    r"\b(?:updat|chang|latest|current|new|differ|match)\w*", re.IGNORECASE)


def _clean(items: Optional[Sequence[Any]]) -> List[str]:
    out: List[str] = []
    seen: set = set()
    for i in items or []:
        t = str(i or "").strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def build_turn_program(
    message: str,
    *,
    decision: Optional[Dict[str, Any]] = None,
    file_mention: Optional[str] = None,
    canvas_items: Optional[Sequence[str]] = None,
    prior_items: Optional[Sequence[str]] = None,
    last_served_items: Optional[Sequence[str]] = None,
    own_items: Optional[Sequence[str]] = None,
    standing_scope_hints: Optional[Sequence[str]] = None,
    prior_retrieval_reference: Optional[bool] = None,
    reference_basis: str = "floor",
) -> Dict[str, Any]:
    """One typed program for one turn.

    Parameters are the typed inputs the interpretation needs:
    ``decision`` is the turn_decision layer's structured output (its
    constraints ride the program); ``file_mention`` the resolved file
    name (explicit or anaphoric — resolution stays with the resolvers);
    ``canvas_items`` / ``prior_items`` / ``last_served_items`` the
    candidate target sets; ``own_items`` codes this message itself
    names; ``standing_scope_hints`` the user's taught preferences (the
    decision layer's constraints); ``prior_retrieval_reference`` the
    NLU residue verdict when the floor was silent (None = floor
    verdict stands).

    Returns a ``turn-program-1`` dict. Key fields:

    - ``operation``: read | rerun | refresh | compare | list | clarify
    - ``target_set``: {kind, items, origin} — kind is explicit |
      inherited | contrastive_resolved | none
    - ``constraints``: {sheets, sources} — provenance kept for receipts
    - ``reference``: {prior_retrieval, basis}
    - ``clarify``: {needed, question} — needed=True means DO NOT read
    - ``decided_facts``: every non-empty decision, for the invariant
    """
    from core.pending_file_task import classify_file_operation
    from core.target_set_resolution import (
        resolve_target_set as _resolve_tsr,
    )

    msg = str(message or "")
    program: Dict[str, Any] = {
        "schema": TURN_PROGRAM_SCHEMA,
        "message": msg[:500],
    }
    facts: List[Dict[str, str]] = []

    def _fact(kind: str, value: Any, origin: str) -> None:
        if value in (None, "", [], {}):
            return
        facts.append({"kind": kind, "value": value, "origin": origin})

    # ---- operation ------------------------------------------------------
    # compare-shape detection outranks the generic refresh classifier:
    # "verify if any pricing needs updating from latest data" is BOTH
    # refresh-shaped and a comparison ask; the comparison is the intent
    # and carries the stronger answer contract (per-item outcome or an
    # explicit unable-to-verify — never an ordinary search answer).
    op = classify_file_operation(msg)
    if _COMPARE_RE.search(msg) and op in ("read", "refresh", "re-run"):
        op = "compare"
    program["operation"] = op
    _fact("operation", op, "classifier+compare-shape")

    # ---- file -----------------------------------------------------------
    _mention = str(file_mention or "").strip()
    program["file"] = {"mention": _mention or None}
    _fact("file_mention", _mention or None, "resolver")

    # ---- reference to prior retrieval work ------------------------------
    # Floor verdict computed by the CALLER's regex (single source of
    # truth: chat_tool_planner._RETRIEVAL_REFERENCE_RE) unless the NLU
    # residue supplied one. Kept as an input so the program layer adds
    # no second regex for the same question.
    from core.chat_tool_planner import _RETRIEVAL_REFERENCE_RE

    floor_ref = bool(_RETRIEVAL_REFERENCE_RE.search(msg))
    if prior_retrieval_reference is None:
        ref, basis = floor_ref, "floor"
    else:
        ref, basis = bool(prior_retrieval_reference), reference_basis
    program["reference"] = {"prior_retrieval": ref, "basis": basis}
    _fact("prior_retrieval_reference", ref or None, basis)

    # ---- target set -----------------------------------------------------
    own = _clean(own_items)
    tsr = _resolve_tsr(
        msg,
        canvas_items=canvas_items,
        prior_items=prior_items,
        last_served_items=last_served_items,
    )
    if tsr.get("kind") == "clarify":
        target_kind, items, origin = "unresolved", [], None
        program["clarify"] = {
            "needed": True,
            "question": str(tsr.get("question")
                            or "Which items should I check?"),
        }
    elif tsr.get("kind") == "resolved":
        target_kind, items = "contrastive_resolved", _clean(
            tsr.get("items"))
        origin = tsr.get("origin")
        program.pop("clarify", None)
    elif own:
        target_kind, items, origin = "explicit", own, "message"
    else:
        inherited = _clean(prior_items)
        if inherited and (ref or op in ("rerun", "compare", "refresh")):
            target_kind, items, origin = "inherited", inherited, "carriers"
        else:
            target_kind, items, origin = "none", [], None
    program["target_set"] = {
        "kind": target_kind, "items": items, "origin": origin}
    _fact("target_set", items or None, target_kind)

    # ---- constraints (sheet scope), provenance kept ---------------------
    sheets: List[str] = []
    sources: Dict[str, str] = {}
    for hint in _clean(standing_scope_hints):
        sheets.append(str(hint))
        sources[str(hint)] = "standing"
    program["constraints"] = {"sheets": sheets, "sources": sources}
    _fact("standing_scope", sheets or None, "decision-constraints")

    # ---- typed action language (consolidated 2026-10-01) ----------------
    # The decision's ACTION PROGRAM (core.action_program, compiled by
    # turn_decision) is the typed execution vocabulary. When present it
    # rides the turn program verbatim — ONE language for what was
    # decided and what executes (the reader's scope-receipt seam runs
    # these same ops through execute_program). When the decision layer
    # is unavailable, the scope constraint is synthesized INTO the same
    # typed shape (FilterPreviousOp record, pending refs — resolution
    # happens against the file's real catalog at read time, never here).
    actions: List[Dict[str, Any]] = []
    _dec_program = (decision or {}).get("action_program")
    if (isinstance(_dec_program, dict)
            and isinstance(_dec_program.get("actions"), list)):
        actions = [dict(a) for a in _dec_program["actions"]
                   if isinstance(a, dict)]
    if not actions and sheets:
        actions = [{
            "op": "filter_previous",
            "action_id": "scope",
            "depends_on": [],
            "item": "",
            "sheets": [
                {"mention": s, "resolved_name": None, "status": "pending"}
                for s in sheets],
        }]
    program["actions"] = actions
    if actions:
        _fact("typed_actions", [str(a.get("op")) for a in actions],
              "decision-program" if _dec_program else "synthesized")

    # ---- decided facts ----------------------------------------------------
    program["decided_facts"] = facts
    return program
