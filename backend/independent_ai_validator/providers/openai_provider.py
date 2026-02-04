#!/usr/bin/env python3
"""
OpenAI Provider Implementation for Independent AI Validator
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional
import aiohttp

from .base_provider import BaseLLMProvider, LLMResponse, ValidationRequest

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI GPT provider for marketing claim validation
    """

    def __init__(self, api_key: str, weight: float = 1.0):
        super().__init__(api_key, "OpenAI", weight)
        self.base_url = "https://api.openai.com/v1"
        self.model = "gpt-4"  # Use GPT-4 for highest quality analysis

    async def validate_claim(self, request: ValidationRequest) -> LLMResponse:
        """
        Validate a marketing claim using OpenAI GPT-4
        """
        start_time = time.time()

        try:
            prompt = self.format_validation_prompt(request)

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an independent, objective AI validator specializing in marketing claim analysis. Provide unbiased, evidence-based assessments."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 1500,
                    "temperature": 0.1,  # Low temperature for consistent analysis
                    "top_p": 0.9,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0
                }

                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=60
                ) as response:

                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API error: {response.status} - {error_text}")
                        return LLMResponse(
                            content="Error: Unable to process request",
                            confidence=0.0,
                            reasoning=f"OpenAI API error: {response.status}",
                            provider=self.name,
                            model=self.model,
                            response_time=time.time() - start_time
                        )

                    result = await response.json()

                    content = result["choices"][0]["message"]["content"]
                    tokens_used = result.get("usage", {}).get("total_tokens", 0)

                    # Extract confidence from response
                    confidence = self.extract_confidence(content)

                    # Extract reasoning
                    reasoning = self.extract_reasoning(content)

                    return LLMResponse(
                        content=content,
                        confidence=confidence,
                        reasoning=reasoning,
                        metadata={
                            "model": self.model,
                            "tokens_used": tokens_used,
                            "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                            "completion_tokens": result.get("usage", {}).get("completion_tokens", 0)
                        },
                        provider=self.name,
                        model=self.model,
                        tokens_used=tokens_used,
                        response_time=time.time() - start_time
                    )

        except asyncio.TimeoutError:
            logger.error("OpenAI API timeout")
            return LLMResponse(
                content="Error: Request timeout",
                confidence=0.0,
                reasoning="OpenAI API request timed out after 60 seconds",
                provider=self.name,
                model=self.model,
                response_time=time.time() - start_time
            )
        except Exception as e:
            logger.error(f"OpenAI provider error: {str(e)}")
            return LLMResponse(
                content=f"Error: {str(e)}",
                confidence=0.0,
                reasoning=f"OpenAI provider encountered an error: {str(e)}",
                provider=self.name,
                model=self.model,
                response_time=time.time() - start_time
            )

    async def analyze_evidence(self, evidence: Dict[str, Any], claim: str) -> LLMResponse:
        """
        Analyze evidence for a claim using OpenAI
        """
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
- Gaps Identified: [List any gaps]
- Overall Assessment: [Detailed analysis]
- Confidence Score: [0-100%]

Be thorough and objective in your analysis.
"""

        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert evidence analyst providing objective, thorough assessments."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.1
                }

                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=45
                ) as response:

                    if response.status != 200:
                        error_text = await response.text()
                        return LLMResponse(
                            content=f"Error: {response.status}",
                            confidence=0.0,
                            reasoning=f"OpenAI API error: {error_text}",
                            provider=self.name,
                            response_time=time.time() - start_time
                        )

                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]
                    tokens_used = result.get("usage", {}).get("total_tokens", 0)

                    # Extract confidence from response
                    confidence = self.extract_confidence(content)

                    return LLMResponse(
                        content=content,
                        confidence=confidence,
                        reasoning="Evidence analysis completed using OpenAI GPT-4",
                        metadata={"analysis_type": "evidence", "tokens_used": tokens_used},
                        provider=self.name,
                        model=self.model,
                        tokens_used=tokens_used,
                        response_time=time.time() - start_time
                    )

        except Exception as e:
            logger.error(f"OpenAI evidence analysis error: {str(e)}")
            return LLMResponse(
                content=f"Error: {str(e)}",
                confidence=0.0,
                reasoning=f"Evidence analysis failed: {str(e)}",
                provider=self.name,
                response_time=time.time() - start_time
            )

    async def check_bias(self, text: str) -> LLMResponse:
        """
        Check for potential bias in the provided text using OpenAI
        """
        prompt = f"""
You are a bias detection expert. Analyze the following text for potential biases that could affect objective validation.

TEXT TO ANALYZE:
"{text}"

BIAS CHECK TASK:
1. Identify any potential confirmation bias
2. Check for leading questions or suggestive language
3. Assess objectivity and neutrality
4. Identify any emotional or persuasive language
5. Evaluate if the analysis appears balanced

RESPONSE FORMAT:
- Bias Detected: [YES/NO/POTENTIAL]
- Bias Types: [List any biases found]
- Objectivity Score: [0-100%]
- Recommendations: [Suggestions for improvement]
- Confidence: [0-100%]

Be thorough and constructive in your analysis.
"""

        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert bias detector providing objective assessments."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 800,
                    "temperature": 0.1
                }

                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30
                ) as response:

                    if response.status != 200:
                        return LLMResponse(
                            content="Error: API call failed",
                            confidence=0.0,
                            reasoning="Bias check failed due to API error",
                            provider=self.name,
                            response_time=time.time() - start_time
                        )

                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]
                    tokens_used = result.get("usage", {}).get("total_tokens", 0)

                    confidence = self.extract_confidence(content)

                    return LLMResponse(
                        content=content,
                        confidence=confidence,
                        reasoning="Bias analysis completed using OpenAI GPT-4",
                        metadata={"analysis_type": "bias", "tokens_used": tokens_used},
                        provider=self.name,
                        model=self.model,
                        tokens_used=tokens_used,
                        response_time=time.time() - start_time
                    )

        except Exception as e:
            logger.error(f"OpenAI bias check error: {str(e)}")
            return LLMResponse(
                content=f"Error: {str(e)}",
                confidence=0.0,
                reasoning=f"Bias check failed: {str(e)}",
                provider=self.name,
                response_time=time.time() - start_time
            )

    def extract_confidence(self, content: str) -> float:
        """Extract confidence score from response content"""
        import re

        # Look for confidence percentage
        confidence_match = re.search(r'Confidence[:\s]*(\d+)%?', content, re.IGNORECASE)
        if confidence_match:
            try:
                confidence_value = int(confidence_match.group(1))
                return min(100.0, max(0.0, confidence_value)) / 100.0
            except:
                pass

        # Look for objectivity score
        objectivity_match = re.search(r'Objectivity Score[:\s]*(\d+)%?', content, re.IGNORECASE)
        if objectivity_match:
            try:
                objectivity_value = int(objectivity_match.group(1))
                return min(100.0, max(0.0, objectivity_value)) / 100.0
            except:
                pass

        # Default confidence based on content length and quality indicators
        if len(content) > 500:
            return 0.8
        elif len(content) > 200:
            return 0.6
        else:
            return 0.4

    def extract_reasoning(self, content: str) -> str:
        """Extract reasoning from response content"""
        lines = content.split('\n')
        reasoning_lines = []

        for line in lines:
            line = line.strip()
            if (line.startswith('Reasoning:') or
                line.startswith('Overall Assessment:') or
                line.startswith('Recommendations:') or
                'because' in line.lower() or
                'evidence' in line.lower() or
                'analysis' in line.lower()):
                reasoning_lines.append(line)

        return '\n'.join(reasoning_lines) if reasoning_lines else content[:200] + "..."

    async def get_available_models(self) -> list:
        """Get list of available models from OpenAI"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=10
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        models = [model["id"] for model in data.get("data", [])
                                if model.get("object") == "model"]
                        return models
                    else:
                        return []

        except Exception as e:
            logger.error(f"Failed to get OpenAI models: {str(e)}")
            return []

    async def health_check(self) -> bool:
        """
        Check if OpenAI API is accessible and working
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }

                # Simple health check - get available models
                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=10
                ) as response:

                    return response.status == 200

        except Exception as e:
            logger.error(f"OpenAI health check failed: {str(e)}")
            return False