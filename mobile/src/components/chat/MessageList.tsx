/**
 * MessageList Component
 *
 * Displays a list of chat messages with governance badges, timestamps,
 * and episode context chips. Supports both user and agent messages.
 */

import React, { useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useTheme, Avatar, Badge } from 'react-native-paper';
import { formatDistanceToNow } from 'date-fns';
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
}

const MessageItem: React.FC<MessageItemProps> = ({ message, onEpisodePress, onAgentPress }) => {
  const theme = useTheme();
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
        {!isUser && message.agent_name && (
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

        <Text style={[styles.timestamp, { color: theme.colors.onSurfaceVariant }]}>
          {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
        </Text>
      </View>

      {isUser && renderAvatar()}
    </View>
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
}) => {
  const flatListRef = useRef<FlatList>(null);

  /**
   * Auto-scroll to bottom when new messages arrive
   */
  useEffect(() => {
    if (messages.length > 0) {
      flatListRef.current?.scrollToEnd({ animated: true });
    }
  }, [messages]);

  /**
   * Render each message
   */
  const renderItem = ({ item }: { item: Message }) => {
    return (
      <MessageItem
        message={item}
        onEpisodePress={onEpisodePress}
        onAgentPress={onAgentPress}
      />
    );
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

  return (
    <FlatList
      ref={flatListRef}
      data={messages}
      renderItem={renderItem}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.listContent}
      ListHeaderComponent={ListHeaderComponent}
      ListFooterComponent={renderFooter}
      scrollEventThrottle={16}
    />
  );
};

const styles = StyleSheet.create({
  listContent: {
    padding: 16,
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
  timestamp: {
    fontSize: 11,
    marginTop: 4,
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
});

export default MessageList;
