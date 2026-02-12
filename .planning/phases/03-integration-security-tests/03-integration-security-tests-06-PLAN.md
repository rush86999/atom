# External Service Mocking and Multi-Agent Coordination Tests

**Phase**: 03 - Integration & Security Tests
**Plan**: 06 - External Service Mocking and Multi-Agent Coordination
**Status**: Pending
**Priority**: P1 (High)

## Objective

Build comprehensive integration tests for external service integration (API calls, webhooks, third-party services) with proper mocking, and test multi-agent coordination scenarios.

## Success Criteria

1. External API calls are tested with mocking
2. Webhook handling is tested
3. Third-party service integration is tested (LLM providers, databases, external APIs)
4. Multi-agent coordination is tested (agent-to-agent communication, shared state)
5. Service failures are tested (timeouts, errors, retries)
6. Mock validation is tested (correct mock usage, no over-mocking)
7. At least 10% increase in overall code coverage

## Key Areas to Cover

### External API Mocking Tests
```python
from unittest.mock import patch, Mock
import pytest

def test_llm_provider_call_with_mock():
    """Test LLM provider API call with mocked response"""
    with patch("core.llm.byok_handler.openai.ChatCompletion.acreate") as mock_create:
        mock_create.return_value = Mock(
            choices=[Mock(message=Mock(content="Test response"))],
            usage={"total_tokens": 100}
        )

        response = client.post("/api/agent/chat", json={
            "agent_id": "test-agent",
            "message": "Hello"
        })

        assert response.status_code == 200
        data = response.json()
        assert "Test response" in data["message"]

        # Verify mock was called correctly
        mock_create.assert_called_once()

def test_external_api_with_timeout():
    """Test external API call with timeout"""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = asyncio.TimeoutError()

        response = client.post("/api/agents/test-agent/fetch", json={
            "url": "https://external-api.com/data"
        })

        assert response.status_code == 408
        assert "timeout" in response.json()["detail"].lower()

def test_external_api_with_retry():
    """Test external API call with retry logic"""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Exception("Connection error"),
            Exception("Connection error"),
            Mock(status_code=200, json={"data": "success"})
        ]

        response = client.post("/api/agents/test-agent/fetch", json={
            "url": "https://external-api.com/data",
            "max_retries": 3
        })

        assert response.status_code == 200
        assert mock_get.call_count == 3
```

### Webhook Handling Tests
```python
def test_webhook_reception():
    """Test webhook reception and processing"""
    webhook_payload = {
        "event": "user.created",
        "user_id": "123",
        "timestamp": "2026-02-12T10:00:00Z"
    }

    response = client.post("/api/webhooks", json=webhook_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["received"] is True

def test_webhook_signature_validation():
    """Test webhook signature validation"""
    webhook_payload = {"event": "test"}

    # Invalid signature
    response = client.post(
        "/api/webhooks",
        json=webhook_payload,
        headers={"X-Webhook-Signature": "invalid"}
    )
    assert response.status_code == 401

    # Valid signature
    valid_signature = generate_webhook_signature(webhook_payload)
    response = client.post(
        "/api/webhooks",
        json=webhook_payload,
        headers={"X-Webhook-Signature": valid_signature}
    )
    assert response.status_code == 200

def test_webhook_retry_on_failure():
    """Test webhook retry on processing failure"""
    with patch("core.webhooks.process_webhook") as mock_process:
        mock_process.side_effect = [Exception("DB error"), None]

        response = client.post("/api/webhooks", json={"event": "test"})
        assert response.status_code == 200

        # Verify retry
        assert mock_process.call_count == 2
```

### Third-Party Service Integration Tests
```python
def test_openai_integration():
    """Test OpenAI integration"""
    with patch("openai.ChatCompletion.acreate") as mock_create:
        mock_create.return_value = Mock(
            choices=[Mock(message=Mock(content="AI response"))]
        )

        response = client.post("/api/agent/chat", json={
            "agent_id": "test-agent",
            "message": "Test",
            "provider": "openai"
        })

        assert response.status_code == 200
        assert "AI response" in response.json()["message"]

def test_anthropic_integration():
    """Test Anthropic integration"""
    with patch("anthropic.Anthropic.completions.create") as mock_create:
        mock_create.return_value = Mock(
            completion="AI response"
        )

        response = client.post("/api/agent/chat", json={
            "agent_id": "test-agent",
            "message": "Test",
            "provider": "anthropic"
        })

        assert response.status_code == 200

def test_database_integration():
    """Test database integration with transaction rollback"""
    with patch("core.models.SessionLocal") as mock_session:
        mock_session.return_value.__enter__.return_value = Mock()

        response = client.post("/api/agents", json={
            "name": "TestAgent",
            "maturity": "STUDENT"
        })

        assert response.status_code == 200

def test_redis_integration():
    """Test Redis integration"""
    with patch("redis.Redis.set") as mock_set, \
         patch("redis.Redis.get") as mock_get:
        mock_set.return_value = True
        mock_get.return_value = b"cached_value"

        # Set cache
        response = client.post("/api/cache/set", json={
            "key": "test_key",
            "value": "test_value"
        })
        assert response.status_code == 200

        # Get cache
        response = client.get("/api/cache/get/test_key")
        assert response.status_code == 200
        assert response.json()["value"] == "cached_value"
```

### Multi-Agent Coordination Tests
```python
def test_agent_to_agent_communication():
    """Test agent-to-agent communication"""
    agent1 = create_agent(name="Agent1", maturity="AUTONOMOUS")
    agent2 = create_agent(name="Agent2", maturity="AUTONOMOUS")

    response = client.post(f"/api/agents/{agent1.id}/message", json={
        "target_agent_id": agent2.id,
        "message": "Hello from Agent1"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["delivered"] is True

def test_shared_agent_state():
    """Test shared state between agents"""
    agent1 = create_agent(name="Agent1")
    agent2 = create_agent(name="Agent2")

    # Agent1 sets state
    client.post(f"/api/agents/{agent1.id}/state", json={
        "key": "shared_data",
        "value": "test_value"
    })

    # Agent2 reads state
    response = client.get(f"/api/agents/{agent2.id}/state/shared_data")
    assert response.status_code == 200
    assert response.json()["value"] == "test_value"

def test_agent_collaboration():
    """Test multiple agents collaborating on a task"""
    agent1 = create_agent(name="Researcher", maturity="AUTONOMOUS")
    agent2 = create_agent(name="Writer", maturity="AUTONOMOUS")

    response = client.post("/api/collaboration", json={
        "agents": [agent1.id, agent2.id],
        "task": "Research and write article",
        "workflow": "sequential"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert len(data["agents"]) == 2

def test_agent_conflict_resolution():
    """Test conflict resolution when agents disagree"""
    agent1 = create_agent(name="Agent1")
    agent2 = create_agent(name="Agent2")

    # Both agents try to update same resource
    response1 = client.put(f"/api/resources/test", json={
        "agent_id": agent1.id,
        "value": "value1"
    })

    response2 = client.put(f"/api/resources/test", json={
        "agent_id": agent2.id,
        "value": "value2"
    })

    # One should succeed, one should fail or merge
    assert response1.status_code != response2.status_code or \
           response1.json()["value"] != response2.json()["value"]
```

### Service Failure Tests
```python
def test_service_timeout_handling():
    """Test handling of service timeouts"""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = asyncio.TimeoutError()

        response = client.post("/api/agents/test-agent/fetch", json={
            "url": "https://slow-api.com/data"
        })

        assert response.status_code == 408
        assert "timeout" in response.json()["detail"]

def test_service_error_handling():
    """Test handling of service errors"""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Mock(
            status_code=500,
            json={"error": "Internal server error"}
        )

        response = client.post("/api/agents/test-agent/fetch", json={
            "url": "https://failing-api.com/data"
        })

        assert response.status_code == 502

def test_service_retry_with_backoff():
    """Test retry with exponential backoff"""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            Mock(status_code=200, json={"data": "success"})
        ]

        import time
        start = time.time()

        response = client.post("/api/agents/test-agent/fetch", json={
            "url": "https://flaky-api.com/data",
            "max_retries": 3
        })

        elapsed = time.time() - start

        assert response.status_code == 200
        assert mock_get.call_count == 3
        # Verify exponential backoff (should take > 3 seconds)
        assert elapsed > 3
```

### Mock Validation Tests
```python
def test_mock_not_over_mocked():
    """Test that we're not over-mocking"""
    # Test should call real service logic, not just return mock value
    with patch("external_api.call") as mock_call:
        mock_call.return_value = "result"

        response = client.post("/api/endpoint", json={"data": "test"})

        # Verify service logic was called, not just mock returned
        assert mock_call.called
        assert response.status_code == 200
        assert response.json()["processed"] is True  # Real processing happened

def test_mock_correct_arguments():
    """Test mocks are called with correct arguments"""
    with patch("external_api.call") as mock_call:
        mock_call.return_value = "result"

        response = client.post("/api/endpoint", json={"data": "test"})

        # Verify mock was called with expected arguments
        mock_call.assert_called_with(
            endpoint="https://api.example.com/endpoint",
            method="POST",
            data={"data": "test"}
        )
```

## Tasks

### Wave 1: External Service Mocking (Priority: P0)

- [ ] **Task 1.1**: Create `backend/tests/integration/external/test_llm_providers.py`
  - Test OpenAI integration
  - Test Anthropic integration
  - Test DeepSeek integration
  - Test Gemini integration
  - **Acceptance**: All LLM provider integrations tested with mocking

- [ ] **Task 1.2**: Create `backend/tests/integration/external/test_external_api.py`
  - Test external API calls
  - Test API timeout handling
  - Test API retry logic
  - Test API error handling
  - **Acceptance**: All external API scenarios tested

- [ ] **Task 1.3**: Create `backend/tests/integration/external/test_database_integration.py`
  - Test PostgreSQL integration
  - Test Redis integration
  - Test connection pooling
  - **Acceptance**: All database integrations tested

### Wave 2: Webhook Tests (Priority: P0)

- [ ] **Task 2.1**: Create `backend/tests/integration/webhooks/test_webhook_reception.py`
  - Test webhook reception
  - Test webhook processing
  - Test webhook storage
  - **Acceptance**: All webhook reception scenarios tested

- [ ] **Task 2.2**: Create `backend/tests/integration/webhooks/test_webhook_security.py`
  - Test webhook signature validation
  - Test webhook authentication
  - Test webhook replay protection
  - **Acceptance**: All webhook security scenarios tested

- [ ] **Task 2.3**: Create `backend/tests/integration/webhooks/test_webhook_retries.py`
  - Test webhook retry on failure
  - Test webhook exponential backoff
  - Test webhook dead letter queue
  - **Acceptance**: All webhook retry scenarios tested

### Wave 3: Multi-Agent Coordination (Priority: P0)

- [ ] **Task 3.1**: Create `backend/tests/integration/agents/test_agent_communication.py`
  - Test agent-to-agent communication
  - Test broadcast messaging
  - Test private messaging
  - **Acceptance**: All agent communication scenarios tested

- [ ] **Task 3.2**: Create `backend/tests/integration/agents/test_agent_shared_state.py`
  - Test shared state between agents
  - Test state synchronization
  - Test state conflict resolution
  - **Acceptance**: All shared state scenarios tested

- [ ] **Task 3.3**: Create `backend/tests/integration/agents/test_agent_collaboration.py`
  - Test sequential collaboration
  - Test parallel collaboration
  - Test agent workflows
  - **Acceptance**: All collaboration scenarios tested

### Wave 4: Service Failure Tests (Priority: P1)

- [ ] **Task 4.1**: Create `backend/tests/integration/external/test_service_failures.py`
  - Test service timeout handling
  - Test service error handling
  - Test service retry with backoff
  - Test service circuit breaker
  - **Acceptance**: All service failure scenarios tested

- [ ] **Task 4.2**: Create `backend/tests/integration/external/test_mock_validation.py`
  - Test mocks are not over-mocked
  - Test mocks use correct arguments
  - Test mocks are cleaned up
  - **Acceptance**: Mock usage validated

### Wave 5: Coverage & Verification (Priority: P1)

- [ ] **Task 5.1**: Run coverage report
  - Generate coverage report
  - Identify uncovered lines
  - **Acceptance**: Coverage report generated

- [ ] **Task 5.2**: Add missing tests
  - Review uncovered lines
  - Add edge case tests
  - **Acceptance**: At least 10% increase in coverage

- [ ] **Task 5.3**: Verify all tests pass
  - Run full test suite
  - Fix failures
  - **Acceptance**: All external service and multi-agent tests passing

## Dependencies

- Phase 1 (Test Infrastructure) - Complete
- Phase 2 (Core Property Tests) - Complete
- External service integrations implemented
- Multi-agent system implemented
- Webhook system implemented

## Estimated Time

- Wave 1: 3-4 hours
- Wave 2: 2-3 hours
- Wave 3: 3-4 hours
- Wave 4: 2-3 hours
- Wave 5: 1-2 hours
- **Total**: 11-16 hours

## Definition of Done

1. External API calls tested with mocking
2. Webhook handling tested
3. Third-party service integration tested
4. Multi-agent coordination tested
5. Service failures tested
6. Mock validation tested
7. At least 10% increase in overall code coverage
8. All tests passing
9. Documentation updated

## Verification Checklist

- [ ] LLM providers tested
- [ ] External API tested
- [ ] Database integration tested
- [ ] Webhooks tested
- [ ] Agent communication tested
- [ ] Agent shared state tested
- [ ] Agent collaboration tested
- [ ] Service failures tested
- [ ] Mock validation tested
- [ ] Coverage increased by at least 10%
- [ ] All tests passing
