"""
Process-wide singleton registry for the LearningBasedRouter.

The learning router holds in-memory state (per-model predictors, cached
weights, pending decisions) that MUST persist across requests for the system
to actually learn. Previously, each call to ``_get_learning_router``
constructed a throwaway instance — predictors were trained and immediately
garbage-collected, so the learning engine was inert.

This module provides a single shared instance, lazily built on first access,
hydrated from the DB and from persisted per-model predictor ``.pkl`` files on
init. Thread-safe via a lock (the app is async, but uvicorn workers share
state within a process).
"""

from __future__ import annotations

import logging
import os
import time
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_SINGLETON: Optional["object"] = None  # LearningBasedRouter, typed loosely to avoid import cycle


def learning_router_mode() -> str:
    """The router's mode: "true" | "false" | "auto".

    AUTO (the default) self-activates re-ranking when the observation
    history is thick enough to re-rank safely and falls back to static
    BPC ordering when it is not — the flip is a DATA question the system
    can answer itself (owner ask, 2026-09-15: cold-start noise was the
    only reason the flag was manual). "true"/"false" remain the operator
    overrides; env wins via the resolver."""
    try:
        from core.runtime_settings import resolve_setting

        resolved = resolve_setting("ATOM_LEARNING_ROUTER")
        if resolved.source != "unknown" and resolved.value is not None:
            v = str(resolved.value).strip().lower()
            if v in ("auto", "true", "false", "1", "0", "yes", "no", "on", "off"):
                if v in ("1", "yes", "on"):
                    return "true"
                if v in ("0", "no", "off"):
                    return "false"
                return v
    except Exception:  # noqa: BLE001 — fall back to the raw env read
        pass
    raw = os.getenv("ATOM_LEARNING_ROUTER", "auto").strip().lower()
    if raw in ("1", "yes", "on", "true"):
        return "true"
    if raw in ("0", "no", "off", "false"):
        return "false"
    return "auto"


# AUTO-mode readiness thresholds: enough RECENT verdict rows, spread over
# enough models, that re-ranking is signal rather than noise. Deliberately
# conservative: two models at eight observations each is the floor at
# which a per-model comparison carries any information.
_LR_AUTO_MIN_ROWS = int(os.getenv("ATOM_LEARNING_ROUTER_AUTO_MIN_ROWS", "30") or 30)
_LR_AUTO_MIN_MODELS = int(os.getenv("ATOM_LEARNING_ROUTER_AUTO_MIN_MODELS", "2") or 2)
_LR_AUTO_MIN_PER_MODEL = int(os.getenv("ATOM_LEARNING_ROUTER_AUTO_MIN_PER_MODEL", "8") or 8)
_LR_AUTO_WINDOW_DAYS = int(os.getenv("ATOM_LEARNING_ROUTER_AUTO_WINDOW_DAYS", "7") or 7)
_LR_READY_TTL_S = 60.0
_lr_ready_cache: dict = {"ts": 0.0, "ready": False, "logged": None}


def learning_history_ready() -> bool:
    """True when llm_routing_feedback holds enough recent per-model
    verdicts to re-rank safely (auto mode's gate). Cached 60s; fail-closed
    to NOT-ready on any error (static BPC ordering is always safe)."""
    now = time.monotonic()
    if now - _lr_ready_cache["ts"] < _LR_READY_TTL_S:
        return _lr_ready_cache["ready"]
    ready = False
    try:
        from datetime import datetime, timedelta

        from core.database import get_db_session
        from core.models import LLMRoutingFeedback

        cutoff = datetime.utcnow() - timedelta(days=_LR_AUTO_WINDOW_DAYS)
        with get_db_session() as db:
            rows = (
                db.query(
                    LLMRoutingFeedback.model_id,
                )
                .filter(LLMRoutingFeedback.created_at >= cutoff)
                .all()
            )
        total = len(rows)
        per_model: dict = {}
        for (model_id,) in rows:
            per_model[model_id] = per_model.get(model_id, 0) + 1
        qualified = sum(
            1 for n in per_model.values() if n >= _LR_AUTO_MIN_PER_MODEL
        )
        ready = (
            total >= _LR_AUTO_MIN_ROWS
            and qualified >= _LR_AUTO_MIN_MODELS
        )
        state = (ready, total, qualified)
        if _lr_ready_cache.get("logged") != state:
            logger.info(
                f"[LearningRouter] auto-mode readiness: {state[1]} verdict "
                f"row(s) in the last {_LR_AUTO_WINDOW_DAYS}d, "
                f"{state[2]} model(s) with >= {_LR_AUTO_MIN_PER_MODEL} "
                f"observations -> re-ranking "
                f"{'ENABLED' if ready else 'not yet (static BPC ordering)'} "
                f"(thresholds: >={_LR_AUTO_MIN_ROWS} rows, "
                f">={_LR_AUTO_MIN_MODELS} models)"
            )
            _lr_ready_cache["logged"] = state
    except Exception as e:  # noqa: BLE001 — fail-closed to static ordering
        logger.debug(f"learning-history readiness check skipped: {e}")
        ready = False
    _lr_ready_cache["ts"] = now
    _lr_ready_cache["ready"] = ready
    return ready


def readiness_report() -> dict:
    """WHY auto mode has (or has not) activated — the numbers behind the flip.

    ``auto`` is the default, so "is it on?" is a data question the operator
    cannot answer from the mode string alone: on a fresh install it reads
    ``auto`` while doing nothing, and the only signal that it flipped is a log
    line. This reports the actual counts against the actual thresholds, so the
    Settings surface can show "auto — waiting for data (1/30 rows, 0/2 models)"
    instead of an opaque ``auto``.

    Read-only and fail-soft: a query failure reports ``error`` rather than
    raising, and never changes what the router decides.
    """
    report: dict = {
        "mode": learning_router_mode(),
        "enabled": None,
        "ready": None,
        "rows_in_window": 0,
        "models_with_enough_observations": 0,
        "thresholds": {
            "min_rows": _LR_AUTO_MIN_ROWS,
            "min_models": _LR_AUTO_MIN_MODELS,
            "min_observations_per_model": _LR_AUTO_MIN_PER_MODEL,
            "window_days": _LR_AUTO_WINDOW_DAYS,
        },
        "reason": "",
    }
    try:
        from datetime import datetime, timedelta

        from core.database import get_db_session
        from core.models import LLMRoutingFeedback

        cutoff = datetime.utcnow() - timedelta(days=_LR_AUTO_WINDOW_DAYS)
        with get_db_session() as db:
            rows = (
                db.query(LLMRoutingFeedback.model_id)
                .filter(LLMRoutingFeedback.created_at >= cutoff)
                .all()
            )
        per_model: dict = {}
        for (model_id,) in rows:
            per_model[model_id] = per_model.get(model_id, 0) + 1
        qualified = sorted(
            (n for n in per_model.values() if n >= _LR_AUTO_MIN_PER_MODEL),
            reverse=True,
        )
        report["rows_in_window"] = len(rows)
        report["models_with_enough_observations"] = len(qualified)

        mode = report["mode"]
        if mode == "false":
            report["reason"] = "re-ranking is switched off manually (mode=false)"
        elif mode == "true":
            report["reason"] = "re-ranking is switched on manually (mode=true)"
        elif (
            report["rows_in_window"] >= _LR_AUTO_MIN_ROWS
            and len(qualified) >= _LR_AUTO_MIN_MODELS
        ):
            report["reason"] = (
                f"active — {report['rows_in_window']} observations across "
                f"{len(qualified)} models; re-ranking by fabrication/quality history"
            )
        else:
            missing = []
            if report["rows_in_window"] < _LR_AUTO_MIN_ROWS:
                missing.append(
                    f"{report['rows_in_window']}/{_LR_AUTO_MIN_ROWS} observations"
                )
            if len(qualified) < _LR_AUTO_MIN_MODELS:
                missing.append(
                    f"{len(qualified)}/{_LR_AUTO_MIN_MODELS} models with "
                    f">= {_LR_AUTO_MIN_PER_MODEL} observations each"
                )
            report["reason"] = (
                "waiting for evidence — " + ", ".join(missing)
                + f" in the last {_LR_AUTO_WINDOW_DAYS}d; static BPC ordering "
                "until then (outcomes are recorded in every mode)"
            )
    except Exception as e:  # noqa: BLE001 — diagnostics must never raise
        report["reason"] = f"readiness unavailable ({type(e).__name__})"

    try:
        report["ready"] = learning_history_ready()
        report["enabled"] = learning_router_enabled()
    except Exception:  # noqa: BLE001
        pass
    return report


def learning_router_enabled() -> bool:
    """Whether re-ranking by learned satisfaction is active.

    true -> always; false -> never; auto (default) -> when the observation
    history is ready (learning_history_ready). Observation itself is NEVER
    gated — rows accrue in every mode so auto has data to flip on."""
    mode = learning_router_mode()
    if mode == "true":
        return True
    if mode == "false":
        return False
    return learning_history_ready()


# Truthy set is intentionally broad: the EMA scoring branch reads this flag in
# learning_llm_router._score_candidates via the SAME set, so centralizing the
# parse here keeps every caller (scoring, stats endpoint, dashboard) consistent
# — previously chat_routes/stats used a "true"-only check that disagreed with
# the {"1","true","yes","on"} set used at the scoring branch.
_TRUTHY = {"1", "true", "yes", "on"}


def ema_router_enabled() -> bool:
    """Whether the EMA (online telemetry) scoring path is enabled.

    Note: this only takes effect when ``learning_router_enabled()`` is also
    true — EMA scoring operates on ``_ema_scores`` state that is only updated
    through the learning router singleton (which the master gate controls).
    """
    try:
        from core.runtime_settings import resolve_setting

        resolved = resolve_setting("ATOM_EMA_ROUTER_ENABLED")
        if resolved.source != "unknown":
            return bool(resolved.value)
    except Exception:  # noqa: BLE001 — fall back to the raw env read
        pass
    return os.getenv("ATOM_EMA_ROUTER_ENABLED", "false").lower() in _TRUTHY


async def record_timeout_outcome(
    model_id: str,
    task_type: Optional[str] = None,
    tenant_id: str = "default",
    elapsed_s: Optional[float] = None,
) -> bool:
    """Tell the router this MODEL WAS TOO SLOW for the window it got.

    Cancelled planning/structured calls leave NO outcome row — the caller's
    wait_for cancels the coroutine before the generation path records
    anything — so a model that burns whole budgets on hidden reasoning kept
    winning the planning route with zero evidence against it (live
    2026-09-15/16: 75s canvas-edit plans, 25s tool-plan timeouts, turn
    after turn, glm still the cost-priority pick). This records the timeout
    where the cancellation is CAUGHT (inside the call), where the resolved
    model is known: truncated-class satisfaction 0.3 (visibly incomplete —
    above fabrication's 0.15 so it never trips the fabrication BENCH;
    below refusal) with the measured latency. The learning router's
    per-model predictor then demotes the model for these task types once
    it re-ranks; observation accrues in every mode. Best-effort, never
    raises."""
    try:
        import uuid as _uuid

        from core.learning_llm_router import RoutingFeedback, LearningBasedRouter

        router = LearningBasedRouter.__new__(LearningBasedRouter)
        feedback = RoutingFeedback(
            routing_result_id=str(_uuid.uuid4()),
            tenant_id=tenant_id,
            task_type=task_type or "planning",
            model_id=model_id,
            success=False,
            quality_satisfied=False,
            cost_within_budget=True,
            user_satisfaction=0.3,
            actual_cost=0.0,
            actual_latency_ms=(elapsed_s or 0.0) * 1000.0,
        )
        router._persist_feedback(feedback, {"verdict": "timeout"})
        return True
    except Exception as e:  # noqa: BLE001 — best-effort signal
        logger.debug(f"timeout outcome not recorded: {e}")
        return False


async def record_fabrication_signal(
    model_id: str,
    task_type: Optional[str] = None,
    tenant_id: str = "default",
    unsupported_figures: Optional[list] = None,
    ungrounded_claims: Optional[list] = None,
) -> bool:
    """Tell the learning router that this MODEL FABRICATED on a real turn.

    The generation path records an outcome as soon as ``generate_completion``
    returns, so it cannot know about fabrication — the deterministic figure
    check and the verification panel both run on the assembled reply, after
    that. This is the corrective signal: the orchestrator calls it when a guard
    catches an invented figure or an unsupported claim, and the per-model
    predictor learns "this model fabricates THIS task type" (quality 0.1/0.15,
    issue ``unsupported_figures``/``ungrounded_claims``).

    That is what turns hallucination into a ROUTING input: BPC's candidate list
    is re-ranked by learned satisfied-rate, so a model that keeps inventing
    numbers loses to one that does not. Best-effort — returns False (and never
    raises) when the learning router is off, so the flag stays the only switch.

    ``model_id`` should be the model that PRODUCED the reply (the resolved
    model), not the one that was requested."""
    # NO SIGNAL, NO OBSERVATION. `assess_response_quality(content="")` reports
    # an "empty" issue, so calling it unconditionally would write a bogus
    # fabrication row for every clean turn — the guard must require an actual
    # verdict to carry.
    if not unsupported_figures and not ungrounded_claims:
        return False
    try:
        from core.llm.response_quality import assess_response_quality
        from core.learning_llm_router import LearningBasedRouter

        quality = assess_response_quality(
            # Non-empty placeholder: the SIGNAL is the verdict, this call must
            # not re-judge content (the caller already has the reply).
            content="[guarded reply]",
            unsupported_figures=unsupported_figures,
            ungrounded_claims=ungrounded_claims,
        )
        if quality.quality_satisfied:
            return False
        import uuid

        routed_task = task_type or "general"
        feedback = LearningBasedRouter.build_feedback(
            routing_result_id=str(uuid.uuid4()),
            tenant_id=tenant_id or "default",
            model_id=model_id,
            task_type=routed_task,
            quality=quality,
        )
        # OBSERVATION IS ALWAYS RECORDED, even with the learning router's
        # routing switch off. The flag gates whether BPC RE-RANKS by the
        # learned signal — not whether the evidence exists. Writing the row
        # unconditionally means flipping ATOM_LEARNING_ROUTER on later starts
        # from real fabrication history instead of an empty table, and the row
        # is the audit trail ("which model fabricated what, when").
        from core.learning_llm_router import LearningBasedRouter

        verdict = ("unsupported_figures" if unsupported_figures
                   else "ungrounded_claims")

        # ONE WRITE PER VERDICT. This used to write the row here AND let
        # ``record_feedback`` write it again (with ``recovered_features=None``),
        # so a single fabrication produced TWO rows — one carrying the verdict,
        # one carrying none. The duplicate inflated the fabrication bench's
        # denominator, and trained a second copy on task-default features
        # (measured 2026-09-16: one verdict -> two ``_persist_feedback`` calls,
        # and two identical live rows sharing routing_result_id ad1fa3e1-…).
        #
        # ``record_feedback`` persists the row itself from
        # ``feedback._prompt_features``, so stamping the verdict there keeps the
        # provenance on the SINGLE row. The manual write is kept only for the
        # flag-off path, where no router exists to do it.
        router = get_learning_router_instance()
        _persisted = False
        if router is not None:
            feedback._prompt_features = {"verdict": verdict}  # type: ignore[attr-defined]
            await router.record_feedback(feedback)
            _persisted = True
        else:
            writer = LearningBasedRouter.__new__(LearningBasedRouter)
            try:
                writer._persist_feedback(feedback, {"verdict": verdict})
                _persisted = True
            except Exception as persist_err:  # noqa: BLE001
                logger.debug(f"fabrication row persist skipped: {persist_err}")
        logger.info(
            "[LearningRouter] fabrication observed for %s (%s): %s%s",
            model_id, routed_task, ", ".join(quality.issues),
            "" if router is not None else " [routing flag off — recorded, not routed]",
        )
        return bool(_persisted or router is not None)
    except Exception as e:  # noqa: BLE001 — telemetry must never break a turn
        logger.debug(f"fabrication signal skipped: {e}")
        return False


def get_learning_router_instance(observe_only: bool = False):
    """Return the process-wide LearningBasedRouter singleton.

    Returns ``None`` when the learning router is disabled or instantiation
    fails. On first successful call, instantiates the router, hydrates
    ``_preference_data`` from the DB, and restores any persisted per-model
    predictors from disk. Subsequent calls return the same object.

    ``observe_only=True`` bypasses the enabled gate: outcome and
    fabrication rows accrue in EVERY mode (auto's data supply — gating
    observation would starve the readiness check that flips re-ranking
    on). Re-ranking consumers keep the default and honor the gate."""
    global _SINGLETON
    if not observe_only and not learning_router_enabled():
        return None
    if _SINGLETON is not None:
        return _SINGLETON

    with _LOCK:
        # Double-checked locking: another thread may have built it.
        if _SINGLETON is not None:
            return _SINGLETON
        try:
            from core.learning_llm_router import get_learning_router

            # Pass None as the db session — the router never uses self.db for
            # reads or writes (every DB-touching method opens its own
            # short-lived get_db_session). Holding a SessionLocal forever leaks
            # a connection from the pool.
            router = get_learning_router(None)

            # Hydrate preference data from the DB so learned data survives restarts.
            try:
                loaded = router.load_feedback_from_db()
                logger.info(f"Learning router hydrated {loaded} feedback rows from DB")
            except Exception as load_err:
                logger.warning(f"Could not hydrate learning router from DB: {load_err}")

            _SINGLETON = router
            logger.info("Learning router singleton initialized")
            return router
        except Exception as e:
            logger.warning(f"Could not instantiate learning router singleton: {e}")
            return None


def reset_learning_router_instance() -> None:
    """Drop the singleton (for tests)."""
    global _SINGLETON
    with _LOCK:
        _SINGLETON = None
