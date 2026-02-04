# Recording Review & Governance Integration

## Overview

The Recording Review System integrates canvas recording playback and review with agent governance and learning, creating a continuous feedback loop that improves agent performance through automated analysis and confidence score updates.

**Status**: ✅ **COMPLETE**

**Date**: February 2, 2026

---

## Architecture

### Feedback Loop

```
Canvas Recording → Auto-Review → Confidence Update → World Model Learning
       ↓                ↓               ↓                    ↓
   Agent Action    Analyze      Agent Maturity      Improved Behavior
   Completed     Performance    Level Adjusted    From Patterns
```

### Components

1. **CanvasRecordingReview Model** - Database model linking recordings to governance outcomes
2. **RecordingReviewService** - Analyzes recordings and updates agent confidence
3. **Integration with AgentGovernanceService** - Confidence score updates
4. **Integration with WorldModel** - Learning from recordings
5. **Auto-Review System** - AI-powered automatic review of recordings
6. **Manual Review Workflow** - Human review interface

---

## Features

### 1. Automatic Recording Review

**Trigger**: When a recording stops (completed/failed)

**Analysis**:
- Event type distribution (errors, completions, interventions)
- Success rate calculation
- User intervention frequency
- Error pattern detection
- Autonomous operation detection

**Outcome**:
- Review status: approved, rejected, needs_changes
- Ratings: overall (1-5), performance (1-5), safety (1-5)
- Confidence delta: positive or negative impact on agent
- Training value: high, medium, low

### 2. Confidence Score Integration

**Positive Impact** (review_status = "approved"):
- Rating 4-5 stars: +0.05 confidence (high impact)
- Rating 1-3 stars: +0.02 confidence (low impact)
- Triggers agent promotion if confidence ≥ 0.9

**Negative Impact** (review_status = "rejected"):
- -0.10 confidence (high impact)
- Triggers agent demotion if confidence drops
- Marks as training opportunity

**Neutral Impact** (review_status = "needs_changes"):
- -0.03 confidence (minor penalty)
- Maintains current maturity level

### 3. Learning Integration

**World Model Updates**:
- Approved recordings with useful patterns → Positive experiences
- Failed recordings → Learning experiences with corrections
- Identified issues → Knowledge gaps to address
- Positive patterns → Reinforce successful behaviors

**Training Data**:
- Recordings marked with `training_value`
- Used for future agent improvements
- Linked to agent world model experiences

---

## Database Schema

### CanvasRecordingReview Model

```python
class CanvasRecordingReview(Base):
    """Recording review linking to governance and learning outcomes"""
    __tablename__ = "canvas_recording_reviews"

    # Core fields
    id = Column(String, primary_key=True)
    recording_id = Column(String, ForeignKey("canvas_recordings.recording_id"))
    agent_id = Column(String, ForeignKey("agent_registry.id"))
    user_id = Column(String, ForeignKey("users.id"))

    # Review outcomes
    review_status = Column(String)  # approved, rejected, needs_changes, pending
    overall_rating = Column(Integer)  # 1-5 stars
    performance_rating = Column(Integer)  # 1-5 stars
    safety_rating = Column(Integer)  # 1-5 stars

    # Feedback and learning
    feedback = Column(Text)
    identified_issues = Column(JSON)  # ["unsafe_action", "error_recovery"]
    positive_patterns = Column(JSON)  # ["efficient_workflow", "autonomous"]
    lessons_learned = Column(Text)

    # Governance impact
    confidence_delta = Column(Float)  # Change to agent confidence
    promoted = Column(Boolean)  # Contributed to promotion?
    demoted = Column(Boolean)  # Contributed to demotion?
    governance_notes = Column(Text)

    # Review metadata
    reviewed_by = Column(String, ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    auto_reviewed = Column(Boolean)  # True if AI-reviewed
    auto_review_confidence = Column(Float)  # AI's confidence in review

    # Learning integration
    used_for_training = Column(Boolean)
    training_value = Column(String)  # high, medium, low
    world_model_updated = Column(Boolean)
```

---

## API Endpoints

### Create Manual Review

```http
POST /api/canvas/recording/review
Content-Type: application/json

{
  "recording_id": "rec_123",
  "review_status": "approved",
  "overall_rating": 5,
  "performance_rating": 5,
  "safety_rating": 5,
  "feedback": "Excellent autonomous execution",
  "positive_patterns": ["error_free", "fast_execution", "no_intervention"],
  "lessons_learned": "Agent successfully completed complex workflow autonomously"
}
```

**Response**:
```json
{
  "review_id": "review_abc",
  "recording_id": "rec_123",
  "agent_id": "agent_456",
  "review_status": "approved",
  "confidence_delta": 0.05,
  "governance_notes": "Confidence increased by 0.050 (high impact)"
}
```

### Get Review

```http
GET /api/canvas/recording/review/{review_id}
```

**Response**:
```json
{
  "review_id": "review_abc",
  "recording_id": "rec_123",
  "agent_id": "agent_456",
  "review_status": "approved",
  "overall_rating": 5,
  "performance_rating": 5,
  "safety_rating": 5,
  "feedback": "Excellent autonomous execution",
  "identified_issues": [],
  "positive_patterns": ["error_free", "fast_execution"],
  "lessons_learned": "Agent successfully completed...",
  "confidence_delta": 0.05,
  "promoted": true,
  "demoted": false,
  "auto_reviewed": false,
  "training_value": "high"
}
```

### Get Agent Review Metrics

```http
GET /api/canvas/recording/review/agent/{agent_id}/metrics?days=30
```

**Response**:
```json
{
  "total_reviews": 25,
  "approval_rate": 0.88,
  "average_rating": 4.2,
  "confidence_impact": 0.35,
  "training_recordings": 18,
  "common_issues": ["api_timeout", "rate_limiting"],
  "strengths": ["autonomous_execution", "error_recovery", "fast_response"]
}
```

### Trigger Auto-Review

```http
POST /api/canvas/recording/review/recording/{recording_id}/auto-review
```

**Response**:
```json
{
  "success": true,
  "message": "Auto-review created",
  "review_id": "review_auto_xyz"
}
```

---

## Auto-Review System

### Analysis Algorithm

**Step 1: Event Analysis**
```python
# Count event types
events = recording.events
error_count = count_events(events, "error")
complete_count = count_events(events, "operation_complete")
intervention_count = count_events(events, "user_input")

# Calculate metrics
total_events = len(events)
success_rate = complete_count / max(total_events, 1)
error_rate = error_count / max(total_events, 1)
```

**Step 2: Pattern Detection**
```python
patterns = []
issues = []

if error_count == 0:
    patterns.append("error_free_execution")
    overall_rating += 1
else:
    issues.append(f"errors_occurred: {error_count} errors")
    overall_rating -= 1

if intervention_count == 0:
    patterns.append("fully_autonomous")
    safety_rating += 1
elif intervention_count > 2:
    issues.append(f"high_intervention: {intervention_count} interventions")
    safety_rating -= 1

if success_rate >= 0.8:
    patterns.append("high_success_rate")
    performance_rating += 1
```

**Step 3: Determine Status**
```python
if len(issues) == 0 and len(patterns) >= 2:
    review_status = "approved"
    overall_rating = min(5, overall_rating + 1)
elif len(issues) >= 3:
    review_status = "rejected"
    overall_rating = max(1, overall_rating - 1)
else:
    review_status = "needs_changes"
```

**Step 4: Calculate Confidence**
```python
confidence = 0.5  # Base

if patterns:
    confidence = min(0.95, confidence + 0.2 * len(patterns))
if issues:
    confidence = min(0.8, confidence + 0.1 * len(issues))

# Auto-review only if confidence >= threshold
if confidence >= AUTO_REVIEW_CONFIDENCE_THRESHOLD:
    create_review(review_status, overall_rating, confidence)
```

### Skipping Rules

Auto-review is skipped if:
1. Recording is `flagged_for_review` (requires human review)
2. Analysis confidence < threshold (default 0.7)
3. `AUTO_REVIEW_ENABLED` is false

---

## Integration with Governance

### Confidence Updates

When a review is created:

```python
# In RecordingReviewService._update_agent_confidence_from_review
confidence_delta = analysis["confidence_delta"]

if confidence_delta > 0:
    impact_level = "high" if confidence_delta >= 0.05 else "low"
    await governance.record_outcome(agent_id, success=True)
    review.promoted = confidence_delta >= 0.05
else:
    impact_level = "high" if confidence_delta <= -0.05 else "low"
    await governance.record_outcome(agent_id, success=False)
    review.demoted = confidence_delta <= -0.05

# Governance service updates agent confidence and maturity
# Agent can be promoted/demoted based on cumulative reviews
```

### Maturity Transitions

Based on confidence score changes:
- **≥ 0.9**: AUTONOMOUS (auto-recording enabled)
- **0.7 - 0.9**: SUPERVISED (requires approval)
- **0.5 - 0.7**: INTERN (learning mode)
- **< 0.5**: STUDENT (read-only)

### Audit Trail

All reviews create audit entries:
```python
CanvasAudit(
    component_type="recording_review",
    action=f"review_{review_status}",
    audit_metadata={
        "review_id": review.id,
        "recording_id": review.recording_id,
        "review_status": review.review_status,
        "confidence_delta": confidence_delta,
        "training_value": training_value,
        "auto_reviewed": review.auto_reviewed
    }
)
```

---

## Integration with Learning

### World Model Updates

Approved recordings with useful patterns:

```python
# In RecordingReviewService._update_world_model
experience = AgentExperience(
    agent_id=recording.agent_id,
    task_type=f"recording_review:{recording.reason}",
    input_summary=f"Recording {recording_id} - {len(events)} events",
    outcome="Success" if review.review_status == "approved" else "Failure",
    learnings=review.lessons_learned or review.feedback,
    timestamp=datetime.utcnow()
)

await world_model.record_experience(experience)
review.used_for_training = True
review.world_model_updated = True
```

### Learning Value Assessment

**High Training Value**:
- Approved with rating 4-5 (reinforce success)
- Rejected with multiple issues (learn from failure)
- Contains unique patterns

**Medium Training Value**:
- Needs_changes status
- Some issues identified

**Low Training Value**:
- Pending status
- No clear patterns
- Low confidence auto-review

---

## Configuration

### Environment Variables

```bash
# Enable/disable auto-review
AUTO_REVIEW_ENABLED=true  # Default: true

# Auto-review confidence threshold
AUTO_REVIEW_CONFIDENCE_THRESHOLD=0.7  # Default: 0.7

# Recording retention (affects training data availability)
RECORDING_RETENTION_DAYS=90  # Default: 90
```

---

## Usage Examples

### Example 1: Successful Autonomous Action

```python
# Agent completes task autonomously
recording_id = await recording_service.auto_record_autonomous_action(
    agent_id="agent_123",
    user_id="user_456",
    action="send_slack_message",
    context={"canvas_id": "canvas_789"}
)

# Record events
await recording_service.record_event(recording_id, "operation_start", {...})
await recording_service.record_event(recording_id, "operation_complete", {...})

# Stop recording → triggers auto-review
await recording_service.stop_recording(recording_id, status="completed")

# Auto-review analyzes:
# - No errors → error_free_execution pattern
# - No user intervention → fully_autonomous pattern
# - 100% success rate → high_success_rate pattern
# → review_status = "approved", rating = 5
# → confidence_delta = +0.05
# → Agent confidence: 0.85 → 0.90
# → Agent promoted to AUTONOMOUS
```

### Example 2: Failed Action with Errors

```python
# Agent action fails
await recording_service.record_event(recording_id, "error", {"error": "api_timeout"})
await recording_service.record_event(recording_id, "error", {"error": "connection_failed"})

# Auto-review analyzes:
# - 2 errors → errors_occurred issue
# - High error rate → performance penalty
# → review_status = "rejected", rating = 2
# → confidence_delta = -0.10
# → Agent confidence: 0.90 → 0.80
# → Agent demoted to SUPERVISED
```

### Example 3: Manual Review with Feedback

```python
# Human reviewer provides detailed feedback
review_id = await review_service.create_review(
    recording_id="rec_123",
    reviewer_id="reviewer_456",
    review_status="approved",
    overall_rating=4,
    feedback="Good execution but slow response time",
    positive_patterns=["error_free", "correct_result"],
    identified_issues=["slow_response"],
    lessons_learned="Optimize API calls for better performance"
)

# Confidence updated: +0.02 (moderate impact)
# World model updated with learning experience
# Future executions can learn from this pattern
```

---

## Monitoring & Metrics

### Agent Performance Dashboard

**Metrics by Agent**:
```python
{
  "agent_id": "agent_123",
  "period": "30 days",
  "total_recordings": 150,
  "total_reviews": 148,
  "auto_reviewed": 140,
  "manually_reviewed": 8,
  "approval_rate": 0.92,
  "average_rating": 4.3,
  "confidence_trend": "+0.15",
  "promotions": 1,
  "demotions": 0,
  "top_strengths": ["autonomous_execution", "error_recovery"],
  "common_issues": ["slow_response", "api_timeout"],
  "training_contributions": 25
}
```

### System Health Metrics

```python
{
  "auto_review_enabled": true,
  "auto_review_confidence_threshold": 0.7,
  "total_recordings": 1500,
  "total_reviews": 1450,
  "auto_review_rate": 0.93,
  "avg_confidence_score": 0.75,
  "pending_reviews": 15,
  "flagged_for_human_review": 35,
  "training_data_collected": 1200
}
```

---

## Testing

### Test Suite

**File**: `tests/test_recording_review.py`

**Test Coverage**:
- ✅ Create approved review
- ✅ Create rejected review
- ✅ Auto-review success
- ✅ Auto-review with errors
- ✅ Auto-review skip flagged
- ✅ Get review metrics
- ✅ Confidence impact on agent
- ✅ Health check

**Running Tests**:
```bash
pytest tests/test_recording_review.py -v
```

**Test Results**:
```
======================== 8 passed, 22 warnings in 0.49s ========================
```

---

## Database Migration

**Migration File**: `alembic/versions/b677f9cd6ac5_add_recording_review_model_for_.py`

**Applying Migration**:
```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

**Rollback**:
```bash
alembic downgrade -1
```

---

## Troubleshooting

### Common Issues

**Issue**: Auto-review not creating reviews

**Solutions**:
```python
# Check if auto-review is enabled
assert AUTO_REVIEW_ENABLED == True

# Check confidence threshold
assert AUTO_REVIEW_CONFIDENCE_THRESHOLD <= 0.7

# Check if recording is flagged
recording = db.query(CanvasRecording).filter_by(recording_id=id).first()
assert recording.flagged_for_review == False
```

**Issue**: Confidence not updating

**Solutions**:
```python
# Check if governance service is working
governance = AgentGovernanceService(db)
await governance.record_outcome(agent_id, success=True)

# Check agent confidence update
agent = db.query(AgentRegistry).filter_by(id=agent_id).first()
print(f"Confidence: {agent.confidence_score}")
```

**Issue**: World model not updating

**Solutions**:
```python
# Check review has useful patterns
review = db.query(CanvasRecordingReview).filter_by(id=review_id).first()
assert review.review_status == "approved"
assert len(review.positive_patterns) > 0
assert review.training_value in ["high", "medium"]
```

---

## Future Enhancements

### Planned Features

1. **ML-Based Analysis**: Use ML to identify complex patterns
2. **Comparative Analysis**: Compare recordings over time
3. **Anomaly Detection**: Flag unusual behavior patterns
4. **Review Queue**: Prioritize reviews by importance
5. **Bulk Review**: Review multiple recordings at once
6. **Review Templates**: Standardize review criteria
7. **Reviewer Assignment**: Auto-assign reviewers based on expertise
8. **Appeals Process**: Allow agents to appeal negative reviews

---

## References

### Related Documentation

- [Canvas Recording Implementation](./CANVAS_RECORDING_IMPLEMENTATION.md)
- [Agent Governance System](./AGENT_GOVERNANCE.md)
- [Agent Guidance System](./AGENT_GUIDANCE_IMPLEMENTATION.md)
- [Database Models](../backend/core/models.py)

### Related Code

- **Service**: `backend/core/recording_review_service.py`
- **API Routes**: `backend/api/recording_review_routes.py`
- **Database Model**: `backend/core/models.py` (CanvasRecordingReview)
- **Tests**: `backend/tests/test_recording_review.py`

---

## Changelog

### February 2, 2026 - Initial Implementation

**Added**:
- CanvasRecordingReview database model
- RecordingReviewService with auto-review and manual review
- Integration with AgentGovernanceService for confidence updates
- Integration with World Model for learning
- REST API endpoints (5 endpoints)
- Auto-review system with AI analysis
- Comprehensive test suite (8 tests, all passing)
- Database migration (b677f9cd6ac5)
- Complete documentation

**Status**: ✅ Complete and Production-Ready

---

## Support

For questions or issues:
1. Check test files for usage examples
2. Review API documentation in code
3. Consult governance team for policy questions
4. Check logs: `tail -f logs/atom.log | grep recording_review`

---

**Implementation Status**: ✅ **COMPLETE**

**Test Coverage**: ✅ **8/8 Tests Passing**

**Production Ready**: ✅ **Yes**
