# Atom: Your Open-Source Superpowered Siri/Alexa (AI assistant) for Enhanced Productivity

Atom is a powerful and flexible open-source AI assistant designed to streamline your workflow, intelligently manage your schedule, automate research, and organize your information. Take control of your productivity with an assistant that you can host yourself, ensuring privacy and customization.

## Why Choose Atom?
*   **Empower Your Productivity:** Let Atom handle schedules, finances, notes, and communications so you can focus on what matters.
*   **Open Source & Transparent:** Full visibility into operations - no black boxes.
*   **Self-Hosted Privacy & Control**: Host on your infrastructure for maximum privacy.
*   **Finance, Money & Budgeting**: Complete finance suite with Plaid banking integration and wake word "Atom" for natural language queries - net worth, budgets, spending analysis, goals, investments, and secure transaction search via Gmail email receipts.
*   **Communication & CRM**: Voice-enabled customer relationship management across emails, Slack, Teams, and social media.
*   **Voice-First Interface**: "Atom show my net worth" or "Atom schedule a meeting" - works after wake word detection.
*   **Highly Customizable:** Extensible design for your specific needs.
*   **Seamless Integrations:** Connected finance (banks, investments), communication tools, calendars and research capabilities.

## Table of Contents
- [Why Choose Atom?](#why-choose-atom)
- [Example Use Cases](#example-use-cases)
- [Comprehensive Use Cases](./USE_CASES.md)
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
- [Comprehensive Use Cases Documentation (All Scenarios)](./USE_CASES.md)


## Example Use Cases
Tired of juggling multiple apps and struggling to stay organized? Atom is here to help you reclaim your focus and boost your productivity. Here are a few ways Atom can simplify your work and personal life:

*   **Effortless Meeting Coordination:** "Find a time next week for a 30-minute meeting with Sarah and John, prioritizing Wednesday afternoon." Atom will check everyone's availability (integrating with their calendars if permitted) and propose optimal times.
*   **Smart Task Management (Voice-Powered):** Use natural voice commands like "Atom, create a task: follow up with marketing by Friday" or "Atom, what are my tasks for today?" Atom manages these tasks in a dedicated Notion database you configure.
*   **Automated Information Gathering:** "Research the latest trends in AI-powered personal assistants and summarize the key findings in a Notion document." Atom's research agents can browse, collect, and synthesize information, delivering it directly to your knowledge base.
*   **Voice-Powered Note-Taking:** While commuting, you can say: "Atom, take an audio note: Idea for marketing campaign - focus on social media engagement and influencer collaborations." Atom will transcribe the audio and save it to Notion.
*   **Automated Meeting Summaries & Action Items:** Atom can process your meeting transcripts (e.g., from live meeting attendance or uploaded recordings) and then automatically extract key decisions and action items directly into your Notion meeting notes.
*   **Intelligent Information Retrieval:** Ask Atom "What did we decide about Project X?" or "Search my meetings for discussions on marketing strategy." Atom can semantically search through your transcribed meeting archives (stored in Notion & LanceDB) to find relevant information quickly.
*   **Proactive Schedule Optimization:** With Autopilot, Atom can learn your work patterns and preferences. "My mornings are for deep work. Keep them as free of meetings as possible." Atom will then intelligently schedule new events accordingly.
*   **LLM-Powered Scheduling:** "Find a time for a 30-minute meeting with Sarah and John to discuss the Q3 marketing plan." Atom will use a large language model to parse your request and then find an optimal time for the meeting.
- **Comprehensive Finance Management:** Wake word activated finance commands via Plaid banking: "Atom what's my net worth today?" gives complete financial overview including secure bank connections, "Atom show my dining budget" displays budget analysis, "Atom where did I spend most money this month?" provides spending insights across categories, "Atom create emergency fund goal for $5000" sets up goal tracking, "Atom find Amazon purchases over $75" combines bank transactions and Gmail receipt search.
- **Quickly Access Information:** "What was the outcome of the Project Phoenix meeting last month?" Atom can search your linked Notion notes and relevant event details to provide you with the context you need.
- **Stay on Top of Your Day:** "What's on my agenda for today?" or "Do I have any free time this afternoon for a quick call?"
- **Proactive Meeting Prep:** "Atom, get me ready for my meeting with 'Project X'." Atom gathers related notes, emails, and tasks.
- **Weekly Review & Preview:** "Atom, what's my weekly digest?" Atom summarizes completed tasks, key meetings, and highlights upcoming critical items.
- **Intelligent Follow-ups:** After a meeting, ask "Atom, what follow-ups for the 'Project X' meeting?" Atom analyzes notes/transcripts for actions, decisions, and questions.
- **Banking Integration**: Complete financial management with bank account connections, budget tracking, and intelligent spending insights.

## Documentation

For comprehensive information about Atom, including setup, deployment, and features, please refer to the following guides:

*   **[Features Overview](./FEATURES.md):** A detailed list and explanation of all of Atom's capabilities.
*   **[Docker Compose Deployment](./atomic-docker/README.md):** Instructions for setting up and running Atom locally using Docker Compose.
*   **[AWS Cloud Deployment](./deployment/aws/README.md):** A guide for deploying Atom to your own AWS account for a scalable, self-hosted solution.
*   **[Technical Documentation](./atomic-docker/docs/):** Additional technical details, API guides, and development information.

## Features

Atom includes complete personal finance management with natural language and voice activation:

**🎤 Atom Finance Suite (Wake Word Enabled)**
- **Complete Net Worth Overview**: "Atom what's my net worth?" - Real-time financial health across all Plaid-connected bank accounts and credit cards
- **Smart Budget Management**: "Atom show my dining budget this month" - Visual insights combining bank transaction data with spending predictions
- **Spending Pattern Analysis**: "Atom where did I spend most money?" - AI-powered categorization from bank transactions with trend alerts
- **Goal Setting & Tracking**: "Atom create emergency fund goal for $5000" - Smart progress tracking connecting bank balances to goal milestones
- **Investment Portfolio**: "Atom show portfolio performance" - Real-time investment holdings and allocation analysis
- **Natural Transaction Search**: "Atom find Amazon purchases over $75 this quarter" - Semantic search across bank transactions plus Gmail receipt extraction
- **Budget vs Actual**: "Atom compare dining budget to actual spending" - Smart variance analysis using live bank transaction data

*   **AI-Powered Scheduling:** Smartly manages your calendar with AI-driven event matching, automated tagging, and customizable templates.
*   **Voice-Powered Finance Suite:** Complete finance management with Plaid-powered bank connections and Gmail integration via natural language voice commands - all accessible via wake word "Atom".
*   **Voice-Powered Task Management:** Use natural language to manage tasks in Notion alongside comprehensive financial management features.
*   **Integrated Notes, Research & Finance:** Take notes via text or audio, leverage multi-agent research, and track personal finances including budgeting, net worth, investments, and spending analysis with natural language queries.
*   **Semantic Search:** Instantly find information across your meeting transcripts and notes.
*   **Live Meeting Assistance:** Atom can join meetings, provide real-time transcription, and extract action items.
*   **Proactive Assistance:** Get automated weekly digests, smart meeting preparation, and intelligent follow-up suggestions.

For a comprehensive list of all features and capabilities, including wake word finance commands, please see our **[Features Overview Document](./FEATURES.md)**.

## Core Agent Capabilities

Use Atom's AI agent via chat or wake word to manage your productivity and finances. The agent's enhanced Natural Language Understanding (NLU) allows you to:

*   **Manage Calendars & Finances:** Create, list, and modify events in Google Calendar and Microsoft Teams, plus manage personal finances via natural language: net worth, budgets, investments, and spending tracking across all accounts.
*   **Manage Calendars & Communications:** Create events in Google Calendar, manage Teams meetings, track emails across Gmail, send Slack messages.
*   **Finance Management with Voice Recognition:** Complete finance suite - wake word "Atom" activates voice commands for net worth, budgets, spending insights, goal tracking, portfolio analysis, and transaction search.
*   **Voice Task Management:** Natural language to create, query and update tasks: "Atom create follow-up task for finance review" in your Notion database.
*   **CRM & Customer Communications:** Voice-enabled contact management, email campaigns, meeting coordination across all platforms.
*   **Search Across Knowledge:** Semantic search through meetings, notes, emails and financial data.
*   **Multi-agent Research:** Automated competitor analysis, market research and data collection. 

For a complete list of integrations and agent capabilities, see the **[Features Overview Document](./FEATURES.md)**.

## Configuration

Atom is configured using environment variables. For a complete and detailed list of all required and optional variables, please consult the `.env.example` file located in the `atomic-docker/project/` directory.

Specific setup instructions and variable explanations for each deployment method can be found in their respective guides:
*   **[Docker Compose Deployment Guide](./atomic-docker/README.md)**
*   **[AWS Cloud Deployment Guide](./deployment/aws/README.md)**

## Diagram

### Voice Finance Integration
```mermaid
    sequenceDiagram
    participant User
    participant Wake
    participant NLU
    participant Finance
    participant Backend
    
    User->>Wake: "Atom what's my net worth"
    Wake->>NLU: Passes query to NLU
    NLU->>Finance: Processes finance intent
    Finance->>Backend: Queries financial data
    Finance-->>User: "Your net worth is [amount]"
```

## Deployment Options

Atom offers two primary methods for deployment, giving you the flexibility to choose between a simple local setup or a scalable cloud solution.

### Local Docker Compose

Run Atom on a single machine for local development, testing, or small-scale self-hosting. This method uses Docker Compose to orchestrate all the necessary services.

*   **Setup and Instructions:** See the **[Docker Compose Deployment Guide](./atomic-docker/README.md)**.

### AWS Cloud Deployment (Self-Hosted)

Deploy the entire application stack to your own AWS account for a robust, scalable, and private cloud environment. This deployment is managed by the AWS Cloud Development Kit (CDK) and leverages AWS managed services for optimal performance and reliability.

*   **Setup and Instructions:** See the **[AWS Cloud Deployment Guide](./deployment/aws/README.md)**.

### Web Version

The web version of Atom is available at [https://github.com/rush86999/atom/tree/main/atomic-docker/app_build_docker](https://github.com/rush86999/atom/tree/main/atomic-docker/app_build_docker).

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


## Comprehensive Use Cases

Atom can automate complex workflows across independent integrations. For complete scenarios including banking, email, team communications, and cross-platform automation, see our [Comprehensive Use Cases Documentation](./USE_CASES.md).

Key scenarios include:
- **Financial Management**: Complete money tracking with banking integrations
- **Communication Hub**: Unified email and team collaboration
- **Project Management**: Multi-platform workflow automation
- **Personal Assistant**: Individual and business role optimization
- **Voice-First Operations**: Cross-platform voice commands