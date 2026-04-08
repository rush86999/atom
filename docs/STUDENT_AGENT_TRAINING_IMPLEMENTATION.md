# Student Agent Training System

**Component**: Agent Maturity & Training
**Files**: `backend/core/trigger_interceptor.py`, `backend/core/student_training_service.py`
**Status**: ✅ Production Ready

## Overview

The Student Agent Training System implements a four-tier maturity framework where agents progress from STUDENT to AUTONOMOUS through supervised learning and practical experience. This system ensures safe agent development by restricting capabilities based on demonstrated competence.

## Maturity Levels

| Level | Confidence | Automated Triggers | Capabilities |
|-------|-----------|-------------------|--------------|
| **STUDENT** | <0.5 | ❌ BLOCKED | Read-only (charts, markdown) |
| **INTERN** | 0.5-0.7 | ⚠️ Proposal Only | Streaming, form presentation |
| **SUPERVISED** | 0.7-0.9 | ✅ Supervised | Form submissions, state changes |
| **AUTONOMOUS** | >0.9 | ✅ Full | Full autonomy, all actions |

## Architecture

### Core Components

1. **Trigger Interceptor** (`backend/core/trigger_interceptor.py`)
   - Intercepts all agent trigger attempts
   - Routes based on maturity level
   - <5ms routing decisions via GovernanceCache

2. **Student Training Service** (`backend/core/student_training_service.py`)
   - Manages training proposals and sessions
   - AI-based training duration estimation
   - Tracks progress and graduation criteria

3. **Meta Agent Training Orchestrator** (`backend/core/meta_agent_training_orchestrator.py`)
   - Coordinates multi-agent training workflows
   - Manages training pipelines
   - Orchestrates graduation exams

## Trigger Interception

### Routing Logic

```python
from core.trigger_interceptor import TriggerInterceptor

interceptor = TriggerInterceptor()

# Intercept agent trigger attempt
result = interceptor.intercept_trigger(
    agent_id="student-agent-123",
    trigger_type="automated",
    action="submit_form"
)

# Returns:
# {
#     "allowed": False,
#     "reason": "STUDENT agents cannot execute automated triggers",
#     "routing": "training_required",
#     "suggested_action": "Route to training service"
# }
```

### Routing Decisions

| Agent Level | Trigger Type | Action | Decision |
|-------------|--------------|--------|----------|
| STUDENT | Automated | Any | ❌ Block → Training |
| STUDENT | Manual | Read-only | ✅ Allow |
| INTERN | Automated | State change | ⚠️ Proposal Required |
| INTERN | Manual | Any | ✅ Allow |
| SUPERVISED | Automated | Any | ✅ Supervised Execution |
| AUTONOMOUS | Automated | Any | ✅ Full Execution |

## Training Workflow

### 1. Training Request

When a STUDENT agent attempts a blocked action:

```python
from core.student_training_service import StudentTrainingService

training_service = StudentTrainingService()

# Create training request
request = training_service.create_training_request(
    agent_id="student-agent-123",
    requested_action="submit_form",
    current_maturity="STUDENT",
    target_maturity="INTERN"
)

# Returns:
# {
#     "request_id": "tr-456",
#     "estimated_duration": "2-3 hours",
#     "training_modules": ["form_safety", "data_validation"],
#     "graduation_criteria": {...}
# }
```

### 2. AI-Based Duration Estimation

The system uses historical data to estimate training duration:

```python
# Get training duration estimate
estimate = training_service.estimate_duration(
    agent_id="student-agent-123",
    target_maturity="INTERN",
    historical_data=True
)

# Returns:
# {
#     "estimated_hours": 2.5,
#     "confidence": 0.85,
#     "factors": {
#         "base_duration": 2.0,
#         "agent_learning_rate": 1.2,
#         "complexity_multiplier": 1.0
#     },
#     "similar_agents": {
#         "avg_duration": 2.3,
//         "min_duration": 1.8,
#         "max_duration": 3.2
#     }
# }
```

### 3. Training Session

```python
# Start training session
session = training_service.start_training_session(
    request_id="tr-456",
    modules=["form_safety", "data_validation"],
    supervised_by="human-trainer-1"
)

# Returns:
# {
#     "session_id": "ts-789",
#     "status": "in_progress",
#     "progress": 0.0,
#     "start_time": "2026-04-07T10:30:00Z"
# }
```

### 4. Progress Tracking

```python
# Update training progress
training_service.update_progress(
    session_id="ts-789",
    module="form_safety",
    progress=0.75,
    performance_score=0.92
)

# Check overall progress
status = training_service.get_session_status("ts-789")

# Returns:
# {
#     "session_id": "ts-789",
#     "status": "in_progress",
#     "overall_progress": 0.5,
#     "modules_completed": 1,
#     "modules_total": 2,
#     "avg_performance": 0.90
# }
```

## Graduation Criteria

### STUDENT → INTERN

| Criterion | Threshold | Description |
|-----------|-----------|-------------|
| Episodes | 10 minimum | Number of training episodes |
| Intervention Rate | <50% | Human assistance frequency |
| Constitutional Score | >0.70 | Safety/compliance score |
| Performance | >0.80 | Task success rate |

### INTERN → SUPERVISED

| Criterion | Threshold | Description |
|-----------|-----------|-------------|
| Episodes | 25 minimum | Cumulative episodes |
| Intervention Rate | <20% | Reduced human assistance |
| Constitutional Score | >0.85 | Higher compliance |
| Performance | >0.90 | Improved success rate |

### SUPERVISED → AUTONOMOUS

| Criterion | Threshold | Description |
|-----------|-----------|-------------|
| Episodes | 50 minimum | Extensive experience |
| Intervention Rate | 0% | No human assistance |
| Constitutional Score | >0.95 | Near-perfect compliance |
| Performance | >0.95 | Excellent success rate |

## Action Proposals (INTERN Agents)

INTERN agents must submit proposals for automated triggers:

```python
# Submit action proposal
proposal = training_service.submit_proposal(
    agent_id="intern-agent-456",
    proposed_action="submit_form",
    context={
        "form_data": {...},
        "validation": "passed",
        "safety_checks": "passed"
    },
    justification="Form validated, all safety checks passed"
)

# Returns:
# {
#     "proposal_id": "prop-101",
#     "status": "pending_approval",
#     "submitted_at": "2026-04-07T10:30:00Z",
#     "expires_at": "2026-04-07T11:30:00Z"
# }
```

### Human Approval

```python
# Approve proposal
training_service.approve_proposal(
    proposal_id="prop-101",
    approved_by="human-admin-1",
    comments="Approved - all checks passed"
)

# Or reject proposal
training_service.reject_proposal(
    proposal_id="prop-102",
    rejected_by="human-admin-1",
    reason="Insufficient justification"
)
```

## Supervision (SUPERVISED Agents)

SUPERVISED agents can execute triggers but under real-time monitoring:

```python
# Start supervision session
supervision = training_service.start_supervision(
    agent_id="supervised-agent-789",
    trigger_type="automated",
    supervisor="human-supervisor-1"
)

# Returns:
# {
#     "session_id": "sup-202",
#     "status": "monitoring",
#     "can_intervene": true,
#     "intervention_methods": ["pause", "correct", "terminate"]
# }
```

### Intervention Methods

```python
# Pause execution
training_service.intervene(
    session_id="sup-202",
    action="pause",
    reason="Reviewing approach"
)

# Correct execution
training_service.intervene(
    session_id="sup-202",
    action="correct",
    correction="Use different parameters"
)

# Terminate execution
training_service.intervene(
    session_id="sup-202",
    action="terminate",
    reason="Safety concern detected"
)
```

## Database Models

### BlockedTriggerContext
Tracks blocked trigger attempts for routing to training.

### AgentProposal
Stores action proposals from INTERN agents awaiting approval.

### SupervisionSession
Records supervision sessions with interventions.

### TrainingSession
Manages training progress and completion.

## API Endpoints

### Training Management

```bash
# Create training request
POST /api/v1/training/request
{
  "agent_id": "student-agent-123",
  "target_maturity": "INTERN"
}

# Start training session
POST /api/v1/training/session/start
{
  "request_id": "tr-456",
  "modules": ["form_safety", "data_validation"]
}

# Update progress
PATCH /api/v1/training/session/{session_id}/progress
{
  "module": "form_safety",
  "progress": 0.75,
  "performance_score": 0.92
}
```

### Proposal Management

```bash
# Submit proposal
POST /api/v1/proposals
{
  "agent_id": "intern-agent-456",
  "proposed_action": "submit_form",
  "context": {...}
}

# Approve proposal
POST /api/v1/proposals/{proposal_id}/approve
{
  "approved_by": "human-admin-1",
  "comments": "Approved"
}

# Reject proposal
POST /api/v1/proposals/{proposal_id}/reject
{
  "rejected_by": "human-admin-1",
  "reason": "Insufficient justification"
}
```

### Supervision

```bash
# Start supervision
POST /api/v1/supervision/start
{
  "agent_id": "supervised-agent-789",
  "supervisor": "human-supervisor-1"
}

# Intervene
POST /api/v1/supervision/{session_id}/intervene
{
  "action": "pause",
  "reason": "Reviewing approach"
}
```

## Performance

| Operation | Target | Actual |
|-----------|--------|--------|
| Trigger Interception | <5ms | ~3ms |
| Training Estimation | <500ms | ~400ms |
| Proposal Creation | <100ms | ~80ms |
| Supervision Start | <200ms | ~150ms |
| Intervention | <50ms | ~30ms |

## Testing

```bash
# Run trigger interceptor tests
pytest backend/tests/test_trigger_interceptor.py -v

# Run training service tests
pytest backend/tests/test_student_training_service.py -v

# Run supervision tests
pytest backend/tests/test_supervision_service.py -v
```

## Best Practices

1. **Training Design**
   - Break into focused modules
   - Include hands-on exercises
   - Provide clear success criteria

2. **Duration Estimation**
   - Use historical data
   - Consider agent learning rate
   - Build in buffer time

3. **Supervision**
   - Set clear intervention thresholds
   - Document all interventions
   - Use for learning opportunities

4. **Graduation**
   - Verify all criteria met
   - Conduct final exam
   - Celebrate milestones

## Troubleshooting

### Common Issues

1. **Training Stalls**
   - Check agent engagement
   - Verify module complexity
   - Adjust difficulty level

2. **High Intervention Rate**
   - Review training materials
   - Provide more practice
   - Adjust graduation criteria

3. **Proposal Rejections**
   - Improve justification quality
   - Provide more context
   - Learn from feedback

4. **Graduation Failures**
   - Ensure adequate preparation
   - Review weak areas
   - Provide additional training

## See Also

- **Trigger Interceptor**: `backend/core/trigger_interceptor.py`
- **Training Service**: `backend/core/student_training_service.py`
- **Agent Graduation**: `docs/AGENT_GRADUATION_GUIDE.md`
- **Episodic Memory**: `docs/EPISODIC_MEMORY_IMPLEMENTATION.md`
- **Governance**: `backend/core/agent_governance_service.py`
