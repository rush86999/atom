/**
 * CanvasTerminal Component
 *
 * Terminal emulator component for coding/orchestration canvas types.
 * Features monospace font, ANSI color support, auto-scroll, copy all, and font controls.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  View,
  StyleSheet,
  Text,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Keyboard,
} from 'react-native';
import { useTheme, IconButton, Portal, Dialog, Button, Menu } from 'react-native-paper';
import * as Clipboard from 'expo-clipboard';
import * as Haptics from 'expo-haptics';

interface TerminalOutput {
  type: 'stdout' | 'stderr' | 'command' | 'system';
  content: string;
  timestamp?: string;
}

interface CanvasTerminalProps {
  output: TerminalOutput[];
  style?: any;
  enableInput?: boolean;
  onCommand?: (command: string) => void;
  readonly?: boolean;
  autoScroll?: boolean;
  maxLines?: number;
  fontSize?: number;
  fontFamily?: string;
  darkTheme?: boolean;
}

/**
 * CanvasTerminal Component
 *
 * Renders terminal output with ANSI colors, auto-scroll, copy support, and font controls.
 */
export const CanvasTerminal: React.FC<CanvasTerminalProps> = ({
  output,
  style,
  enableInput = false,
  onCommand,
  readonly = true,
  autoScroll = true,
  maxLines = 1000,
  fontSize = 13,
  fontFamily = 'Courier',
  darkTheme = true,
}) => {
  const theme = useTheme();

  const scrollViewRef = useRef<ScrollView>(null);
  const textInputRef = useRef<TextInput>(null);

  const [currentFontSize, setCurrentFontSize] = useState(fontSize);
  const [wrapText, setWrapText] = useState(true);
  const [showMenu, setShowMenu] = useState(false);
  const [menuVisible, setMenuVisible] = useState(false);
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [inputValue, setInputValue] = useState('');

  // Auto-scroll to bottom when new output arrives
  useEffect(() => {
    if (autoScroll && scrollViewRef.current) {
      setTimeout(() => {
        scrollViewRef.current?.scrollToEnd({ animated: false });
      }, 50);
    }
  }, [output, autoScroll]);

  /**
   * Parse ANSI color codes
   */
  const parseAnsiColors = useCallback((text: string): Array<{ text: string; color?: string }> => {
    const ansiColors: Record<string, string> = {
      '30': '#000000', // Black
      '31': '#cd3131', // Red
      '32': '#0dbc79', // Green
      '33': '#e5e510', // Yellow
      '34': '#2472c8', // Blue
      '35': '#bc3fbc', // Magenta
      '36': '#11a8cd', // Cyan
      '37': '#e5e5e5', // White
      '90': '#666666', // Bright Black (Gray)
      '91': '#f14c4c', // Bright Red
      '92': '#23d18b', // Bright Green
      '93': '#f5f543', // Bright Yellow
      '94': '#3b8eea', // Bright Blue
      '95': '#d670d6', // Bright Magenta
      '96': '#29b8db', // Bright Cyan
      '97': '#ffffff', // Bright White
    };

    const ansiRegex = /\x1b\[(\d+)(;\d+)?m/g;
    const segments: Array<{ text: string; color?: string }> = [];
    let lastIndex = 0;
    let currentColor: string | undefined;

    let match;
    while ((match = ansiRegex.exec(text)) !== null) {
      // Add text before the ANSI code
      if (match.index > lastIndex) {
        segments.push({ text: text.slice(lastIndex, match.index), color: currentColor });
      }

      // Parse ANSI color code
      const colorCode = match[1];
      if (colorCode === '0') {
        // Reset
        currentColor = undefined;
      } else if (ansiColors[colorCode]) {
        currentColor = ansiColors[colorCode];
      }

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      segments.push({ text: text.slice(lastIndex), color: currentColor });
    }

    return segments.length > 0 ? segments : [{ text, color: undefined }];
  }, []);

  /**
   * Get text color by output type
   */
  const getOutputColor = useCallback((type: string) => {
    if (darkTheme) {
      switch (type) {
        case 'stdout':
          return '#e5e5e5';
        case 'stderr':
          return '#f14c4c';
        case 'command':
          return '#0dbc79';
        case 'system':
          return '#2472c8';
        default:
          return '#e5e5e5';
      }
    } else {
      switch (type) {
        case 'stdout':
          return '#000000';
        case 'stderr':
          return '#d32f2f';
        case 'command':
          return '#388e3c';
        case 'system':
          return '#1976d2';
        default:
          return '#000000';
      }
    }
  }, [darkTheme]);

  /**
   * Render output line with ANSI colors
   */
  const renderOutputLine = useCallback((line: TerminalOutput, index: number) => {
    const segments = parseAnsiColors(line.content);
    const baseColor = getOutputColor(line.type);

    return (
      <View key={index} style={styles.lineContainer}>
        {line.timestamp && (
          <Text style={[styles.timestamp, { color: getOutputColor('system') }]}>
            [{line.timestamp}]{' '}
          </Text>
        )}
        {segments.map((segment, segIndex) => (
          <Text
            key={segIndex}
            style={[
              styles.outputText,
              {
                color: segment.color || baseColor,
                fontSize: currentFontSize,
                fontFamily,
              },
              !wrapText && styles.noWrap,
            ]}
          >
            {segment.text}
          </Text>
        ))}
      </View>
    );
  }, [parseAnsiColors, getOutputColor, currentFontSize, fontFamily, wrapText]);

  /**
   * Copy all output to clipboard
   */
  const copyAll = useCallback(async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    const text = output.map(line => {
      const timestamp = line.timestamp ? `[${line.timestamp}] ` : '';
      return `${timestamp}${line.content}`;
    }).join('\n');

    await Clipboard.setStringAsync(text);
    setShowMenu(true);
  }, [output]);

  /**
   * Clear terminal
   */
  const clearTerminal = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    // Could emit clear event or callback
  }, []);

  /**
   * Increase font size
   */
  const increaseFontSize = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setCurrentFontSize(prev => Math.min(prev + 1, 24));
  }, []);

  /**
   * Decrease font size
   */
  const decreaseFontSize = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setCurrentFontSize(prev => Math.max(prev - 1, 10));
  }, []);

  /**
   * Reset font size
   */
  const resetFontSize = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setCurrentFontSize(fontSize);
  }, [fontSize]);

  /**
   * Toggle text wrap
   */
  const toggleWrap = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setWrapText(prev => !prev);
  }, []);

  /**
   * Handle command submit
   */
  const handleSubmit = useCallback(() => {
    if (!inputValue.trim() || !onCommand) return;

    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    const command = inputValue.trim();
    setCommandHistory(prev => [...prev, command]);
    setHistoryIndex(-1);
    setInputValue('');

    onCommand(command);
    Keyboard.dismiss();
  }, [inputValue, onCommand]);

  /**
   * Handle keyboard navigation in command history
   */
  const handleKeyPress = useCallback(
    (key: string) => {
      if (key === 'ArrowUp') {
        // Navigate back in history
        if (historyIndex === -1 && commandHistory.length > 0) {
          setHistoryIndex(commandHistory.length - 1);
          setInputValue(commandHistory[commandHistory.length - 1]);
        } else if (historyIndex > 0) {
          setHistoryIndex(historyIndex - 1);
          setInputValue(commandHistory[historyIndex - 1]);
        }
      } else if (key === 'ArrowDown') {
        // Navigate forward in history
        if (historyIndex < commandHistory.length - 1) {
          setHistoryIndex(historyIndex + 1);
          setInputValue(commandHistory[historyIndex + 1]);
        } else if (historyIndex === commandHistory.length - 1) {
          setHistoryIndex(-1);
          setInputValue('');
        }
      }
    },
    [commandHistory, historyIndex]
  );

  // Trim output to max lines
  const trimmedOutput = React.useMemo(() => {
    if (output.length <= maxLines) return output;
    return output.slice(-maxLines);
  }, [output, maxLines]);

  const backgroundColor = darkTheme ? '#1e1e1e' : '#ffffff';
  const headerBackgroundColor = darkTheme ? '#2d2d2d' : '#f5f5f5';

  return (
    <View style={[styles.container, { backgroundColor }, style]}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: headerBackgroundColor }]}>
        <Text style={[styles.headerTitle, { color: darkTheme ? '#e5e5e5' : '#000000' }]}>
          Terminal
        </Text>
        <View style={styles.headerActions}>
          <IconButton
            icon="format-font-size-decrease"
            size={18}
            onPress={decreaseFontSize}
            color={darkTheme ? '#e5e5e5' : '#000000'}
          />
          <IconButton
            icon="format-font-size-increase"
            size={18}
            onPress={increaseFontSize}
            color={darkTheme ? '#e5e5e5' : '#000000'}
          />
          <IconButton
            icon="wrap-text"
            size={18}
            onPress={toggleWrap}
            color={wrapText ? (darkTheme ? '#0dbc79' : '#388e3c') : (darkTheme ? '#666666' : '#999999')}
          />
          <IconButton
            icon="content-copy"
            size={18}
            onPress={copyAll}
            color={darkTheme ? '#e5e5e5' : '#000000'}
          />
          <IconButton
            icon="dots-vertical"
            size={18}
            onPress={() => setMenuVisible(true)}
            color={darkTheme ? '#e5e5e5' : '#000000'}
          />
        </View>
      </View>

      {/* Terminal output */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.terminal}
        contentContainerStyle={styles.terminalContent}
        showsVerticalScrollIndicator={true}
        nestedScrollEnabled
      >
        {trimmedOutput.length === 0 ? (
          <Text
            style={[
              styles.emptyText,
              {
                color: darkTheme ? '#666666' : '#999999',
                fontSize: currentFontSize,
                fontFamily,
              },
            ]}
          >
            No output yet...
          </Text>
        ) : (
          trimmedOutput.map((line, index) => renderOutputLine(line, index))
        )}
      </ScrollView>

      {/* Input field (if enabled) */}
      {enableInput && !readonly && (
        <View style={[styles.inputContainer, { borderTopColor: darkTheme ? '#333333' : '#e0e0e0' }]}>
          <Text
            style={[styles.prompt, { color: darkTheme ? '#0dbc79' : '#388e3c', fontSize: currentFontSize, fontFamily }]}
          >
            $
          </Text>
          <TextInput
            ref={textInputRef}
            style={[
              styles.input,
              {
                color: darkTheme ? '#e5e5e5' : '#000000',
                fontSize: currentFontSize,
                fontFamily,
              },
            ]}
            value={inputValue}
            onChangeText={setInputValue}
            onSubmitEditing={handleSubmit}
            placeholder="Type a command..."
            placeholderTextColor={darkTheme ? '#666666' : '#999999'}
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="send"
          />
          <IconButton
            icon="send"
            size={20}
            onPress={handleSubmit}
            disabled={!inputValue.trim()}
            color={darkTheme ? '#0dbc79' : '#388e3c'}
          />
        </View>
      )}

      {/* Menu */}
      <Menu
        visible={menuVisible}
        onDismiss={() => setMenuVisible(false)}
        anchor={{ x: 0, y: 0 }} // Position manually via icon
      >
        <Menu.Item
          leadingIcon="magnify-plus-outline"
          onPress={() => {
            increaseFontSize();
            setMenuVisible(false);
          }}
          title="Increase Font"
        />
        <Menu.Item
          leadingIcon="magnify-minus-outline"
          onPress={() => {
            decreaseFontSize();
            setMenuVisible(false);
          }}
          title="Decrease Font"
        />
        <Menu.Item
          leadingIcon="format-font-size"
          onPress={() => {
            resetFontSize();
            setMenuVisible(false);
          }}
          title="Reset Font"
        />
        <Menu.Item
          leadingIcon={wrapText ? 'wrap-disabled' : 'wrap'}
          onPress={() => {
            toggleWrap();
            setMenuVisible(false);
          }}
          title={wrapText ? 'Disable Wrap' : 'Enable Wrap'}
        />
        <Menu.Item
          leadingIcon="content-copy"
          onPress={() => {
            copyAll();
            setMenuVisible(false);
          }}
          title="Copy All"
        />
        <Menu.Item
          leadingIcon="delete-sweep"
          onPress={() => {
            clearTerminal();
            setMenuVisible(false);
          }}
          title="Clear Terminal"
        />
      </Menu>

      {/* Copied confirmation */}
      <Portal>
        <Dialog visible={showMenu} onDismiss={() => setShowMenu(false)}>
          <Dialog.Title>Copied</Dialog.Title>
          <Dialog.Content>
            <Text>All output copied to clipboard</Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setShowMenu(false)}>OK</Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#333333',
  },
  headerTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  terminal: {
    flex: 1,
  },
  terminalContent: {
    padding: 12,
    flexGrow: 1,
  },
  lineContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: 2,
  },
  outputText: {
    lineHeight: 18,
  },
  noWrap: {
    flexShrink: 1,
  },
  timestamp: {
    fontSize: 11,
    opacity: 0.7,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
  },
  prompt: {
    marginRight: 8,
    fontWeight: '600',
  },
  input: {
    flex: 1,
    paddingVertical: 4,
  },
  emptyText: {
    textAlign: 'center',
    marginTop: 24,
  },
});

export default CanvasTerminal;
