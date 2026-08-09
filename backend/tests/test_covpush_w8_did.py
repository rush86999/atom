"""Coverage wave 8 — core.identity.did_manager.

Hermetic: in-memory DIDManager; DB persistence paths use monkeypatched
get_db_session with an in-memory SQLite engine; cryptography exercised for
real when available, plus the no-crypto fallback via patched CRYPTO_AVAILABLE.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from core.identity.did_manager import (
    CRYPTO_AVAILABLE,
    DIDConfig,
    DIDDocument,
    DIDKey,
    DIDManager,
    DIDMethod,
    DIDResolutionResult,
    DIDService,
    DIDType,
    DIDVerificationMethod,
    _is_valid_base58,
    get_did_manager,
)


class TestDidPrimitives:
    def test_base58_validation(self):
        assert _is_valid_base58("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        assert not _is_valid_base58("0OI")  # excluded chars (0, O, I)
        assert not _is_valid_base58("abc-")  # dash not in alphabet

    def test_config_defaults(self):
        cfg = DIDConfig()
        assert cfg.method == DIDMethod.ATOM
        assert cfg.key_type == "ed25519"
        assert cfg.cache_ttl_seconds == 300
        assert cfg.enable_key_rotation is True

    def test_didkey_hash(self):
        k1 = DIDKey(id="k1")
        k2 = DIDKey(id="k1")
        assert hash(k1) == hash(k2)

    def test_did_document_to_dict(self):
        vm = DIDVerificationMethod(id="did:atom:a#key-1", controller="did:atom:a", public_key_base58="pk")
        svc = DIDService(id="did:atom:a#svc", type="AgentService", service_endpoint="http://x")
        doc = DIDDocument(
            id="did:atom:a",
            controller="did:atom:a",
            verification_method=[vm],
            authentication=["did:atom:a#key-1"],
            service=[svc],
            deactivated=False,
        )
        d = doc.to_dict()
        assert d["@context"] == ["https://www.w3.org/ns/did/v1"]
        assert d["verificationMethod"][0]["publicKeyBase58"] == "pk"
        assert d["service"][0]["serviceEndpoint"] == "http://x"
        assert d["deactivated"] is False

    def test_resolution_result_to_dict(self):
        r = DIDResolutionResult(did="did:atom:a")
        assert r.to_dict()["didDocument"] is None
        r2 = DIDResolutionResult(did="did:atom:a", did_document=DIDDocument(id="did:atom:a"))
        assert r2.to_dict()["didDocument"]["id"] == "did:atom:a"


class TestDidManager:
    def test_generate_did_atom(self):
        m = DIDManager()
        assert m.generate_did(DIDType.AGENT, "agent-1") == "did:atom:agent:agent-1"
        assert m.generate_did(DIDType.INSTANCE, "inst-1", instance_id="i1") == "did:atom:i1:instance:inst-1"

    def test_generate_did_key_method(self):
        m = DIDManager(config=DIDConfig(method=DIDMethod.KEY))
        did = m.generate_did(DIDType.AGENT, "agent-1")
        assert did.startswith("did:key:z")
        assert len(did) == len("did:key:z") + 16

    def test_generate_did_web_fallback_to_atom(self):
        m = DIDManager(config=DIDConfig(method=DIDMethod.WEB))
        did = m.generate_did(DIDType.USER, "u1")
        assert did.startswith("did:atom:")

    def test_create_and_resolve_document(self):
        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, DIDType.AGENT)
        assert doc.id == did
        assert doc.authentication
        assert doc.assertion_method
        assert doc.capability_invocation
        assert doc.capability_delegation
        assert len(doc.verification_method) == 1
        result = m.resolve_did(did)
        assert result.did_document is doc
        assert result.resolution_metadata == {"resolved": "locally"}
        # cached resolution
        result2 = m.resolve_did(did)
        assert result2.resolution_metadata == {"from_cache": True}

    def test_resolve_with_services(self):
        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        svc = DIDService(id="s1", type="Endpoint", service_endpoint="https://x")
        doc = m.create_did_document(did, DIDType.AGENT, services=[svc])
        assert doc.service[0].service_endpoint == "https://x"

    def test_resolve_did_cache_expired(self):
        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        m.create_did_document(did, DIDType.AGENT)
        m.resolve_did(did)
        # Force cache expiry
        cached_at = datetime.now() - timedelta(seconds=m.config.cache_ttl_seconds + 10)
        m._resolution_cache[did] = (m._did_documents[did], cached_at)
        result = m.resolve_did(did)
        assert result.resolution_metadata == {"resolved": "locally"}

    def test_resolve_did_cache_disabled(self):
        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        m.create_did_document(did, DIDType.AGENT)
        m.resolve_did(did)
        result = m.resolve_did(did, use_cache=False)
        assert "from_cache" not in result.resolution_metadata

    def test_resolve_unsupported_method(self):
        m = DIDManager()
        result = m.resolve_did("did:btcr:xyz")
        assert result.did_document is None
        assert "error" in result.resolution_metadata

    def test_resolve_unknown_atom_did(self):
        m = DIDManager()
        result = m.resolve_did("did:atom:agent:ghost")
        assert result.did_document is None
        assert result.resolution_metadata["error"] == "DID not found"

    def test_resolve_atom_via_federation(self):
        m = DIDManager()
        m.register_federation_instance("i1", "https://peer.example")
        result = m._resolve_atom_did("did:atom:i1:agent:a1")
        assert result.did_document is None
        # The federation error must surface (not be masked as "DID not found").
        assert result.resolution_metadata["error"] == "Federation resolution not implemented"

    def test_resolve_web_did(self):
        m = DIDManager()
        result = m.resolve_did("did:web:example.com")
        assert result.did_document is None
        assert "Web resolution not implemented" in result.resolution_metadata["error"]
        # DEAD-CODE note: the invalid-format branch (len(parts) < 3) is
        # unreachable via resolve_did — "did:web:" always splits into >=3
        # parts — so exercise the private method directly for line coverage.
        result2 = m._resolve_web_did("did:web")
        assert "Invalid did:web format" in result2.resolution_metadata["error"]

    def test_resolve_key_did(self):
        m = DIDManager()
        result = m.resolve_did("did:key:z123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        assert result.did_document is not None
        assert result.did_document.verification_method[0].public_key_base58 == (
            "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        )

    def test_resolve_key_did_invalid_suffix(self):
        m = DIDManager()
        # GARBAGE contains invalid base58 chars (O, 0, l, I) — must NOT
        # synthesize a document (BUG-037 regression guard).
        result = m.resolve_did("did:key:zGARBAGE0Il")
        assert result.did_document is None
        assert "not valid base58" in result.resolution_metadata["error"]
        # empty suffix
        result2 = m.resolve_did("did:key:z")
        assert result2.did_document is None
        # no 'z' prefix / short form
        result3 = m.resolve_did("did:key:12345")
        assert result3.did_document is None
        assert "Invalid did:key format" in result3.resolution_metadata["error"]
        result4 = m._resolve_key_did("did:key")
        assert "Invalid did:key format" in result4.resolution_metadata["error"]

    def test_extract_instance_id(self):
        m = DIDManager()
        assert m._extract_instance_id_from_did("did:atom:i1:agent:a1") == "i1"
        assert m._extract_instance_id_from_did("did:atom:agent:a1") is None
        assert m._extract_instance_id_from_did("did:web:x") is None

    def test_verify_signature_roundtrip(self):
        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, DIDType.AGENT)
        key_id = doc.authentication[0]
        key = m._keys[key_id]
        message = b"hello world"
        if not CRYPTO_AVAILABLE:  # pragma: no cover
            pytest.skip("cryptography not installed")
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(key.private_key_base58))
        signature = private_key.sign(message)
        assert m.verify_signature(did, message, signature) is True
        assert m.verify_signature(did, b"tampered", signature) is False

    def test_verify_signature_crypto_unavailable(self):
        with patch("core.identity.did_manager.CRYPTO_AVAILABLE", False):
            m = DIDManager()
            assert m.verify_signature("did:atom:x", b"m", b"s") is False

    def test_verify_signature_no_doc(self):
        m = DIDManager()
        assert m.verify_signature("did:atom:ghost", b"m", b"s") is False

    def test_verify_signature_no_verification_method(self):
        m = DIDManager()
        doc = DIDDocument(id="did:atom:a")
        m._did_documents["did:atom:a"] = doc
        assert m.verify_signature("did:atom:a", b"m", b"s") is False

    def test_verify_signature_key_not_found(self):
        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        m.create_did_document(did, DIDType.AGENT)
        # Wipe keys → falls to by-public-key search → not found → False
        m._keys.clear()
        assert m.verify_signature(did, b"m", b"s") is False

    def test_verify_signature_by_public_key_match(self):
        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, DIDType.AGENT)
        vm = doc.verification_method[0]
        if not CRYPTO_AVAILABLE:  # pragma: no cover
            pytest.skip("cryptography not installed")
        from cryptography.hazmat.primitives.asymmetric import ed25519

        # Sign with the ORIGINAL private key, then hide it under a different
        # key id so only the by-public-key search can find it.
        original = m._keys[doc.authentication[0]]
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(original.private_key_base58)
        )
        message = b"msg"
        sig = private_key.sign(message)
        m._keys.clear()
        m._keys["other"] = DIDKey(
            id="other", public_key_base58=vm.public_key_base58,
            private_key_base58=original.private_key_base58,
        )
        assert m.verify_signature(did, message, sig) is True

    def test_verify_with_key_revoked(self):
        m = DIDManager()
        key = DIDKey(id="k", public_key_base58="00" * 32, revoked=True)
        assert m._verify_with_key(key, b"m", b"s") is False

    def test_verify_with_key_bad_public_key(self):
        m = DIDManager()
        key = DIDKey(id="k", public_key_base58="not-hex")
        assert m._verify_with_key(key, b"m", b"s") is False

    def test_rotate_key(self):
        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, DIDType.AGENT)
        assert m.rotate_key(did) is True
        assert len(doc.verification_method) == 2
        assert doc.version_id
        new_key_id = doc.authentication[-1]
        assert new_key_id in m._keys
        assert m.rotate_key("did:atom:nope") is False

    def test_deactivate_did(self):
        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, DIDType.AGENT)
        assert m.deactivate_did(did) is True
        assert doc.deactivated is True
        # All keys for this DID revoked
        for key in m._keys.values():
            assert key.revoked is True
        assert m.deactivate_did("did:atom:nope") is False

    def test_get_statistics(self):
        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        m.create_did_document(did, DIDType.AGENT)
        m.register_federation_instance("i1", "https://x")
        m.resolve_did(did)
        stats = m.get_statistics()
        assert stats["total_dids"] == 1
        assert stats["total_keys"] >= 1
        assert stats["active_dids"] == 1
        assert stats["federation_instances"] == 1
        assert stats["cache_size"] == 1

    def test_generate_keypair_crypto_unavailable(self):
        with patch("core.identity.did_manager.CRYPTO_AVAILABLE", False):
            m = DIDManager()
            key = m._generate_keypair()
            assert len(key.private_key_base58) == 64
            assert len(key.public_key_base58) == 64

    def test_generate_keypair_crypto_available(self):
        m = DIDManager()
        key = m._generate_keypair()
        assert key.public_key_base58
        assert key.private_key_base58

    def test_version_id(self):
        m = DIDManager()
        v1 = m._generate_version_id()
        v2 = m._generate_version_id()
        assert len(v1) == 16
        assert v1 != v2

    def test_register_federation_instance(self):
        m = DIDManager()
        m.register_federation_instance("i2", "https://peer2")
        assert m._federation_registry["i2"] == "https://peer2"

    @staticmethod
    def _commit_cm(session):
        """Mirror core.database.get_db_session: commit on context exit."""
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            try:
                yield session
                session.commit()
            finally:
                pass

        return _cm()

    def test_persist_did_writes_and_updates(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from core.models import Base, FederationDID

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        m = DIDManager()
        did = m.generate_did(DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, DIDType.AGENT)

        with patch("core.database.get_db_session", return_value=self._commit_cm(session)):
            m._persist_did(did, DIDType.AGENT, doc, list(m._keys.values())[0])
            row = session.query(FederationDID).filter(FederationDID.did == did).first()
            assert row is not None
            assert row.entity_type == "agent"
            # Update path
            m._persist_did(did, DIDType.AGENT, doc, list(m._keys.values())[0])
            session.flush()
        engine.dispose()

    def test_persist_did_exception_swallowed(self):
        m = DIDManager()
        doc = DIDDocument(id="did:atom:a")
        key = DIDKey(id="k", public_key_base58="pk")
        with patch(
            "core.database.get_db_session", side_effect=RuntimeError("db down")
        ):
            m._persist_did("did:atom:a", DIDType.AGENT, doc, key)  # must not raise

    def test_load_dids_from_db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from core.models import Base, FederationDID

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        m = DIDManager()
        row = FederationDID(
            did="did:atom:agent:loaded-1",
            entity_type="agent",
            entity_id="loaded-1",
            document_json={
                "id": "did:atom:agent:loaded-1",
                "authentication": ["did:atom:agent:loaded-1#key-1"],
                "created": "2026-01-01T00:00:00",
                "version_id": "v9",
            },
            public_key_pem="pk",
            is_active=True,
        )
        session.add(row)
        session.commit()

        with patch("core.database.get_db_session", return_value=session):
            loaded = m.load_dids_from_db()
        assert loaded == 1
        assert "did:atom:agent:loaded-1" in m._did_documents
        doc = m._did_documents["did:atom:agent:loaded-1"]
        assert doc.authentication == ["did:atom:agent:loaded-1#key-1"]
        assert doc.version_id == "v9"
        # idempotent — already loaded
        with patch("core.database.get_db_session", return_value=session):
            assert m.load_dids_from_db() == 0
        engine.dispose()

    def test_load_dids_missing_created(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from core.models import Base, FederationDID

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        session.add(
            FederationDID(
                did="did:atom:agent:no-created",
                entity_type="agent",
                entity_id="no-created",
                document_json={"id": "did:atom:agent:no-created", "authentication": []},
                public_key_pem="pk",
                is_active=True,
            )
        )
        session.commit()
        m = DIDManager()
        with patch("core.database.get_db_session", return_value=session):
            assert m.load_dids_from_db() == 1
        engine.dispose()

    def test_load_dids_exception_returns_zero(self):
        m = DIDManager()
        with patch(
            "core.database.get_db_session", side_effect=RuntimeError("db down")
        ):
            assert m.load_dids_from_db() == 0

    def test_get_did_manager_singleton(self):
        with patch("core.identity.did_manager._did_manager_instance", None):
            m1 = get_did_manager()
            m2 = get_did_manager()
            assert m1 is m2
            from core.identity import did_manager as dm

            dm._did_manager_instance = None

    def test_import_fallback_without_cryptography(self):
        """Module must import cleanly with cryptography unavailable and
        set CRYPTO_AVAILABLE=False (fail-closed key generation)."""
        import builtins
        import importlib

        import core.identity.did_manager as dm

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name.startswith("cryptography"):
                raise ImportError("cryptography not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=blocked):
            mod = importlib.reload(dm)
        assert mod.CRYPTO_AVAILABLE is False
        key = mod.DIDManager()._generate_keypair()
        assert len(key.private_key_base58) == 64
        # Restore the real module for any later tests.
        importlib.reload(dm)
