# Atom: Your Open-Source AI Assistant for Enhanced Productivity

Atom is a powerful and flexible open-source AI assistant designed to streamline your workflow, intelligently manage your schedule, automate research, and organize your information. Take control of your productivity with an assistant that you can host yourself, ensuring privacy and customization.

## Why Choose Atom?
*   **Empower Your Productivity:** Let Atom handle the tedious tasks of scheduling, note-taking, and information gathering so you can focus on what matters most.
*   **Open Source & Transparent:** Built with transparency in mind, Atom's open-source nature means you have full visibility into its operations. No black boxes.
*   **Self-Hosted for Privacy & Control:** Host Atom on your own infrastructure for maximum privacy and control over your data and how the assistant operates.
*   **Highly Customizable:** Adapt Atom to your specific needs. Its modular design and open codebase allow for extensive customization and integration possibilities.
*   **Intelligent Automation:** Leverage AI for smart scheduling that considers your preferences, automated event templating, and efficient research capabilities.
*   **Seamless Integrations:** Connect Atom with your favorite tools like Google Calendar, Notion, Slack, Zoom, and more to create a unified productivity hub.

## Table of Contents
- [Why Choose Atom?](#why-choose-atom)
- [Example Use Cases](#example-use-cases)
- [Documentation](#documentation)
- [Features](#features)
- [Core Agent Capabilities & Commands](#core-agent-capabilities--commands)
- [Configuration (Environment Variables)](#configuration-environment-variables)
- [Diagram](#diagram)
  - [Meeting Assist](#meeting-assist)
- [Deployment Options](#deployment-options)
  - [Local Docker Compose](#local-docker-compose)
  - [AWS Cloud Deployment (Self-Hosted)](#aws-cloud-deployment-self-hosted)
- [Support the Project](#support-the-project)
- [Contributing](#contributing)


## Example Use Cases
Tired of juggling multiple apps and struggling to stay organized? Atom is here to help you reclaim your focus and boost your productivity. Here are a few ways Atom can simplify your work and personal life:

*   **Effortless Meeting Coordination:** "Find a time next week for a 30-minute meeting with Sarah and John, prioritizing Wednesday afternoon." Atom will check everyone's availability (integrating with their calendars if permitted) and propose optimal times.
*   **Smart Task Management (Voice-Powered):** Use natural voice commands like "Atom, create a task: follow up with marketing by Friday" or "Atom, what are my tasks for today?" Atom manages these tasks in a dedicated Notion database you configure.
*   **Automated Information Gathering:** "Research the latest trends in AI-powered personal assistants and summarize the key findings in a Notion document." Atom's research agents can browse, collect, and synthesize information, delivering it directly to your knowledge base.
*   **Voice-Powered Note-Taking:** While commuting, you can say: "Atom, take an audio note: Idea for marketing campaign - focus on social media engagement and influencer collaborations." Atom will transcribe the audio and save it to Notion.
*   **Automated Meeting Summaries & Action Items:** Atom can process your meeting transcripts (e.g., from live meeting attendance or uploaded recordings) and then automatically extract key decisions and action items directly into your Notion meeting notes.
*   **Intelligent Information Retrieval:** Ask Atom "What did we decide about Project X?" or "Search my meetings for discussions on marketing strategy." Atom can semantically search through your transcribed meeting archives (stored in Notion & LanceDB) to find relevant information quickly.
*   **Proactive Schedule Optimization:** With Autopilot, Atom can learn your work patterns and preferences. "My mornings are for deep work. Keep them as free of meetings as possible." Atom will then intelligently schedule new events accordingly.
*   **Quickly Access Information:** "What was the outcome of the Project Phoenix meeting last month?" Atom can search your linked Notion notes and relevant event details to provide you with the context you need.
*   **Stay on Top of Your Day:** "What's on my agenda for today?" or "Do I have any free time this afternoon for a quick call?"
*   **Proactive Meeting Prep:** "Atom, get me ready for my meeting with 'Project X'." Atom gathers related notes, emails, and tasks.
*   **Weekly Review & Preview:** "Atom, what's my weekly digest?" Atom summarizes completed tasks, key meetings, and highlights upcoming critical items.
*   **Intelligent Follow-ups:** After a meeting, ask "Atom, what follow-ups for the 'Project X' meeting?" Atom analyzes notes/transcripts for actions, decisions, and questions.

## Documentation

Atom provides several resources to help you get started and make the most of its features:

*   **Local Deployment (Docker Compose):** For detailed instructions on setting up and running Atom locally using Docker Compose, please see the [Local Docker Deployment Guide](./atomic-docker/README.md).
*   **AWS Cloud Deployment:** To deploy Atom to your own AWS account for a scalable solution, refer to the [AWS Cloud Deployment Guide](./deployment/aws/README.md).
*   **Technical Documentation:** Additional technical details, API guides, and development logs can be found in the [atomic-docker/docs/](./atomic-docker/docs/) directory.
*   **Configuration Details:** For a comprehensive list of environment variables, consult the `.env.example` file in the `atomic-docker/project/` directory and the setup sections within the deployment guides mentioned above.

## Features
Atom comes packed with a variety of features designed to enhance your productivity. These include:

*   **Smart Scheduling & Time Management:** AI-powered tools to manage your calendar effectively.
*   **Integrated Note-Taking & Research:** Seamlessly create notes and conduct research with AI assistance.
*   **Live Meeting Attendance and Transcription:** Atom can join Zoom, Google Meet, and Microsoft Teams meetings, transcribe them in real-time, and save the notes to Notion. Includes status tracking and audio device selection (in development).
*   Comprehensive voice-driven task management using a Notion database backend.
*   Semantic search capabilities across your meeting transcript archive.
*   Automated extraction of action items and decisions from meeting transcripts.
*   **Smart Meeting Preparation:** Gathers relevant documents, emails, and tasks before your meetings.
*   **Automated Weekly Digest:** Summarizes your past week's accomplishments and previews upcoming critical items.
*   **Intelligent Follow-up Suggester:** Analyzes meeting notes or project documents to suggest action items, decisions, and questions.

For a detailed list and explanation of all features, please see our [Features Document](./FEATURES.md).

## Core Agent Capabilities & Commands

The Atom Agent understands a variety of commands to interact with your integrated services. Commands are typically issued in a chat interface with the agent.
The agent's natural language understanding (NLU) has been significantly enhanced, particularly for creating and querying calendar events and for managing tasks using voice commands.

Atom provides a rich set of commands to manage your productivity. You can interact with Atom to:
*   **Manage your calendar:** List, create, and modify events across Google Calendar and Microsoft Teams.
*   **Handle CRM tasks:** Create and retrieve contacts in HubSpot.
*   **Manage tasks in Notion:** Create, query, and update tasks in your designated Notion task database using natural language (e.g., "Atom, add 'buy milk' to my shopping list due tomorrow," "Atom, what are my work tasks for this week?").
*   **Search meeting transcripts:** Perform semantic searches across your meeting notes (e.g., "Atom, find meetings where we discussed the Q3 budget").
*   **Communicate via Slack:** Send messages and list channels.
*   **Manage video meetings:** List and get details for Zoom and Google Meet events.
*   **Process payments:** Interact with Stripe to list payments.
*   **Handle accounting:** Work with QuickBooks Online to manage invoices.
*   **Take notes and conduct research:** Create notes in Notion, initiate multi-agent research projects, and process research queues.
*   **Prepare for meetings:** "Atom, prep me for my meeting on [topic/date]."
*   **Get weekly summaries:** "Atom, what's my weekly digest?"
*   **Suggest follow-ups:** "Atom, what are the follow-ups for [meeting/project context]?"
*   And much more, including general commands like `help`.

For a more detailed list of commands and their specific syntax, please refer to the agent's `help` command or explore the agent's capabilities through interaction.

## Configuration (Environment Variables)

The Atom Agent uses environment variables for its configuration and to connect to various third-party services.

Atom requires various environment variables to be set for full functionality, including API keys for OpenAI, Notion, Deepgram, and credentials for integrated services like Google Calendar, HubSpot, Slack, Zoom, Microsoft Teams, Stripe, and QuickBooks Online. You will also need to configure settings for LanceDB storage and web search APIs.
Additional important variables for new features include:
*   `ATOM_NOTION_TASKS_DATABASE_ID`: The ID of your Notion database to be used for task management.
*   `LANCEDB_URI`: The URI for your LanceDB instance (e.g., `./lance_db` for a local setup, or a remote URI if applicable). This is required for the semantic search of meeting transcripts.
*   `PYTHON_API_SERVICE_BASE_URL`: (Optional) If your Python backend service runs on a different URL than the default (`http://localhost:8080`), specify it here.
Remember to consult the `.env.example` file for a comprehensive list.

For a comprehensive list of all environment variables and their setup, please refer to the `.env.example` file in the `atomic-docker/project/` directory and the detailed setup instructions in the deployment guides for [Local Docker Compose](./atomic-docker/README.md) and [AWS Cloud Deployment](./deployment/aws/README.md).

## Diagram

### Meeting Assist
```mermaid
    sequenceDiagram
    actor Alice
    participant A as Atom
    actor Bob
    actor John
    participant H as handshake.Atomlife.app
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

This project offers multiple ways to deploy and run the Atom application stack.

### Local Docker Compose

For local development, testing, and self-hosting on a single machine, the project can be run using Docker Compose. This method utilizes the services defined in the `atomic-docker/` directory.

-   **Setup and Instructions:** See the detailed guide in [atomic-docker/README.md](./atomic-docker/README.md).

### AWS Cloud Deployment (Self-Hosted)

For a scalable and robust cloud environment, you can deploy the entire application stack to your own AWS account. This deployment is managed by the AWS Cloud Development Kit (CDK) and provisions all necessary infrastructure, including managed services for databases, messaging, and search where appropriate.

-   **Features:** Deploys core application services, Optaplanner, a new `python-agent` service (for notes and research), and utilizes AWS S3, Amazon EFS (for LanceDB vector stores), and Amazon MSK Serverless. Amazon OpenSearch Service is no longer used.
Note: The Python backend service (often named `python_api_service` or `python-agent` in deployment configurations) has been updated with new responsibilities. It now handles task management operations with Notion and semantic search queries using LanceDB, in addition to its previous roles. Ensure it is deployed with access to necessary configurations (Notion tokens, LanceDB URI) and that the `notion-client>=2.0.0` dependency is included in its environment.

-   **Detailed Guide:** For prerequisites, setup instructions, deployment steps, and management, please refer to the comprehensive [AWS Deployment Guide](./deployment/aws/README.md).

## Support the Project
- I'm spending 100% of my work time on this project
- Star this repository, so I can start an Open Collective to support this project
- In process of setting up Github Sponsors
- Follow me on Twitter: https://twitter.com/rish1_2
- Used Atom? write a review or let me know!

## Contributing

1. Fork this repository and clone the fork to your machine
2. Create a branch (`git checkout -b my-new-feature`)
3. Implement a new feature or fix a bug and add some tests or proof of fix
4. Commit your changes (`git commit -am 'Added a new feature'`)
5. Push the branch to your fork on GitHub (`git push origin my-new-feature`)
6. Create new Pull Request from your fork
