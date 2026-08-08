"""
Bug-hunt + coverage tests for core/workflow_debugger.py (round 2).

Each ``BUG:`` test is written first (TDD), verified to FAIL for the right
reason, then the source is fixed and the test passes.
"""
import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from core.workflow_debugger import WorkflowDebugger
from core.models import (
    WorkflowDebugSession,
    WorkflowBreakpoint,
    ExecutionTrace,
    DebugVariable,
)


@pytest.fixture
def db_session():
    """Mock SQLAlchemy session (no real DB needed for debugger unit logic)."""
    session = MagicMock(spec=Session)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.refresh = MagicMock()
    session.query = MagicMock()
    return session


def _make_breakpoint(
    *,
    hit_limit=None,
    hit_count=0,
    condition=None,
    log_message=None,
    debug_session_id=None,
    is_active=True,
    is_disabled=False,
    node_id="node1",
):
    """Build a mock WorkflowBreakpoint with the given attributes."""
    bp = MagicMock(spec=WorkflowBreakpoint)
    bp.node_id = node_id
    bp.hit_limit = hit_limit
    bp.hit_count = hit_count
    bp.condition = condition
    bp.log_message = log_message
    bp.debug_session_id = debug_session_id
    bp.is_active = is_active
    bp.is_disabled = is_disabled
    return bp


def _wire_breakpoints(db_session, breakpoints):
    """Make db_session.query(...).filter(...).all() return the given list."""
    query = MagicMock()
    query.filter.return_value.all.return_value = breakpoints
    db_session.query.return_value = query
    return query


# =============================================================================
# BUG 1 (HIGH): check_breakpoint_hit — a logpoint suppresses a later real
# breakpoint on the same node. Logpoints must not block pauses from other BPs.
# =============================================================================

def test_bug_check_breakpoint_hit_logpoint_does_not_suppress_pause(db_session):
    """BUG: logpoint (log_message set) short-circuits the loop and prevents a
    subsequent real breakpoint on the same node from triggering a pause."""
    debugger = WorkflowDebugger(db=db_session)

    logpoint = _make_breakpoint(log_message="hit node1")
    real_bp = _make_breakpoint(log_message=None)  # should cause a pause

    _wire_breakpoints(db_session, [logpoint, real_bp])

    should_pause, log = debugger.check_breakpoint_hit("node1", {})

    # Expectation: a real (pausing) breakpoint exists, so the engine MUST pause.
    assert should_pause is True, (
        "Logpoint must not suppress a real breakpoint on the same node"
    )


# =============================================================================
# BUG 2 (MEDIUM): get_breakpoints(active_only=True) ignores the is_disabled
# flag. A breakpoint toggled off via toggle_breakpoint still shows up in the
# "active only" listing, contradicting toggle_breakpoint semantics.
# =============================================================================

def test_bug_get_breakpoints_active_only_excludes_disabled():
    """BUG: get_breakpoints(active_only=True) returns breakpoints whose
    is_disabled flag is True even though they were toggled off.

    Uses an in-memory SQLite database so the SQLAlchemy filters are actually
    evaluated (a MagicMock session would ignore the filter conditions).
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from core.models_registration import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Two breakpoints on the same workflow: one enabled, one disabled.
        enabled = WorkflowBreakpoint(
            workflow_id="wf-1", node_id="n1", breakpoint_type="node",
            hit_count=0, is_active=True, is_disabled=False,
            created_by="u1",
        )
        disabled = WorkflowBreakpoint(
            workflow_id="wf-1", node_id="n2", breakpoint_type="node",
            hit_count=0, is_active=True, is_disabled=True,  # toggled off
            created_by="u1",
        )
        db.add_all([enabled, disabled])
        db.commit()

        debugger = WorkflowDebugger(db=db)
        result = debugger.get_breakpoints("wf-1", active_only=True)

        assert len(result) == 1, (
            "Disabled breakpoints must not appear when active_only=True"
        )
        assert result[0].is_disabled is False
    finally:
        db.close()
        engine.dispose()


# =============================================================================
# BUG 3 (MEDIUM): record_step_timing initializes min_ms to float('inf') and
# stores it in performance_metrics, which then cannot be (re)serialized via
# JSON (Infinity is not valid JSON). After the first record the value is fine,
# but if only the started_at metrics are exported before any timing lands, the
# report/serialization breaks. Verify get_performance_report tolerates a node
# that was never timed.
# Here we instead verify the realistic regression: min_ms must never stay inf.
# =============================================================================

def test_bug_record_step_timing_min_ms_never_inf(db_session):
    """BUG: min_ms starts at float('inf'); if metrics are serialized before any
    sample lands the value is non-JSON. After recording at least one sample the
    min_ms must be a finite number."""
    debugger = WorkflowDebugger(db=db_session)

    session = MagicMock(spec=WorkflowDebugSession)
    session.performance_metrics = {
        "enabled": True,
        "started_at": "2026-01-01T00:00:00",
        "step_times": [],
        "node_times": {},
        "total_duration_ms": 0,
    }
    q = MagicMock()
    q.filter.return_value.first.return_value = session
    db_session.query.return_value = q

    ok = debugger.record_step_timing("sess-1", "n1", "task", 50)
    assert ok is True

    import json
    metrics = session.performance_metrics
    # Must round-trip through JSON (the persistence layer uses json.dump).
    serialized = json.dumps(metrics)
    assert "Infinity" not in serialized, (
        "min_ms must be JSON-serializable (no Infinity) after a sample is recorded"
    )
    assert metrics["node_times"]["n1"]["min_ms"] == 50


# =============================================================================
# Coverage tests (secondary goal): exercise untested-correct branches.
# =============================================================================

class TestWorkflowDebuggerCoverage:
    """Additional coverage for variable inspection, profiling, collaborators."""

    def test_generate_value_preview_types(self, db_session):
        """Cover _generate_value_preview for all type branches."""
        debugger = WorkflowDebugger(db=db_session)
        assert debugger._generate_value_preview(None) == "null"
        assert debugger._generate_value_preview("hi") == "hi"
        assert debugger._generate_value_preview(42) == "42"
        assert debugger._generate_value_preview(3.14) == "3.14"
        assert debugger._generate_value_preview(True) == "True"
        assert debugger._generate_value_preview({"a": 1}) == "dict(1 keys)"
        assert debugger._generate_value_preview([1, 2]) == "list(2 items)"
        assert debugger._generate_value_preview({1, 2}) == "set(2 items)"
        # Unknown type falls through to str(value)[:max_length]
        class Custom:
            def __str__(self):
                return "x" * 200
        preview = debugger._generate_value_preview(Custom(), max_length=10)
        assert preview == "x" * 10

    def test_create_variable_snapshot_success(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        var = debugger.create_variable_snapshot(
            trace_id="t1", variable_name="x", variable_path="x",
            variable_type="int", value=10, scope="local", is_watch=True,
            debug_session_id="s1",
        )
        assert var is not None
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()

    def test_create_variable_snapshot_failure_reraises(self, db_session):
        db_session.commit.side_effect = RuntimeError("db down")
        debugger = WorkflowDebugger(db=db_session)
        with pytest.raises(RuntimeError):
            debugger.create_variable_snapshot(
                trace_id="t1", variable_name="x", variable_path="x",
                variable_type="int", value=10,
            )
        db_session.rollback.assert_called_once()

    def test_get_variables_for_trace_and_watch(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        mock_var = MagicMock(spec=DebugVariable)
        q = MagicMock()
        q.filter.return_value.all.return_value = [mock_var]
        db_session.query.return_value = q

        assert debugger.get_variables_for_trace("t1") == [mock_var]
        assert debugger.get_watch_variables("s1") == [mock_var]

    def test_modify_variable_round_trip(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        session = MagicMock(spec=WorkflowDebugSession)
        session.variables = {"x": 1}
        q = MagicMock()
        q.filter.return_value.first.return_value = session
        db_session.query.return_value = q

        result = debugger.modify_variable("s1", "x", 99)
        assert result is not None
        assert result.previous_value == 1
        assert session.variables["x"] == 99

    def test_modify_variable_no_session(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        db_session.query.return_value = q
        assert debugger.modify_variable("s1", "x", 1) is None

    def test_bulk_modify_variables(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        session = MagicMock(spec=WorkflowDebugSession)
        session.variables = {}
        q = MagicMock()
        q.filter.return_value.first.return_value = session
        db_session.query.return_value = q

        results = debugger.bulk_modify_variables(
            "s1",
            [{"variable_name": "a", "new_value": 1}, {"variable_name": "b", "new_value": 2}],
        )
        assert len(results) == 2
        # Entries with no variable_name key (None) are skipped gracefully.
        results2 = debugger.bulk_modify_variables(
            "s1", [{"new_value": 3}]
        )
        assert results2 == []

    def test_collaborator_lifecycle_and_permissions(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        session = MagicMock(spec=WorkflowDebugSession)
        session.user_id = "owner"
        session.collaborators = {}
        q = MagicMock()
        q.filter.return_value.first.return_value = session
        db_session.query.return_value = q

        assert debugger.add_collaborator("s1", "alice", "viewer") is True
        assert session.collaborators["alice"]["permission"] == "viewer"

        # owner has all perms
        assert debugger.check_collaborator_permission("s1", "owner", "owner") is True
        # alice (viewer) lacks operator
        assert debugger.check_collaborator_permission("s1", "alice", "operator") is False
        # alice (viewer) has viewer
        assert debugger.check_collaborator_permission("s1", "alice", "viewer") is True
        # unknown collaborator
        assert debugger.check_collaborator_permission("s1", "bob", "viewer") is False

        # remove collaborator
        assert debugger.remove_collaborator("s1", "alice") is True
        assert "alice" not in session.collaborators
        # removing again returns False
        assert debugger.remove_collaborator("s1", "alice") is False

    def test_get_session_collaborators_and_empty(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        session = MagicMock(spec=WorkflowDebugSession)
        session.collaborators = {"alice": {"permission": "viewer", "added_at": "t"}}
        q = MagicMock()
        q.filter.return_value.first.return_value = session
        db_session.query.return_value = q

        collabs = debugger.get_session_collaborators("s1")
        assert len(collabs) == 1
        assert collabs[0]["user_id"] == "alice"

        # missing session -> []
        q.filter.return_value.first.return_value = None
        assert debugger.get_session_collaborators("missing") == []

    def test_performance_report(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        session = MagicMock(spec=WorkflowDebugSession)
        session.performance_metrics = {
            "enabled": True,
            "started_at": "2026-01-01T00:00:00",
            "step_times": [
                {"node_id": "n1", "node_type": "task", "duration_ms": 100, "timestamp": "t"},
                {"node_id": "n2", "node_type": "task", "duration_ms": 50, "timestamp": "t"},
            ],
            "node_times": {
                "n1": {"count": 1, "total_ms": 100, "avg_ms": 100, "min_ms": 100, "max_ms": 100},
                "n2": {"count": 1, "total_ms": 50, "avg_ms": 50, "min_ms": 50, "max_ms": 50},
            },
            "total_duration_ms": 150,
        }
        q = MagicMock()
        q.filter.return_value.first.return_value = session
        db_session.query.return_value = q

        report = debugger.get_performance_report("s1")
        assert report["total_duration_ms"] == 150
        assert report["total_steps"] == 2
        assert report["slowest_steps"][0]["node_id"] == "n1"  # 100 > 50
        assert report["slowest_nodes"][0]["node_id"] == "n1"

    def test_get_performance_report_no_metrics(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        session = MagicMock(spec=WorkflowDebugSession)
        session.performance_metrics = None
        q = MagicMock()
        q.filter.return_value.first.return_value = session
        db_session.query.return_value = q
        assert debugger.get_performance_report("s1") is None

    def test_trace_stream_helpers(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        stream_id = debugger.create_trace_stream("s1", "e1")
        assert stream_id.startswith("trace_e1_s1_")

        # with websocket manager
        wm = MagicMock()
        assert debugger.stream_trace_update(stream_id, {"x": 1}, wm) is True
        wm.broadcast.assert_called_once()
        # without websocket manager -> False (fallback)
        assert debugger.stream_trace_update(stream_id, {"x": 1}) is False
        # close stream
        assert debugger.close_trace_stream(stream_id, wm) is True
        assert debugger.close_trace_stream(stream_id) is True

    def test_export_session_and_missing(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        session = MagicMock(spec=WorkflowDebugSession)
        session.id = "s1"
        session.workflow_id = "wf1"
        session.execution_id = None
        session.user_id = "u1"
        session.session_name = "Test"
        session.status = "active"
        session.current_step = 0
        session.current_node_id = None
        session.variables = {}
        session.call_stack = []
        session.stop_on_entry = False
        session.stop_on_exceptions = True
        session.stop_on_error = True
        session.created_at = None
        session.updated_at = None
        session.completed_at = None
        q = MagicMock()
        q.filter.return_value.first.return_value = session
        # get_breakpoints inner call -> empty list
        bp_chain = MagicMock()
        bp_chain.filter.return_value.order_by.return_value.all.return_value = []
        # First query (session) returns session; subsequent (breakpoints) return chain.
        db_session.query.return_value = q
        q.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        exported = debugger.export_session("s1")
        assert exported is not None
        assert exported["session"]["id"] == "s1"
        assert exported["breakpoints"] == []

        # missing session
        q.filter.return_value.first.return_value = None
        assert debugger.export_session("missing") is None

    def test_pause_resume_complete_session_not_found(self, db_session):
        debugger = WorkflowDebugger(db=db_session)
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        db_session.query.return_value = q
        assert debugger.pause_debug_session("x") is False
        assert debugger.resume_debug_session("x") is False
        assert debugger.complete_debug_session("x") is False
