/**
 * ChatTabScreen - Chat Tab Screen
 *
 * Features:
 * - Chat tab showing recent conversations
 * - New conversation button with agent selector
 * - Swipe to delete conversations
 * - Search conversations
 * - Conversation preview (last message, timestamp)
 * - Unread message indicators
 * - Navigate to AgentChatScreen on tap
 * - Empty state with "Start a conversation" CTA
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  TextInput,
  ActivityIndicator,
  Alert,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

const API_BASE_URL = Constants.expoConfig?.extra?.apiUrl || 'http://localhost:8000';

// Types
interface Conversation {
  id: string;
  agent_id: string;
  agent_name: string;
  agent_maturity: string;
  last_message: string;
  last_message_at: string;
  unread_count: number;
  created_at: string;
}

interface Agent {
  id: string;
  name: string;
  maturity_level: string;
  description: string;
}

export const ChatTabScreen = () => {
  const navigation = useNavigation<any>();

  // State
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [filteredConversations, setFilteredConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [accessToken, setAccessToken] = useState<string | null>(null);

  /**
   * Load access token on mount
   */
  useEffect(() => {
    loadToken();
  }, []);

  /**
   * Load conversations when token is available
   */
  useEffect(() => {
    if (accessToken) {
      loadConversations();
    }
  }, [accessToken]);

  /**
   * Filter conversations based on search
   */
  useEffect(() => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const filtered = conversations.filter((conv) =>
        conv.agent_name.toLowerCase().includes(query) ||
        conv.last_message.toLowerCase().includes(query)
      );
      setFilteredConversations(filtered);
    } else {
      setFilteredConversations(conversations);
    }
  }, [searchQuery, conversations]);

  /**
   * Load access token from AsyncStorage
   */
  const loadToken = async () => {
    try {
      const token = await AsyncStorage.getItem('atom_access_token');
      setAccessToken(token);
    } catch (error) {
      console.error('Failed to load token:', error);
    }
  };

  /**
   * Load conversations from API
   */
  const loadConversations = async () => {
    if (!accessToken) {
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/conversations`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.conversations) {
          setConversations(data.conversations);
        } else {
          setConversations([]);
        }
      } else {
        setConversations([]);
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
      setConversations([]);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle refresh
   */
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadConversations();
    setIsRefreshing(false);
  };

  /**
   * Open conversation
   */
  const openConversation = (conversation: Conversation) => {
    navigation.navigate('AgentChat', {
      agentId: conversation.agent_id,
      conversationId: conversation.id,
    });
  };

  /**
   * Start new conversation
   */
  const startNewConversation = () => {
    // Navigate to agent list or show agent selector modal
    // For now, navigate to Agents tab
    navigation.navigate('AgentsTab' as never);
  };

  /**
   * Delete conversation
   */
  const deleteConversation = async (conversationId: string) => {
    if (!accessToken) return;

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
              const response = await fetch(`${API_BASE_URL}/api/chat/conversations/${conversationId}`, {
                method: 'DELETE',
                headers: {
                  'Authorization': `Bearer ${accessToken}`,
                },
              });

              if (response.ok) {
                // Remove from local state
                setConversations(conversations.filter((c) => c.id !== conversationId));
              } else {
                Alert.alert('Error', 'Failed to delete conversation');
              }
            } catch (error) {
              Alert.alert('Error', 'Failed to delete conversation');
            }
          },
        },
      ]
    );
  };

  /**
   * Format timestamp
   */
  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  /**
   * Render conversation item
   */
  const renderConversation = ({ item }: { item: Conversation }) => (
    <TouchableOpacity
      style={styles.conversationItem}
      onPress={() => openConversation(item)}
      activeOpacity={0.7}
    >
      {/* Agent Icon */}
      <View style={styles.agentIcon}>
        <Ionicons name="person-circle" size={50} color="#2196F3" />
      </View>

      {/* Conversation Info */}
      <View style={styles.conversationInfo}>
        <View style={styles.conversationHeader}>
          <Text style={styles.agentName}>{item.agent_name}</Text>
          <Text style={styles.timestamp}>{formatTimestamp(item.last_message_at)}</Text>
        </View>

        <View style={styles.messageRow}>
          <Text style={styles.lastMessage} numberOfLines={1}>
            {item.last_message}
          </Text>
          {item.unread_count > 0 && (
            <View style={styles.unreadBadge}>
              <Text style={styles.unreadCount}>
                {item.unread_count > 9 ? '9+' : item.unread_count}
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* Maturity Badge */}
      <View
        style={[
          styles.maturityBadge,
          { backgroundColor: getMaturityColor(item.agent_maturity) },
        ]}
      >
        <Text style={styles.maturityText}>{item.agent_maturity}</Text>
      </View>
    </TouchableOpacity>
  );

  /**
   * Render empty state
   */
  const renderEmptyState = () => (
    <View style={styles.emptyContainer}>
      <Ionicons name="chatbubbles-outline" size={80} color="#ccc" />
      <Text style={styles.emptyTitle}>No conversations yet</Text>
      <Text style={styles.emptySubtitle}>Start chatting with Atom AI agents</Text>
      <TouchableOpacity style={styles.startButton} onPress={startNewConversation}>
        <Ionicons name="add" size={20} color="#fff" />
        <Text style={styles.startButtonText}>Start a conversation</Text>
      </TouchableOpacity>
    </View>
  );

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#2196F3" />
        <Text style={styles.loadingText}>Loading conversations...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color="#999" style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search conversations..."
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholderTextColor="#999"
        />
        {searchQuery.length > 0 && (
          <TouchableOpacity onPress={() => setSearchQuery('')} style={styles.clearButton}>
            <Ionicons name="close-circle" size={20} color="#999" />
          </TouchableOpacity>
        )}
      </View>

      {/* Conversations List */}
      <FlatList
        data={filteredConversations}
        keyExtractor={(item) => item.id}
        renderItem={renderConversation}
        contentContainerStyle={conversations.length === 0 ? styles.emptyList : {}}
        ListEmptyComponent={renderEmptyState}
        refreshControl={
          <RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} />
        }
      />

      {/* Floating Action Button */}
      {conversations.length > 0 && (
        <TouchableOpacity style={styles.fab} onPress={startNewConversation}>
          <Ionicons name="add" size={28} color="#fff" />
        </TouchableOpacity>
      )}
    </View>
  );
};

/**
 * Get maturity color
 */
function getMaturityColor(maturity: string): string {
  switch (maturity.toLowerCase()) {
    case 'autonomous':
      return '#4CAF50';
    case 'supervised':
      return '#FF9800';
    case 'intern':
      return '#2196F3';
    case 'student':
      return '#9E9E9E';
    default:
      return '#9E9E9E';
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#666',
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
    margin: 16,
    paddingHorizontal: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  searchIcon: {
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    paddingVertical: 12,
    fontSize: 15,
    color: '#000',
  },
  clearButton: {
    padding: 4,
  },
  conversationItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  agentIcon: {
    marginRight: 12,
  },
  conversationInfo: {
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
    color: '#333',
  },
  timestamp: {
    fontSize: 12,
    color: '#999',
  },
  messageRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  lastMessage: {
    flex: 1,
    fontSize: 14,
    color: '#666',
    marginRight: 8,
  },
  unreadBadge: {
    backgroundColor: '#2196F3',
    borderRadius: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
    minWidth: 20,
    alignItems: 'center',
  },
  unreadCount: {
    fontSize: 11,
    fontWeight: '600',
    color: '#fff',
  },
  maturityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    marginLeft: 8,
  },
  maturityText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#fff',
    textTransform: 'uppercase',
  },
  emptyList: {
    flex: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#333',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#666',
    marginTop: 8,
    marginBottom: 24,
  },
  startButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2196F3',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 24,
  },
  startButtonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
    marginLeft: 8,
  },
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#2196F3',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
  },
});

export default ChatTabScreen;
