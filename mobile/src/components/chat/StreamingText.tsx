/**
 * StreamingText Component
 *
 * Enhanced streaming text with markdown support, code highlighting,
 * governance badges, and special card rendering for canvas/workflow/form mentions.
 */

import React, { useEffect, useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  Easing,
  Platform,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { useTheme, Icon } from 'react-native-paper';
import { Markdown } from 'react-native-markdown-display';
import { Prism } from 'react-native-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

// Types
interface StreamingTextProps {
  text: string;
  isStreaming?: boolean;
  onComplete?: () => void;
  speed?: number; // milliseconds per character (default: 20ms)
  style?: any;
  textStyle?: any;
  enableMarkdown?: boolean;
  maxHeight?: number;
}

interface SpecialCard {
  type: 'canvas' | 'workflow' | 'form';
  id: string;
  title: string;
  metadata?: Record<string, any>;
}

/**
 * StreamingText Component
 *
 * Enhanced streaming text with markdown support and smooth animation.
 */
export const StreamingText: React.FC<StreamingTextProps> = ({
  text,
  isStreaming = false,
  onComplete,
  speed = 20,
  style,
  textStyle,
  enableMarkdown = true,
  maxHeight = 300,
}) => {
  const theme = useTheme();
  const [displayedText, setDisplayedText] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);
  const [specialCards, setSpecialCards] = useState<SpecialCard[]>([]);
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const cursorAnim = useRef(new Animated.Value(1)).current;

  /**
   * Detect special cards in text (canvas/workflow/form mentions)
   */
  useEffect(() => {
    const cards: SpecialCard[] = [];

    // Canvas mentions: [[canvas:canvas-id]]
    const canvasMatches = text.matchAll(/\[\[canvas:([^\]]+)\]\]/g);
    for (const match of canvasMatches) {
      cards.push({
        type: 'canvas',
        id: match[1],
        title: `Canvas: ${match[1]}`,
      });
    }

    // Workflow mentions: [[workflow:workflow-id]]
    const workflowMatches = text.matchAll(/\[\[workflow:([^\]]+)\]\]/g);
    for (const match of workflowMatches) {
      cards.push({
        type: 'workflow',
        id: match[1],
        title: `Workflow: ${match[1]}`,
      });
    }

    // Form mentions: [[form:form-id]]
    const formMatches = text.matchAll(/\[\[form:([^\]]+)\]\]/g);
    for (const match of formMatches) {
      cards.push({
        type: 'form',
        id: match[1],
        title: `Form: ${match[1]}`,
      });
    }

    setSpecialCards(cards);
  }, [text]);

  /**
   * Cursor blinking animation
   */
  useEffect(() => {
    if (isStreaming) {
      const blinkAnimation = Animated.loop(
        Animated.sequence([
          Animated.timing(cursorAnim, {
            toValue: 0,
            duration: 500,
            useNativeDriver: true,
          }),
          Animated.timing(cursorAnim, {
            toValue: 1,
            duration: 500,
            useNativeDriver: true,
          }),
        ])
      );
      blinkAnimation.start();
      return () => blinkAnimation.stop();
    }
  }, [isStreaming, cursorAnim]);

  /**
   * Handle text streaming animation
   */
  useEffect(() => {
    if (!isStreaming) {
      // Not streaming, show full text immediately
      setDisplayedText(text);
      setCurrentIndex(text.length);

      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
        easing: Easing.out(Easing.ease),
      }).start();

      return;
    }

    // Streaming mode - animate smoothly without jitter
    if (currentIndex < text.length) {
      // Use requestAnimationFrame for smooth updates
      const animationFrame = requestAnimationFrame(() => {
        const timeout = setTimeout(() => {
          setDisplayedText(text.substring(0, currentIndex + 1));
          setCurrentIndex(currentIndex + 1);
        }, speed);

        return () => clearTimeout(timeout);
      });

      return () => cancelAnimationFrame(animationFrame);
    } else if (currentIndex === text.length && currentIndex > 0) {
      onComplete?.();
    }
  }, [text, currentIndex, isStreaming, speed, fadeAnim, onComplete]);

  /**
   * Reset when text changes
   */
  useEffect(() => {
    if (!isStreaming) {
      setDisplayedText(text);
      setCurrentIndex(text.length);
    } else {
      if (text.length < currentIndex) {
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

  /**
   * Check if text is too long
   */
  const isTextTooLong = displayedText.length > 500 && !isExpanded;

  /**
   * Get display text (truncated if needed)
   */
  const getDisplayText = () => {
    if (isTextTooLong) {
      return displayedText.substring(0, 500) + '...';
    }
    return displayedText;
  };

  /**
   * Render special card
   */
  const renderSpecialCard = (card: SpecialCard) => (
    <TouchableOpacity
      key={`${card.type}-${card.id}`}
      style={[styles.card, { backgroundColor: theme.colors.surfaceVariant }]}
      onPress={() => {
        // Handle card press - navigate to detail
        console.log('Card pressed:', card);
      }}
    >
      <Icon
        source={
          card.type === 'canvas'
            ? 'presentation'
            : card.type === 'workflow'
              ? 'robot'
              : 'form-select'
        }
        size={20}
        color={theme.colors.primary}
      />
      <Text style={[styles.cardTitle, { color: theme.colors.onSurface }]}>
        {card.title}
      </Text>
      <Icon
        source="chevron-right"
        size={16}
        color={theme.colors.onSurfaceVariant}
      />
    </TouchableOpacity>
  );

  /**
   * Render markdown content
   */
  const renderMarkdown = (content: string) => {
    return (
      <Markdown
        style={markdownStyles(theme)}
        mergeStyle={true}
      >
        {content}
      </Markdown>
    );
  };

  /**
   * Render code block with syntax highlighting
   */
  const renderCodeBlock = (code: string, language: string = 'text') => {
    return (
      <View style={[styles.codeBlockContainer, { backgroundColor: '#1e1e1e' }]}>
        <View style={styles.codeBlockHeader}>
          <Text style={styles.codeLanguage}>{language}</Text>
          <TouchableOpacity
            onPress={() => {
              // Copy code to clipboard
              console.log('Copy code:', code);
            }}
          >
            <Icon
              source="content-copy"
              size={16}
              color="#888"
            />
          </TouchableOpacity>
        </View>
        <ScrollView horizontal style={styles.codeScroll}>
          <Prism
            language={language}
            style={vscDarkPlus}
            customStyle={styles.codeBlock}
          >
            {code}
          </Prism>
        </ScrollView>
      </View>
    );
  };

  /**
   * Check if content has code blocks
   */
  const hasCodeBlocks = /```[\s\S]*?```/.test(displayedText);

  return (
    <Animated.View
      style={[
        styles.container,
        { opacity: fadeAnim },
        style,
      ]}
    >
      {enableMarkdown && !hasCodeBlocks ? (
        <ScrollView style={{ maxHeight: isExpanded ? undefined : maxHeight }}>
          {renderMarkdown(getDisplayText())}
        </ScrollView>
      ) : hasCodeBlocks ? (
        <ScrollView style={{ maxHeight: isExpanded ? undefined : maxHeight }}>
          {displayedText.split(/```(\w+)?\n([\s\S]*?)```/g).map((part, index) => {
            if (index % 3 === 1) {
              // Language
              return null;
            } else if (index % 3 === 2) {
              // Code content
              return (
                <View key={index}>
                  {renderCodeBlock(part, displayedText.split(/```(\w+)?\n/)[index - 1] || 'text')}
                </View>
              );
            } else {
              // Regular text
              return part ? <Text key={index} style={[styles.text, { color: theme.colors.onSurface }, textStyle]}>{part}</Text> : null;
            }
          })}
        </ScrollView>
      ) : (
        <Text
          style={[
            styles.text,
            { color: theme.colors.onSurface },
            textStyle,
          ]}
        >
          {getDisplayText()}
          {isStreaming && currentIndex < text.length && (
            <Animated.Text style={[styles.cursor, { opacity: cursorAnim }]}>|</Animated.Text>
          )}
        </Text>
      )}

      {/* Special cards */}
      {specialCards.length > 0 && (
        <View style={styles.cardsContainer}>
          {specialCards.map(renderSpecialCard)}
        </View>
      )}

      {/* Show more button */}
      {isTextTooLong && (
        <TouchableOpacity onPress={() => setIsExpanded(true)}>
          <Text style={[styles.showMore, { color: theme.colors.primary }]}>
            Show more
          </Text>
        </TouchableOpacity>
      )}

      {/* Progress indicator during streaming */}
      {isStreaming && currentIndex > 0 && currentIndex % 50 === 0 && (
        <View style={styles.progressContainer}>
          <View style={[styles.progressBar, { backgroundColor: theme.colors.surfaceVariant }]}>
            <View
              style={[
                styles.progressFill,
                {
                  backgroundColor: theme.colors.primary,
                  width: `${(currentIndex / text.length) * 100}%`,
                },
              ]}
            />
          </View>
        </View>
      )}
    </Animated.View>
  );
};

/**
 * Markdown styles
 */
const markdownStyles = (theme: any) => ({
  body: { fontSize: 16, lineHeight: 24, color: theme.colors.onSurface },
  heading1: { fontSize: 24, fontWeight: 'bold', marginBottom: 8, color: theme.colors.onSurface },
  heading2: { fontSize: 20, fontWeight: 'bold', marginBottom: 6, color: theme.colors.onSurface },
  heading3: { fontSize: 18, fontWeight: 'bold', marginBottom: 4, color: theme.colors.onSurface },
  strong: { fontWeight: 'bold', color: theme.colors.onSurface },
  em: { fontStyle: 'italic', color: theme.colors.onSurface },
  link: { color: theme.colors.primary, textDecorationLine: 'underline' },
  blockquote: {
    borderLeftWidth: 4,
    borderLeftColor: theme.colors.primary,
    paddingLeft: 12,
    marginBottom: 8,
    fontStyle: 'italic',
    color: theme.colors.onSurfaceVariant,
  },
  code_inline: {
    backgroundColor: theme.colors.surfaceVariant,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 14,
    color: theme.colors.onSurface,
  },
  code_block: {
    backgroundColor: '#1e1e1e',
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
    overflow: 'hidden',
  },
  fence: {
    backgroundColor: '#1e1e1e',
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
  },
  list_item: {
    flexDirection: 'row',
    marginBottom: 4,
    color: theme.colors.onSurface,
  },
  bullet_list: {
    marginLeft: 20,
    marginBottom: 8,
  },
  ordered_list: {
    marginLeft: 20,
    marginBottom: 8,
  },
  hr: {
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.outline,
    marginVertical: 12,
  },
  table: {
    borderWidth: 1,
    borderColor: theme.colors.outline,
    borderRadius: 8,
    marginBottom: 8,
    overflow: 'hidden',
  },
  thead: {
    backgroundColor: theme.colors.surfaceVariant,
  },
  th: {
    padding: 8,
    borderRightWidth: 1,
    borderRightColor: theme.colors.outline,
    fontWeight: 'bold',
    color: theme.colors.onSurface,
  },
  td: {
    padding: 8,
    borderRightWidth: 1,
    borderRightColor: theme.colors.outline,
    color: theme.colors.onSurface,
  },
});

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
  text: {
    fontSize: 16,
    lineHeight: 24,
  },
  cursor: {
    color: '#2196F3',
    fontWeight: 'bold',
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 8,
    marginTop: 8,
    borderWidth: 1,
  },
  cardTitle: {
    flex: 1,
    marginLeft: 8,
    fontSize: 14,
    fontWeight: '600',
  },
  cardsContainer: {
    marginTop: 12,
    gap: 8,
  },
  showMore: {
    fontSize: 14,
    fontWeight: '600',
    marginTop: 8,
    textAlign: 'center',
  },
  progressContainer: {
    marginTop: 12,
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
  codeBlockContainer: {
    borderRadius: 8,
    marginBottom: 8,
    overflow: 'hidden',
  },
  codeBlockHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#333',
  },
  codeLanguage: {
    fontSize: 12,
    color: '#888',
    fontWeight: '600',
  },
  codeScroll: {
    paddingHorizontal: 12,
  },
  codeBlock: {
    fontSize: 13,
    lineHeight: 20,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
});

export default StreamingText;
