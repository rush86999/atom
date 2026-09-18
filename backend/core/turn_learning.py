# -*- coding: utf-8 -*-
"""Turn-level learning: the app remembers which (canvas, evidence-class,
model) combinations recently failed and redirects the next similar turn.

Not a routing algorithm — a circuit breaker per conversation. The system
already has model-level safety (fabrication bench, 401 memo,
reasoning-mandatory exclusion) and evidence-level strategy (provenance
menu, evidence compiler). This module adds the MISSING layer: the
turn-level pattern where a specific canvas + evidence-class combination
repeatedly exceeds its budget or produces structured errors on the same
model. After N failures, the next turn for that pattern uses a different
model (pinned via the existing fallback mechanism) until a success
clears the redirect.

Persistence: JSON sidecar (``turn_learning_<instance>.json``) so the
pattern survives backend restarts — the whole point is that the *next*
turn should benefit from the *previous* turn's failure.
"""
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_LEARNING_DIR = Path(
    os.getenv(
        "ATOM_TURN_LEARNING_DIR",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "turn_learning",
        ),
    )
)
_LEARNING_FILE = _LEARNING_DIR / "patterns.json"
_LEARN_MAX_PATTERNS = int(
    os.getenv("ATOM_TURN_LEARNING_MAX_PATTERNS", "200") or 200)
_LEARN_TTL_S = float(
    os.getenv("ATOM_TURN_LEARNING_TTL_S", "3600") or 3600
)  # 1 hour — stale patterns should not permanently redirect
_LEARN_FAILURE_THRESHOLD = int(
    os.getenv("ATOM_TURN_LEARNING_FAILURE_THRESHOLD", "2") or 2
)
_LEARN_SUCCESS_CLEAR = True


def _classify_ask(message: str) -> str:
    """Coarse evidence-class for a message: what kind of retrieval does
    this ask need? Used to group failures by shape, not by exact text."""
    m = (message or "").lower()
    if any(w in m for w in ("derive", "formula", "calculation", "breakdown",
                            "how was", "how did", "reverse")):
        return "derivation"
    if any(w in m for w in ("attachment", "file", "workbook", "spreadsheet",
                            "xlsx", "doc")):
        return "attachment"
    if any(w in m for w in ("email", "thread", "sent", "received", "forward")):
        return "mail"
    if any(w in m for w in ("stock", "inventory", "on hand", "available")):
        return "inventory"
    return "general"


def _canvas_key(canvas_id: Optional[str], session_id: Optional[str]) -> str:
    """The conversation key: canvas first, then session."""
    return canvas_id or session_id or "no-context"


class TurnLearning:
    """Persists turn outcomes and consults them before the next turn."""

    def __init__(self):
        self._patterns: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            if _LEARNING_FILE.exists():
                data = json.loads(_LEARNING_FILE.read_text())
                self._patterns = data.get("patterns", {})
        except Exception:
            self._patterns = {}

    def _save(self) -> None:
        try:
            _LEARNING_DIR.mkdir(parents=True, exist_ok=True)
            # Evict stale entries
            now = time.monotonic()
            self._patterns = {
                k: v for k, v in self._patterns.items()
                if now - v.get("last_ts", 0) < _LEARN_TTL_S
            }
            # Cap total patterns
            while len(self._patterns) > _LEARN_MAX_PATTERNS:
                oldest = min(self._patterns,
                             key=lambda k: self._patterns[k].get("last_ts", 0))
                del self._patterns[oldest]
            _LEARNING_FILE.write_text(json.dumps(
                {"patterns": self._patterns}, indent=1))
        except Exception:
            pass

    def record_failure(
        self, canvas_id: Optional[str], session_id: Optional[str],
        message: str, model_id: str, stage: str,
    ) -> None:
        """Record a turn failure (budget exceeded, structured error,
        zero-visible stream). After the threshold, the pattern is marked
        for redirect."""
        key = _canvas_key(canvas_id, session_id)
        ev_class = _classify_ask(message)
        pk = f"{key}:{ev_class}"
        now = time.monotonic()
        entry = self._patterns.setdefault(pk, {
            "failures": 0, "successes": 0,
            "models": {}, "last_ts": now,
        })
        entry["failures"] += 1
        entry["last_ts"] = now
        entry["last_stage"] = stage
        entry["last_model"] = model_id
        mkey = f"model:{model_id}"
        entry[mkey] = entry.get(mkey, 0) + 1
        self._save()

    def record_success(
        self, canvas_id: Optional[str], session_id: Optional[str],
        message: str, model_id: str,
    ) -> None:
        """A success on the same pattern clears the redirect."""
        key = _canvas_key(canvas_id, session_id)
        ev_class = _classify_ask(message)
        pk = f"{key}:{ev_class}"
        if pk in self._patterns:
            self._patterns[pk]["successes"] = (
                self._patterns[pk].get("successes", 0) + 1)
            self._patterns[pk]["last_ts"] = time.monotonic()
            # Clear redirect if the success is recent enough
            if _LEARN_SUCCESS_CLEAR:
                self._patterns[pk]["failures"] = 0
                for mk in list(self._patterns[pk].keys()):
                    if mk.startswith("model:"):
                        del self._patterns[pk][mk]
            self._save()

    def should_redirect(
        self, canvas_id: Optional[str], session_id: Optional[str],
        message: str, current_model: str,
    ) -> Optional[str]:
        """Return a replacement model_id if the current model has recently
        failed ≥ threshold times for this pattern, or None to keep it."""
        key = _canvas_key(canvas_id, session_id)
        ev_class = _classify_ask(message)
        pk = f"{key}:{ev_class}"
        entry = self._patterns.get(pk)
        if not entry:
            return None
        mkey = f"model:{current_model}"
        fails = entry.get(mkey, 0)
        if fails >= _LEARN_FAILURE_THRESHOLD:
            # Find a model that worked recently, or any model not in the
            # failure set
            for mk, count in entry.items():
                if mk.startswith("model:") and count == 0:
                    alt = mk.split(":", 1)[1]
                    if alt != current_model:
                        return alt
            # No known-good alternative — just signal that the current
            # model should be skipped (the router picks the next)
            return f"__skip__{current_model}"
        return None


# Module-level singleton
_instance: Optional[TurnLearning] = None


def get_turn_learning() -> TurnLearning:
    global _instance
    if _instance is None:
        _instance = TurnLearning()
    return _instance
