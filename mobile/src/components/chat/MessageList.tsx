/**
 * MessageList Component
 *
 * Enhanced message list with message grouping, timestamps, actions,
 * scroll management, and read receipts.
 */

import React, { useRef, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useTheme, Avatar, Badge, Menu, FAB } from 'react-native-paper';
import { Icon } from 'react-native-paper';
import { formatDistanceToNow, differenceInDays, isToday, isYesterday } from 'date-fns';
import StreamingText from './StreamingText';

// Types
interface Message {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  agent_id?: string;
  agent_name?: string;
  agent_maturity?: 'STUDENT' | 'INTERN' | 'SUPERVISED' | 'AUTONOMOUS';
  timestamp: Date;
  isStreaming?: boolean;
  governance?: {
    action_complexity?: number;
    requires_approval?: boolean;
    supervised?: boolean;
  };
  episode_context?: {
    episode_id: string;
    title: string;
    relevance_score: number;
  };
}

interface MessageListProps {
  messages: Message[];
  onEpisodePress?: (episodeId: string) => void;
  onAgentPress?: (agentId: string) => void;
  loading?: boolean;
  ListHeaderComponent?: React.ComponentType;
  ListFooterComponent?: React.ComponentType;
  onMessageCopy?: (messageId: string) => void;
  onMessageFeedback?: (messageId: string, rating: number) => void;
  onMessageRegenerate?: (messageId: string) => void;
  onMessageDelete?: (messageId: string) => void;
}

/**
 * MessageItem Component
 *
 * Individual message display with avatar, content, and metadata
 */
interface MessageItemProps {
  message: Message;
  onEpisodePress?: (episodeId: string) => void;
  onAgentPress?: (agentId: string) => void;
  onMessageCopy?: (messageId: string) => void;
  onMessageFeedback?: (messageId: string, rating: number) => void;
  onMessageRegenerate?: (messageId: string) => void;
  onMessageDelete?: (messageId: string) => void;
}

const MessageItem: React.FC<MessageItemProps> = ({
  message,
  onEpisodePress,
  onAgentPress,
  onMessageCopy,
  onMessageFeedback,
  onMessageRegenerate,
  onMessageDelete,
}) => {
  const theme = useTheme();
  const [menuVisible, setMenuVisible] = useState(false);
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  /**
   * Get maturity badge color
   */
  const getMaturityColor = (maturity?: string) => {
    switch (maturity) {
      case 'AUTONOMOUS':
        return theme.colors.primary;
      case 'SUPERVISED':
        return theme.colors.tertiary;
      case 'INTERN':
        return theme.colors.secondary;
      case 'STUDENT':
        return theme.colors.error;
      default:
        return theme.colors.surfaceVariant;
    }
  };

  /**
   * Get action complexity label
   */
  const getComplexityLabel = (complexity?: number) => {
    if (!complexity) return null;
    switch (complexity) {
      case 1:
        return 'LOW';
      case 2:
        return 'MODERATE';
      case 3:
        return 'HIGH';
      case 4:
        return 'CRITICAL';
      default:
        return null;
    }
  };

  /**
   * Render governance badges
   */
  const renderGovernanceBadges = () => {
    if (isUser || isSystem || !message.governance) return null;

    const badges = [];

    if (message.agent_maturity) {
      badges.push(
        <Badge
          key="maturity"
          style={[styles.badge, { backgroundColor: getMaturityColor(message.agent_maturity) }]}
        >
          {message.agent_maturity}
        </Badge>
      );
    }

    if (message.governance.supervised) {
      badges.push(
        <Badge key="supervised" style={[styles.badge, { backgroundColor: theme.colors.tertiary }]}>
          SUPERVISED
        </Badge>
      );
    }

    if (message.governance.requires_approval) {
      badges.push(
        <Badge key="approval" style={[styles.badge, { backgroundColor: theme.colors.error }]}>
          REQUIRES APPROVAL
        </Badge>
      );
    }

    const complexityLabel = getComplexityLabel(message.governance.action_complexity);
    if (complexityLabel) {
      badges.push(
        <Badge key="complexity" style={[styles.badge, { backgroundColor: theme.colors.surfaceVariant }]}>
          {complexityLabel}
        </Badge>
      );
    }

    if (badges.length === 0) return null;

    return <View style={styles.badgeContainer}>{badges}</View>;
  };

  /**
   * Render episode context chips
   */
  const renderEpisodeContext = () => {
    if (!message.episode_context) return null;

    return (
      <TouchableOpacity
        style={[styles.episodeChip, { borderColor: theme.colors.outline }]}
        onPress={() => onEpisodePress?.(message.episode_context!.episode_id)}
      >
        <Text style={[styles.episodeChipText, { color: theme.colors.primary }]}>
          💾 {message.episode_context.title}
        </Text>
        <Text style={[styles.episodeChipScore, { color: theme.colors.onSurfaceVariant }]}>
          {Math.round(message.episode_context.relevance_score * 100)}% relevant
        </Text>
      </TouchableOpacity>
    );
  };

  /**
   * Render avatar
   */
  const renderAvatar = () => {
    if (isSystem) {
      return (
        <Avatar.Icon
          size={32}
          icon="information"
          style={{ backgroundColor: theme.colors.surfaceVariant }}
        />
      );
    }

    if (isUser) {
      return (
        <Avatar.Icon
          size={32}
          icon="account"
          style={{ backgroundColor: theme.colors.primary }}
        />
      );
    }

    return (
      <TouchableOpacity onPress={() => onAgentPress?.(message.agent_id || '')}>
        <Avatar.Text
          size={32}
          label={message.agent_name?.substring(0, 2).toUpperCase() || 'AI'}
          style={{ backgroundColor: getMaturityColor(message.agent_maturity) }}
        />
      </TouchableOpacity>
    );
  };

  return (
    <TouchableOpacity
      onLongPress={() => setMenuVisible(true)}
      delayLongPress={500}
    >
      <View
        style={[
          styles.messageContainer,
          isUser ? styles.userMessage : styles.agentMessage,
        ]}
      >
        {!isUser && renderAvatar()}

        <View
          style={[
            styles.messageBubble,
            { backgroundColor: isUser ? theme.colors.primaryContainer : theme.colors.surfaceVariant },
          ]}
        >
          {/* Show agent name for first message in group */}
          {!isUser && message.agent_name && (message as any).showTimestamp !== false && (
            <Text style={[styles.agentName, { color: theme.colors.onSurfaceVariant }]}>
              {message.agent_name}
            </Text>
          )}

          {message.isStreaming ? (
            <StreamingText
              text={message.content}
              isStreaming={true}
              textStyle={[styles.messageText, { color: theme.colors.onSurface }]}
            />
          ) : (
            <Text style={[styles.messageText, { color: theme.colors.onSurface }]}>
              {message.content}
            </Text>
          )}

          {renderEpisodeContext()}
          {renderGovernanceBadges()}

          {/* Show timestamp for first message in group or last message */}
          {(message as any).showTimestamp !== false && (
            <View style={styles.timestampRow}>
              <Text style={[styles.timestamp, { color: theme.colors.onSurfaceVariant }]}>
                {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
              </Text>

              {/* Read receipts for user messages */}
              {isUser && (message as any).read && (
                <Icon
                  source="check-all"
                  size={14}
                  color={theme.colors.primary}
                  style={styles.readReceipt}
                />
              )}
            </View>
          )}

          {/* Action menu */}
          <Menu
            visible={menuVisible}
            onDismiss={() => setMenuVisible(false)}
            anchor={
              <TouchableOpacity style={{ position: 'absolute', top: 0, right: 0, padding: 4 }}>
                <Icon
                  source="dots-vertical"
                  size={16}
                  color={theme.colors.onSurfaceVariant}
                />
              </TouchableOpacity>
            }
          >
            <Menu.Item
              leadingIcon="content-copy"
              onPress={() => {
                onMessageCopy?.(message.id);
                setMenuVisible(false);
              }}
              title="Copy"
            />
            {!isUser && onMessageFeedback && (
              <>
                <Menu.Item
                  leadingIcon="thumb-up"
                  onPress={() => {
                    onMessageFeedback(message.id, 1);
                    setMenuVisible(false);
                  }}
                  title="Thumbs Up"
                />
                <Menu.Item
                  leadingIcon="thumb-down"
                  onPress={() => {
                    onMessageFeedback(message.id, -1);
                    setMenuVisible(false);
                  }}
                  title="Thumbs Down"
                />
                <Menu.Item
                  leadingIcon="refresh"
                  onPress={() => {
                    onMessageRegenerate?.(message.id);
                    setMenuVisible(false);
                  }}
                  title="Regenerate"
                />
              </>
            )}
            {isUser && onMessageDelete && (
              <Menu.Item
                leadingIcon="delete"
                onPress={() => {
                  onMessageDelete(message.id);
                  setMenuVisible(false);
                }}
                title="Delete"
                titleStyle={{ color: theme.colors.error }}
              />
            )}
          </Menu>
        </View>

        {isUser && renderAvatar()}
      </View>
    </TouchableOpacity>
  );
};

/**
 * MessageList Component
 *
 * Main component displaying the list of messages
 */
export const MessageList: React.FC<MessageListProps> = ({
  messages,
  onEpisodePress,
  onAgentPress,
  loading = false,
  ListHeaderComponent,
  ListFooterComponent,
  onMessageCopy,
  onMessageFeedback,
  onMessageRegenerate,
  onMessageDelete,
}) => {
  const theme = useTheme();
  const flatListRef = useRef<FlatList>(null);
  const [isScrolledToBottom, setIsScrolledToBottom] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);

  /**
   * Auto-scroll to bottom when new messages arrive (only if already at bottom)
   */
  useEffect(() => {
    if (messages.length > 0 && isScrolledToBottom) {
      flatListRef.current?.scrollToEnd({ animated: true });
    }
  }, [messages, isScrolledToBottom]);

  /**
   * Handle scroll events
   */
  const handleScroll = (event: any) => {
    const { layoutMeasurement, contentOffset, contentSize } = event.nativeEvent;
    const paddingToBottom = 20;
    const isAtBottom =
      layoutMeasurement.height + contentOffset.y >= contentSize.height - paddingToBottom;

    setIsScrolledToBottom(isAtBottom);
    setShowScrollButton(!isAtBottom);
  };

  /**
   * Scroll to bottom
   */
  const scrollToBottom = () => {
    flatListRef.current?.scrollToEnd({ animated: true });
    setShowScrollButton(false);
  };

  /**
   * Render date separator
   */
  const renderDateSeparator = (date: Date) => {
    let dateText = '';
    if (isToday(date)) {
      dateText = 'Today';
    } else if (isYesterday(date)) {
      dateText = 'Yesterday';
    } else {
      dateText = new Date(date).toLocaleDateString();
    }

    return (
      <View style={styles.dateSeparator}>
        <Text style={[styles.dateSeparatorText, { color: theme.colors.onSurfaceVariant }]}>
          {dateText}
        </Text>
      </View>
    );
  };

  /**
   * Group messages by sender and date
   */
  const [groupedMessages, setGroupedMessages] = useState<Array<{
    id: string;
    type: 'date' | 'message';
    data?: Message;
    date?: Date;
  }>>([]);

  useEffect(() => {
    const groups: Array<{
      id: string;
      type: 'date' | 'message';
      data?: Message;
      date?: Date;
    }> = [];

    let lastDate: Date | null = null;
    let lastSender: string | null = null;

    messages.forEach((message) => {
      const messageDate = new Date(message.timestamp);
      const messageDateOnly = new Date(messageDate.getFullYear(), messageDate.getMonth(), messageDate.getDate());

      // Add date separator if date changed
      if (!lastDate || differenceInDays(messageDateOnly, lastDate) !== 0) {
        groups.push({
          id: `date_${messageDateOnly.getTime()}`,
          type: 'date',
          date: messageDateOnly,
        });
        lastDate = messageDateOnly;
        lastSender = null;
      }

      // Add message (show timestamp only for first message in group)
      const showTimestamp = message.agent_id !== lastSender;
      lastSender = message.agent_id || 'user';

      groups.push({
        id: message.id,
        type: 'message',
        data: { ...message, showTimestamp },
      });
    });

    setGroupedMessages(groups);
  }, [messages]);

  /**
   * Render each item
   */
  const renderItem = ({ item }: { item: { type: string; data?: Message; date?: Date } }) => {
    if (item.type === 'date' && item.date) {
      return renderDateSeparator(item.date);
    }

    if (item.type === 'message' && item.data) {
      return (
        <MessageItem
          message={item.data}
          onEpisodePress={onEpisodePress}
          onAgentPress={onAgentPress}
          onMessageCopy={onMessageCopy}
          onMessageFeedback={onMessageFeedback}
          onMessageRegenerate={onMessageRegenerate}
          onMessageDelete={onMessageDelete}
        />
      );
    }

    return null;
  };

  /**
   * Render loading indicator at bottom
   */
  const renderFooter = () => {
    if (loading) {
      return (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" />
          <Text style={styles.loadingText}>Agent is thinking...</Text>
        </View>
      );
    }
    return ListFooterComponent ? <ListFooterComponent /> : null;
  };

  /**
   * Render empty state
   */
  const renderEmptyState = () => (
    <View style={styles.emptyState}>
      <Icon source="message-text-outline" size={64} color={theme.colors.onSurfaceDisabled} />
      <Text style={[styles.emptyTitle, { color: theme.colors.onSurface }]}>
        No messages yet
      </Text>
      <Text style={[styles.emptySubtitle, { color: theme.colors.onSurfaceVariant }]}>
        Start a conversation to see messages here
      </Text>
    </View>
  );

  return (
    <>
      <FlatList
        ref={flatListRef}
        data={groupedMessages}
        renderItem={renderItem}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        ListHeaderComponent={ListHeaderComponent}
        ListFooterComponent={renderFooter}
        ListEmptyComponent={renderEmptyState}
        onScroll={handleScroll}
        scrollEventThrottle={250}
      />

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <FAB
          icon="arrow-down"
          style={[styles.scrollButton, { backgroundColor: theme.colors.primary }]}
          onPress={scrollToBottom}
          size="small"
        />
      )}
    </>
  );
};

const styles = StyleSheet.create({
  listContent: {
    padding: 16,
    flexGrow: 1,
  },
  messageContainer: {
    flexDirection: 'row',
    marginBottom: 16,
    alignItems: 'flex-start',
  },
  userMessage: {
    justifyContent: 'flex-end',
  },
  agentMessage: {
    justifyContent: 'flex-start',
  },
  messageBubble: {
    flex: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 12,
    maxWidth: '80%',
  },
  agentName: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
  },
  messageText: {
    fontSize: 16,
    lineHeight: 24,
  },
  timestampRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  timestamp: {
    fontSize: 11,
  },
  readReceipt: {
    marginLeft: 4,
  },
  badgeContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 8,
    gap: 4,
  },
  badge: {
    fontSize: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  episodeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginTop: 8,
    gap: 8,
  },
  episodeChipText: {
    fontSize: 12,
    fontWeight: '500',
  },
  episodeChipScore: {
    fontSize: 11,
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    gap: 8,
  },
  loadingText: {
    fontSize: 14,
    fontStyle: 'italic',
  },
  dateSeparator: {
    alignItems: 'center',
    paddingVertical: 8,
  },
  dateSeparatorText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    marginTop: 8,
    textAlign: 'center',
  },
  scrollButton: {
    position: 'absolute',
    right: 16,
    bottom: 16,
  },
});

export default MessageList;
