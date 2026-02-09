from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import json
import logging
import os
import secrets
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

from cryptography.fernet import Fernet
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

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
    supports_structured_output: bool = False

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
                model="claude-3-5-sonnet-20240620",
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
                base_url="https://generativelanguage.googleapis.com/v1beta",
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
                base_url="https://generativelanguage.googleapis.com/v1beta",
                supported_tasks=["general", "chat", "summary", "extraction", "vision", "pdf_ocr"],
                cost_per_token=0.0000005,
                model="gemini-1.5-flash",
                reasoning_level=2,
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
                description="GLM-4 and GLM-4.6 models",
                api_key_env_var="GLM_API_KEY",
                base_url="https://open.bigmodel.cn/api/paas/v4",
                supported_tasks=["general", "chat", "analysis"],
                cost_per_token=0.000005,
                model="glm-4.6",
                reasoning_level=3,
                supports_structured_output=False
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
            )
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
            # Only log error once per session to avoid spamming logs
            if not hasattr(self, '_encryption_error_logged'):
                logger.warning(f"Invalid encryption key encountered: {e}. Generating new key.")
                self._encryption_error_logged = True
                
            # Fallback to a new key if invalid (will invalidate existing data)
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

    def get_api_key(
        self,
        provider_id: str,
        key_name: str = "default",
        environment: str = "production",
    ) -> Optional[str]:
        """Retrieve and decrypt an API key"""
        key_id = f"{provider_id}_{key_name}_{environment}"

        if key_id not in self.api_keys:
            # Fallback to environment variable
            provider = self.providers.get(provider_id)
            if provider:
                env_key = os.getenv(provider.api_key_env_var)
                if env_key:
                    # Store it for future use
                    self.store_api_key(provider_id, env_key, key_name, environment)
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


# Global BYOK Manager instance
_byok_manager = None


def get_byok_manager() -> BYOKManager:
    """Get the global BYOK manager instance"""
    global _byok_manager
    if _byok_manager is None:
        _byok_manager = BYOKManager()
    return _byok_manager


# API Endpoints

@router.get("/api/v1/byok/health")
async def byok_health_check():
    """Health check for BYOK system"""
    return {
        "status": "healthy",
        "service": "BYOK Key Management",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/api/ai/keys", response_model=Dict[str, Any])
async def get_api_keys(byok_manager: BYOKManager = Depends(get_byok_manager)):
    """Get all configured API keys (masked)"""
    keys = []
    for key_id, key_obj in byok_manager.api_keys.items():
        # Mask the key (we only have the encrypted version here, but we can just show it's configured)
        keys.append({
            "provider": key_obj.provider_id,
            "key_name": key_obj.key_name,
            "status": "active" if key_obj.is_active else "inactive",
            "created_at": key_obj.created_at.isoformat() if key_obj.created_at else None,
            "last_used": key_obj.last_used.isoformat() if key_obj.last_used else None,
            "masked_key": f"****...{key_obj.key_hash[:4]}" if key_obj.key_hash else "****"
        })
    
    return {
        "keys": keys,
        "count": len(keys)
    }

@router.post("/api/ai/keys", response_model=Dict[str, Any])
async def add_api_key(key_data: Dict[str, str], byok_manager: BYOKManager = Depends(get_byok_manager)):
    """Add a new API key"""
    provider = key_data.get("provider")
    key = key_data.get("key")
    key_name = key_data.get("key_name", "default")
    environment = key_data.get("environment", "production")
    
    if not provider or not key:
        raise HTTPException(status_code=400, detail="Provider and key are required")
        
    try:
        key_id = byok_manager.store_api_key(
            provider_id=provider,
            api_key=key,
            key_name=key_name,
            environment=environment
        )
        
        return {
            "status": "success",
            "message": f"API key for {provider} added successfully",
            "provider": provider,
            "key_id": key_id,
            "masked_key": f"{key[:4]}...{key[-4:]}"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/ai/providers")
async def get_ai_providers(byok_manager: BYOKManager = Depends(get_byok_manager)):
    """Get available AI providers with status"""
    providers_with_status = []

    for provider_id in byok_manager.providers:
        try:
            status = byok_manager.get_provider_status(provider_id)
            providers_with_status.append(status)
        except Exception as e:
            logger.error(f"Failed to get status for provider {provider_id}: {e}")

    return {
        "providers": providers_with_status,
        "total_providers": len(providers_with_status),
        "active_providers": len(
            [p for p in providers_with_status if p["status"] == "active"]
        ),
    }


@router.get("/api/ai/providers/{provider_id}")
async def get_ai_provider(
    provider_id: str, byok_manager: BYOKManager = Depends(get_byok_manager)
):
    """Get specific AI provider details"""
    try:
        status = byok_manager.get_provider_status(provider_id)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/ai/providers/{provider_id}/keys")
async def store_api_key(
    provider_id: str,
    api_key: str,
    key_name: str = "default",
    environment: str = "production",
    byok_manager: BYOKManager = Depends(get_byok_manager),
):
    """Store an API key for a provider"""
    try:
        key_id = byok_manager.store_api_key(provider_id, api_key, key_name, environment)
        return {
            "success": True,
            "key_id": key_id,
            "message": f"API key stored successfully for {provider_id}",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
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

    return {
        "key_id": key_id,
        "provider_id": key_info.provider_id,
        "key_name": key_info.key_name,
        "environment": key_info.environment,
        "is_active": key_info.is_active,
        "usage_count": key_info.usage_count,
        "created_at": key_info.created_at,
        "last_used": key_info.last_used,
        "has_key": True,
    }


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

    return {"success": True, "message": f"API key {key_id} deleted successfully"}


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

        return {
            "success": True,
            "recommended_provider": optimal_provider,
            "provider_name": provider.name,
            "estimated_cost": estimated_cost,
            "estimated_tokens": estimated_tokens,
            "cost_per_token": provider.cost_per_token,
            "alternatives": sorted(alternatives, key=lambda x: x["estimated_cost"]),
            "reason": f"Most cost-effective for {task_type} tasks",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/api/ai/usage/track")
async def track_ai_usage(
    usage_data: Dict[Any, Any],
    background_tasks: BackgroundTasks,
    byok_manager: BYOKManager = Depends(get_byok_manager),
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
            byok_manager.track_usage, provider_id, success, tokens_used
        )

        return {
            "success": True,
            "message": f"Usage tracked for {provider_id}",
            "tokens_used": tokens_used,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to track usage: {str(e)}")


@router.get("/api/ai/usage/stats")
async def get_usage_stats(
    provider_id: Optional[str] = None,
    byok_manager: BYOKManager = Depends(get_byok_manager),
):
    """Get usage statistics for AI providers"""
    try:
        if provider_id:
            if provider_id not in byok_manager.usage_stats:
                raise HTTPException(
                    status_code=404, detail=f"No usage data for {provider_id}"
                )

            usage = byok_manager.usage_stats[provider_id]
            return {"provider_id": provider_id, "usage": asdict(usage)}
        else:
            # Return all usage stats
            all_stats = {}
            for pid, usage in byok_manager.usage_stats.items():
                all_stats[pid] = asdict(usage)

            return {"total_providers": len(all_stats), "usage_stats": all_stats}

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

    return {
        "pdf_providers": pdf_providers,
        "total_pdf_providers": len(pdf_providers),
        "supported_tasks": [
            "pdf_ocr",
            "image_comprehension",
            "document_processing",
            "multimodal",
        ],
    }


@router.post("/api/ai/pdf/optimize")
async def optimize_pdf_processing(
    pdf_characteristics: Dict[Any, Any],
    byok_manager: BYOKManager = Depends(get_byok_manager),
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
        optimal_provider = byok_manager.get_optimal_provider(
            task_type, budget_constraint
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
            high_quality_provider = byok_manager.get_optimal_provider(
                "image_comprehension"
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
            logger.error(f"Failed to get high quality provider: {e}", exc_info=True)

        # Cost-effective scenario
        try:
            cost_effective_provider = byok_manager.get_optimal_provider(
                "pdf_ocr", 0.001
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
            logger.error(f"Failed to get cost-effective provider: {e}", exc_info=True)

        return {
            "success": True,
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
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
            usage.total_requests for usage in byok_manager.usage_stats.values()
        )
        total_cost = sum(
            usage.cost_accumulated for usage in byok_manager.usage_stats.values()
        )

        return {
            "status": "healthy",
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
        }

    except Exception as e:
        raise HTTPException(status_code=503, detail=f"BYOK system unhealthy: {str(e)}")


# Backward compatibility endpoints for /api/v1/byok/*
@router.get("/api/v1/byok/health")
async def byok_health_v1(byok_manager: BYOKManager = Depends(get_byok_manager)):
    """Health check endpoint for BYOK system (v1 API compatibility)"""
    return await byok_health_check(byok_manager)


@router.get("/api/v1/byok/status")
async def byok_status_v1(byok_manager: BYOKManager = Depends(get_byok_manager)):
    """Status endpoint for BYOK system with provider details"""
    health_response = await byok_health_check(byok_manager)

    # Add provider list
    providers_list = []
    for provider_id in byok_manager.providers:
        try:
            status = byok_manager.get_provider_status(provider_id)
            providers_list.append({
                "id":  provider_id,
                "name": status["provider"]["name"],
                "status": status["status"],
                "has_keys": status["has_api_keys"],
                "active": status["provider"]["is_active"]
            })
        except Exception as e:
            logger.error(f"Failed to get status for provider {provider_id}: {e}")

    return {
        **health_response,
        "status_code": 200,
        "available": True,
        "providers_connected": [p["id"] for p in providers_list if p["has_keys"]],
        "active_models": sum(1 for p in providers_list if p["active"]),
        "cost_tracking": "enabled",
        "providers_list": providers_list
    }


# Dynamic Pricing Endpoints

@router.get("/api/ai/pricing")
async def get_ai_pricing():
    """Get current AI model pricing from cache"""
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        fetcher = get_pricing_fetcher()
        
        return {
            "status": "success",
            "model_count": len(fetcher.pricing_cache),
            "last_updated": fetcher.last_fetch.isoformat() if fetcher.last_fetch else None,
            "cache_valid": fetcher._is_cache_valid(),
            "cheapest_models": fetcher.get_cheapest_models(5),
            "provider_comparison": fetcher.compare_providers()
        }
    except Exception as e:
        logger.error(f"Failed to get pricing: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/ai/pricing/refresh")
async def refresh_ai_pricing(
    force: bool = False,
    byok_manager: BYOKManager = Depends(get_byok_manager)
):
    """Refresh AI pricing from LiteLLM and OpenRouter"""
    try:
        from core.dynamic_pricing_fetcher import refresh_pricing_cache
        pricing = await refresh_pricing_cache(force=force)
        
        # Update BYOK manager costs
        byok_manager.update_provider_costs()

        return {
            "status": "success",
            "models_fetched": len(pricing),
            "message": "Pricing data refreshed successfully and provider costs updated"
        }
    except Exception as e:
        logger.error(f"Failed to refresh pricing: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/api/ai/pricing/model/{model_name:path}")
async def get_model_pricing(model_name: str):
    """Get pricing for a specific model"""
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        fetcher = get_pricing_fetcher()
        
        pricing = fetcher.get_model_price(model_name)
        if pricing:
            return {
                "status": "success",
                "model": model_name,
                "pricing": pricing
            }
        else:
            return {
                "status": "not_found",
                "model": model_name,
                "message": "Model pricing not found. Try refreshing the cache."
            }
    except Exception as e:
        logger.error(f"Failed to get model pricing: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/api/ai/pricing/provider/{provider}")
async def get_provider_pricing(provider: str, limit: int = 10):
    """Get all models and pricing for a specific provider"""
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        fetcher = get_pricing_fetcher()
        
        models = fetcher.get_provider_models(provider)[:limit]
        
        return {
            "status": "success",
            "provider": provider,
            "model_count": len(models),
            "models": models
        }
    except Exception as e:
        logger.error(f"Failed to get provider pricing: {e}")
        return {"status": "error", "message": str(e)}


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
            return {
                "status": "success",
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": estimated_cost
            }
        else:
            # Try to find similar model
            pricing = fetcher.get_model_price(model)
            if pricing:
                input_cost = pricing.get("input_cost_per_token", 0) * input_tokens
                output_cost = pricing.get("output_cost_per_token", 0) * output_tokens
                return {
                    "status": "success",
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "estimated_cost_usd": input_cost + output_cost
                }
            
            return {
                "status": "pricing_unavailable",
                "model": model,
                "message": "Model pricing not found. Refresh pricing cache."
            }
    except Exception as e:
        logger.error(f"Failed to estimate cost: {e}")
        return {"status": "error", "message": str(e)}
