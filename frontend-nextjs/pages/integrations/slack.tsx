/**
 * Slack Integration Page
 * Complete communication and collaboration platform integration
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
  IconButton,
  Tooltip,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Select,
  Switch,
  Wrap,
  WrapItem,
  Link,
  Image,
} from "@chakra-ui/react";
import {
  ChatAltIcon,
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
  CalendarIcon,
  FileIcon,
  FolderIcon,
  ShareIcon,
  DownloadIcon,
  RefreshIcon,
  UserIcon,
  UsersIcon,
  ActivityIcon,
  ClockIcon,
  LightningIcon,
  PaperAirplaneIcon,
  PhoneIcon,
  MailIcon,
  BusinessIcon,
  HashtagIcon,
  LockIcon,
  UnlockIcon,
  CodeIcon,
  ServerIcon,
  PinIcon,
  ReactionsIcon,
  ThreadIcon,
  BotIcon,
  ChannelIcon,
  MessageIcon,
} from "@chakra-ui/icons";

interface SlackUser {
  id: string;
  name: string;
  real_name: string;
  display_name: string;
  email: string;
  phone: string;
  title: string;
  status: string;
  status_emoji: string;
  is_bot: boolean;
  is_admin: boolean;
  is_owner: boolean;
  is_restricted: boolean;
  is_ultra_restricted: boolean;
  presence: string;
  tz: string;
  tz_label: string;
  updated: number;
  deleted: boolean;
  image: string;
  hasImage: boolean;
  hasStatus: boolean;
  hasPhone: boolean;
  hasTitle: boolean;
  hasEmail: boolean;
}

interface SlackChannel {
  id: string;
  name: string;
  name_normalized: string;
  topic: string;
  purpose: string;
  is_archived: boolean;
  is_general: boolean;
  is_private: boolean;
  is_im: boolean;
  is_mpim: boolean;
  created: number;
  creator: string;
  last_read: string;
  unread_count: number;
  unread_count_display: number;
  num_members: number;
  member_count: number;
  is_member: boolean;
  user_name: string;
  user_image: string;
  updated_at: string;
  has_topic: boolean;
  has_purpose: boolean;
  is_active: boolean;
}

interface SlackMessage {
  id: string;
  ts: string;
  text: string;
  user: string;
  team: string;
  bot_id: string;
  is_bot: boolean;
  thread_ts: string;
  is_thread: boolean;
  reply_count: number;
  reactions: any[];
  files: any[];
  has_files: boolean;
  has_reactions: boolean;
  has_thread: boolean;
  edited: boolean;
  pinned: boolean;
  time: string;
  date: string;
  user_name: string;
  user_image: string;
}

interface SlackFile {
  id: string;
  name: string;
  title: string;
  mimetype: string;
  filetype: string;
  pretty_type: string;
  user: string;
  timestamp: number;
  size: number;
  url_private: string;
  url_private_download: string;
  permalink: string;
  permalink_public: string;
  editable: boolean;
  is_public: boolean;
  is_external: boolean;
  has_preview: boolean;
  num_starred: number;
  time: string;
  date: string;
  size_mb: number;
  has_image: boolean;
  has_video: boolean;
  has_audio: boolean;
  is_document: boolean;
}

const SlackIntegration: React.FC = () => {
  const [users, setUsers] = useState<SlackUser[]>([]);
  const [channels, setChannels] = useState<SlackChannel[]>([]);
  const [messages, setMessages] = useState<SlackMessage[]>([]);
  const [files, setFiles] = useState<SlackFile[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<string>("");
  const [teamInfo, setTeamInfo] = useState<any>(null);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<"healthy" | "error" | "unknown">("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [messageText, setMessageText] = useState("");
  const [loading, setLoading] = useState({
    users: false,
    channels: false,
    messages: false,
    files: false,
    team: false,
    search: false,
    send: false,
    refresh: false,
  });

  const { 
    isOpen: isMessageOpen, 
    onOpen: onMessageOpen, 
    onClose: onMessageClose 
  } = useDisclosure();

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/slack/health");
      if (response.ok) {
        const data = await response.json();
        setConnected(data.status === "healthy");
        setHealthStatus(data.status);
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

  // Load team info
  const loadTeamInfo = async () => {
    if (!connected) return;

    setLoading((prev) => ({ ...prev, team: true }));
    try {
      const response = await fetch("/api/integrations/slack/team/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setTeamInfo(data.data);
        }
      }
    } catch (error) {
      console.error("Failed to load team info:", error);
    } finally {
      setLoading((prev) => ({ ...prev, team: false }));
    }
  };

  // Load users
  const loadUsers = async () => {
    if (!connected) return;

    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/slack/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setUsers(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load Slack users:", error);
    } finally {
      setLoading((prev) => ({ ...prev, users: false }));
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
          types: ["public_channel", "private_channel", "im"],
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setChannels(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load Slack channels:", error);
    } finally {
      setLoading((prev) => ({ ...prev, channels: false }));
    }
  };

  // Load messages for selected channel
  const loadMessages = async (channelId: string) => {
    if (!connected || !channelId) return;

    setLoading((prev) => ({ ...prev, messages: true }));
    try {
      const response = await fetch("/api/integrations/slack/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channelId,
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setMessages(data.data || []);
        }
      }
    } catch (error) {
      console.error("Failed to load Slack messages:", error);
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
          types: "all",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setFiles(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load Slack files:", error);
    } finally {
      setLoading((prev) => ({ ...prev, files: false }));
    }
  };

  // Send message
  const sendMessage = async () => {
    if (!selectedChannel || !messageText.trim()) return;

    setLoading((prev) => ({ ...prev, send: true }));
    try {
      const response = await fetch("/api/integrations/slack/messages/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channelId: selectedChannel,
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
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setSearchResults(data.data || []);
      }
    } catch (error) {
      console.error("Failed to search Slack messages:", error);
    } finally {
      setLoading((prev) => ({ ...prev, search: false }));
    }
  };

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadTeamInfo();
      loadUsers();
      loadChannels();
      loadFiles();
    }
  }, [connected]);

  // Stats calculations
  const totalUsers = users.length;
  const totalChannels = channels.length;
  const totalMessages = messages.length;
  const totalFiles = files.length;
  const totalBots = users.filter(u => u.is_bot).length;
  const activeUsers = users.filter(u => u.presence === "active").length;
  const publicChannels = channels.filter(c => !c.is_private && !c.is_im).length;
  const privateChannels = channels.filter(c => c.is_private && !c.is_im).length;
  const directMessages = channels.filter(c => c.is_im).length;
  const messagesWithFiles = messages.filter(m => m.has_files).length;
  const messagesWithReactions = messages.filter(m => m.has_reactions).length;

  const formatTimestamp = (timestamp: string | number): string => {
    const ts = typeof timestamp === 'number' ? timestamp : parseFloat(timestamp);
    return new Date(ts * 1000).toLocaleString();
  };

  const formatDate = (timestamp: string): string => {
    const ts = parseFloat(timestamp);
    return new Date(ts * 1000).toLocaleDateString();
  };

  const getFileIcon = (file: SlackFile) => {
    if (file.has_image) return "🖼️";
    if (file.has_video) return "🎥";
    if (file.has_audio) return "🎵";
    if (file.mimetype.includes("pdf")) return "📄";
    if (file.mimetype.includes("zip") || file.mimetype.includes("tar")) return "📦";
    return "📎";
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={ChatAltIcon} w={8} h={8} color="purple.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Slack Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Complete communication and collaboration platform
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
            {teamInfo && (
              <HStack spacing={2}>
                <Avatar size="xs" name={teamInfo.name} />
                <Text fontSize="sm" fontWeight="medium">{teamInfo.name}</Text>
                <Text fontSize="sm" color="gray.500">({teamInfo.domain})</Text>
              </HStack>
            )}
          </HStack>
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={ChatAltIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect to Slack</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Slack workspace to manage users, channels, messages, and files
                  </Text>
                </VStack>
                <Button
                  colorScheme="purple"
                  size="lg"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() => window.open("/api/integrations/slack/auth/start")}
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
                    <StatLabel>Users</StatLabel>
                    <StatNumber>{totalUsers}</StatNumber>
                    <StatHelpText>{activeUsers} active, {totalBots} bots</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
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
                    <StatHelpText>{messagesWithFiles} with files</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Files</StatLabel>
                    <StatNumber>{totalFiles}</StatNumber>
                    <StatHelpText>Shared files</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Users</Tab>
                <Tab>Channels</Tab>
                <Tab>Messages</Tab>
                <Tab>Files</Tab>
                <Tab>Search</Tab>
              </TabList>

              <TabPanels>
                {/* Users Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Button
                        colorScheme="purple"
                        leftIcon={<RepeatIcon />}
                        onClick={loadUsers}
                        isLoading={loading.users}
                      >
                        Refresh Users
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>User</Th>
                                <Th>Role</Th>
                                <Th>Status</Th>
                                <Th>Presence</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {users.map((user) => (
                                <Tr key={user.id}>
                                  <Td>
                                    <HStack spacing={3}>
                                      <Avatar 
                                        size="sm" 
                                        name={user.display_name} 
                                        src={user.hasImage ? user.image : undefined}
                                      />
                                      <VStack align="start" spacing={0}>
                                        <Text fontWeight="medium">{user.display_name}</Text>
                                        {user.hasTitle && (
                                          <Text fontSize="sm" color="gray.600">
                                            {user.title}
                                          </Text>
                                        )}
                                        {user.hasEmail && (
                                          <Text fontSize="sm" color="blue.600">
                                            {user.email}
                                          </Text>
                                        )}
                                      </VStack>
                                      {user.is_bot && (
                                        <Tag size="sm" colorScheme="orange">
                                          <BotIcon mr={1} />
                                          Bot
                                        </Tag>
                                      )}
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Wrap>
                                      {user.is_owner && (
                                        <WrapItem>
                                          <Tag size="sm" colorScheme="purple">Owner</Tag>
                                        </WrapItem>
                                      )}
                                      {user.is_admin && (
                                        <WrapItem>
                                          <Tag size="sm" colorScheme="blue">Admin</Tag>
                                        </WrapItem>
                                      )}
                                      {user.is_restricted && (
                                        <WrapItem>
                                          <Tag size="sm" colorScheme="yellow">Restricted</Tag>
                                        </WrapItem>
                                      )}
                                    </Wrap>
                                  </Td>
                                  <Td>
                                    {user.hasStatus ? (
                                      <HStack spacing={2}>
                                        <Text fontSize="sm">{user.status}</Text>
                                        <Text>{user.status_emoji}</Text>
                                      </HStack>
                                    ) : (
                                      <Text fontSize="sm" color="gray.400">No status</Text>
                                    )}
                                  </Td>
                                  <Td>
                                    <Badge
                                      colorScheme={user.presence === "active" ? "green" : "gray"}
                                      size="sm"
                                    >
                                      {user.presence}
                                    </Badge>
                                  </Td>
                                  <Td>
                                    <Menu>
                                      <MenuButton
                                        as={IconButton}
                                        aria-label="Options"
                                        icon={<SettingsIcon />}
                                        variant="outline"
                                        size="sm"
                                      />
                                      <MenuList>
                                        <MenuItem
                                          icon={<ExternalLinkIcon />}
                                          onClick={() => window.open(`https://slack.com/app_redirect?channel=${user.id}`, "_blank")}
                                        >
                                          Open Profile
                                        </MenuItem>
                                      </MenuList>
                                    </Menu>
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

                {/* Channels Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Button
                        colorScheme="purple"
                        leftIcon={<RepeatIcon />}
                        onClick={loadChannels}
                        isLoading={loading.channels}
                      >
                        Refresh Channels
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
                                <Th>Purpose/Topic</Th>
                                <Th>Status</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {channels.map((channel) => (
                                <Tr key={channel.id}>
                                  <Td>
                                    <HStack spacing={3}>
                                      <Icon
                                        as={channel.is_im ? UserIcon : channel.is_private ? LockIcon : HashtagIcon}
                                        color={channel.is_im ? "blue" : channel.is_private ? "yellow" : "green"}
                                      />
                                      <VStack align="start" spacing={0}>
                                        <Text fontWeight="medium">
                                          {channel.is_im ? channel.user_name || "Direct Message" : channel.name}
                                        </Text>
                                        {channel.has_topic && (
                                          <Text fontSize="sm" color="gray.600">
                                            {channel.topic}
                                          </Text>
                                        )}
                                      </VStack>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Tag
                                      colorScheme={
                                        channel.is_im ? "blue" : 
                                        channel.is_private ? "yellow" : 
                                        channel.is_general ? "purple" : "green"
                                      }
                                      size="sm"
                                    >
                                      {channel.is_im ? "DM" : 
                                       channel.is_private ? "Private" : 
                                       channel.is_general ? "General" : "Public"}
                                    </Tag>
                                  </Td>
                                  <Td>
                                    {channel.is_im ? (
                                      <Text fontSize="sm">1</Text>
                                    ) : (
                                      <Text fontSize="sm">{channel.member_count || channel.num_members}</Text>
                                    )}
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm" noOfLines={2}>
                                      {channel.has_purpose ? channel.purpose : 
                                       channel.has_topic ? channel.topic : 
                                       "No description"}
                                    </Text>
                                  </Td>
                                  <Td>
                                    {channel.is_archived ? (
                                      <Tag size="sm" colorScheme="gray">Archived</Tag>
                                    ) : (
                                      <Tag size="sm" colorScheme="green">Active</Tag>
                                    )}
                                  </Td>
                                  <Td>
                                    <HStack spacing={2}>
                                      <Button
                                        size="sm"
                                        colorScheme="purple"
                                        onClick={() => {
                                          setSelectedChannel(channel.id);
                                          loadMessages(channel.id);
                                        }}
                                        isLoading={loading.messages && selectedChannel === channel.id}
                                      >
                                        <ViewIcon mr={1} />
                                        View Messages
                                      </Button>
                                      <Menu>
                                        <MenuButton
                                          as={IconButton}
                                          aria-label="Options"
                                          icon={<SettingsIcon />}
                                          variant="outline"
                                          size="sm"
                                        />
                                        <MenuList>
                                          <MenuItem
                                            icon={<ExternalLinkIcon />}
                                            onClick={() => window.open(`https://slack.com/app_redirect?channel=${channel.id}`, "_blank")}
                                          >
                                            Open in Slack
                                          </MenuItem>
                                        </MenuList>
                                      </Menu>
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

                {/* Messages Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    {selectedChannel && (
                      <Card>
                        <CardBody>
                          <HStack justify="space-between">
                            <VStack align="start" spacing={0}>
                              <Text fontWeight="medium">
                                Channel: {channels.find(c => c.id === selectedChannel)?.name || "Unknown"}
                              </Text>
                              <Text fontSize="sm" color="gray.600">
                                {messages.length} messages
                              </Text>
                            </VStack>
                            <Button
                              size="sm"
                              leftIcon={<PaperAirplaneIcon />}
                              onClick={onMessageOpen}
                            >
                              Send Message
                            </Button>
                          </HStack>
                        </CardBody>
                      </Card>
                    )}

                    {!selectedChannel ? (
                      <Alert status="info">
                        <AlertIcon />
                        Please select a channel from the Channels tab to view messages.
                      </Alert>
                    ) : (
                      <Card>
                        <CardBody>
                          <VStack spacing={4} align="stretch">
                            {messages.map((message) => (
                              <Box key={message.ts} p={4} borderWidth="1px" borderRadius="md">
                                <HStack spacing={3} align="start">
                                  <Avatar
                                    size="sm"
                                    name={message.user_name}
                                    src={message.user_image}
                                  />
                                  <VStack align="start" spacing={1} flex={1}>
                                    <HStack spacing={2}>
                                      <Text fontWeight="medium">{message.user_name}</Text>
                                      <Text fontSize="xs" color="gray.500">
                                        {formatTimestamp(message.ts)}
                                      </Text>
                                      {message.edited && (
                                        <Text fontSize="xs" color="gray.400">(edited)</Text>
                                      )}
                                    </HStack>
                                    <Text whiteSpace="pre-wrap">{message.text}</Text>
                                    {message.has_files && (
                                      <HStack spacing={2} mt={2}>
                                        {message.files.map((file, idx) => (
                                          <Tag key={idx} size="sm" colorScheme="blue">
                                            <FileIcon mr={1} />
                                            {file.name}
                                          </Tag>
                                        ))}
                                      </HStack>
                                    )}
                                    {message.has_reactions && (
                                      <HStack spacing={2} mt={2}>
                                        {message.reactions.map((reaction, idx) => (
                                          <Tag key={idx} size="sm" colorScheme="orange">
                                            <ReactionsIcon mr={1} />
                                            {reaction.name} ({reaction.count})
                                          </Tag>
                                        ))}
                                      </HStack>
                                    )}
                                    {message.has_thread && (
                                      <Text fontSize="sm" color="blue.600" mt={2}>
                                        <ThreadIcon mr={1} />
                                        {message.reply_count} replies
                                      </Text>
                                    )}
                                  </VStack>
                                </HStack>
                              </Box>
                            ))}
                          </VStack>
                        </CardBody>
                      </Card>
                    )}
                  </VStack>
                </TabPanel>

                {/* Files Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Button
                        colorScheme="purple"
                        leftIcon={<RepeatIcon />}
                        onClick={loadFiles}
                        isLoading={loading.files}
                      >
                        Refresh Files
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                          {files.map((file) => (
                            <Card key={file.id} variant="outline">
                              <CardBody>
                                <VStack spacing={3} align="start">
                                  <HStack>
                                    <Text fontSize="2xl">{getFileIcon(file)}</Text>
                                    <VStack align="start" spacing={0} flex={1}>
                                      <Text fontWeight="medium" noOfLines={1}>
                                        {file.name}
                                      </Text>
                                      <Text fontSize="sm" color="gray.600">
                                        {file.pretty_type}
                                      </Text>
                                    </VStack>
                                  </HStack>
                                  <HStack justify="space-between" width="100%">
                                    <Text fontSize="sm" color="gray.500">
                                      {formatDate(file.timestamp.toString())}
                                    </Text>
                                    <Text fontSize="sm" color="gray.500">
                                      {file.size_mb} MB
                                    </Text>
                                  </HStack>
                                  <HStack spacing={2}>
                                    <Button
                                      size="sm"
                                      colorScheme="blue"
                                      leftIcon={<ExternalLinkIcon />}
                                      onClick={() => window.open(file.permalink, "_blank")}
                                    >
                                      Open
                                    </Button>
                                    {file.url_private_download && (
                                      <Button
                                        size="sm"
                                        colorScheme="green"
                                        leftIcon={<DownloadIcon />}
                                        onClick={() => window.open(file.url_private_download, "_blank")}
                                      >
                                        Download
                                      </Button>
                                    )}
                                  </HStack>
                                </VStack>
                              </CardBody>
                            </Card>
                          ))}
                        </SimpleGrid>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Search Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search messages across all channels..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            searchMessages();
                          }
                        }}
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
                          {searchResults.map((result: any, index: number) => (
                            <Box key={index} p={4} borderWidth="1px" borderRadius="md">
                              <VStack spacing={3} align="start">
                                <HStack spacing={2}>
                                  <Text fontSize="sm" color="blue.600">
                                    #{result.channel_name}
                                  </Text>
                                  <Text fontSize="xs" color="gray.500">
                                    {formatTimestamp(result.ts)}
                                  </Text>
                                </HStack>
                                <Text noOfLines={3}>{result.text}</Text>
                                {result.user_name && (
                                  <HStack spacing={2}>
                                    <Avatar size="xs" name={result.user_name} />
                                    <Text fontSize="sm">{result.user_name}</Text>
                                  </HStack>
                                )}
                              </VStack>
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

        {/* Send Message Modal */}
        <Modal isOpen={isMessageOpen} onClose={onMessageClose}>
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Send Message</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Channel</FormLabel>
                  <Select
                    value={selectedChannel}
                    onChange={(e) => setSelectedChannel(e.target.value)}
                    placeholder="Select channel"
                  >
                    {channels
                      .filter(c => !c.is_im && !c.is_archived)
                      .map((channel) => (
                        <option key={channel.id} value={channel.id}>
                          {channel.name}
                        </option>
                      ))}
                  </Select>
                </FormControl>
                <FormControl>
                  <FormLabel>Message</FormLabel>
                  <Textarea
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    placeholder="Type your message..."
                    rows={4}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button variant="outline" onClick={onMessageClose}>
                Cancel
              </Button>
              <Button
                colorScheme="purple"
                onClick={sendMessage}
                isLoading={loading.send}
                disabled={!selectedChannel || !messageText.trim()}
              >
                Send Message
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default SlackIntegration;