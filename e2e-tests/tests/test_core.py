"""
Core Functionality E2E Tests for Atom Platform
Tests natural language workflow creation, conversational automation, and AI memory
"""

import json
import time
from typing import Any, Dict, List, Optional

import requests

from config.test_config import TestConfig


def run_tests(config: TestConfig) -> Dict[str, Any]:
    """
    Run core functionality E2E tests

    Args:
        config: Test configuration

    Returns:
        Test results with outputs for LLM verification
    """
    results = {
        "tests_run": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "test_details": {},
        "test_outputs": {},
        "start_time": time.time(),
    }

    # Test 1: Health check and basic connectivity
    results.update(_test_health_check(config))

    # Test 2: Natural language workflow creation
    results.update(_test_natural_language_workflow(config))

    # Test 3: Conversational automation
    results.update(_test_conversational_automation(config))

    # Test 4: AI memory and context management
    results.update(_test_ai_memory(config))

    # Test 5: Service registry and integration discovery
    results.update(_test_service_registry(config))

    results["end_time"] = time.time()
    results["duration_seconds"] = results["end_time"] - results["start_time"]

    return results


def _test_health_check(config: TestConfig) -> Dict[str, Any]:
    """Test basic health and connectivity"""
    test_name = "health_check"
    test_details = {
        "test_name": test_name,
        "description": "Test basic health endpoints and connectivity",
        "status": "failed",
        "details": {},
    }

    try:
        # Test backend health
        backend_response = requests.get(f"{config.BACKEND_URL}/health", timeout=10)
        test_details["details"]["backend_health"] = {
            "status_code": backend_response.status_code,
            "response": backend_response.json()
            if backend_response.status_code == 200
            else None,
        }

        # Test frontend health (via API endpoint)
        frontend_response = requests.get(
            f"{config.FRONTEND_URL}/api/health", timeout=10
        )
        test_details["details"]["frontend_health"] = {
            "status_code": frontend_response.status_code,
            "response": frontend_response.json()
            if frontend_response.status_code == 200
            else None,
        }

        # Test root endpoint
        root_response = requests.get(f"{config.BACKEND_URL}/", timeout=10)
        test_details["details"]["root_endpoint"] = {
            "status_code": root_response.status_code,
            "response": root_response.json()
            if root_response.status_code == 200
            else None,
        }

        # Determine test status
        if (
            backend_response.status_code == 200
            and frontend_response.status_code == 200
            and root_response.status_code == 200
        ):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
        "test_outputs": {test_name: test_details["details"]},
    }


def _test_natural_language_workflow(config: TestConfig) -> Dict[str, Any]:
    """Test natural language workflow creation capabilities"""
    test_name = "natural_language_workflow"
    test_details = {
        "test_name": test_name,
        "description": "Test creating workflows through natural language commands",
        "status": "failed",
        "details": {},
    }

    try:
        # Test workflow endpoints availability
        workflow_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/workflows", timeout=10
        )
        test_details["details"]["workflow_endpoints"] = {
            "status_code": workflow_endpoints_response.status_code,
            "available": workflow_endpoints_response.status_code == 200,
        }

        # Test workflow creation with natural language
        test_workflow_payload = {
            "description": "Create a workflow that sends a Slack message when a new task is created in Asana",
            "trigger_service": "asana",
            "action_service": "slack",
            "parameters": {
                "trigger_event": "task_created",
                "action_type": "send_message",
                "channel": "#general",
                "message_template": "New task created: {task_name}",
            },
        }

        workflow_creation_response = requests.post(
            f"{config.BACKEND_URL}/api/v1/workflows",
            json=test_workflow_payload,
            timeout=30,
        )

        test_details["details"]["workflow_creation"] = {
            "status_code": workflow_creation_response.status_code,
            "response": workflow_creation_response.json()
            if workflow_creation_response.status_code in [200, 201]
            else None,
            "workflow_created": workflow_creation_response.status_code in [200, 201],
        }

        # Test workflow listing
        if workflow_creation_response.status_code in [200, 201]:
            workflow_list_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/workflows", timeout=10
            )
            test_details["details"]["workflow_listing"] = {
                "status_code": workflow_list_response.status_code,
                "workflows_count": len(
                    workflow_list_response.json().get("workflows", [])
                )
                if workflow_list_response.status_code == 200
                else 0,
            }

        # Determine test status based on endpoint availability and basic functionality
        if test_details["details"]["workflow_endpoints"]["available"] and test_details[
            "details"
        ]["workflow_creation"]["status_code"] in [200, 201]:
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
        "test_outputs": {test_name: test_details["details"]},
    }


def _test_conversational_automation(config: TestConfig) -> Dict[str, Any]:
    """Test conversational automation capabilities"""
    test_name = "conversational_automation"
    test_details = {
        "test_name": test_name,
        "description": "Test automation through conversational interface",
        "status": "failed",
        "details": {},
    }

    try:
        # Test chat interface endpoints
        chat_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/chat", timeout=10
        )
        test_details["details"]["chat_endpoints"] = {
            "status_code": chat_endpoints_response.status_code,
            "available": chat_endpoints_response.status_code == 200,
        }

        # Test conversational command processing
        test_commands = [
            "What tasks do I have due today?",
            "Show me my recent messages",
            "Schedule a meeting for tomorrow at 2 PM",
            "Search for project documents",
        ]

        command_responses = {}
        for i, command in enumerate(test_commands):
            try:
                chat_response = requests.post(
                    f"{config.BACKEND_URL}/api/v1/chat/message",
                    json={"message": command, "context": "test_conversation"},
                    timeout=15,
                )
                command_responses[f"command_{i + 1}"] = {
                    "command": command,
                    "status_code": chat_response.status_code,
                    "response_received": chat_response.status_code == 200,
                    "response_type": type(chat_response.json()).__name__
                    if chat_response.status_code == 200
                    else None,
                }
            except Exception as e:
                command_responses[f"command_{i + 1}"] = {
                    "command": command,
                    "error": str(e),
                }

        test_details["details"]["conversational_commands"] = command_responses

        # Calculate success rate
        successful_commands = sum(
            1
            for cmd in command_responses.values()
            if cmd.get("response_received", False)
        )
        test_details["details"]["command_success_rate"] = successful_commands / len(
            test_commands
        )

        # Determine test status
        if (
            test_details["details"]["chat_endpoints"]["available"]
            and successful_commands >= 2
        ):  # At least 50% success rate
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
        "test_outputs": {test_name: test_details["details"]},
    }


def _test_ai_memory(config: TestConfig) -> Dict[str, Any]:
    """Test AI memory and context management"""
    test_name = "ai_memory"
    test_details = {
        "test_name": test_name,
        "description": "Test AI memory and context persistence across conversations",
        "status": "failed",
        "details": {},
    }

    try:
        # Test memory endpoints
        memory_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/memory", timeout=10
        )
        test_details["details"]["memory_endpoints"] = {
            "status_code": memory_endpoints_response.status_code,
            "available": memory_endpoints_response.status_code == 200,
        }

        # Test context persistence
        conversation_id = f"test_conversation_{int(time.time())}"

        # First message - establish context
        first_message = {
            "message": "I'm working on the Project Phoenix documentation",
            "conversation_id": conversation_id,
            "user_id": "test_user",
        }

        first_response = requests.post(
            f"{config.BACKEND_URL}/api/v1/chat/message", json=first_message, timeout=15
        )

        test_details["details"]["first_message"] = {
            "status_code": first_response.status_code,
            "context_established": first_response.status_code == 200,
        }

        # Second message - test context recall
        if first_response.status_code == 200:
            second_message = {
                "message": "What was I working on?",
                "conversation_id": conversation_id,
                "user_id": "test_user",
            }

            second_response = requests.post(
                f"{config.BACKEND_URL}/api/v1/chat/message",
                json=second_message,
                timeout=15,
            )

            second_response_data = (
                second_response.json() if second_response.status_code == 200 else {}
            )
            test_details["details"]["second_message"] = {
                "status_code": second_response.status_code,
                "response": second_response_data.get("response", ""),
                "context_recalled": "Project Phoenix"
                in str(second_response_data.get("response", "")),
            }

        # Test memory retrieval
        memory_retrieval_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/memory/{conversation_id}", timeout=10
        )
        test_details["details"]["memory_retrieval"] = {
            "status_code": memory_retrieval_response.status_code,
            "memory_entries": len(memory_retrieval_response.json().get("memories", []))
            if memory_retrieval_response.status_code == 200
            else 0,
        }

        # Determine test status
        if test_details["details"]["memory_endpoints"]["available"] and test_details[
            "details"
        ].get("second_message", {}).get("context_recalled", False):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
        "test_outputs": {test_name: test_details["details"]},
    }


def _test_service_registry(config: TestConfig) -> Dict[str, Any]:
    """Test service registry and integration discovery"""
    test_name = "service_registry"
    test_details = {
        "test_name": test_name,
        "description": "Test service registry and available integrations",
        "status": "failed",
        "details": {},
    }

    try:
        # Test service registry endpoints
        service_registry_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/services", timeout=10
        )
        test_details["details"]["service_registry"] = {
            "status_code": service_registry_response.status_code,
            "available": service_registry_response.status_code == 200,
        }

        if service_registry_response.status_code == 200:
            services_data = service_registry_response.json()
            test_details["details"]["services"] = {
                "total_services": len(services_data.get("services", [])),
                "available_services": [
                    s.get("name")
                    for s in services_data.get("services", [])
                    if s.get("available", False)
                ],
                "unavailable_services": [
                    s.get("name")
                    for s in services_data.get("services", [])
                    if not s.get("available", False)
                ],
            }

        # Test integration status
        integration_status_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/integrations/status", timeout=10
        )
        test_details["details"]["integration_status"] = {
            "status_code": integration_status_response.status_code,
            "integrations_count": len(
                integration_status_response.json().get("integrations", [])
            )
            if integration_status_response.status_code == 200
            else 0,
        }

        # Test BYOK (Bring Your Own Key) system
        byok_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/byok/status", timeout=10
        )
        test_details["details"]["byok_system"] = {
            "status_code": byok_response.status_code,
            "available": byok_response.status_code == 200,
        }

        # Determine test status
        if (
            test_details["details"]["service_registry"]["available"]
            and test_details["details"].get("services", {}).get("total_services", 0) > 0
        ):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
        "test_outputs": {test_name: test_details["details"]},
    }


# Individual test functions for specific execution
def test_health_check(config: TestConfig) -> Dict[str, Any]:
    """Run only health check test"""
    return _test_health_check(config)


def test_natural_language_workflow(config: TestConfig) -> Dict[str, Any]:
    """Run only natural language workflow test"""
    return _test_natural_language_workflow(config)


def test_conversational_automation(config: TestConfig) -> Dict[str, Any]:
    """Run only conversational automation test"""
    return _test_conversational_automation(config)


def test_ai_memory(config: TestConfig) -> Dict[str, Any]:
    """Run only AI memory test"""
    return _test_ai_memory(config)


def test_service_registry(config: TestConfig) -> Dict[str, Any]:
    """Run only service registry test"""
    return _test_service_registry(config)
