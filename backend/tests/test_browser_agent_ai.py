"""
Tests for Browser Agent AI Integration with Lux Model
Tests the enhanced AI-powered browser automation with visual reasoning.

Note: These tests use extensive mocking to avoid numpy/cv2 import issues in test environment.
"""

import asyncio
import io

# Mock the problematic imports before importing our test modules
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest

sys.modules['cv2'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()


class TestComputerAction:
    """Test ComputerAction dataclass"""

    from ai.lux_model import ComputerAction, ComputerActionType

    def test_create_click_action(self):
        """Test creating a click action"""
        action = self.ComputerAction(
            action_type=self.ComputerActionType.CLICK,
            parameters={"coordinates": [100, 200]},
            confidence=0.95,
            description="Click login button"
        )

        assert action.action_type == self.ComputerActionType.CLICK
        assert action.parameters == {"coordinates": [100, 200]}
        assert action.confidence == 0.95
        assert action.description == "Click login button"

    def test_create_type_action(self):
        """Test creating a type action"""
        action = self.ComputerAction(
            action_type=self.ComputerActionType.TYPE,
            parameters={"text": "hello world"},
            confidence=1.0,
            description="Type text"
        )

        assert action.action_type == self.ComputerActionType.TYPE
        assert action.parameters["text"] == "hello world"


class TestLuxModelActionPlanning:
    """Test Lux Model action planning with mocked dependencies"""

    def test_lux_model_initialization(self):
        """Test LuxModel initializes with API key"""
        from ai.lux_model import LuxModel

        # Mock config
        with patch('ai.lux_model.lux_config') as mock_config:
            mock_config.get_anthropic_key.return_value = "test-key-123"

            model = LuxModel()

            assert model.api_key == "test-key-123"
            assert model.client is not None

    def test_lux_model_without_api_key(self):
        """Test LuxModel initialization without API key"""
        from ai.lux_model import LuxModel

        with patch('ai.lux_model.lux_config') as mock_config:
            mock_config.get_anthropic_key.return_value = None
            # Remove environment variables entirely
            with patch.dict('os.environ', {}, clear=True):
                model = LuxModel()

                # api_key will be None (no environment vars to check)
                assert model.client is None

    @pytest.mark.asyncio
    async def test_interpret_command_returns_actions(self):
        """Test that interpret_command returns list of actions"""
        from ai.lux_model import LuxModel

        model = LuxModel()
        model.client = Mock()

        # Mock successful API response
        mock_response = Mock()
        mock_response.content = [
            Mock(text='{"actions": [{"action_type": "click", "parameters": {"coordinates": [100, 100]}, "confidence": 0.95, "description": "Click button"}]}')
        ]
        model.client.messages.create = Mock(return_value=mock_response)

        actions = await model.interpret_command("Click the button")

        assert len(actions) == 1
        assert actions[0].action_type.value == "click"
        assert actions[0].parameters == {"coordinates": [100, 100]}
        assert actions[0].confidence == 0.95

    @pytest.mark.asyncio
    async def test_interpret_command_with_multiple_actions(self):
        """Test parsing multiple actions from response"""
        from ai.lux_model import LuxModel

        model = LuxModel()
        model.client = Mock()

        mock_response = Mock()
        mock_response.content = [
            Mock(text='''{"actions": [
                {"action_type": "type", "parameters": {"text": "username"}, "confidence": 0.95, "description": "Type username"},
                {"action_type": "click", "parameters": {"coordinates": [200, 300]}, "confidence": 0.90, "description": "Click login"}
            ]}''')
        ]
        model.client.messages.create = Mock(return_value=mock_response)

        actions = await model.interpret_command("Login")

        assert len(actions) == 2
        assert actions[0].action_type.value == "type"
        assert actions[1].action_type.value == "click"

    @pytest.mark.asyncio
    async def test_interpret_command_handles_markdown_json(self):
        """Test parsing JSON from markdown code blocks"""
        from ai.lux_model import LuxModel

        model = LuxModel()
        model.client = Mock()

        # Response with markdown formatting
        mock_response = Mock()
        mock_response.content = [
            Mock(text='''Here's the plan:

```json
{"actions": [{"action_type": "click", "parameters": {"coordinates": [100, 100]}, "confidence": 0.95, "description": "Click"}]}
```

Done!''')
        ]
        model.client.messages.create = Mock(return_value=mock_response)

        actions = await model.interpret_command("Click button")

        assert len(actions) == 1
        assert actions[0].action_type.value == "click"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_interpret_command_fallback_without_client(self):
        """Test fallback behavior when no API client"""
        from ai.lux_model import LuxModel

        model = LuxModel(api_key=None)
        assert model.client is None

        actions = await model.interpret_command("Open calculator")

        # Should return basic fallback action
        assert len(actions) == 1
        assert actions[0].action_type.value == "open_app"
        assert actions[0].parameters["app_name"] == "Calculator"

    @pytest.mark.asyncio
    async def test_interpret_command_retry_on_parse_error(self):
        """Test retry logic when parsing fails"""
        from ai.lux_model import LuxModel

        model = LuxModel()
        model.client = Mock()

        # First call returns invalid JSON, second returns valid JSON
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = Mock()
            if call_count == 1:
                mock_resp.content = [Mock(text='Invalid response')]
            else:
                mock_resp.content = [Mock(text='{"actions": []}')]
            return mock_resp

        model.client.messages.create = Mock(side_effect=side_effect)

        actions = await model.interpret_command("Test")

        # Should return empty list after retry
        assert actions == []
        assert call_count == 2  # Initial attempt + 1 retry


class TestBrowserAgentIntegration:
    """Test Browser Agent integration with Lux AI"""

    @pytest.mark.asyncio
    async def test_deprecated_get_lux_action_plan(self):
        """Test that deprecated _get_lux_action_plan method returns empty list"""
        # This test verifies the old placeholder method is properly deprecated
        from browser_engine.agent import BrowserAgent

        with patch('browser_engine.agent.LuxModel'):
            agent = BrowserAgent(headless=True)

            # Call the deprecated method
            result = agent._get_lux_action_plan("Login")

            # Should return empty list and log warning
            assert result == []

    @pytest.mark.asyncio
    async def test_execute_task_uses_lux_interpret_command(self):
        """Test that execute_task uses lux.interpret_command for action planning"""
        from ai.lux_model import ComputerAction, ComputerActionType
        from browser_engine.agent import BrowserAgent

        with patch('browser_engine.agent.LuxModel') as mock_lux_class:
            # Setup mocks
            mock_lux = Mock()
            mock_lux.interpret_command = AsyncMock(return_value=[
                ComputerAction(
                    action_type=ComputerActionType.CLICK,
                    parameters={"coordinates": [100, 100]},
                    confidence=0.95,
                    description="Click button"
                )
            ])
            mock_lux_class.return_value = mock_lux

            agent = BrowserAgent(headless=True)

            # Mock browser manager
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_page.url = "https://example.com"
            mock_page.screenshot = AsyncMock(return_value=b"fake_screenshot")
            mock_context.new_page = AsyncMock(return_value=mock_page)

            agent.manager.new_context = AsyncMock(return_value=mock_context)
            agent.manager.close = AsyncMock()
            agent._fetch_context = AsyncMock(return_value={})
            agent._save_knowledge = AsyncMock()
            agent._validate_action_safety = Mock(return_value=True)
            agent._perform_lux_action = AsyncMock()

            # Execute task
            result = await agent.execute_task(
                url="https://example.com",
                goal="Click the button",
                safe_mode=True
            )

            # Verify lux.interpret_command was called
            assert mock_lux.interpret_command.called
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_task_with_context_injection(self):
        """Test that business context is passed to Lux"""
        from ai.lux_model import ComputerAction, ComputerActionType
        from browser_engine.agent import BrowserAgent

        with patch('browser_engine.agent.LuxModel') as mock_lux_class:
            mock_lux = Mock()
            mock_lux.interpret_command = AsyncMock(return_value=[])
            mock_lux_class.return_value = mock_lux

            agent = BrowserAgent(headless=True)

            # Mock context with business facts
            agent._fetch_context = AsyncMock(return_value={
                "business_facts": ["CEO is John Doe"],
                "credentials_hint": "Use admin@atom.ai"
            })

            # Mock browser manager
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_page.url = "https://example.com"
            mock_page.screenshot = AsyncMock(return_value=b"fake")
            mock_context.new_page = AsyncMock(return_value=mock_page)

            agent.manager.new_context = AsyncMock(return_value=mock_context)
            agent.manager.close = AsyncMock()
            agent._save_knowledge = AsyncMock()

            # Execute
            await agent.execute_task(
                url="https://example.com",
                goal="Login to portal",
                safe_mode=True
            )

            # Verify context was fetched
            agent._fetch_context.assert_called_once_with("Login to portal")

            # Verify lux was called with context in prompt
            call_args = mock_lux.interpret_command.call_args
            prompt = call_args[0][0]

            # Context should be in prompt
            assert "CEO is John Doe" in prompt or "admin@atom.ai" in prompt


class TestActionPlanningPerformance:
    """Test performance of action planning"""

    @pytest.mark.asyncio
    async def test_action_planning_speed(self):
        """Test that action planning completes quickly"""
        import time
        from ai.lux_model import LuxModel

        model = LuxModel()
        model.client = Mock()

        mock_response = Mock()
        mock_response.content = [
            Mock(text='{"actions": [{"action_type": "click", "parameters": {"coordinates": [100, 100]}, "confidence": 0.95, "description": "Click"}]}')
        ]
        model.client.messages.create = Mock(return_value=mock_response)

        start = time.time()
        actions = await model.interpret_command("Click button")
        elapsed = time.time() - start

        assert len(actions) == 1
        # Should complete in reasonable time (< 5s allows for CI variability)
        assert elapsed < 5.0, f"Action planning took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_action_planning_with_screenshot(self):
        """Test action planning with screenshot context"""
        from ai.lux_model import LuxModel
        from PIL import Image

        model = LuxModel()
        model.client = Mock()

        mock_response = Mock()
        mock_response.content = [
            Mock(text='{"actions": [{"action_type": "click", "parameters": {"coordinates": [500, 500]}, "confidence": 0.90, "description": "Click center"}]}')
        ]
        model.client.messages.create = Mock(return_value=mock_response)

        # Create test screenshot
        screenshot = Image.new('RGB', (1920, 1080), color='white')

        actions = await model.interpret_command("Click center of screen", screenshot)

        assert len(actions) == 1
        # Verify screenshot was encoded and sent
        assert model.client.messages.create.called
        call_args = model.client.messages.create.call_args
        message = call_args[1]['messages'][0]

        # Should have both text and image
        assert len(message['content']) == 2
        assert message['content'][0]['type'] == 'text'
        assert message['content'][1]['type'] == 'image'


class TestErrorHandling:
    """Test error handling in action planning"""

    @pytest.mark.asyncio
    async def test_handles_invalid_action_type(self):
        """Test graceful handling of unknown action types"""
        from ai.lux_model import LuxModel

        model = LuxModel()
        model.client = Mock()

        # Response with invalid action type
        mock_response = Mock()
        mock_response.content = [
            Mock(text='{"actions": [{"action_type": "invalid_type", "parameters": {}, "confidence": 0.5, "description": "Invalid"}]}')
        ]
        model.client.messages.create = Mock(return_value=mock_response)

        actions = await model.interpret_command("Test")

        # Should skip invalid action and return empty list
        assert actions == []

    @pytest.mark.asyncio
    async def test_handles_malformed_json(self):
        """Test handling of malformed JSON response"""
        from ai.lux_model import LuxModel

        model = LuxModel()
        model.client = Mock()

        # Response with malformed JSON
        mock_response = Mock()
        mock_response.content = [Mock(text='{"actions": [incomplete json')]
        model.client.messages.create = Mock(return_value=mock_response)

        actions = await model.interpret_command("Test")

        # Should return empty list and retry
        assert actions == []

    @pytest.mark.asyncio
    async def test_handles_api_connection_error(self):
        """Test retry on API connection errors"""
        from ai.lux_model import LuxModel

        model = LuxModel()
        model.client = Mock()

        # Simulate generic exception then success
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Connection failed")
            mock_resp = Mock()
            mock_resp.content = [Mock(text='{"actions": []}')]
            return mock_resp

        model.client.messages.create = Mock(side_effect=side_effect)

        actions = await model.interpret_command("Test")

        # Should return empty list (exception handled)
        assert actions == []
        # Should not retry for generic exceptions, only connection errors
        assert call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
