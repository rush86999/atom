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

    def validate_with_knowledge_graph(
        self,
        agent_id: str,
        action: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate agent action against Knowledge Graph rules when available.

        This method attempts to use a Knowledge Graph service for more sophisticated
        rule validation, falling back to pattern-based validation if unavailable.

        Args:
            agent_id: ID of the agent performing the action
            action: Action dictionary to validate
            context: Optional context for the validation

        Returns:
            {
                "compliant": bool,
                "violations": List[Dict],
                "total_rules_checked": int,
                "validation_method": "knowledge_graph" | "fallback"
            }
        """
        # Try to use Knowledge Graph service if available
        try:
            from core.knowledge_graph_service import KnowledgeGraphService

            kg_service = KnowledgeGraphService(self.db)

            # Get applicable constitutional rules for this agent and action
            rules = kg_service.get_applicable_rules(
                agent_id=agent_id,
                action_type=action.get("action_type", "unknown"),
                context=context or {}
            )

            if rules:
                # Check each rule for violations using KG
                violations = []
                for rule in rules:
                    if not self._passes_kg_rule(rule, action, context or {}):
                        violations.append({
                            "rule_id": rule.get("id", "unknown"),
                            "rule_name": rule.get("name", "Unknown Rule"),
                            "reason": rule.get("description", ""),
                            "severity": rule.get("severity", "medium"),
                            "category": rule.get("category", "general")
                        })

                return {
                    "compliant": len(violations) == 0,
                    "violations": violations,
                    "total_rules_checked": len(rules),
                    "validation_method": "knowledge_graph"
                }

        except ImportError:
            logger.warning("Knowledge Graph service not available, using fallback validation")
        except Exception as e:
            logger.warning(f"Knowledge Graph validation failed, using fallback: {e}")

        # Fallback: Use pattern-based validation (existing implementation)
        return self._fallback_validation(action, context or {})

    def _passes_kg_rule(
        self,
        rule: Dict[str, Any],
        action: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Check if an action passes a specific Knowledge Graph rule.

        Args:
            rule: Rule dictionary from Knowledge Graph
            action: Action to validate
            context: Execution context

        Returns:
            True if action passes the rule, False otherwise
        """
        # Extract rule conditions
        conditions = rule.get("conditions", {})
        action_type = action.get("action_type", "")

        # Check action type restrictions
        if "allowed_actions" in rule:
            if action_type not in rule["allowed_actions"]:
                return False

        # Check forbidden actions
        if "forbidden_actions" in rule:
            if action_type in rule["forbidden_actions"]:
                return False

        # Check domain-specific conditions
        if "domain_conditions" in rule:
            domain_rules = rule["domain_conditions"]
            # Check if action violates domain-specific constraints
            for domain, constraints in domain_rules.items():
                if context.get("domain") == domain:
                    if not self._check_domain_constraints(action, constraints):
                        return False

        # Check required permissions
        if "required_permissions" in rule:
            user_permissions = context.get("permissions", [])
            required = rule["required_permissions"]
            if not all(perm in user_permissions for perm in required):
                return False

        return True

    def _check_domain_constraints(
        self,
        action: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> bool:
        """
        Check if action satisfies domain-specific constraints.

        Args:
            action: Action to check
            constraints: Domain constraints

        Returns:
            True if constraints are satisfied
        """
        # Check data constraints (e.g., PII, HIPAA)
        if "data_restrictions" in constraints:
            restricted_data = constraints["data_restrictions"]
            action_data = str(action.get("content", {}))

            for restricted_type in restricted_data:
                if restricted_type == "pii":
                    # Simple pattern check for PII
                    pii_patterns = ["ssn", "social_security", "credit_card", "bank_account"]
                    if any(pattern in action_data.lower() for pattern in pii_patterns):
                        return False

                elif restricted_type == "phi":
                    # HIPAA Protected Health Information
                    phi_patterns = ["medical_record", "patient_id", "diagnosis", "treatment"]
                    if any(pattern in action_data.lower() for pattern in phi_patterns):
                        # Check if proper authorization exists
                        if not action.get("authorized", False):
                            return False

        # Check amount constraints for financial actions
        if "max_amount" in constraints and action.get("action_type") == "payment":
            amount = action.get("content", {}).get("amount", 0)
            if amount > constraints["max_amount"]:
                return False

        # Check approval requirements
        if "requires_approval" in constraints:
            if constraints["requires_approval"] and not action.get("approved", False):
                return False

        return True

    def _fallback_validation(
        self,
        action: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fallback validation using pattern matching when KG is unavailable.

        Args:
            action: Action to validate
            context: Execution context

        Returns:
            Validation result dictionary
        """
        violations = []

        # Check against built-in constitutional rules
        for rule_id, rule in self.CONSTITUTIONAL_RULES.items():
            violation = self._check_rule_violation(action, rule_id, rule)
            if violation:
                violations.append(violation)

        return {
            "compliant": len([v for v in violations if v["severity"] == ViolationSeverity.CRITICAL]) == 0,
            "violations": violations,
            "total_rules_checked": len(self.CONSTITUTIONAL_RULES),
            "validation_method": "fallback"
        }


# Singleton instance helper
def get_constitutional_validator(db: Session) -> ConstitutionalValidator:
    """Get or create ConstitutionalValidator instance."""
    return ConstitutionalValidator(db)
