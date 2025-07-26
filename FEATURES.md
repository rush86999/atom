## Features

Atom is designed to enhance your productivity through a comprehensive suite of AI-powered and integrated features.

### Core: AI-Powered Productivity Assistance
*   **Conversational AI Agent:** Interact with Atom through a chat interface to manage tasks, schedule meetings, get information, and control integrations. The agent's Natural Language Understanding (NLU) has been enhanced for more robust interpretation of commands related to task management (create, query, update using a Notion backend), calendar scheduling (handling durations, specific time queries), and can now perform semantic searches across meeting transcripts.
*   **User Onboarding:** Guided setup wizard to configure Atom, connect integrations, and set initial preferences (e.g., work day, default alarms, primary calendar).
*   **User Authentication:** Secure login system for protecting your data and configurations.
*   **Configurable Agent Settings:** Customize various aspects of the Atom agent's behavior and its interaction with integrated services.
*   **Wake Word Detection:** (Experimental) Initiate interaction with Atom using a spoken wake word (e.g., "Atom") for hands-free operation. This feature is implemented differently in the web and desktop versions:
    *   **Web Version:** When enabled in the settings, the web version continuously listens for the wake word using the browser's microphone and a WebSocket-based Speech-to-Text (STT) service. It requires the `NEXT_PUBLIC_AUDIO_PROCESSOR_URL` environment variable to be configured. A mock mode is also available for testing.
    *   **Desktop Version:** The desktop version uses a more resource-friendly approach. Wake word detection is triggered by a Tauri event, meaning it's not always on. When activated, it uses the `MediaRecorder` API to capture audio and sends it to a local WebSocket server for transcription and wake word detection.
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
*   **LLM-Powered Scheduling:** Use natural language to schedule meetings. For example, you can say "Find a time for a 30-minute meeting with Sarah and John to discuss the Q3 marketing plan." Atom will use a large language model to parse your request and then find an optimal time for the meeting.
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
    *   Unlock the knowledge in your past meetings. Transcripts stored in Notion (e.g., from live meeting processing or manual additions to a notes database) are processed into vector embeddings (e.g., using OpenAI models) and stored in a LanceDB vector database, associated with your user ID.
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
    *   Gmail Integration (AI-powered natural language email search and information extraction)
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
*   **Banking & Financial:**
    *   Plaid (Connect bank accounts, credit cards, investments for real-time financial data via secure APIs)
    *   Banking integrations for finance management features
*   **Contact Sync:**
    *   Google Contacts (Keep your contacts synchronized with Atom)
*   **Transcription Services:**
    *   Deepgram (High-quality transcription for audio notes and other audio inputs)
*   **Push Notifications:** Generic support for sending push notifications to keep users updated on calendar changes or important tasks.

### Finance Management (Voice-Powered & Wake Word Enabled)
Complete voice-activated finance management suite integrated with wake word "Atom" for natural language financial queries:

*   **Smart Net Worth Tracking:** Real-time net worth analysis with "Atom what's my net worth?" delivering complete financial overview across all connected accounts
*   **Intelligent Budget Management:** Create budgets via "Atom create dining budget for $400" with category analysis and variance tracking
*   **Advanced Spending Analytics:** AI-powered queries like "Atom where did I spend most money?" with detailed category breakdowns
*   **Goal Setting & Tracking:** Progress tracking with "Atom create emergency fund goal for $5000" including milestone alerts
*   **Portfolio Management:** Investment overview via "Atom show portfolio performance" with real-time holdings and allocation
*   **Natural Transaction Search:** Semantic search "Atom find Amazon purchases over $75 this quarter" across all transactions
*   **Multi-Account Integration:** Unified view across bank accounts, credit cards, and investment accounts via Plaid
*   **Voice Recognition:** Wake word "Atom" triggers finance commands for hands-free management
*   **Gmail Financial Insights:** Extract financial receipts and transactions from Gmail using AI-powered email analysis

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
    *   **Natural Language Email Search:** Ask the agent natural language questions to find emails (e.g., "find emails from Jane about the Q3 report sent last week"). The `atom-agent` uses an LLM (via `llm_email_query_understander.ts`) to parse your query into structured parameters, which are then used to construct a Gmail API compatible search string. This search is executed via a backend action that calls the Gmail API.
    *   **Targeted Information Extraction:** After identifying an email (e.g., through search or by providing an email ID), ask the agent to extract specific pieces of information (e.g., "What was the contract end date mentioned in this email?", "Extract the invoice number and amount from email ID [email_id]"). The `atom-agent` uses an LLM (via `extractInformationFromEmailBody` in `emailSkills.ts`) to read the email content (fetched via a backend action) and find the requested details. Accuracy depends on LLM capabilities and the clarity of the email content.
    *   **Agent Skills:** Core agent skills (`gmailSkills.ts`, `emailSkills.ts`) manage the NLU processing, interaction with LLMs, and calls to backend actions which interface with the Gmail API.
    *   **User Interface:**

### Complete Finance Management Suite (Voice-activated)
Atom provides a comprehensive personal finance management system that rivals leading finance apps, accessible through natural language voice commands and wake word activation.

**🎤 Voice-Activated Finance Commands**
Simply say "Atom" followed by any finance query for instant insights:
- **"Atom what's my net worth?"** - Complete financial overview across all connected accounts
- **"Atom show my budget"** - Detailed budget analysis with visual breakdowns  
- **"Atom how much did I spend on restaurants?"** - Category-specific spending insights
- **"Atom create retirement goal for $1M"** - Smart goal creation and progress tracking
- **"Atom find Amazon purchases this month"** - Natural language transaction search
- **"Atom compare dining budget vs actual"** - Budget vs spending analysis with recommendations

**💰 Core Finance Features**
*   **Real-time Net Worth Tracking**: Aggregate view of all financial accounts including bank balances, credit card debt, investment holdings, crypto assets, and retirement funds with real-time updates
*   **Smart Budget Management**: AI-powered budget creation and tracking across custom categories with predictive spending alerts and monthly analysis
*   **Comprehensive Transaction Analysis**: Natural language search across all transactions with merchant, amount, date, and category filtering
*   **Goal-Oriented Financial Planning**: Create, track, and optimize financial goals including emergency fund, retirement, major purchases, and debt payoff with milestone alerts
*   **Investment Portfolio Overview**: Real-time portfolio performance, asset allocation analysis, sector breakdown, and investment recommendations
*   **Spending Pattern Recognition**: AI identifies spending trends, unusual transactions, and provides personalized savings recommendations
*   **Monthly Financial Reports**: Automated comprehensive financial reports with income vs expenses, net worth changes, and budget performance

**🏦 Banking & Account Integration**
*   **Secure Bank Connection**: Connect all major banks, credit cards, investment accounts via Plaid for real-time financial data synchronization
*   **Multi-Account Financial Dashboard**: Unified view across checking, savings, credit cards, and investment accounts with AI-powered insights

*   **Slack Workspace Integration (Enhanced AI-Powered Querying & Interaction):**
    *   **Secure Connection:** Uses a Bot User OAuth Token (`ATOM_SLACK_BOT_TOKEN`) configured for the `atom-agent` service, with necessary permissions (scopes like `search:read`, `channels:history`, `users:read`, etc.).
    *   **Natural Language Message Search:** Ask the agent natural language questions to find Slack messages (e.g., "find messages from Bob about the project update in #general yesterday"). The `atom-agent` uses an LLM (via `llm_slack_query_understander.ts`) to parse your query into structured parameters. These are then used to construct a Slack API compatible search string (via `nlu_slack_helper.ts`), which is executed via a backend action calling Slack's `search.messages` API.
    *   **Targeted Information Extraction:** After identifying a message (e.g., via search or by providing a permalink/ID pair), ask the agent to extract specific information (e.g., "What was the deadline mentioned in this Slack message?"). The `atom-agent` uses an LLM (via `extractInformationFromSlackMessage` in `slackSkills.ts`) to read the message content (fetched via a backend action) and find the requested details.
    *   **Message Content Retrieval & Permalinks:** Agent skills can fetch detailed message content and permalinks, typically via backend actions that wrap Slack API calls like `conversations.history` (for specific messages if context is known, or `chat.getPermalink`).
    *   **Agent Skills:** Core agent skills (`slackQuerySkills.ts`, `slackSkills.ts`) manage NLU processing, LLM interactions, and calls to backend actions which interface with the Slack API.
    *   **Basic Operations:** Continues to support sending messages (to channels or DMs by name/ID) and listing channels.
    *   **Configuration:** Requires `ATOM_SLACK_BOT_TOKEN` with appropriate scopes. Refer to Slack integration guides for details on necessary scopes (e.g., `search:read`, `channels:read`, `groups:read`, `im:read`, `mpim:read`, `users:read`, `chat:write`). `ATOM_OPENAI_API_KEY` is also needed by the agent for LLM functionalities.
    *   **Developer Documentation:** (To be updated) Guide for Hasura Action setup for Slack and details on LLM prompts.

*   **Microsoft Teams Integration (Enhanced AI-Powered Chat Interaction & Delegated Permissions):**
    *   **Secure User-Contextual Connection:** Connect on behalf of the user via OAuth 2.0 (delegated permissions) to access their Microsoft Teams environment. User-specific tokens are securely stored and used for Graph API calls, typically via backend actions.
    *   **Natural Language Message Search:** Ask the agent natural language questions to find Teams messages (e.g., "find Teams messages from Alex about the Q1 budget in 'Strategy Chat' last week"). The `atom-agent` uses an LLM (via `llm_msteams_query_understander.ts`) to parse the query into structured parameters. These are then used to construct a Microsoft Graph KQL query string (via `nlu_msteams_helper.ts`), which is executed via a backend action calling the MS Graph Search API.
    *   **Targeted Information Extraction:** After identifying a message (e.g., via search or by providing message/context IDs), ask the agent to extract specific information (e.g., "What action items were assigned to me in this Teams message?"). The `atom-agent` uses an LLM (via `extractInformationFromMSTeamsMessage` in `msTeamsSkills.ts`) to read the message content (fetched via a backend action) and find the requested details.
    *   **Message Content Retrieval & Permalinks:** Agent skills can fetch detailed message content and web URLs (permalinks), typically via backend actions that wrap MS Graph API calls (e.g., getting a specific message, getting its webUrl).
    *   **Agent Skills:** Core agent skills (`msTeamsQuerySkills.ts`, `msTeamsSkills.ts`) manage NLU processing, LLM interactions, and calls to backend actions which interface with the Microsoft Graph API.
    *   **Existing Functionality:** Continues to support integration for calendar events and online meetings (details may vary based on app or delegated permissions for calendar access).
    *   **Configuration:** Requires Azure AD App Registration with appropriate delegated permissions (e.g., `Chat.Read`, `ChannelMessage.Read.All`, `User.Read`, `offline_access`). The `atom-agent` needs `ATOM_OPENAI_API_KEY` for LLM functionalities. Frontend/backend API routes for OAuth require `MSTEAMS_CLIENT_ID`, `MSTEAMS_CLIENT_SECRET`, etc. (Refer to `docs/msteams_integration_guide.md`).
    *   **Developer Documentation:** The `docs/msteams_integration_guide.md` provides details on Azure AD setup. (Further updates might be needed for backend action setup for messages and LLM prompt details).

### User Settings & Preferences
Tailor Atom to your specific needs with a range of customizable settings:
*   **General Preferences:** Configure core settings during onboarding and later, such as your typical workday hours, default alarm/reminder times, and primary calendar selection.
*   **Calendar Preferences:** Manage settings for connected calendars, choose your primary calendar for new events, and configure integration-specific options.
*   **Category Management:** Create, edit, and manage event categories, including their default attributes like color, priority, or associated tags.
*   **Autopilot Settings:** Fine-tune how Autopilot functions, including its schedule, aggressiveness in modifying events, and the types of events it should manage.
*   **Chat Meeting Preferences:** Define default preferences for meetings scheduled quickly via the chat interface, such as default duration or video conferencing options.
*   **Integration Management:** View the status of all connected third-party services, manage credentials, and enable/disable specific integrations.

This list is intended to be comprehensive. If you discover a feature not listed here, please consider contributing to our documentation!

### New Complex Use Cases

By combining multiple integrations, Atom can automate complex workflows and provide you with a powerful set of tools to manage your work and personal life. For more detailed information, please see our [New Use Cases Document](./NEW_USE_CASES.md).

*   **Proactive Project and Team Health Monitoring:** Monitor a project's health by combining data from project management, version control, communication, and calendar tools.
*   **Automated Competitor Analysis:** Automatically gather and analyze information about competitors from a variety of sources.
*   **Personalized Learning Assistant:** Create a personalized learning plan for the user based on their interests and learning history.

### Project Health Monitoring

*   **Proactive Project and Team Health Monitoring:** Monitor a project's health by combining data from project management, version control, communication, and calendar tools.

### Competitor Analysis

*   **Automated Competitor Analysis:** Automatically gather and analyze information about competitors from a variety of sources.

### Personalized Learning Assistant

*   **Personalized Learning Assistant:** Create a personalized learning plan for the user based on their interests and learning history.