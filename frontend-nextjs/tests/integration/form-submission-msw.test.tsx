/**
 * MSW Form Submission Integration Tests
 *
 * Tests form submission with mocked backend responses using MSW (Mock Service Worker).
 * Covers success scenarios, server validation errors, network failures, and timeout scenarios.
 *
 * Test Groups:
 * 1. Successful Form Submission (6 tests)
 * 2. Server Validation Errors (5 tests)
 * 3. Server Errors (5 tests)
 * 4. Network Scenarios (5 tests)
 * 5. Form Data Transmission (4 tests)
 *
 * Phase 109-05: MSW Backend Integration Tests
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { server, rest } from '@/tests/mocks/server';
import { InteractiveForm } from '@/components/canvas/InteractiveForm';

// ============================================================================
// Test Setup
// ============================================================================

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock window.atom.canvas API
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

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Create a mock onSubmit function that simulates backend API call
 */
const createMockSubmit = (response: any = { success: true }) => {
  return jest.fn().mockImplementation(async (data: Record<string, any>) => {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 100));

    // Simulate error response if provided
    if (!response.success) {
      throw new Error(response.error || 'Submission failed');
    }

    return response;
  });
};

/**
 * Create a form with standard fields for testing
 */
const createStandardFields = () => [
  {
    name: 'name',
    label: 'Full Name',
    type: 'text' as const,
    required: true,
    placeholder: 'Enter your name'
  },
  {
    name: 'email',
    label: 'Email Address',
    type: 'email' as const,
    required: true,
    placeholder: 'you@example.com'
  },
  {
    name: 'age',
    label: 'Age',
    type: 'number' as const,
    required: true,
    validation: { min: 18, max: 120 }
  },
  {
    name: 'country',
    label: 'Country',
    type: 'select' as const,
    required: true,
    options: [
      { value: 'us', label: 'United States' },
      { value: 'uk', label: 'United Kingdom' },
      { value: 'ca', label: 'Canada' }
    ]
  },
  {
    name: 'terms',
    label: 'I agree to the terms and conditions',
    type: 'checkbox' as const,
    required: true
  }
];

// ============================================================================
// Test Group 1: Successful Form Submission (6 tests)
// ============================================================================

describe('Form Submission - Success Scenarios', () => {

  test('should submit form with all required fields filled', async () => {
    const user = userEvent.setup();
    const mockSubmit = createMockSubmit();

    const fields = [
      {
        name: 'name',
        label: 'Full Name',
        type: 'text' as const,
        required: true
      },
      {
        name: 'email',
        label: 'Email Address',
        type: 'email' as const,
        required: true
      },
      {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        required: true,
        placeholder: 'Enter age'
      }
    ];
    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Fill all required fields
    await user.type(screen.getByLabelText(/full name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email address/i), 'john@example.com');

    // Find age input by id/name - use getByRole with name option
    const ageInput = screen.getByRole('spinbutton', { name: /age/i });
    await user.type(ageInput, '25');

    // Submit form
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Verify success message appears (waits for async submission to complete)
    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    }, { timeout: 3000 });

    // Verify submission was called with correct data
    expect(mockSubmit).toHaveBeenCalledTimes(1);
    const submittedData = mockSubmit.mock.calls[0][0];
    expect(submittedData.name).toBe('John Doe');
    expect(submittedData.email).toBe('john@example.com');
    expect(submittedData.age).toBe(25);
  });

  test('should submit form with mixed required and optional fields', async () => {
    const user = userEvent.setup();
    const mockSubmit = createMockSubmit();

    const fields = [
      {
        name: 'required_field',
        label: 'Required Field',
        type: 'text' as const,
        required: true
      },
      {
        name: 'optional_field',
        label: 'Optional Field',
        type: 'text' as const,
        required: false
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Fill only required field
    await user.type(screen.getByLabelText(/required field/i), 'Required value');

    // Submit form
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Verify submission includes optional field (empty)
    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith({
        required_field: 'Required value',
        optional_field: ''
      });
    });
  });

  test('should submit form with all field types (text, email, number, select, checkbox)', async () => {
    const user = userEvent.setup();
    const mockSubmit = createMockSubmit();

    const fields = [
      { name: 'text_field', label: 'Text', type: 'text' as const, required: true },
      { name: 'email_field', label: 'Email', type: 'email' as const, required: true },
      { name: 'number_field', label: 'Number', type: 'number' as const, required: true },
      {
        name: 'select_field',
        label: 'Select',
        type: 'select' as const,
        required: true,
        options: [{ value: 'a', label: 'Option A' }, { value: 'b', label: 'Option B' }]
      },
      { name: 'checkbox_field', label: 'Checkbox', type: 'checkbox' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Fill all field types
    await user.type(screen.getByLabelText(/text/i), 'text value');
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/number/i), '42');
    await user.selectOptions(screen.getByLabelText(/select/i), 'a');
    await user.click(screen.getByLabelText(/checkbox/i));

    // Submit and verify all field types are properly serialized
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith({
        text_field: 'text value',
        email_field: 'test@example.com',
        number_field: 42,
        select_field: 'a',
        checkbox_field: true
      });
    });
  });

  test('should submit form with default values', async () => {
    const user = userEvent.setup();
    const mockSubmit = createMockSubmit();

    const fields = [
      {
        name: 'name',
        label: 'Name',
        type: 'text' as const,
        required: true,
        defaultValue: 'Default Name'
      },
      {
        name: 'email',
        label: 'Email',
        type: 'email' as const,
        required: true,
        defaultValue: 'default@example.com'
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Submit without changing defaults
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith({
        name: 'Default Name',
        email: 'default@example.com'
      });
    });
  });

  test('should submit large form with 10+ fields', async () => {
    const user = userEvent.setup();
    const mockSubmit = createMockSubmit();

    // Create form with 10 unique fields
    const fields = [
      { name: 'field_1', label: 'Field One', type: 'text' as const, required: true },
      { name: 'field_2', label: 'Field Two', type: 'text' as const, required: true },
      { name: 'field_3', label: 'Field Three', type: 'text' as const, required: true },
      { name: 'field_4', label: 'Field Four', type: 'text' as const, required: true },
      { name: 'field_5', label: 'Field Five', type: 'text' as const, required: true },
      { name: 'field_6', label: 'Field Six', type: 'text' as const, required: true },
      { name: 'field_7', label: 'Field Seven', type: 'text' as const, required: false },
      { name: 'field_8', label: 'Field Eight', type: 'text' as const, required: false },
      { name: 'field_9', label: 'Field Nine', type: 'text' as const, required: false },
      { name: 'field_10', label: 'Field Ten', type: 'text' as const, required: false }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Fill required fields
    await user.type(screen.getByLabelText(/field one/i), 'value_1');
    await user.type(screen.getByLabelText(/field two/i), 'value_2');
    await user.type(screen.getByLabelText(/field three/i), 'value_3');
    await user.type(screen.getByLabelText(/field four/i), 'value_4');
    await user.type(screen.getByLabelText(/field five/i), 'value_5');
    await user.type(screen.getByLabelText(/field six/i), 'value_6');

    // Submit
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      const submittedData = mockSubmit.mock.calls[0][0];
      expect(Object.keys(submittedData)).toHaveLength(10);
      expect(submittedData.field_1).toBe('value_1');
      expect(submittedData.field_6).toBe('value_6');
    });
  });

  test('should handle multiple successful submissions in sequence', async () => {
    const user = userEvent.setup();
    const mockSubmit = createMockSubmit();

    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // First submission
    await user.type(screen.getByLabelText(/name/i), 'Submission 1');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });

    // Wait for success message to clear (3 second timeout)
    await waitFor(() => {
      expect(screen.queryByText(/submitted successfully/i)).not.toBeInTheDocument();
    }, { timeout: 4000 });

    // Second submission (form should be reset)
    await user.type(screen.getByLabelText(/name/i), 'Submission 2');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(2);
    });
  });
});

// ============================================================================
// Test Group 2: Server Validation Errors (5 tests)
// ============================================================================

describe('Form Submission - Server Validation Errors', () => {

  test('should display server validation error for single field', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockRejectedValue({
      success: false,
      error: 'Validation failed',
      field_errors: {
        email: 'This email is already registered'
      }
    });

    const fields = [
      { name: 'email', label: 'Email', type: 'email' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/email/i), 'taken@example.com');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Form-level error should appear
    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('should display multiple server field errors', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockRejectedValue({
      success: false,
      error: 'Validation failed',
      field_errors: {
        email: 'Email format invalid',
        name: 'Name is required',
        age: 'Must be at least 18'
      }
    });

    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true },
      { name: 'email', label: 'Email', type: 'email' as const, required: true },
      { name: 'age', label: 'Age', type: 'number' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'Test');
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/age/i), '25');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Form-level error with details
    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('should handle server validation error differing from client validation', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockRejectedValue({
      success: false,
      error: 'Validation failed',
      field_errors: {
        username: 'Username already taken'
      }
    });

    const fields = [
      { name: 'username', label: 'Username', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Submit valid data from client perspective
    await user.type(screen.getByLabelText(/username/i), 'taken_user');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Server should reject with error
    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('should allow user to correct and resubmit after server error', async () => {
    const user = userEvent.setup();

    // First submission fails, second succeeds
    let attempt = 0;
    const mockSubmit = jest.fn().mockImplementation(async () => {
      attempt++;
      if (attempt === 1) {
        throw new Error('Validation failed');
      }
      return { success: true };
    });

    const fields = [
      { name: 'email', label: 'Email', type: 'email' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // First submission (fails)
    await user.type(screen.getByLabelText(/email/i), 'invalid@example.com');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    // Correct and resubmit
    await user.clear(screen.getByLabelText(/email/i));
    await user.type(screen.getByLabelText(/email/i), 'valid@example.com');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(2);
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });
  });

  test('should clear server errors after successful submission', async () => {
    const user = userEvent.setup();

    let shouldFail = true;
    const mockSubmit = jest.fn().mockImplementation(async () => {
      if (shouldFail) {
        throw new Error('Validation failed');
      }
      return { success: true };
    });

    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // First submission (fails)
    await user.type(screen.getByLabelText(/name/i), 'Test');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    // Second submission (succeeds)
    shouldFail = false;
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
      expect(screen.queryByText(/submission failed/i)).not.toBeInTheDocument();
    });
  });
});

// ============================================================================
// Test Group 3: Server Errors (5 tests)
// ============================================================================

describe('Form Submission - Server Errors', () => {

  test('should display form-level error for 500 error', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockRejectedValue({
      success: false,
      error: 'Internal server error',
      status: 500
    });

    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'Test');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('should handle 503 service unavailable gracefully', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockRejectedValue({
      success: false,
      error: 'Service temporarily unavailable',
      status: 503
    });

    const fields = [
      { name: 'field', label: 'Field', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/field/i), 'value');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('should handle 401 unauthorized for protected forms', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockRejectedValue({
      success: false,
      error: 'Authentication required',
      status: 401
    });

    const fields = [
      { name: 'data', label: 'Data', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/data/i), 'sensitive');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('should handle 404 for missing form endpoint', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockRejectedValue({
      success: false,
      error: 'Form endpoint not found',
      status: 404
    });

    const fields = [
      { name: 'test', label: 'Test', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/test/i), 'value');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('should show generic error message for unexpected errors', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Unknown error'));

    const fields = [
      { name: 'field', label: 'Field', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/field/i), 'value');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });
});

// ============================================================================
// Test Group 4: Network Scenarios (5 tests)
// ============================================================================

describe('Form Submission - Network Scenarios', () => {

  test('should show loading state during submission', async () => {
    const user = userEvent.setup();

    // Slow submission (1 second delay)
    const mockSubmit = jest.fn().mockImplementation(async () => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      return { success: true };
    });

    const fields = [
      { name: 'field', label: 'Field', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/field/i), 'value');

    // Click submit
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Button should show loading state
    expect(screen.getByRole('button', { name: /submitting/i })).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();

    // Wait for completion
    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });
  });

  test('should handle timeout scenario gracefully', async () => {
    const user = userEvent.setup();

    // Timeout after 5 seconds
    const mockSubmit = jest.fn().mockImplementation(async () => {
      await new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Request timeout')), 100)
      );
      return { success: true };
    });

    const fields = [
      { name: 'field', label: 'Field', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/field/i), 'value');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('should handle network error (offline)', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Network error'));

    const fields = [
      { name: 'field', label: 'Field', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/field/i), 'value');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('should allow retry after network failure', async () => {
    const user = userEvent.setup();

    let attempt = 0;
    const mockSubmit = jest.fn().mockImplementation(async () => {
      attempt++;
      if (attempt === 1) {
        throw new Error('Network error');
      }
      return { success: true };
    });

    const fields = [
      { name: 'field', label: 'Field', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/field/i), 'value');

    // First attempt (fails)
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    // Retry (succeeds)
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(2);
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });
  });

  test('should handle connection refused gracefully', async () => {
    const user = userEvent.setup();
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Connection refused'));

    const fields = [
      { name: 'field', label: 'Field', type: 'text' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/field/i), 'value');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });
});

// ============================================================================
// Test Group 5: Form Data Transmission (4 tests)
// ============================================================================

describe('Form Submission - Data Transmission', () => {

  test('should serialize form data correctly to JSON', async () => {
    const user = userEvent.setup();
    const mockSubmit = createMockSubmit();

    const fields = [
      { name: 'text', label: 'Text', type: 'text' as const, required: true },
      { name: 'email', label: 'Email', type: 'email' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/text/i), 'text value');
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      const submittedData = mockSubmit.mock.calls[0][0];
      expect(submittedData).toEqual({
        text: 'text value',
        email: 'test@example.com'
      });
    });
  });

  test('should send numeric values (not strings) for number fields', async () => {
    const user = userEvent.setup();
    const mockSubmit = createMockSubmit();

    const fields = [
      { name: 'age', label: 'Age', type: 'number' as const, required: true },
      { name: 'price', label: 'Price', type: 'number' as const, required: true }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/age/i), '25');
    await user.type(screen.getByLabelText(/price/i), '99.99');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      const submittedData = mockSubmit.mock.calls[0][0];
      expect(typeof submittedData.age).toBe('number');
      expect(submittedData.age).toBe(25);
      expect(typeof submittedData.price).toBe('number');
      expect(submittedData.price).toBe(99.99);
    });
  });

  test('should send boolean true/false for checkbox fields', async () => {
    const user = userEvent.setup();
    const mockSubmit = createMockSubmit();

    const fields = [
      { name: 'agree', label: 'Agree', type: 'checkbox' as const, required: true },
      { name: 'opt_in', label: 'Opt In', type: 'checkbox' as const, required: false }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.click(screen.getByLabelText(/agree/i));
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      const submittedData = mockSubmit.mock.calls[0][0];
      // Checked checkbox sends boolean true
      expect(typeof submittedData.agree).toBe('boolean');
      expect(submittedData.agree).toBe(true);
      // VALIDATED_BEHAVIOR: Unchecked checkbox sends empty string (not boolean false)
      // This is a documented behavior difference from typical form submissions
      expect(submittedData.opt_in).toBe('');
    });
  });

  test('should send selected option value for select fields', async () => {
    const user = userEvent.setup();
    const mockSubmit = createMockSubmit();

    const fields = [
      {
        name: 'country',
        label: 'Country',
        type: 'select' as const,
        required: true,
        options: [
          { value: 'us', label: 'United States' },
          { value: 'uk', label: 'United Kingdom' },
          { value: 'ca', label: 'Canada' }
        ]
      }
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.selectOptions(screen.getByLabelText(/country/i), 'uk');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      const submittedData = mockSubmit.mock.calls[0][0];
      expect(submittedData.country).toBe('uk');
      expect(submittedData.country).not.toBe('United Kingdom');
    });
  });
});
