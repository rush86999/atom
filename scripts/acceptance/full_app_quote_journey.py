#!/usr/bin/env python3
"""Full-app quote/service/exception journey on the normal application.

Logs in through the real UI, creates typed canvases from real CSV bytes,
derives totals, promotes an employee lesson, starts ordinary assignments with
downloadable artifacts, approves a declared registered action, and verifies the
artifact, provider/canvas readback and later consumption.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def _load_smoke():
    path = Path(__file__).with_name("canvas_typed_canvases_local.py")
    spec = importlib.util.spec_from_file_location("canvas_smoke", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


SMOKE = _load_smoke()
login = SMOKE.login
new_canvas = SMOKE.new_canvas
configure = SMOKE.configure
bind = SMOKE.bind
derive = SMOKE.derive
answer = SMOKE.answer
open_panel = SMOKE.open_panel


def api_fetch(page, api: str, path: str, *, method="GET", body=None):
    return page.evaluate(
        """async ({api, path, method, body}) => {
          const token = localStorage.getItem("auth_token")
            || localStorage.getItem("token") || "";
          const response = await fetch(`${api}${path}`, {
            method,
            headers: {"Content-Type": "application/json",
                      Authorization: `Bearer ${token}`},
            body: body === null ? undefined : JSON.stringify(body),
          });
          let payload;
          try { payload = await response.json(); } catch { payload = null; }
          return {status: response.status, body: payload};
        }""",
        {"api": api, "path": path, "method": method, "body": body},
    )


def poll_assignment(page, api: str, run_id: str, timeout=60):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = api_fetch(page, api, f"/api/assignments/{run_id}")
        status = ((last.get("body") or {}).get("assignment") or {}).get(
            "status")
        if status in ("completed", "failed", "cancelled", "blocked",
                      "awaiting_approval", "waiting"):
            return last
        time.sleep(0.5)
    return last


def _quote_manifest(agent_id: str):
    return {
        "schema_version": 2,
        "base_component": "table",
        "operations": ["read", "derive", "edit", "bind"],
        "data_binding": {"subject_field": "Item"},
        "teaching_binding": {"agent_id": agent_id, "scope_id": "quote"},
        "fields": [
            {"id": "item_id", "label": "Item", "type": "string",
             "column": "Item", "required": True},
            {"id": "quantity", "label": "Quantity", "type": "decimal",
             "column": "Qty", "unit": "each", "required": True,
             "editable": True},
            {"id": "unit_price", "label": "Unit price", "type": "currency",
             "column": "Price", "currency": "USD", "required": True,
             "editable": True},
            {"id": "line_total", "label": "Line total", "type": "currency",
             "column": "Line Total", "currency": "USD",
             "derived": "quantity * unit_price", "aggregate": "sum",
             "group_by": "item_id"},
        ],
        "actions": [{
            "id": "publish",
            "operation": "canvas.present_markdown",
            "allowed_fields": ["item_id", "quantity", "unit_price",
                                "line_total"],
            "target": "quote-reviewer",
            "authority": "canvas-owner",
            "arguments": {
                "title": "Quote ${objective}",
                "content": (
                    "# ${objective}\\n\\nTotal: ${total} ${currency}\\n\\n"
                    "Receipt: ${receipt_digest}"),
            },
        }],
        "outputs": ["xlsx"],
    }


def _service_manifest(agent_id: str):
    return {
        "schema_version": 2,
        "base_component": "form",
        "operations": ["read", "derive", "edit", "bind"],
        "data_binding": {"subject_field": "Service"},
        "teaching_binding": {"agent_id": agent_id, "scope_id": "service"},
        "fields": [
            {"id": "service", "label": "Service", "type": "string",
             "column": "Service", "required": True},
            {"id": "hours", "label": "Hours", "type": "decimal",
             "column": "Hours", "unit": "hour", "required": True},
            {"id": "rate", "label": "Rate", "type": "currency",
             "column": "Rate", "currency": "CAD", "required": True},
            {"id": "fee_total", "label": "Fee total", "type": "currency",
             "column": "Fee Total", "currency": "CAD",
             "derived": "hours * rate", "aggregate": "sum",
             "group_by": "service"},
        ],
        "outputs": ["xlsx"],
    }


def _queue_manifest(agent_id: str):
    return {
        "schema_version": 2,
        "base_component": "queue",
        "operations": ["read", "derive", "edit", "select", "bind"],
        "data_binding": {"subject_field": "Exception",
                          "status_field": "Status"},
        "teaching_binding": {"agent_id": agent_id, "scope_id": "queue"},
        "fields": [
            {"id": "exception_id", "label": "Exception", "type": "string",
             "column": "Exception", "required": True,
             "aggregate": "count", "group_by": "status"},
            {"id": "amount", "label": "Amount", "type": "currency",
             "column": "Amount", "currency": "USD", "required": True,
             "editable": True, "aggregate": "sum", "group_by": "status"},
            {"id": "status", "label": "Status", "type": "string",
             "column": "Status", "required": True, "editable": True},
        ],
        "outputs": ["xlsx"],
    }


def _canvas_with_bind(page, frontend, agent_id, manifest, csv_path):
    url = new_canvas(page, frontend, agent_id)
    configure(page, manifest)
    bound = bind(page, csv_path)
    derived = derive(page)
    return url, bound, derived


def _start_assignment(page, canvas_url, kind="document"):
    page.goto(canvas_url, wait_until="domcontentloaded")
    panel = page.get_by_test_id("canvas-capability-panel")
    panel.wait_for(state="visible", timeout=120000)
    open_panel(page)
    panel.get_by_test_id("capability-artifact-kind").select_option(kind)
    with page.expect_response(
            lambda r: "/capability/assign" in r.url
            and r.request.method == "POST", timeout=120000) as info:
        panel.get_by_test_id("capability-assign").click()
    assigned = info.value.json()
    return assigned


def _approve_action(page, api, run_id, step_id):
    approved = api_fetch(
        page, api, f"/api/assignments/{run_id}/approve/{step_id}",
        method="POST", body={"note": "full-app journey approval"})
    if approved["status"] != 200:
        raise AssertionError(
            f"approval failed: {approved['status']} {approved['body']}")
    return approved


def _download_artifact(page, api, run_id, deliverable_id, out_dir):
    result = page.evaluate(
        """async ({api, runId, deliverableId}) => {
          const token = localStorage.getItem("auth_token")
            || localStorage.getItem("token") || "";
          const response = await fetch(
            `${api}/api/assignments/${runId}/deliverables/${deliverableId}/download`,
            {headers: {Authorization: `Bearer ${token}`}});
          const buffer = await response.arrayBuffer();
          return {status: response.status,
                  bytes: Array.from(new Uint8Array(buffer))};
        }""",
        {"api": api, "runId": run_id, "deliverableId": deliverable_id},
    )
    if result["status"] != 200:
        raise AssertionError(f"download failed: {result['status']}")
    path = out_dir / f"{deliverable_id}-{run_id[:8]}.bin"
    path.write_bytes(bytes(result["bytes"]))
    return path


def restart_world(password_file: str, api: str, frontend: str) -> dict:
    """Restart the real app processes against the same durable world."""
    world = Path(password_file).resolve().parent
    root = Path(__file__).resolve().parents[2]
    backend_pid = int((world / "backend.pid").read_text().strip())
    frontend_pid = int((world / "frontend.pid").read_text().strip())
    for pid in (backend_pid, frontend_pid):
        subprocess.run(["kill", "-INT", str(pid)], check=False)
    deadline = time.time() + 30
    while time.time() < deadline:
        alive = []
        for pid in (backend_pid, frontend_pid):
            probe = subprocess.run(
                ["kill", "-0", str(pid)], capture_output=True)
            if probe.returncode == 0:
                alive.append(pid)
        if not alive:
            break
        time.sleep(0.5)
    env = dict(os.environ)
    env.update({
        "WORLD": str(world),
        "ADMIN_PASSWORD": Path(password_file).read_text().strip(),
        "BACKEND_PORT": str(urllib.parse.urlparse(api).port or 8096),
        "FRONTEND_PORT": str(urllib.parse.urlparse(frontend).port or 3137),
        "ATOM_FRONTEND_DIR": str(root / "frontend-nextjs"),
        "PYTHON": os.getenv(
            "BRENNAN_PYTHON",
            "/Users/rushiparikh/projects/atom/backend/venv314/bin/python"),
    })
    completed = subprocess.run(
        ["bash", str(root / "scripts/acceptance/"
         "launch_integrated_local_candidate.sh")],
        env=env, capture_output=True, text=True, timeout=600)
    if completed.returncode != 0:
        raise AssertionError(
            f"world restart failed: {completed.stderr[-800:]}")
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                    f"{api}/api/health", timeout=3) as response:
                if response.status == 200:
                    break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    else:
        raise AssertionError("restarted backend did not become healthy")
    return {
        "old_backend_pid": backend_pid,
        "new_backend_pid": int((world / "backend.pid").read_text().strip()),
        "old_frontend_pid": frontend_pid,
        "new_frontend_pid": int((world / "frontend.pid").read_text().strip()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", required=True)
    parser.add_argument("--api", required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--restart", action="store_true",
                        default=True)
    args = parser.parse_args()
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    password = Path(args.password_file).read_text().strip()

    quote_csv = out / "quote.csv"
    quote_csv.write_text(
        "Item,Qty,Price\nA,2,100.00\nB,3,50.00\n", encoding="utf-8")
    service_csv = out / "service.csv"
    service_csv.write_text(
        "Service,Hours,Rate\nConsulting,4,120.00\nSite trip,2,75.00\n",
        encoding="utf-8")
    queue_csv = out / "queue.csv"
    queue_csv.write_text(
        "Exception,Amount,Status\nEX-1,,Open\nEX-2,50.00,Open\n"
        "EX-3,20.00,Closed\n", encoding="utf-8")

    checks = []

    def record(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS" if ok else "FAIL"), name,
              json.dumps(detail or {}, default=str)[:600])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        page = context.new_page()
        page.set_default_timeout(120000)
        page.set_default_navigation_timeout(120000)
        login(page, args.frontend, password)

        # Teach a document format first; the next assignment must consume it.
        quote_url, quote_bound, quote_derived = _canvas_with_bind(
            page, args.frontend, args.agent_id, _quote_manifest(args.agent_id),
            quote_csv)
        proposal = api_fetch(
            page, args.api,
            f"/api/canvas/{quote_url.rstrip('/').split('/')[-1]}"
            "/capability/teaching/propose",
            method="POST", body={
                "lesson": "Use Georgia 18 for customer quote documents",
                "topic": "quote document format",
                "applies_to": ["document"],
                "format_spec": {"font_name": "Georgia", "font_size": 18},
                "agent_id": args.agent_id,
                "expected_revision": quote_bound["body"]["revision"],
                "manifest_revision": quote_bound["body"]["manifest"][
                    "manifest_revision"],
                "source_version": quote_bound["body"]["source"][
                    "source_version"],
            })
        proposal_id = (proposal["body"] or {}).get("proposal", {}).get("id")
        promoted = api_fetch(
            page, args.api,
            f"/api/canvas/{quote_url.rstrip('/').split('/')[-1]}"
            f"/capability/teaching/{proposal_id}/promote",
            method="POST", body={
                "approved": True,
                "expected_revision": quote_bound["body"]["revision"],
                "manifest_revision": quote_bound["body"]["manifest"][
                    "manifest_revision"],
                "source_version": quote_bound["body"]["source"][
                    "source_version"],
            })
        record("promoted document lesson is explicit and source-bound",
               proposal["status"] == 200
               and promoted["status"] == 200
               and (promoted["body"] or {}).get("status") == "promoted",
               {"proposal": proposal["status"],
                "promote": promoted["status"]})

        quoted = _start_assignment(page, quote_url, "document")
        run_id = quoted.get("run_id")
        record("quote receipt starts an ordinary assignment",
               run_id and quoted.get("assignment", {}).get("status") in (
                   "waiting", "awaiting_approval", "completed"),
               {"run_id": run_id,
                "status": quoted.get("assignment", {}).get("status")})
        step_ids = [
            item.get("step_id")
            for item in quoted.get("assignment", {}).get("steps", [])
        ]
        needs_approval = any(
            item.get("status") == "awaiting_approval"
            and item.get("approval_request")
            for item in quoted.get("assignment", {}).get("steps", []))
        restart_evidence = None
        if needs_approval and args.restart:
            restart_evidence = restart_world(
                args.password_file, args.api, args.frontend)
            record("real backend restart preserves the prepared action",
                   restart_evidence["old_backend_pid"]
                   != restart_evidence["new_backend_pid"],
                   restart_evidence)
            resumed = poll_assignment(page, args.api, run_id)
            resumed_steps = resumed.get("body", {}).get(
                "assignment", {}).get("steps", [])
            record("prepared action survives restart without dispatch",
                   any(item.get("step_id") == "action-publish"
                       and item.get("status") == "awaiting_approval"
                       for item in resumed_steps),
                   {"steps": [item.get("step_id") for item in []]})
            _approve_action(page, args.api, run_id, "action-publish")
        final = poll_assignment(page, args.api, run_id)
        final_assignment = final.get("body", {}).get("assignment", {})
        record("quote assignment completes after action approval",
               final_assignment.get("status") == "completed",
               {"status": final_assignment.get("status"),
                "steps": step_ids})
        artifacts = final_assignment.get("deliverables") or []
        record("quote document artifact is attached",
               artifacts and artifacts[0].get("artifact_path"),
               artifacts)
        if artifacts:
            downloaded = _download_artifact(
                page, args.api, run_id, "del-document", out)
            import docx
            text = "\n".join(
                p.text for p in docx.Document(str(downloaded)).paragraphs)
            record("quote document contains the server total and provenance",
                   "350.00" in text and "Receipt:" in text,
                   {"bytes": downloaded.stat().st_size})
            doc = docx.Document(str(downloaded))
            normal = doc.styles["Normal"].font
            record("quote document consumes the promoted lesson",
                   normal.name == "Georgia"
                   and int(normal.size.pt) == 18,
                   {"font": normal.name,
                    "size_pt": normal.size.pt if normal.size else None})
        action_steps = [
            item for item in final_assignment.get("steps", [])
            if item.get("step_id") == "action-publish"
        ]
        before_ops = final.get("body", {}).get("operations", [])
        before_remote = next(
            (item.get("remote_id") for item in before_ops
             if item.get("step_id") == "action-publish"), None)
        record("declared registered action has readback evidence",
               action_steps and action_steps[0].get("status") == "applied"
               and bool(before_remote),
               {"step": action_steps[:1], "remote_id": before_remote})
        duplicate = api_fetch(
            page, args.api, f"/api/assignments/{run_id}/approve/action-publish",
            method="POST", body={"note": "duplicate continuation control"})
        after = poll_assignment(page, args.api, run_id)
        after_steps = [
            item for item in after.get("body", {}).get(
                "assignment", {}).get("steps", [])
            if item.get("step_id") == "action-publish"
        ]
        after_ops = after.get("body", {}).get("operations", [])
        after_remote = next(
            (item.get("remote_id") for item in after_ops
             if item.get("step_id") == "action-publish"), None)
        record("duplicate continuation does not dispatch the action again",
               duplicate["status"] in (200, 404, 409)
               and before_remote == after_remote,
               {"approve_status": duplicate["status"],
                "before": before_remote, "after": after_remote})

        # Source change: the same canvas, new bytes, a new server receipt.
        changed_csv = out / "quote-changed.csv"
        changed_csv.write_text(
            "Item,Qty,Price\nA,4,100.00\nB,1,50.00\n", encoding="utf-8")
        page.goto(quote_url, wait_until="domcontentloaded")
        open_panel(page)
        changed_bound = bind(page, changed_csv)
        changed_derived = derive(page)
        record("source change produces a new server receipt",
               changed_bound["status"] == 200
               and changed_derived["body"].get("aggregates", {}).get(
                   "line_total") == "450.00",
               {"row_count": changed_bound["body"].get("row_count"),
                "aggregates": changed_derived["body"].get("aggregates")})
        stale = api_fetch(
            page, args.api,
            f"/api/canvas/{quote_url.rstrip('/').split('/')[-1]}"
            "/capability/assign",
            method="POST", body={
                "objective": "stale source control",
                "agent_id": args.agent_id,
                "expected_revision": quote_bound["body"]["revision"],
                "manifest_revision": quote_bound["body"]["manifest"][
                    "manifest_revision"],
                "source_version": quote_bound["body"]["source"][
                    "source_version"],
                "deliverable_kind": "document",
            })
        record("old source receipt is refused after the change",
               stale["status"] == 409
               and ((stale["body"] or {}).get("error") or {}).get("code")
               in ("stale_source", "stale_manifest", "stale_revision"),
               {"status": stale["status"],
                "error": ((stale["body"] or {}).get("error") or {}).get(
                    "code")})

        # Service proposal variant: same mechanisms, different shape/currency.
        service_url, service_bound, service_derived = _canvas_with_bind(
            page, args.frontend, args.agent_id,
            _service_manifest(args.agent_id), service_csv)
        service_assigned = _start_assignment(page, service_url, "document")
        service_final = poll_assignment(
            page, args.api, service_assigned.get("run_id"))
        service_assignment = service_final.get("body", {}).get(
            "assignment", {})
        record("service proposal completes with a document artifact",
               service_assignment.get("status") == "completed"
               and service_assignment.get("deliverables"),
               {"status": service_assignment.get("status")})

        # Exception queue variant: same mechanisms, non-sales rows.
        queue_url, queue_bound, queue_derived = _canvas_with_bind(
            page, args.frontend, args.agent_id,
            _queue_manifest(args.agent_id), queue_csv)
        if queue_derived["body"].get("status") == "clarification":
            answer(page, 2, "amount", "100.00")
        queue_assigned = _start_assignment(page, queue_url, "document")
        queue_final = poll_assignment(
            page, args.api, queue_assigned.get("run_id"))
        queue_assignment = queue_final.get("body", {}).get("assignment", {})
        record("exception queue completes with a document artifact",
               queue_assignment.get("status") == "completed"
               and queue_assignment.get("deliverables"),
               {"status": queue_assignment.get("status")})

        # Cancellation: a waiting action assignment must not dispatch.
        cancel_url, cancel_bound, cancel_derived = _canvas_with_bind(
            page, args.frontend, args.agent_id,
            _quote_manifest(args.agent_id), quote_csv)
        cancelled_assigned = _start_assignment(page, cancel_url, "document")
        cancelled_run = cancelled_assigned.get("run_id")
        cancelled = api_fetch(
            page, args.api, f"/api/assignments/{cancelled_run}/cancel",
            method="POST", body={"reason": "full-app cancellation control"})
        record("cancelled action assignment is terminal",
               cancelled["status"] == 200
               and (cancelled["body"].get("assignment") or {}).get(
                   "status") == "cancelled",
               {"status": cancelled["status"]})

        page.screenshot(path=str(out / "quote-journey.png"), full_page=True)
        result = {
            "schema": "atom-full-app-quote-journey-1",
            "status": "passed" if all(item["ok"] for item in checks) else "failed",
            "checks": checks,
            "quote_canvas": quote_url,
            "service_canvas": service_url,
            "queue_canvas": queue_url,
        }
        (out / "result.json").write_text(json.dumps(result, indent=2))
        browser.close()
    return 0 if all(item["ok"] for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
