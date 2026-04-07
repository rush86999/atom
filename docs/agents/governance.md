# Agent Governance System

**Last Updated**: February 6, 2026

---

## Overview

The Agent Governance System is a comprehensive framework that ensures all AI agent actions are attributable, governable, and auditable. It provides multi-tiered maturity levels, permission checks, and complete audit trails for compliance and security.

---

## Architecture

```
User Request → AgentContextResolver → GovernanceCache → AgentGovernanceService → Action Execution
                                                                         ↓
                                                                    Audit Logs
```

### Core Components

1. **AgentContextResolver** (`core/agent_context_resolver.py`)
   - Multi-layer fallback to determine which agent governs a request
   - Fallback chain: explicit agent_id → session agent → workspace default → system default

2. **AgentGovernanceService** (`core/agent_governance_service.py`)
   - Manages agent lifecycle and permissions
   - Performs maturity-based action validation
   - Handles approval workflows

3. **GovernanceCache** (`core/governance_cache.py`)
   - High-performance caching for governance checks
   - Sub-millisecond lookup times
   - 95%+ cache hit rate

---

## Agent Maturity Levels

| Level | Confidence | Automated Triggers | Capabilities |
|-------|-----------|-------------------|--------------|
| **STUDENT** | <0.5 | **BLOCKED** → Route to Training | Read-only (charts, markdown) |
| **INTERN** | 0.5-0.7 | **PROPOSAL ONLY** → Human Approval Required | Streaming, form presentation |
| **SUPERVISED** | 0.7-0.9 | **RUN UNDER SUPERVISION** → Real-time Monitoring | Form submissions, state changes |
| **AUTONOMOUS** | >0.9 | **FULL EXECUTION** → No Oversight | Full autonomy, all actions |

### Maturity Progression

```
STUDENT → (10 episodes, 50% intervention rate, 0.70 constitutional score) → INTERN
  ↓
INTERN → (25 episodes, 20% intervention rate, 0.85 constitutional score) → SUPERVISED
  ↓
SUPERVISED → (50 episodes, 0% intervention rate, 0.95 constitutional score) → AUTONOMOUS
```

---

## Action Complexity Levels

| Level | Examples | Required Maturity |
|-------|----------|-------------------|
| **1 (LOW)** | Presentations, read-only | STUDENT+ |
| **2 (MODERATE)** | Streaming, moderate actions | INTERN+ |
| **3 (HIGH)** | State changes, submissions | SUPERVISED+ |
| **4 (CRITICAL)** | Deletions, payments | AUTONOMOUS only |

---

## Governance Checks

### Checking Permissions

```python
from core.agent_governance_service import AgentGovernanceService
from core.database import SessionLocal

db = SessionLocal()
governance = AgentGovernanceService(db)

# Check if agent can perform action
check = governance.can_perform_action(
    agent_id="agent_123",
    action_type="social_media_post"
)

if check["allowed"]:
    # Proceed with action
    pass
else:
    # Handle denial
    if check.get("requires_human_approval"):
        # Request approval
        pass
```

### Response Format

```python
{
    "allowed": bool,           # Whether action is permitted
    "requires_human_approval": bool,  # Whether approval is needed
    "reason": str,             # Explanation for decision
    "agent_maturity": str,     # Current maturity level
    "action_complexity": int   # Complexity of action (1-4)
}
```

---

## Audit Trails

All state-changing operations create comprehensive audit entries:

### Social Media Audit

```python
from core.models import SocialMediaAudit

audit = SocialMediaAudit(
    user_id=str(user.id),
    agent_id=agent_id,
    agent_execution_id=execution_id,
    platform="twitter",
    action_type="post",
    content=post_content,
    success=True,
    agent_maturity="SUPERVISED",
    governance_check_passed=True
)
```

### Financial Audit

```python
from core.models import FinancialAudit

audit = FinancialAudit(
    user_id=str(user.id),
    agent_id=agent_id,
    account_id=account_id,
    action_type="update",
    changes={"balance": {"old": "100.00", "new": "200.00"}},
    success=True,
    agent_maturity="AUTONOMOUS",
    governance_check_passed=True
)
```

### Menu Bar Audit

```python
from core.models import MenuBarAudit

audit = MenuBarAudit(
    user_id=str(user.id),
    device_id=device_id,
    agent_id=agent_id,
    action="quick_chat",
    endpoint="/api/menubar/quick/chat",
    request_params={"message": "Hello"},
    success=True
)
```

---

## Agent Resolution

### AgentContextResolver

Resolves which agent should govern a request using fallback chain:

```python
from core.agent_context_resolver import AgentContextResolver

resolver = AgentContextResolver(db)

# Resolve agent for request
agent, context = await resolver.resolve_agent_for_request(
    user_id=str(user.id),
    requested_agent_id=agent_id,  # Optional explicit agent
    session_id=session_id,         # Optional session context
    action_type="chat"
)
```

### Resolution Path

```
1. Explicit agent_id (if provided)
   └─> Return agent or record "explicit_agent_id_not_found"

2. Session context agent
   └─> Return agent or record "no_session_agent"

3. System default "Chat Assistant"
   └─> Return agent or record "resolution_failed"
```

---

## Governance by Feature

### Social Media Posting

**Required Maturity**: SUPERVISED+

```python
# Agent must be SUPERVISED or AUTONOMOUS
governance_check = governance.can_perform_action(
    agent_id=agent.id,
    action_type="social_media_post"
)

# Creates SocialMediaAudit entry
# Tracks: platform, content, success, governance_check_passed
```

### Financial Operations

**Create/Update**: SUPERVISED+
**Delete**: AUTONOMOUS only

```python
# Update account (SUPERVISED+)
governance.can_perform_action(agent_id, "update_financial_account")

# Delete account (AUTONOMOUS only)
governance.can_perform_action(agent_id, "delete_financial_account")

# Creates FinancialAudit entry with old/new values
```

### Device Capabilities

**Camera/Location/Notifications**: INTERN+
**Screen Recording**: SUPERVISED+
**Command Execution**: AUTONOMOUS only

### Browser Automation

**Required Maturity**: INTERN+

```python
governance.can_perform_action(agent_id, "browser_automation")
```

### Canvas Operations

**Present**: STUDENT+
**Submit Form**: SUPERVISED+
**Execute Actions**: SUPERVISED+

---

## Performance

### Governance Cache

```python
from core.governance_cache import get_governance_cache

cache = get_governance_cache()

# Cached check (<1ms)
allowed = cache.is_allowed(agent_id, action_type)
```

**Metrics**:
- Cache hit rate: 95%+
- Average lookup time: <1ms
- P99 latency: 0.027ms
- Throughput: 616k ops/s

---

## Database Models

### AgentRegistry

```python
class AgentRegistry(Base):
    id: String
    name: String
    status: AgentStatus  # STUDENT, INTERN, SUPERVISED, AUTONOMOUS
    confidence_score: Float  # 0.0 to 1.0
    category: String
    configuration: JSON
```

### AgentExecution

```python
class AgentExecution(Base):
    id: String
    agent_id: String (FK → AgentRegistry)
    status: String  # running, completed, failed
    input_summary: Text
    output_summary: Text
    started_at: DateTime
    completed_at: DateTime
    
    # Relationships
    agent: AgentRegistry
    feedback: List[AgentFeedback]
    executions: List[AgentExecution]
```

### Audit Tables

**SocialMediaAudit**
- Tracks all social media operations
- Links to agent, execution, user
- Records platform, content, success

**FinancialAudit**
- Tracks all financial operations
- Links to agent, execution, user, account
- Records changes with old/new values

**MenuBarAudit**
- Tracks menu bar operations
- Links to agent, execution, user, device
- Records action, endpoint, request params

---

## Integration Examples

### Social Media Routes

```python
@router.post("/social/post")
async def create_social_post(
    request: SocialPostRequest,
    db: Session = Depends(get_db)
):
    # Resolve agent
    resolver = AgentContextResolver(db)
    agent, context = await resolver.resolve_agent_for_request(
        user_id=str(current_user.id),
        requested_agent_id=request.agent_id,
        action_type="social_media_post"
    )
    
    # Check governance
    governance = AgentGovernanceService(db)
    governance_check = governance.can_perform_action(
        agent_id=agent.id,
        action_type="social_media_post"
    )
    
    if not governance_check["allowed"]:
        # Create failed audit entry
        audit = SocialMediaAudit(
            user_id=str(current_user.id),
            agent_id=agent.id,
            platform="twitter",
            action_type="post",
            content=request.text,
            success=False,
            error_message="Governance check failed",
            agent_maturity=agent.status,
            governance_check_passed=False
        )
        db.add(audit)
        db.commit()
        
        raise router.permission_denied_error("social media", "post")
    
    # Proceed with posting
    # Create audit entry on completion
```

### Financial Routes

```python
@router.delete("/financial/accounts/{account_id}")
async def delete_financial_account(
    account_id: str,
    agent_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Resolve and validate agent
    if agent_id:
        resolver = AgentContextResolver(db)
        agent, _ = await resolver.resolve_agent_for_request(
            user_id=str(current_user.id),
            requested_agent_id=agent_id,
            action_type="delete_financial_account"
        )
        
        # AUTONOMOUS required for deletion
        governance = AgentGovernanceService(db)
        governance_check = governance.can_perform_action(
            agent_id=agent.id,
            action_type="delete_financial_account"
        )
        
        if not governance_check["allowed"]:
            raise router.permission_denied_error(
                "financial account",
                "delete",
                details={"reason": "AUTONOMOUS maturity required"}
            )
    
    # Delete account and create audit entry
    audit = FinancialAudit(
        user_id=str(current_user.id),
        agent_id=agent_id,
        account_id=account_id,
        action_type="delete",
        changes={"deleted": account_info},
        success=True,
        agent_maturity=agent.status
    )
    db.add(audit)
    db.commit()
```

---

## Monitoring & Compliance

### Audit Queries

```python
# Get all social media posts by an agent
audits = db.query(SocialMediaAudit).filter(
    SocialMediaAudit.agent_id == agent_id
).all()

# Get financial operations in date range
audits = db.query(FinancialAudit).filter(
    FinancialAudit.created_at >= start_date,
    FinancialAudit.created_at <= end_date
).all()

# Get failed governance checks
failed_audits = db.query(SocialMediaAudit).filter(
    SocialMediaAudit.governance_check_passed == False
).all()
```

### Compliance Reports

```python
# Agent activity summary
from sqlalchemy import func

summary = db.query(
    AgentRegistry.name,
    AgentRegistry.status,
    func.count(SocialMediaAudit.id).label('social_posts'),
    func.count(FinancialAudit.id).label('financial_ops')
).outerjoin(
    SocialMediaAudit,
    AgentRegistry.id == SocialMediaAudit.agent_id
).outerjoin(
    FinancialAudit,
    AgentRegistry.id == FinancialAudit.agent_id
).group_by(AgentRegistry.id).all()
```

---

## Testing

### Unit Tests

```python
# test_governance.py
def test_student_cannot_post_to_social_media():
    governance = AgentGovernanceService(db)
    student_agent = create_agent(status=AgentStatus.STUDENT)
    
    check = governance.can_perform_action(
        agent_id=student_agent.id,
        action_type="social_media_post"
    )
    
    assert check["allowed"] == False
    assert check["requires_human_approval"] == True

def test_autonomous_can_delete_financial_account():
    governance = AgentGovernanceService(db)
    autonomous_agent = create_agent(status=AgentStatus.AUTONOMOUS)
    
    check = governance.can_perform_action(
        agent_id=autonomous_agent.id,
        action_type="delete_financial_account"
    )
    
    assert check["allowed"] == True
```

### Integration Tests

```bash
# Test all governance endpoints
pytest tests/test_governance_streaming.py -v
pytest tests/test_governance_performance.py -v
pytest tests/test_social_media_governance.py -v
pytest tests/test_financial_governance.py -v
```

---

## Configuration

### Environment Variables

```bash
# Governance Settings
STREAMING_GOVERNANCE_ENABLED=true
CANVAS_GOVERNANCE_ENABLED=true
FORM_GOVERNANCE_ENABLED=true
BROWSER_GOVERNANCE_ENABLED=true

# Emergency Bypass (NEVER enable in production)
EMERGENCY_GOVERNANCE_BYPASS=false
```

### Feature Flags

```python
from core.feature_flags import FeatureFlags

# Check if governance is enforced for a feature
if FeatureFlags.should_enforce_governance('form'):
    # Perform governance check
    pass
```

---

## Best Practices

### 1. Always Resolve Agents

```python
# GOOD
resolver = AgentContextResolver(db)
agent, context = await resolver.resolve_agent_for_request(
    user_id=str(user.id),
    requested_agent_id=agent_id,
    action_type=action_type
)

# BAD - Skip agent resolution
agent = db.query(AgentRegistry).filter(
    AgentRegistry.id == agent_id
).first()
```

### 2. Always Create Audit Entries

```python
# GOOD
audit = SocialMediaAudit(
    user_id=str(user.id),
    agent_id=agent.id,
    platform=platform,
    action_type="post",
    content=content,
    success=result.get("success"),
    agent_maturity=agent.status,
    governance_check_passed=governance_check["allowed"]
)
db.add(audit)
db.commit()

# BAD - No audit trail
post_to_twitter(content)
```

### 3. Use Standard Error Handling

```python
# GOOD
if not governance_check["allowed"]:
    raise router.permission_denied_error(
        "social media",
        "post",
        details={"reason": governance_check["reason"]}
    )

# BAD
raise HTTPException(
    status_code=403,
    detail="Not allowed"
)
```

### 4. Check Appropriate Maturity Levels

```python
# Action complexity mapping
ACTION_COMPLEXITY = {
    "read": 1,           # STUDENT+
    "present": 1,        # STUDENT+
    "stream": 2,         # INTERN+
    "submit_form": 3,    # SUPERVISED+
    "delete": 4,         # AUTONOMOUS
    "payment": 4,        # AUTONOMOUS
}
```

---

## Troubleshooting

### Common Issues

**Issue**: Agent bypasses governance checks

**Solution**: Ensure `AgentContextResolver` is used to resolve agents, not direct database queries.

**Issue**: Audit entries not created

**Solution**: Verify audit model is imported and `db.commit()` is called after adding audit.

**Issue**: Cache returns stale data

**Solution**: Cache TTL is 5 minutes. Use `cache.clear()` if agent maturity changes.

### Debug Mode

```python
import logging
logging.getLogger("core.agent_governance_service").setLevel(logging.DEBUG)
logging.getLogger("core.agent_context_resolver").setLevel(logging.DEBUG)
```

---

## References

- **Agent Training**: `docs/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md`
- **Episodic Memory**: `docs/EPISODIC_MEMORY_IMPLEMENTATION.md`
- **Graduation Framework**: `docs/AGENT_GRADUATION_GUIDE.md`
- **Implementation**: `backend/core/agent_governance_service.py`
- **Tests**: `tests/test_governance_*.py`

---

## Summary

The Agent Governance System provides:

✅ **Attribution**: Every action tracked to specific agent and user
✅ **Control**: Maturity-based permissions prevent unauthorized actions  
✅ **Audit**: Complete audit trail for compliance and debugging
✅ **Performance**: Sub-millisecond governance checks via caching
✅ **Flexibility**: Configurable maturity levels and action complexity

**Key Principle**: All AI actions must be attributable, governable, and auditable.

