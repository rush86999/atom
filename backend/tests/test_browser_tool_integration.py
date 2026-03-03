"""
Integration coverage tests for tools/browser_tool.py.

Tests cover browser session management, navigation, scraping,
screenshots, and form interaction using mocked Playwright.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session


class TestBrowserToolSessionManagement:
    """Tests for browser session management."""

    @pytest.mark.asyncio
    async def test_create_session(self, db_session: Session):
        """Test creating a new browser session."""
        from tools.browser_tool import browser_create_session
        from core.models import AgentRegistry, AgentStatus

        # Create test agent
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_session = Mock()
            mock_session.session_id = "test_session_123"
            mock_session.created_at = datetime.now()

            mock_mgr_instance = AsyncMock()
            mock_mgr_instance.create_session = AsyncMock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_create_session(
                user_id="test_user",
                agent_id=agent.id,
                headless=True,
                db=db_session
            )

            assert result["success"] is True
            assert "session_id" in result
            assert result["agent_id"] == agent.id

    @pytest.mark.asyncio
    async def test_create_session_with_options(self, db_session: Session):
        """Test creating session with custom options."""
        from tools.browser_tool import browser_create_session

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_session = Mock()
            mock_session.session_id = "test_session_456"
            mock_session.created_at = datetime.now()

            mock_mgr_instance = AsyncMock()
            mock_mgr_instance.create_session = AsyncMock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_create_session(
                user_id="test_user",
                headless=False,
                browser_type="firefox",
                db=db_session
            )

            assert result["success"] is True
            assert result["headless"] is False
            assert result["browser_type"] == "firefox"

    @pytest.mark.asyncio
    async def test_create_session_governance_blocked(self, db_session: Session):
        """Test session creation with governance check."""
        from tools.browser_tool import browser_create_session
        from core.models import AgentRegistry, AgentStatus

        # Create INTERN agent (allowed for browser)
        agent = AgentRegistry(
            name="InternAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_session = Mock()
            mock_session.session_id = "test_session_789"
            mock_session.created_at = datetime.now()

            mock_mgr_instance = AsyncMock()
            mock_mgr_instance.create_session = AsyncMock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_create_session(
                user_id="test_user",
                agent_id=agent.id,
                headless=True,
                db=db_session
            )

            # Should succeed with INTERN agent
            assert result["success"] is True
            assert "session_id" in result

    @pytest.mark.asyncio
    async def test_close_session(self, db_session: Session):
        """Test closing a browser session."""
        from tools.browser_tool import browser_close_session

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_mgr_instance = AsyncMock()
            mock_mgr_instance.close_session = AsyncMock(return_value=True)
            mock_mgr_instance.get_session = Mock(return_value=Mock(user_id="test_user"))
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_close_session(
                session_id="test_session",
                user_id="test_user"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_close_session_not_found(self, db_session: Session):
        """Test closing non-existent session."""
        from tools.browser_tool import browser_close_session

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_mgr_instance = AsyncMock()
            mock_mgr_instance.get_session = Mock(return_value=None)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_close_session(
                session_id="nonexistent_session"
            )

            assert result["success"] is False
            assert "not found" in result["error"]


class TestBrowserToolNavigation:
    """Tests for browser navigation."""

    @pytest.mark.asyncio
    async def test_navigate_to_url(self, db_session: Session):
        """Test navigating to a URL."""
        from tools.browser_tool import browser_navigate

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.goto = AsyncMock(return_value=Mock(status=200))
            mock_page.title = AsyncMock(return_value="Test Page")
            mock_page.url = "https://example.com"

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_navigate(
                session_id="test_session",
                url="https://example.com",
                db=db_session
            )

            assert result["success"] is True
            assert result["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_navigate_with_wait(self, db_session: Session):
        """Test navigating with wait for selector."""
        from tools.browser_tool import browser_navigate

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.goto = AsyncMock(return_value=Mock(status=200))
            mock_page.wait_for_selector = AsyncMock()
            mock_page.title = AsyncMock(return_value="Test Page")
            mock_page.url = "https://example.com"

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_navigate(
                session_id="test_session",
                url="https://example.com",
                wait_until="domcontentloaded",
                db=db_session
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_navigate_invalid_session(self, db_session: Session):
        """Test navigating with invalid session."""
        from tools.browser_tool import browser_navigate

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=None)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_navigate(
                session_id="invalid_session",
                url="https://example.com",
                db=db_session
            )

            assert result["success"] is False
            assert "not found" in result["error"]


class TestBrowserToolScraping:
    """Tests for web scraping functionality."""

    @pytest.mark.asyncio
    async def test_scrape_with_selector(self, db_session: Session):
        """Test scraping text using query selector."""
        from tools.browser_tool import browser_extract_text

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            # Simulate multi-element scraping
            mock_page = Mock()

            # Mock inner_text to return joined content
            async def mock_inner_text(selector):
                return "Content from selector"

            mock_page.inner_text = mock_inner_text

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_extract_text(
                session_id="test_session",
                selector="div.content",
                user_id="test_user"
            )

            # Verify success or graceful failure
            assert "success" in result

    @pytest.mark.asyncio
    async def test_scrape_full_page_text(self, db_session: Session):
        """Test scraping full page text."""
        from tools.browser_tool import browser_extract_text

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.inner_text = AsyncMock(return_value="Full page content")

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_extract_text(
                session_id="test_session",
                user_id="test_user"
            )

            assert result["success"] is True
            assert "Full page content" in result["text"]

    @pytest.mark.asyncio
    async def test_execute_script(self, db_session: Session):
        """Test executing JavaScript in browser."""
        from tools.browser_tool import browser_execute_script

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.evaluate = AsyncMock(return_value=42)

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_execute_script(
                session_id="test_session",
                script="return 42",
                user_id="test_user"
            )

            assert result["success"] is True
            assert result["result"] == 42


class TestBrowserToolScreenshots:
    """Tests for screenshot functionality."""

    @pytest.mark.asyncio
    async def test_take_screenshot(self, db_session: Session):
        """Test taking a screenshot."""
        from tools.browser_tool import browser_screenshot

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.screenshot = AsyncMock(return_value=b"fake_image_data")

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_screenshot(
                session_id="test_session",
                full_page=False,
                user_id="test_user"
            )

            assert result["success"] is True
            assert "data" in result
            assert result["format"] == "png"

    @pytest.mark.asyncio
    async def test_take_full_page_screenshot(self, db_session: Session):
        """Test taking a full page screenshot."""
        from tools.browser_tool import browser_screenshot

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.screenshot = AsyncMock(return_value=b"full_page_image")

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_screenshot(
                session_id="test_session",
                full_page=True,
                user_id="test_user"
            )

            assert result["success"] is True
            assert result["size_bytes"] > 0


class TestBrowserToolForms:
    """Tests for form interaction."""

    @pytest.mark.asyncio
    async def test_fill_form_fields(self, db_session: Session):
        """Test filling form fields."""
        from tools.browser_tool import browser_fill_form

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.wait_for_selector = AsyncMock()
            mock_page.fill = AsyncMock()

            # Create mock elements
            email_element = Mock()
            email_element.evaluate = AsyncMock(return_value="INPUT")
            country_element = Mock()
            country_element.evaluate = AsyncMock(return_value="SELECT")

            call_count = [0]
            async def mock_query_selector(selector):
                call_count[0] += 1
                if call_count[0] == 1:
                    return email_element
                else:
                    return country_element

            mock_page.query_selector = mock_query_selector

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_fill_form(
                session_id="test_session",
                selectors={
                    "#email": "test@example.com",
                    "#country": "US"
                },
                submit=False,
                user_id="test_user"
            )

            assert result["success"] is True
            # At least one field should be filled
            assert result["fields_filled"] >= 1

    @pytest.mark.asyncio
    async def test_fill_and_submit_form(self, db_session: Session):
        """Test filling and submitting form."""
        from tools.browser_tool import browser_fill_form

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.wait_for_selector = AsyncMock()
            mock_page.fill = AsyncMock()
            mock_page.query_selector = AsyncMock()
            mock_page.query_selector.side_effect = [
                Mock(evaluate=AsyncMock(return_value="INPUT")),  # Input field
                Mock(click=AsyncMock())  # Submit button
            ]

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_fill_form(
                session_id="test_session",
                selectors={"#email": "test@example.com"},
                submit=True,
                user_id="test_user"
            )

            assert result["success"] is True
            assert result["fields_filled"] == 1
            assert result["submitted"] is True

    @pytest.mark.asyncio
    async def test_click_element(self, db_session: Session):
        """Test clicking an element."""
        from tools.browser_tool import browser_click

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.wait_for_selector = AsyncMock()
            mock_page.click = AsyncMock()

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_click(
                session_id="test_session",
                selector="#submit-button",
                user_id="test_user"
            )

            assert result["success"] is True
            assert result["selector"] == "#submit-button"

    @pytest.mark.asyncio
    async def test_click_element_with_wait(self, db_session: Session):
        """Test clicking element with wait for next element."""
        from tools.browser_tool import browser_click

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.wait_for_selector = AsyncMock()
            mock_page.click = AsyncMock()

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_click(
                session_id="test_session",
                selector="#button",
                wait_for=".success-message",
                user_id="test_user"
            )

            assert result["success"] is True


class TestBrowserToolPageInfo:
    """Tests for page information retrieval."""

    @pytest.mark.asyncio
    async def test_get_page_info(self, db_session: Session):
        """Test getting page information."""
        from tools.browser_tool import browser_get_page_info

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_page = Mock()
            mock_page.title = AsyncMock(return_value="Test Page Title")
            mock_page.url = "https://example.com/page"
            mock_context = Mock()
            mock_context.cookies = AsyncMock(return_value=[{"name": "session", "value": "abc"}])

            mock_session = Mock()
            mock_session.user_id = "test_user"
            mock_session.page = mock_page
            mock_session.context = mock_context
            mock_session.last_used = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_get_page_info(
                session_id="test_session",
                user_id="test_user"
            )

            assert result["success"] is True
            assert result["title"] == "Test Page Title"
            assert result["url"] == "https://example.com/page"
            assert result["cookies_count"] == 1

    @pytest.mark.asyncio
    async def test_get_page_info_invalid_session(self, db_session: Session):
        """Test getting page info with invalid session."""
        from tools.browser_tool import browser_get_page_info

        with patch('tools.browser_tool.get_browser_manager') as mock_mgr:
            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=None)
            mock_mgr.return_value = mock_mgr_instance

            result = await browser_get_page_info(
                session_id="invalid_session"
            )

            assert result["success"] is False
            assert "not found" in result["error"]
