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
            except Exception as _m1_exc:  # noqa: BLE001 — the seam fails closed, never restores
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
    routes.write_text(patched)
    orchestrator = export_root / "backend" / "integrations" / "chat_orchestrator.py"
    orch_src = orchestrator.read_text()
    if ORCH_ANCHOR not in orch_src:
        raise RuntimeError("M1 identity anchor not found in exported chat_orchestrator.py")
    if 'error_response["execution_id"]' not in orch_src:
        orchestrator.write_text(orch_src.replace(ORCH_ANCHOR, ORCH_PATCH, 1))
    # copy the finalizer module
    here = Path(__file__).resolve().parent
    dst = export_root / "backend" / "core" / "finalization.py"
    shutil.copy2(here.parent.parent.parent / "core" / "finalization.py", dst)
    return {
        "status": "applied",
        "routes_sha256": hashlib.sha256(routes.read_bytes()).hexdigest(),
        "orchestrator_sha256": hashlib.sha256(orchestrator.read_bytes()).hexdigest(),
        "finalization_sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    print(apply(Path(sys.argv[1])))
