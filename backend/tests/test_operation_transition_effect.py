"""Actual operation CAS and target writes share one scratch transaction."""
from contextlib import contextmanager
import hashlib
import pytest
from sqlalchemy import update
from core.models import UserConnection, TaskOperationRecord
from core import outbound_operation_claim as ops
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db

@pytest.fixture
def pending(source_world):
    factory, _ = source_world
    material = hashlib.sha256(b'isolated-transition-material').hexdigest()
    claim = ops.claim_generic_operation(workspace_id='workspace', tenant_id='tenant',
        operation_id='isolated-transition', action='test_transition', payload_hash=material, db_factory=factory)
    assert ops.mark_status(claim['record_id'], ops.DISPATCHING, expected_status=ops.CLAIMED,
        expected_payload_sha256=material, db_factory=factory)
    return factory, claim['record_id'], material


def test_losing_transition_rolls_back_factory_writes(pending):
    factory, record, material = pending
    @contextmanager
    def guarded():
        with factory() as db:
            db.execute(update(UserConnection).where(UserConnection.id == 'connection').values(connection_name='loser'))
            yield db
    assert not ops.mark_status(record, ops.SUCCEEDED, expected_status=ops.CLAIMED,
        expected_payload_sha256=material, db_factory=guarded)
    with factory() as db:
        assert db.get(UserConnection, 'connection').connection_name == 'Synthetic'
        assert db.get(TaskOperationRecord, record).status == ops.DISPATCHING


def test_winner_commits_effect_and_receipt_together(pending):
    factory, record, material = pending
    def effect(db):
        db.execute(update(UserConnection).where(UserConnection.id == 'connection').values(connection_name='winner'))
    assert ops.mark_status(record, ops.SUCCEEDED, expected_status=ops.DISPATCHING,
        expected_payload_sha256=material, result={'proof': 'effect'}, transition_effect=effect, db_factory=factory)
    with factory() as db:
        assert db.get(UserConnection, 'connection').connection_name == 'winner'
        row = db.get(TaskOperationRecord, record)
        assert row.status == ops.SUCCEEDED and row.result_json == {'proof': 'effect'}


def test_peer_winner_does_not_run_effect(pending):
    factory, record, material = pending
    assert ops.mark_status(record, ops.UNCERTAIN_EFFECT, expected_status=ops.DISPATCHING, db_factory=factory)
    calls = []
    assert not ops.mark_status(record, ops.SUCCEEDED, expected_status=ops.DISPATCHING,
        expected_payload_sha256=material, transition_effect=lambda db: calls.append('effect'), db_factory=factory)
    assert calls == []


def test_effect_refusal_rolls_back_receipt_and_target(pending, caplog):
    factory, record, material = pending
    def effect(db):
        db.execute(update(UserConnection).where(UserConnection.id == 'connection').values(connection_name='partial'))
        raise ValueError('synthetic-private-detail')
    assert not ops.mark_status(record, ops.SUCCEEDED, expected_status=ops.DISPATCHING,
        expected_payload_sha256=material, result={'proof': 'uncommitted'}, transition_effect=effect, db_factory=factory)
    with factory() as db:
        row = db.get(TaskOperationRecord, record)
        assert row.status == ops.DISPATCHING and row.result_json is None
        assert db.get(UserConnection, 'connection').connection_name == 'Synthetic'
    assert 'synthetic-private-detail' not in caplog.text


@pytest.mark.parametrize('kind', ['coroutine', 'async_generator'])
def test_async_effect_cannot_certify_unexecuted_write(pending, kind):
    factory, record, material = pending
    async def effect(db):
        raise AssertionError('must not execute asynchronous effect')
    async def generator(db):
        yield 'not executed'
    assert not ops.mark_status(record, ops.SUCCEEDED, expected_status=ops.DISPATCHING,
        expected_payload_sha256=material, transition_effect=effect if kind == 'coroutine' else generator, db_factory=factory)
    with factory() as db: assert db.get(TaskOperationRecord, record).status == ops.DISPATCHING


def test_unconditional_transition_cannot_attach_effect(pending):
    factory, record, material = pending
    calls = []
    assert not ops.mark_status(record, ops.SUCCEEDED, transition_effect=lambda db: calls.append('effect'), db_factory=factory)
    assert calls == []


def test_orm_effect_is_flushed_before_receipt_commit(pending):
    factory, record, material = pending
    def effect(db):
        db.get(UserConnection, 'connection').connection_name = 'orm-winner'
    assert ops.mark_status(record, ops.SUCCEEDED, expected_status=ops.DISPATCHING,
        expected_payload_sha256=material, result={'proof': 'orm-effect'}, transition_effect=effect, db_factory=factory)
    with factory() as db:
        assert db.get(UserConnection, 'connection').connection_name == 'orm-winner'
        assert db.get(TaskOperationRecord, record).status == ops.SUCCEEDED
