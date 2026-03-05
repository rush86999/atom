# Frontend Accessibility Testing Guide

**Last Updated:** March 4, 2026
**Standard:** WCAG 2.1 AA Compliance
**Tooling:** jest-axe v10.0.0, React Testing Library v16.3.0

## Overview

This guide covers automated accessibility testing for the Atom frontend using jest-axe. Automated tests catch ~70% of WCAG violations, ensuring keyboard accessibility, screen reader compatibility, and ARIA attribute correctness.

**What gets tested:**
- ✅ Keyboard navigation (Tab, Enter, Escape, Space)
- ✅ ARIA attributes (aria-label, aria-expanded, aria-invalid)
- ✅ Semantic HTML (headings, landmarks, roles)
- ✅ Form labels and error messages
- ✅ Focus management (focus traps, focus restoration)
- ✅ Dynamic content (aria-live regions)

**What needs manual testing:**
- ⚠️ Color contrast (requires real browser rendering)
- ⚠️ Screen reader navigation (NVDA, JAWS, VoiceOver)
- ⚠️ Keyboard usability (beyond just functional)
- ⚠️ Visual focus indicators

## Setup

### Installation

jest-axe is already installed in frontend-nextjs:

```bash
npm install --save-dev jest-axe
npm install --save-dev @types/jest-axe  # TypeScript definitions
```

### Global Matcher Configuration

The `toHaveNoViolations()` matcher is configured globally in `tests/setup.ts`:

```typescript
// tests/setup.ts
import { toHaveNoViolations } from 'jest-axe';

// Extend Jest expect with jest-axe matcher
expect.extend(toHaveNoViolations);
```

### Accessibility Helper Module

The accessibility configuration is in `tests/accessibility-config.ts`:

```typescript
import { configureAxe } from 'jest-axe';

// Configure for WCAG 2.1 AA
const axe = configureAxe({
  rules: {
    // Disable landmark rules for isolated component testing
    'region': { enabled: false }
  },
  // Only consider critical and serious violations
  impactLevels: ['critical', 'serious']
});

export default axe;
```

## Testing Patterns

### 1. Basic Accessibility Test

Every component should have at least one accessibility test:

```typescript
import { render } from '@testing-library/react';
import { axe } from 'jest-axe';
import { Button } from '@/components/ui/button';

describe('Button Accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(<Button>Click me</Button>);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
```

### 2. Icon-Only Buttons

Icon-only buttons MUST have `aria-label`:

```typescript
it('should have accessible name when using icon', async () => {
  const { container } = render(
    <Button aria-label="Close dialog">
      <XIcon />
    </Button>
  );
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

**Do NOT do this:**
```typescript
// BAD - No accessible name
<Button onClick={handleClose}>
  <XIcon />
</Button>
```

### 3. Keyboard Navigation Testing

All interactive components must be keyboard-accessible:

```typescript
import userEvent from '@testing-library/user-event';

describe('Button Keyboard Navigation', () => {
  it('should be focusable with Tab key', async () => {
    const user = userEvent.setup();
    render(<Button>Submit</Button>);

    const button = screen.getByRole('button', { name: 'Submit' });

    // Tab to focus button
    await user.tab();

    expect(button).toHaveFocus();
  });

  it('should activate with Enter key', async () => {
    const user = userEvent.setup();
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Submit</Button>);

    const button = screen.getByRole('button', { name: 'Submit' });
    button.focus();

    // Press Enter to activate
    await user.keyboard('{Enter}');

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('should activate with Space key', async () => {
    const user = userEvent.setup();
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Submit</Button>);

    const button = screen.getByRole('button', { name: 'Submit' });
    button.focus();

    // Press Space to activate
    await user.keyboard(' ');  // Space character

    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

### 4. ARIA Attributes Testing

Components with dynamic content need proper ARIA attributes:

```typescript
import { Dialog } from '@/components/ui/dialog';

describe('Dialog Accessibility', () => {
  it('should have no accessibility violations when open', async () => {
    const { baseElement } = render(
      <Dialog open>
        <Dialog.Content>
          <Dialog.Title>Confirm Action</Dialog.Title>
          <Dialog.Description>Are you sure?</Dialog.Description>
        </Dialog.Content>
      </Dialog>
    );

    const results = await axe(baseElement);
    expect(results).toHaveNoViolations();
  });

  it('should have aria-labelledby and aria-describedby', () => {
    render(
      <Dialog open>
        <Dialog.Content>
          <Dialog.Title>Confirm</Dialog.Title>
          <Dialog.Description>Are you sure?</Dialog.Description>
        </Dialog.Content>
      </Dialog>
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-labelledby');
    expect(dialog).toHaveAttribute('aria-describedby');
  });
});
```

**React Portal Testing:** Dialog components render via React Portal to `document.body`, so use `baseElement` instead of `container`:

```typescript
it('should test React Portal accessibility', async () => {
  const { baseElement } = render(
    <Dialog open><Dialog.Content>Content</Dialog.Content></Dialog>
  );

  // Use baseElement (includes document.body) instead of container
  const results = await axe(baseElement);
  expect(results).toHaveNoViolations();
});
```

### 5. Focus Management Testing

Dialogs and modals must trap focus within them:

```typescript
describe('Dialog Focus Management', () => {
  it('should trap focus within dialog', async () => {
    const user = userEvent.setup();
    render(
      <Dialog open>
        <Dialog.Content>
          <button>Cancel</button>
          <button>Confirm</button>
        </Dialog.Content>
      </Dialog>
    );

    const cancel = screen.getByText('Cancel');
    const confirm = screen.getByText('Confirm');

    // Focus first button
    cancel.focus();
    expect(cancel).toHaveFocus();

    // Tab to second button
    await user.tab();
    expect(confirm).toHaveFocus();

    // Tab should cycle back to first button (focus trap)
    await user.tab();
    expect(cancel).toHaveFocus();
  });

  it('should close dialog on Escape key', async () => {
    const user = userEvent.setup();
    const handleClose = jest.fn();
    render(
      <Dialog open onClose={handleClose}>
        <Dialog.Content>
          <Dialog.Title>Title</Dialog.Title>
        </Dialog.Content>
      </Dialog>
    );

    await user.keyboard('{Escape}');
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('should return focus to trigger after close', async () => {
    const user = userEvent.setup();
    const handleClose = jest.fn();

    render(
      <>
        <button id="trigger">Open</button>
        <Dialog open onClose={handleClose}>
          <Dialog.Content>
            <Dialog.Title>Title</Dialog.Title>
          </Dialog.Content>
        </Dialog>
      </>
    );

    const trigger = screen.getByText('Open');
    trigger.focus();
    expect(trigger).toHaveFocus();

    // Close dialog
    await user.keyboard('{Escape}');

    // Focus should return to trigger (handled by Radix UI)
    expect(trigger).toHaveFocus();
  });
});
```

### 6. Dynamic Content Testing

Dynamic content updates need `aria-live` regions:

```typescript
import { AgentOperationTracker } from '@/components/canvas/agent-operation-tracker';

describe('AgentOperationTracker Accessibility', () => {
  it('should have aria-live for progress updates', () => {
    render(<AgentOperationTracker operationId="123" />);

    const tracker = screen.getByRole('log');
    expect(tracker).toHaveAttribute('aria-live', 'polite');
  });

  it('should announce operation completion', async () => {
    const { container } = render(
      <AgentOperationTracker operationId="123" status="complete" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
```

### 7. Form Accessibility Testing

Forms need proper labels, error messages, and validation:

```typescript
import { Input } from '@/components/ui/input';

describe('Input Accessibility', () => {
  it('should have accessible label', async () => {
    const { container } = render(
      <div>
        <label htmlFor="name">Name</label>
        <Input id="name" />
      </div>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have aria-label when visible label is absent', async () => {
    const { container } = render(
      <Input aria-label="Search query" placeholder="Search..." />
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should show error message with aria-invalid', async () => {
    render(
      <Input aria-invalid="true" aria-describedby="error" />
    );
    const input = screen.getByRole('textbox');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby', 'error');
  });

  it('should be keyboard navigable', async () => {
    const user = userEvent.setup();
    render(<Input placeholder="Type here" />);

    const input = screen.getByPlaceholderText('Type here');

    // Tab to focus
    await user.tab();
    expect(input).toHaveFocus();

    // Type text
    await user.keyboard('Hello');
    expect(input).toHaveValue('Hello');
  });
});
```

**Required Field Indicators:**
```typescript
<label htmlFor="email">
  Email <span aria-hidden="true">*</span>
</label>
<Input id="email" required aria-required="true" />
```

### 8. Select Component Testing

Select dropdowns need `aria-expanded` state:

```typescript
import { Select } from '@/components/ui/select';

describe('Select Accessibility', () => {
  it('should have no accessibility violations when closed', async () => {
    const { container } = render(
      <Select>
        <Select.Trigger>Choose option</Select.Trigger>
        <Select.Content>
          <Select.Item value="1">Option 1</Select.Item>
          <Select.Item value="2">Option 2</Select.Item>
        </Select.Content>
      </Select>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have aria-expanded when closed', () => {
    render(
      <Select open={false}>
        <Select.Trigger>Choose option</Select.Trigger>
      </Select>
    );
    const trigger = screen.getByRole('combobox');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('should have aria-expanded when open', () => {
    render(
      <Select open>
        <Select.Trigger>Choose option</Select.Trigger>
      </Select>
    );
    const trigger = screen.getByRole('combobox');
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });
});
```

## Common Pitfalls

### 1. Color Contrast Testing in JSDOM

**Problem:** jest-axe reports no color contrast violations even when contrast is insufficient.

**Why:** JSDOM doesn't render CSS or compute actual colors.

**Solution:** Accept this limitation and use manual testing tools:
- WebAIM Contrast Checker: https://webaim.org/resources/contrastchecker/
- axe DevTools browser extension
- Playwright for automated contrast checks

```typescript
// Add test comment to document this limitation
it('should have no accessibility violations', async () => {
  const { container } = render(<Button>Submit</Button>);
  const results = await axe(container);

  // Note: Color contrast not tested (JSDOM limitation)
  // Verified manually with WebAIM Contrast Checker
  expect(results).toHaveNoViolations();
});
```

### 2. Isolated Component Testing with Landmark Violations

**Problem:** Testing a single Button fails with "All page content must be contained by landmarks".

**Why:** axe-core expects page-level landmarks (`<main>`, `<nav>`, `<header>`, `<footer>`). Isolated components don't have these.

**Solution:** The 'region' rule is disabled globally in `tests/accessibility-config.ts`:

```typescript
const axe = configureAxe({
  rules: {
    'region': { enabled: false }  // Disable for isolated component testing
  }
});
```

### 3. jest-axe with jest.useFakeTimers()

**Problem:** Tests timeout when using jest-axe after `jest.useFakeTimers()`.

**Why:** axe-core uses `setTimeout` internally. Fake timers never fire.

**Solution:** Switch to real timers temporarily:

```typescript
it('should work with fake timers', async () => {
  jest.useFakeTimers();

  // Test component logic with fake timers
  // ...

  // Switch to real timers for accessibility check
  jest.useRealTimers();
  const { container } = render(<Component />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();

  // Switch back to fake timers if needed
  jest.useFakeTimers();
});
```

### 4. Testing React Portals

**Problem:** Dialog accessibility tests pass even though component has violations.

**Why:** React Testing Library's `render()` returns `container` (root div), but Portals render at `document.body`. `axe(container)` only checks root div.

**Solution:** Use `baseElement` instead of `container`:

```typescript
it('should test React Portal accessibility', async () => {
  const { baseElement } = render(
    <Dialog open><Dialog.Content>Content</Dialog.Content></Dialog>
  );

  // Use baseElement (includes document.body) instead of container
  const results = await axe(baseElement);
  expect(results).toHaveNoViolations();
});
```

### 5. Missing ARIA Labels on Icon-Only Buttons

**Problem:** jest-axe fails with "Element does not have an accessible name (button-name)".

**Why:** Screen readers can't infer button purpose from icon alone.

**Solution:** Add `aria-label`:

```typescript
// BAD - No accessible name
<Button onClick={handleClose}>
  <XIcon />
</Button>

// GOOD - Has aria-label
<Button onClick={handleClose} aria-label="Close dialog">
  <XIcon />
</Button>

// GOOD - Has visible text
<Button onClick={handleClose}>
  <XIcon /> Close
</Button>
```

## CI/CD Integration

### GitHub Actions Workflow

Accessibility tests run automatically on every PR:

**File:** `frontend-nextjs/.github/workflows/frontend-accessibility.yml`

**Triggers:**
- Push to main/develop
- Pull request to main/develop
- Manual workflow dispatch

**What happens:**
1. Checkout code
2. Install dependencies (npm ci --legacy-peer-deps)
3. Clear Jest cache
4. Run accessibility tests: `npm run test:ci -- --testPathPattern="\.a11y\.test\.tsx$"`
5. Generate JSON test results
6. Comment PR with violation count and remediation guidance
7. Fail workflow if violations found

**Example PR Comment:**

```markdown
## ♿ Accessibility Test Results

**Total Tests:** 17
**Passed:** 15
**Failed:** 2
**Pass Rate:** 88.24%

### ⚠️ Accessibility Violations Found

This PR has accessibility violations that must be fixed before merging.

### Common WCAG 2.1 AA Violations

| Category | Impact | Affected Components |
|----------|--------|---------------------|
| Missing alt text | Critical | Images, icons |
| Missing form labels | Critical | Inputs, selects |
| Low color contrast | Serious | Text, buttons |
| Missing ARIA labels | Serious | Icon buttons |
| Invalid HTML structure | Serious | All components |

### Remediation Steps

1. Run accessibility tests locally: `cd frontend-nextjs && npm test -- --testPathPattern="\\.a11y\\.test\\.tsx$"`
2. Fix WCAG violations in affected components
3. Verify fixes with axe DevTools browser extension
4. Manual test with screen readers (NVDA, JAWS, VoiceOver)
5. Commit fixes and push to this branch

### Resources

- [WCAG 2.1 AA Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [axe DevTools Extension](https://www.deque.com/axe/devtools/)
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- [frontend-nextjs/ACCESSIBILITY.md](https://github.com/rushiparikh/atom/blob/main/frontend-nextjs/ACCESSIBILITY.md)
```

### Running Tests Locally

**Run all accessibility tests:**
```bash
cd frontend-nextjs
npm test -- --testPathPattern="\.a11y\.test\.tsx$"
```

**Run specific accessibility test file:**
```bash
npm test -- Button.a11y.test.tsx
```

**Run with verbose output:**
```bash
npm test -- --testPathPattern="\.a11y\.test\.tsx$" --verbose
```

**Run with coverage:**
```bash
npm test -- --testPathPattern="\.a11y\.test\.tsx$" --coverage
```

## Manual Testing Checklist

Automated tests catch ~70% of issues. Manual testing is required for:

### Screen Reader Testing

**Tools:**
- Windows: NVDA (free), JAWS (paid)
- macOS: VoiceOver (built-in)
- Linux: Orca (built-in)

**Test scenarios:**
1. Navigate page with Tab key
2. Navigate by headings (H key in NVDA)
3. Navigate by landmarks (1-6 keys in NVDA)
4. List all links (Lists > Links in NVDA)
5. List all buttons (Lists > Buttons in NVDA)
6. Verify landmark regions (banner, navigation, main, contentinfo)

### Keyboard-Only Navigation

**Test scenarios:**
1. Navigate entire page with Tab key
2. Activate all interactive elements with Enter/Space
3. Escape modals and dropdowns with Escape key
4. Navigate select dropdowns with arrow keys
5. Verify visible focus indicators on all focusable elements
6. Verify logical tab order (left-to-right, top-to-bottom)

### Color Contrast Verification

**Tools:**
- WebAIM Contrast Checker: https://webaim.org/resources/contrastchecker/
- axe DevTools browser extension
- Chrome DevTools Color Picker (shows contrast ratio)

**WCAG 2.1 AA Requirements:**
- Normal text (< 18pt): 4.5:1 contrast ratio
- Large text (≥ 18pt or ≥ 14pt bold): 3:1 contrast ratio
- UI components and graphical objects: 3:1 contrast ratio

**Test scenarios:**
1. Check all text against background
2. Check form field borders
3. Check focus indicators
4. Check disabled state text
5. Check error messages

### Focus Visible Testing

**Test scenarios:**
1. Tab through page and verify visible focus ring
2. Verify focus ring doesn't get hidden by other elements
3. Verify focus ring is visible on all backgrounds
4. Verify custom focus styles meet 3:1 contrast requirement

## Resources

### WCAG Guidelines
- [WCAG 2.1 AA Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [WCAG 2.1 Checklist](https://www.w3.org/WAI/wcag21/checklist/)
- [WCAG 2.1 Understanding](https://www.w3.org/WAI/WCAG21/Understanding/)

### Accessibility Tools
- [axe DevTools Extension](https://www.deque.com/axe/devtools/) - Browser extension for accessibility testing
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/) - Color contrast verification
- [WAVE Browser Extension](https://wave.webaim.org/) - Visual accessibility evaluation
- [Lighthouse Accessibility Audit](https://developers.google.com/web/tools/lighthouse) - Chrome DevTools integration

### Screen Readers
- [NVDA (Windows)](https://www.nvaccess.org/) - Free, open source
- [JAWS (Windows)](https://www.freedomscientific.com/products/software/jaws/) - Paid
- [VoiceOver (macOS)](https://www.apple.com/accessibility/voiceover/) - Built-in
- [Orca (Linux)](https://wiki.gnome.org/Projects/Orca) - Built-in

### Testing Libraries
- [jest-axe GitHub](https://github.com/nickcolley/jest-axe) - Jest integration for axe-core
- [React Testing Library](https://testing-library.com/react) - Component testing utilities
- [@testing-library/user-event](https://testing-library.com/docs/user-event/intro) - Realistic user interaction simulation

### Atom-Specific Resources
- `frontend-nextjs/tests/accessibility-config.ts` - jest-axe configuration
- `frontend-nextjs/tests/setup.ts` - Global test setup with toHaveNoViolations() matcher
- `frontend-nextjs/.github/workflows/frontend-accessibility.yml` - CI/CD workflow
- Phase 132 plans - Accessibility testing implementation details

## Summary

Automated accessibility testing with jest-axe ensures WCAG 2.1 AA compliance for keyboard navigation, screen reader compatibility, and ARIA attributes. Follow the testing patterns in this guide, use the CI/CD integration, and supplement with manual testing for color contrast and screen reader navigation.

**Key Takeaways:**
- Every component needs at least one accessibility test
- Icon-only buttons must have `aria-label`
- Use `baseElement` for React Portal components
- Use `userEvent.keyboard()` for realistic keyboard testing
- Document JSDOM limitations (color contrast) in test comments
- Manual testing required for ~30% of issues (color, screen readers, usability)
