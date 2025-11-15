"""
Communication Services E2E Tests for Atom Platform
Tests Slack, Discord, Gmail, Outlook, and Teams integrations
"""

import json
import time
from typing import Any, Dict, List, Optional

import requests

from config.test_config import TestConfig


def run_tests(config: TestConfig) -> Dict[str, Any]:
    """
    Run communication services E2E tests

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

    # Test 1: Slack integration
    results.update(_test_slack_integration(config))

    # Test 2: Discord integration
    results.update(_test_discord_integration(config))

    # Test 3: Email integration (Gmail/Outlook)
    results.update(_test_email_integration(config))

    # Test 4: Teams integration
    results.update(_test_teams_integration(config))

    # Test 5: Cross-platform messaging coordination
    results.update(_test_cross_platform_messaging(config))

    results["end_time"] = time.time()
    results["duration_seconds"] = results["end_time"] - results["start_time"]

    return results


def _test_slack_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Slack integration capabilities"""
    test_name = "slack_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Slack workspace connectivity and messaging",
        "status": "failed",
        "details": {},
    }

    try:
        # Test Slack endpoints availability
        slack_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/slack", timeout=10
        )
        test_details["details"]["slack_endpoints"] = {
            "status_code": slack_endpoints_response.status_code,
            "available": slack_endpoints_response.status_code == 200,
        }

        # Test Slack workspace connection
        slack_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/slack/connection", timeout=10
        )
        test_details["details"]["slack_connection"] = {
            "status_code": slack_connection_response.status_code,
            "connected": slack_connection_response.status_code == 200,
            "workspace_info": slack_connection_response.json()
            if slack_connection_response.status_code == 200
            else None,
        }

        # Test Slack channel listing
        if slack_connection_response.status_code == 200:
            channels_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/slack/channels", timeout=10
            )
            test_details["details"]["slack_channels"] = {
                "status_code": channels_response.status_code,
                "channels_count": len(channels_response.json().get("channels", []))
                if channels_response.status_code == 200
                else 0,
            }

        # Test Slack message sending (if channels available)
        if test_details["details"].get("slack_channels", {}).get("channels_count", 0) > 0:
            test_message = {
                "channel": "general",
                "message": f"Test message from Atom E2E tests at {time.time()}",
                "test_mode": True  # Flag to indicate this is a test message
            }

            send_message_response = requests.post(
                f"{config.BACKEND_URL}/api/v1/slack/message",
                json=test_message,
                timeout=15
            )

            test_details["details"]["slack_message_sending"] = {
                "status_code": send_message_response.status_code,
                "message_sent": send_message_response.status_code in [200, 201],
                "response": send_message_response.json()
                if send_message_response.status_code in [200, 201]
                else None,
            }

        # Determine test status
        if (
            test_details["details"]["slack_endpoints"]["available"]
            and test_details["details"]["slack_connection"]["connected"]
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


def _test_discord_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Discord integration capabilities"""
    test_name = "discord_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Discord server connectivity and messaging",
        "status": "failed",
        "details": {},
    }

    try:
        # Test Discord endpoints availability
        discord_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/discord", timeout=10
        )
        test_details["details"]["discord_endpoints"] = {
            "status_code": discord_endpoints_response.status_code,
            "available": discord_endpoints_response.status_code == 200,
        }

        # Test Discord server connection
        discord_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/discord/connection", timeout=10
        )
        test_details["details"]["discord_connection"] = {
            "status_code": discord_connection_response.status_code,
            "connected": discord_connection_response.status_code == 200,
            "server_info": discord_connection_response.json()
            if discord_connection_response.status_code == 200
            else None,
        }

        # Test Discord channel listing
        if discord_connection_response.status_code == 200:
            channels_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/discord/channels", timeout=10
            )
            test_details["details"]["discord_channels"] = {
                "status_code": channels_response.status_code,
                "channels_count": len(channels_response.json().get("channels", []))
                if channels_response.status_code == 200
                else 0,
            }

        # Test Discord message sending
        if test_details["details"].get("discord_channels", {}).get("channels_count", 0) > 0:
            test_message = {
                "channel_id": "general",
                "message": f"Test message from Atom E2E tests at {time.time()}",
                "test_mode": True
            }

            send_message_response = requests.post(
                f"{config.BACKEND_URL}/api/v1/discord/message",
                json=test_message,
                timeout=15
            )

            test_details["details"]["discord_message_sending"] = {
                "status_code": send_message_response.status_code,
                "message_sent": send_message_response.status_code in [200, 201],
            }

        # Determine test status
        if (
            test_details["details"]["discord_endpoints"]["available"]
            and test_details["details"]["discord_connection"]["connected"]
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


def _test_email_integration(config: TestConfig) -> Dict[str, Any]:
    """Test email integration capabilities (Gmail/Outlook)"""
    test_name = "email_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Gmail and Outlook email connectivity",
        "status": "failed",
        "details": {},
    }

    try:
        # Test email endpoints availability
        email_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/email", timeout=10
        )
        test_details["details"]["email_endpoints"] = {
            "status_code": email_endpoints_response.status_code,
            "available": email_endpoints_response.status_code == 200,
        }

        # Test Gmail connection
        gmail_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/gmail/connection", timeout=10
        )
        test_details["details"]["gmail_connection"] = {
            "status_code": gmail_connection_response.status_code,
            "connected": gmail_connection_response.status_code == 200,
        }

        # Test Outlook connection
        outlook_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/outlook/connection", timeout=10
        )
        test_details["details"]["outlook_connection"] = {
            "status_code": outlook_connection_response.status_code,
            "connected": outlook_connection_response.status_code == 200,
        }

        # Test email inbox access
        inbox_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/email/inbox", timeout=15
        )
        test_details["details"]["email_inbox"] = {
            "status_code": inbox_response.status_code,
            "emails_count": len(inbox_response.json().get("emails", []))
            if inbox_response.status_code == 200
            else 0,
            "accessible": inbox_response.status_code == 200,
        }

        # Test email sending capability
        test_email = {
            "to": "test@example.com",
            "subject": f"Test email from Atom E2E tests - {time.time()}",
            "body": "This is a test email from the Atom platform E2E test suite.",
            "test_mode": True
        }

        send_email_response = requests.post(
            f"{config.BACKEND_URL}/api/v1/email/send",
            json=test_email,
            timeout=15
        )

        test_details["details"]["email_sending"] = {
            "status_code": send_email_response.status_code,
            "email_sent": send_email_response.status_code in [200, 201],
        }

        # Determine test status - require at least one email service to be connected
        if (
            test_details["details"]["email_endpoints"]["available"]
            and (
                test_details["details"]["gmail_connection"]["connected"]
                or test_details["details"]["outlook_connection"]["connected"]
            )
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


def _test_teams_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Microsoft Teams integration capabilities"""
    test_name = "teams_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Microsoft Teams connectivity and messaging",
        "status": "failed",
        "details": {},
    }

    try:
        # Test Teams endpoints availability
        teams_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/teams", timeout=10
        )
        test_details["details"]["teams_endpoints"] = {
            "status_code": teams_endpoints_response.status_code,
            "available": teams_endpoints_response.status_code == 200,
        }

        # Test Teams connection
        teams_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/teams/connection", timeout=10
        )
        test_details["details"]["teams_connection"] = {
            "status_code": teams_connection_response.status_code,
            "connected": teams_connection_response.status_code == 200,
            "tenant_info": teams_connection_response.json()
            if teams_connection_response.status_code == 200
            else None,
        }

        # Test Teams channels listing
        if teams_connection_response.status_code == 200:
            channels_response = requests.get(
                f"{config.BACKEND_URL}/api/v1/teams/channels", timeout=10
            )
            test_details["details"]["teams_channels"] = {
                "status_code": channels_response.status_code,
                "channels_count": len(channels_response.json().get("channels", []))
                if channels_response.status_code == 200
                else 0,
            }

        # Test Teams message sending
        if test_details["details"].get("teams_channels", {}).get("channels_count", 0) > 0:
            test_message = {
                "team_id": "test_team",
                "channel_id": "general",
                "message": f"Test message from Atom E2E tests at {time.time()}",
                "test_mode": True
            }

            send_message_response = requests.post(
                f"{config.BACKEND_URL}/api/v1/teams/message",
                json=test_message,
                timeout=15
            )

            test_details["details"]["teams_message_sending"] = {
                "status_code": send_message_response.status_code,
                "message_sent": send_message_response.status_code in [200, 201],
            }

        # Determine test status
        if (
            test_details["details"]["teams_endpoints"]["available"]
            and test_details["details"]["teams_connection"]["connected"]
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


def _test_cross_platform_messaging(config: TestConfig) -> Dict[str, Any]:
    """Test cross-platform messaging coordination"""
    test_name = "cross_platform_messaging"
    test_details = {
        "test_name": test_name,
        "description": "Test unified messaging across multiple platforms",
        "status": "failed",
        "details": {},
    }

    try:
        # Test unified messaging endpoints
        unified_messaging_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/messaging", timeout=10
        )
        test_details["details"]["unified_messaging"] = {
            "status_code": unified_messaging_response.status_code,
            "available": unified_messaging_response.status_code == 200,
        }

        # Test cross-platform message broadcasting
        broadcast_message = {
            "message": f"Cross-platform test message from Atom E2E tests - {time.time()}",
            "platforms": ["slack", "discord", "teams"],
            "test_mode": True
        }

        broadcast_response = requests.post(
            f"{config.BACKEND_URL}/api/v1/messaging/broadcast",
            json=broadcast_message,
            timeout=20
        )

        test_details["details"]["cross_platform_broadcast"] = {
            "status_code": broadcast_response.status_code,
            "broadcast_sent": broadcast_response.status_code in [200, 201],
            "platform_responses": broadcast_response.json().get("platform_responses", {})
            if broadcast_response.status_code in [200, 201]
            else {},
        }

        # Test message aggregation (inbox unification)
        unified_inbox_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/messaging/inbox", timeout=15
        )
        test_details["details"]["unified_inbox"] = {
            "status_code": unified_inbox_response.status_code,
            "messages_count": len(unified_inbox_response.json().get("messages", []))
            if unified_inbox_response.status_code == 200
            else 0,
            "platforms_aggregated": unified_inbox_response.json().get("platforms", [])
            if unified_inbox_response.status_code == 200
            else [],
        }

        # Test smart notifications
        notifications_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/messaging/notifications", timeout=10
        )
        test_details["details"]["smart_notifications"] = {
            "status_code": notifications_response.status_code,
            "notifications_count": len(notifications_response.json().get("notifications", []))
            if notifications_response.status_code == 200
            else 0,
        }

        # Determine test status
        if (
            test_details["details"]["unified_messaging"]["available"]
            and test_details["details"].get("cross_platform_broadcast", {}).get("broadcast_sent", False)
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
def test_slack_integration(config: TestConfig) -> Dict[str, Any]:
    """Run only Slack integration test"""
    return _test_slack_integration(config)


def test_discord_integration(config: TestConfig) -> Dict[str, Any]:
    """Run only Discord integration test"""
    return _test_discord_integration(config)


def test_email_integration(config: TestConfig) -> Dict[str, Any]:
    """Run only email integration test"""
    return _test_email_integration(config)


def test_teams_integration(config: TestConfig) -> Dict[str, Any]:
    """Run only Teams integration test"""
    return _test_teams_integration(config)


def test
