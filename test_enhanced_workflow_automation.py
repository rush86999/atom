#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Comprehensive Test Script for Enhanced Workflow Automation System
Tests all components of the enhanced workflow automation with AI-powered intelligence
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = "http://localhost:5058"
TEST_TIMEOUT = 30


class EnhancedWorkflowAutomationTestSuite:
    """
    Comprehensive test suite for enhanced workflow automation system
    Tests all components including intelligence, optimization, and monitoring
    """

    def __init__(self):
        self.test_results = []
        self.session_id = f"test_session_{int(time.time())}"

    def print_test_header(self, test_name: str):
        """Print formatted test header"""
        print(f"\n{'=' * 60}")
        print(f"🧪 TEST: {test_name}")
        print(f"{'=' * 60}")

    def print_test_result(self, test_name: str, success: bool, details: str = ""):
        """Print formatted test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   📝 {details}")

        # Store result
        self.test_results.append(
            {
                "test_name": test_name,
                "success": success,
                "details": details,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def test_enhanced_service_detection(self) -> bool:
        """Test enhanced service detection with AI-powered intelligence"""
        self.print_test_header("Enhanced Service Detection")

        test_cases = [
            {
                "name": "Multi-Service Email to Task",
                "input": "When I receive an important email from gmail, create a task in asana and send a slack notification to my team",
                "expected_services": ["gmail", "asana", "slack"],
                "complexity": "medium",
            },
            {
                "name": "Meeting Follow-up Workflow",
                "input": "After a calendar meeting in google calendar, create tasks in trello and send follow-up emails using gmail",
                "expected_services": ["google_calendar", "trello", "gmail"],
                "complexity": "medium",
            },
            {
                "name": "Document Processing Pipeline",
                "input": "When a document is uploaded to dropbox, process it and save to google drive for sharing with the team",
                "expected_services": ["dropbox", "google_drive", "slack"],
                "complexity": "complex",
            },
            {
                "name": "Customer Support Automation",
                "input": "When a support email arrives in gmail, create a ticket in salesforce and notify the team on slack",
                "expected_services": ["gmail", "salesforce", "slack"],
                "complexity": "advanced",
            },
            {
                "name": "Development Workflow",
                "input": "When a github issue is created, create a corresponding task in asana and notify the team",
                "expected_services": ["github", "asana", "slack"],
                "complexity": "medium",
            },
        ]

        success_count = 0
        total_tests = len(test_cases)

        for test_case in test_cases:
            try:
                response = requests.post(
                    f"{BASE_URL}/api/workflows/automation/generate",
                    json={
                        "user_input": test_case["input"],
                        "user_id": self.session_id,
                        "enhanced_intelligence": True,
                    },
                    timeout=TEST_TIMEOUT,
                )

                if response.status_code == 200:
                    result = response.json()
                    detected_services = result.get("services", [])
                    workflow_steps = len(result.get("steps", []))

                    # Calculate detection accuracy
                    matched_services = []
                    for expected in test_case["expected_services"]:
                        for detected in detected_services:
                            if (
                                expected in detected.lower()
                                or detected.lower() in expected
                            ):
                                matched_services.append(expected)
                                break

                    accuracy = len(matched_services) / len(
                        test_case["expected_services"]
                    )

                    test_success = accuracy >= 0.7  # 70% accuracy threshold

                    details = (
                        f"Accuracy: {accuracy:.1%} | "
                        f"Detected: {detected_services} | "
                        f"Expected: {test_case['expected_services']} | "
                        f"Steps: {workflow_steps}"
                    )

                    self.print_test_result(test_case["name"], test_success, details)

                    if test_success:
                        success_count += 1
                else:
                    self.print_test_result(
                        test_case["name"],
                        False,
                        f"API Error: HTTP {response.status_code}",
                    )

            except Exception as e:
                self.print_test_result(test_case["name"], False, f"Exception: {str(e)}")

        overall_success = success_count / total_tests >= 0.8  # 80% success rate
        self.print_test_result(
            "Enhanced Service Detection Overall",
            overall_success,
            f"Passed {success_count}/{total_tests} tests",
        )

        return overall_success

    def test_workflow_optimization(self) -> bool:
        """Test AI-powered workflow optimization"""
        self.print_test_header("Workflow Optimization")

        optimization_tests = [
            {
                "name": "Performance Optimization",
                "workflow": {
                    "name": "Performance Test Workflow",
                    "steps": [
                        {
                            "action": "search_emails",
                            "service": "gmail",
                            "estimated_duration": 5.0,
                        },
                        {
                            "action": "create_task",
                            "service": "asana",
                            "estimated_duration": 3.0,
                        },
                        {
                            "action": "send_notification",
                            "service": "slack",
                            "estimated_duration": 2.0,
                        },
                    ],
                },
                "optimization_strategy": "performance",
            },
            {
                "name": "Cost Optimization",
                "workflow": {
                    "name": "Cost Test Workflow",
                    "steps": [
                        {
                            "action": "process_document",
                            "service": "dropbox",
                            "estimated_duration": 10.0,
                        },
                        {
                            "action": "upload_file",
                            "service": "google_drive",
                            "estimated_duration": 8.0,
                        },
                        {
                            "action": "notify_team",
                            "service": "slack",
                            "estimated_duration": 2.0,
                        },
                    ],
                },
                "optimization_strategy": "cost",
            },
            {
                "name": "Reliability Optimization",
                "workflow": {
                    "name": "Reliability Test Workflow",
                    "steps": [
                        {
                            "action": "create_issue",
                            "service": "github",
                            "estimated_duration": 4.0,
                        },
                        {
                            "action": "assign_task",
                            "service": "asana",
                            "estimated_duration": 3.0,
                        },
                        {
                            "action": "send_update",
                            "service": "slack",
                            "estimated_duration": 2.0,
                        },
                    ],
                },
                "optimization_strategy": "reliability",
            },
        ]

        success_count = 0
        total_tests = len(optimization_tests)

        for test in optimization_tests:
            try:
                response = requests.post(
                    f"{BASE_URL}/api/workflows/optimization/analyze",
                    json={
                        "workflow": test["workflow"],
                        "strategy": test["optimization_strategy"],
                        "user_id": self.session_id,
                    },
                    timeout=TEST_TIMEOUT,
                )

                if response.status_code == 200:
                    result = response.json()

                    # Check if optimization suggestions are provided
                    has_suggestions = (
                        len(result.get("optimization_suggestions", [])) > 0
                    )
                    has_improvements = len(result.get("estimated_improvements", {})) > 0

                    test_success = has_suggestions and has_improvements

                    details = (
                        f"Suggestions: {len(result.get('optimization_suggestions', []))} | "
                        f"Improvements: {len(result.get('estimated_improvements', {}))} | "
                        f"Strategy: {test['optimization_strategy']}"
                    )

                    self.print_test_result(test["name"], test_success, details)

                    if test_success:
                        success_count += 1
                else:
                    self.print_test_result(
                        test["name"], False, f"API Error: HTTP {response.status_code}"
                    )

            except Exception as e:
                self.print_test_result(test["name"], False, f"Exception: {str(e)}")

        overall_success = success_count / total_tests >= 0.8
        self.print_test_result(
            "Workflow Optimization Overall",
            overall_success,
            f"Passed {success_count}/{total_tests} tests",
        )

        return overall_success

    def test_workflow_monitoring(self) -> bool:
        """Test enhanced workflow monitoring and alerting"""
        self.print_test_header("Workflow Monitoring")

        monitoring_tests = [
            {
                "name": "Health Check Endpoint",
                "endpoint": "/api/workflows/monitoring/health",
                "expected_status": 200,
            },
            {
                "name": "Metrics Collection",
                "endpoint": "/api/workflows/monitoring/metrics",
                "expected_status": 200,
            },
            {
                "name": "Alert Management",
                "endpoint": "/api/workflows/monitoring/alerts",
                "expected_status": 200,
            },
        ]

        success_count = 0
        total_tests = len(monitoring_tests)

        for test in monitoring_tests:
            try:
                response = requests.get(
                    f"{BASE_URL}{test['endpoint']}", timeout=TEST_TIMEOUT
                )

                test_success = response.status_code == test["expected_status"]

                details = f"Status: {response.status_code} | Expected: {test['expected_status']}"

                self.print_test_result(test["name"], test_success, details)

                if test_success:
                    success_count += 1

            except Exception as e:
                self.print_test_result(test["name"], False, f"Exception: {str(e)}")

        # Test alert creation
        try:
            alert_test_response = requests.post(
                f"{BASE_URL}/api/workflows/monitoring/alerts",
                json={
                    "workflow_id": "test_workflow",
                    "alert_type": "performance_degradation",
                    "severity": "high",
                    "description": "Test alert from automated testing",
                    "user_id": self.session_id,
                },
                timeout=TEST_TIMEOUT,
            )

            alert_test_success = alert_test_response.status_code in [200, 201]
            self.print_test_result(
                "Alert Creation",
                alert_test_success,
                f"Status: {alert_test_response.status_code}",
            )

            if alert_test_success:
                success_count += 1
                total_tests += 1

        except Exception as e:
            self.print_test_result("Alert Creation", False, f"Exception: {str(e)}")

        overall_success = success_count / total_tests >= 0.8
        self.print_test_result(
            "Workflow Monitoring Overall",
            overall_success,
            f"Passed {success_count}/{total_tests} tests",
        )

        return overall_success

    def test_workflow_execution(self) -> bool:
        """Test enhanced workflow execution with error handling"""
        self.print_test_header("Workflow Execution")

        execution_tests = [
            {
                "name": "Simple Email Workflow",
                "workflow": {
                    "name": "Test Email Workflow",
                    "description": "Send test email workflow",
                    "steps": [
                        {
                            "step_id": "step_1",
                            "action": "send_message",
                            "service": "gmail",
                            "parameters": {
                                "to": "test@example.com",
                                "subject": "Test Workflow Execution",
                                "body": "This is a test workflow execution",
                            },
                        }
                    ],
                },
            },
            {
                "name": "Multi-Service Workflow",
                "workflow": {
                    "name": "Test Multi-Service Workflow",
                    "description": "Test workflow with multiple services",
                    "steps": [
                        {
                            "step_id": "step_1",
                            "action": "create_task",
                            "service": "asana",
                            "parameters": {
                                "name": "Test Task",
                                "description": "Created by automated test",
                            },
                        },
                        {
                            "step_id": "step_2",
                            "action": "send_notification",
                            "service": "slack",
                            "parameters": {
                                "channel": "general",
                                "message": "Task created successfully",
                            },
                        },
                    ],
                },
            },
        ]

        success_count = 0
        total_tests = len(execution_tests)

        for test in execution_tests:
            try:
                response = requests.post(
                    f"{BASE_URL}/api/workflows/execute",
                    json={
                        "workflow": test["workflow"],
                        "user_id": self.session_id,
                        "enhanced_execution": True,
                    },
                    timeout=TEST_TIMEOUT,
                )

                # For execution tests, we consider 200 or 202 as success
                # (202 might be returned for async execution)
                test_success = response.status_code in [200, 202]

                execution_id = response.json().get("execution_id", "unknown")

                details = (
                    f"Status: {response.status_code} | Execution ID: {execution_id}"
                )

                self.print_test_result(test["name"], test_success, details)

                if test_success:
                    success_count += 1

            except Exception as e:
                self.print_test_result(test["name"], False, f"Exception: {str(e)}")

        overall_success = success_count / total_tests >= 0.8
        self.print_test_result(
            "Workflow Execution Overall",
            overall_success,
            f"Passed {success_count}/{total_tests} tests",
        )

        return overall_success

    def test_enhanced_intelligence_features(self) -> bool:
        """Test advanced AI-powered intelligence features"""
        self.print_test_header("Enhanced Intelligence Features")

        intelligence_tests = [
            {
                "name": "Context-Aware Workflow Generation",
                "input": "I need to automate my daily standup process for my development team",
                "expected_features": [
                    "context_aware",
                    "team_collaboration",
                    "daily_routine",
                ],
            },
            {
                "name": "Intelligent Error Recovery",
                "scenario": "simulate_step_failure",
                "expected_features": [
                    "auto_retry",
                    "error_handling",
                    "recovery_strategy",
                ],
            },
            {
                "name": "Performance Prediction",
                "workflow": {
                    "name": "Performance Prediction Test",
                    "steps": [
                        {
                            "action": "process_data",
                            "service": "generic",
                            "estimated_duration": 5.0,
                        },
                        {
                            "action": "generate_report",
                            "service": "generic",
                            "estimated_duration": 3.0,
                        },
                    ],
                },
                "expected_features": ["performance_prediction", "resource_estimation"],
            },
        ]

        success_count = 0
        total_tests = len(intelligence_tests)

        for test in intelligence_tests:
            try:
                if "input" in test:
                    # Test context-aware generation
                    response = requests.post(
                        f"{BASE_URL}/api/workflows/automation/generate",
                        json={
                            "user_input": test["input"],
                            "user_id": self.session_id,
                            "enhanced_intelligence": True,
                            "context_aware": True,
                        },
                        timeout=TEST_TIMEOUT,
                    )
                elif "scenario" in test:
                    # Test error recovery
                    response = requests.post(
                        f"{BASE_URL}/api/workflows/troubleshooting/simulate",
                        json={"scenario": test["scenario"], "user_id": self.session_id},
                        timeout=TEST_TIMEOUT,
                    )
                else:
                    # Test performance prediction
                    response = requests.post(
                        f"{BASE_URL}/api/workflows/optimization/predict",
                        json={"workflow": test["workflow"], "user_id": self.session_id},
                        timeout=TEST_TIMEOUT,
                    )

                test_success = response.status_code == 200

                if test_success:
                    result = response.json()
                    # Check if enhanced features are present
                    has_enhanced_features = result.get("enhanced_features", [])

                    if has_enhanced_features:
                        test_success = True
                        details = f"Enhanced features: {has_enhanced_features}"
                    else:
                        test_success = False
                        details = "No enhanced features detected"
                else:
                    details = f"API Error: HTTP {response.status_code}"

                self.print_test_result(test["name"], test_success, details)

                if test_success:
                    success_count += 1

            except Exception as e:
                self.print_test_result(test["name"], False, f"Exception: {str(e)}")

        overall_success = success_count / total_tests >= 0.8
        self.print_test_result(
            "Enhanced Intelligence Overall",
            overall_success,
            f"Passed {success_count}/{total_tests} tests",
        )

        return overall_success

    def run_comprehensive_test_suite(self) -> Dict[str, Any]:
        """Run all tests and generate comprehensive report"""
        print("🚀 ENHANCED WORKFLOW AUTOMATION TEST SUITE")
        print("=" * 60)
        print(f"Session ID: {self.session_id}")
        print(f"Base URL: {BASE_URL}")
