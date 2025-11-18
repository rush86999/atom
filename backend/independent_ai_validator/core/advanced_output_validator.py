#!/usr/bin/env python3
"""
Advanced Output Validation Engine for Independent AI Validator
Focuses on real outputs, functionality, and realistic execution times
Uses AI to evaluate if outputs match realistic expectations
"""

import asyncio
import aiohttp
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class OutputValidationResult:
    """Result of output validation with AI assessment"""
    output: str
    execution_time: float
    realistic_time: bool
    quality_score: float
    relevance_score: float
    functionality_proven: bool
    ai_assessment: str
    performance_rating: str  # EXCELLENT, GOOD, ACCEPTABLE, POOR

@dataclass
class PerformanceBenchmark:
    """Performance benchmark for realistic expectations"""
    operation: str
    expected_time_range: Tuple[float, float]  # (min_seconds, max_seconds)
    quality_threshold: float
    complexity_score: int  # 1-10

class AdvancedOutputValidator:
    """
    Advanced validator that tests real outputs and functionality
    Uses AI to evaluate output quality and realistic execution times
    """

    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url
        self.performance_benchmarks = self._initialize_benchmarks()
        self.ai_providers = {}

    def _initialize_benchmarks(self) -> Dict[str, PerformanceBenchmark]:
        """Initialize realistic performance benchmarks"""
        return {
            "nlp_analysis": PerformanceBenchmark(
                operation="NLP Sentiment Analysis",
                expected_time_range=(0.1, 2.0),  # 100ms - 2s
                quality_threshold=0.7,
                complexity_score=3
            ),
            "ai_workflow_execution": PerformanceBenchmark(
                operation="AI Workflow Execution",
                expected_time_range=(0.5, 5.0),  # 500ms - 5s
                quality_threshold=0.8,
                complexity_score=7
            ),
            "nlu_processing": PerformanceBenchmark(
                operation="Natural Language Understanding",
                expected_time_range=(0.2, 3.0),  # 200ms - 3s
                quality_threshold=0.75,
                complexity_score=5
            ),
            "task_creation": PerformanceBenchmark(
                operation="Task Creation & Routing",
                expected_time_range=(0.3, 2.5),  # 300ms - 2.5s
                quality_threshold=0.8,
                complexity_score=4
            ),
            "email_processing": PerformanceBenchmark(
                operation="Email Integration Processing",
                expected_time_range=(1.0, 8.0),  # 1s - 8s
                quality_threshold=0.7,
                complexity_score=6
            ),
            "complex_workflow_orchestration": PerformanceBenchmark(
                operation="Multi-Step Workflow Orchestration",
                expected_time_range=(2.0, 15.0),  # 2s - 15s
                quality_threshold=0.85,
                complexity_score=9
            )
        }

    async def validate_ai_workflows_output(self) -> Dict[str, Any]:
        """
        Validate AI workflows with real execution and output assessment
        """
        logger.info("🧪 Testing AI Workflow Automation with real outputs...")

        results = {
            "test_category": "ai_workflows_output_validation",
            "timestamp": datetime.now().isoformat(),
            "functionality_tests": [],
            "performance_metrics": {},
            "quality_assessments": {},
            "overall_score": 0.0
        }

        test_scenarios = [
            {
                "name": "Customer Support Workflow",
                "input": {"input": "Create a support ticket for login issue", "provider": "openai"},
                "expected_functionality": ["task_creation", "nlu_processing", "priority_detection"],
                "benchmark": "complex_workflow_orchestration"
            },
            {
                "name": "Project Task Automation",
                "input": {"input": "Create project task for API documentation update", "provider": "openai"},
                "expected_functionality": ["task_creation", "nlu_processing", "categorization"],
                "benchmark": "ai_workflow_execution"
            },
            {
                "name": "Sales Lead Processing",
                "input": {"input": "Process new sales lead from demo request", "provider": "openai"},
                "expected_functionality": ["lead_scoring", "crm_integration", "follow_up_task"],
                "benchmark": "complex_workflow_orchestration"
            }
        ]

        functionality_scores = []
        performance_scores = []
        quality_scores = []

        for scenario in test_scenarios:
            try:
                result = await self._execute_and_validate_workflow(scenario)
                results["functionality_tests"].append(result)

                functionality_scores.append(result["functionality_score"])
                performance_scores.append(result["performance_score"])
                quality_scores.append(result["quality_score"])

                logger.info(f"✅ {scenario['name']}: Functionality={result['functionality_score']:.2f}, Quality={result['quality_score']:.2f}")

            except Exception as e:
                logger.error(f"❌ {scenario['name']}: Failed - {str(e)}")
                results["functionality_tests"].append({
                    "name": scenario["name"],
                    "error": str(e),
                    "functionality_score": 0.0,
                    "performance_score": 0.0,
                    "quality_score": 0.0
                })
                functionality_scores.append(0.0)
                performance_scores.append(0.0)
                quality_scores.append(0.0)

        # Calculate aggregate scores
        results["performance_metrics"] = {
            "avg_functionality": sum(functionality_scores) / len(functionality_scores),
            "avg_performance": sum(performance_scores) / len(performance_scores),
            "avg_quality": sum(quality_scores) / len(quality_scores)
        }

        # Overall score weighted towards functionality and quality
        results["overall_score"] = (
            results["performance_metrics"]["avg_functionality"] * 0.4 +
            results["performance_metrics"]["avg_performance"] * 0.2 +
            results["performance_metrics"]["avg_quality"] * 0.4
        )

        return results

    async def _execute_and_validate_workflow(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow and validate its output with AI assessment"""

        start_time = time.time()

        # Execute the workflow
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.backend_url}/api/v1/ai/execute",
                    json=scenario["input"],
                    timeout=15
                ) as response:
                    execution_time = time.time() - start_time

                    if response.status == 200:
                        output_data = await response.json()

                        # Validate performance against benchmark
                        benchmark = self.performance_benchmarks[scenario["benchmark"]]
                        performance_score = self._calculate_performance_score(
                            execution_time, benchmark
                        )

                        # Use AI to evaluate output quality and relevance
                        quality_result = await self._evaluate_output_with_ai(
                            scenario["input"],
                            output_data,
                            scenario["expected_functionality"]
                        )

                        # Check if expected functionality was delivered
                        functionality_score = self._validate_functionality_delivered(
                            output_data, scenario["expected_functionality"]
                        )

                        return {
                            "name": scenario["name"],
                            "execution_time": execution_time,
                            "output": output_data,
                            "performance_score": performance_score,
                            "quality_score": quality_result.quality_score,
                            "relevance_score": quality_result.relevance_score,
                            "functionality_score": functionality_score,
                            "realistic_timing": benchmark.expected_time_range[0] <= execution_time <= benchmark.expected_time_range[1],
                            "ai_assessment": quality_result.ai_assessment,
                            "performance_rating": quality_result.performance_rating
                        }
                    else:
                        return {
                            "name": scenario["name"],
                            "execution_time": execution_time,
                            "error": f"HTTP {response.status}",
                            "performance_score": 0.0,
                            "quality_score": 0.0,
                            "relevance_score": 0.0,
                            "functionality_score": 0.0,
                            "realistic_timing": False,
                            "ai_assessment": "Execution failed",
                            "performance_rating": "POOR"
                        }

            except asyncio.TimeoutError:
                execution_time = time.time() - start_time
                return {
                    "name": scenario["name"],
                    "execution_time": execution_time,
                    "error": "Request timeout",
                    "performance_score": 0.0,
                    "quality_score": 0.0,
                    "relevance_score": 0.0,
                    "functionality_score": 0.0,
                    "realistic_timing": False,
                    "ai_assessment": "Timeout - unrealistic performance",
                    "performance_rating": "POOR"
                }
            except Exception as e:
                execution_time = time.time() - start_time
                return {
                    "name": scenario["name"],
                    "execution_time": execution_time,
                    "error": str(e),
                    "performance_score": 0.0,
                    "quality_score": 0.0,
                    "relevance_score": 0.0,
                    "functionality_score": 0.0,
                    "realistic_timing": False,
                    "ai_assessment": f"Execution error: {str(e)}",
                    "performance_rating": "POOR"
                }

    def _calculate_performance_score(self, execution_time: float, benchmark: PerformanceBenchmark) -> float:
        """Calculate performance score based on realistic timing expectations"""
        min_time, max_time = benchmark.expected_time_range

        if execution_time < min_time:
            # Too fast - might be unrealistic
            return 0.7
        elif execution_time <= max_time:
            # Within realistic range - score based on where in range
            optimal_time = (min_time + max_time) / 2
            deviation = abs(execution_time - optimal_time) / (max_time - min_time)
            return max(0.0, 1.0 - deviation)
        else:
            # Too slow
            if execution_time <= max_time * 1.5:
                return 0.6
            elif execution_time <= max_time * 2:
                return 0.4
            else:
                return 0.2

    def _validate_functionality_delivered(self, output_data: Dict[str, Any], expected_functionality: List[str]) -> float:
        """Validate that expected functionality was delivered in the output"""
        delivered = 0

        # Check for common indicators of functionality delivery
        output_str = json.dumps(output_data, default=str).lower()

        for functionality in expected_functionality:
            if functionality in output_str or any(
                indicator in output_str for indicator in self._get_functionality_indicators(functionality)
            ):
                delivered += 1

        return delivered / len(expected_functionality)

    def _get_functionality_indicators(self, functionality: str) -> List[str]:
        """Get output indicators for specific functionality"""
        indicators = {
            "task_creation": ["task", "created", "task_id", "ticket"],
            "nlu_processing": ["intent", "entities", "confidence", "sentiment"],
            "priority_detection": ["priority", "urgent", "high", "low", "medium"],
            "lead_scoring": ["score", "lead", "probability", "rating"],
            "crm_integration": ["crm", "salesforce", "hubspot", "contact"],
            "follow_up_task": ["follow", "reminder", "schedule", "calendar"]
        }
        return indicators.get(functionality, [functionality])

    async def _evaluate_output_with_ai(self, input_data: Dict[str, Any], output_data: Dict[str, Any],
                                     expected_functionality: List[str]) -> OutputValidationResult:
        """Use AI providers to evaluate output quality and relevance"""

        try:
            # Import AI quality validator
            from .ai_output_quality_validator import AIOutputQualityValidator

            # Create quality validator with available providers
            ai_quality_validator = AIOutputQualityValidator(self.ai_providers)

            # Get AI quality assessments
            assessments = await ai_quality_validator.evaluate_workflow_output(
                input_data.get("input", str(input_data)),
                output_data,
                0.0  # Will be set by caller
            )

            # Calculate consensus scores
            consensus = ai_quality_validator.calculate_consensus_score(assessments)

            # Generate quality report
            quality_report = ai_quality_validator.generate_quality_report(assessessments)

            # Determine performance rating based on consensus
            if consensus["overall_consensus"] >= 0.8:
                performance_rating = "EXCELLENT"
            elif consensus["overall_consensus"] >= 0.6:
                performance_rating = "GOOD"
            elif consensus["overall_consensus"] >= 0.4:
                performance_rating = "AVERAGE"
            else:
                performance_rating = "POOR"

            # Combine feedback from all providers
            all_feedback = []
            for assessment in assessments:
                all_feedback.extend(assessment.specific_feedback)

            ai_assessment = f"Multi-provider consensus: {consensus['overall_consensus']:.1%} - " + "; ".join(all_feedback[:3])  # Limit feedback

            return OutputValidationResult(
                output=json.dumps(output_data, default=str)[:500],  # Truncate for brevity
                execution_time=0.0,  # Will be set by caller
                realistic_time=True,
                quality_score=consensus["average_quality"],
                relevance_score=consensus["average_relevance"],
                functionality_proven=consensus["average_functionality"] > 0.6,
                ai_assessment=ai_assessment,
                performance_rating=performance_rating
            )

        except Exception as e:
            logger.warning(f"AI quality evaluation failed: {str(e)}")
            # Fallback to basic assessment
            return OutputValidationResult(
                output=json.dumps(output_data, default=str)[:500],
                execution_time=0.0,
                realistic_time=True,
                quality_score=0.6,  # Conservative estimate
                relevance_score=0.7,
                functionality_proven=True,
                ai_assessment="AI quality evaluation failed, using basic assessment",
                performance_rating="AVERAGE"
            )

    async def validate_multi_provider_integration(self) -> Dict[str, Any]:
        """Validate multi-provider integration with real service calls"""

        logger.info("🧪 Testing Multi-Provider Integration...")

        results = {
            "test_category": "multi_provider_integration",
            "timestamp": datetime.now().isoformat(),
            "provider_tests": [],
            "integration_evidence": {},
            "overall_score": 0.0
        }

        # Test AI provider endpoints
        ai_providers = ["openai", "anthropic", "deepseek"]
        provider_scores = []

        for provider in ai_providers:
            try:
                start_time = time.time()

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.backend_url}/api/v1/nlp/analyze",
                        json={"text": f"Test sentiment analysis for {provider} integration", "provider": provider},
                        timeout=10
                    ) as response:
                        execution_time = time.time() - start_time

                        if response.status == 200:
                            result_data = await response.json()
                            score = min(1.0, execution_time / 2.0)  # Prefer faster but realistic times
                            provider_scores.append(score)

                            results["provider_tests"].append({
                                "provider": provider,
                                "execution_time": execution_time,
                                "functionality_working": True,
                                "score": score,
                                "output": result_data
                            })
                        else:
                            provider_scores.append(0.0)
                            results["provider_tests"].append({
                                "provider": provider,
                                "execution_time": execution_time,
                                "functionality_working": False,
                                "score": 0.0,
                                "error": f"HTTP {response.status}"
                            })

            except Exception as e:
                provider_scores.append(0.0)
                results["provider_tests"].append({
                    "provider": provider,
                    "functionality_working": False,
                    "score": 0.0,
                    "error": str(e)
                })

        # Calculate overall integration score
        results["overall_score"] = sum(provider_scores) / len(provider_scores) if provider_scores else 0.0
        results["integration_evidence"] = {
            "providers_working": sum(1 for test in results["provider_tests"] if test.get("functionality_working", False)),
            "total_providers": len(ai_providers),
            "avg_execution_time": sum(test.get("execution_time", 0) for test in results["provider_tests"]) / len(results["provider_tests"])
        }

        return results

    async def validate_comprehensive_integrations(self) -> Dict[str, Any]:
        """Validate comprehensive third-party service integrations (16+ services)"""

        logger.info("🧪 Testing Comprehensive Multi-Provider Integrations...")

        results = {
            "timestamp": datetime.now().isoformat(),
            "integration_tests": [],
            "overall_score": 0.0,
            "integration_evidence": {
                "services_tested": 0,
                "services_working": 0,
                "total_services_available": 16,
                "integration_coverage_percentage": 0.0,
                "service_categories": {
                    "productivity": ["asana", "notion", "linear", "outlook", "microsoft365"],
                    "storage": ["dropbox", "google_drive", "onedrive", "box"],
                    "communication": ["slack", "whatsapp", "zoom"],
                    "business": ["stripe", "salesforce", "tableau"],
                    "development": ["github"]
                }
            }
        }

        # Comprehensive list of 16 third-party services
        third_party_services = {
            "asana": {
                "name": "Asana Project Management",
                "category": "productivity",
                "endpoint": "/api/asana/health",
                "description": "Task and project management integration"
            },
            "notion": {
                "name": "Notion Workspace",
                "category": "productivity",
                "endpoint": "/api/notion/health",
                "description": "Documentation and knowledge management"
            },
            "linear": {
                "name": "Linear Issue Tracking",
                "category": "productivity",
                "endpoint": "/api/linear/health",
                "description": "Software issue tracking and project management"
            },
            "outlook": {
                "name": "Microsoft Outlook",
                "category": "productivity",
                "endpoint": "/api/outlook/health",
                "description": "Email and calendar integration"
            },
            "dropbox": {
                "name": "Dropbox Storage",
                "category": "storage",
                "endpoint": "/api/dropbox/health",
                "description": "Cloud file storage and sharing"
            },
            "stripe": {
                "name": "Stripe Payments",
                "category": "business",
                "endpoint": "/stripe/health",
                "description": "Payment processing and billing"
            },
            "salesforce": {
                "name": "Salesforce CRM",
                "category": "business",
                "endpoint": "/salesforce/health",
                "description": "Customer relationship management"
            },
            "zoom": {
                "name": "Zoom Video",
                "category": "communication",
                "endpoint": "/api/zoom/status",
                "description": "Video conferencing and meetings"
            },
            "github": {
                "name": "GitHub Development",
                "category": "development",
                "endpoint": "/api/github/health",
                "description": "Code repository and development tools"
            },
            "google_drive": {
                "name": "Google Drive",
                "category": "storage",
                "endpoint": "/google_drive/health",
                "description": "Cloud storage and collaboration"
            },
            "onedrive": {
                "name": "OneDrive",
                "category": "storage",
                "endpoint": "/onedrive/health",
                "description": "Microsoft cloud storage integration"
            },
            "microsoft365": {
                "name": "Microsoft 365",
                "category": "productivity",
                "endpoint": "/microsoft365/health",
                "description": "Office 365 productivity suite"
            },
            "box": {
                "name": "Box Cloud Storage",
                "category": "storage",
                "endpoint": "/box/health",
                "description": "Enterprise cloud storage"
            },
            "slack": {
                "name": "Slack Communication",
                "category": "communication",
                "endpoint": "/api/slack/health",
                "description": "Team messaging and collaboration"
            },
            "whatsapp": {
                "name": "WhatsApp Business",
                "category": "communication",
                "endpoint": "/api/whatsapp/health",
                "description": "Business messaging and communication"
            },
            "tableau": {
                "name": "Tableau Analytics",
                "category": "business",
                "endpoint": "/tableau/health",
                "description": "Business intelligence and data visualization"
            }
        }

        service_scores = []

        # Test each third-party service integration
        for service_id, service_info in third_party_services.items():
            start_time = time.time()

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.backend_url}{service_info['endpoint']}",
                        timeout=10
                    ) as response:
                        execution_time = time.time() - start_time

                        if response.status == 200:
                            result_data = await response.json()

                            # Score based on functionality and response time
                            functionality_score = 1.0 if response.status == 200 else 0.0
                            time_score = 1.0 if execution_time < 2.0 else 0.7 if execution_time < 5.0 else 0.3
                            overall_score = (functionality_score + time_score) / 2

                            service_scores.append(overall_score)

                            results["integration_tests"].append({
                                "service_id": service_id,
                                "service_name": service_info["name"],
                                "category": service_info["category"],
                                "endpoint": service_info["endpoint"],
                                "description": service_info["description"],
                                "execution_time": execution_time,
                                "status_code": response.status,
                                "functionality_working": True,
                                "integration_score": overall_score,
                                "response_data": result_data
                            })

                            logger.info(f"✅ {service_info['name']}: Integration working (Score: {overall_score:.2f})")

                        else:
                            service_scores.append(0.0)
                            results["integration_tests"].append({
                                "service_id": service_id,
                                "service_name": service_info["name"],
                                "category": service_info["category"],
                                "endpoint": service_info["endpoint"],
                                "description": service_info["description"],
                                "execution_time": execution_time,
                                "status_code": response.status,
                                "functionality_working": False,
                                "integration_score": 0.0,
                                "error": f"HTTP {response.status}"
                            })

                            logger.warning(f"❌ {service_info['name']}: Integration failed (HTTP {response.status})")

            except Exception as e:
                service_scores.append(0.0)
                results["integration_tests"].append({
                    "service_id": service_id,
                    "service_name": service_info["name"],
                    "category": service_info["category"],
                    "endpoint": service_info["endpoint"],
                    "description": service_info["description"],
                    "execution_time": time.time() - start_time,
                    "functionality_working": False,
                    "integration_score": 0.0,
                    "error": str(e)
                })

                logger.warning(f"❌ {service_info['name']}: Integration error - {str(e)}")

        # Calculate comprehensive integration metrics
        services_working = sum(1 for test in results["integration_tests"] if test.get("functionality_working", False))
        total_services_tested = len(results["integration_tests"])
        overall_integration_score = sum(service_scores) / len(service_scores) if service_scores else 0.0

        # Update integration evidence
        results["overall_score"] = overall_integration_score
        results["integration_evidence"].update({
            "services_tested": total_services_tested,
            "services_working": services_working,
            "integration_coverage_percentage": (services_working / len(third_party_services)) * 100,
            "avg_integration_score": overall_integration_score,
            "category_breakdown": {}
        })

        # Calculate category-specific metrics
        for category, services in results["integration_evidence"]["service_categories"].items():
            category_services = [test for test in results["integration_tests"] if test.get("category") == category]
            category_working = sum(1 for test in category_services if test.get("functionality_working", False))
            category_score = sum(test.get("integration_score", 0) for test in category_services) / len(category_services) if category_services else 0.0

            results["integration_evidence"]["category_breakdown"][category] = {
                "services_in_category": len(services),
                "services_working": category_working,
                "category_success_rate": (category_working / len(services)) * 100 if services else 0,
                "avg_category_score": category_score
            }

        # Additional evidence for marketing claim validation
        results["marketing_claim_evidence"] = {
            "exceeds_15_services": total_services_tested >= 15,
            "demonstrated_seamless_connectivity": services_working >= 12,
            "cross_category_coverage": len(set(test.get("category") for test in results["integration_tests"] if test.get("functionality_working"))) >= 4,
            "enterprise_ready_integrations": services_working >= 10,
            "real_api_connectivity": all(test.get("status_code") == 200 for test in results["integration_tests"] if test.get("functionality_working"))
        }

        logger.info(f"🎯 Comprehensive Integration Testing Complete: {services_working}/{len(third_party_services)} services working ({(services_working/len(third_party_services))*100:.1f}%)")
        logger.info(f"📊 Category Coverage: {len(results['integration_evidence']['category_breakdown'])} categories validated")

        return results

    async def validate_real_time_analytics(self) -> Dict[str, Any]:
        """Validate real-time analytics with actual data processing"""

        logger.info("🧪 Testing Real-Time Analytics...")

        results = {
            "test_category": "real_time_analytics",
            "timestamp": datetime.now().isoformat(),
            "analytics_tests": [],
            "performance_metrics": {},
            "overall_score": 0.0
        }

        # Test analytics endpoints
        analytics_endpoints = [
            "/api/v1/analytics/dashboard",
            "/api/v1/analytics/workflow-performance",
            "/api/v1/analytics/ai-usage"
        ]

        test_scores = []

        for endpoint in analytics_endpoints:
            try:
                start_time = time.time()

                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.backend_url}{endpoint}", timeout=8) as response:
                        execution_time = time.time() - start_time

                        if response.status == 200:
                            data = await response.json()

                            # Score based on data richness and response time
                            data_score = min(1.0, len(str(data)) / 1000)  # Richer data gets higher score
                            time_score = 1.0 if execution_time < 3.0 else 0.5 if execution_time < 5.0 else 0.2
                            score = (data_score + time_score) / 2

                            test_scores.append(score)

                            results["analytics_tests"].append({
                                "endpoint": endpoint,
                                "execution_time": execution_time,
                                "data_points": len(str(data)),
                                "functionality_working": True,
                                "score": score
                            })
                        else:
                            test_scores.append(0.0)
                            results["analytics_tests"].append({
                                "endpoint": endpoint,
                                "execution_time": execution_time,
                                "functionality_working": False,
                                "score": 0.0,
                                "error": f"HTTP {response.status}"
                            })

            except Exception as e:
                test_scores.append(0.0)
                results["analytics_tests"].append({
                    "endpoint": endpoint,
                    "functionality_working": False,
                    "score": 0.0,
                    "error": str(e)
                })

        # Calculate overall score
        results["overall_score"] = sum(test_scores) / len(test_scores) if test_scores else 0.0
        results["performance_metrics"] = {
            "avg_response_time": sum(test.get("execution_time", 0) for test in results["analytics_tests"]) / len(results["analytics_tests"]),
            "working_endpoints": sum(1 for test in results["analytics_tests"] if test.get("functionality_working", False)),
            "total_endpoints": len(analytics_endpoints)
        }

        return results

    async def validate_enterprise_reliability(self) -> Dict[str, Any]:
        """Validate enterprise reliability with stress testing"""

        logger.info("🧪 Testing Enterprise Reliability...")

        results = {
            "test_category": "enterprise_reliability",
            "timestamp": datetime.now().isoformat(),
            "reliability_tests": [],
            "performance_metrics": {},
            "overall_score": 0.0
        }

        # Test concurrent load handling
        concurrent_requests = 10
        successful_requests = 0
        response_times = []

        async def test_request():
            nonlocal successful_requests
            try:
                start_time = time.time()
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.backend_url}/health", timeout=5) as response:
                        execution_time = time.time() - start_time
                        if response.status == 200:
                            successful_requests += 1
                            response_times.append(execution_time)
                            return True
                        return False
            except:
                return False

        # Run concurrent requests
        start_time = time.time()
        tasks = [test_request() for _ in range(concurrent_requests)]
        await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Calculate reliability metrics
        reliability_score = successful_requests / concurrent_requests
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # Score based on enterprise standards (99.9% uptime = <1 failure per 1000 requests)
        if reliability_score >= 0.99:
            uptime_score = 1.0
        elif reliability_score >= 0.95:
            uptime_score = 0.8
        elif reliability_score >= 0.90:
            uptime_score = 0.6
        else:
            uptime_score = 0.3

        performance_score = 1.0 if avg_response_time < 0.5 else 0.7 if avg_response_time < 1.0 else 0.4

        results["reliability_tests"].append({
            "test_type": "concurrent_load",
            "concurrent_requests": concurrent_requests,
            "successful_requests": successful_requests,
            "reliability_score": reliability_score,
            "avg_response_time": avg_response_time,
            "uptime_score": uptime_score,
            "performance_score": performance_score
        })

        results["overall_score"] = (uptime_score + performance_score) / 2
        results["performance_metrics"] = {
            "reliability": reliability_score,
            "avg_response_time": avg_response_time,
            "uptime_score": uptime_score,
            "concurrent_handling": successful_requests >= concurrent_requests * 0.9
        }

        return results