# Zapier Integration - Manual Testing Plan

This document outlines the steps for manually testing the Zapier integration for the Atom Agent.

## 1. Setup

1.  **Create a Zapier Webhook:**
    *   Go to Zapier and create a new Zap.
    *   For the trigger, select "Webhooks by Zapier".
    *   Choose the "Catch Hook" event.
    *   Copy the provided webhook URL.

2.  **Run the Application:**
    *   From the root of the `atomic-docker` directory, run the application using Docker Compose:
        ```bash
        docker-compose -f project/docker-compose.local.yaml up --build
        ```
    *   The application should be accessible at `http://localhost:3000`.

## 2. Configuring the Webhook URL

1.  **Navigate to Settings:**
    *   Open the application in your browser.
    *   Navigate to the settings page (e.g., `/Settings/UserViewSettings`).
    *   Find the "Atom Agent Configuration" or "Integrations" section.

2.  **Save the Webhook URL:**
    *   **Action:** Paste the Zapier webhook URL you copied into the "Zapier Integration" input field.
    *   **Action:** Click the "Save Zapier URL" button.
    *   **Expected Result:** A success message should appear.

3.  **Verify URL Persistence:**
    *   **Action:** Refresh the page.
    *   **Expected Result:** The Zapier webhook URL should still be present in the input field.

## 3. Testing the Zapier Skill via Chat

1.  **Navigate to the Chat Interface:**
    *   Go to the chat interface (e.g., `/Calendar/Chat/UserViewChat`).

2.  **Trigger the Zap:**
    *   **Action:** Type `trigger zap MyTestZap with data {"key":"value"}` and send.
    *   **Expected Result:** Atom should respond with a success message.

3.  **Verify Zapier Trigger:**
    *   **Action:** Go back to your Zap in Zapier.
    *   **Action:** Test the trigger.
    *   **Expected Result:** You should see the data you sent from the chat (`{"key":"value"}`) in the test data.
