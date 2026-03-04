/**
 * Button Component Accessibility Tests
 *
 * Purpose: Test Button component for WCAG 2.1 AA compliance
 * Tests: axe violations, keyboard navigation, ARIA attributes, focus indicators
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from '../../tests/accessibility-config';
import { Button } from '@/components/ui/button';

describe('Button Accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(<Button>Click me</Button>);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible name for icon-only button', async () => {
    const { container } = render(
      <Button aria-label="Close dialog">
        <span aria-hidden="true">×</span>
      </Button>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-label', 'Close dialog');
  });

  it('should be keyboard accessible', async () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Submit</Button>);

    const button = screen.getByRole('button');

    // Tab to focus
    await userEvent.tab();
    expect(button).toHaveFocus();

    // Activate with Enter key
    await userEvent.keyboard('{Enter}');
    expect(handleClick).toHaveBeenCalledTimes(1);

    // Activate with Space key
    await userEvent.keyboard(' ');
    expect(handleClick).toHaveBeenCalledTimes(2);
  });

  it('should not be keyboard accessible when disabled', async () => {
    render(<Button disabled>Disabled</Button>);

    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('should have visible focus indicator', () => {
    const { container } = render(<Button>Focus test</Button>);

    const button = container.querySelector('button');
    expect(button).toHaveClass('focus-visible:ring-2');
    expect(button).toHaveClass('focus-visible:ring-ring');
    expect(button).toHaveClass('focus-visible:ring-offset-2');
  });

  it('should have visible focus indicator for icon buttons', () => {
    const { container } = render(<Button size="icon">Icon</Button>);

    const button = container.querySelector('button');
    expect(button).toHaveClass('focus-visible:ring-2');
  });
});
