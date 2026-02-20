/**
 * Conversation List Screen
 *
 * Displays list of all chat conversations with agents.
 * Supports search, filter, sort, swipe actions, and infinite scroll.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from 'react-native';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { useTheme, Avatar, Badge, Searchbar, Chip, IconButton, SwipeRow, FAB } from 'react-native-paper';
import { Icon } from 'react-native-paper';
import { formatDistanceToNow } from 'date-fns';
import { chatService } from '../../services/chatService';
import { ConversationSummary } from '../../services/chatService';

type SortOption = 'recent' | 'unread' | 'name';
type MaturityFilter = 'ALL' | 'AUTONOMOUS' | 'SUPERVISED' | 'INTERN' | 'STUDENT';

interface ConversationSummaryWithAgent extends ConversationSummary {
  avatar_color?: string;
}

export function ConversationListScreen() {
  const theme = useTheme();
  const navigation = useNavigation();

  const [conversations, setConversations] = useState<ConversationSummaryWithAgent[]>([]);
  const [filteredConversations, setFilteredConversations] = useState<ConversationSummaryWithAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('recent');
  const [maturityFilter, setMaturityFilter] = useState<MaturityFilter>('ALL');
  const [selectedConversations, setSelectedConversations] = useState<Set<string>>(new Set());
  const [multiSelectMode, setMultiSelectMode] = useState(false);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  /**
   * Load conversations
   */
  const loadConversations = async (pageNum: number = 0, append: boolean = false) => {
    if (!hasMore && pageNum > 0) return;

    try {
      const response = await chatService.getConversationList(20, pageNum * 20);

      if (response.success && response.data) {
        const newConversations = response.data.map((conv) => ({
          ...conv,
          avatar_color: getMaturityColor(conv.agent_maturity),
        }));

        setConversations((prev) =>
          append ? [...prev, ...newConversations] : newConversations
        );

        if (newConversations.length < 20) {
          setHasMore(false);
        }

        setPage(pageNum);
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
      Alert.alert('Error', 'Failed to load conversations');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Refresh conversations
   */
  const onRefresh = async () => {
    setRefreshing(true);
    setHasMore(true);
    await loadConversations(0, false);
    setRefreshing(false);
  };

  /**
   * Load more conversations
   */
  const loadMore = () => {
    if (!loading && hasMore) {
      loadConversations(page + 1, true);
    }
  };

  /**
   * Filter and sort conversations
   */
  useEffect(() => {
    let filtered = [...conversations];

    // Search filter
    if (searchQuery) {
      filtered = filtered.filter((conv) =>
        conv.agent_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        conv.last_message.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // Maturity filter
    if (maturityFilter !== 'ALL') {
      filtered = filtered.filter((conv) => conv.agent_maturity === maturityFilter);
    }

    // Sort
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'recent':
          return new Date(b.last_message_time).getTime() - new Date(a.last_message_time).getTime();
        case 'unread':
          return b.unread_count - a.unread_count;
        case 'name':
          return a.agent_name.localeCompare(b.agent_name);
        default:
          return 0;
      }
    });

    setFilteredConversations(filtered);
  }, [conversations, searchQuery, sortBy, maturityFilter]);

  /**
   * Load conversations on screen focus
   */
  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      loadConversations(0, false);
    }, [])
  );

  /**
   * Get maturity color
   */
  const getMaturityColor = (maturity: string): string => {
    switch (maturity) {
      case 'AUTONOMOUS':
        return '#4CAF50';
      case 'SUPERVISED':
        return '#FF9800';
      case 'INTERN':
        return '#2196F3';
      case 'STUDENT':
        return '#9E9E9E';
      default:
        return '#9E9E9E';
    }
  };

  /**
   * Handle conversation press
   */
  const handleConversationPress = (conversation: ConversationSummaryWithAgent) => {
    if (multiSelectMode) {
      toggleSelection(conversation.session_id);
    } else {
      // @ts-ignore
      navigation.navigate('AgentChat', {
        agentId: conversation.agent_id,
        sessionId: conversation.session_id,
      });
    }
  };

  /**
   * Handle conversation long press
   */
  const handleConversationLongPress = (sessionId: string) => {
    setMultiSelectMode(true);
    toggleSelection(sessionId);
  };

  /**
   * Toggle selection
   */
  const toggleSelection = (sessionId: string) => {
    const newSelected = new Set(selectedConversations);
    if (newSelected.has(sessionId)) {
      newSelected.delete(sessionId);
    } else {
      newSelected.add(sessionId);
    }
    setSelectedConversations(newSelected);

    if (newSelected.size === 0) {
      setMultiSelectMode(false);
    }
  };

  /**
   * Handle swipe actions
   */
  const handleArchive = async (sessionId: string) => {
    try {
      const response = await chatService.archiveSession(sessionId);
      if (response.success) {
        setConversations((prev) => prev.filter((c) => c.session_id !== sessionId));
      } else {
        Alert.alert('Error', response.error || 'Failed to archive conversation');
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to archive conversation');
    }
  };

  const handleDelete = async (sessionId: string) => {
    Alert.alert(
      'Delete Conversation',
      'Are you sure you want to delete this conversation?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              const response = await chatService.deleteSession(sessionId);
              if (response.success) {
                setConversations((prev) => prev.filter((c) => c.session_id !== sessionId));
              } else {
                Alert.alert('Error', response.error || 'Failed to delete conversation');
              }
            } catch (error) {
              Alert.alert('Error', 'Failed to delete conversation');
            }
          },
        },
      ]
    );
  };

  const handleMarkAsRead = async (sessionId: string) => {
    try {
      await chatService.markAsRead(sessionId);
      setConversations((prev) =>
        prev.map((c) =>
          c.session_id === sessionId ? { ...c, unread_count: 0 } : c
        )
      );
    } catch (error) {
      console.error('Failed to mark as read:', error);
    }
  };

  /**
   * Handle bulk actions
   */
  const handleBulkDelete = () => {
    Alert.alert(
      'Delete Conversations',
      `Delete ${selectedConversations.size} conversations?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            for (const sessionId of selectedConversations) {
              await chatService.deleteSession(sessionId);
            }
            setConversations((prev) =>
              prev.filter((c) => !selectedConversations.has(c.session_id))
            );
            setSelectedConversations(new Set());
            setMultiSelectMode(false);
          },
        },
      ]
    );
  };

  const handleBulkMarkAsRead = async () => {
    for (const sessionId of selectedConversations) {
      await chatService.markAsRead(sessionId);
    }
    setConversations((prev) =>
      prev.map((c) =>
        selectedConversations.has(c.session_id) ? { ...c, unread_count: 0 } : c
      )
    );
    setSelectedConversations(new Set());
    setMultiSelectMode(false);
  };

  /**
   * Render conversation item
   */
  const renderConversation = ({ item }: { item: ConversationSummaryWithAgent }) => {
    const isSelected = selectedConversations.has(item.session_id);

    return (
      <SwipeRow
        leftOpenValue={80}
        rightOpenValue={-150}
        disableRightSwipe={true}
      >
        {/* Hidden actions */}
        <View style={styles.swipeActions}>
          <TouchableOpacity
            style={[styles.swipeButton, styles.archiveButton]}
            onPress={() => handleArchive(item.session_id)}
          >
            <Icon source="archive" size={24} color="#fff" />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.swipeButton, styles.deleteButton]}
            onPress={() => handleDelete(item.session_id)}
          >
            <Icon source="delete" size={24} color="#fff" />
          </TouchableOpacity>
        </View>

        {/* Visible content */}
        <TouchableOpacity
          style={[
            styles.conversationItem,
            isSelected && { backgroundColor: theme.colors.primaryContainer },
          ]}
          onPress={() => handleConversationPress(item)}
          onLongPress={() => handleConversationLongPress(item.session_id)}
        >
          <View style={styles.conversationLeft}>
            <Avatar.Text
              size={50}
              label={item.agent_name.substring(0, 2).toUpperCase()}
              style={{ backgroundColor: item.avatar_color }}
            />
            {item.unread_count > 0 && (
              <Badge style={styles.unreadBadge}>{item.unread_count}</Badge>
            )}
          </View>

          <View style={styles.conversationContent}>
            <View style={styles.conversationHeader}>
              <Text style={[styles.agentName, { color: theme.colors.onSurface }]}>
                {item.agent_name}
              </Text>
              <Text style={[styles.timestamp, { color: theme.colors.onSurfaceVariant }]}>
                {formatDistanceToNow(new Date(item.last_message_time), { addSuffix: true })}
              </Text>
            </View>

            <View style={styles.conversationMeta}>
              <Chip
                style={[styles.maturityChip, { backgroundColor: item.avatar_color }]}
                textStyle={{ color: '#fff', fontSize: 10 }}
              >
                {item.agent_maturity}
              </Chip>
            </View>

            <Text
              style={[styles.lastMessage, { color: theme.colors.onSurfaceVariant }]}
              numberOfLines={2}
            >
              {item.last_message}
            </Text>
          </View>
        </TouchableOpacity>
      </SwipeRow>
    );
  };

  /**
   * Render list empty state
   */
  const renderEmptyState = () => (
    <View style={styles.emptyState}>
      <Icon source="message-outline" size={64} color={theme.colors.onSurfaceDisabled} />
      <Text style={[styles.emptyTitle, { color: theme.colors.onSurface }]}>
        No conversations yet
      </Text>
      <Text style={[styles.emptySubtitle, { color: theme.colors.onSurfaceVariant }]}>
        Start chatting with your agents to see conversations here
      </Text>
    </View>
  );

  /**
   * Render list header
   */
  const renderListHeader = () => (
    <View style={[styles.listHeader, { borderBottomColor: theme.colors.outline }]}>
      <Searchbar
        placeholder="Search conversations..."
        onChangeText={setSearchQuery}
        value={searchQuery}
        style={styles.searchBar}
      />

      <View style={styles.filters}>
        <Chip
          selected={sortBy === 'recent'}
          onPress={() => setSortBy('recent')}
          style={styles.filterChip}
        >
          Recent
        </Chip>
        <Chip
          selected={sortBy === 'unread'}
          onPress={() => setSortBy('unread')}
          style={styles.filterChip}
        >
          Unread
        </Chip>
        <Chip
          selected={maturityFilter !== 'ALL'}
          onPress={() => {
            if (maturityFilter === 'ALL') setMaturityFilter('AUTONOMOUS');
            else if (maturityFilter === 'AUTONOMOUS') setMaturityFilter('SUPERVISED');
            else if (maturityFilter === 'SUPERVISED') setMaturityFilter('INTERN');
            else if (maturityFilter === 'INTERN') setMaturityFilter('STUDENT');
            else setMaturityFilter('ALL');
          }}
          style={styles.filterChip}
        >
          {maturityFilter === 'ALL' ? 'All Levels' : maturityFilter}
        </Chip>
      </View>
    </View>
  );

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: theme.colors.surface }]}>
        <Text style={[styles.headerTitle, { color: theme.colors.onSurface }]}>
          Conversations
        </Text>

        {multiSelectMode && (
          <View style={styles.multiSelectActions}>
            <IconButton
              icon="close"
              size={20}
              onPress={() => {
                setSelectedConversations(new Set());
                setMultiSelectMode(false);
              }}
            />
            <Text style={[styles.selectedCount, { color: theme.colors.onSurface }]}>
              {selectedConversations.size} selected
            </Text>
            <IconButton
              icon="email-open"
              size={20}
              onPress={handleBulkMarkAsRead}
            />
            <IconButton
              icon="delete"
              size={20}
              onPress={handleBulkDelete}
            />
          </View>
        )}
      </View>

      {/* Conversation list */}
      <FlatList
        data={filteredConversations}
        renderItem={renderConversation}
        keyExtractor={(item) => item.session_id}
        ListHeaderComponent={renderListHeader}
        ListEmptyComponent={!loading ? renderEmptyState : null}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        onEndReached={loadMore}
        onEndReachedThreshold={0.5}
        contentContainerStyle={filteredConversations.length === 0 && !loading ? styles.emptyList : undefined}
      />

      {/* FAB */}
      {!multiSelectMode && (
        <FAB
          icon="message-plus"
          style={[styles.fab, { backgroundColor: theme.colors.primary }]}
          // @ts-ignore
          onPress={() => navigation.navigate('AgentChat')}
          label="New Chat"
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  multiSelectActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  selectedCount: {
    fontSize: 14,
    fontWeight: '600',
  },
  listHeader: {
    padding: 16,
    borderBottomWidth: 1,
  },
  searchBar: {
    marginBottom: 12,
    elevation: 0,
  },
  filters: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  filterChip: {
    height: 32,
  },
  conversationItem: {
    flexDirection: 'row',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  conversationLeft: {
    marginRight: 12,
  },
  conversationContent: {
    flex: 1,
  },
  conversationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  agentName: {
    fontSize: 16,
    fontWeight: '600',
    flex: 1,
  },
  timestamp: {
    fontSize: 12,
    marginLeft: 8,
  },
  conversationMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  maturityChip: {
    height: 20,
  },
  lastMessage: {
    fontSize: 14,
    lineHeight: 20,
  },
  unreadBadge: {
    position: 'absolute',
    top: -4,
    right: -4,
  },
  swipeActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    flex: 1,
  },
  swipeButton: {
    width: 75,
    height: '100%',
    justifyContent: 'center',
    alignItems: 'center',
  },
  archiveButton: {
    backgroundColor: '#FF9800',
  },
  deleteButton: {
    backgroundColor: '#F44336',
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  emptyList: {
    flex: 1,
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
  fab: {
    position: 'absolute',
    right: 16,
    bottom: 16,
  },
});

export default ConversationListScreen;
