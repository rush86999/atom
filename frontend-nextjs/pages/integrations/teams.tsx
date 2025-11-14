/**
 * Microsoft Teams Integration Page
 * Complete Microsoft Teams collaboration and communication integration
 */

import React, { useState, useEffect } from "react";
import {
  Box as ChakraBox,
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
  Spinner,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Checkbox,
  Link,
} from "@chakra-ui/react";
import {
  SettingsIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  ArrowForwardIcon,
  AddIcon,
  SearchIcon,
  RepeatIcon,
  TimeIcon,
  StarIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  ChatIcon,
  EmailIcon,
  CalendarIcon,
  PhoneIcon,
  GenericAvatarIcon,
  AttachmentIcon,
  ExternalLinkIcon,
  LockIcon,
  UnlockIcon,
} from "@chakra-ui/icons";

interface MSTeams {
  id: string;
  displayName: string;
  description: string;
  createdDateTime: string;
  updatedDateTime: string;
  classification?: string;
  specialization: string;
  visibility: string;
  webUrl: string;
  internalId: string;
  isArchived: boolean;
  memberSettings?: {
    allowCreateUpdateRemoveChannels: boolean;
    allowAddRemoveApps: boolean;
    allowCreateUpdateRemoveTabs: boolean;
    allowCreateUpdateRemoveConnectors: boolean;
  };
  guestSettings?: {
    allowCreateUpdateChannels: boolean;
    allowDeleteChannels: boolean;
  };
  funSettings?: {
    allowGiphy: boolean;
    giphyContentRating: string;
    allowStickersAndMemes: boolean;
  };
}

interface MSTeamsChannel {
  id: string;
  displayName: string;
  description: string;
  createdDateTime: string;
  updatedDateTime: string;
  email: string;
  isFavoriteByDefault: boolean;
  membershipType: string;
  tenant: string;
  webUrl: string;
  filesFolder?: {
    id: string;
    name: string;
    webUrl: string;
  };
  moderatedSettings?: {
    allowNewMessagesFromBotsAndConnectors: boolean;
    allowNewMessagesFromEveryone: boolean;
    blockNewMessagesFromNonMembers: boolean;
  };
  tabs: MSTeamsTab[];
  messages: MSTeamsMessage[];
}

interface MSTeamsMessage {
  id: string;
  messageType: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  conversationId: string;
  from: {
    application?: {
      id: string;
      displayName: string;
    };
    device?: {
      id: string;
      displayName: string;
    };
    user?: {
      id: string;
      displayName: string;
    };
  };
  body: {
    content: string;
    contentType: string;
  };
  attachments?: Array<{
    id: string;
    contentType: string;
    name: string;
    url: string;
  }>;
  mentions?: Array<{
    id: number;
    mentionText: string;
    mentioned: {
      user?: {
        displayName: string;
        id: string;
        userIdentityType: string;
      };
    };
  }>;
  importance?: string;
  locale?: string;
  reactions?: Array<{
    reactionType: string;
    createdDateTime: string;
    user: {
      displayName: string;
      id: string;
    };
  }>;
  replies?: MSTeamsMessage[];
}

interface MSTeamsTab {
  id: string;
  displayName: string;
  teamsAppId: string;
  sortorderindex: string;
  webUrl: string;
  configuration?: {
    entityId: string;
    contentUrl: string;
    removeUrl: string;
    websiteUrl: string;
    suggestedDisplayName: string;
  };
}

interface MSTeamsUser {
  id: string;
  displayName: string;
  givenName?: string;
  surname?: string;
  mail?: string;
  mobilePhone?: string;
  jobTitle?: string;
  officeLocation?: string;
  preferredLanguage?: string;
  userPrincipalName: string;
  accountEnabled: boolean;
  department?: string;
  usageLocation?: string;
  licenseAssignmentStates?: Array<{
    skuId: string;
    disabledPlans?: string[];
    state: string;
  }>;
}

interface MSTeamsMeeting {
  id: string;
  subject?: string;
  body?: {
    contentType: string;
    content: string;
  };
  start: {
    dateTime: string;
    timeZone: string;
  };
  end: {
    dateTime: string;
    timeZone: string;
  };
  location?: {
    displayName: string;
  };
  attendees?: Array<{
    type: string;
    status: {
      response: string;
      time: string;
    };
    emailAddress: {
      name: string;
      address: string;
    };
  }>;
  isOnlineMeeting: boolean;
  onlineMeetingUrl?: string;
  joinUrl?: string;
  conferenceId?: string;
  tollNumber?: string;
  dialinUrl?: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
}

const MSTeamsIntegration: React.FC = () => {
  const [teams, setTeams] = useState<MSTeams[]>([]);
  const [channels, setChannels] = useState<MSTeamsChannel[]>([]);
  const [messages, setMessages] = useState<MSTeamsMessage[]>([]);
  const [meetings, setMeetings] = useState<MSTeamsMeeting[]>([]);
  const [users, setUsers] = useState<MSTeamsUser[]>([]);
  const [userProfile, setUserProfile] = useState<MSTeamsUser | null>(null);
  const [currentTeam, setCurrentTeam] = useState<MSTeams | null>(null);
  const [currentChannel, setCurrentChannel] = useState<MSTeamsChannel | null>(
    null,
  );
  const [loading, setLoading] = useState({
    teams: false,
    channels: false,
    messages: false,
    meetings: false,
    users: false,
    profile: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState("all");

  // Form states
  const [teamForm, setTeamForm] = useState({
    name: "",
    description: "",
    visibility: "private",
    specialization: "none",
    classification: "",
  });

  const [channelForm, setChannelForm] = useState({
    name: "",
    description: "",
    membership_type: "standard",
    is_favorite_by_default: false,
  });

  const [messageForm, setMessageForm] = useState({
    content: "",
    importance: "normal",
    mentioned_users: [] as string[],
  });

  const [meetingForm, setMeetingForm] = useState({
    subject: "",
    body: "",
    start_time: "",
    end_time: "",
    attendees: [] as string[],
    is_online_meeting: true,
  });

  const {
    isOpen: isTeamOpen,
    onOpen: onTeamOpen,
    onClose: onTeamClose,
  } = useDisclosure();
  const {
    isOpen: isChannelOpen,
    onOpen: onChannelOpen,
    onClose: onChannelClose,
  } = useDisclosure();
  const {
    isOpen: isMessageOpen,
    onOpen: onMessageOpen,
    onClose: onMessageClose,
  } = useDisclosure();
  const {
    isOpen: isMeetingOpen,
    onOpen: onMeetingOpen,
    onClose: onMeetingClose,
  } = useDisclosure();

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/teams/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadUserProfile();
        loadTeams();
        loadUsers();
        loadMeetings();
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

  // Load Microsoft Teams data
  const loadUserProfile = async () => {
    setLoading((prev) => ({ ...prev, profile: true }));
    try {
      const response = await fetch("/api/integrations/teams/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setUserProfile(data.data?.profile || null);
      }
    } catch (error) {
      console.error("Failed to load user profile:", error);
    } finally {
      setLoading((prev) => ({ ...prev, profile: false }));
    }
  };

  const loadTeams = async () => {
    setLoading((prev) => ({ ...prev, teams: true }));
    try {
      const response = await fetch("/api/integrations/teams/teams", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setTeams(data.data?.teams || []);
      }
    } catch (error) {
      console.error("Failed to load teams:", error);
      toast({
        title: "Error",
        description: "Failed to load teams from Microsoft Teams",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, teams: false }));
    }
  };

  const loadChannels = async (teamId?: string) => {
    if (!teamId && !currentTeam) return;

    setLoading((prev) => ({ ...prev, channels: true }));
    try {
      const response = await fetch("/api/integrations/teams/channels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          team_id: teamId || currentTeam?.id,
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setChannels(data.data?.channels || []);
      }
    } catch (error) {
      console.error("Failed to load channels:", error);
    } finally {
      setLoading((prev) => ({ ...prev, channels: false }));
    }
  };

  const loadMessages = async (channelId?: string) => {
    if (!channelId && !currentChannel) return;

    setLoading((prev) => ({ ...prev, messages: true }));
    try {
      const response = await fetch("/api/integrations/teams/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          team_id: currentTeam?.id,
          channel_id: channelId || currentChannel?.id,
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

  const loadMeetings = async () => {
    setLoading((prev) => ({ ...prev, meetings: true }));
    try {
      const response = await fetch("/api/integrations/teams/meetings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          start_date: new Date().toISOString(),
          end_date: new Date(
            Date.now() + 30 * 24 * 60 * 60 * 1000,
          ).toISOString(),
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMeetings(data.data?.meetings || []);
      }
    } catch (error) {
      console.error("Failed to load meetings:", error);
    } finally {
      setLoading((prev) => ({ ...prev, meetings: false }));
    }
  };

  const loadUsers = async () => {
    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/teams/users", {
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
  };

  // Create operations
  const createTeam = async () => {
    if (!teamForm.name) return;

    try {
      const response = await fetch("/api/integrations/teams/teams/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          displayName: teamForm.name,
          description: teamForm.description,
          visibility: teamForm.visibility,
          specialization: teamForm.specialization,
          classification: teamForm.classification,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Team created successfully",
          status: "success",
          duration: 3000,
        });
        onTeamClose();
        setTeamForm({
          name: "",
          description: "",
          visibility: "private",
          specialization: "none",
          classification: "",
        });
        loadTeams();
      }
    } catch (error) {
      console.error("Failed to create team:", error);
      toast({
        title: "Error",
        description: "Failed to create team",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createChannel = async () => {
    if (!channelForm.name || !currentTeam) return;

    try {
      const response = await fetch("/api/integrations/teams/channels/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          team_id: currentTeam.id,
          displayName: channelForm.name,
          description: channelForm.description,
          membershipType: channelForm.membership_type,
          isFavoriteByDefault: channelForm.is_favorite_by_default,
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
        setChannelForm({
          name: "",
          description: "",
          membership_type: "standard",
          is_favorite_by_default: false,
        });
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

  const sendMessage = async () => {
    if (!messageForm.content || !currentChannel) return;

    try {
      const response = await fetch("/api/integrations/teams/messages/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          team_id: currentTeam?.id,
          channel_id: currentChannel.id,
          content: messageForm.content,
          importance: messageForm.importance,
          mentions: messageForm.mentioned_users.map((userId) => ({
            id: 0,
            mentionText: `<at id="${userId}">User</at>`,
            mentioned: {
              user: {
                displayName:
                  users.find((u) => u.id === userId)?.displayName || "",
                id: userId,
                userIdentityType: "user",
              },
            },
          })),
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
        setMessageForm({
          content: "",
          importance: "normal",
          mentioned_users: [],
        });
        loadMessages();
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

  const createMeeting = async () => {
    if (
      !meetingForm.subject ||
      !meetingForm.start_time ||
      !meetingForm.end_time
    )
      return;

    try {
      const response = await fetch("/api/integrations/teams/meetings/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          subject: meetingForm.subject,
          body: {
            contentType: "text",
            content: meetingForm.body,
          },
          start: {
            dateTime: meetingForm.start_time,
            timeZone: "UTC",
          },
          end: {
            dateTime: meetingForm.end_time,
            timeZone: "UTC",
          },
          attendees: meetingForm.attendees.map((email) => ({
            type: "required",
            emailAddress: {
              address: email,
              name: email.split("@")[0],
            },
            status: {
              response: "notResponded",
              time: new Date().toISOString(),
            },
          })),
          isOnlineMeeting: meetingForm.is_online_meeting,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Meeting scheduled successfully",
          status: "success",
          duration: 3000,
        });
        onMeetingClose();
        setMeetingForm({
          subject: "",
          body: "",
          start_time: "",
          end_time: "",
          attendees: [],
          is_online_meeting: true,
        });
        loadMeetings();
      }
    } catch (error) {
      console.error("Failed to create meeting:", error);
      toast({
        title: "Error",
        description: "Failed to create meeting",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredTeams = teams.filter(
    (team) =>
      team.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      team.description.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredChannels = channels.filter(
    (channel) =>
      channel.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      channel.description.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredMessages = messages.filter(
    (message) =>
      message.body.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      message.from.user?.displayName
        ?.toLowerCase()
        .includes(searchQuery.toLowerCase()),
  );

  const filteredMeetings = meetings.filter(
    (meeting) =>
      (meeting.subject &&
        meeting.subject.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (meeting.body?.content &&
        meeting.body.content.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  const filteredUsers = users.filter(
    (user) =>
      user.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.mail?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.userPrincipalName.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // Stats calculations
  const totalTeams = teams.length;
  const totalChannels = channels.length;
  const totalMessages = messages.length;
  const totalMeetings = meetings.length;
  const upcomingMeetings = meetings.filter(
    (m) => new Date(m.start.dateTime) > new Date(),
  ).length;
  const totalUsers = users.length;
  const activeUsers = users.filter((u) => u.accountEnabled).length;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadUserProfile();
      loadTeams();
      loadUsers();
      loadMeetings();
    }
  }, [connected]);

  useEffect(() => {
    if (currentTeam) {
      loadChannels();
    }
  }, [currentTeam]);

  useEffect(() => {
    if (currentChannel) {
      loadMessages();
    }
  }, [currentChannel]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const getVisibilityColor = (visibility: string): string => {
    switch (visibility?.toLowerCase()) {
      case "public":
        return "green";
      case "private":
        return "yellow";
      default:
        return "gray";
    }
  };

  const getSpecializationColor = (specialization: string): string => {
    switch (specialization?.toLowerCase()) {
      case "educationstandard":
        return "blue";
      case "educationclass":
        return "purple";
      case "educationprofessionallearning":
        return "pink";
      default:
        return "gray";
    }
  };

  const getMembershipTypeColor = (membershipType: string): string => {
    switch (membershipType?.toLowerCase()) {
      case "standard":
        return "blue";
      case "private":
        return "yellow";
      case "shared":
        return "green";
      default:
        return "gray";
    }
  };

  const getImportanceColor = (importance?: string): string => {
    switch (importance?.toLowerCase()) {
      case "high":
        return "red";
      case "normal":
        return "yellow";
      case "low":
        return "blue";
      default:
        return "gray";
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case "accepted":
        return "green";
      case "tentative":
        return "yellow";
      case "declined":
        return "red";
      case "notresponded":
        return "gray";
      default:
        return "gray";
    }
  };

  return (
    <ChakraBox minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={SettingsIcon} w={8} h={8} color="#2B579A" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Microsoft Teams Integration</Heading>
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

          {userProfile && (
            <HStack spacing={4}>
              <Avatar name={userProfile.displayName} />
              <VStack align="start" spacing={0}>
                <Text fontWeight="bold">{userProfile.displayName}</Text>
                <Text fontSize="sm" color="gray.600">
                  {userProfile.jobTitle || userProfile.mail}
                </Text>
              </VStack>
            </HStack>
          )}
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={SettingsIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Microsoft Teams</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Microsoft Teams account to start managing teams
                    and channels
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/teams/auth/start")
                  }
                >
                  Connect Microsoft Teams Account
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
                    <StatLabel>Teams</StatLabel>
                    <StatNumber>{totalTeams}</StatNumber>
                    <StatHelpText>Active workspaces</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Channels</StatLabel>
                    <StatNumber>{totalChannels}</StatNumber>
                    <StatHelpText>Communication channels</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Meetings</StatLabel>
                    <StatNumber>{upcomingMeetings}</StatNumber>
                    <StatHelpText>{totalMeetings} total</StatHelpText>
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
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Teams</Tab>
                <Tab>Channels</Tab>
                <Tab>Messages</Tab>
                <Tab>Meetings</Tab>
                <Tab>Users</Tab>
              </TabList>

              <TabPanels>
                {/* Teams Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <InputGroup>
                        <InputLeftElement pointerEvents="none">
                          <SearchIcon color="gray.400" />
                        </InputLeftElement>
                        <Input
                          placeholder="Search teams..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                      </InputGroup>
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onTeamOpen}
                      >
                        Create Team
                      </Button>
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.teams ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredTeams.map((team) => (
                          <Card
                            key={team.id}
                            cursor="pointer"
                            _hover={{
                              shadow: "md",
                              transform: "translateY(-2px)",
                            }}
                            transition="all 0.2s"
                            onClick={() => setCurrentTeam(team)}
                            borderWidth="1px"
                            borderColor={
                              currentTeam?.id === team.id
                                ? "blue.500"
                                : borderColor
                            }
                          >
                            <CardHeader>
                              <VStack align="start" spacing={2}>
                                <HStack justify="space-between" width="100%">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {team.displayName}
                                  </Text>
                                  <HStack>
                                    <Tag
                                      colorScheme={getVisibilityColor(
                                        team.visibility,
                                      )}
                                      size="sm"
                                    >
                                      {team.visibility}
                                    </Tag>
                                    {team.isArchived && (
                                      <Tag colorScheme="gray" size="sm">
                                        Archived
                                      </Tag>
                                    )}
                                  </HStack>
                                </HStack>
                                {team.description && (
                                  <Text fontSize="sm" color="gray.600">
                                    {team.description}
                                  </Text>
                                )}
                              </VStack>
                            </CardHeader>
                            <CardBody>
                              <VStack spacing={3} align="stretch">
                                <HStack justify="space-between">
                                  <Tag
                                    colorScheme={getSpecializationColor(
                                      team.specialization,
                                    )}
                                    size="sm"
                                  >
                                    {team.specialization}
                                  </Tag>
                                  <Text fontSize="xs" color="gray.500">
                                    Created: {formatDate(team.createdDateTime)}
                                  </Text>
                                </HStack>
                                <Link href={team.webUrl} target="_blank">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    leftIcon={<ExternalLinkIcon />}
                                  >
                                    Open in Teams
                                  </Button>
                                </Link>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                {/* Channels Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Select team"
                        value={currentTeam?.id || ""}
                        onChange={(e) => {
                          const team = teams.find(
                            (t) => t.id === e.target.value,
                          );
                          setCurrentTeam(team || null);
                        }}
                        width="200px"
                      >
                        {teams.map((team) => (
                          <option key={team.id} value={team.id}>
                            {team.displayName}
                          </option>
                        ))}
                      </Select>
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
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onChannelOpen}
                        disabled={!currentTeam}
                      >
                        Create Channel
                      </Button>
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.channels ? (
                        <Spinner size="xl" />
                      ) : currentTeam ? (
                        filteredChannels.map((channel) => (
                          <Card
                            key={channel.id}
                            cursor="pointer"
                            _hover={{
                              shadow: "md",
                              transform: "translateY(-2px)",
                            }}
                            transition="all 0.2s"
                            onClick={() => setCurrentChannel(channel)}
                            borderWidth="1px"
                            borderColor={
                              currentChannel?.id === channel.id
                                ? "blue.500"
                                : borderColor
                            }
                          >
                            <CardHeader>
                              <VStack align="start" spacing={2}>
                                <HStack justify="space-between" width="100%">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {channel.displayName}
                                  </Text>
                                  <HStack>
                                    <Tag
                                      colorScheme={getMembershipTypeColor(
                                        channel.membershipType,
                                      )}
                                      size="sm"
                                    >
                                      {channel.membershipType}
                                    </Tag>
                                    {channel.isFavoriteByDefault && (
                                      <Tag colorScheme="yellow" size="sm">
                                        <StarIcon mr={1} />
                                        Favorite
                                      </Tag>
                                    )}
                                  </HStack>
                                </HStack>
                                {channel.description && (
                                  <Text fontSize="sm" color="gray.600">
                                    {channel.description}
                                  </Text>
                                )}
                              </VStack>
                            </CardHeader>
                            <CardBody>
                              <VStack spacing={3} align="stretch">
                                <Text fontSize="xs" color="gray.500">
                                  Created: {formatDate(channel.createdDateTime)}
                                </Text>
                                {channel.tabs && channel.tabs.length > 0 && (
                                  <Text fontSize="xs" color="gray.500">
                                    {channel.tabs.length} tabs
                                  </Text>
                                )}
                                <Link href={channel.webUrl} target="_blank">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    leftIcon={<ExternalLinkIcon />}
                                  >
                                    Open in Teams
                                  </Button>
                                </Link>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : (
                        <Text color="gray.500" textAlign="center" py={8}>
                          Select a team to view channels
                        </Text>
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                {/* Messages Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Select team"
                        value={currentTeam?.id || ""}
                        onChange={(e) => {
                          const team = teams.find(
                            (t) => t.id === e.target.value,
                          );
                          setCurrentTeam(team || null);
                          setCurrentChannel(null);
                        }}
                        width="150px"
                      />
                      <Select
                        placeholder="Select channel"
                        value={currentChannel?.id || ""}
                        onChange={(e) => {
                          const channel = channels.find(
                            (c) => c.id === e.target.value,
                          );
                          setCurrentChannel(channel || null);
                        }}
                        width="150px"
                        disabled={!currentTeam}
                      >
                        {channels.map((channel) => (
                          <option key={channel.id} value={channel.id}>
                            {channel.displayName}
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
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onMessageOpen}
                        disabled={!currentChannel}
                      >
                        Send Message
                      </Button>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.messages ? (
                        <Spinner size="xl" />
                      ) : currentChannel ? (
                        filteredMessages.map((message) => (
                          <Card key={message.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <Avatar
                                  name={message.from.user?.displayName}
                                  size="md"
                                />
                                <VStack spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <Text fontWeight="medium">
                                      {message.from.user?.displayName}
                                    </Text>
                                    <HStack>
                                      {message.importance && (
                                        <Tag
                                          colorScheme={getImportanceColor(
                                            message.importance,
                                          )}
                                          size="sm"
                                        >
                                          {message.importance}
                                        </Tag>
                                      )}
                                      <Text fontSize="xs" color="gray.500">
                                        {formatDate(message.createdDateTime)}
                                      </Text>
                                    </HStack>
                                  </HStack>
                                  <Text fontSize="sm" whiteSpace="pre-wrap">
                                    {message.body.content}
                                  </Text>
                                  {message.reactions &&
                                    message.reactions.length > 0 && (
                                      <HStack spacing={2} wrap="wrap">
                                        {message.reactions.map(
                                          (reaction, index) => (
                                            <Tag
                                              key={index}
                                              size="sm"
                                              colorScheme="gray"
                                            >
                                              {reaction.reactionType}{" "}
                                              {reaction.user.displayName}
                                            </Tag>
                                          ),
                                        )}
                                      </HStack>
                                    )}
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : (
                        <Text color="gray.500" textAlign="center" py={8}>
                          Select a team and channel to view messages
                        </Text>
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Meetings Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <InputGroup>
                        <InputLeftElement pointerEvents="none">
                          <SearchIcon color="gray.400" />
                        </InputLeftElement>
                        <Input
                          placeholder="Search meetings..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                      </InputGroup>
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onMeetingOpen}
                      >
                        Schedule Meeting
                      </Button>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.meetings ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredMeetings.map((meeting) => (
                          <Card key={meeting.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <Icon
                                  as={GenericAvatarIcon}
                                  w={6}
                                  h={6}
                                  color="#2B579A"
                                />
                                <VStack spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <Text fontWeight="bold">
                                      {meeting.subject}
                                    </Text>
                                    <HStack>
                                      {meeting.isOnlineMeeting && (
                                        <Tag colorScheme="blue" size="sm">
                                          <GenericAvatarIcon mr={1} />
                                          Online Meeting
                                        </Tag>
                                      )}
                                    </HStack>
                                  </HStack>
                                  {meeting.body?.content && (
                                    <Text fontSize="sm" color="gray.600">
                                      {meeting.body.content.substring(0, 200)}
                                      {meeting.body.content.length > 200 &&
                                        "..."}
                                    </Text>
                                  )}
                                  <HStack spacing={4}>
                                    <Text fontSize="sm" color="gray.500">
                                      📅 {formatDate(meeting.start.dateTime)} -{" "}
                                      {formatDate(meeting.end.dateTime)}
                                    </Text>
                                  </HStack>
                                  {meeting.location && (
                                    <Text fontSize="sm" color="gray.500">
                                      📍 {meeting.location.displayName}
                                    </Text>
                                  )}
                                  {meeting.attendees &&
                                    meeting.attendees.length > 0 && (
                                      <HStack wrap="wrap">
                                        {meeting.attendees
                                          .slice(0, 3)
                                          .map((attendee) => (
                                            <Tag
                                              key={
                                                attendee.emailAddress.address
                                              }
                                              size="sm"
                                              colorScheme={getStatusColor(
                                                attendee.status.response,
                                              )}
                                            >
                                              {attendee.emailAddress.name}
                                            </Tag>
                                          ))}
                                        {meeting.attendees.length > 3 && (
                                          <Tag size="sm" colorScheme="gray">
                                            +{meeting.attendees.length - 3} more
                                          </Tag>
                                        )}
                                      </HStack>
                                    )}
                                  {meeting.joinUrl && (
                                    <Link
                                      href={meeting.joinUrl}
                                      target="_blank"
                                    >
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<GenericAvatarIcon />}
                                      >
                                        Join Meeting
                                      </Button>
                                    </Link>
                                  )}
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </VStack>
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

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.users ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredUsers.map((user) => (
                          <Card key={user.id}>
                            <CardBody>
                              <HStack spacing={4}>
                                <Avatar name={user.displayName} size="lg" />
                                <VStack align="start" spacing={1} flex={1}>
                                  <HStack>
                                    <Text fontWeight="bold">
                                      {user.displayName}
                                    </Text>
                                    <Tag
                                      colorScheme={
                                        user.accountEnabled ? "green" : "red"
                                      }
                                      size="sm"
                                    >
                                      {user.accountEnabled
                                        ? "Active"
                                        : "Inactive"}
                                    </Tag>
                                  </HStack>
                                  <Text fontSize="sm" color="gray.600">
                                    {user.mail || user.userPrincipalName}
                                  </Text>
                                  {user.jobTitle && (
                                    <Text fontSize="sm" color="gray.500">
                                      {user.jobTitle}
                                    </Text>
                                  )}
                                  {user.department && (
                                    <Text fontSize="xs" color="gray.500">
                                      {user.department}
                                    </Text>
                                  )}
                                  {user.officeLocation && (
                                    <Text fontSize="xs" color="gray.500">
                                      📍 {user.officeLocation}
                                    </Text>
                                  )}
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create Team Modal */}
            <Modal isOpen={isTeamOpen} onClose={onTeamClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Team</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Team Name</FormLabel>
                      <Input
                        placeholder="Enter team name"
                        value={teamForm.name}
                        onChange={(e) =>
                          setTeamForm({
                            ...teamForm,
                            name: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Team description"
                        value={teamForm.description}
                        onChange={(e) =>
                          setTeamForm({
                            ...teamForm,
                            description: e.target.value,
                          })
                        }
                        rows={3}
                      />
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Visibility</FormLabel>
                        <Select
                          value={teamForm.visibility}
                          onChange={(e) =>
                            setTeamForm({
                              ...teamForm,
                              visibility: e.target.value,
                            })
                          }
                        >
                          <option value="public">Public</option>
                          <option value="private">Private</option>
                        </Select>
                      </FormControl>

                      <FormControl>
                        <FormLabel>Specialization</FormLabel>
                        <Select
                          value={teamForm.specialization}
                          onChange={(e) =>
                            setTeamForm({
                              ...teamForm,
                              specialization: e.target.value,
                            })
                          }
                        >
                          <option value="none">None</option>
                          <option value="educationStandard">
                            Education Standard
                          </option>
                          <option value="educationClass">
                            Education Class
                          </option>
                          <option value="educationProfessionalLearning">
                            Education Professional Learning
                          </option>
                          <option value="educationStaff">
                            Education Staff
                          </option>
                        </Select>
                      </FormControl>
                    </HStack>

                    <FormControl>
                      <FormLabel>Classification</FormLabel>
                      <Input
                        placeholder="Team classification"
                        value={teamForm.classification}
                        onChange={(e) =>
                          setTeamForm({
                            ...teamForm,
                            classification: e.target.value,
                          })
                        }
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onTeamClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createTeam}
                    disabled={!teamForm.name}
                  >
                    Create Team
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
                        placeholder="Enter channel name"
                        value={channelForm.name}
                        onChange={(e) =>
                          setChannelForm({
                            ...channelForm,
                            name: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Channel description"
                        value={channelForm.description}
                        onChange={(e) =>
                          setChannelForm({
                            ...channelForm,
                            description: e.target.value,
                          })
                        }
                        rows={3}
                      />
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Membership Type</FormLabel>
                        <Select
                          value={channelForm.membership_type}
                          onChange={(e) =>
                            setChannelForm({
                              ...channelForm,
                              membership_type: e.target.value,
                            })
                          }
                        >
                          <option value="standard">Standard</option>
                          <option value="private">Private</option>
                          <option value="shared">Shared</option>
                        </Select>
                      </FormControl>

                      <FormControl>
                        <FormLabel>
                          <Checkbox
                            isChecked={channelForm.is_favorite_by_default}
                            onChange={(e) =>
                              setChannelForm({
                                ...channelForm,
                                is_favorite_by_default: e.target.checked,
                              })
                            }
                          >
                            Favorite by default
                          </Checkbox>
                        </FormLabel>
                      </FormControl>
                    </HStack>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onChannelClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createChannel}
                    disabled={!channelForm.name}
                  >
                    Create Channel
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Send Message Modal */}
            <Modal isOpen={isMessageOpen} onClose={onMessageClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Send Message</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Message</FormLabel>
                      <Textarea
                        placeholder="Type your message..."
                        value={messageForm.content}
                        onChange={(e) =>
                          setMessageForm({
                            ...messageForm,
                            content: e.target.value,
                          })
                        }
                        rows={6}
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Importance</FormLabel>
                      <Select
                        value={messageForm.importance}
                        onChange={(e) =>
                          setMessageForm({
                            ...messageForm,
                            importance: e.target.value,
                          })
                        }
                      >
                        <option value="low">Low</option>
                        <option value="normal">Normal</option>
                        <option value="high">High</option>
                      </Select>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Mention Users</FormLabel>
                      <Select
                        value={messageForm.mentioned_users[0] || ""}
                        onChange={(e) =>
                          setMessageForm({
                            ...messageForm,
                            mentioned_users: e.target.value
                              ? [e.target.value]
                              : [],
                          })
                        }
                      >
                        <option value="">Select users to mention</option>
                        {users.map((user) => (
                          <option key={user.id} value={user.id}>
                            {user.displayName}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onMessageClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={sendMessage}
                    disabled={!messageForm.content}
                  >
                    Send Message
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Schedule Meeting Modal */}
            <Modal isOpen={isMeetingOpen} onClose={onMeetingClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Schedule Meeting</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Subject</FormLabel>
                      <Input
                        placeholder="Meeting subject"
                        value={meetingForm.subject}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            subject: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Meeting description"
                        value={meetingForm.body}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            body: e.target.value,
                          })
                        }
                        rows={4}
                      />
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl isRequired>
                        <FormLabel>Start Time</FormLabel>
                        <Input
                          type="datetime-local"
                          value={meetingForm.start_time}
                          onChange={(e) =>
                            setMeetingForm({
                              ...meetingForm,
                              start_time: e.target.value,
                            })
                          }
                        />
                      </FormControl>

                      <FormControl isRequired>
                        <FormLabel>End Time</FormLabel>
                        <Input
                          type="datetime-local"
                          value={meetingForm.end_time}
                          onChange={(e) =>
                            setMeetingForm({
                              ...meetingForm,
                              end_time: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <FormControl>
                      <FormLabel>Attendees</FormLabel>
                      <Input
                        placeholder="Enter email addresses (comma separated)"
                        value={meetingForm.attendees.join(", ")}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            attendees: e.target.value
                              .split(",")
                              .map((s) => s.trim())
                              .filter((s) => s),
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>
                        <Checkbox
                          isChecked={meetingForm.is_online_meeting}
                          onChange={(e) =>
                            setMeetingForm({
                              ...meetingForm,
                              is_online_meeting: e.target.checked,
                            })
                          }
                        >
                          Online Meeting
                        </Checkbox>
                      </FormLabel>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onMeetingClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createMeeting}
                    disabled={
                      !meetingForm.subject ||
                      !meetingForm.start_time ||
                      !meetingForm.end_time
                    }
                  >
                    Schedule Meeting
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </>
        )}
      </VStack>
    </ChakraBox>
  );
};

export default MSTeamsIntegration;
