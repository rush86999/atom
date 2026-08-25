"""
Sales decision-catalog builder — the business-discovery step.

"Learn the business before you automate the business." This module classifies
historical customer emails into structured (Situation -> Action -> Human?)
rows the future sales agent can consult, then aggregates them into a decision
catalog. It uses the free opencode-go model chain (same one as the Outlook
automation drafts) so the discovery step works without a paid LLM balance.
"""

import asyncio
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# The discovery questions the classifier answers for each email.
CATALOG_DIMENSIONS = [
    "intent",
    "customer_question",
    "sales_action",
    "info_needed",
    "systems_checked",
    "people_contacted",
    "decision_reason",
    "exception",
    "outcome",
    "needs_human",
    "business_rule",
]

_DEFAULT_VALUES: Dict[str, Any] = {
    "intent": "unknown",
    "customer_question": "",
    "sales_action": "",
    "info_needed": [],
    "systems_checked": [],
    "people_contacted": [],
    "decision_reason": "",
    "exception": "",
    "outcome": "",
    "needs_human": False,
    "business_rule": "",
}

_CLASSIFIER_SYSTEM_INSTRUCTION = (
    "You are a business-analyst assistant for Brennan Machinery, a machinery "
    "sales company. You classify customer emails into structured fields for "
    "a sales decision catalog. Always respond with JSON only, no prose."
)


# --------------------------------------------------------------------------- #
# Prompt + parsing (pure)
# --------------------------------------------------------------------------- #

def _email_text(email: Dict[str, Any]) -> str:
    body = email.get("body")
    if isinstance(body, dict):
        content = body.get("content", "")
    else:
        content = str(body or "")
    return (content or email.get("body_preview") or "")[:3000]


def _sender(email: Dict[str, Any]) -> tuple:
    from_field = email.get("from_field") or {}
    ea = from_field.get("emailAddress") or {}
    return ea.get("name", ""), ea.get("address", "")


def build_classification_prompt(email: Dict[str, Any]) -> str:
    """Build the classification prompt for one customer email (pure)."""
    name, addr = _sender(email)
    return f"""Classify this customer email for a sales decision catalog.

From: {name} <{addr}> ({email.get('received_date_time', '')})
Subject: {email.get('subject', '')}
Body:
{_email_text(email)}

Answer these questions about what happened (email content + your judgment):
- intent: what was the customer asking? (request_quote, service_call, parts, question, complaint, ...)
- customer_question: one line summarising the ask
- sales_action: what should the salesperson/agent do next? (check_inventory, search_vendor, calculate_quote, ask_human, draft_quote, ...)
- info_needed: what information is missing before an answer/quote?
- systems_checked: which systems would be consulted? (zoho_inventory, price_list, emails, shipping, vendor, ...)
- people_contacted: who inside/outside the company would be involved? (sales, purchasing, shipping, vendor, jeff, ...)
- decision_reason: why this action (business logic)?
- exception: any special condition (CSA, wiring, oversized, custom, ...) or empty string
- outcome: what should happen next / eventual result
- needs_human: true if a human must decide/approve before proceeding
- business_rule: a short reusable rule name, e.g. "standard machine + stock available"

Reply with JSON only, exactly this shape:
{{
  "intent": "...",
  "customer_question": "...",
  "sales_action": "...",
  "info_needed": ["..."],
  "systems_checked": ["..."],
  "people_contacted": ["..."],
  "decision_reason": "...",
  "exception": "...",
  "outcome": "...",
  "needs_human": true,
  "business_rule": "..."
}}"""


def _try_parse_json(cand: str) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(cand)
        return obj if isinstance(obj, dict) else None
    except (ValueError, TypeError):
        pass
    # Salvage truncated JSON: try the last few closing-brace positions.
    start = cand.find("{")
    if start == -1:
        return None
    closes = [i for i in range(len(cand) - 1, start, -1) if cand[i] == "}"]
    for i in closes[:5]:
        try:
            obj = json.loads(cand[start : i + 1])
            if isinstance(obj, dict):
                return obj
        except (ValueError, TypeError):
            continue
    return None


def _salvage_partial_json(cand: str) -> Optional[Dict[str, Any]]:
    """Recover complete key-value pairs from truncated JSON (e.g. cut mid
    string/number) — enough to keep earlier fields like intent/action."""
    out: Dict[str, Any] = {}
    pattern = (
        r'"([A-Za-z_]+)"\s*:\s*'
        r'("(?:[^"\\]|\\.)*"|\[[^\]]*\]|true|false|null|-?\d+(?:\.\d+)?)'
    )
    for m in re.finditer(pattern, cand):
        key, val = m.group(1), m.group(2)
        try:
            out[key] = json.loads(val)
        except (ValueError, TypeError):
            out[key] = val
    return out if out else None


def parse_classification(text: str) -> Dict[str, Any]:
    """Extract a classification dict from the LLM reply. Robust to fenced
    code blocks, stray prose, and truncation. Missing keys get defaults."""
    result = dict(_DEFAULT_VALUES)
    if not text:
        return result
    candidates = [text]
    candidates += re.findall(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    for cand in candidates:
        parsed = _try_parse_json(cand)
        if parsed is None:
            parsed = _salvage_partial_json(cand)
        if parsed is not None:
            for k in _DEFAULT_VALUES:
                if k in parsed:
                    result[k] = parsed[k]
            return result
    return result


# --------------------------------------------------------------------------- #
# Classification (async)
# --------------------------------------------------------------------------- #

async def _default_llm_call(prompt: str, system_instruction: str) -> str:
    """Direct free opencode-go call (fallback chain + retries). Returns ""
    when the client is missing or every model fails — the caller then treats
    the email as unclassifiable rather than raising."""
    try:
        from core.llm_service import get_llm_service
        from outlook_automation_service import (
            _call_free_model_sync,
            _opencode_free_model_chain,
        )

        llm = get_llm_service()
        handler = getattr(llm, "handler", None)
        client = (getattr(handler, "clients", None) or {}).get("opencode-go")
        if client is not None:
            for model in _opencode_free_model_chain():
                content = await asyncio.to_thread(
                    _call_free_model_sync, client, model, prompt, system_instruction
                )
                if content:
                    return content
                await asyncio.sleep(0.3)
    except Exception as e:
        logger.debug(f"sales catalog: free-model call failed: {e}")
    return ""


async def classify_email(
    email: Dict[str, Any],
    call_llm: Optional[Callable[[str, str], Any]] = None,
) -> Dict[str, Any]:
    """Classify one customer email into catalog dimensions. Never raises."""
    if call_llm is None:
        call_llm = _default_llm_call
    prompt = build_classification_prompt(email)
    try:
        text = await asyncio.wait_for(
            call_llm(prompt, _CLASSIFIER_SYSTEM_INSTRUCTION), timeout=30
        )
    except Exception as e:
        logger.debug(f"sales catalog: classify failed: {e}")
        text = ""
    result = parse_classification(text)
    result["subject"] = email.get("subject", "")
    return result


# --------------------------------------------------------------------------- #
# Aggregation (decision table)
# --------------------------------------------------------------------------- #

def aggregate_catalog(classifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group classifications into decision-catalog rows: situation rule ->
    count, dominant actions, whether a human was ever needed, systems checked,
    exceptions seen, example subjects. Sorted by count desc."""
    groups: Dict[str, Dict[str, Any]] = {}
    for c in classifications:
        rule = (c.get("business_rule") or "").strip() or (
            f"{c.get('intent') or 'unknown'} -> {c.get('sales_action') or '?'}"
        )
        g = groups.setdefault(
            rule,
            {
                "rule": rule,
                "count": 0,
                "needs_human": False,
                "actions": {},
                "systems": set(),
                "exceptions": set(),
                "examples": [],
            },
        )
        g["count"] += 1
        action = str(c.get("sales_action") or "?")
        g["actions"][action] = g["actions"].get(action, 0) + 1
        if c.get("needs_human"):
            g["needs_human"] = True
        for s in c.get("systems_checked") or []:
            if s:
                g["systems"].add(str(s))
        exc = (c.get("exception") or "").strip()
        if exc:
            g["exceptions"].add(exc)
        subject = c.get("subject")
        if subject and subject not in g["examples"]:
            g["examples"].append(str(subject))

    rows = []
    for g in groups.values():
        g["systems"] = sorted(g["systems"])
        g["exceptions"] = sorted(g["exceptions"])
        g["examples"] = g["examples"][:3]
        rows.append(g)
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows
