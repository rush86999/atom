#!/usr/bin/env python3
"""
DeepSeek Provider Implementation for Independent AI Validator
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional
import aiohttp

from .base_provider import BaseLLMProvider, LLMResponse, ValidationRequest

logger = logging.getLogger(__name__)

class DeepSeekProvider(BaseLLMProvider):
    """
    DeepSeek provider for marketing claim validation
    """

    def __init__(self, api_key: str, weight: float = 1.0):
        """Initialize DeepSeek provider"""
        super().__init__(api_key, "DeepSeek", weight)
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.model = "deepseek-chat"  # DeepSeek's main model
        self.max_tokens = 4000
        self.temperature = 0.1  # Low temperature for consistent analysis

    def get_name(self) -> str:
        """Get provider name"""
        return "DeepSeek"

    def get_model(self) -> str:
        """Get model name"""
        return self.model

    async def validate_claim(self, request: ValidationRequest) -> LLMResponse:
        """
        Validate a marketing claim using DeepSeek
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
6. **Business Value Delivery**: Based on the evidence, can this integration realistically achieve the claimed business outcomes (time savings, revenue increase, cost reduction, efficiency gains)? Evaluate if the features/capabilities shown in evidence match the business metrics claimed. If the claim is about an integration being "available" or "working", verify the health endpoint returns success AND the integration has the necessary features to deliver its business value (e.g., task management for PM tools, file operations for storage, etc.).

ANALYSIS TASK:
1. Evaluate the claim against each validation criterion
2. Assess the strength and quality of the evidence
3. Identify any potential gaps or inconsistencies
4. Determine the overall validity of the claim
5. For integration claims: verify both technical availability AND business capability
6. Provide specific recommendations for improvement

RESPONSE FORMAT:
- **Overall Score**: [0.0-1.0] where 1.0 = fully validated, 0.0 = not validated
- **Evidence Strength**: [STRONG/MODERATE/WEAK/INSUFFICIENT]
- **Confidence**: [0.0-1.0] how confident are you in this assessment
- **Business Value Assessment**: Can the integration deliver claimed outcomes?
- **Reasoning**: Detailed explanation of your analysis
- **Recommendations**: Specific suggestions for claim improvement
- **Bias Assessment**: Note any potential biases in your analysis

Provide an objective, evidence-based assessment without making assumptions beyond the provided evidence.
"""

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature
                }

                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=60
                ) as response:

                    if response.status == 200:
                        result = await response.json()

                        content = result["choices"][0]["message"]["content"]
                        tokens_used = result.get("usage", {}).get("total_tokens", 0)

                        # Parse the response to extract confidence score
                        confidence = self._parse_confidence_from_response(content)

                        return LLMResponse(
                            content=content,
                            confidence=confidence,
                            reasoning=f"DeepSeek analysis completed successfully",
                            provider=self.name,
                            model=self.model,
                            tokens_used=tokens_used,
                            response_time=time.time() - start_time
                        )

                    else:
                        error_text = await response.text()
                        logger.error(f"DeepSeek API error: {response.status} - {error_text}")

                        return LLMResponse(
                            content=f"Error: Unable to process request",
                            confidence=0.0,
                            reasoning=f"DeepSeek API error: {response.status}",
                            provider=self.name,
                            model=self.model,
                            response_time=time.time() - start_time
                        )

        except Exception as e:
            logger.error(f"DeepSeek provider error: {str(e)}")
            return LLMResponse(
                content=f"Error: Unable to process request",
                confidence=0.0,
                reasoning=f"DeepSeek provider error: {str(e)}",
                provider=self.name,
                model=self.model,
                response_time=time.time() - start_time
            )

    def _parse_confidence_from_response(self, response: str) -> float:
        """
        Parse confidence score from DeepSeek's response
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
        Analyze evidence for a claim using DeepSeek
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
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.2
                }

                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=45
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        tokens_used = result.get("usage", {}).get("total_tokens", 0)

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
                        logger.error(f"DeepSeek evidence analysis error: {response.status} - {error_text}")

                        return LLMResponse(
                            content=f"Evidence analysis failed",
                            confidence=0.0,
                            reasoning=f"DeepSeek API error: {response.status}",
                            provider=self.name,
                            model=self.model,
                            response_time=time.time() - start_time
                        )

        except Exception as e:
            logger.error(f"DeepSeek evidence analysis error: {str(e)}")
            return LLMResponse(
                content=f"Evidence analysis failed",
                confidence=0.0,
                reasoning=f"DeepSeek provider error: {str(e)}",
                provider=self.name,
                model=self.model,
                response_time=time.time() - start_time
            )

    async def check_bias(self, text: str) -> LLMResponse:
        """
        Check for potential bias in text using DeepSeek
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
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.1
                }

                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        tokens_used = result.get("usage", {}).get("total_tokens", 0)

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
                        logger.error(f"DeepSeek bias check error: {response.status} - {error_text}")

                        return LLMResponse(
                            content=f"Bias analysis failed",
                            confidence=0.5,
                            reasoning=f"DeepSeek API error: {response.status}",
                            provider=self.name,
                            model=self.model,
                            response_time=0.0
                        )

        except Exception as e:
            logger.error(f"DeepSeek bias check error: {str(e)}")
            return LLMResponse(
                content=f"Bias analysis failed",
                confidence=0.5,
                reasoning=f"DeepSeek provider error: {str(e)}",
                provider=self.name,
                model=self.model,
                response_time=0.0
            )

    def _parse_neutrality_score(self, response: str) -> float:
        """
        Parse neutrality score from DeepSeek's response
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

    async def health_check(self) -> bool:
        """
        Check if DeepSeek API is accessible and working
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }

                # Simple health check - list models
                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=10
                ) as response:

                    return response.status == 200

        except Exception as e:
            logger.error(f"DeepSeek health check failed: {str(e)}")
            return False

    async def get_available_models(self) -> list:
        """
        Get list of available DeepSeek models
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
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
                        logger.error(f"Failed to get DeepSeek models: {response.status}")
                        return [self.model]  # Return current model as fallback

        except Exception as e:
            logger.error(f"Error getting DeepSeek models: {str(e)}")
            return [self.model]  # Return current model as fallback