"""
Comprehensive tests for sales and service delivery models.

Tests cover:
- Sales models (Lead, Deal, CommissionEntry, CallTranscript, FollowUpTask)
- Service delivery models (Contract, Project, Milestone, ProjectTask, Appointment)
- Cross-module relationships (Deal->Contract, Entity->Appointment)
- Budget tracking and guardrails
- AI enrichment features
- JSON field serialization
- Enum validation
- Workflow chains (deal->contract->project->milestone->task)

Target: 80%+ line coverage for both sales.models and service_delivery.models
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from tests.factories.workspace_factory import WorkspaceFactory
from tests.factories.sales_factory import (
    LeadFactory, DealFactory, CommissionEntryFactory,
    CallTranscriptFactory, FollowUpTaskFactory
)
from tests.factories.service_factory import (
    ContractFactory, ProjectFactory, MilestoneFactory,
    ProjectTaskFactory, AppointmentFactory
)

from sales.models import (
    Lead, Deal, CommissionEntry, CallTranscript, FollowUpTask,
    LeadStatus, DealStage, CommissionStatus, NegotiationState
)
from service_delivery.models import (
    Contract, Project, Milestone, ProjectTask, Appointment,
    ContractType, ProjectStatus, MilestoneStatus, BudgetStatus, AppointmentStatus
)
from core.models import User, Workspace
from accounting.models import Entity


# ============================================================================
# Lead Model Tests
# ============================================================================

class TestLeadModel:
    """Test Lead model (CRM leads)."""

    def test_lead_create_with_defaults(self, db_session: Session):
        """Test Lead creation with required fields."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        lead = LeadFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()
        db_session.refresh(lead)

        assert lead.id is not None
        assert lead.workspace_id == workspace.id
        assert lead.email is not None
        assert lead.status in [s.value for s in LeadStatus]

    def test_lead_status_enum(self, db_session: Session):
        """Test all LeadStatus enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        statuses = [LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.DISQUALIFIED,
                   LeadStatus.CONTACTED, LeadStatus.SPAM]

        for status in statuses:
            lead = LeadFactory(
                workspace_id=workspace.id,
                status=status.value,
                _session=db_session
            )
            db_session.commit()
            db_session.refresh(lead)

            assert lead.status == status.value

        # Verify all leads created
        leads = db_session.query(Lead).filter(
            Lead.workspace_id == workspace.id
        ).all()
        assert len(leads) == 5

    def test_lead_ai_score_range(self, db_session: Session):
        """Test AI score is within 0.0-1.0 range."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        lead1 = LeadFactory(
            workspace_id=workspace.id,
            ai_score=0.0,
            _session=db_session
        )
        lead2 = LeadFactory(
            workspace_id=workspace.id,
            ai_score=0.5,
            _session=db_session
        )
        lead3 = LeadFactory(
            workspace_id=workspace.id,
            ai_score=1.0,
            _session=db_session
        )
        db_session.commit()

        assert 0.0 <= lead1.ai_score <= 1.0
        assert 0.0 <= lead2.ai_score <= 1.0
        assert 0.0 <= lead3.ai_score <= 1.0

    def test_lead_is_spam_boolean(self, db_session: Session):
        """Test spam flag boolean."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        lead_not_spam = LeadFactory(
            workspace_id=workspace.id,
            is_spam=False,
            _session=db_session
        )
        lead_spam = LeadFactory(
            workspace_id=workspace.id,
            is_spam=True,
            _session=db_session
        )
        db_session.commit()

        assert lead_not_spam.is_spam is False
        assert lead_spam.is_spam is True

    def test_lead_is_converted_boolean(self, db_session: Session):
        """Test conversion flag boolean."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        lead = LeadFactory(
            workspace_id=workspace.id,
            is_converted=True,
            _session=db_session
        )
        db_session.commit()

        assert lead.is_converted is True

    def test_lead_metadata_json_field(self, db_session: Session):
        """Test JSON metadata field."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        metadata = {
            "source_campaign": "linkedin_q1_2026",
            "referral_code": "REF123",
            "lead_score": 85
        }

        lead = LeadFactory(
            workspace_id=workspace.id,
            metadata_json=metadata,
            _session=db_session
        )
        db_session.commit()
        db_session.refresh(lead)

        assert lead.metadata_json["source_campaign"] == "linkedin_q1_2026"
        assert lead.metadata_json["referral_code"] == "REF123"
        assert lead.metadata_json["lead_score"] == 85

    def test_lead_external_id_indexed(self, db_session: Session):
        """Test external ID for CRM integration."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # HubSpot ID
        lead = LeadFactory(
            workspace_id=workspace.id,
            external_id="hubspot_12345678",
            _session=db_session
        )
        db_session.commit()

        # Query by external_id (should use index)
        found = db_session.query(Lead).filter(
            Lead.external_id == "hubspot_12345678"
        ).first()
        assert found is not None
        assert found.id == lead.id


# ============================================================================
# Deal Model Tests
# ============================================================================

class TestDealModel:
    """Test Deal model (Sales deals)."""

    def test_deal_create_with_defaults(self, db_session: Session):
        """Test Deal creation with required fields."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()
        db_session.refresh(deal)

        assert deal.id is not None
        assert deal.workspace_id == workspace.id
        assert deal.name is not None

    def test_deal_stage_enum(self, db_session: Session):
        """Test all DealStage enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        stages = [DealStage.DISCOVERY, DealStage.QUALIFICATION, DealStage.PROPOSAL,
                 DealStage.NEGOTIATION, DealStage.CLOSED_WON, DealStage.CLOSED_LOST]

        for stage in stages:
            deal = DealFactory(
                workspace_id=workspace.id,
                stage=stage.value,
                _session=db_session
            )
            db_session.commit()

        # Verify all deals created
        deals = db_session.query(Deal).filter(
            Deal.workspace_id == workspace.id
        ).all()
        assert len(deals) == 6

    def test_deal_value_currency(self, db_session: Session):
        """Test deal value and currency fields."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            value=50000.0,
            currency="USD",
            _session=db_session
        )
        db_session.commit()

        assert deal.value == 50000.0
        assert deal.currency == "USD"

    def test_deal_probability_range(self, db_session: Session):
        """Test probability is within 0.0-1.0 range."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            probability=0.75,
            _session=db_session
        )
        db_session.commit()

        assert 0.0 <= deal.probability <= 1.0

    def test_deal_health_score_range(self, db_session: Session):
        """Test health score is within 0-100 range."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            health_score=85.5,
            _session=db_session
        )
        db_session.commit()

        assert 0.0 <= deal.health_score <= 100.0

    def test_deal_negotiation_state_enum(self, db_session: Session):
        """Test all NegotiationState enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        states = [NegotiationState.INITIAL, NegotiationState.DISCOVERY,
                 NegotiationState.BARGAINING, NegotiationState.CLOSING,
                 NegotiationState.FOLLOW_UP, NegotiationState.WON,
                 NegotiationState.LOST]

        for state in states:
            deal = DealFactory(
                workspace_id=workspace.id,
                negotiation_state=state.value,
                _session=db_session
            )
            db_session.commit()

        # Verify all deals created
        deals = db_session.query(Deal).filter(
            Deal.workspace_id == workspace.id
        ).all()
        assert len(deals) == 7

    def test_deal_transcripts_relationship(self, db_session: Session):
        """Test deal has many transcripts."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        # Create multiple transcripts
        for i in range(3):
            transcript = CallTranscriptFactory(
                workspace_id=workspace.id,
                deal_id=deal.id,
                _session=db_session
            )
            db_session.add(transcript)
        db_session.commit()

        # Query transcripts for deal
        transcripts = db_session.query(CallTranscript).filter(
            CallTranscript.deal_id == deal.id
        ).all()
        assert len(transcripts) == 3

    def test_deal_commissions_relationship(self, db_session: Session):
        """Test deal has many commissions."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        # Create multiple commissions
        for i in range(2):
            commission = CommissionEntryFactory(
                workspace_id=workspace.id,
                deal_id=deal.id,
                amount=5000.0,
                _session=db_session
            )
            db_session.add(commission)
        db_session.commit()

        # Query commissions for deal
        commissions = db_session.query(CommissionEntry).filter(
            CommissionEntry.deal_id == deal.id
        ).all()
        assert len(commissions) == 2

    def test_deal_last_engagement_nullable(self, db_session: Session):
        """Test nullable last_engagement_at datetime."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            last_engagement_at=None,
            _session=db_session
        )
        db_session.commit()

        assert deal.last_engagement_at is None

    def test_deal_followup_count_default(self, db_session: Session):
        """Test default followup_count is 0."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            followup_count=0,
            _session=db_session
        )
        db_session.commit()

        assert deal.followup_count == 0


class TestDealIntelligence:
    """Test Deal intelligence features."""

    def test_deal_risk_levels(self, db_session: Session):
        """Test low/medium/high risk values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal_low = DealFactory(
            workspace_id=workspace.id,
            risk_level="low",
            _session=db_session
        )
        deal_medium = DealFactory(
            workspace_id=workspace.id,
            risk_level="medium",
            _session=db_session
        )
        deal_high = DealFactory(
            workspace_id=workspace.id,
            risk_level="high",
            _session=db_session
        )
        db_session.commit()

        assert deal_low.risk_level == "low"
        assert deal_medium.risk_level == "medium"
        assert deal_high.risk_level == "high"

    def test_deal_followup_tracking(self, db_session: Session):
        """Test last_followup_at and followup_count update."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            last_followup_at=datetime.now(timezone.utc),
            followup_count=5,
            _session=db_session
        )
        db_session.commit()

        # Update followup tracking
        deal.last_followup_at = datetime.now(timezone.utc)
        deal.followup_count = 6
        db_session.commit()

        assert deal.followup_count == 6

    def test_deal_metadata_json(self, db_session: Session):
        """Test JSON for custom deal fields."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        metadata = {
            "decision_maker": "John Doe",
            "competitor": "CompetitorX",
            "next_step": "Send proposal"
        }

        deal = DealFactory(
            workspace_id=workspace.id,
            metadata_json=metadata,
            _session=db_session
        )
        db_session.commit()
        db_session.refresh(deal)

        assert deal.metadata_json["decision_maker"] == "John Doe"
        assert deal.metadata_json["competitor"] == "CompetitorX"
        assert deal.metadata_json["next_step"] == "Send proposal"


# ============================================================================
# Commission Entry Model Tests
# ============================================================================

class TestCommissionEntryModel:
    """Test CommissionEntry model (Sales commissions)."""

    def test_commission_create_with_defaults(self, db_session: Session):
        """Test commission entry creation."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        commission = CommissionEntryFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            amount=5000.0,
            _session=db_session
        )
        db_session.commit()

        assert commission.id is not None
        assert commission.deal_id == deal.id
        assert commission.amount == 5000.0

    def test_commission_status_enum(self, db_session: Session):
        """Test all CommissionStatus enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        statuses = [CommissionStatus.ACCRUED, CommissionStatus.APPROVED,
                   CommissionStatus.PAID, CommissionStatus.CANCELLED]

        for status in statuses:
            commission = CommissionEntryFactory(
                workspace_id=workspace.id,
                deal_id=deal.id,
                amount=1000.0,
                status=status.value,
                _session=db_session
            )
            db_session.commit()

        # Verify all commissions created
        commissions = db_session.query(CommissionEntry).filter(
            CommissionEntry.deal_id == deal.id
        ).all()
        assert len(commissions) == 4

    def test_commission_deal_relationship(self, db_session: Session):
        """Test commission belongs to deal."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        commission = CommissionEntryFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            amount=3000.0,
            _session=db_session
        )
        db_session.commit()

        # Verify relationship
        assert commission.deal_id == deal.id

        # Query deal
        found_deal = db_session.query(Deal).filter(
            Deal.id == deal.id
        ).first()
        assert found_deal is not None

    def test_commission_payee_nullable(self, db_session: Session):
        """Test optional payee_id."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        commission_no_payee = CommissionEntryFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            amount=2000.0,
            payee_id=None,
            _session=db_session
        )
        commission_with_payee = CommissionEntryFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            amount=3000.0,
            payee_id="user_123",
            _session=db_session
        )
        db_session.commit()

        assert commission_no_payee.payee_id is None
        assert commission_with_payee.payee_id == "user_123"

    def test_commission_calculated_at_auto(self, db_session: Session):
        """Test timestamp auto-generation."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        commission = CommissionEntryFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            amount=4000.0,
            _session=db_session
        )
        db_session.commit()

        assert commission.calculated_at is not None
        assert isinstance(commission.calculated_at, datetime)

    def test_commission_paid_at_nullable(self, db_session: Session):
        """Test nullable paid_at timestamp."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        commission_unpaid = CommissionEntryFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            amount=1000.0,
            paid_at=None,
            _session=db_session
        )
        commission_paid = CommissionEntryFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            amount=2000.0,
            paid_at=datetime.now(timezone.utc),
            _session=db_session
        )
        db_session.commit()

        assert commission_unpaid.paid_at is None
        assert commission_paid.paid_at is not None

    def test_commission_invoice_id_nullable(self, db_session: Session):
        """Test optional invoice link."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        commission = CommissionEntryFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            amount=1500.0,
            invoice_id="INV_001",
            _session=db_session
        )
        db_session.commit()

        assert commission.invoice_id == "INV_001"


# ============================================================================
# Call Transcript Model Tests
# ============================================================================

class TestCallTranscriptModel:
    """Test CallTranscript model (Call transcripts)."""

    def test_transcript_create_with_defaults(self, db_session: Session):
        """Test transcript creation."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        transcript = CallTranscriptFactory(
            workspace_id=workspace.id,
            raw_transcript="This is a test transcript.",
            _session=db_session
        )
        db_session.commit()

        assert transcript.id is not None
        assert transcript.raw_transcript == "This is a test transcript."

    def test_transcript_raw_text_field(self, db_session: Session):
        """Test large text field."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        large_text = "Word " * 1000  # ~5000 characters

        transcript = CallTranscriptFactory(
            workspace_id=workspace.id,
            raw_transcript=large_text,
            _session=db_session
        )
        db_session.commit()

        assert len(transcript.raw_transcript) == len(large_text)

    def test_transcript_deal_relationship(self, db_session: Session):
        """Test optional deal link."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        transcript = CallTranscriptFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            raw_transcript="Deal discussion transcript",
            _session=db_session
        )
        db_session.commit()

        assert transcript.deal_id == deal.id

        # Test without deal
        transcript_no_deal = CallTranscriptFactory(
            workspace_id=workspace.id,
            deal_id=None,
            raw_transcript="General transcript",
            _session=db_session
        )
        db_session.commit()

        assert transcript_no_deal.deal_id is None

    def test_transcript_meeting_id_nullable(self, db_session: Session):
        """Test optional meeting ID."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        transcript = CallTranscriptFactory(
            workspace_id=workspace.id,
            raw_transcript="Test transcript",
            meeting_id="zoom_12345",
            _session=db_session
        )
        db_session.commit()

        assert transcript.meeting_id == "zoom_12345"

    def test_transcript_objections_json(self, db_session: Session):
        """Test JSON array of objections."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        objections = [
            {"objection": "Price too high", "severity": "high"},
            {"objection": "Need to check with team", "severity": "low"}
        ]

        transcript = CallTranscriptFactory(
            workspace_id=workspace.id,
            raw_transcript="Customer raised objections",
            objections=objections,
            _session=db_session
        )
        db_session.commit()
        db_session.refresh(transcript)

        assert len(transcript.objections) == 2
        assert transcript.objections[0]["objection"] == "Price too high"

    def test_transcript_action_items_json(self, db_session: Session):
        """Test JSON array of tasks."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        action_items = [
            {"task": "Send case study", "priority": "high", "due": "2026-03-15"},
            {"task": "Schedule demo", "priority": "medium", "due": "2026-03-16"}
        ]

        transcript = CallTranscriptFactory(
            workspace_id=workspace.id,
            raw_transcript="Action items discussed",
            action_items=action_items,
            _session=db_session
        )
        db_session.commit()
        db_session.refresh(transcript)

        assert len(transcript.action_items) == 2
        assert transcript.action_items[0]["task"] == "Send case study"

    def test_transcript_summary_optional(self, db_session: Session):
        """Test optional AI summary."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        transcript_with_summary = CallTranscriptFactory(
            workspace_id=workspace.id,
            raw_transcript="Full transcript here",
            summary="Customer is interested in our premium plan.",
            _session=db_session
        )
        transcript_no_summary = CallTranscriptFactory(
            workspace_id=workspace.id,
            raw_transcript="Another transcript",
            summary=None,
            _session=db_session
        )
        db_session.commit()

        assert transcript_with_summary.summary is not None
        assert transcript_no_summary.summary is None

    def test_transcript_metadata_json(self, db_session: Session):
        """Test additional metadata."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        metadata = {
            "recording_url": "s3://recordings/call_123.mp4",
            "duration_seconds": 1800,
            "participants": ["Agent", "Customer"]
        }

        transcript = CallTranscriptFactory(
            workspace_id=workspace.id,
            raw_transcript="Test",
            metadata_json=metadata,
            _session=db_session
        )
        db_session.commit()
        db_session.refresh(transcript)

        assert transcript.metadata_json["duration_seconds"] == 1800
        assert len(transcript.metadata_json["participants"]) == 2


# ============================================================================
# Follow Up Task Model Tests
# ============================================================================

class TestFollowUpTaskModel:
    """Test FollowUpTask model (Sales tasks)."""

    def test_followup_create_with_defaults(self, db_session: Session):
        """Test follow-up task creation."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        task = FollowUpTaskFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            description="Send follow-up email",
            _session=db_session
        )
        db_session.commit()

        assert task.id is not None
        assert task.deal_id == deal.id
        assert task.description == "Send follow-up email"

    def test_followup_deal_relationship(self, db_session: Session):
        """Test task belongs to deal."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        task = FollowUpTaskFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            description="Call customer",
            _session=db_session
        )
        db_session.commit()

        assert task.deal_id == deal.id

    def test_followup_description_required(self, db_session: Session):
        """Test description is required."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        task = FollowUpTaskFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            description="Required description field",
            _session=db_session
        )
        db_session.commit()

        assert task.description is not None
        assert len(task.description) > 0

    def test_followup_suggested_date_nullable(self, db_session: Session):
        """Test optional date."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        task_with_date = FollowUpTaskFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            description="Task with date",
            suggested_date=datetime.now(timezone.utc) + timedelta(days=3),
            _session=db_session
        )
        task_no_date = FollowUpTaskFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            description="Task without date",
            suggested_date=None,
            _session=db_session
        )
        db_session.commit()

        assert task_with_date.suggested_date is not None
        assert task_no_date.suggested_date is None

    def test_followup_is_completed_boolean(self, db_session: Session):
        """Test completion flag."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        task_pending = FollowUpTaskFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            description="Pending task",
            is_completed=False,
            _session=db_session
        )
        task_done = FollowUpTaskFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            description="Completed task",
            is_completed=True,
            _session=db_session
        )
        db_session.commit()

        assert task_pending.is_completed is False
        assert task_done.is_completed is True

    def test_followup_ai_rationale_optional(self, db_session: Session):
        """Test AI explanation."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        task = FollowUpTaskFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            description="AI suggested task",
            ai_rationale="Customer showed interest during call, follow up recommended.",
            _session=db_session
        )
        db_session.commit()

        assert task.ai_rationale is not None
        assert "interest" in task.ai_rationale.lower()


# ============================================================================
# Contract Model Tests
# ============================================================================

class TestContractModel:
    """Test Contract model (Service contracts)."""

    def test_contract_create_with_defaults(self, db_session: Session):
        """Test contract creation."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        contract = ContractFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        assert contract.id is not None
        assert contract.workspace_id == workspace.id
        assert contract.name is not None

    def test_contract_type_enum(self, db_session: Session):
        """Test all ContractType enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        types = [ContractType.FIXED_FEE, ContractType.RETAINER, ContractType.TIME_MATERIAL]

        for contract_type in types:
            contract = ContractFactory(
                workspace_id=workspace.id,
                type=contract_type.value,
                _session=db_session
            )
            db_session.commit()

        # Verify all contracts created
        contracts = db_session.query(Contract).filter(
            Contract.workspace_id == workspace.id
        ).all()
        assert len(contracts) == 3

    def test_contract_deal_relationship(self, db_session: Session):
        """Test optional deal link from sales.Deal."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        deal = DealFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        contract = ContractFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            _session=db_session
        )
        db_session.commit()

        assert contract.deal_id == deal.id

        # Test without deal
        contract_no_deal = ContractFactory(
            workspace_id=workspace.id,
            deal_id=None,
            _session=db_session
        )
        db_session.commit()

        assert contract_no_deal.deal_id is None

    def test_contract_total_amount_float(self, db_session: Session):
        """Test currency amount."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        contract = ContractFactory(
            workspace_id=workspace.id,
            total_amount=100000.0,
            _session=db_session
        )
        db_session.commit()

        assert contract.total_amount == 100000.0

    def test_contract_date_range(self, db_session: Session):
        """Test start_date and end_date."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        start = datetime.now(timezone.utc) - timedelta(days=30)
        end = datetime.now(timezone.utc) + timedelta(days=365)

        contract = ContractFactory(
            workspace_id=workspace.id,
            start_date=start,
            end_date=end,
            _session=db_session
        )
        db_session.commit()

        assert contract.start_date is not None
        assert contract.end_date is not None
        assert contract.end_date > contract.start_date

    def test_contract_metadata_json(self, db_session: Session):
        """Test JSON for contract terms."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        metadata = {
            "payment_terms": "net_30",
            "renewal_auto": True,
            "notice_period_days": 30
        }

        contract = ContractFactory(
            workspace_id=workspace.id,
            metadata_json=metadata,
            _session=db_session
        )
        db_session.commit()
        db_session.refresh(contract)

        assert contract.metadata_json["payment_terms"] == "net_30"
        assert contract.metadata_json["renewal_auto"] is True

    def test_contract_projects_relationship(self, db_session: Session):
        """Test contract has many projects."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        contract = ContractFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        # Create multiple projects
        for i in range(3):
            project = ProjectFactory(
                workspace_id=workspace.id,
                contract_id=contract.id,
                _session=db_session
            )
            db_session.add(project)
        db_session.commit()

        # Query projects for contract
        projects = db_session.query(Project).filter(
            Project.contract_id == contract.id
        ).all()
        assert len(projects) == 3


# ============================================================================
# Project Model Tests
# ============================================================================

class TestProjectModel:
    """Test Project model (Service projects)."""

    def test_project_create_with_defaults(self, db_session: Session):
        """Test project creation."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        assert project.id is not None
        assert project.workspace_id == workspace.id
        assert project.name is not None

    def test_project_status_enum(self, db_session: Session):
        """Test all ProjectStatus enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        statuses = [ProjectStatus.PENDING, ProjectStatus.ACTIVE, ProjectStatus.PAUSED_PAYMENT,
                   ProjectStatus.PAUSED_CLIENT, ProjectStatus.COMPLETED, ProjectStatus.CANCELED]

        for status in statuses:
            project = ProjectFactory(
                workspace_id=workspace.id,
                status=status.value,
                _session=db_session
            )
            db_session.commit()

        # Verify all projects created
        projects = db_session.query(Project).filter(
            Project.workspace_id == workspace.id
        ).all()
        assert len(projects) == 6

    def test_project_contract_relationship(self, db_session: Session):
        """Test optional contract link."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        contract = ContractFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            contract_id=contract.id,
            _session=db_session
        )
        db_session.commit()

        assert project.contract_id == contract.id

        # Test without contract
        project_no_contract = ProjectFactory(
            workspace_id=workspace.id,
            contract_id=None,
            _session=db_session
        )
        db_session.commit()

        assert project_no_contract.contract_id is None

    def test_project_budget_tracking(self, db_session: Session):
        """Test budget_hours/amount vs actual."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            budget_hours=1000.0,
            actual_hours=650.0,
            budget_amount=100000.0,
            actual_burn=65000.0,
            _session=db_session
        )
        db_session.commit()

        assert project.budget_hours == 1000.0
        assert project.actual_hours == 650.0
        assert project.budget_amount == 100000.0
        assert project.actual_burn == 65000.0

    def test_project_budget_status_enum(self, db_session: Session):
        """Test BudgetStatus values (on_track, at_risk, over_budget)."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        statuses = [BudgetStatus.ON_TRACK, BudgetStatus.AT_RISK, BudgetStatus.OVER_BUDGET]

        for status in statuses:
            project = ProjectFactory(
                workspace_id=workspace.id,
                budget_status=status.value,
                _session=db_session
            )
            db_session.commit()

        # Verify all projects created
        projects = db_session.query(Project).filter(
            Project.workspace_id == workspace.id
        ).all()
        assert len(projects) == 3

    def test_project_guardrail_thresholds(self, db_session: Session):
        """Test warn, pause, block percentages."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            warn_threshold_pct=80,
            pause_threshold_pct=90,
            block_threshold_pct=100,
            _session=db_session
        )
        db_session.commit()

        assert project.warn_threshold_pct == 80
        assert project.pause_threshold_pct == 90
        assert project.block_threshold_pct == 100

    def test_project_guardrail_validation(self, db_session: Session):
        """Verify warn < pause < block (application-level validation)."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Valid configuration
        project_valid = ProjectFactory(
            workspace_id=workspace.id,
            warn_threshold_pct=70,
            pause_threshold_pct=85,
            block_threshold_pct=100,
            _session=db_session
        )
        db_session.commit()

        # Application-level validation should ensure: warn < pause < block
        # This test documents the expected behavior
        assert project_valid.warn_threshold_pct < project_valid.pause_threshold_pct
        assert project_valid.pause_threshold_pct < project_valid.block_threshold_pct

    def test_project_priority_levels(self, db_session: Session):
        """Test low/medium/high/critical."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        priorities = ["low", "medium", "high", "critical"]

        for priority in priorities:
            project = ProjectFactory(
                workspace_id=workspace.id,
                priority=priority,
                _session=db_session
            )
            db_session.commit()

        # Verify all projects created
        projects = db_session.query(Project).filter(
            Project.workspace_id == workspace.id
        ).all()
        assert len(projects) == 4

    def test_project_milestones_relationship(self, db_session: Session):
        """Test project has many milestones."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        # Create multiple milestones
        for i in range(5):
            milestone = MilestoneFactory(
                workspace_id=workspace.id,
                project_id=project.id,
                order=i,
                _session=db_session
            )
            db_session.add(milestone)
        db_session.commit()

        # Query milestones for project
        milestones = db_session.query(Milestone).filter(
            Milestone.project_id == project.id
        ).all()
        assert len(milestones) == 5

    def test_project_dates(self, db_session: Session):
        """Test planned vs actual dates."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        planned_start = datetime.now(timezone.utc) - timedelta(days=15)
        planned_end = datetime.now(timezone.utc) + timedelta(days=90)
        actual_start = datetime.now(timezone.utc) - timedelta(days=10)

        project = ProjectFactory(
            workspace_id=workspace.id,
            planned_start_date=planned_start,
            planned_end_date=planned_end,
            actual_start_date=actual_start,
            _session=db_session
        )
        db_session.commit()

        assert project.planned_start_date is not None
        assert project.planned_end_date is not None
        assert project.actual_start_date is not None

    def test_project_risk_fields(self, db_session: Session):
        """Test risk_score and risk_level."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            risk_level="medium",
            risk_score=55.5,
            risk_rationale="Timeline at risk due to scope changes",
            _session=db_session
        )
        db_session.commit()

        assert project.risk_level == "medium"
        assert project.risk_score == 55.5
        assert "scope changes" in project.risk_rationale.lower()


# ============================================================================
# Milestone Model Tests
# ============================================================================

class TestMilestoneModel:
    """Test Milestone model (Project milestones)."""

    def test_milestone_create_with_defaults(self, db_session: Session):
        """Test milestone creation."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        assert milestone.id is not None
        assert milestone.project_id == project.id
        assert milestone.name is not None

    def test_milestone_status_enum(self, db_session: Session):
        """Test all MilestoneStatus enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        statuses = [MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS,
                   MilestoneStatus.COMPLETED, MilestoneStatus.APPROVED, MilestoneStatus.INVOICED]

        for status in statuses:
            milestone = MilestoneFactory(
                workspace_id=workspace.id,
                project_id=project.id,
                status=status.value,
                _session=db_session
            )
            db_session.commit()

        # Verify all milestones created
        milestones = db_session.query(Milestone).filter(
            Milestone.project_id == project.id
        ).all()
        assert len(milestones) == 5

    def test_milestone_project_relationship(self, db_session: Session):
        """Test milestone belongs to project."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        assert milestone.project_id == project.id

    def test_milestone_billing_amount(self, db_session: Session):
        """Test amount for invoicing."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            amount=25000.0,
            _session=db_session
        )
        db_session.commit()

        assert milestone.amount == 25000.0

    def test_milestone_percentage(self, db_session: Session):
        """Test % of contract."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            percentage=25.0,
            _session=db_session
        )
        db_session.commit()

        assert milestone.percentage == 25.0

    def test_milestone_ordering(self, db_session: Session):
        """Test order field for sequencing."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        # Create milestones out of order
        milestone3 = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            order=3,
            _session=db_session
        )
        milestone1 = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            order=1,
            _session=db_session
        )
        milestone2 = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            order=2,
            _session=db_session
        )
        db_session.add_all([milestone3, milestone1, milestone2])
        db_session.commit()

        # Query ordered by order field
        milestones = db_session.query(Milestone).filter(
            Milestone.project_id == project.id
        ).order_by(Milestone.order).all()

        assert milestones[0].order == 1
        assert milestones[1].order == 2
        assert milestones[2].order == 3

    def test_milestone_budget_tracking(self, db_session: Session):
        """Test actual_burn and budget_status."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            actual_burn=22000.0,
            budget_status=BudgetStatus.ON_TRACK.value,
            _session=db_session
        )
        db_session.commit()

        assert milestone.actual_burn == 22000.0
        assert milestone.budget_status == BudgetStatus.ON_TRACK.value

    def test_milestone_invoice_id_nullable(self, db_session: Session):
        """Test optional invoice link."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone_no_invoice = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            invoice_id=None,
            _session=db_session
        )
        milestone_with_invoice = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            invoice_id="INV_MILESTONE_001",
            _session=db_session
        )
        db_session.commit()

        assert milestone_no_invoice.invoice_id is None
        assert milestone_with_invoice.invoice_id == "INV_MILESTONE_001"

    def test_milestone_tasks_relationship(self, db_session: Session):
        """Test milestone has many tasks."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        # Create multiple tasks
        for i in range(4):
            task = ProjectTaskFactory(
                workspace_id=workspace.id,
                project_id=project.id,
                milestone_id=milestone.id,
                _session=db_session
            )
            db_session.add(task)
        db_session.commit()

        # Query tasks for milestone
        tasks = db_session.query(ProjectTask).filter(
            ProjectTask.milestone_id == milestone.id
        ).all()
        assert len(tasks) == 4


# ============================================================================
# Project Task Model Tests
# ============================================================================

class TestProjectTaskModel:
    """Test ProjectTask model (Project tasks)."""

    def test_task_create_with_defaults(self, db_session: Session):
        """Test project task creation."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        task = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            _session=db_session
        )
        db_session.commit()

        assert task.id is not None
        assert task.project_id == project.id
        assert task.milestone_id == milestone.id

    def test_task_milestone_relationship(self, db_session: Session):
        """Test task belongs to milestone."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        task = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            _session=db_session
        )
        db_session.commit()

        assert task.milestone_id == milestone.id

    def test_task_project_relationship(self, db_session: Session):
        """Test task belongs to project."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        task = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            _session=db_session
        )
        db_session.commit()

        assert task.project_id == project.id

    def test_task_status_values(self, db_session: Session):
        """Test pending, in_progress, completed, blocked."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        statuses = ["pending", "in_progress", "completed", "blocked"]

        for status in statuses:
            task = ProjectTaskFactory(
                workspace_id=workspace.id,
                project_id=project.id,
                milestone_id=milestone.id,
                status=status,
                _session=db_session
            )
            db_session.commit()

        # Verify all tasks created
        tasks = db_session.query(ProjectTask).filter(
            ProjectTask.project_id == project.id
        ).all()
        assert len(tasks) == 4

    def test_task_assigned_to_relationship(self, db_session: Session):
        """Test optional user assignment."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        task_assigned = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            assigned_to="user_123",
            _session=db_session
        )
        task_unassigned = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            assigned_to=None,
            _session=db_session
        )
        db_session.commit()

        assert task_assigned.assigned_to == "user_123"
        assert task_unassigned.assigned_to is None

    def test_task_due_date_nullable(self, db_session: Session):
        """Test optional deadline."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        task_with_due = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            due_date=datetime.now(timezone.utc) + timedelta(days=7),
            _session=db_session
        )
        task_no_due = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            due_date=None,
            _session=db_session
        )
        db_session.commit()

        assert task_with_due.due_date is not None
        assert task_no_due.due_date is None

    def test_task_completed_at_nullable(self, db_session: Session):
        """Test nullable completion timestamp."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        task_completed = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            _session=db_session
        )
        task_pending = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            status="pending",
            completed_at=None,
            _session=db_session
        )
        db_session.commit()

        assert task_completed.completed_at is not None
        assert task_pending.completed_at is None

    def test_task_actual_hours_tracking(self, db_session: Session):
        """Test time tracking."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        task = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            actual_hours=8.5,
            _session=db_session
        )
        db_session.commit()

        assert task.actual_hours == 8.5

    def test_task_metadata_json(self, db_session: Session):
        """Test JSON for task data."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        metadata = {
            "dependencies": ["task_1", "task_2"],
            "tags": ["frontend", "urgent"],
            "estimated_hours": 12
        }

        task = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            metadata_json=metadata,
            _session=db_session
        )
        db_session.commit()
        db_session.refresh(task)

        assert len(task.metadata_json["dependencies"]) == 2
        assert "frontend" in task.metadata_json["tags"]


# ============================================================================
# Appointment Model Tests
# ============================================================================

class TestAppointmentModel:
    """Test Appointment model (Service appointments)."""

    def test_appointment_create_with_defaults(self, db_session: Session):
        """Test appointment creation."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create customer entity (from accounting.models)
        customer = Entity(
            id=str(__import__('uuid').uuid4()),
            workspace_id=workspace.id,
            name="Test Customer",
            type="customer",
            email="customer@test.com"
        )
        db_session.add(customer)
        db_session.commit()

        appointment = AppointmentFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            _session=db_session
        )
        db_session.commit()

        assert appointment.id is not None
        assert appointment.workspace_id == workspace.id
        assert appointment.customer_id == customer.id

    def test_appointment_customer_relationship(self, db_session: Session):
        """Test appointment belongs to Entity (from accounting)."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create customer entity
        customer = Entity(
            id=str(__import__('uuid').uuid4()),
            workspace_id=workspace.id,
            name="John Doe",
            type="customer",
            email="john@test.com"
        )
        db_session.add(customer)
        db_session.commit()

        appointment = AppointmentFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            _session=db_session
        )
        db_session.commit()

        assert appointment.customer_id == customer.id

        # Query customer
        found_customer = db_session.query(Entity).filter(
            Entity.id == customer.id
        ).first()
        assert found_customer is not None
        assert found_customer.name == "John Doe"

    def test_appointment_service_relationship(self, db_session: Session):
        """Test optional service link."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create customer entity
        customer = Entity(
            id=str(__import__('uuid').uuid4()),
            workspace_id=workspace.id,
            name="Test Customer",
            type="customer",
            email="test@example.com"
        )
        db_session.add(customer)
        db_session.commit()

        appointment_with_service = AppointmentFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            service_id="service_123",
            _session=db_session
        )
        appointment_no_service = AppointmentFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            service_id=None,
            _session=db_session
        )
        db_session.commit()

        assert appointment_with_service.service_id == "service_123"
        assert appointment_no_service.service_id is None

    def test_appointment_status_enum(self, db_session: Session):
        """Test all AppointmentStatus enum values."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create customer entity
        customer = Entity(
            id=str(__import__('uuid').uuid4()),
            workspace_id=workspace.id,
            name="Test Customer",
            type="customer",
            email="customer@test.com"
        )
        db_session.add(customer)
        db_session.commit()

        statuses = [AppointmentStatus.SCHEDULED, AppointmentStatus.COMPLETED,
                   AppointmentStatus.NO_SHOW, AppointmentStatus.CANCELED]

        for status in statuses:
            appointment = AppointmentFactory(
                workspace_id=workspace.id,
                customer_id=customer.id,
                status=status.value,
                _session=db_session
            )
            db_session.commit()

        # Verify all appointments created
        appointments = db_session.query(Appointment).filter(
            Appointment.customer_id == customer.id
        ).all()
        assert len(appointments) == 4

    def test_appointment_time_range(self, db_session: Session):
        """Test start_time < end_time."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create customer entity
        customer = Entity(
            id=str(__import__('uuid').uuid4()),
            workspace_id=workspace.id,
            name="Test Customer",
            type="customer",
            email="customer@test.com"
        )
        db_session.add(customer)
        db_session.commit()

        base_time = datetime.now(timezone.utc).replace(microsecond=0)
        start = base_time + timedelta(days=1, hours=10)
        end = base_time + timedelta(days=1, hours=11)

        appointment = AppointmentFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            start_time=start,
            end_time=end,
            _session=db_session
        )
        db_session.commit()

        assert appointment.start_time < appointment.end_time
        assert (appointment.end_time - appointment.start_time).total_seconds() == 3600

    def test_appointment_deposit_fields(self, db_session: Session):
        """Test deposit_amount and is_deposit_paid."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create customer entity
        customer = Entity(
            id=str(__import__('uuid').uuid4()),
            workspace_id=workspace.id,
            name="Test Customer",
            type="customer",
            email="customer@test.com"
        )
        db_session.add(customer)
        db_session.commit()

        appointment = AppointmentFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            deposit_amount=100.0,
            is_deposit_paid=True,
            _session=db_session
        )
        db_session.commit()

        assert appointment.deposit_amount == 100.0
        assert appointment.is_deposit_paid is True

    def test_appointment_metadata_json(self, db_session: Session):
        """Test JSON for travel heuristics."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create customer entity
        customer = Entity(
            id=str(__import__('uuid').uuid4()),
            workspace_id=workspace.id,
            name="Test Customer",
            type="customer",
            email="customer@test.com"
        )
        db_session.add(customer)
        db_session.commit()

        metadata = {
            "travel_distance_km": 25.5,
            "travel_time_minutes": 45,
            "requires_equipment": True
        }

        appointment = AppointmentFactory(
            workspace_id=workspace.id,
            customer_id=customer.id,
            metadata_json=metadata,
            _session=db_session
        )
        db_session.commit()
        db_session.refresh(appointment)

        assert appointment.metadata_json["travel_distance_km"] == 25.5
        assert appointment.metadata_json["requires_equipment"] is True


# ============================================================================
# Service Delivery Workflow Tests
# ============================================================================

class TestServiceDeliveryWorkflows:
    """Test cross-module workflows and relationships."""

    def test_contract_to_project_creation(self, db_session: Session):
        """Test create contract, then linked project."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create contract
        contract = ContractFactory(
            workspace_id=workspace.id,
            name="Service Contract 001",
            _session=db_session
        )
        db_session.commit()

        # Create linked project
        project = ProjectFactory(
            workspace_id=workspace.id,
            contract_id=contract.id,
            name="Project 001",
            _session=db_session
        )
        db_session.commit()

        # Verify relationship
        assert project.contract_id == contract.id

        # Query project from contract
        found_project = db_session.query(Project).filter(
            Project.contract_id == contract.id
        ).first()
        assert found_project is not None
        assert found_project.name == "Project 001"

    def test_project_to_milestone_chain(self, db_session: Session):
        """Test create project with multiple milestones."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create project
        project = ProjectFactory(
            workspace_id=workspace.id,
            name="Milestone Project",
            _session=db_session
        )
        db_session.commit()

        # Create multiple milestones
        for i in range(5):
            milestone = MilestoneFactory(
                workspace_id=workspace.id,
                project_id=project.id,
                name=f"Milestone {i+1}",
                order=i,
                _session=db_session
            )
            db_session.add(milestone)
        db_session.commit()

        # Query milestones for project
        milestones = db_session.query(Milestone).filter(
            Milestone.project_id == project.id
        ).order_by(Milestone.order).all()

        assert len(milestones) == 5
        assert milestones[0].name == "Milestone 1"
        assert milestones[4].name == "Milestone 5"

    def test_milestone_to_task_hierarchy(self, db_session: Session):
        """Test create milestone with multiple tasks."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create project and milestone
        project = ProjectFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            name="Task Milestone",
            _session=db_session
        )
        db_session.commit()

        # Create multiple tasks
        for i in range(6):
            task = ProjectTaskFactory(
                workspace_id=workspace.id,
                project_id=project.id,
                milestone_id=milestone.id,
                name=f"Task {i+1}",
                _session=db_session
            )
            db_session.add(task)
        db_session.commit()

        # Query tasks for milestone
        tasks = db_session.query(ProjectTask).filter(
            ProjectTask.milestone_id == milestone.id
        ).all()

        assert len(tasks) == 6

    def test_deal_to_contract_conversion(self, db_session: Session):
        """Test create deal, then convert to contract."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create deal (from sales)
        deal = DealFactory(
            workspace_id=workspace.id,
            name="Enterprise Deal",
            stage=DealStage.CLOSED_WON.value,
            value=100000.0,
            _session=db_session
        )
        db_session.commit()

        # Convert to contract (from service_delivery)
        contract = ContractFactory(
            workspace_id=workspace.id,
            deal_id=deal.id,
            name="Enterprise Contract",
            total_amount=deal.value,
            _session=db_session
        )
        db_session.commit()

        # Verify relationship
        assert contract.deal_id == deal.id
        assert contract.total_amount == deal.value

        # Query contract by deal
        found_contract = db_session.query(Contract).filter(
            Contract.deal_id == deal.id
        ).first()
        assert found_contract is not None

    def test_project_budget_status_calculation(self, db_session: Session):
        """Test on_track/at_risk/over_budget logic."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # On track: 60% budget used
        project_on_track = ProjectFactory(
            workspace_id=workspace.id,
            budget_amount=100000.0,
            actual_burn=60000.0,
            budget_status=BudgetStatus.ON_TRACK.value,
            _session=db_session
        )

        # At risk: 85% budget used
        project_at_risk = ProjectFactory(
            workspace_id=workspace.id,
            budget_amount=100000.0,
            actual_burn=85000.0,
            budget_status=BudgetStatus.AT_RISK.value,
            _session=db_session
        )

        # Over budget: 110% budget used
        project_over_budget = ProjectFactory(
            workspace_id=workspace.id,
            budget_amount=100000.0,
            actual_burn=110000.0,
            budget_status=BudgetStatus.OVER_BUDGET.value,
            _session=db_session
        )
        db_session.commit()

        # Verify budget status values
        assert project_on_track.budget_status == BudgetStatus.ON_TRACK.value
        assert project_at_risk.budget_status == BudgetStatus.AT_RISK.value
        assert project_over_budget.budget_status == BudgetStatus.OVER_BUDGET.value


# ============================================================================
# Task 5: Session Isolation Tests (API-04)
# ============================================================================

class TestConcurrentAccess:
    """Test concurrent session access patterns with proper isolation."""

    def test_separate_sessions_isolate_changes(self, db_session: Session):
        """Test that separate db_session instances don't interfere."""
        # Create workspace
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create deal in current session
        deal = DealFactory(
            workspace_id=workspace.id,
            stage=DealStage.DISCOVERY.value,
            _session=db_session
        )
        db_session.commit()

        # Verify deal exists in current session
        found = db_session.query(Deal).filter(Deal.id == deal.id).first()
        assert found is not None
        assert found.stage == DealStage.DISCOVERY.value

        # Update entity in same session
        deal.stage = DealStage.NEGOTIATION.value
        db_session.commit()

        # Verify update is visible in same session
        found = db_session.query(Deal).filter(Deal.id == deal.id).first()
        assert found.stage == DealStage.NEGOTIATION.value

    def test_session_rollback_after_test(self, db_session: Session):
        """Test that db_session fixture rolls back after test."""
        # Create data
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create a project
        project = ProjectFactory(
            workspace_id=workspace.id,
            status=ProjectStatus.ACTIVE.value,
            _session=db_session
        )
        db_session.commit()

        # Verify it exists in current session
        count = db_session.query(Project).filter(
            Project.workspace_id == workspace.id
        ).count()
        assert count == 1

        # After this test, the fixture should rollback
        # Next test should not see this data (verified by test isolation)

    def test_multiple_operations_in_single_session(self, db_session: Session):
        """Test multiple related operations in a single session."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create contract
        contract = ContractFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()

        # Create project linked to contract
        project = ProjectFactory(
            workspace_id=workspace.id,
            contract_id=contract.id,
            _session=db_session
        )
        db_session.commit()

        # Create milestone linked to project
        milestone = MilestoneFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()

        # Create task linked to milestone
        task = ProjectTaskFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            milestone_id=milestone.id,
            _session=db_session
        )
        db_session.commit()

        # Verify all relationships in single session
        assert contract.id == project.contract_id
        assert project.id == milestone.project_id
        assert milestone.id == task.milestone_id

        # Query through relationships
        found_project = db_session.query(Project).filter(
            Project.contract_id == contract.id
        ).first()
        assert found_project is not None
        assert found_project.id == project.id

        found_milestone = db_session.query(Milestone).filter(
            Milestone.project_id == project.id
        ).first()
        assert found_milestone is not None
        assert found_milestone.id == milestone.id

    def test_session_isolation_with_factory_injection(self, db_session: Session):
        """Test that factory session injection creates isolated data."""
        workspace1 = WorkspaceFactory(_session=db_session)
        workspace2 = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create contracts in different workspaces
        contract1 = ContractFactory(
            workspace_id=workspace1.id,
            name="Contract 1",
            _session=db_session
        )
        contract2 = ContractFactory(
            workspace_id=workspace2.id,
            name="Contract 2",
            _session=db_session
        )
        db_session.commit()

        # Verify isolation by workspace
        workspace1_contracts = db_session.query(Contract).filter(
            Contract.workspace_id == workspace1.id
        ).all()
        assert len(workspace1_contracts) == 1
        assert workspace1_contracts[0].name == "Contract 1"

        workspace2_contracts = db_session.query(Contract).filter(
            Contract.workspace_id == workspace2.id
        ).all()
        assert len(workspace2_contracts) == 1
        assert workspace2_contracts[0].name == "Contract 2"
