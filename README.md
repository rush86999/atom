<div align="center">

# ATOM Platform
### The AI Workforce for Your Entire Business

> **Developer Note:** For technical setup and architecture, please see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

![Atom Platform](https://github.com/user-attachments/assets/398de2e3-4ea6-487c-93ae-9600a66598fc)

**Automate your workflows by talking to an AI — and let it remember, search, and handle tasks like a real assistant.**

[![License](https://img.shields.io/badge/License-AGPL-blue.svg)](LICENSE.md)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)]()

</div>

## ✨ What is Atom?

Atom is not just another automation tool; it is your **AI-powered digital workforce**. Atom combines the flexibility of visual workflow builders (like Zapier/Activepieces) with the intelligence of LLM-based agents.

Just **speak** or **type** your request, and Atom's specialty agents — from Sales to Engineering — will plan, verify, and execute complex workflows across your entire tech stack.

---

## 🚀 Key Features

### 🎙️ **Voice Interface**
**"Hey Atom, create a workflow to sync new Shopify orders to Slack."**
- **Hands-Free Automation**: Build complex workflows using just your voice.
- **Natural Language Understanding**: No need to learn propriety syntax; just speak naturally.
- **Real-Time Feedback**: Watch as Atom visualizes its reasoning process step-by-step.

### 🤖 **Specialty Agents**
Why rely on generic AI when you can hire experts?
- **Sales Agent**: Manages CRM pipelines, scores leads, and drafts outreach.
- **Marketing Agent**: Automates campaigns, social posting, and analytics reports.
- **Engineering Agent**: Handles PR notifications, deployments, and incident response.
- **Governance**: Agents start as "Students" and earn "Autonomy" as they gain your trust.

### 🛡️ **Agent Governance System**
- **Maturity Levels**: Agents progress from 'Student' to 'Autonomous' based on performance.
- **Approval Workflows**: Sensitive actions (like deployments) require human approval until confidence is high.
- **Safety First**: "Computer Use" agents are strictly sandboxed and monitored.

### 🧠 **Universal Memory & Context**
Atom remembers everything so you don't have to repeat yourself.
- **Capability Recall**: Agents use long-term memory to remember which services you've connected, allowing them to proactively suggest actions.
- **Unified Index**: Emails, Notion docs, Jira tickets, and Slack threads are indexed for instant retrieval.
- **Knowledge Graph**: Atom builds a graph of your people, projects, and tasks to understand *relationships*, not just keywords.
- **Trusted Memory (New)**: Store critical business facts (policies, compliance rules) with **JIT Citations**. Agents must "Trust but Verify" these facts against the source document before acting, ensuring 100% adherence to your rules.
- **Privacy First**: Sensitive data like API keys and PII are automatically redacted and encrypted (Fernet at-rest).
- **Self-Evolving World Model**: Agents store and retrieve past "experiences" to learn from success and failure. See [docs/ai-world-model.md](docs/ai-world-model.md).

### 🔌 **Deep Integrations (Hybrid Runtime)**
Connect your entire business ecosystem with over **500+ apps**.
- **Hybrid Engine**: Python orchestration + Node.js Piece Engine for the full **ActivePieces** catalog.
- **Swarm Discovery**: Every specialty agent now inherently "knows" how to list workflows, trigger automations, and call integrations.
- **Node-on-Demand**: Integrations are installed dynamically on-the-fly to ensure the catalog is always up-to-date.

### 🏢 **Unified Command Centers**
Atom provides a single plane of glass for your departmental operations.
- **Project Command Center**: Unified task view across Jira, Asana, Trello, and Monday.
- **Sales Command Center**: Aggregated pipeline from Salesforce, HubSpot, and Zoho CRM.
- **Support Command Center**: Unified inbox for Zendesk, Freshdesk, and Intercom tickets.
- **Knowledge Command Center**: Global Intelligence Hub for searching across GDrive, OneDrive, Zoho WorkDrive, and Notion.

### 🤝 **Real-time Collaboration**
- **In-Context Discussion**: Every Command Center includes a real-time side-chat for team alignment.
- **Hybrid Chat**: Discussion threads include both humans and specialty agents, allowing for seamless AI-assisted collaboration.
- **Presence Tracking**: See exactly which dashboard your team members are viewing in real-time.

### 🌐 **Universal Communication Bridge** (New)
Seamlessly interact with your workforce from any platform.
- **Unified Messaging**: One standard interface for Slack (`/run`), WhatsApp, and custom webhooks.
- **Agent-to-Agent Loop**: Agents can now discover (`/agents`) and delegate tasks to each other directly via the bridge.
- **Async Feedback**: Delegated tasks automatically route their results back to the requester, whether it's a user on Slack or another agent.

---

## 🎯 Example Use Cases

| Department | Scenario |
|------------|----------|
| **Sales** | **Lead Enrichment**: "When a new lead arrives in HubSpot, research their company on LinkedIn, score them based on fit, and slack the relevant account executive." |
| **Finance** | **Invoice Reconciliation**: "Watch for PDF invoices in Gmail, extract the data, match it against QuickBooks, and flag any discrepancies for review." |
| **Support** | **Ticket Triage**: "Analyze incoming Zendesk tickets for sentiment, route urgent issues to the #escalations channel, and draft a polite initial response." |
| **HR** | **Onboarding**: "When a new employee is added to BambooHR, provision their Google Workspace account, invite them to Slack channels, and schedule their orientation." |

---

## 🏎️ Getting Started

### Quick Start (Docker)
The fastest way to experience Atom is using Docker:

```bash
git clone https://github.com/rush86999/atom.git
cd atom
docker-compose up -d
```
Access the dashboard at: **http://localhost:3000**

> For detailed installation guides, configuration options, and architecture diagrams, please refer to our **[Development Guide](docs/DEVELOPMENT.md)**.

---

## 🔒 Enterprise-Grade Security
- **BYOK (Bring Your Own Key)**: Use your own OpenAI, Anthropic, or Gemini keys with strict budget limits.
- **Human-in-the-Loop**: designated workflows require manual approval before execution.
- **Audit Logs**: Every action taken by an agent is logged, timestamped, and traceable.

---

## 📞 Support & Community

- **Documentation**: Check the `docs/` directory for in-depth guides.
- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues)
- **License**: AGPL v3 - See [LICENSE.md](LICENSE.md)

<div align="center">

**Experience the future of work.**
[Get Started](#-getting-started)

</div>