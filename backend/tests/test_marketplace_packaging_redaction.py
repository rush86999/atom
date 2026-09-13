"""Marketplace packaging redaction + scoping (2026-09-13).

Two review findings pinned here:

* P2-D — key-shaped secrets pasted into FREE TEXT (system_prompt, override
  rationales, descriptions) shipped to the SaaS and local buyers verbatim:
  ``strip_credentials`` only removes credential-NAMED dict keys and
  ``redact_pii`` only covered email/url/phone. The packaging text layer
  now redacts token SHAPES (sk-…, ghp_…, AKIA…, xox…, Bearer …, long
  base64ish runs after key/token/secret cue words) — conservatively.
* P3-I — packaging shipped ALL approved playbooks of the TENANT; the
  Playbook model has no owner/agent linkage, so the workspace is the
  narrowest real scope: an agent bound to a workspace ships that
  workspace's playbooks (plus legacy NULL-workspace rows), never another
  workspace's.

Pattern: service-level on the conftest scratch DB (same shape as
test_agent_marketplace_goal_runs).
"""

import os
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("TESTING", "1")

import core.database as db_mod
from core.agent_marketplace_service import AgentMarketplaceService
from core.experience_marketplace.sanitizer import (
    redact_pii, redact_secrets)
from core.models import AgentRegistry, AgentTemplate, GoalRun, Playbook, User, UserRole

WS = "ws-redact"
WS_OTHER = "ws-other-team"


@pytest.fixture(autouse=True)
def patched_session(db_session):
    original = db_mod.get_db_session

    @contextmanager
    def _test_session():
        yield db_session

    db_mod.get_db_session = _test_session
    try:
        yield db_session
    finally:
        db_mod.get_db_session = original


@pytest.fixture(autouse=True)
def silence_side_effects(monkeypatch):
    monkeypatch.setattr(
        "core.goals.goal_run_notifications.schedule_notification",
        lambda coro: coro.close() if hasattr(coro, "close") else None)
    monkeypatch.setattr(
        "core.marketplace_usage_tracker.MarketplaceUsageTracker.track_usage",
        staticmethod(lambda **kw: None))


# ------------------------------------------------------ P2-D: shapes

SK = "sk-proj-4f8aBcDeFgHiJkLmNoPqRsTuVwXyZ987654321"
GHP = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u"
AKIA = "AKIAIOSFODNN7EXAMPLE"
# Single-segment on purpose: GitHub push protection treats the 3-part
# numeric Slack form as a potentially REAL token and blocks pushes
# containing it — the redactor only needs the xox[a-z]- prefix shape.
XOX = "xoxb-ZZfakeZZfixtureZZtokenZZnotZZaZZrealZZcredential"
JWT = ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
       "eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV")
GENERIC = 'api_key: "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfGh"'


class TestSecretShapeRedaction:

    @pytest.mark.parametrize("leaked", [
        f"Use {SK} for the sandbox account",
        f"the PAT is {GHP}, rotate it monthly",
        f"AWS key {AKIA} plus the secret below",
        f"slack bot {XOX} posts to #ops",
        f"Authorization: {JWT}",
        f'config: {GENERIC} — do not commit',
    ])
    def test_known_key_shapes_are_redacted(self, leaked):
        out = redact_secrets(leaked)
        for fragment in (SK, GHP, AKIA, XOX, JWT.split(" ")[1], GENERIC.split('"')[1]):
            assert fragment not in out, out
        assert "<secret>" in out

    def test_redact_pii_includes_secret_layer(self):
        text = f"email me at a@b.co but the key {SK} matters"
        out = redact_pii(text)
        assert SK not in out and "<secret>" in out and "<email>" in out

    @pytest.mark.parametrize("prose", [
        "Please keep the secret of the trade in mind when quoting",
        "The token economy is a long game",
        "our keyword strategy for Q4",
        "the secret ingredient is patience",
        "set the timeout to 30 token intervals",
    ])
    def test_ordinary_prose_is_not_nuked(self, prose):
        assert redact_secrets(prose) == prose

    def test_short_values_after_cue_words_survive(self):
        assert redact_secrets("api key: abc123") == "api key: abc123"


# ------------------------------------------- P2-D through the packaging

@pytest.fixture
def env(db_session):
    db_session.add(User(
        id="u-owner", email="owner@example.com", first_name="Ow",
        last_name="Ner", role=UserRole.MEMBER.value, status="active"))
    db_session.add(AgentRegistry(
        id="agent-leaky", name="Leaky Agent", category="Sales",
        specialty="sales", module_path="agents.sales",
        class_name="SalesAgent", status="supervised",
        user_id="u-owner", workspace_id=WS,
        description=f"Sales agent. Sandbox creds: {AKIA}",
        configuration={
            "system_prompt": f"You are Leaky. Sandbox key {SK}. "
                             f"GitHub {GHP}. Slack {XOX}. Auth {JWT}.",
        }))
    # an ACHIEVED run whose decision log carries a leaked key in an
    # override rationale (the heuristics that ship to buyers)
    db_session.add(GoalRun(
        workspace_id=WS, tenant_id="default", goal_id="g-1",
        agent_id="agent-leaky", status="achieved",
        supervision_mode="shadow", role="sales", plan=[], cursor=None,
        decision_log=[{"ts": "2026-09-13T00:00:00+00:00",
                       "kind": "override", "decision": "REPLAN",
                       "rationale": f"use the service token {GENERIC} "
                                    f"when the API rejects you"}]))
    # P3-I playbooks: one in the agent's workspace, one in ANOTHER
    # workspace of the SAME tenant, one legacy NULL-workspace
    db_session.add(Playbook(
        tenant_id="default", workspace_id=WS, name="Own quote process",
        approval_state="approved", steps=["Research", "Send"]))
    db_session.add(Playbook(
        tenant_id="default", workspace_id=WS_OTHER,
        name="Other team's payroll process",
        approval_state="approved",
        steps=["Pay everyone from the secret account"]))
    db_session.add(Playbook(
        tenant_id="default", workspace_id=None,
        name="Legacy tenant-wide playbook",
        approval_state="approved", steps=["Old step"]))
    db_session.commit()
    return db_session


def _svc(env):
    return AgentMarketplaceService(env, saas_client=MagicMock())


class TestPackagingRedactsSecrets:

    def test_no_key_shape_reaches_the_listing(self, env):
        out = _svc(env).package_agent_for_sale("agent-leaky", price=0)
        assert out["success"] is True, out
        template = env.query(AgentTemplate).filter(
            AgentTemplate.id == out["template_id"]).one()
        payload = (str(template.configuration)
                   + str(template.anonymized_memory_bundle)
                   + str(template.description))
        for fragment in (SK, GHP, AKIA, XOX,
                         JWT.split(" ")[1],
                         GENERIC.split('"')[1]):
            assert fragment not in payload
        assert "<secret>" in str(template.configuration)

    def test_prose_in_the_prompt_survives(self, env):
        out = _svc(env).package_agent_for_sale("agent-leaky")
        template = env.query(AgentTemplate).filter(
            AgentTemplate.id == out["template_id"]).one()
        prompt = template.configuration["system_prompt"]
        assert "You are Leaky" in prompt  # ordinary persona text survives


class TestPlaybookWorkspaceScoping:

    def test_only_the_agents_workspace_playbooks_ship(self, env):
        out = _svc(env).package_agent_for_sale("agent-leaky")
        template = env.query(AgentTemplate).filter(
            AgentTemplate.id == out["template_id"]).one()
        names = [p["name"]
                 for p in template.configuration["playbooks"]]
        assert "Own quote process" in names
        assert "Legacy tenant-wide playbook" in names  # NULL = legacy scope
        assert "Other team's payroll process" not in names

    def test_workspace_less_agent_keeps_tenant_scope(self, env):
        env.add(AgentRegistry(
            id="agent-legacy", name="Legacy Agent", category="Ops",
            module_path="agents.ops", class_name="OpsAgent",
            status="supervised", user_id="u-owner", workspace_id=None,
            tenant_id="default"))
        env.commit()
        out = _svc(env).package_agent_for_sale("agent-legacy")
        template = env.query(AgentTemplate).filter(
            AgentTemplate.id == out["template_id"]).one()
        names = [p["name"]
                 for p in template.configuration["playbooks"]]
        assert "Other team's payroll process" in names  # legacy behavior
