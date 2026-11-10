import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

os.environ.setdefault(
    "ATOM_WORLD_STORAGE_PATHS",
    "/Users/rushiparikh/projects/atom/backend/config",
)
REPO = Path("/private/tmp/atom-web-graduation-qualification-join-20261110")
os.environ.setdefault("ACC_WORKTREE", str(REPO))
os.environ.setdefault("NEXTAUTH_SECRET", secrets.token_urlsafe(32))
sys.path.insert(0, str(REPO / "backend"))

from scripts.orchestration_acceptance import run_isolated as R
from playwright.sync_api import sync_playwright
import httpx

WORLD = R.BACKEND / "data" / "acceptance_worlds" / "grad_ordinary_ui_6da_1794315411_4d66ed51fe"
RUN_DIR = sorted((WORLD / "runs").glob("run-*"))[-1]
AGENT = "4cca507d-fe5c-43e6-bf2c-cd158f32bd62"
CANVAS = "507e8792-6976-4cd5-840e-fea764f94af0"
ACTION = "9a19f509-86a2-4770-a016-4f913e25542d"
NONCE = "4d66ed51fe"
OUT = Path("/private/tmp/atom-graduation-ordinary-ui-continuation-1794315411")
OUT.mkdir(parents=True, exist_ok=True)
DB = RUN_DIR / "data" / "atom.db"
result = {
    "status": "STARTED",
    "world": WORLD.name,
    "run_dir": str(RUN_DIR),
    "agent_id": AGENT,
    "canvas_id": CANVAS,
    "action_id": ACTION,
    "seeded_training_sessions": [],
    "api": {},
    "ui": {},
    "db": {},
    "requests": [],
    "errors": [],
}


def seed_training_sessions():
    con = sqlite3.connect(str(DB), timeout=30)
    try:
        admin_id = con.execute(
            "SELECT id FROM users WHERE email='admin@example.com'").fetchone()[0]
        agent_name = con.execute(
            "SELECT name FROM agent_registry WHERE id=?", (AGENT,)).fetchone()[0]
        existing = con.execute(
            "SELECT COUNT(*) FROM training_sessions WHERE agent_id=?",
            (AGENT,)).fetchone()[0]
        confidence = con.execute(
            "SELECT confidence_score FROM agent_registry WHERE id=?",
            (AGENT,)).fetchone()[0]
        if confidence is None or float(confidence) < 0.5:
            with con:
                con.execute(
                    "UPDATE agent_registry SET confidence_score=0.62 WHERE id=?",
                    (AGENT,))
            result["seeded_agent_confidence"] = {
                "before": confidence, "after": 0.62,
                "note": "controlled exposure precondition; not model competence",
            }
        if existing:
            return [], admin_id
        started = datetime.now(timezone.utc) - timedelta(days=1)
        seeded = []
        with con:
            for index in range(3):
                proposal_id = f"{NONCE}-training-proposal-{index}"
                session_id = f"{NONCE}-training-session-{index}"
                ts = (started + timedelta(hours=index)).strftime(
                    "%Y-%m-%d %H:%M:%S.%f")
                done = (started + timedelta(hours=index, minutes=45)).strftime(
                    "%Y-%m-%d %H:%M:%S.%f")
                con.execute(
                    """
                    INSERT INTO agent_proposals
                    (id, tenant_id, user_id, agent_id, agent_name, title,
                     description, proposal_type, proposal_data, status,
                     reversible, created_at)
                    VALUES (?, 'default', ?, ?, ?, ?, ?, 'action', '{}',
                            'executed', 1, ?)
                    """,
                    (
                        proposal_id, admin_id, AGENT, agent_name,
                        f"Controlled training {index} for {NONCE}",
                        "Controlled exposure precondition; not model competence",
                        ts,
                    ),
                )
                con.execute(
                    """
                    INSERT INTO training_sessions
                    (id, tenant_id, proposal_id, agent_id, agent_name, status,
                     started_at, completed_at, duration_seconds, supervisor_id,
                     tasks_completed, total_tasks, performance_score,
                     errors_count, confidence_boost, promoted_to_intern,
                     outcomes)
                    VALUES (?, 'default', ?, ?, ?, 'completed', ?, ?, 2700,
                            ?, 10, 10, 1.0, 0, 0.12, 0, ?)
                    """,
                    (
                        session_id, proposal_id, AGENT, agent_name, ts, done,
                        admin_id,
                        json.dumps({"fixture": NONCE, "controlled": True}),
                    ),
                )
                seeded.append(session_id)
        return seeded, admin_id
    finally:
        con.close()


server_proc = None
frontend_proc = None
try:
    R.require_storage_ready()
    seeded, admin_id = seed_training_sessions()
    result["seeded_training_sessions"] = seeded
    result["admin_id"] = admin_id

    server_proc = R.launch_server(8067, WORLD, reuse_run_dir=RUN_DIR)
    backend_base = "http://127.0.0.1:8067"
    frontend_base = "http://127.0.0.1:3000"
    pw = (WORLD / "backend_root" / "logs" / "bootstrap_admin_password.txt").read_text().strip()

    snapshot = WORLD / "frontend_snapshot"
    if not snapshot.exists():
        raise RuntimeError("retained frontend snapshot is missing")
    env = dict(os.environ)
    env.update({
        "NEXT_PUBLIC_API_URL": backend_base,
        "PYTHON_API_SERVICE_BASE_URL": backend_base,
        "NEXTAUTH_URL": frontend_base,
        "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
        "NODE_OPTIONS": "--max-old-space-size=4096",
    })
    log = (OUT / "frontend-continuation.log").open("ab")
    frontend_proc = subprocess.Popen(
        ["node", "node_modules/next/dist/bin/next", "dev", "--webpack",
         "-p", "3000"],
        cwd=str(snapshot), env=env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    deadline = time.time() + 240
    while time.time() < deadline:
        if frontend_proc.poll() is not None:
            raise RuntimeError("frontend exited during continuation")
        try:
            r = httpx.get(frontend_base + "/login", timeout=5, trust_env=False)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        raise RuntimeError("frontend did not answer /login")

    login = httpx.post(
        backend_base + "/api/auth/login",
        json={"username": "admin@example.com", "password": pw},
        timeout=30, trust_env=False,
    )
    token = login.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    sd = httpx.get(
        backend_base + "/api/maturity/training/self-directed",
        headers=headers, timeout=30, trust_env=False,
    )
    sd_body = sd.json()
    sd_agent = next(
        (a for a in (sd_body.get("agents") or [])
         if a.get("agent_id") == AGENT), None)
    result["api"]["self_directed_after_seed"] = sd_agent
    if not sd_agent or not (sd_agent.get("readiness") or {}).get("ready"):
        raise RuntimeError("self-directed readiness still not ready after seed")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(viewport={"width": 1440, "height": 1200})
        page = context.new_page()
        page.set_default_timeout(120000)
        dialogs = []
        page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
        page.goto(frontend_base + "/login", wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        page.fill('input[type="email"]', "admin@example.com")
        page.fill('input[type="password"]', pw)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        if "/login" in page.url:
            raise RuntimeError("continuation UI login failed")
        page.wait_for_timeout(2500)
        if page.get_by_role("dialog").count():
            page.mouse.click(5, 5)
            page.wait_for_timeout(1000)
            result["ui"]["onboarding_dismissed"] = True

        page.goto(
            frontend_base + f"/canvas/{CANVAS}?agent_id={AGENT}&side=training",
            wait_until="domcontentloaded",
        )
        page.wait_for_selector('[data-testid="training-panel"]')
        page.wait_for_timeout(2500)
        if page.get_by_role("dialog").count():
            page.mouse.click(5, 5)
            page.wait_for_timeout(1000)
            result["ui"]["onboarding_dismissed_on_canvas"] = True
        page.locator('[data-testid="training-refresh"]').click()
        page.wait_for_function(
            """() => {
                const s = document.querySelector(
                    '[data-testid="qualification-state"] strong');
                return s && s.getAttribute('title') === 'valid';
            }""")
        page.wait_for_timeout(1500)
        result["ui"]["valid_state"] = {
            "text": page.locator(
                '[data-testid="qualification-state"] strong').inner_text(),
            "raw_title": page.locator(
                '[data-testid="qualification-state"] strong').get_attribute("title"),
            "pending_copy": page.get_by_text(
                "Review pending in Approvals.").count(),
        }
        page.screenshot(path=str(OUT / "training-qualified-continuation.png"),
                        full_page=True)
        promote = page.locator(
            '[data-testid="self-directed-promote-button"], '
            '[data-testid="promote-agent-button"]')
        page.wait_for_selector(
            '[data-testid="self-directed-promote-button"], '
            '[data-testid="promote-agent-button"]')
        enabled = [i for i in range(promote.count())
                   if promote.nth(i).is_enabled()]
        result["ui"]["promote_controls"] = {
            "count": promote.count(),
            "enabled": enabled,
        }
        if not enabled:
            raise RuntimeError("no enabled promote control after training seed")
        with page.expect_response(
                lambda r: "/api/episodes/graduation/promote" in r.url
                and r.request.method == "POST") as info:
            promote.nth(enabled[0]).click()
        response = info.value
        result["requests"].append({
            "step": "promote_retained_agent",
            "method": "POST",
            "path": urlparse(response.url).path,
            "status": response.status,
            "body": response.request.post_data_json,
            "response": response.json(),
        })
        if response.status != 200:
            raise RuntimeError(f"promotion failed: {response.status}")
        page.wait_for_timeout(2500)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="training-panel"]')
        page.wait_for_timeout(2500)
        badge = page.locator('[data-testid="training-tier-badge"]')
        result["ui"]["fresh_reload"] = {
            "tier_badge": badge.inner_text() if badge.count() else None,
            "state_title": page.locator(
                '[data-testid="qualification-state"] strong').get_attribute("title")
            if page.locator(
                '[data-testid="qualification-state"] strong').count() else None,
            "pending_copy": page.get_by_text(
                "Review pending in Approvals.").count(),
        }
        page.screenshot(path=str(OUT / "training-promoted-continuation.png"),
                        full_page=True)
        context.close()
        browser.close()

    con = sqlite3.connect(str(DB), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        agent = con.execute(
            "SELECT status,last_exam_id,promotion_count FROM agent_registry "
            "WHERE id=?", (AGENT,)).fetchone()
        history = con.execute(
            "SELECT id,from_level,to_level,exam_id,promoted_by,justification "
            "FROM promotion_history WHERE agent_id=?", (AGENT,)).fetchall()
        notifications = con.execute(
            "SELECT id,user_id,tenant_id,workspace_id,metadata_json "
            "FROM notifications WHERE user_id=?", (admin_id,)).fetchall()
        exams = con.execute(
            "SELECT COUNT(*) FROM graduation_exams WHERE agent_id=?",
            (AGENT,)).fetchone()[0]
    finally:
        con.close()
    grad_notifs = [
        dict(row) for row in notifications
        if (json.loads(row["metadata_json"] or "{}").get("notification_type")
            == "agent_graduated")
        and (json.loads(row["metadata_json"] or "{}").get("agent_id") == AGENT)
    ]
    result["db"] = {
        "agent": dict(agent) if agent else None,
        "history": [dict(row) for row in history],
        "exam_count": exams,
        "graduation_notifications": grad_notifs,
    }
    if not agent or agent["status"] != "intern":
        raise RuntimeError("agent did not reach INTERN")
    if agent["last_exam_id"] != f"qualification:{ACTION}":
        raise RuntimeError("last_exam_id mismatch")
    if len(history) != 1 or str(history[0]["exam_id"]) != f"qualification:{ACTION}":
        raise RuntimeError("promotion history mismatch")
    if len(grad_notifs) != 1:
        raise RuntimeError("graduation notification missing")
    result["status"] = "PASS"
except Exception as exc:
    result["status"] = "FAIL"
    result["errors"].append(f"{type(exc).__name__}: {exc}")
finally:
    try:
        if frontend_proc is not None:
            import os as _os
            import signal as _signal
            try:
                _os.killpg(_os.getpgid(frontend_proc.pid), _signal.SIGTERM)
            except Exception:
                frontend_proc.terminate()
    except Exception:
        pass
    try:
        if server_proc is not None:
            R.stop_server(server_proc)
    except Exception:
        pass
    (OUT / "journey-continuation.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "status": result["status"],
        "agent_id": AGENT,
        "canvas_id": CANVAS,
        "action_id": ACTION,
        "seeded_training_sessions": result["seeded_training_sessions"],
        "errors": result["errors"],
    }, indent=2))
