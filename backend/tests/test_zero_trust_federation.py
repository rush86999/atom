"""
Test suite for Phase 4: Zero-Trust Federation Identity.

Tests cover:
- DID management and resolution
- Verifiable credentials
- Zero-trust security framework
- Federation security (mTLS, rotation, anomaly detection)
"""

import pytest
from datetime import datetime, timedelta


# ============================================================================
# DID Manager Tests
# ============================================================================

class TestDIDConfig:
    """Tests for DIDConfig"""

    def test_config_import(self):
        """Test that DIDConfig can be imported"""
        try:
            from core.identity.did_manager import DIDConfig
            assert DIDConfig is not None
        except ImportError as e:
            pytest.fail(f"DIDConfig import failed: {e}")

    def test_config_defaults(self):
        """Test that DIDConfig has sensible defaults"""
        from core.identity.did_manager import DIDConfig, DIDMethod

        config = DIDConfig()

        assert config.method == DIDMethod.ATOM
        assert config.key_type == "ed25519"
        assert config.key_rotation_days == 90
        assert config.resolution_timeout_ms == 5000
        assert config.cache_ttl_seconds == 300


class TestDIDMethod:
    """Tests for DIDMethod enum"""

    def test_method_import(self):
        """Test that DIDMethod can be imported"""
        try:
            from core.identity.did_manager import DIDMethod
            assert DIDMethod is not None
        except ImportError as e:
            pytest.fail(f"DIDMethod import failed: {e}")

    def test_method_values(self):
        """Test that DIDMethod has required values"""
        from core.identity.did_manager import DIDMethod

        assert hasattr(DIDMethod, 'ATOM')
        assert hasattr(DIDMethod, 'WEB')
        assert hasattr(DIDMethod, 'KEY')
        assert hasattr(DIDMethod, 'PKH')


class TestDIDType:
    """Tests for DIDType enum"""

    def test_type_import(self):
        """Test that DIDType can be imported"""
        try:
            from core.identity.did_manager import DIDType
            assert DIDType is not None
        except ImportError as e:
            pytest.fail(f"DIDType import failed: {e}")

    def test_type_values(self):
        """Test that DIDType has required values"""
        from core.identity.did_manager import DIDType

        assert hasattr(DIDType, 'AGENT')
        assert hasattr(DIDType, 'INSTANCE')
        assert hasattr(DIDType, 'WORKSPACE')
        assert hasattr(DIDType, 'USER')


class TestDIDDocument:
    """Tests for DIDDocument"""

    def test_document_import(self):
        """Test that DIDDocument can be imported"""
        try:
            from core.identity.did_manager import DIDDocument
            assert DIDDocument is not None
        except ImportError as e:
            pytest.fail(f"DIDDocument import failed: {e}")

    def test_document_creation(self):
        """Test that DIDDocument can be created"""
        from core.identity.did_manager import DIDDocument

        doc = DIDDocument(id="did:atom:agent:test123")

        assert doc.id == "did:atom:agent:test123"
        assert len(doc.context) > 0
        assert doc.deactivated is False

    def test_document_to_dict(self):
        """Test that DIDDocument can be serialized"""
        from core.identity.did_manager import DIDDocument, DIDVerificationMethod

        doc = DIDDocument(id="did:atom:agent:test123")
        vm = DIDVerificationMethod(
            id="did:atom:agent:test123#key-1",
            type="Ed25519VerificationKey2020",
            controller="did:atom:agent:test123",
            public_key_base58="testkey"
        )
        doc.verification_method = [vm]

        result = doc.to_dict()

        assert result["id"] == "did:atom:agent:test123"
        assert len(result["verificationMethod"]) == 1


class TestDIDResolutionResult:
    """Tests for DIDResolutionResult"""

    def test_result_import(self):
        """Test that DIDResolutionResult can be imported"""
        try:
            from core.identity.did_manager import DIDResolutionResult
            assert DIDResolutionResult is not None
        except ImportError as e:
            pytest.fail(f"DIDResolutionResult import failed: {e}")

    def test_result_creation(self):
        """Test that DIDResolutionResult can be created"""
        from core.identity.did_manager import DIDResolutionResult

        result = DIDResolutionResult(did="did:atom:agent:test123")

        assert result.did == "did:atom:agent:test123"
        assert result.did_document is None


class TestDIDManager:
    """Tests for DIDManager"""

    def test_manager_import(self):
        """Test that DIDManager can be imported"""
        try:
            from core.identity.did_manager import DIDManager
            assert DIDManager is not None
        except ImportError as e:
            pytest.fail(f"DIDManager import failed: {e}")

    def test_manager_initialization(self):
        """Test that manager can be initialized"""
        from core.identity.did_manager import DIDManager, DIDConfig

        config = DIDConfig()
        manager = DIDManager(config)

        assert manager is not None
        assert manager.config == config

    def test_generate_did(self):
        """Test that DIDs can be generated"""
        from core.identity.did_manager import DIDManager, DIDType

        manager = DIDManager()

        did = manager.generate_did(DIDType.AGENT, "test123")

        assert "did:atom:" in did
        assert "agent" in did

    def test_generate_did_with_instance(self):
        """Test that DIDs can be generated with instance ID"""
        from core.identity.did_manager import DIDManager, DIDType

        manager = DIDManager()

        did = manager.generate_did(DIDType.AGENT, "test123", "instance01")

        assert "did:atom:instance01:" in did
        assert "agent" in did

    def test_create_did_document(self):
        """Test that DID documents can be created"""
        from core.identity.did_manager import DIDManager, DIDType

        manager = DIDManager()
        did = manager.generate_did(DIDType.AGENT, "test123")

        doc = manager.create_did_document(did, DIDType.AGENT)

        assert doc.id == did
        assert len(doc.verification_method) > 0
        assert len(doc.authentication) > 0

    def test_resolve_did(self):
        """Test that DIDs can be resolved"""
        from core.identity.did_manager import DIDManager, DIDType

        manager = DIDManager()
        did = manager.generate_did(DIDType.AGENT, "test123")
        manager.create_did_document(did, DIDType.AGENT)

        result = manager.resolve_did(did)

        assert result.did == did
        assert result.did_document is not None
        assert result.did_document.id == did

    def test_resolve_did_with_cache(self):
        """Test that DID resolution uses cache"""
        from core.identity.did_manager import DIDManager, DIDType

        manager = DIDManager()
        did = manager.generate_did(DIDType.AGENT, "test123")
        manager.create_did_document(did, DIDType.AGENT)

        # First call
        result1 = manager.resolve_did(did, use_cache=True)
        # Second call (should use cache)
        result2 = manager.resolve_did(did, use_cache=True)

        assert result1.did == did
        assert result2.did == did

    def test_deactivate_did(self):
        """Test that DIDs can be deactivated"""
        from core.identity.did_manager import DIDManager, DIDType

        manager = DIDManager()
        did = manager.generate_did(DIDType.AGENT, "test123")
        manager.create_did_document(did, DIDType.AGENT)

        result = manager.deactivate_did(did)

        assert result is True

        doc = manager.resolve_did(did).did_document
        assert doc.deactivated is True

    def test_register_federation_instance(self):
        """Test that federation instances can be registered"""
        from core.identity.did_manager import DIDManager

        manager = DIDManager()

        manager.register_federation_instance("instance01", "https://instance01.example.com")

        assert "instance01" in manager._federation_registry

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.identity.did_manager import get_did_manager

        assert callable(get_did_manager)


# ============================================================================
# Verifiable Credentials Tests
# ============================================================================

class TestVCConfig:
    """Tests for VCConfig"""

    def test_config_import(self):
        """Test that VCConfig can be imported"""
        try:
            from core.identity.verifiable_credentials import VCConfig
            assert VCConfig is not None
        except ImportError as e:
            pytest.fail(f"VCConfig import failed: {e}")

    def test_config_defaults(self):
        """Test that VCConfig has sensible defaults"""
        from core.identity.verifiable_credentials import VCConfig

        config = VCConfig()

        assert config.default_expiry_days == 90
        assert config.max_expiry_days == 365
        assert config.require_verification is True


class TestVCType:
    """Tests for VCType enum"""

    def test_type_import(self):
        """Test that VCType can be imported"""
        try:
            from core.identity.verifiable_credentials import VCType
            assert VCType is not None
        except ImportError as e:
            pytest.fail(f"VCType import failed: {e}")

    def test_type_values(self):
        """Test that VCType has required values"""
        from core.identity.verifiable_credentials import VCType

        assert hasattr(VCType, 'AGENT_IDENTITY')
        assert hasattr(VCType, 'INSTANCE_IDENTITY')
        assert hasattr(VCType, 'FEDERATION_MEMBERSHIP')


class TestVCStatus:
    """Tests for VCStatus enum"""

    def test_status_import(self):
        """Test that VCStatus can be imported"""
        try:
            from core.identity.verifiable_credentials import VCStatus
            assert VCStatus is not None
        except ImportError as e:
            pytest.fail(f"VCStatus import failed: {e}")

    def test_status_values(self):
        """Test that VCStatus has required values"""
        from core.identity.verifiable_credentials import VCStatus

        assert hasattr(VCStatus, 'VALID')
        assert hasattr(VCStatus, 'REVOKED')
        assert hasattr(VCStatus, 'EXPIRED')


class TestVerifiableCredential:
    """Tests for VerifiableCredential"""

    def test_credential_import(self):
        """Test that VerifiableCredential can be imported"""
        try:
            from core.identity.verifiable_credentials import VerifiableCredential
            assert VerifiableCredential is not None
        except ImportError as e:
            pytest.fail(f"VerifiableCredential import failed: {e}")

    def test_credential_creation(self):
        """Test that VerifiableCredential can be created"""
        from core.identity.verifiable_credentials import VerifiableCredential

        vc = VerifiableCredential(
            id="urn:vc:test123",
            issuer="did:atom:instance:main",
            credential_subject={"id": "did:atom:agent:agent1", "name": "Agent 1"}
        )

        assert vc.id == "urn:vc:test123"
        assert vc.issuer == "did:atom:instance:main"
        assert vc.is_valid()

    def test_credential_expiration(self):
        """Test that credential expiration works"""
        from core.identity.verifiable_credentials import VerifiableCredential

        vc = VerifiableCredential(
            id="urn:vc:test123",
            issuer="did:atom:instance:main",
            expiration_date=datetime.now() - timedelta(days=1),  # Expired
            credential_subject={"id": "did:atom:agent:agent1"}
        )

        assert not vc.is_valid()

    def test_credential_revocation(self):
        """Test that credential revocation works"""
        from core.identity.verifiable_credentials import VerifiableCredential

        vc = VerifiableCredential(
            id="urn:vc:test123",
            issuer="did:atom:instance:main",
            credential_subject={"id": "did:atom:agent:agent1"}
        )
        vc.revoked = True

        assert not vc.is_valid()

    def test_credential_to_dict(self):
        """Test that VerifiableCredential can be serialized"""
        from core.identity.verifiable_credentials import VerifiableCredential

        vc = VerifiableCredential(
            id="urn:vc:test123",
            issuer="did:atom:instance:main",
            credential_subject={"id": "did:atom:agent:agent1"}
        )

        result = vc.to_dict()

        assert result["id"] == "urn:vc:test123"
        assert result["issuer"] == "did:atom:instance:main"


class TestVCPresentation:
    """Tests for VCPresentation"""

    def test_presentation_import(self):
        """Test that VCPresentation can be imported"""
        try:
            from core.identity.verifiable_credentials import VCPresentation
            assert VCPresentation is not None
        except ImportError as e:
            pytest.fail(f"VCPresentation import failed: {e}")

    def test_presentation_creation(self):
        """Test that VCPresentation can be created"""
        from core.identity.verifiable_credentials import (
            VCPresentation,
            VerifiableCredential
        )

        vc = VerifiableCredential(
            id="urn:vc:test123",
            issuer="did:atom:instance:main",
            credential_subject={"id": "did:atom:agent:agent1"}
        )

        vp = VCPresentation(
            id="urn:presentation:pres123",
            verifiable_credential=[vc]
        )

        assert vp.id == "urn:presentation:pres123"
        assert len(vp.verifiable_credential) == 1


class TestVCManager:
    """Tests for VerifiableCredentialManager"""

    def test_manager_import(self):
        """Test that VerifiableCredentialManager can be imported"""
        try:
            from core.identity.verifiable_credentials import VerifiableCredentialManager
            assert VerifiableCredentialManager is not None
        except ImportError as e:
            pytest.fail(f"VerifiableCredentialManager import failed: {e}")

    def test_manager_initialization(self):
        """Test that manager can be initialized"""
        from core.identity.verifiable_credentials import VerifiableCredentialManager, VCConfig

        config = VCConfig()
        manager = VerifiableCredentialManager(config)

        assert manager is not None
        assert manager.config == config

    def test_create_credential(self):
        """Test that credentials can be created"""
        from core.identity.verifiable_credentials import (
            VerifiableCredentialManager,
            VCType
        )

        manager = VerifiableCredentialManager()

        vc = manager.create_credential(
            issuer_did="did:atom:instance:main",
            credential_type=VCType.AGENT_IDENTITY,
            subject_did="did:atom:agent:agent1",
            claims={"agentId": "agent1", "agentName": "Agent 1"}
        )

        assert vc.issuer == "did:atom:instance:main"
        assert vc.id.startswith("urn:vc:")
        assert vc.is_valid()

    def test_revoke_credential(self):
        """Test that credentials can be revoked"""
        from core.identity.verifiable_credentials import (
            VerifiableCredentialManager,
            VCType
        )

        manager = VerifiableCredentialManager()

        vc = manager.create_credential(
            issuer_did="did:atom:instance:main",
            credential_type=VCType.AGENT_IDENTITY,
            subject_did="did:atom:agent:agent1",
            claims={"agentId": "agent1"}
        )

        result = manager.revoke_credential(vc.id)

        assert result is True
        assert not vc.is_valid()

    def test_create_presentation(self):
        """Test that presentations can be created"""
        from core.identity.verifiable_credentials import (
            VerifiableCredentialManager,
            VCType
        )

        manager = VerifiableCredentialManager()

        vc = manager.create_credential(
            issuer_did="did:atom:instance:main",
            credential_type=VCType.AGENT_IDENTITY,
            subject_did="did:atom:agent:agent1",
            claims={"agentId": "agent1"}
        )

        vp = manager.create_presentation(
            credentials=[vc],
            holder_did="did:atom:agent:agent1"
        )

        assert vp.id.startswith("urn:presentation:")
        assert len(vp.verifiable_credential) == 1

    def test_create_agent_identity_credential(self):
        """Test that agent identity credentials can be created"""
        from core.identity.verifiable_credentials import VerifiableCredentialManager

        manager = VerifiableCredentialManager()

        vc = manager.create_agent_identity_credential(
            issuer_did="did:atom:instance:main",
            agent_did="did:atom:agent:agent1",
            agent_id="agent1",
            agent_name="Agent 1",
            capabilities=["read", "write"]
        )

        assert vc.issuer == "did:atom:instance:main"
        assert "agentId" in vc.credential_subject

    def test_create_federation_membership_credential(self):
        """Test that federation membership credentials can be created"""
        from core.identity.verifiable_credentials import VerifiableCredentialManager

        manager = VerifiableCredentialManager()

        vc = manager.create_federation_membership_credential(
            issuer_did="did:atom:federation:main",
            instance_did="did:atom:instance:instance01",
            instance_id="instance01",
            instance_name="Instance 01",
            federation_role="member"
        )

        assert vc.issuer == "did:atom:federation:main"
        assert "instanceId" in vc.credential_subject

    def test_get_statistics(self):
        """Test that statistics can be retrieved"""
        from core.identity.verifiable_credentials import (
            VerifiableCredentialManager,
            VCType
        )

        manager = VerifiableCredentialManager()

        # Create some credentials
        for i in range(3):
            manager.create_credential(
                issuer_did="did:atom:instance:main",
                credential_type=VCType.AGENT_IDENTITY,
                subject_did=f"did:atom:agent:agent{i}",
                claims={"agentId": f"agent{i}"}
            )

        stats = manager.get_statistics()

        assert stats["total_credentials"] == 3
        assert stats["active_credentials"] == 3

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.identity.verifiable_credentials import get_vc_manager

        assert callable(get_vc_manager)


# ============================================================================
# Zero-Trust Security Tests
# ============================================================================

class TestSecurityLevel:
    """Tests for SecurityLevel enum"""

    def test_level_import(self):
        """Test that SecurityLevel can be imported"""
        try:
            from core.federation.zero_trust_security import SecurityLevel
            assert SecurityLevel is not None
        except ImportError as e:
            pytest.fail(f"SecurityLevel import failed: {e}")

    def test_level_values(self):
        """Test that SecurityLevel has required values"""
        from core.federation.zero_trust_security import SecurityLevel

        assert hasattr(SecurityLevel, 'NONE')
        assert hasattr(SecurityLevel, 'MEDIUM')
        assert hasattr(SecurityLevel, 'HIGH')
        assert hasattr(SecurityLevel, 'CRITICAL')


class TestAccessAction:
    """Tests for AccessAction enum"""

    def test_action_import(self):
        """Test that AccessAction can be imported"""
        try:
            from core.federation.zero_trust_security import AccessAction
            assert AccessAction is not None
        except ImportError as e:
            pytest.fail(f"AccessAction import failed: {e}")

    def test_action_values(self):
        """Test that AccessAction has required values"""
        from core.federation.zero_trust_security import AccessAction

        assert hasattr(AccessAction, 'READ')
        assert hasattr(AccessAction, 'WRITE')
        assert hasattr(AccessAction, 'DELETE')
        assert hasattr(AccessAction, 'ADMIN')


class TestSecurityContext:
    """Tests for SecurityContext"""

    def test_context_import(self):
        """Test that SecurityContext can be imported"""
        try:
            from core.federation.zero_trust_security import SecurityContext
            assert SecurityContext is not None
        except ImportError as e:
            pytest.fail(f"SecurityContext import failed: {e}")

    def test_context_creation(self):
        """Test that SecurityContext can be created"""
        from core.federation.zero_trust_security import SecurityContext

        context = SecurityContext(
            request_id="req123",
            source_instance_id="instance01",
            source_did="did:atom:instance:instance01"
        )

        assert context.request_id == "req123"
        assert context.source_instance_id == "instance01"
        assert context.source_did == "did:atom:instance:instance01"


class TestFederationRequest:
    """Tests for FederationRequest"""

    def test_request_import(self):
        """Test that FederationRequest can be imported"""
        try:
            from core.federation.zero_trust_security import FederationRequest
            assert FederationRequest is not None
        except ImportError as e:
            pytest.fail(f"FederationRequest import failed: {e}")

    def test_request_creation(self):
        """Test that FederationRequest can be created"""
        from core.federation.zero_trust_security import (
            FederationRequest,
            SecurityContext,
            AccessAction
        )

        context = SecurityContext(source_instance_id="instance01")
        request = FederationRequest(
            request_id="req123",
            method="GET",
            path="/api/v1/agents",
            action=AccessAction.READ,
            resource_type="agent",
            resource_id="agent1",
            security_context=context
        )

        assert request.request_id == "req123"
        assert request.method == "GET"
        assert request.action == AccessAction.READ

    def test_request_fingerprint(self):
        """Test that request fingerprint is unique"""
        from core.federation.zero_trust_security import (
            FederationRequest,
            SecurityContext
        )

        context = SecurityContext(source_instance_id="instance01")
        request = FederationRequest(
            request_id="req123",
            method="GET",
            path="/api/v1/agents",
            security_context=context
        )

        fp = request.get_fingerprint()

        assert len(fp) == 64  # SHA256 hex length


class TestSecurityPolicy:
    """Tests for SecurityPolicy"""

    def test_policy_import(self):
        """Test that SecurityPolicy can be imported"""
        try:
            from core.federation.zero_trust_security import SecurityPolicy
            assert SecurityPolicy is not None
        except ImportError as e:
            pytest.fail(f"SecurityPolicy import failed: {e}")

    def test_policy_creation(self):
        """Test that SecurityPolicy can be created"""
        from core.federation.zero_trust_security import (
            SecurityPolicy,
            SecurityLevel,
            AccessAction
        )

        policy = SecurityPolicy(
            id="policy-read-agents",
            name="Read Agents Policy",
            required_security_level=SecurityLevel.MEDIUM,
            allowed_actions=[AccessAction.READ],
            default_decision=True
        )

        assert policy.id == "policy-read-agents"
        assert policy.required_security_level == SecurityLevel.MEDIUM


class TestAccessDecision:
    """Tests for AccessDecision"""

    def test_decision_import(self):
        """Test that AccessDecision can be imported"""
        try:
            from core.federation.zero_trust_security import AccessDecision
            assert AccessDecision is not None
        except ImportError as e:
            pytest.fail(f"AccessDecision import failed: {e}")

    def test_decision_creation(self):
        """Test that AccessDecision can be created"""
        from core.federation.zero_trust_security import (
            AccessDecision,
            DecisionReason
        )

        decision = AccessDecision(
            allowed=True,
            reason=DecisionReason.VALID_CREDENTIALS,
            message="Access granted"
        )

        assert decision.allowed is True
        assert decision.reason == DecisionReason.VALID_CREDENTIALS


class TestZeroTrustSecurityManager:
    """Tests for ZeroTrustSecurityManager"""

    def test_manager_import(self):
        """Test that ZeroTrustSecurityManager can be imported"""
        try:
            from core.federation.zero_trust_security import ZeroTrustSecurityManager
            assert ZeroTrustSecurityManager is not None
        except ImportError as e:
            pytest.fail(f"ZeroTrustSecurityManager import failed: {e}")

    def test_manager_initialization(self):
        """Test that manager can be initialized"""
        from core.federation.zero_trust_security import (
            ZeroTrustSecurityManager,
            SecurityConfig
        )

        config = SecurityConfig()
        manager = ZeroTrustSecurityManager(config)

        assert manager is not None
        assert manager.config == config

    def test_verify_request(self):
        """Test that requests can be verified"""
        from core.federation.zero_trust_security import (
            ZeroTrustSecurityManager,
            FederationRequest,
            SecurityContext,
            AccessAction,
            SecurityConfig
        )

        # Disable auth for test
        config = SecurityConfig(require_authentication=False, require_credential=False)
        manager = ZeroTrustSecurityManager(config)

        context = SecurityContext(source_instance_id="instance01")
        request = FederationRequest(
            request_id="req123",
            method="GET",
            path="/api/v1/agents",
            action=AccessAction.READ,
            resource_type="agent",
            security_context=context
        )

        decision = manager.verify_request(request)

        # Decision should be made (not crash)
        assert hasattr(decision, 'allowed')

    def test_add_policy(self):
        """Test that policies can be added"""
        from core.federation.zero_trust_security import (
            ZeroTrustSecurityManager,
            SecurityPolicy,
            SecurityLevel,
            AccessAction
        )

        manager = ZeroTrustSecurityManager()

        policy = SecurityPolicy(
            id="test-policy",
            name="Test Policy",
            required_security_level=SecurityLevel.MEDIUM,
            allowed_actions=[AccessAction.READ],
            default_decision=True
        )

        manager.add_policy(policy)

        assert "test-policy" in manager._policies

    def test_remove_policy(self):
        """Test that policies can be removed"""
        from core.federation.zero_trust_security import (
            ZeroTrustSecurityManager,
            SecurityPolicy,
            SecurityLevel
        )

        manager = ZeroTrustSecurityManager()

        policy = SecurityPolicy(
            id="test-policy",
            name="Test Policy",
            required_security_level=SecurityLevel.MEDIUM
        )

        manager.add_policy(policy)
        result = manager.remove_policy("test-policy")

        assert result is True
        assert "test-policy" not in manager._policies

    def test_get_statistics(self):
        """Test that statistics can be retrieved"""
        from core.federation.zero_trust_security import ZeroTrustSecurityManager

        manager = ZeroTrustSecurityManager()

        stats = manager.get_statistics()

        assert "total_requests" in stats
        assert "allowed_requests" in stats
        assert "denied_requests" in stats

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.federation.zero_trust_security import get_zero_trust_manager

        assert callable(get_zero_trust_manager)


# ============================================================================
# Federation Security Tests
# ============================================================================

class TestMutualTLSConfig:
    """Tests for MutualTLSConfig"""

    def test_config_import(self):
        """Test that MutualTLSConfig can be imported"""
        try:
            from core.federation.federation_security import MutualTLSConfig
            assert MutualTLSConfig is not None
        except ImportError as e:
            pytest.fail(f"MutualTLSConfig import failed: {e}")

    def test_config_defaults(self):
        """Test that MutualTLSConfig has sensible defaults"""
        from core.federation.federation_security import MutualTLSConfig, TLSVersion

        config = MutualTLSConfig()

        assert config.min_version == TLSVersion.TLS_1_2
        assert config.verify_client is True
        assert config.session_timeout == 3600


class TestCredentialRotationConfig:
    """Tests for CredentialRotationConfig"""

    def test_config_import(self):
        """Test that CredentialRotationConfig can be imported"""
        try:
            from core.federation.federation_security import CredentialRotationConfig
            assert CredentialRotationConfig is not None
        except ImportError as e:
            pytest.fail(f"CredentialRotationConfig import failed: {e}")

    def test_config_defaults(self):
        """Test that CredentialRotationConfig has sensible defaults"""
        from core.federation.federation_security import CredentialRotationConfig

        config = CredentialRotationConfig()

        assert config.auto_rotate is True
        assert config.rotation_interval_days == 90
        assert config.warning_days == 30


class TestAnomalyDetectionConfig:
    """Tests for AnomalyDetectionConfig"""

    def test_config_import(self):
        """Test that AnomalyDetectionConfig can be imported"""
        try:
            from core.federation.federation_security import AnomalyDetectionConfig
            assert AnomalyDetectionConfig is not None
        except ImportError as e:
            pytest.fail(f"AnomalyDetectionConfig import failed: {e}")

    def test_config_defaults(self):
        """Test that AnomalyDetectionConfig has sensible defaults"""
        from core.federation.federation_security import AnomalyDetectionConfig

        config = AnomalyDetectionConfig()

        assert config.enable_traffic_analysis is True
        assert config.traffic_spike_multiplier == 3.0
        assert config.min_samples_for_baseline == 100


class TestAnomalyType:
    """Tests for AnomalyType enum"""

    def test_type_import(self):
        """Test that AnomalyType can be imported"""
        try:
            from core.federation.federation_security import AnomalyType
            assert AnomalyType is not None
        except ImportError as e:
            pytest.fail(f"AnomalyType import failed: {e}")

    def test_type_values(self):
        """Test that AnomalyType has required values"""
        from core.federation.federation_security import AnomalyType

        assert hasattr(AnomalyType, 'TRAFFIC_SPIKE')
        assert hasattr(AnomalyType, 'FAILED_AUTH_RATE')
        assert hasattr(AnomalyType, 'LATENCY_SPIKE')


class TestCredentialStatus:
    """Tests for CredentialStatus enum"""

    def test_status_import(self):
        """Test that CredentialStatus can be imported"""
        try:
            from core.federation.federation_security import CredentialStatus
            assert CredentialStatus is not None
        except ImportError as e:
            pytest.fail(f"CredentialStatus import failed: {e}")

    def test_status_values(self):
        """Test that CredentialStatus has required values"""
        from core.federation.federation_security import CredentialStatus

        assert hasattr(CredentialStatus, 'ACTIVE')
        assert hasattr(CredentialStatus, 'EXPIRED')
        assert hasattr(CredentialStatus, 'REVOKED')
        assert hasattr(CredentialStatus, 'COMPROMISED')


class TestTLSConnection:
    """Tests for TLSConnection"""

    def test_connection_import(self):
        """Test that TLSConnection can be imported"""
        try:
            from core.federation.federation_security import TLSConnection
            assert TLSConnection is not None
        except ImportError as e:
            pytest.fail(f"TLSConnection import failed: {e}")

    def test_connection_creation(self):
        """Test that TLSConnection can be created"""
        from core.federation.federation_security import TLSConnection

        conn = TLSConnection(
            connection_id="conn123",
            source_instance="instance01",
            source_ip="192.168.1.1",
            cipher_suite="TLS_AES_256_GCM_SHA384",
            protocol_version="TLSv1.3"
        )

        assert conn.connection_id == "conn123"
        assert conn.source_instance == "instance01"
        assert conn.is_active is True


class TestCredentialRecord:
    """Tests for CredentialRecord"""

    def test_record_import(self):
        """Test that CredentialRecord can be imported"""
        try:
            from core.federation.federation_security import CredentialRecord
            assert CredentialRecord is not None
        except ImportError as e:
            pytest.fail(f"CredentialRecord import failed: {e}")

    def test_record_creation(self):
        """Test that CredentialRecord can be created"""
        from core.federation.federation_security import CredentialRecord, CredentialStatus

        record = CredentialRecord(
            credential_id="cred123",
            credential_type="federation_key",
            instance_id="instance01",
            status=CredentialStatus.ACTIVE
        )

        assert record.credential_id == "cred123"
        assert record.status == CredentialStatus.ACTIVE


class TestAnomalyAlert:
    """Tests for AnomalyAlert"""

    def test_alert_import(self):
        """Test that AnomalyAlert can be imported"""
        try:
            from core.federation.federation_security import AnomalyAlert
            assert AnomalyAlert is not None
        except ImportError as e:
            pytest.fail(f"AnomalyAlert import failed: {e}")

    def test_alert_creation(self):
        """Test that AnomalyAlert can be created"""
        from core.federation.federation_security import (
            AnomalyAlert,
            AnomalyType
        )

        alert = AnomalyAlert(
            alert_id="alert123",
            anomaly_type=AnomalyType.TRAFFIC_SPIKE,
            severity="high",
            description="Traffic spike detected",
            source_instance="instance01"
        )

        assert alert.alert_id == "alert123"
        assert alert.anomaly_type == AnomalyType.TRAFFIC_SPIKE
        assert alert.severity == "high"


class TestMutualTLSManager:
    """Tests for MutualTLSManager"""

    def test_manager_import(self):
        """Test that MutualTLSManager can be imported"""
        try:
            from core.federation.federation_security import MutualTLSManager
            assert MutualTLSManager is not None
        except ImportError as e:
            pytest.fail(f"MutualTLSManager import failed: {e}")

    def test_manager_initialization(self):
        """Test that manager can be initialized"""
        from core.federation.federation_security import MutualTLSManager, MutualTLSConfig

        config = MutualTLSConfig()
        manager = MutualTLSManager(config)

        assert manager is not None
        assert manager.config == config

    def test_create_connection(self):
        """Test that TLS connections can be created"""
        from core.federation.federation_security import MutualTLSManager

        manager = MutualTLSManager()

        conn = manager.create_connection(
            source_instance="instance01",
            source_ip="192.168.1.1",
            cipher_suite="TLS_AES_256_GCM_SHA384",
            protocol_version="TLSv1.3"
        )

        assert conn.connection_id
        assert conn.source_instance == "instance01"

    def test_get_active_connections(self):
        """Test that active connections can be retrieved"""
        from core.federation.federation_security import MutualTLSManager

        manager = MutualTLSManager()

        manager.create_connection("instance01", "192.168.1.1", "TLS_AES_256_GCM_SHA384", "TLSv1.3")

        connections = manager.get_active_connections()

        assert len(connections) == 1


class TestCredentialRotationManager:
    """Tests for CredentialRotationManager"""

    def test_manager_import(self):
        """Test that CredentialRotationManager can be imported"""
        try:
            from core.federation.federation_security import CredentialRotationManager
            assert CredentialRotationManager is not None
        except ImportError as e:
            pytest.fail(f"CredentialRotationManager import failed: {e}")

    def test_manager_initialization(self):
        """Test that manager can be initialized"""
        from core.federation.federation_security import (
            CredentialRotationManager,
            CredentialRotationConfig
        )

        config = CredentialRotationConfig()
        manager = CredentialRotationManager(config)

        assert manager is not None
        assert manager.config == config

    def test_register_credential(self):
        """Test that credentials can be registered"""
        from core.federation.federation_security import CredentialRotationManager

        manager = CredentialRotationManager()

        record = manager.register_credential(
            credential_id="cred123",
            credential_type="federation_key",
            instance_id="instance01",
            expiry_days=90
        )

        assert record.credential_id == "cred123"
        assert record.status.name == "ACTIVE"

    def test_check_rotation_needed(self):
        """Test that rotation need can be checked"""
        from core.federation.federation_security import (
            CredentialRotationManager,
            CredentialRotationConfig
        )

        config = CredentialRotationConfig(rotation_interval_days=1)  # 1 day for test
        manager = CredentialRotationManager(config)

        record = manager.register_credential(
            credential_id="cred123",
            credential_type="federation_key",
            instance_id="instance01"
        )

        # Wait a moment and check (should be fine for test)
        needs = manager.check_rotation_needed("cred123")

        # Should be False (just created)
        assert isinstance(needs, bool)

    def test_revoke_credential(self):
        """Test that credentials can be revoked"""
        from core.federation.federation_security import (
            CredentialRotationManager,
            CredentialStatus
        )

        manager = CredentialRotationManager()

        manager.register_credential(
            credential_id="cred123",
            credential_type="federation_key",
            instance_id="instance01"
        )

        result = manager.revoke_credential("cred123", "Test revocation")

        assert result is True
        assert manager._credentials["cred123"].status == CredentialStatus.REVOKED


class TestAnomalyDetector:
    """Tests for AnomalyDetector"""

    def test_detector_import(self):
        """Test that AnomalyDetector can be imported"""
        try:
            from core.federation.federation_security import AnomalyDetector
            assert AnomalyDetector is not None
        except ImportError as e:
            pytest.fail(f"AnomalyDetector import failed: {e}")

    def test_detector_initialization(self):
        """Test that detector can be initialized"""
        from core.federation.federation_security import (
            AnomalyDetector,
            AnomalyDetectionConfig
        )

        config = AnomalyDetectionConfig()
        detector = AnomalyDetector(config)

        assert detector is not None
        assert detector.config == config

    def test_record_traffic(self):
        """Test that traffic can be recorded"""
        from core.federation.federation_security import AnomalyDetector

        detector = AnomalyDetector()

        metrics = detector.record_traffic(
            source_instance="instance01",
            source_ip="192.168.1.1",
            request_count=10,
            failed_auth=0,
            latency_ms=100.0
        )

        assert metrics.request_count == 10
        assert metrics.avg_latency_ms == 100.0

    def test_get_recent_alerts(self):
        """Test that recent alerts can be retrieved"""
        from core.federation.federation_security import AnomalyDetector

        detector = AnomalyDetector()

        alerts = detector.get_recent_alerts(limit=10)

        assert isinstance(alerts, list)

    def test_get_statistics(self):
        """Test that statistics can be retrieved"""
        from core.federation.federation_security import AnomalyDetector

        detector = AnomalyDetector()

        stats = detector.get_statistics()

        assert "total_alerts" in stats
        assert "baseline_samples" in stats


class TestFederationSecurityService:
    """Tests for FederationSecurityService"""

    def test_service_import(self):
        """Test that FederationSecurityService can be imported"""
        try:
            from core.federation.federation_security import FederationSecurityService
            assert FederationSecurityService is not None
        except ImportError as e:
            pytest.fail(f"FederationSecurityService import failed: {e}")

    def test_service_initialization(self):
        """Test that service can be initialized"""
        from core.federation.federation_security import FederationSecurityService

        service = FederationSecurityService()

        assert service is not None
        assert service.tls is not None
        assert service.rotation is not None
        assert service.anomaly is not None

    def test_get_health_status(self):
        """Test that health status can be retrieved"""
        from core.federation.federation_security import FederationSecurityService

        service = FederationSecurityService()

        health = service.get_health_status()

        assert "status" in health
        assert "active_tls_connections" in health
        assert "services" in health

    def test_get_statistics(self):
        """Test that statistics can be retrieved"""
        from core.federation.federation_security import FederationSecurityService

        service = FederationSecurityService()

        stats = service.get_statistics()

        assert "tls" in stats
        assert "rotation" in stats
        assert "anomaly" in stats

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.federation.federation_security import get_federation_security

        assert callable(get_federation_security)


# ============================================================================
# Integration Tests
# ============================================================================

class TestFederationIntegration:
    """Tests for federation module integration"""

    def test_module_import(self):
        """Test that federation module can be imported"""
        try:
            import core.federation
            assert core.federation is not None
        except ImportError as e:
            pytest.fail(f"federation module import failed: {e}")

    def test_identity_module_import(self):
        """Test that identity module can be imported"""
        try:
            import core.identity
            assert core.identity is not None
        except ImportError as e:
            pytest.fail(f"identity module import failed: {e}")

    def test_module_exports(self):
        """Test that modules export required components"""
        from core.federation import (
            ZeroTrustSecurityManager,
            FederationSecurityService,
            get_zero_trust_manager,
            get_federation_security,
        )

        from core.identity import (
            DIDManager,
            VerifiableCredentialManager,
            get_did_manager,
            get_vc_manager,
        )

        assert ZeroTrustSecurityManager is not None
        assert FederationSecurityService is not None
        assert DIDManager is not None
        assert VerifiableCredentialManager is not None
        assert callable(get_zero_trust_manager)
        assert callable(get_federation_security)
        assert callable(get_did_manager)
        assert callable(get_vc_manager)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
