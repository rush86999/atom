#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run the workbook incident as a revision-stable closure replay.

The replay sends the original two-turn conversation, reads the persisted
pending-file state and trace, and evaluates the final reply against the
workbook evidence contract. It exits nonzero unless every closure condition
passes on one unchanged serving revision.
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast

import httpx


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BASE_DEFAULT = "http://127.0.0.1:8001"
TARGETS = (
    "381", "U-22", "622", "SLE24-16", "GSL48-16", "GSL24-16", "SLE16-8", "U-38",
)
FILE_NAME = "Consolidated Price List 2019.xlsx"
ORIGINAL_ASK = (
    "find the prices of these 8 machines in Consolidated Price List "
    "2019.xlsx: 381, U-22, 622, SLE24-16, GSL48-16, GSL24-16, SLE16-8 "
    "and U-38"
)
CONFIRMATION = "That filename is correct"
RETRY_CONFIRMATION = "go"


def mint_token() -> Tuple[Optional[str], Optional[str]]:
    try:
        from dotenv import load_dotenv

        for filename in (
            os.path.join(PROJECT_ROOT, ".env"),
            os.path.join(PROJECT_ROOT, ".env.local"),
        ):
            if os.path.exists(filename):
                load_dotenv(filename, override=filename.endswith(".env.local"))
    except Exception:
        pass

    from core.auth import create_access_token
    from core.database import get_db_session
    from core.models import User

    with get_db_session() as db:
        user = db.query(User).filter(User.email == "admin@example.com").first()
        if user is None:
            return None, None
        user_id, email = str(user.id), user.email
        role = getattr(user, "role", None)
        role = getattr(role, "value", role)
    return create_access_token({
        "sub": user_id,
        "user_id": user_id,
        "email": email,
        "role": str(role or "workspace_admin"),
    }), user_id


async def turn(
    client: httpx.AsyncClient,
    base: str,
    token: str,
    user_id: str,
    session_id: str,
    message: str,
) -> Dict[str, Any]:
    response = await client.post(
        f"{base}/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "session_id": session_id, "user_id": user_id},
        timeout=240,
    )
    response.raise_for_status()
    return cast(Dict[str, Any], response.json())


async def trace(
    client: httpx.AsyncClient,
    base: str,
    token: str,
    session_id: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    response = await client.get(
        f"{base}/api/chat/trace/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if response.status_code != 200:
        return [], {
            "status_code": response.status_code,
            "error": response.text[:500],
        }
    return flatten_trace(response.json()), {"status_code": 200, "error": ""}


def flatten_trace(payload: Any) -> List[Dict[str, Any]]:
    """Flatten the chat trace API's runs[].steps and older flat responses."""
    if isinstance(payload, list):
        list_result: List[Dict[str, Any]] = []
        for item in payload:
            list_result.extend(flatten_trace(item))
        return list_result
    if not isinstance(payload, dict):
        return []

    if isinstance(payload.get("step_type"), str) or "observation" in payload:
        return [payload]

    result: List[Dict[str, Any]] = []
    runs = payload.get("runs")
    if isinstance(runs, list):
        for run in runs:
            result.extend(flatten_trace(run))
    if "steps" in payload:
        result.extend(flatten_trace(payload.get("steps")))
    for key in ("trace", "data", "result"):
        if key in payload and payload[key] is not payload:
            result.extend(flatten_trace(payload[key]))
    if not result and any(key in payload for key in ("step_type", "observation", "action")):
        result.append(payload)
    return result


def summarize_step(step: Dict[str, Any]) -> str:
    kind = step.get("step_type") or step.get("type") or "?"
    action = step.get("action") or {}
    if isinstance(action, dict):
        tool = action.get("tool") or "?"
        params = action.get("params") or {}
    else:
        tool = str(action or "?")
        params = {}
    observation = str(step.get("observation") or "")[:220].replace("\n", " ")
    return f"[{kind}] {tool} {json.dumps(params, default=str)[:140]} :: {observation}"


def pending_state(session_id: str) -> Dict[str, Any]:
    """Read the durable assistant-row task marker without writing the DB."""
    try:
        from core.database import get_db_session
        from core.models import ChatMessage

        with get_db_session() as db:
            rows = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.conversation_id == session_id,
                    ChatMessage.role == "assistant",
                )
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .limit(24)
                .all()
            )
        for row in rows:
            raw = getattr(row, "metadata_json", None)
            if isinstance(raw, str):
                try:
                    metadata = json.loads(raw or "{}")
                except json.JSONDecodeError:
                    metadata = {}
            elif isinstance(raw, dict):
                metadata = raw
            else:
                metadata = {}
            task = metadata.get("pending_file_task") or metadata.get("_pending_file_task")
            result = metadata.get("pending_file_result") or metadata.get("_pending_file_result")
            if isinstance(task, dict):
                return {
                    "status": task.get("status"),
                    "result_status": result.get("status") if isinstance(result, dict) else None,
                    "task": task,
                    "result": result,
                    "read_error": "",
                }
        return {
            "status": None,
            "result_status": None,
            "task": None,
            "result": None,
            "read_error": "",
        }
    except Exception as exc:
        return {
            "status": None,
            "result_status": None,
            "task": None,
            "result": None,
            "read_error": f"{type(exc).__name__}: {exc}",
        }


def wait_for_delivery(session_id: str, timeout: float = 3.0) -> Dict[str, Any]:
    deadline = time.monotonic() + max(0.0, timeout)
    state = pending_state(session_id)
    while (
        time.monotonic() < deadline
        and state.get("result_status") not in ("delivered", "served")
        and state.get("status") not in ("delivered", "served")
    ):
        time.sleep(0.1)
        state = pending_state(session_id)
    return state


def identity_from_health(payload: Dict[str, Any]) -> Dict[str, Any]:
    identity = payload.get("identity") if isinstance(payload, dict) else {}
    return identity if isinstance(identity, dict) else {}


def same_revision(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    keys = ("instance_id", "source_id", "revision", "started_at", "pid")
    return all(before.get(key) == after.get(key) for key in keys)


def clean_cell(value: str) -> str:
    return re.sub(r"[`*_]", "", str(value or "")).strip()


def parse_outcomes(reply: str) -> List[Dict[str, str]]:
    target_map = {target.lower(): target for target in TARGETS}
    outcomes: List[Dict[str, str]] = []
    for line in str(reply or "").splitlines():
        if "|" not in line:
            continue
        cells = [clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        target = target_map.get(cells[0].lower())
        if target is None:
            continue
        outcomes.append({
            "target": target,
            "status": cells[1],
            "evidence": cells[2],
        })
    return outcomes


def trace_text(steps: Iterable[Dict[str, Any]]) -> str:
    return json.dumps(list(steps), ensure_ascii=False, default=str).lower()


def _is_missing_status(status: str) -> bool:
    upper = str(status or "").upper()
    return any(token in upper for token in ("ABSENT", "NOT FOUND", "INCOMPLETE"))


def evaluate(
    identity_before: Dict[str, Any],
    identity_after: Dict[str, Any],
    r1: Dict[str, Any],
    r2: Dict[str, Any],
    steps: List[Dict[str, Any]],
    trace_meta: Dict[str, Any],
    state_after_1: Dict[str, Any],
    state_after_2: Dict[str, Any],
    expected_revision: str = "",
    outage_mode: bool = False,
) -> Dict[str, Any]:
    reply = str(r2.get("message") or "")
    lower = reply.lower()
    rows = parse_outcomes(reply)
    by_target = {row["target"]: row for row in rows}
    trace_blob = trace_text(steps)
    workbook_name = FILE_NAME.lower()
    source_refs = bool(
        re.search(r"resource[=_ ]", lower)
        and re.search(r"content[ _-]?hash[=_ ]", lower)
        and re.search(r"ingest(?:ed|ion)?[=_ ]", lower)
    )
    foreign_files = [
        name for name in re.findall(r"[^\n|]*\.xlsx", reply, re.IGNORECASE)
        if workbook_name not in name.lower()
    ]
    found_rows = [row for row in rows if not _is_missing_status(row["status"])]
    missing_rows = [row for row in rows if _is_missing_status(row["status"])]
    protocol_tokens = (
        "live tool results", "file_search", "pending file task",
        "workbook read artifact", "sql result", "reproduce verbatim",
        "<tool_call", "</tool_call", "tool_call", "recalculate",
    )
    arithmetic_tokens = (
        "i calculated", "i computed", "interpolat", "recalculate",
        "re-derive", "multiply by", "divided by", "×", "÷",
    )
    direct_delivery = bool(
        (r2.get("data") or {}).get("deterministic_delivery")
        or r2.get("model") in ("deterministic", "structured")
    )
    checks = {
        "revision_stable": same_revision(identity_before, identity_after),
        "expected_revision": not expected_revision or identity_after.get("revision") == expected_revision,
        "turn1_success": bool(r1.get("success")) or (
            outage_mode and state_after_1.get("status") == "pending"
        ),
        "turn2_success": bool(r2.get("success")) or (
            outage_mode and direct_delivery
        ),
        "pending_after_turn1": state_after_1.get("status") == "pending",
        "pending_served_after_turn2": state_after_2.get("status") in (
            "retrieved", "served", "delivered",
        ),
        "delivery_state_accounted_for": (
            state_after_2.get("result_status") in ("retrieved", "delivered")
            or state_after_2.get("status") in ("retrieved", "served", "delivered")
        ),
        "pending_state_readable": not state_after_1.get("read_error") and not state_after_2.get("read_error"),
        "trace_original_ask": direct_delivery or (
            workbook_name in trace_blob and any(
                target.lower() in trace_blob for target in TARGETS
            )
        ),
        "trace_storage_or_datasets": direct_delivery or any(
            token in trace_blob for token in ("datasets", "storage", "workdrive")
        ),
        "trace_readable": trace_meta.get("status_code") == 200,
        "direct_structured_delivery": direct_delivery,
        "eight_structured_outcomes": len(rows) == len(TARGETS) and set(by_target) == set(TARGETS),
        "found_outcomes": len(found_rows) >= 1,
        "missing_outcomes": len(missing_rows) == 3,
        "sheet_cell_lineage": all(
            re.search(r"(?:!\$?[A-Z]{1,3}\$?\d+|\bR\d{1,6}\b)", row["evidence"], re.IGNORECASE)
            for row in found_rows
        ),
        "coverage_present": "coverage" in lower and "indexed content" in lower,
        "misses_are_scoped": all(
            "indexed content" in row["evidence"].lower() or "indexed content" in lower
            for row in missing_rows
        ),
        "provenance_present": source_refs and "materialized copy" in lower,
        "named_file_only": not foreign_files and workbook_name in lower,
        "no_protocol_leakage": not any(token in lower for token in protocol_tokens),
        "no_model_arithmetic": not any(token in lower for token in arithmetic_tokens),
        "no_absolute_absence": not any(
            phrase in lower for phrase in (
                "absent from the workbook", "does not exist in the workbook",
                "the workbook does not contain", "not present in the workbook",
            )
        ),
    }
    return {
        "checks": checks,
        "all_pass": all(checks.values()),
        "outcomes": rows,
        "foreign_files": foreign_files,
        "reply_length": len(reply),
        "trace_steps": len(steps),
        "trace_meta": trace_meta,
        "pending_after_turn1": state_after_1,
        "pending_after_turn2": state_after_2,
    }


def evaluate_retry(
    state_after_2: Dict[str, Any],
    state_after_3: Dict[str, Any],
    r3: Dict[str, Any],
) -> Dict[str, Any]:
    before = state_after_2.get("result") or {}
    after = state_after_3.get("result") or {}
    before_identity = before.get("identity") or {}
    after_identity = after.get("identity") or {}
    before_workbook = before.get("workbook_read") or before_identity.get(
        "workbook_read"
    )
    after_workbook = after.get("workbook_read") or after_identity.get(
        "workbook_read"
    )
    data = r3.get("data") or {}
    deterministic = bool(
        data.get("deterministic_delivery")
        or r3.get("model") in ("deterministic", "structured")
    )
    checks = {
        "successful": bool(r3.get("success")),
        "deterministic_delivery": deterministic,
        "eight_structured_outcomes": (
            len(parse_outcomes(str(r3.get("message") or ""))) == len(TARGETS)
        ),
        "state_delivered": (
            state_after_3.get("status") == "delivered"
            and state_after_3.get("result_status") == "delivered"
        ),
        "no_reread": bool(
            before_identity
            and before_identity == after_identity
            and before.get("execution_id") == after.get("execution_id")
            and before.get("retrieved_at") == after.get("retrieved_at")
            and (
                not before_workbook
                or before_workbook == after_workbook
            )
        ),
    }
    return {"checks": checks, "all_pass": all(checks.values())}


def build_report(
    identity_before: Dict[str, Any],
    identity_after: Dict[str, Any],
    r1: Dict[str, Any],
    r2: Dict[str, Any],
    steps: List[Dict[str, Any]],
    trace_meta: Dict[str, Any],
    state_after_1: Dict[str, Any],
    state_after_2: Dict[str, Any],
    expected_revision: str,
    outage_mode: bool = False,
) -> Dict[str, Any]:
    report = evaluate(
        identity_before, identity_after, r1, r2, steps, trace_meta,
        state_after_1, state_after_2, expected_revision, outage_mode,
    )
    report["outage_mode"] = outage_mode
    report["identity_before"] = identity_before
    report["identity_after"] = identity_after
    report["turn1"] = {
        "success": r1.get("success"),
        "model": r1.get("model"),
        "provider": r1.get("provider"),
        "message": str(r1.get("message") or "")[:2000],
    }
    report["turn2"] = {
        "success": r2.get("success"),
        "model": r2.get("model"),
        "provider": r2.get("provider"),
        "message": str(r2.get("message") or "")[:4000],
    }
    report["trace_summary"] = [summarize_step(step) for step in steps[-30:]]
    return report


async def main_async(args: argparse.Namespace) -> int:
    token, user_id = mint_token()
    if not token or not user_id:
        print("FATAL: could not mint token (admin@example.com missing)", file=sys.stderr)
        return 2

    base = args.base.rstrip("/")
    session_id = f"wb-replay-{int(time.time())}"
    report: Dict[str, Any]
    async with httpx.AsyncClient() as client:
        try:
            health_before = (await client.get(f"{base}/api/health", timeout=10)).json()
            identity_before = identity_from_health(health_before)
            print(f"serving instance: {identity_before.get('instance_id') or identity_before.get('source_id')}")
            print(f"revision: {identity_before.get('revision') or 'unknown'}")
            print(f"scratch session: {session_id}\n")

            print("=== TURN 1 — the original ask ===")
            started = time.monotonic()
            r1 = await turn(client, base, token, user_id, session_id, ORIGINAL_ASK)
            print(
                f"({time.monotonic() - started:.1f}s) "
                f"success={r1.get('success')} "
                f"model={r1.get('model')}/{r1.get('provider')}"
            )
            sid = r1.get("session_id") or session_id
            state_after_1 = pending_state(sid)

            print("\n=== TURN 2 — the confirmation ===")
            started = time.monotonic()
            r2 = await turn(client, base, token, user_id, sid, CONFIRMATION)
            print(
                f"({time.monotonic() - started:.1f}s) "
                f"success={r2.get('success')} "
                f"model={r2.get('model')}/{r2.get('provider')}"
            )
            state_after_2 = pending_state(sid)

            print("\n=== TURN 3 — persisted delivery retry ===")
            started = time.monotonic()
            r3 = await turn(
                client, base, token, user_id, sid, RETRY_CONFIRMATION
            )
            print(
                f"({time.monotonic() - started:.1f}s) "
                f"success={r3.get('success')} "
                f"model={r3.get('model')}/{r3.get('provider')}"
            )
            state_after_3 = wait_for_delivery(sid)

            steps, trace_meta = await trace(client, base, token, sid)
            health_after = (await client.get(f"{base}/api/health", timeout=10)).json()
            identity_after = identity_from_health(health_after)
            report = build_report(
                identity_before,
                identity_after,
                r1,
                r2,
                steps,
                trace_meta,
                state_after_1,
                state_after_2,
                args.expected_revision,
                args.outage_mode,
            )
            retry_report = evaluate_retry(state_after_2, state_after_3, r3)
            report["retry"] = {
                "success": r3.get("success"),
                "model": r3.get("model"),
                "provider": r3.get("provider"),
                "message": str(r3.get("message") or "")[:2000],
                "state": state_after_3,
                **retry_report,
            }
            report["checks"].update({
                f"retry_{key}": value
                for key, value in retry_report["checks"].items()
            })
            report["all_pass"] = all(report["checks"].values())
        except Exception as exc:
            report = {
                "all_pass": False,
                "error": f"{type(exc).__name__}: {exc}",
                "identity_before": {},
                "identity_after": {},
            }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False, default=str)
    print("\n=== CLOSURE REPORT ===")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("all_pass") else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE_DEFAULT)
    parser.add_argument("--expected-revision", default="")
    parser.add_argument(
        "--outage-mode",
        action="store_true",
        help="accept a deliberately unavailable first-turn narration path",
    )
    parser.add_argument("--output", default="")
    return asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
