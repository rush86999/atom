#!/usr/bin/env python3
"""One bounded ordinary-UI graduation qualification episode.

This is an acceptance driver, not a product change and not a new world
launcher. It reuses the existing infrastructure:

  * backend/scripts/orchestration_acceptance/run_isolated.py
    (storage guard, immutable world export, fixture DB, server launch)
  * backend/scripts/orchestration_acceptance/case5_browser_recovery.py
    (real-directory frontend copy + Next dev + dynamic-route probe)
  * backend/scripts/orchestration_acceptance/browser_verify.py
    (real login form helper)

The episode is deliberately narrow:

  normal admin login -> onboarding -> unique STUDENT agent (public API) ->
  controlled task/output DB records -> Agents "Teach" (ordinary UI canvas
  create/attach) -> TrainingPanel shows missing assessment + no promote ->
  explicit evidence checkbox + "Request qualification review" -> one pending
  HITL row -> Approvals UI shows task/output/rubric -> Approve -> valid
  qualified receipt -> TrainingPanel promote control -> INTERN -> fresh reload
  and DB/Notification readback.

Controlled fixture disclosure: the agent's completed task/context and actual
durable output records are seeded by this driver. They are a controlled
fixture, NOT fresh model competence. No GraduationExam, HITL approval,
qualification receipt, last_exam_id, promoted status or policy exception is
seeded. The agent starts STUDENT with only experience preconditions.

No product code is edited. No model/provider/email/live-DB action is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

# MUST be set before importing the guard/launcher.
os.environ.setdefault(
    "ATOM_WORLD_STORAGE_PATHS",
    "/Users/rushiparikh/projects/atom/backend/config",
)
REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
os.environ.setdefault("ACC_WORKTREE", str(REPO))
# Ephemeral NextAuth web-session secret for this isolated frontend copy.
# Never printed, never written to evidence.
os.environ.setdefault("NEXTAUTH_SECRET", secrets.token_urlsafe(32))
sys.path.insert(0, str(BACKEND))

from scripts.orchestration_acceptance import run_isolated as R  # noqa: E402
from scripts.orchestration_acceptance import case5_browser_recovery as C5  # noqa: E402
from scripts.orchestration_acceptance import browser_verify as BV  # noqa: E402
from core import world_storage_guard as WSG  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

import httpx  # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


def api_json(response: httpx.Response) -> dict:
    body = response.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def seed_controlled_work(db_path: Path, admin_id: str, agent_id: str,
                         nonce: str) -> dict:
    """Seed only preconditions: completed task/output records.

    Deliberately does NOT insert graduation_exams, hitl_actions, receipts,
    last_exam_id, promoted status or any policy exception.
    """
    started = datetime.now(timezone.utc) - timedelta(days=1)
    exec_ids, episode_ids = [], []
    con = sqlite3.connect(str(db_path), timeout=30)
    try:
        with con:
            for index in range(10):
                exec_id = f"{nonce}-exec-{index:02d}"
                episode_id = f"{nonce}-ep-{index:02d}"
                exec_ids.append(exec_id)
                episode_ids.append(episode_id)
                ts = (started + timedelta(minutes=index)).strftime(
                    "%Y-%m-%d %H:%M:%S.%f")
                done = (started + timedelta(minutes=index + 5)).strftime(
                    "%Y-%m-%d %H:%M:%S.%f")
                con.execute(
                    """
                    INSERT INTO agent_executions
                    (id, agent_id, tenant_id, workspace_id, status,
                     input_summary, result_summary, output_summary,
                     triggered_by, started_at, completed_at, duration_seconds,
                     metadata_json, human_intervention_count)
                    VALUES (?, ?, 'default', 'default', 'completed',
                            ?, ?, ?, 'manual', ?, ?, 300,
                            ?, 0)
                    """,
                    (
                        exec_id, agent_id,
                        f"Controlled held-out task {index} for {nonce}",
                        f"Controlled actual durable output {index} for {nonce}",
                        f"Controlled actual durable output {index} for {nonce}",
                        ts, done,
                        json.dumps({"fixture": nonce, "controlled": True}),
                    ),
                )
                con.execute(
                    """
                    INSERT INTO agent_episodes
                    (id, agent_id, tenant_id, workspace_id, execution_id,
                     task_description, maturity_at_time, constitutional_score,
                     human_intervention_count, confidence_score, outcome,
                     success, step_efficiency, status, metadata_json,
                     started_at, completed_at, duration_seconds, access_count,
                     importance_score, decay_score, canvas_ids, topics,
                     entities, feedback_ids, canvas_action_count)
                    VALUES (?, ?, 'default', 'default', ?, ?, 'student', 0.9,
                            0, 0.62, 'success', 1, 1.0, 'completed', ?, ?, ?,
                            300, 0, 0.5, 1.0, '[]', '[]', '[]', '[]', 0)
                    """,
                    (
                        episode_id, agent_id, exec_id,
                        f"Controlled held-out work {index} for {nonce}",
                        json.dumps({"fixture": nonce, "controlled": True}),
                        ts, done,
                    ),
                )
            artifact_id = f"{nonce}-artifact-1"
            segment_id = f"{nonce}-segment-1"
            con.execute(
                """
                INSERT INTO artifacts
                (id, tenant_id, workspace_id, agent_id, name, type, content,
                 metadata_json, version, is_locked, author_id)
                VALUES (?, 'default', 'default', ?, ?, 'markdown', ?, ?, 1, 0, ?)
                """,
                (
                    artifact_id, agent_id,
                    f"Controlled actual artifact {nonce}",
                    f"Controlled actual artifact output for {nonce}",
                    json.dumps({"fixture": nonce, "controlled": True}),
                    admin_id,
                ),
            )
            con.execute(
                """
                INSERT INTO episode_segments
                (id, episode_id, segment_type, sequence_order, content,
                 source_type, source_id)
                VALUES (?, ?, 'execution', 1, ?, 'execution', ?)
                """,
                (
                    segment_id, episode_ids[0],
                    f"Controlled actual execution segment for {nonce}",
                    exec_ids[0],
                ),
            )
    finally:
        con.close()
    return {
        "execution_ids": exec_ids,
        "episode_ids": episode_ids,
        "artifact_id": artifact_id,
        "segment_id": segment_id,
        "note": "controlled fixture preconditions only; not model competence",
    }


def find_card(page, agent_id: str, needle: str):
    cards = page.locator("div.rounded-xl")
    short = agent_id[:8]
    for index in range(cards.count()):
        card = cards.nth(index)
        try:
            text = card.inner_text(timeout=2000)
        except Exception:
            continue
        if needle in text and short in text:
            return card
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--world", default=None)
    ap.add_argument("--backend-port", type=int, default=8061)
    ap.add_argument("--frontend-port", type=int, default=3161)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex[:10]
    world_name = args.world or f"grad_ordinary_ui_6da_{int(time.time())}_{nonce}"
    world = R.BACKEND / "data" / "acceptance_worlds" / world_name
    result = {
        "status": "STARTED",
        "world": world_name,
        "nonce": nonce,
        "ports": {"backend": args.backend_port, "frontend": args.frontend_port},
        "source_head": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True, text=True).stdout.strip(),
        "storage_preflight": None,
        "runners_before": None,
        "runners_after": None,
        "seeded": None,
        "ui": {},
        "api": {},
        "db": {},
        "requests": [],
        "screenshots": [],
        "errors": [],
    }
    server_proc = None
    frontend_proc = None
    try:
        R.require_storage_ready()
        report = WSG.preflight()
        result["storage_preflight"] = report.summary()
        if not report.ok:
            raise RuntimeError(f"storage preflight failed: {report.summary()}")
        result["runners_before"] = WSG.list_runners()
        C5.ensure_port_free(args.backend_port)
        C5.ensure_port_free(args.frontend_port)
        if world.exists():
            raise RuntimeError(f"refusing to reuse existing world: {world}")

        R.build_world.snapshot_working_tree = True
        R.build_world.full_dev_db = False
        R.build_world(world, refreeze_db=True)
        pre = R.preflight(world)
        result["world_preflight"] = pre

        server_proc = R.launch_server(args.backend_port, world)
        run_dir = R.launch_server.last_run_dir
        result["run_dir"] = str(run_dir)
        result["db_path"] = str(run_dir / "data" / "atom.db")
        backend_base = f"http://127.0.0.1:{args.backend_port}"
        frontend_base = f"http://127.0.0.1:{args.frontend_port}"

        password_path = world / "backend_root" / "logs" / "bootstrap_admin_password.txt"
        deadline = time.time() + 60
        while time.time() < deadline and not (
                password_path.exists() and password_path.stat().st_size):
            time.sleep(0.5)
        if not password_path.exists():
            raise RuntimeError("bootstrap admin password file was not created")
        admin_password = password_path.read_text().strip()
        if not admin_password:
            raise RuntimeError("bootstrap admin password is empty")

        frontend_proc = C5.start_frontend_copy(
            args.backend_port, args.frontend_port, world)
        if frontend_proc is None:
            raise RuntimeError("frontend copy did not become usable")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel="chrome")
            context = browser.new_context(
                viewport={"width": 1440, "height": 1200})
            page = context.new_page()
            page.set_default_timeout(120000)
            dialogs = []
            page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))

            login = BV.ui_login(
                page, frontend_base, "admin@example.com", admin_password)
            result["ui"]["login"] = {
                "ok": login.get("ok"),
                "landed_path": urlparse(login.get("landed_url") or "").path,
                "token_present": login.get("token_present_after_login"),
            }
            if not login.get("ok"):
                raise RuntimeError(f"UI login failed: {login}")

            # Complete the ordinary onboarding dialog if it opened.
            page.goto(f"{frontend_base}/dashboard", wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            onboarding_seen = page.get_by_text("Welcome to Atom", exact=True).count() > 0
            result["ui"]["onboarding_seen"] = onboarding_seen
            if onboarding_seen:
                finished = False
                for _ in range(6):
                    finish = page.get_by_role(
                        "button", name="Start Automating", exact=True)
                    if finish.count():
                        finish.first.click()
                        page.wait_for_timeout(1800)
                        finished = page.get_by_text(
                            "Welcome to Atom", exact=True).count() == 0
                        break
                    nxt = page.get_by_role("button", name="Next", exact=True)
                    if nxt.count() == 0:
                        break
                    nxt.first.click()
                    page.wait_for_timeout(900)
                if not finished:
                    # Ordinary dialog dismissal: the wizard's own Escape/onClose
                    # path sets the session-scoped dismissal key.
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(800)
            result["ui"]["onboarding_completed"] = (
                page.get_by_text("Welcome to Atom", exact=True).count() == 0)

            token = page.evaluate(
                "() => localStorage.getItem('auth_token') || localStorage.getItem('token')")
            if not token:
                raise RuntimeError("login left no auth token in localStorage")
            client = httpx.Client(
                base_url=backend_base,
                headers={"Authorization": f"Bearer {token}"},
                timeout=60, trust_env=False,
            )

            me = api_json(client.get("/api/users/me"))
            admin_id = str(me.get("id") or "")
            if not admin_id:
                raise RuntimeError("could not read current admin id")
            result["admin_id"] = admin_id

            agent_name = f"Graduation UI Candidate {nonce}"
            created = client.post("/api/agents/custom", json={
                "name": agent_name,
                "description": "Controlled ordinary-UI qualification candidate",
                "category": "operations",
                "configuration": {"learning": {"role": "operations", "log": []}},
            })
            if created.status_code != 201:
                raise RuntimeError(
                    f"agent create failed: {created.status_code} {created.text[:200]}")
            agent_id = str(api_json(created)["agent_id"])
            result["agent_id"] = agent_id
            result["agent_name"] = agent_name

            result["seeded"] = seed_controlled_work(
                run_dir / "data" / "atom.db", admin_id, agent_id, nonce)

            readiness = client.get(
                f"/api/episodes/graduation/readiness/{agent_id}",
                params={"target_maturity": "INTERN"})
            readiness_data = api_json(readiness)
            result["api"]["initial_readiness"] = {
                "status": readiness.status_code,
                "ready": readiness_data.get("ready"),
                "score": readiness_data.get("score"),
                "gaps": readiness_data.get("gaps"),
                "assessment": readiness_data.get("assessment"),
                "assessment_evidence_count": len(
                    readiness_data.get("assessment_evidence") or []),
            }
            if readiness.status_code != 200:
                raise RuntimeError(f"readiness failed: {readiness.text[:300]}")
            if readiness_data.get("ready") is not True:
                raise RuntimeError("controlled experience preconditions are not ready")
            if (readiness_data.get("assessment") or {}).get("state") != "unresolved_missing":
                raise RuntimeError("initial assessment is not missing")
            if not readiness_data.get("assessment_evidence"):
                raise RuntimeError("no reviewable evidence bundles")

            # Agents page: the unique card and the ordinary Teach control.
            page.goto(f"{frontend_base}/agents", wait_until="domcontentloaded")
            page.wait_for_selector(f'[data-testid="agent-card-{agent_name}"]')
            guide_button = page.locator(
                '[data-testid="active-agent-maturity-guide-button"]')
            result["ui"]["maturity_guide_button"] = {
                "present": guide_button.count() > 0,
                "disabled_without_run": (
                    guide_button.count() > 0 and guide_button.first.is_disabled()),
                "note": "AgentMaturityGuide needs an active run; no model run was made",
            }
            page.screenshot(path=str(out / "agents-page.png"), full_page=True)
            result["screenshots"].append("agents-page.png")
            if page.get_by_role("dialog").count():
                page.keyboard.press("Escape")
                page.wait_for_timeout(800)
                result["ui"]["leftover_dialog_dismissed"] = True

            page.locator(
                f'[data-testid="agent-teach-button-{agent_id}"]').click()
            page.wait_for_url("**/canvas/**", timeout=120000)
            page.wait_for_selector('[data-testid="training-panel"]')
            page.wait_for_selector('[data-testid="qualification-state"]')
            canvas_id = page.url.split("/canvas/")[1].split("?")[0]
            result["canvas_id"] = canvas_id
            result["ui"]["canvas_url_path"] = urlparse(page.url).path
            page.wait_for_timeout(2000)

            state = page.locator('[data-testid="qualification-state"] strong')
            result["ui"]["initial_state"] = {
                "text": state.inner_text(),
                "raw_title": state.get_attribute("title"),
            }
            if result["ui"]["initial_state"]["raw_title"] != "unresolved_missing":
                raise RuntimeError(
                    f"initial UI state is not missing: {result['ui']['initial_state']}")
            promote_buttons = page.locator(
                '[data-testid="self-directed-promote-button"], '
                '[data-testid="promote-agent-button"]')
            result["ui"]["initial_promote"] = {
                "count": promote_buttons.count(),
                "any_enabled": any(
                    promote_buttons.nth(i).is_enabled()
                    for i in range(promote_buttons.count())),
            }
            if result["ui"]["initial_promote"]["any_enabled"]:
                raise RuntimeError("promotion is enabled before qualification")
            page.screenshot(
                path=str(out / "training-missing.png"), full_page=True)
            result["screenshots"].append("training-missing.png")

            picker = page.locator('[data-testid="qualification-evidence-picker"]')
            page.wait_for_selector(
                '[data-testid="qualification-evidence-picker"]')
            checkboxes = picker.locator('input[type="checkbox"]')
            if checkboxes.count() < 1:
                raise RuntimeError("no evidence checkbox in the picker")
            selected_label = checkboxes.first.locator(
                "xpath=ancestor::label").inner_text()
            checkboxes.first.check()
            request_button = page.locator(
                '[data-testid="request-qualification-review"]')
            page.wait_for_function(
                """() => {
                    const b = document.querySelector(
                        '[data-testid="request-qualification-review"]');
                    return b && !b.disabled;
                }""")
            with page.expect_response(
                    lambda r: "/api/episodes/graduation/qualification/request" in r.url
                    and r.request.method == "POST") as review_info:
                request_button.click()
            review_response = review_info.value
            review_body = review_response.json()
            result["requests"].append({
                "step": "request_qualification_review",
                "method": "POST",
                "path": urlparse(review_response.url).path,
                "status": review_response.status,
                "body": review_response.request.post_data_json,
                "response": review_body,
            })
            if review_response.status != 200:
                raise RuntimeError(
                    f"qualification request failed: {review_response.status}")
            page.wait_for_selector("text=Review pending in Approvals.")
            result["ui"]["pending_state"] = {
                "text": page.locator(
                    '[data-testid="qualification-state"] strong').inner_text(),
                "raw_title": page.locator(
                    '[data-testid="qualification-state"] strong').get_attribute(
                        "title"),
                "selected_label": selected_label,
                "request_visible": page.locator(
                    '[data-testid="request-qualification-review"]').count(),
            }
            page.screenshot(
                path=str(out / "training-pending.png"), full_page=True)
            result["screenshots"].append("training-pending.png")

            # Exact one pending qualification HITL for this agent.
            pending = client.get("/api/agents/approvals/pending")
            pending_rows = pending.json()
            if isinstance(pending_rows, dict):
                pending_rows = pending_rows.get("data") or []
            matches = [
                row for row in pending_rows
                if row.get("agent_id") == agent_id
                and row.get("action_type") == "agent_qualification_review"
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"expected one pending qualification HITL, got {len(matches)}")
            action = matches[0]
            action_id = str(action["id"])
            params = action.get("params") or {}
            result["hitl_action_id"] = action_id
            result["api"]["pending_action"] = {
                "id": action_id,
                "target_level": params.get("target_level"),
                "policy_revision": params.get("policy_revision"),
                "policy_digest_present": bool(params.get("policy_digest")),
                "rubric_version": params.get("rubric_version"),
                "rubric_ids": [
                    item.get("id") for item in params.get("rubric_criteria") or []],
                "evidence_refs": params.get("evidence_refs"),
            }
            if params.get("target_level") != "INTERN":
                raise RuntimeError("pending action target is not INTERN")
            if not params.get("policy_revision") or not params.get("policy_digest"):
                raise RuntimeError("pending action lacks policy binding")
            if not params.get("rubric_criteria"):
                raise RuntimeError("pending action lacks rubric criteria")

            with sqlite3.connect(str(run_dir / "data" / "atom.db")) as db:
                status_after_request = db.execute(
                    "SELECT status, last_exam_id FROM agent_registry WHERE id=?",
                    (agent_id,)).fetchone()
            result["db"]["after_request"] = {
                "status": status_after_request[0],
                "last_exam_id": status_after_request[1],
            }
            if status_after_request[0] != "student" or status_after_request[1]:
                raise RuntimeError("agent changed before review approval")

            # Ordinary Approvals UI: inspect the exact action and approve.
            page.goto(f"{frontend_base}/approvals", wait_until="domcontentloaded")
            page.wait_for_selector("text=Capability qualification review")
            card = find_card(page, agent_id, "Capability qualification review")
            if card is None:
                raise RuntimeError("qualification card not found in Approvals UI")
            card_text = card.inner_text()
            result["ui"]["approvals_card"] = {
                "contains_action_id": action_id in card_text,
                "contains_task": "Task:" in card_text,
                "contains_output": "Output:" in card_text,
                "contains_rubric": "Frozen rubric" in card_text,
                "text_excerpt": card_text[:1200],
            }
            if not all([
                result["ui"]["approvals_card"]["contains_task"],
                result["ui"]["approvals_card"]["contains_output"],
                result["ui"]["approvals_card"]["contains_rubric"],
            ]):
                raise RuntimeError("Approvals card lacks task/output/rubric")
            page.screenshot(
                path=str(out / "approvals-qualification.png"), full_page=True)
            result["screenshots"].append("approvals-qualification.png")

            approve_button = card.get_by_role("button", name="Approve", exact=True)
            with page.expect_response(
                    lambda r: f"/api/agents/approvals/{action_id}" in r.url
                    and r.request.method == "POST") as approve_info:
                approve_button.click()
            approve_response = approve_info.value
            result["requests"].append({
                "step": "approve_qualification_review",
                "method": "POST",
                "path": urlparse(approve_response.url).path,
                "status": approve_response.status,
                "body": approve_response.request.post_data_json,
                "response": approve_response.json(),
            })
            if approve_response.status != 200:
                raise RuntimeError(
                    f"approval failed: {approve_response.status}")
            page.wait_for_timeout(2000)

            with sqlite3.connect(str(run_dir / "data" / "atom.db")) as db:
                db.row_factory = sqlite3.Row
                hitl = db.execute(
                    "SELECT id,status,action_type,params FROM hitl_actions "
                    "WHERE id=?", (action_id,)).fetchone()
                exams = db.execute(
                    "SELECT id,passed,promoted,target_level,current_level,metadata_json "
                    "FROM graduation_exams WHERE agent_id=?", (agent_id,)).fetchall()
                agent_row = db.execute(
                    "SELECT status,last_exam_id,promotion_count FROM agent_registry "
                    "WHERE id=?", (agent_id,)).fetchone()
            result["db"]["after_approval"] = {
                "hitl_status": hitl["status"] if hitl else None,
                "exam_count": len(exams),
                "exam": dict(exams[0]) if exams else None,
                "agent": dict(agent_row) if agent_row else None,
            }
            if not hitl or hitl["status"] != "approved":
                raise RuntimeError("HITL action was not approved")
            if len(exams) != 1:
                raise RuntimeError(f"expected one receipt, got {len(exams)}")
            exam_meta = json.loads(exams[0]["metadata_json"] or "{}")
            receipt_id = str(exams[0]["id"])
            result["receipt_id"] = receipt_id
            if exam_meta.get("receipt_kind") != "capability_qualification":
                raise RuntimeError("receipt kind is not capability_qualification")
            if exam_meta.get("candidate_capability_qualified") is not True:
                raise RuntimeError("receipt does not claim qualification")
            if str(exam_meta.get("review_action_id")) != action_id:
                raise RuntimeError("receipt review action does not match")
            if agent_row["status"] != "student":
                raise RuntimeError("agent moved before promotion")
            if agent_row["last_exam_id"] != receipt_id:
                raise RuntimeError("receipt pointer was not recorded")

            # Return to the ordinary canvas UI and refetch the assessment.
            page.goto(page.url.split("/approvals")[0] + f"/canvas/{canvas_id}"
                      f"?agent_id={agent_id}&side=training",
                      wait_until="domcontentloaded")
            page.wait_for_selector('[data-testid="training-panel"]')
            page.locator('[data-testid="training-refresh"]').click()
            page.wait_for_function(
                """() => {
                    const s = document.querySelector(
                        '[data-testid="qualification-state"] strong');
                    return s && s.getAttribute('title') === 'valid';
                }""")
            result["ui"]["valid_state"] = {
                "text": page.locator(
                    '[data-testid="qualification-state"] strong').inner_text(),
                "raw_title": page.locator(
                    '[data-testid="qualification-state"] strong').get_attribute(
                        "title"),
                "pending_copy": page.get_by_text(
                    "Review pending in Approvals.").count(),
                "review_required_copy": page.get_by_text(
                    "Capability qualification review required before promotion.").count(),
            }
            if result["ui"]["valid_state"]["pending_copy"]:
                raise RuntimeError("valid receipt still shows pending copy")
            if result["ui"]["valid_state"]["review_required_copy"]:
                raise RuntimeError("valid receipt still shows review-required copy")
            promote = page.locator(
                '[data-testid="self-directed-promote-button"], '
                '[data-testid="promote-agent-button"]')
            page.wait_for_selector(
                '[data-testid="self-directed-promote-button"], '
                '[data-testid="promote-agent-button"]')
            enabled = [i for i in range(promote.count())
                       if promote.nth(i).is_enabled()]
            if not enabled:
                raise RuntimeError("no enabled promote control after valid receipt")
            page.screenshot(
                path=str(out / "training-qualified.png"), full_page=True)
            result["screenshots"].append("training-qualified.png")

            with page.expect_response(
                    lambda r: "/api/episodes/graduation/promote" in r.url
                    and r.request.method == "POST") as promote_info:
                promote.nth(enabled[0]).click()
            promote_response = promote_info.value
            promote_body = promote_response.json()
            result["requests"].append({
                "step": "promote",
                "method": "POST",
                "path": urlparse(promote_response.url).path,
                "status": promote_response.status,
                "body": promote_response.request.post_data_json,
                "response": promote_body,
            })
            if promote_response.status != 200:
                raise RuntimeError(
                    f"promotion failed: {promote_response.status} {promote_body}")
            page.wait_for_timeout(2500)

            with sqlite3.connect(str(run_dir / "data" / "atom.db")) as db:
                db.row_factory = sqlite3.Row
                agent_after = db.execute(
                    "SELECT status,last_exam_id,promotion_count FROM agent_registry "
                    "WHERE id=?", (agent_id,)).fetchone()
                history = db.execute(
                    "SELECT id,from_level,to_level,exam_id,promoted_by,justification "
                    "FROM promotion_history WHERE agent_id=?",
                    (agent_id,)).fetchall()
                notifications = db.execute(
                    "SELECT id,user_id,tenant_id,workspace_id,metadata_json "
                    "FROM notifications WHERE user_id=?", (admin_id,)).fetchall()
                exams_after = db.execute(
                    "SELECT COUNT(*) FROM graduation_exams WHERE agent_id=?",
                    (agent_id,)).fetchone()[0]
            graduation_notifications = [
                dict(row) for row in notifications
                if (json.loads(row["metadata_json"] or "{}")
                    .get("notification_type") == "agent_graduated")
                and (json.loads(row["metadata_json"] or "{}")
                     .get("agent_id") == agent_id)
            ]
            result["db"]["after_promotion"] = {
                "agent": dict(agent_after) if agent_after else None,
                "history": [dict(row) for row in history],
                "exam_count": exams_after,
                "graduation_notifications": graduation_notifications,
            }
            if not agent_after or agent_after["status"] != "intern":
                raise RuntimeError("agent did not reach INTERN")
            if agent_after["last_exam_id"] != receipt_id:
                raise RuntimeError("last_exam_id does not match receipt")
            if len(history) != 1:
                raise RuntimeError(f"expected one promotion history, got {len(history)}")
            if str(history[0]["exam_id"]) != receipt_id:
                raise RuntimeError("promotion history exam_id does not match receipt")
            if len(graduation_notifications) != 1:
                raise RuntimeError(
                    f"expected one graduation notification, got "
                    f"{len(graduation_notifications)}")
            result["notification_id"] = graduation_notifications[0]["id"]
            result["promotion_history_id"] = history[0]["id"]

            # Fresh UI reload must show the same durable result.
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector('[data-testid="training-panel"]')
            page.wait_for_timeout(2500)
            tier_badge = page.locator('[data-testid="training-tier-badge"]')
            result["ui"]["fresh_reload"] = {
                "tier_badge": tier_badge.inner_text() if tier_badge.count() else None,
                "state_title": page.locator(
                    '[data-testid="qualification-state"] strong').get_attribute(
                        "title") if page.locator(
                            '[data-testid="qualification-state"] strong').count() else None,
                "pending_copy": page.get_by_text(
                    "Review pending in Approvals.").count(),
            }
            if "intern" not in (result["ui"]["fresh_reload"]["tier_badge"] or "").lower():
                raise RuntimeError("fresh UI reload did not show INTERN")
            if result["ui"]["fresh_reload"]["state_title"] not in (None, "valid"):
                raise RuntimeError("fresh UI reload state is not valid")
            if result["ui"]["fresh_reload"]["pending_copy"]:
                raise RuntimeError("fresh UI reload shows stale pending copy")
            page.screenshot(
                path=str(out / "training-promoted.png"), full_page=True)
            result["screenshots"].append("training-promoted.png")

            context.close()
            browser.close()

        result["runners_after"] = WSG.list_runners()
        result["status"] = "PASS"
        return 0
    except Exception as exc:
        result["status"] = "FAIL"
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        try:
            if frontend_proc is not None:
                C5._terminate(frontend_proc)
        except Exception:
            pass
        try:
            if server_proc is not None:
                R.stop_server(server_proc)
        except Exception:
            pass
        try:
            result["runners_after"] = WSG.list_runners()
        except Exception:
            pass
        (out / "journey.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({
            "status": result["status"],
            "world": world_name,
            "agent_id": result.get("agent_id"),
            "canvas_id": result.get("canvas_id"),
            "action_id": result.get("hitl_action_id"),
            "receipt_id": result.get("receipt_id"),
            "notification_id": result.get("notification_id"),
            "errors": result["errors"],
        }, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
