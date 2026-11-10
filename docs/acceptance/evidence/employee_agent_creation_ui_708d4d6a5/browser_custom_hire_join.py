#!/usr/bin/env python3
"""Bounded ordinary custom-Hire browser/API join.

Reuses the existing acceptance infrastructure, not a new launcher:
  * run_isolated.py: storage guard, immutable code export, fixture DB, server
  * case5_browser_recovery.py: real frontend directory copy + Next dev
  * browser_verify.py: the real login form

Scope: one ordinary custom Hire from the Agents page at the frozen UI source.
It records the exact one POST, the verified receipt id, the authoritative list
reload, STUDENT/no promotion/no scheduler duplicate, and that no model/provider
request is made. No product code is edited; no live DB or credential is used.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# MUST be set before importing the guard/launcher. The canonical config keeps
# the maintenance lock shared with every other launcher.
os.environ.setdefault(
    "ATOM_WORLD_STORAGE_PATHS",
    "/Users/rushiparikh/projects/atom/backend/config",
)
REPO = Path(__file__).resolve().parents[4]
BACKEND = REPO / "backend"
os.environ.setdefault("ACC_WORKTREE", str(REPO))
os.environ.setdefault("NEXTAUTH_SECRET", secrets.token_urlsafe(32))
sys.path.insert(0, str(BACKEND))

from scripts.orchestration_acceptance import run_isolated as R  # noqa: E402
from scripts.orchestration_acceptance import case5_browser_recovery as C5  # noqa: E402
from scripts.orchestration_acceptance import browser_verify as BV  # noqa: E402
from core import world_storage_guard as WSG  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

import httpx  # noqa: E402

PROVIDER_HOST_MARKERS = (
    "openai", "anthropic", "googleapis", "generativelanguage",
    "openrouter", "deepseek", "groq", "together", "cohere", "mistral",
)


def api_json(response: httpx.Response) -> object:
    body = response.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def wait_until(page, predicate, timeout_s: int = 60, step_ms: int = 250):
    end = time.time() + timeout_s
    while time.time() < end:
        value = predicate()
        if value:
            return value
        page.wait_for_timeout(step_ms)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--world", required=True)
    ap.add_argument("--backend-port", type=int, default=8073)
    ap.add_argument("--frontend-port", type=int, default=3173)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex[:10]
    world = R.BACKEND / "data" / "acceptance_worlds" / args.world
    result = {
        "status": "STARTED",
        "scope": "ordinary custom Hire only; no guided model generation",
        "world": args.world,
        "nonce": nonce,
        "ports": {"backend": args.backend_port, "frontend": args.frontend_port},
        "source": {
            "repo": str(REPO),
            "head": subprocess.run(
                ["git", "-C", str(REPO), "rev-parse", "HEAD"],
                capture_output=True, text=True).stdout.strip(),
            "branch": subprocess.run(
                ["git", "-C", str(REPO), "branch", "--show-current"],
                capture_output=True, text=True).stdout.strip(),
            "dirty": subprocess.run(
                ["git", "-C", str(REPO), "status", "--porcelain"],
                capture_output=True, text=True).stdout.strip(),
        },
        "storage_preflight": None,
        "runners_before": None,
        "runners_after": None,
        "network_boundary": None,
        "world_preflight": None,
        "run_dir": None,
        "db_path": None,
        "requests": [],
        "responses": [],
        "external_hosts": [],
        "ui": {},
        "api": {},
        "db": {},
        "controls": {},
        "screenshots": [],
        "errors": [],
    }
    server_proc = None
    frontend_proc = None
    client = None
    try:
        R.require_storage_ready()
        report = WSG.preflight()
        result["storage_preflight"] = report.summary()
        if not report.ok:
            raise RuntimeError(f"storage preflight failed: {report.summary()}")
        result["runners_before"] = WSG.list_runners()

        if not (world / "fixture" / "atom.db").exists():
            raise RuntimeError(f"world has no fixture DB: {world}")
        result["network_boundary"] = R.verify_network_boundary(world)
        # This world is a hash-pinned WORKING-TREE snapshot at the frozen UI
        # source, exactly as the builder recorded. Declare that mode so the
        # preflight checks the recorded snapshot instead of requiring HEAD to
        # equal the separate archive pin.
        R.build_world.snapshot_working_tree = True
        result["world_preflight"] = R.preflight(world)

        C5.ensure_port_free(args.backend_port)
        C5.ensure_port_free(args.frontend_port)
        # The sandboxed acceptance server only accepts browser calls from
        # explicitly declared origins. The real login form and the Agents page
        # run on the isolated frontend origin, so declare it for this run.
        os.environ["ADDITIONAL_ALLOWED_ORIGINS"] = (
            f"http://localhost:{args.frontend_port},"
            f"http://127.0.0.1:{args.frontend_port}")
        os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

        server_proc = R.launch_server(args.backend_port, world)
        run_dir = R.launch_server.last_run_dir
        result["run_dir"] = str(run_dir)
        result["db_path"] = str(run_dir / "data" / "atom.db")
        backend_base = f"http://127.0.0.1:{args.backend_port}"
        frontend_base = f"http://localhost:{args.frontend_port}"

        credential_dir = world / "backend_root" / "logs"

        def scratch_credential_file():
            candidates = sorted(
                p for p in credential_dir.glob("*.txt")
                if p.is_file() and p.stat().st_size)
            return candidates[0] if len(candidates) == 1 else None

        credential_path = scratch_credential_file()
        deadline = time.time() + 90
        while time.time() < deadline and credential_path is None:
            time.sleep(0.5)
            credential_path = scratch_credential_file()
        if credential_path is None:
            raise RuntimeError("bootstrap credential file was not created")
        credential_value = credential_path.read_text().strip()
        if not credential_value:
            raise RuntimeError("bootstrap credential file is empty")

        frontend_proc = C5.start_frontend_copy(
            args.backend_port, args.frontend_port, world)
        if frontend_proc is None:
            raise RuntimeError("frontend copy did not become usable")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel="chrome")
            context = browser.new_context(viewport={"width": 1440, "height": 1200})
            page = context.new_page()
            page.set_default_timeout(120000)

            custom_requests = []
            custom_responses = []
            response_objects = []
            external_hosts = set()

            def on_request(request):
                try:
                    url = str(request.url)
                    parsed = urlparse(url)
                    if parsed.hostname and parsed.hostname not in (
                            "127.0.0.1", "localhost", "::1"):
                        external_hosts.add(parsed.hostname)
                    if "/api/agents/custom" in url:
                        custom_requests.append({
                            "method": request.method,
                            "url": url,
                            "path": parsed.path,
                            "query": parse_qs(parsed.query),
                            "post_data": request.post_data,
                        })
                except Exception as exc:  # noqa: BLE001 - reported
                    result["errors"].append(
                        f"request capture {type(exc).__name__}: {exc}")

            def on_response(response):
                try:
                    if "/api/agents/custom" in str(response.url):
                        custom_responses.append({
                            "status": response.status,
                            "url": str(response.url),
                        })
                        response_objects.append(response)
                except Exception as exc:  # noqa: BLE001 - reported
                    result["errors"].append(
                        f"response capture {type(exc).__name__}: {exc}")

            page.on("request", on_request)
            page.on("response", on_response)

            login = BV.ui_login(
                page, frontend_base, "admin@example.com", credential_value)
            result["ui"]["login"] = {
                "ok": login.get("ok"),
                "landed_path": urlparse(login.get("landed_url") or "").path,
                "token_present": login.get("token_present_after_login"),
                "error": login.get("error"),
            }
            if not login.get("ok"):
                raise RuntimeError(f"UI login failed: {login}")

            page.goto(f"{frontend_base}/agents", wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            # Ordinary app onboarding modal, if this fresh world opens it.
            # It can mount a beat after the page itself, so wait for it before
            # interacting with the guide underneath.
            welcome = page.get_by_role(
                "heading", name="Welcome to Atom", exact=True)
            for _ in range(40):
                if welcome.count() and welcome.first.is_visible():
                    break
                page.wait_for_timeout(500)
            if welcome.count() and welcome.first.is_visible():
                for _ in range(10):
                    if not welcome.first.is_visible():
                        break
                    nxt = page.get_by_role("button", name="Next", exact=True)
                    start = page.get_by_role(
                        "button", name="Start Automating", exact=True)
                    if start.count() and start.first.is_visible():
                        start.first.click()
                    elif nxt.count() and nxt.first.is_visible():
                        nxt.first.click()
                    else:
                        break
                    page.wait_for_timeout(1200)
                if welcome.count() and welcome.first.is_visible():
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(800)
            page.wait_for_timeout(800)

            # The guide is hidden after mount only if previously dismissed.
            restore = page.get_by_test_id("agent-launch-restore")
            if restore.count() and restore.first.is_visible():
                restore.first.click()
                page.wait_for_timeout(700)

            cta = page.get_by_test_id("create-agent-cta")
            cta.wait_for(state="visible", timeout=60000)
            page.screenshot(path=str(out / "01_agents_before_hire.png"),
                            full_page=True)
            cta.click()

            name = f"Custom Hire Join {nonce}"
            description = (
                "Owns inbound leads and the pipeline. Controlled ordinary custom "
                "Hire join; drafts everything for approval until promoted.")
            page.get_by_test_id("launch-agent-name-input").fill(name)
            page.get_by_test_id("launch-agent-description-input").fill(description)
            page.screenshot(path=str(out / "02_hire_dialog.png"),
                            full_page=True)
            page.get_by_test_id("launch-agent-submit").click()

            # Wait for the network response, not just the toast.
            wait_until(page, lambda: len(custom_responses) > 0, timeout_s=90)
            page.wait_for_timeout(1200)
            page.screenshot(path=str(out / "03_after_hire.png"),
                            full_page=True)

            result["requests"] = custom_requests
            result["responses"] = custom_responses
            result["external_hosts"] = sorted(external_hosts)

            response_body = None
            if response_objects:
                try:
                    response_body = response_objects[0].json()
                except Exception as exc:  # noqa: BLE001 - reported
                    result["errors"].append(
                        f"response body read {type(exc).__name__}: {exc}")

            envelope_data = (response_body or {}).get("data") or {}
            agent_id = str(envelope_data.get("agent_id") or "")
            operation_id = str(envelope_data.get("operation_id") or "")
            verification = envelope_data.get("verification") or {}
            result["api"]["creation"] = {
                "http_status": (custom_responses[0]["status"]
                                if custom_responses else None),
                "success": (response_body or {}).get("success"),
                "agent_id": agent_id,
                "name": envelope_data.get("agent_name"),
                "category": envelope_data.get("category"),
                "operation_id": operation_id,
                "audit_id": envelope_data.get("audit_id"),
                "verification": verification,
            }
            if not agent_id:
                raise RuntimeError(
                    "creation response carried no exact agent_id: "
                    f"{json.dumps(response_body)[:500]}")
            if verification.get("status") not in ("verified", "already_applied"):
                raise RuntimeError(
                    f"creation was not verified: {verification}")

            token = page.evaluate(
                "() => localStorage.getItem('auth_token') || localStorage.getItem('token')")
            client = httpx.Client(
                base_url=backend_base,
                headers={"Authorization": f"Bearer {token}"},
                timeout=60, trust_env=False)

            # The authoritative list must show the exact returned id once.
            listed = client.get("/api/agents/")
            listed.raise_for_status()
            listed_data = api_json(listed)
            rows = listed_data if isinstance(listed_data, list) else []
            exact = [row for row in rows
                     if str(row.get("id") or row.get("agent_id") or "") == agent_id]
            same_name = [row for row in rows
                         if str(row.get("name") or "") == name]
            result["api"]["list"] = {
                "http_status": listed.status_code,
                "count_total": len(rows),
                "count_exact_id": len(exact),
                "count_same_name": len(same_name),
                "exact": exact[0] if exact else None,
            }

            # A real reload, then the same exact card only once.
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            card = page.locator(f'[data-testid="agent-card-{name}"]')
            card.first.wait_for(state="visible", timeout=60000)
            card_count_after_reload = card.count()
            maturity_text = ""
            if card_count_after_reload:
                badge = card.first.locator('[data-testid="agent-maturity-badge"]')
                if badge.count():
                    maturity_text = badge.first.inner_text().strip()
            page.screenshot(path=str(out / "04_after_reload.png"),
                            full_page=True)

            result["ui"]["hire"] = {
                "dialog_opened": True,
                "name": name,
                "card_count_after_reload": card_count_after_reload,
                "maturity_badge": maturity_text,
                "toast_visible": page.get_by_text(
                    re.compile(r"employee hired", re.I)).count() > 0,
            }

            # Give any transport replay time to become visible; it must not.
            page.wait_for_timeout(3000)
            result["controls"]["exactly_one_post_at_end"] = (
                len(custom_requests) == 1)
            result["controls"]["exactly_one_response_at_end"] = (
                len(custom_responses) == 1)

            db_path = run_dir / "data" / "atom.db"
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            agent_rows = con.execute(
                "select id, name, status, confidence_score, schedule_config, "
                "configuration from agent_registry where id = ?",
                (agent_id,)).fetchall()
            name_rows = con.execute(
                "select id, name from agent_registry where name = ?",
                (name,)).fetchall()
            audit_rows = con.execute(
                "select id, event_type from saas_audit_logs where id = ?",
                (operation_id,)).fetchall()
            con.close()

            agent_row = dict(agent_rows[0]) if agent_rows else None
            schedule_value = None
            if agent_row is not None:
                schedule_value = agent_row.get("schedule_config")
            result["db"] = {
                "exact_agent_rows": len(agent_rows),
                "same_name_rows": len(name_rows),
                "audit_rows_for_operation": len(audit_rows),
                "agent": agent_row,
                "audit": [dict(r) for r in audit_rows],
            }

            request_query = (custom_requests[0]["query"]
                             if custom_requests else {})
            sent_operation_id = (request_query.get("operation_id") or [None])[0]

            result["controls"].update({
                "one_post": len(custom_requests) == 1,
                "one_response": len(custom_responses) == 1,
                "request_method_post": bool(
                    custom_requests and custom_requests[0]["method"] == "POST"),
                "operation_id_sent": bool(sent_operation_id),
                "operation_id_receipt_prefix": operation_id.startswith(
                    "agent:create:"),
                "operation_id_receipt_matches_request": bool(
                    sent_operation_id and operation_id.endswith(sent_operation_id)),
                "audit_id_matches_operation": (
                    envelope_data.get("audit_id") == operation_id),
                "verified_receipt": verification.get("status") in (
                    "verified", "already_applied"),
                "exact_list_row_once": len(exact) == 1,
                "same_name_row_once": len(same_name) == 1,
                "db_exact_agent_once": len(agent_rows) == 1,
                "db_same_name_once": len(name_rows) == 1,
                "db_audit_once": len(audit_rows) == 1,
                "ui_card_once_after_reload": card_count_after_reload == 1,
                "ui_student_badge": "student" in maturity_text.lower(),
                "db_student": (
                    agent_row is not None
                    and str(agent_row.get("status") or "").lower() == "student"),
                "no_promotion": (
                    agent_row is not None
                    and str(agent_row.get("status") or "").lower() == "student"),
                "no_scheduler_config": (
                    schedule_value in (None, "", "null", "{}", "None")),
                "no_provider_host_requested": not any(
                    marker in host.lower()
                    for host in external_hosts for marker in PROVIDER_HOST_MARKERS),
                "network_boundary_external_blocked": bool(
                    (result["network_boundary"] or {}).get("external_blocked")),
            })

            failing = [key for key, value in result["controls"].items()
                       if value is not True]
            result["scheduler_note"] = (
                "the custom Hire sends an inactive empty schedule_config and "
                "run_isolated.launch_server launches with ENABLE_SCHEDULER=false; "
                "exactly one agent row/audit and one POST are the duplicate check")
            result["failing_controls"] = failing
            result["status"] = "PASS" if not failing else "FAIL"
            if failing:
                result["errors"].append(f"failing controls: {failing}")

            result["screenshots"] = [
                str(p.relative_to(out)) for p in sorted(out.glob("*.png"))]
            browser.close()
    except Exception as exc:  # noqa: BLE001 - reported as a failed join
        result["status"] = "ERROR"
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        try:
            if client is not None:
                client.close()
        except Exception:
            pass
        for proc in (frontend_proc, server_proc):
            if proc is not None:
                C5.terminate_proc(proc)
        try:
            result["runners_after"] = WSG.list_runners()
        except Exception:
            pass
        result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        (out / "browser_custom_hire_join.json").write_text(
            json.dumps(result, indent=2, default=str) + "\n")
        print(json.dumps({
            "status": result["status"],
            "world": result["world"],
            "agent_id": (result.get("api", {}).get("creation", {}) or {}).get(
                "agent_id"),
            "controls": result.get("controls"),
            "errors": result.get("errors"),
            "out": str(out),
        }, indent=2, default=str))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
