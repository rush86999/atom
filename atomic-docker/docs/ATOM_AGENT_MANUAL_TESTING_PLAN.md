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
3.  **Placeholder Interactivity (Non-functional):**
    *   **Action:** Click the "Connect..." and "Save..." buttons.
    *   **Expected Result:** Nothing functional should happen (e.g., no actual connection attempts). Console logs (if any were added in the placeholder functions in `AtomAgentSettings.tsx`) might appear in the browser's developer console, which is acceptable for this stage.

This manual testing plan covers the core functionalities of the Atom agent as implemented with mock skills and UI placeholders.
