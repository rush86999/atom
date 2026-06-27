# Agent System Documentation

Complete guide to Atom's multi-agent system, governance, and orchestration.

## Overview

Atom's agent system is built around **multi-agent coordination** with graduated autonomy and governance. Agents progress through four maturity levels (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) and can handle tasks ranging from simple queries to complex multi-agent workflows.

## Quick Links

### Core Orchestration Systems
- **[Queen Agent (Queen Hive)](QUEEN_AGENT.md)** - Structured workflow automation (predefined blueprints)
- **[Fleet Admiral](fleet-admiral.md)** - Unstructured complex tasks (dynamic fleet coordination)
- **[Unstructured Complex Tasks](unstructured-tasks.md)** - Intent classification and routing

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
| [supervision-implementation.md](../archive/legacy/supervision-implementation.md) | Supervision system implementation |
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

See: [Queen Agent Documentation](QUEEN_AGENT.md)

### For Complex Problem-Solving (Unstructured Tasks)
Use **Fleet Admiral** when you have:
- Novel, complex challenges
- Tasks requiring adaptive planning
- Need for multiple specialist agents

See: [Fleet Admiral Documentation](fleet-admiral.md)

## Related Documentation

### Root Documentation
- [QUEEN_AGENT.md](QUEEN_AGENT.md) - Queen Agent complete guide
- [FLEET_ADMIRAL.md](fleet-admiral.md) - Fleet Admiral complete guide
- [Unstructured Tasks](unstructured-tasks.md) - Intent classification system
- [STUDENT_AGENT_TRAINING_IMPLEMENTATION.md](../archive/legacy/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md) - Training system
- [ATOM_CLI_SKILLS_GUIDE.md](../guides/ATOM_CLI_SKILLS_GUIDE.md) - CLI skills

### Integration Points
- [Canvas System](../canvas/) - Visual presentations and agent guidance
- [Episodic Memory](../intelligence/episodic-memory.md) - Agent learning framework
- [Package Governance](../security/PYTHON_PACKAGES.md) - Python package support

---

*Last Updated: June 18, 2026*

---

## 🚀 2026 Enhancement Plan Integration

The agent system has been significantly enhanced through the 2026 Enhancement Plan:

### Phase 5: Enhanced Orchestration Patterns ✅ COMPLETE
- **Conductor Agent**: 5 execution strategies (SEQUENTIAL, PARALLEL, HYBRID, ADAPTIVE, ROLLBACK_SAFE)
- **Workflow State Machine**: Validated transitions with automatic rollback capability
- **Event Bus**: Real-time event-driven workflow triggering with pub/sub
- **Arbor Framework**: Hypothesis Tree Refinement (HTR) for workflow optimization

**See**: [ARBOR_FRAMEWORK.md](../architecture/ARBOR_FRAMEWORK.md) - Complete Arbor documentation with WorkflowHypothesisNode

### Enhanced Governance (2026) ✅ COMPLETE
- **Three-Layer Governance**: OPERATIONAL (<10ms), TACTICAL (<100ms), STRATEGIC (human-in-the-loop)
- **Policy Engine**: Context-aware evaluation with priority resolution
- **Experience-Driven Graduation**: Quality-weighted episodes (20% improvement in accuracy)

**See**: [governance.md](governance.md) - Complete governance documentation with 2026 enhancements

### Enhanced Learning (2026) ✅ COMPLETE
- **POMDP Memory Framework**: Write-manage-read loop for agent learning
- **Memory Consolidation**: Offline processing (inspired by human sleep)
- **Canvas Integration**: Canvas feedback feeds directly into graduation criteria

**See**: [../intelligence/episodic-memory.md](../intelligence/episodic-memory.md) - POMDP memory documentation

### Conductor Agent vs Queen Agent vs Fleet Admiral

| Aspect | Queen Agent | Fleet Admiral | Conductor Agent ✨ |
|--------|-------------|---------------|-------------------|
| **Task Type** | Structured, repeatable | Unstructured, novel | Complex optimization |
| **Planning** | Predefined blueprints | Dynamic discovery | Adaptive strategies |
| **Agents** | Fixed team | Dynamic recruitment | Dynamic recruitment |
| **Execution** | Blueprint-based | Intent-based | Strategy-based |
| **Strategies** | Sequential | Parallel | 5 strategies (SEQ, PAR, HYB, ADAPT, ROLLBACK) |
| **Use Case** | "Execute sales blueprint" | "Research + build integration" | "Optimize workflow with Arbor" |

**See**: [Conductor Agent Guide](../guides/QUEEN_AGENT_USER_GUIDE.md) - Complete Conductor documentation
