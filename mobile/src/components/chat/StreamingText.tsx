/**
 * StreamingText Component
 *
 * Displays text that streams in character-by-character or chunk-by-chunk,
 * similar to ChatGPT's streaming effect. Handles streaming state and
 * provides smooth animation for incoming text.
 */

import React, { useEffect, useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  Easing,
  Platform,
} from 'react-native';
import { useTheme } from 'react-native-paper';

interface StreamingTextProps {
  text: string;
  isStreaming?: boolean;
  onComplete?: () => void;
  speed?: number; // milliseconds per character (default: 20ms)
  style?: any;
  textStyle?: any;
}

/**
 * StreamingText Component
 *
 * Displays text with a streaming animation effect.
 * When isStreaming is true, animates text as it arrives.
 * When isStreaming is false or text is complete, displays full text.
 */
export const StreamingText: React.FC<StreamingTextProps> = ({
  text,
  isStreaming = false,
  onComplete,
  speed = 20,
  style,
  textStyle,
}) => {
  const theme = useTheme();
  const [displayedText, setDisplayedText] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  /**
   * Handle text streaming animation
   */
  useEffect(() => {
    if (!isStreaming) {
      // Not streaming, show full text immediately
      setDisplayedText(text);
      setCurrentIndex(text.length);

      // Fade in
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
        easing: Easing.out(Easing.ease),
      }).start();

      return;
    }

    // Streaming mode - animate character by character
    if (currentIndex < text.length) {
      const timeout = setTimeout(() => {
        setDisplayedText(text.substring(0, currentIndex + 1));
        setCurrentIndex(currentIndex + 1);
      }, speed);

      return () => clearTimeout(timeout);
    } else if (currentIndex === text.length && currentIndex > 0) {
      // Streaming complete
      onComplete?.();
    }
  }, [text, currentIndex, isStreaming, speed, fadeAnim, onComplete]);

  /**
   * Reset when text changes dramatically (new message)
   */
  useEffect(() => {
    if (!isStreaming) {
      setDisplayedText(text);
      setCurrentIndex(text.length);
    } else {
      // For streaming, start from current position
      if (text.length < currentIndex) {
        // Text was shortened, reset
        setDisplayedText('');
        setCurrentIndex(0);
      }
    }
  }, [text]);

  /**
   * Fade in animation when streaming starts
   */
  useEffect(() => {
    if (isStreaming && currentIndex === 0) {
      fadeAnim.setValue(0);
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
        easing: Easing.out(Easing.ease),
      }).start();
    }
  }, [isStreaming, currentIndex, fadeAnim]);

  return (
    <Animated.View
      style={[
        styles.container,
        { opacity: fadeAnim },
        style,
      ]}
    >
      <Text
        style={[
          styles.text,
          { color: theme.colors.onSurface },
          textStyle,
        ]}
      >
        {displayedText}
        {isStreaming && currentIndex < text.length && (
          <Text style={styles.cursor}>|</Text>
        )}
      </Text>
    </Animated.View>
  );
};

/**
 * StreamingChunk Component
 *
 * Alternative component that streams in chunks (words or phrases)
 * rather than character-by-character. Better for faster streaming.
 */
interface StreamingChunkProps {
  chunks: string[];
  isStreaming?: boolean;
  onComplete?: () => void;
  speed?: number; // milliseconds per chunk (default: 100ms)
  style?: any;
  textStyle?: any;
}

export const StreamingChunk: React.FC<StreamingChunkProps> = ({
  chunks,
  isStreaming = false,
  onComplete,
  speed = 100,
  style,
  textStyle,
}) => {
  const theme = useTheme();
  const [displayedChunks, setDisplayedChunks] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!isStreaming) {
      // Not streaming, show all chunks immediately
      setDisplayedChunks(chunks);
      setCurrentIndex(chunks.length);

      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }).start();

      return;
    }

    // Streaming mode
    if (currentIndex < chunks.length) {
      const timeout = setTimeout(() => {
        setDisplayedChunks([...displayedChunks, chunks[currentIndex]]);
        setCurrentIndex(currentIndex + 1);
      }, speed);

      return () => clearTimeout(timeout);
    } else if (currentIndex === chunks.length && currentIndex > 0) {
      onComplete?.();
    }
  }, [chunks, currentIndex, isStreaming, speed, displayedChunks, fadeAnim, onComplete]);

  useEffect(() => {
    if (!isStreaming) {
      setDisplayedChunks(chunks);
      setCurrentIndex(chunks.length);
    } else {
      if (chunks.length < currentIndex) {
        setDisplayedChunks([]);
        setCurrentIndex(0);
      }
    }
  }, [chunks]);

  return (
    <Animated.View
      style={[
        styles.container,
        { opacity: fadeAnim },
        style,
      ]}
    >
      <Text
        style={[
          styles.text,
          { color: theme.colors.onSurface },
          textStyle,
        ]}
      >
        {displayedChunks.join('')}
        {isStreaming && currentIndex < chunks.length && (
          <Text style={styles.cursor}>|</Text>
        )}
      </Text>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  text: {
    fontSize: 16,
    lineHeight: 24,
  },
  cursor: {
    opacity: 0.7,
    animation: 'blink 1s infinite',
  },
});

export default StreamingText;
