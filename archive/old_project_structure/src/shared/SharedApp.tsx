#!/usr/bin/env node

/**
 * Atom Project - Shared Chat Application Architecture
 * Web and Desktop App Shared Components Structure

 * CRITICAL IMPLEMENTATION - Week 1
 * Priority: 🔴 HIGH
 * Objective: Create shared codebase for web and desktop apps
 * Timeline: 40 hours development + 8 hours testing

 * This structure provides shared components, services, and utilities
 * that can be used by both web (React) and desktop (Electron) applications.
 * Follows modern monorepo structure with clear separation of concerns.
 */

import React from 'react';
import { render } from 'react-dom';
import { ChakraProvider, ColorModeScript, extendTheme } from '@chakra-ui/react';
import { BrowserRouter } from 'react-router-dom';

// Import shared components
import { AtomChatInterface } from '../components/Chat/AtomChatInterface';
import { MessageItem } from '../components/Chat/MessageItem';
import { ChatWebSocketManager } from '../services/websocketService';
import { NLUChatBridge } from '../services/nluChatBridgeService';

// Import shared types
import { ChatMessage, ChatState } from '../types/chat';
import { AppConfig } from '../types/app';

// Create shared Chakra theme
const theme = extendTheme({
  colors: {
    atom: {
      50: '#f0f9ff',
      100: '#e0f2fe',
      200: '#bae6fd',
      300: '#7dd3fc',
      400: '#38bdf8',
      500: '#0ea5e9',
      600: '#0284c7',
      700: '#0369a1',
      800: '#075985',
      900: '#0c4a6e',
    }
  },
  fonts: {
    heading: 'Inter, system-ui, sans-serif',
    body: 'Inter, system-ui, sans-serif',
  },
  config: {
    initialColorMode: 'light',
    useSystemColorMode: true,
  },
});

/**
 * Shared Application Root Component
 * 
 * This is the root component that can be used by both web and desktop apps.
 * It provides shared context, routing, and layout.
 */
interface SharedAppProps {
  appType: 'web' | 'desktop';
  config: AppConfig;
  userId: string;
  aiAgentId?: string;
}

export const SharedApp: React.FC<SharedAppProps> = ({
  appType,
  config,
  userId,
  aiAgentId = 'default-ai-agent'
}) => {
  const [chatState, setChatState] = React.useState<ChatState>({
    messages: [],
    isLoading: false,
    isTyping: false,
    isConnected: false,
    currentUser: {
      id: userId,
      name: config.user?.name || 'User',
      avatar: config.user?.avatar
    },
    aiAgent: {
      id: aiAgentId,
      name: config.aiAgent?.name || 'Atom AI Assistant',
      avatar: config.aiAgent?.avatar,
      status: 'online'
    }
  });

  // Initialize shared services
  React.useEffect(() => {
    // Initialize WebSocket manager
    const wsManager = ChatWebSocketManager.getInstance();
    
    // Get WebSocket client for this user
    const wsClient = wsManager.getClient({
      websocketUrl: config.websocket?.url || 'ws://localhost:5058',
      userId: userId,
      agentId: aiAgentId
    });

    // Initialize NLU-Chat bridge
    const nluBridge = new NLUChatBridge({
      conversationId: `${userId}-${aiAgentId}`,
      userId: userId,
      enableMemory: true,
      enableWorkflow: true
    });

    // Setup WebSocket event listeners
    wsClient.on('message-received', (message: ChatMessage) => {
      setChatState(prev => ({
        ...prev,
        messages: [...prev.messages, message],
        isTyping: false
      }));
    });

    wsClient.on('message-updated', (message: ChatMessage) => {
      setChatState(prev => ({
        ...prev,
        messages: prev.messages.map(msg =>
          msg.id === message.id ? message : msg
        )
      }));
    });

    wsClient.on('typing-indicator', (data) => {
      setChatState(prev => ({
        ...prev,
        isTyping: data.isTyping
      }));
    });

    wsClient.on('connection-status-changed', (status) => {
      setChatState(prev => ({
        ...prev,
        isConnected: status.connected
      }));
    });

    // Cleanup on unmount
    return () => {
      wsClient.destroy();
      nluBridge.destroy();
    };
  }, [config, userId, aiAgentId]);

  return (
    <ChakraProvider theme={theme}>
      <ColorModeScript initialColorMode={theme.config.initialColorMode} />
      <BrowserRouter>
        <VStack h="100vh" w="100vw" spacing={0}>
          {/* App Header */}
          <SharedHeader 
            appType={appType}
            config={config}
            chatState={chatState}
          />
          
          {/* Main Content */}
          <HStack flex={1} spacing={0}>
            {/* Sidebar */}
            <SharedSidebar 
              appType={appType}
              config={config}
              chatState={chatState}
            />
            
            {/* Chat Interface */}
            <Box flex={1}>
              <AtomChatInterface
                userId={userId}
                aiAgentId={aiAgentId}
                websocketUrl={config.websocket?.url}
                height="100%"
              />
            </Box>
          </HStack>
          
          {/* App Footer */}
          <SharedFooter 
            appType={appType}
            config={config}
          />
        </VStack>
      </BrowserRouter>
    </ChakraProvider>
  );
};

/**
 * Shared Header Component
 * 
 * Common header used by both web and desktop apps.
 */
interface SharedHeaderProps {
  appType: 'web' | 'desktop';
  config: AppConfig;
  chatState: ChatState;
}

const SharedHeader: React.FC<SharedHeaderProps> = ({
  appType,
  config,
  chatState
}) => {
  return (
    <Box
      bg="white"
      borderBottomWidth="1px"
      borderBottomColor="gray.200"
      px={6}
      py={3}
    >
      <HStack justify="space-between" align="center">
        {/* Logo and Title */}
        <HStack spacing={3}>
          <Box
            w={10}
            h={10}
            bg="atom.500"
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
            <Text fontSize="lg" fontWeight="semibold" color="gray.800">
              Atom AI Assistant
            </Text>
            <Text fontSize="xs" color="gray.500">
              {appType === 'desktop' ? 'Desktop App' : 'Web App'}
            </Text>
          </VStack>
        </HStack>

        {/* User Status */}
        <HStack spacing={3}>
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
          
          <Text fontSize="sm" color="gray.600">
            {chatState.currentUser.name}
          </Text>
        </HStack>
      </HStack>
    </Box>
  );
};

/**
 * Shared Sidebar Component
 * 
 * Common sidebar used by both web and desktop apps.
 */
interface SharedSidebarProps {
  appType: 'web' | 'desktop';
  config: AppConfig;
  chatState: ChatState;
}

const SharedSidebar: React.FC<SharedSidebarProps> = ({
  appType,
  config,
  chatState
}) => {
  return (
    <Box
      w={250}
      bg="gray.50"
      borderRightWidth="1px"
      borderRightColor="gray.200"
      p={4}
    >
      <VStack spacing={4} align="stretch">
        {/* Conversations */}
        <VStack align="stretch" spacing={2}>
          <Text fontSize="sm" fontWeight="semibold" color="gray.700">
            Conversations
          </Text>
          <Button
            variant="ghost"
            justifyContent="flex-start"
            leftIcon={<Text fontSize="lg">💬</Text>}
          >
            New Chat
          </Button>
        </VStack>

        {/* Integrations */}
        <VStack align="stretch" spacing={2}>
          <Text fontSize="sm" fontWeight="semibold" color="gray.700">
            Integrations
          </Text>
          <Button
            variant="ghost"
            justifyContent="flex-start"
            leftIcon={<Text fontSize="lg">🔗</Text>}
          >
            Manage Integrations
          </Button>
        </VStack>

        {/* Settings */}
        <VStack align="stretch" spacing={2}>
          <Text fontSize="sm" fontWeight="semibold" color="gray.700">
            Settings
          </Text>
          <Button
            variant="ghost"
            justifyContent="flex-start"
            leftIcon={<Text fontSize="lg">⚙️</Text>}
          >
            Preferences
          </Button>
        </VStack>
      </VStack>
    </Box>
  );
};

/**
 * Shared Footer Component
 * 
 * Common footer used by both web and desktop apps.
 */
interface SharedFooterProps {
  appType: 'web' | 'desktop';
  config: AppConfig;
}

const SharedFooter: React.FC<SharedFooterProps> = ({
  appType,
  config
}) => {
  return (
    <Box
      bg="gray.50"
      borderTopWidth="1px"
      borderTopColor="gray.200"
      px={6}
      py={2}
    >
      <HStack justify="space-between" align="center">
        <Text fontSize="xs" color="gray.500">
          Atom AI Assistant v{config.version || '1.0.0'}
        </Text>
        
        <HStack spacing={4}>
          <Text fontSize="xs" color="gray.500">
            {appType === 'desktop' ? 'Desktop App' : 'Web App'}
          </Text>
          <Text fontSize="xs" color="gray.500">
            Status: {config.status?.health || 'Healthy'}
          </Text>
        </HStack>
      </HStack>
    </Box>
  );
};

/**
 * Web App Entry Point
 * 
 * Entry point for web application.
 */
export const WebApp: React.FC<{ config: AppConfig }> = ({ config }) => {
  const userId = config.user?.id || 'web-user';
  
  return (
    <SharedApp
      appType="web"
      config={config}
      userId={userId}
      aiAgentId={config.aiAgent?.id}
    />
  );
};

/**
 * Desktop App Entry Point
 * 
 * Entry point for desktop (Electron) application.
 */
export const DesktopApp: React.FC<{ config: AppConfig }> = ({ config }) => {
  const userId = config.user?.id || 'desktop-user';
  
  return (
    <SharedApp
      appType="desktop"
      config={config}
      userId={userId}
      aiAgentId={config.aiAgent?.id}
    />
  );
};

/**
 * Initialize Shared Application
 * 
 * Factory function to initialize app based on environment.
 */
export const initializeSharedApp = (appType: 'web' | 'desktop', config: AppConfig) => {
  const App = appType === 'web' ? WebApp : DesktopApp;
  
  // Find root element
  const rootElement = document.getElementById('root');
  
  if (!rootElement) {
    throw new Error('Root element not found');
  }

  // Render app
  render(
    <React.StrictMode>
      <App config={config} />
    </React.StrictMode>,
    rootElement
  );
  
  console.log(`${appType === 'web' ? 'Web' : 'Desktop'} App initialized with config:`, config);
};

export default SharedApp;