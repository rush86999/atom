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
- **Unified Index**: Emails, Notion docs, Jira tickets, and Slack threads are indexed for instant retrieval.
- **Knowledge Graph**: Atom builds a graph of your people, projects, and tasks to understand *relationships*, not just keywords.
- **Contextual Learning**: Atom absorbs your team's history (last 30 days of Slack, Jira, Email) so it hits the ground running with full context.
- **Cross-App Search**: Ask complex questions like *"What features did we promise Client X in last week's email?"*
- **Privacy First**: Sensitive data like API keys and PII are automatically redacted and encrypted.

### 🔌 **500+ Integrations**
Connect your entire business ecosystem.
- **Apps**: Slack, Gmail, HubSpot, Salesforce, Linear, Asana, Notion, and 500+ more via our catalog.
- **Visual Builder**: Drag-and-drop steps, loops, and branches for precise control.
- **Computer Use**: Atom can even control your desktop capabilities to interact with legacy software.

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