/**
 * Google Workspace Integration Page
 * Complete Google Workspace productivity suite integration
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
  EditIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  ArrowForwardIcon,
  AddIcon,
  SearchIcon,
  SettingsIcon,
  RepeatIcon,
  TimeIcon,
  StarIcon,
  ViewIcon,
  EmailIcon,
  ChatIcon,
  CalendarIcon,
} from "@chakra-ui/icons";

interface GoogleDoc {
  id: string;
  name: string;
  mimeType: string;
  createdTime: string;
  modifiedTime: string;
  size: string;
  webViewLink: string;
  webContentLink: string;
  owners: Array<{
    displayName: string;
    email: string;
    photoLink: string;
  }>;
  permissions: Array<{
    id: string;
    type: string;
    role: string;
    emailAddress?: string;
    displayName?: string;
  }>;
  capabilities: {
    canEdit: boolean;
    canComment: boolean;
    canView: boolean;
    canCopy: boolean;
  };
  thumbnailLink?: string;
}

interface GoogleSheet {
  id: string;
  name: string;
  createdTime: string;
  modifiedTime: string;
  size: string;
  webViewLink: string;
  webContentLink: string;
  owners: Array<{
    displayName: string;
    email: string;
    photoLink: string;
  }>;
  sheets: Array<{
    properties: {
      sheetId: number;
      title: string;
      index: number;
      sheetType: string;
      gridProperties: {
        rowCount: number;
        columnCount: number;
      };
    };
  }>;
  spreadsheetId: string;
  spreadsheetUrl: string;
}

interface GoogleEvent {
  id: string;
  summary: string;
  description?: string;
  location?: string;
  start: {
    dateTime: string;
    timeZone?: string;
  };
  end: {
    dateTime: string;
    timeZone?: string;
  };
  attendees?: Array<{
    email: string;
    displayName?: string;
    responseStatus: string;
  }>;
  organizer: {
    email: string;
    displayName?: string;
  };
  created: string;
  updated: string;
  recurringEventId?: string;
  visibility: string;
  transparency: string;
  status: string;
  kind: string;
}

interface GoogleEmail {
  id: string;
  threadId: string;
  labelIds: string[];
  snippet: string;
  internalDate: string;
  payload: {
    headers: Array<{
      name: string;
      value: string;
    }>;
    mimeType: string;
    parts?: Array<{
      mimeType: string;
      body?: {
        data: string;
        size: number;
      };
    }>;
  };
  sizeEstimate: number;
  raw: string;
  historyId: string;
}

const GoogleWorkspaceIntegration: React.FC = () => {
  const [docs, setDocs] = useState<GoogleDoc[]>([]);
  const [sheets, setSheets] = useState<GoogleSheet[]>([]);
  const [events, setEvents] = useState<GoogleEvent[]>([]);
  const [emails, setEmails] = useState<GoogleEmail[]>([]);
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFolder, setSelectedFolder] = useState("");
  const [loading, setLoading] = useState({
    docs: false,
    sheets: false,
    events: false,
    emails: false,
  });

  const {
    isOpen: isDocOpen,
    onOpen: onDocOpen,
    onClose: onDocClose,
  } = useDisclosure();
  const {
    isOpen: isEventOpen,
    onOpen: onEventOpen,
    onClose: onEventClose,
  } = useDisclosure();

  const [newDoc, setNewDoc] = useState({
    title: "",
    type: "document",
    folder: "",
  });

  const [newEvent, setNewEvent] = useState({
    summary: "",
    description: "",
    location: "",
    startTime: "",
    endTime: "",
    attendees: [] as string[],
  });

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/google-workspace/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadDocs();
        loadSheets();
        loadEvents();
        loadEmails();
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

  // Load Google Workspace data
  const loadDocs = async () => {
    setLoading((prev) => ({ ...prev, docs: true }));
    try {
      const response = await fetch("/api/integrations/google-workspace/docs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
          folder: selectedFolder,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setDocs(data.data?.files || []);
      }
    } catch (error) {
      console.error("Failed to load documents:", error);
      toast({
        title: "Error",
        description: "Failed to load documents from Google Workspace",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, docs: false }));
    }
  };

  const loadSheets = async () => {
    setLoading((prev) => ({ ...prev, sheets: true }));
    try {
      const response = await fetch("/api/integrations/google-workspace/sheets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setSheets(data.data?.files || []);
      }
    } catch (error) {
      console.error("Failed to load sheets:", error);
    } finally {
      setLoading((prev) => ({ ...prev, sheets: false }));
    }
  };

  const loadEvents = async () => {
    setLoading((prev) => ({ ...prev, events: true }));
    try {
      const response = await fetch("/api/integrations/google-workspace/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
          start_date: new Date().toISOString(),
          end_date: new Date(
            Date.now() + 7 * 24 * 60 * 60 * 1000
          ).toISOString(),
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

  const loadEmails = async () => {
    setLoading((prev) => ({ ...prev, emails: true }));
    try {
      const response = await fetch("/api/integrations/google-workspace/emails", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
          label_ids: ["INBOX"],
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

  const createDoc = async () => {
    if (!newDoc.title) return;

    try {
      const response = await fetch("/api/integrations/google-workspace/docs/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          title: newDoc.title,
          type: newDoc.type,
          folder: newDoc.folder,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: `${newDoc.type} created successfully`,
          status: "success",
          duration: 3000,
        });
        onDocClose();
        setNewDoc({ title: "", type: "document", folder: "" });
        loadDocs();
      }
    } catch (error) {
      console.error("Failed to create document:", error);
      toast({
        title: "Error",
        description: "Failed to create document",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createEvent = async () => {
    if (!newEvent.summary || !newEvent.startTime || !newEvent.endTime) return;

    try {
      const response = await fetch("/api/integrations/google-workspace/events/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          summary: newEvent.summary,
          description: newEvent.description,
          location: newEvent.location,
          start: { dateTime: newEvent.startTime },
          end: { dateTime: newEvent.endTime },
          attendees: newEvent.attendees.map(email => ({ email })),
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Event created successfully",
          status: "success",
          duration: 3000,
        });
        onEventClose();
        setNewEvent({
          summary: "",
          description: "",
          location: "",
          startTime: "",
          endTime: "",
          attendees: [],
        });
        loadEvents();
      }
    } catch (error) {
      console.error("Failed to create event:", error);
      toast({
        title: "Error",
        description: "Failed to create event",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredDocs = docs.filter(
    (doc) =>
      doc.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredSheets = sheets.filter(
    (sheet) =>
      sheet.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredEvents = events.filter(
    (event) =>
      event.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
      event.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      event.location?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Stats calculations
  const totalDocs = docs.length;
  const totalSheets = sheets.length;
  const totalEvents = events.length;
  const totalEmails = emails.length;
  const upcomingEvents = events.filter(
    (event) => new Date(event.start.dateTime) > new Date()
  ).length;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadDocs();
      loadSheets();
      loadEvents();
      loadEmails();
    }
  }, [connected]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const getMimeTypeIcon = (mimeType: string): any => {
    if (mimeType === "application/vnd.google-apps.document") {
      return EditIcon;
    } else if (mimeType === "application/vnd.google-apps.spreadsheet") {
      return SettingsIcon;
    } else if (mimeType === "application/vnd.google-apps.presentation") {
      return ViewIcon;
    } else if (mimeType === "application/pdf") {
      return ViewIcon;
    } else {
      return TimeIcon;
    }
  };

  const getMimeTypeColor = (mimeType: string): string => {
    if (mimeType === "application/vnd.google-apps.document") {
      return "blue";
    } else if (mimeType === "application/vnd.google-apps.spreadsheet") {
      return "green";
    } else if (mimeType === "application/vnd.google-apps.presentation") {
      return "orange";
    } else if (mimeType === "application/pdf") {
      return "red";
    } else {
      return "gray";
    }
  };

  const getResponseStatusColor = (status: string): string => {
    switch (status) {
      case "accepted":
        return "green";
      case "tentative":
        return "yellow";
      case "declined":
        return "red";
      case "needsAction":
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
            <Icon as={EditIcon} w={8} h={8} color="blue.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Google Workspace Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Complete productivity suite (Docs, Sheets, Slides, Keep, Tasks)
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
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={EditIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Google Workspace</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Google Workspace account to start managing documents,
                    spreadsheets, calendars, and emails
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/google-workspace/auth/start")
                  }
                >
                  Connect Google Workspace
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
                    <StatLabel>Documents</StatLabel>
                    <StatNumber>{totalDocs}</StatNumber>
                    <StatHelpText>Google Docs files</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Spreadsheets</StatLabel>
                    <StatNumber>{totalSheets}</StatNumber>
                    <StatHelpText>Google Sheets files</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Events</StatLabel>
                    <StatNumber>{upcomingEvents}</StatNumber>
                    <StatHelpText>{totalEvents} total</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Emails</StatLabel>
                    <StatNumber>{totalEmails}</StatNumber>
                    <StatHelpText>In Gmail</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Documents</Tab>
                <Tab>Spreadsheets</Tab>
                <Tab>Calendar</Tab>
                <Tab>Gmail</Tab>
              </TabList>

              <TabPanels>
                {/* Documents Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search documents..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onDocOpen}
                      >
                        Create Document
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {loading.docs ? (
                            <Spinner size="xl" />
                          ) : (
                            filteredDocs.map((doc) => (
                              <HStack
                                key={doc.id}
                                p={4}
                                borderWidth="1px"
                                borderRadius="md"
                                _hover={{ bg: "gray.50" }}
                                cursor="pointer"
                                onClick={() => window.open(doc.webViewLink, "_blank")}
                              >
                                <Icon
                                  as={getMimeTypeIcon(doc.mimeType)}
                                  w={6}
                                  h={6}
                                  color={getMimeTypeColor(doc.mimeType)}
                                />
                                <VStack align="start" spacing={1} flex={1}>
                                  <Text fontWeight="bold">{doc.name}</Text>
                                  <HStack>
                                    <Tag
                                      colorScheme={getMimeTypeColor(doc.mimeType)}
                                      size="sm"
                                    >
                                      {doc.mimeType.includes("document")
                                        ? "Document"
                                        : doc.mimeType.includes("spreadsheet")
                                          ? "Spreadsheet"
                                          : doc.mimeType.includes("presentation")
                                            ? "Presentation"
                                            : "File"}
                                    </Tag>
                                    <Text fontSize="xs" color="gray.500">
                                      {formatDate(doc.modifiedTime)}
                                    </Text>
                                  </HStack>
                                  {doc.owners.length > 0 && (
                                    <HStack>
                                      <Avatar
                                        src={doc.owners[0]?.photoLink}
                                        name={doc.owners[0]?.displayName}
                                        size="xs"
                                      />
                                      <Text fontSize="xs" color="gray.500">
                                        {doc.owners[0]?.displayName}
                                      </Text>
                                    </HStack>
                                  )}
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

                {/* Spreadsheets Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search spreadsheets..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {loading.sheets ? (
                            <Spinner size="xl" />
                          ) : (
                            filteredSheets.map((sheet) => (
                              <HStack
                                key={sheet.id}
                                p={4}
                                borderWidth="1px"
                                borderRadius="md"
                                _hover={{ bg: "gray.50" }}
                                cursor="pointer"
                                onClick={() => window.open(sheet.webViewLink, "_blank")}
                              >
                                <Icon as={SettingsIcon} w={6} h={6} color="green.500" />
                                <VStack align="start" spacing={1} flex={1}>
                                  <Text fontWeight="bold">{sheet.name}</Text>
                                  <HStack>
                                    <Tag colorScheme="green" size="sm">
                                      Spreadsheet
                                    </Tag>
                                    <Text fontSize="xs" color="gray.500">
                                      {formatDate(sheet.modifiedTime)}
                                    </Text>
                                  </HStack>
                                  {sheet.sheets.length > 0 && (
                                    <Text fontSize="xs" color="gray.500">
                                      {sheet.sheets.length} sheets
                                    </Text>
                                  )}
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

                {/* Calendar Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search events..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onEventOpen}
                      >
                        Create Event
                      </Button>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.events ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredEvents.map((event) => (
                          <Card key={event.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <Icon as={CalendarIcon} w={6} h={6} color="blue.500" />
                                <VStack align="start" spacing={2} flex={1}>
                                  <Text fontWeight="bold">{event.summary}</Text>
                                  {event.description && (
                                    <Text fontSize="sm" color="gray.600">
                                      {event.description}
                                    </Text>
                                  )}
                                  <HStack>
                                    <Text fontSize="sm" color="gray.500">
                                      {formatDate(event.start.dateTime)} -{" "}
                                      {formatDate(event.end.dateTime)}
                                    </Text>
                                  </HStack>
                                  {event.location && (
                                    <Text fontSize="sm" color="gray.500">
                                      📍 {event.location}
                                    </Text>
                                  )}
                                  {event.attendees && event.attendees.length > 0 && (
                                    <HStack wrap="wrap">
                                      {event.attendees.map((attendee) => (
                                        <Tag
                                          key={attendee.email}
                                          colorScheme={getResponseStatusColor(
                                            attendee.responseStatus
                                          )}
                                          size="sm"
                                        >
                                          {attendee.displayName || attendee.email}
                                        </Tag>
                                      ))}
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

                {/* Gmail Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search emails..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {loading.emails ? (
                            <Spinner size="xl" />
                          ) : (
                            emails.map((email) => (
                              <Card key={email.id}>
                                <CardBody>
                                  <HStack spacing={4} align="start">
                                    <Icon as={EmailIcon} w={6} h={6} color="red.500" />
                                    <VStack align="start" spacing={2} flex={1}>
                                      <Text fontWeight="bold" fontSize="sm">
                                        {email.payload.headers.find(
                                          (h) => h.name === "Subject"
                                        )?.value || "No Subject"}
                                      </Text>
                                      <Text fontSize="sm" color="gray.600">
                                        From:{" "}
                                        {email.payload.headers.find(
                                          (h) => h.name === "From"
                                        )?.value}
                                      </Text>
                                      <Text fontSize="xs" color="gray.500">
                                        {formatDate(email.internalDate)}
                                      </Text>
                                      <Text fontSize="sm" color="gray.600">
                                        {email.snippet}
                                      </Text>
                                    </VStack>
                                  </HStack>
                                </CardBody>
                              </Card>
                            ))
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create Document Modal */}
            <Modal isOpen={isDocOpen} onClose={onDocClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Document</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Title</FormLabel>
                      <Input
                        placeholder="Enter document title"
                        value={newDoc.title}
                        onChange={(e) =>
                          setNewDoc({
                            ...newDoc,
                            title: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Type</FormLabel>
                      <Select
                        value={newDoc.type}
                        onChange={(e) =>
                          setNewDoc({
                            ...newDoc,
                            type: e.target.value,
                          })
                        }
                      >
                        <option value="document">Document</option>
                        <option value="spreadsheet">Spreadsheet</option>
                        <option value="presentation">Presentation</option>
                      </Select>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onDocClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createDoc}
                    disabled={!newDoc.title}
                  >
                    Create
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Event Modal */}
            <Modal isOpen={isEventOpen} onClose={onEventClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Event</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Summary</FormLabel>
                      <Input
                        placeholder="Event title"
                        value={newEvent.summary}
                        onChange={(e) =>
                          setNewEvent({
                            ...newEvent,
                            summary: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Event description"
                        value={newEvent.description}
                        onChange={(e) =>
                          setNewEvent({
                            ...newEvent,
                            description: e.target.value,
                          })
                        }
                        rows={3}
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
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onEventClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createEvent}
                    disabled={
                      !newEvent.summary ||
                      !newEvent.startTime ||
                      !newEvent.endTime
                    }
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

export default GoogleWorkspaceIntegration;