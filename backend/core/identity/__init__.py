"""
Identity Module for Zero-Trust Federation

Provides decentralized identity management for agents and instances using:
- DIDs (Decentralized Identifiers)
- VCs (Verifiable Credentials)
- Zero-trust identity verification

Based on 2025-2026 research:
- OpenID: AI Agent Identity Challenges
- Zero-Trust Identity Framework (arXiv:2505.19301v2)
- Agentic Identity and Access Control (Coalition for Secure AI)
"""

from core.identity.did_manager import (
    DIDManager,
    DIDDocument,
    DIDMethod,
    DIDResolutionResult,
    get_did_manager,
)

from core.identity.verifiable_credentials import (
    VerifiableCredential,
    VCPresentation,
    VCStatus,
    VerifiableCredentialManager,
    get_vc_manager,
)

__all__ = [
    # DID Manager
    "DIDManager",
    "DIDDocument",
    "DIDMethod",
    "DIDResolutionResult",
    "get_did_manager",

    # Verifiable Credentials
    "VerifiableCredential",
    "VCPresentation",
    "VCStatus",
    "VerifiableCredentialManager",
    "get_vc_manager",
]
