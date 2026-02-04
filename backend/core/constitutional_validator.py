"""
Constitutional Validator Service

Validates agent actions against constitutional rules and constraints.
Provides compliance scoring and violation detection for agent graduation.

This is a foundational framework for constitutional AI compliance:
- Mock rules initially (extensible for real Knowledge Graph integration)
- Domain-specific validation (tax laws, HIPAA, financial regulations)
- Action safety checks
- Compliance scoring with detailed violation tracking
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.models import Episode, EpisodeSegment

logger = logging.getLogger(__name__)


class ViolationSeverity:
    """Severity levels for constitutional violations."""
    CRITICAL = "critical"  # Security, legal compliance, safety
    HIGH = "high"  # Major policy violations
    MEDIUM = "medium"  # Moderate policy issues
    LOW = "low"  # Minor deviations, best practices


class ConstitutionalValidator:
    """
    Validates agent actions against constitutional rules.

    Provides:
    - Action validation against rules
    - Domain-specific compliance checks
    - Compliance scoring
    - Detailed violation tracking
    """

    # Mock constitutional rules (extensible for real Knowledge Graph)
    CONSTITUTIONAL_RULES = {
        # Safety rules
        "safety_no_harm": {
            "category": "safety",
            "description": "Agent must not take actions that could cause harm",
            "severity": ViolationSeverity.CRITICAL,
            "domains": ["all"]
        },
        "safety_no_pii_exposure": {
            "category": "safety",
            "description": "Agent must not expose personally identifiable information",
            "severity": ViolationSeverity.HIGH,
            "domains": ["all"]
        },

        # Financial rules
        "financial_no_unauthorized_payments": {
            "category": "financial",
            "description": "Agent must not make payments without explicit approval",
            "severity": ViolationSeverity.CRITICAL,
            "domains": ["financial", "payments"]
        },
        "financial_tax_compliance": {
            "category": "financial",
            "description": "Agent must comply with tax calculation regulations",
            "severity": ViolationSeverity.HIGH,
            "domains": ["financial", "tax"]
        },

        # Privacy rules
        "privacy_hipaa_compliance": {
            "category": "privacy",
            "description": "Agent must comply with HIPAA for healthcare data",
            "severity": ViolationSeverity.CRITICAL,
            "domains": ["healthcare", "medical"]
        },
        "privacy_data_minimization": {
            "category": "privacy",
            "description": "Agent must collect only necessary data",
            "severity": ViolationSeverity.MEDIUM,
            "domains": ["all"]
        },

        # Transparency rules
        "transparency_no_deception": {
            "category": "transparency",
            "description": "Agent must not deceive users or stakeholders",
            "severity": ViolationSeverity.HIGH,
            "domains": ["all"]
        },
        "transparency_explainable": {
            "category": "transparency",
            "description": "Agent actions must be explainable and auditable",
            "severity": ViolationSeverity.MEDIUM,
            "domains": ["all"]
        },

        # Governance rules
        "governance_human_oversight": {
            "category": "governance",
            "description": "High-risk actions require human oversight",
            "severity": ViolationSeverity.HIGH,
            "domains": ["all"]
        },
        "governance_audit_trail": {
            "category": "governance",
            "description": "All actions must be logged for audit",
            "severity": ViolationSeverity.MEDIUM,
            "domains": ["all"]
        },
    }

    def __init__(self, db: Session):
        self.db = db

    def validate_actions(
        self,
        episode_segments: List[EpisodeSegment],
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate episode segments against constitutional rules.

        Args:
            episode_segments: List of episode segments to validate
            domain: Optional domain for domain-specific rules

        Returns:
            {
                "compliant": bool,
                "score": float (0.0 to 1.0),
                "violations": List[Dict],
                "total_actions": int,
                "checked_actions": int
            }
        """
        violations = []
        total_actions = 0
        checked_actions = 0

        # Handle None or non-iterable episode_segments
        if not episode_segments:
            return {
                "compliant": True,
                "score": 1.0,
                "violations": violations,
                "total_actions": 0,
                "checked_actions": 0
            }

        for segment in episode_segments:
            # Extract action data from segment
            action_data = self._extract_action_data(segment)
            if not action_data:
                continue

            total_actions += 1

            # Check each applicable constitutional rule
            for rule_id, rule in self.CONSTITUTIONAL_RULES.items():
                # Skip if domain-specific and domain doesn't match
                if domain and rule["domains"] != ["all"] and domain not in rule["domains"]:
                    continue

                # Validate action against rule
                violation = self._check_rule_violation(
                    action_data, rule_id, rule
                )
                if violation:
                    violations.append(violation)

            checked_actions += 1

        # Calculate compliance score
        score = self._calculate_compliance_score(violations, total_actions)

        return {
            "compliant": len([v for v in violations if v["severity"] == ViolationSeverity.CRITICAL]) == 0,
            "score": score,
            "violations": violations,
            "total_actions": total_actions,
            "checked_actions": checked_actions
        }

    def check_compliance(
        self,
        domain: str,
        actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Domain-specific compliance check for a list of actions.

        Args:
            domain: Domain to check (financial, healthcare, etc.)
            actions: List of action dictionaries

        Returns:
            {
                "compliant": bool,
                "score": float,
                "violations": List[Dict],
                "domain": str
            }
        """
        violations = []

        for action in actions:
            for rule_id, rule in self.CONSTITUTIONAL_RULES.items():
                # Only check rules for this domain or all domains
                if rule["domains"] != ["all"] and domain not in rule["domains"]:
                    continue

                violation = self._check_rule_violation(action, rule_id, rule)
                if violation:
                    violations.append(violation)

        score = self._calculate_compliance_score(violations, len(actions))

        return {
            "compliant": len([v for v in violations if v["severity"] == ViolationSeverity.CRITICAL]) == 0,
            "score": score,
            "violations": violations,
            "domain": domain
        }

    def calculate_score(self, violations: List[Dict[str, Any]]) -> float:
        """
        Calculate overall compliance score from violations.

        Score formula: 1.0 - (weighted_violation_count / total_possible_weight)

        Args:
            violations: List of violation dictionaries

        Returns:
            Compliance score (0.0 to 1.0)
        """
        if not violations:
            return 1.0

        # Weight violations by severity
        severity_weights = {
            ViolationSeverity.CRITICAL: 10.0,
            ViolationSeverity.HIGH: 5.0,
            ViolationSeverity.MEDIUM: 2.0,
            ViolationSeverity.LOW: 0.5
        }

        total_weight = sum(severity_weights.get(v["severity"], 1.0) for v in violations)

        # Normalize score (assuming 10 critical violations = 0.0 score)
        max_weight = 100.0
        score = max(0.0, 1.0 - (total_weight / max_weight))

        return score

    def _extract_action_data(self, segment: EpisodeSegment) -> Optional[Dict[str, Any]]:
        """
        Extract action data from episode segment.

        Args:
            segment: EpisodeSegment to parse

        Returns:
            Action dictionary or None
        """
        try:
            # Segment content is stored as JSON
            import json
            content = json.loads(segment.content) if isinstance(segment.content, str) else segment.content

            return {
                "action_type": segment.segment_type,
                "content": content,
                "timestamp": segment.timestamp.isoformat() if segment.timestamp else None,
                "metadata": segment.metadata or {}
            }
        except Exception as e:
            logger.warning(f"Failed to extract action data from segment {segment.id}: {e}")
            return None

    def _check_rule_violation(
        self,
        action: Dict[str, Any],
        rule_id: str,
        rule: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Check if an action violates a specific constitutional rule.

        This is a mock implementation. In production, this would:
        - Query the Knowledge Graph for relevant rules
        - Use pattern matching to detect violations
        - Integrate with domain-specific compliance engines

        Args:
            action: Action dictionary
            rule_id: Rule identifier
            rule: Rule configuration

        Returns:
            Violation dictionary or None
        """
        # Mock violation detection based on action patterns
        action_type = action.get("action_type", "")
        content = action.get("content", {})

        # Mock: Detect potential PII exposure
        if rule_id == "safety_no_pii_exposure":
            if isinstance(content, dict):
                text = str(content)
                # Simple pattern matching for PII (mock)
                if any(pattern in text.lower() for pattern in ["ssn", "social_security", "credit_card"]):
                    return {
                        "rule_id": rule_id,
                        "rule_description": rule["description"],
                        "severity": rule["severity"],
                        "action_type": action_type,
                        "detected_at": datetime.now().isoformat(),
                        "details": "Potential PII exposure detected"
                    }

        # Mock: Detect unauthorized payments
        if rule_id == "financial_no_unauthorized_payments":
            if action_type == "payment" and not content.get("approval_required"):
                return {
                    "rule_id": rule_id,
                    "rule_description": rule["description"],
                    "severity": rule["severity"],
                    "action_type": action_type,
                    "detected_at": datetime.now().isoformat(),
                    "details": "Payment without explicit approval"
                }

        # Mock: Detect missing audit trail
        if rule_id == "governance_audit_trail":
            metadata = action.get("metadata", {})
            if not metadata.get("logged"):
                return {
                    "rule_id": rule_id,
                    "rule_description": rule["description"],
                    "severity": rule["severity"],
                    "action_type": action_type,
                    "detected_at": datetime.now().isoformat(),
                    "details": "Action not logged for audit"
                }

        # No violation detected
        return None

    def _calculate_compliance_score(
        self,
        violations: List[Dict[str, Any]],
        total_actions: int
    ) -> float:
        """
        Calculate compliance score from violations.

        Args:
            violations: List of violations
            total_actions: Total number of actions checked

        Returns:
            Compliance score (0.0 to 1.0)
        """
        if not violations or total_actions == 0:
            return 1.0

        # Weight by severity
        severity_weights = {
            ViolationSeverity.CRITICAL: 10.0,
            ViolationSeverity.HIGH: 5.0,
            ViolationSeverity.MEDIUM: 2.0,
            ViolationSeverity.LOW: 0.5
        }

        total_penalty = sum(
            severity_weights.get(v["severity"], 1.0) for v in violations
        )

        # Normalize (max penalty = 10 per action)
        max_penalty = total_actions * 10.0
        score = max(0.0, 1.0 - (total_penalty / max_penalty))

        return score


# Singleton instance helper
def get_constitutional_validator(db: Session) -> ConstitutionalValidator:
    """Get or create ConstitutionalValidator instance."""
    return ConstitutionalValidator(db)
