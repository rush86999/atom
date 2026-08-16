"""Org Sharing Crypto — Ed25519 signing/verification for org bundles.

Org Ingestion Sharing (docs/architecture/ORG_INGESTION_SHARING_PLAN.md):
ingestion profiles and org data bundles are Ed25519-signed by the exporting
instance and verified by the importer **before** any payload is parsed.

Key model:
- The instance's own keypair is generated once; the private key lives in
  ``./data/org_sharing_key`` (0600) — the same on-disk pattern as the BYOK
  encryption key (``core/privsec/token_encryption.py``). The private key is
  never stored in the DB.
- Public keys (own + peers) are registered in the ``org_public_keys`` table.
  Peer public keys are distributed out-of-band by the org admin; verification
  succeeds against the own key or any registered peer key for the workspace.

All entry points are fail-closed: a missing key file, bad base64, or absent
table degrades to ``verify`` returning False, never to an unverified accept.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

logger = logging.getLogger(__name__)

DEFAULT_KEY_FILE = os.path.join("data", "org_sharing_key")


def _key_file_path() -> Path:
    return Path(os.getenv("ATOM_ORG_SHARING_KEY_FILE", DEFAULT_KEY_FILE))


def _write_private_key(private_key: Ed25519PrivateKey, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem)
    os.chmod(path, 0o600)


def get_or_create_private_key() -> Ed25519PrivateKey:
    """Load the instance keypair, generating + persisting it on first use."""
    path = _key_file_path()
    if path.exists():
        try:
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
            if isinstance(key, Ed25519PrivateKey):
                return key
            logger.warning("org sharing key file holds a non-Ed25519 key — regenerating")
        except Exception as e:
            logger.warning(f"Could not load org sharing key ({e}) — regenerating")
    key = Ed25519PrivateKey.generate()
    _write_private_key(key, path)
    return key


def public_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def public_key_b64(private_key: Ed25519PrivateKey) -> str:
    return base64.b64encode(public_key_bytes(private_key)).decode("ascii")


def fingerprint(raw_public: bytes) -> str:
    """SHA-256 fingerprint of the raw public key (hex)."""
    return hashlib.sha256(raw_public).hexdigest()


def sign_payload(payload: bytes) -> Tuple[str, str]:
    """Sign ``payload`` with the instance key. Returns (signature_b64, public_key_b64)."""
    key = get_or_create_private_key()
    sig = key.sign(payload)
    return base64.b64encode(sig).decode("ascii"), public_key_b64(key)


def register_public_key(
    db,
    public_key_b64_value: str,
    label: str,
    workspace_id: str,
    tenant_id: Optional[str] = None,
    is_own: bool = False,
):
    """Register (or return the existing) OrgPublicKey row for a public key.

    Idempotent on the key value: re-registering the same key updates the
    label rather than duplicating rows.
    """
    from core.models import OrgPublicKey

    raw = base64.b64decode(public_key_b64_value.encode("ascii"), validate=True)
    if len(raw) != 32:
        raise ValueError("Ed25519 public keys must be exactly 32 bytes")

    row = db.query(OrgPublicKey).filter(OrgPublicKey.public_key == public_key_b64_value).first()
    if row is None:
        row = OrgPublicKey(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            label=label,
            public_key=public_key_b64_value,
            fingerprint=fingerprint(raw),
            is_own=is_own,
        )
        db.add(row)
    else:
        row.label = label
        if is_own:
            row.is_own = True
    db.commit()
    db.refresh(row)
    return row


def ensure_own_key_registered(db, workspace_id: str, tenant_id: Optional[str] = None) -> str:
    """Generate/load the instance keypair and register its public key. Returns b64 public key."""
    pub_b64 = public_key_b64(get_or_create_private_key())
    register_public_key(db, pub_b64, label="own-instance", workspace_id=workspace_id,
                        tenant_id=tenant_id, is_own=True)
    return pub_b64


def verify_payload(db, payload: bytes, signature_b64: str, workspace_id: str) -> bool:
    """Verify a signature against the own key and all registered peer keys.

    Fail-closed: any error (bad base64, no keys registered, DB unavailable)
    returns False.
    """
    try:
        sig = base64.b64decode(signature_b64.encode("ascii"), validate=True)
    except Exception:
        return False

    from core.models import OrgPublicKey

    try:
        rows = db.query(OrgPublicKey).filter(
            (OrgPublicKey.workspace_id == workspace_id) | (OrgPublicKey.workspace_id.is_(None))
        ).all()
    except Exception as e:
        logger.warning(f"org key registry unavailable — verification fails closed: {e}")
        return False

    candidates = [row.public_key for row in rows]
    # The own key always verifies, even if the registry table is fresh/empty.
    try:
        candidates.append(public_key_b64(get_or_create_private_key()))
    except Exception:
        pass

    for pub_b64 in candidates:
        try:
            raw = base64.b64decode(pub_b64.encode("ascii"), validate=True)
            Ed25519PublicKey.from_public_bytes(raw).verify(sig, payload)
            return True
        except (InvalidSignature, ValueError, TypeError):
            continue
    return False
