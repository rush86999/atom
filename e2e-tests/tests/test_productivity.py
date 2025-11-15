"""
Productivity Services E2E Tests for Atom Platform
Tests Asana, Notion, Linear, Monday.com, and Trello integrations
"""

import json
import time
from typing import Any, Dict, List, Optional

import requests

from config.test_config import TestConfig


def run_tests(config: TestConfig) -> Dict[str, Any]:
    """
    Run productivity services E2E tests

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

    # Test 1: Asana integration
    results.update(_test_asana_integration(config))

    # Test 2: Notion integration
    results.update(_test_notion_integration(config))

    # Test 3: Linear integration
    results.update(_test_linear_integration(config))

    # Test 4: Trello integration
    results.update(_test_trello_integration(config))

    # Test 5: Monday.com integration
    results.update(_test_monday_integration(config))

    # Test 6: Cross-platform task coordination
    results.update(_test_cross_platform_tasks(config))

    results["end_time"] = time.time()
    results["duration_seconds"] = results["end_time"] - results["start_time"]

    return results


def _test_asana_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Asana integration capabilities"""
    test_name = "asana_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Asana workspace connectivity and task management",
        "status": "failed",
        "details": {},
    }

    try:
        # Test Asana endpoints availability
        asana_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/asana", timeout=10
        )
        test_details["details"]["asana_endpoints"] = {
            "status_code": asana_endpoints_response.status_code,
            "available": asana_endpoints_response.status_code == 200,
        }

        # Test Asana workspace connection
        asana_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/asana/connection", timeout=10
        )
        test_details["details"]["asana_connection"] = {
            "status_code": asana_connection_response.status_code,
            "connected": asana_connection_response.status_code == 200,
            "workspace_info": asana_connection_response.json()
            if asana_connection_response.status_code == 200
            else None,
        }

        # Test Asana projects listing
        if asana_connection_response.status_code == 200:
            projects_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/asana/projects", timeout=10
            )
            test_details["details"]["asana_projects"] = {
                "status_code": projects_response.status_code,
                "projects_count": len(projects_response.json().get("projects", []))
                if projects_response.status_code == 200
                else 0,
            }

        # Test Asana tasks listing
        if asana_connection_response.status_code == 200:
            tasks_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/asana/tasks", timeout=10
            )
            test_details["details"]["asana_tasks"] = {
                "status_code": tasks_response.status_code,
                "tasks_count": len(tasks_response.json().get("tasks", []))
                if tasks_response.status_code == 200
                else 0,
            }

        # Test Asana task creation
        if test_details["details"].get("asana_projects", {}).get("projects_count", 0) > 0:
            test_task = {
                "name": f"Test Task from Atom E2E - {time.time()}",
                "notes": "This is a test task created by Atom E2E test suite",
                "project_id": "default",
                "test_mode": True
            }

            create_task_response = requests.post(
                f"{config.BACKEND_URL}/api/v1/asana/tasks",
                json=test_task,
                timeout=15
            )

            test_details["details"]["asana_task_creation"] = {
                "status_code": create_task_response.status_code,
                "task_created": create_task_response.status_code in [200, 201],
                "task_id": create_task_response.json().get("task_id")
                if create_task_response.status_code in [200, 201]
                else None,
            }

        # Determine test status
        if (
            test_details["details"]["asana_endpoints"]["available"]
            and test_details["details"]["asana_connection"]["connected"]
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


def _test_notion_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Notion integration capabilities"""
    test_name = "notion_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Notion workspace connectivity and page management",
        "status": "failed",
        "details": {},
    }

    try:
        # Test Notion endpoints availability
        notion_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/notion", timeout=10
        )
        test_details["details"]["notion_endpoints"] = {
            "status_code": notion_endpoints_response.status_code,
            "available": notion_endpoints_response.status_code == 200,
        }

        # Test Notion workspace connection
        notion_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/notion/connection", timeout=10
        )
        test_details["details"]["notion_connection"] = {
            "status_code": notion_connection_response.status_code,
            "connected": notion_connection_response.status_code == 200,
            "workspace_info": notion_connection_response.json()
            if notion_connection_response.status_code == 200
            else None,
        }

        # Test Notion databases listing
        if notion_connection_response.status_code == 200:
            databases_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/notion/databases", timeout=10
            )
            test_details["details"]["notion_databases"] = {
                "status_code": databases_response.status_code,
                "databases_count": len(databases_response.json().get("databases", []))
                if databases_response.status_code == 200
                else 0,
            }

        # Test Notion pages listing
        if notion_connection_response.status_code == 200:
            pages_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/notion/pages", timeout=10
            )
            test_details["details"]["notion_pages"] = {
                "status_code": pages_response.status_code,
                "pages_count": len(pages_response.json().get("pages", []))
                if pages_response.status_code == 200
                else 0,
            }

        # Test Notion page creation
        if test_details["details"].get("notion_databases", {}).get("databases_count", 0) > 0:
            test_page = {
                "title": f"Test Page from Atom E2E - {time.time()}",
                "content": "This is a test page created by Atom E2E test suite",
                "database_id": "default",
                "test_mode": True
            }

            create_page_response = requests.post(
                f"{config.BACKEND_URL}/api/v1/notion/pages",
                json=test_page,
                timeout=15
            )

            test_details["details"]["notion_page_creation"] = {
                "status_code": create_page_response.status_code,
                "page_created": create_page_response.status_code in [200, 201],
                "page_id": create_page_response.json().get("page_id")
                if create_page_response.status_code in [200, 201]
                else None,
            }

        # Determine test status
        if (
            test_details["details"]["notion_endpoints"]["available"]
            and test_details["details"]["notion_connection"]["connected"]
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


def _test_linear_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Linear integration capabilities"""
    test_name = "linear_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Linear workspace connectivity and issue management",
        "status": "failed",
        "details": {},
    }

    try:
        # Test Linear endpoints availability
        linear_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/linear", timeout=10
        )
        test_details["details"]["linear_endpoints"] = {
            "status_code": linear_endpoints_response.status_code,
            "available": linear_endpoints_response.status_code == 200,
        }

        # Test Linear workspace connection
        linear_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/linear/connection", timeout=10
        )
        test_details["details"]["linear_connection"] = {
            "status_code": linear_connection_response.status_code,
            "connected": linear_connection_response.status_code == 200,
            "workspace_info": linear_connection_response.json()
            if linear_connection_response.status_code == 200
            else None,
        }

        # Test Linear teams listing
        if linear_connection_response.status_code == 200:
            teams_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/linear/teams", timeout=10
            )
            test_details["details"]["linear_teams"] = {
                "status_code": teams_response.status_code,
                "teams_count": len(teams_response.json().get("teams", []))
                if teams_response.status_code == 200
                else 0,
            }

        # Test Linear issues listing
        if linear_connection_response.status_code == 200:
            issues_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/linear/issues", timeout=10
            )
            test_details["details"]["linear_issues"] = {
                "status_code": issues_response.status_code,
                "issues_count": len(issues_response.json().get("issues", []))
                if issues_response.status_code == 200
                else 0,
            }

        # Test Linear issue creation
        if test_details["details"].get("linear_teams", {}).get("teams_count", 0) > 0:
            test_issue = {
                "title": f"Test Issue from Atom E2E - {time.time()}",
                "description": "This is a test issue created by Atom E2E test suite",
                "team_id": "default",
                "test_mode": True
            }

            create_issue_response = requests.post(
                f"{config.BACKEND_URL}/api/v1/linear/issues",
                json=test_issue,
                timeout=15
            )

            test_details["details"]["linear_issue_creation"] = {
                "status_code": create_issue_response.status_code,
                "issue_created": create_issue_response.status_code in [200, 201],
                "issue_id": create_issue_response.json().get("issue_id")
                if create_issue_response.status_code in [200, 201]
                else None,
            }

        # Determine test status
        if (
            test_details["details"]["linear_endpoints"]["available"]
            and test_details["details"]["linear_connection"]["connected"]
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


def _test_trello_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Trello integration capabilities"""
    test_name = "trello_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Trello board connectivity and card management",
        "status": "failed",
        "details": {},
    }

    try:
        # Test Trello endpoints availability
        trello_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/trello", timeout=10
        )
        test_details["details"]["trello_endpoints"] = {
            "status_code": trello_endpoints_response.status_code,
            "available": trello_endpoints_response.status_code == 200,
        }

        # Test Trello connection
        trello_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/trello/connection", timeout=10
        )
        test_details["details"]["trello_connection"] = {
            "status_code": trello_connection_response.status_code,
            "connected": trello_connection_response.status_code == 200,
            "user_info": trello_connection_response.json()
            if trello_connection_response.status_code == 200
            else None,
        }

        # Test Trello boards listing
        if trello_connection_response.status_code == 200:
            boards_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/trello/boards", timeout=10
            )
            test_details["details"]["trello_boards"] = {
                "status_code": boards_response.status_code,
                "boards_count": len(boards_response.json().get("boards", []))
                if boards_response.status_code == 200
                else 0,
            }

        # Test Trello cards listing
        if trello_connection_response.status_code == 200:
            cards_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/trello/cards", timeout=10
            )
            test_details["details"]["trello_cards"] = {
                "status_code": cards_response.status_code,
                "cards_count": len(cards_response.json().get("cards", []))
                if cards_response.status_code == 200
                else 0,
            }

        # Test Trello card creation
        if test_details["details"].get("trello_boards", {}).get("boards_count", 0) > 0:
            test_card = {
                "name": f"Test Card from Atom E2E - {time.time()}",
                "desc": "This is a test card created by Atom E2E test suite",
                "board_id": "default",
                "list_id": "todo",
                "test_mode": True
            }

            create_card_response = requests.post(
                f"{config.BACKEND_URL}/api/v1/trello/cards",
                json=test_card,
                timeout=15
            )

            test_details["details"]["trello_card_creation"] = {
                "status_code": create_card_response.status_code,
                "card_created": create_card_response.status_code in [200, 201],
                "card_id": create_card_response.json().get("card_id")
                if create_card_response.status_code in [200, 201]
                else None,
            }

        # Determine test status
        if (
            test_details["details"]["trello_endpoints"]["available"]
            and test_details["details"]["trello_connection"]["connected"]
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


def _test_monday_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Monday.com integration capabilities"""
    test_name = "monday_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Monday.com workspace connectivity and item management",
        "status": "failed",
        "details": {},
    }

    try:
        # Test Monday endpoints availability
        monday_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/monday", timeout=10
        )
        test_details["details"]["monday_endpoints"] = {
            "status_code": monday_endpoints_response.status_code,
            "available": monday_endpoints_response.status_code == 200,
        }

        # Test Monday workspace connection
        monday_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/monday/connection", timeout=10
        )
        test_details["details"]["monday_connection"] = {
            "status_code": monday_connection_response.status_code,
            "connected": monday_connection_response.status_code == 200,
            "workspace_info": monday_connection_response.json()
            if monday_connection_response.status_code == 200
            else None,
        }

        # Test Monday boards listing
        if monday_connection_response.status_code == 200:
            boards_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/monday/boards", timeout=10
            )
            test_details["details"]["monday_boards"] = {
