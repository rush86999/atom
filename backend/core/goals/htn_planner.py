"""HTN-style goal decomposition from reusable methods (gaps B5/B6).

The legacy decomposition paths were keyword templates ("deal"→4 subtasks)
or one-shot free-form LLM calls, and workflow_templates/*.json all shipped
with empty ``steps: []``. This planner treats filled-in templates as HTN
*methods* — reusable recipes — and validates the resulting plan with the
fleet's DAG engine (cycle detection + topological parallel execution
groups), reusing the only real DAG machinery in the codebase instead of
adding another.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "workflow_templates"


class HTNPlanner:
    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = Path(template_dir) if template_dir else DEFAULT_TEMPLATE_DIR

    # ------------------------------------------------------------- templates

    def list_methods(self) -> List[Dict[str, Any]]:
        """Load usable HTN methods (templates with non-empty steps)."""
        methods: List[Dict[str, Any]] = []
        if not self.template_dir.is_dir():
            return methods
        for path in sorted(self.template_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            steps = data.get("steps") or []
            if not steps:
                continue  # legacy empty templates are not usable methods
            methods.append({
                "template_id": data.get("template_id", path.stem),
                "name": data.get("name", path.stem),
                "description": data.get("description", ""),
                "tags": data.get("tags", []),
                "keywords": [k.lower() for k in
                             ([data.get("name", ""), data.get("description", "")] + data.get("tags", []))
                             if isinstance(k, str)],
                "steps": steps,
            })
        return methods

    def select_method(self, goal_text: str) -> Optional[Dict[str, Any]]:
        """Pick the method whose keywords best overlap the goal text."""
        if not goal_text:
            return None
        needle = goal_text.lower()
        best, best_score = None, 0
        for method in self.list_methods():
            score = sum(1 for kw in method["keywords"] if kw and kw in needle)
            if score > best_score:
                best, best_score = method, score
        return best

    # -------------------------------------------------------------- planning

    def decompose(self, goal_text: str, template_id: Optional[str] = None) -> Dict[str, Any]:
        """Decompose a goal into a dependency-validated subtask plan.

        Returns {plan, method, subtasks, execution_groups, cycles}. When no
        method matches, falls back to the generic 4-phase plan (still DAG
        validated) so callers always receive an executable structure.
        """
        methods = self.list_methods()
        method = None
        if template_id:
            method = next((m for m in methods if m["template_id"] == template_id), None)
        if method is None:
            method = self.select_method(goal_text)

        if method:
            steps = method["steps"]
            method_name = method["name"]
        else:
            method_name = "generic_fallback"
            steps = [
                {"id": "clarify", "name": "Clarify scope and success criteria", "depends_on": [], "step_type": "action"},
                {"id": "execute", "name": "Execute primary work stream", "depends_on": ["clarify"], "step_type": "action"},
                {"id": "verify", "name": "Verify outcome against criteria", "depends_on": ["execute"], "step_type": "action"},
                {"id": "report", "name": "Report completion and evidence", "depends_on": ["verify"], "step_type": "action"},
            ]

        subtasks = [
            {
                "id": str(s.get("id") or s.get("step_id") or f"step_{i}"),
                "title": s.get("name", f"step_{i}"),
                "description": s.get("description", ""),
                "depends_on": list(s.get("depends_on") or []),
                "step_type": s.get("step_type", "action"),
                "service": s.get("service"),
                "action": s.get("action"),
            }
            for i, s in enumerate(steps)
        ]

        cycles = self._validate_dag(subtasks)
        execution_groups = self._execution_groups(subtasks) if not cycles else []

        return {
            "method": method_name,
            "matched": method is not None,
            "subtasks": subtasks,
            "execution_groups": execution_groups,
            "cycles": cycles,
        }

    # ------------------------------------------------------------ dag utils

    @staticmethod
    def _validate_dag(subtasks: List[Dict[str, Any]]) -> List[List[str]]:
        """Cycle detection via the fleet DAG engine when available, with a
        dependency-free DFS fallback."""
        try:
            from core.fleet_orchestration.task_decomposition_service import SubTask
            from core.fleet_orchestration.dependency_graph_service import (
                build_graph, validate_cycles,
            )
            fleet_tasks = [
                SubTask(id=t["id"], description=t["title"], depends_on=t["depends_on"])
                for t in subtasks
            ]
            return validate_cycles(build_graph(fleet_tasks)) or []
        except Exception:
            ids = {t["id"] for t in subtasks}
            graph = {t["id"]: [d for d in t["depends_on"] if d in ids] for t in subtasks}
            WHITE, GRAY, BLACK = 0, 1, 2
            color = {n: WHITE for n in graph}
            cycles: List[List[str]] = []

            def dfs(node: str, stack: List[str]) -> None:
                color[node] = GRAY
                stack.append(node)
                for nxt in graph.get(node, []):
                    if color.get(nxt) == GRAY:
                        cycles.append(stack[stack.index(nxt):] + [nxt])
                    elif color.get(nxt) == WHITE:
                        dfs(nxt, stack)
                stack.pop()
                color[node] = BLACK

            for node in list(graph):
                if color[node] == WHITE:
                    dfs(node, [])
            return cycles

    @staticmethod
    def _execution_groups(subtasks: List[Dict[str, Any]]) -> List[List[str]]:
        """Kahn topological levels — tasks in the same group can run in parallel."""
        ids = {t["id"] for t in subtasks}
        deps = {t["id"]: {d for d in t["depends_on"] if d in ids} for t in subtasks}
        groups: List[List[str]] = []
        remaining = set(ids)
        while remaining:
            done = {x for g in groups for x in g}
            ready = sorted(n for n in remaining if not deps[n] - done)
            if not ready:  # cycle guard — should not happen post-validation
                break
            groups.append(ready)
            remaining -= set(ready)
        return groups
