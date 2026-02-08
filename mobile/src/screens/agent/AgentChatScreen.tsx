/**
 * Agent Chat Screen
 * Streaming chat interface for interacting with agents
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { Icon, MD3Colors } from 'react-native-paper';
import { agentService } from '../../services/agentService';
import { useWebSocket } from '../../contexts/WebSocketContext';
import { Agent, ChatMessage, AgentMaturity, EpisodeContext } from '../../types/agent';

type RouteParams = {
  AgentChat: {
    agentId?: string;
    sessionId?: string;
  };
};

export function AgentChatScreen() {
  const route = useRoute<RouteProp<RouteParams, 'AgentChat'>>();
  const navigation = useNavigation();

  const { agentId: initialAgentId, sessionId: initialSessionId } = route.params || {};

  const [agent, setAgent] = useState<Agent | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentAgentId, setCurrentAgentId] = useState<string | null>(initialAgentId || null);
  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(initialSessionId);
  const [episodeContext, setEpisodeContext] = useState<EpisodeContext[]>([]);
  const [showEpisodes, setShowEpisodes] = useState(false);

  const flatListRef = useRef<FlatList>(null);
  const { isConnected, sendStreamingMessage, subscribeToStream } = useWebSocket();

  /**
   * Load agent data
   */
  useEffect(() => {
    if (currentAgentId) {
      loadAgent(currentAgentId);
    } else {
      loadAvailableAgents();
    }
  }, [currentAgentId]);

  /**
   * Load chat session if provided
   */
  useEffect(() => {
    if (currentSessionId) {
      loadSession(currentSessionId);
    }
  }, [currentSessionId]);

  /**
   * Load agent details
   */
  const loadAgent = async (agentId: string) => {
    try {
      const response = await agentService.getAgent(agentId);
      if (response.success && response.data) {
        setAgent(response.data);
      } else {
        Alert.alert('Error', response.error || 'Failed to load agent');
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to load agent');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Load available agents (for agent selection)
   */
  const loadAvailableAgents = async () => {
    try {
      const response = await agentService.getAvailableAgents();
      if (response.success && response.data && response.data.length > 0) {
        // Auto-select first available agent
        setAgent(response.data[0]);
        setCurrentAgentId(response.data[0].id);
      }
    } catch (error) {
      console.error('Failed to load agents:', error);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Load chat session
   */
  const loadSession = async (sessionId: string) => {
    try {
      const response = await agentService.getChatSession(sessionId);
      if (response.success && response.data) {
        setMessages(response.data.messages || []);
      }
    } catch (error) {
      console.error('Failed to load session:', error);
    }
  };

  /**
   * Fetch episode context
   */
  const fetchEpisodeContext = async (query: string) => {
    if (!currentAgentId) return;

    try {
      const response = await agentService.getEpisodeContext(currentAgentId, query, 3);
      if (response.success && response.data) {
        setEpisodeContext(response.data);
        if (response.data.length > 0) {
          setShowEpisodes(true);
        }
      }
    } catch (error) {
      console.error('Failed to fetch episode context:', error);
    }
  };

  /**
   * Send message
   */
  const sendMessage = async () => {
    if (!inputMessage.trim() || isSending || !currentAgentId) return;

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage('');
    setIsSending(true);

    try {
      // Fetch episode context for the message
      await fetchEpisodeContext(inputMessage);

      if (isConnected) {
        // Use streaming
        setIsStreaming(true);
        sendStreamingMessage(currentAgentId, inputMessage, currentSessionId || 'new');

        // Subscribe to stream
        const unsubscribe = subscribeToStream(
          currentSessionId || 'new',
          (chunk) => {
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage && lastMessage.role === 'assistant' && lastMessage.is_streaming) {
                // Update streaming message
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...lastMessage,
                  content: lastMessage.content + chunk.token,
                };
                return updated;
              } else {
                // Create new streaming message
                return [
                  ...prev,
                  {
                    id: `msg_${Date.now()}`,
                    role: 'assistant',
                    content: chunk.token,
                    timestamp: new Date().toISOString(),
                    is_streaming: true,
                    governance_badge: chunk.metadata?.governance_badge
                      ? {
                          maturity: chunk.metadata.governance_badge.maturity as AgentMaturity,
                          confidence: chunk.metadata.governance_badge.confidence,
                          requires_supervision: chunk.metadata.governance_badge.maturity !== 'AUTONOMOUS',
                        }
                      : undefined,
                  },
                ];
              }
            });
          },
          () => {
            // Stream complete
            setIsStreaming(false);
            setIsSending(false);
            setMessages((prev) => {
              const updated = [...prev];
              const lastMessage = updated[updated.length - 1];
              if (lastMessage && lastMessage.is_streaming) {
                updated[updated.length - 1] = { ...lastMessage, is_streaming: false };
              }
              return updated;
            });
          },
          (error) => {
            setIsStreaming(false);
            setIsSending(false);
            Alert.alert('Streaming Error', error);
          }
        );

        // Cleanup subscription after 30 seconds
        setTimeout(unsubscribe, 30000);
      } else {
        // Fallback to non-streaming
        const response = await agentService.sendMessage(
          currentAgentId,
          inputMessage,
          currentSessionId
        );

        if (response.success && response.data) {
          setMessages((prev) => [
            ...prev,
            {
              ...response.data!.message,
              governance_badge: agent
                ? {
                    maturity: agent.maturity_level,
                    confidence: agent.confidence_score || 0.5,
                    requires_supervision: agent.maturity_level !== AgentMaturity.AUTONOMOUS,
                  }
                : undefined,
            },
          ]);
          setCurrentSessionId(response.data.session_id);
        } else {
          Alert.alert('Error', response.error || 'Failed to send message');
        }
        setIsSending(false);
      }
    } catch (error) {
      setIsSending(false);
      Alert.alert('Error', 'Failed to send message');
    }
  };

  /**
   * Render message
   */
  const renderMessage = useCallback(({ item }: { item: ChatMessage }) => {
    const isUser = item.role === 'user';

    return (
      <View
        style={[
          styles.messageContainer,
          isUser ? styles.userMessageContainer : styles.assistantMessageContainer,
        ]}
      >
        {!isUser && item.agent_name && (
          <Text style={styles.agentName}>{item.agent_name}</Text>
        )}

        <View
          style={[
            styles.messageBubble,
            isUser ? styles.userMessageBubble : styles.assistantMessageBubble,
          ]}
        >
          <Text style={[styles.messageText, isUser ? styles.userMessageText : styles.assistantMessageText]}>
            {item.content}
          </Text>

          {item.is_streaming && (
            <ActivityIndicator size="small" color={MD3Colors.primary50} style={{ marginLeft: 8 }} />
          )}
        </View>

        {/* Governance Badge */}
        {!isUser && item.governance_badge && (
          <View style={styles.governanceBadge}>
            <Icon
              source={
                item.governance_badge.maturity === AgentMaturity.AUTONOMOUS
                  ? 'check-circle'
                  : item.governance_badge.maturity === AgentMaturity.SUPERVISED
                    ? 'eye'
                    : 'school'
              }
              size={16}
              color={
                item.governance_badge.maturity === AgentMaturity.AUTONOMOUS
                  ? MD3Colors.primary50
                  : MD3Colors.secondary50
              }
            />
            <Text style={styles.governanceBadgeText}>{item.governance_badge.maturity}</Text>
            {item.governance_badge.requires_supervision && (
              <Icon source="shield-alert" size={14} color={MD3Colors.error50} />
            )}
          </View>
        )}

        <Text style={styles.timestamp}>
          {new Date(item.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </Text>
      </View>
    );
  }, []);

  /**
   * Render episode context chip
   */
  const renderEpisodeChip = (episode: EpisodeContext) => (
    <TouchableOpacity
      key={episode.id}
      style={styles.episodeChip}
      onPress={() => {
        // Could navigate to episode detail screen
        console.log('Episode tapped:', episode.id);
      }}
    >
      <Icon source="history" size={14} color={MD3Colors.primary50} />
      <Text style={styles.episodeChipText}>{episode.title}</Text>
      <Text style={styles.episodeRelevance}>{Math.round(episode.relevance_score * 100)}%</Text>
    </TouchableOpacity>
  );

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={MD3Colors.primary50} />
        <Text style={styles.loadingText}>Loading agent...</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Icon source="arrow-left" size={24} color="#000" />
        </TouchableOpacity>

        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle}>{agent?.name || 'Select Agent'}</Text>
          {agent && (
            <View style={styles.headerBadges}>
              <View
                style={[
                  styles.maturityBadge,
                  { backgroundColor: getMaturityColor(agent.maturity_level) },
                ]}
              >
                <Text style={styles.maturityBadgeText}>{agent.maturity_level}</Text>
              </View>
              <View style={[styles.statusBadge, { backgroundColor: getStatusColor(agent.status) }]}>
                <Text style={styles.statusBadgeText}>{agent.status}</Text>
              </View>
            </View>
          )}
        </View>

        <TouchableOpacity onPress={() => {}}>
          <Icon source="cog" size={24} color="#000" />
        </TouchableOpacity>
      </View>

      {/* Episode Context */}
      {showEpisodes && episodeContext.length > 0 && (
        <View style={styles.episodeContainer}>
          <View style={styles.episodeHeader}>
            <Icon source="brain" size={16} color={MD3Colors.primary50} />
            <Text style={styles.episodeHeaderTitle}>Relevant Context</Text>
            <TouchableOpacity onPress={() => setShowEpisodes(false)}>
              <Icon source="close" size={16} color="#000" />
            </TouchableOpacity>
          </View>
          <View style={styles.episodeChips}>{episodeContext.map(renderEpisodeChip)}</View>
        </View>
      )}

      {/* Messages */}
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messagesList}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
        onLayout={() => flatListRef.current?.scrollToEnd({ animated: true })}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon source="robot" size={64} color={MD3Colors.secondary20} />
            <Text style={styles.emptyText}>Start a conversation with {agent?.name || 'the agent'}</Text>
            <Text style={styles.emptySubtext}>
              {agent?.description || 'Ask me anything about your workflows and automations'}
            </Text>
          </View>
        }
      />

      {/* Connection Status */}
      {!isConnected && (
        <View style={styles.connectionStatus}>
          <Icon source="wifi-off" size={14} color={MD3Colors.error50} />
          <Text style={styles.connectionStatusText}>Reconnecting...</Text>
        </View>
      )}

      {/* Input */}
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          value={inputMessage}
          onChangeText={setInputMessage}
          placeholder="Type a message..."
          placeholderTextColor="#999"
          multiline
          maxLength={2000}
          editable={!isSending}
        />

        <TouchableOpacity
          style={[styles.sendButton, (!inputMessage.trim() || isSending) && styles.sendButtonDisabled]}
          onPress={sendMessage}
          disabled={!inputMessage.trim() || isSending}
        >
          {isSending ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Icon source="send" size={20} color="#fff" />
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

/**
 * Get maturity level color
 */
function getMaturityColor(maturity: AgentMaturity): string {
  switch (maturity) {
    case AgentMaturity.AUTONOMOUS:
      return '#4CAF50';
    case AgentMaturity.SUPERVISED:
      return '#FF9800';
    case AgentMaturity.INTERN:
      return '#2196F3';
    case AgentMaturity.STUDENT:
      return '#9E9E9E';
    default:
      return '#9E9E9E';
  }
}

/**
 * Get status color
 */
function getStatusColor(status: string): string {
  switch (status) {
    case 'online':
      return '#4CAF50';
    case 'offline':
      return '#9E9E9E';
    case 'busy':
      return '#FF9800';
    case 'maintenance':
      return '#F44336';
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
    marginTop: 16,
    fontSize: 16,
    color: '#666',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  headerCenter: {
    flex: 1,
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#000',
  },
  headerBadges: {
    flexDirection: 'row',
    marginTop: 4,
  },
  maturityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 12,
    marginRight: 4,
  },
  maturityBadgeText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#fff',
    textTransform: 'uppercase',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 12,
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#fff',
  },
  episodeContainer: {
    backgroundColor: '#F5F5F5',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  episodeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  episodeHeaderTitle: {
    flex: 1,
    marginLeft: 8,
    fontSize: 12,
    fontWeight: '600',
    color: '#333',
  },
  episodeChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  episodeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  episodeChipText: {
    marginLeft: 6,
    fontSize: 12,
    color: '#333',
    flex: 1,
  },
  episodeRelevance: {
    fontSize: 10,
    color: '#666',
    marginLeft: 6,
  },
  messagesList: {
    padding: 16,
    flexGrow: 1,
  },
  messageContainer: {
    marginBottom: 16,
  },
  userMessageContainer: {
    alignItems: 'flex-end',
  },
  assistantMessageContainer: {
    alignItems: 'flex-start',
  },
  messageBubble: {
    maxWidth: '80%',
    padding: 12,
    borderRadius: 16,
  },
  userMessageBubble: {
    backgroundColor: '#2196F3',
    borderBottomRightRadius: 4,
  },
  assistantMessageBubble: {
    backgroundColor: '#F5F5F5',
    borderBottomLeftRadius: 4,
  },
  agentName: {
    fontSize: 12,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  messageText: {
    fontSize: 15,
    lineHeight: 20,
  },
  userMessageText: {
    color: '#fff',
  },
  assistantMessageText: {
    color: '#000',
  },
  governanceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    gap: 4,
  },
  governanceBadgeText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#666',
    textTransform: 'uppercase',
  },
  timestamp: {
    fontSize: 11,
    color: '#999',
    marginTop: 4,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#666',
    marginTop: 8,
    textAlign: 'center',
  },
  connectionStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    backgroundColor: '#FFF3E0',
    gap: 6,
  },
  connectionStatusText: {
    fontSize: 12,
    color: '#E65100',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
    backgroundColor: '#fff',
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#e0e0e0',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    fontSize: 15,
    maxHeight: 100,
    backgroundColor: '#F5F5F5',
  },
  sendButton: {
    marginLeft: 8,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#2196F3',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendButtonDisabled: {
    backgroundColor: '#BDBDBD',
  },
});
