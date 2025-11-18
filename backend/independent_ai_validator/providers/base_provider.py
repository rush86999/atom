#!/usr/bin/env python3
"""
Base LLM Provider Interface for Independent AI Validator
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import json

logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    """Standard response structure for all LLM providers"""
    content: str
    confidence: float
    reasoning: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    response_time: Optional[float] = None

@dataclass
class ValidationRequest:
    """Standard request structure for validation"""
    claim: str
    evidence: Dict[str, Any]
    claim_type: str
    context: Optional[Dict[str, Any]] = None
    validation_criteria: Optional[List[str]] = None

class BaseLLMProvider(ABC):
    """
    Abstract base class for all LLM providers
    """

    def __init__(self, api_key: str, name: str, weight: float = 1.0):
        self.api_key = api_key
        self.name = name
        self.weight = weight
        self.is_available = False

    @abstractmethod
    async def validate_claim(self, request: ValidationRequest) -> LLMResponse:
        """Validate a marketing claim using the LLM"""
        pass

    @abstractmethod
    async def analyze_evidence(self, evidence: Dict[str, Any], claim: str) -> LLMResponse:
        """Analyze evidence for a claim"""
        pass

    @abstractmethod
    async def check_bias(self, text: str) -> LLMResponse:
        """Check for potential bias in analysis"""
        pass

    async def test_connection(self) -> bool:
        """Test if the provider is accessible"""
        try:
            test_request = ValidationRequest(
                claim="Test claim for connection",
                evidence={"test": "test"},
                claim_type="test"
            )
            response = await self.validate_claim(test_request)
            self.is_available = True
            return True
        except Exception as e:
            logger.error(f"{self.name} connection test failed: {str(e)}")
            self.is_available = False
            return False

    def format_validation_prompt(self, request: ValidationRequest) -> str:
        """Format the validation prompt for the LLM"""
        prompt = f"""
You are an independent AI validator analyzing marketing claims for accuracy and truthfulness.

CLAIM TO VALIDATE: "{request.claim}"
CLAIM TYPE: {request.claim_type}

EVIDENCE PROVIDED:
{self._format_evidence(request.evidence)}

VALIDATION CRITERIA:
{', '.join(request.validation_criteria or ['Accuracy', 'Truthfulness', 'Evidence Support'])}

INSTRUCTIONS:
1. Analyze the claim objectively without bias
2. Evaluate the strength of the evidence
3. Determine if the claim is fully, partially, or not substantiated
4. Provide a confidence score (0-100%) for your assessment
5. Explain your reasoning clearly

RESPONSE FORMAT:
- Assessment: [VALIDATED/PARTIALLY_VALIDATED/NOT_VALIDATED]
- Confidence: [0-100%]
- Reasoning: [Detailed explanation]
- Evidence Strength: [STRONG/MODERATE/WEAK]
- Recommendations: [Any suggestions for improvement]

Be thorough, objective, and evidence-based in your analysis.
"""
        return prompt

    def _format_evidence(self, evidence: Dict[str, Any]) -> str:
        """Format evidence for display"""
        if not evidence:
            return "No evidence provided"

        formatted = []
        for key, value in evidence.items():
            if isinstance(value, (list, dict)):
                formatted.append(f"{key}: {json.dumps(value, indent=2)}")
            else:
                formatted.append(f"{key}: {value}")

        return "\n".join(formatted)

    def calculate_confidence(self, response_text: str, evidence_strength: str) -> float:
        """Calculate confidence score based on response and evidence"""
        # Extract confidence from response if present
        import re

        confidence_match = re.search(r'Confidence:\s*(\d+)%', response_text)
        if confidence_match:
            return float(confidence_match.group(1)) / 100.0

        # Default confidence based on evidence strength
        strength_scores = {
            'STRONG': 0.9,
            'MODERATE': 0.7,
            'WEAK': 0.4
        }
        return strength_scores.get(evidence_strength.upper(), 0.5)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the provider"""
        try:
            connection_ok = await self.test_connection()

            return {
                'provider': self.name,
                'status': 'healthy' if connection_ok else 'unhealthy',
                'weight': self.weight,
                'connection_test': connection_ok,
                'last_check': self._get_timestamp()
            }
        except Exception as e:
            return {
                'provider': self.name,
                'status': 'error',
                'error': str(e),
                'weight': self.weight,
                'last_check': self._get_timestamp()
            }

    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()

    def __repr__(self) -> str:
        return f"{self.name}(weight={self.weight}, available={self.is_available})"