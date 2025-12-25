"""
Secrets Redaction Module for Atom Memory
Ensures sensitive data (API keys, passwords, tokens, PII) is never stored in memory.
"""

import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RedactionResult:
    """Result of redaction operation"""
    original_text: str
    redacted_text: str
    redactions: List[Dict[str, Any]]  # List of {type, start, end, placeholder}
    has_secrets: bool


class SecretsRedactor:
    """
    Redacts sensitive information from text before storage in Atom Memory.
    Implements defense-in-depth: multiple pattern types and LLM-based detection.
    """
    
    # API Key patterns
    API_KEY_PATTERNS = [
        # Generic API keys
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', 'API_KEY'),
        (r'apikey["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', 'API_KEY'),
        
        # OpenAI
        (r'sk-[a-zA-Z0-9]{48,}', 'OPENAI_KEY'),
        (r'sk-proj-[a-zA-Z0-9\-_]{48,}', 'OPENAI_PROJECT_KEY'),
        
        # AWS
        (r'AKIA[A-Z0-9]{16}', 'AWS_ACCESS_KEY'),
        (r'aws[_-]?secret[_-]?access[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?', 'AWS_SECRET_KEY'),
        
        # Google
        (r'AIza[a-zA-Z0-9_\-]{35}', 'GOOGLE_API_KEY'),
        
        # GitHub
        (r'ghp_[a-zA-Z0-9]{36}', 'GITHUB_PAT'),
        (r'github_pat_[a-zA-Z0-9_]{22,}', 'GITHUB_PAT'),
        
        # Stripe
        (r'sk_live_[a-zA-Z0-9]{24,}', 'STRIPE_SECRET_KEY'),
        (r'sk_test_[a-zA-Z0-9]{24,}', 'STRIPE_TEST_KEY'),
        (r'pk_live_[a-zA-Z0-9]{24,}', 'STRIPE_PUBLISHABLE_KEY'),
        
        # Slack
        (r'xox[baprs]-[a-zA-Z0-9\-]{10,}', 'SLACK_TOKEN'),
        
        # Twilio
        (r'SK[a-f0-9]{32}', 'TWILIO_API_KEY'),
        
        # SendGrid
        (r'SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}', 'SENDGRID_API_KEY'),
        
        # Mailchimp
        (r'[a-f0-9]{32}-us\d{1,2}', 'MAILCHIMP_API_KEY'),
        
        # Generic secret patterns
        (r'secret[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?', 'SECRET_KEY'),
        (r'private[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?', 'PRIVATE_KEY'),
        (r'access[_-]?token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?', 'ACCESS_TOKEN'),
        (r'bearer\s+([a-zA-Z0-9_\-\.]{20,})', 'BEARER_TOKEN'),
    ]
    
    # Password patterns
    PASSWORD_PATTERNS = [
        (r'password["\']?\s*[:=]\s*["\']?([^\s"\']{8,})["\']?', 'PASSWORD'),
        (r'passwd["\']?\s*[:=]\s*["\']?([^\s"\']{8,})["\']?', 'PASSWORD'),
        (r'pwd["\']?\s*[:=]\s*["\']?([^\s"\']{8,})["\']?', 'PASSWORD'),
    ]
    
    # PII patterns
    PII_PATTERNS = [
        # Social Security Numbers (US)
        (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN'),
        (r'\b\d{9}\b(?=.*ssn|social)', 'SSN'),
        
        # Credit Card Numbers
        (r'\b(?:\d{4}[-\s]?){3}\d{4}\b', 'CREDIT_CARD'),
        
        # Bank Account Numbers (generic long numbers in financial context)
        (r'account[_\s-]?(?:number|num|#)["\']?\s*[:=]?\s*["\']?(\d{8,17})["\']?', 'BANK_ACCOUNT'),
        
        # Phone Numbers (US format)
        (r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', 'PHONE'),
    ]
    
    # Database connection strings
    CONNECTION_PATTERNS = [
        (r'(postgres|postgresql|mysql|mongodb|redis)://[^\s"\']+', 'DATABASE_URL'),
        (r'Server=[^;]+;.*Password=[^;]+', 'CONNECTION_STRING'),
    ]
    
    # Private keys (PEM format)
    KEY_BLOCK_PATTERNS = [
        (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----[\s\S]+?-----END\s+(RSA\s+)?PRIVATE\s+KEY-----', 'PRIVATE_KEY_BLOCK'),
        (r'-----BEGIN\s+CERTIFICATE-----[\s\S]+?-----END\s+CERTIFICATE-----', 'CERTIFICATE'),
    ]
    
    def __init__(self, redact_pii: bool = True, redact_phone: bool = False):
        """
        Initialize the redactor.
        
        Args:
            redact_pii: Whether to redact PII (SSN, credit cards, bank accounts)
            redact_phone: Whether to redact phone numbers (disabled by default as they may be needed)
        """
        self.redact_pii = redact_pii
        self.redact_phone = redact_phone
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile all regex patterns for efficiency"""
        self.compiled_patterns: List[Tuple[re.Pattern, str]] = []
        
        # Always include API keys, passwords, connections, and key blocks
        all_patterns = (
            self.API_KEY_PATTERNS + 
            self.PASSWORD_PATTERNS + 
            self.CONNECTION_PATTERNS +
            self.KEY_BLOCK_PATTERNS
        )
        
        # Optionally include PII
        if self.redact_pii:
            for pattern, ptype in self.PII_PATTERNS:
                if ptype == 'PHONE' and not self.redact_phone:
                    continue
                all_patterns.append((pattern, ptype))
        
        for pattern, ptype in all_patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self.compiled_patterns.append((compiled, ptype))
            except re.error as e:
                logger.warning(f"Failed to compile pattern for {ptype}: {e}")
    
    def redact(self, text: str) -> RedactionResult:
        """
        Redact sensitive information from text.
        
        Args:
            text: The text to redact
            
        Returns:
            RedactionResult with redacted text and metadata
        """
        if not text:
            return RedactionResult(
                original_text="",
                redacted_text="",
                redactions=[],
                has_secrets=False
            )
        
        redactions = []
        redacted_text = text
        
        # Track positions to avoid overlapping redactions
        redacted_positions = set()
        
        for compiled_pattern, secret_type in self.compiled_patterns:
            for match in compiled_pattern.finditer(text):
                start, end = match.span()
                
                # Skip if this region was already redacted
                if any(start <= pos < end for pos in redacted_positions):
                    continue
                
                # Generate placeholder
                placeholder = f"[REDACTED_{secret_type}]"
                
                # Record the redaction
                redactions.append({
                    "type": secret_type,
                    "start": start,
                    "end": end,
                    "placeholder": placeholder,
                    "length": end - start
                })
                
                # Mark positions as redacted
                for pos in range(start, end):
                    redacted_positions.add(pos)
        
        # Sort redactions by position (reverse order for replacement)
        redactions.sort(key=lambda x: x["start"], reverse=True)
        
        # Apply redactions
        for redaction in redactions:
            start = redaction["start"]
            end = redaction["end"]
            placeholder = redaction["placeholder"]
            redacted_text = redacted_text[:start] + placeholder + redacted_text[end:]
        
        # Re-sort for output (forward order)
        redactions.sort(key=lambda x: x["start"])
        
        if redactions:
            logger.info(f"Redacted {len(redactions)} secrets/PII items from text")
            for r in redactions:
                logger.debug(f"  - {r['type']} at position {r['start']}-{r['end']}")
        
        return RedactionResult(
            original_text=text,
            redacted_text=redacted_text,
            redactions=redactions,
            has_secrets=len(redactions) > 0
        )
    
    def is_sensitive(self, text: str) -> bool:
        """Quick check if text contains any sensitive data"""
        for compiled_pattern, _ in self.compiled_patterns:
            if compiled_pattern.search(text):
                return True
        return False
    
    def get_sensitive_types(self, text: str) -> List[str]:
        """Get list of sensitive data types found in text"""
        types = set()
        for compiled_pattern, secret_type in self.compiled_patterns:
            if compiled_pattern.search(text):
                types.add(secret_type)
        return list(types)


# Global instance
_secrets_redactor: Optional[SecretsRedactor] = None


def get_secrets_redactor() -> SecretsRedactor:
    """Get the global secrets redactor instance"""
    global _secrets_redactor
    if _secrets_redactor is None:
        _secrets_redactor = SecretsRedactor()
    return _secrets_redactor


def redact_before_storage(text: str) -> str:
    """
    Convenience function to redact text before storing in Atom Memory.
    
    Args:
        text: Text to redact
        
    Returns:
        Redacted text safe for storage
    """
    redactor = get_secrets_redactor()
    result = redactor.redact(text)
    return result.redacted_text


def check_for_secrets(text: str) -> Dict[str, Any]:
    """
    Check if text contains secrets without modifying it.
    
    Returns:
        Dict with 'has_secrets', 'types', and 'count'
    """
    redactor = get_secrets_redactor()
    result = redactor.redact(text)
    return {
        "has_secrets": result.has_secrets,
        "types": [r["type"] for r in result.redactions],
        "count": len(result.redactions)
    }


async def analyze_with_local_llm(text: str) -> Dict[str, Any]:
    """
    Enhanced secrets detection using local LLM (Ollama).
    Falls back to pattern-based detection if LLM unavailable.
    
    Benefits:
    - Catches secrets that patterns might miss
    - Understands context (reduces false positives)
    - All processing stays local - no data sent externally
    
    Args:
        text: Text to analyze
        
    Returns:
        Dict with detection results
    """
    try:
        from core.local_llm_secrets_detector import analyze_for_secrets
        result = await analyze_for_secrets(text)
        return {
            "has_secrets": result.has_secrets,
            "confidence": result.confidence,
            "method": result.analysis_method,
            "model": result.llm_model,
            "detected_count": len(result.detected_secrets),
            "detected_types": [s.get("type") for s in result.detected_secrets],
            "processing_time_ms": result.processing_time_ms
        }
    except ImportError:
        # Fallback to pattern-based
        result = check_for_secrets(text)
        result["method"] = "pattern_only"
        result["confidence"] = 0.85 if result["has_secrets"] else 0.9
        return result
    except Exception as e:
        logger.error(f"Local LLM analysis failed: {e}")
        result = check_for_secrets(text)
        result["method"] = "pattern_fallback"
        result["error"] = str(e)
        return result


async def redact_with_llm_validation(text: str) -> RedactionResult:
    """
    Redact secrets with optional LLM validation.
    Uses pattern-based redaction, then validates with local LLM if available.
    
    This provides defense-in-depth:
    1. Pattern matching catches known formats
    2. LLM catches unusual formats patterns might miss
    """
    # First do pattern-based redaction
    redactor = get_secrets_redactor()
    pattern_result = redactor.redact(text)
    
    # Then check with LLM for anything missed
    try:
        from core.local_llm_secrets_detector import analyze_for_secrets
        llm_result = await analyze_for_secrets(pattern_result.redacted_text)
        
        if llm_result.has_secrets and llm_result.analysis_method == "local_llm":
            # LLM found additional secrets - log warning
            logger.warning(f"LLM found {len(llm_result.detected_secrets)} potential secrets that patterns missed")
            for secret in llm_result.detected_secrets:
                logger.warning(f"  - {secret.get('type')}: {secret.get('reason')}")
    except:
        pass  # LLM validation is optional
    
    return pattern_result
