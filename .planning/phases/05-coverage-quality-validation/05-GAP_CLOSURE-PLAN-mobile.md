---
phase: 05-coverage-quality-validation
plan: GAP_CLOSURE-04
subsystem: mobile-testing
type: execute
wave: 1
depends_on: []
files_modified:
  - mobile/src/services/notificationService.ts
  - mobile/src/__tests__/contexts/DeviceContext.test.tsx
  - mobile/src/__tests__/services/notificationService.test.ts
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Mobile app achieves 80% coverage (from 32.09% baseline)"
    - "All 67 failing mobile tests pass"
    - "NotificationService destructuring error is fixed"
    - "DeviceContext tests call actual context methods"
  artifacts:
    - path: "mobile/src/services/notificationService.ts"
      provides: "Fixed notification service without destructuring errors"
      contains: "correct getExpoPushTokenAsync usage"
    - path: "mobile/src/__tests__/contexts/DeviceContext.test.tsx"
      provides: "DeviceContext tests with actual context method calls"
      min_tests_passing: 37
    - path: "mobile/src/__tests__/services/notificationService.test.ts"
      provides: "Notification service tests covering all methods"
      min_tests_passing: 15
  key_links:
    - from: "mobile/src/__tests__/contexts/DeviceContext.test.tsx"
      to: "mobile/src/contexts/DeviceContext.tsx"
      via: "actual context method calls, not mock assertions"
      pattern: "registerDevice|requestCapability|checkCapability|syncDevice"
    - from: "mobile/src/__tests__/services/notificationService.test.ts"
      to: "mobile/src/services/notificationService.ts"
      via: "notification service method coverage"
      pattern: "registerForPushNotifications|scheduleNotification|cancelNotification"
---

<objective>
Fix mobile app test failures and increase coverage from 32.09% to 80%.

**Purpose:** Mobile app currently has 32.09% coverage with 67 failing tests. Key issues: notificationService.ts line 158 has a destructuring error (getExpoPushTokenAsync returns data, not {status}), and DeviceContext.test.tsx has only 4/41 tests passing because tests use mock assertions instead of calling actual context methods.

**Output:** Fixed notificationService.ts destructuring error, updated DeviceContext tests to call actual context methods, and additional tests to reach 80% coverage.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/phases/05-coverage-quality-validation/05-06-SUMMARY.md
@.planning/phases/05-coverage-quality-validation/05-VERIFICATION.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@mobile/src/services/notificationService.ts
@mobile/src/contexts/DeviceContext.tsx
@mobile/src/__tests__/contexts/DeviceContext.test.tsx
@mobile/jest.config.js
</context>

<tasks>

<task type="auto">
  <name>Fix notificationService.ts destructuring error at line 158</name>
  <files>mobile/src/services/notificationService.ts</files>
  <action>
    Fix the destructuring error in the registerForPushNotifications method at line 158.

    Current code (INCORRECT):
    ```typescript
    const { status: existingStatus } = await Notifications.getExpoPushTokenAsync();
    if (existingStatus === 'granted') {
    ```

    Issue: Notifications.getExpoPushTokenAsync() returns an object with a `data` property (the token), not a `status` property. The destructuring is incorrect.

    Fixed code should be:
    ```typescript
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    if (existingStatus === 'granted') {
        // Already have permission, get token
        const { data: tokenData } = await Notifications.getExpoPushTokenAsync({
            projectId: Constants.expoConfig?.extra?.eas?.projectId,
        });
    ```

    Or, to check if a token is already registered:
    ```typescript
    if (this.pushToken) {
        console.log('NotificationService: Push token already registered');
        return this.pushToken;
    }
    ```

    Fix the method to:
    1. Check permissions first with getPermissionsAsync() (returns {status})
    2. Request permissions if not granted
    3. Get push token with getExpoPushTokenAsync() (returns {data: token})
  </action>
  <verify>
    Run: cd mobile && npm test -- --testPathPattern=navigationService --coverage

    Expected: No destructuring errors, notification service tests pass (8/19 currently blocked by this error)
  </verify>
  <done>
    NotificationService.ts line 158 destructuring error fixed. 8 previously blocked tests now pass.
  </done>
</task>

<task type="auto">
  <name>Update DeviceContext tests to call actual context methods</name>
  <files>mobile/src/__tests__/contexts/DeviceContext.test.tsx</files>
  <action>
    Update the DeviceContext tests to call actual context methods instead of just asserting mock return values.

    Current issue: Tests verify that mock functions were called, but don't test the actual context behavior. Only 4/41 tests pass.

    Update test patterns:
    1. Instead of checking `expect(mockFunction).toHaveBeenCalled()`, actually trigger the context methods
    2. Test the full flow: user action -> context method -> state update -> UI update
    3. Use `act()` from @testing-library/react-native for state updates
    4. Test actual state changes via testIDs on rendered components

    Example pattern:
    ```typescript
    test('device registration updates state', async () => {
        const { getByTestId, getByText } = renderWithDeviceProvider();

        // Trigger registration
        const registerButton = getByText('Register Device');
        await act(() => fireEvent.press(registerButton));

        // Verify state updated
        await waitFor(() => {
            expect(getByTestId('isRegistered')).toHaveTextContent('true');
        });
    });
    ```

    Update tests to cover:
    - Device registration flow (currently 4 tests passing - need 10+)
    - Permission request flow (camera, location, notifications, biometric)
    - Device capability checking
    - Device state management transitions
    - Device sync with backend
    - Error handling scenarios

    Target: 37+/41 tests passing (up from 4/41)
  </action>
  <verify>
    Run: cd mobile && npm test -- --testPathPattern=DeviceContext --coverage

    Expected: 37+/41 tests passing (up from 4/41), coverage increases significantly
  </verify>
  <done>
    DeviceContext tests updated to call actual context methods. Pass rate increases from 10% to 90%+.
  </done>
</task>

<task type="auto">
  <name>Add missing mobile tests to reach 80% coverage</name>
  <files>mobile/src/__tests__/services/*.test.ts mobile/src/__tests__/contexts/*.test.tsx</files>
  <action>
    Add additional tests to increase mobile coverage from 32.09% to 80%.

    Identify low-coverage files and add tests:
    1. AuthContext - add tests for authentication flows, token refresh, error handling
    2. Other services - check coverage report for gaps
    3. Components - add tests for uncovered UI components

    Run coverage first to identify gaps:
    ```bash
    cd mobile && npm run test:coverage
    ```

    Then add tests for the lowest coverage files first. Prioritize:
    - Services with <50% coverage
    - Contexts with <50% coverage
    - Frequently used components

    Target: Add 100-200 lines of tests for uncovered paths.
  </action>
  <verify>
    Run: cd mobile && npm run test:coverage

    Expected: Coverage increases from 32.09% to 80%+ across the board
  </verify>
  <done>
    Additional mobile tests added. Overall coverage increases from 32% to 80%+.
  </done>
</task>

</tasks>

<verification>
Overall verification steps:
1. Run mobile tests with coverage: cd mobile && npm run test:coverage
2. Verify coverage exceeds 80% overall
3. Verify all previously failing tests now pass:
   - NotificationService tests: 15+/19 passing (from 11/19)
   - DeviceContext tests: 37+/41 passing (from 4/41)
   - Overall pass rate: 560+/602 (from 535/602)
4. Verify no TypeScript or runtime errors in test output
</verification>

<success_criteria>
Mobile app achieves 80% coverage:
- notificationService.ts destructuring error fixed (line 158)
- DeviceContext tests pass at 90%+ rate (37+/41)
- Overall mobile coverage: 80%+ (from 32.09%)
- All 67 previously failing tests fixed
- Test suite completes without errors
</success_criteria>

<output>
After completion, create `.planning/phases/05-coverage-quality-validation/05-GAP_CLOSURE-04-SUMMARY.md`
</output>
