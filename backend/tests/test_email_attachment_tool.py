"""Agent email-attachment tools + governance wiring (Phase 4).

- tools/email_attachment_tool.py: gate signal, staging caps, attach-from-
  message, provenance-wrapped text reads.
- ToolRegistry: the six tools register with their intended complexity tiers.
"""

import base64
import os

os.environ.setdefault("TESTING", "1")

import contextlib
from unittest.mock import patch

import pytest

import tools.email_attachment_tool as tool_mod
from core.email_policy import UNTRUSTED_OPEN


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base

    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "staged"))
    eng = create_engine(f"sqlite:///{tmp_path}/canvas.db")
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng, expire_on_commit=False)
    with Session() as s:
        yield s


@pytest.fixture
def session_ctx(db_session):
    @contextlib.contextmanager
    def _ctx():
        yield db_session

    with patch("core.database.get_db_session", _ctx):
        yield db_session


@pytest.fixture
def canvas(session_ctx):
    from core.canvas_email_service import EmailCanvasService

    result = EmailCanvasService(session_ctx).create_email_canvas(
        user_id="u-1", subject="Thread", recipients=["mark@external.test"],
        agent_id=None,
    )
    assert result["success"]
    return result["canvas_id"]


@pytest.fixture
def auto_gate():
    """Mutating tools consult gate_for_topic; the test's hire doesn't exist
    in AgentRegistry, so the real gate proposes. Pin it to execute."""
    with patch.object(tool_mod, "gate_for_topic") as fake_gate:
        fake_gate.return_value = {
            "topic": "email_attachment",
            "mode": "auto_if_mature",
            "outcome": "execute",
            "reason": "test gate",
        }
        yield fake_gate


def _add_thread_message(session, canvas, attachments):
    from core.canvas_email_service import EmailCanvasService

    return EmailCanvasService(session).add_message_to_thread(
        canvas_id=canvas,
        user_id="u-1",
        from_email="supplier@corp.test",
        to_emails=["u-1@corp.test"],
        subject="Re: Thread",
        body="Here is the contract.",
        attachments=attachments,
    )


# ─── autonomy gate ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mutations_signal_needs_approval_when_pinned(session_ctx, canvas, monkeypatch):
    async def fake_remove(*a, **kw):
        return {"success": True}

    with patch.object(tool_mod, "gate_for_topic") as fake_gate, patch.object(
        tool_mod, "email_attachment_remove", new=fake_remove
    ):
        # owner pinned the topic to human_always
        fake_gate.return_value = {
            "outcome": "propose",
            "reason": "Owner requires approval",
            "topic": "email_attachment",
        }
        result = await tool_mod.email_attachment_stage_file(
            user_id="u-1", canvas_id=canvas,
            filename="summary.txt",
            content_b64=base64.b64encode(b"summary").decode(),
            agent_id="hire-1",
        )
    assert result["success"] is False
    assert result["needs_approval"] is True
    assert result["topic"] == "email_attachment"


@pytest.mark.asyncio
async def test_reads_skip_the_gate(session_ctx, canvas):
    """Reads (list/get_text) are level-1 tools — no propose gate."""
    with patch.object(tool_mod, "gate_for_topic") as fake_gate:
        result = await tool_mod.email_attachment_list(user_id="u-1", canvas_id=canvas)
    assert result["success"] is True
    fake_gate.assert_not_called()


# ─── stage_file ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stage_file_roundtrip_and_cap(session_ctx, canvas, auto_gate):
    staged = await tool_mod.email_attachment_stage_file(
        user_id="u-1", canvas_id=canvas,
        filename="summary.txt",
        content_b64=base64.b64encode(b"Q3 numbers").decode(),
        agent_id="hire-1",
    )
    assert staged["success"] is True
    staged_att = staged["attachments"][0]
    assert staged_att["origin"] == "staged"
    assert staged_att["added_by"]["actor"] == "agent"

    listed = await tool_mod.email_attachment_list(user_id="u-1", canvas_id=canvas)
    assert [a["attachment_id"] for a in listed["attachments"]] == [
        staged_att["attachment_id"]
    ]

    oversized = await tool_mod.email_attachment_stage_file(
        user_id="u-1", canvas_id=canvas,
        filename="big.txt",
        content_b64=base64.b64encode(b"x" * (tool_mod.AGENT_STAGE_FILE_MAX_BYTES + 1)).decode(),
    )
    assert oversized["success"] is False
    assert "staging cap" in oversized["error"]


@pytest.mark.asyncio
async def test_stage_file_rejects_disallowed_type(session_ctx, canvas, auto_gate):
    result = await tool_mod.email_attachment_stage_file(
        user_id="u-1", canvas_id=canvas,
        filename="payload.sh", content_b64=base64.b64encode(b"#!/bin/sh").decode(),
    )
    assert result["success"] is False


# ─── attach from thread message ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_attach_from_message_promotes_received_file(session_ctx, canvas, auto_gate):
    added = _add_thread_message(
        session_ctx, canvas,
        [{"attachment_id": "att-graph-1", "filename": "contract.pdf",
          "content_type": "application/pdf", "size": 12345}],
    )
    assert added["success"]
    message_id = added["message_id"]

    result = await tool_mod.email_attachment_attach(
        user_id="u-1", canvas_id=canvas,
        message_id=message_id, attachment_id="att-graph-1",
        agent_id="hire-1",
    )
    assert result["success"] is True
    assert result["attachment"]["origin"] == "received"
    assert result["attachment"]["message_id"] == message_id
    assert result["attachment"]["added_by"]["actor"] == "agent"

    # attaching twice is idempotent, not an error
    again = await tool_mod.email_attachment_attach(
        user_id="u-1", canvas_id=canvas,
        message_id=message_id, attachment_id="att-graph-1",
    )
    assert again["success"] is True
    assert again.get("already_attached") is True

    listed = await tool_mod.email_attachment_list(user_id="u-1", canvas_id=canvas)
    assert len(listed["attachments"]) == 1


@pytest.mark.asyncio
async def test_attach_from_message_unknown_attachment(session_ctx, canvas, auto_gate):
    added = _add_thread_message(session_ctx, canvas, [])
    result = await tool_mod.email_attachment_attach(
        user_id="u-1", canvas_id=canvas,
        message_id=added["message_id"], attachment_id="nope",
    )
    assert result["success"] is False
    assert "not found" in result["error"]


# ─── get_text ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_text_returns_provenance_wrapped_csv(session_ctx, canvas, auto_gate):
    staged = await tool_mod.email_attachment_stage_file(
        user_id="u-1", canvas_id=canvas,
        filename="numbers.csv",
        content_b64=base64.b64encode("acct,amount\nacme,120\n".encode()).decode(),
    )
    att = staged["attachments"][0]
    result = await tool_mod.email_attachment_get_text(
        user_id="u-1", canvas_id=canvas, attachment_id=att["attachment_id"],
    )
    assert result["success"] is True
    assert result["filename"] == "numbers.csv"
    # untrusted retrieved data rides in spotlight delimiters (CSV renders
    # as a table — assert on content, not layout)
    assert result["text"].startswith(UNTRUSTED_OPEN)
    assert "acme" in result["text"]


@pytest.mark.asyncio
async def test_get_text_binary_without_layer_suggests_ingest(session_ctx, canvas):
    from core.email_attachment_store import save_staged

    from core.canvas_email_service import EmailCanvasService

    rec = save_staged("u-1", canvas, "pic.png", b"\x89PNG-not-really", "image/png")
    svc = EmailCanvasService(session_ctx)
    svc.stage_attachments(
        canvas, "u-1",
        [{"filename": "pic.png", "content_bytes": b"\x89PNG", "content_type": "image/png"}],
    )
    listed = svc.list_attachments(canvas, "u-1")
    result = await tool_mod.email_attachment_get_text(
        user_id="u-1", canvas_id=canvas,
        attachment_id=listed["attachments"][-1]["attachment_id"],
    )
    assert result["success"] is False
    assert "email_attachment_ingest" in result["error"]


@pytest.mark.asyncio
async def test_remove_via_tool(session_ctx, canvas, auto_gate):
    staged = await tool_mod.email_attachment_stage_file(
        user_id="u-1", canvas_id=canvas,
        filename="a.pdf", content_b64=base64.b64encode(b"%PDF").decode(),
    )
    result = await tool_mod.email_attachment_remove(
        user_id="u-1", canvas_id=canvas,
        attachment_id=staged["attachments"][0]["attachment_id"],
    )
    assert result["success"] is True
    assert result["staged_deleted"] is True


# ─── registry wiring ─────────────────────────────────────────────────────────


def test_registry_registers_email_attachment_tools():
    from tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.initialize()
    for name, complexity in [
        ("email_attachment_list", 1),
        ("email_attachment_get_text", 1),
        ("email_attachment_stage_file", 2),
        ("email_attachment_attach", 2),
        ("email_attachment_remove", 2),
        ("email_attachment_ingest", 2),
    ]:
        meta = registry._tools.get(name)
        assert meta is not None, f"{name} missing from registry"
        assert meta.complexity == complexity


def test_governance_complexity_keys_present():
    from core.agent_governance_service import AgentGovernanceService

    svc = AgentGovernanceService.__new__(AgentGovernanceService)
    assert svc.ACTION_COMPLEXITY["email_attachment_read"] == 1
    assert svc.ACTION_COMPLEXITY["email_attachment_write"] == 2
    # exact-key resolution: the write key must not be shadowed by "read"
    assert (
        AgentGovernanceService.ACTION_COMPLEXITY.get("email_attachment_write") == 2
    )


def test_autonomy_topic_registered():
    from core.autonomy_policy import TOPICS, TOPIC_GATES, topics_for_canvas

    assert "email_attachment" in TOPICS
    assert TOPIC_GATES["email_attachment"]["governance_action"] == "email_attachment_write"
    assert "email_attachment" in topics_for_canvas("email")
