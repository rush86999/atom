"""A durable information pause is neither a maturity success nor a failure."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from sqlalchemy.orm import sessionmaker
from core.generic_agent import GenericAgent
from core.models import AgentRegistry, AgentExecution
from tests.test_generic_oracle_mutation_contract import scratch_db


def test_repeated_waits_preserve_maturity_and_same_durable_execution(scratch_db):
    Session = sessionmaker(bind=scratch_db['engine'])
    with Session() as db:
        db.add(AgentRegistry(id='wait-agent', name='Wait agent', category='acceptance',
            module_path='core.generic_agent', class_name='GenericAgent',
            workspace_id='default', tenant_id='default', status='autonomous',
            confidence_score=0.35, configuration={}))
        db.commit()
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = 'wait-agent'
    agent.workspace_id = 'default'
    agent.tenant_id = 'default'
    agent.config = {}
    agent.world_model = SimpleNamespace(record_experience=AsyncMock())
    for question in ['title', 'priority']:
        asyncio.run(agent._record_execution('Create the closing task', {
            'status': 'waiting', 'output': 'Need '+question,
            'steps': [], 'wait_receipt': {'question': question},
            'resume_state': {'history': []},
        }, {'execution_id': 'one-execution'}))
        with Session() as db:
            row = db.get(AgentRegistry, agent.id)
            assert row.confidence_score == 0.35, 'a pending fact was graded as failure'
            assert row.status == 'autonomous'
            execution = db.get(AgentExecution, 'one-execution')
            assert execution is not None and execution.status == 'waiting'
            assert execution.completed_at is None
            assert db.query(AgentExecution).count() == 1
    assert agent.world_model.record_experience.await_count == 2
