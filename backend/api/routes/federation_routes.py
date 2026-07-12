"""
Federation & Zero-Trust Identity API Routes.

Exposes the Phase 4 identity/federation modules (DID management, verifiable
credentials, zero-trust verification, federation security) over HTTP. These
modules were previously committed but had no API surface — the imports in
main_api_app.py referenced this file which didn't exist, failing silently.

Routes mount at /api/federation/... (the main_api_app includes this router
with prefix="/api").

NOTE: The underlying modules use in-memory storage. State resets on process
restart — documented as a known limitation; DB persistence is a follow-up.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/federation", tags=["Federation & Zero-Trust"])


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class CreateDIDRequest(BaseModel):
    entity_type: str = Field("agent", description="agent | instance | workspace | user")
    entity_id: str = Field(..., description="The entity's unique id")
    services: Optional[Dict[str, Any]] = Field(None, description="Optional service endpoints")


class CreateCredentialRequest(BaseModel):
    issuer_did: str = Field(..., description="DID of the credential issuer")
    credential_type: str = Field("AgentIdentityCredential", description="VC type")
    subject_did: str = Field(..., description="DID of the credential subject")
    claims: Dict[str, Any] = Field(default_factory=dict, description="Credential claims")
    expiry_days: Optional[int] = Field(None, description="Days until expiry (default 90)")


class RevokeCredentialRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Revocation reason")


class VerifyRequest(BaseModel):
    """A federation verification request."""
    method: str = Field("GET", description="HTTP method")
    path: str = Field("/", description="Request path")
    headers: Dict[str, str] = Field(default_factory=dict, description="Request headers (X-Instance-ID, X-Source-DID, X-Verifiable-Credentials)")
    source_did: Optional[str] = Field(None, description="The source DID (convenience: also set as X-Source-DID header)")
    instance_id: Optional[str] = Field(None, description="The instance ID (convenience: also set as X-Instance-ID header)")
    action: str = Field("read", description="read | write | execute | admin")
    resource_type: str = Field("generic", description="Resource type being accessed")


# ---------------------------------------------------------------------------
# DID management
# ---------------------------------------------------------------------------

@router.post("/dids")
async def create_did(request: CreateDIDRequest) -> Dict[str, Any]:
    """Generate a DID and create its DID document."""
    from core.identity.did_manager import get_did_manager, DIDType
    try:
        did_type = DIDType(request.entity_type)
    except ValueError:
        return {"error": f"Invalid entity_type '{request.entity_type}'. Must be one of: {[e.value for e in DIDType]}"}
    manager = get_did_manager()
    did = manager.generate_did(entity_type=did_type, entity_id=request.entity_id)
    document = manager.create_did_document(did, entity_type=did_type, services=request.services)
    return {
        "did": did,
        "document": document.to_dict() if hasattr(document, "to_dict") else str(document),
    }


@router.get("/dids/{did}")
async def resolve_did(did: str) -> Dict[str, Any]:
    """Resolve a DID to its document."""
    from core.identity.did_manager import get_did_manager
    manager = get_did_manager()
    try:
        result = manager.resolve_did(did)
        return {
            "did": did,
            "resolved": True,
            "document": result.to_dict() if hasattr(result, "to_dict") else str(result),
        }
    except Exception as e:
        return {"did": did, "resolved": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Verifiable credentials
# ---------------------------------------------------------------------------

@router.post("/credentials")
async def create_credential(request: CreateCredentialRequest) -> Dict[str, Any]:
    """Issue a verifiable credential."""
    from core.identity.verifiable_credentials import get_vc_manager, VCType
    try:
        vc_type = VCType(request.credential_type)
    except ValueError:
        return {"error": f"Invalid credential_type. Must be one of: {[e.value for e in VCType]}"}
    manager = get_vc_manager()
    vc = manager.create_credential(
        issuer_did=request.issuer_did,
        credential_type=vc_type,
        subject_did=request.subject_did,
        claims=request.claims,
        expiry_days=request.expiry_days,
    )
    return {
        "credential_id": vc.id if hasattr(vc, "id") else str(vc),
        "issued": True,
    }


@router.post("/credentials/{credential_id}/revoke")
async def revoke_credential(credential_id: str, request: RevokeCredentialRequest) -> Dict[str, Any]:
    """Revoke a verifiable credential."""
    from core.identity.verifiable_credentials import get_vc_manager
    manager = get_vc_manager()
    success = manager.revoke_credential(credential_id, reason=request.reason)
    return {"credential_id": credential_id, "revoked": success}


# ---------------------------------------------------------------------------
# Zero-trust verification
# ---------------------------------------------------------------------------

@router.post("/verify")
async def verify_federation_request(request: VerifyRequest) -> Dict[str, Any]:
    """Verify a federation request against zero-trust policies.

    Runs the 4-stage pipeline: authenticate (resolve source DID) → validate
    VCs (verify signatures + revocation + expiry) → evaluate security policies
    → rate-limit. Returns an AccessDecision.
    """
    from core.federation.zero_trust_security import (
        get_zero_trust_manager, FederationRequest, SecurityContext, AccessAction,
    )
    manager = get_zero_trust_manager()

    # Build headers, adding convenience fields if provided.
    headers = dict(request.headers)
    if request.source_did:
        headers.setdefault("X-Source-DID", request.source_did)
    if request.instance_id:
        headers.setdefault("X-Instance-ID", request.instance_id)

    try:
        action = AccessAction(request.action)
    except ValueError:
        action = AccessAction.READ

    fed_request = FederationRequest(
        method=request.method,
        path=request.path,
        headers=headers,
        action=action,
        resource_type=request.resource_type,
    )
    decision = manager.verify_request(fed_request)
    return {
        "allowed": decision.allowed if hasattr(decision, "allowed") else False,
        "reason": decision.reason.value if hasattr(decision, "reason") and hasattr(decision.reason, "value") else str(getattr(decision, "reason", "unknown")),
        "security_level": str(getattr(decision, "security_level", "unknown")),
    }


# ---------------------------------------------------------------------------
# Federation security health & stats
# ---------------------------------------------------------------------------

@router.get("/security/health")
async def security_health() -> Dict[str, Any]:
    """Get federation security health status."""
    from core.federation.federation_security import get_federation_security
    try:
        return get_federation_security().get_health_status()
    except Exception as e:
        return {"healthy": False, "error": str(e)}


@router.get("/security/stats")
async def security_stats() -> Dict[str, Any]:
    """Get zero-trust security statistics."""
    from core.federation.zero_trust_security import get_zero_trust_manager
    try:
        return get_zero_trust_manager().get_statistics()
    except Exception as e:
        return {"error": str(e)}
