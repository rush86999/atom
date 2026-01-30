import logging
import os
import re
import json
from typing import Optional, Dict, Any, List
from enum import Enum

# Try imports
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from core.byok_endpoints import get_byok_manager

logger = logging.getLogger(__name__)


class QueryComplexity(Enum):
    """Query complexity levels for cost-based routing"""
    SIMPLE = "simple"       # Short, straightforward queries -> cheapest provider
    MODERATE = "moderate"   # Medium complexity -> balanced provider
    COMPLEX = "complex"     # Multi-step reasoning -> quality provider
    ADVANCED = "advanced"   # Code, math, analysis -> specialized provider


# Provider tier mapping for cost optimization
PROVIDER_TIERS = {
    # Budget tier - cheapest, good for simple tasks
    "budget": ["deepseek", "moonshot", "glm"],
    # Mid tier - balanced cost/quality
    "mid": ["anthropic", "gemini", "mistral"],
    # Premium tier - best quality, higher cost
    "premium": ["openai", "anthropic"],
    # Specialized - task-specific
    "code": ["deepseek", "openai"],
    "math": ["deepseek", "openai"],
    "creative": ["anthropic", "openai"],
}

# Model recommendations per provider (2026 Frontier Refresh)
COST_EFFICIENT_MODELS = {
    "openai": {
        QueryComplexity.SIMPLE: "o4-mini",
        QueryComplexity.MODERATE: "o4-mini",
        QueryComplexity.COMPLEX: "o3-mini",
        QueryComplexity.ADVANCED: "o3",
    },
    "anthropic": {
        QueryComplexity.SIMPLE: "claude-3-haiku-20240307",
        QueryComplexity.MODERATE: "claude-3-haiku-20240307",
        QueryComplexity.COMPLEX: "claude-3-5-sonnet",
        QueryComplexity.ADVANCED: "claude-4-opus",
    },
    "deepseek": {
        QueryComplexity.SIMPLE: "deepseek-chat",
        QueryComplexity.MODERATE: "deepseek-chat",
        QueryComplexity.COMPLEX: "deepseek-v3.2",
        QueryComplexity.ADVANCED: "deepseek-v3.2-speciale", # User Feedback: Lower cost, frontier reasoning
    },
    "gemini": {
        QueryComplexity.SIMPLE: "gemini-3-flash",
        QueryComplexity.MODERATE: "gemini-3-flash",
        QueryComplexity.COMPLEX: "gemini-3-flash",
        QueryComplexity.ADVANCED: "gemini-3-pro",
    },
    "moonshot": {
        QueryComplexity.SIMPLE: "qwen-3-7b",
        QueryComplexity.MODERATE: "qwen-3-7b",
        QueryComplexity.COMPLEX: "qwen-3-max",
        QueryComplexity.ADVANCED: "qwen-3-max",
    },
}


# Models that do not support tool calling or agentic runtimes (Phase 6.6)
MODELS_WITHOUT_TOOLS = {
    "deepseek-v3.2-speciale",
}

# Phase 14.5: Coordinated Multimodal Reasoning
REASONING_MODELS_WITHOUT_VISION = {
    "deepseek-v3.2",
    "deepseek-v3.2-speciale",
    "o3",
    "o3-mini",
    "deepseek-chat"
}

VISION_ONLY_MODELS = {
    "janus-pro-7b",
    "janus-pro-1.3b",
}


class BYOKHandler:
    """
    Handler for LLM interactions using BYOK system with intelligent cost optimization.
    Automatically routes queries to the most cost-effective provider based on complexity.
    """
    def __init__(self, workspace_id: str = "default", provider_id: str = "auto"):
        self.workspace_id = workspace_id
        self.default_provider_id = provider_id if provider_id != "auto" else None
        self.clients: Dict[str, Any] = {}
        self.byok_manager = get_byok_manager()
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize clients for all available providers"""
        if not OpenAI:
            logger.warning("OpenAI package not installed. LLM features may be limited.")
            return

        # Initialize OpenAI-compatible clients for each provider
        providers_config = {
            "openai": {"base_url": None},
            "deepseek": {"base_url": "https://api.deepseek.com/v1"},
            "moonshot": {"base_url": "https://api.moonshot.cn/v1"},
            "deepinfra": {"base_url": "https://api.deepinfra.com/v1/openai"},
        }
        
        for provider_id, config in providers_config.items():
            # Check if BYOK is configured for this provider and workspace
            if self.byok_manager.is_configured(self.workspace_id, provider_id):
                api_key = self.byok_manager.get_api_key(self.workspace_id, provider_id)
                try:
                    self.clients[provider_id] = OpenAI(
                        api_key=api_key,
                        base_url=config["base_url"] # base_url can be None for OpenAI
                    )
                    logger.info(f"Initialized BYOK client for {provider_id}")
                except Exception as e:
                    logger.error(f"Failed to initialize {provider_id} client: {e}")
            else:
                # Fallback to env for development if BYOK not configured
                env_key = f"{provider_id.upper()}_API_KEY"
                api_key = os.getenv(env_key)
                if api_key:
                    try:
                        if config.get("base_url"):
                            self.clients[provider_id] = OpenAI(
                                api_key=api_key,
                                base_url=config["base_url"]
                            )
                        else:
                            self.clients[provider_id] = OpenAI(api_key=api_key)
                        logger.info(f"Initialized BYOK client for {provider_id}")
                    except Exception as e:
                        logger.error(f"Failed to initialize {provider_id} client: {e}")

    def get_context_window(self, model_name: str) -> int:
        """
        Get the context window size for a model from dynamic pricing data.
        Returns a safe default if not found.
        """
        try:
            from core.dynamic_pricing_fetcher import get_pricing_fetcher
            fetcher = get_pricing_fetcher()
            pricing = fetcher.get_model_price(model_name)
            if pricing:
                # Prefer max_input_tokens, fall back to max_tokens
                return pricing.get("max_input_tokens") or pricing.get("max_tokens") or 4096
        except Exception as e:
            logger.debug(f"Could not get context window for {model_name}: {e}")
        
        # Safe defaults by provider/model
        CONTEXT_DEFAULTS = {
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "gpt-4": 8192,
            "claude-3": 200000,
            "deepseek-chat": 32768,
            "deepseek-reasoner": 32768,
            "gemini": 1000000,  # Gemini has huge context
        }
        for key, size in CONTEXT_DEFAULTS.items():
            if key in model_name.lower():
                return size
        return 4096  # Conservative default

    def truncate_to_context(self, text: str, model_name: str, reserve_tokens: int = 1000) -> str:
        """
        Truncate text to fit within the model's context window.
        Reserves tokens for the response.
        """
        context_window = self.get_context_window(model_name)
        max_input_tokens = context_window - reserve_tokens
        
        # Approximate: 1 token ≈ 4 characters
        max_chars = max_input_tokens * 4
        
        if len(text) <= max_chars:
            return text
        
        # Truncate and add indicator
        truncated = text[:max_chars - 100]
        truncated += "\n\n[... Content truncated to fit context window ...]"
        logger.warning(f"Truncated prompt from {len(text)} to {len(truncated)} chars for {model_name}")
        return truncated

    def analyze_query_complexity(self, prompt: str, task_type: Optional[str] = None) -> QueryComplexity:
        """
        Analyze query complexity to determine optimal provider routing.
        Uses a robust regex-based heuristic with expanded vocabulary.
        """
        # 1. Length-based scoring (estimated tokens)
        estimated_tokens = len(prompt) / 4
        complexity_score = 0
        
        if estimated_tokens >= 2000:
            complexity_score += 3
        elif estimated_tokens >= 500:
            complexity_score += 2
        elif estimated_tokens >= 100:
            complexity_score += 1

        # 2. Regex-based vocabulary analysis
        # Using word boundaries \b to avoid matches inside other words
        patterns = {
            "simple": (r"\b(hello|hi|thanks|greetings|summarize|translate|list|what is|who is|define|how do i|simplify|brief|basic|short|quick|simple)\b", -2),
            "moderate": (r"\b(analyze|compare|evaluate|synthesize|explain|describe|detailed|background|concept|history|nuance|opinion|critique|pros and cons|advantages|disadvantages)\b", 1),
            "technical": (r"\b(calculate|equation|formula|solve|integral|derivative|calculus|geometry|algebra|math|maths|theorem|statistics|probability|regression|vector|matrix|tensor|log|exp|pow|sqrt|abs|sin|cos|tan|pi|infinity|prime|physics|chemistry|biology|science)\b", 3),
            "code": (r"\b(code|coding|function|class|method|script|scripting|debug|debugging|optimize|optimization|refactor|refactoring|snippet|implementation|interface|api|endpoint|webhook|database|sql|postgresql|mongodb|redis|schema|migration|json|xml|yaml|config|docker|kubernetes|aws|lambda|gcp|azure|def|var|let|const|import|return|print|async|await|try|except|catch|throw|public|private|static|final|struct|typedef|typedefs)\b", 3),
            "advanced": (r"\b(architecture|architecting|security audit|vulnerability|cryptography|encryption|decryption|authentication|authorization|auth|oauth|jwt|performance|bottleneck|concurrency|multithread|parallel|distributed|scale|scaling|load balance|cluster|proprietary|reverse engineer|obfuscate|obfuscation|enterprise|global|large-scale)\b", 5)
        }

        # Check for code blocks (significant weight)
        if "```" in prompt:
            complexity_score += 3

        for name, (pattern, weight) in patterns.items():
            if re.search(pattern, prompt, re.IGNORECASE):
                complexity_score += weight

        # 3. Task type override
        if task_type:
            if task_type in ["code", "analysis", "reasoning"]:
                complexity_score += 2
            elif task_type in ["chat", "general"]:
                complexity_score -= 1

        # 4. Map score to complexity level
        # Refined ranges: 2+ is COMPLEX, 5+ is ADVANCED
        if complexity_score <= 0:
            return QueryComplexity.SIMPLE
        elif complexity_score == 1:
            return QueryComplexity.MODERATE
        elif complexity_score <= 4:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.ADVANCED

    def get_optimal_provider(
        self, 
        complexity: QueryComplexity, 
        task_type: Optional[str] = None, 
        prefer_cost: bool = True,
        tenant_plan: str = "free",
        is_managed_service: bool = True,
        requires_tools: bool = False, # Phase 6.6
        requires_structured: bool = False # Phase 6.6
    ) -> tuple[str, str]:
        """Get the single most optimal provider and model."""
        options = self.get_ranked_providers(
            complexity, task_type, prefer_cost, tenant_plan, 
            is_managed_service, requires_tools, requires_structured
        )
        if options:
            return options[0]
        
        # Absolute fallback
        if self.clients:
            provider_id = list(self.clients.keys())[0]
            return provider_id, "gpt-4o-mini"
            
        raise ValueError("No LLM providers available. Please configure BYOK keys.")

    def get_ranked_providers(
        self, 
        complexity: QueryComplexity, 
        task_type: Optional[str] = None,
        prefer_cost: bool = True,
        tenant_plan: str = "free",
        is_managed_service: bool = True,
        requires_tools: bool = False, # Phase 6.6
        requires_structured: bool = False # Phase 6.6
    ) -> List[tuple[str, str]]:
        """
        Get a ranked list of providers and models using the BPC (Benchmark-Price-Capability) algorithm.
        This objectively ranks models based on their value proposition.
        """
        ranked_options = []
        
        # 1. Dynamic BPC Selection (Data-Driven)
        try:
            from core.dynamic_pricing_fetcher import get_pricing_fetcher
            from core.benchmarks import get_quality_score
            fetcher = get_pricing_fetcher()
            
            # Context window requirements
            MIN_CONTEXT_BY_COMPLEXITY = {
                QueryComplexity.SIMPLE: 4000,
                QueryComplexity.MODERATE: 8000,
                QueryComplexity.COMPLEX: 16000,
                QueryComplexity.ADVANCED: 32000
            }
            min_context = MIN_CONTEXT_BY_COMPLEXITY.get(complexity, 8000)
            
            # Filter criteria for benchmarks based on complexity
            MIN_QUALITY_BY_COMPLEXITY = {
                QueryComplexity.SIMPLE: 0,
                QueryComplexity.MODERATE: 80,
                QueryComplexity.COMPLEX: 88,
                QueryComplexity.ADVANCED: 94
            }
            min_quality = MIN_QUALITY_BY_COMPLEXITY.get(complexity, 0)
            
            available_providers = list(self.clients.keys())
            candidates = []
            
            # Use the entire pricing cache to discover models beyond hardcoded lists
            for model_id, pricing in fetcher.pricing_cache.items():
                litellm_provider = pricing.get("litellm_provider", "").lower()
                
                # Check if we have a client for this provider
                active_provider = next((p for p in available_providers if p in model_id.lower() or p == litellm_provider), None)
                if not active_provider:
                    continue
                
                # Check context window
                context_window = pricing.get("max_input_tokens") or pricing.get("max_tokens") or 0
                if context_window < min_context:
                    continue
                
                # Check quality score
                quality_score = get_quality_score(model_id)
                if quality_score < min_quality:
                    continue
                
                # Calculate BPC Value Score
                # Value = (Quality^2) / Cost. We use 1e6 to make costs readable.
                input_cost = pricing.get("input_cost_per_token", 0.00001)
                output_cost = pricing.get("output_cost_per_token", 0.00001)
                avg_cost = (input_cost + output_cost) / 2
                
                # Avoid division by zero and handle free models
                normalized_cost = max(avg_cost, 1e-9) 
                
                # BPC Score: Higher is better value
                # Squaring quality penalizes low-end models regardless of price for complex tasks
                value_score = (quality_score ** 2) / (normalized_cost * 1e6)
                
                candidates.append({
                    "provider": active_provider,
                    "model": model_id,
                    "value_score": value_score,
                    "quality": quality_score,
                    "cost": avg_cost
                })
            
            # Sort by Value Score (Descending)
            candidates.sort(key=lambda x: x["value_score"], reverse=True)
            
            # Filter by plan restrictions
            from core.cost_config import MODEL_TIER_RESTRICTIONS
            allowed_models = MODEL_TIER_RESTRICTIONS.get(tenant_plan.lower(), MODEL_TIER_RESTRICTIONS["free"]) if is_managed_service else "*"
            
            def is_model_approved(model_id: str, allowed_list: any) -> bool:
                if allowed_list == "*" or "*" in allowed_list:
                    return True
                
                # Flexible matching: check if any allowed model name is part of the actual model_id
                model_id_lower = model_id.lower()
                
                # Check Tool/Structured constraints (Phase 6.6)
                if (requires_tools or requires_structured) and any(m in model_id_lower for m in MODELS_WITHOUT_TOOLS):
                    return False

                return any(m.lower() in model_id_lower for m in allowed_list)

            for c in candidates:
                if is_model_approved(c["model"], allowed_models):
                    ranked_options.append((c["provider"], c["model"]))
            
            if ranked_options:
                logger.info(f"BPC Ranking Successful for {complexity.value}: Top model {ranked_options[0][1]} (Value: {candidates[0]['value_score']:.2f})")
                return ranked_options
                
        except Exception as e:
            logger.debug(f"BPC ranking failed, falling back to static mapping: {e}")
        
        # 2. Static Fallback (if BPC logic fails or cache empty)
        if complexity == QueryComplexity.SIMPLE:
            provider_priority = ["deepseek", "moonshot", "gemini", "openai", "anthropic"]
        elif complexity == QueryComplexity.MODERATE:
            provider_priority = ["deepseek", "gemini", "moonshot", "openai", "anthropic"]
        elif complexity == QueryComplexity.COMPLEX:
            provider_priority = ["gemini", "deepseek", "anthropic", "openai", "moonshot"]
        else: # ADVANCED
            provider_priority = ["openai", "deepseek", "anthropic", "gemini", "moonshot"]
        
        for provider_id in provider_priority:
            if provider_id in self.clients:
                models = COST_EFFICIENT_MODELS.get(provider_id, {})
                model = models.get(complexity, "gpt-4o-mini")
                
                if not is_managed_service:
                    # Filter for tool support even in BYOK (Phase 6.6)
                    if (requires_tools or requires_structured) and model in MODELS_WITHOUT_TOOLS:
                        # Fallback to r2 if speciale is disallowed
                        if provider_id == "deepseek" and model == "deepseek-v3.2-speciale":
                            model = "deepseek-r2"
                        else:
                            continue

                    ranked_options.append((provider_id, model))
                    continue

                from core.cost_config import MODEL_TIER_RESTRICTIONS
                allowed_models = MODEL_TIER_RESTRICTIONS.get(tenant_plan.lower(), MODEL_TIER_RESTRICTIONS["free"])
                
                # Check Tool/Structured Support (Phase 6.6)
                if (requires_tools or requires_structured) and model in MODELS_WITHOUT_TOOLS:
                    # Try to downgrade to a model that supports tools within the same provider
                    if provider_id == "deepseek" and model == "deepseek-v3.2-speciale":
                        model = "deepseek-r2" # r2 supports tools/structured
                    else:
                        continue # Skip this provider if no fallback found

                if "*" in allowed_models or model in allowed_models:
                    ranked_options.append((provider_id, model))
                else:
                    for comp in [QueryComplexity.MODERATE, QueryComplexity.SIMPLE]:
                        lower_model = models.get(comp)
                        if lower_model and (lower_model in allowed_models or "*" in allowed_models):
                            ranked_options.append((provider_id, lower_model))
                            break
                            
        return ranked_options

    async def generate_response(
        self, 
        prompt: str, 
        system_instruction: str = "You are a helpful assistant.",
        model_type: str = "auto",  # "auto", "fast", "quality", or specific model
        temperature: float = 0.7,
        task_type: Optional[str] = None,
        prefer_cost: bool = True,
        agent_id: Optional[str] = None, # Phase 65
        image_payload: Optional[str] = None # Phase 14: Base64 or URL
    ) -> str:
        """
        Generate a response using cost-optimized provider routing.
        Supports multimodal inputs (text + image) via `image_payload`.
        """
        # Phase 72: Trial Restriction Check
        if self._is_trial_restricted():
            logger.warning(f"AI Blocked: Trial expired for workspace {self.workspace_id}")
            return "Trial Expired: Your free trial has ended. Please upgrade your plan in settings to continue using AI agents."
        if not self.clients:
            return "LLM Client not initialized (No API Keys configured)."
        
        # --- Budget Enforcement (Phase 56) ---
        from core.llm_usage_tracker import llm_usage_tracker
        if llm_usage_tracker.is_budget_exceeded(self.workspace_id):
            logger.warning(f"AI Generation Blocked: Budget exceeded for workspace {self.workspace_id}")
            return "🚨 BUDGET EXCEEDED: Your AI usage has reached 100% of your limit. Please increase your budget in Settings to continue."

        try:
            # --- Tier & Pricing Mode Enforcement (Phase 59 Refinement) ---
            from core.database import SessionLocal
            from core.models import Workspace, Tenant
            from core.cost_config import BYOK_ENABLED_PLANS
            
            db = SessionLocal()
            tenant_plan = "free"
            is_managed = True
            
            try:
                workspace = db.query(Workspace).filter(Workspace.id == self.workspace_id).first()
                if workspace and workspace.tenant_id:
                    tenant = db.query(Tenant).filter(Tenant.id == workspace.tenant_id).first()
                    if tenant:
                        # 1. Determine Plan level
                        plan_type = tenant.plan_type
                        tenant_plan = plan_type.value if hasattr(plan_type, 'value') else str(plan_type).lower()
                        
                        # 2. Determine if Managed or BYOK (Phase 50 Hybrid Logic)
                        complexity = self.analyze_query_complexity(prompt, task_type)
                        
                        # Agents always require tools (Phase 6.6)
                        requires_tools = agent_id is not None or task_type == "agentic"
                        
                        # Temporary provider check for key resolution
                        temp_provider_id, _ = self.get_optimal_provider(
                            complexity, task_type, prefer_cost, tenant_plan, 
                            is_managed_service=True, requires_tools=requires_tools
                        )
                        
                        tenant_key = self.byok_manager.get_tenant_api_key(tenant.id, temp_provider_id)
                        if tenant_key:
                            is_managed = False  # Custom Key = BYOK
                        elif tenant_plan.lower() in [p.lower() for p in BYOK_ENABLED_PLANS]:
                            is_managed = False  # Enterprise Plan = BYOK
                            
                        # 3. Block Managed AI for Free Tier (Phase 59 User Req)
                        if is_managed and tenant_plan.lower() == "free":
                            return "🚨 PLAN RESTRICTION: Managed AI is not available on the Free plan. Please add your own API key in Settings or upgrade to a Pro plan to continue."
            finally:
                db.close()

            # Analyze complexity
            complexity = self.analyze_query_complexity(prompt, task_type)
            
            # Identify tool/structured requirements (Phase 6.6)
            requires_tools = agent_id is not None or task_type == "agentic"
            
            # --- Phase 14: Vision Routing ---
            # If image payload exists, we MUST route to a model that supports vision (GPT-4o, Gemini 1.5 Pro)
            # We override the normal routing logic to prioritize Vision-Capable models
            requires_vision = image_payload is not None
            
            # Get ranked list of providers
            options = self.get_ranked_providers(
                complexity, task_type, prefer_cost, tenant_plan, is_managed,
                requires_tools=requires_tools, requires_structured=False
            )

            # --- Phase 14.5: Coordinated Vision Logic ---
            if requires_vision:
                # Check if the primary ranked model supports vision natively
                primary_provider, primary_model = options[0] if options else (None, None)
                
                if primary_model and any(m in primary_model.lower() for m in REASONING_MODELS_WITHOUT_VISION):
                    logger.info(f"Coordinating vision for non-vision reasoning model: {primary_model}")
                    vision_desc = await self._get_coordinated_vision_description(
                        image_payload=image_payload,
                        tenant_plan=tenant_plan,
                        is_managed=is_managed
                    )
                    if vision_desc:
                        mapping_instr = (
                            "\n[COORDINATE MAPPING]:\n"
                            "The coordinates below are on a normalized 1000x1000 grid. "
                            "The browser viewport is 1280 pixels wide. "
                            "To click an element at [x, y], use browser_click_coords(x*1.28, y*H) where H is approximately 0.72*1.28.\n"
                        )
                        prompt = f"[VISUAL CONTEXT ANALYSIS]:\n{vision_desc}\n{mapping_instr}\n\n[USER REQUEST]:\n{prompt}"
                        # Disable image_payload for the reasoning call
                        image_payload = None 
                        requires_vision = False

            # Filter for Vision logic if needed
            if requires_vision:
                # 1. Specialized Task Preference (e.g., DeepSeek-OCR for PDF)
                if task_type == "pdf_ocr":
                    # Prefer DeepInfra DeepSeek-OCR or Direct DeepSeek
                    preferred_ocr = [(p, m) for p, m in options if "deepinfra" in p.lower() or "deepseek" in p.lower() or ("deepseek" in m.lower() and "ocr" in m.lower())]
                    if preferred_ocr:
                        options = preferred_ocr
                        logger.info(f"Prioritizing {preferred_ocr[0][0]} for PDF OCR task")

                # 2. Naive filter: Only keep known vision models if not already specialized
                vision_models = ["gpt-4o", "gemini-3-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "claude-3-5-sonnet", "claude-3-opus", "gpt-4-turbo", "deepseek", "deepinfra"]
                vision_options = []
                for prov, mod in options:
                    if any(v in mod.lower() for v in vision_models):
                        vision_options.append((prov, mod))
                
                if vision_options:
                    options = vision_options
                elif not any("deepseek" in p.lower() for p, m in options):
                    # Fallback default if no ranked vision option matches
                    logger.warning("No standard vision models found in ranked options. Defaulting to GPT-4o.")
                    options = [("openai", "gpt-4o")] # Panic fallback
            
            if not options:
                return "No eligible LLM providers found for your current plan."

            last_error = None
            for provider_id, model in options:
                try:
                    client = self.clients[provider_id]
                    
                    # Construct Messages (Phase 14: Multimodal)
                    messages = []
                    messages.append({"role": "system", "content": system_instruction})
                    
                    if image_payload:
                        # OpenAI / Compatible Vision Format
                        user_content = [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_payload if image_payload.startswith("http") else f"data:image/jpeg;base64,{image_payload}"
                                }
                            }
                        ]
                        messages.append({"role": "user", "content": user_content})
                        logger.info(f"Adding visual payload to request for {model}")
                    else:
                        messages.append({"role": "user", "content": prompt})

                    # Make the request
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature
                    )
                    
                    result = response.choices[0].message.content
                    
                    # --- Dynamic Cost Attribution (Phase 47) ---
                    usage = getattr(response, 'usage', None)
                    if usage:
                        input_tokens = getattr(usage, 'prompt_tokens', 0)
                        output_tokens = getattr(usage, 'completion_tokens', 0)
                        
                        # Calculate real cost from dynamic pricing
                        try:
                            from core.dynamic_pricing_fetcher import get_pricing_fetcher
                            fetcher = get_pricing_fetcher()
                            cost = fetcher.estimate_cost(model, input_tokens, output_tokens)
                            
                            # Calculate Reference Cost (gpt-4o) for savings tracking (Phase 58)
                            reference_cost = fetcher.estimate_cost("gpt-4o", input_tokens, output_tokens)
                            savings_usd = max(0, reference_cost - cost) if reference_cost and cost is not None else 0.0
                            
                            # Fallback to static pricing if dynamic not available
                            if cost is None:
                                from core.cost_config import get_llm_cost
                                cost = get_llm_cost(model, input_tokens, output_tokens)
                                # Static reference cost fallback
                                ref_cost_static = get_llm_cost("gpt-4o", input_tokens, output_tokens)
                                savings_usd = max(0, ref_cost_static - cost)
                            
                            if cost and cost > 0:
                                # Record to LLM Usage Tracker
                                from core.llm_usage_tracker import llm_usage_tracker
                                llm_usage_tracker.record(
                                    workspace_id=self.workspace_id,
                                    provider=provider_id,
                                    model=model,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    cost_usd=cost,
                                    savings_usd=savings_usd,
                                    agent_id=agent_id,
                                    complexity=complexity.value, # Phase 6.6
                                    is_managed_service=is_managed
                                )
                                logger.info(f"LLM Cost Attributed ({'Managed' if is_managed else 'BYOK'}): {model} - ${cost:.6f} (Saved: ${savings_usd:.6f})")
                        except Exception as cost_err:
                            logger.warning(f"Could not attribute LLM cost: {cost_err}")
                    
                    # Log for analytics
                    logger.info(f"BYOK Logic: complexity={complexity.value}, provider={provider_id}, model={model}")
                    return result
                
                except Exception as attempt_err:
                    logger.warning(f"Attempt failed for {provider_id}/{model}: {attempt_err}")
                    last_error = attempt_err
                    continue # Try next provider
            
            return f"All providers failed. Last error: {str(last_error)}"
            
        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            return f"Error generating response: {str(e)}"

    async def generate_structured_response(
        self,
        prompt: str,
        system_instruction: str,
        response_model: Any,
        temperature: float = 0.2,
        task_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        image_payload: Optional[str] = None # Phase 14: Vision Support
    ) -> Any:
        """
        Generate a structured response using instructor with tenant-aware routing.
        Works with both BYOK and Managed AI based on subscription.
        Supports multimodal inputs via `image_payload`.
        
        Args:
            prompt: The user prompt
            system_instruction: System instruction for the LLM
            response_model: Pydantic model class for structured output
            temperature: Sampling temperature
            task_type: Optional task type hint
            agent_id: Optional agent ID for cost tracking
            image_payload: Optional Base64 image string or URL
            
        Returns:
            Instance of response_model or None if parsing fails
        """
        # Check trial/budget restrictions
        if self._is_trial_restricted():
            logger.warning(f"AI Blocked: Trial expired for workspace {self.workspace_id}")
            return None
            
        if not self.clients:
            logger.warning("No LLM clients available")
            return None
        
        try:
            # Try to import instructor
            try:
                import instructor
            except ImportError:
                logger.warning("Instructor not available, falling back to raw response")
                return None
            
            # Get tenant plan and determine BYOK vs managed
            from core.database import SessionLocal
            from core.models import Workspace, Tenant
            from core.cost_config import BYOK_ENABLED_PLANS
            
            db = SessionLocal()
            tenant_plan = "free"
            is_managed = True
            
            try:
                workspace = db.query(Workspace).filter(Workspace.id == self.workspace_id).first()
                if workspace and workspace.tenant_id:
                    tenant = db.query(Tenant).filter(Tenant.id == workspace.tenant_id).first()
                    if tenant:
                        plan_type = tenant.plan_type
                        tenant_plan = plan_type.value if hasattr(plan_type, 'value') else str(plan_type).lower()
                        
                        # Check for custom BYOK keys
                        complexity = self.analyze_query_complexity(prompt, task_type)
                        temp_provider_id, _ = self.get_optimal_provider(complexity, task_type, True, tenant_plan, is_managed_service=True)
                        
                        tenant_key = self.byok_manager.get_tenant_api_key(tenant.id, temp_provider_id)
                        if tenant_key:
                            is_managed = False
                        elif tenant_plan.lower() in [p.lower() for p in BYOK_ENABLED_PLANS]:
                            is_managed = False
            finally:
                db.close()
            
            # Block free tier managed AI
            if is_managed and tenant_plan.lower() == "free":
                logger.warning(f"Managed AI blocked for free tier workspace {self.workspace_id}")
                return None
            
            # Get optimal provider and model
            complexity = self.analyze_query_complexity(prompt, task_type)
            
            # Structured generation requires structured support (Phase 6.6)
            requires_tools = agent_id is not None or task_type == "agentic"
            
            # --- Phase 14: Vision Routing ---
            requires_vision = image_payload is not None
            # Get ranked options
            options = self.get_ranked_providers(
                complexity, task_type, True, tenant_plan, is_managed,
                requires_tools=True, requires_structured=True
            )

            # --- Phase 14.5: Coordinated Vision Logic ---
            if image_payload:
                primary_provider, primary_model = options[0] if options else (None, None)
                if primary_model and any(m in primary_model.lower() for m in REASONING_MODELS_WITHOUT_VISION):
                    logger.info(f"Coordinating vision (structured) for non-vision reasoning model: {primary_model}")
                    vision_desc = await self._get_coordinated_vision_description(
                        image_payload=image_payload,
                        tenant_plan=tenant_plan,
                        is_managed=is_managed
                    )
                    if vision_desc:
                        mapping_instr = (
                            "\n[COORDINATE MAPPING]:\n"
                            "The coordinates below are on a normalized 1000x1000 grid. "
                            "The browser viewport is 1280 pixels wide. "
                            "To click an element at [x, y], use browser_click_coords(x*1.28, y*H) where H is approximately 0.72*1.28.\n"
                        )
                        prompt = f"[VISUAL CONTEXT ANALYSIS]:\n{vision_desc}\n{mapping_instr}\n\n[USER REQUEST]:\n{prompt}"
                        image_payload = None 
            
            # Filter for Vision logic if needed
            if requires_vision:
                vision_models = ["gpt-4o", "gemini-3-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "claude-3-5-sonnet", "claude-3-opus", "gpt-4-turbo"]
                vision_options = []
                for prov, mod in options:
                    if any(v in mod.lower() for v in vision_models):
                        vision_options.append((prov, mod))
                
                if vision_options:
                    options = vision_options
                else:
                    logger.warning("No standard vision models found for structured output. Defaulting to GPT-4o.")
                    options = [("openai", "gpt-4o")] # Panic fallback

            if not options:
                return None

            last_error = None
            for provider_id, model in options:
                try:
                    # Get the client and wrap with instructor
                    client = self.clients[provider_id]
                    instructor_client = instructor.from_openai(client)
                    
                    # Truncate prompts to fit context window
                    context_window = self.get_context_window(model)
                    if len(prompt) > context_window * 3:  # ~3 chars per token estimate
                        prompt = self.truncate_to_context(prompt, model, reserve_tokens=1500)
                        logger.info(f"Truncated prompt for model {model} (context: {context_window} tokens)")
                    
                    # Make the structured request
                    logger.info(f"Structured generation ({tenant_plan}, {'Managed' if is_managed else 'BYOK'}): {provider_id}/{model}")
                    
                    # Construct Messages (Phase 14: Multimodal)
                    messages = []
                    messages.append({"role": "system", "content": system_instruction})
                    
                    if image_payload:
                        # OpenAI / Compatible Vision Format
                        user_content = [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_payload if image_payload.startswith("http") else f"data:image/jpeg;base64,{image_payload}"
                                }
                            }
                        ]
                        messages.append({"role": "user", "content": user_content})
                        logger.info(f"Adding visual payload to STRUCTURED request for {model}")
                    else:
                        messages.append({"role": "user", "content": prompt})

                    result = instructor_client.chat.completions.create(
                        model=model,
                        response_model=response_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=1000
                    )
                    
                    # --- Record Usage (Phase 6.6) ---
                    try:
                        # Instructor attaches usage to the response object metadata
                        usage = getattr(result, "_raw_response", {}).usage if hasattr(result, "_raw_response") else None
                        if not usage and hasattr(result, "usage"):
                             usage = result.usage
                        
                        if usage:
                            input_tokens = usage.prompt_tokens
                            output_tokens = usage.completion_tokens
                            
                            from core.dynamic_pricing_fetcher import get_pricing_fetcher
                            fetcher = get_pricing_fetcher()
                            cost = fetcher.estimate_cost(model, input_tokens, output_tokens)
                            
                            if cost and cost > 0:
                                from core.llm_usage_tracker import llm_usage_tracker
                                llm_usage_tracker.record(
                                    workspace_id=self.workspace_id,
                                    provider=provider_id,
                                    model=model,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    cost_usd=cost,
                                    agent_id=agent_id,
                                    complexity=complexity.value,
                                    is_managed_service=is_managed
                                )
                    except Exception as cost_err:
                        logger.warning(f"Could not attribute structured LLM cost: {cost_err}")
                        
                    return result
                except Exception as attempt_err:
                    logger.warning(f"Structured attempt failed for {provider_id}/{model}: {attempt_err}")
                    last_error = attempt_err
                    continue
            
            logger.error(f"All structured providers failed. Last error: {last_error}")
            return None
            
        except Exception as e:
            logger.error(f"Structured generation failed: {e}")
            return None


    def get_available_providers(self) -> List[str]:
        """Get list of providers with valid API keys"""
        return list(self.clients.keys())

    def get_routing_info(self, prompt: str, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Get routing decision info without making an API call (useful for UI)"""
        complexity = self.analyze_query_complexity(prompt, task_type)
        try:
            provider_id, model = self.get_optimal_provider(complexity, task_type)
            
            # Try to get dynamic pricing
            estimated_cost = None
            try:
                from core.dynamic_pricing_fetcher import get_pricing_fetcher
                fetcher = get_pricing_fetcher()
                pricing = fetcher.get_model_price(model)
                if pricing:
                    # Estimate for ~500 token response
                    input_tokens = len(prompt) // 4
                    output_tokens = 500
                    estimated_cost = fetcher.estimate_cost(model, input_tokens, output_tokens)
            except:
                pass
            
            return {
                "complexity": complexity.value,
                "selected_provider": provider_id,
                "selected_model": model,
                "available_providers": self.get_available_providers(),
                "cost_tier": "budget" if provider_id in PROVIDER_TIERS["budget"] else "mid" if provider_id in PROVIDER_TIERS["mid"] else "premium",
                "estimated_cost_usd": estimated_cost
            }
        except ValueError as e:
            return {
                "complexity": complexity.value,
                "error": str(e),
                "available_providers": []
            }

    async def refresh_pricing(self, force: bool = False) -> Dict[str, Any]:
        """Refresh dynamic pricing data from LiteLLM and OpenRouter"""
        try:
            from core.dynamic_pricing_fetcher import refresh_pricing_cache
            pricing = await refresh_pricing_cache(force=force)
            return {"status": "success", "model_count": len(pricing)}
        except Exception as e:
            logger.error(f"Failed to refresh pricing: {e}")
            return {"status": "error", "message": str(e)}

    def get_provider_comparison(self) -> Dict[str, Any]:
        """Get cost comparison across all providers using dynamic pricing"""
        try:
            from core.dynamic_pricing_fetcher import get_pricing_fetcher
            fetcher = get_pricing_fetcher()
            return fetcher.compare_providers()
        except Exception as e:
            logger.warning(f"Could not get provider comparison: {e}")
            # Return static fallback
            return {
                "openai": {"avg_cost_per_token": 0.00003, "tier": "premium"},
                "anthropic": {"avg_cost_per_token": 0.000025, "tier": "premium"},
                "deepseek": {"avg_cost_per_token": 0.000002, "tier": "budget"},
                "moonshot": {"avg_cost_per_token": 0.000003, "tier": "budget"},
            }

    def get_cheapest_models(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the cheapest models available"""
        try:
            from core.dynamic_pricing_fetcher import get_pricing_fetcher
            fetcher = get_pricing_fetcher()
            return fetcher.get_cheapest_models(limit=limit)
        except Exception as e:
            logger.warning(f"Could not get cheapest models: {e}")
            return []
    async def _get_coordinated_vision_description(self, image_payload: str, tenant_plan: str, is_managed: bool) -> Optional[str]:
        """
        Calls a vision-only model to extract a semantic description of an image.
        This allows non-vision reasoning models to understand visual context.
        """
        # Pick a vision-only model (Janus)
        # For now, we'll try to use a specialized provider or default to a cheap vision model if Janus isn't configured
        # 1. Try Gemini Flash (Cheapest Vision)
        if "google_flash" in self.clients:
            provider = "google_flash"
            model = "gemini-2.0-flash" if "gemini-2.0" in str(self.clients["google_flash"]) else "gemini-1.5-flash"
        # 2. Try Deepseek / Janus
        elif provider in self.clients:
            provider = "deepseek"
            model = "janus-pro-7b"
        # 3. Last resort - GPT-4o-mini
        else:
            provider = "openai"
            model = "gpt-4o-mini"
            
        try:
            client = self.clients.get(provider)
            if not client: return None
            
            logger.info(f"Extracting visual description using {model}...")
            
            messages = [
                {
                    "role": "system", 
                    "content": "You are a visual analysis specialist. Your goal is to describe a browser screenshot for an AI agent that cannot see it. "
                               "For every interactive element (buttons, links, inputs, icons, etc.), you MUST provide: "
                               "1. A name or label. "
                               "2. A brief description of its function. "
                               "3. Its precise coordinates as [x, y] center points on a normalized grid from 0 to 1000 "
                               "(where [0, 0] is top-left and [1000, 1000] is bottom-right). "
                               "Format elements as a clear list. Also describe the overall layout and active notifications."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this screenshot and provide a semantic list of interactive elements with [x, y] coordinates on a 1000x1000 grid."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_payload if image_payload.startswith("http") else f"data:image/jpeg;base64,{image_payload}"
                            }
                        }
                    ]
                }
            ]
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=500
            )
            
            desc = response.choices[0].message.content
            return desc
        except Exception as e:
            logger.error(f"Coordinated vision extraction failed: {e}")
            return None
