# Canvas Context for Agent Learning

**Date**: February 2, 2026
**Related**: Agent Guidance System, Agent Governance & Learning Integration

---

## Overview

The Canvas system is not just a **display** layer - it's a **bidirectional feedback system** that continuously learns from user interactions to improve agent performance, confidence scoring, and decision-making.

## Key Principle: Every Canvas Interaction is Learning Data

```
User Action on Canvas → Feedback Signal → Agent Learning → Improved Behavior
```

---

## 1. User Feedback → Confidence Scoring

### Feedback Collection Points

#### A. Operation Completion Feedback

```typescript
// User provides feedback on completed operation
{
  type: "canvas:feedback",
  data: {
    operation_id: "op_123",
    agent_id: "agent_456",
    feedback_type: "thumbs_up" | "thumbs_down" | "rating" | "comment",
    rating: 1-5,  // Star rating
    user_comment: "Great explanation, very clear!",
    context: {
      operation_type: "integration_connect",
      duration_ms: 15000,
      user_engagement: "high"  // User watched entire operation
    }
  }
}
```

**Backend Processing**:

```python
# core/confidence_scorer.py

async def record_canvas_feedback(
    agent_id: str,
    operation_id: str,
    feedback_type: str,
    rating: Optional[int],
    user_comment: Optional[str],
    context: Dict[str, Any]
):
    """Record user feedback from canvas interactions."""

    # 1. Calculate feedback impact
    feedback_value = calculate_feedback_value(
        feedback_type=feedback_type,
        rating=rating,
        user_engagement=context.get("user_engagement")
    )

    # 2. Update agent confidence
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == agent_id
    ).first()

    if agent:
        # Adjust confidence score
        agent.confidence_score = clamp(
            agent.confidence_score + (feedback_value * 0.05),
            0.0, 1.0
        )

        # Track feedback for maturity assessment
        await agent_feedback_store.add_feedback(
            agent_id=agent_id,
            operation_type=context.get("operation_type"),
            feedback_value=feedback_value
        )

        # Check if ready for maturity promotion
        if agent.confidence_score >= 0.7 and agent.maturity < AgentMaturity.SUPERVISED:
            await evaluate_maturity_promotion(agent)
```

#### B. Resolution Selection Feedback

```typescript
// User selects error resolution
{
  type: "error:resolution_selected",
  data: {
    operation_id: "op_123",
    error_type: "auth_expired",
    resolution_index: 0,  // "Let Agent Reconnect"
    resolution: {
      title: "Let Agent Reconnect",
      agent_can_fix: true,
      steps: [...]
    },
    user_outcome: "success" | "failure" | "partial"
  }
}
```

**Learning Impact**:

```python
# Updates error resolution success rates
await error_engine.track_resolution(
    error_type="auth_expired",
    resolution_attempted="Let Agent Reconnect",
    success=(user_outcome == "success"),
    agent_suggested=True
)

# Increases agent confidence in error handling
await confidence_scorer.update_dimension(
    agent_id=agent_id,
    dimension="error_resolution",
    delta=+0.1 if user_outcome == "success" else -0.05
)
```

#### C. Request Response Feedback

```typescript
// User responds to agent request
{
  type: "agent:request_response",
  data: {
    request_id: "req_456",
    agent_id: "agent_456",
    request_type: "permission" | "decision",
    user_response: {
      action: "approve" | "deny" | "approve_once" | "customize",
      label: "Approve Once",
      timestamp: "2026-02-02T11:30:00Z"
    },
    response_time_seconds: 45.2
  }
}
```

**Learning Impact**:

```python
# Records user trust level
await agent_request_manager.handle_response(
    user_id=user_id,
    request_id=request_id,
    response=user_response
)

# Updates agent's "trust score"
await confidence_scorer.update_trust_score(
    agent_id=agent_id,
    request_type=request_type,
    approved=(user_response.action in ["approve", "approve_once"]),
    response_time=response_time_seconds
)
```

---

## 2. Canvas Engagement Metrics

### Tracking User Attention

```python
# core/canvas_analytics.py

class CanvasEngagementTracker:
    """Tracks how users interact with canvas operations."""

    async def track_operation_view_time(
        self,
        operation_id: str,
        user_id: str,
        view_duration_seconds: float
    ):
        """
        Track how long user watched operation.

        Longer view time → higher engagement → more learning impact
        """
        engagement_level = calculate_engagement_level(view_duration_seconds)

        if engagement_level == "high":
            # User paid attention, weigh feedback more heavily
            await confidence_scorer.record_engagement(
                operation_id=operation_id,
                engagement_multiplier=1.5
            )

    async def track_log_expansions(
        self,
        operation_id: str,
        user_id: str,
        logs_expanded: bool
    ):
        """
        Track if user expanded operation logs.

        Indicates user wants more detail → high engagement
        """
        if logs_expanded:
            await confidence_scorer.record_engagement(
                operation_id=operation_id,
                engagement_multiplier=1.2
            )
```

### Engagement Scoring

```python
def calculate_engagement_score(
    view_duration: float,
    logs_expanded: bool,
    feedback_provided: bool,
    guidance_followed: bool
) -> float:
    """
    Calculate overall engagement score (0.0 - 1.0).

    Higher engagement = stronger signal for learning
    """
    score = 0.0

    # View duration (up to 60 seconds = full engagement)
    score += min(view_duration / 60.0, 1.0) * 0.4

    # Log expansion (+0.2)
    if logs_expanded:
        score += 0.2

    # Feedback provided (+0.2)
    if feedback_provided:
        score += 0.2

    # Followed agent guidance (+0.2)
    if guidance_followed:
        score += 0.2

    return min(score, 1.0)
```

---

## 3. Context-Aware Learning

### Operation Type Learning

```python
# core/context_aware_learner.py

class ContextAwareLearner:
    """Learns agent performance in different contexts."""

    async def record_operation_outcome(
        self,
        agent_id: str,
        operation_type: str,  # integration_connect, browser_automate, etc.
        success: bool,
        context: Dict[str, Any]
    ):
        """
        Record operation outcome with context.

        Context includes:
        - Time of day
        - Integration type
        - Data sensitivity
        - User experience level
        """
        # Update agent's performance profile for this operation type
        await agent_performance_profile.update(
            agent_id=agent_id,
            operation_type=operation_type,
            success=success,
            context=context
        )

        # Adjust confidence for this specific operation type
        profile = await agent_performance_profile.get(agent_id, operation_type)

        if profile.success_rate > 0.9:
            # Agent is very good at this operation type
            await confidence_scorer.update_dimension(
                agent_id=agent_id,
                dimension=f"operation_{operation_type}",
                delta=+0.05
            )
```

### Temporal Patterns

```python
async def track_temporal_performance(agent_id: str, operation_type: str):
    """
    Track if agent performs better at certain times.

    Example: Agent might be better at API calls during business hours
    when servers are less overloaded.
    """
    now = datetime.now()
    hour = now.hour
    day_of_week = now.weekday()

    performance = await get_performance_at_time(
        agent_id=agent_id,
        hour=hour,
        day_of_week=day_of_week
    )

    # Learn temporal patterns
    if performance.success_rate > 0.8:
        await agent_performance_profile.add_temporal_strength(
            agent_id=agent_id,
            hour=hour,
            day_of_week=day_of_week
        )
```

---

## 4. Explanation Quality Learning

### What Makes a Good Explanation?

```python
# core/explanation_quality_scorer.py

class ExplanationQualityScorer:
    """Learns which explanations users find helpful."""

    async def score_explanation(
        self,
        operation_id: str,
        explanation: {
            "what": str,
            "why": str,
            "next": str
        },
        user_feedback: {
            "rating": int,
            "engagement_time": float,
            "understood": bool
        }
    ):
        """
        Score explanation quality based on user feedback.

        Learns patterns in effective explanations.
        """
        # Extract features
        features = {
            "what_length": len(explanation["what"]),
            "why_length": len(explanation["why"]),
            "next_length": len(explanation["why"]),
            "has_plain_language": has_plain_language(explanation["what"]),
            "has_context": has_context(explanation["why"]),
            "has_next_steps": has_next_steps(explanation["next"]),
            "user_rating": user_feedback["rating"],
            "engagement_time": user_feedback["engagement_time"],
            "understood": user_feedback["understood"]
        }

        # Update explanation quality model
        await explanation_quality_model.train(features)

        # If user understood well, reinforce this explanation style
        if user_feedback["understood"] and user_feedback["rating"] >= 4:
            await explanation_style_reinforcer.reinforce(
                features=features,
                reinforcement_amount=0.1
            )
```

### Adaptive Explanations

```python
# Over time, agent learns which explanations work best for which users

async def generate_personalized_explanation(
    agent_id: str,
    user_id: str,
    operation_type: str,
    operation_context: Dict[str, Any]
) -> {
    "what": str,
    "why": str,
    "next": str
}:
    """
    Generate explanation personalized to user's preferences.

    Learns from:
    - Past feedback from this user
    - This user's technical level
    - This user's preferred explanation style
    """
    # Get user's preference profile
    user_profile = await user_preference_store.get(user_id)

    # Get agent's explanation history
    explanation_history = await agent_explanation_history.get(
        agent_id=agent_id,
        user_id=user_id
    )

    # Generate explanation based on learned preferences
    if user_profile.technical_level == "beginner":
        # Use more detail, simpler language
        what = generate_beginner_explanation(operation_type)
    elif user_profile.technical_level == "expert":
        # Use concise technical explanations
        what = generate_expert_explanation(operation_type)
    else:
        # Use balanced explanations
        what = generate_balanced_explanation(operation_type)

    return {
        "what": what,
        "why": generate_why_explanation(operation_type, user_profile),
        "next": generate_next_explanation(operation_type, user_profile)
    }
```

---

## 5. Request Pattern Learning

### What Requests Get Approved?

```python
# core/request_pattern_learner.py

class RequestPatternLearner:
    """Learns which requests users are likely to approve."""

    async def analyze_approval_patterns(
        self,
        agent_id: str,
        user_id: str
    ):
        """
        Analyze historical request approvals for this agent/user pair.

        Learns:
        - Which permission types are usually approved
        - Which explanations lead to approval
        - What urgency levels get approved
        - Time of day patterns
        """
        history = await agent_request_log.get_history(agent_id, user_id)

        approval_rate = calculate_approval_rate(history)
        common_factors = extract_common_factors(history, approved=True)

        return {
            "approval_rate": approval_rate,
            "success_factors": common_factors,
            "recommendations": generate_request_recommendations(common_factors)
        }

    async def predict_approval_probability(
        self,
        request: {
            "request_type": str,
            "urgency": str,
            "explanation": str,
            "context": Dict[str, Any]
        }
    ) -> float:
        """
        Predict probability of user approval.

        Agent uses this to:
        - Decide when to make requests
        - Optimize request wording
        - Choose best timing
        """
        features = extract_request_features(request)
        probability = await approval_model.predict(features)
        return probability
```

### Adaptive Requesting

```python
# Agent learns to make better requests over time

async def optimize_request(
    agent_id: str,
    user_id: str,
    base_request: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Optimize request based on learned patterns.

    Improves approval rates over time.
    """
    # Get user's approval patterns
    patterns = await request_pattern_learner.analyze_approval_patterns(
        agent_id=agent_id,
        user_id=user_id
    )

    # Optimize explanation based on success factors
    optimized_explanation = optimize_text(
        base_request["explanation"],
        patterns["success_factors"]
    )

    # Choose best timing
    best_time = predict_best_request_time(user_id, patterns)

    # Adjust urgency based on patterns
    optimal_urgency = determine_optimal_urgency(
        base_request["urgency"],
        patterns["approval_rate_by_urgency"]
    )

    return {
        **base_request,
        "explanation": optimized_explanation,
        "scheduled_for": best_time,
        "urgency": optimal_urgency
    }
```

---

## 6. Error Recovery Learning

### Which Resolutions Work?

```python
# core/error_recovery_learner.py

class ErrorRecoveryLearner:
    """Learns which error resolutions work best."""

    async def track_resolution_outcome(
        self,
        error_type: str,
        resolution: str,
        success: bool,
        time_to_resolve: float,
        user_satisfaction: int
    ):
        """
        Track error resolution outcome.

        Learns:
        - Which resolutions work fastest
        - Which have highest success rate
        - Which users prefer most
        """
        await resolution_success_rate.update(
            error_type=error_type,
            resolution=resolution,
            success=success
        )

        await resolution_time_tracker.record(
            error_type=error_type,
            resolution=resolution,
            time_to_resolve=time_to_resolve
        )

        await resolution_user_satisfaction.record(
            error_type=error_type,
            resolution=resolution,
            satisfaction=user_satisfaction
        )

    async def recommend_resolution(
        self,
        error_type: str,
        user_id: str
    ) -> str:
        """
        Recommend best resolution for this error/user.

        Personalized based on:
        - Historical success rates
        - User's past preferences
        - Resolution time
        - User satisfaction
        """
        user_history = await get_user_error_resolution_history(user_id)

        # Find resolutions that worked for this user before
        successful_for_user = [
            r for r in user_history
            if r.error_type == error_type and r.success
        ]

        if successful_for_user:
            # Use what worked before
            return successful_for_user[0].resolution

        # Fall back to global best
        return await get_best_resolution_globally(error_type)
```

---

## 7. Real-Time Learning Loop

### Canvas → Learning → Agent Improvement

```
┌─────────────────────────────────────────────────────────────┐
│                    CANVAS DISPLAY                           │
│  • Shows operation progress                                │
│  • Displays error with resolutions                         │
│  • Presents requests for input/decisions                   │
└─────────────────────────────────────────────────────────────┘
                          ↓ User Interacts
┌─────────────────────────────────────────────────────────────┐
│                    FEEDBACK COLLECTION                      │
│  • User ratings (thumbs up/down, stars)                    │
│  • Resolution selection                                    │
│  • Request responses                                       │
│  • Engagement metrics (view time, log expansion)           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    LEARNING PROCESSING                      │
│  • Update confidence scores                                │
│  • Track success rates                                    │
│  • Learn user preferences                                 │
│  • Identify patterns                                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    AGENT IMPROVEMENT                        │
│  • Adjust explanations for user                            │
│  • Optimize request timing                                 │
│  • Choose better resolutions                               │
│  • Increase maturity level                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    IMPROVED CANVAS DISPLAY                  │
│  • Better explanations                                     │
│  • More accurate resolution suggestions                    │
│  • More effective requests                                 │
│  • Higher approval rates                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Practical Examples

### Example 1: Learning User Preferences

```python
# Initial interaction (new user)
await agent.connect_slack_integration(user_id="user_123")
# Canvas shows: "Connecting to Slack to enable workflows"
# User feedback: 3/5 stars, comment: "Too technical"
# Learning: User prefers simpler explanations

# Later interaction (same user)
await agent.connect_gmail_integration(user_id="user_123")
# Canvas shows: "Connecting to Gmail (email service)"
# Explanation is simpler, less technical
# User feedback: 5/5 stars, comment: "Much clearer!"
# Learning reinforced: Simple explanations work for this user
```

### Example 2: Optimizing Request Timing

```python
# First request (morning)
await agent.request_permission(
    user_id="user_456",
    permission="calendar:write",
    urgency="medium"
)
# User response: Deny (busy in morning)
# Learning: User is less likely to approve in morning

# Second request (afternoon)
await agent.request_permission(
    user_id="user_456",
    permission="calendar:write",
    urgency="medium"
)
# User response: Approve
# Learning: Afternoon is better time for requests

# Future requests scheduled for afternoon
```

### Example 3: Error Resolution Learning

```python
# First error occurrence
await agent.handle_auth_error(user_id="user_789")
# Canvas shows error with 2 resolution options:
# 1. Let Agent Reconnect (suggested)
# 2. Reconnect Manually
# User selects: Option 2 (Manual)
# Learning: This user prefers manual control for auth errors

# Second error occurrence (same user)
await agent.handle_auth_error(user_id="user_789")
# Canvas shows error with different suggestion:
# 1. Reconnect Manually (suggested - based on past preference)
# 2. Let Agent Reconnect
# User selects: Option 1 (Suggested)
# Learning: Pattern confirmed, user prefers manual auth fixes
```

---

## 9. Implementation Checklist

### Backend Integration

- [x] Canvas feedback endpoints collect engagement metrics
- [x] Confidence scorer integrates with canvas feedback
- [x] Error resolution learning from user choices
- [x] Request response tracking
- [x] Explanation quality scoring
- [ ] Real-time learning pipeline
- [ ] Personalized explanation generation
- [ ] Request timing optimization

### Frontend Integration

- [x] Feedback buttons on operations
- [x] Resolution selection tracking
- [x] Request response handling
- [ ] Engagement time tracking
- [ ] Log expansion tracking
- [ ] User preference collection

### Data Pipeline

- [ ] Canvas feedback → Analytics database
- [ ] Learning model training pipeline
- [ ] Real-time model updates
- [ ] A/B testing for explanation styles
- [ ] User preference persistence

---

## Summary

Canvas is a **learning system**, not just a display:

1. **Every interaction is data** - User actions feed back into learning
2. **Personalization improves over time** - Agents learn individual user preferences
3. **Confidence scoring is continuous** - Real-time updates from canvas feedback
4. **Explainability is adaptive** - Improves based on user feedback
5. **Request optimization** - Better timing, wording, and urgency

This creates a **virtuous cycle**:
- Better explanations → More trust → Higher approval rates
- More trust → More autonomy → Better maturity
- Better maturity → Better operations → More positive feedback

---

**Related Documentation**:
- [Agent Guidance Implementation](./AGENT_GUIDANCE_IMPLEMENTATION.md)
- [Agent Governance & Learning Integration](./AGENT_GOVERNANCE_LEARNING_INTEGRATION.md)
- [Confidence Scoring System](../backend/core/confidence_scorer.py)
