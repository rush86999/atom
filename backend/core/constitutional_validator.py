"""
Constitutional Validator Service

Validates agent actions against constitutional rules and constraints.
Provides compliance scoring and violation detection for agent graduation.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ViolationSeverity:
    """Severity levels for constitutional violations."""
    CRITICAL = "critical"  # Security, legal compliance, safety
    HIGH = "high"          # Major policy violations
    MEDIUM = "medium"      # Moderate policy issues
    LOW = "low"            # Minor deviations, best practices


class ConstitutionalValidator:
    """
    Validates agent actions against constitutional rules.
    """

    # Core constitutional rules for Open Source
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
            "description": "All regulated actions must be logged for audit",
            "severity": ViolationSeverity.MEDIUM,
            "domains": ["all"]
        },
    }

    def __init__(self, db: Session):
        self.db = db

    def get_rules(self) -> Dict[str, Any]:
        """Provides constitutional rules."""
        return self.CONSTITUTIONAL_RULES

    def validate_actions(
        self,
        actions: List[Dict[str, Any]],
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate a list of actions against constitutional rules.

        Args:
            actions: List of action dictionaries {type, content, metadata}
            domain: Optional domain for domain-specific rules
        """
        # Handle None or empty actions
        if actions is None:
            actions = []

        violations = []
        total_actions = len(actions)
        
        for action in actions:
            # Check each applicable constitutional rule
            for rule_id, rule in self.get_rules().items():
                # Skip if domain-specific and domain doesn't match
                if domain and rule["domains"] != ["all"] and domain not in rule["domains"]:
                    continue

                # Validate action against rule
                violation = self._check_rule_violation(action, rule_id, rule)
                if violation:
                    violations.append(violation)

        # Calculate compliance score
        score = self._calculate_compliance_score(violations, total_actions)

        return {
            "compliant": len([v for v in violations if v["severity"] == ViolationSeverity.CRITICAL]) == 0,
            "score": score,
            "violations": violations,
            "total_actions": total_actions
        }

    def _check_rule_violation(
        self,
        action: Dict[str, Any],
        rule_id: str,
        rule: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Check if an action violates a specific constitutional rule using pattern matching.
        """
        action_type = action.get("type") or action.get("action_type", "unknown")
        content = str(action.get("content", ""))
        metadata = action.get("metadata") or {}
        
        # 1. PII Detection (Regex based)
        if rule_id == "safety_no_pii_exposure":
            text = content.lower()
            patterns = {
                "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
                "Credit Card": r"\b(?:\d[ -]*?){13,16}\b",
                "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            }
            for name, pattern in patterns.items():
                if re.search(pattern, text):
                    return {
                        "rule_id": rule_id,
                        "rule_description": rule["description"],
                        "severity": rule["severity"],
                        "action_type": action_type,
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                        "details": f"Potential {name} exposure detected."
                    }

        # 2. Unauthorized Payments
        if rule_id == "financial_no_unauthorized_payments":
            if any(k in action_type.lower() for k in ["payment", "transfer", "payout"]):
                is_approved = metadata.get("is_approved", False) or action.get("is_approved", False)
                if not is_approved:
                    return {
                        "rule_id": rule_id,
                        "rule_description": rule["description"],
                        "severity": rule["severity"],
                        "action_type": action_type,
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                        "details": "Regulated financial action missing explicit approval flag."
                    }

        # 3. Governance Audit Trail
        if rule_id == "governance_audit_trail":
            # For specific sensitive types, require audit log ID
            sensitive_types = ["delete", "drop", "update_config", "payment"]
            if any(t in action_type.lower() for t in sensitive_types):
                if not metadata.get("audit_log_id"):
                    return {
                        "rule_id": rule_id,
                        "rule_description": rule["description"],
                        "severity": rule["severity"],
                        "action_type": action_type,
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                        "details": f"Sensitive action '{action_type}' missing audit_log_id."
                    }

        return None

    def _calculate_compliance_score(
        self,
        violations: List[Dict[str, Any]],
        total_actions: int
    ) -> float:
        """
        Calculate compliance score from violations.
        """
        if total_actions == 0:
            return 1.0
        if not violations:
            return 1.0

        # Weight by severity
        severity_weights = {
            ViolationSeverity.CRITICAL: 10.0,
            ViolationSeverity.HIGH: 5.0,
            ViolationSeverity.MEDIUM: 2.0,
            ViolationSeverity.LOW: 0.5
        }

        total_penalty = sum(
            severity_weights.get(str(v.get("severity") or "low"), 1.0) for v in violations
        )

        # Normalize (max penalty = 10 per action checked)
        max_penalty = total_actions * 10.0
        score = max(0.0, 1.0 - (total_penalty / max_penalty))

        return score


def get_constitutional_validator(db: Session) -> ConstitutionalValidator:
    """Get ConstitutionalValidator instance."""
    return ConstitutionalValidator(db)
