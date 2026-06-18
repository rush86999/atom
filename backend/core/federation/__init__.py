"""
Federation Module for Zero-Trust Security

Provides secure federation between Atom instances using:
- Zero-trust identity verification
- Mutual TLS authentication
- Credential rotation
- Anomaly detection

Based on 2025-2026 research:
- Zero-Trust Identity Framework (arXiv:2505.19301v2)
- Agentic Identity and Access Control (Coalition for Secure AI)
- Multi-Tenant AI Systems Guide
"""

from core.federation.zero_trust_security import (
    ZeroTrustSecurityManager,
    FederationRequest,
    SecurityContext,
    SecurityPolicy,
    AccessDecision,
    get_zero_trust_manager,
)

from core.federation.federation_security import (
    FederationSecurityService,
    MutualTLSConfig,
    CredentialRotationManager,
    AnomalyDetector,
    get_federation_security,
)

__all__ = [
    # Zero-Trust Security
    "ZeroTrustSecurityManager",
    "FederationRequest",
    "SecurityContext",
    "SecurityPolicy",
    "AccessDecision",
    "get_zero_trust_manager",

    # Federation Security
    "FederationSecurityService",
    "MutualTLSConfig",
    "CredentialRotationManager",
    "AnomalyDetector",
    "get_federation_security",
]
