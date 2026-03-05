import { configureAxe } from 'jest-axe';

/**
 * Accessibility testing configuration for WCAG 2.1 AA compliance
 *
 * This configured axe instance is used across all accessibility tests
 * to ensure consistent WCAG 2.1 AA validation.
 *
 * Configuration details:
 * - region rule: Disabled for isolated component testing
 * - impactLevels: Only 'critical' and 'serious' violations are reported
 *
 * @see https://www.deque.com/axe/core-documentation/api-documentation/
 */
const axe = configureAxe({
  rules: {
    'region': { enabled: false } // Disable for isolated component testing
  },
  impactLevels: ['critical', 'serious'] // Only critical/serious violations
});

export default axe;
