"""
Local LLM Secrets Detector
Uses Ollama (local LLM) for enhanced secrets/PII detection.
Ensures sensitive data NEVER leaves the local environment.

This module enhances the pattern-based SecretsRedactor with AI-powered
semantic detection that can catch secrets patterns might miss.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LocalLLMProvider(str, Enum):
    """Supported local LLM providers"""
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    HUGGINGFACE = "huggingface"


@dataclass
class SecretsAnalysis:
    """Result of LLM-based secrets analysis"""
    text_preview: str  # First 100 chars of analyzed text
    has_secrets: bool
    confidence: float  # 0.0 to 1.0
    detected_secrets: List[Dict[str, Any]]
    analysis_method: str  # "local_llm" or "fallback_pattern"
    llm_model: Optional[str] = None
    processing_time_ms: Optional[float] = None


class LocalLLMSecretsDetector:
    """
    AI-powered secrets detection using local LLMs.
    
    Benefits over pure regex:
    - Can detect secrets in unusual formats
    - Understands context (is this really a password or just the word 'password'?)
    - Can identify novel/custom secret patterns
    - All processing stays local - no data sent externally
    
    Requires:
    - Ollama installed and running locally (ollama serve)
    - A model like llama2, mistral, or phi3 pulled
    """
    
    # Recommended models for secrets detection (fast and capable)
    RECOMMENDED_MODELS = [
        "llama3.2:1b",  # Very fast, good for simple detection
        "phi3:mini",    # Fast, good reasoning
        "mistral:7b",   # Good balance of speed/capability
        "llama3:8b",    # High capability
    ]
    
    # Detection prompt template
    DETECTION_PROMPT = """You are a security expert analyzing text for sensitive data. 
Identify any of the following types of secrets or PII:

1. API Keys (any format: sk_xxx, AKIA..., etc.)
2. Passwords or password-like strings
3. Private Keys (RSA, PEM, SSH)
4. Access Tokens (Bearer, OAuth, JWT)
5. Database connection strings
6. Social Security Numbers
7. Credit Card Numbers
8. Bank Account Numbers
9. Phone Numbers that appear to be personal
10. Any other credentials or secrets

TEXT TO ANALYZE:
```
{text}
```

Respond with ONLY a JSON object (no other text):
{{
  "has_secrets": true/false,
  "confidence": 0.0-1.0,
  "secrets": [
    {{"type": "api_key|password|token|ssn|credit_card|phone|other", "snippet": "first 10 chars...", "reason": "why this is a secret"}}
  ]
}}

If no secrets found, return: {{"has_secrets": false, "confidence": 0.95, "secrets": []}}"""

    def __init__(
        self,
        provider: LocalLLMProvider = LocalLLMProvider.OLLAMA,
        model: Optional[str] = None,
        ollama_host: str = "http://localhost:11434",
        timeout_seconds: int = 30,
        fallback_to_pattern: bool = True
    ):
        self.provider = provider
        self.model = model
        self.ollama_host = ollama_host
        self.timeout_seconds = timeout_seconds
        self.fallback_to_pattern = fallback_to_pattern
        self._client = None
        self._available_models: List[str] = []
        
        # Initialize pattern-based fallback
        try:
            from core.secrets_redactor import get_secrets_redactor
            self.pattern_redactor = get_secrets_redactor()
        except ImportError:
            self.pattern_redactor = None
    
    async def initialize(self) -> bool:
        """Initialize connection to local LLM"""
        if self.provider == LocalLLMProvider.OLLAMA:
            return await self._init_ollama()
        else:
            logger.warning(f"Provider {self.provider} not yet implemented")
            return False
    
    async def _init_ollama(self) -> bool:
        """Initialize Ollama client"""
        try:
            import ollama
            self._client = ollama.Client(host=self.ollama_host)
            
            # List available models
            models_response = self._client.list()
            self._available_models = [m['name'] for m in models_response.get('models', [])]
            
            # Auto-select model if not specified
            if not self.model:
                self.model = self._select_best_model()
            
            if self.model:
                logger.info(f"Local LLM initialized: {self.model} via Ollama")
                return True
            else:
                logger.warning("No suitable model found in Ollama")
                return False
                
        except ImportError:
            logger.warning("Ollama package not installed. Install with: pip install ollama")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Ollama: {e}")
            return False
    
    def _select_best_model(self) -> Optional[str]:
        """Select the best available model for secrets detection"""
        if not self._available_models:
            return None
        
        # Prefer recommended models in order
        for recommended in self.RECOMMENDED_MODELS:
            for available in self._available_models:
                if recommended.split(':')[0] in available:
                    return available
        
        # Fallback to first available
        return self._available_models[0] if self._available_models else None
    
    async def analyze_text(self, text: str, max_chars: int = 4000) -> SecretsAnalysis:
        """
        Analyze text for secrets using local LLM.
        
        Args:
            text: Text to analyze
            max_chars: Maximum characters to send to LLM (for performance)
        
        Returns:
            SecretsAnalysis with detection results
        """
        import time
        start_time = time.time()
        
        # Truncate for performance
        truncated_text = text[:max_chars] if len(text) > max_chars else text
        preview = text[:100] + "..." if len(text) > 100 else text
        
        # Try LLM-based detection first
        if self._client and self.model:
            try:
                result = await self._llm_detect(truncated_text)
                result.text_preview = preview
                result.processing_time_ms = (time.time() - start_time) * 1000
                return result
            except Exception as e:
                logger.warning(f"LLM detection failed, falling back to pattern: {e}")
        
        # Fallback to pattern-based detection
        if self.fallback_to_pattern and self.pattern_redactor:
            return self._pattern_detect(text, preview, start_time)
        
        # No detection available
        return SecretsAnalysis(
            text_preview=preview,
            has_secrets=False,
            confidence=0.0,
            detected_secrets=[],
            analysis_method="none",
            processing_time_ms=(time.time() - start_time) * 1000
        )
    
    async def _llm_detect(self, text: str) -> SecretsAnalysis:
        """Perform LLM-based secrets detection"""
        prompt = self.DETECTION_PROMPT.format(text=text)
        
        # Call Ollama
        response = self._client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1, "num_predict": 500}
        )
        
        content = response.get("message", {}).get("content", "")
        
        # Parse JSON response
        try:
            # Clean up response - extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Find JSON object
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                content = content[start:end]
            
            result = json.loads(content)
            
            return SecretsAnalysis(
                text_preview="",
                has_secrets=result.get("has_secrets", False),
                confidence=result.get("confidence", 0.5),
                detected_secrets=result.get("secrets", []),
                analysis_method="local_llm",
                llm_model=self.model
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # If LLM said something about secrets, assume there might be some
            has_secrets = any(word in content.lower() for word in ["secret", "key", "password", "token", "credential"])
            return SecretsAnalysis(
                text_preview="",
                has_secrets=has_secrets,
                confidence=0.3,
                detected_secrets=[],
                analysis_method="local_llm_unparsed",
                llm_model=self.model
            )
    
    def _pattern_detect(self, text: str, preview: str, start_time: float) -> SecretsAnalysis:
        """Fallback to pattern-based detection"""
        import time
        
        if not self.pattern_redactor:
            return SecretsAnalysis(
                text_preview=preview,
                has_secrets=False,
                confidence=0.0,
                detected_secrets=[],
                analysis_method="fallback_unavailable"
            )
        
        result = self.pattern_redactor.redact(text)
        
        detected = [
            {
                "type": r["type"],
                "snippet": r.get("matched_pattern", "")[:10] + "...",
                "reason": f"Matched {r['type']} pattern"
            }
            for r in result.redactions
        ]
        
        return SecretsAnalysis(
            text_preview=preview,
            has_secrets=result.has_secrets,
            confidence=0.85 if result.has_secrets else 0.9,
            detected_secrets=detected,
            analysis_method="fallback_pattern",
            processing_time_ms=(time.time() - start_time) * 1000
        )
    
    def get_available_models(self) -> List[str]:
        """Get list of available Ollama models"""
        return self._available_models
    
    def get_current_model(self) -> Optional[str]:
        """Get currently selected model"""
        return self.model
    
    def set_model(self, model: str) -> bool:
        """Set the model to use for detection"""
        if model in self._available_models:
            self.model = model
            logger.info(f"Model set to: {model}")
            return True
        else:
            logger.warning(f"Model {model} not available")
            return False


# Global instance
_local_detector: Optional[LocalLLMSecretsDetector] = None
_initialized = False


async def get_local_secrets_detector() -> LocalLLMSecretsDetector:
    """Get or create the local LLM secrets detector"""
    global _local_detector, _initialized
    
    if _local_detector is None:
        _local_detector = LocalLLMSecretsDetector()
    
    if not _initialized:
        _initialized = await _local_detector.initialize()
    
    return _local_detector


async def analyze_for_secrets(text: str) -> SecretsAnalysis:
    """
    Convenience function to analyze text for secrets.
    Uses local LLM if available, falls back to pattern matching.
    """
    detector = await get_local_secrets_detector()
    return await detector.analyze_text(text)


def is_ollama_available() -> bool:
    """Check if Ollama is installed and has models"""
    try:
        import ollama
        client = ollama.Client()
        models = client.list()
        return len(models.get('models', [])) > 0
    except Exception as e:
        logger.debug(f"Ollama not available: {e}")
        return False
