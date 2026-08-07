"""TDD bug-hunt: NodeJsSkillAdapter.install_npm_dependencies script-analyzer args.

`analyze_package_scripts` takes a single positional arg (packages); the adapter
passed two (packages, package_manager) → TypeError on every Node.js skill
execution with packages.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_analyze_package_scripts_called_with_single_arg(monkeypatch):
    import core.skill_adapter as sa
    from core.npm_script_analyzer import NpmScriptAnalyzer

    adapter = sa.NodeJsSkillAdapter(
        skill_id="skill-1", code="", node_packages=[], package_manager="npm", agent_id="agent-1"
    )
    adapter._governance = MagicMock()
    adapter._installer = MagicMock()
    adapter._installer.install_packages.return_value = {"success": True, "image_tag": "img:1"}

    calls: dict = {}
    orig = NpmScriptAnalyzer.analyze_package_scripts

    def spy(self, *args, **kwargs):
        calls["args"] = args
        return {"malicious": False, "warnings": [], "details": [], "scripts_found": []}

    monkeypatch.setattr(NpmScriptAnalyzer, "analyze_package_scripts", spy)
    engine = MagicMock()
    conn = MagicMock()
    monkeypatch.setattr("sqlalchemy.create_engine", lambda url: engine)
    monkeypatch.setattr(
        "sqlalchemy.orm.sessionmaker", lambda bind: MagicMock(return_value=conn)
    )

    result = adapter.install_npm_dependencies()

    assert result["success"] is True
    assert len(calls["args"]) == 1, (
        "analyze_package_scripts must be called with packages only, "
        f"got {len(calls['args'])} positional args"
    )
    conn.close.assert_called_once()


def test_analyze_package_scripts_malicious_blocks_install(monkeypatch):
    import core.skill_adapter as sa
    from core.npm_script_analyzer import NpmScriptAnalyzer

    adapter = sa.NodeJsSkillAdapter(
        skill_id="skill-1", code="", node_packages=[], package_manager="npm", agent_id="agent-1"
    )
    adapter._governance = MagicMock()
    adapter._installer = MagicMock()

    def spy(self, *args, **kwargs):
        return {
            "malicious": True,
            "warnings": ["postinstall script detected"],
            "details": [],
            "scripts_found": [],
        }

    monkeypatch.setattr(NpmScriptAnalyzer, "analyze_package_scripts", spy)
    monkeypatch.setattr("sqlalchemy.create_engine", lambda url: MagicMock())
    monkeypatch.setattr(
        "sqlalchemy.orm.sessionmaker", lambda bind: MagicMock(return_value=MagicMock())
    )

    result = adapter.install_npm_dependencies()

    assert result["success"] is False
    adapter.installer.install_packages.assert_not_called()


def test_community_skill_tool_constructs_with_kwargs():
    """Regression: without langchain installed, the fallback BaseTool stub was
    a plain class, so CommunitySkillTool() took no arguments — community skills
    were unconstructable in langchain-less environments."""
    import core.skill_adapter as sa

    tool = sa.CommunitySkillTool(
        name="my-skill",
        description="test skill",
        skill_id="skill-1",
        skill_type="prompt_only",
        skill_content="Answer the query",
    )
    assert tool.skill_id == "skill-1"
    assert tool.name == "my-skill"


def test_create_community_tool_factory_works_without_langchain():
    import core.skill_adapter as sa

    tool = sa.create_community_tool(
        {
            "name": "skill-a",
            "description": "A skill",
            "skill_type": "prompt_only",
            "skill_content": "Do the thing",
        }
    )
    assert tool.name == "skill-a"
    assert tool.skill_type == "prompt_only"
