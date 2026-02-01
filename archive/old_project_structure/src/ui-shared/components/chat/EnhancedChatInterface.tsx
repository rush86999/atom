import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box, VStack, HStack, Text, Input, Button, IconButton,
  useColorModeValue, Badge, Progress, Tooltip, Alert, AlertIcon,
  Flex, Spacer, Divider, Collapse
} from '@chakra-ui/react';
import { FiSend, FiMic, FiMicOff, FiSettings, FiZap, FiBrain, FiTrash2, FiInfo } from 'react-icons/fi';
import { useChatMemory, ConversationMemory, MemoryContext } from '../../../../frontend-nextjs/hooks/useChatMemory';

interface ChatMessage {
  id: string;
  type: 'user' | 'agent' | 'system';
  content: string;
  timestamp: Date;
  metadata?: {
    actionType?: string;
    workflowId?: string;
    stepProgress?: number;
    suggestedActions?: string[];
    memoryContext?: MemoryContext;
  };
}

interface MultiStepProcess {
  id: string;
  currentStep: number;
  totalSteps: number;
  steps: Array<{
    id: string;
    title: string;
    description: string;
    status: 'pending' | 'active' | 'completed' | 'failed';
    requiredInput?: string;
  }>;
}

interface EnhancedChatInterfaceProps {
  userId: string;
  sessionId: string;
  onWorkflowTrigger?: (workflowData: any) => void;
  onVoiceCommand?: (command: string) => void;
  onMultiStepProcess?: (process: MultiStepProcess) => void;
  enableMemory?: boolean;
  showMemoryControls?: boolean;
}

export const EnhancedChatInterface: React.FC<EnhancedChatInterfaceProps> = ({
  userId,
  sessionId,
  onWorkflowTrigger,
  onVoiceCommand,
  onMultiStepProcess,
  enableMemory = true,
  showMemoryControls = true,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'agent',
      content: "Hi! I'm Atom, your intelligent assistant with memory capabilities. I can remember our conversations and provide context-aware responses. What would you like to do today?",
      timestamp: new Date(),
      metadata: {
        suggestedActions: [
          "Create a workflow automation",
          "Schedule a meeting",
          "Check my calendar",
          "Send emails automatically",
          "Manage tasks across platforms"
        ]
      }
    }
  ]);

  const [inputValue, setInputValue] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [activeProcess, setActiveProcess] = useState<MultiStepProcess | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showMemoryInfo, setShowMemoryInfo] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const memoryBgColor = useColorModeValue('blue.50', 'blue.900');

  // Initialize memory system
  const {
    memories,
    memoryContext,
    memoryStats,
    isLoading: memoryLoading,
    error: memoryError,
    storeMemory,
    getMemoryContext,
    clearSessionMemory,
    refreshMemoryStats,
    hasRelevantContext,
    contextRelevanceScore
  } = useChatMemory({
    userId,
    sessionId,
    enableMemory,
    autoStoreMessages: true,
    contextWindow: 10
  });

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (memoryError) {
      console.error('Memory system error:', memoryError);
    }
  }, [memoryError]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isProcessing) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsProcessing(true);

    try {
      // Get memory context for enhanced response
      let memoryContext: MemoryContext | null = null;
      if (enableMemory) {
        memoryContext = await getMemoryContext(inputValue);
      }

      // Generate enhanced response with memory context
      const response = await generateEnhancedResponse(inputValue, memoryContext);

      setMessages(prev => [...prev, response]);

      // Auto-store the conversation in memory (handled by useChatMemory hook)

    } catch (error) {
      console.error('Error processing message:', error);
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        type: 'agent',
        content: "I encountered an issue while processing your request. Please try again.",
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsProcessing(false);
    }
  };

  const generateEnhancedResponse = async (
    userInput: string,
    memoryContext: MemoryContext | null
  ): Promise<ChatMessage> => {
    const input = userInput.toLowerCase();

    // Build context-aware response
    let responseContent = '';
    let metadata: ChatMessage['metadata'] = {
      suggestedActions: []
    };

    // Add memory context to metadata if available
    if (memoryContext && hasRelevantContext) {
      metadata.memoryContext = memoryContext;

      if (memoryContext.relevanceScore > 0.7) {
        responseContent += `I recall our previous discussion about this. `;
      } else if (memoryContext.relevanceScore > 0.4) {
        responseContent += `Based on our past conversations, `;
      }
    }

    // Workflow automation triggers
    if (input.includes('workflow') || input.includes('automate') || input.includes('when')) {
      const workflowData = parseWorkflowIntent(userInput);
      if (onWorkflowTrigger) {
        onWorkflowTrigger(workflowData);
      }

      responseContent += `I'll create a workflow for you! I detected you want to automate: "${workflowData.description}". Let me set this up...`;
      metadata.actionType = 'workflow_creation';
      metadata.workflowId = `wf_${Date.now()}`;
      metadata.stepProgress = 1;
      metadata.suggestedActions = ['Configure triggers', 'Set up actions', 'Test workflow'];
    }
    // Multi-step process initiation
    else if (input.includes('schedule') || input.includes('meeting') || input.includes('calendar')) {
      const process = createCalendarProcess(userInput);
      setActiveProcess(process);
      if (onMultiStepProcess) {
        onMultiStepProcess(process);
      }

      responseContent += `Let's schedule that for you! We'll go through this step by step. First, ${process.steps[0].description}`;
      metadata.actionType = 'multi_step_process';
      metadata.workflowId = process.id;
      metadata.stepProgress = 1;
    }
    // Task management
    else if (input.includes('task') || input.includes('todo') || input.includes('remind')) {
      responseContent = "I can help manage your tasks across all connected platforms (Notion, Trello, Asana, etc.). Would you like me to create a task, check your task list, or set up automated task management?";
      metadata.suggestedActions = ['Create new task', 'View all tasks', 'Set up task automation', 'Sync tasks across platforms'];
    }
    // Email management
    else if (input.includes('email') || input.includes('inbox') || input.includes('send')) {
      responseContent = "I can help with your emails! I can read, send, schedule, and automate email workflows across Gmail and Outlook. What would you like to do?";
      metadata.suggestedActions = ['Check unread emails', 'Send an email', 'Schedule email sending', 'Set up email automation'];
    }
    // Memory-related queries
    else if (input.includes('remember') || input.includes('recall') || input.includes('previous')) {
      if (memoryContext && hasRelevantContext) {
        const recentTopics = memoryContext.shortTermMemories
          .slice(0, 3)
          .map(m => m.content.split(' ').slice(0, 10).join(' ') + '...')
          .join(', ');

        responseContent = `I remember our recent discussions about: ${recentTopics}. How can I help you with these topics?`;
      } else {
        responseContent = "I don't have much context about our previous conversations yet. Let's build some memory together!";
      }
    }
    // Default enhanced response
    else {
      responseContent = "I understand you're looking for assistance. I can help you with workflow automation, calendar management, task coordination, email handling, and much more. What specific action would you like me to take?";
      metadata.suggestedActions = [
        "Create automation workflow",
        "Manage calendar events",
        "Coordinate tasks",
        "Handle communications",
        "Generate reports"
      ];
    }

    return {
      id: Date.now().toString(),
      type: 'agent',
      content: responseContent,
      timestamp: new Date(),
      metadata
    };
  };

  const parseWorkflowIntent = (input: string) => {
    return {
      description: input,
      trigger: detectTrigger(input),
      actions: detectActions(input),
      services: detectServices(input)
    };
  };

  const detectTrigger = (input: string) => {
    if (input.includes('when') && input.includes('email')) return { type: 'email_received', service: 'gmail' };
    if (input.includes('when') && input.includes('calendar')) return { type: 'event_created', service: 'google_calendar' };
    if (input.includes('when') && input.includes('slack')) return { type: 'message_received', service: 'slack' };
    return { type: 'manual', service: 'atom' };
  };

  const detectActions = (input: string) => {
    const actions = [];
    if (input.includes('send') && input.includes('email')) actions.push({ type: 'send_email', service: 'gmail' });
    if (input.includes('create') && input.includes('task')) actions.push({ type: 'create_task', service: 'notion' });
    if (input.includes('schedule') && input.includes('meeting')) actions.push({ type: 'create_event', service: 'google_calendar' });
    return actions;
  };

  const detectServices = (input: string) => {
    const services = new Set<string>();
    if (input.includes('gmail') || input.includes('email')) services.add('gmail');
    if (input.includes('calendar')) services.add('google_calendar');
    if (input.includes('slack')) services.add('slack');
    if (input.includes('notion')) services.add('notion');
    if (input.includes('trello')) services.add('trello');
    if (input.includes('asana')) services.add('asana');
    return Array.from(services);
  };

  const createCalendarProcess = (input: string): MultiStepProcess => {
    return {
      id: `process_${Date.now()}`,
      currentStep: 0,
      totalSteps: 4,
      steps: [
        {
          id: 'step1',
          title: 'Event Details',
          description: 'tell me the event title and description',
          status: 'active',
          requiredInput: 'event_details'
        },
        {
          id: 'step2',
          title: 'Date & Time',
          description: 'specify when this event should happen',
          status: 'pending',
          requiredInput: 'datetime'
        },
        {
          id: 'step3',
          title: 'Attendees',
          description: 'let me know who should be invited',
          status: 'pending',
          requiredInput: 'attendees'
        },
        {
          id: 'step4',
          title: 'Confirmation',
          description: 'review and confirm the event details',
          status: 'pending'
        }
      ]
    };
  };

  const handleVoiceToggle = () => {
    if (isListening) {
      setIsListening(false);
      // Stop voice recognition
    } else {
      setIsListening(true);
      // Start voice recognition
      if (onVoiceCommand) {
        // This would be connected to actual voice recognition
        setTimeout(() => {
          const mockCommand = "Schedule a team meeting for tomorrow at 2 PM";
          setInputValue(mockCommand);
          setIsListening(false);
        }, 2000);
      }
    }
  };

  const handleQuickAction = (action: string) => {
    setInputValue(action);
    handleSendMessage();
  };

  const handleClearMemory = async () => {
    await clearSessionMemory();
    setMessages(prev => [
      {
        id: '1',
        type: 'agent',
        content: "Memory cleared! I've started fresh. How can I help you?",
        timestamp: new Date(),
      }
    ]);
  };

  const MemoryIndicator = () => {
    if (!enableMemory || !memoryStats) return null;

    return (
      <Tooltip label={`Memory: ${memoryStats.shortTermMemoryCount} items, ${memoryStats.userPatternCount} patterns`}>
        <Badge
          colorScheme={hasRelevantContext ? "green" : "gray"}
          cursor="pointer"
          onClick={() => setShowMemoryInfo(!showMemoryInfo)}
        >
          <HStack spacing={1}>
            <FiBrain size={12} />
            <Text fontSize="xs">
              {memoryStats.shortTermMemoryCount}
            </Text>
          </HStack>
        </Badge>
      </Tooltip>
    );
  };

  const MemoryContextDisplay = ({ memoryContext }: { memoryContext: MemoryContext }) => {
    if (!memoryContext || memoryContext.relevanceScore < 0.3) return null;

    return (
      <Box
        bg={memoryBgColor}
        p={3}
        borderRadius="md"
        borderLeft="4px solid"
        borderLeftColor="blue.500"
        fontSize="sm"
      >
        <HStack mb={2}>
          <FiBrain />
          <Text fontWeight="medium">Context Memory</Text>
          <Badge colorScheme="blue" fontSize="xs">
            {Math.round(memoryContext.relevanceScore * 100)}% relevant
          </Badge>
        </HStack>

        <Text mb={2} opacity={0.8}>
          {memoryContext.conversationSummary}
        </Text>

        <HStack spacing={4} fontSize="xs">
          <Text>Short-term: {memoryContext.shortTermMemories.length}</Text>
          <Text>Long-term: {memoryContext.longTermMemories.length}</Text>
          <Text>Patterns: {memoryContext.userPatterns.length}</Text>
        </HStack>
      </Box>
    );
  };

  return (
    <Box
      height="100%"
      display="flex"
      flexDirection="column"
      bg={bgColor}
      border="1px solid"
      borderColor={borderColor}
      borderRadius="lg"
      overflow="hidden"
    >
      {/* Chat Header */}
      <Box
        p={4}
        borderBottom="1px solid"
        borderColor={borderColor}
        bg="blue.500"
        color="white"
      >
        <HStack justify="space-between">
          <HStack>
            <FiZap />
            <Text fontWeight="bold">Atom Assistant</Text>
            {enableMemory && <MemoryIndicator />}
          </HStack>
          <HStack>
            {showMemoryControls && enableMemory && (
              <Tooltip label="Clear conversation memory">
                <IconButton
                  aria-label="Clear memory"
                  icon={<FiTrash2 />}
                  variant="ghost"
                  color="white"
                  size="sm"
                  onClick={handleClearMemory}
                  isLoading={memoryLoading}
                />
              </Tooltip>
            )}
            <Tooltip label="Memory information">
              <IconButton
                aria-label="Memory info"
                icon={<FiInfo />}
                variant="ghost"
                color="white"
                size="sm"
                onClick={() => setShowMemoryInfo(!showMemoryInfo)}
              />
            </Tooltip>
            <IconButton
              aria-label="Settings"
              icon={<FiSettings />}
              variant="ghost"
              color="white"
              size="sm"
            />
          </HStack>
        </HStack>
      </Box>

      {/* Memory Information Panel */}
      <Collapse in={showMemoryInfo && enableMemory}>
        <Box p={3} bg={memoryBgColor} borderBottom="1px solid" borderColor={borderColor}>
          <VStack align="stretch" spacing={2}>
            <HStack justify="space-between">
              <Text fontWeight="medium" fontSize="sm">Memory System</Text>
              <Badge colorScheme={memoryStats?.lancedbAvailable ? "green" : "orange"} fontSize="xs">
                {memoryStats?.lancedbAvailable ? "LanceDB Connected" : "Local Only"}
              </Badge>
            </HStack>

            {memoryStats && (
              <HStack spacing={4} fontSize="xs">
                <Text>Short-term: {memoryStats.shortTermMemoryCount}</Text>
                <Text>Patterns: {memoryStats.userPatternCount}</Text>
                <Text>Sessions: {memoryStats.activeSessions}</Text>
                <Text>Accesses: {memoryStats.totalMemoryAccesses}</Text>
              </HStack>
            )}

            {memoryError && (
              <Alert status="warning" size="sm" borderRadius="md">
                <AlertIcon />
                <Text fontSize="xs">{memoryError}</Text>
              </Alert>
            )}

            <Progress
              value={contextRelevanceScore * 100}
              size="xs"
              colorScheme="blue"
              borderRadius="full"
            />
            <Text fontSize="xs" textAlign="center">
              Context Relevance: {Math.round(contextRelevanceScore * 100)}%
            </Text>
          </VStack>
        </Box>
      </Collapse>

      {/* Messages Area */}
      <Box flex="1" p={4} overflowY="auto">
        <VStack spacing={4} align="stretch">
          {messages.map((message) => (
            <Box key={message.id}>
              {/* Memory Context Display */}
              {message.metadata?.memoryContext && (
                <MemoryContextDisplay memoryContext={message.metadata
