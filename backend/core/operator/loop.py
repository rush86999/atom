"""OperatorLoop — the computer-use decide loop, backend-agnostic.

The rails are the ones LuxModel.run_task established (and
tests/test_computer_use_gpt6_astra.py pins for the desktop path); mature
computer-use harnesses (Anthropic's computer-use tool, OpenAI's CUA) all
work this way:

- ONE action per fresh observation — desktop/page state changes under
  you, and a plan built on a stale screenshot misfires.
- Hard step budget (ATOM_COMPUTER_USE_MAX_STEPS, default 15): bounds the
  loop even when the model never says done.
- Governance and guardrail blocks are HARD stops — one blocked action
  aborts the task; they are policy, not retryable failures.
- Three consecutive failed actions abort (a persistently misfiring model
  is lost; more steps just churn).
- stop_event lets operator_stop_task halt a run between steps.

The decide-step protocol is pluggable. v1 default: JsonVisionDecider —
any vision+tools model the BPC router serves can run it via
LLMService.generate_completion(task_type="computer_use",
image_payload=...). Native CUA protocols (Anthropic computer_20250124
tool-use, OpenAI Responses computer_use_preview) are phase 2 and will
implement the same ``decide`` contract.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from core.lux_config import lux_config
from core.operator.session import BROWSER_ACTIONS

logger = logging.getLogger(__name__)

# History window shown to the model each step: enough context to follow a
# plan, small enough to keep per-step prompt cost flat across long runs.
_HISTORY_WINDOW = 8


@dataclass
class OperatorAction:
    action_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    description: str = ""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON object extraction from a model reply (fenced code
    blocks, leading prose, trailing prose). Same approach as LuxModel."""
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


class JsonVisionDecider:
    """Default decide-step protocol: one JSON action per observation.

    Works with every vision+tools model the router serves; the explicit
    model pick comes from lux_config (ATOM_COMPUTER_USE_MODEL, default
    gpt-6-astra — the ScreenSpot-Pro grounding leader).
    """

    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id

    def _system_prompt(self, viewport) -> str:
        return (
            "You are a computer-use operator controlling a real Chromium "
            "browser through one action per step. After each action you "
            "receive a fresh screenshot plus the page URL and visible text. "
            "Respond with EXACTLY ONE JSON object and nothing else:\n"
            '{"reasoning": "why this action", "action": {"action_type": '
            '"...", "parameters": {...}, "confidence": 0.0-1.0}, "done": '
            'false, "summary": "final answer once done"}\n'
            "Set done=true (with summary) when the task is complete or "
            "clearly impossible. Action types: navigate (parameters.url — "
            "full http(s) URL), click (parameters.coordinates [x,y] in "
            "viewport pixels, or parameters.selector CSS), type "
            "(parameters.text — click the input first), press_key "
            '(parameters.keys e.g. ["cmd","a"]), scroll '
            "(parameters.direction up/down, parameters.amount 1-10), "
            "find_element (parameters.text — verify text is on the page), "
            "wait (parameters.duration seconds), screenshot (no-op — you "
            "always receive a fresh screenshot).\n"
            f"Coordinates are CSS pixels on a {viewport[0]}x{viewport[1]} "
            "viewport, (0,0) top-left. Stay strictly inside those bounds."
        )

    async def decide(self, task: str, observation,
                     history: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Returns {done, action: Optional[OperatorAction], reasoning,
        summary} or None when the model call/parse failed."""
        from core.llm_service import LLMService

        history = history or []
        history_block = "\n".join(history[-_HISTORY_WINDOW:]) or \
            "(none yet — this is the first step)"
        page_facts = (
            f"CURRENT PAGE: url={observation.url or '(blank)'} "
            f"title={observation.title or '(none)'}\n"
            f"VISIBLE TEXT (excerpt):\n{(observation.page_text or '')[:2000]}"
        )
        messages = [
            {"role": "system",
             "content": self._system_prompt(observation.viewport)},
            {"role": "user", "content": (
                f"TASK: {task}\n\n"
                f"ACTIONS TAKEN SO FAR:\n{history_block}\n\n"
                f"{page_facts}\n\n"
                "The attached screenshot is the CURRENT page state. Decide "
                "the single next action (or done)."
            )},
        ]

        kwargs: Dict[str, Any] = {
            "task_type": "computer_use",
            "max_tokens": 1024,
            "temperature": 0.1,
        }
        if observation.screenshot_b64:
            kwargs["image_payload"] = observation.screenshot_b64

        response = await LLMService(tenant_id=self.tenant_id).generate_completion(
            messages=messages,
            model=lux_config.get_computer_use_model(),
            tenant_id=self.tenant_id,
            **kwargs,
        )
        if not response.get("success"):
            logger.error(f"operator decide step failed: {response.get('error')}")
            return None

        data = _extract_json(response.get("content", "") or "")
        if data is None:
            logger.error("operator decide step returned no parseable JSON")
            return None

        done = bool(data.get("done"))
        action: Optional[OperatorAction] = None
        action_data = data.get("action") or {}
        action_type = str(action_data.get("action_type", "") or "").lower()
        if not done and action_type and action_type != "done":
            if action_type not in BROWSER_ACTIONS:
                # Unknown action type: treat the step as failed (None) so
                # the loop re-plans from a fresh observation.
                logger.warning(f"unknown operator action type '{action_type}'")
                return None
            action = OperatorAction(
                action_type=action_type,
                parameters=action_data.get("parameters") or {},
                confidence=float(action_data.get("confidence", 1.0) or 1.0),
                description=action_data.get("description", "") or action_type,
            )
        elif action_type == "done":
            done = True

        return {
            "done": done,
            "action": action,
            "reasoning": data.get("reasoning", ""),
            "summary": data.get("summary", ""),
        }


class OperatorLoop:
    """observe → decide → act → re-observe, over any backend exposing
    observe()/execute(action_dict)/close()."""

    def __init__(
        self,
        backend,
        decider: Optional[Callable] = None,
        max_steps: Optional[int] = None,
        stop_event: Optional[asyncio.Event] = None,
        step_settle_seconds: float = 1.0,
    ):
        self.backend = backend
        self.decider = decider
        self.max_steps = max_steps if max_steps is not None else lux_config.get_max_steps()
        self.stop_event = stop_event
        self.step_settle_seconds = step_settle_seconds

    async def run(self, task: str) -> Dict[str, Any]:
        start_time = datetime.now()
        executed: List[Dict[str, Any]] = []
        history: List[str] = []
        final_summary = ""
        last_url = ""
        last_title = ""
        task_done = False
        stopped = False
        blocked_reason: Optional[str] = None
        consecutive_failures = 0

        try:
            for step in range(self.max_steps):
                if self.stop_event is not None and self.stop_event.is_set():
                    stopped = True
                    break

                observation = await self.backend.observe()
                last_url, last_title = observation.url, observation.title
                if observation.error:
                    # Backend broken (browser died, session expired): retrying
                    # the same broken observation is pointless.
                    blocked_reason = f"observation failed: {observation.error}"
                    break

                decider = self.decider or JsonVisionDecider()
                decision = decider.decide(task, observation, history)
                if asyncio.iscoroutine(decision):
                    decision = await decision

                if decision is None:
                    if not executed:
                        return {
                            "success": False,
                            "error": "no action could be decided for the task",
                            "task": task,
                            "timestamp": start_time.isoformat(),
                        }
                    logger.warning("operator step unparseable — stopping task")
                    break

                if decision.get("done"):
                    task_done = True
                    final_summary = (decision.get("summary")
                                     or decision.get("reasoning") or "")
                    break

                action = decision.get("action")
                if action is None:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        break
                    continue

                result = await self.backend.execute({
                    "action_type": action.action_type,
                    "parameters": action.parameters,
                })
                blocked = (result.get("blocked_by_governance")
                           or result.get("blocked_by_guardrail"))
                if blocked:
                    blocked_reason = result.get("error") or "action blocked"
                    executed.append({
                        "step": step + 1,
                        "action": action.description or action.action_type,
                        "action_type": action.action_type,
                        "success": False,
                        "blocked": True,
                        "confidence": action.confidence,
                    })
                    break

                success = bool(result.get("success"))
                executed.append({
                    "step": step + 1,
                    "action": action.description or action.action_type,
                    "action_type": action.action_type,
                    "success": success,
                    "confidence": action.confidence,
                    "detail": {k: v for k, v in result.items()
                               if k in ("url", "title", "found", "error")},
                })
                history.append(
                    f"{step + 1}. {action.action_type}("
                    f"{json.dumps(action.parameters, default=str)}) -> "
                    f"{'ok' if success else 'FAILED'}"
                )

                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        logger.warning("three consecutive failed operator "
                                       "actions — aborting task")
                        break

                # Let the page settle so the next observation reflects the
                # action's effect.
                await asyncio.sleep(self.step_settle_seconds)

            return {
                "success": (task_done or any(a.get("success")
                                             for a in executed)),
                "task": task,
                "actions": executed,
                "steps": len(executed),
                "done": task_done,
                "stopped": stopped,
                "blocked": bool(blocked_reason),
                "error": blocked_reason,
                "summary": final_summary,
                "final_url": last_url,
                "final_title": last_title,
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
            }

        except Exception as exc:
            logger.error(f"operator task failed: {exc}")
            return {
                "success": False,
                "task": task,
                "actions": executed,
                "steps": len(executed),
                "done": False,
                "stopped": stopped,
                "error": str(exc),
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
            }
