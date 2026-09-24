"""Intern data-trigger proposals — the maturity guard holds an automated
trigger from a learning-tier hire, and that hold must SURFACE as a reviewable
action proposal instead of silently dropping (the trigger previously vanished
behind a blocked_triggers row with zero UI).

Covers:
- _propose_intern_trigger creates a pending ACTION proposal (agent_execute)
- stable trigger-identity dedupe without dropping distinct inbound messages
- operational-tier hires degrade to None (legacy drop-with-audit behavior)
- the coordinator's proposal branch returns the proposal_id
- _sender_email reply-to parsing for the draft-response automation
"""

import asyncio
import os
import sys
import unittest
import uuid

sys.path.append(os.getcwd())

from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.ai_trigger_coordinator import AITriggerCoordinator
from core.communication_intelligence import CommunicationIntelligenceService
from core.database import Base
from core.models import (
    AgentProposal,
    AgentRegistry,
    BlockedTriggerContext,
    Notification,
    ProposalType,
    User,
)


def _make_agent(
    db,
    status="intern",
    agent_id=None,
    category="Sales",
    user_id=None,
    workspace_id=None,
    tenant_id=None,
):
    agent = AgentRegistry(
        id=agent_id or f"hire_{uuid.uuid4().hex[:8]}",
        name="Sales Agent",
        category=category,
        status=status,
        confidence_score=0.6,
        module_path="sales.automations.pipeline",
        class_name="SalesAgent",
        enabled=True,
        user_id=user_id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
    )
    db.add(agent)
    db.commit()
    return agent


class InternDataTriggerProposalTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.coord = AITriggerCoordinator(workspace_id="test")
        self.coord.db = self.db
        self.agent = _make_agent(
            self.db,
            workspace_id="test",
            tenant_id="default",
        )

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _blocked_context(self, message_id):
        blocked = BlockedTriggerContext(
            tenant_id="default",
            agent_id=self.agent.id,
            agent_name=self.agent.name,
            agent_maturity_at_block="intern",
            confidence_score_at_block=0.6,
            trigger_source="ai_coordinator",
            trigger_type="agent_message",
            trigger_context={"message_id": message_id},
            routing_decision="proposal",
            block_reason="INTERN requires approval",
        )
        self.db.add(blocked)
        self.db.commit()
        self.db.refresh(blocked)
        return blocked

    def test_propose_creates_pending_action_proposal(self):
        proposal_id = asyncio.run(self.coord._propose_intern_trigger(
            self.agent,
            {"text": "Acme wants a quote for 50 seats — deal closing this month."},
            {"subject": "Quote request", "message_id": "msg_1", "source_app": "outlook"},
            "sales_assistant",
        ))

        self.assertIsNotNone(proposal_id)
        row = self.db.query(AgentProposal).filter(AgentProposal.id == proposal_id).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.proposal_type, ProposalType.ACTION.value)
        self.assertEqual(row.status, "pending_approval")
        self.assertEqual(row.agent_id, self.agent.id)
        self.assertEqual(row.proposal_data.get("origin"), "data_trigger")
        self.assertEqual(row.proposal_data.get("action_type"), "agent_execute")
        self.assertEqual(row.proposal_data.get("target_agent_id"), self.agent.id)
        self.assertTrue(row.reasoning)

    def test_long_subject_is_bounded_while_full_content_is_preserved(self):
        subject = "S" * 400
        content = {"text": "C" * 1200, "thread_id": "thread-long"}

        proposal_id = asyncio.run(self.coord._propose_intern_trigger(
            self.agent,
            content,
            {"subject": subject, "message_id": "message-long"},
            "sales_assistant",
        ))

        row = self.db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id
        ).one()
        self.assertEqual(len(row.title), 255)
        self.assertEqual(row.proposal_data["subject"], subject)
        self.assertEqual(row.proposal_data["content"], content)

    def test_distinct_message_ids_create_distinct_open_proposals(self):
        first = asyncio.run(self.coord._propose_intern_trigger(
            self.agent,
            {"text": "first message"},
            {"subject": "first", "message_id": "message-1"},
            "sales_assistant",
        ))
        second = asyncio.run(self.coord._propose_intern_trigger(
            self.agent,
            {"text": "second message"},
            {"subject": "second", "message_id": "message-2"},
            "sales_assistant",
        ))

        self.assertNotEqual(first, second)
        rows = (
            self.db.query(AgentProposal)
            .filter(AgentProposal.agent_id == self.agent.id)
            .all()
        )
        self.assertEqual(len(rows), 2)

    def test_same_message_links_new_and_reused_blocked_contexts(self):
        first_context = self._blocked_context("message-link")
        first = asyncio.run(self.coord._propose_intern_trigger(
            self.agent,
            {"text": "first delivery"},
            {"message_id": "message-link"},
            "sales_assistant",
            blocked_context=first_context,
        ))
        second_context = self._blocked_context("message-link")
        second = asyncio.run(self.coord._propose_intern_trigger(
            self.agent,
            {"text": "redelivery"},
            {"message_id": "message-link"},
            "sales_assistant",
            blocked_context=second_context,
        ))

        self.assertEqual(first, second)
        self.db.refresh(first_context)
        self.db.refresh(second_context)
        self.assertEqual(first_context.proposal_id, first)
        self.assertEqual(second_context.proposal_id, first)
        self.assertFalse(first_context.resolved)
        self.assertFalse(second_context.resolved)

    def test_open_data_trigger_proposal_is_reused(self):
        first = asyncio.run(self.coord._propose_intern_trigger(
            self.agent,
            {"text": "first email"},
            {"subject": "s1", "message_id": "same-message"},
            "sales_assistant",
        ))
        second = asyncio.run(self.coord._propose_intern_trigger(
            self.agent,
            {"text": "second email"},
            {"subject": "s2", "message_id": "same-message"},
            "sales_assistant",
        ))

        self.assertEqual(first, second)
        rows = (
            self.db.query(AgentProposal)
            .filter(AgentProposal.agent_id == self.agent.id)
            .all()
        )
        self.assertEqual(len(rows), 1)

    def test_non_data_trigger_open_proposal_does_not_block_new_one(self):
        # A chat-originated pending proposal must not swallow data triggers.
        self.db.add(AgentProposal(
            tenant_id="default",
            user_id="system",
            agent_id=self.agent.id,
            agent_name=self.agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="chat proposal",
            proposal_data={"origin": "chat", "action_type": "agent_execute"},
            status="pending_approval",
        ))
        self.db.commit()

        proposal_id = asyncio.run(self.coord._propose_intern_trigger(
            self.agent, {"text": "email"}, {"subject": "s"}, "sales_assistant"
        ))

        self.assertIsNotNone(proposal_id)
        chat_row = (
            self.db.query(AgentProposal)
            .filter(AgentProposal.title == "chat proposal")
            .first()
        )
        self.assertIsNotNone(chat_row)
        self.assertNotEqual(proposal_id, chat_row.id)

    def test_operational_tier_degrades_to_none(self):
        supervised = _make_agent(self.db, status="supervised")
        proposal_id = asyncio.run(self.coord._propose_intern_trigger(
            supervised, {"text": "x"}, {"subject": "s"}, "sales_assistant"
        ))
        # Proposal creation is limited to learning tiers — the helper must
        # degrade to the legacy behavior (None), not raise.
        self.assertIsNone(proposal_id)

    def test_owner_gets_bell_notification_on_new_proposal(self):
        owner = User(
            id=f"owner_{uuid.uuid4().hex[:8]}",
            email=f"owner_{uuid.uuid4().hex[:6]}@example.com",
            first_name="O", last_name="Wner",
            role="member", status="active",
        )
        self.db.add(owner)
        self.db.commit()
        agent = _make_agent(self.db, user_id=owner.id)

        proposal_id = asyncio.run(self.coord._propose_intern_trigger(
            agent, {"text": "quote email"}, {"subject": "Quote"}, "sales_assistant"
        ))

        self.assertIsNotNone(proposal_id)
        notes = (
            self.db.query(Notification)
            .filter(Notification.user_id == owner.id)
            .all()
        )
        self.assertGreaterEqual(len(notes), 1)
        self.assertTrue(any(n.action_url == "/approvals" for n in notes))
        self.assertTrue(
            any("Sales Agent" in (n.title or "") for n in notes)
        )

    def test_dedup_reuse_does_not_renotify(self):
        owner = User(
            id=f"owner_{uuid.uuid4().hex[:8]}",
            email=f"owner_{uuid.uuid4().hex[:6]}@example.com",
            first_name="O", last_name="Wner",
            role="admin", status="active",
        )
        self.db.add(owner)
        self.db.commit()
        agent = _make_agent(self.db, user_id=owner.id)

        first = asyncio.run(self.coord._propose_intern_trigger(
            agent,
            {"text": "one"},
            {"subject": "s1", "message_id": "same-message"},
            "sales_assistant",
        ))
        second = asyncio.run(self.coord._propose_intern_trigger(
            agent,
            {"text": "two"},
            {"subject": "s2", "message_id": "same-message"},
            "sales_assistant",
        ))

        self.assertEqual(first, second)
        notes = (
            self.db.query(Notification)
            .filter(Notification.user_id == owner.id)
            .all()
        )
        # Reusing the same message proposal must not turn the notification
        # center into a mailing list.
        self.assertEqual(len(notes), 1)

    def test_trigger_agent_proposal_branch_returns_proposal_id(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        atom = MagicMock()
        decision = MagicMock()
        decision.execute = False
        decision.routing_decision.value = "proposal"
        decision.reason = "INTERN requires approval"
        decision.blocked_context = None
        decision.agent_maturity = "INTERN"
        decision.confidence_score = 0.6
        interceptor = MagicMock()
        interceptor.intercept_trigger = AsyncMock(return_value=decision)

        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor), \
             patch("core.trigger_interceptor.TriggerSource", MagicMock()):
            result = asyncio.run(self.coord._trigger_agent(
                "sales_assistant", {"text": "quote request"}, {"subject": "Quote"}, {}
            ))

        self.assertTrue(result["blocked"])
        self.assertEqual(result["routing_decision"], "proposal")
        self.assertTrue(result.get("proposal_id"))
        row = self.db.query(AgentProposal).filter(
            AgentProposal.id == result["proposal_id"]
        ).first()
        self.assertIsNotNone(row)


class SenderEmailParsingTest(unittest.TestCase):
    def setUp(self):
        self.service = CommunicationIntelligenceService(ai_service=None, db_session=None)

    def test_plain_address(self):
        self.assertEqual(
            self.service._sender_email({"sender": "alice@example.com"}),
            "alice@example.com",
        )

    def test_display_name_form(self):
        self.assertEqual(
            self.service._sender_email({"sender": "Alice Wong <alice@example.com>"}),
            "alice@example.com",
        )

    def test_mailto_prefix(self):
        self.assertEqual(
            self.service._sender_email({"sender": "mailto:bob@example.com"}),
            "bob@example.com",
        )

    def test_empty_sender(self):
        self.assertEqual(self.service._sender_email({"sender": None}), "")


if __name__ == "__main__":
    unittest.main()
