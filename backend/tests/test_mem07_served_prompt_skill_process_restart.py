"""MEM-07 served-restart regression: a reviewed prompt skill is applied through
the REAL served HTTP surface, survives a REAL process restart, and is consumed
by the ordinary ``POST /api/agents/{id}/run`` path in a NEW OS process.

What is real here (no doubles on the surfaces under test):

* The failure feedstock is produced in a scratch child by the real
  ``GenericAgent._step_act`` tool-error path, the real ``EpisodeService``
  event emission, the registered ``ReflectionEngine`` and the real
  ``MementoEngine`` lifecycle. Only the Memento model transport is doubled
  (controlled generated-code text) — exactly like
  ``tests/test_mem07_prompt_skill_process_restart.py``.
* Review and apply travel over the actual production entry point
  ``main_api_app:app`` served by uvicorn in a child OS process (bound-socket
  ``--fd`` pattern from ``tests/test_mini_app_records_process_restart.py``),
  with real ``POST /api/auth/login`` JWT auth and the real mounted
  ``/api/autodev`` review router.
* Consumption uses the ordinary ``POST /api/agents/{id}/run`` route with
  ``sync`` so the response reflects the completed run. The request path is
  the real admission + ``execute_agent_task`` + ``GenericAgent.execute``
  chain. Only the model leaf is doubled: ``LLMService.generate_structured``
  captures the exact prompt and returns a fixed ``ReActStep``; the raw
  ``LLMService.generate`` fallback is a tripwire. No provider/network is
  contacted.
* The restart boundary is a genuinely NEW OS process on the SAME scratch
  SQLite file and skill root.

Evidence sequence:

1. A reviewed+applied prompt skill exists on disk and in the scratch DB.
2. Server process A (pid A) performs login/approve/apply over normal HTTP.
3. Server process A is stopped; server process B (pid B != pid A) starts on
   the same durable state.
4. Ordinary run for the correct-workspace agent captures a prompt whose
   system instruction contains the skill marker and description.
5. Ordinary run for a real agent in ANOTHER workspace of the same tenant
   captures a prompt with no marker and no skill-injection block.

Isolation (the 2026-09-04 live-DB-wipe class of bugs):

* Every path-bearing variable is pinned under ``tmp_path`` BEFORE any core
  import in each child: one generated SQLite file, generated
  ``ATOM_DATA_DIR`` / ``ATOM_WORKSPACE_SKILLS_ROOT`` / ``LANCEDB_*``.
* ``TESTING=1`` + ``PYTEST_VERSION`` + explicit scratch ``DATABASE_URL``
  (the documented core/database.py branch) so no child can reach the live
  dev DB or the shared ``backend/test_integration.db``.
* Provider/account secrets are removed from the child environment; only
  loopback HTTP is used (127.0.0.1); no live services or credentials.
* The parent process imports no ``core`` modules: seeding/candidate creation
  and both server lifespans happen in children that freeze their own env
  before importing the application.

Scope limits (stated, not claimed): this qualifies the reviewed prompt-skill
consumption path through the served agent-run surface. It does not exercise
generated-code promotion (never applied), external integrations, or the full
chat UI.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

BOOT_DEADLINE_S = 180.0
SEED_DEADLINE_S = 150.0
REQUEST_OK = "outlook customer email search for the scoped restart"
REQUEST_OTHER = "outlook customer email search from another workspace"
TASK = "look up the customer email in outlook"
INJECTION_HEADER = "The following skills may be relevant to the current task:"


# ---------------------------------------------------------------------------
# Frozen scratch environment (built before any child import)
# ---------------------------------------------------------------------------
def _scratch_child_env(tmp_path: Path, db_path: Path, secret_key: str,
                       reviewer_password: str) -> dict:
    env = os.environ.copy()
    # A scratch child must not inherit real provider/account secrets.
    for key in list(env):
        if any(part in key.upper() for part in
               ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")):
            env.pop(key, None)
    data_dir = tmp_path / "data"
    skills_root = tmp_path / "skills"
    lancedb_dir = tmp_path / "lancedb"
    for directory in (data_dir, skills_root, lancedb_dir):
        directory.mkdir(parents=True, exist_ok=True)
    env.update({
        # DB selection: TESTING=1 alone forces the shared test DB; the pytest
        # branch honors the explicit NON-dev scratch URL. The app lifespan
        # then skips create_all (the seed child owns fresh schema init).
        "TESTING": "1",
        "PYTEST_VERSION": "1",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "ENVIRONMENT": "development",
        "ATOM_DEPLOYMENT_AUDIENCE": "development",
        # Scratch data roots, all under tmp_path.
        "ATOM_DATA_DIR": str(data_dir),
        "ATOM_WORKSPACE_SKILLS_ROOT": str(skills_root),
        "LANCEDB_URI": str(lancedb_dir),
        "LANCEDB_PATH": str(lancedb_dir),
        "LANCEDB_URI_BASE": str(lancedb_dir),
        # The reviewed prompt-skill path under test.
        "ATOM_SKILL_INJECTION_ENABLED": "true",
        "ATOM_MOCK_DATABASE": "false",
        # Synthetic secret so tokens are stable across BOTH children without
        # touching backend/data/.dev_secret_key.
        "SECRET_KEY": secret_key,
        # Keep background workers off; no telemetry/egress.
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "SENTRY_DSN": "",
        "REDIS_URL": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "MEM07_EXPECTED_DB": str(db_path.resolve()),
        "MEM07_REVIEWER_PASSWORD": reviewer_password,
    })
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(BACKEND_DIR), str(REPO_ROOT)) if p)
    return env


def _assert_scratch(env: dict, tmp_path: Path) -> None:
    """Refuse unsafe/non-scratch targets before any child is spawned."""
    db_url = env["DATABASE_URL"]
    assert db_url.startswith("sqlite:///"), f"non-sqlite scratch URL: {db_url!r}"
    db_file = Path(db_url.partition("sqlite:///")[2]).resolve()
    assert tmp_path.resolve() in db_file.parents, (
        f"scratch refusal: DATABASE_URL {db_file} is not under tmp_path")
    for var in ("ATOM_DATA_DIR", "ATOM_WORKSPACE_SKILLS_ROOT",
                "LANCEDB_URI", "LANCEDB_PATH", "LANCEDB_URI_BASE"):
        path = Path(env[var]).resolve()
        assert tmp_path.resolve() in path.parents or path == tmp_path.resolve(), (
            f"scratch refusal: {var}={path} is not under tmp_path")
    assert Path(env["MEM07_EXPECTED_DB"]).resolve() == db_file


# ---------------------------------------------------------------------------
# Child 1: seed the scratch world and create a real pending candidate
# ---------------------------------------------------------------------------
_SEED_SCRIPT = r"""
import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

expected = Path(os.environ["MEM07_EXPECTED_DB"]).resolve()

# Freeze/verify scratch before any product surface sees the world.
from core.database import engine

actual = Path(engine.url.database).resolve()
if not engine.url.drivername.startswith("sqlite") or actual != expected:
    raise SystemExit(f"seed child refused a non-scratch database: {engine.url}")
if os.environ.get("TESTING") != "1":
    raise SystemExit("seed child refused without TESTING=1")

import core.models  # noqa: F401 - register tables on the shared Base
from core.auto_dev import models as autodev_models  # noqa: F401
from core.database import Base, SessionLocal
from core.models import (
    AgentExecution,
    AgentRegistry,
    Tenant,
    User,
    Workspace,
)
from core.auth import get_password_hash

Base.metadata.create_all(engine)

TASK = os.environ["MEM07_TASK"]
PASSWORD = os.environ["MEM07_REVIEWER_PASSWORD"]

tenant = Tenant(
    id="tenant-mem07-served", name="MEM-07 Served Tenant",
    subdomain="mem07-served")
workspace = Workspace(
    id="ws-mem07-served", name="MEM-07 Served Workspace",
    tenant_id=tenant.id, metadata_json={"auto_dev": {"enabled": True}})
other_workspace = Workspace(
    id="ws-mem07-served-other", name="MEM-07 Other Workspace",
    tenant_id=tenant.id, metadata_json={"auto_dev": {"enabled": True}})
agent_config = {
    "system_prompt": "original",
    "capability_maturities": {"*": "intern"},
}
agent = AgentRegistry(
    id="agent-mem07-served", name="MEM-07 Served Employee",
    category="operations", module_path="core.generic_agent",
    class_name="GenericAgent", status="intern", confidence_score=0.5,
    configuration=dict(agent_config), capabilities=[],
    workspace_id=workspace.id, tenant_id=tenant.id, enabled=True)
other_agent = AgentRegistry(
    id="agent-mem07-served-other", name="MEM-07 Other Employee",
    category="operations", module_path="core.generic_agent",
    class_name="GenericAgent", status="intern", confidence_score=0.5,
    configuration=dict(agent_config), capabilities=[],
    workspace_id=other_workspace.id, tenant_id=tenant.id, enabled=True)
# ADMIN may review in-workspace and run agents across workspaces of the
# tenant; the skill's own assignment still decides consumption.
reviewer = User(
    id="reviewer-mem07-served", email="served-reviewer@example.invalid",
    hashed_password=get_password_hash(PASSWORD),
    first_name="R", last_name="V", role="admin", status="active",
    workspace_id=workspace.id, tenant_id=tenant.id, is_active=True)
# The wrong-scope run is performed by a REAL member of the other workspace
# (a cross-workspace admin cannot continue a frozen other-workspace scope).
other_member = User(
    id="member-mem07-other", email="served-other@example.invalid",
    hashed_password=get_password_hash(PASSWORD),
    first_name="O", last_name="W", role="member", status="active",
    workspace_id=other_workspace.id, tenant_id=tenant.id, is_active=True)
execution = AgentExecution(
    id="exec-mem07-served", agent_id=agent.id, tenant_id=tenant.id,
    workspace_id=workspace.id, status="running", metadata_json={})

with SessionLocal() as db:
    db.add_all([tenant, workspace, other_workspace, agent, other_agent,
                reviewer, other_member, execution])
    db.commit()

from core.auto_dev.event_hooks import event_bus
from core.auto_dev.models import SkillCandidate
from core.auto_dev.reflection_engine import ReflectionEngine
from core.episode_service import EpisodeService
from core.generic_agent import GenericAgent

saved = (
    list(event_bus._fail_handlers),
    list(event_bus._success_handlers),
    list(event_bus._skill_handlers),
)
event_bus._fail_handlers[:] = []
event_bus._success_handlers[:] = []
event_bus._skill_handlers[:] = []

calls = []
memento_llm = MagicMock()
memento_llm.generate_completion = AsyncMock(
    side_effect=lambda **kw: calls.append(kw) or {
        "content": "def repair_unknown_tool():\n    return 1"})
from core.auto_dev.memento_engine import MementoEngine
MementoEngine._get_llm_service = lambda self: memento_llm
ReflectionEngine(db=None, failure_threshold=1).register()


async def _run():
    with SessionLocal() as db:
        row = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id).one()
        worker = GenericAgent(row, workspace_id=workspace.id)

        def boom(_args, _context):
            raise RuntimeError(
                "400 Syntax error on the customer email search")

        worker._custom_actions = {"unknown.tool": boom}
        context = {
            "execution_id": execution.id,
            "tenant_id": tenant.id,
            "run_id": "run-mem07-served",
            "operation_id": "op-mem07-served",
        }
        for _ in range(2):
            result = await worker._step_act("unknown.tool", {}, context)
            assert "Error" in result

        db.expire_all()
        persisted = db.query(AgentExecution).filter(
            AgentExecution.id == execution.id).one()
        assert persisted.metadata_json["tool_errors"]

        episode = await EpisodeService(
            db).create_episode_from_execution(
                execution.id, TASK, outcome="success", success=True,
                metadata={})
        assert episode.success is False
        assert episode.outcome == "partial"

        for _ in range(300):
            await asyncio.sleep(0.01)
            with SessionLocal() as fresh:
                rows = fresh.query(SkillCandidate).filter(
                    SkillCandidate.agent_id == agent.id).all()
                if rows:
                    assert len(rows) == 1
                    assert rows[0].validation_status == "pending"
                    assert calls, "controlled Memento leaf was not reached"
                    return rows[0]
        raise AssertionError(
            "the emitted failure event did not create a pending candidate")


try:
    candidate = asyncio.run(_run())
finally:
    (event_bus._fail_handlers[:],
     event_bus._success_handlers[:],
     event_bus._skill_handlers[:]) = saved

payload = {
    "pid": os.getpid(),
    "database_file": str(actual),
    "tenant_id": tenant.id,
    "workspace_id": workspace.id,
    "other_workspace_id": other_workspace.id,
    "agent_id": agent.id,
    "other_agent_id": other_agent.id,
    "reviewer_email": reviewer.email,
    "other_member_email": other_member.email,
    "agent_configuration": agent_config,
    "candidate_id": candidate.id,
    "skill_name": candidate.skill_name,
    "skill_description": candidate.skill_description,
    "generated_code": candidate.generated_code,
    "validation_status": candidate.validation_status,
}
Path(os.environ["MEM07_RESULT_FILE"]).write_text(json.dumps(payload))
engine.dispose()
"""


def _seed_world(env: dict, tmp_path: Path) -> dict:
    result_file = tmp_path / "seed-result.json"
    child_env = dict(
        env, MEM07_TASK=TASK, MEM07_RESULT_FILE=str(result_file))
    completed = subprocess.run(
        [sys.executable, "-c", _SEED_SCRIPT],
        cwd=str(BACKEND_DIR), env=child_env, capture_output=True, text=True,
        timeout=SEED_DEADLINE_S)
    assert completed.returncode == 0, (
        f"seed child failed rc={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
    assert result_file.is_file(), (
        f"seed child produced no result\nstdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}")
    payload = json.loads(result_file.read_text())
    assert payload["pid"] != os.getpid(), "seed must be a separate OS process"
    assert Path(payload["database_file"]).resolve() == Path(
        env["MEM07_EXPECTED_DB"]).resolve()
    assert payload["validation_status"] == "pending"
    assert payload["skill_name"]
    assert payload["generated_code"]
    return payload


# ---------------------------------------------------------------------------
# Child 2: the REAL main_api_app served on an inherited loopback socket
# ---------------------------------------------------------------------------
_SERVER_SCRIPT = r"""
import hashlib
import json
import os
import sys
from pathlib import Path

expected = Path(os.environ["MEM07_EXPECTED_DB"]).resolve()

# Freeze/verify scratch before main_api_app (or any service) is imported.
from core.database import engine

actual = Path(engine.url.database).resolve()
if not engine.url.drivername.startswith("sqlite") or actual != expected:
    raise SystemExit(f"server child refused a non-scratch database: {engine.url}")
if os.environ.get("TESTING") != "1":
    raise SystemExit("server child refused without TESTING=1")

capture_path = os.environ.get("MEM07_CAPTURE_FILE")
if capture_path:
    # Only the model leaf is doubled. Every LLMService instance created by the
    # ordinary agent-run path is controlled here, before main_api_app imports.
    from core.llm_service import LLMService
    from core.react_models import ReActStep

    async def capture_structured(self, **kwargs):
        response_model = kwargs.get("response_model")
        if getattr(response_model, "__name__", None) != "ReActStep":
            raise AssertionError(
                "unexpected structured model leaf in the agent-run control: "
                f"{response_model!r}")
        record = {
            "pid": os.getpid(),
            "system_instruction": kwargs.get("system_instruction"),
            "prompt": kwargs.get("prompt"),
            "model": kwargs.get("model"),
            "agent_id": kwargs.get("agent_id"),
            "response_model": "ReActStep",
        }
        with open(capture_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        return ReActStep(
            thought="controlled served-run prompt capture",
            final_answer="CONTROLLED_SERVED_PIN")

    async def forbidden_generate(self, **kwargs):
        raise AssertionError(
            "raw LLMService.generate() was reached; the structured leaf "
            "should answer")

    LLMService.generate_structured = capture_structured
    LLMService.generate = forbidden_generate

import main_api_app
import uvicorn

identity = {
    "pid": os.getpid(),
    "database_file": str(actual),
    "capture": bool(capture_path),
    "source_files": {
        str(Path(module.__file__).resolve()):
            hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        for module in (main_api_app,)
    },
}
Path(os.environ["MEM07_IDENTITY_FILE"]).write_text(json.dumps(identity))
uvicorn.run(main_api_app.app, fd=int(sys.argv[1]), log_level="warning")
"""


def _boot_server(tmp_path: Path, env: dict, name: str,
                 capture_file: Path | None = None) -> dict:
    """Start the REAL main_api_app in a child OS process on a bound socket."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    log_path = tmp_path / f"{name}.log"
    identity_file = tmp_path / f"{name}-identity.json"
    log = log_path.open("w")
    log.write(f"# launch: {name}\n")
    log.write(f"# pid-parent: {os.getpid()}\n")
    log.write("# app: main_api_app:app (real production entry point)\n")
    log.write(f"# executable: {sys.executable}\n")
    log.write(f"# cwd: {BACKEND_DIR}\n")
    log.write(f"# scratch DATABASE_URL: {env['DATABASE_URL']}\n")
    log.flush()
    child_env = {
        key: value for key, value in env.items()
        if key != "MEM07_REVIEWER_PASSWORD"
    }
    child_env["MEM07_IDENTITY_FILE"] = str(identity_file)
    if capture_file is not None:
        child_env["MEM07_CAPTURE_FILE"] = str(capture_file)
    try:
        process = subprocess.Popen(
            [sys.executable, "-c", _SERVER_SCRIPT, str(listener.fileno())],
            cwd=str(BACKEND_DIR), env=child_env,
            pass_fds=(listener.fileno(),),
            stdout=log, stderr=subprocess.STDOUT,
        )
    finally:
        listener.close()  # child inherited the fd; parent's copy is done

    deadline = time.monotonic() + BOOT_DEADLINE_S
    while True:
        if process.poll() is not None:
            log.close()
            pytest.fail(
                f"{name} (real main_api_app child) exited rc="
                f"{process.returncode} before becoming ready; log tail:\n"
                f"{log_path.read_text()[-6000:]}")
        try:
            with urllib.request.urlopen(
                    base_url + "/api/health", timeout=2) as resp:
                if resp.status == 200:
                    break
        except (OSError, urllib.error.URLError):
            pass
        if time.monotonic() >= deadline:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            log.close()
            pytest.fail(
                f"{name} (real main_api_app child) not ready within "
                f"{BOOT_DEADLINE_S:.0f}s; log tail:\n"
                f"{log_path.read_text()[-6000:]}")
        time.sleep(0.25)
    identity = json.loads(identity_file.read_text())
    assert process.poll() is None
    assert identity["pid"] == process.pid
    assert Path(identity["database_file"]).resolve() == Path(
        env["MEM07_EXPECTED_DB"]).resolve()
    assert identity["capture"] == (capture_file is not None)
    return {"process": process, "base_url": base_url, "log": log,
            "log_path": log_path, "pid": process.pid, "identity": identity}


def _stop_server(server: dict) -> int:
    """Stop the child and WAIT for the real OS exit. Returns the exit rc."""
    process = server["process"]
    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
    server["log"].close()
    assert process.poll() is not None, "server child did not actually exit"
    return process.returncode


# ---------------------------------------------------------------------------
# HTTP helpers (real loopback sockets; no TestClient anywhere in this module)
# ---------------------------------------------------------------------------
def _request(method: str, url: str, token=None, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"raw": body}


def _login(base_url: str, email: str, password: str) -> str:
    status, body = _request(
        "POST", f"{base_url}/api/auth/login",
        payload={"username": email, "password": password})
    assert status == 200, f"login failed with HTTP {status}: {body}"
    token = body.get("access_token")
    assert token, "login returned no access_token"
    return token


def _captured_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _record_for(records: list[dict], request_text: str) -> dict:
    matches = [r for r in records if request_text in (r.get("prompt") or "")]
    assert matches, (
        f"no captured model request for {request_text!r}; captures: "
        f"{[ (r.get('prompt') or '')[:120] for r in records ]}")
    return matches[-1]


# ---------------------------------------------------------------------------
# The journey
# ---------------------------------------------------------------------------
def test_served_reviewed_prompt_skill_survives_process_restart(tmp_path):
    db_path = tmp_path / "scratch_mem07_served.db"
    secret_key = secrets.token_urlsafe(48)
    reviewer_password = secrets.token_urlsafe(18) + "!Aa1"  # kept private
    env = _scratch_child_env(
        tmp_path, db_path, secret_key, reviewer_password)
    _assert_scratch(env, tmp_path)

    seeded = _seed_world(env, tmp_path)
    marker = seeded["skill_name"]
    description = (seeded["skill_description"] or "").strip()
    generated_code = seeded["generated_code"]
    assert TASK in description

    capture_file = tmp_path / "served-captures.jsonl"

    # --- Phase A: real served app performs normal login/approve/apply ------
    server_a = _boot_server(tmp_path, env, "server_a_review")
    try:
        base_a = server_a["base_url"]
        assert server_a["pid"] != os.getpid()

        token = _login(base_a, seeded["reviewer_email"], reviewer_password)
        me_status, me = _request("GET", f"{base_a}/api/auth/me", token)
        assert me_status == 200, me

        approved_status, approved = _request(
            "POST",
            f"{base_a}/api/autodev/skills/{seeded['candidate_id']}/approve",
            token)
        assert approved_status == 200, approved
        assert approved["data"]["status"] == "validated", approved

        applied_status, applied = _request(
            "POST",
            f"{base_a}/api/autodev/skills/{seeded['candidate_id']}/apply",
            token)
        assert applied_status == 200, applied
        applied_data = applied["data"]
        assert applied_data["status"] == "promoted", applied_data
        assert applied_data["generated_code_applied"] is False, applied_data
        pid_a = server_a["pid"]
    finally:
        _stop_server(server_a)

    # The prompt-only package is on the scratch skill root; generated code
    # and executable files are never part of it.
    package = next(
        (tmp_path / "skills" / seeded["tenant_id"] / "skills").glob(
            f"{marker}_r*"))
    markdown = (package / "SKILL.md").read_text()
    assert description in markdown
    assert generated_code not in markdown
    assert not list(package.rglob("*.py"))

    # Durable state is in the scratch DB, not just memory.
    with sqlite3.connect(db_path) as conn:
        candidate_status = conn.execute(
            "SELECT validation_status FROM skill_candidates "
            "WHERE id = ?", (seeded["candidate_id"],)).fetchone()
        assert candidate_status and candidate_status[0] == "promoted"
        assert conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == 1

    # --- Phase B: NEW OS process consumes the skill via the ordinary run --
    server_b = _boot_server(
        tmp_path, env, "server_b_run", capture_file=capture_file)
    try:
        base_b = server_b["base_url"]
        pid_b = server_b["pid"]
        assert pid_b != pid_a, "restart must be a new OS process"
        assert server_b["identity"]["source_files"] == \
            server_a["identity"]["source_files"]

        token_b = _login(base_b, seeded["reviewer_email"], reviewer_password)
        other_token = _login(
            base_b, seeded["other_member_email"], reviewer_password)

        ok_status, ok_body = _request(
            "POST",
            f"{base_b}/api/agents/{seeded['agent_id']}/run"
            f"?operation_id=served-restart-ok-{uuid.uuid4().hex[:8]}",
            token_b,
            {"parameters": {"task_input": REQUEST_OK, "sync": True}},
        )
        assert ok_status == 200, ok_body
        ok_data = ok_body.get("data") or {}
        assert ok_data.get("job_status") == "success", ok_body

        other_status, other_body = _request(
            "POST",
            f"{base_b}/api/agents/{seeded['other_agent_id']}/run"
            f"?operation_id=served-restart-other-{uuid.uuid4().hex[:8]}",
            other_token,
            {"parameters": {"task_input": REQUEST_OTHER, "sync": True}},
        )
        assert other_status == 200, other_body
        other_data = other_body.get("data") or {}
        assert other_data.get("job_status") == "success", other_body

        records = _captured_records(capture_file)
        assert records, "the controlled model leaf was never reached"
        assert {r["pid"] for r in records} == {pid_b}
        assert all(r["response_model"] == "ReActStep" for r in records)

        # Correct scope: the reviewed prompt skill is consumed by the
        # ordinary run path of a NEW process on the same durable state.
        ok_record = _record_for(records, REQUEST_OK)
        assert ok_record.get("agent_id") == seeded["agent_id"]
        ok_system = ok_record.get("system_instruction") or ""
        assert marker in ok_system, ok_record
        assert description in ok_system
        assert INJECTION_HEADER in ok_system
        assert generated_code not in ok_system
        assert generated_code not in (ok_record.get("prompt") or "")

        # Wrong workspace of the same tenant: no marker, no injection block.
        other_record = _record_for(records, REQUEST_OTHER)
        assert other_record.get("agent_id") == seeded["other_agent_id"]
        other_system = other_record.get("system_instruction") or ""
        assert marker not in other_system, other_record
        assert "The following skills may be relevant" not in other_system
        assert description not in other_system
    finally:
        _stop_server(server_b)

    # Both runs were served by distinct PIDs from the parent, in sequence.
    assert {pid_a, pid_b}.isdisjoint({os.getpid()})
