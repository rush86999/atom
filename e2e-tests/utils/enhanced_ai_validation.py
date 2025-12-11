"""
Enhanced AI Validation System for Integration Testing
Supports multiple AI providers with async operations, robust error handling, and fallback mechanisms
"""

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import requests

# Try to import aiohttp and AsyncOpenAI, fall back to sync versions if not available
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class AIProvider(Enum):
    """Supported AI providers for validation"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    GLM = "glm"
    FALLBACK = "fallback"


class AIValidationRequest:
    """Represents a validation request"""
    def __init__(
        self,
        claim: str,
        test_output: Dict[str, Any],
        context: Optional[str] = None,
        request_id: Optional[str] = None
    ):
        self.claim = claim
        self.test_output = test_output
        self.context = context
        self.request_id = request_id or f"req_{int(time.time() * 1000)}"
        self.timestamp = datetime.utcnow()


class AIValidationResult:
    """Represents a validation result"""
    def __init__(
        self,
        claim: str,
        verified: bool,
        confidence: float,
        reasoning: str,
        evidence_cited: List[str],
        gaps: List[str],
        provider: AIProvider,
        request_id: str,
        fallback_used: bool = False,
        error: bool = False,
        error_message: Optional[str] = None
    ):
        self.claim = claim
        self.verified = verified
        self.confidence = confidence
        self.reasoning = reasoning
        self.evidence_cited = evidence_cited
        self.gaps = gaps
        self.provider = provider
        self.request_id = request_id
        self.fallback_used = fallback_used
        self.error = error
        self.error_message = error_message
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "claim": self.claim,
            "verified": self.verified,
            "confidence": self.confidence,
            "reason": self.reasoning,
            "evidence_cited": self.evidence_cited,
            "gaps": self.gaps,
            "provider": self.provider.value,
            "request_id": self.request_id,
            "fallback_used": self.fallback_used,
            "error": self.error,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat()
        }


class BaseAIValidator(ABC):
    """Abstract base class for AI validators"""

    def __init__(self, max_retries: int = 3, request_delay: float = 1.0):
        self.max_retries = max_retries
        self.request_delay = request_delay
        self.use_async = AIOHTTP_AVAILABLE

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._cleanup_session()

    async def _initialize_session(self):
        """Initialize session resources - override in subclasses if needed"""
        pass

    async def _cleanup_session(self):
        """Cleanup session resources - override in subclasses if needed"""
        pass

    @abstractmethod
    async def validate_claim(
        self, request: AIValidationRequest
    ) -> AIValidationResult:
        """Validate a marketing claim - must be implemented by subclasses"""
        pass

    @abstractmethod
    def get_provider_type(self) -> AIProvider:
        """Get the provider type"""
        pass

    def _build_verification_prompt(
        self, request: AIValidationRequest
    ) -> str:
        """Build the standard verification prompt"""
        prompt_parts = [
            "MARKETING CLAIM TO VERIFY:",
            f"'{request.claim}'",
            "",
            "TEST OUTPUT DATA:",
            json.dumps(request.test_output, indent=2, default=str),
            "",
        ]

        if request.context:
            prompt_parts.extend(["ADDITIONAL CONTEXT:", request.context, ""])

        prompt_parts.extend([
            "VERIFICATION INSTRUCTIONS:",
            "1. Analyze whether the test output demonstrates the claimed capability",
            "2. Provide a confidence score (0.0 to 1.0) based on evidence",
            "3. Explain your reasoning with specific references to the test data",
            "4. Identify any gaps or limitations in the evidence",
            "5. Format your response as JSON with these fields:",
            "   - verified: boolean",
            "   - confidence: float (0.0-1.0)",
            "   - reasoning: string (detailed explanation)",
            "   - evidence_cited: list of specific evidence points",
            "   - gaps: list of missing evidence or limitations",
            "",
            "RESPONSE:",
        ])

        return "\n".join(prompt_parts)

    def _parse_verification_response(
        self, result_text: str, request: AIValidationRequest, provider: AIProvider
    ) -> AIValidationResult:
        """Parse verification response from AI provider"""
        try:
            # Extract JSON from response
            if "```json" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                json_str = result_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = result_text

            result_data = json.loads(json_str)

            return AIValidationResult(
                claim=request.claim,
                verified=result_data.get("verified", False),
                confidence=float(result_data.get("confidence", 0.0)),
                reasoning=result_data.get("reasoning", "No reasoning provided"),
                evidence_cited=result_data.get("evidence_cited", []),
                gaps=result_data.get("gaps", []),
                provider=provider,
                request_id=request.request_id,
                fallback_used=False,
                error=False
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return AIValidationResult(
                claim=request.claim,
                verified=False,
                confidence=0.0,
                reasoning=f"Failed to parse {provider.value} response: {str(e)}. Raw response: {result_text}",
                evidence_cited=[],
                gaps=["AI response parsing failed"],
                provider=provider,
                request_id=request.request_id,
                fallback_used=False,
                error=True,
                error_message=str(e)
            )


class OpenAIValidator(BaseAIValidator):
    """OpenAI-based validator with async support"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4", **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.model = model
        self.client: Optional[AsyncOpenAI] = None

    async def _initialize_session(self):
        """Initialize OpenAI client and session"""
        await super()._initialize_session()
        if self.client is None:
            self.client = AsyncOpenAI(api_key=self.api_key)

    async def _cleanup_session(self):
        """Cleanup OpenAI client and session"""
        if self.client:
            await self.client.close()
            self.client = None
        await super()._cleanup_session()

    def get_provider_type(self) -> AIProvider:
        return AIProvider.OPENAI

    async def validate_claim(self, request: AIValidationRequest) -> AIValidationResult:
        """Validate claim using OpenAI"""
        if not self.client:
            await self._initialize_session()

        prompt = self._build_verification_prompt(request)

        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a quality assurance expert that verifies marketing claims against actual test results.
                            Be objective, thorough, and evidence-based in your assessment.
                            Focus on whether the test results demonstrate the claimed capability."""
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=1000,
                )

                result_text = response.choices[0].message.content
                return self._parse_verification_response(result_text, request, AIProvider.OPENAI)

            except Exception as api_error:
                error_str = str(api_error)

                # Check for rate limit errors
                if "429" in error_str or "rate limit" in error_str.lower():
                    if attempt < self.max_retries - 1:
                        wait_time = self.request_delay * (attempt + 1)
                        await asyncio.sleep(wait_time)
                        continue

                # Check for quota errors
                if "insufficient_quota" in error_str or "quota" in error_str.lower():
                    raise Exception(f"OpenAI API quota exhausted: {error_str}")

                # Other errors
                if attempt == self.max_retries - 1:
                    raise api_error
                await asyncio.sleep(self.request_delay)

        raise Exception(f"OpenAI validation failed after {self.max_retries} attempts")


class DeepSeekValidator(BaseAIValidator):
    """DeepSeek-based validator with sync/async support"""

    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat", **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DeepSeek API key is required")

        self.model = model
        self.base_url = "https://api.deepseek.com"

    def get_provider_type(self) -> AIProvider:
        return AIProvider.DEEPSEEK

    async def validate_claim(self, request: AIValidationRequest) -> AIValidationResult:
        """Validate claim using DeepSeek API"""
        prompt = self._build_verification_prompt(request)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": """You are a quality assurance expert that verifies marketing claims against actual test results.
                    Be objective, thorough, and evidence-based in your assessment.
                    Focus on whether the test results demonstrate the claimed capability."""
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1000
        }

        for attempt in range(self.max_retries):
            try:
                # Run synchronous request in thread pool to avoid blocking event loop
                if self.use_async:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, lambda: requests.post(
                            f"{self.base_url}/chat/completions",
                            headers=headers,
                            json=data,
                            timeout=60
                        )
                    )
                else:
                    response = requests.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=60
                    )

                if response.status_code == 200:
                    result = response.json()
                    result_text = result["choices"][0]["message"]["content"]
                    return self._parse_verification_response(result_text, request, AIProvider.DEEPSEEK)
                else:
                    error_text = response.text
                    error_msg = f"DeepSeek API error: {response.status_code} - {error_text}"

                    # Check for rate limit
                    if response.status_code == 429:
                        if attempt < self.max_retries - 1:
                            wait_time = self.request_delay * (attempt + 1)
                            await asyncio.sleep(wait_time)
                            continue

                    # Other errors
                    if attempt == self.max_retries - 1:
                        raise Exception(error_msg)

            except Exception as api_error:
                error_str = str(api_error)
                if "rate limit" in error_str.lower():
                    if attempt < self.max_retries - 1:
                        wait_time = self.request_delay * (attempt + 1)
                        await asyncio.sleep(wait_time)
                        continue

                if attempt == self.max_retries - 1:
                    raise api_error
                await asyncio.sleep(self.request_delay)

        raise Exception(f"DeepSeek validation failed after {self.max_retries} attempts")


class GLMValidator(BaseAIValidator):
    """GLM-based validator with async support"""

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or os.getenv("GLM_API_KEY")
        if not self.api_key:
            raise ValueError("GLM API key is required")

        self.base_url = "https://api.z.ai/api/paas/v4"
        self.models = ["glm-4.6", "glm-4.5", "glm-4-flash"]

    def get_provider_type(self) -> AIProvider:
        return AIProvider.GLM

    async def validate_claim(self, request: AIValidationRequest) -> AIValidationResult:
        """Validate claim using GLM API with fallback models"""

        prompt = self._build_verification_prompt(request)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        for model in self.models:
            data = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": """You are a quality assurance expert that verifies marketing claims against actual test results.
                        Be objective, thorough, and evidence-based in your assessment.
                        Focus on whether the test results demonstrate the claimed capability."""
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 1000
            }

            for attempt in range(self.max_retries):
                try:
                    # Run synchronous request in thread pool to avoid blocking event loop
                    if self.use_async:
                        loop = asyncio.get_event_loop()
                        response = await loop.run_in_executor(
                            None, lambda: requests.post(
                                f"{self.base_url}/chat/completions",
                                headers=headers,
                                json=data,
                                timeout=60
                            )
                        )
                    else:
                        response = requests.post(
                            f"{self.base_url}/chat/completions",
                            headers=headers,
                            json=data,
                            timeout=60
                        )

                    if response.status_code == 200:
                        result = response.json()
                        result_text = result["choices"][0]["message"]["content"]
                        return self._parse_verification_response(result_text, request, AIProvider.GLM)
                    else:
                        error_text = response.text

                        # Check for quota/balance errors
                        if "1113" in error_text or "balance" in error_text.lower():
                            print(f"⚠️  GLM {model} quota exhausted. Trying next model...")
                            break

                        # Check for rate limit
                        if response.status_code == 429:
                            if attempt < self.max_retries - 1:
                                wait_time = self.request_delay * (attempt + 1)
                                await asyncio.sleep(wait_time)
                                continue

                        # Other errors - try next model
                        if attempt == self.max_retries - 1:
                            break

                except Exception as api_error:
                    error_str = str(api_error)
                    if "rate limit" in error_str.lower():
                        if attempt < self.max_retries - 1:
                            wait_time = self.request_delay * (attempt + 1)
                            await asyncio.sleep(wait_time)
                            continue

                    if attempt == self.max_retries - 1:
                        break

        raise Exception(f"All GLM models failed to validate claim")


class FallbackValidator(BaseAIValidator):
    """Rule-based fallback validator when AI providers are unavailable"""

    def get_provider_type(self) -> AIProvider:
        return AIProvider.FALLBACK

    async def validate_claim(self, request: AIValidationRequest) -> AIValidationResult:
        """Validate claim using rule-based logic"""
        # Evidence keywords for different claim types
        evidence_keywords = {
            "workflow": ["workflow", "automation", "automated", "process"],
            "natural language": ["natural_language", "input", "description", "text"],
            "memory": ["memory", "context", "history", "conversation", "recall"],
            "seamless": ["seamless", "integrated", "coordination", "unified"],
            "voice": ["voice", "audio", "speech", "transcription", "speech_to_text"],
            "production": ["production", "ready", "fastapi", "next", "framework", "api"],
            "integration": ["integration", "connected", "api", "service", "connected"],
            "automation": ["automation", "automated", "automatic", "trigger"],
            "ai": ["ai", "artificial", "intelligence", "learning", "model"]
        }

        claim_lower = request.claim.lower()
        evidence_text = str(request.test_output).lower()

        # Check if evidence supports the claim
        supporting_evidence = []
        for keyword, evidence_list in evidence_keywords.items():
            if keyword in claim_lower:
                found_evidence = [ev for ev in evidence_list if ev in evidence_text]
                supporting_evidence.extend(found_evidence)

        # Basic verification logic
        if supporting_evidence:
            confidence = min(0.8, len(supporting_evidence) * 0.15)
            return AIValidationResult(
                claim=request.claim,
                verified=confidence >= 0.3,
                confidence=confidence,
                reasoning=f"Fallback verification found evidence: {supporting_evidence}. Rule-based analysis due to AI provider unavailability.",
                evidence_cited=supporting_evidence,
                gaps=["Limited analysis due to AI provider unavailability"],
                provider=AIProvider.FALLBACK,
                request_id=request.request_id,
                fallback_used=True
            )
        else:
            return AIValidationResult(
                claim=request.claim,
                verified=False,
                confidence=0.0,
                reasoning="No supporting evidence found for marketing claim (fallback verification due to AI provider unavailability)",
                evidence_cited=[],
                gaps=["No supporting evidence", "AI provider unavailable"],
                provider=AIProvider.FALLBACK,
                request_id=request.request_id,
                fallback_used=True
            )


class EnhancedAIValidationSystem:
    """Enhanced AI validation system with multiple providers and robust error handling"""

    def __init__(self, preferred_provider: AIProvider = AIProvider.OPENAI):
        self.preferred_provider = preferred_provider
        self.providers: Dict[AIProvider, BaseAIValidator] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available providers based on environment variables"""
        try:
            # Initialize DeepSeek if available
            if os.getenv("DEEPSEEK_API_KEY"):
                self.providers[AIProvider.DEEPSEEK] = DeepSeekValidator()
                print("✅ DeepSeek validator initialized")
        except Exception as e:
            print(f"❌ Failed to initialize DeepSeek validator: {e}")

        try:
            # Initialize OpenAI if available
            if os.getenv("OPENAI_API_KEY"):
                self.providers[AIProvider.OPENAI] = OpenAIValidator()
                print("✅ OpenAI validator initialized")
        except Exception as e:
            print(f"❌ Failed to initialize OpenAI validator: {e}")

        try:
            # Initialize GLM if available
            if os.getenv("GLM_API_KEY"):
                self.providers[AIProvider.GLM] = GLMValidator()
                print("✅ GLM validator initialized")
        except Exception as e:
            print(f"❌ Failed to initialize GLM validator: {e}")

        # Always have fallback
        self.providers[AIProvider.FALLBACK] = FallbackValidator()
        print("✅ Fallback validator initialized")

        print(f"🤖 Available AI validators: {[p.value for p in self.providers.keys()]}")

    async def validate_claim(
        self,
        claim: str,
        test_output: Dict[str, Any],
        context: Optional[str] = None,
        preferred_provider: Optional[AIProvider] = None
    ) -> AIValidationResult:
        """
        Validate a marketing claim using available AI providers

        Args:
            claim: Marketing claim to verify
            test_output: Test results and outputs
            context: Additional context about the test
            preferred_provider: Preferred AI provider (overrides system default)

        Returns:
            Validation result with confidence score
        """
        request = AIValidationRequest(claim, test_output, context)

        # Determine provider order
        provider_order = []

        # Use preferred provider if specified and available
        if preferred_provider and preferred_provider in self.providers:
            provider_order.append(preferred_provider)
        elif self.preferred_provider in self.providers:
            provider_order.append(self.preferred_provider)

        # Add other providers (excluding fallback for now)
        for provider in [AIProvider.DEEPSEEK, AIProvider.OPENAI, AIProvider.GLM]:
            if provider in self.providers and provider not in provider_order:
                provider_order.append(provider)

        # Always try fallback last
        if AIProvider.FALLBACK in self.providers:
            provider_order.append(AIProvider.FALLBACK)

        print(f"🔍 Validating claim: '{claim[:50]}...' using provider order: {[p.value for p in provider_order]}")

        # Try providers in order
        for provider in provider_order:
            try:
                validator = self.providers[provider]
                print(f"🤖 Attempting validation with {provider.value}...")

                async with validator:
                    result = await validator.validate_claim(request)

                    if not result.error:
                        print(f"✅ Validation successful with {provider.value} (confidence: {result.confidence:.2f})")
                        return result
                    else:
                        print(f"⚠️  Validation failed with {provider.value}: {result.error_message}")

            except Exception as e:
                print(f"❌ Provider {provider.value} failed: {str(e)}")
                continue

        # This should not happen as fallback should always work
        raise Exception("All validation providers failed")

    async def batch_validate_claims(
        self,
        claims: List[str],
        test_output: Dict[str, Any],
        context: Optional[str] = None,
        max_concurrent: int = 3
    ) -> Dict[str, AIValidationResult]:
        """
        Validate multiple marketing claims concurrently

        Args:
            claims: List of marketing claims to verify
            test_output: Test results and outputs
            context: Additional context about the test
            max_concurrent: Maximum concurrent validations

        Returns:
            Dictionary mapping claims to validation results
        """
        print(f"🔍 Batch validating {len(claims)} claims (max concurrent: {max_concurrent})")

        semaphore = asyncio.Semaphore(max_concurrent)

        async def validate_single_claim(claim: str) -> tuple[str, AIValidationResult]:
            async with semaphore:
                result = await self.validate_claim(claim, test_output, context)
                return claim, result

        # Create tasks for all claims
        tasks = [validate_single_claim(claim) for claim in claims]

        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        validation_results: Dict[str, AIValidationResult] = {}

        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Batch validation error: {result}")
                continue

            claim, validation_result = result
            validation_results[claim] = validation_result

        # Print summary
        verified_count = sum(1 for r in validation_results.values() if r.verified and not r.error)
        error_count = sum(1 for r in validation_results.values() if r.error)
        fallback_count = sum(1 for r in validation_results.values() if r.fallback_used)

        print(f"📊 Batch validation complete: {verified_count}/{len(claims)} verified, {error_count} errors, {fallback_count} fallbacks")

        return validation_results

    async def validate_business_outcome(
        self,
        outcome_type: str,
        metrics: Dict[str, Any],
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate business outcome metrics

        Args:
            outcome_type: Type of outcome (e.g., "time_savings", "roi", "efficiency")
            metrics: Measured metrics from the test
            context: Additional context

        Returns:
            Business value assessment
        """
        # Create a business outcome claim
        claim = f"Delivers measurable {outcome_type.replace('_', ' ')} benefits"

        # Add metrics to test output for context
        enhanced_output = {
            "business_metrics": metrics,
            "outcome_type": outcome_type,
            "context": context
        }

        result = await self.validate_claim(claim, enhanced_output, context)

        # Convert to business outcome format
        return {
            "outcome_type": outcome_type,
            "verified": result.verified,
            "business_value_score": result.confidence * 10,  # Scale to 0-10
            "annual_value_projection": self._calculate_annual_value(metrics, outcome_type),
            "reasoning": result.reasoning,
            "metrics": metrics,
            "provider": result.provider.value,
            "confidence": result.confidence
        }

    def _calculate_annual_value(self, metrics: Dict[str, Any], outcome_type: str) -> str:
        """Calculate projected annual value from metrics"""
        try:
            if outcome_type == "time_savings":
                hours_saved = metrics.get("hours_saved_per_task", 0)
                tasks_per_month = metrics.get("tasks_per_month", 0)
                hourly_rate = metrics.get("hourly_rate", 50)

                annual_savings = hours_saved * tasks_per_month * 12 * hourly_rate
                return f"${annual_savings:,.0f}/year"

            elif outcome_type == "roi":
                investment = metrics.get("investment", 0)
                returns = metrics.get("returns", 0)

                if investment > 0:
                    roi_percentage = ((returns - investment) / investment) * 100
                    return f"{roi_percentage:.1f}% ROI"
                return "Insufficient data for ROI calculation"

            else:
                # Generic value calculation
                value_score = sum(metrics.values()) if metrics else 0
                return f"Value score: {value_score:.0f}"

        except Exception:
            return "Unable to calculate annual value"

    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        return {
            "available_providers": [p.value for p in self.providers.keys()],
            "preferred_provider": self.preferred_provider.value,
            "total_providers": len(self.providers),
            "has_ai_providers": len([p for p in self.providers.keys() if p != AIProvider.FALLBACK])
        }


# Utility functions for backward compatibility
def create_validation_system(preferred_provider: str = "auto") -> EnhancedAIValidationSystem:
    """
    Create an enhanced AI validation system

    Args:
        preferred_provider: Preferred provider ("openai", "deepseek", "glm", "auto")

    Returns:
        Enhanced AI validation system instance
    """
    provider_map = {
        "openai": AIProvider.OPENAI,
        "deepseek": AIProvider.DEEPSEEK,
        "glm": AIProvider.GLM,
        "auto": AIProvider.OPENAI  # Default to OpenAI for auto
    }

    provider = provider_map.get(preferred_provider.lower(), AIProvider.OPENAI)
    return EnhancedAIValidationSystem(preferred_provider=provider)


async def validate_marketing_claims(
    claims: List[str],
    test_output: Dict[str, Any],
    context: Optional[str] = None,
    preferred_provider: str = "auto"
) -> Dict[str, Dict[str, Any]]:
    """
    Validate multiple marketing claims (async version for backward compatibility)

    Args:
        claims: List of marketing claims to verify
        test_output: Test results and outputs
        context: Additional context about the test
        preferred_provider: Preferred AI provider

    Returns:
        Dictionary mapping claims to validation results
    """
    system = create_validation_system(preferred_provider)
    results = await system.batch_validate_claims(claims, test_output, context)

    # Convert to legacy format
    return {claim: result.to_dict() for claim, result in results.items()}


# Main execution for testing
async def main():
    """Test the enhanced AI validation system"""
    async with create_validation_system("auto") as system:
        # Test claims
        claims = [
            "Automates workflows with natural language processing",
            "Provides seamless integration across platforms",
            "Delivers production-ready AI automation"
        ]

        # Mock test output
        test_output = {
            "workflow_automation": {
                "status": "success",
                "natural_language_input": "Create a workflow to process emails",
                "automated_actions": ["email_classification", "response_generation"],
                "integration_points": ["gmail", "slack", "calendar"]
            },
            "performance_metrics": {
                "processing_time": 1.2,
                "accuracy": 0.95,
                "success_rate": 0.98
            }
        }

        print("🧪 Testing enhanced AI validation system...")

        # Batch validate
        results = await system.batch_validate_claims(claims, test_output)

        print("\n📊 Results:")
        for claim, result in results.items():
            status = "✅" if result.verified else "❌"
            print(f"{status} {claim[:40]}... (confidence: {result.confidence:.2f}, provider: {result.provider.value})")

        # Test business outcome validation
        business_result = await system.validate_business_outcome(
            "time_savings",
            {"hours_saved_per_task": 2, "tasks_per_month": 100, "hourly_rate": 75}
        )

        print(f"\n💰 Business outcome: {business_result}")


if __name__ == "__main__":
    asyncio.run(main())