"""Teach the agent to reply on an existing email thread (TDD).

Two contracts:
1. TEACHING lands at every tier: a human-taught lesson (/teach) or a
   commented chat rejection journals the rule into the operating agent's
   permanent lesson log status-independently (SUPERVISED/graduated hires
   included — the canvas real-time path already behaved this way).
2. The DIRECTION is executable on the chat/canvas send path:
   EmailCanvasService.send_email(thread_id=...) is a true threaded reply
   (Graph /reply with the composer's To/Cc/Subject as message overrides),
   and resolve_reply_recipients surfaces the conversationId so the
   composer can pass it back.

Zero network: Outlook is patched at the module boundary; DB is the shared
sqlite fixture pattern.
"""
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    from core.models import Base

    Base.metadata.create_all(bind=eng)
    Sess = sessionmaker(bind=eng, expire_on_commit=False)
    session = Sess()
    try:
        yield session
    finally:
        session.close()
        eng.dispose()
        os.unlink(path)


def _agent(db, agent_id="hire-9", status="supervised"):
    from core.models import AgentRegistry

    row = AgentRegistry(
        id=agent_id, name="Hire", category="sales", role="sales_assistant",
        type="worker", capabilities=[], module_path="x", class_name="X",
        status=status, confidence_score=0.6,
    )
    db.add(row)
    db.commit()
    return row


THREAD_RULE = "Always reply on the existing email thread, never start a new one"


# ─────────────────────────── 1. Teaching lands at every tier ────────────────

class TestJournalStandingLesson:
    def test_supervised_agent_receives_teacher_lesson(self, db):
        from core.student_learning_service import (
            get_agent_lessons,
            journal_standing_lesson,
        )

        _agent(db, status="supervised")
        assert journal_standing_lesson(
            db, "hire-9", THREAD_RULE, source="teacher", topic="email",
        ) is True
        lessons = get_agent_lessons(db, "hire-9")
        assert any(THREAD_RULE in str(l.get("lesson") or "") for l in lessons)

    def test_graduated_agent_receives_correction_lesson(self, db):
        from core.student_learning_service import (
            get_agent_lessons,
            journal_standing_lesson,
        )

        _agent(db, status="autonomous")
        assert journal_standing_lesson(db, "hire-9", THREAD_RULE) is True
        lessons = get_agent_lessons(db, "hire-9")
        assert any(THREAD_RULE in str(l.get("summary") or "") for l in lessons)

    def test_identical_lesson_does_not_stack(self, db):
        from core.student_learning_service import (
            get_agent_lessons,
            journal_standing_lesson,
        )

        _agent(db)
        assert journal_standing_lesson(db, "hire-9", THREAD_RULE) is True
        assert journal_standing_lesson(db, "hire-9", THREAD_RULE) is False
        assert len(get_agent_lessons(db, "hire-9")) == 1

    def test_missing_agent_is_a_noop(self, db):
        from core.student_learning_service import journal_standing_lesson

        assert journal_standing_lesson(db, "ghost", THREAD_RULE) is False


class TestTeachEndpointAnyTier:
    def _client(self, db):
        from fastapi import FastAPI

        from api.agent_onboarding_routes import router as onboarding_router
        from core.auth import get_current_user
        from core.database import get_db
        from core.models import User

        app = FastAPI()
        app.include_router(onboarding_router)
        app.dependency_overrides[get_current_user] = lambda: User(
            id="sup-1", email="sup@test.com", first_name="S", last_name="U",
            role="super_admin", status="active",
        )
        app.dependency_overrides[get_db] = lambda: db
        from fastapi.testclient import TestClient

        return TestClient(app)

    def test_teach_supervised_agent_journals_standing_guidance(self, db):
        _agent(db, status="supervised")
        resp = self._client(db).post(
            "/api/agents/hire-9/teach",
            json={"lesson": THREAD_RULE, "topic": "email"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "ok"
        assert body["data"]["mode"] == "standing_guidance"

        from core.student_learning_service import get_agent_lessons

        lessons = get_agent_lessons(db, "hire-9")
        assert any(THREAD_RULE in str(l.get("lesson") or "") for l in lessons)
        assert lessons[0]["source"] == "teacher"
        assert lessons[0]["topic"] == "email"


class TestChatTeachingCircuit:
    @pytest.mark.asyncio
    async def test_commented_rejection_reaches_operating_agent_any_tier(self, db):
        from core.exchange_example_service import _fire_teaching_circuit

        _agent(db, agent_id="hire-9", status="supervised")
        row = SimpleNamespace(
            id="ex-1", label="negative", source="explicit_thumbs",
            comment="never start a new thread", user_query="reply to Mark",
            conversation_id="conv-1", workspace_id="ws-1", agent_id="hire-9",
        )
        with patch("core.student_learning_service.auto_observe", AsyncMock()), \
             patch("core.agent_pedagogy.PedagogicalFramework"), \
             patch("core.database.SessionLocal", return_value=db):
            fired = _fire_teaching_circuit(
                {"agent_id": "hire-9", "user_query": "reply to Mark"}, row,
            )

        assert fired.get("operating_agent_lesson") is True
        from core.student_learning_service import get_agent_lessons

        lessons = get_agent_lessons(db, "hire-9")
        assert any("never start a new thread" in str(l.get("summary") or "") for l in lessons)

    @pytest.mark.asyncio
    async def test_row_without_agent_id_falls_back_to_pair(self, db):
        """Older callers pass rows without agent_id — the pair's agent_id
        (how capture_exchange populates the row) must be used instead."""
        from core.exchange_example_service import _fire_teaching_circuit

        _agent(db, agent_id="hire-9", status="autonomous")
        row = SimpleNamespace(
            id="ex-2", label="negative", source="explicit_thumbs",
            comment="wrong", user_query="q", conversation_id="conv-1",
            workspace_id="ws-1",
        )
        with patch("core.student_learning_service.auto_observe", AsyncMock()), \
             patch("core.agent_pedagogy.PedagogicalFramework"), \
             patch("core.database.SessionLocal", return_value=db):
            fired = _fire_teaching_circuit({"agent_id": "hire-9"}, row)

        assert fired.get("operating_agent_lesson") is True


# ─────────────────── 2. The direction is executable (canvas) ────────────────

def _outlook_mock(message_id="m-latest", reply_ok=True, conversation_id="conv-9"):
    svc = MagicMock()
    svc.get_latest_conversation_message_id = AsyncMock(return_value=message_id)
    svc.reply_to_email = AsyncMock(return_value=reply_ok)
    svc.send_email = AsyncMock(return_value={"id": "s1"})
    svc.last_send_error = {}
    return svc


class TestCanvasThreadReply:
    async def _send(self, db, outlook=None, **kwargs):
        from core.canvas_email_service import EmailCanvasService

        svc = EmailCanvasService(db)
        outlook = outlook or _outlook_mock()
        with patch("integrations.outlook_service.OutlookService", return_value=outlook):
            result = await svc.send_email(
                canvas_id="c1", user_id="u1",
                to_emails=["mark@example.com"],
                subject="Re: Quotation", body="Here it is.",
                **kwargs,
            )
        return result, outlook

    @pytest.mark.asyncio
    async def test_thread_id_sends_graph_reply_not_new_mail(self, db):
        result, outlook = await self._send(db, thread_id="conv-9")

        assert result["success"] is True
        assert result["reply_to_message_id"] == "m-latest"
        outlook.reply_to_email.assert_awaited_once()
        kwargs = outlook.reply_to_email.await_args.kwargs
        assert kwargs["message_id"] == "m-latest"
        assert kwargs["comment"] == "Here it is."
        # The composer's visible fields ride the message override.
        assert kwargs["to_recipients"] == ["mark@example.com"]
        assert kwargs["subject"] == "Re: Quotation"
        outlook.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_thread_fails_without_send(self, db):
        result, outlook = await self._send(
            db, outlook=_outlook_mock(message_id=None), thread_id="conv-404",
        )

        assert result["success"] is False
        assert result["status"] == "failed"
        outlook.reply_to_email.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_attachments_with_thread_are_refused_not_dropped(self, db):
        from unittest.mock import patch as _patch

        from core.canvas_email_service import EmailCanvasService

        svc = EmailCanvasService(db)
        with _patch("integrations.outlook_service.OutlookService", return_value=_outlook_mock()), \
             _patch.object(EmailCanvasService, "_resolve_send_attachments",
                           new=AsyncMock(return_value=[
                               {"filename": "q.pdf", "content_type": "application/pdf",
                                "content_bytes": b"x", "policy_text": "quote"}])):
            result = await svc.send_email(
                canvas_id="c1", user_id="u1", to_emails=["a@b.com"],
                subject="Re: q", body="b", thread_id="conv-9",
                attachment_ids=["att-1"],
            )
        assert result["success"] is False
        assert result["blocked_by"] == "email_policy"
        assert "attachment" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_standalone_send_still_uses_send_email(self, db):
        result, outlook = await self._send(db)

        assert result["success"] is True
        outlook.send_email.assert_awaited_once()
        outlook.reply_to_email.assert_not_awaited()


class TestResolveReplySurfacesThreadId:
    @pytest.mark.asyncio
    async def test_thread_match_returns_conversation_id(self, db):
        from core.canvas_email_service import EmailCanvasService

        svc = EmailCanvasService(db)
        outlook = MagicMock()
        outlook.search_emails = AsyncMock(return_value=[{
            "id": "m1", "subject": "RE: Quotation",
            "conversation_id": "conv-77",
            "from_field": {"emailAddress": {"address": "mark@example.com",
                                            "name": "Mark"}},
            "received_date_time": "2026-09-01T10:00:00Z",
        }])
        outlook.get_user_profile = AsyncMock(return_value={})
        with patch("integrations.outlook_service.OutlookService", return_value=outlook):
            result = await svc.resolve_reply_recipients("u1", "Re: Quotation")

        assert result["to"] is not None
        assert result["thread_id"] == "conv-77"

    @pytest.mark.asyncio
    async def test_mixed_thread_prefills_external_sender(self, db):
        """The same conversation often carries internal legs (colleague
        notes). Prefill must aim the reply at the newest OUTSIDE-the-org
        sender, never at an internal colleague (observed 2026-09-04)."""
        from core.canvas_email_service import EmailCanvasService

        svc = EmailCanvasService(db)
        outlook = MagicMock()
        outlook.search_emails = AsyncMock(return_value=[
            {
                "id": "m-internal", "subject": "RE: Quotation",
                "conversation_id": "conv-88",
                "from_field": {"emailAddress": {"address": "vipul@brennan.ca",
                                                "name": "Vipul"}},
                "received_date_time": "2026-09-02T17:33:17Z",
            },
            {
                "id": "m-external", "subject": "RE: Quotation",
                "conversation_id": "conv-88",
                "from_field": {"emailAddress": {"address": "jacob@customer.ca",
                                                "name": "Jacob"}},
                "received_date_time": "2026-09-02T17:08:35Z",
            },
        ])
        outlook.get_user_profile = AsyncMock(
            return_value={"mail": "rish@brennan.ca"}
        )
        with patch("integrations.outlook_service.OutlookService", return_value=outlook):
            result = await svc.resolve_reply_recipients("u1", "Re: Quotation")

        assert "jacob@customer.ca" in result["to"]
        assert result["thread_id"] == "conv-88"

    @pytest.mark.asyncio
    async def test_unknown_domain_keeps_newest_non_self_sender(self, db):
        """No own address resolvable → no domain filter — previous behavior
        (newest non-self sender) is preserved."""
        from core.canvas_email_service import EmailCanvasService

        svc = EmailCanvasService(db)
        outlook = MagicMock()
        outlook.search_emails = AsyncMock(return_value=[{
            "id": "m1", "subject": "RE: Quotation",
            "conversation_id": "conv-77",
            "from_field": {"emailAddress": {"address": "colleague@anywhere.com",
                                            "name": "Col"}},
            "received_date_time": "2026-09-01T10:00:00Z",
        }])
        outlook.get_user_profile = AsyncMock(return_value={})
        with patch("integrations.outlook_service.OutlookService", return_value=outlook):
            result = await svc.resolve_reply_recipients("u1", "Re: Quotation")

        assert "colleague@anywhere.com" in result["to"]
        assert result["thread_id"] == "conv-77"


class TestReplyOverridesPayload:
    @pytest.mark.asyncio
    async def test_reply_to_email_carries_message_overrides(self):
        from integrations.outlook_service import OutlookService

        svc = OutlookService()
        svc._make_graph_request = AsyncMock(return_value={})
        ok = await svc.reply_to_email(
            "u1", "m1", "Here it is.",
            reply_all=True,
            to_recipients=["mark@example.com"],
            cc_recipients=["sam@example.com"],
            subject="Re: Quotation",
        )
        assert ok is True
        args = svc._make_graph_request.await_args.args
        assert args[1] == "/me/messages/m1/replyAll"
        payload = args[3]
        assert payload["comment"] == "Here it is."
        assert payload["message"]["toRecipients"] == [
            {"emailAddress": {"address": "mark@example.com"}}]
        assert payload["message"]["ccRecipients"] == [
            {"emailAddress": {"address": "sam@example.com"}}]
        assert payload["message"]["subject"] == "Re: Quotation"


class TestPlanSchema:
    def test_action_plan_accepts_thread_fields(self):
        from core.chat_canvas_editor import CanvasActionPlan

        plan = CanvasActionPlan(
            wants_action=True, action="send_email", to="mark@example.com",
            thread_id="conv-9", reply_all=True,
        )
        assert plan.thread_id == "conv-9"
        assert plan.reply_all is True
