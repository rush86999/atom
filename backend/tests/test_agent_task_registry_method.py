"""
Tests for AgentTaskRegistry method resolution (BUG-050).

agent_routes.py called `get_active_tasks` (async) which doesn't exist on
AgentTaskRegistry — the real method is `get_agent_tasks` (sync). The
AttributeError was swallowed by `except Exception: running_tasks = []`,
defeating the running-task guard: delete_agent deleted an executing agent,
and get_agent_status always reported is_running=False.
"""

import pytest

from core.agent_task_registry import AgentTaskRegistry


class TestAgentTaskRegistryMethod:
    def test_get_active_tasks_does_not_exist(self):
        """The method agent_routes calls must actually exist on the class."""
        assert not hasattr(AgentTaskRegistry, "get_active_tasks"), (
            "get_active_tasks exists now — the call sites in agent_routes.py "
            "may need updating if this method was added."
        )

    def test_get_agent_tasks_exists(self):
        """The real method for fetching tasks by agent_id must exist."""
        assert hasattr(AgentTaskRegistry, "get_agent_tasks"), (
            "get_agent_tasks must exist — it's the correct method to check "
            "for running tasks before deleting an agent."
        )

    def test_get_agent_tasks_returns_list(self):
        """The method must return a list (possibly empty) for any agent_id."""
        reg = AgentTaskRegistry()
        result = reg.get_agent_tasks("nonexistent-agent")
        assert isinstance(result, list)
