# -*- coding: utf-8 -*-
"""Durable chat transcripts belong to the authenticated actor, not the
default-scope orchestrator singleton.

Observed on main (fbabef87f) through the real API: a full signup/login for
UserA in TenantA/WorkspaceA produced a correct ``ChatRequestRecord``
(TenantA/userA/session/execution/assistant id) while BOTH persisted
``ChatMessage`` rows carried ``tenant_id='default'``. The chat orchestrator
is a module-level singleton constructed as ``ChatOrchestrator()``; its
``_update_session`` wrote ``self.tenant_id or "default"`` for every user.

This suite drives the REAL served boundary (uvicorn + SQLite + the real
module-level singleton + real JWT signup/login), with only the model
transports doubled (``tests/fixtures/served_chat_scope_app.py``). No auth is
mocked and the transcript writer is never monkeypatched.

Controls (positive and negative, all read back from a fresh SQLite
connection and from a cold/new server process):

* two users in different tenants served by the SAME default-tenant singleton
  keep their own tenant on both rows — including two turns simultaneously
  awaiting the model;
* the keyed transport record, assistant-message id and execution id agree;
* the legitimate global/default user (admin bootstrap, NULL tenant) still
  writes the default tenant;
* the authority admitted at the start of the turn is the authority at the
  write: a tenant move, a workspace move, or both landing while the model is
  awaited refuse the append (the answer is still delivered and the transport
  pin gets no assistant id) instead of re-scoping the turn's content;
* an authority read outage during the write fails closed the same way, and a
  turn with an unchanged scope after the refusals still writes normally;
* a legacy placeholder-owned session is reclaimed DURABLY in the write
  transaction: the first caller owns it across a restart, and a different
  local user can neither append to nor adopt it;
* an authenticated local user targeting a durable external-platform
  (`external_agent_user`) conversation is refused, warm and after a cold
  restart, while the external bridge's own declared-scope write stays valid;
* a foreign durable session, an owner changed while the turn awaits the
  model, and a user revoked while the turn awaits the model all refuse the
  append;
* a storage outage delivers the answer but never claims a durable transcript
  row (no assistant id on the transport pin).

World isolation mirrors ``test_served_spreadsheet_stale_cache.py``: the
served subprocess runs with an absolute scratch DATABASE_URL,
ATOM_DATA_DIR, LanceDB and BYOK paths, every provider key pinned empty,
``ATOM_LOCAL_ONLY=true`` and a loopback-only socket guard. The pytest parent
stays ``TESTING=1`` so it can never touch the live dev DB.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

pytestmark = [
    pytest.mark.integration,
    pytest.mark.api,
    pytest.mark.slow,
]

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_PROVIDER_KEY_ENV_NAMES = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
    "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY",
    "TOGETHER_API_KEY", "GLM_API_KEY", "MOONSHOT_API_KEY",
    "OPENCODE_API_KEY", "TAVILY_API_KEY", "BRAVE_SEARCH_API_KEY",
    "XAI_API_KEY", "MISTRAL_API_KEY",
)


# ---------------------------------------------------------------------------
# Served-world plumbing
# ---------------------------------------------------------------------------
def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _tail(path: Path, limit: int = 8000) -> str:
    try:
        return path.read_text(errors="replace")[-limit:]
    except OSError:
        return "<no log>"


def _wait_for_health(base_url: str, process: subprocess.Popen,
                     log_path: Path, timeout_s: float = 180.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail("served app exited during boot:\n" + _tail(log_path))
        try:
            response = httpx.get(
                base_url + "/alive", timeout=2.0, trust_env=False)
            if response.status_code == 200:
                return
        except Exception:  # noqa: BLE001 — not up yet
            pass
        time.sleep(0.25)
    pytest.fail("served app did not become healthy:\n" + _tail(log_path))


class ServedWorld:
    """One scratch world; ``restart`` yields a genuinely new server process."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "served-chat-scope"
        self.root.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.control_dir = self.root / "control"
        self.trace_path = self.root / "singleton_trace.jsonl"
        self.db_path = self.root / "atom.db"
        self.secret = secrets.token_urlsafe(32)
        self.admin_password = secrets.token_urlsafe(18)
        self.base_url = ""
        self._process: subprocess.Popen | None = None
        self._log_handle = None
        self._log_path: Path | None = None
        self._boot_count = 0
        self._env = self._build_env()

    def _build_env(self) -> dict:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "TMPDIR": os.environ.get("TMPDIR", ""),
            # TESTING=0 + explicit absolute scratch DATABASE_URL: the served
            # app must honour THIS world, not the pytest process's test DB.
            "TESTING": "0",
            "ENVIRONMENT": "development",
            "PYTHON_DOTENV_DISABLED": "1",
            "DATABASE_URL": f"sqlite:///{self.db_path}",
            "ATOM_DATA_DIR": str(self.data_dir),
            "ATOM_OFFICE_DIR": str(self.data_dir / "office"),
            "LANCEDB_URI": str(self.data_dir / "atom_memory"),
            "LANCEDB_URI_BASE": str(self.data_dir / "atom_memory"),
            "BYOK_CONFIG_FILE": str(self.root / "byok_config.json"),
            "BYOK_KEYS_FILE": str(self.root / "byok_keys.json"),
            "BYOK_ENC_KEY_FILE": str(self.root / "byok_encryption_key"),
            "ATOM_LOCAL_ONLY": "true",
            "ATOM_CHAT_STREAMING": "false",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "SECRET_KEY": self.secret,
            "ADMIN_PASSWORD": self.admin_password,
            "PYTHONPATH": str(BACKEND),
            "PYTHONDONTWRITEBYTECODE": "1",
            "SERVED_CHAT_CONTROL_DIR": str(self.control_dir),
            "SERVED_CHAT_TRACE": str(self.trace_path),
        }
        for name in _PROVIDER_KEY_ENV_NAMES:
            env[name] = ""
        for name in ("OLLAMA_HOST", "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
            env[name] = ""
        return env

    def start(self) -> None:
        assert self._process is None
        self.control_dir.mkdir(parents=True, exist_ok=True)
        for stale in self.control_dir.glob("*.awaiting"):
            stale.unlink()
        for stale in self.control_dir.glob("*.release"):
            stale.unlink()
        self._boot_count += 1
        port = _free_port()
        self.base_url = f"http://127.0.0.1:{port}"
        self._log_path = self.root / f"server-{self._boot_count}.log"
        self._log_handle = self._log_path.open("w")
        self._process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "served_chat_scope_app:app",
                "--app-dir", str(FIXTURES),
                "--host", "127.0.0.1",
                "--port", str(port),
                "--log-level", "warning",
            ],
            cwd=str(BACKEND),
            env=self._env,
            stdout=self._log_handle,
            stderr=self._log_handle,
        )
        _wait_for_health(self.base_url, self._process, self._log_path)
        assert self.db_path.exists(), "the served app did not create its DB"
        assert str(self.db_path).startswith(str(self.root))

    def restart(self) -> None:
        self.stop()
        self.start()

    def stop(self) -> None:
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=25)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
            self._process = None
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    def sql(self, statement: str, params: tuple = ()) -> None:
        connection = sqlite3.connect(self.db_path, timeout=20)
        try:
            connection.execute(statement, params)
            connection.commit()
        finally:
            connection.close()

    def rows(self, statement: str, params: tuple = ()) -> list[dict]:
        connection = sqlite3.connect(self.db_path, timeout=20)
        try:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(
                statement, params).fetchall()]
        finally:
            connection.close()

    def table_exists(self, name: str) -> bool:
        return bool(self.rows(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (name,)))

    def wait_for_file(self, name: str, timeout_s: float = 120.0) -> Path:
        path = self.control_dir / name
        deadline = time.monotonic() + timeout_s
        log_path = self._log_path
        while time.monotonic() < deadline:
            if path.exists():
                return path
            if self._process is not None and self._process.poll() is not None:
                pytest.fail(
                    "served app exited while the turn was awaited:\n"
                    + _tail(log_path) if log_path else "<no log>")
            time.sleep(0.02)
        pytest.fail(f"served turn never reached gate {name!r}")

    def release(self, tag: str) -> None:
        (self.control_dir / f"{tag}.release").write_text("1", encoding="utf-8")

    def wait_for_gate(self, tag: str) -> None:
        self.wait_for_file(f"{tag}.awaiting")

    def trace(self) -> list[dict]:
        if not self.trace_path.exists():
            return []
        entries = []
        for line in self.trace_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:  # noqa: BLE001 — trace is diagnostic only
                continue
        return entries


@pytest.fixture()
def world(tmp_path):
    served = ServedWorld(tmp_path)
    served.start()
    try:
        yield served
    finally:
        served.stop()


# ---------------------------------------------------------------------------
# Public API helpers
# ---------------------------------------------------------------------------
def _register(served: ServedWorld, label: str) -> dict:
    email = f"scope_{label}_{uuid.uuid4().hex[:10]}@example.com"
    password = "TestPass123!"
    registered = httpx.post(
        served.base_url + "/api/auth/register",
        json={"email": email, "password": password,
              "first_name": label.title(), "last_name": "Actor"},
        timeout=60,
        trust_env=False,
    )
    assert registered.status_code in (200, 201), registered.text
    return {"email": email, "password": password}


def _login(served: ServedWorld, email: str, password: str) -> dict:
    logged_in = httpx.post(
        served.base_url + "/api/auth/login",
        json={"username": email, "password": password},
        timeout=60,
        trust_env=False,
    )
    assert logged_in.status_code == 200, logged_in.text
    token = logged_in.json().get("access_token")
    assert token, logged_in.text
    me = httpx.get(
        served.base_url + "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
        trust_env=False,
    )
    assert me.status_code == 200, me.text
    identity = me.json()
    return {
        "token": token,
        "id": identity["id"],
        "tenant_id": identity.get("tenant_id"),
        "workspace_id": identity.get("workspace_id"),
    }


def _actor(served: ServedWorld, label: str) -> dict:
    credentials = _register(served, label)
    actor = _login(served, credentials["email"], credentials["password"])
    actor["email"] = credentials["email"]
    actor["password"] = credentials["password"]
    return actor


def _chat(served: ServedWorld, actor: dict, message: str, *,
          session_id: str, request_id: str | None = None,
          context: dict | None = None,
          timeout: float = 240.0) -> dict:
    payload = {
        "message": message,
        "user_id": "ignored-client-supplied-id",
        "session_id": session_id,
    }
    if request_id:
        payload["request_id"] = request_id
    if context is not None:
        payload["context"] = context
    response = httpx.post(
        served.base_url + "/api/chat/message",
        headers={"Authorization": f"Bearer {actor['token']}"},
        json=payload,
        timeout=timeout,
        trust_env=False,
    )
    assert response.status_code == 200, (response.status_code, response.text)
    body = response.json()
    assert body.get("success") is True, body
    return body


def _messages(served: ServedWorld, session_id: str) -> list[dict]:
    return served.rows(
        "SELECT id, conversation_id, tenant_id, role, content, metadata_json "
        "FROM chat_messages WHERE conversation_id=? ORDER BY role DESC, "
        "created_at ASC",
        (session_id,),
    )


def _request_record(served: ServedWorld, request_id: str) -> dict:
    rows = served.rows(
        "SELECT tenant_id, user_id, session_id, request_id, state, "
        "payload_sha256, execution_id, assistant_message_id, "
        "finalized_response FROM chat_request_records "
        "WHERE request_id=?",
        (request_id,),
    )
    assert len(rows) == 1, rows
    return rows[0]


def _verify_canonical_turn_binding(
    *,
    actor: dict,
    requested_session: str,
    response: dict,
    rows: list[dict],
    record: dict,
    canonical_owner: list[dict],
    requested_before: list[dict],
    requested_after: list[dict],
) -> None:
    """Assert the server-canonical binding of a fresh-admission turn.

    Every fact comes from the SERVER: the HTTP response, a fresh SQLite
    readback of the canonical conversation, the durable session owner row and
    the keyed request record. Client-supplied "canonical" metadata is never an
    input. ``rows``/``record`` are deliberately parameters so negative controls
    can prove the verifier rejects forged identities instead of trusting them.
    """
    canonical_session = str(response.get("session_id") or "")
    assert canonical_session, response
    assert canonical_session != requested_session, (
        "a foreign requested id must never be reused as canonical", response)

    assert sorted(str(row["role"]) for row in rows) == [
        "assistant", "user"], rows
    assert {str(row["conversation_id"]) for row in rows} == {
        canonical_session}, rows
    assert {str(row["tenant_id"]) for row in rows} == {
        actor["tenant_id"]}, rows

    assistant = next(row for row in rows if row["role"] == "assistant")
    assert assistant["content"] == response["message"]
    assert canonical_owner == [{"user_id": actor["id"]}], canonical_owner

    # The original request key stays the identity it was reserved under. The
    # canonical/assistant/execution pins point at the fresh owned turn.
    assert record["session_id"] == requested_session, record
    assert record["user_id"] == actor["id"], record
    assert record["tenant_id"] == actor["tenant_id"], record
    assert record["state"] == "completed", record
    assert record["assistant_message_id"] == assistant["id"], record
    assert str(record["execution_id"]) == str(response["execution_id"]), record

    meta = json.loads(assistant["metadata_json"] or "{}")
    assert meta["assistant_message_id"] == assistant["id"], meta
    assert str(meta.get("execution_id")) == str(response["execution_id"]), meta

    assert requested_after == requested_before, (
        "the requested conversation must be byte-unchanged", requested_after)
    assert requested_before, "the requested conversation must have proof rows"


def _assert_canonical_turn_binding(
    served: ServedWorld,
    actor: dict,
    *,
    requested_session: str,
    request_id: str,
    response: dict,
    requested_before: list[dict],
) -> dict:
    canonical_session = str(response.get("session_id") or "")
    rows = _messages(served, canonical_session)
    record = _request_record(served, request_id)
    canonical_owner = served.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?",
        (canonical_session,))
    _verify_canonical_turn_binding(
        actor=actor,
        requested_session=requested_session,
        response=response,
        rows=rows,
        record=record,
        canonical_owner=canonical_owner,
        requested_before=requested_before,
        requested_after=_messages(served, requested_session),
    )
    return {"rows": rows, "record": record, "owner": canonical_owner}


def _assert_actor_rows(served: ServedWorld, actor: dict, session_id: str,
                       request_id: str, response: dict) -> dict:
    rows = _messages(served, session_id)
    roles = sorted(row["role"] for row in rows)
    assert roles == ["assistant", "user"], rows
    for row in rows:
        assert row["conversation_id"] == session_id
        assert row["tenant_id"] == actor["tenant_id"], row
    record = _request_record(served, request_id)
    assert record["tenant_id"] == actor["tenant_id"], record
    assert record["user_id"] == actor["id"], record
    assert record["session_id"] == session_id, record
    assert record["state"] == "completed", record
    assistant = next(row for row in rows if row["role"] == "assistant")
    meta = json.loads(assistant["metadata_json"] or "{}")
    assert meta["assistant_message_id"] == record["assistant_message_id"], meta
    assert meta["assistant_message_id"] == assistant["id"], meta
    assert str(meta.get("execution_id")) == str(response["execution_id"])
    return {"rows": rows, "record": record, "meta": meta}


# ---------------------------------------------------------------------------
# 1. Positive controls: two tenants on the shared default singleton
# ---------------------------------------------------------------------------
def test_shared_default_singleton_keeps_each_actors_scope(world):
    actor_a = _actor(world, "alpha")
    actor_b = _actor(world, "beta")
    assert actor_a["tenant_id"] and actor_b["tenant_id"]
    assert actor_a["tenant_id"] != "default"
    assert actor_b["tenant_id"] != "default"
    assert actor_a["tenant_id"] != actor_b["tenant_id"]

    session_a = f"scope-a-{uuid.uuid4().hex[:10]}"
    session_b = f"scope-b-{uuid.uuid4().hex[:10]}"
    req_a = f"req-a-{uuid.uuid4().hex[:10]}"
    req_b = f"req-b-{uuid.uuid4().hex[:10]}"
    response_a = _chat(world, actor_a, "first turn for alpha",
                       session_id=session_a, request_id=req_a)
    response_b = _chat(world, actor_b, "first turn for beta",
                       session_id=session_b, request_id=req_b)
    capture_a = _assert_actor_rows(
        world, actor_a, session_a, req_a, response_a)
    capture_b = _assert_actor_rows(
        world, actor_b, session_b, req_b, response_b)

    # ------------------------------------------------------------------
    # Concurrent interleave around the model await: BOTH turns are inside
    # the completion call before either writer runs.
    # ------------------------------------------------------------------
    tag_a, tag_b = "interleave-a", "interleave-b"
    session_ia = f"scope-ia-{uuid.uuid4().hex[:10]}"
    session_ib = f"scope-ib-{uuid.uuid4().hex[:10]}"
    req_ia = f"req-ia-{uuid.uuid4().hex[:10]}"
    req_ib = f"req-ib-{uuid.uuid4().hex[:10]}"
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(
            _chat, world, actor_a,
            f"[[probe:{tag_a}]] concurrent turn alpha",
            session_id=session_ia, request_id=req_ia)
        future_b = pool.submit(
            _chat, world, actor_b,
            f"[[probe:{tag_b}]] concurrent turn beta",
            session_id=session_ib, request_id=req_ib)
        world.wait_for_gate(tag_a)
        world.wait_for_gate(tag_b)
        # Both requests are parked in the model call at the same time.
        assert (world.control_dir / f"{tag_a}.awaiting").exists()
        assert (world.control_dir / f"{tag_b}.awaiting").exists()
        world.release(tag_a)
        world.release(tag_b)
        response_ia = future_a.result(timeout=240)
        response_ib = future_b.result(timeout=240)
    assert tag_a in response_ia["message"], response_ia["message"]
    assert tag_b in response_ib["message"], response_ib["message"]
    capture_ia = _assert_actor_rows(
        world, actor_a, session_ia, req_ia, response_ia)
    capture_ib = _assert_actor_rows(
        world, actor_b, session_ib, req_ib, response_ib)

    # The trace is written by the completion double from INSIDE the served
    # process: both interleaved turns were served by the same module-level
    # default-tenant singleton.
    traced = {entry.get("tag"): entry for entry in world.trace()}
    assert tag_a in traced and tag_b in traced, traced
    assert traced[tag_a]["orchestrator_tenant"] == "default", traced[tag_a]
    assert traced[tag_b]["orchestrator_tenant"] == "default", traced[tag_b]
    assert traced[tag_a]["orchestrator_id"] == traced[tag_b]["orchestrator_id"]

    # ------------------------------------------------------------------
    # Legitimate global/default user: the admin bootstrap row has NULL
    # tenant/workspace and must still write the Personal default scope.
    # ------------------------------------------------------------------
    admin = _login(world, "admin@example.com", world.admin_password)
    admin["email"] = "admin@example.com"
    admin["password"] = world.admin_password
    assert admin["tenant_id"] is None and admin["workspace_id"] is None
    session_admin = f"scope-admin-{uuid.uuid4().hex[:10]}"
    req_admin = f"req-admin-{uuid.uuid4().hex[:10]}"
    response_admin = _chat(
        world, admin, "global default turn",
        session_id=session_admin, request_id=req_admin)
    rows_admin = _messages(world, session_admin)
    assert sorted(row["role"] for row in rows_admin) == [
        "assistant", "user"], rows_admin
    assert {row["tenant_id"] for row in rows_admin} == {"default"}, rows_admin
    record_admin = _request_record(world, req_admin)
    assert record_admin["tenant_id"] == "default", record_admin
    assert record_admin["user_id"] == admin["id"]
    assert record_admin["session_id"] == session_admin
    meta_admin = json.loads(next(
        row for row in rows_admin
        if row["role"] == "assistant")["metadata_json"] or "{}")
    assert meta_admin["assistant_message_id"] == record_admin[
        "assistant_message_id"]
    assert str(meta_admin["execution_id"]) == str(
        response_admin["execution_id"])

    # ------------------------------------------------------------------
    # Fresh SQLite readback of every positive capture (independent of the
    # served process's in-memory state).
    # ------------------------------------------------------------------
    for actor, session_id, capture in (
        (actor_a, session_a, capture_a),
        (actor_b, session_b, capture_b),
        (actor_a, session_ia, capture_ia),
        (actor_b, session_ib, capture_ib),
    ):
        fresh = _messages(world, session_id)
        assert {row["tenant_id"] for row in fresh} == {actor["tenant_id"]}
        assert {row["conversation_id"] for row in fresh} == {session_id}

    # ------------------------------------------------------------------
    # Cold/new service instance: a brand-new server process must serve the
    # same durable rows (and the same tenant) from the same scratch DB.
    # ------------------------------------------------------------------
    world.restart()
    for actor, session_id, expected_text in (
        (actor_a, session_a, "first turn for alpha"),
        (actor_b, session_b, "first turn for beta"),
        (actor_a, session_ia, tag_a),
        (actor_b, session_ib, tag_b),
        (admin, session_admin, "global default turn"),
    ):
        # A NEW process must reissue the caller's credential material; the
        # durable rows are what this proof is about.
        fresh_actor = _login(world, actor["email"], actor["password"])
        history = httpx.get(
            world.base_url + f"/api/chat/history/{session_id}",
            headers={"Authorization": f"Bearer {fresh_actor['token']}"},
            timeout=60,
            trust_env=False,
        )
        assert history.status_code == 200, history.text
        payload = history.json()
        rendered = json.dumps(payload)
        assert expected_text in rendered, (session_id, rendered[:2000])
        fresh = _messages(world, session_id)
        expected_tenant = actor["tenant_id"] or "default"
        assert {row["tenant_id"] for row in fresh} == {expected_tenant}, fresh


# ---------------------------------------------------------------------------
# 2. Negative controls: foreign / changed / revoked scopes refuse the write
# ---------------------------------------------------------------------------
def test_foreign_changed_and_revoked_scopes_refuse_the_append(world):
    actor_a = _actor(world, "owner")
    actor_b = _actor(world, "intruder")

    # A durable session owned by A, created by a PREVIOUS run (not in this
    # process's in-memory projection). B's turn must not append to it.
    foreign_session = f"foreign-{uuid.uuid4().hex[:10]}"
    world.sql(
        "INSERT INTO chat_sessions (id, user_id, title, metadata_json, "
        "channel_id, thread_id, created_at, updated_at, message_count) "
        "VALUES (?, ?, ?, ?, NULL, NULL, datetime('now'), datetime('now'), 0)",
        (foreign_session, actor_a["id"], "prior conversation", "{}"),
    )
    foreign_req = f"req-foreign-{uuid.uuid4().hex[:10]}"
    foreign_response = _chat(
        world, actor_b, "write into a foreign conversation",
        session_id=foreign_session, request_id=foreign_req)
    assert foreign_response["success"] is True
    assert _messages(world, foreign_session) == []
    foreign_record = _request_record(world, foreign_req)
    # The turn ran for B; the transcript append was refused, so the pin has
    # no durable assistant row to point at.
    assert foreign_record["assistant_message_id"] is None, foreign_record
    assert foreign_record["user_id"] == actor_b["id"]
    durable_owner = world.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?",
        (foreign_session,))
    assert durable_owner == [{"user_id": actor_a["id"]}], durable_owner

    # Owner changed WHILE the turn awaits the model.
    changed_session = f"changed-{uuid.uuid4().hex[:10]}"
    changed_req = f"req-changed-{uuid.uuid4().hex[:10]}"
    tag_changed = "changed-owner"
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            _chat, world, actor_a,
            f"[[probe:{tag_changed}]] change the owner mid-turn",
            session_id=changed_session, request_id=changed_req)
        world.wait_for_gate(tag_changed)
        assert world.rows(
            "SELECT user_id FROM chat_sessions WHERE id=?",
            (changed_session,)) == [{"user_id": actor_a["id"]}]
        world.sql(
            "UPDATE chat_sessions SET user_id=? WHERE id=?",
            (actor_b["id"], changed_session))
        world.release(tag_changed)
        changed_response = future.result(timeout=240)
    assert changed_response["success"] is True
    assert _messages(world, changed_session) == []
    assert _request_record(
        world, changed_req)["assistant_message_id"] is None

    # Actor revoked WHILE the turn awaits the model (admission already
    # succeeded; the write-time authority read must refuse).
    revoked_session = f"revoked-{uuid.uuid4().hex[:10]}"
    revoked_req = f"req-revoked-{uuid.uuid4().hex[:10]}"
    tag_revoked = "revoked-actor"
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            _chat, world, actor_b,
            f"[[probe:{tag_revoked}]] revoke the actor mid-turn",
            session_id=revoked_session, request_id=revoked_req)
        world.wait_for_gate(tag_revoked)
        world.sql(
            "UPDATE users SET status='suspended', is_active=0 WHERE id=?",
            (actor_b["id"],))
        world.release(tag_revoked)
        revoked_response = future.result(timeout=240)
    assert revoked_response["success"] is True
    assert _messages(world, revoked_session) == []
    assert _request_record(
        world, revoked_req)["assistant_message_id"] is None
    world.sql(
        "UPDATE users SET status='active', is_active=1 WHERE id=?",
        (actor_b["id"],))


# ---------------------------------------------------------------------------
# 3. Mid-turn authority moves: refuse, never re-scope the turn's content
# ---------------------------------------------------------------------------
def _user_scope(served: ServedWorld, user_id: str) -> dict:
    rows = served.rows(
        "SELECT tenant_id, workspace_id FROM users WHERE id=?", (user_id,))
    assert len(rows) == 1, rows
    return rows[0]


def _gated_refused_turn(world: ServedWorld, actor: dict, tag: str,
                        *, expected_tenant: str, mutate) -> dict:
    """Run one turn, mutate durable authority while the model is awaited."""
    session_id = f"{tag}-{uuid.uuid4().hex[:10]}"
    request_id = f"req-{tag}-{uuid.uuid4().hex[:10]}"
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            _chat, world, actor,
            f"[[probe:{tag}]] move authority while awaiting the model",
            session_id=session_id, request_id=request_id)
        world.wait_for_gate(tag)
        mutate()
        world.release(tag)
        response = future.result(timeout=240)
    # The answer is still delivered: refusing a transcript append must not
    # withhold the turn.
    assert response["success"] is True, response
    assert tag in response["message"], response["message"]
    # ...but nothing durable was appended under the changed scope, and the
    # transport pin has no assistant row to point at.
    assert _messages(world, session_id) == [], tag
    record = _request_record(world, request_id)
    assert record["assistant_message_id"] is None, record
    assert record["tenant_id"] == expected_tenant, record
    assert record["user_id"] == actor["id"], record
    return record


def test_midturn_scope_moves_and_authority_outage_refuse_the_append(world):
    actor = _actor(world, "scope-mover")
    other = _actor(world, "scope-destination")
    original = _user_scope(world, actor["id"])
    assert original["tenant_id"] and original["workspace_id"]
    assert other["tenant_id"] and other["tenant_id"] != original["tenant_id"]
    assert (other["workspace_id"]
            and other["workspace_id"] != original["workspace_id"])

    def move(tenant=None, workspace=None):
        world.sql(
            "UPDATE users SET tenant_id=?, workspace_id=? WHERE id=?",
            (tenant or original["tenant_id"],
             workspace or original["workspace_id"], actor["id"]))

    try:
        # Independent moves and the combined move (the root counter's shape).
        _gated_refused_turn(
            world, actor, "scope-tenant-move",
            expected_tenant=original["tenant_id"],
            mutate=lambda: move(tenant=other["tenant_id"]))
        move()
        _gated_refused_turn(
            world, actor, "scope-workspace-move",
            expected_tenant=original["tenant_id"],
            mutate=lambda: move(workspace=other["workspace_id"]))
        move()
        _gated_refused_turn(
            world, actor, "scope-tenant-and-workspace-move",
            expected_tenant=original["tenant_id"],
            mutate=lambda: move(tenant=other["tenant_id"],
                                workspace=other["workspace_id"]))
    finally:
        # Restore before the outage case: it needs a readable `users` table to
        # set up, and a failed assertion above must not poison teardown.
        move()

    # Authority read outage at WRITE time: the actor table is momentarily
    # unreadable. Fail closed rather than invent a snapshot or fall back to
    # the writer's construction scope.
    try:
        _gated_refused_turn(
            world, actor, "scope-authority-outage",
            expected_tenant=original["tenant_id"],
            mutate=lambda: world.sql(
                "ALTER TABLE users RENAME TO users_scope_outage"))
    finally:
        if (not world.table_exists("users")
                and world.table_exists("users_scope_outage")):
            world.sql("ALTER TABLE users_scope_outage RENAME TO users")

    # The admitted actor row disappears while the model is awaited: the
    # write-time authority read finds no row and must refuse, never adopt a
    # different scope for the old turn's content.
    victim = _actor(world, "scope-victim")
    victim_scope = _user_scope(world, victim["id"])
    _gated_refused_turn(
        world, victim, "scope-actor-deleted",
        expected_tenant=victim_scope["tenant_id"],
        mutate=lambda: world.sql(
            "DELETE FROM users WHERE id=?", (victim["id"],)))
    assert world.rows(
        "SELECT id FROM users WHERE id=?", (victim["id"],)) == []

    # A correct, unchanged scope after every refusal still writes normally.
    session_id = f"scope-restored-{uuid.uuid4().hex[:10]}"
    request_id = f"req-scope-restored-{uuid.uuid4().hex[:10]}"
    response = _chat(
        world, actor, "unchanged scope after the refusals",
        session_id=session_id, request_id=request_id)
    capture = _assert_actor_rows(world, actor, session_id, request_id, response)
    assert {row["tenant_id"] for row in capture["rows"]} == {
        original["tenant_id"]}


# ---------------------------------------------------------------------------
# 4. Legacy placeholder reclaim is durable in the write transaction
# ---------------------------------------------------------------------------
def test_legacy_placeholder_reclaim_is_durable_across_restart(world):
    owner = _actor(world, "reclaimer")
    other = _actor(world, "later-visitor")
    legacy_session = f"legacy-{uuid.uuid4().hex[:10]}"
    world.sql(
        "INSERT INTO chat_sessions (id, user_id, title, metadata_json, "
        "channel_id, thread_id, created_at, updated_at, message_count) "
        "VALUES (?, 'default', ?, '{}', NULL, NULL, datetime('now'), "
        "datetime('now'), 0)",
        (legacy_session, "legacy conversation"),
    )
    owner_req = f"req-legacy-owner-{uuid.uuid4().hex[:10]}"
    response = _chat(
        world, owner, "reclaim this legacy conversation",
        session_id=legacy_session, request_id=owner_req)
    _assert_actor_rows(world, owner, legacy_session, owner_req, response)
    # The reclaim is a durable transaction, not an in-memory label.
    assert world.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?",
        (legacy_session,)) == [{"user_id": owner["id"]}]

    # A cold process: another local user must neither append to nor adopt the
    # reclaimed conversation. Canonical admission gives that turn a FRESH,
    # owned conversation instead of the requested foreign id — the request key
    # below stays the ORIGINAL requested session for idempotency.
    world.restart()
    foreign_before = _messages(world, legacy_session)
    other = _login(world, other["email"], other["password"])
    other_req = f"req-legacy-other-{uuid.uuid4().hex[:10]}"
    other_response = _chat(
        world, other, "claim somebody else's reclaimed conversation",
        session_id=legacy_session, request_id=other_req)
    assert other_response["success"] is True

    capture = _assert_canonical_turn_binding(
        world, other,
        requested_session=legacy_session,
        request_id=other_req,
        response=other_response,
        requested_before=foreign_before,
    )
    canonical_session = other_response["session_id"]
    canonical_rows = capture["rows"]
    other_record = capture["record"]
    # The requested conversation's durable owner is still the original owner.
    assert world.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?",
        (legacy_session,)) == [{"user_id": owner["id"]}]

    # Same original request id AFTER a fresh canonical allocation: the exact
    # stored response/canonical id/execution id/assistant id replays with no
    # second execution and no new history rows in either conversation.
    execution_before = world.rows(
        "SELECT id FROM agent_executions WHERE id=?",
        (other_response["execution_id"],))
    assert len(execution_before) == 1, execution_before
    replay = _chat(
        world, other, "claim somebody else's reclaimed conversation",
        session_id=legacy_session, request_id=other_req)
    assert replay["message"] == other_response["message"]
    assert replay["session_id"] == canonical_session
    assert str(replay["execution_id"]) == str(other_response["execution_id"])
    assert replay.get("model") == other_response.get("model")
    assert replay.get("provider") == other_response.get("provider")
    replay_record = _request_record(world, other_req)
    assert replay_record["assistant_message_id"] == (
        other_record["assistant_message_id"])
    assert str(replay_record["execution_id"]) == str(
        other_record["execution_id"])
    assert replay_record["state"] == "completed"
    assert replay_record["session_id"] == legacy_session
    assert _messages(world, canonical_session) == canonical_rows
    assert _messages(world, legacy_session) == foreign_before
    assert world.rows(
        "SELECT id FROM agent_executions WHERE id=?",
        (other_response["execution_id"],)) == execution_before
    assert world.rows(
        "SELECT count(*) AS n FROM chat_request_records WHERE request_id=?",
        (other_req,)) == [{"n": 1}]

    # The owner still owns it after the same cold restart; a legitimate
    # same-user continuation keeps the requested id (no fresh allocation).
    owner = _login(world, owner["email"], owner["password"])
    owner_again = f"req-legacy-owner-2-{uuid.uuid4().hex[:10]}"
    second = _chat(
        world, owner, "the owner continues the conversation",
        session_id=legacy_session, request_id=owner_again)
    assert second["success"] is True
    assert second["session_id"] == legacy_session, second
    rows = _messages(world, legacy_session)
    assert len(rows) == 4, rows
    assert {row["tenant_id"] for row in rows} == {owner["tenant_id"]}, rows
    record = _request_record(world, owner_again)
    assert record["session_id"] == legacy_session, record
    assert record["tenant_id"] == owner["tenant_id"], record
    assert record["user_id"] == owner["id"], record
    assert record["assistant_message_id"] in {
        row["id"] for row in rows if row["role"] == "assistant"}, record
    assert str(record["execution_id"]) == str(second["execution_id"]), record
    owner_assistant = next(
        row for row in rows if row["id"] == record["assistant_message_id"])
    assert owner_assistant["content"] == second["message"]
    # ...and the fresh canonical conversation from the foreign turn is still
    # exactly the other user's two rows, untouched by the owner's turn.
    assert _messages(world, canonical_session) == canonical_rows
    assert world.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?",
        (canonical_session,)) == [{"user_id": other["id"]}]


# ---------------------------------------------------------------------------
# 5. Canonical-binding controls: forged metadata, wrong owner/tenant/rowid
# ---------------------------------------------------------------------------
def test_forged_canonical_metadata_cannot_choose_the_durable_target(world):
    """The server, never client metadata, chooses the canonical conversation.

    A caller can name another user's conversation and send every
    canonical-looking field in ``context`` (session/conversation/durable ids,
    owner and tenant). The turn must still be admitted into a FRESH owned
    conversation, and the verifier must reject forged identities, a wrong
    owner/tenant/assistant rowid or a changed foreign conversation. A valid
    own session, by contrast, keeps its requested id even beside the forged
    metadata.
    """
    owner = _actor(world, "canon-target")
    actor = _actor(world, "canon-forger")

    target = f"canon-{uuid.uuid4().hex[:10]}"
    owner_req = f"req-canon-owner-{uuid.uuid4().hex[:10]}"
    owner_response = _chat(
        world, owner, "the owner's own conversation",
        session_id=target, request_id=owner_req)
    owner_before = _messages(world, target)
    assert sorted(row["role"] for row in owner_before) == [
        "assistant", "user"], owner_before
    assert {row["tenant_id"] for row in owner_before} == {
        owner["tenant_id"]}, owner_before
    assert world.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?",
        (target,)) == [{"user_id": owner["id"]}]

    forged_context = {
        "session_id": target,
        "conversation_id": target,
        "canonical_session_id": target,
        "durable_session_id": target,
        "user_id": owner["id"],
        "tenant_id": owner["tenant_id"],
        "workspace_id": owner["workspace_id"],
    }
    forger_req = f"req-canon-forger-{uuid.uuid4().hex[:10]}"
    forged_response = _chat(
        world, actor, "use the forged canonical target",
        session_id=target, request_id=forger_req,
        context=forged_context)
    assert forged_response["session_id"] != target, forged_response
    assert forged_response["session_id"] != forged_context[
        "canonical_session_id"], forged_response

    capture = _assert_canonical_turn_binding(
        world, actor,
        requested_session=target,
        request_id=forger_req,
        response=forged_response,
        requested_before=owner_before,
    )
    canonical_session = forged_response["session_id"]
    # The requested foreign conversation is still exactly the owner's.
    assert _messages(world, target) == owner_before
    assert world.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?",
        (target,)) == [{"user_id": owner["id"]}]

    # A valid OWN session keeps its requested id, and the forged metadata
    # still cannot redirect the turn elsewhere.
    own_req = f"req-canon-own-{uuid.uuid4().hex[:10]}"
    own_response = _chat(
        world, actor, "continue my own canonical session",
        session_id=canonical_session, request_id=own_req,
        context=forged_context)
    assert own_response["session_id"] == canonical_session, own_response
    own_rows = _messages(world, canonical_session)
    assert len(own_rows) == 4, own_rows
    assert {row["tenant_id"] for row in own_rows} == {actor["tenant_id"]}, (
        own_rows)
    own_record = _request_record(world, own_req)
    assert own_record["session_id"] == canonical_session, own_record
    assert own_record["user_id"] == actor["id"], own_record
    assert own_record["tenant_id"] == actor["tenant_id"], own_record
    assert own_record["state"] == "completed", own_record
    own_assistant = next(
        row for row in own_rows
        if row["id"] == own_record["assistant_message_id"])
    assert own_assistant["role"] == "assistant"
    assert own_assistant["content"] == own_response["message"]
    assert own_record["assistant_message_id"] == own_assistant["id"], (
        own_record)
    assert str(own_record["execution_id"]) == str(
        own_response["execution_id"]), own_record
    assert _messages(world, target) == owner_before
    assert world.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?",
        (canonical_session,)) == [{"user_id": actor["id"]}]

    # Negative controls for the verifier itself: every forged/wrong binding
    # must be rejected, including a relaxed tenant or a guessed rowid.
    good_rows = [dict(row) for row in capture["rows"]]
    good_record = dict(capture["record"])
    assistant_index = next(
        index for index, row in enumerate(good_rows)
        if row["role"] == "assistant")

    def _verify(**overrides):
        kwargs = {
            "actor": actor,
            "requested_session": target,
            "response": forged_response,
            "rows": [dict(row) for row in good_rows],
            "record": dict(good_record),
            "canonical_owner": [{"user_id": actor["id"]}],
            "requested_before": owner_before,
            "requested_after": _messages(world, target),
        }
        kwargs.update(overrides)
        return _verify_canonical_turn_binding(**kwargs)

    _verify()  # the captured turn itself is valid

    with pytest.raises(AssertionError):
        # Client-chosen canonical id (the requested foreign id) is not proof.
        _verify(response={**forged_response, "session_id": target})
    with pytest.raises(AssertionError):
        # Wrong durable owner for the canonical conversation.
        _verify(canonical_owner=[{"user_id": owner["id"]}])

    wrong_tenant = [dict(row) for row in good_rows]
    for row in wrong_tenant:
        row["tenant_id"] = owner["tenant_id"]
    with pytest.raises(AssertionError):
        _verify(rows=wrong_tenant)

    one_wrong_tenant = [dict(row) for row in good_rows]
    one_wrong_tenant[assistant_index]["tenant_id"] = owner["tenant_id"]
    with pytest.raises(AssertionError):
        _verify(rows=one_wrong_tenant)

    wrong_rowid = [dict(row) for row in good_rows]
    wrong_rowid[assistant_index]["id"] = owner_before[assistant_index]["id"]
    with pytest.raises(AssertionError):
        _verify(rows=wrong_rowid)

    with pytest.raises(AssertionError):
        # The original request key may not be rewritten to the canonical id.
        _verify(record={**good_record, "session_id": canonical_session})
    with pytest.raises(AssertionError):
        _verify(record={
            **good_record,
            "assistant_message_id": owner_before[assistant_index]["id"]})
    with pytest.raises(AssertionError):
        _verify(record={
            **good_record, "execution_id": owner_response["execution_id"]})

    tampered_foreign = [dict(row) for row in owner_before]
    tampered_foreign[assistant_index]["content"] = "tampered"
    with pytest.raises(AssertionError):
        _verify(requested_after=tampered_foreign)


# ---------------------------------------------------------------------------
# 6. External-platform declared scope: valid for the bridge, not adoptable
# ---------------------------------------------------------------------------
def test_external_bridge_scope_stays_declared_and_local_callers_cannot_adopt_it(
        world):
    bridge_turn = httpx.post(
        world.base_url + "/__fixture/external-bridge-turn",
        json={"sender_id": "fixture-sender", "recipient_id": "fixture-bot",
              "message": "external bridge turn"},
        # The app's CSRF middleware exempts Bearer-authenticated calls; this
        # fixture-only endpoint has no browser session to protect.
        headers={"Authorization": "Bearer served-chat-scope-fixture"},
        timeout=180,
        trust_env=False,
    )
    assert bridge_turn.status_code == 200, bridge_turn.text
    assert bridge_turn.json().get("status") == "success", bridge_turn.text
    # The universal bridge's canonical session key for a `slack` message.
    session_id = "slack_fixture-bot_fixture-sender_"
    rows = _messages(world, session_id)
    assert sorted(row["role"] for row in rows) == ["assistant", "user"], rows
    assert {row["tenant_id"] for row in rows} == {"default"}, rows
    assert world.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?",
        (session_id,)) == [{"user_id": "external_agent_user"}]

    local = _actor(world, "scope-local-intruder")

    def attempt(tag: str, actor: dict) -> None:
        request_id = f"req-{tag}-{uuid.uuid4().hex[:10]}"
        response = _chat(
            world, actor,
            "claim the external-platform conversation",
            session_id=session_id, request_id=request_id)
        assert response["success"] is True
        assert _messages(world, session_id) == rows
        assert _request_record(
            world, request_id)["assistant_message_id"] is None
        assert world.rows(
            "SELECT user_id FROM chat_sessions WHERE id=?",
            (session_id,)) == [{"user_id": "external_agent_user"}]

    # Warm process.
    attempt("scope-external-warm", local)

    # Cold/new process: the durable owner is still the system identity.
    world.restart()
    local = _login(world, local["email"], local["password"])
    attempt("scope-external-cold", local)


# ---------------------------------------------------------------------------
# 7. Storage outage: answer delivered, durable transcript NOT claimed
# ---------------------------------------------------------------------------
def test_storage_outage_never_claims_a_durable_transcript(world):
    actor = _actor(world, "outage")
    session_id = f"outage-{uuid.uuid4().hex[:10]}"
    request_id = f"req-outage-{uuid.uuid4().hex[:10]}"
    tag = "storage-outage"
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            _chat, world, actor,
            f"[[probe:{tag}]] persist into an unavailable store",
            session_id=session_id, request_id=request_id)
        world.wait_for_gate(tag)
        assert world.table_exists("chat_messages")
        world.sql("DROP TABLE chat_messages")
        world.release(tag)
        response = future.result(timeout=240)

    # The answer is still delivered — losing a transcript write must not
    # withhold the turn.
    assert response["success"] is True
    assert tag in response["message"], response["message"]
    assert response.get("execution_id")
    # ...but nothing claims a durable chat row: the table stayed absent and
    # the transport pin carries no assistant-message identity.
    assert not world.table_exists("chat_messages")
    record = _request_record(world, request_id)
    assert record["state"] == "completed", record
    assert record["assistant_message_id"] is None, record
    assert record["tenant_id"] == actor["tenant_id"], record
