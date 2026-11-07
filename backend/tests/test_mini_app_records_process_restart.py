"""MINI04 — mini-app record persistence across a REAL process restart.

Requirement: install a mini-app, append records through the real
host-mediated record API, query the series, restart the serving PROCESS
(new OS pid on the same scratch DB/config), query again — records persist
with monotonic ``seq`` and per-instance isolation.

What is real here (no doubles on the surfaces under test):

* The actual production entry point ``main_api_app:app`` served by uvicorn
  in a child OS process over an inherited bound loopback socket (the
  race-safe ``--fd`` pattern from ``tests/test_orch01_served_route_http.py``
  and ``scripts/orchestration_acceptance/fresh_install_parity.py``).
* Real normal auth: ``POST /api/auth/register`` / ``POST /api/auth/login``
  / ``GET /api/auth/me`` — no fabricated JWTs, no ``get_current_user``
  overrides.
* Real public mini-app surfaces: ``POST /api/mini-apps/scaffold`` (no
  dependencies → no rootfs/VM gate), ``POST /api/mini-apps/{id}/publish``,
  ``POST /api/mini-apps/{id}/install`` (two distinct instance canvases),
  and the host-mediated record store routes
  ``POST/GET /api/mini-apps/instances/{canvas_id}/records`` backed by
  ``core/mini_app_db_service.py`` on the scratch SQLite store.

Scope limits (stated, not claimed):

* This qualifies ONLY the host-mediated durable record path (MINI04).
  Guest execution, Firecracker/microVM isolation, dev_run/run_tests and
  MINI05 are NOT exercised: the scaffold declares no dependencies and the
  journey never requests guest execution. Child-side runtime execution
  tripwires fail the journey if an unexpected path attempts it.
* This is NOT a whole-app bootstrap proof beyond what the journey
  exercises; the full router surface is mounted because the real
  entrypoint is started, but only the routes above are consumed.

Scratch isolation (the 2026-09-04 live-DB-wipe class of bugs):

* One generated SQLite file under ``tmp_path`` plus generated
  ``ATOM_DATA_DIR``/``LANCEDB_URI``/``MINIAPP_ROOTFS_DIR`` under
  ``tmp_path``. No live dev DB, no acceptance worlds, no network, no
  model/provider calls, no guests/containers.
* DB-branch hazard found in source and handled explicitly: with
  ``TESTING=1`` alone, ``core/database.get_database_url`` IGNORES
  ``DATABASE_URL`` and forces the shared ``backend/test_integration.db``
  (core/database.py:131). Only the pytest-process branch honors an
  explicit non-dev ``DATABASE_URL`` (core/database.py:117). So each child
  is frozen with ``TESTING=1`` AND ``PYTEST_VERSION`` set alongside the
  explicit scratch ``DATABASE_URL`` — which also makes the app's lifespan
  skip its own ``create_all``; the PARENT therefore initializes ONLY the
  fresh scratch schema (``Base.metadata.create_all``, no rows seeded).
  Every row in the scratch DB beyond that schema is created by the real
  application surfaces under test; test mode skips administrative bootstrap.
* The test refuses to launch if the resolved DB/data paths are not under
  ``tmp_path``.

Credentials hygiene: the generated password lives only in the parent's
memory; tokens are used in Authorization headers and excluded from auth failure
messages. Private server diagnostics are inspected before any publication.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

BOOT_DEADLINE_S = 150.0  # main_api_app mounts the full router surface; be patient


# ---------------------------------------------------------------------------
# Child process boot (real main_api_app, bound-socket, frozen env)
# ---------------------------------------------------------------------------
def _scratch_child_env(tmp_path: Path, db_path: Path, secret_key: str) -> dict:
    """Freeze the child environment onto the scratch world.

    Every path-bearing variable is pinned under ``tmp_path`` so neither the
    repo's ``backend/.env`` (loaded by main_api_app with override=False, so
    already-set process env wins) nor the parent's environment can point the
    child at the live dev DB, the shared test DB, the dev LanceDB store, or
    acceptance worlds.
    """
    env = os.environ.copy()
    # A scratch child must not inherit real provider/account secrets.
    for key in list(env):
        if any(part in key.upper() for part in
               ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")):
            env.pop(key, None)
    data_dir = tmp_path / "data"
    lancedb_dir = tmp_path / "lancedb"
    rootfs_dir = tmp_path / "mini_app_rootfs"
    for d in (data_dir, lancedb_dir, rootfs_dir):
        d.mkdir(parents=True, exist_ok=True)
    env.update({
        # DB selection: see module docstring — TESTING=1 + PYTEST_VERSION so
        # get_database_url honors the explicit NON-dev scratch DATABASE_URL
        # (TESTING=1 alone would force the shared backend/test_integration.db),
        # and so the app lifespan skips create_all (parent owns schema init).
        "TESTING": "1",
        "PYTEST_VERSION": "1",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "ENVIRONMENT": "development",
        "ATOM_DEPLOYMENT_AUDIENCE": "development",
        # Scratch data roots
        "ATOM_DATA_DIR": str(data_dir),
        "LANCEDB_URI": str(lancedb_dir),
        "LANCEDB_PATH": str(lancedb_dir),
        "LANCEDB_URI_BASE": str(lancedb_dir),
        "MINIAPP_ROOTFS_DIR": str(rootfs_dir),
        # Mini-app records kill switch explicitly ON (production default).
        "ATOM_MINIAPP_DB_ENABLED": "true",
        # Fail-closed runtime selector: never docker-dev, never a VM.
        "ATOM_MINIAAP_RUNTIME": "firecracker",
        # Synthetic secret so tokens are stable across BOTH children without
        # touching backend/data/.dev_secret_key.
        "SECRET_KEY": secret_key,
        "MINI04_EXPECTED_DB_FILE": str(db_path.resolve()),
        "MINI04_EXECUTION_MARKER": str(tmp_path / "unsafe-execution-attempt"),
        # Keep background workers off: this journey exercises the record API,
        # not schedulers/ingestion, and a quieter child is a more honest one.
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        # No telemetry/cache egress.
        "SENTRY_DSN": "",
        "REDIS_URL": "",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(BACKEND_DIR), str(REPO_ROOT)) if p
    )
    return env


def _assert_scratch(env: dict, tmp_path: Path) -> None:
    """Refuse unsafe/non-scratch targets before any child is spawned."""
    db_url = env["DATABASE_URL"]
    assert db_url.startswith("sqlite:///"), f"non-sqlite scratch URL: {db_url!r}"
    db_file = Path(db_url.partition("sqlite:///")[2])
    resolved = db_file.resolve()
    assert tmp_path.resolve() in resolved.parents, (
        f"scratch refusal: DATABASE_URL {resolved} is not under tmp_path"
    )
    for var in ("ATOM_DATA_DIR", "LANCEDB_URI", "LANCEDB_PATH",
                "LANCEDB_URI_BASE", "MINIAPP_ROOTFS_DIR"):
        p = Path(env[var]).resolve()
        assert tmp_path.resolve() in p.parents or p == tmp_path.resolve(), (
            f"scratch refusal: {var}={p} is not under tmp_path"
        )


_CHILD_BOOTSTRAP = r"""
import hashlib
import json
import os
import sys
from pathlib import Path
from core.database import engine

expected_db = Path(os.environ["MINI04_EXPECTED_DB_FILE"]).resolve()
if not engine.url.drivername.startswith("sqlite") or Path(engine.url.database).resolve() != expected_db:
    raise RuntimeError("mini04 child refused a database outside the frozen scratch file")

from core.sandbox_runtime.firecracker_runner import FirecrackerRuntime
from core.sandbox_runtime.miniapp_dev_runner import MiniAppDevRuntime

async def forbidden_execution(*args, **kwargs):
    Path(os.environ["MINI04_EXECUTION_MARKER"]).write_text("unexpected execution attempt")
    raise RuntimeError("guest/container execution forbidden in record-only control")

for runtime in (FirecrackerRuntime, MiniAppDevRuntime):
    runtime.execute_python = forbidden_execution
    runtime.execute_command = forbidden_execution

import main_api_app
import core.mini_app_service as service
import core.mini_app_db_service as records
identity = {"pid": os.getpid(), "database_file": str(expected_db),
            "source_files": {str(Path(module.__file__).resolve()):
                hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                for module in (main_api_app, service, records)}}
Path(os.environ["MINI04_IDENTITY_FILE"]).write_text(json.dumps(identity))
import uvicorn
uvicorn.run(main_api_app.app, fd=int(sys.argv[1]), log_level="warning")
"""


def _boot_child(tmp_path: Path, env: dict, name: str):
    """Start the REAL main_api_app in a child OS process on a bound socket.

    Returns (handle dict). The inherited bound listener removes the port-race;
    the child's pid is recorded so the restart boundary is a NEW OS process,
    never a thread or an in-process reload.
    """
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    log_path = tmp_path / f"{name}.log"
    log = log_path.open("w")
    log.write(f"# launch: {name}\n")
    log.write(f"# pid-parent: {os.getpid()}\n")
    log.write(f"# app: main_api_app:app (real production entry point)\n")
    log.write(f"# executable: {sys.executable}\n")
    log.write(f"# cwd: {BACKEND_DIR}\n")
    log.write(f"# scratch DATABASE_URL: {env['DATABASE_URL']}\n")
    log.flush()
    try:
        identity_file = tmp_path / f"{name}-identity.json"
        child_env = dict(env, MINI04_IDENTITY_FILE=str(identity_file))
        process = subprocess.Popen(
            [sys.executable, "-c", _CHILD_BOOTSTRAP, str(listener.fileno())],
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
                f"{name} (real main_api_app child) exited rc={process.returncode} "
                f"before becoming ready; log tail:\n{log_path.read_text()[-6000:]}"
            )
        try:
            with urllib.request.urlopen(base_url + "/api/health", timeout=2) as resp:
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
                f"{BOOT_DEADLINE_S:.0f}s; log tail:\n{log_path.read_text()[-6000:]}"
            )
        time.sleep(0.25)
    identity = json.loads(identity_file.read_text())
    assert process.poll() is None
    assert identity["pid"] == process.pid
    assert Path(identity["database_file"]).resolve() == Path(env["MINI04_EXPECTED_DB_FILE"]).resolve()
    return {"process": process, "base_url": base_url, "log": log,
            "log_path": log_path, "pid": process.pid, "identity": identity}


def _stop_child(child: dict) -> int:
    """Stop the child and WAIT for the real OS exit. Returns the exit rc."""
    process = child["process"]
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
    child["log"].close()
    assert process.poll() is not None, "child did not actually exit"
    return process.returncode


# ---------------------------------------------------------------------------
# HTTP helpers (real socket; no TestClient anywhere in this module)
# ---------------------------------------------------------------------------
def _request(method: str, url: str, token=None, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"raw": body}


def _register(base_url: str, email: str, password: str) -> str:
    status, body = _request(
        "POST", f"{base_url}/api/auth/register",
        payload={"email": email, "password": password,
                 "first_name": "Mini", "last_name": "Restart"},
    )
    assert status in (200, 201), f"register failed with HTTP {status}"
    # Registration creates the account; authenticate via the normal login.
    return _login(base_url, email, password)


def _login(base_url: str, email: str, password: str) -> str:
    status, body = _request(
        "POST", f"{base_url}/api/auth/login",
        payload={"username": email, "password": password},
    )
    assert status == 200, f"login failed with HTTP {status}"
    token = body.get("access_token")
    assert token, "login returned no access_token"
    return token


def _append_record(base_url, token, canvas_id, series, data):
    status, body = _request(
        "POST", f"{base_url}/api/mini-apps/instances/{canvas_id}/records",
        token, {"series": series, "data": data},
    )
    assert status == 200, f"append -> {status}: {body}"
    assert body.get("success") is True, body
    return body["record"]


def _query_records(base_url, token, canvas_id, series, order="asc"):
    status, body = _request(
        "GET",
        f"{base_url}/api/mini-apps/instances/{canvas_id}/records"
        f"?series={series}&order={order}",
        token,
    )
    assert status == 200, f"query -> {status}: {body}"
    assert body.get("success") is True, body
    return body


# ---------------------------------------------------------------------------
# The journey
# ---------------------------------------------------------------------------
def test_mini_app_records_persist_across_real_process_restart(tmp_path):
    secret_key = secrets.token_urlsafe(48)
    db_path = tmp_path / "scratch_mini04.db"

    env = _scratch_child_env(tmp_path, db_path, secret_key)
    _assert_scratch(env, tmp_path)

    # Parent initializes ONLY the fresh scratch schema (no rows seeded).
    # main_api_app's lifespan skips create_all in test mode; this mirrors the
    # late-imported model modules it registers before its own create_all.
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        from core.database import Base
        import core.models  # noqa: F401
        from core.auto_dev import models as _autodev_models  # noqa: F401

        Base.metadata.create_all(bind=engine)

        child1 = _boot_child(tmp_path, env, "child1_pre_restart")
        try:
            base1 = child1["base_url"]
            assert child1["pid"] != os.getpid(), "child must be a separate process"

            # --- Real normal auth -------------------------------------------
            email = f"mini04_{uuid.uuid4().hex[:10]}@test.example.com"
            password = secrets.token_urlsafe(16) + "!Aa1"  # kept private
            token = _register(base1, email, password)
            me_status, me = _request("GET", f"{base1}/api/auth/me", token)
            assert me_status == 200, me
            owner_user_id = me["id"]
            assert me["email"] == email

            # Second legitimate user (for the authorization negative).
            email_b = f"mini04b_{uuid.uuid4().hex[:10]}@test.example.com"
            password_b = secrets.token_urlsafe(16) + "!Aa1"  # kept private
            token_b = _register(base1, email_b, password_b)

            # --- Author, publish, install through real public APIs ---------
            series = "events"
            scaffold_status, scaffold = _request(
                "POST", f"{base1}/api/mini-apps/scaffold", token,
                {"name": f"Restart Journal {uuid.uuid4().hex[:6]}",
                 "spec": {},
                 "declared_scopes": ["canvas_render"],
                 "dependencies": []},  # no deps → no rootfs/VM gate anywhere
            )
            assert scaffold_status == 200, scaffold
            assert scaffold.get("success") is True, scaffold
            app_id = scaffold["app"]["id"]
            assert app_id

            pub_status, pub = _request(
                "POST", f"{base1}/api/mini-apps/{app_id}/publish", token)
            assert pub_status == 200, pub

            ins_status, ins = _request(
                "POST", f"{base1}/api/mini-apps/{app_id}/install", token)
            assert ins_status == 200, ins
            instance_a = ins["canvas_id"]
            assert instance_a

            # Second distinct instance of the same app (normal API, same user).
            ins2_status, ins2 = _request(
                "POST", f"{base1}/api/mini-apps/{app_id}/install", token)
            assert ins2_status == 200, ins2
            instance_b = ins2["canvas_id"]
            assert instance_b and instance_b != instance_a

            # --- Append 2 records; capture EXACT ids/seq --------------------
            rec1 = _append_record(base1, token, instance_a, series,
                                  {"kind": "note", "body": "before-restart-1"})
            rec2 = _append_record(base1, token, instance_a, series,
                                  {"kind": "note", "body": "before-restart-2"})
            assert rec1["series"] == series and rec2["series"] == series
            assert rec1["seq"] == 1 and rec2["seq"] == 2, (rec1, rec2)
            assert rec1["id"] != rec2["id"]

            before = _query_records(base1, token, instance_a, series)
            assert before["count"] == 2
            assert [r["seq"] for r in before["records"]] == [1, 2]

            # --- Per-instance isolation BEFORE restart ----------------------
            empty_b = _query_records(base1, token, instance_b, series)
            assert empty_b["count"] == 0, empty_b

            # --- Authorization negative (second real user) ------------------
            neg_status, neg = _request(
                "GET",
                f"{base1}/api/mini-apps/instances/{instance_a}/records"
                f"?series={series}",
                token_b,
            )
            assert neg_status == 403, (neg_status, neg)
            neg_w_status, neg_w = _request(
                "POST",
                f"{base1}/api/mini-apps/instances/{instance_a}/records",
                token_b, {"series": series, "data": {"kind": "intrusion"}},
            )
            assert neg_w_status == 403, (neg_w_status, neg_w)
            # The refused write must not have landed.
            still2 = _query_records(base1, token, instance_a, series)
            assert still2["count"] == 2

            # --- REAL process restart ---------------------------------------
            rc1 = _stop_child(child1)
            assert rc1 is not None
            pid1 = child1["pid"]

            child2 = _boot_child(tmp_path, env, "child2_post_restart")
            try:
                base2 = child2["base_url"]
                pid2 = child2["pid"]
                # The restart boundary is a genuinely NEW OS process on the
                # SAME frozen env/scratch DB.
                assert pid2 != pid1, "restart must be a new OS process"
                assert child2["process"].poll() is None
                assert child2["identity"]["source_files"] == child1["identity"]["source_files"]
                assert not Path(env["MINI04_EXECUTION_MARKER"]).exists()

                # Re-login the SAME account through the real endpoint — the
                # user must survive the restart in the durable store.
                token2 = _login(base2, email, password)
                me2_status, me2 = _request("GET", f"{base2}/api/auth/me", token2)
                assert me2_status == 200, me2
                assert me2["id"] == owner_user_id
                assert me2["email"] == email

                # Installed instance still resolvable: exact records survive.
                after = _query_records(base2, token2, instance_a, series)
                assert after["count"] == 2, after
                assert [r["id"] for r in after["records"]] == [rec1["id"], rec2["id"]]
                assert [r["seq"] for r in after["records"]] == [1, 2]
                assert after["records"][0]["data"] == rec1["data"]
                assert after["records"][1]["data"] == rec2["data"]

                # Monotonic seq continues strictly later after the restart.
                rec3 = _append_record(base2, token2, instance_a, series,
                                      {"kind": "note", "body": "after-restart"})
                assert rec3["seq"] > max(rec1["seq"], rec2["seq"]), rec3
                assert rec3["id"] not in {rec1["id"], rec2["id"]}

                # Per-instance isolation STILL holds after the restart.
                empty_b2 = _query_records(base2, token2, instance_b, series)
                assert empty_b2["count"] == 0, empty_b2

                # And the second user's refusal persists on the new process.
                neg2_status, _ = _request(
                    "GET",
                    f"{base2}/api/mini-apps/instances/{instance_a}/records"
                    f"?series={series}",
                    token_b,
                )
                assert neg2_status == 403, neg2_status
                assert not Path(env["MINI04_EXECUTION_MARKER"]).exists()
            finally:
                _stop_child(child2)
        finally:
            if child1["process"].poll() is None:
                _stop_child(child1)
    finally:
        engine.dispose()
