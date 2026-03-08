/**
 * Mobile Button Component
 *
 * A touch-friendly button component for React Native with support for:
 * - Multiple variants (primary, secondary, destructive, outline, ghost)
 * - Multiple sizes (small, medium, large)
 * - Disabled state
 * - Loading state
 * - Icon support
 * - Accessibility features
 */

import React from 'react';
import {
  TouchableOpacity,
  Text,
  StyleSheet,
  ActivityIndicator,
  ViewStyle,
  TextStyle,
  AccessibilityState,
} from 'react-native';

export type ButtonVariant = 'primary' | 'secondary' | 'destructive' | 'outline' | 'ghost';
export type ButtonSize = 'small' | 'medium' | 'large';

interface ButtonProps {
  /** Button title/text */
  title: string;
  /** Press handler */
  onPress: () => void;
  /** Button variant/style */
  variant?: ButtonVariant;
  /** Button size */
  size?: ButtonSize;
  /** Disabled state */
  disabled?: boolean;
  /** Loading state (shows spinner) */
  loading?: boolean;
  /** Accessibility label */
  accessibilityLabel?: string;
  /** Accessibility hint */
  accessibilityHint?: string;
  /** Custom button style */
  buttonStyle?: ViewStyle;
  /** Custom text style */
  textStyle?: TextStyle;
  /** Test ID for testing */
  testID?: string;
  /** Icon element (optional) */
  icon?: React.ReactNode;
  /** Icon position */
  iconPosition?: 'left' | 'right';
}

export const Button: React.FC<ButtonProps> = ({
  title,
  onPress,
  variant = 'primary',
  size = 'medium',
  disabled = false,
  loading = false,
  accessibilityLabel,
  accessibilityHint,
  buttonStyle,
  textStyle,
  testID,
  icon,
  iconPosition = 'left',
}) => {
  const getVariantStyles = (): { button: ViewStyle; text: TextStyle } => {
    switch (variant) {
      case 'secondary':
        return {
          button: styles.buttonSecondary,
          text: styles.textSecondary,
        };
      case 'destructive':
        return {
          button: styles.buttonDestructive,
          text: styles.textDestructive,
        };
      case 'outline':
        return {
          button: styles.buttonOutline,
          text: styles.textOutline,
        };
      case 'ghost':
        return {
          button: styles.buttonGhost,
          text: styles.textGhost,
        };
      default:
        return {
          button: styles.buttonPrimary,
          text: styles.textPrimary,
        };
    }
  };

  const getSizeStyles = (): ViewStyle => {
    switch (size) {
      case 'small':
        return styles.buttonSmall;
      case 'large':
        return styles.buttonLarge;
      default:
        return styles.buttonMedium;
    }
  };

  const variantStyles = getVariantStyles();
  const sizeStyles = getSizeStyles();
  const isDisabled = disabled || loading;

  const accessibilityState: AccessibilityState = {
    disabled: isDisabled,
    busy: loading,
  };

  return (
    <TouchableOpacity
      testID={testID || 'button'}
      accessible={true}
      accessibilityLabel={accessibilityLabel || title}
      accessibilityHint={accessibilityHint}
      accessibilityRole="button"
      accessibilityState={accessibilityState}
      disabled={isDisabled}
      onPress={onPress}
      activeOpacity={0.7}
      style={[
        styles.button,
        variantStyles.button,
        sizeStyles,
        isDisabled && styles.buttonDisabled,
        buttonStyle,
      ]}
    >
      {loading ? (
        <ActivityIndicator
          testID="button-loading"
          color={variant === 'outline' || variant === 'ghost' ? '#007AFF' : '#FFFFFF'}
          size={size === 'small' ? 'small' : 'small'}
        />
      ) : (
        <>
          {icon && iconPosition === 'left' && (
            <>{icon}</>
          )}
          <Text
            style={[
              styles.text,
              variantStyles.text,
              sizeStyles.text,
              isDisabled && styles.textDisabled,
              textStyle,
            ]}
          >
            {title}
          </Text>
          {icon && iconPosition === 'right' && (
            <>{icon}</>
          )}
        </>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    flexDirection: 'row',
    overflow: 'hidden',
  },
  buttonPrimary: {
    backgroundColor: '#007AFF',
  },
  buttonSecondary: {
    backgroundColor: '#5856D6',
  },
  buttonDestructive: {
    backgroundColor: '#FF3B30',
  },
  buttonOutline: {
    backgroundColor: 'transparent',
    borderWidth: 1.5,
    borderColor: '#007AFF',
  },
  buttonGhost: {
    backgroundColor: 'transparent',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonSmall: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    minHeight: 32,
  },
  buttonMedium: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    minHeight: 44,
  },
  buttonLarge: {
    paddingHorizontal: 24,
    paddingVertical: 16,
    minHeight: 52,
  },
  text: {
    fontWeight: '600',
    textAlign: 'center',
  },
  textPrimary: {
    color: '#FFFFFF',
  },
  textSecondary: {
    color: '#FFFFFF',
  },
  textDestructive: {
    color: '#FFFFFF',
  },
  textOutline: {
    color: '#007AFF',
  },
  textGhost: {
    color: '#007AFF',
  },
  textDisabled: {
    color: '#999999',
  },
  textSmall: {
    fontSize: 14,
  },
  textMedium: {
    fontSize: 16,
  },
  textLarge: {
    fontSize: 18,
  },
});

export default Button;
