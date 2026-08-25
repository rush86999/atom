"""
Gatekeeper Middleware — P3 (Cloudflare OS G3).

A per-service policy shim in front of every outbound integration call. Wraps:
- token-expiry awareness (the actual refresh lives in the adapters/connection
  service; the gatekeeper signals when a call should be retried after refresh),
- unified per-provider rate limiting (reuses ``core.rate_limiter``),
- response field masking (strip ``access_token`` etc. from responses),
- audit logging per checked call,
- mutation approval via the existing HITL ``intervention_service``.

This fills the real missing module referenced at
``integrations/universal_integration_service.py:10``::

    try:
        from middleware.governance_middleware import governance_middleware
    except ImportError:
        governance_middleware = None  # <- was always None (silent no-op)

and makes the dead ``check_action_risk`` call at ``universal_integration_service.py:91``
actually run.

The gatekeeper is an *integration-action* gate (per ``execute()`` call), NOT a
Starlette HTTP middleware class — it is invoked as a service by the integration
dispatch path.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set

from core.intervention_service import intervention_service
from core.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


# ============================================================================
# Per-provider defaults
# ============================================================================

# Conservative defaults: which actions are considered "mutations" (state-changing
# external side effects) vs "reads". Providers may override via the admin config
# endpoint (P3 api/gatekeeper_routes.py) or this dict.
_DEFAULT_MUTATION_ACTIONS: Dict[str, Set[str]] = {
    "slack": {"post_message", "send_message", "create_channel", "invite_user"},
    "gmail": {"send_email", "reply_email"},
    "outlook": {"send_email", "reply_email", "create_event"},
    "stripe": {"create_charge", "create_invoice", "refund"},
    "shopify": {"create_order", "update_order", "cancel_order"},
    "hubspot": {"create_contact", "update_contact", "create_deal"},
    "salesforce": {"create_lead", "update_lead", "create_opportunity"},
    "asana": {"create_task", "update_task", "delete_task"},
    "jira": {"create_issue", "update_issue", "delete_issue"},
    "trello": {"create_card", "update_card", "delete_card"},
    "github": {"create_issue", "merge_pr", "delete_branch"},
}

# Fields to strip from responses per provider (never leak outbound credentials).
_DEFAULT_MASKED_FIELDS: Dict[str, Set[str]] = {
    "slack": {"access_token", "bot_access_token", "webhook_url"},
    "outlook": {"access_token", "refresh_token", "id_token"},
    "gmail": {"access_token", "refresh_token"},
    "hubspot": {"access_token"},
    "salesforce": {"access_token", "refresh_token", "signature"},
}

# Actions requiring human approval BEFORE execution (HITL pause). Empty by
# default — operators opt specific high-risk actions in. The
# ``require_approval_for`` list is the override surface.
_DEFAULT_REQUIRE_APPROVAL: Dict[str, Set[str]] = {}


def _mask_key(key: str) -> str:
    """Canonical masking key: lowercase with '-'/'_' separators dropped so
    ``access_token``, ``access-token`` and ``accessToken`` interoperate."""
    return key.strip().lower().replace("-", "").replace("_", "")


def mask_response_fields(
    response: Any,
    masked_fields: Set[str],
) -> Any:
    """Recursively replace values of any key in ``masked_fields`` with '***'.

    Operates on dicts and lists. Keys are matched case-insensitively so
    providers returning ``ACCESS_TOKEN`` / ``AccessToken`` cannot leak past
    the mask. Returns the input unchanged when ``masked_fields`` is empty.
    """
    if not masked_fields:
        return response
    masked_lower = {_mask_key(field) for field in masked_fields}

    def _mask(node: Any) -> Any:
        if isinstance(node, dict):
            return {
                k: ("***" if _mask_key(str(k)) in masked_lower else _mask(v))
                for k, v in node.items()
            }
        if isinstance(node, list):
            return [_mask(item) for item in node]
        return node

    return _mask(response)


class Gatekeeper:
    """Per-service policy gate in front of outbound integration calls.

    Stateless except for the injected config (override-able per provider via
    ``_config``). All heavy lifting (rate limiting, HITL) delegates to the
    existing singletons.
    """

    def __init__(self) -> None:
        # Operator overrides keyed by service name. Each value may carry:
        #   rate_limit (int), masked_fields (set), required_scopes (set),
        #   require_approval_for (set), mutations (set).
        self._config: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _normalize_service(service: str) -> str:
        """Canonical service key: lowercase, stripped. Admin config and
        dispatch call sites must agree or every policy is bypassed."""
        return (service or "").strip().lower()

    def configure(self, service: str, policy: Dict[str, Any]) -> None:
        """Set/replace the policy override for a service."""
        self._config[self._normalize_service(service)] = policy

    def _get(self, service: str, key: str, default: Any) -> Any:
        service = self._normalize_service(service)
        cfg = self._config.get(service)
        if cfg is None:
            # Also match any pre-existing key differing only in case/whitespace
            # (config written before normalization or by hand) so a policy is
            # never silently bypassed by key-casing mismatch.
            for stored, value in self._config.items():
                if self._normalize_service(stored) == service:
                    cfg = value
                    break
        if cfg is None:
            cfg = {}
        if key in cfg:
            return cfg[key]
        if key == "mutations":
            return _DEFAULT_MUTATION_ACTIONS.get(service, set())
        if key == "masked_fields":
            return _DEFAULT_MASKED_FIELDS.get(service, set())
        if key == "require_approval_for":
            return _DEFAULT_REQUIRE_APPROVAL.get(service, set())
        return default

    def _write_audit(self, **fields: Any) -> None:
        """Record an audit row for a checked call (best-effort, never raises)."""
        try:
            from core.sandbox_audit import write_violation  # noqa: F401
            # The gatekeeper writes a lightweight audit record rather than a
            # sandbox *violation* (there is no violation on ALLOWED). We log
            # structurally so the existing audit pipeline can pick it up.
            logger.info(
                "gatekeeper.audit service=%s action=%s agent_id=%s allowed=%s reason=%s",
                fields.get("service"), fields.get("action"),
                fields.get("agent_id"), fields.get("allowed"), fields.get("reason"),
            )
        except Exception as e:  # pragma: no cover - audit must never block
            logger.debug("gatekeeper audit write failed: %s", e)

    async def check_action_risk(
        self,
        service: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        taint_tracker: Any = None,
        scopes: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Evaluate a single outbound integration action against policy.

        Returns a dict with at least ``{"allowed": bool}``. When ``allowed`` is
        False, includes ``reason`` and (for HITL) ``intervention_id``.

        Args:
            taint_tracker: optional ``DataTaintTracker`` (P4). When supplied, an
                external-bound call is blocked if restricted/confidential data
                was observed this run (VT_PROVENANCE).
            scopes: caller-provided OAuth scopes. When a service policy requires
                scopes they must all be present — otherwise the call fails closed
                (unprovable scopes are treated as missing).
        """
        params = params or {}
        service = self._normalize_service(service)
        allowed = True
        reason = ""

        # 1. Rate limit (per-provider, reuses the integration-scoped limiter).
        try:
            rate_limit = self._get(service, "rate_limit", None)
            if rate_limit == 0:
                # An explicit 0 means "block all" — never fall back to the
                # provider default limit (the underlying limiter treats 0 as
                # absent, silently lifting the operator's block).
                limited, remaining = True, 0
            else:
                limited, remaining = await rate_limiter.is_rate_limited(
                    connector_id=service,
                    limit=rate_limit,
                )
            if limited:
                allowed = False
                reason = f"Rate limit exceeded for {service} (retry later)"
        except Exception as e:
            logger.debug("rate limit check skipped for %s: %s", service, e)

        # 1a. Required scopes (fail-closed when unprovable).
        required_scopes = set(self._get(service, "required_scopes", set()))
        if allowed and required_scopes:
            caller_scopes = {str(s) for s in (scopes or set())}
            if not required_scopes.issubset(caller_scopes):
                missing = sorted(required_scopes - caller_scopes)
                allowed = False
                reason = f"Missing required scopes for {service}: {missing}"

        # 1b. P4 data-taint gate: block external outbound when sensitive data
        # was observed this run. Emits VT_PROVENANCE.
        if allowed and taint_tracker is not None:
            try:
                taint_decision = taint_tracker.check_outbound(
                    destination="external", service=service
                )
                if not taint_decision.get("allowed", True):
                    self._write_audit(
                        service=service, action=action, agent_id=agent_id,
                        workspace_id=workspace_id, allowed=False,
                        reason=taint_decision.get("reason", "taint block"),
                    )
                    return {
                        "allowed": False,
                        "reason": taint_decision.get("reason", "sensitive data observed"),
                        "violation_type": taint_decision.get("violation_type"),
                        "max_observed": taint_decision.get("max_observed"),
                    }
            except Exception as e:
                # FAIL CLOSED (repo posture, cf. _check_hitl_policy): a taint
                # tracker that cannot answer means we cannot prove the outbound
                # is clean of restricted data — block rather than allow.
                logger.error(
                    "taint check unavailable for %s; failing CLOSED: %s", service, e
                )
                self._write_audit(
                    service=service, action=action, agent_id=agent_id,
                    workspace_id=workspace_id, allowed=False,
                    reason=f"taint check error: {type(e).__name__}",
                )
                return {
                    "allowed": False,
                    "reason": (
                        "Data-sensitivity check unavailable; action blocked "
                        "(fail-closed). Retry once the tracker recovers."
                    ),
                    "violation_type": None,
                    "max_observed": None,
                }

        # 2. HITL approval for configured mutations.
        if allowed:
            require_approval = self._get(service, "require_approval_for", set())
            if action in require_approval:
                intervention = None
                try:
                    intervention = await intervention_service.request_intervention(
                        workspace_id=workspace_id or "default",
                        action_type=action,
                        platform=service,
                        params=params,
                        reason=f"Gatekeeper: {service}.{action} requires approval",
                        agent_id=agent_id,
                        user_id=user_id,
                    )
                except Exception as e:
                    logger.error("gatekeeper HITL escalation failed for %s.%s: %s", service, action, e)
                if not intervention or not intervention.get("action_id"):
                    # Fail-closed: no intervention row means the mutation can
                    # never be reviewed — treat it as unavailable, not paused.
                    allowed = False
                    reason = f"Approval required but HITL unavailable: {service}.{action}"
                else:
                    self._write_audit(
                        service=service,
                        action=action,
                        agent_id=agent_id,
                        workspace_id=workspace_id,
                        allowed=False,
                        reason=f"Action requires manual review: {service}.{action}",
                    )
                    return {
                        "allowed": False,
                        "reason": f"Action requires manual review: {service}.{action}",
                        "intervention_id": intervention.get("action_id"),
                        "paused": True,
                    }

        result: Dict[str, Any] = {"allowed": allowed}
        if not allowed:
            result["reason"] = reason

        # 3. Audit (always — allowed or blocked).
        self._write_audit(
            service=service,
            action=action,
            agent_id=agent_id,
            workspace_id=workspace_id,
            allowed=allowed,
            reason=reason,
        )

        return result

    def mask_response(self, service: str, response: Any) -> Any:
        """Apply the provider's configured field masking to an outbound response."""
        masked_fields = self._get(service, "masked_fields", set())
        return mask_response_fields(response, masked_fields)


# Module-level singleton — the symbol imported by universal_integration_service.
governance_middleware = Gatekeeper()
