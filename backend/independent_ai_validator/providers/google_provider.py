#!/usr/bin/env python3
"""
Google Gemini Provider Implementation for Independent AI Validator
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional
import aiohttp

from .base_provider import BaseLLMProvider, LLMResponse, ValidationRequest

logger = logging.getLogger(__name__)

class GoogleProvider(BaseLLMProvider):
    """
    Google Gemini provider for marketing claim validation
    """

    def __init__(self, api_key: str, weight: float = 1.0):
        """Initialize Google provider"""
        super().__init__(api_key, "Google", weight)
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = "gemini-pro"
        self.temperature = 0.1

    def get_name(self) -> str:
        """Get provider name"""
        return "Google"

    def get_model(self) -> str:
        """Get model name"""
        return self.model

    async def validate_claim(self, request: ValidationRequest) -> LLMResponse:
        """
        Validate a marketing claim using Google Gemini
        """
        start_time = time.time()

        try:
            # Extract evidence JSON safely
            evidence_json = json.dumps(request.evidence, indent=2) if request.evidence else "{}"

            prompt = self.format_validation_prompt(request)

            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
                headers = {
                    "Content-Type": "application/json"
                }

                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": self.temperature,
                        "maxOutputTokens": 2048
                    }
                }

                async with session.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=60
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        
                        try:
                            content = result["candidates"][0]["content"]["parts"][0]["text"]
                            # Gemini doesn't always return token usage in the same way, but we can try to extract it
                            # or estimate it. For now, we'll use a placeholder or check if usageMetadata exists
                            tokens_used = result.get("usageMetadata", {}).get("totalTokenCount", 0)
                            
                            # Parse confidence
                            confidence = self.calculate_confidence(content, "MODERATE") # Default to moderate if not found

                            return LLMResponse(
                                content=content,
                                confidence=confidence,
                                reasoning="Google Gemini analysis completed successfully",
                                provider=self.name,
                                model=self.model,
                                tokens_used=tokens_used,
                                response_time=time.time() - start_time
                            )
                        except (KeyError, IndexError) as e:
                            logger.error(f"Error parsing Gemini response: {str(e)}")
                            return LLMResponse(
                                content="Error parsing response",
                                confidence=0.0,
                                reasoning=f"Response parsing error: {str(e)}",
                                provider=self.name,
                                model=self.model,
                                response_time=time.time() - start_time
                            )

                    else:
                        error_text = await response.text()
                        logger.error(f"Google API error: {response.status} - {error_text}")

                        return LLMResponse(
                            content=f"Error: Unable to process request",
                            confidence=0.0,
                            reasoning=f"Google API error: {response.status}",
                            provider=self.name,
                            model=self.model,
                            response_time=time.time() - start_time
                        )

        except Exception as e:
            logger.error(f"Google provider error: {str(e)}")
            return LLMResponse(
                content=f"Error: Unable to process request",
                confidence=0.0,
                reasoning=f"Google provider error: {str(e)}",
                provider=self.name,
                model=self.model,
                response_time=time.time() - start_time
            )

    async def analyze_evidence(self, evidence: Dict[str, Any], claim: str) -> LLMResponse:
        """
        Analyze evidence for a claim using Google Gemini
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
                url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
                headers = {"Content-Type": "application/json"}
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}
                }

                async with session.post(url, headers=headers, json=data, timeout=45) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        tokens_used = result.get("usageMetadata", {}).get("totalTokenCount", 0)

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
                        return LLMResponse(
                            content="Evidence analysis failed",
                            confidence=0.0,
                            reasoning=f"Google API error: {response.status}",
                            provider=self.name,
                            model=self.model,
                            response_time=time.time() - start_time
                        )

        except Exception as e:
            logger.error(f"Google evidence analysis error: {str(e)}")
            return LLMResponse(
                content="Evidence analysis failed",
                confidence=0.0,
                reasoning=f"Google provider error: {str(e)}",
                provider=self.name,
                model=self.model,
                response_time=time.time() - start_time
            )

    async def check_bias(self, text: str) -> LLMResponse:
        """
        Check for potential bias in text using Google Gemini
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
                url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
                headers = {"Content-Type": "application/json"}
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
                }

                async with session.post(url, headers=headers, json=data, timeout=30) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        
                        # Simple heuristic for confidence/neutrality since we can't easily parse it without regex
                        # For now, just return the content and a default confidence
                        return LLMResponse(
                            content=content,
                            confidence=0.7, # Default
                            reasoning="Bias analysis completed successfully",
                            provider=self.name,
                            model=self.model,
                            response_time=0.0
                        )
                    else:
                        return LLMResponse(
                            content="Bias analysis failed",
                            confidence=0.5,
                            reasoning=f"Google API error: {response.status}",
                            provider=self.name,
                            model=self.model,
                            response_time=0.0
                        )

        except Exception as e:
            logger.error(f"Google bias check error: {str(e)}")
            return LLMResponse(
                content="Bias analysis failed",
                confidence=0.5,
                reasoning=f"Google provider error: {str(e)}",
                provider=self.name,
                model=self.model,
                response_time=0.0
            )
