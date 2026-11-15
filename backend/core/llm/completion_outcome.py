"""Shared text outcome from a canonical ``LLMService.generate_completion``.

The canonical completion facade returns a typed mapping. A provider/policy/
budget failure now arrives as ``success=False`` with EMPTY ``content``/``text``
and a typed ``failure`` mapping. Consumers that only need text must not:
  * call a nonexistent ``generate_response`` method on ``LLMService``;
  * publish the legacy failure string as generated content; or
  * stringify a malformed non-string content value.

This helper is deliberately small and pure. It is not a routing, fallback or
provider-selection layer.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def completion_text_outcome(
    result: Any,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Split a canonical completion result into ``(text, failure)``.

    Contract:
    * non-mapping result -> ``invalid_completion_result`` failure;
    * explicit ``success=False`` -> the producer's typed failure, or a
      normalized ``generation_failed``;
    * accepted content must be a real string (``content`` preferred, legacy
      string ``text`` only when content is absent/None). Dict/list/bool/number
      is ``invalid_completion_content``, never ``str(value)``;
    * whitespace-only text is ``empty_generation``;
    * only a non-empty accepted string returns ``(text, None)``.
    """
    if not isinstance(result, dict):
        return None, {
            "reason": "invalid_completion_result",
            "message": "LLM completion returned no result object",
        }
    if result.get("success") is False:
        failure = result.get("failure")
        if not isinstance(failure, dict):
            failure = {
                "reason": "generation_failed",
                "message": str(
                    result.get("error") or "LLM generation failed"),
            }
        return None, failure
    raw_content = result.get("content")
    if raw_content is None:
        raw_content = result.get("text")
    if not isinstance(raw_content, str):
        return None, {
            "reason": "invalid_completion_content",
            "message": "LLM completion content is not text",
        }
    text = raw_content.strip()
    if not text:
        return None, {
            "reason": "empty_generation",
            "message": "LLM generation returned no text",
        }
    return text, None
