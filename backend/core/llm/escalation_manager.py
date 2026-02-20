"""
Escalation Manager for Automatic LLM Tier Escalation

Monitors LLM response quality and failures, automatically escalating queries
to higher cognitive tiers when thresholds are breached. Includes cooldown period
to prevent rapid cycling and database logging for analytics.

Purpose: Maintain response quality while minimizing costs through automatic
tier escalation only when needed.

Key Features:
- Automatic escalation on quality threshold breaches (<80 score)
- Rate limit errors trigger immediate escalation
- 5-minute cooldown prevents rapid tier cycling
- Database logging for analytics and auditing
- Max escalation limit prevents infinite loops

Author: Atom AI Platform
Created: 2026-02-20
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Import CognitiveTier from the tier system
from core.llm.cognitive_tier_system import CognitiveTier


class EscalationReason(Enum):
    """
    Reasons for escalating a query to a higher cognitive tier.

    Each reason has specific trigger conditions and retry limits:
    - LOW_CONFIDENCE: Model confidence score below threshold (0.7)
    - RATE_LIMITED: Provider rate limit error (highest priority escalation)
    - ERROR_RESPONSE: Model returned an error or invalid response
    - QUALITY_THRESHOLD: Response quality score below acceptable level (80)
    - USER_REQUEST: Explicit user request for better quality
    """
    LOW_CONFIDENCE = "low_confidence"
    RATE_LIMITED = "rate_limited"
    ERROR_RESPONSE = "error_response"
    QUALITY_THRESHOLD = "quality_threshold"
    USER_REQUEST = "user_request"


# Escalation thresholds configuration
ESCALATION_THRESHOLDS = {
    EscalationReason.LOW_CONFIDENCE: {
        "confidence": 0.7,
        "max_retries": 2
    },
    EscalationReason.QUALITY_THRESHOLD: {
        "min_quality_score": 80,
        "max_retries": 1
    },
    EscalationReason.RATE_LIMITED: {
        "max_retries": 3
    },
    EscalationReason.ERROR_RESPONSE: {
        "max_retries": 2
    },
    EscalationReason.USER_REQUEST: {
        "max_retries": 1  # User requests honored once
    }
}

# Cooldown period (minutes) - prevents rapid tier cycling
ESCALATION_COOLDOWN = 5

# Maximum escalation limit per request (prevents infinite loops)
MAX_ESCALATION_LIMIT = 2

# Tier order for escalation (micro -> standard -> versatile -> heavy -> complex)
TIER_ORDER = [
    CognitiveTier.MICRO,
    CognitiveTier.STANDARD,
    CognitiveTier.VERSATILE,
    CognitiveTier.HEAVY,
    CognitiveTier.COMPLEX
]


class EscalationManager:
    """
    Manages automatic escalation of LLM queries to higher cognitive tiers.

    Monitors response quality, errors, and rate limits to automatically
    escalate queries to more capable (and expensive) models when needed.

    Key behaviors:
    - Quality-based escalation: Responses scoring <80 trigger escalation
    - Rate limit handling: Immediate escalation on rate limit errors
    - Cooldown enforcement: 5-minute cooldown between escalations per tier
    - Max escalation limit: Maximum 2 tier jumps per request to prevent runaway costs

    Performance targets:
    - Escalation decision: <5ms
    - Cooldown check: <1ms

    Attributes:
        db: Optional database session for persisting escalation logs
        escalation_log: In-memory dict tracking last escalation time per tier {tier_value: datetime}
        request_escalations: In-memory dict tracking escalation count per request {request_id: count}

    Example:
        >>> manager = EscalationManager(db_session)
        >>> should, reason, target = manager.should_escalate(
        ...     current_tier=CognitiveTier.STANDARD,
        ...     response_quality=70,
        ...     error=None,
        ...     rate_limited=False
        ... )
        >>> if should:
        ...     # Re-query with target tier
        ...     pass
    """

    def __init__(self, db_session=None):
        """
        Initialize the escalation manager.

        Args:
            db_session: Optional SQLAlchemy session for database logging.
                       If None, escalations are tracked in-memory only.
        """
        self.db = db_session

        # In-memory escalation tracking
        # {tier_value: datetime} - tracks last escalation time for each tier
        self.escalation_log = {}

        # {request_id: count} - tracks escalation count per request
        self.request_escalations = {}

        logger.info("EscalationManager initialized")

    def should_escalate(
        self,
        current_tier: CognitiveTier,
        response_quality: Optional[float] = None,
        error: Optional[str] = None,
        rate_limited: bool = False,
        confidence: Optional[float] = None,
        request_id: Optional[str] = None
    ) -> Tuple[bool, Optional[EscalationReason], Optional[CognitiveTier]]:
        """
        Determine if a query should be escalated to a higher tier.

        Evaluates escalation conditions in priority order:
        1. Check cooldown period (if on cooldown, don't escalate)
        2. Rate limit errors (highest priority, immediate escalation)
        3. Error responses (automatic escalation)
        4. Low quality score (<80)
        5. Low confidence (<0.7)

        Args:
            current_tier: The cognitive tier that was just used
            response_quality: Optional quality score (0-100)
            error: Optional error message from the response
            rate_limited: Whether the provider returned a rate limit error
            confidence: Optional model confidence score (0-1)
            request_id: Optional request ID for tracking escalation count

        Returns:
            Tuple of (should_escalate, reason, target_tier):
            - should_escalate: True if escalation is recommended
            - reason: The EscalationReason if escalating, None otherwise
            - target_tier: The CognitiveTier to escalate to, None if not escalating

        Example:
            >>> manager = EscalationManager()
            >>> should, reason, target = manager.should_escalate(
            ...     CognitiveTier.STANDARD,
            ...     response_quality=70,
            ...     error=None,
            ...     rate_limited=False
            ... )
            >>> assert should == True
            >>> assert reason == EscalationReason.QUALITY_THRESHOLD
            >>> assert target == CognitiveTier.VERSATILE
        """
        # Check if current tier is already maxed out
        if current_tier == CognitiveTier.COMPLEX:
            logger.debug("Already at COMPLEX tier, no escalation possible")
            return False, None, None

        # Check escalation count limit
        if request_id:
            escalation_count = self.get_escalation_count(request_id)
            if escalation_count >= MAX_ESCALATION_LIMIT:
                logger.warning(
                    f"Request {request_id} has reached max escalation limit "
                    f"({MAX_ESCALATION_LIMIT})"
                )
                return False, None, None

        # Check cooldown first (prevents rapid cycling)
        if self._is_on_cooldown(current_tier):
            logger.debug(f"Tier {current_tier.value} is on cooldown, skipping escalation")
            return False, None, None

        # Priority 1: Rate limit errors (immediate escalation)
        if rate_limited:
            return self._escalate_for_reason(current_tier, EscalationReason.RATE_LIMITED)

        # Priority 2: Error responses
        if error:
            return self._escalate_for_reason(current_tier, EscalationReason.ERROR_RESPONSE)

        # Priority 3: Low quality threshold
        if response_quality is not None:
            threshold = ESCALATION_THRESHOLDS[EscalationReason.QUALITY_THRESHOLD]["min_quality_score"]
            if response_quality < threshold:
                return self._escalate_for_reason(
                    current_tier,
                    EscalationReason.QUALITY_THRESHOLD,
                    trigger_value=response_quality
                )

        # Priority 4: Low confidence
        if confidence is not None:
            threshold = ESCALATION_THRESHOLDS[EscalationReason.LOW_CONFIDENCE]["confidence"]
            if confidence < threshold:
                return self._escalate_for_reason(
                    current_tier,
                    EscalationReason.LOW_CONFIDENCE,
                    trigger_value=confidence
                )

        # No escalation needed
        return False, None, None

    def _escalate_for_reason(
        self,
        current_tier: CognitiveTier,
        reason: EscalationReason,
        trigger_value: Optional[float] = None
    ) -> Tuple[bool, EscalationReason, Optional[CognitiveTier]]:
        """
        Calculate target tier and record escalation.

        Finds the next tier in the escalation order, records the escalation
        with timestamp, and sets cooldown period.

        Args:
            current_tier: The current cognitive tier
            reason: The reason for escalation
            trigger_value: Optional value that triggered escalation (quality/confidence)

        Returns:
            Tuple of (should_escalate, reason, target_tier)
        """
        # Find current tier index
        try:
            current_index = TIER_ORDER.index(current_tier)
        except ValueError:
            logger.error(f"Unknown tier: {current_tier}")
            return False, reason, None

        # Calculate target tier (next in order)
        target_index = current_index + 1
        if target_index >= len(TIER_ORDER):
            # Already at max tier
            logger.warning(f"Cannot escalate beyond {current_tier.value}")
            return False, reason, None

        target_tier = TIER_ORDER[target_index]

        # Record escalation
        self._record_escalation(
            from_tier=current_tier,
            to_tier=target_tier,
            reason=reason,
            trigger_value=trigger_value
        )

        # Set cooldown timestamp
        self.escalation_log[current_tier.value] = datetime.utcnow()

        logger.info(
            f"Escalated from {current_tier.value} to {target_tier.value} "
            f"reason={reason.value} trigger={trigger_value}"
        )

        return True, reason, target_tier

    def _is_on_cooldown(self, tier: CognitiveTier) -> bool:
        """
        Check if a tier is currently on cooldown.

        A tier is on cooldown if an escalation occurred within the last
        ESCALATION_COOLDOWN minutes. This prevents rapid cycling between tiers.

        Args:
            tier: The cognitive tier to check

        Returns:
            True if the tier is on cooldown, False otherwise

        Example:
            >>> manager = EscalationManager()
            >>> # Assume escalation just happened
            >>> manager.escalation_log["standard"] = datetime.utcnow()
            >>> manager._is_on_cooldown(CognitiveTier.STANDARD)
            True
        """
        if tier.value not in self.escalation_log:
            return False

        last_escalation = self.escalation_log[tier.value]
        cooldown_expiry = last_escalation + timedelta(minutes=ESCALATION_COOLDOWN)

        return datetime.utcnow() < cooldown_expiry

    def _record_escalation(
        self,
        from_tier: CognitiveTier,
        to_tier: CognitiveTier,
        reason: EscalationReason,
        trigger_value: Optional[float] = None,
        request_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """
        Record an escalation event.

        Escalations are tracked in-memory for performance and optionally
        persisted to the database for analytics and auditing.

        Args:
            from_tier: The tier being escalated from
            to_tier: The tier being escalated to
            reason: The reason for escalation
            trigger_value: Optional value that triggered escalation
            request_id: Optional request ID for tracking
            provider_id: Optional provider that was being used
            model: Optional model that was being used
            error_message: Optional error message if escalation due to error
        """
        # Track escalation count per request
        if request_id:
            self.request_escalations[request_id] = self.request_escalations.get(request_id, 0) + 1

        # Persist to database if session available
        if self.db:
            try:
                from core.models import EscalationLog
                import uuid

                escalation_record = EscalationLog(
                    id=str(uuid.uuid4()),
                    workspace_id="default",  # TODO: Get from context
                    request_id=request_id or "unknown",
                    from_tier=from_tier.value,
                    to_tier=to_tier.value,
                    reason=reason.value,
                    trigger_value=trigger_value,
                    provider_id=provider_id,
                    model=model,
                    error_message=error_message
                )

                self.db.add(escalation_record)
                self.db.commit()

                logger.debug(f"Escalation logged to database: {from_tier.value} -> {to_tier.value}")

            except Exception as e:
                logger.error(f"Failed to log escalation to database: {e}")
                # Don't fail escalation if DB logging fails
                try:
                    self.db.rollback()
                except Exception:
                    pass

    def get_escalation_count(self, request_id: str) -> int:
        """
        Get the number of escalations for a request.

        Tracks escalations per request to prevent infinite escalation loops.

        Args:
            request_id: The request ID to check

        Returns:
            Number of escalations for this request

        Example:
            >>> manager = EscalationManager()
            >>> manager.request_escalations["req-123"] = 2
            >>> manager.get_escalation_count("req-123")
            2
        """
        return self.request_escalations.get(request_id, 0)

    def reset_cooldown(self, tier: CognitiveTier):
        """
        Manually reset cooldown for a tier.

        Useful for testing or manual intervention scenarios.

        Args:
            tier: The cognitive tier to reset cooldown for
        """
        if tier.value in self.escalation_log:
            del self.escalation_log[tier.value]
            logger.info(f"Cooldown reset for tier {tier.value}")

    def get_cooldown_remaining(self, tier: CognitiveTier) -> float:
        """
        Get remaining cooldown time in seconds for a tier.

        Args:
            tier: The cognitive tier to check

        Returns:
            Remaining cooldown seconds (0 if not on cooldown)
        """
        if tier.value not in self.escalation_log:
            return 0.0

        last_escalation = self.escalation_log[tier.value]
        cooldown_expiry = last_escalation + timedelta(minutes=ESCALATION_COOLDOWN)
        remaining = (cooldown_expiry - datetime.utcnow()).total_seconds()

        return max(0.0, remaining)
