# Email Integration - Manual Testing Plan

This document outlines the steps for manually testing the email integration for the Atom Agent.

## 1. Setup

1.  **Configure Google OAuth:**
    *   Ensure that the Google OAuth consent screen is configured to request the `https://www.googleapis.com/auth/gmail.readonly` scope in addition to the calendar scopes.

2.  **Configure AWS SES:**
    *   Ensure that the following environment variables are set in your `.env` file for the `functions` service:
        *   `AWS_REGION`
        *   `AWS_ACCESS_KEY_ID`
        *   `AWS_SECRET_ACCESS_KEY`
        *   `SES_SOURCE_EMAIL` (a verified email address in SES)

3.  **Run the Application:**
    *   From the root of the `atomic-docker` directory, run the application using Docker Compose:
        ```bash
        docker-compose -f project/docker-compose.local.yaml up --build
        ```
    *   The application should be accessible at `http://localhost:3000`.

## 2. Connecting a Google Account

1.  **Navigate to Settings:**
    *   Open the application in your browser.
    *   Navigate to the settings page (e.g., `/Settings/UserViewSettings`).
    *   Find the "Atom Agent Configuration" or "Integrations" section.

2.  **Connect Google Account:**
    *   **Action:** Click the "Connect Google Account" button.
    *   **Expected Result:** You should be redirected to Google's sign-in page, followed by a consent screen that now includes a permission for "Read, compose, send, and permanently delete all your email from Gmail".

3.  **Grant Consent:**
    *   **Action:** Sign in to your Google account and grant the requested permissions.
    *   **Expected Result:** You should be redirected back to the application's settings page with a success message.

## 3. Testing Email Skills via Chat

1.  **Navigate to the Chat Interface:**
    *   Go to the chat interface (e.g., `/Calendar/Chat/UserViewChat`).

2.  **List Emails:**
    *   **Action:** Type `list emails` and send.
    *   **Expected Result:** Atom should respond with a list of recent emails from your actual Gmail account.

3.  **Read an Email:**
    *   **Action:** Copy the ID of an email from the list and type `read email <email_id>` and send.
    *   **Expected Result:** Atom should respond with the content of the specified email.

4.  **Send an Email:**
    *   **Action:** Type `send email {"to":"<your_personal_email>","subject":"Test from Atom","body":"This is a test email sent from the Atom Agent."}` and send.
    *   **Expected Result:** Atom should confirm that the email was sent. You should then receive this email in your personal inbox.
