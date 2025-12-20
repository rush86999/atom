"""
Additional Service E2E Tests for Atom Platform
Tests service categories not covered by other test files:
- Email (dedicated), Calendar, Database, Webhook, MCP, Main Agent, AI
"""

import json
import time
from typing import Any, Dict

import requests

from config.test_config import TestConfig


def run_tests(config: TestConfig) -> Dict[str, Any]:
    """
    Run additional service E2E tests

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

    # Test 1: Email service endpoints (dedicated test beyond communication)
    email_results = _test_email_service(config)
    results["tests_run"] += email_results["tests_run"]
    results["tests_passed"] += email_results["tests_passed"]
    results["tests_failed"] += email_results["tests_failed"]
    results["test_details"].update(email_results["test_details"])

    # Test 2: Calendar service
    calendar_results = _test_calendar_service(config)
    results["tests_run"] += calendar_results["tests_run"]
    results["tests_passed"] += calendar_results["tests_passed"]
    results["tests_failed"] += calendar_results["tests_failed"]
    results["test_details"].update(calendar_results["test_details"])

    # Test 3: Database service
    database_results = _test_database_service(config)
    results["tests_run"] += database_results["tests_run"]
    results["tests_passed"] += database_results["tests_passed"]
    results["tests_failed"] += database_results["tests_failed"]
    results["test_details"].update(database_results["test_details"])

    # Test 4: Webhook service
    webhook_results = _test_webhook_service(config)
    results["tests_run"] += webhook_results["tests_run"]
    results["tests_passed"] += webhook_results["tests_passed"]
    results["tests_failed"] += webhook_results["tests_failed"]
    results["test_details"].update(webhook_results["test_details"])

    # Test 5: MCP (Model Context Protocol) service
    mcp_results = _test_mcp_service(config)
    results["tests_run"] += mcp_results["tests_run"]
    results["tests_passed"] += mcp_results["tests_passed"]
    results["tests_failed"] += mcp_results["tests_failed"]
    results["test_details"].update(mcp_results["test_details"])

    # Test 6: Main Agent service
    main_agent_results = _test_main_agent_service(config)
    results["tests_run"] += main_agent_results["tests_run"]
    results["tests_passed"] += main_agent_results["tests_passed"]
    results["tests_failed"] += main_agent_results["tests_failed"]
    results["test_details"].update(main_agent_results["test_details"])

    # Test 7: AI service (dedicated beyond workflow AI)
    ai_results = _test_ai_service(config)
    results["tests_run"] += ai_results["tests_run"]
    results["tests_passed"] += ai_results["tests_passed"]
    results["tests_failed"] += ai_results["tests_failed"]
    results["test_details"].update(ai_results["test_details"])

    results["end_time"] = time.time()
    results["duration_seconds"] = results["end_time"] - results["start_time"]

    return results


def _test_email_service(config: TestConfig) -> Dict[str, Any]:
    """Test Email service endpoints"""
    tests_run = 0
    tests_passed = 0
    tests_failed = 0
    test_details = {}

    try:
        # Check if email endpoint is reachable
        response = requests.get(f"{config.api_base_url}/api/email/health", timeout=10)
        tests_run += 1
        if response.status_code == 200:
            tests_passed += 1
            test_details["email_health"] = {"status": "passed", "response": response.json()}
        else:
            tests_failed += 1
            test_details["email_health"] = {"status": "failed", "status_code": response.status_code}
    except Exception as e:
        tests_run += 1
        tests_failed += 1
        test_details["email_health"] = {"status": "error", "error": str(e)}

    return {
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "test_details": test_details
    }


def _test_calendar_service(config: TestConfig) -> Dict[str, Any]:
    """Test Calendar service endpoints"""
    tests_run = 0
    tests_passed = 0
    tests_failed = 0
    test_details = {}

    try:
        # Check if calendar endpoint is reachable
        response = requests.get(f"{config.api_base_url}/api/calendar/health", timeout=10)
        tests_run += 1
        if response.status_code == 200:
            tests_passed += 1
            test_details["calendar_health"] = {"status": "passed", "response": response.json()}
        else:
            tests_failed += 1
            test_details["calendar_health"] = {"status": "failed", "status_code": response.status_code}
    except Exception as e:
        tests_run += 1
        tests_failed += 1
        test_details["calendar_health"] = {"status": "error", "error": str(e)}

    return {
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "test_details": test_details
    }


def _test_database_service(config: TestConfig) -> Dict[str, Any]:
    """Test Database service endpoints"""
    tests_run = 0
    tests_passed = 0
    tests_failed = 0
    test_details = {}

    try:
        # Check if database endpoint is reachable
        response = requests.get(f"{config.api_base_url}/api/database/health", timeout=10)
        tests_run += 1
        if response.status_code == 200:
            tests_passed += 1
            test_details["database_health"] = {"status": "passed", "response": response.json()}
        else:
            tests_failed += 1
            test_details["database_health"] = {"status": "failed", "status_code": response.status_code}
    except Exception as e:
        tests_run += 1
        tests_failed += 1
        test_details["database_health"] = {"status": "error", "error": str(e)}

    return {
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "test_details": test_details
    }


def _test_webhook_service(config: TestConfig) -> Dict[str, Any]:
    """Test Webhook service endpoints"""
    tests_run = 0
    tests_passed = 0
    tests_failed = 0
    test_details = {}

    try:
        # Check if webhook endpoint is reachable
        response = requests.get(f"{config.api_base_url}/api/webhook/health", timeout=10)
        tests_run += 1
        if response.status_code == 200:
            tests_passed += 1
            test_details["webhook_health"] = {"status": "passed", "response": response.json()}
        else:
            tests_failed += 1
            test_details["webhook_health"] = {"status": "failed", "status_code": response.status_code}
    except Exception as e:
        tests_run += 1
        tests_failed += 1
        test_details["webhook_health"] = {"status": "error", "error": str(e)}

    return {
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "test_details": test_details
    }


def _test_mcp_service(config: TestConfig) -> Dict[str, Any]:
    """Test MCP service endpoints"""
    tests_run = 0
    tests_passed = 0
    tests_failed = 0
    test_details = {}

    try:
        # Check if MCP endpoint is reachable
        response = requests.get(f"{config.api_base_url}/api/mcp/health", timeout=10)
        tests_run += 1
        if response.status_code == 200:
            tests_passed += 1
            test_details["mcp_health"] = {"status": "passed", "response": response.json()}
        else:
            tests_failed += 1
            test_details["mcp_health"] = {"status": "failed", "status_code": response.status_code}
    except Exception as e:
        tests_run += 1
        tests_failed += 1
        test_details["mcp_health"] = {"status": "error", "error": str(e)}

    return {
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "test_details": test_details
    }


def _test_main_agent_service(config: TestConfig) -> Dict[str, Any]:
    """Test Main Agent service endpoints"""
    tests_run = 0
    tests_passed = 0
    tests_failed = 0
    test_details = {}

    try:
        # Check if main agent endpoint is reachable
        response = requests.get(f"{config.api_base_url}/api/agent/health", timeout=10)
        tests_run += 1
        if response.status_code == 200:
            tests_passed += 1
            test_details["main_agent_health"] = {"status": "passed", "response": response.json()}
        else:
            tests_failed += 1
            test_details["main_agent_health"] = {"status": "failed", "status_code": response.status_code}
    except Exception as e:
        tests_run += 1
        tests_failed += 1
        test_details["main_agent_health"] = {"status": "error", "error": str(e)}

    return {
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "test_details": test_details
    }


def _test_ai_service(config: TestConfig) -> Dict[str, Any]:
    """Test AI service endpoints"""
    tests_run = 0
    tests_passed = 0
    tests_failed = 0
    test_details = {}

    try:
        # Check if AI endpoint is reachable
        response = requests.get(f"{config.api_base_url}/api/ai/health", timeout=10)
        tests_run += 1
        if response.status_code == 200:
            tests_passed += 1
            test_details["ai_health"] = {"status": "passed", "response": response.json()}
        else:
            tests_failed += 1
            test_details["ai_health"] = {"status": "failed", "status_code": response.status_code}
    except Exception as e:
        tests_run += 1
        tests_failed += 1
        test_details["ai_health"] = {"status": "error", "error": str(e)}

    return {
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "test_details": test_details
    }


if __name__ == "__main__":
    # For local testing
    from config.test_config import TestConfig
    config = TestConfig()
    results = run_tests(config)
    print(json.dumps(results, indent=2))