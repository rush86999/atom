"""
Factories for training models: BlockedTriggerContext, AgentProposal.

NOTE (legacy-kwarg schema drift): ``AgentProposalFactory`` previously
declared many fields that no longer exist on ``AgentProposal``:

    proposed_action, reasoning, learning_objectives, capability_gaps,
    training_scenario_template, estimated_duration_hours,
    duration_estimation_confidence, duration_estimation_reasoning,
    user_override_duration_hours, hours_per_day_limit, proposed_by

Those columns were removed when ``AgentProposal`` was refactored to use
``proposal_data`` (JSON) + ``status`` SQL enum ('pending_approval' /
'approved' / 'rejected' / 'cancelled' / 'executed' / 'execution_failed').
``proposed_action`` and ``reasoning`` survived as read-only @property
helpers, which is why assigning to them raised
``AttributeError: property 'proposed_action' of 'AgentProposal' object
has no setter``.

The factory now declares only canonical columns. Same migration pattern
as the CanvasAudit refactor.
"""

import factory
from factory import fuzzy
from tests.factories.base import BaseFactory
from core.models import BlockedTriggerContext, AgentProposal


# Canonical AgentProposal status values (matches the SQLEnum on the model).
_AGENT_PROPOSAL_STATUSES = [
    'pending_approval', 'approved', 'rejected',
    'cancelled', 'executed', 'execution_failed',
]


class BlockedTriggerContextFactory(BaseFactory):
    """Factory for creating BlockedTriggerContext instances."""

    class Meta:
        model = BlockedTriggerContext

    # Required fields
    id = factory.Faker('uuid4')
    agent_id = factory.Faker('uuid4')
    agent_name = factory.Faker('company')

    # Maturity state
    agent_maturity_at_block = fuzzy.FuzzyChoice(['student', 'intern', 'supervised', 'autonomous'])
    confidence_score_at_block = fuzzy.FuzzyFloat(0.0, 1.0)

    # Trigger source
    trigger_source = fuzzy.FuzzyChoice(['MANUAL', 'DATA_SYNC', 'WORKFLOW_ENGINE', 'AI_COORDINATOR'])
    trigger_type = fuzzy.FuzzyChoice(['webhook', 'schedule', 'event', 'manual'])
    trigger_context = factory.LazyFunction(dict)

    # Routing decision
    routing_decision = fuzzy.FuzzyChoice(['training', 'proposal', 'supervision', 'execution'])
    block_reason = factory.Faker('text', max_nb_chars=300)


class AgentProposalFactory(BaseFactory):
    """Factory for creating AgentProposal instances.

    Only declares columns that exist on the current ``AgentProposal``
    model. Use ``proposal_data=`` to seed ``proposed_action`` /
    ``reasoning`` (those are read-only @property helpers derived from
    ``proposal_data``).
    """

    class Meta:
        model = AgentProposal

    # Required NOT-NULL fields
    id = factory.Faker('uuid4')
    tenant_id = "default"
    user_id = factory.Faker('uuid4')
    agent_id = factory.Faker('uuid4')
    agent_name = factory.Faker('company')

    # Proposal content (canonical schema)
    proposal_type = fuzzy.FuzzyChoice(['action', 'workflow', 'analysis'])
    title = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('text', max_nb_chars=500)
    proposal_data = factory.LazyFunction(dict)

    # Status (canonical SQL enum values; NOT ProposalStatus Python enum,
    # which is stale and out of sync with the model's SQLEnum)
    status = fuzzy.FuzzyChoice(_AGENT_PROPOSAL_STATUSES)

    # Optional fields (kept lazy so they default to None unless overridden)
    approved_by = factory.LazyAttribute(lambda o: None)
    approved_at = factory.LazyAttribute(
        lambda o: None if o.status not in ('approved', 'rejected') else factory.Faker('date_time_this_year').generate({})
    )
