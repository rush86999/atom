"""
Verifiable Credentials (VC) Management

Based on 2025-2026 research:
- W3C Verifiable Credentials Data Model
- Zero-Trust Identity Framework (arXiv:2505.19301v2)
- OpenID AI Agent Identity Challenges

Implements:
- VC creation and signing
- VC verification and validation
- VC presentation and exchange
- Credential status tracking
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logging.warning("Cryptography library not available - VCs will be insecure")

logger = logging.getLogger(__name__)


# Import DID manager
try:
    from core.identity.did_manager import DIDManager, get_did_manager
    DID_AVAILABLE = True
except ImportError:
    DID_AVAILABLE = False
    logger.warning("DID manager not available")


# ============================================================================
# Enums and Configuration
# ============================================================================

class VCType(Enum):
    """Types of verifiable credentials"""
    AGENT_IDENTITY = "AgentIdentityCredential"
    INSTANCE_IDENTITY = "InstanceIdentityCredential"
    AGENT_CAPABILITY = "AgentCapabilityCredential"
    FEDERATION_MEMBERSHIP = "FederationMembershipCredential"
    ACCESS_TOKEN = "AccessTokenCredential"
    STATUS = "StatusCredential"


class VCStatus(Enum):
    """Status of a verifiable credential"""
    VALID = "valid"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    PENDING = "pending"


@dataclass
class VCConfig:
    """Configuration for VC management"""
    # Credential lifetime
    default_expiry_days: int = 90
    max_expiry_days: int = 365

    # Security
    require_verification: bool = True
    enable_revocation: bool = True
    enable_status_list: bool = True

    # Presentation
    allow_frame_selection: bool = True
    require_challenge: bool = True

    # Federation
    cross_instance_validation: bool = True
    trust_anchor_dids: List[str] = field(default_factory=list)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class VCProof:
    """Cryptographic proof for VC"""
    type: str = "Ed25519Signature2020"
    created: Optional[datetime] = None
    proof_purpose: str = "assertionMethod"
    verification_method: str = ""
    proof_value: Optional[str] = None
    challenge: Optional[str] = None
    domain: Optional[str] = None


@dataclass
class VCClaim:
    """A claim in a verifiable credential"""
    id: str = ""
    type: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifiableCredential:
    """W3C Verifiable Credential"""
    context: List[str] = field(default_factory=lambda: [
        "https://www.w3.org/2018/credentials/v1"
    ])
    type: List[str] = field(default_factory=lambda: ["VerifiableCredential"])
    id: str = ""
    issuer: str = ""  # DID of issuer
    issuance_date: datetime = field(default_factory=datetime.now)
    expiration_date: Optional[datetime] = None
    credential_subject: Dict[str, Any] = field(default_factory=dict)
    credential_status: Optional[Dict[str, Any]] = None
    refresh_service: Optional[Dict[str, Any]] = None
    terms_of_use: Optional[List[Dict[str, Any]]] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    proof: Optional[VCProof] = None

    # Metadata
    status: VCStatus = VCStatus.VALID
    revoked: bool = False
    revoked_at: Optional[datetime] = None

    def to_dict(self, include_proof: bool = True) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        result = {
            "@context": self.context,
            "type": self.type,
            "id": self.id,
            "issuer": self.issuer,
            "issuanceDate": self.issuance_date.isoformat(),
            "credentialSubject": self.credential_subject
        }

        if self.expiration_date:
            result["expirationDate"] = self.expiration_date.isoformat()

        if self.credential_status:
            result["credentialStatus"] = self.credential_status

        if self.refresh_service:
            result["refreshService"] = self.refresh_service

        if self.terms_of_use:
            result["termsOfUse"] = self.terms_of_use

        if self.evidence:
            result["evidence"] = self.evidence

        if include_proof and self.proof:
            result["proof"] = {
                "type": self.proof.type,
                "created": self.proof.created.isoformat() if self.proof.created else None,
                "proofPurpose": self.proof.proof_purpose,
                "verificationMethod": self.proof.verification_method,
                "proofValue": self.proof.proof_value,
                "challenge": self.proof.challenge,
                "domain": self.proof.domain
            }

        return result

    def is_valid(self, at_time: Optional[datetime] = None) -> bool:
        """Check if credential is valid at given time"""
        if self.revoked or self.status != VCStatus.VALID:
            return False

        check_time = at_time or datetime.now()

        if self.expiration_date and check_time > self.expiration_date:
            return False

        return True

    def get_age(self) -> timedelta:
        """Get age of credential"""
        return datetime.now() - self.issuance_date

    def get_time_until_expiry(self) -> Optional[timedelta]:
        """Get time until expiry"""
        if self.expiration_date:
            return self.expiration_date - datetime.now()
        return None


@dataclass
class VCPresentation:
    """Verifiable Credential Presentation"""
    context: List[str] = field(default_factory=lambda: [
        "https://www.w3.org/2018/credentials/v1"
    ])
    type: List[str] = field(default_factory=lambda: ["VerifiablePresentation"])
    id: str = ""
    verifiable_credential: List[VerifiableCredential] = field(default_factory=list)
    holder: Optional[str] = None  # DID of holder
    proof: Optional[VCProof] = None

    def to_dict(self, include_proof: bool = True) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        result = {
            "@context": self.context,
            "type": self.type,
            "id": self.id,
            "verifiableCredential": [
                vc.to_dict(include_proof=False) for vc in self.verifiable_credential
            ]
        }

        if self.holder:
            result["holder"] = self.holder

        if include_proof and self.proof:
            result["proof"] = {
                "type": self.proof.type,
                "created": self.proof.created.isoformat() if self.proof.created else None,
                "proofPurpose": self.proof.proof_purpose,
                "verificationMethod": self.proof.verification_method,
                "proofValue": self.proof.proof_value,
                "challenge": self.proof.challenge,
                "domain": self.proof.domain
            }

        return result


@dataclass
class VCVerificationResult:
    """Result of VC verification"""
    is_valid: bool = False
    status: VCStatus = VCStatus.PENDING
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.now)
    issuer_verified: bool = False
    signature_verified: bool = False
    expiration_checked: bool = False
    revocation_checked: bool = False


# ============================================================================
# VC Manager
# ============================================================================

class VerifiableCredentialManager:
    """
    Manages verifiable credentials for agents and instances.

    Features:
    - VC creation and signing
    - VC verification and validation
    - VC presentation
    - Credential revocation
    """

    def __init__(self, config: Optional[VCConfig] = None):
        self.config = config or VCConfig()

        # Get DID manager
        self.did_manager = get_did_manager() if DID_AVAILABLE else None

        # Storage (persist to DB in production)
        self._credentials: Dict[str, VerifiableCredential] = {}
        self._revocation_list: Set[str] = set()
        self._status_list: Dict[str, VCStatus] = {}

    def create_credential(
        self,
        issuer_did: str,
        credential_type: VCType,
        subject_did: str,
        claims: Dict[str, Any],
        expiry_days: Optional[int] = None,
        credential_id: Optional[str] = None
    ) -> VerifiableCredential:
        """
        Create a new verifiable credential.

        Args:
            issuer_did: DID of the issuer
            credential_type: Type of credential
            subject_did: DID of the subject
            claims: Credential claims
            expiry_days: Days until expiration
            credential_id: Optional custom credential ID

        Returns:
            Created verifiable credential
        """
        # Calculate expiration
        expiry_days = expiry_days or self.config.default_expiry_days
        expiry_days = min(expiry_days, self.config.max_expiry_days)
        expiration_date = datetime.now() + timedelta(days=expiry_days)

        # Generate ID
        credential_id = credential_id or f"urn:vc:{uuid4().hex}"

        # Build credential subject
        credential_subject = {
            "id": subject_did,
            "type": credential_type.value,
            **claims
        }

        # Create VC
        vc = VerifiableCredential(
            context=["https://www.w3.org/2018/credentials/v1"],
            type=["VerifiableCredential", credential_type.value],
            id=credential_id,
            issuer=issuer_did,
            issuance_date=datetime.now(),
            expiration_date=expiration_date,
            credential_subject=credential_subject,
            status=VCStatus.VALID
        )

        # Sign if DID manager available
        if self.did_manager:
            vc = self._sign_credential(vc, issuer_did)

        # Store
        self._credentials[credential_id] = vc
        self._status_list[credential_id] = VCStatus.VALID

        # Persist to DB (write-through; best-effort).
        self._persist_credential(vc)

        logger.info(f"Created VC: {credential_id} of type {credential_type.value}")
        return vc

    def _sign_credential(
        self,
        vc: VerifiableCredential,
        issuer_did: str
    ) -> VerifiableCredential:
        """Sign a credential with issuer's DID key"""
        if not CRYPTO_AVAILABLE:
            logger.warning("Cannot sign VC - cryptography not available")
            return vc

        # Get signing key from DID manager
        if not self.did_manager:
            return vc

        # Resolve DID to get key
        result = self.did_manager.resolve_did(issuer_did)
        if not result.did_document:
            logger.warning(f"Cannot resolve issuer DID: {issuer_did}")
            return vc

        # Create proof
        proof = VCProof(
            type="Ed25519Signature2020",
            created=datetime.now(),
            proof_purpose="assertionMethod",
            verification_method=f"{issuer_did}#key-1"
        )

        # Sign the credential (without proof)
        vc_data = vc.to_dict(include_proof=False)
        message = json.dumps(vc_data, sort_keys=True).encode()

        # Sign with private key (in production, use secure key)
        if self.did_manager and hasattr(self.did_manager, '_keys'):
            # Find the key for this DID
            for key_id, key in self.did_manager._keys.items():
                if key.controller == issuer_did and key.private_key_base58:
                    proof.proof_value = self._sign_with_key(
                        key, message
                    )
                    break

        vc.proof = proof
        return vc

    def _sign_with_key(self, key, message: bytes) -> str:
        """Sign message with private key"""
        if not CRYPTO_AVAILABLE:
            return ""

        try:
            private_bytes = bytes.fromhex(key.private_key_base58)
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)
            signature = private_key.sign(message)
            return signature.hex()
        except Exception as e:
            logger.warning(f"Failed to sign: {e}")
            return ""

    def verify_credential(
        self,
        vc: VerifiableCredential,
        at_time: Optional[datetime] = None,
        check_revocation: bool = True
    ) -> VCVerificationResult:
        """
        Verify a verifiable credential.

        Args:
            vc: The credential to verify
            at_time: Time to check validity
            check_revocation: Whether to check revocation status

        Returns:
            Verification result
        """
        result = VCVerificationResult(checked_at=at_time or datetime.now())

        # Check expiration
        result.expiration_checked = True
        if vc.expiration_date and result.checked_at > vc.expiration_date:
            result.status = VCStatus.EXPIRED
            result.errors.append("Credential has expired")

        # Check revocation
        result.revocation_checked = True
        if check_revocation and self._is_revoked(vc.id):
            result.status = VCStatus.REVOKED
            result.errors.append("Credential has been revoked")

        # Verify signature
        result.signature_verified = self._verify_signature(vc)

        if not result.signature_verified:
            result.errors.append("Invalid signature")
        else:
            result.issuer_verified = True

        # Verify issuer DID
        if self.did_manager:
            did_result = self.did_manager.resolve_did(vc.issuer)
            if not did_result.did_document:
                result.errors.append(f"Cannot resolve issuer DID: {vc.issuer}")
            else:
                result.issuer_verified = True

        # Determine final status
        if not result.errors:
            result.is_valid = True
            result.status = VCStatus.VALID
        elif "expired" in str(result.errors).lower():
            result.status = VCStatus.EXPIRED
        elif "revoked" in str(result.errors).lower():
            result.status = VCStatus.REVOKED
        else:
            result.status = VCStatus.PENDING

        return result

    def _verify_signature(self, vc: VerifiableCredential) -> bool:
        """Verify credential signature"""
        if not CRYPTO_AVAILABLE or not vc.proof:
            return False

        if not vc.proof.proof_value:
            return False

        # Get credential data without proof
        vc_data = vc.to_dict(include_proof=False)
        message = json.dumps(vc_data, sort_keys=True).encode()

        # Verify with DID manager
        if self.did_manager:
            signature = bytes.fromhex(vc.proof.proof_value)
            return self.did_manager.verify_signature(vc.issuer, message, signature)

        return False

    def _is_revoked(self, credential_id: str) -> bool:
        """Check if credential is revoked"""
        return credential_id in self._revocation_list

    def revoke_credential(
        self,
        credential_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Revoke a verifiable credential.

        Args:
            credential_id: ID of credential to revoke
            reason: Optional reason for revocation

        Returns:
            True if successful
        """
        if credential_id not in self._credentials:
            return False

        vc = self._credentials[credential_id]
        vc.revoked = True
        vc.revoked_at = datetime.now()
        vc.status = VCStatus.REVOKED

        self._revocation_list.add(credential_id)
        self._status_list[credential_id] = VCStatus.REVOKED

        # Persist revocation to DB.
        self._persist_credential(vc, revoked=True, revocation_reason=reason)

        logger.info(f"Revoked VC: {credential_id}" + (f" - Reason: {reason}" if reason else ""))
        return True

    def create_presentation(
        self,
        credentials: List[VerifiableCredential],
        holder_did: Optional[str] = None,
        challenge: Optional[str] = None
    ) -> VCPresentation:
        """
        Create a verifiable presentation.

        Args:
            credentials: Credentials to include
            holder_did: DID of the holder
            challenge: Optional challenge for binding

        Returns:
            Created presentation
        """
        presentation_id = f"urn:presentation:{uuid4().hex}"

        vp = VCPresentation(
            id=presentation_id,
            verifiable_credential=credentials,
            holder=holder_did
        )

        # Sign presentation if holder provided
        if holder_did and self.did_manager:
            proof = VCProof(
                type="Ed25519Signature2020",
                created=datetime.now(),
                proof_purpose="authentication",
                verification_method=f"{holder_did}#key-1",
                challenge=challenge
            )

            # Sign presentation
            vp_data = vp.to_dict(include_proof=False)
            message = json.dumps(vp_data, sort_keys=True).encode()

            # Get holder's key
            for key_id, key in self.did_manager._keys.items():
                if key.controller == holder_did and key.private_key_base58:
                    proof.proof_value = self._sign_with_key(key, message)
                    break

            vp.proof = proof

        logger.debug(f"Created presentation: {presentation_id}")
        return vp

    def verify_presentation(
        self,
        vp: VCPresentation,
        challenge: Optional[str] = None
    ) -> VCVerificationResult:
        """
        Verify a verifiable presentation.

        Args:
            vp: The presentation to verify
            challenge: Optional expected challenge

        Returns:
            Verification result
        """
        result = VCVerificationResult()

        # Verify challenge if required
        if self.config.require_challenge and challenge:
            if vp.proof and vp.proof.challenge != challenge:
                result.errors.append("Challenge mismatch")

        # Verify all credentials
        credential_results = []
        for vc in vp.verifiable_credential:
            vc_result = self.verify_credential(vc)
            credential_results.append(vc_result)

            if not vc_result.is_valid:
                result.errors.extend(vc_result.errors)

        # Verify presentation signature
        if vp.proof and vp.holder:
            vp_data = vp.to_dict(include_proof=False)
            message = json.dumps(vp_data, sort_keys=True).encode()

            if vp.proof.proof_value:
                signature = bytes.fromhex(vp.proof.proof_value)
                if self.did_manager:
                    result.signature_verified = self.did_manager.verify_signature(
                        vp.holder, message, signature
                    )

        # Determine validity
        if not result.errors and all(cr.is_valid for cr in credential_results):
            result.is_valid = True
            result.status = VCStatus.VALID

        return result

    def create_agent_identity_credential(
        self,
        issuer_did: str,
        agent_did: str,
        agent_id: str,
        agent_name: str,
        capabilities: List[str],
        instance_id: Optional[str] = None
    ) -> VerifiableCredential:
        """
        Create an agent identity credential.

        Args:
            issuer_did: DID of the issuer (instance)
            agent_did: DID of the agent
            agent_id: Internal agent ID
            agent_name: Human-readable name
            capabilities: List of agent capabilities
            instance_id: Optional instance ID

        Returns:
            Agent identity credential
        """
        claims = {
            "agentId": agent_id,
            "agentName": agent_name,
            "capabilities": capabilities,
            "instanceId": instance_id or "",
            "maturityLevel": "STUDENT"  # Default maturity
        }

        return self.create_credential(
            issuer_did=issuer_did,
            credential_type=VCType.AGENT_IDENTITY,
            subject_did=agent_did,
            claims=claims
        )

    def create_federation_membership_credential(
        self,
        issuer_did: str,
        instance_did: str,
        instance_id: str,
        instance_name: str,
        federation_role: str = "member"
    ) -> VerifiableCredential:
        """
        Create a federation membership credential.

        Args:
            issuer_did: DID of the federation issuer
            instance_did: DID of the instance
            instance_id: Internal instance ID
            instance_name: Human-readable name
            federation_role: Role in federation

        Returns:
            Federation membership credential
        """
        claims = {
            "instanceId": instance_id,
            "instanceName": instance_name,
            "federationRole": federation_role,
            "permissions": self._get_default_permissions(federation_role)
        }

        return self.create_credential(
            issuer_did=issuer_did,
            credential_type=VCType.FEDERATION_MEMBERSHIP,
            subject_did=instance_did,
            claims=claims
        )

    def _get_default_permissions(self, role: str) -> List[str]:
        """Get default permissions for federation role"""
        permissions_map = {
            "admin": ["read", "write", "delete", "admin"],
            "member": ["read", "write"],
            "observer": ["read"]
        }
        return permissions_map.get(role, ["read"])

    def get_credential_by_id(self, credential_id: str) -> Optional[VerifiableCredential]:
        """Get credential by ID"""
        return self._credentials.get(credential_id)

    def get_credentials_by_subject(
        self,
        subject_did: str,
        credential_type: Optional[VCType] = None
    ) -> List[VerifiableCredential]:
        """Get all credentials for a subject"""
        credentials = [
            vc for vc in self._credentials.values()
            if vc.credential_subject.get("id") == subject_did
        ]

        if credential_type:
            credentials = [
                vc for vc in credentials
                if credential_type.value in vc.type
            ]

        return credentials

    # ------------------------------------------------------------------
    # DB persistence (write-through + load-on-init)
    # ------------------------------------------------------------------

    def _persist_credential(self, vc, revoked: bool = False, revocation_reason: Optional[str] = None) -> None:
        """Write-through a verifiable credential to the DB."""
        try:
            from core.database import get_db_session
            from core.models import FederationCredential
            from datetime import timezone as _tz
            with get_db_session() as db:
                existing = db.query(FederationCredential).filter(
                    FederationCredential.credential_id == vc.id
                ).first()

                claims_data = {}
                if hasattr(vc, 'credential_subject') and vc.credential_subject:
                    claims_data = vc.credential_subject if isinstance(vc.credential_subject, dict) else {"value": str(vc.credential_subject)}

                status = "revoked" if revoked else "active"
                if revoked:
                    from datetime import datetime as _dt
                    revoked_at = _dt.now(_tz.utc)
                else:
                    revoked_at = None

                if existing:
                    existing.status = status
                    existing.claims_json = claims_data
                    if revoked:
                        existing.revoked_at = revoked_at
                        existing.revocation_reason = revocation_reason
                else:
                    row = FederationCredential(
                        credential_id=vc.id,
                        issuer_did=vc.issuer if hasattr(vc, 'issuer') else "unknown",
                        subject_did=str(vc.credential_subject.get('id', '')) if isinstance(claims_data, dict) else "unknown",
                        credential_type=str(vc.type) if hasattr(vc, 'type') else "unknown",
                        claims_json=claims_data,
                        status=status,
                        expires_at=vc.expiration_date if hasattr(vc, 'expiration_date') else None,
                        revoked_at=revoked_at,
                        revocation_reason=revocation_reason,
                    )
                    db.add(row)
        except Exception as e:
            logger.debug(f"VC DB persist skipped (non-fatal): {e}")

    def load_credentials_from_db(self) -> int:
        """Load persisted credentials from the DB into in-memory state."""
        try:
            from core.database import get_db_session
            from core.models import FederationCredential
            with get_db_session() as db:
                rows = db.query(FederationCredential).all()
                loaded = 0
                for row in rows:
                    if row.credential_id not in self._status_list:
                        self._status_list[row.credential_id] = row.status or "active"
                        if row.status == "revoked":
                            self._revocation_list.add(row.credential_id)
                        loaded += 1
                if loaded:
                    logger.info(f"Loaded {loaded} VCs from DB")
                return loaded
        except Exception as e:
            logger.debug(f"VC DB load skipped (non-fatal): {e}")
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get VC manager statistics"""
        active = sum(1 for vc in self._credentials.values() if vc.is_valid())
        expired = sum(1 for vc in self._credentials.values()
                     if vc.expiration_date and vc.expiration_date < datetime.now())
        revoked = len(self._revocation_list)

        return {
            "total_credentials": len(self._credentials),
            "active_credentials": active,
            "expired_credentials": expired,
            "revoked_credentials": revoked,
            "revocation_list_size": len(self._revocation_list),
            "status_list_size": len(self._status_list)
        }


# ============================================================================
# Factory
# ============================================================================

_vc_manager_instance: Optional[VerifiableCredentialManager] = None


def get_vc_manager(config: Optional[VCConfig] = None) -> VerifiableCredentialManager:
    """Get or create VC manager instance"""
    global _vc_manager_instance
    if _vc_manager_instance is None:
        _vc_manager_instance = VerifiableCredentialManager(config)
    return _vc_manager_instance
