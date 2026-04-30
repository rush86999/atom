# TDD Workshop: Hands-On Training

**Duration**: 3 hours
**Audience**: Atom development team
**Prerequisites**: Laptop with Python/TypeScript installed
**Goal**: Practical experience with red-green-refactor cycle

---

## Workshop Schedule

| Time | Section | Activity |
|------|---------|----------|
| 0:00-0:30 | Introduction | TDD overview, philosophy, benefits |
| 0:30-1:30 | Exercise 1 | Backend bug fix (Python) |
| 1:30-2:30 | Exercise 2 | Frontend component (TypeScript) |
| 2:30-3:00 | Review | Debrief, Q&A, next steps |

---

## Part 1: Introduction (30 minutes)

### What is TDD?

**Definition**: Test-Driven Development (TDD) is writing tests **before** implementation code.

**The Cycle**:
```
RED → GREEN → REFACTOR
```

1. **RED**: Write failing test
2. **GREEN**: Make it pass
3. **REFACTOR**: Improve code

**Why TDD?**
- Catches bugs early (before production)
- Prevents regression (tests ensure bugs don't reoccur)
- Enables confident refactoring (tests catch breakage)
- Improves design (tests drive API design)

### Atom v12.0 Success Stories

**Phase 299**: Frontend pass rate 71.5% → 80.0% (+265 tests)
- Used systematic TDD approach
- 100% pass rate on target files
- 6x better ROI than infrastructure-only fixes

**Phase 298**: Backend 100% pass rate (75/75 tests)
- Exceptional success
- Coverage 54% (+7pp above target)

### Key Principles

1. **Test First**: Write test before implementation
2. **Fail First**: Verify test fails with expected error
3. **Minimal Fix**: Write simplest code to pass
4. **Refactor**: Improve while tests pass
5. **All Bugs Use TDD**: No exceptions

### Common Anti-Patterns

❌ **Testing Implementation Details**:
- Testing private methods
- Testing component state
- Asserting on mock calls

✅ **Testing Behavior**:
- Testing public APIs
- Testing user interactions
- Asserting on observable effects

---

## Part 2: Exercise 1 - Backend Bug Fix (60 minutes)

### Scenario

Agent maturity validation allows demotion from AUTONOMOUS to STUDENT, bypassing graduation requirements.

### Learning Objectives

- Practice red-green-refactor cycle
- Write failing test that reproduces bug
- Implement minimal fix
- Refactor for clarity

### Setup

```bash
# Clone repository
cd /path/to/atom/backend

# Create test file
touch tests/test_agent_maturity_bug.py
```

### Step 1: RED (15 minutes)

**Task**: Write failing test that reproduces bug.

```python
# tests/test_agent_maturity_bug.py

import pytest
from core.models import AgentRegistry, AgentMaturity
from core.agent_governance_service import AgentGovernanceService
from sqlalchemy.orm import Session

def test_agent_maturity_blocks_demotion():
    """
    BUG: Agent maturity allows demotion from AUTONOMOUS to STUDENT.

    EXPECTED: ValueError raised (demotion not allowed)
    ACTUAL: Demotion succeeds (security risk)
    """
    # Arrange
    agent = AgentRegistry(
        id="workshop-agent",
        maturity=AgentMaturity.AUTONOMOUS
    )

    with SessionLocal() as db:
        db.add(agent)
        db.commit()

        service = AgentGovernanceService(db)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid maturity transition"):
            service.update_maturity("workshop-agent", AgentMaturity.STUDENT)
```

**Run Test**:
```bash
pytest tests/test_agent_maturity_bug.py -v
```

**Expected Output**:
```
FAILED - Test did not raise ValueError
```

### Step 2: GREEN (15 minutes)

**Task**: Write minimal fix to make test pass.

```python
# core/agent_governance_service.py

def update_maturity(self, agent_id: str, new_maturity: AgentMaturity):
    """Update agent maturity level."""
    agent = self.db.query(AgentRegistry).filter_by(id=agent_id).first()

    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    # Add validation to block demotion
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
            f"Invalid maturity transition: {agent.maturity} → {new_maturity}"
        )

    agent.maturity = new_maturity
    self.db.commit()
```

**Run Test**:
```bash
pytest tests/test_agent_maturity_bug.py -v
```

**Expected Output**:
```
PASSED ✓
```

### Step 3: REFACTOR (15 minutes)

**Task**: Improve code structure while tests pass.

```python
# core/agent_governance_service.py

class AgentGovernanceService:
    def update_maturity(self, agent_id: str, new_maturity: AgentMaturity):
        """Update agent maturity level with validation."""
        agent = self._get_agent(agent_id)
        self._validate_maturity_transition(agent.maturity, new_maturity)

        agent.maturity = new_maturity
        self.db.commit()

    def _get_agent(self, agent_id: str) -> AgentRegistry:
        """Fetch agent by ID."""
        agent = self.db.query(AgentRegistry).filter_by(id=agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        return agent

    def _validate_maturity_transition(self, current, new):
        """Validate that maturity transition is allowed (no demotion)."""
        if self._is_demotion(current, new):
            raise ValueError(
                f"Invalid maturity transition: {current} → {new}"
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

**Run Tests**:
```bash
pytest tests/test_agent_maturity_bug.py -v
```

**Expected Output**:
```
PASSED ✓
```

### Step 4: Debrief (15 minutes)

**Discussion Questions**:
1. Was it hard to write the test first?
2. Did the test fail as expected?
3. Was the minimal fix simple enough?
4. Did refactoring improve clarity?

**Key Takeaways**:
- Test first forces you to think about API design
- Failing test validates bug exists
- Minimal fix prevents over-engineering
- Refactoring improves code quality

---

## Part 3: Exercise 2 - Frontend Component (60 minutes)

### Scenario

ChatInput component allows submitting empty messages, causing UI errors.

### Learning Objectives

- Practice TDD for React components
- Use React Testing Library
- Test user interactions (not implementation)
- Use accessible queries

### Setup

```bash
# Navigate to frontend
cd /path/to/atom/frontend-nextjs

# Create test file
mkdir -p components/chat/__tests__
touch components/chat/__tests__/ChatInput.test.tsx
```

### Step 1: RED (15 minutes)

**Task**: Write failing test for empty submit.

```typescript
// components/chat/__tests__/ChatInput.test.tsx

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

**Run Test**:
```bash
npm test -- ChatInput.test.tsx
```

**Expected Output**:
```
FAILED - Button is not disabled
FAILED - onSubmit was called
```

### Step 2: GREEN (15 minutes)

**Task**: Implement minimal fix.

```typescript
// components/chat/ChatInput.tsx

import { useState } from 'react';

interface ChatInputProps {
  onSubmit: (message: string) => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSubmit }) => {
  const [input, setInput] = useState('');

  const handleSubmit = () => {
    if (input.trim()) {  // Add validation
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
        disabled={!input.trim()}  // Disable when empty
      >
        Send
      </button>
    </div>
  );
};
```

**Run Test**:
```bash
npm test -- ChatInput.test.tsx
```

**Expected Output**:
```
PASSED ✓
PASSED ✓
```

### Step 3: REFACTOR (15 minutes)

**Task**: Extract logic for clarity.

```typescript
// components/chat/ChatInput.tsx

import { useState } from 'react';

interface ChatInputProps {
  onSubmit: (message: string) => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSubmit }) => {
  const [input, setInput] = useState('');

  const canSubmit = input.trim().length > 0;  // Extract for clarity

  const handleSubmit = () => {
    if (canSubmit) {
      onSubmit(input);
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && canSubmit) {  // Add keyboard support
      handleSubmit();
    }
  };

  return (
    <div>
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        aria-label="Chat input"
        role="textbox"
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

**Run Tests**:
```bash
npm test -- ChatInput.test.tsx
```

**Expected Output**:
```
PASSED ✓
```

### Step 4: Debrief (15 minutes)

**Discussion Questions**:
1. Why use `getByRole` instead of `getByTestId`?
2. Why test user behavior, not component state?
3. Did `canSubmit` extraction improve clarity?
4. What's the benefit of keyboard support?

**Key Takeaways**:
- Accessible queries test accessibility (`getByRole`)
- Test user interactions (click, type), not state
- Extract logic improves testability
- Refactoring adds features (keyboard support)

---

## Part 4: Review & Q&A (30 minutes)

### Workshop Recap

**What We Learned**:
1. Red-green-refactor cycle (write test → make pass → improve)
2. Test first validates bug exists
3. Minimal fix prevents over-engineering
4. Refactoring improves code quality
5. Tests prevent regression

### Common Questions

**Q: Do I always have to write tests first?**
A: For bug fixes and public APIs, yes (100%). For exploratory coding, test-after is acceptable.

**Q: What if I don't know how to implement the feature?**
A: Write test first, it forces you to think about API design. Implementation becomes obvious.

**Q: Isn't TDD slower?**
A: Initially yes, but long-term it's faster (fewer bugs, confident refactoring, less debugging).

**Q: How do I test async code?**
A: Use `async/await` in tests, mock async operations, use `waitFor` for frontend.

**Q: What if tests are flaky (sometimes fail)?**
A: Flaky tests are worse than no tests. Fix flaky tests before adding new ones.

### Next Steps

1. **Practice**: Use TDD for next bug fix
2. **Pair Program**: Work with TDD-experienced developer
3. **Code Reviews**: Enforce TDD compliance (use checklist)
4. **Read Examples**: Review `/docs/testing/TDD_EXAMPLES/`
5. **Ask Questions**: Reach out to TDD champions

### Resources

- **Full Guide**: `/docs/testing/TDD_METHODOLOGY.md`
- **Quick Reference**: `/docs/testing/TDD_QUICK_REFERENCE.md`
- **Examples**: `/docs/testing/TDD_EXAMPLES/`
- **Code Review**: `/docs/testing/TDD_CODE_REVIEW_CHECKLIST.md`

---

## Appendix: Troubleshooting

### Test Won't Fail

**Problem**: Test passes immediately (no red phase)

**Solution**:
1. Verify test is testing the right thing
2. Check if bug actually exists
3. Ensure test is running (not skipped)
4. Check test isolation (no shared state)

### Test Won't Pass

**Problem**: Test keeps failing despite implementation

**Solution**:
1. Verify implementation is correct
2. Check test expectations (are they realistic?)
3. Debug test (add print statements)
4. Check mocks (are they returning correct values?)

### Refactoring Breaks Tests

**Problem**: Tests fail after refactoring

**Solution**:
1. Revert refactoring (tests should pass)
2. Refactor in smaller steps
3. Ensure only structure changes (no behavior)
4. Run tests after each small change

---

## Feedback

**Please provide feedback on this workshop**:
- What was helpful?
- What was confusing?
- What should be added/removed?
- Overall rating (1-5)

**Send feedback to**: [Team Lead / TDD Champion]

---

*Workshop created for Atom v12.0*
*Goal: Hands-on TDD training for development team*
*Duration: 3 hours*
