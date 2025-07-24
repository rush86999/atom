# Atom Agent - Full Manual Testing Plan

This document provides a comprehensive plan for manually testing the Atom Agent, including all integrated skills and general functionality.

## 1. Prerequisites

*   Ensure all necessary environment variables are set in `docker-compose.local.yaml` for the `functions` and `python-agent` services, including credentials for Google, AWS SES, Notion, etc.
*   Run the application using `docker-compose -f project/docker-compose.local.yaml up --build`.

## 2. Settings and Integrations

*   **Google Account:**
    *   Connect a Google account in the settings.
    *   Verify that the connection is successful and that the UI updates to show the connected status.
    *   Disconnect the account and verify that the UI updates accordingly.
*   **Zapier:**
    *   Save a valid Zapier webhook URL in the settings.
    *   Verify that the URL is saved correctly by refreshing the page.
*   **Notion:**
    *   Verify that the Notion API token and database IDs are correctly set in the environment variables.
*   **Other Integrations:**
    *   Briefly check the UI for other integrations like Dropbox, GDrive, and Voice Settings to ensure they load without errors.

## 3. Core Skills Testing (via Chat)

*   **Calendar:**
    *   `list events`: Should show events from your connected Google Calendar.
    *   `create event {"summary":"Test","startTime":"YYYY-MM-DDTHH:MM:SSZ","endTime":"YYYY-MM-DDTHH:MM:SSZ"}`: Should create an event in your Google Calendar.
*   **Email:**
    *   `list emails`: Should show recent emails from your connected Gmail account.
    *   `read email <email_id>`: Should display the content of the specified email.
    *   `send email {"to":"<your_email>","subject":"Test","body":"Test"}`: Should send an email via AWS SES.
*   **Web Research:**
    *   `search web <query>`: Should return relevant search results from Google.
*   **Zapier:**
    *   `trigger zap <zap_name> with data {"key":"value"}`: Should trigger the configured Zapier webhook.
*   **Notion:**
    *   `create task "My new task"`: Should create a new task in your Notion "Tasks" database.
    *   `list my tasks`: Should list tasks from your Notion "Tasks" database.

## 4. Advanced Productivity Skills

*   **Prepare for Meeting:**
    *   `prepare me for my meeting about "<meeting_title>"`: Should provide a summary of relevant documents, emails, and tasks.
*   **Weekly Digest:**
    *   `what's my weekly digest?`: Should generate a summary of the week's activities.
*   **Follow-up Suggester:**
    *   `suggest follow-ups for the <meeting_title> meeting`: Should suggest action items, decisions, and questions.

## 5. General Functionality and Error Handling

*   **Unknown Command:**
    *   Type a random command like `make a pizza`.
    *   **Expected Result:** The agent should respond with a message indicating that it doesn't understand the command.
*   **Skill Failure:**
    *   Try to use a skill without the proper configuration (e.g., `list events` without connecting a Google account).
    *   **Expected Result:** The agent should respond with a specific and helpful error message, rather than a generic "Internal Server Error".

This testing plan covers all the major features of the Atom Agent and will help ensure that it is ready for a live environment.
