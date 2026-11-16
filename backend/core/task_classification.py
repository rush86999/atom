"""Canonical task classification for autonomy boundaries.

This module does NOT introduce a new scheduler, policy registry, or
classifier. It composes the classifiers the repository already trusts:

- **difficulty** — ``QueryComplexity`` from
  ``core.llm.byok_handler.classify_query_complexity`` (the existing
  deterministic routing classifier; task difficulty is deliberately not the
  governance action-risk integer in ``ACTION_COMPLEXITY``).
- **category** — ``TaskDomain`` and its deterministic ``infer_domain`` used by
  the verification cascade.
- **domain** — ``core.domain_attribution.resolve_domain`` business-role
  attribution.

Trusted profiles are server-built objects. They are never parsed from a
request body, a model tool argument, or a mutable ``AgentRegistry.category``.
A context variable lets nested tool gates reuse the profile bound at run
start; the same object is placed in the dispatch context for the shared MCP
guard.
"""
from __future__ import annotations

import logging
import re
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

TASK_PROFILE_CONTEXT_KEY = "_trusted_task_profile"

_DOMAIN_SLUG = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")

DIFFICULTY_VALUES = ("simple", "moderate", "complex", "advanced")
CATEGORY_VALUES = ("code", "math", "qa", "extraction", "planning", "prose")
DOMAIN_SUGGESTIONS = (
    "finance", "hr", "marketing", "operations", "sales", "support",
)


@dataclass(frozen=True)
class TaskProfile:
    """Immutable, server-owned task classification snapshot."""

    difficulty: Optional[str]
    category: Optional[str]
    domain: Optional[str]
    signals: Mapping[str, str] = field(default_factory=dict)
    source: str = "server"
    #: Server-bound task owner (the human on whose behalf the run executes).
    #: Never accepted from a request body or model tool argument.
    owner_user_id: Optional[str] = None
    #: Opaque per-task-start identity. Every server-built profile gets a new
    #: value, so a clearance granted for one task can never authorize another
    #: task that happens to reuse the same context dict, owner, or rule ids.
    #: Never serialized into prompts or accepted from caller/model material.
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def as_dict(self) -> Dict[str, Any]:
        data = {
            "difficulty": self.difficulty,
            "category": self.category,
            "domain": self.domain,
            "source": self.source,
            "signals": dict(self.signals),
        }
        if self.owner_user_id:
            data["owner_user_id"] = self.owner_user_id
        return data

    def missing_dimensions(self) -> tuple:
        return tuple(
            dimension
            for dimension in ("difficulty", "category", "domain")
            if not getattr(self, dimension)
        )


def is_trusted_task_profile(value: Any) -> bool:
    """Only a server-built, immutable profile is authoritative."""
    return isinstance(value, TaskProfile) and value.source == "server"


def is_valid_domain_slug(value: Any) -> bool:
    return bool(_DOMAIN_SLUG.match(str(value or "").strip().lower()))


def _clean_text(value: Any, limit: int = 4000) -> str:
    return str(value or "").strip()[:limit]


def _step_text(steps: Optional[Sequence[Any]]) -> str:
    """Flatten plan-step text without executing or trusting model payloads.

    Steps normally come from the durable assignment plan or workflow
    definition (server-owned). Only small textual fields are read; nested
    executable input is ignored.
    """
    parts = []
    for step in steps or []:
        if isinstance(step, Mapping):
            for key in ("title", "instruction", "description", "operation_type",
                        "adapter", "action"):
                value = step.get(key)
                if value:
                    parts.append(str(value)[:500])
        elif step is not None:
            parts.append(str(step)[:500])
    return " ".join(parts)[:4000]


def _classify_difficulty(text: str, task_type: Optional[str]) -> Optional[str]:
    if not text:
        return None
    try:
        from core.llm.byok_handler import classify_query_complexity

        value = classify_query_complexity(text, task_type)
        return str(getattr(value, "value", value) or "").lower() or None
    except Exception as exc:  # noqa: BLE001 — source unavailable => unknown
        logger.debug("task difficulty classification skipped: %s", exc)
        return None


def _classify_category(text: str) -> Optional[str]:
    if not text:
        return None
    try:
        from core.orchestration.verification.domain import (
            TaskDomain,
            infer_domain,
        )

        step = SimpleNamespace(
            capability="", name="", description=text, parameters={})
        value = infer_domain(step)
        if value == TaskDomain.UNKNOWN:
            return None
        return str(value.value).lower() or None
    except Exception as exc:  # noqa: BLE001
        logger.debug("task category classification skipped: %s", exc)
        return None


def _classify_domain(text: str) -> Optional[str]:
    if not text:
        return None
    try:
        from core.domain_attribution import resolve_domain

        value = resolve_domain(text)
        if not value:
            return None
        slug = str(value).strip().lower()
        return slug if _DOMAIN_SLUG.match(slug) else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("task domain classification skipped: %s", exc)
        return None


def build_task_profile(
    objective: Any,
    *,
    steps: Optional[Sequence[Any]] = None,
    task_type: Optional[str] = None,
    user_id: Optional[str] = None,
) -> TaskProfile:
    """Build the canonical profile from trusted server task material.

    Missing/unknown dimensions are represented as ``None``. Consumers must
    treat those as “cannot prove nonmatch” (see
    ``core.autonomy_policy.evaluate_never_autonomous``), never as a wildcard
    that bypasses a configured rule.
    """
    objective_text = _clean_text(objective)
    steps_text = _step_text(steps)
    combined = " ".join(part for part in (objective_text, steps_text) if part)
    difficulty = _classify_difficulty(combined, task_type)
    category = _classify_category(combined)
    domain = _classify_domain(combined)
    signals = {}
    if difficulty:
        signals["difficulty_source"] = "query_complexity"
    if category:
        signals["category_source"] = "task_domain"
    if domain:
        signals["domain_source"] = "domain_attribution"
    return TaskProfile(
        difficulty=difficulty,
        category=category,
        domain=domain,
        signals=signals,
        owner_user_id=str(user_id).strip() if user_id else None,
    )


def build_assignment_task_profile(assignment: Any) -> TaskProfile:
    """Profile a durable assignment/task plan (server-owned state)."""
    if not isinstance(assignment, Mapping):
        return build_task_profile("")
    provenance = assignment.get("provenance")
    owner = (
        provenance.get("user_id")
        if isinstance(provenance, Mapping) else None
    ) or assignment.get("employee_id")
    return build_task_profile(
        assignment.get("objective") or assignment.get("goal_text"),
        steps=assignment.get("steps") or [],
        user_id=owner,
    )


def build_workflow_task_profile(workflow: Any) -> TaskProfile:
    """Profile a workflow definition (server-owned state)."""
    if not isinstance(workflow, Mapping):
        return build_task_profile("")
    objective = " ".join(
        str(value) for value in (
            workflow.get("name"), workflow.get("description"),
            workflow.get("goal"), workflow.get("objective"),
        ) if value
    )
    return build_task_profile(
        objective,
        steps=workflow.get("steps") or [],
        user_id=workflow.get("created_by") or workflow.get("user_id"),
    )


_CURRENT_TASK_PROFILE: ContextVar[Optional[TaskProfile]] = ContextVar(
    "atom_current_task_profile", default=None)


def bind_task_profile(context: Any, profile: TaskProfile) -> Token:
    """Bind a trusted profile for the current execution and dispatch context.

    Returns the ContextVar token for ``reset_task_profile`` in a finally
    block. The dict key is an object (not serializable), so a request body or
    model-produced tool argument cannot forge it.

    A new task start also invalidates any clearance left over from a prior
    task on the same (reused) context dict: the clearance names the profile's
    per-task identity and the previous identity no longer matches.
    """
    if isinstance(context, dict):
        # Import lazily: autonomy_policy imports this module at call time.
        from core.autonomy_policy import NEVER_CLEARANCE_CONTEXT_KEY

        context.pop(NEVER_CLEARANCE_CONTEXT_KEY, None)
        context[TASK_PROFILE_CONTEXT_KEY] = profile
    try:
        from core.autonomy_policy import clear_current_never_autonomous_clearance

        clear_current_never_autonomous_clearance()
    except Exception:  # noqa: BLE001 — clearance invalidation is best effort
        pass
    return _CURRENT_TASK_PROFILE.set(profile)


def reset_task_profile(token: Optional[Token], context: Any = None) -> None:
    if context is not None and isinstance(context, dict):
        context.pop(TASK_PROFILE_CONTEXT_KEY, None)
        try:
            from core.autonomy_policy import NEVER_CLEARANCE_CONTEXT_KEY

            context.pop(NEVER_CLEARANCE_CONTEXT_KEY, None)
        except Exception:  # noqa: BLE001
            pass
    try:
        from core.autonomy_policy import clear_current_never_autonomous_clearance

        clear_current_never_autonomous_clearance()
    except Exception:  # noqa: BLE001
        pass
    if token is not None:
        try:
            _CURRENT_TASK_PROFILE.reset(token)
        except (ValueError, RuntimeError):
            # A token from another context cannot be reset here; dropping our
            # reference is still safe because no profile is granted.
            pass


def current_task_profile() -> Optional[TaskProfile]:
    value = _CURRENT_TASK_PROFILE.get()
    return value if is_trusted_task_profile(value) else None


def task_profile_from_context(context: Any) -> Optional[TaskProfile]:
    if not isinstance(context, Mapping):
        return None
    value = context.get(TASK_PROFILE_CONTEXT_KEY)
    return value if is_trusted_task_profile(value) else None


__all__ = [
    "CATEGORY_VALUES",
    "DIFFICULTY_VALUES",
    "DOMAIN_SUGGESTIONS",
    "TASK_PROFILE_CONTEXT_KEY",
    "TaskProfile",
    "bind_task_profile",
    "build_assignment_task_profile",
    "build_task_profile",
    "build_workflow_task_profile",
    "current_task_profile",
    "is_trusted_task_profile",
    "is_valid_domain_slug",
    "reset_task_profile",
    "task_profile_from_context",
]
