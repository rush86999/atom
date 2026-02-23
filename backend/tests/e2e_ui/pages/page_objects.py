"""
Page Object Model classes for E2E UI tests.

Page Objects encapsulate UI interaction logic, making tests more maintainable
and resilient to UI changes. Each page represents a specific screen or view
in the application.

Uses data-testid attributes for selectors (resilient to CSS/class changes).

Page Objects:
- LoginPage: Login form (email, password, submit button)
- DashboardPage: Main dashboard (welcome message, navigation)
- SettingsPage: User settings (theme toggle, notifications)
- ProjectsPage: Projects dashboard (project list, create, edit, delete)
- ChatPage: Agent chat interface (message input, streaming, history)
- ExecutionHistoryPage: Agent execution history (timestamp, status, results)
"""

from playwright.sync_api import Page, Locator
from typing import Optional


class BasePage:
    """Base class for all Page Objects.

    Provides common functionality like waiting for page load and
    checking page visibility.
    """

    def __init__(self, page: Page):
        """Initialize Page Object with Playwright page.

        Args:
            page: Playwright page instance
        """
        self.page = page

    def is_loaded(self) -> bool:
        """Check if page is loaded and visible.

        Returns:
            bool: True if page is loaded, False otherwise

        Example:
            assert dashboard.is_loaded() is True
        """
        # Override in subclasses
        raise NotImplementedError("Subclasses must implement is_loaded()")

    def wait_for_load(self, timeout: int = 5000) -> None:
        """Wait for page to load.

        Args:
            timeout: Maximum time to wait in milliseconds

        Example:
            dashboard.wait_for_load()
        """
        from playwright.sync_api import TimeoutError
        try:
            # Poll is_loaded() until True or timeout
            self.page.wait_for_timeout(100)  # Small initial delay
            start_time = __import__('time').time()
            while __import__('time').time() - start_time < timeout / 1000:
                if self.is_loaded():
                    return
                self.page.wait_for_timeout(100)
            raise TimeoutError(f"Page did not load within {timeout}ms")
        except TimeoutError:
            raise


class LoginPage(BasePage):
    """Page Object for Login page.

    Encapsulates login form interactions:
    - Email input field
    - Password input field
    - Submit button
    - Error messages

    Uses data-testid selectors for resilience.
    """

    # Locators using data-testid attributes
    @property
    def email_input(self) -> Locator:
        """Email input field locator."""
        return self.page.get_by_test_id("login-email-input")

    @property
    def password_input(self) -> Locator:
        """Password input field locator."""
        return self.page.get_by_test_id("login-password-input")

    @property
    def submit_button(self) -> Locator:
        """Login submit button locator."""
        return self.page.get_by_test_id("login-submit-button")

    @property
    def error_message(self) -> Locator:
        """Error message locator (shown on login failure)."""
        return self.page.get_by_test_id("login-error-message")

    @property
    def remember_me_checkbox(self) -> Locator:
        """Remember me checkbox locator."""
        return self.page.get_by_test_id("login-remember-me")

    def is_loaded(self) -> bool:
        """Check if login page is loaded.

        Returns:
            bool: True if email input is visible

        Example:
            assert login_page.is_loaded() is True
        """
        return self.email_input.is_visible()

    def navigate(self) -> None:
        """Navigate to login page.

        Example:
            login_page.navigate()
            assert login_page.is_loaded()
        """
        self.page.goto("http://localhost:3000/login")

    def fill_email(self, email: str) -> None:
        """Fill email input field.

        Args:
            email: Email address to enter

        Example:
            login_page.fill_email("test@example.com")
        """
        self.email_input.fill(email)

    def fill_password(self, password: str) -> None:
        """Fill password input field.

        Args:
            password: Password to enter

        Example:
            login_page.fill_password("MyPassword123!")
        """
        self.password_input.fill(password)

    def click_submit(self) -> None:
        """Click submit button to login.

        Example:
            login_page.click_submit()
            # Waits for navigation to dashboard
        """
        with self.page.expect_navigation(timeout=5000):
            self.submit_button.click()

    def login(self, email: str, password: str) -> None:
        """Fill form and submit login (complete flow).

        This is a convenience method that combines fill_email,
        fill_password, and click_submit.

        Args:
            email: User email
            password: User password

        Example:
            login_page.login("test@example.com", "password123")
            # Logged in and redirected
        """
        self.fill_email(email)
        self.fill_password(password)
        self.click_submit()

    def get_error_text(self) -> Optional[str]:
        """Get error message text if present.

        Returns:
            Optional[str]: Error text or None if no error

        Example:
            error = login_page.get_error_text()
            assert "Invalid credentials" in error
        """
        if self.error_message.is_visible():
            return self.error_message.text_content()
        return None

    def set_remember_me(self, checked: bool = True) -> None:
        """Set remember me checkbox state.

        Args:
            checked: True to check, False to uncheck

        Example:
            login_page.set_remember_me(True)
        """
        if checked:
            self.remember_me_checkbox.check()
        else:
            self.remember_me_checkbox.uncheck()


class DashboardPage(BasePage):
    """Page Object for Dashboard page.

    Encapsulates dashboard interactions:
    - Welcome message
    - Navigation menu
    - Agent cards
    - Quick actions

    Uses data-testid selectors for resilience.
    """

    # Locators
    @property
    def welcome_message(self) -> Locator:
        """Welcome message locator."""
        return self.page.get_by_test_id("dashboard-welcome-message")

    @property
    def navigation_menu(self) -> Locator:
        """Main navigation menu locator."""
        return self.page.get_by_test_id("dashboard-navigation-menu")

    @property
    def agent_cards(self) -> Locator:
        """Agent cards grid locator."""
        return self.page.get_by_test_id("dashboard-agent-cards")

    @property
    def quick_actions(self) -> Locator:
        """Quick actions section locator."""
        return self.page.get_by_test_id("dashboard-quick-actions")

    @property
    def create_agent_button(self) -> Locator:
        """Create new agent button locator."""
        return self.page.get_by_test_id("dashboard-create-agent-button")

    @property
    def user_profile_button(self) -> Locator:
        """User profile menu button locator."""
        return self.page.get_by_test_id("dashboard-user-profile-button")

    @property
    def logout_button(self) -> Locator:
        """Logout button locator (in profile menu)."""
        return self.page.get_by_test_id("dashboard-logout-button")

    def is_loaded(self) -> bool:
        """Check if dashboard is loaded.

        Returns:
            bool: True if welcome message is visible

        Example:
            assert dashboard.is_loaded() is True
        """
        return self.welcome_message.is_visible()

    def navigate(self) -> None:
        """Navigate to dashboard.

        Example:
            dashboard.navigate()
            assert dashboard.is_loaded()
        """
        self.page.goto("http://localhost:3000/dashboard")

    def get_welcome_text(self) -> str:
        """Get welcome message text.

        Returns:
            str: Welcome message

        Example:
            text = dashboard.get_welcome_text()
            assert "Welcome" in text
        """
        return self.welcome_message.text_content()

    def get_agent_count(self) -> int:
        """Get number of agent cards displayed.

        Returns:
            int: Number of agent cards

        Example:
            count = dashboard.get_agent_count()
            assert count > 0
        """
        return self.agent_cards.count()

    def click_create_agent(self) -> None:
        """Click create agent button.

        Example:
            dashboard.click_create_agent()
            # Navigates to agent creation flow
        """
        self.create_agent_button.click()

    def click_user_profile(self) -> None:
        """Click user profile button to open menu.

        Example:
            dashboard.click_user_profile()
            assert dashboard.logout_button.is_visible()
        """
        self.user_profile_button.click()

    def click_logout(self) -> None:
        """Click logout button.

        Note: User profile menu must be open first.

        Example:
            dashboard.click_user_profile()
            dashboard.click_logout()
            # Logged out
        """
        self.logout_button.click()

    def logout(self) -> None:
        """Complete logout flow (open menu, click logout).

        Convenience method that combines menu opening and logout.

        Example:
            dashboard.logout()
            # Logged out and redirected to login
        """
        self.click_user_profile()
        self.click_logout()


class SettingsPage(BasePage):
    """Page Object for Settings page.

    Encapsulates settings interactions:
    - Theme toggle (light/dark mode)
    - Notification settings
    - Account settings
    - Security settings

    Uses data-testid selectors for resilience.
    """

    # Locators
    @property
    def theme_toggle(self) -> Locator:
        """Theme toggle switch locator."""
        return self.page.get_by_test_id("settings-theme-toggle")

    @property
    def theme_label(self) -> Locator:
        """Theme label text locator (shows current theme)."""
        return self.page.get_by_test_id("settings-theme-label")

    @property
    def notifications_section(self) -> Locator:
        """Notifications settings section locator."""
        return self.page.get_by_test_id("settings-notifications-section")

    @property
    def email_notifications_checkbox(self) -> Locator:
        """Email notifications checkbox locator."""
        return self.page.get_by_test_id("settings-email-notifications-checkbox")

    @property
    def push_notifications_checkbox(self) -> Locator:
        """Push notifications checkbox locator."""
        return self.page.get_by_test_id("settings-push-notifications-checkbox")

    @property
    def save_button(self) -> Locator:
        """Save settings button locator."""
        return self.page.get_by_test_id("settings-save-button")

    @property
    def success_message(self) -> Locator:
        """Success message locator (shown after save)."""
        return self.page.get_by_test_id("settings-success-message")

    @property
    def account_section(self) -> Locator:
        """Account settings section locator."""
        return self.page.get_by_test_id("settings-account-section")

    @property
    def security_section(self) -> Locator:
        """Security settings section locator."""
        return self.page.get_by_test_id("settings-security-section")

    def is_loaded(self) -> bool:
        """Check if settings page is loaded.

        Returns:
            bool: True if theme toggle is visible

        Example:
            assert settings.is_loaded() is True
        """
        return self.theme_toggle.is_visible()

    def navigate(self) -> None:
        """Navigate to settings page.

        Example:
            settings.navigate()
            assert settings.is_loaded()
        """
        self.page.goto("http://localhost:3000/settings")

    def get_current_theme(self) -> str:
        """Get current theme from label text.

        Returns:
            str: Current theme ("Light" or "Dark")

        Example:
            theme = settings.get_current_theme()
            assert theme in ["Light", "Dark"]
        """
        return self.theme_label.text_content()

    def set_theme(self, theme: str) -> None:
        """Set theme by clicking toggle if needed.

        Args:
            theme: "light" or "dark"

        Example:
            settings.set_theme("dark")
            assert settings.get_current_theme() == "Dark"
        """
        current = self.get_current_theme().lower()

        # Only click toggle if theme is different
        if (theme == "dark" and current == "light") or \
           (theme == "light" and current == "dark"):
            self.theme_toggle.click()

    def toggle_theme(self) -> None:
        """Toggle theme (light to dark or vice versa).

        Example:
            current = settings.get_current_theme()
            settings.toggle_theme()
            assert settings.get_current_theme() != current
        """
        self.theme_toggle.click()

    def set_email_notifications(self, enabled: bool) -> None:
        """Enable or disable email notifications.

        Args:
            enabled: True to enable, False to disable

        Example:
            settings.set_email_notifications(True)
        """
        if enabled:
            self.email_notifications_checkbox.check()
        else:
            self.email_notifications_checkbox.uncheck()

    def set_push_notifications(self, enabled: bool) -> None:
        """Enable or disable push notifications.

        Args:
            enabled: True to enable, False to disable

        Example:
            settings.set_push_notifications(False)
        """
        if enabled:
            self.push_notifications_checkbox.check()
        else:
            self.push_notifications_checkbox.uncheck()

    def click_save(self) -> None:
        """Click save button to save settings.

        Example:
            settings.click_save()
            assert settings.success_message.is_visible()
        """
        self.save_button.click()

    def save_settings(self) -> None:
        """Save current settings and wait for success message.

        Convenience method that clicks save and waits for confirmation.

        Example:
            settings.set_theme("dark")
            settings.save_settings()
            assert settings.success_message.is_visible()
        """
        self.click_save()
        # Wait for success message
        self.page.wait_for_selector('[data-testid="settings-success-message"]', timeout=3000)

    def get_success_message(self) -> Optional[str]:
        """Get success message text if present.

        Returns:
            Optional[str]: Success text or None

        Example:
            settings.save_settings()
            msg = settings.get_success_message()
            assert "saved" in msg.lower()
        """
        if self.success_message.is_visible():
            return self.success_message.text_content()
        return None


class ChatPage(BasePage):
    """Page Object for Agent Chat interface page.

    Encapsulates chat interactions including:
    - Message input and sending
    - Chat history display
    - Streaming response indicators
    - Agent maturity selection

    Uses data-testid selectors for resilience.
    """

    # Locators using data-testid attributes
    @property
    def chat_container(self) -> Locator:
        """Main chat interface container locator."""
        return self.page.get_by_test_id("chat-container")

    @property
    def chat_input(self) -> Locator:
        """Chat message input field locator."""
        return self.page.get_by_test_id("chat-input")

    @property
    def send_button(self) -> Locator:
        """Send message button locator."""
        return self.page.get_by_test_id("send-button")

    @property
    def message_list(self) -> Locator:
        """Chat history/message list container locator."""
        return self.page.get_by_test_id("message-list")

    @property
    def user_message(self) -> Locator:
        """User message bubble locators."""
        return self.page.get_by_test_id("user-message")

    @property
    def assistant_message(self) -> Locator:
        """Agent/assistant message bubble locators."""
        return self.page.get_by_test_id("assistant-message")

    @property
    def streaming_indicator(self) -> Locator:
        """Streaming/loading state indicator locator."""
        return self.page.get_by_test_id("streaming-indicator")

    @property
    def agent_selector(self) -> Locator:
        """Agent maturity level dropdown selector."""
        return self.page.get_by_test_id("agent-selector")

    @property
    def typing_indicator(self) -> Locator:
        """Typing indicator animation locator."""
        return self.page.get_by_test_id("typing-indicator")

    @property
    def message_timestamp(self) -> Locator:
        """Message timestamp locator."""
        return self.page.get_by_test_id("message-timestamp")

    @property
    def clear_chat_button(self) -> Locator:
        """Clear chat history button locator."""
        return self.page.get_by_test_id("clear-chat-button")

    def is_loaded(self) -> bool:
        """Check if chat interface is loaded and visible.

        Returns:
            bool: True if chat container and input are visible

        Example:
            assert chat_page.is_loaded() is True
        """
        return self.chat_container.is_visible() and self.chat_input.is_visible()

    def navigate(self) -> None:
        """Navigate to chat interface page.

        Example:
            chat_page.navigate()
            assert chat_page.is_loaded()
        """
        self.page.goto("http://localhost:3001/chat")

    def send_message(self, text: str) -> None:
        """Type and send a chat message.

        Args:
            text: Message text to send

        Example:
            chat_page.send_message("Hello, how can you help me?")
        """
        self.chat_input.fill(text)
        self.send_button.click()

    def get_last_message(self) -> str:
        """Get the most recent message text from chat history.

        Returns:
            str: The text content of the last message

        Example:
            last_msg = chat_page.get_last_message()
            assert "response" in last_msg.lower()
        """
        # Get all assistant messages and return the last one
        messages = self.assistant_message.all()
        if messages:
            return messages[-1].text_content()
        return ""

    def get_all_messages(self) -> list[str]:
        """Get all messages from chat history.

        Returns:
            list[str]: List of all message texts in chronological order

        Example:
            messages = chat_page.get_all_messages()
            assert len(messages) > 0
        """
        all_messages = []
        # Get user messages
        for msg in self.user_message.all():
            all_messages.append(("user", msg.text_content()))
        # Get assistant messages
        for msg in self.assistant_message.all():
            all_messages.append(("assistant", msg.text_content()))
        return all_messages

    def get_message_count(self) -> int:
        """Count total messages in chat history.

        Returns:
            int: Total number of messages (user + assistant)

        Example:
            count = chat_page.get_message_count()
            assert count > 0
        """
        return self.user_message.count() + self.assistant_message.count()

    def wait_for_response(self, timeout: int = 5000) -> None:
        """Wait for assistant response to appear.

        Args:
            timeout: Maximum time to wait in milliseconds

        Example:
            chat_page.send_message("Hello")
            chat_page.wait_for_response(timeout=10000)
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        try:
            self.page.wait_for_selector('[data-testid="assistant-message"]', timeout=timeout)
        except PlaywrightTimeoutError:
            raise TimeoutError(f"No assistant response within {timeout}ms")

    def is_streaming(self) -> bool:
        """Check if streaming response is in progress.

        Returns:
            bool: True if streaming indicator is visible

        Example:
            chat_page.send_message("Tell me a story")
            assert chat_page.is_streaming() is True
        """
        return self.streaming_indicator.is_visible()

    def wait_for_streaming_complete(self, timeout: int = 30000) -> None:
        """Wait for streaming response to complete.

        Args:
            timeout: Maximum time to wait in milliseconds

        Example:
            chat_page.send_message("Explain quantum computing")
            chat_page.wait_for_streaming_complete(timeout=60000)
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        try:
            # Wait for streaming indicator to disappear
            self.page.wait_for_selector(
                '[data-testid="streaming-indicator"]',
                state="hidden",
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Streaming did not complete within {timeout}ms")

    def select_agent(self, agent_name: str) -> None:
        """Select agent from dropdown by name.

        Args:
            agent_name: Agent name to select (e.g., "AUTONOMOUS", "SUPERVISED")

        Example:
            chat_page.select_agent("AUTONOMOUS")
        """
        self.agent_selector.select_option(agent_name)

    def get_selected_agent(self) -> str:
        """Get currently selected agent maturity level.

        Returns:
            str: Name of selected agent

        Example:
            agent = chat_page.get_selected_agent()
            assert agent == "AUTONOMOUS"
        """
        return self.agent_selector.input_value()

    def clear_chat(self) -> None:
        """Clear chat history.

        Example:
            chat_page.clear_chat()
            assert chat_page.get_message_count() == 0
        """
        self.clear_chat_button.click()

    def wait_for_message(self, message_text: str, timeout: int = 5000) -> None:
        """Wait for a specific message to appear in chat.

        Args:
            message_text: Text to wait for
            timeout: Maximum time to wait in milliseconds

        Example:
            chat_page.send_message("What is 2+2?")
            chat_page.wait_for_message("4", timeout=5000)
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        try:
            self.page.wait_for_selector(
                f'[data-testid="assistant-message"]:has-text("{message_text}")',
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Message '{message_text}' did not appear within {timeout}ms")

    def get_last_user_message(self) -> str:
        """Get the most recent user message text.

        Returns:
            str: The text content of the last user message

        Example:
            last_user_msg = chat_page.get_last_user_message()
            assert "help" in last_user_msg.lower()
        """
        messages = self.user_message.all()
        if messages:
            return messages[-1].text_content()
        return ""

    def is_typing_indicator_visible(self) -> bool:
        """Check if typing indicator is visible.

        Returns:
            bool: True if typing indicator is visible

        Example:
            chat_page.send_message("Hello")
            assert chat_page.is_typing_indicator_visible() is True
        """
        return self.typing_indicator.is_visible()


class ProjectsPage(BasePage):
    """Page Object for Projects dashboard page.

    Encapsulates project list, create, edit, and delete interactions.

    Uses data-testid selectors for resilience.
    """

    # Locators
    @property
    def projects_list(self) -> Locator:
        """Project list/grid locator."""
        return self.page.get_by_test_id("projects-list")

    @property
    def project_cards(self) -> Locator:
        """Individual project card locators."""
        return self.page.get_by_test_id("project-card")

    @property
    def create_project_button(self) -> Locator:
        """Create project button locator."""
        return self.page.get_by_test_id("create-project-button")

    @property
    def quick_create_button(self) -> Locator:
        """Quick Create button in ProjectCommandCenter."""
        return self.page.get_by_test_id("quick-create-button")

    @property
    def create_modal(self) -> Locator:
        """Create project modal dialog."""
        return self.page.get_by_test_id("create-project-modal")

    @property
    def project_name_input(self) -> Locator:
        """Project name input in create modal."""
        return self.page.get_by_test_id("project-name-input")

    @property
    def project_description_input(self) -> Locator:
        """Project description textarea."""
        return self.page.get_by_test_id("project-description-input")

    @property
    def modal_save_button(self) -> Locator:
        """Save button in create/edit modal."""
        return self.page.get_by_test_id("modal-save-button")

    @property
    def modal_cancel_button(self) -> Locator:
        """Cancel button in create/edit modal."""
        return self.page.get_by_test_id("modal-cancel-button")

    @property
    def delete_confirmation_dialog(self) -> Locator:
        """Delete confirmation dialog."""
        return self.page.get_by_test_id("delete-confirmation-dialog")

    @property
    def confirm_delete_button(self) -> Locator:
        """Confirm delete button."""
        return self.page.get_by_test_id("confirm-delete-button")

    @property
    def cancel_delete_button(self) -> Locator:
        """Cancel delete button."""
        return self.page.get_by_test_id("cancel-delete-button")

    def is_loaded(self) -> bool:
        """Check if projects page is loaded.

        Returns:
            bool: True if projects list is visible

        Example:
            assert projects_page.is_loaded() is True
        """
        # Check for Quick Create button as indicator of page load
        return self.quick_create_button.is_visible()

    def navigate(self) -> None:
        """Navigate to projects dashboard.

        Example:
            projects_page.navigate()
            assert projects_page.is_loaded()
        """
        self.page.goto("http://localhost:3001/dashboards/projects")

    def get_project_count(self) -> int:
        """Get number of projects displayed.

        Returns:
            int: Number of project cards visible

        Example:
            count = projects_page.get_project_count()
            assert count > 0
        """
        return self.project_cards.count()

    def get_project_names(self) -> list[str]:
        """Get list of project names displayed.

        Returns:
            list[str]: List of project names

        Example:
            names = projects_page.get_project_names()
            assert "My Project" in names
        """
        names = []
        cards = self.project_cards.all()
        for card in cards:
            name_el = card.get_by_test_id("project-name")
            if name_el.is_visible():
                names.append(name_el.text_content())
        return names

    def open_create_modal(self) -> None:
        """Open create project modal.

        Example:
            projects_page.open_create_modal()
            assert projects_page.create_modal.is_visible()
        """
        self.quick_create_button.click()
        # Wait for modal animation
        self.page.wait_for_timeout(300)

    def fill_project_form(self, name: str, description: str = "") -> None:
        """Fill project creation form.

        Args:
            name: Project name
            description: Optional project description

        Example:
            projects_page.fill_project_form("My Project", "Description")
        """
        self.project_name_input.fill(name)
        if description:
            self.project_description_input.fill(description)

    def submit_create_form(self) -> None:
        """Submit create project form.

        Example:
            projects_page.submit_create_form()
            # Project created, modal closes
        """
        self.modal_save_button.click()

    def create_project(self, name: str, description: str = "") -> None:
        """Complete project creation flow.

        Convenience method that combines opening modal,
        filling form, and submitting.

        Args:
            name: Project name
            description: Optional project description

        Example:
            projects_page.create_project("My Project", "Description")
            # Project created and visible in list
        """
        self.open_create_modal()
        self.fill_project_form(name, description)
        self.submit_create_form()

    def click_project_action(self, project_name: str, action: str) -> None:
        """Click action button on project card.

        Args:
            project_name: Name of project
            action: Action to click (edit, delete, etc.)

        Example:
            projects_page.click_project_action("My Project", "edit")
        """
        # Generate test-id from project name (lowercase, hyphens)
        project_id = f"project-{project_name.lower().replace(' ', '-')}"
        card = self.page.get_by_test_id(project_id)
        card.get_by_test_id(f"{action}-button").click()

    def edit_project(self, project_name: str, new_name: str, new_description: str = "") -> None:
        """Edit existing project.

        Args:
            project_name: Current project name
            new_name: New project name
            new_description: Optional new description

        Example:
            projects_page.edit_project("Old Name", "New Name", "New desc")
        """
        self.click_project_action(project_name, "edit")
        # Wait for edit modal
        self.page.wait_for_timeout(300)
        # Fill edit form and save
        self.project_name_input.fill(new_name)
        if new_description:
            self.project_description_input.fill(new_description)
        self.modal_save_button.click()

    def delete_project(self, project_name: str, confirm: bool = True) -> None:
        """Delete project with confirmation.

        Args:
            project_name: Name of project to delete
            confirm: True to confirm deletion, False to cancel

        Example:
            projects_page.delete_project("My Project", confirm=True)
        """
        self.click_project_action(project_name, "delete")
        # Wait for confirmation dialog
        self.page.wait_for_timeout(300)

        if self.delete_confirmation_dialog.is_visible():
            if confirm:
                self.confirm_delete_button.click()
            else:
                self.cancel_delete_button.click()


class ExecutionHistoryPage(BasePage):
    """Page Object for Agent Execution History page.

    Encapsulates execution history interactions including:
    - History list display
    - Entry details (timestamp, status, agent name, result)
    - Status filtering
    - Navigation to session details

    Uses data-testid selectors for resilience.
    """

    # Locators using data-testid attributes
    @property
    def history_container(self) -> Locator:
        """History list container locator."""
        return self.page.get_by_test_id("execution-history-container")

    @property
    def history_entry(self) -> Locator:
        """Individual history entry locator."""
        return self.page.get_by_test_id("execution-history-entry")

    @property
    def entry_timestamp(self) -> Locator:
        """Timestamp display locator for history entry."""
        return self.page.get_by_test_id("history-entry-timestamp")

    @property
    def entry_status(self) -> Locator:
        """Status indicator locator (running/completed/failed/blocked)."""
        return self.page.get_by_test_id("history-entry-status")

    @property
    def entry_agent(self) -> Locator:
        """Agent name display locator."""
        return self.page.get_by_test_id("history-entry-agent")

    @property
    def entry_result(self) -> Locator:
        """Result preview text locator."""
        return self.page.get_by_test_id("history-entry-result")

    @property
    def entry_details_link(self) -> Locator:
        """Link to session details page locator."""
        return self.page.get_by_test_id("history-entry-details-link")

    @property
    def filter_status(self) -> Locator:
        """Status filter dropdown locator."""
        return self.page.get_by_test_id("history-status-filter")

    @property
    def empty_history_message(self) -> Locator:
        """Empty state message locator (no history entries)."""
        return self.page.get_by_test_id("empty-history-message")

    @property
    def history_loading_spinner(self) -> Locator:
        """Loading spinner locator while fetching history."""
        return self.page.get_by_test_id("history-loading-spinner")

    def is_loaded(self) -> bool:
        """Check if execution history page is loaded.

        Returns:
            bool: True if history container is visible (or empty message shown)

        Example:
            assert history_page.is_loaded() is True
        """
        return (self.history_container.is_visible() or
                self.empty_history_message.is_visible())

    def navigate(self) -> None:
        """Navigate to execution history page.

        Example:
            history_page.navigate()
            assert history_page.is_loaded()
        """
        self.page.goto("http://localhost:3001/execution-history")
        # Wait for loading to complete
        self.page.wait_for_load_state("networkidle", timeout=5000)

    def get_history_count(self) -> int:
        """Count number of history entries visible.

        Returns:
            int: Number of history entries displayed

        Example:
            count = history_page.get_history_count()
            assert count > 0
        """
        if self.empty_history_message.is_visible():
            return 0
        return self.history_entry.count()

    def get_entry_status(self, entry_index: int) -> str:
        """Get status text for a specific history entry.

        Args:
            entry_index: Zero-based index of history entry

        Returns:
            str: Status text (e.g., "completed", "failed", "running", "blocked")

        Example:
            status = history_page.get_entry_status(0)
            assert status == "completed"
        """
        entries = self.history_entry.all()
        if entry_index >= len(entries):
            raise IndexError(f"Entry index {entry_index} out of range (count: {len(entries)})")
        entry = entries[entry_index]
        return entry.get_by_test_id("history-entry-status").text_content()

    def get_entry_timestamp(self, entry_index: int) -> str:
        """Get timestamp for a specific history entry.

        Args:
            entry_index: Zero-based index of history entry

        Returns:
            str: Timestamp text (ISO format or readable format)

        Example:
            timestamp = history_page.get_entry_timestamp(0)
            assert "2026-02-23" in timestamp
        """
        entries = self.history_entry.all()
        if entry_index >= len(entries):
            raise IndexError(f"Entry index {entry_index} out of range (count: {len(entries)})")
        entry = entries[entry_index]
        return entry.get_by_test_id("history-entry-timestamp").text_content()

    def get_entry_agent(self, entry_index: int) -> str:
        """Get agent name for a specific history entry.

        Args:
            entry_index: Zero-based index of history entry

        Returns:
            str: Agent name

        Example:
            agent = history_page.get_entry_agent(0)
            assert agent == "AUTONOMOUS"
        """
        entries = self.history_entry.all()
        if entry_index >= len(entries):
            raise IndexError(f"Entry index {entry_index} out of range (count: {len(entries)})")
        entry = entries[entry_index]
        return entry.get_by_test_id("history-entry-agent").text_content()

    def get_entry_result(self, entry_index: int) -> str:
        """Get result preview text for a specific history entry.

        Args:
            entry_index: Zero-based index of history entry

        Returns:
            str: Result preview text (truncated if long)

        Example:
            result = history_page.get_entry_result(0)
            assert "success" in result.lower()
        """
        entries = self.history_entry.all()
        if entry_index >= len(entries):
            raise IndexError(f"Entry index {entry_index} out of range (count: {len(entries)})")
        entry = entries[entry_index]
        result_el = entry.get_by_test_id("history-entry-result")
        if result_el.is_visible():
            return result_el.text_content()
        return ""

    def filter_by_status(self, status: str) -> None:
        """Filter history by execution status.

        Args:
            status: Status to filter by (e.g., "completed", "failed", "running", "all")

        Example:
            history_page.filter_by_status("completed")
            assert history_page.get_history_count() > 0
        """
        self.filter_status.select_option(status.lower())
        # Wait for filter to apply
        self.page.wait_for_timeout(500)

    def get_current_filter(self) -> str:
        """Get currently selected status filter.

        Returns:
            str: Current filter value

        Example:
            filter_val = history_page.get_current_filter()
            assert filter_val == "completed"
        """
        return self.filter_status.input_value()

    def click_entry_details(self, entry_index: int) -> None:
        """Click details link to view full session details.

        Args:
            entry_index: Zero-based index of history entry

        Example:
            history_page.click_entry_details(0)
            # Navigates to session details page
        """
        entries = self.history_entry.all()
        if entry_index >= len(entries):
            raise IndexError(f"Entry index {entry_index} out of range (count: {len(entries)})")
        entry = entries[entry_index]
        entry.get_by_test_id("history-entry-details-link").click()

    def wait_for_history_load(self, timeout: int = 5000) -> None:
        """Wait for execution history to load.

        Args:
            timeout: Maximum time to wait in milliseconds

        Example:
            history_page.navigate()
            history_page.wait_for_history_load()
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        try:
            # Wait for loading spinner to disappear
            if self.history_loading_spinner.is_visible():
                self.page.wait_for_selector(
                    '[data-testid="history-loading-spinner"]',
                    state="hidden",
                    timeout=timeout
                )
        except PlaywrightTimeoutError:
            raise TimeoutError(f"History did not load within {timeout}ms")

    def get_all_entry_statuses(self) -> list[str]:
        """Get status for all history entries.

        Returns:
            list[str]: List of status values in order

        Example:
            statuses = history_page.get_all_entry_statuses()
            assert "completed" in statuses
        """
        if self.empty_history_message.is_visible():
            return []
        statuses = []
        entries = self.history_entry.all()
        for entry in entries:
            status_el = entry.get_by_test_id("history-entry-status")
            if status_el.is_visible():
                statuses.append(status_el.text_content())
        return statuses

    def is_empty(self) -> bool:
        """Check if history is empty (no entries).

        Returns:
            bool: True if empty message is visible

        Example:
            assert history_page.is_empty() is False
        """
        return self.empty_history_message.is_visible()


class CanvasHostPage(BasePage):
    """Page Object for Canvas Host component.

    The Canvas Host is an absolute positioned overlay that displays
    canvas presentations (charts, markdown, forms, etc.) triggered
    by agent actions via WebSocket messages.

    Canvas structure (from canvas-host.tsx):
    - Container: absolute positioned div (z-50, 600px width)
    - Header: title, component type badge, version, close button
    - Content: Monaco editor, charts, forms based on component type
    - Footer: history button, preview mode toggle, save button

    Uses CSS selectors (canvas uses absolute positioning, no data-testid).
    """

    # Locators using CSS selectors (canvas is absolute positioned)
    @property
    def canvas_host(self) -> Locator:
        """Main canvas container (absolute positioned div with z-50)."""
        return self.page.locator("div.absolute.top-4.right-4.bottom-4.w-\\[600px\\].bg-white")

    @property
    def canvas_close_button(self) -> Locator:
        """X button to close canvas (top right of header)."""
        return self.page.locator("button:has(svg.lucide-x)")

    @property
    def canvas_title(self) -> Locator:
        """Canvas title display in header (truncated to max-w-[250px])."""
        return self.page.locator("h3.font-semibold.text-sm.truncate")

    @property
    def canvas_component_badge(self) -> Locator:
        """Component type badge (e.g., 'markdown', 'form', 'chart')."""
        return self.page.locator("span.text-\\[8px\\].uppercase")

    @property
    def canvas_version(self) -> Locator:
        """Version number display (format: 'v{number}')."""
        return self.page.locator("span.text-\\[10px\\].font-mono")

    @property
    def canvas_content(self) -> Locator:
        """Canvas content area (Monaco editor, charts, etc.)."""
        return self.page.locator("div.flex-1.overflow-hidden.relative")

    @property
    def save_button(self) -> Locator:
        """Save changes button (for editable canvases)."""
        return self.page.locator("button:has(svg.lucide-save)")

    @property
    def history_button(self) -> Locator:
        """Version history button."""
        return self.page.locator("button:has(svg.lucide-history)")

    @property
    def preview_mode_button(self) -> Locator:
        """Preview/Edit mode toggle (for markdown documents)."""
        return self.page.locator("button:has-text('Preview Mode'), button:has-text('Edit Mode')")

    def is_loaded(self) -> bool:
        """Check if canvas host is visible and loaded.

        Returns:
            bool: True if canvas host container is visible

        Example:
            assert canvas_page.is_loaded() is True
        """
        return self.canvas_host.is_visible()

    def get_title(self) -> str:
        """Get canvas title text.

        Returns:
            str: Canvas title (may be truncated if too long)

        Example:
            title = canvas_page.get_title()
            assert "Sales Data" in title
        """
        return self.canvas_title.text_content()

    def get_component_type(self) -> str:
        """Get component type badge text.

        Returns:
            str: Component type (e.g., "markdown", "form", "chart")

        Example:
            component = canvas_page.get_component_type()
            assert component == "markdown"
        """
        return self.canvas_component_badge.text_content()

    def get_version(self) -> str:
        """Get canvas version number.

        Returns:
            str: Version string (format: "v{number}")

        Example:
            version = canvas_page.get_version()
            assert version == "v1"
        """
        return self.canvas_version.text_content()

    def close_canvas(self) -> None:
        """Click close button to hide canvas.

        Example:
            canvas_page.close_canvas()
            assert canvas_page.is_visible() is False
        """
        self.canvas_close_button.click()

    def is_visible(self) -> bool:
        """Check if canvas is currently displayed.

        Returns:
            bool: True if canvas host is visible

        Example:
            if canvas_page.is_visible():
                canvas_page.close_canvas()
        """
        return self.canvas_host.is_visible()

    def wait_for_canvas_visible(self, timeout: int = 5000) -> None:
        """Wait for canvas to appear.

        Args:
            timeout: Maximum time to wait in milliseconds

        Example:
            canvas_page.wait_for_canvas_visible(timeout=10000)
            assert canvas_page.is_loaded() is True
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        try:
            self.page.wait_for_selector(
                "div.absolute.top-4.right-4.bottom-0.w-\\[600px\\].bg-white",
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Canvas did not appear within {timeout}ms")

    def wait_for_canvas_hidden(self, timeout: int = 5000) -> None:
        """Wait for canvas to disappear.

        Args:
            timeout: Maximum time to wait in milliseconds

        Example:
            canvas_page.close_canvas()
            canvas_page.wait_for_canvas_hidden()
            assert canvas_page.is_visible() is False
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        try:
            self.page.wait_for_selector(
                "div.absolute.top-4.right-4.bottom-0.w-\\[600px\\].bg-white",
                state="hidden",
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Canvas did not hide within {timeout}ms")


class CanvasChartPage(BasePage):
    """Page Object for Canvas Chart presentations.

    Encapsulates chart rendering interactions including:
    - Line charts (timestamp/value data with dots)
    - Bar charts (category/value data with bars)
    - Pie charts (segment data with labels)
    - Chart tooltips, legends, and axes
    - Recharts-specific SVG selectors

    Uses SVG-specific selectors for Recharts components.
    """

    # Locators using Recharts-specific CSS selectors
    @property
    def chart_container(self) -> Locator:
        """Recharts ResponsiveContainer wrapper locator."""
        return self.page.locator(".recharts-wrapper").or_(
            self.page.locator("[class*=\"recharts\"]")
        )

    @property
    def line_chart_svg(self) -> Locator:
        """SVG element for line charts locator."""
        return self.page.locator("svg.recharts-line-chart").or_(
            self.page.locator(".recharts-line")
        )

    @property
    def bar_chart_svg(self) -> Locator:
        """SVG element for bar charts locator."""
        return self.page.locator("svg.recharts-bar-chart").or_(
            self.page.locator(".recharts-bar")
        )

    @property
    def pie_chart_svg(self) -> Locator:
        """SVG element for pie charts locator."""
        return self.page.locator("svg.recharts-pie-chart").or_(
            self.page.locator(".recharts-pie")
        )

    @property
    def chart_title(self) -> Locator:
        """Chart title element locator (h4 tag)."""
        return self.page.locator("h4")

    @property
    def chart_tooltip(self) -> Locator:
        """Tooltip element locator (visible on hover)."""
        return self.page.locator(".recharts-tooltip-wrapper").or_(
            self.page.locator(".recharts-tooltip-content")
        )

    @property
    def chart_legend(self) -> Locator:
        """Legend container locator."""
        return self.page.locator(".recharts-legend-wrapper").or_(
            self.page.locator(".recharts-legend-item")
        )

    @property
    def chart_x_axis(self) -> Locator:
        """XAxis element with labels locator."""
        return self.page.locator(".recharts-xAxis").or_(
            self.page.locator("text[data-offset]")  # Recharts axis labels
        )

    @property
    def chart_y_axis(self) -> Locator:
        """YAxis element with labels locator."""
        return self.page.locator(".recharts-yAxis")

    @property
    def data_points(self) -> Locator:
        """Individual data point elements locator (dots, bars, slices)."""
        return self.page.locator(".recharts-dot, .recharts-bar-rectangle, .recharts-pie-sector")

    @property
    def line_dots(self) -> Locator:
        """Line chart dot elements locator."""
        return self.page.locator(".recharts-dot").or_(
            self.page.locator("circle.recharts-dot")
        )

    @property
    def bar_rectangles(self) -> Locator:
        """Bar chart rectangle elements locator."""
        return self.page.locator(".recharts-bar-rectangle").or_(
            self.page.locator("path.recharts-bar")
        )

    @property
    def pie_sectors(self) -> Locator:
        """Pie chart sector elements locator."""
        return self.page.locator(".recharts-pie-sector").or_(
            self.page.locator("path.recharts-pie")
        )

    @property
    def grid_lines(self) -> Locator:
        """CartesianGrid lines locator."""
        return self.page.locator(".recharts-cartesian-grid").or_(
            self.page.locator("line.recharts-cartesian-grid-line")
        )

    @property
    def chart_labels(self) -> Locator:
        """Chart labels (for pie charts) locator."""
        return self.page.locator("text.recharts-text").or_(
            self.page.locator(".recharts-label")
        )

    def is_loaded(self) -> bool:
        """Check if any chart is visible.

        Returns:
            bool: True if any chart SVG is visible

        Example:
            assert chart_page.is_loaded() is True
        """
        return (self.line_chart_svg.is_visible() or
                self.bar_chart_svg.is_visible() or
                self.pie_chart_svg.is_visible())

    def get_chart_type(self) -> str:
        """Detect chart type (line, bar, pie).

        Returns:
            str: Chart type ("line", "bar", "pie", or "unknown")

        Example:
            chart_type = chart_page.get_chart_type()
            assert chart_type == "line"
        """
        if self.line_chart_svg.is_visible():
            return "line"
        elif self.bar_chart_svg.is_visible():
            return "bar"
        elif self.pie_chart_svg.is_visible():
            return "pie"
        return "unknown"

    def get_title(self) -> str:
        """Get chart title text.

        Returns:
            str: Chart title or empty string if not found

        Example:
            title = chart_page.get_title()
            assert "Sales" in title
        """
        if self.chart_title.is_visible():
            return self.chart_title.text_content()
        return ""

    def get_data_point_count(self) -> int:
        """Count visible data points.

        Returns:
            int: Number of visible data points

        Example:
            count = chart_page.get_data_point_count()
            assert count == 5
        """
        chart_type = self.get_chart_type()
        if chart_type == "line":
            return self.line_dots.count()
        elif chart_type == "bar":
            return self.bar_rectangles.count()
        elif chart_type == "pie":
            return self.pie_sectors.count()
        return 0

    def get_x_axis_label(self) -> str:
        """Get X axis label text.

        Returns:
            str: X axis label or empty string

        Example:
            label = chart_page.get_x_axis_label()
            assert "Time" in label
        """
        # X-axis labels are typically text elements in Recharts
        labels = self.chart_x_axis.all()
        if labels:
            # First label is usually the axis name
            return labels[0].text_content() if labels[0].is_visible() else ""
        return ""

    def get_y_axis_label(self) -> str:
        """Get Y axis label text.

        Returns:
            str: Y axis label or empty string

        Example:
            label = chart_page.get_y_axis_label()
            assert "Value" in label
        """
        if self.chart_y_axis.is_visible():
            return self.chart_y_axis.text_content()
        return ""

    def hover_data_point(self, index: int) -> None:
        """Hover over data point to show tooltip.

        Args:
            index: Zero-based index of data point to hover

        Example:
            chart_page.hover_data_point(0)
            assert chart_page.chart_tooltip.is_visible()
        """
        chart_type = self.get_chart_type()
        if chart_type == "line":
            dots = self.line_dots.all()
            if index < len(dots):
                dots[index].hover()
        elif chart_type == "bar":
            bars = self.bar_rectangles.all()
            if index < len(bars):
                bars[index].hover()
        elif chart_type == "pie":
            sectors = self.pie_sectors.all()
            if index < len(sectors):
                sectors[index].hover()

    def get_tooltip_text(self) -> str:
        """Get tooltip content if visible.

        Returns:
            str: Tooltip text or empty string if not visible

        Example:
            chart_page.hover_data_point(0)
            tooltip = chart_page.get_tooltip_text()
            assert "100" in tooltip
        """
        if self.chart_tooltip.is_visible():
            return self.chart_tooltip.text_content()
        return ""

    def has_legend(self) -> bool:
        """Check if legend is displayed.

        Returns:
            bool: True if legend is visible

        Example:
            assert chart_page.has_legend() is True
        """
        return self.chart_legend.is_visible()

    def get_legend_items(self) -> list[str]:
        """Get legend item labels.

        Returns:
            list[str]: List of legend item names

        Example:
            items = chart_page.get_legend_items()
            assert "Series 1" in items
        """
        items = []
        legend_elements = self.chart_legend.all()
        for legend in legend_elements:
            text = legend.text_content()
            if text:
                items.append(text)
        return items

    def get_chart_colors(self) -> list[str]:
        """Extract chart colors from SVG.

        Returns:
            list[str]: List of color values (stroke, fill)

        Example:
            colors = chart_page.get_chart_colors()
            assert "#8884d8" in colors
        """
        colors = []
        chart_type = self.get_chart_type()

        if chart_type == "line":
            # Line charts use stroke
            lines = self.page.locator(".recharts-line").all()
            for line in lines:
                stroke = line.get_attribute("stroke")
                if stroke:
                    colors.append(stroke)
        elif chart_type == "bar":
            # Bar charts use fill
            bars = self.bar_rectangles.all()
            for bar in bars:
                fill = bar.get_attribute("fill")
                if fill:
                    colors.append(fill)
        elif chart_type == "pie":
            # Pie charts use fill on sectors
            sectors = self.pie_sectors.all()
            for sector in sectors:
                fill = sector.get_attribute("fill")
                if fill:
                    colors.append(fill)

        return colors

    def verify_line_chart_data(self, expected_data: list) -> bool:
        """Verify line chart data points match expected values.

        Args:
            expected_data: List of expected values [value1, value2, ...]

        Returns:
            bool: True if data point count matches

        Example:
            assert chart_page.verify_line_chart_data([10, 20, 30])
        """
        dot_count = self.line_dots.count()
        return dot_count == len(expected_data)

    def verify_bar_chart_data(self, expected_data: list) -> bool:
        """Verify bar chart data points match expected values.

        Args:
            expected_data: List of expected category-value dicts

        Returns:
            bool: True if bar count matches

        Example:
            assert chart_page.verify_bar_chart_data([
                {"name": "A", "value": 10},
                {"name": "B", "value": 20}
            ])
        """
        bar_count = self.bar_rectangles.count()
        return bar_count == len(expected_data)

    def verify_pie_chart_data(self, expected_data: list) -> bool:
        """Verify pie chart segments match expected values.

        Args:
            expected_data: List of expected segment-value dicts

        Returns:
            bool: True if segment count matches

        Example:
            assert chart_page.verify_pie_chart_data([
                {"name": "A", "value": 30},
                {"name": "B", "value": 70}
            ])
        """
        sector_count = self.pie_sectors.count()
        return sector_count == len(expected_data)

    def wait_for_chart_render(self, timeout: int = 3000) -> None:
        """Wait for chart to finish rendering.

        Args:
            timeout: Maximum time to wait in milliseconds

        Example:
            chart_page.wait_for_chart_render(timeout=5000)
            assert chart_page.is_loaded()
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        try:
            # Wait for any chart SVG to be visible
            self.page.wait_for_selector(
                ".recharts-wrapper, .recharts-line-chart, .recharts-bar-chart, .recharts-pie-chart",
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Chart did not render within {timeout}ms")

    def get_pie_labels(self) -> list[str]:
        """Get labels from pie chart segments.

        Returns:
            list[str]: List of label text from pie segments

        Example:
            labels = chart_page.get_pie_labels()
            assert "Category A: 100" in labels
        """
        labels = []
        label_elements = self.chart_labels.all()
        for label in label_elements:
            text = label.text_content()
            if text and ":" in text:  # Pie labels show "name: value"
                labels.append(text)
        return labels


class SkillsMarketplacePage(BasePage):
    """Page Object for Skills Marketplace page.

    Encapsulates marketplace browsing interactions including:
    - Skill search and filtering (query, category, skill_type)
    - Skill card display (name, description, category, rating, author)
    - Pagination controls (next, prev, page indicator)
    - Empty state handling
    - Skill installation from marketplace

    Uses data-testid selectors for resilience (check frontend for test-id attributes).

    Marketplace API:
    - GET /api/skills/list with query, category, skill_type, page, page_size params
    - SkillMarketplaceService.search_skills() provides PostgreSQL full-text search
    - Categories: data_processing, automation, integration, productivity, utilities, developer_tools
    - Skill types: prompt_only, python_code, nodejs
    - Pagination: default page_size=20
    """

    # Locators using data-testid attributes (update when frontend adds test-ids)
    @property
    def marketplace_container(self) -> Locator:
        """Main marketplace container div."""
        return self.page.get_by_test_id("marketplace-container").or_(
            self.page.locator("div[class*=\"marketplace\"], div[class*=\"skills-list\"]")
        )

    @property
    def search_input(self) -> Locator:
        """Search text input field locator."""
        return self.page.get_by_test_id("marketplace-search-input").or_(
            self.page.locator("input[type=\"search\"], input[placeholder*=\"search\" i]")
        )

    @property
    def search_button(self) -> Locator:
        """Search submit button locator."""
        return self.page.get_by_test_id("marketplace-search-button").or_(
            self.page.locator("button:has-text(\"Search\"), button:has(svg.lucide-search)")
        )

    @property
    def category_filter(self) -> Locator:
        """Category dropdown/selector locator."""
        return self.page.get_by_test_id("marketplace-category-filter").or_(
            self.page.locator("select[name=\"category\"], select[placeholder*=\"category\" i]")
        )

    @property
    def skill_type_filter(self) -> Locator:
        """Skill type filter locator (prompt_only, python_code)."""
        return self.page.get_by_test_id("marketplace-skill-type-filter").or_(
            self.page.locator("select[name=\"skill_type\"], select[placeholder*=\"type\" i]")
        )

    @property
    def skill_cards(self) -> Locator:
        """Individual skill card elements locator."""
        return self.page.get_by_test_id("skill-card").or_(
            self.page.locator("div[class*=\"skill-card\"], div[class*=\"skill-item\"]")
        )

    @property
    def skill_card_name(self) -> Locator:
        """Skill name display on card locator."""
        return self.page.get_by_test_id("skill-card-name").or_(
            self.page.locator("h3[class*=\"skill-name\"], h4[class*=\"skill-name\"]")
        )

    @property
    def skill_card_description(self) -> Locator:
        """Skill description text locator."""
        return self.page.get_by_test_id("skill-card-description").or_(
            self.page.locator("p[class*=\"skill-description\"]")
        )

    @property
    def skill_card_category(self) -> Locator:
        """Category badge on card locator."""
        return self.page.get_by_test_id("skill-card-category").or_(
            self.page.locator("span[class*=\"category\"], span[class*=\"badge\"]")
        )

    @property
    def skill_card_rating(self) -> Locator:
        """Star rating display locator."""
        return self.page.get_by_test_id("skill-card-rating").or_(
            self.page.locator("div[class*=\"rating\"], span[class*=\"star\"]")
        )

    @property
    def skill_card_author(self) -> Locator:
        """Author name display locator."""
        return self.page.get_by_test_id("skill-card-author").or_(
            self.page.locator("span[class*=\"author\"], p[class*=\"author\"]")
        )

    @property
    def skill_card_install_button(self) -> Locator:
        """Install button on skill card locator."""
        return self.page.get_by_test_id("skill-card-install-button").or_(
            self.page.locator("button:has-text(\"Install\"), button:has(svg.lucide-download)")
        )

    @property
    def pagination_container(self) -> Locator:
        """Pagination controls container locator."""
        return self.page.get_by_test_id("marketplace-pagination").or_(
            self.page.locator("div[class*=\"pagination\"], nav[class*=\"pagination\"]")
        )

    @property
    def next_page_button(self) -> Locator:
        """Next page button locator."""
        return self.page.get_by_test_id("marketplace-next-page").or_(
            self.page.locator("button[aria-label=\"Next\"], button:has-text(\"Next\"), button:has(svg.lucide-chevron-right)")
        )

    @property
    def prev_page_button(self) -> Locator:
        """Previous page button locator."""
        return self.page.get_by_test_id("marketplace-prev-page").or_(
            self.page.locator("button[aria-label=\"Previous\"], button:has-text(\"Prev\"), button:has(svg.lucide-chevron-left)")
        )

    @property
    def page_indicator(self) -> Locator:
        """Current page indicator locator."""
        return self.page.get_by_test_id("marketplace-page-indicator").or_(
            self.page.locator("span[class*=\"page-indicator\"], span[class*=\"current-page\"]")
        )

    @property
    def empty_state(self) -> Locator:
        """Empty state message locator (when no skills found)."""
        return self.page.get_by_test_id("marketplace-empty-state").or_(
            self.page.locator("div[class*=\"empty\"], div[class*=\"no-results\"]")
        )

    @property
    def loading_spinner(self) -> Locator:
        """Loading state indicator locator."""
        return self.page.get_by_test_id("marketplace-loading").or_(
            self.page.locator("div[class*=\"loading\"], div[class*=\"spinner\"], span[class*=\"loading\"]")
        )

    def is_loaded(self) -> bool:
        """Check if marketplace page is loaded and visible.

        Returns:
            bool: True if marketplace container is visible

        Example:
            assert marketplace.is_loaded() is True
        """
        return (self.marketplace_container.is_visible() or
                self.empty_state.is_visible())

    def navigate(self) -> None:
        """Navigate to skills marketplace page.

        Example:
            marketplace.navigate()
            assert marketplace.is_loaded()
        """
        self.page.goto("http://localhost:3001/marketplace")

    def search(self, query: str) -> None:
        """Enter search query and submit.

        Args:
            query: Search query text

        Example:
            marketplace.search("data processing")
            # Search results updated
        """
        self.search_input.fill(query)
        if self.search_button.is_visible():
            self.search_button.click()
        else:
            # Trigger search via Enter key if no button
            self.search_input.press("Enter")

    def select_category(self, category: str) -> None:
        """Select category filter.

        Args:
            category: Category name (e.g., "data_processing", "automation")

        Example:
            marketplace.select_category("data_processing")
        """
        if self.category_filter.is_visible():
            self.category_filter.select_option(category)

    def select_skill_type(self, skill_type: str) -> None:
        """Select skill type filter.

        Args:
            skill_type: Skill type ("prompt_only", "python_code", "nodejs")

        Example:
            marketplace.select_skill_type("python_code")
        """
        if self.skill_type_filter.is_visible():
            self.skill_type_filter.select_option(skill_type)

    def get_skill_count(self) -> int:
        """Get number of skill cards displayed.

        Returns:
            int: Number of skill cards visible (0 if empty state shown)

        Example:
            count = marketplace.get_skill_count()
            assert count > 0
        """
        if self.is_empty_state_visible():
            return 0
        return self.skill_cards.count()

    def get_skill_names(self) -> list[str]:
        """Get list of displayed skill names.

        Returns:
            list[str]: List of skill names in order

        Example:
            names = marketplace.get_skill_names()
            assert "DataProcessor" in names
        """
        names = []
        cards = self.skill_cards.all()
        for card in cards:
            name_el = card.locator("h3, h4").first
            if name_el.is_visible():
                names.append(name_el.text_content())
        return names

    def get_skill_card_info(self, index: int) -> dict:
        """Get skill details at specific index.

        Args:
            index: Zero-based index of skill card

        Returns:
            dict: Skill details (name, description, category, rating, author)

        Example:
            info = marketplace.get_skill_card_info(0)
            assert info["category"] == "data_processing"
        """
        cards = self.skill_cards.all()
        if index >= len(cards):
            raise IndexError(f"Skill index {index} out of range (count: {len(cards)})")

        card = cards[index]

        # Extract skill information from card
        info = {}

        # Name
        name_el = card.locator("h3, h4").first
        if name_el.is_visible():
            info["name"] = name_el.text_content()

        # Description
        desc_el = card.locator("p[class*=\"description\"], p").first
        if desc_el.is_visible():
            info["description"] = desc_el.text_content()

        # Category (from badge)
        category_el = card.locator("span[class*=\"category\"], span[class*=\"badge\"]").first
        if category_el.is_visible():
            info["category"] = category_el.text_content()

        # Rating (extract from stars or text)
        rating_el = card.locator("div[class*=\"rating\"], span[class*=\"rating\"]").first
        if rating_el.is_visible():
            info["rating"] = rating_el.text_content()

        # Author
        author_el = card.locator("span[class*=\"author\"], p[class*=\"author\"]").first
        if author_el.is_visible():
            info["author"] = author_el.text_content()

        return info

    def click_skill_install(self, index: int) -> None:
        """Click install button on skill card.

        Args:
            index: Zero-based index of skill card

        Example:
            marketplace.click_skill_install(0)
            # Installation started
        """
        cards = self.skill_cards.all()
        if index >= len(cards):
            raise IndexError(f"Skill index {index} out of range (count: {len(cards)})")

        card = cards[index]
        install_btn = card.locator("button:has-text(\"Install\"), button:has(svg.lucide-download)").first
        if install_btn.is_visible():
            install_btn.click()

    def click_next_page(self) -> None:
        """Navigate to next page.

        Example:
            marketplace.click_next_page()
            # Moved to next page of results
        """
        if self.next_page_button.is_visible() and not self.next_page_button.is_disabled():
            self.next_page_button.click()

    def click_prev_page(self) -> None:
        """Navigate to previous page.

        Example:
            marketplace.click_prev_page()
            # Moved to previous page of results
        """
        if self.prev_page_button.is_visible() and not self.prev_page_button.is_disabled():
            self.prev_page_button.click()

    def get_current_page(self) -> int:
        """Get current page number.

        Returns:
            int: Current page number (1-based)

        Example:
            page = marketplace.get_current_page()
            assert page == 1
        """
        if self.page_indicator.is_visible():
            text = self.page_indicator.text_content()
            # Extract page number from text like "Page 1 of 5" or "1 / 5"
            import re
            match = re.search(r"\d+", text)
            if match:
                return int(match.group())
        return 1  # Default to page 1

    def is_empty_state_visible(self) -> bool:
        """Check if empty state is shown.

        Returns:
            bool: True if empty state message is visible

        Example:
            assert marketplace.is_empty_state_visible() is True
        """
        return self.empty_state.is_visible()

    def wait_for_skills_load(self, timeout: int = 5000) -> None:
        """Wait for skill cards to load.

        Args:
            timeout: Maximum time to wait in milliseconds

        Example:
            marketplace.navigate()
            marketplace.wait_for_skills_load(timeout=10000)
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        try:
            # Wait for loading spinner to disappear and skills to appear
            if self.loading_spinner.is_visible():
                self.page.wait_for_selector(
                    "div[class*=\"loading\"], div[class*=\"spinner\"]",
                    state="hidden",
                    timeout=timeout
                )
            # Wait for skill cards or empty state
            self.page.wait_for_selector(
                "div[class*=\"skill-card\"], div[class*=\"empty\"], div[class*=\"no-results\"]",
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Skills did not load within {timeout}ms")


class CanvasFormPage(BasePage):
    """Page Object for Canvas Form presentations.

    Encapsulates form interaction within canvas including:
    - Form field rendering (text, email, number, select, checkbox)
    - Field validation (required, pattern, min/max)
    - Form submission and success/error feedback
    - Form state API access (window.atom.canvas.getState)

    Uses name attribute selectors for fields (most reliable).

    Form validation behavior:
    - Required fields show asterisk (*) and error if empty
    - Pattern validation uses regex (e.g., email format)
    - Number fields validate min/max values
    - Errors display with AlertCircle icon below field
    - Submit button disables during submission ("Submitting...")
    - Success message shows with Check icon after submission
    """

    # Locators using CSS selectors and name attributes
    @property
    def form_container(self) -> Locator:
        """Form container div (within canvas content)."""
        return self.page.locator("form.space-y-4")

    @property
    def form_title(self) -> Locator:
        """Form title element (h3 tag)."""
        return self.page.locator("h3.text-sm.font-semibold")

    @property
    def form_field(self) -> Locator:
        """Generic form field locator (use with filter)."""
        return self.page.locator("input, select")

    @property
    def form_input_text(self) -> Locator:
        """Text input field locator."""
        return self.page.locator("input[type=\"text\"]")

    @property
    def form_input_email(self) -> Locator:
        """Email input field locator."""
        return self.page.locator("input[type=\"email\"]")

    @property
    def form_input_number(self) -> Locator:
        """Number input field locator."""
        return self.page.locator("input[type=\"number\"]")

    @property
    def form_select(self) -> Locator:
        """Select dropdown field locator."""
        return self.page.locator("select")

    @property
    def form_checkbox(self) -> Locator:
        """Checkbox field locator."""
        return self.page.locator("input[type=\"checkbox\"]")

    @property
    def form_submit_button(self) -> Locator:
        """Submit button locator."""
        return self.page.locator("button[type=\"submit\"]")

    @property
    def form_error_message(self) -> Locator:
        """Field-level error message (with AlertCircle icon)."""
        return self.page.locator("div.flex.items-center.text-xs.text-red-500")

    @property
    def form_success_message(self) -> Locator:
        """Success message (with Check icon)."""
        return self.page.locator("div.flex.items-center.justify-center.p-8.text-green-600")

    @property
    def form_label(self) -> Locator:
        """Field label element locator."""
        return self.page.locator("label.text-xs.font-medium")

    @property
    def required_indicator(self) -> Locator:
        """Required field asterisk (*) indicator."""
        return self.page.locator("span.text-red-500.ml-1")

    def is_loaded(self) -> bool:
        """Check if form is visible and loaded.

        Returns:
            bool: True if form container is visible

        Example:
            assert form_page.is_loaded() is True
        """
        return self.form_container.is_visible()

    def get_title(self) -> str:
        """Get form title text.

        Returns:
            str: Form title or empty string if not found

        Example:
            title = form_page.get_title()
            assert "User Information" in title
        """
        if self.form_title.is_visible():
            return self.form_title.text_content()
        return ""

    def get_field_count(self) -> int:
        """Count total form fields.

        Returns:
            int: Number of form fields (inputs, selects, checkboxes)

        Example:
            count = form_page.get_field_count()
            assert count == 5
        """
        return self.form_field.count()

    def fill_text_field(self, name: str, value: str) -> None:
        """Fill a text input field by name attribute.

        Args:
            name: Field name attribute value
            value: Text value to enter

        Example:
            form_page.fill_text_field("full_name", "John Doe")
        """
        field = self.page.locator(f"input[name=\"{name}\"][type=\"text\"]")
        field.fill(value)

    def fill_email_field(self, name: str, value: str) -> None:
        """Fill an email input field by name attribute.

        Args:
            name: Field name attribute value
            value: Email address to enter

        Example:
            form_page.fill_email_field("email", "user@example.com")
        """
        field = self.page.locator(f"input[name=\"{name}\"][type=\"email\"]")
        field.fill(value)

    def fill_number_field(self, name: str, value: float) -> None:
        """Fill a number input field by name attribute.

        Args:
            name: Field name attribute value
            value: Numeric value to enter

        Example:
            form_page.fill_number_field("age", 25)
        """
        field = self.page.locator(f"input[name=\"{name}\"][type=\"number\"]")
        field.fill(str(value))

    def select_option(self, name: str, value: str) -> None:
        """Select an option from dropdown by name attribute.

        Args:
            name: Field name attribute value
            value: Option value to select

        Example:
            form_page.select_option("country", "US")
        """
        dropdown = self.page.locator(f"select[name=\"{name}\"]")
        dropdown.select_option(value)

    def set_checkbox(self, name: str, checked: bool) -> None:
        """Set checkbox state by name attribute.

        Args:
            name: Field name attribute value
            checked: True to check, False to uncheck

        Example:
            form_page.set_checkbox("agree_terms", True)
        """
        checkbox = self.page.locator(f"input[name=\"{name}\"][type=\"checkbox\"]")
        if checked:
            checkbox.check()
        else:
            checkbox.uncheck()

    def get_field_value(self, name: str) -> str:
        """Get current value of a field by name attribute.

        Args:
            name: Field name attribute value

        Returns:
            str: Current field value (empty string if not found)

        Example:
            value = form_page.get_field_value("email")
            assert "@" in value
        """
        # Try input fields first
        input_field = self.page.locator(f"input[name=\"{name}\"]")
        if input_field.is_visible():
            return input_field.input_value()

        # Try select fields
        select_field = self.page.locator(f"select[name=\"{name}\"]")
        if select_field.is_visible():
            return select_field.input_value()

        # Try checkbox fields
        checkbox = self.page.locator(f"input[name=\"{name}\"][type=\"checkbox\"]")
        if checkbox.is_visible():
            return "checked" if checkbox.is_checked() else "unchecked"

        return ""

    def get_field_error(self, name: str) -> str:
        """Get error message for a specific field.

        Args:
            name: Field name attribute value

        Returns:
            str: Error message or empty string if no error

        Example:
            error = form_page.get_field_error("email")
            assert "invalid" in error.lower()
        """
        # Find the field's parent container
        field = self.page.locator(f"input[name=\"{name}\"], select[name=\"{name}\"]")
        if field.is_visible():
            # Look for error message in same container
            container = field.locator("xpath=../..")
            error_el = container.locator("div.flex.items-center.text-xs.text-red-500")
            if error_el.is_visible():
                return error_el.text_content()
        return ""

    def has_field_error(self, name: str) -> bool:
        """Check if a field has validation error.

        Args:
            name: Field name attribute value

        Returns:
            bool: True if field has error message visible

        Example:
            assert form_page.has_field_error("email") is True
        """
        return len(self.get_field_error(name)) > 0

    def click_submit(self) -> None:
        """Click form submit button.

        Example:
            form_page.fill_text_field("name", "John")
            form_page.click_submit()
        """
        self.form_submit_button.click()

    def is_submit_enabled(self) -> bool:
        """Check if submit button is enabled.

        Returns:
            bool: True if submit button is not disabled

        Example:
            assert form_page.is_submit_enabled() is True
        """
        return not self.form_submit_button.is_disabled()

    def is_submitting(self) -> bool:
        """Check if form is currently submitting.

        Returns:
            bool: True if button shows "Submitting..." text

        Example:
            form_page.click_submit()
            assert form_page.is_submitting() is True
        """
        button_text = self.form_submit_button.text_content()
        return "Submitting..." in button_text if button_text else False

    def is_success_message_visible(self) -> bool:
        """Check if success message is displayed.

        Returns:
            bool: True if success message with Check icon is visible

        Example:
            form_page.wait_for_submission()
            assert form_page.is_success_message_visible() is True
        """
        return self.form_success_message.is_visible()

    def get_success_message(self) -> str:
        """Get success message text.

        Returns:
            str: Success message text or empty string

        Example:
            msg = form_page.get_success_message()
            assert "submitted successfully" in msg.lower()
        """
        if self.form_success_message.is_visible():
            return self.form_success_message.text_content()
        return ""

    def wait_for_submission(self, timeout: int = 5000) -> None:
        """Wait for form submission to complete (success or error).

        Args:
            timeout: Maximum time to wait in milliseconds

        Example:
            form_page.click_submit()
            form_page.wait_for_submission(timeout=10000)
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        try:
            # Wait for either success message or submit button to re-enable
            self.page.wait_for_selector(
                "div.flex.items-center.justify-center.p-8.text-green-600, "
                "button[type=\"submit\"]:not([disabled])",
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Form submission did not complete within {timeout}ms")

    def get_form_data(self) -> dict:
        """Extract current form data from all fields.

        Returns:
            dict: Form field names and current values

        Example:
            data = form_page.get_form_data()
            assert data["email"] == "user@example.com"
        """
        data = {}
        all_fields = self.form_field.all()

        for field in all_fields:
            name = field.get_attribute("name")
            if not name:
                continue

            field_type = field.get_attribute("type")
            if field_type == "checkbox":
                data[name] = field.is_checked()
            elif field_type == "number":
                value = field.input_value()
                data[name] = float(value) if value else None
            else:
                data[name] = field.input_value()

        return data

    def is_field_required(self, name: str) -> bool:
        """Check if field has required indicator (asterisk).

        Args:
            name: Field name attribute value

        Returns:
            bool: True if field has required asterisk

        Example:
            assert form_page.is_field_required("email") is True
        """
        field = self.page.locator(f"input[name=\"{name}\"], select[name=\"{name}\"]")
        if field.is_visible():
            # Look for required asterisk in label container
            container = field.locator("xpath=../..")
            asterisk = container.locator("span.text-red-500.ml-1")
            return asterisk.is_visible()
        return False

    def get_field_label(self, name: str) -> str:
        """Get label text for a field.

        Args:
            name: Field name attribute value

        Returns:
            str: Field label text or empty string

        Example:
            label = form_page.get_field_label("email")
            assert label == "Email Address"
        """
        field = self.page.locator(f"input[name=\"{name}\"], select[name=\"{name}\"]")
        if field.is_visible():
            # Get label text from parent container
            container = field.locator("xpath=../..")
            label_el = container.locator("label.text-xs.font-medium")
            if label_el.is_visible():
                label_text = label_el.text_content()
                # Remove asterisk if present
                if label_text and "*" in label_text:
                    return label_text.replace("*", "").strip()
                return label_text
        return ""
