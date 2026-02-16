"""
Factories for training models: BlockedTriggerContext, AgentProposal.
"""

import factory
from factory import fuzzy
from datetime import datetime
from tests.factories.base import BaseFactory
from core.models import BlockedTriggerContext, AgentProposal, ProposalStatus


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
    """Factory for creating AgentProposal instances."""

    class Meta:
        model = AgentProposal

    # Required fields
    id = factory.Faker('uuid4')
    agent_id = factory.Faker('uuid4')
    agent_name = factory.Faker('company')

    # Proposal details
    proposal_type = fuzzy.FuzzyChoice(['training', 'action', 'analysis'])
    title = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('text', max_nb_chars=500)

    # Proposed action / training
    proposed_action = factory.LazyAttribute(lambda o: None)
    reasoning = factory.Faker('text', max_nb_chars=300)

    # Training-specific fields
    learning_objectives = factory.LazyAttribute(lambda o: None)
    capability_gaps = factory.LazyAttribute(lambda o: None)
    training_scenario_template = factory.LazyAttribute(lambda o: None)

    # Duration estimation
    estimated_duration_hours = fuzzy.FuzzyFloat(1.0, 100.0)
    duration_estimation_confidence = fuzzy.FuzzyFloat(0.5, 1.0)
    duration_estimation_reasoning = factory.Faker('text', max_nb_chars=200)
    user_override_duration_hours = factory.LazyAttribute(lambda o: None)
    hours_per_day_limit = factory.LazyAttribute(lambda o: None)

    # Status
    status = fuzzy.FuzzyChoice([s.value for s in ProposalStatus])
    human_review = factory.Faker('text', max_nb_chars=300)
    reviewed_at = factory.LazyAttribute(
        lambda o: datetime.now() if o.status in ['approved', 'rejected'] else None
    )
