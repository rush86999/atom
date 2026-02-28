# Pitfalls Research: Frontend/Mobile/Desktop Integration & Property Testing

**Domain:** Multi-platform application testing (Next.js, React Native, Tauri)
**Researched:** 2026-02-26
**Confidence:** MEDIUM (based on training data, limited by web search quota)

## Executive Summary

Integration testing and property-based testing for frontend (Next.js), mobile (React Native), and desktop (Tauri) applications introduces unique pitfalls beyond backend testing challenges. Based on research across React Testing Library patterns, property-based testing for UI invariants, React Native device fragmentation, Tauri desktop testing, and cross-platform integration testing, this document identifies critical pitfalls specific to adding comprehensive testing to multi-platform applications.

The most critical pitfall is **test isolation failures causing state leakage between tests** - React state, localStorage, and async effects persist between test runs, causing intermittent failures that depend on execution order. The second most critical is **async testing timeouts and race conditions** - React's batch updates and async state management cause tests to fail inconsistently.

## Key Findings

**Stack:** React Testing Library (user behavior queries), MSW (API mocking), Fast Check (property testing), Jest/Detox (mobile), Rust unit tests (Tauri backend)
**Architecture:** Integration tests for real components, minimal mocking, shared OpenAPI contracts, cross-platform test infrastructure
**Critical pitfall:** Test isolation failures causing intermittent test failures that erode confidence in test suite
**Integration challenge:** Frontend-backend contract drift without automated schema validation

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Frontend Integration Infrastructure** - MUST USE FIRST to establish testing foundation
   - Addresses: Test isolation, async handling, user behavior queries
   - Avoids: Brittle tests that break on refactoring
   - Property tests: UI state invariants, form validation determinism

2. **Mobile Testing Infrastructure** - SECOND to prevent device-specific bugs
   - Addresses: Platform fragmentation, permissions, native modules
   - Avoids: Bugs that only appear on real devices
   - Integration tests: iOS and Android code paths covered

3. **Desktop Testing Infrastructure** - THIRD to validate cross-platform behavior
   - Addresses: Shell command safety, path handling, IPC contracts
   - Avoids: Platform-specific security issues
   - Integration tests: Windows, macOS, Linux differences tested

4. **Frontend Property Testing** - FOURTH to add invariant-based testing
   - Addresses: Meaningful UI invariants, state transitions
   - Avoids: Trivial properties that never fail
   - Property tests: State management invariants, form validation rules

**Phase ordering rationale:**
- Test isolation is foundational - if caught late, require rewriting entire test suite
- Mobile and desktop testing share patterns (cross-platform concerns) - can be done in parallel
- Property testing builds on stable test infrastructure from earlier phases
- Frontend-backend contracts validated in Phase 1 prevent drift in later phases

**Research flags for phases:**
- Phase 1 (Frontend Integration): HIGH risk - Test isolation failures cause widespread test suite instability
- Phase 2 (Mobile Testing): MEDIUM risk - Device fragmentation requires real device testing investment
- Phase 3 (Desktop Testing): MEDIUM risk - Shell command escapes have security implications
- Phase 4 (Property Testing): LOW risk - Standard property testing patterns apply

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| React Testing Library patterns | HIGH | Official documentation, best practices well-established |
| Async testing challenges | HIGH | Common pitfalls well-documented in React testing guides |
| Property testing for UI | MEDIUM | Fast Check docs, but UI invariants harder to identify than backend |
| React Native testing | MEDIUM | Platform fragmentation issues known, but testing patterns vary |
| Tauri desktop testing | LOW/MEDIUM | Less established patterns, Rust testing ecosystem mature but Tauri-specific patterns emerging |
| Cross-platform test sharing | MEDIUM | General patterns known, but tool-specific (Jest vs Detox) differences |

## Gaps to Address

- **Specific property test invariants for UI**: Frontend invariants less obvious than backend - need Phase 4 research to identify meaningful properties
- **Tauri testing best practices**: Desktop testing patterns less mature than web/mobile - may need iteration in Phase 3
- **Visual regression testing**: Not primary focus, but should consider for UI-heavy features

---

## Critical Pitfalls

### Pitfall 1: Test Isolation Failures

**What goes wrong:**
Tests share state through browser localStorage, sessionStorage, or React state, causing intermittent failures that depend on execution order. One test's side effects cause cascading failures in subsequent tests.

**Why it happens:**
- React state persists between test runs in jsdom
- Testing Library doesn't automatically clean up all side effects
- Async state updates (useEffect, useState) complete after test finishes
- WebSocket connections or event listeners remain attached
- Mocks not reset between tests

**Consequences:**
- **Intermittent failures**: Tests pass individually but fail in suites
- **False bug reports**: "Flaky tests" waste debugging time
- **Lost confidence**: Team stops running tests due to unreliability
- **CI failures**: Tests pass locally but fail on CI due to execution order
- **Slow debugging**: Hard to reproduce failures that depend on test order

**Prevention:**
```javascript
// GOOD: Explicit cleanup after each test
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup(); // Unmounts components, removes DOM
  localStorage.clear();
  sessionStorage.clear();
  jest.clearAllMocks();
  jest.clearAllTimers();
});

// GOOD: Unmount components explicitly
test('component cleans up event listeners', () => {
  const { unmount } = render(<MyComponent />);
  // ... test code
  unmount(); // Explicit cleanup
  // Verify no memory leaks
});

// GOOD: Use unique IDs for parallel-safe tests
test('creates agent with unique ID', () => {
  const uniqueId = `agent_${Date.now()}_${Math.random()}`;
  const agent = createAgent({ id: uniqueId });
  // No collision with parallel tests
});
```

**Detection:**
- Warning sign: Tests pass when run individually but fail in suites
- Warning sign: Failures disappear when using `--testNamePattern` to run single test
- Warning sign: Intermittent failures that "go away" on retry
- Warning sign: Tests depend on execution order (test A must run before test B)
- Warning sign: `cleanup()` not called in `afterEach`

**Phase to address:**
**Phase 084: Frontend Integration Testing** - Establish `afterEach(cleanup())` pattern before writing frontend tests. Document state sharing anti-patterns. Audit existing tests for isolation issues.

**Sources:**
- React Testing Library documentation - HIGH confidence, official cleanup patterns
- Jest `afterEach` documentation - HIGH confidence, standard cleanup hooks
- Existing Atom backend test isolation patterns - HIGH confidence, `db_session` rollback, `unique_resource_name` fixture

---

### Pitfall 2: Async Testing Timeouts and Race Conditions

**What goes wrong:**
Tests fail with "Unable to find element" or timeouts because:
- React state updates haven't propagated to DOM
- API mocks return after assertions run
- useEffect hooks haven't executed
- Transitions/animations haven't completed
- WebSocket messages not received yet

**Why it happens:**
- React batch updates cause delayed DOM updates
- Jest runs assertions synchronously but state updates are async
- Network mocks using Promises without proper await
- Missing waitFor/findBy* queries for async operations
- Tests assume immediate UI updates after actions

**Consequences:**
- **Brittle tests**: Random timeouts cause inconsistent failures
- **Slow tests**: Excessive `setTimeout` calls increase test duration
- **False failures**: Tests fail on slower CI machines
- **Hidden bugs**: Tests pass despite timing issues due to long timeouts
- **Developer friction**: Need to constantly increase timeout values

**Prevention:**
```javascript
// BAD: Assume immediate DOM update
test('shows loading then data', () => {
  render(<UserList />);
  expect(screen.getByText('Loading')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Load'));
  expect(screen.getByText('Data loaded')).toBeInTheDocument(); // Race condition
});

// GOOD: Use findBy* for async operations
test('shows loading then data', async () => {
  render(<UserList />);
  expect(screen.getByText('Loading')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Load'));
  
  await waitFor(() => {
    expect(screen.getByText('Data loaded')).toBeInTheDocument();
  }, { timeout: 3000 });
});

// GOOD: Use findBy queries for async elements
test('async data loading', async () => {
  render(<UserProfile userId="123" />);
  const userName = await screen.findByText('John Doe', { timeout: 2000 });
  expect(userName).toBeInTheDocument();
});

// GOOD: Mock promises with proper timing
jest.mock('../api/users', () => ({
  getUser: jest.fn(() => new Promise(resolve => {
    setTimeout(() => resolve(mockUser), 100); // Realistic delay
  })),
}));
```

**Detection:**
- Warning sign: Frequent use of `setTimeout` or `jest.advanceTimersByTime` in tests
- Warning sign: Tests fail on CI but pass locally (slower CI environment)
- Warning sign: "Cannot find element" errors that are intermittent
- Warning sign: Need to increase `jest.setTimeout()` to make tests pass
- Warning sign: Using `getBy*` after async actions instead of `findBy*`

**Phase to address:**
**Phase 084: Frontend Integration Testing** - Establish async testing patterns before writing integration tests. Document when to use `findBy*` vs `waitFor`. Remove all `setTimeout` calls from tests.

**Sources:**
- React Testing Library async documentation - HIGH confidence, official async patterns
- Jest timer documentation - HIGH confidence, fake timers usage
- Common React testing async pitfalls - MEDIUM confidence, community patterns

---

### Pitfall 3: Implementation Testing Over User Behavior

**What goes wrong:**
Tests break on every refactor because they test implementation details (internal state, component methods, CSS classes) instead of user-visible behavior.

**Why it happens:**
- Easiest way to test React components is by checking internal state
- Testing Library's `container.querySelector` feels familiar from jQuery
- Developers test what they can see in code, not what users experience
- Snapshot testing encourages testing structure over behavior
- TypeScript types tested instead of UI behavior

**Consequences:**
- **Brittle tests**: CSS refactoring breaks all tests
- **False confidence**: Tests pass but UI doesn't work for users
- **Slow refactoring**: Fear of breaking tests impedes code improvements
- **Test maintenance burden**: Tests require constant updates
- **Wrong focus**: Testing implementation instead of value

**Prevention:**
```javascript
// BAD: Testing implementation details
test('button component', () => {
  const { container } = render(<Button primary />);
  expect(container.querySelector('.btn-primary')).toBeInTheDocument(); // CSS coupling
  expect(container.querySelector('button').disabled).toBe(false); // Internal property
});

// GOOD: Testing user behavior
test('primary button submits form', () => {
  const handleSubmit = jest.fn();
  render(<Button onClick={handleSubmit} primary>Submit</Button>);

  fireEvent.click(screen.getByRole('button', { name: /submit/i }));

  expect(handleSubmit).toHaveBeenCalledTimes(1);
});

// PREFERRED QUERY ORDER (React Testing Library):
// 1. getByRole (most accessible)
// 2. getByLabelText (form inputs)
// 3. getByText (user-visible text)
// 4. getByTestId (last resort, only if no accessible alternative)

// GOOD: Test what users see, not how it's implemented
test('form validation shows error messages', () => {
  render(<LoginForm />);
  
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: 'invalid-email' }
  });
  fireEvent.click(screen.getByRole('button', { name: /submit/i }));
  
  expect(screen.getByText(/please enter a valid email/i)).toBeInTheDocument();
});
```

**Detection:**
- Warning sign: Tests fail after CSS refactoring (renaming classes, changing structure)
- Warning sign: Heavy use of `container.querySelector` or shallow rendering
- Warning sign: Tests check `component.state` or internal properties
- Warning sign: Snapshot tests without reviewing changes
- Warning sign: Tests break after code restructuring without behavior change

**Phase to address:**
**Phase 084: Frontend Integration Testing** - Establish user behavior testing guidelines. Train team on query priority (role > label > text > testId). Audit existing tests for implementation testing.

**Sources:**
- React Testing Library guidelines - HIGH confidence, "The more your tests resemble the way your software is used, the more confidence they can give you"
- Testing Library query priority - HIGH confidence, official query documentation
- Common anti-patterns in React testing - MEDIUM confidence, community discussions

---

### Pitfall 4: Property Testing Without Meaningful Invariants

**What goes wrong:**
Property tests for frontend state either:
1. Test trivial properties that never fail (`x === x`)
2. Test implementation details that change frequently
3. Generate invalid inputs that don't represent real usage

**Why it happens:**
- Frontend state invariants harder to identify than backend rules
- Generating valid React component state/props is complex
- No clear mapping from "random inputs" to "UI behavior properties"
- Lack of experience with property-based testing in frontend
- Pressure to add "fancy tests" without understanding value

**Consequences:**
- **Expensive assertions**: Property tests run 100x but never find bugs
- **False confidence**: "We have property tests" but they're useless
- **Slow test suite**: 200 examples per test with no value
- **Property tests abandoned**: Team stops running them due to lack of value
- **Missed opportunities**: Real invariants not tested

**Prevention:**
```javascript
// BAD: Trivial property that never fails
test('idempotent render', () => {
  fastCheck.assert(
    fastCheck.property(
      fastCheck.string(),
      (name) => {
        const component = render(<Greeting name={name} />);
        const result1 = component.asFragment();
        const result2 = component.asFragment();
        expect(result1).toEqual(result2); // Always passes
        return true;
      }
    )
  );
});

// GOOD: Meaningful UI invariant
test('form validation is deterministic', () => {
  fastCheck.assert(
    fastCheck.property(
      fastCheck.record({
        email: fastCheck.email(),
        age: fastCheck.nat(),
        name: fastCheck.string()
      }),
      (formData) => {
        const { result } = renderHook(() => useFormValidation(formData));
        const { isValid, errors } = result.current;

        // Invariant: Validation result is deterministic for same input
        expect(typeof isValid).toBe('boolean');
        expect(typeof errors).toBe('object');
        
        // Invariant: Valid form has no errors
        if (isValid) {
          expect(Object.keys(errors)).toHaveLength(0);
        }

        return true;
      }
    ),
    { numRuns: 100 }
  );
});

// GOOD: State transition invariant
test('todo list maintains count invariant', () => {
  fastCheck.assert(
    fastCheck.property(
      fastCheck.array(fastCheck.record({ text: fastCheck.string() })),
      (initialTodos) => {
        const { result } = renderHook(() => useTodoList(initialTodos));
        const initialCount = result.current.todos.length;

        // Add a todo
        act(() => {
          result.current.addTodo('New Todo');
        });

        // Invariant: Count increases by exactly 1
        expect(result.current.todos.length).toBe(initialCount + 1);

        return true;
      }
    )
  );
});

// GOOD: UI state invariant
test('counter maintains non-negative invariant', () => {
  fastCheck.assert(
    fastCheck.property(
      fastck.array(fastck.boolean(), { minLength: 1 }),
      (actions) => {
        const { result } = renderHook(() => useCounter());

        actions.forEach((shouldIncrement) => {
          act(() => {
            if (shouldIncrement) {
              result.current.increment();
            } else {
              result.current.decrement();
            }
          });
        });

        // Invariant: Counter never goes negative
        expect(result.current.count).toBeGreaterThanOrEqual(0);
        return true;
      }
    )
  );
});
```

**Detection:**
- Warning sign: Property tests always pass (100% pass rate with no bugs found)
- Warning sign: Tests generate random strings/numbers but don't use them meaningfully
- Warning sign: Tests only verify types (`typeof x === 'string'`)
- Warning sign: No clear business rule or invariant being tested
- Warning sign: Tests feel "forced" - not natural properties of the system

**Phase to address:**
**Phase 086: Frontend Property Testing** - Dedicate time to invariant identification before implementation. Document UI invariants in test docstrings. Require "bug this would catch" for each property test.

**Sources:**
- Fast Check documentation - MEDIUM confidence, property testing patterns for JavaScript
- Property-based testing for UI - LOW/MEDIUM confidence, less established than backend patterns
- Existing Atom backend property tests - HIGH confidence, invariant identification patterns

---

### Pitfall 5: React Native Device Fragmentation Testing

**What goes wrong:**
Tests pass on development machine but fail on real devices due to:
- Platform-specific code (iOS vs Android) not tested
- Different async behavior on native modules
- Device-specific permissions or capabilities
- Screen size/orientation differences

**Why it happens:**
- Development happens on simulator/emulator, not real devices
- Native modules have different timing on real hardware
- Tests mock native modules, missing edge cases
- Platform detection code (`Platform.OS`) untested
- Permissions testing skipped due to complexity

**Consequences:**
- **Production bugs**: Features work in tests but fail on real devices
- **Platform-specific crashes**: iOS-only or Android-only issues
- **Permission dialogs**: Unhandled permission denies cause crashes
- **Device-specific layout**: UI breaks on different screen sizes
- **User complaints**: "App doesn't work on my phone"

**Prevention:**
```javascript
// BAD: Only testing iOS
jest.mock('react-native/Libraries/Utilities/Platform', () => ({
  OS: 'ios',
  select: jest.fn((obj) => obj.ios),
}));

test('navigation', () => {
  render(<App />); // Only iOS path tested
});

// GOOD: Test both platforms
describe('Platform-specific navigation', () => {
  const platforms = ['ios', 'android'];
  
  platforms.forEach((platform) => {
    describe(`on ${platform}`, () => {
      beforeEach(() => {
        jest.resetModules();
        jest.doMock('react-native/Libraries/Utilities/Platform', () => ({
          OS: platform,
          select: jest.fn((obj) => obj[platform]),
        }));
      });

      test('navigates correctly', () => {
        const { getByText } = render(<App />);
        expect(getByText(/platform-specific feature/i)).toBeInTheDocument();
      });
    });
  });
});

// GOOD: Mock native modules with realistic behavior
jest.mock('react-native-camera', () => ({
  Camera: {
    Constants: { 
      FlashMode: { off: 'off', on: 'on' } 
    },
  },
}));

test('camera permission handling', async () => {
  // Test permission grant
  PermissionsAndroid.request.mockResolvedValueOnce('granted');

  const { getByText } = render(<CameraScreen />);
  await act(async () => {
    fireEvent.press(getByText(/open camera/i));
  });

  expect(getByText(/camera active/i)).toBeInTheDocument();

  // Test permission deny
  PermissionsAndroid.request.mockResolvedValueOnce('denied');
  
  const { getByText: getByText2 } = render(<CameraScreen />);
  await act(async () => {
    fireEvent.press(getByText2(/open camera/i));
  });

  expect(getByText2(/camera permission denied/i)).toBeInTheDocument();
});
```

**Detection:**
- Warning sign: Tests pass on CI but fail on device testing
- Warning sign: Heavy mocking of Platform or native modules
- Warning sign: No tests for `Platform.OS` conditional logic
- Warning sign: "It works on my machine" syndrome with real devices
- Warning sign: Permission dialogs untested

**Phase to address:**
**Phase 087: Mobile Testing Infrastructure** - Add real device testing pipeline. Test both iOS and Android code paths. Mock native modules with realistic error cases. Test permission grant/deny/error scenarios.

**Sources:**
- React Native testing challenges - MEDIUM confidence, platform fragmentation well-known
- React Native Testing Library - MEDIUM confidence, testing patterns for RN
- Detox documentation - MEDIUM confidence, E2E testing for React Native

---

### Pitfall 6: Tauri Desktop Testing Shell Command Escapes

**What goes wrong:**
Tauri tests either:
1. Execute real shell commands (security risk, non-deterministic)
2. Mock shell commands but miss error cases
3. Don't test cross-platform differences (Windows vs macOS vs Linux)

**Why it happens:**
- Tauri's invoke system makes shell commands easy to execute
- Mocking Tauri's IPC requires understanding Rust side
- Shell command output differs by OS
- Error handling in shell commands complex
- Cross-platform differences not considered

**Consequences:**
- **Security vulnerabilities**: Shell injection attacks
- **Platform-specific bugs**: Commands work on Windows but fail on Unix
- **Non-deterministic tests**: Real shell commands fail in CI
- **Production crashes**: Unhandled shell command errors
- **Path issues**: Windows backslashes vs Unix forward slashes

**Prevention:**
```rust
// BAD: Real shell command execution in tests
#[tauri::command]
async fn read_file(path: String) -> Result<String, String> {
    std::fs::read_to_string(&path).map_err(|e| e.to_string())
}

// Test fails on non-Windows if testing Windows-specific paths

// GOOD: Abstract command execution with trait
trait FileSystem {
    fn read_file(&self, path: &str) -> Result<String, std::io::Error>;
}

struct RealFileSystem;
impl FileSystem for RealFileSystem {
    fn read_file(&self, path: &str) -> Result<String, std::io::Error> {
        std::fs::read_to_string(path)
    }
}

struct MockFileSystem {
    files: HashMap<String, String>
}
impl FileSystem for MockFileSystem {
    fn read_file(&self, path: &str) -> Result<String, std::io::Error> {
        self.files.get(path)
            .cloned()
            .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::NotFound, "Not found"))
    }
}

// Use dependency injection in commands
struct AppState<F: FileSystem> {
    fs: F,
}

#[tauri::command]
async fn read_file<F: FileSystem>(
    state: tauri::State<'_, AppState<F>>,
    path: String
) -> Result<String, String> {
    state.fs.read_file(&path).map_err(|e| e.to_string())
}
```

```javascript
// Frontend test with mocked Tauri invoke
import { invoke } from '@tauri-apps/api/tauri';

jest.mock('@tauri-apps/api/tauri', () => ({
  invoke: jest.fn(),
}));

test('file read error handling', async () => {
  invoke.mockRejectedValue(new Error('File not found'));

  const { getByText } = render(<FileReader path="/nonexistent.txt" />);

  await waitFor(() => {
    expect(getByText(/error reading file/i)).toBeInTheDocument();
  });
});

test('cross-platform path handling', async () => {
  // Test Windows paths
  invoke.mockResolvedValue('C:\\Users\\test\\file.txt');
  let { getByText } = render(<FileReader />);
  expect(getByText(/C:\\Users/i)).toBeInTheDocument();

  // Test Unix paths
  invoke.mockResolvedValue('/home/user/file.txt');
  ({ getByText } = render(<FileReader />));
  expect(getByText(/\/home\/user/i)).toBeInTheDocument();
});
```

**Detection:**
- Warning sign: Tests fail when run on different OS
- Warning sign: Shell commands execute in tests (`ls`, `dir`, `cat`)
- Warning sign: No tests for command error cases
- Warning sign: Path handling untested
- Warning sign: "Works on my OS" syndrome

**Phase to address:**
**Phase 088: Desktop Testing Infrastructure** - Add Rust unit tests for shell command abstractions. Test cross-platform path handling. Mock Tauri invoke with realistic error cases. Test on Windows, macOS, and Linux CI.

**Sources:**
- Tauri testing patterns - LOW/MEDIUM confidence, less established than web/mobile
- Rust testing patterns - HIGH confidence, Rust's testing ecosystem mature
- Cross-platform shell command challenges - MEDIUM confidence, OS differences well-known

---

### Pitfall 7: Frontend-Backend Contract Drift

**What goes wrong:**
Frontend tests mock API responses with outdated schemas, but real backend returns different data structure. Tests pass but integration fails in production.

**Why it happens:**
- Frontend and backend developed separately
- Mock fixtures created once and never updated
- API changes not reflected in test mocks
- TypeScript types don't match actual JSON responses
- No automated contract validation

**Consequences:**
- **Production integration failures**: Tests pass but real API calls fail
- **Data corruption**: Frontend expects `user.name` but backend returns `user.username`
- **Silent failures**: Missing fields cause undefined behavior
- **Debugging time**: Hard to trace where contract mismatch occurred
- **Lost features**: API changes break frontend without test failures

**Prevention:**
```javascript
// BAD: Hardcoded mock responses
jest.mock('../api/users', () => ({
  getUser: jest.fn(() => Promise.resolve({
    id: 1,
    name: 'John',
    // Missing: email, created_at fields that backend returns
  })),
}));

// GOOD: Shared types from backend
// types.ts - generated from OpenAPI or backend types
export interface User {
  id: number;
  name: string;
  email: string;
  created_at: string;
}

// GOOD: MSW (Mock Service Worker) with realistic handlers
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  rest.get('/api/users/:id', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        id: Number(req.params.id),
        name: 'John Doe',
        email: 'john@example.com',
        created_at: new Date().toISOString(),
      })
    );
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test('user profile displays all fields', async () => {
  const { getByText } = render(<UserProfile userId="123" />);

  await waitFor(() => {
    expect(getByText('John Doe')).toBeInTheDocument();
    expect(getByText('john@example.com')).toBeInTheDocument();
    expect(getByText(/\d{4}-\d{2}-\d{2}/)).toBeInTheDocument(); // Date
  });
});
```

**Detection:**
- Warning sign: Tests pass but production integration fails
- Warning sign: TypeScript `any` types in API calls
- Warning sign: Mock fixtures manually created instead of derived from OpenAPI
- Warning sign: Backend field changes break frontend without test failures
- Warning sign: No contract tests or shared types

**Phase to address:**
**Phase 084: Frontend Integration Testing** - Establish MSW with OpenAPI schema validation. Share TypeScript types between frontend and backend. Add contract tests that fail on schema mismatch.

**Sources:**
- MSW documentation - HIGH confidence, modern API mocking
- OpenAPI schema validation - MEDIUM confidence, contract testing patterns
- Frontend-backend contract testing - MEDIUM confidence, emerging best practices

---

### Pitfall 8: Flaky Visual Regression Tests

**What goes wrong:**
Visual regression tests fail due to:
- Font rendering differences across OS
- Anti-aliasing variations (Windows ClearType vs macOS)
- Random animations or transitions
- Timestamps or dynamic content

**Why it happens:**
- Screenshots capture environment-specific rendering
- Tests don't normalize dynamic content
- CI environment differs from local machine
- No stable visual baselines
- Fonts not installed on CI

**Consequences:**
- **False positives**: Visual tests fail due to environment, not code changes
- **Team disables tests**: Flaky tests abandoned
- **Missed regressions**: Real visual changes lost in noise
- **Time wasted**: Constant snapshot reviews
- **Platform-specific failures**: Tests pass locally but fail on CI

**Prevention:**
```javascript
// GOOD: Mock dynamic content before screenshots
test('dashboard visual snapshot', () => {
  jest.useFakeTimers().setSystemTime(new Date('2026-02-26'));

  const { container } = render(<Dashboard />);

  // Hide dynamic elements
  document.querySelectorAll('[data-timestamp]').forEach(el => {
    el.setAttribute('data-timestamp', '2026-02-26T12:00:00Z');
  });

  // Disable animations
  document.body.classList.add('disable-animations');

  expect(container).toMatchSnapshot();
});

// GOOD: Use data attributes to exclude dynamic content
test('user list visual regression', () => {
  const { container } = render(<UserList users={testUsers} />);

  // Exclude dynamic elements from snapshot
  const dynamicElements = container.querySelectorAll('[data-dynamic]');
  dynamicElements.forEach(el => el.remove());

  expect(container.firstChild).toMatchImageSnapshot({
    customDiffConfig: { threshold: 0.1 },
    noColors: true, // Ignore anti-aliasing differences
  });
});
```

**Detection:**
- Warning sign: Snapshot tests fail on CI but pass locally
- Warning sign: Frequent snapshot updates despite no changes
- Warning sign: Random failures in visual tests
- Warning sign: Large snapshot diff files
- Warning sign: Team commits snapshot updates without reviewing

**Phase to address:**
**Phase 085: Visual Regression Testing** - Normalize dynamic content before snapshots. Use consistent fonts across environments. Configure anti-aliasing tolerance. Add snapshot review to PR process.

**Sources:**
- Jest snapshot testing - HIGH confidence, official documentation
- Visual regression testing challenges - MEDIUM confidence, environment-specific issues well-known

---

## Moderate Pitfalls

### Pitfall 9: Over-Mocking in React Tests

**What goes wrong:**
Tests mock so much that they test nothing - code works in tests but fails in production because all real dependencies replaced.

**Why it happens:**
- Easiest way to isolate components
- External dependencies hard to set up in tests
- Desire for "fast" unit tests
- Misunderstanding of integration vs unit testing

**Consequences:**
- **False confidence**: Tests pass but production fails
- **Missed integration bugs**: Real dependencies have issues
- **Maintenance burden**: Mocks larger than real code
- **Brittle tests**: Mock implementations drift from real code

**Prevention:**
```javascript
// BAD: Mocking everything
test('user list', () => {
  jest.mock('../api/users');
  jest.mock('../components/UserCard');
  jest.mock('../hooks/useUsers');

  const { getByText } = render(<UserList />);
  // All dependencies mocked - testing nothing
  expect(getByText('User List')).toBeInTheDocument();
});

// GOOD: Only mock external services (API, native modules)
test('user list displays users', async () => {
  // Only mock HTTP client
  jest.mock('../api/client', () => ({
    get: jest.fn(() => Promise.resolve({ data: mockUsers })),
  }));

  const { getByText } = render(<UserList />);

  await waitFor(() => {
    expect(getByText('John Doe')).toBeInTheDocument();
    expect(getByText('Jane Smith')).toBeInTheDocument();
  });

  // Verify real API call made
  expect(client.get).toHaveBeenCalledWith('/users');
});
```

**Detection:**
- Warning sign: Tests pass when implementation is deleted
- Warning sign: `jest.mock` outnumbers real imports
- Warning sign: Tests never fail when bugs introduced
- Warning sign: No integration tests, only unit tests
- Warning sign: Mock implementations larger than real code

**Phase to address:**
**Phase 084: Frontend Integration Testing** - Establish "integration first" testing philosophy. Only mock external APIs, not internal components. Add integration tests that test real code paths.

---

### Pitfall 10: State Management Testing Gaps

**What goes wrong:**
State management logic (Redux, Zustand, React Context) insufficiently tested, causing:
- State mutations violating invariants
- Race conditions in async actions
- Memory leaks from unsubscribed listeners
- State sync issues across components

**Why it happens:**
- State logic scattered across reducers, actions, selectors
- Hard to test state transitions without UI
- Async state updates complex
- Developers test UI components, not state layer

**Consequences:**
- **Silent state corruption**: State violates business rules
- **Inconsistent UI**: Different components show different state
- **Memory leaks**: Event listeners not cleaned up
- **Lost updates**: Race conditions in async actions

**Prevention:**
```javascript
// GOOD: Test Redux reducers independently
import userReducer, { setUser, updateUser } from './userSlice';

test('user slice maintains invariants', () => {
  const initialState = userReducer(undefined, { type: 'init' });

  // Invariant: User object has required fields
  const stateWithUser = userReducer(initialState, setUser({
    id: 1,
    name: 'John',
    email: 'john@example.com'
  }));

  expect(stateWithUser.user).toMatchObject({
    id: expect.any(Number),
    name: expect.any(String),
    email: expect.stringContaining('@'),
  });
});

// GOOD: Test async actions with loading/error states
test('fetch user async flow', async () => {
  const store = makeStore();

  // Initial state
  expect(store.getState().users.loading).toBe(false);
  expect(store.getState().users.error).toBeNull();

  // Start fetch
  store.dispatch(fetchUser.pending(''));
  expect(store.getState().users.loading).toBe(true);

  // Success
  await store.dispatch(fetchUser.fulfilled(mockUser, '', '123'));
  expect(store.getState().users.loading).toBe(false);
  expect(store.getState().users.data).toEqual(mockUser);

  // Error
  await store.dispatch(fetchUser.rejected(new Error('API error'), '', '123'));
  expect(store.getState().users.loading).toBe(false);
  expect(store.getState().users.error).toBeTruthy();
});
```

**Detection:**
- Warning sign: State changes only tested through UI interactions
- Warning sign: Reducers/actions have no unit tests
- Warning sign: Async state updates untested
- Warning sign: No tests for error states
- Warning sign: State mutations violate business rules

**Phase to address:**
**Phase 084: Frontend Integration Testing** - Add unit tests for reducers, actions, selectors. Test async state transitions. Add property tests for state invariants.

---

## Minor Pitfalls

### Pitfall 11: Missing Accessibility Testing

**What goes wrong:**
Tests don't verify accessibility, causing:
- Keyboard navigation broken
- Screen reader incompatibility
- Missing ARIA labels
- Focus management issues

**Prevention:**
- Use `getByRole` queries (enforces accessible markup)
- Test keyboard navigation
- Verify ARIA labels on interactive elements
- Test focus management

**Detection:**
- Warning sign: Tests use `getByTestId` instead of `getByRole`
- Warning sign: No keyboard navigation tests
- Warning sign: ARIA attributes not tested

**Phase to address:**
**Phase 084: Frontend Integration Testing** - Establish accessible testing patterns. Require `getByRole` queries. Add keyboard navigation tests.

---

### Pitfall 12: Performance Regression Testing Missing

**What goes wrong:**
No tests for rendering performance, causing:
- Slow component re-renders
- Memory leaks from subscriptions
- Unnecessary re-renders

**Prevention:**
- Test render times with `@testing-library/react-hooks`
- Test component unmount cleans up subscriptions
- Use React DevTools profiling in tests

**Detection:**
- Warning sign: Apps slow down with more data
- Warning sign: Memory usage increases over time
- Warning sign: No performance benchmarks

**Phase to address:**
**Phase 084: Frontend Integration Testing** - Add performance benchmarks for critical components. Test memory leak scenarios.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Snapshot testing without review | Fast to write, catches UI changes | False confidence, snapshots ignored, brittle to CSS changes | Never - better to test user behavior |
| Mocking native modules | Fast tests, no device needed | Miss platform-specific bugs, unrealistic behavior | MVP only - must add device tests later |
| `setTimeout` in async tests | Quick fix for race conditions | Brittle, slow tests, non-deterministic | Never - use waitFor/eventually |
| Testing internal state | Easy to write | Brittle to refactoring, false security | Never - test user behavior |
| Skipping visual tests | Saves time, avoids flakiness | Misses CSS regressions, layout breaks | Only for prototypes, add before production |
| Hardcoded API mocks | Fast setup, simple | Drift from real API, production bugs | Only with schema validation (MSW + OpenAPI) |
| Ignoring platform differences | Write once, test once | Platform-specific bugs in production | Never - test each target platform |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Slow test suites (minutes) | Developers skip running tests, CI takes too long | Use integration tests instead of E2E, parallelize tests, mock external services | >100 tests, >2min runtime |
| Property test explosion | Tests run for hours, CI times out | Limit `max_examples`, use targeted generators, separate slow tests | Complex state with many combinations |
| Visual regression flakiness | Random failures, team disables tests | Normalize dynamic content, disable animations, use stable baselines | Any visual regression testing |
| Heavy DOM cleanup between tests | Tests slow down as suite progresses | Proper cleanup, jest.clearAllMocks(), afterEach cleanup | >50 integration tests |
| Unmocked network requests in tests | Slow, non-deterministic, rate-limited | MSW or nock for mocking, validate with contract tests | Any API integration |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **Next.js API routes** | Import route handlers directly in tests (bypasses Next.js request parsing) | Use `createMocks` from `next/test/api-utils` or integration test with TestClient |
| **React Native Navigation** | Mock navigation entirely, miss state management bugs | Use `react-navigation` testing library with real navigation container |
| **Tauri IPC** | Don't test Rust backend, only mock JS side | Add Rust unit tests, test IPC contract with both sides |
| **WebSocket connections** | Mock WebSocket, miss real connection issues | Use `mock-socket` for realistic socket testing |
| **LocalStorage/AsyncStorage** | Don't clear between tests, state leakage | Clear in `afterEach`, test persistence explicitly |
| **Camera/Device permissions** | Mock grant every time, miss deny scenarios | Test grant, deny, error cases with realistic mocks |
| **File system operations (Tauri)** | Execute real commands in tests | Abstract with trait objects, mock for tests, integration tests with temp dirs |

---

## Platform-Specific Pitfalls

### Frontend (Next.js)

**Async State Updates:**
- Use `findBy*` queries for async elements
- Wait for React batch updates with `waitFor`
- Avoid `getBy*` after async actions

**Server Component Testing:**
- Server components can't be tested directly
- Test through integration with client components
- Use `createMocks` for API route testing

**Form Validation:**
- Test validation with realistic user input
- Test error messages display correctly
- Test form submission with valid/invalid data

### Mobile (React Native)

**Platform Code Splitting:**
- Test both iOS and Android code paths
- Mock `Platform.OS` for conditional logic
- Test platform-specific features (Camera, GPS, etc.)

**Native Module Mocks:**
- Mock with realistic behavior and errors
- Test permission grant/deny/error cases
- Test async operations with proper timing

**Screen Orientation/Size:**
- Test different screen sizes
- Test orientation changes
- Test layout on tablets vs phones

### Desktop (Tauri)

**Cross-Platform Paths:**
- Test both Windows (`\`) and Unix (`/`) paths
- Test path normalization
- Test home directory differences

**Shell Command Escaping:**
- Test command injection prevention
- Test error handling for invalid commands
- Test cross-platform command differences

**IPC Communication:**
- Test Rust backend with Rust tests
- Test frontend-backend contract
- Test error propagation across IPC boundary

---

## "Looks Done But Isn't" Checklist

- [ ] **Frontend async handling:** Tests use `findBy*` or `waitFor` for all async operations — verify no `getBy*` after async actions
- [ ] **Platform coverage:** Both iOS and Android code paths tested — verify `Platform.OS` conditionals covered
- [ ] **Cross-platform desktop:** Tests run on Windows, macOS, and Linux CI — verify shell command differences tested
- [ ] **API contract sync:** Frontend tests match actual backend schemas — verify using OpenAPI or shared types
- [ ] **State management:** Reducers, actions, selectors have unit tests — verify not just UI tests
- [ ] **Permission handling:** Camera, location, filesystem permissions tested for deny/error — verify not just grant
- [ ] **Error boundaries:** React error boundaries tested with real errors — verify error UI displays
- [ ] **Native module errors:** Native modules mocked with realistic failures — verify error handling
- [ ] **Visual regression:** Screenshots exclude dynamic content — verify timestamps, random IDs excluded
- [ ] **Property test invariants:** Frontend property tests test meaningful invariants — verify not just trivial properties
- [ ] **Memory leaks:** Event listeners, WebSocket, subscriptions cleaned up — verify unmount/removal tests
- [ ] **Accessibility:** a11y queries used in tests — verify role-based queries preferred

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Test isolation failures | HIGH | Add `afterEach(cleanup())`, audit state sharing, add unique IDs to tests |
| Async race conditions | MEDIUM | Replace `setTimeout` with `waitFor`, add `findBy*` queries, increase test timeout |
| Implementation testing | HIGH | Rewrite tests to use user behavior queries (getByRole), remove state assertions |
| Trivial property tests | LOW | Identify meaningful invariants, rewrite with business rules |
| Device fragmentation bugs | HIGH | Add real device testing, test both iOS/Android, add permission tests |
| Shell command escapes | MEDIUM | Add sandbox abstractions, test error cases, add integration tests |
| API contract drift | MEDIUM | Add contract tests, use MSW with OpenAPI schema, sync frontend/backend types |
| Flaky visual tests | MEDIUM | Exclude dynamic content, normalize timestamps, use stable baselines |
| Over-mocked tests | HIGH | Replace mocks with real components, add integration tests |
| State management gaps | MEDIUM | Add unit tests for reducers, selectors, async actions |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Test isolation failures | Phase 084 (Frontend Integration) | Tests run in parallel without failures |
| Async race conditions | Phase 084 (Frontend Integration) | No `setTimeout` or `waitFor` abuse |
| Implementation testing | Phase 084 (Frontend Integration) | Refactoring doesn't break tests |
| Trivial property tests | Phase 086 (Frontend Property Testing) | Property tests find bugs, not just pass |
| Device fragmentation | Phase 087 (Mobile Testing) | Tests run on real iOS and Android devices |
| Shell command escapes | Phase 088 (Desktop Testing) | Shell injection tests added, sandboxing verified |
| API contract drift | Phase 084 (Frontend Integration) | Contract tests fail on schema mismatch |
| Flaky visual tests | Phase 085 (Visual Regression) | Visual tests stable across platforms |
| Over-mocked tests | Phase 084 (Frontend Integration) | Integration tests cover real code paths |
| State management gaps | Phase 084 (Frontend Integration) | State layer has >80% coverage |

---

## Sources

**MEDIUM Confidence** (based on training data, web search unavailable):

### General Testing Pitfalls
- Common React Testing Library mistakes from official documentation patterns
- Hypothesis property testing anti-patterns from community experience
- Jest best practices and common pitfalls

### Frontend Testing
- React Testing Library guidelines: "The more your tests resemble the way your software is used, the more confidence they can give you"
- Testing Library queries priority: getByRole > getByLabelText > getByText > getByTestId
- Async testing patterns from React docs and community

### Mobile Testing
- React Native testing challenges from community discussions
- Platform fragmentation issues common in cross-platform apps
- Permission testing patterns for mobile devices

### Desktop Testing
- Tauri testing patterns from official docs and community
- Cross-platform shell command differences
- IPC testing challenges

### Property-Based Testing
- Fast-check documentation for JavaScript property testing
- Frontend state invariant identification challenges
- Differences between backend and frontend property testing

**Note: Web search was unavailable during research. Findings based on training data and general testing knowledge. Some specifics may vary - verify with current documentation when implementing.**

---

*Pitfalls research for: Multi-platform integration & property testing*
*Researched: 2026-02-26*
*Confidence: MEDIUM*
