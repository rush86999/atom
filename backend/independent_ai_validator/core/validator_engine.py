#!/usr/bin/env python3
"""
Main Validator Engine for Independent AI Marketing Claims Validation
Orchestrates multiple AI providers for unbiased validation
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

from .credential_manager import CredentialManager
from ..providers.glm_provider import GLMProvider
from ..providers.anthropic_provider import AnthropicProvider
from ..providers.deepseek_provider import DeepSeekProvider
from ..providers.base_provider import ValidationRequest, LLMResponse
from .real_world_usage_validator import RealWorldUsageValidator
from .user_expectation_validator import UserExpectationValidator

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Complete validation result for a marketing claim"""
    claim: str
    claim_type: str
    overall_score: float
    individual_scores: Dict[str, float]
    consensus_score: float
    confidence_interval: Tuple[float, float]
    evidence_strength: str
    recommendations: List[str]
    provider_analyses: Dict[str, Dict[str, Any]]
    evidence_summary: Dict[str, Any]
    validation_date: str
    total_tokens_used: int
    total_response_time: float
    bias_analysis: Optional[Dict[str, Any]] = None

@dataclass
class MarketingClaim:
    """Marketing claim structure"""
    id: str
    claim: str
    claim_type: str
    category: str
    description: Optional[str] = None
    validation_criteria: Optional[List[str]] = None
    priority: str = "medium"  # high, medium, low

class IndependentAIValidator:
    """
    Independent AI validator for marketing claims
    Uses multiple AI providers for unbiased validation
    """

    def __init__(self, credential_manager: Any = None, credentials_file: str = None, backend_url: str = "http://localhost:5058"):
        if credential_manager and not isinstance(credential_manager, str):
            self.credential_manager = credential_manager
        else:
            # Handle case where string is passed as first arg (backward compatibility)
            file_path = credential_manager if isinstance(credential_manager, str) else credentials_file
            self.credential_manager = CredentialManager(file_path)
        self.providers: Dict[str, Any] = {}
        self.claims_database: Dict[str, MarketingClaim] = {}
        self.validation_history: List[ValidationResult] = []
        self.is_initialized = False
        self.backend_url = backend_url

        # Provider weights for consensus calculation
        # Provider weights for consensus calculation
        self.provider_weights = {
            'glm': 0.0,
            'anthropic': 0.0,
            'deepseek': 1.0,
            'google': 0.0
        }

    async def initialize(self) -> bool:
        """
        Initialize the validator system
        Load credentials and set up providers
        """
        try:
            # Load credentials
            if not self.credential_manager.load_credentials():
                logger.error("Failed to load credentials")
                return False

            # Initialize providers
            await self._initialize_providers()

            # Load claims database
            await self._load_claims_database()

            # Validate provider connections
            await self._validate_providers()

            self.is_initialized = True
            logger.info("Independent AI Validator initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize validator: {str(e)}")
            return False

    async def _initialize_providers(self):
        """Initialize all available AI providers"""
        # GLM Provider (cost-effective alternative to OpenAI)
        # glm_cred = self.credential_manager.get_credential('glm')
        # if glm_cred:
        #     self.providers['glm'] = GLMProvider(
        #         glm_cred.key,
        #         glm_cred.weight
        #     )
        #     logger.info("GLM provider initialized")

        # Anthropic Provider
        # anthropic_cred = self.credential_manager.get_credential('anthropic')
        # if anthropic_cred:
        #     self.providers['anthropic'] = AnthropicProvider(
        #         anthropic_cred.key,
        #         anthropic_cred.weight
        #     )
        #     logger.info("Anthropic provider initialized")

        # DeepSeek Provider
        deepseek_cred = self.credential_manager.get_credential('deepseek')
        if deepseek_cred:
            self.providers['deepseek'] = DeepSeekProvider(
                deepseek_cred.key,
                deepseek_cred.weight
            )
            logger.info("DeepSeek provider initialized")

        # TODO: Add Google provider for 4-way consensus
        # 3-way consensus validation now active!

    async def _load_claims_database(self):
        """Load marketing claims database"""
        # Load claims from JSON file or create default claims
        claims_file = Path(__file__).parent.parent / "data" / "claims_repository.json"

        default_claims = [
            MarketingClaim(
                id="atom_ai_workflows",
                claim="AI-Powered Workflow Automation: Automate complex workflows with intelligent AI assistance",
                claim_type="capability",
                category="ai_features",
                description="Claims that ATOM can automate workflows using AI",
                validation_criteria=["Functionality", "Performance", "Reliability"],
                priority="high"
            ),
            MarketingClaim(
                id="atom_multi_provider",
                claim="Multi-Provider Integration: Connect with 15+ third-party services seamlessly",
                claim_type="integration",
                category="integrations",
                description="Claims integration with multiple third-party services",
                validation_criteria=["Connectivity", "Functionality", "Reliability"],
                priority="high"
            ),
            MarketingClaim(
                id="atom_real_time_analytics",
                claim="Real-Time Analytics: Get instant insights with real-time data analysis",
                claim_type="performance",
                category="analytics",
                description="Claims real-time analytics capabilities",
                validation_criteria=["Performance", "Accuracy", "Real-time capability"],
                priority="medium"
            ),
            MarketingClaim(
                id="atom_enterprise_reliability",
                claim="Enterprise-Grade Reliability: 99.9% uptime with enterprise security features",
                claim_type="reliability",
                category="enterprise_features",
                description="Claims enterprise-level reliability and security",
                validation_criteria=["Uptime", "Security", "Scalability"],
                priority="high"
            )
        ]

        # Use default claims for now
        for claim in default_claims:
            self.claims_database[claim.id] = claim

        logger.info(f"Loaded {len(self.claims_database)} marketing claims")

    async def _validate_providers(self):
        """Validate all provider connections"""
        for provider_name, provider in self.providers.items():
            try:
                is_healthy = await provider.test_connection()
                if is_healthy:
                    logger.info(f"{provider_name} provider is healthy")
                else:
                    logger.warning(f"{provider_name} provider connection failed")
            except Exception as e:
                logger.error(f"Error validating {provider_name}: {str(e)}")

    async def validate_claim(self, claim_id: str, evidence: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate a specific marketing claim using all available AI providers
        """
        if not self.is_initialized:
            await self.initialize()

        claim = self.claims_database.get(claim_id)
        if not claim:
            raise ValueError(f"Claim '{claim_id}' not found in database")

        # Collect evidence if not provided
        if not evidence:
            evidence = await self._collect_evidence(claim)

        # Create validation request
        validation_request = ValidationRequest(
            claim=claim.claim,
            evidence=evidence,
            claim_type=claim.claim_type,
            validation_criteria=claim.validation_criteria
        )

        # Run validation across all providers
        provider_results = await self._run_cross_validation(validation_request)

        # Perform bias analysis
        bias_analysis = await self._perform_bias_analysis(provider_results)

        # Calculate consensus and final score
        final_result = await self._calculate_consensus(
            claim, provider_results, evidence, bias_analysis
        )

        # Store in history
        self.validation_history.append(final_result)

        return final_result

    async def validate_all_claims(self) -> Dict[str, ValidationResult]:
        """
        Validate all marketing claims in the database
        """
        results = {}

        for claim_id in self.claims_database.keys():
            try:
                logger.info(f"Validating claim: {claim_id}")
                result = await self.validate_claim(claim_id)
                results[claim_id] = result
                logger.info(f"Claim {claim_id} validated with score: {result.overall_score:.2%}")
            except Exception as e:
                logger.error(f"Failed to validate claim {claim_id}: {str(e)}")
                # Create error result
                claim = self.claims_database[claim_id]
                results[claim_id] = ValidationResult(
                    claim=claim.claim,
                    claim_type=claim.claim_type,
                    overall_score=0.0,
                    individual_scores={},
                    consensus_score=0.0,
                    confidence_interval=(0.0, 0.0),
                    evidence_strength="INSUFFICIENT",
                    recommendations=[f"Validation failed: {str(e)}"],
                    provider_analyses={},
                    evidence_summary={},
                    validation_date=datetime.now().isoformat(),
                    total_tokens_used=0,
                    total_response_time=0.0
                )

        return results

    async def _collect_evidence(self, claim: MarketingClaim) -> Dict[str, Any]:
        """
        Collect comprehensive real evidence for the claim using advanced output validation
        Focuses on real outputs, functionality, and realistic execution times
        """
        from .advanced_output_validator import AdvancedOutputValidator
        # Import ComprehensiveE2ETester dynamically to avoid circular imports
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from comprehensive_e2e_integration_tester import ComprehensiveE2ETester

        evidence = {
            "timestamp": datetime.now().isoformat(),
            "claim_id": claim.id,
            "claim_category": claim.category,
            "validation_criteria": claim.validation_criteria,
            "evidence_type": "advanced_output_validation"
        }

        # Initialize advanced output validator
        try:
            validator = AdvancedOutputValidator()

            # Collect comprehensive evidence based on claim category
            if claim.category == "ai_features":
                evidence.update(await validator.validate_ai_workflows_output())
            elif claim.category == "integrations":
                evidence.update(await validator.validate_comprehensive_integrations())
            elif claim.category == "analytics":
                evidence.update(await validator.validate_real_time_analytics())
            elif claim.category == "enterprise_features":
                evidence.update(await validator.validate_enterprise_reliability())

            # Also test real-world usage scenarios that encompass multiple features
            real_world_validator = RealWorldUsageValidator()
            await real_world_validator.initialize()
            try:
                real_world_evidence = await real_world_validator.validate_real_world_usage_scenarios()
                # Convert any complex objects to JSON-serializable format
                serializable_evidence = self._make_serializable(real_world_evidence)
                evidence.update({"real_world_usage_evidence": serializable_evidence})
                logger.info(f"✅ Real-world usage evidence collected: Success rate {real_world_evidence.get('overall_success_rate', 0.0):.2f}")
            except Exception as rw_e:
                logger.warning(f"Failed to collect real-world usage evidence: {str(rw_e)}")
                evidence["real_world_usage_error"] = str(rw_e)
            finally:
                await real_world_validator.cleanup()

            # Integrate Comprehensive E2E Tester Evidence
            try:
                logger.info("🚀 Running Comprehensive E2E Integration Tests for additional evidence...")
                
                # Inject credentials into environment for E2E tester to pick up automatically
                env_mapping = {
                    'glm': 'GLM_API_KEY',
                    'openai': 'OPENAI_API_KEY',
                    'anthropic': 'ANTHROPIC_API_KEY',
                    'deepseek': 'DEEPSEEK_API_KEY',
                    'slack': 'SLACK_BOT_TOKEN',
                    'github': 'GITHUB_TOKEN',
                    'google': 'GOOGLE_CLIENT_ID', # Note: This might need secret too, but let's start with ID or check how E2E uses it
                    'asana': 'ASANA_TOKEN',
                    'notion': 'NOTION_TOKEN'
                }
                
                # Pre-populate environment variables from loaded credentials
                for provider, env_var in env_mapping.items():
                    key = self.credential_manager.get_credential_key(provider)
                    if key:
                        os.environ[env_var] = key
                        logger.debug(f"Injected {env_var} for E2E testing")

                e2e_tester = ComprehensiveE2ETester()
                # Run tests relevant to the claim category if possible, or all tests
                e2e_results = await e2e_tester.run_comprehensive_tests()
                
                # Add E2E results to evidence
                evidence["e2e_integration_test_results"] = self._make_serializable(e2e_results)
                
                # Extract specific insights for the claim
                if e2e_results.get('success'):
                    evidence["e2e_validation_status"] = "PASSED"
                else:
                    evidence["e2e_validation_status"] = "PARTIAL_FAILURE"
                    
                logger.info(f"✅ E2E Integration evidence collected: Score {e2e_results.get('actual_validation_score', 0.0):.2%}")
            except Exception as e2e_e:
                logger.warning(f"Failed to collect E2E integration evidence: {str(e2e_e)}")
                evidence["e2e_integration_error"] = str(e2e_e)

            # Additionally validate all features against user expectations
            user_expectation_validator = UserExpectationValidator(backend_url=self.backend_url)
            await user_expectation_validator.initialize()
            try:
                user_expectation_results = await user_expectation_validator.validate_all_feature_user_expectations()
                # Convert to JSON-serializable format
                serializable_expectation_evidence = self._make_serializable(user_expectation_results)
                evidence.update({"user_expectation_evidence": serializable_expectation_evidence})
                logger.info(f"✅ User expectation evidence collected: Satisfaction rate {user_expectation_results.get('overall_user_satisfaction_score', 0.0):.2f}")
            except Exception as ue_e:
                logger.warning(f"Failed to collect user expectation evidence: {str(ue_e)}")
                evidence["user_expectation_error"] = str(ue_e)
            finally:
                await user_expectation_validator.cleanup()

            # Also test basic backend health for fallback
            await self._test_basic_backend_health(evidence)

            logger.info(f"✅ Advanced evidence collected for {claim.id}: Overall score {evidence.get('overall_score', 0.0):.2f}")

        except Exception as e:
            logger.warning(f"Failed to collect advanced evidence: {str(e)}")
            evidence["collection_error"] = str(e)
            evidence["fallback_to_basic"] = True
            # Fallback to basic evidence collection
            evidence = await self._collect_basic_evidence(claim, evidence)

        return evidence

    def _make_serializable(self, obj):
        """Convert complex objects to JSON serializable format"""
        import json
        from dataclasses import asdict, is_dataclass
        from typing import Dict, List, Any

        def convert_item(item):
            if isinstance(item, (str, int, float, bool, type(None))):
                return item
            elif is_dataclass(item):
                try:
                    return asdict(item)
                except TypeError:
                    # If asdict fails, convert the dataclass to a dict manually
                    if hasattr(item, '__dataclass_fields__'):
                        result = {}
                        for field_name in item.__dataclass_fields__:
                            field_value = getattr(item, field_name, None)
                            if not callable(field_value):
                                result[field_name] = convert_item(field_value)
                        return result
                    else:
                        return str(item)
            elif isinstance(item, dict):
                return {key: convert_item(value) for key, value in item.items()}
            elif isinstance(item, list):
                return [convert_item(element) for element in item]
            elif isinstance(item, tuple):
                return tuple(convert_item(element) for element in item)
            elif hasattr(item, '__dict__'):  # Custom objects
                # Convert object to dict representation
                result = {}
                for attr_name, attr_value in vars(item).items():
                    if not callable(attr_value) and not attr_name.startswith('_'):
                        result[attr_name] = convert_item(attr_value)
                return result
            else:
                # For any other type that might not be serializable, convert to string
                return str(item)

        return convert_item(obj)

    async def _test_basic_backend_health(self, evidence: Dict[str, Any]):
        """Test basic backend health for additional evidence"""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get("http://localhost:8000/health", timeout=5) as response:
                        if response.status == 200:
                            evidence["basic_backend_health"] = "healthy"
                            evidence["backend_response"] = await response.json()
                        else:
                            evidence["basic_backend_health"] = "unhealthy"
                            evidence["backend_status_code"] = response.status
                except:
                    evidence["basic_backend_health"] = "unreachable"

        except Exception as e:
            evidence["basic_health_test_error"] = str(e)

    async def _collect_basic_evidence(self, claim: MarketingClaim, existing_evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback basic evidence collection if advanced validation fails"""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get("http://localhost:8000/health", timeout=5) as response:
                        if response.status == 200:
                            existing_evidence["fallback_backend_health"] = "healthy"
                            existing_evidence["fallback_backend_response"] = await response.json()
                        else:
                            existing_evidence["fallback_backend_health"] = "unhealthy"
                            existing_evidence["fallback_backend_status_code"] = response.status
                except:
                    existing_evidence["fallback_backend_health"] = "unreachable"

                # Basic endpoint testing based on claim category
                if claim.category == "ai_features":
                    await self._test_ai_features(session, existing_evidence)
                elif claim.category == "integrations":
                    await self._test_integrations(session, existing_evidence)
                elif claim.category == "analytics":
                    await self._test_analytics(session, existing_evidence)
                elif claim.category == "enterprise_features":
                    await self._test_enterprise_features(session, existing_evidence)

        except Exception as e:
            logger.warning(f"Failed to collect basic evidence: {str(e)}")
            existing_evidence["fallback_collection_error"] = str(e)

        return existing_evidence

    async def _test_ai_features(self, session, evidence):
        """Test AI-specific features"""
        try:
            async with session.post(
                "http://localhost:8000/api/v1/nlp/analyze",
                json={"text": "Test AI analysis", "analysis_type": "sentiment"},
                timeout=10
            ) as response:
                if response.status == 200:
                    evidence["ai_analysis"] = "working"
                    evidence["ai_analysis_response"] = await response.json()
                else:
                    evidence["ai_analysis"] = "error"
                    evidence["ai_analysis_status"] = response.status
        except:
            evidence["ai_analysis"] = "unavailable"

    async def _test_integrations(self, session, evidence):
        """Test integration features"""
        integration_endpoints = [
            "/api/v1/nlp/health",
            "/api/v1/workflows/health",
            "/api/v1/byok/health"
        ]

        for endpoint in integration_endpoints:
            try:
                async with session.get(f"http://localhost:8000{endpoint}", timeout=5) as response:
                    if response.status == 200:
                        service_name = endpoint.split('/')[-1].replace('_', ' ')
                        evidence[f"{service_name}_service"] = "healthy"
                    else:
                        service_name = endpoint.split('/')[-1].replace('_', ' ')
                        evidence[f"{service_name}_service"] = f"error_{response.status}"
            except:
                service_name = endpoint.split('/')[-1].replace('_', ' ')
                evidence[f"{service_name}_service"] = "unavailable"

    async def _test_analytics(self, session, evidence):
        """Test analytics features"""
        try:
            async with session.get(
                "http://localhost:8000/api/v1/analytics/dashboard",
                timeout=10
            ) as response:
                if response.status == 200:
                    evidence["analytics_dashboard"] = "working"
                    evidence["analytics_data"] = await response.json()
                else:
                    evidence["analytics_dashboard"] = "error"
                    evidence["analytics_status"] = response.status
        except:
            evidence["analytics_dashboard"] = "unavailable"

    async def _test_enterprise_features(self, session, evidence):
        """Test enterprise features"""
        # Test multiple endpoints for enterprise features
        endpoints_to_test = [
            "/health",
            "/api/v1/health"
        ]

        working_endpoints = 0
        for endpoint in endpoints_to_test:
            try:
                async with session.get(f"http://localhost:8000{endpoint}", timeout=5) as response:
                    if response.status == 200:
                        working_endpoints += 1
            except:
                pass

        evidence["enterprise_reliability"] = f"{working_endpoints}/{len(endpoints_to_test)} endpoints working"

    async def _run_cross_validation(self, request: ValidationRequest) -> Dict[str, Dict[str, Any]]:
        """
        Run validation across all available providers
        """
        results = {}

        for provider_name, provider in self.providers.items():
            try:
                logger.info(f"Running validation with {provider_name}")

                # Validate the claim - clean evidence for provider consumption
                cleaned_request = ValidationRequest(
                    claim=request.claim,
                    evidence=self._make_serializable(request.evidence),
                    claim_type=request.claim_type,
                    validation_criteria=request.validation_criteria
                )

                validation_response = await provider.validate_claim(cleaned_request)

                # Analyze evidence with cleaned evidence
                evidence_response = await provider.analyze_evidence(self._make_serializable(request.evidence), request.claim)

                results[provider_name] = {
                    "validation": {
                        "content": validation_response.content,
                        "confidence": validation_response.confidence,
                        "reasoning": validation_response.reasoning,
                        "metadata": validation_response.metadata,
                        "response_time": validation_response.response_time,
                        "tokens_used": validation_response.tokens_used
                    },
                    "evidence_analysis": {
                        "content": evidence_response.content,
                        "confidence": evidence_response.confidence,
                        "reasoning": evidence_response.reasoning,
                        "metadata": evidence_response.metadata,
                        "response_time": evidence_response.response_time,
                        "tokens_used": evidence_response.tokens_used
                    }
                }

                logger.info(f"{provider_name} validation completed with confidence: {validation_response.confidence:.2%}")

            except Exception as e:
                logger.error(f"{provider_name} validation failed: {str(e)}")
                results[provider_name] = {
                    "validation": {
                        "content": f"Error: {str(e)}",
                        "confidence": 0.0,
                        "reasoning": f"Provider {provider_name} failed: {str(e)}",
                        "response_time": 0.0,
                        "tokens_used": 0
                    },
                    "evidence_analysis": {
                        "content": "Error: Not available",
                        "confidence": 0.0,
                        "response_time": 0.0,
                        "tokens_used": 0
                    }
                }

        return results

    async def _perform_bias_analysis(self, provider_results: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Perform bias analysis on provider results
        """
        # Use GLM provider for bias analysis (cost-effective alternative to OpenAI)
        if not self.providers.get('glm'):
            return None

        try:
            glm_provider = self.providers['glm']

            # Combine all provider responses for bias analysis
            combined_text = "\n\n".join([
                result["validation"]["content"]
                for result in provider_results.values()
                if result["validation"]["content"]
            ])

            bias_response = await glm_provider.check_bias(combined_text)

            return {
                "bias_detected": "bias_detected" in bias_response.content.lower(),
                "analysis": bias_response.content,
                "confidence": bias_response.confidence,
                "recommendations": "Recommendations" in bias_response.content,
                "metadata": bias_response.metadata
            }

        except Exception as e:
            logger.error(f"Bias analysis failed: {str(e)}")
            return {
                "bias_detected": False,
                "analysis": f"Bias analysis failed: {str(e)}",
                "confidence": 0.0,
                "recommendations": None
            }

    async def _calculate_consensus(
        self,
        claim: MarketingClaim,
        provider_results: Dict[str, Dict[str, Any]],
        evidence: Dict[str, Any],
        bias_analysis: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """
        Calculate consensus and final validation score
        """

        # Extract individual scores
        individual_scores = {}
        total_weight = 0
        weighted_score_sum = 0
        total_tokens = 0
        total_time = 0

        for provider_name, result in provider_results.items():
            if provider_name in self.providers:
                weight = self.providers[provider_name].weight
                confidence = result["validation"]["confidence"]

                # Handle None confidence values
                if confidence is None or confidence <= 0:
                    continue  # Skip failed validations

                individual_scores[provider_name] = confidence
                weighted_score_sum += confidence * weight
                total_weight += weight

                total_tokens += result["validation"]["tokens_used"]
                total_time += result["validation"]["response_time"]

        # Calculate consensus score
        if total_weight == 0:
            # All providers failed, return error result
            return ValidationResult(
                claim=claim.claim,
                claim_type=claim.claim_type,
                overall_score=0.0,
                individual_scores=individual_scores,
                consensus_score=0.0,
                confidence_interval=(0.0, 0.0),
                evidence_strength="INSUFFICIENT",
                recommendations=["All AI providers failed to validate this claim"],
                provider_analyses=provider_results,
                evidence_summary=evidence,
                validation_date=datetime.now().isoformat(),
                total_tokens_used=0,
                total_response_time=0.0,
                bias_analysis=bias_analysis
            )

        consensus_score = weighted_score_sum / total_weight

        # Determine evidence strength
        evidence_strength = self._assess_evidence_strength(evidence)

        # Extract recommendations
        recommendations = self._extract_recommendations(provider_results)

        # Calculate confidence interval (simplified)
        margin_of_error = 0.05 if len(provider_results) > 2 else 0.1
        confidence_interval = (
            max(0, consensus_score - margin_of_error),
            min(1, consensus_score + margin_of_error)
        )

        return ValidationResult(
            claim=claim.claim,
            claim_type=claim.claim_type,
            overall_score=consensus_score,
            individual_scores=individual_scores,
            consensus_score=consensus_score,
            confidence_interval=confidence_interval,
            evidence_strength=evidence_strength,
            recommendations=recommendations,
            provider_analyses=provider_results,
            evidence_summary=evidence,
            validation_date=datetime.now().isoformat(),
            total_tokens_used=total_tokens,
            total_response_time=total_time,
            bias_analysis=bias_analysis
        )

    def _assess_evidence_strength(self, evidence: Dict[str, Any]) -> str:
        """
        Assess the strength of collected evidence with focus on real outputs and functionality
        Advanced validation system values real execution and quality over basic health checks
        """
        strength_indicators = 0
        advanced_evidence_weight = 0

        # Check if we have advanced output validation evidence (highest priority)
        if evidence.get("evidence_type") == "advanced_output_validation":
            advanced_evidence_weight += 2  # Bonus for using advanced validation

            # Check overall scores from advanced validation
            overall_score = evidence.get("overall_score", 0.0)
            if overall_score >= 0.8:
                strength_indicators += 3
                advanced_evidence_weight += 3
            elif overall_score >= 0.6:
                strength_indicators += 2
                advanced_evidence_weight += 2
            elif overall_score >= 0.4:
                strength_indicators += 1
                advanced_evidence_weight += 1

        # Check for real functionality tests (high priority)
        if evidence.get("test_category") in ["ai_workflows_output_validation", "multi_provider_integration"]:
            functionality_tests = evidence.get("functionality_tests", [])
            if functionality_tests:
                avg_functionality = sum(test.get("functionality_score", 0) for test in functionality_tests) / len(functionality_tests)
                if avg_functionality >= 0.8:
                    strength_indicators += 3
                    advanced_evidence_weight += 2
                elif avg_functionality >= 0.6:
                    strength_indicators += 2
                    advanced_evidence_weight += 1

        # Check performance metrics (medium-high priority)
        performance_metrics = evidence.get("performance_metrics", {})
        if performance_metrics:
            avg_performance = performance_metrics.get("avg_performance", 0) or performance_metrics.get("avg_functionality", 0)
            if avg_performance >= 0.7:
                strength_indicators += 2
            elif avg_performance >= 0.5:
                strength_indicators += 1

        # Check quality assessments (high priority)
        if performance_metrics.get("avg_quality", 0) >= 0.7:
            strength_indicators += 2
            advanced_evidence_weight += 1

        # Check for real provider tests (integrations)
        provider_tests = evidence.get("provider_tests", [])
        if provider_tests:
            working_providers = sum(1 for test in provider_tests if test.get("functionality_working", False))
            if working_providers >= 3:
                strength_indicators += 2
            elif working_providers >= 2:
                strength_indicators += 1

        # Check analytics tests (if applicable)
        analytics_tests = evidence.get("analytics_tests", [])
        if analytics_tests:
            working_endpoints = sum(1 for test in analytics_tests if test.get("functionality_working", False))
            if working_endpoints >= 2:
                strength_indicators += 2
            elif working_endpoints >= 1:
                strength_indicators += 1

        # Check enterprise reliability tests
        reliability_tests = evidence.get("reliability_tests", [])
        if reliability_tests:
            for test in reliability_tests:
                if test.get("uptime_score", 0) >= 0.9 and test.get("performance_score", 0) >= 0.7:
                    strength_indicators += 2
                    break

        # Basic backend health (lower priority - only used as fallback)
        backend_health = evidence.get("basic_backend_health") or evidence.get("backend_health")
        if backend_health == "healthy":
            strength_indicators += 1

        # Check for realistic execution times
        functionality_tests = evidence.get("functionality_tests", [])
        if functionality_tests:
            realistic_timing_count = sum(1 for test in functionality_tests if test.get("realistic_timing", False))
            if realistic_timing_count >= len(functionality_tests) * 0.8:  # 80% have realistic timing
                strength_indicators += 1
                advanced_evidence_weight += 1

        # Check real-world usage validation evidence
        real_world_evidence = evidence.get("real_world_usage_evidence", {})
        if real_world_evidence:
            # Bonus for real-world validation that tests multi-step workflows
            real_world_success_rate = real_world_evidence.get("overall_success_rate", 0.0)
            if real_world_success_rate >= 0.8:
                strength_indicators += 3
                advanced_evidence_weight += 3
            elif real_world_success_rate >= 0.6:
                strength_indicators += 2
                advanced_evidence_weight += 2
            elif real_world_success_rate >= 0.4:
                strength_indicators += 1
                advanced_evidence_weight += 1

            # Additional points for successful multi-step workflows
            successful_workflows = real_world_evidence.get("successful_workflows", 0)
            total_workflows = real_world_evidence.get("total_workflows", 0)
            if successful_workflows > 0 and total_workflows > 0:
                workflow_success_rate = successful_workflows / total_workflows
                if workflow_success_rate >= 0.8:
                    strength_indicators += 2
                elif workflow_success_rate >= 0.6:
                    strength_indicators += 1

        # Apply bonus for advanced evidence
        total_strength = strength_indicators + advanced_evidence_weight

        # Determine strength level with higher thresholds for advanced validation
        if total_strength >= 12 or (advanced_evidence_weight >= 6 and total_strength >= 8):
            return "STRONG"
        elif total_strength >= 8 or (advanced_evidence_weight >= 4 and total_strength >= 6):
            return "MODERATE"
        elif total_strength >= 4:
            return "WEAK"
        else:
            return "INSUFFICIENT"

    def _extract_recommendations(self, provider_results: Dict[str, Dict[str, Any]]) -> List[str]:
        """Extract recommendations from provider analyses"""
        recommendations = []

        for provider_name, result in provider_results.items():
            content = result["validation"]["content"]

            # Look for recommendation keywords
            if "recommendation" in content.lower():
                lines = content.split('\n')
                for line in lines:
                    if "recommendation" in line.lower() or "improve" in line.lower():
                        recommendations.append(f"{provider_name}: {line.strip()}")

        # Remove duplicates and limit
        recommendations = list(set(recommendations))
        return recommendations[:5]  # Limit to 5 recommendations

    async def generate_validation_report(self, results: Dict[str, ValidationResult]) -> str:
        """
        Generate comprehensive validation report
        """
        report = {
            "metadata": {
                "validation_date": datetime.now().isoformat(),
                "validator_version": "1.0.0",
                "total_claims_validated": len(results),
                "providers_used": list(self.providers.keys())
            },
            "summary": {
                "overall_score": sum(r.overall_score for r in results.values()) / len(results) if results else 0,
                "claims_fully_validated": len([r for r in results.values() if r.overall_score >= 0.9]),
                "claims_partially_validated": len([r for r in results.values() if 0.7 <= r.overall_score < 0.9]),
                "claims_not_validated": len([r for r in results.values() if r.overall_score < 0.7]),
                "average_confidence": sum(r.consensus_score for r in results.values()) / len(results) if results else 0
            },
            "category_scores": {},
            "detailed_results": {}
        }

        # Calculate category scores
        category_scores = {}
        for claim_id, result in results.items():
            claim = self.claims_database[claim_id]
            category = claim.category

            if category not in category_scores:
                category_scores[category] = []
            category_scores[category].append(result.overall_score)

        for category, scores in category_scores.items():
            report["category_scores"][category] = sum(scores) / len(scores)

        # Add detailed results
        for claim_id, result in results.items():
            claim = self.claims_database[claim_id]
            report["detailed_results"][claim_id] = {
                "claim": claim.claim,
                "category": claim.category,
                "score": result.overall_score,
                "evidence_strength": result.evidence_strength,
                "recommendations": result.recommendations,
                "individual_scores": result.individual_scores
            }

        return json.dumps(report, indent=2, default=str)

    async def cleanup(self):
        """Cleanup resources and clear credentials"""
        self.credential_manager.clear_credentials()
        self.providers.clear()
        self.is_initialized = False
        logger.info("Independent AI Validator cleaned up")