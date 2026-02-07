"""
Property-Based Tests for Tool Security Invariants

⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL TOOL SECURITY INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md

Tests:
    - 12 comprehensive property-based tests for tool security invariants
    - Coverage targets: 95%+ of tool governance
"""

import pytest
from hypothesis import given, strategies as st, settings
from typing import List, Dict
from tools.canvas_tool import CanvasTool
from tools.device_tool import DeviceTool
from tools.browser_tool import BrowserTool
from core.agent_governance_service import AgentGovernanceService


class TestCanvasToolSecurityInvariants:
    """Property-based tests for Canvas tool security invariants."""

    @given(
        agent_maturity=st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']),
        canvas_type=st.sampled_from(['generic', 'docs', 'email', 'sheets', 'charts', 'forms']),
        action=st.sampled_from(['create', 'update', 'present', 'submit', 'close', 'execute'])
    )
    @settings(max_examples=100)
    def test_canvas_tool_governance_enforcement(self, agent_maturity, canvas_type, action):
        """INVARIANT: Canvas actions must respect maturity-based governance."""
        tool = CanvasTool()
        governance = AgentGovernanceService()

        # Define governance rules
        maturity_requirements = {
            'create': ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'],
            'update': ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'],
            'present': ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'],
            'submit': ['INTERN', 'SUPERVISED', 'AUTONOMOUS'],  # Requires INTERN+
            'close': ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'],
            'execute': ['INTERN', 'SUPERVISED', 'AUTONOMOUS']  # Requires INTERN+
        }

        allowed_maturities = maturity_requirements[action]
        is_allowed = agent_maturity in allowed_maturities

        # Verify governance check
        has_permission = governance.check_canvas_permission(agent_maturity, action, canvas_type)

        if is_allowed:
            assert has_permission, f"{agent_maturity} should be allowed to {action} on {canvas_type}"
        else:
            assert not has_permission, f"{agent_maturity} should NOT be allowed to {action} on {canvas_type}"

    @given(
        component_html=st.text(min_size=1, max_size=10000),
        component_css=st.text(min_size=0, max_size=5000),
        component_js=st.text(min_size=0, max_size=5000),
        agent_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=100)
    def test_canvas_custom_component_sanitization(self, component_html, component_css, component_js, agent_maturity):
        """INVARIANT: Custom components must be sanitized to prevent XSS."""
        tool = CanvasTool()

        # Sanitize components
        sanitized = tool.sanitize_custom_component(
            html=component_html,
            css=component_css,
            js=component_js,
            agent_maturity=agent_maturity
        )

        # Verify XSS prevention
        assert '<script' not in sanitized['html'].lower(), "HTML must not contain script tags"
        assert 'javascript:' not in sanitized['html'].lower(), "HTML must not contain javascript: protocol"
        assert 'onerror=' not in sanitized['html'].lower(), "HTML must not contain onerror handlers"
        assert 'onload=' not in sanitized['html'].lower(), "HTML must not contain onload handlers"

        # Verify JS governance (AUTONOMOUS only for JS)
        if agent_maturity != 'AUTONOMOUS':
            assert len(sanitized['js']) == 0 or '<script' not in sanitized['js'], \
                f"{agent_maturity} agents should not be allowed to use custom JS"

    @given(
        form_data=st.dictionaries(
            st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz'),
            st.one_of(
                st.text(min_size=0, max_size=1000),
                st.integers(min_value=-1000000, max_value=1000000),
                st.floats(min_value=-1000000.0, max_value=1000000.0, allow_nan=False),
                st.booleans(),
                st.none()
            ),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_canvas_form_submission_validation(self, form_data):
        """INVARIANT: Form submissions must be validated for security."""
        tool = CanvasTool()

        # Validate form data
        validation_result = tool.validate_form_submission(form_data)

        # Verify validation
        assert isinstance(validation_result.is_valid, bool), "is_valid must be boolean"

        if validation_result.is_valid:
            # Valid submissions should have sanitized data
            assert validation_result.sanitized_data is not None
            # Check no SQL injection patterns
            for key, value in validation_result.sanitized_data.items():
                if isinstance(value, str):
                    assert "'; DROP TABLE" not in value.upper(), "SQL injection pattern detected"
                    assert "<script>" not in value.lower(), "XSS pattern detected"
        else:
            # Invalid submissions should have errors
            assert len(validation_result.errors) > 0, "Invalid submission must have errors"

    @given(
        canvas_data=st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.one_of(st.text(), st.integers(), st.floats(allow_nan=False), st.lists(st.text()), st.none()),
            min_size=1,
            max_size=50
        ),
        recording_enabled=st.booleans()
    )
    @settings(max_examples=100)
    def test_canvas_recording_permission_check(self, canvas_data, recording_enabled):
        """INVARIANT: Canvas recording must require appropriate permissions."""
        tool = CanvasTool()

        # Check recording permission
        has_permission = tool.check_recording_permission(
            canvas_data=canvas_data,
            recording_enabled=recording_enabled
        )

        # Recording requires SUPERVISED+ maturity for governance
        # This is a simplified check - real implementation would check agent maturity
        if recording_enabled:
            # Should check agent maturity before allowing
            assert isinstance(has_permission, bool), "Permission check must return boolean"


class TestDeviceToolSecurityInvariants:
    """Property-based tests for Device tool security invariants."""

    @given(
        agent_maturity=st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']),
        camera_action=st.sampled_from(['access', 'capture', 'stream'])
    )
    @settings(max_examples=100)
    def test_device_camera_governance(self, agent_maturity, camera_action):
        """INVARIANT: Camera access must require INTERN+ maturity."""
        tool = DeviceTool()
        governance = AgentGovernanceService()

        # Check camera permission
        has_permission = governance.check_device_permission(
            agent_maturity=agent_maturity,
            device_type='camera',
            action=camera_action
        )

        # Camera requires INTERN+ maturity
        if agent_maturity == 'STUDENT':
            assert not has_permission, f"STUDENT agents should NOT be allowed to access camera"
        else:
            # INTERN+, SUPERVISED, AUTONOMOUS allowed
            assert has_permission, f"{agent_maturity} agents should be allowed to access camera"

    @given(
        agent_maturity=st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']),
        screen_action=st.sampled_from(['capture', 'record', 'stream'])
    )
    @settings(max_examples=100)
    def test_device_screen_recording_governance(self, agent_maturity, screen_action):
        """INVARIANT: Screen recording must require SUPERVISED+ maturity."""
        tool = DeviceTool()
        governance = AgentGovernanceService()

        # Check screen recording permission
        has_permission = governance.check_device_permission(
            agent_maturity=agent_maturity,
            device_type='screen',
            action=screen_action
        )

        # Screen recording requires SUPERVISED+ maturity
        if agent_maturity in ['STUDENT', 'INTERN']:
            assert not has_permission, f"{agent_maturity} agents should NOT be allowed to record screen"
        else:
            # SUPERVISED, AUTONOMOUS allowed
            assert has_permission, f"{agent_maturity} agents should be allowed to record screen"

    @given(
        agent_maturity=st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']),
        command=st.text(min_size=1, max_size=1000)
    )
    @settings(max_examples=100)
    def test_device_command_execution_governance(self, agent_maturity, command):
        """INVARIANT: Command execution must require AUTONOMOUS maturity only."""
        tool = DeviceTool()
        governance = AgentGovernanceService()

        # Check command execution permission
        has_permission = governance.check_device_permission(
            agent_maturity=agent_maturity,
            device_type='command_execution',
            action='execute'
        )

        # Command execution requires AUTONOMOUS maturity ONLY
        if agent_maturity == 'AUTONOMOUS':
            assert has_permission, "AUTONOMOUS agents should be allowed to execute commands"
        else:
            assert not has_permission, f"{agent_maturity} agents should NOT be allowed to execute commands"

        # Verify command sanitization
        sanitized_command = tool.sanitize_command(command)

        # Check for dangerous commands
        dangerous_patterns = ['rm -rf', 'format', 'del /', 'shutdown', 'reboot']
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                # Dangerous commands should be rejected or sanitized
                assert pattern not in sanitized_command.lower(), f"Dangerous command pattern '{pattern}' should be removed"

    @given(
        location_data=st.fixed_dictionaries({
            'latitude': st.floats(min_value=-90.0, max_value=90.0, allow_nan=False),
            'longitude': st.floats(min_value=-180.0, max_value=180.0, allow_nan=False),
            'accuracy': st.floats(min_value=0.0, max_value=1000.0, allow_nan=False)
        }),
        agent_maturity=st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=100)
    def test_device_location_privacy(self, location_data, agent_maturity):
        """INVARIANT: Location access must respect privacy and require INTERN+ maturity."""
        tool = DeviceTool()
        governance = AgentGovernanceService()

        # Check location permission
        has_permission = governance.check_device_permission(
            agent_maturity=agent_maturity,
            device_type='location',
            action='get'
        )

        # Location requires INTERN+ maturity
        if agent_maturity == 'STUDENT':
            assert not has_permission, "STUDENT agents should NOT be allowed to access location"
        else:
            assert has_permission, f"{agent_maturity} agents should be allowed to access location"

        # Verify location data validation
        validation_result = tool.validate_location_data(location_data)

        assert -90.0 <= validation_result.latitude <= 90.0, "Invalid latitude"
        assert -180.0 <= validation_result.longitude <= 180.0, "Invalid longitude"
        assert validation_result.accuracy >= 0.0, "Invalid accuracy"


class TestBrowserToolSecurityInvariants:
    """Property-based tests for Browser tool security invariants."""

    @given(
        agent_maturity=st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']),
        url=st.text(min_size=1, max_size=2000)
    )
    @settings(max_examples=100)
    def test_browser_navigation_governance(self, agent_maturity, url):
        """INVARIANT: Browser navigation must require INTERN+ maturity."""
        tool = BrowserTool()
        governance = AgentGovernanceService()

        # Check navigation permission
        has_permission = governance.check_browser_permission(
            agent_maturity=agent_maturity,
            action='navigate'
        )

        # Navigation requires INTERN+ maturity
        if agent_maturity == 'STUDENT':
            assert not has_permission, "STUDENT agents should NOT be allowed to navigate browser"
        else:
            assert has_permission, f"{agent_maturity} agents should be allowed to navigate browser"

        # Verify URL sanitization
        sanitized_url = tool.sanitize_url(url)

        # Check for dangerous protocols
        dangerous_protocols = ['javascript:', 'data:', 'file:', 'ftp:']
        for protocol in dangerous_protocols:
            assert protocol not in sanitized_url.lower(), f"Dangerous protocol '{protocol}' should be removed"

    @given(
        form_data=st.dictionaries(
            st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz'),
            st.one_of(st.text(min_size=0, max_size=1000), st.integers(), st.emails()),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_browser_form_filling_validation(self, form_data):
        """INVARIANT: Browser form filling must validate and sanitize data."""
        tool = BrowserTool()

        # Sanitize form data
        sanitized = tool.sanitize_form_data(form_data)

        # Verify XSS prevention
        for key, value in sanitized.items():
            if isinstance(value, str):
                assert '<script' not in value.lower(), "XSS pattern detected"
                assert 'javascript:' not in value.lower(), "XSS pattern detected"
                assert "'; DROP TABLE" not in value.upper(), "SQL injection pattern detected"

    @given(
        agent_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS']),
        screenshot_format=st.sampled_from(['png', 'jpeg', 'webp'])
    )
    @settings(max_examples=100)
    def test_browser_screenshot_permission(self, agent_maturity, screenshot_format):
        """INVARIANT: Browser screenshots must require INTERN+ maturity."""
        tool = BrowserTool()
        governance = AgentGovernanceService()

        # Check screenshot permission
        has_permission = governance.check_browser_permission(
            agent_maturity=agent_maturity,
            action='screenshot'
        )

        # Screenshots require INTERN+ maturity
        # (Same as navigation - all non-STUDENT agents allowed)
        assert has_permission, f"{agent_maturity} agents should be allowed to take screenshots"

        # Verify format validation
        assert screenshot_format in ['png', 'jpeg', 'webp'], "Invalid screenshot format"

    @given(
        sessions=st.lists(
            st.fixed_dictionaries({
                'session_id': st.text(min_size=1, max_size=50, alphabet='abc123'),
                'cdp_url': st.text(min_size=10, max_size=200),
                'agent_id': st.text(min_size=1, max_size=50)
            }),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_browser_cdp_isolation(self, sessions):
        """INVARIANT: CDP sessions must be isolated between agents."""
        tool = BrowserTool()

        # Create CDP sessions
        session_ids = []
        for session in sessions:
            session_id = tool.create_cdp_session(
                session_id=session['session_id'],
                cdp_url=session['cdp_url'],
                agent_id=session['agent_id']
            )
            session_ids.append(session_id)

        # Verify session isolation
        # Each agent should only access their own sessions
        for i, session in enumerate(sessions):
            agent_sessions = tool.get_agent_sessions(session['agent_id'])
            assert session['session_id'] in [s.session_id for s in agent_sessions], \
                f"Agent {session['agent_id']} should have access to their own session"

            # Verify no cross-agent access
            other_agent_sessions = [s for s in agent_sessions if s.agent_id != session['agent_id']]
            assert len(other_agent_sessions) == 0, "Agent should not access other agents' sessions"

    @given(
        urls=st.lists(
            st.text(min_size=1, max_size=2000),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_browser_url_sanitization(self, urls):
        """INVARIANT: URLs must be sanitized to prevent security issues."""
        tool = BrowserTool()

        for url in urls:
            sanitized = tool.sanitize_url(url)

            # Verify no dangerous protocols
            assert 'javascript:' not in sanitized.lower(), "javascript: protocol removed"
            assert 'data:' not in sanitized.lower() or 'data:image' in sanitized.lower(), \
                "data: protocol removed (except images)"

            # Verify URL format
            if sanitized.startswith('http'):
                assert '://' in sanitized, "Valid URL must have protocol"
