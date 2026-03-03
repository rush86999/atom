/**
 * Test ID constants for E2E testing.
 *
 * This file exports all data-testid attribute values used by E2E tests.
 * Using constants avoids typos and ensures consistency across the codebase.
 *
 * **IMPORTANT**: These test IDs are used by E2E tests. Do not remove or rename
 * without updating the corresponding test plans in:
 * - backend/tests/e2e_ui/tests/cross-platform/test_shared_workflows.py
 * - backend/tests/e2e_ui/tests/cross-platform/test_feature_parity.py
 *
 * Cross-platform note: Mobile (React Native) uses `testID` prop with the same
 * values. Desktop (Tauri) uses `data-testid` attributes with the same values.
 * This ensures test selector consistency across platforms.
 *
 * @see https://playwright.dev/docs/selectors#test-ids
 */

// ===========================================================================
// Agent Chat Test IDs
// ===========================================================================

export const AGENT_CHAT = {
  /** Input field for typing agent messages */
  INPUT: 'agent-chat-input',

  /** Button to send the message */
  SEND_BUTTON: 'send-message-button',

  /** Container for agent response messages */
  RESPONSE: 'agent-response',

  /** Loading indicator during streaming responses */
  STREAMING_INDICATOR: 'streaming-indicator',

  /** Button to toggle execution history sidebar */
  HISTORY_BUTTON: 'history-button',

  /** List container for execution history items */
  HISTORY_LIST: 'execution-history-list',

  /** Individual history item (append index, e.g., history-item-0) */
  HISTORY_ITEM: 'history-item',
} as const;

// ===========================================================================
// Canvas Test IDs
// ===========================================================================

export const CANVAS = {
  /** Main canvas container */
  CONTAINER: 'canvas-container',

  /** Button to close canvas presentation */
  CLOSE_BUTTON: 'close-canvas-button',

  /** Canvas type-specific containers (append type: generic, docs, email, etc.) */
  TYPE_PREFIX: 'canvas-type-',
} as const;

// Helper to generate canvas type test ID
export const getCanvasTypeTestId = (type: 'generic' | 'docs' | 'email' | 'sheets' | 'orchestration' | 'terminal' | 'coding'): string => {
  return `${CANVAS.TYPE_PREFIX}${type}`;
};

// ===========================================================================
// Authentication Test IDs
// ===========================================================================

export const AUTH = {
  /** Email input field on login form */
  EMAIL_INPUT: 'login-email-input',

  /** Password input field on login form */
  PASSWORD_INPUT: 'login-password-input',

  /** Submit button on login form */
  SUBMIT_BUTTON: 'login-submit-button',

  /** Error message displayed on login failure */
  ERROR_MESSAGE: 'login-error-message',

  /** Remember me checkbox */
  REMEMBER_ME_CHECKBOX: 'login-remember-me',

  /** Logout button in user menu/header */
  LOGOUT_BUTTON: 'logout-button',
} as const;

// ===========================================================================
// Form Test IDs
// ===========================================================================

export const FORM = {
  /** Form field prefix (append field name, e.g., form-field-email) */
  FIELD_PREFIX: 'form-field-',

  /** Submit button for forms */
  SUBMIT_BUTTON: 'form-submit-button',

  /** Success message after form submission */
  SUCCESS_MESSAGE: 'form-success-message',
} as const;

// Helper to generate form field test ID
export const getFormFieldTestId = (fieldName: string): string => {
  return `${FORM.FIELD_PREFIX}${fieldName}`;
};

// ===========================================================================
// Skills Test IDs
// ===========================================================================

export const SKILLS = {
  /** Skills marketplace list container */
  MARKETPLACE_LIST: 'skills-marketplace-list',

  /** Install button for a skill */
  INSTALL_BUTTON: 'skill-install-button',

  /** Execute button for a skill */
  EXECUTE_BUTTON: 'skill-execute-button',

  /** Skill output container */
  OUTPUT_CONTAINER: 'skill-output',
} as const;

// ===========================================================================
// Settings Test IDs
// ===========================================================================

export const SETTINGS = {
  /** Theme toggle button */
  THEME_TOGGLE: 'settings-theme-toggle',

  /** Notifications toggle */
  NOTIFICATIONS_TOGGLE: 'settings-notifications-toggle',

  /** User preferences section */
  PREFERENCES_SECTION: 'settings-preferences',
} as const;

// ===========================================================================
// Type Definitions
// ===========================================================================

type TestIds = typeof AGENT_CHAT &
  typeof CANVAS &
  typeof AUTH &
  typeof FORM &
  typeof SKILLS &
  typeof SETTINGS;

// Export all test IDs as a single object for convenience
export const TEST_IDS = {
  AGENT_CHAT,
  CANVAS,
  AUTH,
  FORM,
  SKILLS,
  SETTINGS,
} as const;

// Export individual constants for named imports
export { AGENT_CHAT, CANVAS, AUTH, FORM, SKILLS, SETTINGS };

// Default export for quick access
export default TEST_IDS;
