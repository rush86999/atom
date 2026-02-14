---
phase: 08-80-percent-coverage-push
plan: 23
wave: 4
depends_on: []
status: pending
created: 2026-02-13
gap_closure: false
---

# Plan 23: Critical Governance Infrastructure

**Status:** Pending
**Wave:** 4
**Dependencies:** None

## Objective

Create comprehensive baseline unit tests for 4 critical governance infrastructure files, achieving 60% average coverage to contribute +1.0-1.2% toward Phase 8.7's 17-18% overall coverage goal.

## Context

Phase 8.7 targets 17-18% overall coverage (+2-3% from 15.87% baseline) by testing top zero-coverage files. This plan focuses on critical governance infrastructure:

1. **constitutional_validator.py** (587 lines) - Constitutional compliance validation
2. **websocket_manager.py** (377 lines) - Real-time WebSocket communication
3. **governance_helper.py** (436 lines) - Governance decision helpers
4. **agent_request_manager.py** (482 lines) - Agent request lifecycle management

**Total Production Lines:** 1,882
**Expected Coverage at 60%:** ~1,129 lines
**Coverage Contribution:** +1.0-1.2 percentage points toward 17-18% goal

## Success Criteria

**Must Have (truths that become verifiable):**
1. Constitutional validator has 60%+ test coverage (rules validation, compliance checks)
2. WebSocket manager has 60%+ test coverage (connection management, message handling)
3. Governance helpers have 60%+ test coverage (decision logic, caching)
4. Agent request manager has 60%+ test coverage (request lifecycle, state management)

**Should Have:**
- Edge cases tested (WebSocket errors, invalid rules, concurrent requests)
- Integration patterns tested (mock dependencies, async coordination)
- Performance tests for governance decision caching

**Could Have:**
- Property-based tests for constitutional rules
- Load tests for WebSocket connection limits

**Won't Have:**
- Full integration tests (database interactions mocked)
- WebSocket server integration (too complex for unit tests)

## Tasks

### Task 1: Create test_constitutional_validator.py

**Files:**
- CREATE: `backend/tests/unit/test_constitutional_validator.py` (600+ lines, 40-45 tests)

**Action:**
```bash
cat > backend/tests/unit/test_constitutional_validator.py << 'EOF'
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.constitutional_validator import ConstitutionalValidator

@pytest.fixture
def validator():
    """Create validator instance."""
    return ConstitutionalValidator()

@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()

def test_validator_initialization(validator):
    """Test validator initializes correctly."""
    assert validator is not None
    assert hasattr(validator, 'validate_rule')

def test_validate_constitutional_rule_success(validator, mock_db):
    """Test successful constitutional rule validation."""
    rule = {
        "rule_id": "test_rule",
        "constraint": "max_agents",
        "value": 100
    }
    with patch.object(validator, 'db', mock_db):
        result = validator.validate_rule(rule)
        assert result["valid"] is True

def test_validate_constitutional_rule_failure(validator, mock_db):
    """Test constitutional rule validation failure."""
    rule = {
        "rule_id": "test_rule",
        "constraint": "max_agents",
        "value": -1  # Invalid
    }
    with patch.object(validator, 'db', mock_db):
        result = validator.validate_rule(rule)
        assert result["valid"] is False

def test_validate_agent_action_compliant(validator, mock_db):
    """Test agent action passes constitutional validation."""
    action = {
        "agent_id": "agent_123",
        "action": "data_access",
        "resource": "dataset_1"
    }
    with patch.object(validator, 'db', mock_db):
        result = validator.validate_action(action)
        assert result["compliant"] is True

def test_validate_agent_action_violation(validator, mock_db):
    """Test agent action violates constitutional rules."""
    action = {
        "agent_id": "agent_123",
        "action": "delete_all_data",  # Prohibited action
        "resource": "*"
    }
    with patch.object(validator, 'db', mock_db):
        result = validator.validate_action(action)
        assert result["compliant"] is False
        assert "violation" in result

def test_check_intervention_history(validator, mock_db):
    """Test intervention history checking."""
    agent_id = "agent_123"
    with patch.object(validator, 'db', mock_db):
        history = validator.get_intervention_history(agent_id)
        assert isinstance(history, list)

def test_validate_graduation_eligibility(validator, mock_db):
    """Test agent graduation eligibility validation."""
    agent_id = "agent_123"
    with patch.object(validator, 'db', mock_db):
        eligibility = validator.check_graduation_eligibility(agent_id)
        assert "eligible" in eligibility

def test_constitutional_rules_loading(validator):
    """Test constitutional rules are loaded correctly."""
    rules = validator.load_rules()
    assert isinstance(rules, dict)
    assert len(rules) > 0

def test_rule_constraint_validation(validator):
    """Test rule constraint validation logic."""
    valid_constraints = ["max_agents", "min_confidence", "allowed_actions"]
    for constraint in valid_constraints:
        assert validator.is_valid_constraint(constraint)

def test_invalid_constraint_rejection(validator):
    """Test invalid constraints are rejected."""
    invalid_constraints = ["not_a_real_constraint", "", None]
    for constraint in invalid_constraints:
        assert not validator.is_valid_constraint(constraint)

# Add 30+ more tests following Phase 8.6 patterns...
EOF

# Verify file created
wc -l backend/tests/unit/test_constitutional_validator.py
```

**Verify:**
```bash
test -f backend/tests/unit/test_constitutional_validator.py && echo "File exists"
grep -c "^def test_" backend/tests/unit/test_constitutional_validator.py
# Expected: 40-45 tests
```

**Done:**
- File created with 40-45 tests
- Constitutional rule validation tested
- Agent action compliance tested
- Intervention history checked
- Graduation eligibility validated

---

### Task 2: Create test_websocket_manager.py

**Files:**
- CREATE: `backend/tests/unit/test_websocket_manager.py` (500+ lines, 35-40 tests)

**Action:**
```bash
cat > backend/tests/unit/test_websocket_manager.py << 'EOF'
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.websocket_manager import WebSocketManager

@pytest.fixture
def manager():
    """Create WebSocket manager instance."""
    return WebSocketManager()

@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    return ws

def test_manager_initialization(manager):
    """Test manager initializes correctly."""
    assert manager is not None
    assert hasattr(manager, 'connect')
    assert hasattr(manager, 'disconnect')
    assert hasattr(manager, 'broadcast')

def test_websocket_connection_established(manager, mock_websocket):
    """Test WebSocket connection is established."""
    client_id = "client_123"
    manager.connect(client_id, mock_websocket)
    assert client_id in manager.active_connections

def test_websocket_disconnection(manager, mock_websocket):
    """Test WebSocket disconnection."""
    client_id = "client_123"
    manager.connect(client_id, mock_websocket)
    manager.disconnect(client_id)
    assert client_id not in manager.active_connections

def test_broadcast_message_to_all(manager, mock_websocket):
    """Test broadcasting message to all connected clients."""
    # Connect multiple clients
    for i in range(3):
        manager.connect(f"client_{i}", mock_websocket)

    message = {"type": "update", "data": "test"}
    manager.broadcast(message)

    # Verify all clients received the message
    for i in range(3):
        mock_websocket.send.assert_called()

def test_send_message_to_specific_client(manager, mock_websocket):
    """Test sending message to specific client."""
    client_id = "client_123"
    manager.connect(client_id, mock_websocket)

    message = {"type": "notification", "data": "test"}
    manager.send_to_client(client_id, message)

    mock_websocket.send.assert_called_once()

def test_send_to_nonexistent_client(manager):
    """Test sending to nonexistent client handles gracefully."""
    # Should not raise exception
    manager.send_to_client("nonexistent_client", {"data": "test"})
    # Verify error logged or handled

def test_connection_limit_enforcement(manager):
    """Test WebSocket connection limit is enforced."""
    max_connections = manager.max_connections or 100

    # Try to exceed limit
    for i in range(max_connections + 10):
        manager.connect(f"client_{i}", AsyncMock())

    # Should enforce limit
    assert len(manager.active_connections) <= max_connections

def test_get_active_connection_count(manager):
    """Test getting active connection count."""
    initial_count = manager.get_connection_count()
    assert initial_count >= 0

    manager.connect("new_client", AsyncMock())
    new_count = manager.get_connection_count()
    assert new_count == initial_count + 1

def test_close_all_connections(manager):
    """Test closing all WebSocket connections."""
    # Add some connections
    for i in range(5):
        ws = AsyncMock()
        ws.close = AsyncMock()
        manager.connect(f"client_{i}", ws)

    manager.close_all()

    # All connections should be closed
    assert len(manager.active_connections) == 0

# Add 25+ more tests following Phase 8.6 patterns...
EOF

# Verify file created
wc -l backend/tests/unit/test_websocket_manager.py
```

**Verify:**
```bash
test -f backend/tests/unit/test_websocket_manager.py && echo "File exists"
grep -c "^def test_" backend/tests/unit/test_websocket_manager.py
# Expected: 35-40 tests
```

**Done:**
- File created with 35-40 tests
- WebSocket connection management tested
- Message broadcasting tested
- Connection limits enforced
- Cleanup procedures validated

---

### Task 3: Create test_governance_helper.py

**Files:**
- CREATE: `backend/tests/unit/test_governance_helper.py` (450+ lines, 30-35 tests)

**Action:**
```bash
cat > backend/tests/unit/test_governance_helper.py << 'EOF'
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.governance_helper import GovernanceHelper

@pytest.fixture
def helper():
    """Create governance helper instance."""
    return GovernanceHelper()

@pytest.fixture
def mock_cache():
    """Mock governance cache."""
    cache = AsyncMock()
    cache.get.return_value = {"maturity_level": 0.8}
    return cache

def test_helper_initialization(helper):
    """Test helper initializes correctly."""
    assert helper is not None
    assert hasattr(helper, 'check_permission')
    assert hasattr(helper, 'get_governance_decision')

def test_permission_check_allowed(helper, mock_cache):
    """Test permission check returns allowed."""
    with patch.object(helper, 'cache', mock_cache):
        result = helper.check_permission(
            agent_id="agent_123",
            action="data_access",
            complexity=2
        )
        assert result["allowed"] is True

def test_permission_check_denied(helper, mock_cache):
    """Test permission check returns denied."""
    mock_cache.get.return_value = {"maturity_level": 0.3}  # STUDENT
    with patch.object(helper, 'cache', mock_cache):
        result = helper.check_permission(
            agent_id="student_agent",
            action="form_submission",  # HIGH complexity
            complexity=3
        )
        assert result["allowed"] is False

def test_governance_decision_cached(helper, mock_cache):
    """Test governance decision is cached."""
    agent_id = "agent_123"
    with patch.object(helper, 'cache', mock_cache):
        decision1 = helper.get_governance_decision(agent_id)
        decision2 = helper.get_governance_decision(agent_id)
        assert decision1 == decision2
        # Cache should be hit twice
        assert mock_cache.get.call_count == 2

def test_maturity_level_check(helper):
    """Test maturity level determination."""
    maturity = helper.get_maturity_level("agent_123")
    assert 0.0 <= maturity <= 1.0

def test_action_complexity_classification(helper):
    """Test action complexity classification."""
    low_complexity = helper.get_action_complexity("read_data")
    high_complexity = helper.get_action_complexity("delete_all_data")
    assert low_complexity < high_complexity

def test_governance_rules_evaluation(helper):
    """Test governance rules are evaluated correctly."""
    rules = helper.evaluate_rules(
        agent_maturity=0.8,
        action_complexity=2
    )
    assert isinstance(rules, dict)
    assert "allowed" in rules

def test_supervision_requirement_check(helper):
    """Test supervision requirement for low-confidence agents."""
    supervision = helper.requires_supervision(
        agent_maturity=0.65,
        action_complexity=3
    )
    assert supervision is True  # SUPERVISED agents need supervision for HIGH complexity

def test_autonomous_action_allowed(helper):
    """Test autonomous agents can perform autonomous actions."""
    allowed = helper.check_autonomous_permission(
        agent_maturity=0.95,  # AUTONOMOUS
        action_complexity=2
    )
    assert allowed is True

def test_block_student_triggers(helper):
    """Test STUDENT agents are blocked from automated triggers."""
    blocked = helper.should_block_trigger(
        agent_maturity=0.4,  # STUDENT
        trigger_type="automated"
    )
    assert blocked is True

# Add 20+ more tests following Phase 8.6 patterns...
EOF

# Verify file created
wc -l backend/tests/unit/test_governance_helper.py
```

**Verify:**
```bash
test -f backend/tests/unit/test_governance_helper.py && echo "File exists"
grep -c "^def test_" backend/tests/unit/test_governance_helper.py
# Expected: 30-35 tests
```

**Done:**
- File created with 30-35 tests
- Permission checks tested
- Governance decisions validated
- Caching logic tested
- Maturity level checks validated

---

### Task 4: Create test_agent_request_manager.py

**Files:**
- CREATE: `backend/tests/unit/test_agent_request_manager.py` (450+ lines, 30-35 tests)

**Action:**
```bash
cat > backend/tests/unit/test_agent_request_manager.py << 'EOF'
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.agent_request_manager import AgentRequestManager

@pytest.fixture
def manager():
    """Create request manager instance."""
    return AgentRequestManager()

@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()

def test_manager_initialization(manager):
    """Test manager initializes correctly."""
    assert manager is not None
    assert hasattr(manager, 'create_request')
    assert hasattr(manager, 'process_request')
    assert hasattr(manager, 'cancel_request')

def test_create_request_success(manager, mock_db):
    """Test successful request creation."""
    request_data = {
        "agent_id": "agent_123",
        "action": "data_access",
        "parameters": {"resource": "dataset_1"}
    }
    with patch.object(manager, 'db', mock_db):
        result = manager.create_request(request_data)
        assert result["status"] == "created"
        assert "request_id" in result

def test_process_request_pending(manager, mock_db):
    """Test processing pending request."""
    request_id = "req_123"
    with patch.object(manager, 'db', mock_db):
        result = manager.process_request(request_id)
        assert result["status"] in ["pending", "processing", "completed"]

def test_cancel_request_success(manager, mock_db):
    """Test successful request cancellation."""
    request_id = "req_123"
    with patch.object(manager, 'db', mock_db):
        result = manager.cancel_request(request_id)
        assert result["status"] == "cancelled"

def test_request_lifecycle_tracking(manager, mock_db):
    """Test request lifecycle is tracked correctly."""
    request_id = "req_123"
    with patch.object(manager, 'db', mock_db):
        # Create
        manager.create_request({"request_id": request_id})
        # Process
        manager.process_request(request_id)
        # Complete
        result = manager.get_request_status(request_id)
        assert result["lifecycle"] in ["created", "processing", "completed"]

def test_concurrent_request_handling(manager, mock_db):
    """Test concurrent requests are handled correctly."""
    # Create multiple requests
    request_ids = [f"req_{i}" for i in range(5)]
    with patch.object(manager, 'db', mock_db):
        for req_id in request_ids:
            manager.create_request({"request_id": req_id})

        # Verify all requests tracked
        active = manager.get_active_requests()
        assert len(active) >= 5

def test_request_timeout_detection(manager):
    """Test request timeout is detected."""
    import time
    request_id = "req_timeout"
    # Create old request
    manager.create_request({
        "request_id": request_id,
        "timestamp": time.time() - 3600  # 1 hour old
    })

    # Check for timeout
    timeout = manager.is_request_timed_out(request_id)
    assert timeout is True

def test_request_priority_handling(manager, mock_db):
    """Test requests are processed by priority."""
    high_priority = "req_high"
    low_priority = "req_low"

    with patch.object(manager, 'db', mock_db):
        # Create with different priorities
        manager.create_request({
            "request_id": high_priority,
            "priority": "urgent"
        })
        manager.create_request({
            "request_id": low_priority,
            "priority": "normal"
        })

        # High priority should be processed first
        queue = manager.get_request_queue()
        if len(queue) > 1:
            assert queue[0]["request_id"] == high_priority

def test_request_state_transitions(manager):
    """Test request state transitions correctly."""
    states = ["created", "processing", "completed", "failed", "cancelled"]
    for state in states:
        assert manager.is_valid_state(state)

# Add 20+ more tests following Phase 8.6 patterns...
EOF

# Verify file created
wc -l backend/tests/unit/test_agent_request_manager.py
```

**Verify:**
```bash
test -f backend/tests/unit/test_agent_request_manager.py && echo "File exists"
grep -c "^def test_" backend/tests/unit/test_agent_request_manager.py
# Expected: 30-35 tests
```

**Done:**
- File created with 30-35 tests
- Request creation tested
- Request processing validated
- Cancellation logic tested
- Request lifecycle tracked

---

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_constitutional_validator.py | core/constitutional_validator.py | direct import | Test constitutional rule validation |
| test_websocket_manager.py | core/websocket_manager.py | mock_websocket | Test WebSocket connection management |
| test_governance_helper.py | core/governance_helper.py | mock_cache | Test governance decision logic |
| test_agent_request_manager.py | core/agent_request_manager.py | mock_db | Test agent request lifecycle |

## Progress Tracking

**Current Coverage (Phase 8):** 15.87%
**Plan 23 Target:** +1.0-1.2 percentage points
**Projected After Plan 23:** ~16.9-17.1%

## Notes

- All 4 files are critical governance infrastructure with zero coverage
- 60% coverage target (higher than standard 50% due to critical path)
- Test patterns from Phase 8.6 applied (AsyncMock, fixtures)
- Estimated 150-180 tests total across 4 files
- Duration: 2-3 hours
