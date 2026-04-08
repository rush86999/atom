# Agent System Documentation

Complete guide to Atom's multi-agent system, governance, and orchestration.

## Overview

Atom's agent system is built around **multi-agent coordination** with graduated autonomy and governance. Agents progress through four maturity levels (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) and can handle tasks ranging from simple queries to complex multi-agent workflows.

## Quick Links

### Core Orchestration Systems
- **[Queen Agent (Queen Hive)](../QUEEN_AGENT.md)** - Structured workflow automation (predefined blueprints)
- **[Fleet Admiral](../FLEET_ADMIRAL.md)** - Unstructured complex tasks (dynamic fleet coordination)
- **[Unstructured Complex Tasks](../UNSTRUCTURED_COMPLEX_TASKS.md)** - Intent classification and routing

### Key Concept: Queen Agent vs Fleet Admiral

| Aspect | Queen Agent (Queen Hive) | Fleet Admiral |
|--------|-------------------------|---------------|
| **Task Type** | Structured, repeatable | Unstructured, novel |
| **Planning** | Predefined blueprints | Dynamic discovery |
| **Agents** | Fixed team | Dynamic recruitment |
| **Use Case** | Workflow automation | Complex problem-solving |
| **Example** | "Execute sales blueprint" | "Research competitors + build integration" |

## Core Documentation

### Governance & Maturity
| Document | Description |
|----------|-------------|
| [governance.md](governance.md) | Maturity levels, permissions, and lifecycle management |
| [graduation.md](graduation.md) | How agents learn and get promoted |
| [training.md](training.md) | Training workflow for student agents |

### Orchestration & Routing
| Document | Description |
|----------|-------------|
| [meta-agent.md](meta-agent.md) | Intent classification and central orchestration |
| [overview.md](overview.md) | Agent system overview and intent classification |
| [unstructured-tasks.md](unstructured-tasks.md) | Unstructured tasks and domain creation |

### Guidance & Supervision
| Document | Description |
|----------|-------------|
| [guidance-system.md](guidance-system.md) | Real-time agent operation tracking |
| [supervision-implementation.md](supervision-implementation.md) | Supervision system implementation |
| [fleet-admiral.md](fleet-admiral.md) | Fleet Admiral orchestration (also see root docs) |

### Training & Learning
| Document | Description |
|----------|-------------|
| [marketplace.md](marketplace.md) | Agent marketplace integration |

## Agent Maturity Levels

| Level | Confidence | Triggers | Capabilities |
|-------|-----------|----------|-------------|
| **STUDENT** | <0.5 | ❌ Blocked | Read-only (charts, markdown) |
| **INTERN** | 0.5-0.7 | ⚠️ Proposal required | Streaming, form presentation |
| **SUPERVISED** | 0.7-0.9 | ✅ Supervised | Form submissions, state changes |
| **AUTONOMOUS** | >0.9 | ✅ Full execution | All capabilities |

## Intent Classification

User requests are classified into three types:

1. **CHAT** - Simple informational queries → LLMService
2. **WORKFLOW** - Structured, repeatable processes → **Queen Agent** (Workflow Automation)
3. **TASK** - Unstructured, complex tasks → **Fleet Admiral** (Dynamic Fleet Coordination)

## Agent Specialization

Atom supports **8 built-in domain templates** for specialist agents:

- `finance_analyst` - Financial analysis, reporting, forecasting
- `sales_assistant` - Lead management, CRM integration, pipeline tracking
- `ops_coordinator` - Workflow optimization, scheduling
- `hr_assistant` - Employee management, onboarding, policies
- `procurement_specialist` - Purchasing, vendor management, RFPs
- `knowledge_analyst` - Research, documentation, synthesis
- `marketing_analyst` - Campaign management, ROI analysis
- `king_agent` - Multi-domain coordination

## Quick Start

### For Workflow Automation (Structured Tasks)
Use **Queen Agent** when you have:
- Predefined, repeatable business processes
- Known steps that can be blueprinted
- Requirements for consistent, reliable execution

See: [Queen Agent Documentation](../QUEEN_AGENT.md)

### For Complex Problem-Solving (Unstructured Tasks)
Use **Fleet Admiral** when you have:
- Novel, complex challenges
- Tasks requiring adaptive planning
- Need for multiple specialist agents

See: [Fleet Admiral Documentation](../FLEET_ADMIRAL.md)

## Related Documentation

### Root Documentation
- [QUEEN_AGENT.md](../QUEEN_AGENT.md) - Queen Agent complete guide
- [FLEET_ADMIRAL.md](../FLEET_ADMIRAL.md) - Fleet Admiral complete guide
- [UNSTRUCTURED_COMPLEX_TASKS.md](../UNSTRUCTURED_COMPLEX_TASKS.md) - Intent classification system
- [STUDENT_AGENT_TRAINING_IMPLEMENTATION.md](../STUDENT_AGENT_TRAINING_IMPLEMENTATION.md) - Training system
- [ATOM_CLI_SKILLS_GUIDE.md](../ATOM_CLI_SKILLS_GUIDE.md) - CLI skills

### Integration Points
- [Canvas System](../canvas/) - Visual presentations and agent guidance
- [Episodic Memory](../intelligence/episodic-memory.md) - Agent learning framework
- [Package Governance](../PYTHON_PACKAGES.md) - Python package support

---

*Last Updated: April 7, 2026*
