/**
 * ATOM AI Conversational Interface
 * Advanced NLP-powered conversation interface for ATOM platform
 * Provides natural language control over integrations, workflows, and analytics
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Box, Container, VStack, HStack, Text, Heading, Divider,
  Input, InputGroup, InputRightElement, Button, ButtonGroup,
  Avatar, Badge, Icon, Spinner, Alert, AlertIcon,
  AlertTitle, AlertDescription, Card, CardBody, CardHeader,
  useColorModeValue, Fade, Scale, Slide, SimpleGrid,
  Flex, Grid, GridItem, Link, Menu, MenuButton,
  MenuList, MenuItem, Tooltip, Progress, Stat,
  StatLabel, StatNumber, StatHelpText, Tabs, TabList,
  TabPanels, TabPanel, Accordion, AccordionItem,
  AccordionButton, AccordionPanel, AccordionIcon,
  useToast, useDisclosure, Modal, ModalOverlay,
  ModalContent, ModalHeader, ModalFooter, ModalBody,
  ModalCloseButton, FormControl, FormLabel, FormErrorMessage,
  Select, Switch, Textarea, Stack, Tag, TagLabel,
  TagLeftIcon, useBreakpointValue, IconButton, Drawer,
  DrawerOverlay, DrawerContent, DrawerHeader, DrawerFooter,
  DrawerBody, DrawerCloseButton, List, ListItem, ListIcon
} from '@chakra-ui/react';
import {
  FiSend, FiMic, FiSettings, FiRefreshCw, FiThumbsUp,
  FiThumbsDown, FiCopy, FiShare2, FiBook, FiTrendingUp,
  FiActivity, FiDatabase, FiZap, FiAlertTriangle,
  FiCheckCircle, FiXCircle, FiInfo, FiHelpCircle,
  FiMoreHorizontal, FiClock, FiUser, FiShield, FiLock,
  FiUnlock, FiSave, FiTrash2, FiEdit2, FiFilter,
  FiSearch, FiPlus, FiMinus, FiArrowUp, FiArrowDown,
  FiDownload, FiUpload, FiGrid, FiList, FiMaximize2,
  FiMinimize2, FiEye, FiEyeOff, FiBell, FiVolume2,
  FiVolumeX, FiSkipBack, FiSkipForward, FiPause,
  FiPlay, FiSquare, FiRepeat, FiShuffle
} from 'react-icons/fi';
import { AtomAdvancedAIAgent } from '../ai/agents/AtomAdvancedAIAgent';
import { AtomPredictiveWorkflowEngine } from '../ai/workflows/AtomPredictiveWorkflowEngine';

// Types and Interfaces
export interface ConversationMessage {
  id: string;
  type: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  timestamp: string;
  confidence?: number;
  reasoning?: string;
  suggestedActions?: string[];
  integrationInsights?: any;
  proactiveSuggestions?: any;
  metadata?: {
    model?: string;
    responseTime?: number;
    tokenUsage?: number;
    sources?: string[];
  };
  status: 'sending' | 'sent' | 'processing' | 'completed' | 'failed';
  userFeedback?: {
    helpful: boolean;
    reason?: string;
  };
}

export interface ConversationContext {
  userId: string;
  sessionId: string;
  integrations: string[];
  userPreferences: UserPreferences;
  organizationContext: OrganizationContext;
  currentWorkflow?: WorkflowContext;
  conversationHistory: ConversationMessage[];
  realtimeData: Record<string, any>;
  permissions: UserPermissions;
  timeContext: TimeContext;
  geographicContext: GeographicContext;
}

export interface UserPreferences {
  language: string;
  timezone: string;
  voiceEnabled: boolean;
  autoSuggestion: boolean;
  showReasoning: boolean;
  showIntegrationInsights: boolean;
  conversationStyle: 'formal' | 'casual' | 'technical' | 'friendly';
  responseSpeed: 'fast' | 'balanced' | 'thorough';
  suggestionFrequency: 'low' | 'medium' | 'high';
}

export interface AIResponse {
  content: string;
  confidence: number;
  reasoning: string;
  sources: string[];
  suggestedActions: string[];
  metadata: any;
  integrationInsights?: any;
  proactiveSuggestions?: any;
}

export interface VoiceRecognition {
  enabled: boolean;
  isListening: boolean;
  transcript: string;
  confidence: number;
  language: string;
}

export interface ConversationAnalytics {
  totalMessages: number;
  averageResponseTime: number;
  satisfactionScore: number;
  integrationUsage: Record<string, number>;
  topicDistribution: Record<string, number>;
  automationSuggestions: number;
  workflowGenerations: number;
  errorRate: number;
}

// Props Interface
interface AtomAIConversationInterfaceProps {
  aiAgent: AtomAdvancedAIAgent;
  workflowEngine: AtomPredictiveWorkflowEngine;
  userId: string;
  organizationContext: OrganizationContext;
  integrations: string[];
  userPermissions: UserPermissions;
  onAction: (action: string, params: any) => void;
  onWorkflowCreate: (workflow: any) => void;
  onIntegrationConnect: (integration: string) => void;
  height?: string;
  width?: string;
  theme?: 'light' | 'dark' | 'auto';
}

// Main Component
const AtomAIConversationInterface: React.FC<AtomAIConversationInterfaceProps> = ({
  aiAgent,
  workflowEngine,
  userId,
  organizationContext,
  integrations,
  userPermissions,
  onAction,
  onWorkflowCreate,
  onIntegrationConnect,
  height = "100%",
  width = "100%",
  theme = 'auto'
}) => {
  // State Management
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [voiceRecognition, setVoiceRecognition] = useState<VoiceRecognition>({
    enabled: false,
    isListening: false,
    transcript: '',
    confidence: 0,
    language: 'en-US'
  });
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [analytics, setAnalytics] = useState<ConversationAnalytics>();
  const [userPreferences, setUserPreferences] = useState<UserPreferences>({
    language: 'en-US',
    timezone: 'UTC',
    voiceEnabled: false,
    autoSuggestion: true,
    showReasoning: false,
    showIntegrationInsights: true,
    conversationStyle: 'friendly',
    responseSpeed: 'balanced',
    suggestionFrequency: 'medium'
  });
  
  // UI State
  const { isOpen: settingsOpen, onOpen: settingsOnOpen, onClose: settingsOnClose } = useDisclosure();
  const { isOpen: insightsOpen, onOpen: insightsOnOpen, onClose: insightsOnClose } = useDisclosure();
  const { isOpen: historyOpen, onOpen: historyOnOpen, onClose: historyOnClose } = useDisclosure();
  const { isOpen: suggestionsOpen, onOpen: suggestionsOnOpen, onClose: suggestionsOnClose } = useDisclosure();
  const toast = useToast();
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const voiceRef = useRef<SpeechRecognition | null>(null);

  // Theme and responsive values
  const bgColor = useColorModeValue('white', 'gray.900');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'gray.200');
  const isMobile = useBreakpointValue({ base: true, md: false });

  // Conversation context
  const conversationContext = useMemo((): ConversationContext => ({
    userId,
    sessionId: `session-${Date.now()}`,
    integrations,
    userPreferences,
    organizationContext,
    currentWorkflow: undefined,
    conversationHistory: messages,
    realtimeData: {},
    permissions: userPermissions,
    timeContext: {
      timezone: userPreferences.timezone,
      workingHours: { start: '09:00', end: '17:00' },
      businessDays: [1, 2, 3, 4, 5]
    },
    geographicContext: {
      country: 'US',
      region: 'NA',
      language: userPreferences.language
    }
  }), [userId, integrations, userPreferences, organizationContext, messages, userPermissions]);

  // Effects
  useEffect(() => {
    // Initialize voice recognition if enabled
    if (userPreferences.voiceEnabled && !voiceRef.current) {
      initializeVoiceRecognition();
    }
    
    // Welcome message
    if (messages.length === 0) {
      addWelcomeMessage();
    }
    
    // Load conversation analytics
    loadConversationAnalytics();
    
  }, [userPreferences.voiceEnabled]);

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Generate suggestions based on context
    if (userPreferences.autoSuggestion && inputMessage.length > 0) {
      generateSuggestions();
    }
  }, [inputMessage, conversationContext]);

  // Voice Recognition
  const initializeVoiceRecognition = useCallback(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = voiceRecognition.language;
      
      recognition.onstart = () => {
        setVoiceRecognition(prev => ({ ...prev, isListening: true }));
      };
      
      recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map(result => result[0])
          .map(result => result.transcript)
          .join('');
        
        setVoiceRecognition(prev => ({
          ...prev,
          transcript,
          confidence: event.results[event.results.length - 1][0].confidence
        }));
        
        setInputMessage(transcript);
      };
      
      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setVoiceRecognition(prev => ({ ...prev, isListening: false, transcript: '' }));
        toast({
          title: "Voice Recognition Error",
          description: "Unable to recognize speech. Please try again.",
          status: "error",
          duration: 3000
        });
      };
      
      recognition.onend = () => {
        setVoiceRecognition(prev => ({ ...prev, isListening: false }));
      };
      
      voiceRef.current = recognition;
      setVoiceRecognition(prev => ({ ...prev, enabled: true }));
      
    } else {
      toast({
        title: "Voice Recognition Not Available",
        description: "Your browser does not support voice recognition.",
        status: "warning",
        duration: 5000
      });
    }
  }, [voiceRecognition.language]);

  // Message Handlers
  const handleSendMessage = useCallback(async () => {
    if (!inputMessage.trim() || isProcessing) return;
    
    const userMessage: ConversationMessage = {
      id: `msg-${Date.now()}`,
      type: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
      status: 'sent'
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsProcessing(true);
    setShowSuggestions(false);
    
    try {
      // Add processing message
      const processingMessage: ConversationMessage = {
        id: `msg-processing-${Date.now()}`,
        type: 'system',
        content: 'Thinking...',
        timestamp: new Date().toISOString(),
        status: 'processing'
      };
      
      setMessages(prev => [...prev, processingMessage]);
      
      // Process with AI agent
      const aiResponse: AIResponse = await aiAgent.processUserQuery(
        inputMessage,
        conversationContext
      );
      
      // Update processing message with AI response
      const assistantMessage: ConversationMessage = {
        id: processingMessage.id,
        type: 'assistant',
        content: aiResponse.content,
        timestamp: new Date().toISOString(),
        confidence: aiResponse.confidence,
        reasoning: aiResponse.reasoning,
        suggestedActions: aiResponse.suggestedActions,
        integrationInsights: aiResponse.integrationInsights,
        proactiveSuggestions: aiResponse.proactiveSuggestions,
        metadata: aiResponse.metadata,
        status: 'completed'
      };
      
      setMessages(prev => {
        const updated = prev.map(msg => 
          msg.id === processingMessage.id ? assistantMessage : msg
        );
        return updated;
      });
      
      // Update analytics
      updateConversationAnalytics();
      
      // Generate proactive suggestions
      if (aiResponse.proactiveSuggestions && aiResponse.proactiveSuggestions.length > 0) {
        generateProactiveSuggestions(aiResponse.proactiveSuggestions);
      }
      
    } catch (error) {
      console.error('AI processing error:', error);
      
      const errorMessage: ConversationMessage = {
        id: `msg-error-${Date.now()}`,
        type: 'error',
        content: 'I apologize, but I encountered an error processing your request. Please try again.',
        timestamp: new Date().toISOString(),
        status: 'failed'
      };
      
      setMessages(prev => {
        const updated = prev.map(msg => 
          msg.id === `msg-processing-${Date.now()}` ? errorMessage : msg
        );
        return updated;
      });
      
      toast({
        title: "Processing Error",
        description: "Failed to process your message. Please try again.",
        status: "error",
        duration: 3000
      });
    } finally {
      setIsProcessing(false);
    }
  }, [inputMessage, isProcessing, aiAgent, conversationContext]);

  const handleVoiceToggle = useCallback(() => {
    if (!voiceRef.current) return;
    
    if (voiceRecognition.isListening) {
      voiceRef.current.stop();
    } else {
      voiceRef.current.start();
    }
  }, [voiceRecognition.isListening]);

  const handleSuggestionClick = useCallback((suggestion: string) => {
    setInputMessage(suggestion);
    setShowSuggestions(false);
    inputRef.current?.focus();
  }, []);

  const handleActionClick = useCallback((action: string, params?: any) => {
    onAction(action, params);
  }, [onAction]);

  const handleFeedback = useCallback((messageId: string, helpful: boolean, reason?: string) => {
    setMessages(prev => prev.map(msg => 
      msg.id === messageId 
        ? { ...msg, userFeedback: { helpful, reason } }
        : msg
    ));
    
    // Send feedback to AI for learning
    if (aiAgent && aiAgent.recordFeedback) {
      aiAgent.recordFeedback(messageId, helpful, reason);
    }
  }, [aiAgent]);

  // Utility Functions
  const addWelcomeMessage = useCallback(() => {
    const welcomeMessage: ConversationMessage = {
      id: 'msg-welcome',
      type: 'assistant',
      content: `Hello! I'm ATOM's AI assistant. I can help you with:\n\n• Managing your ${integrations.length} integrations\n• Creating and optimizing workflows\n• Analyzing usage patterns\n• Generating automation suggestions\n• Providing insights and recommendations\n\nWhat would you like to accomplish today?`,
      timestamp: new Date().toISOString(),
      status: 'completed'
    };
    
    setMessages([welcomeMessage]);
  }, [integrations.length]);

  const generateSuggestions = useCallback(() => {
    const suggestionList = [
      'Create a new workflow for automated file sync',
      'Analyze my integration usage patterns',
      'Optimize my existing workflows',
      'Set up automated notifications',
      'Generate a performance report',
      'Connect a new integration',
      'Show me automation opportunities',
      'Help me troubleshoot an integration issue'
    ];
    
    // Filter suggestions based on input and context
    const filtered = suggestionList.filter(suggestion => 
      suggestion.toLowerCase().includes(inputMessage.toLowerCase()) ||
      suggestion.toLowerCase().includes(contextSuggestions(inputMessage).toLowerCase())
    );
    
    setSuggestions(filtered.slice(0, 5));
    setShowSuggestions(filtered.length > 0);
  }, [inputMessage]);

  const contextSuggestions = useCallback((input: string): string => {
    const lowerInput = input.toLowerCase();
    
    if (lowerInput.includes('workflow')) return 'workflow automation';
    if (lowerInput.includes('integration')) return 'integration management';
    if (lowerInput.includes('analyze')) return 'usage analysis';
    if (lowerInput.includes('optimize')) return 'workflow optimization';
    if (lowerInput.includes('create')) return 'content creation';
    if (lowerInput.includes('connect')) return 'integration setup';
    if (lowerInput.includes('troubleshoot')) return 'issue resolution';
    
    return 'general assistance';
  }, []);

  const generateProactiveSuggestions = useCallback((suggestions: any[]) => {
    // This would process AI proactive suggestions
    // and display them as quick actions or cards
    console.log('Proactive suggestions:', suggestions);
  }, []);

  const updateConversationAnalytics = useCallback(() => {
    const recentMessages = messages.slice(-50); // Last 50 messages
    const assistantMessages = recentMessages.filter(msg => msg.type === 'assistant');
    const feedbackMessages = assistantMessages.filter(msg => msg.userFeedback);
    
    const analytics: ConversationAnalytics = {
      totalMessages: messages.length,
      averageResponseTime: assistantMessages.reduce((sum, msg) => 
        sum + (msg.metadata?.responseTime || 0), 0) / Math.max(assistantMessages.length, 1),
      satisfactionScore: feedbackMessages.reduce((sum, msg) => 
        sum + (msg.userFeedback?.helpful ? 1 : 0), 0) / Math.max(feedbackMessages.length, 1),
      integrationUsage: {}, // Would be calculated from message content
      topicDistribution: {}, // Would be calculated from message content
      automationSuggestions: 0,
      workflowGenerations: 0,
      errorRate: recentMessages.filter(msg => msg.type === 'error').length / Math.max(recentMessages.length, 1)
    };
    
    setAnalytics(analytics);
  }, [messages]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const loadConversationAnalytics = useCallback(() => {
    // This would load analytics from backend or cache
    updateConversationAnalytics();
  }, [messages]);

  // UI Components
  const renderMessage = useCallback((message: ConversationMessage) => {
    const isUser = message.type === 'user';
    const isAssistant = message.type === 'assistant';
    const isSystem = message.type === 'system' || message.type === 'error';
    
    return (
      <Fade in key={message.id}>
        <Flex
          direction={isUser ? 'row-reverse' : 'row'}
          mb={4}
          align="start"
        >
          <Avatar
            size="md"
            bg={isUser ? 'blue.500' : isAssistant ? 'green.500' : isSystem ? 'red.500' : 'gray.500'}
            icon={isUser ? <FiUser /> : isAssistant ? <FiZap /> : isSystem ? <FiAlertTriangle /> : <FiInfo />}
            ml={isUser ? 3 : 0}
            mr={isUser ? 0 : 3}
          />
          
          <Box
            maxW="80%"
            bg={isUser ? 'blue.50' : isAssistant ? 'green.50' : isSystem ? 'red.50' : 'gray.50'}
            borderColor={isUser ? 'blue.200' : isAssistant ? 'green.200' : isSystem ? 'red.200' : 'gray.200'}
            borderWidth={1}
            borderRadius="lg"
            p={4}
            ml={isUser ? 3 : 0}
            mr={isUser ? 0 : 3}
            position="relative"
          >
            {/* Message Content */}
            <Text fontSize="sm" color={textColor} whiteSpace="pre-wrap">
              {message.content}
            </Text>
            
            {/* Confidence Badge */}
            {isAssistant && message.confidence && (
              <Badge
                size="xs"
                position="absolute"
                top={2}
                right={2}
                colorScheme={message.confidence > 0.8 ? 'green' : message.confidence > 0.6 ? 'yellow' : 'red'}
              >
                {Math.round(message.confidence * 100)}% confidence
              </Badge>
            )}
            
            {/* Reasoning */}
            {isAssistant && userPreferences.showReasoning && message.reasoning && (
              <Accordion mt={3} allowToggle>
                <AccordionItem border="none">
                  <AccordionButton px={0} py={2}>
                    <Box flex="1" textAlign="left" fontSize="xs" color="gray.600">
                      AI Reasoning
                    </Box>
                    <AccordionIcon />
                  </AccordionButton>
                  <AccordionPanel pb={2}>
                    <Text fontSize="xs" color="gray.700">
                      {message.reasoning}
                    </Text>
                  </AccordionPanel>
                </AccordionItem>
              </Accordion>
            )}
            
            {/* Integration Insights */}
            {isAssistant && userPreferences.showIntegrationInsights && message.integrationInsights && (
              <Accordion mt={3} allowToggle>
                <AccordionItem border="none">
                  <AccordionButton px={0} py={2}>
                    <Box flex="1" textAlign="left" fontSize="xs" color="gray.600">
                      Integration Insights
                    </Box>
                    <AccordionIcon />
                  </AccordionButton>
                  <AccordionPanel pb={2}>
                    <Text fontSize="xs" color="gray.700">
                      {JSON.stringify(message.integrationInsights, null, 2)}
                    </Text>
                  </AccordionPanel>
                </AccordionItem>
              </Accordion>
            )}
            
            {/* Suggested Actions */}
            {isAssistant && message.suggestedActions && message.suggestedActions.length > 0 && (
              <VStack mt={3} align="start" spacing={2}>
                <Text fontSize="xs" color="gray.600" fontWeight="bold">
                  Suggested Actions:
                </Text>
                {message.suggestedActions.map((action, index) => (
                  <Button
                    key={index}
                    size="xs"
                    colorScheme="blue"
                    variant="outline"
                    leftIcon={<FiZap />}
                    onClick={() => handleActionClick(action)}
                  >
                    {action}
                  </Button>
                ))}
              </VStack>
            )}
            
            {/* Message Footer */}
            <HStack mt={2} justify="space-between">
              <Text fontSize="xs" color="gray.500">
                {new Date(message.timestamp).toLocaleTimeString()}
              </Text>
              
              {isAssistant && !isSystem && message.status === 'completed' && (
                <HStack spacing={1}>
                  <Tooltip label="Helpful">
                    <IconButton
                      size="xs"
                      variant="ghost"
                      icon={<FiThumbsUp />}
                      colorScheme={message.userFeedback?.helpful ? 'green' : 'gray'}
                      onClick={() => handleFeedback(message.id, true)}
                    />
                  </Tooltip>
                  
                  <Tooltip label="Not Helpful">
                    <IconButton
                      size="xs"
                      variant="ghost"
                      icon={<FiThumbsDown />}
                      colorScheme={message.userFeedback?.helpful === false ? 'red' : 'gray'}
                      onClick={() => handleFeedback(message.id, false)}
                    />
                  </Tooltip>
                  
                  <Tooltip label="Copy">
                    <IconButton
                      size="xs"
                      variant="ghost"
                      icon={<FiCopy />}
                      onClick={() => navigator.clipboard.writeText(message.content)}
                    />
                  </Tooltip>
                </HStack>
              )}
            </HStack>
            
            {/* User Feedback */}
            {message.userFeedback && (
              <Alert
                status={message.userFeedback.helpful ? 'success' : 'warning'}
                mt={2}
                size="xs"
              >
                <AlertIcon />
                <AlertTitle fontSize="xs">
                  {message.userFeedback.helpful ? 'Thanks for the feedback!' : 'Thank you for helping me improve!'}
                </AlertTitle>
                {message.userFeedback.reason && (
                  <AlertDescription fontSize="xs">
                    Reason: {message.userFeedback.reason}
                  </AlertDescription>
                )}
              </Alert>
            )}
          </Box>
        </Flex>
      </Fade>
    );
  }, [textColor, userPreferences, handleActionClick, handleFeedback]);

  // Main Render
  return (
    <Container maxW="container.xl" h={height} w={width} py={4}>
      <VStack h="full" spacing={4} align="stretch">
        {/* Header */}
        <HStack justify="space-between" w="full" px={4}>
          <VStack align="start" spacing={1}>
            <Heading size="lg" color={textColor}>
              🤖 ATOM AI Assistant
            </Heading>
            <Text fontSize="sm" color="gray.600">
              Natural language control for integrations, workflows, and analytics
            </Text>
          </VStack>
          
          <HStack spacing={2}>
            {/* Insights Button */}
            <Tooltip label="Conversation Insights">
              <IconButton
                variant="outline"
                icon={<FiTrendingUp />}
                onClick={insightsOnOpen}
              />
            </Tooltip>
            
            {/* History Button */}
            <Tooltip label="Conversation History">
              <IconButton
                variant="outline"
                icon={<FiClock />}
                onClick={historyOnOpen}
              />
            </Tooltip>
            
            {/* Suggestions Button */}
            <Tooltip label="Quick Suggestions">
              <IconButton
                variant="outline"
                icon={<FiHelpCircle />}
                onClick={suggestionsOnOpen}
              />
            </Tooltip>
            
            {/* Settings Button */}
            <Tooltip label="Settings">
              <IconButton
                variant="outline"
                icon={<FiSettings />}
                onClick={settingsOnOpen}
              />
            </Tooltip>
          </HStack>
        </HStack>
        
        {/* Messages Area */}
        <Box
          flex="1"
          overflow="auto"
          bg={bgColor}
          borderColor={borderColor}
          borderWidth={1}
          borderRadius="lg"
          p={4}
        >
          <VStack spacing={4} align="stretch">
            {messages.map(renderMessage)}
            
            {isProcessing && (
              <HStack spacing={3}>
                <Spinner size="sm" color="green.500" />
                <Text fontSize="sm" color="gray.600">
                  Processing your request...
                </Text>
              </HStack>
            )}
            
            <div ref={messagesEndRef} />
          </VStack>
        </Box>
        
        {/* Suggestions */}
        {showSuggestions && suggestions.length > 0 && (
          <Card>
            <CardBody>
              <VStack align="start" spacing={2}>
                <Text fontSize="sm" fontWeight="bold" color="gray.700">
                  Suggestions:
                </Text>
                <HStack spacing={2} flexWrap="wrap">
                  {suggestions.map((suggestion, index) => (
                    <Button
                      key={index}
                      size="xs"
                      variant="outline"
                      onClick={() => handleSuggestionClick(suggestion)}
                    >
                      {suggestion}
                    </Button>
                  ))}
                </HStack>
              </VStack>
            </CardBody>
          </Card>
        )}
        
        {/* Input Area */}
        <Card>
          <CardBody>
            <VStack spacing={3}>
              {/* Voice Recognition Status */}
              {voiceRecognition.enabled && (
                <HStack spacing={2} justify="center">
                  {voiceRecognition.isListening ? (
                    <>
                      <Spinner size="xs" color="red.500" />
                      <Text fontSize="xs" color="red.500">
                        Listening... {voiceRecognition.transcript}
                      </Text>
                    </>
                  ) : (
                    <Text fontSize="xs" color="gray.500">
                      Voice recognition ready
                    </Text>
                  )}
                </HStack>
              )}
              
              <InputGroup>
                <Input
                  ref={inputRef}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="Ask me anything about your integrations, workflows, or analytics..."
                  isDisabled={isProcessing}
                  pr={20}
                />
                
                <InputRightElement width="20">
                  <HStack spacing={1}>
                    {/* Voice Button */}
                    {userPreferences.voiceEnabled && (
                      <Tooltip label={voiceRecognition.isListening ? 'Stop Recording' : 'Start Voice'}>
                        <IconButton
                          size="sm"
                          variant="ghost"
                          icon={voiceRecognition.isListening ? <FiVolumeX /> : <FiMic />}
                          color={voiceRecognition.isListening ? 'red.500' : 'gray.500'}
                          onClick={handleVoiceToggle}
                        />
                      </Tooltip>
                    )}
                    
                    {/* Send Button */}
                    <Tooltip label="Send Message">
                      <IconButton
                        size="sm"
                        variant="ghost"
                        icon={<FiSend />}
                        colorScheme="blue"
                        isDisabled={!inputMessage.trim() || isProcessing}
                        onClick={handleSendMessage}
                      />
                    </Tooltip>
                  </HStack>
                </InputRightElement>
              </InputGroup>
            </VStack>
          </CardBody>
        </Card>
      </VStack>
    </Container>
  );
};

// Supporting Type Definitions
interface UserPreferences {
  language: string;
  timezone: string;
  voiceEnabled: boolean;
  autoSuggestion: boolean;
  showReasoning: boolean;
  showIntegrationInsights: boolean;
  conversationStyle: 'formal' | 'casual' | 'technical' | 'friendly';
  responseSpeed: 'fast' | 'balanced' | 'thorough';
  suggestionFrequency: 'low' | 'medium' | 'high';
}

interface OrganizationContext {
  id: string;
  name: string;
  industry: string;
  size: string;
  department: string;
}

interface WorkflowContext {
  id: string;
  name: string;
  status: string;
  integrations: string[];
}

interface UserPermissions {
  integrations: string[];
  actions: string[];
  dataAccess: string[];
}

interface TimeContext {
  timezone: string;
  workingHours: {
    start: string;
    end: string;
  };
  businessDays: number[];
}

interface GeographicContext {
  country: string;
  region: string;
  language: string;
}

// Global type declarations for voice recognition
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

export default AtomAIConversationInterface;