"""Pinned-model decider: the operator loop's brain, routing-frozen.

For the Phase 4 experiment the pre-registration requires "same pinned model,
frozen routing, no runtime ladder drift". `JsonVisionDecider` routes through
LLMService, whose ladder re-ranks per call — for a live vision payload it
can bypass the pinned model entirely (observed 2026-09-21: explicit
opencode-go picks were vision-gate-vetoed and fell through to a 402-dead
openrouter rung). This decider calls the handler's opencode-go client
DIRECTLY: one provider, one model, zero ladder. Same prompts, same JSON
contract, same action parsing as the default decider.

Bounded parse retry: the loop treats a None decision as fatal on the first
step, so a transient unparseable reply is retried once before giving up.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.operator.loop import (  # noqa: E402
    BROWSER_ACTIONS,
    JsonVisionDecider,
    OperatorAction,
    _extract_json,
)


class PinnedVisionDecider(JsonVisionDecider):
    """JsonVisionDecider with the model call pinned to one provider client."""

    def __init__(self, client: Any, model: str,
                 tenant_id: str = "default", attempts: int = 2):
        super().__init__(tenant_id=tenant_id)
        self._client = client
        self._model = model
        self._attempts = attempts

    async def _call(self, messages: list, max_tokens: int) -> str:
        response = await asyncio.wait_for(self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.1,
        ), timeout=120)
        return (response.choices[0].message.content or "").strip()

    async def decide(self, task: str, observation,
                     history: Optional[list] = None) -> Optional[Dict[str, Any]]:
        history = history or []
        history_block = "\n".join(history[-8:]) or \
            "(none yet — this is the first step)"
        page_facts = (
            f"CURRENT PAGE: url={observation.url or '(blank)'} "
            f"title={observation.title or '(none)'}\n"
            f"VISIBLE TEXT (excerpt):\n{(observation.page_text or '')[:2000]}"
        )
        content: list = [
            {"type": "text", "text": (
                f"TASK: {task}\n\n"
                f"ACTIONS TAKEN SO FAR:\n{history_block}\n\n"
                f"{page_facts}\n\n"
                "The attached screenshot is the CURRENT page state. Decide "
                "the single next action (or done).")},
        ]
        if observation.screenshot_b64:
            content.append({"type": "image_url", "image_url": {
                "url": f"data:image/png;base64,{observation.screenshot_b64}"}})
        messages = [
            {"role": "system", "content": self._system_prompt(observation.viewport)},
            {"role": "user", "content": content},
        ]

        text = ""
        for attempt in range(self._attempts):
            try:
                text = await self._call(messages, max_tokens=1024)
            except Exception as exc:
                # Provider/auth/network failure: infrastructure, not an
                # agent decision. Re-raise so OperatorLoop records error=
                # and the adapter classifies HARNESS_ERROR — returning a
                # synthetic done=True here would launder infra failures
                # into agent_fail (or worse, into passes via a lucky
                # verifier). Parse failures below are different: they go
                # through the loop's own unparseable-step handling.
                if attempt == self._attempts - 1:
                    raise RuntimeError(
                        f"pinned model call failed after {self._attempts} "
                        f"attempts: {type(exc).__name__}: {exc}"
                    ) from exc
                continue
            data = _extract_json(text)
            if data is not None:
                break
        else:
            return None
        if data is None:
            return None

        done = bool(data.get("done"))
        action = None
        action_data = data.get("action") or {}
        action_type = str(action_data.get("action_type", "") or "").lower()
        if not done and action_type and action_type != "done":
            if action_type not in BROWSER_ACTIONS:
                return None  # unknown action — let the loop re-plan
            action = OperatorAction(
                action_type=action_type,
                parameters=action_data.get("parameters") or {},
                confidence=float(action_data.get("confidence", 1.0) or 1.0),
                description=action_data.get("description", "") or action_type,
            )
        elif action_type == "done":
            done = True
        return {"done": done, "action": action,
                "reasoning": data.get("reasoning", ""),
                "summary": data.get("summary", "")}
