"""Registered trigger consumption uses durable event material, not connector reads."""
import asyncio
import copy
from unittest.mock import AsyncMock
import pytest
from core.workflow_engine import WorkflowEngine
from core.execution_state_manager import EXECUTION_SCOPE_KEY
from core.workflow_event_admission import payload_digest


def admitted():
    binding = {'connection_id': 'connection', 'source': 'synthetic-mail',
               'event_type': 'message.created', 'enabled': True}
    event = dict(connection_id='connection', source='synthetic-mail', event_type='message.created',
                 tenant_id='tenant', workspace_id='workspace', owner_id='owner',
                 provider_event_id='provider-event', payload={'invoice': 'synthetic-one'})
    snapshot = {'id': 'workflow', 'nodes': [{'id': 'trigger', 'type': 'trigger',
                 'config': {'event_subscription': copy.deepcopy(binding)}}]}
    receipt = dict(event, execution_id='evt_one', workflow_id='workflow', subscription_id='trigger',
                   payload_digest=payload_digest(event['payload']), workflow_snapshot=snapshot)
    receipt.pop('payload')
    state = {'execution_id': 'evt_one', 'workflow_id': 'workflow',
             'context': {'_atom_event_admission': receipt},
             'input_data': {'event': event, EXECUTION_SCOPE_KEY: {
                 'user_id': 'owner', 'tenant_id': 'tenant', 'workspace_id': 'workspace'}}}
    step = {'id': 'trigger', 'type': 'trigger', 'service': 'synthetic-mail',
            'action': 'message.created', 'event_subscription': binding}
    return step, state


def test_registered_trigger_consumes_durable_event_without_connector():
    step, state = admitted()
    engine = WorkflowEngine()
    engine._execute_step = AsyncMock(side_effect=AssertionError('source must not be called'))
    before = copy.deepcopy(state)
    output = asyncio.run(engine._execute_dispatched_step(step, {}, state))
    assert output['result'] == state['input_data']['event']
    assert output['execution_method'] == 'durable_event_admission'
    output['result']['payload']['invoice'] = 'mutated'
    assert state == before
    engine._execute_step.assert_not_awaited()


@pytest.mark.parametrize('case', ['manual', 'payload', 'source', 'node', 'disabled', 'owner', 'snapshot'])
def test_mismatched_trigger_refuses_without_source_dispatch(case):
    step, state = admitted()
    if case == 'manual':
        state['execution_id'] = 'manual-one'
    elif case == 'payload':
        state['input_data']['event']['payload']['invoice'] = 'different'
    elif case == 'source':
        state['input_data']['event']['connection_id'] = 'different'
    elif case == 'node':
        step['id'] = 'other'
    elif case == 'disabled':
        step['event_subscription']['enabled'] = False
    elif case == 'owner':
        state['input_data']['event']['owner_id'] = 'other'
    else:
        state['context']['_atom_event_admission']['workflow_snapshot']['nodes'] = []
    engine = WorkflowEngine()
    engine._execute_step = AsyncMock(side_effect=AssertionError('no source dispatch'))
    with pytest.raises(ValueError):
        asyncio.run(engine._execute_dispatched_step(step, {}, state))
    engine._execute_step.assert_not_awaited()


def test_ordinary_action_uses_existing_dispatch():
    engine = WorkflowEngine()
    engine._execute_step = AsyncMock(return_value={'status': 'success', 'result': 'ordinary'})
    step = {'id': 'action', 'service': 'synthetic', 'action': 'send'}
    assert asyncio.run(engine._execute_dispatched_step(step, {'body': 'saved'}, {}))['result'] == 'ordinary'
    engine._execute_step.assert_awaited_once_with(step, {'body': 'saved'})


def test_selected_event_root_runs_only_its_reachable_branch_without_mutating_snapshot():
    step, state = admitted()
    snapshot = state['context']['_atom_event_admission']['workflow_snapshot']
    snapshot['nodes'] += [
        {'id': 'selected-action', 'type': 'action', 'config': {}},
        {'id': 'other-trigger', 'type': 'trigger', 'config': {
            'event_subscription': dict(step['event_subscription'], event_type='other.event')}},
        {'id': 'other-action', 'type': 'action', 'config': {}},
        {'id': 'unrelated-root', 'type': 'action', 'config': {}},
    ]
    snapshot['connections'] = [{'source': 'trigger', 'target': 'selected-action'},
                               {'source': 'other-trigger', 'target': 'other-action'}]
    before = copy.deepcopy(snapshot)
    engine = WorkflowEngine()
    engine._execute_step = AsyncMock(side_effect=AssertionError('no connector during projection'))
    projected = asyncio.run(engine._project_admitted_event_graph(snapshot, state))
    assert {n['id'] for n in projected['nodes']} == {'trigger', 'selected-action'}
    assert {s['id'] for s in projected['steps']} == {'trigger', 'selected-action'}
    assert snapshot == before
    engine._execute_step.assert_not_awaited()


from tests.test_workflow_event_reservation import event_db


def test_real_reserved_graph_consumes_trigger_and_dispatches_only_selected_action(event_db, monkeypatch, tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from core.execution_state_manager import ExecutionStateManager
    from unittest.mock import Mock
    sync_engine = create_engine(f"sqlite:///{tmp_path / 'workflow_event_reservations.db'}")
    monkeypatch.setattr('core.workflow_engine.get_db_session', lambda: Session(sync_engine))
    monkeypatch.setattr('core.workflow_engine.get_connection_manager', lambda: AsyncMock())
    async def scenario():
        step, state = admitted()
        receipt = state['context']['_atom_event_admission']
        workflow = receipt['workflow_snapshot']
        workflow['name'] = 'Synthetic source routing'
        workflow['nodes'] += [
            {'id': 'effect', 'type': 'action', 'config': {
                'service': 'synthetic', 'action': 'record',
                'parameters': {'record': '${input.event.payload.invoice}'}}},
            {'id': 'other-trigger', 'type': 'trigger', 'config': {
                'event_subscription': dict(step['event_subscription'], event_type='other.event')}},
            {'id': 'other-effect', 'type': 'action', 'config': {'service': 'synthetic', 'action': 'other'}},
        ]
        workflow['connections'] = [{'source': 'trigger', 'target': 'effect'},
                                    {'source': 'other-trigger', 'target': 'other-effect'}]
        before = copy.deepcopy(workflow)
        manager = ExecutionStateManager()
        reserved, created = await manager.reserve_event_execution(
            'workflow', state['input_data'], execution_id='evt_one',
            identity={'user_id': 'owner', 'tenant_id': 'tenant', 'workspace_id': 'workspace'}, admission=receipt)
        assert created
        engine = WorkflowEngine()
        engine.state_manager = manager
        engine._publish_orchestration_event = Mock()
        engine._execute_step = AsyncMock(return_value={'status': 'success', 'result': {'recorded': True}})
        assert await engine.launch_reserved_event_execution('evt_one', reserved, AsyncMock(return_value=True))
        await asyncio.gather(*list(engine._background_tasks))
        final = await manager.get_execution_state('evt_one')
        assert final['status'] == 'COMPLETED', final
        engine._execute_step.assert_awaited_once()
        args = engine._execute_step.await_args.args
        assert args[0]['id'] == 'effect'
        assert args[1] == {'record': 'synthetic-one'}
        assert final['steps']['trigger']['output']['execution_method'] == 'durable_event_admission'
        assert final['context']['_atom_event_admission']['workflow_snapshot'] == before
    try:
        asyncio.run(asyncio.wait_for(scenario(), timeout=20))
    finally:
        sync_engine.dispose()
