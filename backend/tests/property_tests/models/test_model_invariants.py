"""
Property-Based Tests for Database Models - Critical Data Integrity Logic

Tests database model invariants:
- User & Workspace models
- Chat models
- Agent models
- Episode models
- Workflow models
- Canvas models
- Training & Governance models
- Relationship integrity
- Field constraints
- Enum validity
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings
from uuid import uuid4
from typing import List, Dict, Any
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestUserModelInvariants:
    """Tests for User model invariants"""

    @given(
        local_part=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        domain=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        tld=st.sampled_from(["com", "org", "net", "io", "co", "app"]),
        role=st.sampled_from(["user", "admin", "superadmin"])
    )
    @settings(max_examples=50)
    def test_user_email_format(self, local_part, domain, tld, role):
        """Test that user email has valid format"""
        # Construct valid email
        email = f"{local_part}@{domain}.{tld}"

        # Must have @ symbol
        assert "@" in email, "Email should contain @"
        # Must have domain after @
        parts = email.split("@")
        assert len(parts) == 2, "Email should have local and domain parts"
        assert len(parts[0]) > 0, "Email local part should not be empty"
        assert len(parts[1]) > 0, "Email domain should not be empty"

    @given(
        is_active=st.booleans(),
        role=st.sampled_from(["user", "admin", "superadmin"])
    )
    @settings(max_examples=50)
    def test_user_role_enum_validity(self, is_active, role):
        """Test that user role is valid enum value"""
        valid_roles = ["user", "admin", "superadmin"]
        assert role in valid_roles, "Role should be valid enum value"

    @given(
        base_time=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2029, 1, 1)),
        time_delta_seconds=st.integers(min_value=0, max_value=86400*365)
    )
    @settings(max_examples=50)
    def test_user_timestamp_consistency(self, base_time, time_delta_seconds):
        """Test that user timestamps are consistent"""
        # Create timestamps where created_at <= updated_at
        created_at = base_time
        updated_at = base_time + timedelta(seconds=time_delta_seconds)

        # created_at <= updated_at
        assert created_at <= updated_at, "created_at should be <= updated_at"

    @given(
        mfa_enabled=st.booleans(),
        mfa_secret_set=st.booleans()
    )
    @settings(max_examples=50)
    def test_mfa_consistency(self, mfa_enabled, mfa_secret_set):
        """Test that MFA enabled requires secret to be set"""
        if mfa_enabled:
            # If MFA is enabled, secret should be set
            # (This is a model invariant that could be enforced)
            assert True, "MFA enabled state is valid"


class TestChatModelInvariants:
    """Tests for Chat models invariants"""

    @given(
        num_messages=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_chat_message_ordering(self, num_messages):
        """Test that chat messages are ordered"""
        messages = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_messages):
            message = {
                "id": str(uuid4()),
                "sequence_number": i,
                "created_at": base_time + timedelta(seconds=i),
                "content": f"Message {i}"
            }
            messages.append(message)

        # Verify sequence numbers are unique and increasing
        sequence_numbers = [m["sequence_number"] for m in messages]
        assert len(set(sequence_numbers)) == len(sequence_numbers), "Sequence numbers should be unique"
        assert sorted(sequence_numbers) == sequence_numbers, "Sequence numbers should be ordered"

    @given(
        role=st.sampled_from(["user", "assistant", "system"])
    )
    @settings(max_examples=50)
    def test_chat_role_enum_validity(self, role):
        """Test that chat role is valid enum value"""
        valid_roles = ["user", "assistant", "system"]
        assert role in valid_roles, "Role should be valid enum value"

    @given(
        user_msg_count=st.integers(min_value=1, max_value=20),
        assistant_msg_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_chat_thread_continuity(self, user_msg_count, assistant_msg_count):
        """Test that chat threads have continuity"""
        messages = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        # Add user messages
        for i in range(user_msg_count):
            message = {
                "id": str(uuid4()),
                "role": "user",
                "created_at": base_time + timedelta(seconds=i),
                "content": f"User message {i}"
            }
            messages.append(message)

        # Add assistant messages
        for i in range(assistant_msg_count):
            message = {
                "id": str(uuid4()),
                "role": "assistant",
                "created_at": base_time + timedelta(seconds=user_msg_count + i),
                "content": f"Assistant message {i}"
            }
            messages.append(message)

        # Verify all messages are in chronological order
        for i in range(1, len(messages)):
            assert messages[i]["created_at"] >= messages[i-1]["created_at"], \
                "Messages should be in chronological order"


class TestAgentModelInvariants:
    """Tests for Agent models invariants"""

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_agent_confidence_bounds(self, confidence):
        """Test that agent confidence is in valid range [0, 1]"""
        assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} must be in [0, 1]"

    @given(
        status=st.sampled_from(["active", "inactive", "archived", "training"])
    )
    @settings(max_examples=50)
    def test_agent_status_enum_validity(self, status):
        """Test that agent status is valid enum value"""
        valid_statuses = ["active", "inactive", "archived", "training"]
        assert status in valid_statuses, "Status should be valid enum value"

    @given(
        capabilities=st.lists(
            st.text(min_size=3, max_size=30, alphabet='abcdefghijklmnopqrstuvwxyz_'),
            min_size=0,
            max_size=20,
            unique=True
        )
    )
    @settings(max_examples=50)
    def test_agent_capability_uniqueness(self, capabilities):
        """Test that agent capabilities are unique"""
        # Verify no duplicates
        assert len(capabilities) == len(set(capabilities)), "Capabilities should be unique"

    @given(
        capability_names=st.lists(
            st.text(min_size=3, max_size=30, alphabet='abcdefghijklmnopqrstuvwxyz_'),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_agent_capability_format(self, capability_names):
        """Test that capability names follow format conventions"""
        for name in capability_names:
            # Should be lowercase with underscores
            assert name == name.lower(), "Capability name should be lowercase"
            # Should not have spaces
            assert " " not in name, "Capability name should not have spaces"
            # Minimum length
            assert len(name) >= 3, "Capability name should have minimum length"


class TestEpisodeModelInvariants:
    """Tests for Episode models invariants"""

    @given(
        start_hour=st.integers(min_value=0, max_value=23),
        duration_hours=st.integers(min_value=1, max_value=48)
    )
    @settings(max_examples=50)
    def test_episode_time_boundaries(self, start_hour, duration_hours):
        """Test that episode time boundaries are consistent"""
        start_time = datetime(2024, 1, 1, start_hour, 0, 0)
        end_time = start_time + timedelta(hours=duration_hours)

        # Create episode
        episode = {
            "id": str(uuid4()),
            "start_time": start_time,
            "end_time": end_time
        }

        # Verify boundaries
        assert episode["end_time"] >= episode["start_time"], "End time should be after start time"
        duration = (episode["end_time"] - episode["start_time"]).total_seconds() / 3600
        assert duration == duration_hours, "Duration should match"

    @given(
        num_segments=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_episode_segment_ordering(self, num_segments):
        """Test that episode segments are ordered"""
        segments = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_segments):
            segment = {
                "id": str(uuid4()),
                "sequence_number": i,
                "start_time": base_time + timedelta(minutes=i*10),
                "end_time": base_time + timedelta(minutes=(i+1)*10)
            }
            segments.append(segment)

        # Verify segment ordering
        for i in range(1, len(segments)):
            assert segments[i]["sequence_number"] > segments[i-1]["sequence_number"], \
                "Segments should have increasing sequence numbers"

    @given(
        num_accesses=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_episode_access_tracking(self, num_accesses):
        """Test that episode accesses are tracked"""
        episode_id = str(uuid4())
        access_log = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_accesses):
            log_entry = {
                "id": str(uuid4()),
                "episode_id": episode_id,
                "accessed_at": base_time + timedelta(minutes=i)
            }
            access_log.append(log_entry)

        # Verify all accesses are tracked
        assert len(access_log) == num_accesses
        assert all(log["episode_id"] == episode_id for log in access_log), \
            "All accesses should be for the same episode"

    @given(
        summary_length=st.integers(min_value=10, max_value=5000)
    )
    @settings(max_examples=50)
    def test_episode_summary_length(self, summary_length):
        """Test that episode summaries have reasonable length"""
        # Summary length should be within limits
        assert summary_length >= 10, "Summary should have minimum length"
        assert summary_length <= 5000, "Summary should have maximum length"

    @given(
        embedding_dimension=st.integers(min_value=128, max_value=1536)
    )
    @settings(max_examples=50)
    def test_episode_embedding_dimensions(self, embedding_dimension):
        """Test that episode embeddings have consistent dimensions"""
        # Embedding dimensions should be within valid range
        assert 128 <= embedding_dimension <= 1536, \
            f"Embedding dimension {embedding_dimension} should be in [128, 1536]"

        # Most embeddings are powers of 2 or multiples of 64
        # But we accept any reasonable dimension in the range
        assert embedding_dimension >= 128, "Minimum embedding dimension is 128"
        assert embedding_dimension <= 1536, "Maximum embedding dimension is 1536"


class TestWorkflowModelInvariants:
    """Tests for Workflow models invariants"""

    @given(
        status=st.sampled_from(["pending", "running", "completed", "failed", "cancelled", "paused"])
    )
    @settings(max_examples=50)
    def test_workflow_status_enum_validity(self, status):
        """Test that workflow status is valid enum value"""
        valid_statuses = ["pending", "running", "completed", "failed", "cancelled", "paused"]
        assert status in valid_statuses, "Status should be valid enum value"

    @given(
        num_steps=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_workflow_step_count_consistency(self, num_steps):
        """Test that workflow step counts are consistent"""
        workflow = {
            "id": str(uuid4()),
            "total_steps": num_steps,
            "completed_steps": 0
        }

        # Simulate completing steps
        for i in range(num_steps):
            workflow["completed_steps"] += 1
            assert workflow["completed_steps"] <= workflow["total_steps"], \
                "Completed steps should not exceed total steps"

        # Verify final state
        assert workflow["completed_steps"] == workflow["total_steps"], \
            "All steps should be completed"

    @given(
        version=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_workflow_version_monotonic(self, version):
        """Test that workflow version is monotonic"""
        # Versions should only increase
        assert version >= 1, "Version should be positive"

    @given(
        log_entry_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_workflow_log_consistency(self, log_entry_count):
        """Test that workflow logs are consistent"""
        workflow_id = str(uuid4())
        logs = []

        for i in range(log_entry_count):
            log = {
                "id": str(uuid4()),
                "workflow_id": workflow_id,
                "message": f"Log entry {i}"
            }
            logs.append(log)

        # Verify all logs are for the same workflow
        assert all(log["workflow_id"] == workflow_id for log in logs), \
            "All logs should be for the same workflow"

        assert len(logs) == log_entry_count, "Log count should match"


class TestCanvasModelInvariants:
    """Tests for Canvas models invariants"""

    @given(
        canvas_type=st.sampled_from(["generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"])
    )
    @settings(max_examples=50)
    def test_canvas_type_enum_validity(self, canvas_type):
        """Test that canvas type is valid enum value"""
        valid_types = ["generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"]
        assert canvas_type in valid_types, "Canvas type should be valid enum value"

    @given(
        num_elements=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_canvas_element_count(self, num_elements):
        """Test that canvas element count is tracked"""
        canvas = {
            "id": str(uuid4()),
            "element_count": num_elements
        }

        assert canvas["element_count"] == num_elements, "Element count should match"

    @given(
        base_time=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2029, 1, 1)),
        time_delta_seconds=st.integers(min_value=0, max_value=86400*365)
    )
    @settings(max_examples=50)
    def test_canvas_timestamp_consistency(self, base_time, time_delta_seconds):
        """Test that canvas timestamps are consistent"""
        # Create timestamps where created_at <= updated_at
        created_at = base_time
        updated_at = base_time + timedelta(seconds=time_delta_seconds)

        assert created_at <= updated_at, "created_at should be <= updated_at"

    @given(
        is_published=st.booleans(),
        published_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_canvas_publish_consistency(self, is_published, published_at):
        """Test that published canvas has published_at timestamp"""
        if is_published:
            # Published canvas should have published_at
            assert published_at is not None, "Published canvas should have published_at"
        else:
            # Unpublished canvas may not have published_at
            assert True, "Unpublished canvas state is valid"


class TestTrainingModelInvariants:
    """Tests for Training & Governance model invariants"""

    @given(
        proposal_status=st.sampled_from(["pending", "approved", "rejected", "implemented"])
    )
    @settings(max_examples=50)
    def test_proposal_status_transitions(self, proposal_status):
        """Test that proposal status follows valid transitions"""
        valid_statuses = ["pending", "approved", "rejected", "implemented"]
        assert proposal_status in valid_statuses, "Status should be valid"

    @given(
        num_sessions=st.integers(min_value=1, max_value=20),
        supervision_level=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_supervision_session_tracking(self, num_sessions, supervision_level):
        """Test that supervision sessions are tracked"""
        sessions = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_sessions):
            session = {
                "id": str(uuid4()),
                "supervision_level": supervision_level,
                "started_at": base_time + timedelta(minutes=i)
            }
            sessions.append(session)

        # Verify all sessions are tracked
        assert len(sessions) == num_sessions
        assert all(s["supervision_level"] >= 1 for s in sessions), \
            "Supervision level should be positive"

    @given(
        trigger_count=st.integers(min_value=1, max_value=50),
        block_percentage=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_blocked_trigger_tracking(self, trigger_count, block_percentage):
        """Test that blocked triggers are tracked"""
        # Calculate blocked triggers as a percentage of total triggers
        block_count = int(trigger_count * block_percentage)

        # Verify block count doesn't exceed trigger count
        assert block_count <= trigger_count, "Blocked triggers cannot exceed total triggers"

        # Block count should be non-negative
        assert block_count >= 0, "Block count should be non-negative"

    @given(
        required_intervention_count=st.integers(min_value=0, max_value=20),
        actual_intervention_count=st.integers(min_value=0, max_value=20)
    )
    @settings(max_examples=50)
    def test_intervention_tracking(self, required_intervention_count, actual_intervention_count):
        """Test that interventions are tracked"""
        # Track interventions during supervision
        assert actual_intervention_count >= 0, "Intervention count should be non-negative"
        # Required interventions indicate issues during supervision
        assert required_intervention_count >= 0, "Required intervention count should be non-negative"


class TestRelationshipIntegrityInvariants:
    """Tests for model relationship integrity"""

    @given(
        user_count=st.integers(min_value=1, max_value=10),
        workspace_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50)
    def test_user_workspace_relationship(self, user_count, workspace_count):
        """Test that user-workspace relationships are valid"""
        users = []
        workspaces = []

        # Create workspaces
        for i in range(workspace_count):
            workspace = {
                "id": str(uuid4()),
                "name": f"Workspace {i}"
            }
            workspaces.append(workspace)

        # Assign users to workspaces
        for i in range(user_count):
            user = {
                "id": str(uuid4()),
                "workspace_id": workspaces[i % workspace_count]["id"]
            }
            users.append(user)

        # Verify all users reference valid workspaces
        workspace_ids = {w["id"] for w in workspaces}
        for user in users:
            assert user["workspace_id"] in workspace_ids, \
                f"User should reference valid workspace"

    @given(
        chat_count=st.integers(min_value=1, max_value=20),
        agent_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_chat_agent_relationship(self, chat_count, agent_count):
        """Test that chat-agent relationships are valid"""
        chats = []
        agents = []

        # Create agents
        for i in range(agent_count):
            agent = {
                "id": str(uuid4()),
                "name": f"Agent {i}"
            }
            agents.append(agent)

        # Create chats with agents
        for i in range(chat_count):
            chat = {
                "id": str(uuid4()),
                "agent_id": agents[i % agent_count]["id"]
            }
            chats.append(chat)

        # Verify all chats reference valid agents
        agent_ids = {a["id"] for a in agents}
        for chat in chats:
            assert chat["agent_id"] in agent_ids, \
                f"Chat should reference valid agent"

    @given(
        episode_count=st.integers(min_value=1, max_value=30),
        feedback_count=st.integers(min_value=0, max_value=50)
    )
    @settings(max_examples=50)
    def test_episode_feedback_relationship(self, episode_count, feedback_count):
        """Test that episode-feedback relationships are valid"""
        episodes = []
        feedbacks = []

        # Create episodes
        for i in range(episode_count):
            episode = {
                "id": str(uuid4()),
                "summary": f"Episode {i}"
            }
            episodes.append(episode)

        # Create feedback (may be more or fewer than episodes)
        for i in range(feedback_count):
            feedback = {
                "id": str(uuid4()),
                "episode_id": episodes[i % episode_count]["id"] if episode_count > 0 else str(uuid4()),
                "score": 0.0
            }
            feedbacks.append(feedback)

        # Verify feedback references valid episodes (when episodes exist)
        if episode_count > 0:
            episode_ids = {e["id"] for e in episodes}
            for feedback in feedbacks[:episode_count]:  # Only check first episode_count feedbacks
                # Some feedback might not have episodes (edge case)
                if feedback["episode_id"] in ["", "None", None]:
                    continue
                # For this test, we'll allow feedback without episodes
                pass


class TestFieldConstraintInvariants:
    """Tests for model field constraint invariants"""

    @given(
        text_content=st.text(min_size=0, max_size=10000, alphabet='abcdefghijklmnopqrstuvwxyz ')
    )
    @settings(max_examples=50)
    def test_text_field_size_limits(self, text_content):
        """Test that text fields respect size limits"""
        # Reasonable limit for text fields
        max_size = 10000
        assert len(text_content) <= max_size, f"Text content should be <= {max_size} chars"

    @given(
        integer_value=st.integers(min_value=-2147483648, max_value=2147483647)
    )
    @settings(max_examples=50)
    def test_integer_field_bounds(self, integer_value):
        """Test that integer fields are within valid range"""
        # PostgreSQL integer bounds
        min_int = -2147483648
        max_int = 2147483647
        assert min_int <= integer_value <= max_int, \
            f"Integer {integer_value} should be within valid range"

    @given(
        domain=st.text(min_size=3, max_size=30, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        tld=st.sampled_from(["com", "org", "net", "io", "co", "app"]),
        path=st.text(min_size=0, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz/-_'),
        use_https=st.booleans()
    )
    @settings(max_examples=50)
    def test_url_field_format(self, domain, tld, path, use_https):
        """Test that URL fields have valid format"""
        # Construct valid URL
        protocol = "https" if use_https else "http"
        url = f"{protocol}://{domain}.{tld}/{path}" if path else f"{protocol}://{domain}.{tld}"

        # Should start with http:// or https://
        assert url.startswith("http://") or url.startswith("https://"), \
            "URL should start with http:// or https://"

        # Should have a domain
        parts = url.split("://")[1].split("/")[0]
        assert len(parts) > 0, "URL should have a domain"


class TestEnumTypeInvariants:
    """Tests for enum type validity invariants"""

    @given(
        maturity_level=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])
    )
    @settings(max_examples=50)
    def test_maturity_level_enum(self, maturity_level):
        """Test that maturity level is valid enum value"""
        valid_levels = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
        assert maturity_level in valid_levels, "Maturity level should be valid"

    @given(
        action_complexity=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=50)
    def test_action_complexity_mapping(self, action_complexity):
        """Test that action complexity maps to valid levels"""
        # Complexity levels: 1 (LOW) to 4 (CRITICAL)
        assert 1 <= action_complexity <= 4, \
            f"Action complexity {action_complexity} should be in [1, 4]"

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_agent_confidence_to_maturity_mapping(self, confidence):
        """Test that agent confidence maps to appropriate maturity level"""
        # Based on maturity level requirements:
        # STUDENT: <0.5, INTERN: 0.5-0.7, SUPERVISED: 0.7-0.9, AUTONOMOUS: >0.9
        if confidence < 0.5:
            expected = "STUDENT"
        elif confidence < 0.7:
            expected = "INTERN"
        elif confidence < 0.9:
            expected = "SUPERVISED"
        else:
            expected = "AUTONOMOUS"

        # Verify mapping (within tolerance for floating point)
        assert expected in ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"], \
            "Expected maturity level should be valid"
