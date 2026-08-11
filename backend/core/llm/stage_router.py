"""Stage Router — turn-level model-tier routing from agent progress signals.

Port of NVIDIA Switchyard's ``stage_router`` concept (see
``docs/routing_algorithms/stage_router_routing.md``) onto Atom's 5-tier
cognitive system. The stage router scores each ReAct turn from the recent
tool-result history on two axes:

- **WRONG → capable**: windowed error ``severity``, ``spinning`` (churn with no
  reads or writes) and ``exploring`` (reading/planning without producing)
  push toward the capable tier.
- **PROGRESS → efficient**: ``production_intensity`` (writes landing in the
  recent window) pushes toward the efficient tier.

The signed score is ``tanh``-squashed so the axes are **corroborative**: one
full signal alone scores ~0.46 (below the default 0.5 threshold) and a second
corroborating signal is what pushes a turn decisively across it. A critical
error is a hard override that escalates on its own.

``decision_source`` distinguishes the paths through the cascade:

- ``override`` — critical error forced the capable tier.
- ``dimensions`` — the corroborative scorer crossed ``confidence_threshold``.
- ``fall_open`` — signals were ambiguous; the picker's default tier was used.

Deployment model (research-backed, see docs/architecture/SWITCHYARD_GAP_ANALYSIS.md):

1. **Harness first** — ``ATOM_STAGE_ROUTING_SPLIT`` enables a weighted-random
   A/B split between the ``efficient`` (``fast``) and ``capable`` (``quality``)
   model types. Every turn's audit row records both the stage router's
   *would-have* pick (``selected_group``) and the group that *actually ran*
   (``applied_group``), which is exactly the data needed for the RESCUE/LOSS
   quadrant calibration methodology (RouteGuard-style certification).
2. **Shadow mode** (default) — the router logs decisions but never changes
   the model type. ``ATOM_STAGE_ROUTING_FORCE_ENFORCE=true`` flips it live.
3. **Per-workload calibration** — tune ``confidence_threshold`` against the
   logged pairs before enforcing.

Flags:
- ``ATOM_STAGE_ROUTING_ENABLED`` (default ``true``) — master switch; on alone
  = shadow (audit-only, model selection untouched).
- ``ATOM_STAGE_ROUTING_FORCE_ENFORCE`` (default ``false``) — false = shadow.
- ``ATOM_STAGE_ROUTING_PICKER`` (default ``efficient_first``) — default tier
  when signals are ambiguous (``capable_first`` is quality-first).
- ``ATOM_STAGE_ROUTING_CONFIDENCE_THRESHOLD`` (default ``0.5``).
- ``ATOM_STAGE_ROUTING_WINDOW`` (default ``3``) — recent turns scored.
- ``ATOM_STAGE_ROUTING_SPLIT`` (optional JSON weights, e.g.
  ``'{"efficient": 0.7, "capable": 0.3}'``) — A/B harness (opt-in, forces
  traffic arms; off by default).
- ``ATOM_STAGE_ROUTING_SPLIT_SEED`` (optional int) — deterministic split.

The router never raises: any failure degrades to a no-op (the agent loop
keeps its existing model selection untouched).
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import re
import uuid
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ── Feature flags (read once at import; kill switches) ──────────────────────
STAGE_ROUTING_ENABLED = os.getenv("ATOM_STAGE_ROUTING_ENABLED", "true").lower() == "true"
STAGE_ROUTING_FORCE_ENFORCE = os.getenv(
    "ATOM_STAGE_ROUTING_FORCE_ENFORCE", "false"
).lower() == "true"
STAGE_ROUTING_PICKER = os.getenv("ATOM_STAGE_ROUTING_PICKER", "efficient_first").lower()
STAGE_ROUTING_CONFIDENCE_THRESHOLD = float(
    os.getenv("ATOM_STAGE_ROUTING_CONFIDENCE_THRESHOLD", "0.5")
)
STAGE_ROUTING_WINDOW = int(os.getenv("ATOM_STAGE_ROUTING_WINDOW", "3"))
_STAGE_ROUTING_SPLIT_RAW = os.getenv("ATOM_STAGE_ROUTING_SPLIT", "")
_STAGE_SPLIT_SEED_RAW = os.getenv("ATOM_STAGE_ROUTING_SPLIT_SEED", "")

CAPABLE = "capable"
EFFICIENT = "efficient"
GROUPS = (CAPABLE, EFFICIENT)

# Model-type vocabulary understood by the agent loops (byok_handler
# ``model_type``: "auto", "fast", "quality", "reasoning" or a concrete model).
GROUP_TO_MODEL_TYPE = {CAPABLE: "quality", EFFICIENT: "fast"}


class StagePicker(str, Enum):
    """Which tier is the default when the signals are ambiguous."""

    EFFICIENT_FIRST = "efficient_first"  # cost-first: escalate only on clear signals
    CAPABLE_FIRST = "capable_first"  # quality-first: drop only on clear signals


class DecisionSource(str, Enum):
    """Why a turn was routed the way it was (mirrors Switchyard's taxonomy)."""

    OVERRIDE = "override"  # critical error forced the capable tier
    DIMENSIONS = "dimensions"  # corroborative scorer crossed the threshold
    FALL_OPEN = "fall_open"  # ambiguous signals; picker default used


class SignalSeverity(IntEnum):
    """Windowed error severity of the recent tool results."""

    NONE = 0
    MINOR = 1
    MAJOR = 2
    CRITICAL = 3


# Platform-canonical failure phrasings (anchored, like
# ``atom_meta_agent._is_error_observation``) plus generic markers. Order
# matters: CRITICAL is checked first.
CRITICAL_MARKERS: Tuple[str, ...] = (
    "permission denied",
    "not authorized",
    "unauthorized",
    "forbidden",
    "governance blocked",
    "sandbox blocked",
    "security violation",
    "fatal",
    "corrupt",
    "breach",
)
MAJOR_MARKERS: Tuple[str, ...] = (
    "tool error.",
    "tool execution failed",
    "governance error",
    "was rejected",
    "rejected or timed out",
    "sandbox error",
    "error",
    "exception",
    "traceback",
    "failed",
    "failure",
    "timeout",
    "timed out",
    "denied",
    "internal server error",
)
MINOR_MARKERS: Tuple[str, ...] = (
    "warning",
    "not found",
    "missing",
    "empty",
    "invalid",
    "skipped",
    "retry",
    "no results",
    "unavailable",
)

# Heuristic read/write classification by tool name. Conservative substring
# hints tuned to Atom's tool vocabulary (``get_``/``list_``/``_post_`` etc.).
READ_HINTS: Tuple[str, ...] = (
    "search",
    "list_",
    "read",
    "fetch",
    "lookup",
    "describe",
    "query",
    "history",
    "retrieve",
    "scan",
    "find",
    "get_",
    "inspect",
    "analy",
    "show",
    "preview",
    "cat ",
    "ls ",
)
WRITE_HINTS: Tuple[str, ...] = (
    "create",
    "update",
    "write",
    "save",
    "insert",
    "delete",
    "edit",
    "post",
    "send",
    "push",
    "put_",
    "patch",
    "record",
    "upload",
    "set_",
    "store",
    "submit",
    "publish",
    "install",
    "build",
    "trigger",
)

_ACTION_RE = re.compile(r"Action:\s*(.*?)\nObservation:\s*(.*?)(?=\nAction:|\Z)", re.DOTALL)
_TOOL_CALL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(")

# Corroborative weights — one full signal alone lands at ~0.46 under the
# default 1.0 squash factor; a second corroborating signal crosses 0.5.
_SEVERITY_WEIGHT = 0.5
_SPINNING_WEIGHT = 0.5
_EXPLORING_WEIGHT = 0.35
_PRODUCTION_WEIGHT = 0.5
_TANH_FACTOR = 1.0


@dataclass
class ToolOutcome:
    """One observed tool call + its result, in run order."""

    tool_name: str
    is_read: bool = False
    is_write: bool = False
    severity: SignalSeverity = SignalSeverity.NONE
    success: bool = True


@dataclass
class StageSignals:
    """Extracted agent-progress signals from the recent tool-result window."""

    severity: float = 0.0  # effective windowed severity, 0.0–3.0
    spinning: bool = False  # churn with no reads or writes
    exploring: bool = False  # reading/planning without producing
    production_intensity: float = 0.0  # fraction of window calls that wrote
    critical: bool = False  # any critical error → hard override

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class StageDecision:
    """Outcome of one turn's stage-router decision."""

    selected_group: str  # what the stage router would pick (signal-driven)
    applied_group: str  # what actually runs (split may override in harness mode)
    default_group: str  # picker default
    split_group: Optional[str]  # A/B harness assignment, when active
    confidence: float  # |signed score|, 0.0–1.0
    source: str  # DecisionSource value
    rationale: str  # human-readable explanation
    handoff_note: Optional[str] = None  # contextual note for the next model
    id: str = field(default_factory=lambda: str(uuid.uuid4()))  # audit row PK


@dataclass
class ToolHistoryEntry:
    """Parsed (tool, observation) pair from the execution-history string."""

    outcome: ToolOutcome
    observation: str


class WeightedRandomSplit:
    """Fixed-ratio A/B split between the efficient and capable groups.

    The calibration harness for the stage router: forcing a fixed traffic
    split while the router shadows its would-have picks produces the
    RESCUE/LOSS quadrant data needed to certify (or reject) enforcement for
    a given workload. Mirrors Switchyard's ``random`` route type.
    """

    def __init__(self, weights: Dict[str, float], seed: Optional[int] = None) -> None:
        valid = {g: w for g, w in weights.items() if g in GROUPS and w > 0}
        total = sum(valid.values())
        if total <= 0 or not valid:
            raise ValueError(f"split weights must be positive for groups in {GROUPS}")
        self._groups: List[str] = list(valid.keys())
        self._weights: List[float] = [w / total for w in valid.values()]
        self._rng = random.Random(seed)

    def pick(self) -> str:
        """Return a group (``capable`` or ``efficient``) by the configured ratio."""
        return self._rng.choices(self._groups, self._weights, k=1)[0]

    @classmethod
    def from_env(cls) -> Optional["WeightedRandomSplit"]:
        """Build the split from ``ATOM_STAGE_ROUTING_SPLIT``/``_SEED`` env vars."""
        raw = os.getenv("ATOM_STAGE_ROUTING_SPLIT", "")
        if not raw:
            return None
        try:
            weights = json.loads(raw)
            if not isinstance(weights, dict):
                raise ValueError("split config must be a JSON object")
            seed_raw = os.getenv("ATOM_STAGE_ROUTING_SPLIT_SEED", "")
            seed = int(seed_raw) if seed_raw else None
            return cls(weights, seed=seed)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid ATOM_STAGE_ROUTING_SPLIT, split disabled: {e}")
            return None


def classify_severity(observation: Optional[str]) -> SignalSeverity:
    """Map a tool observation to a severity level (CRITICAL > MAJOR > MINOR)."""
    if observation is None:
        return SignalSeverity.NONE
    text = str(observation).lower()
    if any(m in text for m in CRITICAL_MARKERS):
        return SignalSeverity.CRITICAL
    if any(m in text for m in MAJOR_MARKERS):
        return SignalSeverity.MAJOR
    if any(m in text for m in MINOR_MARKERS):
        return SignalSeverity.MINOR
    return SignalSeverity.NONE


def classify_tool_roles(tool_name: str) -> Tuple[bool, bool]:
    """Heuristic (is_read, is_write) classification for a tool name."""
    lowered = tool_name.lower()
    is_read = any(h in lowered for h in READ_HINTS)
    is_write = any(h in lowered for h in WRITE_HINTS)
    return is_read, is_write


def parse_tool_history(history: Optional[str]) -> List[ToolHistoryEntry]:
    """Parse an agent execution-history string into ordered tool entries.

    Handles both serialized forms written by the ReAct loops:
    ``Action: {"tool": ..., "params": {...}}`` and the parallel
    ``Action: tool_name({json})`` form.
    """
    if not history:
        return []
    entries: List[ToolHistoryEntry] = []
    for match in _ACTION_RE.finditer(history):
        action_text = match.group(1).strip()
        observation_text = match.group(2).strip()
        if not action_text:
            continue
        tool_name: Optional[str] = None
        try:
            action = json.loads(action_text)
            if isinstance(action, dict):
                tool_name = action.get("tool")
        except (ValueError, TypeError):
            parsed = _TOOL_CALL_RE.match(action_text)
            if parsed:
                tool_name = parsed.group(1)
        if not tool_name:
            continue
        is_read, is_write = classify_tool_roles(tool_name)
        severity = classify_severity(observation_text)
        entries.append(
            ToolHistoryEntry(
                outcome=ToolOutcome(
                    tool_name=tool_name,
                    is_read=is_read,
                    is_write=is_write,
                    severity=severity,
                    success=severity < SignalSeverity.MAJOR,
                ),
                observation=observation_text[:500],
            )
        )
    return entries


class StageRouter:
    """Turn-level tier router driven by agent-progress signals.

    Compatible with Atom's agent loops: call ``decide_for_history`` once per
    ReAct turn with the execution history and the previous turn's group, then
    (in enforce mode) map the decision to a model type via
    ``map_decision_to_model_type``.
    """

    def __init__(
        self,
        picker: StagePicker = StagePicker.EFFICIENT_FIRST,
        confidence_threshold: float = STAGE_ROUTING_CONFIDENCE_THRESHOLD,
        window: int = STAGE_ROUTING_WINDOW,
        enabled: bool = STAGE_ROUTING_ENABLED,
        enforce: bool = STAGE_ROUTING_FORCE_ENFORCE,
        split: Optional[WeightedRandomSplit] = None,
        audit: bool = True,
    ) -> None:
        self.picker = picker if isinstance(picker, StagePicker) else StagePicker(picker)
        self.confidence_threshold = max(0.0, min(confidence_threshold, 1.0))
        self.window = max(1, window)
        self.enabled = enabled
        self.enforce = enforce and enabled
        self.split = split
        self.audit = audit

    # ── Signal extraction ───────────────────────────────────────────────────
    def extract_signals(self, outcomes: Sequence[ToolOutcome], window: Optional[int] = None) -> StageSignals:
        """Score the recent tool-result window into agent-progress signals."""
        window_size = self.window if window is None else max(1, window)
        recent = list(outcomes)[-window_size:]
        if not recent:
            return StageSignals()
        max_sev = max(o.severity for o in recent)
        writes = [o for o in recent if o.is_write]
        reads = [o for o in recent if o.is_read]
        neutral = [o for o in recent if not o.is_read and not o.is_write]
        repeated = len(recent) >= 2 and len({o.tool_name for o in recent}) == 1
        any_trouble = any(o.severity > SignalSeverity.NONE or not o.success for o in recent)
        spinning = len(neutral) == len(recent) and (any_trouble or repeated or len(recent) >= 3)
        exploring = len(writes) == 0 and len(reads) > 0
        return StageSignals(
            severity=float(max_sev),
            spinning=spinning,
            exploring=exploring,
            production_intensity=len(writes) / len(recent),
            critical=max_sev == SignalSeverity.CRITICAL,
        )

    def _score(self, signals: StageSignals) -> float:
        """Signed confidence in [-1, 1]; positive → capable, negative → efficient."""
        severity_term = _SEVERITY_WEIGHT * min(signals.severity / 3.0, 1.0)
        spinning_term = _SPINNING_WEIGHT if signals.spinning else 0.0
        exploring_term = _EXPLORING_WEIGHT if signals.exploring else 0.0
        production_term = _PRODUCTION_WEIGHT * signals.production_intensity
        signed = _TANH_FACTOR * (
            severity_term + spinning_term + exploring_term - production_term
        )
        return math.tanh(signed)

    # ── Decision ────────────────────────────────────────────────────────────
    def decide(
        self,
        outcomes: Sequence[ToolOutcome],
        previous_group: Optional[str] = None,
        use_split: bool = False,
    ) -> StageDecision:
        """Route one turn from its tool-outcome history."""
        signals = self.extract_signals(outcomes)
        split_group: Optional[str] = None
        if use_split and self.split is not None:
            split_group = self.split.pick()

        default_group = CAPABLE if self.picker == StagePicker.CAPABLE_FIRST else EFFICIENT

        if signals.critical:
            selected_group = CAPABLE
            source = DecisionSource.OVERRIDE
            confidence = 1.0
        else:
            signed = self._score(signals)
            confidence = abs(signed)
            if confidence >= self.confidence_threshold:
                selected_group = CAPABLE if signed > 0 else EFFICIENT
                source = DecisionSource.DIMENSIONS
            else:
                selected_group = default_group
                source = DecisionSource.FALL_OPEN

        applied_group = split_group if split_group is not None else selected_group
        if source == DecisionSource.OVERRIDE and split_group is not None:
            applied_group = CAPABLE  # critical errors never ride the A/B split
        rationale = (
            f"stage_router selected {selected_group} "
            f"(confidence {confidence:.3f}, {source.value})"
        )
        if split_group is not None:
            rationale += f"; harness split forced {applied_group}"
        return StageDecision(
            selected_group=selected_group,
            applied_group=applied_group,
            default_group=default_group,
            split_group=split_group,
            confidence=confidence,
            source=source.value,
            rationale=rationale,
            handoff_note=self.handoff_note_for(applied_group, previous_group, source.value),
        )

    def handoff_note_for(
        self,
        group: str,
        previous_group: Optional[str],
        source: str = "",
    ) -> Optional[str]:
        """Contextual note for the model a tier switch hands off to."""
        if previous_group is None or group == previous_group:
            return None
        if group == CAPABLE:
            return (
                "ROUTING HANDOFF: you are now on the capable tier. The previous "
                "model was stalling or erroring on this run — pick up the "
                "diagnosis, verify tool outputs, and make concrete progress."
            )
        return (
            "ROUTING HANDOFF: the run has settled into routine work and you are "
            "on the efficient tier. Follow the established plan and keep edits "
            "focused; escalate only if a critical error appears."
        )

    # ── Agent-loop entry point ──────────────────────────────────────────────
    async def decide_for_history(
        self,
        history: Optional[str],
        previous_group: Optional[str] = None,
        use_split: bool = False,
        agent_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        step_index: Optional[int] = None,
    ) -> Optional[StageDecision]:
        """Parse the execution history, decide, and persist an audit row.

        Never raises: returns ``None`` on any failure so the agent loop keeps
        its existing model selection untouched.
        """
        if not self.enabled:
            return None
        try:
            entries = parse_tool_history(history)
            outcomes = [e.outcome for e in entries]
            decision = self.decide(outcomes, previous_group=previous_group, use_split=use_split)
            if self.audit:
                self.record_audit(
                    decision=decision,
                    signals=self.extract_signals(outcomes),
                    agent_id=agent_id,
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    execution_id=execution_id,
                    step_index=step_index,
                )
            return decision
        except Exception as e:  # pragma: no cover - defensive, never breaks loop
            logger.warning(f"Stage router decision failed, no-op: {e}")
            return None

    def record_audit(
        self,
        decision: StageDecision,
        signals: Optional[StageSignals] = None,
        agent_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        step_index: Optional[int] = None,
        model_type: Optional[str] = None,
    ) -> None:
        """Persist one routing decision (shadow or enforced) to the audit table.

        Uses the repo's context-manager session pattern; failures are logged,
        never raised.
        """
        try:
            from core.database import get_db_session
            from core.models import StageRouterAudit

            with get_db_session() as db:
                db.add(
                    StageRouterAudit(
                        id=decision.id,
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        agent_id=agent_id,
                        execution_id=execution_id,
                        step_index=step_index,
                        picker=self.picker.value,
                        confidence_threshold=self.confidence_threshold,
                        signals=signals.to_json() if signals else None,
                        selected_group=decision.selected_group,
                        applied_group=decision.applied_group,
                        split_group=decision.split_group,
                        default_group=decision.default_group,
                        confidence=decision.confidence,
                        decision_source=decision.source,
                        enforced=self.enforce,
                        model_type=model_type,
                        handoff_note=decision.handoff_note,
                        rationale=decision.rationale,
                        created_at=datetime.now(timezone.utc),
                    )
                )
                db.commit()
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Stage router audit persist failed (non-fatal): {e}")


def map_decision_to_model_type(
    decision: Optional[StageDecision], enforce: bool
) -> Optional[str]:
    """Map an enforced stage decision to the agent-loop model-type vocabulary.

    Returns ``None`` in shadow mode or when there is no decision, so callers
    keep their existing model selection untouched.
    """
    if decision is None or not enforce:
        return None
    return GROUP_TO_MODEL_TYPE.get(decision.applied_group)


# ── Outcome join (calibration data) ─────────────────────────────────────────
# The agent loop hands the decision id to the LLM call; byok_handler's
# ``generate_structured_response`` stashes it on a per-request contextvar
# carrier, and ``_record_outcome_feedback`` (fired per generation attempt)
# writes the attempt's outcome back onto the audit row. That pairing — what
# the stage router picked vs. what actually happened — is the RESCUE/LOSS
# quadrant data the calibration script consumes.
_stage_decision_carrier: ContextVar[Optional[str]] = ContextVar(
    "stage_decision_id", default=None
)


def set_stage_decision_carrier(decision_id: Optional[str]) -> None:
    """Stash the active decision id for the current request's outcome join."""
    _stage_decision_carrier.set(decision_id)


def get_stage_decision_carrier() -> Optional[str]:
    """Read the active decision id (None when no stage decision was made)."""
    return _stage_decision_carrier.get()


def record_stage_outcome(
    decision_id: str,
    *,
    success: bool,
    schema_error: bool = False,
    exception: Optional[BaseException] = None,
    content: Optional[str] = None,
    finish_reason: Optional[str] = None,
    actual_cost: Optional[float] = None,
    actual_latency_ms: Optional[float] = None,
    actual_model: Optional[str] = None,
    actual_provider: Optional[str] = None,
) -> None:
    """Write the generation attempt's outcome onto a stage-decision audit row.

    Called from ``byok_handler._record_outcome_feedback``. Quality is
    assessed with the same signal set the learning router uses (finish_reason,
    content, exception, schema validation). Never raises — calibration data
    is best-effort and must not affect the hot generation path.
    """
    try:
        from core.database import get_db_session
        from core.models import StageRouterAudit

        quality_satisfied: Optional[bool] = None
        try:
            from core.llm.response_quality import assess_response_quality

            quality_satisfied = bool(
                assess_response_quality(
                    content=content,
                    finish_reason=finish_reason,
                    schema_error=schema_error,
                    exception=exception,
                )
            )
        except Exception:
            quality_satisfied = None  # quality signal unavailable — keep success only

        with get_db_session() as db:
            row = db.query(StageRouterAudit).filter(StageRouterAudit.id == decision_id).first()
            if row is None:
                return
            row.success = success
            row.quality_satisfied = quality_satisfied
            row.actual_cost = actual_cost
            row.actual_latency_ms = actual_latency_ms
            row.actual_model = actual_model
            row.actual_provider = actual_provider
            db.commit()
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Stage router outcome join failed (non-fatal): {e}")


_stage_router: Optional[StageRouter] = None


def get_stage_router() -> StageRouter:
    """Process-wide singleton (config read from env at import time)."""
    global _stage_router
    if _stage_router is None:
        picker = StagePicker.EFFICIENT_FIRST
        if STAGE_ROUTING_PICKER == StagePicker.CAPABLE_FIRST.value:
            picker = StagePicker.CAPABLE_FIRST
        elif STAGE_ROUTING_PICKER not in (StagePicker.EFFICIENT_FIRST.value,):
            logger.warning(
                f"Invalid ATOM_STAGE_ROUTING_PICKER '{STAGE_ROUTING_PICKER}', "
                "using efficient_first"
            )
        split: Optional[WeightedRandomSplit] = None
        try:
            from core.llm.routing.traffic_split import get_traffic_split

            split = get_traffic_split()
        except Exception:  # pragma: no cover - harness must never block the router
            split = None
        _stage_router = StageRouter(
            picker=picker,
            confidence_threshold=STAGE_ROUTING_CONFIDENCE_THRESHOLD,
            window=STAGE_ROUTING_WINDOW,
            enabled=STAGE_ROUTING_ENABLED,
            enforce=STAGE_ROUTING_FORCE_ENFORCE,
            split=split,
        )
    return _stage_router
