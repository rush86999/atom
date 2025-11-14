/**
 * Microsoft 365 Integration Page
 * Complete Microsoft 365 productivity suite integration
 */

import React, { useState, useEffect } from "react";
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
  ChatIcon,
  EmailIcon,
  CalendarIcon,
  FileIcon,
} from "@chakra-ui/icons";

interface Microsoft365User {
  id: string;
  displayName: string;
  givenName: string;
  surname: string;
  userPrincipalName: string;
  jobTitle?: string;
  mail?: string;
  mobilePhone?: string;
  officeLocation?: string;
  department?: string;
  businessPhones: string[];
  accountEnabled: boolean;
}

interface Microsoft365Calendar {
  id: string;
  subject: string;
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
    address?: {
      street: string;
      city: string;
      state: string;
      postalCode: string;
      countryOrRegion: string;
    };
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
  organizer: {
    emailAddress: {
      name: string;
      address: string;
    };
  };
  isOnlineMeeting: boolean;
  onlineMeetingUrl?: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  recurrence?: any;
}

interface Microsoft365Email {
  id: string;
  subject: string;
  body: {
    contentType: string;
    content: string;
  };
  sender: {
    emailAddress: {
      name: string;
      address: string;
    };
  };
  from: {
    emailAddress: {
      name: string;
      address: string;
    };
  };
  toRecipients: Array<{
    emailAddress: {
      name: string;
      address: string;
    };
  }>;
  ccRecipients?: Array<{
    emailAddress: {
      name: string;
      address: string;
    };
  }>;
  bccRecipients?: Array<{
    emailAddress: {
      name: string;
      address: string;
    };
  }>;
  receivedDateTime: string;
  sentDateTime: string;
  hasAttachments: boolean;
  attachments?: Array<{
    id: string;
    contentType: string;
    name: string;
    size: number;
    isInline: boolean;
  }>;
  importance: "low" | "normal" | "high";
  isRead: boolean;
  isDraft: boolean;
  categories: string[];
  conversationId: string;
  webLink: string;
}

interface Microsoft365File {
  id: string;
  name: string;
  size: number;
  file?: {
    mimeType: string;
    hashes: {
      sha1Hash: string;
      quickXorHash: string;
    };
  };
  folder?: {
    childCount: number;
    view: {
      sortBy: string;
      sortOrder: string;
    };
  };
  createdDateTime: string;
  lastModifiedDateTime: string;
  parentReference: {
    driveId: string;
    driveType: string;
    id: string;
    name: string;
    path: string;
  };
  webUrl: string;
  createdBy?: {
    application?: {
      displayName: string;
      id: string;
    };
    device?: {
      displayName: string;
      id: string;
    };
    user?: {
      displayName: string;
      id: string;
    };
  };
  lastModifiedBy?: {
    application?: {
      displayName: string;
      id: string;
    };
    device?: {
      displayName: string;
      id: string;
    };
    user?: {
      displayName: string;
      id: string;
    };
  };
  sharePointIds?: {
    webUrl: string;
    siteId: string;
    siteUrl: string;
    listId: string;
    listItemId: string;
  }[];
}

interface Microsoft365Team {
  id: string;
  displayName: string;
  description: string;
  createdDateTime: string;
  updatedDateTime: string;
  classification?: string;
  specialization: "none" | "educationStandard" | "educationClass" | "educationProfessionalLearning" | "educationStaff";
  visibility: "public" | "private";
  webUrl: string;
  internalId: string;
  isArchived: boolean;
  members?: Array<{
    displayName: string;
    id: string;
    roles: string[];
  }>;
  channels?: Array<{
    id: string;
    displayName: string;
    description: string;
    isFavoriteByDefault: boolean;
    membershipType: string;
    createdDateTime: string;
    lastModifiedDateTime: string;
  }>;
}

const Microsoft365Integration: React.FC = () => {
  const [users, setUsers] = useState<Microsoft365User[]>([]);
  const [calendars, setCalendars] = useState<Microsoft365Calendar[]>([]);
  const [emails, setEmails] = useState<Microsoft365Email[]>([]);
  const [files, setFiles] = useState<Microsoft365File[]>([]);
  const [teams, setTeams] = useState<Microsoft365Team[]>([]);
  const [userProfile, setUserProfile] = useState<Microsoft365User | null>(null);
  const [loading, setLoading] = useState({
    users: false,
    calendars: false,
    emails: false,
    files: false,
    teams: false,
    profile: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFolder, setSelectedFolder] = useState("");

  const {
    isOpen: isEmailOpen,
    onOpen: onEmailOpen,
    onClose: onEmailClose,
  } = useDisclosure();
  const {
    isOpen: isCalendarOpen,
    onOpen: onCalendarOpen,
    onClose: onCalendarClose,
  } = useDisclosure();

  const [newEmail, setNewEmail] = useState({
    to: "",
    subject: "",
    body: "",
    importance: "normal" as "low" | "normal" | "high",
    cc: "",
  });

  const [newEvent, setNewEvent] = useState({
    subject: "",
    body: "",
    startTime: "",
    endTime: "",
    location: "",
    attendees: [] as string[],
  });

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/microsoft365/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadUserProfile();
        loadUsers();
        loadCalendars();
        loadEmails();
        loadFiles();
        loadTeams();
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

  // Load Microsoft 365 data
  const loadUserProfile = async () => {
    setLoading((prev) => ({ ...prev, profile: true }));
    try {
      const response = await fetch("/api/integrations/microsoft365/profile", {
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

  const loadUsers = async () => {
    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/microsoft365/users", {
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

  const loadCalendars = async () => {
    setLoading((prev) => ({ ...prev, calendars: true }));
    try {
      const response = await fetch("/api/integrations/microsoft365/calendars", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          start_date: new Date().toISOString(),
          end_date: new Date(
            Date.now() + 7 * 24 * 60 * 60 * 1000
          ).toISOString(),
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setCalendars(data.data?.events || []);
      }
    } catch (error) {
      console.error("Failed to load calendars:", error);
    } finally {
      setLoading((prev) => ({ ...prev, calendars: false }));
    }
  };

  const loadEmails = async () => {
    setLoading((prev) => ({ ...prev, emails: true }));
    try {
      const response = await fetch("/api/integrations/microsoft365/emails", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
          folder: "inbox",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setEmails(data.data?.messages || []);
      }
    } catch (error) {
      console.error("Failed to load emails:", error);
      toast({
        title: "Error",
        description: "Failed to load emails from Microsoft 365",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, emails: false }));
    }
  };

  const loadFiles = async () => {
    setLoading((prev) => ({ ...prev, files: true }));
    try {
      const response = await fetch("/api/integrations/microsoft365/files", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
          folder: selectedFolder,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setFiles(data.data?.files || []);
      }
    } catch (error) {
      console.error("Failed to load files:", error);
    } finally {
      setLoading((prev) => ({ ...prev, files: false }));
    }
  };

  const loadTeams = async () => {
    setLoading((prev) => ({ ...prev, teams: true }));
    try {
      const response = await fetch("/api/integrations/microsoft365/teams", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setTeams(data.data?.teams || []);
      }
    } catch (error) {
      console.error("Failed to load teams:", error);
    } finally {
      setLoading((prev) => ({ ...prev, teams: false }));
    }
  };

  const sendEmail = async () => {
    if (!newEmail.to || !newEmail.subject || !newEmail.body) return;

    try {
      const response = await fetch("/api/integrations/microsoft365/emails/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          to: newEmail.to.split(",").map(email => ({ address: email.trim() })),
          subject: newEmail.subject,
          body: {
            contentType: "text",
            content: newEmail.body,
          },
          importance: newEmail.importance,
          cc: newEmail.cc ? newEmail.cc.split(",").map(email => ({ address: email.trim() })) : [],
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Email sent successfully",
          status: "success",
          duration: 3000,
        });
        onEmailClose();
        setNewEmail({ to: "", subject: "", body: "", importance: "normal", cc: "" });
        loadEmails();
      }
    } catch (error) {
      console.error("Failed to send email:", error);
      toast({
        title: "Error",
        description: "Failed to send email",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createCalendarEvent = async () => {
    if (!newEvent.subject || !newEvent.startTime || !newEvent.endTime) return;

    try {
      const response = await fetch("/api/integrations/microsoft365/calendars/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          subject: newEvent.subject,
          body: {
            contentType: "text",
            content: newEvent.body,
          },
          start: {
            dateTime: newEvent.startTime,
            timeZone: "UTC",
          },
          end: {
            dateTime: newEvent.endTime,
            timeZone: "UTC",
          },
          location: {
            displayName: newEvent.location,
          },
          attendees: newEvent.attendees.map(email => ({
            type: "required",
            emailAddress: {
              address: email,
              name: email.split("@")[0],
            },
          })),
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Calendar event created successfully",
          status: "success",
          duration: 3000,
        });
        onCalendarClose();
        setNewEvent({ subject: "", body: "", startTime: "", endTime: "", location: "", attendees: [] });
        loadCalendars();
      }
    } catch (error) {
      console.error("Failed to create calendar event:", error);
      toast({
        title: "Error",
        description: "Failed to create calendar event",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredEmails = emails.filter(
    (email) =>
      email.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      email.sender.emailAddress.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      email.sender.emailAddress.address.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredCalendars = calendars.filter(
    (calendar) =>
      calendar.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      calendar.location?.displayName.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredFiles = files.filter(
    (file) =>
      file.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredUsers = users.filter(
    (user) =>
      user.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.userPrincipalName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (user.mail && user.mail.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const filteredTeams = teams.filter(
    (team) =>
      team.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      team.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Stats calculations
  const totalUsers = users.length;
  const activeUsers = users.filter(u => u.accountEnabled).length;
  const totalEmails = emails.length;
  const unreadEmails = emails.filter(e => !e.isRead).length;
  const totalEvents = calendars.length;
  const upcomingEvents = calendars.filter(e => new Date(e.start.dateTime) > new Date()).length;
  const totalFiles = files.length;
  const totalTeams = teams.length;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadUserProfile();
      loadUsers();
      loadCalendars();
      loadEmails();
      loadFiles();
      loadTeams();
    }
  }, [connected]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const getImportanceColor = (importance: string): string => {
    switch (importance) {
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

  const getFileIcon = (mimeType: string): any => {
    if (mimeType.startsWith("image/")) return FileIcon;
    if (mimeType.startsWith("video/")) return FileIcon;
    if (mimeType.startsWith("audio/")) return FileIcon;
    if (mimeType.includes("pdf")) return FileIcon;
    if (mimeType.includes("word")) return FileIcon;
    if (mimeType.includes("excel") || mimeType.includes("spreadsheet")) return FileIcon;
    if (mimeType.includes("powerpoint") || mimeType.includes("presentation")) return FileIcon;
    if (mimeType.includes("zip") || mimeType.includes("rar")) return FileIcon;
    return FileIcon;
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={SettingsIcon} w={8} h={8} color="#0078D4" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Microsoft 365 Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Complete productivity suite with Teams, Outlook, and OneDrive
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
                  {userProfile.jobTitle || userProfile.userPrincipalName}
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
                  <Heading size="lg">Connect Microsoft 365</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Microsoft 365 account to access Teams, Outlook, and OneDrive
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/microsoft365/auth/start")
                  }
                >
                  Connect Microsoft 365 Account
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
                    <StatHelpText>{activeUsers} active</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Emails</StatLabel>
                    <StatNumber>{totalEmails}</StatNumber>
                    <StatHelpText>{unreadEmails} unread</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Calendar Events</StatLabel>
                    <StatNumber>{upcomingEvents}</StatNumber>
                    <StatHelpText>{totalEvents} total</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Files</StatLabel>
                    <StatNumber>{totalFiles}</StatNumber>
                    <StatHelpText>OneDrive</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Outlook</Tab>
                <Tab>Calendar</Tab>
                <Tab>OneDrive</Tab>
                <Tab>Teams</Tab>
                <Tab>Users</Tab>
              </TabList>

              <TabPanels>
                {/* Outlook Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search emails..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onEmailOpen}
                      >
                        Compose Email
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {loading.emails ? (
                            <Spinner size="xl" />
                          ) : (
                            filteredEmails.map((email) => (
                              <HStack
                                key={email.id}
                                p={4}
                                borderWidth="1px"
                                borderRadius="md"
                                _hover={{ bg: "gray.50" }}
                                cursor="pointer"
                                onClick={() => window.open(email.webLink, "_blank")}
                              >
                                <Icon as={EmailIcon} w={6} h={6} color="blue.500" />
                                <VStack align="start" spacing={1} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <Text fontWeight="bold">
                                      {email.subject}
                                    </Text>
                                    <HStack>
                                      {!email.isRead && (
                                        <Tag colorScheme="blue" size="sm">
                                          New
                                        </Tag>
                                      )}
                                      <Tag colorScheme={getImportanceColor(email.importance)} size="sm">
                                        {email.importance}
                                      </Tag>
                                    </HStack>
                                  </HStack>
                                  <Text fontSize="sm" color="gray.600">
                                    From: {email.sender.emailAddress.name} ({email.sender.emailAddress.address})
                                  </Text>
                                  <Text fontSize="xs" color="gray.500">
                                    {formatDate(email.receivedDateTime)}
                                  </Text>
                                  {email.hasAttachments && (
                                    <Tag colorScheme="orange" size="sm">
                                      📎 Has attachments
                                    </Tag>
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

                {/* Calendar Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search calendar events..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onCalendarOpen}
                      >
                        Create Event
                      </Button>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.calendars ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredCalendars.map((event) => (
                          <Card key={event.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <Icon as={CalendarIcon} w={6} h={6} color="green.500" />
                                <VStack align="start" spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <Text fontWeight="bold">
                                      {event.subject}
                                    </Text>
                                    <HStack>
                                      {event.isOnlineMeeting && (
                                        <Tag colorScheme="blue" size="sm">
                                          📹 Online Meeting
                                        </Tag>
                                      )}
                                    </HStack>
                                  </HStack>
                                  {event.body && (
                                    <Text fontSize="sm" color="gray.600">
                                      {event.body.content.substring(0, 200)}
                                      {event.body.content.length > 200 && "..."}
                                    </Text>
                                  )}
                                  <HStack spacing={4}>
                                    <Text fontSize="sm" color="gray.500">
                                      📅 {formatDate(event.start.dateTime)} - {formatDate(event.end.dateTime)}
                                    </Text>
                                  </HStack>
                                  {event.location && (
                                    <Text fontSize="sm" color="gray.500">
                                      📍 {event.location.displayName}
                                    </Text>
                                  )}
                                  {event.attendees && event.attendees.length > 0 && (
                                    <HStack wrap="wrap">
                                      {event.attendees.slice(0, 3).map((attendee) => (
                                        <Tag key={attendee.emailAddress.address} size="sm" colorScheme="gray">
                                          {attendee.emailAddress.name}
                                        </Tag>
                                      ))}
                                      {event.attendees.length > 3 && (
                                        <Tag size="sm" colorScheme="gray">
                                          +{event.attendees.length - 3} more
                                        </Tag>
                                      )}
                                    </HStack>
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

                {/* OneDrive Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search files..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {loading.files ? (
                            <Spinner size="xl" />
                          ) : (
                            filteredFiles.map((file) => (
                              <HStack
                                key={file.id}
                                p={4}
                                borderWidth="1px"
                                borderRadius="md"
                                _hover={{ bg: "gray.50" }}
                                cursor="pointer"
                                onClick={() => window.open(file.webUrl, "_blank")}
                              >
                                <Icon
                                  as={getFileIcon(file.file?.mimeType || "")}
                                  w={6}
                                  h={6}
                                  color="blue.500"
                                />
                                <VStack align="start" spacing={1} flex={1}>
                                  <Text fontWeight="bold">{file.name}</Text>
                                  <HStack>
                                    <Text fontSize="xs" color="gray.500">
                                      {formatFileSize(file.size)}
                                    </Text>
                                    <Text fontSize="xs" color="gray.500">
                                      • {formatDate(file.lastModifiedDateTime)}
                                    </Text>
                                  </HStack>
                                </VStack>
                              </HStack>
                            ))
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Teams Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search teams..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {loading.teams ? (
                            <Spinner size="xl" />
                          ) : (
                            filteredTeams.map((team) => (
                              <HStack
                                key={team.id}
                                p={4}
                                borderWidth="1px"
                                borderRadius="md"
                                _hover={{ bg: "gray.50" }}
                                cursor="pointer"
                                onClick={() => window.open(team.webUrl, "_blank")}
                              >
                                <Icon as={ChatIcon} w={6} h={6} color="purple.500" />
                                <VStack align="start" spacing={1} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <Text fontWeight="bold">{team.displayName}</Text>
                                    <HStack>
                                      <Tag colorScheme={team.visibility === "private" ? "gray" : "green"} size="sm">
                                        {team.visibility}
                                      </Tag>
                                      {team.isArchived && (
                                        <Tag colorScheme="red" size="sm">
                                          Archived
                                        </Tag>
                                      )}
                                    </HStack>
                                  </HStack>
                                  <Text fontSize="sm" color="gray.600">
                                    {team.description}
                                  </Text>
                                  <HStack spacing={4}>
                                    <Text fontSize="xs" color="gray.500">
                                      Created: {formatDate(team.createdDateTime)}
                                    </Text>
                                    {team.channels && (
                                      <Text fontSize="xs" color="gray.500">
                                        {team.channels.length} channels
                                      </Text>
                                    )}
                                  </HStack>
                                </VStack>
                              </HStack>
                            ))
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
                      <Input
                        placeholder="Search users..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
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
                                <Avatar name={user.displayName} />
                                <VStack align="start" spacing={1} flex={1}>
                                  <HStack>
                                    <Text fontWeight="bold">{user.displayName}</Text>
                                    <Tag colorScheme={user.accountEnabled ? "green" : "red"} size="sm">
                                      {user.accountEnabled ? "Active" : "Inactive"}
                                    </Tag>
                                  </HStack>
                                  <Text fontSize="sm" color="gray.600">
                                    {user.userPrincipalName}
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
                            ))
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Compose Email Modal */}
            <Modal isOpen={isEmailOpen} onClose={onEmailClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Compose Email</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>To</FormLabel>
                      <Input
                        placeholder="recipient@example.com, recipient2@example.com"
                        value={newEmail.to}
                        onChange={(e) =>
                          setNewEmail({
                            ...newEmail,
                            to: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Cc</FormLabel>
                      <Input
                        placeholder="cc@example.com"
                        value={newEmail.cc}
                        onChange={(e) =>
                          setNewEmail({
                            ...newEmail,
                            cc: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Subject</FormLabel>
                      <Input
                        placeholder="Email subject"
                        value={newEmail.subject}
                        onChange={(e) =>
                          setNewEmail({
                            ...newEmail,
                            subject: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Message</FormLabel>
                      <Textarea
                        placeholder="Your message..."
                        value={newEmail.body}
                        onChange={(e) =>
                          setNewEmail({
                            ...newEmail,
                            body: e.target.value,
                          })
                        }
                        rows={6}
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Importance</FormLabel>
                      <Select
                        value={newEmail.importance}
                        onChange={(e) =>
                          setNewEmail({
                            ...newEmail,
                            importance: e.target.value as "low" | "normal" | "high",
                          })
                        }
                      >
                        <option value="low">Low</option>
                        <option value="normal">Normal</option>
                        <option value="high">High</option>
                      </Select>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onEmailClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={sendEmail}
                    disabled={!newEmail.to || !newEmail.subject || !newEmail.body}
                  >
                    Send Email
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Event Modal */}
            <Modal isOpen={isCalendarOpen} onClose={onCalendarClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Calendar Event</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Subject</FormLabel>
                      <Input
                        placeholder="Event subject"
                        value={newEvent.subject}
                        onChange={(e) =>
                          setNewEvent({
                            ...newEvent,
                            subject: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Event description"
                        value={newEvent.body}
                        onChange={(e) =>
                          setNewEvent({
                            ...newEvent,
                            body: e.target.value,
                          })
                        }
                        rows={4}
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Start Time</FormLabel>
                      <Input
                        type="datetime-local"
                        value={newEvent.startTime}
                        onChange={(e) =>
                          setNewEvent({
                            ...newEvent,
                            startTime: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>End Time</FormLabel>
                      <Input
                        type="datetime-local"
                        value={newEvent.endTime}
                        onChange={(e) =>
                          setNewEvent({
                            ...newEvent,
                            endTime: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Location</FormLabel>
                      <Input
                        placeholder="Event location"
                        value={newEvent.location}
                        onChange={(e) =>
                          setNewEvent({
                            ...newEvent,
                            location: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Attendees</FormLabel>
                      <Input
                        placeholder="attendee@example.com, attendee2@example.com"
                        value={newEvent.attendees.join(", ")}
                        onChange={(e) =>
                          setNewEvent({
                            ...newEvent,
                            attendees: e.target.value.split(",").map(s => s.trim()).filter(s => s),
                          })
                        }
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onCalendarClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createCalendarEvent}
                    disabled={!newEvent.subject || !newEvent.startTime || !newEvent.endTime}
                  >
                    Create Event
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

export default Microsoft365Integration;