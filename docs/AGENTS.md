# Agent System Documentation

Core agent capabilities including governance, graduation, and orchestration.

## Core Components

### Governance & Maturity
- **[Agent Governance](AGENT_GOVERNANCE.md)** - Maturity levels, permissions, and lifecycle management
- **[Agent Graduation Guide](AGENT_GRADUATION_GUIDE.md)** - How agents learn and get promoted
- **[Capability Graduation](AGENT_GOVERNANCE_LEARNING_INTEGRATION.md#capability-graduation-logic)** ⚡ **Individual capability progression (5/20/50 rule)**
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

### ⚡ Capability Graduation Logic

Individual capabilities (skills, tools, actions) graduate independently based on usage:

| Capability Level | Promotion Requirement | Added Permissions |
|-----------------|---------------------|-------------------|
| **STUDENT → INTERN** | 5 successful uses | Basic tool access |
| **INTERN → SUPERVISED** | 20 successful uses | Advanced integrations |
| **SUPERVISED → AUTONOMOUS** | 50 successful uses | Full autonomy, critical actions |

**How It Works**:
1. Each capability use is tracked via `CapabilityGraduationService.record_usage()`
2. Success counts accumulate in `agent.properties["capability_stats"]`
3. Automatic promotion when thresholds are reached
4. Can be reset to STUDENT if issues occur

**See**: [Capability Graduation Details](AGENT_GOVERNANCE_LEARNING_INTEGRATION.md#capability-graduation-logic)

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
