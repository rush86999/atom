"""Multi-turn regressions for canvas a1a13834; all stores/providers mocked."""
from unittest.mock import AsyncMock, patch

import pytest

import core.chat_tool_planner as planner
import integrations.chat_orchestrator as chat


HISTORY = {"history": [
    {"message": "search for this one: $ 5,350.00 - 10 % in stock"},
    {"message": "is WG-350DSAV in stock?"},
]}


def mail(content, subject="RFQ - Foot shear", sender="chandrakant@dealer.test"):
    return {"id": "source-1", "sender": sender, "recipient": "owner@dealer.test",
            "subject": subject, "content": content, "metadata": "",
            "timestamp": "2026-08-26T14:06:00"}


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch):
    monkeypatch.setattr(planner, "_comms_store_records", lambda: [])
    monkeypatch.setattr(planner, "_PEOPLE_INDEX", {})
    monkeypatch.setattr(planner, "_search_ingested_by_tokens",
                        lambda *a, **k: ["unrelated older bandsaw stock result"])


@pytest.mark.asyncio
async def test_current_phrase_beats_previous_model_number(monkeypatch):
    monkeypatch.setattr(planner, "_comms_store_records",
                        lambda: [mail("Put 25 percent only")])
    lines = await chat._verbatim_mail_evidence(
        "find the email that said: put 25 percent only", "u1", HISTORY)
    assert "Put 25 percent only" in "\n".join(lines)
    assert "bandsaw" not in "\n".join(lines)


@pytest.mark.asyncio
async def test_current_participant_beats_previous_model_number(monkeypatch):
    monkeypatch.setattr(planner, "_comms_store_records",
                        lambda: [mail("Foot shear list calculation: cost plus freight")])
    lines = await chat._verbatim_mail_evidence(
        "check the email thread chandrakant forwarded about foot shear list price",
        "u1", HISTORY)
    assert "cost plus freight" in "\n".join(lines)
    assert "bandsaw" not in "\n".join(lines)


@pytest.mark.asyncio
async def test_phrase_in_elided_middle_is_visible(monkeypatch):
    body = "intro " * 4000 + "Put 25 percent only" + " footer" * 4000
    monkeypatch.setattr(planner, "_comms_store_records", lambda: [mail(body)])
    lines = await chat._verbatim_mail_evidence(
        "find the email that said: put 25 percent only", "u1", {})
    assert "Put 25 percent only" in "\n".join(lines)


def test_phrase_matches_wrapped_and_nbsp_text(monkeypatch):
    row = mail("Put\n25\u00a0percent  only")
    monkeypatch.setattr(planner, "_comms_store_records", lambda: [row])
    assert planner._mail_contains_phrases(["put 25 percent only"]) == [row]


@pytest.mark.asyncio
async def test_missing_current_phrase_does_not_return_old_stock():
    lines = await chat._verbatim_mail_evidence(
        'find the email that said: never shipped the blue pump', "u1", HISTORY)
    assert lines == []


@pytest.mark.asyncio
async def test_retry_still_uses_previous_figure():
    lines = await chat._verbatim_mail_evidence("try again", "u1", HISTORY)
    assert lines == ["unrelated older bandsaw stock result"]


@pytest.mark.asyncio
async def test_failed_edit_planner_allows_search_without_action_dispatch():
    from core.chat_canvas_editor import CanvasPlanUnavailable, FreshDataResult
    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    session = {"id": "isolated", "history": []}
    canvas = {"canvas_id": "c1", "canvas_type": "email",
              "content": {"subject": "Draft", "body": "Unchanged"}}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=canvas)),
        patch.object(orch, "_refresh_canvas_from_store", new=AsyncMock(return_value=canvas)),
        patch.object(orch, "_heal_degenerate_canvas", new=AsyncMock(return_value=canvas)),
        patch.object(orch, "_start_chat_execution", return_value="e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch("core.chat_canvas_editor.fetch_fresh_data_section", new=AsyncMock(
            return_value=FreshDataResult(section="", needed=False, ok=True))),
        patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(
            side_effect=CanvasPlanUnavailable("provider down"))),
        patch("core.chat_canvas_editor.plan_canvas_action", new=AsyncMock()),
        patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock()) as edit,
        patch.object(orch, "_try_canvas_action", new=AsyncMock()) as action,
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()) as crm,
        patch.object(orch, "_route_to_features", new=AsyncMock()) as features,
        patch.object(orch, "_get_qwen_response", new=AsyncMock(return_value={
            "content": "Found the source email.", "model": "test", "provider": "test",
        })) as answer,
        patch.object(planner, "_provenance_menu", new=AsyncMock(return_value="")),
        patch.object(planner, "plan_tool_use", new=AsyncMock(return_value=planner.ToolPlan(
            use_tool=True, service="memory", intent="search", query="quoted price"))),
    ):
        result = await orch.process_chat_message(
            "u1", "search for this one: $ 5,350.00 - 10 % in stock",
            "isolated", context={"canvas_id": "c1", "agent_id": "a1"})
    assert result["message"] == "Found the source email."
    assert result["data"]["canvas_edit"]["updated"] is False
    from core.chat_canvas_editor import CanvasEvidenceStatus

    assert answer.await_args.kwargs["canvas_evidence_status"] is (
        CanvasEvidenceStatus.PLANNER_UNAVAILABLE)
    edit.assert_not_awaited()
    action.assert_not_awaited()
    crm.assert_not_awaited()
    features.assert_not_awaited()


@pytest.mark.parametrize("live", [None, "LIVE INVENTORY: stock_on_hand=0"])
def test_old_email_cannot_confirm_current_inventory(live):
    block = chat._compose_lookup_evidence(
        "is WG-350DSAV in stock?",
        planner.ToolPlan(use_tool=True, service="zoho_inventory", intent="search"),
        live, ["EMAIL September 11: WG-350DSAV in stock"],
    )
    assert "cannot establish current availability" in block
    assert "answer the question from it now" not in block
    if live:
        assert block.index(live) < block.index("EMAIL September 11")
    else:
        assert "could not complete" in block


def test_quoted_source_survives_failed_inventory_lookup():
    block = chat._compose_lookup_evidence(
        "search for this one: $ 5,350.00 - 10 % in stock",
        planner.ToolPlan(use_tool=True, service="zoho_inventory", intent="search"),
        None, ["EMAIL: $ 5,350.00 - 10 % in stock"],
    )
    assert "answer the question from it now" in block
    assert block.index("EMAIL:") < block.index("live zoho_inventory")
