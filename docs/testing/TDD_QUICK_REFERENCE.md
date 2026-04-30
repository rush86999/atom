# TDD Quick Reference Guide

**Version**: 1.0
**Milestone**: v12.0 TDD & Quality Culture

---

## Red-Green-Refactor Cycle

```
┌─────────┐    ┌─────────┐    ┌─────────┐
│   RED   │ → │  GREEN  │ → │REFACTOR │
└─────────┘    └─────────┘    └─────────┘
Write Failing  Make Pass     Improve
Test          Test          Code
```

### 1. RED (Write Failing Test)
- Write test that exposes bug or specifies behavior
- Run test, verify it fails with expected error
- **Key**: Test must fail before implementation (validates test works)

### 2. GREEN (Make Test Pass)
- Write minimal code to make test pass
- Don't add features yet (YAGNI)
- Hardcode values if necessary

### 3. REFACTOR (Improve Code)
- Improve code structure while tests pass
- Extract methods, rename, simplify
- **Key**: Tests must still pass (no behavior changes)

---

## When to Use TDD

### Test-First (Always)
- ✅ Bug fixes (ALL bug fixes use TDD)
- ✅ Public APIs (REST, GraphQL)
- ✅ Complex business logic
- ✅ Database migrations
- ✅ Security/governance features

### Test-After (Exceptions)
- 🔄 Exploratory coding (spikes)
- 🔄 UI prototypes (throwaway)
- 🔄 Emergency fixes (add tests after)
- 🔄 Refactoring legacy code (characterization tests)

---

## Common TDD Patterns

### API Endpoints (Python/FastAPI)
```python
# RED: Test API contract
def test_create_agent_returns_201():
    response = client.post("/api/v1/agents", json={"name": "Test"})
    assert response.status_code == 201

# GREEN: Implement endpoint
@app.post("/api/v1/agents", status_code=201)
def create_agent(agent: AgentCreate):
    return service.create_agent(agent)
```

### React Components (TypeScript)
```typescript
// RED: Test component behavior
test('submits form when valid', () => {
  render(<ChatInput onSubmit={jest.fn()} />);
  userEvent.type(screen.getByRole('textbox'), 'Hello');
  userEvent.click(screen.getByRole('button', { name: /send/i }));
  expect(onSubmit).toHaveBeenCalledWith('Hello');
});

// GREEN: Implement component
export const ChatInput = ({ onSubmit }) => {
  const [input, setInput] = useState('');
  return (
    <input value={input} onChange={(e) => setInput(e.target.value)} />
    <button onClick={() => onSubmit(input)}>Send</button>
  );
};
```

### Service Layer (Python)
```python
# RED: Test business logic
def test_agent_maturity_blocks_demotion():
    with pytest.raises(ValueError):
        service.update_maturity("test", AUTONOMOUS, STUDENT)

# GREEN: Implement validation
def update_maturity(self, agent_id, new_maturity):
    if self._is_demotion(current, new):
        raise ValueError("Invalid transition")
    agent.maturity = new_maturity
```

---

## Anti-Patterns to Avoid

### ❌ Testing Implementation Details
```python
# BAD: Testing private method
service._validate_input("")  # Don't test internals

# GOOD: Testing public behavior
service.process("")  # Test observable behavior
```

### ❌ Over-Mocking
```python
# BAD: Mocking everything
with patch('datetime.datetime'):  # Don't mock simple things
    service.execute()

# GOOD: Only mock external dependencies
with patch('core.llm_service.LLMService'):  # Mock LLM (external)
    service.execute()
```

### ❌ Brittle Selectors (React)
```typescript
// BAD: Using className
screen.getByClassName('chat-input')  // Brittle

// GOOD: Using accessible queries
screen.getByRole('textbox')  // Robust
```

### ❌ Skipping Red Phase
```python
# BAD: Writing code first, then test
def create_agent(name):
    return Agent(id=uuid4(), name=name)
# Test always passes (no red phase)

# GOOD: Write test first, verify it fails
def test_create_agent_generates_id():
    agent1 = create_agent("A")
    agent2 = create_agent("B")
    assert agent1.id != agent2.id  # Fails until IDs unique
```

---

## Code Review Checklist

### TDD Compliance
- [ ] Test written before implementation (red phase)
- [ ] Test fails before fix (validates test works)
- [ ] Minimal fix (no over-engineering in green phase)
- [ ] Refactoring done while tests pass
- [ ] All tests pass (no regressions)

### Test Quality
- [ ] Tests behavior, not implementation
- [ ] Uses accessible queries (getByRole, not getByTestId)
- [ ] Only mocks external dependencies (LLM, database)
- [ ] Test name describes behavior (not implementation)
- [ ] One assertion per test (focused)

### Bug Fixes
- [ ] Failing test reproduces bug
- [ ] Test added to prevent regression
- [ ] Root cause addressed (not just symptom)
- [ ] Fix documented (why bug occurred, how fixed)

---

## Commands

### Run Tests
```bash
# Backend
pytest backend/tests/ -v

# Specific test
pytest backend/tests/test_agent_service.py::test_create_agent -v

# With coverage
pytest backend/tests/ --cov=core --cov-report=html

# Frontend
npm test

# Specific test
npm test -- ChatInput.test.tsx

# Watch mode
npm test -- --watch
```

### Debug Tests
```bash
# Backend (pdb)
pytest backend/tests/ -s --pdb

# Frontend (debugger)
node --inspect-brk node_modules/.bin/jest --runInBand
```

---

## Quick Tips

1. **Start small**: One test at a time (don't write 10 tests then implement)
2. **Keep it simple**: Minimal code in green phase (refactor later)
3. **Test behavior**: Test what users see, not how it works
4. **Use accessible queries**: getByRole, getByLabelText (not getByTestId)
5. **Only mock externals**: Mock LLM, database (not datetime, random)
6. **Maintain pass rate**: Keep 80%+ frontend, 100% backend

---

## Help

- **Full TDD Guide**: `/docs/testing/TDD_METHODOLOGY.md`
- **Examples**: `/docs/testing/TDD_EXAMPLES/`
- **Templates**: `/docs/testing/TDD_TEMPLATES/`

---

*Quick Reference created for Atom v12.0*
*Philosophy: "Tests first, code second, quality always."*
