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

**It is CRITICAL that all the following prerequisites are meticulously met for successful end-to-end testing.** Failure to meet these will result in expected test failures or incomplete functionality.

1.  **Hasura Database & Table (`public.Calendar_Integration`):**
    *   **Existence & Schema:** The table must exist and precisely match the schema defined in `docs/TOKEN_STORAGE_SCHEMA.md` and used by `token-utils.ts`. This includes correct column names and data types for `userId`, `token` (encrypted access token), `refreshToken` (encrypted refresh token), `expiresAt`, `scope`, `token_type`, `resource`, `clientType`, `name`, and `appEmail`.
    *   **Unique Constraint (Absolutely Essential):** A unique constraint **MUST** be defined on the combination of (`userId`, `resource`, `clientType`). For Atom Agent, the specific values are `resource = 'google_atom_calendar'` and `clientType = 'atom_agent'`. This is vital for the upsert logic in `saveAtomGoogleCalendarTokens`. Refer to `docs/CALENDAR_INTEGRATION_TABLE_VERIFICATION.md` for details on verifying or adding this constraint.
2.  **Google Cloud Project:**
    *   Google Calendar API **must be enabled** in your Google Cloud Console project.
    *   Valid OAuth 2.0 credentials (Client ID and Client Secret) **must be created**.
    *   The "Authorized redirect URIs" for the OAuth 2.0 client **must exactly match** the value of the `ATOM_GOOGLE_CALENDAR_REDIRECT_URI` environment variable (e.g., `http://localhost:3000/api/atom/auth/calendar/callback` for local testing). Any mismatch will cause a Google error.
3.  **Environment Variables (Backend - e.g., `.env.local` for `app_build_docker`):**
    The following **MUST be correctly set and accessible** by the Next.js backend:
    *   `ATOM_GOOGLE_CALENDAR_CLIENT_ID` (from Google Cloud Console)
    *   `ATOM_GOOGLE_CALENDAR_CLIENT_SECRET` (from Google Cloud Console)
    *   `ATOM_GOOGLE_CALENDAR_REDIRECT_URI` (as configured in Google Cloud Console)
    *   `HASURA_GRAPHQL_URL` (or `HASURA_GRAPHQL_GRAPHQL_URL` - the correct endpoint for your Hasura instance)
    *   `HASURA_ADMIN_SECRET` (your Hasura admin secret for backend operations)
    *   `ATOM_TOKEN_ENCRYPTION_KEY`: A **securely generated 64-character hexadecimal string** (32 bytes) used for AES-256 token encryption. (Example generation: `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`)
    *   `ATOM_TOKEN_ENCRYPTION_IV`: A **securely generated 32-character hexadecimal string** (16 bytes) used as the initialization vector for AES-256 token encryption. (Example generation: `node -e "console.log(require('crypto').randomBytes(16).toString('hex'))"`)
    *   *(Security Note: The encryption key and IV are critical for protecting stored OAuth tokens.)*
4.  **Supertokens Integration:**
    *   The Supertokens service **must be running** and the Next.js application **must be correctly initialized** with Supertokens for user authentication and session management. All Atom Agent related API routes (`/api/atom/...`) are protected by Supertokens.
5.  **Atom Agent Handler `userId` (Verified & Critical):**
    *   The `userId` used by `atomic-docker/project/functions/atom-agent/handler.ts` (passed from the `/api/atom/message` route) is now sourced from the authenticated Supertokens session. This ensures that all calendar (and other) operations are performed specifically for the logged-in user.
6.  **Token Encryption (Verified):**
    *   AES-256-CBC encryption/decryption is implemented and used in `token-utils.ts` for storing and retrieving OAuth tokens from the database.

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
    *   **Action:** Temporarily stop your Hasura instance or change `HASURA_ADMIN_SECRET` to an incorrect value. Restart the application. Attempt the Google Calendar connection and grant consent.
    *   **Expected Result:** The `/api/atom/auth/calendar/callback` route should fail when `saveAtomGoogleCalendarTokens` attempts to communicate with Hasura. The user should be redirected to the settings page with an error like `calendar_auth_error=token_storage_failed`. Server logs (from `token-utils.ts`) should detail the Hasura connection failure.
3.  **Invalid/Missing Encryption Key/IV:**
    *   **Action:** Set `ATOM_TOKEN_ENCRYPTION_KEY` or `ATOM_TOKEN_ENCRYPTION_IV` to an invalid value (e.g., wrong length for hex decoding, or completely unset them). Restart the application. Attempt the OAuth connection.
    *   **Expected Result:** During the OAuth callback, `saveAtomGoogleCalendarTokens` will call `encryptToken`, which will fail (return `null` and log an error). This causes `saveAtomGoogleCalendarTokens` to throw an error ("Token encryption failed"). The user should be redirected to the settings page, likely with `calendar_auth_error=token_storage_failed` or a similar propagated error. Server logs in `token-utils.ts` should clearly indicate "Encryption key or IV is missing" or "Invalid key or IV length".
    *   **Follow-up (if tokens were somehow stored with one key/IV and then key/IV changed):** Any subsequent attempt by skills to use stored tokens (e.g., `list events` command) would fail during the decryption step in `getAtomGoogleCalendarTokens`, leading to the skill reporting connection issues or failing to retrieve data.
4.  **Revoked App Permissions in Google Account:**
    *   **Action:** Connect Google Calendar successfully. Then, go to your Google Account's security settings ("Third-party apps with account access") and **remove access for "Atom Docker"** (or whatever your Google Cloud Project is named). Afterwards, in the application, try a chat command like `list events`.
    *   **Expected Result:** The API call from `calendarSkills.ts` should fail. Google will return an error (typically `invalid_grant` as the token is no longer authorized). The chat interface should display a user-friendly error like "Could not retrieve calendar events. Please ensure your Google Calendar is connected...". Server logs from `calendarSkills.ts` should indicate the specific token failure (e.g., "Token error (invalid_grant or expired/revoked)").
    *   **Action:** In settings, click "Disconnect Google Calendar".
    *   **Expected Result:** This should successfully delete the (now invalid) local tokens from the database. The UI should update to "Status: Not Connected".
    *   **Action:** Attempt to "Connect Google Calendar" again.
    *   **Expected Result:** The full OAuth flow should initiate, and Google should prompt for consent again, as the previous application grant was revoked.
    *   **Note on Unit Test Coverage:** Many specific backend error conditions (e.g., database connectivity issues during token storage, cryptographic errors, API authentication failures, invalid API request formats) are now robustly covered by unit tests. Manual testing should focus on verifying the end-to-end user experience, including how the UI gracefully handles errors propagated from the backend, and overall system integration.

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

## 5. End-to-End Gmail Integration Testing

This section details testing the actual OAuth flow with Gmail and subsequent API calls by the Atom Agent. Success depends on all prerequisites being met.

### Prerequisites (Gmail)

Ensure all general prerequisites from Section 4 (Hasura, Google Cloud Project base, Supertokens, `userId` in handler, Encryption) are met, plus the following Gmail-specific items:

1.  **Google Cloud Project (Gmail Specific):**
    *   **Gmail API must be enabled** in your Google Cloud Console project.
    *   OAuth 2.0 credentials used by Atom Agent (`ATOM_GMAIL_CLIENT_ID`, `ATOM_GMAIL_CLIENT_SECRET`) must be valid and authorized for the Gmail API scopes defined in `constants.ts` (`GMAIL_API_SCOPES`).
    *   The "Authorized redirect URIs" for this OAuth client must include the exact URI for Gmail callback: (`http://localhost:3000/api/atom/auth/email/callback` for local testing, or your production equivalent).
2.  **Environment Variables (Backend - Gmail Specific):**
    The following **MUST be correctly set** in the backend environment:
    *   `ATOM_GMAIL_CLIENT_ID`
    *   `ATOM_GMAIL_CLIENT_SECRET`
    *   `ATOM_GMAIL_REDIRECT_URI`
    *   *(Ensure `ATOM_TOKEN_ENCRYPTION_KEY`, `ATOM_TOKEN_ENCRYPTION_IV`, `HASURA_GRAPHQL_URL`, `HASURA_ADMIN_SECRET` are also set as per general prerequisites).*

### 5.1. OAuth Flow Testing & Status Verification (Gmail)

1.  **Navigate to Settings:** Go to Settings -> Atom Agent Configuration.
2.  **Initiate Connection:**
    *   **Action:** Click the "Connect Gmail Account" button.
    *   **Expected Result:** You should be redirected to a Google Account sign-in page, followed by a consent screen requesting permissions for Gmail (e.g., "Read, compose, send, and permanently delete all your email from Gmail", "View and modify but not delete your email", "View your basic profile info" - depending on the scopes defined in `GMAIL_API_SCOPES`).
3.  **Cancel Consent:**
    *   **Action:** On the Google consent screen, click "Cancel" or deny permission.
    *   **Expected Result:** Redirected back to settings page. An error message like "Gmail account connection failed: access_denied" should be displayed. Status should remain "Gmail Not Connected".
4.  **Grant Consent:**
    *   **Action:** Click "Connect Gmail Account" again. Grant permissions on the Google consent screen.
    *   **Expected Result:** Redirected back to settings page. Success message "Gmail account connected successfully!" displayed. UI should show "Status: Gmail Connected (your.email@gmail.com)".
    *   **Server Log:** Check for logs from `email/callback.ts` and `token-utils.ts` indicating successful token fetch, user info fetch (email), token encryption, and storage (with `resource = ATOM_GMAIL_RESOURCE_NAME`).
    *   **Status API Check:** Manually call `/api/atom/auth/email/status`. It should return `{ "isConnected": true, "email": "your.email@gmail.com" }`.
5.  **Disconnect Gmail:**
    *   **Action:** Click "Disconnect Gmail Account".
    *   **Expected Result:** Success message. UI updates to "Gmail Not Connected". Server logs show token deletion for `ATOM_GMAIL_RESOURCE_NAME`. `/api/atom/auth/email/status` returns `{ "isConnected": false }`.

### 5.2. Chat Interface - Email Commands (Post Successful Gmail Connection)

1.  **List Emails Command:**
    *   **Action:** Type `list emails` and send.
    *   **Expected Result:** If the connected Gmail account has emails in the inbox, they should be listed (e.g., "1. Subject: [Subject], From: [Sender], Date: [Date], ID: [MsgId]"). If inbox is empty, "No recent emails found..." message.
    *   **Server Log:** Check `emailSkills.ts` logs for API call attempts.
2.  **List Emails with Limit:**
    *   **Action:** Type `list emails 3` and send.
    *   **Expected Result:** Maximum of 3 emails listed.
3.  **Read Email Command (using ID from list):**
    *   **Action:** Type `read email <message_id_from_list>` and send.
    *   **Expected Result:** Full email content (Subject, From, To, Date, Body) displayed. The email should be marked as read in Gmail (verify this if possible).
    *   **Server Log:** Check `emailSkills.ts` for `messages.get` and `messages.modify` (for unread label removal) calls.
4.  **Read Email (Invalid ID):**
    *   **Action:** Type `read email invalid_id_string` and send.
    *   **Expected Result:** "Could not read email. Email not found or access issue." (or similar error from API).
5.  **Send Email Command:**
    *   **Action:** Type `send email {"to":"your_other_email@example.com","subject":"Atom Test Email","body":"Hello from Atom Agent!"}` and send.
    *   **Expected Result:** "Email sent successfully! ... (Message ID: ...)" displayed. Verify the email is received at `your_other_email@example.com` and appears in the "Sent" folder of the connected Gmail account.
    *   **Server Log:** Check `emailSkills.ts` for `messages.send` call.

### 5.3. Token Refresh Testing (Gmail - Conceptual & Observational)

*   Similar to calendar, this is hard to trigger manually.
*   **Observation Method:** After connecting, wait over an hour, then try an email command. It should succeed. Check server logs for "Gmail API tokens were refreshed" messages from `emailSkills.ts` and token saving logs from `token-utils.ts`.

### 5.4. Error Condition Testing (Gmail Specific)

1.  **Invalid Gmail Redirect URI:**
    *   **Action:** Temporarily misconfigure `ATOM_GMAIL_REDIRECT_URI`. Try "Connect Gmail Account".
    *   **Expected Result:** Google OAuth screen error (e.g., "redirect_uri_mismatch").
2.  **Revoked App Permissions for Gmail in Google Account:**
    *   **Action:** Connect Gmail. Revoke app access in Google Account settings. Try `list emails` command.
    *   **Expected Result:** Chat error "No recent emails found, or there was an issue...". Server logs show `invalid_grant`. Disconnect/reconnect should require full consent again.

### 5.5. Multi-User Data Isolation Testing (Gmail)

*   Perform similar steps as outlined in **Section 4.5 (Multi-User Data Isolation Testing)** but for Gmail connections and email commands.
*   Verify User A's Gmail actions/data are entirely separate from User B's.

This manual testing plan covers the core functionalities of the Atom agent, focusing on the end-to-end Google Calendar and Gmail integrations, including OAuth, secure token storage, and API interactions with real user context.
