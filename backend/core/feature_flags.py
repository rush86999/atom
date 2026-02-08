"""
Centralized Feature Flags for Atom Platform

This module consolidates all feature flags into a single location for better
maintainability and consistency. Flags are loaded from environment variables
with sensible defaults.

Usage:
    from core.feature_flags import FeatureFlags

    if FeatureFlags.BROWSER_GOVERNANCE_ENABLED:
        # Perform governed operation
        pass
"""
import os
from typing import Any, Dict


class FeatureFlags:
    """
    Centralized feature flags management.

    All flags default to 'true' (enabled) unless explicitly disabled via environment variable.
    Emergency bypass flags default to 'false' (disabled) for safety.

    Environment Variable Format:
        - Feature flags: <FEATURE_NAME>_ENABLED=true|false
        - Emergency bypass: EMERGENCY_<FEATURE>_BYPASS=true|false
    """

    # ============================================================================
    # Governance Feature Flags
    # ============================================================================

    # Browser Automation Governance
    BROWSER_GOVERNANCE_ENABLED = os.getenv("BROWSER_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Canvas Presentation Governance
    CANVAS_GOVERNANCE_ENABLED = os.getenv("CANVAS_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Device Capabilities Governance
    DEVICE_GOVERNANCE_ENABLED = os.getenv("DEVICE_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Form Submission Governance
    FORM_GOVERNANCE_ENABLED = os.getenv("FORM_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Workflow Governance
    WORKFLOW_GOVERNANCE_ENABLED = os.getenv("WORKFLOW_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Background Agent Governance
    BACKGROUND_AGENT_GOVERNANCE_ENABLED = os.getenv("BACKGROUND_AGENT_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Memory/Context Governance
    MEMORY_GOVERNANCE_ENABLED = os.getenv("MEMORY_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Project Management Governance
    PROJECT_GOVERNANCE_ENABLED = os.getenv("PROJECT_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Connection/Integration Governance
    CONNECTION_GOVERNANCE_ENABLED = os.getenv("CONNECTION_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Financial Operations Governance
    FINANCIAL_GOVERNANCE_ENABLED = os.getenv("FINANCIAL_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Billing/Payment Governance
    BILLING_GOVERNANCE_ENABLED = os.getenv("BILLING_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Admin Operations Governance
    ADMIN_GOVERNANCE_ENABLED = os.getenv("ADMIN_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Operations/Task Governance
    OPERATIONS_GOVERNANCE_ENABLED = os.getenv("OPERATIONS_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Reconciliation Governance
    RECONCILIATION_GOVERNANCE_ENABLED = os.getenv("RECONCILIATION_GOVERNANCE_ENABLED", "true").lower() == "true"

    # ============================================================================
    # Emergency Bypass Flags (Security-Critical: Default to False)
    # ============================================================================

    # Global emergency bypass for ALL governance checks
    # ⚠️  SECURITY RISK: Only enable in genuine emergencies
    EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

    # ============================================================================
    # Streaming and Real-Time Features
    # ============================================================================

    # Streaming LLM Governance
    STREAMING_GOVERNANCE_ENABLED = os.getenv("STREAMING_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Real-Time Collaboration
    REALTIME_COLLABORATION_ENABLED = os.getenv("REALTIME_COLLABORATION_ENABLED", "true").lower() == "true"

    # WebSocket Support
    WEBSOCKET_ENABLED = os.getenv("WEBSOCKET_ENABLED", "true").lower() == "true"

    # ============================================================================
    # AI/ML Features
    # ============================================================================

    # Proposal Execution (INTERN agents)
    PROPOSAL_EXECUTION_ENABLED = os.getenv("PROPOSAL_EXECUTION_ENABLED", "true").lower() == "true"

    # Student Agent Training
    STUDENT_TRAINING_ENABLED = os.getenv("STUDENT_TRAINING_ENABLED", "true").lower() == "true"

    # Supervision Monitoring
    SUPERVISION_ENABLED = os.getenv("SUPERVISION_ENABLED", "true").lower() == "true"

    # ============================================================================
    # Integration Features
    # ============================================================================

    # Browser Automation (Playwright CDP)
    BROWSER_AUTOMATION_ENABLED = os.getenv("BROWSER_AUTOMATION_ENABLED", "true").lower() == "true"

    # Device Capabilities (Camera, Screen Recording, etc.)
    DEVICE_CAPABILITIES_ENABLED = os.getenv("DEVICE_CAPABILITIES_ENABLED", "true").lower() == "true"

    # Deep Linking
    DEEPLINK_ENABLED = os.getenv("DEEPLINK_ENABLED", "true").lower() == "true"

    # ============================================================================
    # Development/Debug Features
    # ============================================================================

    # Debug Mode
    DEBUG_ENABLED = os.getenv("DEBUG_ENABLED", "false").lower() == "true"

    # Verbose Logging
    VERBOSE_LOGGING_ENABLED = os.getenv("VERBOSE_LOGGING_ENABLED", "false").lower() == "true"

    # Mock Database (for testing)
    MOCK_DATABASE_ENABLED = os.getenv("ATOM_MOCK_DATABASE", "false").lower() == "true"

    # ============================================================================
    # Class Methods
    # ============================================================================

    @classmethod
    def is_governance_enabled(cls, feature: str) -> bool:
        """
        Check if governance is enabled for a specific feature.

        Args:
            feature: Feature name (e.g., 'browser', 'canvas', 'device')

        Returns:
            True if governance is enabled for the feature

        Example:
            if FeatureFlags.is_governance_enabled('browser'):
                # Perform governance check
                pass
        """
        flag_name = f"{feature.upper()}_GOVERNANCE_ENABLED"
        return getattr(cls, flag_name, True)

    @classmethod
    def is_emergency_bypass_active(cls) -> bool:
        """
        Check if emergency bypass is active.

        ⚠️  SECURITY: Log all emergency bypass usage for audit.

        Returns:
            True if emergency bypass is enabled
        """
        if cls.EMERGENCY_GOVERNANCE_BYPASS:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("⚠️  EMERGENCY GOVERNANCE BYPASS IS ACTIVE - All governance checks are disabled!")

        return cls.EMERGENCY_GOVERNANCE_BYPASS

    @classmethod
    def should_enforce_governance(cls, feature: str) -> bool:
        """
        Determine if governance should be enforced for a feature.

        Returns False if:
        - Emergency bypass is active, OR
        - Feature-specific governance is disabled

        Args:
            feature: Feature name (e.g., 'browser', 'canvas')

        Returns:
            True if governance should be enforced

        Example:
            if FeatureFlags.should_enforce_governance('browser'):
                # Enforce governance
                pass
        """
        if cls.is_emergency_bypass_active():
            return False

        return cls.is_governance_enabled(feature)

    @classmethod
    def get_all_flags(cls) -> Dict[str, Any]:
        """
        Get all feature flags as a dictionary.

        Useful for debugging and monitoring.

        Returns:
            Dictionary of all feature flags
        """
        flags = {}
        for attr_name in dir(cls):
            if attr_name.isupper() and not attr_name.startswith('_'):
                flags[attr_name] = getattr(cls, attr_name)
        return flags

    @classmethod
    def validate_flags(cls) -> Dict[str, bool]:
        """
        Validate feature flags for potential security issues.

        Returns:
            Dictionary with validation results
        """
        issues = {}

        # Check for emergency bypass
        if cls.EMERGENCY_GOVERNANCE_BYPASS:
            issues['EMERGENCY_BYPASS_ACTIVE'] = True

        # Check for disabled governance in production
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            critical_governance = [
                'BROWSER_GOVERNANCE_ENABLED',
                'DEVICE_GOVERNANCE_ENABLED',
                'FINANCIAL_GOVERNANCE_ENABLED',
                'BILLING_GOVERNANCE_ENABLED'
            ]
            for flag in critical_governance:
                if not getattr(cls, flag):
                    issues[f'{flag}_DISABLED_IN_PRODUCTION'] = True

        return issues


# ============================================================================
# Convenience Functions
# ============================================================================

def is_governance_required(feature: str = None) -> bool:
    """
    Convenience function to check if governance is required.

    Args:
        feature: Optional feature name. If None, checks general governance.

    Returns:
        True if governance should be enforced
    """
    if FeatureFlags.is_emergency_bypass_active():
        return False

    if feature:
        return FeatureFlags.is_governance_enabled(feature)

    # Default to true if no specific feature
    return True


def get_feature_status() -> Dict[str, Any]:
    """
    Get status of all feature flags for monitoring.

    Returns:
        Dictionary with feature flag statuses
    """
    return FeatureFlags.get_all_flags()
