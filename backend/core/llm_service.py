"""
LLM service wrapper for backward compatibility.

This module provides a compatibility layer for imports expecting core.llm_service.
The actual LLM handling is implemented in core.llm.byok_handler.
"""

from core.llm.byok_handler import BYOKHandler

# Export BYOKHandler as LLMService for backward compatibility
LLMService = BYOKHandler

__all__ = ['LLMService']
