"""
Employee-friendly automation onboarding.

Two capabilities:
- GuidedAgentFactory: turns a plain-language goal ("keep an eye on our
  invoices and flag anything overdue") into a complete agent config and
  registers it. No admin knowledge required — the employee describes the
  job, we generate the agent. New agents always start at STUDENT maturity
  so they are spoon-fed (guided, HITL-gated) until they graduate.
- AutomationSuggestionService: mines workspace history (agent executions,
  HITL approvals, workflow runs) for repeated manual patterns and proposes
  workflow automations, with a rule-based fallback when no LLM is available.

Agent-initiated use is gated by the standard trust/maturity policy via
AgentGovernanceService.can_perform_action_async — an autonomous agent can
create helpers on its own, a supervised one gets an HITL approval instead.
"""

import json
import logging
import re
import threading
from collections import Counter
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.llm_service import LLMService

logger = logging.getLogger(__name__)


# Keyword → template mapping for the no-LLM fallback path. Keys are matched
# (case-insensitive) against the employee's goal text.
_TEMPLATE_KEYWORDS = {
    "finance_analyst": ["invoice", "finance", "expense", "budget", "reconcil", "accounting", "payment"],
    "sales_assistant": ["sales", "lead", "crm", "outreach", "prospect", "deal", "pipeline"],
    "ops_coordinator": ["inventory", "logistics", "vendor", "shipping", "order", "operations", "supply"],
    "hr_assistant": ["hr", "onboarding", "leave", "policy", "recruit", "employee handbook"],
    "procurement_specialist": ["procurement", "purchase order", "po ", "sourcing", "supplier quote"],
    "knowledge_analyst": ["knowledge", "research", "summarize", "document", "wiki", "answer questions"],
    "marketing_analyst": ["marketing", "campaign", "social media", "seo", "content calendar", "newsletter"],
}


class GuidedAgentFactory:
    """Designs an agent from a plain-language goal and registers it."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService(tenant_id="default")

    async def design_agent(self, goal: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Turn a natural-language goal into an agent blueprint.

        Returns {"name", "description", "category", "capabilities",
        "template", "configuration"}. LLM-designed when possible, template
        fallback otherwise — never raises for a soft LLM failure.
        """
        blueprint = None
        try:
            blueprint = await self._design_with_llm(goal, context)
        except Exception as e:
            logger.warning(f"Guided agent LLM design failed, using template fallback: {e}")

        if not blueprint:
            blueprint = self._design_from_template(goal)
        return blueprint

    async def _design_with_llm(self, goal: str, context: Optional[str]) -> Optional[Dict[str, Any]]:
        from core.atom_meta_agent import SpecialtyAgentTemplate

        template_names = ", ".join(SpecialtyAgentTemplate.TEMPLATES.keys())
        prompt = f"""An employee describes a job they want automated:

GOAL: {goal}
{"ADDITIONAL CONTEXT: " + context if context else ""}

Design an AI agent for this. Respond ONLY with a JSON object with keys:
- "name": short human-friendly agent name (max 60 chars)
- "description": one sentence describing what it does
- "category": one of Finance, Sales, Operations, HR, Marketing, Knowledge, General
- "capabilities": list of 3-8 concrete capability strings
- "template": closest template name from [{template_names}] or "custom"
- "configuration": object with keys "system_prompt" (operating instructions for the agent) and "constraints" (list of safety constraints, must include "require human approval for destructive actions")
"""
        response = await self.llm_service.generate_completion(
            messages=[
                {"role": "system", "content": "You are an expert AI agent designer. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            model="quality",
        )
        content = (response.get("content") or "").strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        blueprint = json.loads(content)
        # Sanitize to the contract the caller expects.
        if not isinstance(blueprint, dict) or not blueprint.get("name"):
            return None
        configuration = blueprint.get("configuration") or {}
        if not isinstance(configuration, dict):
            configuration = {}
        constraints = configuration.get("constraints") or []
        if "require human approval for destructive actions" not in constraints:
            constraints.append("require human approval for destructive actions")
        configuration["constraints"] = constraints
        return {
            "name": str(blueprint["name"])[:100].strip(),
            "description": str(blueprint.get("description") or "Agent created from employee goal")[:500],
            "category": str(blueprint.get("category") or "General")[:50],
            "capabilities": [str(c) for c in (blueprint.get("capabilities") or [])][:8],
            "template": blueprint.get("template") or "custom",
            "configuration": configuration,
        }

    def _design_from_template(self, goal: str) -> Dict[str, Any]:
        from core.atom_meta_agent import SpecialtyAgentTemplate

        goal_lower = goal.lower()
        best_match, best_score = None, 0
        for template_name, keywords in _TEMPLATE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in goal_lower)
            if score > best_score:
                best_match, best_score = template_name, score

        if best_match is None:
            return {
                "name": self._name_from_goal(goal),
                "description": goal[:500],
                "category": "General",
                "capabilities": ["search", "summarize", "draft_response"],
                "template": "custom",
                "configuration": {
                    "system_prompt": f"You help with the following job: {goal}",
                    "constraints": ["require human approval for destructive actions"],
                },
            }

        template = SpecialtyAgentTemplate.TEMPLATES[best_match]
        return {
            "name": template["name"],
            "description": template["description"],
            "category": template["category"],
            "capabilities": list(template.get("capabilities", [])),
            "template": best_match,
            "configuration": {
                "system_prompt": f"You are a {template['name']}. Employee goal: {goal}",
                "constraints": ["require human approval for destructive actions"],
            },
        }

    @staticmethod
    def _name_from_goal(goal: str) -> str:
        words = re.findall(r"[a-zA-Z]+", goal)[:4]
        return (" ".join(words).title() + " Assistant")[:100]


class AutomationSuggestionService:
    """Mines workspace history and proposes workflow automations."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService(tenant_id="default")

    async def generate_suggestions(
        self,
        db: Session,
        workspace_id: str = "default",
        tenant_id: str = "default",
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Return automation suggestions derived from real usage history."""
        history = self._mine_history(db, workspace_id, tenant_id)

        suggestions = None
        try:
            suggestions = await self._suggest_with_llm(history, limit)
        except Exception as e:
            logger.warning(f"Automation suggestion LLM call failed, using rule-based fallback: {e}")

        if not suggestions:
            suggestions = self._rule_based_suggestions(history, limit)

        return {"history_summary": history["summary"], "suggestions": suggestions[:limit]}

    # ------------------------------------------------------------------
    # History mining
    # ------------------------------------------------------------------

    def _mine_history(self, db: Session, workspace_id: str, tenant_id: str) -> Dict[str, Any]:
        from core.models import AgentExecution, HITLAction, WorkflowExecutionLog

        # Frequently manually-triggered agent runs — the prime automation
        # candidates (a human repeatedly kicking off the same agent = a job
        # that wants a workflow trigger).
        manual_runs = Counter()
        try:
            rows = (
                db.query(AgentExecution)
                .filter(
                    AgentExecution.workspace_id == workspace_id,
                    AgentExecution.triggered_by == "manual",
                )
                .order_by(AgentExecution.started_at.desc())
                .limit(1000)
                .all()
            )
            for row in rows:
                label = row.input_summary or "unnamed task"
                manual_runs[str(label)[:120]] += 1
        except Exception as e:
            logger.debug(f"AgentExecution mining skipped: {e}")

        # Human-approved action types — what people keep green-lighting is
        # what they would automate if trust allowed.
        approved_actions = Counter()
        try:
            hitl_rows = (
                db.query(HITLAction)
                .filter(HITLAction.workspace_id == workspace_id)
                .order_by(HITLAction.created_at.desc())
                .limit(1000)
                .all()
            )
            for row in hitl_rows:
                if row.status == "approved":
                    approved_actions[row.action_type or "unknown"] += 1
        except Exception as e:
            logger.debug(f"HITLAction mining skipped: {e}")

        # Existing workflow volume — where automation already lives and
        # could be extended.
        workflow_runs = Counter()
        try:
            wf_rows = (
                db.query(WorkflowExecutionLog)
                .order_by(WorkflowExecutionLog.start_time.desc())
                .limit(2000)
                .all()
            )
            for row in wf_rows:
                workflow_runs[row.workflow_id or "unknown"] += 1
        except Exception as e:
            logger.debug(f"WorkflowExecutionLog mining skipped: {e}")

        top_manual = manual_runs.most_common(10)
        top_approved = approved_actions.most_common(10)
        top_workflows = workflow_runs.most_common(10)

        summary = {
            "frequent_manual_agent_runs": [
                {"task": task, "count": count} for task, count in top_manual
            ],
            "frequently_approved_actions": [
                {"action": action, "approvals": count} for action, count in top_approved
            ],
            "most_run_workflows": [
                {"workflow_id": wf, "runs": count} for wf, count in top_workflows
            ],
        }
        return {
            "manual_runs": manual_runs,
            "approved_actions": approved_actions,
            "workflow_runs": workflow_runs,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Suggestion generation
    # ------------------------------------------------------------------

    async def _suggest_with_llm(self, history: Dict[str, Any], limit: int) -> Optional[List[Dict[str, Any]]]:
        prompt = f"""Workspace usage history (JSON):

{json.dumps(history["summary"], indent=2)}

Based ONLY on this history, propose the top {limit} workflow automations. Respond ONLY with a JSON array where each item has:
- "title": short name for the workflow
- "description": what it automates and why (reference the evidence)
- "trigger": what starts it (schedule, event, or manual)
- "steps": ordered list of 2-6 step descriptions
- "evidence": the history signal that motivated this (e.g. "task X run manually 14 times")
- "estimated_time_saved_minutes_per_month": integer
"""
        response = await self.llm_service.generate_completion(
            messages=[
                {"role": "system", "content": "You are an automation consultant. Output only a valid JSON array."},
                {"role": "user", "content": prompt},
            ],
            model="quality",
        )
        content = (response.get("content") or "").strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        suggestions = json.loads(content)
        if not isinstance(suggestions, list):
            return None
        return [s for s in suggestions if isinstance(s, dict) and s.get("title")]

    def _rule_based_suggestions(self, history: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        suggestions = []
        for task, count in history["manual_runs"].most_common(limit):
            if count < 2:
                continue
            suggestions.append({
                "title": f"Automate: {task[:80]}",
                "description": (
                    f"'{task}' has been run manually {count} times. Wrapping it in a "
                    "scheduled or event-triggered workflow removes the repeated manual effort."
                ),
                "trigger": "schedule or event",
                "steps": [f"Run the agent task '{task}'", "notify the requester with the result"],
                "evidence": f"manual run count: {count}",
                "estimated_time_saved_minutes_per_month": count * 15,
            })

        for action, count in history["approved_actions"].most_common(limit):
            if count < 3:
                continue
            suggestions.append({
                "title": f"Auto-approve low-risk '{action}' actions",
                "description": (
                    f"'{action}' has been approved by a human {count} times with no rejections "
                    "in recent history — a candidate for graduated autonomy (auto-run with audit)."
                ),
                "trigger": "each time the action is requested",
                "steps": ["agent requests the action", "auto-approve if confidence is high", "log for audit"],
                "evidence": f"approvals: {count}",
                "estimated_time_saved_minutes_per_month": count * 5,
            })
        return suggestions[:limit]


_instance: Optional[GuidedAgentFactory] = None
_suggestion_instance: Optional[AutomationSuggestionService] = None
_instance_lock = threading.Lock()


def get_guided_agent_factory() -> GuidedAgentFactory:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = GuidedAgentFactory()
    return _instance


def get_automation_suggestion_service() -> AutomationSuggestionService:
    global _suggestion_instance
    if _suggestion_instance is None:
        with _instance_lock:
            if _suggestion_instance is None:
                _suggestion_instance = AutomationSuggestionService()
    return _suggestion_instance
