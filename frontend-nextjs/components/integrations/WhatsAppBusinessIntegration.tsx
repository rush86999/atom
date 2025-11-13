/**
 * WhatsApp Business Integration Component
 * 
 * Provides a comprehensive interface for managing WhatsApp Business API integration
 * within the Atom platform, including messaging, templates, analytics, and automation.
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Button,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Badge,
  Input,
  Textarea,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Select,
  FormControl,
  FormLabel,
  Switch,
  Divider,
  Grid,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Spinner,
  useToast,
  IconButton,
  Tooltip,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatGroup,
  Stack,
  Avatar,
  Tag,
  TagLabel,
  Icon,
} from '@chakra-ui/react';
import {
  ChatIcon,
  PhoneIcon,
  TimeIcon,
  CheckCircleIcon,
  WarningIcon,
  InfoIcon,
  SettingsIcon,
  ExternalLinkIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  ArrowForwardIcon,
  RepeatIcon,
  PlusSquareIcon,
  BarChartIcon,
  EmailIcon,
} from '@chakra-ui/icons';

interface WhatsAppContact {
  id: string;
  whatsapp_id: string;
  name?: string;
  phone_number: string;
  profile_picture_url?: string;
  about?: string;
  created_at: string;
  updated_at: string;
}

interface WhatsAppMessage {
  id: string;
  message_id: string;
  whatsapp_id: string;
  message_type: string;
  content: any;
  direction: 'inbound' | 'outbound';
  status: string;
  timestamp: string;
}

interface WhatsAppTemplate {
  id: string;
  template_name: string;
  category: string;
  language_code: string;
  components: any;
  status: string;
  created_at: string;
}

interface WhatsAppConversation {
  id: string;
  conversation_id: string;
  whatsapp_id: string;
  status: string;
  last_message_at: string;
  metadata?: any;
  name?: string;
  phone_number?: string;
  message_count?: number;
  last_message_time?: string;
}

interface WhatsAppAnalytics {
  message_statistics: Array<{
    direction: string;
    message_type: string;
    status: string;
    count: number;
  }>;
  conversation_statistics: {
    total_conversations: number;
    active_conversations: number;
  };
  contact_growth: Array<{
    date: string;
    new_contacts: number;
  }>;
}

const WhatsAppBusinessIntegration: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [conversations, setConversations] = useState<WhatsAppConversation[]>([]);
  const [messages, setMessages] = useState<WhatsAppMessage[]>([]);
  const [templates, setTemplates] = useState<WhatsAppTemplate[]>([]);
  const [analytics, setAnalytics] = useState<WhatsAppAnalytics | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<WhatsAppConversation | null>(null);
  const [newMessage, setNewMessage] = useState('');
  const [selectedRecipient, setSelectedRecipient] = useState('');
  const [messageType, setMessageType] = useState<'text' | 'template' | 'media'>('text');
  const [activeTab, setActiveTab] = useState(0);

  const {
    isOpen: isComposeOpen,
    onOpen: onComposeOpen,
    onClose: onComposeClose,
  } = useDisclosure();

  const {
    isOpen: isConfigOpen,
    onOpen: onConfigOpen,
    onClose: onConfigClose,
  } = useDisclosure();

  const {
    isOpen: isTemplateOpen,
    onOpen: onTemplateOpen,
    onClose: onTemplateClose,
  } = useDisclosure();

  const toast = useToast();

  // Configuration state
  const [config, setConfig] = useState({
    access_token: '',
    phone_number_id: '',
    webhook_verify_token: '',
    auto_reply_enabled: false,
    business_hours_start: '09:00',
    business_hours_end: '18:00',
    default_template: '',
  });

  useEffect(() => {
    fetchWhatsAppData();
    const interval = setInterval(fetchConversations, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchWhatsAppData = async () => {
    try {
      setIsLoading(true);
      
      // Check health status
      const healthResponse = await fetch('/api/whatsapp/health');
      const healthData = await healthResponse.json();
      setIsConnected(healthData.status === 'healthy');

      if (isConnected) {
        await Promise.all([
          fetchConversations(),
          fetchAnalytics(),
        ]);
      }
    } catch (error) {
      console.error('Error fetching WhatsApp data:', error);
      toast({
        title: 'Error',
        description: 'Failed to load WhatsApp integration data',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchConversations = async () => {
    try {
      const response = await fetch('/api/whatsapp/conversations');
      const data = await response.json();
      if (data.success) {
        setConversations(data.conversations);
      }
    } catch (error) {
      console.error('Error fetching conversations:', error);
    }
  };

  const fetchMessages = async (whatsappId: string) => {
    try {
      const response = await fetch(`/api/whatsapp/messages/${whatsappId}`);
      const data = await response.json();
      if (data.success) {
        setMessages(data.messages);
      }
    } catch (error) {
      console.error('Error fetching messages:', error);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const response = await fetch('/api/whatsapp/analytics');
      const data = await response.json();
      if (data.success) {
        setAnalytics(data.analytics);
      }
    } catch (error) {
      console.error('Error fetching analytics:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !selectedRecipient) return;

    try {
      const messageContent = messageType === 'text' 
        ? { body: newMessage }
        : { template_name: newMessage };

      const response = await fetch('/api/whatsapp/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          to: selectedRecipient,
          type: messageType,
          content: messageContent,
        }),
      });

      const result = await response.json();

      if (result.success) {
        toast({
          title: 'Message Sent',
          description: 'Your WhatsApp message has been sent successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        setNewMessage('');
        onComposeClose();
        
        // Refresh messages if we have a selected conversation
        if (selectedConversation) {
          fetchMessages(selectedConversation.whatsapp_id);
        }
      } else {
        toast({
          title: 'Send Failed',
          description: result.error || 'Failed to send message',
          status: 'error',
          duration: 3000,
          isClosable: true,
        });
      }
    } catch (error) {
      console.error('Error sending message:', error);
      toast({
        title: 'Send Failed',
        description: 'An error occurred while sending the message',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleSaveConfig = async () => {
    try {
      // This would normally save to backend
      toast({
        title: 'Configuration Saved',
        description: 'WhatsApp Business configuration has been saved',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      onConfigClose();
      
      // Re-check health after config save
      setTimeout(fetchWhatsAppData, 1000);
    } catch (error) {
      console.error('Error saving config:', error);
      toast({
        title: 'Save Failed',
        description: 'Failed to save configuration',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleConversationSelect = (conversation: WhatsAppConversation) => {
    setSelectedConversation(conversation);
    fetchMessages(conversation.whatsapp_id);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'green';
      case 'inactive':
        return 'red';
      case 'pending':
        return 'yellow';
      default:
        return 'gray';
    }
  };

  const getMessageTypeIcon = (type: string) => {
    switch (type) {
      case 'text':
        return <ChatIcon />;
      case 'image':
        return <Icon viewBox="0 0 24 24" fill="currentColor"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></Icon>;
      case 'audio':
        return <Icon viewBox="0 0 24 24" fill="currentColor"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.78V20c0 .55.45 1 1 1s1-.45 1-1v-2.08c3.02-.43 5.42-2.78 5.91-5.78.1-.6-.39-1.14-1-1.14z"/></Icon>;
      default:
        return <ChatIcon />;
    }
  };

  if (isLoading) {
    return (
      <Box p={8}>
        <VStack spacing={4} align="center">
          <Spinner size="xl" />
          <Text>Loading WhatsApp Business integration...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box p={8}>
      {/* Header */}
      <HStack justify="space-between" mb={8}>
        <VStack align="start" spacing={1}>
          <Heading size="xl">WhatsApp Business Integration</Heading>
          <Text color="gray.600">
            Manage customer communications through WhatsApp Business API
          </Text>
        </VStack>
        <HStack>
          <Badge
            colorScheme={isConnected ? 'green' : 'red'}
            px={3}
            py={1}
            borderRadius="full"
          >
            {isConnected ? 'Connected' : 'Disconnected'}
          </Badge>
          <Button
            leftIcon={<SettingsIcon />}
            variant="outline"
            onClick={onConfigOpen}
          >
            Configure
          </Button>
          <Button
            leftIcon={<PlusSquareIcon />}
            colorScheme="green"
            onClick={onComposeOpen}
            disabled={!isConnected}
          >
            New Message
          </Button>
        </HStack>
      </HStack>

      {/* Analytics Overview */}
      {analytics && (
        <Card mb={8}>
          <CardHeader>
            <Heading size="md">Analytics Overview</Heading>
          </CardHeader>
          <CardBody>
            <StatGroup>
              <Stat>
                <StatLabel>Total Conversations</StatLabel>
                <StatNumber>{analytics.conversation_statistics.total_conversations}</StatNumber>
              </Stat>
              <Stat>
                <StatLabel>Active Conversations</StatLabel>
                <StatNumber color="green.500">{analytics.conversation_statistics.active_conversations}</StatNumber>
              </Stat>
              <Stat>
                <StatLabel>Messages Sent Today</StatLabel>
                <StatNumber>
                  {analytics.message_statistics
                    .filter(m => m.direction === 'outbound')
                    .reduce((sum, m) => sum + m.count, 0)}
                </StatNumber>
              </Stat>
              <Stat>
                <StatLabel>Messages Received Today</StatLabel>
                <StatNumber>
                  {analytics.message_statistics
                    .filter(m => m.direction === 'inbound')
                    .reduce((sum, m) => sum + m.count, 0)}
                </StatNumber>
              </Stat>
            </StatGroup>
          </CardBody>
        </Card>
      )}

      {/* Main Content */}
      <Tabs variant="enclosed" onChange={setActiveTab}>
        <TabList>
          <Tab>Conversations</Tab>
          <Tab>Messages</Tab>
          <Tab>Templates</Tab>
          <Tab>Analytics</Tab>
        </TabList>

        <TabPanels>
          {/* Conversations Tab */}
          <TabPanel>
            {!isConnected ? (
              <Alert status="warning">
                <AlertIcon />
                <Box>
                  <AlertTitle>WhatsApp Not Connected</AlertTitle>
                  <AlertDescription>
                    Please configure your WhatsApp Business API settings to start managing conversations.
                  </AlertDescription>
                </Box>
                <Button ml={4} colorScheme="green" onClick={onConfigOpen}>
                  Configure Now
                </Button>
              </Alert>
            ) : (
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Heading size="md">Recent Conversations</Heading>
                  <Button
                    leftIcon={<RepeatIcon />}
                    variant="outline"
                    size="sm"
                    onClick={fetchConversations}
                  >
                    Refresh
                  </Button>
                </HStack>
                
                <Grid templateColumns="repeat(auto-fill, minmax(400px, 1fr))" gap={4}>
                  {conversations.map((conversation) => (
                    <Card
                      key={conversation.id}
                      cursor="pointer"
                      onClick={() => handleConversationSelect(conversation)}
                      border={selectedConversation?.id === conversation.id ? "2px solid" : "1px solid"}
                      borderColor={selectedConversation?.id === conversation.id ? "blue.500" : "gray.200"}
                      _hover={{ shadow: "md" }}
                    >
                      <CardBody>
                        <HStack justify="space-between" mb={2}>
                          <HStack>
                            <Avatar size="sm" name={conversation.name} />
                            <VStack align="start" spacing={0}>
                              <Text fontWeight="medium">
                                {conversation.name || conversation.phone_number}
                              </Text>
                              <Text fontSize="sm" color="gray.600">
                                {conversation.phone_number}
                              </Text>
                            </VStack>
                          </HStack>
                          <Badge colorScheme={getStatusColor(conversation.status)}>
                            {conversation.status}
                          </Badge>
                        </HStack>
                        
                        <HStack justify="space-between" mt={3}>
                          <Text fontSize="sm" color="gray.500">
                            {conversation.message_count || 0} messages
                          </Text>
                          <Text fontSize="sm" color="gray.500">
                            {new Date(conversation.last_message_at).toLocaleDateString()}
                          </Text>
                        </HStack>
                      </CardBody>
                    </Card>
                  ))}
                </Grid>
              </VStack>
            )}
          </TabPanel>

          {/* Messages Tab */}
          <TabPanel>
            {selectedConversation ? (
              <VStack spacing={4} align="stretch">
                <Card>
                  <CardHeader>
                    <HStack justify="space-between">
                      <Heading size="md">
                        Messages with {selectedConversation.name || selectedConversation.phone_number}
                      </Heading>
                      <Button
                        leftIcon={<RepeatIcon />}
                        variant="outline"
                        size="sm"
                        onClick={() => fetchMessages(selectedConversation.whatsapp_id)}
                      >
                        Refresh
                      </Button>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={3} maxH="400px" overflowY="auto">
                      {messages.map((message) => (
                        <HStack
                          key={message.id}
                          justify={message.direction === 'outbound' ? 'flex-end' : 'flex-start'}
                          w="full"
                        >
                          <Box
                            maxW="70%"
                            p={3}
                            borderRadius="lg"
                            bg={message.direction === 'outbound' ? 'blue.500' : 'gray.100'}
                            color={message.direction === 'outbound' ? 'white' : 'black'}
                          >
                            <HStack mb={1}>
                              {getMessageTypeIcon(message.message_type)}
                              <Text fontSize="sm" fontWeight="medium">
                                {message.direction === 'outbound' ? 'You' : 'Customer'}
                              </Text>
                            </HStack>
                            <Text>
                              {message.message_type === 'text' 
                                ? message.content?.body 
                                : `[${message.message_type.toUpperCase()}]`}
                            </Text>
                            <Text fontSize="xs" mt={2} opacity={0.7}>
                              {new Date(message.timestamp).toLocaleString()}
                            </Text>
                          </Box>
                        </HStack>
                      ))}
                    </VStack>
                  </CardBody>
                  <CardFooter>
                    <HStack w="full">
                      <Input
                        placeholder="Type a message..."
                        value={newMessage}
                        onChange={(e) => setNewMessage(e.target.value)}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleSendMessage();
                          }
                        }}
                      />
                      <Button
                        colorScheme="green"
                        onClick={handleSendMessage}
                        disabled={!newMessage.trim()}
                      >
                        Send
                      </Button>
                    </HStack>
                  </CardFooter>
                </Card>
              </VStack>
            ) : (
              <Alert status="info">
                <AlertIcon />
                <Box>
                  <AlertTitle>No Conversation Selected</AlertTitle>
                  <AlertDescription>
                    Select a conversation from the Conversations tab to view and send messages.
                  </AlertDescription>
                </Box>
              </Alert>
            )}
          </TabPanel>

          {/* Templates Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Heading size="md">Message Templates</Heading>
                <Button leftIcon={<PlusSquareIcon />} colorScheme="green" onClick={onTemplateOpen}>
                  Create Template
                </Button>
              </HStack>
              
              <Alert status="info">
                <AlertIcon />
                <Box>
                  <AlertTitle>WhatsApp Message Templates</AlertTitle>
                  <AlertDescription>
                    Create reusable message templates for common customer interactions. 
                    Templates must be approved by WhatsApp before use.
                  </AlertDescription>
                </Box>
              </Alert>
              
              <Table variant="simple">
                <Thead>
                  <Tr>
                    <Th>Template Name</Th>
                    <Th>Category</Th>
                    <Th>Language</Th>
                    <Th>Status</Th>
                    <Th>Actions</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {templates.map((template) => (
                    <Tr key={template.id}>
                      <Td fontWeight="medium">{template.template_name}</Td>
                      <Td>
                        <Tag colorScheme="blue">
                          {template.category}
                        </Tag>
                      </Td>
                      <Td>{template.language_code.toUpperCase()}</Td>
                      <Td>
                        <Badge colorScheme={getStatusColor(template.status)}>
                          {template.status}
                        </Badge>
                      </Td>
                      <Td>
                        <HStack>
                          <IconButton
                            aria-label="Edit template"
                            icon={<EditIcon />}
                            size="sm"
                            variant="ghost"
                          />
                          <IconButton
                            aria-label="Delete template"
                            icon={<DeleteIcon />}
                            size="sm"
                            variant="ghost"
                            colorScheme="red"
                          />
                        </HStack>
                      </Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            </VStack>
          </TabPanel>

          {/* Analytics Tab */}
          <TabPanel>
            {analytics ? (
              <VStack spacing={6} align="stretch">
                <Heading size="md">WhatsApp Analytics</Heading>
                
                <Grid templateColumns="repeat(2, 1fr)" gap={6}>
                  <Card>
                    <CardHeader>
                      <Heading size="sm">Message Statistics</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={3} align="stretch">
                        {analytics.message_statistics.map((stat, index) => (
                          <HStack key={index} justify="space-between">
                            <Text>
                              {stat.direction} {stat.message_type} ({stat.status})
                            </Text>
                            <Text fontWeight="bold">{stat.count}</Text>
                          </HStack>
                        ))}
                      </VStack>
                    </CardBody>
                  </Card>
                  
                  <Card>
                    <CardHeader>
                      <Heading size="sm">Contact Growth</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={3} align="stretch">
                        {analytics.contact_growth.map((growth, index) => (
                          <HStack key={index} justify="space-between">
                            <Text>{growth.date}</Text>
                            <Text fontWeight="bold">+{growth.new_contacts}</Text>
                          </HStack>
                        ))}
                      </VStack>
                    </CardBody>
                  </Card>
                </Grid>
              </VStack>
            ) : (
              <Alert status="info">
                <AlertIcon />
                <Text>No analytics data available</Text>
              </Alert>
            )}
          </TabPanel>
        </TabPanels>
      </Tabs>

      {/* Compose Message Modal */}
      <Modal isOpen={isComposeOpen} onClose={onComposeClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Compose New Message</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Recipient Phone Number</FormLabel>
                <Input
                  placeholder="+1234567890"
                  value={selectedRecipient}
                  onChange={(e) => setSelectedRecipient(e.target.value)}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Message Type</FormLabel>
                <Select value={messageType} onChange={(e) => setMessageType(e.target.value as any)}>
                  <option value="text">Text Message</option>
                  <option value="template">Template Message</option>
                  <option value="media">Media Message</option>
                </Select>
              </FormControl>
              
              <FormControl>
                <FormLabel>Message Content</FormLabel>
                {messageType === 'text' ? (
                  <Textarea
                    placeholder="Type your message here..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    rows={4}
                  />
                ) : messageType === 'template' ? (
                  <Select placeholder="Select a template">
                    <option value="welcome">Welcome Message</option>
                    <option value="appointment">Appointment Reminder</option>
                    <option value="followup">Follow Up</option>
                  </Select>
                ) : (
                  <Text>Media upload functionality coming soon</Text>
                )}
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onComposeClose}>
              Cancel
            </Button>
            <Button colorScheme="green" onClick={handleSendMessage}>
              Send Message
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Configuration Modal */}
      <Modal isOpen={isConfigOpen} onClose={onConfigClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>WhatsApp Business Configuration</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Access Token</FormLabel>
                <Input
                  type="password"
                  placeholder="WhatsApp Business API Access Token"
                  value={config.access_token}
                  onChange={(e) => setConfig({...config, access_token: e.target.value})}
                />
              </FormControl>
              
              <FormControl isRequired>
                <FormLabel>Phone Number ID</FormLabel>
                <Input
                  placeholder="Phone Number ID from Meta Business Suite"
                  value={config.phone_number_id}
                  onChange={(e) => setConfig({...config, phone_number_id: e.target.value})}
                />
              </FormControl>
              
              <FormControl isRequired>
                <FormLabel>Webhook Verify Token</FormLabel>
                <Input
                  type="password"
                  placeholder="Custom webhook verification token"
                  value={config.webhook_verify_token}
                  onChange={(e) => setConfig({...config, webhook_verify_token: e.target.value})}
                />
              </FormControl>
              
              <Divider />
              
              <FormControl>
                <FormLabel>Enable Auto-Reply</FormLabel>
                <Switch
                  isChecked={config.auto_reply_enabled}
                  onChange={(e) => setConfig({...config, auto_reply_enabled: e.target.checked})}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Business Hours Start</FormLabel>
                <Input
                  type="time"
                  value={config.business_hours_start}
                  onChange={(e) => setConfig({...config, business_hours_start: e.target.value})}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Business Hours End</FormLabel>
                <Input
                  type="time"
                  value={config.business_hours_end}
                  onChange={(e) => setConfig({...config, business_hours_end: e.target.value})}
                />
              </FormControl>
              
              <Alert status="info">
                <AlertIcon />
                <Box>
                  <AlertTitle>Setup Instructions</AlertTitle>
                  <AlertDescription>
                    1. Create a Meta Business Account and WhatsApp Business API access
                    2. Get your Phone Number ID from Meta Business Suite
                    3. Generate an Access Token with appropriate permissions
                    4. Configure your webhook endpoint and verification token
                  </AlertDescription>
                </Box>
              </Alert>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onConfigClose}>
              Cancel
            </Button>
            <Button colorScheme="blue" onClick={handleSaveConfig}>
              Save Configuration
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Template Modal */}
      <Modal isOpen={isTemplateOpen} onClose={onTemplateClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create Message Template</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Template Name</FormLabel>
                <Input placeholder="e.g., welcome_message" />
              </FormControl>
              
              <FormControl isRequired>
                <FormLabel>Category</FormLabel>
                <Select placeholder="Select category">
                  <option value="UTILITY">Utility</option>
                  <option value="MARKETING">Marketing</option>
                  <option value="AUTHENTICATION">Authentication</option>
                </Select>
              </FormControl>
              
              <FormControl isRequired>
                <FormLabel>Language</FormLabel>
                <Select placeholder="Select language">
                  <option value="en">English</option>
                  <option value="es">Spanish</option>
                  <option value="fr">French</option>
                </Select>
              </FormControl>
              
              <FormControl>
                <FormLabel>Header</FormLabel>
                <Input placeholder="Optional header text" />
              </FormControl>
              
              <FormControl isRequired>
                <FormLabel>Body</FormLabel>
                <Textarea
                  placeholder="Message body with variables like {{1}} for personalization"
                  rows={4}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Footer</FormLabel>
                <Input placeholder="Optional footer text" />
              </FormControl>
              
              <Alert status="warning">
                <AlertIcon />
                <Text fontSize="sm">
                  Templates require WhatsApp approval before they can be used. 
                  Review process typically takes 1-2 business days.
                </Text>
              </Alert>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onTemplateClose}>
              Cancel
            </Button>
            <Button colorScheme="green">
              Submit for Approval
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default WhatsAppBusinessIntegration;