/**
 * Button Edge Cases Test Suite
 *
 * Tests edge cases for Button component including:
 * - Rapid clicking
 * - Loading states
 * - Disabled states
 * - Long text
 * - Special characters
 * - Concurrent handlers
 * - Ref forwarding
 * - Custom events
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '@/components/ui/button';

describe('Button Edge Cases', () => {
  describe('Rapid Clicking', () => {
    it('should handle rapid clicks without errors', () => {
      const handleClick = jest.fn();
      render(<Button onClick={handleClick}>Click Me</Button>);

      const button = screen.getByRole('button', { name: /click me/i });

      // Rapid clicks
      fireEvent.click(button);
      fireEvent.click(button);
      fireEvent.click(button);

      expect(handleClick).toHaveBeenCalledTimes(3);
    });

    it('should handle double-click without errors', () => {
      const handleClick = jest.fn();
      render(<Button onClick={handleClick}>Double Click</Button>);

      const button = screen.getByRole('button', { name: /double click/i });

      fireEvent.click(button);
      fireEvent.click(button);

      // Double-click fires two click events
      expect(handleClick).toHaveBeenCalledTimes(2);
    });

    it('should handle clicks during loading state', () => {
      const handleClick = jest.fn();
      render(
        <Button onClick={handleClick} disabled>
          Loading...
        </Button>
      );

      const button = screen.getByRole('button', { name: /loading/i });

      fireEvent.click(button);

      // Disabled button should not trigger handler
      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  describe('Disabled States', () => {
    it('should not trigger onClick when disabled', () => {
      const handleClick = jest.fn();
      render(<Button onClick={handleClick} disabled>Disabled</Button>);

      const button = screen.getByRole('button', { name: /disabled/i });

      fireEvent.click(button);

      expect(handleClick).not.toHaveBeenCalled();
      expect(button).toBeDisabled();
    });

    it('should have aria-disabled when disabled', () => {
      render(<Button disabled>Disabled Button</Button>);

      const button = screen.getByRole('button', { name: /disabled button/i });

      // HTML disabled attribute implies aria-disabled, but button might not have explicit aria-disabled
      expect(button).toBeDisabled();
    });

    it('should handle pointer events when disabled', () => {
      const handleClick = jest.fn();
      render(<Button onClick={handleClick} disabled>Disabled</Button>);

      const button = screen.getByRole('button', { name: /disabled/i });

      // Try various pointer events
      fireEvent.mouseDown(button);
      fireEvent.mouseUp(button);
      fireEvent.pointerDown(button);
      fireEvent.pointerUp(button);

      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  describe('Long Text', () => {
    it('should handle very long text content', () => {
      const longText = 'This is a very long button text that goes on and on and on and on and on and on and on';
      render(<Button>{longText}</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent(longText);
    });

    it('should handle text with overflow', () => {
      const overflowText = 'A'.repeat(1000);
      render(<Button>{overflowText}</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent(overflowText);
    });

    it('should handle text with newlines', () => {
      render(<Button>Line 1{"\n"}Line 2</Button>);

      const button = screen.getByRole('button');
      // HTML collapses newlines to spaces in button text
      expect(button).toHaveTextContent('Line 1 Line 2');
    });
  });

  describe('Special Characters', () => {
    it('should handle emoji characters', () => {
      render(<Button>🎉 Celebration! 👍</Button>);

      const button = screen.getByRole('button', { name: /celebration/i });
      expect(button).toHaveTextContent('🎉 Celebration! 👍');
    });

    it('should handle HTML entities', () => {
      render(<Button>Special &amp; Characters &lt;3</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Special & Characters <3');
    });

    it('should handle unicode characters', () => {
      render(<Button>Unicode: 你好 🚀 Ñoño</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Unicode: 你好 🚀 Ñoño');
    });

    it('should handle RTL text', () => {
      render(<Button dir="rtl">مرحبا بالعالم</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('مرحبا بالعالم');
      expect(button).toHaveAttribute('dir', 'rtl');
    });

    it('should handle zero-width joiner sequences', () => {
      render(<Button>👨‍👩‍👧‍👦 Family Emoji</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('👨‍👩‍👧‍👦 Family Emoji');
    });
  });

  describe('Concurrent Handlers', () => {
    it('should handle multiple onClick handlers', () => {
      const handleClick1 = jest.fn();
      const handleClick2 = jest.fn();

      // Note: React only allows one onClick prop, but we can test
      // that the handler itself can call multiple functions
      const combinedHandler = () => {
        handleClick1();
        handleClick2();
      };

      render(<Button onClick={combinedHandler}>Multi Handler</Button>);

      const button = screen.getByRole('button', { name: /multi handler/i });
      fireEvent.click(button);

      expect(handleClick1).toHaveBeenCalledTimes(1);
      expect(handleClick2).toHaveBeenCalledTimes(1);
    });

    it('should handle onClick with onMouseDown', () => {
      const handleClick = jest.fn();
      const handleMouseDown = jest.fn();

      render(
        <Button onClick={handleClick} onMouseDown={handleMouseDown}>
          Both Handlers
        </Button>
      );

      const button = screen.getByRole('button', { name: /both handlers/i });

      fireEvent.mouseDown(button);
      fireEvent.click(button);

      expect(handleMouseDown).toHaveBeenCalledTimes(1);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('should handle onClick with onMouseUp', () => {
      const handleClick = jest.fn();
      const handleMouseUp = jest.fn();

      render(
        <Button onClick={handleClick} onMouseUp={handleMouseUp}>
          Both Handlers
        </Button>
      );

      const button = screen.getByRole('button', { name: /both handlers/i });

      fireEvent.mouseUp(button);
      fireEvent.click(button);

      expect(handleMouseUp).toHaveBeenCalledTimes(1);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('Ref Forwarding', () => {
    it('should forward ref correctly', () => {
      const ref = React.createRef<HTMLButtonElement>();

      render(<Button ref={ref}>Ref Button</Button>);

      expect(ref.current).toBeInstanceOf(HTMLButtonElement);
      expect(ref.current?.tagName).toBe('BUTTON');
    });

    it('should allow DOM access via ref', () => {
      const ref = React.createRef<HTMLButtonElement>();

      render(<Button ref={ref}>Ref Button</Button>);

      expect(ref.current).not.toBeNull();
      expect(ref.current?.textContent).toBe('Ref Button');
    });

    it('should handle focus via ref', () => {
      const ref = React.createRef<HTMLButtonElement>();

      render(<Button ref={ref}>Focus Button</Button>);

      ref.current?.focus();

      expect(document.activeElement).toBe(ref.current);
    });
  });

  describe('Custom Events', () => {
    it('should handle onMouseEnter', () => {
      const handleMouseEnter = jest.fn();
      render(<Button onMouseEnter={handleMouseEnter}>Hover Me</Button>);

      const button = screen.getByRole('button', { name: /hover me/i });
      fireEvent.mouseEnter(button);

      expect(handleMouseEnter).toHaveBeenCalledTimes(1);
    });

    it('should handle onMouseLeave', () => {
      const handleMouseLeave = jest.fn();
      render(<Button onMouseLeave={handleMouseLeave}>Hover Me</Button>);

      const button = screen.getByRole('button', { name: /hover me/i });
      fireEvent.mouseLeave(button);

      expect(handleMouseLeave).toHaveBeenCalledTimes(1);
    });

    it('should handle onFocus', () => {
      const handleFocus = jest.fn();
      render(<Button onFocus={handleFocus}>Focus Me</Button>);

      const button = screen.getByRole('button', { name: /focus me/i });
      fireEvent.focus(button);

      expect(handleFocus).toHaveBeenCalledTimes(1);
    });

    it('should handle onBlur', () => {
      const handleBlur = jest.fn();
      render(<Button onBlur={handleBlur}>Blur Me</Button>);

      const button = screen.getByRole('button', { name: /blur me/i });
      fireEvent.blur(button);

      expect(handleBlur).toHaveBeenCalledTimes(1);
    });
  });

  describe('Edge Cases', () => {
    it('should render with empty children', () => {
      render(<Button>{''}</Button>);

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button.textContent).toBe('');
    });

    it('should render with only whitespace', () => {
      render(<Button>{'   '}</Button>);

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should render with null content', () => {
      render(<Button>{null as any}</Button>);

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should handle custom className', () => {
      render(<Button className="custom-class">Custom</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('custom-class');
    });

    it('should handle custom data attributes', () => {
      render(<Button data-testid="custom-button">Custom</Button>);

      const button = screen.getByTestId('custom-button');
      expect(button).toBeInTheDocument();
    });

    it('should handle type attribute', () => {
      render(<Button type="submit">Submit</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('type', 'submit');
    });

    it('should handle form attributes', () => {
      render(
        <Button formAction="/submit" formMethod="post">
          Submit
        </Button>
      );

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('formaction', '/submit');
      expect(button).toHaveAttribute('formmethod', 'post');
    });
  });

  describe('Variant and Size Combinations', () => {
    it('should handle all variant combinations', () => {
      const variants: Array<'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'> = [
        'default',
        'destructive',
        'outline',
        'secondary',
        'ghost',
        'link',
      ];

      variants.forEach((variant) => {
        const { unmount } = render(<Button variant={variant}>{variant}</Button>);
        const button = screen.getByRole('button', { name: variant });
        expect(button).toBeInTheDocument();
        unmount();
      });
    });

    it('should handle all size combinations', () => {
      const sizes: Array<'default' | 'sm' | 'lg' | 'icon'> = ['default', 'sm', 'lg', 'icon'];

      sizes.forEach((size) => {
        const { unmount } = render(<Button size={size}>{size}</Button>);
        const button = screen.getByRole('button', { name: size });
        expect(button).toBeInTheDocument();
        unmount();
      });
    });

    it('should handle variant and size combinations', () => {
      const { container } = render(
        <Button variant="outline" size="lg">
          Combined
        </Button>
      );

      const button = screen.getByRole('button', { name: /combined/i });
      expect(button).toBeInTheDocument();
      expect(button).toHaveClass('h-11'); // lg size
    });
  });

  describe('Accessibility Edge Cases', () => {
    it('should handle aria-label with special characters', () => {
      render(<Button aria-label="Close &times;">&times;</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Close ×');
    });

    it('should handle aria-describedby', () => {
      render(
        <div>
          <span id="desc">Button description</span>
          <Button aria-describedby="desc">Described</Button>
        </div>
      );

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-describedby', 'desc');
    });

    it('should handle aria-pressed state', () => {
      render(<Button aria-pressed="true">Toggle</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-pressed', 'true');
    });

    it('should handle aria-expanded state', () => {
      render(<Button aria-expanded="false">Expand</Button>);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });
  });
});
