"""
LLM Service module.

Provides a unified interface for LLM interactions across the platform,
wrapping the advanced BYOKHandler infrastructure.
"""

import json
import logging
import os
import asyncio
import threading
from typing import Optional, Dict, Any, List, Tuple, Union, Type, AsyncGenerator
from enum import Enum

from pydantic import BaseModel
from core.llm.byok_handler import BYOKHandler, QueryComplexity, AwaitableResult
from core.llm.cognitive_tier_system import CognitiveTier, CognitiveClassifier
from core.llm.context.token_counter import TokenCounter, ContextValidator
from core.llm_usage_tracker import llm_usage_tracker
from core.continuous_learning_service import ContinuousLearningService

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    GROQ = "groq"
    MINIMAX = "minimax"
    MISTRAL = "mistral"
    QWEN = "qwen"
    COHERE = "cohere"
    XIAOMI = "xiaomi"
    OLLAMA = "ollama"


class LLMModel(str, Enum):
    """Common LLM models"""
    # OpenAI
    GPT4 = "gpt-4"
    GPT4_TURBO = "gpt-4-turbo"
    GPT35_TURBO = "gpt-3.5-turbo"
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    GPT_5_3 = "gpt-5.3"

    # Anthropic
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet"

    # DeepSeek
    DEEPSEEK_V3 = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"

    # Gemini
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_3_5_FLASH = "gemini-3.5-flash"

    # MiniMax
    MINIMAX_M3 = "MiniMax-M3"
    MINIMAX_M3_HIGHSPEED = "MiniMax-M3-highspeed"
    MINIMAX_M27 = "MiniMax-M2.7"
    MINIMAX_M27_HIGHSPEED = "MiniMax-M2.7-highspeed"
    MINIMAX_2_5 = "minimax-m2.5"  # legacy

    # Xiaomi
    XIAOMI_MIMO_2_5_PRO = "xiaomi/mimo-v2.5-pro"


class LLMSentiment(BaseModel):
    """Structured sentiment analysis output"""
    score: float  # -1.0 to 1.0
    label: str    # "positive", "neutral", "negative"
    confidence: float


class LLMScopeUnresolvedError(RuntimeError):
    """An explicitly named tenant could not be resolved to its OWN
    unique workspace. Dispatch refuses — it never substitutes another
    scope's providers, keys or endpoints (owner correction 2026-10-12).
    ``reason`` distinguishes unknown tenant, ambiguous multi-workspace
    binding and lookup failure."""

    def __init__(self, tenant_id: str, reason: str):
        self.tenant_id = tenant_id
        self.reason = reason
        super().__init__(
            f"workspace resolution for tenant {tenant_id!r} is "
            f"unresolved ({reason}); dispatch refused rather than "
            f"substituting another scope")


class LLMTopics(BaseModel):
    """Structured topic extraction output"""
    topics: List[str]
    confidence: float


class LLMService:
    """
    LLM Service for managing LLM interactions across the platform.
    Provides unified interface for different LLM providers, wrapping BYOKHandler.

    Harmonized with SaaS version for feature parity.
    """

    # SCOPE RESOLUTION TRI-STATE (owner correction 2026-10-12): a
    # tenant-only scope resolves to ITS OWN workspace — uniquely, or not
    # at all. The sentinel means "explicitly named, not resolvable"
    # (unknown tenant, ambiguous multi-workspace tenant, or lookup
    # failure). An unresolved scope is NEVER substituted with another
    # workspace (least of all the default's): dispatch refuses with an
    # explicit unresolved-scope result and zero provider calls.
    _UNRESOLVED = object()

    def __init__(self, db=None, workspace_id: Optional[str] = None, tenant_id: Optional[str] = None):
        """
        Args:
            db: Optional SQLAlchemy session.
            workspace_id: Primary identifier for workspace-level grouping.
            tenant_id: Identifier for the tenant (SaaS convention).
        """
        self._db = db
        self._tenant_id = tenant_id or "default"
        self._tenant_workspace_cache: Dict[str, str] = {}
        # WORKSPACE FROM THE AUTHORIZED CONTEXT (J2 provider-scope work
        # order): an explicit workspace wins. A service constructed with
        # only a tenant (the chat orchestrator's shape) resolves the
        # workspace THAT tenant owns through the product's own
        # tenant→workspace link — a tenant id is never itself a
        # workspace id. Resolution must be UNIQUE; an unknown, ambiguous
        # or failed resolution leaves the service UNRESOLVED — never
        # substituted with "default" or any other scope (owner
        # correction 2026-10-12: substituting would select another
        # scope's local-provider configuration).
        self._workspace_id = workspace_id or "default"
        self._scope_unresolved_reason: Optional[str] = None
        # HOW the service obtained its workspace: only a scope obtained
        # through TENANT RESOLUTION is subject to per-dispatch
        # revalidation. An explicit workspace argument is authenticated
        # constructor context — never treated as a stale cacheable
        # resolution (verifier probe P3 follow-up: validating explicit
        # scopes broke injected handlers and re-asked the tenant question
        # the caller already answered).
        self._workspace_from_tenant_resolution = False
        if workspace_id is None and self._tenant_id != "default":
            resolved = self._workspace_for_tenant(self._tenant_id)
            if resolved is None or resolved is LLMService._UNRESOLVED:
                self._scope_unresolved_reason = (
                    f"tenant {self._tenant_id!r} has no unique workspace "
                    "binding (missing, ambiguous, or the lookup failed)")
                self._workspace_id = None
            else:
                self._workspace_id = resolved
                self._workspace_from_tenant_resolution = True
        self._handler: Optional[BYOKHandler] = None

        # In single-tenant open source, we mostly care about workspace_id.
        # But we preserve tenant_id for compatibility. An unresolved
        # scope builds NO handler: zero provider construction, zero
        # endpoint reachability.
        if self._scope_unresolved_reason is None:
            self._handler = BYOKHandler(workspace_id=self._workspace_id, tenant_id=self._tenant_id, db_session=db)
        # Handlers for OTHER (workspace, tenant) scopes, created on
        # demand and keyed by the FULL identity pair. The shared
        # handler is never mutated between requests; handler reuse
        # requires both identifiers to match.
        self._scoped_handlers: Dict[Tuple[str, str], BYOKHandler] = {}
        # SCOPE LOCK (Agent 3 finding 1 on d6fbcd846): adoption swaps the
        # service's workspace AND shared handler; a concurrent reader
        # must never pair the new workspace id with the old handler (it
        # handed the OLD endpoint's client to post-change dispatches).
        # Selection and adoption are serialized; dispatch itself runs
        # outside the lock, so an in-flight request keeps the handler it
        # selected (retention). Reentrant: adoption runs inside a
        # selection that already holds the lock.
        self._scope_lock = threading.RLock()
        self.continuous_learning = ContinuousLearningService(db) if db else None
        self._token_counter = TokenCounter()
        self._context_validator = ContextValidator()
        self._cognitive_classifier = CognitiveClassifier()

    @property
    def handler(self) -> BYOKHandler:
        """Alias for _handler (parity with some callers). Raises the
        explicit unresolved-scope error rather than letting a None
        handler AttributeError deep inside a dispatch."""
        # Route through the policy-refresh path. A policy change between
        # requests must rebuild the handler; callers that hold the previous
        # handler keep their in-flight snapshot.
        handler = self._get_handler()
        if handler is None and self._scope_unresolved_reason:
            raise LLMScopeUnresolvedError(
                self._tenant_id, self._scope_unresolved_reason)
        return handler

    @handler.setter
    def handler(self, value: BYOKHandler) -> None:
        """Allow callers/tests to inject a mock handler."""
        self._handler = value

    @property
    def workspace_id(self) -> str:
        """Return the workspace identifier."""
        return self._workspace_id

    @property
    def tenant_id(self) -> str:
        """Return the tenant identifier."""
        return self._tenant_id

    def scope_is_unresolved(self) -> bool:
        """True when an explicitly named tenant could not be resolved to
        its own unique workspace — dispatch must refuse."""
        return self._scope_unresolved_reason is not None

    def _unresolved_scope_reason_for(self, tenant_id: Optional[str]) -> str:
        if tenant_id and tenant_id != "default" and \
                tenant_id != self._tenant_id:
            return (f"tenant {tenant_id!r} has no unique workspace "
                    "binding (missing, ambiguous, or the lookup failed)")
        return (self._scope_unresolved_reason
                or f"tenant {self._tenant_id!r} has no unique workspace "
                "binding")

    def _unresolved_scope_message(self, tenant_id: Optional[str]) -> str:
        """The explicit unresolved-scope text result for the plain
        generate() contract — honest about what did NOT run."""
        reason = self._unresolved_scope_reason_for(tenant_id)
        logger.warning("LLM dispatch refused: %s", reason)
        return (f"No LLM provider was consulted: workspace resolution "
                f"for this tenant is unresolved ({reason}). No provider "
                f"was called.")

    def _unresolved_scope_result(self, tenant_id: Optional[str],
                                 model: str) -> Dict[str, Any]:
        """The explicit unresolved-scope result for the
        generate_completion contract: success=False, no provider/model
        claim, and the resolution reason on the record."""
        reason = self._unresolved_scope_reason_for(tenant_id)
        logger.warning("LLM completion refused: %s", reason)
        return {
            "success": False,
            "content": (
                f"No LLM provider was consulted: workspace resolution "
                f"for this tenant is unresolved ({reason}). No provider "
                f"was called."),
            "text": (
                f"No LLM provider was consulted: workspace resolution "
                f"for this tenant is unresolved ({reason}). No provider "
                f"was called."),
            "model": model,
            "provider": None,
            "unresolved_scope": {
                "tenant_id": tenant_id or self._tenant_id,
                "reason": reason,
            },
            "usage": {"prompt_tokens": 0, "completion_tokens": 0,
                      "total_tokens": 0},
        }

    def _workspace_for_tenant(self, tenant_id: str):
        """The workspace a tenant owns, through the product's own
        tenant→workspace link.

        Returns the workspace id ONLY on a unique resolution. The
        ``_UNRESOLVED`` sentinel covers every other case: the tenant is
        unknown, binds MULTIPLE workspaces (ambiguous — registration
        creating one workspace does not mean a tenant always has
        exactly one), or the lookup fails. ``None`` means no
        tenant-scoped resolution applies (default/deliberate scope).

        Positive resolutions are CACHED but never trusted blind (verifier
        finding P3 on 316317f3b): every cache hit is validated against
        the tenant's CURRENT binding set — a binding that was revoked,
        or changed to a different workspace, re-resolves by the normal
        rules instead of dispatching to a stale scope. The cost is one
        indexed query per tenant-only dispatch; scope correctness is
        worth it. A lookup failure during validation refuses (zero
        calls) rather than dispatching on an unvalidated scope.
        """
        if not tenant_id or tenant_id == "default":
            return None
        try:
            from core.models import Workspace

            if self._db is not None:
                rows = (self._db.query(Workspace)
                        .filter(Workspace.tenant_id == tenant_id)
                        .all())
            else:
                from core.database import get_db_session

                with get_db_session() as db:
                    rows = (db.query(Workspace)
                            .filter(Workspace.tenant_id == tenant_id)
                            .all())
            ids = [row.id for row in rows]
        except Exception as exc:  # noqa: BLE001 — scope resolution, not routing
            logger.debug("workspace resolution for tenant %s failed: %s",
                         tenant_id, exc)
            self._tenant_workspace_cache.pop(tenant_id, None)
            return LLMService._UNRESOLVED
        if len(ids) == 1:
            self._tenant_workspace_cache[tenant_id] = ids[0]
            return ids[0]
        # zero (binding revoked / unknown tenant) or many (ambiguous) —
        # unresolved. The stale positive entry is dropped so a repaired
        # binding resolves on the next call.
        self._tenant_workspace_cache.pop(tenant_id, None)
        return LLMService._UNRESOLVED

    def _adopt_workspace(self, workspace_id: str) -> None:
        """Adopt a (possibly new) workspace for the service's own
        tenant: the shared handler is REBUILT for the adopted scope —
        never reused across a binding change. The adopted scope IS a
        tenant resolution, so it stays subject to revalidation."""
        with self._scope_lock:
            self._workspace_id = workspace_id
            self._scope_unresolved_reason = None
            self._workspace_from_tenant_resolution = True
            self._handler = BYOKHandler(
                workspace_id=self._workspace_id,
                tenant_id=self._tenant_id, db_session=self._db)
        logger.info(
            "workspace binding for tenant %s adopted -> %s; the handler "
            "was rebuilt for the adopted scope", self._tenant_id,
            workspace_id)

    def _get_handler(self, workspace_id: Optional[str] = None, tenant_id: Optional[str] = None) -> Optional[BYOKHandler]:
        """Handler for one (workspace, tenant) scope — or ``None`` when
        the scope is explicitly named but UNRESOLVED. Selection and
        scope adoption are serialized under the scope lock (Agent 3
        finding 1): a concurrent reader can never pair the adopted
        workspace with the previous handler. Dispatch itself runs
        outside this lock on the returned handler, so an in-flight
        request retains the handler it selected.
        """
        with self._scope_lock:
            return self._get_handler_locked(
                workspace_id=workspace_id, tenant_id=tenant_id)

    def _get_handler_locked(self, workspace_id: Optional[str] = None, tenant_id: Optional[str] = None) -> Optional[BYOKHandler]:
        """Locking contract: called with ``_scope_lock`` held.

        Tenant and workspace remain SEPARATE identifiers: an explicit
        tenant never becomes a workspace. A tenant-only caller (the
        chat path) is resolved to the workspace that tenant owns —
        uniquely, validated against the CURRENT binding set, or not at
        all: an unresolved scope is never substituted with this
        service's workspace or the default, and a binding that was
        revoked or changed after construction never serves through a
        stale handler. Reuse of the shared handler requires BOTH
        identifiers to match the service's own scope; every other pair
        gets its own handler, cached — a shared handler is never
        mutated between requests.
        """
        if workspace_id is None and tenant_id is not None and \
                tenant_id != self._tenant_id:
            # A DIFFERENT tenant's authorized context: resolve its own
            # workspace — uniquely and validated, or refuse.
            resolved = self._workspace_for_tenant(tenant_id)
            if resolved is None or resolved is LLMService._UNRESOLVED:
                return None
            target_ws = resolved
        elif workspace_id is None and (
                self._workspace_from_tenant_resolution or
                self._scope_unresolved_reason):
            # The service's OWN tenant, tenant-only call (or no scope
            # kwargs at all), on a scope that came from TENANT
            # RESOLUTION — or that is STILL unresolved from a failed
            # construction (whose retry must never be permanently
            # stuck): the VALIDATED resolution decides. A binding
            # revoked since construction refuses; a binding CHANGED
            # since construction adopts the new workspace and REBUILDS
            # the shared handler. Explicit-workspace services skip this
            # (their scope is constructor context, not a cached
            # resolution).
            resolved = self._workspace_for_tenant(self._tenant_id)
            if resolved is None or resolved is LLMService._UNRESOLVED:
                if self._handler is not None or \
                        not self._scope_unresolved_reason:
                    self._scope_unresolved_reason = (
                        f"tenant {self._tenant_id!r} currently has no "
                        "unique workspace binding (revoked, ambiguous, "
                        "or the lookup failed)")
                    self._handler = None
                return None
            if resolved != self._workspace_id or self._handler is None:
                self._adopt_workspace(resolved)
            target_ws = self._workspace_id
        else:
            target_ws = workspace_id or self._workspace_id
            if target_ws is None:
                # The service itself is scope-unresolved (constructor
                # tenant failed) and the caller named no explicit
                # workspace: refuse — zero provider calls.
                return None
        target_tenant = tenant_id or self._tenant_id

        from core.llm.provider_policy import ProviderPolicy

        def _is_real_handler(handler) -> bool:
            try:
                from unittest.mock import Mock as _Mock

                if isinstance(handler, _Mock):
                    return False
                return isinstance(handler, BYOKHandler)
            except TypeError:
                # Tests frequently replace BYOKHandler with a MagicMock.
                return False

        def _policy_key(handler) -> tuple:
            policy = getattr(handler, "provider_policy", None)
            if not isinstance(policy, ProviderPolicy):
                return ()
            return (policy.source, policy.revision, policy.mode,
                    policy.error, tuple(sorted(policy.allowed_providers)))

        def _fresh_policy_key() -> tuple:
            try:
                from core.llm.provider_policy import resolve_provider_policy

                fresh = resolve_provider_policy(
                    workspace_id=target_ws, tenant_id=target_tenant)
                return (fresh.source, fresh.revision, fresh.mode,
                        fresh.error, tuple(sorted(fresh.allowed_providers)))
            except Exception as exc:  # noqa: BLE001 — fail closed
                return ("invalid", "invalid", "invalid", str(exc), ())

        def _credentials_changed(handler) -> bool:
            checker = getattr(handler, "credentials_changed", None)
            if not callable(checker):
                return False
            try:
                return bool(checker())
            except Exception:  # noqa: BLE001 — refresh must not break dispatch
                return False

        if self._handler is not None and \
                target_ws == self._workspace_id and \
                target_tenant == self._tenant_id:
            # Test/mocked handlers keep their established replacement
            # semantics; policy/credential refresh applies to real BYOK
            # handlers.
            if not _is_real_handler(self._handler):
                return self._handler
            policy_same = _policy_key(self._handler) == _fresh_policy_key()
            credentials_same = not _credentials_changed(self._handler)
            # Policy and credential changes apply to NEW requests. Rebuild
            # rather than mutating the shared handler, so an in-flight turn
            # keeps the snapshot it was admitted under.
            if policy_same and credentials_same:
                return self._handler
            if not policy_same:
                logger.info(
                    "provider policy changed; rebuilding LLM handler for "
                    "workspace=%s tenant=%s", target_ws, target_tenant)
            else:
                logger.info(
                    "BYOK credential store changed; rebuilding LLM handler "
                    "for workspace=%s tenant=%s", target_ws, target_tenant)
            self._handler = BYOKHandler(
                workspace_id=target_ws, tenant_id=target_tenant,
                db_session=self._db)
            return self._handler

        key = (target_ws, target_tenant)
        handler = self._scoped_handlers.get(key)
        if handler is not None and not _is_real_handler(handler):
            return handler
        policy_changed = (
            handler is not None
            and _policy_key(handler) != _fresh_policy_key())
        credentials_changed = (
            handler is not None and _credentials_changed(handler))
        if handler is None or policy_changed or credentials_changed:
            if handler is not None:
                logger.info(
                    "BYOK credential/policy changed; rebuilding scoped LLM "
                    "handler for workspace=%s tenant=%s",
                    target_ws, target_tenant)
            handler = BYOKHandler(
                workspace_id=target_ws, tenant_id=target_tenant,
                db_session=self._db)
            self._scoped_handlers[key] = handler
        return handler

    def get_provider(self, model: str) -> LLMProvider:
        """Get the provider for a given model."""
        model_l = model.lower()
        # Ollama check first: explicit "ollama/" prefix or canonical local model
        # tags (llama3, mistral:7b, mixtral, etc.) that are served by Ollama.
        if model_l.startswith("ollama/") or model_l in {
            "llama3", "llama3:8b", "llama3:70b",
            "mistral:7b", "mixtral:8x7b",
            "phi3", "gemma:7b", "codellama",
        }:
            return LLMProvider.OLLAMA
        if "gpt" in model_l:
            return LLMProvider.OPENAI
        elif "claude" in model_l:
            return LLMProvider.ANTHROPIC
        elif "deepseek" in model_l:
            return LLMProvider.DEEPSEEK
        elif "gemini" in model_l:
            return LLMProvider.GEMINI
        elif "minimax" in model_l:
            return LLMProvider.MINIMAX
        elif "mistral" in model_l:
            return LLMProvider.MISTRAL
        elif "qwen" in model_l:
            return LLMProvider.QWEN
        elif "xiaomi" in model_l or "mimo" in model_l:
            return LLMProvider.XIAOMI
        elif "command" in model_l:
            return LLMProvider.COHERE
        else:
            return LLMProvider.OPENAI  # Default

    def _resolve_governance_model(self, tenant_id: str, model: str, **kwargs) -> str:
        """
        Interrogates tenant governance state to determine if model de-escalation is required.
        Implements 'Frugal Mode' for budget preservation.
        """
        # 1. Check for bypass flags (Security/System Critical)
        if kwargs.get("is_critical_security") or kwargs.get("is_system_repair"):
            return model

        # 2. Check tenant status
        if not self._db:
            return model

        from core.models import Workspace

        workspace = self._db.query(Workspace).filter(Workspace.id == tenant_id).first()
        if not workspace:
            return model

        # 3. Check for Frugal Mode in metadata
        meta = workspace.metadata_json or {}
        if not meta.get("frugal_mode"):
            return model

        # 4. Perform mapping
        mapping = {
            "gpt-4o": "gpt-4o-mini",
            "gpt-4": "gpt-4o-mini",
            "gpt-4-turbo": "gpt-4o-mini",
            "claude-3-5-sonnet": "claude-3-haiku-20240307",
            "claude-3-opus-20240229": "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229": "claude-3-haiku-20240307",
            "gemini-1.5-pro": "gemini-1.5-flash",
            "deepseek-reasoner": "deepseek-chat",
        }

        resolved = mapping.get(model, model)
        if resolved != model:
            logger.info(
                f"❄️ FRUGAL MODE ACTIVE: De-escalating {model} -> {resolved} for workspace {tenant_id}"
            )

        return resolved

    async def generate(
        self,
        prompt: str,
        system_instruction: str = "You are a helpful assistant.",
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Simple text generation interface."""
        # Personalization
        agent_id = kwargs.get("agent_id")
        user_id = kwargs.get("user_id")
        # Tenant and workspace stay separate: the handler is selected by
        # BOTH identifiers (a tenant-only caller resolves the tenant's
        # own workspace inside _get_handler — the tenant id never
        # becomes a workspace id). None = unresolved scope: refuse with
        # an explicit result, zero provider calls.
        handler = self._get_handler(workspace_id=workspace_id,
                                    tenant_id=tenant_id)
        if handler is None:
            return self._unresolved_scope_message(tenant_id)
        # Governance reads workspace metadata — use the workspace the
        # handler actually resolved to, not the raw argument. getattr:
        # an injected handler stand-in may not carry the attribute.
        target_ws = (getattr(handler, "workspace_id", None)
                     or workspace_id or self._workspace_id)

        # Apply Governance De-escalation
        model = self._resolve_governance_model(target_ws, model, **kwargs)

        if agent_id and self.continuous_learning:
            params = self.continuous_learning.get_personalized_parameters(
                tenant_id=target_ws,
                agent_id=agent_id,
                user_id=user_id
            )
            # Personalization applies only when the caller did not pass an
            # explicit temperature. "temperature" never reaches kwargs here —
            # the named parameter consumes it — so a caller-supplied value is
            # detected by differing from the 0.7 default.
            if "temperature" in params and temperature == 0.7:
                temperature = params["temperature"]

        # turn_index is passed positionally below; pop it from kwargs to avoid
        # a duplicate-keyword TypeError when callers pass it explicitly.
        turn_index = kwargs.pop("turn_index", 0)

        return await handler.generate_response(
            prompt=prompt,
            system_instruction=system_instruction,
            model_type=model,
            temperature=temperature,
            turn_index=turn_index,
            **kwargs
        )

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate completion with OpenAI-style messages.
        Maps messages to prompt/system for BYOKHandler.

        Multimodal content (OpenAI-style content-part lists with "image_url"
        blocks) is normalized here: text parts stay in the message, the last
        embedded image is lifted into the handler's `image_payload` param so
        vision-based routing sees it. `max_tokens` (when explicitly given)
        is forwarded to the provider request; None keeps the handler default
        (ATOM_COMPLETION_MAX_TOKENS).
        """
        # Tenant and workspace stay separate: the handler is selected by
        # BOTH identifiers (see generate). None = unresolved scope: an
        # explicit result, and NO handler is built — zero provider calls.
        handler = self._get_handler(workspace_id=workspace_id,
                                    tenant_id=tenant_id)
        if handler is None:
            return self._unresolved_scope_result(tenant_id, model)
        target_ws = (getattr(handler, "workspace_id", None)
                     or workspace_id or self._workspace_id)

        # Apply Governance De-escalation
        model = self._resolve_governance_model(target_ws, model, **kwargs)

        # Multimodal normalization: callers may embed image content-parts
        # inside message content lists. The routing layer keys vision
        # routing off the `image_payload` param — embedded parts were
        # invisible to it (a vision-blind model could win the turn and then
        # 400 or hallucinate), and the prompt-extraction loop below treated
        # a content LIST as the prompt string, corrupting the complexity
        # heuristic (len(list)/4 tokens). Pull the parts apart once, here:
        # every downstream consumer (vision filtering, request assembly)
        # then sees a uniform contract. The LAST image wins — for
        # screenshot loops that is the most recent observation.
        normalized_messages: List[Dict[str, Any]] = []
        extracted_image: Optional[str] = None
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                normalized_messages.append(msg)
                continue
            text_parts: List[str] = []
            for part in content:
                if not isinstance(part, dict):
                    text_parts.append(str(part))
                    continue
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    url = (part.get("image_url") or {}).get("url", "") or ""
                    if url.startswith("data:"):
                        # Strip the "data:<mime>;base64," prefix — the
                        # handler re-wraps raw base64 itself.
                        extracted_image = url.split(",", 1)[-1]
                    elif url:
                        extracted_image = url
            new_msg = dict(msg)
            new_msg["content"] = "\n".join(p for p in text_parts if p)
            normalized_messages.append(new_msg)
        if extracted_image and "image_payload" not in kwargs:
            kwargs["image_payload"] = extracted_image
        messages = normalized_messages

        # Extract prompt and system from messages
        prompt = ""
        system_instruction = "You are a helpful assistant."

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role == "user":
                prompt = content  # Use the last user message as prompt for now

        # Call underlying handler
        # turn_index is passed positionally below; pop it from kwargs to avoid
        # a duplicate-keyword TypeError when callers pass it explicitly.
        turn_index = kwargs.pop("turn_index", 0)
        # max_tokens: previously swallowed here (signature default 1000) and
        # NEVER forwarded — every caller silently got the handler-wide
        # ATOM_COMPLETION_MAX_TOKENS instead of the value it asked for.
        # Forward only when the caller set it explicitly, so the old default
        # keeps today's behavior (handler default) instead of clamping every
        # request down to 1000.
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        response_text = await handler.generate_response(
            prompt=prompt,
            system_instruction=system_instruction,
            model_type=model,
            temperature=temperature,
            turn_index=turn_index,
            # MEASURED input size, when the caller measured it. Routing's
            # window filter otherwise uses char/4, which understates
            # number/formula-dense prompts badly enough to admit a model that
            # cannot hold the prompt (closure item 4).
            estimated_tokens=kwargs.pop("estimated_tokens", None),
            # Full conversation through to the model: `prompt` alone only
            # feeds routing (complexity/last-user-text). Previously this call
            # flattened messages to (prompt, last-system) and the BYOK handler
            # never saw the transcript — multi-turn recall was impossible.
            messages=messages,
            **kwargs
        )

        # Approximate token usage
        input_tokens = self.estimate_tokens(prompt + system_instruction, model)
        output_tokens = self.estimate_tokens(response_text, model)

        # Surface the concrete model/provider BPC actually selected (not the
        # "auto" input). BYOKHandler stashes these before returning; fall back
        # to the input model if the stash is empty (defensive).
        used_model = getattr(handler, "_last_used_model", None) or model
        used_provider = getattr(handler, "_last_used_provider", None)
        if used_provider is None:
            used_provider = self.get_provider(used_model).value

        return {
            "success": True,
            "content": response_text,
            "text": response_text, # Parity with some saas callers
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            },
            "model": used_model,
            "provider": used_provider,
            # Identity of this generation's outcome row (set by the handler
            # when it recorded one). Callers that judge the ASSEMBLED reply
            # afterwards — the figure-grounding and verification guards — pass
            # it back to record_fabrication_signal so the corrective verdict
            # annotates THIS generation rather than appearing as a second one.
            "routing_result_id": getattr(
                handler, "_last_feedback_decision_id", None),
            # The model's chain-of-thought for this call, when the provider
            # returned one (reasoning_content/reasoning/thinking). None for
            # models that don't emit it — callers treat it as optional.
            "reasoning": getattr(handler, "_last_reasoning", None),
        }

    async def generate_structured_response(
        self,
        prompt: str,
        response_model: Any,
        system_instruction: str = "You are a helpful assistant.",
        model: str = "quality",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Generate structured response using Pydantic model."""
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        if handler is None:
            raise LLMScopeUnresolvedError(
                tenant_id or self._tenant_id,
                self._unresolved_scope_reason_for(tenant_id))

        # Personalization
        agent_id = kwargs.get("agent_id")
        user_id = kwargs.get("user_id")
        explicit_temperature = kwargs.pop("temperature", None)
        if agent_id and self.continuous_learning:
            params = self.continuous_learning.get_personalized_parameters(
                tenant_id=workspace_id or tenant_id or self._workspace_id,
                agent_id=agent_id,
                user_id=user_id
            )
            # Personalization applies only when the caller did not pass an
            # explicit temperature (temperature is a **kwargs entry here).
            if "temperature" in params and explicit_temperature is None:
                kwargs["temperature"] = params["temperature"]

        # Re-forward the caller's explicit temperature (popped above).
        if explicit_temperature is not None:
            kwargs["temperature"] = explicit_temperature

        # The `model` argument doubles as the DEFAULT task_type
        # ("quality"/"fast"/a model name) — legacy behaviour, kept when the
        # caller is silent. A caller-supplied task_type MUST win: it is how
        # small structured workloads (planning / extraction / nl2sql) declare
        # themselves for BPC's cost-priority ranking. Passing both is a
        # TypeError ("got multiple values for keyword argument 'task_type'"),
        # which silently killed every tagged leg — the planner and canvas
        # editor both returned no plan in 0.2s (observed live 2026-09-10).
        effective_task_type = kwargs.pop("task_type", None) or model

        return await handler.generate_structured_response(
            prompt=prompt,
            system_instruction=system_instruction,
            response_model=response_model,
            task_type=effective_task_type,
            **kwargs
        )

    async def generate_speech(
        self,
        text: str,
        voice: str = "alloy",
        model: str = "tts-1",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """Generate speech via BYOKHandler (OpenAI TTS)."""
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        if handler is None:
            raise LLMScopeUnresolvedError(
                tenant_id or self._tenant_id,
                self._unresolved_scope_reason_for(tenant_id))
        provider_id = self.get_provider(model).value
        client = handler.async_clients.get(provider_id) or handler.clients.get(provider_id)

        if not client:
            raise ValueError(f"No client found for provider {provider_id}")

        response = await client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            **kwargs
        )
        return response.read()

    def estimate_tokens(self, text: Union[str, List[Dict[str, str]]], model: str = "gpt-4o-mini") -> int:
        """Estimate tokens for text or a list of chat messages."""
        if isinstance(text, str):
            return self._token_counter.count_tokens(text, model)
        elif isinstance(text, list):
            return self._context_validator.estimate_request_tokens(text, model)
        return 0

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost in USD."""
        try:
            from core.cost_config import get_llm_cost
            return get_llm_cost(model, input_tokens, output_tokens)
        except ImportError:
            # Fallback hardcoded pricing (approximate)
            if "gpt-4o-mini" in model: return (input_tokens * 0.15 + output_tokens * 0.6) / 1e6
            if "gpt-4o" in model: return (input_tokens * 5.0 + output_tokens * 15.0) / 1e6
            if "deepseek" in model: return (input_tokens * 0.14 + output_tokens * 0.28) / 1e6
            return (input_tokens * 1.0 + output_tokens * 2.0) / 1e6

    async def generate_with_tier(
        self,
        prompt: str,
        system_instruction: str = "You are a helpful assistant.",
        task_type: Optional[str] = None,
        user_tier_override: Optional[str] = None,
        agent_id: Optional[str] = None,
        image_payload: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate response using cognitive tier routing with intelligent 5-tier system.

        Phase 222-03: Exposes BYOKHandler's generate_with_cognitive_tier method for
        cost-optimized, quality-aware LLM routing with automatic escalation.

        Five Cognitive Tiers:
        - MICRO: Ultra-low cost (<$0.01/M tokens), simple tasks (greetings, basic QA)
        - STANDARD: Balanced cost/quality (~$0.50/M tokens), general tasks (chat, summarization)
        - VERSATILE: Advanced capabilities (~$2-5/M tokens), complex tasks (reasoning, analysis)
        - HEAVY: High-performance (~$10-20/M tokens), demanding tasks (code gen, research)
        - COMPLEX: Maximum quality (~$30+/M tokens), critical tasks (architecture, security)

        Pipeline:
        1. Classify prompt complexity (token count + semantic analysis + task type)
        2. Check budget constraints (monthly + per-request limits)
        3. Select optimal model (cache-aware cost scoring)
        4. Generate with automatic escalation on quality issues

        Args:
            prompt: The user query
            system_instruction: System prompt for the LLM
            task_type: Optional task type hint (code, chat, analysis, etc.)
            user_tier_override: Optional user-specified tier (bypasses classification)
                Valid values: "micro", "standard", "versatile", "heavy", "complex"
            agent_id: Optional agent ID for cost tracking and escalation history
            image_payload: Optional base64/URL image for multimodal input

        Returns:
            Dictionary with keys:
            - response: str - Generated text response
            - tier: str - Cognitive tier used (e.g., "standard", "versatile")
            - provider: str - Provider ID used (e.g., "openai", "anthropic")
            - model: str - Model name used (e.g., "gpt-4o-mini", "claude-3-5-sonnet")
            - cost_cents: float - Estimated cost in cents
            - escalated: bool - Whether escalation occurred (True if tier was upgraded)
            - request_id: str - Unique request ID for tracking
            - error: str - Error message if generation failed

        Example:
            >>> service = LLMService()
            >>> result = await service.generate_with_tier(
            ...     "Explain quantum computing in simple terms",
            ...     task_type="analysis"
            ... )
            >>> print(result["response"])
            >>> print(f"Tier: {result['tier']}, Model: {result['model']}, Cost: ${result['cost_cents']/100:.4f}")

            >>> # Force specific tier (bypass classification)
            >>> result = await service.generate_with_tier(
            ...     "Write a Python function",
            ...     user_tier_override="versatile"
            ... )
        """
        return await self.handler.generate_with_cognitive_tier(
            prompt=prompt,
            system_instruction=system_instruction,
            task_type=task_type,
            user_tier_override=user_tier_override,
            agent_id=agent_id,
            image_payload=image_payload
        )

    async def analyze_proposal(self, proposal: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Governance helper: Analyze an agent proposal for safety and alignment."""
        prompt = f"Analyze the following agent proposal for safety, alignment, and efficiency:\n\nPROPOSAL:\n{proposal}"
        if context:
            prompt += f"\n\nCONTEXT:\n{context}"

        system = "You are an Agent Governance Auditor. Evaluate the proposal and return a JSON-formatted analysis with 'safe' (bool), 'risk_level' (str), and 'recommendation' (str)."

        response = await self.generate(prompt, system_instruction=system, model="quality")

        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            return json.loads(json_str)
        except Exception:
            return {
                "safe": "Unknown" in response or "safe" in response.lower(),
                "raw_response": response,
                "error": "Failed to parse structured audit"
            }

    def is_available(self) -> bool:
        """Check if LLM service is available. An unresolved scope is
        explicitly NOT available (it would dispatch another scope's
        providers)."""
        if self._scope_unresolved_reason:
            return False
        return len(self.handler.clients) > 0 if hasattr(self, 'handler') and self.handler else False

    def get_optimal_provider(
        self,
        complexity: str = "moderate",
        task_type: Optional[str] = None,
        prefer_cost: bool = True,
        tenant_plan: str = "free",
        is_managed_service: bool = True,
        requires_tools: bool = False,
        requires_structured: bool = False,
        turn_index: int = 0
    ) -> tuple[str, str]:
        """
        Get the optimal provider and model for a given complexity level.
        
        Args:
            complexity: Query complexity level
            task_type: Optional task type hint
            prefer_cost: Whether to prefer cost over quality
            tenant_plan: Tenant plan for model restrictions
            is_managed_service: Whether this is managed service or BYOK
            requires_tools: Whether model must support tool calling
            requires_structured: Whether model must support structured output
            turn_index: Interaction turn (0 = creation, 1+ = reuse)
        """
        # Map complexity string to QueryComplexity enum
        complexity_map = {
            "simple": QueryComplexity.SIMPLE,
            "moderate": QueryComplexity.MODERATE,
            "complex": QueryComplexity.COMPLEX,
            "advanced": QueryComplexity.ADVANCED
        }
        complexity_enum = complexity_map.get(complexity.lower(), QueryComplexity.MODERATE)

        result = self.handler.get_optimal_provider(
            complexity=complexity_enum,
            task_type=task_type,
            prefer_cost=prefer_cost,
            tenant_plan=tenant_plan,
            is_managed_service=is_managed_service,
            requires_tools=requires_tools,
            requires_structured=requires_structured,
            turn_index=turn_index
        )
        return AwaitableResult(result)

    def get_ranked_providers(
        self,
        complexity: str = "moderate",
        task_type: Optional[str] = None,
        prefer_cost: bool = True,
        tenant_plan: str = "free",
        is_managed_service: bool = True,
        requires_tools: bool = False,
        requires_structured: bool = False,
        estimated_tokens: int = 1000,
        cognitive_tier: Optional[str] = None,
        turn_index: int = 0
    ) -> List[tuple[str, str]]:
        # Map complexity string to QueryComplexity enum
        complexity_map = {
            "simple": QueryComplexity.SIMPLE,
            "moderate": QueryComplexity.MODERATE,
            "complex": QueryComplexity.COMPLEX,
            "advanced": QueryComplexity.ADVANCED
        }
        complexity_enum = complexity_map.get(complexity.lower(), QueryComplexity.MODERATE)

        # Map cognitive_tier string to CognitiveTier enum if provided
        cognitive_tier_enum = None
        if cognitive_tier:
            tier_map = {
                "micro": CognitiveTier.MICRO,
                "standard": CognitiveTier.STANDARD,
                "versatile": CognitiveTier.VERSATILE,
                "heavy": CognitiveTier.HEAVY,
                "complex": CognitiveTier.COMPLEX
            }
            cognitive_tier_enum = tier_map.get(cognitive_tier.lower())

        result = self.handler.get_ranked_providers(
            complexity=complexity_enum,
            task_type=task_type,
            prefer_cost=prefer_cost,
            tenant_plan=tenant_plan,
            is_managed_service=is_managed_service,
            requires_tools=requires_tools,
            requires_structured=requires_structured,
            estimated_tokens=estimated_tokens,
            workspace_id=self.workspace_id,
            cognitive_tier=cognitive_tier_enum,
            turn_index=turn_index
        )
        return AwaitableResult(result)

    def get_available_providers(self) -> List[str]:
        """
        Get list of providers with valid API keys.

        Returns:
            List of provider IDs (e.g., ["openai", "anthropic", "deepseek"])

        Example:
            >>> service = LLMService()
            >>> providers = service.get_available_providers()
            >>> print(providers)  # ['openai', 'deepseek', ...]
        """
        return self.handler.get_available_providers()

    def get_context_window(self, model_name: str) -> int:
        """
        Get the context window size for a model from dynamic pricing data.
        Returns a safe default if not found.

        Args:
            model_name: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet")

        Returns:
            Context window size in tokens (e.g., 128000, 200000)

        Example:
            >>> service = LLMService()
            >>> context = service.get_context_window("gpt-4o")
            >>> print(context)  # 128000
        """
        return self.handler.get_context_window(model_name)

    def truncate_to_context(self, text: str, model_name: str, reserve_tokens: int = 1000) -> str:
        """
        Truncate text to fit within the model's context window.
        Reserves tokens for the response.

        Args:
            text: Input text to truncate
            model_name: Model identifier for context window lookup
            reserve_tokens: Tokens to reserve for response (default 1000)

        Returns:
            Truncated text that fits in context window, with truncation indicator

        Example:
            >>> service = LLMService()
            >>> short = service.truncate_to_context(long_text, "gpt-4o", reserve_tokens=2000)
        """
        return self.handler.truncate_to_context(text, model_name, reserve_tokens)

    def get_routing_info(self, prompt: str, task_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get routing decision info without making an API call.

        Useful for UI preview features - shows users which model will be used
        and estimated cost before generation.

        Args:
            prompt: The user prompt to analyze
            task_type: Optional task type hint

        Returns:
            Dict with keys:
                - complexity: str (complexity level)
                - selected_provider: str (provider ID)
                - selected_model: str (model name)
                - available_providers: List[str] (list of providers)
                - cost_tier: str (budget/mid/premium)
                - estimated_cost_usd: Optional[float] (estimated cost)
                - error: Optional[str] (error message if no providers available)

        Example:
            >>> service = LLMService()
            >>> info = service.get_routing_info("Explain quantum computing")
            >>> print(f"Using {info['selected_model']} at {info['estimated_cost_usd']}")
        """
        return self.handler.get_routing_info(prompt=prompt, task_type=task_type)

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "auto",
        provider_id: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        agent_id: Optional[str] = None,
        db = None,
        reasoning_sink: Optional[Dict[str, Any]] = None,
        fallback_models: Optional[List[str]] = None,
        fallback_routes: Optional[List[tuple]] = None,
        estimated_tokens: Optional[int] = None,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        """
        Stream LLM responses token-by-token with automatic provider fallback.

        Provides real-time streaming of LLM responses with governance tracking and
        automatic provider fallback on failure. This is the unified streaming interface
        for all LLM interactions in the platform.

        Args:
            messages: Chat messages in OpenAI format (role + content)
            model: Model name (default: "auto" for optimal model selection)
            provider_id: Provider identifier (default: "auto" for optimal provider)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            agent_id: Optional agent ID for governance tracking
            db: Optional database session for governance tracking

        Yields:
            Individual tokens as they arrive from the LLM

        Example:
            ```python
            llm_service = LLMService()
            messages = [{"role": "user", "content": "Hello!"}]
            async for token in llm_service.stream_completion(messages):
                print(token, end="", flush=True)
            ```

        Note:
            - When provider_id="auto", analyzes query complexity to select optimal provider
            - Includes automatic provider fallback on failure
            - Integrates with governance tracking when agent_id and db are provided
        """
        # Analyze complexity for auto provider selection
        # Explicit request scope reaches handler selection here too: the
        # streamed turn routes with the SAME handler scope the
        # non-streaming paths use (both identifiers, never a collapse).
        handler = self._get_handler(workspace_id=workspace_id,
                                    tenant_id=tenant_id)
        if handler is None:
            # Unresolved scope: refuse BEFORE any dispatch — the caller's
            # non-streaming fallback renders the explicit refusal.
            raise LLMScopeUnresolvedError(
                tenant_id or self._tenant_id,
                self._unresolved_scope_reason_for(tenant_id))
        if provider_id == "auto":
            # Extract prompt from messages for complexity analysis
            prompt = ""
            for msg in messages:
                if msg.get("role") == "user":
                    prompt += msg.get("content", "") + "\n"

            # Get optimal provider based on complexity
            complexity = handler.analyze_query_complexity(prompt)
            optimal_provider, optimal_model = await handler.get_optimal_provider(complexity)
            provider_id = optimal_provider  # Already a string, not an enum

            # Map model from "auto" to optimal model for complexity
            if model == "auto":
                model = optimal_model

        # Delegate to BYOKHandler's stream_completion
        async for token in handler.stream_completion(
            messages=messages,
            model=model,
            provider_id=provider_id,
            temperature=temperature,
            max_tokens=max_tokens,
            agent_id=agent_id,
            db=db,
            reasoning_sink=reasoning_sink,
            fallback_models=fallback_models,
            # Ranked (provider, model) pairs: the provider travels WITH the
            # model, so a fallback ranked for provider B is dispatched to B.
            fallback_routes=fallback_routes,
            # MEASURED input size so the streaming path can apply the same
            # dispatch-time window check the non-streaming path uses.
            estimated_tokens=estimated_tokens,
        ):
            yield token

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        system_instruction: str = "You are a helpful assistant.",
        temperature: float = 0.2,
        model: str = "auto",
        task_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        image_payload: Optional[str] = None,
        enable_self_consistency: bool = False,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        stage_decision_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[BaseModel]:
        """
        Generate structured output using Pydantic model validation.

        Provides tenant-aware routing between BYOK and Managed AI based on subscription,
        with support for vision inputs via image_payload.

        Phase 2 hallucination-mitigation kwargs:

          * ``enable_self_consistency`` — when True AND the
            ``ATOM_SELF_CONSISTENCY`` env flag is enabled, dispatches to the
            ``SelfConsistencyVoter`` for N-sample majority voting. The voter
            uses the BYOKHandler directly, so each sample composes naturally
            with cascade routing inside the handler. Shadow + audit: a
            ``SelfConsistencyVote`` row is written for every vote (regardless
            of agreement level) when the voter runs.

        Cascade routing (Workstream B) is handled *inside* the BYOKHandler
        when the ``ATOM_CASCADE_ROUTING`` env flag is enabled — this wrapper
        just forwards the resolved flag value.

        Args:
            prompt: The user prompt
            response_model: Pydantic model class for structured output validation
            system_instruction: System instruction for the LLM
            temperature: Sampling temperature (0.0-1.0)
            model: Model name (default: "auto" for optimal model selection)
            task_type: Optional task type hint (e.g., "summarization", "code_generation")
            agent_id: Optional agent ID for cost tracking
            image_payload: Optional Base64 image string or URL for vision support
            enable_self_consistency: Opt in to N-sample majority voting for
                irreversible-action decisions (Phase 2 hallucination
                mitigation; default off).
            session_id: Optional session ID for audit attribution when the
                self-consistency voter runs.
            user_id: Optional user ID for audit attribution when the
                self-consistency voter runs.

        Returns:
            Instance of response_model with validated data, or None if generation fails
        """
        # Check if handler has clients available — for the scope the
        # request actually names (both identifiers, never a collapse).
        _structured_handler = self._get_handler(workspace_id=workspace_id,
                                                tenant_id=tenant_id)
        if _structured_handler is None:
            logger.warning(
                "Structured generation refused: %s",
                self._unresolved_scope_reason_for(tenant_id))
            return None
        if not _structured_handler.clients:
            logger.warning("No LLM clients available for structured generation")
            return None

        # Phase 2: resolve mitigation flags once per call. The actual
        # cascade retry loop lives inside BYOKHandler.generate_structured_response.
        from core.hallucination_config import (
            is_cascade_routing_enabled,
            is_self_consistency_enabled,
        )

        cascade_on = is_cascade_routing_enabled()

        # Self-consistency voter dispatch (Workstream C). Shadow + audit:
        # dispatches to vote_with_consensus, writes a SelfConsistencyVote
        # audit row, and returns the modal plan. Force-proposal gating
        # (routing to ProposalService on partial/ambiguous) is the caller's
        # responsibility via generate_structured_with_consensus.
        if enable_self_consistency and is_self_consistency_enabled():
            winner, _vote = await self._run_self_consistency_vote(
                prompt=prompt,
                response_model=response_model,
                system_instruction=system_instruction,
                temperature=temperature,
                task_type=task_type,
                agent_id=agent_id,
                image_payload=image_payload,
                cascade=cascade_on,
                session_id=session_id,
                user_id=user_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
            )
            return winner

        # Delegate to BYOKHandler's generate_structured_response
        try:
            result = await _structured_handler.generate_structured_response(
                prompt=prompt,
                system_instruction=system_instruction,
                response_model=response_model,
                temperature=temperature,
                task_type=task_type,
                agent_id=agent_id,
                image_payload=image_payload,
                cascade=cascade_on,
                stage_decision_id=stage_decision_id,
            )
            return result
        except Exception as e:
            logger.error(f"Structured generation failed: {e}")
            return None

    async def generate_structured_with_consensus(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        system_instruction: str = "You are a helpful assistant.",
        temperature: float = 0.2,
        model: str = "auto",
        task_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        image_payload: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Generate structured output with self-consistency metadata.

        Always dispatches through the self-consistency voter (requires
        ``ATOM_SELF_CONSISTENCY=true``). Returns ``(winner, vote_result)``
        where ``vote_result`` is a ``VoteResult`` or ``None`` (when the
        flag is off or the voter is otherwise disabled).

        Callers that want to gate on agreement level should use this method
        and inspect ``vote_result.requires_review``. The gating decision
        itself (calling ProposalService) is the caller's responsibility,
        mirroring the match-confidence pattern where ``browser_tool.py``
        decides whether to gate, not ``selector_confidence_service``.

        Example::

            winner, vote = await llm.generate_structured_with_consensus(
                prompt=plan_prompt,
                response_model=ActionPlan,
                agent_id=agent.id,
            )
            if vote and vote.requires_review and force_proposal_enabled:
                await proposal_service.create_action_proposal(...)
                return None  # do not execute
            # Execute winner exactly once.
        """
        if not self.is_available():
            logger.warning("No LLM clients available for structured generation")
            return None, None

        from core.hallucination_config import (
            is_cascade_routing_enabled,
            is_self_consistency_enabled,
        )

        cascade_on = is_cascade_routing_enabled()

        if not is_self_consistency_enabled():
            # Flag off — fall through to single-sample path, no vote metadata.
            try:
                result = await self.handler.generate_structured_response(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_model=response_model,
                    temperature=temperature,
                    task_type=task_type,
                    agent_id=agent_id,
                    image_payload=image_payload,
                    cascade=cascade_on,
                )
                return result, None
            except Exception as e:
                logger.error(f"Structured generation failed: {e}")
                return None, None

        return await self._run_self_consistency_vote(
            prompt=prompt,
            response_model=response_model,
            system_instruction=system_instruction,
            temperature=temperature,
            task_type=task_type,
            agent_id=agent_id,
            image_payload=image_payload,
            cascade=cascade_on,
            session_id=session_id,
            user_id=user_id,
        )

    async def _run_self_consistency_vote(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        system_instruction: str,
        temperature: float,
        task_type: Optional[str],
        agent_id: Optional[str],
        image_payload: Optional[str],
        cascade: bool,
        session_id: Optional[str],
        user_id: Optional[str],
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        """Dispatch to SelfConsistencyVoter.vote_with_consensus + persist audit.

        Returns ``(winner, VoteResult)``. Never raises — voter and audit
        failures degrade gracefully to ``(None, None)`` so the caller's
        LLM call never crashes due to audit infrastructure.

        Shadow mode: audit row is written unconditionally; force-proposal
        gating is NOT applied here (caller's job).
        """
        from core.llm.self_consistency_voter import SelfConsistencyVoter

        try:
            voter = SelfConsistencyVoter(
                handler=self._get_handler(workspace_id=workspace_id,
                                          tenant_id=tenant_id),
                db=self._db,
                tenant_id=self._tenant_id,
            )
            if voter.handler is None:
                logger.warning(
                    "Self-consistency vote refused: %s",
                    self._unresolved_scope_reason_for(tenant_id))
                return None, None
            vote = await voter.vote_with_consensus(
                prompt=prompt,
                response_model=response_model,
                temperature=temperature,
                agent_id=agent_id,
                cascade=cascade,
                system_instruction=system_instruction,
                task_type=task_type,
                image_payload=image_payload,
            )
        except Exception as exc:
            logger.error(f"Self-consistency voter failed: {exc}")
            return None, None

        # Persist audit row. Best-effort — never let audit failures break
        # the LLM call.
        try:
            self._write_self_consistency_audit(
                vote=vote,
                agent_id=agent_id,
                session_id=session_id,
                user_id=user_id,
                response_model=response_model,
            )
        except Exception as exc:
            logger.warning(f"Self-consistency audit write failed: {exc}")

        return vote.winner, vote

    def _write_self_consistency_audit(
        self,
        vote,
        agent_id: Optional[str],
        session_id: Optional[str],
        user_id: Optional[str],
        response_model: Type[BaseModel],
    ) -> None:
        """Write one ``SelfConsistencyVote`` row. Best-effort.

        Uses ``self._db`` when available (does NOT close it — caller owns the
        lifecycle); otherwise opens a fresh session via the
        ``get_db_session()`` context manager (auto-closed on exit).
        """
        try:
            from core.models import SelfConsistencyVote
        except Exception:
            return

        row = SelfConsistencyVote(
            tenant_id=self._tenant_id if self._tenant_id != "default" else None,
            workspace_id=self._workspace_id if self._workspace_id != "default" else None,
            agent_id=agent_id,
            user_id=user_id,
            session_id=session_id,
            prompt_hash=vote.prompt_hash,
            response_model_name=getattr(response_model, "__name__", None),
            sample_count=vote.sample_count,
            valid_count=vote.valid_count,
            winner_count=vote.winner_count,
            distinct_hashes=vote.distinct_hashes,
            agreement_ratio=vote.agreement_ratio,
            level=vote.level,
            winner_hash=vote.winner_hash,
            hash_algo=vote.hash_algo,
            temperatures=vote.temperatures,
            gated=False,  # gating is the caller's responsibility
            proposal_id=None,
            error_message=None if vote.valid_count > 0 else "all samples returned None",
        )

        # Caller-provided session — add+commit but do not close.
        if self._db is not None:
            try:
                self._db.add(row)
                self._db.commit()
            except Exception as exc:
                try:
                    self._db.rollback()
                except Exception:
                    pass
                logger.debug(f"Self-consistency audit commit failed: {exc}")
            return

        # No caller session — open our own via the context manager.
        try:
            from core.database import get_db_session

            with get_db_session() as db:
                db.add(row)
                # get_db_session auto-commits on clean context exit; the
                # explicit commit is belt-and-suspenders.
                db.commit()
        except Exception as exc:
            logger.debug(f"Self-consistency audit (own session) failed: {exc}")

    async def generate_embedding(
        self,
        text: str,
        model: str = "text-embedding-3-small",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[float]:
        """
        Generate embedding vector for a single text string using unified BYOK resolution.
        Supports OpenAI and Cohere via BYOKHandler.
        """
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        if handler is None:
            raise LLMScopeUnresolvedError(
                tenant_id or self._tenant_id,
                self._unresolved_scope_reason_for(tenant_id))
        
        # Identify provider from model name
        provider = "openai"
        if "embed-english" in model.lower() or "embed-multilingual" in model.lower():
            provider = "cohere"

        try:
            embedding = await handler.generate_embedding(
                text=text,
                model=model,
                provider=provider
            )
            
            # Metadata for tracking
            token_count = len(text) // 4 # Basic estimate
            if provider == "openai":
                cost_per_1k = 0.00002 if model == "text-embedding-3-small" else 0.00013
                estimated_cost = (token_count / 1000) * cost_per_1k
            else:
                estimated_cost = (token_count / 1000) * 0.0001
            
            # Track usage. Previously called llm_usage_tracker.track_usage(...)
            # which doesn't exist (the method is `record`, with different kwargs:
            # workspace_id + cost_usd, not estimated_cost). The AttributeError
            # was swallowed by this try/except, so ALL embedding usage/cost went
            # untracked — budgets and spend totals missed every embedding call.
            try:
                llm_usage_tracker.record(
                    workspace_id=self._workspace_id,
                    provider=provider,
                    model=model,
                    input_tokens=token_count,
                    output_tokens=0,
                    cost_usd=estimated_cost,
                )
            except Exception as tracking_error:
                logger.debug(f"Usage tracking failed: {tracking_error}")

            return embedding

        except Exception as e:
            logger.error(f"Embedding generation failed for provider {provider}: {e}")
            raise

    async def transcribe_audio(
        self,
        file: Any,
        model: str = "whisper-1",
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: str = "json",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text.
        
        Args:
            file: Audio file object (as required by OpenAI API)
            model: Transcription model (default: "whisper-1")
            language: Optional language of the audio
            prompt: Optional guiding prompt for transcription
            response_format: "json", "text", "srt", "verbose_json", "vtt"
            tenant_id: Optional tenant override
            
        Returns:
            Dict containing 'text' and metadata.
        """
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        if handler is None:
            raise LLMScopeUnresolvedError(
                tenant_id or self._tenant_id,
                self._unresolved_scope_reason_for(tenant_id))
        return await handler.generate_transcription(
            file=file,
            model=model,
            language=language,
            prompt=prompt,
            response_format=response_format
        )

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[List[float]]:
        """
        Generate embedding vectors for multiple texts in a single batch operation using unified BYOK.
        """
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        if handler is None:
            raise LLMScopeUnresolvedError(
                tenant_id or self._tenant_id,
                self._unresolved_scope_reason_for(tenant_id))
        
        provider = "openai"
        if "embed-english" in model.lower() or "embed-multilingual" in model.lower():
            provider = "cohere"

        try:
            all_embeddings = await handler.generate_embeddings_batch(
                texts=texts,
                model=model,
                provider=provider
            )
            
            # Metadata for tracking
            total_tokens = sum(len(t) // 4 for t in texts)
            if provider == "openai":
                cost_per_1k = 0.00002 if model == "text-embedding-3-small" else 0.00013
                estimated_cost = (total_tokens / 1000) * cost_per_1k
            else:
                estimated_cost = (total_tokens / 1000) * 0.0001

            # Track usage (see generate_embedding: record(), not track_usage()).
            try:
                llm_usage_tracker.record(
                    workspace_id=self._workspace_id,
                    provider=provider,
                    model=model,
                    input_tokens=total_tokens,
                    output_tokens=0,
                    cost_usd=estimated_cost,
                )
            except Exception as tracking_error:
                logger.debug(f"Usage tracking failed: {tracking_error}")

            return all_embeddings

        except Exception as e:
            logger.error(f"Batch embedding generation failed for provider {provider}: {e}")
            raise

    def classify_tier(self, prompt: str, task_type: Optional[str] = None) -> CognitiveTier:
        """
        Classify a prompt into a cognitive tier.

        Phase 222-03: Helper method to understand tier decisions without making API calls.

        Uses the CognitiveClassifier to analyze prompt complexity based on:
        - Token count (shorter prompts -> lower tiers)
        - Semantic complexity (keywords, structure)
        - Task type hints (code, analysis, etc.)

        Args:
            prompt: The user prompt to classify
            task_type: Optional task type hint (code, chat, analysis, etc.)

        Returns:
            CognitiveTier enum value (MICRO, STANDARD, VERSATILE, HEAVY, or COMPLEX)

        Example:
            >>> service = LLMService()
            >>> tier = service.classify_tier("Hi there")
            >>> print(tier)  # CognitiveTier.MICRO

            >>> tier = service.classify_tier("Write a Python REST API with authentication", task_type="code")
            >>> print(tier)  # CognitiveTier.VERSATILE or HEAVY

        Note:
            This is a classification-only operation. It does not check budgets,
            select models, or make API calls. Use generate_with_tier() for full routing.
        """
        return self.handler.classify_cognitive_tier(prompt, task_type)

    def get_tier_description(self, tier: Union[str, CognitiveTier]) -> Dict[str, Any]:
        """
        Get human-readable description of a cognitive tier.

        Phase 222-03: Helper method to understand tier characteristics without making API calls.

        Provides detailed information about each cognitive tier including:
        - Cost range (per million tokens)
        - Quality level (benchmark scores)
        - Typical use cases
        - Example models

        Args:
            tier: Cognitive tier as string (e.g., "standard") or CognitiveTier enum

        Returns:
            Dictionary with keys:
                - name: str (tier name)
                - cost_range: str (cost per million tokens)
                - quality_level: str (quality description)
                - use_cases: List[str] (typical use cases)
                - example_models: List[str] (example models in this tier)

        Example:
            >>> service = LLMService()
            >>> desc = service.get_tier_description("versatile")
            >>> print(desc["cost_range"])  # "~$2-5/M tokens"
            >>> print(desc["use_cases"])   # ["Reasoning", "Analysis", "Code generation"]

            >>> # Can also use CognitiveTier enum
            >>> from core.llm.cognitive_tier_system import CognitiveTier
            >>> desc = service.get_tier_description(CognitiveTier.MICRO)
            >>> print(desc["cost_range"])  # "<$0.01/M tokens"

        Note:
            If tier string is invalid, returns description for STANDARD tier as fallback.
        """
        # Convert string to CognitiveTier enum if needed
        if isinstance(tier, str):
            tier_map = {
                "micro": CognitiveTier.MICRO,
                "standard": CognitiveTier.STANDARD,
                "versatile": CognitiveTier.VERSATILE,
                "heavy": CognitiveTier.HEAVY,
                "complex": CognitiveTier.COMPLEX
            }
            tier_enum = tier_map.get(tier.lower(), CognitiveTier.STANDARD)
        else:
            tier_enum = tier

        # Tier descriptions
        descriptions = {
            CognitiveTier.MICRO: {
                "name": "MICRO",
                "cost_range": "<$0.01/M tokens",
                "quality_level": "Basic quality for simple tasks",
                "use_cases": [
                    "Greetings and casual chat",
                    "Basic Q&A",
                    "Simple confirmations",
                    "Low-stakes recommendations"
                ],
                "example_models": [
                    "gpt-4o-mini",
                    "claude-3-haiku",
                    "gemini-1.5-flash"
                ]
            },
            CognitiveTier.STANDARD: {
                "name": "STANDARD",
                "cost_range": "~$0.50/M tokens",
                "quality_level": "Balanced cost/quality for general tasks",
                "use_cases": [
                    "General conversation",
                    "Text summarization",
                    "Basic explanations",
                    "Everyday tasks"
                ],
                "example_models": [
                    "gpt-4o-mini",
                    "claude-3-haiku",
                    "mini-m2.5"
                ]
            },
            CognitiveTier.VERSATILE: {
                "name": "VERSATILE",
                "cost_range": "~$2-5/M tokens",
                "quality_level": "Advanced capabilities for complex tasks",
                "use_cases": [
                    "Complex reasoning",
                    "Data analysis",
                    "Code generation",
                    "Multi-step problem solving"
                ],
                "example_models": [
                    "gpt-4o",
                    "claude-3-5-sonnet",
                    "gemini-1.5-pro"
                ]
            },
            CognitiveTier.HEAVY: {
                "name": "HEAVY",
                "cost_range": "~$10-20/M tokens",
                "quality_level": "High-performance for demanding tasks",
                "use_cases": [
                    "Advanced code generation",
                    "Research and analysis",
                    "Complex document processing",
                    "Architectural decisions"
                ],
                "example_models": [
                    "claude-3-opus",
                    "gpt-4-turbo",
                    "gemini-1.5-pro"
                ]
            },
            CognitiveTier.COMPLEX: {
                "name": "COMPLEX",
                "cost_range": "~$30+/M tokens",
                "quality_level": "Maximum quality for critical tasks",
                "use_cases": [
                    "Security analysis",
                    "System architecture",
                    "Critical business decisions",
                    "Complex multi-agent coordination"
                ],
                "example_models": [
                    "claude-3-opus",
                    "gpt-4",
                    "claude-3-5-sonnet"
                ]
            }
        }

        return descriptions.get(tier_enum, descriptions[CognitiveTier.STANDARD])

    def analyze_query_complexity(self, prompt: str, task_type: Optional[str] = None) -> QueryComplexity:
        """
        Analyze query complexity to determine optimal provider routing.

        Uses regex-based heuristic with expanded vocabulary for robust classification.

        Args:
            prompt: The user prompt to analyze
            task_type: Optional task type hint (code, chat, analysis, etc.)

        Returns:
            QueryComplexity enum value (SIMPLE, MODERATE, COMPLEX, or ADVANCED)

        Example:
            >>> service = LLMService()
            >>> complexity = service.analyze_query_complexity("Write a Python REST API")
            >>> print(complexity.value)  # 'complex' or 'advanced'
        """
        return self.handler.analyze_query_complexity(prompt, task_type)


def get_llm_service(workspace_id: Optional[str] = None, db=None, tenant_id: Optional[str] = None) -> LLMService:
    """Factory function to get an LLMService instance."""
    return LLMService(workspace_id=workspace_id, tenant_id=tenant_id, db=db)
