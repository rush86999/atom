#!/usr/bin/env python3
"""Thin browser acceptance driver for the TASK-WAIT-01 Agents-page scenario.

PREPARATION SCOPE (2026-11-07)
=============================
This file was written and preflighted on the combined source candidate. It
does **not** launch a world, a browser, an application model/provider or a
live account. Root owns the actual browser capture. The `--preflight` path is
safe to run anywhere: it validates the authored provider envelopes against the
real ``core.react_models.ReActStep`` schema and the existing
``provider_shim`` script index, records the source/dependency/world checks it
did and did not run, and writes a small JSON report.

The `--execute` path composes the existing harness instead of reimplementing
it:

* ``backend/scripts/orchestration_acceptance/run_isolated.py``
  (``build_world``, ``launch_server``, ``stop_server``, ``launch_shim``,
  ``current_run_db``, storage estimate/guard hooks)
* ``backend/scripts/orchestration_acceptance/provider_shim.py``
  (loopback OpenAI-compatible authored completions; provider response only)
* ``backend/scripts/orchestration_acceptance/case5_browser_recovery.py``
  (``start_frontend_copy``, ``terminate_proc``, ``wait_port_free``,
  ``NetWatch``)
* ``backend/scripts/orchestration_acceptance/browser_verify.py``
  (``ui_login`` — the real login form, never token/cookie seeding)

Only the provider response is substituted. Routing, execution, persistence,
wait/resume, the registered ``tasks.create`` action and the default oracle run
in production code. The authored ReAct steps are labelled everywhere as
simulated model decisions / controlled transport; they do not prove served
model quality or general judgment.

Scenario (one job, no second job):
  login -> enabled agent Run objective -> durable question 1 -> real backend
  and frontend restart while waiting -> same job answer -> question 2 ->
  page reload -> same job answer -> real registered ``tasks.create`` /
  default oracle -> one durable BoardTask. Duplicate-answer and stale-answer
  negatives run on the same job; no separate cancelled-job is created.

Usage
-----
Preparation only (no world/browser/model)::

    TESTING=1 \\
    DATABASE_URL=sqlite:////tmp/atom-browser-preflight/atom.db \\
    ATOM_DATA_DIR=/tmp/atom-browser-preflight/data \\
    ATOM_OFFICE_DIR=/tmp/atom-browser-preflight/office \\
    python3 scripts/acceptance/browser_agent_job_wait.py --preflight \\
        --out /tmp/atom-browser-preflight/report

Root-owned execution (from the frozen capture worktree, prepared venv)::

    python scripts/acceptance/browser_agent_job_wait.py --execute \\
        --world browser_wait_<unique> --backend-port 8031 \\
        --frontend-port 3131 --shim-port 8097 \\
        --out <scratch-evidence>/browser_wait_<sha10> \\
        --provision-admin-password   # or --admin-password-file <0600 file>

The driver refuses an existing world, refuses the live dev DB, calls the world
storage guard before ``build_world``, measures disk through the existing
``storage_policy`` estimate, and never passes ``ATOM_WORLD_STORAGE_BYPASS``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Schema/consumer imports are deliberately light: no DB engine is opened here.
from core.react_models import ReActStep  # noqa: E402
from scripts.orchestration_acceptance import provider_shim  # noqa: E402
from scripts.orchestration_acceptance import run_isolated as R  # noqa: E402

FIXTURE = Path(__file__).with_name("fixtures") / "browser_agent_job_wait_shim.json"
AGENT_NAME = "Wait Acceptance Employee"
AGENT_CATEGORY = "acceptance"
BOARD_NAME = "Browser wait acceptance"
OBJECTIVE = (
    "Create a closing task after asking me for its exact title and priority."
)
Q1 = "What title should the closing task have?"
Q2 = "What priority should the closing task have?"
TITLE_ANSWER = "Quarterly close checklist"
PRIORITY_ANSWER = "high"
FINAL_ANSWER = "Created the closing task from both authorized facts."
ADMIN_EMAIL = "admin@example.com"

FORBIDDEN_PORTS = {3000: "user frontend", 8001: "user backend",
                   8000: "atom-saas backend"}
SHIM_DEFAULT_LABEL = (
    "SIMULATED CONTROL TRANSPORT: no authored ReAct completion matched this "
    "request."
)
WAIT_ACTION_TYPE = "agent_information_request"

LABELS = {
    "model_decisions": (
        "SIMULATED MODEL DECISIONS: authored provider completions served by "
        "the existing loopback provider shim. Not served-model output."
    ),
    "transport": (
        "CONTROLLED TRANSPORT: only the provider response is substituted; "
        "routing, execution, persistence, wait/resume, tasks.create and the "
        "default oracle run in production code."
    ),
    "not_claimed": [
        "served model or provider quality",
        "general model judgment or prompt quality",
        "a second job or a synthetic completed DB row",
        "any live provider, account, credential, send, spend or download",
    ],
}


class PreflightError(RuntimeError):
    pass


class DriverError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------
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


def _git(*argv: str) -> str:
    try:
        out = subprocess.run(
            ["git", *argv], cwd=str(REPO), capture_output=True, text=True,
            timeout=30)
        return out.stdout.strip()
    except Exception:
        return ""


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


def _db_path_from_url(url: str) -> Path:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise PreflightError(
            "DATABASE_URL must be an explicit sqlite:/// scratch URL")
    raw = url[len(prefix):]
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _origin(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else ""


def _path_of(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).path


def _port_free(port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def _process_cwd(pid: int) -> Optional[str]:
    """Best-effort node/backend cwd observation (macOS lsof)."""
    try:
        proc = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True, text=True, timeout=10)
        for line in proc.stdout.splitlines():
            if line.startswith("n"):
                return line[1:]
    except Exception:
        return None
    return None


def _same_path(observed: Any, expected: Any) -> bool:
    """Exact resolved-path equality; absent/unreadable observations fail."""
    if not observed or not expected:
        return False
    try:
        return Path(str(observed)).resolve() == Path(str(expected)).resolve()
    except Exception:
        return False


def _frontend_cwd_matches(observed: Optional[str], expected: Path) -> bool:
    """A frontend cwd is valid only when OBSERVED and exactly the world copy."""
    return _same_path(observed, expected)


def _manifest_subset_hash(manifest: Dict[str, str],
                          prefix: str = "") -> Dict[str, Any]:
    subset = {
        str(path): str(digest)
        for path, digest in (manifest or {}).items()
        if str(path).startswith(prefix)
    }
    encoded = json.dumps(sorted(subset.items()), separators=(",", ":")).encode()
    return {
        "prefix": prefix,
        "file_count": len(subset),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _backend_source_binding(
    *,
    frozen_source_sha: str,
    source_head: str,
    preflight: Dict[str, Any],
    manifest: Dict[str, Any],
    code_manifest: Dict[str, str],
    export_tree: Dict[str, str],
    health_identity: Dict[str, Any],
    descriptor: Dict[str, Any],
    world: Path,
) -> Dict[str, Any]:
    """Bind the initial server to the frozen source and its exported files.

    The world MANIFEST has no source_revision, so absence is recorded but is
    never allowed to satisfy the check. Certification is the chain:
    frozen source == preflight source, exported tree == code_manifest, and the
    running server cwd/export path is exactly this world's backend_root.
    """
    health = health_identity or {}
    desc = descriptor or {}
    manifest_rev = (manifest or {}).get("source_revision")
    backend_export = _manifest_subset_hash(code_manifest, "backend/")
    whole_export = _manifest_subset_hash(code_manifest, "")
    expected_export = (Path(world) / "backend_root").resolve()
    checks = {
        "frozen_source_sha_present": bool(frozen_source_sha),
        "frozen_source_matches_head": (
            bool(frozen_source_sha)
            and str(frozen_source_sha) == str(source_head)),
        "preflight_source_matches_frozen": (
            bool(frozen_source_sha)
            and str((preflight or {}).get("source_revision") or "")
            == str(frozen_source_sha)),
        "manifest_export_hash_present": bool(
            (manifest or {}).get("code_snapshot_sha256")
            or (manifest or {}).get("code_archive_sha256")),
        "manifest_source_revision_not_conflicting": (
            manifest_rev is None
            or (bool(frozen_source_sha)
                and str(manifest_rev) == str(frozen_source_sha))),
        "export_tree_matches_code_manifest": (
            export_tree == code_manifest),
        "backend_export_hash_present": backend_export["file_count"] > 0,
        "health_cwd_exact": _same_path(health.get("cwd"), expected_export),
        "descriptor_export_exact": _same_path(
            desc.get("export_path"), expected_export),
        "health_source_id_observed": bool(health.get("source_id")),
    }
    return {
        **checks,
        "ok": all(checks.values()),
        "certified_by": (
            "frozen_source+preflight_source+export_tree+backend_export+"
            "isolated_cwd+descriptor"),
        "frozen_source_sha": frozen_source_sha,
        "source_head": source_head,
        "preflight_source_revision": (preflight or {}).get("source_revision"),
        "manifest_source_revision": manifest_rev,
        "manifest_source_revision_present": manifest_rev is not None,
        "code_snapshot_sha256": (manifest or {}).get("code_snapshot_sha256"),
        "code_archive_sha256": (manifest or {}).get("code_archive_sha256"),
        "export_tree": whole_export,
        "backend_export": backend_export,
        "health_source_id": health.get("source_id"),
        "health_source_id_is_unknown": (
            str(health.get("source_id") or "").startswith("unknown")),
        "health_cwd": health.get("cwd"),
        "descriptor_export_path": desc.get("export_path"),
    }


def _stop_frontend_group(proc: Any) -> None:
    """Stop the frontend's own process group, then fall back to terminate."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        pass
    try:
        proc.wait(timeout=15)
        return
    except Exception:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------
def _require_scratch_env() -> Dict[str, Any]:
    """Enforce an explicit fresh scratch DB/data/office for preparation.

    This is the LIVE-DB-WIPE guard, not a convenience check. The driver only
    imports schema modules here, but an accidental ``core.database`` import
    must never be able to resolve the user's dev database.
    """
    problems: List[str] = []
    testing = os.environ.get("TESTING")
    db_url = os.environ.get("DATABASE_URL", "")
    data_raw = os.environ.get("ATOM_DATA_DIR", "")
    office_raw = os.environ.get("ATOM_OFFICE_DIR", "")

    if testing != "1":
        problems.append("TESTING=1 is required for the preparation preflight")
    if not db_url:
        problems.append("DATABASE_URL is required")
    if not data_raw:
        problems.append("ATOM_DATA_DIR is required")
    if not office_raw:
        problems.append("ATOM_OFFICE_DIR is required")
    if problems:
        raise PreflightError("; ".join(problems))

    try:
        db_path = _db_path_from_url(db_url)
    except PreflightError as exc:
        problems.append(str(exc))
        db_path = Path("/nonexistent")

    data_path = Path(data_raw).expanduser().resolve()
    office_path = Path(office_raw).expanduser().resolve()
    live_db = (BACKEND / "data" / "atom.db").resolve()
    live_data = (BACKEND / "data").resolve()
    live_office = (BACKEND / "data" / "office").resolve()

    if db_path == live_db or live_data in db_path.parents:
        problems.append(f"DATABASE_URL resolves inside the live data tree: {db_path}")
    if data_path == live_data or live_data in data_path.parents:
        problems.append(f"ATOM_DATA_DIR resolves inside the live data tree: {data_path}")
    if office_path == live_office or live_data in office_path.parents:
        problems.append(f"ATOM_OFFICE_DIR resolves inside the live data tree: {office_path}")
    if not db_path.parent.is_dir():
        problems.append(f"DATABASE_URL parent does not exist: {db_path.parent}")
    if not data_path.is_dir():
        problems.append(f"ATOM_DATA_DIR does not exist: {data_path}")
    if not office_path.is_dir():
        problems.append(f"ATOM_OFFICE_DIR does not exist: {office_path}")
    if problems:
        raise PreflightError("; ".join(problems))

    return {
        "testing": testing,
        "database_url": db_url,
        "database_path": str(db_path),
        "database_is_live_dev_db": False,
        "data_dir": str(data_path),
        "office_dir": str(office_path),
        "scratch_ok": True,
    }


def _source_probe(expected_sha: Optional[str] = None) -> Dict[str, Any]:
    head = _git("rev-parse", "HEAD")
    tracked_status = _git("status", "--porcelain=v1", "--untracked-files=no")
    backend_status = _git("status", "--porcelain=v1", "--", "backend")
    dirty_tracked = [ln for ln in tracked_status.splitlines() if ln.strip()]
    dirty_backend = [ln for ln in backend_status.splitlines() if ln.strip()]
    runtime: Dict[str, Any] = {}
    try:
        from core.runtime_identity import capture_runtime_identity
        ident = capture_runtime_identity()
        runtime = {
            "source_id": ident.source_id,
            "revision": ident.revision,
            "dirty": ident.dirty,
            "dirty_paths_count": len(ident.dirty_paths),
            "untracked_paths_count": len(ident.untracked_paths),
            "error": ident.error,
        }
    except Exception as exc:  # noqa: BLE001 - reported, not hidden
        runtime = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "repo": str(REPO),
        "head": head or "unknown",
        "expected_sha": expected_sha or None,
        "matches_expected": (
            bool(expected_sha) and head == expected_sha
            if expected_sha else None),
        "tracked_dirty": dirty_tracked[:50],
        "tracked_dirty_count": len(dirty_tracked),
        "backend_dirty": dirty_backend[:50],
        "backend_dirty_count": len(dirty_backend),
        "driver_sha256": _sha256_file(Path(__file__).resolve()),
        "driver_path": str(Path(__file__).resolve()),
        "runtime_identity": runtime,
    }


def _dependency_probe() -> Dict[str, Any]:
    import importlib.util
    mods = {}
    for name in ("pydantic", "httpx", "playwright", "sqlalchemy",
                 "fastapi", "uvicorn", "instructor"):
        mods[name] = importlib.util.find_spec(name) is not None
    node = shutil.which("node")
    node_version = ""
    if node:
        try:
            node_version = subprocess.run(
                [node, "--version"], capture_output=True, text=True,
                timeout=10).stdout.strip()
        except Exception:
            node_version = ""
    return {
        "interpreter": sys.version.split()[0],
        "interpreter_path": sys.executable,
        "modules": mods,
        "node": node,
        "node_version": node_version,
        "chrome_app": Path("/Applications/Google Chrome.app").exists(),
        "venv314_python": (BACKEND / "venv314" / "bin" / "python").exists(),
        "frontend_node_modules": (
            REPO / "frontend-nextjs" / "node_modules").exists(),
    }


def _schema_probe(scratch_dir: Path) -> Dict[str, Any]:
    """Validate authored envelopes against the real ReActStep schema."""
    sample = {
        "__BOARD_ID__": "board-preflight",
        "__COLUMN_ID__": "column-preflight",
        "__TITLE_ANSWER__": TITLE_ANSWER,
        "__PRIORITY_ANSWER__": PRIORITY_ANSWER,
    }
    doc = _fill_fixture(sample)
    responses = doc.get("responses")
    if not isinstance(responses, list) or not responses:
        raise PreflightError("fixture has no responses")

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
        elif parsed.actions:
            kind = "actions"
            detail = {"tools": [a.tool for a in parsed.actions]}
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

    wait_q = [
        s for s in steps
        if s["kind"] == "information_wait"
        and s["detail"].get("question") == Q1
    ]
    wait_p = [
        s for s in steps
        if s["kind"] == "information_wait"
        and s["detail"].get("question") == Q2
    ]
    actions = [
        s for s in steps
        if s["kind"] == "action"
        and (s["detail"].get("tool") or "") == "tasks.create"
    ]
    finals = [
        s for s in steps
        if s["kind"] == "final_answer"
        and FINAL_ANSWER in str(s["detail"].get("final_answer") or "")
    ]
    if not wait_q or wait_q[0]["detail"].get("missing_fact") != "task title":
        raise PreflightError("first information_wait does not request the title")
    if not wait_p or wait_p[0]["detail"].get("missing_fact") != "priority":
        raise PreflightError("second information_wait does not request priority")
    if not actions:
        raise PreflightError("no tasks.create action envelope")
    if not finals:
        raise PreflightError("no final-answer envelope")
    for action in actions:
        params = action["detail"].get("params") or {}
        if (params.get("board_id") != "board-preflight"
                or params.get("column_id") != "column-preflight"
                or params.get("title") != TITLE_ANSWER
                or params.get("priority") != PRIORITY_ANSWER):
            raise PreflightError(
                "tasks.create envelope does not bind the scratch board/column "
                "and the two authorized answers")

    # Shim selection is "first matching entry in script order". The more
    # specific resumed states must precede the bare first-wait fallback.
    final_index = finals[0]["index"]
    action_indexes = [a["index"] for a in actions]
    wait_p_index = wait_p[0]["index"]
    wait_q_index = wait_q[0]["index"]
    if not (final_index < min(action_indexes) < wait_p_index < wait_q_index):
        raise PreflightError(
            "script order would let a less-specific state shadow a later "
            f"state (final={final_index}, action={action_indexes}, "
            f"priority={wait_p_index}, title={wait_q_index})")

    script_path = scratch_dir / "browser_agent_job_wait_shim.json"
    _write_json(script_path, doc)
    index = provider_shim.load_script(script_path)
    index_keys = [str(k) for k in index]
    tuple_keys = [k for k in index if isinstance(k, tuple)]
    if "ReActStep" not in index:
        raise PreflightError("provider_shim lost the bare ReActStep fallback")
    if len(tuple_keys) < 4:
        raise PreflightError(
            "provider_shim indexed fewer state-specific entries than authored")
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
        "provider_shim_index_keys": index_keys,
        "provider_shim_bare_fallback": "ReActStep" in index,
        "provider_shim_tuple_entries": len(tuple_keys),
        "default_labelled": SHIM_DEFAULT_LABEL in str(doc.get("default") or ""),
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
        "tool_name_source": (
            "response_model.__name__, the tool name instructor's OpenAI "
            "TOOLS handler emits; confirmed by source inspection at "
            "preparation, not exercised against a live provider here"),
        "envelope": {
            "message.tool_calls[0].function.name": "ReActStep",
            "arguments": "a JSON object validated as ReActStep",
        },
        "selection_protocol": [
            "(tool, match) exact entry, script order wins",
            "bare tool entry (first wait fallback)",
            "substring entry",
            "labelled default text",
        ],
        "state_selection": (
            "from durable prompt history: no fact -> first wait; authorized "
            "title -> second wait; authorized priority block -> tasks.create; "
            "oracle_verified observation -> final answer. No process counter."),
        "server_acceptance_exercised": False,
        "server_acceptance_note": (
            "The real shim Handler and the real structured consumer are not "
            "started by --preflight; root's --execute run exercises them."),
    }


def _storage_probe(world: Path) -> Dict[str, Any]:
    try:
        import core.world_storage_guard as WSG
        cfg = WSG.load_config()
        return {
            "guard_invoked": False,
            "enabled": getattr(cfg, "enabled", None),
            "layout": getattr(cfg, "layout", None),
            "worlds_root": str(getattr(cfg, "root", "") or ""),
            "world_exists": world.exists(),
            "execute_will_call": "core.world_storage_guard.require_storage_ready",
            "reason_not_invoked": (
                "preparation only; --execute calls the guard before build_world "
                "and never sets ATOM_WORLD_STORAGE_BYPASS"),
        }
    except Exception as exc:  # noqa: BLE001 - reported
        return {
            "guard_invoked": False,
            "error": f"{type(exc).__name__}: {exc}",
            "world_exists": world.exists(),
            "execute_will_call": "core.world_storage_guard.require_storage_ready",
        }


def _world_path(name: str) -> Path:
    return BACKEND / "data" / "acceptance_worlds" / name


def _run_preflight(args: argparse.Namespace) -> int:
    try:
        ctx = _require_scratch_env()
        source = _source_probe(args.expect_source_sha)
        if args.expect_source_sha and source.get("matches_expected") is not True:
            raise PreflightError(
                f"HEAD {source['head']} does not match --expect-source-sha "
                f"{args.expect_source_sha}")
        if source.get("backend_dirty_count"):
            raise PreflightError(
                "backend working tree is dirty; a working-tree export would "
                "not be the frozen candidate")
        deps = _dependency_probe()
        ports = {str(p): _port_free(p)
                 for p in (args.backend_port, args.frontend_port, args.shim_port)}
        world = _world_path(args.world)
        storage = _storage_probe(world)
        with tempfile.TemporaryDirectory(
                dir=ctx["data_dir"], prefix="schema-preflight-") as tmp:
            schema = _schema_probe(Path(tmp))

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
                "backend/venv314/bin/python is absent in this worktree; "
                "--execute needs the prepared acceptance interpreter")
        if not deps["frontend_node_modules"]:
            warnings.append(
                "frontend-nextjs/node_modules is absent in this worktree; "
                "--execute must run from the installed capture worktree")
        if world.exists():
            warnings.append(f"world {args.world!r} already exists; --execute requires a fresh name")
        if not all(ports.values()):
            warnings.append(
                "not all requested ports are free right now: "
                + ", ".join(f"{p}={v}" for p, v in ports.items()))

        checks = {
            "scratch_environment": ctx["scratch_ok"],
            "source_head_recorded": bool(source.get("head")),
            "source_expected_sha_ok": (
                source.get("matches_expected") is not False),
            "backend_tree_clean": source.get("backend_dirty_count") == 0,
            "react_schema_envelopes": True,
            "provider_shim_index": schema["provider_shim_bare_fallback"],
            "default_labelled": schema["default_labelled"],
        }
        report = {
            "kind": "browser_agent_job_wait_preflight",
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
            "environment": ctx,
            "schema": schema,
            "protocol": _protocol_record(),
            "dependencies": deps,
            "ports": ports,
            "world": {
                "name": args.world,
                "path": str(world),
                "exists": world.exists(),
                "required_fresh": True,
            },
            "storage_guard": storage,
            "warnings": warnings,
            "not_exercised": [
                "world build / storage guard acceptance",
                "backend or frontend launch",
                "Playwright browser or login form",
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
                "python3 scripts/acceptance/browser_agent_job_wait.py "
                "--preflight --out <report-dir>"),
        }
        target = Path(args.report) if args.report else (
            Path(args.out) / "preflight.json" if args.out else None)
        if target is None:
            raise PreflightError("--preflight needs --report or --out")
        target = target.resolve()
        _write_json(target, report)
        print(f"[preflight] ok={report['ok']} report={target}")
        print(f"[preflight] schema={schema['response_count']} envelopes, "
              f"tool={schema['tool_name']}, "
              f"shim_keys={len(schema['provider_shim_index_keys'])}")
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


# ---------------------------------------------------------------------------
# execution helpers
# ---------------------------------------------------------------------------
def _prepare_execute_environment(args: argparse.Namespace) -> Dict[str, Any]:
    """Point the driver's own imports at a harmless scratch DB.

    The server gets its own explicit DATABASE_URL from launch_server. This
    only protects the driver process from a stray ``core.database`` import
    resolving the live dev DB.
    """
    scratch = Path(tempfile.mkdtemp(prefix="atom-browser-driver-"))
    (scratch / "data").mkdir()
    (scratch / "office").mkdir()
    os.environ["DATABASE_URL"] = f"sqlite:///{scratch / 'driver_schema.db'}"
    os.environ["ATOM_DATA_DIR"] = str(scratch / "data")
    os.environ["ATOM_OFFICE_DIR"] = str(scratch / "office")
    return {
        "driver_scratch": str(scratch),
        "database_url": os.environ["DATABASE_URL"],
        "testing": os.environ.get("TESTING"),
        "live_db_touched": False,
    }


def _check_execute_ready(args: argparse.Namespace) -> Dict[str, Any]:
    deps = _dependency_probe()
    missing = [name for name, present in deps["modules"].items()
               if name in ("httpx", "playwright") and not present]
    if missing:
        raise DriverError(f"missing python modules for --execute: {missing}")
    if not deps["node"]:
        raise DriverError("node is not on PATH")
    if not deps["chrome_app"]:
        raise DriverError(
            "Google Chrome.app not found; Playwright is configured for "
            "channel='chrome' and must not install a browser")
    if not deps["venv314_python"]:
        raise DriverError(
            "backend/venv314/bin/python is absent; run from the prepared "
            "capture worktree (root owns that worktree)")
    if not deps["frontend_node_modules"]:
        raise DriverError(
            "frontend-nextjs/node_modules is absent; run from the installed "
            "capture worktree; no npm install is permitted")
    ports = {p: _port_free(p) for p in
             (args.backend_port, args.frontend_port, args.shim_port)}
    busy = [p for p, free in ports.items() if not free]
    if busy:
        raise DriverError(f"ports already in use: {busy}")
    return {"dependencies": deps, "ports": {str(k): v for k, v in ports.items()}}


def _build_world(world: Path, frozen_source_sha: str) -> Dict[str, Any]:
    from core.world_storage_guard import require_storage_ready
    require_storage_ready()
    if world.exists():
        raise DriverError(
            f"world {world.name!r} already exists; this driver requires a "
            "unique fresh world and does not delete or rebuild one")
    # preflight() resolves the source from R.WORKTREE. The snapshot export is
    # taken from this driver's REPO, so bind the harness's source identity to
    # the same worktree instead of its historical default.
    R.WORKTREE = REPO
    disk = R._check_disk_before_world(world).as_dict()
    R.build_world.snapshot_working_tree = True
    R.build_world.full_dev_db = False
    R.build_world(world, refreeze_db=True)
    manifest = world / "MANIFEST.json"
    fixture = world / "fixture" / "atom.db"
    if not manifest.exists() or not fixture.exists():
        raise DriverError("world build did not produce MANIFEST.json/fixture/atom.db")
    manifest_doc = _load_json(manifest)
    pre = R.preflight(world)
    code_manifest = _load_json(world / "code_manifest.json")
    export_tree = R._tree_manifest(world / "code")
    if pre.get("source_revision") != frozen_source_sha:
        raise DriverError(
            "harness preflight source revision does not match the frozen "
            f"source: {pre.get('source_revision')!r} != {frozen_source_sha!r}")
    if export_tree != code_manifest:
        raise DriverError(
            "exported code tree does not match code_manifest.json; the files "
            "that would run are not the frozen snapshot")
    return {
        "world": str(world),
        "disk_preflight": disk,
        "manifest_path": str(manifest),
        "fixture_path": str(fixture),
        "preflight": pre,
        "manifest_doc": manifest_doc,
        "code_manifest": code_manifest,
        "export_tree": export_tree,
        "source_revision": manifest_doc.get("source_revision"),
        "code_snapshot_sha256": manifest_doc.get("code_snapshot_sha256"),
        "code_archive_sha256": manifest_doc.get("code_archive_sha256"),
        "code_source": manifest_doc.get("code_source"),
        "fixture_source": manifest_doc.get("fixture_source"),
        "backend_export": _manifest_subset_hash(code_manifest, "backend/"),
        "export": _manifest_subset_hash(code_manifest, ""),
    }


def _health(port: int) -> Dict[str, Any]:
    import httpx
    response = httpx.get(f"http://127.0.0.1:{port}/api/health",
                         timeout=10, trust_env=False)
    response.raise_for_status()
    return response.json()


def _api_client(port: int, token: Optional[str] = None):
    import httpx
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=f"http://127.0.0.1:{port}",
                        headers=headers, timeout=120, trust_env=False)


def _safe_error_body(response: Any) -> Any:
    try:
        body = response.json()
    except Exception:
        return {"status": response.status_code}
    detail = body.get("detail")
    if isinstance(detail, dict):
        detail = {
            "code": (detail.get("error") or {}).get("code")
            if isinstance(detail.get("error"), dict) else detail.get("code"),
            "message": (detail.get("error") or {}).get("message")
            if isinstance(detail.get("error"), dict) else detail.get("message"),
        }
    elif not isinstance(detail, str):
        detail = str(detail)[:300] if detail is not None else None
    return {
        "status": response.status_code,
        "success": body.get("success"),
        "detail": detail,
        "error": body.get("error") if isinstance(body.get("error"), str) else None,
    }


def _api_login(port: int, password: str) -> Tuple[str, Dict[str, Any]]:
    with _api_client(port) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": ADMIN_EMAIL, "password": password})
    if response.status_code != 200:
        raise DriverError(
            f"admin login failed ({response.status_code}); the password "
            "source did not authenticate this scratch world")
    body = response.json()
    if body.get("two_factor_required"):
        raise DriverError("scratch admin unexpectedly requires 2FA")
    token = str(body.get("access_token") or "")
    if not token:
        raise DriverError("admin login returned no access_token")
    return token, {"status": response.status_code, "token_present": True}


def _provision_admin(world: Path, db_path: Path, run_dir: Path,
                     password: str) -> Dict[str, Any]:
    """Provision/refresh the scratch admin via the app's own bootstrap.

    This is a normal fixture user, created through ``core.admin_bootstrap``,
    not a direct AgentJob/result/plan/receipt row. The password is passed in
    the child environment and in memory only; it is never written to evidence.
    """
    data_dir = run_dir / "data"
    office_dir = data_dir / "office"
    office_dir.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != "TESTING"}
    env.update({
        "DATABASE_URL": f"sqlite:///{db_path}",
        "ATOM_DATA_DIR": str(data_dir),
        "ATOM_OFFICE_DIR": str(office_dir),
        "ADMIN_PASSWORD": password,
        "ATOM_BOOTSTRAP_PASSWORD_FILE": str(
            world / "bootstrap_admin_password.txt"),
    })
    code = (
        "from core.admin_bootstrap import ensure_admin_user; "
        "ensure_admin_user()")
    proc = subprocess.run(
        [str(R.VENV_PY), "-c", code], cwd=str(BACKEND), env=env,
        capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-800:]
        raise DriverError(
            f"scratch admin bootstrap failed rc={proc.returncode}: {tail}")
    return {
        "source": "driver-provisioned scratch ADMIN_PASSWORD via "
                  "core.admin_bootstrap.ensure_admin_user",
        "password_written_to_evidence": False,
    }


def _password_for_run(args: argparse.Namespace, world: Path,
                      db_path: Path, run_dir: Path) -> Tuple[str, Dict[str, Any]]:
    if args.admin_password_file:
        path = Path(args.admin_password_file)
        if not path.is_file():
            raise DriverError(f"admin password file not found: {path}")
        return path.read_text(encoding="utf-8").strip(), {
            "source": "admin-password-file (contents not recorded)"}
    env_password = os.environ.get("ATOM_PREVIEW_PASSWORD")
    if env_password:
        return env_password, {
            "source": "ATOM_PREVIEW_PASSWORD (value not recorded)"}
    if args.provision_admin_password:
        password = secrets.token_urlsafe(24)
        meta = _provision_admin(world, db_path, run_dir, password)
        return password, meta
    candidates = [
        world / "bootstrap_admin_password.txt",
        world / "backend_root" / "logs" / "bootstrap_admin_password.txt",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip(), {
                "source": f"world password file ({candidate.name}; value not recorded)"}
    raise DriverError(
        "no scratch admin password source. Pass --admin-password-file, set "
        "ATOM_PREVIEW_PASSWORD, or pass --provision-admin-password. The "
        "driver deliberately does not seed a cookie instead of the real form.")


def _setup_fixture(api: Any) -> Dict[str, Any]:
    created = api.post("/api/agents/custom", json={
        "name": AGENT_NAME,
        "description": "Scratch employee for the browser information-wait acceptance.",
        "category": AGENT_CATEGORY,
    })
    if created.status_code not in (200, 201):
        raise DriverError(f"agent create failed: {_safe_error_body(created)}")
    created_body = created.json()
    agent_id = str(((created_body.get("data") or {}).get("agent_id"))
                   or created_body.get("agent_id") or "")
    if not agent_id:
        raise DriverError("agent create returned no agent_id")
    promoted = api.post(f"/api/agents/{agent_id}/promote")
    if promoted.status_code != 200:
        raise DriverError(f"agent promote failed: {_safe_error_body(promoted)}")
    board = api.post("/api/boards", json={
        "name": BOARD_NAME,
        "seed_default_columns": True,
    })
    if board.status_code not in (200, 201):
        raise DriverError(f"board create failed: {_safe_error_body(board)}")
    board_body = board.json()
    board_id = str(board_body.get("id")
                   or (board_body.get("data") or {}).get("id") or "")
    if not board_id:
        raise DriverError("board create returned no board id")
    detail = api.get(f"/api/boards/{board_id}")
    if detail.status_code != 200:
        raise DriverError(f"board read failed: {_safe_error_body(detail)}")
    detail_body = detail.json()
    columns = detail_body.get("columns") or (
        detail_body.get("data") or {}).get("columns") or []
    if not columns or not columns[0].get("id"):
        raise DriverError("scratch board has no default columns")
    return {
        "agent_id": agent_id,
        "agent_name": AGENT_NAME,
        "agent_promote_status": promoted.status_code,
        "board_id": board_id,
        "board_name": BOARD_NAME,
        "column_id": str(columns[0]["id"]),
        "column_name": columns[0].get("name"),
    }


def _write_shim_script(world: Path, fixture: Dict[str, Any]) -> Path:
    path = world / "browser_agent_job_wait_shim.json"
    _write_json(path, fixture)
    return path


def _shim_snapshot(port: int) -> Dict[str, Any]:
    import httpx
    try:
        response = httpx.get(f"http://127.0.0.1:{port}/log",
                             timeout=5, trust_env=False)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:  # noqa: BLE001 - evidence records the gap
        return {"available": False, "error": f"{type(exc).__name__}: {exc}",
                "calls": 0, "react_calls": 0, "log": []}
    log = body.get("log") or []
    calls = [
        entry for entry in log
        if int(entry.get("messages") or 0) > 0
        and entry.get("model") != "(catalog-discovery)"
    ]
    react_calls = [
        entry for entry in calls
        if "ReActStep" in (entry.get("tool_names") or [])
    ]
    return {
        "available": True,
        "calls": len(calls),
        "react_calls": len(react_calls),
        "log": log,
    }


def _capture_contains(capture_path: Path, needles: List[str]) -> bool:
    if not capture_path.exists():
        return False
    for line in capture_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        blob = json.dumps(entry.get("messages_full") or entry)
        if any(needle and needle in blob for needle in needles):
            return True
    return False


def _capture_has_full_messages(capture_path: Path) -> bool:
    if not capture_path.exists():
        return False
    for line in capture_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        messages = entry.get("messages_full")
        if isinstance(messages, list) and messages:
            return True
    return False


def _public_wait(wait: Any) -> Any:
    if not isinstance(wait, dict):
        return None
    return {
        "id": wait.get("id"),
        "kind": wait.get("kind"),
        "status": wait.get("status"),
        "question": wait.get("question"),
        "missing_fact": wait.get("missing_fact"),
        "subject": wait.get("subject"),
        "correlation_id": wait.get("correlation_id"),
        "can_answer": wait.get("can_answer"),
    }


def _public_job(data: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "agent_id": data.get("agent_id"),
        "job_id": data.get("job_id"),
        "execution_id": data.get("execution_id"),
        "job_status": data.get("job_status"),
        "outcome": data.get("outcome"),
        "reason": data.get("reason"),
        "next_action": data.get("next_action"),
        "requires_reconciliation": data.get("requires_reconciliation"),
        "wait": _public_wait(data.get("wait")),
    }
    result = data.get("result")
    if isinstance(result, dict):
        out["result"] = {
            "status": result.get("status"),
            "output": result.get("output"),
        }
    return out


def _public_steps(steps: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(steps, list):
        return out
    for step in steps:
        if not isinstance(step, dict):
            continue
        action = step.get("action") if isinstance(step.get("action"), dict) else {}
        output = step.get("output") if isinstance(step.get("output"), dict) else {}
        task = output.get("task") if isinstance(output.get("task"), dict) else {}
        out.append({
            "action_tool": action.get("tool"),
            "oracle_verified": output.get("oracle_verified"),
            "task_id": output.get("task_id") or task.get("id"),
        })
    return out


def _read_job(api: Any, agent_id: str, job_id: str) -> Dict[str, Any]:
    response = api.get(f"/api/agents/{agent_id}/jobs/{job_id}")
    if response.status_code != 200:
        raise DriverError(f"job read failed: {_safe_error_body(response)}")
    body = response.json()
    data = body.get("data") or {}
    return {"status": response.status_code, "data": data,
            "public": _public_job(data)}


def _post_answer(api: Any, agent_id: str, job_id: str, answer: str,
                 correlation_id: str) -> Dict[str, Any]:
    response = api.post(
        f"/api/agents/{agent_id}/jobs/{job_id}/answer",
        json={"answer": answer, "correlation_id": correlation_id})
    try:
        body = response.json()
    except Exception:
        body = {}
    data = body.get("data") or {}
    return {
        "status": response.status_code,
        "success": body.get("success"),
        "detail": (body.get("detail")
                   if isinstance(body.get("detail"), str) else None),
        "data": data,
        "public": _public_job(data),
        "result_steps": _public_steps((data.get("result") or {}).get("steps")),
    }


def _wait_for_text(page: Any, selector: str, predicate: Any,
                   timeout_s: float = 180.0, label: str = "text") -> str:
    end = time.time() + timeout_s
    last = ""
    while time.time() < end:
        try:
            last = page.locator(selector).inner_text(timeout=2000).strip()
        except Exception:
            last = ""
        if predicate(last):
            return last
        page.wait_for_timeout(1000)
    raise DriverError(f"timed out waiting for {label} ({selector}); last={last!r}")


def _wait_selector(page: Any, selector: str, timeout_ms: int = 240000) -> None:
    page.wait_for_selector(selector, timeout=timeout_ms)


def _screenshot(page: Any, out: Path, name: str) -> str:
    shots = out / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    path = shots / name
    page.screenshot(path=str(path), full_page=True)
    return str(path.relative_to(out))


def _json_column(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}
    return {}


def _db_rows(db_path: Path, query: str, params: Tuple[Any, ...] = ()) -> List[Tuple[Any, ...]]:
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        con.row_factory = sqlite3.Row
        return [tuple(row) for row in con.execute(query, params).fetchall()]
    finally:
        con.close()


def _durable_state(db_path: Path, agent_id: str, job_id: str,
                   execution_id: str, board_id: str) -> Dict[str, Any]:
    jobs = _db_rows(
        db_path,
        "SELECT id, status, result_summary FROM agent_jobs WHERE id=?",
        (job_id,))
    executions = _db_rows(
        db_path,
        "SELECT id, status, result_summary FROM agent_executions WHERE id=?",
        (execution_id,))
    hitl = _db_rows(
        db_path,
        "SELECT id, status, action_type, user_feedback, context_snapshot, params "
        "FROM hitl_actions WHERE agent_id=? ORDER BY created_at, id",
        (agent_id,))
    tasks = _db_rows(
        db_path,
        "SELECT id, title, priority, status, board_id, column_id "
        "FROM board_tasks WHERE board_id=?",
        (board_id,))
    job_count = _db_rows(
        db_path, "SELECT COUNT(*) FROM agent_jobs WHERE agent_id=?",
        (agent_id,))[0][0]
    execution_count = _db_rows(
        db_path, "SELECT COUNT(*) FROM agent_executions WHERE id=?",
        (execution_id,))[0][0]
    task_count = _db_rows(
        db_path, "SELECT COUNT(*) FROM board_tasks WHERE board_id=?",
        (board_id,))[0][0]

    waits: List[Dict[str, Any]] = []
    for row in hitl:
        snapshot = _json_column(row[4])
        params = _json_column(row[5])
        bound_job = str(snapshot.get("job_id") or params.get("job_id") or "")
        if str(row[2] or "") != WAIT_ACTION_TYPE or bound_job != job_id:
            continue
        waits.append({
            "id": row[0],
            "status": row[1],
            "action_type": row[2],
            "user_feedback": row[3],
            "correlation_id": snapshot.get("correlation_id")
            or params.get("correlation_id"),
        })

    exec_steps: List[Dict[str, Any]] = []
    if executions:
        summary = _json_column(executions[0][2])
        if isinstance(summary, dict):
            exec_steps = _public_steps(summary.get("steps"))

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


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------
def _run_scenario(args: argparse.Namespace) -> int:
    if not args.out:
        print("[execute] --out is required for the evidence bundle",
              file=sys.stderr)
        return 2
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    world = _world_path(args.world)
    scenario: Dict[str, Any] = {
        "kind": "browser_agent_job_wait_scenario",
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
        exec_env = _prepare_execute_environment(args)
        stack["driver_environment"] = exec_env
        ready = _check_execute_ready(args)
        stack["preflight"] = ready
        source = _source_probe(args.expect_source_sha)
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

        build = _build_world(world, source.get("head") or "")
        stack["world_build"] = build
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
        }, details={"disk_preflight": build.get("disk_preflight"),
                    "preflight": build.get("preflight"),
                    "export": build.get("export"),
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
        health1 = _health(args.backend_port)
        stack.update({
            "run_dir": str(run_dir),
            "db_path": str(db_path),
            "backend_descriptor": descriptor1,
            "health_before_restart": health1,
            "auth_secret_present": bool(os.environ.get("SECRET_KEY")),
        })
        identity1 = health1.get("identity") or {}
        source_binding = _backend_source_binding(
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
        if not source_binding["manifest_source_revision_present"]:
            stack.setdefault("notes", []).append(
                "world MANIFEST has no source_revision; the initial server is "
                "certified by frozen source + exported tree hashes + isolated "
                "cwd, never by the absent manifest field")
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
            "db_not_live": db_path.resolve() != (BACKEND / "data" / "atom.db").resolve(),
        }, details={"descriptor": descriptor1,
                    "health_identity": identity1})

        password, password_meta = _password_for_run(
            args, world, db_path, run_dir)
        stack["admin_password_source"] = password_meta
        token, login_api = _api_login(args.backend_port, password)
        with _api_client(args.backend_port, token) as api:
            fixture = _setup_fixture(api)
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
                "__TITLE_ANSWER__": TITLE_ANSWER,
                "__PRIORITY_ANSWER__": PRIORITY_ANSWER,
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
            shim0 = _shim_snapshot(args.shim_port)
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
                "cwd": _process_cwd(fe_proc.pid),
                "source_revision": (stack.get("source") or {}).get("head"),
            }
            build_id_path = world / "frontend_snapshot" / ".next" / "BUILD_ID"
            stack["frontend"]["build_id"] = (
                build_id_path.read_text(encoding="utf-8").strip()
                if build_id_path.is_file() else None)
            stack["frontend"]["build_id_note"] = (
                "dev server; BUILD_ID is recorded only if Next writes one")
            frontend_cwd = stack["frontend"]["cwd"]
            step("frontend_cwd_isolated", {
                "cwd_observed": frontend_cwd is not None,
                "cwd_exact": _frontend_cwd_matches(
                    frontend_cwd, world / "frontend_snapshot"),
            }, details={"cwd": frontend_cwd,
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
                    path = _path_of(url)
                    if "/answer" in path and request.method == "POST":
                        answer_posts.append({"path": path})
                    requests_seen.append({
                        "method": request.method,
                        "origin": _origin(url),
                        "host": parsed.hostname or "",
                        "path": path,
                    })
                page.on("request", _on_request)

                login = BV.ui_login(
                    page, fe_base, ADMIN_EMAIL, password)
                if not login.get("ok"):
                    # Give the real form one bounded extra wait; never replace
                    # it with cookie/token seeding.
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
                _screenshot(page, out, "00_login.png")

                page.goto(f"{fe_base}/agents", wait_until="domcontentloaded",
                          timeout=300000)
                card_selector = f'[data-testid="agent-card-{AGENT_NAME}"]'
                _wait_selector(page, card_selector, 240000)
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
                _wait_selector(page, '[role="dialog"]', 30000)
                textarea = dialog.locator("textarea").first
                textarea.fill(OBJECTIVE)
                with page.expect_response(
                        lambda response: (
                            response.request.method == "POST"
                            and "/api/agents/" in response.url
                            and _path_of(response.url).rstrip("/").endswith("/run")),
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
                execution_id = str(run_data.get("execution_id") or "")
                if not job_id or not execution_id:
                    raise DriverError(
                        f"run response lacked job/execution identity: "
                        f"{_safe_error_body(run_response)}")
                stack["job"] = {
                    "agent_id": fixture["agent_id"],
                    "job_id": job_id,
                    "execution_id": execution_id,
                    "run_response_status": run_response.status,
                    "run_response_job_status": run_data.get("job_status"),
                }
                step("run_admitted", {
                    "http_2xx": 200 <= run_response.status < 300,
                    "job_id_present": bool(job_id),
                    "execution_id_present": bool(execution_id),
                }, details=_public_job(run_data))

                _wait_selector(page, '[data-testid="agent-job-wait-panel"]',
                               180000)
                first_question = _wait_for_text(
                    page, '[data-testid="agent-job-question"]',
                    lambda text: text == Q1, 180000, "first question")
                first_status = _wait_for_text(
                    page, '[data-testid="agent-job-status"]',
                    lambda text: "Waiting for your answer" in text,
                    180000, "waiting status")
                first_blocking = page.locator(
                    '[data-testid="agent-job-blocking"]').inner_text().strip()
                panel_text = page.locator(
                    '[data-testid="agent-job-wait-panel"]').inner_text().strip()
                job1 = _read_job(api, fixture["agent_id"], job_id)
                wait1 = (job1["data"].get("wait") or {})
                shim1 = _shim_snapshot(args.shim_port)
                step("first_durable_question", {
                    "job_status_waiting": job1["data"].get("job_status") == "waiting",
                    "same_job_id": str(job1["data"].get("job_id")) == job_id,
                    "same_execution_id": str(
                        job1["data"].get("execution_id")) == execution_id,
                    "wait_id_present": bool(wait1.get("id")),
                    "correlation_present": bool(wait1.get("correlation_id")),
                    "question_exact": wait1.get("question") == Q1,
                    "ui_question_exact": first_question == Q1,
                    "ui_waiting_status": "Waiting for your answer" in first_status,
                    "ui_blocking_fact": "task title" in first_blocking.lower(),
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
                # The read must be pure: no provider call, unchanged wait.
                job1_again = _read_job(api, fixture["agent_id"], job_id)
                shim1b = _shim_snapshot(args.shim_port)
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
                    "capture_has_full_messages": _capture_has_full_messages(
                        shim_capture_path),
                    "correlation_absent": not _capture_contains(
                        shim_capture_path,
                        [str(wait1.get("correlation_id") or "___none___")]),
                    "hitl_id_absent": not _capture_contains(
                        shim_capture_path,
                        [str(wait1.get("id") or "___none___")]),
                }, details={"capture_has_messages": shim_capture_path.exists()})
                _screenshot(page, out, "01_first_question.png")

                # ---- restart while waiting (real backend + frontend) ----
                job_before_restart = _read_job(
                    api, fixture["agent_id"], job_id)
                wait_before_restart = job_before_restart["data"].get("wait") or {}
                _stop_frontend_group(fe_proc)
                C5.wait_port_free(args.frontend_port)
                R.stop_server(backend)
                C5.wait_port_free(args.backend_port)
                shim_alive = _shim_snapshot(args.shim_port)
                step("restart_ports_freed", {
                    "frontend_port_free": _port_free(args.frontend_port),
                    "backend_port_free": _port_free(args.backend_port),
                    "shim_alive": shim_alive["available"],
                }, details={"shim_calls": shim_alive["calls"]})

                backend = R.launch_server(
                    args.backend_port, world, provider_shim=True,
                    reuse_run_dir=run_dir, shim_port=args.shim_port)
                cleanups.append(("backend", backend))
                descriptor2 = dict(R.launch_server.descriptor)
                health2 = _health(args.backend_port)
                identity2 = health2.get("identity") or {}
                fe_proc = C5.start_frontend_copy(
                    args.backend_port, args.frontend_port, world)
                if not fe_proc:
                    raise DriverError("frontend restart failed")
                cleanups.append(("frontend", fe_proc))
                fe_cwd2 = _process_cwd(fe_proc.pid)
                build_id_path2 = (
                    world / "frontend_snapshot" / ".next" / "BUILD_ID")
                stack["frontend_after_restart"] = {
                    "pid": fe_proc.pid,
                    "cwd": fe_cwd2,
                    "build_id": (
                        build_id_path2.read_text(encoding="utf-8").strip()
                        if build_id_path2.is_file() else None),
                }
                step("frontend_restarted_isolated", {
                    "cwd_observed": fe_cwd2 is not None,
                    "cwd_exact": _frontend_cwd_matches(
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

                page.reload(wait_until="domcontentloaded")
                _wait_selector(page, '[data-testid="agent-job-wait-panel"]',
                               180000)
                after_restart_question = _wait_for_text(
                    page, '[data-testid="agent-job-question"]',
                    lambda text: text == Q1, 180000, "same first question")
                job2 = _read_job(api, fixture["agent_id"], job_id)
                wait2 = job2["data"].get("wait") or {}
                shim2 = _shim_snapshot(args.shim_port)
                step("same_wait_after_restart", {
                    "same_job_id": str(job2["data"].get("job_id")) == job_id,
                    "same_execution_id": str(
                        job2["data"].get("execution_id")) == execution_id,
                    "same_wait_id": wait2.get("id") == wait_before_restart.get("id"),
                    "same_correlation": (
                        wait2.get("correlation_id")
                        == wait_before_restart.get("correlation_id")),
                    "same_question": wait2.get("question") == Q1,
                    "ui_same_question": after_restart_question == Q1,
                    "answer_input_empty": (
                        page.locator(
                            '[data-testid="agent-job-answer-input"]'
                        ).input_value() == ""),
                    "no_completion": page.locator(
                        '[data-testid="agent-job-completed"]').count() == 0,
                    "no_new_provider_call": shim2["calls"] == shim1b["calls"],
                }, details={"job_read": job2["public"],
                            "shim_calls": shim2["calls"]})
                _screenshot(page, out, "02_after_restart_same_wait.png")

                # ---- answer first question (same job) ----
                answer_input = page.locator(
                    '[data-testid="agent-job-answer-input"]')
                answer_submit = page.locator(
                    '[data-testid="agent-job-answer-submit"]')
                answer_input.fill(TITLE_ANSWER)
                with page.expect_response(
                        lambda response: (
                            response.request.method == "POST"
                            and "/answer" in _path_of(response.url)),
                        timeout=180000) as answer_info:
                    answer_submit.click()
                answer_response = answer_info.value
                try:
                    answer_body = answer_response.json()
                except Exception:
                    answer_body = {}
                answer_data = answer_body.get("data") or {}
                step("first_answer_accepted", {
                    "http_202": answer_response.status == 202,
                    "resumed": answer_data.get("resumed") is True,
                    "same_job_id": str(answer_data.get("job_id")) == job_id,
                    "same_execution_id": str(
                        answer_data.get("execution_id")) == execution_id,
                    "still_waiting": answer_data.get("job_status") == "waiting",
                    "single_answer_post": len(answer_posts) == 1,
                }, details={"response": _public_job(answer_data)})

                second_question = _wait_for_text(
                    page, '[data-testid="agent-job-question"]',
                    lambda text: text == Q2, 180000, "second question")
                job3 = _read_job(api, fixture["agent_id"], job_id)
                wait3 = job3["data"].get("wait") or {}
                shim3 = _shim_snapshot(args.shim_port)
                waits_after_first = _durable_state(
                    db_path, fixture["agent_id"], job_id, execution_id,
                    fixture["board_id"])["waits"]
                step("second_durable_question", {
                    "job_status_waiting": job3["data"].get("job_status") == "waiting",
                    "same_execution_id": str(
                        job3["data"].get("execution_id")) == execution_id,
                    "new_wait_id": wait3.get("id") != wait1.get("id"),
                    "new_correlation": (
                        wait3.get("correlation_id")
                        != wait1.get("correlation_id")),
                    "question_exact": wait3.get("question") == Q2,
                    "ui_question_exact": second_question == Q2,
                    "answer_input_cleared": answer_input.input_value() == "",
                    "no_completion": page.locator(
                        '[data-testid="agent-job-completed"]').count() == 0,
                    "two_wait_rows": len(waits_after_first) == 2,
                    "first_wait_approved_with_title": (
                        len(waits_after_first) == 2
                        and waits_after_first[0].get("status") == "approved"
                        and waits_after_first[0].get("user_feedback")
                        == TITLE_ANSWER),
                    "second_wait_pending": (
                        len(waits_after_first) == 2
                        and waits_after_first[1].get("status") == "pending"),
                }, details={"job_read": job3["public"],
                            "waits": waits_after_first,
                            "shim_calls": shim3["calls"]})
                _screenshot(page, out, "03_second_question.png")

                # ---- stale-answer negative (same job, no second job) ----
                calls_before_stale = shim3["calls"]
                stale = _post_answer(
                    api, fixture["agent_id"], job_id, TITLE_ANSWER,
                    str(wait1.get("correlation_id") or ""))
                job_after_stale = _read_job(api, fixture["agent_id"], job_id)
                shim_after_stale = _shim_snapshot(args.shim_port)
                job_count_stale = _durable_state(
                    db_path, fixture["agent_id"], job_id, execution_id,
                    fixture["board_id"])["counts"]["jobs_for_agent"]
                step("stale_answer_refused", {
                    "http_409": stale["status"] == 409,
                    "job_still_waiting": (
                        job_after_stale["data"].get("job_status") == "waiting"),
                    "same_second_wait": (
                        (job_after_stale["data"].get("wait") or {}).get("id")
                        == wait3.get("id")),
                    "no_provider_call": (
                        shim_after_stale["calls"] == calls_before_stale),
                    "no_task_created": _durable_state(
                        db_path, fixture["agent_id"], job_id, execution_id,
                        fixture["board_id"])["counts"][
                            "tasks_on_scratch_board"] == 0,
                    "no_second_job": job_count_stale == 1,
                }, details={"response_status": stale["status"],
                            "response_detail": stale["detail"],
                            "ui_409_note": (
                                "The panel owns the correlation and does not "
                                "expose it for editing; the API-level 409 is "
                                "the authoritative stale-answer control.")})

                # ---- reload, same second question ----
                job_count_before_reload = _durable_state(
                    db_path, fixture["agent_id"], job_id, execution_id,
                    fixture["board_id"])["counts"]["jobs_for_agent"]
                page.reload(wait_until="domcontentloaded")
                _wait_selector(page, '[data-testid="agent-job-wait-panel"]',
                               180000)
                reload_question = _wait_for_text(
                    page, '[data-testid="agent-job-question"]',
                    lambda text: text == Q2, 180000, "same second question")
                job4 = _read_job(api, fixture["agent_id"], job_id)
                wait4 = job4["data"].get("wait") or {}
                shim4 = _shim_snapshot(args.shim_port)
                job_count_after_reload = _durable_state(
                    db_path, fixture["agent_id"], job_id, execution_id,
                    fixture["board_id"])["counts"]["jobs_for_agent"]
                step("same_second_question_after_reload", {
                    "same_job_id": str(job4["data"].get("job_id")) == job_id,
                    "same_execution_id": str(
                        job4["data"].get("execution_id")) == execution_id,
                    "same_wait_id": wait4.get("id") == wait3.get("id"),
                    "same_correlation": (
                        wait4.get("correlation_id")
                        == wait3.get("correlation_id")),
                    "same_question": wait4.get("question") == Q2,
                    "ui_same_question": reload_question == Q2,
                    "answer_input_empty": (
                        page.locator(
                            '[data-testid="agent-job-answer-input"]'
                        ).input_value() == ""),
                    "no_new_provider_call": shim4["calls"] == shim3["calls"],
                    "no_new_job": (
                        job_count_after_reload == job_count_before_reload),
                }, details={"job_read": job4["public"],
                            "shim_calls": shim4["calls"]})
                _screenshot(page, out, "04_reload_same_second_question.png")

                # ---- answer second question, verify real effect ----
                answer_input = page.locator(
                    '[data-testid="agent-job-answer-input"]')
                answer_submit = page.locator(
                    '[data-testid="agent-job-answer-submit"]')
                answer_input.fill(PRIORITY_ANSWER)
                with page.expect_response(
                        lambda response: (
                            response.request.method == "POST"
                            and "/answer" in _path_of(response.url)),
                        timeout=240000) as final_info:
                    answer_submit.click()
                final_response = final_info.value
                try:
                    final_body = final_response.json()
                except Exception:
                    final_body = {}
                final_data = final_body.get("data") or {}
                final_steps = _public_steps(
                    (final_data.get("result") or {}).get("steps"))
                task_steps = [
                    item for item in final_steps
                    if item.get("action_tool") == "tasks.create"
                ]
                step("final_answer_verified", {
                    "http_200": final_response.status == 200,
                    "job_status_success": final_data.get("job_status") == "success",
                    "outcome_success": final_data.get("outcome") == "success",
                    "same_execution_id": str(
                        final_data.get("execution_id")) == execution_id,
                    "result_output": FINAL_ANSWER in str(
                        (final_data.get("result") or {}).get("output") or ""),
                    "tasks_create_step": bool(task_steps),
                    "oracle_verified": bool(
                        task_steps
                        and task_steps[0].get("oracle_verified") is True),
                    "two_answer_posts": len(answer_posts) == 2,
                }, details={"result_steps": final_steps,
                            "response": _public_job(final_data)})

                _wait_selector(page, '[data-testid="agent-job-completed"]',
                               180000)
                completed_text = page.locator(
                    '[data-testid="agent-job-completed"]').inner_text().strip()
                _wait_selector(page, '[data-testid="agent-job-result"]',
                               60000)
                result_text = page.locator(
                    '[data-testid="agent-job-result"]').inner_text().strip()
                step("ui_shows_verified_result", {
                    "completed_panel": bool(completed_text),
                    "result_visible": FINAL_ANSWER in result_text,
                    "no_failure_banner": page.locator(
                        '[data-testid="agent-job-failure"]').count() == 0,
                    "no_open_question": page.locator(
                        '[data-testid="agent-job-question"]').count() == 0,
                }, details={"completed_text": completed_text,
                            "result_text": result_text[:1000]})
                _screenshot(page, out, "05_verified_result.png")

                job5 = _read_job(api, fixture["agent_id"], job_id)
                step("durable_readback_after_success", {
                    "job_status_success": job5["data"].get("job_status") == "success",
                    "same_execution_id": str(
                        job5["data"].get("execution_id")) == execution_id,
                    "result_output": FINAL_ANSWER in str(
                        (job5["data"].get("result") or {}).get("output") or ""),
                }, details={"job_read": job5["public"]})

                durable = _durable_state(
                    db_path, fixture["agent_id"], job_id, execution_id,
                    fixture["board_id"])
                waits = durable["waits"]
                tasks = durable["tasks"]
                step("durable_effect_exactly_once", {
                    "one_job_row": durable["job"]["id"] == job_id,
                    "job_status_success": durable["job"]["status"] == "success",
                    "one_execution_row": (
                        durable["execution"]["id"] == execution_id),
                    "execution_terminal": durable["execution"]["status"] in (
                        "completed", "success"),
                    "two_information_waits": len(waits) == 2,
                    "both_waits_approved": (
                        len(waits) == 2
                        and all(w.get("status") == "approved" for w in waits)),
                    "first_answer_persisted": (
                        len(waits) == 2
                        and waits[0].get("user_feedback") == TITLE_ANSWER),
                    "second_answer_persisted": (
                        len(waits) == 2
                        and waits[1].get("user_feedback") == PRIORITY_ANSWER),
                    "one_board_task": (
                        len(tasks) == 1
                        and tasks[0].get("title") == TITLE_ANSWER
                        and tasks[0].get("priority") == PRIORITY_ANSWER),
                    "one_task_on_board": (
                        durable["counts"]["tasks_on_scratch_board"] == 1),
                    "one_job_for_agent": (
                        durable["counts"]["jobs_for_agent"] == 1),
                    "one_execution_for_id": (
                        durable["counts"]["executions_for_id"] == 1),
                }, details={"durable": durable})
                _write_json(out / "durable.json", durable)
                shim_after_final = _shim_snapshot(args.shim_port)

                # ---- duplicate-answer negative (same successful job) ----
                shim_before_duplicate = _shim_snapshot(args.shim_port)
                task_count_before_duplicate = durable["counts"][
                    "tasks_on_scratch_board"]
                duplicate = _post_answer(
                    api, fixture["agent_id"], job_id, TITLE_ANSWER,
                    str(wait1.get("correlation_id") or ""))
                durable_after_duplicate = _durable_state(
                    db_path, fixture["agent_id"], job_id, execution_id,
                    fixture["board_id"])
                shim_after_duplicate = _shim_snapshot(args.shim_port)
                duplicate_ok = (
                    duplicate["status"] == 409
                    or (duplicate["status"] == 200
                        and duplicate["data"].get("already_resumed") is True))
                step("duplicate_answer_idempotent", {
                    "status_409_or_already_resumed": duplicate_ok,
                    "http_200_alone_not_success": (
                        duplicate["status"] != 200
                        or duplicate["data"].get("already_resumed") is True),
                    "same_execution_id": (
                        duplicate["data"].get("execution_id") in (
                            None, execution_id)),
                    "same_task_count": (
                        durable_after_duplicate["counts"][
                            "tasks_on_scratch_board"]
                        == task_count_before_duplicate),
                    "no_new_provider_call": (
                        shim_after_duplicate["calls"]
                        == shim_before_duplicate["calls"]),
                    "job_still_success": (
                        durable_after_duplicate["job"]["status"] == "success"),
                }, details={"status": duplicate["status"],
                            "detail": duplicate["detail"]})
                scenario["shim"] = {
                    "calls_after_reload_before_final": shim4["calls"],
                    "calls_after_final": shim_after_final["calls"],
                    "calls_final": shim_after_duplicate["calls"],
                    "react_calls_final": shim_after_duplicate["react_calls"],
                }
                step("shim_one_call_per_reasoning_step", {
                    "react_calls_exactly_four": (
                        shim_after_duplicate["react_calls"] == 4),
                    "no_calls_from_reload_or_negatives": (
                        shim_after_duplicate["calls"]
                        == shim_after_final["calls"]),
                }, details=scenario["shim"])

                # Browser origin / forbidden-port control.
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
                    if entry.get("host") not in ("localhost", "127.0.0.1", "::1")
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
                        _stop_frontend_group(proc)
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
                str(port): _port_free(port)
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
        "kind": "browser_agent_job_wait_evidence_manifest",
        "generated_at": _now(),
        "source_commit": source_commit,
        "files": files,
    })


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _default_world_name() -> str:
    head = _git("rev-parse", "HEAD")[:10] or time.strftime("%Y%m%d%H%M%S")
    return f"browser_wait_{head}"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Thin preparation/execution driver for the Agents-page durable "
            "information-wait acceptance. Default is --preflight; root owns "
            "--execute."),
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
                    help="acceptance world name (default browser_wait_<HEAD10>)")
    ap.add_argument("--backend-port", type=int, default=8031)
    ap.add_argument("--frontend-port", type=int, default=3131)
    ap.add_argument("--shim-port", type=int, default=8097)
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
