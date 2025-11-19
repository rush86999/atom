import hashlib
import json
import logging
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

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

    def _generate_encryption_key(self) -> str:
        """Generate a default encryption key for development"""
        return secrets.token_hex(32)

    def _load_configuration(self):
        """Load BYOK configuration from files"""
        try:
            # Load provider configuration
            if os.path.exists(BYOK_CONFIG_FILE):
                with open(BYOK_CONFIG_FILE, "r") as f:
                    config_data = json.load(f)
                    self._load_providers_from_config(config_data)

            # Load API keys
            if os.path.exists(BYOK_KEYS_FILE):
                with open(BYOK_KEYS_FILE, "r") as f:
                    keys_data = json.load(f)
                    self._load_keys_from_config(keys_data)

        except Exception as e:
            logger.error(f"Failed to load BYOK configuration: {e}")

    def _save_configuration(self):
        """Save BYOK configuration to files"""
        try:
            # Save provider configuration
            config_data = {
                "providers": {
                    pid: asdict(provider) for pid, provider in self.providers.items()
                },
                "usage_stats": {
                    pid: asdict(usage) for pid, usage in self.usage_stats.items()
                },
            }

            os.makedirs(os.path.dirname(BYOK_CONFIG_FILE), exist_ok=True)
            with open(BYOK_CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=2, default=str)

            # Save API keys
            keys_data = {
                "api_keys": {kid: asdict(key) for kid, key in self.api_keys.items()},
                "encryption_key_hash": hashlib.sha256(
                    self.encryption_key.encode()
                ).hexdigest(),
            }

            with open(BYOK_KEYS_FILE, "w") as f:
                json.dump(keys_data, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to save BYOK configuration: {e}")

    def _load_providers_from_config(self, config_data: Dict[str, Any]):
        """Load providers from configuration data"""
        providers_data = config_data.get("providers", {})
        for provider_id, provider_data in providers_data.items():
            try:
                # Convert string dates back to datetime objects
                if "last_used" in provider_data and provider_data["last_used"]:
                    provider_data["last_used"] = datetime.fromisoformat(
                        provider_data["last_used"]
                    )

                self.providers[provider_id] = AIProviderConfig(**provider_data)
            except Exception as e:
                logger.error(f"Failed to load provider {provider_id}: {e}")

    def _load_keys_from_config(self, keys_data: Dict[str, Any]):
        """Load API keys from configuration data"""
        keys_data = keys_data.get("api_keys", {})
        for key_id, key_data in keys_data.items():
            try:
                # Convert string dates back to datetime objects
                if "created_at" in key_data and key_data["created_at"]:
                    key_data["created_at"] = datetime.fromisoformat(
                        key_data["created_at"]
                    )
                if "last_used" in key_data and key_data["last_used"]:
                    key_data["last_used"] = datetime.fromisoformat(
                        key_data["last_used"]
                    )

                self.api_keys[key_id] = APIKey(**key_data)
            except Exception as e:
                logger.error(f"Failed to load API key {key_id}: {e}")

    def _initialize_default_providers(self):
        """Initialize default AI providers"""
        default_providers = [
            AIProviderConfig(
                id="glm",
                name="GLM-4.6",
                description="GLM-4.6 models for cost-effective AI tasks and document processing",
                api_key_env_var="GLM_API_KEY",
                base_url="https://api.z.ai/api/paas/v4",
                model="glm-4.6",
                cost_per_token=0.0001,
                supported_tasks=[
                    "chat",
                    "code",
                    "analysis",
                    "pdf_processing",
                    "document_processing",
                ],
                max_requests_per_minute=120,
            ),
            AIProviderConfig(
                id="openai",
                name="OpenAI",
                description="GPT models for general AI tasks and PDF processing (paused for cost optimization)",
                api_key_env_var="OPENAI_API_KEY",
                cost_per_token=0.002,
                supported_tasks=[
                    "chat",
                    "code",
                    "analysis",
                    "pdf_ocr",
                    "image_comprehension",
                ],
                max_requests_per_minute=60,
                is_active=False,  # Paused for cost optimization
            ),
            AIProviderConfig(
                id="anthropic",
                name="Anthropic Claude",
                description="Advanced reasoning and document analysis",
                api_key_env_var="ANTHROPIC_API_KEY",
                cost_per_token=0.008,
                supported_tasks=[
                    "analysis",
                    "reasoning",
                    "chat",
                    "document_processing",
                ],
                max_requests_per_minute=40,
            ),
            AIProviderConfig(
                id="google_gemini",
                name="Google Gemini",
                description="Document analysis and multimodal AI",
                api_key_env_var="GOOGLE_API_KEY",
                cost_per_token=0.0005,
                supported_tasks=[
                    "analysis",
                    "chat",
                    "documents",
                    "pdf_processing",
                    "multimodal",
                ],
                max_requests_per_minute=60,
            ),
            AIProviderConfig(
                id="azure_openai",
                name="Azure OpenAI",
                description="Enterprise OpenAI services",
                api_key_env_var="AZURE_OPENAI_API_KEY",
                base_url=None,  # Will be constructed from resource name
                cost_per_token=0.002,
                supported_tasks=["chat", "code", "analysis", "pdf_processing"],
                max_requests_per_minute=120,
            ),
            AIProviderConfig(
                id="deepseek",
                name="DeepSeek",
                description="Cost-effective code generation and analysis",
                api_key_env_var="DEEPSEEK_API_KEY",
                cost_per_token=0.0001,
                supported_tasks=["code", "analysis", "text_processing"],
                max_requests_per_minute=100,
            ),
            AIProviderConfig(
                id="huggingface",
                name="Hugging Face",
                description="Open source models and inference API",
                api_key_env_var="HUGGINGFACE_API_KEY",
                cost_per_token=0.0,  # Free tier available
                supported_tasks=["text_generation", "summarization", "translation"],
                max_requests_per_minute=30,
            ),
        ]

        # Add providers if they don't exist
        for provider in default_providers:
            if provider.id not in self.providers:
                self.providers[provider.id] = provider
                self.usage_stats[provider.id] = ProviderUsage(provider_id=provider.id)

    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key (simplified - in production use proper encryption)"""
        # This is a simplified encryption for demonstration
        # In production, use proper encryption like Fernet or AES
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        # Simple XOR encryption for demo (not secure for production)
        encrypted = "".join(
            chr(ord(c) ^ ord(k))
            for c, k in zip(api_key, self.encryption_key * len(api_key))
        )
        return encrypted

    def decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt API key (simplified - in production use proper decryption)"""
        # Simple XOR decryption for demo (not secure for production)
        decrypted = "".join(
            chr(ord(c) ^ ord(k))
            for c, k in zip(encrypted_key, self.encryption_key * len(encrypted_key))
        )
        return decrypted

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
        self, task_type: str, budget_constraint: float = None
    ) -> str:
        """Get the optimal provider for a given task type"""
        suitable_providers = []

        for provider_id, provider in self.providers.items():
            if not provider.is_active:
                continue

            if task_type in provider.supported_tasks:
                # Check if we have API keys for this provider
                if self.get_api_key(provider_id):
                    suitable_providers.append((provider_id, provider))

        if not suitable_providers:
            raise ValueError(f"No suitable providers found for task type: {task_type}")

        # Sort by cost (cheapest first)
        suitable_providers.sort(key=lambda x: x[1].cost_per_token)

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


# Global BYOK Manager instance
_byok_manager = None


def get_byok_manager() -> BYOKManager:
    """Get the global BYOK manager instance"""
    global _byok_manager
    if _byok_manager is None:
        _byok_manager = BYOKManager()
    return _byok_manager


# API Endpoints


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
        except:
            pass

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
        except:
            pass

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
