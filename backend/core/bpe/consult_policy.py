"""Cost-aware consult policy for the BPE workspace (plan Phase 2).

EvoHarness-RL's cost mechanism: harness actions consume the same budget as
environment actions, so the agent must learn when consultation is worth its
cost. Without weight training (the RL stage is out of scope here), the
policy-learning moves *outside* the model — this module scores consultation
value per agent from episode outcomes (EMA, the ``LearningBasedRouter``
pattern) and gates workspace exposure accordingly:

- **Complexity gate** — simple turns never see the block (prompt bloat
  guard; mirrors R_eff penalizing needless consultation).
- **Value gate** — if episodes with consults underperform the agent's
  no-consult baseline (EMA < 0 over enough episodes), rendering is
  suppressed. Feedback flows in via :meth:`ConsultPolicy.record_episode`.
- **Annealing analog** — the paper observed ``commit``/``note`` decay to
  zero while ``recall`` persists longest. We mirror the render-side effect:
  once an agent's commit+note share of consults falls below
  :data:`RECALL_ONLY_SHARE`, the rendered block keeps experience/progress
  state but drops the commit/note prompt line (routines internalized).

Shadow-first: outcome recording is always on (it only touches in-memory
EMAs + telemetry); gating applies only when ``ATOM_BPE_CONSULT_POLICY`` is
enabled. Never raises.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

from core.bpe.telemetry import record_bpe_span

logger = logging.getLogger(__name__)

EMA_ALPHA = 0.3                 # EMA responsiveness (LearningBasedRouter-style)
MIN_EPISODES_FOR_VALUE_GATE = 5  # don't gate on noise
VALUE_SUPPRESS_THRESHOLD = 0.0   # suppress when EMA reward < 0
RECALL_ONLY_SHARE = 0.1          # commit+note share below this → recall-only
RECALL_ONLY_MIN_EPISODES = 10
SIMPLE_COMPLEXITIES = ("simple",)
POLICY_FLAG = "ATOM_BPE_CONSULT_POLICY"


def policy_gating_enabled() -> bool:
    return os.getenv(POLICY_FLAG, "false").strip().lower() in ("1", "true", "yes")


class AgentConsultState:
    """Per-agent EMA state (in-process; resets with the registry)."""

    __slots__ = ("episodes", "value_ema", "consults_total", "commit_note_total",
                 "consult_episodes", "updated_at")

    def __init__(self) -> None:
        self.episodes = 0
        self.value_ema = 0.0
        self.consults_total = 0
        self.commit_note_total = 0
        self.consult_episodes = 0
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episodes": self.episodes,
            "value_ema": round(self.value_ema, 4),
            "consults_total": self.consults_total,
            "commit_note_total": self.commit_note_total,
            "consult_episodes": self.consult_episodes,
            "updated_at": self.updated_at,
        }


class ConsultPolicy:
    """Complexity + value gating over workspace exposure. In-memory, cheap."""

    def __init__(self) -> None:
        self._agents: Dict[str, AgentConsultState] = {}

    # ------------------------------------------------------------------
    # Rendering decisions (called per _react_step)
    # ------------------------------------------------------------------

    def should_render(self, agent_id: str, complexity: str,
                      workspace_nonempty: bool) -> bool:
        """Whether the BPE block should be rendered for this turn."""
        if not workspace_nonempty:
            return False
        if str(complexity or "").lower() in SIMPLE_COMPLEXITIES:
            return False
        if not policy_gating_enabled():
            return True  # shadow: flag off → render whenever there is state
        state = self._agents.get(str(agent_id))
        if state is None or state.episodes < MIN_EPISODES_FOR_VALUE_GATE:
            return True
        return state.value_ema >= VALUE_SUPPRESS_THRESHOLD

    def render_mode(self, agent_id: str) -> str:
        """'full' or 'recall_only' (annealing: commit/note internalized)."""
        state = self._agents.get(str(agent_id))
        if state is None or state.episodes < RECALL_ONLY_MIN_EPISODES:
            return "full"
        if state.consults_total == 0:
            return "full"
        share = state.commit_note_total / max(1, state.consults_total)
        return "recall_only" if share < RECALL_ONLY_SHARE else "full"

    # ------------------------------------------------------------------
    # Feedback (called once per finished run)
    # ------------------------------------------------------------------

    def record_episode(self, agent_id: str, consult_count: int,
                       success: bool, step_efficiency: float) -> None:
        """Update the per-agent value EMA from one finished run.

        Reward: +1 success with sane step efficiency, -1 otherwise — the
        analog of EvoHarness's success-gated efficiency reward, learned
        post-hoc instead of via GRPO.
        """
        agent_id = str(agent_id)
        state = self._agents.setdefault(agent_id, AgentConsultState())
        reward = 1.0 if (success and float(step_efficiency or 1.0) <= 1.5) else -1.0
        if state.episodes == 0:
            state.value_ema = reward
        else:
            state.value_ema += EMA_ALPHA * (reward - state.value_ema)
        state.episodes += 1
        if consult_count > 0:
            state.consults_total += consult_count
            state.consult_episodes += 1
        state.updated_at = time.time()
        record_bpe_span(
            action="policy_episode",
            agent_id=agent_id,
            success=success,
            extra={
                "consult_count": consult_count,
                "value_ema": round(state.value_ema, 4),
                "episodes": state.episodes,
            },
        )

    def record_consult_mix(self, agent_id: str, commit_note_count: int) -> None:
        """Attribute commit/note share for the annealing metric."""
        state = self._agents.setdefault(str(agent_id), AgentConsultState())
        state.commit_note_total += max(0, int(commit_note_count))

    def value_below_threshold(self, agent_id: str) -> bool:
        """True when the value gate has evidence to suppress this agent."""
        state = self._agents.get(str(agent_id))
        if state is None or state.episodes < MIN_EPISODES_FOR_VALUE_GATE:
            return False
        return state.value_ema < VALUE_SUPPRESS_THRESHOLD

    def harness_call_rate(self, agent_id: str) -> float:
        """Consults per episode (paper annealing metric: →~1/episode)."""
        state = self._agents.get(str(agent_id))
        if state is None or state.episodes == 0:
            return 0.0
        return state.consults_total / state.episodes

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {aid: s.to_dict() for aid, s in self._agents.items()}


# Module-level singleton — cheap in-process state, same lifetime as the
# workspace registry (durable scoring history is a Phase-3+ concern).
consult_policy = ConsultPolicy()


def get_consult_policy() -> ConsultPolicy:
    return consult_policy
