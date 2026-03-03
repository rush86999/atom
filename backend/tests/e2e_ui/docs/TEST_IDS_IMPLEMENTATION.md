# Test ID Implementation Guide for Cross-Platform E2E Tests

## Overview

This document explains how to add `data-testid` attributes to frontend components for cross-platform E2E testing. The test ID constants are defined in `frontend-nextjs/src/lib/testIds.ts`.

## Why Test IDs?

**Problem**: CSS selectors (classes, IDs) are fragile and break when styling changes.
**Solution**: Use `data-testid` attributes that are stable and only used for testing.

## Cross-Platform Consistency

- **Web (Next.js)**: Uses `data-testid="..."` attributes
- **Mobile (React Native)**: Uses `testID="..."` props (same values)
- **Desktop (Tauri)**: Uses `data-testid="..."` attributes (same values)

This ensures E2E tests can use the same selectors across all platforms.

## Test ID Constants File

**Location**: `frontend-nextjs/src/lib/testIds.ts`

This file exports all test ID constants to avoid typos and ensure consistency.

### Usage Example

```tsx
import { TEST_IDS } from '@/lib/testIds';

// In your component
<input
  data-testid={TEST_IDS.AGENT_CHAT.INPUT}
  type="text"
  placeholder="Type a message..."
/>

<button data-testid={TEST_IDS.AGENT_CHAT.SEND_BUTTON}>
  Send
</button>
```

## Required Test IDs by Component

### 1. Agent Chat Components

**File**: `frontend-nextjs/pages/chat/index.tsx` or equivalent

Required test IDs:
- `agent-chat-input`: Message input field
- `send-message-button`: Send button
- `agent-response`: Agent response container
- `streaming-indicator`: Loading indicator during streaming
- `history-button`: Toggle history sidebar
- `execution-history-list`: History list container
- `history-item-{index}`: Individual history items

### 2. Canvas Components

**File**: `frontend-nextjs/components/canvas/CanvasContainer.tsx` or equivalent

Required test IDs:
- `canvas-container`: Main canvas container
- `canvas-type-{type}`: Canvas type-specific container (generic, docs, email, sheets, orchestration, terminal, coding)
- `close-canvas-button`: Close button

### 3. Authentication Components

**File**: `frontend-nextjs/pages/login.tsx` or equivalent

Required test IDs:
- `login-email-input`: Email input field
- `login-password-input`: Password input field
- `login-submit-button`: Login button
- `login-error-message`: Error message
- `logout-button`: Logout button

### 4. Form Components

**File**: Any form component (canvas forms, settings forms, etc.)

Required test IDs:
- `form-field-{name}`: Form field (use field name as suffix)
- `form-submit-button`: Submit button
- `form-success-message`: Success message

### 5. Skills Components

**File**: `frontend-nextjs/pages/marketplace.tsx` or equivalent

Required test IDs:
- `skills-marketplace-list`: Skills list
- `skill-install-button`: Install button
- `skill-execute-button`: Execute button
- `skill-output`: Output container

### 6. Settings Components

**File**: `frontend-nextjs/pages/settings/index.tsx` or equivalent

Required test IDs:
- `settings-theme-toggle`: Theme toggle
- `settings-notifications-toggle`: Notifications toggle
- `settings-preferences`: Preferences section

## Implementation Checklist

### Phase 1: Web Components (Current)
- [ ] Add data-testid to agent chat page (`pages/chat/index.tsx`)
- [ ] Add data-testid to canvas components (`components/canvas/`)
- [ ] Add data-testid to login page (`pages/login.tsx`)
- [ ] Add data-testid to skills marketplace (`pages/marketplace.tsx`)
- [ ] Add data-testid to settings page (`pages/settings/index.tsx`)

### Phase 2: Mobile Components (React Native)
- [ ] Create `mobile/src/constants/testIds.ts` with same values
- [ ] Add testID props to mobile AgentChatScreen
- [ ] Add testID props to mobile CanvasScreen
- [ ] Add testID props to mobile LoginScreen

### Phase 3: Desktop Components (Tauri)
- [ ] Ensure Tauri components use same data-testid values
- [ ] Verify tauri-driver can access data-testid attributes

## Example Implementation

### Before (Fragile)

```tsx
// ❌ Bad: Breaks if CSS classes change
<input className="chat-input w-full px-4 py-2" />
<button className="bg-blue-500 text-white">Send</button>
```

### After (Resilient)

```tsx
// ✅ Good: Stable test selectors
import { TEST_IDS } from '@/lib/testIds';

<input
  data-testid={TEST_IDS.AGENT_CHAT.INPUT}
  className="chat-input w-full px-4 py-2"
/>
<button
  data-testid={TEST_IDS.AGENT_CHAT.SEND_BUTTON}
  className="bg-blue-500 text-white"
>
  Send
</button>
```

## Testing Your Implementation

After adding test IDs, verify they exist in the DOM:

1. Start dev server: `cd frontend-nextjs && npm run dev`
2. Open browser DevTools (F12)
3. Go to Elements tab
4. Use search (Ctrl+F) for `data-testid`
5. Verify all expected test IDs are present

```bash
# Run E2E tests to verify selectors work
cd backend/tests/e2e_ui
pytest tests/cross-platform/test_shared_workflows.py -v
```

## JSDoc Documentation

Add JSDoc comments to components that use test IDs:

```tsx
/**
 * Agent Chat Input Component
 *
 * **data-testid attributes used by E2E tests - do not remove without updating test plans**
 * - agent-chat-input: Main input field
 * - send-message-button: Send button
 */
export function AgentChatInput() {
  // ...
}
```

## Migration Path

If you encounter existing components without test IDs:

1. **Import test ID constants**:
   ```tsx
   import { TEST_IDS } from '@/lib/testIds';
   ```

2. **Add data-testid to key interactive elements**:
   - Inputs, buttons, links
   - Containers, lists, grids
   - Modals, popovers, dropdowns

3. **Run E2E tests to verify**:
   ```bash
   pytest backend/tests/e2e_ui/tests/cross-platform/ -v
   ```

4. **Document in component JSDoc** (see above)

## Troubleshooting

### E2E tests can't find elements

**Problem**: `Locator.click: Target closed` or `TimeoutError`
**Solution**:
1. Verify data-testid is spelled correctly
2. Check browser DevTools to confirm element exists
3. Ensure element is visible (not hidden by CSS)
4. Check for dynamic IDs (use data-testid instead)

### Tests work locally but fail in CI

**Problem**: Flaky tests in CI environment
**Solution**:
1. Ensure data-testid values are constants (not generated)
2. Avoid using index-based selectors (e.g., `li:nth-child(3)`)
3. Use explicit waits: `await page.waitForSelector('[data-testid="..."]')`

### Mobile testID props not working

**Problem**: React Native testID not found by Detox
**Solution**:
1. Verify `testID` prop (not `data-testid`) for React Native
2. Check mobile/constants/testIds.ts exports match web values
3. Ensure component is rendered (not conditionally hidden)

## References

- **Web Tests**: `backend/tests/e2e_ui/tests/cross-platform/test_shared_workflows.py`
- **Test Constants**: `frontend-nextjs/src/lib/testIds.ts`
- **Page Objects**: `backend/tests/e2e_ui/pages/cross_platform_objects.py`
- **Playwright Selectors**: https://playwright.dev/docs/selectors
- **Detox Selectors**: https://wix.github.io/Detox/docs/api/simulation/matchers

## Summary

By following this guide, you ensure that:
1. E2E tests are resilient to styling changes
2. Test selectors are consistent across web, mobile, and desktop
3. Tests are easier to maintain and debug
4. New developers can understand the testing approach

**Remember**: Test IDs are for testing only. Don't use them for CSS styling or JavaScript logic.
