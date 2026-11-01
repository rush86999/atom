#!/usr/bin/env python3
"""Part B — one authorized live Outlook send and Sent Items reconciliation.

The exact body is read from the frozen file (which already contains the
account's stored signature) and passed as the assignment/outbound body, so the
product does not append a second signature. The standing authority is one
effect, one recipient, 24 hours. No retry is ever created: an uncertain send
is left to the durable operation's reconciliation.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from integrations.onedrive_service import OneDriveService

GRAPH = "https://graph.microsoft.com/v1.0"
ACCOUNT = "rish@brennan.ca"
SUBJECT = "[Atom qualification] One authorized send 2026-11-01"
EXPECTED_BODY_SHA256 = "0b8c96d5aab954cc4b5a879ea95c37b7680a7b0984d877d526294385d8a1e696"
EXPECTED_WIRE_SHA256 = "ef3472ddc5401b8ab700b9545f75193042afc8958c9ec3f0994680cfd9783e67"


def api_call(base: str, path: str, token: str | None = None, body=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{base}{path}", data=data,
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"API {path} refused: {exc.code} {exc.read().decode()[:2000]}")


def login(base: str, password: str) -> str:
    return api_call(base, "/api/auth/login",
                    body={"username": "admin@example.com", "password": password},
                    method="POST")["access_token"]


def graph_get(client: httpx.Client, token: str, path: str) -> dict:
    response = client.get(f"{GRAPH}{path}",
                          headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return response.json()


def sent_messages(client: httpx.Client, token: str) -> list[dict]:
    payload = graph_get(
        client, token,
        "/me/mailFolders/sentitems/messages?$top=50&$orderby=sentDateTime desc"
        "&$select=id,subject,toRecipients,sentDateTime,hasAttachments,"
        "internetMessageId,body,from",
    )
    return payload.get("value") or []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", default="http://127.0.0.1:8071")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--user-id", default="b83eb105-d9e7-41a5-83e3-a632b15b9ee3")
    ap.add_argument("--source-file", default="release_update_workbook_c912375de.csv")
    ap.add_argument("--source-sheet", default="release_update_workbook_c912375de")
    ap.add_argument("--run-id")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    body = Path(args.body_file).read_text()
    checks = []

    def record(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name, detail or "")

    body_sha = hashlib.sha256(body.encode()).hexdigest()
    record("exact body file matches the frozen hash", body_sha == EXPECTED_BODY_SHA256,
           body_sha)

    service = OneDriveService()
    token, resolution = asyncio.run(service.get_access_token_resolution(
        "b83eb105-d9e7-41a5-83e3-a632b15b9ee3"))
    record("normal token resolver returned a usable grant", bool(token)
           and resolution.get("token_available") is True, resolution)
    if not token:
        return 1

    with httpx.Client(timeout=120, follow_redirects=True) as client:
        me = graph_get(client, token, "/me?$select=id,userPrincipalName,mail,displayName")
        record("mailbox identity is the authorized account",
               me.get("userPrincipalName") == ACCOUNT and me.get("mail") == ACCOUNT, me)
        (out / "identity.json").write_text(json.dumps(me, indent=2) + "\n")
        if me.get("userPrincipalName") != ACCOUNT:
            return 1

        token_api = login(args.api_base, Path(args.password_file).read_text().strip())

        if args.verify:
            if not args.run_id:
                raise SystemExit("--run-id is required with --verify")
            run_id = args.run_id
            detail = api_call(args.api_base, f"/api/assignments/{run_id}", token_api)
            saved = json.loads((out / "send.json").read_text())
            window_start = datetime.fromisoformat(saved["window_start"])
            window_end = datetime.fromisoformat(saved["window_end"])
            messages = sent_messages(client, token)
            matches = [m for m in messages
                       if str(m.get("subject") or "") == SUBJECT
                       and any(str((r.get("emailAddress") or {}).get("address") or "").lower()
                               == ACCOUNT
                               for r in m.get("toRecipients") or [])
                       and window_start <= datetime.fromisoformat(
                           str(m.get("sentDateTime")).replace("Z", "+00:00"))
                       <= window_end]
            record("restart left the operation terminal",
                   (detail.get("assignment") or {}).get("status") in
                   ("completed", "achieved"), (detail.get("assignment") or {}).get("status"))
            record("restart did not add a second Sent Items row", len(matches) == 1,
                   {"matches": len(matches)})
            (out / "reopen.json").write_text(json.dumps({
                "assignment": detail,
                "sent_items_matches": matches,
                "window_start": saved["window_start"],
                "window_end": saved["window_end"],
            }, indent=2) + "\n")
            result = {"schema": "atom-live-qualification-b-verify-1",
                      "checks": checks,
                      "passed": all(item["ok"] for item in checks),
                      "run_id": run_id}
            (out / "verify-result.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 1

        sources = api_call(args.api_base, "/api/assignments/sources", token_api)
        source_row = next((
            item for item in sources
            if item.get("file_name") == args.source_file
            and item.get("sheet") == args.source_sheet
            and item.get("source") == "upload"), None)
        record("independent local source is available for the send assignment",
               source_row is not None,
               {"file": args.source_file, "sheet": args.source_sheet})
        if not source_row:
            return 1

        created = api_call(args.api_base, "/api/canvas/email/create", token_api, {
            "user_id": args.user_id,
            "subject": SUBJECT,
            "recipients": [ACCOUNT],
            "layout": "compose",
        }, "POST")
        canvas_id = created["canvas_id"]
        record("owned email canvas created for the prepared send",
               bool(canvas_id) and created.get("success") is True, canvas_id)

        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=24)
        grant = {
            "grant_id": f"sga-live-qual-{int(time.time())}",
            "actions": ["outbound"],
            "max_effects": 1,
            "recipients": [ACCOUNT],
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
        }
        assignment_body = {
            "objective": "Authorized live Outlook qualification send",
            "agent_id": args.agent_id,
            "sources": [{
                "kind": "workbook",
                "dataset_name": source_row["dataset_name"],
                "source": source_row["source"],
                "external_id": source_row["external_id"],
                "source_version": source_row["source_version"],
                "sheet": source_row["sheet"],
            }],
            "deliverables": [{
                "kind": "email_draft",
                "description": "Authorized qualification email draft",
                "to": [ACCOUNT],
                "subject": SUBJECT,
                "body": body,
            }],
            "outbound": {
                "to": [ACCOUNT],
                "subject": SUBJECT,
                "body": body,
                "canvas_id": canvas_id,
            },
            "standing_authority": grant,
        }
        created_assignment = api_call(args.api_base, "/api/assignments", token_api,
                                      assignment_body, "POST")
        run_id = created_assignment["run_id"]
        record("assignment created with the one-use grant", True,
               {"run_id": run_id, "grant_id": grant["grant_id"]})
        (out / "request.json").write_text(json.dumps({
            "run_id": run_id, "canvas_id": canvas_id, "grant": grant,
            "assignment": assignment_body,
        }, indent=2) + "\n")

        deadline = time.time() + 180
        detail = None
        while time.time() < deadline:
            detail = api_call(args.api_base, f"/api/assignments/{run_id}", token_api)
            status = (detail.get("assignment") or {}).get("status")
            if status in ("completed", "achieved", "failed", "cancelled", "waiting"):
                break
            time.sleep(2)
        assignment = (detail or {}).get("assignment") or {}
        send_step = next((s for s in assignment.get("steps") or []
                          if s.get("step_id") == "send"), {})
        record("send step applied", send_step.get("status") == "applied",
               {"status": send_step.get("status"),
                "receipt": send_step.get("standing_authority_receipt")})
        record("assignment completed", assignment.get("status") in
               ("completed", "achieved"), assignment.get("status"))

        # Exact pre-send payload from the durable operation record.
        con = sqlite3.connect(args.db)
        con.row_factory = sqlite3.Row
        row = con.execute("select parameters from goal_runs where id=?", (run_id,)).fetchone()
        lifecycle = json.loads(row["parameters"]).get("task_lifecycle") or {}
        send_ops = [op for op in lifecycle.get("operations") or []
                    if op.get("step_id") == "send"]
        operation = send_ops[0] if send_ops else {}
        arguments = ((operation.get("operation_binding") or {}).get("arguments") or {})
        record("durable send binding carries the exact body", arguments.get("body") == body,
               hashlib.sha256(str(arguments.get("body") or "").encode()).hexdigest())
        record("durable send binding carries the exact recipient and subject",
               arguments.get("to") == [ACCOUNT]
               and arguments.get("subject") == SUBJECT,
               {"to": arguments.get("to"), "subject": arguments.get("subject")})
        (out / "operation.json").write_text(json.dumps({
            "operation": operation,
            "payload_sha256": operation.get("payload_sha256"),
        }, indent=2) + "\n")

        window_start = now - timedelta(minutes=5)
        window_end = now + timedelta(minutes=30)
        matches = []
        for _ in range(15):
            messages = sent_messages(client, token)
            matches = [m for m in messages
                       if str(m.get("subject") or "") == SUBJECT
                       and any(str((r.get("emailAddress") or {}).get("address") or "").lower()
                               == ACCOUNT
                               for r in m.get("toRecipients") or [])
                       and window_start <= datetime.fromisoformat(
                           str(m.get("sentDateTime")).replace("Z", "+00:00"))
                       <= window_end]
            if matches:
                break
            time.sleep(4)
        record("exactly one Sent Items message matches the authorized send",
               len(matches) == 1, {"matches": len(matches)})
        if matches:
            message = matches[0]
            record("Sent Items recipient and no attachment are exact",
                   not message.get("hasAttachments")
                   and any(str((r.get("emailAddress") or {}).get("address") or "").lower()
                           == ACCOUNT for r in message.get("toRecipients") or []),
                   {"to": message.get("toRecipients"),
                    "hasAttachments": message.get("hasAttachments")})
            graph_body = str((message.get("body") or {}).get("content") or "")
            record("Sent Items body matches the frozen wire body",
                   hashlib.sha256(graph_body.encode()).hexdigest() == EXPECTED_WIRE_SHA256,
                   {"sha256": hashlib.sha256(graph_body.encode()).hexdigest()})
            (out / "sent-item.json").write_text(json.dumps(message, indent=2) + "\n")

        (out / "send.json").write_text(json.dumps({
            "schema": "atom-live-qualification-b-1",
            "checks": checks,
            "passed": all(item["ok"] for item in checks),
            "run_id": run_id,
            "canvas_id": canvas_id,
            "grant": grant,
            "assignment": assignment,
            "sent_items_matches": matches,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "body_sha256": body_sha,
            "wire_sha256": EXPECTED_WIRE_SHA256,
            "serving_identity": api_call(args.api_base, "/health"),
        }, indent=2) + "\n")
        print(json.dumps({"passed": all(item["ok"] for item in checks),
                          "run_id": run_id, "checks": len(checks)}, indent=2))
        return 0 if all(item["ok"] for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
