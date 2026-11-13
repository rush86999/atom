"""Reviewed executable skill survives a REAL service restart.

This is the served-restart twin of ``tests/test_reviewed_executable_skill.py``
and ``tests/test_reviewed_executable_skill_docker.py``.  It deliberately uses
the full production entry point rather than an in-test FastAPI app:

* a scratch world (SQLite file, data root, workspace skill root, LanceDB roots)
  is seeded in a child OS process before any server starts;
* server process A runs ``main_api_app:app`` on a bound loopback socket and
  performs an ordinary ``POST /api/auth/login``, the public
  ``POST /api/autodev/skills/{candidate_id}/approve`` review call, and the
  explicit bodyless ``POST /api/autodev/skills/{candidate_id}/apply-executable``
  call.  There is no direct service apply and no test app;
* server process A is stopped and process B is started on the SAME durable
  scratch state; B has a different pid, a fresh login, and executes the
  registered skill through the ordinary ``POST /api/skills/execute`` route;
* execution runs the reviewed benign arithmetic in a REAL ``skill_*`` Docker
  container (no host fallback), and the durable ``SkillExecution`` receipt is
  re-read from SQLite after the service has stopped.

Isolation follows the MEM-07 restart pattern
(``tests/test_mem07_prompt_skill_process_restart.py`` and its served twin
``tests/test_mem07_served_prompt_skill_process_restart.py``): every child
freezes/verifies its scratch database before importing a product surface,
provider/account secrets are stripped, only loopback HTTP is used, and no live
DB, scheduler, ingestion worker, or external provider is contacted.  The only
product leaf doubled inside the server child is the LLM-based skill security
scanner (deterministic ``LOW``): the reviewed artifact and Docker sandbox are
real.

The Docker availability check happens AFTER the seed/login/approve/apply and
restart phases, so a Docker-less local host still exercises every pre-container
layer and then skips.  Hosted CI must set ``ATOM_REQUIRE_DOCKER_SANDBOX=1`` so
an unavailable daemon fails instead of skipping.
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
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

BOOT_DEADLINE_S = 180.0
SEED_DEADLINE_S = 150.0

REVIEWER_EMAIL = "executable-restart@example.invalid"
CANDIDATE_ID = "cand-reviewed-executable-restart"
SKILL_NAME = "reviewed_arithmetic"
SKILL_DESCRIPTION = "deterministically add and multiply two integers"

BENIGN_CODE = (
    "def execute(inputs):\n"
    "    left = int(inputs.get(\"left\", 0))\n"
    "    right = int(inputs.get(\"right\", 0))\n"
    "    return {\"sum\": left + right, \"product\": left * right}\n"
)
SYNTHETIC_INPUTS = {"left": 19, "right": 23}
EXPECTED_RESULT = {"sum": 42, "product": 437}
RECEIPT_SCHEMA = "atom-reviewed-executable-receipt-1"


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
        # TESTING=1 alone forces the shared test DB; the pytest branch honors
        # the explicit NON-dev scratch URL.  The app lifespan then skips
        # create_all (the seed child owns fresh schema init).
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
        # BYOKManager persists defaults/keys to __file__-anchored paths under
        # backend/data when these are unset; pin every one to the scratch tree.
        "BYOK_CONFIG_FILE": str(tmp_path / "byok_config.json"),
        "BYOK_KEYS_FILE": str(tmp_path / "byok_keys.json"),
        "BYOK_ENC_KEY_FILE": str(tmp_path / "byok_encryption_key"),
        "ATOM_PROVIDER_MODEL_CATALOG_PATH": str(
            tmp_path / "provider_model_catalog.json"),
        "REX_EXPECTED_DB": str(db_path.resolve()),
        "REX_REVIEWER_PASSWORD": reviewer_password,
        "REX_REVIEWER_EMAIL": REVIEWER_EMAIL,
        "REX_CANDIDATE_ID": CANDIDATE_ID,
        "REX_SKILL_NAME": SKILL_NAME,
        "REX_SKILL_DESCRIPTION": SKILL_DESCRIPTION,
        "REX_BENIGN_CODE": BENIGN_CODE,
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
                "LANCEDB_URI", "LANCEDB_PATH", "LANCEDB_URI_BASE",
                "BYOK_CONFIG_FILE", "BYOK_KEYS_FILE", "BYOK_ENC_KEY_FILE",
                "ATOM_PROVIDER_MODEL_CATALOG_PATH"):
        path = Path(env[var]).resolve()
        assert tmp_path.resolve() in path.parents or path == tmp_path.resolve(), (
            f"scratch refusal: {var}={path} is not under tmp_path")
    assert Path(env["REX_EXPECTED_DB"]).resolve() == db_file


# ---------------------------------------------------------------------------
# Child 1: seed the scratch world and one pending reviewed candidate
# ---------------------------------------------------------------------------
_SEED_SCRIPT = r"""
import json
import os
from pathlib import Path

expected = Path(os.environ["REX_EXPECTED_DB"]).resolve()

# Freeze/verify scratch before any product surface sees the world.
from core.database import engine

actual = Path(engine.url.database).resolve()
if not engine.url.drivername.startswith("sqlite") or actual != expected:
    raise SystemExit(f"seed child refused a non-scratch database: {engine.url}")
if os.environ.get("TESTING") != "1":
    raise SystemExit("seed child refused without TESTING=1")

import core.models  # noqa: F401 - register tables on the shared Base
from core.auto_dev import models as autodev_models  # noqa: F401
from core.auto_dev.models import SkillCandidate
from core.auth import get_password_hash
from core.database import Base, SessionLocal
from core.models import AgentRegistry, Tenant, User, Workspace

Base.metadata.create_all(engine)

tenant_id = "tenant-reviewed-executable-restart"
workspace_id = "ws-reviewed-executable-restart"
agent_id = "agent-reviewed-executable-restart"
reviewer_id = "reviewer-reviewed-executable-restart"
password = os.environ["REX_REVIEWER_PASSWORD"]

with SessionLocal() as db:
    tenant = Tenant(
        id=tenant_id, name="Reviewed Executable Restart Tenant",
        subdomain="reviewed-executable-restart")
    workspace = Workspace(
        id=workspace_id, name="Reviewed Executable Restart Workspace",
        tenant_id=tenant_id,
        metadata_json={"auto_dev": {"enabled": True}})
    agent = AgentRegistry(
        id=agent_id, name="Reviewed Executable Restart Employee",
        category="operations", module_path="core.generic_agent",
        class_name="GenericAgent", status="intern", confidence_score=0.5,
        configuration={"capability_maturities": {"*": "intern"}},
        capabilities=[], workspace_id=workspace_id, tenant_id=tenant_id,
        enabled=True)
    reviewer = User(
        id=reviewer_id, email=os.environ["REX_REVIEWER_EMAIL"],
        hashed_password=get_password_hash(password),
        first_name="R", last_name="V", role="team_lead", status="active",
        workspace_id=workspace_id, tenant_id=tenant_id, is_active=True)
    candidate = SkillCandidate(
        id=os.environ["REX_CANDIDATE_ID"], tenant_id=tenant_id,
        agent_id=agent_id, source_episode_id="episode-reviewed-executable",
        skill_name=os.environ["REX_SKILL_NAME"],
        skill_description=os.environ["REX_SKILL_DESCRIPTION"],
        generated_code=os.environ["REX_BENIGN_CODE"],
        failure_pattern={"failure_summary": "could not add two integers"},
        validation_status="pending")
    db.add_all([tenant, workspace, agent, reviewer, candidate])
    db.commit()
    db.refresh(candidate)

    payload = {
        "pid": os.getpid(),
        "database_file": str(actual),
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "agent_id": agent_id,
        "reviewer_id": reviewer_id,
        "reviewer_email": reviewer.email,
        "candidate_id": candidate.id,
        "skill_name": candidate.skill_name,
        "skill_description": candidate.skill_description,
        "generated_code": candidate.generated_code,
        "validation_status": candidate.validation_status,
    }
    Path(os.environ["REX_RESULT_FILE"]).write_text(json.dumps(payload))

engine.dispose()
"""


def _seed_world(env: dict, tmp_path: Path) -> dict:
    result_file = tmp_path / "seed-result.json"
    child_env = dict(env, REX_RESULT_FILE=str(result_file))
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
        env["REX_EXPECTED_DB"]).resolve()
    assert payload["validation_status"] == "pending"
    assert payload["generated_code"] == BENIGN_CODE
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

expected = Path(os.environ["REX_EXPECTED_DB"]).resolve()

# Freeze/verify scratch before main_api_app (or any service) is imported.
from core.database import engine

actual = Path(engine.url.database).resolve()
if not engine.url.drivername.startswith("sqlite") or actual != expected:
    raise SystemExit(f"server child refused a non-scratch database: {engine.url}")
if os.environ.get("TESTING") != "1":
    raise SystemExit("server child refused without TESTING=1")

# Only the LLM security scanner leaf is doubled.  The reviewed artifact,
# approval/apply routes, registry rows and Docker sandbox stay real.
import core.skill_registry_service as skill_registry_service


class _DeterministicScanner:
    async def scan_skill(self, skill_name, skill_content):
        return {"safe": True, "risk_level": "LOW", "findings": []}


skill_registry_service.SkillSecurityScanner = _DeterministicScanner

import main_api_app
import uvicorn

identity = {
    "pid": os.getpid(),
    "database_file": str(actual),
    "source_files": {
        str(Path(module.__file__).resolve()):
            hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        for module in (main_api_app,)
    },
}
Path(os.environ["REX_IDENTITY_FILE"]).write_text(json.dumps(identity))
uvicorn.run(main_api_app.app, fd=int(sys.argv[1]), log_level="warning")
"""


def _boot_server(tmp_path: Path, env: dict, name: str) -> dict:
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
        if key != "REX_REVIEWER_PASSWORD"
    }
    child_env["REX_IDENTITY_FILE"] = str(identity_file)
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
        env["REX_EXPECTED_DB"]).resolve()
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


def _docker_unavailable_reason():
    """Why a REAL Docker daemon is unavailable, or None when it is usable.

    A test double left in ``sys.modules`` must never be mistaken for a daemon:
    that would let this real-Docker acceptance run against nothing (the failure
    then looks like a product bug instead of test pollution).  In hosted CI
    ``ATOM_REQUIRE_DOCKER_SANDBOX=1`` turns a polluted/missing probe into a
    failure, never a skip.
    """
    try:
        import docker

        client = docker.from_env()
        if not type(client).__module__.startswith("docker"):
            return (
                "Docker SDK is mocked in this process "
                f"({type(client).__module__}); no real daemon was probed")
        client.ping()
        return None
    except Exception as exc:  # noqa: BLE001 - reported verbatim
        return f"{type(exc).__name__}: {exc}"


def _source_revision() -> str:
    if os.getenv("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=30)
        if completed.returncode == 0:
            return completed.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


def _json_column(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def _execution_failure_diagnostics(db_path: Path, execute_data: dict,
                                   log_path: Path) -> dict:
    """Collect the whole failure, not the 240-char repr pytest shows.

    The #918 CI log only carried ``SANDBOX_ERROR: Sa...`` because pytest
    truncates a long assertion dict in the middle.  The durable row and the
    server child log both hold the complete cause, so put them in one payload
    that the failure message and a per-test JSON file can carry verbatim.
    """
    row = None
    execution_id = execute_data.get("execution_id")
    if execution_id:
        try:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT status, error_message, container_id, exit_code, "
                    "stdout, stderr, audit_metadata FROM skill_executions "
                    "WHERE id = ?", (execution_id,)).fetchone()
        except sqlite3.Error as exc:  # diagnostics must never mask the failure
            row = (f"<sqlite error: {exc}>",)
    columns = ("status", "error_message", "container_id", "exit_code",
               "stdout", "stderr", "audit_metadata")
    try:
        log_tail = log_path.read_text(errors="replace")[-8000:]
    except OSError as exc:
        log_tail = f"<log unreadable: {exc}>"
    return {
        "execute_response": execute_data,
        "durable_execution": dict(zip(columns, row)) if row else None,
        "server_log_tail": log_tail,
    }


# ---------------------------------------------------------------------------
# The journey
# ---------------------------------------------------------------------------
def test_reviewed_executable_skill_survives_service_restart(tmp_path):
    db_path = tmp_path / "scratch_reviewed_executable_restart.db"
    secret_key = secrets.token_urlsafe(48)
    reviewer_password = secrets.token_urlsafe(18) + "!Aa1"  # kept private
    env = _scratch_child_env(
        tmp_path, db_path, secret_key, reviewer_password)
    _assert_scratch(env, tmp_path)

    seeded = _seed_world(env, tmp_path)
    assert seeded["skill_name"] == SKILL_NAME
    assert seeded["skill_description"] == SKILL_DESCRIPTION

    # --- Phase A: real served app performs ordinary login/approve/apply ----
    server_a = _boot_server(tmp_path, env, "server_a_review")
    pid_a = server_a["pid"]
    try:
        base_a = server_a["base_url"]
        assert pid_a != os.getpid()

        token = _login(base_a, REVIEWER_EMAIL, reviewer_password)
        me_status, me = _request("GET", f"{base_a}/api/auth/me", token)
        assert me_status == 200, me
        assert me["id"] == seeded["reviewer_id"]
        assert me["email"] == REVIEWER_EMAIL

        approved_status, approved = _request(
            "POST",
            f"{base_a}/api/autodev/skills/{seeded['candidate_id']}/approve",
            token)
        assert approved_status == 200, approved
        assert approved["data"]["status"] == "validated", approved

        # Bodyless explicit apply: approval alone must not write executable
        # artifacts, and this is the only apply path used by the test.
        applied_status, applied = _request(
            "POST",
            f"{base_a}/api/autodev/skills/{seeded['candidate_id']}"
            f"/apply-executable",
            token)
        assert applied_status == 200, applied
        applied_data = applied["data"]
        assert applied_data["status"] == "promoted", applied_data
        assert applied_data["generated_code_applied"] is True, applied_data
        assert applied_data["execution_kind"] == "reviewed_executable"
        assert applied_data["sandbox_backend"] == "docker"
        assert applied_data["review_revision"] == approved["data"][
            "review_revision"]
        assert applied_data["review_digest"] == approved["data"][
            "review_digest"]
        registry_id = applied_data["registry_execution_id"]
        skill_id = applied_data["skill_id"]
        executable_sha = applied_data["executable_code_sha256"]
    finally:
        rc_a = _stop_server(server_a)
    assert rc_a is not None, "server A did not report a real OS exit"

    # Pre-Docker durable state: the reviewed package and both registry rows
    # exist on the scratch filesystem/DB, not only in the HTTP response.
    package = next(
        (tmp_path / "skills" / seeded["tenant_id"] / "skills").glob(
            f"{SKILL_NAME}_r*"))
    markdown = (package / "SKILL.md").read_text()
    assert BENIGN_CODE.strip() in markdown
    assert "atom reviewed executable harness (trusted, fixed)" in markdown
    assert not list(package.rglob("*.py"))

    with sqlite3.connect(db_path) as conn:
        candidate_status = conn.execute(
            "SELECT validation_status FROM skill_candidates WHERE id = ?",
            (seeded["candidate_id"],)).fetchone()
        assert candidate_status and candidate_status[0] == "promoted"

        skill_row = conn.execute(
            "SELECT id, type, code, config FROM skills WHERE id = ?",
            (skill_id,)).fetchone()
        assert skill_row is not None
        assert skill_row[1] == "script"
        assert BENIGN_CODE.strip() in skill_row[2]
        skill_config = _json_column(skill_row[3])
        assert skill_config["sandbox"] == "docker"
        assert skill_config["entrypoint"] == "execute"
        assert skill_config["reviewed_executable"]["candidate_id"] == (
            seeded["candidate_id"])
        assert skill_config["reviewed_executable"][
            "executable_code_sha256"] == executable_sha

        registry_row = conn.execute(
            "SELECT status, sandbox_enabled, input_params "
            "FROM skill_executions WHERE id = ?", (registry_id,)).fetchone()
        assert registry_row is not None
        assert registry_row[0] == "Active"
        assert registry_row[1] in (1, True)
        registry_params = _json_column(registry_row[2])
        assert registry_params["reviewed_executable"][
            "review_digest"] == applied_data["review_digest"]

    # --- Phase B: NEW OS process consumes the skill via the ordinary route --
    server_b = _boot_server(tmp_path, env, "server_b_execute")
    pid_b = server_b["pid"]
    try:
        base_b = server_b["base_url"]
        assert pid_b != pid_a, "restart must be a new OS process"
        assert server_b["identity"]["source_files"] == \
            server_a["identity"]["source_files"]

        token_b = _login(base_b, REVIEWER_EMAIL, reviewer_password)
        me_status, me_b = _request("GET", f"{base_b}/api/auth/me", token_b)
        assert me_status == 200, me_b
        assert me_b["id"] == seeded["reviewer_id"]

        # Pre-Docker verification deliberately happens after the restart and
        # fresh login, so a Docker-less host still proves the full reviewed
        # apply/restart chain before skipping only the container replay.
        reason = _docker_unavailable_reason()
        if reason is not None:
            if os.getenv("ATOM_REQUIRE_DOCKER_SANDBOX") == "1":
                pytest.fail(
                    "ATOM_REQUIRE_DOCKER_SANDBOX=1 but the Docker daemon is "
                    f"not reachable after the pre-Docker phases: {reason}")
            pytest.skip(
                "pre-Docker phases passed (seed/login/approve/apply/restart); "
                f"Docker daemon unavailable: {reason}")

        execute_status, execute_body = _request(
            "POST", f"{base_b}/api/skills/execute", token_b,
            {
                "skill_id": registry_id,
                "inputs": SYNTHETIC_INPUTS,
                "agent_id": seeded["agent_id"],
            })
        assert execute_status == 200, execute_body
        execute_data = execute_body["data"]
        if execute_data.get("success") is not True:
            diagnostics = _execution_failure_diagnostics(
                db_path, execute_data, server_b["log_path"])
            (tmp_path / "execute-failure.json").write_text(
                json.dumps(diagnostics, indent=2, sort_keys=True, default=str),
                encoding="utf-8")
            # Fail with plain text: pytest's assertion rewriting truncates a
            # long dict mid-value, which is why #918 only showed the cause as
            # "SANDBOX_ERROR: Sa...".
            pytest.fail(
                "reviewed executable execution failed:\n"
                + json.dumps(diagnostics, indent=2, sort_keys=True,
                             default=str))
        assert execute_data["success"] is True, execute_data
        assert json.loads(execute_data["result"]) == EXPECTED_RESULT
        execution_id = execute_data["execution_id"]

        receipt = execute_data["reviewed_executable"]
        sandbox = receipt["sandbox"]
        assert receipt["schema"] == RECEIPT_SCHEMA
        assert receipt["binding"]["verified"] is True
        assert receipt["binding"]["candidate_id"] == seeded["candidate_id"]
        assert receipt["binding"]["review_revision"] == (
            applied_data["review_revision"])
        assert receipt["binding"]["review_digest"] == (
            applied_data["review_digest"])
        assert receipt["binding"]["executable_code_sha256"] == executable_sha
        assert receipt["binding"]["tenant_id"] == seeded["tenant_id"]
        assert receipt["binding"]["workspace_id"] == seeded["workspace_id"]
        assert receipt["binding"]["agent_id"] == seeded["agent_id"]
        assert receipt["executed_by"] == seeded["reviewer_id"]
        assert receipt["registry_execution_id"] == registry_id
        assert receipt["inputs_sha256"]
        assert receipt["result_sha256"]
        assert sandbox["backend"] == "docker"
        assert sandbox["ran"] is True
        assert sandbox["container_id"].startswith("skill_")
        assert sandbox["docker_container_id"], (
            "the sandbox must report the Docker container id it created")
        assert sandbox["image"] == "python:3.11-slim"
        assert sandbox["network_disabled"] is True
        assert sandbox["read_only"] is True
        # The sandbox owns removal; these are observed results, not claims.
        assert sandbox["ephemeral"] is True
        assert sandbox["removed"] is True
        assert sandbox["cleanup_error"] is None
        assert sandbox["timed_out"] is False
        assert sandbox["exit_code"] == 0
        assert sandbox["nonce"] and sandbox["nonce"] == sandbox["nonce_echo"]
        container_id = sandbox["container_id"]
        docker_container_id = sandbox["docker_container_id"]
    finally:
        rc_b = _stop_server(server_b)
    assert rc_b is not None, "server B did not report a real OS exit"

    # Durable receipt: re-read the row from the same scratch SQLite file
    # after the executing service process has stopped.
    with sqlite3.connect(db_path) as conn:
        execution_row = conn.execute(
            "SELECT status, skill_id, output_result, container_id, exit_code, "
            "audit_metadata FROM skill_executions WHERE id = ?",
            (execution_id,)).fetchone()
    assert execution_row is not None
    status, linked_skill_id, output_result, row_container, exit_code, audit = (
        execution_row)
    assert status == "success"
    assert linked_skill_id == skill_id
    assert json.loads(_json_column(output_result)["result"]) == EXPECTED_RESULT
    assert row_container == container_id
    assert exit_code == 0

    persisted = _json_column(audit)["reviewed_executable"]
    assert persisted["schema"] == RECEIPT_SCHEMA
    assert persisted["status"] == "success"
    assert persisted["binding"]["verified"] is True
    assert persisted["binding"]["candidate_id"] == seeded["candidate_id"]
    assert persisted["binding"]["review_revision"] == (
        applied_data["review_revision"])
    assert persisted["binding"]["review_digest"] == (
        applied_data["review_digest"])
    assert persisted["binding"]["executable_code_sha256"] == executable_sha
    assert persisted["binding"]["tenant_id"] == seeded["tenant_id"]
    assert persisted["binding"]["workspace_id"] == seeded["workspace_id"]
    assert persisted["binding"]["agent_id"] == seeded["agent_id"]
    assert persisted["binding"]["registry_execution_id"] == registry_id
    assert persisted["executed_by"] == seeded["reviewer_id"]
    assert persisted["sandbox"]["backend"] == "docker"
    assert persisted["sandbox"]["ran"] is True
    assert persisted["sandbox"]["container_id"] == container_id
    assert persisted["sandbox"]["docker_container_id"] == docker_container_id
    assert persisted["sandbox"]["network_disabled"] is True
    assert persisted["sandbox"]["read_only"] is True
    assert persisted["sandbox"]["ephemeral"] is True
    assert persisted["sandbox"]["removed"] is True
    assert persisted["sandbox"]["cleanup_error"] is None
    assert persisted["sandbox"]["timed_out"] is False
    assert persisted["sandbox"]["exit_code"] == 0
    assert persisted["sandbox"]["nonce"] == persisted["sandbox"]["nonce_echo"]
    assert persisted["inputs_sha256"] and persisted["result_sha256"]

    # The container must really be gone: a truthful receipt is not enough if a
    # stopped-but-present container leaked.  (Docker is reachable here; the
    # unavailable case skipped above.)
    import docker as docker_sdk

    live_client = docker_sdk.from_env()
    try:
        leftover = live_client.containers.get(container_id)
    except docker_sdk.errors.NotFound:
        leftover = None
    finally:
        live_client.close()
    assert leftover is None, (
        f"sandbox container {container_id} still exists after the durable "
        "receipt claimed removal")

    # Every durable receipt assertion above has passed.  Emit a portable
    # acceptance record (no tokens, passwords, or secret material) for CI.
    record = {
        "acceptance_schema": "atom-reviewed-executable-restart-1",
        "source_revision": _source_revision(),
        "provider_simulated": True,
        "provider_detail": "LLM security scan stubbed to LOW",
        "docker_sandbox_real": True,
        "service_restart_real": True,
        "service_pids": {"review": pid_a, "execute": pid_b},
        "source_files_identical_across_restart": True,
        "seed_pid": seeded["pid"],
        "database_file": seeded["database_file"],
        "candidate_id": seeded["candidate_id"],
        "skill_id": skill_id,
        "execution_id": execution_id,
        "registry_execution_id": registry_id,
        "review_revision": applied_data["review_revision"],
        "review_digest": applied_data["review_digest"],
        "executable_code_sha256": executable_sha,
        "container_id": container_id,
        "docker_container_id": docker_container_id,
        "sandbox_backend": sandbox["backend"],
        "image": sandbox["image"],
        "nonce_echo_verified": True,
        "sandbox_container_removed": persisted["sandbox"]["removed"],
        "sandbox_cleanup_error": persisted["sandbox"]["cleanup_error"],
        "sandbox_timed_out": persisted["sandbox"]["timed_out"],
        "result": EXPECTED_RESULT,
        "durable_receipt_verified": True,
        "binding": {
            "verified": persisted["binding"]["verified"],
            "candidate_id": persisted["binding"]["candidate_id"],
            "review_revision": persisted["binding"]["review_revision"],
            "review_digest": persisted["binding"]["review_digest"],
            "executable_code_sha256": persisted["binding"][
                "executable_code_sha256"],
            "tenant_id": persisted["binding"]["tenant_id"],
            "workspace_id": persisted["binding"]["workspace_id"],
            "agent_id": persisted["binding"]["agent_id"],
            "registry_execution_id": persisted["binding"][
                "registry_execution_id"],
        },
    }
    print("REVIEWED_EXECUTABLE_RESTART_ACCEPTANCE=" + json.dumps(
        record, sort_keys=True))
    output = os.getenv("ATOM_ACCEPTANCE_OUTPUT")
    if output:
        Path(output).write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
