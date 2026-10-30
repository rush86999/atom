# -*- coding: utf-8 -*-
"""The one product-surface configuration.

The core release is a company-data + trained-agent workspace. These tests
lock the parts that must never drift: only the six core surfaces are exposed,
deferred routes are denied on direct access, supervisors keep the approval
safeguard, the full profile restores everything, and worker defaults are off.
"""
import importlib

import pytest

import core.product_profile as pp


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("ATOM_PRODUCT_PROFILE", raising=False)
    monkeypatch.delenv("ATOM_PRODUCT_PROFILE_PATH", raising=False)
    monkeypatch.setattr(pp, "_PROFILE_CACHE", None)
    yield
    monkeypatch.setattr(pp, "_PROFILE_CACHE", None)


def test_core_profile_exposes_only_the_agreed_surfaces():
    doc = pp.profile_document()
    assert doc["profile"] == "core"
    assert set(doc["enabled_capabilities"]) == {
        "chat", "documents", "canvas", "agents", "activity", "settings",
        "approvals",
    }
    for deferred in (
        "tasks", "boards", "automations", "marketplace", "command_centers",
        "business_dashboards", "productivity", "governance", "connectors",
        "team_chat", "search",
    ):
        assert deferred in doc["deferred_capabilities"]


@pytest.mark.parametrize("path", [
    "/chat", "/documents", "/canvas", "/canvas/abc", "/agents",
    "/goal-runs", "/goal-runs/run-1", "/execution-history",
    "/settings", "/settings/ai", "/settings/local-models",
])
def test_core_routes_are_enabled(path):
    assert pp.route_enabled(path) is True


@pytest.mark.parametrize("path", [
    "/tasks", "/boards", "/automations", "/workflows/builder",
    "/workflows/schedule", "/scheduling", "/marketplace", "/sales",
    "/marketing", "/finance", "/analytics", "/dashboards/projects",
    "/calendar", "/health", "/voice", "/admin/users", "/audit-trail",
    "/dev-studio", "/integrations", "/team-chat", "/system-status",
    "/settings/harness-evolution", "/search", "/some-new-page",
])
def test_deferred_or_unknown_routes_are_not_exposed(path):
    assert pp.route_enabled(path) is False


def test_approvals_stay_available_as_a_safeguard_but_not_in_nav():
    meta = pp.profile_document()["capabilities"]["approvals"]
    assert meta["enabled"] is True
    assert meta["nav"] is False
    assert meta["min_role"] == "team_lead"
    assert pp.for_role("approvals", role_level=4) is True
    assert pp.for_role("approvals", role_level=3) is False


def test_full_profile_restores_deferred_capabilities(monkeypatch):
    monkeypatch.setenv("ATOM_PRODUCT_PROFILE", "full")
    monkeypatch.setattr(pp, "_PROFILE_CACHE", None)
    doc = pp.profile_document()
    assert doc["profile"] == "full"
    assert "tasks" in doc["enabled_capabilities"]
    assert pp.route_enabled("/automations") is True
    assert pp.deferred_capabilities() == []


def test_core_worker_defaults_are_disabled(monkeypatch):
    for key in ("ENABLE_SCHEDULER", "ENABLE_INGESTION_SYNC",
                "ATOM_AGENT_EVOLUTION_ENABLED"):
        monkeypatch.delenv(key, raising=False)
    applied = pp.apply_runtime_defaults()
    assert applied["ENABLE_SCHEDULER"] == "false"
    assert applied["ENABLE_INGESTION_SYNC"] == "false"
    assert applied["ATOM_AGENT_EVOLUTION_ENABLED"] == "false"


def test_full_profile_does_not_force_worker_flags(monkeypatch):
    monkeypatch.setenv("ATOM_PRODUCT_PROFILE", "full")
    monkeypatch.setattr(pp, "_PROFILE_CACHE", None)
    assert pp.apply_runtime_defaults() == {}


def test_route_capability_uses_longest_prefix():
    assert pp.route_capability("/settings/harness-evolution") == "governance"
    assert pp.route_capability("/settings/ai") == "settings"
    assert pp.route_capability("/dashboard/forensics") == "governance"
    assert pp.route_capability("/dashboard") == "chat"
    assert pp.route_capability("/assignments") == "activity"
