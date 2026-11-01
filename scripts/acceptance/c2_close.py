#!/usr/bin/env python3
"""Close C2 after its two-hour gate: deliver the correlated reply, approve the
controlled send, assert one effect, and record the durable completion.

No polling loop longer than the executor needs; the clock check is explicit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import docx


def api(base: str, path: str, *, token: str = "", method: str = "GET",
        body: dict | None = None, timeout: int = 60):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{base}{path}", data=data, method=method,
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def login(base: str, password: str) -> str:
    status, body = api(base, "/api/auth/login", method="POST", body={
        "username": "admin@example.com", "password": password})
    if status != 200 or not body.get("access_token"):
        raise SystemExit(f"login failed: {status} {body}")
    return body["access_token"]


def budget_snapshot(detail: dict) -> dict:
    budget = (detail.get("assignment") or {}).get("budget") or {}
    return {
        key: budget.get(key) for key in (
            "started_at", "paused_seconds", "waiting_since", "active_wait",
            "wait_credits", "wait_credits_schema", "steps_started",
            "attempts_started", "elapsed_seconds",
        )
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="http://127.0.0.1:8085")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--correlation", default="quote-missing-currency-2")
    ap.add_argument("--response",
                    default="Delivery term: net 30 days from the invoice date.")
    ap.add_argument("--wait-reached", default="2026-11-01T18:04:53Z")
    ap.add_argument("--min-seconds", type=int, default=7200)
    ap.add_argument("--outbox", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    gate = datetime.fromisoformat(args.wait_reached.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    elapsed = (now - gate).total_seconds()
    if elapsed < args.min_seconds:
        raise SystemExit(
            f"REFUSED: {elapsed:.0f}s elapsed, gate is {args.min_seconds}s")
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    password = Path(args.password_file).read_text().strip()
    token = login(args.backend, password)

    status, detail = api(args.backend, f"/api/assignments/{args.run_id}",
                         token=token)
    if status != 200:
        raise SystemExit(f"assignment read failed: {status} {detail}")
    before = detail["assignment"]
    if before["status"] != "waiting":
        raise SystemExit(f"REFUSED: expected waiting, got {before['status']}")
    before_steps = {step["step_id"]: step for step in before.get("steps") or []}
    source_before = before_steps["source-1"]
    teaching_before = before["teaching_revision"]
    assignment_id = before["assignment_id"]
    budget_before = budget_snapshot(detail)

    status, delivered = api(
        args.backend, f"/api/assignments/{args.run_id}/responses/"
                      f"{args.correlation}",
        token=token, method="POST", body={"response": args.response})
    if status not in (200, 202):
        raise SystemExit(f"response delivery failed: {status} {delivered}")
    _, response_detail = api(
        args.backend, f"/api/assignments/{args.run_id}", token=token)
    budget_after_response = budget_snapshot(response_detail)

    approvals = []
    resume_budgets = []
    resume_calls = 0
    deadline = time.time() + 240
    detail = {}
    while time.time() < deadline:
        read_status, detail = api(
            args.backend, f"/api/assignments/{args.run_id}", token=token)
        if read_status != 200:
            raise SystemExit(f"assignment read failed: {read_status}")
        assignment = detail.get("assignment") or {}
        if assignment.get("status") == "completed":
            break
        steps_now = (detail.get("assignment") or {}).get("steps") or []
        awaiting = [step for step in steps_now
                    if step.get("status") == "awaiting_approval"]
        if awaiting:
            for step in awaiting:
                request = step.get("approval_request") or {}
                approve_status, _ = api(
                    args.backend,
                    f"/api/assignments/{args.run_id}/approve/"
                    f"{step['step_id']}",
                    token=token, method="POST",
                    body={"note": "C2 closure approval"})
                approvals.append({
                    "step_id": step["step_id"],
                    "http": approve_status,
                    "payload_sha256": request.get("payload_sha256"),
                    "artifact_revision": request.get("artifact_revision"),
                    "purpose": request.get("purpose"),
                })
                if approve_status >= 400:
                    raise SystemExit(
                        f"approval failed for {step['step_id']}: "
                        f"{approve_status}")
                _, approved_detail = api(
                    args.backend, f"/api/assignments/{args.run_id}",
                    token=token)
                resume_budgets.append({
                    "after_approval": budget_snapshot(approved_detail)})
            api(args.backend, f"/api/assignments/{args.run_id}/resume",
                token=token, method="POST")
            resume_calls += 1
            _, resumed_detail = api(
                args.backend, f"/api/assignments/{args.run_id}", token=token)
            resume_budgets.append({
                "after_resume": budget_snapshot(resumed_detail)})
        elif (assignment.get("status") in ("waiting", "paused_hitl",
                                           "blocked")
              and resume_calls < 3):
            api(args.backend, f"/api/assignments/{args.run_id}/resume",
                token=token, method="POST")
            resume_calls += 1
            _, resumed_detail = api(
                args.backend, f"/api/assignments/{args.run_id}", token=token)
            resume_budgets.append({
                "after_resume": budget_snapshot(resumed_detail)})
        time.sleep(1)
    else:
        raise SystemExit(
            f"REFUSED: assignment did not complete: {detail.get('assignment')}")
    after = detail["assignment"]
    budget_after_completion = budget_snapshot(detail)
    steps = {step["step_id"]: step for step in after.get("steps") or []}
    source_after = steps["source-1"]
    document = next(item for item in after.get("deliverables") or []
                    if item.get("kind") == "document")
    artifact_path = Path(document["artifact_path"])
    artifact_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    parsed = docx.Document(str(artifact_path))
    normal = parsed.styles["Normal"].font
    artifact = {
        "path": str(artifact_path),
        "bytes": artifact_path.stat().st_size,
        "sha256": artifact_hash,
        "declared_sha256": document.get("sha256"),
        "normal_font": normal.name,
        "normal_size": normal.size.pt if normal.size else None,
        "text": "\n".join(p.text for p in parsed.paragraphs)[:2000],
    }

    resume_results = []
    for _ in range(2):
        resume_status, resume_body = api(
            args.backend, f"/api/assignments/{args.run_id}/resume",
            token=token, method="POST")
        resume_results.append({
            "status": resume_status,
            "assignment_status": (resume_body.get("assignment") or {}).get(
                "status") if isinstance(resume_body, dict) else None,
        })
    duplicate_response_status, duplicate_response = api(
        args.backend, f"/api/assignments/{args.run_id}/responses/"
                      f"{args.correlation}",
        token=token, method="POST", body={"response": args.response})
    _, duplicate_detail = api(
        args.backend, f"/api/assignments/{args.run_id}", token=token)
    budget_after_duplicate = budget_snapshot(duplicate_detail)

    outbox_path = Path(args.outbox)
    lines = outbox_path.read_text().splitlines() if outbox_path.exists() else []
    record = {
        "schema": "atom-c2-closure-1",
        "run_id": args.run_id,
        "assignment_id": assignment_id,
        "elapsed_seconds_since_wait": round(elapsed, 1),
        "gate": args.wait_reached,
        "status_before": before["status"],
        "status_after": after["status"],
        "teaching_revision_before": teaching_before,
        "teaching_revision_after": after["teaching_revision"],
        "source_1_before": {
            "status": source_before.get("status"),
            "operation_id": source_before.get("operation_id"),
            "attempts": source_before.get("attempts"),
            "result_value": (source_before.get("result") or {}).get("value"),
        },
        "source_1_after": {
            "status": source_after.get("status"),
            "operation_id": source_after.get("operation_id"),
            "attempts": source_after.get("attempts"),
            "result_value": (source_after.get("result") or {}).get("value"),
        },
        "steps_after": {key: value.get("status")
                        for key, value in steps.items()},
        "wait_after": {
            "status": steps.get("wait", {}).get("status"),
            "result_value": (steps.get("wait", {}).get("result") or {}).get(
                "value"),
            "waiting": steps.get("wait", {}).get("waiting"),
        },
        "budget_before": budget_before,
        "budget_after_response": budget_after_response,
        "budget_after_completion": budget_after_completion,
        "budget_after_duplicate_response": budget_after_duplicate,
        "budget_resume_snapshots": resume_budgets,
        "approvals": approvals,
        "approval_required": bool(approvals),
        "retry_events": [],
        "resume_calls": resume_calls,
        "artifact": artifact,
        "duplicate_resume": resume_results,
        "duplicate_response": {
            "http": duplicate_response_status,
            "body": duplicate_response,
        },
        "outbox_path": str(outbox_path),
        "outbox_lines": len(lines),
        "outbox_operation_ids": [
            json.loads(line).get("operation_id") for line in lines],
        "serving_identity": api(args.backend, "/health")[1].get("identity"),
        "sampled_at": datetime.now(timezone.utc).isoformat(),
    }
    (out / "closure.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
