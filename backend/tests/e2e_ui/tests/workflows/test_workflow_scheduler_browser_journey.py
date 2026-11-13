"""J8 — browser scheduler restart + approval journey (isolated acceptance).

Work order (START_HERE_SUCCESSOR.md, final paragraph):

* use the supported interval selector on ``pages/workflows/schedule.tsx``;
* register a benign workflow through the browser and capture the job id;
* restart the backend *before* the job's due time;
* observe the same persisted job produce a correlated execution without
  anyone invoking the execution endpoint;
* for a workflow with an approval step, show the effect is absent before
  approval, decide through the mounted ``/approvals`` UI, and confirm one
  persisted effect plus a completed execution after a refresh;
* remove the recurring schedule after the observation window;
* no external write, live provider, or live database.

This test owns its whole stack (backend + Next dev server) on isolated
ports.  It never touches port 8001/3001, the repository's dev databases, or
any provider credential.  Static evidence goes to ``J8_SCRATCH_DIR``.

Two run modes are deliberate:

``J8_RUN_MODE=unmounted`` (default)
    The real ``main_api_app`` boot, unmodified.  This is the mounted product
    path.  On exact main 31cedd241 it fails at the scheduler-start boundary
    (recorded blocker): the SQLAlchemy jobstore cannot pickle the resumed
    system-pipeline bound methods (``_thread.lock``), so
    ``WorkflowScheduler.start()`` raises and every workflow schedule is only
    a pending in-memory job.  The test still drives the browser scheduling
    flow, restarts the backend, and proves the job/execution do not survive.

``J8_RUN_MODE=fixture-stub``
    The same real app with ONE documented fixture seam applied: the
    ``reschedule_system_pipelines`` hook is a no-op, exactly as every
    existing scheduler test already does
    (``tests/test_workflow_scheduled_process_restart.py``,
    ``tests/test_workflow_public_approval_flow.py``,
    ``tests/test_workflow_scheduler_recovery.py``).  Workflow scheduling,
    the APScheduler SQLAlchemy jobstore, the restart, the durable
    WorkflowEngine, governance HITL, the approval UI and the local
    ``database.create`` effect are all real.  Bounded coverage, not a claim
    about unattended system-pipeline ingestion.

The product profile's default ``core`` release defers the Automations
capability, which hides ``/workflows/schedule`` behind "not part of this
release".  Both modes enable only that capability through the documented
``ATOM_PRODUCT_PROFILE_PATH`` override; no source file is changed for it.

Prerequisites supplied by the runner environment (never invented here)::

    TESTING=1
    J8_SCRATCH_DIR=<absolute dir outside the checkout>
    J8_RUN_MODE=unmounted|fixture-stub
    J8_NODE_MODULES_SOURCE=<existing node_modules dir>  # only if absent

Optional (defaults keep the journey unchanged)::

    J8_BACKEND_STARTUP_TIMEOUT=<seconds>  # backend /alive deadline; default 180

Run from ``backend/``::

    TESTING=1 J8_SCRATCH_DIR=... J8_RUN_MODE=fixture-stub \\
      /usr/local/bin/python3 -m pytest \\
      tests/e2e_ui/tests/workflows/test_workflow_scheduler_browser_journey.py \\
      -q -s
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
# ---------------------------------------------------------------------------
# Fixed identities for the scratch world (never a live account).
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[4]
REPO_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = REPO_ROOT / "frontend-nextjs"

WORKFLOW_ID = "j8-browser-benign"
AGENT_ID = "j8-browser-agent"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "J8ScratchAdmin!123"
SERVER_SECRET = "j8-scratch-secret-0123456789abcdef"
NEXTAUTH_SECRET = "j8-nextauth-secret-0123456789abcdef"
INTERVAL_MINUTES = int(os.getenv("J8_INTERVAL_MINUTES", "2"))
BACKEND_PORT = int(os.getenv("J8_BACKEND_PORT", "8031"))
FRONTEND_PORT = int(os.getenv("J8_FRONTEND_PORT", "3031"))
# Backend readiness deadline.  The real main_api_app boot does a lot of work
# (route registration, DB bootstrap) before Uvicorn serves /alive, and on a
# slow volume it can overrun 180s while still making progress — observed with
# the scheduler jobstore already holding both system jobs.  Overridable for
# that case; the default is unchanged.
BACKEND_STARTUP_TIMEOUT = float(os.getenv("J8_BACKEND_STARTUP_TIMEOUT", "180"))
RUN_MODE = os.getenv("J8_RUN_MODE", "unmounted").strip()
STUB_SYSTEM_PIPELINES = RUN_MODE == "fixture-stub"

BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"

# The effect is the engine's own durable dispatch record for the harmless
# registered ``database.create`` action.  It is a local SQLite row; no
# transport, provider, file export, or external service is involved.
EFFECT_TABLE = "analytics_workflow_logs"

# Opt-in only: this acceptance owns two ports and a full stack, so it must
# never execute (or fail setup) during an ordinary suite collection.
pytestmark = pytest.mark.skipif(
    not os.getenv("J8_SCRATCH_DIR"),
    reason="J8 browser scheduler acceptance requires the isolated J8_SCRATCH_DIR harness",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prefix() -> str:
    return "fixture-stub" if STUB_SYSTEM_PIPELINES else "unmounted"


# ---------------------------------------------------------------------------
# HTTP helpers (proxy-free loopback only).
# ---------------------------------------------------------------------------

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_json(path: str, *, method: str = "GET", body=None, token=None,
              timeout: float = 30.0):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(BACKEND_URL + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with _OPENER.open(request, timeout=timeout) as response:
        payload = response.read()
        return response.status, (json.loads(payload) if payload else {})


def wait_http_ok(url: str, timeout: float, interval: float = 0.5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with _OPENER.open(url, timeout=3) as response:
                if 200 <= response.status < 400:
                    return True
        except Exception:  # noqa: BLE001 - startup polling
            pass
        time.sleep(interval)
    return False


def login() -> str:
    status, payload = http_json(
        "/api/auth/login", method="POST",
        body={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert status == 200, payload
    token = payload.get("access_token")
    assert token, payload
    return token


# ---------------------------------------------------------------------------
# SQLite evidence helpers (scratch database only).
# ---------------------------------------------------------------------------

def db_rows(sql: str, params=()):
    con = sqlite3.connect(SCRATCH / "app.db", timeout=15)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def job_rows():
    con = sqlite3.connect(SCRATCH / "jobs.db", timeout=15)
    try:
        table = con.execute(
            "select name from sqlite_master where type='table' "
            "and name='apscheduler_jobs'").fetchone()
        if not table:
            return []
        return [
            {"id": row[0],
             "next_run_epoch": row[1],
             "next_run_iso": (
                 datetime.fromtimestamp(float(row[1]), timezone.utc).isoformat()
                 if row[1] is not None else None)}
            for row in con.execute(
                "select id, next_run_time from apscheduler_jobs").fetchall()
        ]
    finally:
        con.close()


# A normal-mode boot persists the two System Pipeline jobs
# (``system_sales_ingestion`` / ``system_projects_ingestion``), so the
# jobstore and the scheduler API are legitimately non-empty after the user
# schedule is removed.  Removal assertions are therefore scoped to the exact
# job id, while these ids verify the system jobs were preserved.
SYSTEM_JOB_PREFIX = "system_"


def is_system_job_id(job_id: str) -> bool:
    return str(job_id).startswith(SYSTEM_JOB_PREFIX)


def system_job_ids_from_rows(rows) -> set[str]:
    return {row["id"] for row in rows if is_system_job_id(row["id"])}


def system_job_ids_from_api(jobs) -> set[str]:
    return {str(job.get("id")) for job in jobs
            if is_system_job_id(job.get("id", ""))}


def effect_count(execution_id: str) -> int:
    rows = db_rows(
        f"select count(*) as n from {EFFECT_TABLE} where execution_id=?",
        (execution_id,))
    return int(rows[0]["n"])


def workflow_executions() -> list[dict]:
    return db_rows(
        "select execution_id, workflow_id, status, input_data, outputs, "
        "created_at, completed_at, error from workflow_executions "
        "where workflow_id=? order by rowid", (WORKFLOW_ID,))


def hitl_rows(execution_id: str) -> list[dict]:
    return db_rows(
        "select id, action_type, status, reason, params, reviewed_by "
        "from hitl_actions where params like ?", (f"%{execution_id}%",))


# ---------------------------------------------------------------------------
# Process / port helpers.
# ---------------------------------------------------------------------------

def assert_port_free(port: int) -> None:
    assert port not in (8001, 3001), (
        f"refusing to use live port {port}; this acceptance owns isolated ports")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise AssertionError(
                f"port {port} is already in use; refusing to disturb a "
                f"pre-existing process ({exc})") from exc


def stop_process(process: subprocess.Popen, name: str) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        process.wait(timeout=15)
    assert process.poll() is not None, f"{name} did not exit"


# ---------------------------------------------------------------------------
# Scratch world.
# ---------------------------------------------------------------------------

SCRATCH = Path(os.environ.get("J8_SCRATCH_DIR", "")).expanduser()
EVIDENCE = SCRATCH / "evidence"
WORKFLOWS_FILE = BACKEND_DIR / "workflows.json"
NEXT_DIST_REL = ".next-j8-browser"


def workflow_definition() -> dict:
    """A benign definition: one local DB action behind a governance pause.

    The definition source is a fixture input (the same boundary the public
    approval tests patch); the scheduler, engine, governance service, HITL
    row and effect are real.
    """
    return {
        "id": WORKFLOW_ID,
        "name": "J8 benign scheduled approval",
        "description": "Browser scheduler acceptance; no external effect.",
        "version": "1",
        "nodes": [],
        "connections": [],
        "triggers": [],
        "enabled": True,
        "agent_id": AGENT_ID,
        "steps": [{
            "id": "s1",
            "name": "Local database action",
            "service": "database",
            "action": "create",
            "parameters": {"record": "j8-benign"},
            "continue_on_error": False,
            "timeout": None,
            "input_schema": {},
            "output_schema": {},
        }],
    }


def product_profile_override() -> dict:
    """Enable only the deferred Automations capability (documented override).

    The default ``core`` release intentionally hides /workflows/*.  The work
    order names that page, so the isolated acceptance uses the supported
    profile-file switch rather than editing product code.
    """
    return {"capabilities": {"automations": {"enabled": True}}}


class Stack:
    def __init__(self):
        self.backend: subprocess.Popen | None = None
        self.frontend: subprocess.Popen | None = None
        self.token: str = ""
        self.restart_count = 0
        self.node_modules_created = False
        self.dist_created = False
        self.workflows_original: bytes | None = None
        self.workflows_fixture: bytes | None = None
        self.next_env_original: bytes | None = None
        self.env_manifest: dict = {}

    # -- setup ---------------------------------------------------------
    def prepare(self):
        assert SCRATCH and SCRATCH.is_absolute(), (
            "J8_SCRATCH_DIR must be an absolute path outside the checkout")
        assert SCRATCH.is_dir(), f"J8_SCRATCH_DIR does not exist: {SCRATCH}"
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        assert_port_free(BACKEND_PORT)
        assert_port_free(FRONTEND_PORT)
        assert RUN_MODE in {"unmounted", "fixture-stub"}, RUN_MODE

        # Exact source identity, before fixtures touch anything.
        self.env_manifest = {
            "run_mode": RUN_MODE,
            "stub_system_pipelines": STUB_SYSTEM_PIPELINES,
            "repo_root": str(REPO_ROOT),
            "git_head": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                capture_output=True, text=True).stdout.strip(),
            "git_status_porcelain": subprocess.run(
                ["git", "status", "--porcelain"], cwd=REPO_ROOT,
                capture_output=True, text=True).stdout,
            "backend_port": BACKEND_PORT,
            "frontend_port": FRONTEND_PORT,
            "interval_minutes": INTERVAL_MINUTES,
            "backend_startup_timeout_seconds": BACKEND_STARTUP_TIMEOUT,
            "python": sys.executable,
            "backend_url": BACKEND_URL,
            "frontend_url": FRONTEND_URL,
            "scratch": str(SCRATCH),
            "started_at": _now(),
        }
        _write_json(EVIDENCE / f"{_prefix()}-manifest.json", self.env_manifest)

        # 1. Workflow definition source: fixture in, exact bytes saved.
        self.workflows_original = WORKFLOWS_FILE.read_bytes()
        (EVIDENCE / "workflows.json.original").write_bytes(self.workflows_original)
        self.workflows_fixture = (
            json.dumps([workflow_definition()], indent=2) + "\n").encode()
        WORKFLOWS_FILE.write_bytes(self.workflows_fixture)
        (EVIDENCE / "workflows.json.fixture").write_bytes(self.workflows_fixture)
        _write_json(EVIDENCE / f"{_prefix()}-workflows-hashes.json", {
            "original_sha256": _sha256(self.workflows_original),
            "fixture_sha256": _sha256(self.workflows_fixture),
            "tracked_file": "backend/workflows.json",
            "restored_after_run": False,
        })

        # 2. Product profile override (only the release-surface gate).
        profile_path = SCRATCH / "product_profile.json"
        profile_bytes = (json.dumps(product_profile_override(), indent=2) + "\n").encode()
        profile_path.write_bytes(profile_bytes)
        (EVIDENCE / "product_profile.fixture.json").write_bytes(profile_bytes)

        # 3. Frontend dependency reuse. node_modules is gitignored and the
        # repo explicitly supports symlinking it from a sibling checkout.
        node_modules = FRONTEND_DIR / "node_modules"
        if not node_modules.exists():
            source = os.getenv("J8_NODE_MODULES_SOURCE", "").strip()
            assert source and Path(source).is_dir(), (
                "frontend-nextjs/node_modules is absent; set "
                "J8_NODE_MODULES_SOURCE to an existing installation")
            node_modules.symlink_to(Path(source))
            self.node_modules_created = True
        dist = FRONTEND_DIR / NEXT_DIST_REL
        if not dist.exists():
            dist.mkdir()
            self.dist_created = True
        # `next dev` rewrites this tracked generated file to point at the
        # active distDir.  Keep the source tree exact across the acceptance.
        next_env = FRONTEND_DIR / "next-env.d.ts"
        if next_env.exists():
            self.next_env_original = next_env.read_bytes()

        # 4. Stack processes.
        self.start_backend(tag="first")
        self.seed_scratch_world()
        self.token = login()
        self.start_frontend()

        _write_json(EVIDENCE / f"{_prefix()}-stack-ready.json", {
            "backend_pid": self.backend.pid,
            "frontend_pid": self.frontend.pid,
            "token_issued_at": _now(),
            "node_modules_symlinked": self.node_modules_created,
            "next_dist_created": self.dist_created,
        })
        return self

    def launcher_path(self) -> Path:
        launcher = SCRATCH / "j8_launcher.py"
        launcher.write_text(
            "import os, sys\n"
            f"sys.path.insert(0, {str(BACKEND_DIR)!r})\n"
            "if os.environ.get('J8_STUB_SYSTEM_PIPELINES') == '1':\n"
            "    from ai.workflow_scheduler import WorkflowScheduler\n"
            "    # The same seam every existing scheduler test already uses.\n"
            "    WorkflowScheduler.reschedule_system_pipelines = lambda self: None\n"
            "import uvicorn\n"
            "from main_api_app import app\n"
            "uvicorn.run(app, host='127.0.0.1',\n"
            "            port=int(os.environ['J8_BACKEND_PORT']), log_level='info')\n"
        )
        return launcher

    def server_env(self) -> dict:
        env = os.environ.copy()
        # The *test* process runs with TESTING=1.  The backend child runs
        # TESTING=0 because core/database.py maps TESTING=1 to an in-repo
        # filename and ignores an explicit DATABASE_URL (documented coupling);
        # TESTING=0 keeps the explicit absolute scratch URL authoritative.
        # No pytest marker is set, so normal schema bootstrap and the
        # scheduler gate behave as they do for a real dev boot.
        env.pop("PYTEST_CURRENT_TEST", None)
        env.pop("PYTEST_VERSION", None)
        env.update({
            "TESTING": "0",
            "ENVIRONMENT": "development",
            "DATABASE_URL": f"sqlite:///{SCRATCH / 'app.db'}",
            "SCHEDULER_JOB_STORE_TYPE": "sqlalchemy",
            "SCHEDULER_JOB_STORE_URL": f"sqlite:///{SCRATCH / 'jobs.db'}",
            "ENABLE_SCHEDULER": "true",
            "ENABLE_INGESTION_SYNC": "false",
            "SECRET_KEY": SERVER_SECRET,
            "ADMIN_PASSWORD": ADMIN_PASSWORD,
            "BYPASS_RATE_LIMIT": "1",
            "ALLOWED_ORIGINS": FRONTEND_URL,
            "ATOM_PRODUCT_PROFILE_PATH": str(SCRATCH / "product_profile.json"),
            "ATOM_DATA_DIR": str(SCRATCH / "data"),
            "LANCEDB_URI": str(SCRATCH / "lancedb"),
            "BYOK_CONFIG_FILE": str(SCRATCH / "byok_config.json"),
            "BYOK_KEYS_FILE": str(SCRATCH / "byok_keys.json"),
            "BYOK_ENC_KEY_FILE": str(SCRATCH / "byok_enc_key"),
            "J8_BACKEND_PORT": str(BACKEND_PORT),
            "J8_STUB_SYSTEM_PIPELINES": "1" if STUB_SYSTEM_PIPELINES else "0",
            # No external effects: a dead loopback proxy for everything except
            # loopback itself.  Nothing in this journey needs egress.
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "127.0.0.1,localhost",
        })
        return env

    def start_backend(self, tag: str):
        launcher = self.launcher_path()
        log_path = EVIDENCE / f"backend-{_prefix()}-{tag}.log"
        log = open(log_path, "wb")
        self.backend = subprocess.Popen(
            [sys.executable, str(launcher)],
            cwd=str(BACKEND_DIR), env=self.server_env(),
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        log.close()
        started = time.monotonic()
        if not wait_http_ok(BACKEND_URL + "/alive", timeout=BACKEND_STARTUP_TIMEOUT):
            tail = log_path.read_text(errors="replace")[-4000:]
            raise AssertionError(
                f"backend ({tag}) did not become healthy on {BACKEND_URL} "
                f"within {BACKEND_STARTUP_TIMEOUT:g}s "
                f"(J8_BACKEND_STARTUP_TIMEOUT); persisted jobs are not "
                f"readiness — the app may still have been booting\n{tail}")
        healthy_at = time.monotonic()
        _write_json(EVIDENCE / f"backend-{_prefix()}-{tag}-timing.json", {
            "pid": self.backend.pid,
            "started_at": _now(),
            "startup_seconds": round(healthy_at - started, 3),
            "log": str(log_path),
        })

    def seed_scratch_world(self):
        """Assign the scratch admin a coherent scope and add one STUDENT agent.

        Both writes are on the disposable acceptance database only.  The agent
        is what makes the real governance layer pause the state-changing
        step; the browser then decides it through /approvals.
        """
        con = sqlite3.connect(SCRATCH / "app.db", timeout=15)
        try:
            con.execute(
                "update users set workspace_id='default', tenant_id='default', "
                "status='active' where email=?", (ADMIN_EMAIL,))
            con.execute(
                "insert or replace into agent_registry "
                "(id, name, category, role, type, capabilities, module_path, "
                " class_name, status, tenant_id, workspace_id) "
                "values (?,?,?,?,?,?,?,?,?,?,?)",
                (AGENT_ID, "J8 Browser Agent", "test", "worker", "stateless",
                 '["*"]', "tests.workflow", "ScopedAgent", "student",
                 "default", "default"))
            con.commit()
            user = con.execute(
                "select id, workspace_id, tenant_id, role, status from users "
                "where email=?", (ADMIN_EMAIL,)).fetchone()
            agent = con.execute(
                "select id, status, workspace_id, tenant_id from agent_registry "
                "where id=?", (AGENT_ID,)).fetchone()
        finally:
            con.close()
        assert user and user[1:] == ("default", "default", "workspace_admin", "active"), user
        assert agent and agent[1] == "student", agent
        _write_json(EVIDENCE / f"{_prefix()}-seeded-world.json", {
            "admin": {"id": user[0], "workspace_id": user[1],
                      "tenant_id": user[2], "role": user[3], "status": user[4]},
            "agent": {"id": agent[0], "status": agent[1],
                      "workspace_id": agent[2], "tenant_id": agent[3]},
        })

    def start_frontend(self):
        next_bin = FRONTEND_DIR / "node_modules" / ".bin" / "next"
        assert next_bin.exists(), f"next binary missing at {next_bin}"
        log_path = EVIDENCE / f"frontend-{_prefix()}.log"
        log = open(log_path, "wb")
        env = os.environ.copy()
        env.update({
            "NEXT_PUBLIC_API_URL": BACKEND_URL,
            "NEXT_PUBLIC_USE_BACKEND_API": "true",
            "BACKEND_URL": BACKEND_URL,
            "PYTHON_BACKEND_URL": BACKEND_URL,
            "PYTHON_API_SERVICE_BASE_URL": BACKEND_URL,
            "NEXTAUTH_URL": FRONTEND_URL,
            "NEXTAUTH_SECRET": NEXTAUTH_SECRET,
            "NEXT_TELEMETRY_DISABLED": "1",
            "NEXT_DIST_DIR": NEXT_DIST_REL,
            # Turbopack refuses a node_modules symlink that leaves the project
            # root, so this isolated dev server explicitly uses webpack.
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "127.0.0.1,localhost",
        })
        self.frontend = subprocess.Popen(
            [str(next_bin), "dev", "--webpack", "-p", str(FRONTEND_PORT),
             "-H", "127.0.0.1"],
            cwd=str(FRONTEND_DIR), env=env,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        log.close()
        started = time.monotonic()
        if not wait_http_ok(FRONTEND_URL + "/login", timeout=240, interval=1.0):
            tail = log_path.read_text(errors="replace")[-5000:]
            raise AssertionError(
                f"frontend did not become healthy on {FRONTEND_URL}\n{tail}")
        _write_json(EVIDENCE / f"frontend-{_prefix()}-timing.json", {
            "pid": self.frontend.pid,
            "started_at": _now(),
            "startup_seconds": round(time.monotonic() - started, 3),
            "log": str(log_path),
        })

    # -- actions -------------------------------------------------------
    def restart_backend(self) -> dict:
        assert self.backend is not None
        self.restart_count += 1
        tag = f"restart{self.restart_count}"
        stopped_at = _now()
        stop_process(self.backend, "backend")
        self.start_backend(tag=tag)
        # ADMIN_PASSWORD is set on every boot, so the bootstrap resets the
        # credential hash and invalidates the prior bearer by design.
        self.token = login()
        timing = {
            "stopped_at": stopped_at,
            "restarted_at": _now(),
            "pid": self.backend.pid,
            "new_token_issued_at": _now(),
        }
        _write_json(EVIDENCE / f"backend-{_prefix()}-{tag}.json", timing)
        return timing

    # -- teardown ------------------------------------------------------
    def close(self):
        stop_process(self.frontend, "frontend")
        stop_process(self.backend, "backend")
        # Preserve the durable artifacts after the writers are stopped.
        for name in ("app.db", "jobs.db"):
            source = SCRATCH / name
            if source.exists():
                # SQLite WAL: a plain file copy can omit committed rows that
                # still live in <db>-wal.  The backup API produces one
                # self-contained evidence artifact after writers stopped.
                _snapshot_sqlite(source, EVIDENCE / f"{_prefix()}-{name}")
        # Exact source restore, verified by hash.
        restored = False
        if self.workflows_original is not None:
            WORKFLOWS_FILE.write_bytes(self.workflows_original)
            restored = WORKFLOWS_FILE.read_bytes() == self.workflows_original
            _write_json(EVIDENCE / f"{_prefix()}-workflows-hashes.json", {
                "original_sha256": _sha256(self.workflows_original),
                "fixture_sha256": _sha256(self.workflows_fixture or b""),
                "tracked_file": "backend/workflows.json",
                "restored_after_run": restored,
                "restored_sha256": _sha256(WORKFLOWS_FILE.read_bytes()),
            })
        if self.node_modules_created:
            node_modules = FRONTEND_DIR / "node_modules"
            if node_modules.is_symlink():
                node_modules.unlink()
        if self.dist_created:
            shutil.rmtree(FRONTEND_DIR / NEXT_DIST_REL, ignore_errors=True)
        if self.next_env_original is not None:
            (FRONTEND_DIR / "next-env.d.ts").write_bytes(self.next_env_original)
        self.env_manifest["finished_at"] = _now()
        self.env_manifest["workflows_json_restored"] = restored
        _write_json(EVIDENCE / f"{_prefix()}-manifest.json", self.env_manifest)


def _snapshot_sqlite(source: Path, destination: Path) -> None:
    source_con = sqlite3.connect(source, timeout=15)
    destination_con = sqlite3.connect(destination)
    try:
        source_con.backup(destination_con)
    finally:
        destination_con.close()
        source_con.close()


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")


# ---------------------------------------------------------------------------
# Pytest surface.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def prewarm_frontend_routes():
    """The generic e2e prewarm targets port 3001; this stack is isolated."""
    yield


@pytest.fixture(scope="session")
def base_url():
    return FRONTEND_URL


@pytest.fixture(scope="session")
def stack():
    instance = Stack()
    try:
        instance.prepare()
        yield instance
    finally:
        instance.close()


@pytest.fixture(scope="session")
def full_log():
    path = EVIDENCE / f"{_prefix()}-journey.json"
    record = {"run_mode": RUN_MODE, "phases": [], "console": [],
              "page_errors": [], "requests": []}

    def append(phase, payload):
        record["phases"].append({"phase": phase, "at": _now(), **payload})
        _write_json(path, record)

    record["append"] = append
    _write_json(path, record)
    yield record


def _new_context(browser, token: str):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.add_cookies([{
        "name": "auth_token", "value": token, "url": FRONTEND_URL}])
    # The schedule page reads the bearer from localStorage directly; the
    # cookie is what admits the page through middleware.
    context.add_init_script(
        "localStorage.setItem('auth_token', %s);"
        "localStorage.setItem('token', %s);"
        # The onboarding wizard is a global modal for a not-yet-onboarded
        # scratch admin; dismiss it with the app's own session key so it
        # cannot intercept the scheduler/approval controls under test.
        "sessionStorage.setItem('atom.onboarding.dismissed', '1');"
        % (json.dumps(token), json.dumps(token)))
    return context


def _screenshot(page, name: str):
    path = EVIDENCE / f"{_prefix()}-{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def _wait_until(predicate, timeout: float, interval: float = 0.5,
                description: str = "condition"):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for {description}; last={last!r}")


def test_browser_scheduler_restart_approval_journey(stack, browser, full_log):
    """The work order, end to end, at the browser + API/DB boundaries."""
    append = full_log["append"]
    token = stack.token

    # ------------------------------------------------------------------
    # Phase A — register the schedule through the mounted page.
    # ------------------------------------------------------------------
    context = _new_context(browser, token)
    page = context.new_page()
    page.set_default_timeout(120_000)
    page.on("console", lambda msg: full_log["console"].append(
        {"type": msg.type, "text": msg.text}))
    page.on("pageerror", lambda exc: full_log["page_errors"].append(str(exc)))

    page.goto(FRONTEND_URL + "/workflows/schedule", wait_until="domcontentloaded")
    page.get_by_role("heading", name="Schedule a workflow").wait_for()
    assert page.get_by_text("is not part of this release").count() == 0, (
        "Automations capability is still release-deferred; the documented "
        "ATOM_PRODUCT_PROFILE_PATH override did not take effect")

    page.locator("#workflow-id").fill(WORKFLOW_ID)
    # Exercise the supported selector itself (interval), not just the default.
    page.locator("#trigger-type").click()
    page.get_by_role("option", name="Every N minutes (interval)").click()
    page.locator("#interval-min").fill(str(INTERVAL_MINUTES))

    with page.expect_response(
            lambda r: r.request.method == "POST"
            and f"/workflows/{WORKFLOW_ID}/schedule" in r.url,
            timeout=60_000) as response_info:
        page.get_by_role("button", name="Schedule workflow").click()
    schedule_response = response_info.value
    assert schedule_response.status == 200, schedule_response.text()
    schedule_body = schedule_response.json()
    job_id = schedule_body["job_id"]
    scheduled_at = time.time()

    page.get_by_text("Workflow scheduled", exact=True).wait_for()
    job_item = page.locator("li", has_text=job_id).first
    job_item.wait_for()
    assert WORKFLOW_ID in job_item.inner_text()
    page_shot = _screenshot(page, "1-scheduled")

    rows_before = job_rows()
    scheduler_blocked = not any(row["id"] == job_id for row in rows_before)
    if scheduler_blocked:
        # The mounted-path blocker: the browser got 200 + job_id, but the
        # scheduler is not running, so this is only an in-memory pending job.
        due_epoch = scheduled_at + INTERVAL_MINUTES * 60
    else:
        due_epoch = next(
            float(row["next_run_epoch"])
            for row in rows_before if row["id"] == job_id)
        assert due_epoch > scheduled_at, (due_epoch, scheduled_at)
    due_at = datetime.fromtimestamp(due_epoch, timezone.utc)

    _status, jobs_api_before = http_json(
        "/api/v1/workflows/scheduler/jobs", token=token)
    append("A_scheduled_via_browser", {
        "browser_response": schedule_body,
        "browser_list_shows_job": job_id in page.locator("ul.divide-y").inner_text(),
        "jobstore_rows": rows_before,
        "scheduler_api_jobs": jobs_api_before,
        "scheduled_at_epoch": scheduled_at,
        "due_epoch": due_epoch,
        "due_iso": due_at.isoformat(),
        "scheduler_blocked_in_memory_only": scheduler_blocked,
        "screenshot": page_shot,
    })

    # ------------------------------------------------------------------
    # Phase B — restart the backend before the due time.
    # ------------------------------------------------------------------
    restart = stack.restart_backend()
    healthy_epoch = time.time()
    assert healthy_epoch < due_epoch, (
        f"restart was not before the due time: healthy={healthy_epoch} "
        f"due={due_epoch}")
    context.close()

    # ------------------------------------------------------------------
    # Phase C — the same persisted job must still be listed after restart.
    # ------------------------------------------------------------------
    context = _new_context(browser, stack.token)
    page = context.new_page()
    page.set_default_timeout(120_000)
    page.on("console", lambda msg: full_log["console"].append(
        {"type": msg.type, "text": msg.text}))
    page.on("pageerror", lambda exc: full_log["page_errors"].append(str(exc)))
    page.goto(FRONTEND_URL + "/workflows/schedule", wait_until="domcontentloaded")
    page.get_by_role("heading", name="Schedule a workflow").wait_for()

    rows_after = job_rows()
    _status, jobs_api_after = http_json(
        "/api/v1/workflows/scheduler/jobs", token=stack.token)
    persisted = [row for row in rows_after if row["id"] == job_id]
    job_visible_after_restart = any(
        job.get("id") == job_id for job in jobs_api_after)
    # Preserve the system-job side of persistence: a normal-mode restart must
    # keep every System Pipeline job that existed before it, in both the
    # jobstore and the API (empty in fixture-stub mode, where they are never
    # registered).
    system_ids_before_restart = system_job_ids_from_rows(rows_before)
    system_ids_after_restart = system_job_ids_from_rows(rows_after)
    api_system_ids_after_restart = system_job_ids_from_api(jobs_api_after)

    if scheduler_blocked:
        # Finish the mounted-path observation rather than stopping at the
        # first anomaly: wait past the due time and prove nothing fires.
        page.reload(wait_until="domcontentloaded")
        page.get_by_role("heading", name="Schedule a workflow").wait_for()
        blocker_shot = _screenshot(page, "2-blocker-after-restart")
        wait_seconds = max(0.0, due_epoch + 30 - time.time())
        time.sleep(wait_seconds)
        no_execution = not workflow_executions()
        append("B_blocker_after_restart", {
            "restart": restart,
            "healthy_before_due": healthy_epoch < due_epoch,
            "job_id": job_id,
            "jobstore_rows_after_restart": rows_after,
            "scheduler_api_jobs_after_restart": jobs_api_after,
            "job_persisted_after_restart": bool(persisted),
            "job_visible_after_restart": job_visible_after_restart,
            "waited_past_due_seconds": round(wait_seconds, 1),
            "execution_created_after_due": not no_execution,
            "executions": workflow_executions(),
            "screenshot": blocker_shot,
        })
        assert not persisted and not job_visible_after_restart, (
            "unmounted run unexpectedly persisted the job; rerun classification")
        assert no_execution, "unexpected execution without a persisted job"
        pytest.fail(
            "BLOCKER (unmounted mounted path): the browser received HTTP 200 "
            "and a job_id from POST /schedule, but the backend's "
            "WorkflowScheduler never started: SQLAlchemyJobStore cannot pickle "
            "the resumed system-pipeline bound methods (TypeError: cannot "
            "pickle '_thread.lock' object). The job lived only in the "
            "unscheduled APScheduler pending list, survived no restart, and "
            "produced no execution after its due time. Evidence: "
            f"{EVIDENCE} (see backend-{_prefix()}-first.log for the startup "
            "warning and 'apscheduler_jobs' row count 0).")

    assert persisted, (
        f"job {job_id} did not survive the backend restart; jobstore={rows_after} "
        f"api={jobs_api_after}.")
    assert job_visible_after_restart, jobs_api_after
    assert system_ids_before_restart <= system_ids_after_restart, (
        f"system jobs vanished across the restart: "
        f"before={sorted(system_ids_before_restart)} "
        f"after={sorted(system_ids_after_restart)}")
    assert system_ids_before_restart <= api_system_ids_after_restart, (
        f"system jobs vanished from the scheduler API across the restart: "
        f"before={sorted(system_ids_before_restart)} "
        f"api={sorted(api_system_ids_after_restart)}")

    page.reload(wait_until="domcontentloaded")
    page.get_by_role("heading", name="Schedule a workflow").wait_for()
    same_item = page.locator("li", has_text=job_id).first
    same_item.wait_for()
    shot_persisted = _screenshot(page, "2-after-restart-job-persisted")

    append("B_restart_and_persisted_job", {
        "restart": restart,
        "healthy_before_due": healthy_epoch < due_epoch,
        "jobstore_rows_after_restart": rows_after,
        "scheduler_api_jobs_after_restart": jobs_api_after,
        "browser_list_shows_same_job": job_id in page.locator("ul.divide-y").inner_text(),
        "system_job_ids_before_restart": sorted(system_ids_before_restart),
        "system_job_ids_after_restart": sorted(system_ids_after_restart),
        "system_jobs_persisted_after_restart": (
            system_ids_before_restart <= system_ids_after_restart),
        "screenshot": shot_persisted,
    })

    # ------------------------------------------------------------------
    # Phase D — the persisted job fires by itself; nobody calls /execute.
    # ------------------------------------------------------------------
    executions = _wait_until(
        lambda: workflow_executions() or None,
        timeout=max(90, INTERVAL_MINUTES * 60 + 120),
        description="a scheduled execution row")
    execution = executions[0]
    execution_id = execution["execution_id"]
    created_epoch = time.time()  # bounded upper bound for the observation
    created_dt = datetime.fromisoformat(
        str(execution["created_at"])).replace(tzinfo=timezone.utc)
    # The row is SQLite CURRENT_TIMESTAMP (UTC).  The fire must be at or after
    # the persisted due time, not merely observed later by the test.
    assert created_dt >= due_at - timedelta(seconds=1), (
        f"execution row predates its due time: created={created_dt} due={due_at}")
    assert time.time() >= due_epoch, "execution appeared before the due time"

    _wait_until(
        lambda: any(row["status"] == "PAUSED"
                    for row in workflow_executions()),
        timeout=60, description="the execution to pause for governance")
    before_effect = effect_count(execution_id)
    pending_before = hitl_rows(execution_id)
    assert before_effect == 0, (
        f"the local effect ran before approval: {before_effect} rows")
    assert len(pending_before) == 1, pending_before
    assert pending_before[0]["status"] == "pending", pending_before

    second_log = EVIDENCE / f"backend-{_prefix()}-restart{stack.restart_count}.log"
    manual_execute_calls = subprocess.run(
        ["grep", "-c", "-E", r"POST /api/v1/workflows/workflows/[^ ]+/execute",
         str(second_log)],
        capture_output=True, text=True).stdout.strip() or "0"
    assert manual_execute_calls == "0", (
        f"an execution endpoint was invoked manually ({manual_execute_calls})")
    assert "Executing scheduled workflow: " + WORKFLOW_ID in second_log.read_text(
        errors="replace")

    append("C_fired_without_manual_invocation", {
        "execution": execution,
        "effect_rows_before_approval": before_effect,
        "pending_hitl_before_approval": pending_before,
        "manual_execute_calls_in_restarted_backend": int(manual_execute_calls),
        "backend_log": str(second_log),
        "execution_created_utc": created_dt.isoformat(),
        "observed_upper_bound_epoch": created_epoch,
    })

    # ------------------------------------------------------------------
    # Phase E — remove the recurring schedule before approval so a second
    # interval fire cannot race the decision window.
    # ------------------------------------------------------------------
    item = page.locator("li", has_text=job_id).first
    item.wait_for()
    with page.expect_response(
            lambda r: r.request.method == "DELETE" and job_id in r.url,
            timeout=60_000) as delete_info:
        item.get_by_role("button", name="Remove").click()
    delete_response = delete_info.value
    assert delete_response.status == 200, delete_response.text()

    # The exact user schedule must disappear at all three boundaries.  Do not
    # use the page-wide empty state as the removal signal: a normal-mode boot
    # persists the System Pipeline jobs, so the list is legitimately non-empty
    # after this user's job is gone.
    system_ids_before_delete = system_job_ids_from_rows(rows_after)

    def _user_job_absent_everywhere():
        rows = job_rows()
        _status, jobs = http_json(
            "/api/v1/workflows/scheduler/jobs", token=stack.token)
        return (
            not any(row["id"] == job_id for row in rows)
            and not any(job.get("id") == job_id for job in jobs)
            and page.locator("li", has_text=job_id).count() == 0
        )

    _wait_until(
        _user_job_absent_everywhere, timeout=30,
        description="the removed schedule to leave the UI, API and jobstore")

    rows_after_delete = job_rows()
    _status, jobs_api_after_delete = http_json(
        "/api/v1/workflows/scheduler/jobs", token=stack.token)
    system_ids_after_delete = system_job_ids_from_rows(rows_after_delete)
    api_system_ids_after_delete = system_job_ids_from_api(jobs_api_after_delete)

    assert not any(row["id"] == job_id for row in rows_after_delete), (
        f"removed job {job_id} is still in the jobstore: {rows_after_delete}")
    assert not any(job.get("id") == job_id for job in jobs_api_after_delete), (
        f"removed job {job_id} is still listed by the scheduler API: "
        f"{jobs_api_after_delete}")
    assert page.locator("li", has_text=job_id).count() == 0, (
        f"removed job {job_id} is still shown in the browser list")
    assert system_ids_before_delete <= system_ids_after_delete, (
        f"removing the user schedule also dropped persisted system jobs: "
        f"before={sorted(system_ids_before_delete)} "
        f"after={sorted(system_ids_after_delete)}")
    assert system_ids_before_delete <= api_system_ids_after_delete, (
        f"removing the user schedule also dropped system jobs from the API: "
        f"before={sorted(system_ids_before_delete)} "
        f"api={sorted(api_system_ids_after_delete)}")

    if jobs_api_after_delete:
        # System jobs remain listed; a page-wide empty state would be false.
        assert page.get_by_text("No scheduled jobs yet.").count() == 0, (
            "the page shows the global empty state while the scheduler still "
            f"lists jobs: {jobs_api_after_delete}")
    else:
        # No jobs at all (fixture-stub mode): the empty state is still real.
        page.get_by_text("No scheduled jobs yet.").wait_for()

    shot_removed = _screenshot(page, "3-schedule-removed")

    append("D_schedule_removed_via_browser", {
        "delete_status": delete_response.status,
        "delete_url": delete_response.url,
        "jobstore_rows_after_delete": rows_after_delete,
        "scheduler_api_jobs_after_delete": jobs_api_after_delete,
        "user_job_absent_from_ui": page.locator(
            "li", has_text=job_id).count() == 0,
        "user_job_absent_from_api": not any(
            job.get("id") == job_id for job in jobs_api_after_delete),
        "user_job_absent_from_jobstore": not any(
            row["id"] == job_id for row in rows_after_delete),
        "system_job_ids_before_delete": sorted(system_ids_before_delete),
        "system_job_ids_after_delete": sorted(system_ids_after_delete),
        "system_jobs_persisted_after_delete": (
            system_ids_before_delete <= system_ids_after_delete),
        "global_empty_state_visible": (
            page.get_by_text("No scheduled jobs yet.").count() > 0),
        "screenshot": shot_removed,
    })

    # ------------------------------------------------------------------
    # Phase F — decide through the mounted /approvals UI.
    # ------------------------------------------------------------------
    _status, pending_api = http_json("/api/agents/approvals/pending", token=stack.token)
    assert len(pending_api) == 1, pending_api
    approval_id = pending_api[0]["id"]
    assert pending_api[0]["params"]["execution_id"] == execution_id

    page.goto(FRONTEND_URL + "/approvals", wait_until="domcontentloaded")
    page.get_by_role("heading", name="Approvals").wait_for()
    card = page.locator("div.rounded-xl.border", has_text=execution_id).first
    card.wait_for()
    assert "Maturity check failed" in card.inner_text()
    shot_pending = _screenshot(page, "4-approval-pending")

    # Effect still absent immediately before the click.
    assert effect_count(execution_id) == 0

    with page.expect_response(
            lambda r: r.request.method == "POST"
            and r.url.endswith("/api/agents/approvals/" + approval_id),
            timeout=60_000) as approve_info:
        card.get_by_role("button", name="Approve", exact=True).click()
    approve_response = approve_info.value
    assert approve_response.status == 200, approve_response.text()
    assert approve_response.json()["data"]["resume"]["resumed"] is True, (
        approve_response.text())
    page.get_by_text("Action approved.", exact=True).wait_for()
    page.get_by_text("Nothing waiting for approval.").wait_for()

    completed = _wait_until(
        lambda: next((row for row in workflow_executions()
                      if row["status"] == "COMPLETED"), None),
        timeout=60, description="a completed execution")
    final_effect = effect_count(execution_id)
    final_hitl = hitl_rows(execution_id)
    assert final_effect == 1, (
        f"expected exactly one persisted local effect, saw {final_effect}")
    assert len(final_hitl) == 1 and final_hitl[0]["status"] == "approved"
    assert approval_id in (completed["input_data"] or "")

    # Refresh is part of the order: the decided work must stay decided.
    page.reload(wait_until="domcontentloaded")
    page.get_by_role("heading", name="Approvals").wait_for()
    page.get_by_text("Nothing waiting for approval.").wait_for()
    shot_after = _screenshot(page, "5-approval-completed-after-refresh")

    executions_after = workflow_executions()
    assert len(executions_after) == 1, (
        f"recurring schedule produced more than one execution: {executions_after}")

    _status, execution_api = http_json(
        f"/api/v1/workflows/workflows/executions/{execution_id}", token=stack.token)
    append("E_approved_in_ui_and_completed", {
        "approval_id": approval_id,
        "approve_response": approve_response.json(),
        "final_hitl": final_hitl,
        "final_effect_rows": final_effect,
        "completed_execution": completed,
        "executions_after_window": executions_after,
        "execution_api": execution_api,
        "screenshots": [shot_pending, shot_after],
    })

    # ------------------------------------------------------------------
    # Final evidence + invariants.
    # ------------------------------------------------------------------
    assert not full_log["page_errors"], full_log["page_errors"]
    final_rows = job_rows()
    final_system_ids = system_job_ids_from_rows(final_rows)
    assert not any(row["id"] == job_id for row in final_rows), (
        "the recurring schedule was not fully removed")
    assert system_ids_before_delete <= final_system_ids, (
        f"system jobs were not preserved through the journey: "
        f"before={sorted(system_ids_before_delete)} "
        f"after={sorted(final_system_ids)}")
    append("F_invariants", {
        "single_execution": len(executions_after) == 1,
        "single_local_effect": final_effect == 1,
        "user_job_removed_from_jobstore": not any(
            row["id"] == job_id for row in final_rows),
        "system_job_ids": sorted(final_system_ids),
        "system_jobs_persisted": system_ids_before_delete <= final_system_ids,
        "page_errors": full_log["page_errors"],
        "browser_console_messages": len(full_log["console"]),
    })
    context.close()
