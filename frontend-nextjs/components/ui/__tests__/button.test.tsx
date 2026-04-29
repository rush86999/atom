import React from 'react';
import { renderWithProviders, screen } from '../../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { Button } from '@/components/ui/button';

describe('Button Component', () => {
  describe('Rendering', () => {
    it('renders default button', () => {
      renderWithProviders(<Button>Click me</Button>);
      const button = screen.getByRole('button', { name: 'Click me' });
      expect(button).toBeInTheDocument();
      expect(button).toHaveClass('bg-primary-600');
    });

    it('renders destructive variant', () => {
      renderWithProviders(<Button variant="destructive">Delete</Button>);
      const button = screen.getByRole('button', { name: 'Delete' });
      expect(button).toBeInTheDocument();
      expect(button).toHaveClass('bg-red-500');
    });

    it('renders outline variant', () => {
      renderWithProviders(<Button variant="outline">Cancel</Button>);
      const button = screen.getByRole('button', { name: 'Cancel' });
      expect(button).toBeInTheDocument();
      expect(button).toHaveClass('border');
      expect(button).toHaveClass('border-input');
    });

    it('renders secondary variant', () => {
      renderWithProviders(<Button variant="secondary">Secondary</Button>);
      const button = screen.getByRole('button', { name: 'Secondary' });
      expect(button).toBeInTheDocument();
      expect(button).toHaveClass('bg-secondary-100');
    });

    it('renders ghost variant', () => {
      renderWithProviders(<Button variant="ghost">Ghost</Button>);
      const button = screen.getByRole('button', { name: 'Ghost' });
      expect(button).toBeInTheDocument();
      expect(button).toHaveClass('hover:bg-accent');
    });

    it('renders link variant', () => {
      renderWithProviders(<Button variant="link">Learn more</Button>);
      const button = screen.getByRole('button', { name: 'Learn more' });
      expect(button).toBeInTheDocument();
      expect(button).toHaveClass('underline-offset-4');
      expect(button).toHaveClass('hover:underline');
    });
  });

  describe('Size Variants', () => {
    it.each([
      ['default', 'h-10'],
      ['sm', 'h-9'],
      ['lg', 'h-11'],
      ['icon', 'h-10 w-10'],
    ])('renders %s size with correct classes', (size, expectedClass) => {
      renderWithProviders(<Button size={size as any}>Button</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass(expectedClass);
    });
  });

  describe('User Interactions', () => {
    it('calls onClick handler when clicked', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();

      renderWithProviders(<Button onClick={handleClick}>Click me</Button>);

      const button = screen.getByRole('button');
      await user.click(button);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('does not call onClick when disabled', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();

      renderWithProviders(<Button onClick={handleClick} disabled>Click me</Button>);

      const button = screen.getByRole('button');
      expect(button).toBeDisabled();

      await user.click(button);

      expect(handleClick).not.toHaveBeenCalled();
    });

    it('prevents default behavior for form submissions', async () => {
      const user = userEvent.setup();
      const handleSubmit = jest.fn((e: React.FormEvent) => e.preventDefault());

      renderWithProviders(<Button onClick={handleSubmit}>Submit</Button>);

      const button = screen.getByRole('button');
      await user.click(button);

      expect(handleSubmit).toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has accessible name', () => {
      renderWithProviders(<Button>Submit</Button>);
      const button = screen.getByRole('button', { name: 'Submit' });
      expect(button).toBeInTheDocument();
    });

    it('forwards aria-label', () => {
      renderWithProviders(<Button aria-label="Close dialog">&times;</Button>);
      const button = screen.getByRole('button', { name: /close dialog/i });
      expect(button).toBeInTheDocument();
    });

    it('forwards aria-describedby', () => {
      renderWithProviders(
        <>
          <Button aria-describedby="description">Submit</Button>
          <span id="description">Form submission</span>
        </>
      );
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-describedby', 'description');
    });

    it('has correct button role', () => {
      renderWithProviders(<Button>Click me</Button>);
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('keyboard navigation works with Enter key', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();

      renderWithProviders(<Button onClick={handleClick}>Submit</Button>);

      const button = screen.getByRole('button');
      button.focus();
      await user.keyboard('{Enter}');

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('keyboard navigation works with Space key', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();

      renderWithProviders(<Button onClick={handleClick}>Submit</Button>);

      const button = screen.getByRole('button');
      button.focus();
      await user.keyboard('{ }');

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('disabled attribute communicated to screen readers', () => {
      renderWithProviders(<Button disabled>Disabled</Button>);
      const button = screen.getByRole('button');
      expect(button).toBeDisabled();
    });

    it('has visible focus indicator for keyboard users', () => {
      renderWithProviders(<Button>Focus test</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('focus-visible:outline-none');
      expect(button).toHaveClass('focus-visible:ring-2');
    });
  });

  describe('Edge Cases', () => {
    it('renders with text children', () => {
      renderWithProviders(<Button>Text content</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Text content');
    });

    it('renders with icon children', () => {
      renderWithProviders(
        <Button>
          <span data-testid="icon">🔥</span>
          Icon
        </Button>
      );
      const button = screen.getByRole('button');
      const icon = screen.getByTestId('icon');
      expect(button).toContainElement(icon);
      expect(button).toHaveTextContent('Icon');
    });

    it('renders with custom className', () => {
      renderWithProviders(<Button className="custom-class">Custom</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('custom-class');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLButtonElement>();
      renderWithProviders(<Button ref={ref}>Ref test</Button>);
      expect(ref.current).toBeInstanceOf(HTMLButtonElement);
      expect(ref.current?.tagName).toBe('BUTTON');
    });

    it('handles multiple clicks', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();

      renderWithProviders(<Button onClick={handleClick}>Click me</Button>);

      const button = screen.getByRole('button');
      await user.dblClick(button);

      expect(handleClick).toHaveBeenCalledTimes(2);
    });

    it('renders with data-* attributes', () => {
      renderWithProviders(<Button data-testid="custom-button">Test</Button>);
      const button = screen.getByTestId('custom-button');
      expect(button).toBeInTheDocument();
    });

    it('handles form attribute', () => {
      renderWithProviders(<Button form="my-form">Submit</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('form', 'my-form');
    });

    it('handles type attribute', () => {
      renderWithProviders(<Button type="submit">Submit</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('type', 'submit');
    });

    it('renders with long text content', () => {
      const longText = 'This is a very long button text that might wrap or truncate';
      renderWithProviders(<Button>{longText}</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveTextContent(longText);
    });

    it('handles special characters in text', () => {
      renderWithProviders(<Button>Button with &lt;special&gt; &amp; &quot;characters&quot;</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Button with <special> & "characters"');
    });
  });

  describe('Combined Props', () => {
    it('renders with variant and size', () => {
      renderWithProviders(<Button variant="destructive" size="lg">Delete All</Button>);
      const button = screen.getByRole('button', { name: 'Delete All' });
      expect(button).toHaveClass('bg-red-500');
      expect(button).toHaveClass('h-11');
    });

    it('renders with all props combined', () => {
      renderWithProviders(
        <Button
          variant="outline"
          size="sm"
          disabled
          className="extra-class"
          aria-label="Save draft"
        >
          Save
        </Button>
      );
      const button = screen.getByRole('button', { name: /save draft/i });
      expect(button).toHaveClass('border');
      expect(button).toHaveClass('h-9');
      expect(button).toHaveClass('extra-class');
      expect(button).toBeDisabled();
    });

    it('respects className merging with cva classes', () => {
      renderWithProviders(<Button className="bg-red-600">Custom Style</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-red-600');
    });
  });
});
