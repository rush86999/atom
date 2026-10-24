import hashlib
import json
import logging
import os
import secrets
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from core.auth import get_current_user, User
from core.models import (
    RuntimeSetting,
    SettingChangeAudit,
    Tenant,
    TenantSetting,
    UserRole,
)
from core.database import get_db
from core.auth import get_current_tenant
from core.byok_endpoints import sanitize_key_label
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from core.schemas import ApiResponse

# BYOK Configuration Storage
# Anchored to <backend>/data regardless of the launch CWD: the previous
# "./data" form made the key store depend on where uvicorn was started
# (repo root vs backend/), silently splitting credentials across two files.
# The BYOK_* env vars override — tests/isolated installs rely on them.
_BYOK_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
BYOK_CONFIG_FILE = os.getenv("BYOK_CONFIG_FILE") or os.path.join(
    _BYOK_DATA_DIR, "byok_config.json"
)
BYOK_KEYS_FILE = os.getenv("BYOK_KEYS_FILE") or os.path.join(
    _BYOK_DATA_DIR, "byok_keys.json"
)
# R59: the Fernet encryption key must survive restarts — without persistence a
# fresh random key is generated per process and every stored API key becomes
# undecryptable (silent bricking of the BYOK system).
BYOK_ENC_KEY_FILE = os.getenv("BYOK_ENC_KEY_FILE") or os.path.join(
    _BYOK_DATA_DIR, "byok_encryption_key"
)


def _clear_provider_check(byok_manager, tenant_id: str, provider_id: str) -> None:
    """A key change invalidates the last connection check.

    A global key change affects every tenant's resolution, so it clears
    the provider's check in every usage bucket, not only ``"global"``.
    """
    try:
        stats = getattr(byok_manager, "usage_stats", {}) or {}
        scopes = list(stats.keys()) if tenant_id == "global" else [tenant_id]
        for scope in scopes:
            usage = (stats.get(scope) or {}).get(provider_id)
            if usage is None:
                continue
            usage.last_check_at = None
            usage.last_check_ok = None
            usage.last_check_status = None
            usage.last_check_message = None
            usage.last_check_provider = None
            usage.last_check_model = None
            usage.last_check_latency_ms = None
    except Exception as exc:  # noqa: BLE001 — best-effort status reset
        logger.debug("provider check reset skipped: %s", exc)


def _invalidate_provider_route_state(provider_id: Optional[str] = None) -> None:
    """Clear cached route knowledge after a credential change.

    A key the provider rejected five minutes ago may be valid now, and a model
    catalogue fetched with the old key may not describe the new one. Recovery
    must not wait for a cooldown TTL: storing or deleting a key re-opens the
    provider (and its discovery) immediately. Best-effort — never blocks the
    operator's request.
    """
    try:
        from core.llm.byok_handler import BYOKHandler

        BYOKHandler.invalidate_provider_failures(provider_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("provider route state not invalidated: %s", exc)


def _is_usable_api_key(key: Optional[str]) -> bool:
    """True when a resolved key exists AND is not a known placeholder.

    Mirrors the runtime dummy filter in core/llm/byok_handler (keys shorter
    than 12 chars or "dummy"-prefixed are refused before any provider call),
    so the UI's "active" badge means the key would actually be usable. A
    stored leftover like "sk-test" therefore reports inactive instead of
    presenting a broken provider as configured.
    """
    if not key:
        return False
    if key.startswith("60a9596d") or key.startswith("dummy") or len(key) < 12:
        return False
    return True


def _db_key_sync_enabled() -> bool:
    """SaaS parity gate for the ``tenant_settings`` BYOK mirror.

    Atom is single-tenant: the encrypted file store (``BYOK_KEYS_FILE``) is
    the SINGLE source of truth for API keys. The DB mirror is a co-equal
    second source only under SaaS parity mode (``ATOM_BYOK_DB_SYNC=true``);
    locally it is off by default, so keys are stored/read/deleted in exactly
    one place. Legacy DB rows remain deleteable either way (hygiene).
    """
    import os

    return os.getenv("ATOM_BYOK_DB_SYNC", "false").strip().lower() in ("1", "true", "yes")


@dataclass
class AIProviderConfig:
    """Configuration for AI providers"""

    id: str
    name: str
    description: str
    api_key_env_var: str
    base_url: Optional[str] = None
    model: Optional[str] = None
    cost_per_token: float = 0.0
    supported_tasks: List[str] = None
    max_requests_per_minute: int = 60
    rate_limit_window: int = 60
    is_active: bool = True
    requires_encryption: bool = True
    reasoning_level: int = 1  # 1=Low, 2=Medium, 3=High, 4=Very High

    def __post_init__(self):
        if self.supported_tasks is None:
            self.supported_tasks = []


@dataclass
class ProviderUsage:
    """Usage tracking for AI providers"""

    provider_id: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens_used: int = 0
    cost_accumulated: float = 0.0
    last_used: Optional[datetime] = None
    rate_limit_remaining: int = 0
    rate_limit_reset: Optional[datetime] = None
    # The LAST bounded connection check for this provider, if one was run.
    # "active" alone is not a successful inference test; the UI reads these
    # fields to distinguish Key saved / Not checked / Ready / auth / quota.
    last_check_at: Optional[datetime] = None
    last_check_ok: Optional[bool] = None
    last_check_status: Optional[str] = None
    last_check_message: Optional[str] = None
    last_check_provider: Optional[str] = None
    last_check_model: Optional[str] = None
    last_check_latency_ms: Optional[int] = None


@dataclass
class APIKey:
    """Encrypted API key storage"""

    provider_id: str
    key_name: str
    encrypted_key: str
    key_hash: str
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool = True
    usage_count: int = 0
    environment: str = "production"
    tenant_id: Optional[str] = None
    # Friendly display label (e.g. "Ollama (local)", "<provider> (onboarding)").
    # NEVER part of the lookup identity — resolution keys on
    # (tenant_id, provider_id, key_name, environment), so the canonical
    # key_name="default" written by the wizard and Settings resolves through
    # every reader while the human label lives only here. Round-trips through
    # the shared byok_keys.json via the dataclass fields (see the matching
    # field in core.byok_endpoints, whose loader filters by field names).
    label: Optional[str] = None


class BYOKManager:
    """BYOK (Bring Your Own Key) Management System"""

    #: See core.byok_endpoints.BYOKManager: class-level so __new__-constructed
    #: instances (tests/tooling) still have the store-state contract.
    _store_lock: "threading.RLock" = threading.RLock()
    _keys_file_signature: Optional[tuple] = None

    def __init__(self):
        self.providers: Dict[str, AIProviderConfig] = {}
        self.usage_stats: Dict[str, Dict[str, ProviderUsage]] = {}  # tenant_id -> provider_id -> ProviderUsage
        self.api_keys: Dict[str, APIKey] = {}
        self._store_lock = threading.RLock()
        self._keys_file_signature: Optional[tuple] = None
        # R59: env override wins; otherwise reuse the persisted key so stored
        # ciphertext survives process restarts (previously a fresh random key
        # per start made every stored key undecryptable).
        self.encryption_key = os.getenv("BYOK_ENCRYPTION_KEY")
        if not self.encryption_key:
            self.encryption_key = self._load_or_create_encryption_key()
        else:
            # Keep the persisted file in sync with the env override so keys
            # survive even if .env is later lost or regenerated (see mirror).
            self._mirror_encryption_key_file(self.encryption_key)
        self._load_configuration()
        try:
            stamp = os.stat(BYOK_KEYS_FILE)
            self._keys_file_signature = (stamp.st_mtime_ns, stamp.st_size)
        except OSError:
            self._keys_file_signature = None
        self._initialize_default_providers()

    def _load_configuration(self):
        """Load configuration from disk"""
        # Load providers
        if os.path.exists(BYOK_CONFIG_FILE):
            try:
                with open(BYOK_CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    from dataclasses import fields
                    provider_fields = {f.name for f in fields(AIProviderConfig)}
                    for p_data in data.get("providers", []):
                        # R62: filter to known fields — a single unknown field
                        # (older/newer writer) used to brick the whole load.
                        p_data_filtered = {
                            k: v for k, v in p_data.items() if k in provider_fields
                        }
                        provider = AIProviderConfig(**p_data_filtered)
                        self.providers[provider.id] = provider
            except Exception as e:
                logger.error(f"Failed to load BYOK config: {e}")

        # Load API keys
        if os.path.exists(BYOK_KEYS_FILE):
            try:
                with open(BYOK_KEYS_FILE, "r") as f:
                    data = json.load(f)
                    from dataclasses import fields
                    key_fields = {f.name for f in fields(APIKey)}
                    for k_id, k_data in data.get("keys", {}).items():
                        # Convert ISO strings back to datetime
                        if k_data.get("created_at"):
                            k_data["created_at"] = datetime.fromisoformat(k_data["created_at"])
                        if k_data.get("last_used"):
                            k_data["last_used"] = datetime.fromisoformat(k_data["last_used"])

                        # R62: filter to known fields — same rationale as providers.
                        k_data_filtered = {
                            k: v for k, v in k_data.items() if k in key_fields
                        }
                        api_key = APIKey(**k_data_filtered)
                        self.api_keys[k_id] = api_key
            except Exception as e:
                logger.error(f"Failed to load BYOK keys: {e}")

    def _save_configuration(self):
        """Save configuration to disk — ATOMICALLY.

        Same-file contract with ``core.byok_endpoints``: the runtime manager
        re-reads whenever the file signature changes (lazy refresh), so a
        torn non-atomic write here would make the runtime see a half-written
        store. ``os.replace`` means readers observe the old or the new file,
        never a partially flushed one.
        """
        # Ensure data directory exists
        os.makedirs(os.path.dirname(BYOK_CONFIG_FILE), exist_ok=True)
        
        # Save providers
        try:
            self._atomic_write_json(BYOK_CONFIG_FILE, {
                "providers": [asdict(p) for p in self.providers.values()]
            })
        except Exception as e:
            logger.error(f"Failed to save BYOK config: {e}")

        # Save API keys
        try:
            # LOST-UPDATE GUARD (review finding 3): a peer writer (the runtime
            # manager, a tool constructing its own manager) may have saved
            # since our last read/write; adopt its entries before serialising
            # our view, or the next save silently drops them.
            self._merge_disk_entries()
            # Convert datetime objects to ISO strings for JSON serialization
            keys_data = {}
            for k_id, k_obj in self.api_keys.items():
                k_dict = asdict(k_obj)
                if k_dict.get("created_at"):
                    k_dict["created_at"] = k_dict["created_at"].isoformat()
                if k_dict.get("last_used"):
                    k_dict["last_used"] = k_dict["last_used"].isoformat()
                keys_data[k_id] = k_dict

            self._atomic_write_json(BYOK_KEYS_FILE, {"keys": keys_data})
            try:
                stamp = os.stat(BYOK_KEYS_FILE)
                self._keys_file_signature = (stamp.st_mtime_ns, stamp.st_size)
            except OSError:
                self._keys_file_signature = None
        except Exception as e:
            logger.error(f"Failed to save BYOK keys: {e}")

    def _merge_disk_entries(self) -> None:
        """Adopt entries another writer saved since our last read/write.

        Mirror of ``core.byok_endpoints.BYOKManager._merge_disk_entries``:
        entries this manager already holds win; disk-only entries are
        adopted. Called before every save and before reads, so wizard/
        Settings writes never clobber a peer's key and admin status reads
        see keys written through the runtime manager.
        """
        with self._store_lock:
            try:
                stamp = os.stat(BYOK_KEYS_FILE)
                signature = (stamp.st_mtime_ns, stamp.st_size)
            except OSError:
                return
            if signature == self._keys_file_signature:
                return
            try:
                with open(BYOK_KEYS_FILE, "r") as f:
                    data = json.load(f)
                from dataclasses import fields
                key_fields = {f.name for f in fields(APIKey)}
                for k_id, k_data in (data.get("keys") or {}).items():
                    if k_id in self.api_keys:
                        continue
                    row = dict(k_data)
                    if row.get("created_at"):
                        row["created_at"] = datetime.fromisoformat(row["created_at"])
                    if row.get("last_used"):
                        row["last_used"] = datetime.fromisoformat(row["last_used"])
                    filtered = {k: v for k, v in row.items() if k in key_fields}
                    self.api_keys[k_id] = APIKey(**filtered)
                self._keys_file_signature = signature
            except Exception as e:
                # Never drop this manager's entries because of a foreign read.
                logger.error(f"Failed to merge BYOK keys from disk: {e}")

    @staticmethod
    def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
        """Write JSON to ``path`` via a same-directory temp file + replace.

        Mirrors ``core.byok_endpoints.BYOKManager._atomic_write_json`` (the
        two managers share one durable file; keep the write discipline
        identical).
        """
        import tempfile

        directory = os.path.dirname(path) or "."
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2)
                f.write("\n")
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _initialize_default_providers(self):
        """Initialize default AI providers"""
        defaults = [
            AIProviderConfig(
                id="openai",
                name="OpenAI",
                description="GPT-5.3, GPT-4o and GPT-4o-mini models",
                api_key_env_var="OPENAI_API_KEY",
                supported_tasks=["general", "chat", "code", "analysis", "reasoning", "pdf_ocr"],
                cost_per_token=0.00003,
                model="gpt-5.3",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="anthropic",
                name="Anthropic",
                description="Claude 4.6 Opus and Claude 3.5 Sonnet",
                api_key_env_var="ANTHROPIC_API_KEY",
                supported_tasks=["general", "chat", "code", "analysis", "writing", "reasoning"],
                cost_per_token=0.000015,
                model="claude-4.6-opus",
                reasoning_level=2
            ),
            AIProviderConfig(
                id="moonshot",
                name="Moonshot AI (Kimi)",
                description="Kimi k1.5 Thinking Model",
                api_key_env_var="MOONSHOT_API_KEY",
                base_url="https://api.moonshot.cn/v1",
                supported_tasks=["general", "chat", "thinking", "reasoning"],
                cost_per_token=0.00001, # Estimated
                model="kimi-k2-thinking",
                reasoning_level=4
            ),
            AIProviderConfig(
                id="google",
                name="Google Gemini",
                description="Gemini 1.5 Pro",
                api_key_env_var="GOOGLE_API_KEY",
                base_url="https://generativelanguage.googleapis.com/v1beta",
                supported_tasks=["general", "chat", "code", "analysis", "multimodal", "reasoning"],
                cost_per_token=0.0000125,
                model="gemini-1.5-pro",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="google_flash",
                name="Google Gemini Flash",
                description="Gemini 1.5 Flash - High Speed",
                api_key_env_var="GOOGLE_API_KEY",
                base_url="https://generativelanguage.googleapis.com/v1beta",
                supported_tasks=["general", "chat", "summary", "extraction", "vision", "pdf_ocr"],
                cost_per_token=0.0000005,
                model="gemini-1.5-flash",
                reasoning_level=2
            ),
            AIProviderConfig(
                id="google_flash_3_5",
                name="Google Gemini 3.5 Flash",
                description="Gemini 3.5 Flash - Ultra High Speed",
                api_key_env_var="GOOGLE_API_KEY",
                base_url="https://generativelanguage.googleapis.com/v1beta",
                supported_tasks=["general", "chat", "summary", "extraction", "vision", "pdf_ocr"],
                cost_per_token=0.0000003,
                model="gemini-3.5-flash",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="gemini",
                name="Gemini (OpenAI-compatible)",
                description="Google Gemini via the OpenAI-compatible endpoint",
                api_key_env_var="GEMINI_API_KEY",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                supported_tasks=["general", "chat", "code", "reasoning", "vision"],
                cost_per_token=0.000001,
                model="gemini-3.5-flash",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="lux",
                name="Lux Computer Use",
                description="Lux Model for Computer Use Agents",
                api_key_env_var="LUX_MODEL_API_KEY",
                supported_tasks=["computer_use", "agentic", "desktop"],
                cost_per_token=0.00002, 
                model="lux-1.0",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="deepseek",
                name="DeepSeek",
                description="DeepSeek-V3 and DeepSeek-R1",
                api_key_env_var="DEEPSEEK_API_KEY",
                base_url="https://api.deepseek.com/v1",
                supported_tasks=["general", "chat", "code", "analysis", "reasoning"],
                cost_per_token=0.000002,
                model="deepseek-chat",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="glm",
                name="Zhipu GLM",
                description="GLM-4, GLM-4.6, and GLM-5 models",
                api_key_env_var="GLM_API_KEY",
                base_url="https://open.bigmodel.cn/api/paas/v4",
                supported_tasks=["general", "chat", "analysis", "reasoning", "vision"],
                cost_per_token=0.000005,
                model="glm-5",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="qwen",
                name="Qwen (Alibaba)",
                description="Qwen 3.5 capabilities",
                api_key_env_var="QWEN_API_KEY",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                supported_tasks=["general", "chat", "code", "analysis", "reasoning"],
                cost_per_token=0.000002,
                model="qwen-turbo",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="minimax",
                name="MiniMax",
                description="MiniMax M3 Flagship (512K context, image input)",
                api_key_env_var="MINIMAX_API_KEY",
                base_url="https://api.minimax.io/v1",
                supported_tasks=["general", "chat", "code", "reasoning", "vision"],
                cost_per_token=0.00000075,
                model="MiniMax-M3",
                reasoning_level=4
            ),
            AIProviderConfig(
                id="groq",
                name="Groq",
                description="Groq Llama 3.1 and Mixtral models",
                api_key_env_var="GROQ_API_KEY",
                base_url="https://api.groq.com/openai/v1",
                supported_tasks=["general", "chat", "code", "analysis"],
                cost_per_token=0.000001,
                model="llama-3.1-70b-versatile",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="mistral",
                name="Mistral AI",
                description="Mistral Large 2 and Mixtral models",
                api_key_env_var="MISTRAL_API_KEY",
                base_url="https://api.mistral.ai/v1",
                supported_tasks=["general", "chat", "code", "analysis"],
                cost_per_token=0.000004,
                model="mistral-large-latest",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="perplexity",
                name="Perplexity",
                description="Perplexity Sonar online models",
                api_key_env_var="PERPLEXITY_API_KEY",
                base_url="https://api.perplexity.ai",
                supported_tasks=["search", "chat", "analysis"],
                cost_per_token=0.000005,
                model="llama-3.1-sonar-large-128k-online",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="cohere",
                name="Cohere",
                description="Command R and Command R+ models",
                api_key_env_var="COHERE_API_KEY",
                base_url="https://api.cohere.ai/v1",
                supported_tasks=["chat", "rag", "analysis"],
                cost_per_token=0.000015,
                model="command-r-plus",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="deepinfra",
                name="DeepInfra",
                description="DeepSeek-OCR and other open models",
                api_key_env_var="DEEPINFRA_API_KEY",
                base_url="https://api.deepinfra.com/v1/openai",
                supported_tasks=["general", "chat", "pdf_ocr", "image_comprehension"],
                cost_per_token=0.000001, # Varies by model
                model="deepseek-ai/DeepSeek-OCR",
                reasoning_level=2
            ),
            AIProviderConfig(
                id="deepgram",
                name="Deepgram",
                description="High-speed audio transcription and voice AI",
                api_key_env_var="DEEPGRAM_API_KEY",
                supported_tasks=["transcription", "text_to_speech", "audio_analysis"],
                cost_per_token=0.0001, # Estimated
                model="nova-2",
                reasoning_level=2
            ),
            AIProviderConfig(
                id="tavily",
                name="Tavily",
                description="AI-native web search for agents and RAG",
                api_key_env_var="TAVILY_API_KEY",
                base_url="https://api.tavily.com",
                supported_tasks=["search", "web_search", "research", "rag"],
                cost_per_token=0.00001, # Per search query (estimated)
                model="search",
                reasoning_level=1
            ),
            AIProviderConfig(
                id="brightdata",
                name="Bright Data",
                description="Web scraping and data collection with anti-bot protection",
                api_key_env_var="BRIGHTDATA_API_KEY",
                base_url="https://api.brightdata.com",
                supported_tasks=["search", "crawl", "access", "navigate", "scraping"],
                cost_per_token=0.0,  # Per-request pricing varies
                model="mcp-server",
                reasoning_level=2
            ),
            AIProviderConfig(
                id="openrouter",
                name="OpenRouter",
                description="Unified gateway to 300+ models (OpenAI, Anthropic, Google, Meta, and more). One API key.",
                api_key_env_var="OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1",
                supported_tasks=["general", "chat", "code", "reasoning", "analysis", "vision"],
                cost_per_token=0.000003,  # Varies by model — rough floor
                model="minimax/minimax-m3",
                reasoning_level=4
            ),
            # OpenCode Zen gateway — the BYOK handler has routed provider id
            # "opencode-go" (and alias "opencode") since the OpenCode Go
            # integration, but the catalog never listed them, so the API
            # Keys page had no option to view/store the key (and
            # store_tenant_api_key 404'd for these ids). Same key serves
            # both; Go is the subscription tier.
            AIProviderConfig(
                id="opencode",
                name="OpenCode",
                description="OpenCode Zen gateway — tested open coding models (DeepSeek, Kimi) via one API key.",
                api_key_env_var="OPENCODE_API_KEY",
                base_url="https://opencode.ai/zen/v1",
                supported_tasks=["code", "general", "chat", "reasoning"],
                cost_per_token=0.0,  # Usage-billed; flash-class pricing
                model="deepseek-v4.1-flash",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="opencode-go",
                name="OpenCode Go",
                description="OpenCode Go subscription — flat-rate access to the Zen model catalog (~90% cheaper than direct APIs).",
                api_key_env_var="OPENCODE_API_KEY",
                base_url="https://opencode.ai/zen/v1",
                supported_tasks=["code", "general", "chat", "reasoning"],
                cost_per_token=0.0,  # Subscription: ~$0 marginal per token
                model="deepseek-v4.1-flash",
                reasoning_level=3
            )
        ]
        
        for provider in defaults:
            if provider.id not in self.providers:
                self.providers[provider.id] = provider
        
        # Save defaults
        self._save_configuration()

    def get_available_providers(self) -> List[str]:
        """Get list of available AI provider IDs"""
        return list(self.providers.keys())

    def _generate_encryption_key(self) -> str:
        """Generate a secure encryption key for Fernet"""
        return Fernet.generate_key().decode()

    def _mirror_encryption_key_file(self, env_key: str) -> None:
        """Mirror the env-var Fernet key into the persisted key file.

        ``BYOK_ENCRYPTION_KEY`` wins over the file when both exist, but new
        installs (quickstart-generated .env) therefore never write the file —
        so losing or regenerating .env later made the next restart mint a
        fresh key and brick every stored credential. Writing the winning env
        key to the file keeps an env-less restart decryptable. A DIFFERENT
        file key is left untouched: silently overwriting it could brick keys
        stored under it (only a warning is logged).
        """
        try:
            if os.path.exists(BYOK_ENC_KEY_FILE):
                with open(BYOK_ENC_KEY_FILE, "r") as f:
                    existing = f.read().strip()
                if existing == env_key:
                    return
                if existing:
                    logger.warning(
                        "BYOK_ENCRYPTION_KEY differs from the persisted key "
                        "file — keeping the env override. Credentials stored "
                        "under the file's key will not decrypt."
                    )
                    return
            os.makedirs(os.path.dirname(BYOK_ENC_KEY_FILE), exist_ok=True)
            with open(BYOK_ENC_KEY_FILE, "w") as f:
                f.write(env_key)
            os.chmod(BYOK_ENC_KEY_FILE, 0o600)
        except Exception as e:
            logger.error(f"Failed to mirror BYOK encryption key file: {e}")

    def _load_or_create_encryption_key(self) -> str:
        """Load the persisted Fernet key, or generate and persist one (0600).

        R59: without persistence every process restart generated a fresh key,
        making all previously-stored API keys undecryptable.
        """
        try:
            if os.path.exists(BYOK_ENC_KEY_FILE):
                with open(BYOK_ENC_KEY_FILE, "r") as f:
                    key = f.read().strip()
                if key:
                    return key
        except Exception as e:
            logger.error(f"Failed to read BYOK encryption key: {e}")
        key = self._generate_encryption_key()
        try:
            os.makedirs(os.path.dirname(BYOK_ENC_KEY_FILE), exist_ok=True)
            with open(BYOK_ENC_KEY_FILE, "w") as f:
                f.write(key)
            os.chmod(BYOK_ENC_KEY_FILE, 0o600)
        except Exception as e:
            logger.error(f"Failed to persist BYOK encryption key: {e}")
        return key

    def _get_fernet(self):
        """Get Fernet instance with current key"""
        try:
            key = self.encryption_key
            if not key:
                raise ValueError("Encyrption key is empty")

            if isinstance(key, str):
                key = key.encode()

            return Fernet(key)
        except Exception as e:
            # R61: do NOT rotate the key here — the old code silently generated
            # a fresh key, invalidating all stored ciphertext and diverging
            # from the persisted key. Fail loudly instead.
            logger.error(f"Invalid BYOK encryption key: {e}")
            raise

    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key using Fernet (AES)"""
        f = self._get_fernet()
        return f.encrypt(api_key.encode()).decode()

    def decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt API key using Fernet (AES)"""
        f = self._get_fernet()
        return f.decrypt(encrypted_key.encode()).decode()

    def store_api_key(
        self,
        provider_id: str,
        api_key: str,
        key_name: str = "default",
        environment: str = "production",
        label: Optional[str] = None,
    ) -> str:
        """Store an encrypted API key.

        ``label`` is display-only (bounded, sanitised); ``key_name`` is the
        lookup identity and defaults to the canonical ``"default"``.
        """
        if provider_id not in self.providers:
            raise ValueError(f"Provider {provider_id} not found")

        key_id = f"{provider_id}_{key_name}_{environment}"
        encrypted_key = self.encrypt_api_key(api_key)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        api_key_obj = APIKey(
            provider_id=provider_id,
            key_name=key_name,
            encrypted_key=encrypted_key,
            key_hash=key_hash,
            created_at=datetime.now(),
            environment=environment,
            label=sanitize_key_label(label),
        )

        self.api_keys[key_id] = api_key_obj
        self._save_configuration()
        _invalidate_provider_route_state(provider_id)

        return key_id

    def is_configured(self, tenant_id_or_workspace: str, provider_id: str) -> bool:
        """Check if BYOK is configured for a specific tenant/workspace and provider.

        Must agree with what can actually be RETRIEVED for the same caller:
        the global/named key first, then this tenant's own scoped entry — the
        same resolution ``get_api_key``/``get_tenant_api_key`` perform. The
        old exact-id check returned True for rows whose ciphertext could not
        be decrypted at all, so "configured" and "retrievable" disagreed.
        """
        # 1. Global (or named) key, then this caller's own scoped entry.
        if self.get_api_key(provider_id, tenant_id=tenant_id_or_workspace):
            return True

        # 2. Tenant-scoped key for this caller.
        if self.get_tenant_api_key(tenant_id_or_workspace, provider_id):
            return True

        return False

    def get_api_key(
        self,
        provider_id: str,
        key_name: str = "default",
        environment: str = "production",
        tenant_id: Optional[str] = None,
    ) -> Optional[str]:
        """Retrieve and decrypt an API key.

        This manager serves per-tenant HTTP requests, so an UNSCOPED lookup
        stays global: a tenant's scoped credential must never be reported as
        the installation's global key (that is exactly the leak the
        single-operator carve-out in ``core/byok_endpoints`` must not open
        here). Pass ``tenant_id`` to resolve a specific owner's credential —
        own scope first, then global, never another tenant's.
        """
        api_key_obj = self._find_stored_key(
            provider_id, key_name, environment, tenant_id=tenant_id
        )
        if api_key_obj is None:
            return None

        # Update usage stats
        api_key_obj.last_used = datetime.now()
        api_key_obj.usage_count += 1

        try:
            decrypted_key = self.decrypt_api_key(api_key_obj.encrypted_key)
            return decrypted_key
        except Exception as e:
            logger.error(
                "Failed to decrypt API key %s/%s/%s: %s",
                provider_id, key_name, environment, e,
            )
            return None

    @staticmethod
    def _entry_scope(key_id: str, obj: "APIKey") -> Optional[str]:
        """Owning tenant of a stored entry, or ``None`` when it is global.

        Shared contract with ``core.byok_endpoints.BYOKManager._entry_scope``:
        the recorded field wins, otherwise the tenant is recovered from the id
        the tenant-scoped writer itself constructed. Recovered from the tail,
        because key names may contain underscores and spaces.
        """
        recorded = getattr(obj, "tenant_id", None)
        if isinstance(recorded, str) and recorded.strip():
            return recorded.strip()

        prefix = "tenant_"
        suffix = f"{obj.provider_id}_{obj.key_name}_{obj.environment}"
        if (
            key_id.startswith(prefix)
            and len(key_id) > len(prefix) + len(suffix) + 1
            and key_id.endswith(f"_{suffix}")
        ):
            scope = key_id[len(prefix):-(len(suffix) + 1)]
            return scope or None
        return None

    def _find_stored_key(
        self,
        provider_id: str,
        key_name: str,
        environment: str,
        tenant_id: Optional[str] = None,
    ) -> Optional["APIKey"]:
        """Resolve a stored key by IDENTITY: ``(scope, provider, name, env)``.

        Match by FIELDS, never by the dict id (id shapes differ per writer).
        ``tenant_id`` binds the lookup to that owner; without it, only global
        entries are candidates — see :meth:`get_api_key`.

        A peer writer's save since our last read/write is adopted first
        (lost-update guard), so admin status reads see runtime-written keys.
        """
        self._merge_disk_entries()
        global_entry: Optional[APIKey] = None
        scoped: Dict[str, APIKey] = {}
        for key_id, obj in self.api_keys.items():
            if not isinstance(obj, APIKey):
                continue
            if not getattr(obj, "is_active", True):
                continue
            if (
                str(getattr(obj, "provider_id", "")) != provider_id
                or str(getattr(obj, "key_name", "")) != key_name
                or str(getattr(obj, "environment", "")) != environment
            ):
                continue
            scope = self._entry_scope(key_id, obj)
            if scope is None:
                if global_entry is None:
                    global_entry = obj
            elif scope not in scoped:
                scoped[scope] = obj

        # Fast path for entries addressed by the id their writer constructed
        # but carrying no usable identity fields — the same anchor the core
        # resolver keeps. The id is what the writers build for these values.
        def _by_id(key_id):
            if not key_id:
                return None
            obj = self.api_keys.get(key_id)
            if obj is None or not getattr(obj, "is_active", True):
                return None
            return obj

        if tenant_id:
            own = scoped.get(str(tenant_id)) or _by_id(
                f"tenant_{tenant_id}_{provider_id}_{key_name}_{environment}"
            )
            if own is not None:
                return own
            return global_entry or _by_id(
                f"{provider_id}_{key_name}_{environment}")
        return global_entry or _by_id(f"{provider_id}_{key_name}_{environment}")

    def track_usage(self, tenant_id: str, provider_id: str, success: bool = True, tokens_used: int = 0):
        """Track provider usage for a specific tenant"""
        if not tenant_id:
            tenant_id = "default"
            
        if tenant_id not in self.usage_stats:
            self.usage_stats[tenant_id] = {}
            
        if provider_id not in self.usage_stats[tenant_id]:
            self.usage_stats[tenant_id][provider_id] = ProviderUsage(provider_id=provider_id)

        usage = self.usage_stats[tenant_id][provider_id]
        usage.total_requests += 1
        usage.last_used = datetime.now()

        if success:
            usage.successful_requests += 1
            usage.total_tokens_used += tokens_used

            # Calculate cost
            provider = self.providers.get(provider_id)
            if provider:
                usage.cost_accumulated += tokens_used * provider.cost_per_token
        else:
            usage.failed_requests += 1

    def get_tenant_usage(self, tenant_id: str) -> Dict[str, ProviderUsage]:
        """Get usage statistics for a specific tenant"""
        return self.usage_stats.get(tenant_id, {})

    def get_optimal_provider(
        self, task_type: str, budget_constraint: float = None, min_reasoning_level: int = 1
    ) -> Optional[str]:
        """Get the optimal provider for a given task type"""
        suitable_providers = []

        for provider_id, provider in self.providers.items():
            if not provider.is_active:
                continue

            if task_type in provider.supported_tasks:
                if provider.reasoning_level < min_reasoning_level:
                    continue

                if self.get_api_key(provider_id):
                    suitable_providers.append((provider_id, provider))

        if not suitable_providers:
            return None

        suitable_providers.sort(key=lambda x: x[1].cost_per_token)

        if budget_constraint is not None:
            suitable_providers = [
                p for p in suitable_providers if p[1].cost_per_token <= budget_constraint
            ]

        return suitable_providers[0][0] if suitable_providers else None

    def get_tenant_optimal_provider(
        self,
        tenant_id: str,
        task_type: str,
        budget_constraint: float = None,
        min_reasoning_level: int = 1,
        db: Session = None,
    ) -> Optional[str]:
        """Get the optimal provider for a given task type for a specific tenant (BYOK aware)"""
        suitable_providers = []

        for provider_id, provider in self.providers.items():
            if not provider.is_active:
                continue

            if task_type in provider.supported_tasks:
                if provider.reasoning_level < min_reasoning_level:
                    continue

                status = self.get_tenant_provider_status(tenant_id, provider_id, db=db)
                if status["has_api_keys"]:
                    suitable_providers.append((provider_id, provider))

        if not suitable_providers:
            return self.get_optimal_provider(
                task_type, budget_constraint, min_reasoning_level
            )

        suitable_providers.sort(key=lambda x: x[1].cost_per_token)

        if budget_constraint is not None:
            suitable_providers = [
                p for p in suitable_providers if p[1].cost_per_token <= budget_constraint
            ]

        return suitable_providers[0][0] if suitable_providers else None

    def get_provider_status(
        self, provider_id: str, tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive status for a provider (global status).

        ``tenant_id`` asks the question for a specific caller. Without it the
        answer is about GLOBAL keys only, which on a store whose every entry is
        tenant-scoped reads as "no keys configured" while the same provider
        resolves fine for its owner — the health summary said 0 of 37 providers
        had keys while the per-tenant endpoint reported all three configured
        (verified live 2026-09-16).
        """
        provider = self.providers.get(provider_id)
        usage = self.get_tenant_usage("global").get(
            provider_id, ProviderUsage(provider_id=provider_id)
        )
        has_keys = _is_usable_api_key(
            self.get_api_key(provider_id, tenant_id=tenant_id))

        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        return {
            "provider": asdict(provider),
            "usage": asdict(usage),
            "has_api_keys": has_keys,
            "status": "active" if provider.is_active and has_keys else "inactive",
        }

    def has_tenant_keys(self, tenant_id: str, db: Session = None) -> bool:
        """Check if a tenant has ANY API keys configured (self-provided only)."""
        # 1. Check tenant settings in DB if provided (SaaS parity mode only —
        # the file store is the single source of truth otherwise).
        if db and _db_key_sync_enabled():
            from core.models import TenantSetting
            # Check for keys like OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
            # These are the keys added by users in the Settings UI
            provider_keys = [f"{p_id.upper()}_API_KEY" for p_id in self.providers.keys()]
            count = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key.in_(provider_keys)
            ).count()
            if count > 0:
                return True
                
        # 2. Check BYOKManager's own tenant storage (memory cache/dynamic keys)
        prefix = f"tenant_{tenant_id}_"
        for k_id in self.api_keys.keys():
            if k_id.startswith(prefix):
                return True
            
        return False

    def get_tenant_provider_status(self, tenant_id: str, provider_id: str, db: Session = None) -> Dict[str, Any]:
        """Get comprehensive status for a provider for a specific tenant"""
        provider = self.providers.get(provider_id)
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")
            
        # Resolve the tenant's key value (DB mirror first under SaaS parity
        # mode, then the encrypted file store). Decryption is attempted so a
        # corrupted/legacy row counts as NOT configured instead of active.
        tenant_key = self.get_tenant_api_key(tenant_id, provider_id, db=db)
        has_tenant_key = _is_usable_api_key(tenant_key)

        # Overall status (has global key OR tenant key)
        has_keys = has_tenant_key or _is_usable_api_key(self.get_api_key(provider_id))
        
        usage = self.get_tenant_usage(tenant_id).get(provider_id, ProviderUsage(provider_id=provider_id))
        
        return {
            "provider": asdict(provider),
            "usage": asdict(usage),
            "has_api_keys": has_keys,
            "has_tenant_key": has_tenant_key,
            "status": "active" if provider.is_active and has_keys else "inactive",
        }

    def store_tenant_api_key(
        self,
        tenant_id: str,
        provider_id: str,
        api_key: str,
        key_name: str = "default",
        environment: str = "production",
        db: Session = None,
        label: Optional[str] = None,
    ) -> str:
        """Store an encrypted API key for a specific tenant (Syncs with DB).

        ``key_name`` is the LOOKUP IDENTITY (wizard and Settings both write
        the canonical ``"default"``); ``label`` is the friendly display name,
        persisted separately and never consulted by any resolver.
        """
        if provider_id not in self.providers:
            raise ValueError(f"Provider {provider_id} not found")

        # 1. Store in BYOKManager's own storage (JSON/encrypted)
        key_id = f"tenant_{tenant_id}_{provider_id}_{key_name}_{environment}"
        encrypted_key = self.encrypt_api_key(api_key)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        api_key_obj = APIKey(
            provider_id=provider_id,
            key_name=key_name,
            encrypted_key=encrypted_key,
            key_hash=key_hash,
            created_at=datetime.now(),
            environment=environment,
            tenant_id=tenant_id,
            label=sanitize_key_label(label),
        )

        self.api_keys[key_id] = api_key_obj
        self._save_configuration()
        _invalidate_provider_route_state(provider_id)

        # 2. Sync with tenant_settings table for frontend compatibility.
        # R81: store the Fernet-encrypted value, not the plaintext — the
        # tenant_settings table previously held raw credentials at rest.
        # SaaS-parity gated (single-tenant: the file store above is the only
        # source of truth; a second live copy produced split-brain keys).
        if db and _db_key_sync_enabled():
            setting_key = f"{provider_id.upper()}_API_KEY"
            setting = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key == setting_key
            ).first()

            encrypted_value = self.encrypt_api_key(api_key)
            if setting:
                setting.setting_value = encrypted_value
                setting.updated_at = datetime.now()
            else:
                new_setting = TenantSetting(
                    tenant_id=tenant_id,
                    setting_key=setting_key,
                    setting_value=encrypted_value,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(new_setting)
            db.commit()

        return key_id

    def get_tenant_api_key(
        self,
        tenant_id: str,
        provider_id: str,
        key_name: str = "default",
        environment: str = "production",
        db: Session = None
    ) -> Optional[str]:
        """Retrieve and decrypt an API key for a specific tenant.

        Source of truth is the manager's encrypted file store. The
        ``tenant_settings`` DB copy is consulted only in SaaS parity mode
        (:func:`_db_key_sync_enabled`) — keeping two live sources of truth
        in single-tenant deployments produced split-brain credentials.
        """

        # 1. SaaS parity mode: DB (tenant_settings) first.
        if db and _db_key_sync_enabled():
            setting_key = f"{provider_id.upper()}_API_KEY"
            setting = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key == setting_key
            ).first()
            if setting and setting.setting_value:
                try:
                    return self.decrypt_api_key(str(setting.setting_value))
                except Exception:
                    # Legacy rows written before R81 hold plaintext — keep
                    # them readable instead of bricking stored credentials.
                    return str(setting.setting_value)

        # 2. Fallback to BYOKManager storage — same identity-based resolver as
        # get_api_key, bound to this tenant's scope.
        api_key_obj = self._find_stored_key(
            provider_id, key_name, environment, tenant_id=tenant_id
        )

        if api_key_obj is None:
            return None

        # Update usage stats
        api_key_obj.last_used = datetime.now()
        api_key_obj.usage_count += 1

        try:
            decrypted_key = self.decrypt_api_key(api_key_obj.encrypted_key)
            return decrypted_key
        except Exception as e:
            logger.error(f"Failed to decrypt Tenant API key {provider_id}/{tenant_id}: {e}")
            return None


# Global BYOK Manager instance
_byok_manager = None


def get_byok_manager() -> BYOKManager:
    """Get the global BYOK manager instance"""
    global _byok_manager
    if _byok_manager is None:
        _byok_manager = BYOKManager()
    return _byok_manager


# API Router
router = APIRouter()

# API Endpoints

@router.get("/api/v1/byok/health")
async def byok_health(current_user: User = Depends(get_current_user)):
    """Health check for BYOK system"""
    return ApiResponse(success=True, data={
        "status": "healthy",
        "service": "BYOK Key Management",
        "timestamp": datetime.now().isoformat()
    })

@router.get("/api/ai/keys")
async def get_api_keys(
    current_user: User = Depends(get_current_user),
    byok_manager: BYOKManager = Depends(get_byok_manager),
):
    """Get all configured API keys (masked)"""
    keys = []
    for key_id, key_obj in byok_manager.api_keys.items():
        masked = None
        try:
            plain = byok_manager.decrypt_api_key(key_obj.encrypted_key)
            masked = f"{plain[:4]}...{plain[-4:]}" if len(plain) >= 8 else "***"
        except Exception:
            masked = f"{key_obj.key_hash[:4]}...{key_obj.key_hash[-4:]}"
        keys.append({
            "provider": key_obj.provider_id,
            "key_id": key_id,
            "key_name": key_obj.key_name,
            "label": getattr(key_obj, "label", None),
            "environment": key_obj.environment,
            "masked_key": masked,
            "status": "active" if key_obj.is_active else "inactive",
        })
    return ApiResponse(success=True, data={
        "keys": keys,
        "count": len(keys)
    })

@router.post("/api/ai/keys")
async def add_api_key(
    key_data: Dict[str, str],
    current_user: User = Depends(get_current_user),
    byok_manager: BYOKManager = Depends(get_byok_manager),
):
    """Add a new API key"""
    provider = key_data.get("provider")
    key = key_data.get("key")

    if not provider or not key:
        raise HTTPException(status_code=400, detail="Provider and key are required")

    if provider not in byok_manager.providers:
        raise HTTPException(status_code=400, detail=f"Provider {provider} not found")

    key_id = byok_manager.store_api_key(provider, key)
    _clear_provider_check(byok_manager, "global", provider)

    return ApiResponse(success=True, data={
        "status": "success",
        "message": f"API key for {provider} added successfully",
        "provider": provider,
        "key_id": key_id,
        "masked_key": f"{key[:4]}...{key[-4:]}"
    })

@router.get("/api/ai/providers")
async def get_ai_providers(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    byok_manager: BYOKManager = Depends(get_byok_manager),
    db: Session = Depends(get_db)
):
    """Get available AI providers with status for the current tenant"""
    providers_with_status = []

    for provider_id in byok_manager.providers:
        try:
            # Check if tenant has a specific key in DB first
            # We'll add a helper to byok_manager for this
            status = byok_manager.get_tenant_provider_status(tenant.id, provider_id, db=db)
            providers_with_status.append(status)
        except Exception as e:
            logger.error(f"Failed to get status for provider {provider_id} for tenant {tenant.id}: {e}")

    return ApiResponse(success=True, data={
        "providers": providers_with_status,
        "total_providers": len(providers_with_status),
        "active_providers": len(
            [p for p in providers_with_status if p["has_api_keys"]]
        ),
        "ai_mode": tenant.ai_mode
    })


@router.get("/api/ai/providers/{provider_id}")
async def get_ai_provider(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    byok_manager: BYOKManager = Depends(get_byok_manager),
    db: Session = Depends(get_db)
):
    """Get specific AI provider details"""
    try:
        status = byok_manager.get_tenant_provider_status(tenant.id, provider_id, db=db)
        return ApiResponse(success=True, data=status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Internal error")


_POLICY_ADMIN_ROLES = {
    UserRole.SUPER_ADMIN.value,
    UserRole.OWNER.value,
    UserRole.ADMIN.value,
    UserRole.WORKSPACE_ADMIN.value,
}


def _require_policy_admin(current_user: User = Depends(get_current_user)) -> User:
    role = getattr(current_user, "role", None)
    role_value = getattr(role, "value", role)
    if role_value not in _POLICY_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


@router.get("/api/ai/provider-policy")
async def get_provider_policy(
    current_user: User = Depends(get_current_user),
    byok_manager: BYOKManager = Depends(get_byok_manager),
):
    """Effective installation provider policy (credentials stay masked)."""
    from core.llm.provider_policy import resolve_provider_policy

    policy = resolve_provider_policy()
    return ApiResponse(success=True, data={
        "policy": policy.public_dict(),
        "providers": [
            {"id": pid, "name": getattr(prov, "name", pid)}
            for pid, prov in sorted(byok_manager.providers.items())
        ],
    })


@router.put("/api/ai/provider-policy")
async def update_provider_policy(
    payload: Dict[str, Any],
    admin: User = Depends(_require_policy_admin),
    byok_manager: BYOKManager = Depends(get_byok_manager),
    db: Session = Depends(get_db),
):
    """Save the installation policy. Env override is authoritative.

    The stored BYOK keys are never touched. A malformed or unknown-provider
    policy is rejected before persistence; an explicitly empty selected
    policy is accepted and means "no routes".
    """
    from core.llm.provider_policy import (
        PROVIDER_POLICY_KEY,
        ProviderPolicyError,
        resolve_provider_policy,
        validate_provider_policy,
    )
    from core.runtime_settings import invalidate_settings_cache

    if os.environ.get(PROVIDER_POLICY_KEY) is not None:
        raise HTTPException(
            status_code=409,
            detail=("Provider policy is managed by the installation "
                    "environment; conflicting UI saves are disabled."),
        )
    try:
        canonical = validate_provider_policy(
            payload, known_ids=set(byok_manager.providers.keys()))
    except ProviderPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    old_row = db.get(RuntimeSetting, PROVIDER_POLICY_KEY)
    old_value = old_row.value_json if old_row is not None else None
    try:
        if old_row is None:
            old_row = RuntimeSetting(
                key=PROVIDER_POLICY_KEY,
                value_json=canonical,
                updated_by=getattr(admin, "email", None),
            )
            db.add(old_row)
        else:
            old_row.value_json = canonical
            old_row.updated_by = getattr(admin, "email", None)
        db.add(SettingChangeAudit(
            setting_key=PROVIDER_POLICY_KEY,
            old_value_json=old_value,
            new_value_json=canonical,
            changed_by=getattr(admin, "email", None),
        ))
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("provider policy write failed: %s", exc)
        raise HTTPException(status_code=500, detail="Policy write failed") from exc

    invalidate_settings_cache()
    # Re-resolve from the persisted row (not from the request) so the
    # response is the effective value, including any operator env override.
    policy = resolve_provider_policy()
    return ApiResponse(success=True, data={
        "policy": policy.public_dict(),
        "providers": [
            {"id": pid, "name": getattr(prov, "name", pid)}
            for pid, prov in sorted(byok_manager.providers.items())
        ],
    })


def _classify_probe_error(exc: BaseException) -> tuple[str, str]:
    """Turn a provider probe failure into an honest, actionable class."""
    text = f"{type(exc).__name__} {exc}".lower()
    if any(k in text for k in ("401", "403", "unauthorized", "forbidden",
                               "invalid api key", "authentication", "auth")):
        return "authentication_failed", "The provider rejected the saved credential."
    if any(k in text for k in ("429", "rate limit", "quota", "credit",
                               "billing", "insufficient", "402")):
        return "usage_limit", "The provider reports a rate, quota, or billing limit."
    if any(k in text for k in ("timeout", "timed out", "connect", "network",
                               "dns", "unreachable")):
        return "unavailable", "The provider could not be reached from this installation."
    return "unavailable", "The provider probe did not complete successfully."


@router.post("/api/ai/providers/{provider_id}/test")
async def test_provider_key(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    byok_manager: BYOKManager = Depends(get_byok_manager),
    db: Session = Depends(get_db)
):
    """Run one bounded models-list probe and record its actual result.

    A saved key is not a successful inference test. The response and the
    process-local ``last_check_*`` usage fields distinguish authentication,
    quota/rate, network-unavailable, and successful checks with a timestamp
    (a restart honestly reports "not checked").
    The probe is only run when the operator clicks Test; page loads do not
    probe every configured provider.
    """
    import asyncio
    from datetime import datetime, timezone
    from starlette.concurrency import run_in_threadpool

    usage_map = byok_manager.get_tenant_usage(tenant.id)
    usage = usage_map.get(provider_id)
    if usage is None:
        usage = ProviderUsage(provider_id=provider_id)
        usage_map[provider_id] = usage
    provider = byok_manager.providers.get(provider_id)
    model = str(getattr(provider, "model", "") or "")
    started = datetime.now(timezone.utc)
    result: Dict[str, Any]
    try:
        def _probe() -> Dict[str, Any]:
            from core.llm.byok_handler import BYOKHandler

            handler = BYOKHandler(
                workspace_id=getattr(current_user, "workspace_id", None) or "default",
                tenant_id=tenant.id,
                user_id=getattr(current_user, "id", None),
            )
            client = handler.clients.get(provider_id)
            if client is None:
                raise RuntimeError("provider_not_configured")
            models = client.models.list()
            return {
                "ok": True,
                "sample_models": [
                    m.id for m in getattr(models, "data", [])][:5],
            }

        # Bound the check at the HTTP boundary. The thread may finish later
        # (the SDK call is not cancellable here) but the UI/API cannot hang
        # indefinitely on an unresponsive provider.
        result = await asyncio.wait_for(
            run_in_threadpool(_probe), timeout=20.0)
        status = "ready"
        message = ("Provider answered a bounded models-list check "
                   "(catalogue-level, not an inference test).")
        ok = True
    except Exception as exc:  # noqa: BLE001 — probe boundary
        logger.warning("Provider key test failed for %s: %s", provider_id, exc)
        status, message = _classify_probe_error(exc)
        result = {"ok": False, "status": status, "message": message}
        ok = False

    checked_at = datetime.now(timezone.utc)
    usage.last_check_at = checked_at
    usage.last_check_ok = ok
    usage.last_check_status = status
    usage.last_check_message = message
    usage.last_check_provider = provider_id
    usage.last_check_model = model
    usage.last_check_latency_ms = int(
        (checked_at - started).total_seconds() * 1000)
    return ApiResponse(
        success=ok,
        data={
            **result,
            "provider": provider_id,
            "model": model,
            "checked_at": checked_at.isoformat(),
            "latency_ms": usage.last_check_latency_ms,
        },
        message=message,
    )


@router.post("/api/ai/providers/{provider_id}/keys")
async def store_api_key(
    provider_id: str,
    api_key: Optional[str] = Query(None),
    key_name: str = "default",
    environment: str = "production",
    label: Optional[str] = Query(None),
    body: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    byok_manager: BYOKManager = Depends(get_byok_manager),
    db: Session = Depends(get_db)
):
    """Store an API key for a provider (tenant-specific).

    R83: accept BOTH contracts — the legacy query-param form and the JSON
    body form the frontend actually sends ({api_key, key_name, environment}).
    Body-only callers previously got a guaranteed 422 (query param missing),
    dead-ending onboarding step 1 on both the wizard and Settings→AI.

    F4 (2026-10-17): ``key_name`` is the LOOKUP IDENTITY and both the wizard
    and Settings→AI now write the canonical ``"default"``. The friendly label
    ("Ollama (local)", "<provider> (onboarding)") is a separate display-only
    field with no role in resolution: the resolver is unchanged, and existing
    keys stored under other key names keep working exactly as before.
    """
    if body and isinstance(body, dict):
        api_key = api_key or body.get("api_key")
        key_name = body.get("key_name") or key_name
        environment = body.get("environment") or environment
        label = body.get("label") or label
    if not api_key or len(api_key) < 10:
        raise HTTPException(
            status_code=422,
            detail="Invalid API key: must be at least 10 characters"
        )
    try:
        key_id = byok_manager.store_tenant_api_key(
            tenant.id, provider_id, api_key, key_name, environment,
            db=db, label=label)
        _clear_provider_check(byok_manager, tenant.id, provider_id)
        return ApiResponse(success=True, data={
            "key_id": key_id,
            "message": f"API key stored successfully for {provider_id} in {tenant.name}",
        })
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Internal error")
    except Exception as e:
        logger.error(f"Failed to store API key: {e}")
        raise HTTPException(
            status_code=500, detail="Internal error"
        )


@router.get("/api/ai/providers/{provider_id}/keys/{key_name}")
async def get_api_key_status(
    provider_id: str,
    key_name: str = "default",
    environment: str = "production",
    current_user: User = Depends(get_current_user),
    byok_manager: BYOKManager = Depends(get_byok_manager),
):
    """Get status of an API key (without revealing the key)"""
    key_id = f"{provider_id}_{key_name}_{environment}"

    if key_id not in byok_manager.api_keys:
        raise HTTPException(status_code=404, detail="API key not found")

    key_info = byok_manager.api_keys[key_id]

    return ApiResponse(success=True, data={
        "key_id": key_id,
        "provider_id": key_info.provider_id,
        "key_name": key_info.key_name,
        "label": getattr(key_info, "label", None),
        "environment": key_info.environment,
        "is_active": key_info.is_active,
        "usage_count": key_info.usage_count,
        "created_at": key_info.created_at,
        "last_used": key_info.last_used,
        "has_key": True,
    })


@router.delete("/api/ai/providers/{provider_id}/keys/{key_name}")
async def delete_api_key(
    provider_id: str,
    key_name: str = "default",
    environment: str = "production",
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    byok_manager: BYOKManager = Depends(get_byok_manager),
    db: Session = Depends(get_db),
):
    """Delete an API key — across ALL the stores it may live in.

    A provider's key can exist in three places (see store_tenant_api_key):
    the manager's file store under a GLOBAL id (``{provider}_{key}_{env}``),
    under TENANT-scoped ids (``tenant_{tenant}_{provider}_{key}_{env}``), and
    synced into the ``tenant_settings`` table. The previous implementation
    only removed the exact global id, so wizard/Settings-saved keys (custom
    key_names, tenant-scoped, DB-synced) were undeletable from the UI — the
    404 here, then the provider still showing "configured" from the DB row.

    Semantics: an exact key_name match (including ``default``) removes that
    named key everywhere it lives.
    """
    key_id = f"{provider_id}_{key_name}_{environment}"
    tenant_prefix = f"tenant_{tenant.id}_{provider_id}_"

    removed: list = []

    # 1. Manager file store — exact global id, then any tenant-scoped row
    # for this provider+key_name+environment.
    if key_id in byok_manager.api_keys:
        del byok_manager.api_keys[key_id]
        removed.append(key_id)
    suffix = f"_{key_name}_{environment}"
    for row_id in list(byok_manager.api_keys.keys()):
        if row_id.startswith(tenant_prefix) and row_id.endswith(suffix):
            del byok_manager.api_keys[row_id]
            removed.append(row_id)
    byok_manager._save_configuration()

    # 2. DB sync (tenant_settings) — same row store_tenant_api_key writes.
    try:
        setting_key = f"{provider_id.upper()}_API_KEY"
        setting = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant.id,
            TenantSetting.setting_key == setting_key,
        ).first()
        if setting:
            db.delete(setting)
            db.commit()
            removed.append(f"tenant_settings:{setting_key}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete {provider_id} key from tenant_settings: {e}")

    if not removed:
        raise HTTPException(status_code=404, detail="API key not found")

    # Deleting a key changes what this provider can do: drop any cached
    # cooldown/catalogue so the next turn re-evaluates instead of serving a
    # stale verdict about a credential that no longer exists.
    _invalidate_provider_route_state(provider_id)
    _clear_provider_check(byok_manager, tenant.id, provider_id)

    return ApiResponse(success=True, message=f"API key {provider_id}/{key_name} deleted", data={"removed": removed})


@router.post("/api/ai/optimize-cost")
async def optimize_cost_usage(
    usage_data: Dict[Any, Any], current_user: User = Depends(get_current_user), byok_manager: BYOKManager = Depends(get_byok_manager)
):
    """Optimize AI cost usage and recommend providers"""
    task_type = usage_data.get("task_type", "general")
    budget_constraint = usage_data.get("budget_constraint")
    estimated_tokens = usage_data.get("estimated_tokens", 1000)

    try:
        optimal_provider = byok_manager.get_optimal_provider(
            task_type, budget_constraint
        )

        if not optimal_provider:
            raise HTTPException(
                status_code=400,
                detail=f"No suitable providers found for task type: {task_type}",
            )

        provider = byok_manager.providers[optimal_provider]
        estimated_cost = estimated_tokens * provider.cost_per_token

        # Get alternative providers for comparison
        alternatives = []
        for provider_id, alt_provider in byok_manager.providers.items():
            if (
                provider_id != optimal_provider
                and task_type in alt_provider.supported_tasks
                and byok_manager.get_api_key(provider_id)
            ):
                alt_cost = estimated_tokens * alt_provider.cost_per_token
                alternatives.append(
                    {
                        "provider_id": provider_id,
                        "name": alt_provider.name,
                        "estimated_cost": alt_cost,
                        "cost_per_token": alt_provider.cost_per_token,
                    }
                )

        return ApiResponse(success=True, data={
            "recommended_provider": optimal_provider,
            "provider_name": provider.name,
            "estimated_cost": estimated_cost,
            "estimated_tokens": estimated_tokens,
            "cost_per_token": provider.cost_per_token,
            "alternatives": sorted(alternatives, key=lambda x: x["estimated_cost"]),
            "reason": f"Most cost-effective for {task_type} tasks",
        })

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Internal error")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal error")


@router.post("/api/ai/usage/track")
async def track_ai_usage(
    usage_data: Dict[Any, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    byok_manager: BYOKManager = Depends(get_byok_manager),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Track AI usage for cost monitoring"""
    provider_id = usage_data.get("provider_id")
    success = usage_data.get("success", True)
    tokens_used = usage_data.get("tokens_used", 0)

    if not provider_id:
        raise HTTPException(status_code=400, detail="provider_id is required")

    try:
        # Track usage in background to avoid blocking
        background_tasks.add_task(
            byok_manager.track_usage, tenant.id, provider_id, success, tokens_used
        )

        return ApiResponse(success=True, message=f"Usage tracked for {provider_id}", data={"tokens_used": tokens_used})

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/api/ai/usage/stats")
async def get_usage_stats(
    tenant_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    provider_id: Optional[str] = None,
    byok_manager: BYOKManager = Depends(get_byok_manager),
):
    """Get usage statistics for AI providers"""
    try:
        stats = byok_manager.usage_stats
        
        if tenant_id:
            if tenant_id not in stats:
                return ApiResponse(success=True, data={"total_providers": 0, "usage_stats": {}})
            tenant_stats = stats[tenant_id]
            if provider_id:
                if provider_id not in tenant_stats:
                    raise HTTPException(status_code=404, detail=f"No usage data for {provider_id}")
                return ApiResponse(success=True, data={"tenant_id": tenant_id, "provider_id": provider_id, "usage": asdict(tenant_stats[provider_id])})
            return ApiResponse(success=True, data={"tenant_id": tenant_id, "usage_stats": {pid: asdict(u) for pid, u in tenant_stats.items()}})
        
        all_stats = {}
        for tid, t_stats in stats.items():
            all_stats[tid] = {pid: asdict(u) for pid, u in t_stats.items()}
            
        return ApiResponse(success=True, data={"total_tenants": len(all_stats), "usage_stats": all_stats})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal error"
        )


@router.get("/api/ai/usage/calls")
async def get_llm_usage_calls(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
):
    """Per-call LLM provider usage logs (all providers incl. opencode-go).

    Returns recent call records (timestamp, provider, model, success,
    latency_ms, input_tokens, output_tokens, fallback, fallback_provider,
    error) from the in-memory call tracker plus an aggregated summary,
    optionally filtered by provider/model.
    """
    try:
        from core.llm_call_tracker import get_llm_call_tracker

        tracker = get_llm_call_tracker()
        n = max(1, min(int(limit or 100), 1000))
        calls = tracker.get_recent_calls(provider=provider, model=model, limit=n)
        summary = tracker.get_summary(provider=provider, model=model)
        return ApiResponse(
            success=True,
            data={
                "calls": [asdict(c) for c in calls],
                "summary": summary,
            },
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error")


# PDF-specific BYOK endpoints


@router.get("/api/ai/pdf/providers")
async def get_pdf_ai_providers(current_user: User = Depends(get_current_user), byok_manager: BYOKManager = Depends(get_byok_manager)):
    """Get AI providers specifically for PDF processing tasks"""
    pdf_providers = []

    for provider_id, provider in byok_manager.providers.items():
        pdf_tasks = [
            "pdf_ocr",
            "image_comprehension",
            "document_processing",
            "multimodal",
        ]
        has_pdf_capabilities = any(
            task in provider.supported_tasks for task in pdf_tasks
        )

        if has_pdf_capabilities and provider.is_active:
            status = byok_manager.get_provider_status(provider_id)
            pdf_providers.append(status)

    return ApiResponse(success=True, data={
        "pdf_providers": pdf_providers,
        "total_pdf_providers": len(pdf_providers),
        "supported_tasks": [
            "pdf_ocr",
            "image_comprehension",
            "document_processing",
            "multimodal",
        ],
    })


@router.post("/api/ai/pdf/optimize")
async def optimize_pdf_processing(
    pdf_characteristics: Dict[Any, Any],
    current_user: User = Depends(get_current_user),
    byok_manager: BYOKManager = Depends(get_byok_manager),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Optimize AI provider selection for PDF processing"""
    pdf_type = pdf_characteristics.get(
        "pdf_type", "searchable"
    )  # searchable, scanned, mixed
    needs_ocr = pdf_characteristics.get("needs_ocr", False)
    needs_image_comprehension = pdf_characteristics.get(
        "needs_image_comprehension", False
    )
    estimated_pages = pdf_characteristics.get("estimated_pages", 10)
    budget_constraint = pdf_characteristics.get("budget_constraint")

    # Determine task type based on PDF characteristics
    if needs_image_comprehension:
        task_type = "image_comprehension"
    elif needs_ocr:
        task_type = "pdf_ocr"
    else:
        task_type = "document_processing"

    # Estimate tokens (rough calculation)
    estimated_tokens = estimated_pages * 500  # ~500 tokens per page

    try:
        optimal_provider = byok_manager.get_tenant_optimal_provider(
            tenant.id, task_type, budget_constraint, db=db
        )

        if not optimal_provider:
            raise HTTPException(
                status_code=400,
                detail=f"No suitable providers found for PDF processing task: {task_type}",
            )

        provider = byok_manager.providers[optimal_provider]
        estimated_cost = estimated_tokens * provider.cost_per_token

        # Get provider recommendations for different scenarios
        scenarios = {}

        # High quality scenario
        try:
            high_quality_provider = byok_manager.get_tenant_optimal_provider(
                tenant.id, "image_comprehension", db=db
            )
            if high_quality_provider:
                hq_provider = byok_manager.providers[high_quality_provider]
                scenarios["high_quality"] = {
                    "provider": high_quality_provider,
                    "name": hq_provider.name,
                    "estimated_cost": estimated_tokens * hq_provider.cost_per_token,
                    "recommended_for": "Complex PDFs with images and diagrams",
                }
        except Exception as e:
            logger.warning(f"Failed to get high quality OCR provider: {e}")

        # Cost-effective scenario
        try:
            cost_effective_provider = byok_manager.get_tenant_optimal_provider(
                tenant.id, "pdf_ocr", 0.001, db=db
            )  # Max $0.001 per token
            if cost_effective_provider:
                ce_provider = byok_manager.providers[cost_effective_provider]
                scenarios["cost_effective"] = {
                    "provider": cost_effective_provider,
                    "name": ce_provider.name,
                    "estimated_cost": estimated_tokens * ce_provider.cost_per_token,
                    "recommended_for": "Simple OCR tasks on scanned documents",
                }
        except Exception as e:
            logger.warning(f"Failed to get cost effective OCR provider: {e}")

        return ApiResponse(success=True, data={
            "pdf_analysis": {
                "pdf_type": pdf_type,
                "needs_ocr": needs_ocr,
                "needs_image_comprehension": needs_image_comprehension,
                "estimated_pages": estimated_pages,
                "estimated_tokens": estimated_tokens,
            },
            "recommended_provider": {
                "provider_id": optimal_provider,
                "name": provider.name,
                "task_type": task_type,
                "estimated_cost": estimated_cost,
                "cost_per_token": provider.cost_per_token,
            },
            "alternative_scenarios": scenarios,
            "optimization_reason": f"Optimal for {pdf_type} PDF with {task_type} requirements",
        })

    except ValueError as e:
        raise HTTPException(status_code=400, detail="Internal error")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal error"
        )


@router.get("/api/ai/health")
async def byok_health_check(current_user: User = Depends(get_current_user), byok_manager: BYOKManager = Depends(get_byok_manager)):
    """Health check for BYOK system.

    Counts keys for the CALLER's scope, not global-only: on a single-operator
    install every stored key is tenant-prefixed, so a global-only count
    reported ``with_keys: 0`` for a system that resolves three providers.
    """
    try:
        from core.personal_scope import resolve_tenant_id

        tenant_id = resolve_tenant_id(current_user)
        active_providers = 0
        providers_with_keys = 0

        for provider_id in byok_manager.providers:
            status = byok_manager.get_provider_status(
                provider_id, tenant_id=tenant_id)
            if status["status"] == "active":
                active_providers += 1
            if status["has_api_keys"]:
                providers_with_keys += 1

        total_usage = sum(
            u.total_requests
            for t_stats in byok_manager.usage_stats.values()
            for u in t_stats.values()
        )
        total_cost = sum(
            u.cost_accumulated
            for t_stats in byok_manager.usage_stats.values()
            for u in t_stats.values()
        )

        return ApiResponse(success=True, data={
            "system": "BYOK AI Provider Management",
            "providers": {
                "total": len(byok_manager.providers),
                "active": active_providers,
                "with_keys": providers_with_keys,
            },
            "usage": {
                "total_requests": total_usage,
                "total_cost": total_cost,
                "providers_tracked": len(byok_manager.usage_stats),
            },
            "storage": {
                "config_file": BYOK_CONFIG_FILE,
                "keys_file": BYOK_KEYS_FILE,
                "encryption_enabled": True,
            },
        })

    except Exception as e:
        raise HTTPException(status_code=503, detail="Internal error")


# Backward compatibility endpoints for /api/v1/byok/*
@router.get("/api/v1/byok/health")
async def byok_health_v1(current_user: User = Depends(get_current_user), byok_manager: BYOKManager = Depends(get_byok_manager)):
    """Health check endpoint for BYOK system (v1 API compatibility)"""
    return await byok_health_check(current_user=current_user, byok_manager=byok_manager)


# Dynamic Pricing Endpoints

@router.get("/api/ai/pricing")
async def get_ai_pricing(current_user: User = Depends(get_current_user)):
    """Get current AI model pricing from cache"""
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        fetcher = get_pricing_fetcher()
        
        return ApiResponse(success=True, data={
            "model_count": len(fetcher.pricing_cache),
            "last_updated": fetcher.last_fetch.isoformat() if fetcher.last_fetch else None,
            "cache_valid": fetcher._is_cache_valid(),
            "cheapest_models": fetcher.get_cheapest_models(5),
            "provider_comparison": fetcher.compare_providers()
        })
    except Exception as e:
        logger.error(f"Failed to get pricing: {e}")
        return ApiResponse(success=False, message="Failed to get pricing")


@router.post("/api/ai/pricing/refresh")
async def refresh_ai_pricing(force: bool = False, current_user: User = Depends(get_current_user)):
    """Refresh AI pricing from LiteLLM and OpenRouter"""
    try:
        from core.dynamic_pricing_fetcher import refresh_pricing_cache
        pricing = await refresh_pricing_cache(force=force)
        
        return ApiResponse(success=True, message="Pricing data refreshed successfully", data={
            "models_fetched": len(pricing)
        })
    except Exception as e:
        logger.error(f"Failed to refresh pricing: {e}")
        return ApiResponse(success=False, message="Failed to refresh pricing")


@router.get("/api/ai/pricing/staleness-stats")
async def get_pricing_staleness_stats(current_user: User = Depends(get_current_user)):
    """Phase M measurement gate: cache staleness + availability-diff stats.

    Numbers here decide whether the server-side OpenRouter query-param
    candidate path is ever built (plan v2 Phases 1–3) — see
    docs/testing/TESTED_FILES_TRACKER.md.
    """
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        return ApiResponse(success=True, data=get_pricing_fetcher().staleness_summary())
    except Exception as e:
        logger.error(f"Failed to get staleness stats: {e}")
        return ApiResponse(success=False, message="Failed to get staleness stats")


@router.get("/api/ai/pricing/model/{model_name:path}")
async def get_model_pricing(model_name: str, current_user: User = Depends(get_current_user)):
    """Get pricing for a specific model"""
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        fetcher = get_pricing_fetcher()
        
        pricing = fetcher.get_model_price(model_name)
        if pricing:
            return ApiResponse(success=True, data={
                "model": model_name,
                "pricing": pricing
            })
        else:
            return ApiResponse(success=False, message="Model pricing not found. Try refreshing the cache.", data={
                "model": model_name
            })
    except Exception as e:
        logger.error(f"Failed to get model pricing: {e}")
        return ApiResponse(success=False, message="Failed to get model pricing")


@router.get("/api/ai/pricing/provider/{provider}")
async def get_provider_pricing(provider: str, limit: int = 10, current_user: User = Depends(get_current_user)):
    """Get all models and pricing for a specific provider"""
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        fetcher = get_pricing_fetcher()
        
        models = fetcher.get_provider_models(provider)[:limit]
        
        return ApiResponse(success=True, data={
            "provider": provider,
            "model_count": len(models),
            "models": models
        })
    except Exception as e:
        logger.error(f"Failed to get provider pricing: {e}")
        return ApiResponse(success=False, message="Failed to get provider pricing")


@router.post("/api/ai/pricing/estimate")
async def estimate_request_cost(request_data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    """Estimate the cost of an AI request"""
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        fetcher = get_pricing_fetcher()
        
        model = request_data.get("model", "gpt-4o-mini")
        input_tokens = request_data.get("input_tokens", 0)
        output_tokens = request_data.get("output_tokens", 500)
        
        # If prompt provided, estimate tokens
        prompt = request_data.get("prompt")
        if prompt and not input_tokens:
            input_tokens = len(prompt) // 4  # Rough token estimate
        
        estimated_cost = fetcher.estimate_cost(model, input_tokens, output_tokens)
        
        if estimated_cost is not None:
            return ApiResponse(success=True, data={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": estimated_cost
            })
        else:
            # Try to find similar model
            pricing = fetcher.get_model_price(model)
            if pricing:
                input_cost = pricing.get("input_cost_per_token", 0) * input_tokens
                output_cost = pricing.get("output_cost_per_token", 0) * output_tokens
                return ApiResponse(success=True, data={
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "estimated_cost_usd": input_cost + output_cost
                })
            
            return ApiResponse(success=False, message="Model pricing not found. Refresh pricing cache.", data={
                "model": model
            })
    except Exception as e:
        logger.error(f"Failed to estimate cost: {e}")
        return ApiResponse(success=False, message="Failed to estimate cost")
