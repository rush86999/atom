"""Dynamic promotion policy tuner: seeded → history-tuned thresholds."""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.promotion_policy_service import (  # noqa: E402
    _clamp,
    get_promotion_policy,
    seeded_policy,
)


def test_seed_defaults():
    policy = seeded_policy()
    assert policy["min_sessions"] == 3
    assert policy["min_episodes"] == 10
    assert policy["min_success_ratio"] == 0.7
    assert policy["source"] == "seeded"


def test_clamp_bounds():
    tuned = _clamp(0, 1, 0.2)  # ease below floors → clamped
    assert tuned["min_sessions"] >= 1
    assert tuned["min_episodes"] >= 3
    assert tuned["min_success_ratio"] >= 0.5
    tuned = _clamp(99, 99, 1.5)  # tighten above caps → clamped
    assert tuned["min_sessions"] <= 6
    assert tuned["min_episodes"] <= 20
    assert tuned["min_success_ratio"] <= 0.9


def test_cold_start_returns_seed_with_basis():
    db = MagicMock()
    # No promoted agents at all.
    db.query.return_value.filter.return_value.all.return_value = []
    policy = get_promotion_policy(db, "sales")
    assert policy["source"] == "seeded"
    assert "seeded" in policy["basis"]["reason"]


def _promoted_agent(db, episodes, successes):
    agent = MagicMock()
    agent.id = f"agent-{episodes}-{successes}"
    agent.status = "intern"

    def query(model):
        q = MagicMock()
        if model.__name__ == "AgentEpisode":
            q.filter.return_value.count.return_value = (
                episodes if successes is None else successes
            )
        else:
            q.filter.return_value.all.return_value = [agent]
            q.filter.return_value.first.return_value = agent
        return q

    return query


def test_tighten_on_underperforming_domain():
    os.environ["ATOM_PROMOTION_DYNAMIC_TUNING"] = "true"
    db = MagicMock()
    # 3 promoted agents, each 5 episodes but only 2 successes (0.4 < 0.7 seed).
    agents = []
    for _ in range(3):
        agent = MagicMock()
        agent.id = "a"
        agent.status = "intern"
        agents.append(agent)
    db.query.return_value.filter.return_value.all.return_value = agents

    calls = {"n": 0}

    def query(model):
        q = MagicMock()
        if model.__name__ == "AgentEpisode":
            calls["n"] += 1
            # alternate: first call = episode count, second = success count
            val = 5 if calls["n"] % 2 == 1 else 2
            q.filter.return_value.count.return_value = val
        else:
            q.filter.return_value.all.return_value = agents
        return q

    db.query = query
    policy = get_promotion_policy(db, "sales")
    assert policy["source"] == "tuned:tighten"
    assert policy["min_sessions"] == 4  # 3 + 1
    assert policy["min_episodes"] == 15  # 10 + 5
    assert policy["min_success_ratio"] == 0.75  # 0.7 + 0.05
