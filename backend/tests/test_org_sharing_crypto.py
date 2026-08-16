"""Org Sharing Crypto — Ed25519 sign/verify for org profiles/bundles (Phase 1).

Key file isolation via ATOM_ORG_SHARING_KEY_FILE; no network; fail-closed
verification semantics.
"""
import base64

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import org_sharing_crypto
from core.models import Base, OrgPublicKey


@pytest.fixture()
def key_file(tmp_path, monkeypatch):
    path = tmp_path / "org_sharing_key"
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(path))
    return path


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[OrgPublicKey.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestKeypairLifecycle:
    def test_generate_and_persist(self, key_file):
        key = org_sharing_crypto.get_or_create_private_key()
        assert key_file.exists()
        again = org_sharing_crypto.get_or_create_private_key()
        assert org_sharing_crypto.public_key_bytes(key) == org_sharing_crypto.public_key_bytes(again)

    def test_permissions_0600(self, key_file):
        import os
        org_sharing_crypto.get_or_create_private_key()
        assert (os.stat(key_file).st_mode & 0o777) == 0o600

    def test_corrupt_key_file_regenerates(self, key_file):
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(b"garbage")
        key = org_sharing_crypto.get_or_create_private_key()
        assert len(org_sharing_crypto.public_key_bytes(key)) == 32

    def test_public_key_b64_roundtrip(self, key_file):
        pub = org_sharing_crypto.public_key_b64(org_sharing_crypto.get_or_create_private_key())
        raw = base64.b64decode(pub)
        assert len(raw) == 32
        assert org_sharing_crypto.fingerprint(raw) == org_sharing_crypto.fingerprint(raw)


class TestSignVerify:
    def test_sign_then_verify_own(self, key_file, db):
        sig, pub = org_sharing_crypto.sign_payload(b"hello")
        assert org_sharing_crypto.verify_payload(db, b"hello", sig, "default") is True

    def test_tampered_payload_fails(self, key_file, db):
        sig, _ = org_sharing_crypto.sign_payload(b"hello")
        assert org_sharing_crypto.verify_payload(db, b"tampered", sig, "default") is False

    def test_bad_base64_signature_fails(self, key_file, db):
        assert org_sharing_crypto.verify_payload(db, b"x", "!!!not-b64!!!", "default") is False

    def test_foreign_key_does_not_verify(self, key_file, db, tmp_path, monkeypatch):
        sig, _ = org_sharing_crypto.sign_payload(b"hello")
        # Swap in a different instance key — old signature must fail.
        other = tmp_path / "other_key"
        monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(other))
        org_sharing_crypto.get_or_create_private_key()
        assert org_sharing_crypto.verify_payload(db, b"hello", sig, "default") is False


class TestRegistry:
    def test_register_peer_and_verify(self, key_file, db, tmp_path, monkeypatch):
        # Member A signs with its own key.
        sig, pub = org_sharing_crypto.sign_payload(b"payload")
        # Member B (this instance) generates a DIFFERENT key...
        other = tmp_path / "b_key"
        monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(other))
        org_sharing_crypto.get_or_create_private_key()
        # ...and does not trust A yet.
        assert org_sharing_crypto.verify_payload(db, b"payload", sig, "ws1") is False
        # After registering A's public key it verifies.
        row = org_sharing_crypto.register_public_key(db, pub, label="member-a", workspace_id="ws1")
        assert row.is_own is False
        assert len(row.fingerprint) == 64
        assert org_sharing_crypto.verify_payload(db, b"payload", sig, "ws1") is True

    def test_register_idempotent(self, key_file, db):
        pub = org_sharing_crypto.public_key_b64(org_sharing_crypto.get_or_create_private_key())
        org_sharing_crypto.register_public_key(db, pub, label="one", workspace_id="ws1")
        row = org_sharing_crypto.register_public_key(db, pub, label="renamed", workspace_id="ws1")
        assert row.label == "renamed"
        assert db.query(OrgPublicKey).count() == 1

    def test_register_rejects_wrong_length(self, key_file, db):
        with pytest.raises(ValueError):
            org_sharing_crypto.register_public_key(db, base64.b64encode(b"short").decode(), "bad", "ws1")

    def test_ensure_own_registers(self, key_file, db):
        pub = org_sharing_crypto.ensure_own_key_registered(db, "ws1", "t1")
        row = db.query(OrgPublicKey).filter_by(public_key=pub).one()
        assert row.is_own is True
        # Calling again is idempotent.
        org_sharing_crypto.ensure_own_key_registered(db, "ws1", "t1")
        assert db.query(OrgPublicKey).filter_by(is_own=True).count() == 1
