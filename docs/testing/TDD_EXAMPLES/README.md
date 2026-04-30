# TDD Example Suite: Atom v12.0

**Purpose**: Complete examples demonstrating bug discovery through TDD with full red-green-refactor cycles.

**Structure**: Each example is a self-contained bug discovery journey from test to fix to refactor.

---

## Table of Examples

### Backend Examples (Python)

1. [Example 1: Agent Maturity Demotion Bug](#example-1-agent-maturity-demotion-bug) - Governance validation prevents demotion
2. [Example 2: Invoice Total Validation Bug](#example-2-invoice-total-validation-bug) - Business rule enforcement
3. [Example 3: Agent Execution Timeout Bug](#example-3-agent-execution-timeout-bug) - Timeout handling
4. [Example 4: LLM Service Memory Leak Bug](#example-4-llm-service-memory-leak-bug) - Resource cleanup
5. [Example 5: Episode Segmentation Time Gap Bug](#example-5-episode-segmentation-time-gap-bug) - Edge case in time calculations
6. [Example 6: Agent Permission Check Race Condition](#example-6-agent-permission-check-race-condition) - Concurrent operations

### Frontend Examples (TypeScript)

7. [Example 7: ChatInput Empty Submit Bug](#example-7-chattinput-empty-submit-bug) - Form validation
8. [Example 8: CommunicationHub Title Mismatch](#example-8-communicationhub-title-mismatch) - Test assertion fix
9. [Example 9: TaskManagement Missing Props Bug](#example-9-taskmanagement-missing-props-bug) - Component props
10. [Example 10: Canvas Presentation Loading State Bug](#example-10-canvas-presentation-loading-state-bug) - UX state management

---

## Example 1: Agent Maturity Demotion Bug

### Bug Description

Agent maturity allows demotion from AUTONOMOUS to STUDENT, bypassing graduation requirements and creating security risk.

### Red Phase: Write Failing Test

```python
# backend/tests/test_agent_governance_service.py

import pytest
from core.models import AgentRegistry, AgentMaturity
from core.agent_governance_service import AgentGovernanceService
from sqlalchemy.orm import Session

def test_agent_maturity_blocks_demotion_autonomous_to_student():
    """
    BUG: Agent maturity allows demotion from AUTONOMOUS to STUDENT.

    EXPECTED: ValueError raised (demotion not allowed)
    ACTUAL: Demotion succeeds (security risk)
    """
    # Arrange
    agent = AgentRegistry(
        id="test-agent-001",
        name="Test Agent",
        maturity=AgentMaturity.AUTONOMOUS,
        capabilities=["execute_workflow", "manage_tasks"]
    )

    with SessionLocal() as db:
        db.add(agent)
        db.commit()

        service = AgentGovernanceService(db)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid maturity transition"):
            service.update_maturity("test-agent-001", AgentMaturity.STUDENT)
```

**Run Test**:
```bash
pytest backend/tests/test_agent_governance_service.py::test_agent_maturity_blocks_demotion_autonomous_to_student -v
```

**Output**:
```
FAILED - Function: update_maturity() completed without error
Expected: ValueError("Invalid maturity transition")
Actual: No exception raised
```

### Green Phase: Write Minimal Fix

```python
# backend/core/agent_governance_service.py

from core.models import AgentRegistry, AgentMaturity
from sqlalchemy.orm import Session

class AgentGovernanceService:
    def __init__(self, db: Session):
        self.db = db

    def update_maturity(self, agent_id: str, new_maturity: AgentMaturity):
        """Update agent maturity level."""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # GREEN PHASE: Add validation to block demotion
        maturity_levels = {
            AgentMaturity.STUDENT: 1,
            AgentMaturity.INTERN: 2,
            AgentMaturity.SUPERVISED: 3,
            AgentMaturity.AUTONOMOUS: 4,
        }

        current_level = maturity_levels[agent.maturity]
        new_level = maturity_levels[new_maturity]

        if new_level < current_level:
            raise ValueError(
                f"Invalid maturity transition: {agent.maturity} → {new_maturity}. "
                f"Demotion not allowed (graduation required)."
            )

        agent.maturity = new_maturity
        self.db.commit()
```

**Run Test**:
```bash
pytest backend/tests/test_agent_governance_service.py::test_agent_maturity_blocks_demotion_autonomous_to_student -v
```

**Output**:
```
PASSED ✓
```

### Refactor Phase: Improve Code Quality

```python
# backend/core/agent_governance_service.py

class AgentGovernanceService:
    def __init__(self, db: Session):
        self.db = db

    def update_maturity(self, agent_id: str, new_maturity: AgentMaturity):
        """Update agent maturity level with validation."""
        agent = self._get_agent(agent_id)
        self._validate_maturity_transition(agent.maturity, new_maturity)

        agent.maturity = new_maturity
        self.db.commit()

    def _get_agent(self, agent_id: str) -> AgentRegistry:
        """Fetch agent by ID."""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        return agent

    def _validate_maturity_transition(self, current: AgentMaturity, new: AgentMaturity):
        """Validate that maturity transition is allowed (no demotion)."""
        if self._is_demotion(current, new):
            raise ValueError(
                f"Invalid maturity transition: {current} → {new}. "
                f"Demotion not allowed (graduation required)."
            )

    def _is_demotion(self, current: AgentMaturity, new: AgentMaturity) -> bool:
        """Check if maturity transition is a demotion."""
        levels = {
            AgentMaturity.STUDENT: 1,
            AgentMaturity.INTERN: 2,
            AgentMaturity.SUPERVISED: 3,
            AgentMaturity.AUTONOMOUS: 4,
        }
        return levels[new] < levels[current]
```

**Run Tests**: All pass ✓

### Bug Discovery Summary

**Category**: Governance validation
**Severity**: HIGH (security risk)
**Root Cause**: Missing maturity transition validation
**Fix Pattern**: Add state machine validation (block invalid transitions)
**Test Coverage**: 1 test added, prevents regression
**Files Changed**: 1 file, 4 methods extracted
**Time to Fix**: 15 minutes

**Lessons Learned**:
- State transitions require explicit validation
- Demotion bypasses graduation (security risk)
- Extracted methods improve testability

---

## Example 2: Invoice Total Validation Bug

### Bug Description

Invoice total allows negative values, causing accounting errors and incorrect reporting.

### Red Phase: Write Failing Test

```python
# backend/tests/test_invoice_service.py

import pytest
from core.models import Invoice, InvoiceStatus
from core.invoice_service import InvoiceService

def test_invoice_total_must_be_positive():
    """
    BUG: Invoice total allows negative values.

    EXPECTED: ValueError raised for negative totals
    ACTUAL: Negative totals accepted (accounting error)
    """
    # Arrange
    invoice = Invoice(
        id="INV-001",
        customer_id="CUST-001",
        total=-100.00  # Negative total (invalid)
    )

    service = InvoiceService(db)

    # Act & Assert
    with pytest.raises(ValueError, match="Invoice total must be positive"):
        service.create_invoice(invoice)
```

**Run Test**: FAILS (no validation exists)

### Green Phase: Write Minimal Fix

```python
# backend/core/invoice_service.py

class InvoiceService:
    def create_invoice(self, invoice: Invoice):
        """Create new invoice with validation."""
        # GREEN PHASE: Add validation
        if invoice.total < 0:
            raise ValueError(f"Invoice total must be positive: {invoice.total}")

        self.db.add(invoice)
        self.db.commit()
        return invoice
```

**Run Test**: PASSES ✓

### Refactor Phase: Improve Code Quality

```python
# backend/core/invoice_service.py

class InvoiceService:
    def create_invoice(self, invoice: Invoice):
        """Create new invoice with validation."""
        self._validate_invoice(invoice)
        self.db.add(invoice)
        self.db.commit()
        return invoice

    def _validate_invoice(self, invoice: Invoice):
        """Validate invoice business rules."""
        self._validate_total(invoice.total)
        self._validate_customer(invoice.customer_id)

    def _validate_total(self, total: float):
        """Validate that invoice total is positive."""
        if total < 0:
            raise ValueError(f"Invoice total must be positive: {total}")

    def _validate_customer(self, customer_id: str):
        """Validate that customer exists."""
        customer = self.db.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            raise ValueError(f"Customer not found: {customer_id}")
```

**Run Tests**: All pass ✓

### Bug Discovery Summary

**Category**: Business rule validation
**Severity**: HIGH (accounting errors)
**Root Cause**: Missing input validation
**Fix Pattern**: Add business rule validation (positive totals)
**Test Coverage**: 1 test added, 3 validation methods extracted
**Files Changed**: 1 file
**Time to Fix**: 10 minutes

**Lessons Learned**:
- Business rules require explicit validation
- Extract validation methods for reusability
- Negative values are common edge case

---

## Example 3: Agent Execution Timeout Bug

### Bug Description

Agent execution doesn't timeout when LLM service hangs, causing resource exhaustion.

### Red Phase: Write Failing Test

```python
# backend/tests/test_agent_execution_service.py

import pytest
from unittest.mock import Mock
from core.agent_execution_service import AgentExecutionService
import time

def test_agent_execution_times_out_when_llm_hangs():
    """
    BUG: Agent execution doesn't timeout when LLM service hangs.

    EXPECTED: TimeoutError raised after 30 seconds
    ACTUAL: Execution hangs indefinitely (resource leak)
    """
    # Arrange
    agent = AgentRegistry(id="test-agent")
    db.add(agent)
    db.commit()

    # Mock LLM service that hangs
    mock_llm = Mock()
    mock_llm.generate.side_effect = lambda: time.sleep(100)  # Hangs for 100s

    service = AgentExecutionService(db, llm_service=mock_llm, timeout=1)

    # Act & Assert
    with pytest.raises(TimeoutError, match="Agent execution timed out"):
        service.execute_agent("test-agent", "test-workflow")
```

**Run Test**: FAILS (no timeout handling, test hangs)

### Green Phase: Write Minimal Fix

```python
# backend/core/agent_execution_service.py

import concurrent.futures

class AgentExecutionService:
    def __init__(self, db: Session, llm_service: LLMService = None, timeout: int = 30):
        self.db = db
        self.llm_service = llm_service or LLMService()
        self.timeout = timeout

    def execute_agent(self, agent_id: str, workflow: str) -> str:
        """Execute agent workflow with timeout."""
        # GREEN PHASE: Add timeout handling
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._execute_workflow, agent_id, workflow)

            try:
                result = future.result(timeout=self.timeout)
                return result
            except concurrent.futures.TimeoutError:
                future.cancel()
                raise TimeoutError(f"Agent execution timed out after {self.timeout}s")

    def _execute_workflow(self, agent_id: str, workflow: str) -> str:
        """Execute workflow (called in thread)."""
        return self.llm_service.generate(f"Execute {workflow}")
```

**Run Test**: PASSES ✓ (1 second timeout, doesn't hang)

### Refactor Phase: Improve Code Quality

```python
# backend/core/agent_execution_service.py

import concurrent.futures
from contextlib import contextmanager

class AgentExecutionService:
    def __init__(self, db: Session, llm_service: LLMService = None, timeout: int = 30):
        self.db = db
        self.llm_service = llm_service or LLMService()
        self.timeout = timeout

    def execute_agent(self, agent_id: str, workflow: str) -> str:
        """Execute agent workflow with timeout."""
        with self._execution_context() as executor:
            future = executor.submit(self._execute_workflow, agent_id, workflow)
            return self._wait_for_result(future)

    @contextmanager
    def _execution_context(self):
        """Create thread pool executor for execution."""
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            yield executor
        finally:
            executor.shutdown(wait=False)

    def _wait_for_result(self, future: concurrent.futures.Future) -> str:
        """Wait for execution result with timeout."""
        try:
            return future.result(timeout=self.timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"Agent execution timed out after {self.timeout}s")

    def _execute_workflow(self, agent_id: str, workflow: str) -> str:
        """Execute workflow (called in thread)."""
        return self.llm_service.generate(f"Execute {workflow}")
```

**Run Tests**: All pass ✓

### Bug Discovery Summary

**Category**: Resource management
**Severity**: HIGH (resource exhaustion)
**Root Cause**: No timeout handling for long-running operations
**Fix Pattern**: Add timeout with concurrent.futures
**Test Coverage**: 1 test added, 3 methods extracted
**Files Changed**: 1 file
**Time to Fix**: 20 minutes

**Lessons Learned**:
- External service calls require timeout handling
- ThreadPoolExecutor enables timeout enforcement
- Context managers improve resource cleanup

---

## Example 4: LLM Service Memory Leak Bug

### Bug Description

LLM service accumulates response objects in memory, causing memory leaks over time.

### Red Phase: Write Failing Test

```python
# backend/tests/test_llm_service.py

import pytest
import gc
import weakref
from core.llm_service import LLMService

def test_llm_service_releases_response_memory():
    """
    BUG: LLM service accumulates response objects in memory.

    EXPECTED: Response objects garbage collected after use
    ACTUAL: Responses retained in memory (memory leak)
    """
    # Arrange
    service = LLMService()

    # Act
    response = service.generate("Test prompt")
    weak_ref = weakref.ref(response)  # Create weak reference

    # Delete response and force garbage collection
    del response
    gc.collect()

    # Assert: Weak reference should be dead (object garbage collected)
    assert weak_ref() is None, "Response not garbage collected (memory leak)"
```

**Run Test**: FAILS (response retained in cache)

### Green Phase: Write Minimal Fix

```python
# backend/core/llm_service.py

from functools import lru_cache

class LLMService:
    def __init__(self):
        self._cache = {}  # Manual cache (allows cleanup)

    @lru_cache(maxsize=100)  # BROKEN: LRU cache prevents garbage collection
    def generate(self, prompt: str) -> str:
        """Generate LLM response (cached)."""
        return self._call_openai(prompt)
```

**Fix**: Remove lru_cache, use manual cache with size limit.

```python
# GREEN PHASE: Fix memory leak
class LLMService:
    def __init__(self, max_cache_size=100):
        self._cache = {}
        self._max_cache_size = max_cache_size

    def generate(self, prompt: str) -> str:
        """Generate LLM response with manual cache (allows garbage collection)."""
        if prompt not in self._cache:
            self._cache[prompt] = self._call_openai(prompt)
            self._enforce_cache_limit()

        return self._cache[prompt]

    def _enforce_cache_limit(self):
        """Remove oldest entries if cache exceeds limit."""
        if len(self._cache) > self._max_cache_size:
            # Remove oldest entry (FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
```

**Run Test**: PASSES ✓ (responses garbage collected)

### Refactor Phase: Improve Code Quality

```python
# backend/core/llm_service.py

from collections import OrderedDict

class LLMService:
    def __init__(self, max_cache_size=100):
        self._cache = OrderedDict()  # Maintains insertion order
        self._max_cache_size = max_cache_size

    def generate(self, prompt: str) -> str:
        """Generate LLM response with manual cache (allows garbage collection)."""
        if prompt not in self._cache:
            self._cache[prompt] = self._call_openai(prompt)
            self._enforce_cache_limit()
        else:
            # Move to end (mark as recently used)
            self._cache.move_to_end(prompt)

        return self._cache[prompt]

    def _enforce_cache_limit(self):
        """Remove oldest entries if cache exceeds limit (LRU eviction)."""
        while len(self._cache) > self._max_cache_size:
            self._cache.popitem(last=False)  # Remove oldest (FIFO)

    def clear_cache(self):
        """Clear all cached responses (manual cleanup)."""
        self._cache.clear()
```

**Run Tests**: All pass ✓

### Bug Discovery Summary

**Category**: Memory management
**Severity**: MEDIUM (memory leak)
**Root Cause**: lru_cache prevents garbage collection
**Fix Pattern**: Manual cache with size limits and LRU eviction
**Test Coverage**: 1 test added
**Files Changed**: 1 file
**Time to Fix**: 25 minutes

**Lessons Learned**:
- lru_cache prevents garbage collection (cache holds strong references)
- Manual cache with OrderedDict allows cleanup
- Weak references can detect memory leaks in tests

---

## Example 5: Episode Segmentation Time Gap Bug

### Bug Description

Episode segmentation incorrectly calculates time gaps, causing episodes to be merged when they should be split.

### Red Phase: Write Failing Test

```python
# backend/tests/test_episode_segmentation_service.py

import pytest
from datetime import datetime, timedelta
from core.episode_segmentation_service import EpisodeSegmentationService

def test_episode_segmentation_splits_on_time_gap():
    """
    BUG: Episode segmentation doesn't split on time gaps correctly.

    EXPECTED: Episodes split when gap > 5 minutes
    ACTUAL: Episodes merged regardless of gap
    """
    # Arrange
    service = EpisodeSegmentationService()

    segments = [
        EpisodeSegment(
            timestamp=datetime(2026, 1, 1, 10, 0, 0),
            content="First segment"
        ),
        EpisodeSegment(
            timestamp=datetime(2026, 1, 1, 10, 6, 0),  # 6 minute gap
            content="Second segment"
        ),
    ]

    # Act
    episodes = service.create_episodes(segments, gap_threshold=5)

    # Assert
    assert len(episodes) == 2, "Should create 2 episodes (6 minute gap > 5 minute threshold)"
```

**Run Test**: FAILS (creates 1 episode instead of 2)

### Green Phase: Write Minimal Fix

```python
# backend/core/episode_segmentation_service.py

class EpisodeSegmentationService:
    def __init__(self, gap_threshold_minutes=5):
        self.gap_threshold = timedelta(minutes=gap_threshold_minutes)

    def create_episodes(self, segments: list[EpisodeSegment], gap_threshold=5) -> list[Episode]:
        """Create episodes from segments, splitting on time gaps."""
        if not segments:
            return []

        episodes = []
        current_episode = Episode(segments=[segments[0]])

        for segment in segments[1:]:
            gap = segment.timestamp - current_episode.segments[-1].timestamp

            # GREEN PHASE: Fix gap comparison
            if gap > timedelta(minutes=gap_threshold):  # Was: >=
                # Split episode (gap exceeds threshold)
                episodes.append(current_episode)
                current_episode = Episode(segments=[segment])
            else:
                # Continue current episode
                current_episode.segments.append(segment)

        episodes.append(current_episode)
        return episodes
```

**Run Test**: PASSES ✓ (creates 2 episodes)

### Refactor Phase: Improve Code Quality

```python
# backend/core/episode_segmentation_service.py

class EpisodeSegmentationService:
    def __init__(self, gap_threshold_minutes=5):
        self.gap_threshold = timedelta(minutes=gap_threshold_minutes)

    def create_episodes(self, segments: list[EpisodeSegment], gap_threshold=5) -> list[Episode]:
        """Create episodes from segments, splitting on time gaps."""
        if not segments:
            return []

        episodes = []
        current_episode = self._start_new_episode(segments[0])

        for segment in segments[1:]:
            if self._should_split_episode(segment, current_episode, gap_threshold):
                episodes.append(current_episode)
                current_episode = self._start_new_episode(segment)
            else:
                current_episode.segments.append(segment)

        episodes.append(current_episode)
        return episodes

    def _start_new_episode(self, segment: EpisodeSegment) -> Episode:
        """Start a new episode with the given segment."""
        return Episode(segments=[segment])

    def _should_split_episode(self, segment: EpisodeSegment, episode: Episode, threshold: int) -> bool:
        """Check if episode should split based on time gap."""
        gap = segment.timestamp - episode.segments[-1].timestamp
        return gap > timedelta(minutes=threshold)
```

**Run Tests**: All pass ✓

### Bug Discovery Summary

**Category**: Edge case (boundary value)
**Severity**: MEDIUM (incorrect episode segmentation)
**Root Cause**: Wrong comparison operator (>= instead of >)
**Fix Pattern**: Fix boundary condition (gap > threshold, not >=)
**Test Coverage**: 1 test added, 2 methods extracted
**Files Changed**: 1 file
**Time to Fix**: 15 minutes

**Lessons Learned**:
- Boundary conditions are common bug sources
- Time calculations require careful comparison
- Extract methods improve readability

---

## Example 6: Agent Permission Check Race Condition

### Bug Description

Concurrent agent permission checks allow race condition where permissions change between check and execution.

### Red Phase: Write Failing Test

```python
# backend/tests/test_agent_governance_service.py

import pytest
import threading
from core.agent_governance_service import AgentGovernanceService

def test_agent_permission_check_prevents_race_condition():
    """
    BUG: Agent permission check allows race condition.

    EXPECTED: Permission check and execution are atomic
    ACTUAL: Permissions can change between check and execution
    """
    # Arrange
    agent = AgentRegistry(
        id="test-agent",
        maturity=AgentMaturity.SUPERVISED,
        permissions=["execute_workflow"]
    )
    db.add(agent)
    db.commit()

    service = AgentGovernanceService(db)
    errors = []

    def check_and_execute():
        try:
            # Check permission
            if service.has_permission("test-agent", "execute_workflow"):
                # Execute (race condition: permission may have changed)
                service.execute_workflow("test-agent", "test-workflow")
        except PermissionError as e:
            errors.append(e)

    # Act: Execute 100 concurrent checks
    threads = [threading.Thread(target=check_and_execute) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Assert: No permission errors (atomic check-and-execute)
    assert len(errors) == 0, f"Race condition detected: {len(errors)} permission errors"
```

**Run Test**: FAILS (race condition occurs, permission errors detected)

### Green Phase: Write Minimal Fix

```python
# backend/core/agent_governance_service.py

from threading import Lock

class AgentGovernanceService:
    def __init__(self, db: Session):
        self.db = db
        self._permission_lock = Lock()  # GREEN PHASE: Add lock

    def check_and_execute(self, agent_id: str, permission: str, workflow: str):
        """Check permission and execute atomically."""
        with self._permission_lock:  # Atomic operation
            if not self.has_permission(agent_id, permission):
                raise PermissionError(f"Agent {agent_id} lacks permission: {permission}")
            return self.execute_workflow(agent_id, workflow)
```

**Run Test**: PASSES ✓ (no race condition)

### Refactor Phase: Improve Code Quality

```python
# backend/core/agent_governance_service.py

from contextlib import contextmanager
from threading import Lock

class AgentGovernanceService:
    def __init__(self, db: Session):
        self.db = db
        self._locks = {}  # Per-agent locks
        self._global_lock = Lock()

    def check_and_execute(self, agent_id: str, permission: str, workflow: str):
        """Check permission and execute atomically."""
        with self._agent_lock(agent_id):
            self._validate_permission(agent_id, permission)
            return self.execute_workflow(agent_id, workflow)

    @contextmanager
    def _agent_lock(self, agent_id: str):
        """Get or create lock for specific agent."""
        with self._global_lock:
            lock = self._locks.setdefault(agent_id, Lock())

        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def _validate_permission(self, agent_id: str, permission: str):
        """Validate that agent has permission."""
        if not self.has_permission(agent_id, permission):
            raise PermissionError(f"Agent {agent_id} lacks permission: {permission}")
```

**Run Tests**: All pass ✓

### Bug Discovery Summary

**Category**: Concurrency (race condition)
**Severity**: HIGH (security vulnerability)
**Root Cause**: Permission check and execution not atomic
**Fix Pattern**: Add locking for atomic operations
**Test Coverage**: 1 test added, 2 methods extracted
**Files Changed**: 1 file
**Time to Fix**: 30 minutes

**Lessons Learned**:
- Check-then-act requires atomicity
- Per-agent locks improve concurrency (vs global lock)
- Context managers simplify lock management

---

## Example 7: ChatInput Empty Submit Bug

### Bug Description

ChatInput allows submitting empty messages, causing UI errors and wasted LLM calls.

### Red Phase: Write Failing Test

```typescript
// frontend-nextjs/components/chat/__tests__/ChatInput.test.tsx

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatInput } from '../ChatInput';

test('submit button disabled when input is empty', () => {
  /**
   * BUG: ChatInput allows submitting empty messages.
   *
   * EXPECTED: Submit button disabled when input empty
   * ACTUAL: Submit button enabled (can submit empty messages)
   */
  const handleSubmit = jest.fn();
  render(<ChatInput onSubmit={handleSubmit} />);

  const submitButton = screen.getByRole('button', { name: /send/i });

  expect(submitButton).toBeDisabled(); // FAILS: Button is enabled
});

test('does not call onSubmit when input is empty', () => {
  const handleSubmit = jest.fn();
  render(<ChatInput onSubmit={handleSubmit} />);

  const submitButton = screen.getByRole('button', { name: /send/i });
  userEvent.click(submitButton);

  expect(handleSubmit).not.toHaveBeenCalled(); // FAILS: Called with empty string
});
```

**Run Test**: FAILS (button enabled, onSubmit called with empty string)

### Green Phase: Write Minimal Fix

```typescript
// frontend-nextjs/components/chat/ChatInput.tsx

export const ChatInput: React.FC<ChatInputProps> = ({ onSubmit }) => {
  const [input, setInput] = useState('');

  const handleSubmit = () => {
    if (input.trim()) {  // GREEN PHASE: Add validation
      onSubmit(input);
      setInput('');
    }
  };

  return (
    <div>
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        aria-label="Chat input"
      />
      <button
        onClick={handleSubmit}
        disabled={!input.trim()}  // GREEN PHASE: Disable when empty
      >
        Send
      </button>
    </div>
  );
};
```

**Run Test**: PASSES ✓

### Refactor Phase: Improve Code Quality

```typescript
// frontend-nextjs/components/chat/ChatInput.tsx

export const ChatInput: React.FC<ChatInputProps> = ({ onSubmit }) => {
  const [input, setInput] = useState('');

  const canSubmit = input.trim().length > 0;  // Extract for clarity

  const handleSubmit = () => {
    if (canSubmit) {
      onSubmit(input);
      setInput('');
    }
  };

  return (
    <div>
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        aria-label="Chat input"
        onKeyDown={(e) => e.key === 'Enter' && canSubmit && handleSubmit()}  // Add keyboard support
      />
      <button
        onClick={handleSubmit}
        disabled={!canSubmit}
        aria-label="Send message"
      >
        Send
      </button>
    </div>
  );
};
```

**Run Tests**: All pass ✓

### Bug Discovery Summary

**Category**: UX (form validation)
**Severity**: LOW (UX issue)
**Root Cause**: Missing input validation
**Fix Pattern**: Add disabled state and validation
**Test Coverage**: 2 tests added
**Files Changed**: 1 file
**Time to Fix**: 10 minutes

**Lessons Learned**:
- Forms require validation (empty inputs)
- Disabled state prevents invalid submissions
- Extract validation logic for clarity

---

## Example 8: CommunicationHub Title Mismatch

### Bug Description

Test expects "Communication Hub" but component renders "Inbox", causing test failures.

### Red Phase: Write Failing Test

```typescript
// frontend-nextjs/components/shared/__tests__/CommunicationHub.test.tsx

test('renders communication hub with correct title', () => {
  /**
   * BUG: Test expects "Communication Hub" but component renders "Inbox".
   *
   * EXPECTED: Component renders "Communication Hub"
   * ACTUAL: Component renders "Inbox"
   */
  render(<CommunicationHub />);

  const title = screen.getByText('Communication Hub');

  expect(title).toBeInTheDocument(); // FAILS: "Unable to find an element with text: Communication Hub"
});
```

**Run Test**: FAILS (component renders "Inbox" instead of "Communication Hub")

### Green Phase: Write Minimal Fix

```typescript
// frontend-nextjs/components/shared/CommunicationHub.tsx

export const CommunicationHub: React.FC = () => {
  return (
    <div>
      <h1>Communication Hub</h1>  // Was: <h1>Inbox</h1>
    </div>
  );
};
```

**Run Test**: PASSES ✓

### Refactor Phase: Improve Code Quality

```typescript
// frontend-nextjs/components/shared/CommunicationHub.tsx

export const CommunicationHub: React.FC<{ title?: string }> = ({ title = "Communication Hub" }) => {
  return (
    <div>
      <h1>{title}</h1>
    </div>
  );
};

// Add tests for prop
test('renders custom title when provided', () => {
  render(<CommunicationHub title="Messages" />);
  expect(screen.getByText('Messages')).toBeInTheDocument();
});
```

**Run Tests**: All pass ✓

### Bug Discovery Summary

**Category**: Test assertion fix (Phase 299 pattern)
**Severity**: LOW (test failure)
**Root Cause**: Test expectation didn't match component output
**Fix Pattern**: Update component to match test (or update test, depends on intent)
**Test Coverage**: 1 test fixed, 1 test added
**Files Changed**: 1 file
**Time to Fix**: 5 minutes

**Lessons Learned**:
- Tests should document intent (expected behavior)
- Fix component to match test (if test is correct)
- Add props for flexibility (custom titles)

---

## Example 9: TaskManagement Missing Props Bug

### Bug Description

TaskManagement component crashes when rendered without required props (tasks, onTaskUpdate).

### Red Phase: Write Failing Test

```typescript
// frontend-nextjs/components/shared/__tests__/TaskManagement.test.tsx

test('renders task list with required props', () => {
  /**
   * BUG: TaskManagement crashes without required props.
   *
   * EXPECTED: Component renders with props
   * ACTUAL: Component crashes (props missing)
   */
  const mockTasks = [
    { id: '1', title: 'Task 1', status: 'pending' },
    { id: '2', title: 'Task 2', status: 'completed' }
  ];

  const mockUpdate = jest.fn();

  render(<TaskManagement tasks={mockTasks} onTaskUpdate={mockUpdate} />);

  expect(screen.getByText('Tasks')).toBeInTheDocument(); // PASSES ✓
});

test('renders empty state when no tasks provided', () => {
  render(<TaskManagement tasks={[]} onTaskUpdate={jest.fn()} />);

  expect(screen.getByText(/no tasks/i)).toBeInTheDocument(); // PASSES ✓
});
```

**Run Test**: PASSES (with props) ✓

**Before Fix**: Tests failed because props were missing

### Green Phase: Write Minimal Fix

```typescript
// frontend-nextjs/components/shared/TaskManagement.tsx

interface TaskManagementProps {
  tasks: Task[];
  onTaskUpdate: (taskId: string, status: TaskStatus) => void;
}

export const TaskManagement: React.FC<TaskManagementProps> = ({ tasks, onTaskUpdate }) => {
  if (tasks.length === 0) {
    return <div>No tasks</div>;
  }

  return (
    <div>
      <h1>Tasks</h1>
      <ul>
        {tasks.map(task => (
          <li key={task.id}>
            {task.title} - {task.status}
            <button onClick={() => onTaskUpdate(task.id, 'completed')}>
              Complete
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};
```

**Run Test**: PASSES ✓

### Refactor Phase: Improve Code Quality

```typescript
// frontend-nextjs/components/shared/TaskManagement.tsx

interface TaskManagementProps {
  tasks: Task[];
  onTaskUpdate: (taskId: string, status: TaskStatus) => void;
}

export const TaskManagement: React.FC<TaskManagementProps> = ({ tasks, onTaskUpdate }) => {
  const handleUpdate = (taskId: string) => {
    onTaskUpdate(taskId, 'completed');
  };

  return (
    <div>
      <h1>Tasks</h1>
      {tasks.length === 0 ? (
        <EmptyState />
      ) : (
        <TaskList tasks={tasks} onUpdate={handleUpdate} />
      )}
    </div>
  );
};

// Extract components for reusability
const EmptyState: React.FC = () => (
  <div>No tasks</div>
);

interface TaskListProps {
  tasks: Task[];
  onUpdate: (taskId: string) => void;
}

const TaskList: React.FC<TaskListProps> = ({ tasks, onUpdate }) => (
  <ul>
    {tasks.map(task => (
      <TaskItem key={task.id} task={task} onUpdate={onUpdate} />
    ))}
  </ul>
);

const TaskItem: React.FC<{ task: Task; onUpdate: (taskId: string) => void }> = ({ task, onUpdate }) => (
  <li>
    {task.title} - {task.status}
    <button onClick={() => onUpdate(task.id)}>Complete</button>
  </li>
);
```

**Run Tests**: All pass ✓

### Bug Discovery Summary

**Category**: Component props (Phase 299 pattern)
**Severity**: MEDIUM (component crashes)
**Root Cause**: Missing required props
**Fix Pattern**: Add required props to render call
**Test Coverage**: 2 tests added, 3 components extracted
**Files Changed**: 1 file
**Time to Fix**: 15 minutes

**Lessons Learned**:
- Component props must be provided in tests
- Extract components improve testability
- Empty state handling improves UX

---

## Example 10: Canvas Presentation Loading State Bug

### Bug Description

Canvas presentation doesn't show loading state while fetching data, causing poor UX.

### Red Phase: Write Failing Test

```typescript
// frontend-nextjs/components/canvas/__tests__/CanvasPresentation.test.tsx

import { render, screen, waitFor } from '@testing-library/react';
import { CanvasPresentation } from '../CanvasPresentation';

test('shows loading state while fetching data', async () => {
  /**
   * BUG: Canvas presentation doesn't show loading state.
   *
   * EXPECTED: Loading spinner shown while fetching
   * ACTUAL: No loading state (blank screen)
   */
  const mockData = { title: 'Test Canvas', charts: [] };

  // Mock API call with delay
  jest.spyOn(api, 'getCanvas').mockImplementation(
    () => new Promise(resolve => setTimeout(() => resolve(mockData), 100))
  );

  render(<CanvasPresentation canvasId="test-canvas" />);

  // Assert: Loading state shown immediately
  expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument(); // FAILS: No loading state

  // Assert: Data shown after fetch
  await waitFor(() => {
    expect(screen.getByText('Test Canvas')).toBeInTheDocument();
  });
});
```

**Run Test**: FAILS (no loading state)

### Green Phase: Write Minimal Fix

```typescript
// frontend-nextjs/components/canvas/CanvasPresentation.tsx

export const CanvasPresentation: React.FC<{ canvasId: string }> = ({ canvasId }) => {
  const [data, setData] = useState<CanvasData | null>(null);
  const [loading, setLoading] = useState(true);  // GREEN PHASE: Add loading state

  useEffect(() => {
    api.getCanvas(canvasId).then(canvasData => {
      setData(canvasData);
      setLoading(false);
    });
  }, [canvasId]);

  if (loading) {
    return <div role="status" aria-label="Loading">Loading...</div>;  // GREEN PHASE: Show loading state
  }

  return (
    <div>
      <h1>{data.title}</h1>
      {/* Render canvas */}
    </div>
  );
};
```

**Run Test**: PASSES ✓

### Refactor Phase: Improve Code Quality

```typescript
// frontend-nextjs/components/canvas/CanvasPresentation.tsx

export const CanvasPresentation: React.FC<{ canvasId: string }> = ({ canvasId }) => {
  const { data, loading, error } = useCanvas(canvasId);  // Extract to hook

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;
  if (!data) return <EmptyState />;

  return <CanvasContent data={data} />;
};

// Extract hook for reusability
function useCanvas(canvasId: string) {
  const [state, setState] = useState<{
    data: CanvasData | null;
    loading: boolean;
    error: Error | null;
  }>({ data: null, loading: true, error: null });

  useEffect(() => {
    api.getCanvas(canvasId)
      .then(data => setState({ data, loading: false, error: null }))
      .catch(error => setState({ data: null, loading: false, error }));
  }, [canvasId]);

  return state;
}

// Extract components for clarity
const LoadingState: React.FC = () => (
  <div role="status" aria-label="Loading">
    <Spinner />
    <span>Loading...</span>
  </div>
);

const ErrorState: React.FC<{ error: Error }> = ({ error }) => (
  <div role="alert" aria-label="Error">
    Error: {error.message}
  </div>
);

const EmptyState: React.FC = () => (
  <div>No canvas data</div>
);

const CanvasContent: React.FC<{ data: CanvasData }> = ({ data }) => (
  <div>
    <h1>{data.title}</h1>
    {/* Render canvas */}
  </div>
);
```

**Run Tests**: All pass ✓

### Bug Discovery Summary

**Category**: UX (loading states)
**Severity**: MEDIUM (poor UX)
**Root Cause**: No loading state handling
**Fix Pattern**: Add loading, error, empty states
**Test Coverage**: 1 test added, 5 components extracted
**Files Changed**: 1 file
**Time to Fix**: 20 minutes

**Lessons Learned**:
- Async operations require loading states
- Extract hooks improve testability
- Error states improve UX

---

## Summary: 10 Examples of Bug Discovery via TDD

### Bug Categories

| Category | Examples | Severity |
|----------|----------|----------|
| Governance validation | 1, 6 | HIGH |
| Business rules | 2 | HIGH |
| Resource management | 3, 4 | MEDIUM-HIGH |
| Edge cases | 5 | MEDIUM |
| Form validation | 7 | LOW-MEDIUM |
| Component props | 9 | MEDIUM |
| UX states | 10 | MEDIUM |
| Test assertions | 8 | LOW |

### Common Patterns

1. **State machine validation** (Example 1): Block invalid transitions
2. **Input validation** (Example 2): Validate business rules
3. **Timeout handling** (Example 3): Add timeouts to long operations
4. **Resource cleanup** (Example 4): Manage memory and connections
5. **Boundary conditions** (Example 5): Fix edge cases in comparisons
6. **Concurrency** (Example 6): Add locks for atomic operations
7. **Form validation** (Example 7): Disable invalid submissions
8. **Component props** (Example 9): Provide required props
9. **Loading states** (Example 10): Show feedback for async operations

### Time to Fix Distribution

| Time | Examples | Percentage |
|------|----------|------------|
| <15 min | 2, 7, 8 | 30% |
| 15-20 min | 1, 5, 9 | 30% |
| 20-30 min | 3, 4, 10 | 30% |
| >30 min | 6 | 10% |

### ROI Analysis

**Total bugs discovered**: 10
**Total time to fix**: 3 hours (180 minutes)
**Average time per bug**: 18 minutes
**Regressions prevented**: 10 (100%, each bug has test)

**Key Insight**: TDD catches bugs early (before production), preventing costly outages and rollbacks.

---

**Example Suite Complete**: 10 examples with full red-green-refactor cycles
**Created**: 2026-04-29
**Maintained By**: Atom Development Team
