#!/usr/bin/env python3
"""L1+L2+L3 integrated composed served acceptance — one workflow.

LIVE-WORLD REHEARSAL — not a fresh-scratch campaign.

UNFILTERED-BYOK VARIANT (2026-10-24): the isolated scratch world receives
a COPY of the pilot's full BYOK configuration (all providers/keys) instead
of the historical DeepSeek-only credential. The pilot files are never
modified. Actual provider POST destinations and reply routes are recorded.

Candidate: fix/l3-required-read-timeout at 09cccb5b0, containing the
live-world diagnosis repair: a unique catalog title mention binds the
accepted document requirement, a document-only required read owns the
turn (legacy SEARCH/AI_ANALYTICS/AGENT skip), and the legacy synchronous
entity search is bounded off the event loop. The database is the
verified pre-cutover 786 MB snapshot; auxiliary stores are fresh and
isolated; scheduler/ingestion/outbound writers are disabled. Gate
harness is f2f832997. This runner only adds acceptance files and never
edits the product or the pilot.

This runner serves the pinned product from its worktree in the
PREDECLARED isolated configuration. One fresh user, one session:

  upload -> L3 sourced answer -> draft -> edit -> identical re-ask (no-op,
  zero canvas writes) -> L2 comparison (broader obligation visibly open)
  -> L2 date-only continuation -> restart/reload agreement.

The observation launcher wraps production seams outside the candidate
source, calls the originals, returns their results unchanged, and records
the session-scoped requirement/capture state. The durable execution row is
authoritative for settlement.
"""
from __future__ import annotations

import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from successor_gates_live import (  # noqa: E402
    all_open_work_is_prior_s3,  # noqa: F401 — re-exported for tests
    cf_completed_scope,
    continuation_source_ok,
    restart_agreement_ok,
    s7_settlement_ok,
)

MAIN = Path("/Users/rushiparikh/projects/atom")
L2_EVID = (MAIN / "backend/scripts/orchestration_acceptance/journey_matrix/"
           "l2_continuation_served_20261019")
sys.path.insert(0, str(L2_EVID))
import run_l2_served as base  # noqa: E402

CAND = Path(
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/"
    "l3-required-read-timeout")
CAND_BACKEND = CAND / "backend"
PY = MAIN / "backend/venv314/bin/python"
SCRATCH = Path(
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/"
    "l2-fix/scratch/l1-l2-l3-live-rehearsal-20261024-unfiltered")
PORT = 8121
BASE = f"http://127.0.0.1:{PORT}"
LIVE_DB = MAIN / "backend/data/atom.db"
PILOT_BACKEND = "http://127.0.0.1:8001"
PILOT_FRONTEND = "http://127.0.0.1:3000"
PRODUCT_SHA = "09cccb5b0b977f86c0a39d59af5b922c83143e7f"
CANDIDATE_SHA = PRODUCT_SHA
HARNESS_GATE_COMMIT = "f2f8329971129bc14e9f107aa234b98db7f18379"
HARNESS_GATE_TAG = "successor/live-rehearsal-20261024-unfiltered"
EXPECTED_GATES_SHA256 = (
    "6d66d0b8b3b2c9a24efbe111a750c477f623a207d34692dcd4fa07cfceb88dd2")
PRE_DECL = HERE / "PREDECLARED_CONFIG_LIVE_REHEARSAL_UNFILTERED.md"

EXPECTED_SOURCE_SHA256 = {
    "chat_tool_planner": "807dd65eb83fe7676ac29fba475ef188cac6ad82146c02321d66564a023414c5",
    "chat_orchestrator": "7736adbf3bbf9e007087201f4e72b212a1667f7384ec44426efc915b3802d91c",
    "answer_boundary": "3a36a5dd99cd11e1767c036461f84342fbf41e4f20d6644e147f5047a6b49db3",
    "workbook_read_artifact": "db23d66749eb79ed37f0011b96b0096ad0e746cc0c981fd5f5f6edb89889da67",
    "chat_canvas_editor": "5f724ceb645cff36718c13a5c6a3cb3de2417f63f9b2e04cc5be84c55170dece",
    "chat_routes": "d86d0be9334e8927c6811b998a5cc8c28a3b535d03cace57e8f9529679ffa0e0",
    "turn_decision": "f5342f1d8deac03a917142d5931efec190fe58a52889e8acf9cc551963508065",
}

base.BASE = BASE
base.PORT = PORT
base.SETTLE_TIMEOUT_S = 460
base.POLL_INTERVAL_S = 5
base.PILOT_BACKEND = PILOT_BACKEND
base.PILOT_FRONTEND = PILOT_FRONTEND

# Declared structured route: DeepSeek direct, one authorized vault entry.
CREDENTIAL_PROVIDER = "deepseek"
CREDENTIAL_VAULT_KEY = "tenant_default_deepseek_default_production"
CREDENTIAL_KEY_NAME = "default"
CREDENTIAL_ENVIRONMENT = "production"
CREDENTIAL_LABEL = "Authorized L1+L2+L3 composed route (DeepSeek direct)"
CREDENTIAL_ROUTE = "https://api.deepseek.com/v1"
CREDENTIAL_STEP = "deepseek_activation"
DEEPSEEK_PIN = "deepseek:deepseek-v4-pro"
EDIT_PIN = "deepseek/deepseek-v4-pro"

FIXTURE_NAME = "approved_records_q2026_114.txt"
FIXTURE_TEXT = (
    "APPROVED RECORDS \u2014 Quotation Q-2026-114\n"
    "Source: Sales Operations approved-terms register\n"
    "Client: Dunmore Fabrication LLC\n"
    "Item: CNC press brake, 50-ton\n"
    "Approved unit price: $48,000.00\n"
    "Approved payment terms: Net 30\n"
    "Approved valid until: 2026-12-31\n"
    "Approved by: Sales Operations\n")

# The L3 parent acceptance's exact fixture and ask. The L3 repair was proven
# with this ask/fixture under the ollama reply route; a paraphrased
# "approved valid-until date" ask in attempt 1 did not trigger the
# documents lane, so attempt 2 uses the proven request unchanged.
L3_FIXTURE_NAME = "l3_zephyr9_fixture.txt"
L3_FIXTURE_TEXT = (
    "ATOM PHASE D FIXTURE \u2014 internal notes.\n"
    "Project Zephyr-9 launch planning.\n"
    "The launch code for project Zephyr-9 is QUARTZ-77.\n"
    "Owner: R. Parikh. Team: acceptance.\n"
    "Decoy: the archive key for project Halcyon-2 is BASALT-13.\n")
L3_EXPECTED_CODE = "QUARTZ-77"
L3_DECOY_CODE = "BASALT-13"

CANVAS_TITLE = "Quotation Q-2026-114 (DRAFT)"
CANVAS_BODY = (
    "# Quotation Q-2026-114 (DRAFT)\n\n"
    "Client: Dunmore Fabrication LLC\n"
    "Prepared for: Elena Sorokina, Operations\n"
    "Item: CNC press brake, 50-ton\n"
    "Unit price: $48,000.00\n"
    "Subtotal: $48,000.00\n"
    "Terms: Net 45\n"
    "Valid until: 2026-12-31\n")

L3_ASK = (
    "search my uploaded documents for the launch code for project "
    "Zephyr-9 and tell me the code")
EDIT_ASK = "Please update the payment terms in the draft to Net 30."
S3_ASK = (
    "Compare the draft quotation with my uploaded Approved Records document. "
    "Does the Valid Until date in the draft match the approved record? "
    "Flag anything that differs. Do not change anything yet.")
S7_ASK = (
    "What is the current Valid until date on the draft, and does it still "
    "match the approved record?")


def l3_answer_contract(message: str) -> bool:
    """The declared L3 answer contract: expected code, no decoy.

    Kept as a named predicate so the answer-boundary replay can exercise
    the same contract the campaign checks.
    """
    text = str(message or "")
    return bool(
        L3_EXPECTED_CODE in text
        and L3_DECOY_CODE not in text
        and "needs to be connected" not in text.casefold())

WRONG_VALUES = ("2026-11-30", "2026-10-31", "2025-12-31")
GLOBAL_CLAIMS = (
    "everything appears consistent", "everything matches",
    "all other fields match", "no other differences",
    "remaining fields match", "everything else matches")
ALLOWED_ACTION_KINDS = (
    "research", "learning", "canvas_edit", "calculation",
    "presentation", "conversation")


def sha256_file(path: Path) -> str:
    return base.sha256_file(path)


def source_hashes(cand_backend: Path) -> dict:
    """The product source hash set the launch guard verifies.

    Kept in one place so the preflight can assert the builder covers every
    expected key — the missing answer_boundary entry was caught only at
    launch on 2026-10-23.
    """
    return {
        "chat_tool_planner": sha256_file(
            cand_backend / "core" / "chat_tool_planner.py"),
        "chat_orchestrator": sha256_file(
            cand_backend / "integrations" / "chat_orchestrator.py"),
        "chat_routes": sha256_file(
            cand_backend / "integrations" / "chat_routes.py"),
        "answer_boundary": sha256_file(
            cand_backend / "core" / "answer_boundary.py"),
        "chat_canvas_editor": sha256_file(
            cand_backend / "core" / "chat_canvas_editor.py"),
        "workbook_read_artifact": sha256_file(
            cand_backend / "core" / "workbook_read_artifact.py"),
        "turn_decision": sha256_file(
            cand_backend / "core" / "turn_decision.py"),
    }


def port_open(port: int) -> bool:
    return base.port_open(port)


def run(cmd, **kw):
    return base.run(cmd, **kw)


LIVE_DB_TABLES = (
    "users", "agents", "chat_sessions", "chat_messages",
    "agent_executions", "canvases", "canvas_audit", "ingested_documents",
    "task_operation_records", "tool_mutations",
)


def live_db_fingerprint(path: Path) -> dict:
    """Content + open-store fingerprint, not an mtime-only signal."""
    out = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return out
    st = path.stat()
    out.update({"size_bytes": st.st_size, "mtime": st.st_mtime,
                "sha256": sha256_file(path)})
    wal = Path(str(path) + "-wal")
    if wal.exists():
        out["wal_size_bytes"] = wal.stat().st_size
        out["wal_sha256"] = sha256_file(wal)
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True,
                              timeout=10)
        try:
            out["quick_check"] = con.execute(
                "PRAGMA quick_check").fetchone()[0]
            counts = {}
            for table in LIVE_DB_TABLES:
                try:
                    counts[table] = con.execute(
                        f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except Exception:
                    counts[table] = None
            out["row_counts"] = counts
        finally:
            con.close()
    except Exception as exc:
        out["error"] = repr(exc)
    return out


def _pid_tree(pid: int) -> list[int]:
    pids = [int(pid)]
    i = 0
    while i < len(pids):
        child = run(["pgrep", "-P", str(pids[i])])
        for line in (child.stdout or "").splitlines():
            try:
                pids.append(int(line.strip()))
            except ValueError:
                pass
        i += 1
    return sorted(set(pids))


def live_db_holders(path: Path, pid: int | None = None) -> dict:
    """Which processes hold the live DB/WAL open, via lsof."""
    targets = [path, Path(str(path) + "-wal"), Path(str(path) + "-shm")]
    target_strs = {str(t) for t in targets}
    out = {"path": str(path), "holders": []}
    if not path.exists():
        return out
    cmd = ["lsof", "-F", "pcn"]
    if pid is not None:
        pids = _pid_tree(int(pid))
        out["pid_tree"] = pids
        cmd += ["-p", ",".join(str(p) for p in pids)]
    else:
        cmd += [str(path)]
    r = run(cmd)
    out["lsof_rc"] = r.returncode
    current = {}
    holders = []
    for line in (r.stdout or "").splitlines():
        if line.startswith("p"):
            if current:
                holders.append(current)
            current = {"pid": int(line[1:])}
        elif line.startswith("c") and current is not None:
            current["command"] = line[1:]
        elif line.startswith("n") and current is not None:
            name = line[1:]
            if name in target_strs or name.startswith(str(path)):
                current.setdefault("names", []).append(name)
    if current:
        holders.append(current)
    out["holders"] = [h for h in holders if h.get("names")]
    return out


def declared_env() -> dict:
    data = SCRATCH / "data"
    data.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": "en_US.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "DATABASE_URL": f"sqlite:///{SCRATCH}/atom.db",
        "ATOM_DATA_DIR": str(data),
        "LANCEDB_URI": str(SCRATCH / "atom_memory"),
        "LANCEDB_URI_BASE": str(SCRATCH / "atom_memory"),
        "BYOK_CONFIG_FILE": str(SCRATCH / "byok_config.json"),
        "BYOK_KEYS_FILE": str(SCRATCH / "byok_keys.json"),
        "BYOK_ENC_KEY_FILE": str(SCRATCH / "byok_encryption_key"),
        "CHAT_FINALIZATION_M1": "1",
        "CHAT_FINALIZATION_M2": "1",
        "ATOM_TASK_LIFECYCLE_ENABLED": "1",
        "ATOM_TURN_DECISION_ROUTING": "1",
        "ATOM_TURN_INTERPRETATION": "1",
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ENVIRONMENT": "development",
        "ALLOW_DEV_TEMP_USERS": "true",
        "EMBEDDING_PROVIDER": "fastembed",
        "FASTEMBED_MODEL": "BAAI/bge-small-en-v1.5",
        "EMBEDDING_DIM": "384",
        # Pilot-class default for unpinned/legacy paths; NOT the structured
        # route. Structured turns carry the DeepSeek credential + pins.
        "OPENCODE_BASE_URL": "https://opencode.ai/zen/go/v1",
        # The reply / intent leg is the proven local Ollama route (the L3
        # parent acceptance also answered through llama3.1:8b). DeepSeek is
        # pinned for structured interpretation and edit planning only.
        "ATOM_PROVIDER": "ollama",
        "ATOM_DEFAULT_MODEL": "llama3.1:8b",
        "PREFERRED_PROVIDER": "ollama",
        "ATOM_PREFERRED_LLM_PROVIDER": "ollama",
        "ATOM_PREFERRED_LLM_MODEL": "llama3.1:8b",
        "ATOM_TURN_INTERPRET_PIN": DEEPSEEK_PIN,
        "ATOM_TURN_INTERPRET_CAPTURE": "1",
        "ATOM_ASYNC_EDIT_PLAN_MODEL": EDIT_PIN,
    }


def launch(tag: str):
    obs = HERE / f"live_rehearsal_observation_{tag}.jsonl"
    log_path = HERE / f"live_rehearsal_server_{tag}.log"
    env = declared_env()
    env.update({
        "L2_CAND_BACKEND": str(CAND_BACKEND),
        "L2_PORT": str(PORT),
        "L2_OBSERVATION_LOG": str(obs),
    })
    log = log_path.open("w")
    os.chmod(log_path, 0o600)
    proc = subprocess.Popen(
        [str(PY), str(HERE / "server_observe.py")],
        cwd=str(CAND_BACKEND), env=env,
        stdout=log, stderr=subprocess.STDOUT)
    return proc, log, obs, log_path


def stop_proc(proc) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=45)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=15)
                except Exception:
                    pass
    except Exception:
        pass
    deadline = time.time() + 60
    while time.time() < deadline and port_open(PORT):
        time.sleep(0.5)


def wait_health(proc, timeout: float = 300.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return None
        try:
            r = httpx.get(f"{BASE}/api/health", timeout=5,
                          trust_env=False)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(2)
    return None


def read_history_retry(session_id: str, auth: dict, uid: str) -> dict:
    last = {}
    for _ in range(12):
        hist = base.read_history(session_id, auth, uid)
        last = hist
        if hist.get("http") == 200:
            return hist
        time.sleep(1)
    return last


def date_ok(text: str) -> bool:
    low = str(text or "").casefold()
    return any(x in low for x in (
        "2026-12-31", "december 31, 2026", "dec 31, 2026",
        "12/31/2026", "12-31-2026"))


def wrong_date(text: str) -> bool:
    return any(x in str(text or "") for x in WRONG_VALUES)


def cf_of(step: dict) -> dict:
    return (step.get("context_fulfillment")
            or (step.get("fallback_state") or {}).get(
                "context_fulfillment") or {})


def restart_execution_ok(edit_brief: dict, reask_brief: dict,
                         s7_brief: dict, expected_reask_id: str) -> bool:
    """Check the flattened ``exec_brief`` records captured after restart.

    ``restart`` stores ``execution_record`` rows through ``exec_brief``
    (mutation/objective flattened), not through the nested
    ``task_outcome``. Read the shape that was actually persisted.
    """
    edit_brief = edit_brief or {}
    reask_brief = reask_brief or {}
    s7_brief = s7_brief or {}
    return bool(
        edit_brief.get("found") is True
        and edit_brief.get("objective_met") is True
        and (edit_brief.get("mutation") or {}).get(
            "readback_matched") is True
        and reask_brief.get("found") is True
        and str(reask_brief.get("execution_id") or "")
        == str(expected_reask_id or "")
        and s7_brief.get("found") is True
        and s7_brief.get("objective_met") is True)


def task_of(step: dict) -> dict:
    """The execution summary with the durable row's outcome as an additive
    fallback.

    The base ``task_summary`` intentionally projects only a few fields, so
    edit-specific evidence (``mutation``) was absent from the attempt-2
    extraction even though the durable row carried it
    (``mutation.readback_matched=true``). Merging the row's ``task_outcome``
    under the summary — never overriding what the summary already states —
    reconstructs the full record from preserved evidence without rewriting
    the attempt-2 result.
    """
    execution = step.get("execution") or {}
    summary = dict(execution.get("task_summary") or {})
    row_outcome = (execution.get("row") or {}).get("task_outcome") or {}
    for key, value in row_outcome.items():
        summary.setdefault(key, value)
    return summary


def eid_of(step: dict) -> str:
    return str((step.get("execution") or {}).get(
        "response_execution_id") or "")


def msg_of(step: dict) -> str:
    final = step.get("settlement") or {}
    initial = step.get("initial_response") or {}
    return str(final.get("final_message") or initial.get("message") or "")


def initial_msg_of(step: dict) -> str:
    return str((step.get("initial_response") or {}).get("message") or "")


def canvas_edit_payload(step: dict) -> dict:
    """The canvas-edit receipt. Served canvas edits carry it under
    ``metadata.canvas_edit``; older/synchronous shapes used ``data``.
    Attempt 1's no-op receipt was missed because only ``data`` was read."""
    for src in (
            step.get("initial_response") or {},
            step.get("settlement") or {},
            (step.get("fresh_history") or {}).get(
                "assistant_response") or {}):
        for container in (src.get("metadata"), src.get("data")):
            if not isinstance(container, dict):
                continue
            ce = container.get("canvas_edit") or {}
            if isinstance(ce, dict) and ce:
                return ce
    return {}


def agreement(initial, final, fresh, last_meta, eid, rec) -> bool:
    out = final.get("final_outcome")
    succ = final.get("final_success")
    if out is None or succ is None:
        return False
    if last_meta.get("meta_outcome") != out:
        return False
    if last_meta.get("meta_success") != succ:
        return False
    fresh_out = fresh.get("outcome")
    fresh_succ = fresh.get("success")
    if fresh_out is not None and fresh_out != out:
        return False
    if fresh_succ is not None and fresh_succ != succ:
        return False
    if initial.get("success") not in (None, succ):
        return False
    if initial.get("outcome") not in (None, "unconfirmed", out):
        return False
    task = (rec or {}).get("task_outcome") or {}
    if str(task.get("execution_id") or "") != eid:
        return False
    if str((rec or {}).get("row_id") or "") != eid:
        return False
    return True


def simple_agreement(step: dict) -> bool:
    final = step.get("settlement") or {}
    initial = step.get("initial_response") or {}
    fresh = (step.get("fresh_history") or {}).get(
        "assistant_response") or {}
    rows = [r for r in (step.get("persisted_rows") or [])
            if r.get("role") == "assistant"]
    last = rows[-1] if rows else {}
    out = final.get("final_outcome")
    succ = final.get("final_success")
    if out is None or succ is None:
        return False
    if last.get("meta_outcome") != out:
        return False
    if last.get("meta_success") != succ:
        return False
    if fresh.get("outcome") is not None and fresh.get("outcome") != out:
        return False
    if fresh.get("success") is not None and fresh.get("success") != succ:
        return False
    if initial.get("outcome") not in (None, "unconfirmed", out):
        return False
    if initial.get("success") not in (None, succ):
        return False
    return True


def cf_completed(cf: dict, task: dict) -> bool:
    matched = [str(m.get("file_name") or "")
               for m in (cf.get("matched") or [])
               if isinstance(m, dict)]
    supplied = [str(f) for f in (cf.get("supplied_fields") or [])]
    date_field = any(w in " ".join(supplied).casefold()
                     for w in ("expiration", "valid", "date"))
    return bool(
        cf.get("state") == "completed"
        and FIXTURE_NAME in matched
        and date_field
        and task.get("objective_met") is True
        and (task.get("delivery") or {}).get("delivered") is True)


def cf_partial(cf: dict, task: dict, fallback: dict) -> bool:
    matched = [str(m.get("file_name") or "")
               for m in (cf.get("matched") or [])
               if isinstance(m, dict)]
    supplied = [str(f) for f in (cf.get("supplied_fields") or [])]
    date_field = any(w in " ".join(supplied).casefold()
                     for w in ("expiration", "valid", "date"))
    gap = bool(cf.get("missing_comparison")
               or (cf.get("missing_fields") or []))
    return bool(
        cf.get("state") == "partial"
        and gap
        and FIXTURE_NAME in matched
        and date_field
        and (task.get("delivery") or {}).get("delivered") is True
        and bool((fallback or {}).get("open_work")))


def settlement_ok(final: dict, cf: dict, task: dict,
                  fallback: dict) -> bool:
    if final.get("final_success") is not True:
        return False
    outcome = final.get("final_outcome")
    if outcome == "completed":
        return cf_completed(cf, task)
    if outcome == "partial":
        return cf_partial(cf, task, fallback)
    return False


def open_task_obligations(db_file: Path,
                          conversation_id: str) -> list[dict] | None:
    """Open unresolved questions from the conversation's task lifecycle.

    The successor prefers the structured questions
    (``GoalRun.parameters.task_lifecycle.task_revision.unresolved``) over
    the resolver's text snapshot. Returns ``None`` when no structured task
    record is available at all — only then may the caller use the
    explicitly bounded text fallback. An empty list means the record
    exists and has no open structured questions.
    """
    conversation = str(conversation_id or "").strip()
    if not conversation:
        return None
    try:
        rows = base.db_read_rows(
            db_file,
            "SELECT parameters FROM goal_runs ORDER BY rowid DESC")
    except Exception:  # noqa: BLE001 — absence is a disclosed fallback
        return None
    for (raw,) in rows:
        try:
            params = json.loads(raw or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(params, dict):
            continue
        lifecycle = params.get("task_lifecycle")
        if not isinstance(lifecycle, dict):
            continue
        if str(lifecycle.get("conversation_id") or "") != conversation:
            continue
        revision = lifecycle.get("task_revision")
        if not isinstance(revision, dict):
            continue
        unresolved = revision.get("unresolved")
        if not isinstance(unresolved, list):
            return []
        return [dict(q) for q in unresolved if isinstance(q, dict)]
    return None


def capture_prior_obligation_from_durable_record(
        db_file: Path, conversation_id: str) -> dict | None:
    """Capture THIS run's open prior obligations before S7 starts.

    Called after S3 settles and before the S7 turn is sent. The returned
    identities are the expected prior work; the gate must not derive them
    from whatever S7 later lists as open.
    """
    obligations = open_task_obligations(db_file, conversation_id)
    if obligations is None:
        return None
    return {
        "source": "durable_task_record_before_s7",
        "conversation_id": conversation_id,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "items": [
            dict(item) for item in obligations
            if str(item.get("status") or "open") == "open"],
    }


def stage_summary(step: dict, log_text: str) -> dict:
    request_id = str(step.get("request_id") or "")
    interp_event = ((step.get("observation") or {}).get(
        "interpretation") or {})
    interp = interp_event.get("interpretation") or {}
    dispatch_lines = [
        ln for ln in log_text.splitlines()
        if f"route=turn_interpretation:{request_id}" in ln]
    dispatch_models = sorted({
        m for ln in dispatch_lines
        for m in re.findall(r"\[structured-dispatch\] ([^\s]+)", ln)})
    capture_lines = [
        ln for ln in log_text.splitlines()
        if "[turn-interpretation-capture]" in ln and request_id in ln]
    phases = sorted({
        "pre_validation" if '"pre_validation"' in ln
        else "post_validation"
        for ln in capture_lines if '"phase"' in ln})
    actions = [a for a in (interp.get("actions") or [])
               if isinstance(a, dict)]
    return {
        "request_id": request_id,
        "dispatch_attempted": bool(dispatch_lines),
        "dispatch_models": dispatch_models,
        "interpretation_origin": interp.get("origin"),
        "interpretation_unresolved_reason": interp.get(
            "unresolved_reason"),
        "scope_change": interp.get("scope_change"),
        "action_count": len(actions),
        "action_kinds": [str(a.get("kind") or "") for a in actions],
        "capture_archived": bool(capture_lines),
        "capture_phases": phases,
        "total_turn_latency_s": step.get("latency_s"),
    }


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    env = declared_env()
    procs = []
    logs = []

    head = run(["git", "-C", str(CAND), "rev-parse",
                "HEAD"]).stdout.strip()
    product_commit = run(["git", "-C", str(CAND), "rev-parse",
                          CANDIDATE_SHA]).stdout.strip()
    if product_commit != CANDIDATE_SHA:
        raise RuntimeError("frozen product commit missing; no launch")
    ancestor = run(["git", "-C", str(CAND), "merge-base", "--is-ancestor",
                    CANDIDATE_SHA, "HEAD"])
    if ancestor.returncode != 0:
        raise RuntimeError("candidate product commit not in HEAD; no launch")
    product_diff = run(["git", "-C", str(CAND), "diff", "--name-only",
                        CANDIDATE_SHA, "HEAD", "--", "backend/core",
                        "backend/integrations"])
    product_diff_names = [
        line.strip() for line in (product_diff.stdout or "").splitlines()
        if line.strip()]
    if product_diff_names:
        raise RuntimeError(
            "product source changed after the frozen commit; no launch: "
            + ", ".join(product_diff_names))

    # The later gate commit is launchable only when its runtime product
    # files are byte-identical to the pinned product tree. The diff above
    # is the proof; also require the frozen gate commit itself to be an
    # ancestor and the gate module to match the reviewed freeze.
    gate_commit = run(["git", "-C", str(CAND), "rev-parse",
                       HARNESS_GATE_COMMIT]).stdout.strip()
    if gate_commit != HARNESS_GATE_COMMIT:
        raise RuntimeError("frozen gate commit missing; no launch")
    gate_ancestor = run(["git", "-C", str(CAND), "merge-base",
                         "--is-ancestor", HARNESS_GATE_COMMIT, "HEAD"])
    if gate_ancestor.returncode != 0:
        raise RuntimeError("frozen gate commit not in HEAD; no launch")
    gate_hash = sha256_file(HERE / "successor_gates_live.py")
    if gate_hash != EXPECTED_GATES_SHA256:
        raise RuntimeError("successor gate module changed; no launch")

    if run(["git", "-C", str(CAND), "status", "--porcelain"]).stdout.strip():
        raise RuntimeError("candidate dirty; no launch")
    if port_open(PORT):
        raise RuntimeError("acceptance port occupied; no launch")
    if not PRE_DECL.exists():
        raise RuntimeError("predeclared configuration missing; no launch")

    predecl_sha = sha256_file(PRE_DECL)
    cfg = {
        "attempt": "live-rehearsal-1",
        "declared_at": stamp,
        "predeclared_config": {"path": str(PRE_DECL),
                               "sha256": predecl_sha},
        "candidate": {
            "worktree": str(CAND),
            "branch": run(["git", "-C", str(CAND), "branch",
                           "--show-current"]).stdout.strip(),
            "product_commit": PRODUCT_SHA,
            "head_at_launch": head,
            "harness_commit": head,
            "product_tree_equals_pin": True,
            "product_diff_names": product_diff_names,
            "status_clean": True,
            "parents": {
                "l3_contains_l1": "6d662abff (L1 aaa1169d7)",
                "l2": "c0cbea9f1",
                "main": "e6308cb54",
                "base_candidate": "ddcc404dd",
            },
            "source_sha256": source_hashes(CAND_BACKEND),
        },
        "interpreter": {
            "absolute_path": str(PY),
            "version": run([str(PY), "--version"]).stdout.strip(),
        },
        "harness": {
            "gate_commit": HARNESS_GATE_COMMIT,
            "gate_tag": HARNESS_GATE_TAG,
            "gate_module_sha256": gate_hash,
            "runner_sha256": sha256_file(Path(__file__)),
            "server_observe_sha256": sha256_file(
                HERE / "server_observe.py"),
        },
        "ports": {"backend": PORT, "frontend": None},
        "isolation": {
            "cwd": str(CAND_BACKEND),
            "scratch_dir": str(SCRATCH),
            "database_url": f"sqlite:///{SCRATCH}/atom.db",
            "stores": ["DATABASE_URL", "ATOM_DATA_DIR", "LANCEDB_URI",
                       "LANCEDB_URI_BASE", "BYOK_CONFIG_FILE",
                       "BYOK_KEYS_FILE", "BYOK_ENC_KEY_FILE"],
            "live_env_copied_wholesale": False,
            "credential_vault_copied": True,
        },
        "flags": {
            "declared": {
                "CHAT_FINALIZATION_M1": "1",
                "CHAT_FINALIZATION_M2": "1",
                "ATOM_TASK_LIFECYCLE_ENABLED": "1",
                "ATOM_TURN_DECISION_ROUTING": "1",
                "ATOM_TURN_INTERPRETATION": "1",
                "ATOM_TURN_INTERPRET_PIN": DEEPSEEK_PIN,
                "ATOM_TURN_INTERPRET_CAPTURE": "1",
                "ATOM_ASYNC_EDIT_PLAN_MODEL": EDIT_PIN,
                "ATOM_PROVIDER": "ollama",
                "ATOM_DEFAULT_MODEL": "llama3.1:8b",
                "PREFERRED_PROVIDER": "ollama",
                "ATOM_PREFERRED_LLM_PROVIDER": "ollama",
                "ATOM_PREFERRED_LLM_MODEL": "llama3.1:8b",
            },
        },
        "model": {
            "structured_route": CREDENTIAL_ROUTE,
            "interpretation": ("DeepSeek direct, pinned "
                               f"{DEEPSEEK_PIN}; actual origin recorded"),
            "edit_planning": (f"configured {EDIT_PIN}; the deterministic "
                              "assignment/no-op path may run without an "
                              "LLM plan; actual path recorded"),
            "tool_planning": ("product-selected structured dispatch; the "
                              "full pilot BYOK registry is copied into the "
                              "isolated scratch world and DeepSeek is "
                              "pinned for structured interpretation/edit "
                              "planning; actual routes recorded"),
            "reply": ("declared local Ollama llama3.1:8b (the L3 parent "
                      "acceptance's observed reply route); DeepSeek is the "
                      "declared fallback; actual reply route recorded"),
            "credentials": [{
                "provider": CREDENTIAL_PROVIDER,
                "key_name": CREDENTIAL_KEY_NAME,
                "environment": CREDENTIAL_ENVIRONMENT,
                "source": "pilot BYOK copied into isolated scratch",
                "value_recorded": False,
                "vault_copied_wholesale": True,
            }],
        },
        "embeddings": {"provider": "fastembed",
                       "model": "BAAI/bge-small-en-v1.5", "dim": 384},
        "observation_harness": {
            "launcher": str(HERE / "server_observe.py"),
            "candidate_source_edited": False,
            "hooks": [
                "interpret_turn_request",
                "apply_interpretation_references",
                "_stash_evidence_requirement",
                "_context_backed_fulfillment",
                "_fallback_turn_outcome",
            ],
        },
        "job": {
            "fixtures": [FIXTURE_NAME, L3_FIXTURE_NAME],
            "upload_route": "POST /api/documents/upload",
            "l3_ask": L3_ASK,
            "l3_expected_code": L3_EXPECTED_CODE,
            "l3_decoy_code": L3_DECOY_CODE,
            "edit_ask": EDIT_ASK,
            "reask": ("identical EDIT_ASK in the same session/canvas "
                      "(session A)"),
            "s3_ask": S3_ASK,
            "s7_ask": S7_ASK,
            "comparison_session": ("fresh conversation (session B) against "
                                   "the same draft, so the comparison is a "
                                   "replace-scope request as in the L2 "
                                   "attempt-12 acceptance"),
            "restart": "stop/relaunch the same scratch process/stores; "
                       "reload both sessions' history/canvas/audits",
        },
        "live_db_guard": {
            "path": str(LIVE_DB),
            "before": live_db_fingerprint(LIVE_DB),
            "holders_before": live_db_holders(LIVE_DB),
        },
        "pilot_before": base.pilot_identity(),
    }
    actual_sources = cfg["candidate"]["source_sha256"]
    for key, expected in EXPECTED_SOURCE_SHA256.items():
        if actual_sources.get(key) != expected:
            raise RuntimeError(
                f"frozen source hash mismatch for {key}; no launch")
    (HERE / "live_rehearsal_config.json").write_text(
        json.dumps(cfg, indent=2, sort_keys=True, default=str))

    SCRATCH.mkdir(parents=True, exist_ok=True)
    freeze = run([str(PY), "-m", "pip", "freeze"])
    (HERE / "live_rehearsal_interpreter_freeze.txt").write_text(freeze.stdout)

    db_file = SCRATCH / "atom.db"
    if db_file.exists():
        raise RuntimeError("rehearsal world already exists; refuse reuse")
    import gzip as _gzip
    import shutil as _shutil
    _snapshot = Path(
        "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/"
        "opencode/atom-cutover-final-20261024/"
        "atom-pre-cutover-final-20261024-091936.db.gz")
    if not _snapshot.exists():
        raise RuntimeError("pre-cutover snapshot missing; no rehearsal")
    with _gzip.open(_snapshot, "rb") as _src, db_file.open("wb") as _dst:
        _shutil.copyfileobj(_src, _dst, length=1024 * 1024)
    # UNFILTERED BYOK: copy the pilot's full provider configuration into
    # the isolated scratch world. The live files are only read.
    for _name in ("byok_config.json", "byok_keys.json",
                  "byok_encryption_key"):
        _src = MAIN / "backend/data" / _name
        _dst = SCRATCH / _name
        if not _src.exists():
            raise RuntimeError(f"live BYOK file missing: {_src}")
        _shutil.copy2(_src, _dst)
        _dst.chmod(0o600)
    _byok_keys = json.loads(
        (SCRATCH / "byok_keys.json").read_text()).get("keys") or {}
    cfg["byok_copy"] = {
        "source": str(MAIN / "backend/data"),
        "destination": str(SCRATCH),
        "files": ["byok_config.json", "byok_keys.json",
                  "byok_encryption_key"],
        "keys_count": len(_byok_keys),
        "provider_ids": sorted({
            str(row.get("provider_id"))
            for row in _byok_keys.values() if row.get("provider_id")}),
        "live_files_modified": False,
    }
    (HERE / "live_rehearsal_config.json").write_text(
        json.dumps(cfg, indent=2, sort_keys=True, default=str))
    # The snapshot is the live-world shape; all auxiliary stores remain
    # fresh/isolated under SCRATCH. No background/outbound writers run
    # because declared_env disables the scheduler and ingestion sync.
    for existing in (HERE / "live_rehearsal_observation_pre.jsonl",
                     HERE / "live_rehearsal_observation_restart.jsonl"):
        if existing.exists():
            raise RuntimeError("observation log already exists; refuse reuse")

    result = {"declared_config": cfg, "steps": {}}
    proc, log, obs_path, server_log_path = launch("pre")
    procs.append(proc)
    logs.append(log)

    def capture_after_guards():
        if "pilot_after" not in result:
            result["pilot_after"] = base.pilot_identity()
        if "live_db_guard_after" not in result:
            after = live_db_fingerprint(LIVE_DB)
            before = cfg["live_db_guard"]["before"]
            active = procs[-1] if procs else None
            scratch_pid = (active.pid
                           if active is not None
                           and active.poll() is None else None)
            scratch_holders = (
                live_db_holders(LIVE_DB, pid=scratch_pid)
                if scratch_pid else {"holders": [], "pid_tree": []})
            env = declared_env()
            scratch_paths_isolated = bool(
                str(SCRATCH) in env["DATABASE_URL"]
                and str(SCRATCH) in env["ATOM_DATA_DIR"]
                and str(SCRATCH) in env["LANCEDB_URI"]
                and scratch_pid is not None)
            result["live_db_guard_after"] = {
                "fingerprint": after,
                "holders": live_db_holders(LIVE_DB),
                "scratch_holders": scratch_holders,
                "scratch_paths_isolated": scratch_paths_isolated,
                "unchanged": after == before,
                "isolated": bool(
                    not (scratch_holders.get("holders") or [])
                    and scratch_paths_isolated),
            }

    def finish_result(output_summary: dict | None = None) -> int:
        capture_after_guards()
        for p in procs:
            stop_proc(p)
        for lh in logs:
            try:
                lh.close()
            except Exception:
                pass
        result["observation_events"] = base.load_events(obs_path)
        restart_obs = HERE / "live_rehearsal_observation_restart.jsonl"
        if restart_obs.exists():
            result["restart_observation_events"] = base.load_events(
                restart_obs)
        (HERE / "live_rehearsal_result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True, default=str))
        summary = output_summary or {}
        summary.update({
            "attempt": "live-rehearsal-1",
            "classification": result.get("classification"),
            "pass": result.get("pass"),
            "checks": result.get("checks"),
            "first_failure": result.get("first_failure"),
            "stage_summary": result.get("stage_summary"),
            "provider_routes": result.get("provider_routes"),
            "runtime_identity": (result.get("steps", {}).get(
                "runtime_identity")),
            "live_db_unchanged": (result.get("live_db_guard_after") or {}
                                  ).get("unchanged"),
            "live_db_isolated": (result.get("live_db_guard_after") or {}
                                  ).get("isolated"),
            "live_db_guard_after": result.get("live_db_guard_after"),
            "pilot_untouched": result.get("pilot_untouched"),
        })
        (HERE / "live_rehearsal_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True, default=str))
        print(json.dumps(summary, indent=2, default=str))
        return 0 if result.get("pass") else 1

    def api_events_for(request_id: str) -> dict:
        events = base.load_events(obs_path)
        matched = base.events_for_request(events, request_id)
        return {
            "interpretation": base.last_event(
                matched, "interpret_turn_request"),
            "apply": base.last_event(
                matched, "apply_interpretation_references"),
            "events": matched,
        }

    def capture_turn(label: str, ask: str, session_id: str, auth: dict,
                     uid: str, cid: str | None,
                     canvas_before: str | None,
                     audit_before: list | None) -> dict:
        request_id = f"l1l2l3-{label}-{uuid.uuid4().hex}"
        context = {"request_id": request_id}
        if cid:
            context["canvas_id"] = cid
        t0 = time.monotonic()
        chat = httpx.post(
            f"{BASE}/api/chat/message", headers=auth,
            json={"message": ask, "session_id": session_id,
                  "user_id": uid, "context": context},
            timeout=900, trust_env=False)
        latency = time.monotonic() - t0
        try:
            chat_json = chat.json()
        except Exception:
            chat_json = {"_raw": chat.text[:4000]}
        step = {
            "request_id": request_id,
            "ask": ask,
            "canvas_id": cid,
            "http": chat.status_code,
            "latency_s": round(latency, 2),
            "initial_response": chat_json,
        }
        final, polls = base.poll_settlement(
            session_id, auth, uid, t0, proc)
        time.sleep(1.0)
        fresh = read_history_retry(session_id, auth, uid)
        step["settlement"] = {
            "polls": polls,
            "final_outcome": final.get("outcome"),
            "final_success": final.get("success"),
            "final_error_code": final.get("error_code"),
            "final_message": str(final.get("message") or "")[:4000],
            "final_execution_id": final.get("execution_id"),
        }
        step["fresh_history"] = {
            "http": fresh.get("http"),
            "assistant_count": fresh.get("assistant_count"),
            "assistant_response": fresh.get("assistant_response"),
        }
        step["persisted_rows"] = base.persisted_rows(db_file, session_id)

        if cid:
            got_after = httpx.get(f"{BASE}/api/canvas/{cid}",
                                  headers=auth, timeout=60,
                                  trust_env=False).json()
            step["canvas_before"] = canvas_before
            step["canvas_after"] = base.canvas_body(got_after)
            step["audit_before"] = audit_before or []
            step["audit_after"] = base.audits(db_file, cid)
        else:
            step["canvas_before"] = None
            step["canvas_after"] = None
            step["audit_before"] = None
            step["audit_after"] = None

        exec_candidates = [
            chat_json.get("execution_id")
            if isinstance(chat_json, dict) else None,
            final.get("execution_id"),
            fresh.get("assistant_response", {}).get("execution_id"),
        ]
        exec_id = next((str(e) for e in exec_candidates if e), "")
        rec = base.execution_record(db_file, exec_id)
        step["execution"] = {
            "response_execution_id": exec_id,
            "execution_candidates": [str(e) for e in exec_candidates
                                     if e],
            "row_found": bool(rec),
            "row": rec,
            "task_summary": base.task_summary(rec),
        }

        obs = api_events_for(request_id)
        step["observation"] = obs
        stash_event = None
        for e in obs.get("events") or []:
            if e.get("event") == "stash_evidence_requirement":
                if not exec_id or str(
                        e.get("execution_id") or "") == exec_id:
                    stash_event = e
        if stash_event is None:
            for e in base.load_events(obs_path):
                if (e.get("event") == "stash_evidence_requirement"
                        and e.get("message") == ask
                        and (not exec_id
                             or str(e.get("execution_id") or "")
                             == exec_id)):
                    stash_event = e
        step["requirement_event"] = stash_event
        step["requirement_summary"] = (
            stash_event.get("requirement") if stash_event else None)
        step["accepted_request"] = (
            stash_event.get("accepted_request") if stash_event else None)
        cf_event = None
        fb_event = None
        for e in base.load_events(obs_path):
            if str(e.get("execution_id") or "") != exec_id:
                continue
            if e.get("event") == "context_backed_fulfillment":
                cf_event = e
            if e.get("event") == "fallback_turn_outcome":
                fb_event = e
        step["context_fulfillment"] = (cf_event or {}).get("verdict")
        step["fallback_state"] = (fb_event or {}).get("state")
        return step

    try:
        health = wait_health(proc)
        result["steps"]["health"] = health
        if not health:
            result["classification"] = "server_not_healthy"
            result["pass"] = False
            return finish_result()

        identity = health.get("identity") or {}
        result["steps"]["runtime_identity"] = {
            "cwd": identity.get("cwd"),
            "git_commit": identity.get("git_commit"),
            "dirty": identity.get("dirty"),
            "source_id": identity.get("source_id"),
            "revision": identity.get("revision"),
            "candidate_cwd_ok": str(identity.get("cwd") or "")
            == str(CAND_BACKEND),
            "candidate_commit_ok": str(
                identity.get("git_commit") or "").startswith(
                    head[:12]),
        }
        if not (result["steps"]["runtime_identity"]["candidate_cwd_ok"]
                and result["steps"]["runtime_identity"][
                    "candidate_commit_ok"]
                and result["steps"]["runtime_identity"]["dirty"] is False):
            result["classification"] = "runtime_identity_mismatch"
            result["pass"] = False
            return finish_result()

        # Provider parity is part of the declared configuration. Warm the
        # local Ollama model BEFORE the first user turn; the live-world
        # attempt-3 trace showed L3/S3 cold-start streaming produced no
        # tokens after 10 s and silently fell back to DeepSeek. A warm-up is
        # readiness, not a provider switch; the parity check below still
        # rejects any turn that falls back.
        try:
            _warm_t0 = time.monotonic()
            _warm = httpx.post(
                "http://127.0.0.1:11434/api/generate",
                json={"model": "llama3.1:8b",
                      "prompt": "Reply with the single word OK.",
                      "stream": False,
                      "options": {"num_predict": 8}},
                timeout=180, trust_env=False)
            result["steps"]["ollama_warmup"] = {
                "http": _warm.status_code,
                "duration_s": round(time.monotonic() - _warm_t0, 2),
                "has_response": bool(
                    (_warm.json() or {}).get("response"))
                if _warm.status_code == 200 else False,
            }
        except Exception as _warm_err:  # noqa: BLE001
            result["steps"]["ollama_warmup"] = {
                "error": type(_warm_err).__name__,
            }
        if not (result["steps"]["ollama_warmup"].get("http") == 200
                and result["steps"]["ollama_warmup"].get(
                    "has_response") is True):
            result["classification"] = "ollama_warmup_failed"
            result["pass"] = False
            return finish_result()

        email = f"l1l2l3_{uuid.uuid4().hex[:10]}@example.com"
        password = "L1L2L3-" + uuid.uuid4().hex[:12] + "A1"
        reg = httpx.post(f"{BASE}/api/auth/register",
                         json={"email": email, "password": password,
                               "first_name": "L1L2L3",
                               "last_name": "Composed"},
                         timeout=60, trust_env=False)
        result["steps"]["register"] = {"http": reg.status_code}
        tok = (reg.json().get("access_token")
               if reg.status_code == 200 else None)
        if not tok:
            lg = httpx.post(f"{BASE}/api/auth/login",
                            json={"email": email, "username": email,
                                  "password": password},
                            timeout=60, trust_env=False)
            tok = (lg.json().get("access_token")
                   if lg.status_code == 200 else None)
            result["steps"]["login_fallback"] = {"http": lg.status_code}
        if not tok:
            result["classification"] = "auth_failed"
            result["pass"] = False
            return finish_result()
        auth = {"Authorization": f"Bearer {tok}"}
        me = httpx.get(f"{BASE}/api/auth/me", headers=auth, timeout=30,
                       trust_env=False).json()
        uid = me.get("id")
        workspace_id = str(me.get("workspace_id") or "")
        result["steps"]["user"] = {"id": uid,
                                   "workspace_id": workspace_id}
        if not uid:
            result["classification"] = "user_resolution_failed"
            result["pass"] = False
            return finish_result()

        # ONE authorized operator credential, through the product.
        from cryptography.fernet import Fernet
        vault = MAIN / "backend/data/byok_keys.json"
        enc = MAIN / "backend/data/byok_encryption_key"
        vault_row = json.loads(
            vault.read_text())["keys"][CREDENTIAL_VAULT_KEY]
        assert vault_row.get("provider_id") == CREDENTIAL_PROVIDER
        assert vault_row.get("key_name") == CREDENTIAL_KEY_NAME
        assert vault_row.get("environment") == CREDENTIAL_ENVIRONMENT
        assert vault_row.get("is_active", True) is True
        key = Fernet(enc.read_bytes().strip()).decrypt(
            vault_row["encrypted_key"].encode()).decode()
        assert key, "authorized credential unavailable"
        oact = httpx.post(
            f"{BASE}/api/ai/providers/{CREDENTIAL_PROVIDER}/keys",
            headers=auth,
            json={"api_key": key, "key_name": CREDENTIAL_KEY_NAME,
                  "environment": CREDENTIAL_ENVIRONMENT,
                  "label": CREDENTIAL_LABEL},
            timeout=60, trust_env=False)
        result["steps"][CREDENTIAL_STEP] = {
            "store_http": oact.status_code,
            "credential_value_recorded": False,
            "route": CREDENTIAL_ROUTE,
        }
        del key, vault_row
        if oact.status_code != 200:
            result["classification"] = (
                "authorized_provider_registration_failed")
            result["pass"] = False
            return finish_result()
        providers = httpx.get(f"{BASE}/api/ai/providers", headers=auth,
                              timeout=60, trust_env=False)
        try:
            pj = providers.json()
        except Exception:
            pj = {}
        state = next(
            (p for p in ((pj.get("data") or {}).get("providers") or [])
             if (p.get("provider") or {}).get("id")
             == CREDENTIAL_PROVIDER), None)
        credential_active = bool(
            state and (state.get("status") == "active"
                       or state.get("is_active")
                       or state.get("has_api_key")
                       or state.get("has_keys")))
        result["steps"][CREDENTIAL_STEP]["active"] = credential_active

        # Both fixtures, uploaded through the PRODUCT: the L3 parent
        # acceptance's Zephyr-9 brief (proven documents-source ask) and the
        # approved records used by the L2 comparison.
        uploads = []
        for name, text in ((FIXTURE_NAME, FIXTURE_TEXT),
                           (L3_FIXTURE_NAME, L3_FIXTURE_TEXT)):
            up = httpx.post(
                f"{BASE}/api/documents/upload", headers=auth,
                files={"file": (name, text.encode("utf-8"),
                                "text/plain")},
                timeout=300, trust_env=False)
            try:
                up_json = up.json()
            except Exception:
                up_json = {"_raw": up.text[:800]}
            row = None
            if up_json.get("id"):
                rows = base.db_read_rows(
                    db_file,
                    "SELECT id, file_name, workspace_id, content_preview, "
                    "file_size_bytes FROM ingested_documents WHERE id=?",
                    (up_json.get("id"),))
                if rows:
                    row = rows[0]
            uploads.append({
                "http": up.status_code,
                "doc_id": up_json.get("id"),
                "title": up_json.get("title"),
                "chunk_count": up_json.get("chunk_count"),
                "row": ({"id": row[0], "file_name": row[1],
                         "workspace_id": row[2],
                         "preview_has_date": "2026-12-31"
                         in str(row[3] or ""),
                         "preview_has_code": L3_EXPECTED_CODE
                         in str(row[3] or ""),
                         "size": row[4]} if row else None),
            })
        result["steps"]["upload"] = {"uploads": uploads}
        approved_up, l3_up = uploads[0], uploads[1]
        upload_ok = bool(
            all(u["http"] == 200 and u["doc_id"] and u["row"]
                for u in uploads)
            and approved_up["row"]["file_name"] == FIXTURE_NAME
            and approved_up["row"]["preview_has_date"]
            and l3_up["row"]["file_name"] == L3_FIXTURE_NAME
            and l3_up["row"]["preview_has_code"])

        # Session A carries the L3 sourced answer, edit and identical
        # re-ask. Session B is a fresh comparison conversation against the
        # same draft: the L2 request-bound comparison is a replace-scope
        # request (attempt 12), and a continuation in session A narrowed
        # the same ask to the date in attempt 1.
        session_a = str(uuid.uuid4())
        session_b = str(uuid.uuid4())
        result["steps"]["session_id"] = {"a": session_a, "b": session_b}
        canvas_count_before_l3 = base.db_read_rows(
            db_file, "SELECT COUNT(*) FROM canvases")[0][0]

        # STAGE 1 — L3 sourced answer (no canvas context).
        l3 = capture_turn("l3", L3_ASK, session_a, auth, uid,
                          None, None, None)
        result["steps"]["l3"] = l3
        canvas_count_after_l3 = base.db_read_rows(
            db_file, "SELECT COUNT(*) FROM canvases")[0][0]

        # The draft, created through the PRODUCT.
        ccreate = httpx.post(f"{BASE}/api/canvas", headers=auth,
                             json={"title": CANVAS_TITLE,
                                   "canvas_type": "document"},
                             timeout=60, trust_env=False)
        try:
            ccreate_json = ccreate.json()
        except Exception:
            ccreate_json = {}
        cid = ccreate_json.get("canvas_id")
        result["steps"]["canvas"] = {"create_http": ccreate.status_code,
                                     "canvas_id": cid}
        if ccreate.status_code != 200 or not cid:
            result["classification"] = "canvas_create_failed"
            result["pass"] = False
            return finish_result()
        cput = httpx.put(f"{BASE}/api/canvas/{cid}", headers=auth,
                         json=CANVAS_BODY, timeout=60, trust_env=False)
        got = httpx.get(f"{BASE}/api/canvas/{cid}", headers=auth,
                        timeout=60, trust_env=False).json()
        seeded_body = base.canvas_body(got)
        result["steps"]["canvas"].update({
            "seed_http": cput.status_code,
            "seeded_body": seeded_body,
            "seed_exact": seeded_body == CANVAS_BODY,
        })
        seed_ok = bool(cput.status_code == 200
                       and seeded_body == CANVAS_BODY)
        baseline_audits = base.audits(db_file, cid)
        result["steps"]["baseline_audits"] = baseline_audits

        # STAGE 2 — edit (one real write).
        edit = capture_turn("edit", EDIT_ASK, session_a, auth, uid,
                            cid, seeded_body, baseline_audits)
        result["steps"]["edit"] = edit

        # STAGE 3 — identical re-ask (no-op, zero additional writes).
        reask = capture_turn("reask", EDIT_ASK, session_a, auth, uid,
                             cid, edit["canvas_after"],
                             edit["audit_after"])
        result["steps"]["reask"] = reask

        # STAGE 4 — comparison in the fresh conversation (replace scope,
        # broader obligation visibly open).
        s3 = capture_turn("s3", S3_ASK, session_b, auth, uid,
                          cid, reask["canvas_after"],
                          reask["audit_after"])
        result["steps"]["s3"] = s3

        # CAPTURE THE PRIOR OBLIGATION FROM THIS RUN BEFORE S7. The
        # expected identity must not be derived from S7's own open list.
        s7_expected_prior = capture_prior_obligation_from_durable_record(
            db_file, session_b)

        # STAGE 5 — date-only continuation in the comparison conversation.
        s7 = capture_turn("s7", S7_ASK, session_b, auth, uid,
                          cid, s3["canvas_after"], s3["audit_after"])
        s7["expected_prior"] = s7_expected_prior
        result["steps"]["s7"] = s7

        # STAGE 6 — restart/reload agreement for BOTH conversations.
        def last_assistant(rows):
            for r in reversed(rows or []):
                if r.get("role") == "assistant":
                    return r
            return {}

        def exec_brief(rec):
            to = (rec or {}).get("task_outcome") or {}
            return {
                "found": bool(rec),
                "execution_id": (to.get("execution_id")
                                 or (rec or {}).get("row_id")),
                "status": (rec or {}).get("status"),
                "outcome": to.get("outcome"),
                "success": to.get("success"),
                "objective_met": to.get("objective_met"),
                "mutation": to.get("mutation") or {},
                "delivery": to.get("delivery") or {},
            }

        pre_restart = {
            "session_a": {
                "assistant_count": (reask.get("fresh_history") or {}).get(
                    "assistant_count"),
                "last_response": (reask.get("fresh_history") or {}).get(
                    "assistant_response") or {},
                # Served no-op receipt (metadata.canvas_edit). The durable
                # history row keeps the receipt-derived reply + execution
                # linkage, not this metadata flag.
                "canvas_edit": canvas_edit_payload(reask),
                "assistant_rows": sum(
                    1 for r in (reask.get("persisted_rows") or [])
                    if r.get("role") == "assistant"),
                "last_persisted": last_assistant(
                    reask.get("persisted_rows")),
                "execution_id": eid_of(reask),
            },
            "session_b": {
                "assistant_count": (s7.get("fresh_history") or {}).get(
                    "assistant_count"),
                "last_response": (s7.get("fresh_history") or {}).get(
                    "assistant_response") or {},
                "assistant_rows": sum(
                    1 for r in (s7.get("persisted_rows") or [])
                    if r.get("role") == "assistant"),
                "last_persisted": last_assistant(
                    s7.get("persisted_rows")),
                # The accepted pre-restart S7 state the reload must match.
                "outcome": (s7.get("settlement") or {}).get(
                    "final_outcome"),
                "success": (s7.get("settlement") or {}).get(
                    "final_success"),
                "message": (s7.get("fresh_history") or {}).get(
                    "assistant_response", {}).get("message"),
                "execution_id": eid_of(s7),
                "status": (((s7.get("execution") or {}).get("row") or {})
                           .get("status")),
                "delivery": ((((s7.get("execution") or {}).get("row") or {})
                              .get("task_outcome") or {}).get("delivery")
                             or {}),
            },
            "body": s7.get("canvas_after"),
            "audits": s7.get("audit_after"),
            "execution_ids": {
                "edit": eid_of(edit),
                "reask": eid_of(reask),
                "s7": eid_of(s7),
            },
        }
        stop_proc(proc)
        log.close()
        proc2, log2, obs2_path, server_log2_path = launch("restart")
        procs.append(proc2)
        logs.append(log2)
        health2 = wait_health(proc2)
        result["steps"]["restart_health"] = health2
        if not health2:
            result["classification"] = "restart_server_not_healthy"
            result["pass"] = False
            return finish_result()
        identity2 = health2.get("identity") or {}
        restart_identity = {
            "cwd": identity2.get("cwd"),
            "git_commit": identity2.get("git_commit"),
            "dirty": identity2.get("dirty"),
            "candidate_cwd_ok": str(identity2.get("cwd") or "")
            == str(CAND_BACKEND),
            "candidate_commit_ok": str(
                identity2.get("git_commit") or "").startswith(
                    head[:12]),
        }
        history_a2 = read_history_retry(session_a, auth, uid)
        history_b2 = read_history_retry(session_b, auth, uid)
        got2 = httpx.get(f"{BASE}/api/canvas/{cid}", headers=auth,
                         timeout=60, trust_env=False).json()
        body2 = base.canvas_body(got2)
        audits2 = base.audits(db_file, cid)
        persisted_a2 = base.persisted_rows(db_file, session_a)
        persisted_b2 = base.persisted_rows(db_file, session_b)
        exec_edit2 = base.execution_record(
            db_file, pre_restart["execution_ids"]["edit"])
        exec_reask2 = base.execution_record(
            db_file, pre_restart["execution_ids"]["reask"])
        exec_s7_2 = base.execution_record(
            db_file, pre_restart["execution_ids"]["s7"])
        last_a2 = history_a2.get("assistant_response") or {}
        last_b2 = history_b2.get("assistant_response") or {}
        result["steps"]["restart"] = {
            "identity": restart_identity,
            "session_a": {
                "assistant_count": history_a2.get("assistant_count"),
                "last_response": last_a2,
                "assistant_rows": sum(
                    1 for r in persisted_a2
                    if r.get("role") == "assistant"),
                "last_persisted": last_assistant(persisted_a2),
            },
            "session_b": {
                "assistant_count": history_b2.get("assistant_count"),
                "last_response": last_b2,
                "assistant_rows": sum(
                    1 for r in persisted_b2
                    if r.get("role") == "assistant"),
                "last_persisted": last_assistant(persisted_b2),
                "outcome": last_b2.get("outcome"),
                "success": last_b2.get("success"),
                "message": last_b2.get("message"),
                "execution_id": (
                    (exec_brief(exec_s7_2) or {}).get("execution_id")),
                "status": ((exec_brief(exec_s7_2) or {}).get("status")),
                "delivery": ((exec_brief(exec_s7_2) or {}).get("delivery")
                             or {}),
            },
            "body": body2,
            "audits": audits2,
            "executions": {
                "edit": exec_brief(exec_edit2),
                "reask": exec_brief(exec_reask2),
                "s7": exec_brief(exec_s7_2),
            },
        }

        # Served-log route evidence (pre + restart logs).
        for lh in logs:
            try:
                lh.flush()
            except Exception:
                pass
        log_text = (server_log_path.read_text(errors="replace")
                    + "\n"
                    + server_log2_path.read_text(errors="replace"))
        # Capture the live-store fingerprint/holders while the restart
        # process is still alive, before the log-derived isolation flag.
        capture_after_guards()
        dispatch_models = sorted(set(re.findall(
            r"\[structured-dispatch\] ([^\s]+)", log_text)))
        deepseek_posts = log_text.count(
            "POST https://api.deepseek.com/v1/chat/completions")
        reply_routes = sorted(set(re.findall(
            r"reply STREAMED:.*?\(([^,]+), \d+ chunks\)", log_text)))
        interpretation_lines = [
            ln[:240] for ln in log_text.splitlines()
            if "route=turn_interpretation:" in ln]
        edit_plan_lines = [
            ln[:240] for ln in log_text.splitlines()
            if ("edit plan" in ln.lower() or "edit_plan" in ln.lower())][-12:]
        source_ask_lines = [
            ln[:240] for ln in log_text.splitlines()
            if ("source-ask" in ln.lower()
                or "tool planner" in ln.lower())][-12:]
        provider_posts = sorted(set(re.findall(
            r"POST (https?://[^\s]+)", log_text)))
        _allowed_posts = ("https://api.deepseek.com/v1",
                          "http://localhost:11434/v1",
                          "http://127.0.0.1:11434/v1")
        unexpected_posts = [
            url for url in provider_posts
            if not url.startswith(_allowed_posts)]
        result["provider_routes"] = {
            "structured_dispatch_models": dispatch_models,
            "deepseek_chat_posts": deepseek_posts,
            "reply_streamed_routes": reply_routes,
            "provider_posts": provider_posts,
            "unexpected_provider_posts": unexpected_posts,
            "interpretation_lines": interpretation_lines,
            "edit_plan_lines": edit_plan_lines,
            "source_ask_lines": source_ask_lines,
        }
        live_path_in_logs = str(LIVE_DB) in log_text
        guard_after = result.get("live_db_guard_after") or {}
        guard_after["live_db_path_in_server_logs"] = live_path_in_logs
        guard_after["isolated"] = bool(
            guard_after.get("isolated") and not live_path_in_logs)
        result["live_db_guard_after"] = guard_after

        # ---- stage readings ------------------------------------------------
        l3_task = task_of(l3)
        l3_eid = eid_of(l3)
        l3_rec = (l3.get("execution") or {}).get("row")
        l3_rows = [r for r in (l3.get("persisted_rows") or [])
                   if r.get("role") == "assistant"]
        l3_last = l3_rows[-1] if l3_rows else {}
        l3_msg = msg_of(l3)
        l3_initial = l3.get("initial_response") or {}
        l3_tools = [t for t in (l3_task.get("tool_outcomes") or [])
                    if isinstance(t, dict)]
        l3_docs = [t for t in l3_tools
                   if str(t.get("tool") or "").startswith("documents")]
        l3_complete_refs = [
            r for t in l3_docs for r in (t.get("evidence_refs") or [])
            if isinstance(r, dict) and r.get("coverage") == "complete"
            and isinstance(r.get("match_count"), int)
            and not isinstance(r.get("match_count"), bool)
            and r.get("match_count") >= 1]
        l3_exact = bool(
            l3_eid and l3_rec
            and str(((l3_rec.get("task_outcome") or {}).get(
                "execution_id")) or "") == l3_eid)
        l3_workspace_ok = bool(
            workspace_id
            and str(l3_task.get("workspace_id") or "") == workspace_id)
        l3_interp = ((l3.get("observation") or {}).get(
            "interpretation") or {}).get("interpretation") or {}
        l3_origin = str(l3_interp.get("origin") or "")
        l3_answer_ok = l3_answer_contract(l3_msg)
        l3_settled = bool(
            (l3.get("settlement") or {}).get("final_outcome")
            == "completed"
            and (l3.get("settlement") or {}).get("final_success") is True
            and l3_task.get("objective_met") is True
            and (l3_task.get("delivery") or {}).get("delivered") is True)
        l3_agreement = agreement(
            l3_initial, l3.get("settlement") or {},
            (l3.get("fresh_history") or {}).get(
                "assistant_response") or {},
            l3_last, l3_eid, l3_rec)

        edit_task = task_of(edit)
        edit_mutation = edit_task.get("mutation") or {}
        edit_body = edit.get("canvas_after") or ""
        edit_terms30 = bool(re.search(
            r"(?im)^\s*terms:\s*net\s*30\s*$", edit_body))
        edit_terms45 = bool(re.search(
            r"(?im)^\s*terms:\s*net\s*45\s*$", edit_body))
        edit_applied = edit_terms30 and not edit_terms45
        edit_delta = (len(edit.get("audit_after") or [])
                      - len(edit.get("audit_before") or []))
        edit_ce = canvas_edit_payload(edit)
        # A synchronous canvas edit has a NULL top-level task outcome in the
        # served response. Its settlement is the served canvas_edit receipt
        # (completed / postcondition verified / updated) backed by the
        # durable execution row (objective met, readback matched) and the
        # body+audit delta. The top-level outcome stays nullable.
        edit_settled = bool(
            (edit.get("initial_response") or {}).get("success") is True
            and edit_ce.get("outcome") == "completed"
            and edit_ce.get("postcondition_verified") is True
            and edit_ce.get("updated") is True
            and edit_task.get("objective_met") is True
            and edit_mutation.get("readback_matched") is True)
        edit_preserved = all(x in edit_body for x in (
            "Dunmore Fabrication LLC", "$48,000.00", "2026-12-31",
            "CNC press brake"))

        reask_ce = canvas_edit_payload(reask)
        reask_noop = bool(
            reask_ce.get("noop") is True
            and reask_ce.get("noop_reason") == "already_satisfied"
            and reask_ce.get("updated") is False
            and reask_ce.get("no_apply") is True)
        reask_zero = (reask.get("audit_after")
                      == edit.get("audit_after"))
        reask_body_ok = (reask.get("canvas_after")
                         == edit.get("canvas_after"))
        reask_initial = reask.get("initial_response") or {}
        reask_completed = bool(
            (reask_initial.get("outcome") == "completed"
             or (reask.get("settlement") or {}).get("final_outcome")
             == "completed")
            and (reask_initial.get("success") is True
                 or (reask.get("settlement") or {}).get(
                     "final_success") is True))
        reask_msg = msg_of(reask)
        reask_initial_msg = initial_msg_of(reask)
        reask_reply = bool(
            ("Verified on the current draft" in reask_msg
             or "Verified on the current draft" in reask_initial_msg)
            and ("nothing was sent" in reask_msg
                 or "nothing was sent" in reask_initial_msg))
        reask_agreement = simple_agreement(reask)

        s3_cf = cf_of(s3)
        s3_task = task_of(s3)
        s3_fb = s3.get("fallback_state") or {}
        s3_msg = msg_of(s3)
        s3_low = s3_msg.casefold()
        s3_apply = ((s3.get("observation") or {}).get("apply") or {})
        s3_req = s3.get("requirement_summary") or {}
        s3_eid = eid_of(s3)
        s3_rec = (s3.get("execution") or {}).get("row")
        s3_rows = [r for r in (s3.get("persisted_rows") or [])
                   if r.get("role") == "assistant"]
        s3_last = s3_rows[-1] if s3_rows else {}
        s3_interp = ((s3.get("observation") or {}).get(
            "interpretation") or {}).get("interpretation") or {}
        s3_origin = str(s3_interp.get("origin") or "")
        s3_truthful = bool(
            date_ok(s3_msg)
            and not wrong_date(s3_msg)
            and not re.search(
                r"valid.?until.{0,90}(does not match|doesn.t match|"
                r"differs|mismatch|not match)", s3_low)
            and not any(x in s3_low for x in GLOBAL_CLAIMS))
        s3_no_false = not wrong_date(s3_msg)
        s3_no_global = not any(x in s3_low for x in GLOBAL_CLAIMS)
        s3_broader = bool(
            s3_req.get("broader_comparison") is True
            and s3_cf.get("state") == "partial"
            and (s3_cf.get("missing_comparison")
                 or (s3_cf.get("missing_fields") or []))
            and (("broader comparison" in s3_low and "open" in s3_low)
                 or "not compared" in s3_low
                 or "unassessed" in s3_low))
        s3_zero = s3.get("audit_after") == reask.get("audit_after")
        s3_body_ok = (s3.get("canvas_after")
                      == reask.get("canvas_after"))
        s3_settle = settlement_ok(
            s3.get("settlement") or {}, s3_cf, s3_task, s3_fb)
        s3_req_ok = bool(
            s3_req.get("required") is True
            and "document" in [str(s).lower()
                               for s in (s3_req.get("sources") or [])]
            and s3_req.get("artifact_attached") is True
            and s3_req.get("broader_comparison") is True
            and s3_eid
            and str((s3.get("requirement_event") or {}).get(
                "execution_id") or "") == s3_eid
            and (s3.get("requirement_event") or {}).get(
                "bound_to_execution_key") is True)
        s3_interp_deepseek = bool(
            s3_origin.startswith("llm:")
            and "deepseek" in s3_origin.casefold())
        s3_agreement = agreement(
            s3.get("initial_response") or {},
            s3.get("settlement") or {},
            (s3.get("fresh_history") or {}).get(
                "assistant_response") or {},
            s3_last, s3_eid, s3_rec)

        s7_cf = cf_of(s7)
        s7_task = task_of(s7)
        s7_fb = s7.get("fallback_state") or {}
        s7_msg = msg_of(s7)
        s7_low = s7_msg.casefold()
        s7_apply = ((s7.get("observation") or {}).get("apply") or {})
        s7_req = s7.get("requirement_summary") or {}
        s7_identity = s7_req.get("identity") or {}
        s7_eid = eid_of(s7)
        s7_rec = (s7.get("execution") or {}).get("row")
        s7_rows = [r for r in (s7.get("persisted_rows") or [])
                   if r.get("role") == "assistant"]
        s7_last = s7_rows[-1] if s7_rows else {}
        s7_interp = ((s7.get("observation") or {}).get(
            "interpretation") or {}).get("interpretation") or {}
        s7_origin = str(s7_interp.get("origin") or "")
        s7_after_refs = ((s7_apply.get("decision_refs_after") or {})
                         .get("continuation_evidence") or {})
        s7_observed = s7_apply.get("observed") or []
        s7_truthful = bool(
            date_ok(s7_msg)
            and not wrong_date(s7_msg)
            and not re.search(
                r"valid.?until.{0,90}(does not match|doesn.t match|"
                r"no longer match|differs|mismatch|not match)", s7_low)
            and not base.contains_any(s7_low, (
                "i updated", "i changed", "updated the draft",
                "changed the draft", "modified the draft",
                "set the draft")))
        s7_zero = s7.get("audit_after") == s3.get("audit_after")
        s7_body_ok = (s7.get("canvas_after")
                      == s3.get("canvas_after"))
        s7_antecedent_ids = {
            str(a.get("execution_id") or "")
            for a in (s7_after_refs.get("antecedents") or [])
            if isinstance(a, dict) and a.get("execution_id")}
        # Prefer the structured task record's open questions; None means
        # no record is available and the gate falls back to the exact,
        # fixture-bounded text expectation (disclosed in gate_basis).
        s7_obligations = open_task_obligations(db_file, session_b)
        s7_antecedent_records = {
            eid: base.execution_record(db_file, eid)
            for eid in s7_antecedent_ids}
        s7_completed = bool(
            s7_settlement_ok(
                s7.get("settlement") or {}, s7_cf, s7_task, s7_fb,
                s7_req, s7_obligations,
                expected_prior=(s7_expected_prior or {}).get("items"))
            and s7_cf.get("state") == "completed")
        s7_source_ok = continuation_source_ok(
            s7_after_refs, s7_observed, s7_origin,
            s7_interp.get("scope_change"),
            expected_conversation_id=session_b,
            expected_workspace_id=workspace_id,
            antecedent_records=s7_antecedent_records)
        s7["gate_basis"] = {
            "open_work_source": (
                "structured" if s7_obligations is not None
                else "text_bounded"),
            "expected_prior_source": (
                (s7_expected_prior or {}).get("source")),
            "expected_prior_count": len(
                (s7_expected_prior or {}).get("items") or []),
            "structured_open_count": sum(
                1 for q in (s7_obligations or [])
                if isinstance(q, dict)
                and str(q.get("status") or "open") == "open"),
            "fallback_open_count": len(
                (s7_fb or {}).get("open_work") or []),
            "antecedent_ids": sorted(s7_antecedent_ids),
            "antecedent_records_found": sorted(
                eid for eid, rec in s7_antecedent_records.items()
                if isinstance(rec, dict)),
        }
        s7_actions = bool(
            len(s7_interp.get("actions") or []) > 0
            and all(str((a or {}).get("kind") or "")
                    in ALLOWED_ACTION_KINDS
                    for a in (s7_interp.get("actions") or [])
                    if isinstance(a, dict)))
        s7_interp_deepseek = bool(
            s7_origin.startswith("llm:")
            and "deepseek" in s7_origin.casefold())
        s7_capture = bool(
            stage_summary(s7, log_text).get("capture_archived")
            and "pre_validation" in stage_summary(
                s7, log_text).get("capture_phases", [])
            and "post_validation" in stage_summary(
                s7, log_text).get("capture_phases", []))
        s7_req_ok = bool(
            s7_req.get("required") is True
            and "document" in [str(s).lower()
                               for s in (s7_req.get("sources") or [])]
            and (s7_req.get("file") or {}).get(
                "file_name") == FIXTURE_NAME
            and s7_identity.get("state") == "resolved"
            and bool(s7_identity.get("file_id"))
            and s7_identity.get("file_name") == FIXTURE_NAME
            and s7_req.get("fields") == ["expiration_date"]
            and s7_req.get("broader_comparison") is False
            and s7_req.get("artifact_attached") is True
            and s7_eid
            and str((s7.get("requirement_event") or {}).get(
                "execution_id") or "") == s7_eid
            and (s7.get("requirement_event") or {}).get(
                "bound_to_execution_key") is True)
        s7_settle = s7_settlement_ok(
            s7.get("settlement") or {}, s7_cf, s7_task, s7_fb,
            s7_req, s7_obligations,
            expected_prior=(s7_expected_prior or {}).get("items"))
        s7_agreement = agreement(
            s7.get("initial_response") or {},
            s7.get("settlement") or {},
            (s7.get("fresh_history") or {}).get(
                "assistant_response") or {},
            s7_last, s7_eid, s7_rec)

        # ---- restart readings ---------------------------------------------
        restart_identity_ok = bool(
            restart_identity.get("candidate_cwd_ok")
            and restart_identity.get("candidate_commit_ok")
            and restart_identity.get("dirty") is False)
        pre_a = pre_restart["session_a"]
        pre_b = pre_restart["session_b"]
        post_b = ((result["steps"].get("restart") or {})
                  .get("session_b") or {})
        pre_a_last = pre_a["last_response"] or {}
        pre_b_last = pre_b["last_response"] or {}
        pre_a_persisted = pre_a["last_persisted"] or {}
        pre_b_persisted = pre_b["last_persisted"] or {}
        post_a_persisted = last_assistant(persisted_a2)
        post_b_persisted = last_assistant(persisted_b2)
        restart_execs = ((result["steps"].get("restart") or {})
                         .get("executions") or {})
        exec_edit2 = restart_execs.get("edit") or {}
        exec_reask2 = restart_execs.get("reask") or {}
        exec_s7_2 = restart_execs.get("s7") or {}
        # The served no-op receipt is a turn field (metadata.canvas_edit);
        # the reload agreement is over the receipt-derived reply, success,
        # persisted execution linkage, execution rows and zero-write
        # audits/body. Session B's final continuation carries the explicit
        # non-null completed outcome.
        restart_hist_ok = bool(
            history_a2.get("assistant_count")
            == pre_a["assistant_count"]
            and history_b2.get("assistant_count")
            == pre_b["assistant_count"]
            and last_a2.get("message") == pre_a_last.get("message")
            and last_a2.get("success") is pre_a_last.get("success")
            and last_b2.get("message") == pre_b_last.get("message")
            and last_b2.get("outcome") == pre_b_last.get("outcome")
            and last_b2.get("success") is pre_b_last.get("success")
            and restart_agreement_ok(
                {**pre_b, "s7_gate_ok": s7_settle},
                {**post_b, "s7_gate_ok": s7_settle})
            and post_a_persisted.get("meta_execution_id")
            == pre_a_persisted.get("meta_execution_id")
            == pre_a["execution_id"]
            and post_a_persisted.get("content")
            == pre_a_persisted.get("content")
            and post_a_persisted.get("meta_success")
            == pre_a_persisted.get("meta_success")
            and post_a_persisted.get("meta_outcome")
            == pre_a_persisted.get("meta_outcome")
            and post_b_persisted.get("meta_execution_id")
            == pre_b_persisted.get("meta_execution_id")
            and post_b_persisted.get("content")
            == pre_b_persisted.get("content")
            and post_b_persisted.get("meta_success")
            == pre_b_persisted.get("meta_success")
            and post_b_persisted.get("meta_outcome")
            == pre_b_persisted.get("meta_outcome"))
        restart_zero = bool(
            audits2 == pre_restart["audits"]
            and sum(1 for r in persisted_a2
                    if r.get("role") == "assistant")
            == pre_a["assistant_rows"]
            and sum(1 for r in persisted_b2
                    if r.get("role") == "assistant")
            == pre_b["assistant_rows"])
        restart_canvas_ok = body2 == pre_restart["body"]
        restart_exec_ok = restart_execution_ok(
            exec_edit2, exec_reask2, exec_s7_2,
            pre_a["execution_id"])

        l3_summary = stage_summary(l3, log_text)
        edit_summary = stage_summary(edit, log_text)
        reask_summary = stage_summary(reask, log_text)
        s3_summary = stage_summary(s3, log_text)
        s7_summary = stage_summary(s7, log_text)

        _reply_providers = [
            (l3.get("initial_response") or {}).get("provider"),
            (s3.get("initial_response") or {}).get("provider"),
            (s7.get("initial_response") or {}).get("provider"),
        ]
        _reply_streams = list(reply_routes or [])
        # DECLARED FALLBACK PROFILE (2026-10-24): local Ollama is preferred;
        # if it emits no tokens, DeepSeek is the declared supported fallback.
        # Any other provider is a parity failure. Actual routes are recorded.
        _allowed_providers = {"ollama", "deepseek"}
        _allowed_prefixes = ("ollama/", "deepseek/")
        _reply_parity = bool(
            all(str(p or "").casefold() in _allowed_providers
                for p in _reply_providers)
            and _reply_streams
            and all(str(r).casefold().startswith(_allowed_prefixes)
                    for r in _reply_streams))
        result["reply_actual_routes"] = {
            "l3": _reply_providers[0], "s3": _reply_providers[1],
            "s7": _reply_providers[2], "streams": _reply_streams,
            "declared": "ollama preferred; deepseek fallback",
        }

        checks = {
            "runtime_identity": bool(
                result["steps"]["runtime_identity"]["candidate_cwd_ok"]
                and result["steps"]["runtime_identity"][
                    "candidate_commit_ok"]
                and result["steps"]["runtime_identity"]["dirty"]
                is False),
            "auth_user_resolved": bool(uid),
            "deepseek_credential_active": credential_active,
            "fixture_uploaded_through_product": upload_ok,
            "l3_http_ok": l3.get("http") == 200,
            "l3_answer_correct": l3_answer_ok,
            "l3_documents_receipt_executed": bool(
                any(t.get("verified") is True for t in l3_docs)),
            "l3_receipt_verified_complete": bool(l3_complete_refs),
            "l3_receipt_bound_to_execution": l3_exact,
            "l3_receipt_bound_to_workspace": l3_workspace_ok,
            "l3_objective_met": l3_task.get("objective_met") is True,
            "l3_settlement_completed": l3_settled,
            "l3_no_canvas_created": (
                canvas_count_after_l3 == canvas_count_before_l3),
            "l3_interpretation_deepseek": bool(
                (l3_origin.startswith("llm:")
                 and "deepseek" in l3_origin.casefold())
                or any(m.startswith("deepseek/")
                       for m in l3_summary.get("dispatch_models", []))),
            "l3_history_agreement": l3_agreement,
            "draft_created_through_product": seed_ok,
            "edit_http_ok": edit.get("http") == 200,
            "edit_body_applied": edit_applied,
            "edit_audit_exactly_one": edit_delta == 1,
            "edit_settled_completed": edit_settled,
            "edit_other_fields_preserved": edit_preserved,
            "reask_http_ok": reask.get("http") == 200,
            "reask_noop_receipt": reask_noop,
            "reask_zero_additional_writes": reask_zero,
            "reask_body_unchanged": reask_body_ok,
            "reask_completed": reask_completed,
            "reask_receipt_reply": reask_reply,
            "reask_history_agreement": reask_agreement,
            "comparison_http_ok": s3.get("http") == 200,
            "comparison_truthful_date": s3_truthful,
            "comparison_no_false_date": s3_no_false,
            "comparison_no_global_claim": s3_no_global,
            "comparison_broader_obligation_open": s3_broader,
            "comparison_zero_writes": s3_zero,
            "comparison_draft_unchanged": s3_body_ok,
            "comparison_settlement_basis": s3_settle,
            "comparison_requirement_captured": s3_req_ok,
            "comparison_interpretation_deepseek": s3_interp_deepseek,
            "comparison_history_agreement": s3_agreement,
            "continuation_http_ok": s7.get("http") == 200,
            "continuation_truthful_date": s7_truthful,
            "continuation_zero_writes": s7_zero,
            "continuation_draft_unchanged": s7_body_ok,
            "continuation_date_only_completed": s7_completed,
            "continuation_source_resolved": s7_source_ok,
            "continuation_actions_proposed": s7_actions,
            "continuation_capture_archived": s7_capture,
            "continuation_requirement_captured": s7_req_ok,
            "continuation_settlement_basis": s7_settle,
            "continuation_interpretation_deepseek": s7_interp_deepseek,
            "continuation_history_agreement": s7_agreement,
            "restart_runtime_identity": restart_identity_ok,
            "restart_history_agreement": restart_hist_ok,
            "restart_zero_new_writes": restart_zero,
            "restart_canvas_unchanged": restart_canvas_ok,
            "restart_execution_persists": restart_exec_ok,
            "provider_structured_deepseek": bool(
                dispatch_models
                and any(m.startswith("deepseek/")
                        for m in dispatch_models)),
            "provider_reply_parity": _reply_parity,
            "provider_allowlist_clean": bool(
                provider_posts and not unexpected_posts),
        }

        # Guards, captured before the pass/fail decision.
        capture_after_guards()
        pilot_after = result["pilot_after"]
        pilot_before_ident = (cfg.get("pilot_before") or {}).get(
            "identity") or {}
        pilot_after_ident = pilot_after.get("identity") or {}
        result["pilot_untouched"] = bool(
            pilot_before_ident.get("instance_id")
            == pilot_after_ident.get("instance_id")
            and pilot_before_ident.get("pid")
            == pilot_after_ident.get("pid")
            and pilot_before_ident.get("started_at")
            == pilot_after_ident.get("started_at")
            and pilot_after.get("backend_8001_listening")
            and pilot_after.get("frontend_3000_listening"))
        # The live-DB file is owned by the pilot; its own checkpoint/
        # maintenance can change the content fingerprint. Isolation is
        # proven by store access (the scratch process tree holds no live
        # DB/WAL/SHM handle and every configured path is under SCRATCH),
        # not by an unattributable mtime/hash change.
        checks["live_db_isolated"] = bool(
            (result.get("live_db_guard_after") or {}).get("isolated"))
        checks["pilot_untouched"] = result["pilot_untouched"]

        result["stage_summary"] = {
            "l3_sourced_answer": {
                "request_id": l3.get("request_id"),
                "outcome": (l3.get("settlement") or {}).get(
                    "final_outcome"),
                "success": (l3.get("settlement") or {}).get(
                    "final_success"),
                "message": l3_msg[:500],
                "expected_code": L3_EXPECTED_CODE,
                "decoy_present": L3_DECOY_CODE in l3_msg,
                "documents_receipts": [
                    {"tool": t.get("tool"),
                     "verified": t.get("verified"),
                     "refs": [{"coverage": r.get("coverage"),
                               "match_count": r.get("match_count")}
                              for r in (t.get("evidence_refs") or [])
                              if isinstance(r, dict)]}
                    for t in l3_docs],
                "planning_timeout_seen": (
                    "tool planning skipped: TimeoutError()" in log_text),
                "old_plan_none_seen": (
                    "tool plan executed: None" in log_text),
                "required_read_after_timeout": bool(
                    l3_docs and "tool planning skipped: TimeoutError()"
                    in log_text),
                "route": l3_summary,
            },
            "edit": {
                "request_id": edit.get("request_id"),
                "outcome": (edit.get("settlement") or {}).get(
                    "final_outcome"),
                "success": (edit.get("settlement") or {}).get(
                    "final_success"),
                "audit_delta": edit_delta,
                "canvas_edit": canvas_edit_payload(edit),
                "route": edit_summary,
            },
            "identical_reask": {
                "request_id": reask.get("request_id"),
                "outcome": (reask.get("settlement") or {}).get(
                    "final_outcome"),
                "success": (reask.get("settlement") or {}).get(
                    "final_success"),
                "canvas_edit": reask_ce,
                "audit_delta": (len(reask.get("audit_after") or [])
                                - len(edit.get("audit_after") or [])),
                "message": reask_msg[:500],
                "route": reask_summary,
            },
            "comparison": {
                "request_id": s3.get("request_id"),
                "outcome": (s3.get("settlement") or {}).get(
                    "final_outcome"),
                "success": (s3.get("settlement") or {}).get(
                    "final_success"),
                "context_fulfillment_state": s3_cf.get("state"),
                "missing_comparison": s3_cf.get("missing_comparison"),
                "missing_fields": s3_cf.get("missing_fields"),
                "broader_comparison_requirement": s3_req.get(
                    "broader_comparison"),
                "message_has_open": (
                    ("broader comparison" in s3_low and "open" in s3_low)
                    or "not compared" in s3_low
                    or "unassessed" in s3_low),
                "message": s3_msg[:900],
                "route": s3_summary,
            },
            "date_only_continuation": {
                "request_id": s7.get("request_id"),
                "outcome": (s7.get("settlement") or {}).get(
                    "final_outcome"),
                "success": (s7.get("settlement") or {}).get(
                    "final_success"),
                "context_fulfillment_state": s7_cf.get("state"),
                "fields": s7_req.get("fields"),
                "broader_comparison": s7_req.get(
                    "broader_comparison"),
                "message": s7_msg[:900],
                "route": s7_summary,
            },
            "restart": {
                "session_a_assistant_count": history_a2.get(
                    "assistant_count"),
                "session_a_pre_count": pre_a["assistant_count"],
                "session_b_assistant_count": history_b2.get(
                    "assistant_count"),
                "session_b_pre_count": pre_b["assistant_count"],
                "session_a_noop": pre_a["canvas_edit"].get("noop"),
                "session_a_noop_reason": pre_a["canvas_edit"].get(
                    "noop_reason"),
                "session_b_outcome": last_b2.get("outcome"),
                "session_b_success": last_b2.get("success"),
                "executions": {
                    "edit": exec_edit2,
                    "reask": exec_reask2,
                    "s7": exec_s7_2,
                },
                "route": restart_identity,
            },
            "total_turn_latency_s": {
                "l3": l3.get("latency_s"),
                "edit": edit.get("latency_s"),
                "reask": reask.get("latency_s"),
                "comparison": s3.get("latency_s"),
                "continuation": s7.get("latency_s"),
            },
        }

        result["checks"] = checks
        result["pass"] = all(checks.values())
        order = [
            ("runtime_identity", "runtime_identity_mismatch"),
            ("auth_user_resolved", "auth_failed"),
            ("deepseek_credential_active",
             "authorized_provider_registration_failed"),
            ("fixture_uploaded_through_product", "upload_failed"),
            ("l3_http_ok", "l3_no_reply"),
            ("l3_answer_correct", "l3_untruthful_answer"),
            ("l3_documents_receipt_executed",
             "l3_documents_receipt_missing"),
            ("l3_receipt_verified_complete",
             "l3_receipt_incomplete"),
            ("l3_receipt_bound_to_execution", "l3_receipt_unbound"),
            ("l3_receipt_bound_to_workspace", "l3_receipt_wrong_workspace"),
            ("l3_objective_met", "l3_objective_not_met"),
            ("l3_settlement_completed", "l3_settlement_invalid"),
            ("l3_no_canvas_created", "l3_created_canvas"),
            ("l3_interpretation_deepseek", "l3_route_not_deepseek"),
            ("l3_history_agreement", "l3_history_disagreement"),
            ("draft_created_through_product", "draft_create_failed"),
            ("edit_http_ok", "edit_no_reply"),
            ("edit_body_applied", "edit_not_applied"),
            ("edit_audit_exactly_one", "edit_write_count_wrong"),
            ("edit_settled_completed", "edit_not_completed"),
            ("edit_other_fields_preserved", "edit_clobbered_fields"),
            ("reask_http_ok", "reask_no_reply"),
            ("reask_noop_receipt", "reask_not_a_noop"),
            ("reask_zero_additional_writes",
             "reask_planner_proposed_redundant_edit"),
            ("reask_body_unchanged", "reask_changed_draft"),
            ("reask_completed", "reask_not_completed"),
            ("reask_receipt_reply", "reask_reply_not_receipt_derived"),
            ("reask_history_agreement", "reask_history_disagreement"),
            ("comparison_http_ok", "comparison_no_reply"),
            ("comparison_truthful_date", "comparison_untruthful"),
            ("comparison_no_false_date", "comparison_false_date"),
            ("comparison_no_global_claim",
             "comparison_global_consistency_claim"),
            ("comparison_broader_obligation_open",
             "comparison_broader_not_open"),
            ("comparison_zero_writes", "comparison_canvas_write"),
            ("comparison_draft_unchanged", "comparison_draft_changed"),
            ("comparison_settlement_basis",
             "comparison_settlement_invalid"),
            ("comparison_requirement_captured",
             "comparison_requirement_missing"),
            ("comparison_interpretation_deepseek",
             "comparison_route_not_deepseek"),
            ("comparison_history_agreement",
             "comparison_history_disagreement"),
            ("continuation_http_ok", "continuation_no_reply"),
            ("continuation_truthful_date", "continuation_untruthful"),
            ("continuation_zero_writes", "continuation_canvas_write"),
            ("continuation_draft_unchanged",
             "continuation_draft_changed"),
            ("continuation_date_only_completed",
             "continuation_not_date_only_completed"),
            ("continuation_source_resolved",
             "continuation_source_not_resolved"),
            ("continuation_actions_proposed",
             "continuation_no_actions"),
            ("continuation_capture_archived",
             "continuation_capture_missing"),
            ("continuation_requirement_captured",
             "continuation_requirement_missing"),
            ("continuation_settlement_basis",
             "continuation_settlement_invalid"),
            ("continuation_interpretation_deepseek",
             "continuation_route_not_deepseek"),
            ("continuation_history_agreement",
             "continuation_history_disagreement"),
            ("restart_runtime_identity",
             "restart_runtime_identity_mismatch"),
            ("restart_history_agreement",
             "restart_history_disagreement"),
            ("restart_zero_new_writes", "restart_new_writes"),
            ("restart_canvas_unchanged", "restart_canvas_changed"),
            ("restart_execution_persists",
             "restart_execution_missing"),
            ("provider_structured_deepseek",
             "structured_route_not_deepseek"),
            ("provider_reply_parity", "reply_route_not_parity"),
            ("provider_allowlist_clean", "unexpected_provider_post"),
            ("live_db_isolated", "live_db_isolated_failed"),
            ("pilot_untouched", "pilot_touched"),
        ]
        result["first_failure"] = next(
            (cls for key, cls in order if not checks.get(key)), None)
        result["classification"] = (
            "verified_l1_l2_l3_composed_workflow"
            if result["pass"]
            else (result["first_failure"] or "unclassified_failure"))
        return finish_result()
    finally:
        for p in procs:
            stop_proc(p)
        for lh in logs:
            try:
                lh.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
