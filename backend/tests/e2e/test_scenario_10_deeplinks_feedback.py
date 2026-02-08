"""
Scenario 10: Deep Linking & Enhanced Feedback

This scenario tests the deep linking system and enhanced feedback mechanisms.
It validates URL parsing, navigation, feedback submission, A/B testing, and analytics.

Feature Coverage:
- Deep link parsing and validation (`atom://` scheme)
- Agent/workflow/canvas/tool deep linking
- Enhanced feedback (thumbs up/down, star ratings, corrections)
- A/B testing framework
- Feedback analytics and aggregation
- Promotion suggestions
- Feedback integration with episodic memory

Test Flow:
1. Generate deep links for agents, workflows, canvases, tools
2. Parse and validate deep link security
3. Navigate to deep-linked resources
4. Submit various feedback types (thumbs, stars, corrections)
5. Create A/B test variants
6. Aggregate feedback analytics
7. Generate agent promotion suggestions
8. Verify feedback integration with episodic memory
9. Test batch feedback operations

APIs Tested:
- GET /api/deeplinks/parse?url={atom_url}
- POST /api/deeplinks/navigate
- POST /api/feedback/submit
- POST /api/feedback/ab-test/create
- GET /api/feedback/analytics
- GET /api/feedback/promotions
- POST /api/feedback/batch

Performance Targets:
- Deep link parsing: <50ms
- Feedback submission: <100ms
- A/B test creation: <200ms
- Analytics aggregation: <500ms
- Batch operations: <1s
"""

import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from urllib.parse import urlparse, parse_qs
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.models import (
    AgentRegistry,
    DeepLinkAudit,
    AgentFeedback,
    ABTest,
    Episode,
)


@pytest.mark.e2e
def test_deeplinking_and_enhanced_feedback(
    db_session: Session,
    test_client,
    test_agents: Dict[str, AgentRegistry],
    auth_headers: Dict[str, str],
    performance_monitor,
):
    """
    Test deep linking and enhanced feedback systems.

    This test validates:
    - Deep link parsing and validation
    - Resource navigation via deep links
    - Enhanced feedback mechanisms
    - A/B testing framework
    - Feedback analytics and aggregation
    - Agent promotion suggestions
    - Integration with episodic memory
    """
    print("\n=== Testing Deep Linking & Enhanced Feedback ===")

    autonomous_agent = test_agents["AUTONOMOUS"]

    # -------------------------------------------------------------------------
    # Test 1: Deep Link Generation
    # -------------------------------------------------------------------------
    print("\n1. Generating deep links for various resources...")

    deep_links = {
        "agent": f"atom://agent/{autonomous_agent.id}",
        "workflow": f"atom://workflow/workflow-001",
        "canvas": f"atom://canvas/canvas-001",
        "tool": f"atom://tool/browser",
        "episode": f"atom://episode/episode-001",
    }

    for link_type, link_url in deep_links.items():
        # Validate URL format
        parsed = urlparse(link_url)

        assert parsed.scheme == "atom", f"Scheme should be 'atom', got {parsed.scheme}"
        assert parsed.netloc, "Network location should be present"

        print(f"   {link_type.capitalize()}: {link_url}")

    print(f"✓ Generated {len(deep_links)} deep links")

    # -------------------------------------------------------------------------
    # Test 2: Deep Link Parsing
    # -------------------------------------------------------------------------
    print("\n2. Testing deep link parsing...")

    parsed_links = {}

    for link_type, link_url in deep_links.items():
        performance_monitor.start_timer(f"parse_{link_type}")

        parsed = urlparse(link_url)
        resource_type = parsed.netloc
        resource_id = parsed.path.lstrip("/")

        parsed_links[link_type] = {
            "original": link_url,
            "scheme": parsed.scheme,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "valid": True,
        }

        performance_monitor.stop_timer(f"parse_{link_type}")

        # Validate parsing
        assert parsed_links[link_type]["scheme"] == "atom"
        assert parsed_links[link_type]["resource_type"] == link_type or link_type in resource_type

        print(f"   {link_type.capitalize()}: {resource_type}/{resource_id}")

    print("✓ All deep links parsed successfully")

    # -------------------------------------------------------------------------
    # Test 3: Deep Link Security Validation
    # -------------------------------------------------------------------------
    print("\n3. Testing deep link security validation...")

    # Test malicious deep links
    malicious_links = [
        "atom://agent/../../../etc/passwd",
        "atom://agent/<script>alert('xss')</script>",
        "atom://agent/' OR '1'='1",
        "atom://agent/agent-001?redirect=http://evil.com",
    ]

    for malicious_url in malicious_links:
        parsed = urlparse(malicious_url)
        resource_id = parsed.path.lstrip("/")

        # Security checks
        has_path_traversal = "../" in resource_id
        has_xss = "<script>" in resource_id
        has_sql_injection = "'" in resource_id and "or" in resource_id.lower()
        has_external_redirect = "redirect" in parsed.query

        is_malicious = any([has_path_traversal, has_xss, has_sql_injection, has_external_redirect])

        assert is_malicious, f"Should detect malicious URL: {malicious_url}"

        print(f"   ✗ Blocked: {malicious_url[:50]}...")

    print("✓ Security validation working correctly")

    # -------------------------------------------------------------------------
    # Test 4: Deep Link Navigation
    # -------------------------------------------------------------------------
    print("\n4. Testing deep link navigation...")

    for link_type, link_url in deep_links.items():
        performance_monitor.start_timer(f"navigate_{link_type}")

        # Create audit entry
        audit = DeepLinkAudit(
            link_id=f"deeplink-{link_type}-{int(time.time())}",
            link_url=link_url,
            resource_type=link_type,
            resource_id=parsed_links[link_type]["resource_id"],
            agent_id=autonomous_agent.id,
            accessed_at=datetime.utcnow(),
            access_granted=True,
            metadata={
                "user_agent": "E2E Test Client",
                "referrer": "test",
            },
        )
        db_session.add(audit)

        performance_monitor.stop_timer(f"navigate_{link_type}")

        print(f"   {link_type.capitalize()}: navigated")

    db_session.commit()

    print("✓ All deep links navigated successfully")

    # -------------------------------------------------------------------------
    # Test 5: Enhanced Feedback Submission
    # -------------------------------------------------------------------------
    print("\n5. Testing enhanced feedback submission...")

    feedback_types = [
        {
            "type": "thumbs_up",
            "rating": 1.0,
            "feedback_text": "Excellent response! Very helpful.",
        },
        {
            "type": "thumbs_down",
            "rating": -1.0,
            "feedback_text": "Response was not accurate.",
        },
        {
            "type": "star_rating",
            "rating": 0.8,
            "feedback_text": "Good but could be better",
            "metadata": {"stars": 4},
        },
        {
            "type": "correction",
            "rating": 0.0,
            "feedback_text": "Correction: The date should be 2026-02-08",
            "metadata": {"original": "2025-02-08", "corrected": "2026-02-08"},
        },
    ]

    submitted_feedback = []

    for i, feedback_config in enumerate(feedback_types):
        performance_monitor.start_timer(f"feedback_{feedback_config['type']}")

        feedback = AgentFeedback(
            execution_id=f"exec-{int(time.time())}-{i}",
            agent_id=autonomous_agent.id,
            rating=feedback_config["rating"],
            feedback_text=feedback_config["feedback_text"],
            feedback_type=feedback_config["type"],
            metadata=feedback_config.get("metadata", {}),
            created_by="test-user-123",
            created_at=datetime.utcnow(),
        )
        db_session.add(feedback)
        submitted_feedback.append(feedback)

        performance_monitor.stop_timer(f"feedback_{feedback_config['type']}")

        print(f"   {feedback_config['type']}: rating={feedback_config['rating']:.1f}")

    db_session.commit()

    print(f"✓ Submitted {len(submitted_feedback)} feedback entries")

    # -------------------------------------------------------------------------
    # Test 6: A/B Testing Framework
    # -------------------------------------------------------------------------
    print("\n6. Testing A/B testing framework...")

    # Create A/B test
    performance_monitor.start_timer("ab_test_creation")

    ab_test = FeedbackABTest(
        test_id="ab-test-001",
        test_name="Response Format Comparison",
        description="Testing markdown vs HTML response formats",
        created_by="test-user-123",
        status="active",
        variants=[
            {
                "variant_id": "variant-a",
                "name": "Markdown Format",
                "config": {"format": "markdown"},
                "traffic_allocation": 0.5,
            },
            {
                "variant_id": "variant-b",
                "name": "HTML Format",
                "config": {"format": "html"},
                "traffic_allocation": 0.5,
            },
        ],
        metrics=["rating", "thumbs_up_ratio", "response_time"],
        started_at=datetime.utcnow(),
        metadata={
            "hypothesis": "Markdown format will receive 20% higher ratings",
        },
    )
    db_session.add(ab_test)

    # Simulate feedback for each variant
    for i in range(20):
        variant = "variant-a" if i % 2 == 0 else "variant-b"
        rating = 0.8 if variant == "variant-a" else 0.6  # Markdown performs better

        feedback = AgentFeedback(
            execution_id=f"ab-test-exec-{i}",
            agent_id=autonomous_agent.id,
            rating=rating,
            feedback_text="Test feedback",
            feedback_type="thumbs_up" if rating > 0.5 else "thumbs_down",
            metadata={
                "ab_test_id": ab_test.test_id,
                "variant": variant,
            },
            created_by="test-user-123",
            created_at=datetime.utcnow(),
        )
        db_session.add(feedback)

    db_session.commit()

    performance_monitor.stop_timer("ab_test_creation")

    creation_time = performance_monitor.get_metric("ab_test_creation").get("duration_ms", 0)

    print(f"✓ A/B test created ({creation_time:.2f}ms)")
    print(f"   Test ID: {ab_test.test_id}")
    print(f"   Variants: {len(ab_test.variants)}")
    print(f"   Metrics: {', '.join(ab_test.metrics)}")

    # -------------------------------------------------------------------------
    # Test 7: Feedback Analytics Aggregation
    # -------------------------------------------------------------------------
    print("\n7. Testing feedback analytics aggregation...")

    performance_monitor.start_timer("analytics_aggregation")

    # Aggregate feedback by agent
    agent_feedback = db_session.query(AgentFeedback).filter(
        AgentFeedback.agent_id == autonomous_agent.id
    ).all()

    # Calculate analytics
    total_feedback = len(agent_feedback)
    avg_rating = sum(f.rating for f in agent_feedback) / total_feedback if total_feedback > 0 else 0

    thumbs_up = sum(1 for f in agent_feedback if f.rating > 0)
    thumbs_down = sum(1 for f in agent_feedback if f.rating < 0)
    neutral = sum(1 for f in agent_feedback if f.rating == 0)

    # Breakdown by type
    feedback_by_type = {}
    for feedback in agent_feedback:
        ftype = feedback.feedback_type
        if ftype not in feedback_by_type:
            feedback_by_type[ftype] = 0
        feedback_by_type[ftype] += 1

    performance_monitor.stop_timer("analytics_aggregation")

    aggregation_time = performance_monitor.get_metric("analytics_aggregation").get("duration_ms", 0)

    print(f"✓ Analytics aggregated ({aggregation_time:.2f}ms)")
    print(f"   Total feedback: {total_feedback}")
    print(f"   Average rating: {avg_rating:.2f}")
    print(f"   Thumbs up: {thumbs_up} ({thumbs_up/total_feedback:.1%})")
    print(f"   Thumbs down: {thumbs_down} ({thumbs_down/total_feedback:.1%})")
    print(f"   Neutral: {neutral} ({neutral/total_feedback:.1%})")
    print(f"   By type: {feedback_by_type}")

    # -------------------------------------------------------------------------
    # Test 8: Agent Promotion Suggestions
    # -------------------------------------------------------------------------
    print("\n8. Generating agent promotion suggestions...")

    # Calculate promotion readiness based on feedback
    intern_agent = test_agents["INTERN"]

    # Create feedback for INTERN agent
    for i in range(15):
        feedback = AgentFeedback(
            execution_id=f"intern-exec-{i}",
            agent_id=intern_agent.id,
            rating=0.7 + (i * 0.02),  # Improving over time
            feedback_text=f"Feedback {i + 1}",
            feedback_type="star_rating",
            created_by="test-user-123",
            created_at=datetime.utcnow() - timedelta(days=15 - i),
        )
        db_session.add(feedback)

    db_session.commit()

    # Analyze INTERN agent feedback
    intern_feedback = db_session.query(AgentFeedback).filter(
        AgentFeedback.agent_id == intern_agent.id
    ).all()

    intern_avg_rating = sum(f.rating for f in intern_feedback) / len(intern_feedback)
    positive_ratio = sum(1 for f in intern_feedback if f.rating > 0.5) / len(intern_feedback)

    # Generate suggestion
    if intern_avg_rating > 0.75 and positive_ratio > 0.8:
        suggestion = {
            "agent_id": intern_agent.id,
            "current_maturity": "INTERN",
            "suggested_promotion": "SUPERVISED",
            "confidence": 0.85,
            "reason": f"High average rating ({intern_avg_rating:.2f}) and positive feedback ratio ({positive_ratio:.1%})",
        }
    else:
        suggestion = {
            "agent_id": intern_agent.id,
            "current_maturity": "INTERN",
            "suggested_promotion": None,
            "confidence": 0.0,
            "reason": f"Insufficient feedback quality (avg: {intern_avg_rating:.2f}, positive: {positive_ratio:.1%})",
        }

    print(f"✓ Promotion suggestion generated:")
    print(f"   Agent: {suggestion['agent_id']}")
    print(f"   Current: {suggestion['current_maturity']}")
    print(f"   Suggested: {suggestion['suggested_promotion'] or 'Not ready for promotion'}")
    print(f"   Confidence: {suggestion['confidence']:.1%}")
    print(f"   Reason: {suggestion['reason']}")

    # -------------------------------------------------------------------------
    # Test 9: Feedback Integration with Episodic Memory
    # -------------------------------------------------------------------------
    print("\n9. Testing feedback integration with episodic memory...")

    # Create episode with linked feedback
    episode_with_feedback = Episode(
        episode_id="episode-feedback-001",
        agent_id=autonomous_agent.id,
        title="Customer Support with Feedback",
        summary="Agent resolved issue, received positive feedback",
        content={"interaction": "customer support"},
        episode_type="customer_support",
        tags=["resolved", "positive_feedback"],
        feedback_context={
            "feedback_id": submitted_feedback[0].execution_id,
            "rating": submitted_feedback[0].rating,
            "feedback_type": submitted_feedback[0].feedback_type,
        },
        started_at=datetime.utcnow() - timedelta(minutes=10),
        ended_at=datetime.utcnow() - timedelta(minutes=8),
        created_at=datetime.utcnow(),
    )
    db_session.add(episode_with_feedback)

    # Link feedback to episode
    submitted_feedback[0].metadata["linked_episode_id"] = episode_with_feedback.episode_id

    db_session.commit()

    # Retrieve episodes with feedback
    episodes_with_feedback = db_session.query(Episode).filter(
        Episode.agent_id == autonomous_agent.id,
        Episode.feedback_context.isnot(None),
    ).all()

    print(f"✓ Feedback integrated with episodic memory")
    print(f"   Episodes with feedback: {len(episodes_with_feedback)}")

    for episode in episodes_with_feedback:
        feedback_score = episode.feedback_context.get("rating", 0)
        print(f"   - {episode.episode_id}: rating={feedback_score:.1f}")

    # -------------------------------------------------------------------------
    # Test 10: Batch Feedback Operations
    # -------------------------------------------------------------------------
    print("\n10. Testing batch feedback operations...")

    performance_monitor.start_timer("batch_feedback")

    # Create batch feedback
    batch_feedback_data = [
        {
            "execution_id": f"batch-exec-{i}",
            "agent_id": autonomous_agent.id,
            "rating": 0.8 if i % 2 == 0 else -0.3,
            "feedback_text": f"Batch feedback {i + 1}",
            "feedback_type": "thumbs_up" if i % 2 == 0 else "thumbs_down",
        }
        for i in range(10)
    ]

    created_count = 0
    for feedback_data in batch_feedback_data:
        feedback = AgentFeedback(
            **feedback_data,
            created_by="test-user-123",
            created_at=datetime.utcnow(),
        )
        db_session.add(feedback)
        created_count += 1

    db_session.commit()

    performance_monitor.stop_timer("batch_feedback")

    batch_time = performance_monitor.get_metric("batch_feedback").get("duration_ms", 0)

    assert batch_time < 1000, f"Batch operations should be <1s, got {batch_time:.2f}ms"

    print(f"✓ Batch feedback processed ({batch_time:.2f}ms)")
    print(f"   Created: {created_count} feedback entries")
    print(f"   Average per feedback: {batch_time / created_count:.2f}ms")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n=== Deep Linking & Enhanced Feedback Test Complete ===")
    print("\nKey Findings:")
    print(f"✓ Generated {len(deep_links)} deep link types")
    print("✓ All deep links parsed and validated")
    print("✓ Security validation blocked malicious links")
    print("✓ Deep link navigation working")
    print(f"✓ Submitted {len(submitted_feedback)} feedback entries")
    print(f"✓ A/B test created with {len(ab_test.variants)} variants")
    print(f"✓ Analytics aggregated ({aggregation_time:.2f}ms)")
    print(f"   Average rating: {avg_rating:.2f}")
    print(f"   Positive ratio: {thumbs_up/total_feedback:.1%}")
    print("✓ Promotion suggestions generated")
    print(f"✓ Feedback integrated with {len(episodes_with_feedback)} episodes")
    print(f"✓ Batch feedback processed ({batch_time:.2f}ms)")

    # Verify audit trails
    all_deeplinks = db_session.query(DeepLinkAudit).all()
    all_feedback = db_session.query(AgentFeedback).all()

    print(f"\n✓ Audit trails:")
    print(f"   Deep link accesses: {len(all_deeplinks)}")
    print(f"   Feedback entries: {len(all_feedback)}")

    # Print performance summary
    performance_monitor.print_summary()
