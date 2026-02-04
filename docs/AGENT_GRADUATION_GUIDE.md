# Agent Graduation Guide

## Overview

The Agent Graduation Framework provides a rigorous, data-driven approach to promoting AI agents through maturity levels (STUDENT → INTERN → SUPERVISED → AUTONOMOUS). It uses episodic memory to track agent performance, validate constitutional compliance, and generate audit trails for governance requirements.

## Table of Contents

- [Why Graduation Matters](#why-graduation-matters)
- [Graduation Criteria](#graduation-criteria)
- [Readiness Score Calculation](#readiness-score-calculation)
- [Constitutional Compliance](#constitutional-compliance)
- [Use Cases](#use-cases)
- [Graduation Workflow](#graduation-workflow)
- [Edge Case Testing](#edge-case-testing)
- [Audit Trail Generation](#audit-trail-generation)

---

## Why Graduation Matters

### 1. Safety

Agents must demonstrate competence before gaining autonomy. Graduation ensures:
- Zero critical errors in AUTONOMOUS mode
- Constitutional compliance (tax laws, HIPAA, etc.)
- Proven track record of correct decisions

### 2. Governance Compliance

Regulated industries require audit trails proving:
- Agent performance over time
- Human intervention rates
- Compliance with domain-specific rules

### 3. Trust

Users need confidence that agents:
- Learn from past experiences
- Improve over time
- Don't repeat mistakes

---

## Graduation Criteria

### Maturity Levels

| Level | Description | Permissions |
|-------|-------------|-------------|
| **STUDENT** | Learning phase | Read-only, presentations |
| **INTERN** | Basic autonomy | Streaming, form presentations |
| **SUPERVISED** | Advanced autonomy | Form submissions, state changes (with supervision) |
| **AUTONOMOUS** | Full independence | All actions, no oversight |

### Promotion Requirements

| Promotion | Min Episodes | Max Intervention Rate | Min Constitutional Score |
|-----------|--------------|----------------------|--------------------------|
| STUDENT → INTERN | 10 | 50% | 0.70 |
| INTERN → SUPERVISED | 25 | 20% | 0.85 |
| SUPERVISED → AUTONOMOUS | 50 | 0% | 0.95 |

### Key Metrics

**Episode Count**: Number of completed episodes at current maturity level

**Intervention Rate**: Percentage of episodes requiring human correction
```
intervention_rate = total_interventions / episode_count
```

**Constitutional Score**: Compliance with domain rules (0.0 to 1.0)
- Validated against Knowledge Graph
- Tracks violations of tax laws, HIPAA, etc.
- Calculated per episode

---

## Readiness Score Calculation

### Formula

```
Readiness Score = (Episode Score × 40%) + (Intervention Score × 30%) + (Constitutional Score × 30%)

Where:
Episode Score = min(episode_count / min_episodes, 1.0) × 40
Intervention Score = (1 - intervention_rate / max_intervention_rate) × 30
Constitutional Score = (avg_constitutional_score / min_constitutional_score) × 30
```

### Example Calculation

**Scenario**: Agent seeking promotion to INTERN

**Metrics**:
- Episode count: 12 (min required: 10)
- Interventions: 4 out of 12 episodes = 33% (max allowed: 50%)
- Avg constitutional score: 0.78 (min required: 0.70)

**Score**:
```
Episode Score = (12 / 10) × 40 = 40 (capped at 40)
Intervention Score = (1 - 0.33 / 0.50) × 30 = (1 - 0.66) × 30 = 10.2
Constitutional Score = (0.78 / 0.70) × 30 = 33.4

Total = 40 + 10.2 + 33.4 = 83.6/100
```

**Result**: Ready for promotion (score > 70, all criteria met)

---

## Constitutional Compliance

### What is Constitutional Compliance?

Agents must adhere to domain-specific rules stored in the Knowledge Graph:
- **Tax Agents**: HST rules, provincial tax rates, exemption criteria
- **Medical Agents**: HIPAA regulations, clinical documentation standards
- **Legal Agents**: Confidentiality rules, document retention policies

### Validation

```python
from core.agent_graduation_service import AgentGraduationService

service = AgentGraduationService(db)

# Validate specific episode
result = await service.validate_constitutional_compliance(
    episode_id="episode_123"
)

# Returns:
# {
#   "compliant": True,
#   "score": 0.95,
#   "violations": [],
#   "episode_id": "episode_123"
# }
```

### Score Tracking

Each episode tracks:
```python
class Episode:
    constitutional_score: float  # 0.0 to 1.0
    human_intervention_count: int  # Number of corrections
    human_edits: JSON  # List of specific corrections
```

---

## Use Cases

### Use Case 1: MedScribe (Clinical Documentation)

**Scenario**: Hospital board requires proof that MedScribe agent can document clinical encounters with zero errors before autonomous operation.

**Requirements**:
- 100 episodes of clinical documentation
- 0 human interventions
- 1.0 constitutional score (HIPAA compliance)
- Full audit trail for board review

**Implementation**:

```python
# Create clinical documentation episodes
for encounter in patient_encounters:
    episode = await service.create_episode_from_session(
        session_id=encounter.session_id,
        agent_id="medscribe_agent",
        title=f"Clinical Documentation: {encounter.patient_id}"
    )
    # Episodes track:
    # - human_intervention_count (must be 0)
    # - constitutional_score (validated against HIPAA rules)
    # - clinical_accuracy_score (validated against medical records)

# Generate audit report for hospital board
audit = await service.get_graduation_audit_trail(agent_id="medscribe_agent")

board_report = f"""
MedScribe Graduation Report for Hospital Board Review
======================================================

Agent: {audit['agent_name']}
Current Maturity: {audit['current_maturity']}

Performance Metrics:
- Total Clinical Episodes: {audit['total_episodes']}
- Total Interventions: {audit['total_interventions']}
- Avg Constitutional Score (HIPAA): {audit['avg_constitutional_score']:.2f}

Graduation Status: {'✓ READY FOR AUTONOMOUS OPERATION' if audit['total_interventions'] == 0 else '✗ NOT READY'}

Episode Breakdown by Maturity:
"""
for maturity, count in audit['episodes_by_maturity'].items():
    board_report += f"- {maturity}: {count} episodes\n"

print(board_report)
```

**Sample Output**:
```
MedScribe Graduation Report for Hospital Board Review
======================================================

Agent: MedScribe Clinical Agent
Current Maturity: AUTONOMOUS

Performance Metrics:
- Total Clinical Episodes: 100
- Total Interventions: 0
- Avg Constitutional Score (HIPAA): 1.00

Graduation Status: ✓ READY FOR AUTONOMOUS OPERATION

Episode Breakdown by Maturity:
- STUDENT: 20 episodes
- INTERN: 30 episodes
- SUPERVISED: 50 episodes
- AUTONOMOUS: 0 episodes (ready to begin)

Recent Autonomous-Ready Episodes:
1. "Clinical Documentation: Patient #12345" - 0 interventions, 1.0 score
2. "Clinical Documentation: Patient #12346" - 0 interventions, 1.0 score
3. "Clinical Documentation: Patient #12347" - 0 interventions, 1.0 score
```

### Use Case 2: Brennan.ca (Sales Tax Compliance)

**Scenario**: Sales agent must understand Woodstock, Ontario pricing nuances (including HST exemptions) before sending autonomous emails to clients.

**Requirements**:
- 50 Woodstock-specific sales episodes
- 0 interventions on Woodstock pricing
- 0.95 constitutional score (Canada Tax Knowledge Graph)
- Validation of HST calculations for machinery sales

**Implementation**:

```python
# Create Woodstock-specific training episodes
woodstock_episodes = []
for sale in woodstock_sales:
    episode = await service.create_episode_from_session(
        session_id=sale.session_id,
        agent_id="sales_bot",
        title=f"Woodstock Sale: {sale.machinery_type} - HST Calculation"
    )
    woodstock_episodes.append(episode.id)

# Calculate readiness for Woodstock-specific operations
result = await service.calculate_readiness_score(
    agent_id="sales_bot",
    target_maturity="AUTONOMOUS"
)

# Filter for Woodstock episodes specifically
woodstock_count = len([ep for ep in episodes if "Woodstock" in ep.title])
woodstock_interventions = sum([
    ep.human_intervention_count for ep in episodes
    if "Woodstock" in ep.title
])

print(f"Woodstock-Specific Readiness:")
print(f"  Episodes: {woodstock_count}/50")
print(f"  Interventions: {woodstock_interventions} (must be 0)")

if woodstock_count >= 50 and woodstock_interventions == 0:
    print("✓ Ready for autonomous Woodstock sales emails")
else:
    print("✗ Not ready - more training required")
```

### Use Case 3: Tax Bot (Multi-Jurisdictional Compliance)

**Scenario**: Tax calculation agent must validate HST calculations across Canadian provinces before autonomous operation.

**Requirements**:
- 100 episodes per province (ON, BC, QC, AB)
- 0 interventions on tax rate calculations
- Validation against Canada Tax Knowledge Graph
- Edge case testing for exemption scenarios

**Implementation**:

```python
# Group episodes by province
province_stats = {}
for episode in all_episodes:
    province = extract_province(episode.title)  # e.g., "ON", "BC"
    if province not in province_stats:
        province_stats[province] = {"count": 0, "interventions": 0}
    province_stats[province]["count"] += 1
    province_stats[province]["interventions"] += episode.human_intervention_count

# Validate each province meets criteria
for province, stats in province_stats.items():
    print(f"{province}: {stats['count']} episodes, {stats['interventions']} interventions")
    if stats['count'] >= 100 and stats['interventions'] == 0:
        print(f"  ✓ {province} ready for autonomous operation")
    else:
        print(f"  ✗ {province} needs more training")
```

---

## Graduation Workflow

### Step 1: Check Readiness

```python
from core.agent_graduation_service import AgentGraduationService

service = AgentGraduationService(db)

result = await service.calculate_readiness_score(
    agent_id="student_agent",
    target_maturity="INTERN"
)

print(f"Ready: {result['ready']}")
print(f"Score: {result['score']}/100")
print(f"Gaps: {result['gaps']}")
print(f"Recommendation: {result['recommendation']}")
```

### Step 2: Run Edge Case Tests

```python
# Test agent on historical failures from other agents
edge_cases = [
    "edge_case_tax_exemption_1",
    "edge_case_hipaa_violation_1",
    "edge_case_pricing_error_1"
]

exam_result = await service.run_graduation_exam(
    agent_id="student_agent",
    edge_case_episodes=edge_cases
)

print(f"Exam Passed: {exam_result['passed']}")
print(f"Score: {exam_result['score']}/100")
```

### Step 3: Promote Agent

```python
if result['ready'] and exam_result['passed']:
    await service.promote_agent(
        agent_id="student_agent",
        new_maturity="INTERN",
        validated_by="admin_user"
    )
    print("Agent promoted successfully!")
```

### Step 4: Generate Audit Trail

```python
audit = await service.get_graduation_audit_trail(agent_id="student_agent")

# Save for compliance records
with open(f"graduation_audit_{agent_id}.json", "w") as f:
    json.dump(audit, f, indent=2)
```

---

## Edge Case Testing

### What are Edge Cases?

Edge cases are historical failure scenarios from other agents. Testing current agents against these edge cases ensures they don't repeat past mistakes.

### Creating Edge Case Episodes

```python
# Create edge case episode from historical failure
edge_case = Episode(
    title="Edge Case: HST Exemption for Agricultural Machinery",
    description="Historical failure where agent incorrectly applied HST to exempt equipment",
    agent_id="archive_failed_agent",
    topics=["hst", "exemptions", "agriculture"],
    constitutional_score=0.0,  # Failed
    human_intervention_count=1,  # Required correction
    human_edits=[
        {
            "field": "tax_rate",
            "original": "0.13",
            "correction": "0.0",
            "reason": "Agricultural machinery exempt from HST"
        }
    ]
)
```

### Running Edge Case Tests

```python
exam_result = await service.run_graduation_exam(
    agent_id="current_agent",
    edge_case_episodes=[edge_case.id]
)

# Check if agent handles edge case correctly
if exam_result['passed']:
    print("✓ Agent correctly handled edge case")
else:
    print("✗ Agent failed edge case - more training needed")
```

---

## Audit Trail Generation

### What's in the Audit Trail?

```python
audit = await service.get_graduation_audit_trail(agent_id="agent_123")

# Returns:
{
    "agent_id": "agent_123",
    "agent_name": "Tax Calculation Agent",
    "current_maturity": "INTERN",
    "total_episodes": 45,
    "total_interventions": 8,
    "avg_constitutional_score": 0.87,
    "episodes_by_maturity": {
        "STUDENT": 15,
        "INTERN": 30
    },
    "recent_episodes": [
        {
            "id": "ep_45",
            "title": "HST Calculation for Invoice #123",
            "started_at": "2026-02-03T10:30:00",
            "human_intervention_count": 0,
            "constitutional_score": 1.0
        },
        ...
    ]
}
```

### Exporting for Compliance

```python
import json
from datetime import datetime

# Generate compliance report
audit = await service.get_graduation_audit_trail(agent_id="agent_123")

report = {
    "generated_at": datetime.now().isoformat(),
    "agent_info": {
        "id": audit["agent_id"],
        "name": audit["agent_name"],
        "current_maturity": audit["current_maturity"]
    },
    "performance_metrics": {
        "total_episodes": audit["total_episodes"],
        "total_interventions": audit["total_interventions"],
        "avg_constitutional_score": audit["avg_constitutional_score"]
    },
    "episode_breakdown": audit["episodes_by_maturity"],
    "recent_episodes": audit["recent_episodes"][:10]
}

# Save to file
with open(f"graduation_audit_{agent_id}_{datetime.now().date()}.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"Audit trail saved: {f.name}")
```

---

## Best Practices

### 1. Track Interventions Granularly

```python
# Instead of just counting interventions
episode.human_intervention_count = 1

# Track what was corrected
episode.human_edits = [
    {
        "timestamp": "2026-02-03T10:30:00",
        "field": "tax_rate",
        "original": "0.13",
        "correction": "0.0",
        "reason": "Agricultural machinery exempt",
        "corrected_by": "tax_expert_1"
    }
]
```

### 2. Validate Constitutional Compliance

```python
# After each episode, validate against domain rules
compliance_result = await service.validate_constitutional_compliance(
    episode_id=episode.id
)

episode.constitutional_score = compliance_result["score"]

if not compliance_result["compliant"]:
    logger.warning(f"Constitutional violations: {compliance_result['violations']}")
```

### 3. Use Domain-Specific Episodes

```python
# Create domain-specific episodes for better tracking
episode = Episode(
    title=f"{domain} Task: {specific_task}",
    topics=[domain, ...],  # e.g., ["tax", "hst", "ontario"]
    metadata={
        "domain": domain,
        "jurisdiction": jurisdiction,
        "task_type": task_type
    }
)
```

### 4. Regular Readiness Checks

```python
# Check readiness weekly
from celery import Celery

@celery.task
def weekly_readiness_check():
    agents = db.query(AgentRegistry).filter(
        AgentRegistry.status != AgentStatus.AUTONOMOUS
    ).all()

    for agent in agents:
        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity=get_next_maturity(agent.status)
        )

        if result["ready"]:
            notify_admins(
                subject=f"Agent {agent.name} ready for promotion",
                body=f"Score: {result['score']}/100\n{result['recommendation']}"
            )
```

---

## Troubleshooting

### Problem: Agent Not Ready Despite Good Performance

**Symptoms**: High episode count, low interventions, but score < 70

**Possible Causes**:
1. Low constitutional score dragging down average
2. Interventions concentrated in recent episodes
3. Episodes not all at current maturity level

**Solution**:
```python
# Check each component separately
episode_score = min(episodes / min_episodes, 1.0) * 40
intervention_score = (1 - intervention_rate / max_intervention) * 30
constitutional_score = (avg_constitutional / min_constitutional) * 30

print(f"Episode Score: {episode_score}/40")
print(f"Intervention Score: {intervention_score}/30")
print(f"Constitutional Score: {constitutional_score}/30")

# Address the weakest component
```

### Problem: Interventions Not Tracking

**Symptoms**: `human_intervention_count` always 0 despite corrections

**Solution**:
```python
# Explicitly track interventions in agent code
if human_correction_made:
    episode.human_intervention_count += 1
    episode.human_edits.append({
        "timestamp": datetime.now().isoformat(),
        "field": corrected_field,
        "original": original_value,
        "correction": corrected_value,
        "reason": correction_reason
    })
```

---

## Next Steps

1. **Set up tracking**: Ensure all agent executions track interventions
2. **Create domain-specific episodes**: Organize episodes by domain/jurisdiction
3. **Validate constitutional compliance**: Run compliance checks after each episode
4. **Schedule readiness checks**: Automate weekly readiness assessments
5. **Generate audit trails**: Export reports for governance compliance

For more information:
- [Episodic Memory Implementation](EPISODIC_MEMORY_IMPLEMENTATION.md)
- [Quick Start Guide](EPISODIC_MEMORY_QUICK_START.md)
- [API Documentation](../api/episode_routes.py)
