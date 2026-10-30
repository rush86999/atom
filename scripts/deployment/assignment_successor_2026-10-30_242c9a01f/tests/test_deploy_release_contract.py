"""Failure controls for the reversible deployment transaction."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
KIT = Path(__file__).resolve().parents[1]
DEPLOY = KIT / "deploy_release.sh"


def _identity():
    return {
        "schema": "atom-assignment-successor-release-1",
        "release_tag": "assignment-successor-2026-10-29-a96484324",
        "release_commit": "ef95ceb3194ec92c51e64941d7bb364c0b8b0e75",
        "tested_runtime_commit": "a96484324",
        "product_paths": ["backend", "frontend-nextjs"],
        "product_tree_sha256": "12060bee618e7a58a98324f682d39077c144c19a6fb7d22d77de8179237dbb9e",
        "frontend_build_id": "test-build",
        "api_port": 18071,
        "frontend_port": 13130,
        "audience": "single_user",
        "pilot_email": "admin@example.com",
        "outbound_scope": "draft_and_approval_only",
        "send_authorized": False,
        "topology": "one_worker_process_per_assignment",
    }


def _fake_kit(root: Path):
    scripts = root / "current" / "scripts"
    scripts.mkdir(parents=True)
    tool = scripts / "release_tool.py"
    tool.write_text(r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
state_file = Path(os.environ["FAKE_STATE_FILE"])
scenario = os.environ.get("FAKE_SCENARIO", "success")
state = json.loads(state_file.read_text()) if state_file.is_file() else {"calls": []}
args = sys.argv[1:]
command = next((a for a in args if a in {"approval-check","preflight","backup","stop","start","status","rollback"}), "")
state["calls"].append({"command": command, "args": args})
def save():
    state_file.write_text(json.dumps(state))
if command == "approval-check":
    save(); sys.exit(0)
if command == "preflight":
    save(); sys.exit(1 if scenario == "preflight_fail" else 0)
if command == "backup":
    save(); sys.exit(1 if scenario == "backup_fail" else 0)
if command == "stop":
    state["stop_calls"] = state.get("stop_calls", 0) + 1
    save()
    if scenario == "partial_stop_fail":
        sys.exit(1)
    if scenario == "unexpected_exit_after_shutdown":
        sys.exit(9)
    state["previous_stopped"] = True; save(); sys.exit(0)
if command == "start":
    if scenario == "candidate_start_fail":
        save(); sys.exit(1)
    if scenario == "rollback_fail" and not state.get("rollback_called"):
        save(); sys.exit(1)
    if scenario == "rollback_fail" and state.get("rollback_called"):
        save(); sys.exit(1)
    state["candidate_started"] = True; save(); sys.exit(0)
if command == "rollback":
    state["rollback_called"] = True; save()
    sys.exit(1 if scenario == "rollback_fail" else 0)
if command == "status":
    save(); sys.exit(0)
save(); sys.exit(0)
''')
    freshness = scripts / "check_freshness.py"
    freshness.write_text(
        "import json,os,sys\n"
        "state_file=os.environ['FAKE_STATE_FILE']\n"
        "from pathlib import Path\n"
        "state=json.loads(Path(state_file).read_text()) if Path(state_file).is_file() else {'calls':[]}\n"
        "state['calls'].append({'command':'freshness','args':sys.argv[1:]})\n"
        "Path(state_file).write_text(json.dumps(state))\n"
        "scenario=os.environ.get('FAKE_SCENARIO')\n"
        "phase=sys.argv[sys.argv.index('--phase')+1] if '--phase' in sys.argv else 'preflight'\n"
        "fail=(scenario=='freshness_stale' or (scenario=='freshness_post_backup_stale' and phase=='post-backup') or (scenario=='freshness_pre_activation_stale' and phase=='pre-activation'))\n"
        "sys.exit(1 if fail else 0)\n")
    for name, body in {
        "smoke_auth.py": "import json,os,sys\nstate=os.environ.get('FAKE_SCENARIO','success')\nif state=='auth_fail': sys.exit(1)\nout=sys.argv[sys.argv.index('--out-dir')+1]\nos.makedirs(out,exist_ok=True)\nopen(out+'/auth-smoke.json','w').write(json.dumps({'status':'passed'}))\n",
        "smoke_assignment.py": "import json,os,sys\nstate=os.environ.get('FAKE_SCENARIO','success')\nrestart='--compare-to' in sys.argv\nif state=='assignment_fail' or (state=='restart_fail' and restart): sys.exit(1)\nout=sys.argv[sys.argv.index('--out')+1]\nopen(out,'w').write(json.dumps({'ok':True,'snapshot':{}}))\n",
        "smoke_fresh_assignment.py": "import json,os,sys\nstate=os.environ.get('FAKE_SCENARIO','success')\nif state=='fresh_fail': sys.exit(1)\nout=sys.argv[sys.argv.index('--out')+1]\nopen(out,'w').write(json.dumps({'ok':True,'fresh':{}}))\n",
    }.items():
        (scripts / name).write_text(body)
    (root / "config").mkdir(parents=True)
    (root / "config" / "env.release").write_text(
        "API_PORT=18071\nFE_PORT=13130\n")
    (root / "config" / "rehearsal_admin_password").write_text("test\n")
    (root / "RELEASE_IDENTITY.json").write_text(json.dumps(_identity(), indent=2))


def _run(root: Path, scenario: str, *, mode: str = "rehearsal",
         receipt: Path | None = None):
    env = dict(os.environ)
    env.update({
        "RELEASE_ROOT": str(root),
        "RELEASE_PYTHON": sys.executable,
        "FAKE_SCENARIO": scenario,
        "FAKE_STATE_FILE": str(root / "state.json"),
        "ATOM_SMOKE_PASSWORD_FILE": str(root / "config" / "rehearsal_admin_password"),
    })
    if receipt is not None:
        env["DEPLOY_RECEIPT_PATH"] = str(receipt)
    args = ["bash", str(DEPLOY)]
    if mode == "rehearsal":
        args.append("--rehearsal")
    return subprocess.run(args, env=env, capture_output=True, text=True,
                          timeout=60)


def _state(root: Path):
    return json.loads((root / "state.json").read_text())


def test_pre_shutdown_failures_leave_service_alone(tmp_path):
    for scenario in ("preflight_fail", "backup_fail"):
        root = tmp_path / scenario
        _fake_kit(root)
        result = _run(root, scenario)
        assert result.returncode != 0
        assert not (root / "state.json").is_file() or \
            all(c["command"] != "stop" for c in _state(root)["calls"])
        assert not _state(root).get("rollback_called")


def test_stale_freshness_refuses_before_shutdown(tmp_path):
    root = tmp_path / "stale"
    _fake_kit(root)
    result = _run(root, "freshness_stale")
    assert result.returncode != 0
    state = _state(root)
    assert state["calls"][-1]["command"] == "freshness"
    assert all(c["command"] != "stop" for c in state["calls"])
    assert not state.get("rollback_called")


def test_post_backup_stale_refuses_before_shutdown(tmp_path):
    root = tmp_path / "post-backup-stale"
    _fake_kit(root)
    result = _run(root, "freshness_post_backup_stale")
    assert result.returncode != 0
    state = _state(root)
    commands = [c["command"] for c in state["calls"]]
    assert "backup" in commands
    assert "freshness" in commands
    assert "stop" not in commands
    assert not state.get("rollback_called")


def test_pre_activation_stale_after_stop_rolls_back(tmp_path):
    root = tmp_path / "pre-activation-stale"
    _fake_kit(root)
    result = _run(root, "freshness_pre_activation_stale")
    assert result.returncode != 0
    state = _state(root)
    assert state.get("rollback_called") is True
    assert not state.get("candidate_started")


def test_partial_stop_triggers_recovery(tmp_path):
    root = tmp_path / "partial"
    _fake_kit(root)
    result = _run(root, "partial_stop_fail")
    assert result.returncode != 0
    assert _state(root).get("rollback_called") is True


def test_unexpected_exit_after_shutdown_triggers_recovery(tmp_path):
    root = tmp_path / "unexpected"
    _fake_kit(root)
    result = _run(root, "unexpected_exit_after_shutdown")
    assert result.returncode != 0
    assert _state(root).get("rollback_called") is True


def test_candidate_and_acceptance_failures_trigger_recovery(tmp_path):
    for scenario in ("candidate_start_fail", "auth_fail", "assignment_fail",
                     "restart_fail", "fresh_fail"):
        root = tmp_path / scenario
        _fake_kit(root)
        result = _run(root, scenario)
        assert result.returncode != 0, scenario
        assert _state(root).get("rollback_called") is True, scenario


def test_receipt_failure_is_not_committed_and_rolls_back(tmp_path):
    root = tmp_path / "receipt"
    _fake_kit(root)
    receipt = root / "missing-parent" / "receipt.json"
    result = _run(root, "success", receipt=receipt)
    assert result.returncode != 0
    assert _state(root).get("rollback_called") is True
    assert not receipt.is_file()


def test_rollback_failure_is_reported_explicitly(tmp_path):
    root = tmp_path / "rollback-fail"
    _fake_kit(root)
    result = _run(root, "rollback_fail")
    assert result.returncode != 0
    assert "ROLLBACK FAILED" in result.stderr
    failure = root / "run" / "deployment_failure.json"
    assert failure.is_file()
    assert json.loads(failure.read_text())["rollback_start_rc"] != 0


def test_successful_commit_has_no_rollback(tmp_path):
    root = tmp_path / "success"
    _fake_kit(root)
    receipt = root / "run" / "deployment_receipt.json"
    result = _run(root, "success", receipt=receipt)
    assert result.returncode == 0, result.stderr
    assert _state(root).get("rollback_called") is None
    assert receipt.is_file()


def test_production_plan_has_no_rehearsal_flag(tmp_path):
    root = tmp_path / "plan-production"
    _fake_kit(root)
    result = subprocess.run(
        ["bash", str(DEPLOY), "--print-plan"],
        env={**os.environ, "RELEASE_ROOT": str(root),
             "RELEASE_PYTHON": sys.executable},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["mode"] == "production"
    assert plan["rehearsal_args"] == []
    assert all("--rehearsal" not in part for part in plan["start"])
    assert "--require-quiescent-source" in plan["freshness_before_backup"]
    assert "--require-quiescent-source" in plan["freshness_after_backup"]
    assert "--require-quiescent-source" in plan["freshness_before_activation"]


def test_rehearsal_plan_has_one_rehearsal_flag(tmp_path):
    root = tmp_path / "plan-rehearsal"
    _fake_kit(root)
    result = subprocess.run(
        ["bash", str(DEPLOY), "--print-plan", "--rehearsal"],
        env={**os.environ, "RELEASE_ROOT": str(root),
             "RELEASE_PYTHON": sys.executable},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["mode"] == "rehearsal"
    assert plan["rehearsal_args"] == ["--rehearsal"]
    assert plan["start"].count("--rehearsal") == 1


def _real_root(root: Path):
    root.mkdir(parents=True)
    (root / "config").mkdir()
    (root / "config" / "env.release").write_text("API_PORT=18071\nFE_PORT=13130\n")
    (root / "RELEASE_IDENTITY.json").write_text(json.dumps(_identity(), indent=2))
    (root / "current").mkdir()
    (root / "current" / "scripts").symlink_to(KIT, target_is_directory=True)


def _run_real_approval(root: Path, mode: str = "production"):
    args = ["bash", str(DEPLOY)]
    if mode == "rehearsal":
        args.append("--rehearsal")
    return subprocess.run(
        args, env={**os.environ, "RELEASE_ROOT": str(root),
                   "RELEASE_PYTHON": sys.executable},
        capture_output=True, text=True, timeout=30)


def test_production_refuses_without_approval_before_shutdown(tmp_path):
    root = tmp_path / "no-approval"
    _real_root(root)
    result = _run_real_approval(root)
    assert result.returncode == 2
    assert "approval" in (result.stdout + result.stderr).lower()


def test_rehearsal_approval_cannot_authorize_production(tmp_path):
    root = tmp_path / "rehearsal-only"
    _real_root(root)
    (root / "config" / "REHEARSAL_APPROVED").write_text(json.dumps({
        "approver": "test", "approved_at": "2026-10-29",
        "release_tag": "assignment-successor-2026-10-29-a96484324",
        "product_commit": "ef95ceb3194ec92c51e64941d7bb364c0b8b0e75",
        "product_tree_sha256": "12060bee618e7a58a98324f682d39077c144c19a6fb7d22d77de8179237dbb9e",
        "scope": "single_user", "mode": "rehearsal"}, indent=2))
    result = _run_real_approval(root)
    assert result.returncode == 2


def test_mismatched_production_approval_refuses(tmp_path):
    root = tmp_path / "mismatch"
    _real_root(root)
    (root / "config" / "APPROVED").write_text(json.dumps({
        "approver": "test", "approved_at": "2026-10-29",
        "release_tag": "assignment-successor-2026-10-29-a96484324",
        "product_commit": "wrong",
        "product_tree_sha256": "wrong",
        "scope": "single_user", "mode": "production"}, indent=2))
    result = _run_real_approval(root)
    assert result.returncode == 2


def _write_source_scope(root: Path):
    (root / "config" / "source_shutdown_scope.json").write_text(json.dumps({
        "pid": 19046, "service": "atom-c912375de",
        "commit": "c912375de81b55465e61fe468bf0bc2b405fd206",
        "database": "/tmp/source/atom.db",
        "restore_command": "python -m uvicorn main_api_app:app --port 8001",
    }, indent=2))


def _approval_record(scope: dict | None):
    record = {
        "approver": "test", "approved_at": "2026-10-30",
        "release_tag": "assignment-successor-2026-10-29-a96484324",
        "product_commit": "ef95ceb3194ec92c51e64941d7bb364c0b8b0e75",
        "product_tree_sha256": "12060bee618e7a58a98324f682d39077c144c19a6fb7d22d77de8179237dbb9e",
        "scope": "single_user", "mode": "production",
    }
    if scope is not None:
        record["source_shutdown_scope"] = scope
    return record


def test_production_approval_binds_source_shutdown_scope(tmp_path):
    root = tmp_path / "scope"
    _real_root(root)
    _write_source_scope(root)
    scope = json.loads((root / "config" / "source_shutdown_scope.json").read_text())
    (root / "config" / "APPROVED").write_text(json.dumps(
        _approval_record(scope), indent=2))
    result = subprocess.run(
        [sys.executable, str(root / "current" / "scripts" / "release_tool.py"),
         "--root", str(root), "approval-check", "--mode", "production"],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_production_approval_without_scope_is_refused(tmp_path):
    root = tmp_path / "no-scope"
    _real_root(root)
    _write_source_scope(root)
    (root / "config" / "APPROVED").write_text(json.dumps(
        _approval_record(None), indent=2))
    result = subprocess.run(
        [sys.executable, str(root / "current" / "scripts" / "release_tool.py"),
         "--root", str(root), "approval-check", "--mode", "production"],
        capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
