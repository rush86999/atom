#!/usr/bin/env python3
"""Verify the declared DeepSeek configuration through the scoped product API.

This is a product-route check, not a direct-endpoint screening harness. It
creates an agent, teaches the task policy through the product endpoint,
uploads the source CSV through the product upload endpoint, waits for the
authoritative sheet dataset, and sends ONE assessment turn through
``/api/chat/message``. It never retries a substantive failure.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import httpx

ASK = (
    "Assess each Open invoice in vendor_loop.csv under the taught threshold "
    "rule. Give a table with vendor reference, amount and decision."
)
POLICY = (
    "Use exactly these decision labels: FUND, HOLD, DECLINE. Requested amount "
    "at or above 10000 is HOLD for CFO review. 5000 to 9999 is HOLD. Below "
    "5000 is DECLINE. Cite the reference and amount from the row."
)
TOPIC = "grant threshold rule"
EXPECTED = {"IN-7301": "DECLINE", "IN-7302": "HOLD", "IN-7303": "HOLD"}


def _json(response: httpx.Response) -> dict:
    try:
        return response.json()
    except Exception:  # noqa: BLE001
        return {"raw_text": response.text[:4000]}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")


def _dataset_rows(db_path: str, file_name: str) -> list[dict]:
    uri = f"file:{db_path}?mode=ro"
    out: list[dict] = []
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        for row in connection.execute(
                "SELECT file_name, entity_name, dataset_name, content_hash, "
                "row_count FROM dataset_entries WHERE file_name = ?",
                (file_name,)):
            out.append(dict(row))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8062")
    parser.add_argument("--admin-password-file", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--model-header", default="deepseek-v4-pro")
    parser.add_argument("--ask", default=ASK)
    parser.add_argument("--policy", default=POLICY)
    parser.add_argument("--topic", default=TOPIC)
    parser.add_argument("--expected-json", default="")
    parser.add_argument("--file-name", default="vendor_loop.csv")
    args = parser.parse_args()

    out = Path(args.out_dir).resolve()
    if (out / "product_route_result.json").exists():
        raise SystemExit("REFUSING TO OVERWRITE product-route result")
    out.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/")
    expected = json.loads(args.expected_json) if args.expected_json else EXPECTED
    ask = args.ask
    policy = args.policy
    topic = args.topic
    password = Path(args.admin_password_file).read_text(encoding="utf-8").strip()
    client = httpx.Client(trust_env=False, timeout=330.0)
    steps: list[dict] = []

    def step(name: str, ok: bool, detail: object = None) -> None:
        steps.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS" if ok else "FAIL"), name, detail if detail is not None else "")

    login = client.post(
        base + "/api/auth/login",
        json={"username": "admin@example.com", "password": password},
    )
    login_body = _json(login)
    token = str(login_body.get("access_token") or "")
    step("admin login", login.status_code == 200 and bool(token), login.status_code)
    if not token:
        _write(out / "product_route_result.json",
               {"steps": steps, "login": login_body})
        return 2
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get(base + "/api/auth/me", headers=headers)
    me_body = _json(me)
    user_id = str(me_body.get("id") or me_body.get("user_id") or "")
    step("authenticated workspace/user", me.status_code == 200 and bool(user_id),
         {"status": me.status_code, "workspace_id": me_body.get("workspace_id")})

    created = client.post(
        base + "/api/agents/custom",
        headers=headers,
        json={
            "name": "Core Release DeepSeek Assessor",
            "description": "DeepSeek product-route verification hire.",
            "category": "Operations",
            "configuration": {
                "system_prompt": (
                    "You assess tabular records against the policy you were "
                    "taught and cite the source row.")
            },
            "schedule_config": {},
        },
    )
    created_body = _json(created)
    agent_id = str(((created_body.get("data") or {}).get("agent_id"))
                   or created_body.get("agent_id") or "")
    step("agent created through product API",
         created.status_code in (200, 201) and bool(agent_id),
         {"status": created.status_code, "agent_id": agent_id})
    if not agent_id:
        _write(out / "product_route_result.json",
               {"steps": steps, "create": created_body})
        return 2

    taught = client.post(
        base + f"/api/agents/{agent_id}/teach",
        headers=headers,
        json={"lesson": policy, "topic": topic},
    )
    taught_body = _json(taught)
    _write(out / "teach_response.json", taught_body)
    # The teach endpoint returns the composite result, not always a
    # teaching_point object. Read the persisted journal (same source the
    # Training tab shows) and bind the exact point id.
    detail = client.get(base + f"/api/agents/{agent_id}", headers=headers)
    detail_body = _json(detail)
    _write(out / "agent_detail_after_teach.json", detail_body)
    learning = (((detail_body.get("data") or {}).get("configuration") or {})
                .get("learning") or {})
    log = learning.get("log") if isinstance(learning, dict) else []
    point = next(
        (
            entry for entry in (log or [])
            if isinstance(entry, dict)
            and str(entry.get("lesson") or "") == policy
        ),
        {},
    )
    policy_id = str(point.get("id") or "")
    step("policy taught through product API",
         taught.status_code == 200 and bool(policy_id),
         {"status": taught.status_code, "policy_id": policy_id,
          "lesson": point.get("lesson")})

    csv_bytes = Path(args.csv).read_bytes()
    uploaded = client.post(
        base + "/api/documents/upload",
        headers=headers,
        files={"file": (args.file_name, csv_bytes, "text/csv")},
    )
    upload_body = _json(uploaded)
    step("source uploaded through product API", uploaded.status_code == 200,
         {"status": uploaded.status_code,
          "document_id": upload_body.get("id") or upload_body.get("document_id")})

    entries: list[dict] = []
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        entries = _dataset_rows(args.db, args.file_name)
        if entries:
            break
        time.sleep(1.5)
    step("authoritative sheet dataset materialized", bool(entries), entries)
    if not entries:
        _write(out / "product_route_result.json",
               {"steps": steps, "upload": upload_body})
        return 2

    request_payload = {
        "message": ask,
        "user_id": user_id,
        "session_id": "new",
        "agent_id": agent_id,
        "request_id": f"req_{uuid.uuid4()}",
        "context": {
            "current_page": "/chat",
            "agent_id": agent_id,
            "conversation_history": [],
        },
    }
    request_headers = {
        **headers,
        "x-atom-model": args.model_header,
        "x-atom-intent": "reasoning",
    }
    started = time.monotonic()
    chat = client.post(
        base + "/api/chat/message", headers=request_headers, json=request_payload)
    latency_ms = int((time.monotonic() - started) * 1000)
    chat_body = _json(chat)
    metadata = chat_body.get("metadata") or {}
    review = metadata.get("review_result") or chat_body.get("review_result") or {}
    decisions = {
        str(a.get("subject_id")): str(a.get("decision"))
        for a in (review.get("assessments") or [])
        if isinstance(a, dict)
    }
    review_ok = bool(review.get("ok"))
    decisions_ok = decisions == expected
    step("one assessment turn returned", chat.status_code == 200,
         {"status": chat.status_code, "latency_ms": latency_ms})
    step("review structurally certified", review_ok, review.get("errors") or [])
    step("review decisions match the taught policy", decisions_ok, decisions)
    step("source hash present", all(
        str((ref.get("source_identity") or {}).get("content_hash") or "")
        for assessment in review.get("assessments") or []
        for ref in assessment.get("evidence_refs") or []
    ), entries)

    session_id = str(chat_body.get("session_id") or "")
    if session_id and session_id != "new":
        history = client.get(
            base + f"/api/chat/history/{session_id}", headers=headers)
        _write(out / "history.json", _json(history))

    result = {
        "schema": "deepseek-product-route-verification-1",
        "base_url": base,
        "agent_id": agent_id,
        "user_id": user_id,
        "session_id": session_id,
        "policy_id": policy_id,
        "policy_lesson": policy,
        "requested_model_header": args.model_header,
        "request": request_payload,
        "response_status": chat.status_code,
        "latency_ms": latency_ms,
        "response": chat_body,
        "review": review,
        "decisions": decisions,
        "expected": expected,
        "dataset_entries": entries,
        "steps": steps,
        "all_ok": all(item["ok"] for item in steps),
    }
    _write(out / "product_route_result.json", result)
    print(json.dumps({"all_ok": result["all_ok"],
                      "decisions": decisions,
                      "latency_ms": latency_ms}, indent=1))
    return 0 if result["all_ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
