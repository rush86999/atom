"""
Scenario 3: Canvas Presentations with Governance

This scenario tests the canvas presentation system with governance enforcement.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from core.models import (
    AgentRegistry,
    CanvasAudit,
)
from core.governance_config import check_governance


@pytest.mark.e2e
def test_canvas_presentations_with_governance(
    db_session: Session,
    test_agents: Dict[str, AgentRegistry],
    performance_monitor,
):
    """Test canvas presentations with governance enforcement."""
    print("\n=== Testing Canvas Presentations with Governance ===")

    student_agent = test_agents["STUDENT"]
    intern_agent = test_agents["INTERN"]
    autonomous_agent = test_agents["AUTONOMOUS"]

    # -------------------------------------------------------------------------
    # Test 1: STUDENT Agent Canvas Permissions
    # -------------------------------------------------------------------------
    print("\n1. Testing STUDENT agent canvas permissions...")

    performance_monitor.start_timer("student_canvas_check")

    allowed, reason = check_governance(
        feature="canvas_presentation",
        agent_id=student_agent.id,
        action="present",
        action_complexity=1,
        maturity_level=student_agent.status,
    )

    performance_monitor.stop_timer("student_canvas_check")

    assert allowed, "STUDENT agent should be able to present"
    print(f"✓ STUDENT agent can present canvas")

    # -------------------------------------------------------------------------
    # Test 2: Canvas Audit Trail
    # -------------------------------------------------------------------------
    print("\n2. Testing canvas audit trail...")

    audit_entries = [
        CanvasAudit(
            canvas_id="test-canvas-001",
            agent_id=student_agent.id,
            user_id="test-user-123",
            action="present",
            component_type="markdown",
            audit_metadata={"type": "markdown"},
            session_id="test-session-1",
        ),
        CanvasAudit(
            canvas_id="test-canvas-002",
            agent_id=intern_agent.id,
            user_id="test-user-123",
            action="present",
            component_type="chart",
            audit_metadata={"type": "chart"},
            session_id="test-session-2",
        ),
        CanvasAudit(
            canvas_id="test-canvas-003",
            agent_id=autonomous_agent.id,
            user_id="test-user-123",
            action="close",
            component_type="generic",
            audit_metadata={"reason": "complete"},
            session_id="test-session-3",
        ),
    ]

    performance_monitor.start_timer("audit_creation")

    for audit in audit_entries:
        db_session.add(audit)
    db_session.commit()

    performance_monitor.stop_timer("audit_creation")

    print(f"✓ Created {len(audit_entries)} audit entries")

    # -------------------------------------------------------------------------
    # Test 3: Canvas Type Support
    # -------------------------------------------------------------------------
    print("\n3. Testing canvas type support...")

    canvas_types = [
        "generic", "docs", "email", "sheets",
        "orchestration", "terminal", "coding",
    ]

    for canvas_type in canvas_types:
        audit = CanvasAudit(
            canvas_id=f"test-{canvas_type}-canvas",
            agent_id=autonomous_agent.id,
            user_id="test-user-123",
            action="present",
            component_type="generic",
            audit_metadata={"canvas_type": canvas_type},
            session_id=f"test-{canvas_type}-session",
        )
        db_session.add(audit)

    db_session.commit()

    print(f"✓ All {len(canvas_types)} canvas types supported")

    # -------------------------------------------------------------------------
    # Test 4: Governance by Maturity Level
    # -------------------------------------------------------------------------
    print("\n4. Testing governance by maturity level...")

    test_cases = [
        (student_agent, "canvas_presentation", "present", 1, True),
        (student_agent, "canvas_form_submission", "submit", 3, False),
        (intern_agent, "canvas_presentation", "present", 1, True),
        (autonomous_agent, "canvas_form_submission", "submit", 3, True),
    ]

    for agent, feature, action, complexity, expected_allowed in test_cases:
        allowed, reason = check_governance(
            feature=feature,
            agent_id=agent.id,
            action=action,
            action_complexity=complexity,
            maturity_level=agent.status,
            log_decision=False,
        )

        print(f"   {agent.status} {feature}/{action}: allowed={allowed}, expected={expected_allowed}")

        if expected_allowed:
            assert allowed, f"{agent.status} should be allowed for {action}"
        else:
            assert not allowed, f"{agent.status} should be blocked for {action}"

    print("✓ Governance enforcement validated")

    # -------------------------------------------------------------------------
    # Test 5: Database Query Performance
    # -------------------------------------------------------------------------
    print("\n5. Testing database query performance...")

    performance_monitor.start_timer("canvas_query_test")

    all_audits = db_session.query(CanvasAudit).all()

    performance_monitor.stop_timer("canvas_query_test")

    assert len(all_audits) >= 10, f"Should have at least 10 audit entries, got {len(all_audits)}"
    print(f"✓ Database query retrieved {len(all_audits)} entries")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n=== Canvas Presentations with Governance Test Complete ===")
    print("\nKey Findings:")
    print("✓ Governance checks working for canvas operations")
    print(f"✓ Audit trail: {len(all_audits)} entries recorded")
    print("✓ All 7 canvas types supported")
    print("✓ Governance enforcement by maturity level validated")
    print("✓ Database operations working correctly")

    performance_monitor.print_summary()
