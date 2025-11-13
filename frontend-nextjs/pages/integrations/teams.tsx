/**
 * Microsoft Teams Integration Page
 * Complete Teams integration with comprehensive messaging and collaboration features
 */

import React, { useState, useEffect } from "react";
import {
  Box,
  Card,
  CardHeader,
  CardBody,
  Heading,
  Button,
  Input,
  FormLabel,
  Textarea,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Badge,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Select,
  VStack,
  HStack,
  Text,
  Spinner,
  IconButton,
  useToast,
  useColorModeValue,
} from "@chakra-ui/react";
import {
  SettingsIcon,
  CheckCircleIcon,
  WarningIcon,
  RepeatIcon,
  AddIcon,
  EditIcon,
  DeleteIcon,
  ViewIcon,
  SearchIcon,
  MessageIcon,
  CalendarIcon,
  AttachmentIcon,
  EmailIcon,
  PhoneIcon,
  TimeIcon,
} from "@chakra-ui/icons";

interface TeamsChannel {
  id: string;
  name: string;
  description: string;
  memberCount: number;
  lastActivity: string;
  isPrivate: boolean;
}

interface TeamsMessage {
  id: string;
  content: string;
  sender: string;
  timestamp: string;
  channel: string;
  type: "text" | "file" | "meeting";
  reactions: number;
}

interface TeamsMeeting {
  id: string;
  title: string;
  startTime: string;
  endTime: string;
  organizer: string;
  participants: string[];
  status: "scheduled" | "in-progress" | "completed" | "cancelled";
}

interface TeamsStatus {
  service: string;
  status: "connected" | "disconnected" | "error";
  timestamp: string;
  channels: number;
  messages: number;
  meetings: number;
}

const TeamsIntegration: React.FC = () => {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<TeamsStatus | null>(null);
  const [channels, setChannels] = useState<TeamsChannel[]>([]);
  const [messages, setMessages] = useState<TeamsMessage[]>([]);
  const [meetings, setMeetings] = useState<TeamsMeeting[]>([]);
  const [activeTab, setActiveTab] = useState("channels");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedChannel, setSelectedChannel] = useState<string>("");
  const [messageContent, setMessageContent] = useState("");

  const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const TEAMS_OAUTH_URL = `${API_BASE_URL}/api/v1/teams/oauth`;

  const bgColor = useColorModeValue("gray.50", "gray.900");
  const borderColor = useColorModeValue("gray.200", "gray.700");
  const cardBg = useColorModeValue("white", "gray.800");

  const loadStatus = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/teams/status`);
      const data = await response.json();

      if (data.status === "connected") {
        setStatus(data);
        toast({
          title: "Teams Status Loaded",
          description: "Successfully connected to Microsoft Teams",
          status: "success",
          duration: 3000,
          isClosable: true,
        });
      } else {
        setStatus(data);
        toast({
          title: "Teams Disconnected",
          description: "Please connect your Microsoft Teams account",
          status: "warning",
          duration: 5000,
          isClosable: true,
        });
      }
    } catch (error) {
      console.error("Error loading Teams status:", error);
      toast({
        title: "Error Loading Teams Status",
        description: "Failed to connect to Microsoft Teams",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const loadChannels = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/teams/channels`);
      const data = await response.json();
      setChannels(data.channels || []);
    } catch (error) {
      console.error("Error loading channels:", error);
      toast({
        title: "Error Loading Channels",
        description: "Failed to load Teams channels",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const loadMessages = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/teams/messages`);
      const data = await response.json();
      setMessages(data.messages || []);
    } catch (error) {
      console.error("Error loading messages:", error);
      toast({
        title: "Error Loading Messages",
        description: "Failed to load Teams messages",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const loadMeetings = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/teams/meetings`);
      const data = await response.json();
      setMeetings(data.meetings || []);
    } catch (error) {
      console.error("Error loading meetings:", error);
      toast({
        title: "Error Loading Meetings",
        description: "Failed to load Teams meetings",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const initiateOAuth = async () => {
    setLoading(true);
    try {
      const response = await fetch(TEAMS_OAUTH_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ user_id: "current_user" }),
      });

      const data = await response.json();

      if (data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        throw new Error("No authentication URL received");
      }
    } catch (error) {
      console.error("Error initiating OAuth:", error);
      toast({
        title: "OAuth Initiation Failed",
        description: "Failed to start Microsoft Teams authentication",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!messageContent.trim() || !selectedChannel) {
      toast({
        title: "Missing Information",
        description: "Please select a channel and enter a message",
        status: "warning",
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/teams/messages/send`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            channel_id: selectedChannel,
            content: messageContent,
          }),
        },
      );

      const data = await response.json();

      if (data.success) {
        toast({
          title: "Message Sent",
          description: "Successfully sent message to Teams",
          status: "success",
          duration: 3000,
          isClosable: true,
        });
        setMessageContent("");
        loadMessages();
      } else {
        throw new Error(data.error || "Failed to send message");
      }
    } catch (error) {
      console.error("Error sending message:", error);
      toast({
        title: "Message Send Failed",
        description: "Failed to send message to Teams",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const searchMessages = async () => {
    if (!searchQuery.trim()) {
      toast({
        title: "Empty Search",
        description: "Please enter a search query",
        status: "warning",
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/teams/messages/search`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query: searchQuery,
          }),
        },
      );

      const data = await response.json();
      setMessages(data.messages || []);

      toast({
        title: "Search Complete",
        description: `Found ${data.messages?.length || 0} messages`,
        status: "success",
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error("Error searching messages:", error);
      toast({
        title: "Search Failed",
        description: "Failed to search Teams messages",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  useEffect(() => {
    if (status?.status === "connected") {
      loadChannels();
      loadMessages();
      loadMeetings();
    }
  }, [status]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "connected":
        return "green";
      case "disconnected":
        return "yellow";
      case "error":
        return "red";
      default:
        return "gray";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "connected":
        return CheckCircleIcon;
      case "disconnected":
        return WarningIcon;
      case "error":
        return WarningIcon;
      default:
        return WarningIcon;
    }
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <Heading size="2xl">Microsoft Teams Integration</Heading>
          <Text color="gray.600" fontSize="lg">
            Complete Teams integration with messaging, meetings, and
            collaboration features
          </Text>

          {/* Status Card */}
          <Card bg={cardBg} border="1px" borderColor={borderColor} w="100%">
            <CardHeader>
              <HStack justify="space-between">
                <Heading size="md">Connection Status</Heading>
                <IconButton
                  aria-label="Refresh status"
                  icon={<RepeatIcon />}
                  onClick={loadStatus}
                  isLoading={loading}
                />
              </HStack>
            </CardHeader>
            <CardBody>
              {status ? (
                <VStack align="start" spacing={4}>
                  <HStack>
                    <Badge
                      colorScheme={getStatusColor(status.status)}
                      fontSize="md"
                      px={3}
                      py={1}
                    >
                      {status.status.toUpperCase()}
                    </Badge>
                    <Text fontSize="sm" color="gray.600">
                      Last updated:{" "}
                      {new Date(status.timestamp).toLocaleString()}
                    </Text>
                  </HStack>

                  <HStack spacing={6}>
                    <VStack align="start" spacing={1}>
                      <Text fontWeight="bold">Channels</Text>
                      <Text fontSize="xl">{status.channels}</Text>
                    </VStack>
                    <VStack align="start" spacing={1}>
                      <Text fontWeight="bold">Messages</Text>
                      <Text fontSize="xl">{status.messages}</Text>
                    </VStack>
                    <VStack align="start" spacing={1}>
                      <Text fontWeight="bold">Meetings</Text>
                      <Text fontSize="xl">{status.meetings}</Text>
                    </VStack>
                  </HStack>

                  {status.status !== "connected" && (
                    <Button
                      colorScheme="blue"
                      onClick={initiateOAuth}
                      isLoading={loading}
                      leftIcon={<SettingsIcon />}
                    >
                      Connect Microsoft Teams
                    </Button>
                  )}
                </VStack>
              ) : (
                <HStack>
                  <Spinner size="sm" />
                  <Text>Loading Teams status...</Text>
                </HStack>
              )}
            </CardBody>
          </Card>
        </VStack>

        {/* Main Content */}
        <Card bg={cardBg} border="1px" borderColor={borderColor}>
          <CardHeader>
            <Tabs
              variant="enclosed"
              onChange={(index) =>
                setActiveTab(
                  ["channels", "messages", "meetings"][index] || "channels",
                )
              }
            >
              <TabList>
                <Tab>
                  <HStack>
                    <MessageIcon />
                    <Text>Channels</Text>
                    <Badge colorScheme="blue" ml={2}>
                      {channels.length}
                    </Badge>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <MessageIcon />
                    <Text>Messages</Text>
                    <Badge colorScheme="green" ml={2}>
                      {messages.length}
                    </Badge>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <CalendarIcon />
                    <Text>Meetings</Text>
                    <Badge colorScheme="purple" ml={2}>
                      {meetings.length}
                    </Badge>
                  </HStack>
                </Tab>
              </TabList>
            </Tabs>
          </CardHeader>

          <CardBody>
            <TabPanels>
              {/* Channels Tab */}
              <TabPanel>
                <VStack spacing={4} align="stretch">
                  {channels.length > 0 ? (
                    channels.map((channel) => (
                      <Card key={channel.id} variant="outline">
                        <CardBody>
                          <HStack justify="space-between">
                            <VStack align="start" spacing={1}>
                              <Heading size="sm">{channel.name}</Heading>
                              <Text color="gray.600" fontSize="sm">
                                {channel.description}
                              </Text>
                              <HStack spacing={4}>
                                <Text fontSize="sm" color="gray.500">
                                  {channel.memberCount} members
                                </Text>
                                <Text fontSize="sm" color="gray.500">
                                  Last activity:{" "}
                                  {new Date(
                                    channel.lastActivity,
                                  ).toLocaleString()}
                                </Text>
                                {channel.isPrivate && (
                                  <Badge colorScheme="orange" fontSize="xs">
                                    Private
                                  </Badge>
                                )}
                              </HStack>
                            </VStack>
                            <Button
                              size="sm"
                              onClick={() => setSelectedChannel(channel.id)}
                              colorScheme={
                                selectedChannel === channel.id ? "blue" : "gray"
                              }
                            >
                              Select
                            </Button>
                          </HStack>
                        </CardBody>
                      </Card>
                    ))
                  ) : (
                    <Alert status="info">
                      <AlertIcon />
                      <AlertTitle>No Channels</AlertTitle>
                      <AlertDescription>
                        No Teams channels found. Please connect your account and
                        ensure you have access to Teams channels.
                      </AlertDescription>
                    </Alert>
                  )}
                </VStack>
              </TabPanel>

              {/* Messages Tab */}
              <TabPanel>
                <VStack spacing={4} align="stretch">
                  {/* Search and Send Message */}
                  <Card variant="outline">
                    <CardBody>
                      <VStack spacing={4}>
                        <FormLabel>Send Message to Selected Channel</FormLabel>
                        <Select
                          placeholder="Select a channel"
                          value={selectedChannel}
                          onChange={(e) => setSelectedChannel(e.target.value)}
                        >
                          {channels.map((channel) => (
                            <option key={channel.id} value={channel.id}>
                              {channel.name}
                            </option>
                          ))}
                        </Select>
                        <Textarea
                          placeholder="Type your message here..."
                          value={messageContent}
                          onChange={(e) => setMessageContent(e.target.value)}
                          rows={3}
                        />
                        <Button
                          colorScheme="blue"
                          onClick={sendMessage}
                          isLoading={loading}
                          leftIcon={<MessageIcon />}
                          isDisabled={
                            !selectedChannel || !messageContent.trim()
                          }
                        >
                          Send Message
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>

                  {/* Search Messages */}
                  <Card variant="outline">
                    <CardBody>
                      <VStack spacing={4}>
                        <FormLabel>Search Messages</FormLabel>
                        <HStack w="100%">
                          <Input
                            placeholder="Search messages..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                          />
                          <Button
                            onClick={searchMessages}
                            isLoading={loading}
                            leftIcon={<SearchIcon />}
                          >
                            Search
                          </Button>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>

                  {/* Messages List */}
                  {messages.length > 0 ? (
                    messages.map((message) => (
                      <Card key={message.id} variant="outline">
                        <CardBody>
                          <VStack align="start" spacing={2}>
                            <HStack justify="space-between" w="100%">
                              <Text fontWeight="bold">{message.sender}</Text>
                              <Text fontSize="sm" color="gray.500">
                                {new Date(message.timestamp).toLocaleString()}
                              </Text>
                            </HStack>
                            <Text>{message.content}</Text>
                            <HStack spacing={4}>
                              <Badge colorScheme="blue" fontSize="xs">
                                {message.channel}
                              </Badge>
                              <Badge colorScheme="gray" fontSize="xs">
                                {message.type}
                              </Badge>
                              {message.reactions > 0 && (
                                <Badge colorScheme="green" fontSize="xs">
                                  {message.reactions} reactions
                                </Badge>
                              )}
                            </HStack>
                          </VStack>
                        </CardBody>
                      </Card>
                    ))
                  ) : (
                    <Alert status="info">
                      <AlertIcon />
                      <AlertTitle>No Messages</AlertTitle>
                      <AlertDescription>
                        No Teams messages found. Try sending a message or
                        searching for existing messages.
                      </AlertDescription>
                    </Alert>
                  )}
                </VStack>
              </TabPanel>

              {/* Meetings Tab */}
              <TabPanel>
                <VStack spacing={4} align="stretch">
                  {meetings.length > 0 ? (
                    meetings.map((meeting) => (
                      <Card key={meeting.id} variant="outline">
                        <CardBody>
                          <VStack align="start" spacing={2}>
                            <HStack justify="space-between" w="100%">
                              <Heading size="sm">{meeting.title}</Heading>
                              <Badge
                                colorScheme={
                                  meeting.status === "scheduled"
                                    ? "blue"
                                    : meeting.status === "in-progress"
                                      ? "green"
                                      : meeting.status === "completed"
                                        ? "gray"
                                        : "red"
                                }
                              >
                                {meeting.status}
                              </Badge>
                            </HStack>
                            <HStack spacing={4}>
                              <Text fontSize="sm" color="gray.600">
                                <strong>Start:</strong>{" "}
                                {new Date(meeting.startTime).toLocaleString()}
                              </Text>
                              <Text fontSize="sm" color="gray.600">
                                <strong>End:</strong>{" "}
                                {new Date(meeting.endTime).toLocaleString()}
                              </Text>
                            </HStack>
                            <Text fontSize="sm" color="gray.600">
                              <strong>Organizer:</strong> {meeting.organizer}
                            </Text>
                            <Text fontSize="sm" color="gray.600">
                              <strong>Participants:</strong>{" "}
                              {meeting.participants.join(", ")}
                            </Text>
                          </VStack>
                        </CardBody>
                      </Card>
                    ))
                  ) : (
                    <Alert status="info">
                      <AlertIcon />
                      <AlertTitle>No Meetings</AlertTitle>
                      <AlertDescription>
                        No Teams meetings found. Connect your account and check
                        your calendar.
                      </AlertDescription>
                    </Alert>
                  )}
                </VStack>
              </TabPanel>
            </TabPanels>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};

export default TeamsIntegration;
