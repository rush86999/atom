"""
Zero-Trust Security Framework for Federation

Based on 2025-2026 research:
- Zero-Trust Identity Framework (arXiv:2505.19301v2)
- Agentic Identity and Access Control (Coalition for Secure AI)
- OpenID: AI Agent Identity Challenges

Core Principles:
1. Never trust, always verify
2. Least privilege access
3. Assume breach mentality
4. Verify explicitly

Implements:
- Per-request identity verification
- Credential validation at boundaries
- Audit trail for all access
- Policy-based access control
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque

try:
    from core.identity.did_manager import DIDManager, get_did_manager
    from core.identity.verifiable_credentials import (
        VerifiableCredential,
        VerifiableCredentialManager,
        VCType,
        get_vc_manager
    )
    IDENTITY_AVAILABLE = True
except ImportError:
    IDENTITY_AVAILABLE = False
    logging.warning("Identity modules not available")

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class SecurityLevel(Enum):
    """Security levels for federation requests"""
    NONE = "none"           # No security (development only)
    LOW = "low"             # Basic authentication
    MEDIUM = "medium"       # Authentication + credential check
    HIGH = "high"           # Full zero-trust verification
    CRITICAL = "critical"   # Maximum security + anomaly detection


class AccessAction(Enum):
    """Actions that can be performed"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    EXECUTE = "execute"
    FEDERATE = "federate"


class DecisionReason(Enum):
    """Reasons for access decisions"""
    VALID_CREDENTIALS = "valid_credentials"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    EXPIRED_CREDENTIAL = "expired_credential"
    REVOKED_CREDENTIAL = "revoked_credential"
    ANOMALY_DETECTED = "anomaly_detected"
    UNKNOWN_IDENTITY = "unknown_identity"
    INVALID_SIGNATURE = "invalid_signature"
    POLICY_VIOLATION = "policy_violation"
    RATE_LIMITED = "rate_limited"


@dataclass
class SecurityConfig:
    """Configuration for zero-trust security"""
    # Verification
    require_authentication: bool = True
    require_credential: bool = True
    require_signature: bool = True

    # Credential validation
    check_revocation: bool = True
    check_expiration: bool = True
    min_security_level: SecurityLevel = SecurityLevel.MEDIUM

    # Rate limiting
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 1000
    max_requests_per_hour: int = 10000

    # Anomaly detection
    enable_anomaly_detection: bool = True
    anomaly_threshold: float = 0.7

    # Audit
    enable_audit_log: bool = True
    audit_retention_days: int = 90

    # Policies
    default_policy: str = "deny"  # allow or deny
    trust_anchor_dids: List[str] = field(default_factory=list)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SecurityContext:
    """Security context for a request"""
    request_id: str = ""
    source_instance_id: str = ""
    source_did: Optional[str] = None
    presented_credentials: List[VerifiableCredential] = field(default_factory=list)
    signature: Optional[bytes] = None
    timestamp: datetime = field(default_factory=datetime.now)
    user_agent: str = ""
    ip_address: str = ""

    # Computed properties
    is_authenticated: bool = False
    is_authorized: bool = False
    security_level: SecurityLevel = SecurityLevel.NONE


@dataclass
class FederationRequest:
    """A federation request with security context"""
    request_id: str = ""
    method: str = ""  # GET, POST, etc.
    path: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[bytes] = None
    query_params: Dict[str, str] = field(default_factory=dict)

    # Security context
    security_context: Optional[SecurityContext] = None

    # Requested action
    action: AccessAction = AccessAction.READ
    resource_type: str = ""
    resource_id: str = ""

    # Timestamp
    received_at: datetime = field(default_factory=datetime.now)

    def get_fingerprint(self) -> str:
        """Get unique fingerprint for request"""
        data = f"{self.method}:{self.path}:{self.security_context.source_did}:{self.security_context.timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class SecurityPolicy:
    """Security policy for access control"""
    id: str = ""
    name: str = ""
    description: str = ""

    # Conditions
    required_security_level: SecurityLevel = SecurityLevel.MEDIUM
    required_credentials: List[VCType] = field(default_factory=list)
    allowed_actions: List[AccessAction] = field(default_factory=list)

    # Resource constraints
    allowed_resources: List[str] = field(default_factory=list)  # Regex patterns
    denied_resources: List[str] = field(default_factory=list)

    # Temporal constraints
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # IP constraints
    allowed_ips: List[str] = field(default_factory=list)
    denied_ips: List[str] = field(default_factory=list)

    # DID constraints
    allowed_dids: List[str] = field(default_factory=list)
    denied_dids: List[str] = field(default_factory=list)

    # Default decision
    default_decision: bool = False

    def matches(self, request: FederationRequest) -> bool:
        """Check if policy matches request"""
        # Check security level
        if request.security_context:
            level_order = {SecurityLevel.NONE: 0, SecurityLevel.LOW: 1,
                          SecurityLevel.MEDIUM: 2, SecurityLevel.HIGH: 3,
                          SecurityLevel.CRITICAL: 4}
            if level_order.get(request.security_context.security_level, 0) < level_order.get(self.required_security_level, 0):
                return False

        # Check action
        if self.allowed_actions and request.action not in self.allowed_actions:
            return False

        # Check resource constraints
        if self.denied_resources:
            import re
            for pattern in self.denied_resources:
                if re.match(pattern, request.resource_id):
                    return False

        if self.allowed_resources:
            import re
            matched = any(re.match(pattern, request.resource_id) for pattern in self.allowed_resources)
            if not matched:
                return False

        # Check temporal constraints
        now = datetime.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False

        return True


@dataclass
class AccessDecision:
    """Decision on federation access"""
    allowed: bool = False
    reason: DecisionReason = DecisionReason.POLICY_VIOLATION
    policy_id: str = ""
    message: str = ""

    # Timing
    evaluated_at: datetime = field(default_factory=datetime.now)
    evaluation_time_ms: float = 0.0

    # Conditions
    conditions_met: List[str] = field(default_factory=list)
    conditions_failed: List[str] = field(default_factory=list)

    # Metadata
    request_fingerprint: str = ""
    security_level: SecurityLevel = SecurityLevel.NONE


@dataclass
class AuditLogEntry:
    """Entry in security audit log"""
    timestamp: datetime = field(default_factory=datetime.now)
    request_id: str = ""
    source_instance: str = ""
    source_did: str = ""
    action: str = ""
    resource: str = ""
    decision: str = ""  # allow or deny
    reason: str = ""
    policy_id: str = ""
    security_level: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for logging"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
            "source_instance": self.source_instance,
            "source_did": self.source_did,
            "action": self.action,
            "resource": self.resource,
            "decision": self.decision,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "security_level": self.security_level
        }


# ============================================================================
# Zero-Trust Security Manager
# ============================================================================

class ZeroTrustSecurityManager:
    """
    Implements zero-trust security for federation.

    Core Principles:
    1. Verify explicitly - Never trust, always verify
    2. Least privilege - Minimum required access
    3. Assume breach - Continuous validation
    """

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()

        # Get identity managers
        self.did_manager = get_did_manager() if IDENTITY_AVAILABLE else None
        self.vc_manager = get_vc_manager() if IDENTITY_AVAILABLE else None

        # Policies
        self._policies: Dict[str, SecurityPolicy] = {}
        self._default_policies_loaded = False

        # Rate limiting
        self._rate_limits: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.config.max_requests_per_minute))

        # Audit log
        self._audit_log: List[AuditLogEntry] = []

        # Statistics
        self._stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "denied_requests": 0,
            "anomalies_detected": 0
        }

    def verify_request(
        self,
        request: FederationRequest
    ) -> AccessDecision:
        """
        Verify a federation request using zero-trust principles.

        Args:
            request: The federation request to verify

        Returns:
            Access decision
        """
        start_time = datetime.now()

        # Build security context
        if not request.security_context:
            request.security_context = self._build_security_context(request)

        self._stats["total_requests"] += 1

        # Step 1: Authentication (verify identity)
        auth_result = self._authenticate(request)
        if not auth_result:
            decision = AccessDecision(
                allowed=False,
                reason=DecisionReason.UNKNOWN_IDENTITY,
                message="Authentication failed - unknown identity",
                evaluation_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                request_fingerprint=request.get_fingerprint()
            )
            self._log_decision(request, decision)
            return decision

        # Step 2: Credential validation
        cred_result = self._validate_credentials(request)
        if not cred_result["valid"]:
            decision = AccessDecision(
                allowed=False,
                reason=cred_result.get("reason", DecisionReason.INVALID_SIGNATURE),
                message=cred_result.get("message", "Credential validation failed"),
                evaluation_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                request_fingerprint=request.get_fingerprint()
            )
            self._log_decision(request, decision)
            return decision

        # Step 3: Policy evaluation
        policy_result = self._evaluate_policies(request)
        if not policy_result.allowed:
            self._log_decision(request, policy_result)
            return policy_result

        # Step 4: Rate limiting
        if self.config.enable_rate_limiting:
            if not self._check_rate_limit(request):
                decision = AccessDecision(
                    allowed=False,
                    reason=DecisionReason.RATE_LIMITED,
                    message="Rate limit exceeded",
                    evaluation_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                    request_fingerprint=request.get_fingerprint()
                )
                self._log_decision(request, decision)
                return decision

        # All checks passed
        decision = AccessDecision(
            allowed=True,
            reason=DecisionReason.VALID_CREDENTIALS,
            message="Access granted",
            policy_id=policy_result.policy_id,
            evaluation_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            request_fingerprint=request.get_fingerprint(),
            security_level=request.security_context.security_level if request.security_context else SecurityLevel.NONE
        )

        self._stats["allowed_requests"] += 1
        self._log_decision(request, decision)
        return decision

    def _build_security_context(self, request: FederationRequest) -> SecurityContext:
        """Build security context from request"""
        context = SecurityContext(
            request_id=request.request_id,
            timestamp=request.received_at
        )

        # Extract headers
        context.source_instance_id = request.headers.get("X-Instance-ID", "")
        source_did = request.headers.get("X-Source-DID", "")

        # Extract credentials from header
        creds_header = request.headers.get("X-Verifiable-Credentials", "")
        if creds_header:
            try:
                cred_ids = creds_header.split(",")
                for cred_id in cred_ids:
                    if self.vc_manager:
                        vc = self.vc_manager.get_credential_by_id(cred_id.strip())
                        if vc:
                            context.presented_credentials.append(vc)
            except Exception as e:
                logger.warning(f"Failed to parse credentials header: {e}")

        # Set DID
        if source_did:
            context.source_did = source_did

        return context

    def _authenticate(self, request: FederationRequest) -> bool:
        """Authenticate the request"""
        if not self.config.require_authentication:
            return True

        context = request.security_context
        if not context:
            return False

        # Check for source DID
        if not context.source_did:
            return False

        # Verify DID exists
        if self.did_manager:
            result = self.did_manager.resolve_did(context.source_did)
            if not result.did_document:
                return False

        context.is_authenticated = True
        return True

    def _validate_credentials(self, request: FederationRequest) -> Dict[str, Any]:
        """Validate presented credentials"""
        if not self.config.require_credential:
            return {"valid": True}

        context = request.security_context
        if not context:
            return {"valid": False, "reason": DecisionReason.UNKNOWN_IDENTITY}

        # Check if credentials were presented
        if not context.presented_credentials:
            return {
                "valid": False,
                "reason": DecisionReason.INSUFFICIENT_PERMISSIONS,
                "message": "No credentials presented"
            }

        # Validate each credential
        for vc in context.presented_credentials:
            if not self.vc_manager:
                continue

            result = self.vc_manager.verify_credential(
                vc,
                check_revocation=self.config.check_revocation
            )

            if not result.is_valid:
                return {
                    "valid": False,
                    "reason": DecisionReason.REVOKED_CREDENTIAL if result.status.value == "revoked"
                            else DecisionReason.EXPIRED_CREDENTIAL if result.status.value == "expired"
                            else DecisionReason.INVALID_SIGNATURE,
                    "message": f"Credential validation failed: {', '.join(result.errors)}"
                }

        return {"valid": True}

    def _evaluate_policies(self, request: FederationRequest) -> AccessDecision:
        """Evaluate security policies"""
        # Load default policies if not loaded
        if not self._default_policies_loaded:
            self._load_default_policies()

        # Find matching policy
        matching_policies = [
            policy for policy in self._policies.values()
            if policy.matches(request)
        ]

        if not matching_policies:
            # No matching policy - use default
            return AccessDecision(
                allowed=self.config.default_policy == "allow",
                reason=DecisionReason.POLICY_VIOLATION,
                message="No matching policy found"
            )

        # Evaluate matching policies (first allow wins)
        for policy in matching_policies:
            if policy.default_decision:
                return AccessDecision(
                    allowed=True,
                    reason=DecisionReason.VALID_CREDENTIALS,
                    policy_id=policy.id,
                    security_level=policy.required_security_level
                )

        # All policies denied
        return AccessDecision(
            allowed=False,
            reason=DecisionReason.INSUFFICIENT_PERMISSIONS,
            message="No policy allowed access"
        )

    def _check_rate_limit(self, request: FederationRequest) -> bool:
        """Check rate limiting"""
        context = request.security_context
        if not context:
            return True

        key = context.source_did or context.source_instance_id or request.headers.get("X-Forwarded-For", "")

        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        # Clean old entries
        self._rate_limits[key] = deque(
            [ts for ts in self._rate_limits[key] if ts > minute_ago],
            maxlen=self.config.max_requests_per_minute
        )

        # Check limit
        if len(self._rate_limits[key]) >= self.config.max_requests_per_minute:
            return False

        # Add current request
        self._rate_limits[key].append(now)
        return True

    def add_policy(self, policy: SecurityPolicy) -> None:
        """Add a security policy"""
        self._policies[policy.id] = policy
        logger.debug(f"Added security policy: {policy.id}")

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a security policy"""
        if policy_id in self._policies:
            del self._policies[policy_id]
            logger.debug(f"Removed security policy: {policy_id}")
            return True
        return False

    def _load_default_policies(self) -> None:
        """Load default security policies"""
        # Policy for federation members
        member_policy = SecurityPolicy(
            id="federation-member-read",
            name="Federation Member Read Access",
            description="Allow read access for federation members",
            required_security_level=SecurityLevel.MEDIUM,
            required_credentials=[VCType.FEDERATION_MEMBERSHIP],
            allowed_actions=[AccessAction.READ],
            default_decision=True
        )
        self._policies[member_policy.id] = member_policy

        # Policy for admin operations
        admin_policy = SecurityPolicy(
            id="federation-admin",
            name="Federation Admin Access",
            description="Allow admin access for trusted instances",
            required_security_level=SecurityLevel.HIGH,
            required_credentials=[VCType.FEDERATION_MEMBERSHIP],
            allowed_actions=[AccessAction.READ, AccessAction.WRITE, AccessAction.ADMIN],
            default_decision=False
        )
        self._policies[admin_policy.id] = admin_policy

        self._default_policies_loaded = True

    def _log_decision(self, request: FederationRequest, decision: AccessDecision) -> None:
        """Log access decision to audit log"""
        if not self.config.enable_audit_log:
            return

        context = request.security_context
        entry = AuditLogEntry(
            request_id=request.request_id,
            source_instance=context.source_instance_id if context else "",
            source_did=context.source_did if context else "",
            action=request.action.value,
            resource=f"{request.resource_type}:{request.resource_id}",
            decision="allow" if decision.allowed else "deny",
            reason=decision.reason.value,
            policy_id=decision.policy_id,
            security_level=decision.security_level.value
        )

        self._audit_log.append(entry)

        # Trim audit log if needed
        if len(self._audit_log) > 10000:  # Keep last 10k entries
            self._audit_log = self._audit_log[-10000:]

        if not decision.allowed:
            self._stats["denied_requests"] += 1

        logger.debug(
            f"Access decision: {decision.allowed} for {request.action} on {request.resource_type}:{request.resource_id} by {context.source_did if context else 'unknown'}"
        )

    def get_audit_log(
        self,
        since: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[AuditLogEntry]:
        """Get audit log entries"""
        if since:
            return [e for e in self._audit_log if e.timestamp >= since][-limit:]
        return self._audit_log[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get security statistics"""
        total = self._stats["total_requests"]
        allowed = self._stats["allowed_requests"]
        denied = self._stats["denied_requests"]

        return {
            "total_requests": total,
            "allowed_requests": allowed,
            "denied_requests": denied,
            "allow_rate": allowed / total if total > 0 else 0,
            "deny_rate": denied / total if total > 0 else 0,
            "anomalies_detected": self._stats["anomalies_detected"],
            "active_policies": len(self._policies),
            "audit_log_size": len(self._audit_log),
            "rate_limit_entries": len(self._rate_limits)
        }

    def reset_statistics(self) -> None:
        """Reset security statistics"""
        self._stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "denied_requests": 0,
            "anomalies_detected": 0
        }


# ============================================================================
# Factory
# ============================================================================

_zero_trust_manager_instance: Optional[ZeroTrustSecurityManager] = None


def get_zero_trust_manager(config: Optional[SecurityConfig] = None) -> ZeroTrustSecurityManager:
    """Get or create zero-trust manager instance"""
    global _zero_trust_manager_instance
    if _zero_trust_manager_instance is None:
        _zero_trust_manager_instance = ZeroTrustSecurityManager(config)
    return _zero_trust_manager_instance
