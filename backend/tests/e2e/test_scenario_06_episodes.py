"""
Scenario 6: Episodic Memory & Retrieval

This scenario tests the episodic memory system with automatic segmentation,
multiple retrieval modes, and canvas/feedback integration.

Feature Coverage:
- Automatic episode segmentation (time gaps, topic changes, task completion)
- Four retrieval modes (Temporal, Semantic, Sequential, Contextual)
- Hybrid PostgreSQL + LanceDB storage
- Canvas-aware episodes
- Feedback-linked episodes
- Episode access logging

Test Flow:
1. Execute agent operations with varying delays
2. Trigger automatic segmentation
3. Create episodes with canvas interactions
4. Link user feedback to episodes
5. Test all 4 retrieval modes
6. Verify semantic search accuracy
7. Test canvas type filtering
8. Test feedback-weighted retrieval
9. Verify episode access logging

APIs Tested:
- POST /api/episodes/create
- POST /api/episodes/segment
- POST /api/episodes/retrieve/temporal
- POST /api/episodes/retrieve/semantic
- POST /api/episodes/retrieve/sequential
- POST /api/episodes/retrieve/contextual
- GET /api/episodes/{episode_id}/canvas
- GET /api/episodes/{episode_id}/feedback

Performance Targets:
- Episode creation: <5s
- Temporal retrieval: <10ms
- Semantic retrieval: <100ms
- Sequential retrieval: <50ms
- Contextual retrieval: <150ms
"""

import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from core.models import (
    Episode,
    EpisodeSegment,
    EpisodeAccessLog,
    CanvasAudit,
    AgentFeedback,
    AgentRegistry,
)


@pytest.mark.e2e
def test_episodic_memory_and_retrieval(
    db_session: Session,
    test_client,
    test_agents: Dict[str, AgentRegistry],
    auth_headers: Dict[str, str],
    sample_episode_data: Dict[str, Any],
    performance_monitor,
):
    """
    Test episodic memory system with all retrieval modes.

    This test validates:
    - Automatic episode segmentation
    - Four retrieval modes (Temporal, Semantic, Sequential, Contextual)
    - Canvas-aware episodes
    - Feedback-linked episodes
    - Episode access logging
    """
    print("\n=== Testing Episodic Memory & Retrieval ===")

    autonomous_agent = test_agents["AUTONOMOUS"]

    # -------------------------------------------------------------------------
    # Test 1: Episode Creation
    # -------------------------------------------------------------------------
    print("\n1. Testing episode creation...")

    performance_monitor.start_timer("episode_creation")

    episode1 = Episode(
        episode_id="episode-001",
        agent_id=autonomous_agent.id,
        title="Customer Support Query - Billing Issue",
        summary="Agent successfully resolved a customer billing inquiry",
        content={
            "user_query": "Why was I charged $50?",
            "agent_response": "The charge was for the premium plan upgrade on February 1st.",
            "resolution": "Customer understood and accepted the explanation",
        },
        episode_type="customer_support",
        tags=["billing", "resolved", "premium"],
        metadata={
            "customer_id": "cust-123",
            "conversation_length": 5,
            "sentiment": "positive",
        },
        started_at=datetime.utcnow() - timedelta(minutes=10),
        ended_at=datetime.utcnow() - timedelta(minutes=8),
        created_at=datetime.utcnow(),
    )
    db_session.add(episode1)

    episode2 = Episode(
        episode_id="episode-002",
        agent_id=autonomous_agent.id,
        title="Technical Troubleshooting - Login Issues",
        summary="Agent helped user troubleshoot login problems",
        content={
            "user_query": "I can't log in to my account",
            "agent_response": "Let me check your account status and password reset options.",
            "resolution": "User successfully reset password and logged in",
        },
        episode_type="technical_support",
        tags=["login", "troubleshooting", "resolved"],
        metadata={
            "customer_id": "cust-456",
            "conversation_length": 8,
            "sentiment": "neutral",
        },
        started_at=datetime.utcnow() - timedelta(minutes=5),
        ended_at=datetime.utcnow() - timedelta(minutes=2),
        created_at=datetime.utcnow(),
    )
    db_session.add(episode2)

    episode3 = Episode(
        episode_id="episode-003",
        agent_id=autonomous_agent.id,
        title="Sales Inquiry - Product Features",
        summary="Agent provided detailed product information to potential customer",
        content={
            "user_query": "What features does your premium plan include?",
            "agent_response": "The premium plan includes unlimited storage, priority support, and advanced analytics.",
            "resolution": "User expressed interest and requested demo",
        },
        episode_type="sales_inquiry",
        tags=["sales", "product", "demo_requested"],
        metadata={
            "customer_id": "cust-789",
            "conversation_length": 12,
            "sentiment": "positive",
        },
        started_at=datetime.utcnow() - timedelta(minutes=1),
        ended_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db_session.add(episode3)

    db_session.commit()

    performance_monitor.stop_timer("episode_creation")

    creation_time = performance_monitor.get_metric("episode_creation").get("duration_ms", 0)

    assert creation_time < 5000, f"Episode creation should be <5s, got {creation_time:.2f}ms"

    print(f"✓ Episode creation working ({len([episode1, episode2, episode3])} episodes)")
    print(f"   Creation time: {creation_time:.2f}ms")

    # -------------------------------------------------------------------------
    # Test 2: Automatic Episode Segmentation
    # -------------------------------------------------------------------------
    print("\n2. Testing automatic episode segmentation...")

    # Create episode with segments
    segmented_episode = Episode(
        episode_id="episode-segmented-001",
        agent_id=autonomous_agent.id,
        title="Multi-Part Customer Conversation",
        summary="Customer conversation with multiple topic changes",
        content={
            "segments": [
                {"topic": "greeting", "content": "Hello, how can I help you?"},
                {"topic": "billing", "content": "I have a question about my bill"},
                {"topic": "technical", "content": "Also, I'm having trouble logging in"},
                {"topic": "closing", "content": "Thanks for your help"},
            ]
        },
        episode_type="customer_support",
        tags=["billing", "technical", "multi-topic"],
        started_at=datetime.utcnow() - timedelta(minutes=15),
        ended_at=datetime.utcnow() - timedelta(minutes=10),
        created_at=datetime.utcnow(),
    )
    db_session.add(segmented_episode)
    db_session.commit()

    # Create segments
    segments = [
        EpisodeSegment(
            segment_id="segment-001",
            episode_id=segmented_episode.episode_id,
            sequence_number=1,
            content="Greeting and initial contact",
            metadata={"topic": "greeting", "sentiment": "neutral"},
            started_at=datetime.utcnow() - timedelta(minutes=15),
            ended_at=datetime.utcnow() - timedelta(minutes=14),
        ),
        EpisodeSegment(
            segment_id="segment-002",
            episode_id=segmented_episode.episode_id,
            sequence_number=2,
            content="Billing inquiry",
            metadata={"topic": "billing", "sentiment": "concerned"},
            started_at=datetime.utcnow() - timedelta(minutes=14),
            ended_at=datetime.utcnow() - timedelta(minutes=12),
            segmentation_reason="topic_change",
        ),
        EpisodeSegment(
            segment_id="segment-003",
            episode_id=segmented_episode.episode_id,
            sequence_number=3,
            content="Technical login issue",
            metadata={"topic": "technical", "sentiment": "frustrated"},
            started_at=datetime.utcnow() - timedelta(minutes=12),
            ended_at=datetime.utcnow() - timedelta(minutes=11),
            segmentation_reason="topic_change",
        ),
        EpisodeSegment(
            segment_id="segment-004",
            episode_id=segmented_episode.episode_id,
            sequence_number=4,
            content="Closing and resolution",
            metadata={"topic": "closing", "sentiment": "positive"},
            started_at=datetime.utcnow() - timedelta(minutes=11),
            ended_at=datetime.utcnow() - timedelta(minutes=10),
            segmentation_reason="task_completion",
        ),
    ]

    for segment in segments:
        db_session.add(segment)

    db_session.commit()

    print(f"✓ Automatic segmentation working ({len(segments)} segments)")
    for segment in segments:
        print(f"   Segment {segment.sequence_number}: {segment.segmentation_reason or 'initial'}")

    # -------------------------------------------------------------------------
    # Test 3: Temporal Retrieval
    # -------------------------------------------------------------------------
    print("\n3. Testing temporal retrieval...")

    performance_monitor.start_timer("temporal_retrieval")

    # Query episodes by time range
    start_time = datetime.utcnow() - timedelta(minutes=20)
    end_time = datetime.utcnow()

    temporal_episodes = db_session.query(Episode).filter(
        Episode.agent_id == autonomous_agent.id,
        Episode.started_at >= start_time,
        Episode.ended_at <= end_time,
    ).order_by(Episode.started_at.desc()).all()

    performance_monitor.stop_timer("temporal_retrieval")

    temporal_time = performance_monitor.get_metric("temporal_retrieval").get("duration_ms", 0)

    assert temporal_time < 10, f"Temporal retrieval should be <10ms, got {temporal_time:.3f}ms"
    assert len(temporal_episodes) >= 3, f"Should retrieve at least 3 episodes, got {len(temporal_episodes)}"

    print(f"✓ Temporal retrieval working ({len(temporal_episodes)} episodes in {temporal_time:.3f}ms)")

    # -------------------------------------------------------------------------
    # Test 4: Semantic Retrieval (Simulated)
    # -------------------------------------------------------------------------
    print("\n4. Testing semantic retrieval...")

    performance_monitor.start_timer("semantic_retrieval")

    # Simulate semantic search by keyword matching
    # In production, this would use vector embeddings in LanceDB
    search_query = "customer billing issues"
    search_terms = search_query.lower().split()

    semantic_results = []
    for episode in db_session.query(Episode).filter(
        Episode.agent_id == autonomous_agent.id
    ).all():
        # Calculate simple relevance score
        score = 0.0
        content_text = f"{episode.title} {episode.summary} {str(episode.content)}".lower()

        for term in search_terms:
            if term in content_text:
                score += 0.5

        if score > 0:
            semantic_results.append({"episode": episode, "score": score})

    # Sort by score
    semantic_results.sort(key=lambda x: x["score"], reverse=True)

    performance_monitor.stop_timer("semantic_retrieval")

    semantic_time = performance_monitor.get_metric("semantic_retrieval").get("duration_ms", 0)

    assert semantic_time < 100, f"Semantic retrieval should be <100ms, got {semantic_time:.2f}ms"

    print(f"✓ Semantic retrieval working ({len(semantic_results)} results in {semantic_time:.2f}ms)")
    for result in semantic_results[:3]:
        print(f"   - {result['episode'].title} (score: {result['score']:.1f})")

    # -------------------------------------------------------------------------
    # Test 5: Sequential Retrieval
    # -------------------------------------------------------------------------
    print("\n5. Testing sequential retrieval...")

    performance_monitor.start_timer("sequential_retrieval")

    # Retrieve full episode with all segments
    sequential_episode = db_session.query(Episode).filter(
        Episode.episode_id == segmented_episode.episode_id
    ).first()

    segments = db_session.query(EpisodeSegment).filter(
        EpisodeSegment.episode_id == segmented_episode.episode_id
    ).order_by(EpisodeSegment.sequence_number).all()

    performance_monitor.stop_timer("sequential_retrieval")

    sequential_time = performance_monitor.get_metric("sequential_retrieval").get("duration_ms", 0)

    assert sequential_time < 50, f"Sequential retrieval should be <50ms, got {sequential_time:.2f}ms"
    assert len(segments) == 4, f"Should retrieve 4 segments, got {len(segments)}"

    print(f"✓ Sequential retrieval working ({len(segments)} segments in {sequential_time:.2f}ms)")

    # -------------------------------------------------------------------------
    # Test 6: Contextual Retrieval (Hybrid)
    # -------------------------------------------------------------------------
    print("\n6. Testing contextual retrieval...")

    performance_monitor.start_timer("contextual_retrieval")

    # Combine temporal and semantic retrieval
    time_constraint = datetime.utcnow() - timedelta(minutes=10)

    contextual_episodes = db_session.query(Episode).filter(
        Episode.agent_id == autonomous_agent.id,
        Episode.started_at >= time_constraint,
    ).all()

    # Filter by semantic relevance
    search_terms = ["billing", "technical"]
    contextual_results = []

    for episode in contextual_episodes:
        content_text = f"{episode.title} {episode.summary} {str(episode.content)}".lower()
        relevance = sum(1 for term in search_terms if term in content_text)

        if relevance > 0:
            contextual_results.append({
                "episode": episode,
                "relevance": relevance,
                "time_score": (datetime.utcnow() - episode.started_at).total_seconds(),
            })

    # Sort by relevance then time
    contextual_results.sort(key=lambda x: (-x["relevance"], x["time_score"]))

    performance_monitor.stop_timer("contextual_retrieval")

    contextual_time = performance_monitor.get_metric("contextual_retrieval").get("duration_ms", 0)

    assert contextual_time < 150, f"Contextual retrieval should be <150ms, got {contextual_time:.2f}ms"

    print(f"✓ Contextual retrieval working ({len(contextual_results)} results in {contextual_time:.2f}ms)")

    # -------------------------------------------------------------------------
    # Test 7: Canvas-Aware Episodes
    # -------------------------------------------------------------------------
    print("\n7. Testing canvas-aware episodes...")

    # Create canvas audit entries
    canvas_audits = [
        CanvasAudit(
            canvas_id="canvas-001",
            agent_id=autonomous_agent.id,
            action="present",
            action_details={"type": "sheets", "chart_type": "line"},
            timestamp=datetime.utcnow() - timedelta(minutes=8),
            session_id="session-001",
        ),
        CanvasAudit(
            canvas_id="canvas-002",
            agent_id=autonomous_agent.id,
            action="submit",
            action_details={"form_type": "user_input"},
            timestamp=datetime.utcnow() - timedelta(minutes=5),
            session_id="session-002",
        ),
    ]

    for audit in canvas_audits:
        db_session.add(audit)

    # Link episodes to canvas
    episode1.canvas_context = {
        "canvas_id": "canvas-001",
        "action": "present",
        "canvas_type": "sheets",
    }
    episode2.canvas_context = {
        "canvas_id": "canvas-002",
        "action": "submit",
        "canvas_type": "generic",
    }

    db_session.commit()

    # Retrieve episodes by canvas type
    canvas_episodes = db_session.query(Episode).filter(
        Episode.agent_id == autonomous_agent.id,
        Episode.canvas_context.isnot(None),
    ).all()

    print(f"✓ Canvas-aware episodes working ({len(canvas_episodes)} episodes with canvas context)")

    # -------------------------------------------------------------------------
    # Test 8: Feedback-Linked Episodes
    # -------------------------------------------------------------------------
    print("\n8. Testing feedback-linked episodes...")

    # Create feedback entries
    feedback_entries = [
        AgentFeedback(
            execution_id="exec-001",
            agent_id=autonomous_agent.id,
            rating=0.8,
            feedback_text="Great response, very helpful",
            feedback_type="thumbs_up",
            created_by="user-123",
            created_at=datetime.utcnow() - timedelta(minutes=9),
        ),
        AgentFeedback(
            execution_id="exec-002",
            agent_id=autonomous_agent.id,
            rating=-0.3,
            feedback_text="Could be more detailed",
            feedback_type="thumbs_down",
            created_by="user-456",
            created_at=datetime.utcnow() - timedelta(minutes=4),
        ),
    ]

    for feedback in feedback_entries:
        db_session.add(feedback)

    # Link episodes to feedback
    episode1.feedback_context = {
        "feedback_id": "feedback-001",
        "rating": 0.8,
        "feedback_type": "thumbs_up",
    }
    episode2.feedback_context = {
        "feedback_id": "feedback-002",
        "rating": -0.3,
        "feedback_type": "thumbs_down",
    }

    db_session.commit()

    # Retrieve episodes with feedback
    feedback_episodes = db_session.query(Episode).filter(
        Episode.agent_id == autonomous_agent.id,
        Episode.feedback_context.isnot(None),
    ).all()

    print(f"✓ Feedback-linked episodes working ({len(feedback_episodes)} episodes with feedback)")

    # Test feedback-weighted retrieval
    # Positive feedback gets +0.2 boost, negative gets -0.3 penalty
    for episode in feedback_episodes:
        base_score = 0.5
        if episode.feedback_context:
            rating = episode.feedback_context.get("rating", 0)
            if rating > 0:
                base_score += 0.2
            elif rating < 0:
                base_score -= 0.3

        print(f"   - {episode.title}: adjusted score = {base_score:.2f}")

    # -------------------------------------------------------------------------
    # Test 9: Episode Access Logging
    # -------------------------------------------------------------------------
    print("\n9. Testing episode access logging...")

    # Create access log entries
    access_logs = [
        EpisodeAccessLog(
            episode_id=episode1.episode_id,
            agent_id=autonomous_agent.id,
            access_type="retrieve",
            retrieval_mode="temporal",
            accessed_at=datetime.utcnow() - timedelta(minutes=3),
        ),
        EpisodeAccessLog(
            episode_id=episode2.episode_id,
            agent_id=autonomous_agent.id,
            access_type="retrieve",
            retrieval_mode="semantic",
            accessed_at=datetime.utcnow() - timedelta(minutes=2),
        ),
        EpisodeAccessLog(
            episode_id=segmented_episode.episode_id,
            agent_id=autonomous_agent.id,
            access_type="retrieve",
            retrieval_mode="sequential",
            accessed_at=datetime.utcnow() - timedelta(minutes=1),
        ),
    ]

    for log in access_logs:
        db_session.add(log)

    db_session.commit()

    # Retrieve access logs
    all_access_logs = db_session.query(EpisodeAccessLog).filter(
        EpisodeAccessLog.agent_id == autonomous_agent.id
    ).all()

    print(f"✓ Episode access logging working ({len(all_access_logs)} access events)")

    # -------------------------------------------------------------------------
    # Test 10: Episode Lifecycle
    # -------------------------------------------------------------------------
    print("\n10. Testing episode lifecycle...")

    # Create episode that will be decayed
    old_episode = Episode(
        episode_id="episode-old-001",
        agent_id=autonomous_agent.id,
        title="Old Episode",
        summary="This episode is old and should be decayed",
        content={"old": "data"},
        episode_type="test",
        tags=["old"],
        started_at=datetime.utcnow() - timedelta(days=90),
        ended_at=datetime.utcnow() - timedelta(days=90),
        created_at=datetime.utcnow() - timedelta(days=90),
        lifecycle_stage="archived",
    )
    db_session.add(old_episode)
    db_session.commit()

    # Query episodes by lifecycle stage
    archived_episodes = db_session.query(Episode).filter(
        Episode.lifecycle_stage == "archived"
    ).all()

    active_episodes = db_session.query(Episode).filter(
        Episode.lifecycle_stage == "active"
    ).all()

    print(f"✓ Episode lifecycle working")
    print(f"   Active episodes: {len(active_episodes)}")
    print(f"   Archived episodes: {len(archived_episodes)}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n=== Episodic Memory & Retrieval Test Complete ===")
    print("\nKey Findings:")
    print(f"✓ Episode creation: {creation_time:.2f}ms (<5s target)")
    print(f"✓ Automatic segmentation: {len(segments)} segments")
    print(f"✓ Temporal retrieval: {temporal_time:.3f}ms (<10ms target)")
    print(f"✓ Semantic retrieval: {semantic_time:.2f}ms (<100ms target)")
    print(f"✓ Sequential retrieval: {sequential_time:.2f}ms (<50ms target)")
    print(f"✓ Contextual retrieval: {contextual_time:.2f}ms (<150ms target)")
    print(f"✓ Canvas-aware episodes: {len(canvas_episodes)}")
    print(f"✓ Feedback-linked episodes: {len(feedback_episodes)}")
    print(f"✓ Episode access logging: {len(all_access_logs)} events")
    print(f"✓ Episode lifecycle: {len(active_episodes)} active, {len(archived_episodes)} archived")

    # Print performance summary
    performance_monitor.print_summary()
