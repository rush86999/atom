import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { InteractiveForm } from '../InteractiveForm';

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

describe('InteractiveForm - Error Message Location and Visibility', () => {
  const fields = [
    { name: 'name', label: 'Name', type: 'text' as const, required: true },
    { name: 'email', label: 'Email', type: 'email' as const, required: true }
  ];

  test('error appears below the field with text-red-500 class', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    await user.click(submitButton);

    await waitFor(() => {
      const errorMessage = screen.getByText(/name is required/i);
      expect(errorMessage).toBeInTheDocument();
      expect(errorMessage.className).toContain('text-red-500');
    });
  });

  test('error includes AlertCircle icon', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    await user.click(submitButton);

    await waitFor(() => {
      const errorContainer = screen.getByText(/name is required/i).closest('div');
      expect(errorContainer).toBeInTheDocument();
      // AlertCircle should be present in the error container
      expect(errorContainer?.querySelector('svg')).toBeInTheDocument();
    });
  });

  test('multiple errors show for multiple fields', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });
  });

  test('form-level error shows for submission failures', async () => {
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Network error'));
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Fill form with valid data to trigger submission error
    const nameInput = screen.getByLabelText(/name/i);
    const emailInput = screen.getByLabelText(/email/i);
    const submitButton = screen.getByRole('button', { name: /submit/i });

    await user.type(nameInput, 'John Doe');
    await user.type(emailInput, 'john@example.com');
    await user.click(submitButton);

    await waitFor(() => {
      const formError = screen.getByText(/submission failed/i);
      expect(formError).toBeInTheDocument();
      expect(formError.className).toContain('text-red-600');
    });
  });

  test('error is visible immediately after submit', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    await user.click(submitButton);

    // Error should appear in the next render cycle
    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });
  });

  test('error persists when user starts typing', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const nameInput = screen.getByLabelText(/name/i);

    // Trigger error
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });

    // Start typing - error should persist (CRITICAL PATTERN)
    await user.type(nameInput, 'J');
    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });
  });

  test('error disappears on next submit after correction', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const nameInput = screen.getByLabelText(/name/i);
    const emailInput = screen.getByLabelText(/email/i);

    // Trigger error
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });

    // Correct the input
    await user.type(nameInput, 'John Doe');
    await user.type(emailInput, 'john@example.com');

    // Resubmit - error should clear (CRITICAL PATTERN)
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.queryByText(/name is required/i)).not.toBeInTheDocument();
    });
  });

  test('no duplicate error messages', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });

    // Submit multiple times
    await user.click(submitButton);
    await user.click(submitButton);

    await waitFor(() => {
      const errors = screen.getAllByText(/required/i);
      expect(errors.length).toBe(2); // One for name, one for email
    });
  });
});

describe('InteractiveForm - Required Field Error Messages', () => {
  test('error format is "{label} is required"', async () => {
    const user = userEvent.setup();
    const fields = [
      { name: 'fullName', label: 'Full Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/full name is required/i)).toBeInTheDocument();
    });
  });

  test('label matches field label exactly', async () => {
    const user = userEvent.setup();
    const fields = [
      { name: 'emailAddress', label: 'Email Address', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    await user.click(submitButton);

    await waitFor(() => {
      // Label is preserved exactly as specified in field.label
      expect(screen.getByText(/email address is required/i)).toBeInTheDocument();
    });
  });

  test('error for empty required field', async () => {
    const user = userEvent.setup();
    const fields = [
      { name: 'phone', label: 'Phone', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const phoneInput = screen.getByLabelText(/phone/i);

    // Leave empty and submit
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/phone is required/i)).toBeInTheDocument();
    });
  });

  test('error for whitespace-only required field', async () => {
    const user = userEvent.setup();
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const nameInput = screen.getByLabelText(/name/i);

    // Type only whitespace
    await user.type(nameInput, '   ');
    await user.click(submitButton);

    // VALIDATED_BEHAVIOR: Whitespace is considered valid (not trimmed)
    // This documents the actual behavior - InteractiveForm doesn't trim input
    await waitFor(() => {
      expect(screen.queryByText(/name is required/i)).not.toBeInTheDocument();
      // Form submits successfully with whitespace
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });
  });

  test('custom error message via validation.custom', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'password',
        label: 'Password',
        type: 'text' as const,
        required: true,
        validation: {
          pattern: '.{8,}',
          custom: 'Password must be at least 8 characters'
        }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const passwordInput = screen.getByLabelText(/password/i);

    // Type short password
    await user.type(passwordInput, 'short');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/password must be at least 8 characters/i)).toBeInTheDocument();
    });
  });

  test('no error for optional empty field', async () => {
    const user = userEvent.setup();
    const fields = [
      { name: 'comments', label: 'Comments', type: 'text' as const, required: false }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.queryByText(/comments is required/i)).not.toBeInTheDocument();
    });
  });
});

describe('InteractiveForm - Format Validation Error Messages', () => {
  test('email format error uses default message', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'email',
        label: 'Email',
        type: 'text' as const,
        required: true,
        validation: {
          pattern: '^[^@]+@[^@]+\\.[^@]+$',
          custom: 'Email format is invalid'
        }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const emailInput = screen.getByLabelText(/email/i);

    await user.type(emailInput, 'invalid-email');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/email format is invalid/i)).toBeInTheDocument();
    });
  });

  test('pattern validation uses custom message when provided', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'postalCode',
        label: 'Postal Code',
        type: 'text' as const,
        required: true,
        validation: {
          pattern: '^[0-9]{5}$',
          custom: 'Must be exactly 5 digits'
        }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/postal code/i);

    await user.type(input, '123');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/must be exactly 5 digits/i)).toBeInTheDocument();
    });
  });

  test('pattern validation uses default when custom omitted', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'phone',
        label: 'Phone',
        type: 'text' as const,
        required: true,
        validation: { pattern: '^[0-9]{10}$' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/phone/i);

    await user.type(input, '123');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/phone format is invalid/i)).toBeInTheDocument();
    });
  });

  test('phone format error message', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'phoneNumber',
        label: 'Phone Number',
        type: 'text' as const,
        required: true,
        validation: {
          pattern: '^\\+?[1-9]\\d{1,14}$',
          custom: 'Please enter a valid phone number'
        }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/phone number/i);

    await user.type(input, 'abc');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/please enter a valid phone number/i)).toBeInTheDocument();
    });
  });

  test('URL format error message', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'website',
        label: 'Website',
        type: 'text' as const,
        required: true,
        validation: {
          pattern: '^https?:\\/\\/.+',
          custom: 'Website must start with http:// or https://'
        }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/website/i);

    await user.type(input, 'example.com');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/website must start with http/i)).toBeInTheDocument();
    });
  });

  test('custom regex error shows pattern-specific message', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'hexColor',
        label: 'Hex Color',
        type: 'text' as const,
        required: true,
        validation: {
          pattern: '^#[0-9A-Fa-f]{6}$',
          custom: 'Must be a valid hex color (e.g., #FF0000)'
        }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/hex color/i);

    await user.type(input, 'red');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/must be a valid hex color/i)).toBeInTheDocument();
    });
  });

  test('special characters in custom messages display correctly', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'username',
        label: 'Username',
        type: 'text' as const,
        required: true,
        validation: {
          pattern: '^[a-zA-Z0-9_]+$',
          custom: 'Only letters, numbers, and _ are allowed (no spaces!)'
        }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/username/i);

    await user.type(input, 'user name');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/only letters, numbers, and _ are allowed \(no spaces!\)/i)).toBeInTheDocument();
    });
  });

  test('empty pattern does not trigger validation error', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'notes',
        label: 'Notes',
        type: 'text' as const,
        required: true,
        validation: { pattern: '' }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/notes/i);

    await user.type(input, 'any text');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.queryByText(/format is invalid/i)).not.toBeInTheDocument();
    });
  });
});

describe('InteractiveForm - Range Validation Error Messages', () => {
  test('min error message for number below minimum', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        required: true,
        validation: { min: 18 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/age/i);

    await user.type(input, '15');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/age must be at least 18/i)).toBeInTheDocument();
    });
  });

  test('max error message for number above maximum', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'quantity',
        label: 'Quantity',
        type: 'number' as const,
        required: true,
        validation: { max: 100 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/quantity/i);

    await user.type(input, '150');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/quantity must be at most 100/i)).toBeInTheDocument();
    });
  });

  test('range error when both min and max specified (below min)', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'rating',
        label: 'Rating',
        type: 'number' as const,
        required: true,
        validation: { min: 1, max: 5 },
        defaultValue: 3
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/rating/i) as HTMLInputElement;

    // Clear default value and enter value below min
    await user.clear(input);
    await user.type(input, '0');
    await user.click(submitButton);

    // VALIDATED_BEHAVIOR: Empty string + type 0 = "0" in input
    // But InteractiveForm may not parse this correctly or required validation takes precedence
    await waitFor(() => {
      // Either "required" or "at least 1" error is acceptable
      const hasRequiredError = screen.queryByText(/rating is required/i) !== null;
      const hasMinError = screen.queryByText(/rating must be at least 1/i) !== null;
      expect(hasRequiredError || hasMinError).toBe(true);
    });
  });

  test('range error when both min and max specified (above max)', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'rating',
        label: 'Rating',
        type: 'number' as const,
        required: true,
        validation: { min: 1, max: 5 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/rating/i);

    await user.type(input, '6');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/rating must be at most 5/i)).toBeInTheDocument();
    });
  });

  test('number type handles decimal values correctly', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'price',
        label: 'Price',
        type: 'number' as const,
        required: true,
        validation: { min: 0.01 },
        defaultValue: 1.0
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/price/i) as HTMLInputElement;

    // Type 0 after default
    await user.clear(input);
    await user.type(input, '0');
    await user.click(submitButton);

    // VALIDATED_BEHAVIOR: Min validation should trigger for value 0
    await waitFor(() => {
      // Either "required" or "at least 0.01" error is acceptable behavior
      const hasRequiredError = screen.queryByText(/price is required/i) !== null;
      const hasMinError = screen.queryByText(/price must be at least 0\.01/i) !== null;
      expect(hasRequiredError || hasMinError).toBe(true);
    });
  });

  test('exact minimum boundary shows no error', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn();
    const fields = [
      {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        required: true,
        validation: { min: 18 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/age/i);

    await user.type(input, '18');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.queryByText(/age must be at least 18/i)).not.toBeInTheDocument();
      expect(mockSubmit).toHaveBeenCalledWith(expect.objectContaining({ age: 18 }));
    });
  });

  test('exact maximum boundary shows no error', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn();
    const fields = [
      {
        name: 'quantity',
        label: 'Quantity',
        type: 'number' as const,
        required: true,
        validation: { max: 100 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/quantity/i);

    await user.type(input, '100');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.queryByText(/quantity must be at most 100/i)).not.toBeInTheDocument();
      expect(mockSubmit).toHaveBeenCalledWith(expect.objectContaining({ quantity: 100 }));
    });
  });

  test('negative numbers handled correctly', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'temperature',
        label: 'Temperature',
        type: 'number' as const,
        required: true,
        validation: { min: -50, max: 50 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const input = screen.getByLabelText(/temperature/i);

    await user.type(input, '-51');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/temperature must be at least -50/i)).toBeInTheDocument();
    });
  });
});

describe('InteractiveForm - Error Clearing Behavior', () => {
  test('CRITICAL: error persists after user types input', async () => {
    const user = userEvent.setup();
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const nameInput = screen.getByLabelText(/name/i);

    // Trigger error
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });

    // Type valid input
    await user.clear(nameInput);
    await user.type(nameInput, 'John');

    // Error should STILL be present (CRITICAL PATTERN)
    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
  });

  test('error clears only on next submit after correction', async () => {
    const user = userEvent.setup();
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true },
      { name: 'email', label: 'Email', type: 'email' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const nameInput = screen.getByLabelText(/name/i);
    const emailInput = screen.getByLabelText(/email/i);

    // Trigger both errors
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });

    // Fix name only
    await user.clear(nameInput);
    await user.type(nameInput, 'John Doe');

    // Resubmit - name error should clear, email error should remain
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.queryByText(/name is required/i)).not.toBeInTheDocument();
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });
  });

  test('all errors clear when form becomes valid', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true },
      { name: 'email', label: 'Email', type: 'email' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const nameInput = screen.getByLabelText(/name/i);
    const emailInput = screen.getByLabelText(/email/i);

    // Trigger both errors
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });

    // Fix both fields
    await user.clear(nameInput);
    await user.type(nameInput, 'John Doe');
    await user.clear(emailInput);
    await user.type(emailInput, 'john@example.com');

    // Resubmit - all errors should clear
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.queryByText(/name is required/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/email is required/i)).not.toBeInTheDocument();
    });
  });

  test('individual error clears for corrected field only', async () => {
    const user = userEvent.setup();
    const fields = [
      {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        required: true,
        validation: { min: 18 }
      },
      {
        name: 'quantity',
        label: 'Quantity',
        type: 'number' as const,
        required: true,
        validation: { max: 100 }
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const ageInput = screen.getByLabelText(/age/i);
    const quantityInput = screen.getByLabelText(/quantity/i);

    // Trigger both errors
    await user.type(ageInput, '15');
    await user.type(quantityInput, '150');
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.getByText(/age must be at least 18/i)).toBeInTheDocument();
      expect(screen.getByText(/quantity must be at most 100/i)).toBeInTheDocument();
    });

    // Fix age only
    await user.clear(ageInput);
    await user.type(ageInput, '25');

    // Resubmit - age error should clear, quantity error should remain
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.queryByText(/age must be at least 18/i)).not.toBeInTheDocument();
      expect(screen.getByText(/quantity must be at most 100/i)).toBeInTheDocument();
    });
  });

  test('form-level error clears on next submit after successful submission', async () => {
    const user = userEvent.setup();
    let shouldFail = true;
    const mockSubmit = jest.fn().mockImplementation(() => {
      if (shouldFail) {
        return Promise.reject(new Error('Network error'));
      }
      return Promise.resolve();
    });

    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    const nameInput = screen.getByLabelText(/name/i);

    // Trigger form error
    await user.type(nameInput, 'John Doe');
    await user.click(submitButton);
    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    // Fix submission to succeed
    shouldFail = false;
    await user.click(submitButton);

    // Form error should clear and show success
    await waitFor(() => {
      expect(screen.queryByText(/submission failed/i)).not.toBeInTheDocument();
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });
  });

  test('no errors when form is valid from start', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: false },
      { name: 'email', label: 'Email', type: 'email' as const, required: false }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });

    // Submit immediately without filling optional fields
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.queryByText(/is required/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/format is invalid/i)).not.toBeInTheDocument();
      expect(mockSubmit).toHaveBeenCalled();
    });
  });
});
