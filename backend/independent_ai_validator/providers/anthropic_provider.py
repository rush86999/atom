#!/usr/bin/env python3
"""
Anthropic Claude Provider Implementation for Independent AI Validator
"""

import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional
import aiohttp
from .base_provider import BaseLLMProvider, ValidationRequest, LLMResponse

logger = logging.getLogger(__name__)

class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude provider for marketing claim validation
    """

    def __init__(self, api_key: str, weight: float = 1.0):
        """Initialize Anthropic Claude provider"""
        super().__init__(api_key, "Anthropic", weight)
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
        self.model = "claude-3-haiku-20240307"  # Haiku model for lightweight analysis
        self.max_tokens = 4000
        self.temperature = 0.1  # Low temperature for consistent analysis

    def get_name(self) -> str:
        """Get provider name"""
        return "Anthropic"

    def get_model(self) -> str:
        """Get model name"""
        return self.model

    async def validate_claim(self, request: ValidationRequest) -> LLMResponse:
        """
        Validate a marketing claim using Anthropic Claude
        """
        start_time = time.time()

        try:
            # Extract evidence JSON safely
            evidence_json = json.dumps(request.evidence, indent=2) if request.evidence else "{}"

            prompt = f"""
You are an independent marketing claim validation expert. Your task is to objectively evaluate the following marketing claim based on the provided evidence.

MARKETING CLAIM:
{request.claim}

CLAIM TYPE: {request.claim_type}

EVIDENCE:
{evidence_json}

VALIDATION CRITERIA:
1. **Truthfulness**: Is the claim factually accurate?
2. **Support**: Does the evidence strongly support the claim?
3. **Precision**: Is the claim specific and not misleading?
4. **Relevance**: Is the evidence relevant to the claim?
5. **Completeness**: Are there important missing details?

ANALYSIS TASK:
1. Evaluate the claim against each validation criterion
2. Assess the strength and quality of the evidence
3. Identify any potential gaps or inconsistencies
4. Determine the overall validity of the claim
5. Provide specific recommendations for improvement

RESPONSE FORMAT:
- **Overall Score**: [0.0-1.0] where 1.0 = fully validated, 0.0 = not validated
- **Evidence Strength**: [STRONG/MODERATE/WEAK/INSUFFICIENT]
- **Confidence**: [0.0-1.0] how confident are you in this assessment
- **Reasoning**: Detailed explanation of your analysis
- **Recommendations**: Specific suggestions for claim improvement
- **Bias Assessment**: Note any potential biases in your analysis

Provide an objective, evidence-based assessment without making assumptions beyond the provided evidence.
"""

            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }

                async with session.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=data,
                    timeout=60
                ) as response:

                    if response.status == 200:
                        result = await response.json()

                        content = result["content"][0]["text"]
                        tokens_used = result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0)

                        # Parse the response to extract confidence score
                        confidence = self._parse_confidence_from_response(content)

                        return LLMResponse(
                            content=content,
                            confidence=confidence,
                            reasoning=f"Anthropic Claude analysis completed successfully",
                            provider=self.name,
                            model=self.model,
                            tokens_used=tokens_used,
                            response_time=time.time() - start_time
                        )

                    else:
                        error_text = await response.text()
                        logger.error(f"Anthropic API error: {response.status} - {error_text}")

                        return LLMResponse(
                            content=f"Error: Unable to process request",
                            confidence=0.0,
                            reasoning=f"Anthropic API error: {response.status}",
                            provider=self.name,
                            model=self.model,
                            response_time=time.time() - start_time
                        )

        except Exception as e:
            logger.error(f"Anthropic provider error: {str(e)}")
            return LLMResponse(
                content=f"Error: Unable to process request",
                confidence=0.0,
                reasoning=f"Anthropic provider error: {str(e)}",
                provider=self.name,
                model=self.model,
                response_time=time.time() - start_time
            )

    def _parse_confidence_from_response(self, response: str) -> float:
        """
        Parse confidence score from Claude's response
        """
        try:
            # Look for Overall Score pattern
            import re

            # Pattern to match "Overall Score: [0.0-1.0]"
            score_match = re.search(r'Overall Score:\s*([0-9]*\.?[0-9]+)', response)
            if score_match:
                score = float(score_match.group(1))
                # Normalize to 0-1 range if it's in percentage
                if score > 1.0:
                    score = score / 100.0
                return min(max(score, 0.0), 1.0)

            # Fallback: look for confidence score
            confidence_match = re.search(r'Confidence:\s*([0-9]*\.?[0-9]+)', response)
            if confidence_match:
                confidence = float(confidence_match.group(1))
                if confidence > 1.0:
                    confidence = confidence / 100.0
                return min(max(confidence, 0.0), 1.0)

            # If no score found, analyze sentiment and return default
            response_lower = response.lower()
            if any(word in response_lower for word in ['strong', 'fully validated', 'excellent']):
                return 0.9
            elif any(word in response_lower for word in ['moderate', 'partially', 'good']):
                return 0.7
            elif any(word in response_lower for word in ['weak', 'insufficient', 'poor']):
                return 0.3
            else:
                return 0.5  # Default neutral score

        except Exception:
            return 0.5  # Default fallback value

    async def analyze_evidence(self, evidence: Dict[str, Any], claim: str) -> LLMResponse:
        """
        Analyze evidence for a claim using Anthropic Claude
        """
        start_time = time.time()

        try:
            evidence_json = json.dumps(evidence, indent=2)
            prompt = f"""
You are an evidence analysis expert. Analyze the provided evidence for the following marketing claim.

CLAIM: "{claim}"

EVIDENCE:
{evidence_json}

ANALYSIS TASK:
1. Evaluate the quality and relevance of the evidence
2. Determine how strongly the evidence supports or contradicts the claim
3. Identify any gaps or inconsistencies in the evidence
4. Assess the reliability and credibility of the evidence sources
5. Provide an overall evidence strength assessment

RESPONSE FORMAT:
- Evidence Strength: [STRONG/MODERATE/WEAK/INSUFFICIENT]
- Support Level: [STRONGLY_SUPPORTS/SUPPORTS/PARTIALLY_SUPPORTS/CONTRADICTS]
- Credibility: [HIGH/MEDIUM/LOW]
- Gaps Identified: [List key gaps if any]
- Overall Assessment: [Detailed analysis]
"""

            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model,
                    "max_tokens": 2000,
                    "temperature": 0.2,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }

                async with session.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=data,
                    timeout=45
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        content = result["content"][0]["text"]
                        tokens_used = result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0)

                        return LLMResponse(
                            content=content,
                            confidence=0.8,
                            reasoning="Evidence analysis completed successfully",
                            provider=self.name,
                            model=self.model,
                            tokens_used=tokens_used,
                            response_time=time.time() - start_time
                        )
                    else:
                        error_text = await response.text()
                        logger.error(f"Anthropic evidence analysis error: {response.status} - {error_text}")

                        return LLMResponse(
                            content=f"Evidence analysis failed",
                            confidence=0.0,
                            reasoning=f"Anthropic API error: {response.status}",
                            provider=self.name,
                            model=self.model,
                            response_time=time.time() - start_time
                        )

        except Exception as e:
            logger.error(f"Anthropic evidence analysis error: {str(e)}")
            return LLMResponse(
                content=f"Evidence analysis failed",
                confidence=0.0,
                reasoning=f"Anthropic provider error: {str(e)}",
                provider=self.name,
                model=self.model,
                response_time=time.time() - start_time
            )

    async def detect_bias(self, content: str) -> Dict[str, Any]:
        """
        Detect bias in marketing claim content using Anthropic Claude
        """
        try:
            prompt = f"""
Analyze the following marketing claim content for potential biases:

CONTENT:
{content}

ANALYSIS TASK:
1. Identify any exaggerated or superlative language
2. Check for unsubstantiated claims
3. Identify potential confirmation bias
4. Assess emotional manipulation tactics
5. Note any vague or ambiguous statements

RESPONSE FORMAT:
- **Bias Detected**: [YES/NO]
- **Bias Types**: [List identified bias types]
- **Severity**: [LOW/MEDIUM/HIGH]
- **Recommendations**: [Suggestions for improvement]
- **Overall Assessment**: [Brief summary]
"""

            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model,
                    "max_tokens": 1500,
                    "temperature": 0.1,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }

                async with session.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=data,
                    timeout=30
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        content = result["content"][0]["text"]

                        # Parse bias detection results
                        bias_detected = "YES" in content.upper() or "BIAS TYPES:" in content
                        severity = "MEDIUM"  # Default

                        if "HIGH" in content.upper():
                            severity = "HIGH"
                        elif "LOW" in content.upper():
                            severity = "LOW"

                        return {
                            "bias_detected": bias_detected,
                            "severity": severity,
                            "analysis": content,
                            "confidence": 0.9
                        }
                    else:
                        return {
                            "bias_detected": False,
                            "severity": "LOW",
                            "analysis": f"Bias analysis failed: API error",
                            "confidence": 0.0
                        }

        except Exception as e:
            logger.error(f"Anthropic bias detection error: {str(e)}")
            return {
                "bias_detected": False,
                "severity": "LOW",
                "analysis": f"Bias analysis failed: {str(e)}",
                "confidence": 0.0
            }

    async def health_check(self) -> bool:
        """
        Check if Anthropic API is accessible and working
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01"
                }

                # Simple health check - get available models
                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=10
                ) as response:

                    return response.status == 200

        except Exception as e:
            logger.error(f"Anthropic health check failed: {str(e)}")
            return False

    async def check_bias(self, text: str) -> LLMResponse:
        """
        Check for potential bias in text using Anthropic Claude
        """
        try:
            prompt = f"""
Analyze the following text for potential biases and provide an objective assessment:

TEXT TO ANALYZE:
{text}

ANALYSIS TASK:
1. Identify any emotional language or exaggeration
2. Check for subjective claims without evidence
3. Identify potential confirmation bias
4. Assess neutrality and objectivity
5. Note any vague or ambiguous statements

RESPONSE FORMAT:
- **Bias Level**: [NONE/LOW/MEDIUM/HIGH]
- **Bias Types**: [List any identified biases]
- **Neutrality Score**: [0.0-1.0 where 1.0 = completely neutral]
- **Recommendations**: [Suggestions for improvement]
- **Analysis**: [Detailed explanation]
"""

            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model,
                    "max_tokens": 2000,
                    "temperature": 0.1,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }

                async with session.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=data,
                    timeout=30
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        content = result["content"][0]["text"]
                        tokens_used = result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0)

                        # Extract neutrality score from response
                        neutrality_score = self._parse_neutrality_score(content)

                        return LLMResponse(
                            content=content,
                            confidence=neutrality_score,
                            reasoning="Bias analysis completed successfully",
                            provider=self.name,
                            model=self.model,
                            tokens_used=tokens_used,
                            response_time=0.0
                        )
                    else:
                        error_text = await response.text()
                        logger.error(f"Anthropic bias check error: {response.status} - {error_text}")

                        return LLMResponse(
                            content=f"Bias analysis failed",
                            confidence=0.5,
                            reasoning=f"Anthropic API error: {response.status}",
                            provider=self.name,
                            model=self.model,
                            response_time=0.0
                        )

        except Exception as e:
            logger.error(f"Anthropic bias check error: {str(e)}")
            return LLMResponse(
                content=f"Bias analysis failed",
                confidence=0.5,
                reasoning=f"Anthropic provider error: {str(e)}",
                provider=self.name,
                model=self.model,
                response_time=0.0
            )

    def _parse_neutrality_score(self, response: str) -> float:
        """
        Parse neutrality score from Claude's response
        """
        try:
            import re

            # Pattern to match "Neutrality Score: [0.0-1.0]"
            score_match = re.search(r'Neutrality Score:\s*([0-9]*\.?[0-9]+)', response)
            if score_match:
                score = float(score_match.group(1))
                return min(max(score, 0.0), 1.0)

            # Fallback: assess bias level
            response_lower = response.lower()
            if 'none' in response_lower or 'low' in response_lower:
                return 0.9
            elif 'medium' in response_lower:
                return 0.6
            elif 'high' in response_lower:
                return 0.3
            else:
                return 0.7  # Default

        except Exception:
            return 0.7  # Default fallback value

    async def get_available_models(self) -> list:
        """
        Get list of available Anthropic models
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01"
                }

                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=15
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        models = [model["id"] for model in data.get("data", [])
                                if model.get("object") == "model"]
                        return models
                    else:
                        logger.error(f"Failed to get Anthropic models: {response.status}")
                        return [self.model]  # Return current model as fallback

        except Exception as e:
            logger.error(f"Error getting Anthropic models: {str(e)}")
            return [self.model]  # Return current model as fallback