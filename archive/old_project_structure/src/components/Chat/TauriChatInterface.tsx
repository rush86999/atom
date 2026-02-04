#!/usr/bin/env node

/**
 * Atom Project - Missing Chat Interface
 * Tauri Chat Component for Desktop App

 * CRITICAL IMPLEMENTATION - Week 1
 * Priority: 🔴 HIGH
 * Objective: Build functional chat interface for existing Tauri app
 * Timeline: 24 hours development + 8 hours testing

 * This component provides the missing chat interface for the Atom
 * desktop application, connecting to existing Tauri commands and
 * integrating with the comprehensive service integrations.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Box, 
  VStack, 
  HStack, 
  Text, 
  Input, 
  Button, 
  Avatar, 
  Spinner, 
  Icon,
  Divider,
  Heading,
  useColorModeValue,
  useToast
} from '@chakra-ui/react';
import { 
  FiSend, 
  FiPaperclip, 
  FiMic, 
  FiSettings, 
  FiMoreVertical,
  FiMessageSquare,
  FiCheck,
  FiCheckCircle
} from 'react-icons/fi';

import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';

// Import existing types if available, or create simple interfaces
interface ChatMessage {
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
    integration?: string;
    action?: string;
  };
}

interface ChatState {
  messages: ChatMessage[];
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

/**
 * Tauri Chat Interface Component
 * 
 * Provides chat interface for Atom desktop app with Tauri integration
 * and connection to existing service integrations (Slack, Teams, Notion, etc.)
 */
export const TauriChatInterface: React.FC = () => {
  const toast = useToast();
  
  // Chat state
  const [chatState, setChatState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    isTyping: false,
    isConnected: false,
    currentUser: {
      id: 'desktop-user',
      name: 'User',
      avatar: undefined
    },
    aiAgent: {
      id: 'atom-ai',
      name: 'Atom AI Assistant',
      avatar: undefined,
      status: 'online'
    }
  });

  // UI state
  const [inputValue, setInputValue] = useState('');
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [activeIntegrations, setActiveIntegrations] = useState<string[]>([]);

  // Color mode values
  const bgHover = useColorModeValue('gray.50', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'gray.100');
  const subTextColor = useColorModeValue('gray.600', 'gray.400');

  // Refs
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  /**
   * Initialize chat with existing Tauri app state
   */
  useEffect(() => {
    initializeChat();
  }, []);

  /**
   * Auto-scroll to bottom when new messages arrive
   */
  useEffect(() => {
    scrollToBottom();
  }, [chatState.messages]);

  /**
   * Setup event listeners for Tauri events
   */
  useEffect(() => {
    const unlistenFunctions: Promise<(() => void)>[] = [];

    // Listen for Atom agent responses
    const setupAgentListener = async () => {
      const unlisten = await listen<string>('atom-agent-response', (event) => {
        handleAgentResponse(event.payload);
      });
      unlistenFunctions.push(unlisten);
    };

    // Listen for integration events
    const setupIntegrationListener = async () => {
      const unlisten = await listen<string>('integration-event', (event) => {
        handleIntegrationEvent(event.payload);
      });
      unlistenFunctions.push(unlisten);
    };

    // Listen for status updates
    const setupStatusListener = async () => {
      const unlisten = await listen<string>('status-update', (event) => {
        handleStatusUpdate(event.payload);
      });
      unlistenFunctions.push(unlisten);
    };

    setupAgentListener();
    setupIntegrationListener();
    setupStatusListener();

    // Cleanup
    return () => {
      unlistenFunctions.forEach(unlisten => unlisten());
    };
  }, []);

  /**
   * Initialize chat with existing app state
   */
  const initializeChat = async () => {
    try {
      // Get existing integrations health
      const healthResponse = await invoke('get_integrations_health') as any;
      if (healthResponse.success) {
        const integrations = healthResponse.data || {};
        const active = Object.keys(integrations).filter(key => integrations[key].connected);
        setActiveIntegrations(active);
        setChatState(prev => ({
          ...prev,
          isConnected: active.length > 0
        }));
      }

      // Get Atom agent status
      const agentStatusResponse = await invoke('get_atom_agent_status') as any;
      if (agentStatusResponse.success) {
        const agentData = agentStatusResponse.data || {};
        setChatState(prev => ({
          ...prev,
          aiAgent: {
            ...prev.aiAgent,
            status: agentData.status || 'online',
            name: agentData.name || 'Atom AI Assistant'
          }
        }));
      }

      // Add welcome message
      const welcomeMessage: ChatMessage = {
        id: `msg-${Date.now()}-welcome`,
        content: `👋 Welcome to Atom AI Assistant!

I'm ready to help you manage your integrated services:
${active.length > 0 ? active.map(i => `✅ ${i.charAt(0).toUpperCase() + i.slice(1)}`).join('\n') : '📋 No integrations connected yet'}

Try asking me to:
• Check your Slack messages
• Create a Notion document  
• Get your Asana tasks
• Search your Teams conversations
• Help with workflow automation

What would you like to do?`,
        sender: 'ai',
        timestamp: new Date(),
        status: 'sent',
        metadata: {
          agent: 'system',
          intent: 'welcome'
        }
      };

      setChatState(prev => ({
        ...prev,
        messages: [welcomeMessage]
      }));

    } catch (error) {
      console.error('Failed to initialize chat:', error);
      toast({
        title: 'Chat Initialization Error',
        description: 'Failed to initialize chat interface',
        status: 'error',
        duration: 5000
      });
    }
  };

  /**
   * Handle sending messages
   */
  const sendMessage = useCallback(async () => {
    if (!inputValue.trim() || !chatState.isConnected) {
      return;
    }

    const newMessage: ChatMessage = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      content: inputValue.trim(),
      sender: 'user',
      timestamp: new Date(),
      status: 'sending'
    };

    // Add message to chat
    setChatState(prev => ({
      ...prev,
      messages: [...prev.messages, newMessage],
      isTyping: true
    }));

    // Clear input
    setInputValue('');
    
    // Focus input
    inputRef.current?.focus();

    try {
      // Send message to Atom agent via Tauri
      const response = await invoke('process_atom_agent_message', {
        message: newMessage.content,
        userId: chatState.currentUser.id,
        activeIntegrations
      }) as any;

      // Update message status
      setChatState(prev => ({
        ...prev,
        messages: prev.messages.map(msg =>
          msg.id === newMessage.id ? { ...msg, status: 'sent' } : msg
        )
      }));

      if (!response.success) {
        throw new Error(response.error || 'Failed to send message');
      }

    } catch (error) {
      console.error('Failed to send message:', error);
      
      // Update message status to error
      setChatState(prev => ({
        ...prev,
        messages: prev.messages.map(msg =>
          msg.id === newMessage.id 
            ? { 
                ...msg, 
                status: 'error',
                metadata: {
                  ...msg.metadata,
                  error: error instanceof Error ? error.message : 'Unknown error'
                }
              } 
            : msg
        ),
        isTyping: false
      }));

      toast({
        title: 'Message Send Error',
        description: 'Failed to send message to Atom AI',
        status: 'error',
        duration: 5000
      });
    }
  }, [inputValue, chatState.isConnected, chatState.currentUser.id, activeIntegrations, toast]);

  /**
   * Handle agent responses
   */
  const handleAgentResponse = useCallback((response: string) => {
    try {
      const data = JSON.parse(response);
      
      const agentMessage: ChatMessage = {
        id: `msg-${Date.now()}-agent`,
        content: data.content || 'I processed your request.',
        sender: 'ai',
        timestamp: new Date(),
        status: 'sent',
        metadata: {
          agent: data.agent || 'atom-ai',
          intent: data.intent,
          entities: data.entities,
          processing_time: data.processing_time,
          integration: data.integration,
          action: data.action
        }
      };

      setChatState(prev => ({
        ...prev,
        messages: [...prev.messages, agentMessage],
        isTyping: false
      }));

    } catch (error) {
      console.error('Failed to handle agent response:', error);
      
      // Add error message
      const errorMessage: ChatMessage = {
        id: `msg-${Date.now()}-error`,
        content: 'I encountered an error processing your request. Please try again.',
        sender: 'system',
        timestamp: new Date(),
        status: 'error',
        metadata: {
          error: error instanceof Error ? error.message : 'Unknown error'
        }
      };

      setChatState(prev => ({
        ...prev,
        messages: [...prev.messages, errorMessage],
        isTyping: false
      }));
    }
  }, []);

  /**
   * Handle integration events
   */
  const handleIntegrationEvent = useCallback((event: string) => {
    try {
      const data = JSON.parse(event);
      
      // Add integration event message
      const eventMessage: ChatMessage = {
        id: `msg-${Date.now()}-integration`,
        content: `📋 ${data.integration}: ${data.message}`,
        sender: 'system',
        timestamp: new Date(),
        status: 'sent',
        metadata: {
          integration: data.integration,
          action: data.action,
          intent: 'integration_event'
        }
      };

      setChatState(prev => ({
        ...prev,
        messages: [...prev.messages, eventMessage]
      }));

    } catch (error) {
      console.error('Failed to handle integration event:', error);
    }
  }, []);

  /**
   * Handle status updates
   */
  const handleStatusUpdate = useCallback((update: string) => {
    try {
      const data = JSON.parse(update);
      
      // Update AI agent status
      if (data.agent) {
        setChatState(prev => ({
          ...prev,
          aiAgent: {
            ...prev.aiAgent,
            status: data.agent.status
          }
        }));
      }

      // Update integration status
      if (data.integration) {
        setActiveIntegrations(prev => {
          if (data.integration.connected && !prev.includes(data.integration.name)) {
            return [...prev, data.integration.name];
          } else if (!data.integration.connected) {
            return prev.filter(i => i !== data.integration.name);
          }
          return prev;
        });
      }

    } catch (error) {
      console.error('Failed to handle status update:', error);
    }
  }, []);

  /**
   * Handle file attachment
   */
  const handleFileAttachment = useCallback(async () => {
    try {
      const response = await invoke('open_file_dialog', {
        filters: [
          { name: 'All Files', extensions: ['*'] },
          { name: 'Text Files', extensions: ['txt', 'md'] },
          { name: 'Documents', extensions: ['pdf', 'doc', 'docx'] },
          { name: 'Images', extensions: ['jpg', 'png', 'gif', 'svg'] }
        ]
      }) as any;

      if (response.success && response.path) {
        toast({
          title: 'File Selected',
          description: `File selected: ${response.path}`,
          status: 'success',
          duration: 3000
        });
      }

    } catch (error) {
      toast({
        title: 'File Selection Error',
        description: 'Failed to select file',
        status: 'error',
        duration: 5000
      });
    }
  }, [toast]);

  /**
   * Handle voice recording
   */
  const handleVoiceRecording = useCallback(() => {
    setIsVoiceRecording(!isVoiceRecording);
    
    if (!isVoiceRecording) {
      toast({
        title: 'Voice Recording Started',
        description: 'Speak now...',
        status: 'info',
        duration: 2000
      });
    } else {
      toast({
        title: 'Voice Recording Stopped',
        description: 'Processing speech...',
        status: 'info',
        duration: 2000
      });
    }
  }, [isVoiceRecording, toast]);

  /**
   * Scroll to bottom of messages
   */
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  /**
   * Format timestamp
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
  const renderMessage = useCallback((message: ChatMessage) => {
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
            bg={
              message.sender === 'system'
                ? 'yellow.500'
                : isAI
                ? 'blue.500'
                : 'gray.500'
            }
            mr={2}
            icon={
              message.sender === 'system' ? '📋' :
              isAI ? '🤖' : '👤'
            }
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
            color={isUser ? 'white' : textColor}
            px={4}
            py={3}
            borderRadius="lg"
            borderTopLeftRadius={isUser ? 'lg' : 'none'}
            borderTopRightRadius={isUser ? 'none' : 'lg'}
            boxShadow="md"
            whiteSpace="pre-wrap"
          >
            <Text fontSize="sm">
              {message.content}
            </Text>
            
            {/* Integration metadata */}
            {message.metadata?.integration && (
              <Text
                fontSize="xs"
                color={subTextColor}
                mt={2}
                pt={2}
                borderTopWidth="1px"
                borderColor={useColorModeValue('gray.200', 'gray.600')}
              >
                📋 via {message.metadata.integration}
              </Text>
            )}
            
            {/* Error message */}
            {message.metadata?.error && (
              <Text
                fontSize="xs"
                color="red.500"
                mt={2}
                pt={2}
                borderTopWidth="1px"
                borderColor={useColorModeValue('gray.200', 'gray.600')}
              >
                ❌ Error: {message.metadata.error}
              </Text>
            )}
          </Box>
          
          <HStack justify="space-between" w="full" px={1}>
            <Text fontSize="xs" color={subTextColor}>
              {formatTimestamp(message.timestamp)}
            </Text>
            {isUser && (
              <Text fontSize="xs" color={subTextColor}>
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
            icon="👤"
          />
        )}
      </HStack>
    );
  }, [
    chatState.aiAgent,
    chatState.currentUser,
    textColor,
    subTextColor,
    formatTimestamp,
    useColorModeValue
  ]);

  return (
    <VStack
      h="100vh"
      w="100vw"
      bg={useColorModeValue('gray.50', 'gray.900')}
      spacing={0}
    >
      {/* Header */}
      <Box
        bg="white"
        borderBottomWidth="1px"
        borderBottomColor="gray.200"
        px={6}
        py={3}
        w="full"
      >
        <HStack justify="space-between" align="center" w="full">
          <HStack spacing={3}>
            <Box
              w={10}
              h={10}
              bg="blue.500"
              borderRadius="md"
              display="flex"
              alignItems="center"
              justifyContent="center"
              color="white"
              fontWeight="bold"
              fontSize="lg"
            >
              A
            </Box>
            <VStack spacing={0} align="flex-start">
              <Heading size="sm" color="gray.800">
                Atom AI Assistant
              </Heading>
              <Text fontSize="xs" color="gray.500">
                Desktop App with {activeIntegrations.length} Integrations
              </Text>
            </VStack>
          </HStack>

          <HStack spacing={3}>
            {/* AI Agent Status */}
            <HStack align="center">
              <Box
                w={2}
                h={2}
                borderRadius="full"
                bg={
                  chatState.aiAgent.status === 'online' ? 'green.500' :
                  chatState.aiAgent.status === 'busy' ? 'yellow.500' : 'red.500'
                }
              />
              <Text fontSize="sm" color="gray.600">
                {chatState.aiAgent.status}
              </Text>
            </HStack>
            
            {/* Connection Status */}
            <HStack align="center">
              <Box
                w={2}
                h={2}
                borderRadius="full"
                bg={chatState.isConnected ? 'green.500' : 'red.500'}
              />
              <Text fontSize="sm" color="gray.600">
                {chatState.isConnected ? 'Connected' : 'Disconnected'}
              </Text>
            </HStack>

            {/* Settings */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSettings(!showSettings)}
            >
              <Icon as={FiSettings} />
            </Button>
          </HStack>
        </HStack>
      </Box>

      {/* Messages Container */}
      <VStack
        flex={1}
        overflow="auto"
        p={4}
        spacing={0}
        align="stretch"
        justify="flex-end"
        w="full"
      >
        {chatState.messages.length === 0 ? (
          <Box textAlign="center" py={8}>
            <FiMessageSquare size={48} color="gray.400" />
            <Text color="gray.500" fontSize="lg" mt={4}>
              Welcome to Atom AI Assistant
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
                  bg="blue.500"
                  mr={2}
                  icon="🤖"
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

      {/* Input Area */}
      <Box
        px={4}
        py={4}
        bg="white"
        borderTopWidth="1px"
        borderTopColor="gray.200"
        w="full"
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
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Type your message here... (Try: 'Check my Slack messages' or 'Create a Notion document')"
            flex={1}
            bg="white"
            disabled={!chatState.isConnected}
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
        
        {/* Quick Actions */}
        {activeIntegrations.length > 0 && (
          <HStack spacing={2} mt={3} flexWrap="wrap">
            <Text fontSize="xs" color="gray.500" mr={2}>
              Quick actions:
            </Text>
            {activeIntegrations.map(integration => (
              <Button
                key={integration}
                variant="outline"
                size="xs"
                onClick={() => setInputValue(`Check my ${integration} messages`)}
              >
                {integration.charAt(0).toUpperCase() + integration.slice(1)}
              </Button>
            ))}
          </HStack>
        )}
      </Box>
    </VStack>
  );
};

export default TauriChatInterface;