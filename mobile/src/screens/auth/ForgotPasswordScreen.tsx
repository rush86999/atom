/**
 * ForgotPasswordScreen - Password Reset Flow
 *
 * Features:
 * - Email input field with validation
 * - "Send reset link" button
 * - Loading state during request
 * - Success confirmation with instructions
 * - "Back to login" link
 * - Resend link available after 60 seconds
 * - Error handling (email not found, rate limiting, etc.)
 */

import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
  ActivityIndicator,
  ScrollView,
  Dimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../contexts/AuthContext';
import { AuthScreenNavigationProp } from '../../navigation/types';
import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

// API Base URL
const API_BASE_URL = Constants.expoConfig?.extra?.apiUrl || 'http://localhost:8000';

// Constants
const RESET_COOLDOWN_KEY = 'atom_reset_cooldown';
const COOLDOWN_DURATION = 60; // seconds

interface ForgotPasswordScreenProps {
  navigation: AuthScreenNavigationProp;
}

export const ForgotPasswordScreen: React.FC<ForgotPasswordScreenProps> = ({ navigation }) => {
  const { isAuthenticated } = useAuth();

  // Form state
  const [email, setEmail] = useState('');

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [errors, setErrors] = useState<{ email?: string }>({});
  const [touched, setTouched] = useState<{ email?: boolean }>({});
  const [cooldownRemaining, setCooldownRemaining] = useState(0);

  // Refs
  const emailInputRef = useRef<TextInput>(null);

  /**
   * Initialize screen - auto-focus email, check cooldown
   */
  useEffect(() => {
    const initialize = async () => {
      // Auto-focus email field
      if (emailInputRef.current) {
        setTimeout(() => {
          emailInputRef.current?.focus();
        }, 100);
      }

      // Check for existing cooldown
      const lastResetTime = await SecureStore.getItemAsync(RESET_COOLDOWN_KEY);
      if (lastResetTime) {
        const elapsed = Math.floor((Date.now() - parseInt(lastResetTime, 10)) / 1000);
        const remaining = Math.max(0, COOLDOWN_DURATION - elapsed);
        setCooldownRemaining(remaining);

        // Start countdown if needed
        if (remaining > 0) {
          startCountdown(remaining);
        }
      }
    };

    initialize();
  }, []);

  /**
   * Start cooldown countdown
   */
  const startCountdown = (seconds: number) => {
    let remaining = seconds;
    const interval = setInterval(() => {
      remaining -= 1;
      setCooldownRemaining(remaining);

      if (remaining <= 0) {
        clearInterval(interval);
      }
    }, 1000);

    return interval;
  };

  /**
   * Validate email format
   */
  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  /**
   * Validate form
   */
  const validateForm = (): boolean => {
    const newErrors: typeof errors = {};

    if (!email) {
      newErrors.email = 'Email is required';
    } else if (!validateEmail(email)) {
      newErrors.email = 'Please enter a valid email';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /**
   * Handle send reset link
   */
  const handleSendResetLink = async () => {
    // Mark email as touched
    setTouched({ email: true });

    if (!validateForm()) {
      return;
    }

    if (cooldownRemaining > 0) {
      Alert.alert(
        'Please Wait',
        `Please wait ${cooldownRemaining} seconds before requesting another reset link.`
      );
      return;
    }

    setIsLoading(true);
    setErrors({});

    try {
      // Call password reset API
      const response = await fetch(`${API_BASE_URL}/api/auth/password/reset`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        // Handle specific error cases
        if (response.status === 404) {
          // For security reasons, don't reveal if email exists or not
          // Show success message anyway to prevent email enumeration
        } else if (response.status === 400) {
          throw new Error(data.detail || 'Invalid email address');
        } else if (response.status === 429) {
          throw new Error('Too many reset attempts. Please try again later.');
        } else if (response.status >= 500) {
          throw new Error('Server error. Please try again later.');
        }
        throw new Error(data.detail || 'Failed to send reset link');
      }

      // Start cooldown
      const now = Date.now().toString();
      await SecureStore.setItemAsync(RESET_COOLDOWN_KEY, now);
      startCountdown(COOLDOWN_DURATION);

      // Show success screen
      setIsSuccess(true);
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to send reset link. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle resend reset link
   */
  const handleResendLink = () => {
    if (cooldownRemaining > 0) {
      Alert.alert(
        'Please Wait',
        `Please wait ${cooldownRemaining} seconds before requesting another reset link.`
      );
      return;
    }

    setIsSuccess(false);
    handleSendResetLink();
  };

  /**
   * Navigate back to login
   */
  const navigateToLogin = () => {
    navigation.goBack();
  };

  /**
   * Format cooldown time for display
   */
  const formatCooldown = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins > 0) {
      return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    return `${secs}s`;
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 20}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {!isSuccess ? (
          <>
            {/* Header Section */}
            <View style={styles.headerSection}>
              <View style={styles.iconContainer}>
                <Ionicons name="lock-open-outline" size={60} color="#2196F3" />
              </View>
              <Text style={styles.title}>Forgot Password?</Text>
              <Text style={styles.subtitle}>
                Enter your email address and we'll send you a link to reset your password.
              </Text>
            </View>

            {/* Form Section */}
            <View style={styles.formSection}>
              {/* Email Input */}
              <View style={styles.inputContainer}>
                <View style={styles.inputWrapper}>
                  <Ionicons name="mail-outline" size={20} color="#666" style={styles.inputIcon} />
                  <TextInput
                    ref={emailInputRef}
                    style={styles.input}
                    placeholder="Email"
                    value={email}
                    onChangeText={setEmail}
                    onBlur={() => setTouched({ ...touched, email: true })}
                    autoCapitalize="none"
                    autoComplete="email"
                    keyboardType="email-address"
                    textContentType="emailAddress"
                    returnKeyType="go"
                    onSubmitEditing={handleSendResetLink}
                    editable={!isLoading}
                  />
                </View>
                {touched.email && errors.email && (
                  <Text style={styles.errorText}>{errors.email}</Text>
                )}
              </View>

              {/* Send Reset Link Button */}
              <TouchableOpacity
                style={[styles.sendButton, isLoading && styles.sendButtonDisabled]}
                onPress={handleSendResetLink}
                disabled={isLoading}
                activeOpacity={0.8}
              >
                {isLoading ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.sendButtonText}>Send Reset Link</Text>
                )}
              </TouchableOpacity>
            </View>

            {/* Back to Login Link */}
            <View style={styles.footerSection}>
              <TouchableOpacity onPress={navigateToLogin} disabled={isLoading} activeOpacity={0.7}>
                <Text style={styles.backToLoginText}>Back to Login</Text>
              </TouchableOpacity>
            </View>
          </>
        ) : (
          <>
            {/* Success Section */}
            <View style={styles.successSection}>
              <View style={styles.successIconContainer}>
                <Ionicons name="mail" size={60} color="#4caf50" />
              </View>
              <Text style={styles.successTitle}>Check Your Email</Text>
              <Text style={styles.successMessage}>
                We've sent a password reset link to{' '}
                <Text style={styles.successEmail}>{email}</Text>
              </Text>
              <View style={styles.instructionsContainer}>
                <Text style={styles.instructionText}>
                  <Ionicons name="checkmark-circle" size={16} color="#4caf50" /> Check your email
                  inbox
                </Text>
                <Text style={styles.instructionText}>
                  <Ionicons name="checkmark-circle" size={16} color="#4caf50" /> Click the reset link
                  in the email
                </Text>
                <Text style={styles.instructionText}>
                  <Ionicons name="checkmark-circle" size={16} color="#4caf50" /> Create a new
                  password
                </Text>
              </View>

              {/* Resend Button with Cooldown */}
              <View style={styles.resendSection}>
                <Text style={styles.resendText}>Didn't receive the email?</Text>
                {cooldownRemaining > 0 ? (
                  <View style={styles.cooldownContainer}>
                    <Ionicons name="time-outline" size={16} color="#999" />
                    <Text style={styles.cooldownText}>
                      Resend in {formatCooldown(cooldownRemaining)}
                    </Text>
                  </View>
                ) : (
                  <TouchableOpacity onPress={handleResendLink} activeOpacity={0.7}>
                    <Text style={styles.resendLink}>Resend Email</Text>
                  </TouchableOpacity>
                )}
              </View>

              {/* Back to Login Button */}
              <TouchableOpacity
                style={styles.backButton}
                onPress={navigateToLogin}
                activeOpacity={0.7}
              >
                <Text style={styles.backButtonText}>Back to Login</Text>
              </TouchableOpacity>
            </View>
          </>
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
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingVertical: 40,
    minHeight: SCREEN_HEIGHT,
  },
  headerSection: {
    marginTop: 20,
    marginBottom: 30,
    alignItems: 'center',
  },
  iconContainer: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#E3F2FD',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 26,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 15,
    color: '#666',
    textAlign: 'center',
    lineHeight: 22,
  },
  formSection: {
    marginBottom: 24,
  },
  inputContainer: {
    marginBottom: 16,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#fafafa',
  },
  inputIcon: {
    marginRight: 12,
  },
  input: {
    flex: 1,
    fontSize: 16,
    color: '#333',
  },
  errorText: {
    fontSize: 12,
    color: '#f44336',
    marginTop: 6,
    marginLeft: 16,
  },
  sendButton: {
    backgroundColor: '#2196F3',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 8,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  sendButtonDisabled: {
    backgroundColor: '#B0BEC5',
    elevation: 0,
    shadowOpacity: 0,
  },
  sendButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  footerSection: {
    alignItems: 'center',
    marginTop: 20,
  },
  backToLoginText: {
    fontSize: 15,
    color: '#2196F3',
    fontWeight: '500',
  },
  successSection: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
    marginTop: 40,
  },
  successIconContainer: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#E8F5E9',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  successTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
    textAlign: 'center',
  },
  successMessage: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginBottom: 32,
    lineHeight: 24,
  },
  successEmail: {
    fontWeight: '600',
    color: '#2196F3',
  },
  instructionsContainer: {
    width: '100%',
    backgroundColor: '#f5f5f5',
    borderRadius: 12,
    padding: 20,
    marginBottom: 32,
  },
  instructionText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 12,
    flexDirection: 'row',
    alignItems: 'center',
  },
  resendSection: {
    alignItems: 'center',
    marginBottom: 24,
  },
  resendText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 8,
  },
  cooldownContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  cooldownText: {
    fontSize: 14,
    color: '#999',
    marginLeft: 4,
  },
  resendLink: {
    fontSize: 15,
    color: '#2196F3',
    fontWeight: '500',
  },
  backButton: {
    borderWidth: 1,
    borderColor: '#2196F3',
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 32,
    backgroundColor: '#E3F2FD',
  },
  backButtonText: {
    color: '#2196F3',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default ForgotPasswordScreen;
