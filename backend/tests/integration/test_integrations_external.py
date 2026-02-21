"""
Integration tests for external service integrations using HTTP-level mocking.

Tests external API calls using respx to mock HTTP responses, testing real
integration code without actual external dependencies (Slack, Discord, etc.).
"""

import pytest
import httpx
import respx


# ============================================================================
# Slack Integration Tests (using respx)
# ============================================================================

@pytest.mark.integration
@respx.mock
async def test_slack_send_message_success():
    """Test Slack message sending with HTTP mock."""
    # Mock Slack API at HTTP level
    respx.post(
        "https://slack.com/api/chat.postMessage"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "channel": "C12345",
                "ts": "1234567890.123456",
                "message": {
                    "text": "Test message",
                    "username": "bot"
                }
            }
        )
    )

    from integrations.slack_enhanced_service import SlackEnhancedService

    # Create service with test token
    service = SlackEnhancedService(
        bot_token="xoxb-test-token",
        team_id="T12345"
    )

    # Send message
    result = await service.send_message(
        channel="C12345",
        text="Test message"
    )

    assert result["success"] == True
    assert result["message_ts"] == "1234567890.123456"


@pytest.mark.integration
@respx.mock
@pytest.mark.parametrize("status_code,error_msg,expected_success", [
    (400, "invalid_arguments", False),
    (401, "invalid_auth", False),
    (403, "account_inactive", False),
    (429, "rate_limited", False),
    (500, "internal_error", False),
    (200, None, True),
])
async def test_slack_http_status_codes(status_code, error_msg, expected_success):
    """Parametrized test for various HTTP status codes."""
    response_json = {"ok": status_code == 200}
    if error_msg:
        response_json["error"] = error_msg

    respx.post(
        "https://slack.com/api/chat.postMessage"
    ).mock(
        return_value=httpx.Response(status_code, json=response_json)
    )

    from integrations.slack_enhanced_service import SlackEnhancedService

    service = SlackEnhancedService(
        bot_token="xoxb-test-token",
        team_id="T12345"
    )

    result = await service.send_message(
        channel="C12345",
        text="Test"
    )

    assert result["success"] == expected_success


@pytest.mark.integration
@respx.mock
async def test_slack_rate_limiting():
    """Test Slack rate limiting handling."""
    # Mock rate limit response
    respx.post(
        "https://slack.com/api/chat.postMessage"
    ).mock(
        return_value=httpx.Response(
            429,
            json={
                "ok": False,
                "error": "rate_limited"
            },
            headers={
                "Retry-After": "30"
            }
        )
    )

    from integrations.slack_enhanced_service import SlackEnhancedService

    service = SlackEnhancedService(
        bot_token="xoxb-test-token",
        team_id="T12345"
    )

    result = await service.send_message(
        channel="C12345",
        text="Test"
    )

    assert result["success"] == False
    assert "rate_limited" in result.get("error", "")


@pytest.mark.integration
@respx.mock
async def test_slack_error_handling():
    """Test Slack API error handling."""
    respx.post(
        "https://slack.com/api/chat.postMessage"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": False,
                "error": "channel_not_found"
            }
        )
    )

    from integrations.slack_enhanced_service import SlackEnhancedService

    service = SlackEnhancedService(
        bot_token="xoxb-test-token",
        team_id="T12345"
    )

    result = await service.send_message(
        channel="invalid-channel",
        text="Test"
    )

    assert result["success"] == False
    assert "channel_not_found" in result.get("error", "")


@pytest.mark.integration
@respx.mock
async def test_slack_update_message():
    """Test Slack message update."""
    respx.post(
        "https://slack.com/api/chat.update"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "channel": "C12345",
                "ts": "1234567890.123456",
                "text": "Updated message"
            }
        )
    )

    from integrations.slack_enhanced_service import SlackEnhancedService

    service = SlackEnhancedService(
        bot_token="xoxb-test-token",
        team_id="T12345"
    )

    result = await service.update_message(
        channel="C12345",
        ts="1234567890.123456",
        text="Updated message"
    )

    assert result["success"] == True


@pytest.mark.integration
@respx.mock
async def test_slack_delete_message():
    """Test Slack message deletion."""
    respx.post(
        "https://slack.com/api/chat.delete"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True
            }
        )
    )

    from integrations.slack_enhanced_service import SlackEnhancedService

    service = SlackEnhancedService(
        bot_token="xoxb-test-token",
        team_id="T12345"
    )

    result = await service.delete_message(
        channel="C12345",
        ts="1234567890.123456"
    )

    assert result["success"] == True


# ============================================================================
# Generic HTTP Client Tests
# ============================================================================

@pytest.mark.integration
@respx.mock
async def test_http_client_post_request():
    """Test generic HTTP POST request."""
    respx.post(
        "https://api.example.com/v1/messages"
    ).mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "msg-123",
                "status": "sent",
                "created_at": "2026-02-21T12:00:00Z"
            }
        )
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.example.com/v1/messages",
            json={"text": "Hello"},
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "msg-123"
        assert data["status"] == "sent"


@pytest.mark.integration
@respx.mock
async def test_http_client_get_request():
    """Test generic HTTP GET request."""
    respx.get(
        "https://api.example.com/v1/messages/msg-123"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "msg-123",
                "text": "Hello",
                "created_at": "2026-02-21T12:00:00Z"
            }
        )
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.example.com/v1/messages/msg-123",
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "msg-123"


@pytest.mark.integration
@respx.mock
async def test_http_client_json_parsing_error():
    """Test HTTP client handles invalid JSON."""
    respx.get(
        "https://api.example.com/v1/bad-json"
    ).mock(
        return_value=httpx.Response(
            200,
            content=b"invalid json {"
        )
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.DecodingError):
            response = await client.get("https://api.example.com/v1/bad-json")
            response.json()


# ============================================================================
# API Contract Validation Tests
# ============================================================================

@pytest.mark.integration
@respx.mock
async def test_slack_api_contract_validation():
    """Test that integration validates Slack API contract."""
    respx.post(
        "https://slack.com/api/chat.postMessage"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "channel": "C12345",
                "ts": "1234567890.123456",
                "message": {
                    "bot_id": "B12345",
                    "type": "message",
                    "text": "Test",
                    "user": "U12345",
                    "ts": "1234567890.123456"
                }
            }
        )
    )

    from integrations.slack_enhanced_service import SlackEnhancedService

    service = SlackEnhancedService(
        bot_token="xoxb-test-token",
        team_id="T12345"
    )

    result = await service.send_message(
        channel="C12345",
        text="Test"
    )

    # Verify API contract compliance
    assert result["success"] == True
    assert "message_ts" in result
    assert len(result["message_ts"].split(".")) == 2  # timestamp.microseconds format


@pytest.mark.integration
@respx.mock
async def test_slack_invalid_token():
    """Test Slack rejects invalid token."""
    respx.post(
        "https://slack.com/api/chat.postMessage"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": False,
                "error": "invalid_auth"
            }
        )
    )

    from integrations.slack_enhanced_service import SlackEnhancedService

    service = SlackEnhancedService(
        bot_token="xoxb-invalid-token",
        team_id="T12345"
    )

    result = await service.send_message(
        channel="C12345",
        text="Test"
    )

    assert result["success"] == False
    assert "invalid_auth" in result.get("error", "")
