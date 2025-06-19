<h1 align="center">Atom - An open-source AI Agent to solve your problems</h1>

⭐⭐⭐ If you like where this repo is heading, please support me with a star on the top right corner ⭐⭐⭐

⭐⭐⭐ New Direction ⭐⭐⭐


## Table of Contents
- [Table of Contents](#table-of-contents)
- [Problem](#problem)
- [Documentation](#documentation)
- [Features](#features)
  - [Benefits of Self Hosted](#benefits-of-self-hosted)
  - [Cloud Hosted Atomic](#cloud-hosted-atomic)
  - [Customize Atomic for your team on your cloud](#customize-atomic-for-your-team-on-your-cloud)
  - [Note-Taking (Notion & Audio)](#note-taking-notion--audio)
  - [Multi-Agent Research System (Notion & LanceDB)](#multi-agent-research-system-notion--lancedb)
- [Core Agent Capabilities & Commands](#core-agent-capabilities--commands)
  - [General Commands](#general-commands)
  - [Note-Taking and Research (Conceptual)](#note-taking-and-research-conceptual)
  - [Google Calendar & Google Meet](#google-calendar--google-meet)
  - [HubSpot CRM](#hubspot-crm)
  - [Slack](#slack)
  - [Zoom Meetings](#zoom-meetings)
  - [Microsoft Teams Meetings (via MS Graph)](#microsoft-teams-meetings-via-ms-graph)
  - [Stripe Payments](#stripe-payments)
  - [QuickBooks Online](#quickbooks-online)
  - [Other Skills (from initial handler)](#other-skills-from-initial-handler)
- [Configuration (Environment Variables)](#configuration-environment-variables)
  - [General Agent Configuration](#general-agent-configuration)
  - [Google Calendar & Google Meet](#google-calendar--google-meet-1)
  - [HubSpot CRM](#hubspot-crm-1)
  - [Slack](#slack-1)
  - [Zoom Meetings](#zoom-meetings-1)
  - [Microsoft Teams Meetings (via MS Graph)](#microsoft-teams-meetings-via-ms-graph-1)
  - [Stripe](#stripe)
  - [QuickBooks Online](#quickbooks-online-1)
- [Diagram](#diagram)
  - [Meeting Assist](#meeting-assist)
- [Deployment Options](#deployment-options)
  - [Local Docker Compose](#local-docker-compose)
  - [AWS Cloud Deployment (Self-Hosted)](#aws-cloud-deployment-self-hosted)
- [Support the Project](#support-the-project)
- [Contributing](#contributing)


## Problem
Agents are closed source. It's time to create a truly open agent that works for you! Manage your time, tasks, notes and do research on your behalf. This is the starting template for a universal assistant. 

Examples related to managing your time:

1. "Schedule a meeting with [person] at [date and time] for [purpose]."
2. "Remind me to follow up with [person] on [date] regarding [topic]."
3. "Block off [time frame] for [task or activity]."
4. "Find an available time slot for a team meeting with [list of attendees]."
5. "Let's respond to emails either on 8 - 11 am or 2 - 4 pm on weekdays with a priority of 3"
6. "Let's have [X] meetings on either Mondays or Wednesdays, anytime between 8 - 11 am, and keep it a priority of 5"
7. "When is my next appointment?"
8. "What time is my meeting with [person] on [date]?"
9. "Are there any overlapping events on my calendar?"
10. "Do I have any free time on Thursday?"


## Documentation

- Pending

## Features

| Feature | Description |
| ----------- | ----------- |
| Semantic search | Leverage AI-powered semantic search to match new or queried events with relevant past events, effectively turning your history into smart templates. Event details are converted into vector embeddings (via OpenAI models) and stored in **LanceDB**. The new `lance-event-matcher` service then employs a **two-stage AI process** for superior accuracy: 1.  **Query Enhancement:** User queries (and optionally, recent chat history) are first processed by an AI to refine search terms, understand the core intent, and identify potential date or category filters. 2.  **Results Processing & Categorization:** Events retrieved from LanceDB (using the AI-enhanced query) are then further analyzed by a second AI stage. This stage filters events for relevance, assigns the most appropriate category (which can dictate attributes like duration, color, priority, linked default behaviors, etc.), and provides a relevance score for ranking. This ensures highly relevant and accurately categorized results, making event templating more powerful and intuitive. Note: 'Training' involves ensuring events are properly categorized so the AI can learn these patterns for future application. |
| Automated tagging | Automated event categorization (effectively, 'smart tagging') is performed by an AI model integrated within the `lance-event-matcher` service's results processing stage. Based on event content and the context of the user's query, the AI assigns the most relevant category to an event. Each category can define a set of default attributes and behaviors (e.g., duration, priority, color, time blocking preferences), which are then applied to the categorized events. This system streamlines event creation and ensures consistency in how similar events are handled. |
| Flexible Meetings | Create recurring 1:1's or ad hoc team meetings that works with everyone's schedule. Every attendee's calendar is taken into account. Non-Atomic users can also sync their calendars and submit their time preferences. Once setup, your flexible recurring meetings occur automagically conflict free based on your time preferences.|
| Note-Taking (Notion & Audio) | Create text and audio notes directly in Notion. Audio notes are transcribed using Deepgram. Notes can be searched, updated, and linked to tasks or calendar events within Notion. |
| Multi-Agent Research System (Notion & LanceDB) | Initiate research projects based on user queries. A lead researcher agent decomposes the query into sub-tasks, which are assigned to sub-agents. Sub-agents perform simulated tool use (e.g., web search, internal Notion search using LanceDB for vector search if applicable), log their findings, and update task status in a dedicated Notion database. The lead agent synthesizes completed task outputs into a final report in Notion. |
| Autopilot | You can run the AI planner on Autopilot that will also search & apply features to new events based on past trained event templates. The AI planner will always run before your work day starts |
|Time Preferences |Select time preferences for flexible meetings and other modifiable events |
| Train events| You can train existing events and make them templates for new ones. Attributes you can change include transparency, buffer times, priority, time preferences, modifiable nature, tags, color, duration, break type, alarms. You can also "untrain" by turning "link off" in the event menu options.|
| Time Blocking | You can automate time blockings of tasks that have a daily or weekly deadline with priority to let Atomic place them in the right place on your calendar. The deadlines can be soft or hard based on your requirements.|
|Priority | You can set priority to modifiable events. Priority of 1 is neutral. 1 has no impact on the AI planner's decision making process. Any number > 1 will impact sooner it appears on the calendar relative other low priority events.|
|Rating| You can rate events to tell Atomic how productive you were for the time block. Next run, Atomic will take it into consideration before the placing the event if it's modifiable|
| Smart Tags | You can apply settings to tags. These settings will tell Atomic how to apply features or attributes to new events that are tagged by the AI model or manually.|

## Key Technologies & Services Update

The event matching and retrieval core has been significantly updated:

*   **`lance-event-matcher` Service:** This is the new primary backend service for all event search, matching, and categorization tasks. It leverages:
    *   **LanceDB** for efficient vector storage and similarity search of event embeddings.
    *   A **two-stage AI processing pipeline** (using models like GPT) to:
        1.  Enhance and understand the user's initial search query.
        2.  Process and filter search results from LanceDB, assign relevant categories, and score them for relevance.

*   **LanceDB:** Has replaced OpenSearch as the vector database for storing and searching event embeddings and associated metadata (like start/end dates and user IDs).

*   **OpenSearch (for Event Search - Deprecated):** The previous system using OpenSearch for event vector search and the associated `events-search` backend service have been deprecated and are no longer in use. Client applications should utilize the new `lance-event-matcher` service.

#### Benefits of Self Hosted
- Privacy enabled by default
- Customizable - adjust any parameters to make it work to your requirements

### Cloud Hosted Atomic
- Prioritized version
- Full customer support & bug fixes
- Road map
  - SSO for teams
  - Microsoft Outlook Calendar integration
  - ChatGPT integration for Premium version
  - Zoom video is integrated.
  - docker self-hosted version

### Customize Atomic for your team on your cloud
- Same level of support & features as cloud hosted version
- Same features
- 1 year support included
- $15 / month support afterwards

## Core Agent Capabilities & Commands

The Atomic Agent understands a variety of commands to interact with your integrated services. Commands are typically issued in a chat interface with the agent.

### General Commands
*   `help` or `?`: Displays a list of understood commands (this should be the agent's default response if a command isn't recognized).

### Google Calendar & Google Meet
*   **`list events [limit]`**: Lists upcoming Google Calendar events.
    *   Example: `list events 5`
*   **`create event {JSON_DETAILS}`**: Creates a new Google Calendar event.
    *   Example: `create event {"summary":"My Meeting","startTime":"YYYY-MM-DDTHH:mm:ssZ","endTime":"YYYY-MM-DDTHH:mm:ssZ"}`
*   **`list google meet events [limit]`**: Lists upcoming Google Calendar events that have Google Meet links.
    *   Example: `list google meet events 3`
*   **`get google meet event <eventId>`**: Retrieves details for a specific Google Calendar event, highlighting Google Meet information.
    *   Example: `get google meet event your_calendar_event_id`
*   **`slack my agenda`**: Fetches your upcoming Google Calendar events and sends a summary to your Slack direct message.

### HubSpot CRM
*   **`create hubspot contact {JSON_DETAILS}`**: Creates a new contact in HubSpot. If `ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID` is configured, a notification is sent to that Slack channel.
    *   Example: `create hubspot contact {"email":"name@example.com", "firstname":"John", "lastname":"Doe"}`
*   **`create hubspot contact and dm me details {JSON_DETAILS}`**: Creates a new contact in HubSpot and sends the details (including a HubSpot link if `ATOM_HUBSPOT_PORTAL_ID` is configured) to you via Slack direct message.
    *   Example: `create hubspot contact and dm me details {"email":"lead@example.com", "firstname":"Jane"}`
*   **`get hubspot contact by email <email>`**: (Skill available) Retrieves HubSpot contact details for the given email.
    *   *Note: This command might not yet be directly wired into the primary command handler but the underlying skill exists.*

### Slack
*   **`send slack message <channel_id_or_name> <text>`**: Sends a message to the specified Slack channel ID or name.
    *   Example: `send slack message C123ABC456 Hello team!`
    *   Example: `send slack message #general Important update!`
*   **`list slack channels [limit] [cursor]`**: Lists available Slack channels.
    *   Example: `list slack channels 20`

### Zoom Meetings
*   **`list zoom meetings [type] [page_size] [next_page_token]`**: Lists your Zoom meetings.
    *   `type`: Can be `upcoming` (default), `live`, `scheduled`.
    *   Example: `list zoom meetings upcoming 5`
*   **`get zoom meeting <meetingId>`**: Retrieves details for a specific Zoom meeting.
    *   Example: `get zoom meeting 1234567890`

### Microsoft Teams Meetings (via MS Graph)
*   **`list teams meetings [limit] [nextLink]`**: Lists your Microsoft Teams meetings from your calendar.
    *   Example: `list teams meetings 5`
*   **`get teams meeting <eventId>`**: Retrieves details for a specific Teams meeting (using its Microsoft Graph event ID).
    *   Example: `get teams meeting AAMkAG...`

### Stripe Payments
*   **`list stripe payments [limit=N] [starting_after=ID] [customer=ID]`**: Lists Stripe payments (PaymentIntents).
    *   Example: `list stripe payments limit=5 customer=cus_123abc`
*   **`get stripe payment <paymentIntentId>`**: Retrieves details for a specific Stripe PaymentIntent.
    *   Example: `get stripe payment pi_123abc...`

### QuickBooks Online
*   **`qb get auth url`**: Provides the URL to manually authorize the agent with your QuickBooks Online account. This is a one-time setup step.
*   **`list qb invoices [limit=N] [offset=N] [customer=ID] [status=STATUS]`**: Lists invoices from QuickBooks Online.
    *   Example: `list qb invoices limit=10 status=Open customer=123`
*   **`get qb invoice <invoiceId>`**: Retrieves details for a specific QuickBooks Online invoice.
    *   Example: `get qb invoice 456`

### Other Skills (from initial handler)

### Note-Taking and Research (Multi-Agent System with Notion & LanceDB)
*   **`research \"<topic>\"`**: Initiates a new research project on the specified topic. The agent decomposes the topic into sub-tasks, performs web searches for each task, and stores the findings in a Notion database (specified by `NOTION_RESEARCH_TASKS_DB_ID`). A main project page is created in `NOTION_RESEARCH_PROJECTS_DB_ID`. This command relies on `OPENAI_API_KEY` for decomposing tasks and synthesizing reports, `NOTION_API_TOKEN` for Notion interactions, and `SEARCH_API_KEY` for web searches.
*   **`process_research_queue`**: Triggers the agent to work on any pending research tasks found in the Notion tasks database. This includes performing web searches for tasks not yet completed and generating synthesized reports for projects where all tasks are finished. The final report is saved to the main project page in Notion.

*   **`list emails [limit]`**: Lists recent emails (generic, implementation details may vary).
*   **`read email <id>`**: Reads a specific email.
*   **`send email {JSON_DETAILS}`**: Sends an email.
*   **`search web <query>`**: Performs a web search.
*   **`trigger zap <ZapName> [with data {JSON_DATA}]`**: Triggers a Zapier zap.

### General Note-Taking in Notion (Conceptual - see Multi-Agent System for implemented research notes)
*   **`note create --title "My Idea" --content "This is a new idea..."`**: Creates a new text note in Notion.
*   **`note audio create --title "Meeting Recap" --file /path/to/audio.mp3`**: Creates an audio note in Notion, transcribing the audio file.
*   **`note search "keyword"`**: Searches for notes in Notion containing the keyword.
*   **`note link <note_id> to task <task_id>`**: Links an existing Notion note to a task ID (conceptual).
*   **`research "topic like AI in healthcare"`**: Initiates a new research project on the specified topic.
*   **`get research report <project_id>`**: Retrieves the status or the synthesized report for a given research project ID.


## Configuration (Environment Variables)

The Atomic Agent uses environment variables for its configuration and to connect to various third-party services.

### General Agent Configuration
*   `OPENAI_API_KEY`: Your OpenAI API key (used for embeddings, classification, etc.).
*   `DEEPGRAM_API_KEY`: Your Deepgram API key (for audio transcription).
*   `NOTION_API_TOKEN`: Your Notion API integration token.
*   `NOTION_NOTES_DATABASE_ID`: The ID of your Notion database for general notes.
*   `NOTION_RESEARCH_PROJECTS_DB_ID`: The ID of your Notion database for research projects.
*   `NOTION_RESEARCH_TASKS_DB_ID`: The ID of your Notion database for research sub-agent tasks.
*   `LANCEDB_URI`: URI for LanceDB storage (e.g., `file:///mnt/lancedb_data/atomic_lancedb` when running in Docker/AWS with EFS, or a local path like `./data/lancedb` for local-only development).
*   `SEARCH_API_KEY`: Your API key for the chosen web search engine (e.g., Google Custom Search API, Bing Search API, SerpApi, etc.). This is required for the research agent's web search capabilities.
*   _(Remove any OpenSearch-specific variables like `OPENSEARCH_ENDPOINT`, `OPENSEARCH_USERNAME`, `OPENSEARCH_PASSWORD`)_


### Google Calendar & Google Meet
*   `ATOM_GOOGLE_CALENDAR_CLIENT_ID`: Your Google Cloud project's Client ID.
*   `ATOM_GOOGLE_CALENDAR_CLIENT_SECRET`: Your Google Cloud project's Client Secret.
*   `ATOM_GOOGLE_CALENDAR_SCOPES`: Space-separated list of Google API scopes (e.g., `https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events.readonly`).
*   _(Note: Google tokens are typically stored per user, often managed via an OAuth consent screen flow. The agent skills expect these tokens to be available.)_

### HubSpot CRM
*   `ATOM_HUBSPOT_API_KEY`: Your HubSpot API Key.
*   `ATOM_HUBSPOT_PORTAL_ID`: (Optional) Your HubSpot Portal ID, used for creating direct links to contacts in Slack notifications.

### Slack
*   `ATOM_SLACK_BOT_TOKEN`: Your Slack App's Bot User OAuth Token (starts with `xoxb-`).
*   `ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID`: (Optional) Slack Channel ID where notifications for new HubSpot contacts will be sent.

### Zoom Meetings
*   `ATOM_ZOOM_ACCOUNT_ID`: Your Zoom Account ID (for Server-to-Server OAuth).
*   `ATOM_ZOOM_CLIENT_ID`: Your Zoom Server-to-Server OAuth App's Client ID.
*   `ATOM_ZOOM_CLIENT_SECRET`: Your Zoom Server-to-Server OAuth App's Client Secret.

### Microsoft Teams Meetings (via MS Graph)
*   `ATOM_MSGRAPH_CLIENT_ID`: Azure AD App Registration Client ID.
*   `ATOM_MSGRAPH_CLIENT_SECRET`: Azure AD App Registration Client Secret.
*   `ATOM_MSGRAPH_TENANT_ID`: Azure AD Tenant ID.
*   `ATOM_MSGRAPH_AUTHORITY`: (Optional, defaults to `https://login.microsoftonline.com/{TENANT_ID}`) The MSAL authority URL.
*   `ATOM_MSGRAPH_SCOPES`: Space-separated list of Microsoft Graph API scopes (e.g., `Calendars.Read OnlineMeetings.Read`).

### Stripe
*   `ATOM_STRIPE_SECRET_KEY`: Your Stripe Secret API Key (e.g., `sk_test_...` or `sk_live_...`).

### QuickBooks Online
*   `ATOM_QB_CLIENT_ID`: QuickBooks Online App Client ID.
*   `ATOM_QB_CLIENT_SECRET`: QuickBooks Online App Client Secret.
*   `ATOM_QB_REDIRECT_URI`: Redirect URI configured in your QBO App (e.g., `http://localhost:3000/callback`).
*   `ATOM_QB_ENVIRONMENT`: Set to `sandbox` or `production`. Defaults to `sandbox`.
*   `ATOM_QB_TOKEN_FILE_PATH`: Path where OAuth tokens will be stored (e.g., `./qb_oauth_tokens.json`). The agent needs write access to this path.
    *   *Note: Initial authorization requires manually visiting a URL provided by `qb get auth url` and saving the tokens.*

## Diagram

### Meeting Assist
```mermaid
    sequenceDiagram
    actor Alice
    participant A as Atomic
    actor Bob
    actor John
    participant H as handshake.atomiclife.app
    participant P as AI Scheduler

    participant G as Google Calendar
    Alice->>A: Create a new meeting assist with John & Bob as attendees
    A->>John: Sends handshake link for a possible meeting
    A->>Bob: Sends another handshake link to another attendee 
    John->>H: Selects time preferences (not availability like a booking link)
    Bob->>H: Also selects time preferences
    H->>P: Submits & starts AI planner after minimum threshold met
    P->>G: finds an optimal slot & creates the new event

```

## Deployment Options

This project offers multiple ways to deploy and run the Atomic application stack.

### Local Docker Compose

For local development, testing, and self-hosting on a single machine, the project can be run using Docker Compose. This method utilizes the services defined in the `atomic-docker/` directory.

-   **Setup and Instructions:** See the detailed guide in [atomic-docker/README.md](./atomic-docker/README.md).

### AWS Cloud Deployment (Self-Hosted)

For a scalable and robust cloud environment, you can deploy the entire application stack to your own AWS account. This deployment is managed by the AWS Cloud Development Kit (CDK) and provisions all necessary infrastructure, including managed services for databases, messaging, and search where appropriate.

-   **Features:** Deploys core application services, Optaplanner, a new `python-agent` service (for notes and research), and utilizes AWS S3, Amazon EFS (for LanceDB vector stores), and Amazon MSK Serverless. Amazon OpenSearch Service is no longer used.

-   **Detailed Guide:** For prerequisites, setup instructions, deployment steps, and management, please refer to the comprehensive [AWS Deployment Guide](./deployment/aws/README.md).

## Support the Project
- I'm spending 100% of my work time on this project
- Star this repository, so I can start an Open Collective to support this project
- In process of setting up Github Sponsors
- Follow me on Twitter: https://twitter.com/rish1_2
- Used Atomic? write a review or let me know!

## Contributing

1. Fork this repository and clone the fork to your machine
2. Create a branch (`git checkout -b my-new-feature`)
3. Implement a new feature or fix a bug and add some tests or proof of fix
4. Commit your changes (`git commit -am 'Added a new feature'`)
5. Push the branch to your fork on GitHub (`git push origin my-new-feature`)
6. Create new Pull Request from your fork
