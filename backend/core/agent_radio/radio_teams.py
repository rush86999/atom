"""Loader for declarative lateral-team configs (config/lateral_teams/*.yaml).

A team definition lists roles + the @mention graph + a system-prompt fragment
per role, plus per-thread defaults. Teams are reference templates — Atom's
fleet stays single-agent by default and only assembles a team when a task
crosses a responsibility breakpoint (``radio_breaker``).

YAML is optional: if PyYAML is unavailable, loading degrades gracefully
(returns ``None``) so the radio layer never hard-fails on a missing optional
dependency. Configs are validated structurally and never ``exec``'d.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/core/agent_radio -> repo root
_DEFAULT_TEAMS_DIR = _REPO_ROOT / "config" / "lateral_teams"


@dataclass
class TeamRole:
    key: str
    name: str
    responsibility: str = ""
    prompt: str = ""
    mentions: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class TeamConfig:
    name: str
    description: str = ""
    roles: List[TeamRole] = field(default_factory=list)
    defaults: Dict[str, Any] = field(default_factory=dict)

    def role_keys(self) -> List[str]:
        return [r.key for r in self.roles]

    def reviewer(self) -> Optional[TeamRole]:
        """The reviewer role (carries the falsification pass)."""
        return next((r for r in self.roles if r.key == "reviewer"), None)


def _try_import_yaml():
    try:
        import yaml  # type: ignore

        return yaml
    except Exception:  # pragma: no cover - optional dep
        return None


def _validate(team_dict: Dict[str, Any]) -> Optional["TeamConfig"]:
    """Structurally validate a parsed team dict; return a TeamConfig or None."""
    if not isinstance(team_dict, dict) or not isinstance(team_dict.get("team"), dict):
        logger.warning("radio team config: missing top-level 'team' mapping")
        return None
    t = team_dict["team"]
    name = t.get("name")
    if not name:
        logger.warning("radio team config: team.name is required")
        return None
    roles: List[TeamRole] = []
    for r in t.get("roles", []) or []:
        if not isinstance(r, dict) or not r.get("key") or not r.get("name"):
            logger.warning(f"radio team config: role missing key/name: {r}")
            continue
        roles.append(
            TeamRole(
                key=str(r["key"]),
                name=str(r["name"]),
                responsibility=str(r.get("responsibility", "")).strip(),
                prompt=str(r.get("prompt", "")).strip(),
                mentions=list(r.get("mentions", []) or []),
            )
        )
    if not roles:
        logger.warning(f"radio team config '{name}': no valid roles")
        return None
    return TeamConfig(
        name=str(name),
        description=str(t.get("description", "")).strip(),
        roles=roles,
        defaults=dict(t.get("defaults", {}) or {}),
    )


def load_team(name: str, teams_dir: Optional[Path] = None) -> Optional[TeamConfig]:
    """Load ``<teams_dir>/<name>.yaml`` (or .yml). Returns None on any failure."""
    yaml = _try_import_yaml()
    if yaml is None:
        logger.debug("radio team loader: PyYAML unavailable; skipping team config")
        return None
    base = Path(teams_dir) if teams_dir else _DEFAULT_TEAMS_DIR
    for ext in (".yaml", ".yml"):
        path = base / f"{name}{ext}"
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    parsed = yaml.safe_load(fh) or {}
                return _validate(parsed)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"radio team loader: failed to parse {path}: {e}")
                return None
    logger.debug(f"radio team loader: no config for team '{name}' in {base}")
    return None


def list_team_names(teams_dir: Optional[Path] = None) -> List[str]:
    """Available team config stems in the teams dir (without extension)."""
    base = Path(teams_dir) if teams_dir else _DEFAULT_TEAMS_DIR
    if not base.is_dir():
        return []
    names: List[str] = []
    for p in sorted(base.iterdir()):
        if p.suffix in (".yaml", ".yml") and p.is_file():
            names.append(p.stem)
    return names


def falsification_prompt_block() -> str:
    """The falsification-pass prompt the Reviewer role always includes.

    Paper finding: "Passive awareness can distribute an idea that somebody
    develops. It cannot supply a conception that never appears anywhere in the
    team." The Reviewer explicitly enumerates negative conclusions to defend
    against shared blind spots.
    """
    return (
        "[FALSIFICATION PASS]\n"
        "For each claim or rubric item, ask: what would prove this WRONG? Then check it.\n"
        "Explicitly enumerate what was NOT observed / NOT verified. If a rubric requires\n"
        "a negative conclusion (e.g. 'X did not auto-select', 'no error was logged'),\n"
        "verify the negative directly — absence of evidence is never evidence of absence.\n"
    )
