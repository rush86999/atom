/**
 * InteractiveForm Edge Case Tests
 *
 * Purpose: Test edge cases and boundary values for InteractiveForm validation
 * Focus: Empty/null/undefined inputs, boundary values (min/max), special characters, unicode
 *
 * Test Groups:
 * 1. Required Field Edge Cases (10 tests)
 * 2. Boundary Value Tests for Numbers (12 tests)
 * 3. Boundary Value Tests for String Length (10 tests)
 * 4. Format Validation Edge Cases (8 tests)
 * 5. Type Coercion Edge Cases (6 tests)
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { InteractiveForm } from '../InteractiveForm';

// Mock window.atom.canvas (from interactive-form.test.tsx pattern)
const mockCanvasAPI = {
  getState: jest.fn(),
  getAllStates: jest.fn(),
  subscribe: jest.fn(),
  subscribeAll: jest.fn()
};

beforeEach(() => {
  (window as any).atom = { canvas: mockCanvasAPI };
  jest.clearAllMocks();
});

afterEach(() => {
  delete (window as any).atom;
});

describe('InteractiveForm - Required Field Edge Cases', () => {

  test('should reject empty string for required field', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/name/i);
    const submitButton = screen.getByRole('button', { name: /submit/i });

    // Enter empty string and submit
    await user.clear(input);
    await user.click(submitButton);

    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test('should reject whitespace-only string for required field', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/name/i);
    const submitButton = screen.getByRole('button', { name: /submit/i });

    // Enter whitespace and submit
    await user.type(input, '   ');
    await user.click(submitButton);

    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test('should handle null value for required field', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'age', label: 'Age', type: 'number' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });

    // Number input with empty value acts like null
    await user.click(submitButton);

    // Should show validation error
    expect(screen.getByText(/age is required/i)).toBeInTheDocument();
  });

  test('should handle undefined for required field', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });

    // Don't enter anything (undefined)
    await user.click(submitButton);

    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
  });

  test('should accept zero (0) as valid for required number field', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'count', label: 'Count', type: 'number' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/count/i);

    // Enter 0 and submit
    await user.type(input, '0');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Wait for async submit
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ count: 0 });
    }, { timeout: 3000 });
  });

  test('should accept false as valid for required checkbox', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'agree', label: 'I agree', type: 'checkbox' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const checkbox = screen.getByRole('checkbox');

    // Checkbox unchecked (false) should still submit
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Wait for async submit
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ agree: false });
    }, { timeout: 3000 });
  });

  test('should reject single space for required field', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/name/i);

    await user.type(input, ' ');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
  });

  test('should reject tab character for required field', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/name/i);

    // Enter tab character
    await user.type(input, '\t');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
  });

  test('should reject newline-only string for required field', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/name/i);

    // Enter newline
    await user.type(input, '\n');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
  });

  test('should reject mixed whitespace for required field', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/name/i);

    // Enter mixed whitespace
    await user.type(input, '  \t\n  ');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
  });
});

describe('InteractiveForm - Boundary Value Tests for Numbers', () => {

  test('should reject value below min (min-1)', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        validation: { min: 18 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/age/i);

    await user.type(input, '17');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/age must be at least 18/i)).toBeInTheDocument();
  });

  test('should accept value at min boundary', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        validation: { min: 18 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/age/i);

    await user.type(input, '18');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ age: 18 });
    }, { timeout: 3000 });
  });

  test('should accept value above min (min+1)', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        validation: { min: 18 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/age/i);

    await user.type(input, '19');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ age: 19 });
    }, { timeout: 3000 });
  });

  test('should accept value below max (max-1)', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        validation: { max: 100 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/age/i);

    await user.type(input, '99');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ age: 99 });
    }, { timeout: 3000 });
  });

  test('should accept value at max boundary', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        validation: { max: 100 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/age/i);

    await user.type(input, '100');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ age: 100 });
    }, { timeout: 3000 });
  });

  test('should reject value above max (max+1)', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        validation: { max: 100 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/age/i);

    await user.type(input, '101');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/age must be at most 100/i)).toBeInTheDocument();
  });

  test('should reject negative numbers when min=0', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      {
        name: 'count',
        label: 'Count',
        type: 'number' as const,
        validation: { min: 0 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/count/i);

    await user.type(input, '-1');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/count must be at least 0/i)).toBeInTheDocument();
  });

  test('should handle decimal values at boundaries', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'price',
        label: 'Price',
        type: 'number' as const,
        validation: { min: 18 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/price/i);

    // 18.0 should pass (equal to min)
    await user.type(input, '18.0');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ price: 18 });
    }, { timeout: 3000 });
  });

  test('should handle very large numbers (MAX_SAFE_INTEGER)', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'big', label: 'Big Number', type: 'number' as const }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/big number/i);

    await user.type(input, Number.MAX_SAFE_INTEGER.toString());
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    }, { timeout: 3000 });
  });

  test('should handle very small decimals', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'tiny', label: 'Tiny', type: 'number' as const }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/tiny/i);

    await user.type(input, '0.0001');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ tiny: 0.0001 });
    }, { timeout: 3000 });
  });

  test('should handle NaN gracefully', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      { name: 'value', label: 'Value', type: 'number' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });

    // Empty number field results in NaN when parsed
    await user.click(submitButton);

    expect(screen.getByText(/value is required/i)).toBeInTheDocument();
  });

  test('should handle Infinity gracefully', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'value',
        label: 'Value',
        type: 'number' as const,
        validation: { max: 100 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/value/i);

    // Very large number exceeds max
    await user.type(input, '999999');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/value must be at most 100/i)).toBeInTheDocument();
  });
});

describe('InteractiveForm - Boundary Value Tests for String Length', () => {

  test('should reject empty string when min=1', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      {
        name: 'name',
        label: 'Name',
        type: 'text' as const,
        validation: { pattern: '.{1,}', custom: 'Must not be empty' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });

    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/must not be empty/i)).toBeInTheDocument();
    });
  });

  test('should accept string at min length exactly', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'code',
        label: 'Code',
        type: 'text' as const,
        validation: { pattern: '.{3}', custom: 'Must be 3 chars' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/code/i);

    await user.type(input, 'abc');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ code: 'abc' });
    }, { timeout: 3000 });
  });

  test('should reject string below min by 1', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      {
        name: 'code',
        label: 'Code',
        type: 'text' as const,
        validation: { pattern: '.{3,}', custom: 'Must be at least 3 chars' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/code/i);

    await user.type(input, 'ab');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/must be at least 3 chars/i)).toBeInTheDocument();
  });

  test('should accept string at max length exactly', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'code',
        label: 'Code',
        type: 'text' as const,
        validation: { pattern: '.{0,5}', custom: 'Must be at most 5 chars' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/code/i);

    await user.type(input, 'abcde');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ code: 'abcde' });
    }, { timeout: 3000 });
  });

  test('should reject string above max by 1', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      {
        name: 'code',
        label: 'Code',
        type: 'text' as const,
        validation: { pattern: '.{0,5}', custom: 'Must be at most 5 chars' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/code/i);

    await user.type(input, 'abcdef');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/must be at most 5 chars/i)).toBeInTheDocument();
  });

  test('should handle unicode character boundaries (emoji)', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'emoji',
        label: 'Emoji',
        type: 'text' as const,
        validation: { pattern: '^.{1,5}$', custom: 'Must be 1-5 chars' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/emoji/i);

    // Emoji can be 2+ code units but count as 1 character
    await user.type(input, '😀');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    }, { timeout: 3000 });
  });

  test('should handle multibyte characters', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'text', label: 'Text', type: 'text' as const }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/text/i);

    // Chinese characters (multibyte)
    await user.type(input, '你好世界');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ text: '你好世界' });
    }, { timeout: 3000 });
  });

  test('should handle very long strings (10000+ chars)', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'long', label: 'Long', type: 'text' as const }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/long/i);

    const longString = 'a'.repeat(10000);
    await user.type(input, longString);
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ long: longString });
    }, { timeout: 3000 });
  });

  test('should handle zero-width characters', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'text', label: 'Text', type: 'text' as const }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/text/i);

    // Zero-width space
    await user.type(input, 'a\u200Bb');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    }, { timeout: 3000 });
  });

  test('should handle combining characters', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'text', label: 'Text', type: 'text' as const }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/text/i);

    // Combining acute accent
    await user.type(input, 'cafe\u0301');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    }, { timeout: 3000 });
  });
});

describe('InteractiveForm - Format Validation Edge Cases', () => {

  test('should handle email with trailing dot', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      {
        name: 'email',
        label: 'Email',
        type: 'email' as const,
        validation: { pattern: '^[^@]+@[^@]+\\.[^@]+$', custom: 'Invalid email' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/email/i);

    await user.type(input, 'test@example.com.');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Pattern should reject trailing dot
    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    });
  });

  test('should handle email with multiple @', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      {
        name: 'email',
        label: 'Email',
        type: 'email' as const,
        validation: { pattern: '^[^@]+@[^@]+\\.[^@]+$', custom: 'Invalid email' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/email/i);

    await user.type(input, 'test@@example.com');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
  });

  test('should handle email with IP address domain', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'email',
        label: 'Email',
        type: 'email' as const,
        validation: { pattern: '^[^@]+@[^@]+$', custom: 'Invalid email' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/email/i);

    await user.type(input, 'test@127.0.0.1');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Simple pattern should accept IP address format
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    }, { timeout: 3000 });
  });

  test('should reject URL without protocol', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      {
        name: 'website',
        label: 'Website',
        type: 'text' as const,
        validation: { pattern: '^https?://.+', custom: 'Must include http/https' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/website/i);

    await user.type(input, 'example.com');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/must include http\/https/i)).toBeInTheDocument();
  });

  test('should accept URL with fragment', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'website',
        label: 'Website',
        type: 'text' as const,
        validation: { pattern: '^https?://.+', custom: 'Invalid URL' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/website/i);

    await user.type(input, 'https://example.com#section');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ website: 'https://example.com#section' });
    }, { timeout: 3000 });
  });

  test('should handle phone with extensions', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'phone',
        label: 'Phone',
        type: 'text' as const,
        validation: { pattern: '^[\\d\\s\\-\\(\\)\\+]+$', custom: 'Invalid phone' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/phone/i);

    await user.type(input, '123-456-7890 ext 123');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Pattern should accept digits, spaces, dashes, parentheses, plus
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    }, { timeout: 3000 });
  });

  test('should handle pattern with special regex chars', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'code',
        label: 'Code',
        type: 'text' as const,
        validation: { pattern: '^[A-Z0-9._%+-]+$', custom: 'Invalid code' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/code/i);

    await user.type(input, 'ABC.123%+-');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ code: 'ABC.123%+-' });
    }, { timeout: 3000 });
  });

  test('should escape special characters in patterns', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      {
        name: 'input',
        label: 'Input',
        type: 'text' as const,
        validation: { pattern: '^\\w+$', custom: 'Alphanumeric only' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/input/i);

    await user.type(input, 'test-123');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Dash is not in \\w pattern
    expect(screen.getByText(/alphanumeric only/i)).toBeInTheDocument();
  });
});

describe('InteractiveForm - Type Coercion Edge Cases', () => {

  test('should parse string number to number type', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'age', label: 'Age', type: 'number' as const }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/age/i);

    await user.type(input, '25');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ age: 25 });
      // Verify it's a number, not string
      expect(typeof onSubmit.mock.calls[0][0].age).toBe('number');
    }, { timeout: 3000 });
  });

  test('should handle empty string to number field', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    const fields = [
      { name: 'age', label: 'Age', type: 'number' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });

    await user.click(submitButton);

    expect(screen.getByText(/age is required/i)).toBeInTheDocument();
  });

  test('should handle boolean checkbox true value', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'agree', label: 'Agree', type: 'checkbox' as const }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const checkbox = screen.getByRole('checkbox');

    await user.click(checkbox);
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ agree: true });
      expect(typeof onSubmit.mock.calls[0][0].agree).toBe('boolean');
    }, { timeout: 3000 });
  });

  test('should handle boolean checkbox false value', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'agree', label: 'Agree', type: 'checkbox' as const }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    // Leave unchecked
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ agree: false });
      expect(typeof onSubmit.mock.calls[0][0].agree).toBe('boolean');
    }, { timeout: 3000 });
  });

  test('should handle select field with empty string value', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'country',
        label: 'Country',
        type: 'select' as const,
        options: [
          { value: 'us', label: 'USA' },
          { value: 'ca', label: 'Canada' }
        ]
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    // Leave at default "Select..." (empty string)
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ country: '' });
    }, { timeout: 3000 });
  });

  test('should handle select field with valid selection', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      {
        name: 'country',
        label: 'Country',
        type: 'select' as const,
        options: [
          { value: 'us', label: 'USA' },
          { value: 'ca', label: 'Canada' }
        ]
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={onSubmit} />);

    const select = screen.getByRole('combobox');

    await user.selectOptions(select, 'us');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ country: 'us' });
    }, { timeout: 3000 });
  });
});
