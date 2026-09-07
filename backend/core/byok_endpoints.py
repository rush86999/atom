from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import json
import logging
import os
import tempfile
import secrets
import threading
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# DEAD-ROUTE REMOVAL (2026-08-28): this module previously ALSO registered a
# parallel set of /api/ai/* routes via `router`. That router was never mounted
# ("byok" is absent from ESSENTIAL_API_ROUTERS), but the lazy registry mapped
# "byok" here — an on-demand load would have silently double-registered
# global-store routes beside api/byok_routes.py's tenant-store routes (the
# two-source-of-truth landmine behind the BYOK incidents of 2026-08-28).
# The routes live ONLY in api/byok_routes.py now; this module is the manager
# + singleton shared by byok_handler / mcp_service / workflow code.

from cryptography.fernet import Fernet
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# Request Models for API Key Submission (Security: POST body instead of query params)
class AddAPIKeyRequest(BaseModel):
    """

DEAD-ROUTE REMOVAL (2026-08-28): this module previously ALSO registered a
parallel set of /api/ai/* routes via `router`. That router was never mounted
(byok is absent from ESSENTIAL_API_ROUTERS), but the lazy registry mapped
"byok" here — an on-demand load would have silently double-registered
global-store routes beside api/byok_routes.py's tenant-store routes (the
two-source-of-truth landmine behind the BYOK incidents of 2026-08-28).
The routes live ONLY in api/byok_routes.py now; this module is the
manager + singleton, which byok_handler / mcp_service / workflow code share.Secure API key submission via POST body"""
    api_key: str = Field(..., min_length=10, description="API key string")
    key_name: str = Field(default="default", max_length=100, description="Key identifier")

    @field_validator('key_name')
    @classmethod
    def validate_key_name(cls, v: str) -> str:
        if v and not v.replace('_', '').isalnum():
            raise ValueError("key_name must be alphanumeric with underscores only")
        return v

# BYOK Configuration Storage
# Anchored to <backend>/data regardless of the launch CWD — must match
# api/byok_routes (see the rationale there). BYOK_* env vars override.
BYOK_CONFIG_FILE = os.getenv("BYOK_CONFIG_FILE") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
    "byok_config.json"
)
BYOK_KEYS_FILE = os.getenv("BYOK_KEYS_FILE") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
    "byok_keys.json"
)
# R61: the runtime manager must share the SAME persisted Fernet key as the
# admin manager (api/byok_routes) — otherwise keys stored via the admin API
# are undecryptable by the LLM runtime, and every restart bricks stored keys.
BYOK_ENC_KEY_FILE = os.getenv("BYOK_ENC_KEY_FILE") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
    "byok_encryption_key"
)


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
    supports_vision: bool = False
    supports_tools: bool = False
    supports_cache: bool = False
    supports_structured_output: bool = False
    reasoning_level: int = 1  # 1=Low, 2=Medium, 3=High, 4=Very High
    quality_score: float = 0.0
    max_requests_per_minute: int = 60
    rate_limit_window: int = 60
    is_active: bool = True
    requires_encryption: bool = True

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


class BYOKManager:
    """BYOK (Bring Your Own Key) Management System"""

    def __init__(self):
        self.providers: Dict[str, AIProviderConfig] = {}
        self.usage_stats: Dict[str, ProviderUsage] = {}
        self.api_keys: Dict[str, APIKey] = {}
        # R61: env override wins; otherwise reuse the persisted key (same file
        # as the admin manager) so stored ciphertext survives restarts and is
        # shared across both managers.
        self.encryption_key = os.getenv("BYOK_ENCRYPTION_KEY")
        if not self.encryption_key:
            self.encryption_key = self._load_or_create_encryption_key()
        else:
            # Keep the persisted file in sync with the env override so keys
            # survive even if .env is later lost or regenerated (see mirror).
            self._mirror_encryption_key_file(self.encryption_key)
        self._load_configuration()
        self._initialize_default_providers()

    def _load_configuration(self):
        """Load configuration from disk"""
        # Load providers
        # TOCTOU FIX: Use try-except instead of exists check
        try:
            with open(BYOK_CONFIG_FILE, "r") as f:
                data = json.load(f)
                from dataclasses import fields
                provider_fields = {f.name for f in fields(AIProviderConfig)}
                for p_data in data.get("providers", []):
                    # Filter to only valid fields for AIProviderConfig
                    p_data_filtered = {k: v for k, v in p_data.items() if k in provider_fields}
                    provider = AIProviderConfig(**p_data_filtered)
                    self.providers[provider.id] = provider
        except FileNotFoundError:
            # Config file doesn't exist yet, start empty
            logger.debug(f"BYOK config file not found: {BYOK_CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to load BYOK config: {e}")

        # Load API keys
        # TOCTOU FIX: Use try-except instead of exists check
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

                    # Filter to only valid fields for APIKey
                    k_data_filtered = {k: v for k, v in k_data.items() if k in key_fields}
                    api_key = APIKey(**k_data_filtered)
                    self.api_keys[k_id] = api_key
        except FileNotFoundError:
            # Keys file doesn't exist yet, start empty
            logger.debug(f"BYOK keys file not found: {BYOK_KEYS_FILE}")
        except Exception as e:
            logger.error(f"Failed to load BYOK keys: {e}")

    def _save_configuration(self):
        """Save configuration to disk"""
        # Ensure data directory exists
        os.makedirs(os.path.dirname(BYOK_CONFIG_FILE), exist_ok=True)
        
        # Save providers
        try:
            self._atomic_write_json(
                BYOK_CONFIG_FILE,
                {"providers": [self._provider_to_dict(p) for p in self.providers.values()]},
            )
        except Exception as e:
            logger.error(f"Failed to save BYOK config: {e}")

        # Save API keys
        try:
            keys_data = {
                k_id: self._api_key_to_dict(k_obj)
                for k_id, k_obj in self.api_keys.items()
                if isinstance(k_obj, APIKey)
            }
            self._atomic_write_json(BYOK_KEYS_FILE, {"keys": keys_data})
        except Exception as e:
            logger.error(f"Failed to save BYOK keys: {e}")

    @staticmethod
    def _provider_to_dict(provider: AIProviderConfig) -> Dict[str, Any]:
        return {
            "id": provider.id,
            "name": provider.name,
            "description": provider.description,
            "api_key_env_var": provider.api_key_env_var,
            "base_url": provider.base_url,
            "model": provider.model,
            "cost_per_token": provider.cost_per_token,
            "supported_tasks": list(provider.supported_tasks or []),
            "supports_vision": provider.supports_vision,
            "supports_tools": provider.supports_tools,
            "supports_cache": provider.supports_cache,
            "supports_structured_output": provider.supports_structured_output,
            "reasoning_level": provider.reasoning_level,
            "quality_score": provider.quality_score,
            "max_requests_per_minute": provider.max_requests_per_minute,
            "rate_limit_window": provider.rate_limit_window,
            "is_active": provider.is_active,
            "requires_encryption": provider.requires_encryption,
        }

    @staticmethod
    def _api_key_to_dict(api_key: APIKey) -> Dict[str, Any]:
        return {
            "provider_id": api_key.provider_id,
            "key_name": api_key.key_name,
            "encrypted_key": api_key.encrypted_key,
            "key_hash": api_key.key_hash,
            "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
            "last_used": api_key.last_used.isoformat() if api_key.last_used else None,
            "is_active": api_key.is_active,
            "usage_count": api_key.usage_count,
            "environment": api_key.environment,
        }

    @staticmethod
    def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
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
        # Optimized provider list based on 2025 Architecture Report
        defaults = [
            AIProviderConfig(
                id="deepseek",
                name="DeepSeek V3",
                description="Commoditized Intelligence (Reasoning Engine)",
                api_key_env_var="DEEPSEEK_API_KEY",
                base_url="https://api.deepseek.com/v1",
                supported_tasks=["general", "chat", "code", "analysis", "reasoning", "vision"],
                cost_per_token=0.00000014, # ~$0.14 per million tokens
                model="deepseek-chat",
                reasoning_level=4, # High reasoning capability
                supports_structured_output=True # Via OpenAI compat + instructor
            ),
            AIProviderConfig(
                id="openai",
                name="OpenAI",
                description="GPT-4 and GPT-3.5 models",
                api_key_env_var="OPENAI_API_KEY",
                supported_tasks=["general", "chat", "code", "analysis", "vision", "reasoning"],
                cost_per_token=0.00003, # ~$30 per million
                model="gpt-4o",
                reasoning_level=3,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="anthropic",
                name="Anthropic",
                description="Claude 3 Opus, Sonnet, and Haiku",
                api_key_env_var="ANTHROPIC_API_KEY",
                supported_tasks=["general", "chat", "code", "analysis", "writing", "vision", "reasoning"],
                cost_per_token=0.000015,
                model="claude-3-5-sonnet-20241022",
                reasoning_level=3,
                supports_structured_output=True # Via tool use / instructor
            ),
            AIProviderConfig(
                id="groq",
                name="Groq (Llama 3)",
                description="Ultra-fast Llama 3.3/3.1 inference",
                api_key_env_var="GROQ_API_KEY",
                base_url="https://api.groq.com/openai/v1",
                supported_tasks=["general", "chat", "code", "analysis", "realtime"],
                cost_per_token=0.0000008, # Very cheap
                model="llama-3.1-70b-versatile", # Update to 3.3 if available
                reasoning_level=3,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="google",
                name="Google Gemini",
                description="Gemini 1.5 Pro",
                api_key_env_var="GOOGLE_API_KEY",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                supported_tasks=["general", "chat", "code", "analysis", "multimodal", "vision", "reasoning"],
                cost_per_token=0.0000125,
                model="gemini-1.5-pro",
                reasoning_level=3,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="google_flash",
                name="Google Gemini Flash",
                description="Gemini 1.5 Flash - High Speed",
                api_key_env_var="GOOGLE_API_KEY",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                supported_tasks=["general", "chat", "summary", "extraction", "vision", "pdf_ocr"],
                cost_per_token=0.0000005,
                model="gemini-1.5-flash",
                reasoning_level=2,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="google_flash_3_5",
                name="Google Gemini 3.5 Flash",
                description="Gemini 3.5 Flash - Ultra High Speed",
                api_key_env_var="GOOGLE_API_KEY",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                supported_tasks=["general", "chat", "summary", "extraction", "vision", "pdf_ocr"],
                cost_per_token=0.0000003,
                model="gemini-3.5-flash",
                reasoning_level=3,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="gemini",
                name="Google Gemini",
                description="Gemini 1.5 Pro (OpenAI-compatible)",
                api_key_env_var="GOOGLE_API_KEY",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                supported_tasks=["general", "chat", "code", "analysis", "multimodal", "vision", "reasoning"],
                cost_per_token=0.0000125,
                model="gemini-1.5-pro",
                reasoning_level=3,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="gemini_flash",
                name="Google Gemini Flash",
                description="Gemini 1.5 Flash (OpenAI-compatible)",
                api_key_env_var="GOOGLE_API_KEY",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                supported_tasks=["general", "chat", "summary", "extraction", "vision", "pdf_ocr"],
                cost_per_token=0.0000005,
                model="gemini-1.5-flash",
                reasoning_level=2,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="gemini_flash_3_5",
                name="Google Gemini 3.5 Flash",
                description="Gemini 3.5 Flash (OpenAI-compatible)",
                api_key_env_var="GOOGLE_API_KEY",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                supported_tasks=["general", "chat", "summary", "extraction", "vision", "pdf_ocr"],
                cost_per_token=0.0000003,
                model="gemini-3.5-flash",
                reasoning_level=3,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="lux",
                name="Lux Computer Use",
                description="Lux Model for Computer Use Agents",
                api_key_env_var="LUX_MODEL_API_KEY",
                supported_tasks=["computer_use", "agentic", "desktop"],
                cost_per_token=0.00002, 
                model="lux-1.0",
                reasoning_level=3,
                supports_structured_output=True
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
                reasoning_level=3,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="glm",
                name="Zhipu GLM",
                description="GLM-4.6 and GLM-5.2 models (1M context, reasoning)",
                api_key_env_var="GLM_API_KEY",
                base_url="https://open.bigmodel.cn/api/paas/v4",
                supported_tasks=["general", "chat", "analysis", "reasoning", "code"],
                cost_per_token=0.000002,
                model="glm-5.2",
                reasoning_level=4,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="moonshot",
                name="Moonshot (Kimi)",
                description="Kimi K2 models — 256K context, vision, reasoning",
                api_key_env_var="MOONSHOT_API_KEY",
                base_url="https://api.moonshot.cn/v1",
                supported_tasks=["general", "chat", "code", "reasoning", "analysis", "vision"],
                cost_per_token=0.000001,
                model="kimi-k2.6",
                reasoning_level=4,
                supports_structured_output=True,
                supports_vision=True,
            ),
            AIProviderConfig(
                id="qwen",
                name="Qwen (Alibaba)",
                description="Qwen 3.5 — high-quality open-weight model via DashScope",
                api_key_env_var="QWEN_API_KEY",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                supported_tasks=["general", "chat", "code", "analysis", "reasoning"],
                cost_per_token=0.000002,
                model="qwen-turbo",
                reasoning_level=3,
                supports_structured_output=True
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
                id="glm_5",
                name="Zhipu GLM 5",
                description="Next-generation GLM-5 model",
                api_key_env_var="GLM_API_KEY",
                base_url="https://open.bigmodel.cn/api/paas/v4",
                supported_tasks=["general", "chat", "analysis"],
                cost_per_token=0.0000021,
                model="glm-5",
                reasoning_level=4
            ),
            AIProviderConfig(
                id="minimax_m3",
                name="MiniMax M3",
                description="MiniMax M3 Flagship (512K context, image input)",
                api_key_env_var="MINIMAX_API_KEY",
                base_url="https://api.minimax.io/v1",
                supported_tasks=["general", "chat", "code"],
                cost_per_token=0.00000075,
                model="MiniMax-M3",
                reasoning_level=3
            ),
            AIProviderConfig(
                id="minimax",
                name="MiniMax",
                description="MiniMax M3 (512K context, OpenAI-compatible). Matches the client key in byok_handler.",
                api_key_env_var="MINIMAX_API_KEY",
                base_url="https://api.minimax.io/v1",
                supported_tasks=["general", "chat", "code", "reasoning", "vision"],
                cost_per_token=0.00000075,
                model="MiniMax-M3",
                reasoning_level=3,
                supports_structured_output=True,
                supports_vision=True,
            ),
            AIProviderConfig(
                id="anthropic_opus_4_6",
                name="Anthropic Claude Opus 4.6",
                description="Advanced Reasoning and Analysis",
                api_key_env_var="ANTHROPIC_API_KEY",
                supported_tasks=["general", "chat", "analysis", "reasoning"],
                cost_per_token=0.000015,
                model="claude-3-opus-4-6",
                reasoning_level=4
            ),
            AIProviderConfig(
                id="openai_5_3",
                name="OpenAI GPT 5.3",
                description="State-of-the-art GPT 5.3 model",
                api_key_env_var="OPENAI_API_KEY",
                supported_tasks=["general", "chat", "code", "reasoning"],
                cost_per_token=0.000007875,
                model="gpt-5.3",
                reasoning_level=4
            ),
            AIProviderConfig(
                id="xiaomi",
                name="Xiaomi",
                description="Xiaomi MiMo V2.5 Pro Agentic Model",
                api_key_env_var="XIAOMI_API_KEY",
                base_url="https://api.xiaomi.com/v1",
                supported_tasks=["general", "chat", "code", "reasoning", "analysis"],
                cost_per_token=0.000001,
                model="xiaomi/mimo-v2.5-pro",
                reasoning_level=4,
                supports_structured_output=True
            ),
            AIProviderConfig(
                id="ollama",
                name="Ollama (Local)",
                description="Local LLM inference via Ollama (OpenAI-compatible). No API key required.",
                api_key_env_var="OLLAMA_API_KEY",  # Optional, not required
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                supported_tasks=["general", "chat", "code", "analysis", "reasoning"],
                cost_per_token=0.0,  # Free — runs locally
                model=os.getenv("OLLAMA_MODEL", "llama3:8b"),
                reasoning_level=3,
                supports_structured_output=True,
                requires_encryption=False,
            ),
            AIProviderConfig(
                id="openrouter",
                name="OpenRouter",
                description="Unified gateway to 300+ models (OpenAI, Anthropic, Google, Meta, and more). One API key.",
                api_key_env_var="OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1",
                supported_tasks=["general", "chat", "code", "reasoning", "analysis", "vision"],
                cost_per_token=0.000003,  # Varies by model — this is a rough floor
                model="openai/gpt-4o-mini",
                reasoning_level=4,
                supports_structured_output=True,
                supports_vision=True,
                supports_tools=True,
            ),
            AIProviderConfig(
                id="xai",
                name="xAI (Grok)",
                description="xAI Grok models — OpenAI-compatible API.",
                api_key_env_var="XAI_API_KEY",
                base_url="https://api.x.ai/v1",
                supported_tasks=["general", "chat", "code", "reasoning"],
                cost_per_token=0.000003,
                model="grok-3-mini",
                reasoning_level=3,
                supports_structured_output=True,
                supports_tools=True,
            ),
            AIProviderConfig(
                id="cerebras",
                name="Cerebras",
                description="Cerebras Inference — ultra-fast OpenAI-compatible API.",
                api_key_env_var="CEREBRAS_API_KEY",
                base_url="https://api.cerebras.ai/v1",
                supported_tasks=["general", "chat"],
                cost_per_token=0.000001,
                model="llama3.1-8b",
                reasoning_level=2,
                supports_structured_output=True,
                supports_tools=True,
            ),
            AIProviderConfig(
                id="fireworks",
                name="Fireworks AI",
                description="Fireworks AI — OpenAI-compatible inference for open models.",
                api_key_env_var="FIREWORKS_API_KEY",
                base_url="https://api.fireworks.ai/inference/v1",
                supported_tasks=["general", "chat", "code", "vision"],
                cost_per_token=0.000002,
                model="accounts/fireworks/models/llama-v3p1-8b-instruct",
                reasoning_level=3,
                supports_structured_output=True,
                supports_vision=True,
                supports_tools=True,
            ),
            AIProviderConfig(
                id="huggingface",
                name="Hugging Face",
                description="Hugging Face Inference Router — OpenAI-compatible API.",
                api_key_env_var="HUGGINGFACE_API_KEY",
                base_url="https://router.huggingface.co/v1",
                supported_tasks=["general", "chat"],
                cost_per_token=0.0,
                model="meta-llama/Llama-3.3-70B-Instruct",
                reasoning_level=3,
                supports_structured_output=True,
                supports_tools=True,
            ),
            AIProviderConfig(
                id="nvidia_nim",
                name="NVIDIA NIM",
                description="NVIDIA NIM — OpenAI-compatible API for self-hosted models.",
                api_key_env_var="NVIDIA_NIM_API_KEY",
                base_url="https://integrate.api.nvidia.com/v1",
                supported_tasks=["general", "chat", "code"],
                cost_per_token=0.0,
                model="meta/llama-3.1-8b-instruct",
                reasoning_level=3,
                supports_structured_output=True,
                supports_tools=True,
            ),
            AIProviderConfig(
                id="zai",
                name="Z.AI",
                description="Z.AI (z.ai) — OpenAI-compatible API (DeepSeek/GLM families).",
                api_key_env_var="ZAI_API_KEY",
                base_url="https://api.z.ai/api/paas/v4",
                supported_tasks=["general", "chat", "code", "reasoning"],
                cost_per_token=0.000003,
                model="glm-4.5",
                reasoning_level=3,
                supports_structured_output=True,
                supports_tools=True,
            ),
            # OpenCode Zen gateway — routed by the BYOK handler as
            # "opencode-go" (alias "opencode"); catalog entry added so the
            # API Keys page can view/store the key (same key serves both).
            AIProviderConfig(
                id="opencode",
                name="OpenCode",
                description="OpenCode Zen gateway — tested open coding models (DeepSeek, Kimi) via one API key.",
                api_key_env_var="OPENCODE_API_KEY",
                base_url="https://opencode.ai/zen/v1",
                supported_tasks=["code", "general", "chat", "reasoning"],
                cost_per_token=0.0,
                model="deepseek-v4-flash",
                reasoning_level=3,
                supports_structured_output=True,
                supports_tools=True,
            ),
            AIProviderConfig(
                id="opencode-go",
                name="OpenCode Go",
                description="OpenCode Go subscription — flat-rate access to the Zen model catalog (~90% cheaper than direct APIs).",
                api_key_env_var="OPENCODE_API_KEY",
                base_url="https://opencode.ai/zen/v1",
                supported_tasks=["code", "general", "chat", "reasoning"],
                cost_per_token=0.0,
                model="deepseek-v4-flash",
                reasoning_level=3,
                supports_structured_output=True,
                supports_tools=True,
            ),
        ]
        
        for provider in defaults:
            if provider.id not in self.providers:
                self.providers[provider.id] = provider
        
        # Update costs from dynamic fetcher
        self.update_provider_costs()

        # Save defaults
        self._save_configuration()

    def update_provider_costs(self):
        """Update provider costs from dynamic pricing fetcher"""
        try:
            from core.dynamic_pricing_fetcher import get_pricing_fetcher
            fetcher = get_pricing_fetcher()

            updated_count = 0
            for provider_id, provider in self.providers.items():
                if provider.model:
                    # Try exact match first, then model name
                    pricing = fetcher.get_model_price(provider.model)

                    if pricing:
                        input_cost = pricing.get("input_cost_per_token", 0)
                        output_cost = pricing.get("output_cost_per_token", 0)

                        # Update cost if we have valid data (average of input and output as single metric)
                        if input_cost > 0 or output_cost > 0:
                            new_cost = (input_cost + output_cost) / 2
                            if new_cost > 0:
                                provider.cost_per_token = new_cost
                                updated_count += 1

            if updated_count > 0:
                logger.info(f"Updated costs for {updated_count} providers from dynamic pricing")

        except Exception as e:
            logger.error(f"Failed to update provider costs: {e}")

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

        R61: mirrors the R59 fix in api/byok_routes — the runtime manager must
        use the same persisted key, or stored keys brick on every restart.
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
            # Ensure key is bytes
            key = self.encryption_key
            if not key:
                raise ValueError("Encyrption key is empty")

            if isinstance(key, str):
                key = key.encode()

            return Fernet(key)
        except Exception as e:
            # R61: do NOT rotate the key here. The old code silently generated
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
    ) -> str:
        """Store an encrypted API key"""
        key_name = self._normalize_key_part(key_name, "default")
        environment = self._normalize_key_part(environment, "production")
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
        )

        self.api_keys[key_id] = api_key_obj
        self._save_configuration()

        return key_id

    def get_api_key(
        self,
        provider_id: str,
        key_name: str = "default",
        environment: str = "production",
    ) -> Optional[str]:
        """Retrieve and decrypt an API key"""
        key_name = self._normalize_key_part(key_name, "default")
        environment = self._normalize_key_part(environment, "production")
        key_id = f"{provider_id}_{key_name}_{environment}"

        if key_id not in self.api_keys:
            # Fallback to environment variable — read-only. Deliberately NOT
            # persisted: auto-storing env values here is what let the test
            # suite's fake provider keys (set by conftest env setup) leak into
            # the live key store. Callers needing a durable key must store it
            # explicitly; the runtime handler applies its own env fallback.
            provider = self.providers.get(provider_id)
            if provider:
                env_key = os.getenv(provider.api_key_env_var)
                if env_key:
                    return env_key
            return None

        api_key_obj = self.api_keys[key_id]

        # Update usage stats
        api_key_obj.last_used = datetime.now()
        api_key_obj.usage_count += 1

        try:
            decrypted_key = self.decrypt_api_key(api_key_obj.encrypted_key)
            return decrypted_key
        except Exception as e:
            logger.error(f"Failed to decrypt API key {key_id}: {e}")
            return None

    def track_usage(self, provider_id: str, success: bool = True, tokens_used: int = 0):
        """Track provider usage"""
        if provider_id not in self.usage_stats:
            self.usage_stats[provider_id] = ProviderUsage(provider_id=provider_id)

        usage = self.usage_stats[provider_id]
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

    def get_optimal_provider(
        self, task_type: str, budget_constraint: float = None, min_reasoning_level: int = 1
    ) -> str:
        """Get the optimal provider for a given task type"""
        suitable_providers = []

        for provider_id, provider in self.providers.items():
            if not provider.is_active:
                continue

            if task_type in provider.supported_tasks:
                # Check reasoning level
                if provider.reasoning_level < min_reasoning_level:
                    continue

                # Check if we have API keys for this provider
                if self.get_api_key(provider_id):
                    suitable_providers.append((provider_id, provider))

        if not suitable_providers:
            # If no provider meets the specific reasoning level, try to fallback to ANY provider with keys
            # for 'general' tasks, but respect reasoning if strict
            if min_reasoning_level > 3:
                 raise ValueError(f"No high-reasoning providers (level {min_reasoning_level}) available for task: {task_type}")
            # Try relaxing reasoning constraint if possible (implied fallback logic)

        if not suitable_providers:
            # Last ditch: Check if OpenAI or DeepSeek keys exist even if not explicitly matched (fallback)
            if self.get_api_key("deepseek") and min_reasoning_level <= 4:
                return "deepseek"
            if self.get_api_key("openai"):
                return "openai"

            return None

        # Sort by cost (cheapest first)
        suitable_providers.sort(key=lambda x: x[1].cost_per_token)

        # INTELLIGENT ROUTING LOGIC (2025 Architecture)
        # If High Reasoning is needed (>=3) and DeepSeek is available, favor it due to extreme cost efficiency
        # unless budget is unlimited and OpenAI is preferred explicitly.
        # The sort above uses dynamically fetched pricing to ensure we always pick the cheapest valid provider.

        # Apply budget constraints if provided
        if budget_constraint is not None:
            suitable_providers = [
                p
                for p in suitable_providers
                if p[1].cost_per_token <= budget_constraint
            ]

        return suitable_providers[0][0] if suitable_providers else None

    def get_provider_status(self, provider_id: str) -> Dict[str, Any]:
        """Get comprehensive status for a provider"""
        provider = self.providers.get(provider_id)
        usage = self.usage_stats.get(
            provider_id, ProviderUsage(provider_id=provider_id)
        )
        has_keys = bool(self.get_api_key(provider_id))

        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        return {
            "provider": asdict(provider),
            "usage": asdict(usage),
            "has_api_keys": has_keys,
            "status": "active" if provider.is_active and has_keys else "inactive",
        }

    # --- Compatibility Methods for BYOKHandler ---
    def is_configured(self, workspace_id: str, provider_id: str) -> bool:
        """Check if a provider is configured for a workspace (compatibility alias)"""
        # Map workspace_id to key_name
        return bool(self.get_api_key(provider_id, key_name=workspace_id))

    def get_tenant_api_key(self, tenant_id: str, provider_id: str) -> Optional[str]:
        """Get API key for a tenant (compatibility alias)"""
        return self.get_api_key(provider_id, key_name=tenant_id)

    @staticmethod
    def _normalize_key_part(value: Any, default: str) -> str:
        if value is None:
            return default
        if isinstance(value, (str, int, float, bool)):
            text = str(value).strip()
            return text or default
        logger.warning("Invalid BYOK key identifier %r; using %s", type(value).__name__, default)
        return default


# Global BYOK Manager instance
_byok_manager = None
_byok_manager_lock = threading.Lock()


def get_byok_manager() -> BYOKManager:
    """Get the global BYOK manager instance (thread-safe singleton)."""
    global _byok_manager
    if _byok_manager is None:
        with _byok_manager_lock:
            # Double-checked locking — avoid re-creating under contention
            if _byok_manager is None:
                _byok_manager = BYOKManager()
    return _byok_manager
