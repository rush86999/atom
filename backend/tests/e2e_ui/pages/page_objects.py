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
