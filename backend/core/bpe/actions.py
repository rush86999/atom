"""BPE meta-actions registered in the shared action registry.

Exposes the four harness meta-actions — ``workspace.track``,
``workspace.commit``, ``workspace.recall``, ``workspace.note`` — through
``core.action_registry`` so both the agent MCP dispatch and the frontend RPC
route them like any other tool (plan Phase 1). Handlers are thin: state
lives in the per-scope :class:`~core.bpe.workspace.BPEWorkspace`.

Scope resolution (2026-11-08 current-principal repair): the namespace is
derived from *server authority*, never from caller-supplied arguments.

- RPC passes the authenticated ``User`` row + DB session. The row is re-read
  fresh, must be active, and its ``workspace_id`` (or an isolated
  ``personal:<user>`` namespace when the app is running the single-tenant
  Personal / NULL-workspace default) + the principal id form the scope.
  Two different users therefore never share a buffer, even in one workspace.
- Agent dispatchers (GenericAgent / AtomMetaAgent / MCP) bind the reserved
  :data:`PRINCIPAL_SCOPE_CONTEXT_KEY` with the authoritative agent workspace,
  agent id and session/run key. Caller body params are *not* a scope source;
  the dispatchers strip any caller-supplied copy before binding.
- A bare ``workspace_id`` in a trusted server context remains accepted for
  internal direct-action callers, but the anonymous shared ``default``
  namespace is refused (typed no-effect) rather than silently shared.

The previous implementation read ``context['workspace_id']`` /
``context['agent_id']`` / ``context['session_id']`` directly and defaulted
them to ``("default", "atom_main", "")``. RPC supplied none of those, so every
authenticated caller appended to the same buffer. Appends now also claim the
active principal row inside the write transaction (conditional no-op UPDATE)
to close the check-then-append window.

Maturity-gated visibility is enforced upstream by
``GenericAgent._custom_action_visible`` — these actions ship enabled for
INTERN+ agents; ``ATOM_BPE_WORKSPACE_ENABLED`` defaults ON (set false to)
shadow logging.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

from core.action_registry import register_action
from core.bpe.workspace import get_workspace

logger = logging.getLogger(__name__)

# Reserved context key bound by SERVER dispatchers only (GenericAgent,
# AtomMetaAgent, MCP). It is stripped from caller params before binding, so a
# model/client-supplied copy can never choose a namespace.
PRINCIPAL_SCOPE_CONTEXT_KEY = "_bpe_principal_scope"
PERSONAL_WORKSPACE_PREFIX = "personal:"

# Typed no-effect envelope (the mutation contract distinguishes a proven
# refusal from "may have applied").
_SCOPE_PRINCIPAL_MISSING = "scope_principal_missing"
_SCOPE_PRINCIPAL_INACTIVE = "scope_principal_inactive"
_SCOPE_PRINCIPAL_UNVERIFIED = "scope_principal_unverified"
_SCOPE_AUTHORITY_MISSING = "scope_authority_missing"
_SCOPE_AUTHORITY_CHANGED = "scope_authority_changed"
_SCOPE_WORKSPACE_UNAVAILABLE = "scope_workspace_unavailable"


def bpe_enabled() -> bool:
    """Flag gate (Switchyard convention: off → shadow-log only, prompt unchanged).

    Default ON (2026-08-29): the BPE workspace is a default platform feature.
    Resolution: explicit ATOM_BPE_WORKSPACE_ENABLED env var (kill-switch)
    wins, then a UI-persisted runtime-settings override, else ON.
    """
    raw = os.getenv("ATOM_BPE_WORKSPACE_ENABLED")
    if raw is not None:
        return raw.strip().lower() not in ("0", "false", "no", "off")
    try:
        from core.runtime_settings import resolve_setting

        res = resolve_setting("ATOM_BPE_WORKSPACE_ENABLED")
        if res.source == "db" and isinstance(res.value, bool):
            return res.value
    except Exception:
        pass
    return True


def _deny(code: str, message: str) -> Dict[str, Any]:
    """Typed, proven no-effect refusal (never a success wrapper)."""
    return {
        "success": False,
        "error": code,
        "message": message,
        "action_result": "not_applied",
        "effect_possible": False,
    }


def _user_id_from(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        raw = value.get("id")
    else:
        raw = getattr(value, "id", None)
    return str(raw) if raw else None


def _user_workspace_from(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        raw = value.get("workspace_id")
    else:
        raw = getattr(value, "workspace_id", None)
    return str(raw) if raw else None


def _is_db_session(value: Any) -> bool:
    """True when ``value`` is a usable DB session (never a caller string)."""
    return value is not None and hasattr(value, "query") and hasattr(value, "execute")


def _is_inactive_user(row: Any) -> bool:
    """Active-user check matching core.board_access (status + is_active)."""
    if row is None:
        return True
    status = getattr(row, "status", None)
    status = getattr(status, "value", status)
    if str(status or "").lower() != "active":
        return True
    return getattr(row, "is_active", True) is False


def _fresh_active_user(db: Any, user_id: str) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """Re-read the principal row so a stale token cannot authorize a write."""
    from core.models import User

    row = (
        db.query(User)
        .filter(User.id == str(user_id))
        .populate_existing()
        .first()
    )
    if row is None:
        return None, _deny(
            _SCOPE_PRINCIPAL_MISSING,
            "BPE workspace requires an existing authenticated principal.",
        )
    if _is_inactive_user(row):
        return None, _deny(
            _SCOPE_PRINCIPAL_INACTIVE,
            "BPE workspace requires the principal to be active.",
        )
    return row, None


def _canonical_user_workspace(row: Any, user_id: str) -> str:
    raw = getattr(row, "workspace_id", None)
    return str(raw) if raw else f"{PERSONAL_WORKSPACE_PREFIX}{user_id}"


def resolve_scope(context: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Resolve the canonical BPE namespace, or a typed no-effect denial.

    Returns ``(scope, None)`` on success and ``(None, denial)`` when the
    caller has no current, verifiable authority. Never falls back to the
    anonymous ``default`` namespace.
    """
    ctx = context or {}
    db = ctx.get("db") if _is_db_session(ctx.get("db")) else None
    presented_user = ctx.get("user")
    presented_id = _user_id_from(presented_user)
    context_user_id = str(ctx.get("user_id")) if ctx.get("user_id") else None
    # A context whose actor fields disagree cannot name one principal.
    if presented_id and context_user_id and presented_id != context_user_id:
        return None, _deny(
            _SCOPE_AUTHORITY_CHANGED,
            "Principal identity changed; refresh before writing.",
        )
    user_id = presented_id or context_user_id

    # 1) Authenticated principal (RPC / request-bound MCP).
    if user_id and db is not None:
        row, denial = _fresh_active_user(db, user_id)
        if denial:
            return None, denial
        authoritative_workspace = _canonical_user_workspace(row, user_id)
        presented_workspace = _user_workspace_from(presented_user)
        # A stale presented row may disagree with the current row; refuse
        # instead of silently moving the buffer or merging two authorities.
        if presented_workspace and presented_workspace != authoritative_workspace:
            return None, _deny(
                _SCOPE_AUTHORITY_CHANGED,
                "Principal workspace changed; refresh before writing.",
            )
        return {
            "workspace_id": authoritative_workspace,
            "agent_id": "atom_main",
            # Per-principal key: same user continues their own buffer, a
            # different user (including a NULL/Personal default principal)
            # never inherits it.
            "scope_key": f"user:{user_id}",
            "user_id": user_id,
            # The literal single-tenant ``default`` workspace has no row to
            # claim; the per-user key above is what isolates it.
            "workspace_claim": bool(getattr(row, "workspace_id", None))
            and str(getattr(row, "workspace_id", "")) != "default",
            "authority": "user",
        }, None

    # A user object without a DB session cannot prove *current* activity.
    if presented_user is not None and user_id and db is None:
        return None, _deny(
            _SCOPE_PRINCIPAL_UNVERIFIED,
            "BPE workspace requires a verifiable authenticated principal.",
        )

    # 2) Server-bound dispatch scope (GenericAgent / AtomMetaAgent / MCP).
    trusted = ctx.get(PRINCIPAL_SCOPE_CONTEXT_KEY)
    if isinstance(trusted, dict):
        workspace_id = str(trusted.get("workspace_id") or "").strip()
        scope_key = str(trusted.get("scope_key") or "").strip()
        scoped_user_id = str(trusted.get("user_id") or "").strip()
        verified_user = False
        if scoped_user_id and db is not None:
            row, denial = _fresh_active_user(db, scoped_user_id)
            if denial:
                return None, denial
            verified_user = True
            authoritative_workspace = _canonical_user_workspace(row, scoped_user_id)
            if (workspace_id and workspace_id != authoritative_workspace
                    and not (workspace_id == "default"
                             and authoritative_workspace.startswith(
                                 PERSONAL_WORKSPACE_PREFIX))):
                return None, _deny(
                    _SCOPE_AUTHORITY_CHANGED,
                    "Principal workspace changed; refresh before writing.",
                )
            workspace_id = authoritative_workspace
        # ``default`` is tolerated only for a server-bound agent scope with a
        # real session/run key: that is single-tenant Personal parity, not a
        # shared anonymous buffer.
        if workspace_id and (workspace_id != "default" or scope_key):
            scope = {
                "workspace_id": workspace_id,
                "agent_id": str(trusted.get("agent_id") or "atom_main"),
                "scope_key": scope_key,
                "authority": "user" if verified_user else "server",
            }
            if verified_user:
                scope["user_id"] = scoped_user_id
                scope["workspace_claim"] = (
                    bool(getattr(row, "workspace_id", None))
                    and str(getattr(row, "workspace_id", "")) != "default"
                )
                scope["scope_key"] = (
                    f"user:{scoped_user_id}:{scope_key}" if scope_key
                    else f"user:{scoped_user_id}"
                )
            return scope, None
        return None, _deny(
            _SCOPE_AUTHORITY_MISSING,
            "Server-bound BPE scope requires a workspace and session/run key.",
        )

    # 3) Legacy trusted server context (direct action-registry callers).
    workspace_id = str(ctx.get("workspace_id") or "").strip()
    if workspace_id and workspace_id != "default":
        return {
            "workspace_id": workspace_id,
            "agent_id": str(ctx.get("agent_id") or "atom_main"),
            "scope_key": str(ctx.get("session_id") or ctx.get("execution_id") or "").strip(),
            "authority": "context",
        }, None

    return None, _deny(
        _SCOPE_AUTHORITY_MISSING,
        "BPE workspace requires an authenticated principal or a "
        "server-bound workspace scope.",
    )


def bpe_scope_from_context(context: Dict[str, Any]) -> Tuple[str, str, str]:
    """Return ``(workspace_id, agent_id, scope_key)`` for prompt/close-out.

    Agent code uses this same helper for the rendered Prompt block, the
    episode reset and the close-out consolidation, so all three always
    address the namespace the action handlers use.
    """
    scope, _denial = resolve_scope(context)
    if scope is not None:
        return scope["workspace_id"], scope["agent_id"], scope["scope_key"]
    trusted = (context or {}).get(PRINCIPAL_SCOPE_CONTEXT_KEY)
    if isinstance(trusted, dict):
        return (
            str(trusted.get("workspace_id") or "default"),
            str(trusted.get("agent_id") or "atom_main"),
            str(trusted.get("scope_key") or ""),
        )
    return "default", "atom_main", ""


def bind_trusted_scope(context: Dict[str, Any], *, workspace_id: Any,
                       agent_id: Any, scope_key: Any,
                       user_id: Any = None) -> Optional[Dict[str, Any]]:
    """Bind the server-authoritative BPE scope onto a dispatch context.

    Dispatchers call this AFTER reading any caller params: any caller-supplied
    copy of the reserved key is dropped first, so request/browser params can
    never grant a namespace.
    """
    if context is None:
        return None
    context.pop(PRINCIPAL_SCOPE_CONTEXT_KEY, None)
    context[PRINCIPAL_SCOPE_CONTEXT_KEY] = {
        "workspace_id": str(workspace_id or ""),
        "agent_id": str(agent_id or ""),
        "scope_key": str(scope_key or ""),
        **({"user_id": str(user_id)} if user_id else {}),
    }
    return context


def _claim_authority(context: Dict[str, Any], scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Claim the active principal (and workspace) before an append.

    A conditional no-op UPDATE executes inside the same transaction as the
    buffer append. Zero rows means the principal was deactivated/changed (or
    the workspace vanished) after the earlier read, so the append is refused
    before any effect. Follow-up reads only select the typed error; they never
    authorize the write.
    """
    if scope.get("authority") != "user":
        return None
    raw_db = (context or {}).get("db")
    db = raw_db if _is_db_session(raw_db) else None
    user_id = scope.get("user_id")
    if db is None or not user_id:
        return None

    try:
        from sqlalchemy import update

        from core.models import User, UserStatus, Workspace

        claimed = db.execute(
            update(User)
            .where(
                User.id == str(user_id),
                User.status == UserStatus.ACTIVE.value,
                User.is_active.is_(True),
            )
            .values(updated_at=User.updated_at)
        )
        if claimed.rowcount != 1:
            row = (
                db.query(User)
                .filter(User.id == str(user_id))
                .populate_existing()
                .first()
            )
            if row is None:
                return _deny(
                    _SCOPE_PRINCIPAL_MISSING,
                    "Principal disappeared before the append; nothing was written.",
                )
            return _deny(
                _SCOPE_PRINCIPAL_INACTIVE,
                "Principal is no longer active; nothing was written.",
            )

        row = (
            db.query(User)
            .filter(User.id == str(user_id))
            .populate_existing()
            .first()
        )
        if row is None:
            return _deny(
                _SCOPE_PRINCIPAL_MISSING,
                "Principal disappeared before the append; nothing was written.",
            )
        if _canonical_user_workspace(row, str(user_id)) != scope["workspace_id"]:
            return _deny(
                _SCOPE_AUTHORITY_CHANGED,
                "Principal workspace changed before the append; nothing was written.",
            )

        if scope.get("workspace_claim"):
            claimed_workspace = db.execute(
                update(Workspace)
                .where(Workspace.id == scope["workspace_id"])
                .values(updated_at=Workspace.updated_at)
            )
            if claimed_workspace.rowcount != 1:
                return _deny(
                    _SCOPE_WORKSPACE_UNAVAILABLE,
                    "Workspace is no longer available; nothing was written.",
                )
    except Exception as e:  # noqa: BLE001 — unverifiable authority fails closed
        logger.warning("bpe authority claim failed closed: %s", e)
        return _deny(
            _SCOPE_AUTHORITY_MISSING,
            "Could not verify BPE workspace authority; nothing was written.",
        )
    return None


def _resolve_workspace(context: Dict[str, Any], *, claim: bool = False):
    scope, denial = resolve_scope(context)
    if denial:
        return None, None, denial
    if claim:
        denial = _claim_authority(context, scope)
        if denial:
            return None, scope, denial
    ws = get_workspace(scope["workspace_id"], scope["agent_id"], scope["scope_key"])
    # Late-bind the belief adapter (avoid import cycles at module load).
    if ws.adapter is None:
        try:
            from core.bpe.chat_adapter import ChatBeliefAdapter

            ws.adapter = ChatBeliefAdapter()
        except Exception:
            from core.bpe.adapter import NullAdapter

            ws.adapter = NullAdapter()
    return ws, scope, None


_COMMON_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
}


@register_action(
    "workspace.track",
    description="Read the workspace Belief state — task-relevant facts about "
                "entities, their states and relations. Pass a topic (entity "
                "name) or 'world' for a compact global summary. Cheap to "
                "consult; still consumes a step.",
    parameters_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Entity/topic to inspect, or 'world'"},
        },
        "required": [],
    },
    effects=[{"effect": "read"}],
)
async def _bpe_track(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    ws, scope, denial = _resolve_workspace(context)
    if denial:
        return denial
    # The belief adapter reads stores by workspace; hand it the canonical
    # scope so a peer's workspace can never answer a track/recall.
    tracked_context = dict(context or {})
    tracked_context["workspace_id"] = scope["workspace_id"]
    tracked_context["agent_id"] = scope["agent_id"]
    if scope.get("user_id"):
        tracked_context["user_id"] = scope["user_id"]
    return await ws.apply("track", args.get("topic") or "world", tracked_context)


@register_action(
    "workspace.commit",
    description="Commit execution state to workspace Progress: add a subgoal "
                "(no status) or update an existing subgoal's status "
                "(pending|in_progress|done|blocked). Keeps the plan external "
                "and bounded (max 8 subgoals).",
    parameters_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Subgoal title (or prefix to match)"},
            "status": {"type": "string", "description": "pending|in_progress|done|blocked (omit to add new)"},
        },
        "required": ["title"],
    },
    effects=[{"effect": "update", "scope": "local"}],
)
async def _bpe_commit(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    ws, _scope, denial = _resolve_workspace(context, claim=True)
    if denial:
        return denial
    payload = {"title": args.get("title") or "", "status": args.get("status")}
    return await ws.apply("commit", payload)


@register_action(
    "workspace.recall",
    description="Recall reusable Experience — past skills, procedures, common "
                "mistakes, and search priors matching a query. Query modes: "
                "how-to procedures, mistakes to avoid, entity facts.",
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to recall (procedures / mistakes / facts)"},
        },
        "required": ["query"],
    },
    effects=[{"effect": "read"}],
)
async def _bpe_recall(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    ws, _scope, denial = _resolve_workspace(context)
    if denial:
        return denial
    return await ws.apply("recall", args.get("query") or "")


@register_action(
    "workspace.note",
    description="Buffer an insight for later consolidation into long-term "
                "Experience (does NOT answer anything now). Use to record a "
                "lesson, failure mode, or discovered fact worth remembering.",
    parameters_schema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The insight to note"},
        },
        "required": ["content"],
    },
    effects=[{"effect": "create", "scope": "local"}],
)
async def _bpe_note(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    ws, _scope, denial = _resolve_workspace(context, claim=True)
    if denial:
        return denial
    return await ws.apply("note", args.get("content") or "")
