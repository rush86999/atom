## Features

Atom is designed to enhance your productivity through a comprehensive suite of AI-powered and integrated features.

### Core: AI-Powered Productivity Assistance
*   **Conversational AI Agent:** Interact with Atom through a chat interface to manage tasks, schedule meetings, get information, and control integrations.
*   **User Onboarding:** Guided setup wizard to configure Atom, connect integrations, and set initial preferences (e.g., work day, default alarms, primary calendar).
*   **User Authentication:** Secure login system for protecting your data and configurations.
*   **Configurable Agent Settings:** Customize various aspects of the Atom agent's behavior and its interaction with integrated services.
*   **Wake Word Detection:** (If confirmed as fully functional) Initiate interaction with Atom using a spoken wake word for hands-free operation.

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
*   **Event-Specific Time Preferences:** Set preferred meeting times for individual events, overriding global preferences where necessary.
*   **Follow-up Event Creation:** Quickly create follow-up events based on existing meetings or tasks, ensuring timely next steps.

### Task Management
*   **Task Creation & Management:** Add, view, edit, and manage your tasks within Atom.
*   **Automated Time Blocking for Tasks:** Atom can automatically find and block time on your calendar for tasks that have daily or weekly deadlines. It intelligently places these blocks based on task priority and your defined requirements (e.g., soft or hard deadlines).
*   **Task Scheduling:** Define deadlines for your tasks and have Atom schedule them onto your calendar, integrating them with your other events.
*   **GPT-Powered Task Assistance:**
    *   Break down complex tasks into smaller, more manageable sub-tasks.
    *   Receive "how-to" instructions or guidance for completing specific tasks.

### Integrated Note-Taking & Research
Keep your knowledge organized and accessible with Atom's integrated capabilities:
*   **Note-Taking (Notion & Audio):** Create text and audio notes directly. Audio notes are automatically transcribed (e.g., using Deepgram) and saved, typically within Notion. Your notes can be searched, updated, and linked to tasks or calendar events.
*   **Multi-Agent Research System (Notion & LanceDB):** Initiate research projects based on simple queries. A lead AI agent decomposes your query into sub-tasks and assigns them to specialized sub-agents. These agents perform research (e.g., web searches, internal Notion searches using LanceDB for vector-based information retrieval) and log their findings in a dedicated Notion database. The lead agent then synthesizes this information into a comprehensive final report, also in Notion.
*   **Python API for Notes & Research:** Backend handlers and APIs for managing notes and research processes programmatically.

### Automation & AI Capabilities
Leverage Atom's advanced automation and AI functionalities:
*   **Autopilot (Scheduled Actions):** As part of Smart Scheduling, Autopilot proactively manages your schedule by applying learned features and templates to events.
*   **GPT-Powered Summaries:** Create concise summaries of information, such as a series of notes or research findings, over a defined period.
*   **Event Feature Application Engine:** A backend system (potentially utilizing Optaplanner) responsible for applying defined features, rules, and templates to calendar events, ensuring consistent and intelligent scheduling.
*   **Event-to-Vector Processing:** For semantic search and event matching, Atom processes event information into vectors, enabling more accurate matching and templating (uses LanceDB).
*   **Live Meeting Attendance:** (If confirmed as fully functional) Atom can "attend" live meetings to perform tasks like automated note-taking or action item identification (details on this capability would be needed based on implementation).
*   **Audio Processing:** Transcribe audio from various sources for notes, commands, or meeting recordings.

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

### User Settings & Preferences
Tailor Atom to your specific needs with a range of customizable settings:
*   **General Preferences:** Configure core settings during onboarding and later, such as your typical workday hours, default alarm/reminder times, and primary calendar selection.
*   **Calendar Preferences:** Manage settings for connected calendars, choose your primary calendar for new events, and configure integration-specific options.
*   **Category Management:** Create, edit, and manage event categories, including their default attributes like color, priority, or associated tags.
*   **Autopilot Settings:** Fine-tune how Autopilot functions, including its schedule, aggressiveness in modifying events, and the types of events it should manage.
*   **Chat Meeting Preferences:** Define default preferences for meetings scheduled quickly via the chat interface, such as default duration or video conferencing options.
*   **Integration Management:** View the status of all connected third-party services, manage credentials, and enable/disable specific integrations.

This list is intended to be comprehensive. If you discover a feature not listed here, please consider contributing to our documentation!
