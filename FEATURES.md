## Features

Atom is designed to enhance your productivity through a comprehensive suite of AI-powered and integrated features.

### Core: AI-Powered Productivity Assistance
*   **Conversational AI Agent:** Interact with Atom through a chat interface to manage tasks, schedule meetings, get information, and control integrations. The agent's Natural Language Understanding (NLU) has been enhanced for more robust interpretation of commands related to task management (create, query, update using a Notion backend), calendar scheduling (handling durations, specific time queries), and can now perform semantic searches across meeting transcripts.
*   **User Onboarding:** Guided setup wizard to configure Atom, connect integrations, and set initial preferences (e.g., work day, default alarms, primary calendar).
*   **User Authentication:** Secure login system for protecting your data and configurations.
*   **Configurable Agent Settings:** Customize various aspects of the Atom agent's behavior and its interaction with integrated services.
*   **Wake Word Detection:** (Experimental) Initiate interaction with Atom using a spoken wake word (e.g., "Atom") for hands-free operation. This feature can be enabled in settings and requires microphone permission. Its functionality depends on a configured external WebSocket-based Speech-to-Text (STT) service (configure via `NEXT_PUBLIC_AUDIO_PROCESSOR_URL`). A mock mode (enable via `NEXT_PUBLIC_MOCK_WAKE_WORD_DETECTION=true`) is available for testing the UI flow without a live STT service.
*   **Smart Meeting Preparation:** Proactively gathers relevant notes, emails, and tasks for your upcoming meetings. Example command: *"Atom, prepare me for my meeting with 'Project X' tomorrow."*
*   **Automated Weekly Digest:** Provides a summary of your past week's accomplishments (completed tasks, key meetings) and a preview of critical items for the upcoming week. Can be triggered on-demand or scheduled. Example command: *"Atom, what's my weekly digest?"*
*   **Intelligent Follow-up Suggester:** Analyzes meeting notes, transcripts, or project documents to identify and suggest potential action items, key decisions, and unresolved questions. Example command: *"Atom, suggest follow-ups for the 'Q3 Strategy discussion'."*

### Smart Scheduling & Calendar Management
Atom revolutionizes how you manage your time with a suite of AI-powered scheduling tools:
*   **AI-Powered Event Matching (Semantic Search & Templating):** Atom uses **LanceDB** and a two-stage AI process to understand your events. It matches new or queried events with past ones, turning your history into smart templates. This includes AI-driven query enhancement and accurate categorization of events, applying attributes like duration, priority, and color automatically.
*   **Automated Event Tagging & Categorization:** Events are intelligently categorized and tagged by AI or manually. This streamlines event creation and ensures consistent handling of similar events based on learned patterns. Users can manage event categories with custom attributes like color.
*   **Flexible Meeting Scheduling:**
    *   Easily create, edit, and manage calendar events with comprehensive support for attendees, recurrence settings, virtual meeting links (Zoom, Google Meet), event visibility, and reminders.
    *   Utilize user-friendly wizards for guided event creation and editing processes.
*   **Meeting Assist:**
    *   A dedicated wizard simplifies the setup of "meeting assists" for coordinating meetings, particularly useful when involving external participants.
    *   External users can submit their time preferences via a secure handshake link without needing an Atom account, facilitating easier scheduling across organizations.
*   **Autopilot Planning:** Let Atom's AI planner manage your schedule proactively. It can identify and apply features (based on your trained templates) to new and existing events, typically running before your workday begins or as configured. Autopilot settings are customizable.
*   **Customizable Time Preferences:** Define your preferred times for flexible meetings and other modifiable events, allowing Atom to schedule them according to your work patterns.
*   **Trainable Event Templates:** Teach Atom how to handle different types of events by creating templates. Customize attributes such as transparency, buffer times, priority, modifiable nature, tags, color, duration, and break types. You can also "untrain" or modify existing templates.
*   **Event Priority & Rating:** Set priorities for modifiable events to influence their placement on your calendar. Rate past events to provide feedback on your productivity, which Atom considers for future scheduling decisions.
*   **Configurable Smart Tags:** Apply specific settings to tags. These tags dictate how Atom applies features or attributes to new events that are either AI-tagged or manually tagged, enabling fine-grained control over event handling.
*   **Calendar Views:** View your schedule in a user-friendly calendar interface, offering clear visibility of your upcoming events and commitments.
*   **GPT-Powered Meeting Assistance:**
    *   Automatically generate meeting agendas based on event details or prompts.
    *   Summarize your daily availability to simplify scheduling conversations.
*   **Automated Action Item & Decision Logging:** Leveraging its summarization capabilities, Atom can process meeting transcripts (from live attendance or processed recordings) to identify and extract key decisions and action items. This structured information can be automatically saved into your Notion meeting notes, helping you keep track of important outcomes.
*   NLU for calendar event creation and querying is now more robust, understanding specific durations (e.g., "schedule for 45 minutes") and more precise time-based questions (e.g., "Am I free at 3 PM on Friday?").
*   **Event-Specific Time Preferences:** Set preferred meeting times for individual events, overriding global preferences where necessary.
*   **Follow-up Event Creation:** Quickly create follow-up events based on existing meetings or tasks, ensuring timely next steps.
*   **Task Scheduling (Future & Recurring)**: Atom can schedule tasks or actions for future execution. You can ask the agent to perform a task at a specific date and time, or set up recurring tasks (e.g., "remind me every Monday at 9 AM to check emails"). This uses a persistent, internal scheduling system (Agenda with MongoDB) to ensure tasks are reliably executed even if the system restarts.

### Task Management (Voice-Powered with Notion Backend)
Atom offers comprehensive voice-powered task management using a dedicated Notion database (configure via `ATOM_NOTION_TASKS_DATABASE_ID`). The agent understands natural language commands to create, query, and update tasks.
*   **Task Creation:** Create tasks by specifying descriptions, due dates (e.g., "tomorrow", "next Friday at 5pm"), priorities (e.g., "high", "low"), and list names (e.g., "work", "personal"). Example: "Atom, add 'Draft Q4 report' to my work list due next Friday, priority high." Atom parses these details and populates the corresponding fields in your Notion task database.
*   **Task Querying:** Ask about your tasks using various filters like date conditions ("today", "overdue", "this week"), priority, list name, status, or keywords in the description. Example: "Atom, what are my high priority work tasks due today?"
*   **Task Updates:** Modify existing tasks by referring to them (e.g., by name) and specifying the changes, such as marking them complete, changing due dates, or updating priorities. Example: "Atom, mark 'buy groceries' as done" or "Change the due date for 'Draft Q4 report' to next Monday."
*   **Flexible Task Properties:** Tasks are stored in Notion with properties like:
    *   `Task Description` (Title type in Notion)
    *   `Due Date` (Date type)
    *   `Status` (Select type, e.g., "To Do", "In Progress", "Done")
    *   `Priority` (Select type, e.g., "High", "Medium", "Low")
    *   `List Name` (Text type, for categorizing tasks like "Work", "Personal")
    *   `Notes` (Page content for additional details)
*   **Configuration:** Requires the `ATOM_NOTION_TASKS_DATABASE_ID` environment variable to be set to the ID of your Notion tasks database. You'll need to create this database in Notion with the suggested properties.

### Integrated Note-Taking & Research
Keep your knowledge organized and accessible with Atom's integrated capabilities:
*   **Note-Taking (Notion & Audio):** Create text notes directly. Audio notes can be generated from existing audio files (e.g., via URL) or by recording directly within Atom for in-person meetings (see below). All audio notes are automatically transcribed (e.g., using Deepgram), summarized (using OpenAI), and saved into Notion. Your notes can be searched, updated, and linked to tasks or calendar events.
*   **In-Person Meeting Audio Notes (Agent-Activated):**
    *   **Agent-Controlled Recording:** Users can ask the Atom agent (via voice or text commands like "Atom, start an audio note" or "Record my meeting discussion") to begin recording audio using their device's microphone. The agent can also be commanded to stop or cancel the recording.
    *   **Direct Microphone Capture:** This feature is designed for capturing discussions in physical meetings, personal voice memos, or any scenario where direct microphone input is needed.
    *   **Automated Processing:** Once the recording is stopped, the captured audio is automatically:
        *   Transcribed using Deepgram.
        *   Summarized by an AI model (e.g., OpenAI GPT) to extract key points, decisions, and action items.
        *   Saved as a new note in the user's configured Notion database, including the transcript, summary, and optionally a link to the raw audio file.
    *   **UI Feedback:** The client application provides UI feedback for recording status (e.g., "Recording...", "Processing...") when initiated or controlled by the agent.
    *   **Manual UI Recording:** A dedicated UI (e.g., an `AudioRecorder` component) also allows users to manually initiate, stop, and save microphone recordings directly without agent interaction.
*   **Multi-Agent Research System (Notion & LanceDB):** Initiate research projects based on simple queries. A lead AI agent decomposes your query into sub-tasks and assigns them to specialized sub-agents. These agents perform research (e.g., web searches, internal Notion searches using LanceDB for vector-based information retrieval) and log their findings in a dedicated Notion database. The lead agent then synthesizes this information into a comprehensive final report, also in Notion.
*   **Python API for Notes & Research:** Backend handlers and APIs for managing notes and research processes programmatically, including endpoints for handling direct audio uploads and processing.
*   **Searchable Meeting Archive (Semantic Search):**
    *   Unlock the knowledge in your past meetings. Transcripts stored in Notion (e.g., from live meeting processing or manual additions) are processed into vector embeddings (e.g., using OpenAI models) and stored in a LanceDB vector database, associated with your user ID.
    *   **Agent Interaction:** You can ask Atom natural language questions like, "What were the main points about the Q3 budget?" or "Find meetings where we discussed marketing collaborations."
    *   **Backend Process:** The Atom agent sends your query to a Python backend service. This service generates an embedding for your query (using an AI model like OpenAI) and then searches the LanceDB database for the most similar transcript chunks corresponding to your user ID.
    *   **Results:** Atom displays relevant meeting titles, dates, and links to the Notion pages containing the full context.
    *   **Dependencies:**
        *   A running LanceDB instance (configure its URI via `LANCEDB_URI`).
        *   An `OPENAI_API_KEY` for generating query embeddings and for the ingestion pipeline to embed transcripts.
        *   The Python backend service (e.g., `python-api-service` or `functions`, configured via `PYTHON_API_SERVICE_BASE_URL` for the `atom-agent`) must be operational and expose an endpoint like `/api/semantic_search_meetings` for querying.
        *   **Ingestion Pipeline:** A dedicated Ingestion Pipeline service (`ingestion-pipeline-service`) is now implemented. This service reads transcripts/notes from a configured Notion database (via `NOTION_TRANSCRIPTS_DATABASE_ID`), processes the text into chunks, generates embeddings using OpenAI, and stores them in LanceDB. It can be triggered via its API or run on a schedule. See `docs/ingestion_pipeline_guide.md` for setup and operational details. This pipeline ensures that data in Notion is made available for semantic search.

### Automation & AI Capabilities
Leverage Atom's advanced automation and AI functionalities:
*   **Autopilot (Scheduled Actions):** As part of Smart Scheduling, Autopilot proactively manages your schedule by applying learned features and templates to events.
*   **GPT-Powered Summaries:** Create concise summaries of information, such as a series of notes or research findings, over a defined period.
*   **Event Feature Application Engine:** A backend system (potentially utilizing Optaplanner) responsible for applying defined features, rules, and templates to calendar events, ensuring consistent and intelligent scheduling.
*   **Event-to-Vector Processing:** For semantic search and event matching, Atom processes event information into vectors, enabling more accurate matching and templating (uses LanceDB).
*   **Live Meeting Attendance:** (Backend Implemented, Experimental UI)
    *   Atom can "attend" live meetings (or capture desktop audio) to perform tasks like (eventual) automated note-taking or action item identification.
    *   **Frontend UI:** The UI in Atom Agent Settings allows users to:
        *   Select an audio source (from devices listed by the Python worker).
        *   Specify meeting details (platform, ID, Notion title).
        *   Start, monitor (viewing status, previews, duration), and stop attendance tasks.
    *   **Backend Worker:** A dedicated Python (FastAPI) worker service (`live-meeting-worker`) is now implemented and containerized.
        *   It exposes an API for listing audio devices, starting, stopping, and querying the status of attendance tasks. (See `atomic-docker/docs/live-meeting-attendance-api.md` for API details).
        *   Currently, the worker's audio processing is a placeholder (simulates audio capture and data generation). Real-time STT and advanced note-taking are future enhancements for this worker.
        *   The frontend communicates with this worker via the URL specified in `NEXT_PUBLIC_LIVE_MEETING_WORKER_URL`.
    *   **Audio Setup:** Correct audio routing by the user is crucial for capturing desired audio. Refer to `atomic-docker/docs/live-meeting-attendance-setup.md`.
    *   **Note:** The previous experimental Zoom C++ SDK agent details are less relevant to this new Python worker, which currently uses `sounddevice` for audio device listing and would use it for capture.
*   **Audio Processing:** Transcribe audio from various sources for notes, commands, or meeting recordings. The Live Meeting Attendance worker will be a key component for this.

### Dependencies & Setup Notes for Advanced Features

To leverage some of Atom's more advanced capabilities, specific setup and configurations are required:

*   **Notion Task Management:**
    *   Create a dedicated database in your Notion workspace for tasks.
    *   This database should have the following properties (case-sensitive names recommended for easier integration, types are Notion property types):
        *   `Task Description` (Type: `Title`) - *Required*
        *   `Due Date` (Type: `Date`) - *Optional*
        *   `Status` (Type: `Select` with options like "To Do", "In Progress", "Done", "Blocked", "Cancelled") - *Required, defaults to "To Do"*
        *   `Priority` (Type: `Select` with options like "High", "Medium", "Low") - *Optional*
        *   `List Name` (Type: `Text`) - *Optional, for task categorization*
    *   Set the `ATOM_NOTION_TASKS_DATABASE_ID` environment variable to the ID of this Notion database.

*   **Meeting Transcript Semantic Search:**
    *   Ensure your meeting transcripts are being stored in Notion (e.g., via Atom's live meeting processing or manual additions to a notes database).
    *   Set up a LanceDB instance. This can be a local directory (e.g., `./lance_db`) or a connection to a remote LanceDB service.
    *   Configure the `LANCEDB_URI` environment variable with the connection string for your LanceDB instance.
    *   An `OPENAI_API_KEY` is required for generating the text embeddings stored in LanceDB.
    *   The Python backend service (`python_api_service`) must be running and correctly configured, as it handles the embedding storage and search query processing.

*   **Wake Word Detection:**
    *   This feature is marked as `(Experimental)`.
    *   It requires the setup of an external WebSocket-based Speech-to-Text (STT) service, referred to as the `audio_processor`. The URL for this service must be configured via the `NEXT_PUBLIC_AUDIO_PROCESSOR_URL` environment variable for the frontend application.
    *   A mock mode can be enabled by setting `NEXT_PUBLIC_MOCK_WAKE_WORD_DETECTION=true`, which simulates wake word detection for UI testing purposes without needing a live STT service.
    *   The feature can be toggled on/off in the Atom Agent Configuration settings.

*   **Live Meeting Attendance:**
    *   This feature is marked as `(Experimental UI Implemented)`.
    *   Its ability to reliably capture meeting audio (not just microphone input) is highly dependent on the user's operating system and system audio configuration. Users typically need to route their meeting application's output audio to a virtual input device that Atom can then listen to. Refer to `atomic-docker/docs/live-meeting-attendance-setup.md` for audio setup guidance.
    *   The frontend UI (in settings) allows users to refresh and select an audio device (listed by the `live_meeting_worker`). The URL for the worker's device listing endpoint should be configured via `NEXT_PUBLIC_LIVE_MEETING_WORKER_URL`.
    *   Initiating and monitoring tasks is supported via the UI, but full end-to-end functionality relies on correctly configured backend services (API handler, Kafka, live meeting worker, and potentially a fully implemented Zoom C++ SDK helper) and secure API key management.

### Integrations
Atom connects with a wide range of third-party services to create a unified productivity hub:
*   **File Storage & Management:**
    *   Dropbox (Connect your Dropbox account to list, search, and ingest files.)
    *   Google Drive (Connect your Google Drive account to list, search, and ingest files.)
*   **Project Management:**
    *   Trello (Connect your Trello account to manage your boards, lists, and cards.)
*   **CRM:**
    *   HubSpot (Manage contacts, sync activities)
    *   Salesforce (Connect your Salesforce account to manage your contacts, accounts, and opportunities.)
*   **Financial & Payments:**
    *   Stripe (List payments, potentially link to projects or clients)
    *   QuickBooks (Manage invoices, link financial data)
    *   Xero (Connect your Xero account to manage your invoices, bills, and contacts.)
*   **Social Media:**
    *   Twitter (Connect your Twitter account to view your timeline, post tweets, and search for tweets.)
    *   LinkedIn (Schedule posts to your LinkedIn profile.)
*   **Personal Assistant:**
    *   Weather (Get the current weather for any location.)
    *   News (Get the top headlines from a variety of news sources.)
    *   Reminders (Set reminders for yourself.)
*   **Calendar Providers:**
    *   Google Calendar (Full sync via OAuth 2.0, with token management for agent interactions. Ensure redirect URI `/api/atom/auth/calendar/callback` is configured in Google Cloud Console.)
    *   Microsoft Teams (Integration for calendar events and online meetings)
*   **Communication & Collaboration:**
    *   Slack (Send messages, list channels, receive notifications)
    *   Email (General email functionalities for sending notifications, meeting invites, and summaries)
*   **Video Conferencing:**
    *   Zoom (Create, delete, get, and update meetings; OAuth 2.0 for secure integration)
    *   Google Meet (Agent capabilities for managing meeting links and details)
*   **Note-Taking & Knowledge Management:**
    *   Notion (Primary integration for notes, research databases, and knowledge organization)
*   **Scheduling Services:**
    *   Calendly (Integration to coordinate external scheduling)
*   **Automation Platforms:**
    *   Zapier (Connect Atom with a vast ecosystem of other apps and services)
*   **Contact Sync:**
    *   Google Contacts (Keep your contacts synchronized with Atom)
*   **Transcription Services:**
    *   Deepgram (High-quality transcription for audio notes and other audio inputs)
*   **Push Notifications:** Generic support for sending push notifications to keep users updated on calendar changes or important tasks.

### Use Cases
By combining multiple integrations, Atom can automate complex workflows and provide you with a powerful set of tools to manage your work and personal life.

*   **Social Media Manager:**
    *   Schedule posts to be published on Twitter and LinkedIn at a later time.
    *   Monitor your Twitter mentions and automatically add them to a Trello board for review.
    *   Create a new Salesforce lead from a Twitter user who has expressed interest in your product or service.
    *   Get analytics for a specific tweet, such as likes, retweets, and replies.
*   **Sales Manager:**
    *   Create a new Xero invoice from a Salesforce opportunity that has been marked as "Closed Won".
    *   Create a new Trello card for each new Salesforce opportunity, so you can track its progress through your sales pipeline.
    *   Create a new Salesforce contact from a Xero contact.
    *   Get a list of all open opportunities for a specific account.
*   **Project Manager:**
    *   Create a new Google Drive folder for each new Trello board, so you can keep all your project files organized.
    *   Automatically upload Trello card attachments to the corresponding Google Drive folder.
    *   Create a new Trello board from a Google Drive folder.
    *   Automatically create a Trello card for each new file added to a Google Drive folder.
*   **Gmail Account Integration (Read-Only & AI-Powered Querying):**
    *   **Secure Connection:** Connect your personal Gmail account via OAuth 2.0 for secure, read-only access. Tokens are encrypted at rest.
    *   **Natural Language Email Search:** Ask the agent natural language questions to find emails (e.g., "find emails from Jane about the Q3 report sent last week"). The `atom-agent` uses an LLM (via `llm_email_query_understander.ts`) to parse your query into structured parameters, which are then used to construct a Gmail API compatible search string. This search is executed via a Hasura Action that calls the Gmail API.
    *   **Targeted Information Extraction:** After identifying an email (e.g., through search or by providing an email ID), ask the agent to extract specific pieces of information (e.g., "What was the contract end date mentioned in this email?", "Extract the invoice number and amount from email ID [email_id]"). The `atom-agent` uses an LLM (via `extractInformationFromEmailBody` in `emailSkills.ts`) to read the email content (fetched via a Hasura Action) and find the requested details. Accuracy depends on LLM capabilities and the clarity of the email content.
    *   **Agent Skills:** Core agent skills (`gmailSkills.ts`, `emailSkills.ts`) manage the NLU processing, interaction with LLMs, and calls to Hasura Actions which interface with the Gmail API.
    *   **User Interface:**
        *   The main "Google Account" connection in Settings now includes `gmail.readonly` scope. Reconnecting may be necessary if previously connected for Calendar only.
        *   (Future) A proof-of-concept UI for direct Gmail searching could be developed.
    *   **Dependencies & Setup:** Requires `ATOM_OPENAI_API_KEY` (or similar) for the `atom-agent`'s LLM utilities. The Hasura backend must be configured with appropriate Google Cloud credentials and handling for user-specific OAuth tokens with Gmail scopes.
    *   **Developer Documentation:** (To be updated) Guide for Hasura Action setup for Gmail and details on the LLM prompts used for query understanding and information extraction.

*   **Slack Workspace Integration (Enhanced AI-Powered Querying & Interaction):**
    *   **Secure Connection:** Uses a Bot User OAuth Token (`ATOM_SLACK_BOT_TOKEN`) configured for the `atom-agent` service, with necessary permissions (scopes like `search:read`, `channels:history`, `users:read`, etc.).
    *   **Natural Language Message Search:** Ask the agent natural language questions to find Slack messages (e.g., "find messages from Bob about the project update in #general yesterday"). The `atom-agent` uses an LLM (via `llm_slack_query_understander.ts`) to parse your query into structured parameters. These are then used to construct a Slack API compatible search string (via `nlu_slack_helper.ts`), which is executed via a Hasura Action calling Slack's `search.messages` API.
    *   **Targeted Information Extraction:** After identifying a message (e.g., via search or by providing a permalink/ID pair), ask the agent to extract specific information (e.g., "What was the deadline mentioned in this Slack message?"). The `atom-agent` uses an LLM (via `extractInformationFromSlackMessage` in `slackSkills.ts`) to read the message content (fetched via a Hasura Action) and find the requested details.
    *   **Message Content Retrieval & Permalinks:** Agent skills can fetch detailed message content and permalinks, typically via Hasura Actions that wrap Slack API calls like `conversations.history` (for specific messages if context is known, or `chat.getPermalink`).
    *   **Agent Skills:** Core agent skills (`slackQuerySkills.ts`, `slackSkills.ts`) manage NLU processing, LLM interactions, and calls to Hasura Actions which interface with the Slack API.
    *   **Basic Operations:** Continues to support sending messages (to channels or DMs by name/ID) and listing channels.
    *   **Configuration:** Requires `ATOM_SLACK_BOT_TOKEN` with appropriate scopes. Refer to Slack integration guides for details on necessary scopes (e.g., `search:read`, `channels:read`, `groups:read`, `im:read`, `mpim:read`, `users:read`, `chat:write`). `ATOM_OPENAI_API_KEY` is also needed by the agent for LLM functionalities.
    *   **Developer Documentation:** (To be updated) Guide for Hasura Action setup for Slack and details on LLM prompts.

*   **Microsoft Teams Integration (Enhanced AI-Powered Chat Interaction & Delegated Permissions):**
    *   **Secure User-Contextual Connection:** Connect on behalf of the user via OAuth 2.0 (delegated permissions) to access their Microsoft Teams environment. User-specific tokens are securely stored (e.g., in `user_tokens` table) and used for Graph API calls, typically via Hasura Actions.
    *   **Natural Language Message Search:** Ask the agent natural language questions to find Teams messages (e.g., "find Teams messages from Alex about the Q1 budget in 'Strategy Chat' last week"). The `atom-agent` uses an LLM (via `llm_msteams_query_understander.ts`) to parse the query into structured parameters. These are then used to construct a Microsoft Graph KQL query string (via `nlu_msteams_helper.ts`), which is executed via a Hasura Action calling the MS Graph Search API.
    *   **Targeted Information Extraction:** After identifying a message (e.g., via search or by providing message/context IDs), ask the agent to extract specific information (e.g., "What action items were assigned to me in this Teams message?"). The `atom-agent` uses an LLM (via `extractInformationFromMSTeamsMessage` in `msTeamsSkills.ts`) to read the message content (fetched via a Hasura Action) and find the requested details.
    *   **Message Content Retrieval & Permalinks:** Agent skills can fetch detailed message content and web URLs (permalinks), typically via Hasura Actions that wrap MS Graph API calls (e.g., getting a specific message, getting its webUrl).
    *   **Agent Skills:** Core agent skills (`msTeamsQuerySkills.ts`, `msTeamsSkills.ts`) manage NLU processing, LLM interactions, and calls to Hasura Actions which interface with the Microsoft Graph API.
    *   **Existing Functionality:** Continues to support integration for calendar events and online meetings (details may vary based on app or delegated permissions for calendar access).
    *   **Configuration:** Requires Azure AD App Registration with appropriate delegated permissions (e.g., `Chat.Read`, `ChannelMessage.Read.All`, `User.Read`, `offline_access`). The `atom-agent` needs `ATOM_OPENAI_API_KEY` for LLM functionalities. Frontend/backend API routes for OAuth require `MSTEAMS_CLIENT_ID`, `MSTEAMS_CLIENT_SECRET`, etc. (Refer to `docs/msteams_integration_guide.md`).
    *   **Developer Documentation:** The `docs/msteams_integration_guide.md` provides details on Azure AD setup. (Further updates might be needed for Hasura Action setup for messages and LLM prompt details).

### User Settings & Preferences
Tailor Atom to your specific needs with a range of customizable settings:
*   **General Preferences:** Configure core settings during onboarding and later, such as your typical workday hours, default alarm/reminder times, and primary calendar selection.
*   **Calendar Preferences:** Manage settings for connected calendars, choose your primary calendar for new events, and configure integration-specific options.
*   **Category Management:** Create, edit, and manage event categories, including their default attributes like color, priority, or associated tags.
*   **Autopilot Settings:** Fine-tune how Autopilot functions, including its schedule, aggressiveness in modifying events, and the types of events it should manage.
*   **Chat Meeting Preferences:** Define default preferences for meetings scheduled quickly via the chat interface, such as default duration or video conferencing options.
*   **Integration Management:** View the status of all connected third-party services, manage credentials, and enable/disable specific integrations.

This list is intended to be comprehensive. If you discover a feature not listed here, please consider contributing to our documentation!
