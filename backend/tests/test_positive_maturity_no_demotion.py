"""Positive evidence must not demote an explicitly promoted low-score agent."""
import pytest
from sqlalchemy.orm import sessionmaker
from core.models import AgentRegistry
from core.agent_governance_service import AgentGovernanceService
from tests.test_generic_oracle_mutation_contract import scratch_db

@pytest.mark.parametrize('tier,score,positive,expected_tier,expected_score', [
    ('autonomous', 0.35, True, 'autonomous', 0.36),
    ('autonomous', 0.35, False, 'student', 0.33),
    ('autonomous', 0.95, True, 'autonomous', 0.96),
    ('student', 0.49, True, 'student', 0.50),
    ('paused', 0.35, True, 'paused', 0.36),
    ('stopped', 0.35, True, 'stopped', 0.36),
])
def test_outcome_direction_preserves_authority_and_evidence_gates(
        scratch_db, monkeypatch, tier, score, positive, expected_tier, expected_score):
    monkeypatch.setenv('ATOM_PROMOTION_EVIDENCE_GATE', '1')
    Session = sessionmaker(bind=scratch_db['engine'])
    with Session() as db:
        db.add(AgentRegistry(id='direction-agent', name='Direction agent',
            category='acceptance', module_path='core.generic_agent',
            class_name='GenericAgent', workspace_id='default', tenant_id='default',
            status=tier, confidence_score=score, configuration={},
            promotion_episode_floor=3))
        db.commit()
        AgentGovernanceService(db)._update_confidence_score(
            'direction-agent', positive=positive, impact_level='low')
    with Session() as db:
        row = db.get(AgentRegistry, 'direction-agent')
        assert row.confidence_score == expected_score
        assert row.status == expected_tier
