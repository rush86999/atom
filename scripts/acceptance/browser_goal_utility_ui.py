#!/usr/bin/env python3
"""Prepared ordinary-UI episode for the existing GOAL-02 utility surface.

PREPARATION ONLY (root owns the actual browser episode)
=======================================================
This driver does not launch a world, browser, backend, frontend, app model or
provider by default. ``--preflight`` is safe: it reads Git/source/config and
validates the controlled analytics fixture. ``--execute`` is root-owned and
runs one ordinary UI episode in a fresh marked isolated world.

The episode uses the enabled Activity / Goal Runs detail surface:

  supervisor normal login -> Activity -> one run -> existing utility editor ->
  set target -> two eligible completed histories rank -> failed/unknown
  candidates visibly withheld -> reload/fresh API read -> member normal login
  -> read-only target/ranking -> supervisor clear -> no target/ranking.

The only seeded history is an explicitly labelled CONTROLLED ANALYTICS FIXTURE:
two achieved GoalRun rows with fixed metric counts, one failed row and one
achieved row with unknown (negative) metric evidence. It is not completed agent
work, not a model outcome and not a fabricated UI response. The target is
created only through the existing public supervisor API/UI; no target or winner
is written to the database by the fixture. Goal creation and target set/clear
use the existing public authorized routes. Member and supervisor log in through
the real form; no token/cookie seeding.

Reused existing infrastructure (no new engine):
  * ``backend/scripts/orchestration_acceptance/run_isolated.py``
    (build_world/launch_server/storage guard hooks)
  * ``backend/scripts/orchestration_acceptance/case5_browser_recovery.py``
    (start_frontend_copy/NetWatch)
  * ``backend/scripts/orchestration_acceptance/browser_verify.py``
    (ui_login, real form)
  * ``scripts/acceptance/browser_agent_job_wait.py``
    (source proof/world/health/API/screenshot/DB readback helpers)
  * the existing ``GoalRunService`` and ``GoalService`` for fixture history and
    ranking readback.

Out of scope: source upload/answer, Generic model calls, downloads, live
provider/account/credential/send/spend, install/deploy, PostgreSQL, multi-worker,
soak and full TASK-WAIT-01/whole-app acceptance. No model decision quality is
claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.orchestration_acceptance import run_isolated as R  # noqa: E402


def _load_d3():
    path = REPO / "scripts" / "acceptance" / "browser_agent_job_wait.py"
    spec = importlib.util.spec_from_file_location("browser_agent_job_wait", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D3 = _load_d3()

ADMIN_EMAIL = D3.ADMIN_EMAIL
MEMBER_EMAIL = "goal-utility-member@example.test"
GOAL_TITLE = "[FIXTURE] Utility ranking analytics — not model work"
GOAL_DESCRIPTION = (
    "Controlled ANALYTICS fixture for the ordinary GOAL-02 UI episode. The "
    "GoalRun rows are synthetic history with fixed metric counts, not completed "
    "agent work and not model outcomes."
)
TARGET: Dict[str, Any] = {
    "metric": "human_interventions",
    "direction": "minimize",
    "source": "goal_run",
    "description": "fixture analytics: prefer fewer human interventions",
}
FIXTURE_ROWS: List[Dict[str, Any]] = [
    {
        "fixture_id": "eligible-low",
        "status": "achieved",
        "metrics": {"human_interventions": 2, "steps_executed": 5,
                    "replan_count": 1},
        "expected": "eligible",
    },
    {
        "fixture_id": "eligible-high",
        "status": "achieved",
        "metrics": {"human_interventions": 5, "steps_executed": 8,
                    "replan_count": 2},
        "expected": "eligible",
    },
    {
        "fixture_id": "failed-candidate",
        "status": "failed",
        "metrics": {"human_interventions": 0, "steps_executed": 4,
                    "replan_count": 1},
        "expected": "not_completed",
    },
    {
        "fixture_id": "unknown-candidate",
        "status": "achieved",
        "metrics": {"human_interventions": -1, "steps_executed": 6,
                    "replan_count": 0},
        "expected": "metric_unknown",
    },
]

SOURCE_FILES = [
    "backend/api/goal_routes.py",
    "backend/core/goals/goal_service.py",
    "backend/core/goals/goal_run_router.py",
    "backend/core/goals/goal_run_service.py",
    "backend/core/goals/goal_write_service.py",
    "backend/core/goals/utility_target.py",
    "backend/core/personal_scope.py",
    "backend/core/product_profile.py",
    "frontend-nextjs/lib/goal-run-api.ts",
    "frontend-nextjs/pages/goal-runs/[id].tsx",
    "scripts/acceptance/browser_goal_utility_ui.py",
    "scripts/acceptance/browser_agent_job_wait.py",
    "backend/scripts/orchestration_acceptance/run_isolated.py",
]
FRONTEND_SOURCE_FILES = [
    "frontend-nextjs/lib/goal-run-api.ts",
    "frontend-nextjs/pages/goal-runs/[id].tsx",
]
WORLD_PREFIX = "goal_utility_ui_"
LAUNCHER_FILES = (
    "backend/scripts/orchestration_acceptance/run_isolated.py",
    "backend/scripts/orchestration_acceptance/provider_shim.py",
    "scripts/acceptance/browser_agent_job_wait.py",
)
ACC_DIR = REPO / "docs" / "architecture" / "orchestration_migration" / "acceptance"
FIXTURES_DIR = ACC_DIR / "fixtures"
FIXTURE_CHECKSUMS = FIXTURES_DIR / "SHA256SUMS"
FIXTURE_ENTRY_COUNT = 55
WORLDS_ROOT = BACKEND / "data" / "acceptance_worlds"

LABELS = {
    "fixture_history": (
        "CONTROLLED ANALYTICS FIXTURE: two trusted achieved GoalRun rows with "
        "fixed metric counts plus one failed and one unknown-metric candidate. "
        "This is synthetic history, not completed agent work or model output."),
    "production_boundary": (
        "The existing public goal routes, GoalService/GoalRunService, "
        "goal_write_service CAS, durable GoalObjective/GoalRun rows, normal "
        "login form, Activity navigation and Goal Runs detail UI run in "
        "production code."),
    "not_claimed": [
        "served model or provider quality",
        "general model judgment or prompt quality",
        "that the fixture rows are real agent work",
        "TASK-WAIT-01, source upload/answer, downloads or a Generic model call",
        "live provider/account/credential/send/spend/install/deploy",
        "full application, PostgreSQL, multi-worker or soak acceptance",
    ],
}


class PreflightError(RuntimeError):
    pass


class DriverError(RuntimeError):
    pass


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n",
                    encoding="utf-8")


def _git_bytes(path: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "show", f"HEAD:{path}"],
        capture_output=True, timeout=30)
    if proc.returncode != 0:
        raise PreflightError(f"git show HEAD:{path} failed: "
                             f"{proc.stderr.decode('utf-8', 'replace')[:300]}")
    return proc.stdout


def _git_blob(path: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", f"HEAD:{path}"],
        capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise PreflightError(f"git rev-parse HEAD:{path} failed")
    return proc.stdout.strip()


def _per_file_source_proof() -> Dict[str, Any]:
    files: Dict[str, Any] = {}
    ok = True
    for path in SOURCE_FILES:
        git_blob = _git_bytes(path)
        worktree = REPO / path
        actual = worktree.read_bytes() if worktree.is_file() else b""
        entry = {
            "git_blob": _git_blob(path),
            "git_sha256": _sha256_bytes(git_blob),
            "git_bytes": len(git_blob),
            "worktree_sha256": _sha256_bytes(actual),
            "worktree_bytes": len(actual),
            "matches": bool(actual) and actual == git_blob,
        }
        ok = ok and entry["matches"]
        files[path] = entry
    return {"ok": ok, "files": files}


def _source_proof(expected_sha: Optional[str]) -> Dict[str, Any]:
    source = D3._source_probe(expected_sha)
    per_file = _per_file_source_proof()
    tracked_clean = source.get("tracked_dirty_count") == 0
    backend_clean = source.get("backend_dirty_count") == 0
    expected_ok = (source.get("matches_expected") is not False)
    return {
        **source,
        "tracked_tree_clean": tracked_clean,
        "backend_tree_clean": backend_clean,
        "expected_sha_ok": expected_ok,
        "per_file": per_file,
        "source_proof_ok": bool(
            source.get("head")
            and tracked_clean and backend_clean and expected_ok
            and per_file["ok"]),
    }


def _fixture_proof() -> Dict[str, Any]:
    from core.goals.utility_target import (
        normalize_utility_target, outcome_from_goal_run, rank_trajectories,
    )
    target = normalize_utility_target(TARGET)
    outcomes = []
    for row in FIXTURE_ROWS:
        outcomes.append(outcome_from_goal_run({
            "id": row["fixture_id"],
            "goal_id": "fixture-goal",
            "status": row["status"],
            **row["metrics"],
        }))
    ranking = rank_trajectories(target, outcomes)
    by_id = {entry["id"]: entry for entry in ranking["ranking"]}
    eligible = [entry for entry in ranking["ranking"] if entry["eligible"]]

    def _reason_matches(row: Dict[str, Any], entry: Dict[str, Any]) -> bool:
        if row["expected"] == "eligible":
            return entry["eligible"] is True
        return entry["reason"] == row["expected"]

    reasons_ok = all(
        _reason_matches(row, by_id[row["fixture_id"]])
        for row in FIXTURE_ROWS)
    return {
        "target": target,
        "rows": FIXTURE_ROWS,
        "ranking": ranking,
        "eligible_count": len(eligible),
        "winner": ranking.get("winner"),
        "eligible_ids": [entry["id"] for entry in eligible],
        "withheld": [
            {"id": entry["id"], "reason": entry["reason"]}
            for entry in ranking["ranking"] if not entry["eligible"]
        ],
        "expected_reasons_ok": reasons_ok,
        "winner_expected": "eligible-low",
        "ok": (
            len(eligible) == 2
            and ranking.get("winner") == "eligible-low"
            and reasons_ok
            and len(ranking["ranking"]) == len(FIXTURE_ROWS)
        ),
    }


def _profile_probe() -> Dict[str, Any]:
    try:
        from core.product_profile import (
            active_profile, capability_enabled, route_capability,
        )
        profile = active_profile()
        activity = capability_enabled("activity")
        route = route_capability("/goal-runs")
        tasks = capability_enabled("tasks")
        boards = capability_enabled("boards")
        return {
            "profile": profile,
            "activity_enabled": activity,
            "goal_runs_route": route,
            "goal_runs_enabled": (
                route == "activity" and activity),
            "tasks_enabled": tasks,
            "boards_enabled": boards,
            "core_profile": profile == "core",
            "deferred_not_forced": not tasks and not boards,
            "ok": (
                profile == "core" and activity and route == "activity"
                and not tasks and not boards),
        }
    except Exception as exc:  # noqa: BLE001 - reported, not hidden
        return {"error": f"{type(exc).__name__}: {exc}", "ok": False}


def _world_path(name: str) -> Path:
    return D3._world_path(name)


def _world_name(args: argparse.Namespace, source: Dict[str, Any]) -> str:
    name = args.world or (WORLD_PREFIX + str(source.get("head") or "")[:10])
    if not name.startswith(WORLD_PREFIX):
        raise PreflightError(
            f"--world must start with {WORLD_PREFIX!r}; got {name!r}")
    return name


def _execute_ready(args: argparse.Namespace) -> Dict[str, Any]:
    deps = D3._dependency_probe()
    missing = [
        name for name, present in deps["modules"].items()
        if name in ("httpx", "playwright") and not present
    ]
    if missing:
        raise DriverError(f"missing python modules for --execute: {missing}")
    if not deps["node"]:
        raise DriverError("node is not on PATH")
    if not deps["chrome_app"]:
        raise DriverError(
            "Google Chrome.app not found; the driver never installs a browser")
    if not deps["venv314_python"]:
        raise DriverError(
            "backend/venv314/bin/python is absent; run from the prepared "
            "frozen capture worktree, not the prep-only worktree")
    if not deps["frontend_node_modules"]:
        raise DriverError(
            "frontend-nextjs/node_modules is absent; run from the prepared "
            "capture worktree; no npm install is permitted")
    ports = {p: D3._port_free(p) for p in
             (args.backend_port, args.frontend_port)}
    busy = [p for p, free in ports.items() if not free]
    if busy:
        raise DriverError(f"ports already in use: {busy}")
    return {"dependencies": deps, "ports": {str(k): v for k, v in ports.items()}}


def _build_world(world: Path, source_sha: str) -> Dict[str, Any]:
    build = D3._build_world(world, source_sha)
    marker = {
        "schema": "atom-goal-utility-ui-episode-world-1",
        "kind": "controlled_analytics_fixture",
        "source_sha": source_sha,
        "world": world.name,
        "fixture_history": LABELS["fixture_history"],
        "not_real_model_outcomes": True,
        "created_at": _now(),
    }
    _write_json(world / "GOAL_UTILITY_UI_EPISODE.json", marker)
    readback = json.loads(
        (world / "GOAL_UTILITY_UI_EPISODE.json").read_text(encoding="utf-8"))
    build["marker_path"] = str(world / "GOAL_UTILITY_UI_EPISODE.json")
    build["marker"] = readback
    return build


def _frontend_export_proof(world: Path) -> Dict[str, Any]:
    root = world / "frontend_snapshot"
    files: Dict[str, Any] = {}
    ok = True
    for path in FRONTEND_SOURCE_FILES:
        rel = path.split("frontend-nextjs/", 1)[1]
        exported = root / rel
        git_blob = _git_bytes(path)
        actual = exported.read_bytes() if exported.is_file() else b""
        entry = {
            "path": path,
            "snapshot_path": str(exported),
            "git_sha256": _sha256_bytes(git_blob),
            "snapshot_sha256": _sha256_bytes(actual),
            "matches": bool(actual) and actual == git_blob,
        }
        ok = ok and entry["matches"]
        files[path] = entry
    return {"ok": ok, "files": files}


def _durable_goal(db_path: Path, goal_id: str) -> Dict[str, Any]:
    rows = D3._db_rows(
        db_path,
        "SELECT status, progress, metadata_json, workspace_id FROM goal_objectives WHERE id=?",
        (goal_id,))
    if not rows:
        return {"found": False}
    metadata = D3._json_column(rows[0][2])
    return {
        "found": True,
        "workspace_id": rows[0][3],
        "status": rows[0][0],
        "progress": rows[0][1],
        "utility_target": metadata.get("utility_target"),
    }


def _actor_scope(db_path: Path, public_user: Dict[str, Any]) -> Dict[str, Any]:
    """Bind public identity to the scratch SQL actor, then use Personal scope.

    Bootstrap NULL scope is supported production behavior, not missing
    authority. The public /auth/me endpoint omits tenant_id, so never invent
    it from a response field that is not part of that endpoint's contract.
    """
    from types import SimpleNamespace
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    user_id = str(public_user.get("id") or "")
    rows = D3._db_rows(db_path,
        "SELECT id, workspace_id, tenant_id FROM users WHERE id=?", (user_id,))
    if not user_id or len(rows) != 1:
        raise DriverError("public authenticated identity has no exact SQL actor")
    row = rows[0]
    if public_user.get("workspace_id") != row[1]:
        raise DriverError("public authenticated workspace disagrees with SQL")
    actor = SimpleNamespace(workspace_id=row[1], tenant_id=row[2])
    return {"actor_id": user_id, "raw_workspace_id": row[1],
            "raw_tenant_id": row[2],
            "workspace_id": resolve_workspace_id(actor),
            "tenant_id": resolve_tenant_id(actor),
            "source": "exact public identity + read-only scratch SQL + existing personal_scope resolvers"}


def _create_goal(api: Any) -> Dict[str, Any]:
    response = api.post("/api/goals", json={
        "title": GOAL_TITLE,
        "description": GOAL_DESCRIPTION,
    })
    if response.status_code != 200:
        raise DriverError(
            f"goal create failed: {D3._safe_error_body(response)}")
    body = response.json()
    data = body.get("goal") or (body.get("data") or {}).get("goal") or {}
    if not data.get("id"):
        raise DriverError("goal create returned no id")
    return {
        "status": response.status_code,
        "goal": data,
        "verification": body.get("verification"),
        "operation_id": body.get("operation_id"),
        "audit_id": body.get("audit_id"),
    }


def _api_login_as(port: int, email: str, password: str) -> Tuple[str, Dict[str, Any]]:
    with D3._api_client(port) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": email, "password": password})
    if response.status_code != 200:
        raise DriverError(
            f"login failed for {email} ({response.status_code}): "
            f"{D3._safe_error_body(response)}")
    body = response.json()
    if body.get("two_factor_required"):
        raise DriverError(f"{email} unexpectedly requires 2FA")
    token = str(body.get("access_token") or "")
    if not token:
        raise DriverError(f"{email} login returned no access_token")
    return token, {"status": response.status_code, "token_present": True}


def _seed_member(db_path: Path, password: str) -> Dict[str, Any]:
    """Create a disclosed member fixture in the same workspace, then log in
    through the normal form. This is not a token/cookie seed and grants no
    production authority; the member role is lower-privileged than the admin."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.auth import get_password_hash
    from core.models import User

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with Session() as db:
            admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
            if admin is None:
                raise DriverError("scratch admin row not found for member fixture")
            member = User(
                id="goal-utility-member-fixture",
                email=MEMBER_EMAIL,
                hashed_password=get_password_hash(password),
                first_name="Utility",
                last_name="Member",
                role="member",
                status="active",
                is_active=True,
                tenant_id=admin.tenant_id,
                workspace_id=admin.workspace_id,
            )
            db.add(member)
            db.commit()
            return {
                "user_id": member.id,
                "email": member.email,
                "role": member.role,
                "workspace_id": member.workspace_id,
                "tenant_id": member.tenant_id,
                "fixture": "disclosed member fixture in the scratch admin workspace; normal form login; password not recorded",
            }
    finally:
        engine.dispose()


def _seed_history(db_path: Path, workspace_id: str, tenant_id: str,
                  goal_id: str, created_by: str) -> Dict[str, Any]:
    """Seed controlled analytics GoalRun rows through GoalRunService; the
    target/winner is never written here. Fixed counts are fixture analytics."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.goals.goal_run_service import GoalRunService
    from core.models import GoalRun

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    service = GoalRunService(
        workspace_id=workspace_id, tenant_id=tenant_id,
        session_factory=Session)
    seeded: List[Dict[str, Any]] = []
    try:
        for row in FIXTURE_ROWS:
            created = service.create_run(
                goal_id,
                role="analytics_fixture",
                supervision_mode="shadow",
                created_by=created_by,
            )
            run_id = created["id"]
            service.activate(run_id)
            with Session() as db:
                db_run = db.query(GoalRun).filter(GoalRun.id == run_id).one()
                for key, value in row["metrics"].items():
                    setattr(db_run, key, value)
                db.commit()
            service.transition(run_id, row["status"])
            seeded.append({
                **row,
                "run_id": run_id,
                "role": "analytics_fixture",
                "label": "controlled analytics fixture, not agent work",
            })
    finally:
        engine.dispose()
    return {
        "goal_id": goal_id,
        "rows": seeded,
        "no_target_or_winner_written": True,
        "source": "GoalRunService.create_run/activate/transition + ORM fixture counters",
    }


def _public_utility(api: Any, goal_id: str) -> Dict[str, Any]:
    response = api.get(f"/api/goals/{goal_id}/utility")
    body = response.json() if response.status_code == 200 else {}
    return {
        "status": response.status_code,
        "body": body,
        "target": body.get("target"),
        "ranking": body.get("ranking") or [],
        "winner": body.get("winner"),
        "eligible_count": body.get("eligible_count"),
    }


def _complete_onboarding_if_present(page: Any, api: Any) -> Dict[str, Any]:
    """Observe authoritative onboarding, then finish it through ordinary UI.

    ``Locator.is_visible`` does not wait for a late host fetch. Fresh accounts
    must wait for the wizard rather than racing a fixed delay or swallowing a
    blocked click. Existing completed accounts keep their durable state.
    """
    def status() -> bool:
        response = api.get("/api/onboarding/status")
        if response.status_code != 200:
            raise DriverError("onboarding status unavailable")
        body = response.json()
        data = body.get("data") or body
        value = data.get("onboarding_completed")
        if not isinstance(value, bool):
            raise DriverError("onboarding status missing completion evidence")
        return value

    out = {"wizard_seen": False, "dismissed": False,
           "completion_durable": False}
    welcome = page.get_by_role("heading", name="Welcome to Atom", exact=True)
    if status():
        welcome.wait_for(state="hidden", timeout=30000)
        out["completion_durable"] = True
        return out
    welcome.wait_for(state="visible", timeout=30000)
    out["wizard_seen"] = True
    for _ in range(3):
        page.get_by_role("button", name="Next", exact=True).click()
    page.get_by_role("button", name="Start Automating", exact=True).click()
    welcome.wait_for(state="hidden", timeout=30000)
    deadline = time.monotonic() + 30
    while not status():
        if time.monotonic() >= deadline:
            raise DriverError("onboarding UI closed without durable completion")
        time.sleep(0.2)
    out.update(dismissed=True, completion_durable=True)
    return out


def _open_run_detail(page: Any, fe_base: str, run_id: str) -> None:
    page.goto(f"{fe_base}/goal-runs", wait_until="domcontentloaded",
              timeout=300000)
    D3._wait_selector(page, '[data-testid="goal-runs-page"]', 120000)
    selector = f'a[href="/goal-runs/{run_id}"]'
    D3._wait_selector(page, selector, 120000)
    page.locator(selector).first.click()
    D3._wait_selector(page, '[data-testid="goal-run-detail"]', 120000)
    D3._wait_selector(page, '[data-testid="goal-utility-card"]', 120000)


def _ui_receipt(response: Any) -> Dict[str, Any]:
    try:
        body = response.json()
    except Exception:
        body = {}
    verification = body.get("verification")
    return {
        "status": response.status,
        "verification": verification,
        "verification_status": (
            verification.get("status") if isinstance(verification, dict)
            else None),
        "operation_id": body.get("operation_id"),
        "audit_id": body.get("audit_id"),
        "utility_target": body.get("utility_target"),
        "ok": (
            200 <= response.status < 300
            and isinstance(verification, dict)
            and verification.get("status") == "verified"
            and bool(body.get("operation_id"))
            and bool(body.get("audit_id"))),
    }


def _stop_proc(proc: Any) -> None:
    if proc is None or getattr(proc, "poll", lambda: 0)() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            return
    try:
        proc.wait(timeout=15)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------

def _launcher_paths_probe() -> Dict[str, Any]:
    files = {path: (REPO / path).is_file() for path in LAUNCHER_FILES}
    acc_dir = ACC_DIR.is_dir()
    acc_writable = acc_dir and os.access(ACC_DIR, os.W_OK)
    checksums_present = FIXTURE_CHECKSUMS.is_file()
    worlds_present = WORLDS_ROOT.exists()
    worlds_resolves = bool(
        worlds_present
        and (not WORLDS_ROOT.is_symlink() or WORLDS_ROOT.resolve().is_dir()))
    return {
        "ok": (all(files.values()) and acc_writable and checksums_present
               and worlds_resolves),
        "files": files,
        "acc_dir": str(ACC_DIR),
        "acc_dir_writable": acc_writable,
        "fixtures_checksums_present": checksums_present,
        "worlds_root": str(WORLDS_ROOT),
        "worlds_root_exists": worlds_present,
        "worlds_root_is_symlink": WORLDS_ROOT.is_symlink(),
        "worlds_root_resolves": worlds_resolves,
    }


def _fixture_checksum_probe() -> Dict[str, Any]:
    entries = 0
    checksum_exit = None
    stderr = ""
    if FIXTURE_CHECKSUMS.is_file():
        entries = len([
            line for line in FIXTURE_CHECKSUMS.read_text(
                encoding="utf-8").splitlines() if line.strip()])
        proc = subprocess.run(
            ["shasum", "-a", "256", "-c", "SHA256SUMS"],
            cwd=str(FIXTURES_DIR), capture_output=True, text=True,
            timeout=300)
        checksum_exit = proc.returncode
        stderr = (proc.stderr or "")[-500:]
    return {
        "ok": bool(checksum_exit == 0 and entries == FIXTURE_ENTRY_COUNT),
        "path": str(FIXTURE_CHECKSUMS),
        "sha256": (
            _sha256_file(FIXTURE_CHECKSUMS)
            if FIXTURE_CHECKSUMS.is_file() else ""),
        "entry_count": entries,
        "expected_entry_count": FIXTURE_ENTRY_COUNT,
        "checksum_exit": checksum_exit,
        "stderr": stderr,
    }


def _output_target_probe(target: Path) -> Dict[str, Any]:
    target = target.resolve()
    worlds = WORLDS_ROOT.resolve()
    inside_worlds = target == worlds or worlds in target.parents
    probe = target.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    writable = probe.exists() and os.access(probe, os.W_OK)
    return {
        "ok": (not inside_worlds) and writable,
        "target": str(target),
        "parent": str(target.parent),
        "existing_ancestor": str(probe),
        "existing_ancestor_writable": writable,
        "inside_worlds_root": inside_worlds,
    }


def _storage_readiness_probe() -> Dict[str, Any]:
    try:
        import core.world_storage_guard as WSG
        report = WSG.preflight()
        return {
            "ok": bool(getattr(report, "ok", False)),
            "checks": list(getattr(report, "checks", []) or []),
            "problems": list(getattr(report, "problems", []) or []),
            "worlds_root": str(WORLDS_ROOT),
            "worlds_root_exists": WORLDS_ROOT.exists(),
            "worlds_root_is_symlink": WORLDS_ROOT.is_symlink(),
            "worlds_root_resolves": bool(
                WORLDS_ROOT.exists()
                and (not WORLDS_ROOT.is_symlink()
                     or WORLDS_ROOT.resolve().is_dir())),
            "mkdir_in_preflight": False,
        }
    except Exception as exc:  # noqa: BLE001 - reported, not hidden
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "mkdir_in_preflight": False,
        }


def _run_preflight(args: argparse.Namespace) -> int:
    try:
        ctx = D3._require_scratch_env()
        source = _source_proof(args.expect_source_sha)
        if args.expect_source_sha and not source.get("expected_sha_ok"):
            raise PreflightError(
                f"HEAD {source.get('head')} does not match --expect-source-sha "
                f"{args.expect_source_sha}")
        if not source.get("tracked_tree_clean"):
            raise PreflightError(
                "tracked worktree is dirty; per-file Git source proof is not "
                "a frozen candidate")
        if not source.get("per_file", {}).get("ok"):
            raise PreflightError("per-file Git source proof failed")
        deps = D3._dependency_probe()
        profile = _profile_probe()
        if not profile.get("ok"):
            raise PreflightError(
                "core Activity/Goal Runs profile is not enabled as expected: "
                f"{profile}")
        fixture = _fixture_proof()
        if not fixture.get("ok"):
            raise PreflightError(f"analytics fixture proof failed: {fixture}")
        world_name = _world_name(args, source)
        world = _world_path(world_name)
        world_under_root = (
            world.parent.resolve() == WORLDS_ROOT.resolve())
        if not world_under_root:
            raise PreflightError(
                f"--world {world_name!r} resolves outside the configured "
                f"worlds root {WORLDS_ROOT}")
        ports = {str(p): D3._port_free(p)
                 for p in (args.backend_port, args.frontend_port)}
        storage = D3._storage_probe(world)
        storage_ready = _storage_readiness_probe()
        launcher = _launcher_paths_probe()
        fixtures = _fixture_checksum_probe()
        target = Path(args.report) if args.report else (
            Path(args.out) / "preflight.json" if args.out else None)
        if target is None:
            raise PreflightError("--preflight needs --report or --out")
        output = _output_target_probe(target)
        if not output["ok"]:
            raise PreflightError(
                f"preflight report target is not writable or is inside the "
                f"worlds root: {output}")

        warnings: List[str] = []
        for name, present in deps["modules"].items():
            if not present and name in ("httpx", "playwright", "sqlalchemy",
                                        "fastapi"):
                warnings.append(f"python module missing: {name}")
        if not deps["venv314_python"]:
            warnings.append(
                "backend/venv314/bin/python is absent in this prep worktree; "
                "--execute requires a prepared frozen capture worktree")
        if not deps["frontend_node_modules"]:
            warnings.append(
                "frontend-nextjs/node_modules is absent; --execute requires "
                "the prepared capture worktree; no install is permitted")
        if world.exists():
            warnings.append(
                f"world {world_name!r} already exists; --execute requires a "
                "fresh name and never deletes/rebuilds one")
        if not all(ports.values()):
            warnings.append("backend/frontend port is not free: " + str(ports))
        if storage.get("error"):
            warnings.append(f"storage guard probe: {storage['error']}")
        if not storage_ready.get("ok"):
            warnings.append(
                f"storage readiness probe: {storage_ready.get('problems') or storage_ready.get('error')}")

        checks = {
            "scratch_environment": ctx["scratch_ok"],
            "source_head_recorded": bool(source.get("head")),
            "source_expected_sha_ok": bool(source.get("expected_sha_ok")),
            "tracked_tree_clean": bool(source.get("tracked_tree_clean")),
            "per_file_git_source_proof": bool(
                source.get("per_file", {}).get("ok")),
            "launcher_paths_present": bool(launcher["ok"]),
            "fixture_set_55_verified": bool(fixtures["ok"]),
            "output_parent_writable": bool(output["ok"]),
            "worlds_root_usable": bool(storage_ready["ok"]),
            "dependencies_present": bool(
                deps["venv314_python"] and deps["frontend_node_modules"]
                and deps["node"] and deps["chrome_app"]),
            "analytics_fixture_valid": bool(fixture.get("ok")),
            "core_activity_enabled": bool(profile.get("goal_runs_enabled")),
            "deferred_surfaces_not_forced": bool(
                profile.get("deferred_not_forced")),
            "fresh_marked_world_name": (
                world_name.startswith(WORLD_PREFIX) and not world.exists()),
            "backend_frontend_ports_free": all(ports.values()),
            "storage_guard_configured": not bool(storage.get("error")),
        }
        report = {
            "kind": "goal_utility_ui_preflight",
            "status": "preparation-only",
            "generated_at": _now(),
            "ok": all(checks.values()),
            "checks": checks,
            "labels": LABELS,
            "driver": {
                "path": str(Path(__file__).resolve()),
                "sha256": _sha256_file(Path(__file__).resolve()),
            },
            "source": source,
            "launcher": launcher,
            "fixtures": fixtures,
            "output": output,
            "storage_readiness": storage_ready,
            "fixture": fixture,
            "profile": profile,
            "environment": ctx,
            "dependencies": deps,
            "ports": ports,
            "world": {
                "name": world_name,
                "path": str(world),
                "exists": world.exists(),
                "under_worlds_root": world_under_root,
                "required_prefix": WORLD_PREFIX,
                "required_fresh": True,
            },
            "storage_guard": storage,
            "warnings": warnings,
            "not_exercised": [
                "world build / storage guard acceptance",
                "backend or frontend launch",
                "Playwright browser or ordinary login",
                "seeded GoalRun history or durable GoalObjective readback",
                "supervisor set/clear mutation or member read-only UI",
                "goal status/progress or operation receipt effects",
                "model provider/inference/live account/send/spend/install/deploy",
            ],
            "remaining_inputs": [
                "prepared frozen capture worktree with backend/venv314 and frontend-nextjs/node_modules",
                "unique fresh --world starting goal_utility_ui_",
                "free --backend-port and --frontend-port",
                "admin password source: --admin-password-file (0600) or --provision-admin-password for the scratch world",
                "explicit --execute --expect-source-sha; this preparation does not run it",
            ],
            "exact_preparation_command": (
                "TESTING=1 DATABASE_URL=sqlite:///<fresh>/atom.db "
                "ATOM_DATA_DIR=<fresh>/data ATOM_OFFICE_DIR=<fresh>/office "
                "python3 scripts/acceptance/browser_goal_utility_ui.py "
                "--preflight --expect-source-sha <frozen-sha> --out <report-dir>"),
        }
        target = target.resolve()
        _write_json(target, report)
        print(f"[preflight] ok={report['ok']} report={target}")
        print(f"[preflight] source={source.get('head')} "
              f"files={len(source.get('per_file', {}).get('files', {}))} "
              f"fixture_winner={fixture.get('winner')} "
              f"eligible={fixture.get('eligible_count')}")
        print(f"[preflight] fixtures={fixtures['entry_count']}/"
              f"{fixtures['expected_entry_count']} launcher="
              f"{sum(1 for v in launcher['files'].values() if v)}/"
              f"{len(launcher['files'])}")
        for warning in warnings:
            print(f"[preflight] warning: {warning}")
        return 0 if report["ok"] else 1
    except PreflightError as exc:
        print(f"[preflight] REFUSED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - preparation must fail loud
        print(f"[preflight] ERROR: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 3

def _run_execute(args: argparse.Namespace) -> int:
    if not args.expect_source_sha:
        print("[execute] --expect-source-sha is required", file=sys.stderr)
        return 2
    if not args.out:
        print("[execute] --out is required for the evidence bundle",
              file=sys.stderr)
        return 2
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = _source_proof(args.expect_source_sha)
    _write_json(out / "source.json", source)
    if not source.get("source_proof_ok"):
        print("[execute] source proof failed; refusing to build/launch",
              file=sys.stderr)
        return 2
    world_name = _world_name(args, source)
    world = _world_path(world_name)
    if world.exists():
        print(f"[execute] world {world_name!r} already exists; refusing",
              file=sys.stderr)
        return 2

    scenario: Dict[str, Any] = {
        "kind": "goal_utility_ui_scenario",
        "status": "running",
        "started_at": _now(),
        "labels": LABELS,
        "source": source,
        "fixture": _fixture_proof(),
        "steps": [],
        "checks": {},
        "not_claimed": LABELS["not_claimed"],
    }
    cleanups: List[Tuple[str, Any]] = []
    supervisor_proc = None
    frontend_proc = None

    def step(name: str, checks: Dict[str, Any],
             details: Optional[Dict[str, Any]] = None) -> None:
        ok = bool(checks) and all(value is True for value in checks.values())
        scenario["steps"].append({
            "name": name,
            "status": "PASS" if ok else "FAIL",
            "checks": checks,
            "details": details or {},
            "at": _now(),
        })
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        for key, value in checks.items():
            print(f"    {'ok' if value is True else 'FAIL'} {key}: {value}")
        if not ok:
            raise DriverError(f"scenario check failed: {name}")

    try:
        exec_env = D3._prepare_execute_environment(args)
        ready = _execute_ready(args)
        profile = _profile_probe()
        if not profile.get("ok"):
            raise DriverError(f"core Activity profile is not enabled: {profile}")
        if not scenario["fixture"].get("ok"):
            raise DriverError("analytics fixture proof failed before build")
        os.environ.setdefault(
            "SECRET_KEY", secrets.token_urlsafe(32))
        scenario["driver_environment"] = exec_env
        scenario["ready"] = ready
        scenario["profile_prelaunch"] = profile
        scenario["secret_key"] = "synthetic per-run value (not recorded)"
        step("source_and_fixture_proof", {
            "source_proof_ok": source.get("source_proof_ok") is True,
            "expected_sha_ok": source.get("expected_sha_ok") is True,
            "tracked_tree_clean": source.get("tracked_tree_clean") is True,
            "per_file_match": source.get("per_file", {}).get("ok") is True,
            "fixture_ok": scenario["fixture"].get("ok") is True,
        }, details={"head": source.get("head"),
                    "files": list(source.get("per_file", {}).get("files", {}))})

        build = _build_world(world, source["head"])
        scenario["world_build"] = {
            key: value for key, value in build.items()
            if key not in ("code_manifest", "export_tree", "manifest_doc")
        }
        step("fresh_marked_world_built_once", {
            "manifest_present": Path(build["manifest_path"]).is_file(),
            "fixture_present": Path(build["fixture_path"]).is_file(),
            "marker_present": Path(build["marker_path"]).is_file(),
            "marker_source_matches": (
                build["marker"].get("source_sha") == source["head"]),
            "marker_fixture_labelled": (
                "CONTROLLED ANALYTICS FIXTURE"
                in str(build["marker"].get("fixture_history"))),
            "disk_preflight_ok": bool(
                (build.get("disk_preflight") or {}).get("ok")),
            "preflight_source_matches_frozen": (
                (build.get("preflight") or {}).get("source_revision")
                == source["head"]),
            "export_tree_matches_manifest": (
                build.get("export_tree") == build.get("code_manifest")),
        }, details={"world": str(world), "marker": build["marker"]})

        os.environ["ADDITIONAL_ALLOWED_ORIGINS"] = (
            f"http://localhost:{args.frontend_port},"
            f"http://127.0.0.1:{args.frontend_port}")
        os.environ["ALLOWED_HOSTS"] = (
            f"localhost,127.0.0.1,localhost:{args.backend_port},"
            f"localhost:{args.frontend_port}")
        backend = R.launch_server(args.backend_port, world,
                                  provider_shim=False)
        supervisor_proc = backend
        cleanups.append(("backend", backend))
        run_dir = R.launch_server.last_run_dir
        descriptor = dict(R.launch_server.descriptor)
        db_path = run_dir / "data" / "atom.db"
        health = D3._health(args.backend_port)
        identity = health.get("identity") or {}
        scenario["stack"] = {
            "world": str(world),
            "run_dir": str(run_dir),
            "db_path": str(db_path),
            "backend_port": args.backend_port,
            "frontend_port": args.frontend_port,
            "backend_descriptor": descriptor,
            "health": health,
            "provider_shim": False,
        }
        binding = D3._backend_source_binding(
            frozen_source_sha=source["head"],
            source_head=source["head"],
            preflight=build.get("preflight") or {},
            manifest=build.get("manifest_doc") or {},
            code_manifest=build.get("code_manifest") or {},
            export_tree=build.get("export_tree") or {},
            health_identity=identity,
            descriptor=descriptor,
            world=world,
        )
        scenario["backend_source_binding"] = binding
        step("backend_source_bound", binding["checks"],
             details={"git_blob_files_checked": binding.get(
                 "git_blob_files_checked"),
                 "git_backend_export": binding.get("git_backend_export")})
        step("backend_identity", {
            "health_ok": health.get("status") in (
                None, "healthy", "degraded", "ok"),
            "cwd_is_world_backend_root": (
                Path(str(identity.get("cwd") or "")).resolve()
                == (world / "backend_root").resolve()),
            "db_is_run_db": (
                Path(str(descriptor.get("db_path") or "")).resolve()
                == db_path.resolve()),
            "db_not_live": (
                db_path.resolve() != (BACKEND / "data" / "atom.db").resolve()),
        }, details={"descriptor": descriptor, "health_identity": identity})

        from scripts.orchestration_acceptance import (
            case5_browser_recovery as C5,
            browser_verify as BV,
        )
        frontend_proc = C5.start_frontend_copy(
            args.backend_port, args.frontend_port, world)
        if not frontend_proc:
            raise DriverError("frontend copy failed to start")
        cleanups.append(("frontend", frontend_proc))
        fe_base = f"http://localhost:{args.frontend_port}"
        frontend_proof = _frontend_export_proof(world)
        scenario["frontend"] = {
            "pid": frontend_proc.pid,
            "base": fe_base,
            "snapshot": str(world / "frontend_snapshot"),
            "source_proof": frontend_proof,
        }
        step("frontend_source_bytes_match_git", {
            "source_proof_ok": frontend_proof["ok"],
            "files_checked": len(frontend_proof["files"]) == len(
                FRONTEND_SOURCE_FILES),
        }, details=frontend_proof)

        with D3._api_client(args.backend_port) as profile_api:
            profile_response = profile_api.get("/api/product/profile")
            profile_body = (
                profile_response.json()
                if profile_response.status_code == 200 else {})
        scenario["profile"] = {
            "status": profile_response.status_code,
            "body": profile_body,
            "activity_enabled": bool(
                (profile_body.get("capabilities") or {})
                .get("activity", {}).get("enabled")),
            "tasks_enabled": bool(
                (profile_body.get("capabilities") or {})
                .get("tasks", {}).get("enabled")),
            "boards_enabled": bool(
                (profile_body.get("capabilities") or {})
                .get("boards", {}).get("enabled")),
        }
        step("core_activity_profile_enabled", {
            "profile_core": profile_body.get("profile") == "core",
            "activity_enabled": scenario["profile"]["activity_enabled"],
            "tasks_not_forced": not scenario["profile"]["tasks_enabled"],
            "boards_not_forced": not scenario["profile"]["boards_enabled"],
        }, details=scenario["profile"])

        password, password_meta = D3._password_for_run(
            args, world, db_path, run_dir)
        scenario["admin_password_source"] = password_meta
        supervisor_token, supervisor_login = _api_login_as(
            args.backend_port, ADMIN_EMAIL, password)
        with D3._api_client(args.backend_port, supervisor_token) as api:
            me = api.get("/api/auth/me")
            me_body = me.json() if me.status_code == 200 else {}
            if me.status_code != 200:
                raise DriverError("authenticated public identity read failed")
            actor_scope = _actor_scope(db_path, me_body)
            scenario["supervisor_scope"] = actor_scope
            goal_create = _create_goal(api)
            goal_id = str(goal_create["goal"]["id"])
            scenario["goal"] = {
                **goal_create,
                "goal_id": goal_id,
                "workspace_id": actor_scope["workspace_id"],
                "tenant_id": actor_scope["tenant_id"],
            }
            step("goal_created_through_public_api", {
                "http_2xx": 200 <= goal_create["status"] < 300,
                "goal_id_present": bool(goal_id),
                "effective_workspace_matches_durable_goal": (
                    _durable_goal(db_path, goal_id).get("workspace_id")
                    == actor_scope["workspace_id"]),
                "no_utility_target_written": (
                    goal_create["goal"].get("utility_target") is None),
                "receipt_present": bool(goal_create.get("operation_id")),
            }, details={"goal": goal_create.get("goal"),
                        "verification": goal_create.get("verification")})

            member_password = secrets.token_urlsafe(18)
            member = _seed_member(db_path, member_password)
            scenario["member_fixture"] = member
            history = _seed_history(
                db_path, actor_scope["workspace_id"],
                actor_scope["tenant_id"], goal_id,
                created_by=str(me_body.get("id") or "goal-utility-supervisor"))
            scenario["fixture_history"] = history
            expected = scenario["fixture"]
            step("controlled_analytics_history_seeded", {
                "four_rows": len(history["rows"]) == 4,
                "two_eligible": expected.get("eligible_count") == 2,
                "winner_expected": expected.get("winner") == "eligible-low",
                "withheld_expected": sorted(
                    item["reason"] for item in expected.get("withheld", [])
                ) == ["metric_unknown", "not_completed"],
                "no_target_written": _durable_goal(
                    db_path, goal_id).get("utility_target") is None,
                "rows_are_fixture_labelled": all(
                    row.get("role") == "analytics_fixture"
                    for row in history["rows"]),
            }, details=history)

            before = _durable_goal(db_path, goal_id)
            scenario["goal_before_target"] = before

            run_id = history["rows"][0]["run_id"]
            member_token, _ = _api_login_as(
                args.backend_port, member["email"], member_password)
            with D3._api_client(args.backend_port, member_token) as member_api:
                member_read_before = _public_utility(member_api, goal_id)

            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=not args.headed, channel="chrome")
                try:
                    context = browser.new_context(
                        viewport={"width": 1440, "height": 1000},
                        accept_downloads=False)
                    page = context.new_page()
                    ui_mutations: List[Dict[str, Any]] = []

                    def _on_request(request: Any) -> None:
                        url = str(request.url)
                        path = D3._path_of(url)
                        if request.method in ("PUT", "DELETE") and (
                                "/api/goals/" in path
                                and path.rstrip("/").endswith("/utility")):
                            ui_mutations.append({
                                "method": request.method,
                                "path": path,
                            })

                    page.on("request", _on_request)
                    login = BV.ui_login(
                        page, fe_base, ADMIN_EMAIL, password)
                    if not login.get("ok"):
                        try:
                            page.wait_for_url(
                                lambda url: "/login" not in str(url),
                                timeout=30000)
                            login["ok"] = "/login" not in page.url
                            login["landed_url"] = page.url
                        except Exception:
                            pass
                    step("supervisor_ordinary_ui_login", {
                        "attempted": login.get("attempted") is True,
                        "landed_off_login": login.get("ok") is True,
                        "token_present_after_login": bool(
                            login.get("token_present_after_login")),
                    }, details=login)
                    D3._screenshot(page, out, "00_supervisor_login.png")
                    onboarding = _complete_onboarding_if_present(page, api)
                    scenario["supervisor_onboarding"] = onboarding

                    _open_run_detail(page, fe_base, run_id)
                    step("activity_goal_run_detail_opened", {
                        "detail_visible": page.locator(
                            '[data-testid="goal-run-detail"]').count() == 1,
                        "utility_card_visible": page.locator(
                            '[data-testid="goal-utility-card"]').count() == 1,
                        "no_target_state": page.locator(
                            '[data-testid="goal-utility-no-target"]').count() == 1,
                        "editor_visible": page.locator(
                            '[data-testid="goal-utility-editor"]').count() == 1,
                        "fixture_goal_title_visible": (
                            "Utility ranking analytics" in page.locator(
                                '[data-testid="run-goal-heading"]').inner_text()),
                    }, details={"run_id": run_id, "onboarding": onboarding})
                    D3._screenshot(page, out, "01_activity_no_target.png")

                    page.locator(
                        '[data-testid="goal-utility-metric"]'
                    ).select_option("human_interventions")
                    page.locator(
                        '[data-testid="goal-utility-direction"]'
                    ).select_option("minimize")
                    page.locator(
                        '[data-testid="goal-utility-description"]'
                    ).fill(TARGET["description"])
                    with page.expect_response(
                            lambda response: (
                                response.request.method == "PUT"
                                and "/api/goals/" in D3._path_of(response.url)
                                and D3._path_of(response.url).rstrip("/").endswith(
                                    "/utility")),
                            timeout=120000) as put_info:
                        page.locator('[data-testid="goal-utility-save"]').click()
                    put_response = put_info.value
                    put_receipt = _ui_receipt(put_response)
                    scenario["set_target_receipt"] = put_receipt
                    step("supervisor_sets_existing_target_via_ui", {
                        "http_2xx": put_receipt["ok"],
                        "verified": put_receipt["verification_status"] == "verified",
                        "operation_id": bool(put_receipt["operation_id"]),
                        "audit_id": bool(put_receipt["audit_id"]),
                        "one_put_request": len([
                            m for m in ui_mutations if m["method"] == "PUT"]) == 1,
                    }, details=put_receipt)
                    D3._wait_selector(page, '[data-testid="goal-utility-ranking"]',
                                      60000)
                    eligible_rows = page.locator(
                        '[data-testid="goal-utility-entry"]')
                    withheld_text = page.locator(
                        '[data-testid="goal-utility-withheld"]').inner_text()
                    target_text = page.locator(
                        '[data-testid="goal-utility-target"]').inner_text()
                    step("ui_ranking_two_eligible_and_withheld", {
                        "target_visible": "Human interventions" in target_text,
                        "two_eligible_rows": eligible_rows.count() == 2,
                        "winner_badge": page.locator(
                            '[data-testid="goal-utility-winner"]').count() == 1,
                        "failed_withheld": "not completed" in withheld_text.lower(),
                        "unknown_withheld": "metric unknown" in withheld_text.lower(),
                        "fixture_labelled": "ANALYTICS fixture"
                        in page.locator(
                            '[data-testid="goal-run-detail"]').inner_text(),
                    }, details={"target_text": target_text,
                                "withheld": withheld_text})
                    D3._screenshot(page, out, "02_supervisor_ranking.png")

                    public_after = _public_utility(api, goal_id)
                    durable_after = _durable_goal(db_path, goal_id)
                    expected_eligible_ids = [
                        row["run_id"] for row in history["rows"]
                        if row["expected"] == "eligible"]
                    ranked_ids = [
                        entry.get("id") for entry in public_after["ranking"]
                        if entry.get("eligible")]
                    step("public_api_and_durable_readback_after_set", {
                        "api_target_matches": public_after["target"] == TARGET,
                        "eligible_count_two": public_after["eligible_count"] == 2,
                        "winner_is_fixture_low": public_after["winner"]
                        == history["rows"][0]["run_id"],
                        "eligible_ids_match": set(ranked_ids)
                        == set(expected_eligible_ids),
                        "durable_target_matches": durable_after.get(
                            "utility_target") == TARGET,
                        "status_unchanged": durable_after.get("status")
                        == before.get("status"),
                        "progress_unchanged": durable_after.get("progress")
                        == before.get("progress"),
                    }, details={"public": public_after,
                                "durable": durable_after})

                    page.reload(wait_until="domcontentloaded", timeout=120000)
                    D3._wait_selector(page, '[data-testid="goal-utility-card"]',
                                      120000)
                    D3._wait_selector(page, '[data-testid="goal-utility-ranking"]',
                                      120000)
                    with D3._api_client(args.backend_port, supervisor_token) as fresh_api:
                        fresh = _public_utility(fresh_api, goal_id)
                    step("reload_and_fresh_read_persist_target", {
                        "ui_ranking_after_reload": page.locator(
                            '[data-testid="goal-utility-entry"]').count() == 2,
                        "fresh_api_target_matches": fresh["target"] == TARGET,
                        "fresh_api_winner_matches": fresh["winner"]
                        == public_after["winner"],
                    }, details={"fresh": fresh})
                    D3._screenshot(page, out, "03_supervisor_reload.png")

                    # Member read-only, same goal/workspace, normal form login.
                    member_context = browser.new_context(
                        viewport={"width": 1440, "height": 1000},
                        accept_downloads=False)
                    member_page = member_context.new_page()
                    member_login = BV.ui_login(
                        member_page, fe_base, member["email"], member_password)
                    if not member_login.get("ok"):
                        try:
                            member_page.wait_for_url(
                                lambda url: "/login" not in str(url),
                                timeout=30000)
                            member_login["ok"] = "/login" not in member_page.url
                            member_login["landed_url"] = member_page.url
                        except Exception:
                            pass
                    with D3._api_client(args.backend_port, member_token) as member_api:
                        scenario["member_onboarding"] = _complete_onboarding_if_present(
                            member_page, member_api)
                    _open_run_detail(member_page, fe_base, run_id)
                    member_target = member_page.locator(
                        '[data-testid="goal-utility-target"]').inner_text()
                    member_ranked = member_page.locator(
                        '[data-testid="goal-utility-entry"]').count()
                    step("member_ordinary_ui_read_only", {
                        "login_ok": member_login.get("ok") is True,
                        "card_visible": member_page.locator(
                            '[data-testid="goal-utility-card"]').count() == 1,
                        "target_visible": "Human interventions" in member_target,
                        "two_ranked_rows": member_ranked == 2,
                        "readonly_note": member_page.locator(
                            '[data-testid="goal-utility-readonly"]').count() == 1,
                        "no_save_button": member_page.locator(
                            '[data-testid="goal-utility-save"]').count() == 0,
                        "no_clear_button": member_page.locator(
                            '[data-testid="goal-utility-clear"]').count() == 0,
                    }, details={"login": member_login})
                    D3._screenshot(member_page, out, "04_member_readonly.png")
                    with D3._api_client(
                            args.backend_port, member_token) as member_api:
                        member_mutation = member_api.put(
                            f"/api/goals/{goal_id}/utility",
                            json=TARGET)
                    step("member_api_mutation_refused", {
                        "http_403": member_mutation.status_code == 403,
                        "target_unchanged_after_refusal": _public_utility(
                            api, goal_id)["target"] == TARGET,
                    }, details={"status": member_mutation.status_code})
                    member_context.close()

                    # Supervisor clear through the same ordinary UI.
                    with page.expect_response(
                            lambda response: (
                                response.request.method == "DELETE"
                                and "/api/goals/" in D3._path_of(response.url)
                                and D3._path_of(response.url).rstrip("/").endswith(
                                    "/utility")),
                            timeout=120000) as delete_info:
                        page.locator('[data-testid="goal-utility-clear"]').click()
                    delete_response = delete_info.value
                    delete_receipt = _ui_receipt(delete_response)
                    scenario["clear_target_receipt"] = delete_receipt
                    step("supervisor_clears_target_via_ui", {
                        "http_2xx": delete_receipt["ok"],
                        "verified": delete_receipt["verification_status"] == "verified",
                        "operation_id": bool(delete_receipt["operation_id"]),
                        "audit_id": bool(delete_receipt["audit_id"]),
                        "one_delete_request": len([
                            m for m in ui_mutations if m["method"] == "DELETE"]) == 1,
                    }, details=delete_receipt)
                    D3._wait_selector(
                        page, '[data-testid="goal-utility-no-target"]', 60000)
                    cleared = _public_utility(api, goal_id)
                    cleared_durable = _durable_goal(db_path, goal_id)
                    step("clear_removes_target_and_ranking_truthfully", {
                        "ui_no_target": page.locator(
                            '[data-testid="goal-utility-no-target"]').count() == 1,
                        "ui_ranking_gone": page.locator(
                            '[data-testid="goal-utility-ranking"]').count() == 0,
                        "api_target_none": cleared["target"] is None,
                        "api_ranking_empty": cleared["ranking"] == [],
                        "durable_target_none": cleared_durable.get(
                            "utility_target") is None,
                        "status_unchanged": cleared_durable.get("status")
                        == before.get("status"),
                        "progress_unchanged": cleared_durable.get("progress")
                        == before.get("progress"),
                    }, details={"public": cleared, "durable": cleared_durable})
                    D3._screenshot(page, out, "05_supervisor_cleared.png")
                    context.close()
                finally:
                    browser.close()
        scenario["status"] = "passed"
        scenario["finished_at"] = _now()
        scenario["ui_mutations"] = ui_mutations if 'ui_mutations' in locals() else []
        scenario["operation_receipts"] = {
            "set": scenario.get("set_target_receipt"),
            "clear": scenario.get("clear_target_receipt"),
            "one_each": (
                scenario.get("set_target_receipt") is not None
                and scenario.get("clear_target_receipt") is not None),
        }
        _write_json(out / "scenario.json", scenario)
        print(f"[execute] PASS evidence={out / 'scenario.json'}")
        return 0
    except Exception as exc:  # noqa: BLE001 - preserve the failure
        scenario["status"] = "failed"
        scenario["error"] = f"{type(exc).__name__}: {exc}"
        scenario["finished_at"] = _now()
        _write_json(out / "scenario.json", scenario)
        print(f"[execute] FAIL: {scenario['error']}", file=sys.stderr)
        return 1
    finally:
        for label, proc in reversed(cleanups):
            try:
                _stop_proc(proc)
            except Exception:
                pass


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Prepared ordinary-UI GOAL-02 utility episode")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true",
                      help="read-only preparation checks; no launch")
    mode.add_argument("--execute", action="store_true",
                      help="root-owned single UI episode")
    ap.add_argument("--expect-source-sha", default=None,
                    help="explicit frozen Git source SHA")
    ap.add_argument("--world", default=None,
                    help=f"fresh world name; must start {WORLD_PREFIX!r}")
    ap.add_argument("--backend-port", type=int, default=8041)
    ap.add_argument("--frontend-port", type=int, default=3141)
    ap.add_argument("--out", default=None,
                    help="evidence output directory")
    ap.add_argument("--report", default=None,
                    help="preflight report path (or use --out/preflight.json)")
    ap.add_argument("--headed", action="store_true",
                    help="show the browser during root-owned --execute")
    ap.add_argument("--admin-password-file", default=None,
                    help="0600 file containing the scratch admin password")
    ap.add_argument("--provision-admin-password", action="store_true",
                    help="provision a scratch admin through core.admin_bootstrap")
    args = ap.parse_args()

    if args.preflight:
        return _run_preflight(args)
    return _run_execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
