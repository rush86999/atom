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
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ── Feature flags (runtime settings: env wins > UI admin row > default) ─────
def stage_router_enabled() -> bool:
    """Master switch — on alone = shadow (audit-only)."""
    from core.runtime_settings import get_bool_setting

    return get_bool_setting("ATOM_STAGE_ROUTING_ENABLED", True)


def stage_routing_force_enforce() -> bool:
    """Live tier override (default off = shadow)."""
    from core.runtime_settings import get_bool_setting

    return get_bool_setting("ATOM_STAGE_ROUTING_FORCE_ENFORCE", False)


def stage_routing_picker() -> str:
    from core.runtime_settings import get_setting

    return str(get_setting("ATOM_STAGE_ROUTING_PICKER", "efficient_first") or "efficient_first").strip().lower()


def stage_routing_confidence_threshold() -> float:
    from core.runtime_settings import get_float_setting

    return get_float_setting("ATOM_STAGE_ROUTING_CONFIDENCE_THRESHOLD", 0.5)


def stage_routing_window() -> int:
    from core.runtime_settings import get_int_setting

    return max(1, get_int_setting("ATOM_STAGE_ROUTING_WINDOW", 3))


def _stage_routing_split_raw() -> str:
    from core.runtime_settings import get_setting

    return str(get_setting("ATOM_STAGE_ROUTING_SPLIT", "") or "")


def _stage_split_seed_raw() -> str:
    from core.runtime_settings import get_setting

    return str(get_setting("ATOM_STAGE_ROUTING_SPLIT_SEED", "") or "")


# Deprecated import-time snapshots kept ONLY for legacy readers; live decision
# paths use the accessor functions above.
STAGE_ROUTING_ENABLED = stage_router_enabled()
STAGE_ROUTING_FORCE_ENFORCE = stage_routing_force_enforce()
STAGE_ROUTING_PICKER = stage_routing_picker()
STAGE_ROUTING_CONFIDENCE_THRESHOLD = stage_routing_confidence_threshold()
STAGE_ROUTING_WINDOW = stage_routing_window()

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


@dataclass
class AgentStagePolicy:
    """Effective stage-routing policy for one agent (workload).

    Resolved from the agent's ``configuration["stage_routing"]`` block on
    top of the global env flags. Readiness is workload-specific — every
    agent reaches a different phase at a different time — so enforcement
    must be controllable per agent, not just globally:

    .. code-block:: json

        {"stage_routing": {"enforce": true, "confidence_threshold": 0.45,
                           "picker": "capable_first"}}

    Absent block = inherit the global policy. ``enforce`` is the only field
    that *overrides*; the tuning knobs fall back per-field when unset.
    """

    enforce: bool = False
    picker: StagePicker = StagePicker.EFFICIENT_FIRST
    confidence_threshold: float = field(default_factory=stage_routing_confidence_threshold)
    window: int = field(default_factory=stage_routing_window)
    source: str = "global"  # "global" | "agent-config" (which layer set enforce)


def resolve_agent_policy(
    agent_config: Optional[Dict[str, Any]],
    global_enforce: Optional[bool] = None,
    global_picker: StagePicker = StagePicker.EFFICIENT_FIRST,
    global_threshold: Optional[float] = None,
    global_window: Optional[int] = None,
) -> AgentStagePolicy:
    """Resolve the effective stage-routing policy for one agent.

    Per-agent overrides live in ``AgentRegistry.configuration["stage_routing"]``
    (see ``AgentStagePolicy``). This is the workload-level control: after
    ``scripts/calibrate_stage_router.py`` certifies ONE agent, that agent's
    config flips ``enforce: true`` while every other workload keeps shadowing.
    Never raises — invalid values fall back to the global defaults.
    """
    picker = global_picker
    threshold = max(0.0, min(
        global_threshold if global_threshold is not None else stage_routing_confidence_threshold(),
        1.0,
    ))
    window = max(1, global_window if global_window is not None else stage_routing_window())
    enforce = (
        global_enforce if global_enforce is not None else stage_routing_force_enforce()
    )
    source = "global"
    try:
        block = (agent_config or {}).get("stage_routing")
        if isinstance(block, dict):
            if isinstance(block.get("enforce"), bool):
                enforce = block["enforce"]
                source = "agent-config"
            if block.get("picker") in (StagePicker.EFFICIENT_FIRST.value, StagePicker.CAPABLE_FIRST.value):
                picker = StagePicker(block["picker"])
            elif block.get("picker") is not None:
                logger.warning(
                    f"Invalid stage_routing.picker '{block.get('picker')}' in "
                    "agent config; using global default"
                )
            if isinstance(block.get("confidence_threshold"), (int, float)):
                threshold = max(0.0, min(float(block["confidence_threshold"]), 1.0))
            if isinstance(block.get("window"), int) and block["window"] > 0:
                window = block["window"]
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Agent stage_routing policy resolution failed: {e}")
    return AgentStagePolicy(
        enforce=enforce,
        picker=picker,
        confidence_threshold=threshold,
        window=window,
        source=source,
    )


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
        raw = _stage_routing_split_raw()
        if not raw:
            return None
        try:
            weights = json.loads(raw)
            if not isinstance(weights, dict):
                raise ValueError("split config must be a JSON object")
            seed_raw = _stage_split_seed_raw()
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
        confidence_threshold: Optional[float] = None,
        window: Optional[int] = None,
        enabled: Optional[bool] = None,
        enforce: Optional[bool] = None,
        split: Optional[WeightedRandomSplit] = None,
        audit: bool = True,
    ) -> None:
        confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else stage_routing_confidence_threshold()
        )
        window = window if window is not None else stage_routing_window()
        enabled = enabled if enabled is not None else stage_router_enabled()
        enforce = enforce if enforce is not None else stage_routing_force_enforce()
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
        policy: Optional[AgentStagePolicy] = None,
    ) -> StageDecision:
        """Route one turn from its tool-outcome history.

        ``policy`` (per-agent override) wins over the router's own
        picker/threshold/window when provided.
        """
        picker = policy.picker if policy else self.picker
        threshold = policy.confidence_threshold if policy else self.confidence_threshold
        window = policy.window if policy else self.window

        signals = self.extract_signals(outcomes, window=window)
        split_group: Optional[str] = None
        if use_split and self.split is not None:
            split_group = self.split.pick()

        default_group = CAPABLE if picker == StagePicker.CAPABLE_FIRST else EFFICIENT

        if signals.critical:
            selected_group = CAPABLE
            source = DecisionSource.OVERRIDE
            confidence = 1.0
        else:
            signed = self._score(signals)
            confidence = abs(signed)
            if confidence >= threshold:
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
        policy: Optional[AgentStagePolicy] = None,
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
            decision = self.decide(
                outcomes,
                previous_group=previous_group,
                use_split=use_split,
                policy=policy,
            )
            if self.audit:
                self.record_audit(
                    decision=decision,
                    signals=self.extract_signals(
                        outcomes, window=policy.window if policy else None
                    ),
                    agent_id=agent_id,
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    execution_id=execution_id,
                    step_index=step_index,
                    picker=(policy.picker.value if policy else self.picker.value),
                    confidence_threshold=(
                        policy.confidence_threshold if policy else self.confidence_threshold
                    ),
                    policy_source=(policy.source if policy else "global"),
                    enforced=(policy.enforce if policy else self.enforce),
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
        picker: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        policy_source: str = "global",
        enforced: Optional[bool] = None,
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
                        picker=picker or self.picker.value,
                        confidence_threshold=(
                            confidence_threshold
                            if confidence_threshold is not None
                            else self.confidence_threshold
                        ),
                        signals=signals.to_json() if signals else None,
                        selected_group=decision.selected_group,
                        applied_group=decision.applied_group,
                        split_group=decision.split_group,
                        default_group=decision.default_group,
                        confidence=decision.confidence,
                        decision_source=decision.source,
                        enforced=self.enforce if enforced is None else enforced,
                        model_type=model_type,
                        handoff_note=decision.handoff_note,
                        rationale=decision.rationale,
                        policy_source=policy_source,
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

# Guidance thresholds for operator-facing phase/readiness status. "Ready" is
# NOT a fixed turn count — it is per-workload, per-arm, and effect-size-aware:
# detecting a 10-point success-rate gap with 80% power needs ~200 outcome
# rows per arm (two-proportion z-test, base rate ~0.8); a 20-point gap needs
# ~50. MIN_OUTCOME_ROWS_PER_ARM is only the floor for an *attempt* at
# calibration; the status endpoint reports the minimum detectable gap at the
# current volume so operators can judge sufficiency for themselves.
MIN_OUTCOME_ROWS_PER_ARM = 30
DEFAULT_TARGET_EFFECT_SIZE = 0.10  # 10-point success-rate gap to detect
_ALPHA = 0.05
_POWER = 0.80
_Z_ALPHA = 1.959964  # z(0.975)
_Z_BETA = 0.841621  # z(0.80)


def min_turns_per_arm(
    effect_size: float = DEFAULT_TARGET_EFFECT_SIZE,
    base_rate: float = 0.8,
    alpha: float = _ALPHA,
    power: float = _POWER,
) -> int:
    """Outcome rows needed per arm to detect ``effect_size`` with ``power``.

    Standard two-proportion sample-size formula (pooled z-approximation,
    continuity correction omitted):

        n = (z_{1-α/2} + z_{1-β})^2 · 2·p̄(1-p̄) / Δ^2,  p̄ = base + Δ/2

    Returns 0 when the inputs make the formula inapplicable (Δ ≤ 0 or p̄
    outside (0, 1)).
    """
    if effect_size <= 0 or not (0.0 < base_rate < 1.0):
        return 0
    z_alpha = 1.959964 if alpha == 0.05 else _z_score(1.0 - alpha / 2)
    z_beta = 0.841621 if power == 0.80 else _z_score(power)
    p_bar = base_rate + effect_size / 2
    if not (0.0 < p_bar < 1.0):
        return 0
    pooled = p_bar * (1.0 - p_bar)
    n = (z_alpha + z_beta) ** 2 * 2.0 * pooled / (effect_size ** 2)
    return math.ceil(n)


def min_detectable_gap(
    turns_per_arm: int,
    base_rate: float = 0.8,
    alpha: float = _ALPHA,
    power: float = _POWER,
) -> float:
    """The smallest success-rate gap detectable with the given turns per arm.

    Inverse of ``min_turns_per_arm`` (fixed-point solve — the forward formula
    pools variance at ``base + Δ/2``, so Δ appears on both sides). At low
    volumes only LARGE gaps are visible, which is exactly why a flat "50
    turns" rule lies about sufficiency — a 5-point quality difference needs
    ~800 turns/arm.
    """
    if turns_per_arm <= 0:
        return 1.0
    z_alpha = 1.959964 if alpha == 0.05 else _z_score(1.0 - alpha / 2)
    z_beta = 0.841621 if power == 0.80 else _z_score(power)
    z_sq = (z_alpha + z_beta) ** 2
    gap = math.sqrt(z_sq * 2.0 * base_rate * (1.0 - base_rate) / turns_per_arm)
    for _ in range(4):  # fixed point: p̄ = base + Δ/2
        p_bar = base_rate + gap / 2
        if not (0.0 < p_bar < 1.0):
            break
        gap = math.sqrt(z_sq * 2.0 * p_bar * (1.0 - p_bar) / turns_per_arm)
    return gap


def _z_score(p: float) -> float:
    """Inverse normal CDF (Acklam's approximation) — tiny, dependency-free."""
    if p <= 0.0:
        return -6.0
    if p >= 1.0:
        return 6.0
    a = (-39.69683028665376, 220.9460984245205, -275.9285104469687,
         138.3577518672690, -30.66479806614716, 2.506628277459239)
    b = (-54.47609879822406, 161.5858368580409, -155.6989798598866,
         66.80131188771972, -13.28068155288572)
    c = (-0.007784894002430293, -0.3223964580411365, -2.400758277161838,
         -2.549732539343734, 4.374664141464968, 2.938163982698783)
    d = (0.007784695709041462, 0.3224671290700398, 2.445134137142996,
         3.754408661907416)
    p_low = 0.02425
    p_high = 1.0 - p_low
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    if p > p_high:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0
    )


def _read_arm_counts() -> Dict[str, Dict[str, int]]:
    """Per-workload outcome-joined arm counts: {agent_id: {efficient: n, capable: n}}.

    Only rows with a populated outcome (``success IS NOT NULL``) count — a
    shadowed turn without an outcome join tells us nothing about what
    happened. Raises on DB failure so the caller can distinguish "no data
    yet" from "cannot read the audit table".
    """
    from collections import defaultdict

    from sqlalchemy import func

    from core.database import get_db_session
    from core.models import StageRouterAudit

    counts: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {EFFICIENT: 0, CAPABLE: 0}
    )
    with get_db_session() as db:
        rows = (
            db.query(
                StageRouterAudit.agent_id,
                StageRouterAudit.applied_group,
                func.count(),
            )
            .filter(StageRouterAudit.success.isnot(None))
            .group_by(StageRouterAudit.agent_id, StageRouterAudit.applied_group)
            .all()
        )
        for agent_id, group, n in rows:
            if group in (EFFICIENT, CAPABLE):
                counts[agent_id or "unknown"][group] = int(n)
    return dict(counts)


def stage_router_status() -> Dict[str, Any]:
    """Operator guidance: what phase the stage router is in and what to flip.

    The stage router ships shadow-on (audit-only). This answers the question
    "when do I turn on the next flag?":

    - ``off``        → set ``ATOM_STAGE_ROUTING_ENABLED=true`` to start shadow.
    - ``collecting`` → shadow scoring is active but no workload has enough
                       outcome-joined turns in BOTH arms yet. ``sufficiency``
                       reports per workload the arm counts and the minimum
                       success-rate gap detectable at that volume — turns
                       differ in task complexity, so a flat turn count can't
                       certify anything; volume must be enough to *see* the
                       quality difference you care about.
    - ``ready``      → at least one workload has ≥ ``MIN_OUTCOME_ROWS_PER_ARM``
                       in both arms; run ``scripts/calibrate_stage_router.py``,
                       review the RESCUE/LOSS quadrants, then set
                       ``ATOM_STAGE_ROUTING_FORCE_ENFORCE=true`` only if
                       escalation is justified per workload.
    - ``enforced``   → live routing is on; keep shadow logging for continuous
                       re-certification (re-run calibration periodically).

    Never raises — a DB failure returns an ``error`` phase with generic text.
    """
    config = {
        "enabled": stage_router_enabled(),
        "force_enforce": stage_routing_force_enforce(),
        "picker": stage_routing_picker(),
        "confidence_threshold": stage_routing_confidence_threshold(),
        "traffic_split": bool(_stage_routing_split_raw()),
    }
    try:
        from core.llm.stage_router_automation import get_automation_status

        config["automation"] = get_automation_status()
    except Exception:  # pragma: no cover - defensive
        config["automation"] = {}
    try:
        arms = _read_arm_counts()
    except Exception as e:
        logger.warning(f"Stage router status DB read failed: {e}")
        return {
            **config,
            "phase": "error",
            "next_action": "Status unavailable — check the audit table "
            "(llm_stage_router_audit) exists; run the migration if not.",
            "why": "The guidance surface reads audit-row counts; without the "
            "table (or DB access) it cannot tell you what phase you are in.",
            "counts": {"outcome_joined": 0},
        }
    total_rows = sum(sum(a.values()) for a in arms.values())
    workloads = sorted(arms.keys())

    if not config["enabled"]:
        return {
            **config,
            "phase": "off",
            "counts": {"outcome_joined": total_rows},
            "next_action": (
                "Set ATOM_STAGE_ROUTING_ENABLED=true to start shadow scoring "
                "(audit-only; model selection is untouched)."
            ),
            "why": (
                "Shadow mode is free: it scores every agent turn from "
                "tool-result signals and writes an audit row, but never "
                "changes which model runs. Turning it on now starts the "
                "measurement pipeline nothing else can work without."
            ),
        }

    harness_note = (
        "The A/B harness is active (ATOM_TRAFFIC_SPLIT / ATOM_STAGE_ROUTING_SPLIT) "
        "— audit rows carry forced applied_group arms for RESCUE/LOSS comparison."
        if config["traffic_split"]
        else "Enable the A/B harness (ATOM_TRAFFIC_SPLIT=true + "
        "ATOM_STAGE_ROUTING_SPLIT JSON weights) to collect both-arm "
        "RESCUE/LOSS comparison data."
    )

    if config["force_enforce"]:
        return {
            **config,
            "phase": "enforced",
            "counts": {"outcome_joined": total_rows},
            "next_action": (
                "Live routing is active. Keep shadow logging on and re-run "
                "scripts/calibrate_stage_router.py periodically to re-certify "
                f"thresholds. Kill switch: ATOM_STAGE_ROUTING_ENABLED=false. {harness_note}"
            ),
            "why": (
                "Routing gains are workload-dependent (RouteGuard: gains "
                "collapsed to 3 of 86 benchmark cells under resampling). "
                "Continuous re-certification against your own outcome rows is "
                "the guardrail — workloads drift as models and tasks change."
            ),
        }

    # Per-workload sufficiency: both arms observed, and the volume is enough
    # to see the target gap (or the biggest gap it *can* see is reported).
    # Every agent reaches a different phase at a different pace — this is the
    # per-workload view; enforcement is controlled per agent via
    # configuration["stage_routing"] (see resolve_agent_policy).
    sufficiency = {}
    for workload in workloads:
        n_efficient = arms[workload][EFFICIENT]
        n_capable = arms[workload][CAPABLE]
        turns = min(n_efficient, n_capable)
        ready = turns >= MIN_OUTCOME_ROWS_PER_ARM
        sufficiency[workload] = {
            "phase": "ready" if ready else "collecting",
            "efficient_turns": n_efficient,
            "capable_turns": n_capable,
            "min_detectable_gap": round(min_detectable_gap(turns), 3),
            "turns_needed_for_10pt_gap": min_turns_per_arm(),
            "calibration_ready": ready,
        }
    ready_workloads = [w for w, s in sufficiency.items() if s["calibration_ready"]]

    if not ready_workloads:
        best_note = ""
        if sufficiency:
            best_workload = max(
                sufficiency,
                key=lambda w: min(
                    sufficiency[w]["efficient_turns"], sufficiency[w]["capable_turns"]
                ),
            )
            best_gap = sufficiency[best_workload]["min_detectable_gap"]
            best_note = (
                f"Best workload '{best_workload}' can detect ~{best_gap:.0%} "
                "success-rate gaps at current volume; detecting a 10-point "
                f"gap needs ~{min_turns_per_arm()} turns/arm. "
            )
        return {
            **config,
            "phase": "collecting",
            "counts": {"outcome_joined": total_rows},
            "sufficiency": sufficiency,
            "next_action": (
                f"Shadow scoring active — {total_rows} outcome-joined turns "
                f"across {len(workloads)} workload(s); none has "
                f"{MIN_OUTCOME_ROWS_PER_ARM}+ outcome-joined turns in BOTH "
                f"arms yet. {best_note}{harness_note}"
            ),
            "why": (
                "Calibration needs both arms of the comparison (what the "
                "router WOULD have picked vs. what ran and succeeded) AND "
                "enough volume to see the quality difference — turns differ "
                "in task complexity, so '50 turns' is not a magic number: a "
                "10-point success-rate gap needs ~200 outcome rows per arm, "
                "a 20-point gap ~50, a 5-point gap ~500 (two-proportion "
                "z-test, 80% power). Enforcing with less means making "
                "decisions on noise."
            ),
        }

    return {
        **config,
        "phase": "ready",
        "counts": {"outcome_joined": total_rows},
        "sufficiency": sufficiency,
        "ready_workloads": ready_workloads,
        "next_action": (
            f"Workloads ready for calibration: {', '.join(ready_workloads)}. "
            "Run scripts/calibrate_stage_router.py, review the RESCUE/LOSS "
            "quadrants, then enforce per workload — set "
            'configuration["stage_routing"]["enforce"]=true on ONLY the '
            "certified agent(s), or flip the global "
            "ATOM_STAGE_ROUTING_FORCE_ENFORCE=true for all. "
            f"{harness_note}"
        ),
        "why": (
            "Ready means both arms are observed at sufficient volume for "
            "at least one workload — enough to compute RESCUE (capable arm "
            "rescued a turn efficient would have failed) vs LOSS (capable "
            "arm wasted) and to see the gap you care about. Note the "
            "min_detectable_gap per workload: if your workloads' quality "
            "difference is smaller than that, keep collecting before "
            "enforcing (RouteGuard-style certification — arXiv:2608.07583)."
        ),
    }


def get_stage_router() -> StageRouter:
    """Process-wide singleton (config read from env at import time)."""
    global _stage_router
    if _stage_router is None:
        picker = StagePicker.EFFICIENT_FIRST
        if stage_routing_picker() == StagePicker.CAPABLE_FIRST.value:
            picker = StagePicker.CAPABLE_FIRST
        elif stage_routing_picker() not in (StagePicker.EFFICIENT_FIRST.value,):
            logger.warning(
                f"Invalid ATOM_STAGE_ROUTING_PICKER '{stage_routing_picker()}', "
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
            confidence_threshold=stage_routing_confidence_threshold(),
            window=stage_routing_window(),
            enabled=stage_router_enabled(),
            enforce=stage_routing_force_enforce(),
            split=split,
        )
    # Auto-certification (consent-gated): lazily start the background pass
    # that certifies per-workload enforcement from calibration data. Never
    # blocks the routing path.
    try:
        from core.llm.stage_router_automation import ensure_automation_task

        ensure_automation_task()
    except Exception:  # pragma: no cover - defensive
        pass
    return _stage_router
