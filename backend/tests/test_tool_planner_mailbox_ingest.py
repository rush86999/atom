"""Mailbox on-demand ingest INTENT in the live-evidence tool planner.

The canvas co-editor and the chat lane both run their live-data lookup through
``core.chat_tool_planner``. This intent is what lets either of them say "that
content is not in memory — fetch it from the mailbox and add it" instead of
telling the user an attachment/image is inaccessible.

Contract under test:
  - an ``ingest`` plan on a mailbox service calls the pipeline's on-demand
    single-message ingest (body + attachments, images OCR'd) and returns the
    freshly indexed evidence plus a memory read-back;
  - idempotency surfaces as "already in memory" (the pipeline short-circuits);
  - the ``email_attachment`` autonomy topic still gates the write;
  - the kill switch disables the leg entirely;
  - ``plan_tool_use`` does not downgrade a legitimately-planned ``ingest``
    intent on a mailbox service back to ``search``.
"""

import os

os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, patch

import pytest


def _plan(service="outlook", intent="ingest", query="Chandrakant quote lathe"):
    from core.chat_tool_planner import ToolPlan

    return ToolPlan(use_tool=True, service=service, intent=intent, query=query)


@pytest.fixture
def approve_gate():
    import tools.email_attachment_tool as attachment_tool_mod

    with patch.object(attachment_tool_mod, "gate_for_topic") as fake_gate:
        fake_gate.return_value = {"outcome": "execute", "reason": "test gate"}
        yield fake_gate


@pytest.fixture
def memory_hit():
    with patch(
        "core.chat_tool_planner._memory_search_block",
        new=AsyncMock(return_value="MEMORY HIT: BS-460GB bandsaw photo"),
    ):
        yield


@pytest.mark.asyncio
async def test_ingest_intent_pulls_message_into_memory(approve_gate, memory_hit):
    from core.chat_tool_planner import execute_tool_plan

    with patch(
        "core.chat_tool_planner._resolve_mailbox_message_ids",
        new=AsyncMock(return_value=["graph-msg-1"]),
    ), patch(
        "integrations.atom_communication_ingestion_pipeline.ingestion_pipeline.ingest_email_on_demand",
        new=AsyncMock(
            return_value={"status": "ingested", "subject": "RFQ - Lathe", "attachments": 2}
        ),
    ) as ingest:
        block = await execute_tool_plan(
            _plan(), user_id="u-1", context={"agent_id": "agent-9"}
        )

    assert block is not None
    assert "INGESTED" in block
    assert "RFQ - Lathe" in block
    assert "MEMORY HIT" in block
    ingest.assert_awaited_once_with("outlook", "u-1", "graph-msg-1")


@pytest.mark.asyncio
async def test_ingest_intent_reports_already_in_memory(approve_gate, memory_hit):
    from core.chat_tool_planner import execute_tool_plan

    with patch(
        "core.chat_tool_planner._resolve_mailbox_message_ids",
        new=AsyncMock(return_value=["g-1"]),
    ), patch(
        "integrations.atom_communication_ingestion_pipeline.ingestion_pipeline.ingest_email_on_demand",
        new=AsyncMock(return_value={"status": "already_ingested"}),
    ):
        block = await execute_tool_plan(_plan(), user_id="u-1")

    assert "already in memory" in block


@pytest.mark.asyncio
async def test_ingest_intent_with_no_matching_message_is_honest(approve_gate, memory_hit):
    from core.chat_tool_planner import execute_tool_plan

    with patch(
        "core.chat_tool_planner._resolve_mailbox_message_ids",
        new=AsyncMock(return_value=[]),
    ), patch(
        "integrations.atom_communication_ingestion_pipeline.ingestion_pipeline.ingest_email_on_demand",
        new=AsyncMock(),
    ) as ingest:
        block = await execute_tool_plan(_plan(), user_id="u-1")

    assert "no matching message" in block
    ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_intent_honors_pinned_approval(memory_hit):
    from core.chat_tool_planner import execute_tool_plan
    import tools.email_attachment_tool as attachment_tool_mod

    with patch.object(attachment_tool_mod, "gate_for_topic") as fake_gate, patch(
        "core.chat_tool_planner._resolve_mailbox_message_ids",
        new=AsyncMock(return_value=["g-1"]),
    ), patch(
        "integrations.atom_communication_ingestion_pipeline.ingestion_pipeline.ingest_email_on_demand",
        new=AsyncMock(),
    ) as ingest:
        fake_gate.return_value = {"outcome": "propose", "reason": "owner pinned"}
        block = await execute_tool_plan(_plan(), user_id="u-1")

    assert "needs owner approval" in block
    ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_intent_kill_switch(approve_gate, memory_hit, monkeypatch):
    from core.chat_tool_planner import execute_tool_plan

    monkeypatch.setattr(
        "core.chat_tool_planner._planner_ingest_enabled", lambda: False
    )
    with patch(
        "core.chat_tool_planner._resolve_mailbox_message_ids",
        new=AsyncMock(return_value=["g-1"]),
    ), patch(
        "integrations.atom_communication_ingestion_pipeline.ingestion_pipeline.ingest_email_on_demand",
        new=AsyncMock(),
    ) as ingest:
        block = await execute_tool_plan(_plan(), user_id="u-1")

    assert "disabled by configuration" in block
    ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_gmail_ingest_intent_uses_gmail_provider(approve_gate, memory_hit):
    from core.chat_tool_planner import execute_tool_plan

    with patch(
        "core.chat_tool_planner._resolve_mailbox_message_ids",
        new=AsyncMock(return_value=["gm-1"]),
    ), patch(
        "integrations.atom_communication_ingestion_pipeline.ingestion_pipeline.ingest_email_on_demand",
        new=AsyncMock(return_value={"status": "ingested", "attachments": 1}),
    ) as ingest:
        await execute_tool_plan(_plan(service="gmail"), user_id="u-1")

    ingest.assert_awaited_once_with("gmail", "u-1", "gm-1")


@pytest.mark.asyncio
async def test_plan_tool_use_keeps_ingest_intent_for_mailbox():
    """`ingest` is only valid for mailbox services — but when planned there it
    must not be silently downgraded to `search` (which is what the user was
    already doing when the content proved inaccessible)."""
    from core.chat_tool_planner import ToolPlan, plan_tool_use

    with patch(
        "core.chat_tool_planner.get_connected_services", return_value=["outlook"]
    ), patch(
        "core.chat_tool_planner._structured_with_fallback",
        new=AsyncMock(
            return_value=ToolPlan(
                use_tool=True,
                service="outlook",
                intent="ingest",
                query="Chandrakant lathe photo",
            )
        ),
    ):
        plan = await plan_tool_use("use the image from Chandrakant's quote email", [], "u-1", object())

    assert plan is not None
    assert plan.service == "outlook"
    assert plan.intent == "ingest"


@pytest.mark.asyncio
async def test_plan_tool_use_rejects_ingest_for_non_mailbox():
    from core.chat_tool_planner import ToolPlan, plan_tool_use

    with patch(
        "core.chat_tool_planner.get_connected_services", return_value=["google_drive"]
    ), patch(
        "core.chat_tool_planner._structured_with_fallback",
        new=AsyncMock(
            return_value=ToolPlan(
                use_tool=True, service="google_drive", intent="ingest", query="x"
            )
        ),
    ):
        plan = await plan_tool_use("ingest this file", [], "u-1", object())

    assert plan is not None
    assert plan.intent == "search"
