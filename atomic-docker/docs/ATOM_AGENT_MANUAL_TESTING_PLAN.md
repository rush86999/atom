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
    *   **Action (Google Calendar):** See "Real Google Calendar Integration Testing" below for the "Connect/Disconnect Google Calendar" buttons.

## 4. Real Google Calendar Integration Testing

This section details testing the actual OAuth flow with Google Calendar and subsequent API calls (which are currently expected to fail due to mock tokens being used by the skills, but the flow itself can be tested).

### 4.1. OAuth Flow Testing

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
    *   **Action:** With the status showing "Connected", click the "Disconnect Google Calendar" button.
    *   **Expected Result:** A success message "Google Calendar disconnected successfully (mocked)." should be displayed. The UI should update to "Status: Not Connected", and the "Connect Google Calendar" button should reappear.

### 4.2. Chat Interface - Calendar Commands (Post OAuth Attempt)

After successfully completing the "Grant Consent" step in the OAuth Flow Testing (even though the tokens aren't fully stored and used by skills yet):

1.  **List Events Command:**
    *   **Action:** In the chat interface, type `list events` and send.
    *   **Expected Result:** Atom should respond with: "Could not retrieve calendar events. Please ensure your Google Calendar is connected in settings and try again, or there might be no upcoming events."
    *   **Reasoning:** This is because `calendarSkills.ts` currently uses `mock_access_token_from_storage` which is invalid for actual API calls. The API call will fail (likely with an "invalid_grant" or similar error logged in the server console by `calendarSkills.ts`), and the skill will return an empty array, leading to this message from `handler.ts`.
2.  **Create Event Command:**
    *   **Action:** In the chat interface, type `create event {"summary":"Atom Test Event","startTime":"2024-12-01T10:00:00Z","endTime":"2024-12-01T11:00:00Z"}` (use valid future ISO dates/times).
    *   **Expected Result:** Atom should respond with: "Failed to create calendar event. Failed to create event with Google Calendar: invalid_grant" (or similar error message from the API call failure).
    *   **Reasoning:** Similar to listing events, the mock token will cause the event creation API call to fail.

### 4.3. Important Note for Testers

*   **Actual event listing/creation via chat commands is NOT expected to work at this stage.** The `calendarSkills.ts` functions are making calls to the Google Calendar API, but they are using placeholder mock tokens (`mock_access_token_from_storage`) for these calls because the real tokens obtained from the OAuth flow are not yet securely stored and retrieved by these skill functions.
*   The purpose of the "Chat Interface - Calendar Commands (Post OAuth Attempt)" tests is to verify that the OAuth flow *attempt* (connection showing in settings) is followed by the skills *attempting* to use tokens, even if those attempts currently fail due to the mock token values. This confirms the basic wiring up to the point of API call attempts.
*   You should see error messages in the **server-side console** (where you ran `npm run dev`) originating from `calendarSkills.ts`, indicating failed Google API calls (e.g., "invalid_grant", "Login Required").

This manual testing plan covers the core functionalities of the Atom agent as implemented with mock skills and UI placeholders, as well as the initial (partially mocked) Google Calendar OAuth flow.

## 5. Advanced Productivity Skills Testing (Conceptual & Mocked Data)

This section outlines tests for newly implemented productivity skills. For initial manual testing, these will rely on:
*   Correct NLU parsing (conceptual: assume NLU correctly identifies intent and entities based on training phrases).
*   Mocked responses from underlying data services (Notion search, email search, LLM analysis) to verify the agent's orchestration and response formatting logic.
*   Actual data retrieval will depend on the live integration and robustness of those underlying services.

### 5.1. Smart Meeting Preparation (`PrepareForMeeting`)

**Prerequisites:**
*   A few mock calendar events in the user's calendar for different days/times with varied summaries and attendees.
*   Conceptual mock data for:
    *   Notion pages (titles, URLs, brief snippets) that would be relevant to meeting titles/keywords.
    *   Emails (subjects, senders, brief snippets) relevant to meeting titles/attendees.
    *   Notion tasks (descriptions, due dates, statuses) relevant to meeting titles.
*   Set `OPENAI_API_KEY` in environment if any part of this skill (even sub-components like semantic search in Notion if it uses it) relies on it. (Note: The V1 `PrepareForMeeting` skill itself does not directly call an LLM).

**Test Cases:**

1.  **Prepare for a Specific Upcoming Meeting:**
    *   **Action:** Type `Atom, prepare me for my meeting about "Team Sync Q3 Planning"` (assuming "Team Sync Q3 Planning" is a mock event).
    *   **Expected NLU (Conceptual):** `intent: "PrepareForMeeting"`, `entities: {"meeting_identifier": "Team Sync Q3 Planning"}`.
    *   **Expected Result:** Atom should respond with:
        *   Confirmation of the target meeting (summary, date/time).
        *   A list of 2-3 mock relevant Notion documents (title, URL, snippet).
        *   A list of 2-3 mock relevant recent emails (subject, sender, snippet).
        *   A list of 2-3 mock relevant open Notion tasks (description, due date, status).
        *   If any data source returns an error or no items, this should be gracefully indicated.

2.  **Prepare for "Next Meeting":**
    *   **Action:** Type `Atom, get me ready for my next meeting.`
    *   **Expected NLU (Conceptual):** `intent: "PrepareForMeeting"`, `entities: {"meeting_identifier": "next meeting"}` (or similar).
    *   **Expected Result:** Atom identifies the soonest upcoming mock meeting and provides a preparation summary for it, similar to the above.

3.  **Meeting Not Found:**
    *   **Action:** Type `Atom, prepare for "NonExistent Meeting"`.
    *   **Expected NLU (Conceptual):** `intent: "PrepareForMeeting"`, `entities: {"meeting_identifier": "NonExistent Meeting"}`.
    *   **Expected Result:** Atom responds with a message like "Sorry, I couldn't find a meeting matching 'NonExistent Meeting'."

4.  **Partial Data Availability:**
    *   **Setup:** Configure mocks so that (e.g.) Notion search returns results, but email search returns an error or no results.
    *   **Action:** Type `Atom, prep for "Team Sync Q3 Planning"`.
    *   **Expected Result:** Atom provides preparation details from Notion and tasks (if any), and includes a message like "Could not fetch relevant emails at this time" or "No specific recent emails found."

### 5.2. Automated Weekly Digest (`GenerateWeeklyDigest`)

**Prerequisites:**
*   Mock data for:
    *   Notion tasks with various statuses ("Done", "In Progress") and `last_edited_time` or conceptual "Completed At" dates spanning "this week" and "last week".
    *   Calendar events for "this week" and "last week" (some significant, some minor).
    *   Notion tasks with "High" priority due "next week".
    *   Calendar events for "next week" (some significant).
*   Set `ATOM_NOTION_TASKS_DATABASE_ID` environment variable.

**Test Cases:**

1.  **Digest for "This Week":**
    *   **Action:** Type `Atom, what's my weekly digest?` (or `... for this week`).
    *   **Expected NLU (Conceptual):** `intent: "GenerateWeeklyDigest"`, `entities: {"time_period": "this week"}` (or default).
    *   **Expected Result:** Atom responds with a formatted digest for the current week (Mon - current day, or Mon - Fri if past Friday), including:
        *   A section for "Accomplishments" listing mock completed tasks.
        *   A section for "Key Meetings Attended" listing mock significant meetings.
        *   A section for "Focus for Next Period" listing mock high-priority upcoming tasks and significant meetings.
        *   Graceful messages if any section has no items.

2.  **Digest for "Last Week":**
    *   **Action:** Type `Atom, show me last week's digest`.
    *   **Expected NLU (Conceptual):** `intent: "GenerateWeeklyDigest"`, `entities: {"time_period": "last week"}`.
    *   **Expected Result:** Atom responds with a formatted digest for the previous full week (Mon - Sun), structured similarly to the "this week" digest.

3.  **No Data for Some Sections:**
    *   **Setup:** Configure mocks so that, e.g., no tasks were completed, or no critical items are upcoming.
    *   **Action:** Type `Atom, weekly digest for this week`.
    *   **Expected Result:** The digest should still be generated, with messages like "No specific tasks marked completed this period" or "No high-priority tasks specifically logged for next period yet."

4.  **Error in Data Fetching:**
    *   **Setup:** Configure a mock for one of the underlying services (e.g., `queryNotionTasks`) to return an error.
    *   **Action:** Type `Atom, my weekly digest`.
    *   **Expected Result:** Atom should still attempt to generate the digest with data from other sources and include an error message for the failed part (e.g., "⚠️ Issues encountered: Could not fetch completed tasks.").

### 5.3. Intelligent Follow-up Suggester (`SuggestFollowUps`)

**Prerequisites:**
*   Set `OPENAI_API_KEY` environment variable (as the skill now makes real calls, though for manual testing, the LLM's actual output quality isn't the primary focus, rather the agent's handling of *some* structured response).
*   Mock data for:
    *   A Notion page (e.g., "Meeting Notes - Project Phoenix Q1") with text containing clear (mock) action items, decisions, and questions.
    *   A few Notion tasks, some of which might vaguely match the mock action items.
*   Set `ATOM_NOTION_TASKS_DATABASE_ID`.

**Test Cases:**

1.  **Suggest Follow-ups for a Meeting (Notion Notes Found):**
    *   **Setup:** Ensure `searchNotionRaw` mock will return the mock Notion page content when queried about "Project Phoenix Q1 meeting".
    *   **Action:** Type `Atom, suggest follow-ups for the Project Phoenix Q1 meeting`.
    *   **Expected NLU (Conceptual):** `intent: "SuggestFollowUps"`, `entities: {"context_identifier": "Project Phoenix Q1 meeting", "context_type": "meeting"}`.
    *   **Expected Result:**
        *   Atom indicates it's analyzing notes for "Meeting: Meeting Notes - Project Phoenix Q1...".
        *   The response should list:
            *   🎯 Action Items: (e.g., "Alice to update roadmap (Assignee: Alice) - [Consider creating a task]")
            *   ⚖️ Key Decisions: (e.g., "Q2 budget approved")
            *   ❓ Open Questions: (e.g., "When is Phase 2 starting?")
        *   If mock `queryNotionTasks` finds a match for an action, it should state `(Possibly related to existing task: ...)`

2.  **Suggest Follow-ups (Context Document Not Found):**
    *   **Setup:** Ensure `searchNotionRaw` (and `findTargetMeeting` if "last meeting" is used) returns no relevant document for the context.
    *   **Action:** Type `Atom, what are the follow-ups for "Unknown Project X meeting"?`
    *   **Expected Result:** Atom responds with a message like "Sorry, I couldn't find a document or meeting notes for 'Unknown Project X meeting' to analyze." or similar error from the skill.

3.  **Suggest Follow-ups (LLM Analysis Returns No Items):**
    *   **Setup:** `searchNotionRaw` returns a document, but the (mocked or real if permissive) `analyzeTextForFollowUps` returns empty arrays for actions, decisions, and questions.
    *   **Action:** Type `Atom, suggest follow-ups for "Vague Meeting Notes"`.
    *   **Expected Result:** Atom responds with a message like "No specific action items, decisions, or questions were identified for follow-up from the provided context for 'Vague Meeting Notes'."

4.  **Suggest Follow-ups (LLM Analysis Fails):**
    *   **Setup:** `searchNotionRaw` returns a document, but `analyzeTextForFollowUps` is mocked to return an error (e.g., API key issue, LLM error).
    *   **Action:** Type `Atom, suggest follow-ups for "Meeting with LLM error"`.
    *   **Expected Result:** Atom includes an error message in its response, e.g., "⚠️ Issues encountered: LLM analysis failed: OpenAI API key not configured." or similar.

5.  **Suggest Follow-ups (Action Item Matches Existing Task):**
    *   **Setup:**
        *   `searchNotionRaw` returns notes with "Action: Bob to send proposal".
        *   `analyzeTextForFollowUps` mock extracts this action.
        *   `queryNotionTasks` mock returns an existing task like "Bob send Q3 proposal" when queried with keywords from the action.
    *   **Action:** Type `Atom, follow-ups for "Proposal Meeting"`.
    *   **Expected Result:** The action item "Bob to send proposal" should be listed with an indication that a related task exists, e.g., `(Possibly related to existing task: Bob send Q3 proposal - ID: task123)`.

This new section provides a framework for manually testing the more complex, AI-driven skills.
