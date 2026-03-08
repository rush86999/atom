/**
 * Mobile Card Component
 *
 * A versatile card component for React Native with support for:
 * - Multiple variants (elevated, outlined, filled)
 * - Touch handling (optional)
 * - Custom content (children, title, description)
 * - Icon support
 * - Accessibility features
 * - Platform-specific styling (iOS/Android)
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ViewStyle,
  Platform,
  AccessibilityRole,
} from 'react-native';

export type CardVariant = 'elevated' | 'outlined' | 'filled';

interface CardProps {
  /** Card title */
  title?: string;
  /** Card description */
  description?: string;
  /** Card content (children) */
  children?: React.ReactNode;
  /** Card variant/style */
  variant?: CardVariant;
  /** Press handler (makes card clickable) */
  onPress?: () => void;
  /** Long press handler */
  onLongPress?: () => void;
  /** Disabled state */
  disabled?: boolean;
  /** Accessibility label */
  accessibilityLabel?: string;
  /** Accessibility hint */
  accessibilityHint?: string;
  /** Custom card style */
  cardStyle?: ViewStyle;
  /** Test ID for testing */
  testID?: string;
  /** Icon element (optional) */
  icon?: React.ReactNode;
  /** Custom background color */
  backgroundColor?: string;
  /** Border radius */
  borderRadius?: number;
  /** Padding */
  padding?: number;
}

export const Card: React.FC<CardProps> = ({
  title,
  description,
  children,
  variant = 'elevated',
  onPress,
  onLongPress,
  disabled = false,
  accessibilityLabel,
  accessibilityHint,
  cardStyle,
  testID,
  icon,
  backgroundColor,
  borderRadius = 12,
  padding = 16,
}) => {
  const getVariantStyles = (): ViewStyle => {
    switch (variant) {
      case 'outlined':
        return {
          backgroundColor: backgroundColor || '#FFFFFF',
          borderWidth: 1,
          borderColor: '#E5E7EB',
          ...Platform.select({
            ios: {
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 0 },
              shadowOpacity: 0,
              shadowRadius: 0,
            },
            android: {
              elevation: 0,
            },
          }),
        };
      case 'filled':
        return {
          backgroundColor: backgroundColor || '#F3F4F6',
          borderWidth: 0,
          ...Platform.select({
            ios: {
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 1 },
              shadowOpacity: 0.05,
              shadowRadius: 2,
            },
            android: {
              elevation: 1,
            },
          }),
        };
      default:
        return {
          backgroundColor: backgroundColor || '#FFFFFF',
          borderWidth: 0,
          ...Platform.select({
            ios: {
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 2 },
              shadowOpacity: 0.1,
              shadowRadius: 4,
            },
            android: {
              elevation: 3,
            },
          }),
        };
    }
  };

  const accessibilityRole: AccessibilityRole = onPress ? 'button' : 'none';

  const CardView = (
    <View
      testID={testID || 'card'}
      accessible={true}
      accessibilityLabel={accessibilityLabel || title}
      accessibilityHint={accessibilityHint}
      accessibilityRole={accessibilityRole}
      style={[
        styles.card,
        getVariantStyles(),
        { borderRadius, padding },
        disabled && styles.cardDisabled,
        cardStyle,
      ]}
    >
      {(title || description || icon) && (
        <View style={styles.header}>
          {icon && <View style={styles.iconContainer}>{icon}</View>}
          <View style={styles.headerContent}>
            {title && (
              <Text style={styles.title} numberOfLines={2}>
                {title}
              </Text>
            )}
            {description && (
              <Text style={styles.description} numberOfLines={3}>
                {description}
              </Text>
            )}
          </View>
        </View>
      )}
      {children && <View style={styles.content}>{children}</View>}
    </View>
  );

  if (onPress || onLongPress) {
    return (
      <TouchableOpacity
        onPress={onPress}
        onLongPress={onLongPress}
        disabled={disabled}
        activeOpacity={0.7}
      >
        {CardView}
      </TouchableOpacity>
    );
  }

  return CardView;
};

const styles = StyleSheet.create({
  card: {
    overflow: 'hidden',
  },
  cardDisabled: {
    opacity: 0.5,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  iconContainer: {
    marginRight: 12,
    marginTop: 2,
  },
  headerContent: {
    flex: 1,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 4,
  },
  description: {
    fontSize: 14,
    color: '#6B7280',
    lineHeight: 20,
  },
  content: {
    marginTop: 8,
  },
});

export default Card;
