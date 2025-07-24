# Google Calendar Integration - Manual Testing Plan

This document outlines the steps for manually testing the fixed Google Calendar integration for the Atom Agent.

## 1. Setup

1.  **Run the Application:**
    *   From the root of the `atomic-docker` directory, run the application using Docker Compose:
        ```bash
        docker-compose -f project/docker-compose.local.yaml up --build
        ```
    *   The application should be accessible at `http://localhost:3000`.

## 2. Testing the OAuth Flow and Token Storage

1.  **Navigate to Settings:**
    *   Open the application in your browser.
    *   Navigate to the settings page (e.g., `/Settings/UserViewSettings`).
    *   Find the "Atom Agent Configuration" or "Integrations" section.

2.  **Connect Google Calendar:**
    *   **Action:** Click the "Connect Google Calendar" button.
    *   **Expected Result:** You should be redirected to Google's sign-in page, followed by a consent screen for the "Google Calendar API".

3.  **Grant Consent:**
    *   **Action:** Sign in to your Google account and grant the requested permissions.
    *   **Expected Result:** You should be redirected back to the application's settings page. A success message should appear, and the UI should indicate that your Google Calendar is connected.

4.  **Verify Token Storage (Developer Task):**
    *   **Action:** Check the application's database (e.g., the `user_tokens` table in the `postgres` service).
    *   **Expected Result:** A new entry should exist for the user, with the `service_name` as `google_calendar`, containing encrypted access and refresh tokens.

## 3. Testing Calendar Skills via Chat

1.  **Navigate to the Chat Interface:**
    *   Go to the chat interface (e.g., `/Calendar/Chat/UserViewChat`).

2.  **List Events:**
    *   **Action:** Type `list events` and send.
    *   **Expected Result:** Atom should respond with a list of upcoming events from your actual Google Calendar. If you have no upcoming events, it should state that.

3.  **Create an Event:**
    *   **Action:** Type `create event {"summary":"Test Event via Atom","startTime":"YYYY-MM-DDTHH:MM:SSZ","endTime":"YYYY-MM-DDTHH:MM:SSZ"}` (using a valid future ISO 8601 timestamp) and send.
    *   **Expected Result:** Atom should confirm that the event was created. You should then be able to see this event in your Google Calendar.

## 4. Disconnecting Google Calendar

1.  **Navigate back to Settings:**
    *   Return to the integrations settings page.

2.  **Disconnect:**
    *   **Action:** Click the "Disconnect Google Calendar" button.
    *   **Expected Result:** The UI should update to show that the calendar is no longer connected. The `user_tokens` entry in the database for this user and service should be cleared or marked as invalid.

3.  **Verify Disconnection:**
    *   **Action:** Go back to the chat and type `list events`.
    *   **Expected Result:** Atom should respond with an error message indicating that it cannot access your calendar and that you need to connect it in the settings.
