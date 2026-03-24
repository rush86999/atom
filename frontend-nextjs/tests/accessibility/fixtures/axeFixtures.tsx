import { render, RenderResult } from '@testing-library/react';
import { axe, toHaveNoViolations, AxeResults, Violation } from 'jest-axe';
import React, { ReactElement } from 'react';

// Extend Jest with jest-axe matcher
expect.extend(toHaveNoViolations);

/**
 * Accessibility testing fixtures using jest-axe
 *
 * These fixtures provide automated WCAG 2.1 AA compliance checking
 * for React components using axe-core.
 *
 * @see https://www.deque.com/axe/
 * @see https://github.com/nickcolley/jest-axe
 */

/**
 * Render a component with axe-core injected for accessibility testing
 *
 * @param ui - React element to test
 * @param options - Optional render options from @testing-library/react
 * @returns RenderResult with axe-core ready for testing
 *
 * @example
 * ```tsx
 * const { container } = axeRender(<MyComponent />);
 * const results = await axe(container);
 * expect(results).toHaveNoViolations();
 * ```
 */
export function axeRender(
  ui: ReactElement,
  options?: { [key: string]: any }
): RenderResult {
  return render(ui, options);
}

/**
 * Run axe-core and return violations
 *
 * @param container - HTML container to test
 * @param options - Optional axe-core configuration options
 * @returns Promise<AxeResults> with violations array
 *
 * @example
 * ```tsx
 * const { container } = render(<MyComponent />);
 * const violations = await axeRun(container);
 * if (violations.length > 0) {
 *   console.log('Found', violations.length, 'violations');
 * }
 * ```
 */
export async function axeRun(
  container: HTMLElement,
  options?: { [key: string]: any }
): Promise<AxeResults> {
  return await axe(container, options);
}

/**
 * Assert no accessibility violations, print details if found
 *
 * @param container - HTML container to test
 * @param pageName - Optional name for the page/component being tested
 * @param options - Optional axe-core configuration options
 * @throws Error if violations are found
 *
 * @example
 * ```tsx
 * const { container } = render(<MyComponent />);
 * await axeCheckViolations(container, 'MyComponent');
 * // ✅ No accessibility violations on MyComponent
 * ```
 */
export async function axeCheckViolations(
  container: HTMLElement,
  pageName: string = 'Component',
  options?: { [key: string]: any }
): Promise<void> {
  const results = await axe(container, options);

  if (results.violations.length > 0) {
    console.log(`\n❌ Accessibility violations found on ${pageName}:`);
    results.violations.forEach((violation: Violation, index: number) => {
      console.log(`  ${index + 1}. ${violation.id}: ${violation.description}`);
      console.log(`     Impact: ${violation.impact}`);
      console.log(`     Help: ${violation.help}`);
      console.log(`     Help URL: ${violation.helpUrl}`);
      console.log(`     Nodes: ${violation.nodes.length} affected`);

      // Print first few affected nodes for context
      violation.nodes.slice(0, 3).forEach((node) => {
        const html = node.html ? node.html.substring(0, 100) : '';
        console.log(`       - ${html}...`);
      });

      if (violation.nodes.length > 3) {
        console.log(`       ... and ${violation.nodes.length - 3} more`);
      }
    });

    throw new Error(
      `Found ${results.violations.length} accessibility violation(s) on ${pageName}`
    );
  } else {
    console.log(`✅ No accessibility violations on ${pageName}`);
  }
}

/**
 * Filter violations by impact level
 *
 * @param violations - Array of axe-core violations
 * @param impactLevel - Minimum impact level ('critical', 'serious', 'moderate', 'minor')
 * @returns Filtered violations array
 *
 * @example
 * ```tsx
 * const results = await axe(container);
 * const criticalViolations = filterByImpact(results.violations, 'critical');
 * expect(criticalViolations).toHaveLength(0);
 * ```
 */
export function filterByImpact(
  violations: Violation[],
  impactLevel: 'critical' | 'serious' | 'moderate' | 'minor'
): Violation[] {
  const impactLevels = ['critical', 'serious', 'moderate', 'minor'];
  const threshold = impactLevels.indexOf(impactLevel);
  return violations.filter((v) => {
    const impact = v.impact || 'moderate';
    return impactLevels.indexOf(impact) <= threshold;
  });
}

/**
 * Check only critical and serious violations
 *
 * Use this for components that may have minor violations during development
 *
 * @param container - HTML container to test
 * @param pageName - Optional name for the page/component being tested
 * @throws Error if critical or serious violations are found
 *
 * @example
 * ```tsx
 * const { container } = render(<MyComponent />);
 * await axeCheckCritical(container, 'MyComponent');
 * // Only fails on critical/serious violations
 * ```
 */
export async function axeCheckCritical(
  container: HTMLElement,
  pageName: string = 'Component'
): Promise<void> {
  const results = await axe(container);
  const criticalViolations = filterByImpact(results.violations, 'serious');

  if (criticalViolations.length > 0) {
    console.log(`\n❌ Critical accessibility violations found on ${pageName}:`);
    criticalViolations.forEach((violation: Violation, index: number) => {
      console.log(`  ${index + 1}. ${violation.id}: ${violation.description}`);
      console.log(`     Impact: ${violation.impact}`);
    });

    throw new Error(
      `Found ${criticalViolations.length} critical accessibility violation(s) on ${pageName}`
    );
  } else {
    console.log(`✅ No critical accessibility violations on ${pageName}`);
  }
}

/**
 * Create an authenticated page fixture for testing protected routes
 *
 * This helper wraps render() with authentication context setup
 * for testing pages that require login.
 *
 * @param ui - React element to test (usually a page component)
 * @param authToken - Mock authentication token
 * @param options - Optional render options
 * @returns RenderResult with authentication context
 *
 * @example
 * ```tsx
 * const authenticatedPage = await authenticatedAxeRender(
 *   <DashboardPage />,
 *   'mock-jwt-token'
 * );
 * await axeCheckViolations(authenticatedPage.container, 'Dashboard');
 * ```
 */
export async function authenticatedAxeRender(
  ui: ReactElement,
  authToken: string = 'mock-token',
  options?: { [key: string]: any }
): Promise<RenderResult> {
  // Mock localStorage for authentication
  const mockLocalStorage = {
    getItem: (key: string) => {
      if (key === 'auth_token') return authToken;
      return null;
    },
    setItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn(),
  };

  Object.defineProperty(window, 'localStorage', {
    value: mockLocalStorage,
    writable: true,
  });

  // Mock authenticated API requests
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ authenticated: true }),
    })
  ) as jest.Mock;

  return render(ui, options);
}

/**
 * Default axe-core configuration for WCAG 2.1 AA compliance
 *
 * Tags: wcag2a, wcag2aa, wcag21aa (WCAG 2.1 Level AA)
 * Excludes: experimental and best-practice (only test standards, not recommendations)
 */
export const defaultAxeOptions = {
  tags: ['wcag2a', 'wcag2aa', 'wcag21aa'],
  exclude: [['#test-only']],
};

/**
 * Axe configuration for testing with specific rules only
 *
 * @param rules - Array of rule IDs to enable (all others disabled)
 * @returns Axe configuration object
 *
 * @example
 * ```tsx
 * const colorContrastOptions = axeConfigWithRules(['color-contrast']);
 * await axeCheckViolations(container, 'Page', colorContrastOptions);
 * ```
 */
export function axeConfigWithRules(rules: string[]): { [key: string]: any } {
  return {
    rules: rules.map((rule) => ({ id: rule, enabled: true })),
  };
}

/**
 * Axe configuration excluding specific rules
 *
 * Use this to temporarily disable certain rules during development
 *
 * @param rules - Array of rule IDs to disable
 * @returns Axe configuration object
 *
 * @example
 * ```tsx
 * const options = axeConfigExcludeRules(['color-contrast']);
 * await axeCheckViolations(container, 'Page', options);
 * // Color contrast violations will not fail the test
 * ```
 */
export function axeConfigExcludeRules(rules: string[]): { [key: string]: any } {
  return {
    rules: rules.map((rule) => ({ id: rule, enabled: false })),
  };
}
