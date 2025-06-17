# Atom Agent - Manual Testing Plan

This document outlines the steps for manually testing the Atom Agent integration within the Atomic Docker application.

## 1. Setup

1.  **Clone the Repository:** Ensure you have the latest version of the `atomic-docker` repository.
2.  **Install Dependencies:**
    *   Navigate to `atomic-docker/app_build_docker` and run `npm install` (or `yarn install`).
    *   Navigate to `atomic-docker/project/functions/atom-agent` (and any other relevant function directories if they have their own dependencies, though for now Atom agent is self-contained for its logic). If these functions were to be deployed as separate services, they might have their own `package.json`.
3.  **Environment Variables:**
    *   Ensure any necessary environment variables for the Next.js application are set up in `atomic-docker/app_build_docker/.env.local` (or equivalent). For Atom agent testing specifically, no new backend ENV vars are strictly needed yet as skills are mocked.
4.  **Run the Application:**
    *   From the `atomic-docker/app_build_docker` directory, run the Next.js development server: `npm run dev` (or `yarn dev`).
    *   The application should typically be accessible at `http://localhost:3000`.

## 2. Chat Interface Testing

Navigate to the chat interface within the application (currently accessible via the Calendar page at `/Calendar/Chat/UserViewChat`).

### 2.1. Calendar Skills

1.  **List Events (Default):**
    *   **Action:** Type `list events` and send.
    *   **Expected Result:** Atom should respond with a list of mock upcoming calendar events (e.g., "Upcoming events:\n- Team Meeting...", "No upcoming events found." if mock is empty).
2.  **List Events (With Limit):**
    *   **Action:** Type `list events 1` and send.
    *   **Expected Result:** Atom should respond with a maximum of 1 mock event.
    *   **Action:** Type `list events 0` and send.
    *   **Expected Result:** Atom should respond with "No upcoming events found." or an empty list.
3.  **Create Event (Valid JSON):**
    *   **Action:** Type `create event {"summary":"Dentist Appointment","startTime":"2024-04-10T14:00:00Z","endTime":"2024-04-10T15:00:00Z","description":"Check-up"}` and send.
    *   **Expected Result:** Atom should respond with a success message like "Event created: Calendar event created successfully (mock). (ID: mockEvent_...)"
4.  **Create Event (Default/Fallback):**
    *   **Action:** Type `create event` and send.
    *   **Expected Result:** Atom should respond with a success message for a default event, e.g., "Event created: Calendar event created successfully (mock). (ID: mockEvent_...)".
5.  **Create Event (Invalid JSON):**
    *   **Action:** Type `create event {"summary":"Missing time"` and send.
    *   **Expected Result:** Atom should respond with an error like "Invalid event details format. Please provide JSON for event details..."
6.  **Create Event (Missing Required Fields, but Valid JSON):**
    *   **Action:** Type `create event {"summary":"Only Summary"}` and send.
    *   **Expected Result:** Atom should respond with a message indicating failure due to missing fields, e.g., "Failed to create event: Missing required event details (summary, startTime, endTime)."

### 2.2. Email Skills

1.  **List Emails (Default):**
    *   **Action:** Type `list emails` and send.
    *   **Expected Result:** Atom should respond with a list of mock recent emails, showing sender, subject, and read status (e.g., "Recent emails:\n- (unread) From: no-reply@example.com, Subject: Your Weekly Digest (ID: email1)...").
2.  **List Emails (With Limit):**
    *   **Action:** Type `list emails 1` and send.
    *   **Expected Result:** Atom should respond with a maximum of 1 mock email.
3.  **Read Email (Valid ID):**
    *   **Action:** Type `read email email1` (or another ID from the mock list) and send.
    *   **Expected Result:** Atom should display the details of the mock email (From, To, Subject, Date, Body). The email should be marked as "read" if listed again.
4.  **Read Email (Invalid ID):**
    *   **Action:** Type `read email nonExistentId` and send.
    *   **Expected Result:** Atom should respond with "Could not read email." or "Email with ID nonExistentId not found."
5.  **Send Email (Valid JSON):**
    *   **Action:** Type `send email {"to":"test@example.com","subject":"Hello from Atom","body":"This is a test email."}` and send.
    *   **Expected Result:** Atom should respond with a success message like "Email sent: Email sent successfully (mock). (ID: mockSentEmail_...)".
6.  **Send Email (Invalid JSON):**
    *   **Action:** Type `send email {"to":"test@example.com",` and send.
    *   **Expected Result:** Atom should respond with "Invalid email details format..."
7.  **Send Email (Missing Required Fields):**
    *   **Action:** Type `send email {"to":"test@example.com"}` and send.
    *   **Expected Result:** Atom should respond with "Failed to send email: Missing required email details (to, subject, body)."

### 2.3. Web Research Skills

1.  **Search Web (Valid Query):**
    *   **Action:** Type `search web what is AI` and send.
    *   **Expected Result:** Atom should respond with a list of mock search results, including title, link, and snippet (e.g., "Web search results for "what is AI":\n\n- Result 1..."). If the query matches mock data (e.g., "example" or "iana"), specific mock results should appear.
2.  **Search Web (Query not matching specific mocks):**
    *   **Action:** Type `search web uniquequery123abc` and send.
    *   **Expected Result:** Atom should respond with a generic mock result indicating no specific results were found for that query but providing a link to a search engine.
3.  **Search Web (Empty Query):**
    *   **Action:** Type `search web` and send.
    *   **Expected Result:** Atom should respond with "Please provide a search query..."

### 2.4. Zapier Skills

1.  **Trigger Zap (With Data):**
    *   **Action:** Type `trigger zap MyAweSomeZap with data {"name":"Test User","value":42}` and send.
    *   **Expected Result:** Atom should respond with a success message like "Zap triggered: Zap "MyAwesomeZap" triggered successfully (mock). (Run ID: zapRun_...)".
2.  **Trigger Zap (Without Data):**
    *   **Action:** Type `trigger zap MySimpleZap` and send.
    *   **Expected Result:** Atom should respond with a success message like "Zap triggered: Zap "MySimpleZap" triggered successfully (mock). (Run ID: zapRun_...)".
3.  **Trigger Zap (Invalid JSON Data):**
    *   **Action:** Type `trigger zap MyZapName with data {"name":` and send.
    *   **Expected Result:** Atom should respond with "Invalid JSON data format..."
4.  **Trigger Zap (No Zap Name):**
    *   **Action:** Type `trigger zap` and send.
    *   **Expected Result:** Atom should respond with "Please provide a Zap name..."

### 2.5. General Chat Functionality

1.  **Unknown Command:**
    *   **Action:** Type `make me a sandwich` and send.
    *   **Expected Result:** Atom should respond with its standard fallback message: `Atom received: "make me a sandwich". I can understand "list events", ...`.
2.  **Error Handling (Conceptual - API Failure):**
    *   **Action:** (This is hard to trigger without modifying code or network conditions). If the `/api/atom/message` endpoint were to fail (e.g., return a 500 error).
    *   **Expected Result (UI):** The chat interface should display a user-friendly error message like "Error: Internal Server Error from Atom agent" or similar, instead of crashing.

## 3. Settings Page Testing

1.  **Navigate to Settings:**
    *   Access the application and navigate to the main settings page (typically via a user menu or settings icon). The URL is usually `/Settings/UserViewSettings`.
2.  **Verify Atom Agent Section:**
    *   **Action:** Scroll or look through the settings page.
    *   **Expected Result:**
        *   A section titled "Atom Agent Configuration" (or similar) should be visible.
        *   Inside this section, the following UI elements should be present:
            *   Label: "Google Calendar" and Button: "Connect Google Calendar".
            *   Label: "Email Account" and Button: "Connect Email Account".
            *   Label: "Zapier Integration", an input field with placeholder "Enter Zapier Webhook URL for Atom", and a Button: "Save Zapier URL".
3.  **Placeholder Interactivity (Non-functional for some buttons):**
    *   **Action:** Click the "Connect Email Account", "Save Zapier URL" buttons.
    *   **Expected Result:** Nothing functional should happen. Console logs might appear if any were added in `AtomAgentSettings.tsx`.
    *   Action (Google Calendar):** See "End-to-End Google Calendar Integration Testing" below for the "Connect/Disconnect Google Calendar" buttons.

## 4. End-to-End Google Calendar Integration Testing

This section details testing the actual OAuth flow with Google Calendar and subsequent API calls.
Success of these tests, especially chat commands, depends on all prerequisites being met.

### Prerequisites

Before proceeding with these tests, ensure the following are correctly configured and operational:

1.  **Hasura Database & Table:**
    *   The `Calendar_Integration` table must exist in your Hasura database and match the schema used by `token-utils.ts`. This includes columns like `userId`, `token` (encrypted access token), `refreshToken` (encrypted refresh token), `expiresAt`, `scope`, `resource`, `clientType`, `name`, `enabled`.
    *   A unique constraint (e.g., `Calendar_Integration_userId_resource_clientType_key`) must exist on (`userId`, `resource`, `clientType`). For Atom, these are `resource = 'google_atom_calendar'` and `clientType = 'atom_agent'`.
2.  **Google Cloud Project:**
    *   Google Calendar API enabled.
    *   OAuth 2.0 credentials (Client ID and Client Secret) created.
    *   Authorized redirect URI for OAuth 2.0 client correctly set to point to `/api/atom/auth/calendar/callback` for your environment.
3.  **Environment Variables:** The following MUST be correctly set in the backend environment:
    *   `ATOM_GOOGLE_CALENDAR_CLIENT_ID`
    *   `ATOM_GOOGLE_CALENDAR_CLIENT_SECRET`
    *   `ATOM_GOOGLE_CALENDAR_REDIRECT_URI`
    *   `HASURA_GRAPHQL_URL` (or `HASURA_GRAPHQL_GRAPHQL_URL`)
    *   `HASURA_ADMIN_SECRET`
    *   `ATOM_TOKEN_ENCRYPTION_KEY`: A 64-character hex string (32 bytes) for AES-256 token encryption.
    *   `ATOM_TOKEN_ENCRYPTION_IV`: A 32-character hex string (16 bytes) for AES-256 token encryption.
    *   *(Purpose: `ATOM_TOKEN_ENCRYPTION_KEY` and `IV` are used to encrypt and decrypt OAuth tokens before storing them in and after retrieving them from the database, enhancing security.)*
4.  **Supertokens:**
    *   Supertokens service running and correctly initialized for user authentication.
5.  **Atom Agent Handler `userId`:**
    *   The `userId` passed to `atomic-docker/project/functions/atom-agent/handler.ts` (via `pages/api/atom/message.ts`) is now the real, authenticated user's ID from their Supertokens session. This is crucial for per-user operations.
6.  **Token Encryption:**
    *   Real AES-256-CBC encryption is now implemented in `token-utils.ts`. The placeholder comments are removed.

### 4.1. OAuth Flow Testing & Status Verification

1.  **Navigate to Settings:** Go to Settings -> Atom Agent Configuration.
2.  **Initiate Connection:**
    *   **Action:** Click the "Connect Google Calendar" button.
    *   **Expected Result:** You should be redirected to a Google Account sign-in page, followed by a consent screen requesting permission for "Google Calendar API" (or similar, based on the scope `https://www.googleapis.com/auth/calendar`).
3.  **Cancel Consent:**
    *   **Action:** On the Google consent screen, click "Cancel" (or deny permission).
    *   **Expected Result:** You should be redirected back to the Atom Agent Configuration settings page. An error message like "Google Calendar connection failed: access_denied" (or similar, depending on Google's response) should be displayed. The status should remain "Status: Not Connected".
4.  **Grant Consent:**
    *   **Action:** Click "Connect Google Calendar" again. This time, on the Google consent screen, select your account and grant the requested permissions.
    *   **Expected Result:** You should be redirected back to the Atom Agent Configuration settings page. A success message "Google Calendar connected successfully!" should be displayed. The UI should update to show "Status: Connected (user@example.com - mock)" (the email is mocked for now).
5.  **Disconnect Calendar:**
    *   **Server Log:** During the callback, check for logs from `token-utils.ts` indicating successful encryption and from `saveAtomGoogleCalendarTokens` showing successful token storage for the authenticated user.
    *   **Status API Check:** Manually (e.g., via browser tab or Postman, ensuring you are authenticated for the API call) call `/api/atom/auth/calendar/status`. It should return `{ "isConnected": true, "email": "user_from_token@example.com" }` (email is still mock, but `isConnected` should be true).
5.  **Disconnect Calendar:**
    *   **Action:** With the status showing "Connected", click the "Disconnect Google Calendar" button.
    *   **Expected Result:**
        *   A success message "Google Calendar disconnected successfully for Atom Agent." (or similar) should be displayed by the settings UI.
        *   The UI should update to "Status: Not Connected".
        *   **Server Log:** Check for logs from `/api/atom/auth/calendar/disconnect.ts` indicating `deleteAtomGoogleCalendarTokens` was called for the correct user ID.
        *   **Status API Check:** Call `/api/atom/auth/calendar/status` again. It should return `{ "isConnected": false }`.

### 4.2. Chat Interface - Calendar Commands (Post Successful Connection)

After successfully completing the "Grant Consent" step and verifying "Status: Connected":

1.  **List Events Command:**
    *   **Action:** In the chat interface, type `list events` and send.
    *   **Expected Result:**
        *   If the authenticated user's connected Google Calendar has upcoming events, they should be listed (e.g., "- Event Summary (StartTime - EndTime) [Link: ...]").
        *   If the calendar is empty, Atom should respond with "Could not retrieve calendar events. Please ensure your Google Calendar is connected in settings and try again, or there might be no upcoming events." (This message appears if the skill returns an empty list, which can mean genuinely no events or an issue like invalid tokens if prerequisites aren't perfectly met).
    *   **Server Log:** Check for logs from `calendarSkills.ts` (token decryption, API call attempt).
2.  **Create Event Command:**
    *   **Action:** In the chat interface, type `create event {"summary":"Atom Test Event via Chat","startTime":"YYYY-MM-DDTHH:MM:SSZ","endTime":"YYYY-MM-DDTHH:MM:SSZ"}` (use valid future ISO dates/times for your connected calendar's timezone).
    *   **Expected Result:**
        *   Atom should respond with a success message: "Event created: Calendar event created successfully with Google Calendar. (ID: ...)[Link: ...]".
        *   Verify the event appears in the authenticated user's connected Google Calendar.
    *   **Server Log:** Check for logs from `calendarSkills.ts` (token decryption, event insertion API call).
3.  **Create Event (Minimal):**
    *   **Action:** `create event {"summary":"Quick Meeting","startTime":"YYYY-MM-DDTHH:MM:SSZ","endTime":"YYYY-MM-DDTHH:MM:SSZ"}`
    *   **Expected Result:** Event created in the user's Google Calendar.
4.  **Create Event (Past):**
    *   **Action:** `create event {"summary":"Past Event Test","startTime":"YYYY-MM-DDTHH:MM:SSZ","endTime":"YYYY-MM-DDTHH:MM:SSZ"}` (use past ISO dates/times).
    *   **Expected Result:** Event created in the user's Google Calendar.

### 4.3. Token Refresh Testing (Conceptual & Observational)

*   **Background:** The `googleapis` library automatically attempts to refresh the access token if it's expired and a refresh token is available. The `calendarSkills.ts` has a listener to save these refreshed tokens.
*   **Manual Trigger Difficulty:** It's hard to manually force an access token (typically valid for 1 hour) to expire on demand for a quick test.
*   **Observation Method:**
    1.  Successfully connect Google Calendar.
    2.  Wait for over an hour (or however long the access token is valid).
    3.  Try a calendar command again (e.g., `list events`).
    4.  **Expected Result:** The command should still succeed.
    5.  **Server Log:** Check for console logs from `calendarSkills.ts` like "Google API tokens were refreshed for Atom Agent..." and from `token-utils.ts` indicating `saveAtomGoogleCalendarTokens` was called due to the refresh. This confirms the refresh flow worked.
*   **Alternative (if tools available):** If you have a way to manually revoke the specific access token (e.g., via Google Account security settings or an API tool, without revoking the entire application grant/refresh token), doing so would immediately trigger the refresh flow on the next API call.

### 4.4. Error Condition Testing

1.  **Invalid Redirect URI:**
    *   **Action:** Temporarily misconfigure `ATOM_GOOGLE_CALENDAR_REDIRECT_URI` in your environment (e.g., change a character) and restart the application. Try the "Connect Google Calendar" flow.
    *   **Expected Result:** Google's OAuth screen should show an error (e.g., "redirect_uri_mismatch").
2.  **Hasura Connectivity/Secret Issues during Token Storage:**
    *   **Action:** Temporarily stop your Hasura instance or change `HASURA_ADMIN_SECRET` to an incorrect value. Attempt the Google Calendar connection and grant consent.
    *   **Expected Result:** The `/api/atom/auth/calendar/callback` route should fail when trying to call `saveAtomGoogleCalendarTokens`. The user should be redirected to the settings page with an error like `calendar_auth_error=token_storage_failed`. Server logs should detail the Hasura connection failure.
3.  **Invalid/Missing Encryption Key/IV:**
    *   **Action:** Set `ATOM_TOKEN_ENCRYPTION_KEY` or `ATOM_TOKEN_ENCRYPTION_IV` to an invalid value (e.g., wrong length, not valid hex) or unset them. Restart the application. Attempt the OAuth connection.
    *   **Expected Result:** During the callback, when `saveAtomGoogleCalendarTokens` calls `encryptToken`, it should fail. The user should be redirected to the settings page with an error (e.g., `calendar_auth_error=token_storage_failed` or a more specific encryption error if propagated). Server logs in `token-utils.ts` should indicate "Encryption key or IV is missing" or "Invalid key or IV length". Subsequent attempts to use skills requiring tokens (if any were somehow stored before) would fail during decryption.
4.  **Revoked App Permissions in Google Account:**
    *   **Action:** Connect Google Calendar successfully. Then, go to your Google Account's "Security" -> "Third-party apps with account access" section and remove Atom Docker's access. Then, try a chat command like `list events`.
    *   **Expected Result:** The API call from `calendarSkills.ts` should fail (likely with an `invalid_grant` error). The chat should display "Could not retrieve calendar events...". Server logs should indicate the token failure.
    *   **Action:** Try clicking "Disconnect Google Calendar" in settings.
    *   **Expected Result:** This should still proceed to delete local tokens. The UI should show "Not Connected".
    *   **Action:** Try to "Connect Google Calendar" again.
    *   **Expected Result:** The OAuth flow should restart, and you should be prompted for consent again by Google.

### 4.5. Multi-User Data Isolation Testing (Requires multiple Google accounts & application user accounts):**

*   **User A:** Register and log in to the application.
*   **User A:** Navigate to Settings -> Atom Agent Configuration. Connect their Google Calendar (Google Account A).
*   **User A:** Open chat with Atom. Successfully list events from Google Account A's calendar.
*   **User A:** Successfully create an event in Google Account A's calendar.
*   **User B:** Register and log in to the application (ensure this is a separate user session, e.g., different browser or incognito mode).
*   **User B:** Navigate to Settings -> Atom Agent Configuration. Verify it shows 'Not Connected' for Google Calendar.
*   **User B:** Connect their Google Calendar (Google Account B - different from User A's).
*   **User B:** Open chat with Atom. Successfully list events from Google Account B's calendar. These events should be different from User A's events.
*   **User B:** Successfully create an event in Google Account B's calendar. This event should not appear in User A's calendar.
*   **User A:** Re-check their chat with Atom. List events again. Should still only see events from Google Account A.
*   **User A & B:** Each user disconnects their Google Calendar via settings. Verify status updates correctly for each and that subsequent calendar commands for that user indicate no connection or an error.


### 4.6. Important Note for Testers (Revised)

*   The success of "Chat Interface - Calendar Commands" **now directly depends on the real, authenticated `userId` being used throughout the system**, from API route protection to token storage and skill execution.
*   Real AES-256-CBC encryption is implemented in `token-utils.ts`. Ensure `ATOM_TOKEN_ENCRYPTION_KEY` and `ATOM_TOKEN_ENCRYPTION_IV` are correctly set in your environment for testing.
*   Focus on server logs from the API routes (`initiate.ts`, `callback.ts`, `disconnect.ts`, `status.ts`), `token-utils.ts` (encryption/decryption logs), and `calendarSkills.ts` (token usage, API call attempts, refresh events) for detailed insight.

This manual testing plan covers the core functionalities of the Atom agent, focusing on the end-to-end Google Calendar integration, including OAuth, secure token storage, and API interactions with real user context.
