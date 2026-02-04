# Agent Graduation Guide

**Last Updated**: February 4, 2026

Learn how agents progress through maturity levels using episodic memory and constitutional compliance validation.

---

## Overview

The Agent Graduation Framework ensures agents only gain autonomy after demonstrating:

1. **Sufficient Experience** - Minimum episode counts per level
2. **Low Intervention Rate** - Minimal human oversight needed
3. **Constitutional Compliance** - 100% adherence to governance rules

### Maturity Levels

```
┌─────────────┐      ┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│  STUDENT    │ ───▶ │   INTERN    │ ───▶ │  SUPERVISED  │ ───▶ │  AUTONOMOUS  │
│  (Learn)    │      │ (Proposals) │      │ (Monitoring) │      │   (Trust)    │
└─────────────┘      └─────────────┘      └──────────────┘      └──────────────┘
      │                     │                      │                      │
      ▼                     ▼                      ▼                      ▼
  Read-only         Streaming +         Form submissions    Full autonomy
  (charts,          Proposals           + state changes    + all actions
   markdown)        (approval req)
```

---

## Graduation Criteria

### Level-by-Level Requirements

#### STUDENT → INTERN

| Requirement | Threshold | Description |
|-------------|-----------|-------------|
| **Episode Count** | ≥ 10 | Minimum completed tasks |
| **Intervention Rate** | ≤ 50% | Human can still guide frequently |
| **Constitutional Score** | ≥ 0.70 | Learning governance basics |
| **Confidence Score** | ≥ 0.5 | Basic decision-making |

**Use Case**: Agent can handle simple tasks but needs approval for complex ones.

**Example**: 
- MedScribe agent completes 10 clinical documentation episodes
- 5/10 required human corrections (50% intervention rate)
- Constitutional compliance: 75% (still learning, but improving)
- ✅ **Ready for INTERN promotion**

---

#### INTERN → SUPERVISED

| Requirement | Threshold | Description |
|-------------|-----------|-------------|
| **Episode Count** | ≥ 25 | Substantial task experience |
| **Intervention Rate** | ≤ 20% | Mostly autonomous |
| **Constitutional Score** | ≥ 0.85 | Strong governance adherence |
| **Confidence Score** | ≥ 0.7 | Reliable decision-making |

**Use Case**: Agent can handle most tasks independently, monitored for edge cases.

**Example**:
- Customer support agent completes 25 support episodes
- 3/25 required human corrections (12% intervention rate)
- Constitutional compliance: 90% (strong rule-following)
- ✅ **Ready for SUPERVISED promotion**

---

#### SUPERVISED → AUTONOMOUS

| Requirement | Threshold | Description |
|-------------|-----------|-------------|
| **Episode Count** | ≥ 50 | Extensive task experience |
| **Intervention Rate** | 0% | Fully autonomous |
| **Constitutional Score** | ≥ 0.95 | Perfect governance adherence |
| **Confidence Score** | ≥ 0.9 | Highly reliable |

**Use Case**: Agent can be trusted with critical decisions without oversight.

**Example**:
- Brennan.ca pricing agent completes 50 pricing validation episodes
- 0/50 required human corrections (0% intervention rate)
- Constitutional compliance: 98% (near-perfect rule-following)
- ✅ **Ready for AUTONOMOUS promotion**

---

## Readiness Score Calculation

### Formula

```
readiness_score = (
    (episode_score * 0.40) +      # 40% weight on experience
    (intervention_score * 0.30) + # 30% weight on autonomy
    (constitutional_score * 0.30) # 30% weight on compliance
)
```

### Component Scores

#### Episode Score
```python
episode_score = min(1.0, actual_episodes / required_episodes)

# Examples:
# - 5 episodes for INTERN (10 required): 5/10 = 0.50
# - 10 episodes for INTERN (10 required): 10/10 = 1.00 ✅
# - 15 episodes for INTERN (10 required): 15/10 = 1.00 ✅ (capped at 1.0)
```

#### Intervention Score
```python
intervention_score = 1.0 - (intervention_rate / threshold)

# Examples for INTERN (50% threshold):
# - 30% intervention rate: 1.0 - (0.30 / 0.50) = 0.40
# - 50% intervention rate: 1.0 - (0.50 / 0.50) = 0.00 ❌
# - 20% intervention rate: 1.0 - (0.20 / 0.50) = 0.60 ✅

# Examples for SUPERVISED (20% threshold):
# - 10% intervention rate: 1.0 - (0.10 / 0.20) = 0.50
# - 20% intervention rate: 1.0 - (0.20 / 0.20) = 0.00 ❌
# - 5% intervention rate: 1.0 - (0.05 / 0.20) = 0.75 ✅
```

#### Constitutional Score
```python
constitutional_score = compliance_validation_score

# Calculated by validating last N episodes against Knowledge Graph rules:
# - Check for security violations
# - Check for compliance violations
# - Check for governance violations
# - Score = (clean_episodes / total_episodes)
```

### Example Calculation

```python
# Agent seeking INTERN promotion
actual_episodes = 12
required_episodes = 10
intervention_rate = 0.35  # 35%
constitutional_compliance = 0.82  # 82%

episode_score = min(1.0, 12 / 10) = 1.00
intervention_score = 1.0 - (0.35 / 0.50) = 0.30
constitutional_score = 0.82

readiness_score = (1.00 * 0.40) + (0.30 * 0.30) + (0.82 * 0.30)
                 = 0.40 + 0.09 + 0.246
                 = 0.636

# Result: 63.6% ready - NOT READY for promotion
# Gap: Need 36.4% more readiness
```

---

## Graduation Exam Process

### Step 1: Check Prerequisites

```python
from core.agent_graduation_service import AgentGraduationService

graduation = AgentGraduationService(db)

# Verify prerequisites
prerequisites = await graduation.check_graduation_prerequisites(
    agent_id="agent_123",
    target_level=AgentMaturityLevel.INTERN
)

if not prerequisites["met"]:
    print(f"Missing prerequisites: {prerequisites['missing']}")
    return
```

### Step 2: Calculate Readiness

```python
readiness = await graduation.calculate_readiness(
    agent_id="agent_123",
    target_level=AgentMaturityLevel.INTERN
)

print(f"Readiness Score: {readiness['readiness_score']}")
print(f"Episodes: {readiness['episode_count']}/{readiness['required_episodes']}")
print(f"Intervention Rate: {readiness['intervention_rate']*100:.1f}%")
print(f"Constitutional Score: {readiness['constitutional_score']:.2f}")

if readiness["readiness_score"] < 1.0:
    print(f"❌ Not ready. Gap: {(1.0 - readiness['readiness_score'])*100:.1f}%")
    return
```

### Step 3: Validate Constitutional Compliance

```python
compliance = await graduation.validate_constitutional_compliance(
    agent_id="agent_123",
    episode_window=100  # Check last 100 episodes
)

print(f"Compliance Score: {compliance['score']:.2f}")
print(f"Violations: {compliance['violation_count']}")
print(f"Clean Episodes: {compliance['clean_episodes']}/{compliance['total_episodes']}")

if compliance["score"] < 0.70:
    print("❌ Constitutional compliance too low")
    return
```

### Step 4: Run Graduation Exam

```python
exam_result = await graduation.run_graduation_exam(
    agent_id="agent_123",
    target_level=AgentMaturityLevel.INTERN,
    exam_config={
        "scenarios": [
            "customer_refund",
            "technical_issue",
            "escalation_handling"
        ],
        "strict_mode": True  # Fail on any violation
    }
)

print(f"Exam Passed: {exam_result['passed']}")
print(f"Score: {exam_result['score']:.2f}")
print(f"Scenarios Completed: {exam_result['scenarios_completed']}/{exam_result['scenarios_total']}")

if not exam_result["passed"]:
    print(f"❌ Exam failed: {exam_result['failure_reason']}")
    return
```

### Step 5: Promote Agent

```python
# All checks passed - promote agent
result = await graduation.promote_agent(
    agent_id="agent_123",
    target_level=AgentMaturityLevel.INTERN,
    metadata={
        "graduation_exam_id": exam_result["exam_id"],
        "promoted_by": "system",
        "reason": "Passed all graduation criteria"
    }
)

print(f"✅ Agent promoted to {result['new_level']}!")
print(f"Promotion ID: {result['promotion_id']}")
```

---

## Constitutional Compliance Validation

### What Gets Validated

1. **Security Violations**
   - Unauthorized data access
   - Bypassing security checks
   - Exceeding permission boundaries

2. **Compliance Violations**
   - Data privacy violations (GDPR, HIPAA)
   - Regulatory non-compliance
   - Audit trail gaps

3. **Governance Violations**
   - Maturity level violations (e.g., STUDENT performing AUTONOMOUS actions)
   - Missing required approvals
   - Trigger interception failures

### Validation Process

```python
# For each episode in the window:
for episode in recent_episodes:
    # 1. Check for security violations
    security_violations = validate_security(episode)
    
    # 2. Check for compliance violations
    compliance_violations = validate_compliance(episode)
    
    # 3. Check for governance violations
    governance_violations = validate_governance(episode)
    
    # 4. Calculate score
    if not any([security_violations, compliance_violations, governance_violations]):
        clean_episodes += 1

constitutional_score = clean_episodes / total_episodes
```

### Improving Constitutional Score

```python
# If score is too low, identify common violations
violations_by_type = await graduation.get_violation_breakdown(
    agent_id="agent_123"
)

print("Common Violations:")
for violation_type, count in violations_by_type.items():
    print(f"  {violation_type}: {count}")

# Focus training on most common violation types
```

---

## Tracking Progress

### Monitoring Agent Readiness

```python
async def print_agent_progress(agent_id: str):
    """Print detailed progress toward next level"""
    
    levels = [
        AgentMaturityLevel.INTERN,
        AgentMaturityLevel.SUPERVISED,
        AgentMaturityLevel.AUTONOMOUS
    ]
    
    for level in levels:
        readiness = await graduation.calculate_readiness(
            agent_id=agent_id,
            target_level=level
        )
        
        print(f"\n{'='*60}")
        print(f"Progress toward {level.value}")
        print(f"{'='*60}")
        print(f"Overall Readiness: {readiness['readiness_score']*100:.1f}%")
        
        print(f"\nComponents:")
        print(f"  Episodes: {readiness['episode_count']}/{readiness['required_episodes']}")
        print(f"    Score: {readiness['episode_score']:.2f}")
        print(f"  Intervention Rate: {readiness['intervention_rate']*100:.1f}%")
        print(f"    Score: {readiness['intervention_score']:.2f}")
        print(f"  Constitutional: {readiness['constitutional_score']:.2f}")
        print(f"    Score: {readiness['constitutional_score']:.2f}")
        
        if readiness["readiness_score"] >= 1.0:
            print(f"\n  ✅ READY FOR {level.value.upper()} GRADUATION!")
        else:
            gap = 1.0 - readiness["readiness_score"]
            print(f"\n  ⏳ Gap: {gap*100:.1f}%")
            
            # Show what needs improvement
            if readiness["episode_score"] < 1.0:
                needed = readiness["required_episodes"] - readiness["episode_count"]
                print(f"     Need {needed} more episodes")
            
            if readiness["intervention_score"] < 1.0:
                current = readiness["intervention_rate"] * 100
                target = 50 if level == AgentMaturityLevel.INTERN else 20
                print(f"     Reduce intervention rate from {current:.1f}% to ≤{target}%")
            
            if readiness["constitutional_score"] < 1.0:
                needed = 0.70 if level == AgentMaturityLevel.INTERN else 0.85
                current = readiness["constitutional_score"]
                print(f"     Improve constitutional score from {current:.2f} to ≥{needed:.2f}")
```

---

## Audit Trail

All graduation events are logged for audit purposes:

```python
# Get graduation audit trail
audit_trail = await graduation.get_graduation_audit_trail(
    agent_id="agent_123"
)

for event in audit_trail:
    print(f"{event['timestamp']}: {event['event_type']}")
    print(f"  Level: {event['from_level']} → {event['to_level']}")
    print(f"  Triggered by: {event['triggered_by']}")
    print(f"  Readiness Score: {event['readiness_score']}")
    print(f"  Constitutional Score: {event['constitutional_score']}")
```

---

## Best Practices

### 1. Gradual Autonomy

Don't rush agents through levels. Each level should have meaningful experience:

```python
# GOOD: Agent spends time at each level
STUDENT: 2-4 weeks (10-15 episodes)
INTERN: 4-8 weeks (25-35 episodes)
SUPERVISED: 8-16 weeks (50-75 episodes)

# BAD: Rushing through levels
STUDENT → INTERN: 2 days (3 episodes) ❌
INTERN → SUPERVISED: 1 week (8 episodes) ❌
```

### 2. Monitor Interventions

Track why interventions happen:

```python
# Get intervention breakdown
interventions = await graduation.get_intervention_breakdown(
    agent_id="agent_123",
    episode_window=50
)

# Common intervention reasons:
# - Uncertainty (confidence too low)
# - Rule violation (constitutional issue)
# - Complexity (task too hard)
# - Edge case (unseen scenario)

# Use this to focus training
```

### 3. Constitutional Compliance First

Never compromise on constitutional score:

```python
# Even if episode count and intervention rate are perfect:
readiness = {
    "episode_score": 1.0,        # ✅ Perfect
    "intervention_score": 1.0,   # ✅ Perfect
    "constitutional_score": 0.65 # ❌ Below 0.70 threshold
}

# Result: NOT READY
# Agent must improve constitutional compliance before graduating
```

### 4. Use Graduation Exams

Graduation exams validate readiness in realistic scenarios:

```python
# Define scenarios relevant to your use case
exam_scenarios = {
    "customer_support": [
        "refund_request",
        "angry_customer",
        "technical_issue",
        "escalation_handling"
    ],
    "medical_documentation": [
        "patient_history",
        "diagnosis_coding",
        "treatment_plan",
        "privacy_compliance"
    ],
    "pricing_validation": [
        "discount_approval",
        "competitor_pricing",
        "margin_validation",
        "contract_terms"
    ]
}
```

---

## API Endpoints

### Check Readiness
```http
GET /api/episodes/graduation/readiness/{agent_id}?target_level=INTERN
```

Response:
```json
{
  "agent_id": "agent_123",
  "current_level": "STUDENT",
  "target_level": "INTERN",
  "readiness_score": 0.85,
  "episode_count": 12,
  "required_episodes": 10,
  "episode_score": 1.0,
  "intervention_rate": 0.35,
  "intervention_score": 0.30,
  "constitutional_score": 0.82,
  "gaps": {
    "intervention_rate": "Reduce from 35% to ≤50%"
  }
}
```

### Run Graduation Exam
```http
POST /api/episodes/graduation/exam
Content-Type: application/json

{
  "agent_id": "agent_123",
  "target_level": "INTERN",
  "scenarios": ["customer_refund", "technical_issue"]
}
```

### Promote Agent
```http
POST /api/episodes/graduation/promote
Content-Type: application/json

{
  "agent_id": "agent_123",
  "target_level": "INTERN",
  "reason": "Passed all graduation criteria"
}
```

---

## Troubleshooting

### Issue: Agent not graduating despite meeting criteria

**Check**: Are all components ≥ required threshold?

```python
readiness = await graduation.calculate_readiness(agent_id, target_level)

# ALL must be true:
readiness["episode_score"] >= 1.0        # Enough episodes
readiness["intervention_score"] >= 1.0   # Low enough intervention rate
readiness["constitutional_score"] >= threshold  # Compliant enough
```

### Issue: Constitutional score not improving

**Solution**: Review violations and focus training

```python
violations = await graduation.get_violation_breakdown(agent_id)

# Target most common violation type in training scenarios
```

### Issue: Intervention rate too high

**Solution**: Identify intervention reasons

```python
interventions = await graduation.get_intervention_breakdown(agent_id)

# Is agent uncertain? → Improve confidence calibration
# Is agent violating rules? → Improve constitutional training
# Are tasks too complex? → Simplify or provide more examples
```

---

## Case Studies

### MedScribe: Clinical Documentation Agent

**Goal**: Achieve AUTONOMOUS level for hospital board certification

**Requirements**:
- 100 clinical episodes (higher than standard 50)
- 0% intervention rate (stricter than standard)
- 1.0 constitutional score (perfect HIPAA compliance)

**Timeline**:
- STUDENT: 4 weeks (15 episodes)
- INTERN: 8 weeks (35 episodes)
- SUPERVISED: 16 weeks (100 episodes)
- AUTONOMOUS: ✅ Certified by hospital board

**Key Success Factors**:
- Extensive training on edge cases
- Rigorous HIPAA compliance validation
- Perfect documentation accuracy required

---

### Brennan.ca: Pricing Validation Agent

**Goal**: Automate pricing approval for Woodstock region

**Requirements**:
- 50 pricing validation episodes
- 0% intervention rate
- 0.95 constitutional score (strict financial controls)

**Timeline**:
- STUDENT: 2 weeks (12 episodes)
- INTERN: 6 weeks (30 episodes)
- SUPERVISED: 12 weeks (50 episodes)
- AUTONOMOUS: ✅ Fully automated pricing

**Key Success Factors**:
- Real-time market data integration
- Strict margin validation rules
- Comprehensive competitor pricing analysis

---

## Next Steps

1. **Read the episodic memory guide**: `EPISODIC_MEMORY_IMPLEMENTATION.md`
2. **Quick start**: `EPISODIC_MEMORY_QUICK_START.md`
3. **API documentation**: `API_STANDARDS.md`
4. **Run tests**: `pytest tests/test_agent_graduation.py -v`

---

**Authors**: Atom Development Team
**Version**: 1.0.0
**Status**: Production Ready ✅
