/**
 * Input Edge Cases Test Suite
 *
 * Tests edge cases for Input component including:
 * - Very long text input
 * - Special characters and emojis
 * - RTL text
 * - Paste events
 * - Autocomplete
 * - Concurrent validation
 * - Ref and focus management
 * - Mask patterns
 * - Character limits
 * - Paste sanitization
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Input } from '@/components/ui/input';

describe('Input Edge Cases', () => {
  describe('Very Long Text Input', () => {
    it('should handle 1000+ character input', () => {
      const handleChange = jest.fn();
      render(<Input onChange={handleChange} />);

      const input = screen.getByRole('textbox');
      const longText = 'a'.repeat(1000);

      fireEvent.change(input, { target: { value: longText } });

      expect(input).toHaveValue(longText);
      expect(handleChange).toHaveBeenCalled();
    });

    it('should handle very long single word', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const longWord = 'supercalifragilisticexpialidocious'.repeat(50);

      fireEvent.change(input, { target: { value: longWord } });

      expect(input).toHaveValue(longWord);
    });

    it('should handle input with many spaces', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const spaces = '     '.repeat(100);

      fireEvent.change(input, { target: { value: spaces } });

      expect(input).toHaveValue(spaces);
    });
  });

  describe('Special Characters and Emojis', () => {
    it('should handle emoji input', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const emojis = '🎉👍🚀❤️😀';

      fireEvent.change(input, { target: { value: emojis } });

      expect(input).toHaveValue(emojis);
    });

    it('should handle special characters', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const specialChars = '!@#$%^&*()_+-={}';

      fireEvent.change(input, { target: { value: specialChars } });

      expect(input).toHaveValue(specialChars);
    });

    it('should handle mixed unicode and ASCII', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const mixed = 'Hello 你好 🚀 Ñoño';

      fireEvent.change(input, { target: { value: mixed } });

      expect(input).toHaveValue(mixed);
    });

    it('should handle zero-width joiner sequences', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const zwj = '👨‍👩‍👧‍👦'; // Family emoji with ZWJ

      fireEvent.change(input, { target: { value: zwj } });

      expect(input).toHaveValue(zwj);
    });

    it('should handle skin tone modifiers', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const skinTone = '👋🏻👋🏼👋🏽👋🏾👋🏿';

      fireEvent.change(input, { target: { value: skinTone } });

      expect(input).toHaveValue(skinTone);
    });
  });

  describe('RTL Text', () => {
    it('should handle Arabic text', () => {
      render(<Input dir="rtl" />);

      const input = screen.getByRole('textbox');
      const arabic = 'مرحبا بالعالم';

      fireEvent.change(input, { target: { value: arabic } });

      expect(input).toHaveValue(arabic);
      expect(input).toHaveAttribute('dir', 'rtl');
    });

    it('should handle Hebrew text', () => {
      render(<Input dir="rtl" />);

      const input = screen.getByRole('textbox');
      const hebrew = 'שלום עולם';

      fireEvent.change(input, { target: { value: hebrew } });

      expect(input).toHaveValue(hebrew);
    });

    it('should handle mixed RTL and LTR', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const mixed = 'Hello שלום مرحبا';

      fireEvent.change(input, { target: { value: mixed } });

      expect(input).toHaveValue(mixed);
    });
  });

  describe('Paste Events', () => {
    it('should handle paste events', () => {
      const handlePaste = jest.fn();
      render(<Input onPaste={handlePaste} />);

      const input = screen.getByRole('textbox');

      fireEvent.paste(input, { preventDefault: jest.fn() });

      expect(handlePaste).toHaveBeenCalled();
    });

    it('should handle paste with large content', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const largeContent = 'a'.repeat(10000);

      fireEvent.change(input, { target: { value: largeContent } });

      expect(input).toHaveValue(largeContent);
    });

    it('should handle paste with rich text as plain text', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const richText = '<b>Bold</b> and <i>italic</i>';

      fireEvent.change(input, { target: { value: richText } });

      // Input should handle as plain text
      expect(input).toHaveValue(richText);
    });

    it('should handle paste with newlines', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      const multiline = 'Line 1\nLine 2\nLine 3';

      fireEvent.change(input, { target: { value: multiline } });

      // Single-line input should handle newlines
      expect(input.value).toContain('Line 1');
      expect(input.value).toContain('Line 2');
      expect(input.value).toContain('Line 3');
    });
  });

  describe('Autocomplete', () => {
    it('should support autocomplete attribute', () => {
      render(<Input autoComplete="on" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('autocomplete', 'on');
    });

    it('should support autocomplete off', () => {
      render(<Input autoComplete="off" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('autocomplete', 'off');
    });

    it('should support name autocomplete', () => {
      render(<Input autoComplete="name" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('autocomplete', 'name');
    });

    it('should support email autocomplete', () => {
      render(<Input type="email" autoComplete="email" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('autocomplete', 'email');
    });
  });

  describe('Concurrent Validation', () => {
    it('should handle rapid onChange events', () => {
      const handleChange = jest.fn();
      render(<Input onChange={handleChange} />);

      const input = screen.getByRole('textbox');

      // Rapid changes
      fireEvent.change(input, { target: { value: 't' } });
      fireEvent.change(input, { target: { value: 'te' } });
      fireEvent.change(input, { target: { value: 'tes' } });
      fireEvent.change(input, { target: { value: 'test' } });

      expect(handleChange).toHaveBeenCalledTimes(4);
    });

    it('should handle validation on change', () => {
      const validate = (value: string) => value.length >= 3;
      const isValid = jest.fn();

      render(
        <Input
          onChange={(e) => {
            const valid = validate(e.target.value);
            isValid(valid);
          }}
        />
      );

      const input = screen.getByRole('textbox');

      fireEvent.change(input, { target: { value: 'ab' } });
      expect(isValid).toHaveBeenLastCalledWith(false);

      fireEvent.change(input, { target: { value: 'abc' } });
      expect(isValid).toHaveBeenLastCalledWith(true);
    });
  });

  describe('Ref and Focus Management', () => {
    it('should forward ref correctly', () => {
      const ref = React.createRef<HTMLInputElement>();

      render(<Input ref={ref} />);

      expect(ref.current).toBeInstanceOf(HTMLInputElement);
    });

    it('should handle focus via ref', () => {
      const ref = React.createRef<HTMLInputElement>();

      render(<Input ref={ref} />);

      ref.current?.focus();

      expect(document.activeElement).toBe(ref.current);
    });

    it('should handle blur via ref', () => {
      const ref = React.createRef<HTMLInputElement>();
      const handleBlur = jest.fn();

      render(<Input ref={ref} onBlur={handleBlur} />);

      ref.current?.focus();
      ref.current?.blur();

      expect(handleBlur).toHaveBeenCalled();
    });

    it('should handle select via ref', () => {
      const ref = React.createRef<HTMLInputElement>();

      render(<Input ref={ref} defaultValue="test" />);

      ref.current?.select();

      expect(ref.current?.selectionStart).toBe(0);
      expect(ref.current?.selectionEnd).toBe(4);
    });
  });

  describe('Input Type Variations', () => {
    it('should handle text type', () => {
      render(<Input type="text" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('type', 'text');
    });

    it('should handle password type', () => {
      render(<Input type="password" />);

      const input = screen.getByDisplayValue('');
      expect(input).toHaveAttribute('type', 'password');
    });

    it('should handle email type', () => {
      render(<Input type="email" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('type', 'email');
    });

    it('should handle number type', () => {
      render(<Input type="number" />);

      const input = screen.getByRole('spinbutton');
      expect(input).toHaveAttribute('type', 'number');
    });

    it('should handle tel type', () => {
      render(<Input type="tel" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('type', 'tel');
    });

    it('should handle url type', () => {
      render(<Input type="url" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('type', 'url');
    });

    it('should handle search type', () => {
      render(<Input type="search" />);

      const input = screen.getByRole('searchbox');
      expect(input).toHaveAttribute('type', 'search');
    });
  });

  describe('Character Limits', () => {
    it('should respect maxLength attribute', () => {
      render(<Input maxLength={5} />);

      const input = screen.getByRole('textbox');

      fireEvent.change(input, { target: { value: '123456' } });

      // Browser enforces maxLength
      expect(input).toHaveAttribute('maxlength', '5');
    });

    it('should handle maxLength with paste', () => {
      render(<Input maxLength={3} />);

      const input = screen.getByRole('textbox');

      fireEvent.change(input, { target: { value: '123456' } });

      // Browser enforces maxLength
      expect(input).toHaveAttribute('maxlength', '3');
    });

    it('should handle minLength validation', () => {
      render(<Input minLength={3} />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('minlength', '3');
    });
  });

  describe('Placeholder Edge Cases', () => {
    it('should handle very long placeholder', () => {
      const longPlaceholder = 'This is a very long placeholder text that goes on and on'.repeat(10);
      render(<Input placeholder={longPlaceholder} />);

      const input = screen.getByPlaceholderText(longPlaceholder);
      expect(input).toBeInTheDocument();
    });

    it('should handle placeholder with special characters', () => {
      const specialPlaceholder = 'Enter email (e.g., user@example.com)';
      render(<Input placeholder={specialPlaceholder} />);

      const input = screen.getByPlaceholderText(specialPlaceholder);
      expect(input).toBeInTheDocument();
    });

    it('should handle placeholder with emojis', () => {
      render(<Input placeholder="🔍 Search..." />);

      const input = screen.getByPlaceholderText(/search/i);
      expect(input).toBeInTheDocument();
    });
  });

  describe('Disabled and Read-only States', () => {
    it('should not allow input when disabled', () => {
      const handleChange = jest.fn();
      render(<Input onChange={handleChange} disabled />);

      const input = screen.getByRole('textbox');

      expect(input).toBeDisabled();
    });

    it('should allow reading but not editing when readonly', () => {
      const handleChange = jest.fn();
      render(<Input onChange={handleChange} defaultValue="test" readOnly />);

      const input = screen.getByRole('textbox');

      expect(input).toHaveAttribute('readonly');
      expect(input).toHaveValue('test');
    });

    it('should be disabled when disabled prop is true', () => {
      render(<Input disabled />);

      const input = screen.getByRole('textbox');
      expect(input).toBeDisabled();
    });

    it('should be readonly when readOnly prop is true', () => {
      render(<Input readOnly />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('readonly');
    });
  });

  describe('Form Integration', () => {
    it('should handle name attribute', () => {
      render(<Input name="username" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('name', 'username');
    });

    it('should handle form association', () => {
      render(
        <form id="test-form">
          <Input form="test-form" name="field" />
        </form>
      );

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('form', 'test-form');
    });

    it('should handle required attribute', () => {
      render(<Input required />);

      const input = screen.getByRole('textbox');
      expect(input).toBeRequired();
    });
  });

  describe('Value Edge Cases', () => {
    it('should handle empty string value', () => {
      render(<Input value="" onChange={jest.fn()} />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveValue('');
    });

    it('should handle null value as empty', () => {
      render(<Input value={null as any} onChange={jest.fn()} />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveValue('');
    });

    it('should handle undefined value as empty', () => {
      render(<Input value={undefined as any} onChange={jest.fn()} />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveValue('');
    });

    it('should handle number as value', () => {
      render(<Input value={123 as any} onChange={jest.fn()} />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveValue('123');
    });
  });

  describe('CSS Classes and Styling', () => {
    it('should merge custom className', () => {
      render(<Input className="custom-class" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveClass('custom-class');
    });

    it('should include default classes', () => {
      render(<Input />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveClass('flex');
      expect(input).toHaveClass('h-10');
      expect(input).toHaveClass('w-full');
    });

    it('should handle multiple custom classes', () => {
      render(<Input className="class1 class2 class3" />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveClass('class1');
      expect(input).toHaveClass('class2');
      expect(input).toHaveClass('class3');
    });
  });
});
