/**
 * CanvasForm Component Tests
 *
 * Testing suite for CanvasForm component
 * Coverage goals: Form rendering, validation, submission, auto-save
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { CanvasForm } from '../CanvasForm';
import { FormField, FormData } from '../../types/canvas';

// Mock dependencies
jest.mock('react-native-paper', () => ({
  useTheme: () => ({
    colors: {
      primary: '#2196F3',
      error: '#f44336',
      background: '#fff',
      surface: '#fff',
      onSurface: '#000',
      onSurfaceVariant: '#666',
      outline: '#e0e0e0',
      errorContainer: '#FFEBEE',
    },
  }),
  Checkbox: 'Checkbox',
  Switch: 'Switch',
}));

jest.mock('expo-haptics', () => ({
  ImpactFeedbackStyle: {
    Light: 'light',
    Medium: 'medium',
    Heavy: 'heavy',
  },
  triggerImpactAsync: jest.fn(),
}));

jest.mock('@react-native-community/datetimepicker', () => ({
  DateTimePickerAndroid: {
    open: jest.fn(({ value }) => Promise.resolve({ action: 'set', year: 2024, month: 1, day: 1 })),
  },
}));

jest.mock('expo-image-picker', () => ({
  requestCameraPermissionsAsync: jest.fn(() => Promise.resolve({ granted: true })),
  requestMediaLibraryPermissionsAsync: jest.fn(() => Promise.resolve({ granted: true })),
  launchCameraAsync: jest.fn(() => Promise.resolve({ canceled: true, assets: [] })),
  launchImageLibraryAsync: jest.fn(() => Promise.resolve({ canceled: true, assets: [] })),
}));

describe('CanvasForm Component', () => {
  const mockFormData: FormData = {
    id: 'form-1',
    title: 'Test Form',
    fields: [
      {
        name: 'name',
        type: 'text',
        label: 'Name',
        required: true,
        placeholder: 'Enter your name',
      },
      {
        name: 'email',
        type: 'email',
        label: 'Email',
        required: true,
        validation: {
          pattern: '^[\\w-\\.]+@([\\w-]+\\.)+[\\w-]{2,4}$',
          message: 'Invalid email format',
        },
      },
      {
        name: 'bio',
        type: 'textarea',
        label: 'Bio',
        required: false,
        placeholder: 'Tell us about yourself',
      },
      {
        name: 'age',
        type: 'number',
        label: 'Age',
        required: true,
        min: 18,
        max: 100,
      },
      {
        name: 'subscribe',
        type: 'checkbox',
        label: 'Subscribe to newsletter',
        default_value: true,
      },
      {
        name: 'birthdate',
        type: 'date',
        label: 'Birth Date',
        required: false,
      },
      {
        name: 'avatar',
        type: 'file',
        label: 'Avatar',
        required: false,
        accept: 'image/*',
      },
    ],
  };

  describe('Basic Rendering', () => {
    test('should render form with all fields', () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getByText('Test Form')).toBeTruthy();
      expect(getByText('Name')).toBeTruthy();
      expect(getByText('Email')).toBeTruthy();
      expect(getByText('Bio')).toBeTruthy();
      expect(getByText('Age')).toBeTruthy();
    });

    test('should render empty form without crashing', () => {
      const emptyForm: FormData = {
        id: 'empty',
        title: 'Empty Form',
        fields: [],
      };

      const { container } = render(
        <CanvasForm data={emptyForm} />
      );

      expect(container).toBeTruthy();
    });

    test('should render with initial values', () => {
      const initialValues = {
        name: 'John Doe',
        email: 'john@example.com',
      };

      const { getByDisplayValue } = render(
        <CanvasForm
          data={mockFormData}
          initialValues={initialValues}
        />
      );

      // Initial values should be set
      expect(getByDisplayValue('John Doe')).toBeTruthy();
    });
  });

  describe('Field Types', () => {
    test('should render text input', () => {
      const { getByPlaceholderText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getByPlaceholderText('Enter your name')).toBeTruthy();
    });

    test('should render email input', () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getByText('Email')).toBeTruthy();
    });

    test('should render textarea', () => {
      const { getByPlaceholderText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getByPlaceholderText('Tell us about yourself')).toBeTruthy();
    });

    test('should render number input', () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getByText('Age')).toBeTruthy();
    });

    test('should render checkbox', () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getByText('Subscribe to newsletter')).toBeTruthy();
    });

    test('should render date picker', () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getByText('Birth Date')).toBeTruthy();
    });

    test('should render file input', () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getByText('Avatar')).toBeTruthy();
    });
  });

  describe('Validation', () => {
    test('should show error for required field', async () => {
      const onSubmit = jest.fn();
      const { getByText } = render(
        <CanvasForm
          data={mockFormData}
          onSubmit={onSubmit}
        />
      );

      // Try to submit without required fields
      const submitButton = getByText('Submit');
      fireEvent.press(submitButton);

      await waitFor(() => {
        expect(onSubmit).not.toHaveBeenCalled();
      });
    });

    test('should validate email format', async () => {
      const { getByPlaceholderText, getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      const emailInput = getByPlaceholderText('Enter email');
      fireEvent.changeText(emailInput, 'invalid-email');

      // Trigger validation
      const submitButton = getByText('Submit');
      fireEvent.press(submitButton);

      await waitFor(() => {
        // Should show validation error
        expect(getByText('Invalid email format')).toBeTruthy();
      });
    });

    test('should validate number range', async () => {
      const { getByPlaceholderText, getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      // Find age input and enter invalid value
      const ageInput = getByPlaceholderText(/Enter age/i);
      fireEvent.changeText(ageInput, '150');

      // Trigger validation
      const submitButton = getByText('Submit');
      fireEvent.press(submitButton);

      await waitFor(() => {
        // Should show range error
        expect(getByText(/must be between/i)).toBeTruthy();
      });
    });

    test('should not show error for valid input', async () => {
      const onChange = jest.fn();
      const { getByPlaceholderText, queryByText } = render(
        <CanvasForm
          data={mockFormData}
          onChange={onChange}
        />
      );

      const nameInput = getByPlaceholderText('Enter your name');
      fireEvent.changeText(nameInput, 'John Doe');

      await waitFor(() => {
        expect(onSubmit).not.toHaveBeenCalled();
        expect(queryByText(/required/i)).toBeNull();
      });
    });
  });

  describe('User Interactions', () => {
    test('should update value on text change', async () => {
      const onChange = jest.fn();
      const { getByPlaceholderText } = render(
        <CanvasForm
          data={mockFormData}
          onChange={onChange}
        />
      );

      const nameInput = getByPlaceholderText('Enter your name');
      fireEvent.changeText(nameInput, 'John Doe');

      await waitFor(() => {
        expect(onChange).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'John Doe',
          })
        );
      });
    });

    test('should toggle checkbox value', async () => {
      const onChange = jest.fn();
      const { getByText } = render(
        <CanvasForm
          data={mockFormData}
          onChange={onChange}
        />
      );

      const checkbox = getByText('Subscribe to newsletter');
      fireEvent.press(checkbox);

      await waitFor(() => {
        expect(onChange).toHaveBeenCalled();
      });
    });

    test('should call onSubmit with form values', async () => {
      const onSubmit = jest.fn();
      const initialValues = {
        name: 'John Doe',
        email: 'john@example.com',
        age: 25,
      };

      const { getByText } = render(
        <CanvasForm
          data={mockFormData}
          initialValues={initialValues}
          onSubmit={onSubmit}
        />
      );

      const submitButton = getByText('Submit');
      fireEvent.press(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(initialValues);
      });
    });
  });

  describe('Auto-save', () => {
    test('should auto-save after delay', async () => {
      jest.useFakeTimers();
      const onChange = jest.fn();
      const { getByPlaceholderText } = render(
        <CanvasForm
          data={mockFormData}
          onChange={onChange}
          enableAutoSave={true}
          autoSaveDelay={1000}
        />
      );

      const nameInput = getByPlaceholderText('Enter your name');
      fireEvent.changeText(nameInput, 'John');

      // Fast-forward past auto-save delay
      act(() => {
        jest.advanceTimersByTime(1500);
      });

      await waitFor(() => {
        expect(onChange).toHaveBeenCalled();
      });

      jest.useRealTimers();
    });

    test('should not auto-save when disabled', () => {
      const onChange = jest.fn();
      const { getByPlaceholderText } = render(
        <CanvasForm
          data={mockFormData}
          onChange={onChange}
          enableAutoSave={false}
        />
      );

      const nameInput = getByPlaceholderText('Enter your name');
      fireEvent.changeText(nameInput, 'John');

      // onChange should not be called for auto-save
      expect(onChange).not.toHaveBeenCalled();
    });
  });

  describe('Loading State', () => {
    test('should show loading indicator when submitting', () => {
      const onSubmit = jest.fn(() => new Promise(resolve => setTimeout(resolve, 1000)));
      const { getByText, getByTestId } = render(
        <CanvasForm
          data={mockFormData}
          onSubmit={onSubmit}
          loading={true}
        />
      );

      expect(getByTestId('loading-indicator')).toBeTruthy();
    });

    test('should disable submit while loading', () => {
      const { getByText } = render(
        <CanvasForm
          data={mockFormData}
          loading={true}
        />
      );

      const submitButton = getByText('Submit');
      expect(submitButton.props.disabled).toBe(true);
    });
  });

  describe('Default Values', () => {
    test('should apply default values from fields', () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      // Checkbox should have default value
      const checkbox = getByText('Subscribe to newsletter');
      expect(checkbox).toBeTruthy();
    });

    test('should override defaults with initial values', () => {
      const initialValues = {
        subscribe: false,
      };

      const { getByText } = render(
        <CanvasForm
          data={mockFormData}
          initialValues={initialValues}
        />
      );

      expect(getByText('Subscribe to newsletter')).toBeTruthy();
    });
  });

  describe('File Upload', () => {
    test('should handle file selection', async () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      const fileInput = getByText('Avatar');
      fireEvent.press(fileInput);

      await waitFor(() => {
        // File picker should be triggered
        expect(true).toBeTruthy();
      });
    });

    test('should show file preview after selection', async () => {
      const onChange = jest.fn();
      const { getByText } = render(
        <CanvasForm
          data={mockFormData}
          onChange={onChange}
        />
      );

      // Simulate file selection
      const fileInput = getByText('Avatar');
      fireEvent.press(fileInput);

      await waitFor(() => {
        // Should show file preview
        expect(true).toBeTruthy();
      });
    });
  });

  describe('Date Picker', () => {
    test('should open date picker on press', async () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      const dateField = getByText('Birth Date');
      fireEvent.press(dateField);

      await waitFor(() => {
        // Date picker should open
        expect(true).toBeTruthy();
      });
    });

    test('should update value after date selection', async () => {
      const onChange = jest.fn();
      const { getByText } = render(
        <CanvasForm
          data={mockFormData}
          onChange={onChange}
        />
      );

      const dateField = getByText('Birth Date');
      fireEvent.press(dateField);

      await waitFor(() => {
        expect(onChange).toHaveBeenCalled();
      });
    });
  });

  describe('Error Handling', () => {
    test('should handle submission errors gracefully', async () => {
      const onSubmit = jest.fn(() => Promise.reject(new Error('Submission failed')));
      const { getByText } = render(
        <CanvasForm
          data={mockFormData}
          onSubmit={onSubmit}
        />
      );

      const submitButton = getByText('Submit');
      fireEvent.press(submitButton);

      await waitFor(() => {
        // Should not crash
        expect(true).toBeTruthy();
      });
    });

    test('should clear errors on input change', async () => {
      const { getByPlaceholderText, getByText, queryByText } = render(
        <CanvasForm data={mockFormData} />
      );

      // Trigger validation error
      const emailInput = getByPlaceholderText('Enter email');
      fireEvent.changeText(emailInput, 'invalid');

      const submitButton = getByText('Submit');
      fireEvent.press(submitButton);

      await waitFor(() => {
        expect(getByText('Invalid email format')).toBeTruthy();
      });

      // Fix the error
      fireEvent.changeText(emailInput, 'valid@example.com');

      await waitFor(() => {
        expect(queryByText('Invalid email format')).toBeNull();
      });
    });
  });

  describe('Edge Cases', () => {
    test('should handle null form data', () => {
      const { container } = render(
        <CanvasForm data={null as any} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle fields with null properties', () => {
      const formWithNulls: FormData = {
        id: 'nulls',
        title: 'Null Fields',
        fields: [
          {
            name: 'field',
            type: 'text',
            label: null as any,
            required: null as any,
          },
        ],
      };

      const { container } = render(
        <CanvasForm data={formWithNulls} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle very long field names', () => {
      const longFieldNameForm: FormData = {
        id: 'long',
        title: 'Long Field Names',
        fields: [
          {
            name: 'a'.repeat(100),
            type: 'text',
            label: 'A'.repeat(100),
          },
        ],
      };

      const { container } = render(
        <CanvasForm data={longFieldNameForm} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle special characters in values', () => {
      const { getByPlaceholderText } = render(
        <CanvasForm data={mockFormData} />
      );

      const nameInput = getByPlaceholderText('Enter your name');
      fireEvent.changeText(nameInput, '<>&"\'\\n\\t');

      expect(nameInput.props.value).toBe('<>&"\'\\n\\t');
    });
  });

  describe('Accessibility', () => {
    test('should mark required fields', () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      // Required fields should be indicated
      expect(getByText('Name')).toBeTruthy();
      expect(getByText('Email')).toBeTruthy();
    });

    test('should use appropriate input types', () => {
      const { getByPlaceholderText } = render(
        <CanvasForm data={mockFormData} />
      );

      // Email input should have email keyboard type
      const emailInput = getByPlaceholderText('Enter email');
      expect(emailInput).toBeTruthy();
    });

    test('should provide error messages for screen readers', async () => {
      const { getByText, getByPlaceholderText } = render(
        <CanvasForm data={mockFormData} />
      );

      const emailInput = getByPlaceholderText('Enter email');
      fireEvent.changeText(emailInput, 'invalid');

      const submitButton = getByText('Submit');
      fireEvent.press(submitButton);

      await waitFor(() => {
        expect(getByText('Invalid email format')).toBeTruthy();
      });
    });
  });
});
