# -*- coding: utf-8 -*-
"""Public chat read envelopes belong to the durable session owner/scope.

Baseline observed on ``ba0f056e5`` (2026-11-17) through the real served
boundary and recorded by the paired scratch counter
(``/private/tmp/atom-chat-history-reader-scope-paired-counter-20261117.py``,
results ``...-baseline-result-...json`` / ``...-final-result-...json``):

* an ordinary non-default user cold-loading a conversation durably owned by
  the external-platform system identity got ``200`` with both private rows
  from ``/history`` and the linked run from ``/trace`` (also ``/sessions``);
* the same user cold-loading a foreign local user's durable conversation got
  ``200`` with its rows;
* after a durable owner change, the warm in-memory label still served the
  content (and a cold process still did, because the route lazy-created a
  caller-owned projection and then read the row by conversation id);
* a default-scope legacy placeholder conversation was served to a non-default
  caller, and the placeholder owner was left unclaimed;
* the external bridge's own write was correct (2 rows, ``default`` tenant,
  ``external_agent_user`` owner), but a local caller could then read it.

This suite pins the corrected envelope: the durable ``ChatSession`` owner is
read on EVERY request (warm cache and cold process), a named owner is served
only to that same verified local principal, a legacy placeholder is reclaimed
only inside the caller's CURRENT canonical scope, and external/system-owned
rows are never handed to a local caller. Legitimate own history, the default
(NULL-tenant) admin's own history and the external bridge writer stay
unchanged. The real JWT signup/login, SQLite, uvicorn process and transcript
writer are used; only the LLM/embedding transports are doubled by
``tests/fixtures/served_chat_scope_app.py``. No real model quality is claimed.
"""
from __future__ import annotations

import json
import uuid

import httpx
import pytest

from tests.test_chat_message_actor_scope import (
    ServedWorld,
    _actor,
    _chat,
    _login,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.api,
    pytest.mark.slow,
]

_SECRET_USER = "counter-user-secret"
_SECRET_ASSISTANT = "counter-assistant-secret"


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
def _auth(actor: dict) -> dict:
    return {"Authorization": f"Bearer {actor['token']}"}


def _history(world: ServedWorld, actor: dict, session_id: str) -> httpx.Response:
    return httpx.get(
        world.base_url + f"/api/chat/history/{session_id}",
        headers=_auth(actor), timeout=60, trust_env=False)


def _trace(world: ServedWorld, actor: dict, session_id: str) -> httpx.Response:
    return httpx.get(
        world.base_url + f"/api/chat/trace/{session_id}",
        headers=_auth(actor), timeout=60, trust_env=False)


def _details(world: ServedWorld, actor: dict,
             session_id: str) -> httpx.Response:
    return httpx.get(
        world.base_url + f"/api/chat/sessions/{session_id}",
        headers=_auth(actor), timeout=60, trust_env=False)


def _task(world: ServedWorld, actor: dict, session_id: str) -> httpx.Response:
    return httpx.get(
        world.base_url + f"/api/chat/task/{session_id}",
        headers=_auth(actor), timeout=60, trust_env=False)


def _memory(world: ServedWorld, actor: dict,
            session_id: str) -> httpx.Response:
    return httpx.get(
        world.base_url + f"/api/chat/memory/{session_id}",
        headers=_auth(actor), timeout=60, trust_env=False)


def _seed_session(
    world: ServedWorld, session_id: str, owner: str, tenant_id: str,
    *, title: str = "counter conversation",
) -> None:
    world.sql(
        "INSERT INTO chat_sessions (id, user_id, title, metadata_json, "
        "channel_id, thread_id, created_at, updated_at, message_count) "
        "VALUES (?, ?, ?, '{}', NULL, NULL, datetime('now'), "
        "datetime('now'), 2)",
        (session_id, owner, title),
    )
    for role, content in (("user", _SECRET_USER),
                          ("assistant", _SECRET_ASSISTANT)):
        world.sql(
            "INSERT INTO chat_messages (id, conversation_id, tenant_id, role, "
            "content, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (str(uuid.uuid4()), session_id, tenant_id, role, content),
        )


def _seed_execution(world: ServedWorld, session_id: str) -> str:
    execution_id = str(uuid.uuid4())
    world.sql(
        "INSERT INTO agent_executions (id, agent_id, tenant_id, status, "
        "input_summary, triggered_by, started_at, metadata_json) "
        "VALUES (?, 'atom_main', 'default', 'completed', 'counter trace', "
        "'chat', datetime('now'), ?)",
        (execution_id, json.dumps({"session_id": session_id})),
    )
    return execution_id


def _durable_messages(world: ServedWorld, session_id: str) -> list[dict]:
    return world.rows(
        "SELECT id, tenant_id, role, content FROM chat_messages "
        "WHERE conversation_id=? ORDER BY role", (session_id,))


def _durable_owner(world: ServedWorld, session_id: str) -> list[dict]:
    return world.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?", (session_id,))


def _fresh_login(world: ServedWorld, actor: dict) -> dict:
    return _login(world, actor["email"], actor["password"])


def _assert_refused_before_content(response: httpx.Response) -> None:
    assert response.status_code in (403, 404), response.text
    assert _SECRET_USER not in response.text, response.text[:500]
    assert _SECRET_ASSISTANT not in response.text, response.text[:500]


# ---------------------------------------------------------------------------
# 1. System-owned and foreign local conversations: warm + cold refusal
# ---------------------------------------------------------------------------
def test_system_and_foreign_durable_reads_refuse_warm_and_cold(world):
    local = _actor(world, "read-local")
    other = _actor(world, "read-other")
    assert local["tenant_id"] and local["tenant_id"] != "default"
    assert other["tenant_id"] != local["tenant_id"]

    system_session = f"read-system-{uuid.uuid4().hex[:8]}"
    _seed_session(world, system_session, "external_agent_user", "default")
    system_execution = _seed_execution(world, system_session)
    system_rows_before = _durable_messages(world, system_session)
    system_owner_before = _durable_owner(world, system_session)

    foreign_session = f"read-foreign-{uuid.uuid4().hex[:8]}"
    _seed_session(world, foreign_session, other["id"], other["tenant_id"])
    foreign_execution = _seed_execution(world, foreign_session)
    foreign_rows_before = _durable_messages(world, foreign_session)
    foreign_owner_before = _durable_owner(world, foreign_session)

    # Cold/new process: no caller-owned projection exists in memory.
    world.restart()
    local = _fresh_login(world, local)

    for session_id, execution_id, rows_before, owner_before in (
        (system_session, system_execution, system_rows_before,
         system_owner_before),
        (foreign_session, foreign_execution, foreign_rows_before,
         foreign_owner_before),
    ):
        _assert_refused_before_content(_history(world, local, session_id))
        trace = _trace(world, local, session_id)
        _assert_refused_before_content(trace)
        assert json.loads(trace.text).get("runs", []) == []
        _assert_refused_before_content(_details(world, local, session_id))
        _assert_refused_before_content(_task(world, local, session_id))
        # Every parallel read surface is refused, not just /history.
        assert _memory(world, local, session_id).status_code in (403, 404)
        # The same durable envelope fences the session mutations and the
        # fork (which would copy the private rows into a caller-owned id).
        renamed = httpx.patch(
            world.base_url + f"/api/chat/sessions/{session_id}",
            headers=_auth(local),
            json={"title": "hijacked", "user_id": "ignored-client-id"},
            timeout=60, trust_env=False)
        assert renamed.status_code == 403, renamed.text
        deleted = httpx.delete(
            world.base_url + f"/api/chat/sessions/{session_id}",
            headers=_auth(local), timeout=60, trust_env=False)
        assert deleted.status_code == 403, deleted.text
        forked = httpx.post(
            world.base_url + f"/api/chat/sessions/{session_id}/fork",
            headers=_auth(local), json={}, timeout=60, trust_env=False)
        assert forked.status_code == 403, forked.text

        # Read refusals never mutate the durable owner, rows or the execution
        # row the trace would have exposed.
        assert _durable_messages(world, session_id) == rows_before
        assert _durable_owner(world, session_id) == owner_before
        assert world.rows(
            "SELECT id FROM agent_executions WHERE id=?", (execution_id,)
        ) == [{"id": execution_id}]

    # A legacy JSON-file session label claiming the local user must not
    # override the foreign durable owner in the sidebar list either. The
    # manager merges file-only ids, so seed exactly that stale cache shape.
    sessions_file = world.data_dir / "chat_sessions.json"
    sessions_file.write_text(json.dumps([{
        "session_id": foreign_session,
        "user_id": local["id"],
        "title": "stale cached sidebar entry",
        "history": [{"role": "user", "content": "stale-cache-secret"}],
        "created_at": "2026-01-01T00:00:00",
        "last_active": "2026-01-01T00:00:00",
    }]), encoding="utf-8")
    listed = httpx.get(
        world.base_url + "/api/chat/sessions",
        headers=_auth(local), timeout=60, trust_env=False)
    assert listed.status_code == 200, listed.text
    assert foreign_session not in listed.text
    assert "stale-cache-secret" not in listed.text

    # Warm process: retrying must not fall back to a caller-owned cache.
    _assert_refused_before_content(_history(world, local, system_session))
    _assert_refused_before_content(_trace(world, local, foreign_session))
    assert _durable_messages(world, system_session) == system_rows_before
    assert _durable_owner(world, system_session) == system_owner_before
    assert _durable_messages(world, foreign_session) == foreign_rows_before
    assert _durable_owner(world, foreign_session) == foreign_owner_before


# ---------------------------------------------------------------------------
# 2. A warm in-memory label cannot outlive a durable owner change
# ---------------------------------------------------------------------------
def test_durable_owner_change_overrides_warm_cache(world):
    owner = _actor(world, "owner-change")
    other = _actor(world, "owner-change-destination")
    session_id = f"read-owner-change-{uuid.uuid4().hex[:8]}"
    _chat(
        world, owner, "owner-change-marker",
        session_id=session_id,
        request_id=f"req-owner-change-{uuid.uuid4().hex[:8]}",
    )

    # The owner reads its own conversation (warm, caller-owned projection).
    ok = _history(world, owner, session_id)
    assert ok.status_code == 200, ok.text
    assert "owner-change-marker" in ok.text

    # The DURABLE owner changes while the process (and its in-memory label)
    # stays warm. The next read must consult the DB, not the cache.
    world.sql(
        "UPDATE chat_sessions SET user_id=? WHERE id=?",
        (other["id"], session_id),
    )
    refused = _history(world, owner, session_id)
    assert refused.status_code == 403, refused.text
    assert "owner-change-marker" not in refused.text

    # Cold/new process: the same refusal; the durable owner is unchanged.
    world.restart()
    owner = _fresh_login(world, owner)
    assert _history(world, owner, session_id).status_code == 403
    assert _durable_owner(world, session_id) == [{"user_id": other["id"]}]

    # The new durable owner can read it (legitimate owner read).
    other = _fresh_login(world, other)
    owned = _history(world, other, session_id)
    assert owned.status_code == 200, owned.text
    assert "owner-change-marker" in owned.text


# ---------------------------------------------------------------------------
# 3. Legacy placeholder reclaim is scoped to the caller's canonical scope
# ---------------------------------------------------------------------------
def test_legacy_placeholder_reclaim_requires_current_canonical_scope(world):
    local = _actor(world, "scope-local")
    admin = _login(world, "admin@example.com", world.admin_password)
    admin.update(email="admin@example.com", password=world.admin_password)
    assert admin["tenant_id"] is None

    # A default-scope legacy conversation is NOT claimable by a non-default
    # caller just because the owner label is a placeholder.
    default_placeholder = f"read-placeholder-default-{uuid.uuid4().hex[:8]}"
    _seed_session(world, default_placeholder, "default", "default")
    refused = _history(world, local, default_placeholder)
    _assert_refused_before_content(refused)
    assert _durable_owner(world, default_placeholder) == [{"user_id": "default"}]

    # The default/NULL-tenant admin is the documented Personal-Edition
    # compatibility principal: its canonical scope matches the rows, so it
    # reclaims the same conversation DURABLY (not just an in-memory label).
    reclaimed = _history(world, admin, default_placeholder)
    assert reclaimed.status_code == 200, reclaimed.text
    assert _SECRET_USER in reclaimed.text
    assert _durable_owner(world, default_placeholder) == [
        {"user_id": admin["id"]}]

    # Cold process: the reclaim survives, and a different local caller still
    # cannot take it.
    world.restart()
    local = _fresh_login(world, local)
    admin = _fresh_login(world, admin)
    assert _history(world, local, default_placeholder).status_code == 403
    again = _history(world, admin, default_placeholder)
    assert again.status_code == 200, again.text
    assert _durable_owner(world, default_placeholder) == [
        {"user_id": admin["id"]}]

    # A same-scope legacy conversation is reclaimable by its real scope owner.
    scoped = _actor(world, "scope-match")
    old_scope = scoped["tenant_id"]
    scoped_placeholder = f"read-placeholder-scoped-{uuid.uuid4().hex[:8]}"
    _seed_session(world, scoped_placeholder, "anonymous", old_scope)
    scoped_read = _history(world, scoped, scoped_placeholder)
    assert scoped_read.status_code == 200, scoped_read.text
    assert _durable_owner(world, scoped_placeholder) == [
        {"user_id": scoped["id"]}]

    # The caller's CURRENT canonical scope moved. A different placeholder
    # conversation still carrying the OLD scope is no longer claimable.
    other = _actor(world, "scope-destination")
    assert other["tenant_id"] != old_scope
    world.sql(
        "UPDATE users SET tenant_id=?, workspace_id=? WHERE id=?",
        (other["tenant_id"], other["workspace_id"], scoped["id"]),
    )
    moved_placeholder = f"read-placeholder-moved-{uuid.uuid4().hex[:8]}"
    _seed_session(world, moved_placeholder, "default", old_scope)
    moved = _history(world, scoped, moved_placeholder)
    assert moved.status_code == 403, moved.text
    assert _SECRET_USER not in moved.text
    assert _durable_owner(world, moved_placeholder) == [{"user_id": "default"}]


# ---------------------------------------------------------------------------
# 4. Positives: own history, default admin, bridge writer, in-memory surface
# ---------------------------------------------------------------------------
def test_own_default_and_bridge_writer_positives_are_unchanged(world):
    local = _actor(world, "positive-local")
    admin = _login(world, "admin@example.com", world.admin_password)
    admin.update(email="admin@example.com", password=world.admin_password)

    own_session = f"read-own-{uuid.uuid4().hex[:8]}"
    _chat(
        world, local, "positive-own-marker",
        session_id=own_session,
        request_id=f"req-own-{uuid.uuid4().hex[:8]}",
    )
    own = _history(world, local, own_session)
    assert own.status_code == 200, own.text
    assert "positive-own-marker" in own.text
    details = _details(world, local, own_session)
    assert details.status_code == 200, details.text
    assert details.json()["user_id"] == local["id"]
    # The session is in the served process's memory after its turn.
    assert _memory(world, local, own_session).status_code == 200
    assert _task(world, local, own_session).status_code == 200

    # A different local user still cannot read the owner's conversation.
    intruder = _actor(world, "positive-intruder")
    assert _history(world, intruder, own_session).status_code == 403

    # The opposite cache direction: a stale FILE label naming someone else
    # must not deny the verified durable owner. Write that legacy-file shape
    # and restart so the served process loads it into memory.
    sessions_file = world.data_dir / "chat_sessions.json"
    sessions_file.write_text(json.dumps([{
        "session_id": own_session,
        "user_id": "legacy-stale-owner",
        "title": "stale file title",
        "history": [{"role": "user", "content": "stale-file-secret"}],
        "created_at": "2026-01-01T00:00:00",
        "last_active": "2026-01-01T00:00:00",
    }]), encoding="utf-8")
    world.restart()
    local = _fresh_login(world, local)
    admin = _fresh_login(world, admin)
    own_after = _history(world, local, own_session)
    assert own_after.status_code == 200, own_after.text
    assert "positive-own-marker" in own_after.text
    # Durable history is authoritative; the stale file body was not served.
    assert "stale-file-secret" not in own_after.text
    assert world.rows(
        "SELECT user_id FROM chat_sessions WHERE id=?", (own_session,)
    ) == [{"user_id": local["id"]}]

    # The default/NULL-tenant admin's own history is a legitimate positive.
    admin_session = f"read-admin-{uuid.uuid4().hex[:8]}"
    _chat(
        world, admin, "positive-admin-marker",
        session_id=admin_session,
        request_id=f"req-admin-{uuid.uuid4().hex[:8]}",
    )
    admin_read = _history(world, admin, admin_session)
    assert admin_read.status_code == 200, admin_read.text
    assert "positive-admin-marker" in admin_read.text

    # The external bridge's declared-scope write is unchanged...
    bridge = httpx.post(
        world.base_url + "/__fixture/external-bridge-turn",
        json={"sender_id": "read-bridge-sender",
              "recipient_id": "read-bridge-bot",
              "message": "read bridge turn"},
        headers={"Authorization": "Bearer served-chat-scope-fixture"},
        timeout=180, trust_env=False,
    )
    assert bridge.status_code == 200, bridge.text
    assert bridge.json().get("status") == "success", bridge.text
    bridge_session = "slack_read-bridge-bot_read-bridge-sender_"
    bridge_rows = world.rows(
        "SELECT role, tenant_id FROM chat_messages WHERE conversation_id=? "
        "ORDER BY role", (bridge_session,))
    assert sorted(row["role"] for row in bridge_rows) == ["assistant", "user"]
    assert {row["tenant_id"] for row in bridge_rows} == {"default"}
    assert _durable_owner(world, bridge_session) == [
        {"user_id": "external_agent_user"}]

    # ...but a local caller still cannot read the bridge's conversation.
    _assert_refused_before_content(_history(world, local, bridge_session))


# ---------------------------------------------------------------------------
# 5. Unverifiable / unavailable authority is honest, never content
# ---------------------------------------------------------------------------
def test_unverifiable_or_unreadable_authority_never_serves_content(world):
    local = _actor(world, "unverified-local")

    # Message rows with no durable session row: no verifiable owner.
    orphan_session = f"read-orphan-{uuid.uuid4().hex[:8]}"
    for role, content in (("user", _SECRET_USER),
                          ("assistant", _SECRET_ASSISTANT)):
        world.sql(
            "INSERT INTO chat_messages (id, conversation_id, tenant_id, role, "
            "content, created_at) VALUES (?, ?, 'default', ?, ?, "
            "datetime('now'))",
            (str(uuid.uuid4()), orphan_session, role, content),
        )
    _assert_refused_before_content(_history(world, local, orphan_session))
    _assert_refused_before_content(_trace(world, local, orphan_session))
    _assert_refused_before_content(_details(world, local, orphan_session))
    # The refusal did not invent a session row or claim the messages.
    assert _durable_owner(world, orphan_session) == []

    # An execution that merely NAMES an unknown session id is not a grant:
    # the trace surface returns no runs instead of querying arbitrary
    # execution rows by a caller-supplied string.
    unknown_session = f"read-unknown-{uuid.uuid4().hex[:8]}"
    unknown_execution = _seed_execution(world, unknown_session)
    unknown_trace = _trace(world, local, unknown_session)
    assert unknown_trace.status_code == 200, unknown_trace.text
    assert unknown_trace.json().get("runs") == []
    assert world.rows(
        "SELECT id FROM agent_executions WHERE id=?", (unknown_execution,)
    ) == [{"id": unknown_execution}]

    # An EMPTY placeholder session has no message-row scope evidence, but it
    # may still carry foreign trace/task records keyed by its id. A
    # non-default caller must not be able to adopt that id into a grant.
    empty_placeholder = f"read-empty-placeholder-{uuid.uuid4().hex[:8]}"
    world.sql(
        "INSERT INTO chat_sessions (id, user_id, title, metadata_json, "
        "channel_id, thread_id, created_at, updated_at, message_count) "
        "VALUES (?, 'default', 'empty legacy', '{}', NULL, NULL, "
        "datetime('now'), datetime('now'), 0)",
        (empty_placeholder,),
    )
    empty_execution = _seed_execution(world, empty_placeholder)
    _assert_refused_before_content(_history(world, local, empty_placeholder))
    empty_trace = _trace(world, local, empty_placeholder)
    _assert_refused_before_content(empty_trace)
    assert json.loads(empty_trace.text).get("runs", []) == []
    assert _durable_owner(world, empty_placeholder) == [{"user_id": "default"}]
    assert world.rows(
        "SELECT id FROM agent_executions WHERE id=?", (empty_execution,)
    ) == [{"id": empty_execution}]

    # The documented default/NULL-tenant admin compatibility does not invent
    # a scope for an empty placeholder either: no durable rows = no grant.
    admin = _login(world, "admin@example.com", world.admin_password)
    admin.update(email="admin@example.com", password=world.admin_password)
    admin_empty = _history(world, admin, empty_placeholder)
    assert admin_empty.status_code == 404, admin_empty.text
    assert _durable_owner(world, empty_placeholder) == [{"user_id": "default"}]

    # Authority read outage: the durable owner table is momentarily
    # unreadable. The read is unavailable (503), never cached content.
    try:
        world.sql("ALTER TABLE chat_sessions RENAME TO chat_sessions_outage")
        outage = _history(world, local, f"read-outage-{uuid.uuid4().hex[:8]}")
        assert outage.status_code == 503, outage.text
        assert _SECRET_USER not in outage.text
        assert _SECRET_ASSISTANT not in outage.text
    finally:
        if (not world.table_exists("chat_sessions")
                and world.table_exists("chat_sessions_outage")):
            world.sql(
                "ALTER TABLE chat_sessions_outage RENAME TO chat_sessions")

    # The restored authority still serves a legitimate own conversation.
    own_session = f"read-restored-{uuid.uuid4().hex[:8]}"
    _chat(
        world, local, "restored-own-marker",
        session_id=own_session,
        request_id=f"req-restored-{uuid.uuid4().hex[:8]}",
    )
    assert _history(world, local, own_session).status_code == 200
