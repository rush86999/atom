/**
 * Slack Integration Page
 * Complete Slack communication and collaboration integration
 */

import React, { useState, useEffect, useCallback } from "react";
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
  Flex,
  Spacer,
  Input,
  InputGroup,
  InputLeftElement,
  Select,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Textarea,
  useDisclosure,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
  Tag,
  TagLabel,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Avatar,
  AvatarGroup,
  Spinner,
} from "@chakra-ui/react";
import {
  ChatIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  ArrowForwardIcon,
  AddIcon,
  SearchIcon,
  SettingsIcon,
  RepeatIcon,
  TimeIcon,
  StarIcon,
  EmailIcon,
  PhoneIcon,
} from "@chakra-ui/icons";

interface SlackChannel {
  id: string;
  name: string;
  purpose: string;
  num_members: number;
  is_archived: boolean;
  is_general: boolean;
  created: number;
  creator: string;
  is_private: boolean;
}

interface SlackMessage {
  team: string;
  user: string;
  user_profile: {
    real_name: string;
    display_name: string;
    image_24: string;
    image_32: string;
    image_48: string;
    image_72: string;
    image_192: string;
    image_512: string;
    image_102: string;
  };
  text: string;
  ts: string;
  attachments: Array<any>;
  reactions: Array<{
    name: string;
    count: number;
    users: string[];
  }>;
  thread_ts?: string;
  reply_count?: number;
  replies?: Array<{
    user: string;
    ts: string;
  }>;
  files?: Array<any>;
  upload?: boolean;
}

interface SlackUser {
  id: string;
  name: string;
  real_name: string;
  display_name: string;
  email?: string;
  phone?: string;
  title?: string;
  is_admin: boolean;
  is_owner: boolean;
  is_bot: boolean;
  deleted: boolean;
  profile: {
    real_name: string;
    display_name: string;
    real_name_normalized: string;
    display_name_normalized: string;
    email: string;
    image_24: string;
    image_32: string;
    image_48: string;
    image_72: string;
    image_192: string;
    image_512: string;
    image_1024: string;
    image_102: string;
  };
}

interface SlackWorkspace {
  id: string;
  name: string;
  domain: string;
  email_domain: string;
  icon: {
    image_34: string;
    image_44: string;
    image_68: string;
    image_88: string;
    image_102: string;
    image_132: string;
    image_230: string;
    image_default: boolean;
  };
}

const SlackIntegration: React.FC = () => {
  const [channels, setChannels] = useState<SlackChannel[]>([]);
  const [messages, setMessages] = useState<SlackMessage[]>([]);
  const [users, setUsers] = useState<SlackUser[]>([]);
  const [workspace, setWorkspace] = useState<SlackWorkspace | null>(null);
  const [loading, setLoading] = useState({
    channels: false,
    messages: false,
    users: false,
    workspace: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedChannel, setSelectedChannel] = useState("");
  const [selectedUser, setSelectedUser] = useState("");
  const [messageText, setMessageText] = useState("");

  const {
    isOpen: isMessageOpen,
    onOpen: onMessageOpen,
    onClose: onMessageClose,
  } = useDisclosure();
  const {
    isOpen: isChannelOpen,
    onOpen: onChannelOpen,
    onClose: onChannelClose,
  } = useDisclosure();

  const [newMessage, setNewMessage] = useState({
    channel: "",
    text: "",
  });

  const [newChannel, setNewChannel] = useState({
    name: "",
    purpose: "",
    is_private: false,
  });

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Load Slack data

  const loadWorkspace = useCallback(async () => {
    setLoading((prev) => ({ ...prev, workspace: true }));
    try {
      const response = await fetch("/api/integrations/slack/workspace", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setWorkspace(data.data?.workspace || null);
      }
    } catch (error) {
      console.error("Failed to load workspace:", error);
    } finally {
      setLoading((prev) => ({ ...prev, workspace: false }));
    }
  }, []);

  const loadChannels = useCallback(async () => {
    setLoading((prev) => ({ ...prev, channels: true }));
    try {
      const response = await fetch("/api/integrations/slack/channels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setChannels(data.data?.channels || []);
      }
    } catch (error) {
      console.error("Failed to load channels:", error);
      toast({
        title: "Error",
        description: "Failed to load channels from Slack",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, channels: false }));
    }
  }, [toast]);

  const loadMessages = async (channelId: string) => {
    if (!channelId) return;

    setLoading((prev) => ({ ...prev, messages: true }));
    try {
      const response = await fetch("/api/integrations/slack/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          channel: channelId,
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMessages(data.data?.messages || []);
      }
    } catch (error) {
      console.error("Failed to load messages:", error);
    } finally {
      setLoading((prev) => ({ ...prev, messages: false }));
    }
  };

  const loadUsers = useCallback(async () => {
    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/slack/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setUsers(data.data?.users || []);
      }
    } catch (error) {
      console.error("Failed to load users:", error);
    } finally {
      setLoading((prev) => ({ ...prev, users: false }));
    }
  }, []);

  // Check connection status
  const checkConnection = useCallback(async () => {
    try {
      const response = await fetch("/api/integrations/slack/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadWorkspace();
        loadChannels();
        loadUsers();
      } else {
        setConnected(false);
        setHealthStatus("error");
      }
    } catch (error) {
      console.error("Health check failed:", error);
      setConnected(false);
      setHealthStatus("error");
    }
  }, [loadWorkspace, loadChannels, loadUsers]);

  const sendMessage = async () => {
    if (!newMessage.channel || !newMessage.text) return;

    try {
      const response = await fetch("/api/integrations/slack/messages/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          channel: newMessage.channel,
          text: newMessage.text,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Message sent successfully",
          status: "success",
          duration: 3000,
        });
        onMessageClose();
        setNewMessage({ channel: "", text: "" });
        if (newMessage.channel === selectedChannel) {
          loadMessages(selectedChannel);
        }
      }
    } catch (error) {
      console.error("Failed to send message:", error);
      toast({
        title: "Error",
        description: "Failed to send message",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createChannel = async () => {
    if (!newChannel.name) return;

    try {
      const response = await fetch("/api/integrations/slack/channels/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          name: newChannel.name,
          purpose: newChannel.purpose,
          is_private: newChannel.is_private,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Channel created successfully",
          status: "success",
          duration: 3000,
        });
        onChannelClose();
        setNewChannel({ name: "", purpose: "", is_private: false });
        loadChannels();
      }
    } catch (error) {
      console.error("Failed to create channel:", error);
      toast({
        title: "Error",
        description: "Failed to create channel",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredChannels = channels.filter(
    (channel) =>
      channel.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      channel.purpose.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredUsers = users.filter(
    (user) =>
      user.real_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (user.email &&
        user.email.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  const filteredMessages = messages.filter(
    (message) =>
      message.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (message.user_profile?.display_name || "")
        .toLowerCase()
        .includes(searchQuery.toLowerCase()),
  );

  // Stats calculations
  const totalChannels = channels.length;
  const privateChannels = channels.filter((ch) => ch.is_private).length;
  const totalUsers = users.length;
  const activeUsers = users.filter((u) => !u.deleted && !u.is_bot).length;
  const totalMessages = messages.length;

  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  useEffect(() => {
    if (connected) {
      loadWorkspace();
      loadChannels();
      loadUsers();
    }
  }, [connected, loadChannels, loadWorkspace, loadUsers]);

  useEffect(() => {
    if (selectedChannel) {
      loadMessages(selectedChannel);
    }
  }, [selectedChannel]);

  const formatDate = (timestamp: string): string => {
    return new Date(parseFloat(timestamp) * 1000).toLocaleString();
  };

  const getStatusColor = (channel: SlackChannel): string => {
    if (channel.is_archived) return "gray";
    if (channel.is_private) return "purple";
    if (channel.is_general) return "green";
    return "blue";
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
                Team communication and collaboration platform
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
                <WarningTwoIcon mr={1} />
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

          {workspace && (
            <HStack spacing={4}>
              <Avatar src={workspace.icon.image_102} name={workspace.name} />
              <Text fontWeight="bold">{workspace.name}</Text>
              <Text color="gray.600">({workspace.domain})</Text>
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
                    Connect your Slack workspace to start managing conversations
                    and teams
                  </Text>
                </VStack>
                <Button
                  colorScheme="purple"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/slack/auth/start")
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
                    <StatHelpText>{privateChannels} private</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Users</StatLabel>
                    <StatNumber>{activeUsers}</StatNumber>
                    <StatHelpText>{totalUsers} total</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Messages</StatLabel>
                    <StatNumber>{totalMessages}</StatNumber>
                    <StatHelpText>In selected channel</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Workspace</StatLabel>
                    <StatNumber>{workspace?.name || "Unknown"}</StatNumber>
                    <StatHelpText>Connected</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Channels</Tab>
                <Tab>Messages</Tab>
                <Tab>Users</Tab>
                <Tab>Workspace</Tab>
              </TabList>

              <TabPanels>
                {/* Channels Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <InputGroup>
                        <InputLeftElement pointerEvents="none">
                          <SearchIcon color="gray.400" />
                        </InputLeftElement>
                        <Input
                          placeholder="Search channels..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                      </InputGroup>
                      <Spacer />
                      <Button
                        colorScheme="purple"
                        leftIcon={<AddIcon />}
                        onClick={onChannelOpen}
                      >
                        Create Channel
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {loading.channels ? (
                            <Spinner size="xl" />
                          ) : (
                            filteredChannels.map((channel) => (
                              <HStack
                                key={channel.id}
                                p={4}
                                borderWidth="1px"
                                borderRadius="md"
                                _hover={{ bg: "gray.50" }}
                                cursor="pointer"
                                onClick={() => {
                                  setSelectedChannel(channel.id);
                                  loadMessages(channel.id);
                                }}
                              >
                                <VStack align="start" spacing={1} flex={1}>
                                  <HStack>
                                    <Text fontWeight="bold">
                                      #{channel.name}
                                    </Text>
                                    <Tag
                                      colorScheme={getStatusColor(channel)}
                                      size="sm"
                                    >
                                      {channel.is_private
                                        ? "Private"
                                        : channel.is_general
                                          ? "General"
                                          : "Public"}
                                    </Tag>
                                    {channel.is_archived && (
                                      <Tag colorScheme="gray" size="sm">
                                        Archived
                                      </Tag>
                                    )}
                                  </HStack>
                                  <Text fontSize="sm" color="gray.600">
                                    {channel.purpose || "No purpose"}
                                  </Text>
                                  <Text fontSize="xs" color="gray.500">
                                    {channel.num_members} members
                                  </Text>
                                </VStack>
                                <ArrowForwardIcon color="gray.400" />
                              </HStack>
                            ))
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Messages Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Select channel"
                        value={selectedChannel}
                        onChange={(e) => setSelectedChannel(e.target.value)}
                        width="300px"
                      >
                        {channels.map((channel) => (
                          <option key={channel.id} value={channel.id}>
                            #{channel.name}
                          </option>
                        ))}
                      </Select>
                      <InputGroup>
                        <InputLeftElement pointerEvents="none">
                          <SearchIcon color="gray.400" />
                        </InputLeftElement>
                        <Input
                          placeholder="Search messages..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                      </InputGroup>
                      <Spacer />
                      <Button
                        colorScheme="purple"
                        leftIcon={<AddIcon />}
                        onClick={onMessageOpen}
                        disabled={!selectedChannel}
                      >
                        Send Message
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack
                          spacing={4}
                          align="stretch"
                          maxH="600px"
                          overflowY="auto"
                        >
                          {loading.messages ? (
                            <Spinner size="xl" />
                          ) : selectedChannel ? (
                            filteredMessages.map((message) => (
                              <HStack
                                key={message.ts}
                                p={4}
                                borderWidth="1px"
                                borderRadius="md"
                                align="start"
                                spacing={4}
                              >
                                <Avatar
                                  src={message.user_profile?.image_48}
                                  name={message.user_profile?.display_name}
                                  size="sm"
                                />
                                <VStack align="start" spacing={1} flex={1}>
                                  <HStack>
                                    <Text fontWeight="bold">
                                      {message.user_profile?.display_name ||
                                        "Unknown"}
                                    </Text>
                                    <Text fontSize="xs" color="gray.500">
                                      {formatDate(message.ts)}
                                    </Text>
                                  </HStack>
                                  <Text fontSize="sm">{message.text}</Text>
                                  {message.reactions &&
                                    message.reactions.length > 0 && (
                                      <HStack spacing={2}>
                                        {message.reactions.map(
                                          (reaction, idx) => (
                                            <Tag key={idx} size="sm">
                                              {reaction.name} {reaction.count}
                                            </Tag>
                                          ),
                                        )}
                                      </HStack>
                                    )}
                                </VStack>
                              </HStack>
                            ))
                          ) : (
                            <Text color="gray.500" textAlign="center" py={8}>
                              Select a channel to view messages
                            </Text>
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Users Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <InputGroup>
                        <InputLeftElement pointerEvents="none">
                          <SearchIcon color="gray.400" />
                        </InputLeftElement>
                        <Input
                          placeholder="Search users..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                      </InputGroup>
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {loading.users ? (
                            <Spinner size="xl" />
                          ) : (
                            filteredUsers.map((user) => (
                              <HStack
                                key={user.id}
                                p={4}
                                borderWidth="1px"
                                borderRadius="md"
                                _hover={{ bg: "gray.50" }}
                              >
                                <Avatar
                                  src={user.profile.image_48}
                                  name={user.display_name}
                                  size="md"
                                />
                                <VStack align="start" spacing={1} flex={1}>
                                  <HStack>
                                    <Text fontWeight="bold">
                                      {user.real_name}
                                    </Text>
                                    {user.is_admin && (
                                      <Tag colorScheme="red" size="sm">
                                        Admin
                                      </Tag>
                                    )}
                                    {user.is_owner && (
                                      <Tag colorScheme="orange" size="sm">
                                        Owner
                                      </Tag>
                                    )}
                                    {user.is_bot && (
                                      <Tag colorScheme="blue" size="sm">
                                        Bot
                                      </Tag>
                                    )}
                                  </HStack>
                                  <Text fontSize="sm" color="gray.600">
                                    @{user.name}
                                  </Text>
                                  {user.title && (
                                    <Text fontSize="xs" color="gray.500">
                                      {user.title}
                                    </Text>
                                  )}
                                  {user.profile.email && (
                                    <HStack>
                                      <EmailIcon boxSize={3} color="gray.400" />
                                      <Text fontSize="xs" color="gray.500">
                                        {user.profile.email}
                                      </Text>
                                    </HStack>
                                  )}
                                </VStack>
                              </HStack>
                            ))
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Workspace Tab */}
                <TabPanel>
                  <Card>
                    <CardBody>
                      <VStack spacing={6} align="stretch">
                        {workspace ? (
                          <>
                            <HStack spacing={6}>
                              <Avatar
                                src={workspace.icon.image_102}
                                name={workspace.name}
                                size="xl"
                              />
                              <VStack align="start" spacing={2}>
                                <Heading size="lg">{workspace.name}</Heading>
                                <Text color="gray.600">
                                  {workspace.domain}.slack.com
                                </Text>
                                {workspace.email_domain && (
                                  <Text fontSize="sm" color="gray.500">
                                    Email domain: {workspace.email_domain}
                                  </Text>
                                )}
                              </VStack>
                            </HStack>

                            <Divider />

                            <SimpleGrid
                              columns={{ base: 1, md: 3 }}
                              spacing={6}
                            >
                              <Stat>
                                <StatLabel>Total Channels</StatLabel>
                                <StatNumber>{totalChannels}</StatNumber>
                              </Stat>
                              <Stat>
                                <StatLabel>Total Users</StatLabel>
                                <StatNumber>{totalUsers}</StatNumber>
                              </Stat>
                              <Stat>
                                <StatLabel>Active Users</StatLabel>
                                <StatNumber>{activeUsers}</StatNumber>
                              </Stat>
                            </SimpleGrid>
                          </>
                        ) : (
                          <Text color="gray.500">
                            Loading workspace information...
                          </Text>
                        )}
                      </VStack>
                    </CardBody>
                  </Card>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Send Message Modal */}
            <Modal isOpen={isMessageOpen} onClose={onMessageClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Send Message</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Channel</FormLabel>
                      <Select
                        value={newMessage.channel}
                        onChange={(e) =>
                          setNewMessage({
                            ...newMessage,
                            channel: e.target.value,
                          })
                        }
                      >
                        <option value="">Select a channel</option>
                        {channels.map((channel) => (
                          <option key={channel.id} value={channel.id}>
                            #{channel.name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Message</FormLabel>
                      <Textarea
                        placeholder="Type your message..."
                        value={newMessage.text}
                        onChange={(e) =>
                          setNewMessage({
                            ...newMessage,
                            text: e.target.value,
                          })
                        }
                        rows={4}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onMessageClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="purple"
                    onClick={sendMessage}
                    disabled={!newMessage.channel || !newMessage.text}
                  >
                    Send Message
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Channel Modal */}
            <Modal isOpen={isChannelOpen} onClose={onChannelClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Channel</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Channel Name</FormLabel>
                      <Input
                        placeholder="channel-name"
                        value={newChannel.name}
                        onChange={(e) =>
                          setNewChannel({
                            ...newChannel,
                            name: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Purpose</FormLabel>
                      <Textarea
                        placeholder="What's this channel about?"
                        value={newChannel.purpose}
                        onChange={(e) =>
                          setNewChannel({
                            ...newChannel,
                            purpose: e.target.value,
                          })
                        }
                        rows={3}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onChannelClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="purple"
                    onClick={createChannel}
                    disabled={!newChannel.name}
                  >
                    Create Channel
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </>
        )}
      </VStack>
    </Box>
  );
};

export default SlackIntegration;
