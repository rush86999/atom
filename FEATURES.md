## Features

Atom is designed to enhance your productivity through a comprehensive suite of AI-powered and integrated features.

### Core: AI-Powered Productivity Assistance
*   **Conversational AI Agent:** Interact with Atom through a chat interface to manage tasks, schedule meetings, get information, and control integrations. The agent's Natural Language Understanding (NLU) has been enhanced for more robust interpretation of commands related to task management (create, query, update using a Notion backend), calendar scheduling (handling durations, specific time queries), and can now perform semantic searches across meeting transcripts.
*   **User Onboarding:** Guided setup wizard to configure Atom, connect integrations, and set initial preferences (e.g., work day, default alarms, primary calendar).
*   **User Authentication:** Secure login system for protecting your data and configurations.
*   **Configurable Agent Settings:** Customize various aspects of the Atom agent's behavior and its interaction with integrated services.
*   **Wake Word Detection:** (If confirmed as fully functional) Initiate interaction with Atom using a spoken wake word for hands-free operation.
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
Atom now offers comprehensive voice-powered task management, using a dedicated Notion database that you configure.
*   **Task Creation:** Easily create new tasks using natural language (e.g., "Atom, add 'Draft Q4 report' to my work list due next Friday"). Atom captures the description, due date/time, priority, and can assign it to a specific list.
*   **Task Querying:** Ask Atom about your tasks with various filters. For example: "What are my tasks for today?", "Show me overdue items on my shopping list," or "List high priority work tasks."
*   **Task Updates:** Modify existing tasks using voice commands, such as marking them as complete (e.g., "Atom, mark 'buy groceries' as done") or changing their properties.
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
*   **Note-Taking (Notion & Audio):** Create text and audio notes directly. Audio notes are automatically transcribed (e.g., using Deepgram) and saved, typically within Notion. Your notes can be searched, updated, and linked to tasks or calendar events.
*   **Multi-Agent Research System (Notion & LanceDB):** Initiate research projects based on simple queries. A lead AI agent decomposes your query into sub-tasks and assigns them to specialized sub-agents. These agents perform research (e.g., web searches, internal Notion searches using LanceDB for vector-based information retrieval) and log their findings in a dedicated Notion database. The lead agent then synthesizes this information into a comprehensive final report, also in Notion.
*   **Python API for Notes & Research:** Backend handlers and APIs for managing notes and research processes programmatically.
*   **Searchable Meeting Archive (Semantic Search):**
    *   Unlock the knowledge in your past meetings. Transcripts stored in Notion (e.g., from live meeting processing or other sources) can be automatically converted into vector embeddings using AI models (like OpenAI).
    *   These embeddings are stored in a LanceDB vector database, enabling powerful semantic search capabilities.
    *   You can ask Atom natural language questions like, "What were the main points about the Q3 budget?" or "Find meetings where we discussed marketing collaborations," and Atom will search the content of your transcripts to find the most relevant discussions.
    *   **Dependencies:** This feature requires a running LanceDB instance (configure via `LANCEDB_URI`), an `OPENAI_API_KEY` for generating embeddings, and the Python backend service to be operational.

### Automation & AI Capabilities
Leverage Atom's advanced automation and AI functionalities:
*   **Autopilot (Scheduled Actions):** As part of Smart Scheduling, Autopilot proactively manages your schedule by applying learned features and templates to events.
*   **GPT-Powered Summaries:** Create concise summaries of information, such as a series of notes or research findings, over a defined period.
*   **Event Feature Application Engine:** A backend system (potentially utilizing Optaplanner) responsible for applying defined features, rules, and templates to calendar events, ensuring consistent and intelligent scheduling.
*   **Event-to-Vector Processing:** For semantic search and event matching, Atom processes event information into vectors, enabling more accurate matching and templating (uses LanceDB).
*   **Live Meeting Attendance:** (If confirmed as fully functional) Atom can "attend" live meetings to perform tasks like automated note-taking or action item identification (details on this capability would be needed based on implementation).
*   **Audio Processing:** Transcribe audio from various sources for notes, commands, or meeting recordings.

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
    *   This feature is marked as `(If confirmed as fully functional)`.
    *   It requires the setup of an external WebSocket-based Speech-to-Text (STT) service, referred to as the `audio_processor`. The URL for this service must be configured via `AUDIO_PROCESSOR_URL`. The implementation or specific choice of this STT service is currently up to the user.

*   **Live Meeting Attendance:**
    *   This feature is also marked as `(If confirmed as fully functional)`.
    *   Its ability to reliably capture meeting audio (not just microphone input) is highly dependent on the user's operating system and system audio configuration. Users typically need to route their meeting application's output audio to a virtual input device that Atom can then listen to. Detailed platform-specific guides for this audio routing are recommended but not yet part of this documentation.

### Integrations
Atom connects with a wide range of third-party services to create a unified productivity hub:
*   **Calendar Providers:**
    *   Google Calendar (Full sync, watch for changes via push notifications, OAuth 2.0 for secure access)
    *   Microsoft Teams (Integration for calendar events and online meetings)
*   **Communication & Collaboration:**
    *   Slack (Send messages, list channels, receive notifications)
    *   Email (General email functionalities for sending notifications, meeting invites, and summaries)
*   **CRM:**
    *   HubSpot (Manage contacts, sync activities)
*   **Video Conferencing:**
    *   Zoom (Create, delete, get, and update meetings; OAuth 2.0 for secure integration)
    *   Google Meet (Agent capabilities for managing meeting links and details)
*   **Note-Taking & Knowledge Management:**
    *   Notion (Primary integration for notes, research databases, and knowledge organization)
*   **Scheduling Services:**
    *   Calendly (Integration to coordinate external scheduling)
*   **Financial & Payments:**
    *   Stripe (List payments, potentially link to projects or clients)
    *   QuickBooks (Manage invoices, link financial data)
*   **Automation Platforms:**
    *   Zapier (Connect Atom with a vast ecosystem of other apps and services)
*   **Contact Sync:**
    *   Google Contacts (Keep your contacts synchronized with Atom)
*   **Transcription Services:**
    *   Deepgram (High-quality transcription for audio notes and other audio inputs)
*   **Push Notifications:** Generic support for sending push notifications to keep users updated on calendar changes or important tasks.
*   **Gmail Account Integration (Read-Only & AI-Powered Querying):**
    *   **Secure Connection:** Connect your personal Gmail account via OAuth 2.0 for secure, read-only access. Tokens are encrypted at rest.
    *   **Natural Language Email Search:** Ask the agent in natural language to find emails (e.g., "find emails from Jane about the Q3 report sent last week"). The agent uses an LLM to understand complex queries, resolve relative dates, and identify key search parameters.
    *   **Targeted Information Extraction:** Request specific information from found emails (e.g., "What was the contract end date mentioned in the email from XYZ?"). The agent uses an LLM to read the email content and extract the requested details. (Note: Accuracy depends on LLM capabilities and prompt engineering).
    *   **Agent Skills:** Core agent skills updated to search emails and read email content via the Gmail API.
    *   **User Interface:**
        *   Settings page to connect/disconnect Gmail account and view connection status.
        *   Proof-of-concept UI for direct Gmail searching.
    *   **Developer Documentation:** Comprehensive guide for setup, API details, and agent integration logic.

*   **Slack Workspace Integration (Enhanced AI-Powered Querying & Interaction):**
    *   **Secure Connection:** Connect your Slack workspace using a Bot User OAuth Token with necessary permissions.
    *   **Natural Language Message Search:** Ask the agent in natural language to find Slack messages (e.g., "find messages from Bob about the project update in #general yesterday"). The agent uses an LLM to understand complex queries, resolve relative dates/users/channels, and identify key search parameters for Slack's API.
    *   **Targeted Information Extraction:** Request specific information from found Slack messages (e.g., "What was the deadline mentioned in the message from Alice in #design?"). The agent uses an LLM to read the message content and extract the requested details.
    *   **Message Content Retrieval:** Fetch and display content of specific Slack messages.
    *   **Permalink Generation:** Get direct links to Slack messages.
    *   **Agent Skills:** Core agent skills updated to search Slack messages, read their content, extract information, and get permalinks via the Slack API.
    *   **Basic Operations:** Continues to support sending messages and listing channels.
    *   **Configuration:** Requires `ATOM_SLACK_BOT_TOKEN` with appropriate scopes (see Slack integration guide).
    *   **Developer Documentation:** Comprehensive guide for setup, API details, required scopes, and agent integration logic.

*   **Microsoft Teams Integration (Enhanced AI-Powered Chat Interaction & Delegated Permissions):**
    *   **Secure User-Contextual Connection:** Connect on behalf of the user via OAuth 2.0 (delegated permissions) to access their Microsoft Teams environment. User-specific tokens are securely stored.
    *   **Natural Language Message Search:** Ask the agent in natural language to find Teams messages (e.g., "find Teams messages from Alex about the Q1 budget in our 'Strategy Chat' from last week"). The agent uses an LLM to understand complex queries and map them to Microsoft Graph Search API queries.
    *   **Targeted Information Extraction:** Request specific information from found Teams messages (e.g., "What action items were assigned to me in the Teams message from Lee in the 'Project Phoenix' channel?"). The agent uses an LLM to read message content and extract details.
    *   **Message Content Retrieval:** Fetch and display content of specific Teams chat or channel messages the user has access to.
    *   **Permalink (WebURL) Generation:** Get direct links to Teams messages.
    *   **Agent Skills:** Core agent skills developed to search Teams messages, read content, extract information, and get webUrls via the Microsoft Graph API, operating within the user's permissions.
    *   **Existing Functionality:** Continues to support integration for calendar events and online meetings (details may vary based on app or delegated permissions for calendar access).
    *   **Configuration:** Requires Azure AD App Registration with appropriate delegated permissions (e.g., `Chat.Read`, `ChannelMessage.Read.All`, `User.Read`, `offline_access`) and corresponding environment variables (see MS Teams integration guide).
    *   **Developer Documentation:** New comprehensive guide (`docs/msteams_integration_guide.md`) for setup, Azure AD configuration, API details, required delegated scopes, and agent integration logic.

### User Settings & Preferences
Tailor Atom to your specific needs with a range of customizable settings:
*   **General Preferences:** Configure core settings during onboarding and later, such as your typical workday hours, default alarm/reminder times, and primary calendar selection.
*   **Calendar Preferences:** Manage settings for connected calendars, choose your primary calendar for new events, and configure integration-specific options.
*   **Category Management:** Create, edit, and manage event categories, including their default attributes like color, priority, or associated tags.
*   **Autopilot Settings:** Fine-tune how Autopilot functions, including its schedule, aggressiveness in modifying events, and the types of events it should manage.
*   **Chat Meeting Preferences:** Define default preferences for meetings scheduled quickly via the chat interface, such as default duration or video conferencing options.
*   **Integration Management:** View the status of all connected third-party services, manage credentials, and enable/disable specific integrations.

This list is intended to be comprehensive. If you discover a feature not listed here, please consider contributing to our documentation!
