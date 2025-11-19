"""
Communication E2E Tests for Atom Platform
Tests Email, Slack, Zoom, and WhatsApp integrations
"""

import json
import time
from typing import Any, Dict

import requests

from config.test_config import TestConfig


def run_tests(config: TestConfig) -> Dict[str, Any]:
    """
    Run communication E2E tests
    
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

    # Test 1: Email integration (Gmail/Outlook)
    email_results = _test_email_integration(config)
    results["tests_run"] += email_results["tests_run"]
    results["tests_passed"] += email_results["tests_passed"]
    results["tests_failed"] += email_results["tests_failed"]
    results["test_details"].update(email_results["test_details"])

    # Test 2: Slack integration
    slack_results = _test_slack_integration(config)
    results["tests_run"] += slack_results["tests_run"]
    results["tests_passed"] += slack_results["tests_passed"]
    results["tests_failed"] += slack_results["tests_failed"]
    results["test_details"].update(slack_results["test_details"])

    # Test 3: Zoom integration
    zoom_results = _test_zoom_integration(config)
    results["tests_run"] += zoom_results["tests_run"]
    results["tests_passed"] += zoom_results["tests_passed"]
    results["tests_failed"] += zoom_results["tests_failed"]
    results["test_details"].update(zoom_results["test_details"])

    # Test 4: WhatsApp integration
    whatsapp_results = _test_whatsapp_integration(config)
    results["tests_run"] += whatsapp_results["tests_run"]
    results["tests_passed"] += whatsapp_results["tests_passed"]
    results["tests_failed"] += whatsapp_results["tests_failed"]
    results["test_details"].update(whatsapp_results["test_details"])

    results["end_time"] = time.time()
    results["duration_seconds"] = results["end_time"] - results["start_time"]

    return results


def _test_email_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Email integration (Gmail/Outlook)"""
    test_name = "email_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Email integration for sending and receiving messages",
        "status": "failed",
        "details": {},
    }

    try:
        # Test email health endpoint
        base_url = config.BACKEND_URL
        
        health_response = requests.get(
            f"{base_url}/api/email/health", timeout=10
        )
        test_details["details"]["email_health"] = {
            "status_code": health_response.status_code,
            "available": health_response.status_code == 200,
            "response": health_response.json()
            if health_response.status_code == 200
            else None,
        }

        # Test send email capability
        send_email_payload = {
            "to": "test@example.com",
            "subject": "E2E Test Email",
            "body": "This is a test email sent via Atom platform E2E testing",
            "provider": "gmail"  # or "outlook"
        }

        send_response = requests.post(
            f"{base_url}/api/email/send",
            json=send_email_payload,
            timeout=15,
        )

        test_details["details"]["email_send"] = {
            "status_code": send_response.status_code,
            "sent_successfully": send_response.status_code in [200, 201],
            "response": send_response.json()
            if send_response.status_code in [200, 201]
            else None,
        }

        #Test list emails
        list_response = requests.get(
            f"{base_url}/api/email/messages?limit=5", timeout=10
        )
        
        test_details["details"]["email_list"] = {
            "status_code": list_response.status_code,
            "messages_count": len(list_response.json().get("messages", []))
            if list_response.status_code == 200
            else 0,
        }

        # Determine test status
        if (
            test_details["details"]["email_health"]["available"]
            and test_details["details"]["email_send"]["status_code"] in [200, 201]
        ):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
    }


def _test_slack_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Slack integration"""
    test_name = "slack_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Slack integration for messaging and notifications",
        "status": "failed",
        "details": {},
    }

    try:
        base_url = config.BACKEND_URL

        # Test Slack health endpoint
        health_response = requests.get(
            f"{base_url}/api/slack/health", timeout=10
        )
        test_details["details"]["slack_health"] = {
            "status_code": health_response.status_code,
            "available": health_response.status_code == 200,
            "response": health_response.json()
            if health_response.status_code == 200
            else None,
        }

        # Test send message
        send_message_payload = {
            "channel": "#general",
            "text": "E2E Test: Atom platform integration test",
            "username": "Atom Bot"
        }

        send_response = requests.post(
            f"{base_url}/api/slack/messages",
            json=send_message_payload,
            timeout=15,
        )

        test_details["details"]["slack_send_message"] = {
            "status_code": send_response.status_code,
            "sent_successfully": send_response.status_code in [200, 201],
            "response": send_response.json()
            if send_response.status_code in [200, 201]
            else None,
        }

        # Test list channels
        channels_response = requests.get(
            f"{base_url}/api/slack/channels", timeout=10
        )

        test_details["details"]["slack_channels"] = {
            "status_code": channels_response.status_code,
            "channels_count": len(channels_response.json().get("channels", []))
            if channels_response.status_code == 200
            else 0,
        }

        # Determine test status
        if (
            test_details["details"]["slack_health"]["available"]
            and test_details["details"]["slack_send_message"]["status_code"] in [200, 201]
        ):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
    }


def _test_zoom_integration(config: TestConfig) -> Dict[str, Any]:
    """Test Zoom integration"""
    test_name = "zoom_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test Zoom integration for meetings and webinars",
        "status": "failed",
        "details": {},
    }

    try:
        base_url = config.BACKEND_URL

        # Test Zoom health endpoint
        health_response = requests.get(
            f"{base_url}/api/zoom/health", timeout=10
        )
        test_details["details"]["zoom_health"] = {
            "status_code": health_response.status_code,
            "available": health_response.status_code == 200,
            "response": health_response.json()
            if health_response.status_code == 200
            else None,
        }

        # Test create meeting
        create_meeting_payload = {
            "topic": "E2E Test Meeting",
            "type": 2,  # Scheduled meeting
            "start_time": "2025-12-01T10:00:00Z",
            "duration": 30,
            "settings": {
                "auto_recording": "none",
                "join_before_host": True
            }
        }

        create_response = requests.post(
            f"{base_url}/api/zoom/meetings",
            json=create_meeting_payload,
            timeout=15,
        )

        test_details["details"]["zoom_create_meeting"] = {
            "status_code": create_response.status_code,
            "meeting_created": create_response.status_code in [200, 201],
            "response": create_response.json()
            if create_response.status_code in [200, 201]
            else None,
        }

        # Test list meetings
        meetings_response = requests.get(
            f"{base_url}/api/zoom/meetings", timeout=10
        )

        test_details["details"]["zoom_meetings"] = {
            "status_code": meetings_response.status_code,
            "meetings_count": len(meetings_response.json().get("meetings", []))
            if meetings_response.status_code == 200
            else 0,
        }

        # Determine test status
        if (
            test_details["details"]["zoom_health"]["available"]
            and test_details["details"]["zoom_create_meeting"]["status_code"] in [200, 201]
        ):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
    }


def _test_whatsapp_integration(config: TestConfig) -> Dict[str, Any]:
    """Test WhatsApp Business integration"""
    test_name = "whatsapp_integration"
    test_details = {
        "test_name": test_name,
        "description": "Test WhatsApp Business integration for messaging",
        "status": "failed",
        "details": {},
    }

    try:
        base_url = config.BACKEND_URL

        # Test WhatsApp health endpoint
        health_response = requests.get(
            f"{base_url}/api/whatsapp/health", timeout=10
        )
        test_details["details"]["whatsapp_health"] = {
            "status_code": health_response.status_code,
            "available": health_response.status_code == 200,
            "response": health_response.json()
            if health_response.status_code == 200
            else None,
        }

        # Test send message
        send_message_payload = {
            "to": "+1234567890",
            "message": "E2E Test: Atom platform WhatsApp integration",
            "type": "text"
        }

        send_response = requests.post(
            f"{base_url}/api/whatsapp/messages",
            json=send_message_payload,
            timeout=15,
        )

        test_details["details"]["whatsapp_send_message"] = {
            "status_code": send_response.status_code,
            "sent_successfully": send_response.status_code in [200, 201],
            "response": send_response.json()
            if send_response.status_code in [200, 201]
            else None,
        }

        # Test get messages
        messages_response = requests.get(
            f"{base_url}/api/whatsapp/messages?limit=10", timeout=10
        )

        test_details["details"]["whatsapp_messages"] = {
            "status_code": messages_response.status_code,
            "messages_count": len(messages_response.json().get("messages", []))
            if messages_response.status_code == 200
            else 0,
        }

        # Determine test status
        if (
            test_details["details"]["whatsapp_health"]["available"]
            and test_details["details"]["whatsapp_send_message"]["status_code"] in [200, 201]
        ):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
    }
