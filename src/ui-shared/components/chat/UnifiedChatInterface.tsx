import React, { useState, useRef, useEffect } from 'react';
import { Box, VStack, HStack, Text, Input, Button, IconButton, useColorModeValue } from '@chakra-ui/react';
import { FiSend, FiMic, FiMicOff, FiSettings, FiZap } from 'react-icons/fi';

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

interface UnifiedChatInterfaceProps {
  onWorkflowTrigger?: (workflowData: any) => void;
  onVoiceCommand?: (command: string) => void;
  onMultiStepProcess?: (process: MultiStepProcess) => void;
}

export const UnifiedChatInterface: React.FC<UnifiedChatInterfaceProps> = ({
  onWorkflowTrigger,
  onVoiceCommand,
  onMultiStepProcess,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'agent',
      content: "Hi! I'm Atom, your intelligent assistant. I can help you with workflows, automation, calendar management, and much more. What would you like to do today?",
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

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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

    // Simulate processing and response
    setTimeout(() => {
      const response = generateAgentResponse(inputValue);
      setMessages(prev => [...prev, response]);
      setIsProcessing(false);
    }, 1000);
  };

  const generateAgentResponse = (userInput: string): ChatMessage => {
    const input = userInput.toLowerCase();

    // Workflow automation triggers
    if (input.includes('workflow') || input.includes('automate') || input.includes('when')) {
      const workflowData = parseWorkflowIntent(userInput);
      if (onWorkflowTrigger) {
        onWorkflowTrigger(workflowData);
      }

      return {
        id: Date.now().toString(),
        type: 'agent',
        content: `I'll create a workflow for you! I detected you want to automate: "${workflowData.description}". Let me set this up...`,
        timestamp: new Date(),
        metadata: {
          actionType: 'workflow_creation',
          workflowId: `wf_${Date.now()}`,
          stepProgress: 1,
          suggestedActions: ['Configure triggers', 'Set up actions', 'Test workflow']
        }
      };
    }

    // Multi-step process initiation
    if (input.includes('schedule') || input.includes('meeting') || input.includes('calendar')) {
      const process = createCalendarProcess(userInput);
      setActiveProcess(process);
      if (onMultiStepProcess) {
        onMultiStepProcess(process);
      }

      return {
        id: Date.now().toString(),
        type: 'agent',
        content: `Let's schedule that for you! We'll go through this step by step. First, ${process.steps[0].description}`,
        timestamp: new Date(),
        metadata: {
          actionType: 'multi_step_process',
          workflowId: process.id,
          stepProgress: 1
        }
      };
    }

    // Task management
    if (input.includes('task') || input.includes('todo') || input.includes('remind')) {
      return {
        id: Date.now().toString(),
        type: 'agent',
        content: "I can help manage your tasks across all connected platforms (Notion, Trello, Asana, etc.). Would you like me to create a task, check your task list, or set up automated task management?",
        timestamp: new Date(),
        metadata: {
          suggestedActions: ['Create new task', 'View all tasks', 'Set up task automation', 'Sync tasks across platforms']
        }
      };
    }

    // Email management
    if (input.includes('email') || input.includes('inbox') || input.includes('send')) {
      return {
        id: Date.now().toString(),
        type: 'agent',
        content: "I can help with your emails! I can read, send, schedule, and automate email workflows across Gmail and Outlook. What would you like to do?",
        timestamp: new Date(),
        metadata: {
          suggestedActions: ['Check unread emails', 'Send an email', 'Schedule email sending', 'Set up email automation']
        }
      };
    }

    // Default response
    return {
      id: Date.now().toString(),
      type: 'agent',
      content: "I understand you're looking for assistance. I can help you with workflow automation, calendar management, task coordination, email handling, and much more. What specific action would you like me to take?",
      timestamp: new Date(),
      metadata: {
        suggestedActions: [
          "Create automation workflow",
          "Manage calendar events",
          "Coordinate tasks",
          "Handle communications",
          "Generate reports"
        ]
      }
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
          </HStack>
          <HStack>
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

      {/* Messages Area */}
      <Box flex="1" p={4} overflowY="auto">
        <VStack spacing={4} align="stretch">
          {messages.map((message) => (
            <Box
              key={message.id}
              alignSelf={message.type === 'user' ? 'flex-end' : 'flex-start'}
              maxWidth="70%"
            >
              <Box
                bg={message.type === 'user' ? 'blue.500' : 'gray.100'}
                color={message.type === 'user' ? 'white' : 'gray.800'}
                p={3}
                borderRadius="lg"
                boxShadow="sm"
              >
                <Text fontSize="sm">{message.content}</Text>
                <Text fontSize="xs" opacity={0.7} mt={1}>
                  {message.timestamp.toLocaleTimeString()}
                </Text>
              </Box>

              {/* Suggested Actions */}
              {message.metadata?.suggestedActions && (
                <HStack mt={2} spacing={2} flexWrap="wrap">
                  {message.metadata.suggestedActions.map((action, index) => (
                    <Button
                      key={index}
                      size="xs"
                      variant="outline"
                      onClick={() => handleQuickAction(action)}
                    >
                      {action}
                    </Button>
                  ))}
                </HStack>
              )}
            </Box>
          ))}

          {isProcessing && (
            <Box alignSelf="flex-start" maxWidth="70%">
              <Box
                bg="gray.100"
                color="gray.800"
                p={3}
                borderRadius="lg"
                boxShadow="sm"
              >
                <Text fontSize="sm">Atom is thinking...</Text>
              </Box>
            </Box>
          )}

          <div ref={messagesEndRef} />
        </VStack>
      </Box>

      {/* Input Area */}
      <Box p={4} borderTop="1px solid" borderColor={borderColor}>
        <VStack spacing={3}>
          {/* Multi-step Process Progress */}
          {activeProcess && (
            <Box width="100%" bg="blue.50" p={3} borderRadius="md">
              <Text fontSize="sm" fontWeight="medium" mb={2}>
                Current Process: Step {activeProcess.currentStep + 1} of {activeProcess.totalSteps}
              </Text>
              <VStack spacing={1} align="stretch">
                {activeProcess.steps.map((step, index) => (
                  <HStack key={step.id} spacing={2}>
                    <Box
                      width="20px"
                      height="20px"
                      borderRadius="full"
                      bg={
                        step.status === 'completed' ? 'green.500' :
                        step.status === 'active' ? 'blue.500' : 'gray.300'
                      }
                      display="flex"
                      alignItems="center"
                      justifyContent="center"
                    >
                      <Text fontSize="xs" color="white" fontWeight="bold">
                        {index + 1}
                      </Text>
                    </Box>
                    <Text fontSize="sm" opacity={step.status === 'pending' ? 0.6 : 1}>
                      {step.title}
                    </Text>
                  </HStack>
                ))}
              </VStack>
            </Box>
          )}

          <HStack width="100%" spacing={2}>
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask Atom to automate, schedule, or coordinate anything..."
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              isDisabled={isProcessing}
            />
            <IconButton
              aria-label={isListening ? "Stop listening" : "Start voice command"}
              icon={isListening ? <FiMicOff /> : <FiMic />}
              onClick={handleVoiceToggle}
              colorScheme={isListening ? "red" : "gray"}
              isDisabled={isProcessing}
            />
            <Button
              leftIcon={<FiSend />}
              onClick={handleSendMessage}
              colorScheme="blue"
              isDisabled={!inputValue.trim() || isProcessing}
            >
              Send
            </Button>
          </HStack>
        </VStack>
      </Box>
    </Box>
  );
};

export default UnifiedChatInterface;
