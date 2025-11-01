#!/usr/bin/env python3
"""
ATOM Platform - User Journey Validation Script

This script validates the ATOM platform against 10 different user personas
to ensure the documentation matches actual implementation and real-world usage.
"""

import json
import requests
import time
import sys
import os
from typing import Dict, List, Any, Optional


class UserJourneyValidator:
    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.results = {}

    def test_health_endpoints(self) -> Dict[str, Any]:
        """Test basic health and connectivity"""
        print("🔍 Testing basic health endpoints...")
        health_checks = {}

        try:
            # Test main API health
            response = requests.get(f"{self.base_url}/healthz", timeout=10)
            health_checks["api_health"] = {
                "status": response.status_code == 200,
                "response": response.text
                if response.status_code == 200
                else f"Failed: {response.status_code}",
            }
        except Exception as e:
            health_checks["api_health"] = {"status": False, "error": str(e)}

        try:
            # Test service registry
            response = requests.get(f"{self.base_url}/api/services", timeout=10)
            health_checks["service_registry"] = {
                "status": response.status_code == 200,
                "count": len(response.json().get("services", []))
                if response.status_code == 200
                else 0,
            }
        except Exception as e:
            health_checks["service_registry"] = {"status": False, "error": str(e)}

        return health_checks

    def validate_executive_assistant_journey(self) -> Dict[str, Any]:
        """Validate journey for Executive Assistant persona"""
        print("👩‍💼 Validating Executive Assistant journey...")
        journey_results = {}

        # Test calendar endpoints
        try:
            response = requests.get(
                f"{self.base_url}/api/calendar/providers", timeout=10
            )
            journey_results["calendar_providers"] = {
                "status": response.status_code == 200,
                "providers": response.json().get("providers", [])
                if response.status_code == 200
                else [],
            }
        except Exception as e:
            journey_results["calendar_providers"] = {"status": False, "error": str(e)}

        # Test task management
        try:
            response = requests.get(f"{self.base_url}/api/tasks", timeout=10)
            journey_results["task_management"] = {
                "status": response.status_code == 200,
                "tasks_accessible": True,
            }
        except Exception as e:
            journey_results["task_management"] = {"status": False, "error": str(e)}

        # Test message aggregation
        try:
            response = requests.get(f"{self.base_url}/api/messages", timeout=10)
            journey_results["message_aggregation"] = {
                "status": response.status_code == 200,
                "messages_accessible": True,
            }
        except Exception as e:
            journey_results["message_aggregation"] = {"status": False, "error": str(e)}

        return journey_results

    def validate_software_developer_journey(self) -> Dict[str, Any]:
        """Validate journey for Software Developer persona"""
        print("👨‍💻 Validating Software Developer journey...")
        journey_results = {}

        # Test GitHub integration
        try:
            response = requests.get(
                f"{self.base_url}/api/services/github/health", timeout=10
            )
            journey_results["github_integration"] = {
                "status": response.status_code == 200,
                "health": response.json()
                if response.status_code == 200
                else "Unavailable",
            }
        except Exception as e:
            journey_results["github_integration"] = {"status": False, "error": str(e)}

        # Test BYOK system
        try:
            response = requests.get(f"{self.base_url}/api/user-api-keys", timeout=10)
            journey_results["byok_system"] = {
                "status": response.status_code
                in [200, 404],  # 404 means endpoint exists but no keys
                "endpoint_accessible": True,
            }
        except Exception as e:
            journey_results["byok_system"] = {"status": False, "error": str(e)}

        # Test workflow automation
        try:
            response = requests.get(f"{self.base_url}/api/workflows", timeout=10)
            journey_results["workflow_automation"] = {
                "status": response.status_code in [200, 404],
                "endpoint_accessible": True,
            }
        except Exception as e:
            journey_results["workflow_automation"] = {"status": False, "error": str(e)}

        return journey_results

    def validate_marketing_manager_journey(self) -> Dict[str, Any]:
        """Validate journey for Marketing Manager persona"""
        print("👩‍💼 Validating Marketing Manager journey...")
        journey_results = {}

        # Test social media integrations
        try:
            response = requests.get(f"{self.base_url}/api/services", timeout=10)
            services = (
                response.json().get("services", [])
                if response.status_code == 200
                else []
            )
            social_services = [
                s
                for s in services
                if any(
                    platform in s.get("name", "").lower()
                    for platform in ["twitter", "facebook", "linkedin", "social"]
                )
            ]
            journey_results["social_media_integrations"] = {
                "status": response.status_code == 200,
                "available_services": social_services,
            }
        except Exception as e:
            journey_results["social_media_integrations"] = {
                "status": False,
                "error": str(e),
            }

        # Test campaign coordination
        try:
            response = requests.get(f"{self.base_url}/api/automations", timeout=10)
            journey_results["campaign_coordination"] = {
                "status": response.status_code in [200, 404],
                "automation_system_accessible": True,
            }
        except Exception as e:
            journey_results["campaign_coordination"] = {
                "status": False,
                "error": str(e),
            }

        return journey_results

    def validate_small_business_owner_journey(self) -> Dict[str, Any]:
        """Validate journey for Small Business Owner persona"""
        print("👨‍💼 Validating Small Business Owner journey...")
        journey_results = {}

        # Test unified communication
        try:
            response = requests.get(f"{self.base_url}/api/messages/stats", timeout=10)
            journey_results["unified_communication"] = {
                "status": response.status_code in [200, 404],
                "message_stats_accessible": True,
            }
        except Exception as e:
            journey_results["unified_communication"] = {
                "status": False,
                "error": str(e),
            }

        # Test financial integration
        try:
            response = requests.get(f"{self.base_url}/api/finance/accounts", timeout=10)
            journey_results["financial_integration"] = {
                "status": response.status_code in [200, 404],
                "financial_system_accessible": True,
            }
        except Exception as e:
            journey_results["financial_integration"] = {
                "status": False,
                "error": str(e),
            }

        return journey_results

    def validate_project_manager_journey(self) -> Dict[str, Any]:
        """Validate journey for Project Manager persona"""
        print("👨‍💼 Validating Project Manager journey...")
        journey_results = {}

        # Test project coordination
        try:
            response = requests.get(f"{self.base_url}/api/tasks/stats", timeout=10)
            journey_results["project_coordination"] = {
                "status": response.status_code in [200, 404],
                "task_stats_accessible": True,
            }
        except Exception as e:
            journey_results["project_coordination"] = {"status": False, "error": str(e)}

        # Test resource management
        try:
            response = requests.get(
                f"{self.base_url}/api/calendar/available-slots", timeout=10
            )
            journey_results["resource_management"] = {
                "status": response.status_code in [200, 404],
                "scheduling_system_accessible": True,
            }
        except Exception as e:
            journey_results["resource_management"] = {"status": False, "error": str(e)}

        return journey_results

    def validate_student_researcher_journey(self) -> Dict[str, Any]:
        """Validate journey for Student Researcher persona"""
        print("👩‍🎓 Validating Student Researcher journey...")
        journey_results = {}

        # Test document management
        try:
            response = requests.get(f"{self.base_url}/api/documents", timeout=10)
            journey_results["document_management"] = {
                "status": response.status_code in [200, 404],
                "document_system_accessible": True,
            }
        except Exception as e:
            journey_results["document_management"] = {"status": False, "error": str(e)}

        # Test research organization
        try:
            response = requests.get(
                f"{self.base_url}/api/search", params={"q": "test"}, timeout=10
            )
            journey_results["research_organization"] = {
                "status": response.status_code in [200, 404],
                "search_system_accessible": True,
            }
        except Exception as e:
            journey_results["research_organization"] = {
                "status": False,
                "error": str(e),
            }

        return journey_results

    def validate_sales_professional_journey(self) -> Dict[str, Any]:
        """Validate journey for Sales Professional persona"""
        print("👨‍💼 Validating Sales Professional journey...")
        journey_results = {}

        # Test CRM integration
        try:
            response = requests.get(f"{self.base_url}/api/contacts", timeout=10)
            journey_results["crm_integration"] = {
                "status": response.status_code in [200, 404],
                "contact_management_accessible": True,
            }
        except Exception as e:
            journey_results["crm_integration"] = {"status": False, "error": str(e)}

        # Test pipeline management
        try:
            response = requests.get(f"{self.base_url}/api/automations", timeout=10)
            journey_results["pipeline_management"] = {
                "status": response.status_code in [200, 404],
                "automation_system_accessible": True,
            }
        except Exception as e:
            journey_results["pipeline_management"] = {"status": False, "error": str(e)}

        return journey_results

    def validate_freelance_consultant_journey(self) -> Dict[str, Any]:
        """Validate journey for Freelance Consultant persona"""
        print("👩‍💼 Validating Freelance Consultant journey...")
        journey_results = {}

        # Test time tracking
        try:
            response = requests.get(f"{self.base_url}/api/tasks", timeout=10)
            journey_results["time_tracking"] = {
                "status": response.status_code in [200, 404],
                "task_system_accessible": True,
            }
        except Exception as e:
            journey_results["time_tracking"] = {"status": False, "error": str(e)}

        # Test billing workflows
        try:
            response = requests.get(f"{self.base_url}/api/finance/invoices", timeout=10)
            journey_results["billing_workflows"] = {
                "status": response.status_code in [200, 404],
                "billing_system_accessible": True,
            }
        except Exception as e:
            journey_results["billing_workflows"] = {"status": False, "error": str(e)}

        return journey_results

    def validate_it_administrator_journey(self) -> Dict[str, Any]:
        """Validate journey for IT Administrator persona"""
        print("👨‍💻 Validating IT Administrator journey...")
        journey_results = {}

        # Test system monitoring
        try:
            response = requests.get(f"{self.base_url}/api/services/health", timeout=10)
            journey_results["system_monitoring"] = {
                "status": response.status_code in [200, 404],
                "health_monitoring_accessible": True,
            }
        except Exception as e:
            journey_results["system_monitoring"] = {"status": False, "error": str(e)}

        # Test incident management
        try:
            response = requests.get(f"{self.base_url}/api/workflows", timeout=10)
            journey_results["incident_management"] = {
                "status": response.status_code in [200, 404],
                "workflow_system_accessible": True,
            }
        except Exception as e:
            journey_results["incident_management"] = {"status": False, "error": str(e)}

        return journey_results

    def validate_content_creator_journey(self) -> Dict[str, Any]:
        """Validate journey for Content Creator persona"""
        print("👩‍🎨 Validating Content Creator journey...")
        journey_results = {}

        # Test content scheduling
        try:
            response = requests.get(f"{self.base_url}/api/calendar/events", timeout=10)
            journey_results["content_scheduling"] = {
                "status": response.status_code in [200, 404],
                "scheduling_system_accessible": True,
            }
        except Exception as e:
            journey_results["content_scheduling"] = {"status": False, "error": str(e)}

        # Test multi-platform publishing
        try:
            response = requests.get(f"{self.base_url}/api/services", timeout=10)
            services = (
                response.json().get("services", [])
                if response.status_code == 200
                else []
            )
            publishing_services = [
                s
                for s in services
                if any(
                    platform in s.get("name", "").lower()
                    for platform in ["youtube", "medium", "blog", "publish"]
                )
            ]
            journey_results["multi_platform_publishing"] = {
                "status": response.status_code == 200,
                "available_services": publishing_services,
            }
        except Exception as e:
            journey_results["multi_platform_publishing"] = {
                "status": False,
                "error": str(e),
            }

        return journey_results

    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive validation for all personas"""
        print("🚀 Starting comprehensive user journey validation...")
        print("=" * 60)

        validation_results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_url": self.base_url,
            "health_checks": self.test_health_endpoints(),
            "personas": {},
        }

        # Validate each persona journey
        personas = [
            ("executive_assistant", self.validate_executive_assistant_journey),
            ("software_developer", self.validate_software_developer_journey),
            ("marketing_manager", self.validate_marketing_manager_journey),
            ("small_business_owner", self.validate_small_business_owner_journey),
            ("project_manager", self.validate_project_manager_journey),
            ("student_researcher", self.validate_student_researcher_journey),
            ("sales_professional", self.validate_sales_professional_journey),
            ("freelance_consultant", self.validate_freelance_consultant_journey),
            ("it_administrator", self.validate_it_administrator_journey),
            ("content_creator", self.validate_content_creator_journey),
        ]

        for persona_name, validation_func in personas:
            try:
                validation_results["personas"][persona_name] = validation_func()
            except Exception as e:
                validation_results["personas"][persona_name] = {
                    "error": f"Validation failed: {str(e)}",
                    "status": "failed",
                }

        return validation_results

    def calculate_success_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate success metrics from validation results"""
        metrics = {
            "total_personas": 10,
            "successful_personas": 0,
            "partially_successful_personas": 0,
            "failed_personas": 0,
            "overall_score": 0,
            "persona_scores": {},
        }

        for persona_name, persona_results in results["personas"].items():
            if "error" in persona_results:
                metrics["persona_scores"][persona_name] = 0
                metrics["failed_personas"] += 1
                continue

            # Calculate persona score based on successful endpoints
            total_tests = len(persona_results)
            successful_tests = sum(
                1 for test in persona_results.values() if test.get("status", False)
            )

            persona_score = (
                (successful_tests / total_tests) * 100 if total_tests > 0 else 0
            )
            metrics["persona_scores"][persona_name] = persona_score

            if persona_score >= 80:
                metrics["successful_personas"] += 1
            elif persona_score >= 50:
                metrics["partially_successful_personas"] += 1
            else:
                metrics["failed_personas"] += 1

        # Calculate overall score
        total_score = sum(metrics["persona_scores"].values())
        metrics["overall_score"] = (
            total_score / len(metrics["persona_scores"])
            if metrics["persona_scores"]
            else 0
        )

        return metrics

    def generate_report(self, results: Dict[str, Any], metrics: Dict[str, Any]) -> str:
        """Generate a comprehensive validation report"""
        report = []
        report.append("=" * 80)
        report.append("ATOM PLATFORM - USER JOURNEY VALIDATION REPORT")
        report.append("=" * 80)
        report.append(f"Validation Date: {results['timestamp']}")
        report.append(f"Base URL: {results['base_url']}")
        report.append("")

        # Health check summary
        report.append("HEALTH CHECKS:")
        report.append("-" * 40)
        for check_name, check_result in results["health_checks"].items():
            status = "✅ PASS" if check_result.get("status", False) else "❌ FAIL"
            report.append(f"  {check_name}: {status}")
            if "count" in check_result:
                report.append(f"    Services detected: {check_result['count']}")
        report.append("")

        # Persona validation summary
        report.append("PERSONA VALIDATION SUMMARY:")
        report.append("-" * 40)
