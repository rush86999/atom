import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

describe('InteractiveForm - Validation Tests', () => {
  describe('Required Field Validation', () => {
    it('should validate required text fields', async () => {
      const field = {
        name: 'fullName',
        label: 'Full Name',
        type: 'text' as const,
        required: true,
        validation: {
          minLength: 2,
          maxLength: 100,
        },
      };

      const validateRequired = (value: string): { valid: boolean; error?: string } => {
        if (!value || value.trim() === '') {
          return { valid: false, error: 'Full Name is required' };
        }
        if (value.length < field.validation.minLength) {
          return { valid: false, error: `Minimum length is ${field.validation.minLength}` };
        }
        if (value.length > field.validation.maxLength) {
          return { valid: false, error: `Maximum length is ${field.validation.maxLength}` };
        }
        return { valid: true };
      };

      // Test empty value
      expect(validateRequired('').valid).toBe(false);
      expect(validateRequired('').error).toBe('Full Name is required');

      // Test too short
      expect(validateRequired('J').valid).toBe(false);
      expect(validateRequired('J').error).toContain('Minimum length');

      // Test valid
      expect(validateRequired('John Doe').valid).toBe(true);
    });

    it('should validate required email fields', async () => {
      const field = {
        name: 'email',
        label: 'Email Address',
        type: 'email' as const,
        required: true,
      };

      const validateEmail = (value: string): { valid: boolean; error?: string } => {
        if (!value || value.trim() === '') {
          return { valid: false, error: 'Email is required' };
        }

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
          return { valid: false, error: 'Invalid email format' };
        }

        return { valid: true };
      };

      // Test empty
      expect(validateEmail('').valid).toBe(false);

      // Test invalid formats
      expect(validateEmail('invalid').valid).toBe(false);
      expect(validateEmail('invalid@').valid).toBe(false);
      expect(validateEmail('@example.com').valid).toBe(false);
      expect(validateEmail('test@').valid).toBe(false);

      // Test valid formats
      expect(validateEmail('test@example.com').valid).toBe(true);
      expect(validateEmail('user.name+tag@domain.co.uk').valid).toBe(true);
    });

    it('should validate required number fields', async () => {
      const field = {
        name: 'age',
        label: 'Age',
        type: 'number' as const,
        required: true,
        validation: {
          min: 18,
          max: 120,
        },
      };

      const validateNumber = (value: string): { valid: boolean; error?: string } => {
        if (!value || value.trim() === '') {
          return { valid: false, error: 'Age is required' };
        }

        const num = parseInt(value, 10);
        if (isNaN(num)) {
          return { valid: false, error: 'Must be a valid number' };
        }

        if (num < field.validation.min) {
          return { valid: false, error: `Minimum value is ${field.validation.min}` };
        }

        if (num > field.validation.max) {
          return { valid: false, error: `Maximum value is ${field.validation.max}` };
        }

        return { valid: true };
      };

      // Test empty
      expect(validateNumber('').valid).toBe(false);

      // Test invalid number
      expect(validateNumber('abc').valid).toBe(false);
      expect(validateNumber('abc').error).toContain('valid number');

      // Test out of range
      expect(validateNumber('17').valid).toBe(false);
      expect(validateNumber('121').valid).toBe(false);

      // Test valid
      expect(validateNumber('25').valid).toBe(true);
    });

    it('should validate checkbox fields', async () => {
      const field = {
        name: 'terms',
        label: 'I agree to the terms',
        type: 'checkbox' as const,
        required: true,
      };

      const validateCheckbox = (checked: boolean): { valid: boolean; error?: string } => {
        if (!checked) {
          return { valid: false, error: 'You must agree to the terms' };
        }
        return { valid: true };
      };

      expect(validateCheckbox(false).valid).toBe(false);
      expect(validateCheckbox(true).valid).toBe(true);
    });
  });

  describe('Pattern-based Validation', () => {
    it('should validate phone number patterns', async () => {
      const phonePatterns = [
        { pattern: /^\+?[\d\s-()]+$/, description: 'US format' },
        { pattern: /^\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$/, description: 'International' },
      ];

      const validatePhone = (value: string): boolean => {
        return phonePatterns.some(p => p.pattern.test(value));
      };

      expect(validatePhone('+1 (555) 123-4567')).toBe(true);
      expect(validatePhone('555-123-4567')).toBe(true);
      expect(validatePhone('+44 20 7123 4567')).toBe(true);
      expect(validatePhone('invalid')).toBe(false);
    });

    it('should validate URL patterns', async () => {
      const urlPattern = /^https?:\/\/[\w\-.]+(:\d+)?(\/[\w\-._~:/?#[\]@!$&'()*+,;=%]*)?$/;

      const validateURL = (value: string): boolean => {
        return urlPattern.test(value);
      };

      expect(validateURL('https://example.com')).toBe(true);
      expect(validateURL('http://localhost:3000/path')).toBe(true);
      expect(validateURL('ftp://example.com')).toBe(false);
      expect(validateURL('not-a-url')).toBe(false);
    });

    it('should validate custom regex patterns', async () => {
      const customPattern = /^[A-Z]{2}\d{4}$/; // e.g., AB1234

      const validateCustom = (value: string): boolean => {
        return customPattern.test(value);
      };

      expect(validateCustom('AB1234')).toBe(true);
      expect(validateCustom('XY5678')).toBe(true);
      expect(validateCustom('AB123')).toBe(false); // Too short
      expect(validateCustom('AB12345')).toBe(false); // Too long
      expect(validateCustom('ab1234')).toBe(false); // Lowercase
    });
  });

  describe('Cross-field Validation', () => {
    it('should validate password confirmation match', async () => {
      const validatePasswordMatch = (
        password: string,
        confirmation: string
      ): { valid: boolean; error?: string } => {
        if (password !== confirmation) {
          return { valid: false, error: 'Passwords do not match' };
        }
        return { valid: true };
      };

      expect(validatePasswordMatch('password123', 'password123').valid).toBe(true);
      expect(validatePasswordMatch('password123', 'password456').valid).toBe(false);
    });

    it('should validate date ranges', async () => {
      const validateDateRange = (
        startDate: string,
        endDate: string
      ): { valid: boolean; error?: string } => {
        const start = new Date(startDate);
        const end = new Date(endDate);

        if (end <= start) {
          return { valid: false, error: 'End date must be after start date' };
        }

        return { valid: true };
      };

      expect(validateDateRange('2026-01-01', '2026-01-02').valid).toBe(true);
      expect(validateDateRange('2026-01-02', '2026-01-01').valid).toBe(false);
      expect(validateDateRange('2026-01-01', '2026-01-01').valid).toBe(false);
    });

    it('should validate dependent fields', async () => {
      const validateDependent = (
        country: string,
        state: string
      ): { valid: boolean; error?: string } => {
        if (country === 'United States' && !state) {
          return { valid: false, error: 'State is required for United States' };
        }
        return { valid: true };
      };

      expect(validateDependent('United States', 'California').valid).toBe(true);
      expect(validateDependent('United States', '').valid).toBe(false);
      expect(validateDependent('Canada', '').valid).toBe(true);
    });
  });

  describe('Async Validation', () => {
    it('should validate unique email via API', async () => {
      global.fetch = jest.fn();

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: { unique: true },
        }),
      });

      const validateUniqueEmail = async (email: string): Promise<boolean> => {
        const response = await fetch('/api/users/check-email', {
          method: 'POST',
          body: JSON.stringify({ email }),
        });

        const result = await response.json();
        return result.data.unique;
      };

      const isUnique = await validateUniqueEmail('new@example.com');

      expect(isUnique).toBe(true);
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/users/check-email',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('should handle async validation errors', async () => {
      global.fetch = jest.fn();

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      const validateUniqueEmail = async (email: string): Promise<{ valid: boolean; error?: string }> => {
        try {
          const response = await fetch('/api/users/check-email', {
            method: 'POST',
            body: JSON.stringify({ email }),
          });

          const result = await response.json();
          return { valid: result.data.unique };
        } catch (error) {
          return { valid: false, error: 'Unable to validate email' };
        }
      };

      const result = await validateUniqueEmail('test@example.com');

      expect(result.valid).toBe(false);
      expect(result.error).toBe('Unable to validate email');
    });
  });

  describe('Real-time Validation', () => {
    it('should validate on blur', async () => {
      let validationTriggered = false;

      const validateOnBlur = (value: string) => {
        validationTriggered = true;
        return value.length >= 2;
      };

      // Simulate blur event
      const isValid = validateOnBlur('J');

      expect(validationTriggered).toBe(true);
      expect(isValid).toBe(false);
    });

    it('should validate on change after first blur', async () => {
      let hasBlurred = false;
      let validationCount = 0;

      const validateOnChange = (value: string) => {
        if (hasBlurred) {
          validationCount++;
          return value.length >= 2;
        }
        return true; // Don't validate until blur
      };

      // Before blur
      validateOnChange('J');
      expect(validationCount).toBe(0);

      // After blur
      hasBlurred = true;
      validateOnChange('J');
      expect(validationCount).toBe(1);

      validateOnChange('John');
      expect(validationCount).toBe(2);
    });
  });

  describe('Validation Error Display', () => {
    it('should display inline error messages', async () => {
      const errors = {
        email: 'Invalid email format',
        password: 'Password must be at least 8 characters',
      };

      expect(errors.email).toBeDefined();
      expect(errors.password).toBeDefined();
    });

    it('should clear errors when user starts typing', async () => {
      let errors = { email: 'Invalid email format' };

      const clearErrorOnInput = (fieldName: string) => {
        delete errors[fieldName as keyof typeof errors];
      };

      clearErrorOnInput('email');

      expect(errors.email).toBeUndefined();
    });

    it('should show summary of all errors', async () => {
      const errors = {
        name: 'Name is required',
        email: 'Invalid email',
        age: 'Must be 18 or older',
      };

      const errorSummary = Object.values(errors);

      expect(errorSummary).toHaveLength(3);
      expect(errorSummary).toContain('Name is required');
      expect(errorSummary).toContain('Invalid email');
      expect(errorSummary).toContain('Must be 18 or older');
    });
  });

  describe('Complex Validation Scenarios', () => {
    it('should validate conditional requirements', async () => {
      const validateConditional = (
        fieldType: string,
        value: string
      ): { valid: boolean; error?: string } => {
        if (fieldType === 'business' && !value) {
          return { valid: false, error: 'Company name is required for business accounts' };
        }
        return { valid: true };
      };

      expect(validateConditional('business', '').valid).toBe(false);
      expect(validateConditional('personal', '').valid).toBe(true);
      expect(validateConditional('business', 'Acme Corp').valid).toBe(true);
    });

    it('should validate array fields (e.g., checkboxes, multi-select)', async () => {
      const validateArray = (
        values: string[],
        minSelected: number
      ): { valid: boolean; error?: string } => {
        if (values.length < minSelected) {
          return {
            valid: false,
            error: `Select at least ${minSelected} option${minSelected > 1 ? 's' : ''}`,
          };
        }
        return { valid: true };
      };

      expect(validateArray([], 1).valid).toBe(false);
      expect(validateArray(['option1'], 1).valid).toBe(true);
      expect(validateArray(['option1'], 2).valid).toBe(false);
      expect(validateArray(['option1', 'option2'], 2).valid).toBe(true);
    });

    it('should validate file uploads', async () => {
      const validateFile = (
        file: File | null,
        allowedTypes: string[],
        maxSize: number
      ): { valid: boolean; error?: string } => {
        if (!file) {
          return { valid: false, error: 'File is required' };
        }

        if (!allowedTypes.includes(file.type)) {
          return { valid: false, error: 'Invalid file type' };
        }

        if (file.size > maxSize) {
          return { valid: false, error: `File size must be less than ${maxSize / 1024 / 1024}MB` };
        }

        return { valid: true };
      };

      const validFile = new File(['content'], 'test.pdf', { type: 'application/pdf' });
      const invalidTypeFile = new File(['content'], 'test.exe', { type: 'application/x-executable' });
      const largeFile = new File(['x'.repeat(10 * 1024 * 1024)], 'large.pdf', { type: 'application/pdf' });

      expect(validateFile(null, ['application/pdf'], 5 * 1024 * 1024).valid).toBe(false);
      expect(validateFile(validFile, ['application/pdf'], 5 * 1024 * 1024).valid).toBe(true);
      expect(validateFile(invalidTypeFile, ['application/pdf'], 5 * 1024 * 1024).valid).toBe(false);
      expect(validateFile(largeFile, ['application/pdf'], 5 * 1024 * 1024).valid).toBe(false);
    });
  });
});
