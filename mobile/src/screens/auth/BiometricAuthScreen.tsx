/**
 * BiometricAuthScreen - Biometric Authentication Screen
 *
 * Features:
 * - Biometric icon (Face ID/Touch ID based on device)
 * - "Authenticate to access Atom" prompt
 * - Fallback to password login link
 * - Auto-trigger biometric on mount
 * - Success/failure animation
 * - Support for both Face ID and Touch ID
 * - Handle biometric not available/enrolled
 * - Max 3 attempts before requiring password
 */

import React, { useEffect, useState, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Animated,
  Dimensions,
  StatusBar,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as LocalAuthentication from 'expo-local-authentication';
import { useAuth } from '../../contexts/AuthContext';
import { AuthScreenNavigationProp } from '../../navigation/types';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

// Constants
const MAX_ATTEMPTS = 3;

interface BiometricAuthScreenProps {
  navigation: AuthScreenNavigationProp;
  route: {
    params?: {
      onSuccessNavigate?: string;
    };
  };
}

export const BiometricAuthScreen: React.FC<BiometricAuthScreenProps> = ({ navigation, route }) => {
  const { authenticateWithBiometric, login } = useAuth();

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [biometricType, setBiometricType] = useState<LocalAuthentication.AuthenticationType | null>(
    null
  );
  const [isAvailable, setIsAvailable] = useState(false);

  // Animation refs
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const scaleAnim = useRef(new Animated.Value(0.8)).current;
  const shakeAnim = useRef(new Animated.Value(0)).current;

  /**
   * Initialize screen
   */
  useEffect(() => {
    const initialize = async () => {
      // Check biometric availability
      const hasHardware = await LocalAuthentication.hasHardwareAsync();
      const isEnrolled = await LocalAuthentication.isEnrolledAsync();

      if (!hasHardware || !isEnrolled) {
        setError('Biometric authentication is not available on this device');
        setIsAvailable(false);
        return;
      }

      setIsAvailable(true);

      // Detect biometric type
      const supportedTypes = await LocalAuthentication.supportedAuthenticationTypesAsync();
      if (supportedTypes.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
        setBiometricType(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION);
      } else if (
        supportedTypes.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)
      ) {
        setBiometricType(LocalAuthentication.AuthenticationType.FINGERPRINT);
      }

      // Animate in
      animateIn();

      // Auto-trigger biometric after short delay
      setTimeout(() => {
        triggerBiometric();
      }, 500);
    };

    initialize();
  }, []);

  /**
   * Animate screen elements in
   */
  const animateIn = () => {
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 400,
        useNativeDriver: true,
      }),
      Animated.spring(scaleAnim, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
    ]).start();
  };

  /**
   * Animate shake on error
   */
  const animateShake = () => {
    shakeAnim.setValue(0);
    Animated.sequence([
      Animated.timing(shakeAnim, {
        toValue: 10,
        duration: 50,
        useNativeDriver: true,
      }),
      Animated.timing(shakeAnim, {
        toValue: -10,
        duration: 50,
        useNativeDriver: true,
      }),
      Animated.timing(shakeAnim, {
        toValue: 10,
        duration: 50,
        useNativeDriver: true,
      }),
      Animated.timing(shakeAnim, {
        toValue: 0,
        duration: 50,
        useNativeDriver: true,
      }),
    ]).start();
  };

  /**
   * Animate success pulse
   */
  const animateSuccess = () => {
    Animated.sequence([
      Animated.timing(scaleAnim, {
        toValue: 1.2,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(scaleAnim, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start();
  };

  /**
   * Trigger biometric authentication
   */
  const triggerBiometric = async () => {
    if (!isAvailable || attempts >= MAX_ATTEMPTS) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await authenticateWithBiometric();

      if (result.success) {
        // Success animation
        animateSuccess();

        // Navigate to main app after short delay
        setTimeout(() => {
          // Navigation handled automatically by AuthNavigator
        }, 500);
      } else {
        // Increment attempts
        const newAttempts = attempts + 1;
        setAttempts(newAttempts);

        // Show error
        setError(result.error || 'Biometric authentication failed');
        animateShake();

        // Check if max attempts reached
        if (newAttempts >= MAX_ATTEMPTS) {
          setError('Maximum attempts reached. Please use password to sign in.');
        }
      }
    } catch (err: any) {
      const newAttempts = attempts + 1;
      setAttempts(newAttempts);
      setError(err.message || 'Authentication failed');
      animateShake();

      if (newAttempts >= MAX_ATTEMPTS) {
        setError('Maximum attempts reached. Please use password to sign in.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Retry biometric authentication
   */
  const handleRetry = () => {
    triggerBiometric();
  };

  /**
   * Navigate to password login
   */
  const navigateToPasswordLogin = () => {
    navigation.navigate('Login');
  };

  /**
   * Get biometric icon name
   */
  const getBiometricIcon = (): string => {
    if (biometricType === LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION) {
      return 'face-id'; // Note: Ionicons doesn't have face-id, using custom rendering
    }
    return 'finger-print';
  };

  /**
   * Get biometric label
   */
  const getBiometricLabel = (): string => {
    if (biometricType === LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION) {
      return 'Face ID';
    }
    return 'Touch ID';
  };

  /**
   * Get remaining attempts text
   */
  const getAttemptsText = (): string => {
    if (attempts >= MAX_ATTEMPTS) {
      return 'No attempts remaining';
    }
    const remaining = MAX_ATTEMPTS - attempts;
    return remaining === 1 ? '1 attempt remaining' : `${remaining} attempts remaining`;
  };

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" />

      <Animated.View
        style={[
          styles.contentContainer,
          {
            opacity: fadeAnim,
            transform: [
              { scale: scaleAnim },
              { translateX: shakeAnim },
            ],
          },
        ]}
      >
        {/* Biometric Icon */}
        <View style={styles.iconContainer}>
          {biometricType === LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION ? (
            // Face ID icon (custom rendering)
            <View style={styles.faceIdIcon}>
              <View style={styles.faceIdOutline} />
              <View style={styles.faceIdInner} />
            </View>
          ) : (
            <Ionicons name={getBiometricIcon() as any} size={80} color="#2196F3" />
          )}
        </View>

        {/* Title */}
        <Text style={styles.title}>Authenticate to Access Atom</Text>

        {/* Subtitle */}
        {isAvailable && !error && (
          <Text style={styles.subtitle}>Use {getBiometricLabel()} to sign in</Text>
        )}

        {/* Loading State */}
        {isLoading && (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#2196F3" />
            <Text style={styles.loadingText}>Authenticating...</Text>
          </View>
        )}

        {/* Error State */}
        {error && !isLoading && (
          <View style={styles.errorContainer}>
            <Ionicons name="close-circle" size={24} color="#f44336" />
            <Text style={styles.errorText}>{error}</Text>
            <Text style={styles.attemptsText}>{getAttemptsText()}</Text>

            {/* Retry Button (if attempts remaining) */}
            {attempts < MAX_ATTEMPTS && (
              <TouchableOpacity
                style={styles.retryButton}
                onPress={handleRetry}
                activeOpacity={0.8}
              >
                <Ionicons name="refresh" size={20} color="#2196F3" />
                <Text style={styles.retryButtonText}>Try Again</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* Not Available State */}
        {!isAvailable && (
          <View style={styles.errorContainer}>
            <Ionicons name="warning" size={24} color="#ff9800" />
            <Text style={styles.errorText}>
              Biometric authentication is not available or not set up on this device
            </Text>
          </View>
        )}

        {/* Use Password Button */}
        <TouchableOpacity
          style={styles.passwordButton}
          onPress={navigateToPasswordLogin}
          activeOpacity={0.8}
        >
          <Ionicons name="lock-closed-outline" size={20} color="#2196F3" />
          <Text style={styles.passwordButtonText}>Use Password Instead</Text>
        </TouchableOpacity>
      </Animated.View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#2196F3',
    justifyContent: 'center',
    alignItems: 'center',
  },
  contentContainer: {
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  iconContainer: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#fff',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 32,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 8,
  },
  faceIdIcon: {
    width: 60,
    height: 60,
    justifyContent: 'center',
    alignItems: 'center',
  },
  faceIdOutline: {
    position: 'absolute',
    width: 60,
    height: 60,
    borderRadius: 30,
    borderWidth: 3,
    borderColor: '#2196F3',
  },
  faceIdInner: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#2196F3',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    textAlign: 'center',
    marginBottom: 12,
  },
  subtitle: {
    fontSize: 16,
    color: 'rgba(255, 255, 255, 0.9)',
    textAlign: 'center',
    marginBottom: 32,
  },
  loadingContainer: {
    alignItems: 'center',
    marginVertical: 24,
  },
  loadingText: {
    fontSize: 14,
    color: 'rgba(255, 255, 255, 0.9)',
    marginTop: 12,
  },
  errorContainer: {
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    marginVertical: 24,
    minWidth: 280,
  },
  errorText: {
    fontSize: 14,
    color: '#fff',
    textAlign: 'center',
    marginTop: 12,
    marginBottom: 8,
  },
  attemptsText: {
    fontSize: 12,
    color: 'rgba(255, 255, 255, 0.8)',
    textAlign: 'center',
    marginBottom: 16,
  },
  retryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#2196F3',
    fontSize: 14,
    fontWeight: '600',
    marginLeft: 8,
  },
  passwordButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 24,
  },
  passwordButtonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
    marginLeft: 8,
  },
});

export default BiometricAuthScreen;
