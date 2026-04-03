"""
Token counting and context validation for accurate LLM request sizing.

Provides model-specific token counting with tiktoken integration where available,
and context window validation to prevent requests from exceeding model limits.
"""

from __future__ import annotations

import re
import logging
from enum import Enum
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Try to import tiktoken for accurate token counting
try:
    import tiktoken

    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    logger.warning("tiktoken not installed, using character-based approximation")


class ModelFamily(Enum):
    """LLM provider families for token counting."""

    OPENAI = "openai"  # cl100k_base encoding
    ANTHROPIC = "anthropic"  # cl100k_base for Claude 3
    COHERE = "cohere"  # custom tokenizer approximation
    GOOGLE = "google"  # approximation: 1 token ≈ 4 characters
    FALLBACK = "fallback"  # generic: 1 token ≈ 4 characters


class TokenCounter:
    """
    Accurate token counting for different model families.

    Uses tiktoken for OpenAI/Anthropic models when available,
    with character-based fallback for other providers.
    """

    # Encoding cache for tiktoken
    _encoding_cache: Dict[ModelFamily, Any] = {}

    def count_tokens(self, text: str, model: str) -> int:
        """
        Count tokens for text using model-specific encoding.

        Args:
            text: Input text to count
            model: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet")

        Returns:
            Token count
        """
        family = self.get_model_family(model)
        return self.count_tokens_by_family(text, family)

    def count_tokens_by_family(self, text: str, family: ModelFamily) -> int:
        """
        Count tokens using family-specific encoding.

        Args:
            text: Input text to count
            family: Model family enum

        Returns:
            Token count
        """
        if not text:
            return 0

        # Use tiktoken for OpenAI/Anthropic if available
        if HAS_TIKTOKEN and family in [ModelFamily.OPENAI, ModelFamily.ANTHROPIC]:
            try:
                encoding = self._get_encoding(family)
                return len(encoding.encode(text))
            except Exception as e:
                logger.warning(f"tiktoken encoding failed: {e}, falling back to approximation")

        # Fallback to character-based approximation
        return self.estimate_tokens(text)

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate tokens using character approximation (1 token ≈ 4 chars).

        Args:
            text: Input text to estimate

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        return len(text) // 4

    def get_model_family(self, model: str) -> ModelFamily:
        """
        Detect model family from model name.
        """
        model_lower = model.lower()

        # OpenAI models
        if any(
            pattern in model_lower
            for pattern in ["gpt-", "o1-", "o3-", "text-embedding-"]
        ):
            return ModelFamily.OPENAI

        # Anthropic models
        if "claude-" in model_lower:
            return ModelFamily.ANTHROPIC

        # Cohere models
        if any(pattern in model_lower for pattern in ["command-", "embed-"]):
            return ModelFamily.COHERE

        # Google models
        if "gemini-" in model_lower:
            return ModelFamily.GOOGLE

        # Default fallback
        return ModelFamily.FALLBACK

    def _get_encoding(self, family: ModelFamily) -> Any:
        """
        Get cached tiktoken encoding for model family.
        """
        if family not in self._encoding_cache:
            if family == ModelFamily.OPENAI:
                self._encoding_cache[family] = tiktoken.get_encoding("cl100k_base")
            elif family == ModelFamily.ANTHROPIC:
                self._encoding_cache[family] = tiktoken.get_encoding("cl100k_base")
            else:
                raise ValueError(f"No tiktoken encoding for family: {family}")

        return self._encoding_cache[family]


class ContextValidator:
    """
    Context window validation and truncation for LLM requests.
    """

    # Model context limits (tokens)
    MODEL_CONTEXT_LIMITS: Dict[str, int] = {
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4-turbo": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        "o1": 200000,
        "o3": 200000,
        "claude-3-5-sonnet": 200000,
        "claude-3-5-haiku": 200000,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        "gemini-1.5-pro": 2800000,
        "gemini-1.5-flash": 2800000,
        "command-r": 128000,
        "command-r-plus": 128000,
        "text-embedding-3-large": 8191,
        "text-embedding-3-small": 8191,
        "text-embedding-ada-002": 8191,
    }

    DEFAULT_CONTEXT_LIMIT: int = 128000

    def __init__(self):
        """Initialize context validator with token counter."""
        self.token_counter = TokenCounter()

    def validate_request_fits(
        self, text: str, model: str, max_tokens: int = 0
    ) -> bool:
        """Check if request fits within model context window."""
        context_limit = self.get_model_context_limit(model)
        input_tokens = self.token_counter.count_tokens(text, model)
        return input_tokens + max_tokens <= context_limit

    def get_model_context_limit(self, model: str) -> int:
        """Get context window size for model."""
        model_lower = model.lower()
        for known_model, limit in self.MODEL_CONTEXT_LIMITS.items():
            if known_model.lower() == model_lower:
                return limit
        sorted_keys = sorted(self.MODEL_CONTEXT_LIMITS.keys(), key=len, reverse=True)
        for known_model in sorted_keys:
            if model_lower.startswith(known_model):
                return self.MODEL_CONTEXT_LIMITS[known_model]
        return self.DEFAULT_CONTEXT_LIMIT

    def truncate_to_fit(
        self,
        text: str,
        model: str,
        max_tokens: int = 0,
        reserve_for_output: int = 0,
    ) -> str:
        """Truncate text to fit within context window."""
        context_limit = self.get_model_context_limit(model)
        available_tokens = context_limit - reserve_for_output
        if max_tokens > 0:
            available_tokens = min(available_tokens, max_tokens)
        current_tokens = self.token_counter.count_tokens(text, model)
        if current_tokens <= available_tokens:
            return text
        target_ratio = (available_tokens * 0.95) / current_tokens
        target_chars = int(len(text) * target_ratio)
        truncated = text[:target_chars]
        truncated = self._truncate_at_boundary(truncated)
        return truncated

    def estimate_request_tokens(self, messages: List[Dict], model: str) -> int:
        """Estimate tokens for chat message list."""
        total_tokens = 0
        for message in messages:
            content = message.get("content", "")
            total_tokens += self.token_counter.count_tokens(content, model)
            total_tokens += 10
        return total_tokens

    def _truncate_at_boundary(self, text: str) -> str:
        """Try to truncate at sentence/word boundary."""
        if not text:
            return text
        sentence_ends = [". ", "! ", "? ", "\n"]
        for end in reversed(sentence_ends):
            last_pos = text.rfind(end)
            if last_pos > len(text) * 0.8:
                return text[: last_pos + len(end)]
        last_space = text.rfind(" ")
        if last_space > len(text) * 0.9:
            return text[:last_space]
        return text
