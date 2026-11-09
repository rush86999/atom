/**
 * CanvasForm Component
 *
 * Mobile-optimized form component using native React Native controls.
 * Supports various input types with validation, auto-save, and progress tracking.
 */

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  View,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useTheme, Checkbox, Switch } from 'react-native-paper';
import * as Haptics from 'expo-haptics';
import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';

import { FormField, FormData } from '../../types/canvas';

interface CanvasFormProps {
  data: FormData;
  initialValues?: Record<string, any>;
  onSubmit?: (values: Record<string, any>) => void;
  onChange?: (values: Record<string, any>) => void;
  loading?: boolean;
  style?: any;
  enableAutoSave?: boolean;
  autoSaveDelay?: number;
}

/**
 * CanvasForm Component
 *
 * Renders mobile-friendly forms with native inputs, validation, and auto-save.
 */
export const CanvasForm: React.FC<CanvasFormProps> = ({
  data,
  initialValues = {},
  onSubmit,
  onChange,
  loading = false,
  style,
  enableAutoSave = true,
  autoSaveDelay = 1000,
}) => {
  const theme = useTheme();

  const [values, setValues] = useState<Record<string, any>>(initialValues);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [draftSaving, setDraftSaving] = useState(false);
  const [activePicker, setActivePicker] = useState<{ name: string; mode: 'date' | 'time' } | null>(
    null
  );

  // Stable reference: when `data?.fields` is undefined/null (edge payloads),
  // a bare `data?.fields ?? []` re-created the array on every render, which
  // re-ran the defaults effect every render → setValues → re-render →
  // infinite render loop → JS heap OOM (CanvasForm.test "null form data").
  const fields = useMemo(() => data?.fields ?? [], [data?.fields]);

  // Initialize default values
  useEffect(() => {
    const defaults: Record<string, any> = {};
    fields.forEach(field => {
      if (field.default_value !== undefined) {
        defaults[field.name] = field.default_value;
      }
    });
    setValues(prev => ({ ...defaults, ...prev }));
  }, [fields]);

  // Auto-save draft
  useEffect(() => {
    if (!enableAutoSave) return;

    const timer = setTimeout(() => {
      const hasTouched = Object.keys(touched).some(key => touched[key]);
      if (hasTouched && !submitting) {
        saveDraft();
      }
    }, autoSaveDelay);

    return () => clearTimeout(timer);
  }, [values, touched, enableAutoSave, autoSaveDelay, submitting]);

  /**
   * Save draft (auto-save)
   */
  const saveDraft = useCallback(async () => {
    setDraftSaving(true);
    // Could save to AsyncStorage here
    console.log('Saving draft:', values);
    onChange?.(values);
    setTimeout(() => setDraftSaving(false), 500);
  }, [values, onChange]);

  /**
   * Validate field
   */
  const validateField = useCallback((field: FormField, value: any): string | null => {
    if (field.required && (value === undefined || value === null || value === '')) {
      return `${field.label} is required`;
    }

    // Input text remains unchanged in the submitted values. Interpret it only
    // for number-field validation; numeric-looking text still uses text lengths.
    const hasValue = value !== undefined && value !== null && value !== '';
    const numericValue = typeof value === 'number'
      ? value
      : typeof value === 'string' && value.trim() !== '' ? Number(value) : NaN;
    if (field.type === 'number' && hasValue && !Number.isFinite(numericValue)) {
      return `${field.label} must be a finite number`;
    }

    if (field.validation) {
      const { min, max, pattern } = field.validation;

      if (field.type === 'number' && hasValue && min !== undefined && numericValue < min) {
        return `${field.label} must be at least ${min}`;
      }

      if (field.type === 'number' && hasValue && max !== undefined && numericValue > max) {
        return `${field.label} must be at most ${max}`;
      }

      if (typeof value === 'string' && pattern) {
        const regex = new RegExp(pattern);
        if (!regex.test(value)) {
          return field.validation.message || `${field.label} format is invalid`;
        }
      }

      if (field.type !== 'number' && typeof value === 'string' && min !== undefined && value.length < min) {
        return `${field.label} must be at least ${min} characters`;
      }

      if (field.type !== 'number' && typeof value === 'string' && max !== undefined && value.length > max) {
        return `${field.label} must be at most ${max} characters`;
      }
    }

    return null;
  }, []);

  /**
   * Validate all fields
   */
  const validateAll = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};

    fields.forEach(field => {
      const error = validateField(field, values[field.name]);
      if (error) {
        newErrors[field.name] = error;
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [fields, values, validateField]);

  /**
   * Handle field value change
   */
  const handleChange = useCallback((fieldName: string, value: any) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    setValues(prev => ({ ...prev, [fieldName]: value }));
    setTouched(prev => ({ ...prev, [fieldName]: true }));

    // Clear error on change
    if (errors[fieldName]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[fieldName];
        return newErrors;
      });
    }
  }, [errors]);

  /**
   * Handle field blur (validate)
   */
  const handleBlur = useCallback((fieldName: string) => {
    const field = fields.find(f => f.name === fieldName);
    if (field) {
      const error = validateField(field, values[fieldName]);
      if (error) {
        setErrors(prev => ({ ...prev, [fieldName]: error }));
      }
    }
  }, [fields, values, validateField]);

  /**
   * Handle submit
   */
  const handleSubmit = useCallback(async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    const isValid = validateAll();
    if (!isValid) {
      Alert.alert('Validation Error', 'Please fix the errors before submitting');
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit?.(values);
    } catch (error) {
      Alert.alert('Submit Error', 'Failed to submit form. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }, [values, validateAll, onSubmit]);

  /**
   * Calculate form progress
   */
  const calculateProgress = useCallback(() => {
    const requiredFields = fields.filter(f => f.required);
    if (requiredFields.length === 0) return 100;

    const filledRequired = requiredFields.filter(
      f => values[f.name] !== undefined && values[f.name] !== null && values[f.name] !== ''
    ).length;

    return Math.round((filledRequired / requiredFields.length) * 100);
  }, [fields, values]);

  /**
   * Render text input
   */
  const renderTextInput = (field: FormField) => (
    <TextInput
      style={[
        styles.input,
        { borderColor: errors[field.name] ? theme.colors.error : theme.colors.outline },
      ]}
      value={values[field.name] || ''}
      onChangeText={value => handleChange(field.name, value)}
      onBlur={() => handleBlur(field.name)}
      placeholder={field.placeholder || field.label}
      placeholderTextColor={theme.colors.onSurfaceVariant}
      keyboardType={
        field.type === 'email'
          ? 'email-address'
          : field.type === 'number'
          ? 'decimal-pad'
          : field.type === 'phone'
          ? 'phone-pad'
          : 'default'
      }
      secureTextEntry={field.type === 'password'}
      autoCapitalize="none"
      autoComplete="off"
    />
  );

  /**
   * Render textarea
   */
  const renderTextarea = (field: FormField) => (
    <TextInput
      style={[
        styles.textarea,
        { borderColor: errors[field.name] ? theme.colors.error : theme.colors.outline },
      ]}
      value={values[field.name] || ''}
      onChangeText={value => handleChange(field.name, value)}
      onBlur={() => handleBlur(field.name)}
      placeholder={field.placeholder || field.label}
      placeholderTextColor={theme.colors.onSurfaceVariant}
      multiline
      numberOfLines={4}
      textAlignVertical="top"
    />
  );

  /**
   * Render select dropdown
   */
  const renderSelect = (field: FormField) => {
    if (!field.options || field.options.length === 0) return null;

    return (
      <View style={styles.dropdownContainer}>
        {field.options.map((option, index) => (
          <TouchableOpacity
            key={index}
            style={[
              styles.dropdownOption,
              {
                backgroundColor:
                  values[field.name] === option ? theme.colors.primaryContainer : theme.colors.surface,
                borderColor: theme.colors.outline,
              },
            ]}
            onPress={() => handleChange(field.name, option)}
          >
            <Text
              style={{
                color:
                  values[field.name] === option
                    ? theme.colors.onPrimaryContainer
                    : theme.colors.onSurface,
              }}
            >
              {option}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    );
  };

  /**
   * Open a native date/time picker.
   *
   * Android exposes an imperative API; iOS uses the cross-platform component
   * rendered inline below. Test doubles must implement the real SDK exports.
   */
  const openPicker = useCallback(
    (field: FormField, mode: 'date' | 'time') => {
      const currentValue = values[field.name] ? new Date(values[field.name]) : new Date();

      if (Platform.OS === 'android') {
        DateTimePickerAndroid.open({
          value: currentValue,
          mode,
          onChange: (event, selectedDate) => {
            if (event.type === 'set' && selectedDate) {
              handleChange(field.name, selectedDate.toISOString());
            }
          },
        });
        return;
      }

      if (Platform.OS === 'ios') {
        setActivePicker({ name: field.name, mode });
        return;
      }
      setTouched(previous => ({ ...previous, [field.name]: true }));
      setErrors(previous => ({ ...previous, [field.name]: 'Date/time picking is unavailable on this platform' }));
    },
    [values, handleChange]
  );

  /**
   * Render the cross-platform picker inline (iOS).
   */
  const renderInlinePicker = (field: FormField, mode: 'date' | 'time') => {
    if (
      !activePicker ||
      activePicker.name !== field.name ||
      activePicker.mode !== mode ||
      Platform.OS !== 'ios'
    ) {
      return null;
    }

    return (
      <View>
        <DateTimePicker
          value={values[field.name] ? new Date(values[field.name]) : new Date()}
          mode={mode}
          display="spinner"
          onChange={(event, selectedDate) => {
            if (event.type === 'set' && selectedDate) {
              handleChange(field.name, selectedDate.toISOString());
            }
          }}
        />
        <TouchableOpacity
          style={[styles.datePicker, { borderColor: theme.colors.outline, marginTop: 8 }]}
          onPress={() => setActivePicker(null)}
        >
          <Text style={{ color: theme.colors.primary }}>Done</Text>
        </TouchableOpacity>
      </View>
    );
  };

  /**
   * Render date picker
   */
  const renderDatePicker = (field: FormField) => (
    <View>
      <TouchableOpacity
        style={[styles.datePicker, { borderColor: theme.colors.outline }]}
        onPress={() => openPicker(field, 'date')}
      >
        <Text style={{ color: values[field.name] ? theme.colors.onSurface : theme.colors.onSurfaceVariant }}>
          {values[field.name]
            ? new Date(values[field.name]).toLocaleDateString()
            : field.placeholder || `Select ${field.label}`}
        </Text>
      </TouchableOpacity>
      {renderInlinePicker(field, 'date')}
    </View>
  );

  /**
   * Render time picker
   */
  const renderTimePicker = (field: FormField) => (
    <View>
      <TouchableOpacity
        style={[styles.datePicker, { borderColor: theme.colors.outline }]}
        onPress={() => openPicker(field, 'time')}
      >
        <Text style={{ color: values[field.name] ? theme.colors.onSurface : theme.colors.onSurfaceVariant }}>
          {values[field.name]
            ? new Date(values[field.name]).toLocaleTimeString()
            : field.placeholder || `Select ${field.label}`}
        </Text>
      </TouchableOpacity>
      {renderInlinePicker(field, 'time')}
    </View>
  );

  /**
   * Render toggle switch
   */
  const renderToggle = (field: FormField) => (
    <Switch
      value={values[field.name] || false}
      onValueChange={value => handleChange(field.name, value)}
      color={theme.colors.primary}
    />
  );

  /**
   * Render checkbox
   */
  const renderCheckbox = (field: FormField) => (
    <Checkbox.Item
      status={values[field.name] ? 'checked' : 'unchecked'}
      onPress={() => handleChange(field.name, !values[field.name])}
      label={field.label}
      mode="android"
    />
  );

  /**
   * Render multi-select checkboxes
   */
  const renderMultiSelect = (field: FormField) => {
    if (!field.options || field.options.length === 0) return null;

    const selectedValues = values[field.name] || [];

    return (
      <View style={styles.multiSelectContainer}>
        {field.options.map((option, index) => (
          <Checkbox.Item
            key={index}
            status={selectedValues.includes(option) ? 'checked' : 'unchecked'}
            onPress={() => {
              const newValues = selectedValues.includes(option)
                ? selectedValues.filter((v: any) => v !== option)
                : [...selectedValues, option];
              handleChange(field.name, newValues);
            }}
            label={option}
            mode="android"
          />
        ))}
      </View>
    );
  };

  /**
   * Render file upload
   */
  const renderFileUpload = (field: FormField) => {
    const handlePickFile = async () => {
      try {
        const result = await DocumentPicker.getDocumentAsync({
          type: field.accept ?? '*/*',
          copyToCacheDirectory: true,
          multiple: false,
        });

        if (!result.canceled && result.assets.length > 0) {
          handleChange(field.name, result.assets[0].uri);
        }
      } catch (error) {
        console.error('Error picking file:', error);
      }
    };

    const handleTakePhoto = async () => {
      try {
        const result = await ImagePicker.launchCameraAsync({
          allowsEditing: true,
          quality: 1,
        });

        if (!result.canceled) {
          handleChange(field.name, result.assets[0].uri);
        }
      } catch (error) {
        console.error('Error taking photo:', error);
      }
    };

    return (
      <View style={styles.fileUploadContainer}>
        {values[field.name] ? (
          <View style={styles.filePreview}>
            <Text style={[styles.fileName, { color: theme.colors.onSurface }]}>
              File selected
            </Text>
            <TouchableOpacity onPress={() => handleChange(field.name, null)}>
              <Text style={[styles.removeFile, { color: theme.colors.error }]}>Remove</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.fileButtons}>
            <TouchableOpacity
              style={[styles.fileButton, { backgroundColor: theme.colors.primary }]}
              onPress={handlePickFile}
            >
              <Text style={[styles.fileButtonText, { color: theme.colors.onPrimary }]}>
                Choose File
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.fileButton, { backgroundColor: theme.colors.secondary }]}
              onPress={handleTakePhoto}
            >
              <Text style={[styles.fileButtonText, { color: theme.colors.onSecondary }]}>
                Take Photo
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    );
  };

  /**
   * Render field by type
   */
  const renderField = (field: FormField) => {
    const showError = touched[field.name] && errors[field.name];

    return (
      <View key={field.name} style={styles.fieldContainer}>
        <Text style={[styles.label, { color: theme.colors.onSurface }]}>
          {field.label}
          {field.required && <Text style={{ color: theme.colors.error }}> *</Text>}
        </Text>

        {field.type === 'textarea' && renderTextarea(field)}
        {field.type === 'select' && renderSelect(field)}
        {field.type === 'date' && renderDatePicker(field)}
        {field.type === 'time' && renderTimePicker(field)}
        {field.type === 'checkbox' && renderCheckbox(field)}
        {field.type === 'multiselect' && renderMultiSelect(field)}
        {field.type === 'file' && renderFileUpload(field)}
        {field.type === 'toggle' && renderToggle(field)}
        {![
          'textarea',
          'select',
          'date',
          'time',
          'checkbox',
          'multiselect',
          'file',
          'toggle',
        ].includes(field.type) && renderTextInput(field)}

        {showError && (
          <Text style={[styles.errorText, { color: theme.colors.error }]}>{errors[field.name]}</Text>
        )}
      </View>
    );
  };

  if (!data) {
    return null;
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={[styles.container, style]}
    >
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={true}>
        {/* Header */}
        <Text style={[styles.title, { color: theme.colors.onSurface }]}>{data.title}</Text>
        {data.description && (
          <Text style={[styles.description, { color: theme.colors.onSurfaceVariant }]}>
            {data.description}
          </Text>
        )}

        {/* Progress indicator */}
        <View style={[styles.progressContainer, { backgroundColor: theme.colors.surfaceVariant }]}>
          <View style={styles.progressInfo}>
            <Text style={[styles.progressText, { color: theme.colors.onSurfaceVariant }]}>
              Form Progress
            </Text>
            <Text style={[styles.progressPercentage, { color: theme.colors.primary }]}>
              {calculateProgress()}%
            </Text>
          </View>
          <View style={[styles.progressBar, { backgroundColor: theme.colors.outline }]}>
            <View
              style={[
                styles.progressFill,
                { backgroundColor: theme.colors.primary, width: `${calculateProgress()}%` },
              ]}
            />
          </View>
          {draftSaving && (
            <Text style={[styles.savingText, { color: theme.colors.onSurfaceVariant }]}>
              Saving draft...
            </Text>
          )}
        </View>

        {/* Fields */}
        {fields.map(renderField)}

        {/* Submit button */}
        <TouchableOpacity
          style={[styles.submitButton, { backgroundColor: theme.colors.primary }]}
          onPress={handleSubmit}
          disabled={submitting || loading}
          testID="submit-button"
        >
          {submitting || loading ? (
            <ActivityIndicator size="small" color={theme.colors.onPrimary} testID="loading-indicator" />
          ) : (
            <Text style={[styles.submitButtonText, { color: theme.colors.onPrimary }]}>
              {data.submit_button_text || 'Submit'}
            </Text>
          )}
        </TouchableOpacity>

        {/* Cancel button */}
        {data.cancel_button_text && (
          <TouchableOpacity
            style={[styles.cancelButton, { borderColor: theme.colors.outline }]}
            onPress={() => {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
              // Handle cancel
            }}
          >
            <Text style={[styles.cancelButtonText, { color: theme.colors.onSurface }]}>
              {data.cancel_button_text}
            </Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  scrollView: {
    flex: 1,
    padding: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: '600',
    marginBottom: 8,
  },
  description: {
    fontSize: 14,
    marginBottom: 24,
    lineHeight: 20,
  },
  progressContainer: {
    padding: 12,
    borderRadius: 8,
    marginBottom: 24,
  },
  progressInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  progressText: {
    fontSize: 12,
    fontWeight: '500',
  },
  progressPercentage: {
    fontSize: 14,
    fontWeight: '600',
  },
  progressBar: {
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },
  savingText: {
    fontSize: 11,
    marginTop: 8,
    textAlign: 'center',
  },
  fieldContainer: {
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
    marginBottom: 8,
  },
  input: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    backgroundColor: '#fff',
  },
  textarea: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    backgroundColor: '#fff',
    minHeight: 100,
  },
  dropdownContainer: {
    borderWidth: 1,
    borderRadius: 8,
    overflow: 'hidden',
  },
  dropdownOption: {
    padding: 12,
    borderBottomWidth: 1,
  },
  datePicker: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    backgroundColor: '#fff',
  },
  multiSelectContainer: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 8,
    backgroundColor: '#fff',
  },
  fileUploadContainer: {
    marginTop: 8,
  },
  fileButtons: {
    flexDirection: 'row',
    gap: 8,
  },
  fileButton: {
    flex: 1,
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  fileButtonText: {
    fontWeight: '600',
  },
  filePreview: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
    borderWidth: 1,
    borderRadius: 8,
    backgroundColor: '#fff',
  },
  fileName: {
    fontSize: 14,
  },
  removeFile: {
    fontSize: 14,
    fontWeight: '600',
  },
  errorText: {
    fontSize: 12,
    marginTop: 4,
  },
  submitButton: {
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 8,
    minHeight: 48,
  },
  submitButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
  cancelButton: {
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 8,
    borderWidth: 1,
  },
  cancelButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
});

export default CanvasForm;
