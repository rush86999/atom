#!/usr/bin/env node

/**
 * Atom Project - Phase 1: Chat Interface Foundation
 * React Chat Interface Component Implementation

 * CRITICAL IMPLEMENTATION - Week 1
 * Priority: 🔴 HIGH
 * Objective: Build functional conversational AI chat interface
 * Timeline: 40 hours development + 8 hours testing

 * This is the MISSING component - Atom claims "talk to an AI" but no functional chat interface exists.
 * This implementation provides a production-ready React chat interface with real-time messaging,
 * message history, typing indicators, and integration with existing NLU systems.
 */

import * as React from 'react';
import { useState, useEffect, useRef, useCallback } from 'react';
import { Box, VStack, HStack, Text, Input, Button, Avatar, Spinner, Icon } from '@chakra-ui/react';
import { FiSend, FiPaperclip, FiMic, FiSettings, FiSearch, FiMoreVertical } from 'react-icons/fi';

// Type definitions for chat interface
interface Message {
  id: string;
  content: string;
  sender: 'user' | 'ai' | 'system';
  timestamp: Date;
  status: 'sending' | 'sent' | 'delivered' | 'read' | 'error';
  metadata?: {
    intent?: string;
    entities?: any[];
    agent?: string;
    processing_time?: number;
    error?: string;
  };
}

interface ChatState {
  messages: Message[];
  isLoading: boolean;
  isTyping: boolean;
  isConnected: boolean;
  currentUser: {
    id: string;
    name: string;
    avatar?: string;
  };
  aiAgent: {
    id: string;
    name: string;
    avatar?: string;
    status: 'online' | 'offline' | 'busy';
  };
}

interface ChatInterfaceProps {
  userId: string;
  aiAgentId?: string;
  websocketUrl?: string;
  onMessageSent?: (message: Message) => void;
  onMessageReceived?: (message: Message) => void;
  onTypingChange?: (isTyping: boolean) => void;
  className?: string;
  height?: string | number;
  showHeader?: boolean;
  showFooter?: boolean;
  placeholder?: string;
}

/**
 * Main Chat Interface Component
 * 
 * This component provides a complete chat interface for the Atom conversational AI system.
 * It handles real-time messaging, message history, typing indicators, and integrates
 * with the existing NLU and AI agent systems.
 */
export const AtomChatInterface: React.FC<ChatInterfaceProps> = ({
  userId,
  aiAgentId = 'default-ai-agent',
  websocketUrl = process.env.REACT_APP_WEBSOCKET_URL || 'ws://localhost:5058',
  onMessageSent,
  onMessageReceived,
  onTypingChange,
  className,
  height = '600px',
  showHeader = true,
  showFooter = true,
  placeholder = 'Type your message here...'
}) => {
  // Core state management
  const [chatState, setChatState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    isTyping: false,
    isConnected: false,
    currentUser: {
      id: userId,
      name: 'User',
      avatar: undefined
    },
    aiAgent: {
      id: aiAgentId,
      name: 'Atom AI Assistant',
      avatar: undefined,
      status: 'online'
    }
  });

  // UI state
  const [inputValue, setInputValue] = useState('');
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);
  const [isAttachmentModalOpen, setIsAttachmentModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);

  // Refs for DOM manipulation
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * WebSocket connection management
   */
  const connectWebSocket = useCallback(() => {
    try {
      const ws = new WebSocket(`${websocketUrl}?userId=${userId}&agentId=${aiAgentId}`);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setChatState(prev => ({ ...prev, isConnected: true }));
        websocketRef.current = ws;
        
        // Request message history
        ws.send(JSON.stringify({
          type: 'history_request',
          userId,
          limit: 50
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          switch (data.type) {
            case 'message':
              handleReceivedMessage(data.message);
              break;
            case 'typing_indicator':
              setChatState(prev => ({ ...prev, isTyping: data.isTyping }));
              onTypingChange?.(data.isTyping);
              break;
            case 'history_response':
              setChatState(prev => ({ ...prev, messages: data.messages }));
              break;
            case 'agent_status':
              setChatState(prev => ({ 
                ...prev, 
                aiAgent: { ...prev.aiAgent, status: data.status }
              }));
              break;
            case 'connection_status':
              setChatState(prev => ({ ...prev, isConnected: data.connected }));
              break;
            default:
              console.log('Unknown message type:', data.type);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setChatState(prev => ({ ...prev, isConnected: false }));
        websocketRef.current = null;
        
        // Attempt to reconnect after 3 seconds
        setTimeout(() => {
          connectWebSocket();
        }, 3000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setChatState(prev => ({ ...prev, isConnected: false }));
      };

    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setChatState(prev => ({ ...prev, isConnected: false }));
    }
  }, [userId, aiAgentId, websocketUrl, onTypingChange]);

  /**
   * Initialize WebSocket connection on mount
   */
  useEffect(() => {
    connectWebSocket();

    return () => {
      if (websocketRef.current) {
        websocketRef.current.close();
      }
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    };
  }, [connectWebSocket]);

  /**
   * Auto-scroll to bottom when new messages arrive
   */
  useEffect(() => {
    scrollToBottom();
  }, [chatState.messages]);

  /**
   * Handle sending messages
   */
  const sendMessage = useCallback(async () => {
    if (!inputValue.trim() || !chatState.isConnected) {
      return;
    }

    const newMessage: Message = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      content: inputValue.trim(),
      sender: 'user',
      timestamp: new Date(),
      status: 'sending'
    };

    // Add message to local state
    setChatState(prev => ({
      ...prev,
      messages: [...prev.messages, newMessage],
      isTyping: true
    }));

    // Clear input
    setInputValue('');
    
    // Focus input
    inputRef.current?.focus();

    // Send via WebSocket
    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'message',
        message: newMessage,
        userId,
        agentId: aiAgentId
      }));

      // Update message status
      setChatState(prev => ({
        ...prev,
        messages: prev.messages.map(msg =>
          msg.id === newMessage.id ? { ...msg, status: 'sent' } : msg
        )
      }));

      onMessageSent?.(newMessage);
    } else {
      // Handle offline scenario
      setChatState(prev => ({
        ...prev,
        messages: prev.messages.map(msg =>
          msg.id === newMessage.id ? { ...msg, status: 'error' } : msg
        )
      }));
    }
  }, [inputValue, chatState.isConnected, userId, aiAgentId, onMessageSent]);

  /**
   * Handle received messages
   */
  const handleReceivedMessage = useCallback((message: Message) => {
    setChatState(prev => ({
      ...prev,
      messages: [...prev.messages, message],
      isTyping: false
    }));
    onMessageReceived?.(message);
  }, [onMessageReceived]);

  /**
   * Handle typing indicators
   */
  const handleTyping = useCallback((value: string) => {
    setInputValue(value);

    // Send typing indicator
    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'typing_indicator',
        isTyping: value.length > 0,
        userId,
        agentId: aiAgentId
      }));
    }

    // Clear existing timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    // Set new timeout to stop typing indicator
    if (value.length > 0) {
      typingTimeoutRef.current = setTimeout(() => {
        if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
          websocketRef.current.send(JSON.stringify({
            type: 'typing_indicator',
            isTyping: false,
            userId,
            agentId: aiAgentId
          }));
        }
      }, 3000);
    }
  }, [userId, aiAgentId]);

  /**
   * Handle file attachments
   */
  const handleFileAttachment = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  /**
   * Handle file selection
   */
  const handleFileSelect = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    // TODO: Implement file upload functionality
    console.log('File upload not yet implemented:', files);
  }, []);

  /**
   * Handle voice recording
   */
  const handleVoiceRecording = useCallback(() => {
    // TODO: Implement voice recording functionality
    console.log('Voice recording not yet implemented');
    setIsVoiceRecording(!isVoiceRecording);
  }, [isVoiceRecording]);

  /**
   * Scroll to bottom of messages
   */
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  /**
   * Format message timestamp
   */
  const formatTimestamp = useCallback((date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    }).format(date);
  }, []);

  /**
   * Render message bubble
   */
  const renderMessage = useCallback((message: Message) => {
    const isUser = message.sender === 'user';
    const isAI = message.sender === 'ai';
    const isError = message.status === 'error';

    return (
      <HStack
        key={message.id}
        justify={isUser ? 'flex-end' : 'flex-start'}
        mb={4}
        align="flex-start"
      >
        {!isUser && (
          <Avatar
            size="sm"
            name={chatState.aiAgent.name}
            src={chatState.aiAgent.avatar}
            bg={isAI ? 'blue.500' : 'gray.500'}
            mr={2}
          />
        )}
        
        <VStack
          maxW="70%"
          align={isUser ? 'flex-end' : 'flex-start'}
        >
          <Box
            bg={
              isError
                ? 'red.100'
                : isUser
                ? 'blue.500'
                : isAI
                ? 'gray.100'
                : 'yellow.100'
            }
            color={isUser ? 'white' : 'gray.800'}
            px={4}
            py={3}
            borderRadius="lg"
            borderTopLeftRadius={isUser ? 'lg' : 'none'}
            borderTopRightRadius={isUser ? 'none' : 'lg'}
            boxShadow="md"
          >
            <Text fontSize="sm" whiteSpace="pre-wrap">
              {message.content}
            </Text>
            
            {message.metadata?.error && (
              <Text fontSize="xs" color="red.500" mt={1}>
                Error: {message.metadata.error}
              </Text>
            )}
          </Box>
          
          <HStack justify="space-between" w="full" px={1}>
            <Text fontSize="xs" color="gray.500">
              {formatTimestamp(message.timestamp)}
            </Text>
            {isUser && (
              <Text fontSize="xs" color="gray.500">
                {message.status === 'sending' && '⏳'}
                {message.status === 'sent' && '✓'}
                {message.status === 'delivered' && '✓✓'}
                {message.status === 'read' && '✓✓'}
                {message.status === 'error' && '❌'}
              </Text>
            )}
          </HStack>
        </VStack>
        
        {isUser && (
          <Avatar
            size="sm"
            name={chatState.currentUser.name}
            src={chatState.currentUser.avatar}
            bg="blue.500"
            ml={2}
          />
        )}
      </HStack>
    );
  }, [chatState.aiAgent, chatState.currentUser, formatTimestamp]);

  return (
    <Box
      className={className}
      h={height}
      bg="white"
      borderRadius="lg"
      boxShadow="lg"
      display="flex"
      flexDirection="column"
      borderWidth="1px"
      borderColor="gray.200"
    >
      {/* Header */}
      {showHeader && (
        <HStack
          justify="space-between"
          align="center"
          p={4}
          bg="gray.50"
          borderBottomWidth="1px"
          borderBottomColor="gray.200"
        >
          <HStack align="center">
            <Avatar
              size="sm"
              name={chatState.aiAgent.name}
              src={chatState.aiAgent.avatar}
              bg={
                chatState.aiAgent.status === 'online'
                  ? 'green.500'
                  : chatState.aiAgent.status === 'busy'
                  ? 'yellow.500'
                  : 'gray.500'
              }
            />
            <VStack align="flex-start" spacing={0}>
              <Text fontSize="font-semibold" color="gray.800">
                {chatState.aiAgent.name}
              </Text>
              <Text fontSize="xs" color="gray.500">
                {chatState.aiAgent.status === 'online' && '🟢 Online'}
                {chatState.aiAgent.status === 'busy' && '🟡 Busy'}
                {chatState.aiAgent.status === 'offline' && '🔴 Offline'}
              </Text>
            </VStack>
          </HStack>

          <HStack>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSearch(!showSearch)}
            >
              <Icon as={FiSearch} />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsSettingsModalOpen(true)}
            >
              <Icon as={FiSettings} />
            </Button>
            <Button
              variant="ghost"
              size="sm"
            >
              <Icon as={FiMoreVertical} />
            </Button>
          </HStack>
        </HStack>
      )}

      {/* Search Bar */}
      {showSearch && (
        <Box px={4} py={2} bg="gray.50" borderBottomWidth="1px" borderBottomColor="gray.200">
          <Input
            placeholder="Search messages..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            size="sm"
          />
        </Box>
      )}

      {/* Connection Status */}
      {!chatState.isConnected && (
        <HStack justify="center" p={2} bg="yellow.50">
          <Text fontSize="sm" color="yellow.700">
            🔄 Reconnecting to server...
          </Text>
        </HStack>
      )}

      {/* Messages Container */}
      <VStack
        flex={1}
        overflow="auto"
        p={4}
        spacing={0}
        align="stretch"
        justify="flex-end"
      >
        {chatState.messages.length === 0 ? (
          <Box textAlign="center" py={8}>
            <Text color="gray.500" fontSize="lg">
              👋 Welcome to Atom AI Assistant!
            </Text>
            <Text color="gray.400" fontSize="md" mt={2}>
              Start a conversation by typing a message below.
            </Text>
          </Box>
        ) : (
          <>
            {chatState.messages.map(renderMessage)}
            {chatState.isTyping && (
              <HStack justify="flex-start" mb={4}>
                <Avatar
                  size="sm"
                  name={chatState.aiAgent.name}
                  src={chatState.aiAgent.avatar}
                  bg="gray.500"
                  mr={2}
                />
                <Box
                  bg="gray.100"
                  px={4}
                  py={3}
                  borderRadius="lg"
                  boxShadow="md"
                >
                  <Text fontSize="sm" color="gray.600">
                    {chatState.aiAgent.name} is typing
                    <span className="typing-indicator">
                      <span>.</span>
                      <span>.</span>
                      <span>.</span>
                    </span>
                  </Text>
                </Box>
              </HStack>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </VStack>

      {/* Footer */}
      {showFooter && (
        <Box
          p={4}
          bg="gray.50"
          borderTopWidth="1px"
          borderTopColor="gray.200"
        >
          <HStack spacing={2}>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleFileAttachment}
              title="Attach file"
            >
              <Icon as={FiPaperclip} />
            </Button>
            
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => handleTyping(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder={placeholder}
              flex={1}
              bg="white"
            />
            
            <Button
              variant="ghost"
              size="sm"
              onClick={handleVoiceRecording}
              title={isVoiceRecording ? 'Stop recording' : 'Start recording'}
              color={isVoiceRecording ? 'red.500' : 'gray.500'}
            >
              <Icon as={FiMic} />
            </Button>
            
            <Button
              colorScheme="blue"
              onClick={sendMessage}
              isDisabled={!inputValue.trim() || !chatState.isConnected}
              title="Send message"
            >
              <Icon as={FiSend} />
            </Button>
          </HStack>
          
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </Box>
      )}
    </Box>
  );
};

export default AtomChatInterface;

// CSS for typing indicator
const style = document.createElement('style');
style.textContent = `
  .typing-indicator {
    display: inline-block;
    margin-left: 4px;
  }
  
  .typing-indicator span {
    display: inline-block;
    width: 4px;
    height: 4px;
    background-color: #718096;
    border-radius: 50%;
    margin: 0 1px;
    animation: typing 1.4s infinite ease-in-out;
  }
  
  .typing-indicator span:nth-child(1) {
    animation-delay: -0.32s;
  }
  
  .typing-indicator span:nth-child(2) {
    animation-delay: -0.16s;
  }
  
  @keyframes typing {
    0%, 80%, 100% {
      opacity: 0;
    }
    40% {
      opacity: 1;
    }
  }
`;
document.head.appendChild(style);