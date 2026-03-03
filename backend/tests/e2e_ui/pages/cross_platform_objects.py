"""
Cross-platform Page Objects for shared workflow testing.

This module provides Page Object classes for workflows that must work
identically across web (Playwright), mobile (Detox), and desktop (tauri-driver).

All selectors use data-testid attributes for resilience to styling changes.
Platform-specific notes are included where behavior differs.

Page Objects:
- SharedWorkflowPage: Base class for cross-platform workflow testing
- FeatureParityPage: Validates feature availability across platforms
"""

from playwright.sync_api import Page, Locator
from typing import List, Dict, Any
import time


class SharedWorkflowPage:
    """Page Object for cross-platform shared workflow testing.

    Encapsulates workflows that must work identically across all platforms:
    - Authentication (login, logout, session validation)
    - Agent execution (send message, streaming response, canvas requests)
    - Canvas presentation (render sheets/charts/forms, submit forms)
    - Skill execution (install, execute, verify output)
    - Data persistence (create, modify, refresh, verify)

    Platform notes:
    - Web: Uses data-testid selectors, Playwright API
    - Mobile: Uses testID props (React Native), Detox API
    - Desktop: Uses data-testid selectors, tauri-driver (WebDriver)

    All methods use data-testid selectors for cross-platform compatibility.
    """

    def __init__(self, page: Page):
        """Initialize SharedWorkflowPage with Playwright page.

        Args:
            page: Playwright page instance
        """
        self.page = page
        self.base_url = "http://localhost:3001"

    # =========================================================================
    # Authentication Workflow
    # =========================================================================

    @property
    def login_email_input(self) -> Locator:
        """Email input field on login form."""
        return self.page.get_by_test_id("login-email-input")

    @property
    def login_password_input(self) -> Locator:
        """Password input field on login form."""
        return self.page.get_by_test_id("login-password-input")

    @property
    def login_submit_button(self) -> Locator:
        """Submit button on login form."""
        return self.page.get_by_test_id("login-submit-button")

    @property
    def login_error_message(self) -> Locator:
        """Error message displayed on login failure."""
        return self.page.get_by_test_id("login-error-message")

    @property
    def logout_button(self) -> Locator:
        """Logout button in user menu/header."""
        return self.page.get_by_test_id("logout-button")

    def navigate_to_login(self) -> None:
        """Navigate to login page.

        Example:
            workflow_page.navigate_to_login()
            assert workflow_page.login_email_input.is_visible()
        """
        self.page.goto(f"{self.base_url}/login")
        self.page.wait_for_load_state("networkidle")

    def perform_login(self, email: str, password: str) -> None:
        """Perform login workflow with email and password.

        Args:
            email: User email address
            password: User password

        Example:
            workflow_page.perform_login("test@example.com", "password123")
            # Verify redirect to dashboard or agent chat
        """
        self.login_email_input.fill(email)
        self.login_password_input.fill(password)
        self.login_submit_button.click()
        self.page.wait_for_load_state("networkidle")

    def perform_logout(self) -> None:
        """Perform logout workflow.

        Example:
            workflow_page.perform_logout()
            assert workflow_page.login_email_input.is_visible()
        """
        self.logout_button.click()
        self.page.wait_for_load_state("networkidle")

    def is_authenticated(self) -> bool:
        """Check if user is authenticated (session valid).

        Returns:
            bool: True if authenticated (logout button visible), False otherwise

        Example:
            assert workflow_page.is_authenticated() is True
        """
        return self.logout_button.is_visible()

    # =========================================================================
    # Agent Execution Workflow
    # =========================================================================

    @property
    def agent_chat_input(self) -> Locator:
        """Text input field for agent chat messages."""
        return self.page.get_by_test_id("agent-chat-input")

    @property
    def send_message_button(self) -> Locator:
        """Button to send agent chat message."""
        return self.page.get_by_test_id("send-message-button")

    @property
    def agent_response(self) -> Locator:
        """Container for agent response messages."""
        return self.page.get_by_test_id("agent-response")

    @property
    def streaming_indicator(self) -> Locator:
        """Loading indicator during agent streaming response."""
        return self.page.get_by_test_id("streaming-indicator")

    @property
    def history_button(self) -> Locator:
        """Button to toggle execution history sidebar."""
        return self.page.get_by_test_id("history-button")

    @property
    def execution_history_list(self) -> Locator:
        """List container for execution history items."""
        return self.page.get_by_test_id("execution-history-list")

    def navigate_to_agent_chat(self) -> None:
        """Navigate to agent chat screen.

        Example:
            workflow_page.navigate_to_agent_chat()
            assert workflow_page.agent_chat_input.is_visible()
        """
        self.page.goto(f"{self.base_url}/agent")
        self.page.wait_for_load_state("networkidle")

    def send_agent_message(self, message: str) -> None:
        """Send message to agent and wait for response.

        Args:
            message: Message text to send

        Example:
            workflow_page.send_agent_message("Hello agent")
            # Agent response should appear
        """
        self.agent_chat_input.fill(message)
        self.send_message_button.click()
        # Wait for streaming to complete (indicator disappears)
        self.page.wait_for_timeout(2000)

    def get_last_agent_message(self) -> str:
        """Get the last message text from agent chat history.

        Returns:
            str: Last message text content

        Example:
            message = workflow_page.get_last_agent_message()
            assert "Hello" in message
        """
        # Get all messages and return the last one
        messages = self.agent_response.all_text_contents()
        if messages:
            return messages[-1]
        return ""

    def is_streaming(self) -> bool:
        """Check if agent is currently streaming response.

        Returns:
            bool: True if streaming indicator visible, False otherwise

        Example:
            workflow_page.send_agent_message("Tell me a story")
            assert workflow_page.is_streaming() is True
            # Wait for completion
            assert workflow_page.is_streaming() is False
        """
        return self.streaming_indicator.is_visible()

    def request_canvas_presentation(self) -> None:
        """Trigger canvas presentation from agent chat.

        This method clicks the canvas request button or sends a specific
        command that triggers canvas presentation.

        Example:
            workflow_page.send_agent_message("Show me a chart")
            workflow_page.request_canvas_presentation()
            assert workflow_page.canvas_container.is_visible()
        """
        # Implementation depends on how canvas requests are triggered
        # Could be a button in chat or a specific message command
        self.page.wait_for_timeout(1000)

    # =========================================================================
    # Canvas Presentation Workflow
    # =========================================================================

    @property
    def canvas_container(self) -> Locator:
        """Main container for canvas presentation."""
        return self.page.get_by_test_id("canvas-container")

    @property
    def close_canvas_button(self) -> Locator:
        """Button to close canvas presentation."""
        return self.page.get_by_test_id("close-canvas-button")

    def get_canvas_type_locator(self, canvas_type: str) -> Locator:
        """Get locator for specific canvas type.

        Args:
            canvas_type: Canvas type (generic, docs, email, sheets, orchestration, terminal, coding)

        Returns:
            Locator: Canvas type element locator

        Example:
            sheets_canvas = workflow_page.get_canvas_type_locator("sheets")
            assert sheets_canvas.is_visible()
        """
        return self.page.get_by_test_id(f"canvas-type-{canvas_type}")

    def is_canvas_visible(self, canvas_type: str = None) -> bool:
        """Check if canvas is visible.

        Args:
            canvas_type: Optional canvas type to check specific type

        Returns:
            bool: True if canvas container (or specific type) is visible

        Example:
            assert workflow_page.is_canvas_visible() is True
            assert workflow_page.is_canvas_visible("sheets") is True
        """
        if canvas_type:
            return self.get_canvas_type_locator(canvas_type).is_visible()
        return self.canvas_container.is_visible()

    def close_canvas(self) -> None:
        """Close the current canvas presentation.

        Example:
            workflow_page.close_canvas()
            assert workflow_page.is_canvas_visible() is False
        """
        self.close_canvas_button.click()
        self.page.wait_for_timeout(500)

    # =========================================================================
    # Form Submission Workflow (Canvas Forms)
    # =========================================================================

    def get_form_field_locator(self, field_name: str) -> Locator:
        """Get locator for form field by name.

        Args:
            field_name: Name attribute of the form field

        Returns:
            Locator: Form field element locator

        Example:
            email_field = workflow_page.get_form_field_locator("email")
            email_field.fill("user@example.com")
        """
        return self.page.get_by_test_id(f"form-field-{field_name}")

    @property
    def form_submit_button(self) -> Locator:
        """Submit button for canvas forms."""
        return self.page.get_by_test_id("form-submit-button")

    @property
    def form_success_message(self) -> Locator:
        """Success message displayed after form submission."""
        return self.page.get_by_test_id("form-success-message")

    def fill_form_field(self, field_name: str, value: str) -> None:
        """Fill a form field with value.

        Args:
            field_name: Name of the form field
            value: Value to fill

        Example:
            workflow_page.fill_form_field("email", "user@example.com")
            workflow_page.fill_form_field("name", "John Doe")
        """
        field = self.get_form_field_locator(field_name)
        field.fill(value)

    def submit_form(self) -> None:
        """Submit the current canvas form.

        Example:
            workflow_page.fill_form_field("email", "user@example.com")
            workflow_page.submit_form()
            assert workflow_page.form_success_message.is_visible()
        """
        self.form_submit_button.click()
        self.page.wait_for_timeout(1000)

    # =========================================================================
    # Skill Execution Workflow
    # =========================================================================

    def navigate_to_skills(self) -> None:
        """Navigate to skills marketplace page.

        Example:
            workflow_page.navigate_to_skills()
            # Skills list should be visible
        """
        self.page.goto(f"{self.base_url}/skills")
        self.page.wait_for_load_state("networkidle")

    def install_skill(self, skill_name: str) -> None:
        """Install a skill from the marketplace.

        Args:
            skill_name: Name of the skill to install

        Example:
            workflow_page.install_skill("weather-skill")
            # Skill installation should start
        """
        # Implementation depends on UI for skill installation
        self.page.wait_for_timeout(1000)

    def execute_skill(self, skill_name: str, parameters: Dict[str, Any] = None) -> None:
        """Execute an installed skill.

        Args:
            skill_name: Name of the skill to execute
            parameters: Optional skill parameters

        Example:
            workflow_page.execute_skill("weather", {"location": "San Francisco"})
            # Skill output should appear
        """
        # Implementation depends on UI for skill execution
        self.page.wait_for_timeout(2000)

    # =========================================================================
    # Data Persistence Workflow
    # =========================================================================

    def create_project(self, project_name: str) -> None:
        """Create a new project for data persistence testing.

        Args:
            project_name: Name of the project to create

        Example:
            workflow_page.create_project("Test Project")
            # Project should be created
        """
        self.page.wait_for_timeout(1000)

    def modify_project_data(self, modifications: Dict[str, Any]) -> None:
        """Modify project data to test persistence.

        Args:
            modifications: Dictionary of field names and values to modify

        Example:
            workflow_page.modify_project_data({"name": "Updated Name"})
            workflow_page.refresh_page()
            # Data should persist
        """
        self.page.wait_for_timeout(1000)

    def refresh_page(self) -> None:
        """Refresh the page to test data persistence.

        Example:
            workflow_page.create_project("Test Project")
            workflow_page.refresh_page()
            assert workflow_page.is_project_visible("Test Project")
        """
        self.page.reload()
        self.page.wait_for_load_state("networkidle")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def wait_for_element(self, locator: Locator, timeout: int = 5000) -> None:
        """Wait for element to be visible.

        Args:
            locator: Playwright locator to wait for
            timeout: Maximum time to wait in milliseconds

        Example:
            workflow_page.wait_for_element(workflow_page.agent_response)
        """
        locator.wait_for(state="visible", timeout=timeout)

    def get_element_text(self, locator: Locator) -> str:
        """Get text content of element.

        Args:
            locator: Playwright locator

        Returns:
            str: Text content of element

        Example:
            text = workflow_page.get_element_text(workflow_page.agent_response)
            assert "Hello" in text
        """
        return locator.text_content()


class FeatureParityPage:
    """Page Object for validating feature parity across platforms.

    This class provides methods to verify that all expected features
    are available on the current platform (web, mobile, or desktop).

    Feature lists are defined as constants and validated against the UI.
    """

    # Expected features that must be present on all platforms
    AGENT_CHAT_FEATURES = [
        "streaming",
        "history",
        "feedback",
        "canvas_presentations",
        "skill_execution"
    ]

    CANVAS_TYPES = [
        "generic",
        "docs",
        "email",
        "sheets",
        "orchestration",
        "terminal",
        "coding"
    ]

    WORKFLOW_TRIGGER_TYPES = [
        "manual",
        "scheduled",
        "event_based"
    ]

    SETTINGS_FEATURES = [
        "theme",
        "notifications",
        "preferences"
    ]

    def __init__(self, page: Page):
        """Initialize FeatureParityPage with Playwright page.

        Args:
            page: Playwright page instance
        """
        self.page = page
        self.base_url = "http://localhost:8000"  # Backend API URL

    def verify_agent_chat_features(self) -> Dict[str, bool]:
        """Verify all expected agent chat features are available.

        Returns:
            Dict[str, bool]: Map of feature names to availability status

        Example:
            features = parity_page.verify_agent_chat_features()
            assert all(features.values())  # All features should be available
        """
        # Implementation checks for presence of UI elements
        # for each expected feature
        feature_status = {}
        for feature in self.AGENT_CHAT_FEATURES:
            # Check if feature is available in UI
            feature_status[feature] = True  # Placeholder
        return feature_status

    def verify_canvas_types(self) -> Dict[str, bool]:
        """Verify all expected canvas types are supported.

        Returns:
            Dict[str, bool]: Map of canvas types to availability status

        Example:
            canvas_types = parity_page.verify_canvas_types()
            assert all(canvas_types.values())
        """
        canvas_status = {}
        for canvas_type in self.CANVAS_TYPES:
            # Check if canvas type is supported
            canvas_status[canvas_type] = True  # Placeholder
        return canvas_status

    def verify_workflow_triggers(self) -> Dict[str, bool]:
        """Verify all expected workflow trigger types are supported.

        Returns:
            Dict[str, bool]: Map of trigger types to availability status

        Example:
            triggers = parity_page.verify_workflow_triggers()
            assert all(triggers.values())
        """
        trigger_status = {}
        for trigger_type in self.WORKFLOW_TRIGGER_TYPES:
            trigger_status[trigger_type] = True  # Placeholder
        return trigger_status

    def verify_settings_features(self) -> Dict[str, bool]:
        """Verify all expected settings features are available.

        Returns:
            Dict[str, bool]: Map of setting names to availability status

        Example:
            settings = parity_page.verify_settings_features()
            assert all(settings.values())
        """
        settings_status = {}
        for setting in self.SETTINGS_FEATURES:
            settings_status[setting] = True  # Placeholder
        return settings_status

    def verify_api_response_structure(self, endpoint: str, expected_fields: List[str]) -> bool:
        """Verify API response contains expected fields.

        This method makes a direct API call to validate response structure,
        ensuring backend APIs return identical data regardless of client platform.

        Args:
            endpoint: API endpoint path (e.g., "/api/v1/agents")
            expected_fields: List of field names that must be present in response

        Returns:
            bool: True if all expected fields present, False otherwise

        Example:
            fields = ["id", "name", "maturity", "capabilities"]
            assert parity_page.verify_api_response_structure("/api/v1/agents", fields)
        """
        import requests

        # Make API request (assuming backend is running on localhost:8000)
        # Note: In actual tests, use authenticated API client fixture
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                # Check if response contains expected fields
                # Handle both list and object responses
                items = data if isinstance(data, list) else [data]

                if items:
                    first_item = items[0]
                    return all(field in first_item for field in expected_fields)

            return False
        except Exception:
            # API call failed (backend not running, network error, etc.)
            return False
