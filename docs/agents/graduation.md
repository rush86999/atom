# Agent Graduation Guide

> **Removed (2026-08-20):** the bespoke three-layer policy engine
> (`core/governance/` — `policy_engine.py`, `dynamic_governance.py`,
> `governance_service.py`) has been deleted. It was never wired into the live
> dispatch path (live governance is `core/agent_governance_service.py`,
> `core/governance_engine.py`, and the Gatekeeper middleware). Code samples
> below referencing it are historical. For external policy-as-code, integrate
> an OPA sidecar (roadmap).


## Overview

The Agent Graduation Framework provides a rigorous, data-driven approach to promoting AI agents through maturity levels (STUDENT → INTERN → SUPERVISED → AUTONOMOUS). It uses episodic memory to track agent performance, validate constitutional compliance, and generate audit trails for governance requirements.

## Table of Contents

- [Why Graduation Matters](#why-graduation-matters)
- [Two Types of Graduation](#two-types-of-graduation) ⚡ **IMPORTANT**
- [Graduation Criteria](#graduation-criteria)
- [How Graduation is Triggered](#how-graduation-is-triggered)
- [Readiness Score Calculation](#readiness-score-calculation)
- [Constitutional Compliance](#constitutional-compliance)
- [Use Cases](#use-cases)
- [Graduation Workflow](#graduation-workflow)
- [Edge Case Testing](#edge-case-testing)
- [Audit Trail Generation](#audit-trail-generation)

---

## Two Types of Graduation ⚡ IMPORTANT

Atom has **two distinct graduation systems** that work together:

### 1. Agent Graduation (This Guide)
**What**: Overall agent maturity level
**Progression**: STUDENT → INTERN → SUPERVISED → AUTONOMOUS
**Based on**: Episodes, intervention rates, constitutional compliance
**Scope**: Agent-wide (affects all capabilities)

### 2. Capability Graduation ⚡
**What**: Individual skill/capability maturity
**Progression**: 5 → 20 → 50 successful uses
**Based on**: Usage count per capability
**Scope**: Per-capability (skills graduate independently)

**Example**:
- An agent can be **INTERN** overall (agent graduation)
- But have **AUTONOMOUS** level for "data_query" capability (capability graduation)
- While still being **STUDENT** for "shell_access" capability

**See**: Capability Graduation Logic for the 5/20/50 rule.

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

### 4. Multi-Dimensional Learning

Graduation tracking includes:
- **Episodic Memory**: Agent interactions and past experiences
- **Community Skills**: Skill usage diversity and learning velocity
- **Canvas Presentations**: Context-aware decision making
- **User Feedback**: Performance ratings and corrections

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

## How Graduation is Triggered

Graduation is an autonomous, event-driven process that monitors agent performance across two distinct paths:

### 1. Event-Driven Trigger (Post-Task)
Immediately following every execution of the `GenericAgent`, the system invokes the `GraduationService`. 
- **Mechanism**: The `_record_execution` hook captures the task outcome.
- **Context**: Passing the `agent_id` and the `skill_id` (e.g., "tax_calculation") to the evaluation engine.
- **Immediate Action**: If the local streak threshold is met, the skill is promoted to `AUTONOMOUS` instantly.

### 2. Autonomous Review Trigger (Background Audit)
The `BackgroundAgentRunner` performs system-wide audits independently of user interaction.
- **Mechanism**: Periodic scheduled jobs (e.g., every 5 minutes).
- **Context**: Scans the `AgentRegistry` for skills in the `SUPERVISED` or `INTERN` tiers.
- **Action**: Aggregates episodic data across all sessions for a comprehensive readiness review.

---

## Skill Promotion Logic

**Note**: This section describes skill promotion within the agent graduation framework. For per-capability graduation based on usage count (5/20/50 rule), see Capability Graduation Logic.

Promotion to `AUTONOMOUS` state is governed by the **Dynamic Streak Rule**:

| Complexity | Required Consecutive Clean Runs |
|------------|--------------------------------|
| **Simple**   | 3                              |
| **Moderate** | 5                              |
| **Complex**  | 8                              |
| **Advanced** | 8                              |

**A "Clean Run" is defined as:**
1.  **Success**: `True` (Task completed objective).
2.  **Human Interventions**: `0` (Zero manual corrections).
3.  **Constitutional Score**: `≥ 0.95` (Full domain compliance).

## Readiness Score Calculation

### ⚡ MATURITY-ADJUSTED FORMULA (Current Implementation)

The readiness score uses **per-target-level weights**, and each agent is
scored only on the factors its maturity tier can actually evidence. Factors
whose weight is nonzero but which have **no recorded evidence** for the
agent (e.g. constitutional scores for chat-segmented episodes, supervision
when no proposal-linked episodes exist) are **excluded and the remaining
weights renormalized**:

```
readiness = Σ(value_i × weight_i) / Σ(weight_i)   over factors with
                                                  weight > 0 AND recorded evidence
```

**Per-level base weights** (source: `core/episode_service.py::ReadinessWeights`):

| Factor | student → intern | intern → supervised | supervised → autonomous |
|--------|-----------------:|--------------------:|------------------------:|
| Zero Intervention Ratio | 35% | 25% | 30% |
| Average Constitutional Score | 25% | 20% | 25% |
| Average Confidence Score | 20% | 15% | 15% |
| Success Rate | 20% | 25% | 20% |
| Supervision Success Rate | — | 15% | 10% |
| Skill Diversity Score | — | — | — |
| Proposal Quality Score | — | — | — |

**Why the weights differ per maturity (practical basis)**:

- **Students cannot create proposals** (hard block in `ProposalService`) —
  supervision evidence is structurally unreachable at the student tier, so
  it carries no weight there.
- **Interns route every action through a proposal** whose decision episode
  records `human_intervention_count = 1` by design, capping
  zero-intervention near 0.5 — so it carries a reduced weight, and
  supervision (approval rate) is live instead.
- **Skill diversity and proposal quality carry 0% at every tier**: no
  episode writer currently stamps `skill_type="openclaw"` or
  `episode_type="meta_agent_proposal"` metadata. Enabling one in promotion
  scoring is a deliberate weight change in `ReadinessWeights`, not a side
  effect of adding a writer.
- **Supervision success rate** blends approval rate (60%) and
  execution-followed rate (40%) only when follow-through was recorded;
  with no follow-through telemetry it equals the approval rate alone.

**Example Calculation**:

**Scenario**: Chat-trained student seeking promotion to INTERN — 12
episodes, all successful with zero interventions, episode confidence 0.5,
no constitutional scores recorded (chat segmentation does not record one),
no proposals:

```
Applied factors (constitutional excluded — nothing recorded):
  Zero Intervention: 1.00 × 0.35 = 0.350
  Confidence:        0.50 × 0.20 = 0.100
  Success:           1.00 × 0.20 = 0.200
Renormalize over applied weight 0.75:
  readiness = 0.650 / 0.75 = 0.867  ≥ 0.70 threshold → READY
```

Previously the unrecorded constitutional score averaged in as 0.0 and the
formula included structurally-zero factors, so this same agent scored
0.475 and could never cross the threshold — perfect runs included.

### Key Changes from Previous Formula

| Old Formula | Maturity-Adjusted Formula | Change |
|-------------|---------------------------|--------|
| One 6/7-component formula for all tiers | Per-tier weight tables | Each tier scored on evidence it can produce |
| Unrecorded scores averaged in as 0.0 | Unrecorded factors excluded + renormalized | Missing telemetry ≠ zero score |
| Skill diversity 10% (later 7%) + proposal quality 3% | Both 0% (no telemetry writers) | Dead factors no longer cap scores below thresholds |
| Supervision capped at 0.6 (dead follow-through column) | Approval-rate fallback when unrecorded | Supervision credit usable at intern tier |

### Skill Diversity (currently weight 0%)

`skill_diversity_score = min(unique_skills_used / 10, 1.0)` — variety of
skills successfully executed. No writer currently stamps the required
episode metadata, so the factor is disabled (0%) until one does; it
re-enters scoring only by giving it a weight in `ReadinessWeights`.

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
1. Low constitutional score dragging down average (or constitutional not recorded → factor excluded, check breakdown)
2. Low confidence score from recent self-assessments
3. Poor success rate despite low interventions
4. Low supervision success rate (intern/supervised tiers — approval-driven)
5. Below the minimum episode count for the target level (10/25/50)

**Solution**:
```python
# Check each component separately (weights are per target level — see
# ReadinessWeights; the example below uses the student→intern table)
weights = {"zero_intervention": 35, "constitutional": 25, "confidence": 20, "success": 20}

zero_intervention = zero_interventions / total_episodes
constitutional = avg_constitutional_score       # None/absent → factor excluded
confidence = avg(episode.confidence_score)      # None/absent → factor excluded
success = successful_tasks / total_tasks

print(f"Zero Intervention ({weights['zero_intervention']}%): {zero_intervention:.2f}")
print(f"Constitutional ({weights['constitutional']}%): {constitutional if constitutional is not None else 'NOT RECORDED → excluded'}")
print(f"Confidence ({weights['confidence']}%): {confidence if confidence is not None else 'NOT RECORDED → excluded'}")
print(f"Success Rate ({weights['success']}%): {success:.2f}")

# Unrecorded factors are dropped and the rest renormalized — the readiness
# breakdown from EpisodeService.get_graduation_readiness() reports exactly
# which weights were applied and which factors were excluded.
print(f"\nBreakdown: {readiness.breakdown['weights']}")

# Address the weakest applied component
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

## Enhanced Governance Integration (2026) ✨

> **Status:** implemented and wired (reintroduced 2026-08-30). The original
> general-purpose version was removed 2026-08-20 because it was never wired
> into any live path; this version is scoped to graduation decisions and
> enforced in `GraduationExamService.execute_graduation_exam` (Stage 5.5)
> and `AgentGraduationService.promote_agent` — see
> `tests/test_governance_graduation_integration.py`.

### Three-Layer Governance

Graduation decisions route through **three governance layers**
(`core/governance/dynamic_governance.py`):

| Layer | Graduation Role | Decision Type | Wired at |
|-------|----------------|---------------|----------|
| **OPERATIONAL** | student → intern checks | Automated | Exam Stage 5.5 |
| **TACTICAL** | intern → supervised with policy review | Adaptive (policy floors) | Exam Stage 5.5 |
| **STRATEGIC** | supervised → autonomous | **Human-in-the-loop** | Exam Stage 5.5 + promote gate |

**STRATEGIC semantics:** when a supervised agent passes every exam gate
for AUTONOMOUS, the exam records `passed=True` but **withholds the
promotion** (`promoted=False`, `awaiting_human_approval=True`). A
supervisor then completes it via `POST /api/episodes/graduation/promote`,
which re-evaluates the same policy against live evidence. Agents can no
longer auto-promote to AUTONOMOUS.

**Usage:**
```python
from core.governance import DynamicGovernanceManager, GovernanceLayer

manager = DynamicGovernanceManager()

# OPERATIONAL layer - standard graduation checks (automated allow)
decision = manager.decide(
    agent_id="agent_123",
    action="graduate_to_intern",
    layer=GovernanceLayer.OPERATIONAL,
    context={"episode_count": 12, "readiness_score": 0.75, ...},
)
assert decision.allowed and not decision.requires_human

# STRATEGIC layer - policies pass AND human approval required
decision = manager.decide(
    agent_id="agent_123",
    action="graduate_to_autonomous",
    layer=GovernanceLayer.STRATEGIC,
    context={"episode_count": 60, "readiness_score": 0.96, ...},
)
assert decision.allowed and decision.requires_human
```

### Policy-Based Graduation

Graduation criteria are enforced by the policy engine
(`core/governance/policy_engine.py`). **Default policies are derived from
`ReadinessThresholds` and the per-level minimum episode counts** (10 / 25 /
50), so the policy layer cannot drift from the exam's own gates. A rule
whose evidence is missing counts as violated.

```python
from core.governance.policy_engine import PolicyEngine, GovernancePolicy, PolicyPriority

engine = PolicyEngine()  # seeds the default graduation policies

# Custom policies can extend the defaults
policy = GovernancePolicy(
    policy_id="graduation_policy",
    priority=PolicyPriority.HIGH,
    condition="action == 'graduate_to_autonomous'",
    effect="DENY",
    layer="strategic",
    rules={
        "min_episodes": 50,
        "max_intervention_rate": 0.0,
        "min_constitutional_score": 0.95
    }
)

engine.register_policy(policy)

# Evaluate graduation request
result = engine.evaluate(
    agent_id="agent_123",
    action="graduate_to_autonomous",
    layer="strategic",
    context={
        "episode_count": 48,
        "intervention_rate": 0.02,
        "constitutional_score": 0.92
    }
)
# Result: DENIED (episodes < 50, intervention > 0%, score < 0.95)
```

Rule → context-key mapping: `min_episodes` → `episode_count`,
`max_intervention_rate` → `intervention_rate`; the rest match by name
(`readiness_score`, `success_rate`, `constitutional_score`,
`confidence_score`).

See [Agent Governance](governance.md) for the full governance
architecture, and
`backend/tests/test_governance_graduation_integration.py` for the
enforcement contract in executable form.

---

## Next Steps

1. **Set up tracking**: Ensure all agent executions track interventions
2. **Create domain-specific episodes**: Organize episodes by domain/jurisdiction
3. **Validate constitutional compliance**: Run compliance checks after each episode
4. **Schedule readiness checks**: Automate weekly readiness assessments
5. **Generate audit trails**: Export reports for governance compliance

For more information:
- [Episodic Memory Implementation](../intelligence/episodic-memory.md)
- Quick Start Guide
- [API Documentation](../api/episode_routes.py)

---

## Related Documentation

### Agent Learning & Intelligence
- **[Self-Evolution & Reflection Pool](../intelligence/self-evolution.md)** - Critique-based learning, Memento-Skills, and AlphaEvolver for autonomous agent improvement
- **[Episodic Memory](../intelligence/episodic-memory.md)** - Episode tracking and retrieval system for agent learning
- **[GraphRAG & Entity Types](../intelligence/graphrag.md)** - Knowledge graph and entity extraction
- **[World Model & JIT Facts](../intelligence/world-model-guide.md)** - Knowledge management and real-time fact verification

### Agent Systems
- **[Agent Governance](governance.md)** - Maturity levels and permissions system
- **[Student Training](training.md)** - Maturity routing and training proposals
- **Queen Agent** - Structured workflow automation
- **[Fleet Admiral](fleet-admiral.md)** - Dynamic agent recruitment for unstructured tasks

### Integration Guides
- **Auto-Dev User Guide** - Self-evolving agent capabilities (Memento-Skills, AlphaEvolver)
- **[Memory Integration Guide](../intelligence/memory-integration.md)** - Complete memory system integration
