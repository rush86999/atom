/**
 * PasswordStrengthIndicator tests
 * (components/auth/PasswordStrengthIndicator.tsx)
 *
 * Covers: null render for empty password, strong/weak/very-weak states,
 * requirements checklist met/unmet icons, requirements hidden via
 * showRequirements=false, and filtered feedback messages.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { PasswordStrengthIndicator } from '@/components/auth/PasswordStrengthIndicator';

// Scores map to labels: 0 Very Weak, 1 Weak, 2 Fair, 3 Strong, 4 Very Strong
const strongPassword = 'Str0ng!PasswordExample2026'; // 20+, all requirements, no sequences

describe('PasswordStrengthIndicator', () => {
  it('renders nothing when the password is empty', () => {
    const { container } = render(<PasswordStrengthIndicator password="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders all met requirements and a strong label for a strong password', () => {
    render(<PasswordStrengthIndicator password={strongPassword} />);

    expect(screen.getByText('Password Strength:')).toBeInTheDocument();
    expect(
      screen.getByText(/^Very Strong$|^Strong$|^Fair$/)
    ).toBeInTheDocument();

    const requirements = [
      'At least 12 characters',
      'One uppercase letter',
      'One lowercase letter',
      'One number',
      'One special character',
    ];
    requirements.forEach((text) => {
      expect(screen.getByText(text)).toBeInTheDocument();
      expect(
        screen.getByText(text).closest('li')!.querySelector('svg.lucide-circle-check')
      ).toBeTruthy();
    });
  });

  it('shows unmet requirement icons and feedback for a weak password', () => {
    render(<PasswordStrengthIndicator password="weakpass" />);

    // score 0 -> Very Weak
    expect(screen.getByText('Very Weak')).toBeInTheDocument();

    // unmet: uppercase, number, special char, length
    const upper = screen.getByText('One uppercase letter').closest('li')!;
    expect(upper.querySelector('svg.lucide-circle-x')).toBeTruthy();
    expect(upper.querySelector('svg.lucide-circle-check')).toBeNull();

    // feedback lines are rendered as bullets
    expect(
      screen.getByText(/Password must be at least 12 characters long/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Include at least one uppercase letter/)
    ).toBeInTheDocument();
  });

  it('warns about repeated and sequential characters', () => {
    // invalid (short) and contains the sequential run "abc"
    render(<PasswordStrengthIndicator password="Abc123!" />);

    expect(
      screen.getByText(/Avoid sequential characters/)
    ).toBeInTheDocument();
  });

  it('hides the requirements checklist when showRequirements is false', () => {
    render(
      <PasswordStrengthIndicator
        password="weakpass"
        showRequirements={false}
      />
    );

    expect(screen.queryByText('Requirements:')).not.toBeInTheDocument();
    expect(
      screen.queryByText('At least 12 characters')
    ).not.toBeInTheDocument();
    // strength bar is still rendered
    expect(screen.getByText('Password Strength:')).toBeInTheDocument();
  });

  it('does not show feedback when the password is valid', () => {
    render(<PasswordStrengthIndicator password={strongPassword} />);

    // "Password meets all requirements" is filtered out of the feedback block
    expect(
      screen.queryByText(/meets all requirements/)
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/must be at least/i)).not.toBeInTheDocument();
  });
});
