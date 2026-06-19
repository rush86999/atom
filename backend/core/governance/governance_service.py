"""
Governance-as-a-Service Module

Based on 2025-2026 research:
- Governance-as-a-Service: Multi-Agent Framework (arXiv:2508.18765v1)

Implements:
- Reusable governance decision service
- API for governance queries
- Centralized policy management
- Multi-tenant governance support
"""

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import threading

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class ServiceAction(Enum):
    """Actions supported by governance service"""
    CHECK_PERMISSION = "check_permission"
    REQUEST_ESCALATION = "request_escalation"
    SUBMIT_POLICY = "submit_policy"
    GET_STATUS = "get_status"
    RECORD_FEEDBACK = "record_feedback"
    BULK_DECISION = "bulk_decision"


class ServiceStatus(Enum):
    """Status of governance service"""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class GovernanceServiceConfig:
    """Configuration for governance service"""
    # Service
    max_concurrent_requests: int = 100
    request_timeout_ms: int = 5000

    # Caching
    enable_caching: bool = True
    cache_ttl_seconds: int = 300
    max_cache_size: int = 10000

    # Rate limiting
    enable_rate_limiting: bool = True
    requests_per_minute: int = 10000
    requests_per_hour: int = 100000

    # High availability
    enable_ha: bool = True
    health_check_interval_ms: int = 30000


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class GovernanceServiceRequest:
    """Request to governance service"""
    request_id: str = ""
    action: ServiceAction = ServiceAction.CHECK_PERMISSION
    tenant_id: str = ""
    user_id: str = ""

    # Request parameters
    agent_id: str = ""
    operation: str = ""
    resource: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    timeout_ms: int = 5000


@dataclass
class GovernanceServiceResponse:
    """Response from governance service"""
    request_id: str = ""
    action: ServiceAction = ServiceAction.CHECK_PERMISSION

    # Decision
    allowed: bool = False
    confidence: float = 0.0
    reasoning: str = ""

    # Conditions
    conditions: List[str] = field(default_factory=list)
    required_approvals: List[str] = field(default_factory=list)

    # Metadata
    service_status: ServiceStatus = ServiceStatus.AVAILABLE
    processing_time_ms: float = 0.0
    cache_hit: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return {
            "request_id": self.request_id,
            "action": self.action.value,
            "allowed": self.allowed,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "conditions": self.conditions,
            "required_approvals": self.required_approvals,
            "service_status": self.service_status.value,
            "processing_time_ms": self.processing_time_ms,
            "cache_hit": self.cache_hit,
            "error": self.error
        }


@dataclass
class ServiceMetrics:
    """Metrics for governance service"""
    total_requests: int = 0
    allowed_requests: int = 0
    denied_requests: int = 0
    conditional_requests: int = 0

    # Performance
    avg_response_time_ms: float = 0.0
    p50_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0

    # Cache
    cache_hits: int = 0
    cache_misses: int = 0

    # Errors
    error_count: int = 0
    last_error_at: Optional[datetime] = None


# ============================================================================
# Governance-as-a-Service
# ============================================================================

class GovernanceAsAService:
    """
    Governance-as-a-Service for reusable governance decisions.

    Provides:
    - Centralized governance decision API
    - Permission checking
    - Escalation requests
    - Policy management
    - Bulk decision support
    """

    def __init__(self, config: Optional[GovernanceServiceConfig] = None):
        self.config = config or GovernanceServiceConfig()

        # Request tracking
        self._active_requests: Dict[str, GovernanceServiceRequest] = {}
        self._request_history: List[GovernanceServiceRequest] = []

        # Response cache
        self._response_cache: Dict[str, GovernanceServiceResponse] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

        # Metrics
        self._metrics = ServiceMetrics()
        self._response_times: List[float] = []

        # Rate limiting
        self._rate_limit_windows: Dict[str, List[datetime]] = defaultdict(list)

        # Thread safety
        self._lock = threading.RLock()

        # Status
        self._status = ServiceStatus.AVAILABLE

        # Integrate with governance manager
        try:
            from core.governance.dynamic_governance import get_governance_manager
            self.governance_manager = get_governance_manager()
        except ImportError:
            self.governance_manager = None
            logger.warning("Governance manager not available")

    def check_permission(
        self,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        action: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None
    ) -> GovernanceServiceResponse:
        """
        Check if an action is allowed.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            agent_id: Agent identifier
            action: Action to check
            resource: Resource being accessed
            context: Additional context

        Returns:
            Governance service response
        """
        start_time = datetime.now()
        request_id = f"req_{uuid.uuid4().hex[:16]}"

        # Create request
        request = GovernanceServiceRequest(
            request_id=request_id,
            action=ServiceAction.CHECK_PERMISSION,
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            operation=action,
            resource=resource,
            context=context or {}
        )

        # Check rate limit
        if self.config.enable_rate_limiting:
            if not self._check_rate_limit(request):
                return GovernanceServiceResponse(
                    request_id=request_id,
                    action=ServiceAction.CHECK_PERMISSION,
                    allowed=False,
                    reasoning="Rate limit exceeded",
                    service_status=self._status,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                    error="Rate limit exceeded"
                )

        # Check cache
        cache_key = self._get_cache_key(request)
        if self.config.enable_caching and cache_key in self._response_cache:
            # Check if cache is still valid
            cache_time = self._cache_timestamps.get(cache_key)
            if cache_time and (datetime.now() - cache_time).total_seconds() < self.config.cache_ttl_seconds:
                cached_response = self._response_cache[cache_key]
                cached_response.cache_hit = True
                self._metrics.cache_hits += 1
                return cached_response

        self._metrics.cache_misses += 1

        # Track request
        self._active_requests[request_id] = request
        self._request_history.append(request)

        # Make decision
        if self.governance_manager:
            decision = self.governance_manager.decide(
                agent_id=agent_id,
                action=action,
                context=request.context
            )

            response = GovernanceServiceResponse(
                request_id=request_id,
                action=ServiceAction.CHECK_PERMISSION,
                allowed=decision.is_allowed(),
                confidence=decision.confidence,
                reasoning=decision.reasoning,
                conditions=decision.conditions,
                required_approvals=decision.required_approvals,
                service_status=self._status,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )
        else:
            # Fallback: allow
            response = GovernanceServiceResponse(
                request_id=request_id,
                action=ServiceAction.CHECK_PERMISSION,
                allowed=True,
                confidence=0.5,
                reasoning="Governance manager not available, defaulting to allow",
                service_status=self._status,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

        # Update metrics
        self._update_metrics(response, start_time)

        # Cache response
        if self.config.enable_caching:
            self._response_cache[cache_key] = response
            self._cache_timestamps[cache_key] = datetime.now()

            # Trim cache if needed
            if len(self._response_cache) > self.config.max_cache_size:
                self._trim_cache()

        # Remove from active
        self._active_requests.pop(request_id, None)

        return response

    def bulk_decision(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[GovernanceServiceResponse]:
        """
        Make bulk governance decisions.

        Args:
            requests: List of request parameters

        Returns:
            List of responses
        """
        responses = []

        for req in requests:
            response = self.check_permission(
                tenant_id=req.get("tenant_id", ""),
                user_id=req.get("user_id", ""),
                agent_id=req.get("agent_id", ""),
                action=req.get("action", ""),
                resource=req.get("resource", ""),
                context=req.get("context", {})
            )
            responses.append(response)

        return responses

    def request_escalation(
        self,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        current_maturity: str,
        performance_score: float,
        context: Optional[Dict[str, Any]] = None
    ) -> GovernanceServiceResponse:
        """
        Request agent maturity escalation.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            agent_id: Agent to escalate
            current_maturity: Current maturity level
            performance_score: Performance score
            context: Additional context

        Returns:
            Governance service response
        """
        start_time = datetime.now()
        request_id = f"esc_{uuid.uuid4().hex[:16]}"

        if not self.governance_manager:
            return GovernanceServiceResponse(
                request_id=request_id,
                action=ServiceAction.REQUEST_ESCALATION,
                allowed=False,
                reasoning="Governance manager not available",
                service_status=self._status
            )

        # Make escalation decision
        decision = self.governance_manager.decide(
            agent_id=agent_id,
            action="escalate",
            context={
                "current_maturity": current_maturity,
                "performance_score": performance_score,
                "decision_type": "escalation",
                **(context or {})
            }
        )

        return GovernanceServiceResponse(
            request_id=request_id,
            action=ServiceAction.REQUEST_ESCALATION,
            allowed=decision.outcome.value in ["allow", "allow_with_conditions"],
            confidence=decision.confidence,
            reasoning=decision.reasoning,
            conditions=decision.conditions,
            service_status=self._status,
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
        )

    def submit_policy(
        self,
        tenant_id: str,
        user_id: str,
        policy_name: str,
        rules: List[Dict[str, Any]],
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """
        Submit a new governance policy.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            policy_name: Name of policy
            rules: Policy rules
            priority: Priority level

        Returns:
            Submission result
        """
        # In production, would persist to database
        policy_id = f"policy_{uuid.uuid4().hex[:16]}"

        return {
            "policy_id": policy_id,
            "name": policy_name,
            "status": "submitted",
            "submitted_at": datetime.now().isoformat()
        }

    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "status": self._status.value,
            "active_requests": len(self._active_requests),
            "cache_size": len(self._response_cache),
            "metrics": {
                "total_requests": self._metrics.total_requests,
                "allowed_rate": self._metrics.allowed_requests / max(self._metrics.total_requests, 1),
                "avg_response_time_ms": self._metrics.avg_response_time_ms,
                "cache_hit_rate": self._metrics.cache_hits / max(self._metrics.cache_hits + self._metrics.cache_misses, 1)
            }
        }

    def _check_rate_limit(self, request: GovernanceServiceRequest) -> bool:
        """Check if request is within rate limits"""
        key = f"{request.tenant_id}:{request.user_id}"
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        # Clean old entries
        self._rate_limit_windows[key] = [
            t for t in self._rate_limit_windows[key]
            if t > minute_ago
        ]

        # Check minute limit
        if len(self._rate_limit_windows[key]) >= self.config.requests_per_minute:
            return False

        # Add current request
        self._rate_limit_windows[key].append(now)

        return True

    def _get_cache_key(self, request: GovernanceServiceRequest) -> str:
        """Generate cache key for request"""
        import hashlib
        key_data = f"{request.action.value}:{request.tenant_id}:{request.agent_id}:{request.operation}:{request.resource}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def _update_metrics(self, response: GovernanceServiceResponse, start_time: datetime) -> None:
        """Update service metrics"""
        with self._lock:
            self._metrics.total_requests += 1

            if response.allowed:
                self._metrics.allowed_requests += 1
            else:
                self._metrics.denied_requests += 1

            if response.conditions:
                self._metrics.conditional_requests += 1

            # Track response time
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            self._response_times.append(response_time)

            # Keep only last 1000 response times
            if len(self._response_times) > 1000:
                self._response_times = self._response_times[-1000:]

            # Update averages
            if self._response_times:
                self._metrics.avg_response_time_ms = sum(self._response_times) / len(self._response_times)

                # Calculate percentiles
                sorted_times = sorted(self._response_times)
                self._metrics.p50_response_time_ms = sorted_times[len(sorted_times) // 2]
                self._metrics.p95_response_time_ms = sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) > 1 else 0
                self._metrics.p99_response_time_ms = sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) > 1 else 0

    def _trim_cache(self) -> None:
        """Trim cache to max size"""
        # Remove oldest entries
        while len(self._response_cache) > self.config.max_cache_size:
            # Find oldest cache entry
            oldest_key = min(self._cache_timestamps.items(), key=lambda x: x[1])[0]
            del self._response_cache[oldest_key]
            del self._cache_timestamps[oldest_key]

    def get_statistics(self) -> ServiceMetrics:
        """Get current service metrics"""
        with self._lock:
            return self._metrics


# ============================================================================
# Factory
# ============================================================================

_governance_service_instance: Optional[GovernanceAsAService] = None


def get_governance_service(config: Optional[GovernanceServiceConfig] = None) -> GovernanceAsAService:
    """Get or create governance service instance"""
    global _governance_service_instance
    if _governance_service_instance is None:
        _governance_service_instance = GovernanceAsAService(config)
    return _governance_service_instance
