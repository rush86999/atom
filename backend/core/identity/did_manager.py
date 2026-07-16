"""
Decentralized Identifier (DID) Management

Based on 2025-2026 research:
- DID Core specification (W3C)
- did:atom method for agent identities
- Zero-Trust Identity Framework (arXiv:2505.19301v2)

Implements:
- DID generation and resolution
- DID document management
- Cross-instance DID resolution
- Agent and instance DIDs
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logging.warning("Cryptography library not available - DIDs will be insecure")

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class DIDMethod(Enum):
    """Supported DID methods"""
    ATOM = "did:atom"  # Atom-specific method for agents
    WEB = "did:web"    # Web-based DIDs
    KEY = "did:key"    # Key-based DIDs
    PKH = "did:pkh"    # Public key hash (Ethereum)


class DIDType(Enum):
    """Types of DIDs in the Atom system"""
    AGENT = "agent"          # Agent-specific DID
    INSTANCE = "instance"    # Instance DID
    WORKSPACE = "workspace"  # Workspace DID
    USER = "user"           # User DID


@dataclass
class DIDConfig:
    """Configuration for DID management"""
    # DID method to use
    method: DIDMethod = DIDMethod.ATOM

    # Key management
    key_type: str = "ed25519"  # ed25519, secp256k1, rsa
    key_rotation_days: int = 90  # Key rotation interval

    # Resolution
    resolution_timeout_ms: int = 5000
    cache_ttl_seconds: int = 300

    # Security
    enable_key_rotation: bool = True
    require_verification: bool = True

    # Federation
    federation_resolution: bool = True
    trust_anchor_dids: List[str] = field(default_factory=list)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DIDKey:
    """Cryptographic key for DID"""
    id: str = ""
    type: str = "Ed25519VerificationKey2020"
    controller: str = ""
    public_key_base58: str = ""
    private_key_base58: Optional[str] = None  # Only for owner
    created_at: datetime = field(default_factory=datetime.now)
    revoked: bool = False
    expires_at: Optional[datetime] = None

    def __hash__(self):
        return hash(self.id)


@dataclass
class DIDVerificationMethod:
    """Verification method in DID document"""
    id: str = ""
    type: str = "Ed25519VerificationKey2020"
    controller: str = ""
    public_key_base58: str = ""


@dataclass
class DIDService:
    """Service endpoint in DID document"""
    id: str = ""
    type: str = ""
    service_endpoint: str = ""
    description: Optional[str] = None


@dataclass
class DIDDocument:
    """DID Document as per W3C spec"""
    context: List[str] = field(default_factory=lambda: ["https://www.w3.org/ns/did/v1"])
    id: str = ""
    controller: Optional[str] = None

    # Verification methods
    verification_method: List[DIDVerificationMethod] = field(default_factory=list)
    authentication: List[str] = field(default_factory=list)
    assertion_method: List[str] = field(default_factory=list)
    capability_invocation: List[str] = field(default_factory=list)
    capability_delegation: List[str] = field(default_factory=list)

    # Services
    service: List[DIDService] = field(default_factory=list)

    # Metadata
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)
    version_id: str = ""
    deactivated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            "@context": self.context,
            "id": self.id,
            "controller": self.controller,
            "verificationMethod": [
                {
                    "id": vm.id,
                    "type": vm.type,
                    "controller": vm.controller,
                    "publicKeyBase58": vm.public_key_base58
                }
                for vm in self.verification_method
            ],
            "authentication": self.authentication,
            "assertionMethod": self.assertion_method,
            "capabilityInvocation": self.capability_invocation,
            "capabilityDelegation": self.capability_delegation,
            "service": [
                {
                    "id": s.id,
                    "type": s.type,
                    "serviceEndpoint": s.service_endpoint,
                    "description": s.description
                }
                for s in self.service
            ],
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "versionId": self.version_id,
            "deactivated": self.deactivated
        }


@dataclass
class DIDResolutionResult:
    """Result of DID resolution"""
    did: str = ""
    did_document: Optional[DIDDocument] = None
    resolution_metadata: Dict[str, Any] = field(default_factory=dict)
    did_resolution_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            "did": self.did,
            "didDocument": self.did_document.to_dict() if self.did_document else None,
            "resolutionMetadata": self.resolution_metadata,
            "didResolutionMetadata": self.did_resolution_metadata
        }


# ============================================================================
# DID Manager
# ============================================================================

class DIDManager:
    """
    Manages Decentralized Identifiers for agents and instances.

    Features:
    - DID generation for multiple entity types
    - DID document management
    - Cross-instance resolution
    - Key rotation support
    """

    def __init__(self, config: Optional[DIDConfig] = None):
        self.config = config or DIDConfig()

        # Storage (persist to DB in production)
        self._did_documents: Dict[str, DIDDocument] = {}
        self._keys: Dict[str, DIDKey] = {}
        self._resolution_cache: Dict[str, Tuple[DIDDocument, datetime]] = {}

        # Federation registry for cross-instance resolution
        self._federation_registry: Dict[str, str] = {}  # instance_id -> base_url

    def generate_did(
        self,
        entity_type: DIDType,
        entity_id: str,
        instance_id: Optional[str] = None
    ) -> str:
        """
        Generate a DID for an entity.

        Args:
            entity_type: Type of entity (agent, instance, workspace, user)
            entity_id: Unique identifier for the entity
            instance_id: Optional instance ID for namespacing

        Returns:
            Generated DID string
        """
        if self.config.method == DIDMethod.ATOM:
            # did:atom:{instance_id}:{entity_type}:{entity_id}
            if instance_id:
                did = f"did:atom:{instance_id}:{entity_type.value}:{entity_id}"
            else:
                did = f"did:atom:{entity_type.value}:{entity_id}"
        elif self.config.method == DIDMethod.KEY:
            # Generate from public key
            key = self._generate_keypair()
            public_key_hash = hashlib.sha256(key.public_key_base58.encode()).hexdigest()[:16]
            did = f"did:key:z{public_key_hash}"
        else:
            # Fallback to atom method
            did = f"did:atom:{entity_type.value}:{entity_id}"

        logger.debug(f"Generated DID: {did} for {entity_type.value}:{entity_id}")
        return did

    def create_did_document(
        self,
        did: str,
        entity_type: DIDType,
        services: Optional[List[DIDService]] = None
    ) -> DIDDocument:
        """
        Create a DID document for an entity.

        Args:
            did: The DID string
            entity_type: Type of entity
            services: Optional service endpoints

        Returns:
            Created DID document
        """
        # Generate keypair
        key = self._generate_keypair()
        key_id = f"{did}#key-1"
        key.id = key_id
        key.controller = did

        # Create verification method
        vm = DIDVerificationMethod(
            id=key_id,
            type=f"Ed25519VerificationKey2020",
            controller=did,
            public_key_base58=key.public_key_base58
        )

        # Build document
        doc = DIDDocument(
            id=did,
            verification_method=[vm],
            authentication=[key_id],
            assertion_method=[key_id],
            capability_invocation=[key_id],
            capability_delegation=[key_id],
            service=services or [],
            created=datetime.now(),
            updated=datetime.now(),
            version_id=self._generate_version_id()
        )

        # Store
        self._did_documents[did] = doc
        self._keys[key_id] = key

        # Persist to DB (write-through; best-effort).
        self._persist_did(did, entity_type, doc, key)

        logger.info(f"Created DID document for {did}")
        return doc

    def resolve_did(
        self,
        did: str,
        use_cache: bool = True
    ) -> DIDResolutionResult:
        """
        Resolve a DID to its DID document.

        Args:
            did: The DID string to resolve
            use_cache: Whether to use cached results

        Returns:
            DID resolution result
        """
        # Check cache first
        if use_cache and did in self._resolution_cache:
            cached_doc, cached_time = self._resolution_cache[did]
            if datetime.now() - cached_time < timedelta(seconds=self.config.cache_ttl_seconds):
                return DIDResolutionResult(
                    did=did,
                    did_document=cached_doc,
                    resolution_metadata={"from_cache": True}
                )

        # Determine resolution method
        if did.startswith("did:atom:"):
            result = self._resolve_atom_did(did)
        elif did.startswith("did:web:"):
            result = self._resolve_web_did(did)
        elif did.startswith("did:key:"):
            result = self._resolve_key_did(did)
        else:
            result = DIDResolutionResult(
                did=did,
                resolution_metadata={"error": "Unsupported DID method"}
            )

        # Cache successful resolutions
        if result.did_document and use_cache:
            self._resolution_cache[did] = (result.did_document, datetime.now())

        return result

    def _resolve_atom_did(self, did: str) -> DIDResolutionResult:
        """Resolve did:atom DIDs"""
        # Check local storage
        if did in self._did_documents:
            return DIDResolutionResult(
                did=did,
                did_document=self._did_documents[did],
                resolution_metadata={"resolved": "locally"}
            )

        # Try federation resolution
        if self.config.federation_resolution:
            instance_id = self._extract_instance_id_from_did(did)
            if instance_id and instance_id in self._federation_registry:
                result = self._resolve_via_federation(did, instance_id)
                if result.did_document:
                    return result

        # Not found
        return DIDResolutionResult(
            did=did,
            resolution_metadata={"error": "DID not found"}
        )

    def _resolve_web_did(self, did: str) -> DIDResolutionResult:
        """Resolve did:web DIDs"""
        # Extract domain from did:web:domain
        parts = did.split(":")
        if len(parts) < 3:
            return DIDResolutionResult(
                did=did,
                resolution_metadata={"error": "Invalid did:web format"}
            )

        # In production, fetch from https://{domain}/.well-known/did.json
        return DIDResolutionResult(
            did=did,
            resolution_metadata={"error": "Web resolution not implemented"}
        )

    def _resolve_key_did(self, did: str) -> DIDResolutionResult:
        """Resolve did:key DIDs"""
        # did:key is self-describing - the DID itself contains the key
        # Parse the key and create a minimal DID document
        parts = did.split(":")
        if len(parts) < 3 or not parts[2].startswith("z"):
            return DIDResolutionResult(
                did=did,
                resolution_metadata={"error": "Invalid did:key format"}
            )

        # Create minimal document with key
        key_id = f"{did}#controller"
        vm = DIDVerificationMethod(
            id=key_id,
            type="Ed25519VerificationKey2020",
            controller=did,
            public_key_base58=parts[2][1:]  # Remove 'z' prefix
        )

        doc = DIDDocument(
            id=did,
            verification_method=[vm],
            authentication=[key_id],
            assertion_method=[key_id],
            created=datetime.now(),
            updated=datetime.now()
        )

        return DIDResolutionResult(
            did=did,
            did_document=doc,
            resolution_metadata={"resolved": "inline"}
        )

    def _resolve_via_federation(
        self,
        did: str,
        instance_id: str
    ) -> DIDResolutionResult:
        """Resolve DID via federation registry"""
        # In production, make HTTP request to federated instance
        # GET https://{instance_base_url}/.well-known/did.json/{did}
        base_url = self._federation_registry[instance_id]
        logger.debug(f"Would resolve {did} via federation at {base_url}")

        return DIDResolutionResult(
            did=did,
            resolution_metadata={"error": "Federation resolution not implemented"}
        )

    def _extract_instance_id_from_did(self, did: str) -> Optional[str]:
        """Extract instance ID from did:atom DID"""
        parts = did.split(":")
        if len(parts) >= 4 and parts[1] == "atom":
            # did:atom:{instance_id}:{type}:{id}
            return parts[2]
        return None

    def verify_signature(
        self,
        did: str,
        message: bytes,
        signature: bytes
    ) -> bool:
        """
        Verify a signature using DID's verification method.

        Args:
            did: The DID that created the signature
            message: The signed message
            signature: The signature bytes

        Returns:
            True if signature is valid
        """
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography not available - cannot verify signature")
            return False

        result = self.resolve_did(did)
        if not result.did_document:
            return False

        doc = result.did_document
        if not doc.verification_method:
            return False

        # Get first verification method
        vm = doc.verification_method[0]

        # Find corresponding key
        key_id = f"{did}#key-1"
        if key_id not in self._keys:
            # Try to find by public key
            for key in self._keys.values():
                if key.public_key_base58 == vm.public_key_base58:
                    return self._verify_with_key(key, message, signature)
            return False

        key = self._keys[key_id]
        return self._verify_with_key(key, message, signature)

    def _verify_with_key(
        self,
        key: DIDKey,
        message: bytes,
        signature: bytes
    ) -> bool:
        """Verify signature with specific key"""
        if not CRYPTO_AVAILABLE or key.revoked:
            return False

        try:
            # Decode public key
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(key.public_key_base58)
            )
            public_key.verify(signature, message)
            return True
        except Exception as e:
            logger.debug(f"Signature verification failed: {e}")
            return False

    def rotate_key(self, did: str) -> bool:
        """
        Rotate the key for a DID.

        Args:
            did: The DID to rotate keys for

        Returns:
            True if successful
        """
        if did not in self._did_documents:
            return False

        doc = self._did_documents[did]

        # Generate new key
        new_key = self._generate_keypair()
        new_key_id = f"{did}#key-{len(doc.verification_method) + 1}"
        new_key.id = new_key_id
        new_key.controller = did

        # Create new verification method
        vm = DIDVerificationMethod(
            id=new_key_id,
            type="Ed25519VerificationKey2020",
            controller=did,
            public_key_base58=new_key.public_key_base58
        )

        # Add to document
        doc.verification_method.append(vm)
        doc.authentication.append(new_key_id)
        doc.assertion_method.append(new_key_id)

        # Update timestamp
        doc.updated = datetime.now()
        doc.version_id = self._generate_version_id()

        # Store key
        self._keys[new_key_id] = new_key

        logger.info(f"Rotated key for {did}")
        return True

    def deactivate_did(self, did: str) -> bool:
        """
        Deactivate a DID.

        Args:
            did: The DID to deactivate

        Returns:
            True if successful
        """
        if did not in self._did_documents:
            return False

        doc = self._did_documents[did]
        doc.deactivated = True
        doc.updated = datetime.now()

        # Revoke all keys
        for key in self._keys.values():
            if key.controller == did:
                key.revoked = True

        logger.info(f"Deactivated {did}")
        return True

    def register_federation_instance(
        self,
        instance_id: str,
        base_url: str
    ) -> None:
        """Register an instance for federation resolution"""
        self._federation_registry[instance_id] = base_url
        logger.debug(f"Registered federation instance: {instance_id} at {base_url}")

    def _generate_keypair(self) -> DIDKey:
        """Generate a new keypair"""
        if CRYPTO_AVAILABLE:
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()

            # Serialize to base58-like format (hex for simplicity)
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )

            private_hex = private_bytes.hex()
            public_hex = public_bytes.hex()
        else:
            # Fallback: generate random bytes
            import os
            private_hex = os.urandom(32).hex()
            public_hex = hashlib.sha256(private_hex.encode()).hexdigest()

        return DIDKey(
            public_key_base58=public_hex,
            private_key_base58=private_hex
        )

    def _generate_version_id(self) -> str:
        """Generate a version ID for DID document"""
        return hashlib.sha256(datetime.now().isoformat().encode()).hexdigest()[:16]

    def get_statistics(self) -> Dict[str, Any]:
        """Get DID manager statistics"""
        return {
            "total_dids": len(self._did_documents),
            "total_keys": len(self._keys),
            "active_dids": sum(1 for d in self._did_documents.values() if not d.deactivated),
            "federation_instances": len(self._federation_registry),
            "cache_size": len(self._resolution_cache)
        }

    # ------------------------------------------------------------------
    # DB persistence (write-through + load-on-init)
    # ------------------------------------------------------------------

    def _persist_did(self, did: str, entity_type: DIDType, doc: DIDDocument, key: DIDKey) -> None:
        """Write-through a DID document to the DB so it survives restarts."""
        try:
            from core.database import get_db_session
            from core.models import FederationDID
            with get_db_session() as db:
                existing = db.query(FederationDID).filter(FederationDID.did == did).first()
                doc_data = {
                    "id": doc.id,
                    "verification_method": [vm.__dict__ for vm in (doc.verification_method or [])],
                    "authentication": doc.authentication,
                    "created": doc.created.isoformat() if doc.created else None,
                    "updated": doc.updated.isoformat() if doc.updated else None,
                    "version_id": doc.version_id,
                }
                if existing:
                    existing.entity_type = entity_type.value
                    existing.document_json = doc_data
                    existing.public_key_pem = key.public_key_base58
                else:
                    row = FederationDID(
                        did=did,
                        entity_type=entity_type.value,
                        entity_id=did.split(":")[-1] if ":" in did else did,
                        document_json=doc_data,
                        public_key_pem=key.public_key_base58,
                    )
                    db.add(row)
        except Exception as e:
            logger.debug(f"DID DB persist skipped (non-fatal): {e}")

    def load_dids_from_db(self) -> int:
        """Load persisted DIDs from the DB into in-memory state.

        Call on startup so identity state survives restarts. Returns count.
        """
        try:
            from core.database import get_db_session
            from core.models import FederationDID
            with get_db_session() as db:
                rows = db.query(FederationDID).filter(FederationDID.is_active == True).all()  # noqa: E712
                loaded = 0
                for row in rows:
                    if row.did not in self._did_documents and row.document_json:
                        # Reconstruct a minimal DIDDocument from stored data.
                        doc_data = row.document_json
                        doc = DIDDocument(
                            id=doc_data.get("id", row.did),
                            verification_method=[],
                            authentication=doc_data.get("authentication", []),
                            created=datetime.fromisoformat(doc_data["created"]) if doc_data.get("created") else datetime.now(),
                            updated=datetime.now(),
                            version_id=doc_data.get("version_id", "1"),
                        )
                        self._did_documents[row.did] = doc
                        loaded += 1
                if loaded:
                    logger.info(f"Loaded {loaded} DIDs from DB")
                return loaded
        except Exception as e:
            logger.debug(f"DID DB load skipped (non-fatal): {e}")
            return 0


# ============================================================================
# Factory
# ============================================================================

_did_manager_instance: Optional[DIDManager] = None


def get_did_manager(config: Optional[DIDConfig] = None) -> DIDManager:
    """Get or create DID manager instance"""
    global _did_manager_instance
    if _did_manager_instance is None:
        _did_manager_instance = DIDManager(config)
    return _did_manager_instance
