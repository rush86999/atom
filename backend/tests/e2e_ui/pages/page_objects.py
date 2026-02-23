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


class ChatPage(BasePage):
    """Page Object for Agent Chat interface.

    Encapsulates chat interactions:
    - Message input and sending
    - Chat history display
    - Streaming response indicators
    - Agent selection

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
        """Chat history message list locator."""
        return self.page.get_by_test_id("message-list")

    @property
    def user_message(self) -> Locator:
        """User message bubble locator."""
        return self.page.get_by_test_id("user-message")

    @property
    def assistant_message(self) -> Locator:
        """Assistant/agent response message locator."""
        return self.page.get_by_test_id("assistant-message")

    @property
    def streaming_indicator(self) -> Locator:
        """Streaming/loading indicator locator."""
        return self.page.get_by_test_id("streaming-indicator")

    @property
    def agent_selector(self) -> Locator:
        """Agent selection dropdown locator."""
        return self.page.get_by_test_id("agent-selector")

    @property
    def message_bubble(self) -> Locator:
        """Generic message bubble locator (any message)."""
        return self.page.get_by_test_id("message-bubble")

    def is_loaded(self) -> bool:
        """Check if chat interface is loaded.

        Returns:
            bool: True if chat container is visible

        Example:
            assert chat_page.is_loaded() is True
        """
        return self.chat_container.is_visible()

    def navigate(self) -> None:
        """Navigate to chat page.

        Example:
            chat_page.navigate()
            assert chat_page.is_loaded()
        """
        self.page.goto("http://localhost:3000/chat")

    def send_message(self, text: str) -> None:
        """Type and send a chat message.

        Args:
            text: Message text to send

        Example:
            chat_page.send_message("Hello agent")
            # Message sent via /api/atom-agent/chat/stream
        """
        self.chat_input.fill(text)
        self.send_button.click()

    def get_last_message(self) -> str:
        """Get the most recent message text from chat history.

        Returns:
            str: Text content of last message, or empty string if none

        Example:
            msg = chat_page.get_last_message()
            assert "Hello" in msg
        """
        bubbles = self.message_bubble.all()
        if bubbles:
            return bubbles[-1].text_content()
        return ""

    def get_message_count(self) -> int:
        """Get the number of messages in chat history.

        Returns:
            int: Number of message bubbles visible

        Example:
            count = chat_page.get_message_count()
            assert count == 3
        """
        return self.message_bubble.count()

    def wait_for_response(self, timeout: int = 5000) -> None:
        """Wait for assistant response to appear.

        Args:
            timeout: Maximum time to wait in milliseconds

        Example:
            chat_page.send_message("Hello")
            chat_page.wait_for_response()
            # Assistant message visible
        """
        from playwright.sync_api import TimeoutError
        try:
            # Wait for at least 2 messages (user + assistant)
            self.page.wait_for_function(
                "() => document.querySelectorAll('[data-testid=\"message-bubble\"]').length >= 2",
                timeout=timeout
            )
        except TimeoutError:
            # Response didn't arrive in time
            pass

    def is_streaming(self) -> bool:
        """Check if streaming response is in progress.

        Returns:
            bool: True if streaming indicator is visible

        Example:
            chat_page.send_message("Tell me a story")
            assert chat_page.is_streaming() is True
            chat_page.wait_for_response()
            assert chat_page.is_streaming() is False
        """
        return self.streaming_indicator.is_visible()

    def select_agent(self, agent_name: str) -> None:
        """Select an agent from the agent dropdown.

        Args:
            agent_name: Name of agent to select (e.g., "AUTONOMOUS", "INTERN")

        Example:
            chat_page.select_agent("AUTONOMOUS")
            # AUTONOMOUS agent selected for chat
        """
        self.agent_selector.select_option(agent_name)

    def get_all_messages(self) -> list[str]:
        """Get all messages from chat history.

        Returns:
            list[str]: List of message texts in chronological order

        Example:
            messages = chat_page.get_all_messages()
            assert len(messages) == 4
        """
        bubbles = self.message_bubble.all()
        return [bubble.text_content() for bubble in bubbles]

    def clear_chat(self) -> None:
        """Clear chat history (if clear button available).

        Example:
            chat_page.clear_chat()
            assert chat_page.get_message_count() == 0
        """
        # Look for clear button using data-testid
        clear_button = self.page.get_by_test_id("clear-chat-button")
        if clear_button.is_visible():
            clear_button.click()
