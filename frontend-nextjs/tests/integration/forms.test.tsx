import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InteractiveForm } from '@/components/canvas/InteractiveForm';

/**
 * Integration tests for form validation using actual InteractiveForm component
 *
 * Tests cover:
 * - Required field validation
 * - Email validation
 * - Number validation (min/max)
 * - Pattern validation
 * - Form submission
 * - Loading states
 * - Error display
 * - Success state
 */

describe('Form Validation Integration', () => {
  // Clean up after each test to prevent state leakage
  afterEach(() => {
    jest.clearAllMocks();
  });

  // Helper function to find input by name
  const getInputByName = (name: string) => {
    return document.querySelector(`input[name="${name}"]`) as HTMLInputElement ||
           document.querySelector(`select[name="${name}"]`) as HTMLSelectElement;
  };

  describe('Required field validation', () => {
    it('should show error when required field is empty', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'email',
          label: 'Email',
          type: 'email' as const,
          required: true,
        },
        {
          name: 'name',
          label: 'Name',
          type: 'text' as const,
          required: true,
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Email is required/i)).toBeInTheDocument();
        expect(screen.getByText(/Name is required/i)).toBeInTheDocument();
      });

      expect(mockSubmit).not.toHaveBeenCalled();
    });

    it('should show error then allow correction on next submit', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'email',
          label: 'Email',
          type: 'email' as const,
          required: true,
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Email is required/i)).toBeInTheDocument();
      });

      // Find the email input by type
      const emailInput = screen.getByDisplayValue('') as HTMLInputElement;
      expect(emailInput.type).toBe('email');

      // Type valid email
      await userEvent.type(emailInput, 'test@example.com');

      // Error still exists until next submit
      expect(screen.getByText(/Email is required/i)).toBeInTheDocument();

      // Submit again - error should clear and form should submit
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText(/Email is required/i)).not.toBeInTheDocument();
      });

      expect(mockSubmit).toHaveBeenCalledWith({ email: 'test@example.com' });
    });

    it('should not show error for non-required empty field', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'comment',
          label: 'Comment',
          type: 'text' as const,
          required: false,
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText(/Comment is required/i)).not.toBeInTheDocument();
      });

      expect(mockSubmit).toHaveBeenCalled();
    });
  });

  describe('Email validation', () => {
    it('should show error for invalid email format', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'email',
          label: 'Email',
          type: 'email' as const,
          required: true,
          validation: {
            pattern: '^[^@]+@[^@]+\\.[^@]+$',
            custom: 'Invalid email format',
          },
        },
      ];

      const { container } = render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      // Find email input and type invalid email
      const emailInput = container.querySelector('input[type="email"]') as HTMLInputElement;
      await userEvent.type(emailInput, 'invalid-email');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      // Check that some error is displayed (validation failed)
      await waitFor(() => {
        const errorElements = container.querySelectorAll('.text-red-500');
        expect(errorElements.length).toBeGreaterThan(0);
      });

      expect(mockSubmit).not.toHaveBeenCalled();
    });

    it('should accept valid email format', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'email',
          label: 'Email',
          type: 'email' as const,
          required: true,
          validation: {
            pattern: '^[^@]+@[^@]+\\.[^@]+$',
          },
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const emailInput = screen.getByDisplayValue('') as HTMLInputElement;
      await userEvent.type(emailInput, 'test@example.com');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText(/format is invalid/i)).not.toBeInTheDocument();
      });

      expect(mockSubmit).toHaveBeenCalledWith({ email: 'test@example.com' });
    });
  });

  describe('Number validation', () => {
    it('should show error for number below minimum', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'age',
          label: 'Age',
          type: 'number' as const,
          required: true,
          validation: {
            min: 18,
          },
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const ageInput = screen.getByDisplayValue('') as HTMLInputElement;
      await userEvent.type(ageInput, '15');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Age must be at least 18/i)).toBeInTheDocument();
      });

      expect(mockSubmit).not.toHaveBeenCalled();
    });

    it('should show error for number above maximum', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'quantity',
          label: 'Quantity',
          type: 'number' as const,
          required: true,
          validation: {
            max: 100,
          },
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const quantityInput = screen.getByDisplayValue('') as HTMLInputElement;
      await userEvent.type(quantityInput, '150');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Quantity must be at most 100/i)).toBeInTheDocument();
      });

      expect(mockSubmit).not.toHaveBeenCalled();
    });

    it('should accept number within range', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'age',
          label: 'Age',
          type: 'number' as const,
          required: true,
          validation: {
            min: 18,
            max: 100,
          },
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const ageInput = screen.getByDisplayValue('') as HTMLInputElement;
      await userEvent.type(ageInput, '25');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText(/must be at least|must be at most/i)).not.toBeInTheDocument();
      });

      expect(mockSubmit).toHaveBeenCalledWith({ age: 25 });
    });
  });

  describe('Pattern validation', () => {
    it('should validate custom pattern', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'phone',
          label: 'Phone',
          type: 'text' as const,
          required: true,
          validation: {
            pattern: '^\\d{3}-\\d{3}-\\d{4}$',
            custom: 'Phone must be in format XXX-XXX-XXXX',
          },
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const phoneInput = screen.getByDisplayValue('') as HTMLInputElement;
      await userEvent.type(phoneInput, 'invalid');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Phone must be in format XXX-XXX-XXXX/i)).toBeInTheDocument();
      });

      expect(mockSubmit).not.toHaveBeenCalled();
    });

    it('should accept valid pattern match', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'phone',
          label: 'Phone',
          type: 'text' as const,
          required: true,
          validation: {
            pattern: '^\\d{3}-\\d{3}-\\d{4}$',
          },
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const phoneInput = screen.getByDisplayValue('') as HTMLInputElement;
      await userEvent.type(phoneInput, '555-123-4567');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText(/format is invalid/i)).not.toBeInTheDocument();
      });

      expect(mockSubmit).toHaveBeenCalledWith({ phone: '555-123-4567' });
    });
  });

  describe('Form submission', () => {
    it('should submit form data when all validations pass', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'name',
          label: 'Name',
          type: 'text' as const,
          required: true,
        },
        {
          name: 'email',
          label: 'Email',
          type: 'email' as const,
          required: true,
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const inputs = screen.getAllByDisplayValue('') as HTMLInputElement[];
      const nameInput = inputs.find(i => i.type === 'text')!;
      const emailInput = inputs.find(i => i.type === 'email')!;

      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'john@example.com');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalledWith({
          name: 'John Doe',
          email: 'john@example.com',
        });
      });
    });

    it('should show loading state during submission', async () => {
      const mockSubmit = jest.fn(() => new Promise(resolve => setTimeout(resolve, 1000)));
      const fields = [
        {
          name: 'name',
          label: 'Name',
          type: 'text' as const,
          required: true,
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const nameInput = screen.getByDisplayValue('') as HTMLInputElement;
      await userEvent.type(nameInput, 'John Doe');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      // Check button is disabled and shows loading text
      await waitFor(() => {
        expect(submitButton).toBeDisabled();
        expect(screen.getByText(/Submitting.../i)).toBeInTheDocument();
      });

      // Wait for submission to complete
      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalled();
      }, { timeout: 2000 });
    });

    it('should show success message after successful submission', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'name',
          label: 'Name',
          type: 'text' as const,
          required: true,
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const nameInput = screen.getByDisplayValue('') as HTMLInputElement;
      await userEvent.type(nameInput, 'John Doe');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Submitted successfully/i)).toBeInTheDocument();
      });
    });
  });

  describe('Error state display', () => {
    it('should show server error message', async () => {
      const mockSubmit = jest.fn(() => Promise.reject(new Error('Server error')));
      const fields = [
        {
          name: 'name',
          label: 'Name',
          type: 'text' as const,
          required: true,
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const nameInput = screen.getByDisplayValue('') as HTMLInputElement;
      await userEvent.type(nameInput, 'John Doe');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Submission failed/i)).toBeInTheDocument();
      });
    });

    it('should clear errors after user corrects input and resubmits', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'email',
          label: 'Email',
          type: 'email' as const,
          required: true,
          validation: {
            pattern: '^[^@]+@[^@]+\\.[^@]+$',
          },
        },
      ];

      const { container } = render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const emailInput = container.querySelector('input[type="email"]') as HTMLInputElement;

      // Submit with invalid email
      await userEvent.type(emailInput, 'invalid');
      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      // Wait for error to appear
      await waitFor(() => {
        const errorElements = container.querySelectorAll('.text-red-500');
        expect(errorElements.length).toBeGreaterThan(0);
      });

      // Correct the email
      await userEvent.clear(emailInput);
      await userEvent.type(emailInput, 'test@example.com');

      // Error still exists until resubmit
      let errorElements = container.querySelectorAll('.text-red-500');
      expect(errorElements.length).toBeGreaterThan(0);

      // Resubmit - error should clear and form should submit
      fireEvent.click(submitButton);

      await waitFor(() => {
        errorElements = container.querySelectorAll('.text-red-500');
        expect(errorElements.length).toBe(0);
      });

      expect(mockSubmit).toHaveBeenCalledWith({ email: 'test@example.com' });
    });
  });

  describe('Select field', () => {
    it('should handle select field validation', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'country',
          label: 'Country',
          type: 'select' as const,
          required: true,
          options: [
            { value: 'us', label: 'United States' },
            { value: 'uk', label: 'United Kingdom' },
            { value: 'ca', label: 'Canada' },
          ],
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Country is required/i)).toBeInTheDocument();
      });

      expect(mockSubmit).not.toHaveBeenCalled();
    });

    it('should submit selected value', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'country',
          label: 'Country',
          type: 'select' as const,
          required: true,
          options: [
            { value: 'us', label: 'United States' },
            { value: 'uk', label: 'United Kingdom' },
          ],
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const select = screen.getByDisplayValue('Select...') as HTMLSelectElement;
      await userEvent.selectOptions(select, 'us');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalledWith({ country: 'us' });
      });
    });
  });

  describe('Checkbox field', () => {
    it('should handle checkbox field', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'agree',
          label: 'I agree to terms',
          type: 'checkbox' as const,
          required: true,
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/I agree to terms is required/i)).toBeInTheDocument();
      });

      const checkbox = screen.getByRole('checkbox');
      await userEvent.click(checkbox);
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalledWith({ agree: true });
      });
    });

    it('should handle unchecked checkbox when not required', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'newsletter',
          label: 'Subscribe to newsletter',
          type: 'checkbox' as const,
          required: false,
        },
      ];

      const { container } = render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      // Checkbox should be unchecked by default
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).not.toBeChecked();

      const submitButton = screen.getByRole('button', { name: /submit/i });

      // Submit immediately with unchecked checkbox
      fireEvent.click(submitButton);

      // Wait for submission to complete
      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalled();
      });

      // The component uses empty string for unchecked checkbox initially
      expect(mockSubmit).toHaveBeenCalledWith({ newsletter: '' });
    });
  });

  describe('Default values', () => {
    it('should populate form with default values', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'name',
          label: 'Name',
          type: 'text' as const,
          defaultValue: 'John Doe',
        },
        {
          name: 'email',
          label: 'Email',
          type: 'email' as const,
          defaultValue: 'john@example.com',
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      const nameInput = screen.getByDisplayValue('John Doe') as HTMLInputElement;
      const emailInput = screen.getByDisplayValue('john@example.com') as HTMLInputElement;

      expect(nameInput).toBeInTheDocument();
      expect(emailInput).toBeInTheDocument();

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalledWith({
          name: 'John Doe',
          email: 'john@example.com',
        });
      });
    });
  });

  describe('Multiple field types', () => {
    it('should validate mixed field types correctly', async () => {
      const mockSubmit = jest.fn().mockResolvedValue({ success: true });
      const fields = [
        {
          name: 'name',
          label: 'Name',
          type: 'text' as const,
          required: true,
        },
        {
          name: 'email',
          label: 'Email',
          type: 'email' as const,
          required: true,
          validation: {
            pattern: '^[^@]+@[^@]+\\.[^@]+$',
          },
        },
        {
          name: 'age',
          label: 'Age',
          type: 'number' as const,
          required: true,
          validation: {
            min: 18,
            max: 100,
          },
        },
        {
          name: 'country',
          label: 'Country',
          type: 'select' as const,
          required: true,
          options: [
            { value: 'us', label: 'United States' },
            { value: 'uk', label: 'United Kingdom' },
          ],
        },
      ];

      render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

      // Submit with empty form
      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Name is required/i)).toBeInTheDocument();
        expect(screen.getByText(/Email is required/i)).toBeInTheDocument();
        expect(screen.getByText(/Age is required/i)).toBeInTheDocument();
        expect(screen.getByText(/Country is required/i)).toBeInTheDocument();
      });

      expect(mockSubmit).not.toHaveBeenCalled();

      // Get fresh form elements after validation errors
      const inputs = screen.getAllByDisplayValue('') as HTMLInputElement[];
      const nameInput = inputs.find(i => i.type === 'text')!;
      const emailInput = inputs.find(i => i.type === 'email')!;
      const ageInput = inputs.find(i => i.type === 'number')!;
      const countrySelect = screen.getByDisplayValue('Select...') as HTMLSelectElement;

      // Fill form correctly
      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'john@example.com');
      await userEvent.type(ageInput, '25');
      await userEvent.selectOptions(countrySelect, 'us');

      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalledWith({
          name: 'John Doe',
          email: 'john@example.com',
          age: 25,
          country: 'us',
        });
      });
    });
  });
});
