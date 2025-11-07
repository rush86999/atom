/**
 * Outlook Integration Page
 * Enhanced Microsoft Outlook integration with Chakra UI
 * Complete email, calendar, contact, and task management interface
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
  AvatarGroup,
} from "@chakra-ui/react";
import {
  CalendarIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  ExternalLinkIcon,
  AddIcon,
  SearchIcon,
  SettingsIcon,
  RepeatIcon,
  EmailIcon,
  PhoneIcon,
  StarIcon,
} from "@chakra-ui/icons";

interface OutlookEmail {
  id: string;
  subject: string;
  from: {
    name: string;
    email: string;
  };
  to: Array<{
    name: string;
    email: string;
  }>;
  body: string;
  receivedDateTime: string;
  isRead: boolean;
  hasAttachments: boolean;
  importance: "low" | "normal" | "high";
  webLink?: string;
}

interface OutlookEvent {
  id: string;
  subject: string;
  start: {
    dateTime: string;
    timeZone: string;
  };
  end: {
    dateTime: string;
    timeZone: string;
  };
  location?: string;
  attendees?: Array<{
    name: string;
    email: string;
    type: string;
  }>;
  isAllDay: boolean;
  showAs: "free" | "tentative" | "busy" | "oof";
}

interface OutlookContact {
  id: string;
  displayName: string;
  emailAddresses: Array<{
    address: string;
    name?: string;
  }>;
  businessPhones: string[];
  mobilePhone?: string;
  jobTitle?: string;
  companyName?: string;
}

interface OutlookTask {
  id: string;
  title: string;
  status:
    | "notStarted"
    | "inProgress"
    | "completed"
    | "waitingOnOthers"
    | "deferred";
  importance: "low" | "normal" | "high";
  dueDateTime?: string;
  reminderDateTime?: string;
  categories: string[];
}

interface OutlookUser {
  id: string;
  displayName: string;
  mail: string;
  userPrincipalName: string;
  jobTitle?: string;
  officeLocation?: string;
}

const OutlookIntegration: React.FC = () => {
  const [emails, setEmails] = useState<OutlookEmail[]>([]);
  const [events, setEvents] = useState<OutlookEvent[]>([]);
  const [contacts, setContacts] = useState<OutlookContact[]>([]);
  const [tasks, setTasks] = useState<OutlookTask[]>([]);
  const [userProfile, setUserProfile] = useState<OutlookUser | null>(null);
  const [loading, setLoading] = useState({
    emails: false,
    events: false,
    contacts: false,
    tasks: false,
    profile: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFolder, setSelectedFolder] = useState("inbox");
  const [selectedImportance, setSelectedImportance] = useState("");

  const { isOpen, onOpen, onClose } = useDisclosure();
  const [newEmail, setNewEmail] = useState({
    to: "",
    subject: "",
    body: "",
    importance: "normal" as "low" | "normal" | "high",
  });

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/outlook/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadUserProfile();
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

  // Load Outlook data
  const loadUserProfile = async () => {
    setLoading((prev) => ({ ...prev, profile: true }));
    try {
      const response = await fetch("/api/integrations/outlook/profile", {
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

  const loadEmails = async () => {
    setLoading((prev) => ({ ...prev, emails: true }));
    try {
      const response = await fetch("/api/integrations/outlook/emails", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          folder: selectedFolder,
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setEmails(data.data?.emails || []);
      }
    } catch (error) {
      console.error("Failed to load emails:", error);
      toast({
        title: "Error",
        description: "Failed to load emails from Outlook",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, emails: false }));
    }
  };

  const loadEvents = async () => {
    setLoading((prev) => ({ ...prev, events: true }));
    try {
      const response = await fetch("/api/integrations/outlook/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          start_date: new Date().toISOString(),
          end_date: new Date(
            Date.now() + 7 * 24 * 60 * 60 * 1000,
          ).toISOString(),
          limit: 20,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setEvents(data.data?.events || []);
      }
    } catch (error) {
      console.error("Failed to load events:", error);
    } finally {
      setLoading((prev) => ({ ...prev, events: false }));
    }
  };

  const loadContacts = async () => {
    setLoading((prev) => ({ ...prev, contacts: true }));
    try {
      const response = await fetch("/api/integrations/outlook/contacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 30,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setContacts(data.data?.contacts || []);
      }
    } catch (error) {
      console.error("Failed to load contacts:", error);
    } finally {
      setLoading((prev) => ({ ...prev, contacts: false }));
    }
  };

  const loadTasks = async () => {
    setLoading((prev) => ({ ...prev, tasks: true }));
    try {
      const response = await fetch("/api/integrations/outlook/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 20,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setTasks(data.data?.tasks || []);
      }
    } catch (error) {
      console.error("Failed to load tasks:", error);
    } finally {
      setLoading((prev) => ({ ...prev, tasks: false }));
    }
  };

  // Send email
  const sendEmail = async () => {
    try {
      const response = await fetch("/api/integrations/outlook/emails/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          to: newEmail.to,
          subject: newEmail.subject,
          body: newEmail.body,
          importance: newEmail.importance,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Email sent successfully",
          status: "success",
          duration: 3000,
        });
        onClose();
        setNewEmail({ to: "", subject: "", body: "", importance: "normal" });
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

  // Filter emails based on search and filters
  const filteredEmails = emails.filter((email) => {
    const matchesSearch =
      email.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      email.from.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      email.from.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesImportance =
      !selectedImportance || email.importance === selectedImportance;

    return matchesSearch && matchesImportance;
  });

  // Stats calculations
  const totalEmails = emails.length;
  const unreadEmails = emails.filter((email) => !email.isRead).length;
  const importantEmails = emails.filter(
    (email) => email.importance === "high",
  ).length;
  const upcomingEvents = events.filter(
    (event) => new Date(event.start.dateTime) > new Date(),
  ).length;
  const completedTasks = tasks.filter(
    (task) => task.status === "completed",
  ).length;
  const completionRate =
    tasks.length > 0 ? (completedTasks / tasks.length) * 100 : 0;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadEmails();
      loadEvents();
      loadContacts();
      loadTasks();
    }
  }, [connected, selectedFolder]);

  const getImportanceColor = (importance: string) => {
    switch (importance) {
      case "high":
        return "red";
      case "normal":
        return "blue";
      case "low":
        return "gray";
      default:
        return "gray";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "green";
      case "inProgress":
        return "orange";
      case "notStarted":
        return "gray";
      case "waitingOnOthers":
        return "yellow";
      case "deferred":
        return "red";
      default:
        return "gray";
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "completed":
        return "Completed";
      case "inProgress":
        return "In Progress";
      case "notStarted":
        return "Not Started";
      case "waitingOnOthers":
        return "Waiting";
      case "deferred":
        return "Deferred";
      default:
        return "Unknown";
    }
  };

  const formatDateTime = (dateTime: string) => {
    return (
      new Date(dateTime).toLocaleDateString() +
      " " +
      new Date(dateTime).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    );
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={EmailIcon} w={8} h={8} color="blue.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Outlook Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Email, calendar, contacts, and task management
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
            {userProfile && (
              <Badge colorScheme="blue" variant="outline">
                {userProfile.displayName}
              </Badge>
            )}
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RepeatIcon />}
              onClick={checkConnection}
            >
              Refresh Status
            </Button>
          </HStack>
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={EmailIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Outlook</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Outlook account to manage emails, calendar,
                    contacts, and tasks
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() =>
                    (window.location.href = "/api/auth/outlook/authorize")
                  }
                >
                  Connect Outlook Account
                </Button>
              </VStack>
            </CardBody>
          </Card>
        ) : (
          // Connected State
          <>
            {/* Stats Overview */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 5 }} spacing={6}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Total Emails</StatLabel>
                    <StatNumber>{totalEmails}</StatNumber>
                    <StatHelpText>In selected folder</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Unread</StatLabel>
                    <StatNumber>{unreadEmails}</StatNumber>
                    <StatHelpText>Require attention</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Important</StatLabel>
                    <StatNumber>{importantEmails}</StatNumber>
                    <StatHelpText>High priority</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Upcoming Events</StatLabel>
                    <StatNumber>{upcomingEvents}</StatNumber>
                    <StatHelpText>Next 7 days</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Task Completion</StatLabel>
                    <StatNumber>{Math.round(completionRate)}%</StatNumber>
                    <Progress
                      value={completionRate}
                      colorScheme="green"
                      size="sm"
                      mt={2}
                    />
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Emails</Tab>
                <Tab>Calendar</Tab>
                <Tab>Contacts</Tab>
                <Tab>Tasks</Tab>
              </TabList>

              <TabPanels>
                {/* Emails Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    {/* Filters and Actions */}
                    <Card>
                      <CardBody>
                        <Stack
                          direction={{ base: "column", md: "row" }}
                          spacing={4}
                        >
                          <Input
                            placeholder="Search emails..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            leftAddon={<SearchIcon />}
                          />
                          <Select
                            value={selectedFolder}
                            onChange={(e) => setSelectedFolder(e.target.value)}
                          >
                            <option value="inbox">Inbox</option>
                            <option value="sent">Sent Items</option>
                            <option value="drafts">Drafts</option>
                            <option value="archive">Archive</option>
                          </Select>
                          <Select
                            placeholder="All Importance"
                            value={selectedImportance}
                            onChange={(e) =>
                              setSelectedImportance(e.target.value)
                            }
                          >
                            <option value="high">High</option>
                            <option value="normal">Normal</option>
                            <option value="low">Low</option>
                          </Select>
                          <Spacer />
                          <Button
                            colorScheme="blue"
                            leftIcon={<AddIcon />}
                            onClick={onOpen}
                          >
                            New Email
                          </Button>
                        </Stack>
                      </CardBody>
                    </Card>

                    {/* Emails Table */}
                    <Card>
                      <CardBody>
                        {loading.emails ? (
                          <VStack spacing={4} py={8}>
                            <Text>Loading emails...</Text>
                            <Progress size="sm" isIndeterminate width="100%" />
                          </VStack>
                        ) : filteredEmails.length === 0 ? (
                          <VStack spacing={4} py={8}>
                            <Icon
                              as={EmailIcon}
                              w={12}
                              h={12}
                              color="gray.400"
                            />
                            <Text color="gray.600">No emails found</Text>
                            <Button
                              variant="outline"
                              leftIcon={<AddIcon />}
                              onClick={onOpen}
                            >
                              Compose New Email
                            </Button>
                          </VStack>
                        ) : (
                          <Box overflowX="auto">
                            <Table variant="simple">
                              <Thead>
                                <Tr>
                                  <Th>From</Th>
                                  <Th>Subject</Th>
                                  <Th>Importance</Th>
                                  <Th>Received</Th>
                                  <Th>Status</Th>
                                  <Th>Actions</Th>
                                </Tr>
                              </Thead>
                              <Tbody>
                                {filteredEmails.map((email) => (
                                  <Tr key={email.id}>
                                    <Td>
                                      <VStack align="start" spacing={1}>
                                        <Text fontWeight="medium">
                                          {email.from.name}
                                        </Text>
                                        <Text fontSize="sm" color="gray.600">
                                          {email.from.email}
                                        </Text>
                                      </VStack>
                                    </Td>
                                    <Td>
                                      <Text fontWeight="medium" noOfLines={2}>
                                        {email.subject}
                                      </Text>
                                      {email.body && (
                                        <Text
                                          fontSize="sm"
                                          color="gray.600"
                                          noOfLines={1}
                                        >
                                          {email.body}
                                        </Text>
                                      )}
                                    </Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getImportanceColor(
                                          email.importance,
                                        )}
                                        size="sm"
                                      >
                                        <TagLabel>{email.importance}</TagLabel>
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {formatDateTime(email.receivedDateTime)}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <HStack spacing={2}>
                                        {email.isRead ? (
                                          <CheckCircleIcon color="green.500" />
                                        ) : (
                                          <Badge colorScheme="red">
                                            Unread
                                          </Badge>
                                        )}
                                        {email.hasAttachments && (
                                          <Badge colorScheme="blue">
                                            Attachment
                                          </Badge>
                                        )}
                                      </HStack>
                                    </Td>
                                    <Td>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ExternalLinkIcon />}
                                        onClick={() =>
                                          window.open(email.webLink, "_blank")
                                        }
                                      >
                                        View
                                      </Button>
                                    </Td>
                                  </Tr>
                                ))}
                              </Tbody>
                            </Table>
                          </Box>
                        )}
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Calendar Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <SimpleGrid
                          columns={{ base: 1, md: 2, lg: 3 }}
                          spacing={6}
                        >
                          {events.map((event) => (
                            <Card key={event.id} variant="outline">
                              <CardBody>
                                <VStack spacing={3} align="start">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {event.subject}
                                  </Text>
                                  <Text color="gray.600" fontSize="sm">
                                    {formatDateTime(event.start.dateTime)} -{" "}
                                    {formatDateTime(event.end.dateTime)}
                                  </Text>
                                  {event.location && (
                                    <HStack spacing={1}>
                                      <Icon
                                        as={CalendarIcon}
                                        w={3}
                                        h={3}
                                        color="gray.500"
                                      />
                                      <Text fontSize="sm" color="gray.600">
                                        {event.location}
                                      </Text>
                                    </HStack>
                                  )}
                                  {event.attendees &&
                                    event.attendees.length > 0 && (
                                      <VStack align="start" spacing={1}>
                                        <Text fontSize="sm" fontWeight="medium">
                                          Attendees ({event.attendees.length})
                                        </Text>
                                        <AvatarGroup size="sm" max={3}>
                                          {event.attendees
                                            .slice(0, 3)
                                            .map((attendee, index) => (
                                              <Avatar
                                                key={index}
                                                name={attendee.name}
                                                src=""
                                                bg="blue.500"
                                              />
                                            ))}
                                        </AvatarGroup>
                                      </VStack>
                                    )}
                                  <Badge
                                    colorScheme={
                                      event.showAs === "busy" ? "red" : "green"
                                    }
                                  >
                                    {event.showAs}
                                  </Badge>
                                </VStack>
                              </CardBody>
                            </Card>
                          ))}
                        </SimpleGrid>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Contacts Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <SimpleGrid
                          columns={{ base: 1, md: 2, lg: 3 }}
                          spacing={6}
                        >
                          {contacts.map((contact) => (
                            <Card key={contact.id} variant="outline">
                              <CardBody>
                                <VStack spacing={3} align="start">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {contact.displayName}
                                  </Text>
                                  {contact.emailAddresses.map(
                                    (email, index) => (
                                      <HStack key={index} spacing={1}>
                                        <Icon
                                          as={EmailIcon}
                                          w={3}
                                          h={3}
                                          color="gray.500"
                                        />
                                        <Text fontSize="sm" color="gray.600">
                                          {email.address}
                                        </Text>
                                      </HStack>
                                    ),
                                  )}
                                  {contact.businessPhones.length > 0 && (
                                    <HStack spacing={1}>
                                      <Icon
                                        as={PhoneIcon}
                                        w={3}
                                        h={3}
                                        color="gray.500"
                                      />
                                      <Text fontSize="sm" color="gray.600">
                                        {contact.businessPhones[0]}
                                      </Text>
                                    </HStack>
                                  )}
                                  {contact.jobTitle && (
                                    <Text fontSize="sm" color="gray.600">
                                      {contact.jobTitle}
                                    </Text>
                                  )}
                                  {contact.companyName && (
                                    <Text fontSize="sm" color="gray.600">
                                      {contact.companyName}
                                    </Text>
                                  )}
                                </VStack>
                              </CardBody>
                            </Card>
                          ))}
                        </SimpleGrid>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Tasks Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <SimpleGrid
                          columns={{ base: 1, md: 2, lg: 3 }}
                          spacing={6}
                        >
                          {tasks.map((task) => (
                            <Card key={task.id} variant="outline">
                              <CardBody>
                                <VStack spacing={3} align="start">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {task.title}
                                  </Text>
                                  <HStack spacing={2}>
                                    <Tag
                                      colorScheme={getStatusColor(task.status)}
                                      size="sm"
                                    >
                                      <TagLabel>
                                        {getStatusLabel(task.status)}
                                      </TagLabel>
                                    </Tag>
                                    <Tag
                                      colorScheme={getImportanceColor(
                                        task.importance,
                                      )}
                                      size="sm"
                                    >
                                      <TagLabel>{task.importance}</TagLabel>
                                    </Tag>
                                  </HStack>
                                  {task.dueDateTime && (
                                    <HStack spacing={1}>
                                      <Icon
                                        as={CalendarIcon}
                                        w={3}
                                        h={3}
                                        color="gray.500"
                                      />
                                      <Text fontSize="sm" color="gray.600">
                                        Due: {formatDateTime(task.dueDateTime)}
                                      </Text>
                                    </HStack>
                                  )}
                                  {task.categories.length > 0 && (
                                    <HStack spacing={1}>
                                      {task.categories.map(
                                        (category, index) => (
                                          <Badge
                                            key={index}
                                            colorScheme="blue"
                                            variant="outline"
                                          >
                                            {category}
                                          </Badge>
                                        ),
                                      )}
                                    </HStack>
                                  )}
                                </VStack>
                              </CardBody>
                            </Card>
                          ))}
                        </SimpleGrid>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create Email Modal */}
            <Modal isOpen={isOpen} onClose={onClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Compose New Email</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>To</FormLabel>
                      <Input
                        placeholder="recipient@example.com"
                        value={newEmail.to}
                        onChange={(e) =>
                          setNewEmail({ ...newEmail, to: e.target.value })
                        }
                      />
                    </FormControl>
                    <FormControl isRequired>
                      <FormLabel>Subject</FormLabel>
                      <Input
                        placeholder="Email subject"
                        value={newEmail.subject}
                        onChange={(e) =>
                          setNewEmail({ ...newEmail, subject: e.target.value })
                        }
                      />
                    </FormControl>
                    <FormControl>
                      <FormLabel>Importance</FormLabel>
                      <Select
                        value={newEmail.importance}
                        onChange={(e) =>
                          setNewEmail({
                            ...newEmail,
                            importance: e.target.value as
                              | "low"
                              | "normal"
                              | "high",
                          })
                        }
                      >
                        <option value="low">Low</option>
                        <option value="normal">Normal</option>
                        <option value="high">High</option>
                      </Select>
                    </FormControl>
                    <FormControl isRequired>
                      <FormLabel>Body</FormLabel>
                      <Textarea
                        placeholder="Email content"
                        value={newEmail.body}
                        onChange={(e) =>
                          setNewEmail({ ...newEmail, body: e.target.value })
                        }
                        rows={6}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={sendEmail}
                    isDisabled={
                      !newEmail.to || !newEmail.subject || !newEmail.body
                    }
                  >
                    Send Email
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

export default OutlookIntegration;
