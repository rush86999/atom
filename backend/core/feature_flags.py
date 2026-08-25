from __future__ import annotations
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
from typing import Any, Union


class FeatureFlags:
    """
    Centralized feature flags management.

    All flags default to 'true' (enabled) unless explicitly disabled via environment variable.
    Emergency bypass flags default to 'false' (disabled) for safety.

    Environment Variable Format:
        - Feature flags: <FEATURE_NAME>_ENABLED=(true|false)
        - Emergency bypass: EMERGENCY_<FEATURE>_BYPASS=(true|false)
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
    BACKGROUND_AGENT_GOVERNANCE_ENABLED = (
        os.getenv("BACKGROUND_AGENT_GOVERNANCE_ENABLED", "true").lower() == "true"
    )

    # Memory/Context Governance
    MEMORY_GOVERNANCE_ENABLED = os.getenv("MEMORY_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Project Management Governance
    PROJECT_GOVERNANCE_ENABLED = os.getenv("PROJECT_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Connection/Integration Governance
    CONNECTION_GOVERNANCE_ENABLED = (
        os.getenv("CONNECTION_GOVERNANCE_ENABLED", "true").lower() == "true"
    )

    # Financial Operations Governance
    FINANCIAL_GOVERNANCE_ENABLED = (
        os.getenv("FINANCIAL_GOVERNANCE_ENABLED", "true").lower() == "true"
    )

    # Billing/Payment Governance
    BILLING_GOVERNANCE_ENABLED = os.getenv("BILLING_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Admin Operations Governance
    ADMIN_GOVERNANCE_ENABLED = os.getenv("ADMIN_GOVERNANCE_ENABLED", "true").lower() == "true"

    # Operations/Task Governance
    OPERATIONS_GOVERNANCE_ENABLED = (
        os.getenv("OPERATIONS_GOVERNANCE_ENABLED", "true").lower() == "true"
    )

    # Reconciliation Governance
    RECONCILIATION_GOVERNANCE_ENABLED = (
        os.getenv("RECONCILIATION_GOVERNANCE_ENABLED", "true").lower() == "true"
    )

    # ============================================================================
    # Emergency Bypass Flags (Security-Critical: Default to False)
    # ============================================================================

    # Global emergency bypass for ALL governance checks
    # ⚠️  SECURITY RISK: Only enable in genuine emergencies
    EMERGENCY_GOVERNANCE_BYPASS = (
        os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"
    )

    # ============================================================================
    # OAuth Security Kill-Switches (Emergency Only)
    # ============================================================================

    # WARNING: Only activate these if critical issues arise in production
    # Disable PKCE enforcement (allows OAuth flows without code_verifier)
    DISABLE_PKCE_ENFORCEMENT = os.getenv("DISABLE_PKCE_ENFORCEMENT", "false").lower() == "true"

    # Disable HMAC state validation (allows unsigned state parameters)
    DISABLE_HMAC_VALIDATION = os.getenv("DISABLE_HMAC_VALIDATION", "false").lower() == "true"

    # Disable state consumption (allows state replay attacks)
    DISABLE_STATE_CONSUMPTION = os.getenv("DISABLE_STATE_CONSUMPTION", "false").lower() == "true"

    # Disable tenant isolation (allows cross-tenant OAuth state access)
    DISABLE_TENANT_ISOLATION = os.getenv("DISABLE_TENANT_ISOLATION", "false").lower() == "true"

    # Global OAuth System Kill-Switch
    DISABLE_OAUTH_SYSTEM = os.getenv("DISABLE_OAUTH_SYSTEM", "false").lower() == "true"

    # ============================================================================
    # Streaming and Real-Time Features
    # ============================================================================

    # Streaming LLM Governance
    STREAMING_GOVERNANCE_ENABLED = (
        os.getenv("STREAMING_GOVERNANCE_ENABLED", "true").lower() == "true"
    )

    # Real-Time Collaboration
    REALTIME_COLLABORATION_ENABLED = (
        os.getenv("REALTIME_COLLABORATION_ENABLED", "true").lower() == "true"
    )

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

    # Smart Home Control (Philips Hue, Home Assistant) — referenced by
    # core/smarthome/hue_service.py + home_assistant_service.py; declared here
    # (wave 99: the attribute was missing and every service construction
    # raised AttributeError).
    SMART_HOME_CONTROL_ENABLED = os.getenv("SMART_HOME_CONTROL_ENABLED", "true").lower() == "true"

    # Deep Linking
    DEEPLINK_ENABLED = os.getenv("DEEPLINK_ENABLED", "true").lower() == "true"

    # Integration Action (UnifiedActionExecutor for workflow automation)
    # Defaults to FALSE for backwards compatibility (COMPAT-01)
    INTEGRATION_ACTION_ENABLED = os.getenv("INTEGRATION_ACTION_ENABLED", "false").lower() == "true"

    # Gradual rollout percentage for INTEGRATION_ACTION (0-100) (COMPAT-05)
    INTEGRATION_ACTION_ROLLOUT_PCT = int(os.getenv("INTEGRATION_ACTION_ROLLOUT_PCT", "0"))

    # ============================================================================
    # Identity & Normalization Features
    # ============================================================================

    # Tenant UUID Normalization (Standardize slugs to UUIDs at ingress)
    TENANT_UUID_NORMALIZATION_ENABLED = (
        os.getenv("TENANT_UUID_NORMALIZATION_ENABLED", "true").lower() == "true"
    )

    # Gradual rollout percentage for normalization (0-100)
    TENANT_UUID_NORMALIZATION_ROLLOUT_PCT = int(
        os.getenv("TENANT_UUID_NORMALIZATION_ROLLOUT_PCT", "100")
    )

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
    # Infrastructure & Persistence (Phase 45)
    # ============================================================================

    # Atomic OAuth Persistence (PostgreSQL upserts)
    ATOMIC_OAUTH_PERSISTENCE_ENABLED = (
        os.getenv("ATOMIC_OAUTH_PERSISTENCE_ENABLED", "true").lower() == "true"
    )

    # Rollout percentage for atomic persistence (0-100)
    ATOMIC_OAUTH_PERSISTENCE_ROLLOUT_PCT = int(
        os.getenv("ATOMIC_OAUTH_PERSISTENCE_ROLLOUT_PCT", "100")
    )

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
            logger.warning(
                "⚠️  EMERGENCY GOVERNANCE BYPASS IS ACTIVE - All governance checks are disabled!"
            )

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
    def is_integration_action_enabled(cls, tenant_id: str) -> bool:
        """
        Check if INTEGRATION_ACTION feature is enabled for tenant.

        Uses hash-based rollout for consistent assignment (COMPAT-05).
        Rollout: 0% (disabled) → 1% → 10% → 100% (fully enabled)

        Args:
            tenant_id: Tenant UUID for hash-based assignment

        Returns:
            True if integration action enabled for tenant
        """
        if not cls.INTEGRATION_ACTION_ENABLED:
            return False

        rollout_pct = cls.INTEGRATION_ACTION_ROLLOUT_PCT
        if rollout_pct >= 100:
            return True
        if rollout_pct <= 0:
            return False

        # Hash-based assignment for consistency
        import hashlib

        tenant_hash = int(hashlib.sha256(tenant_id.encode()).hexdigest(), 16)
        tenant_pct = (tenant_hash % 100) + 1  # 1-100

        return tenant_pct <= rollout_pct

    @classmethod
    def should_normalize_tenant(cls, tenant_id: str) -> bool:
        """
        Check if UUID normalization should be applied for this tenant.
        Uses hash-based rollout for consistent assignment.

        Args:
            tenant_id: Provided identifier (slug or UUID)

        Returns:
            True if normalization should be applied
        """
        if not cls.TENANT_UUID_NORMALIZATION_ENABLED:
            return False

        rollout_pct = cls.TENANT_UUID_NORMALIZATION_ROLLOUT_PCT
        if rollout_pct >= 100:
            return True
        if rollout_pct <= 0:
            return False

        # Hash-based assignment for consistency
        import hashlib
        tenant_hash = int(hashlib.sha256(tenant_id.encode()).hexdigest(), 16)
        tenant_pct = (tenant_hash % 100) + 1  # 1-100

        return tenant_pct <= rollout_pct

    @classmethod
    def is_atomic_oauth_persistence_enabled(cls, tenant_id: str) -> bool:
        """
        Check if atomic OAuth persistence is enabled for tenant.
        Uses hash-based rollout (COMPAT-05).
        """
        if not cls.ATOMIC_OAUTH_PERSISTENCE_ENABLED:
            return False

        rollout_pct = cls.ATOMIC_OAUTH_PERSISTENCE_ROLLOUT_PCT
        if rollout_pct >= 100:
            return True
        if rollout_pct <= 0:
            return False

        import hashlib
        tenant_hash = int(hashlib.sha256(tenant_id.encode()).hexdigest(), 16)
        tenant_pct = (tenant_hash % 100) + 1  # 1-100

        return tenant_pct <= rollout_pct

    @classmethod
    def is_webhook_enabled(cls, provider: str) -> bool:
        """
        Check if webhooks are enabled for a specific provider.
        Environment variable format: ENABLE_WEBHOOK_{PROVIDER_UPPERCASE}=true|false
        Defaults to True unless explicitly set to 'false'.
        """
        env_var = f"ENABLE_WEBHOOK_{provider.upper()}"
        return os.getenv(env_var, "true").lower() == "true"

    @classmethod
    def is_webhook_canary_enabled(cls, provider: str, tenant_id: str) -> bool:
        """
        Check if the webhook handler for a provider is enabled for a specific tenant
        based on a hash-based canary rollout percentage (0-100).
        Environment variable format: WEBHOOK_CANARY_PCT_{PROVIDER_UPPERCASE}=rollout_percentage
        Defaults to 100% (fully enabled).
        """
        env_var = f"WEBHOOK_CANARY_PCT_{provider.upper()}"
        pct_str = os.getenv(env_var, "100")
        try:
            rollout_pct = int(pct_str)
        except ValueError:
            rollout_pct = 100

        if rollout_pct >= 100:
            return True
        if rollout_pct <= 0:
            return False

        # Hash-based consistent assignment
        import hashlib
        combined = f"{provider}:{tenant_id}"
        hasher = int(hashlib.sha256(combined.encode()).hexdigest(), 16)
        tenant_pct = (hasher % 100) + 1  # 1-100

        return tenant_pct <= rollout_pct

    @classmethod
    def get_all_flags(cls) -> dict[str, Any]:
        """
        Get all feature flags as a dictionary.

        Useful for debugging and monitoring.

        Returns:
            Dictionary of all feature flags
        """
        flags = {}
        for attr_name in dir(cls):
            if attr_name.isupper() and not attr_name.startswith("_"):
                flags[attr_name] = getattr(cls, attr_name)
        return flags

    @classmethod
    def get_oauth_kill_switches(cls) -> dict[str, bool]:
        """
        Return current status of all OAuth kill-switches.

        Returns:
            Dictionary with kill-switch names and their active status
        """
        return {
            "DISABLE_PKCE_ENFORCEMENT": cls.DISABLE_PKCE_ENFORCEMENT,
            "DISABLE_HMAC_VALIDATION": cls.DISABLE_HMAC_VALIDATION,
            "DISABLE_STATE_CONSUMPTION": cls.DISABLE_STATE_CONSUMPTION,
            "DISABLE_TENANT_ISOLATION": cls.DISABLE_TENANT_ISOLATION,
        }

    @classmethod
    def log_oauth_kill_switch_warning(cls, kill_switch_name: str, component: str):
        """
        Log warning when OAuth kill-switch is active.

        Args:
            kill_switch_name: Name of the active kill-switch
            component: Component where enforcement is disabled
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"OAuth kill-switch ACTIVE: {kill_switch_name} - "
            f"Security enforcement disabled for {component}. "
            f"This should only be used in emergency situations. "
            f"Re-enable as soon as possible."
        )

    @classmethod
    def validate_flags(cls) -> dict[str, bool]:
        """
        Validate feature flags for potential security issues.

        Returns:
            Dictionary with validation results
        """
        issues = {}

        # Check for emergency bypass
        if cls.EMERGENCY_GOVERNANCE_BYPASS:
            issues["EMERGENCY_BYPASS_ACTIVE"] = True

        # Check for disabled governance in production
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            critical_governance = [
                "BROWSER_GOVERNANCE_ENABLED",
                "DEVICE_GOVERNANCE_ENABLED",
                "FINANCIAL_GOVERNANCE_ENABLED",
                "BILLING_GOVERNANCE_ENABLED",
            ]
            for flag in critical_governance:
                if not getattr(cls, flag):
                    issues[f"{flag}_DISABLED_IN_PRODUCTION"] = True

        return issues


# ============================================================================
# Module-level aliases for class attributes (backward compatibility)
# Many integrations import these as module-level constants rather than
# accessing them through FeatureFlags.*.
# ============================================================================

DISABLE_PKCE_ENFORCEMENT = FeatureFlags.DISABLE_PKCE_ENFORCEMENT
DISABLE_HMAC_VALIDATION = FeatureFlags.DISABLE_HMAC_VALIDATION
DISABLE_STATE_CONSUMPTION = FeatureFlags.DISABLE_STATE_CONSUMPTION
DISABLE_TENANT_ISOLATION = FeatureFlags.DISABLE_TENANT_ISOLATION


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


def get_feature_status() -> dict[str, Any]:
    """
    Get status of all feature flags for monitoring.

    Returns:
        Dictionary with feature flag statuses
    """
    return FeatureFlags.get_all_flags()


# ============================================================================
# Compliance Control-Mapping Registry (R83 #7)
# ============================================================================
# Declarative map of safety/reliability CONTROLS to the compliance-framework
# requirements they implement, so governance can enumerate "which flags
# satisfy which controls" instead of hand-maintaining
# docs/compliance/COMPLIANCE_MAPPING.md. Framework vocabulary mirrors that
# doc: SOC 2 Trust Services Criteria, EU AI Act articles, NIST AI RMF
# functions (GOVERN/MAP/MEASURE/MANAGE), GDPR.
#
# Resolvers are imported lazily by dotted path so this module never pulls
# subsystem imports at load time (feature_flags must stay leaf-safe).
# ``flag: None`` marks always-on controls (no runtime toggle) or CI-enforced
# gates. Mode-style resolvers (returning e.g. "off"/"shadow") are treated
# as enabled iff the value is not "off"/empty.

COMPLIANCE_FRAMEWORKS: tuple = ("soc2", "eu_ai_act", "nist_ai_rmf", "gdpr")

CONTROL_MAPPINGS: dict = {
    "llm.cascade_routing": {
        "title": "Cascade routing on schema-validation failure",
        "frameworks": {"soc2": ["CC7.2"], "eu_ai_act": ["art-12"], "nist_ai_rmf": ["MEASURE"]},
        "implementation": "core/llm/byok_handler.py",
        "flag": "ATOM_CASCADE_ROUTING",
        "resolver": "core.hallucination_config.is_cascade_routing_enabled",
        "evidence": "docs/compliance/COMPLIANCE_MAPPING.md",
    },
    "llm.self_consistency_voting": {
        "title": "N-sample majority vote for irreversible actions",
        "frameworks": {"soc2": ["CC7.2"], "eu_ai_act": ["art-14", "art-12"], "nist_ai_rmf": ["MEASURE"]},
        "implementation": "core/llm/self_consistency_voter.py",
        "flag": "ATOM_SELF_CONSISTENCY",
        "resolver": "core.hallucination_config.is_self_consistency_enabled",
        "evidence": "docs/architecture/SELF_CONSISTENCY_VOTER.md",
    },
    "llm.vote_hash_versioning": {
        "title": "Algo-tagged vote hashes (version, don't migrate)",
        "frameworks": {"soc2": ["CC7.2"], "eu_ai_act": ["art-12"]},
        "implementation": "core/llm/jcs.py; SelfConsistencyVote.hash_algo",
        "flag": None,
        "resolver": None,
        "evidence": "alembic/versions/20260823_scv_hash_algo.py",
    },
    "llm.usc_judge_fallback": {
        "title": "Universal Self-Consistency judge on all-distinct votes",
        "frameworks": {"nist_ai_rmf": ["MEASURE"]},
        "implementation": "core/llm/self_consistency_voter.py::_usc_judge_pick",
        "flag": "ATOM_SC_USC_FALLBACK",
        "resolver": "core.hallucination_config.is_usc_fallback_enabled",
        "evidence": "docs/agents/R83_RELIABILITY_PLAN.md",
    },
    "retrieval.memory_eval_gate": {
        "title": "recall@k regression gate on the golden set (P2.3)",
        "frameworks": {"nist_ai_rmf": ["MEASURE"], "eu_ai_act": ["art-10"]},
        "implementation": "core/memory_eval.py",
        "flag": None,  # CI-enforced gate, not a runtime toggle
        "resolver": None,
        "evidence": "tests/test_memory_eval_gate.py",
    },
    # retrieval.fusion_ab_arm REMOVED 2026-08-24: the rrf/linear arms were
    # measured inert by construction (legs LIMIT 5+5 vs a 15-entity context
    # window — reordering cannot change output; byte-identical contexts
    # verified on the hard-suite corpus). See
    # docs/agents/R83_RELIABILITY_PLAN.md #4 for the closure record.
    "prompt.datamarking": {
        "title": "Datamarking/spotlighting of untrusted prompt content",
        "frameworks": {"nist_ai_rmf": ["MAP"], "eu_ai_act": ["art-10"]},
        "implementation": "core/prompt_datamarking.py",
        "flag": "ATOM_DATAMARKING",
        "resolver": "core.prompt_datamarking.get_datamarking_mode",
        "evidence": "docs/security/PROMPT_INJECTION_DEFENSE_PLAN.md",
    },
    "security.token_encryption": {
        "title": "OAuth/integration tokens encrypted at rest (Fernet)",
        "frameworks": {"soc2": ["CC6.1"]},
        "implementation": "core/privsec/token_encryption.py",
        "flag": None,  # always-on; production fails closed without a key
        "resolver": None,
        "evidence": "docs/compliance/COMPLIANCE_MAPPING.md",
    },
    "security.outbound_gatekeeper": {
        "title": "Outbound gatekeeper: rate limits, masking, taint egress blocking",
        "frameworks": {"soc2": ["CC6.6"], "eu_ai_act": ["art-10"]},
        "implementation": "middleware/governance_middleware.py; core/data_taint_tracker.py",
        "flag": None,
        "resolver": None,
        "evidence": "docs/compliance/COMPLIANCE_MAPPING.md",
    },
    "governance.rbac_administration": {
        "title": "Role-based administration + governance config surfaces",
        "frameworks": {"nist_ai_rmf": ["GOVERN"], "soc2": ["CC6.1"]},
        "implementation": "core/rbac_service.py; api/gatekeeper_routes.py; core/edition.py",
        "flag": None,
        "resolver": None,
        "evidence": "docs/compliance/COMPLIANCE_MAPPING.md",
    },
    "governance.hitl_oversight": {
        "title": "Human-in-the-loop approval gates",
        "frameworks": {"eu_ai_act": ["art-14"], "soc2": ["CC7.3"], "nist_ai_rmf": ["MANAGE"]},
        "implementation": "core/hitl_service.py; core/proposal_service.py",
        "flag": None,
        "resolver": None,
        "evidence": "docs/agents/governance.md",
    },
    "ops.audit_trail": {
        "title": "Audit trail for agent actions, tool calls, approvals",
        "frameworks": {"eu_ai_act": ["art-12"], "soc2": ["CC7.2"]},
        "implementation": "core/audit_service.py",
        "flag": None,
        "resolver": None,
        "evidence": "docs/compliance/COMPLIANCE_MAPPING.md",
    },
    "ops.killrun": {
        "title": "KillRun immediate-stop registry for live runs",
        "frameworks": {"soc2": ["CC7.3"], "nist_ai_rmf": ["MANAGE"]},
        "implementation": "core/sandbox_killrun.py",
        "flag": None,
        "resolver": None,
        "evidence": "docs/compliance/COMPLIANCE_MAPPING.md",
    },
}

_NIST_AI_RMF_FUNCTIONS = ("GOVERN", "MAP", "MEASURE", "MANAGE")


def get_control_mappings() -> dict:
    """Copy of the declarative control registry (safe to hand to callers)."""
    return {
        cid: {
            **entry,
            "frameworks": {fw: list(reqs) for fw, reqs in entry["frameworks"].items()},
        }
        for cid, entry in CONTROL_MAPPINGS.items()
    }


def _resolve_control_enabled(entry: dict):
    """Resolve a control's live state via its dotted-path resolver.

    Returns True/False, or None when there is no resolver or it cannot be
    imported/called (audit surfaces report those separately, never guess).
    Mode-style resolvers (returning e.g. "off"/"shadow") count as enabled
    iff the value is not "off"/empty.
    """
    resolver = entry.get("resolver")
    if not resolver:
        return None
    try:
        import importlib

        module_name, fn_name = resolver.rsplit(".", 1)
        value = getattr(importlib.import_module(module_name), fn_name)()
    except Exception:
        return None
    if isinstance(value, bool):
        return value
    return value not in ("off", "", None)


def get_compliance_coverage() -> dict:
    """Live control-mapping coverage + gaps (R83 #7 audit surface).

    ``gaps.disabled_controls`` — controls whose resolver currently reports
    off (deployments should review before attesting coverage).
    ``gaps.unresolvable`` — controls with a resolver that failed to resolve.
    ``gaps.nist_ai_rmf_unmapped_functions`` — RMF functions with no mapped
    control at all.
    """
    controls: dict = {}
    disabled: list = []
    unresolvable: list = []
    for cid, entry in CONTROL_MAPPINGS.items():
        enabled = _resolve_control_enabled(entry)
        controls[cid] = {
            "title": entry["title"],
            "frameworks": dict(entry["frameworks"]),
            "implementation": entry["implementation"],
            "flag": entry["flag"],
            "enabled": enabled,
        }
        if enabled is False:
            disabled.append(cid)
        elif enabled is None and entry.get("resolver"):
            unresolvable.append(cid)

    mapped = {
        fn
        for entry in CONTROL_MAPPINGS.values()
        for fn in entry["frameworks"].get("nist_ai_rmf", [])
    }
    return {
        "frameworks": list(COMPLIANCE_FRAMEWORKS),
        "controls": controls,
        "gaps": {
            "disabled_controls": sorted(disabled),
            "unresolvable": sorted(unresolvable),
            "nist_ai_rmf_unmapped_functions": [
                fn for fn in _NIST_AI_RMF_FUNCTIONS if fn not in mapped
            ],
        },
    }
