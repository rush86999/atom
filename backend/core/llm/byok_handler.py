
import logging
import os
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

# Model recommendations per provider
COST_EFFICIENT_MODELS = {
    "openai": {
        QueryComplexity.SIMPLE: "gpt-4o-mini",
        QueryComplexity.MODERATE: "gpt-4o-mini",
        QueryComplexity.COMPLEX: "gpt-4o",
        QueryComplexity.ADVANCED: "gpt-4o",
    },
    "anthropic": {
        QueryComplexity.SIMPLE: "claude-3-haiku-20240307",
        QueryComplexity.MODERATE: "claude-3-5-sonnet-20241022",
        QueryComplexity.COMPLEX: "claude-3-5-sonnet-20241022",
        QueryComplexity.ADVANCED: "claude-3-5-sonnet-20241022",
    },
    "deepseek": {
        QueryComplexity.SIMPLE: "deepseek-chat",
        QueryComplexity.MODERATE: "deepseek-chat",
        QueryComplexity.COMPLEX: "deepseek-reasoner",
        QueryComplexity.ADVANCED: "deepseek-reasoner",
    },
    "moonshot": {
        QueryComplexity.SIMPLE: "kimi-k1-5",
        QueryComplexity.MODERATE: "kimi-k1-5",
        QueryComplexity.COMPLEX: "kimi-k1-5",
        QueryComplexity.ADVANCED: "kimi-k1-5",
    },
    "gemini": {
        QueryComplexity.SIMPLE: "gemini-2.0-flash",
        QueryComplexity.MODERATE: "gemini-2.0-flash",
        QueryComplexity.COMPLEX: "gemini-2.0-flash-thinking-exp",
        QueryComplexity.ADVANCED: "gemini-2.0-flash-thinking-exp",
    },
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
        }
        
        for provider_id, config in providers_config.items():
            api_key = self.byok_manager.get_api_key(provider_id)
            
            # Fallback to env for development
            if not api_key:
                env_key = f"{provider_id.upper()}_API_KEY"
                api_key = os.getenv(env_key)
            
            if api_key:
                try:
                    if config["base_url"]:
                        self.clients[provider_id] = OpenAI(
                            api_key=api_key,
                            base_url=config["base_url"]
                        )
                    else:
                        self.clients[provider_id] = OpenAI(api_key=api_key)
                    logger.info(f"Initialized BYOK client for {provider_id}")
                except Exception as e:
                    logger.error(f"Failed to initialize {provider_id} client: {e}")

    def analyze_query_complexity(self, prompt: str, task_type: Optional[str] = None) -> QueryComplexity:
        """
        Analyze query complexity to determine optimal provider routing.
        Uses heuristics to estimate complexity without making an API call.
        """
        # Token count approximation (rough: 1 token ≈ 4 chars)
        estimated_tokens = len(prompt) / 4
        
        # Complexity indicators
        complexity_score = 0
        
        # Length-based scoring
        if estimated_tokens < 100:
            complexity_score += 0
        elif estimated_tokens < 500:
            complexity_score += 1
        elif estimated_tokens < 2000:
            complexity_score += 2
        else:
            complexity_score += 3
        
        # Content-based analysis
        prompt_lower = prompt.lower()
        
        # Code indicators
        code_keywords = ["```", "def ", "function ", "class ", "import ", "const ", "var ", "let "]
        if any(kw in prompt for kw in code_keywords):
            complexity_score += 2
        
        # Math/reasoning indicators
        math_keywords = ["calculate", "equation", "formula", "prove", "derive", "solve for"]
        if any(kw in prompt_lower for kw in math_keywords):
            complexity_score += 2
        
        # Multi-step reasoning indicators
        reasoning_keywords = ["step by step", "analyze", "compare", "evaluate", "synthesize", "explain why"]
        if any(kw in prompt_lower for kw in reasoning_keywords):
            complexity_score += 1
        
        # Simple task indicators (reduce complexity)
        simple_keywords = ["summarize", "translate", "list", "what is", "who is", "define"]
        if any(kw in prompt_lower for kw in simple_keywords):
            complexity_score -= 1
        
        # Task type override
        if task_type:
            if task_type in ["code", "analysis", "reasoning"]:
                complexity_score += 2
            elif task_type in ["chat", "general"]:
                complexity_score -= 1
        
        # Map score to complexity level
        if complexity_score <= 0:
            return QueryComplexity.SIMPLE
        elif complexity_score <= 2:
            return QueryComplexity.MODERATE
        elif complexity_score <= 4:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.ADVANCED

    def get_optimal_provider(
        self, 
        complexity: QueryComplexity, 
        task_type: Optional[str] = None,
        prefer_cost: bool = True
    ) -> tuple[str, str]:
        """
        Get the optimal provider and model based on complexity and available keys.
        Returns (provider_id, model_name)
        """
        # If user specified a provider, use it
        if self.default_provider_id and self.default_provider_id in self.clients:
            provider = self.default_provider_id
            models = COST_EFFICIENT_MODELS.get(provider, {})
            model = models.get(complexity, "gpt-4o-mini")
            return provider, model
        
        # Priority order based on complexity and cost preference
        if complexity == QueryComplexity.SIMPLE:
            provider_priority = ["deepseek", "moonshot", "openai"]
        elif complexity == QueryComplexity.MODERATE:
            provider_priority = ["deepseek", "openai", "anthropic"]
        elif complexity == QueryComplexity.COMPLEX:
            if task_type == "code":
                provider_priority = ["deepseek", "openai"]
            else:
                provider_priority = ["openai", "anthropic", "deepseek"]
        else:  # ADVANCED
            if task_type in ["code", "math"]:
                provider_priority = ["deepseek", "openai"]
            else:
                provider_priority = ["openai", "anthropic"]
        
        # Find first available provider
        for provider_id in provider_priority:
            if provider_id in self.clients:
                models = COST_EFFICIENT_MODELS.get(provider_id, {})
                model = models.get(complexity, "gpt-4o-mini")
                logger.info(f"Cost-optimized routing: {complexity.value} -> {provider_id}/{model}")
                return provider_id, model
        
        # Fallback to any available provider
        if self.clients:
            provider_id = list(self.clients.keys())[0]
            return provider_id, "gpt-4o-mini"
        
        raise ValueError("No LLM providers available. Please configure BYOK keys.")

    async def generate_response(
        self, 
        prompt: str, 
        system_instruction: str = "You are a helpful assistant.",
        model_type: str = "auto",  # "auto", "fast", "quality", or specific model
        temperature: float = 0.7,
        task_type: Optional[str] = None,
        prefer_cost: bool = True
    ) -> str:
        """
        Generate a response using cost-optimized provider routing.
        
        Args:
            prompt: The user prompt
            system_instruction: System instruction for the LLM
            model_type: "auto" for complexity-based routing, or specify model
            temperature: Sampling temperature
            task_type: Optional task type hint (code, chat, analysis, etc.)
            prefer_cost: If True, prefer cheaper providers when quality is similar
        """
        if not self.clients:
            return "LLM Client not initialized (No API Keys configured)."
        
        try:
            # Analyze complexity for routing
            complexity = self.analyze_query_complexity(prompt, task_type)
            
            # Get optimal provider
            provider_id, model = self.get_optimal_provider(complexity, task_type, prefer_cost)
            
            client = self.clients[provider_id]
            
            # Make the request
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature
            )
            
            result = response.choices[0].message.content
            
            # Log for analytics
            logger.info(f"BYOK Cost Optimization: complexity={complexity.value}, provider={provider_id}, model={model}")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            return f"Error generating response: {str(e)}"

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
