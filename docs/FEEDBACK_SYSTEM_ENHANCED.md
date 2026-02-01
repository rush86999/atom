# Enhanced Feedback System - Implementation Guide

## Overview

Atom's enhanced feedback system enables users to provide quick and detailed feedback on agent actions, which is then used to improve agent performance through confidence adjustments and learning signals.

**Security**: All feedback is attributed to users and linked to specific agent executions for full auditability.

---

## Features

### 1. Quick Feedback (Thumbs Up/Down)
Users can quickly provide positive or negative feedback with a single click.

### 2. Star Ratings (1-5 Stars)
Users can rate agent performance on a 5-star scale for more nuanced feedback.

### 3. Detailed Corrections
Users can provide specific corrections when an agent makes mistakes.

### 4. Feedback Types
- **rating** - Star rating provided
- **correction** - User correction provided
- **approval** - Thumbs up without correction
- **comment** - Text feedback without rating

### 5. Feedback Analytics
Comprehensive analytics dashboard showing:
- Total feedback count
- Positive/negative ratios
- Average ratings
- Top performing agents
- Most corrected agents
- Feedback trends over time

### 6. Confidence Adjustments
Feedback automatically adjusts agent confidence scores:
- Thumbs up: +0.05
- Thumbs down: -0.05
- 5-star rating: +0.10
- 4-star rating: +0.05
- 3-star rating: 0.00
- 2-star rating: -0.05
- 1-star rating: -0.10
- Correction: -0.03

### 7. Learning Signals
Agents receive learning signals based on feedback patterns to identify strengths and weaknesses.

---

## Database Schema

### Enhanced AgentFeedback Model

```sql
ALTER TABLE agent_feedback ADD COLUMN thumbs_up_down BOOLEAN;
ALTER TABLE agent_feedback ADD COLUMN agent_execution_id VARCHAR;
ALTER TABLE agent_feedback ADD COLUMN rating INTEGER;
ALTER TABLE agent_feedback ADD COLUMN feedback_type VARCHAR;

CREATE INDEX ix_agent_feedback_agent_execution_id ON agent_feedback(agent_execution_id);
CREATE INDEX ix_agent_feedback_rating ON agent_feedback(rating);
CREATE INDEX ix_agent_feedback_feedback_type ON agent_feedback(feedback_type);
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Primary key |
| `agent_id` | String | Foreign key to agent_registry |
| `agent_execution_id` | String (nullable) | Foreign key to agent_executions |
| `user_id` | String | Foreign key to users |
| `input_context` | Text (nullable) | What triggered the agent |
| `original_output` | Text | Agent's original output |
| `user_correction` | Text | User's correction or comment |
| `feedback_type` | String (nullable) | correction, rating, approval, comment |
| `thumbs_up_down` | Boolean (nullable) | Thumbs up (True) or down (False) |
| `rating` | Integer (nullable) | Star rating (1-5) |
| `status` | String | Adjudication status |
| `ai_reasoning` | Text (nullable) | AI judge's explanation |
| `created_at` | DateTime | When feedback was created |
| `adjudicated_at` | DateTime (nullable) | When feedback was adjudicated |

---

## REST API Endpoints

### 1. Submit Enhanced Feedback

```http
POST /api/feedback/submit
Content-Type: application/json

{
  "agent_id": "agent-1",
  "agent_execution_id": "exec-123",
  "user_id": "user-1",
  "thumbs_up_down": true,
  "rating": 5,
  "user_correction": "Great job!",
  "input_context": "What is 2+2?",
  "original_output": "2+2=4",
  "feedback_type": "approval"
}
```

**Response**:
```json
{
  "success": true,
  "feedback_id": "feedback-123",
  "agent_id": "agent-1",
  "feedback_type": "approval",
  "message": "Feedback submitted successfully"
}
```

### 2. Get Agent Feedback Summary

```http
GET /api/feedback/agent/agent-1?days=30
```

**Response**:
```json
{
  "agent_id": "agent-1",
  "agent_name": "Sales Assistant",
  "total_feedback": 50,
  "positive_count": 40,
  "negative_count": 5,
  "thumbs_up_count": 35,
  "thumbs_down_count": 5,
  "average_rating": 4.5,
  "rating_distribution": {
    "1": 1,
    "2": 2,
    "3": 5,
    "4": 12,
    "5": 30
  },
  "feedback_types": {
    "rating": 35,
    "correction": 5,
    "approval": 8,
    "comment": 2
  }
}
```

### 3. Get Overall Analytics

```http
GET /api/feedback/analytics?days=30&limit=10
```

**Response**:
```json
{
  "period_days": 30,
  "summary": {
    "total_feedback": 250,
    "total_agents_with_feedback": 12,
    "overall_positive_ratio": 0.8,
    "overall_average_rating": 4.2,
    "feedback_by_type": {
      "rating": 150,
      "correction": 40,
      "approval": 45,
      "comment": 15
    }
  },
  "top_performing_agents": [
    {
      "agent_id": "agent-1",
      "agent_name": "Sales Assistant",
      "positive_count": 45,
      "total_count": 50,
      "positive_ratio": 0.9
    }
  ],
  "most_corrected_agents": [
    {
      "agent_id": "agent-5",
      "agent_name": "Data Analyst",
      "correction_count": 15
    }
  ],
  "trends": [
    {
      "date": "2026-01-15",
      "total": 10,
      "positive": 8,
      "negative": 2,
      "average_rating": 4.5
    }
  ]
}

### 4. Get Feedback Trends

```http
GET /api/feedback/trends?days=30
```

**Response**:
```json
{
  "period_days": 30,
  "trends": [
    {
      "date": "2026-01-15",
      "total": 10,
      "positive": 8,
      "negative": 2,
      "average_rating": 4.5
    },
    {
      "date": "2026-01-16",
      "total": 12,
      "positive": 10,
      "negative": 2,
      "average_rating": 4.6
    }
  ]
}
```

---

## Python API Usage

### Submitting Feedback

```python
from core.models import AgentFeedback
from core.database import SessionLocal

db = SessionLocal()

# Thumbs up feedback
feedback = AgentFeedback(
    agent_id="agent-1",
    agent_execution_id="exec-123",
    user_id="user-1",
    original_output="Agent response",
    user_correction="",
    thumbs_up_down=True,
    feedback_type="approval"
)

db.add(feedback)
db.commit()
```

### Getting Feedback Summary

```python
from core.feedback_analytics import FeedbackAnalytics
from core.database import SessionLocal

db = SessionLocal()
analytics = FeedbackAnalytics(db)

# Get agent feedback summary
summary = analytics.get_agent_feedback_summary(
    agent_id="agent-1",
    days=30
)

print(summary["positive_ratio"])  # 0.8
print(summary["average_rating"])  # 4.5
```

### Adjusting Confidence

```python
from core.agent_learning_enhanced import AgentLearningEnhanced
from core.database import SessionLocal

db = SessionLocal()
learning = AgentLearningEnhanced(db)

# Adjust confidence based on feedback
new_confidence = learning.adjust_confidence_with_feedback(
    agent_id="agent-1",
    feedback=feedback_obj,
    current_confidence=0.7
)

print(new_confidence)  # 0.75 (increased due to thumbs up)
```

### Getting Learning Signals

```python
from core.agent_learning_enhanced import AgentLearningEnhanced
from core.database import SessionLocal

db = SessionLocal()
learning = AgentLearningEnhanced(db)

# Get learning signals
signals = learning.get_learning_signals(
    agent_id="agent-1",
    days=30
)

print(signals["learning_signals"])
# [
#   {
#     "type": "strength",
#     "message": "Agent is performing well with high positive feedback",
#     "confidence_impact": "positive"
#   }
# ]

print(signals["improvement_suggestions"])
# [
#   {
#     "type": "training",
#     "message": "Review common correction patterns",
#     "priority": "high"
#   }
# ]
```

### Batch Confidence Update

```python
from core.agent_learning_enhanced import AgentLearningEnhanced
from core.database import SessionLocal

db = SessionLocal()
learning = AgentLearningEnhanced(db)

# Batch update confidence from all recent feedback
new_confidence = learning.batch_update_confidence_from_feedback(
    agent_id="agent-1",
    days=30
)

print(new_confidence)  # Updated confidence score
```

---

## Confidence Adjustment Algorithm

### Individual Feedback Weights

| Feedback Type | Weight |
|--------------|--------|
| Thumbs up | +0.05 |
| Thumbs down | -0.05 |
| 5-star rating | +0.10 |
| 4-star rating | +0.05 |
| 3-star rating | 0.00 |
| 2-star rating | -0.05 |
| 1-star rating | -0.10 |
| Correction | -0.03 |

### Example Calculation

```
Initial Confidence: 0.70

Feedback 1: Thumbs up (+0.05)
Feedback 2: 5-star rating (+0.10)
Feedback 3: Correction (-0.03)

Total Adjustment: +0.12
New Confidence: 0.70 + 0.12 = 0.82
```

### Batch Update with Recency Weighting

When doing batch updates, recent feedback has higher weight:

```
Recency Weight = max(0.1, 1.0 - (days_old / analysis_period))

Example:
- Feedback today: weight = 1.0
- Feedback 15 days ago (30-day analysis): weight = 0.5
- Feedback 29 days ago (30-day analysis): weight = 0.03
```

---

## Learning Signals

### Strength Signals

Triggered when:
- Positive ratio >= 80%
- Average rating >= 4.5

Example:
```json
{
  "type": "strength",
  "message": "Agent is performing well with high positive feedback",
  "confidence_impact": "positive"
}
```

### Weakness Signals

Triggered when:
- Positive ratio <= 40%
- Average rating <= 2.5

Example:
```json
{
  "type": "weakness",
  "message": "Agent is struggling with low positive feedback",
  "confidence_impact": "negative"
}
```

### Pattern Signals

Triggered when:
- 5+ corrections in analysis period

Example:
```json
{
  "type": "pattern",
  "message": "Agent received 7 corrections - may need retraining",
  "confidence_impact": "negative",
  "correction_count": 7
}
```

### Improvement Suggestions

Generated based on feedback patterns:

```json
[
  {
    "type": "training",
    "message": "Review common correction patterns to identify knowledge gaps",
    "priority": "high"
  },
  {
    "type": "supervision",
    "message": "Increase human supervision until performance improves",
    "priority": "medium"
  }
]
```

---

## World Model Integration

Feedback is automatically recorded in the world model as learning experiences:

```python
from core.agent_learning_enhanced import AgentLearningEnhanced
from core.database import SessionLocal

db = SessionLocal()
learning = AgentLearningEnhanced(db)

# Record feedback in world model
await learning.record_feedback_in_world_model(feedback_obj)
```

This creates an `AgentExperience` entry with:
- **feedback_score**: Calculated from thumbs up/down and rating (-1.0 to 1.0)
- **outcome**: Success/Failure based on feedback
- **learnings**: User correction or AI reasoning
- **agent_execution_id**: Link to original execution

Agents can then retrieve these experiences during future tasks to learn from past feedback.

---

## Migration

### Create Migration

```bash
cd backend
alembic revision -m "Enhance AgentFeedback with ratings and execution linking"
```

### Run Migration

```bash
alembic upgrade head
```

### Migration ID

- `8b6243295b71` - Enhance AgentFeedback with ratings and execution linking

---

## Frontend Integration

### Feedback Widget Component

```typescript
interface FeedbackWidgetProps {
  agentId: string;
  agentExecutionId: string;
  userId: string;
}

const FeedbackWidget: React.FC<FeedbackWidgetProps> = ({
  agentId,
  agentExecutionId,
  userId
}) => {
  const [thumbsUp, setThumbsUp] = useState<boolean | null>(null);
  const [rating, setRating] = useState<number | null>(null);
  const [correction, setCorrection] = useState("");

  const handleSubmit = async () => {
    await fetch("/api/feedback/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: agentId,
        agent_execution_id: agentExecutionId,
        user_id: userId,
        thumbs_up_down: thumbsUp,
        rating: rating,
        user_correction: correction
      })
    });
  };

  return (
    <div className="feedback-widget">
      <button onClick={() => setThumbsUp(true)}>👍</button>
      <button onClick={() => setThumbsUp(false)}>👎</button>

      <StarRating rating={rating} onChange={setRating} />

      <textarea
        placeholder="Add correction or comment..."
        value={correction}
        onChange={(e) => setCorrection(e.target.value)}
      />

      <button onClick={handleSubmit}>Submit Feedback</button>
    </div>
  );
};
```

### Analytics Dashboard Component

```typescript
const FeedbackAnalytics: React.FC = () => {
  const [analytics, setAnalytics] = useState(null);

  useEffect(() => {
    fetch("/api/feedback/analytics?days=30")
      .then(res => res.json())
      .then(setAnalytics);
  }, []);

  return (
    <div className="analytics-dashboard">
      <h2>Feedback Analytics</h2>

      <div className="summary">
        <p>Total Feedback: {analytics?.summary?.total_feedback}</p>
        <p>Positive Ratio: {analytics?.summary?.overall_positive_ratio}</p>
        <p>Average Rating: {analytics?.summary?.overall_average_rating}</p>
      </div>

      <div className="top-agents">
        <h3>Top Performing Agents</h3>
        {analytics?.top_performing_agents.map(agent => (
          <div key={agent.agent_id}>
            <p>{agent.agent_name}: {agent.positive_ratio}% positive</p>
          </div>
        ))}
      </div>

      <FeedbackTrendsChart data={analytics?.trends} />
    </div>
  );
};
```

---

## Testing

### Unit Tests

```bash
pytest tests/test_feedback_enhanced.py -v
```

### Test Coverage

- Feedback submission (thumbs up/down, ratings, corrections)
- Feedback analytics (summaries, statistics, trends)
- Confidence adjustments
- Learning signals
- Batch updates
- Integration tests

### Manual Testing

```bash
# Test feedback submission
curl -X POST http://localhost:8000/api/feedback/submit \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-1",
    "user_id": "user-1",
    "thumbs_up_down": true,
    "rating": 5
  }'

# Get agent summary
curl http://localhost:8000/api/feedback/agent/agent-1?days=30

# Get overall analytics
curl http://localhost:8000/api/feedback/analytics?days=30

# Get trends
curl http://localhost:8000/api/feedback/trends?days=30
```

---

## Best Practices

### 1. Collect Feedback Immediately
Request feedback right after agent execution while the interaction is fresh.

### 2. Keep It Simple
Start with thumbs up/down. Offer detailed feedback options only when needed.

### 3. Provide Context
Include the original input and agent output with feedback requests.

### 4. Act on Feedback
- Use confidence adjustments to automatically improve agents
- Review learning signals regularly
- Address recurring correction patterns

### 5. Monitor Trends
Track feedback trends over time to identify:
- Improving or declining performance
- Agents needing additional training
- Common failure patterns

### 6. Set Thresholds
Define thresholds for automatic actions:
- Positive ratio < 40%: Increase supervision
- Correction count > 10: Trigger retraining
- Average rating < 3.0: Review agent configuration

---

## Troubleshooting

### Low Feedback Collection

**Problem**: Users aren't providing feedback.

**Solutions**:
- Make feedback requests prominent but not annoying
- Offer quick options (thumbs up/down) first
- Request feedback at the right time (after task completion)

### Skewed Feedback

**Problem**: Only negative feedback being collected.

**Solutions**:
- Make positive feedback as easy as negative
- Use random sampling for feedback requests
- Offer incentives for balanced feedback

### Confidence Not Adjusting

**Problem**: Agent confidence not changing despite feedback.

**Solutions**:
- Check if batch update job is running
- Verify feedback is being recorded correctly
- Review confidence adjustment weights

### Learning Signals Not Generated

**Problem**: No learning signals appearing.

**Solutions**:
- Ensure minimum feedback threshold is met (5+ feedback)
- Check feedback type classification
- Review signal generation logic

---

## Performance Considerations

### Database Indexes

Key indexes for performance:
- `agent_feedback.agent_execution_id`
- `agent_feedback.rating`
- `agent_feedback.feedback_type`
- `agent_feedback.created_at`

### Query Optimization

- Use date range filters to limit query size
- Aggregate statistics periodically (daily/hourly)
- Cache frequently accessed summaries

### Scalability

- Partition feedback by date for large datasets
- Use read replicas for analytics queries
- Implement pagination for trend data

---

## Future Enhancements

### Planned

1. **Batch Feedback Approval** - Approve/reject multiple feedback at once
2. **Feedback-Based Promotions** - Auto-promote agents based on feedback
3. **A/B Testing Framework** - Test agent configurations
4. **Feedback Export/Import** - Share feedback between environments
5. **Sentiment Analysis** - Analyze text feedback for sentiment
6. **Feedback Categorization** - Auto-categorize corrections by type

### Researching

1. **Reinforcement Learning** - Use feedback for RL training
2. **Feedback Clustering** - Identify common correction patterns
3. **Predictive Feedback** - Predict when feedback will be negative
4. **Multi-Dimensional Ratings** - Rate different aspects (accuracy, speed, tone)

---

## References

### Files
- `backend/core/models.py` - AgentFeedback model
- `backend/api/feedback_enhanced.py` - Enhanced feedback API
- `backend/api/feedback_analytics.py` - Analytics API
- `backend/core/feedback_analytics.py` - Analytics service
- `backend/core/agent_learning_enhanced.py` - Learning service
- `backend/core/agent_world_model.py` - World model integration
- `backend/tests/test_feedback_enhanced.py` - Test suite

### Related Documentation
- `CLAUDE.md` - Project documentation
- `docs/DEEPLINK_IMPLEMENTATION.md` - Deep linking guide
- `docs/AGENT_GOVERNANCE.md` - Agent governance

---

## Summary

Atom's enhanced feedback system provides:

✅ **Quick feedback** - Thumbs up/down for instant feedback
✅ **Star ratings** - 1-5 star scale for nuanced feedback
✅ **Detailed corrections** - Specific corrections for learning
✅ **Auto-classification** - Feedback types detected automatically
✅ **Analytics dashboard** - Comprehensive statistics and trends
✅ **Confidence adjustments** - Automatic score adjustments
✅ **Learning signals** - Identifies strengths and weaknesses
✅ **World model integration** - Stores feedback as experiences

**Key Takeaway**: User feedback drives continuous improvement through confidence adjustments and learning signals, enabling agents to learn from mistakes and build on successes.
