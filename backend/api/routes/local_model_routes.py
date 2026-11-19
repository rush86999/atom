"""
Local Model Provider API Routes.

Lets users register OpenAI-compatible local LLM backends (Ollama, LM Studio,
vLLM, LocalAI, custom) and configure per-model capabilities. Registered models
become eligible for BPC ranking, cognitive tier assignment, and learning-router
re-ranking — just like cloud models, but at zero cost.

Routes mount at /api/local-models/...
"""

from __future__ import annotations

import inspect
import logging
import math
import mimetypes
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.database import get_db
from core.llm_service import LLMService
from core.media_duration import media_duration_seconds
from core.models import LocalModelProvider, LocalModelCapabilities, User
from core.security_dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/local-models", tags=["Local Models"])

# Upload limits for the signed-in recording path. 25 MiB mirrors the
# OpenAI-compatible transcription family's documented request limit. The
# route reads at most one byte beyond the limit so an oversized upload is
# refused without buffering an arbitrarily large body.
MAX_TRANSCRIPTION_UPLOAD_BYTES = 25 * 1024 * 1024

_CONTENT_TYPE_EXTENSIONS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/flac": ".flac",
}

_EXTENSION_CONTENT_TYPES = {
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".flac": "audio/flac",
}


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class RegisterProviderRequest(BaseModel):
    name: str = Field(..., description="User-friendly label, e.g. 'My Ollama'")
    provider_type: str = Field("custom", description="ollama | lm_studio | vllm | localai | custom")
    base_url: str = Field(..., description="OpenAI-compatible endpoint, e.g. http://localhost:11434/v1")
    api_key: Optional[str] = Field(None, description="Optional — for backends that require a key")


class SetCapabilitiesRequest(BaseModel):
    """Capability upsert payload.

    The existing capability fields keep their original request defaults and
    replacement behavior. The chat and audio fields are the exception: they are
    optional and omission-preserving so an edit from a client that predates
    them cannot accidentally disable chat, disable transcription or clear its
    rate. Explicit ``false``/``null`` still changes the setting, because
    Pydantic distinguishes those from an omitted field. A new row defaults to
    chat-capable, which is also the historical behavior.

    ``supports_chat=false`` marks an AUDIO-ONLY model: transcription must be
    enabled as well, and the model is then excluded from every chat discovery,
    ranking and pricing path.
    """

    model_id: str = Field(..., description="Model name as served by the provider, e.g. 'llama3:8b'")
    supports_tools: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    supports_chat: Optional[bool] = Field(
        None,
        description=(
            "Offer this model for chat. Defaults to true for new models and "
            "keeps its stored value when omitted. False marks an audio-only "
            "model, which requires transcription to be enabled."
        ),
    )
    supports_transcription: Optional[bool] = Field(
        None,
        description="Enable audio transcription for this model. Requires audio_input_cost_per_second_usd.",
    )
    audio_input_cost_per_second_usd: Optional[float] = Field(
        None,
        ge=0.0,
        description="USD per second of audio input. 0 is a valid explicit rate; null clears it.",
    )
    quality_score: float = Field(0.5, ge=0.0, le=1.0)
    speed_score: float = Field(0.5, ge=0.0, le=1.0)
    context_window: int = Field(4096, gt=0)

    @field_validator("audio_input_cost_per_second_usd")
    @classmethod
    def _finite_audio_rate(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and not math.isfinite(value):
            raise ValueError("audio_input_cost_per_second_usd must be a finite number")
        return value


class ProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str
    is_active: bool
    has_api_key: bool


class CapabilitiesResponse(BaseModel):
    model_id: str
    supports_tools: bool
    supports_vision: bool
    supports_reasoning: bool
    supports_transcription: bool
    audio_input_cost_per_second_usd: Optional[float] = None
    quality_score: float
    speed_score: float
    context_window: int
    supports_chat: bool = True


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("")
async def list_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all registered local model providers for the current user's workspace."""
    ws_id = current_user.workspace_id or "default"
    providers = db.query(LocalModelProvider).filter(
        LocalModelProvider.workspace_id == ws_id,
        LocalModelProvider.is_active == True,  # noqa: E712
    ).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "provider_type": p.provider_type,
            "base_url": p.base_url,
            "is_active": p.is_active,
            "has_api_key": bool(p.api_key),
        }
        for p in providers
    ]


@router.post("")
async def register_provider(
    request: RegisterProviderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Register a new local model provider."""
    # SSRF guard: base_url must be http(s) and not target private/loopback
    # addresses (169.254.169.254 metadata, localhost, internal services).
    from urllib.parse import urlparse
    import ipaddress
    parsed = urlparse(request.base_url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="base_url must be http or https")
    hostname = parsed.hostname or ""
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(
                status_code=400,
                detail="base_url must not point to a private, loopback, or link-local address",
            )
    except ValueError:
        # hostname is a DNS name, not an IP — allow (DNS rebinding is a
        # residual risk but blocking all DNS names would break legitimate use).
        pass
    ws_id = current_user.workspace_id or "default"
    provider = LocalModelProvider(
        workspace_id=ws_id,
        tenant_id=current_user.tenant_id,
        name=request.name,
        provider_type=request.provider_type,
        base_url=request.base_url.rstrip("/"),
        api_key=request.api_key,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    logger.info(f"Registered local model provider '{request.name}' at {request.base_url}")
    return {"id": provider.id, "name": provider.name, "registered": True}


def _get_owned_provider(provider_id: str, workspace_id: str, db: Session) -> LocalModelProvider:
    """Fetch a provider and verify workspace ownership. 404 if not found or not owned."""
    provider = db.query(LocalModelProvider).filter(
        LocalModelProvider.id == provider_id,
        LocalModelProvider.workspace_id == workspace_id,
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.delete("/{provider_id}")
async def unregister_provider(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Unregister a local model provider."""
    ws_id = current_user.workspace_id or "default"
    provider = _get_owned_provider(provider_id, ws_id, db)
    db.delete(provider)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Model discovery
# ---------------------------------------------------------------------------

@router.get("/{provider_id}/models")
async def discover_models(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Auto-discover available models from a local provider.

    Calls GET {base_url}/models (the OpenAI-compatible endpoint) and returns
    the model list. Also registers each discovered model into the pricing cache
    so capability detection works.
    """
    ws_id = current_user.workspace_id or "default"
    provider = _get_owned_provider(provider_id, ws_id, db)

    try:
        headers = {}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{provider.base_url}/models", headers=headers)
            resp.raise_for_status()
            data = resp.json()

        models = []
        # Audio-only models stay discoverable so they can be configured for
        # transcription, but they must not (re)enter the shared chat pricing
        # catalog during discovery.
        try:
            configured = {
                c.model_id: c
                for c in db.query(LocalModelCapabilities).filter(
                    LocalModelCapabilities.provider_id == provider.id,
                    LocalModelCapabilities.workspace_id == ws_id,
                ).all()
            }
        except Exception:  # noqa: BLE001 — discovery is best-effort
            configured = {}
        for m in data.get("data", []):
            model_id = m.get("id") or m.get("name", "")
            if model_id:
                models.append(model_id)
                capability = configured.get(model_id)
                chat_enabled = (
                    True if capability is None
                    else getattr(capability, "supports_chat", True) is not False
                )
                # Register into the pricing cache so capability detection works.
                # Audio-only rows are explicitly excluded from that catalog.
                _register_in_pricing_cache(
                    model_id, provider,
                    None if chat_enabled else {"supports_chat": False},
                )

        return {"models": models, "count": len(models)}
    except Exception as e:
        logger.warning(f"Model discovery failed for {provider.name}: {e}")
        return {"models": [], "count": 0, "error": "model discovery failed"}


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

@router.get("/{provider_id}/capabilities")
async def get_capabilities(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get configured capabilities for all models under a provider."""
    ws_id = current_user.workspace_id or "default"
    provider = _get_owned_provider(provider_id, ws_id, db)
    caps = db.query(LocalModelCapabilities).filter(
        LocalModelCapabilities.provider_id == provider.id,
        LocalModelCapabilities.workspace_id == ws_id,
    ).all()
    return [
        {
            "model_id": c.model_id,
            "supports_tools": c.supports_tools,
            "supports_vision": c.supports_vision,
            "supports_reasoning": c.supports_reasoning,
            "supports_chat": (
                True if getattr(c, "supports_chat", True) is None
                else bool(getattr(c, "supports_chat"))
            ),
            "supports_transcription": bool(c.supports_transcription),
            "audio_input_cost_per_second_usd": c.audio_input_cost_per_second_usd,
            "quality_score": c.quality_score,
            "speed_score": c.speed_score,
            "context_window": c.context_window,
        }
        for c in caps
    ]


@router.post("/{provider_id}/capabilities")
async def set_capabilities(
    provider_id: str,
    request: SetCapabilitiesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Set capabilities for a specific model under a provider.

    This tells the system what the local model can do (since there's no
    pricing-cache metadata for local models). Feeds into BPC capability
    filtering, cognitive tier assignment, and the learning router registry.

    The original non-audio fields keep their replacement semantics: an omitted
    field takes its request default. The chat and audio settings are preserved
    when omitted, so edits from clients that predate them cannot accidentally
    disable chat or transcription (or clear the rate). A NEW row defaults to
    chat-capable.
    """
    ws_id = current_user.workspace_id or "default"
    provider = _get_owned_provider(provider_id, ws_id, db)

    # Upsert: update if exists, create if not.
    existing = db.query(LocalModelCapabilities).filter(
        LocalModelCapabilities.provider_id == provider.id,
        LocalModelCapabilities.workspace_id == ws_id,
        LocalModelCapabilities.model_id == request.model_id,
    ).first()

    provided = request.model_fields_set

    def _resolve_optional(field: str, default: Any) -> Any:
        """Omitted optional setting keeps its stored value on update."""
        if field in provided:
            return getattr(request, field)
        if existing is not None:
            stored = getattr(existing, field, None)
            return default if stored is None else stored
        return default

    resolved_chat = _resolve_optional("supports_chat", True)
    values: Dict[str, Any] = {
        "supports_tools": request.supports_tools,
        "supports_vision": request.supports_vision,
        "supports_reasoning": request.supports_reasoning,
        # NULL is not an explicit audio-only declaration: only ``false``
        # disables chat. Omitted values keep the stored value (default true).
        "supports_chat": True if resolved_chat is None else bool(resolved_chat),
        "supports_transcription": bool(
            _resolve_optional("supports_transcription", False)
        ),
        "audio_input_cost_per_second_usd": _resolve_optional(
            "audio_input_cost_per_second_usd", None
        ),
        "quality_score": request.quality_score,
        "speed_score": request.speed_score,
        "context_window": request.context_window,
    }

    audio_rate = values["audio_input_cost_per_second_usd"]
    if audio_rate is not None and (not math.isfinite(audio_rate) or audio_rate < 0):
        raise HTTPException(
            status_code=400,
            detail="audio_input_cost_per_second_usd must be a finite, non-negative number",
        )
    if not values["supports_chat"] and not values["supports_transcription"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Audio-only models require transcription to be enabled "
                "(supports_transcription=true)."
            ),
        )
    if values["supports_transcription"] and audio_rate is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "audio_input_cost_per_second_usd is required to enable transcription "
                "(0 is a valid explicit rate)"
            ),
        )

    if existing:
        existing.supports_tools = values["supports_tools"]
        existing.supports_vision = values["supports_vision"]
        existing.supports_reasoning = values["supports_reasoning"]
        existing.supports_chat = values["supports_chat"]
        existing.supports_transcription = values["supports_transcription"]
        existing.audio_input_cost_per_second_usd = audio_rate
        existing.quality_score = values["quality_score"]
        existing.speed_score = values["speed_score"]
        existing.context_window = values["context_window"]
    else:
        cap = LocalModelCapabilities(
            provider_id=provider.id,
            workspace_id=ws_id,
            model_id=request.model_id,
            **values,
        )
        db.add(cap)

    db.commit()

    # Register into the pricing cache so BPC capability detection works.
    # Only the pre-existing routing metadata is passed; audio pricing stays a
    # settings concern and does not alter provider billing. An audio-only
    # model is REMOVED from chat catalog/pricing metadata instead.
    _register_in_pricing_cache(request.model_id, provider, values)

    return {
        "model_id": request.model_id,
        "set": True,
        "supports_chat": values["supports_chat"],
        "supports_transcription": values["supports_transcription"],
        "audio_input_cost_per_second_usd": audio_rate,
    }


# ---------------------------------------------------------------------------
# Transcription (signed-in recording path)
# ---------------------------------------------------------------------------

def _require_actor_scope(current_user: User) -> Tuple[str, str]:
    """Return the actor's (workspace, tenant) or refuse.

    Unlike the settings list endpoints, this path never substitutes
    ``"default"`` for a missing workspace: audio is dispatched through a
    provider selected by scope, so an unidentified scope must fail closed.
    """
    workspace_id = str(getattr(current_user, "workspace_id", "") or "").strip()
    tenant_id = str(getattr(current_user, "tenant_id", "") or "").strip()
    if not workspace_id or not tenant_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "Your account is not associated with a workspace. "
                "Sign in again with a workspace account and retry."
            ),
        )
    return workspace_id, tenant_id


def _safe_upload_filename(upload: UploadFile) -> str:
    """A bounded, path-free filename for the downstream multipart part."""
    raw = str(getattr(upload, "filename", "") or "").replace("\\", "/")
    name = os.path.basename(raw).strip()
    # Keep only a conservative filename charset (defense against multipart
    # header injection) and cap the length; the name is only a label.
    name = "".join(
        ch if ch.isalnum() or ch in "._- " else "_" for ch in name
    )[:200].strip()
    if not name:
        name = "recording"
    if "." not in name:
        content_type = (
            str(getattr(upload, "content_type", "") or "")
            .split(";", 1)[0]
            .strip()
            .lower()
        )
        name += _CONTENT_TYPE_EXTENSIONS.get(content_type, ".webm")
    return name


def _sniff_audio_content_type(data: bytes) -> Optional[str]:
    """Best-effort MIME type from container magic, never from the filename."""
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[:4] == b"fLaC":
        return "audio/flac"
    if data[:4] == b"OggS":
        return "audio/ogg"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "audio/webm"
    if len(data) >= 12 and data[4:8] in (
        b"ftyp",
        b"moov",
        b"free",
        b"mdat",
        b"wide",
        b"skip",
    ):
        return "audio/mp4"
    if data[:3] == b"ID3" or (
        len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0
    ):
        return "audio/mpeg"
    return None


def _validate_audio_payload(data: bytes, filename: str) -> float:
    """Refuse empty, excessive, or unmeasurable audio and return its duration.

    Duration is measured from the submitted bytes (not from caller-supplied
    metadata) so an upload cannot under-state how much audio is being sent.
    A blob with no readable duration is rejected instead of being forwarded
    with a guessed/unknown length.
    """
    if not data:
        raise HTTPException(
            status_code=400,
            detail="Record or choose an audio file first.",
        )
    if len(data) > MAX_TRANSCRIPTION_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Audio file is too large. Keep recordings under 25 MB.",
        )
    try:
        seconds = media_duration_seconds(data, filename)
    except Exception:  # noqa: BLE001 — malformed media is a user error
        seconds = None
    if seconds is None or not math.isfinite(seconds) or seconds <= 0:
        raise HTTPException(
            status_code=400,
            detail="That audio file could not be read. Try recording again.",
        )
    return seconds


class _AudioUploadPart(tuple):
    """One audio part that is both an OpenAI-style tuple and file-like.

    The existing service's audio helpers consume a
    ``(filename, bytes, content_type)`` tuple, while a service wrapper may
    legitimately treat the argument as an uploaded file. This value supports
    both readings without changing either contract.
    """

    filename: str
    content_type: str
    size: int

    def __new__(cls, filename: str, data: bytes, content_type: str):
        instance = super().__new__(cls, (filename, data, content_type))
        instance.filename = filename
        instance.content_type = content_type
        instance.size = len(data)
        return instance

    @property
    def name(self) -> str:
        return self.filename

    async def read(self, size: int = -1) -> bytes:
        data = self[1]
        if size is not None and size >= 0:
            return data[:size]
        return data

    async def seek(self, offset: int = 0, whence: int = 0) -> int:
        # The payload is immutable, so every read starts at the beginning.
        return 0

    async def close(self) -> None:
        return None


def _extract_transcript(result: Any) -> Optional[str]:
    """Normalize the service's text result without inventing a transcript."""
    if isinstance(result, str):
        return result
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text
    if isinstance(result, dict):
        for key in ("transcript", "transcription", "text", "content"):
            value = result.get(key)
            if isinstance(value, str):
                return value
        nested = result.get("data")
        if isinstance(nested, str):
            return nested
        if isinstance(nested, dict):
            for key in ("transcript", "transcription", "text"):
                value = nested.get(key)
                if isinstance(value, str):
                    return value
    return None


@router.post("/{provider_id}/transcriptions")
async def transcribe_with_local_model(
    provider_id: str,
    model: str = Form(..., description="Model id enabled for transcription"),
    file: UploadFile = File(..., description="One audio recording"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Transcribe one audio file with an explicitly selected local model.

    The caller's authenticated (workspace, tenant) scope is authoritative.
    Both the provider and the per-model transcription declaration must be
    active and belong to that exact scope; anything else is refused before
    any audio leaves the process.

    The uploaded bytes are validated and measured here (so empty, oversized
    and unreadable media fail with a user-facing 4xx), then handed to the
    existing :class:`LLMService` scoped audio dispatch. No provider endpoint,
    client, or URL is constructed in this route.
    """
    workspace_id, tenant_id = _require_actor_scope(current_user)

    model_id = str(model or "").strip()
    if not model_id:
        raise HTTPException(
            status_code=400,
            detail="Choose a transcription model first.",
        )
    if len(model_id) > 200:
        raise HTTPException(
            status_code=400,
            detail="Choose a valid transcription model.",
        )

    provider = db.query(LocalModelProvider).filter(
        LocalModelProvider.id == provider_id,
        LocalModelProvider.workspace_id == workspace_id,
        LocalModelProvider.tenant_id == tenant_id,
        LocalModelProvider.is_active.is_(True),
    ).first()
    if provider is None:
        # Same response for unknown, foreign, and inactive providers so the
        # route cannot be used to probe another workspace's registrations.
        raise HTTPException(
            status_code=404,
            detail="Provider not found or inactive.",
        )

    capability = db.query(LocalModelCapabilities).filter(
        LocalModelCapabilities.provider_id == provider.id,
        LocalModelCapabilities.workspace_id == workspace_id,
        LocalModelCapabilities.model_id == model_id,
        LocalModelCapabilities.supports_transcription.is_(True),
        LocalModelCapabilities.audio_input_cost_per_second_usd.isnot(None),
    ).first()
    if capability is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "This model is not enabled for transcription. "
                "Enable audio transcription for it in Local Models settings."
            ),
        )
    audio_rate = capability.audio_input_cost_per_second_usd
    try:
        audio_rate_is_valid = (
            audio_rate is not None
            and math.isfinite(float(audio_rate))
            and float(audio_rate) >= 0
        )
    except (TypeError, ValueError):
        audio_rate_is_valid = False
    if not audio_rate_is_valid:
        raise HTTPException(
            status_code=400,
            detail=(
                "This model's audio configuration is not valid. "
                "Review it in Local Models settings."
            ),
        )

    try:
        payload = await file.read(MAX_TRANSCRIPTION_UPLOAD_BYTES + 1)
    except Exception:
        logger.warning(
            "Could not read local transcription upload for provider=%s",
            provider.id,
        )
        raise HTTPException(
            status_code=400,
            detail="That audio file could not be read. Try recording again.",
        )
    finally:
        try:
            await file.close()
        except Exception:
            pass

    filename = _safe_upload_filename(file)
    duration_seconds = _validate_audio_payload(payload, filename)

    content_type = (
        str(getattr(file, "content_type", "") or "")
        .split(";", 1)[0]
        .strip()
        .lower()
    )
    if not content_type or content_type == "application/octet-stream":
        extension = os.path.splitext(filename)[1].lower()
        content_type = (
            _EXTENSION_CONTENT_TYPES.get(extension)
            or mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )
    content_type = _sniff_audio_content_type(payload) or content_type

    # The existing service accepts the OpenAI-style (filename, bytes, type)
    # multipart payload. Passing bytes also means the service's own duration
    # probe sees the same media this route validated.
    transport_file = _AudioUploadPart(filename, payload, content_type)

    try:
        service = LLMService(
            db=db, workspace_id=workspace_id, tenant_id=tenant_id
        )
        result = service.transcribe_audio(
            file=transport_file,
            model=model_id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            local_provider_id=provider.id,
        )
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:  # noqa: BLE001 — provider detail stays server-side
        logger.warning(
            "Local transcription failed for provider=%s model=%s: %s",
            provider.id,
            model_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Transcription failed. Please try again.",
        )

    if isinstance(result, dict) and result.get("success") is False:
        logger.warning(
            "Local transcription refused for provider=%s model=%s",
            provider.id,
            model_id,
        )
        raise HTTPException(
            status_code=502,
            detail="Transcription failed. Please try again.",
        )

    transcript = _extract_transcript(result)
    if transcript is None:
        logger.warning(
            "Local transcription returned no text for provider=%s model=%s",
            provider.id,
            model_id,
        )
        raise HTTPException(
            status_code=502,
            detail="Transcription failed. Please try again.",
        )

    return {
        "transcript": transcript,
        "text": transcript,
        "model": model_id,
        "provider_id": provider.id,
        "provider_name": provider.name,
        "duration_seconds": round(duration_seconds, 3),
    }


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------

@router.post("/{provider_id}/test")
async def test_connection(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Test whether a local provider is reachable."""
    ws_id = current_user.workspace_id or "default"
    provider = _get_owned_provider(provider_id, ws_id, db)

    try:
        headers = {}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{provider.base_url}/models", headers=headers)
            resp.raise_for_status()
        return {"reachable": True, "status_code": resp.status_code}
    except Exception as e:
        logger.warning(f"Local model connectivity check failed: {e}")
        return {"reachable": False, "error": "connectivity check failed"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_in_pricing_cache(
    model_id: str,
    provider: LocalModelProvider,
    capabilities: Optional[Dict[str, Any]] = None,
) -> None:
    """Inject a local model into the in-memory pricing cache so BPC and
    capability-detection functions work without changing their logic.

    The entry carries its ASSOCIATION (J2 provider-scope work order):
    the owning workspace and the ``local_<id>`` client key that holds
    the endpoint. Two workspaces registering the same model name keep
    separate routes — the shared entry only carries public pricing
    metadata; endpoint selection and registration-specific capabilities
    are read from the handler's own scoped records.

    An AUDIO-ONLY model (``supports_chat`` false) is never published here:
    the shared cache feeds chat discovery/ranking/pricing, so this helper
    removes this registration's own entry (and only that entry) instead of
    advertising a model that must not be offered for chat.
    """
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        fetcher = get_pricing_fetcher()
        provider_key = f"local_{provider.id[:8]}"
        if capabilities is not None and capabilities.get(
                "supports_chat", True) is False:
            existing_entry = fetcher.pricing_cache.get(model_id)
            if (
                isinstance(existing_entry, dict)
                and str(existing_entry.get("provider_key") or "") == provider_key
                and str(existing_entry.get("workspace_id") or "")
                == str(provider.workspace_id)
            ):
                fetcher.pricing_cache.pop(model_id, None)
            return
        entry = {
            "model_id": model_id,
            "litellm_provider": provider.provider_type,
            "input_cost": 0.0,
            "output_cost": 0.0,
            "max_input_tokens": (capabilities or {}).get("context_window", 8192),
            "supports_tools": (capabilities or {}).get("supports_tools", True),
            "supports_vision": (capabilities or {}).get("supports_vision", False),
            "supports_reasoning": (capabilities or {}).get("supports_reasoning", False),
            "quality_score": (capabilities or {}).get("quality_score", 0.5),
            "provider_key": provider_key,
            "workspace_id": provider.workspace_id,
        }
        fetcher.pricing_cache[model_id] = entry
    except Exception as e:
        logger.debug(f"Could not register local model in pricing cache: {e}")
