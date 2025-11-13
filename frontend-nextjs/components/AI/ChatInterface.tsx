import React, { useState, useRef, useEffect } from "react";
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Card,
  CardHeader,
  CardBody,
  Badge,
  Button,
  IconButton,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  FormControl,
  FormLabel,
  Input,
  Select,
  Textarea,
  Switch,
  Alert,
  AlertIcon,
  SimpleGrid,
  Flex,
  Spinner,
  useToast,
  Progress,
  Code,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Avatar,
  Divider,
} from "@chakra-ui/react";
import {
  SettingsIcon,
  ChevronDownIcon,
  CopyIcon,
  DeleteIcon,
} from "@chakra-ui/icons";
import { ArrowForwardIcon } from "@chakra-ui/icons";

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  model?: string;
  toolCalls?: ToolCall[];
}

interface ToolCall {
  id: string;
  name: string;
  arguments: any;
  result?: any;
}

interface Attachment {
  name: string;
  type: string;
  size: number;
  content: string | ArrayBuffer;
}

interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: Date;
  updatedAt: Date;
}

interface ChatInterfaceProps {
  initialSession?: ChatSession;
  onSessionUpdate?: (session: ChatSession) => void;
  availableModels?: string[];
  defaultModel?: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  initialSession,
  onSessionUpdate,
  availableModels = ["gpt-4", "gpt-3.5-turbo", "claude-2", "llama-2"],
  defaultModel = "gpt-4",
}) => {
  const [currentSession, setCurrentSession] = useState<ChatSession>(
    initialSession || {
      id: Date.now().toString(),
      title: "New Chat",
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    },
  );
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState(defaultModel);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(1000);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentSession.messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() && attachments.length === 0) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: inputMessage,
      timestamp: new Date(),
    };

    const updatedMessages = [...currentSession.messages, userMessage];
    const updatedSession = {
      ...currentSession,
      messages: updatedMessages,
      updatedAt: new Date(),
    };

    setCurrentSession(updatedSession);
    setInputMessage("");
    setIsLoading(true);

    // Simulate AI response
    setTimeout(() => {
      const aiMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `I received your message: "${inputMessage}". This is a simulated response from the ${selectedModel} model.`,
        timestamp: new Date(),
        model: selectedModel,
      };

      const finalMessages = [...updatedMessages, aiMessage];
      const finalSession = {
        ...updatedSession,
        messages: finalMessages,
        updatedAt: new Date(),
      };

      setCurrentSession(finalSession);
      setIsLoading(false);
      onSessionUpdate?.(finalSession);
    }, 2000);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          const attachment: Attachment = {
            name: file.name,
            type: file.type,
            size: file.size,
            content: event.target.result,
          };
          setAttachments((prev) => [...prev, attachment]);
        }
      };
      reader.readAsDataURL(file);
    });

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
    toast({
      title: "Message copied",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const exportChat = () => {
    const chatData = {
      session: currentSession,
      exportDate: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(chatData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chat-${currentSession.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const clearChat = () => {
    setCurrentSession({
      id: Date.now().toString(),
      title: "New Chat",
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    });
    setAttachments([]);
    toast({
      title: "Chat cleared",
      status: "info",
      duration: 2000,
      isClosable: true,
    });
  };

  return (
    <Box height="100vh" display="flex" flexDirection="column">
      {/* Header */}
      <Box p={4} borderBottom="1px" borderColor="gray.200">
        <HStack justifyContent="space-between" alignItems="center">
          <VStack align="start" spacing={1}>
            <Heading size="md">{currentSession.title}</Heading>
            <Text fontSize="sm" color="gray.600">
              {currentSession.messages.length} messages
            </Text>
          </VStack>
          <HStack spacing={2}>
            <Button
              leftIcon={<SettingsIcon />}
              variant="outline"
              size="sm"
              onClick={onOpen}
            >
              Settings
            </Button>
            <Button
              leftIcon={<ChevronDownIcon />}
              variant="outline"
              size="sm"
              onClick={exportChat}
            >
              Export
            </Button>
            <Button
              variant="outline"
              size="sm"
              colorScheme="red"
              onClick={clearChat}
            >
              Clear
            </Button>
          </HStack>
        </HStack>
      </Box>

      {/* Main Content */}
      <Flex flex="1" overflow="hidden">
        <VStack flex="1" spacing={0}>
          {/* Messages Area */}
          <Box flex="1" overflowY="auto" p={4} width="100%">
            <VStack spacing={4} align="stretch">
              {currentSession.messages.length === 0 && (
                <Card>
                  <CardBody textAlign="center" py={10}>
                    <VStack spacing={4}>
                      <Heading size="md" color="gray.500">
                        Start a conversation
                      </Heading>
                      <Text color="gray.600">
                        Type a message below to begin chatting with the AI
                        assistant.
                      </Text>
                    </VStack>
                  </CardBody>
                </Card>
              )}

              {currentSession.messages.map((message) => (
                <Card
                  key={message.id}
                  size="sm"
                  alignSelf={
                    message.role === "user" ? "flex-end" : "flex-start"
                  }
                  maxWidth="80%"
                >
                  <CardBody>
                    <Flex
                      justifyContent="space-between"
                      alignItems="flex-start"
                    >
                      <VStack align="start" spacing={2} flex="1">
                        <HStack spacing={2}>
                          <Avatar
                            size="xs"
                            name={message.role}
                            bg={
                              message.role === "user" ? "blue.500" : "green.500"
                            }
                          />
                          <Text
                            fontSize="xs"
                            fontWeight="bold"
                            color="gray.600"
                          >
                            {message.role}
                          </Text>
                          {message.model && (
                            <Badge size="sm" colorScheme="purple">
                              {message.model}
                            </Badge>
                          )}
                          <Text fontSize="xs" color="gray.500">
                            {message.timestamp.toLocaleTimeString()}
                          </Text>
                        </HStack>
                        <Text whiteSpace="pre-wrap">{message.content}</Text>
                        {message.toolCalls && message.toolCalls.length > 0 && (
                          <Accordion allowToggle width="100%">
                            <AccordionItem>
                              <AccordionButton>
                                <Box flex="1" textAlign="left">
                                  <Text fontSize="sm">
                                    Tool Calls ({message.toolCalls.length})
                                  </Text>
                                </Box>
                                <AccordionIcon />
                              </AccordionButton>
                              <AccordionPanel>
                                <VStack align="start" spacing={2}>
                                  {message.toolCalls.map((toolCall) => (
                                    <Code
                                      key={toolCall.id}
                                      fontSize="xs"
                                      p={2}
                                      width="100%"
                                    >
                                      {toolCall.name}(
                                      {JSON.stringify(toolCall.arguments)})
                                    </Code>
                                  ))}
                                </VStack>
                              </AccordionPanel>
                            </AccordionItem>
                          </Accordion>
                        )}
                      </VStack>
                      <IconButton
                        aria-label="Copy message"
                        icon={<CopyIcon />}
                        size="xs"
                        variant="ghost"
                        onClick={() => copyMessage(message.content)}
                      />
                    </Flex>
                  </CardBody>
                </Card>
              ))}

              {isLoading && (
                <Card size="sm" alignSelf="flex-start" maxWidth="80%">
                  <CardBody>
                    <HStack spacing={3}>
                      <Spinner size="sm" />
                      <Text fontSize="sm" color="gray.600">
                        AI is thinking...
                      </Text>
                    </HStack>
                  </CardBody>
                </Card>
              )}
              <div ref={messagesEndRef} />
            </VStack>
          </Box>

          {/* Input Area */}
          <Box p={4} borderTop="1px" borderColor="gray.200">
            <VStack spacing={3} align="stretch">
              {/* Attachments */}
              {attachments.length > 0 && (
                <HStack spacing={2} flexWrap="wrap">
                  {attachments.map((file, index) => (
                    <Badge
                      key={index}
                      colorScheme="blue"
                      px={2}
                      py={1}
                      borderRadius="md"
                    >
                      <HStack spacing={1}>
                        <Text fontSize="xs">{file.name}</Text>
                        <IconButton
                          aria-label="Remove attachment"
                          icon={<DeleteIcon />}
                          size="2xs"
                          variant="ghost"
                          onClick={() => removeAttachment(index)}
                        />
                      </HStack>
                    </Badge>
                  ))}
                </HStack>
              )}

              {/* Message Input */}
              <HStack spacing={2}>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Attach File
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  style={{ display: "none" }}
                  onChange={handleFileUpload}
                />
                <Textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message..."
                  rows={3}
                  flex="1"
                />
                <IconButton
                  aria-label="Send message"
                  icon={<ArrowForwardIcon />}
                  colorScheme="blue"
                  onClick={handleSendMessage}
                  isDisabled={!inputMessage.trim() || isLoading}
                  isLoading={isLoading}
                />
              </HStack>
            </VStack>
          </Box>
        </VStack>
      </Flex>

      {/* Settings Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Chat Settings</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>AI Model</FormLabel>
                <Select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                >
                  {availableModels.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Temperature: {temperature}</FormLabel>
                <Input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                />
                <Text fontSize="sm" color="gray.600">
                  Controls randomness (0 = deterministic, 1 = creative)
                </Text>
              </FormControl>

              <FormControl>
                <FormLabel>Max Tokens: {maxTokens}</FormLabel>
                <Input
                  type="range"
                  min="100"
                  max="4000"
                  step="100"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                />
                <Text fontSize="sm" color="gray.600">
                  Maximum response length
                </Text>
              </FormControl>

              <Alert status="info">
                <AlertIcon />
                These settings will apply to all future messages in this chat.
              </Alert>
            </VStack>
          </ModalBody>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default ChatInterface;
