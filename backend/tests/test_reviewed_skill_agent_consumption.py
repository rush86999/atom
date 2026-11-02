"""Ordinary-work consumption of a reviewed prompt skill.

The accepted lifecycle proved SkillRetrievalService directly. This control
goes through the real GenericAgent prompt-injection path and a new session,
and proves the generated executable code is not present.
"""
from __future__ import annotations

import pytest

from tests.test_reviewed_improvement_apply import (  # noqa: F401
    _apply,
    _candidate,
    env,
)

REQUEST = "outlook customer email search"


def _agent(env, db):
    from core.generic_agent import GenericAgent

    model = db.query(type(env["agent"])).filter(
        type(env["agent"]).id == env["agent"].id).one()
    agent = GenericAgent(model, workspace_id=env["workspace"].id)
    agent.tenant_id = env["tenant"].id
    return agent


def test_promoted_skill_reaches_the_real_agent_prompt(env, monkeypatch):  # noqa: F811
    candidate = _candidate(env)
    applied = _apply(env, candidate)
    assert applied["status"] == "promoted"

    monkeypatch.setattr("core.database.get_db_session", env["factory"])
    agent = _agent(env, env["db"])
    block = agent._retrieve_skill_instructions(REQUEST)
    assert "repair_outlook_search" in block
    assert "repair outlook customer email search failures" in block
    assert "def repair_outlook_search" not in block

    workspace_block = agent._workspace_context_block()
    assert "WORKSPACE-ASSIGNED SKILLS" in workspace_block
    assert "repair_outlook_search" in workspace_block


def test_promoted_skill_is_consumed_after_a_new_session(env, monkeypatch):  # noqa: F811
    candidate = _candidate(env)
    _apply(env, candidate)
    monkeypatch.setattr("core.database.get_db_session", env["factory"])

    fresh = env["factory"]()
    try:
        agent = _agent(env, fresh)
        block = agent._retrieve_skill_instructions(REQUEST)
        assert "repair_outlook_search" in block
        assert "def repair_outlook_search" not in block
    finally:
        fresh.close()


def test_promoted_skill_does_not_leak_to_another_workspace(env):  # noqa: F811
    from core.models import Workspace
    from core.skill_retrieval_service import SkillRetrievalService

    candidate = _candidate(env)
    _apply(env, candidate)
    other = Workspace(
        id="other-consumer-workspace", name="Other",
        tenant_id=env["tenant"].id)
    env["db"].add(other)
    env["db"].commit()
    block = SkillRetrievalService().retrieve_top_skills(
        env["db"], env["tenant"].id, other.id, REQUEST)
    assert block == ""
    own = SkillRetrievalService().retrieve_top_skills(
        env["db"], env["tenant"].id, env["workspace"].id, REQUEST)
    assert "repair_outlook_search" in own


def test_meta_agent_consumes_the_promoted_skill(env, monkeypatch):  # noqa: F811
    candidate = _candidate(env)
    _apply(env, candidate)
    import core.atom_meta_agent as meta

    monkeypatch.setattr(meta, "SessionLocal", env["factory"])
    agent = object.__new__(meta.AtomMetaAgent)
    agent.workspace_id = env["workspace"].id
    agent.tenant_id = env["tenant"].id
    block = agent._retrieve_skill_instructions(REQUEST)
    assert "repair_outlook_search" in block
    assert "def repair_outlook_search" not in block
