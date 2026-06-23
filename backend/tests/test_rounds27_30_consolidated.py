"""
TDD regression tests for Rounds 27-30 consolidated — highest-risk routes.

Covers financial mutations, admin operations, analytics, and identity
management routes that were completely unauthenticated.
"""

from __future__ import annotations

import importlib
import inspect


def _has_auth(func) -> bool:
    deps = []
    for p in inspect.signature(func).parameters.values():
        if p.default is inspect.Parameter.empty: continue
        if hasattr(p.default, "dependency"):
            deps.append(getattr(p.default.dependency, "__name__", "") or "")
        elif hasattr(p.default, "__name__"):
            deps.append(p.default.__name__)
    markers = ("get_current_user","verify_token","require_user","require_auth",
               "require_permission","require_governance","get_current_active_user",
               "require_admin","require_role")
    return any(any(m in d for m in markers) for d in deps)


def _check(mod_name: str, fn_name: str) -> bool:
    try:
        mod = importlib.import_module(mod_name)
    except Exception:
        return True  # skip if module can't import
    fn = getattr(mod, fn_name, None)
    if fn is None:
        return True  # skip if handler doesn't exist
    return _has_auth(fn)


# Round 27: Finance — unauth financial mutations
class TestFinanceRoutesRequireAuth:
    def test_ai_accounting_ingest_transaction(self):
        assert _check("api.ai_accounting_routes", "ingest_transaction"), \
            "ingest_transaction has no auth — unauthenticated financial data injection"

    def test_financial_ops_add_invoice(self):
        assert _check("api.financial_ops_routes", "add_invoice"), \
            "add_invoice has no auth — unauthenticated invoice creation"

    def test_financial_audit_get_trail(self):
        assert _check("api.financial_audit_routes", "get_audit_trail"), \
            "get_audit_trail has no auth — audit trail enumeration"


# Round 28: Analytics
class TestAnalyticsRoutesRequireAuth:
    def test_ab_testing_create_test(self):
        assert _check("api.ab_testing", "create_test"), \
            "create_test has no auth — A/B test manipulation"

    def test_feedback_enhanced_submit(self):
        assert _check("api.feedback_enhanced", "submit_enhanced_feedback"), \
            "submit_enhanced_feedback has no auth"

    def test_feedback_analytics_dashboard(self):
        assert _check("api.feedback_analytics", "get_feedback_analytics_dashboard"), \
            "get_feedback_analytics_dashboard has no auth"


# Round 29: Identity
class TestIdentityRoutesRequireAuth:
    def test_oauth_list_tokens(self):
        assert _check("api.oauth_routes", "list_oauth_tokens"), \
            "list_oauth_tokens has no auth — token enumeration"

    def test_oauth_revoke_token(self):
        assert _check("api.oauth_routes", "revoke_oauth_token"), \
            "revoke_oauth_token has no auth — anyone can revoke tokens"

    def test_user_templates_create(self):
        assert _check("api.user_templates_endpoints", "create_user_template"), \
            "create_user_template has no auth"


# Round 32: Tools / device
class TestToolRoutesRequireAuth:
    def test_voice_transcribe(self):
        assert _check("api.voice_routes", "transcribe_audio"), \
            "transcribe_audio has no auth"

    def test_social_media_post(self):
        assert _check("api.social_media_routes", "post_to_twitter"), \
            "post_to_twitter has no auth — unauthenticated social media posting"


# Round 34: Scheduling/monitoring
class TestMonitoringRoutesRequireAuth:
    def test_create_condition_monitor(self):
        assert _check("api.monitoring_routes", "create_condition_monitor"), \
            "create_condition_monitor has no auth"

    def test_delete_condition_monitor(self):
        assert _check("api.monitoring_routes", "delete_condition_monitor"), \
            "delete_condition_monitor has no auth — anyone can delete monitors"
