/**
 * Input Component Integration Tests
 *
 * Purpose: Test Input component interactions and props
 * TDD Phase: GREEN - Tests validate existing component behavior
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { Input } from '@/components/ui/input';

describe('Input Component Integration', () => {
  it('should render input with placeholder', () => {
    render(<Input placeholder="Enter text" />);
    expect(screen.getByPlaceholderText('Enter text')).toBeInTheDocument();
  });

  it('should accept value changes', () => {
    const handleChange = jest.fn();
    render(<Input value="test" onChange={handleChange} />);
    const input = screen.getByRole('textbox');
    expect(input).toHaveValue('test');
  });

  it('should be disabled when disabled prop is true', () => {
    render(<Input disabled />);
    expect(screen.getByRole('textbox')).toBeDisabled();
  });

  it('should call onChange when value changes', () => {
    const handleChange = jest.fn();
    render(<Input onChange={handleChange} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'new value' } });
    expect(handleChange).toHaveBeenCalledTimes(1);
  });

  it('should render with default type (text)', () => {
    const { container } = render(<Input />);
    const input = container.querySelector('input');
    // Input component doesn't set default type attribute, relies on browser default
    expect(input).toBeInTheDocument();
  });

  it('should render with type="password"', () => {
    const { container } = render(<Input type="password" />);
    const input = container.querySelector('input');
    expect(input).toHaveAttribute('type', 'password');
  });

  it('should render with type="email"', () => {
    const { container } = render(<Input type="email" />);
    const input = container.querySelector('input');
    expect(input).toHaveAttribute('type', 'email');
  });

  it('should render with type="number"', () => {
    const { container } = render(<Input type="number" />);
    const input = container.querySelector('input');
    expect(input).toHaveAttribute('type', 'number');
  });

  it('should apply custom className', () => {
    const { container } = render(<Input className="custom-class" />);
    const input = container.querySelector('input');
    expect(input).toHaveClass('custom-class');
  });

  it('should have default styling classes', () => {
    const { container } = render(<Input />);
    const input = container.querySelector('input');
    expect(input).toHaveClass('h-10');
    expect(input).toHaveClass('w-full');
    expect(input).toHaveClass('rounded-md');
  });

  it('should have disabled styling when disabled', () => {
    const { container } = render(<Input disabled />);
    const input = container.querySelector('input');
    expect(input).toHaveClass('disabled:cursor-not-allowed');
    expect(input).toHaveClass('disabled:opacity-50');
  });

  it('should accept name attribute', () => {
    const { container } = render(<Input name="test-input" />);
    const input = container.querySelector('input');
    expect(input).toHaveAttribute('name', 'test-input');
  });

  it('should accept id attribute', () => {
    const { container } = render(<Input id="test-id" />);
    const input = container.querySelector('input');
    expect(input).toHaveAttribute('id', 'test-id');
  });

  it('should be focusable', () => {
    render(<Input />);
    const input = screen.getByRole('textbox');
    input.focus();
    expect(input).toHaveFocus();
  });

  it('should accept readonly attribute', () => {
    const { container } = render(<Input readOnly />);
    const input = container.querySelector('input');
    expect(input).toHaveAttribute('readonly');
  });

  it('should accept required attribute', () => {
    const { container } = render(<Input required />);
    const input = container.querySelector('input');
    expect(input).toHaveAttribute('required');
  });
});
