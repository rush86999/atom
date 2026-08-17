"""Machine-checkable success criteria (gaps B2, B7 — the "knowledge spine").

Previously ``Objective.success_criteria`` was a ``List[str]`` stored and
never evaluated, and ``definition_of_done`` required a Python callable with
zero production injectors. This evaluator turns criteria into structured
predicates evaluated against the knowledge graph, board state, the agent
loop state, or workspace metrics — closing the loop between goal
satisfaction and the GraphRAG store.

Criterion schema (JSON dicts, safe to persist and to send over the wire):

- {"type": "graph_edge_exists", "source": {"name": .., "type": ..},
   "relation": "OWNS", "target": {"name": .., "type": ..}}
- {"type": "entity_exists", "name": "..", "type": "Deal"}
- {"type": "board_task_status", "task_id": ".." | "title": "..", "status": "DONE"}
- {"type": "state_equals"|"state_contains", "key": "final_answer", "value": ..}
- {"type": "numeric_compare", "left": 5 | {"$state": "steps_done"},
   "op": ">=|<=|==|!=|>|<", "right": 3}
- {"type": "metric_gte", "metric": "graph_node_count"|"graph_edge_count"|
   "verified_edge_count"|"goal_achievement_rate", "target": 100}
- {"type": "all_of"|"any_of", "criteria": [ ... ]}
- {"type": "manual", "note": ".."} — never auto-satisfied; human sign-off.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CriterionResult:
    criterion: Dict[str, Any]
    satisfied: bool
    detail: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion": self.criterion,
            "satisfied": self.satisfied,
            "detail": self.detail,
            "error": self.error,
        }


def _norm(name: Optional[str]) -> Optional[str]:
    return name.strip().lower() if isinstance(name, str) and name.strip() else None


class CriterionEvaluator:
    """Evaluates structured criteria against graph/board/state/metrics."""

    def __init__(self, workspace_id: str = "default", session_factory=None):
        self.workspace_id = workspace_id or "default"
        self._session_factory = session_factory

    def _sessions(self):
        if self._session_factory is not None:
            return self._session_factory
        from core.database import get_db_session
        return get_db_session

    # ------------------------------------------------------------------ api

    def evaluate(self, criteria: List[Dict[str, Any]], state: Optional[Dict[str, Any]] = None) -> List[CriterionResult]:
        state = state or {}
        return [self._evaluate_one(c, state) for c in (criteria or [])]

    def all_satisfied(self, results: List[CriterionResult]) -> bool:
        return bool(results) and all(r.satisfied for r in results)

    def satisfaction_ratio(self, results: List[CriterionResult]) -> float:
        if not results:
            return 0.0
        return sum(1 for r in results if r.satisfied) / len(results)

    # ------------------------------------------------------------- dispatch

    def _evaluate_one(self, criterion: Dict[str, Any], state: Dict[str, Any]) -> CriterionResult:
        ctype = (criterion.get("type") or "").strip()
        try:
            handler = getattr(self, f"_check_{ctype}", None)
            if handler is None:
                return CriterionResult(criterion, False, error=f"unknown criterion type '{ctype}'")
            ok, detail = handler(criterion, state)
            return CriterionResult(criterion, bool(ok), detail=detail)
        except Exception as exc:
            logger.debug(f"criterion evaluation error ({ctype}): {exc}")
            return CriterionResult(criterion, False, error=str(exc))

    # ------------------------------------------------------------ graph leg

    def _graph_session(self):
        return self._sessions()()

    def _find_node(self, session, spec: Dict[str, Any]):
        from core.models import GraphNode
        from sqlalchemy import or_
        q = session.query(GraphNode).filter(GraphNode.workspace_id == self.workspace_id)
        name = _norm(spec.get("name"))
        if name:
            like = f"%{name}%"
            q = q.filter(or_(GraphNode.name.ilike(like), GraphNode.name.ilike(name)))
        # entity_type (not "type" — that key holds the criterion type at the
        # top level of entity_exists criteria)
        entity_type = spec.get("entity_type") or spec.get("node_type")
        if entity_type:
            q = q.filter(GraphNode.type.ilike(str(entity_type)))
        return q.first()

    def _check_entity_exists(self, c: Dict[str, Any], state: Dict[str, Any]):
        if not c.get("name"):
            return False, "criterion missing 'name'"
        with self._graph_session() as session:
            node = self._find_node(session, c)
        if node is None:
            return False, f"no entity matching {c.get('name')!r}"
        return True, f"found {node.name} ({node.type})"

    def _check_graph_edge_exists(self, c: Dict[str, Any], state: Dict[str, Any]):
        with self._graph_session() as session:
            src = self._find_node(session, c.get("source") or {})
            tgt = self._find_node(session, c.get("target") or {})
            if not src or not tgt:
                return False, f"endpoint not found (src={bool(src)}, tgt={bool(tgt)})"
            from core.models import GraphEdge
            q = session.query(GraphEdge).filter(
                GraphEdge.workspace_id == self.workspace_id,
                GraphEdge.source_node_id == src.id,
                GraphEdge.target_node_id == tgt.id,
            )
            rel = c.get("relation")
            if rel:
                q = q.filter(GraphEdge.relationship_type.ilike(str(rel)))
            edge = q.first()
        if edge is None:
            return False, f"no {rel or 'edge'} between {src.name} and {tgt.name}"
        return True, f"edge {edge.relationship_type}: {src.name} -> {tgt.name}"

    # ------------------------------------------------------------ board leg

    def _check_board_task_status(self, c: Dict[str, Any], state: Dict[str, Any]):
        from core.models_board import BoardTask
        with self._graph_session() as session:
            q = session.query(BoardTask)
            if c.get("task_id"):
                q = q.filter(BoardTask.id == str(c["task_id"]))
            elif c.get("title"):
                q = q.filter(BoardTask.title.ilike(f"%{str(c['title'])}%"))
            else:
                return False, "criterion needs task_id or title"
            task = q.first()
        if task is None:
            return False, "board task not found"
        want = str(c.get("status", "DONE")).upper()
        actual = str(task.status or "").upper()
        return (actual == want,
                f"task '{task.title}' status={actual}" if actual == want
                else f"task '{task.title}' status={actual}, want {want}")

    # ----------------------------------------------------------- state leg

    def _check_state_equals(self, c: Dict[str, Any], state: Dict[str, Any]):
        key, want = c.get("key"), c.get("value")
        actual = state.get(key)
        return (actual == want, f"state[{key!r}]={actual!r}")

    def _check_state_contains(self, c: Dict[str, Any], state: Dict[str, Any]):
        key, needle = c.get("key"), c.get("value")
        actual = state.get(key)
        ok = isinstance(actual, (str, list, dict)) and needle in actual
        return (ok, f"state[{key!r}] contains {needle!r}" if ok else f"state[{key!r}] missing {needle!r}")

    def _resolve_operand(self, operand: Any, state: Dict[str, Any]) -> float:
        if isinstance(operand, dict) and "$state" in operand:
            value = state.get(operand["$state"], 0)
        else:
            value = operand
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"operand {operand!r} is not numeric")

    def _check_numeric_compare(self, c: Dict[str, Any], state: Dict[str, Any]):
        import operator
        ops = {">=": operator.ge, "<=": operator.le, "==": operator.eq,
               "!=": operator.ne, ">": operator.gt, "<": operator.lt}
        op_name = str(c.get("op", ">="))
        if op_name not in ops:
            return False, f"unknown op {op_name!r}"
        left = self._resolve_operand(c.get("left", 0), state)
        right = self._resolve_operand(c.get("right", 0), state)
        ok = ops[op_name](left, right)
        return ok, f"{left} {op_name} {right} -> {ok}"

    # --------------------------------------------------------- metrics leg

    def _check_metric_gte(self, c: Dict[str, Any], state: Dict[str, Any]):
        metric, target = c.get("metric"), c.get("target", 0)
        value = self._metric_value(str(metric))
        if value is None:
            return False, f"unknown metric {metric!r}"
        return (value >= float(target), f"{metric}={value} >= {target}")

    def _metric_value(self, metric: str) -> Optional[float]:
        try:
            from core.models import GoalObjective, GraphEdge, GraphNode
            from sqlalchemy import func
            with self._graph_session() as session:
                if metric == "graph_node_count":
                    return float(session.query(func.count(GraphNode.id)).filter(
                        GraphNode.workspace_id == self.workspace_id).scalar() or 0)
                if metric == "graph_edge_count":
                    return float(session.query(func.count(GraphEdge.id)).filter(
                        GraphEdge.workspace_id == self.workspace_id).scalar() or 0)
                if metric == "verified_edge_count":
                    # JSON dialect-portable count: verified flag lives in
                    # properties->verification; count in Python over capped rows.
                    rows = session.query(GraphEdge.properties).filter(
                        GraphEdge.workspace_id == self.workspace_id).limit(10000).all()
                    return float(sum(
                        1 for (props,) in rows
                        if (props or {}).get("verification") == "verified"))
                if metric == "goal_achievement_rate":
                    goals = session.query(GoalObjective).filter(
                        GoalObjective.workspace_id == self.workspace_id).limit(1000).all()
                    if not goals:
                        return 0.0
                    achieved = sum(1 for g in goals if g.status == "achieved")
                    return achieved / len(goals) * 100.0
        except Exception as exc:
            logger.debug(f"metric {metric} unavailable: {exc}")
        return None

    # ------------------------------------------------------- combinators

    def _check_all_of(self, c: Dict[str, Any], state: Dict[str, Any]):
        results = self.evaluate(c.get("criteria", []), state)
        ok = bool(results) and all(r.satisfied for r in results)
        return ok, f"{sum(r.satisfied for r in results)}/{len(results)} satisfied"

    def _check_any_of(self, c: Dict[str, Any], state: Dict[str, Any]):
        results = self.evaluate(c.get("criteria", []), state)
        ok = any(r.satisfied for r in results)
        return ok, f"{sum(r.satisfied for r in results)}/{len(results)} satisfied"

    def _check_manual(self, c: Dict[str, Any], state: Dict[str, Any]):
        return False, f"manual sign-off required: {c.get('note', '')}"
