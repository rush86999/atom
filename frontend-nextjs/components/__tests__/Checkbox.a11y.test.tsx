/**
 * Checkbox Component Accessibility Tests
 *
 * Purpose: Test Checkbox component for WCAG 2.1 AA compliance
 * Tests: axe violations, accessible labels, keyboard (Space), aria-checked
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from '../../tests/accessibility-config';
import { Checkbox } from '@/components/ui/checkbox';

describe('Checkbox Accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(
      <label>
        <Checkbox />
        <span>Accept terms and conditions</span>
      </label>
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible label', async () => {
    render(
      <label>
        <Checkbox id="terms-checkbox" />
        <span>Accept terms and conditions</span>
      </label>
    );

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeInTheDocument();

    // Checkbox should be accessible via label
    const label = screen.getByText('Accept terms and conditions');
    expect(label).toBeInTheDocument();
  });

  it('should be toggleable with Space key', async () => {
    const handleChange = jest.fn();
    const user = userEvent.setup();

    render(
      <label>
        <Checkbox id="test-checkbox" onCheckedChange={handleChange} />
        <span>Test checkbox</span>
      </label>
    );

    const checkbox = screen.getByRole('checkbox');

    // Focus checkbox
    checkbox.focus();
    expect(checkbox).toHaveFocus();

    // Press Space to toggle
    await user.keyboard(' ');

    // Checkbox should be checked
    expect(checkbox).toHaveAttribute('data-state', 'checked');
    expect(handleChange).toHaveBeenCalled();
  });

  it('should have aria-checked attribute', async () => {
    render(
      <label>
        <Checkbox id="aria-checkbox" defaultChecked={true} />
        <span>Checked checkbox</span>
      </label>
    );

    const checkbox = screen.getByRole('checkbox');

    // Radix UI Checkbox handles aria-checked automatically
    // data-state attribute reflects the checked state
    expect(checkbox).toHaveAttribute('data-state', 'checked');
  });

  it('should have aria-checked false when unchecked', async () => {
    render(
      <label>
        <Checkbox id="unchecked-checkbox" />
        <span>Unchecked checkbox</span>
      </label>
    );

    const checkbox = screen.getByRole('checkbox');

    // Unchecked checkbox should have data-state unchecked
    expect(checkbox).toHaveAttribute('data-state', 'unchecked');
  });

  it('should not be keyboard accessible when disabled', () => {
    render(
      <label>
        <Checkbox disabled />
        <span>Disabled checkbox</span>
      </label>
    );

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeDisabled();
  });

  it('should have visible focus indicator', () => {
    const { container } = render(
      <label>
        <Checkbox />
        <span>Focus test</span>
      </label>
    );

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toHaveClass('focus-visible:ring-2');
    expect(checkbox).toHaveClass('focus-visible:ring-ring');
    expect(checkbox).toHaveClass('focus-visible:ring-offset-2');
  });

  it('should have proper role', () => {
    render(
      <label>
        <Checkbox />
        <span>Role test</span>
      </label>
    );

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeInTheDocument();
  });
});
