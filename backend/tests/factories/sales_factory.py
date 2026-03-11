"""
Factory Boy factories for sales models.

Provides factories for:
- Lead (CRM leads)
- Deal (Sales deals)
- CommissionEntry (Sales commissions)
- CallTranscript (Call transcripts)
- FollowUpTask (Sales tasks)
"""

import factory
from factory import fuzzy
from tests.factories.base import BaseFactory
from tests.factories.workspace_factory import WorkspaceFactory
from sales.models import (
    Lead, Deal, CommissionEntry, CallTranscript, FollowUpTask,
    LeadStatus, DealStage, CommissionStatus, NegotiationState
)


class LeadFactory(BaseFactory):
    """Factory for creating Lead instances (CRM leads)."""

    class Meta:
        model = Lead

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')  # Override in tests with WorkspaceFactory
    email = factory.Faker('email')

    # Optional fields
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    company = factory.Faker('company')
    source = factory.Iterator(['website', 'linkedin', 'referral', 'cold_outreach', 'event'])
    status = fuzzy.FuzzyChoice([s.value for s in LeadStatus])

    # AI Enrichment
    ai_score = fuzzy.FuzzyFloat(0.0, 1.0)
    ai_qualification_summary = factory.Faker('text', max_nb_chars=500)
    is_spam = fuzzy.FuzzyChoice([True, False])
    is_converted = fuzzy.FuzzyChoice([True, False])

    # External ID for CRM integration
    external_id = factory.Faker('uuid4')

    # Metadata
    metadata_json = factory.LazyFunction(dict)


class DealFactory(BaseFactory):
    """Factory for creating Deal instances (Sales deals)."""

    class Meta:
        model = Deal

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')  # Override in tests
    name = factory.Faker('company')

    # Deal value
    value = fuzzy.FuzzyFloat(0.0, 100000.0)
    currency = "USD"

    # Stage and probability
    stage = fuzzy.FuzzyChoice([s.value for s in DealStage])
    probability = fuzzy.FuzzyFloat(0.0, 1.0)

    # Intelligence
    health_score = fuzzy.FuzzyFloat(0.0, 100.0)
    risk_level = factory.Iterator(['low', 'medium', 'high'])

    # Negotiation state
    negotiation_state = fuzzy.FuzzyChoice([s.value for s in NegotiationState])

    # Engagement tracking
    last_engagement_at = factory.Faker('date_time_this_year')
    last_followup_at = factory.Faker('date_time_this_year')
    followup_count = fuzzy.FuzzyInteger(0, 50)

    # External ID
    external_id = factory.Faker('uuid4')

    # Metadata
    metadata_json = factory.LazyFunction(dict)


class CommissionEntryFactory(BaseFactory):
    """Factory for creating CommissionEntry instances (Sales commissions)."""

    class Meta:
        model = CommissionEntry

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')  # Override in tests
    deal_id = factory.Faker('uuid4')  # Override in tests with DealFactory
    amount = fuzzy.FuzzyFloat(0.0, 50000.0)

    # Optional payee
    payee_id = factory.Faker('uuid4')

    # Status
    status = fuzzy.FuzzyChoice([s.value for s in CommissionStatus])

    # Invoice link
    invoice_id = factory.Faker('uuid4')

    # Currency
    currency = "USD"

    # Timestamps
    calculated_at = factory.Faker('date_time_this_year')
    paid_at = factory.Faker('date_time_this_year')

    # Metadata
    metadata_json = factory.LazyFunction(dict)


class CallTranscriptFactory(BaseFactory):
    """Factory for creating CallTranscript instances (Call transcripts)."""

    class Meta:
        model = CallTranscript

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')  # Override in tests
    raw_transcript = factory.Faker('text', max_nb_chars=5000)

    # Optional deal link
    deal_id = factory.Faker('uuid4')  # Override in tests with DealFactory

    # Meeting metadata
    meeting_id = factory.Faker('uuid4')
    title = factory.Faker('sentence', nb_words=4)
    summary = factory.Faker('text', max_nb_chars=1000)

    # AI-extracted data
    objections = factory.LazyFunction(lambda: [
        {"objection": "Price too high", "severity": "medium"},
        {"objection": "Need to check with team", "severity": "low"}
    ])
    action_items = factory.LazyFunction(lambda: [
        {"task": "Send case study", "priority": "high"},
        {"task": "Schedule follow-up", "priority": "medium"}
    ])

    # Metadata
    metadata_json = factory.LazyFunction(dict)


class FollowUpTaskFactory(BaseFactory):
    """Factory for creating FollowUpTask instances (Sales tasks)."""

    class Meta:
        model = FollowUpTask

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')  # Override in tests
    deal_id = factory.Faker('uuid4')  # Override in tests with DealFactory
    description = factory.Faker('text', max_nb_chars=500)

    # Optional fields
    suggested_date = factory.Faker('date_time_this_month')
    is_completed = fuzzy.FuzzyChoice([True, False])

    # AI rationale
    ai_rationale = factory.Faker('text', max_nb_chars=500)
