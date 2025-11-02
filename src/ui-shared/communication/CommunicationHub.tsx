import React, { useState, useEffect } from "react";
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Grid,
  GridItem,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Button,
  IconButton,
  Badge,
  Spinner,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  Select,
  Checkbox,
  Switch,
  useDisclosure,
  SimpleGrid,
  Flex,
  Divider,
  Alert,
  AlertIcon,
  Avatar,
  AvatarGroup,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  InputGroup,
  InputLeftElement,
  InputRightElement,
} from "@chakra-ui/react";
import {
  AddIcon,
  CalendarIcon,
  EditIcon,
  DeleteIcon,
  CheckIcon,
  TimeIcon,
  ViewIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  AttachmentIcon,
  ChatIcon,
  StarIcon,
  SearchIcon,
  EmailIcon,
  PhoneIcon,
  ExternalLinkIcon,
  RepeatIcon,
  CopyIcon,
  DownloadIcon,
} from "@chakra-ui/icons";

export interface Message {
  id: string;
  platform: "email" | "slack" | "teams" | "discord" | "whatsapp" | "sms";
  from: string;
  to?: string;
  subject: string;
  preview: string;
  content: string;
  timestamp: Date;
  unread: boolean;
  priority: "high" | "normal" | "low";
  attachments?: string[];
  threadId?: string;
  isReply?: boolean;
  status: "sent" | "received" | "draft" | "failed";
  color?: string;
}

export interface Conversation {
  id: string;
  title: string;
  participants: string[];
  messages: Message[];
  unreadCount: number;
  lastMessage: Date;
  platform: string;
  tags?: string[];
  priority: "high" | "normal" | "low";
}

export interface QuickReplyTemplate {
  id: string;
  name: string;
  content: string;
  category: string;
  platform: string[];
}

export interface CommunicationView {
  type: "inbox" | "thread" | "compose";
  filter: {
    platform?: string[];
    priority?: string[];
    unread?: boolean;
    search?: string;
  };
  sort: {
    field: "timestamp" | "priority" | "from";
    direction: "asc" | "desc";
  };
}

export interface CommunicationHubProps {
  onMessageSend?: (
    message: Omit<Message, "id" | "timestamp" | "status">,
  ) => void;
  onMessageUpdate?: (messageId: string, updates: Partial<Message>) => void;
  onMessageDelete?: (messageId: string) => void;
  onConversationCreate?: (conversation: Conversation) => void;
  initialMessages?: Message[];
  initialConversations?: Conversation[];
  initialTemplates?: QuickReplyTemplate[];
  showNavigation?: boolean;
  compactView?: boolean;
}

const CommunicationHub: React.FC<CommunicationHubProps> = ({
  onMessageSend,
  onMessageUpdate,
  onMessageDelete,
  onConversationCreate,
  initialMessages = [],
  initialConversations = [],
  initialTemplates = [],
  showNavigation = true,
  compactView = false,
}) => {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [conversations, setConversations] =
    useState<Conversation[]>(initialConversations);
  const [templates, setTemplates] =
    useState<QuickReplyTemplate[]>(initialTemplates);
  const [view, setView] = useState<CommunicationView>({
    type: "inbox",
    filter: {},
    sort: { field: "timestamp", direction: "desc" },
  });
  const [selectedConversation, setSelectedConversation] =
    useState<Conversation | null>(null);
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const {
    isOpen: isComposeOpen,
    onOpen: onComposeOpen,
    onClose: onComposeClose,
  } = useDisclosure();
  const {
    isOpen: isMessageOpen,
    onOpen: onMessageOpen,
    onClose: onMessageClose,
  } = useDisclosure();
  const toast = useToast();

  // Real data hooks for communication platforms
  const useRealCommunicationData = (platforms: string[], userId?: string) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    
    useEffect(() => {
      const fetchRealMessages = async () => {
        if (!userId || platforms.length === 0) {
          setMessages([]);
          return;
        }
        
        setLoading(true);
        setError(null);
        
        try {
          const response = await fetch('/api/communication/messages', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              user_id: userId,
              platforms: platforms,
              limit: 100
            })
          });
          
          const data = await response.json();
          
          if (data.ok) {
            // Transform messages to Message interface
            const transformedMessages: Message[] = data.messages.map((msg: any) => ({
              id: msg.id,
              platform: msg.platform as any,
              from: msg.from,
              to: msg.to,
              subject: msg.subject,
              preview: msg.preview,
              content: msg.content,
              timestamp: new Date(msg.timestamp),
              unread: msg.unread,
              priority: msg.priority as any,
              attachments: msg.attachments,
              threadId: msg.thread_id,
              isReply: false,
              status: msg.status as any,
              color: getPlatformColor(msg.platform)
            }));
            
            setMessages(transformedMessages);
          } else {
            setError(data.error || 'Failed to fetch messages');
          }
        } catch (err) {
          setError('Network error fetching messages');
          console.error('Error fetching real messages:', err);
        } finally {
          setLoading(false);
        }
      };
      
      fetchRealMessages();
    }, [platforms, userId]);
    
    return { messages, loading, error, refetch: () => fetchRealMessages() };
  };

  const [currentUserId] = useState<string>("demo-user"); // Replace with actual user ID from auth
  const realData = useRealCommunicationData(['slack', 'teams'], currentUserId);

    const mockConversations: Conversation[] = [
      {
        id: "conv-1",
        title: "Weekly Team Updates",
        participants: ["team@company.com", "user@example.com"],
        messages: realData.messages.filter((msg) => msg.platform === "email"),
        unreadCount: realData.messages.filter((msg) => msg.platform === "email" && msg.unread).length,
        lastMessage: realData.messages.length > 0 ? realData.messages[0].timestamp : new Date(),
        platform: "email",
        tags: ["work", "updates"],
        priority: "normal",
      },
      {
        id: "conv-2",
        title: "Design Review Discussion",
        participants: ["john.doe", "user@example.com", "sarah.wilson"],
        messages: realData.messages.filter((msg) => msg.platform === "slack"),
        unreadCount: realData.messages.filter((msg) => msg.platform === "slack" && msg.unread).length,
        lastMessage: realData.messages.length > 0 ? realData.messages[0].timestamp : new Date(),
        platform: "slack",
        tags: ["design", "review"],
        priority: "high",
      },
    ];

    const mockTemplates: QuickReplyTemplate[] = [
      {
        id: "temp-1",
        name: "Meeting Confirmation",
        content:
          "Thank you for scheduling the meeting. I have added it to my calendar.",
        category: "meetings",
        platform: ["email", "slack"],
      },
      {
        id: "temp-2",
        name: "Quick Follow-up",
        content:
          "Just following up on our previous conversation. Let me know if you need anything else.",
        category: "follow-up",
        platform: ["email", "slack", "teams"],
      },
      {
        id: "temp-3",
        name: "Availability Check",
        content: "What time works best for you this week?",
        category: "scheduling",
        platform: ["email", "slack"],
      },
    ];

    setMessages(realData.messages);
    setConversations(mockConversations);
    setTemplates(mockTemplates);
    setLoading(false);
  }, [realData.messages]);

  const handleSendMessage = async (
    messageData: Omit<Message, "id" | "timestamp" | "status">,
  ) => {
    try {
      // Send real message if platform is supported
      if (['slack', 'teams'].includes(messageData.platform)) {
        const response = await fetch('/api/communication/send', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            platform: messageData.platform,
            user_id: currentUserId,
            channel_id: messageData.threadId || 'default', // Need channel for sending
            content: messageData.content,
            team_id: messageData.to // Can be used as team_id for Teams
          })
        });
        
        const result = await response.json();
        
        if (result.ok) {
          // Create local message to show in UI
          const newMessage: Message = {
            ...messageData,
            id: result.message_id || Date.now().toString(),
            timestamp: new Date(),
            status: "sent",
          };
          setMessages((prev) => [newMessage, ...prev]);
          
          onMessageSend?.(messageData);
          toast({
            title: "Message sent",
            description: `Message sent via ${messageData.platform}`,
            status: "success",
            duration: 2000,
            isClosable: true,
          });
        } else {
          throw new Error(result.error || 'Failed to send message');
        }
      } else {
        // Fallback for email or other platforms
        const newMessage: Message = {
          ...messageData,
          id: Date.now().toString(),
          timestamp: new Date(),
          status: "sent",
        };
        setMessages((prev) => [...prev, newMessage]);
        onMessageSend?.(messageData);
        toast({
          title: "Message created",
          description: `${messageData.platform} message created (local only)`,
          status: "info",
          duration: 2000,
          isClosable: true,
        });
      }
    } catch (error) {
      console.error('Error sending message:', error);
      toast({
        title: "Failed to send message",
        description: error instanceof Error ? error.message : 'Unknown error',
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleUpdateMessage = (
    messageId: string,
    updates: Partial<Message>,
  ) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId ? { ...message, ...updates } : message,
      ),
    );
    onMessageUpdate?.(messageId, updates);
    toast({
      title: "Message updated",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDeleteMessage = (messageId: string) => {
    setMessages((prev) => prev.filter((message) => message.id !== messageId));
    onMessageDelete?.(messageId);
    toast({
      title: "Message deleted",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleMarkAsRead = (messageId: string) => {
    handleUpdateMessage(messageId, { unread: false });
  };

  const handleMarkAllAsRead = () => {
    setMessages((prev) => prev.map((msg) => ({ ...msg, unread: false })));
    toast({
      title: "All messages marked as read",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const getPlatformColor = (platform: string) => {
    switch (platform) {
      case "email":
        return "#3182CE";
      case "slack":
        return "#4A154B";
      case "teams":
        return "#6264A7";
      case "discord":
        return "#5865F2";
      case "whatsapp":
        return "#25D366";
      case "sms":
        return "#34B7F1";
      default:
        return "#718096";
    }
  };

  const getPlatformIcon = (platform: string) => {
    switch (platform) {
      case "email":
        return <EmailIcon />;
      case "slack":
        return <ChatIcon />;
      case "teams":
        return <ChatIcon />;
      case "discord":
        return <ChatIcon />;
      case "whatsapp":
        return <PhoneIcon />;
      case "sms":
        return <PhoneIcon />;
      default:
        return <ChatIcon />;
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  };

  const getFilteredMessages = () => {
    let filtered = [...messages];

    // Apply search filter
    if (searchQuery) {
      filtered = filtered.filter(
        (message) =>
          message.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
          message.preview.toLowerCase().includes(searchQuery.toLowerCase()) ||
          message.from.toLowerCase().includes(searchQuery.toLowerCase()),
      );
    }

    // Apply platform filters
    if (view.filter.platform?.length) {
      filtered = filtered.filter((message) =>
        view.filter.platform?.includes(message.platform),
      );
    }

    // Apply priority filters
    if (view.filter.priority?.length) {
      filtered = filtered.filter((message) =>
        view.filter.priority?.includes(message.priority),
      );
    }

    // Apply unread filter
    if (view.filter.unread) {
      filtered = filtered.filter((message) => message.unread);
    }

    // Apply sorting
    filtered.sort((a, b) => {
      const direction = view.sort.direction === "asc" ? 1 : -1;
      switch (view.sort.field) {
        case "timestamp":
          return (a.timestamp.getTime() - b.timestamp.getTime()) * direction;
        case "priority":
          const priorityOrder = { high: 3, normal: 2, low: 1 };
          return (
            (priorityOrder[a.priority] - priorityOrder[b.priority]) * direction
          );
        case "from":
          return a.from.localeCompare(b.from) * direction;
        default:
          return 0;
      }
    });

    return filtered;
  };

  const MessageComposer: React.FC<{
    onSubmit: (data: Omit<Message, "id" | "timestamp" | "status">) => void;
    onCancel: () => void;
    replyTo?: Message;
  }> = ({ onSubmit, onCancel, replyTo }) => {
    const [formData, setFormData] = useState({
      platform: replyTo?.platform || "email",
      to: replyTo?.from || "",
      subject: replyTo ? `Re: ${replyTo.subject}` : "",
      content: replyTo
        ? `\n\nOn ${replyTo.timestamp.toLocaleString()}, ${replyTo.from} wrote:\n> ${replyTo.content.split("\n").join("\n> ")}`
        : "",
      priority: "normal" as "high" | "normal" | "low",
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit({
        platform: formData.platform as any,
        from: "user@example.com", // Current user
        to: formData.to,
        subject: formData.subject,
        preview:
          formData.content.slice(0, 100) +
          (formData.content.length > 100 ? "..." : ""),
        content: formData.content,
        unread: false,
        priority: formData.priority,
        isReply: !!replyTo,
        threadId: replyTo?.threadId || Date.now().toString(),
      });
      onCancel();
    };

    const applyTemplate = (template: QuickReplyTemplate) => {
      setFormData((prev) => ({
        ...prev,
        content: template.content + (prev.content ? `\n\n${prev.content}` : ""),
      }));
    };

    return (
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <SimpleGrid columns={2} spacing={4} width="100%">
            <FormControl>
              <FormLabel>Platform</FormLabel>
              <Select
                value={formData.platform}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, platform: e.target.value }))
                }
              >
                <option value="email">Email</option>
                <option value="slack">Slack</option>
                <option value="teams">Microsoft Teams</option>
                <option value="discord">Discord</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="sms">SMS</option>
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Priority</FormLabel>
              <Select
                value={formData.priority}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    priority: e.target.value as any,
                  }))
                }
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
              </Select>
            </FormControl>
          </SimpleGrid>

          <FormControl isRequired>
            <FormLabel>To</FormLabel>
            <Input
              value={formData.to}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, to: e.target.value }))
              }
              placeholder="Recipient email or username"
            />
          </FormControl>

          <FormControl isRequired>
            <FormLabel>Subject</FormLabel>
            <Input
              value={formData.subject}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, subject: e.target.value }))
              }
              placeholder="Message subject"
            />
          </FormControl>

          <FormControl isRequired>
            <FormLabel>Message</FormLabel>
            <Textarea
              value={formData.content}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, content: e.target.value }))
              }
              placeholder="Type your message here..."
              minHeight="200px"
            />
          </FormControl>

          {/* Quick Reply Templates */}
          {templates.length > 0 && (
            <FormControl>
              <FormLabel>Quick Reply Templates</FormLabel>
              <SimpleGrid columns={2} spacing={2}>
                {templates
                  .filter((template) =>
                    template.platform.includes(formData.platform),
                  )
                  .slice(0, 4)
                  .map((template) => (
                    <Button
                      key={template.id}
                      size="sm"
                      variant="outline"
                      onClick={() => applyTemplate(template)}
                      leftIcon={<CopyIcon />}
                    >
                      {template.name}
                    </Button>
                  ))}
              </SimpleGrid>
            </FormControl>
          )}

          <HStack width="100%" justifyContent="flex-end" spacing={3}>
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" colorScheme="blue">
              Send Message
            </Button>
          </HStack>
        </VStack>
      </form>
    );
  };

  const MessageViewer: React.FC<{
    message: Message;
    onClose: () => void;
  }> = ({ message, onClose }) => {
    return (
      <Modal isOpen={true} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={2}>
              <Badge colorScheme={getPlatformColor(message.platform)}>
                {message.platform.toUpperCase()}
              </Badge>
              <Text>{message.subject}</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Text fontWeight="bold">{message.from}</Text>
                <Text fontSize="sm" color="gray.500">
                  {formatDate(message.timestamp)} at{" "}
                  {formatTime(message.timestamp)}
                </Text>
              </HStack>
              <Badge
                colorScheme={getPlatformColor(message.platform)}
                alignSelf="flex-start"
              >
                {message.platform.toUpperCase()}
              </Badge>
              <Box
                p={4}
                borderWidth="1px"
                borderRadius="md"
                bg="gray.50"
                whiteSpace="pre-wrap"
              >
                {message.content}
              </Box>
              {message.attachments && message.attachments.length > 0 && (
                <VStack align="stretch">
                  <Text fontWeight="bold">Attachments:</Text>
                  {message.attachments.map((attachment, index) => (
                    <HStack key={index}>
                      <AttachmentIcon />
                      <Text>{attachment}</Text>
                      <IconButton
                        aria-label="Download attachment"
                        icon={<DownloadIcon />}
                        size="sm"
                        variant="ghost"
                      />
                    </HStack>
                  ))}
                </VStack>
              )}
            </VStack>
          </ModalBody>
          <ModalFooter>
            <HStack spacing={2}>
              <Button
                leftIcon={<RepeatIcon />}
                onClick={() => {
                  setSelectedMessage(message);
                  onComposeOpen();
                  onMessageClose();
                }}
              >
                Reply
              </Button>
              <Button
                variant="outline"
                onClick={() => handleMarkAsRead(message.id)}
              >
                Mark as Read
              </Button>
              <Button
                variant="outline"
                colorScheme="red"
                onClick={() => {
                  handleDeleteMessage(message.id);
                  onMessageClose();
                }}
              >
                Delete
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>
    );
  };

  if (loading) {
    return (
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Loading messages...</Text>
      </Box>
    );
  }

  const filteredMessages = getFilteredMessages();

  return (
    <Box p={compactView ? 2 : 6}>
      <VStack spacing={compactView ? 3 : 6} align="stretch">
        {/* Header */}
        {showNavigation && (
          <Flex justify="space-between" align="center">
            <Heading size={compactView ? "md" : "lg"}>
              Communication Hub
            </Heading>
            <Button
              leftIcon={<AddIcon />}
              colorScheme="blue"
              size={compactView ? "sm" : "md"}
              onClick={onComposeOpen}
            >
              New Message
            </Button>
          </Flex>
        )}

        {/* Search and Filters */}
        {showNavigation && (
          <Card size={compactView ? "sm" : "md"}>
            <CardBody>
              <VStack spacing={4}>
                <InputGroup>
                  <InputLeftElement>
                    <SearchIcon color="gray.300" />
                  </InputLeftElement>
                  <Input
                    placeholder="Search messages..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  {searchQuery && (
                    <InputRightElement>
                      <IconButton
                        aria-label="Clear search"
                        icon={<DeleteIcon />}
                        size="sm"
                        variant="ghost"
                        onClick={() => setSearchQuery("")}
                      />
                    </InputRightElement>
                  )}
                </InputGroup>
                <HStack spacing={4} wrap="wrap">
                  <Button
                    size="sm"
                    variant={view.filter.unread ? "solid" : "outline"}
                    onClick={() =>
                      setView((prev) => ({
                        ...prev,
                        filter: { ...prev.filter, unread: !prev.filter.unread },
                      }))
                    }
                  >
                    Unread Only
                  </Button>
                  <Menu>
                    <MenuButton as={Button} size="sm" variant="outline">
                      Platform: {view.filter.platform?.length || "All"}
                    </MenuButton>
                    <MenuList>
                      {[
                        "email",
                        "slack",
                        "teams",
                        "discord",
                        "whatsapp",
                        "sms",
                      ].map((platform) => (
                        <MenuItem key={platform}>
                          <Checkbox
                            isChecked={view.filter.platform?.includes(platform)}
                            onChange={(e) => {
                              const newPlatforms = e.target.checked
                                ? [...(view.filter.platform || []), platform]
                                : (view.filter.platform || []).filter(
                                    (p) => p !== platform,
                                  );
                              setView((prev) => ({
                                ...prev,
                                filter: {
                                  ...prev.filter,
                                  platform: newPlatforms,
                                },
                              }));
                            }}
                          >
                            {platform.charAt(0).toUpperCase() +
                              platform.slice(1)}
                          </Checkbox>
                        </MenuItem>
                      ))}
                    </MenuList>
                  </Menu>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleMarkAllAsRead}
                  >
                    Mark All Read
                  </Button>
                </HStack>
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Messages List */}
        <Card size={compactView ? "sm" : "md"}>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>
              Messages ({filteredMessages.length})
            </Heading>
          </CardHeader>
          <CardBody>
            <VStack spacing={2} align="stretch">
              {filteredMessages.map((message) => (
                <Flex
                  key={message.id}
                  p={3}
                  borderWidth="1px"
                  borderRadius="md"
                  bg={message.unread ? "blue.50" : "white"}
                  cursor="pointer"
                  onClick={() => {
                    setSelectedMessage(message);
                    onMessageOpen();
                    if (message.unread) {
                      handleMarkAsRead(message.id);
                    }
                  }}
                >
                  <HStack spacing={3} flex={1}>
                    <Box color={getPlatformColor(message.platform)}>
                      {getPlatformIcon(message.platform)}
                    </Box>
                    <Box flex={1}>
                      <HStack justify="space-between" mb={1}>
                        <Text
                          fontWeight="bold"
                          fontSize={compactView ? "sm" : "md"}
                        >
                          {message.from}
                        </Text>
                        <HStack spacing={2}>
                          {message.unread && (
                            <Badge colorScheme="blue" size="sm">
                              New
                            </Badge>
                          )}
                          <Badge
                            colorScheme={
                              message.priority === "high"
                                ? "red"
                                : message.priority === "normal"
                                  ? "blue"
                                  : "gray"
                            }
                            size="sm"
                          >
                            {message.priority}
                          </Badge>
                          <Text fontSize="xs" color="gray.500">
                            {formatTime(message.timestamp)}
                          </Text>
                        </HStack>
                      </HStack>
                      <Text
                        fontWeight="bold"
                        fontSize={compactView ? "xs" : "sm"}
                        mb={1}
                      >
                        {message.subject}
                      </Text>
                      <Text
                        fontSize={compactView ? "xs" : "sm"}
                        color="gray.600"
                        noOfLines={2}
                      >
                        {message.preview}
                      </Text>
                    </Box>
                  </HStack>
                </Flex>
              ))}
              {filteredMessages.length === 0 && (
                <Box textAlign="center" py={8}>
                  <Text color="gray.500">No messages found</Text>
                  <Button
                    mt={2}
                    colorScheme="blue"
                    variant="outline"
                    onClick={onComposeOpen}
                  >
                    Compose New Message
                  </Button>
                </Box>
              )}
            </VStack>
          </CardBody>
        </Card>

        {/* Recent Conversations */}
        {conversations.length > 0 && (
          <Card size={compactView ? "sm" : "md"}>
            <CardHeader>
              <Heading size={compactView ? "sm" : "md"}>
                Recent Conversations
              </Heading>
            </CardHeader>
            <CardBody>
              <VStack spacing={2} align="stretch">
                {conversations
                  .sort(
                    (a, b) => b.lastMessage.getTime() - a.lastMessage.getTime(),
                  )
                  .slice(0, compactView ? 3 : 5)
                  .map((conversation) => (
                    <Flex
                      key={conversation.id}
                      p={2}
                      borderWidth="1px"
                      borderRadius="md"
                      cursor="pointer"
                      onClick={() => setSelectedConversation(conversation)}
                    >
                      <HStack spacing={3} flex={1}>
                        <Avatar
                          size="sm"
                          name={conversation.title}
                          bg={getPlatformColor(conversation.platform)}
                        />
                        <Box flex={1}>
                          <HStack justify="space-between" mb={1}>
                            <Text
                              fontWeight="bold"
                              fontSize={compactView ? "sm" : "md"}
                            >
                              {conversation.title}
                            </Text>
                            {conversation.unreadCount > 0 && (
                              <Badge colorScheme="blue">
                                {conversation.unreadCount}
                              </Badge>
                            )}
                          </HStack>
                          <Text
                            fontSize={compactView ? "xs" : "sm"}
                            color="gray.600"
                          >
                            {conversation.participants.join(", ")}
                          </Text>
                          <Text fontSize="xs" color="gray.500">
                            Last: {formatDate(conversation.lastMessage)}
                          </Text>
                        </Box>
                      </HStack>
                    </Flex>
                  ))}
              </VStack>
            </CardBody>
          </Card>
        )}
      </VStack>

      {/* Compose Modal */}
      <Modal
        isOpen={isComposeOpen}
        onClose={onComposeClose}
        size={compactView ? "md" : "lg"}
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {selectedMessage
              ? `Reply to ${selectedMessage.from}`
              : "Compose New Message"}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <MessageComposer
              onSubmit={(data) => {
                handleSendMessage(data);
                onComposeClose();
              }}
              onCancel={onComposeClose}
              replyTo={selectedMessage || undefined}
            />
          </ModalBody>
        </ModalContent>
      </Modal>

      {/* Message Viewer Modal */}
      {selectedMessage && (
        <MessageViewer
          message={selectedMessage}
          onClose={() => {
            setSelectedMessage(null);
            onMessageClose();
          }}
        />
      )}
    </Box>
  );
};

export default CommunicationHub;
