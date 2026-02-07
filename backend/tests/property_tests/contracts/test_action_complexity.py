"""
⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus


class TestActionComplexityMatrix:
    """Test action complexity matrix business rules."""

    @pytest.mark.parametrize("agent_status", [
        AgentStatus.STUDENT, AgentStatus.INTERN,
        AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS
    ])
    def test_complexity_1_allows_student_plus(
        self, db_session: Session, agent_status: AgentStatus
    ):
        """
        BUSINESS RULE: Complexity 1 (LOW) actions MUST be allowed by ALL agents.

        LOW complexity actions: search, read, list, get, fetch, summarize,
        present_chart, present_markdown
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status.value,
            confidence_score=0.5,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Complexity 1 actions
        complexity_1_actions = [
            "search",
            "read",
            "list",
            "get",
            "fetch",
            "summarize",
            "present_chart",
            "present_markdown"
        ]

        # Act & Assert
        for action in complexity_1_actions:
            decision = service.can_perform_action(agent.id, action)

            assert decision["allowed"] is True, \
                f"{agent_status.value} should be allowed to perform {action} (complexity 1)"

    def test_complexity_2_allows_intern_plus(
        self, db_session: Session
    ):
        """
        BUSINESS RULE: Complexity 2 (MODERATE) actions MUST be allowed by INTERN+.

        MODERATE complexity actions: stream_chat, present_form, llm_stream,
        browser_navigate, browser_screenshot, browser_extract, device_camera_snap,
        device_get_location, device_send_notification, update_canvas
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        # Test INTERN, SUPERVISED, AUTONOMOUS
        allowed_statuses = [
            AgentStatus.INTERN,
            AgentStatus.SUPERVISED,
            AgentStatus.AUTONOMOUS
        ]

        # Complexity 2 actions
        complexity_2_actions = [
            "stream_chat",
            "present_form",
            "llm_stream",
            "browser_navigate",
            "browser_screenshot",
            "browser_extract",
            "device_camera_snap",
            "device_get_location",
            "device_send_notification",
            "update_canvas"
        ]

        for agent_status in allowed_statuses:
            agent = AgentRegistry(
                name=f"TestAgent_{agent_status.value}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=agent_status.value,
                confidence_score=0.5,
                
            )
            db_session.add(agent)
            db_session.commit()
            db_session.refresh(agent)

            for action in complexity_2_actions:
                decision = service.can_perform_action(agent.id, action)

                assert decision["allowed"] is True, \
                    f"{agent_status.value} should be allowed to perform {action} (complexity 2)"

    def test_complexity_2_denies_student(
        self, db_session: Session
    ):
        """
        BUSINESS RULE: Complexity 2 (MODERATE) actions MUST be denied to STUDENT.

        STUDENT agents lack maturity for LLM streaming and device operations.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Complexity 2 actions
        complexity_2_actions = [
            "stream_chat",
            "present_form",
            "llm_stream",
            "browser_navigate"
        ]

        # Act & Assert
        for action in complexity_2_actions:
            decision = service.can_perform_action(agent.id, action)

            assert decision["allowed"] is False, \
                f"STUDENT should NOT be allowed to perform {action} (complexity 2)"

    def test_complexity_3_allows_supervised_plus(
        self, db_session: Session
    ):
        """
        BUSINESS RULE: Complexity 3 (HIGH) actions MUST be allowed by SUPERVISED+.

        HIGH complexity actions: create, update, send_email, post_message,
        schedule, submit_form, device_screen_record*
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        # Test SUPERVISED and AUTONOMOUS
        allowed_statuses = [
            AgentStatus.SUPERVISED,
            AgentStatus.AUTONOMOUS
        ]

        # Complexity 3 actions
        complexity_3_actions = [
            "create",
            "update",
            "send_email",
            "post_message",
            "schedule",
            "submit_form",
            "device_screen_record",
            "device_screen_record_start",
            "device_screen_record_stop"
        ]

        for agent_status in allowed_statuses:
            agent = AgentRegistry(
                name=f"TestAgent_{agent_status.value}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=agent_status.value,
                confidence_score=0.5,
                
            )
            db_session.add(agent)
            db_session.commit()
            db_session.refresh(agent)

            for action in complexity_3_actions:
                decision = service.can_perform_action(agent.id, action)

                assert decision["allowed"] is True, \
                    f"{agent_status.value} should be allowed to perform {action} (complexity 3)"

    def test_complexity_3_denies_student_and_intern(
        self, db_session: Session
    ):
        """
        BUSINESS RULE: Complexity 3 (HIGH) actions MUST be denied to STUDENT and INTERN.

        State-changing operations require SUPERVISED maturity.
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        denied_statuses = [
            AgentStatus.STUDENT,
            AgentStatus.INTERN
        ]

        # Complexity 3 actions
        complexity_3_actions = [
            "create",
            "update",
            "submit_form"
        ]

        for agent_status in denied_statuses:
            agent = AgentRegistry(
                name=f"TestAgent_{agent_status.value}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=agent_status.value,
                confidence_score=0.5,
                
            )
            db_session.add(agent)
            db_session.commit()
            db_session.refresh(agent)

            for action in complexity_3_actions:
                decision = service.can_perform_action(agent.id, action)

                assert decision["allowed"] is False, \
                    f"{agent_status.value} should NOT be allowed to perform {action} (complexity 3)"

    def test_complexity_4_allows_autonomous_only(
        self, db_session: Session
    ):
        """
        BUSINESS RULE: Complexity 4 (CRITICAL) actions MUST be allowed by AUTONOMOUS only.

        CRITICAL complexity actions: delete, execute, deploy, transfer, payment,
        approve, device_execute_command, canvas_execute_javascript
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        # Only AUTONOMOUS should be allowed
        agent = AgentRegistry(
            name="TestAgent_Autonomous",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Complexity 4 actions
        complexity_4_actions = [
            "delete",
            "execute",
            "deploy",
            "transfer",
            "payment",
            "approve",
            "device_execute_command",
            "canvas_execute_javascript"
        ]

        # Act & Assert
        for action in complexity_4_actions:
            decision = service.can_perform_action(agent.id, action)

            assert decision["allowed"] is True, \
                f"AUTONOMOUS should be allowed to perform {action} (complexity 4)"

    def test_complexity_4_denies_non_autonomous(
        self, db_session: Session
    ):
        """
        BUSINESS RULE: Complexity 4 (CRITICAL) actions MUST be denied to non-AUTONOMOUS.

        Only AUTONOMOUS agents can perform critical operations.
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        denied_statuses = [
            AgentStatus.STUDENT,
            AgentStatus.INTERN,
            AgentStatus.SUPERVISED
        ]

        # Complexity 4 actions
        complexity_4_actions = [
            "delete",
            "execute",
            "deploy"
        ]

        for agent_status in denied_statuses:
            agent = AgentRegistry(
                name=f"TestAgent_{agent_status.value}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=agent_status.value,
                confidence_score=0.5,
                
            )
            db_session.add(agent)
            db_session.commit()
            db_session.refresh(agent)

            for action in complexity_4_actions:
                decision = service.can_perform_action(agent.id, action)

                assert decision["allowed"] is False, \
                    f"{agent_status.value} should NOT be allowed to perform {action} (complexity 4)"

    @given(
        unknown_action=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() and not any(
            known in x.lower() for known in [
                "search", "read", "list", "get", "fetch", "summarize", "present_chart",
                "present_markdown", "analyze", "suggest", "draft", "generate", "recommend",
                "stream_chat", "present_form", "llm_stream", "browser_navigate",
                "browser_screenshot", "browser_extract", "device_camera_snap",
                "device_get_location", "device_send_notification", "update_canvas",
                "create", "update", "delete", "execute", "deploy", "submit",
                "approve", "reject", "cancel"
            ]
        ))
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unknown_actions_have_safe_defaults(
        self, db_session: Session, unknown_action: str
    ):
        """
        BUSINESS RULE: Unknown actions MUST have safe default complexity (2 = INTERN+).

        When an action is not explicitly mapped, system should default to MODERATE complexity.
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        # Student agent (should be denied unknown actions)
        student = AgentRegistry(
            name="StudentAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            
        )
        db_session.add(student)
        db_session.commit()
        db_session.refresh(student)

        # Intern agent (should be allowed unknown actions)
        intern = AgentRegistry(
            name="InternAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.5,
            
        )
        db_session.add(intern)
        db_session.commit()
        db_session.refresh(intern)

        # Act: Check permissions for unknown action
        student_decision = service.can_perform_action(student.id, unknown_action)
        intern_decision = service.can_perform_action(intern.id, unknown_action)

        # Assert: Safe default - STUDENT denied, INTERN allowed
        # (Default complexity 2 requires INTERN+)
        assert student_decision["allowed"] is False, \
            f"STUDENT should be denied unknown action {unknown_action}"
        assert intern_decision["allowed"] is True, \
            f"INTERN should be allowed unknown action {unknown_action}"
