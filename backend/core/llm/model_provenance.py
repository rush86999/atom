"""Model provenance + silent-bump drift detection for the LLM gateway.

Round 82 (adjudicated design, HARNESS_EVOLUTION follow-up):

Every LLM call has TWO model identities:
- **requested**: the router-selected concrete model the request was sent with
  (post BPC/tier/stage resolution — never a caller alias like ``"auto"``).
- **resolved**: the model ID the provider echoes back in the response body.

A *silent checkpoint bump* (CAIN-style vendor drift) changes the resolved ID
while the requested alias stays stable. Requested-keyed consumers are
structurally blind to that; this module is the detector.

Components:
- contextvar carrier for the per-call resolved ID (set by byok_handler right
  after each successful provider call; read by outcome feedback and agent-loop
  provenance stamping).
- :class:`ModelDriftDetector` — baseline map keyed ``(provider_id,
  requested_model) -> resolved`` persisted to a JSON state file. Fires a
  :class:`DriftEvent` when the echo changes under a stable requested key.
  Missing echoes are "unknown", never "unchanged". A drifted key only heals
  after ``ATOM_DRIFT_STABLE_ECHOES`` (default 3) consecutive echoes matching
  the new baseline — a silent bump IS a new steady state, so a single repeat
  observation must not re-enable patches that were never re-validated on the
  new checkpoint. :meth:`ModelDriftDetector.mark_revalidated` clears drift
  immediately once scoped patches have been explicitly re-validated.
- :func:`normalize_model_family` — policy-based family collapse for patch
  scoping: strips dates/snapshots/preview/free suffixes but KEEPS variant
  tiers (deepseek-v4-flash != deepseek-v4-pro). Family governs harness-patch
  breadth only; drift detection stays keyed on the concrete ID for maximum
  sensitivity. Emits vocabulary compatible with AgentRegistry
  ``diversity_profile["model_family"]``.

Detection-only: never blocks or mutates generation. Never raises from the
observe path. Flag: ``ATOM_MODEL_DRIFT_DETECTION_ENABLED`` (default on).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_FLAG = "ATOM_MODEL_DRIFT_DETECTION_ENABLED"
_STABLE_ECHOES_FLAG = "ATOM_DRIFT_STABLE_ECHOES"
_DEFAULT_STABLE_ECHOES = 3
_DEFAULT_STATE_PATH = Path("./data/model_resolution_state.json")

_resolved_model_cv: ContextVar[Optional[str]] = ContextVar(
    "atom_resolved_model", default=None
)


def set_resolved_model(model_id: Optional[str]) -> None:
    """Record the provider-echoed model ID for the current call context."""
    _resolved_model_cv.set(model_id)


def get_resolved_model() -> Optional[str]:
    """Return the echoed model ID for this context, or None when unknown."""
    return _resolved_model_cv.get()


def clear_resolved_model() -> None:
    _resolved_model_cv.set(None)


def _enabled() -> bool:
    return os.getenv(_FLAG, "true").lower() == "true"


def _stable_echoes_required() -> int:
    try:
        n = int(os.getenv(_STABLE_ECHOES_FLAG, str(_DEFAULT_STABLE_ECHOES)))
        return max(1, n)
    except (TypeError, ValueError):
        return _DEFAULT_STABLE_ECHOES


# ── family normalization (policy, not guesswork) ──────────────────────

_STRIP_TOKENS = {"free", "preview", "latest"}
# Trailing date/snapshot tails: -2026-03 | -20260219 | @2026-01-17 | :20260317
_DATE_TAIL = re.compile(r"(?:[-:@](?:20\d{2})(?:[-._:]?\d{2})*)$")


def normalize_model_family(model_id: Optional[str]) -> str:
    """Collapse a concrete model ID to its scoping family.

    Collapses: case, vendor path prefixes, trailing date/snapshot tails,
    ``free`` / ``preview`` / ``latest`` tags. Preserves version dots
    (``gpt-5.4`` stays ``gpt-5.4``) and variant tiers (``deepseek-v4-flash``
    != ``deepseek-v4-pro``) because they denote materially different behavior
    classes — fragmenting there is correct: a prompt rule mined on flash
    failures must not serve pro. Returns "" for empty/unknown input.
    """
    if not model_id:
        return ""
    name = str(model_id).lower().strip()
    name = name.split("/", 1)[-1]  # drop vendor prefix (openai/gpt-...)
    name = _DATE_TAIL.sub("", name)
    tokens = [t for t in re.split(r"[-_:\s]+", name) if t]
    kept = [t for t in tokens if t not in _STRIP_TOKENS]
    return "-".join(kept).strip("-")


@dataclass
class DriftEvent:
    provider_id: str
    requested_model: str
    previous_resolved: str
    new_resolved: str
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ModelDriftDetector:
    """Detects provider-side checkpoint bumps under stable request aliases.

    State shape (JSON): ``{"baselines": {"<provider>:<requested>": "<resolved>"}}``
    plus in-memory sets of currently-drifted keys and their consecutive
    stable-echo counts. On detection the baseline moves to the new echo and
    the key is marked drifted — family-scoped patches for that identity are
    suppressed. Healing is debounced: the key stays drifted until the echo has
    matched the new baseline ``ATOM_DRIFT_STABLE_ECHOES`` times in a row
    (default 3) OR :meth:`mark_revalidated` is called after explicit patch
    re-validation. Rationale: a silent bump is a steady state, so one repeat
    observation proves consistency, not that the old patches are still good.
    """

    def __init__(self, state_path: Optional[Path] = None):
        self._state_path = Path(state_path) if state_path else _DEFAULT_STATE_PATH
        self._lock = threading.Lock()
        self._baselines: Dict[str, str] = {}
        self._drifted: set = set()
        self._stable: Dict[str, int] = {}
        self._load()

    # ── persistence (best-effort, never raises) ──
    def _load(self) -> None:
        try:
            if self._state_path.exists():
                data = json.loads(self._state_path.read_text())
                baselines = data.get("baselines", {})
                if isinstance(baselines, dict):
                    self._baselines = {
                        str(k): str(v) for k, v in baselines.items()
                    }
        except Exception as e:  # corrupted/unreadable state → fresh start
            logger.warning("ModelDriftDetector state load failed, starting fresh: %s", e)
            self._baselines = {}

    def _save(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps({"baselines": self._baselines}, indent=0)
            )
        except Exception as e:
            logger.debug("ModelDriftDetector state save skipped: %s", e)

    @staticmethod
    def _key(provider_id: str, requested_model: str) -> str:
        return f"{provider_id}:{requested_model}"

    # ── public API ──
    def observe(
        self, provider_id: str, requested_model: str, resolved_model: Optional[str]
    ) -> Optional[DriftEvent]:
        """Record one echo. Returns DriftEvent on a silent-bump detection.

        ``resolved_model=None`` means unknown (provider didn't echo / non-
        standard endpoint): treated as a gap — no event, baseline untouched.
        Never raises.
        """
        if not _enabled():
            return None
        try:
            if not resolved_model:
                return None
            key = self._key(provider_id, requested_model)
            with self._lock:
                previous = self._baselines.get(key)
                if previous is None:
                    self._baselines[key] = resolved_model
                    self._save()
                    return None
                if previous == resolved_model:
                    if key in self._drifted:
                        self._stable[key] = self._stable.get(key, 0) + 1
                        if self._stable[key] >= _stable_echoes_required():
                            # debounced heal: echo proven consistent N times
                            self._drifted.discard(key)
                            self._stable.pop(key, None)
                    return None
                self._baselines[key] = resolved_model
                self._drifted.add(key)
                self._stable.pop(key, None)
                self._save()
            event = DriftEvent(
                provider_id=provider_id,
                requested_model=requested_model,
                previous_resolved=previous,
                new_resolved=resolved_model,
            )
            logger.warning(
                "MODEL DRIFT: %s/%s now resolves to '%s' (was '%s') — "
                "model-family-scoped harness patches for this identity are "
                "suppressed until the echo stabilizes",
                provider_id, requested_model, resolved_model, previous,
            )
            return event
        except Exception as e:
            logger.debug("drift observe skipped: %s", e)
            return None

    def is_drifted(self, provider_id: str, requested_model: str) -> bool:
        """True while the echo for this identity is unstable or unre-validated."""
        try:
            with self._lock:
                return self._key(provider_id, requested_model) in self._drifted
        except Exception:
            return False

    def mark_revalidated(self, provider_id: str, requested_model: str) -> None:
        """Clear drift immediately after explicit patch re-validation.

        Callers: the re-validation path (sandbox validate_mutation_in_sandbox
        against the new checkpoint) — NOT the observe loop. Never raises.
        """
        try:
            with self._lock:
                key = self._key(provider_id, requested_model)
                self._drifted.discard(key)
                self._stable.pop(key, None)
        except Exception:
            pass


_detector: Optional[ModelDriftDetector] = None
_detector_lock = threading.Lock()


def get_drift_detector() -> ModelDriftDetector:
    """Process-wide singleton (lazy; safe under concurrency)."""
    global _detector
    if _detector is None:
        with _detector_lock:
            if _detector is None:
                _detector = ModelDriftDetector()
    return _detector


# ---------------------------------------------------------------------------
# Route attribution for employee reasoning boundaries.
# Requested = the route selected by BPC/pin before dispatch; served = the
# route whose response was actually accepted. A failed attempt is never
# reported as served. These are context-local so concurrent assignments do
# not overwrite one another's attribution.
# ---------------------------------------------------------------------------
from contextvars import ContextVar as _ContextVar
from typing import Any as _Any, Tuple as _Tuple

_requested_route_cv: _ContextVar[_Any] = _ContextVar(
    "atom_requested_route", default=None)
_served_route_cv: _ContextVar[_Any] = _ContextVar(
    "atom_served_route", default=None)
_route_mode_cv: _ContextVar[_Any] = _ContextVar(
    "atom_route_mode", default=None)
_routing_profile_cv: _ContextVar[_Any] = _ContextVar(
    "atom_routing_profile", default=None)
_routing_error_cv: _ContextVar[_Any] = _ContextVar(
    "atom_routing_error", default=None)
#: Identity of the feedback row THIS generation wrote. The business consumer
#: evaluates the proposal AFTER the model call, so it needs the exact
#: generation id to annotate the real outcome row instead of inserting an
#: unattributed judgement. Context-local so concurrent assignments never
#: annotate each other's rows.
_feedback_id_cv: _ContextVar[_Any] = _ContextVar(
    "atom_feedback_id", default=None)


def set_feedback_id(feedback_id: Optional[str]) -> None:
    _feedback_id_cv.set(str(feedback_id or "") or None)


def get_feedback_id() -> Optional[str]:
    return _feedback_id_cv.get()


def clear_feedback_id() -> None:
    _feedback_id_cv.set(None)


def set_requested_route(provider_id: Optional[str], model: Optional[str]) -> None:
    if provider_id or model:
        _requested_route_cv.set((str(provider_id or ""), str(model or "")))


def set_served_route(provider_id: Optional[str], model: Optional[str]) -> None:
    if provider_id or model:
        _served_route_cv.set((str(provider_id or ""), str(model or "")))
        # An accepted response supersedes any earlier candidate-exclusion
        # warning from the same boundary.
        _routing_error_cv.set(None)


def set_route_mode(mode: Optional[str]) -> None:
    _route_mode_cv.set(str(mode or "") or None)


def set_routing_profile(name: Optional[str], version: Optional[str] = None) -> None:
    if name:
        _routing_profile_cv.set((str(name), str(version or "")))


def set_routing_error(code: Optional[str], detail: Optional[str] = None) -> None:
    if code:
        _routing_error_cv.set({
            "code": str(code)[:120],
            "detail": str(detail or "")[:500],
        })


def clear_routing_error() -> None:
    """A successful fallback supersedes an earlier route's failure."""
    _routing_error_cv.set(None)


def clear_route_attribution() -> None:
    _requested_route_cv.set(None)
    _served_route_cv.set(None)
    _route_mode_cv.set(None)
    _routing_profile_cv.set(None)
    _routing_error_cv.set(None)
    clear_feedback_id()
    # A previous call's echoed checkpoint must not be attributed to this one.
    clear_resolved_model()


def get_route_attribution() -> Dict[str, _Any]:
    """Business-safe route attribution; never contains raw provider errors."""
    requested = _requested_route_cv.get()
    served = _served_route_cv.get()
    profile = _routing_profile_cv.get()
    return {
        "mode": _route_mode_cv.get(),
        "requested_route": (
            {"provider": requested[0], "model": requested[1]}
            if requested else None),
        "served_route": (
            {"provider": served[0], "model": served[1]}
            if served else None),
        "resolved_model": get_resolved_model(),
        "profile": (
            {"name": profile[0], "version": profile[1]}
            if profile else None),
        "error": _routing_error_cv.get(),
        "routing_result_id": get_feedback_id(),
    }
