"""
Centralized Governance Configuration for Atom Platform

Provides single source of truth for all governance settings including:
- Feature flags
- Maturity level validation
- Action complexity requirements
- Governance decision logging
- Configuration validation

Usage:
    from core.governance_config import check_governance, GovernanceConfig

    # Simple check
    allowed, reason = check_governance(
        feature="canvas",
        agent_id=agent.id,
        action="submit_form",
        action_complexity=3,
        maturity_level=agent.maturity_level
    )

    if not allowed:
        raise router.permission_denied_error("submit_form", reason)

    # Advanced usage
    config = GovernanceConfig()
    if config.is_governance_enabled("browser_automation"):
        # Browser automation is governed
        ...
"""

from dataclasses import dataclass
from enum import Enum
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ========================================================================
# Enums and Constants
# ========================================================================

class MaturityLevel(Enum):
    """Agent maturity levels"""
    STUDENT = "STUDENT"
    INTERN = "INTERN"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"


class ActionComplexity(Enum):
    """Action complexity levels"""
    LOW = 1          # Presentations, read-only → STUDENT+
    MODERATE = 2     # Streaming, moderate actions → INTERN+
    HIGH = 3         # State changes, submissions → SUPERVISED+
    CRITICAL = 4     # Deletions, payments → AUTONOMOUS only


class FeatureType(Enum):
    """Feature types for governance"""
    # Core features
    AGENT_EXECUTION = "agent_execution"
    CANVAS_PRESENTATION = "canvas_presentation"
    CANVAS_FORM_SUBMISSION = "canvas_form_submission"
    BROWSER_AUTOMATION = "browser_automation"

    # Device capabilities
    DEVICE_CAMERA = "device_camera"
    DEVICE_SCREEN_RECORDING = "device_screen_recording"
    DEVICE_LOCATION = "device_location"
    DEVICE_NOTIFICATIONS = "device_notifications"
    DEVICE_COMMAND_EXECUTION = "device_command_execution"

    # Workflow features
    WORKFLOW_EXECUTION = "workflow_execution"
    WORKFLOW_MODIFICATION = "workflow_modification"

    # Integration features
    EXTERNAL_API_CALL = "external_api_call"
    WEBHOOK_EXECUTION = "webhook_execution"

    # Admin features
    USER_MANAGEMENT = "user_management"
    AGENT_MANAGEMENT = "agent_management"
    SYSTEM_CONFIGURATION = "system_configuration"


# ========================================================================
# Configuration Data Classes
# ========================================================================

@dataclass
class GovernanceRule:
    """Governance rule for a feature"""
    feature: FeatureType
    min_maturity: MaturityLevel
    action_complexity: ActionComplexity
    description: str
    requires_human_approval: bool = False
    audit_log_only: bool = False


@dataclass
class GovernanceDecision:
    """Result of a governance check"""
    allowed: bool
    reason: str
    feature: FeatureType
    agent_maturity: MaturityLevel
    required_maturity: Optional[MaturityLevel] = None
    action_complexity: Optional[ActionComplexity] = None


# ========================================================================
# Main Governance Configuration Class
# ========================================================================

class GovernanceConfig:
    """
    Centralized governance configuration.

    Provides single source of truth for:
    - Feature flags
    - Maturity level requirements
    - Action complexity rules
    - Governance validation
    """

    # Default governance rules
    DEFAULT_RULES: Dict[FeatureType, GovernanceRule] = {
        # Core features
        FeatureType.AGENT_EXECUTION: GovernanceRule(
            feature=FeatureType.AGENT_EXECUTION,
            min_maturity=MaturityLevel.STUDENT,
            action_complexity=ActionComplexity.LOW,
            description="Agent execution and response generation"
        ),
        FeatureType.CANVAS_PRESENTATION: GovernanceRule(
            feature=FeatureType.CANVAS_PRESENTATION,
            min_maturity=MaturityLevel.STUDENT,
            action_complexity=ActionComplexity.LOW,
            description="Canvas presentations (read-only)"
        ),
        FeatureType.CANVAS_FORM_SUBMISSION: GovernanceRule(
            feature=FeatureType.CANVAS_FORM_SUBMISSION,
            min_maturity=MaturityLevel.INTERN,
            action_complexity=ActionComplexity.HIGH,
            description="Canvas form submissions",
            requires_human_approval=True
        ),
        FeatureType.BROWSER_AUTOMATION: GovernanceRule(
            feature=FeatureType.BROWSER_AUTOMATION,
            min_maturity=MaturityLevel.INTERN,
            action_complexity=ActionComplexity.MODERATE,
            description="Browser automation (scraping, form filling)"
        ),

        # Device capabilities
        FeatureType.DEVICE_CAMERA: GovernanceRule(
            feature=FeatureType.DEVICE_CAMERA,
            min_maturity=MaturityLevel.INTERN,
            action_complexity=ActionComplexity.MODERATE,
            description="Device camera access"
        ),
        FeatureType.DEVICE_SCREEN_RECORDING: GovernanceRule(
            feature=FeatureType.DEVICE_SCREEN_RECORDING,
            min_maturity=MaturityLevel.SUPERVISED,
            action_complexity=ActionComplexity.HIGH,
            description="Device screen recording"
        ),
        FeatureType.DEVICE_LOCATION: GovernanceRule(
            feature=FeatureType.DEVICE_LOCATION,
            min_maturity=MaturityLevel.INTERN,
            action_complexity=ActionComplexity.MODERATE,
            description="Device location access"
        ),
        FeatureType.DEVICE_NOTIFICATIONS: GovernanceRule(
            feature=FeatureType.DEVICE_NOTIFICATIONS,
            min_maturity=MaturityLevel.INTERN,
            action_complexity=ActionComplexity.MODERATE,
            description="Device notifications"
        ),
        FeatureType.DEVICE_COMMAND_EXECUTION: GovernanceRule(
            feature=FeatureType.DEVICE_COMMAND_EXECUTION,
            min_maturity=MaturityLevel.AUTONOMOUS,
            action_complexity=ActionComplexity.CRITICAL,
            description="Device command execution"
        ),

        # Workflow features
        FeatureType.WORKFLOW_EXECUTION: GovernanceRule(
            feature=FeatureType.WORKFLOW_EXECUTION,
            min_maturity=MaturityLevel.INTERN,
            action_complexity=ActionComplexity.MODERATE,
            description="Workflow execution"
        ),
        FeatureType.WORKFLOW_MODIFICATION: GovernanceRule(
            feature=FeatureType.WORKFLOW_MODIFICATION,
            min_maturity=MaturityLevel.SUPERVISED,
            action_complexity=ActionComplexity.HIGH,
            description="Workflow modification",
            requires_human_approval=True
        ),

        # Integration features
        FeatureType.EXTERNAL_API_CALL: GovernanceRule(
            feature=FeatureType.EXTERNAL_API_CALL,
            min_maturity=MaturityLevel.INTERN,
            action_complexity=ActionComplexity.MODERATE,
            description="External API calls"
        ),
        FeatureType.WEBHOOK_EXECUTION: GovernanceRule(
            feature=FeatureType.WEBHOOK_EXECUTION,
            min_maturity=MaturityLevel.SUPERVISED,
            action_complexity=ActionComplexity.HIGH,
            description="Webhook execution"
        ),

        # Admin features
        FeatureType.USER_MANAGEMENT: GovernanceRule(
            feature=FeatureType.USER_MANAGEMENT,
            min_maturity=MaturityLevel.AUTONOMOUS,
            action_complexity=ActionComplexity.CRITICAL,
            description="User management"
        ),
        FeatureType.AGENT_MANAGEMENT: GovernanceRule(
            feature=FeatureType.AGENT_MANAGEMENT,
            min_maturity=MaturityLevel.AUTONOMOUS,
            action_complexity=ActionComplexity.CRITICAL,
            description="Agent management"
        ),
        FeatureType.SYSTEM_CONFIGURATION: GovernanceRule(
            feature=FeatureType.SYSTEM_CONFIGURATION,
            min_maturity=MaturityLevel.AUTONOMOUS,
            action_complexity=ActionComplexity.CRITICAL,
            description="System configuration",
            audit_log_only=True
        ),
    }

    # Maturity level hierarchy (lower = more restricted)
    MATURITY_HIERARCHY = {
        MaturityLevel.STUDENT: 0,
        MaturityLevel.INTERN: 1,
        MaturityLevel.SUPERVISED: 2,
        MaturityLevel.AUTONOMOUS: 3,
    }

    def __init__(self):
        """Initialize governance configuration"""
        self._rules = self.DEFAULT_RULES.copy()
        self._feature_flags = self._load_feature_flags()
        self._emergency_bypass = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

        if self._emergency_bypass:
            logger.error("⚠️ EMERGENCY GOVERNANCE BYPASS ENABLED - All checks will be bypassed!")

    def _load_feature_flags(self) -> Dict[str, bool]:
        """
        Load feature flags from environment variables.

        Format: GOVERNANCE_{FEATURE_NAME}_ENABLED=true/false

        Returns:
            Dictionary of feature flags
        """
        flags = {}

        # Default enabled features
        for feature in FeatureType:
            env_var = f"GOVERNANCE_{feature.value.upper()}_ENABLED"
            flags[feature.value] = os.getenv(env_var, "true").lower() == "true"

        # Global governance switch
        flags["_global"] = os.getenv("GOVERNANCE_ENABLED", "true").lower() == "true"

        return flags

    def is_governance_enabled(self, feature: str) -> bool:
        """
        Check if governance is enabled for a feature.

        Args:
            feature: Feature name or type

        Returns:
            True if governance is enabled
        """
        # Check emergency bypass
        if self._emergency_bypass:
            return False

        # Check global switch
        if not self._feature_flags.get("_global", True):
            return False

        # Check feature-specific flag
        return self._feature_flags.get(feature, True)

    def validate_maturity_for_action(
        self,
        maturity_level: str,
        action_complexity: int
    ) -> bool:
        """
        Validate if agent maturity is sufficient for action complexity.

        Args:
            maturity_level: Agent's maturity level
            action_complexity: Action complexity (1-4)

        Returns:
            True if maturity is sufficient
        """
        try:
            maturity = MaturityLevel(maturity_level)
            complexity = ActionComplexity(action_complexity)

            # Map complexity to required maturity
            required_maturity_map = {
                ActionComplexity.LOW: MaturityLevel.STUDENT,
                ActionComplexity.MODERATE: MaturityLevel.INTERN,
                ActionComplexity.HIGH: MaturityLevel.SUPERVISED,
                ActionComplexity.CRITICAL: MaturityLevel.AUTONOMOUS,
            }

            required = required_maturity_map[complexity]
            actual = maturity

            return self.MATURITY_HIERARCHY[actual] >= self.MATURITY_HIERARCHY[required]

        except (ValueError, KeyError) as e:
            logger.error(f"Invalid maturity/complexity: {e}")
            return False

    def get_required_maturity(self, feature: FeatureType) -> MaturityLevel:
        """
        Get required maturity level for a feature.

        Args:
            feature: Feature type

        Returns:
            Required maturity level
        """
        rule = self._rules.get(feature)
        return rule.min_maturity if rule else MaturityLevel.AUTONOMOUS

    def check_governance(
        self,
        feature: str,
        agent_id: str,
        action: str,
        action_complexity: int = 1,
        maturity_level: str = "STUDENT"
    ) -> GovernanceDecision:
        """
        Perform comprehensive governance check.

        Args:
            feature: Feature name
            agent_id: Agent identifier
            action: Action being performed
            action_complexity: Action complexity (1-4)
            maturity_level: Agent's maturity level

        Returns:
            GovernanceDecision with result
        """
        # Emergency bypass
        if self._emergency_bypass:
            logger.warning(f"Emergency bypass: Allowing {action} for agent {agent_id}")
            return GovernanceDecision(
                allowed=True,
                reason="Emergency bypass active",
                feature=FeatureType.AGENT_EXECUTION,  # Default
                agent_maturity=MaturityLevel(maturity_level)
            )

        # Check if governance is enabled
        if not self.is_governance_enabled(feature):
            return GovernanceDecision(
                allowed=True,
                reason=f"Governance disabled for {feature}",
                feature=FeatureType.AGENT_EXECUTION,
                agent_maturity=MaturityLevel(maturity_level)
            )

        # Parse inputs
        try:
            feature_enum = FeatureType(feature)
            maturity = MaturityLevel(maturity_level)
            complexity = ActionComplexity(action_complexity)
        except (ValueError, KeyError) as e:
            return GovernanceDecision(
                allowed=False,
                reason=f"Invalid governance parameters: {e}",
                feature=FeatureType.AGENT_EXECUTION,
                agent_maturity=MaturityLevel.STUDENT
            )

        # Get rule
        rule = self._rules.get(feature_enum)
        if not rule:
            logger.warning(f"No governance rule for feature: {feature}")
            # Default to allowing with autonomous requirement
            return GovernanceDecision(
                allowed=maturity == MaturityLevel.AUTONOMOUS,
                reason=f"No rule defined, requires AUTONOMOUS",
                feature=feature_enum,
                agent_maturity=maturity,
                required_maturity=MaturityLevel.AUTONOMOUS
            )

        # Check maturity requirement
        if self.MATURITY_HIERARCHY[maturity] < self.MATURITY_HIERARCHY[rule.min_maturity]:
            return GovernanceDecision(
                allowed=False,
                reason=(
                    f"Agent maturity {maturity.value} insufficient for {feature}. "
                    f"Required: {rule.min_maturity.value}"
                ),
                feature=feature_enum,
                agent_maturity=maturity,
                required_maturity=rule.min_maturity,
                action_complexity=complexity
            )

        # Check complexity requirement
        required_maturity_for_complexity = {
            ActionComplexity.LOW: MaturityLevel.STUDENT,
            ActionComplexity.MODERATE: MaturityLevel.INTERN,
            ActionComplexity.HIGH: MaturityLevel.SUPERVISED,
            ActionComplexity.CRITICAL: MaturityLevel.AUTONOMOUS,
        }

        required = required_maturity_for_complexity[complexity]
        if self.MATURITY_HIERARCHY[maturity] < self.MATURITY_HIERARCHY[required]:
            return GovernanceDecision(
                allowed=False,
                reason=(
                    f"Action complexity {complexity.value} requires {required.value} maturity. "
                    f"Agent: {maturity.value}"
                ),
                feature=feature_enum,
                agent_maturity=maturity,
                required_maturity=required,
                action_complexity=complexity
            )

        # All checks passed
        return GovernanceDecision(
            allowed=True,
            reason=f"Governance check passed for {feature}",
            feature=feature_enum,
            agent_maturity=maturity,
            required_maturity=rule.min_maturity,
            action_complexity=complexity
        )

    def log_governance_decision(
        self,
        feature: str,
        agent_id: str,
        action: str,
        allowed: bool,
        reason: str,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """
        Log governance decision for audit trail.

        Args:
            feature: Feature name
            agent_id: Agent identifier
            action: Action being performed
            allowed: Whether action was allowed
            reason: Reason for decision
            additional_context: Optional additional context
        """
        log_data = {
            "feature": feature,
            "agent_id": agent_id,
            "action": action,
            "allowed": allowed,
            "reason": reason,
        }

        if additional_context:
            log_data.update(additional_context)

        if allowed:
            logger.info(f"Governance: Allowed {action} on {feature}", extra=log_data)
        else:
            logger.warning(f"Governance: Blocked {action} on {feature}", extra=log_data)

    def validate_config(self) -> Dict[str, Any]:
        """
        Validate governance configuration for security issues.

        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []

        # Check for emergency bypass
        if self._emergency_bypass:
            issues.append({
                "severity": "CRITICAL",
                "issue": "EMERGENCY_GOVERNANCE_BYPASS is enabled",
                "recommendation": "Disable emergency bypass immediately"
            })

        # Check if global governance is disabled
        if not self._feature_flags.get("_global", True):
            issues.append({
                "severity": "HIGH",
                "issue": "GOVERNANCE_ENABLED is false",
                "recommendation": "Enable governance unless in development environment"
            })

        # Check for overly permissive rules
        for feature, rule in self._rules.items():
            if rule.min_maturity == MaturityLevel.STUDENT and rule.action_complexity == ActionComplexity.CRITICAL:
                warnings.append({
                    "severity": "MEDIUM",
                    "issue": f"{feature.value} allows CRITICAL actions with STUDENT maturity",
                    "recommendation": "Review maturity requirements"
                })

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "rules_count": len(self._rules),
            "features_governed": len([f for f, enabled in self._feature_flags.items() if enabled and not f.startswith("_")])
        }


# ========================================================================
# Global Instance and Convenience Functions
# ========================================================================

_governance_config: Optional[GovernanceConfig] = None


def get_governance_config() -> GovernanceConfig:
    """Get or create global governance configuration instance"""
    global _governance_config
    if _governance_config is None:
        _governance_config = GovernanceConfig()
    return _governance_config


def check_governance(
    feature: str,
    agent_id: str,
    action: str,
    action_complexity: int = 1,
    maturity_level: str = "STUDENT",
    log_decision: bool = True
) -> Tuple[bool, str]:
    """
    Convenience function for governance checks in route handlers.

    Args:
        feature: Feature name (e.g., "canvas", "browser", "device")
        agent_id: Agent identifier
        action: Action being performed (e.g., "submit_form", "navigate")
        action_complexity: Action complexity (1-4)
        maturity_level: Agent's maturity level
        log_decision: Whether to log the decision

    Returns:
        Tuple of (allowed: bool, reason: str)

    Example:
        from core.governance_config import check_governance

        allowed, reason = check_governance(
            feature="canvas",
            agent_id=agent.id,
            action="submit_form",
            action_complexity=3,
            maturity_level=agent.maturity_level
        )

        if not allowed:
            raise router.permission_denied_error("submit_form", reason=reason)
    """
    config = get_governance_config()
    decision = config.check_governance(
        feature=feature,
        agent_id=agent_id,
        action=action,
        action_complexity=action_complexity,
        maturity_level=maturity_level
    )

    if log_decision:
        config.log_governance_decision(
            feature=feature,
            agent_id=agent_id,
            action=action,
            allowed=decision.allowed,
            reason=decision.reason
        )

    return decision.allowed, decision.reason


def is_governance_enabled(feature: str) -> bool:
    """
    Check if governance is enabled for a feature.

    Args:
        feature: Feature name

    Returns:
        True if governance is enabled
    """
    config = get_governance_config()
    return config.is_governance_enabled(feature)


def validate_maturity_for_action(maturity_level: str, action_complexity: int) -> bool:
    """
    Validate if agent maturity is sufficient for action complexity.

    Args:
        maturity_level: Agent's maturity level
        action_complexity: Action complexity (1-4)

    Returns:
        True if maturity is sufficient
    """
    config = get_governance_config()
    return config.validate_maturity_for_action(maturity_level, action_complexity)
