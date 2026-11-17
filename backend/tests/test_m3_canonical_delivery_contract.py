# -*- coding: utf-8 -*-
"""M3 canonical delivery contract — the public chat boundary.

The earlier M3 repair only reconciled the WebSocket close when
``_validate_response_payload`` FAILED. An ordinary valid payload took the
``valid`` branch, which assigned the raw stream buffer to the close frame
and to ``response_data["content"]`` — and the shared tail then returned that
raw text to the HTTP caller and to the durable ``ChatMessage`` row. The
enabled M3 workflow validation was therefore bypassed on every normal turn:
``FakeLLM.stream_completion`` ran once, ``_m3_reconcile_stream_done`` ran
zero times, and an unsupported "I sent the email." reached all three sinks.

These tests drive the REAL public boundary:

* the real ``POST /api/chat/message`` router (``integrations.chat_routes``),
* a REAL signed JWT validated by ``core.auth.get_current_user``,
* the real orchestration + reply leg (``process_chat_message`` →
  ``_get_qwen_response``),
* the real WebSocket close frames captured from ``core.websockets.manager``,
* a FRESH read of the durable ``ChatMessage`` assistant row.

Only the external model outputs, memory assembly, the planner and the WS
transport are doubled. No real email is sent, no receipt is fabricated as a
legitimate send, and the safety paths are not disabled to make a test pass.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auth import create_access_token
from core.llm.byok_handler import QueryComplexity
from core.models import ChatMessage, ChatSession, User
from core.models_registration import Base
from integrations import chat_routes as cr

CANVAS_ID = "canvas-m3-contract"
SESSION_ID = "session-m3-contract"
READ_ONLY_ASK = "What is the status of the draft?"

#: A benign read-only sentence beside an unsupported workflow completion.
SUMMARY_PLUS_UNSUPPORTED_SEND = (
    "The draft is ready for your review. I sent the email.")
ONLY_UNSUPPORTED_SEND = "I sent the email."
BENIGN_READ_ONLY = "The draft is ready for your review."
MIXED_VERIFIED_SEND = (
    "I've updated item 381 in the quote table. I sent the email.")


@contextmanager
def _scratch_world(monkeypatch, tmp_path):
    """Scratch SQLite world + scratch data/memory roots.

    ``TESTING=1`` is already forced by tests/conftest.py before core imports;
    the engine here is an in-memory scratch store that both the FastAPI
    dependency and ``core.database.get_db_session`` resolve to. The live dev
    DB is never reachable.
    """
    import core.database as db_module

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    @contextmanager
    def get_db_session():
        db = Session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", Session)
    monkeypatch.setattr(db_module, "get_db_session", get_db_session)
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LANCEDB_URI", str(tmp_path / "memory"))
    monkeypatch.setenv("ATOM_CHAT_STREAMING", "true")
    # The M3 operator gate is explicit: every test sets it itself.
    monkeypatch.delenv("CHAT_FINALIZATION_M3", raising=False)
    monkeypatch.delenv("CHAT_FINALIZATION_M1", raising=False)
    monkeypatch.delenv("CHAT_FINALIZATION_M2", raising=False)
    try:
        yield SimpleNamespace(Session=Session, engine=engine, get_db=get_db)
    finally:
        engine.dispose()


@pytest.fixture()
def world(monkeypatch, tmp_path):
    with _scratch_world(monkeypatch, tmp_path) as scratch:
        yield scratch


@pytest.fixture()
def app(world):
    application = FastAPI()
    application.include_router(cr.router)
    application.dependency_overrides[cr.get_db] = world.get_db
    return application


def _seed_user(world) -> tuple[User, str]:
    user_id = f"user-{uuid.uuid4().hex[:10]}"
    user = User(
        id=user_id,
        tenant_id="default",
        email=f"{user_id}@test.example.com",
        hashed_password="x",
        first_name="M3",
        last_name="Contract",
        role="member",
        status="active",
        workspace_id="default",
        is_active=True,
    )
    with world.Session() as db:
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(
            {"sub": user.id, "type": "access"}, user=user)
    return user, token


def _seed_owned_session(world, user: User) -> None:
    """Persist the owned ``ChatSession`` row the real admission producer writes.

    ``_install_orchestrator`` doubles only the in-memory session projection
    (``_get_or_create_session``) plus the external model transport. In the
    served boundary that producer also persists a durable ``ChatSession`` row
    through ``ChatSessionManager.create_session`` BEFORE the turn's transcript
    write. Without that row the write-time owned-session guard correctly
    refuses the append (``CHAT_SESSION_UNVERIFIED``) — so the fixture must
    materialise the same row, not bypass the guard.

    This is faithful fixture setup, not an authority substitute: the writer
    still re-reads this row, the actor and the admission snapshot and fences
    them inside its own transaction; any mismatch still refuses.
    """
    with world.Session() as db:
        db.add(ChatSession(
            id=SESSION_ID,
            user_id=user.id,
            metadata_json={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            message_count=0,
        ))
        db.commit()


class _FakeLLM:
    """Doubles ONLY the external model outputs.

    ``stream_completion`` is the real reply leg's streaming call; the test
    asserts it runs exactly once. ``on_stream`` fires with the turn's real
    ``execution_id`` before any token is yielded, which lets a test seed the
    canvas audit row that the REAL receipt renderer/readback must verify.
    """

    def __init__(self, stream_text, *, nonstream_text=None, on_stream=None):
        self.stream_text = stream_text
        self.nonstream_text = (
            stream_text if nonstream_text is None else nonstream_text)
        self.on_stream = on_stream
        self.stream_calls = []
        self.generate_calls = []
        self.handler = MagicMock()
        self.handler.analyze_query_complexity.return_value = (
            QueryComplexity.SIMPLE)
        self.handler.get_optimal_provider = AsyncMock(
            return_value=("scripted", "scripted-model"))
        self.handler.get_fallback_routes.return_value = []
        self.handler._last_used_provider = "scripted"
        self.handler._last_used_model = "scripted-model"

    async def stream_completion(self, **kwargs):
        self.stream_calls.append(kwargs)
        if self.on_stream is not None:
            self.on_stream(kwargs.get("execution_id"))
        # Chunk on word-ish boundaries so the incremental M3 gate actually
        # sees the claim before close.
        text = self.stream_text
        chunks = []
        cursor = 0
        for part in text.split(" "):
            end = cursor + len(part) + 1
            chunks.append(text[cursor:end])
            cursor = end
        for chunk in chunks:
            if chunk:
                yield chunk

    async def generate_completion(self, **kwargs):
        self.generate_calls.append(kwargs)
        return {
            "success": True,
            "content": self.nonstream_text,
            "model": "scripted-model",
            "provider": "scripted",
        }


def _session():
    session = {"id": SESSION_ID, "history": []}
    return session


def _canvas_context():
    return {
        "canvas_id": CANVAS_ID,
        "canvas_type": "email",
        "title": "Quote draft",
        "content": {
            "to": "customer@example.com",
            "subject": "Quote",
            "body": "| item | price |\n|---|---|\n| 381 | $8,880.00 |",
        },
    }


def _install_orchestrator(monkeypatch, llm, *, session=None):
    import integrations.chat_orchestrator as co

    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    orch.tenant_id = "default"
    orch.session_manager = None
    orch._cancelled_sessions = set()
    orch._budget_exceeded_runs = set()
    orch._turn_agent_id = None
    orch.llm_service = llm

    session = _session() if session is None else session
    canvas = _canvas_context()

    monkeypatch.setattr(cr, "chat_orchestrator", orch)

    async def _interpret(message_, session_=None, history=None,
                         context=None, **kw):
        return {
            "schema": "turn-interpretation-1", "request_id": "",
            "origin": "llm:test-model", "unresolved_reason": "",
            "message": message_, "actions": [], "subjects": [],
            "sources": [], "requested_fields": [], "output_format": "",
            "constraints": [], "scope_change": "replace", "confidence": 0.9,
            "deterministic_decision": None,
        }

    async def _assemble(**kwargs):
        return ""

    async def _plan_ce(*a, **k):
        class _P:
            wants_edit = False
        return _P()

    async def _structured(llm_service, *, prompt, response_model,
                          system_instruction, **_kw):
        from core.chat_tool_planner import ToolPlan

        return ToolPlan(use_tool=False, service=None, intent="search",
                        query="", reason="conversation turn")

    async def _resolve_canvas(context_, user_id_=None):
        # The REAL resolver only returns a canvas when the request carries
        # one; keep that shape so the non-canvas control is genuine.
        if not isinstance(context_, dict) or not (
                context_.get("canvas_id") or context_.get("canvas")):
            return None
        return canvas

    monkeypatch.setattr(orch, "_get_or_create_session",
                        lambda *a, **k: session)
    monkeypatch.setattr(orch, "_resolve_canvas_ctx", _resolve_canvas)
    monkeypatch.setattr(orch, "_record_chat_step", AsyncMock())
    monkeypatch.setattr(orch, "_emit_agent_status", AsyncMock())
    monkeypatch.setattr(orch, "_load_conversation_mail_handles",
                        lambda *a, **k: ([], []))
    monkeypatch.setattr(orch, "_route_to_features",
                        AsyncMock(return_value={}))
    monkeypatch.setattr(
        "core.memory_context_assembler.assemble_memory_context", _assemble)
    monkeypatch.setattr(
        "core.memory_context_assembler.assembly_enabled",
        lambda *a, **k: False)
    monkeypatch.setattr(
        "core.turn_decision.interpret_turn_request", _interpret)
    monkeypatch.setattr(
        "core.chat_mini_app_authoring.try_handle", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "core.chat_tool_planner._provenance_menu", AsyncMock(return_value=""))
    monkeypatch.setattr(
        "integrations.chat_orchestrator._verbatim_mail_evidence",
        AsyncMock(return_value=[]))
    monkeypatch.setattr(
        "integrations.chat_orchestrator._begin_task_edit",
        lambda *a, **k: {"status": "legacy"})
    monkeypatch.setattr(
        "core.chat_canvas_editor.plan_canvas_edit", _plan_ce)
    monkeypatch.setattr(
        "core.student_learning_service.get_agent_lessons",
        lambda *a, **k: [])
    monkeypatch.setattr(
        "core.chat_tool_planner._structured_with_fallback", _structured)
    return orch


@pytest.fixture()
def ws_capture(monkeypatch):
    events = []

    async def _broadcast(channel, message):
        events.append((channel, message))

    import core.websockets as websockets_module

    monkeypatch.setattr(websockets_module.manager, "broadcast", _broadcast)
    return events


def _post(client, token, user_id, message, *, context=None):
    return client.post(
        "/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": message,
            "user_id": user_id,
            "session_id": SESSION_ID,
            "context": context or {"canvas_id": CANVAS_ID},
        },
    )


def _durable_assistant(world) -> str:
    with world.Session() as db:
        row = (
            db.query(ChatMessage)
            .filter(ChatMessage.role == "assistant")
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .first()
        )
        return str(row.content) if row is not None else ""


def _ws_payloads(events, event_type):
    return [
        message.get("data") or {}
        for _channel, message in events
        if isinstance(message, dict) and message.get("type") == event_type
    ]


def _streamed_tokens(events) -> str:
    return "".join(str(p.get("delta") or "") for p in _ws_payloads(
        events, "chat_token"))


def _done_content(events) -> str:
    done = _ws_payloads(events, "chat_token_done")
    assert done, "chat_token_done must be emitted by the stream close"
    return str(done[-1].get("content") or "")


def _seed_verified_canvas(world, user_id, execution_id):
    """A REAL recorded operation whose postconditions hold on the served
    revision — the same rows the canvas edit lane writes."""
    from core.models import Canvas, CanvasAudit

    body = "| item | price |\n|---|---|\n| 381 | $8,880.00 |"
    content = {"to": "customer@example.com", "subject": "Quote", "body": body}
    with world.Session() as db:
        db.add(Canvas(
            id=CANVAS_ID, tenant_id="default", created_by=user_id,
            name="Quote draft", content=content,
        ))
        db.add(CanvasAudit(
            id=f"audit-{uuid.uuid4().hex[:10]}",
            canvas_id=CANVAS_ID,
            tenant_id="default",
            session_id=SESSION_ID,
            action_type="update",
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            details_json={
                "operation_id": execution_id,
                "content": content,
                "review_status": "accepted",
                "postconditions": [{
                    "entity_id": "381",
                    "field": "price",
                    "expected": {"raw_value": "$8,880.00"},
                }],
            },
        ))
        db.commit()


@pytest.fixture()
def user_token(world):
    user, token = _seed_user(world)
    _seed_owned_session(world, user)
    return user, token


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def test_m3_on_streaming_valid_payload_unsupported_claim_is_canonical(
        client, world, ws_capture, user_token, monkeypatch):
    """M3=1, streaming, ORDINARY VALID payload.

    The read-only summary survives byte-for-byte; the unsupported send is
    removed; WS close, HTTP message and the durable assistant row all carry
    the SAME canonical text. This is the branch that used to bypass M3.
    """
    user, token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    llm = _FakeLLM(SUMMARY_PLUS_UNSUPPORTED_SEND)
    orch = _install_orchestrator(monkeypatch, llm)

    canonical_calls = []
    real_canonical = orch._m3_canonical_delivery_text

    async def _spy(*args, **kwargs):
        result = await real_canonical(*args, **kwargs)
        canonical_calls.append((args, result))
        return result

    monkeypatch.setattr(orch, "_m3_canonical_delivery_text", _spy)

    resp = _post(client, token, user.id, READ_ONLY_ASK)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(llm.stream_calls) == 1, "the real streaming reply leg must run once"
    assert canonical_calls, "the canonical M3 boundary must actually be invoked"

    http_message = str(body["message"])
    durable = _durable_assistant(world)
    done = _done_content(ws_capture)
    streamed = _streamed_tokens(ws_capture)

    assert "I sent the email." not in http_message
    assert "I sent the email." not in durable
    assert "I sent the email." not in done
    assert "I sent the email." not in streamed
    assert "The draft is ready for your review." in http_message
    assert "The draft is ready for your review." in durable
    assert "The draft is ready for your review." in done

    # ONE text for every sink.
    assert http_message == durable == done
    # KNOWN LIMITATION (root trace 2026-11-17): these synthetic canvas
    # turns resolve `success=False / outcome=unconfirmed` even for the
    # benign twin, because the durable outcome resolver sees a read-only
    # canvas turn with no recorded operation. That is NOT a claim-specific
    # error and NOT a statement about normal model quality — do not read it
    # as the M3 gate failing, and do not "fix" it by asserting success.
    assert body["model"] == "scripted-model"
    assert body["provider"] == "scripted"


def test_m3_on_streaming_only_unsupported_claim_gets_honest_notice(
        client, world, ws_capture, user_token, monkeypatch):
    """Only the unsupported claim: a non-empty honest notice, never the raw
    hallucination and never an empty reply."""
    user, token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    llm = _FakeLLM(ONLY_UNSUPPORTED_SEND)
    _install_orchestrator(monkeypatch, llm)

    resp = _post(client, token, user.id, READ_ONLY_ASK)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    http_message = str(body["message"])
    durable = _durable_assistant(world)
    done = _done_content(ws_capture)

    assert "I sent the email." not in http_message
    assert "I sent the email." not in durable
    assert "I sent the email." not in done
    assert http_message.strip()
    assert "Unverified" in http_message
    assert http_message == durable == done
    assert len(llm.stream_calls) == 1


def test_m3_on_streaming_mixed_verified_receipt_keeps_one_section(
        client, world, ws_capture, user_token, monkeypatch):
    """A verified canvas receipt beside an unsupported send: the send is
    stripped and the ONE exact verified section survives on every sink."""
    user, token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    llm = _FakeLLM(
        MIXED_VERIFIED_SEND,
        on_stream=lambda execution_id: _seed_verified_canvas(
            world, user.id, execution_id))
    _install_orchestrator(monkeypatch, llm)

    resp = _post(client, token, user.id, READ_ONLY_ASK)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    http_message = str(body["message"])
    durable = _durable_assistant(world)
    done = _done_content(ws_capture)

    for text in (http_message, durable, done):
        assert "I sent the email." not in text
        assert text.count("Verified on the canvas as served") == 1, text
        assert "Verified on the canvas as served: 381 — price." in text
    assert http_message == durable == done
    assert "Review status: accepted." in http_message


def test_m3_on_streaming_benign_read_only_is_byte_unchanged(
        client, world, ws_capture, user_token, monkeypatch):
    user, token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    llm = _FakeLLM(BENIGN_READ_ONLY)
    _install_orchestrator(monkeypatch, llm)

    resp = _post(client, token, user.id, READ_ONLY_ASK)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["message"] == BENIGN_READ_ONLY
    assert _durable_assistant(world) == BENIGN_READ_ONLY
    assert _done_content(ws_capture) == BENIGN_READ_ONLY
    assert len(llm.stream_calls) == 1


def test_m3_off_streaming_legacy_compatibility_controls(
        client, world, ws_capture, user_token, monkeypatch):
    """Flag OFF: the legacy behavior is untouched (the unsupported send still
    survives — the frozen legacy guard is not M3)."""
    user, token = user_token
    monkeypatch.delenv("CHAT_FINALIZATION_M3", raising=False)
    llm = _FakeLLM(SUMMARY_PLUS_UNSUPPORTED_SEND)
    _install_orchestrator(monkeypatch, llm)

    resp = _post(client, token, user.id, READ_ONLY_ASK)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["message"] == SUMMARY_PLUS_UNSUPPORTED_SEND
    assert _durable_assistant(world) == SUMMARY_PLUS_UNSUPPORTED_SEND
    assert len(llm.stream_calls) == 1
    assert llm.generate_calls == []


def test_m3_on_nonstream_same_canonical_contract(
        client, world, ws_capture, user_token, monkeypatch):
    """Non-streaming M3=1 applies the SAME canonical guard after the legacy
    correction: HTTP/durable carry the guarded text, no extra LLM call."""
    user, token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    monkeypatch.setenv("ATOM_CHAT_STREAMING", "false")
    llm = _FakeLLM(
        SUMMARY_PLUS_UNSUPPORTED_SEND,
        nonstream_text=SUMMARY_PLUS_UNSUPPORTED_SEND)
    orch = _install_orchestrator(monkeypatch, llm)

    canonical_calls = []
    real_canonical = orch._m3_canonical_delivery_text

    async def _spy(*args, **kwargs):
        result = await real_canonical(*args, **kwargs)
        canonical_calls.append((args, result))
        return result

    monkeypatch.setattr(orch, "_m3_canonical_delivery_text", _spy)

    resp = _post(client, token, user.id, READ_ONLY_ASK)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert llm.stream_calls == [], "streaming leg must stay off in this control"
    assert len(llm.generate_calls) == 1, "exactly one generation, no extra call"
    # FULL MESSAGES / USAGE UNCHANGED: the call carries the complete message
    # list, and the turn made no additional model call.
    _messages = llm.generate_calls[0].get("messages") or []
    assert isinstance(_messages, list) and _messages
    assert all(isinstance(m.get("role"), str) for m in _messages)
    assert canonical_calls, "non-streaming M3 must invoke the canonical boundary"

    http_message = str(body["message"])
    durable = _durable_assistant(world)
    assert "I sent the email." not in http_message
    assert "I sent the email." not in durable
    assert "The draft is ready for your review." in http_message
    assert http_message == durable


def test_m3_on_unavailable_validation_never_releases_raw_claim(
        client, world, ws_capture, user_token, monkeypatch):
    """Guard fault: fail closed with an honest notice; the raw withheld claim
    never reaches WS close, HTTP or the durable row."""
    user, token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    llm = _FakeLLM(SUMMARY_PLUS_UNSUPPORTED_SEND)
    orch = _install_orchestrator(monkeypatch, llm)

    from integrations.chat_orchestrator import ChatOrchestrator

    monkeypatch.setattr(
        ChatOrchestrator, "_canvas_claim_correction",
        AsyncMock(side_effect=RuntimeError("guard unavailable")))
    monkeypatch.setattr(orch, "_m3_canonical_delivery_text",
                        ChatOrchestrator._m3_canonical_delivery_text)

    resp = _post(client, token, user.id, READ_ONLY_ASK)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    http_message = str(body["message"])
    durable = _durable_assistant(world)
    done = _done_content(ws_capture)

    for text in (http_message, durable, done):
        assert "I sent the email." not in text
        assert "Unverified" in text
    assert http_message == durable == done


@pytest.mark.parametrize("withheld", [None, "", "   ", "unreleased-span"])
@pytest.mark.asyncio
async def test_m3_unavailable_validation_never_releases_known_claim(
        monkeypatch, withheld):
    """ROOT COUNTER (2026-11-17): an explicit EMPTY withheld string must not
    disable the frozen-claim-shape check.

    Empty ``withheld`` means "no CURRENT unreleased span", not "the whole
    raw buffer was validated". The incremental gate only sees its current
    window, so a claim split across already-released chunks can leave
    ``withheld == ""`` while the full raw buffer still carries a frozen
    claim. An unavailable receipt read must then return the honest notice,
    never the raw claim and never "unchanged".
    """
    from integrations.chat_orchestrator import ChatOrchestrator

    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    monkeypatch.setattr(
        ChatOrchestrator, "_canvas_claim_correction",
        AsyncMock(side_effect=OSError(
            "synthetic unavailable receipt read")))

    text, status = await ChatOrchestrator._m3_canonical_delivery_text(
        "I updated the draft.",
        {"canvas_id": "synthetic"}, "session", "user", False,
        execution_id="execution", withheld=withheld,
    )

    assert status == "unavailable", (withheld, text, status)
    assert "I updated the draft." not in text
    assert "Unverified" in text


@pytest.mark.parametrize("withheld", [None, "", "   "])
@pytest.mark.asyncio
async def test_m3_unavailable_validation_keeps_benign_text(
        monkeypatch, withheld):
    """A benign direct reply with no claim shape is still delivered
    unchanged when the receipt read is unavailable."""
    from integrations.chat_orchestrator import ChatOrchestrator

    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    monkeypatch.setattr(
        ChatOrchestrator, "_canvas_claim_correction",
        AsyncMock(side_effect=OSError(
            "synthetic unavailable receipt read")))
    benign = "The draft is ready for your review."

    text, status = await ChatOrchestrator._m3_canonical_delivery_text(
        benign, {"canvas_id": "synthetic"}, "session", "user", False,
        execution_id="execution", withheld=withheld,
    )

    assert (text, status) == (benign, "unchanged")


@pytest.mark.asyncio
async def test_m3_off_is_not_affected(monkeypatch):
    """M3 OFF returns before any validation (the guard must not be called)."""
    from integrations.chat_orchestrator import ChatOrchestrator

    claim = "I updated the draft."
    monkeypatch.delenv("CHAT_FINALIZATION_M3", raising=False)
    monkeypatch.setattr(
        ChatOrchestrator, "_canvas_claim_correction",
        AsyncMock(side_effect=OSError("must not be called")))

    text, status = await ChatOrchestrator._m3_canonical_delivery_text(
        claim, {"canvas_id": "synthetic"}, "session", "user", False,
        execution_id="execution", withheld="",
    )
    assert (text, status) == (claim, "off")


@pytest.mark.asyncio
async def test_m3_normal_noncanvas_turn_is_unchanged(monkeypatch):
    """A normal non-canvas turn has no operation outcome and is unchanged."""
    from integrations.chat_orchestrator import ChatOrchestrator

    claim = "I updated the draft."
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")

    text, status = await ChatOrchestrator._m3_canonical_delivery_text(
        claim, None, "session", "user", False,
        execution_id="execution", withheld="",
    )
    assert (text, status) == (claim, "unchanged")


def test_m3_on_stream_empty_withheld_unavailable_guard_does_not_release_claim(
        client, world, ws_capture, user_token, monkeypatch):
    """PUBLIC STREAM FAULT CONTROL: with M3=1, the claim is split across
    already-released chunks so the close receives ``withheld == ""`` and the
    original raw buffer still contains the frozen claim. The final receipt
    read is unavailable. WS close, HTTP and the durable row must not
    reintroduce that raw claim; they must carry the truthful non-empty
    unverified notice.

    The spy proves the stream-close call really saw the EMPTY span — this is
    the exact root counter, not an inferred internal state.
    """
    user, token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    claim = "I updated the draft."
    llm = _FakeLLM(claim)
    _install_orchestrator(monkeypatch, llm)

    from integrations.chat_orchestrator import ChatOrchestrator

    seen_withheld = []
    real_canonical = ChatOrchestrator._m3_canonical_delivery_text

    async def _spy(content, *args, **kwargs):
        if "withheld" in kwargs:
            seen_withheld.append(kwargs["withheld"])
        return await real_canonical(content, *args, **kwargs)

    monkeypatch.setattr(
        ChatOrchestrator, "_m3_canonical_delivery_text",
        staticmethod(_spy))
    monkeypatch.setattr(
        ChatOrchestrator, "_canvas_claim_correction",
        AsyncMock(side_effect=OSError(
            "synthetic unavailable receipt read")))

    resp = _post(client, token, user.id, READ_ONLY_ASK)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert seen_withheld and seen_withheld[0] == "", (
        "the stream-close boundary must receive the empty withheld span")
    assert len(llm.stream_calls) == 1

    http_message = str(body["message"])
    durable = _durable_assistant(world)
    done = _done_content(ws_capture)

    for text in (http_message, durable, done):
        assert claim not in text
        assert "Unverified" in text
        assert text.strip()
    assert http_message == durable == done
    # NOTE: the incremental legacy gate can release a frozen claim that is
    # split across already-released chunks (pre-existing limitation, NOT
    # this repair). The contract under test is that the FINAL carriers do
    # not reintroduce it; no assertion is made about the mid-stream delta.


def test_m3_on_noncanvas_turn_is_untouched(
        client, world, ws_capture, user_token, monkeypatch):
    """No canvas operation outcome exists, so M3 has no boundary: the reply
    is delivered unchanged."""
    user, token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    llm = _FakeLLM(SUMMARY_PLUS_UNSUPPORTED_SEND)
    _install_orchestrator(monkeypatch, llm)

    resp = client.post(
        "/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": READ_ONLY_ASK, "user_id": user.id,
              "session_id": SESSION_ID, "context": {}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["message"] == SUMMARY_PLUS_UNSUPPORTED_SEND
    assert _durable_assistant(world) == SUMMARY_PLUS_UNSUPPORTED_SEND


def test_m3_on_protocol_rejected_stream_still_does_not_deliver_raw_claim(
        client, world, ws_capture, user_token, monkeypatch):
    """Protocol rejection keeps its existing handling; a malformed streamed
    payload never becomes delivered text just because it is truthy."""
    user, token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    llm = _FakeLLM(
        "I sent the email. <tool_call>{\"name\": \"send\"}</tool_call>",
        nonstream_text="The draft is ready for your review.",
    )
    _install_orchestrator(monkeypatch, llm)

    resp = _post(client, token, user.id, READ_ONLY_ASK)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    http_message = str(body["message"])
    durable = _durable_assistant(world)
    done = _done_content(ws_capture)

    assert "I sent the email." not in http_message
    assert "I sent the email." not in durable
    assert "I sent the email." not in done
    assert "<tool_call>" not in http_message
    assert "<tool_call>" not in done


def test_m3_on_structured_payload_is_delivered_unchanged(
        client, world, ws_capture, user_token, monkeypatch):
    """A certified structured payload is not ordinary prose: the existing
    restore path still owns it and the M3 boundary leaves it byte-identical
    (no workflow claim shape, no rewrite)."""
    user, token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    monkeypatch.setenv("ATOM_CHAT_STREAMING", "false")
    structured = (
        "Assessment\n\n```review\n{\"subjects\": [\"draft\"], "
        "\"decision\": \"accept\"}\n```")
    llm = _FakeLLM(structured, nonstream_text=structured)
    llm.generate_payload = {
        "success": True,
        "content": structured,
        "model": "scripted-model",
        "provider": "scripted",
        "structured_review": True,
    }

    async def _generate(**kwargs):
        llm.generate_calls.append(kwargs)
        return dict(llm.generate_payload)

    monkeypatch.setattr(llm, "generate_completion", _generate)
    _install_orchestrator(monkeypatch, llm)

    resp = _post(client, token, user.id, READ_ONLY_ASK)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["message"] == structured
    assert _durable_assistant(world) == structured
    assert len(llm.generate_calls) == 1


@pytest.mark.asyncio
async def test_m3_canonical_boundary_is_idempotent_for_rendered_section(
        world, user_token, monkeypatch):
    """A later guard may append deterministic content to canonical text.
    Re-entering the boundary must not produce a second verified section."""
    user, _token = user_token
    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    _seed_verified_canvas(world, user.id, "exec-idem")

    from integrations.chat_orchestrator import ChatOrchestrator

    first, status = await ChatOrchestrator._m3_canonical_delivery_text(
        "I've updated item 381 in the quote table.",
        {"canvas_id": CANVAS_ID}, SESSION_ID, user.id, False,
        execution_id="exec-idem",
    )
    assert status == "reconciled"
    assert first.count("Operation status:") == 1

    second, status = await ChatOrchestrator._m3_canonical_delivery_text(
        first + "\n\nCompared with the approved record.",
        {"canvas_id": CANVAS_ID}, SESSION_ID, user.id, False,
        execution_id="exec-idem",
    )
    assert status == "unchanged", "a re-entered canonical text is safe as-is"
    assert second.count("Operation status:") == 1
    assert second.count("Verified on the canvas as served") == 1
    assert second.endswith("Compared with the approved record.")


@pytest.mark.asyncio
async def test_m3_on_noop_and_none_semantics_preserved(monkeypatch):
    """Direct contract for None/empty/no-op: M3 never invents a notice for
    an empty reply and never changes a benign canvas-free text."""
    from integrations.chat_orchestrator import ChatOrchestrator

    monkeypatch.setenv("CHAT_FINALIZATION_M3", "1")
    empty = await ChatOrchestrator._m3_canonical_delivery_text(
        "", {"canvas_id": CANVAS_ID}, SESSION_ID, "u", False,
        execution_id="e")
    none_text = await ChatOrchestrator._m3_canonical_delivery_text(
        None, {"canvas_id": CANVAS_ID}, SESSION_ID, "u", False,
        execution_id="e")
    benign = await ChatOrchestrator._m3_canonical_delivery_text(
        "The draft is ready.", None, SESSION_ID, "u", False,
        execution_id="e")
    assert empty == ("", "unchanged")
    assert none_text == ("", "unchanged")
    assert benign == ("The draft is ready.", "unchanged")
