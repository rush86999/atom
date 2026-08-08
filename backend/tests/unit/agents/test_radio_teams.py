"""radio_teams tests — declarative team-config loader + falsification prompt.

Covers: discovery of team configs, structural validation, the coding-team
reference (4 roles incl. reviewer), and the falsification-pass prompt block
that defends against the paper's "negative-hypothesis blindness".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.agent_radio.radio_teams import (
    TeamConfig,
    falsification_prompt_block,
    list_team_names,
    load_team,
)


class TestDiscovery:
    def test_coding_team_is_listed(self):
        names = list_team_names()
        assert "coding_team" in names

    def test_missing_dir_returns_empty(self, tmp_path):
        assert list_team_names(tmp_path) == []


class TestCodingTeam:
    def test_loads_four_roles(self):
        t = load_team("coding_team")
        assert isinstance(t, TeamConfig)
        assert set(t.role_keys()) == {"planner", "researcher", "implementer", "reviewer"}

    def test_reviewer_role_present(self):
        t = load_team("coding_team")
        reviewer = t.reviewer()
        assert reviewer is not None
        assert reviewer.key == "reviewer"

    def test_roles_have_prompt_fragments(self):
        t = load_team("coding_team")
        for role in t.roles:
            assert role.prompt.strip(), f"{role.key} missing prompt fragment"

    def test_defaults_populated(self):
        t = load_team("coding_team")
        assert t.defaults.get("budget_usd") == 0.20
        assert t.defaults.get("wait_timeout_seconds") == 30

    def test_mention_graph_describes_peer_routing(self):
        t = load_team("coding_team")
        planner = next(r for r in t.roles if r.key == "planner")
        targets = [m.get("role") for m in planner.mentions]
        assert "researcher" in targets


class TestValidation:
    def test_missing_team_returns_none(self):
        assert load_team("does_not_exist") is None

    def test_invalid_structure_returns_none(self, tmp_path):
        cfg = tmp_path / "broken.yaml"
        cfg.write_text("not-a-team-mapping: 42\n")
        assert load_team("broken", teams_dir=tmp_path) is None

    def test_role_missing_key_is_dropped(self, tmp_path):
        cfg = tmp_path / "partial.yaml"
        cfg.write_text(
            "team:\n"
            "  name: partial\n"
            "  roles:\n"
            "    - key: ok\n"
            "      name: OK\n"
            "    - name: NoKey\n"
        )
        t = load_team("partial", teams_dir=tmp_path)
        assert t is not None
        assert t.role_keys() == ["ok"]


class TestFalsificationPrompt:
    def test_block_is_nonempty(self):
        block = falsification_prompt_block()
        assert isinstance(block, str) and block.strip()

    def test_block_mentions_negative_conclusions(self):
        block = falsification_prompt_block()
        # The whole point of the falsification pass (paper: Grafana case 4/9
        # rubrics required negative conclusions).
        assert "WRONG" in block or "falsif" in block.lower()
        assert "negative" in block.lower()
