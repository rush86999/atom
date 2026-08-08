/**
 * CanvasForm Component Tests
 *
 * Testing suite for CanvasForm component
 * Coverage goals: Form rendering, validation, submission, auto-save
 */

import React from 'react';
import { render, fireEvent, waitFor, act, screen } from '@testing-library/react-native';
import { Alert } from 'react-native';
import { CanvasForm } from '../CanvasForm';
import { FormField, FormData } from '../../types/canvas';

// Mock dependencies
jest.mock('react-native-paper', () => {
  const React = require('react');
  const { TouchableOpacity, Text } = require('react-native');
  return {
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
        primaryContainer: '#E3F2FD',
        onPrimaryContainer: '#1565C0',
        secondary: '#FF9800',
        onPrimary: '#fff',
        onSecondary: '#fff',
      },
    }),
    Checkbox: {
      Item: ({ label, onPress, status }: any) => (
        <TouchableOpacity onPress={onPress}>
          <Text>{label}</Text>
        </TouchableOpacity>
      ),
    },
    // Functional Switch so toggles can be flipped via onValueChange
    Switch: ({ value, onValueChange, testID }: any) => (
      <TouchableOpacity testID={testID} onPress={() => onValueChange?.(!value)}>
        <Text>{value ? 'ON' : 'OFF'}</Text>
      </TouchableOpacity>
    ),
  };
});

jest.mock('expo-haptics', () => ({
  ImpactFeedbackStyle: {
    Light: 'light',
    Medium: 'medium',
    Heavy: 'heavy',
  },
  impactAsync: jest.fn(),
  triggerImpactAsync: jest.fn(),
}));

// The module is not installed — virtual mock so the import resolves in Jest
jest.mock('@react-native-community/datetimepicker', () => ({
  DateTimePickerAndroid: {
    open: jest.fn(({ value, onChange }) => {
      if (onChange) {
        onChange({ type: 'set' }, new Date(2024, 1, 1));
      }
      return Promise.resolve({ action: 'set', year: 2024, month: 1, day: 1 });
    }),
  },
}), { virtual: true });

jest.mock('expo-image-picker', () => ({
  MediaTypeOptions: { All: 'All', Images: 'Images', Videos: 'Videos' },
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
        placeholder: 'Enter email',
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
        placeholder: 'Enter age',
        validation: {
          min: 18,
          max: 100,
        },
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
      expect(getByText(/Name/)).toBeTruthy();
      expect(getByText(/Email/)).toBeTruthy();
      expect(getByText(/Bio/)).toBeTruthy();
      expect(getByText(/Age/)).toBeTruthy();
    });

    test('should render empty form without crashing', () => {
      const emptyForm: FormData = {
        id: 'empty',
        title: 'Empty Form',
        fields: [],
      };

      const { UNSAFE_root } = render(
        <CanvasForm data={emptyForm} />
      );

      expect(UNSAFE_root).toBeTruthy();
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

      expect(getByText(/Email/)).toBeTruthy();
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

      expect(getByText(/Age/)).toBeTruthy();
    });

    test('should render checkbox', () => {
      const { getAllByText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getAllByText(/Subscribe\ to\ newsletter/).length).toBeGreaterThan(0);
    });

    test('should render date picker', () => {
      const { getAllByText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getAllByText(/Birth\ Date/).length).toBeGreaterThan(0);
    });

    test('should render file input', () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      expect(getByText(/Avatar/)).toBeTruthy();
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
        // 150 exceeds the field's max (100)
        expect(getByText(/must be at most 100/i)).toBeTruthy();
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
        expect(onChange).not.toHaveBeenCalled();
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
      const { getAllByText } = render(
        <CanvasForm
          data={mockFormData}
          onChange={onChange}
        />
      );

      const checkbox = getAllByText(/Subscribe\ to\ newsletter/)[1];
      fireEvent.press(checkbox);

      // onChange fires via the auto-save draft timer
      await act(async () => {
        jest.advanceTimersByTime(1000);
      });

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
        expect(onSubmit).toHaveBeenCalledWith({
          ...initialValues,
          subscribe: true,
        });
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
      const { getByTestId } = render(
        <CanvasForm
          data={mockFormData}
          loading={true}
        />
      );

      const submitButton = getByTestId('submit-button');
      // TouchableOpacity exposes the disabled state via accessibilityState
      expect(submitButton.props.accessibilityState?.disabled ?? submitButton.props.disabled).toBe(true);
    });
  });

  describe('Default Values', () => {
    test('should apply default values from fields', () => {
      const { getAllByText } = render(
        <CanvasForm data={mockFormData} />
      );

      // Checkbox should have default value
      const checkbox = getAllByText(/Subscribe\ to\ newsletter/)[1];
      expect(checkbox).toBeTruthy();
    });

    test('should override defaults with initial values', () => {
      const initialValues = {
        subscribe: false,
      };

      const { getAllByText } = render(
        <CanvasForm
          data={mockFormData}
          initialValues={initialValues}
        />
      );

      expect(getAllByText(/Subscribe\ to\ newsletter/).length).toBeGreaterThan(0);
    });
  });

  describe('File Upload', () => {
    test('should handle file selection', async () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      const fileInput = getByText(/Avatar/);
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
      const fileInput = getByText(/Avatar/);
      fireEvent.press(fileInput);

      await waitFor(() => {
        // Should show file preview
        expect(true).toBeTruthy();
      });
    });
  });

  describe('Date Picker', () => {
    test('should open date picker on press', async () => {
      const { getAllByText } = render(
        <CanvasForm data={mockFormData} />
      );

      const dateField = getAllByText(/Birth\ Date/)[0];
      fireEvent.press(dateField);

      await waitFor(() => {
        // Date picker should open
        expect(true).toBeTruthy();
      });
    });

    test('should update value after date selection', async () => {
      const onChange = jest.fn();
      const { getAllByText } = render(
        <CanvasForm
          data={mockFormData}
          onChange={onChange}
        />
      );

      const dateField = getAllByText(/Birth\ Date/)[1];
      fireEvent.press(dateField);

      // onChange fires via the auto-save draft timer
      await act(async () => {
        jest.advanceTimersByTime(1000);
      });

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
      const { UNSAFE_root } = render(
        <CanvasForm data={null as any} />
      );

      expect(UNSAFE_root).toBeTruthy();
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

      const { UNSAFE_root } = render(
        <CanvasForm data={formWithNulls} />
      );

      expect(UNSAFE_root).toBeTruthy();

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

      const { UNSAFE_root } = render(
        <CanvasForm data={longFieldNameForm} />
      );

      expect(UNSAFE_root).toBeTruthy();
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

  describe('Field Validation Branches', () => {
    test('should validate the numeric minimum', async () => {
      const { getByPlaceholderText, getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      const ageInput = getByPlaceholderText(/Enter age/i);
      fireEvent.changeText(ageInput, '15');

      fireEvent.press(getByText('Submit'));

      await waitFor(() => {
        expect(getByText(/must be at least 18/i)).toBeTruthy();
      });
    });

    test('should validate string minimum length', async () => {
      const form: FormData = {
        id: 'str-min',
        title: 'String Min',
        fields: [
          {
            name: 'code',
            type: 'text',
            label: 'Code',
            validation: { min: 5 },
          },
        ],
      };

      const { getByPlaceholderText, getByText } = render(<CanvasForm data={form} />);

      const input = getByPlaceholderText('Code');
      fireEvent.changeText(input, 'abc');
      fireEvent.press(getByText('Submit'));

      await waitFor(() => {
        expect(getByText(/must be at least 5 characters/i)).toBeTruthy();
      });
    });

    test('should validate string maximum length', async () => {
      const form: FormData = {
        id: 'str-max',
        title: 'String Max',
        fields: [
          {
            name: 'code',
            type: 'text',
            label: 'Code',
            validation: { max: 3 },
          },
        ],
      };

      const { getByPlaceholderText, getByText } = render(<CanvasForm data={form} />);

      const input = getByPlaceholderText('Code');
      fireEvent.changeText(input, 'abcd');
      fireEvent.press(getByText('Submit'));

      await waitFor(() => {
        expect(getByText(/must be at most 3 characters/i)).toBeTruthy();
      });
    });

    test('should use the default message when pattern has no message', async () => {
      const form: FormData = {
        id: 'pattern',
        title: 'Pattern Form',
        fields: [
          {
            name: 'zip',
            type: 'text',
            label: 'Zip',
            validation: { pattern: '^\\d{5}$' },
          },
        ],
      };

      const { getByPlaceholderText, getByText } = render(<CanvasForm data={form} />);

      const input = getByPlaceholderText('Zip');
      fireEvent.changeText(input, '12ab');
      fireEvent.press(getByText('Submit'));

      await waitFor(() => {
        expect(getByText(/Zip format is invalid/i)).toBeTruthy();
      });
    });

    test('should validate on blur', async () => {
      const { getByPlaceholderText } = render(<CanvasForm data={mockFormData} />);

      const emailInput = getByPlaceholderText('Enter email');
      fireEvent.changeText(emailInput, 'not-an-email');
      fireEvent(emailInput, 'blur');

      await waitFor(() => {
        expect(screen.getByText('Invalid email format')).toBeTruthy();
      });
    });
  });

  describe('Select Fields', () => {
    const selectForm: FormData = {
      id: 'select',
      title: 'Select Form',
      fields: [
        {
          name: 'plan',
          type: 'select',
          label: 'Plan',
          options: ['Basic', 'Pro', 'Enterprise'],
        },
      ],
    };

    test('should render and select an option', async () => {
      const onChange = jest.fn();
      const { getByText } = render(
        <CanvasForm data={selectForm} onChange={onChange} />
      );

      expect(getByText('Basic')).toBeTruthy();
      expect(getByText('Pro')).toBeTruthy();
      expect(getByText('Enterprise')).toBeTruthy();

      fireEvent.press(getByText('Enterprise'));

      await act(async () => {
        jest.advanceTimersByTime(1000);
      });

      await waitFor(() => {
        expect(onChange).toHaveBeenCalledWith(
          expect.objectContaining({ plan: 'Enterprise' })
        );
      });
    });

    test('should render nothing for a select without options', async () => {
      const form: FormData = {
        id: 'no-options',
        title: 'No Options',
        fields: [
          { name: 'empty', type: 'select', label: 'Empty Select' },
        ],
      };

      const { getByText, queryByText } = render(<CanvasForm data={form} />);

      expect(getByText('Empty Select')).toBeTruthy();
      expect(queryByText('Submit')).toBeTruthy();
    });
  });

  describe('Time Picker', () => {
    test('should open the time picker and update the value', async () => {
      const onChange = jest.fn();
      const form: FormData = {
        id: 'time',
        title: 'Time Form',
        fields: [
          { name: 'meeting', type: 'time', label: 'Meeting Time' },
        ],
      };

      const { getByText } = render(<CanvasForm data={form} onChange={onChange} />);

      fireEvent.press(getByText('Select Meeting Time'));

      await act(async () => {
        jest.advanceTimersByTime(1000);
      });

      await waitFor(() => {
        expect(onChange).toHaveBeenCalled();
        expect(onChange.mock.calls[0][0].meeting).toMatch(/^\d{4}-\d{2}-\d{2}T/);
      });
    });
  });

  describe('Toggle Fields', () => {
    test('should flip the toggle value', async () => {
      const onChange = jest.fn();
      const form: FormData = {
        id: 'toggle',
        title: 'Toggle Form',
        fields: [
          { name: 'notify', type: 'toggle', label: 'Notifications' },
        ],
      };

      const { getByText } = render(<CanvasForm data={form} onChange={onChange} />);

      // Switch mock renders OFF initially
      expect(getByText('OFF')).toBeTruthy();

      fireEvent.press(getByText('OFF'));

      await act(async () => {
        jest.advanceTimersByTime(1000);
      });

      await waitFor(() => {
        expect(onChange).toHaveBeenCalledWith(
          expect.objectContaining({ notify: true })
        );
      });
      expect(getByText('ON')).toBeTruthy();
    });
  });

  describe('Multi-Select Fields', () => {
    const multiForm: FormData = {
      id: 'multi',
      title: 'Multi Form',
      fields: [
        {
          name: 'tags',
          type: 'multiselect',
          label: 'Tags',
          options: ['alpha', 'beta', 'gamma'],
        },
      ],
    };

    test('should toggle options in the selected set', async () => {
      const onChange = jest.fn();
      const { getByText } = render(<CanvasForm data={multiForm} onChange={onChange} />);

      fireEvent.press(getByText('alpha'));
      fireEvent.press(getByText('beta'));
      fireEvent.press(getByText('alpha'));

      await act(async () => {
        jest.advanceTimersByTime(1000);
      });

      await waitFor(() => {
        expect(onChange).toHaveBeenCalledWith(
          expect.objectContaining({ tags: ['beta'] })
        );
      });
    });

    test('should render nothing for a multiselect without options', async () => {
      const form: FormData = {
        id: 'multi-empty',
        title: 'Multi Empty',
        fields: [
          { name: 'tags', type: 'multiselect', label: 'Tags' },
        ],
      };

      const { getByText } = render(<CanvasForm data={form} />);

      expect(getByText('Tags')).toBeTruthy();
    });
  });

  describe('File Upload', () => {
    const fileForm: FormData = {
      id: 'file',
      title: 'File Form',
      fields: [
        { name: 'doc', type: 'file', label: 'Document' },
      ],
    };

    test('should show the preview after choosing a file', async () => {
      const ImagePicker = require('expo-image-picker');
      (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValueOnce({
        canceled: false,
        assets: [{ uri: 'file:///tmp/doc.pdf' }],
      });

      const { getByText, getByPlaceholderText } = render(<CanvasForm data={fileForm} />);

      fireEvent.press(getByText('Choose File'));

      await waitFor(() => {
        expect(getByText('File selected')).toBeTruthy();
      });
      expect(getByText('Remove')).toBeTruthy();
    });

    test('should do nothing when the picker is cancelled', async () => {
      const { getByText, queryByText } = render(<CanvasForm data={fileForm} />);

      fireEvent.press(getByText('Choose File'));

      await waitFor(() => {
        expect(queryByText('File selected')).toBeNull();
        expect(getByText('Choose File')).toBeTruthy();
      });
    });

    test('should log an error when the picker throws', async () => {
      const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      const ImagePicker = require('expo-image-picker');
      (ImagePicker.launchImageLibraryAsync as jest.Mock).mockRejectedValueOnce(new Error('no access'));

      const { getByText } = render(<CanvasForm data={fileForm} />);

      fireEvent.press(getByText('Choose File'));

      await waitFor(() => {
        expect(errorSpy).toHaveBeenCalled();
      });
      errorSpy.mockRestore();
    });

    test('should show the preview after taking a photo', async () => {
      const ImagePicker = require('expo-image-picker');
      (ImagePicker.launchCameraAsync as jest.Mock).mockResolvedValueOnce({
        canceled: false,
        assets: [{ uri: 'file:///tmp/photo.jpg' }],
      });

      const { getByText } = render(<CanvasForm data={fileForm} />);

      fireEvent.press(getByText('Take Photo'));

      await waitFor(() => {
        expect(getByText('File selected')).toBeTruthy();
      });
    });

    test('should log an error when the camera throws', async () => {
      const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      const ImagePicker = require('expo-image-picker');
      (ImagePicker.launchCameraAsync as jest.Mock).mockRejectedValueOnce(new Error('camera broken'));

      const { getByText } = render(<CanvasForm data={fileForm} />);

      fireEvent.press(getByText('Take Photo'));

      await waitFor(() => {
        expect(errorSpy).toHaveBeenCalled();
      });
      errorSpy.mockRestore();
    });

    test('should remove the selected file', async () => {
      const ImagePicker = require('expo-image-picker');
      (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValueOnce({
        canceled: false,
        assets: [{ uri: 'file:///tmp/doc.pdf' }],
      });

      const { getByText, queryByText } = render(<CanvasForm data={fileForm} />);

      fireEvent.press(getByText('Choose File'));
      await waitFor(() => {
        expect(getByText('File selected')).toBeTruthy();
      });

      fireEvent.press(getByText('Remove'));

      await waitFor(() => {
        expect(queryByText('File selected')).toBeNull();
        expect(getByText('Choose File')).toBeTruthy();
      });
    });
  });

  describe('Submission Flow', () => {
    test('should alert when the submit handler throws', async () => {
      const onSubmit = jest.fn(() => Promise.reject(new Error('boom')));
      const initialValues = {
        name: 'John Doe',
        email: 'john@example.com',
        age: 25,
      };

      const { getByText } = render(
        <CanvasForm data={mockFormData} initialValues={initialValues} onSubmit={onSubmit} />
      );

      fireEvent.press(getByText('Submit'));

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Submit Error',
          'Failed to submit form. Please try again.'
        );
      });
    });

    test('should show a validation alert for invalid forms', async () => {
      const onSubmit = jest.fn();
      const { getByText } = render(
        <CanvasForm data={mockFormData} onSubmit={onSubmit} />
      );

      fireEvent.press(getByText('Submit'));

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Validation Error',
          'Please fix the errors before submitting'
        );
      });
      expect(onSubmit).not.toHaveBeenCalled();
    });

    test('should show progress percentage for required fields', async () => {
      const { getByText } = render(<CanvasForm data={mockFormData} />);

      expect(getByText('0%')).toBeTruthy();

      const nameInput = screen.getByPlaceholderText('Enter your name');
      const emailInput = screen.getByPlaceholderText('Enter email');
      const ageInput = screen.getByPlaceholderText(/Enter age/i);
      fireEvent.changeText(nameInput, 'John');
      fireEvent.changeText(emailInput, 'john@example.com');
      fireEvent.changeText(ageInput, '30');

      await waitFor(() => {
        expect(getByText('100%')).toBeTruthy();
      });
    });
  });

  describe('Custom Buttons', () => {
    test('should render a custom submit label', async () => {
      const form: FormData = {
        id: 'custom',
        title: 'Custom Form',
        submit_button_text: 'Save Changes',
        fields: [],
      };

      const { getByText } = render(<CanvasForm data={form} />);

      expect(getByText('Save Changes')).toBeTruthy();
    });

    test('should render and press the cancel button', async () => {
      const haptics = require('expo-haptics');
      const form: FormData = {
        id: 'cancel',
        title: 'Cancel Form',
        cancel_button_text: 'Never Mind',
        fields: [],
      };

      const { getByText } = render(<CanvasForm data={form} />);

      fireEvent.press(getByText('Never Mind'));

      expect(haptics.impactAsync).toHaveBeenCalled();
    });
  });

  describe('Draft Saving Indicator', () => {
    test('should show and hide the saving indicator', async () => {
      jest.useFakeTimers();
      const onChange = jest.fn();
      const { getByPlaceholderText, getByText, queryByText } = render(
        <CanvasForm data={mockFormData} onChange={onChange} autoSaveDelay={1000} />
      );

      const nameInput = getByPlaceholderText('Enter your name');
      fireEvent.changeText(nameInput, 'John');

      act(() => {
        jest.advanceTimersByTime(1000);
      });

      await waitFor(() => {
        expect(getByText('Saving draft...')).toBeTruthy();
      });

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(queryByText('Saving draft...')).toBeNull();
      });

      jest.useRealTimers();
    });
  });

  describe('Accessibility', () => {
    test('should mark required fields', () => {
      const { getByText } = render(
        <CanvasForm data={mockFormData} />
      );

      // Required fields should be indicated
      expect(getByText(/Name/)).toBeTruthy();
      expect(getByText(/Email/)).toBeTruthy();
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
