/**
 * Select Component Accessibility Tests
 *
 * Purpose: Test Select component for WCAG 2.1 AA compliance
 * Tests: axe violations, aria-expanded, keyboard navigation support
 */

import { render, screen } from '@testing-library/react';
import axe from '../../tests/accessibility-config';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

describe('Select Accessibility', () => {
  it('should have no accessibility violations when closed', async () => {
    const { container } = render(
      <Select>
        <SelectTrigger aria-label="Select an option">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="option1">Option 1</SelectItem>
          <SelectItem value="option2">Option 2</SelectItem>
          <SelectItem value="option3">Option 3</SelectItem>
        </SelectContent>
      </Select>
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have aria-expanded when closed', async () => {
    render(
      <Select>
        <SelectTrigger aria-label="Select an option">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="option1">Option 1</SelectItem>
        </SelectContent>
      </Select>
    );

    const trigger = screen.getByRole('combobox');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('should have proper role and attributes', async () => {
    const { container } = render(
      <Select>
        <SelectTrigger aria-label="Select an option">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="option1">Option 1</SelectItem>
          <SelectItem value="option2">Option 2</SelectItem>
          <SelectItem value="option3">Option 3</SelectItem>
        </SelectContent>
      </Select>
    );

    const trigger = screen.getByRole('combobox');
    expect(trigger).toHaveAttribute('role', 'combobox');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible name via aria-label', async () => {
    const { container } = render(
      <Select>
        <SelectTrigger aria-label="Choose your preference">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="option1">Option 1</SelectItem>
        </SelectContent>
      </Select>
    );

    const trigger = screen.getByRole('combobox');
    expect(trigger).toHaveAttribute('aria-label', 'Choose your preference');

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have visible focus indicator', () => {
    const { container } = render(
      <Select>
        <SelectTrigger aria-label="Select an option">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="option1">Option 1</SelectItem>
        </SelectContent>
      </Select>
    );

    const trigger = container.querySelector('button');
    expect(trigger).toHaveClass('focus:ring-2');
    expect(trigger).toHaveClass('focus:ring-ring');
    expect(trigger).toHaveClass('focus:ring-offset-2');
  });

  it('should support keyboard interaction structure', () => {
    render(
      <Select>
        <SelectTrigger aria-label="Select an option">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="option1">Option 1</SelectItem>
        </SelectContent>
      </Select>
    );

    const trigger = screen.getByRole('combobox');

    // Radix UI Select handles Enter/Space/Escape automatically
    // This test verifies the component has correct ARIA structure
    expect(trigger).toHaveAttribute('role', 'combobox');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });
});
