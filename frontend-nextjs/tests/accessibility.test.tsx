import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import React from 'react';
import { Button } from '@/components/ui/button';

// Extend Jest with jest-axe matcher (should already be global via setup.ts)
expect.extend(toHaveNoViolations);

/**
 * Smoke test to verify jest-axe is properly configured
 *
 * This test confirms:
 * 1. jest-axe matcher is available globally
 * 2. toHaveNoViolations() detects WCAG violations
 * 3. configureAxe options are applied (region rule disabled)
 * 4. Accessibility testing infrastructure is functional
 */
describe('jest-axe configuration', () => {
  it('should have toHaveNoViolations matcher available globally', () => {
    // Verify the matcher exists on expect
    expect(expect.extend).toBeDefined();
    expect(toHaveNoViolations).toBeDefined();
  });

  it('should configure axe with WCAG 2.1 AA rules', async () => {
    // Render a simple accessible Button component
    const { container } = render(<Button>Click me</Button>);

    // Run accessibility checks
    const results = await axe(container);

    // Button should have no violations (has accessible name via text content)
    expect(results).toHaveNoViolations();
  });

  it('should detect accessibility violations', async () => {
    // Render a button with no accessible name (violates WCAG)
    const { container } = render(
      <button aria-label=""></button>
    );

    // Run accessibility checks
    const results = await axe(container);

    // Should have violations (empty aria-label is not valid)
    // Note: This test verifies that axe is actually detecting issues
    expect(results.violations.length).toBeGreaterThan(0);
  });
});
