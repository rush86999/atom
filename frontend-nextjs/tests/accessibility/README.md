# Accessibility Testing

Comprehensive WCAG 2.1 AA compliance testing for the Atom platform using jest-axe and React Testing Library.

## Overview

This suite verifies that the Atom platform is accessible to users with disabilities, meeting WCAG 2.1 Level AA standards for compliance and usability. Accessibility testing ensures:

- **Perceivable**: Information and UI components must be presentable in ways users can perceive
- **Operable**: UI components and navigation must be operable
- **Understandable**: Information and UI operation must be understandable
- **Robust**: Content must be robust enough to be interpreted by assistive technologies

## Prerequisites

```bash
# jest-axe is already installed in package.json
npm install --save-dev jest-axe @testing-library/react @testing-library/user-event
```

## Running Tests

### Run All Accessibility Tests

```bash
# From project root
cd frontend-nextjs
npm test -- tests/accessibility/

# With verbose output
npm test -- tests/accessibility/ --verbose

# With coverage
npm test -- tests/accessibility/ --coverage
```

### Run Specific Test Files

```bash
# WCAG compliance tests
npm test -- testAccessibilityCompliance.test.tsx

# Color contrast tests
npm test -- testColorContrast.test.tsx

# Keyboard navigation tests
npm test -- testKeyboardNavigation.test.tsx

# Workflow accessibility tests
npm test -- accessibility-workflows.test.tsx
```

### Run with Watch Mode

```bash
npm test -- tests/accessibility/ --watch
```

### Run in CI/CD

```bash
npm run test:ci -- tests/accessibility/
```

## Test Categories

### 1. WCAG 2.1 AA Compliance Tests (`testAccessibilityCompliance.test.tsx`)

Automated WCAG compliance checking using axe-core across all critical pages:

- **Login Page**: Form labels, submit buttons, error messages
- **Dashboard Page**: Navigation landmarks, card accessibility, color contrast
- **Agents Page**: Agent list ARIA labels, proper roles and structure
- **Canvas Page**: ARIA labels for visual content, live regions
- **Workflows Page**: Keyboard-accessible workflow builder
- **Forms**: Proper labels, error messages, instructions, validation
- **Modals**: Focus trap, aria-modal, proper roles and attributes
- **Navigation**: Landmark structure (banner, nav, main, contentinfo)

**Example:**

```tsx
import { axeCheckViolations, defaultAxeOptions } from './fixtures/axeFixtures';

it('should have no WCAG violations on login page', async () => {
  const { container } = render(<LoginPage />);
  await axeCheckViolations(container, 'Login Page', defaultAxeOptions);
});
```

### 2. Color Contrast Tests (`testColorContrast.test.tsx`)

Verify WCAG 2.1 AA contrast requirements:

- **Normal text** (< 18px or < 14px bold): **4.5:1** minimum
- **Large text** (>= 18px or >= 14px bold): **3.1** minimum
- **UI components**: **3:1** minimum
- **Focus indicators**: **3:1** against adjacent colors

**Tests include:**

- Login page: Text colors, form labels, buttons, error messages
- Dashboard page: Text, icons, links, cards
- Text variants: All Tailwind colors tested (gray, blue, red, green, yellow, purple)
- Interactive elements: Button states, hover/focus states, disabled states
- Dark mode: Sufficient contrast on dark backgrounds

**Example:**

```tsx
import { getContrastRatio, meetsWCAG_AA } from './testColorContrast';

const ratio = getContrastRatio('#333333', '#ffffff');
console.log(`Contrast ratio: ${ratio.toFixed(1)}:1`);
console.log(`Meets WCAG AA: ${meetsWCAG_AA(ratio, false)}`);
```

### 3. Keyboard Navigation Tests (`testKeyboardNavigation.test.tsx`)

Verify all functionality is available via keyboard:

- **Tab Order**: Logical visual flow (left-to-right, top-to-bottom)
- **Enter Key**: Form submission, button activation
- **Escape Key**: Close modals, dropdowns, exit fullscreen
- **Arrow Keys**: Navigate lists, tabs, grids
- **Keyboard Shortcuts**: Cmd+K (palette), / (search), ? (help)
- **Focus Management**: Focus trap in modals, focus restoration, error focusing
- **Focus Indicators**: Visible on all interactive elements

**Example:**

```tsx
import userEvent from '@testing-library/user-event';

it('should navigate login form in logical tab order', async () => {
  render(<LoginForm />);
  const user = userEvent.setup();

  await user.tab(); // Focus email input
  await user.tab(); // Focus password input
  await user.tab(); // Focus submit button
  await user.keyboard('{Enter}'); // Submit form
});
```

### 4. Workflow Accessibility Tests (`accessibility-workflows.test.tsx`)

Real user workflow testing:

- Keyboard navigation through canvas
- Screen reader announcements for form errors
- Modal focus trapping and restoration
- Dynamic content announcements
- Custom interactive elements
- Image accessibility (alt text)
- Focus indicators

## Fixtures and Helpers

### axeFixtures.tsx

Core fixtures for accessibility testing:

```tsx
import {
  axeRender,
  axeRun,
  axeCheckViolations,
  axeCheckCritical,
  authenticatedAxeRender,
  defaultAxeOptions,
} from './fixtures/axeFixtures';
```

#### `axeRender(ui, options)`

Render a component with axe-core ready:

```tsx
const { container } = axeRender(<MyComponent />);
const results = await axe(container);
expect(results).toHaveNoViolations();
```

#### `axeRun(container, options)`

Run axe-core and return violations:

```tsx
const violations = await axeRun(container);
if (violations.length > 0) {
  console.log('Found violations:', violations);
}
```

#### `axeCheckViolations(container, pageName, options)`

Assert no violations with detailed error reporting:

```tsx
await axeCheckViolations(container, 'MyComponent');
// ✅ No accessibility violations on MyComponent

// Or with custom options
await axeCheckViolations(container, 'MyPage', {
  rules: { 'color-contrast': { enabled: true } }
});
```

#### `axeCheckCritical(container, pageName)`

Check only critical and serious violations (allows minor violations):

```tsx
await axeCheckCritical(container, 'MyComponent');
// Only fails on critical/serious violations
```

#### `authenticatedAxeRender(ui, authToken, options)`

Render authenticated pages with mocked auth:

```tsx
const { container } = await authenticatedAxeRender(<DashboardPage />);
await axeCheckViolations(container, 'Dashboard');
```

## WCAG 2.1 AA Standards

### Perceivable

1. **Text Alternatives**: Alt text for images, aria-labels for icons
2. **Captions**: Captions for video content
3. **Adaptable**: Content can be presented in different ways
4. **Distinguishable**: Easy to see and hear (color contrast >= 4.5:1)

### Operable

1. **Keyboard Accessible**: All functionality via keyboard (2.1.1)
2. **No Keyboard Trap**: Can navigate away from any focus (2.1.2)
3. **Timing Adjustable**: Sufficient time to read and interact
4. **Seizures**: No flashing content (> 3 flashes per second)
5. **Navigable**: Easy to navigate and find content
6. **Input Modalities**: Functionality beyond keyboard (speech, touch)

### Understandable

1. **Readable**: Text is readable and understandable
2. **Predictable**: Web pages operate in predictable ways
3. **Input Assistance**: Help users avoid and correct mistakes

### Robust

1. **Compatible**: Compatible with current and future assistive technologies

## Common Violations and Fixes

### 1. Missing Alt Text

**Violation:**

```
image-alt: Ensures <img> elements have alternate text
Impact: serious
```

**Fix:**

```tsx
// ❌ Missing alt text
<img src="/logo.png" />

// ✅ With alt text
<img src="/logo.png" alt="Company Logo" />

// ✅ Decorative image
<img src="/divider.png" alt="" role="presentation" />
```

### 2. Color Contrast Issues

**Violation:**

```
color-contrast: Ensures contrast ratio meets WCAG 2 AA (4.5:1 for text)
Impact: serious
```

**Fix:**

```tsx
// ❌ Low contrast (gray-400 on white = 3.0:1)
<p style={{ color: '#9ca3af' }}>This text</p>

// ✅ Sufficient contrast (gray-600 on white = 7.1:1)
<p style={{ color: '#4b5563' }}>This text</p>
```

### 3. Missing Form Labels

**Violation:**

```
label: Ensures form elements have associated labels
Impact: critical
```

**Fix:**

```tsx
// ❌ Missing label
<input type="email" placeholder="Email" />

// ✅ With label
<label htmlFor="email">Email</label>
<input id="email" type="email" />

// ✅ With aria-label
<input type="email" aria-label="Email address" />
```

### 4. Keyboard Trap

**Violation:**

```
focus-trap: Ensures keyboard focus is not trapped
Impact: serious
```

**Fix:**

```tsx
// Use focus trap in modals
import { FocusTrap } from '@headlessui/react';

<FocusTrap>
  <dialog>
    <button>Cancel</button>
    <button>Confirm</button>
  </dialog>
</FocusTrap>
```

### 5. Missing ARIA Attributes

**Violation:**

```
aria: Ensures ARIA attributes are valid and used correctly
Impact: serious
```

**Fix:**

```tsx
// ❌ Missing aria-label
<button><Icon name="settings" /></button>

// ✅ With aria-label
<button aria-label="Open settings">
  <Icon name="settings" />
</button>

// ✅ Visually hidden label
<button>
  <span className="sr-only">Open settings</span>
  <Icon name="settings" />
</button>
```

## Troubleshooting

### Test Fails with "No violations found"

If tests pass locally but fail in CI, check:

1. **Browser differences**: Chrome vs Firefox vs Safari render differently
2. **Font loading**: Custom fonts may affect contrast ratios
3. **Environment**: CI may run in headless mode without proper styling

```tsx
// Wait for fonts to load
beforeEach(async () => {
  await document.fonts.ready;
});
```

### Tests timeout on slow networks

Increase timeout for network-heavy tests:

```tsx
it('should load accessible dashboard', async () => {
  // Increase timeout to 30s
  jest.setTimeout(30000);

  const { container } = render(<DashboardPage />);
  await axeCheckViolations(container, 'Dashboard');
}, 30000);
```

### Axe-core not injected

Ensure jest-axe is properly configured:

```tsx
// tests/setup.ts
import { toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);
```

### False positives from axe-core

Some violations may be false positives. Exclude rules selectively:

```tsx
await axeCheckViolations(container, 'Page', {
  rules: {
    'color-contrast': { enabled: false }, // Temporarily disable
  },
});
```

**Do not ignore violations without justification!** Each violation represents a real accessibility barrier for users.

## Resources

### WCAG 2.1 Quick Reference

https://www.w3.org/WAI/WCAG21/quickref/

### axe-core Documentation

https://www.deque.com/axe/

### WebAIM Contrast Checker

https://webaim.org/resources/contrastchecker/

### jest-axe Repository

https://github.com/nickcolley/jest-axe

### React Testing Library

https://testing-library.com/docs/react-testing-library/intro/

### A11y Project Checklist

https://www.a11yproject.com/checklist/

## CI/CD Integration

Accessibility tests run automatically in CI/CD pipeline:

```yaml
# .github/workflows/test.yml
- name: Run accessibility tests
  run: |
    cd frontend-nextjs
    npm test -- tests/accessibility/ --ci --coverage
```

Tests block merging if critical or serious violations are found.

## Example Violation Output

```
❌ Accessibility violations found on Login Page:

  1. color-contrast: Ensures the contrast between foreground and background colors meets WCAG 2 AA
     Impact: serious
     Help: https://dequeuniversity.com/rules/axe/4.8/color-contrast?application=axeAPI
     Nodes: 2 affected
       - <p style="color: #9ca3af">Forgot password?</p>
       - <a href="#" style="color: #60a5fa">Learn more</a>

  2. label: Ensures form elements have associated labels
     Impact: critical
     Help: https://dequeuniversity.com/rules/axe/4.8/label?application=axeAPI
     Nodes: 1 affected
       - <input type="text" placeholder="Username" />

FAIL Found 3 accessibility violation(s) on Login Page
```

## Best Practices

1. **Test Early and Often**: Write accessibility tests alongside component development
2. **Test Real User Flows**: Test complete workflows, not just individual components
3. **Use Semantic HTML**: Proper use of HTML elements reduces need for ARIA
4. **Test with Screen Readers**: Automated tests don't catch all issues
5. **Test with Keyboard**: Try navigating your app with only keyboard
6. **Involve Users with Disabilities**: Nothing replaces real user testing
7. **Monitor Violations in Production**: Use tools like axe DevTools in production

## Contributing

When adding new components:

1. Write accessibility tests alongside unit tests
2. Test keyboard navigation (Tab, Enter, Escape, Arrow keys)
3. Verify color contrast (4.5:1 for normal text, 3:1 for large text)
4. Add proper ARIA labels and roles
5. Test with screen reader (NVDA, JAWS, VoiceOver)

## License

MIT

## Contact

For accessibility questions or concerns, contact the team at:
- GitHub Issues: https://github.com/your-org/atom/issues
- Accessibility Slack Channel: #accessibility
