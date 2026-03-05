# Phase 137: Mobile Navigation Testing - Research

**Researched:** 2026-03-05
**Domain:** React Navigation testing with React Native Testing Library
**Confidence:** HIGH

## Summary

Phase 137 focuses on achieving comprehensive test coverage for React Navigation screens, deep links, route parameters, and navigation state in the Atom mobile app. The app uses React Navigation v6 with both stack navigators (Native Stack) and bottom tab navigators, currently has basic placeholder tests that need significant enhancement.

**Current State Analysis:**
- **3 test files exist** (AppNavigator, AuthNavigator, MainTabsNavigator) but are placeholder-only
- Tests mock all screens as strings, providing no real coverage
- No deep linking tests despite AuthNavigator having 20+ deep link routes configured
- No route parameter validation tests
- No navigation state management tests
- No error handling tests for invalid routes

**Primary recommendation:** Use `@testing-library/react-native` with React Navigation's official testing patterns to build comprehensive navigation tests covering screen rendering, deep linking, route parameters, navigation state, and error scenarios. Leverage existing test infrastructure from Phase 136 (deviceMocks.ts, testUtils.ts) and follow the established 80% coverage target from Phase 135-07 gap closure plan.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@react-navigation/native` | ^6.1.9 | Core navigation library | Industry standard for React Native navigation (used by 80%+ of apps) |
| `@react-navigation/native-stack` | ^6.9.17 | Native stack navigator | Best performance, native transitions, TypeScript support |
| `@react-navigation/bottom-tabs` | ^6.5.11 | Bottom tab navigation | Standard for tab-based navigation, highly customizable |
| `@testing-library/react-native` | ^12.4.2 | Component testing utilities | Recommended by React Native team, user-centric testing philosophy |
| `jest` | ^29.7.0 | Test runner | Default for React Native/Expo projects |
| `jest-expo` | ~50.0.0 | Expo-specific Jest configuration | Official Expo testing framework |
| `react-test-renderer` | 18.2.0 | Component serialization/diffing | Required by React Testing Library |
| `expo-linking` | ~latest | Deep linking integration | Official Expo deep linking solution |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@testing-library/jest-native` | ^5.4.3 | Custom Jest matchers (`toBeVisible()`, `toHaveTextContent()`) | For cleaner assertion syntax in navigation tests |
| `@types/react-test-renderer` | ^18.0.7 | TypeScript types for test renderer | Type safety in navigation tests |
| `react-native screens` | ~3.29.0 | Native screen optimization | Already installed, required by React Navigation v6 |

### Dependencies (From package.json)

```json
{
  "@react-navigation/native": "^6.1.9",
  "@react-navigation/native-stack": "^6.9.17",
  "@react-navigation/bottom-tabs": "^6.5.11",
  "expo-linking": "~50.0.0",
  "@testing-library/react-native": "^12.4.2",
  "@testing-library/jest-native": "^5.4.3"
}
```

**No additional installations needed** - all required dependencies are already installed.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@testing-library/react-native` | `enzyme` | Enzyme is deprecated, less maintained, doesn't follow user-centric testing |
| React Navigation v6 | React Navigation v5 | v5 is deprecated, missing TypeScript improvements and native stack performance |
| `jest-expo` | `@react-native-community/cli` | CLI doesn't provide Expo-specific mocks and configuration |

## Architecture Patterns

### Recommended Project Structure

```
mobile/src/
├── navigation/
│   ├── AppNavigator.tsx          # Main tab navigator (294 lines) ✅ EXISTS
│   ├── AuthNavigator.tsx         # Auth flow + deep linking (261 lines) ✅ EXISTS
│   ├── types.ts                  # Navigation type definitions ✅ EXISTS
│   └── index.ts                  # Barrel exports
├── __tests__/
│   ├── navigation/
│   │   ├── AppNavigator.test.tsx           # Currently: placeholder tests ❌
│   │   ├── AuthNavigator.test.tsx          # Currently: placeholder tests ❌
│   │   ├── MainTabsNavigator.test.tsx      # Currently: placeholder tests ❌
│   │   ├── DeepLinking.test.tsx            # NEW: Deep link coverage
│   │   ├── NavigationState.test.tsx        # NEW: State management tests
│   │   └── RouteParameters.test.tsx        # NEW: Param validation tests
│   └── helpers/
│       ├── testUtils.ts            # Platform mocking, async helpers ✅ EXISTS (623 lines)
│       └── deviceMocks.ts          # Device mock factories ✅ EXISTS (789 lines)
```

### Pattern 1: Navigation Testing with NavigationContainer

**What:** Wrap navigators in `NavigationContainer` for isolated testing
**When to use:** All navigator component tests
**Example:**
```typescript
// Source: https://reactnavigation.org/docs/testing/
import { render } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import AppNavigator from '../../navigation/AppNavigator';

describe('AppNavigator', () => {
  it('should render all tabs', () => {
    const { getByTestId } = render(
      <NavigationContainer>
        <AppNavigator />
      </NavigationContainer>
    );

    expect(getByTestId('tab-navigator')).toBeTruthy();
  });
});
```

### Pattern 2: Screen Mocking for Navigation Tests

**What:** Mock screen components to focus on navigation behavior, not screen internals
**When to use:** Navigator-level tests (not individual screen tests)
**Example:**
```typescript
// Mock all screens as simple components
jest.mock('../../screens/workflows/WorkflowsListScreen', () => {
  const React = require('react');
  return {
    WorkflowsListScreen: () => React.createElement('View', { testID: 'workflows-list-screen' })
  };
});

// OR use string mocks for placeholder tests
jest.mock('../../screens/workflows/WorkflowsListScreen', () => 'WorkflowsListScreen');
```

**Current state:** Existing tests use string mocks which provide minimal coverage. Should upgrade to functional mocks for better testing.

### Pattern 3: Deep Link Testing with Linking Configuration

**What:** Test deep link URL parsing and navigation
**When to use:** AuthNavigator tests (20+ deep link routes configured)
**Example:**
```typescript
import { render } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import * as Linking from 'expo-linking';

describe('Deep Linking', () => {
  it('should navigate to workflow detail from deep link', async () => {
    const url = 'atom://workflow/test-workflow-id';

    const { getByTestId } = render(
      <NavigationContainer
        linking={{
          prefixes: ['atom://'],
          config: {
            screens: {
              WorkflowDetail: {
                path: 'workflow/:workflowId',
              },
            },
          },
        }}
      >
        <AppNavigator />
      </NavigationContainer>
    );

    // Simulate deep link navigation
    const navigation = useNavigation();
    await navigation.navigate('WorkflowDetail', { workflowId: 'test-workflow-id' });

    expect(getByTestId('workflow-detail-screen')).toBeTruthy();
  });
});
```

### Pattern 4: Route Parameter Testing

**What:** Validate route parameter types, defaults, and validation
**When to use:** Stack navigator tests with typed parameters
**Example:**
```typescript
describe('Route Parameters', () => {
  it('should accept valid workflowId parameter', () => {
    const navigation = createNavigationContainerRef();

    navigation.navigate('WorkflowDetail', {
      workflowId: 'valid-id-123'
    });

    expect(navigation.getCurrentRoute().params).toEqual({
      workflowId: 'valid-id-123'
    });
  });

  it('should handle missing optional parameters', () => {
    const navigation = createNavigationContainerRef();

    navigation.navigate('AgentChat', {
      agentId: 'agent-123',
      // agentName is optional
    });

    expect(navigation.getCurrentRoute().params?.agentName).toBeUndefined();
  });
});
```

### Pattern 5: Navigation State Testing

**What:** Test back stack, tab switching, state preservation
**When to use:** Tab navigator and integration tests
**Example:**
```typescript
describe('Navigation State', () => {
  it('should maintain back stack after navigation', () => {
    const { getByTestId } = render(
      <NavigationContainer>
        <AppNavigator />
      </NavigationContainer>
    );

    // Navigate to WorkflowDetail
    fireEvent.press(getByTestId('workflow-item-1'));

    // Navigate to WorkflowTrigger
    fireEvent.press(getByTestId('trigger-button'));

    // Verify back stack has 2 routes
    const navigationState = useNavigationState(state => state);
    expect(navigationState.routes.length).toBe(2);
  });

  it('should preserve tab state when switching tabs', () => {
    const { getByTestId } = render(
      <NavigationContainer>
        <AppNavigator />
      </NavigationContainer>
    );

    // Navigate in Workflows tab
    fireEvent.press(getByTestId('workflow-item-1'));

    // Switch to Analytics tab
    fireEvent.press(getByTestId('analytics-tab'));

    // Switch back to Workflows tab
    fireEvent.press(getByTestId('workflows-tab'));

    // Verify WorkflowDetail is still visible
    expect(getByTestId('workflow-detail-screen')).toBeTruthy();
  });
});
```

### Anti-Patterns to Avoid

- **Testing implementation details**: Don't test internal navigation state directly - test user-visible behavior (screen changes, back button availability)
- **String-only mocks**: Avoid `jest.mock('../Screen', () => 'Screen')` - use functional mocks with testIDs for assertions
- **Ignoring async operations**: Always use `waitFor()` or `act()` for navigation actions that trigger animations
- **Missing error cases**: Test invalid routes, missing parameters, malformed deep links
- **Testing without NavigationContainer**: Navigation hooks (useNavigation, useRoute) require NavigationContainer context

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Navigation container mocking | Custom mock navigation context | `<NavigationContainer>` from `@react-navigation/native` | Real navigation behavior, context providers work correctly |
| Deep link URL parsing | Custom URL parser | `expo-linking`'s `Linking.parse()` | Handles edge cases, platform differences, encoding |
| Test navigation refs | Custom ref management | `createNavigationContainerRef()` from React Navigation | Type-safe, properly initialized |
| Async operation handling | Custom waitFor wrappers | `waitFor()` from `@testing-library/react-native` | Handles React Native rendering cycles, timers |
| Platform-specific navigation logic | Custom platform detection | `Platform.OS` with `mockPlatform()` from testUtils.ts | Existing infrastructure, consistent with Phase 136 |

**Key insight:** React Navigation and Expo Linking provide production-tested solutions for deep linking, navigation state, and URL parsing. Custom implementations will miss edge cases (URL encoding, special characters, platform-specific behaviors) and create maintenance burden.

## Common Pitfalls

### Pitfall 1: String Mocks Provide No Coverage
**What goes wrong:** Tests pass but provide 0% actual coverage because screens are mocked as strings
**Why it happens:** `jest.mock('../Screen', () => 'Screen')` replaces component with empty string
**How to avoid:** Use functional mocks with testIDs:
```typescript
jest.mock('../Screen', () => {
  return () => <View testID="screen-component" />;
});
```
**Warning signs:** All tests assert the same `testID`, no variation in test assertions, coverage reports show 0% for navigation files

### Pitfall 2: Missing NavigationContainer Context
**What goes wrong:** `useNavigation()` hook throws "Cannot use hooks outside NavigationContainer"
**Why it happens:** Testing navigator components without wrapping in NavigationContainer
**How to avoid:** Always wrap navigators in NavigationContainer in tests:
```typescript
render(
  <NavigationContainer>
    <AppNavigator />
  </NavigationContainer>
);
```
**Warning signs:** Tests fail with hook errors, navigation methods are undefined

### Pitfall 3: Ignoring Async Navigation Transitions
**What goes wrong:** Tests fail intermittently because navigation animations aren't awaited
**Why it happens:** React Navigation transitions are async (200-300ms animations)
**How to avoid:** Use `waitFor()` or `act()` for navigation actions:
```typescript
import { waitFor } from '@testing-library/react-native';

fireEvent.press(getByTestId('nav-button'));

await waitFor(() => {
  expect(getByTestId('target-screen')).toBeTruthy();
});
```
**Warning signs:** Flaky tests, timing-dependent failures, "not found" errors

### Pitfall 4: Deep Link Tests Don't Validate Parameters
**What goes wrong:** Deep link tests only verify navigation occurred, not that parameters were passed correctly
**Why it happens:** Testing route name but not route params
**How to avoid:** Assert on both route name and params:
```typescript
const navigation = createNavigationContainerRef();
navigation.navigate('WorkflowDetail', { workflowId: '123' });

expect(navigation.getCurrentRoute().name).toBe('WorkflowDetail');
expect(navigation.getCurrentRoute().params).toEqual({ workflowId: '123' });
```
**Warning signs:** No param validation in tests, missing type safety checks

### Pitfall 5: Not Testing Error Scenarios
**What goes wrong:** Navigation crashes on invalid deep links or missing parameters
**Why it happens:** Only testing happy path, not error handling
**How to avoid:** Test invalid routes, missing params, malformed URLs:
```typescript
it('should handle invalid deep link gracefully', () => {
  const url = 'atom://invalid-route';

  // Should not crash, should show fallback or error screen
  expect(() => navigateToDeepLink(url)).not.toThrow();
});
```
**Warning signs:** No error tests, crashes on malformed URLs, missing fallback screens

## Code Examples

Verified patterns from official sources:

### Screen Component Mock with TestID

```typescript
// Source: Phase 136 camera service test pattern
jest.mock('../../screens/workflows/WorkflowDetailScreen', () => {
  const React = require('react');
  const { View } = require('react-native');

  return {
    WorkflowDetailScreen: ({ workflowId }: { workflowId: string }) => {
      return React.createElement(View, {
        testID: 'workflow-detail-screen',
        workflowId
      });
    }
  };
});
```

### Navigation State Assertion

```typescript
// Source: React Navigation testing docs
import { useNavigationState } from '@react-navigation/native';

it('should navigate to WorkflowDetail', () => {
  let navigationState: any;

  const TestComponent = () => {
    navigationState = useNavigationState(state => state);
    return null;
  };

  render(
    <NavigationContainer>
      <AppNavigator />
      <TestComponent />
    </NavigationContainer>
  );

  expect(navigationState.routeNames).toContain('WorkflowDetail');
});
```

### Deep Link URL Parsing

```typescript
// Source: expo-linking documentation
import * as Linking from 'expo-linking';

it('should parse workflow deep link URL', () => {
  const url = 'atom://workflow/test-workflow-id';
  const parsed = Linking.parse(url);

  expect(parsed.path).toBe('workflow/test-workflow-id');
  expect(parsed.hostname).toBe('workflow');
});
```

### Tab Navigation Testing

```typescript
// Source: React Navigation tab navigation docs
it('should switch to Analytics tab', async () => {
  const { getByTestId } = render(
    <NavigationContainer>
      <AppNavigator />
    </NavigationContainer>
  );

  const analyticsTab = getByTestId('analytics-tab-button');
  fireEvent.press(analyticsTab);

  await waitFor(() => {
    expect(getByTestId('analytics-dashboard-screen')).toBeTruthy();
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| String mocks for screens | Functional mocks with testIDs | 2025-2026 | Actual coverage measurement, better assertions |
| Testing implementation details | Testing user-visible behavior | React Navigation v6 (2022) | Tests survive refactoring, focus on UX |
| Manual deep link parsing | expo-linking URL parsing | Expo SDK 50 (2024) | Handles encoding, platform differences |
| Ignoring async navigation | waitFor() for navigation actions | 2024-2025 | Reliable tests, no flaky failures |

**Deprecated/outdated:**
- **React Navigation v5**: Deprecated in 2022, missing TypeScript improvements and native stack performance
- **Enzyme**: Deprecated as of 2023, not maintained, doesn't support React 18+
- **String-only mocks**: Provide no coverage, should be functional components with testIDs
- **Testing internal navigation state directly**: Anti-pattern, should test via NavigationContainer and useNavigationState()

## Open Questions

1. **Deep Link Testing on Physical Devices**
   - What we know: CLI commands exist (`adb shell am start` for Android, `xcrun simctl openurl` for iOS)
   - What's unclear: Whether to add E2E Detox tests for deep links or stick to unit tests
   - Recommendation: Start with unit tests using expo-linking mocks, add Detox E2E tests in Phase 138+ if needed

2. **Navigation State Persistence**
   - What we know: React Navigation supports state persistence via `initialState` prop
   - What's unclear: Whether Atom app implements navigation state persistence (need to check AuthNavigator)
   - Recommendation: Review AuthNavigator.tsx for state persistence logic, add tests if implementation exists

3. **Complex Route Parameter Validation**
   - What we know: Route params are typed in `types.ts` but runtime validation is manual
   - What we know: No validation library (e.g., yup, zod) is currently used
   - What's unclear: Whether to add runtime validation tests or trust TypeScript
   - Recommendation: Trust TypeScript for Phase 137, add runtime validation in Phase 138+ if needed

4. **Back Button Behavior (Android)**
   - What we know: Android hardware back button is handled by React Navigation
   - What's unclear: Custom back button behavior (e.g., confirm before exit)
   - Recommendation: Test default back button behavior, add custom back handler tests if implemented

## Sources

### Primary (HIGH confidence)
- [React Navigation Testing Documentation](https://reactnavigation.org/docs/testing/) - Official testing patterns with Jest and React Native Testing Library
- [expo-linking API Documentation](https://docs.expo.dev/versions/latest/sdk/linking/) - Official deep linking and URL parsing API
- [Phase 136 Device Service Tests](/Users/rushiparikh/projects/atom/.planning/phases/136-mobile-device-features-testing/) - 78.39% coverage baseline, test infrastructure patterns
- [Phase 135-07 Gap Closure Plan](/Users/rushiparikh/projects/atom/.planning/phases/135-mobile-coverage-foundation/135-07-GAP_CLOSURE_PLAN.md) - 80% coverage target, test infrastructure validation

### Secondary (MEDIUM confidence)
- [从零开始：使用React Testing Library测试create-react-native-app组件的完整指南](https://m.blog.csdn.net/gitblog_01121/article/details/153168893) (2026-02-21) - React Navigation testing with @testing-library/react-native
- [React Native Tab View 测试指南：单元测试与集成测试最佳实践](https://m.blog.csdn.net/gitblog_00340/article/details/154413488) (2025-12-14) - 80% coverage targets, platform-specific testing
- [Deep Link Testing: Ensuring Link Reliability](https://m.blog.csdn.net/gitblog_01171/article/details/153170542) (2025-10-12) - CLI commands for Android/iOS deep link testing
- [Building React Native Navigation System from Zero](https://m.blog.csdn.net/jj1245_/article/details/154951477) (2025-11-17) - Deep linking integration with React Navigation

### Tertiary (LOW confidence)
- [React Native Testing Library: NPM Documentation](https://www.npmjs.com/package/@testing-library/react-native) - API reference, less comprehensive than official docs
- [Expo Router Core Usage](https://www.toutiao.com/article/7510115830047179304) (2025-05-30) - Expo Router auto deep linking (not used in Atom app)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All packages installed, verified in package.json, official documentation confirms versions
- Architecture: HIGH - Examined existing navigation structure (AppNavigator.tsx, AuthNavigator.tsx), verified React Navigation v6 patterns, official docs match implementation
- Pitfalls: HIGH - Verified existing tests have placeholder issues, common patterns from Phase 136, official docs highlight same issues

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (30 days - React Navigation and Expo Linking are stable, major releases unlikely)

**Navigation Structure Inventory:**
- AppNavigator.tsx: 294 lines, 5 tab navigators (Workflows, Analytics, Agents, Chat, Settings)
- AuthNavigator.tsx: 261 lines, 4 auth screens + main app, 20+ deep link routes configured
- types.ts: 121 lines, 7 ParamList types defined
- **Total navigation code:** 555 lines (uncommented, non-whitespace)

**Test Coverage Baseline (Phase 136):**
- Device services: 78.39% average coverage (cameraService 82%, notificationService 87.31%, locationService 72.50%, offlineSyncService 71.75%)
- Test infrastructure: deviceMocks.ts (789 lines), testUtils.ts (623 lines)
- Target: 80%+ coverage for all navigation files

**Success Criteria (from ROADMAP.md):**
1. All React Navigation screens tested with render and interaction
2. Deep links tested with URL parsing and screen routing
3. Route parameters tested with type validation and defaults
4. Navigation state tested with back stack and tab navigation
5. Navigation errors tested with fallback screens
