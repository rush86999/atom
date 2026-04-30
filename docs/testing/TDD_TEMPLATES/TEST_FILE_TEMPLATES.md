# TDD Test File Templates

**Purpose**: Reusable templates for writing tests in Atom v12.0.

**Version**: 1.0

---

## Backend Test Template (Python/pytest)

### File Structure

```python
# backend/tests/test_<feature>_service.py

"""
Test suite for <Feature>Service.

This test suite covers:
- <Primary functionality>
- <Error cases>
- <Edge cases>
"""

import pytest
from core.<feature>_service import <Feature>Service
from core.models import <RelatedModel>
from sqlalchemy.orm import Session


class Test<Feature>Service:
    """Test suite for <Feature>Service."""

    def setup_method(self):
        """Setup test fixtures before each test."""
        self.service = <Feature>Service(db)

    def test_<behavior>_when_<condition>(self):
        """
        Test <behavior> when <condition>.

        SCENARIO: <Describe scenario>
        EXPECTED: <Expected result>
        ACTUAL: <Actual result if bug>
        """
        # Arrange
        input_data = ...

        # Act
        result = self.service.<method>(input_data)

        # Assert
        assert result == expected_value

    def test_<error_case>_raises_<error>(self):
        """
        Test that <error case> raises <error>.

        SCENARIO: <Describe scenario>
        EXPECTED: <Error> raised with message
        ACTUAL: <Actual result if bug>
        """
        # Arrange
        invalid_input = ...

        # Act & Assert
        with pytest.raises(<Error>, match="<expected message>"):
            self.service.<method>(invalid_input)
```

### Example: Agent Governance Service

```python
# backend/tests/test_agent_governance_service.py

"""
Test suite for AgentGovernanceService.

This test suite covers:
- Agent maturity transitions
- Permission checks
- Agent lifecycle management
"""

import pytest
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentMaturity
from sqlalchemy.orm import Session


class TestAgentGovernanceService:
    """Test suite for AgentGovernanceService."""

    def setup_method(self):
        """Setup test fixtures before each test."""
        self.service = AgentGovernanceService(db)

    def test_update_maturity_allows_valid_transitions(self):
        """
        Test valid maturity transition succeeds.

        SCENARIO: Upgrade agent from INTERN to SUPERVISED
        EXPECTED: Maturity updated successfully
        """
        # Arrange
        agent = AgentRegistry(
            id="test-agent",
            maturity=AgentMaturity.INTERN
        )
        db.add(agent)
        db.commit()

        # Act
        self.service.update_maturity("test-agent", AgentMaturity.SUPERVISED)

        # Assert
        assert agent.maturity == AgentMaturity.SUPERVISED

    def test_update_maturity_blocks_demotion(self):
        """
        Test that maturity demotion is blocked.

        SCENARIO: Demote agent from AUTONOMOUS to STUDENT
        EXPECTED: ValueError raised (demotion not allowed)
        ACTUAL: Demotion succeeds (security risk)
        """
        # Arrange
        agent = AgentRegistry(
            id="test-agent",
            maturity=AgentMaturity.AUTONOMOUS
        )
        db.add(agent)
        db.commit()

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid maturity transition"):
            self.service.update_maturity("test-agent", AgentMaturity.STUDENT)
```

---

## Frontend Test Template (TypeScript/React Testing Library)

### File Structure

```typescript
// frontend-nextjs/components/<feature>/__tests__/<Component>.test.tsx

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { <Component> } from '../<Component>';

describe('<Component>', () => {
  /**
   * Test suite for <Component>.
   *
   * This test suite covers:
   * - <Primary functionality>
   * - <User interactions>
   * - <Error cases>
   */

  test('<behavior> when <condition>', () => {
    /**
     * Test <behavior> when <condition>.
     *
     * SCENARIO: <Describe scenario>
     * EXPECTED: <Expected result>
     * ACTUAL: <Actual result if bug>
     */
    // Arrange
    const mockProps = {
      prop1: 'value1',
      onAction: jest.fn(),
    };

    // Act
    render(<<Component> {...mockProps} />);

    // Assert
    expect(screen.getByRole('<role>', { name: /<name>/i })).toBeInTheDocument();
  });

  test('calls <callback> when <interaction>', () => {
    /**
     * Test user interaction triggers callback.
     *
     * SCENARIO: <Describe scenario>
     * EXPECTED: <Callback> called with <args>
     * ACTUAL: <Actual result if bug>
     */
    // Arrange
    const mockCallback = jest.fn();
    render(<<Component> onAction={mockCallback} />);

    // Act
    const button = screen.getByRole('button', { name: /<label>/i });
    userEvent.click(button);

    // Assert
    expect(mockCallback).toHaveBeenCalledWith('<expected-arg>');
  });
});
```

### Example: ChatInput Component

```typescript
// frontend-nextjs/components/chat/__tests__/ChatInput.test.tsx

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatInput } from '../ChatInput';

describe('ChatInput', () => {
  /**
   * Test suite for ChatInput component.
   *
   * This test suite covers:
   * - User input handling
   * - Submit validation
   * - Keyboard interactions
   */

  test('renders input and submit button', () => {
    /**
     * Test component renders correctly.
     *
     * SCENARIO: Component mounted
     * EXPECTED: Input textbox and submit button visible
     */
    render(<ChatInput onSubmit={jest.fn()} />);

    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
  });

  test('calls onSubmit with message when submitted', () => {
    /**
     * Test form submission triggers callback.
     *
     * SCENARIO: User types message and clicks submit
     * EXPECTED: onSubmit called with message
     */
    const handleSubmit = jest.fn();
    render(<ChatInput onSubmit={handleSubmit} />);

    const input = screen.getByRole('textbox');
    const button = screen.getByRole('button', { name: /send/i });

    userEvent.type(input, 'Hello, world!');
    userEvent.click(button);

    expect(handleSubmit).toHaveBeenCalledWith('Hello, world!');
  });

  test('disables submit button when input is empty', () => {
    /**
     * Test submit button disabled validation.
     *
     * SCENARIO: Input is empty
     * EXPECTED: Submit button disabled
     * ACTUAL: Submit button enabled (can submit empty messages)
     */
    render(<ChatInput onSubmit={jest.fn()} />);

    const button = screen.getByRole('button', { name: /send/i });

    expect(button).toBeDisabled();
  });
});
```

---

## Integration Test Template (Python)

### File Structure

```python
# backend/tests/integration/test_<workflow>.py

"""
Integration test suite for <workflow>.

This test suite covers:
- End-to-end workflow execution
- Component interactions
- API contracts
"""

import pytest
from core.<service> import <Service>
from core.models import <Model>


class Test<Workflow>Integration:
    """Integration test suite for <workflow>."""

    def test_<workflow>_creates_<entity>_and_updates_status(self):
        """
        Test <workflow> end-to-end.

        SCENARIO: <Describe workflow>
        EXPECTED: <Entity> created and status updated
        """
        # Arrange
        <initial_state>

        # Act
        service = <Service>(db)
        result = service.<workflow>(<input>)

        # Assert
        <entity> = db.query(<Model>).filter_by(<condition>).first()
        assert <entity> is not None
        assert <entity>.status == <ExpectedStatus>
```

### Example: Agent Execution Workflow

```python
# backend/tests/integration/test_agent_execution.py

"""
Integration test suite for agent execution workflow.

This test suite covers:
- Agent execution end-to-end
- LLM service integration
- Execution record creation
"""

import pytest
from core.agent_execution_service import AgentExecutionService
from core.models import AgentRegistry, AgentExecution, ExecutionStatus


class TestAgentExecutionIntegration:
    """Integration test suite for agent execution."""

    def test_agent_execution_creates_record_and_updates_status(self):
        """
        Test agent execution workflow end-to-end.

        SCENARIO: Execute agent workflow
        EXPECTED: Execution record created and status updated to COMPLETED
        """
        # Arrange
        agent = AgentRegistry(
            id="test-agent",
            maturity=AgentMaturity.AUTONOMOUS
        )
        db.add(agent)
        db.commit()

        # Act
        service = AgentExecutionService(db)
        execution_id = service.execute_agent("test-agent", "test-workflow")

        # Assert
        execution = db.query(AgentExecution).filter_by(id=execution_id).first()
        assert execution is not None
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.agent_id == "test-agent"
```

---

## Property Test Template (Python/hypothesis)

### File Structure

```python
# backend/tests/property_tests/test_<invariants>.py

"""
Property-based test suite for <invariants>.

This test suite covers:
- <Invariant 1>
- <Invariant 2>
- <Invariant 3>
"""

from hypothesis import given, strategies as st
import pytest


class Test<Invariants>:
    """Property-based test suite for <invariants>."""

    @given(st.<type>(min_value=<min>, max_value=<max>))
    def test_<invariant>_holds_for_all_<input>(self, <input>):
        """
        Test that <invariant> holds for all <input>.

        INVARIANT: <Describe invariant>
        SCENARIO: <Input> varies across range
        EXPECTED: <Invariant> always holds
        """
        # Arrange
        <setup>

        # Act
        result = <function>(<input>)

        # Assert
        assert <invariant_check>(result)
```

### Example: Agent ID Uniqueness

```python
# backend/tests/property_tests/test_agent_invariants.py

"""
Property-based test suite for agent invariants.

This test suite covers:
- Agent ID uniqueness
- Invoice total positivity
- Maturity transition validity
"""

from hypothesis import given, strategies as st
import pytest


class TestAgentInvariants:
    """Property-based test suite for agent invariants.*/

    @given(st.text(min_size=1, max_size=100))
    def test_agent_id_is_always_unique(self, agent_id):
        """
        Test that agent IDs are unique.

        INVARIANT: No two agents can have the same ID
        SCENARIO: Create agents with same ID
        EXPECTED: Second creation raises IntegrityError
        """
        # Arrange
        agent1 = AgentRegistry(id=agent_id)

        with SessionLocal() as db:
            db.add(agent1)
            db.commit()

            # Act
            agent2 = AgentRegistry(id=agent_id)
            db.add(agent2)

            # Assert
            with pytest.raises(IntegrityError):
                db.commit()
```

---

## Test Checklist

Before committing test code, verify:

### Backend Tests (Python)
- [ ] Test file named `test_*.py`
- [ ] Test class named `Test<Feature>`
- [ ] Test methods named `test_<behavior>`
- [ ] Docstrings describe scenario, expected, actual
- [ ] Uses `pytest.raises` for error cases
- [ ] Only mocks external dependencies
- [ ] Tests are independent (no shared state)

### Frontend Tests (TypeScript)
- [ ] Test file named `<Component>.test.tsx`
- [ ] Uses `describe` for test suite
- [ ] Uses `test` for individual tests
- [ ] Docstrings describe scenario, expected, actual
- [ ] Uses `getByRole`, `getByLabelText` (not `getByTestId`)
- [ ] Uses `userEvent` (not `fireEvent`)
- [ ] Tests user behavior (not component state)

---

*Test File Templates created for Atom v12.0*
*Purpose: Standardize test structure across codebase*
