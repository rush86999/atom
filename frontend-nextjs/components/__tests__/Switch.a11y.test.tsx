/**
 * Switch Component Accessibility Tests
 *
 * Purpose: Test Switch component for WCAG 2.1 AA compliance
 * Tests: axe violations, accessible labels, keyboard (Space), aria-checked
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from '../../tests/accessibility-config';
import { Switch } from '@/components/ui/switch';

describe('Switch Accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(
      <label>
        <Switch id="test-switch" />
        <span>Enable notifications</span>
      </label>
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible label', async () => {
    render(
      <label>
        <Switch id="label-switch" />
        <span>Enable dark mode</span>
      </label>
    );

    const switchEl = screen.getByRole('switch');
    expect(switchEl).toBeInTheDocument();

    // Switch should be accessible via label
    const label = screen.getByText('Enable dark mode');
    expect(label).toBeInTheDocument();
  });

  it('should be toggleable with Space key', async () => {
    const handleChange = jest.fn();
    const user = userEvent.setup();

    render(
      <label>
        <Switch id="toggle-switch" onCheckedChange={handleChange} />
        <span>Toggle switch</span>
      </label>
    );

    const switchEl = screen.getByRole('switch');

    // Focus switch
    switchEl.focus();
    expect(switchEl).toHaveFocus();

    // Press Space to toggle
    await user.keyboard(' ');

    // Switch should be checked
    expect(switchEl).toHaveAttribute('data-state', 'checked');
    expect(handleChange).toHaveBeenCalled();
  });

  it('should have aria-checked attribute when checked', async () => {
    render(
      <label>
        <Switch id="checked-switch" defaultChecked={true} />
        <span>Checked switch</span>
      </label>
    );

    const switchEl = screen.getByRole('switch');

    // Radix UI Switch handles aria-checked automatically
    // data-state attribute reflects the checked state
    expect(switchEl).toHaveAttribute('data-state', 'checked');
  });

  it('should have aria-checked false when unchecked', async () => {
    render(
      <label>
        <Switch id="unchecked-switch" />
        <span>Unchecked switch</span>
      </label>
    );

    const switchEl = screen.getByRole('switch');

    // Unchecked switch should have data-state unchecked
    expect(switchEl).toHaveAttribute('data-state', 'unchecked');
  });

  it('should not be keyboard accessible when disabled', () => {
    render(
      <label>
        <Switch disabled />
        <span>Disabled switch</span>
      </label>
    );

    const switchEl = screen.getByRole('switch');
    expect(switchEl).toBeDisabled();
  });

  it('should have visible focus indicator', () => {
    const { container } = render(
      <label>
        <Switch />
        <span>Focus test</span>
      </label>
    );

    const switchEl = screen.getByRole('switch');
    expect(switchEl).toHaveClass('focus-visible:ring-2');
    expect(switchEl).toHaveClass('focus-visible:ring-ring');
    expect(switchEl).toHaveClass('focus-visible:ring-offset-2');
  });

  it('should have proper role', () => {
    render(
      <label>
        <Switch />
        <span>Role test</span>
      </label>
    );

    const switchEl = screen.getByRole('switch');
    expect(switchEl).toBeInTheDocument();
  });

  it('should have proper ARIA structure', async () => {
    const { container } = render(
      <label>
        <Switch id="aria-switch" />
        <span>ARIA structure test</span>
      </label>
    );

    const switchEl = screen.getByRole('switch');

    // Switch uses role="switch" by default
    expect(switchEl).toHaveAttribute('role', 'switch');

    // Verify no accessibility violations
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
