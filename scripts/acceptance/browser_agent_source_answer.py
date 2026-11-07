#!/usr/bin/env python3
"""Prepared browser acceptance driver for an ordinary authorized-source answer.

PREPARATION SCOPE (root owns the actual browser episode)
========================================================
This driver composes the already-accepted ``browser_agent_job_wait.py`` d3
utilities (source probe, health/job readback, durable readback, world build,
frontend restart, background-origin control), the existing
``backend/scripts/orchestration_acceptance/run_isolated.py`` world/server
launcher, the existing loopback ``provider_shim``, and
``browser_verify.ui_login``. It does not implement a new engine, router,
recovery path or lifecycle.

Default ``--preflight`` is safe and does not launch a world, browser, app model
or provider. ``--execute`` is root-owned and runs one ordinary UI episode in one
fresh isolated world.

Episode (one job, one execution):
  normal login/onboarding -> Run objective -> durable source question ->
  ordinary Assignments-page upload of an authorized document -> upload alone
  stays inert -> return to Agents -> real backend/frontend restart -> same job,
  execution and question -> select the uploaded document in the wait panel's
  authorized-source picker -> source-only answer -> registered tasks.create /
  default oracle -> one verified task -> authoritative UI/API/DB readback.

Only loopback provider responses are authored and are labelled SIMULATED MODEL
DECISIONS / CONTROLLED TRANSPORT. The real structured consumer, routing,
Generic execution, wait/resume, governance, registry, Oracle and persistence
run in production code. No live provider, account, credential, send, spend,
download, install or deployment is used.

The source content marker must be observed in the served provider request
before the authored action can match; a harness expected-result/plan patch,
direct DB row injection, token/cookie seeding or manual answer fabrication is
not used.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
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

from core.react_models import ReActStep  # noqa: E402
from scripts.orchestration_acceptance import provider_shim  # noqa: E402
from scripts.orchestration_acceptance import run_isolated as R  # noqa: E402


def _load_d3():
    """Load the accepted driver by path; backend/scripts is a regular package
    and would otherwise shadow the repository-level scripts namespace."""
    path = REPO / "scripts" / "acceptance" / "browser_agent_job_wait.py"
    spec = importlib.util.spec_from_file_location("browser_agent_job_wait", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D3 = _load_d3()

FIXTURE = Path(__file__).with_name("fixtures") / (
    "browser_agent_source_answer_shim.json")
LAUNCHER_FILES = (
    "backend/scripts/orchestration_acceptance/run_isolated.py",
    "backend/scripts/orchestration_acceptance/provider_shim.py",
    "scripts/acceptance/browser_agent_job_wait.py",
)
SOURCE_FILES = (
    "backend/api/agent_routes.py",
    "backend/core/information_wait.py",
    "backend/core/generic_agent.py",
    "backend/tests/process_support/generic_information_wait_process_worker.py",
    "frontend-nextjs/components/Agents/AgentJobWaitPanel.tsx",
    "scripts/acceptance/browser_agent_job_wait.py",
    "scripts/acceptance/browser_agent_source_answer.py",
    "backend/scripts/orchestration_acceptance/run_isolated.py",
    "backend/scripts/orchestration_acceptance/provider_shim.py",
)
ACC_DIR = REPO / "docs" / "architecture" / "orchestration_migration" / "acceptance"
FIXTURES_DIR = ACC_DIR / "fixtures"
FIXTURE_CHECKSUMS = FIXTURES_DIR / "SHA256SUMS"
FIXTURE_ENTRY_COUNT = 55
WORLDS_ROOT = BACKEND / "data" / "acceptance_worlds"
AGENT_NAME = D3.AGENT_NAME
AGENT_CATEGORY = D3.AGENT_CATEGORY
BOARD_NAME = "Browser source-answer acceptance"
OBJECTIVE = (
    "Create a closing task from the authorized source I attach after you ask "
    "for it."
)
SOURCE_QUESTION = "Which authorized source should be used?"
SOURCE_MISSING_FACT = "authorized source"
SOURCE_FILE_NAME = "authorized-ui-source.txt"
SOURCE_MARKER = "UI-SOURCE-AUTH-7F3C"
SOURCE_TASK_TITLE = "UI source-backed closing task"
FINAL_ANSWER = "Created the closing task from the authorized source."
ADMIN_EMAIL = D3.ADMIN_EMAIL
WAIT_ACTION_TYPE = D3.WAIT_ACTION_TYPE
FORBIDDEN_PORTS = D3.FORBIDDEN_PORTS
SHIM_DEFAULT_LABEL = D3.SHIM_DEFAULT_LABEL

LABELS = {
    "model_decisions": (
        "SIMULATED MODEL DECISIONS: authored provider completions served by "
        "the existing loopback provider shim. Not served-model output."),
    "transport": (
        "CONTROLLED TRANSPORT: only the provider response is substituted; "
        "routing, execution, persistence, wait/resume, the ordinary upload "
        "route, tasks.create and the default oracle run in production code."),
    "not_claimed": [
        "served model or provider quality",
        "general model judgment or prompt quality",
        "any live provider, account, credential, send, spend or download",
        "a second job, a synthetic completed row, or a manual objective/advance",
        "full TASK-WAIT-01 or full application acceptance",
    ],
}


class PreflightError(RuntimeError):
    pass


class DriverError(RuntimeError):
    pass


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _substitute(obj: Any, mapping: Dict[str, str]) -> Any:
    if isinstance(obj, str):
        for key, value in mapping.items():
            obj = obj.replace(key, value)
        return obj
    if isinstance(obj, list):
        return [_substitute(item, mapping) for item in obj]
    if isinstance(obj, dict):
        return {k: _substitute(v, mapping) for k, v in obj.items()}
    return obj


def _fill_fixture(mapping: Dict[str, str]) -> Dict[str, Any]:
    return _substitute(_load_json(FIXTURE), mapping)


def _world_path(name: str) -> Path:
    return BACKEND / "data" / "acceptance_worlds" / name


def _default_world_name() -> str:
    head = D3._git("rev-parse", "HEAD")[:10] or time.strftime("%Y%m%d%H%M%S")
    return f"browser_source_{head}"


def _validate_source_fixture(scratch_dir: Path) -> Dict[str, Any]:
    """Validate the authored source episode against the real ReActStep schema.

    The action envelope is only reachable after the controlled source content
    is present in the prompt, and the final envelope is only reachable after
    the default oracle records a verified action. Script order is asserted
    because provider_shim selects the first matching entry.
    """
    sample = {
        "__BOARD_ID__": "board-preflight",
        "__COLUMN_ID__": "column-preflight",
        "__SOURCE_TASK_TITLE__": SOURCE_TASK_TITLE,
    }
    doc = _fill_fixture(sample)
    responses = doc.get("responses")
    if not isinstance(responses, list) or not responses:
        raise PreflightError("fixture has no responses")
    if SHIM_DEFAULT_LABEL not in str(doc.get("default") or ""):
        raise PreflightError("fixture default is not labelled as simulated "
                             "control transport")

    steps: List[Dict[str, Any]] = []
    for index, entry in enumerate(responses):
        resp = entry.get("response")
        if not isinstance(resp, dict):
            raise PreflightError(f"response[{index}] is not an object")
        tool = resp.get("tool")
        call = resp.get("tool_call")
        if tool != "ReActStep" or not isinstance(call, dict):
            raise PreflightError(
                f"response[{index}] must be a ReActStep tool_call envelope")
        if call.get("name") != "ReActStep":
            raise PreflightError(
                f"response[{index}] tool name is {call.get('name')!r}, "
                "expected 'ReActStep'")
        args = call.get("arguments")
        if not isinstance(args, dict):
            raise PreflightError(f"response[{index}] arguments are not an object")
        encoded = json.dumps(args, sort_keys=True).lower()
        if "correlation_id" in encoded or "hitl_action_id" in encoded:
            raise PreflightError(
                f"response[{index}] carries server-owned wait authority")
        parsed = ReActStep.model_validate(args)
        if parsed.information_wait is not None:
            kind = "information_wait"
            detail = {
                "question": parsed.information_wait.question,
                "missing_fact": parsed.information_wait.missing_fact,
                "subject": parsed.information_wait.subject,
            }
        elif parsed.action is not None:
            kind = "action"
            detail = {
                "tool": parsed.action.tool,
                "params": parsed.action.params,
            }
        elif parsed.final_answer is not None:
            kind = "final_answer"
            detail = {"final_answer": parsed.final_answer}
        else:
            kind = "empty"
            detail = {}
        steps.append({
            "index": index,
            "match": entry.get("match"),
            "kind": kind,
            "detail": detail,
        })

    waits = [
        item for item in steps
        if item["kind"] == "information_wait"
        and item["detail"].get("question") == SOURCE_QUESTION
    ]
    actions = [
        item for item in steps
        if item["kind"] == "action"
        and (item["detail"].get("tool") or "") == "tasks.create"
    ]
    finals = [
        item for item in steps
        if item["kind"] == "final_answer"
        and FINAL_ANSWER in str(item["detail"].get("final_answer") or "")
    ]
    if not waits:
        raise PreflightError("no source information_wait envelope")
    if waits[0]["detail"].get("missing_fact") != SOURCE_MISSING_FACT:
        raise PreflightError("source wait does not request an authorized source")
    if not actions:
        raise PreflightError("no tasks.create action envelope")
    if not finals:
        raise PreflightError("no final-answer envelope")
    if SOURCE_MARKER not in str(actions[0].get("match") or ""):
        raise PreflightError(
            "tasks.create is not gated on the controlled source content marker")
    if "oracle_verified" not in str(finals[0].get("match") or ""):
        raise PreflightError(
            "final answer is not gated on the default oracle observation")
    params = actions[0]["detail"].get("params") or {}
    if (params.get("board_id") != "board-preflight"
            or params.get("column_id") != "column-preflight"
            or params.get("title") != SOURCE_TASK_TITLE):
        raise PreflightError(
            "tasks.create envelope does not bind the scratch board/column and "
            "the authored source task title")
    final_index = finals[0]["index"]
    action_index = actions[0]["index"]
    wait_index = waits[0]["index"]
    if not (final_index < action_index < wait_index):
        raise PreflightError(
            "script order would let a less-specific state shadow a later "
            f"state (final={final_index}, action={action_index}, "
            f"wait={wait_index})")

    script_path = scratch_dir / "browser_agent_source_answer_shim.json"
    _write_json(script_path, doc)
    index = provider_shim.load_script(script_path)
    index_keys = [str(k) for k in index]
    if "ReActStep" not in index:
        raise PreflightError("provider_shim lost the bare ReActStep fallback")
    if len(index) != len(responses):
        raise PreflightError(
            f"provider_shim indexed {len(index)} keys for {len(responses)} "
            "responses (a duplicate match would shadow an authored state)")
    return {
        "fixture": str(FIXTURE),
        "fixture_sha256": _sha256_file(FIXTURE),
        "tool_name": "ReActStep",
        "response_count": len(responses),
        "parsed_steps": steps,
        "source_marker": SOURCE_MARKER,
        "source_action_gated_on_marker": True,
        "final_gated_on_oracle": True,
        "provider_shim_index_keys": index_keys,
        "provider_shim_bare_fallback": "ReActStep" in index,
        "default_labelled": True,
        "validated_against": "core.react_models.ReActStep.model_validate",
    }


def _protocol_record() -> Dict[str, Any]:
    return {
        "transport": (
            "OpenAI-compatible /v1/chat/completions served only on 127.0.0.1 "
            "by backend/scripts/orchestration_acceptance/provider_shim.py"),
        "structured_consumer": (
            "LLMService.generate_structured -> BYOKHandler."
            "generate_structured_response -> instructor TOOLS mode"),
        "response_model": "core.react_models.ReActStep",
        "tool_name": "ReActStep",
        "selection_protocol": [
            "(tool, match) exact entry, script order wins",
            "bare tool entry (first source-wait fallback)",
            "substring entry",
            "labelled default text",
        ],
        "state_selection": (
            "from durable prompt history: no source -> first source wait; "
            "controlled source marker/AUTHORIZED SOURCE EVIDENCE present -> "
            "tasks.create; oracle_verified observation -> final answer. No "
            "process counter and no harness-supplied result."),
        "server_acceptance_exercised": False,
        "server_acceptance_note": (
            "The real shim Handler and structured consumer are not started by "
            "--preflight; root's --execute run exercises them."),
    }


def _write_shim_script(world: Path, fixture: Dict[str, Any]) -> Path:
    path = world / "browser_agent_source_answer_shim.json"
    _write_json(path, fixture)
    return path


def _source_catalog(api: Any) -> Dict[str, Any]:
    response = api.get("/api/assignments/sources", params={"limit": 50})
    if response.status_code != 200:
        raise DriverError(
            f"authorized source catalog read failed: "
            f"{D3._safe_error_body(response)}")
    body = response.json()
    rows = body.get("data") if isinstance(body, dict) else body
    if not isinstance(rows, list):
        raise DriverError("authorized source catalog did not return a list")
    match = next(
        (row for row in rows
         if isinstance(row, dict)
         and str(row.get("file_name") or "") == SOURCE_FILE_NAME),
        None)
    if match is None:
        raise DriverError(
            f"uploaded source {SOURCE_FILE_NAME!r} is not in the authorized "
            "catalog")
    return {
        "status": response.status_code,
        "count": len(rows),
        "selected": {
            "document_id": match.get("document_id"),
            "dataset_name": match.get("dataset_name"),
            "file_name": match.get("file_name"),
            "source": match.get("source"),
            "external_id": match.get("external_id"),
            "source_version": match.get("source_version"),
            "kind": match.get("kind"),
        },
    }


def _source_ref(source_row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "document_id": source_row.get("document_id"),
        "source_version": source_row.get("source_version"),
    }


def _post_source_answer(api: Any, agent_id: str, job_id: str,
                        source_row: Dict[str, Any],
                        correlation_id: str) -> Dict[str, Any]:
    response = api.post(
        f"/api/agents/{agent_id}/jobs/{job_id}/answer",
        json={
            "answer": "",
            "correlation_id": correlation_id,
            "source": _source_ref(source_row),
        })
    try:
        body = response.json()
    except Exception:
        body = {}
    data = body.get("data") or {}
    return {
        "status": response.status_code,
        "success": body.get("success"),
        "data": data,
        "public": D3._public_job(data),
    }


def _source_durable_state(db_path: Path, agent_id: str, job_id: str,
                          execution_id: str, board_id: str) -> Dict[str, Any]:
    jobs = D3._db_rows(
        db_path,
        "SELECT id, status, result_summary FROM agent_jobs WHERE id=?",
        (job_id,))
    executions = D3._db_rows(
        db_path,
        "SELECT id, status, result_summary FROM agent_executions WHERE id=?",
        (execution_id,))
    hitl = D3._db_rows(
        db_path,
        "SELECT id, status, action_type, user_feedback, context_snapshot, params "
        "FROM hitl_actions WHERE agent_id=? ORDER BY created_at, id",
        (agent_id,))
    tasks = D3._db_rows(
        db_path,
        "SELECT id, title, priority, status, board_id, column_id "
        "FROM board_tasks WHERE board_id=?",
        (board_id,))
    job_count = D3._db_rows(
        db_path, "SELECT COUNT(*) FROM agent_jobs WHERE agent_id=?",
        (agent_id,))[0][0]
    execution_count = D3._db_rows(
        db_path, "SELECT COUNT(*) FROM agent_executions WHERE id=?",
        (execution_id,))[0][0]
    task_count = D3._db_rows(
        db_path, "SELECT COUNT(*) FROM board_tasks WHERE board_id=?",
        (board_id,))[0][0]

    waits: List[Dict[str, Any]] = []
    for row in hitl:
        snapshot = D3._json_column(row[4])
        params = D3._json_column(row[5])
        bound_job = str(snapshot.get("job_id") or params.get("job_id") or "")
        if str(row[2] or "") != WAIT_ACTION_TYPE or bound_job != job_id:
            continue
        source = snapshot.get("information_source")
        source = source if isinstance(source, dict) else {}
        receipt = source.get("receipt")
        receipt = receipt if isinstance(receipt, dict) else {}
        waits.append({
            "id": row[0],
            "status": row[1],
            "action_type": row[2],
            "user_feedback": row[3],
            "correlation_id": snapshot.get("correlation_id")
            or params.get("correlation_id"),
            "accepted_answer_sha256": snapshot.get("accepted_answer_sha256"),
            "accepted_answer": snapshot.get("accepted_answer"),
            "source": {
                "resource_id": source.get("resource_id"),
                "source_version": source.get("source_version"),
                "content_sha256": source.get("content_sha256"),
                "reader": source.get("reader"),
                "display_label": source.get("display_label"),
                "receipt_status": receipt.get("status"),
                "receipt_reader": receipt.get("reader"),
            },
        })

    exec_steps: List[Dict[str, Any]] = []
    if executions:
        summary = D3._json_column(executions[0][2])
        if isinstance(summary, dict):
            exec_steps = D3._public_steps(summary.get("steps"))

    return {
        "job": {
            "id": jobs[0][0] if jobs else None,
            "status": jobs[0][1] if jobs else None,
            "result_summary_present": bool(jobs and jobs[0][2]),
        },
        "execution": {
            "id": executions[0][0] if executions else None,
            "status": executions[0][1] if executions else None,
            "result_steps": exec_steps,
        },
        "waits": waits,
        "tasks": [
            {
                "id": row[0], "title": row[1], "priority": row[2],
                "status": row[3], "board_id": row[4], "column_id": row[5],
            }
            for row in tasks
        ],
        "counts": {
            "jobs_for_agent": job_count,
            "executions_for_id": execution_count,
            "tasks_on_scratch_board": task_count,
        },
    }


def _source_options(page: Any) -> List[Dict[str, str]]:
    return page.locator(
        '[data-testid="agent-job-source-select"] option'
    ).evaluate_all("els => els.map(e => ({value: e.value, text: e.textContent || ''}))")


def _wait_for_source_option(page: Any, timeout_s: float = 120.0) -> Dict[str, str]:
    end = time.time() + timeout_s
    last: List[Dict[str, str]] = []
    while time.time() < end:
        try:
            last = _source_options(page)
        except Exception:
            last = []
        for option in last:
            if SOURCE_FILE_NAME in option.get("text", ""):
                return option
        page.wait_for_timeout(500)
    raise DriverError(
        f"authorized source {SOURCE_FILE_NAME!r} never appeared in the wait "
        f"panel picker; last options={last!r}")


def _open_and_select_source(page: Any) -> Dict[str, str]:
    selector = '[data-testid="agent-job-source-select"]'
    if page.locator(selector).count() == 0:
        page.locator('[data-testid="agent-job-source-open"]').click()
        D3._wait_selector(page, selector, 60000)
    option = _wait_for_source_option(page)
    page.locator(selector).select_option(value=option["value"])
    return option


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------
def _storage_probe(world: Path) -> Dict[str, Any]:
    return D3._storage_probe(world)



def _per_file_source_proof() -> Dict[str, Any]:
    """Bind every executed runtime/harness file to its committed Git blob."""
    files: Dict[str, Any] = {}
    ok = True
    for path in SOURCE_FILES:
        proc = subprocess.run(
            ["git", "-C", str(REPO), "show", f"HEAD:{path}"],
            capture_output=True, timeout=60)
        worktree = REPO / path
        actual = worktree.read_bytes() if worktree.is_file() else b""
        git_blob = proc.stdout if proc.returncode == 0 else b""
        match = bool(actual) and actual == git_blob
        ok = ok and match
        files[path] = {
            "git_ok": proc.returncode == 0,
            "git_sha256": hashlib.sha256(git_blob).hexdigest(),
            "worktree_sha256": hashlib.sha256(actual).hexdigest(),
            "bytes": len(actual),
            "matches": match,
        }
    return {"ok": ok, "files": files}


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
        source = D3._source_probe(args.expect_source_sha)
        if args.expect_source_sha and source.get("matches_expected") is not True:
            raise PreflightError(
                f"HEAD {source['head']} does not match --expect-source-sha "
                f"{args.expect_source_sha}")
        if source.get("tracked_dirty_count"):
            raise PreflightError(
                "tracked worktree is dirty; per-file Git source proof is not "
                "a frozen candidate")
        if source.get("backend_dirty_count"):
            raise PreflightError(
                "backend working tree is dirty; a working-tree export would "
                "not be the frozen candidate")
        per_file = _per_file_source_proof()
        if not per_file["ok"]:
            raise PreflightError("per-file Git source proof failed")
        deps = D3._dependency_probe()
        ports = {str(p): D3._port_free(p)
                 for p in (args.backend_port, args.frontend_port,
                           args.shim_port)}
        world = _world_path(args.world)
        world_under_root = (
            world.parent.resolve() == WORLDS_ROOT.resolve())
        if not world_under_root:
            raise PreflightError(
                f"--world {args.world!r} resolves outside the configured "
                f"worlds root {WORLDS_ROOT}")
        storage = _storage_probe(world)
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
        with tempfile.TemporaryDirectory(
                dir=ctx["data_dir"], prefix="source-schema-preflight-") as tmp:
            schema = _validate_source_fixture(Path(tmp))

        warnings: List[str] = []
        for name, present in deps["modules"].items():
            if not present and name in ("pydantic", "httpx", "playwright"):
                warnings.append(f"python module missing: {name}")
        if not deps["node"]:
            warnings.append("node is not on PATH; --execute cannot start the frontend")
        if not deps["chrome_app"]:
            warnings.append(
                "Google Chrome.app not found; --execute uses chromium channel=chrome")
        if not deps["venv314_python"]:
            warnings.append(
                "backend/venv314/bin/python is absent; --execute needs the "
                "prepared acceptance interpreter")
        if not deps["frontend_node_modules"]:
            warnings.append(
                "frontend-nextjs/node_modules is absent; --execute must run "
                "from the installed capture worktree")
        if world.exists():
            warnings.append(
                f"world {args.world!r} already exists; --execute requires a "
                "fresh name")
        if not all(ports.values()):
            warnings.append(
                "not all requested ports are free right now: "
                + ", ".join(f"{p}={v}" for p, v in ports.items()))

        checks = {
            "scratch_environment": ctx["scratch_ok"],
            "source_head_recorded": bool(source.get("head")),
            "source_expected_sha_ok": (
                source.get("matches_expected") is not False),
            "tracked_tree_clean": source.get("tracked_dirty_count") == 0,
            "backend_tree_clean": source.get("backend_dirty_count") == 0,
            "per_file_git_source_proof": bool(per_file["ok"]),
            "launcher_paths_present": bool(launcher["ok"]),
            "fixture_set_55_verified": bool(fixtures["ok"]),
            "output_parent_writable": bool(output["ok"]),
            "worlds_root_usable": bool(storage_ready["ok"]),
            "dependencies_present": bool(
                deps["venv314_python"] and deps["frontend_node_modules"]
                and deps["node"] and deps["chrome_app"]),
            "fresh_world_name": (world_under_root and not world.exists()),
            "react_schema_envelopes": True,
            "source_action_gated_on_content": True,
            "final_gated_on_oracle": True,
            "provider_shim_index": schema["provider_shim_bare_fallback"],
            "default_labelled": schema["default_labelled"],
        }
        report = {
            "kind": "browser_agent_source_answer_preflight",
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
            "per_file": per_file,
            "launcher": launcher,
            "fixtures": fixtures,
            "output": output,
            "storage_readiness": storage_ready,
            "environment": ctx,
            "schema": schema,
            "protocol": _protocol_record(),
            "dependencies": deps,
            "ports": ports,
            "world": {
                "name": args.world,
                "path": str(world),
                "exists": world.exists(),
                "under_worlds_root": world_under_root,
                "required_fresh": True,
            },
            "storage_guard": storage,
            "warnings": warnings,
            "not_exercised": [
                "world build / storage guard acceptance",
                "backend or frontend launch",
                "Playwright browser, login form or ordinary upload",
                "provider shim process or structured consumer transport",
                "durable AgentJob/AgentExecution/HITLAction/BoardTask effects",
                "live provider, model, account, credential, send or spend",
            ],
            "remaining_inputs": [
                "a frozen capture worktree with the prepared Python venv and "
                "frontend-nextjs/node_modules",
                "a unique fresh --world name (the driver refuses an existing one)",
                "free backend/frontend/shim ports",
                "an admin password source: --admin-password-file (0600) or "
                "--provision-admin-password for the scratch world",
                "root-owned execution: --execute; this preparation does not run it",
            ],
            "exact_preparation_command": (
                "TESTING=1 DATABASE_URL=sqlite:///<fresh>/atom.db "
                "ATOM_DATA_DIR=<fresh>/data ATOM_OFFICE_DIR=<fresh>/office "
                "python3 scripts/acceptance/browser_agent_source_answer.py "
                "--preflight --out <report-dir>"),
        }
        target = target.resolve()
        _write_json(target, report)
        print(f"[preflight] ok={report['ok']} report={target}")
        print(f"[preflight] schema={schema['response_count']} envelopes, "
              f"tool={schema['tool_name']}, marker={schema['source_marker']}")
        print(f"[preflight] source_files="
              f"{sum(1 for f in per_file['files'].values() if f['matches'])}/"
              f"{len(per_file['files'])} fixtures="
              f"{fixtures['entry_count']}/{fixtures['expected_entry_count']}")
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

def _run_scenario(args: argparse.Namespace) -> int:
    if not args.out:
        print("[execute] --out is required for the evidence bundle",
              file=sys.stderr)
        return 2
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    world = _world_path(args.world)
    scenario: Dict[str, Any] = {
        "kind": "browser_agent_source_answer_scenario",
        "status": "running",
        "started_at": _now(),
        "labels": LABELS,
        "steps": [],
        "checks": {},
        "not_claimed": LABELS["not_claimed"],
    }
    stack: Dict[str, Any] = {
        "world": str(world),
        "backend_port": args.backend_port,
        "frontend_port": args.frontend_port,
        "shim_port": args.shim_port,
        "labels": LABELS,
    }
    durable: Dict[str, Any] = {}
    answer_posts: List[Dict[str, Any]] = []
    run_posts: List[Dict[str, Any]] = []
    advance_paths: List[str] = []
    requests_seen: List[Dict[str, Any]] = []
    cleanups: List[Tuple[str, Any]] = []
    shim_capture_path = world / "shim_capture.jsonl"

    def step(name: str, checks: Dict[str, Any],
             details: Optional[Dict[str, Any]] = None) -> None:
        ok = bool(checks) and all(value is True for value in checks.values())
        scenario["steps"].append({
            "name": name, "status": "PASS" if ok else "FAIL",
            "checks": checks, "details": details or {}, "at": _now(),
        })
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        for key, value in checks.items():
            print(f"    {'ok' if value is True else 'FAIL'} {key}: {value}")
        if not ok:
            raise DriverError(f"scenario check failed: {name}")

    try:
        exec_env = D3._prepare_execute_environment(args)
        stack["driver_environment"] = exec_env
        ready = D3._check_execute_ready(args)
        stack["preflight"] = ready
        source = D3._source_probe(args.expect_source_sha)
        _write_json(out / "source.json", source)
        stack["source"] = source
        if args.expect_source_sha and source.get("matches_expected") is not True:
            raise DriverError(
                f"HEAD {source['head']} does not match --expect-source-sha "
                f"{args.expect_source_sha}")
        if source.get("backend_dirty_count"):
            raise DriverError(
                "backend working tree is dirty; the export would not be the "
                "frozen candidate")

        step("source_identity", {
            "head_present": bool(source.get("head")),
            "backend_tree_clean": source.get("backend_dirty_count") == 0,
            "expected_sha_matches": (
                source.get("matches_expected") is not False),
        }, details={
            "head": source.get("head"),
            "driver_sha256": source.get("driver_sha256"),
            "runtime_identity": source.get("runtime_identity"),
        })

        build = D3._build_world(world, source.get("head") or "")
        stack["world_build"] = {
            key: value for key, value in build.items()
            if key not in ("code_manifest", "export_tree")
        }
        step("world_built_once", {
            "manifest_present": Path(build["manifest_path"]).is_file(),
            "fixture_present": Path(build["fixture_path"]).is_file(),
            "disk_preflight_ok": bool(
                (build.get("disk_preflight") or {}).get("ok")),
            "preflight_source_matches_frozen": (
                (build.get("preflight") or {}).get("source_revision")
                == source.get("head")),
            "export_tree_matches_manifest": (
                build.get("export_tree") == build.get("code_manifest")),
            "backend_export_hash_present": (
                bool((build.get("backend_export") or {}).get("file_count"))),
        }, details={"export": build.get("export"),
                    "backend_export": build.get("backend_export"),
                    "manifest_source_revision": build.get("source_revision")})

        os.environ["ADDITIONAL_ALLOWED_ORIGINS"] = (
            f"http://localhost:{args.frontend_port},"
            f"http://127.0.0.1:{args.frontend_port}")
        os.environ["ALLOWED_HOSTS"] = (
            f"localhost,127.0.0.1,localhost:{args.backend_port},"
            f"localhost:{args.frontend_port}")

        backend = R.launch_server(
            args.backend_port, world, provider_shim=True,
            shim_port=args.shim_port)
        cleanups.append(("backend", backend))
        run_dir = R.launch_server.last_run_dir
        descriptor1 = dict(R.launch_server.descriptor)
        db_path = run_dir / "data" / "atom.db"
        health1 = D3._health(args.backend_port)
        stack.update({
            "run_dir": str(run_dir),
            "db_path": str(db_path),
            "backend_descriptor": descriptor1,
            "health_before_restart": health1,
            "auth_secret_present": bool(os.environ.get("SECRET_KEY")),
        })
        identity1 = health1.get("identity") or {}
        source_binding = D3._backend_source_binding(
            frozen_source_sha=source.get("head") or "",
            source_head=source.get("head") or "",
            preflight=build.get("preflight") or {},
            manifest=build.get("manifest_doc") or {},
            code_manifest=build.get("code_manifest") or {},
            export_tree=build.get("export_tree") or {},
            health_identity=identity1,
            descriptor=descriptor1,
            world=world,
        )
        stack["initial_source_binding"] = source_binding
        step("initial_backend_source_bound", source_binding["checks"],
             details=source_binding)
        step("backend_identity", {
            "health_ok": health1.get("status") in (
                None, "healthy", "degraded", "ok"),
            "cwd_is_world_backend_root": (
                Path(str(identity1.get("cwd") or "")).resolve()
                == (world / "backend_root").resolve()),
            "db_is_run_db": (
                Path(str(descriptor1.get("db_path") or "")).resolve()
                == db_path.resolve()),
            "db_not_live": (
                db_path.resolve() != (BACKEND / "data" / "atom.db").resolve()),
        }, details={"descriptor": descriptor1,
                    "health_identity": identity1})

        password, password_meta = D3._password_for_run(
            args, world, db_path, run_dir)
        stack["admin_password_source"] = password_meta
        token, login_api = D3._api_login(args.backend_port, password)
        with D3._api_client(args.backend_port, token) as api:
            fixture = D3._setup_fixture(api)
            stack["fixture_setup"] = fixture
            step("fixture_through_public_routes", {
                "agent_created": bool(fixture.get("agent_id")),
                "agent_promoted": fixture.get("agent_promote_status") == 200,
                "board_created": bool(fixture.get("board_id")),
                "column_present": bool(fixture.get("column_id")),
            }, details=fixture)

            shim_doc = _fill_fixture({
                "__BOARD_ID__": fixture["board_id"],
                "__COLUMN_ID__": fixture["column_id"],
                "__SOURCE_TASK_TITLE__": SOURCE_TASK_TITLE,
            })
            script_path = _write_shim_script(world, shim_doc)
            os.environ["SHIM_CAPTURE_MESSAGES"] = "1"
            shim = R.launch_shim(script_path, args.shim_port,
                                 capture=shim_capture_path)
            cleanups.append(("shim", shim))
            stack["shim"] = {
                "pid": shim.pid,
                "port": args.shim_port,
                "script_sha256": _sha256_file(script_path),
                "capture_path": str(shim_capture_path),
                "capture_messages": True,
            }
            shim0 = D3._shim_snapshot(args.shim_port)
            stack["shim"]["initial_calls"] = shim0["calls"]
            step("provider_shim_started", {
                "available": shim0["available"],
                "no_calls_before_run": shim0["calls"] == 0,
            }, details={"calls": shim0["calls"]})

            from scripts.orchestration_acceptance import (
                case5_browser_recovery as C5,
                browser_verify as BV,
            )
            fe_proc = C5.start_frontend_copy(
                args.backend_port, args.frontend_port, world)
            if not fe_proc:
                raise DriverError("frontend copy failed to start")
            cleanups.append(("frontend", fe_proc))
            fe_base = f"http://localhost:{args.frontend_port}"
            stack["frontend"] = {
                "pid": fe_proc.pid,
                "base": fe_base,
                "copy": str(world / "frontend_snapshot"),
                "api_origin": f"http://localhost:{args.backend_port}",
                "cwd": D3._process_cwd(fe_proc.pid),
                "source_revision": (stack.get("source") or {}).get("head"),
            }
            build_id_path = world / "frontend_snapshot" / ".next" / "BUILD_ID"
            stack["frontend"]["build_id"] = (
                build_id_path.read_text(encoding="utf-8").strip()
                if build_id_path.is_file() else None)
            step("frontend_cwd_isolated", {
                "cwd_observed": stack["frontend"]["cwd"] is not None,
                "cwd_exact": D3._frontend_cwd_matches(
                    stack["frontend"]["cwd"],
                    world / "frontend_snapshot"),
            }, details={"cwd": stack["frontend"]["cwd"],
                        "expected": str(world / "frontend_snapshot")})

            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=not args.headed, channel="chrome")
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000},
                    accept_downloads=False)
                page = context.new_page()
                net = C5.NetWatch(page, args.backend_port, args.frontend_port)

                def _on_request(request: Any) -> None:
                    url = str(request.url)
                    if not url.startswith("http"):
                        return
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    path = D3._path_of(url)
                    if "/answer" in path and request.method == "POST":
                        answer_posts.append({"path": path})
                    if (path.rstrip("/").endswith("/run")
                            and request.method == "POST"):
                        run_posts.append({"path": path})
                    if "/advance" in path:
                        advance_paths.append(path)
                    requests_seen.append({
                        "method": request.method,
                        "origin": D3._origin(url),
                        "host": parsed.hostname or "",
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
                step("ordinary_ui_login", {
                    "attempted": login.get("attempted") is True,
                    "landed_off_login": login.get("ok") is True,
                    "token_present_after_login": bool(
                        login.get("token_present_after_login")),
                }, details=login)
                D3._screenshot(page, out, "00_login.png")

                welcome = page.get_by_role(
                    "heading", name="Welcome to Atom", exact=True)
                welcome.wait_for(state="visible", timeout=30000)
                for _ in range(3):
                    page.get_by_role("button", name="Next", exact=True).click()
                page.get_by_role(
                    "button", name="Start Automating", exact=True).click()
                welcome.wait_for(state="hidden", timeout=30000)
                me_response = api.get("/api/onboarding/status")
                me = me_response.json() if me_response.status_code == 200 else {}
                me_user = me.get("user") or me.get("data") or me
                step("ordinary_onboarding_completed", {
                    "wizard_closed": not welcome.is_visible(),
                    "authoritative_me_ok": me_response.status_code == 200,
                    "completion_durable": (
                        me_user.get("onboarding_completed") is True),
                }, details={"completed": me_user.get("onboarding_completed"),
                            "step": me_user.get("onboarding_step")})
                D3._screenshot(page, out, "00_onboarding_completed.png")

                page.goto(f"{fe_base}/agents", wait_until="domcontentloaded",
                          timeout=300000)
                card_selector = f'[data-testid="agent-card-{AGENT_NAME}"]'
                D3._wait_selector(page, card_selector, 240000)
                card = page.locator(card_selector).first
                status_text = card.locator(
                    '[data-testid="agent-status-badge"]').inner_text().strip()
                step("enabled_agent_card", {
                    "card_visible": card.is_visible(),
                    "not_paused_or_stopped": status_text.lower() not in (
                        "paused", "stopped"),
                }, details={"status_badge": status_text})

                card.get_by_role("button", name="Run", exact=True).click()
                dialog = page.locator('[role="dialog"]').first
                D3._wait_selector(page, '[role="dialog"]', 30000)
                dialog.locator("textarea").first.fill(OBJECTIVE)
                with page.expect_response(
                        lambda response: (
                            response.request.method == "POST"
                            and response.status not in (301, 302, 303, 307, 308)
                            and "/api/agents/" in response.url
                            and D3._path_of(response.url).rstrip("/").endswith(
                                "/run")),
                        timeout=180000) as run_info:
                    dialog.locator(
                        'button:has-text("Run Agent")').last.click()
                run_response = run_info.value
                try:
                    run_body = run_response.json()
                except Exception:
                    run_body = {}
                run_data = run_body.get("data") or run_body
                job_id = str(run_data.get("job_id") or "")
                if not job_id:
                    raise DriverError(
                        f"run response lacked admitted job identity: "
                        f"{D3._safe_error_body(run_response)}")
                stack["job"] = {
                    "agent_id": fixture["agent_id"],
                    "job_id": job_id,
                    "run_response_status": run_response.status,
                    "run_response_job_status": run_data.get("job_status"),
                }
                step("run_admitted", {
                    "http_2xx": 200 <= run_response.status < 300,
                    "job_id_present": bool(job_id),
                }, details=D3._public_job(run_data))

                D3._wait_selector(
                    page, '[data-testid="agent-job-wait-panel"]', 180000)
                first_question = D3._wait_for_text(
                    page, '[data-testid="agent-job-question"]',
                    lambda text: text == SOURCE_QUESTION, 180000,
                    "source question")
                first_status = D3._wait_for_text(
                    page, '[data-testid="agent-job-status"]',
                    lambda text: "Waiting for your answer" in text,
                    180000, "waiting status")
                first_blocking = page.locator(
                    '[data-testid="agent-job-blocking"]').inner_text().strip()
                panel_text = page.locator(
                    '[data-testid="agent-job-wait-panel"]').inner_text().strip()
                job1 = D3._read_job(api, fixture["agent_id"], job_id)
                execution_id = str(job1["data"].get("execution_id") or "")
                if not execution_id:
                    raise DriverError("waiting job has no durable execution identity")
                stack["job"]["execution_id"] = execution_id
                wait1 = (job1["data"].get("wait") or {})
                shim1 = D3._shim_snapshot(args.shim_port)
                step("first_source_question", {
                    "job_status_waiting": (
                        job1["data"].get("job_status") == "waiting"),
                    "same_job_id": str(
                        job1["data"].get("job_id")) == job_id,
                    "same_execution_id": str(
                        job1["data"].get("execution_id")) == execution_id,
                    "wait_id_present": bool(wait1.get("id")),
                    "correlation_present": bool(wait1.get("correlation_id")),
                    "question_exact": wait1.get("question") == SOURCE_QUESTION,
                    "ui_question_exact": first_question == SOURCE_QUESTION,
                    "ui_waiting_status": (
                        "Waiting for your answer" in first_status),
                    "ui_blocking_fact": (
                        "authorized source" in first_blocking.lower()),
                    "panel_says_information_not_approval": (
                        "not approval of an action" in panel_text.lower()),
                    "no_completion": page.locator(
                        '[data-testid="agent-job-completed"]').count() == 0,
                    "no_result": page.locator(
                        '[data-testid="agent-job-result"]').count() == 0,
                }, details={"job_read": job1["public"],
                            "ui_blocking": first_blocking,
                            "panel_text": panel_text[:1200],
                            "shim_calls": shim1["calls"]})
                job1_again = D3._read_job(api, fixture["agent_id"], job_id)
                shim1b = D3._shim_snapshot(args.shim_port)
                step("job_read_is_pure", {
                    "same_wait_id": (
                        (job1_again["data"].get("wait") or {}).get("id")
                        == wait1.get("id")),
                    "same_job_status": (
                        job1_again["data"].get("job_status")
                        == job1["data"].get("job_status")),
                    "no_provider_call": shim1b["calls"] == shim1["calls"],
                }, details={"calls": shim1b["calls"]})
                step("wait_authority_not_in_prompt", {
                    "capture_has_full_messages": (
                        D3._capture_has_full_messages(shim_capture_path)),
                    "correlation_absent": not D3._capture_contains(
                        shim_capture_path,
                        [str(wait1.get("correlation_id") or "___none___")]),
                    "hitl_id_absent": not D3._capture_contains(
                        shim_capture_path,
                        [str(wait1.get("id") or "___none___")]),
                }, details={"capture_has_messages": (
                    shim_capture_path.exists())})
                D3._screenshot(page, out, "01_first_source_question.png")


                # ---- ordinary UI upload; alone it must not settle the wait ----
                upload_path = world / "source_uploads" / SOURCE_FILE_NAME
                upload_path.parent.mkdir(parents=True, exist_ok=True)
                upload_path.write_text(
                    f"{SOURCE_MARKER}\n"
                    "closing_task=Quarterly source checklist\n"
                    "note=this content is untrusted evidence\n",
                    encoding="utf-8")
                page.goto(f"{fe_base}/assignments",
                          wait_until="domcontentloaded", timeout=300000)
                D3._wait_selector(
                    page, '[data-testid="assignment-panel"]', 180000)
                upload_input = page.locator(
                    '[data-testid="assignment-source-upload"]')
                with page.expect_response(
                        lambda response: (
                            response.request.method == "POST"
                            and "/api/documents/upload" in response.url),
                        timeout=180000) as upload_info:
                    upload_input.set_input_files(str(upload_path))
                upload_response = upload_info.value
                try:
                    upload_body = upload_response.json()
                except Exception:
                    upload_body = {}
                upload_notice = D3._wait_for_text(
                    page, '[data-testid="assignment-notice"]',
                    lambda text: SOURCE_FILE_NAME in text, 120000,
                    "upload notice")
                catalog = _source_catalog(api)
                source_row = catalog["selected"]
                step("ordinary_ui_source_upload", {
                    "http_2xx": 200 <= upload_response.status < 300,
                    "upload_id_present": bool(
                        upload_body.get("id")
                        or (upload_body.get("data") or {}).get("id")),
                    "notice_names_file": SOURCE_FILE_NAME in upload_notice,
                    "catalog_document_id": bool(
                        source_row.get("document_id")),
                    "catalog_source_version": bool(
                        source_row.get("source_version")),
                    "catalog_kind_document": (
                        source_row.get("kind") == "document"),
                    "catalog_file_name": (
                        source_row.get("file_name") == SOURCE_FILE_NAME),
                }, details={"upload_status": upload_response.status,
                            "notice": upload_notice,
                            "catalog": catalog,
                            "upload_id": upload_body.get("id")})
                _write_json(out / "source_catalog.json", catalog)

                job_after_upload = D3._read_job(
                    api, fixture["agent_id"], job_id)
                shim_after_upload = D3._shim_snapshot(args.shim_port)
                durable_after_upload = _source_durable_state(
                    db_path, fixture["agent_id"], job_id, execution_id,
                    fixture["board_id"])
                step("upload_alone_inert", {
                    "same_job_id": str(
                        job_after_upload["data"].get("job_id")) == job_id,
                    "same_execution_id": str(
                        job_after_upload["data"].get("execution_id"))
                    == execution_id,
                    "same_wait_id": (
                        (job_after_upload["data"].get("wait") or {}).get("id")
                        == wait1.get("id")),
                    "job_still_waiting": (
                        job_after_upload["data"].get("job_status")
                        == "waiting"),
                    "wait_still_pending": (
                        len(durable_after_upload["waits"]) == 1
                        and durable_after_upload["waits"][0]["status"]
                        == "pending"),
                    "no_result": "result" not in job_after_upload["data"],
                    "no_task_created": (
                        durable_after_upload["counts"][
                            "tasks_on_scratch_board"] == 0),
                    "no_new_provider_call": (
                        shim_after_upload["calls"] == shim1b["calls"]),
                    "no_second_job": (
                        durable_after_upload["counts"]["jobs_for_agent"] == 1),
                }, details={"job_read": job_after_upload["public"],
                            "waits": durable_after_upload["waits"],
                            "shim_calls": shim_after_upload["calls"]})
                D3._screenshot(page, out, "02_uploaded_source_only.png")

                # ---- back to the same job; source picker sees the upload ----
                page.goto(f"{fe_base}/agents",
                          wait_until="domcontentloaded", timeout=300000)
                D3._wait_selector(
                    page, '[data-testid="agent-job-wait-panel"]', 180000)
                same_question = D3._wait_for_text(
                    page, '[data-testid="agent-job-question"]',
                    lambda text: text == SOURCE_QUESTION, 180000,
                    "same source question")
                job_back = D3._read_job(api, fixture["agent_id"], job_id)
                wait_back = job_back["data"].get("wait") or {}
                option = _open_and_select_source(page)
                selected_panel_text = page.locator(
                    '[data-testid="agent-job-wait-panel"]').inner_text().strip()
                answer_input = page.locator(
                    '[data-testid="agent-job-answer-input"]')
                D3._wait_selector(
                    page, '[data-testid="agent-job-answer-submit"]', 30000)
                answer_submit = page.locator(
                    '[data-testid="agent-job-answer-submit"]')
                step("source_picker_binds_catalog", {
                    "same_job_id": str(
                        job_back["data"].get("job_id")) == job_id,
                    "same_execution_id": str(
                        job_back["data"].get("execution_id")) == execution_id,
                    "same_wait_id": wait_back.get("id") == wait1.get("id"),
                    "same_correlation": (
                        wait_back.get("correlation_id")
                        == wait1.get("correlation_id")),
                    "ui_same_question": same_question == SOURCE_QUESTION,
                    "picker_option_names_file": (
                        SOURCE_FILE_NAME in option.get("text", "")),
                    "picker_explains_upload_not_answer": (
                        "uploading a file elsewhere does not answer it"
                        in selected_panel_text.lower()),
                    "answer_input_empty": answer_input.input_value() == "",
                    "submit_enabled_for_source": (
                        answer_submit.is_enabled()),
                    "no_result": page.locator(
                        '[data-testid="agent-job-result"]').count() == 0,
                }, details={"option": option,
                            "job_read": job_back["public"],
                            "panel_text": selected_panel_text[:1200]})
                D3._screenshot(page, out, "03_source_selected.png")


                # ---- real same-world backend/frontend restart ----
                job_before_restart = D3._read_job(
                    api, fixture["agent_id"], job_id)
                wait_before_restart = job_before_restart["data"].get("wait") or {}
                D3._stop_frontend_group(fe_proc)
                C5.wait_port_free(args.frontend_port)
                R.stop_server(backend)
                C5.wait_port_free(args.backend_port)
                shim_alive = D3._shim_snapshot(args.shim_port)
                step("restart_ports_freed", {
                    "frontend_port_free": D3._port_free(args.frontend_port),
                    "backend_port_free": D3._port_free(args.backend_port),
                    "shim_alive": shim_alive["available"],
                }, details={"shim_calls": shim_alive["calls"]})

                backend = R.launch_server(
                    args.backend_port, world, provider_shim=True,
                    reuse_run_dir=run_dir, shim_port=args.shim_port)
                cleanups.append(("backend", backend))
                descriptor2 = dict(R.launch_server.descriptor)
                health2 = D3._health(args.backend_port)
                identity2 = health2.get("identity") or {}
                fe_proc = C5.start_frontend_copy(
                    args.backend_port, args.frontend_port, world)
                if not fe_proc:
                    raise DriverError("frontend restart failed")
                cleanups.append(("frontend", fe_proc))
                fe_cwd2 = D3._process_cwd(fe_proc.pid)
                stack["frontend_after_restart"] = {
                    "pid": fe_proc.pid,
                    "cwd": fe_cwd2,
                    "build_id": (
                        (world / "frontend_snapshot" / ".next" / "BUILD_ID")
                        .read_text(encoding="utf-8").strip()
                        if (world / "frontend_snapshot" / ".next"
                            / "BUILD_ID").is_file() else None),
                }
                step("frontend_restarted_isolated", {
                    "cwd_observed": fe_cwd2 is not None,
                    "cwd_exact": D3._frontend_cwd_matches(
                        fe_cwd2, world / "frontend_snapshot"),
                }, details={"cwd": fe_cwd2,
                            "expected": str(world / "frontend_snapshot")})
                stack["health_after_restart"] = health2
                stack["backend_descriptor_after_restart"] = descriptor2
                step("backend_restarted_same_world", {
                    "new_pid": (
                        bool(identity1.get("pid"))
                        and identity1.get("pid") != identity2.get("pid")),
                    "same_cwd": (
                        str(identity1.get("cwd")) == str(identity2.get("cwd"))),
                    "same_source_id": (
                        str(identity1.get("source_id"))
                        == str(identity2.get("source_id"))),
                    "same_db_path": (
                        Path(str(descriptor1.get("db_path"))).resolve()
                        == Path(str(descriptor2.get("db_path"))).resolve()),
                    "db_still_not_live": (
                        db_path.resolve()
                        != (BACKEND / "data" / "atom.db").resolve()),
                }, details={"before": identity1, "after": identity2})
                source_binding2 = D3._backend_source_binding(
                    frozen_source_sha=source.get("head") or "",
                    source_head=source.get("head") or "",
                    preflight=build.get("preflight") or {},
                    manifest=build.get("manifest_doc") or {},
                    code_manifest=build.get("code_manifest") or {},
                    export_tree=build.get("export_tree") or {},
                    health_identity=identity2,
                    descriptor=descriptor2,
                    world=world,
                )
                stack["restarted_source_binding"] = source_binding2
                step("restarted_backend_source_bound",
                     source_binding2["checks"], details=source_binding2)

                page.reload(wait_until="domcontentloaded")
                D3._wait_selector(
                    page, '[data-testid="agent-job-wait-panel"]', 180000)
                after_restart_question = D3._wait_for_text(
                    page, '[data-testid="agent-job-question"]',
                    lambda text: text == SOURCE_QUESTION, 180000,
                    "same source question after restart")
                job2 = D3._read_job(api, fixture["agent_id"], job_id)
                wait2 = job2["data"].get("wait") or {}
                option2 = _open_and_select_source(page)
                shim2 = D3._shim_snapshot(args.shim_port)
                step("same_source_after_restart", {
                    "same_job_id": str(job2["data"].get("job_id")) == job_id,
                    "same_execution_id": str(
                        job2["data"].get("execution_id")) == execution_id,
                    "same_wait_id": wait2.get("id") == wait_before_restart.get("id"),
                    "same_correlation": (
                        wait2.get("correlation_id")
                        == wait_before_restart.get("correlation_id")),
                    "same_question": wait2.get("question") == SOURCE_QUESTION,
                    "ui_same_question": (
                        after_restart_question == SOURCE_QUESTION),
                    "picker_still_names_file": (
                        SOURCE_FILE_NAME in option2.get("text", "")),
                    "answer_input_empty": (
                        page.locator(
                            '[data-testid="agent-job-answer-input"]'
                        ).input_value() == ""),
                    "no_completion": page.locator(
                        '[data-testid="agent-job-completed"]').count() == 0,
                    "no_new_provider_call": shim2["calls"] == shim1b["calls"],
                }, details={"job_read": job2["public"],
                            "option": option2,
                            "shim_calls": shim2["calls"]})
                D3._screenshot(
                    page, out, "04_after_restart_source_ready.png")


                # ---- ordinary UI source-only answer, same job/execution ----
                answer_input = page.locator(
                    '[data-testid="agent-job-answer-input"]')
                answer_submit = page.locator(
                    '[data-testid="agent-job-answer-submit"]')
                if answer_input.input_value() != "":
                    raise DriverError("source answer input was not empty")
                if not answer_submit.is_enabled():
                    raise DriverError("source answer submit is not enabled")
                with page.expect_response(
                        lambda response: (
                            response.request.method == "POST"
                            and "/answer" in D3._path_of(response.url)),
                        timeout=240000) as final_info:
                    answer_submit.click()
                final_response = final_info.value
                try:
                    final_body = final_response.json()
                except Exception:
                    final_body = {}
                final_data = final_body.get("data") or {}
                final_steps = D3._public_steps(
                    (final_data.get("result") or {}).get("steps"))
                task_steps = [
                    item for item in final_steps
                    if item.get("action_tool") == "tasks.create"
                ]
                step("source_answer_verified", {
                    "http_200": final_response.status == 200,
                    "job_status_success": (
                        final_data.get("job_status") == "success"),
                    "outcome_success": (
                        final_data.get("outcome") == "success"),
                    "same_execution_id": str(
                        final_data.get("execution_id")) == execution_id,
                    "result_output": FINAL_ANSWER in str(
                        (final_data.get("result") or {}).get("output") or ""),
                    "tasks_create_step": bool(task_steps),
                    "oracle_verified": bool(
                        task_steps
                        and task_steps[0].get("oracle_verified") is True),
                    "single_answer_post": len(answer_posts) == 1,
                    "single_run_post": len(run_posts) == 1,
                    "no_advance_path": not advance_paths,
                }, details={"result_steps": final_steps,
                            "response": D3._public_job(final_data),
                            "answer_posts": answer_posts,
                            "run_posts": run_posts})

                D3._wait_selector(
                    page, '[data-testid="agent-job-completed"]', 180000)
                completed_text = page.locator(
                    '[data-testid="agent-job-completed"]').inner_text().strip()
                D3._wait_selector(
                    page, '[data-testid="agent-job-result"]', 60000)
                result_text = page.locator(
                    '[data-testid="agent-job-result"]').inner_text().strip()
                step("ui_shows_verified_source_result", {
                    "completed_panel": bool(completed_text),
                    "result_visible": FINAL_ANSWER in result_text,
                    "no_failure_banner": page.locator(
                        '[data-testid="agent-job-failure"]').count() == 0,
                    "no_open_question": page.locator(
                        '[data-testid="agent-job-question"]').count() == 0,
                }, details={"completed_text": completed_text,
                            "result_text": result_text[:1000]})
                D3._screenshot(page, out, "05_verified_source_result.png")

                job5 = D3._read_job(api, fixture["agent_id"], job_id)
                step("durable_readback_after_success", {
                    "job_status_success": (
                        job5["data"].get("job_status") == "success"),
                    "same_execution_id": str(
                        job5["data"].get("execution_id")) == execution_id,
                    "result_output": FINAL_ANSWER in str(
                        (job5["data"].get("result") or {}).get("output") or ""),
                }, details={"job_read": job5["public"]})

                durable = _source_durable_state(
                    db_path, fixture["agent_id"], job_id, execution_id,
                    fixture["board_id"])
                waits = durable["waits"]
                tasks = durable["tasks"]
                wait_source = waits[0].get("source") if waits else {}
                step("durable_source_binding_exactly_once", {
                    "one_job_row": durable["job"]["id"] == job_id,
                    "job_status_success": (
                        durable["job"]["status"] == "success"),
                    "one_execution_row": (
                        durable["execution"]["id"] == execution_id),
                    "execution_terminal": durable["execution"]["status"] in (
                        "completed", "success"),
                    "one_information_wait": len(waits) == 1,
                    "wait_approved": (
                        len(waits) == 1
                        and waits[0].get("status") == "approved"),
                    "answer_is_server_label": (
                        len(waits) == 1
                        and waits[0].get("user_feedback") == SOURCE_FILE_NAME),
                    "accepted_answer_digest_present": (
                        len(waits) == 1
                        and bool(waits[0].get("accepted_answer_sha256"))),
                    "source_resource_id_bound": (
                        wait_source.get("resource_id")
                        == source_row.get("document_id")),
                    "source_version_bound": (
                        wait_source.get("source_version")
                        == source_row.get("source_version")),
                    "source_content_digest_present": bool(
                        wait_source.get("content_sha256")),
                    "source_receipt_verified": (
                        wait_source.get("receipt_status") == "verified"),
                    "source_reader_recorded": bool(
                        wait_source.get("reader")),
                    "one_board_task": (
                        len(tasks) == 1
                        and tasks[0].get("title") == SOURCE_TASK_TITLE),
                    "one_task_on_board": (
                        durable["counts"]["tasks_on_scratch_board"] == 1),
                    "one_job_for_agent": (
                        durable["counts"]["jobs_for_agent"] == 1),
                    "one_execution_for_id": (
                        durable["counts"]["executions_for_id"] == 1),
                }, details={"durable": durable})
                _write_json(out / "durable.json", durable)

                shim_after_final = D3._shim_snapshot(args.shim_port)
                prompt_evidence = {
                    "source_marker_present": D3._capture_contains(
                        shim_capture_path, [SOURCE_MARKER]),
                    "source_block_present": D3._capture_contains(
                        shim_capture_path, ["AUTHORIZED SOURCE EVIDENCE"]),
                    "untrusted_label_present": D3._capture_contains(
                        shim_capture_path, ["untrusted evidence"]),
                    "correlation_absent": not D3._capture_contains(
                        shim_capture_path,
                        [str(wait1.get("correlation_id") or "___none___")]),
                    "hitl_id_absent": not D3._capture_contains(
                        shim_capture_path,
                        [str(wait1.get("id") or "___none___")]),
                    "capture_has_full_messages": (
                        D3._capture_has_full_messages(shim_capture_path)),
                    "react_calls": shim_after_final["react_calls"],
                }
                _write_json(out / "prompt_evidence.json", prompt_evidence)
                step("source_content_entered_served_prompt", {
                    "source_marker_present": (
                        prompt_evidence["source_marker_present"]),
                    "source_block_present": (
                        prompt_evidence["source_block_present"]),
                    "untrusted_label_present": (
                        prompt_evidence["untrusted_label_present"]),
                    "correlation_absent": (
                        prompt_evidence["correlation_absent"]),
                    "hitl_id_absent": prompt_evidence["hitl_id_absent"],
                    "capture_has_full_messages": (
                        prompt_evidence["capture_has_full_messages"]),
                    "react_calls_exactly_three": (
                        shim_after_final["react_calls"] == 3),
                }, details=prompt_evidence)


                # Exact source replay is a bounded API control, not the
                # ordinary UI path. It must not create a second effect.
                tasks_before_duplicate = durable["counts"][
                    "tasks_on_scratch_board"]
                calls_before_duplicate = D3._shim_snapshot(
                    args.shim_port)["calls"]
                duplicate = _post_source_answer(
                    api, fixture["agent_id"], job_id, source_row,
                    str(wait1.get("correlation_id") or ""))
                durable_after_duplicate = _source_durable_state(
                    db_path, fixture["agent_id"], job_id, execution_id,
                    fixture["board_id"])
                step("duplicate_source_replay_idempotent", {
                    "status_409_or_already_resumed": (
                        duplicate["status"] == 409
                        or (duplicate["status"] == 200
                            and duplicate["data"].get("already_resumed")
                            is True)),
                    "http_200_alone_not_success": (
                        duplicate["status"] != 200
                        or duplicate["data"].get("already_resumed") is True),
                    "same_task_count": (
                        durable_after_duplicate["counts"][
                            "tasks_on_scratch_board"]
                        == tasks_before_duplicate),
                    "no_new_provider_call": (
                        D3._shim_snapshot(args.shim_port)["calls"]
                        == calls_before_duplicate),
                    "job_still_success": (
                        durable_after_duplicate["job"]["status"] == "success"),
                }, details={"status": duplicate["status"],
                            "data": D3._public_job(duplicate["data"])})

                step("no_new_objective_or_manual_advance", {
                    "single_run_post": len(run_posts) == 1,
                    "single_answer_post": len(answer_posts) == 1,
                    "no_advance_request": not advance_paths,
                    "one_job_for_agent": (
                        durable_after_duplicate["counts"]["jobs_for_agent"]
                        == 1),
                }, details={"run_posts": run_posts,
                            "answer_posts": answer_posts,
                            "advance_paths": advance_paths})

                foreign = list(net.foreign)
                forbidden_seen = []
                for entry in requests_seen:
                    for port, label in FORBIDDEN_PORTS.items():
                        if f":{port}" in entry["origin"]:
                            forbidden_seen.append(
                                {"origin": entry["origin"], "label": label,
                                 "path": entry["path"]})
                backend_origin_seen = any(
                    f":{args.backend_port}" in entry["origin"]
                    for entry in requests_seen)
                non_loopback = [
                    entry for entry in requests_seen
                    if entry.get("host") not in (
                        "localhost", "127.0.0.1", "::1")
                ]
                step("browser_origins_isolated", {
                    "no_forbidden_origin": (
                        not foreign and not forbidden_seen),
                    "no_non_loopback_origin": not non_loopback,
                    "backend_origin_observed": backend_origin_seen,
                    "frontend_origin_observed": any(
                        f":{args.frontend_port}" in entry["origin"]
                        for entry in requests_seen),
                }, details={
                    "foreign": foreign[:20],
                    "forbidden_seen": forbidden_seen[:20],
                    "non_loopback": non_loopback[:20],
                    "request_count": len(requests_seen),
                })
                context.close()
                browser.close()

            capture_dir = out / "capture"
            capture_dir.mkdir(parents=True, exist_ok=True)
            with open(capture_dir / "requests.jsonl", "w",
                      encoding="utf-8") as fh:
                for entry in requests_seen:
                    fh.write(json.dumps(entry, sort_keys=False) + "\n")
            _write_json(out / "stack.json", stack)
            scenario["status"] = "pass"
            scenario["finished_at"] = _now()
    except Exception as exc:  # noqa: BLE001 - preserve evidence, fail loud
        scenario["status"] = "fail"
        scenario["error"] = f"{type(exc).__name__}: {exc}"
        scenario["finished_at"] = _now()
        import traceback
        scenario["traceback"] = traceback.format_exc()[-4000:]
        print(f"[execute] FAILED: {scenario['error']}", file=sys.stderr)
    finally:
        if not args.keep_stack:
            for role, proc in reversed(cleanups):
                try:
                    if role == "backend":
                        R.stop_server(proc)
                    elif role == "frontend":
                        D3._stop_frontend_group(proc)
                    else:
                        from scripts.orchestration_acceptance import (
                            case5_browser_recovery as C5,
                        )
                        C5.terminate_proc(proc)
                except Exception as exc:  # noqa: BLE001 - recorded
                    scenario.setdefault("teardown_errors", []).append(
                        f"{role}: {type(exc).__name__}: {exc}")
            for port in (args.frontend_port, args.backend_port,
                         args.shim_port):
                try:
                    from scripts.orchestration_acceptance import (
                        case5_browser_recovery as C5,
                    )
                    C5.wait_port_free(port, deadline_s=20.0)
                except Exception as exc:  # noqa: BLE001 - recorded
                    scenario.setdefault("teardown_errors", []).append(
                        f"port {port}: {type(exc).__name__}: {exc}")

        stack["teardown"] = {
            "kept": bool(args.keep_stack),
            "errors": scenario.get("teardown_errors") or [],
            "ports_free": {
                str(port): D3._port_free(port)
                for port in (args.frontend_port, args.backend_port,
                             args.shim_port)
            },
        }
        _write_json(out / "stack.json", stack)
        _write_json(out / "scenario.json", scenario)
        if shim_capture_path.exists():
            shutil.copy2(shim_capture_path, out / "shim_capture.jsonl")
        _write_manifest(out, source_commit=(
            (stack.get("source") or {}).get("head") or "unknown"))
        print(f"[execute] evidence written to {out}")
    return 0 if scenario.get("status") == "pass" else 1


def _write_manifest(out: Path, source_commit: str) -> None:
    files: List[Dict[str, Any]] = []
    for path in sorted(out.rglob("*")):
        if not path.is_file() or path.name == "MANIFEST.json":
            continue
        files.append({
            "path": str(path.relative_to(out)),
            "sha256": _sha256_file(path),
            "bytes": path.stat().st_size,
        })
    _write_json(out / "MANIFEST.json", {
        "kind": "browser_agent_source_answer_evidence_manifest",
        "generated_at": _now(),
        "source_commit": source_commit,
        "labels": LABELS,
        "files": files,
    })


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Prepared driver for one ordinary UI authorized-source answer. "
            "Default is --preflight; root owns --execute."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Preparation preflight needs TESTING=1 and explicit fresh scratch "
            "DATABASE_URL/ATOM_DATA_DIR/ATOM_OFFICE_DIR. It never launches a "
            "world, browser, app model/provider or live credential."))
    ap.add_argument("--preflight", action="store_true",
                    help="validate source/environment/schema only (default)")
    ap.add_argument("--execute", action="store_true",
                    help="root-owned world/browser execution")
    ap.add_argument("--world", default=None,
                    help="acceptance world name (default browser_source_<HEAD10>)")
    ap.add_argument("--backend-port", type=int, default=8041)
    ap.add_argument("--frontend-port", type=int, default=3141)
    ap.add_argument("--shim-port", type=int, default=8098)
    ap.add_argument("--out", default="",
                    help="evidence/report directory")
    ap.add_argument("--report", default="",
                    help="preflight JSON path (default <out>/preflight.json)")
    ap.add_argument("--expect-source-sha", default="",
                    help="require this exact HEAD")
    ap.add_argument("--admin-password-file", default="",
                    help="0600 scratch admin password file (execute only)")
    ap.add_argument("--provision-admin-password", action="store_true",
                    help="provision a scratch admin password via app bootstrap")
    ap.add_argument("--headed", action="store_true",
                    help="show the browser (execute only; default headless)")
    ap.add_argument("--keep-stack", action="store_true",
                    help="leave the scratch stack running for inspection")
    args = ap.parse_args(argv)
    if args.preflight and args.execute:
        ap.error("--preflight and --execute are mutually exclusive")
    if not args.world:
        args.world = _default_world_name()
    if args.execute:
        return _run_scenario(args)
    return _run_preflight(args)


if __name__ == "__main__":
    raise SystemExit(main())
