<h1 align="center">Atomic - An open-source priority-driven AI scheduler to solve your time problems</h1>

<h2 align="center">An alternative to Motion, Clockwise, Cal.ai & Reclaim</h2>

⭐⭐⭐ If you like where this repo is heading, please support me with a star on the top right corner ⭐⭐⭐

⭐⭐⭐ Self-hosted now available :) ⭐⭐⭐

For a good user experience use [Groq](https://wow.groq.com/)


https://github.com/rush86999/atomic/assets/16848240/da8c0826-573e-44a4-849b-083d61dc4c60

https://github.com/rush86999/atomic/assets/16848240/b2dc08e8-8e9f-41b5-b249-dadb13b914c6

https://github.com/rush86999/atomic/assets/16848240/9390a703-31fa-4622-b6be-818bf462b3f8

https://github.com/rush86999/atomic/assets/16848240/5720e9a3-e4d6-4dce-8e3c-5d614a39e305


## Table of Contents
- [Table of Contents](#table-of-contents)
- [Problem](#problem)
- [Documentation](#documentation)
- [Features](#features)
  - [Benefits of Self Hosted](#benefits-of-self-hosted)
  - [Cloud Hosted Atomic](#cloud-hosted-atomic)
  - [Customize Atomic for your team on your cloud](#customize-atomic-for-your-team-on-your-cloud)
- [Core Agent Capabilities & Commands](#core-agent-capabilities--commands)
  - [General Commands](#general-commands)
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
  - [AWS Cloud Deployment (via AWS CDK)](#aws-cloud-deployment-via-aws-cdk)
  - [AWS Cloud Deployment (via Terraform)](#aws-cloud-deployment-via-terraform)
- [Support the Project](#support-the-project)
- [Contributing](#contributing)


## Problem
Scheduling and managing time is always a problem. Finding a time that works for everybody is a bigger problem. What if you can tell your calendar your time preferences and priorities for things you have to do every day? Now what if everyone on your team could do the same thing? Now finding a time becomes easier when everyone's priorities are accounted for. 

Let all of this happen automatically for you and your team on a daily basis before work starts.

All of this is possible with vector-based search to create a memory for your calendar and Autopilot.

Memory + Decisions + Natural Conversation Interface => Perfect Time Management Assistant

It will be easier than ever to teach, find, block, create, meet, schedule, update, and more with your calendar using ChatGPT. The goal is to allow a natural conversation with your calendar assistant for your end goals.

Examples:

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


For simple 1:1 meetings, you won't need calendly links anymore. Your recipient replies to you and Atomic, and a meeting gets scheduled for you automatically.

## Documentation

- You can find documentation on how to use Atomic at https://docs.atomiclife.app

## Features

| Feature | Description |
| ----------- | ----------- |
| Semantic search | Use unique key phrases to match semantically similar past task events and apply them to new ones. Now your past tasks are templates for new ones! Apply duration, color, time preferences, priority, tags and more. Event details are converted into vectors and indexed for search. The vectorization of event details now leverages direct calls to advanced OpenAI embedding models for enhanced performance and cost-effectiveness. Note: You need to "train" Atomic on existing events to create event templates for new events. Read the [docs](https://docs.atomiclife.app) for more info. |
| Automated tagging | Apply tags automatically using an AI model used for classification. Each tag comes with its own set of settings configured to apply to all matched events. This classification is now primarily handled by direct integration with powerful OpenAI language models. |
| Flexible Meetings | Create recurring 1:1's or ad hoc team meetings that works with everyone's schedule. Every attendee's calendar is taken into account. Non-Atomic users can also sync their calendars and submit their time preferences. Once setup, your flexible recurring meetings occur automagically conflict free based on your time preferences.|
| Autopilot | You can run the AI planner on Autopilot that will also search & apply features to new events based on past trained event templates. The AI planner will always run before your work day starts |
|Time Preferences |Select time preferences for flexible meetings and other modifiable events |
| Train events| You can train existing events and make them templates for new ones. Attributes you can change include transparency, buffer times, priority, time preferences, modifiable nature, tags, color, duration, break type, alarms. You can also "untrain" by turning "link off" in the event menu options.|
| Time Blocking | You can automate time blockings of tasks that have a daily or weekly deadline with priority to let Atomic place them in the right place on your calendar. The deadlines can be soft or hard based on your requirements.|
|Priority | You can set priority to modifiable events. Priority of 1 is neutral. 1 has no impact on the AI planner's decision making process. Any number > 1 will impact sooner it appears on the calendar relative other low priority events.|
|Rating| You can rate events to tell Atomic how productive you were for the time block. Next run, Atomic will take it into consideration before the placing the event if it's modifiable|
| Smart Tags | You can apply settings to tags. These settings will tell Atomic how to apply features or attributes to new events that are tagged by the AI model or manually.|

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
*   **`list emails [limit]`**: Lists recent emails (generic, implementation details may vary).
*   **`read email <id>`**: Reads a specific email.
*   **`send email {JSON_DETAILS}`**: Sends an email.
*   **`search web <query>`**: Performs a web search.
*   **`trigger zap <ZapName> [with data {JSON_DATA}]`**: Triggers a Zapier zap.

## Configuration (Environment Variables)

The Atomic Agent uses environment variables for its configuration and to connect to various third-party services.

### General Agent Configuration
*   _(Add any general agent config vars here if known, e.g., `PORT`, `LOG_LEVEL`)_

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

### AWS Cloud Deployment (via AWS CDK)

It is possible to deploy the entire application stack to your own AWS account using the AWS Cloud Development Kit (CDK). This provides a scalable and robust cloud environment managed with TypeScript/Python code.

-   **Features:** Deploys core application services, Optaplanner, and utilizes AWS S3, Amazon OpenSearch Service, and Amazon MSK Serverless.
-   **Detailed Guide:** For prerequisites, setup instructions, deployment steps, and management, please refer to the [AWS CDK Deployment Guide](./deployment/aws/README.md).

### AWS Cloud Deployment (via Terraform)

Alternatively, you can deploy the full application stack to your AWS account using Terraform. This option also provisions a scalable cloud environment using HashiCorp's Infrastructure as Code tool.

-   **Features:** Deploys core application services, Optaplanner, and utilizes AWS S3, Amazon OpenSearch Service, and Amazon MSK Serverless, similar to the CDK deployment.
-   **Detailed Guide:** For prerequisites, setup, deployment instructions (including manual configuration steps for secrets and MSK), and management using Terraform, please see the [Terraform AWS Deployment Guide](./terraform/aws/README.md).

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
