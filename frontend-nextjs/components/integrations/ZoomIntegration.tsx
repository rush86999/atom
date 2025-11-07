import React, { useState, useEffect } from "react";
import {
  Box,
  Button,
  VStack,
  HStack,
  Text,
  Heading,
  Spinner,
  Alert,
  AlertIcon,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  IconButton,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Card,
  CardBody,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  useToast,
} from "@chakra-ui/react";
import {
  CalendarIcon,
  TimeIcon,
  CheckCircleIcon,
  WarningIcon,
  ExternalLinkIcon,
  RepeatIcon,
  AddIcon,
  ViewIcon,
  DownloadIcon,
} from "@chakra-ui/icons";

interface ZoomMeeting {
  id: string;
  topic: string;
  start_time: string;
  duration: number;
  timezone: string;
  join_url: string;
  password?: string;
  agenda?: string;
  created_at: string;
  status: "scheduled" | "live" | "completed" | "cancelled";
}

interface ZoomUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  type: number;
  status: "active" | "inactive" | "pending";
}

interface ZoomRecording {
  id: string;
  meeting_id: string;
  topic: string;
  start_time: string;
  duration: number;
  file_size: number;
  download_url: string;
}

interface ZoomConnectionStatus {
  is_connected: boolean;
  user_info?: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
  };
  reason?: string;
}

interface MeetingAnalytics {
  period: {
    from: string;
    to: string;
  };
  total_meetings: number;
  total_participants: number;
  average_duration: number;
  meetings_by_type: {
    scheduled: number;
    instant: number;
    recurring: number;
  };
}

const ZoomIntegration: React.FC = () => {
  const [connectionStatus, setConnectionStatus] =
    useState<ZoomConnectionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [meetings, setMeetings] = useState<ZoomMeeting[]>([]);
  const [users, setUsers] = useState<ZoomUser[]>([]);
  const [recordings, setRecordings] = useState<ZoomRecording[]>([]);
  const [analytics, setAnalytics] = useState<MeetingAnalytics | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const fetchConnectionStatus = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch("/api/zoom/connection-status");
      if (response.ok) {
        const data = await response.json();
        setConnectionStatus(data);
      } else {
        throw new Error("Failed to fetch connection status");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
      setConnectionStatus({ is_connected: false, reason: "Connection failed" });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchMeetings = async () => {
    if (!connectionStatus?.is_connected) return;

    try {
      setIsLoadingData(true);
      const response = await fetch(
        "/api/zoom/meetings?user_id=me&type=scheduled",
      );
      if (response.ok) {
        const data = await response.json();
        setMeetings(data.meetings || []);
      } else {
        throw new Error("Failed to fetch meetings");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load meetings");
      setMeetings([]);
    } finally {
      setIsLoadingData(false);
    }
  };

  const fetchUsers = async () => {
    if (!connectionStatus?.is_connected) return;

    try {
      setIsLoadingData(true);
      const response = await fetch("/api/zoom/users?page_size=50");
      if (response.ok) {
        const data = await response.json();
        setUsers(data.users || []);
      } else {
        throw new Error("Failed to fetch users");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
      setUsers([]);
    } finally {
      setIsLoadingData(false);
    }
  };

  const fetchRecordings = async () => {
    if (!connectionStatus?.is_connected) return;

    try {
      setIsLoadingData(true);
      const fromDate = new Date();
      fromDate.setDate(fromDate.getDate() - 30); // Last 30 days
      const toDate = new Date();

      const response = await fetch(
        `/api/zoom/recordings?user_id=me&from_date=${fromDate.toISOString().split("T")[0]}&to_date=${toDate.toISOString().split("T")[0]}`,
      );
      if (response.ok) {
        const data = await response.json();
        setRecordings(data.recordings || []);
      } else {
        throw new Error("Failed to fetch recordings");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load recordings",
      );
      setRecordings([]);
    } finally {
      setIsLoadingData(false);
    }
  };

  const fetchAnalytics = async () => {
    if (!connectionStatus?.is_connected) return;

    try {
      const fromDate = new Date();
      fromDate.setDate(fromDate.getDate() - 30);
      const toDate = new Date();

      const response = await fetch(
        `/api/zoom/analytics/meetings?from_date=${fromDate.toISOString().split("T")[0]}&to_date=${toDate.toISOString().split("T")[0]}`,
      );
      if (response.ok) {
        const data = await response.json();
        setAnalytics(data);
      }
    } catch (err) {
      console.error("Failed to fetch analytics:", err);
    }
  };

  const handleConnectZoom = async () => {
    try {
      // In a real implementation, this would redirect to Zoom OAuth
      // For now, we'll simulate connection
      toast({
        title: "Connecting to Zoom",
        description: "Redirecting to Zoom for authentication...",
        status: "info",
        duration: 3000,
        isClosable: true,
      });

      // Simulate connection success
      setTimeout(() => {
        setConnectionStatus({
          is_connected: true,
          user_info: {
            id: "user123",
            email: "user@example.com",
            first_name: "Zoom",
            last_name: "User",
          },
        });
        toast({
          title: "Connected to Zoom",
          description: "Successfully connected to your Zoom account",
          status: "success",
          duration: 3000,
          isClosable: true,
        });
      }, 2000);
    } catch (err) {
      toast({
        title: "Connection failed",
        description:
          err instanceof Error ? err.message : "Failed to connect to Zoom",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const handleDisconnectZoom = async () => {
    try {
      const response = await fetch("/api/zoom/auth/disconnect", {
        method: "POST",
      });

      if (response.ok) {
        setConnectionStatus({ is_connected: false });
        setMeetings([]);
        setUsers([]);
        setRecordings([]);
        setAnalytics(null);

        toast({
          title: "Disconnected",
          description: "Successfully disconnected from Zoom",
          status: "success",
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error("Failed to disconnect");
      }
    } catch (err) {
      toast({
        title: "Disconnect failed",
        description:
          err instanceof Error ? err.message : "Failed to disconnect from Zoom",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const handleCreateMeeting = async () => {
    try {
      const meetingData = {
        topic: "ATOM Integration Meeting",
        duration: 30,
        timezone: "UTC",
        agenda: "Meeting created via ATOM integration",
      };

      const response = await fetch("/api/zoom/meetings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(meetingData),
      });

      if (response.ok) {
        const data = await response.json();
        toast({
          title: "Meeting created",
          description: `Meeting "${data.meeting.topic}" created successfully`,
          status: "success",
          duration: 5000,
          isClosable: true,
        });
        fetchMeetings(); // Refresh meetings list
      } else {
        throw new Error("Failed to create meeting");
      }
    } catch (err) {
      toast({
        title: "Failed to create meeting",
        description:
          err instanceof Error ? err.message : "Unknown error occurred",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (minutes: number) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
  };

  const formatFileSize = (bytes: number) => {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  useEffect(() => {
    fetchConnectionStatus();
  }, []);

  useEffect(() => {
    if (connectionStatus?.is_connected) {
      fetchMeetings();
      fetchUsers();
      fetchRecordings();
      fetchAnalytics();
    }
  }, [connectionStatus]);

  if (isLoading) {
    return (
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Checking Zoom connection status...</Text>
      </Box>
    );
  }

  if (!connectionStatus?.is_connected) {
    return (
      <Box>
        <VStack spacing={6} align="stretch">
          <Heading size="lg">Zoom Integration</Heading>

          <Alert status="warning">
            <AlertIcon />
            Zoom integration is not connected
          </Alert>

          <Card>
            <CardBody>
              <VStack spacing={4} align="start">
                <Text>
                  Connect your Zoom account to manage meetings, users, and
                  recordings directly from ATOM.
                </Text>
                <Text fontSize="sm" color="gray.600">
                  Features include:
                </Text>
                <VStack spacing={2} align="start" pl={4}>
                  <Text fontSize="sm">• Create and manage Zoom meetings</Text>
                  <Text fontSize="sm">
                    • View meeting analytics and recordings
                  </Text>
                  <Text fontSize="sm">• Manage Zoom users and settings</Text>
                  <Text fontSize="sm">• Real-time webhook notifications</Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  leftIcon={<CalendarIcon />}
                  onClick={handleConnectZoom}
                >
                  Connect Zoom Account
                </Button>
              </VStack>
            </CardBody>
          </Card>
        </VStack>
      </Box>
    );
  }

  return (
    <Box>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <VStack align="start" spacing={1}>
            <Heading size="lg">Zoom Integration</Heading>
            <HStack>
              <Badge colorScheme="green" variant="solid">
                Connected
              </Badge>
              <Text fontSize="sm" color="gray.600">
                {connectionStatus.user_info?.email}
              </Text>
            </HStack>
          </VStack>
          <HStack>
            <Button
              leftIcon={<RepeatIcon />}
              variant="outline"
              onClick={() => {
                fetchMeetings();
                fetchUsers();
                fetchRecordings();
                fetchAnalytics();
              }}
            >
              Refresh
            </Button>
            <Button
              colorScheme="red"
              variant="outline"
              onClick={handleDisconnectZoom}
            >
              Disconnect
            </Button>
          </HStack>
        </HStack>

        {error && (
          <Alert status="error">
            <AlertIcon />
            {error}
          </Alert>
        )}

        {/* Analytics Overview */}
        {analytics && (
          <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Total Meetings</StatLabel>
                  <StatNumber>{analytics.total_meetings}</StatNumber>
                  <StatHelpText>Last 30 days</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Participants</StatLabel>
                  <StatNumber>{analytics.total_participants}</StatNumber>
                  <StatHelpText>Last 30 days</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Avg Duration</StatLabel>
                  <StatNumber>{analytics.average_duration}m</StatNumber>
                  <StatHelpText>Per meeting</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Scheduled</StatLabel>
                  <StatNumber>
                    {analytics.meetings_by_type.scheduled}
                  </StatNumber>
                  <StatHelpText>Meetings</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Main Content Tabs */}
        <Tabs variant="enclosed" onChange={(index) => setActiveTab(index)}>
          <TabList>
            <Tab>Meetings</Tab>
            <Tab>Users</Tab>
            <Tab>Recordings</Tab>
            <Tab>Analytics</Tab>
          </TabList>

          <TabPanels>
            {/* Meetings Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Heading size="md">Meetings</Heading>
                  <Button
                    leftIcon={<AddIcon />}
                    colorScheme="blue"
                    onClick={handleCreateMeeting}
                  >
                    Create Meeting
                  </Button>
                </HStack>

                {isLoadingData ? (
                  <Box textAlign="center" py={8}>
                    <Spinner />
                    <Text mt={2}>Loading meetings...</Text>
                  </Box>
                ) : meetings.length === 0 ? (
                  <Alert status="info">
                    <AlertIcon />
                    No meetings found
                  </Alert>
                ) : (
                  <Card>
                    <CardBody p={0}>
                      <Table variant="simple">
                        <Thead>
                          <Tr>
                            <Th>Topic</Th>
                            <Th>Start Time</Th>
                            <Th>Duration</Th>
                            <Th>Status</Th>
                            <Th>Actions</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {meetings.map((meeting) => (
                            <Tr key={meeting.id}>
                              <Td>
                                <Text fontWeight="medium">{meeting.topic}</Text>
                                {meeting.agenda && (
                                  <Text
                                    fontSize="sm"
                                    color="gray.600"
                                    noOfLines={1}
                                  >
                                    {meeting.agenda}
                                  </Text>
                                )}
                              </Td>
                              <Td>{formatDate(meeting.start_time)}</Td>
                              <Td>{formatDuration(meeting.duration)}</Td>
                              <Td>
                                <Badge
                                  colorScheme={
                                    meeting.status === "scheduled"
                                      ? "blue"
                                      : meeting.status === "live"
                                        ? "green"
                                        : meeting.status === "completed"
                                          ? "gray"
                                          : "red"
                                  }
                                >
                                  {meeting.status}
                                </Badge>
                              </Td>
                              <Td>
                                <HStack spacing={2}>
                                  <IconButton
                                    aria-label="Join meeting"
                                    icon={<ExternalLinkIcon />}
                                    size="sm"
                                    variant="outline"
                                    onClick={() =>
                                      window.open(meeting.join_url, "_blank")
                                    }
                                  />
                                  <IconButton
                                    aria-label="View details"
                                    icon={<ViewIcon />}
                                    size="sm"
                                    variant="outline"
                                  />
                                </HStack>
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Users Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Heading size="md">Zoom Users</Heading>

                {isLoadingData ? (
                  <Box textAlign="center" py={8}>
                    <Spinner />
                    <Text mt={2}>Loading users...</Text>
                  </Box>
                ) : users.length === 0 ? (
                  <Alert status="info">
                    <AlertIcon />
                    No users found
                  </Alert>
                ) : (
                  <Card>
                    <CardBody p={0}>
                      <Table variant="simple">
                        <Thead>
                          <Tr>
                            <Th>Name</Th>
                            <Th>Email</Th>
                            <Th>Type</Th>
                            <Th>Status</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {users.map((user) => (
                            <Tr key={user.id}>
                              <Td>
                                <Text fontWeight="medium">
                                  {user.first_name} {user.last_name}
                                </Text>
                              </Td>
                              <Td>{user.email}</Td>
                              <Td>
                                <Badge
                                  colorScheme={
                                    user.type === 2 ? "blue" : "gray"
                                  }
                                >
                                  {user.type === 2 ? "Licensed" : "Basic"}
                                </Badge>
                              </Td>
                              <Td>
                                <Badge
                                  colorScheme={
                                    user.status === "active"
                                      ? "green"
                                      : user.status === "inactive"
                                        ? "red"
                                        : "yellow"
                                  }
                                >
                                  {user.status}
                                </Badge>
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Recordings Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Heading size="md">Recordings</Heading>

                {isLoadingData ? (
                  <Box textAlign="center" py={8}>
                    <Spinner />
                    <Text mt={2}>Loading recordings...</Text>
                  </Box>
                ) : recordings.length === 0 ? (
                  <Alert status="info">
                    <AlertIcon />
                    No recordings found
                  </Alert>
                ) : (
                  <Card>
                    <CardBody p={0}>
                      <Table variant="simple">
                        <Thead>
                          <Tr>
                            <Th>Topic</Th>
                            <Th>Date</Th>
                            <Th>Duration</Th>
                            <Th>Size</Th>
                            <Th>Actions</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {recordings.map((recording) => (
                            <Tr key={recording.id}>
                              <Td>
                                <Text fontWeight="medium">
                                  {recording.topic}
                                </Text>
                              </Td>
                              <Td>{formatDate(recording.start_time)}</Td>
                              <Td>{formatDuration(recording.duration)}</Td>
                              <Td>{formatFileSize(recording.file_size)}</Td>
                              <Td>
                                <IconButton
                                  aria-label="Download recording"
                                  icon={<DownloadIcon />}
                                  size="sm"
                                  variant="outline"
                                  onClick={() =>
                                    window.open(
                                      recording.download_url,
                                      "_blank",
                                    )
                                  }
                                />
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Analytics Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Heading size="md">Meeting Analytics</Heading>

                {analytics ? (
                  <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="start">
                          <Heading size="sm">Meeting Types</Heading>
                          <VStack spacing={2} align="start" width="100%">
                            <HStack justify="space-between" width="100%">
                              <Text>Scheduled Meetings</Text>
                              <Badge colorScheme="blue">
                                {analytics.meetings_by_type.scheduled}
                              </Badge>
                            </HStack>
                            <HStack justify="space-between" width="100%">
                              <Text>Instant Meetings</Text>
                              <Badge colorScheme="green">
                                {analytics.meetings_by_type.instant}
                              </Badge>
                            </HStack>
                            <HStack justify="space-between" width="100%">
                              <Text>Recurring Meetings</Text>
                              <Badge colorScheme="purple">
                                {analytics.meetings_by_type.recurring}
                              </Badge>
                            </HStack>
                          </VStack>
                        </VStack>
                      </CardBody>
                    </Card>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="start">
                          <Heading size="sm">Performance Metrics</Heading>
                          <VStack spacing={2} align="start" width="100%">
                            <HStack justify="space-between" width="100%">
                              <Text>Total Participants</Text>
                              <Text fontWeight="bold">
                                {analytics.total_participants}
                              </Text>
                            </HStack>
                            <HStack justify="space-between" width="100%">
                              <Text>Average Duration</Text>
                              <Text fontWeight="bold">
                                {analytics.average_duration} minutes
                              </Text>
                            </HStack>
                            <HStack justify="space-between" width="100%">
                              <Text>Period</Text>
                              <Text fontSize="sm">
                                {analytics.period.from} to {analytics.period.to}
                              </Text>
                            </HStack>
                          </VStack>
                        </VStack>
                      </CardBody>
                    </Card>
                  </SimpleGrid>
                ) : (
                  <Alert status="info">
                    <AlertIcon />
                    No analytics data available for the selected period
                  </Alert>
                )}
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default ZoomIntegration;
