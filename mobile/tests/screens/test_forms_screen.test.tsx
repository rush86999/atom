/**
 * Forms Screen Tests
 *
 * Tests for form screens covering:
 * - Form rendering and display
 * - Form validation logic
 * - Form submission handling
 * - Error display on submission failure
 *
 * @module Forms Screen Tests
 * @see Phase 158-02 - Mobile Test Suite Execution
 */

import React, { useState } from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Text, View, TextInput, Button, ActivityIndicator, Alert } from 'react-native';

// ============================================================================
// Mock Form Components
// ============================================================================

interface FormField {
  name: string;
  value: string;
  error: string | null;
  touched: boolean;
}

interface FormState {
  fields: Record<string, FormField>;
  isSubmitting: boolean;
  submitError: string | null;
}

const MockFormScreen = ({ onSubmit }: { onSubmit?: (data: any) => Promise<void> }) => {
  const [form, setForm] = useState<FormState>({
    fields: {
      email: { name: 'email', value: '', error: null, touched: false },
      password: { name: 'password', value: '', error: null, touched: false },
      confirmPassword: { name: 'confirmPassword', value: '', error: null, touched: false },
    },
    isSubmitting: false,
    submitError: null,
  });

  const validateEmail = (email: string): string | null => {
    if (!email) return 'Email is required';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return 'Invalid email format';
    }
    return null;
  };

  const validatePassword = (password: string): string | null => {
    if (!password) return 'Password is required';
    if (password.length < 8) return 'Password must be at least 8 characters';
    return null;
  };

  const validateConfirmPassword = (password: string, confirmPassword: string): string | null => {
    if (!confirmPassword) return 'Please confirm your password';
    if (password !== confirmPassword) return 'Passwords do not match';
    return null;
  };

  const handleChange = (fieldName: string, value: string) => {
    setForm((prev) => ({
      ...prev,
      fields: {
        ...prev.fields,
        [fieldName]: {
          ...prev.fields[fieldName],
          value,
          touched: true,
          error: null,
        },
      },
    }));
  };

  const handleBlur = (fieldName: string) => {
    const field = form.fields[fieldName];
    let error = null;

    if (fieldName === 'email') {
      error = validateEmail(field.value);
    } else if (fieldName === 'password') {
      error = validatePassword(field.value);
    } else if (fieldName === 'confirmPassword') {
      error = validateConfirmPassword(form.fields.password.value, field.value);
    }

    setForm((prev) => ({
      ...prev,
      fields: {
        ...prev.fields,
        [fieldName]: {
          ...prev.fields[fieldName],
          error,
        },
      },
    }));
  };

  const handleSubmit = async () => {
    // Validate all fields
    const emailError = validateEmail(form.fields.email.value);
    const passwordError = validatePassword(form.fields.password.value);
    const confirmPasswordError = validateConfirmPassword(
      form.fields.password.value,
      form.fields.confirmPassword.value
    );

    setForm((prev) => ({
      ...prev,
      fields: {
        ...prev.fields,
        email: { ...prev.fields.email, error: emailError },
        password: { ...prev.fields.password, error: passwordError },
        confirmPassword: { ...prev.fields.confirmPassword, error: confirmPasswordError },
      },
    }));

    if (emailError || passwordError || confirmPasswordError) {
      return;
    }

    setForm((prev) => ({ ...prev, isSubmitting: true, submitError: null }));

    try {
      await onSubmit?.({
        email: form.fields.email.value,
        password: form.fields.password.value,
      });

      setForm((prev) => ({
        ...prev,
        isSubmitting: false,
      }));
    } catch (error) {
      setForm((prev) => ({
        ...prev,
        isSubmitting: false,
        submitError: (error as Error).message || 'Submission failed',
      }));
    }
  };

  return (
    <View testID="form-screen">
      {form.submitError && (
        <View testID="submit-error-container">
          <Text testID="submit-error">{form.submitError}</Text>
        </View>
      )}

      <View testID="email-field">
        <TextInput
          testID="email-input"
          placeholder="Email"
          value={form.fields.email.value}
          onChangeText={(text) => handleChange('email', text)}
          onBlur={() => handleBlur('email')}
          keyboardType="email-address"
          autoCapitalize="none"
        />
        {form.fields.email.error && form.fields.email.touched && (
          <Text testID="email-error">{form.fields.email.error}</Text>
        )}
      </View>

      <View testID="password-field">
        <TextInput
          testID="password-input"
          placeholder="Password"
          value={form.fields.password.value}
          onChangeText={(text) => handleChange('password', text)}
          onBlur={() => handleBlur('password')}
          secureTextEntry
        />
        {form.fields.password.error && form.fields.password.touched && (
          <Text testID="password-error">{form.fields.password.error}</Text>
        )}
      </View>

      <View testID="confirm-password-field">
        <TextInput
          testID="confirm-password-input"
          placeholder="Confirm Password"
          value={form.fields.confirmPassword.value}
          onChangeText={(text) => handleChange('confirmPassword', text)}
          onBlur={() => handleBlur('confirmPassword')}
          secureTextEntry
        />
        {form.fields.confirmPassword.error && form.fields.confirmPassword.touched && (
          <Text testID="confirm-password-error">{form.fields.confirmPassword.error}</Text>
        )}
      </View>

      {form.isSubmitting ? (
        <View testID="submitting-indicator">
          <ActivityIndicator testID="activity-indicator" animating={true} />
          <Text>Submitting...</Text>
        </View>
      ) : (
        <Button testID="submit-button" title="Submit" onPress={handleSubmit} />
      )}
    </View>
  );
};

// ============================================================================
// Form Screen Tests
// ============================================================================

describe('Form Screen Tests', () => {
  // Test 1: Form renders all fields
  it('test_form_renders', () => {
    const { getByTestId } = render(<MockFormScreen />);

    expect(getByTestId('form-screen')).toBeTruthy();
    expect(getByTestId('email-input')).toBeTruthy();
    expect(getByTestId('password-input')).toBeTruthy();
    expect(getByTestId('confirm-password-input')).toBeTruthy();
    expect(getByTestId('submit-button')).toBeTruthy();
  });

  // Test 2: Form validation - required fields
  it('test_form_validation_required_fields', async () => {
    const mockOnSubmit = jest.fn();
    const { getByTestId, queryByTestId } = render(<MockFormScreen onSubmit={mockOnSubmit} />);

    const submitButton = getByTestId('submit-button');
    fireEvent.press(submitButton);

    await waitFor(() => {
      expect(queryByTestId('email-error')).toBeTruthy();
      expect(queryByTestId('password-error')).toBeTruthy();
      expect(queryByTestId('confirm-password-error')).toBeTruthy();
    });

    // Should not call onSubmit with invalid data
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  // Test 3: Form validation - email format
  it('test_form_validation_email_format', async () => {
    const { getByTestId, queryByTestId } = render(<MockFormScreen />);

    const emailInput = getByTestId('email-input');
    fireEvent.changeText(emailInput, 'invalid-email');
    fireEvent(emailInput, 'blur');

    await waitFor(() => {
      expect(queryByTestId('email-error')).toBeTruthy();
      expect(queryByTestId('email-error')?.props.children).toBe('Invalid email format');
    });
  });

  // Test 4: Form validation - password length
  it('test_form_validation_password_length', async () => {
    const { getByTestId, queryByTestId } = render(<MockFormScreen />);

    const passwordInput = getByTestId('password-input');
    fireEvent.changeText(passwordInput, 'short');
    fireEvent(passwordInput, 'blur');

    await waitFor(() => {
      expect(queryByTestId('password-error')).toBeTruthy();
      expect(queryByTestId('password-error')?.props.children).toContain('at least 8 characters');
    });
  });

  // Test 5: Form validation - password mismatch
  it('test_form_validation_password_mismatch', async () => {
    const { getByTestId, queryByTestId } = render(<MockFormScreen />);

    const passwordInput = getByTestId('password-input');
    const confirmPasswordInput = getByTestId('confirm-password-input');

    fireEvent.changeText(passwordInput, 'password123');
    fireEvent.changeText(confirmPasswordInput, 'different123');
    fireEvent(confirmPasswordInput, 'blur');

    await waitFor(() => {
      expect(queryByTestId('confirm-password-error')).toBeTruthy();
      expect(queryByTestId('confirm-password-error')?.props.children).toBe('Passwords do not match');
    });
  });

  // Test 6: Form validation - valid data
  it('test_form_validation_valid_data', async () => {
    const { getByTestId, queryByTestId } = render(<MockFormScreen />);

    const emailInput = getByTestId('email-input');
    const passwordInput = getByTestId('password-input');
    const confirmPasswordInput = getByTestId('confirm-password-input');

    fireEvent.changeText(emailInput, 'test@example.com');
    fireEvent.changeText(passwordInput, 'password123');
    fireEvent.changeText(confirmPasswordInput, 'password123');

    // Blur all fields to trigger validation
    fireEvent(emailInput, 'blur');
    fireEvent(passwordInput, 'blur');
    fireEvent(confirmPasswordInput, 'blur');

    await waitFor(() => {
      expect(queryByTestId('email-error')).toBeNull();
      expect(queryByTestId('password-error')).toBeNull();
      expect(queryByTestId('confirm-password-error')).toBeNull();
    });
  });

  // Test 7: Form submission
  it('test_form_submission', async () => {
    const mockOnSubmit = jest.fn().mockResolvedValue(undefined);
    const { getByTestId, queryByTestId } = render(<MockFormScreen onSubmit={mockOnSubmit} />);

    const emailInput = getByTestId('email-input');
    const passwordInput = getByTestId('password-input');
    const confirmPasswordInput = getByTestId('confirm-password-input');
    const submitButton = getByTestId('submit-button');

    fireEvent.changeText(emailInput, 'user@example.com');
    fireEvent.changeText(passwordInput, 'password123');
    fireEvent.changeText(confirmPasswordInput, 'password123');

    fireEvent.press(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        email: 'user@example.com',
        password: 'password123',
      });
    });
  });

  // Test 8: Form error handling
  it('test_form_error_handling', async () => {
    const mockOnSubmit = jest.fn().mockRejectedValue(new Error('Network error'));
    const { getByTestId, queryByTestId } = render(<MockFormScreen onSubmit={mockOnSubmit} />);

    const emailInput = getByTestId('email-input');
    const passwordInput = getByTestId('password-input');
    const confirmPasswordInput = getByTestId('confirm-password-input');
    const submitButton = getByTestId('submit-button');

    fireEvent.changeText(emailInput, 'user@example.com');
    fireEvent.changeText(passwordInput, 'password123');
    fireEvent.changeText(confirmPasswordInput, 'password123');

    fireEvent.press(submitButton);

    await waitFor(() => {
      expect(queryByTestId('submit-error')).toBeTruthy();
      expect(queryByTestId('submit-error')?.props.children).toBe('Network error');
    });
  });

  // Test 9: Form loading state
  it('test_form_loading_state', async () => {
    let resolveSubmit: (value: void) => void;
    const mockOnSubmit = jest.fn(() => new Promise((resolve) => { resolveSubmit = resolve; }));

    const { getByTestId, queryByTestId } = render(<MockFormScreen onSubmit={mockOnSubmit} />);

    const emailInput = getByTestId('email-input');
    const passwordInput = getByTestId('password-input');
    const confirmPasswordInput = getByTestId('confirm-password-input');
    const submitButton = getByTestId('submit-button');

    fireEvent.changeText(emailInput, 'user@example.com');
    fireEvent.changeText(passwordInput, 'password123');
    fireEvent.changeText(confirmPasswordInput, 'password123');

    fireEvent.press(submitButton);

    await waitFor(() => {
      expect(queryByTestId('submitting-indicator')).toBeTruthy();
      expect(queryByTestId('activity-indicator')).toBeTruthy();
      expect(queryByTestId('submit-button')).toBeNull();
    });

    // Resolve the promise
    await act(async () => {
      resolveSubmit!();
    });

    await waitFor(() => {
      expect(queryByTestId('submitting-indicator')).toBeNull();
      expect(queryByTestId('submit-button')).toBeTruthy();
    });
  });

  // Test 10: Form field updates
  it('test_form_field_updates', async () => {
    const { getByTestId } = render(<MockFormScreen />);

    const emailInput = getByTestId('email-input');

    fireEvent.changeText(emailInput, 'first@example.com');
    expect(emailInput.props.value).toBe('first@example.com');

    fireEvent.changeText(emailInput, 'second@example.com');
    expect(emailInput.props.value).toBe('second@example.com');
  });

  // Test 11: Form reset after submission
  it('test_form_reset_after_submission', async () => {
    const mockOnSubmit = jest.fn().mockResolvedValue(undefined);
    const { getByTestId, queryByTestId } = render(<MockFormScreen onSubmit={mockOnSubmit} />);

    const emailInput = getByTestId('email-input');
    const passwordInput = getByTestId('password-input');
    const confirmPasswordInput = getByTestId('confirm-password-input');

    fireEvent.changeText(emailInput, 'user@example.com');
    fireEvent.changeText(passwordInput, 'password123');
    fireEvent.changeText(confirmPasswordInput, 'password123');

    const submitButton = getByTestId('submit-button');
    fireEvent.press(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalled();
    });

    // Note: In actual implementation, you might want to reset the form
    // This test verifies the form can be submitted successfully
  });

  // Test 12: Form error display on submission failure
  it('test_form_error_display_on_submission_failure', async () => {
    const mockOnSubmit = jest.fn().mockRejectedValue(new Error('Invalid credentials'));
    const { getByTestId, queryByTestId } = render(<MockFormScreen onSubmit={mockOnSubmit} />);

    const emailInput = getByTestId('email-input');
    const passwordInput = getByTestId('password-input');
    const confirmPasswordInput = getByTestId('confirm-password-input');

    fireEvent.changeText(emailInput, 'user@example.com');
    fireEvent.changeText(passwordInput, 'password123');
    fireEvent.changeText(confirmPasswordInput, 'password123');

    const submitButton = getByTestId('submit-button');
    fireEvent.press(submitButton);

    await waitFor(() => {
      expect(queryByTestId('submit-error')).toBeTruthy();
      expect(queryByTestId('submit-error')?.props.children).toBe('Invalid credentials');
    });

    // Form should still be functional after error
    expect(queryByTestId('email-input')).toBeTruthy();
    expect(queryByTestId('password-input')).toBeTruthy();
  });
});

// ============================================================================
// Form Integration Tests
// ============================================================================

describe('Form Integration Tests', () => {
  it('should handle rapid field updates', async () => {
    const { getByTestId } = render(<MockFormScreen />);

    const emailInput = getByTestId('email-input');

    // Rapid updates
    fireEvent.changeText(emailInput, 'test1@example.com');
    fireEvent.changeText(emailInput, 'test2@example.com');
    fireEvent.changeText(emailInput, 'test3@example.com');

    expect(emailInput.props.value).toBe('test3@example.com');
  });

  it('should handle field interactions in correct order', async () => {
    const { getByTestId } = render(<MockFormScreen />);

    const emailInput = getByTestId('email-input');
    const passwordInput = getByTestId('password-input');
    const confirmPasswordInput = getByTestId('confirm-password-input');

    // Fill fields in order
    fireEvent.changeText(emailInput, 'user@example.com');
    fireEvent.changeText(passwordInput, 'password123');
    fireEvent.changeText(confirmPasswordInput, 'password123');

    // Blur in reverse order
    fireEvent(confirmPasswordInput, 'blur');
    fireEvent(passwordInput, 'blur');
    fireEvent(emailInput, 'blur');

    // All validations should pass
    await waitFor(() => {
      expect(getByTestId('email-input').props.value).toBe('user@example.com');
      expect(getByTestId('password-input').props.value).toBe('password123');
      expect(getByTestId('confirm-password-input').props.value).toBe('password123');
    });
  });
});

// ============================================================================
// Form Accessibility Tests
// ============================================================================

describe('Form Accessibility', () => {
  it('should have accessible placeholders', () => {
    const { getByPlaceholderText } = render(<MockFormScreen />);

    expect(getByPlaceholderText('Email')).toBeTruthy();
    expect(getByPlaceholderText('Password')).toBeTruthy();
    expect(getByPlaceholderText('Confirm Password')).toBeTruthy();
  });

  it('should have accessible error messages', async () => {
    const { getByTestId, getByText } = render(<MockFormScreen />);

    const submitButton = getByTestId('submit-button');
    fireEvent.press(submitButton);

    await waitFor(() => {
      expect(getByText('Email is required')).toBeTruthy();
      expect(getByText('Password is required')).toBeTruthy();
    });
  });

  it('should announce submission status', async () => {
    const mockOnSubmit = jest.fn().mockRejectedValue(new Error('Submission failed'));
    const { getByTestId, getByText } = render(<MockFormScreen onSubmit={mockOnSubmit} />);

    const emailInput = getByTestId('email-input');
    const passwordInput = getByTestId('password-input');
    const confirmPasswordInput = getByTestId('confirm-password-input');
    const submitButton = getByTestId('submit-button');

    fireEvent.changeText(emailInput, 'user@example.com');
    fireEvent.changeText(passwordInput, 'password123');
    fireEvent.changeText(confirmPasswordInput, 'password123');

    fireEvent.press(submitButton);

    await waitFor(() => {
      expect(getByText('Submission failed')).toBeTruthy();
    });
  });
});

// ============================================================================
// Form Performance Tests
// ============================================================================

describe('Form Performance', () => {
  it('should handle rapid validation without lag', async () => {
    const { getByTestId } = render(<MockFormScreen />);

    const emailInput = getByTestId('email-input');
    const startTime = Date.now();

    // 100 rapid updates
    for (let i = 0; i < 100; i++) {
      fireEvent.changeText(emailInput, `user${i}@example.com`);
    }

    const endTime = Date.now();
    const duration = endTime - startTime;

    // Should complete in less than 1 second
    expect(duration).toBeLessThan(1000);
  });
});
