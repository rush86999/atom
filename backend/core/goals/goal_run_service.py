"""GoalRunService — the durable, self-steering goal run
(docs/architecture/GOAL_RUN_ORCHESTRATION.md §3.1-§3.5, §3.7).

A GoalRun is a long-lived, event-resumable execution of a role-bound goal.
After every step boundary (canvas done-signal, action result, event wake)
the service asks the router (goal_run_router.py) for one structured
decision — ADVANCE / REVISE_CURRENT / BRANCH_NEW_CANVAS / SKIP / REPLAN /
WAIT / ASK_HUMAN / DONE — persists it with its rationale in the
append-only decision log, mutates the run parameters, and executes the
choice through the executor registry (goal_run_executors.py).

Design constraints honored here:
- Durable state, not in-memory graphs: every decision and parameter
  mutation is a persisted row column; the run survives restarts.
- The router NEVER executes anything itself; the loop does, behind the
  same governance/HITL gates the rest of the repo uses.
- Guardrails (§3.5): replan budget, replan-magnitude HITL gate, stuck
  detector, DONE verification against goal criteria (never trusted).
- Training mode (§3.7B): EVERY router decision becomes an automatic HITL
  checkpoint before it executes; overrides flow to the correction
  machinery via goal_run_learning (fault-isolated).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GOAL_RUN_STATUSES = (
    "planning", "active", "waiting", "paused_hitl",
    "achieved", "failed", "cancelled",
)

# Guarded transition table (mirrors GOAL_TRANSITIONS in goal_service.py).
GOAL_RUN_TRANSITIONS: Dict[str, set] = {
    "planning":   {"active", "cancelled"},
    "active":     {"waiting", "paused_hitl", "achieved", "failed", "cancelled"},
    "waiting":    {"active", "paused_hitl", "failed", "cancelled"},
    "paused_hitl": {"active", "waiting", "failed", "cancelled"},
    "achieved":   set(),   # terminal
    "failed":     set(),   # terminal
    "cancelled":  set(),   # terminal
}

SUPERVISION_MODES = ("training", "shadow", "autonomous")

# Tier WAIT ceilings (§8.6 resolution): how far into the future a router
# WAIT deadline may reach before it needs human approval. Supervisors can
# override per run via parameters["wait_ceiling_days"]. Deliberately in the
# gate table, NOT the BPE genome — self-evolving wait limits would be
# unsupervised drift.
DEFAULT_WAIT_CEILING_DAYS = {"training": 3, "shadow": 14, "autonomous": 30}

DECISION_TYPES = (
    "ADVANCE", "REVISE_CURRENT", "BRANCH_NEW_CANVAS", "SKIP",
    "REPLAN", "WAIT", "ASK_HUMAN", "DONE",
)

# Guardrail defaults (§3.5) — overridable per run via parameters.
DEFAULT_REPLAN_BUDGET = 5
STUCK_DECISION_WINDOW = 3
REPLAN_MAGNITUDE_THRESHOLD = 0.5  # dropping more than half the remaining plan


class GoalRunTransitionError(ValueError):
    """Raised on an illegal goal-run status transition."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso() -> str:
    return _utcnow().isoformat()


class GoalRunService:
    """Lifecycle, wait bookkeeping, and the router-driven decision loop."""

    def __init__(self, workspace_id: str = "default", tenant_id: str = "default",
                 session_factory=None):
        self.workspace_id = workspace_id or "default"
        self.tenant_id = tenant_id or "default"
        self._session_factory = session_factory

    def _sessions(self):
        if self._session_factory is not None:
            return self._session_factory
        from core.database import get_db_session
        return get_db_session

    # ------------------------------------------------------------------ CRUD

    def create_run(
        self,
        goal_id: str,
        agent_id: Optional[str] = None,
        role: Optional[str] = None,
        supervision_mode: str = "shadow",
        plan: Optional[List[Dict[str, Any]]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        from core.models import GoalObjective, GoalRun
        if supervision_mode not in SUPERVISION_MODES:
            raise ValueError(
                f"supervision_mode must be one of {SUPERVISION_MODES}")
        with self._sessions()() as session:
            goal = session.query(GoalObjective).filter(
                GoalObjective.id == goal_id).first()
            if not goal:
                raise ValueError(f"goal {goal_id} not found")
            run = GoalRun(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                goal_id=goal_id,
                agent_id=agent_id,
                role=role,
                status="planning",
                supervision_mode=supervision_mode,
                plan=list(plan or []),
                parameters=dict(parameters or {}),
                decision_log=[],
                created_by=created_by,
            )
            if run.plan:
                run.cursor = run.plan[0].get("id")
            session.add(run)
            session.commit()
            session.refresh(run)
            return self._to_dict(run)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        from core.models import GoalRun
        with self._sessions()() as session:
            run = session.query(GoalRun).filter(GoalRun.id == run_id).first()
            return self._to_dict(run) if run else None

    def list_runs(self, goal_id: Optional[str] = None,
                  agent_id: Optional[str] = None,
                  role: Optional[str] = None,
                  status: Optional[str] = None,
                  include_terminal: bool = True,
                  limit: int = 200) -> List[Dict[str, Any]]:
        from core.models import GoalRun
        with self._sessions()() as session:
            q = session.query(GoalRun).filter(
                GoalRun.workspace_id == self.workspace_id)
            if goal_id:
                q = q.filter(GoalRun.goal_id == goal_id)
            if agent_id:
                q = q.filter(GoalRun.agent_id == agent_id)
            if role:
                q = q.filter(GoalRun.role == role)
            if status:
                q = q.filter(GoalRun.status == status)
            elif not include_terminal:
                q = q.filter(GoalRun.status.notin_(
                    ("achieved", "failed", "cancelled")))
            rows = q.order_by(GoalRun.created_at.desc()).limit(limit).all()
            return [self._to_dict(r) for r in rows]

    def _load(self, session, run_id: str):
        from core.models import GoalRun
        return session.query(GoalRun).filter(GoalRun.id == run_id).first()

    # ------------------------------------------------------------ surfaces

    def set_supervision_mode(self, run_id: str, mode: str) -> Dict[str, Any]:
        """Explicit supervisor act (§3.7B — promotion is earned and applied
        per run, never an automatic toggle)."""
        from core.models import GoalRun
        if mode not in SUPERVISION_MODES:
            raise ValueError(f"supervision_mode must be one of {SUPERVISION_MODES}")
        with self._sessions()() as session:
            run = self._load(session, run_id)
            if not run:
                raise ValueError(f"goal run {run_id} not found")
            run.supervision_mode = mode
            session.commit()
            session.refresh(run)
            return self._to_dict(run)

    def list_canvases(self, run_id: str) -> List[Dict[str, Any]]:
        """The run's touch-point canvases (goal-grouped gallery, §5)."""
        from core.models import Canvas
        with self._sessions()() as session:
            rows = session.query(Canvas).filter(
                Canvas.goal_run_id == run_id).order_by(
                Canvas.created_at.asc()).all()
            return [{"id": c.id, "name": c.name, "canvas_type": c.canvas_type,
                     "step_id": c.goal_run_step_id,
                     "created_at": c.created_at.isoformat() if c.created_at else None}
                    for c in rows]

    def latest_canvas_for_step(self, run_id: str,
                               step_id: Optional[str]) -> Optional[str]:
        """The canvas a plan step already produced — REVISE_CURRENT reworks
        THIS canvas instead of opening a sibling (§3.2 semantics)."""
        if not step_id:
            return None
        from core.models import Canvas
        with self._sessions()() as session:
            row = session.query(Canvas).filter(
                Canvas.goal_run_id == run_id,
                Canvas.goal_run_step_id == step_id).order_by(
                Canvas.created_at.desc()).first()
            return row.id if row else None

    def rewind_to_work_before(self, run_id: str, step_id: Optional[str]) -> None:
        """Checkpoint REJECTED: point the cursor back at the nearest real
        work step before the checkpoint, so the router's next decision can
        target actual work (revise the quote) instead of re-requesting the
        same approval."""
        run = self.get_run(run_id)
        plan = run.get("plan") or []
        ids = [s.get("id") for s in plan]
        if step_id not in ids:
            return
        idx = ids.index(step_id)
        for j in range(idx - 1, -1, -1):
            step = plan[j]
            if step.get("kind") != "human_checkpoint" and not step.get("done"):
                self._set_cursor(run_id, step["id"])
                return

    # -------------------------------------------------------- state machine

    def transition(self, run_id: str, new_status: str) -> Dict[str, Any]:
        from core.models import GoalRun
        new_status = (new_status or "").strip().lower()
        if new_status not in GOAL_RUN_STATUSES:
            raise GoalRunTransitionError(f"unknown status '{new_status}'")
        with self._sessions()() as session:
            run = self._load(session, run_id)
            if not run:
                raise GoalRunTransitionError(f"goal run {run_id} not found")
            allowed = GOAL_RUN_TRANSITIONS.get(run.status, set())
            if new_status not in allowed:
                raise GoalRunTransitionError(
                    f"illegal transition {run.status} -> {new_status} "
                    f"(allowed: {sorted(allowed) or 'none — terminal'})")
            run.status = new_status
            session.commit()
            session.refresh(run)
            result = self._to_dict(run)
            if new_status in ("achieved", "failed", "cancelled"):
                self._on_terminal(result)
            return result

    def _on_terminal(self, run: Dict[str, Any]) -> None:
        """Nothing-silent (§6): terminal outcomes notify the run's creator
        and record the outcome into the learning loop (experience on
        achieve, critique on failure). Fire-and-forget, fault-isolated."""
        try:
            from core.goals.goal_run_notifications import (
                notify_run_event, schedule_notification)
            kind = "achieved" if run["status"] == "achieved" else "stopped"
            schedule_notification(notify_run_event(kind, run))
        except Exception as exc:
            logger.warning(f"goal run {run.get('id')}: terminal notification "
                           f"failed: {exc}")
        if run["status"] in ("achieved", "failed"):
            # Cancelled ≠ a judgment failure — no critique noise.
            try:
                from core.goals.goal_run_learning import record_run_outcome
                from core.goals.goal_run_notifications import schedule_notification
                schedule_notification(record_run_outcome(self, run, run["status"]))
            except Exception as exc:
                logger.warning(f"goal run {run.get('id')}: outcome recording "
                               f"failed: {exc}")

    def activate(self, run_id: str) -> Dict[str, Any]:
        run = self.transition(run_id, "active")
        if not run["cursor"] and run["plan"]:
            self._set_cursor(run_id, run["plan"][0].get("id"))
            run = self.get_run(run_id)
        return run

    def cancel(self, run_id: str, reason: str = "") -> Dict[str, Any]:
        run = self.transition(run_id, "cancelled")
        self.append_decision(run_id, {
            "kind": "cancelled", "rationale": reason or "cancelled by user",
        })
        return run

    def _set_cursor(self, run_id: str, step_id: Optional[str]) -> None:
        from core.models import GoalRun
        with self._sessions()() as session:
            run = self._load(session, run_id)
            if run:
                run.cursor = step_id
                session.commit()

    # ------------------------------------------------------------- plan

    def set_plan(self, run_id: str, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        from core.models import GoalRun
        with self._sessions()() as session:
            run = self._load(session, run_id)
            if not run:
                raise ValueError(f"goal run {run_id} not found")
            run.plan = list(plan or [])
            if run.status == "planning" and run.plan:
                run.cursor = run.plan[0].get("id")
            session.commit()
            session.refresh(run)
            return self._to_dict(run)

    # -------------------------------------------------- parameters / log

    def patch_parameters(self, run_id: str,
                         updates: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Mutational state update (§3.1): top-level merge, one nested level
        for dicts — a decision's ``parameter_updates`` lands here."""
        from core.models import GoalRun
        if not updates:
            return self.get_run(run_id) or {}
        with self._sessions()() as session:
            run = self._load(session, run_id)
            if not run:
                raise ValueError(f"goal run {run_id} not found")
            merged = dict(run.parameters or {})
            for key, value in updates.items():
                if (isinstance(value, dict) and isinstance(merged.get(key), dict)):
                    merged[key] = {**merged[key], **value}
                else:
                    merged[key] = value
            run.parameters = merged
            session.commit()
            session.refresh(run)
            return self._to_dict(run)

    def append_decision(self, run_id: str, entry: Dict[str, Any]) -> None:
        """Append-only decision log (§3.1) — the informal process made
        visible and auditable. Never raises into the caller's flow."""
        from core.models import GoalRun
        try:
            with self._sessions()() as session:
                run = self._load(session, run_id)
                if not run:
                    return
                log = list(run.decision_log or [])
                record = {"ts": _iso(), **entry}
                log.append(record)
                run.decision_log = log
                session.commit()
        except Exception as exc:  # fault-isolated by design
            logger.warning(f"goal run {run_id}: decision log append failed: {exc}")

    def get_decisions(self, run_id: str) -> List[Dict[str, Any]]:
        run = self.get_run(run_id)
        return list(run["decision_log"]) if run else []

    def complete_checkpoint(self, run_id: str, step_id: Optional[str] = None) -> None:
        """A resolved checkpoint counts as an executed step; on approval the
        step is marked done in the persisted plan and the cursor moves past
        it, so the next advance() can't re-create the same checkpoint
        (rejections leave the cursor — the router sees the rejection event
        and re-decides the guarded work)."""
        from core.models import GoalRun
        self._count_step(run_id, "human_checkpoint")
        with self._sessions()() as session:
            run = self._load(session, run_id)
            if run:
                # Rebuild the dicts — in-place mutation of JSON column
                # members is NOT detected by SQLAlchemy (same trap
                # journal_standing_lesson documents).
                plan = [dict(s) for s in (run.plan or [])]
                for step in plan:
                    if step.get("id") == (step_id or run.cursor):
                        step["done"] = True
                run.plan = plan
                session.commit()
        self._advance_cursor(run_id, {})

    # ------------------------------------------------------------ waits

    def set_wait(self, run_id: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Suspend the run until an event (§3.3): email reply, integration
        event, timer, or human input. The spec is consumed exactly once —
        by consume_wake()."""
        from core.models import GoalRun
        if not isinstance(spec, dict) or not spec.get("event"):
            raise ValueError("wait spec must be a dict with an 'event' key")
        with self._sessions()() as session:
            run = self._load(session, run_id)
            if not run:
                raise ValueError(f"goal run {run_id} not found")
            if run.status not in ("active", "waiting", "paused_hitl"):
                # waiting → waiting is legal: a wake arrives and the router
                # decides to wait again for something else (§3.3).
                raise GoalRunTransitionError(
                    f"cannot wait from status '{run.status}'")
            run.waiting_on = {**spec, "created_at": _iso()}
            run.status = "waiting"
            session.commit()
            session.refresh(run)
            result = self._to_dict(run)
            # Nothing-silent (§6): the supervisor is told the run is asleep,
            # what it waits for, and that there is nothing to do — UNLESS
            # the wait is a human checkpoint (the checkpoint notification
            # covers it with action-needed guidance instead).
            if str(spec.get("event")) != "human_checkpoint":
                try:
                    from core.goals.goal_run_notifications import (
                        notify_run_event, schedule_notification)
                    schedule_notification(notify_run_event(
                        "waiting", result, deadline=spec.get("deadline"),
                        event_desc=spec.get("summary") or spec.get("event")))
                except Exception as exc:
                    logger.warning(f"goal run {run_id}: waiting notification "
                                   f"failed: {exc}")
            return result

    def consume_wake(self, run_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Try to wake a waiting run with an event. Consumed-once: the
        waiting_on spec is cleared on match; a non-matching event leaves
        the run asleep. Returns {consumed, matched_by, run}."""
        from core.models import GoalRun
        with self._sessions()() as session:
            run = self._load(session, run_id)
            if not run:
                return {"consumed": False, "reason": "run not found"}
            spec = run.waiting_on or {}
            if run.status != "waiting" or not spec:
                return {"consumed": False, "reason": f"run is {run.status}, not waiting"}
            matched_by = self._match_wait(spec, event or {})
            if not matched_by:
                return {"consumed": False, "reason": "event does not match wait spec"}
            run.waiting_on = None
            run.status = "active"
            log = list(run.decision_log or [])
            log.append({"ts": _iso(), "kind": "wake",
                        "event": {k: v for k, v in (event or {}).items()
                                  if k in ("event", "from", "subject", "summary", "source")},
                        "matched_by": matched_by})
            run.decision_log = log
            session.commit()
            session.refresh(run)
            return {"consumed": True, "matched_by": matched_by,
                    "run": self._to_dict(run)}

    @staticmethod
    def _match_wait(spec: Dict[str, Any], event: Dict[str, Any]) -> Optional[str]:
        """Wait-spec matching (§3.4): event type must match; ``match`` fields
        (from/thread_id/keyword) must be contained in the event payload."""
        want_event = str(spec.get("event") or "")
        got_event = str(event.get("event") or "")
        if want_event in ("any", "*") or got_event in ("any", "*"):
            base = True
        else:
            base = bool(want_event and got_event
                        and want_event.lower() == got_event.lower())
        if not base:
            return None
        constraints = spec.get("match") or {}
        for key, needle in constraints.items():
            hay = str(event.get(key) or "")
            if not hay or str(needle).lower() not in hay.lower():
                return None
        if not constraints:
            # Unconstrained waits match only a declared timer/event source.
            return got_event or "timer"
        return f"match:{','.join(constraints.keys())}"

    # ------------------------------------------------------- decision loop

    async def advance(self, run_id: str, step_digest: Optional[Dict[str, Any]] = None,
                      event: Optional[Dict[str, Any]] = None,
                      router=None, executors=None) -> Dict[str, Any]:
        """One loop turn (§3.3): evaluate goal → guardrails → router →
        persist decision → (training/HITL: hold) → execute.

        Fault-isolated at the boundaries the loop cannot control: goal
        evaluation and the router never crash the run; the executor result
        is the caller's contract.
        """
        run = self.get_run(run_id)
        if not run:
            return {"advanced": False, "reason": "run not found"}
        if run["status"] == "waiting" and not event:
            return {"advanced": False,
                    "reason": f"waiting on {run['waiting_on']}"}
        if run["status"] not in ("active", "waiting"):
            return {"advanced": False, "reason": f"run is {run['status']}"}
        if run.get("pending_decision"):
            # A wake flipped us active while a held decision still awaits
            # the supervisor — never execute around an unresolved hold.
            return {"advanced": False,
                    "reason": "held decision awaiting approval"}

        # 1. Goal evaluation drives termination/escalation (§3.4).
        goal_state = self._evaluate_goal(run)
        if goal_state.get("status") == "achieved":
            self.append_decision(run_id, {
                "kind": "goal_achieved", "rationale": "criteria satisfied",
            })
            return {"advanced": True, "decision": "GOAL_ACHIEVED",
                    "run": self.transition(run_id, "achieved")}

        # 2. Router decision.
        router = router or self._default_router()
        context = self._router_context(run, goal_state, step_digest, event)
        decision = await router.decide(context)

        # 3. Guardrails (§3.5) may override the decision BEFORE it lands.
        decision = self._apply_guardrails(run, decision)
        decision = self._apply_wait_ceiling(run, decision)
        if decision.get("held"):
            return {"advanced": True, "decision": decision["decision"],
                    "held": True, "reason": decision.get("hold_reason"),
                    "run": self.get_run(run_id)}

        # 4. Persist the decision + rationale, apply parameter patch.
        self.append_decision(run_id, {
            "kind": "decision",
            "decision": decision.get("decision"),
            "rationale": decision.get("rationale"),
            "parameter_diff": decision.get("parameter_updates") or {},
            "step_id": decision.get("target_step") or run["cursor"],
            "canvas_id": (step_digest or {}).get("canvas_id"),
            "event": (event or {}).get("event"),
            "model": decision.get("model"),
            "confidence": decision.get("confidence"),
        })
        if decision.get("parameter_updates"):
            run = self.patch_parameters(run_id, decision["parameter_updates"])

        # 5. Training mode: every decision is an automatic HITL checkpoint
        # before execution (§3.7B). ASK_HUMAN always checkpoints.
        if (run["supervision_mode"] == "training"
                and decision.get("decision") != "ASK_HUMAN"):
            return self._hold_for_approval(run_id, decision,
                                           reason="training mode checkpoint")
        if decision.get("decision") == "ASK_HUMAN":
            return self._hold_for_approval(
                run_id, decision,
                reason=decision.get("rationale") or "router requests human input")

        # 6. Execute.
        return await self.execute_decision(run_id, decision, executors=executors)

    async def execute_decision(self, run_id: str, decision: Dict[str, Any],
                               executors=None) -> Dict[str, Any]:
        """Execute a persisted decision. Exposed separately so resume()
        (HITL approval) replays the exact held decision."""
        from core.goals.goal_run_executors import GoalRunExecutors
        executors = executors or GoalRunExecutors(self)
        run = self.get_run(run_id)
        if not run:
            return {"advanced": False, "reason": "run not found"}
        kind = decision.get("decision")

        if kind == "WAIT":
            spec = decision.get("wait_spec") or {"event": "timer"}
            updated = self.set_wait(run_id, spec)
            return {"advanced": True, "decision": "WAIT", "run": updated}

        if kind == "REPLAN":
            new_plan = decision.get("new_plan")
            if isinstance(new_plan, list) and new_plan:
                # Magnitude guardrail (§3.5): a replan that discards more
                # than half the remaining plan is a direction change big
                # enough to require a human before it takes effect.
                if self._replan_is_major(run, new_plan):
                    return self._hold_for_approval(
                        run_id,
                        {**decision, "decision": "ASK_HUMAN",
                         "rationale": f"major replan (drops most of the "
                                      f"remaining plan) — human approval "
                                      f"required: {decision.get('rationale')}"},
                        reason="major replan gate")
                self.set_plan(run_id, new_plan)
            with self._sessions()() as session:
                db_run = self._load(session, run_id)
                if db_run:
                    db_run.replan_count = (db_run.replan_count or 0) + 1
                    if db_run.plan and not db_run.cursor:
                        db_run.cursor = db_run.plan[0].get("id")
                    session.commit()
            return {"advanced": True, "decision": "REPLAN",
                    "run": self.get_run(run_id)}

        if kind == "DONE":
            return self._finish_done(run_id, decision)

        result = await executors.execute(run, decision)
        # Non-terminal canvas work updates the counters; REVISE_CURRENT
        # stays on the step (that is what "revise" means) — only ADVANCE /
        # BRANCH / SKIP move the cursor.
        if kind in ("ADVANCE", "BRANCH_NEW_CANVAS", "SKIP"):
            self._count_step(run_id, kind)
            self._advance_cursor(run_id, decision)
        elif kind == "REVISE_CURRENT":
            self._count_step(run_id, kind)
        return {"advanced": True, "decision": kind, "result": result,
                "run": self.get_run(run_id)}

    # ------------------------------------------------------------- HITL

    def _hold_for_approval(self, run_id: str, decision: Dict[str, Any],
                           reason: str) -> Dict[str, Any]:
        """Hold a decision for human approval (§3.7B training checkpoints and
        ASK_HUMAN): pending_decision + HITLAction row, status → paused_hitl."""
        from core.models import HITLAction, HITLActionStatus
        run = self.get_run(run_id)
        with self._sessions()() as session:
            db_run = self._load(session, run_id)
            if db_run:
                db_run.pending_decision = decision
                if db_run.status == "active":
                    db_run.status = "paused_hitl"
                db_run.human_interventions = (db_run.human_interventions or 0) + 1
                session.commit()
        hitl_id = None
        try:
            with self._sessions()() as session:
                hitl = HITLAction(
                    workspace_id=self.workspace_id,
                    tenant_id=self.tenant_id,
                    agent_id=run.get("agent_id"),
                    action_type="goal_run_decision",
                    platform="in_app",
                    params={"run_id": run_id, "decision": decision},
                    status=HITLActionStatus.PENDING.value,
                    reason=(reason or "")[:500],
                    context_snapshot={"goal_id": run.get("goal_id"),
                                      "cursor": run.get("cursor")},
                )
                session.add(hitl)
                session.commit()
                hitl_id = hitl.id
        except Exception as exc:
            logger.warning(f"goal run {run_id}: HITL row create failed: {exc}")
        self.append_decision(run_id, {
            "kind": "held_for_approval", "decision": decision.get("decision"),
            "rationale": reason, "hitl_id": hitl_id,
        })
        # Nothing-silent (§6): the supervisor learns NOW — with the decision,
        # its rationale, and what approve/override each mean.
        try:
            from core.goals.goal_run_notifications import (
                notify_run_event, schedule_notification)
            schedule_notification(notify_run_event(
                "decision_held", run, decision=decision))
        except Exception as exc:
            logger.warning(f"goal run {run_id}: held notification failed: {exc}")
        return {"advanced": True, "decision": decision.get("decision"),
                "held": True, "hitl_id": hitl_id, "reason": reason,
                "run": self.get_run(run_id)}

    async def resume(self, run_id: str, approved: bool,
                     reviewer: Optional[str] = None,
                     guidance: Optional[str] = None) -> Dict[str, Any]:
        """Resolve a held decision: approve → execute it; reject/override →
        the run continues from the supervisor's guidance (the override is a
        correction — goal_run_learning, fault-isolated)."""
        run = self.get_run(run_id)
        if not run:
            return {"resumed": False, "reason": "run not found"}
        pending = run.get("pending_decision")
        if not pending:
            return {"resumed": False, "reason": "no pending decision"}

        if not approved:
            # The override is a correction (§3.7C) — but a learning-pipeline
            # failure must never block the supervisor's resume.
            try:
                from core.goals.goal_run_learning import record_decision_override
                record_decision_override(self, run, pending,
                                         guidance=guidance, approved=False)
            except Exception as exc:
                logger.warning(f"goal run {run_id}: override learning "
                               f"recording failed: {exc}")
        with self._sessions()() as session:
            db_run = self._load(session, run_id)
            if db_run:
                db_run.pending_decision = None
                if db_run.status == "paused_hitl":
                    db_run.status = "waiting" if db_run.waiting_on else "active"
                session.commit()
        self.append_decision(run_id, {
            "kind": "override" if not approved else "approved",
            "decision": pending.get("decision"),
            "rationale": guidance or "",
            "reviewer": reviewer,
        })
        if not approved:
            return {"resumed": True, "approved": False,
                    "run": self.get_run(run_id)}
        executed = await self.execute_decision(run_id, pending)
        return {"resumed": True, "approved": True, **executed}

    # -------------------------------------------------------- guardrails

    def _apply_guardrails(self, run: Dict[str, Any],
                          decision: Dict[str, Any]) -> Dict[str, Any]:
        """§3.5: replan budget, stuck detector. Violations force an
        ASK_HUMAN hold instead of silently proceeding (direction-changing is
        also drift risk)."""
        params = run.get("parameters") or {}
        budget = int(params.get("replan_budget", DEFAULT_REPLAN_BUDGET))
        if (decision.get("decision") == "REPLAN"
                and run.get("replan_count", 0) >= budget):
            return {**decision, "decision": "ASK_HUMAN",
                    "held": False,
                    "rationale": f"replan budget ({budget}) exhausted — "
                                 f"human checkpoint required"}
        window = STUCK_DECISION_WINDOW - 1
        recent = [d for d in run.get("decision_log") or []
                  if d.get("kind") == "decision"][-window:]
        incoming_step = decision.get("target_step") or run.get("cursor")
        if (len(recent) == window
                and len({(d.get("decision"), d.get("step_id"))
                         for d in recent}) == 1
                and all(d.get("decision") == decision.get("decision")
                        and d.get("step_id") == incoming_step
                        for d in recent)
                and decision.get("decision") in ("REVISE_CURRENT", "REPLAN")):
            return {**decision, "decision": "ASK_HUMAN", "held": False,
                    "rationale": f"stuck detector: {STUCK_DECISION_WINDOW} "
                                 f"identical decisions — human checkpoint"}
        return decision

    def _apply_wait_ceiling(self, run: Dict[str, Any],
                            decision: Dict[str, Any]) -> Dict[str, Any]:
        """§8.6 resolution: a WAIT whose deadline reaches further than the
        supervision tier's ceiling is a commitment a human signs off on."""
        if decision.get("decision") != "WAIT":
            return decision
        deadline = (decision.get("wait_spec") or {}).get("deadline")
        if not deadline:
            return decision
        parsed = None
        try:
            from core.goals.goal_run_events import _parse_deadline
            parsed = _parse_deadline(deadline)
        except Exception:
            parsed = None
        if parsed is None:
            return decision
        params = run.get("parameters") or {}
        ceiling_days = params.get(
            "wait_ceiling_days",
            DEFAULT_WAIT_CEILING_DAYS.get(run.get("supervision_mode") or "shadow", 14))
        try:
            from datetime import timedelta
            ceiling = _utcnow() + timedelta(days=float(ceiling_days))
        except (TypeError, ValueError):
            return decision
        if parsed > ceiling:
            return {**decision, "decision": "ASK_HUMAN", "held": False,
                    "rationale": f"wait deadline {deadline} exceeds the "
                                 f"{ceiling_days}-day ceiling for "
                                 f"'{run.get('supervision_mode')}' mode — "
                                 f"human sign-off required"}
        return decision

    def _replan_is_major(self, run: Dict[str, Any],
                         new_plan: List[Dict[str, Any]]) -> bool:
        remaining = [s for s in (run.get("plan") or [])
                     if s.get("id") and s["id"] != run.get("cursor")]
        if not remaining or not isinstance(new_plan, list):
            return False
        kept = len([s for s in new_plan
                    if s.get("id") in {r.get("id") for r in remaining}])
        dropped = len(remaining) - kept
        return dropped / len(remaining) > REPLAN_MAGNITUDE_THRESHOLD

    # ------------------------------------------------------------ helpers

    def _default_router(self):
        from core.goals.goal_run_router import GoalRunRouter
        return GoalRunRouter(tenant_id=self.tenant_id,
                             workspace_id=self.workspace_id)

    def _evaluate_goal(self, run: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from core.goals.goal_service import GoalService
            goal_svc = GoalService(workspace_id=self.workspace_id,
                                   tenant_id=self.tenant_id,
                                   session_factory=self._session_factory)
            return goal_svc.evaluate(run["goal_id"])
        except Exception as exc:
            logger.warning(f"goal run {run['id']}: goal evaluate failed: {exc}")
            return {"status": "unknown", "progress": 0}

    def _router_context(self, run: Dict[str, Any],
                        goal_state: Dict[str, Any],
                        step_digest: Optional[Dict[str, Any]],
                        event: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "run": run,
            "goal": goal_state,
            "step_digest": step_digest or {},
            "event": event or {},
        }

    def _count_step(self, run_id: str, kind: str) -> None:
        with self._sessions()() as session:
            db_run = self._load(session, run_id)
            if db_run:
                db_run.steps_executed = (db_run.steps_executed or 0) + 1
                session.commit()

    def _advance_cursor(self, run_id: str, decision: Dict[str, Any]) -> None:
        target = decision.get("target_step")
        if target:
            self._set_cursor(run_id, target)
            return
        run = self.get_run(run_id)
        plan = run.get("plan") or []
        cursor = run.get("cursor")
        ids = [s.get("id") for s in plan]
        if cursor in ids:
            idx = ids.index(cursor)
            if idx + 1 < len(plan):
                self._set_cursor(run_id, plan[idx + 1].get("id"))

    def _finish_done(self, run_id: str, decision: Dict[str, Any]) -> Dict[str, Any]:
        """DONE is claimed by the router but verified against criteria
        (§3.2) — an unsatisfied goal downgrades to a human checkpoint."""
        run = self.get_run(run_id)
        goal_state = self._evaluate_goal(run)
        fully_satisfied = (goal_state.get("total", 0) > 0
                           and goal_state.get("satisfied", 0)
                           == goal_state.get("total", 0))
        if goal_state.get("status") == "achieved" or fully_satisfied:
            self.append_decision(run_id, {
                "kind": "run_done", "rationale": decision.get("rationale"),
            })
            return {"advanced": True, "decision": "DONE",
                    "run": self.transition(run_id, "achieved")}
        return self._hold_for_approval(
            run_id,
            {**decision, "decision": "ASK_HUMAN",
             "rationale": "router claimed DONE but goal criteria are not "
                          f"all satisfied ({goal_state.get('satisfied', 0)}/"
                          f"{goal_state.get('total', 0)}) — human verification"},
            reason="DONE claim failed criteria verification")

    # ----------------------------------------------------------------- util

    @staticmethod
    def _to_dict(run) -> Dict[str, Any]:
        return {
            "id": run.id,
            "tenant_id": run.tenant_id,
            "workspace_id": run.workspace_id,
            "goal_id": run.goal_id,
            "agent_id": run.agent_id,
            "role": run.role,
            "status": run.status,
            "supervision_mode": run.supervision_mode,
            "plan": run.plan or [],
            "cursor": run.cursor,
            "parameters": run.parameters or {},
            "waiting_on": run.waiting_on,
            "pending_decision": run.pending_decision,
            "decision_log": run.decision_log or [],
            "replan_count": run.replan_count,
            "steps_executed": run.steps_executed,
            "human_interventions": run.human_interventions,
            "created_by": run.created_by,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        }
