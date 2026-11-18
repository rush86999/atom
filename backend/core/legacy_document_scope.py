"""Guarded compatibility proof for pre-scope ("legacy") document uploads.

Before the Personal-workspace resolver was wired into the document routes, an
authenticated account with NULL workspace scope handed ``None`` to
``get_lancedb_handler`` and its upload was written to the legacy *shared*
``default_shared`` store. The SQL mirror was already stamped ``"default"``.
After the scope repair the resolved store is ``"default"``, so those rows must
remain reachable through a narrowly guarded compatibility path shared by every
read surface (direct list/read/export/delete and hybrid ``documents.search``):

  * only the KNOWN legacy namespace is consulted (never an arbitrary store);
  * the caller must be the proven, persisted bootstrap authority;
  * the durable SQL row must prove the resolved workspace + raw tenant and be
    explicitly ``fresh``;
  * the vector row must be stamped to this exact principal and legacy
    namespace, carry the same PG join key and the same source revision.

A digest or id is identity, never permission: a foreign or unprovable row is
left untouched and fails closed. No function here relocates, rewrites or widens
a store.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from core.personal_scope import (
    PERSONAL_WORKSPACE_ID,
    is_bootstrap_identity,
)

#: The one physical namespace pre-scope uploads were written to.
LEGACY_SHARED_WORKSPACE_ID = "default_shared"


def document_row_scope_matches(row, workspace_id: Optional[str],
                               tenant_id: Optional[str]) -> bool:
    """True only when an existing SQL row's authoritative owner is this scope.

    Personal-Edition storage normalizes a missing workspace to ``"default"``;
    tenant is compared raw, so a NULL tenant is not silently treated as the
    literal ``"default"`` tenant. A digest is identity, never permission: a
    mismatched row must never be adopted or overwritten.
    """
    if row is None:
        return False
    row_workspace = str(getattr(row, "workspace_id", "") or "default")
    expected_workspace = str(workspace_id or "default")
    return (row_workspace == expected_workspace
            and getattr(row, "tenant_id", None) == tenant_id)


def legacy_scope_applies(workspace_id: Optional[str]) -> bool:
    """Only the Personal workspace can own pre-repair shared-store uploads."""
    return str(workspace_id or "") == PERSONAL_WORKSPACE_ID


def legacy_shared_store_present() -> bool:
    """Whether the documented legacy namespace physically exists.

    A probe only: callers must never create the shared store merely because a
    Personal-scope read looked for old rows. Remote deployments cannot probe a
    directory, so the handler decides (a missing table is an honest empty
    read). ``legacy_shared_handler`` already returns ``None`` for a scope that
    may not consult the namespace, so this helper is namespace-only.
    """
    base_uri = os.getenv("LANCEDB_URI_BASE", "./data/atom_memory")
    if str(base_uri).startswith(("s3://", "db://", "gs://")):
        return True
    from core.lancedb_handler import _resolve_local_db_path

    legacy_path = _resolve_local_db_path(
        os.path.join(base_uri, LEGACY_SHARED_WORKSPACE_ID))
    return os.path.isdir(legacy_path)


def legacy_shared_handler(workspace_id: Optional[str]):
    """The known legacy shared store, or ``None`` when scope is not Personal.

    The existence check is a probe of the one documented legacy namespace,
    never a directory walk.
    """
    if not legacy_scope_applies(workspace_id):
        return None
    if not legacy_shared_store_present():
        return None
    from core.lancedb_handler import get_lancedb_handler

    return get_lancedb_handler(LEGACY_SHARED_WORKSPACE_ID)


def _principal_id(owner: Any) -> str:
    """The persisted principal id behind either a user object or an id."""
    if owner is None:
        return ""
    if isinstance(owner, str):
        return owner.strip()
    return str(getattr(owner, "id", "") or "").strip()


def legacy_vector_owned(document: dict, owner: Any, row, doc_id: str,
                        workspace_id: Optional[str],
                        tenant_id: Optional[str]) -> bool:
    """True only when a legacy vector row is provably this principal's record.

    Requirements are intentionally redundant: the store namespace, the user
    stamp, the authoritative SQL scope/raw tenant, the PG join key and the
    source revision must all agree. Any missing or contradictory proof —
    including a non-``fresh`` vector row — refuses the read.
    """
    if not isinstance(document, dict) or owner is None or row is None:
        return False
    if not document_row_scope_matches(row, workspace_id, tenant_id):
        return False
    if str(document.get("id") or "") != str(doc_id):
        return False
    if str(document.get("workspace_id") or "") != LEGACY_SHARED_WORKSPACE_ID:
        return False
    owner_id = _principal_id(owner)
    vector_owner = str(document.get("user_id") or "").strip()
    # A non-empty, matching principal is required: two absent ids are not a
    # shared identity, and an unscoped row must never be adopted by default.
    if not owner_id or not vector_owner or vector_owner != owner_id:
        return False
    # Freshness must be explicit on the vector side too. Missing/unknown is
    # not "fresh enough"; only a positive ``fresh`` stamp is served.
    if str(document.get("freshness_status") or "").strip().lower() != "fresh":
        return False

    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        return False
    if str(metadata.get("pg_document_id") or "") != str(doc_id):
        return False
    indexed_version = str(
        metadata.get("source_content_hash") or "").strip()
    row_version = str(
        getattr(row, "source_content_hash", "") or "").strip()
    if not indexed_version or not row_version:
        return False
    if indexed_version != row_version:
        return False
    return True


def legacy_document_authority(user: Any) -> Optional[dict]:
    """The authority a legacy-namespace read needs, or ``None`` when unproven.

    This is the ONLY identity that may reach pre-scope rows: the server-owned
    bootstrap account, persisted with raw NULL tenant/workspace. Every other
    principal — including one merely shaped like it — is refused here, and a
    refusal simply means "no legacy lane", never a fallback to the shared
    store. Total by design: an identity check that cannot be completed is not
    a grant.
    """
    if user is None:
        return None
    try:
        if not is_bootstrap_identity(user):
            return None
    except Exception:  # noqa: BLE001 — unprovable identity is not authority
        return None
    user_id = _principal_id(user)
    if not user_id:
        return None
    return {
        "user_id": user_id,
        "workspace_id": PERSONAL_WORKSPACE_ID,
        "tenant_id": getattr(user, "tenant_id", None),
    }


def verify_legacy_document_authority(db: Any,
                                    authority: Optional[dict]) -> bool:
    """Re-prove the authority against the persisted principal row.

    The action context's user object is trusted at dispatch, but the legacy
    lane spans two stores and must not serve rows on a stale/forged shape.
    Returns ``False`` only when the durable row is absent or provably not the
    bootstrap identity; an unreadable authority store raises so the caller
    records an unavailable read instead of claiming absence.
    """
    if not isinstance(authority, dict):
        return False
    user_id = str(authority.get("user_id") or "").strip()
    if not user_id:
        return False
    from core.models import User

    persisted = (
        db.query(User).filter(User.id == user_id).first()
    )
    if persisted is None:
        return False
    proven = legacy_document_authority(persisted)
    if proven is None:
        return False
    return (
        str(proven.get("user_id") or "") == user_id
        and str(proven.get("workspace_id") or "")
        == str(authority.get("workspace_id") or "")
        and proven.get("tenant_id") == authority.get("tenant_id")
    )
