
import logging
import os
import openai
import anthropic
from typing import Optional, Dict, Any, List, Union
from enum import Enum

# Try imports
try:
    from openai import OpenAI, AsyncOpenAI
except ImportError:
    OpenAI = None
    AsyncOpenAI = None

from core.byok_endpoints import get_byok_manager
from core.dynamic_pricing_fetcher import get_pricing_fetcher

logger = logging.getLogger(__name__)


class QueryComplexity(Enum):
    """Query complexity levels for cost-based routing"""
    SIMPLE = "simple"       # Short, straightforward queries -> cheapest provider
    MODERATE = "moderate"   # Medium complexity -> balanced provider
    COMPLEX = "complex"     # Multi-step reasoning -> quality provider
    ADVANCED = "advanced"   # Code, math, analysis -> specialized provider


# Base Model Preferences (Hardcoded fallback if dynamic fetching fails)
# We prioritize DeepSeek for reasoning due to architecture report
DEFAULT_REASONING_MODELS = ["deepseek-chat", "gpt-4o", "claude-3-5-sonnet-20241022"]
DEFAULT_BUDGET_MODELS = ["deepseek-chat", "gpt-4o-mini", "llama-3.1-70b-versatile"]


class BYOKHandler:
    """
    Handler for LLM interactions using BYOK system with intelligent cost optimization.
    Automatically routes queries to the most cost-effective provider based on complexity and dynamic pricing.
    """
    def __init__(self, workspace_id: str = "default", provider_id: str = "auto"):
        self.workspace_id = workspace_id
        self.default_provider_id = provider_id if provider_id != "auto" else None
        self.byok_manager = get_byok_manager()
        self.pricing_fetcher = get_pricing_fetcher()
        self.clients: Dict[str, Any] = {}

    def get_client(self, provider_id: str, async_client: bool = True) -> Union[OpenAI, AsyncOpenAI, Any]:
        """
        Get an initialized client for the specific provider.
        Supports OpenAI, Anthropic, DeepSeek, Groq, Moonshot, etc.
        """
        if provider_id in self.clients:
            return self.clients[provider_id]

        api_key = self.byok_manager.get_api_key(provider_id)
        if not api_key:
            # Fallback to env
            api_key = os.getenv(f"{provider_id.upper()}_API_KEY")
        
        if not api_key:
            logger.error(f"No API key found for {provider_id}")
            return None

        provider_config = self.byok_manager.providers.get(provider_id)
        base_url = provider_config.base_url if provider_config else None

        client = None
        try:
            if provider_id == "anthropic":
                # Native Anthropic Client
                if async_client:
                    client = anthropic.AsyncAnthropic(api_key=api_key)
                else:
                    client = anthropic.Anthropic(api_key=api_key)
            elif provider_id == "google":
                # Google via OpenAI Compat
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                if async_client:
                    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                else:
                    client = OpenAI(api_key=api_key, base_url=base_url)
            else:
                # Generic OpenAI Compatible (DeepSeek, Groq, OpenAI, Moonshot)
                if provider_id == "deepseek" and not base_url:
                    base_url = "https://api.deepseek.com/v1"
                elif provider_id == "groq" and not base_url:
                    base_url = "https://api.groq.com/openai/v1"

                if async_client:
                    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                else:
                    client = OpenAI(api_key=api_key, base_url=base_url)

            if client:
                self.clients[provider_id] = client
                logger.debug(f"Initialized client for {provider_id}")
                return client

        except Exception as e:
            logger.error(f"Failed to initialize client for {provider_id}: {e}")
            return None

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
        reasoning_keywords = ["step by step", "analyze", "compare", "evaluate", "synthesize", "explain why", "react", "loop"]
        if any(kw in prompt_lower for kw in reasoning_keywords):
            complexity_score += 1
        
        # Simple task indicators (reduce complexity)
        simple_keywords = ["summarize", "translate", "list", "what is", "who is", "define"]
        if any(kw in prompt_lower for kw in simple_keywords):
            complexity_score -= 1
        
        # Task type override
        if task_type:
            if task_type in ["code", "analysis", "reasoning", "react_loop"]:
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
        estimated_tokens: int = 0
    ) -> tuple[str, str]:
        """
        Get the optimal provider and model based on complexity, Dynamic Pricing, and Context Window.
        Returns (provider_id, model_name).
        """
        # 1. Check if user forced a provider
        if self.default_provider_id:
            if self.default_provider_id == "deepseek":
                return "deepseek", "deepseek-chat"
            if self.default_provider_id == "openai":
                return "openai", "gpt-4o" if complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED] else "gpt-4o-mini"
            return self.default_provider_id, "default"

        # 2. Determine Candidate Models based on Complexity
        candidates = []
        
        if complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]:
            # Reasoning/High-Performance Tier
            candidates = self._get_reasoning_candidates(estimated_tokens)
        else:
            # Budget/Simple Tier
            candidates = self._get_budget_candidates(estimated_tokens)

        # 3. Filter Candidates by Available API Keys
        available_candidates = []
        for cand in candidates:
            provider = self._infer_provider_from_model(cand['model'])
            if self.byok_manager.get_api_key(provider):
                available_candidates.append({**cand, "provider": provider})

        if not available_candidates:
            # If nothing fits, check for fallback (ignore context limit constraint if desperate or allow truncation)
            # Or just check if we filtered everything out due to context
            # We'll try reasoning candidates again without token limit just to find *something*
            if estimated_tokens > 0:
                 candidates = self._get_reasoning_candidates(0)
                 for cand in candidates:
                    provider = self._infer_provider_from_model(cand['model'])
                    if self.byok_manager.get_api_key(provider):
                        available_candidates.append({**cand, "provider": provider})

            if not available_candidates:
                # Absolute Fallback
                active_keys = [p for p in self.byok_manager.providers.keys() if self.byok_manager.get_api_key(p)]
                if not active_keys:
                    raise ValueError("No active AI provider keys found.")

                fallback_provider = active_keys[0]
                fallback_model = "gpt-4o" if fallback_provider == "openai" else "deepseek-chat" if fallback_provider == "deepseek" else "default"
                logger.warning(f"No optimal candidates found. Falling back to {fallback_provider}/{fallback_model}")
                return fallback_provider, fallback_model

        # 4. Sort by Price (Cheapest First)
        available_candidates.sort(key=lambda x: x.get('input_cost_per_token', 999))
        
        best_choice = available_candidates[0]
        logger.info(f"Optimal Model Selected: {best_choice['model']} ({best_choice['provider']}) - Cost: ${best_choice.get('input_cost_per_token', 0):.8f}/token - Context: {best_choice.get('max_tokens', 'unknown')}")
        
        return best_choice['provider'], best_choice['model']

    def _get_reasoning_candidates(self, min_context: int = 0) -> List[Dict[str, Any]]:
        """
        Get list of candidate models suitable for reasoning, with current pricing and context validation.
        """
        target_models = ["deepseek-chat", "gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro", "llama-3.1-70b"]
        
        candidates = []
        for model in target_models:
            price = self.pricing_fetcher.get_model_price(model)
            if price:
                max_tokens = price.get("max_input_tokens") or price.get("max_tokens") or 128000
                if max_tokens >= min_context:
                    candidates.append({"model": model, **price})
            else:
                # Default fallback context for known models
                default_context = 128000 if "gpt-4" in model or "claude" in model or "deepseek" in model else 8000
                if default_context >= min_context:
                    fallback_cost = 0.00000014 if "deepseek" in model else 0.000005
                    candidates.append({"model": model, "input_cost_per_token": fallback_cost, "max_tokens": default_context})

        return candidates

    def _get_budget_candidates(self, min_context: int = 0) -> List[Dict[str, Any]]:
        """
        Get list of cheapest models for simple tasks with context validation.
        """
        cheapest = self.pricing_fetcher.get_cheapest_models(limit=15)
        supported_substrings = ["deepseek", "gpt-4o-mini", "haiku", "llama-3", "flash"]
        valid_candidates = []

        for cand in cheapest:
            name = cand['model'].lower()
            if any(s in name for s in supported_substrings):
                max_tokens = cand.get("max_input_tokens") or cand.get("max_tokens") or 8000 # Assume small if unknown
                if max_tokens >= min_context:
                    valid_candidates.append(cand)

        # Ensure DeepSeek is in there
        if not any("deepseek" in c['model'] for c in valid_candidates):
             deepseek_price = self.pricing_fetcher.get_model_price("deepseek-chat")
             if deepseek_price:
                 max_tokens = deepseek_price.get("max_input_tokens", 128000)
                 if max_tokens >= min_context:
                     valid_candidates.append({"model": "deepseek-chat", **deepseek_price})

        return valid_candidates

    def _infer_provider_from_model(self, model_name: str) -> str:
        """Helper to map model name to provider ID"""
        m = model_name.lower()
        if "gpt" in m or "o1" in m: return "openai"
        if "claude" in m: return "anthropic"
        if "deepseek" in m: return "deepseek"
        if "gemini" in m: return "google"
        if "llama" in m or "mixtral" in m: return "groq"
        if "kimi" in m: return "moonshot"
        return "openai" # Default fallback
