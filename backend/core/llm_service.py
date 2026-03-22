"""
LLM Service module.

Provides a unified interface for LLM interactions across the platform,
wrapping the advanced BYOKHandler infrastructure.
"""

import json
import logging
import os
import asyncio
from typing import Optional, Dict, Any, List, Union
from enum import Enum

from core.llm.byok_handler import BYOKHandler, QueryComplexity
from core.llm_usage_tracker import llm_usage_tracker

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    GROQ = "groq"
    MINIMAX = "minimax"
    MISTRAL = "mistral"
    QWEN = "qwen"
    COHERE = "cohere"


class LLMModel(str, Enum):
    """Common LLM models"""
    # OpenAI
    GPT4 = "gpt-4"
    GPT4_TURBO = "gpt-4-turbo"
    GPT35_TURBO = "gpt-3.5-turbo"
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    GPT_5_3 = "gpt-5.3"

    # Anthropic
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet"

    # DeepSeek
    DEEPSEEK_V3 = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"

    # Gemini
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"

    # MiniMax
    MINIMAX_2_5 = "minimax-m2.5"


class LLMService:
    """
    LLM Service for managing LLM interactions across the platform.
    Provides unified interface for different LLM providers, wrapping BYOKHandler.
    """

    def __init__(self, workspace_id: str = "default", db=None):
        """
        Args:
            workspace_id: Workspace ID for BYOK resolution.
            db: Optional database session for BYOK/Usage tracking.
        """
        self.workspace_id = workspace_id
        self.handler = BYOKHandler(workspace_id=workspace_id, db_session=db)

    def get_provider(self, model: str) -> LLMProvider:
        """Get the provider for a given model."""
        model_l = model.lower()
        if "gpt" in model_l:
            return LLMProvider.OPENAI
        elif "claude" in model_l:
            return LLMProvider.ANTHROPIC
        elif "deepseek" in model_l:
            return LLMProvider.DEEPSEEK
        elif "gemini" in model_l:
            return LLMProvider.GEMINI
        elif "minimax" in model_l:
            return LLMProvider.MINIMAX
        elif "mistral" in model_l:
            return LLMProvider.MISTRAL
        elif "qwen" in model_l:
            return LLMProvider.QWEN
        elif "command" in model_l:
            return LLMProvider.COHERE
        else:
            return LLMProvider.OPENAI  # Default

    async def generate(
        self,
        prompt: str,
        system_instruction: str = "You are a helpful assistant.",
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """Simple text generation interface."""
        return await self.handler.generate_response(
            prompt=prompt,
            system_instruction=system_instruction,
            model_type=model,
            temperature=temperature,
            **kwargs
        )

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate completion with OpenAI-style messages.
        Maps messages to prompt/system for BYOKHandler.
        """
        # Extract prompt and system from messages
        prompt = ""
        system_instruction = "You are a helpful assistant."
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role == "user":
                prompt = content  # Use the last user message as prompt for now

        # Call underlying handler
        response_text = await self.handler.generate_response(
            prompt=prompt,
            system_instruction=system_instruction,
            model_type=model,
            temperature=temperature,
            **kwargs
        )

        # Approximate token usage (BYOKHandler tracks this internally in DB, 
        # but we return an estimation for immediate API consumers)
        input_tokens = self.estimate_tokens(prompt + system_instruction, model)
        output_tokens = self.estimate_tokens(response_text, model)

        return {
            "success": True,
            "content": response_text,
            "text": response_text, # Parity with some saas callers
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            },
            "model": model,
            "provider": self.get_provider(model).value
        }

    def estimate_tokens(self, text: str, model: str = "gpt-4o-mini") -> int:
        """Estimate token count for text."""
        try:
            import tiktoken
            try:
                # Try to get specific encoding or model match
                if "gpt-4" in model or "gpt-3.5" in model or "o1" in model or "o3" in model:
                    encoding = tiktoken.encoding_for_model("gpt-4o")
                else:
                    encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            # Fallback: ~4 chars per token
            return max(1, len(text) // 4)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost in USD."""
        # Use existing cost utilities if available
        try:
            from core.cost_config import get_llm_cost
            return get_llm_cost(model, input_tokens, output_tokens)
        except ImportError:
            # Fallback hardcoded pricing (approximate)
            if "gpt-4o-mini" in model: return (input_tokens * 0.15 + output_tokens * 0.6) / 1e6
            if "gpt-4o" in model: return (input_tokens * 5.0 + output_tokens * 15.0) / 1e6
            if "deepseek" in model: return (input_tokens * 0.14 + output_tokens * 0.28) / 1e6
            return (input_tokens * 1.0 + output_tokens * 2.0) / 1e6

    async def analyze_proposal(self, proposal: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Governance helper: Analyze an agent proposal for safety and alignment.
        """
        prompt = f"Analyze the following agent proposal for safety, alignment, and efficiency:\n\nPROPOSAL:\n{proposal}"
        if context:
            prompt += f"\n\nCONTEXT:\n{context}"
            
        system = "You are an Agent Governance Auditor. Evaluate the proposal and return a JSON-formatted analysis with 'safe' (bool), 'risk_level' (str), and 'recommendation' (str)."
        
        response = await self.generate(prompt, system_instruction=system, model="quality")
        
        try:
            # Try to extract JSON if the model wrapped it in markdown
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            return json.loads(json_str)
        except Exception:
            return {
                "safe": "Unknown" in response or "safe" in response.lower(),
                "raw_response": response,
                "error": "Failed to parse structured audit"
            }

    def is_available(self) -> bool:
        """Check if LLM service is available by checking for any initialized clients."""
        return len(self.handler.clients) > 0


def get_llm_service(workspace_id: str = "default", db=None) -> LLMService:
    """Factory function to get an LLMService instance."""
    return LLMService(workspace_id=workspace_id, db=db)
