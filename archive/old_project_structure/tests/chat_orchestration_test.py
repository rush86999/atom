import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.ChatOrchestrationService import (
    ChatOrchestrationService,
    chatOrchestrationService,
)
from src.nlu_agents.nlu_bridge_service import NLUBridgeService
from src.workflows.WorkflowExecutionService import WorkflowExecutionService
from src.orchestration.ConversationalOrchestration import ConversationalOrchestration


class TestChatOrchestrationService:
    """Test suite for ChatOrchestrationService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = ChatOrchestrationService()
        self.user_id = "test_user_123"
        self.session_id = "test_session_456"

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test service initialization"""
        with (
            patch.object(self.service.nlu_bridge, "initialize") as mock_nlu_init,
            patch.object(
                self.service.workflow_service, "initialize"
            ) as mock_workflow_init,
        ):
            await self.service.initialize()

            mock_nlu_init.assert_called_once()
            mock_workflow_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_workflow_request(self):
        """Test processing a workflow creation message"""
        test_message = "When I receive important emails, create tasks in Notion"

        # Mock NLU analysis result
        mock_nlu_result = Mock()
        mock_nlu_result.is_workflow_request = True
        mock_nlu_result.trigger = {"service": "gmail", "event": "new_email"}
        mock_nlu_result.actions = [{"service": "notion", "action": "create_task"}]
        mock_nlu_result.primary_goal = "Automate email to task workflow"
        mock_nlu_result.confidence = 0.85

        with (
            patch.object(
                self.service.nlu_bridge,
                "analyze_workflow_request",
                return_value=mock_nlu_result,
            ) as mock_analyze,
            patch.object(
                self.service.nlu_bridge,
                "generate_workflow_from_nlu_analysis",
                return_value={"name": "Test Workflow", "description": "Test"},
            ) as mock_generate,
            patch.object(
                self.service.workflow_service,
                "execute_workflow",
                return_value="wf_test_123",
            ) as mock_execute,
        ):
            response = await self.service.process_message(self.user_id, test_message)

            # Verify NLU analysis was called
            mock_analyze.assert_called_once_with(test_message, self.user_id)

            # Verify workflow generation and execution
            mock_generate.assert_called_once_with(mock_nlu_result)
            mock_execute.assert_called_once()

            # Verify response structure
            assert response.type == "workflow"
            assert "workflowId" in response.metadata
            assert response.metadata["workflowId"] == "wf_test_123"
            assert "I've created and started a workflow" in response.message

    @pytest.mark.asyncio
    async def test_process_message_conversational(self):
        """Test processing a conversational message"""
        test_message = "What's on my calendar today?"

        # Mock NLU analysis result (not a workflow request)
        mock_nlu_result = Mock()
        mock_nlu_result.is_workflow_request = False

        # Mock conversational response
        mock_conversational_response = {
            "response": "Here's what's on your calendar today...",
            "followUpQuestions": ["Would you like to schedule something else?"],
        }

        with (
            patch.object(
                self.service.nlu_bridge,
                "analyze_workflow_request",
                return_value=mock_nlu_result,
            ) as mock_analyze,
            patch.object(
                self.service.conversational_orchestration,
                "process_user_message",
                return_value=mock_conversational_response,
            ) as mock_conversational,
        ):
            response = await self.service.process_message(self.user_id, test_message)

            # Verify NLU analysis was called
            mock_analyze.assert_called_once_with(test_message, self.user_id)

            # Verify conversational processing was called
            mock_conversational.assert_called_once()

            # Verify response structure
            assert response.type == "text"
            assert "Here's what's on your calendar" in response.message
            assert "suggestedActions" in response.metadata

    @pytest.mark.asyncio
    async def test_multi_step_process_creation(self):
        """Test starting a multi-step process"""
        process_name = "schedule_meeting"

        response = await self.service.start_multi_step_process(
            self.user_id, process_name
        )

        # Verify response structure
        assert response.type == "multi_step"
        assert "processId" in response.metadata
        assert "Let's set up" in response.message

        # Verify process was stored
        active_process = await self.service.get_active_process(self.user_id)
        assert active_process is not None
        assert active_process.name == "Meeting Scheduling"
        assert active_process.current_step == 0

    @pytest.mark.asyncio
    async def test_multi_step_process_execution(self):
        """Test executing steps in a multi-step process"""
        # Start a process first
        await self.service.start_multi_step_process(self.user_id, "schedule_meeting")

        # Execute first step
        step_response = await self.service.process_message(
            self.user_id, "Team planning meeting for Q4 strategy"
        )

        # Verify step response
        assert step_response.type == "multi_step"
        assert "Great! Now" in step_response.message

        # Verify process state updated
        active_process = await self.service.get_active_process(self.user_id)
        assert active_process.current_step == 1
        assert active_process.steps[0].status == "completed"
        assert active_process.steps[1].status == "active"

    @pytest.mark.asyncio
    async def test_process_cancellation(self):
        """Test cancelling an active process"""
        # Start a process
        await self.service.start_multi_step_process(self.user_id, "schedule_meeting")

        # Verify process exists
        active_process = await self.service.get_active_process(self.user_id)
        assert active_process is not None

        # Cancel the process
        await self.service.cancel_process(self.user_id)

        # Verify process was removed
        active_process = await self.service.get_active_process(self.user_id)
        assert active_process is None

    @pytest.mark.asyncio
    async def test_conversation_history_management(self):
        """Test conversation history storage and retrieval"""
        # Process multiple messages
        await self.service.process_message(self.user_id, "Hello")
        await self.service.process_message(self.user_id, "How are you?")

        # Retrieve conversation history
        history = await self.service.get_conversation_history(self.user_id)

        # Verify history structure
        assert len(history) >= 4  # 2 user messages + 2 assistant responses
        assert history[0].role == "user"
        assert history[0].content == "Hello"
        assert history[1].role == "assistant"

        # Clear history
        await self.service.clear_conversation_history(self.user_id)

        # Verify history is cleared
        history = await self.service.get_conversation_history(self.user_id)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in message processing"""
        test_message = "This should cause an error"

        with patch.object(
            self.service.nlu_bridge,
            "analyze_workflow_request",
            side_effect=Exception("Test error"),
        ):
            response = await self.service.process_message(self.user_id, test_message)

            # Verify error response
            assert response.type == "error"
            assert "I encountered an error" in response.message

    @pytest.mark.asyncio
    async def test_context_creation_and_retrieval(self):
        """Test chat context creation and management"""
        # Process a message to create context
        await self.service.process_message(self.user_id, "Test message")

        # Verify context was created
        context = await self.service.get_or_create_context(self.user_id)
        assert context.user_id == self.user_id
        assert context.session_id is not None
        assert len(context.conversation_history) > 0
        assert "gmail" in context.user_preferences.preferred_services

    @pytest.mark.asyncio
    async def test_workflow_creation_event_emission(self):
        """Test that workflow creation emits events"""
        test_message = "Create a workflow for email automation"

        # Mock NLU result
        mock_nlu_result = Mock()
        mock_nlu_result.is_workflow_request = True
        mock_nlu_result.trigger = {"service": "gmail", "event": "new_email"}
        mock_nlu_result.actions = [{"service": "slack", "action": "send_message"}]

        event_called = False
        event_data = None

        def event_handler(data):
            nonlocal event_called, event_data
            event_called = True
            event_data = data

        self.service.on("workflowCreated", event_handler)

        with (
            patch.object(
                self.service.nlu_bridge,
                "analyze_workflow_request",
                return_value=mock_nlu_result,
            ),
            patch.object(
                self.service.nlu_bridge,
                "generate_workflow_from_nlu_analysis",
                return_value={"name": "Test"},
            ),
            patch.object(
                self.service.workflow_service,
                "execute_workflow",
                return_value="wf_test",
            ),
        ):
            await self.service.process_message(self.user_id, test_message)

            # Verify event was emitted
            assert event_called is True
            assert event_data["userId"] == self.user_id
            assert event_data["workflowId"] == "wf_test"


class TestChatOrchestrationIntegration:
    """Integration tests for chat orchestration"""

    @pytest.mark.asyncio
    async def test_end_to_end_workflow_creation(self):
        """Test complete workflow creation from chat message"""
        service = ChatOrchestrationService()

        # Real message that should trigger workflow creation
        test_message = (
            "When I get emails labeled important, send me a Slack notification"
        )

        try:
            await service.initialize()
            response = await service.process_message(
                "integration_test_user", test_message
            )

            # Verify we got some kind of response
            assert response is not None
            assert response.message is not None
            assert response.type in ["workflow", "text", "multi_step", "error"]

        finally:
            await service.dispose()

    @pytest.mark.asyncio
    async def test_multi_step_scheduling_process(self):
        """Test complete multi-step scheduling process"""
        service = ChatOrchestrationService()

        try:
            await service.initialize()

            # Start scheduling process
            start_response = await service.start_multi_step_process(
                "integration_test_user", "schedule_meeting"
            )
            assert start_response.type == "multi_step"

            # Execute steps
            step1_response = await service.process_message(
                "integration_test_user", "Team retrospective meeting"
            )
            assert step1_response.type == "multi_step"

            step2_response = await service.process_message(
                "integration_test_user", "Tomorrow at 3 PM"
            )
            assert step2_response.type == "multi_step"

            step3_response = await service.process_message(
                "integration_test_user", "team@company.com, manager@company.com"
            )

            # Final step might complete the process
            if step3_response.type == "multi_step":
                step4_response = await service.process_message(
                    "integration_test_user", "Yes, confirm everything"
                )
                assert step4_response.type == "text"  # Process completed

        finally:
            await service.dispose()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
