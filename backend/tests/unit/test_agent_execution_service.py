"""
Unit Tests for Agent Execution Service

Tests centralized agent chat execution with:
- Governance integration
- WebSocket streaming support
- AgentExecution audit trail
- Episode creation for memory

Target Coverage: 80%
Target Branch Coverage: 50%+
Pass Rate Target: 95%+
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.agent_execution_service import execute_agent_chat, ChatMessage
from core.models import AgentRegistry, AgentExecution, AgentStatus, User, UserRole


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def db():
    """Create database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_agent(db):
    """Create sample agent."""
    agent = AgentRegistry(
        id="test-agent-123",
        name="Test Agent",
        description="A test agent for unit testing",
        category="testing",
        status=AgentStatus.SUPERVISED,
        confidence_score=0.85,
        module_path="agents.test_agent",
        class_name="TestAgent",
        configuration={"param1": "value1"},
        schedule_config={},
        version=1,
        workspace_id="default",
        user_id="test-user-123"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def sample_user(db):
    """Create sample user."""
    user = User(
        id="test-user-123",
        email="test@example.com",
        hashed_password="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# =============================================================================
# Test Class: Execute Agent Chat - Governance
# =============================================================================

class TestExecuteAgentChatGovernance:
    """Tests for governance integration in execute_agent_chat."""

    @pytest.mark.asyncio
    async def test_governance_blocks_student_agent_chat(self, db, sample_agent):
        """RED: Test that governance blocks STUDENT agents from chat."""
        sample_agent.status = AgentStatus.STUDENT
        db.commit()

        result = await execute_agent_chat(
            agent_id=sample_agent.id,
            message="Hello",
            user_id="test-user-123",
            db_session=db
        )

        # Should block student agents
        assert result["success"] is False
        assert "blocked" in result["error"].lower() or "governance" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_governance_allows_supervised_agent_chat(self, db, sample_agent):
        """RED: Test that governance allows SUPERVISED agents to chat."""
        sample_agent.status = AgentStatus.SUPERVISED
        db.commit()

        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm.return_value.stream_completion = AsyncMock(return_value=iter(["Hello", " world"]))
            mock_llm.return_value.analyze_query_complexity = Mock(return_value="low")
            mock_llm.return_value.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            result = await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Hello",
                user_id="test-user-123",
                db_session=db
            )

            # Should allow supervised agents
            assert result["success"] is True
            assert "response" in result

    @pytest.mark.asyncio
    async def test_emergency_bypass_allows_all_agents(self, db, sample_agent):
        """RED: Test emergency bypass allows all agents regardless of maturity."""
        sample_agent.status = AgentStatus.STUDENT
        db.commit()

        with patch('core.agent_execution_service.LLMService') as mock_llm, \
             patch.dict('os.environ', {'EMERGENCY_GOVERNANCE_BYPASS': 'true'}):
            mock_llm.return_value.stream_completion = AsyncMock(return_value=iter(["Hello"]))
            mock_llm.return_value.analyze_query_complexity = Mock(return_value="low")
            mock_llm.return_value.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            result = await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Hello",
                user_id="test-user-123",
                db_session=db
            )

            # Emergency bypass should allow execution
            assert result["success"] is True


# =============================================================================
# Test Class: Execute Agent Chat - Execution Record
# =============================================================================

class TestExecuteAgentChatExecutionRecord:
    """Tests for AgentExecution audit trail creation."""

    @pytest.mark.asyncio
    async def test_creates_agent_execution_record(self, db, sample_agent):
        """RED: Test that AgentExecution record is created."""
        initial_count = db.query(AgentExecution).filter(
            AgentExecution.agent_id == sample_agent.id
        ).count()

        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm.return_value.stream_completion = AsyncMock(return_value=iter(["Response"]))
            mock_llm.return_value.analyze_query_complexity = Mock(return_value="low")
            mock_llm.return_value.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Test message",
                user_id="test-user-123",
                db_session=db
            )

            final_count = db.query(AgentExecution).filter(
                AgentExecution.agent_id == sample_agent.id
            ).count()

            assert final_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_execution_record_has_correct_metadata(self, db, sample_agent):
        """RED: Test that AgentExecution record has correct metadata."""
        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm.return_value.stream_completion = AsyncMock(return_value=iter(["Response"]))
            mock_llm.return_value.analyze_query_complexity = Mock(return_value="low")
            mock_llm.return_value.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Test message",
                user_id="test-user-123",
                session_id="test-session-123",
                db_session=db
            )

            execution = db.query(AgentExecution).filter(
                AgentExecution.agent_id == sample_agent.id
            ).order_by(AgentExecution.created_at.desc()).first()

            assert execution is not None
            assert execution.user_id == "test-user-123"
            assert execution.session_id == "test-session-123"
            assert execution.action_type == "chat"
            assert execution.status in ["running", "completed", "failed"]

    @pytest.mark.asyncio
    async def test_execution_record_includes_input_data(self, db, sample_agent):
        """RED: Test that execution record includes input message."""
        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm.return_value.stream_completion = AsyncMock(return_value=iter(["Response"]))
            mock_llm.return_value.analyze_query_complexity = Mock(return_value="low")
            mock_llm.return_value.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            test_message = "Test input message"
            await execute_agent_chat(
                agent_id=sample_agent.id,
                message=test_message,
                user_id="test-user-123",
                db_session=db
            )

            execution = db.query(AgentExecution).filter(
                AgentExecution.agent_id == sample_agent.id
            ).order_by(AgentExecution.created_at.desc()).first()

            assert execution is not None
            assert execution.input_data is not None
            assert execution.input_data.get("message") == test_message


# =============================================================================
# Test Class: Execute Agent Chat - LLM Integration
# =============================================================================

class TestExecuteAgentChatLLM:
    """Tests for LLM service integration."""

    @pytest.mark.asyncio
    async def test_initializes_llm_service(self, db, sample_agent):
        """RED: Test that LLM service is initialized."""
        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm.return_value.stream_completion = AsyncMock(return_value=iter(["Response"]))
            mock_llm.return_value.analyze_query_complexity = Mock(return_value="low")
            mock_llm.return_value.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Test",
                user_id="test-user-123",
                db_session=db
            )

            # Verify LLM service was called
            mock_llm.assert_called_once()
            mock_llm.assert_called_with(tenant_id="default", db=db)

    @pytest.mark.asyncio
    async def test_analyzes_query_complexity(self, db, sample_agent):
        """RED: Test that query complexity is analyzed."""
        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm_instance = mock_llm.return_value
            mock_llm_instance.stream_completion = AsyncMock(return_value=iter(["Response"]))
            mock_llm_instance.analyze_query_complexity = Mock(return_value="medium")
            mock_llm_instance.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Complex query requiring analysis",
                user_id="test-user-123",
                db_session=db
            )

            # Verify complexity analysis was called
            mock_llm_instance.analyze_query_complexity.assert_called_once()
            call_args = mock_llm_instance.analyze_query_complexity.call_args
            assert call_args[0][0] == "Complex query requiring analysis"

    @pytest.mark.asyncio
    async def test_gets_optimal_provider(self, db, sample_agent):
        """RED: Test that optimal provider is selected."""
        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm_instance = mock_llm.return_value
            mock_llm_instance.stream_completion = AsyncMock(return_value=iter(["Response"]))
            mock_llm_instance.analyze_query_complexity = Mock(return_value="low")
            mock_llm_instance.get_optimal_provider = Mock(return_value=("anthropic", "claude-3-sonnet"))

            await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Test message",
                user_id="test-user-123",
                db_session=db
            )

            # Verify optimal provider selection
            mock_llm_instance.get_optimal_provider.assert_called_once()
            call_args = mock_llm_instance.get_optimal_provider.call_args
            assert call_args[1]["task_type"] == "chat"


# =============================================================================
# Test Class: Execute Agent Chat - Response Handling
# =============================================================================

class TestExecuteAgentChatResponse:
    """Tests for response handling and return values."""

    @pytest.mark.asyncio
    async def test_returns_execution_id(self, db, sample_agent):
        """RED: Test that execution ID is returned."""
        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm.return_value.stream_completion = AsyncMock(return_value=iter(["Response"]))
            mock_llm.return_value.analyze_query_complexity = Mock(return_value="low")
            mock_llm.return_value.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            result = await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Test",
                user_id="test-user-123",
                db_session=db
            )

            assert "execution_id" in result
            assert result["execution_id"] is not None
            assert len(result["execution_id"]) > 0

    @pytest.mark.asyncio
    async def test_returns_agent_info(self, db, sample_agent):
        """RED: Test that agent information is returned."""
        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm.return_value.stream_completion = AsyncMock(return_value=iter(["Response"]))
            mock_llm.return_value.analyze_query_complexity = Mock(return_value="low")
            mock_llm.return_value.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            result = await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Test",
                user_id="test-user-123",
                db_session=db
            )

            assert result["agent_id"] == sample_agent.id
            assert result["agent_name"] == sample_agent.name

    @pytest.mark.asyncio
    async def test_accumulates_streamed_response(self, db, sample_agent):
        """RED: Test that streamed response is accumulated."""
        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm_instance = mock_llm.return_value
            mock_llm_instance.stream_completion = AsyncMock(
                return_value=iter(["Hello", " ", "world", "!"])
            )
            mock_llm_instance.analyze_query_complexity = Mock(return_value="low")
            mock_llm_instance.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            result = await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Test",
                user_id="test-user-123",
                db_session=db
            )

            assert result["success"] is True
            assert result["response"] == "Hello world!"


# =============================================================================
# Test Class: Execute Agent Chat - Error Handling
# =============================================================================

class TestExecuteAgentChatErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handles_missing_agent_gracefully(self, db):
        """RED: Test execution when agent doesn't exist."""
        with patch('core.agent_execution_service.LLMService') as mock_llm, \
             patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
            mock_llm.return_value.stream_completion = AsyncMock(return_value=iter(["Response"]))
            mock_llm.return_value.analyze_query_complexity = Mock(return_value="low")
            mock_llm.return_value.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            mock_resolver_instance = mock_resolver.return_value
            mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(None, None))

            # Should still execute with system defaults
            result = await execute_agent_chat(
                agent_id="nonexistent-agent",
                message="Test",
                user_id="test-user-123",
                db_session=db
            )

            # Should succeed with defaults
            assert result["success"] is True
            assert "response" in result

    @pytest.mark.asyncio
    async def test_handles_llm_failure(self, db, sample_agent):
        """RED: Test handling of LLM service failure."""
        with patch('core.agent_execution_service.LLMService') as mock_llm:
            mock_llm_instance = mock_llm.return_value
            mock_llm_instance.stream_completion = AsyncMock(side_effect=Exception("LLM failure"))
            mock_llm_instance.analyze_query_complexity = Mock(return_value="low")
            mock_llm_instance.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            result = await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Test",
                user_id="test-user-123",
                db_session=db
            )

            # Should handle error gracefully
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_handles_budget_check_failure(self, db, sample_agent):
        """RED: Test that budget check failure doesn't block execution."""
        with patch('core.agent_execution_service.LLMService') as mock_llm, \
             patch('core.agent_execution_service.personal_budget_service') as mock_budget:
            mock_llm.return_value.stream_completion = AsyncMock(return_value=iter(["Response"]))
            mock_llm.return_value.analyze_query_complexity = Mock(return_value="low")
            mock_llm.return_value.get_optimal_provider = Mock(return_value=("openai", "gpt-4"))

            # Budget check raises exception
            mock_budget.is_budget_exceeded = Mock(side_effect=Exception("Budget service down"))

            result = await execute_agent_chat(
                agent_id=sample_agent.id,
                message="Test",
                user_id="test-user-123",
                db_session=db
            )

            # Should continue despite budget check failure
            assert result["success"] is True


# =============================================================================
# Test Class: ChatMessage Model
# =============================================================================

class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_chat_message_initialization(self):
        """RED: Test ChatMessage initialization."""
        message = ChatMessage(role="user", content="Hello")
        assert message.role == "user"
        assert message.content == "Hello"

    def test_chat_message_with_system_role(self):
        """RED: Test ChatMessage with system role."""
        message = ChatMessage(role="system", content="You are a helpful assistant")
        assert message.role == "system"
        assert "helpful assistant" in message.content


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
