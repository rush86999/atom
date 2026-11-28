"""Shared credential claim binds actual encrypted grant and raw source scope."""
from datetime import datetime, timedelta, timezone
import pytest
from core.connection_service import ConnectionService
from core.models import User, UserConnection
from core.workflow_event_source_registration import SourceRegistrationError
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


def test_shared_commitment_preserves_existing_renewal_algorithm(enrollment_world):
    from core.workflow_event_source_binding import credential_commitment, snapshot, claim
    from core.workflow_event_source_renewal import _credential_commitment
    factory, _, _, _ = enrollment_world
    with factory() as db:
        before = db.get(UserConnection, 'connection').updated_at
        frozen = snapshot(db, 'owner', 'connection', 'outlook', expected_credentials={'access_token':'synthetic'})
        assert credential_commitment(db, 'connection') == _credential_commitment(db, 'connection')
        claim(db, frozen)
        db.commit()
    with factory() as db:
        assert db.get(UserConnection, 'connection').updated_at == before


@pytest.mark.parametrize('change', ['grant', 'expiry', 'actor', 'scope', 'connection_status'])
def test_claim_preserves_peer_reconnect_authority_and_scope(enrollment_world, change):
    from core.workflow_event_source_binding import snapshot, claim
    factory, _, _, _ = enrollment_world
    with factory() as db:
        frozen = snapshot(db, 'owner', 'connection', 'outlook')
    with factory() as peer:
        if change == 'grant': peer.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token':'peer-private'})
        elif change == 'expiry': peer.get(UserConnection, 'connection').expires_at = datetime.now(timezone.utc)+timedelta(hours=1)
        elif change == 'actor': peer.get(User, 'owner').role = 'member'
        elif change == 'scope': peer.get(UserConnection, 'connection').workspace_id = 'peer-space'
        else: peer.get(UserConnection, 'connection').status = 'revoked'
        peer.commit()
    with factory() as db:
        with pytest.raises(SourceRegistrationError):
            claim(db, frozen)
        db.rollback()
    with factory() as db:
        if change == 'grant': assert ConnectionService()._decrypt(db.get(UserConnection, 'connection').credentials)['access_token'] == 'peer-private'
        elif change == 'actor': assert db.get(User, 'owner').role == 'member'
        elif change == 'scope': assert db.get(UserConnection, 'connection').workspace_id == 'peer-space'
        elif change == 'connection_status': assert db.get(UserConnection, 'connection').status == 'revoked'
        else: assert db.get(UserConnection, 'connection').expires_at is not None


@pytest.mark.parametrize('case', ['plaintext', 'malformed', 'expired', 'different_private'])
def test_snapshot_refuses_unverified_credential_material(enrollment_world, case):
    from core.workflow_event_source_binding import snapshot
    factory, _, _, _ = enrollment_world
    with factory() as db:
        row = db.get(UserConnection, 'connection')
        if case == 'plaintext': row.credentials = '{"access_token":"plaintext-private"}'
        elif case == 'malformed': row.credentials = 'not-encrypted'
        elif case == 'expired': row.expires_at = datetime.now(timezone.utc)-timedelta(hours=1)
        db.commit()
    with factory() as db:
        with pytest.raises(SourceRegistrationError):
            snapshot(db, 'owner', 'connection', 'outlook',
                     expected_credentials={'access_token':'different-private'} if case == 'different_private' else None)


def test_expiry_during_provider_lookup_refuses_claim(enrollment_world, monkeypatch):
    from core import workflow_event_source_binding as proof
    factory, _, _, _ = enrollment_world
    expiry = datetime.now(timezone.utc)+timedelta(minutes=1)
    with factory() as db:
        db.get(UserConnection, 'connection').expires_at = expiry
        db.commit()
    with factory() as db:
        frozen = proof.snapshot(db, 'owner', 'connection', 'outlook')
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return (expiry+timedelta(seconds=1)).astimezone(tz)
    monkeypatch.setattr(proof, 'datetime', Clock)
    with factory() as db:
        with pytest.raises(SourceRegistrationError, match='SOURCE_CREDENTIALS_EXPIRED'):
            proof.claim(db, frozen)
        db.rollback()
