/**
 * TypingIndicator Component
 *
 * Animated typing indicator showing when agents are responding.
 * Supports multiple agents with smooth entrance/exit animations.
 */

import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated, Easing } from 'react-native';
import { Avatar } from 'react-native-paper';

// Types
interface TypingAgent {
  id: string;
  name: string;
  avatar_url?: string;
}

interface TypingIndicatorProps {
  agents: TypingAgent[];
  visible?: boolean;
}

/**
 * TypingIndicator Component
 *
 * Shows animated dots when agents are typing
 */
export const TypingIndicator: React.FC<TypingIndicatorProps> = ({
  agents,
  visible = true,
}) => {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(20)).current;
  const dotAnims = useRef([
    new Animated.Value(0),
    new Animated.Value(0),
    new Animated.Value(0),
  ]).current;

  /**
   * Animate dots bouncing
   */
  useEffect(() => {
    if (!visible) return;

    const createDotAnimation = (anim: Animated.Value, delay: number) => {
      return Animated.loop(
        Animated.sequence([
          Animated.timing(anim, {
            toValue: -10,
            duration: 400,
            delay,
            useNativeDriver: true,
            easing: Easing.inOut(Easing.ease),
          }),
          Animated.timing(anim, {
            toValue: 0,
            duration: 400,
            useNativeDriver: true,
            easing: Easing.inOut(Easing.ease),
          }),
        ])
      );
    };

    const animations = dotAnims.map((anim, index) =>
      createDotAnimation(anim, index * 150)
    );

    animations.forEach((anim) => anim.start());

    return () => {
      animations.forEach((anim) => anim.stop());
    };
  }, [visible, dotAnims]);

  /**
   * Animate entrance
   */
  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 300,
          useNativeDriver: true,
          easing: Easing.out(Easing.ease),
        }),
        Animated.timing(slideAnim, {
          toValue: 0,
          duration: 300,
          useNativeDriver: true,
          easing: Easing.out(Easing.ease),
        }),
      ]).start();
    } else {
      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(slideAnim, {
          toValue: 20,
          duration: 200,
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [visible, fadeAnim, slideAnim]);

  if (agents.length === 0) return null;

  const getAgentInitials = (name: string) => {
    return name
      .split(' ')
      .map((word) => word[0])
      .join('')
      .substring(0, 2)
      .toUpperCase();
  };

  const getAgentLabel = () => {
    if (agents.length === 1) {
      return agents[0].name;
    } else if (agents.length === 2) {
      return `${agents[0].name} and ${agents[1].name}`;
    } else {
      return `${agents[0].name} and ${agents.length - 1} others`;
    }
  };

  return (
    <Animated.View
      style={[
        styles.container,
        {
          opacity: fadeAnim,
          transform: [{ translateY: slideAnim }],
        },
      ]}
    >
      {/* Avatar */}
      <Avatar.Text
        size={32}
        label={getAgentInitials(agents[0].name)}
        style={styles.avatar}
      />

      {/* Typing bubble */}
      <View style={styles.bubble}>
        <Text style={styles.label}>{getAgentLabel()}</Text>
        <Text style={styles.typingText}>is typing</Text>

        {/* Animated dots */}
        <View style={styles.dotsContainer}>
          <Animated.View
            style={[
              styles.dot,
              { transform: [{ translateY: dotAnims[0] }] },
            ]}
          />
          <Animated.View
            style={[
              styles.dot,
              { transform: [{ translateY: dotAnims[1] }] },
            ]}
          />
          <Animated.View
            style={[
              styles.dot,
              { transform: [{ translateY: dotAnims[2] }] },
            ]}
          />
        </View>
      </View>
    </Animated.View>
  );
};

/**
 * CompactTypingIndicator Component
 *
 * Smaller version for inline use
 */
export const CompactTypingIndicator: React.FC<{ visible?: boolean }> = ({ visible = true }) => {
  const fadeAnim = useRef(new Animated.Value(visible ? 1 : 0)).current;
  const dotAnims = useRef([
    new Animated.Value(0),
    new Animated.Value(0),
    new Animated.Value(0),
  ]).current;

  useEffect(() => {
    if (!visible) {
      Animated.timing(fadeAnim, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }).start();
      return;
    }

    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 300,
      useNativeDriver: true,
    }).start();

    const createDotAnimation = (anim: Animated.Value, delay: number) => {
      return Animated.loop(
        Animated.sequence([
          Animated.timing(anim, {
            toValue: -8,
            duration: 300,
            delay,
            useNativeDriver: true,
          }),
          Animated.timing(anim, {
            toValue: 0,
            duration: 300,
            useNativeDriver: true,
          }),
        ])
      );
    };

    const animations = dotAnims.map((anim, index) =>
      createDotAnimation(anim, index * 100)
    );

    animations.forEach((anim) => anim.start());

    return () => {
      animations.forEach((anim) => anim.stop());
    };
  }, [visible, fadeAnim, dotAnims]);

  return (
    <Animated.View style={[styles.compactContainer, { opacity: fadeAnim }]}>
      <Animated.View
        style={[styles.compactDot, { transform: [{ translateY: dotAnims[0] }] }]}
      />
      <Animated.View
        style={[styles.compactDot, { transform: [{ translateY: dotAnims[1] }] }]}
      />
      <Animated.View
        style={[styles.compactDot, { transform: [{ translateY: dotAnims[2] }] }]}
      />
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
    marginHorizontal: 16,
    marginBottom: 8,
  },
  avatar: {
    marginRight: 8,
  },
  bubble: {
    backgroundColor: '#F5F5F5',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 16,
    borderBottomLeftRadius: 4,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: '#333',
    marginBottom: 2,
  },
  typingText: {
    fontSize: 12,
    color: '#666',
  },
  dotsContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
    marginLeft: 4,
    gap: 4,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#999',
  },
  compactContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    gap: 4,
  },
  compactDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#999',
  },
});

export default TypingIndicator;
