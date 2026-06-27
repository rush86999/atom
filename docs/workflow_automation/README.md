# Workflow Automation

Workflow engines, optimization, and automation systems.

## 📚 Quick Navigation

- **[Enhanced Workflow Guide](ENHANCED_WORKFLOW_GUIDE.md)** - Complete workflow guide
- **[Intelligence Engine](INTELLIGENCE_ENGINE.md)** - AI-powered workflow optimization
- **[Monitoring System](MONITORING_SYSTEM.md)** - Workflow monitoring
- **[Optimization Engine](OPTIMIZATION_ENGINE.md)** - Performance optimization
- **[Troubleshooting Engine](TROUBLESHOOTING_ENGINE.md)** - Debugging workflows

## 🔄 Workflow Types

### Structured Workflows (Queen Agent) ✨ Enhanced 2026
- **Blueprint-Based**: Predefined workflow templates
- **Conductor Agent**: 5 execution strategies (SEQUENTIAL, PARALLEL, HYBRID, ADAPTIVE, ROLLBACK_SAFE)
- **Workflow State Machine**: Validated state transitions with rollback support
- **Event Bus**: Event-driven workflow triggering with pub/sub
- **Workflow Templates**: Pre-built enterprise patterns
- **Use Cases**: Daily reports, data pipelines, CRM workflows
- **Guide**: Queen Agent User Guide

### Unstructured Tasks (Fleet Admiral) ✨ Enhanced 2026
- **Dynamic**: Agent recruitment for complex tasks
- **Flexible**: Adapts to task requirements
- **Enhanced Coordination**: Event bus + blackboard communication
- **Rollback Support**: Automatic fleet recovery
- **Use Cases**: Research, multi-step projects, cross-domain tasks
- **Guide**: [Fleet Admiral](../agents/fleet-admiral.md)

### Skill Composition
- **DAG Workflows**: Directed acyclic graph execution
- **Skill Chaining**: Connect multiple skills
- **Error Handling**: Automatic retry and fallback
- **Guide**: Skill Composition Patterns

## 🎯 Key Features

### AI-Powered Optimization
- **Smart Routing**: Intent-based workflow selection
- **Performance Tuning**: Automatic optimization
- **Error Recovery**: Self-healing workflows

### Monitoring & Debugging
- **Real-Time Tracking**: Monitor workflow execution
- **Error Analysis**: Automatic error detection
- **Performance Metrics**: Latency, success rate, resource usage

### Integration Support
- **40+ Platforms**: Slack, Gmail, HubSpot, Salesforce, etc.
- **Custom Skills**: Python and npm package support
- **Webhooks**: Trigger workflows from external events

## 🔧 Quick Start

### Create a Structured Workflow
```python
# Define blueprint
blueprint = {
    "name": "Daily Sales Report",
    "steps": [
        {"action": "fetch_sales_data", "source": "hubspot"},
        {"action": "analyze_data", "model": "gpt-4"},
        {"action": "create_chart", "type": "line"},
        {"action": "send_report", "destination": "slack"}
    ]
}

# Execute workflow
queen_agent.execute_blueprint(blueprint)
```

### Create an Unstructured Task
```python
# Fleet Admiral recruits specialists
task = {
    "description": "Research competitors and build Slack integration",
    "complexity": "high",
    "deadline": "2026-04-15"
}

fleet_admiral.execute_task(task)
```

## 📖 Related Documentation

- **[Queen Agent](../agents/QUEEN_AGENT.md)** - Structured workflow automation
- **[Fleet Admiral](../agents/fleet-admiral.md)** - Dynamic agent coordination
- **Integrations** - Platform integrations

---

*Last Updated: April 12, 2026*
