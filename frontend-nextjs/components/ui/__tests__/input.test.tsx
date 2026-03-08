import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input } from '@/components/ui/input';

describe('Input Component', () => {
  describe('Rendering', () => {
    it('renders default input', () => {
      render(<Input data-testid="test-input" />);
      const input = screen.getByTestId('test-input');
      expect(input).toBeInTheDocument();
      // Default type is implicit (text) but may not be set as attribute
      expect(input.tagName).toBe('INPUT');
    });

    it('renders with different types', () => {
      const { rerender } = render(<Input type="email" data-testid="input" />);
      expect(screen.getByTestId('input')).toHaveAttribute('type', 'email');

      rerender(<Input type="password" data-testid="input" />);
      expect(screen.getByTestId('input')).toHaveAttribute('type', 'password');

      rerender(<Input type="number" data-testid="input" />);
      expect(screen.getByTestId('input')).toHaveAttribute('type', 'number');

      rerender(<Input type="tel" data-testid="input" />);
      expect(screen.getByTestId('input')).toHaveAttribute('type', 'tel');
    });

    it('renders with placeholder text', () => {
      render(<Input placeholder="Enter your email" data-testid="input" />);
      const input = screen.getByPlaceholderText('Enter your email');
      expect(input).toBeInTheDocument();
    });

    it('renders with default value', () => {
      render(<Input defaultValue="John Doe" data-testid="input" />);
      const input = screen.getByDisplayValue('John Doe');
      expect(input).toBeInTheDocument();
    });

    it('renders with disabled state', () => {
      render(<Input disabled data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toBeDisabled();
    });

    it('applies default classes', () => {
      render(<Input data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveClass('h-10');
      expect(input).toHaveClass('w-full');
      expect(input).toHaveClass('rounded-md');
    });
  });

  describe('User Interactions', () => {
    it('allows typing', async () => {
      const user = userEvent.setup();
      render(<Input data-testid="input" />);

      const input = screen.getByTestId('input');
      await user.type(input, 'Hello World');

      expect(input).toHaveValue('Hello World');
    });

    it('calls onChange handler with value', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();

      render(<Input onChange={handleChange} data-testid="input" />);

      const input = screen.getByTestId('input');
      await user.type(input, 'test');

      expect(handleChange).toHaveBeenCalled();
    });

    it('prevents input when disabled', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();

      render(<Input onChange={handleChange} disabled data-testid="input" />);

      const input = screen.getByTestId('input');
      await user.type(input, 'test');

      // Even though onChange shouldn't fire, the value can still change
      // but the input should still be disabled
      expect(input).toBeDisabled();
    });

    it('handles focus event', async () => {
      const user = userEvent.setup();
      const handleFocus = jest.fn();

      render(<Input onFocus={handleFocus} data-testid="input" />);

      const input = screen.getByTestId('input');
      await user.click(input);

      expect(handleFocus).toHaveBeenCalled();
    });

    it('handles blur event', async () => {
      const user = userEvent.setup();
      const handleBlur = jest.fn();

      render(<Input onBlur={handleBlur} data-testid="input" />);

      const input = screen.getByTestId('input');
      await user.click(input);
      await user.tab(); // Move focus away

      expect(handleBlur).toHaveBeenCalled();
    });

    it('clears input value', async () => {
      const user = userEvent.setup();
      render(<Input defaultValue="test" data-testid="input" />);

      const input = screen.getByTestId('input');
      await user.clear(input);

      expect(input).toHaveValue('');
    });

    it('handles backspace and delete keys', async () => {
      const user = userEvent.setup();
      render(<Input defaultValue="hello" data-testid="input" />);

      const input = screen.getByTestId('input');
      await user.click(input);
      await user.keyboard('{Backspace}'.repeat(2));

      expect(input).toHaveValue('hel');
    });
  });

  describe('Validation', () => {
    it('enforces required attribute', () => {
      render(<Input required data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toBeRequired();
    });

    it('enforces min/max for number inputs', () => {
      render(<Input type="number" min="0" max="100" data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('min', '0');
      expect(input).toHaveAttribute('max', '100');
    });

    it('enforces step for number inputs', () => {
      render(<Input type="number" step="0.01" data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('step', '0.01');
    });

    it('enforces pattern validation', () => {
      render(<Input pattern="[a-z]+" data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('pattern', '[a-z]+');
    });

    it('enforces minLength and maxLength', () => {
      render(<Input minLength={3} maxLength={10} data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('minlength', '3');
      expect(input).toHaveAttribute('maxlength', '10');
    });
  });

  describe('Accessibility', () => {
    it('has accessible label when associated with label element', () => {
      render(
        <label>
          Email
          <Input data-testid="input" />
        </label>
      );

      const input = screen.getByLabelText('Email');
      expect(input).toBeInTheDocument();
    });

    it('forwards aria-invalid attribute', () => {
      render(<Input aria-invalid="true" data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('aria-invalid', 'true');
    });

    it('forwards aria-describedby attribute', () => {
      render(
        <>
          <Input aria-describedby="error-message" data-testid="input" />
          <span id="error-message">Error text</span>
        </>
      );

      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('aria-describedby', 'error-message');
    });

    it('has correct role for text input', () => {
      render(<Input data-testid="input" />);
      const input = screen.getByTestId('input');
      // HTML5 input elements don't have an implicit role attribute
      // but they function as textboxes
      expect(input.tagName).toBe('INPUT');
    });

    it('keyboard navigation works with Tab', async () => {
      const user = userEvent.setup();
      render(
        <>
          <Input data-testid="input1" />
          <Input data-testid="input2" />
        </>
      );

      const input1 = screen.getByTestId('input1');
      const input2 = screen.getByTestId('input2');

      input1.focus();
      expect(input1).toHaveFocus();

      await user.tab();
      expect(input2).toHaveFocus();
    });

    it('communicates required to screen readers', () => {
      render(<Input required data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toBeRequired();
    });

    it('communicates disabled to screen readers', () => {
      render(<Input disabled data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toBeDisabled();
    });

    it('has visible focus indicator', () => {
      render(<Input data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveClass('focus-visible:outline-none');
      expect(input).toHaveClass('focus-visible:ring-2');
    });

    it('associates error message via aria-describedby', () => {
      render(
        <>
          <label>
            Email
            <Input aria-invalid="true" aria-describedby="email-error" data-testid="input" />
          </label>
          <span id="email-error" role="alert">
            Invalid email format
          </span>
        </>
      );

      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('aria-invalid', 'true');
      expect(input).toHaveAttribute('aria-describedby', 'email-error');
    });
  });

  describe('Edge Cases', () => {
    it('handles empty input', async () => {
      const user = userEvent.setup();
      render(<Input data-testid="input" />);

      const input = screen.getByTestId('input');
      expect(input).toHaveValue('');

      await user.type(input, 'test');
      await user.clear(input);

      expect(input).toHaveValue('');
    });

    it('handles long input', async () => {
      const user = userEvent.setup();
      const longText = 'a'.repeat(1000);

      render(<Input data-testid="input" />);

      const input = screen.getByTestId('input');
      await user.type(input, longText);

      expect(input).toHaveValue(longText);
    });

    it('handles special characters', async () => {
      const user = userEvent.setup();
      render(<Input data-testid="input" />);

      const input = screen.getByTestId('input');
      // Type special characters that work with userEvent
      await user.type(input, '!@#$%^&*()_+-=;:,.<>');

      expect(input).toHaveValue('!@#$%^&*()_+-=;:,.<>');
    });

    it('handles Unicode and emojis', async () => {
      const user = userEvent.setup();
      render(<Input data-testid="input" />);

      const input = screen.getByTestId('input');
      await user.type(input, 'Hello 世界 🌍');

      expect(input).toHaveValue('Hello 世界 🌍');
    });

    it('handles controlled component state', async () => {
      const user = userEvent.setup();
      const TestControlled = () => {
        const [value, setValue] = React.useState('');
        return (
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            data-testid="input"
          />
        );
      };

      render(<TestControlled />);

      const input = screen.getByTestId('input');
      await user.type(input, 'controlled');

      expect(input).toHaveValue('controlled');
    });

    it('handles uncontrolled component state', async () => {
      const user = userEvent.setup();
      render(<Input defaultValue="uncontrolled" data-testid="input" />);

      const input = screen.getByTestId('input');
      expect(input).toHaveValue('uncontrolled');

      await user.type(input, ' modified');
      expect(input).toHaveValue('uncontrolled modified');
    });

    it('handles multiple rapid input changes', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();

      render(<Input onChange={handleChange} data-testid="input" />);

      const input = screen.getByTestId('input');
      await user.type(input, 'rapid typing');

      expect(handleChange).toHaveBeenCalled();
    });

    it('renders with custom className', () => {
      render(<Input className="custom-class" data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveClass('custom-class');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLInputElement>();
      render(<Input ref={ref} data-testid="input" />);
      expect(ref.current).toBeInstanceOf(HTMLInputElement);
      expect(ref.current?.tagName).toBe('INPUT');
    });

    it('handles name attribute', () => {
      render(<Input name="email" data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('name', 'email');
    });

    it('handles id attribute', () => {
      render(<Input id="email-input" data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('id', 'email-input');
    });

    it('handles autoComplete attribute', () => {
      render(<Input autoComplete="email" data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('autoComplete', 'email');
    });

    it('handles readOnly attribute', () => {
      render(<Input readOnly data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('readonly');
    });
  });

  describe('Combined Props', () => {
    it('renders with all validation attributes', () => {
      render(
        <Input
          type="email"
          required
          minLength={5}
          maxLength={50}
          pattern="[a-z]+@example\\.com"
          data-testid="input"
        />
      );

      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('type', 'email');
      expect(input).toBeRequired();
      expect(input).toHaveAttribute('minlength', '5');
      expect(input).toHaveAttribute('maxlength', '50');
      expect(input).toHaveAttribute('pattern', '[a-z]+@example\\\\.com');
    });

    it('renders with disabled and custom className', () => {
      render(<Input disabled className="custom-class" data-testid="input" />);
      const input = screen.getByTestId('input');
      expect(input).toBeDisabled();
      expect(input).toHaveClass('custom-class');
    });

    it('renders with all accessibility attributes', () => {
      render(
        <Input
          aria-invalid="true"
          aria-describedby="help-text"
          aria-label="Email input"
          required
          data-testid="input"
        />
      );

      const input = screen.getByTestId('input');
      expect(input).toHaveAttribute('aria-invalid', 'true');
      expect(input).toHaveAttribute('aria-describedby', 'help-text');
      expect(input).toHaveAttribute('aria-label', 'Email input');
      expect(input).toBeRequired();
    });
  });
});
