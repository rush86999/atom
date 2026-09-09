"""GoalRun executors — turn a router decision into real work
(docs/architecture/GOAL_RUN_ORCHESTRATION.md §3.3, slice 3).

Step kinds (the plan's vocabulary):
- canvas_work         → create/link a canvas for the step, then (best-effort,
                        flag-gated) delegate content work to the step agent's
                        GenericAgent objective loop with context.goal_id. The
                        canvas done-signals (apply_canvas_edit `no_change`,
                        canvas_close, non-terminal dispatch) drive the NEXT
                        run boundary — the loop never bypasses the existing
                        chat/canvas pipeline or its maturity gates.
- integration_action  → action_registry.execute_action (the general
                        mechanism — 40+ integrations; no per-integration
                        special cases).
- human_checkpoint    → a PROCESS-INTRINSIC approval step (e.g. quote
                        approval before send): HITLAction row + the run
                        waits on the human_checkpoint event until resolved
                        (goal_run_routes.resolve_checkpoint).
- wait_for            → GoalRunService.set_wait.

Every canvas created here carries the goal-run back-links so the goal's
touch points group as one unit (Canvas.goal_run_id / goal_run_step_id).
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Opt-in agent delegation for canvas content (off by default: the run
# creates and links the canvas; content flows through the proven
# chat/canvas co-editing path unless this is enabled).
AGENT_WORK_FLAG = "ATOM_GOAL_RUN_AGENT_WORK"


class GoalRunExecutors:
    def __init__(self, service):
        """service: GoalRunService — used for wait bookkeeping and cursor
        state on checkpoint steps."""
        self.service = service

    # ------------------------------------------------------------------ api

    async def execute(self, run: Dict[str, Any],
                      decision: Dict[str, Any]) -> Dict[str, Any]:
        kind = decision.get("decision")
        if kind in ("ADVANCE", "REVISE_CURRENT"):
            return await self._run_current_step(run, decision,
                                                revise=(kind == "REVISE_CURRENT"))
        if kind == "BRANCH_NEW_CANVAS":
            return await self._branch_new_canvas(run, decision)

    async def _branch_new_canvas(self, run, decision) -> Dict[str, Any]:
        """The multi-canvas requirement (§1.1): an additional canvas opened
        mid-run because the finished canvas's data demanded it."""
        spec = decision.get("new_canvas") or {}
        title = spec.get("title") or decision.get("rationale", "New canvas")[:120]
        canvas_type = spec.get("canvas_type") or "document"
        step_id = decision.get("target_step") or f"branch-{uuid.uuid4().hex[:6]}"
        workspace_id = run.get("workspace_id") or self.service.workspace_id
        tenant_id = run.get("tenant_id") or self.service.tenant_id
        canvas_id = self._create_linked_canvas(
            run, workspace_id, tenant_id, step_id, title, canvas_type)
        return {"canvas_id": canvas_id, "step_id": step_id, "branched": True}
        if kind == "SKIP":
            return {"skipped": decision.get("target_step") or run.get("cursor")}
        if kind == "WAIT":
            return {"wait": decision.get("wait_spec")}
        if kind in ("ASK_HUMAN", "DONE", "REPLAN"):
            return {"delegated_to": kind}  # handled by the service itself
        logger.warning(f"goal run {run.get('id')}: unhandled decision {kind!r}")
        return {"error": f"unhandled decision {kind!r}"}

    # ---------------------------------------------------------- canvas work

    async def _run_current_step(self, run, decision, revise: bool) -> Dict[str, Any]:
        step = self._current_step(run, decision)
        if step is None:
            # Plan exhausted (e.g. last step was the checkpoint just
            # resolved): the router re-decides with an empty remaining plan.
            return {"plan_exhausted": True}
        kind = (step or {}).get("kind", "canvas_work")
        if kind == "integration_action":
            return await self._integration_action(run, decision, step or {})
        if kind == "human_checkpoint":
            return self._human_checkpoint(run, step or {})
        if kind == "wait_for":
            spec = (step or {}).get("wait_spec") or {"event": "timer"}
            self.service.set_wait(run["id"], spec)
            return {"wait": spec}
        return await self._canvas_work(run, decision, step or {}, revise=revise)

    async def _canvas_work(self, run, decision, step, revise: bool = False) -> Dict[str, Any]:
        workspace_id = run.get("workspace_id") or self.service.workspace_id
        tenant_id = run.get("tenant_id") or self.service.tenant_id
        step_id = step.get("id") or decision.get("target_step")
        title = step.get("title") or decision.get("rationale", "Goal run step")[:120]
        canvas_type = step.get("canvas_type") or "document"

        canvas_id: Optional[str] = None
        if revise:
            # REVISE_CURRENT reworks the canvas this step ALREADY produced —
            # never opens a sibling (§3.2 semantics).
            canvas_id = self.service.latest_canvas_for_step(run["id"], step_id)
        if not canvas_id:
            canvas_id = self._create_linked_canvas(
                run, workspace_id, tenant_id, step_id, title, canvas_type)

        result: Dict[str, Any] = {"canvas_id": canvas_id, "step_id": step_id,
                                  "revised": revise}
        directive = (step.get("directive")
                     or decision.get("rationale")
                     or title)
        delegated = await self._delegate_agent_work(run, step_id, directive,
                                                    canvas_id)
        result["agent_delegated"] = delegated
        return result

    def _create_linked_canvas(self, run, workspace_id, tenant_id, step_id,
                              title, canvas_type) -> str:
        from core.models import Canvas, CanvasAudit
        canvas_id = f"canvas-{uuid.uuid4().hex[:12]}"
        with self.service._sessions()() as session:
            session.add(Canvas(
                id=canvas_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                created_by=run.get("agent_id") or run.get("created_by") or "goal_run",
                name=title[:255],
                description=f"Goal-run step: {title}"[:2000],
                canvas_type=canvas_type,
                content={"goal_run_directive": title[:500]},
                goal_run_id=run["id"],
                goal_run_step_id=step_id,
            ))
            session.add(CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=tenant_id,
                action_type="goal_run_canvas_create",
                agent_id=run.get("agent_id"),
                canvas_type=canvas_type,
                details_json={"goal_run_id": run["id"],
                              "step_id": step_id},
            ))
            session.commit()
        return canvas_id

    async def _delegate_agent_work(self, run, step_id, directive, canvas_id) -> bool:
        """Best-effort delegation to the step agent's objective loop
        (GenericAgent.execute with context.goal_id — the DoD loop already
        exists). Off unless ATOM_GOAL_RUN_AGENT_WORK is enabled; failures are
        logged, never raised — the run continues and the co-editing pipeline
        remains the primary content path."""
        if not run.get("agent_id"):
            return False
        if os.environ.get(AGENT_WORK_FLAG, "").strip().lower() not in ("1", "true", "yes"):
            return False
        try:
            from core.generic_agent import GenericAgent
            agent = GenericAgent(agent_id=run["agent_id"])
            coro = agent.execute(
                directive,
                context={"goal_id": run.get("goal_id"),
                         "workspace_id": run.get("workspace_id"),
                         "goal_run_id": run["id"],
                         "goal_run_step_id": step_id,
                         "canvas_id": canvas_id},
            )
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None:
                loop.create_task(coro)
                return True  # fire-and-forget; its done-signals drive the loop
            asyncio.run(coro)
            return True
        except Exception as exc:
            logger.warning(f"goal run {run.get('id')}: agent delegation "
                           f"failed: {exc}")
            return False

    # ----------------------------------------------------- integration act

    async def _integration_action(self, run, decision, step) -> Dict[str, Any]:
        from core.action_registry import action_registry, ActionNotFoundError
        name = step.get("action") or step.get("title")
        if not name:
            return {"error": "integration_action step missing 'action'"}
        arguments = dict(step.get("arguments") or {})
        try:
            result = await action_registry.execute_action(
                str(name), arguments,
                context={"workspace_id": run.get("workspace_id"),
                         "tenant_id": run.get("tenant_id"),
                         "agent_id": run.get("agent_id"),
                         "goal_run_id": run["id"],
                         "goal_id": run.get("goal_id")})
            return {"action": name, "result": result}
        except ActionNotFoundError as exc:
            return {"error": str(exc), "action": name}

    # ------------------------------------------------------- human checkpoint

    def _human_checkpoint(self, run, step) -> Dict[str, Any]:
        """Process-intrinsic approval (e.g. quote sign-off before send):
        HITL row + the run WAITS on the human_checkpoint event; resolution
        goes through goal_run_routes.resolve_checkpoint (NOT decision
        resume — this is a plan step, not a held decision)."""
        from core.models import HITLAction, HITLActionStatus
        hitl_id = None
        with self.service._sessions()() as session:
            hitl = HITLAction(
                workspace_id=run.get("workspace_id") or self.service.workspace_id,
                tenant_id=run.get("tenant_id") or self.service.tenant_id,
                agent_id=run.get("agent_id"),
                action_type="goal_run_checkpoint",
                platform="in_app",
                params={"run_id": run["id"], "step_id": step.get("id"),
                        "title": step.get("title"),
                        "note": step.get("note")},
                status=HITLActionStatus.PENDING.value,
                reason=f"goal-run checkpoint: {step.get('title', '')}"[:500],
            )
            session.add(hitl)
            session.commit()
            hitl_id = hitl.id
        self.service.set_wait(run["id"], {
            "event": "human_checkpoint", "match": {"hitl_id": hitl_id},
        })
        self.service.append_decision(run["id"], {
            "kind": "checkpoint_created", "step_id": step.get("id"),
            "rationale": step.get("title") or "", "hitl_id": hitl_id,
        })
        # Nothing-silent (§6): approval-needed notification with guidance.
        try:
            from core.goals.goal_run_notifications import (
                notify_run_event, schedule_notification)
            schedule_notification(notify_run_event(
                "checkpoint", run, step_title=step.get("title")))
        except Exception as exc:
            logger.warning(f"goal run {run.get('id')}: checkpoint "
                           f"notification failed: {exc}")
        return {"checkpoint": hitl_id, "step_id": step.get("id")}

    # ---------------------------------------------------------------- util

    @staticmethod
    def _current_step(run, decision) -> Optional[Dict[str, Any]]:
        plan = run.get("plan") or []
        cursor = decision.get("target_step") or run.get("cursor")
        for step in plan:
            if step.get("id") == cursor:
                return None if step.get("done") else step
        for step in plan:
            if not step.get("done"):
                return step
        return None
