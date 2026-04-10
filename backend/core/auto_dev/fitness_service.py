"""
Auto-Dev Fitness Service

Evaluates the performance (fitness) of mutated agent workflows via
multi-stage evaluation:

1. Immediate Proxy Signals — syntax pass, execution success, latency
2. Deferred Async Signals — downstream webhook events (conversions, errors)

Architecturally aligned with the SaaS fitness_service.py but operates
independently against the upstream database.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.auto_dev.models import WorkflowVariant

logger = logging.getLogger(__name__)


class FitnessService:
    """
    Multi-stage fitness evaluation for workflow variants.

    Stage 1 - evaluate_initial_proxy(): Immediate feedback from sandbox execution.
    Stage 2 - evaluate_delayed_webhook(): Async signals from downstream integrations.
    """

    def __init__(self, db: Session):
        self.db = db

    def evaluate_initial_proxy(
        self, variant_id: str, tenant_id: str, proxy_signals: dict[str, Any]
    ) -> float:
        """
        Record immediate proxy signals and calculate baseline fitness.

        Proxy signals:
        - execution_success (bool): Ran without runtime crash
        - syntax_error (bool): Code had syntax errors
        - execution_latency_ms (float): Execution time
        - user_approved_proposal (bool): HITL approval from governance
        """
        variant = (
            self.db.query(WorkflowVariant)
            .filter(
                WorkflowVariant.id == variant_id,
                WorkflowVariant.tenant_id == tenant_id,
            )
            .first()
        )

        if not variant:
            logger.warning(
                f"WorkflowVariant {variant_id} not found for tenant {tenant_id}."
            )
            return 0.0

        score = 0.0

        # Penalize syntax errors
        if proxy_signals.get("syntax_error", False):
            score -= 1.0
        else:
            score += 0.2  # Survived syntax check

        # Reward successful execution
        if proxy_signals.get("execution_success", False):
            score += 0.3

        # HITL governance signal
        if proxy_signals.get("user_approved_proposal") is True:
            score += 0.5
        elif proxy_signals.get("user_approved_proposal") is False:
            score -= 0.5

        # Clamp to [0.0, 1.0]
        final_score = max(0.0, min(1.0, score))

        # Update variant
        signals = variant.fitness_signals or {}
        signals["proxy"] = proxy_signals
        variant.fitness_signals = signals
        variant.fitness_score = final_score

        if proxy_signals.get("expects_delayed_eval", True):
            variant.evaluation_status = "pending"
        else:
            variant.evaluation_status = "evaluated"

        variant.last_evaluated_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(f"Variant {variant_id} proxy fitness: {final_score}")
        return final_score

    def evaluate_delayed_webhook(
        self, variant_id: str, tenant_id: str, external_signals: dict[str, Any]
    ) -> float:
        """
        Process downstream webhook signals and adjust fitness score.

        External signals:
        - invoice_created, crm_conversion, conversion_success → positive
        - email_bounce, error_signal → negative
        - conversion_value (float) → scaled positive adjustment
        """
        variant = (
            self.db.query(WorkflowVariant)
            .filter(
                WorkflowVariant.id == variant_id,
                WorkflowVariant.tenant_id == tenant_id,
            )
            .first()
        )

        if not variant:
            logger.warning(
                f"WorkflowVariant {variant_id} not found for tenant {tenant_id}."
            )
            return 0.0

        current_score = variant.fitness_score or 0.0
        signals = variant.fitness_signals or {}
        signals["external"] = external_signals

        adjustment = 0.0

        # Positive signals
        if external_signals.get("invoice_created"):
            adjustment += 0.4
        if external_signals.get("crm_conversion"):
            adjustment += 0.5
        if external_signals.get("conversion_success"):
            adjustment += 0.6

        # Negative signals
        if external_signals.get("email_bounce"):
            adjustment -= 0.3
        if external_signals.get("error_signal"):
            adjustment -= 0.5

        # Value-based scaling
        if "conversion_value" in external_signals:
            val = external_signals["conversion_value"]
            adjustment += min(0.5, val / 1000.0)

        final_score = max(0.0, min(1.0, current_score + adjustment))

        variant.fitness_signals = signals
        variant.fitness_score = final_score
        variant.evaluation_status = "evaluated"
        variant.last_evaluated_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(f"Variant {variant_id} delayed fitness updated: {final_score}")
        return final_score

    def get_top_variants(
        self, tenant_id: str, limit: int = 5
    ) -> list[WorkflowVariant]:
        """Retrieve highest-fitness variants for crossover/mutation operations."""
        return (
            self.db.query(WorkflowVariant)
            .filter(
                WorkflowVariant.tenant_id == tenant_id,
                WorkflowVariant.fitness_score.isnot(None),
                WorkflowVariant.fitness_score > 0.0,
            )
            .order_by(WorkflowVariant.fitness_score.desc())
            .limit(limit)
            .all()
        )
