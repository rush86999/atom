"""
Managed-agent runtime resolution tests (upstream engine port).

Mock-based unit tests: no database dependencies.
"""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from core.marketplace_runtime import (
    ManagedAgentBlockedError,
    is_managed_agent,
    render_guidance_block,
    resolve_managed_agent,
)


def make_agent(**config_extra):
    agent = Mock()
    agent.id = "agent-9"
    agent.configuration = {
        "marketplace_managed": True,
        "template_id": "tpl-1",
        "managed_version": "1.0.0",
        "capabilities": ["Search"],
        "tunables": {},
    }
    agent.configuration.update(config_extra)
    return agent


def make_template(**overrides):
    t = Mock()
    t.id = "tpl-1"
    t.version = "1.1.0"
    t.is_active = True
    t.configuration = {"system_prompt": "SECRET PROMPT", "tools": ["search"]}
    t.permission_profile = {"blocked_tools": ["shell_exec"]}
    t.anonymized_memory_bundle = {
        "heuristics": [{"error_type": "timeout", "error_code": "E408", "resolution": "retry twice"}],
        "golden_paths": [{"sequence": ["search", "create_record"], "success": True}],
    }
    for k, v in overrides.items():
        setattr(t, k, v)
    return t


def make_installation(**overrides):
    i = Mock()
    i.id = "inst-1"
    i.instantiated_agent_id = "agent-9"
    i.tenant_id = "tenant-1"
    i.is_active = True
    i.installed_version = "1.0.0"
    for k, v in overrides.items():
        setattr(i, k, v)
    return i


def db_with(template="__unset__", installation="__unset__"):
    db = Mock()

    def q(model, *a, **k):
        query = Mock()
        payload = {
            "AgentTemplate": template,
            "AgentInstallation": installation,
        }.get(model.__name__, "__unset__")
        # Chained .filter() calls return the same query (SQLAlchemy semantics)
        query.filter.return_value = query
        query.first.return_value = None if payload == "__unset__" else payload
        return query

    db.query.side_effect = q
    return db


@pytest.mark.fast
class TestResolution:
    def test_non_managed_agent_returns_none(self):
        agent = Mock()
        agent.configuration = {"system_prompt": "regular agent"}
        assert resolve_managed_agent(db_with(), agent) is None
        assert is_managed_agent(agent) is False

    def test_local_manifest_resolves_to_overrides(self):
        template = make_template()
        installation = make_installation()

        overrides = resolve_managed_agent(
            db_with(template, installation), make_agent(), tenant_id="tenant-1"
        )

        assert overrides["system_prompt"] == "SECRET PROMPT"
        # Manifest tool list is a list, so profile blocks are applied to it
        # directly (residual blocked_tools only applies to wildcard surface)
        assert overrides["allowed_tools"] == ["search"]
        assert overrides["blocked_tools"] == []
        assert overrides["guidance"]["heuristics"][0]["resolution"] == "retry twice"

    def test_missing_template_degrades_gracefully(self):
        # Upstream divergence: a missing local manifest runs with defaults
        # instead of blocking (self-hosted resilience).
        overrides = resolve_managed_agent(
            db_with(template=None, installation=make_installation()), make_agent()
        )
        assert overrides["system_prompt"] is None
        assert overrides["allowed_tools"] is None
        assert overrides["guidance"]["heuristics"] == []

    def test_deactivated_template_blocks(self):
        template = make_template(is_active=False)
        with pytest.raises(ManagedAgentBlockedError, match="deactivated"):
            resolve_managed_agent(
                db_with(template, make_installation()), make_agent()
            )

    def test_inactive_installation_blocks(self):
        with pytest.raises(ManagedAgentBlockedError, match="inactive"):
            resolve_managed_agent(
                db_with(make_template(), make_installation(is_active=False)), make_agent()
            )

    def test_lazy_version_sync(self):
        template = make_template()
        installation = make_installation(installed_version="1.0.0")
        db = db_with(template, installation)

        resolve_managed_agent(db, make_agent(), tenant_id="tenant-1")

        assert installation.installed_version == "1.1.0"
        assert installation.last_synced_version == "1.1.0"


@pytest.mark.fast
class TestGuidanceRendering:
    def test_render_contains_playbook_and_sequences(self):
        block = render_guidance_block(
            {
                "heuristics": [
                    {"error_type": "timeout", "error_code": "E408", "resolution": "retry twice"}
                ],
                "golden_paths": [["search", "create_record"]],
            }
        )
        assert "PROVEN PLAYBOOK" in block
        assert "When timeout [E408]: retry twice" in block
        assert "search -> create_record" in block

    def test_render_empty_when_no_guidance(self):
        assert render_guidance_block(None) == ""
