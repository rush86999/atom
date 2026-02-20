"""
API request/response test fixtures.

Provides factory functions for creating test API data with minimal boilerplate.
"""

from typing import Any, Dict, Optional
from datetime import datetime
from fastapi.testclient import TestClient


def create_chat_request(
    message: str = "Test message",
    agent_id: str = "test_agent",
    **kwargs
) -> Dict[str, Any]:
    """Factory function to create chat API request payloads.

    Args:
        message: Chat message content
        agent_id: Agent ID to send message to
        **kwargs: Additional request fields

    Returns:
        Chat request dictionary

    Example:
        request = create_chat_request(message="Hello", agent_id="agent_123")
    """
    return {
        "message": message,
        "agent_id": agent_id,
        "conversation_id": kwargs.get("conversation_id"),
        "stream": kwargs.get("stream", False),
        "parameters": kwargs.get("parameters", {}),
        **{k: v for k, v in kwargs.items() if k not in [
            "conversation_id", "stream", "parameters"
        ]}
    }


def create_canvas_request(
    canvas_type: str = "generic",
    title: str = "Test Canvas",
    **kwargs
) -> Dict[str, Any]:
    """Factory function to create canvas API request payloads.

    Args:
        canvas_type: Canvas type (generic, docs, email, sheets, etc.)
        title: Canvas title
        **kwargs: Additional request fields

    Returns:
        Canvas request dictionary
    """
    return {
        "canvas_type": canvas_type,
        "title": title,
        "data": kwargs.get("data", {}),
        "agent_id": kwargs.get("agent_id", "test_agent"),
        **{k: v for k, v in kwargs.items() if k not in ["data", "agent_id"]}
    }


def create_workflow_request(
    workflow_id: str = "test_workflow",
    input_data: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Factory function to create workflow execution request payloads.

    Args:
        workflow_id: Workflow ID to execute
        input_data: Input data for workflow
        **kwargs: Additional request fields

    Returns:
        Workflow request dictionary
    """
    return {
        "workflow_id": workflow_id,
        "input_data": input_data or {},
        "agent_id": kwargs.get("agent_id", "test_agent"),
        "async_execution": kwargs.get("async_execution", False),
        **{k: v for k, v in kwargs.items() if k not in [
            "agent_id", "async_execution"
        ]}
    }


def create_agent_response(
    response: str = "Test response",
    agent_id: str = "test_agent",
    success: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """Factory function to create agent API response objects.

    Args:
        response: Response text
        agent_id: Agent ID
        success: Whether the request was successful
        **kwargs: Additional response fields

    Returns:
        Agent response dictionary
    """
    data = {
        "success": success,
        "response": response,
        "agent_id": agent_id,
        "timestamp": kwargs.get("timestamp", datetime.utcnow().isoformat()),
    }

    if not success:
        data["error"] = kwargs.get("error", "Test error")

    data.update({k: v for k, v in kwargs.items() if k not in [
        "error", "timestamp"
    ]})

    return data


def create_canvas_response(
    canvas_id: str = "test_canvas",
    canvas_type: str = "generic",
    success: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """Factory function to create canvas API response objects.

    Args:
        canvas_id: Canvas ID
        canvas_type: Canvas type
        success: Whether the request was successful
        **kwargs: Additional response fields

    Returns:
        Canvas response dictionary
    """
    data = {
        "success": success,
        "canvas_id": canvas_id,
        "canvas_type": canvas_type,
        "timestamp": kwargs.get("timestamp", datetime.utcnow().isoformat()),
    }

    if success:
        data["url"] = kwargs.get("url", f"/canvas/{canvas_id}")
    else:
        data["error"] = kwargs.get("error", "Test error")

    data.update({k: v for k, v in kwargs.items() if k not in [
        "url", "error", "timestamp"
    ]})

    return data


def create_error_response(
    error_code: str = "TEST_ERROR",
    message: str = "Test error message",
    status_code: int = 400,
    **kwargs
) -> Dict[str, Any]:
    """Factory function to create API error responses.

    Args:
        error_code: Error code
        message: Error message
        status_code: HTTP status code
        **kwargs: Additional error fields

    Returns:
        Error response dictionary
    """
    return {
        "success": False,
        "error_code": error_code,
        "message": message,
        "status_code": status_code,
        "timestamp": kwargs.get("timestamp", datetime.utcnow().isoformat()),
        "details": kwargs.get("details", {}),
        **{k: v for k, v in kwargs.items() if k not in ["timestamp", "details"]}
    }


class MockTestClient:
    """Mock TestClient for testing without actual FastAPI app.

    Provides simple request/response simulation for unit tests.
    """

    def __init__(self):
        self.responses = {}
        self.requests = []

    def set_response(self, method: str, path: str, response: Any):
        """Set a mock response for a specific endpoint."""
        key = f"{method.upper()}:{path}"
        self.responses[key] = response

    def request(self, method: str, path: str, **kwargs):
        """Simulate an HTTP request."""
        self.requests.append({
            "method": method.upper(),
            "path": path,
            "kwargs": kwargs
        })
        key = f"{method.upper()}:{path}"
        return self.responses.get(key, {"success": False, "error": "Not found"})

    def get(self, path: str, **kwargs):
        """Simulate GET request."""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        """Simulate POST request."""
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs):
        """Simulate PUT request."""
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs):
        """Simulate DELETE request."""
        return self.request("DELETE", path, **kwargs)

    def clear(self):
        """Clear request history."""
        self.requests = []
