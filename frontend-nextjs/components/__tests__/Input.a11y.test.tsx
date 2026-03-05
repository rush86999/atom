/**
 * Input Component Accessibility Tests
 *
 * Purpose: Test Input component for WCAG 2.1 AA compliance
 * Tests: axe violations, labels, ARIA attributes, keyboard accessibility
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from '../../tests/accessibility-config';
import { Input } from '@/components/ui/input';

describe('Input Accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(<Input placeholder="Enter text" />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible label', async () => {
    const { container } = render(
      <label htmlFor="test-input">
        Username
        <Input id="test-input" placeholder="Enter username" />
      </label>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();

    const input = screen.getByLabelText('Username');
    expect(input).toBeInTheDocument();
  });

  it('should have aria-label when visible label is absent', async () => {
    const { container } = render(
      <Input
        aria-label="Search query"
        placeholder="Search..."
      />
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();

    const input = screen.getByLabelText('Search query');
    expect(input).toHaveAttribute('aria-label', 'Search query');
  });

  it('should show error state with aria-invalid', async () => {
    const { container } = render(
      <label htmlFor="email-input">
        Email
        <Input
          id="email-input"
          type="email"
          aria-invalid="true"
          aria-describedby="email-error"
        />
        <span id="email-error" role="alert">
          Please enter a valid email address
        </span>
      </label>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();

    const input = screen.getByRole('textbox');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby', 'email-error');
  });

  it('should be keyboard accessible', async () => {
    render(<Input placeholder="Type here" />);

    const input = screen.getByPlaceholderText('Type here');

    // Tab to focus
    await userEvent.tab();
    expect(input).toHaveFocus();

    // Type text
    await userEvent.keyboard('Hello World');
    expect(input).toHaveValue('Hello World');
  });

  it('should not be accessible when disabled', () => {
    render(<Input disabled placeholder="Disabled" />);

    const input = screen.getByPlaceholderText('Disabled');
    expect(input).toBeDisabled();
  });

  it('should have visible focus indicator', () => {
    const { container } = render(<Input placeholder="Focus test" />);

    const input = container.querySelector('input');
    expect(input).toHaveClass('focus-visible:ring-2');
    expect(input).toHaveClass('focus-visible:ring-ring');
    expect(input).toHaveClass('focus-visible:ring-offset-2');
  });
});
