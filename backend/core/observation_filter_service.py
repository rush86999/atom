"""
Ported from atom-saas (single-tenant strip).
SaaS-only features removed: tenant_id threading, BYOK tenant routing,
tenant-scoped usage tracker. Algorithm is identical.

SupervisorAgent-style LLM-free adaptive observation filter.

Sits between ReAct steps. After each observation is appended to
``execution_history``, this service:

1. runs a cheap **rule pass** (exact-duplicate removal, repeated-error collapse,
   ANSI/control-char scrub, per-observation length cap), and
2. if the history is long enough to amortize the cost, runs an **embedding
   pass** that clusters near-duplicate ``Observation:`` blocks by cosine
   similarity and keeps only the last ``KEEP_LAST_N`` per cluster.

Stateless (per-call only). Additive + flag-gated + default-OFF. With the flag
off it is a passthrough. Any internal failure returns the post-rule history
unchanged with zero reported savings — never propagate into the ReAct loop.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

OBSERVATION_FILTER_ENABLED: bool = (
    os.getenv("OBSERVATION_FILTER_ENABLED", "false").lower() == "true"
)
OBS_FILTER_SIM_THRESHOLD: float = float(os.getenv("OBS_FILTER_SIM_THRESHOLD", "0.88"))

EMBEDDING_MIN_STEP: int = int(os.getenv("OBS_FILTER_EMBEDDING_MIN_STEP", "4"))
PER_OBSERVATION_LENGTH_CAP: int = int(
    os.getenv("OBS_FILTER_PER_OBSERVATION_LENGTH_CAP", "4000")
)
KEEP_LAST_N: int = int(os.getenv("OBS_FILTER_KEEP_LAST_N", "3"))

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ObservationFilterService:
    """LLM-free rule + embedding filter for ReAct observation history."""

    def __init__(self, llm: Any):
        self.llm = llm
        self.threshold: float = OBS_FILTER_SIM_THRESHOLD
        self.KEEP_LAST_N: int = KEEP_LAST_N
        self.embedding_min_step: int = EMBEDDING_MIN_STEP

    async def filter_history(
        self,
        execution_history: str,
        current_step: int,
        task_input: str,
    ) -> Tuple[str, Dict[str, Any]]:
        original_tokens = self._count_tokens(execution_history)

        if not OBSERVATION_FILTER_ENABLED:
            return execution_history, {
                "savings_tokens": 0,
                "original_tokens": original_tokens,
                "filtered_tokens": original_tokens,
                "embedding_pass": False,
                "enabled": False,
            }

        try:
            filtered = self._apply_rules(execution_history)
        except Exception as exc:
            logger.debug("observation filter rule pass failed: %s", exc)
            filtered = execution_history

        embedding_pass = False
        if current_step >= self.embedding_min_step:
            try:
                filtered = await self._collapse_semantic_duplicates(filtered)
                embedding_pass = True
            except Exception as exc:
                logger.debug("observation filter embedding pass skipped: %s", exc)
                embedding_pass = False

        filtered_tokens = self._count_tokens(filtered)
        savings = max(0, original_tokens - filtered_tokens)
        return filtered, {
            "savings_tokens": savings,
            "original_tokens": original_tokens,
            "filtered_tokens": filtered_tokens,
            "embedding_pass": embedding_pass,
            "enabled": True,
        }

    def _apply_rules(self, history: str) -> str:
        history = _ANSI_RE.sub("", history)
        history = _CTRL_RE.sub("", history)

        lines = history.split("\n")
        seen_observations: set[str] = set()
        out_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Observation:"):
                payload = stripped[len("Observation:"):].strip()
                payload = self._collapse_repeated_errors(payload)
                if len(payload) > PER_OBSERVATION_LENGTH_CAP:
                    payload = payload[:PER_OBSERVATION_LENGTH_CAP] + " …[truncated]"
                key = payload
                if key in seen_observations:
                    continue
                seen_observations.add(key)
                out_lines.append(f"Observation: {payload}")
            else:
                out_lines.append(line)
        return "\n".join(out_lines)

    def _collapse_repeated_errors(self, payload: str) -> str:
        if "Error:" not in payload:
            return payload
        parts = payload.split("Error:")
        if len(parts) <= 2:
            return payload
        seen: set[str] = set()
        kept = [parts[0]]
        for p in parts[1:]:
            if p in seen:
                continue
            seen.add(p)
            kept.append(p)
        return "Error:".join(kept)

    async def _collapse_semantic_duplicates(self, history: str) -> str:
        lines = history.split("\n")
        obs_indices = [i for i, l in enumerate(lines) if l.strip().startswith("Observation:")]
        if len(obs_indices) <= self.KEEP_LAST_N:
            return history

        obs_texts = [lines[i].strip()[len("Observation:"):].strip() for i in obs_indices]
        embeddings = []
        for t in obs_texts:
            emb = await self.llm.generate_embedding(text=t)
            embeddings.append(emb)

        clusters: list[list[int]] = []
        for pos, emb in enumerate(embeddings):
            placed = False
            for cluster in clusters:
                rep_emb = embeddings[cluster[0]]
                if self._cosine(emb, rep_emb) >= self.threshold:
                    cluster.append(pos)
                    placed = True
                    break
            if not placed:
                clusters.append([pos])

        drop_positions: set[int] = set()
        for cluster in clusters:
            if len(cluster) <= self.KEEP_LAST_N:
                continue
            for pos in cluster[:- self.KEEP_LAST_N]:
                drop_positions.add(pos)

        if not drop_positions:
            return history

        drop_line_indices = {obs_indices[p] for p in drop_positions}
        new_lines = [line for idx, line in enumerate(lines) if idx not in drop_line_indices]
        return "\n".join(new_lines)

    def _count_tokens(self, text: str) -> int:
        try:
            import tiktoken  # type: ignore

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return max(0, len(text) // 4)

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        try:
            import numpy as np

            va = np.asarray(a, dtype=float)
            vb = np.asarray(b, dtype=float)
            na = np.linalg.norm(va)
            nb = np.linalg.norm(vb)
            if na == 0 or nb == 0:
                return 0.0
            return float(np.dot(va, vb) / (na * nb))
        except Exception:
            return 0.0
