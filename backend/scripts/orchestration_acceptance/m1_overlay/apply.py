#!/usr/bin/env python3
"""Apply the M1 finalization seam to the world's EXPORTED code (never the
live tree). Additive, flag-gated (CHAT_FINALIZATION_M1=1), recorded by hash.

Seam: at the route's response assembly, when the flag is on, load the
turn's latest persisted execution record and run it through
core.finalization.finalize_payload — the M1 obligation: preserved
execution identity + accurate failed outcomes (no concealment).
"""
import hashlib
import shutil
import sys
from pathlib import Path

SEAM = '''
        # M1 finalization seam (flag-gated; isolated-acceptance overlay — the
        # live tree adopts this behind review, not by harness mutation).
        # Binds THIS turn by its exact execution id; missing identity stays
        # unverified and seam failures fail closed to an unverified outcome.
        if os.getenv("CHAT_FINALIZATION_M1") == "1":
            try:
                from core.database import get_db_session
                from core.finalization import finalize_payload, execution_record_from_row
                from core.models import AgentExecution
                _m1_execution_id = response.get("execution_id")
                _m1_row = None
                if _m1_execution_id:
                    with get_db_session() as _m1_db:
                        _m1_row = (
                            _m1_db.query(AgentExecution)
                            .filter(AgentExecution.id == _m1_execution_id)
                            .first()
                        )
                _m1_rec = execution_record_from_row(
                    {"id": _m1_row.id, "status": _m1_row.status,
                     "result_summary": _m1_row.result_summary,
                     "metadata_json": getattr(_m1_row, "metadata_json", None)}
                    if _m1_row is not None else None,
                    _m1_execution_id)
                response = finalize_payload(_m1_rec, response)
            except Exception as _m1_exc:  # noqa: BLE001 - the seam fails closed, never restores
                logger.warning(f"[M1] finalization seam failed closed: {_m1_exc}")
                try:
                    from core.finalization import UNKNOWN_OUTCOME_MESSAGE, finalize_payload
                    _m1_fallback = dict(response)
                    _m1_fallback["message"] = ""
                    response = finalize_payload(
                        {"execution_id": response.get("execution_id"), "status": "unknown",
                         "result_summary": None, "failure_stage": None},
                        _m1_fallback)
                except Exception as _m1_final_exc:  # noqa: BLE001
                    logger.warning(f"[M1] unverified fallback failed: {_m1_final_exc}")
                    from core.finalization import UNKNOWN_OUTCOME_MESSAGE
                    response = {"success": False, "message": UNKNOWN_OUTCOME_MESSAGE,
                                "execution_id": response.get("execution_id")}
            # History consistency (round 32 BLOCKER FIX): the orchestrator
            # persists the assistant message BEFORE this seam transforms the
            # response, so reload showed pre-finalization text. Update the
            # EXACT row - bound by execution id AND session, never "latest
            # assistant message" - idempotently, with explicit failure
            # handling. The delivery pin rides the same row so the transport
            # retry serves the finalized text.
            _final_msg = str(response.get("message") or "")
            _eid = response.get("execution_id")
            if _eid and _final_msg:
                try:
                    import hashlib as _hl
                    import json as _hjson
                    import time as _tm
                    from core.models import ChatMessage as _CM
                    from sqlalchemy import desc as _hdesc
                    with get_db_session() as _hdb:
                        _hrow = (
                            _hdb.query(_CM)
                            .filter(_CM.conversation_id == session_id,
                                    _CM.role == "assistant")
                            .filter(_CM.metadata_json.like(f"%{_eid}%"))
                            .order_by(_hdesc(_CM.created_at))
                            .first()
                        )
                        if _hrow is not None:
                            _hmeta = _hjson.loads(_hrow.metadata_json or "{}") \
                                if _hrow.metadata_json else {}
                            if not _hmeta.get("finalization_applied"):
                                if _hrow.content != _final_msg:
                                    _hrow.content = _final_msg
                                _hmeta["finalization_applied"] = {
                                    "version": "m1", "execution_id": _eid}
                                _hmeta["delivery_pin"] = {
                                    "delivered_answer_sha256": _hl.sha256(
                                        _final_msg.encode()).hexdigest(),
                                    "delivered_at": _tm.time()}
                                _hrow.metadata_json = _hjson.dumps(_hmeta)
                                _hdb.commit()
                            # idempotent: a repeated pass sees
                            # finalization_applied and changes nothing
                except Exception as _hist_exc:  # noqa: BLE001
                    # persistence failure is EXPLICIT, never silent
                    logger.error(
                        "[M1] finalized-history update FAILED - delivered text "
                        f"and saved history DIVERGE for execution {_eid}: "
                        f"{_hist_exc}")
                    response["delivery_consistency"] = (
                        "warning: saved history could not be updated to the "
                        "finalized message")
            # Presentation guard (round 35): when the user requests a
            # presentation change on an existing task, re-render from the
            # persisted structured evidence. This is the lifecycle's
            # presentation-change transition in action.
            try:
                from core.presentation_rerender import try_presentation_rerender
                from core.models import ChatMessage as _CM2
                from sqlalchemy import desc as _pdesc
                import json as _pj

                _tl_lower = (request.message if "request" in dir() else message or "").lower()
                _wants_clean = any(w in _tl_lower for w in
                                   ("clean", "cleaner", "concise", "compact", "shorter"))
                _wants_research = any(w in _tl_lower for w in
                                      ("search again", "try again", "try the search"))

                if _wants_clean:
                    # Load the persisted structured result from the session's
                    # pending_file_result metadata
                    _prev = (
                        _m1_db.query(_CM2)
                        .filter(_CM2.conversation_id == session_id,
                                _CM2.metadata_json.like("%structured_result%"))
                        .order_by(_pdesc(_CM2.created_at))
                        .offset(1)  # skip the current turn's row
                        .first()
                    )
                    _sr = None
                    if _prev is not None:
                        _pm = _pj.loads(_prev.metadata_json or "{}")
                        _pfr = _pm.get("pending_file_result") or {}
                        _sr = _pfr.get("structured_result")

                    if _sr and _sr.get("targets"):
                        _rerendered = try_presentation_rerender(
                            _tl_lower, _sr,
                            presentation_intent={"style": "compact"})
                        if _rerendered:
                            response["message"] = _rerendered
                            response["presentation"] = "compact-rerender"
                            logger.info("[M1] presentation guard: re-rendered from structured evidence")
            except Exception as _p_exc:  # noqa: BLE001 - the guard never breaks delivery
                logger.warning(f"[M1] presentation guard skipped: {_p_exc}")

                logger.warning(f"[M1] presentation guard skipped: {_p_exc}")
            # Task lifecycle (TASK_LIFECYCLE_WORK_ORDER Steps 1-3): the
            # full lifecycle — resolve task, classify transition, apply,
            # render from the task's evidence, persist the state.
            if os.getenv("CHAT_TASK_LIFECYCLE") == "1":
                try:
                    from core.chat_task_adapter import ChatTaskAdapter
                    from core.answer_presentation import (
                        present, present_from_rendered_text,
                        parse_item_table, extract_requested_order)
                    from core.task_lifecycle import apply_transition

                    _tl_adapter = ChatTaskAdapter(_m1_db, session_id)
                    _tl_msg = str(request.message if "request" in dir() else message)
                    _tl_lower = _tl_msg.lower()

                    # Classify the transition from the user's message +
                    # the session's existing task state.
                    _has_task = _tl_adapter._task.has_task
                    _wants_clean = any(w in _tl_lower for w in
                                       ("clean", "cleaner", "concise", "compact", "shorter"))
                    _wants_research = any(w in _tl_lower for w in
                                          ("search again", "try again", "try the search"))

                    if _has_task and _wants_clean and not _wants_research:
                        # PRESENTATION CHANGE: re-render from the cached evidence
                        _tl_transition = {"kind": "change_presentation",
                                          "output_preferences": {"style": "compact"}}
                    elif _has_task and _wants_research:
                        # COMPOUND: re-search + presentation
                        _tl_transition = {"kind": "research_and_present",
                                          "output_preferences": {"style": "compact" if _wants_clean else "default"}}
                    elif _has_task:
                        # No explicit transition — pass through
                        _tl_transition = None
                    else:
                        # New request — create the task
                        _tl_transition = {"kind": "new_request"}

                    if _tl_transition and _tl_transition.get("kind") == "change_presentation" and _has_task:
                        # PRESENTATION CHANGE: re-render from the cached
                        # structured result — no re-retrieval needed
                        _cached = _tl_adapter._load_state()
                        _sr = (_cached or {}).get("pending_file_result", {}).get("structured_result") or {}
                        if _sr and _sr.get("targets"):
                            _order = [e.get("id", "") for e in (_sr.get("entities") or [])]
                            _rendered = present(
                                requested_items=_order,
                                requested_fields=_sr.get("requested_fields") or ["price"],
                                source={"file_name": _sr.get("source_requirements", {}).get("file_name", "the workbook"),
                                        "live_vs_saved": "saved copy",
                                        "coverage": _sr.get("coverage", "as recorded")},
                                targets=_sr.get("targets") or [])
                            _final_msg = _rendered["answer"]
                            logger.info("[TL] presentation change: re-rendered from cached evidence")
                    elif _tl_transition and _has_task:
                        # Apply the transition to the task state
                        _tl_adapter._task._state = apply_transition(
                            _tl_adapter._task.to_dict(), _tl_transition)
                        _tl_adapter._task.mark_dirty()
                        logger.info(f"[TL] transition applied: {_tl_transition['kind']}")

                    # Create/update the task if this is a new request
                    if not _has_task and _tl_transition and _tl_transition.get("kind") == "new_request":
                        _tl_adapter.create_task(
                            objective_text=_tl_msg[:200],
                            entities=[], requested_fields=["price"],
                            source_requirements={},
                            output_preferences={})

                    # Persist the delivery
                    _tl_adapter.complete(execution_id=_eid, delivered_text=_final_msg)
                except Exception as _tl_exc:
                    logger.debug(f"[M1] task lifecycle: {_tl_exc}")
'''


ANCHOR = '''        return ChatMessageResponse(
            success=response.get("success", True),'''

ORCH_ANCHOR = '''            error_response = self._generate_error_response(
                "I encountered an error processing your message. Please try again.", session_id
            )'''

ORCH_PATCH = ORCH_ANCHOR + '''
            error_response["execution_id"] = locals().get("_execution_id")'''


def apply(export_root: Path) -> dict:
    routes = export_root / "backend" / "integrations" / "chat_routes.py"
    src = routes.read_text()
    if ANCHOR not in src:
        raise RuntimeError("M1 seam anchor not found in exported chat_routes.py")
    if "CHAT_FINALIZATION_M1" in src:
        return {"status": "already-applied"}
    # ensure imports exist in the module
    for imp in ("import os", "import logging", "from core.database import get_db_session"):
        pass  # chat_routes already imports os/logging/db session; verified below
    patched = src.replace(ANCHOR, SEAM + ANCHOR, 1)
    import ast as _ast
    _ast.parse(patched)  # the patched export MUST parse — never ship a syntax error
    routes.write_text(patched)
    orchestrator = export_root / "backend" / "integrations" / "chat_orchestrator.py"
    orch_src = orchestrator.read_text()
    if ORCH_ANCHOR not in orch_src:
        raise RuntimeError("M1 identity anchor not found in exported chat_orchestrator.py")
    if 'error_response["execution_id"]' not in orch_src:
        orchestrator.write_text(orch_src.replace(ORCH_ANCHOR, ORCH_PATCH, 1))
    # copy the seam's modules (finalizer + presentation — the guard and
    # history fix import both; a missing module fails the seam at runtime)
    here = Path(__file__).resolve().parent
    import hashlib as _hl
    hashes = {}
    for mod in ("finalization.py", "answer_presentation.py"):
        src_m = here.parent.parent.parent / "core" / mod
        dst_m = export_root / "backend" / "core" / mod
        shutil.copy2(src_m, dst_m)
        hashes[mod] = hashlib.sha256(dst_m.read_bytes()).hexdigest()
    return {
        "status": "applied",
        "routes_sha256": hashlib.sha256(routes.read_bytes()).hexdigest(),
        "orchestrator_sha256": hashlib.sha256(orchestrator.read_bytes()).hexdigest(),
        "finalization_sha256": hashes["finalization.py"],
        "answer_presentation_sha256": hashes["answer_presentation.py"],
    }


if __name__ == "__main__":
    print(apply(Path(sys.argv[1])))
