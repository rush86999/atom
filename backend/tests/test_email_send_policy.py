"""Release-wide draft-and-approval email gate."""
import pytest

from core.canvas_email_service import EmailCanvasService
from core.email_send_policy import disabled_result, live_email_send_disabled
import asyncio


def test_gate_is_off_by_default(monkeypatch):
    monkeypatch.delenv("ATOM_EMAIL_SEND_DISABLED", raising=False)
    assert live_email_send_disabled() is False


def test_gate_blocks_canvas_send_before_transport(monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_SEND_DISABLED", "1")
    result = asyncio.run(EmailCanvasService(db=None).send_email(
        canvas_id="",
        user_id="user-1",
        to_emails=["smoke@example.invalid"],
        subject="Blocked",
        body="No transport should be reached.",
    ))
    assert result["success"] is False
    assert result["provider_state"] == "not_sent"
    assert result["transport_attempted"] is False
    assert result["policy"] == "draft_and_approval_only"


def test_disabled_result_is_explicit():
    result = disabled_result()
    assert result["status"] == "blocked"
    assert result["provider_state"] == "not_sent"
    assert "disabled" in result["error"].lower()
