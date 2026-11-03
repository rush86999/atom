"""GoalRunRouter — the "person changing direction" decision point
(docs/architecture/GOAL_RUN_ORCHESTRATION.md §3.2).

One structured LLM call at every step boundary / event wake. Input is the
run's full situation (goal + criteria state, mutational parameters, the
finished step's digest, remaining plan, recent decisions, role lessons and
advisory playbook steps, maturity tier); output is ONE decision from the
fixed vocabulary, always with a rationale, plus optional parameter updates.

Contract honored here (AGENTS.md §2 — evidence over plausibility): the full
request prompt and raw model output are logged on every call. Failure mode
is NEVER a crash: invalid JSON, unknown decision types, missing required
payloads (WAIT without a spec), or an unavailable LLM all degrade to
ASK_HUMAN — the run pauses for a human instead of guessing.

The router NEVER executes anything; it only proposes. GoalRunService owns
guardrails, persistence, and execution.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from core.goals.goal_run_service import DECISION_TYPES

logger = logging.getLogger(__name__)

# Below this confidence (when the model reports one) a non-trivial decision
# degrades to ASK_HUMAN (§3.2 fallback).
MIN_CONFIDENCE = 0.2
DECISIONS_REQUIRING_HUMAN_WHEN_UNCERTAIN = ("REPLAN", "DONE", "BRANCH_NEW_CANVAS")

_DECISIONS_REQUIRING_SPEC = {"WAIT": "wait_spec", "REPLAN": "new_plan"}


class RouterDecisionModel(BaseModel):
    """Structured output contract for the router LLM call."""
    decision: str = Field(description="One of: " + ", ".join(DECISION_TYPES))
    rationale: str = Field(
        description="Why this direction, given the canvas data and goal — "
                    "shown to the supervisor")
    parameter_updates: Dict[str, Any] = Field(default_factory=dict)
    target_step: Optional[str] = None
    new_plan: Optional[List[Dict[str, Any]]] = None
    wait_spec: Optional[Dict[str, Any]] = None
    confidence: float = 0.5


class GoalRunRouter:
    def __init__(self, tenant_id: str = "default", workspace_id: str = "default",
                 llm_service: Any = None):
        self.tenant_id = tenant_id or "default"
        self.workspace_id = workspace_id or "default"
        self._llm_service = llm_service

    # ------------------------------------------------------------------ api

    async def decide(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_prompt(context)
        raw, error = await self._structured(prompt)
        if error:
            logger.warning(f"goal run router unavailable: {error}")
            return self._fallback(f"router unavailable: {error}")
        logger.info("goal_run_router request:\n%s", prompt[-2000:])
        logger.info("goal_run_router raw output:\n%s", str(raw)[:2000])

        decision = self._coerce(raw)
        if decision is not None:
            return decision

        defect = self._replan_defect(raw)
        if not defect:
            return self._fallback(
                f"router returned an unusable decision: {str(raw)[:300]}")
        # One explicit corrective pass, same schema and consumer prompt. The
        # invalid output is preserved in the returned decision metadata; no
        # plan is fabricated and no execution follows an unrepaired REPLAN.
        repair_prompt = (
            prompt
            + "\n\nREPAIR REQUIRED: the previous decision was rejected: "
            + defect
            + "\nReturn a corrected object. If no concrete plan can be "
              "produced, choose ASK_HUMAN instead of REPLAN.\n\nPrevious "
              "invalid output:\n"
            + str(raw)[:2000]
        )
        repaired_raw, repair_error = await self._structured(repair_prompt)
        repaired = self._coerce(repaired_raw)
        repair_meta = {
            "attempted": True,
            "recovered": repaired is not None,
            "defect": defect,
            "invalid_output": str(raw)[:800],
            "repair_error": repair_error,
        }
        if repaired is not None:
            repaired["repair"] = repair_meta
            return repaired
        fallback = self._fallback(
            f"router returned an unusable decision after one repair: "
            f"{str(raw)[:300]}")
        fallback["repair"] = repair_meta
        return fallback

    async def _structured(self, prompt: str):
        """One structured router call under the configured pin."""
        try:
            llm = self._get_llm()
            kwargs: Dict[str, Any] = {}
            pin = os.environ.get(
                "ATOM_GOAL_RUN_ROUTER_PROVIDER_MODEL", "").strip()
            if pin and ":" in pin:
                provider, model = pin.split(":", 1)
                kwargs["provider_model"] = (provider, model)
            raw = await llm.generate_structured_response(
                disable_reasoning=True,
                prompt=prompt,
                response_model=RouterDecisionModel,
                system_instruction="You return only the requested JSON object.",
                temperature=0.0,
                **kwargs,
            )
            return raw, None
        except Exception as exc:  # noqa: BLE001 - unavailable is reported
            return None, exc

    @staticmethod
    def _replan_defect(raw: Any) -> Optional[str]:
        """The exact invalid-REPLAN defect, or None for other outputs."""
        if isinstance(raw, RouterDecisionModel):
            data = raw.model_dump()
        elif isinstance(raw, dict):
            data = raw
        else:
            return None
        if str(data.get("decision") or "").strip().upper() != "REPLAN":
            return None
        plan = data.get("new_plan")
        if not isinstance(plan, list) or not plan:
            return "REPLAN requires a non-empty new_plan list"
        if any(not isinstance(item, dict) or not str(
                item.get("id") or "").strip() for item in plan):
            return "every new_plan item requires a non-empty id"
        return None

    # ------------------------------------------------------------- prompt

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        run = context.get("run") or {}
        goal = context.get("goal") or {}
        digest = context.get("step_digest") or {}
        event = context.get("event") or {}
        plan: List[Dict[str, Any]] = run.get("plan") or []
        cursor = run.get("cursor")
        remaining = [s for s in plan if s.get("id") != cursor]
        current = next((s for s in plan if s.get("id") == cursor), None)
        recent = [d for d in run.get("decision_log") or []
                  if d.get("kind") in ("decision", "wake", "override")][-6:]

        agent_name = context.get("agent_name")
        who = (f"You are {agent_name}'s own judgment — the agent working "
               f"this process decides its next move through you"
               if agent_name else
               "You are the judgment of a role agent working this process")
        tier = str(context.get("maturity_tier") or "unknown").lower()
        if tier in ("student", "intern"):
            tier_guidance = ("junior — bias toward ASK_HUMAN; prefer asking "
                             "over acting on thin evidence")
        elif tier == "autonomous":
            tier_guidance = ("fully trusted — act on your own judgment; "
                             "reserve ASK_HUMAN for decisions that need a "
                             "human regardless of your skill (sign-offs, "
                             "external commitments, facts only the human "
                             "has)")
        else:
            tier_guidance = ("operational — act within the process; ask "
                             "when the evidence is thin")

        sections = [
            who + " — an INFORMAL, multi-touch-point process toward one "
            "goal, like an experienced employee, not a pipeline. Decide the "
            "next direction from the evidence below. The plan is a familiar "
            "path, not a schedule: deviate from it whenever the data says so.",
            f"ROLE: {run.get('role') or 'unspecified'}",
            f"MATURITY TIER: {tier} — {tier_guidance}",
            f"GOAL: {goal.get('status', 'unknown')} "
            f"({goal.get('satisfied', 0)}/{goal.get('total', 0)} criteria "
            f"satisfied) — {run.get('goal_id')}",
            "EVOLVING PARAMETERS (the deal/project state as known so far):\n"
            + self._json(run.get("parameters")),
        ]
        if digest:
            sections.append("JUST-FINISHED STEP RESULT:\n" + self._json(digest))
        if event:
            sections.append("NEW EVENT THAT WOKE THIS RUN:\n" + self._json(event))
        if current:
            sections.append(f"CURRENT STEP: {self._json(current)}")
        sections.append("REMAINING PLAN (advisory):\n" + self._json(remaining))
        if recent:
            sections.append("RECENT DECISIONS (oldest first):\n" + self._json([
                {k: d.get(k) for k in ("decision", "rationale", "event")
                 if d.get(k) is not None} for d in recent]))
        advisory = self._role_context(run)
        if advisory:
            sections.append(advisory)
        sections.append(
            "DECISION RULES:\n"
            "- DONE only when the evidence shows the goal is met.\n"
            "- WAIT suspends until an event (wait_spec: {event, match?, "
            "deadline?}) — e.g. email_reply from the lead, or a follow-up "
            "timer.\n"
            "- REPLAN rewrites the remaining plan (new_plan: full step list "
            "with stable ids).\n"
            "- BRANCH_NEW_CANVAS opens an additional canvas (target_step: "
            "short id; the step kind is canvas_work).\n"
            "- ASK_HUMAN when judgment, authority, or missing information "
            "warrants it.\n"
            "- ALWAYS explain the rationale in terms of the canvas data and "
            "the goal.\n"
            "Return the JSON object.")
        return "\n\n".join(sections)

    def _role_context(self, run: Dict[str, Any]) -> str:
        """Advisory role memory: this role's approved playbook steps + the
        agent's lessons. Fault-isolated — never blocks the decision."""
        parts: List[str] = []
        try:
            from core.database import get_db_session
            with get_db_session() as db:
                # Match playbooks/lessons on the goal TITLE — passing the
                # goal_id (a UUID) matched nothing and quietly starved the
                # router of the company process and the agent's lessons.
                goal_text = ""
                try:
                    from core.models import GoalObjective
                    goal_row = db.query(GoalObjective).filter(
                        GoalObjective.id == run.get("goal_id")).first()
                    if goal_row:
                        goal_text = str(goal_row.title or "")
                except Exception:
                    pass
                goal_text = goal_text or str(run.get("goal_id") or "")
                try:
                    from core.playbook_service import PlaybookService
                    pbs = PlaybookService(db, tenant_id=self.tenant_id)
                    matched = pbs.get_relevant(goal_text, canvas_type=None)
                    steps = [s for pb in (matched or [])
                             for s in (pb.get("steps") or [])][:8]
                    if steps:
                        parts.append("COMPANY PROCESS (advisory playbook steps):\n"
                                     + "\n".join(f"- {s}" for s in steps))
                except Exception:
                    pass
                agent_id = run.get("agent_id")
                if agent_id:
                    try:
                        from core.student_learning_service import get_agent_lessons
                        # goal_id = the scope being worked: lessons taught
                        # against THIS goal ride along with the agent's global
                        # guidance; other goals' deal-specific lessons stay out.
                        lessons = get_agent_lessons(db, str(agent_id),
                                                    query=goal_text, limit=4,
                                                    goal_id=run.get("goal_id"))
                        if lessons:
                            parts.append("YOUR LESSONS:\n"
                                         + "\n".join(f"- {l.get('lesson', l)}"
                                                     for l in lessons))
                    except Exception:
                        pass
        except Exception:
            pass
        return "\n\n".join(parts)

    # ----------------------------------------------------------- validation

    def _coerce(self, raw: Any) -> Optional[Dict[str, Any]]:
        if isinstance(raw, RouterDecisionModel):
            data = raw.model_dump()
        elif isinstance(raw, dict):
            data = raw
        else:
            return None
        kind = str(data.get("decision") or "").strip().upper()
        if kind not in DECISION_TYPES:
            return None
        required = _DECISIONS_REQUIRING_SPEC.get(kind)
        if required:
            value = data.get(required)
            if required == "new_plan":
                if not (isinstance(value, list) and value
                        and all(isinstance(item, dict)
                                and str(item.get("id") or "").strip()
                                for item in value)):
                    return None
            elif not isinstance(value, (dict, list)):
                return None
        try:
            confidence = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        if (confidence < MIN_CONFIDENCE
                and kind in DECISIONS_REQUIRING_HUMAN_WHEN_UNCERTAIN):
            return self._fallback(
                f"low-confidence {kind} ({confidence:.2f})", model=data.get("model"))
        decision = {
            "decision": kind,
            "rationale": str(data.get("rationale") or "")[:2000],
            "parameter_updates": data.get("parameter_updates") or {},
            "target_step": data.get("target_step"),
            "new_plan": data.get("new_plan"),
            "wait_spec": data.get("wait_spec"),
            "confidence": confidence,
            "model": data.get("model"),
        }
        if kind == "WAIT":
            spec = decision["wait_spec"] or {}
            decision["wait_spec"] = {"event": spec.get("event", "timer"),
                                     **{k: v for k, v in spec.items() if k != "event"}}
        return decision

    def _fallback(self, reason: str, model: Optional[str] = None) -> Dict[str, Any]:
        return {"decision": "ASK_HUMAN", "rationale": reason,
                "parameter_updates": {}, "target_step": None,
                "new_plan": None, "wait_spec": None,
                "confidence": 0.0, "model": model}

    # ----------------------------------------------------------------- util

    def _get_llm(self):
        if self._llm_service is not None:
            return self._llm_service
        from core.service_factory import ServiceFactory
        self._llm_service = ServiceFactory.get_llm_service(
            workspace_id=self.workspace_id, tenant_id=self.tenant_id)
        return self._llm_service

    @staticmethod
    def _json(value: Any) -> str:
        import json
        try:
            text = json.dumps(value, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(value)
        return text[:3000]
