"""
Preference Data Collection for Learning-Based Router

Based on 2025-2026 research:
- "RouteLLM: Learning to Route" (arXiv:2406.18665)
- "State of AI 2025: 100T Token Study" (openrouter.ai)

Implements:
- Preference data collection from router decisions
- User feedback tracking on routing quality
- Training dataset generation for RouteLLM
- A/B testing support for router evaluation
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from core.database import get_db_session

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class FeedbackType(Enum):
    """Types of user feedback on routing decisions"""
    EXPLICIT = "explicit"  # User explicitly rated the routing
    IMPLICIT = "implicit"  # Feedback inferred from user behavior
    A_B_TEST = "ab_test"  # Feedback from A/B test comparison


class FeedbackSource(Enum):
    """Sources of routing feedback"""
    USER_RATING = "user_rating"  # Direct user rating (1-5 stars)
    QUALITY_METRICS = "quality_metrics"  # Automated quality assessment
    COST_SAVINGS = "cost_savings"  # Cost-based feedback
    LATENCY = "latency"  # Response time feedback
    RETRY = "retry"  # User requested different model


class RoutingOutcome(Enum):
    """Possible outcomes of a routing decision"""
    SUCCESS = "success"  # User accepted the routing
    REJECTED = "rejected"  # User requested different model
    MODIFIED = "modified"  # User modified and used response
    ERROR = "error"  # Routing resulted in error
    TIMEOUT = "timeout"  # Request timed out


@dataclass
class FeedbackConfig:
    """Configuration for feedback collection"""
    # Collection triggers
    collect_on_success: bool = True
    collect_on_rejection: bool = True
    collect_on_error: bool = True
    collect_on_retry: bool = True

    # A/B testing
    enable_ab_testing: bool = True
    ab_test_sample_rate: float = 0.1  # 10% of requests go to learning router

    # Quality thresholds
    min_quality_score: float = 0.3  # Minimum quality to include in training
    min_confidence_score: float = 0.5  # Minimum router confidence

    # Data retention
    max_sample_age_days: int = 90  # Days to keep preference data
    min_samples_for_training: int = 1000  # Minimum samples before training

    # Privacy
    anonymize_data: bool = True  # Remove PII from training data
    include_prompts: bool = False  # Whether to include actual prompts


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class RoutingDecision:
    """A routing decision made by the router"""
    decision_id: str = field(default="")
    timestamp: datetime = field(default_factory=datetime.now)
    workspace_id: str = ""
    tenant_id: str = ""

    # Query characteristics
    estimated_tokens: int = 0
    task_type: str = ""
    prompt_hash: str = ""
    prompt_prefix: str = ""  # First 1k tokens for caching

    # Router decision
    chosen_model: str = ""
    chosen_provider: str = ""
    chosen_tier: str = ""
    router_type: str = "rule_based"  # rule_based or learning_based
    confidence: float = 1.0
    alternatives: List[Dict[str, Any]] = field(default_factory=list)

    # Context
    session_id: str = ""
    user_id: str = ""

    def __post_init__(self):
        if not self.decision_id:
            self.decision_id = hashlib.md5(
                f"{self.timestamp}:{self.workspace_id}:{self.prompt_hash}".encode(), usedforsecurity=False
            ).hexdigest()[:16]


@dataclass
class RoutingFeedback:
    """User feedback on a routing decision"""
    feedback_id: str = field(default="")
    decision_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # Feedback content
    feedback_type: FeedbackType = FeedbackType.IMPLICIT
    feedback_source: FeedbackSource = FeedbackSource.USER_RATING
    outcome: RoutingOutcome = RoutingOutcome.SUCCESS

    # Quality metrics
    quality_score: float = 0.5  # 0-1, user satisfaction
    accuracy_score: float = 0.5  # 0-1, response quality
    latency_ms: int = 0
    cost_usd: float = 0.0

    # User preference (if explicitly chosen)
    preferred_model: Optional[str] = None
    preferred_provider: Optional[str] = None
    rejected_reason: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.feedback_id:
            self.feedback_id = hashlib.md5(
                f"{self.decision_id}:{self.timestamp}".encode(), usedforsecurity=False
            ).hexdigest()[:16]


@dataclass
class TrainingExample:
    """A single training example for RouteLLM"""
    example_id: str = field(default="")
    created_at: datetime = field(default_factory=datetime.now)

    # Input features (query characteristics)
    estimated_tokens: int = 0
    task_type: str = ""
    prompt_features: Dict[str, float] = field(default_factory=dict)

    # Router decision
    chosen_model: str = ""
    chosen_provider: str = ""
    chosen_tier: str = ""
    router_confidence: float = 1.0

    # Outcome (target for training)
    user_satisfaction: float = 0.5  # 0-1
    was_successful: bool = True
    quality_score: float = 0.5

    # Alternative models that could have been chosen
    available_models: List[str] = field(default_factory=list)

    # Weights for training (preference weighting)
    weight: float = 1.0

    def __post_init__(self):
        if not self.example_id:
            self.example_id = hashlib.md5(
                f"{self.created_at}:{self.estimated_tokens}:{self.task_type}".encode(), usedforsecurity=False
            ).hexdigest()[:16]


# ============================================================================
# Preference Data Collector
# ============================================================================

class PreferenceDataCollector:
    """
    Collects preference data for learning-based router training.

    Features:
    - Track routing decisions and outcomes
    - Collect user feedback (explicit and implicit)
    - Generate training examples
    - Support A/B testing
    """

    def __init__(self, config: Optional[FeedbackConfig] = None):
        self.config = config or FeedbackConfig()

        # In-memory storage (persist to DB in production)
        self.decisions: Dict[str, RoutingDecision] = {}
        self.feedback_records: Dict[str, RoutingFeedback] = {}

        # A/B test state
        self.ab_test_group: Dict[str, str] = {}  # workspace -> group (learning/control)
        self.ab_test_decisions: Dict[str, str] = {}  # decision_id -> group

    def record_routing_decision(
        self,
        workspace_id: str,
        tenant_id: str,
        estimated_tokens: int,
        task_type: str,
        prompt: str,
        chosen_model: str,
        chosen_provider: str,
        chosen_tier: str,
        router_type: str = "rule_based",
        confidence: float = 1.0,
        alternatives: Optional[List[Dict[str, Any]]] = None,
        session_id: str = "",
        user_id: str = ""
    ) -> str:
        """
        Record a routing decision made by the router.

        Args:
            workspace_id: Workspace identifier
            tenant_id: Tenant identifier
            estimated_tokens: Estimated token count
            task_type: Type of task
            prompt: Full prompt text
            chosen_model: Model that was chosen
            chosen_provider: Provider that was chosen
            chosen_tier: Tier that was chosen
            router_type: Type of router (rule_based or learning_based)
            confidence: Router confidence score
            alternatives: Alternative models that could have been chosen
            session_id: Session identifier
            user_id: User identifier

        Returns:
            Decision ID for feedback tracking
        """
        # Generate prompt hash and prefix
        prompt_hash = hashlib.md5(prompt.encode(), usedforsecurity=False).hexdigest()
        prompt_prefix = prompt[:1024]  # First 1k characters

        decision = RoutingDecision(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            estimated_tokens=estimated_tokens,
            task_type=task_type,
            prompt_hash=prompt_hash,
            prompt_prefix=prompt_prefix,
            chosen_model=chosen_model,
            chosen_provider=chosen_provider,
            chosen_tier=chosen_tier,
            router_type=router_type,
            confidence=confidence,
            alternatives=alternatives or [],
            session_id=session_id,
            user_id=user_id
        )

        self.decisions[decision.decision_id] = decision

        logger.debug(
            f"Recorded routing decision: {decision.decision_id[:8]}, "
            f"model={chosen_model}, tier={chosen_tier}, "
            f"tokens={estimated_tokens}"
        )

        return decision.decision_id

    def record_feedback(
        self,
        decision_id: str,
        outcome: RoutingOutcome,
        quality_score: float = 0.5,
        latency_ms: int = 0,
        cost_usd: float = 0.0,
        preferred_model: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        rejected_reason: Optional[str] = None,
        feedback_type: FeedbackType = FeedbackType.IMPLICIT,
        feedback_source: FeedbackSource = FeedbackSource.USER_RATING
    ) -> str:
        """
        Record user feedback on a routing decision.

        Args:
            decision_id: ID of the routing decision
            outcome: What happened with the routing
            quality_score: User satisfaction (0-1)
            latency_ms: Response latency in milliseconds
            cost_usd: Cost of the request in USD
            preferred_model: Model user would have preferred
            preferred_provider: Provider user would have preferred
            rejected_reason: Why the routing was rejected
            feedback_type: Type of feedback
            feedback_source: Source of feedback

        Returns:
            Feedback ID
        """
        # Verify decision exists
        if decision_id not in self.decisions:
            logger.warning(f"Decision {decision_id} not found, cannot record feedback")
            return ""

        feedback = RoutingFeedback(
            decision_id=decision_id,
            outcome=outcome,
            quality_score=quality_score,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            preferred_model=preferred_model,
            preferred_provider=preferred_provider,
            rejected_reason=rejected_reason,
            feedback_type=feedback_type,
            feedback_source=feedback_source
        )

        self.feedback_records[feedback.feedback_id] = feedback

        logger.debug(
            f"Recorded feedback: {feedback.feedback_id[:8]}, "
            f"outcome={outcome.value}, quality={quality_score:.2f}"
        )

        return feedback.feedback_id

    def assign_ab_test_group(self, workspace_id: str) -> str:
        """
        Assign workspace to A/B test group.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Group assignment ("learning" or "control")
        """
        if workspace_id not in self.ab_test_group:
            # Hash-based deterministic assignment
            hash_val = int(hashlib.md5(workspace_id.encode(), usedforsecurity=False).hexdigest()[:8], 16)
            self.ab_test_group[workspace_id] = "learning" if hash_val % 2 else "control"

        return self.ab_test_group[workspace_id]

    def should_use_learning_router(self, workspace_id: str) -> bool:
        """
        Determine if learning router should be used for this request.

        Args:
            workspace_id: Workspace identifier

        Returns:
            True if learning router should be used
        """
        if not self.config.enable_ab_testing:
            return False

        group = self.assign_ab_test_group(workspace_id)
        return group == "learning"

    def generate_training_dataset(
        self,
        workspace_id: str,
        min_quality: float = 0.3,
        max_age_days: int = 90
    ) -> List[TrainingExample]:
        """
        Generate training dataset from collected preferences.

        Args:
            workspace_id: Workspace identifier
            min_quality: Minimum quality score to include
            max_age_days: Maximum age of examples to include

        Returns:
            List of training examples
        """
        examples = []
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        # Process each decision with feedback
        for decision_id, decision in self.decisions.items():
            if decision.workspace_id != workspace_id:
                continue

            if decision.timestamp < cutoff_date:
                continue

            # Find feedback for this decision
            feedback = None
            for fb in self.feedback_records.values():
                if fb.decision_id == decision_id:
                    feedback = fb
                    break

            if not feedback:
                # No feedback yet, skip or use default
                continue

            # Apply quality filter
            if feedback.quality_score < min_quality:
                continue

            # Extract prompt features
            prompt_features = self._extract_prompt_features(decision)

            # Calculate weight based on feedback type
            weight = self._calculate_example_weight(feedback)

            example = TrainingExample(
                estimated_tokens=decision.estimated_tokens,
                task_type=decision.task_type,
                prompt_features=prompt_features,
                chosen_model=decision.chosen_model,
                chosen_provider=decision.chosen_provider,
                chosen_tier=decision.chosen_tier,
                router_confidence=decision.confidence,
                user_satisfaction=feedback.quality_score,
                was_successful=(feedback.outcome == RoutingOutcome.SUCCESS),
                quality_score=feedback.quality_score,
                available_models=[alt.get("model", "") for alt in decision.alternatives],
                weight=weight
            )

            examples.append(example)

        logger.info(f"Generated {len(examples)} training examples for workspace {workspace_id}")
        return examples

    def _extract_prompt_features(self, decision: RoutingDecision) -> Dict[str, float]:
        """Extract numerical features from prompt for training"""
        features = {}

        # Basic features
        features["log_tokens"] = max(0, (decision.estimated_tokens + 1).bit_length() - 1)
        features["token_bucket"] = self._get_token_bucket(decision.estimated_tokens)

        # Task type encoding
        task_types = ["code", "analysis", "reasoning", "chat", "general"]
        for task in task_types:
            features[f"task_{task}"] = 1.0 if decision.task_type == task else 0.0

        # Prompt complexity (simple heuristic)
        prompt_lower = decision.prompt_prefix.lower()
        features["has_code"] = 1.0 if "```" in prompt_lower else 0.0
        features["has_numbers"] = 1.0 if any(c.isdigit() for c in prompt_lower) else 0.0
        features["avg_word_length"] = len(decision.prompt_prefix) / max(decision.prompt_prefix.count(" ") + 1, 1)

        return features

    def _get_token_bucket(self, tokens: int) -> int:
        """Get token bucket for training"""
        if tokens < 100:
            return 0
        elif tokens < 500:
            return 1
        elif tokens < 2000:
            return 2
        elif tokens < 5000:
            return 3
        else:
            return 4

    def _calculate_example_weight(self, feedback: RoutingFeedback) -> float:
        """Calculate weight for training example based on feedback quality"""
        weight = 1.0

        # Explicit feedback gets higher weight
        if feedback.feedback_type == FeedbackType.EXPLICIT:
            weight *= 2.0

        # Rejections are informative for learning
        if feedback.outcome == RoutingOutcome.REJECTED:
            weight *= 1.5

        # High quality (good or bad) is more informative
        if feedback.quality_score >= 0.8 or feedback.quality_score <= 0.2:
            weight *= 1.3

        return weight

    def get_collection_stats(self, workspace_id: str) -> Dict[str, Any]:
        """Get statistics about collected preference data"""
        workspace_decisions = [
            d for d in self.decisions.values()
            if d.workspace_id == workspace_id
        ]
        workspace_feedback = [
            f for f in self.feedback_records.values()
            if self.decisions.get(f.decision_id, {}).get("workspace_id") == workspace_id
        ]

        # Calculate stats
        total_decisions = len(workspace_decisions)
        total_feedback = len(workspace_feedback)

        if total_feedback > 0:
            outcomes = [f.outcome for f in workspace_feedback]
            success_rate = outcomes.count(RoutingOutcome.SUCCESS) / total_feedback
            avg_quality = sum(f.quality_score for f in workspace_feedback) / total_feedback

            # Preferred models
            preferred_models = [f.preferred_model for f in workspace_feedback if f.preferred_model]
        else:
            success_rate = 0.0
            avg_quality = 0.0
            preferred_models = []

        return {
            "workspace_id": workspace_id,
            "total_decisions": total_decisions,
            "total_feedback": total_feedback,
            "feedback_coverage": total_feedback / total_decisions if total_decisions > 0 else 0,
            "success_rate": round(success_rate, 3),
            "avg_quality_score": round(avg_quality, 3),
            "preferred_models": preferred_models,
            "ready_for_training": total_feedback >= self.config.min_samples_for_training
        }


# ============================================================================
# Factory
# ============================================================================

def get_preference_collector(config: Optional[FeedbackConfig] = None) -> PreferenceDataCollector:
    """Factory function to get preference collector instance"""
    return PreferenceDataCollector(config)
