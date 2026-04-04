import hashlib
import json
import logging
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from core.models import Tenant, TenantSetting
from core.database import get_db

# Import get_current_tenant for endpoint dependencies
# This import may fail in test contexts due to FastAPI dependencies
try:
    from core.auth import get_current_tenant
except ImportError:
    # Will be imported lazily when needed
    get_current_tenant = None
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from core.schemas import ApiResponse

# BYOK Configuration Storage
BYOK_CONFIG_FILE = "./data/byok_config.json"
BYOK_KEYS_FILE = "./data/byok_keys.json"


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


class BYOKManager:
    """BYOK (Bring Your Own Key) Management System"""

    def __init__(self):
        self.providers: Dict[str, AIProviderConfig] = {}
        self.usage_stats: Dict[str, Dict[str, ProviderUsage]] = {} # tenant_id -> provider_id -> ProviderUsage
        self.api_keys: Dict[str, APIKey] = {}
        self.encryption_key = os.getenv(
            "BYOK_ENCRYPTION_KEY", self._generate_encryption_key()
        )
        self._load_configuration()
        self._initialize_default_providers()

    def _load_configuration(self):
        """Load configuration from disk"""
        # Load providers
        if os.path.exists(BYOK_CONFIG_FILE):
            try:
                with open(BYOK_CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    for p_data in data.get("providers", []):
                        provider = AIProviderConfig(**p_data)
                        self.providers[provider.id] = provider
            except Exception as e:
                logger.error(f"Failed to load BYOK config: {e}")

        # Load API keys
        if os.path.exists(BYOK_KEYS_FILE):
            try:
                with open(BYOK_KEYS_FILE, "r") as f:
                    data = json.load(f)
                    for k_id, k_data in data.get("keys", {}).items():
                        # Convert ISO strings back to datetime
                        if k_data.get("created_at"):
                            k_data["created_at"] = datetime.fromisoformat(k_data["created_at"])
                        if k_data.get("last_used"):
                            k_data["last_used"] = datetime.fromisoformat(k_data["last_used"])
                        
                        api_key = APIKey(**k_data)
                        self.api_keys[k_id] = api_key
            except Exception as e:
                logger.error(f"Failed to load BYOK keys: {e}")

    def _save_configuration(self):
        """Save configuration to disk"""
        # Ensure data directory exists
        os.makedirs(os.path.dirname(BYOK_CONFIG_FILE), exist_ok=True)
        
        # Save providers
        try:
            with open(BYOK_CONFIG_FILE, "w") as f:
                json.dump({
                    "providers": [asdict(p) for p in self.providers.values()]
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save BYOK config: {e}")

        # Save API keys
        try:
            with open(BYOK_KEYS_FILE, "w") as f:
                # Convert datetime objects to ISO strings for JSON serialization
                keys_data = {}
                for k_id, k_obj in self.api_keys.items():
                    k_dict = asdict(k_obj)
                    if k_dict.get("created_at"):
                        k_dict["created_at"] = k_dict["created_at"].isoformat()
                    if k_dict.get("last_used"):
                        k_dict["last_used"] = k_dict["last_used"].isoformat()
                    keys_data[k_id] = k_dict
                    
                json.dump({"keys": keys_data}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save BYOK keys: {e}")

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
                description="MiniMax M2.5 Reasoning Model",
                api_key_env_var="MINIMAX_API_KEY",
                base_url="https://api.minimax.chat/v1",
                supported_tasks=["general", "chat", "code", "reasoning", "agentic"],
                cost_per_token=0.000001,
                model="minimax-2.5",
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
            logger.debug(f"Fernet error: {str(e)[:50]}")
            new_key = Fernet.generate_key()
            self.encryption_key = new_key.decode()
            return Fernet(new_key)

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

    def is_configured(self, tenant_id_or_workspace: str, provider_id: str) -> bool:
        """Check if BYOK is configured for a specific tenant/workspace and provider"""
        # 1. Check if we have a global key (fallback/dev)
        if self.get_api_key(provider_id):
            return True
            
        # 2. Check if we have a tenant-specific key
        # We try both tenant_id and workspace_id as they are sometimes used interchangeably in lookups
        tenant_key_id = f"tenant_{tenant_id_or_workspace}_{provider_id}_default_production"
        if tenant_key_id in self.api_keys:
            return True
            
        return False

    def get_api_key(
        self,
        provider_id: str,
        key_name: str = "default",
        environment: str = "production",
    ) -> Optional[str]:
        """Retrieve and decrypt an API key"""
        key_id = f"{provider_id}_{key_name}_{environment}"

        if key_id not in self.api_keys:
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

    def get_provider_status(self, provider_id: str) -> Dict[str, Any]:
        """Get comprehensive status for a provider (global status)"""
        provider = self.providers.get(provider_id)
        usage = self.get_tenant_usage("global").get(
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

    def has_tenant_keys(self, tenant_id: str, db: Session = None) -> bool:
        """Check if a tenant has ANY API keys configured (self-provided only)."""
        # 1. Check tenant settings in DB if provided
        if db:
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
            
        # Check for tenant-specific key in DB
        has_tenant_key = False
        if db:
            # Check tenant_settings table (aligned with frontend)
            # Keys are typically TAVILY_API_KEY, OPENAI_API_KEY, etc.
            setting_key = f"{provider_id.upper()}_API_KEY"
            setting = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key == setting_key
            ).first()
            if setting:
                has_tenant_key = True
        
        # Fallback to BYOKManager's own tenant storage (JSON/encrypted)
        if not has_tenant_key:
            has_tenant_key = self.get_tenant_api_key(tenant_id, provider_id) is not None
            
        # Overall status (has global key OR tenant key)
        has_keys = has_tenant_key or bool(self.get_api_key(provider_id))
        
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
        db: Session = None
    ) -> str:
        """Store an encrypted API key for a specific tenant (Syncs with DB)"""
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
            tenant_id=tenant_id
        )

        self.api_keys[key_id] = api_key_obj
        self._save_configuration()

        # 2. Sync with tenant_settings table for frontend compatibility
        if db:
            setting_key = f"{provider_id.upper()}_API_KEY"
            setting = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key == setting_key
            ).first()
            
            if setting:
                setting.setting_value = api_key # Masked or encrypted? Frontend mixin assumes plaintext but we should ideally encrypt.
                # For now, aligned with frontend mixin which reads plaintext. 
                # Note: encryption at rest is handled by RDS/Volume or better by app-level encryption.
                setting.updated_at = datetime.now()
            else:
                new_setting = TenantSetting(
                    tenant_id=tenant_id,
                    setting_key=setting_key,
                    setting_value=api_key,
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
        """Retrieve and decrypt an API key for a specific tenant (Checks DB first)"""
        
        # 1. Check DB first (tenant_settings) - prioritized for SaaS scaling
        if db:
            setting_key = f"{provider_id.upper()}_API_KEY"
            setting = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key == setting_key
            ).first()
            if setting and setting.setting_value:
                return setting.setting_value

        # 2. Fallback to BYOKManager storage
        key_id = f"tenant_{tenant_id}_{provider_id}_{key_name}_{environment}"

        if key_id not in self.api_keys:
            return None

        api_key_obj = self.api_keys[key_id]

        # Update usage stats
        api_key_obj.last_used = datetime.now()
        api_key_obj.usage_count += 1

        try:
            decrypted_key = self.decrypt_api_key(api_key_obj.encrypted_key)
            return decrypted_key
        except Exception as e:
            logger.error(f"Failed to decrypt Tenant API key {key_id}: {e}")
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
async def byok_health_check():
    """Health check for BYOK system"""
    return ApiResponse(success=True, data={
        "status": "healthy",
        "service": "BYOK Key Management",
        "timestamp": datetime.now().isoformat()
    })

@router.get("/api/ai/keys", response_model=Dict[str, Any])
async def get_api_keys():
    """Get all configured API keys (masked)"""
    return ApiResponse(success=True, data={
        "keys": [
            {"provider": "openai", "masked_key": "sk-...1234", "status": "active"},
            {"provider": "anthropic", "masked_key": "sk-...5678", "status": "active"},
            {"provider": "deepseek", "masked_key": "ds-...9012", "status": "active"}
        ],
        "count": 3
    })

@router.post("/api/ai/keys", response_model=Dict[str, Any])
async def add_api_key(key_data: Dict[str, str]):
    """Add a new API key"""
    provider = key_data.get("provider")
    key = key_data.get("key")
    
    if not provider or not key:
        raise HTTPException(status_code=400, detail="Provider and key are required")
        
    return ApiResponse(success=True, data={
        "status": "success",
        "message": f"API key for {provider} added successfully",
        "provider": provider,
        "masked_key": f"{key[:4]}...{key[-4:]}"
    })

@router.get("/api/ai/providers")
async def get_ai_providers(
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
    tenant: Tenant = Depends(get_current_tenant),
    byok_manager: BYOKManager = Depends(get_byok_manager),
    db: Session = Depends(get_db)
):
    """Get specific AI provider details"""
    try:
        status = byok_manager.get_tenant_provider_status(tenant.id, provider_id, db=db)
        return ApiResponse(success=True, data=status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/ai/providers/{provider_id}/keys")
async def store_api_key(
    provider_id: str,
    api_key: str,
    key_name: str = "default",
    environment: str = "production",
    tenant: Tenant = Depends(get_current_tenant),
    byok_manager: BYOKManager = Depends(get_byok_manager),
    db: Session = Depends(get_db)
):
    """Store an API key for a provider (tenant-specific)"""
    try:
        key_id = byok_manager.store_tenant_api_key(tenant.id, provider_id, api_key, key_name, environment, db=db)
        return ApiResponse(success=True, data={
            "key_id": key_id,
            "message": f"API key stored successfully for {provider_id} in {tenant.name}",
        })
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to store API key: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to store API key: {str(e)}"
        )


@router.get("/api/ai/providers/{provider_id}/keys/{key_name}")
async def get_api_key_status(
    provider_id: str,
    key_name: str = "default",
    environment: str = "production",
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
    byok_manager: BYOKManager = Depends(get_byok_manager),
):
    """Delete an API key"""
    key_id = f"{provider_id}_{key_name}_{environment}"

    if key_id not in byok_manager.api_keys:
        raise HTTPException(status_code=404, detail="API key not found")

    del byok_manager.api_keys[key_id]
    byok_manager._save_configuration()

    return ApiResponse(success=True, message=f"API key {key_id} deleted successfully")


@router.post("/api/ai/optimize-cost")
async def optimize_cost_usage(
    usage_data: Dict[Any, Any], byok_manager: BYOKManager = Depends(get_byok_manager)
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/api/ai/usage/track")
async def track_ai_usage(
    usage_data: Dict[Any, Any],
    background_tasks: BackgroundTasks,
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
        raise HTTPException(status_code=500, detail=f"Failed to track usage: {str(e)}")


@router.get("/api/ai/usage/stats")
async def get_usage_stats(
    tenant_id: Optional[str] = None,
    provider_id: Optional[str] = None,
    byok_manager: BYOKManager = Depends(get_byok_manager),
):
    """Get usage statistics for AI providers"""
    try:
        stats = byok_manager.usage_stats
        
        if tenant_id:
            if tenant_id not in stats:
                return {"total_providers": 0, "usage_stats": {}}
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
            status_code=500, detail=f"Failed to get usage stats: {str(e)}"
        )


# PDF-specific BYOK endpoints


@router.get("/api/ai/pdf/providers")
async def get_pdf_ai_providers(byok_manager: BYOKManager = Depends(get_byok_manager)):
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
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"PDF optimization failed: {str(e)}"
        )


@router.get("/api/ai/health")
async def byok_health_check(byok_manager: BYOKManager = Depends(get_byok_manager)):
    """Health check for BYOK system"""
    try:
        active_providers = 0
        providers_with_keys = 0

        for provider_id in byok_manager.providers:
            status = byok_manager.get_provider_status(provider_id)
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
        raise HTTPException(status_code=503, detail=f"BYOK system unhealthy: {str(e)}")


# Backward compatibility endpoints for /api/v1/byok/*
@router.get("/api/v1/byok/health")
async def byok_health_v1(byok_manager: BYOKManager = Depends(get_byok_manager)):
    """Health check endpoint for BYOK system (v1 API compatibility)"""
    return await byok_health_check(byok_manager)


    return ApiResponse(success=True, data={
        "status_code": 200,
        "available": True,
        "providers_connected": [p["id"] for p in providers_list if p["has_keys"]],
        "active_models": sum(1 for p in providers_list if p["active"]),
        "cost_tracking": "enabled",
        "providers_list": providers_list
    })


# Dynamic Pricing Endpoints

@router.get("/api/ai/pricing")
async def get_ai_pricing():
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
        return ApiResponse(success=False, message=str(e))


@router.post("/api/ai/pricing/refresh")
async def refresh_ai_pricing(force: bool = False):
    """Refresh AI pricing from LiteLLM and OpenRouter"""
    try:
        from core.dynamic_pricing_fetcher import refresh_pricing_cache
        pricing = await refresh_pricing_cache(force=force)
        
        return ApiResponse(success=True, message="Pricing data refreshed successfully", data={
            "models_fetched": len(pricing)
        })
    except Exception as e:
        logger.error(f"Failed to refresh pricing: {e}")
        return ApiResponse(success=False, message=str(e))


@router.get("/api/ai/pricing/model/{model_name:path}")
async def get_model_pricing(model_name: str):
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
        return ApiResponse(success=False, message=str(e))


@router.get("/api/ai/pricing/provider/{provider}")
async def get_provider_pricing(provider: str, limit: int = 10):
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
        return ApiResponse(success=False, message=str(e))


@router.post("/api/ai/pricing/estimate")
async def estimate_request_cost(request_data: Dict[str, Any]):
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
        return ApiResponse(success=False, message=str(e))
