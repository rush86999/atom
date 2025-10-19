import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Input,
  Button,
  IconButton,
  Card,
  CardBody,
  CardFooter,
  Badge,
  Avatar,
  useToast,
  Spinner,
  Flex,
  Divider,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Progress,
  Tag,
  TagLabel,
  TagCloseButton,
} from '@chakra-ui/react';
import {
  SendIcon,
  BotIcon,
  UserIcon,
  PlayIcon,
  CalendarIcon,
  SettingsIcon,
  CheckIcon,
  ClockIcon,
  EditIcon,
  TrashIcon,
  PlusIcon,
} from '@chakra-ui/icons';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  workflowData?: {
    workflowId?: string;
    workflowName?: string;
    stepsCount?: number;
    isScheduled?: boolean;
    requiresConfirmation?: boolean;
  };
  actions?: ChatAction[];
}

interface ChatAction {
  type: 'execute' | 'schedule' | 'edit' | 'confirm' | 'cancel';
  label: string;
  workflowId?: string;
  data?: any;
}

interface WorkflowChatProps {
  userId?: string;
  onWorkflowCreated?: (workflowId: string) => void;
  onWorkflowExecuted?: (workflowId: string, executionId: string) => void;
}

const WorkflowChat: React.FC<WorkflowChatProps> = ({
  userId = 'anonymous',
  onWorkflowCreated,
  onWorkflowExecuted,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [selectedWorkflow, setSelectedWorkflow] = useState<any>(null);
  const toast = useToast();

  // Initialize with welcome message
  useEffect(() => {
    const welcomeMessage: ChatMessage = {
      id: 'welcome',
      type: 'assistant',
      content: 'Hi! I can help you create automated workflows. Tell me what you\'d like to automate, for example: "Create a workflow that sends me an email when I receive a calendar invitation" or "Automate my task creation from emails".',
      timestamp: new Date(),
    };
    setMessages([welcomeMessage]);
    setSessionId(`session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      type: 'user',
      content: inputMessage,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/workflow-agent/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputMessage,
          user_id: userId,
          session_id: sessionId,
          conversation_history: messages.slice(-10).map(msg => ({
            role: msg.type === 'user' ? 'user' : 'assistant',
            content: msg.content,
          })),
        }),
      });

      const data = await response.json();

      if (data.success) {
        const assistantMessage: ChatMessage = {
          id: `assistant_${Date.now()}`,
          type: 'assistant',
          content: data.response.message,
          timestamp: new Date(),
          workflowData: data.response.workflow_id ? {
            workflowId: data.response.workflow_id,
            workflowName: data.response.workflow_name,
            stepsCount: data.response.steps_count,
            isScheduled: data.response.is_scheduled,
            requiresConfirmation: data.response.requires_confirmation,
          } : undefined,
          actions: data.response.actions || [],
        };

        setMessages(prev => [...prev, assistantMessage]);

        // Call callback if workflow was created
        if (data.response.workflow_id && onWorkflowCreated) {
          onWorkflowCreated(data.response.workflow_id);
        }
      } else {
        throw new Error(data.error || 'Failed to process message');
      }
    } catch (error) {
      console.error('Error sending message:', error);
      toast({
        title: 'Error',
        description: 'Failed to process your message. Please try again.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });

      const errorMessage: ChatMessage = {
        id: `error_${Date.now()}`,
        type: 'assistant',
        content: 'Sorry, I encountered an error while processing your request. Please try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActionClick = async (action: ChatAction) => {
    switch (action.type) {
      case 'execute':
        await executeWorkflow(action.workflowId!);
        break;
      case 'schedule':
        await scheduleWorkflow(action.workflowId!);
        break;
      case 'edit':
        await editWorkflow(action.workflowId!);
        break;
      case 'confirm':
        await confirmWorkflow(action.workflowId!);
        break;
      case 'cancel':
        await cancelWorkflow(action.workflowId!);
        break;
    }
  };

  const executeWorkflow = async (workflowId: string) => {
    try {
      const response = await fetch('/api/workflow-agent/execute-generated', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          workflow_id: workflowId,
          input_data: {},
        }),
      });

      const data = await response.json();

      if (data.success) {
        toast({
          title: 'Workflow Started',
          description: `Execution ${data.execution_id} has started`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });

        if (onWorkflowExecuted) {
          onWorkflowExecuted(workflowId, data.execution_id);
        }

        // Add execution confirmation message
        const executionMessage: ChatMessage = {
          id: `execution_${Date.now()}`,
          type: 'assistant',
          content: `Workflow execution started! You can monitor the progress in the Workflow Automation tab.`,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, executionMessage]);
      } else {
        throw new Error(data.error || 'Failed to execute workflow');
      }
    } catch (error) {
      console.error('Error executing workflow:', error);
      toast({
        title: 'Execution Failed',
        description: 'Failed to start workflow execution',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const scheduleWorkflow = async (workflowId: string) => {
    // Open schedule modal
    setSelectedWorkflow({ id: workflowId });
    onOpen();
  };

  const editWorkflow = async (workflowId: string) => {
    toast({
      title: 'Edit Workflow',
      description: 'Opening workflow editor...',
      status: 'info',
      duration: 2000,
      isClosable: true,
    });
    // In a real implementation, this would navigate to the workflow editor
  };

  const confirmWorkflow = async (workflowId: string) => {
    await executeWorkflow(workflowId);
  };

  const cancelWorkflow = async (workflowId: string) => {
    toast({
      title: 'Workflow Cancelled',
      description: 'The workflow creation was cancelled',
      status: 'info',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const renderMessage = (message: ChatMessage) => {
    const isUser = message.type === 'user';

    return (
      <Box
        key={message.id}
        alignSelf={isUser ? 'flex-end' : 'flex-start'}
        maxW="80%"
        mb={4}
      >
        <HStack spacing={3} align="start">
          {!isUser && (
            <Avatar
              size="sm"
              icon={<BotIcon />}
              bg="blue.500"
              color="white"
            />
          )}
          <Card
            bg={isUser ? 'blue.500' : 'gray.100'}
            color={isUser ? 'white' : 'gray.800'}
            borderRadius="lg"
            boxShadow="sm"
          >
            <CardBody py={3} px={4}>
              <Text whiteSpace="pre-wrap">{message.content}</Text>

              {message.workflowData && (
                <Box mt={3} p={3} bg={isUser ? 'blue.600' : 'white'} borderRadius="md">
                  <VStack align="start" spacing={2}>
                    <HStack>
                      <Badge colorScheme="green">
                        {message.workflowData.stepsCount} steps
                      </Badge>
                      {message.workflowData.isScheduled && (
                        <Badge colorScheme="purple">
                          <ClockIcon mr={1} /> Scheduled
                        </Badge>
                      )}
                    </HStack>
                    <Text fontSize="sm" fontWeight="medium">
                      {message.workflowData.workflowName}
                    </Text>
                  </VStack>
                </Box>
              )}
            </CardBody>

            {message.actions && message.actions.length > 0 && (
              <CardFooter pt={0} px={4} pb={3}>
                <HStack spacing={2} wrap="wrap">
                  {message.actions.map((action, index) => (
                    <Button
                      key={index}
                      size="sm"
                      variant={action.type === 'execute' ? 'solid' : 'outline'}
                      colorScheme={action.type === 'execute' ? 'green' : 'blue'}
                      leftIcon={getActionIcon(action.type)}
                      onClick={() => handleActionClick(action)}
                    >
                      {action.label}
                    </Button>
                  ))}
                </HStack>
              </CardFooter>
            )}
          </Card>
          {isUser && (
            <Avatar
              size="sm"
              icon={<UserIcon />}
              bg="gray.500"
              color="white"
            />
          )}
        </HStack>
        <Text
          fontSize="xs"
          color="gray.500"
          mt={1}
          textAlign={isUser ? 'right' : 'left'}
          ml={isUser ? 0 : 12}
          mr={isUser ? 12 : 0}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
          })}
        </Text>
      </Box>
    );
  };

  const getActionIcon = (actionType: string) => {
    switch (actionType) {
      case 'execute':
        return <PlayIcon />;
      case 'schedule':
        return <CalendarIcon />;
      case 'edit':
        return <EditIcon />;
      case 'confirm':
        return <CheckIcon />;
      case 'cancel':
        return <TrashIcon />;
      default:
        return <SettingsIcon />;
    }
  };

  return (
    <Box h="600px" display="flex" flexDirection="column" bg="white" borderRadius="lg" boxShadow="md">
      {/* Chat Header */}
      <Box p={4} borderBottom="1px" borderColor="gray.200">
        <HStack justify="space-between">
          <VStack align="start" spacing={0}>
            <Text fontWeight="bold" fontSize="lg">
              Workflow Assistant
            </Text>
            <Text fontSize="sm" color="gray.600">
              Create automated workflows with natural language
            </Text>
          </VStack>
          <Badge colorScheme="green" variant="subtle">
            AI Powered
          </Badge>
        </HStack>
      </Box>

      {/* Messages Area */}
      <Box flex={1} p={4} overflowY="auto" bg="gray.50">
        <VStack align="stretch" spacing={0}>
          {messages.map(renderMessage)}
          {isLoading && (
            <Box alignSelf="flex-start" maxW="80%">
              <HStack spacing={3} align="start">
                <Avatar
                  size="sm"
                  icon={<BotIcon />}
                  bg="blue.500"
                  color="white"
                />
                <Card bg="gray.100" borderRadius="lg">
                  <CardBody py={3} px={4}>
                    <HStack spacing={2}>
                      <Spinner size="sm" color="blue.500" />
                      <Text color="gray.600">Creating your workflow...</Text>
                    </HStack>
                  </CardBody>
                </Card>
              </HStack>
            </Box>
          )}
          <div ref={messagesEndRef} />
        </VStack>
      </Box>

      {/* Input Area */}
      <Box p={4} borderTop="1px" borderColor="gray.200">
        <HStack spacing={3}>
          <Input
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Describe the workflow you want to create..."
            size="lg"
            disabled={isLoading}
          />
          <IconButton
            aria-label="Send message"
            icon={<SendIcon />}
            colorScheme="blue"
            size="lg"
            onClick={handleSendMessage}
            isLoading={isLoading}
            isDisabled={!inputMessage.trim()}
          />
        </HStack>
        <Text fontSize="xs" color="gray.500" mt={2} textAlign="center">
          Examples: "When I get an email from boss, create a task in Asana" or "Schedule weekly report generation"
        </Text>
      </Box>

      {/* Schedule Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Schedule Workflow</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <Alert status="info">
                <AlertIcon />
                <Box>
                  <AlertTitle>Scheduling Feature</AlertTitle>
                  <AlertDescription>
                    Workflow scheduling is coming soon! For now, you can execute workflows manually.
                  </AlertDescription>
                </Box>
              </Alert>
              <Text>
                Would you like to execute this workflow now instead?
              </Text>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={() => {
                if (selectedWorkflow) {
                  executeWorkflow(selectedWorkflow.id);
                }
                onClose();
              }}
            >
              Execute Now
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default WorkflowChat;
