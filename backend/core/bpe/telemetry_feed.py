"""BPE telemetry → harness-evolution weakness feed (plan Phase 3).

Converts ``bpe.*`` observability spans into weakness patterns in the SAME
shape ``HarnessEvolutionService.mine_weaknesses`` returns (step_type / tool /
model_family / failure_count / examples), so ``propose_mutation`` can treat
harness misbehavior like any other mined failure:

- **Errored consults** — spans with ``success=False`` cluster per meta-action
  (``tool="bpe.track"`` etc., ``step_type="harness_action"``).
- **Negative consult value** — ``bpe.policy_episode`` spans showing an agent
  whose value EMA stayed below zero with meaningful consult traffic
  (``step_type="consult_value"``) — the signal that this agent's workspace
  exposure is hurting, i.e. exactly what a harness patch should address.

This is the read side of the AlphaEvolve-lite loop in
``core/bpe/evolution.py``: mined weakness + policy fitness are the
evaluator signals that guide harness-config search.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# A negative-value agent only becomes a weakness signal once there is enough
# episode evidence (mirrors the consult policy's own gate) and the deficit
# is material.
MIN_EPISODES = 3
NEGATIVE_VALUE_FLOOR = -0.2


def collect_bpe_weakness_patterns() -> List[Dict[str, Any]]:
    """Build weakness patterns from recent bpe.* spans. Never raises."""
    patterns: List[Dict[str, Any]] = {}
    try:
        from core.observability.tracing import get_recent_spans

        spans = get_recent_spans(limit=1000, name_prefix="bpe.")
    except Exception as e:
        logger.debug("bpe span read failed: %s", e)
        return []

    for span in spans:
        attrs = span.get("attributes") or {}
        name = str(span.get("name") or "")

        if name == "bpe.policy_episode":
            agent_id = str(attrs.get("agent_id") or "unknown")
            episodes = int(attrs.get("episodes") or 0)
            value_ema = float(attrs.get("value_ema") or 0.0)
            if episodes >= MIN_EPISODES and value_ema < NEGATIVE_VALUE_FLOOR:
                key = ("consult_value", agent_id)
                pat = patterns.setdefault(key, {
                    "step_type": "consult_value",
                    "tool": "workspace.block",
                    "model_family": None,
                    "failure_count": 0,
                    "examples": [],
                    "agent_id": agent_id,
                })
                pat["failure_count"] = episodes
                if len(pat["examples"]) < 3:
                    pat["examples"].append({
                        "agent_id": agent_id,
                        "value_ema": value_ema,
                        "episodes": episodes,
                    })
            continue

        if str(span.get("status")) != "error":
            continue
        action = name.replace("bpe.", "", 1) or "unknown"
        key = ("harness_action", action)
        pat = patterns.setdefault(key, {
            "step_type": "harness_action",
            "tool": f"bpe.{action}",
            "model_family": None,
            "failure_count": 0,
            "examples": [],
        })
        pat["failure_count"] += 1
        if len(pat["examples"]) < 3:
            pat["examples"].append({
                "agent_id": attrs.get("agent_id"),
                "scope_key": attrs.get("scope_key"),
            })

    return list(patterns.values())
