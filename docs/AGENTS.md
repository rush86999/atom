# Agent System Documentation

Core agent capabilities including governance, graduation, and orchestration.

## Core Components

### Governance & Maturity
- **[Agent Governance](AGENT_GOVERNANCE.md)** - Maturity levels, permissions, and lifecycle management
- **[Agent Graduation Guide](AGENT_GRADUATION_GUIDE.md)** - How agents learn and get promoted
- **[Student Agent Training](STUDENT_AGENT_TRAINING_IMPLEMENTATION.md)** - Training workflow for student agents
- **[Supervision & Learning](SUPERVISION_LEARNING_INTEGRATION_COMPLETE.md)** - Real-time supervision system

### Guidance & Orchestration
- **[Agent Guidance Implementation](AGENT_GUIDANCE_IMPLEMENTATION.md)** - Real-time agent operation tracking
- **[Governance Learning Integration](AGENT_GOVERNANCE_LEARNING_INTEGRATION.md)** - Learning from governance events

### Multi-Agent Coordination ✨ NEW
- **[Unstructured Complex Tasks](UNSTRUCTURED_COMPLEX_TASKS.md)** - Intent classification and dynamic routing
- **[Fleet Admiral](FLEET_ADMIRAL.md)** - Multi-agent orchestration for complex tasks

## Key Concepts

### Agent Maturity Levels
| Level | Confidence | Automated Triggers | Capabilities |
|-------|-----------|-------------------|--------------|
| **STUDENT** | <0.5 | Blocked (read-only) | Charts, markdown presentation |
| **INTERN** | 0.5-0.7 | Proposal required | Streaming, form presentation |
| **SUPERVISED** | 0.7-0.9 | Supervised execution | Form submissions, state changes |
| **AUTONOMOUS** | >0.9 | Full execution | All capabilities |

### Intent Classification
- **CHAT** - Simple queries → LLMService
- **WORKFLOW** - Structured tasks → QueenAgent
- **TASK** - Unstructured complex tasks → FleetAdmiral

## Quick Links

- **[Testing Index](TESTING_INDEX.md)** - Agent testing documentation
- **[Development Guide](DEVELOPMENT.md)** - Building agents
- **[API Documentation](API.md)** - Agent API endpoints

---

*Last Updated: April 5, 2026*
