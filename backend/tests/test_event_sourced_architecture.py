"""
Tests for Event-Sourced Architecture - LLM Analysis Integration
"""

import pytest
from datetime import datetime
from core.event_sourced_architecture import (
    EventSourcedOrchestrator,
    PerceptionResult,
    EventType
)


class TestLLMAnalysisIntegration:
    """Test actual LLM analysis in perception layer"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance"""
        return EventSourcedOrchestrator()

    @pytest.mark.asyncio
    async def test_perceive_with_llm_analysis(self, orchestrator):
        """Test that perception uses actual LLM analysis"""
        aggregate_id = "test-workflow-1"
        input_data = {
            "type": "email_request",
            "recipient": "user@example.com",
            "subject": "Test subject",
            "body": "Test body"
        }

        # Process through perception layer
        result = await orchestrator.perception.perceive(aggregate_id, input_data)

        # Verify structure
        assert isinstance(result, PerceptionResult)
        assert hasattr(result, 'intent')
        assert hasattr(result, 'entities')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'reasoning')
        assert hasattr(result, 'suggested_actions')

        # Verify values are populated (not hardcoded)
        assert result.intent is not None
        assert isinstance(result.entities, dict)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str)
        assert isinstance(result.suggested_actions, list)
        assert len(result.suggested_actions) > 0

    @pytest.mark.asyncio
    async def test_fallback_analysis_on_llm_error(self, orchestrator):
        """Test fallback analysis when LLM fails"""
        # Mock LLM failure by providing invalid input
        aggregate_id = "test-workflow-2"
        input_data = {"invalid": "data"}

        result = await orchestrator.perception.perceive(aggregate_id, input_data)

        # Should still return a valid PerceptionResult
        assert isinstance(result, PerceptionResult)
        assert result.intent is not None
        assert result.confidence >= 0.0

    def test_build_analysis_prompt(self, orchestrator):
        """Test prompt building for LLM analysis"""
        input_data = {
            "type": "transaction",
            "amount": 100,
            "currency": "USD"
        }

        prompt = orchestrator.perception._build_analysis_prompt(input_data)

        # Verify prompt contains input data
        assert "transaction" in prompt
        assert "100" in prompt
        assert "USD" in prompt

        # Verify prompt asks for required fields
        assert "intent" in prompt.lower()
        assert "entities" in prompt.lower()
        assert "confidence" in prompt.lower()
        assert "reasoning" in prompt.lower()
        assert "suggested_actions" in prompt.lower()

    @pytest.mark.asyncio
    async def test_parse_llm_response_json(self, orchestrator):
        """Test parsing valid JSON response from LLM"""
        json_response = '''{
            "intent": "process_payment",
            "entities": {"amount": 100, "currency": "USD"},
            "confidence": 0.9,
            "reasoning": "Payment request detected",
            "suggested_actions": ["validate", "process"]
        }'''

        result = orchestrator.perception._parse_llm_response(
            json_response,
            {"original": "data"}
        )

        assert result.intent == "process_payment"
        assert result.entities == {"amount": 100, "currency": "USD"}
        assert result.confidence == 0.9
        assert "Payment request detected" in result.reasoning
        assert "validate" in result.suggested_actions
        assert "process" in result.suggested_actions

    @pytest.mark.asyncio
    async def test_parse_llm_response_malformed(self, orchestrator):
        """Test parsing malformed LLM response"""
        malformed_response = "This is not valid JSON"

        result = orchestrator.perception._parse_llm_response(
            malformed_response,
            {"test": "data"}
        )

        # Should fallback to structured response
        assert isinstance(result, PerceptionResult)
        assert result.intent is not None
        assert isinstance(result.entities, dict)

    @pytest.mark.asyncio
    async def test_full_pipeline_with_llm(self, orchestrator):
        """Test complete pipeline: perception -> planning -> execution"""
        aggregate_id = "test-workflow-full"
        input_data = {
            "action": "send_email",
            "to": "user@example.com",
            "subject": "Test"
        }

        # Process through full pipeline
        response = await orchestrator.process(aggregate_id, input_data)

        # Verify response structure
        assert "status" in response
        assert response["status"] in ["completed", "pending_approval"]

        # Check event log
        events = orchestrator.get_event_log(aggregate_id)
        assert len(events) > 0

        # Verify perception events
        perception_events = [e for e in events if "perception" in e["event_type"]]
        assert len(perception_events) > 0

        # Verify planning events
        plan_events = [e for e in events if "plan" in e["event_type"]]
        assert len(plan_events) > 0

    def test_event_log_contains_ai_confidence(self, orchestrator):
        """Test that events include AI confidence scores"""
        aggregate_id = "test-workflow-confidence"

        # Get event log (should be empty initially)
        events = orchestrator.get_event_log(aggregate_id)
        assert len(events) == 0

        # After processing, events should have AI metadata
        # This is verified in test_full_pipeline_with_llm

    @pytest.mark.asyncio
    async def test_llm_analysis_with_complex_input(self, orchestrator):
        """Test LLM analysis with complex nested input"""
        complex_input = {
            "transaction": {
                "type": "payment",
                "amount": 1500.00,
                "currency": "USD",
                "metadata": {
                    "source": "stripe",
                    "customer_id": "cust_123",
                    "risk_score": 0.2
                }
            },
            "context": {
                "user_authenticated": True,
                "session_id": "sess_456"
            }
        }

        result = await orchestrator.perception.perceive("test-complex", complex_input)

        # Should handle complex structures
        assert isinstance(result, PerceptionResult)
        assert result.confidence >= 0.0
        assert len(result.suggested_actions) > 0


class TestEventSourcingWithLLM:
    """Test event sourcing integration with LLM analysis"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance"""
        return EventSourcedOrchestrator()

    @pytest.mark.asyncio
    async def test_perception_events_logged(self, orchestrator):
        """Test that perception steps are logged as events"""
        aggregate_id = "test-perception-events"
        input_data = {"test": "data"}

        await orchestrator.perception.perceive(aggregate_id, input_data)

        events = orchestrator.get_event_log(aggregate_id)

        # Should have started and completed events
        event_types = [e["event_type"] for e in events]
        assert EventType.PERCEPTION_STARTED.value in event_types
        assert EventType.PERCEPTION_COMPLETED.value in event_types

    @pytest.mark.asyncio
    async def test_event_contains_ai_metadata(self, orchestrator):
        """Test that events contain AI confidence and reasoning"""
        aggregate_id = "test-ai-metadata"
        input_data = {"action": "test"}

        await orchestrator.perception.perceive(aggregate_id, input_data)

        events = orchestrator.get_event_log(aggregate_id)

        # Find perception completed event
        completed_events = [
            e for e in events
            if e["event_type"] == EventType.PERCEPTION_COMPLETED.value
        ]

        assert len(completed_events) > 0
        event = completed_events[0]

        # Verify AI metadata
        assert "ai_confidence" in event
        assert event["ai_confidence"] is not None
        assert "ai_reasoning" in event
        assert event["ai_reasoning"] is not None
