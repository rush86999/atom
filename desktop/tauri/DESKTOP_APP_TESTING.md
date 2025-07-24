# Atom Desktop App - Full Manual Testing Plan

This document provides a comprehensive plan for manually testing the refactored Atom Desktop Application.

## 1. Prerequisites

1.  **Run the Web App Backend:**
    *   The desktop app relies on the web app's backend for NLU and skill execution. Ensure it's running:
        ```bash
        docker-compose -f atomic-docker/project/docker-compose.local.yaml up --build
        ```
2.  **Run the Desktop App:**
    *   Navigate to the `desktop/tauri` directory.
    *   Run the app in development mode:
        ```bash
        npm run tauri dev
        ```

## 2. Settings and Secure Storage

1.  **Navigate to Settings:**
    *   In the desktop app, go to the "Settings" view.

2.  **Configure Notion:**
    *   **Action:** Enter a valid Notion API key and click "Save Settings".
    *   **Expected Result:** A success message should appear, and the API key should be masked.
    *   **Action:** Restart the application and return to the settings page.
    *   **Expected Result:** The Notion API key field should still show the masked value, indicating it was saved securely.

3.  **Configure Zapier:**
    *   **Action:** Enter a valid Zapier webhook URL and click "Save Settings".
    *   **Action:** Restart the application.
    *   **Expected Result:** The Zapier webhook URL should be visible in the input field.

4.  **Configure Voice Settings:**
    *   **Action:** Select "ElevenLabs" from the dropdown, enter a valid API key, and click "Save Settings".
    *   **Action:** Restart the application and return to settings.
    *   **Expected Result:** "ElevenLabs" should be the selected provider, and the API key should be masked.
    *   **Action:** Repeat the process for "Deepgram".

## 3. Core Skills Testing (via Chat)

1.  **Navigate to the Chat Interface.**

2.  **Notion Skill:**
    *   **Action:** Type `create notion page My Desktop Test` and send.
    *   **Expected Result:** The agent should respond with a confirmation message. Check your Notion workspace to ensure the page was created.

3.  **Zapier Skill:**
    *   **Action:** Type `trigger zap MyDesktopZap` and send.
    *   **Expected Result:** The agent should confirm the Zap was triggered. Check your Zapier history to verify.

4.  **Browser Skill (Desktop-Specific):**
    *   **Action:** Type `browser https://www.google.com` and send.
    *   **Expected Result:** The agent should confirm it's opening the URL, and your default web browser should open to the specified page.

5.  **TTS Skill:**
    *   **Action:** Type any message that doesn't match another intent (e.g., `hello world`).
    *   **Expected Result:** The agent should respond with a message indicating that the TTS skill is not fully implemented in the Rust backend yet. (This is the expected behavior for now, as the audio playback is not yet implemented).

## 4. General Functionality

*   **Error Handling:**
    *   Try using a skill without configuring the necessary API key in settings.
    *   **Expected Result:** The agent should respond with a clear error message indicating that the required credentials are not configured.
*   **UI Responsiveness:**
    *   Ensure the UI remains responsive while the agent is processing requests.
