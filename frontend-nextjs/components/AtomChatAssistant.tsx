import React, { useState, useRef, useEffect } from "react";
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
} from "@chakra-ui/react";
import {
  ArrowForwardIcon,
  ChatIcon,
  CalendarIcon,
  EmailIcon,
  TimeIcon,
  SettingsIcon,
  CheckCircleIcon,
  EditIcon,
  DeleteIcon,
  SearchIcon,
  ExternalLinkIcon,
} from "@chakra-ui/icons";
import { AddIcon } from "@chakra-ui/icons";

interface AtomChatMessage {
  id: string;
  type: "user" | "assistant" | "system";
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
  type: "execute" | "schedule" | "edit" | "confirm" | "cancel" |
  "create_event" | "send_email" | "view_inbox" | "view_calendar";
  label: string;
  workflowId?: string;
  data?: any;
}

interface AtomChatAssistantProps {
  userId?: string;
  onWorkflowCreated?: (workflowId: string) => void;
  onWorkflowExecuted?: (workflowId: string, executionId: string) => void;
}

const AtomChatAssistant: React.FC<AtomChatAssistantProps> = ({
  userId = "anonymous",
  onWorkflowCreated,
  onWorkflowExecuted,
}) => {
  const [messages, setMessages] = useState<AtomChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [selectedAction, setSelectedAction] = useState<ChatAction | null>(null);
  const toast = useToast();

  // Initialize session and load history
  useEffect(() => {
    const welcomeMessage: AtomChatMessage = {
      id: "welcome",
      type: "assistant",
      content:
        'Hi! I am your Universal ATOM Assistant. 🚀\n\nI can help you with:\n📅 **Calendar**: "Schedule meeting tomorrow"\n📧 **Email**: "Send email to boss"\n⚙️ **Workflows**: "Run Daily Report"\n\nWhat would you like to do?',
      timestamp: new Date(),
    };

    // Check for existing session in localStorage
    const storedSessionId = localStorage.getItem('atom_chat_session_id');

    if (storedSessionId) {
      // Resume existing session
      setSessionId(storedSessionId);
      loadSessionHistory(storedSessionId, welcomeMessage);
    } else {
      // Create new session
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      setSessionId(newSessionId);
      localStorage.setItem('atom_chat_session_id', newSessionId);
      setMessages([welcomeMessage]);
    }
  }, []);

  // Load session history from backend
  const loadSessionHistory = async (sessionId: string, welcomeMessage: ChatMessage) => {
    try {
      setIsLoading(true);
      const response = await fetch(`/api/atom-agent/sessions/${sessionId}/history`);
      const data = await response.json();

      if (data.success && data.messages && data.messages.length > 0) {
        // Convert backend messages to frontend format
        const chatMessages: ChatMessage[] = data.messages.map((msg: any) => ({
          id: msg.id || `msg_${Date.now()}_${Math.random()}`,
          type: msg.role === 'user' ? 'user' : 'assistant',
          content: msg.content || '',
          timestamp: new Date(msg.timestamp),
          workflowData: msg.metadata?.workflow_id ? {
            workflowId: msg.metadata.workflow_id,
            workflowName: msg.metadata.workflow_name,
            stepsCount: msg.metadata.steps_count,
            isScheduled: msg.metadata.is_scheduled,
          } : undefined,
          actions: msg.metadata?.actions || [],
        }));

        setMessages(chatMessages);
      } else {
        // No history or error, show welcome message
        setMessages([welcomeMessage]);
      }
    } catch (error) {
      console.error('Failed to load session history:', error);
      setMessages([welcomeMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: AtomChatMessage = {
      id: `user_${Date.now()}`,
      type: "user",
      content: inputMessage,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/atom-agent/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: inputMessage,
          user_id: userId,
          session_id: sessionId,
          conversation_history: messages.slice(-10).map((msg) => ({
            role: msg.type === "user" ? "user" : "assistant",
            content: msg.content,
          })),
        }),
      });

      const data = await response.json();

      if (data.success) {
        const assistantMessage: AtomChatMessage = {
          id: `assistant_${Date.now()}`,
          type: "assistant",
          content: data.response.message,
          timestamp: new Date(),
          workflowData: data.response.workflow_id
            ? {
              workflowId: data.response.workflow_id,
              workflowName: data.response.workflow_name,
              stepsCount: data.response.steps_count,
              isScheduled: data.response.is_scheduled,
              requiresConfirmation: data.response.requires_confirmation,
            }
            : undefined,
          actions: data.response.actions || [],
        };

        setMessages((prev) => [...prev, assistantMessage]);

        // Call callback if workflow was created
        if (data.response.workflow_id && onWorkflowCreated) {
          onWorkflowCreated(data.response.workflow_id);
        }
      } else {
        throw new Error(data.error || "Failed to process message");
      }
    } catch (error) {
      console.error("Error sending message:", error);
      toast({
        title: "Error",
        description: "Failed to process your message. Please try again.",
        status: "error",
        duration: 3000,
        isClosable: true,
      });

      const errorMessage: AtomChatMessage = {
        id: `error_${Date.now()}`,
        type: "assistant",
        content:
          "Sorry, I encountered an error while processing your request. Please try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActionClick = async (action: ChatAction) => {
    switch (action.type) {
      case "execute":
        await executeWorkflow(action.workflowId!);
        break;
      case "schedule":
        // Open schedule modal
        setSelectedAction(action);
        onOpen();
        break;
      case "create_event":
        // Mock event creation confirmation
        toast({
          title: "Event Created",
          description: `Created event: ${action.data?.summary}`,
          status: "success",
          duration: 3000,
          isClosable: true,
        });
        break;
      case "send_email":
        // Mock email sending
        toast({
          title: "Email Sent",
          description: `Sent email to ${action.data?.recipient}`,
          status: "success",
          duration: 3000,
          isClosable: true,
        });
        break;
      case "view_inbox":
      case "view_calendar":
        toast({
          title: "Opening View",
          description: `Navigating to ${action.label}...`,
          status: "info",
          duration: 2000,
          isClosable: true,
        });
        break;
      default:
        toast({
          title: "Action",
          description: `Action ${action.label} clicked`,
          status: "info",
          duration: 2000,
          isClosable: true,
        });
    }
  };

  const executeWorkflow = async (workflowId: string) => {
    try {
      const response = await fetch("/api/atom-agent/execute-generated", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          workflow_id: workflowId,
          input_data: {},
        }),
      });

      const data = await response.json();

      if (data.success) {
        toast({
          title: "Workflow Started",
          description: `Execution ${data.execution_id} has started`,
          status: "success",
          duration: 3000,
          isClosable: true,
        });

        if (onWorkflowExecuted) {
          onWorkflowExecuted(workflowId, data.execution_id);
        }

        // Add execution confirmation message
        const executionMessage: AtomChatMessage = {
          id: `execution_${Date.now()}`,
          type: "assistant",
          content: `Workflow execution started! You can monitor the progress in the Workflow Automation tab.`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, executionMessage]);
      } else {
        throw new Error(data.error || "Failed to execute workflow");
      }
    } catch (error) {
      console.error("Error executing workflow:", error);
      toast({
        title: "Execution Failed",
        description: "Failed to start workflow execution",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleNewChat = () => {
    const welcomeMessage: AtomChatMessage = {
      id: "welcome",
      type: "assistant",
      content:
        'Hi! I am your Universal ATOM Assistant. 🚀\n\nI can help you with:\n📅 **Calendar**: "Schedule meeting tomorrow"\n📧 **Email**: "Send email to boss"\n⚙️ **Workflows**: "Run Daily Report"\n\nWhat would you like to do?',
      timestamp: new Date(),
    };

    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newSessionId);
    localStorage.setItem('atom_chat_session_id', newSessionId);
    setMessages([welcomeMessage]);

    toast({
      title: "New Chat Started",
      description: "Previous conversation has been saved",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const renderMessage = (message: AtomChatMessage) => {
    const isUser = message.type === "user";

    return (
      <Box
        key={message.id}
        alignSelf={isUser ? "flex-end" : "flex-start"}
        maxW="80%"
        mb={4}
      >
        <HStack spacing={3} align="start">
          {!isUser && (
            <Avatar size="sm" icon={<ChatIcon />} bg="purple.500" color="white" />
          )}
          <Card
            bg={isUser ? "blue.500" : "gray.100"}
            color={isUser ? "white" : "gray.800"}
            borderRadius="lg"
            boxShadow="sm"
          >
            <CardBody py={3} px={4}>
              <Text whiteSpace="pre-wrap">{message.content}</Text>

              {message.workflowData && (
                <Box
                  mt={3}
                  p={3}
                  bg={isUser ? "blue.600" : "white"}
                  borderRadius="md"
                >
                  <VStack align="start" spacing={2}>
                    <HStack>
                      <Badge colorScheme="green">
                        {message.workflowData.stepsCount} steps
                      </Badge>
                      {message.workflowData.isScheduled && (
                        <Badge colorScheme="purple">
                          <TimeIcon mr={1} /> Scheduled
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
                  {message.actions.map((action: ChatAction, index: number) => (
                    <Button
                      key={index}
                      size="sm"
                      variant={action.type === "execute" ? "solid" : "outline"}
                      colorScheme={getActionColor(action.type)}
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
              name="User"
              bg="gray.500"
              color="white"
            />
          )}
        </HStack>
        <Text
          fontSize="xs"
          color="gray.500"
          mt={1}
          textAlign={isUser ? "right" : "left"}
          ml={isUser ? 0 : 12}
          mr={isUser ? 12 : 0}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </Text>
      </Box>
    );
  };

  const getActionIcon = (actionType: string) => {
    switch (actionType) {
      case "execute":
        return <ArrowForwardIcon />;
      case "schedule":
        return <TimeIcon />;
      case "create_event":
      case "view_calendar":
        return <CalendarIcon />;
      case "send_email":
      case "view_inbox":
        return <EmailIcon />;
      case "edit":
        return <EditIcon />;
      case "confirm":
        return <CheckCircleIcon />;
      case "cancel":
        return <DeleteIcon />;
      default:
        return <SettingsIcon />;
    }
  };

  const getActionColor = (actionType: string) => {
    switch (actionType) {
      case "execute":
        return "green";
      case "create_event":
      case "view_calendar":
        return "purple";
      case "send_email":
      case "view_inbox":
        return "orange";
      case "cancel":
        return "red";
      default:
        return "blue";
    }
  };

  return (
    <Box
      h="600px"
      display="flex"
      flexDirection="column"
      bg="white"
      borderRadius="lg"
      boxShadow="md"
    >
      {/* Chat Header */}
      <Box p={4} borderBottom="1px" borderColor="gray.200">
        <HStack justify="space-between">
          <VStack align="start" spacing={0}>
            <Text fontWeight="bold" fontSize="lg">
              ATOM Assistant
            </Text>
            <Text fontSize="sm" color="gray.600">
              Universal AI Assistant for Workflows, Calendar & Email
            </Text>
          </VStack>
          <HStack>
            <Badge colorScheme="purple" variant="subtle">
              Universal Agent
            </Badge>
            <Button
              size="sm"
              leftIcon={<AddIcon />}
              onClick={handleNewChat}
              variant="outline"
              colorScheme="purple"
            >
              New Chat
            </Button>
          </HStack>
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
                  icon={<ChatIcon />}
                  bg="purple.500"
                  color="white"
                />
                <Card bg="gray.100" borderRadius="lg">
                  <CardBody py={3} px={4}>
                    <HStack spacing={2}>
                      <Spinner size="sm" color="purple.500" />
                      <Text color="gray.600">Processing...</Text>
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
            placeholder="Ask ATOM to schedule meetings, send emails, or run workflows..."
            size="lg"
            disabled={isLoading}
          />
          <IconButton
            aria-label="Send message"
            icon={<ArrowForwardIcon />}
            colorScheme="purple"
            size="lg"
            onClick={handleSendMessage}
            isLoading={isLoading}
            isDisabled={!inputMessage.trim()}
          />
        </HStack>
        <Text fontSize="xs" color="gray.500" mt={2} textAlign="center">
          Try: "Schedule standup tomorrow at 10am" or "Send email to team"
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
                    Workflow scheduling is available in the Workflow Editor.
                  </AlertDescription>
                </Box>
              </Alert>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default AtomChatAssistant;
