/**
 * Slack Integration Page
 * Complete Slack messaging and collaboration integration
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Divider,
  useColorModeValue,
  Stack,
  Spacer,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
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
  TableContainer,
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
  useDisclosure,
  Tag,
  TagLabel,
  Flex,
  Grid,
  GridItem,
  Alert,
  AlertIcon,
  Avatar,
  Image,
  IconButton,
  Tooltip,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  CheckboxGroup,
  Checkbox,
} from "@chakra-ui/react";
import {
  ChatIcon,
  Icon as ChakraIcon,
  SearchIcon,
  AddIcon,
  EditIcon,
  DeleteIcon,
  ExternalLinkIcon,
  ViewIcon,
  RepeatIcon,
  SettingsIcon,
  CheckCircleIcon,
  WarningIcon,
  InfoIcon,
  TimeIcon,
  PhoneIcon,
  UserIcon,
  EmailIcon,
  CalendarIcon,
  AttachmentIcon,
  HeartIcon,
  ReplyIcon,
  ForwardIcon,
} from "@chakra-ui/icons";

interface SlackChannel {
  id: string;
  name: string;
  type: string;
  topic: string;
  purpose: string;
  created: number;
  creator: string;
  is_archived: boolean;
  is_general: boolean;
  is_private: boolean;
  member_count: number;
  last_read: string;
  latest: any;
  unread_count: number;
  team_id: string;
}

interface SlackMessage {
  id: string;
  user_id: string;
  user_name: string;
  text: string;
  type: string;
  subtype: string;
  channel_id: string;
  timestamp: string;
  thread_ts: string;
  reply_count: number;
  has_files: boolean;
  file_count: number;
  reactions: any[];
  is_edited: boolean;
  edited_timestamp: string;
}

interface SlackFile {
  id: string;
  name: string;
  title: string;
  mimetype: string;
  filetype: string;
  size: number;
  url_private: string;
  url_private_download: string;
  permalink: string;
  user_id: string;
  username: string;
  channel_ids: string[];
  is_public: boolean;
  timestamp: number;
  created: number;
  has_expiration: boolean;
  expires: number;
  editable: boolean;
  preview: string;
  thumb_64: string;
  thumb_80: string;
  thumb_360: string;
  thumb_360_w: number;
  thumb_360_h: number;
  original_w: number;
  original_h: number;
}

interface SlackUser {
  id: string;
  name: string;
  real_name: string;
  display_name: string;
  email: string;
  avatar: string;
  is_admin: boolean;
  is_owner: boolean;
  team_id: string;
  presence: string;
}

interface SlackWorkspace {
  team_id: string;
  team_name: string;
  domain: string;
  email_domain: string;
  icon: string;
  created: number;
  enterprise_id: string;
  enterprise_name: string;
}

const SlackIntegration: React.FC = () => {
  const [channels, setChannels] = useState<SlackChannel[]>([]);
  const [messages, setMessages] = useState<SlackMessage[]>([]);
  const [files, setFiles] = useState<SlackFile[]>([]);
  const [searchResults, setSearchResults] = useState<SlackMessage[]>([]);
  const [workspace, setWorkspace] = useState<SlackWorkspace | null>(null);
  const [user, setUser] = useState<SlackUser | null>(null);
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<"healthy" | "error" | "unknown">("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedChannel, setSelectedChannel] = useState("");
  const [selectedMessage, setSelectedMessage] = useState<SlackMessage | null>(null);
  const [loading, setLoading] = useState({
    channels: false,
    messages: false,
    files: false,
    search: false,
    send: false,
  });

  // Message composition states
  const [messageText, setMessageText] = useState("");
  const [replyText, setReplyText] = useState("");
  const [channelFilter, setChannelFilter] = useState<string[]>(["public_channel", "private_channel", "mpim", "im"]);

  const { isOpen: isMessageOpen, onOpen: onMessageOpen, onClose: onMessageClose } = useDisclosure();
  const { isOpen: isReplyOpen, onOpen: onReplyOpen, onClose: onReplyClose } = useDisclosure();
  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/slack/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        // Load workspace info
        await loadWorkspaceInfo();
        await loadUserInfo();
      } else {
        setConnected(false);
        setHealthStatus("error");
      }
    } catch (error) {
      console.error("Health check failed:", error);
      setConnected(false);
      setHealthStatus("error");
    }
  };

  // Load workspace info
  const loadWorkspaceInfo = async () => {
    try {
      const response = await fetch("/api/integrations/slack/user/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data.team_id) {
          setWorkspace({
            team_id: data.data.team_id,
            team_name: data.data.team_name || data.data.name,
            domain: data.data.domain,
            email_domain: data.data.email_domain,
            icon: data.data.avatar,
            created: data.data.created,
            enterprise_id: data.data.enterprise_id,
            enterprise_name: data.data.enterprise_name,
          });
        }
      }
    } catch (error) {
      console.error("Failed to load workspace info:", error);
    }
  };

  // Load user info
  const loadUserInfo = async () => {
    try {
      const response = await fetch("/api/integrations/slack/user/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "me",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setUser(data.data);
        }
      }
    } catch (error) {
      console.error("Failed to load user info:", error);
    }
  };

  // Load channels
  const loadChannels = async () => {
    if (!connected) return;

    setLoading((prev) => ({ ...prev, channels: true }));
    try {
      const response = await fetch("/api/integrations/slack/channels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          types: channelFilter,
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setChannels(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load channels:", error);
    } finally {
      setLoading((prev) => ({ ...prev, channels: false }));
    }
  };

  // Load messages
  const loadMessages = async (channelId: string) => {
    if (!connected || !channelId) return;

    setLoading((prev) => ({ ...prev, messages: true }));
    try {
      const response = await fetch("/api/integrations/slack/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channel_id: channelId,
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMessages(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load messages:", error);
    } finally {
      setLoading((prev) => ({ ...prev, messages: false }));
    }
  };

  // Load files
  const loadFiles = async () => {
    if (!connected) return;

    setLoading((prev) => ({ ...prev, files: true }));
    try {
      const response = await fetch("/api/integrations/slack/files", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          types: "all",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setFiles(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load files:", error);
    } finally {
      setLoading((prev) => ({ ...prev, files: false }));
    }
  };

  // Send message
  const sendMessage = async () => {
    if (!messageText.trim() || !selectedChannel) return;

    setLoading((prev) => ({ ...prev, send: true }));
    try {
      const response = await fetch("/api/integrations/slack/messages/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channel_id: selectedChannel,
          text: messageText,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          toast({
            title: "Message sent",
            status: "success",
            duration: 3000,
          });
          setMessageText("");
          await loadMessages(selectedChannel);
        }
      }
    } catch (error) {
      console.error("Failed to send message:", error);
      toast({
        title: "Failed to send message",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, send: false }));
    }
  };

  // Search messages
  const searchMessages = async () => {
    if (!searchQuery.trim() || !connected) return;

    setLoading((prev) => ({ ...prev, search: true }));
    try {
      const response = await fetch("/api/integrations/slack/search/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery,
          count: 50,
          sort: "timestamp_desc",
          channel_id: selectedChannel || undefined,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setSearchResults(data.data || []);
      }
    } catch (error) {
      console.error("Failed to search messages:", error);
    } finally {
      setLoading((prev) => ({ ...prev, search: false }));
    }
  };

  // Filter data based on search
  const filteredChannels = channels.filter((channel) =>
    channel.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    channel.topic?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    channel.purpose?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Stats calculations
  const totalChannels = channels.length;
  const publicChannels = channels.filter((c) => c.type === "public").length;
  const privateChannels = channels.filter((c) => c.type === "private").length;
  const totalMessages = messages.length;
  const totalFiles = files.length;
  const unreadMessages = channels.reduce((sum, channel) => sum + channel.unread_count, 0);

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadChannels();
      loadFiles();
    }
  }, [connected, channelFilter]);

  useEffect(() => {
    if (selectedChannel) {
      loadMessages(selectedChannel);
    }
  }, [selectedChannel]);

  const getChannelTypeColor = (type: string): string => {
    switch (type) {
      case "public":
        return "green";
      case "private":
        return "yellow";
      case "dm":
        return "blue";
      case "group_dm":
        return "purple";
      default:
        return "gray";
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case "active":
        return "green";
      case "away":
        return "yellow";
      case "offline":
        return "gray";
      default:
        return "gray";
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formatDate = (timestamp: string | number): string => {
    return new Date(typeof timestamp === 'number' ? timestamp * 1000 : timestamp).toLocaleString();
  };

  const formatTime = (timestamp: string | number): string => {
    const date = new Date(typeof timestamp === 'number' ? timestamp * 1000 : timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={ChatIcon} w={8} h={8} color="purple.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Slack Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Team messaging and collaboration platform
              </Text>
            </VStack>
          </HStack>

          <HStack spacing={4}>
            <Badge
              colorScheme={healthStatus === "healthy" ? "green" : "red"}
              display="flex"
              alignItems="center"
            >
              {healthStatus === "healthy" ? (
                <CheckCircleIcon mr={1} />
              ) : (
                <WarningIcon mr={1} />
              )}
              {connected ? "Connected" : "Disconnected"}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RepeatIcon />}
              onClick={checkConnection}
            >
              Refresh Status
            </Button>
          </HStack>

          {/* Workspace Info */}
          {workspace && user && (
            <HStack spacing={4} p={4} borderWidth="1px" borderRadius="md" bg={bgColor}>
              <Avatar size="sm" src={user.avatar} name={user.real_name} />
              <VStack align="start" spacing={0}>
                <Text fontWeight="medium">{workspace.team_name}</Text>
                <Text fontSize="sm" color="gray.600">
                  {user.real_name} • {user.display_name}
                </Text>
              </VStack>
              <Spacer />
              <Badge colorScheme={getStatusColor(user.presence)}>
                {user.presence}
              </Badge>
            </HStack>
          )}
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={ChatIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Slack</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Slack workspace to start messaging and collaboration
                  </Text>
                </VStack>
                <Button
                  colorScheme="purple"
                  size="lg"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() =>
                    (window.location.href = "/api/integrations/slack/auth/start")
                  }
                >
                  Connect Slack Workspace
                </Button>
              </VStack>
            </CardBody>
          </Card>
        ) : (
          // Connected State
          <>
            {/* Services Overview */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Channels</StatLabel>
                    <StatNumber>{totalChannels}</StatNumber>
                    <StatHelpText>{publicChannels} public, {privateChannels} private</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Messages</StatLabel>
                    <StatNumber>{totalMessages}</StatNumber>
                    <StatHelpText>{unreadMessages} unread</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Files</StatLabel>
                    <StatNumber>{totalFiles}</StatNumber>
                    <StatHelpText>Shared documents</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Workspace</StatLabel>
                    <StatNumber>{workspace?.team_name || "Loading..."}</StatNumber>
                    <StatHelpText>Active workspace</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Channels</Tab>
                <Tab>Messages</Tab>
                <Tab>Files</Tab>
                <Tab>Search</Tab>
              </TabList>

              <TabPanels>
                {/* Channels Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <CheckboxGroup value={channelFilter} onChange={setChannelFilter}>
                        <HStack spacing={4}>
                          <Checkbox value="public_channel">Public</Checkbox>
                          <Checkbox value="private_channel">Private</Checkbox>
                          <Checkbox value="mpim">Group DMs</Checkbox>
                          <Checkbox value="im">DMs</Checkbox>
                        </HStack>
                      </CheckboxGroup>
                      <Spacer />
                      <Button
                        colorScheme="purple"
                        leftIcon={<RepeatIcon />}
                        onClick={loadChannels}
                        isLoading={loading.channels}
                      >
                        Refresh
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Channel</Th>
                                <Th>Type</Th>
                                <Th>Members</Th>
                                <Th>Unread</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {filteredChannels.map((channel) => (
                                <Tr key={channel.id}>
                                  <Td>
                                    <HStack>
                                      <Icon as={ChatIcon} color={getChannelTypeColor(channel.type) + ".500"} />
                                      <VStack align="start" spacing={0}>
                                        <Text fontWeight="medium">{channel.name}</Text>
                                        {channel.topic && (
                                          <Text fontSize="sm" color="gray.600" noOfLines={1}>
                                            {channel.topic}
                                          </Text>
                                        )}
                                      </VStack>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Tag colorScheme={getChannelTypeColor(channel.type)} size="sm">
                                      <TagLabel>{channel.type}</TagLabel>
                                    </Tag>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{channel.member_count}</Text>
                                  </Td>
                                  <Td>
                                    {channel.unread_count > 0 && (
                                      <Badge colorScheme="red">
                                        {channel.unread_count}
                                      </Badge>
                                    )}
                                  </Td>
                                  <Td>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => setSelectedChannel(channel.id)}
                                      color={selectedChannel === channel.id ? "purple" : "gray"}
                                    >
                                      Open
                                    </Button>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Messages Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    {selectedChannel && (
                      <VStack spacing={4} p={4} borderWidth="1px" borderRadius="md">
                        <Text fontWeight="medium">
                          Channel: {channels.find((c) => c.id === selectedChannel)?.name}
                        </Text>
                        
                        {/* Message Input */}
                        <HStack spacing={2}>
                          <Input
                            placeholder="Type a message..."
                            value={messageText}
                            onChange={(e) => setMessageText(e.target.value)}
                            onKeyPress={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                sendMessage();
                              }
                            }}
                          />
                          <Button
                            colorScheme="purple"
                            onClick={sendMessage}
                            isLoading={loading.send}
                            disabled={!messageText.trim()}
                          >
                            Send
                          </Button>
                        </HStack>
                      </VStack>
                    )}

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {messages.map((message) => (
                            <Box key={message.id} p={4} borderWidth="1px" borderRadius="md">
                              <HStack spacing={3} mb={2}>
                                <Avatar size="sm" name={message.user_name} />
                                <VStack align="start" spacing={0}>
                                  <Text fontWeight="medium">{message.user_name}</Text>
                                  <Text fontSize="sm" color="gray.600">
                                    {formatTime(message.timestamp)}
                                  </Text>
                                </VStack>
                                <Spacer />
                                {message.has_files && (
                                  <Tooltip label="Has attachments">
                                    <Icon as={AttachmentIcon} color="gray.500" />
                                  </Tooltip>
                                )}
                                {message.reactions.length > 0 && (
                                  <Tooltip label={`${message.reactions.length} reactions`}>
                                    <Icon as={HeartIcon} color="gray.500" />
                                  </Tooltip>
                                )}
                              </HStack>
                              
                              <Text mb={2}>{message.text}</Text>
                              
                              {message.thread_ts && message.reply_count > 0 && (
                                <HStack>
                                  <Button size="sm" variant="outline" leftIcon={<ReplyIcon />}>
                                    View {message.reply_count} replies
                                  </Button>
                                </HStack>
                              )}
                              
                              {message.is_edited && (
                                <Text fontSize="sm" color="gray.500">
                                  (edited {formatDate(message.edited_timestamp)})
                                </Text>
                              )}
                            </Box>
                          ))}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Files Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Button
                      colorScheme="purple"
                      leftIcon={<RepeatIcon />}
                      onClick={loadFiles}
                      isLoading={loading.files}
                      alignSelf="flex-end"
                    >
                      Refresh Files
                    </Button>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>File</Th>
                                <Th>Type</Th>
                                <Th>Size</Th>
                                <Th>Modified</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {files.map((file) => (
                                <Tr key={file.id}>
                                  <Td>
                                    <HStack>
                                      {file.thumb_80 ? (
                                        <Image
                                          src={file.thumb_80}
                                          alt={file.name}
                                          boxSize="40px"
                                          borderRadius="md"
                                        />
                                      ) : (
                                        <Icon as={AttachmentIcon} boxSize="40px" color="gray.500" />
                                      )}
                                      <VStack align="start" spacing={0}>
                                        <Text fontWeight="medium">{file.name}</Text>
                                        {file.title && file.title !== file.name && (
                                          <Text fontSize="sm" color="gray.600">
                                            {file.title}
                                          </Text>
                                        )}
                                      </VStack>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Badge colorScheme="blue" size="sm">
                                      {file.filetype || file.mimetype?.split('/')[0] || 'Unknown'}
                                    </Badge>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatFileSize(file.size)}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatDate(file.timestamp)}</Text>
                                  </Td>
                                  <Td>
                                    <HStack>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ViewIcon />}
                                        onClick={() => window.open(file.url_private)}
                                      >
                                        View
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ExternalLinkIcon />}
                                        onClick={() => window.open(file.permalink)}
                                      >
                                        Open
                                      </Button>
                                    </HStack>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Search Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search messages..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            searchMessages();
                          }
                        }}
                        leftElement={<SearchIcon />}
                      />
                      <Button
                        colorScheme="purple"
                        onClick={searchMessages}
                        isLoading={loading.search}
                        disabled={!searchQuery.trim()}
                      >
                        Search
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {searchResults.map((result) => (
                            <Box key={result.id} p={4} borderWidth="1px" borderRadius="md">
                              <HStack spacing={3} mb={2}>
                                <Avatar size="sm" name={result.username} />
                                <VStack align="start" spacing={0}>
                                  <Text fontWeight="medium">{result.username}</Text>
                                  <Text fontSize="sm" color="gray.600">
                                    {result.channel_name} • {formatDate(result.timestamp)}
                                  </Text>
                                </VStack>
                                <Spacer />
                                <Tag colorScheme="blue" size="sm">
                                  Score: {Math.round(result.score * 100)}
                                </Tag>
                              </HStack>
                              
                              <Text mb={2}>{result.text}</Text>
                              
                              <Button
                                size="sm"
                                variant="outline"
                                leftIcon={<ExternalLinkIcon />}
                                onClick={() => window.open(result.permalink)}
                              >
                                View in Slack
                              </Button>
                            </Box>
                          ))}
                          
                          {searchResults.length === 0 && searchQuery && (
                            <VStack spacing={4} py={8}>
                              <Icon as={SearchIcon} w={12} h={12} color="gray.400" />
                              <Text color="gray.600">No search results found</Text>
                            </VStack>
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </>
        )}
      </VStack>
    </Box>
  );
};

export default SlackIntegration;