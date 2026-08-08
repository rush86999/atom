"""
TDD bug hunt — federation zero-trust identity stack.

Bugs under test:
A. ZeroTrustSecurityManager._validate_credentials never binds a presented
   credential's subject to the request's source DID (X-Source-DID) — an
   attacker who knows a valid credential ID can present another entity's
   credential under their own identity (borrowed-credential impersonation).
B. ZeroTrustSecurityManager._authenticate accepts DIDs whose documents are
   deactivated — a revoked identity keeps authenticating.
C. VerifiableCredentialManager.create_credential lets caller claims override
   the fixed "id"/"type" fields of credential_subject — subject spoofing at
   issuance.
D. SecurityPolicy.required_credentials is declared but never enforced by
   SecurityPolicy.matches — a policy that requires a federation membership
   credential allows requests that present no credentials at all.
"""

import pytest

from core.identity.did_manager import DIDManager, DIDType
from core.identity.verifiable_credentials import (
    VCConfig,
    VCType,
    VerifiableCredentialManager,
)
from core.federation.zero_trust_security import (
    AccessAction,
    AccessDecision,
    DecisionReason,
    FederationRequest,
    SecurityConfig,
    SecurityLevel,
    SecurityPolicy,
    ZeroTrustSecurityManager,
)


@pytest.fixture
def dids():
    mgr = DIDManager()
    issuer = mgr.generate_did(DIDType.INSTANCE, "issuer")
    alice = mgr.generate_did(DIDType.AGENT, "alice")
    mallory = mgr.generate_did(DIDType.AGENT, "mallory")
    for d, t in ((issuer, DIDType.INSTANCE), (alice, DIDType.AGENT), (mallory, DIDType.AGENT)):
        mgr.create_did_document(d, t)
    return mgr, issuer, alice, mallory


def make_vc_manager(did_manager: DIDManager) -> VerifiableCredentialManager:
    manager = VerifiableCredentialManager(VCConfig())
    manager.did_manager = did_manager
    return manager


def make_zt_manager(config: SecurityConfig, did_manager, vc_manager) -> ZeroTrustSecurityManager:
    manager = ZeroTrustSecurityManager(config)
    manager.did_manager = did_manager
    manager.vc_manager = vc_manager
    manager.add_policy(
        SecurityPolicy(
            id="allow-read",
            name="Allow read",
            required_security_level=SecurityLevel.NONE,
            allowed_actions=[AccessAction.READ],
            default_decision=True,
        )
    )
    return manager


def read_request(zt: ZeroTrustSecurityManager, source_did: str, credential_ids=()) -> AccessDecision:
    headers = {"X-Source-DID": source_did}
    if credential_ids:
        headers["X-Verifiable-Credentials"] = ",".join(credential_ids)
    return zt.verify_request(
        FederationRequest(
            method="GET",
            path="/api/v1/data",
            headers=headers,
            action=AccessAction.READ,
            resource_type="generic",
        )
    )


class TestCredentialSubjectBinding:
    """BUG A — presented credentials must belong to the source DID."""

    def test_presenting_another_subjects_credential_is_denied(self, dids):
        mgr, issuer, alice, mallory = dids
        vcman = make_vc_manager(mgr)
        vc = vcman.create_credential(
            issuer_did=issuer,
            credential_type=VCType.AGENT_IDENTITY,
            subject_did=alice,
            claims={"name": "alice"},
        )
        zt = make_zt_manager(
            SecurityConfig(require_credential=True, enable_rate_limiting=False), mgr, vcman
        )

        decision = read_request(zt, mallory, [vc.id])

        assert decision.allowed is False, (
            "mallory authenticated as herself while presenting alice's credential — "
            "credentials are not bound to the presenting identity"
        )

    def test_own_credential_is_accepted(self, dids):
        mgr, issuer, alice, mallory = dids
        vcman = make_vc_manager(mgr)
        vc = vcman.create_credential(
            issuer_did=issuer,
            credential_type=VCType.AGENT_IDENTITY,
            subject_did=alice,
            claims={"name": "alice"},
        )
        zt = make_zt_manager(
            SecurityConfig(require_credential=True, enable_rate_limiting=False), mgr, vcman
        )

        decision = read_request(zt, alice, [vc.id])

        assert decision.allowed is True, "legitimate holder of a valid credential was denied"


class TestDeactivatedDIDRejected:
    """BUG B — deactivated DIDs must not authenticate."""

    def test_authenticate_rejects_deactivated_did(self, dids):
        mgr, issuer, alice, mallory = dids
        vcman = make_vc_manager(mgr)
        zt = make_zt_manager(
            SecurityConfig(require_credential=False, enable_rate_limiting=False), mgr, vcman
        )
        mgr.deactivate_did(mallory)

        decision = read_request(zt, mallory)

        assert decision.allowed is False, (
            "a deactivated DID still authenticated — revoked identities must be rejected"
        )
        assert decision.reason == DecisionReason.UNKNOWN_IDENTITY

    def test_active_did_still_authenticates(self, dids):
        mgr, issuer, alice, mallory = dids
        vcman = make_vc_manager(mgr)
        zt = make_zt_manager(
            SecurityConfig(require_credential=False, enable_rate_limiting=False), mgr, vcman
        )

        decision = read_request(zt, alice)

        assert decision.allowed is True


class TestClaimsCannotSpoofSubject:
    """BUG C — caller claims must not override the credential subject."""

    def test_claims_id_cannot_override_subject_did(self, dids):
        mgr, issuer, alice, mallory = dids
        vcman = make_vc_manager(mgr)

        vc = vcman.create_credential(
            issuer_did=issuer,
            credential_type=VCType.AGENT_IDENTITY,
            subject_did=alice,
            claims={"id": "did:evil:spoof", "name": "alice"},
        )

        assert vc.credential_subject["id"] == alice, (
            "claims['id'] overwrote the subject DID — the credential claims a "
            "different subject than the one it was issued to"
        )

    def test_claims_type_cannot_override_credential_type(self, dids):
        mgr, issuer, alice, mallory = dids
        vcman = make_vc_manager(mgr)

        vc = vcman.create_credential(
            issuer_did=issuer,
            credential_type=VCType.AGENT_IDENTITY,
            subject_did=alice,
            claims={"type": "AgentCapabilityCredential"},
        )

        assert vc.credential_subject["type"] == VCType.AGENT_IDENTITY.value, (
            "claims['type'] overwrote the credential type in credential_subject"
        )


class TestPolicyRequiredCredentialsEnforced:
    """BUG D — SecurityPolicy.required_credentials must be enforced."""

    def test_policy_denies_request_without_required_credential(self, dids):
        mgr, issuer, alice, mallory = dids
        vcman = make_vc_manager(mgr)
        zt = ZeroTrustSecurityManager(
            SecurityConfig(require_credential=False, enable_rate_limiting=False)
        )
        zt.did_manager = mgr
        zt.vc_manager = vcman
        zt.add_policy(
            SecurityPolicy(
                id="members-only",
                name="Members only",
                required_security_level=SecurityLevel.NONE,
                required_credentials=[VCType.FEDERATION_MEMBERSHIP],
                allowed_actions=[AccessAction.READ],
                default_decision=True,
            )
        )

        decision = read_request(zt, alice)

        assert decision.allowed is False, (
            "a policy requiring a FederationMembershipCredential allowed a request "
            "that presented no credentials at all"
        )

    def test_policy_allows_request_with_required_credential(self, dids):
        mgr, issuer, alice, mallory = dids
        vcman = make_vc_manager(mgr)
        vc = vcman.create_federation_membership_credential(
            issuer_did=issuer,
            instance_did=alice,
            instance_id="alice-instance",
            instance_name="Alice",
        )
        zt = ZeroTrustSecurityManager(
            SecurityConfig(require_credential=False, enable_rate_limiting=False)
        )
        zt.did_manager = mgr
        zt.vc_manager = vcman
        zt.add_policy(
            SecurityPolicy(
                id="members-only",
                name="Members only",
                required_security_level=SecurityLevel.NONE,
                required_credentials=[VCType.FEDERATION_MEMBERSHIP],
                allowed_actions=[AccessAction.READ],
                default_decision=True,
            )
        )

        decision = read_request(zt, alice, [vc.id])

        assert decision.allowed is True, (
            "a request presenting the required membership credential was denied"
        )
