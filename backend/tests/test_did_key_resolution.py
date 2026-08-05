"""
Tests for did:key resolution validation (core/identity/did_manager.py).

did:key is self-describing, but the resolver previously accepted ANY string
of the form did:key:z<anything> — no validation that the suffix is a real
multibase/base58-encoded key. An attacker could craft did:key:zGARBAGE and
the resolver synthesized a valid DIDDocument, which the zero-trust
_authenticate then treated as an authenticated identity.
"""

import pytest

from core.identity.did_manager import DIDManager


@pytest.fixture
def mgr():
    return DIDManager()


class TestDidKeyResolution:
    def test_rejects_invalid_multibase_suffix(self, mgr):
        """A did:key with a suffix that is NOT valid base58 must NOT resolve."""
        result = mgr._resolve_key_did("did:key:z!!!invalid!!!")
        assert result.did_document is None, (
            "did:key:z!!!invalid!!! resolved to a document — the suffix must "
            "be valid base58 multibase, not just any string starting with 'z'."
        )

    def test_rejects_obvious_garbage_suffix(self, mgr):
        """A clearly malformed suffix (with spaces, special chars) is rejected."""
        result = mgr._resolve_key_did("did:key:z not a key $$$$")
        assert result.did_document is None

    def test_accepts_valid_base58_suffix(self, mgr):
        """Sanity: a valid-looking base58 suffix (alphanumeric, no 0/O/I/l)
        still resolves."""
        # A realistic did:key suffix is base58 (no 0, O, I, l).
        result = mgr._resolve_key_did("did:key:z6MkhaXgBZDvotDkL5257faiztiGi5a2i")
        assert result.did_document is not None
