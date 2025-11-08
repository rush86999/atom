/**
 * Microsoft 365 Integration Page
 * Unified Microsoft productivity suite integration
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
} from "@chakra-ui/react";
import {
  ChatIcon,
  MailIcon,
  FolderIcon,
  CalendarIcon,
  SettingsIcon,
  ExternalLinkIcon,
  SearchIcon,
  AddIcon,
  RepeatIcon,
  PhoneIcon,
  UserIcon,
  TimeIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  LinkIcon,
  CheckCircleIcon,
  WarningIcon,
  InfoIcon,
} from "@chakra-ui/icons";

interface M365Service {
  name: string;
  displayName: string;
  description: string;
  status: "connected" | "disconnected" | "error";
  icon: any;
  color: string;
  endpoint: string;
  healthEndpoint: string;
}

interface OutlookEmail {
  id: string;
  subject: string;
  from: string;
  fromEmail: string;
  to: string;
  body: string;
  receivedTime: string;
  isRead: boolean;
  hasAttachments: boolean;
  importance: string;
}

interface TeamsMessage {
  id: string;
  teamName: string;
  channelName: string;
  from: string;
  fromEmail: string;
  content: string;
  messageType: string;
  timestamp: string;
  replyCount: number;
  hasAttachments: boolean;
}

interface OneDriveFile {
  id: string;
  name: string;
  type: string;
  size: number;
  modifiedTime: string;
  parentPath: string;
  sharingStatus: string;
  webUrl: string;
}

interface CalendarEvent {
  id: string;
  subject: string;
  startTime: string;
  endTime: string;
  isAllDay: boolean;
  location: string;
  organizer: string;
  attendees: string[];
  status: string;
  importance: string;
}

const Microsoft365Integration: React.FC = () => {
  const [services, setServices] = useState<M365Service[]>([
    {
      name: "outlook",
      displayName: "Outlook",
      description: "Email, calendar, and contacts",
      status: "disconnected",
      icon: MailIcon,
      color: "blue",
      endpoint: "/integrations/outlook",
      healthEndpoint: "/api/integrations/microsoft/health",
    },
    {
      name: "teams",
      displayName: "Teams",
      description: "Team collaboration and meetings",
      status: "disconnected",
      icon: ChatIcon,
      color: "purple",
      endpoint: "/integrations/teams",
      healthEndpoint: "/api/integrations/teams/health",
    },
    {
      name: "onedrive",
      displayName: "OneDrive",
      description: "Cloud storage and file sharing",
      status: "disconnected",
      icon: FolderIcon,
      color: "orange",
      endpoint: "/integrations/onedrive",
      healthEndpoint: "/api/onedrive/health",
    },
  ]);

  const [emails, setEmails] = useState<OutlookEmail[]>([]);
  const [messages, setMessages] = useState<TeamsMessage[]>([]);
  const [files, setFiles] = useState<OneDriveFile[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState({
    emails: false,
    messages: false,
    files: false,
    events: false,
    services: false,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedService, setSelectedService] = useState("");

  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check service health
  const checkServiceHealth = async (service: M365Service) => {
    try {
      const response = await fetch(service.healthEndpoint);
      if (response.ok) {
        return "connected";
      } else {
        return "error";
      }
    } catch (error) {
      console.error(`Health check failed for ${service.name}:`, error);
      return "error";
    }
  };

  // Check all services health
  const checkAllServices = async () => {
    setLoading((prev) => ({ ...prev, services: true }));
    
    const serviceHealthChecks = services.map(async (service) => {
      const health = await checkServiceHealth(service);
      return { name: service.name, health };
    });

    const healthResults = await Promise.all(serviceHealthChecks);
    
    setServices((prev) =>
      prev.map((service) => {
        const healthResult = healthResults.find(
          (result) => result.name === service.name
        );
        return {
          ...service,
          status: healthResult?.health || "error",
        };
      })
    );

    setLoading((prev) => ({ ...prev, services: false }));
  };

  // Load data for services
  const loadEmails = async () => {
    if (!services.find((s) => s.name === "outlook")?.connected) return;

    setLoading((prev) => ({ ...prev, emails: true }));
    try {
      const response = await fetch("/api/integrations/microsoft/outlook/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 25,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setEmails(data.data?.messages || []);
      }
    } catch (error) {
      console.error("Failed to load emails:", error);
    } finally {
      setLoading((prev) => ({ ...prev, emails: false }));
    }
  };

  const loadTeamsMessages = async () => {
    if (!services.find((s) => s.name === "teams")?.connected) return;

    setLoading((prev) => ({ ...prev, messages: true }));
    try {
      const response = await fetch("/api/integrations/teams/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 25,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMessages(data.data?.messages || []);
      }
    } catch (error) {
      console.error("Failed to load Teams messages:", error);
    } finally {
      setLoading((prev) => ({ ...prev, messages: false }));
    }
  };

  const loadOneDriveFiles = async () => {
    if (!services.find((s) => s.name === "onedrive")?.connected) return;

    setLoading((prev) => ({ ...prev, files: true }));
    try {
      const response = await fetch("/api/onedrive/files", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setFiles(data.data?.files || []);
      }
    } catch (error) {
      console.error("Failed to load OneDrive files:", error);
    } finally {
      setLoading((prev) => ({ ...prev, files: false }));
    }
  };

  const loadCalendarEvents = async () => {
    if (!services.find((s) => s.name === "outlook")?.connected) return;

    setLoading((prev) => ({ ...prev, events: true }));
    try {
      const response = await fetch("/api/integrations/microsoft/calendar/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 25,
          startDate: new Date().toISOString(),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setEvents(data.data?.events || []);
      }
    } catch (error) {
      console.error("Failed to load calendar events:", error);
    } finally {
      setLoading((prev) => ({ ...prev, events: false }));
    }
  };

  // Filter data based on search
  const filteredEmails = emails.filter((email) =>
    email.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
    email.from.toLowerCase().includes(searchQuery.toLowerCase()) ||
    email.body.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredMessages = messages.filter((message) =>
    message.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
    message.from.toLowerCase().includes(searchQuery.toLowerCase()) ||
    message.teamName.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredFiles = files.filter((file) =>
    file.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    file.type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredEvents = events.filter((event) =>
    event.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
    event.location.toLowerCase().includes(searchQuery.toLowerCase()) ||
    event.organizer.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Stats calculations
  const connectedServices = services.filter((s) => s.status === "connected").length;
  const totalEmails = emails.length;
  const unreadEmails = emails.filter((e) => !e.isRead).length;
  const totalMessages = messages.length;
  const totalFiles = files.length;
  const totalEvents = events.length;

  useEffect(() => {
    checkAllServices();
  }, []);

  useEffect(() => {
    if (connectedServices > 0) {
      loadEmails();
      loadTeamsMessages();
      loadOneDriveFiles();
      loadCalendarEvents();
    }
  }, [connectedServices]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case "connected":
        return "green";
      case "disconnected":
        return "gray";
      case "error":
        return "red";
      default:
        return "gray";
    }
  };

  const getImportanceColor = (importance: string): string => {
    switch (importance?.toLowerCase()) {
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

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={SettingsIcon} w={8} h={8} color="blue.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Microsoft 365 Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Complete productivity suite integration
              </Text>
            </VStack>
          </HStack>

          <HStack spacing={4}>
            <Badge colorScheme="blue" fontSize="md" px={3} py={1}>
              {connectedServices}/{services.length} Services Connected
            </Badge>
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RepeatIcon />}
              onClick={checkAllServices}
              isLoading={loading.services}
            >
              Check Status
            </Button>
          </HStack>
        </VStack>

        {/* Services Overview */}
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
          {services.map((service) => (
            <Card
              key={service.name}
              bg={bgColor}
              borderWidth="1px"
              borderColor={borderColor}
            >
              <CardHeader>
                <VStack spacing={3}>
                  <Icon
                    as={service.icon}
                    w={12}
                    h={12}
                    color={`${service.color}.500`}
                  />
                  <VStack spacing={1} align="start">
                    <Heading size="md">{service.displayName}</Heading>
                    <Text color="gray.600" fontSize="sm" textAlign="center">
                      {service.description}
                    </Text>
                  </VStack>
                </VStack>
              </CardHeader>
              <CardBody>
                <VStack spacing={4}>
                  <Badge
                    colorScheme={getStatusColor(service.status)}
                    w="100%"
                    display="flex"
                    alignItems="center"
                    justifyContent="center"
                    py={2}
                  >
                    {service.status === "connected" ? (
                      <>
                        <CheckCircleIcon mr={2} />
                        Connected
                      </>
                    ) : service.status === "error" ? (
                      <>
                        <WarningIcon mr={2} />
                        Error
                      </>
                    ) : (
                      <>
                        <InfoIcon mr={2} />
                        Not Connected
                      </>
                    )}
                  </Badge>

                  <Button
                    w="100%"
                    colorScheme={service.status === "connected" ? "gray" : service.color}
                    onClick={() => {
                      if (service.status !== "connected") {
                        window.location.href = `/integrations/${service.name}`;
                      } else {
                        window.location.href = `/integrations/${service.name}`;
                      }
                    }}
                    leftIcon={
                      service.status === "connected" ? <ViewIcon /> : <ExternalLinkIcon />
                    }
                  >
                    {service.status === "connected" ? "Manage" : "Connect"}
                  </Button>
                </VStack>
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>

        {/* Unified Stats */}
        {connectedServices > 0 && (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
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
                  <StatLabel>Teams Messages</StatLabel>
                  <StatNumber>{totalMessages}</StatNumber>
                  <StatHelpText>Recent activity</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>OneDrive Files</StatLabel>
                  <StatNumber>{totalFiles}</StatNumber>
                  <StatHelpText>Cloud storage</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Calendar Events</StatLabel>
                  <StatNumber>{totalEvents}</StatNumber>
                  <StatHelpText>Upcoming</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Unified Data View */}
        {connectedServices > 0 && (
          <Tabs variant="enclosed">
            <TabList>
              <Tab>Overview</Tab>
              {services.find((s) => s.name === "outlook")?.connected && (
                <>
                  <Tab>Email</Tab>
                  <Tab>Calendar</Tab>
                </>
              )}
              {services.find((s) => s.name === "teams")?.connected && <Tab>Teams</Tab>}
              {services.find((s) => s.name === "onedrive")?.connected && <Tab>OneDrive</Tab>}
            </TabList>

            <TabPanels>
              {/* Overview Tab */}
              <TabPanel>
                <VStack spacing={6} align="stretch">
                  <Alert status="info">
                    <InfoIcon />
                    <Text>
                      Microsoft 365 services are connected and synchronized. Click on individual service tabs to manage specific data.
                    </Text>
                  </Alert>

                  <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                    {totalEmails > 0 && (
                      <Card>
                        <CardHeader>
                          <Heading size="sm">Recent Emails</Heading>
                        </CardHeader>
                        <CardBody>
                          <VStack spacing={3} align="start">
                            {emails.slice(0, 3).map((email) => (
                              <Box key={email.id} w="100%">
                                <Text fontWeight="medium" noOfLines={1}>
                                  {email.subject}
                                </Text>
                                <Text fontSize="sm" color="gray.600">
                                  {email.from} • {formatDate(email.receivedTime)}
                                </Text>
                              </Box>
                            ))}
                          </VStack>
                        </CardBody>
                      </Card>
                    )}

                    {totalMessages > 0 && (
                      <Card>
                        <CardHeader>
                          <Heading size="sm">Teams Activity</Heading>
                        </CardHeader>
                        <CardBody>
                          <VStack spacing={3} align="start">
                            {messages.slice(0, 3).map((message) => (
                              <Box key={message.id} w="100%">
                                <Text fontWeight="medium" noOfLines={1}>
                                  {message.teamName} • {message.channelName}
                                </Text>
                                <Text fontSize="sm" color="gray.600">
                                  {message.from} • {formatDate(message.timestamp)}
                                </Text>
                              </Box>
                            ))}
                          </VStack>
                        </CardBody>
                      </Card>
                    )}

                    {totalFiles > 0 && (
                      <Card>
                        <CardHeader>
                          <Heading size="sm">Recent Files</Heading>
                        </CardHeader>
                        <CardBody>
                          <VStack spacing={3} align="start">
                            {files.slice(0, 3).map((file) => (
                              <Box key={file.id} w="100%">
                                <HStack>
                                  <Icon as={FolderIcon} color="orange.500" />
                                  <Text fontWeight="medium" noOfLines={1}>
                                    {file.name}
                                  </Text>
                                </HStack>
                                <Text fontSize="sm" color="gray.600">
                                  {formatFileSize(file.size)} • {formatDate(file.modifiedTime)}
                                </Text>
                              </Box>
                            ))}
                          </VStack>
                        </CardBody>
                      </Card>
                    )}

                    {totalEvents > 0 && (
                      <Card>
                        <CardHeader>
                          <Heading size="sm">Upcoming Events</Heading>
                        </CardHeader>
                        <CardBody>
                          <VStack spacing={3} align="start">
                            {events.slice(0, 3).map((event) => (
                              <Box key={event.id} w="100%">
                                <Text fontWeight="medium" noOfLines={1}>
                                  {event.subject}
                                </Text>
                                <Text fontSize="sm" color="gray.600">
                                  {formatDate(event.startTime)} • {event.location}
                                </Text>
                              </Box>
                            ))}
                          </VStack>
                        </CardBody>
                      </Card>
                    )}
                  </SimpleGrid>
                </VStack>
              </TabPanel>

              {/* Email Tab */}
              <TabPanel>
                <VStack spacing={6} align="stretch">
                  <Card>
                    <CardBody>
                      <Input
                        placeholder="Search emails..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                    </CardBody>
                  </Card>

                  <Card>
                    <CardBody>
                      {loading.emails ? (
                        <VStack spacing={4} py={8}>
                          <Text>Loading emails...</Text>
                          <Progress size="sm" isIndeterminate width="100%" />
                        </VStack>
                      ) : filteredEmails.length === 0 ? (
                        <VStack spacing={4} py={8}>
                          <Icon as={MailIcon} w={12} h={12} color="gray.400" />
                          <Text color="gray.600">No emails found</Text>
                        </VStack>
                      ) : (
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Subject</Th>
                                <Th>From</Th>
                                <Th>Received</Th>
                                <Th>Importance</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {filteredEmails.map((email) => (
                                <Tr key={email.id}>
                                  <Td>
                                    <VStack align="start" spacing={1}>
                                      <Text
                                        fontWeight={email.isRead ? "normal" : "bold"}
                                        noOfLines={1}
                                      >
                                        {email.subject}
                                      </Text>
                                      {email.hasAttachments && (
                                        <Icon as={LinkIcon} w={3} h={3} color="gray.500" />
                                      )}
                                    </VStack>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{email.from}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatDate(email.receivedTime)}</Text>
                                  </Td>
                                  <Td>
                                    <Tag
                                      colorScheme={getImportanceColor(email.importance)}
                                      size="sm"
                                    >
                                      <TagLabel>{email.importance || "Normal"}</TagLabel>
                                    </Tag>
                                  </Td>
                                  <Td>
                                    <Button size="sm" variant="outline">
                                      View
                                    </Button>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
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
                      {loading.events ? (
                        <VStack spacing={4} py={8}>
                          <Text>Loading calendar events...</Text>
                          <Progress size="sm" isIndeterminate width="100%" />
                        </VStack>
                      ) : filteredEvents.length === 0 ? (
                        <VStack spacing={4} py={8}>
                          <Icon as={CalendarIcon} w={12} h={12} color="gray.400" />
                          <Text color="gray.600">No upcoming events</Text>
                        </VStack>
                      ) : (
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Subject</Th>
                                <Th>Start</Th>
                                <Th>End</Th>
                                <Th>Location</Th>
                                <Th>Organizer</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {filteredEvents.map((event) => (
                                <Tr key={event.id}>
                                  <Td>
                                    <Text fontWeight="medium">{event.subject}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatDate(event.startTime)}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatDate(event.endTime)}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{event.location || "N/A"}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{event.organizer}</Text>
                                  </Td>
                                  <Td>
                                    <Button size="sm" variant="outline">
                                      View
                                    </Button>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      )}
                    </CardBody>
                  </Card>
                </VStack>
              </TabPanel>

              {/* Teams Tab */}
              <TabPanel>
                <VStack spacing={6} align="stretch">
                  <Card>
                    <CardBody>
                      {loading.messages ? (
                        <VStack spacing={4} py={8}>
                          <Text>Loading Teams messages...</Text>
                          <Progress size="sm" isIndeterminate width="100%" />
                        </VStack>
                      ) : filteredMessages.length === 0 ? (
                        <VStack spacing={4} py={8}>
                          <Icon as={ChatIcon} w={12} h={12} color="gray.400" />
                          <Text color="gray.600">No messages found</Text>
                        </VStack>
                      ) : (
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Message</Th>
                                <Th>Team/Channel</Th>
                                <Th>From</Th>
                                <Th>Time</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {filteredMessages.map((message) => (
                                <Tr key={message.id}>
                                  <Td>
                                    <Text noOfLines={2}>{message.content}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">
                                      {message.teamName}/{message.channelName}
                                    </Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{message.from}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatDate(message.timestamp)}</Text>
                                  </Td>
                                  <Td>
                                    <Button size="sm" variant="outline">
                                      View
                                    </Button>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      )}
                    </CardBody>
                  </Card>
                </VStack>
              </TabPanel>

              {/* OneDrive Tab */}
              <TabPanel>
                <VStack spacing={6} align="stretch">
                  <Card>
                    <CardBody>
                      {loading.files ? (
                        <VStack spacing={4} py={8}>
                          <Text>Loading OneDrive files...</Text>
                          <Progress size="sm" isIndeterminate width="100%" />
                        </VStack>
                      ) : filteredFiles.length === 0 ? (
                        <VStack spacing={4} py={8}>
                          <Icon as={FolderIcon} w={12} h={12} color="gray.400" />
                          <Text color="gray.600">No files found</Text>
                        </VStack>
                      ) : (
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Type</Th>
                                <Th>Size</Th>
                                <Th>Modified</Th>
                                <Th>Sharing</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {filteredFiles.map((file) => (
                                <Tr key={file.id}>
                                  <Td>
                                    <HStack>
                                      <Icon as={FolderIcon} color="orange.500" />
                                      <Text fontWeight="medium">{file.name}</Text>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Badge colorScheme="blue" size="sm">
                                      {file.type}
                                    </Badge>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatFileSize(file.size)}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatDate(file.modifiedTime)}</Text>
                                  </Td>
                                  <Td>
                                    <Badge
                                      colorScheme={
                                        file.sharingStatus === "shared"
                                          ? "green"
                                          : "gray"
                                      }
                                      size="sm"
                                    >
                                      {file.sharingStatus}
                                    </Badge>
                                  </Td>
                                  <Td>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      leftIcon={<ExternalLinkIcon />}
                                      onClick={() => window.open(file.webUrl)}
                                    >
                                      Open
                                    </Button>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      )}
                    </CardBody>
                  </Card>
                </VStack>
              </TabPanel>
            </TabPanels>
          </Tabs>
        )}
      </VStack>
    </Box>
  );
};

export default Microsoft365Integration;