---
phase: 212-80pct-coverage-clean-slate
plan: WAVE3B
type: execute
wave: 3
depends_on: ["212-WAVE2A", "212-WAVE2B", "212-WAVE2C", "212-WAVE2D"]
files_modified:
  - mobile/src/components/__tests__/Camera.test.tsx
  - mobile/src/components/__tests__/Location.test.tsx
  - mobile/src/components/__tests__/Notifications.test.tsx
  - mobile/src/storage/__tests__/AsyncStorage.test.ts
  - mobile/src/navigation/__tests__/Navigation.test.tsx
  - desktop-app/src-tauri/tests/core_logic_test.rs
  - desktop-app/src-tauri/tests/ipc_handlers_test.rs
  - desktop-app/src/components/__tests__/WindowManager.test.tsx
autonomous: true

must_haves:
  truths:
    - "Mobile device feature components tested (Camera, Location, Notifications)"
    - "Mobile storage and navigation tested"
    - "Desktop Rust backend tested"
    - "Desktop Tauri frontend tested"
    - "Mobile coverage increases from 0% to 40%+ (realistic target)"
    - "Desktop coverage increases from 0% to 40%+ (realistic target)"
  artifacts:
    - path: "mobile/src/components/__tests__/Camera.test.tsx"
      provides: "React Native tests for Camera component"
      min_lines: 150
    - path: "mobile/src/components/__tests__/Location.test.tsx"
      provides: "React Native tests for Location component"
      min_lines: 150
    - path: "mobile/src/components/__tests__/Notifications.test.tsx"
      provides: "React Native tests for Notifications component"
      min_lines: 150
    - path: "mobile/src/storage/__tests__/AsyncStorage.test.ts"
      provides: "React Native tests for AsyncStorage"
      min_lines: 150
    - path: "mobile/src/navigation/__tests__/Navigation.test.tsx"
      provides: "React Native tests for Navigation"
      min_lines: 150
    - path: "desktop-app/src-tauri/tests/core_logic_test.rs"
      provides: "Rust tests for desktop core logic"
      min_lines: 200
      exports: ["test_core_logic", "test_file_operations"]
    - path: "desktop-app/src/components/__tests__/WindowManager.test.tsx"
      provides: "React tests for Tauri window management"
      min_lines: 200
  key_links:
    - from: "mobile/src/components/__tests__/Camera.test.tsx"
      to: "mobile/src/components/Camera.tsx"
      via: "React Native Testing Library"
    - from: "desktop-app/src-tauri/tests/core_logic_test.rs"
      to: "desktop-app/src-tauri/src/core_logic.rs"
      via: "Rust unit tests"
---

<objective>
Establish mobile and desktop testing foundation with realistic 40%+ coverage targets.

Purpose: Mobile and desktop platforms have large codebases (~15,000 and ~10,000 lines respectively). Achieving 70%+ from 0% with only 4-5 test files is unrealistic. This plan establishes test infrastructure and achieves 40%+ coverage with focused tests on critical components.

Note: 70%+ coverage would require 6-8 additional test files per platform. 40%+ is a realistic target for this wave.

Output: 8 test files (5 mobile, 3 desktop) with 1,300+ total lines, achieving mobile 40%+ and desktop 40%+ coverage.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md

# Mobile Testing Pattern Reference
React Native Testing Library: @testing-library/react-native
Mock native modules: react-native-mock-render
Async storage mock: @react-native-async-storage/async-storage/jest/async-storage-mock

# Desktop Testing Pattern Reference
Rust: cargo test, tarpaulin for coverage
Tauri: @tauri-apps/api mock

# Realistic Coverage Analysis

## Mobile (Target: 40%)
- Baseline: 0%
- Codebase: ~15,000 lines
- 40% target: ~6,000 lines to cover
- This plan: 5 test files (~750 lines tests)
- Tests critical paths: device features, storage, navigation

## Desktop (Target: 40%)
- Baseline: 0%
- Codebase: ~10,000 lines (Rust + TypeScript)
- 40% target: ~4,000 lines to cover
- This plan: 3 test files (~600 lines tests)
- Tests critical paths: core logic, IPC handlers, window management

# Target Files

## Mobile Device Features
- Camera.test.tsx: Camera component tests
- Location.test.tsx: Location component tests
- Notifications.test.tsx: Notification tests

## Mobile State & Navigation
- AsyncStorage.test.ts: Storage tests
- Navigation.test.tsx: Navigation tests

## Desktop Rust Backend
- core_logic_test.rs: Core logic tests
- ipc_handlers_test.rs: IPC handler tests

## Desktop Tauri Frontend
- WindowManager.test.tsx: Window management tests
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create mobile tests for device features</name>
  <files>mobile/src/components/__tests__/Camera.test.tsx mobile/src/components/__tests__/Location.test.tsx mobile/src/components/__tests__/Notifications.test.tsx</files>
  <action>
Create React Native tests for mobile device features:

1. mobile/src/components/__tests__/Camera.test.tsx:
   - test_renders_camera_view(): Renders camera component
   - test_request_camera_permission(): Requests permission
   - test_take_picture(): Takes picture
   - test_handle_permission_denied(): Handles denial
   - test_camera_error(): Handles camera errors

2. mobile/src/components/__tests__/Location.test.tsx:
   - test_renders_location_view(): Renders location component
   - test_request_location_permission(): Requests permission
   - test_get_current_location(): Gets current location
   - test_watch_location(): Watches location changes
   - test_location_error(): Handles location errors

3. mobile/src/components/__tests__/Notifications.test.tsx:
   - test_renders_notification_view(): Renders notifications
   - test_request_notification_permission(): Requests permission
   - test_send_local_notification(): Sends notification
   - test_schedule_notification(): Schedules notification
   - test_notification_error(): Handles errors

Use @testing-library/react-native, react-native-mock-render
  </action>
  <verify>
cd mobile && npm test -- --coverage
# Mobile coverage should be 40%+
  </verify>
  <done>
All mobile device feature tests passing, 40%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 2: Create mobile tests for state and navigation</name>
  <files>mobile/src/storage/__tests__/AsyncStorage.test.ts mobile/src/navigation/__tests__/Navigation.test.tsx</files>
  <action>
Create React Native tests for state management and navigation:

1. mobile/src/storage/__tests__/AsyncStorage.test.ts:
   - test_set_item(): Stores item
   - test_get_item(): Retrieves item
   - test_remove_item(): Removes item
   - test_clear(): Clears all items
   - test_persistence(): Survives app restart
   - test_json_serialization(): Handles JSON data

2. mobile/src/navigation/__tests__/Navigation.test.tsx:
   - test_navigate_to_screen(): Navigates to screen
   - test_navigate_with_params(): Passes params
   - test_go_back(): Goes back
   - test_navigate_replace(): Replaces screen
   - test_deep_link(): Handles deep links
   - test_tab_navigation(): Tests tab navigation

Use @testing-library/react-native, @react-navigation/native mock
  </action>
  <verify>
cd mobile && npm test -- --coverage
# Mobile coverage should be 40%+
  </verify>
  <done>
All mobile state and navigation tests passing, 40%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 3: Create desktop tests for Rust backend</name>
  <files>desktop-app/src-tauri/tests/core_logic_test.rs desktop-app/src-tauri/tests/ipc_handlers_test.rs</files>
  <action>
Create Rust tests for desktop backend:

1. desktop-app/src-tauri/tests/core_logic_test.rs:
   #[cfg(test)]
   mod tests {
       use super::*;

       #[test]
       fn test_core_logic_initialization() {
           // Test core logic initialization
       }

       #[test]
       fn test_file_operations() {
           // Test file read/write
       }

       #[test]
       fn test_state_management() {
           // Test state persistence
       }

       #[test]
       fn test_error_handling() {
           // Test error cases
       }
   }

2. desktop-app/src-tauri/tests/ipc_handlers_test.rs:
   #[cfg(test)]
   mod tests {
       use super::*;

       #[test]
       fn test_ipc_command_registration() {
           // Test command registration
       }

       #[test]
       fn test_ipc_handler_execution() {
           // Test handler execution
       }

       #[test]
       fn test_ipc_error_handling() {
           // Test error handling
       }
   }

Use cargo test, tarpaulin for coverage
  </action>
  <verify>
cd desktop-app/src-tauri && cargo test
cd desktop-app/src-tauri && cargo tarpaulin --out Html
# Rust coverage should be 40%+
  </verify>
  <done>
All desktop Rust tests passing, 40%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 4: Create desktop tests for Tauri frontend</name>
  <files>desktop-app/src/components/__tests__/WindowManager.test.tsx</files>
  <action>
Create Tauri frontend tests:

1. desktop-app/src/components/__tests__/WindowManager.test.tsx:
   - test_renders_main_window(): Renders main window
   - test_create_window(): Creates new window
   - test_close_window(): Closes window
   - test_minimize_window(): Minimizes window
   - test_maximize_window(): Maximizes window
   - test_window_focus(): Handles focus events

2. Use @testing-library/react, mock @tauri-apps/api

3. Mock Tauri invoke API
  </action>
  <verify>
cd desktop-app && npm test -- --coverage
# Desktop frontend coverage should be 40%+
  </verify>
  <done>
All desktop Tauri tests passing, 40%+ coverage achieved
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run mobile tests:
   cd mobile && npm test -- --coverage --watchAll=false
   # Mobile should be 40%+ (realistic target)

2. Run desktop Rust tests:
   cd desktop-app/src-tauri && cargo tarpaulin --out Html
   # Rust should be 40%+

3. Run desktop frontend tests:
   cd desktop-app && npm test -- --coverage
   # Desktop frontend should be 40%+

4. Verify all platforms meet targets
</verification>

<success_criteria>
1. Mobile coverage >= 40% (realistic target from 0% baseline)
2. Desktop Rust coverage >= 40% (realistic target from 0% baseline)
3. Desktop frontend coverage >= 40% (realistic target from 0% baseline)
4. All mobile tests pass
5. All desktop tests pass
6. No regression in existing tests
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE3B-SUMMARY.md`
</output>
