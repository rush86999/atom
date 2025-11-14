/**
 * Zoom Integration Page
 * Complete Zoom video conferencing and collaboration integration
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
  NumberInput,
  NumberInputField,
  Link,
  Box,
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
  AttachmentIcon,
  DownloadIcon,
  ExternalLinkIcon,
  GenericAvatarIcon,
  LockIcon,
} from "@chakra-ui/icons";

interface ZoomMeeting {
  uuid: string;
  id: number;
  topic: string;
  type: number;
  start_time: string;
  duration: number;
  timezone: string;
  agenda?: string;
  created_at: string;
  start_url: string;
  join_url: string;
  password?: string;
  settings?: {
    host_video: boolean;
    participant_video: boolean;
    cn_meeting: boolean;
    in_meeting: boolean;
    join_before_host: boolean;
    mute_upon_entry: boolean;
    watermark: boolean;
    use_pmi: boolean;
    approval_type: number;
    registration_type?: number;
    audio: string;
    auto_recording: string;
    enforce_login: boolean;
    enforce_login_domains?: string;
    alternative_hosts?: string;
    global_dial_in_countries?: string[];
    registrant_email_notification: boolean;
    meeting_authentication?: string;
    authentication_option?: string;
    authentication_domains?: string;
    encryption_type?: string;
    approved_or_denied_countries_or_regions?: {
      enable: boolean;
      method: string;
      approved_list: string[];
      denied_list: string[];
    };
    breakout_room?: {
      enable: boolean;
      rooms: Array<{
        id: number;
        name: string;
        participants: string[];
      }>;
    };
    alternative_hosts_email_notification: boolean;
    device_testing?: boolean;
    focus_mode: boolean;
    private_meeting: boolean;

    waiting_room: boolean;
    pass_enterprise_sso: boolean;
    status: string;
    jbh_time: number;
    sign_language_interpretation?: {
      enable: boolean;
      interpreters: Array<{
        email: string;
        languages: string[];
      }>;
    };
    request_permission_to_start_record?: boolean;
    allow_multiple_devices: boolean;
    global_dial_in_numbers: Array<{
      country_name: string;
      country_code: string;
      country_iso2: string;
      city: string;
      number: string;
      type: string;
    }>;
    global_dial_in_permission: string;
    personal_meeting_id: boolean;
    audio_conference_info?: {
      type: string;
      toll_number: string;
      toll_free_number: string;
    };
    language_interpretation?: {
      enable: boolean;
      interpreters: Array<{
        email: string;
        languages: string[];
      }>;
    };
    close_registration: boolean;
    show_share_button: boolean;
    allow_live_streaming: boolean;
    start_type: string;
    enable_embedded_browser: boolean;
    live_streaming_url?: string;
    certificate: string;
    calendar_type: number;
    registrants_confirmation_email?: boolean;
    calendar_template_id?: number;
    enable_host_and_cohost_powerpoint: boolean;
    meeting_authentication_exception?: Array<{
      id: string;
      user_type: string;
      name: string;
    }>;
    alternative_host_automation: string;

    allow_registration_with_phonenumber: boolean;
    allow_registration_work_email: boolean;
    allow_registration_student_email: boolean;
    allow_registration_frequently_used_email: boolean;
    allow_registration_same_domain: boolean;
    allow_registration_all_email: boolean;
    allow_registration_discussion: boolean;
    registrants_email_notification: boolean;

    registrants_require_approval: boolean;
    registrants_require_email: boolean;
    registrants_require_name: boolean;
    registrants_require_phone: boolean;
    registrants_require_company: boolean;
    registrants_require_job_title: boolean;
    registrants_require_address: boolean;
    registrants_require_city: boolean;
    registrants_require_state: boolean;
    registrants_require_zip: boolean;
    registrants_require_country: boolean;
    registrants_require_website: boolean;
    registrants_require_industry: boolean;
    registrants_require_org: boolean;
    registrants_require_role: boolean;
    registrants_require_purchase: boolean;
    registrants_require_comments: boolean;
    registrants_require_custom_questions: boolean;
  };
  participant_count?: number;
  host_email: string;
}

interface ZoomUser {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  type: number;
  role_name: string;
  pmi: number;
  use_pmi: boolean;
  vanity_url?: string;
  personal_meeting_url: string;
  timezone: string;
  verified: number;
  dept: string;
  created_at: string;
  last_login_time: string;
  pic_url?: string;
  host_key?: string;
  jid: string;
  group_ids: string[];
  im_group_ids: string[];
  account_id: number;
  account_name?: string;
  status: string;
  zoom_user_type?: string;
  enable_cloud_auto_recording: boolean;
  enable_webinar: boolean;
  enable_scheduled_webinar: boolean;
  enable_cmr: boolean;
  enable_virtual_background: boolean;
  enable_waiting_room: boolean;
  enable_recording: boolean;
  enable_hosts_email: boolean;
  enable_schedule_for_others: boolean;
  enable_breakout_room: boolean;
  enable_co_host: boolean;
  enable_auto_schedule_for_delegates: boolean;
  enable_polling: boolean;
  enable_screen_sharing: boolean;
  enable_remote_support: boolean;
  enable_file_transfer: boolean;
  enable_anonymous_join: boolean;
  enable_large_meeting: boolean;
  enable_large_webinar: boolean;
  enable_special_offer: boolean;
  enable_custom_live_streaming: boolean;
  enable_auto_schedule_meeting: boolean;
  enable_auto_schedule_webinar: boolean;
  enable_auto_schedule_meeting_for_hosts: boolean;
  enable_auto_schedule_webinar_for_hosts: boolean;
  enable_auto_schedule_meeting_for_users: boolean;
  enable_auto_schedule_webinar_for_users: boolean;
  enable_auto_schedule_meeting_for_groups: boolean;
  enable_auto_schedule_webinar_for_groups: boolean;
  enable_auto_schedule_meeting_for_admins: boolean;
  enable_auto_schedule_webinar_for_admins: boolean;
  enable_auto_schedule_meeting_for_delegates: boolean;
  enable_auto_schedule_webinar_for_delegates: boolean;
  enable_auto_schedule_meeting_for_contacts: boolean;
  enable_auto_schedule_webinar_for_contacts: boolean;
  enable_auto_schedule_meeting_for_apps: boolean;
  enable_auto_schedule_webinar_for_apps: boolean;
  enable_auto_schedule_meeting_for_channels: boolean;
  enable_auto_schedule_webinar_for_channels: boolean;
  enable_auto_schedule_meeting_for_webinars: boolean;
  enable_auto_schedule_webinar_for_webinars: boolean;
  enable_auto_schedule_meeting_for_meetings: boolean;
  enable_auto_schedule_webinar_for_meetings: boolean;
  enable_auto_schedule_meeting_for_recordings: boolean;
  enable_auto_schedule_webinar_for_recordings: boolean;
  enable_auto_schedule_meeting_for_playbacks: boolean;
  enable_auto_schedule_webinar_for_playbacks: boolean;
  enable_auto_schedule_meeting_for_cmr: boolean;
  enable_auto_schedule_webinar_for_cmr: boolean;
  enable_auto_schedule_meeting_for_shares: boolean;
  enable_auto_schedule_webinar_for_shares: boolean;
  enable_auto_schedule_meeting_for_incidents: boolean;
  enable_auto_schedule_webinar_for_incidents: boolean;
  enable_auto_schedule_meeting_for_surveys: boolean;
  enable_auto_schedule_webinar_for_surveys: boolean;
  enable_auto_schedule_meeting_for_forms: boolean;
  enable_auto_schedule_webinar_for_forms: boolean;
  enable_auto_schedule_meeting_for_polls: boolean;
  enable_auto_schedule_webinar_for_polls: boolean;
  enable_auto_schedule_meeting_for_quizzes: boolean;
  enable_auto_schedule_webinar_for_quizzes: boolean;
  enable_auto_schedule_meeting_for_reports: boolean;
  enable_auto_schedule_webinar_for_reports: boolean;
  enable_auto_schedule_meeting_for_metrics: boolean;
  enable_auto_schedule_webinar_for_metrics: boolean;
  enable_auto_schedule_meeting_for_insights: boolean;
  enable_auto_schedule_webinar_for_insights: boolean;
  enable_auto_schedule_meeting_for_analytics: boolean;
  enable_auto_schedule_webinar_for_analytics: boolean;
  enable_auto_schedule_meeting_for_dashboard?: boolean;
  enable_auto_schedule_webinar_for_dashboard?: boolean;
}

interface ZoomRecording {
  uuid: string;
  id: number;
  account_id: number;
  user_id: string;
  topic: string;
  start_time: string;
  timezone: string;
  duration: number;
  total_size: number;
  recording_files: Array<{
    id: string;
    meeting_id: string;
    recording_start: string;
    recording_end: string;
    file_type: string;
    file_size: number;
    play_url: string;
    download_url: string;
    delete_url: string;
    password: string;
    recording_type: string;
  }>;
  password?: string;
  share_url: string;
  share_password: string;
}

const ZoomIntegration: React.FC = () => {
  const [meetings, setMeetings] = useState<ZoomMeeting[]>([]);
  const [users, setUsers] = useState<ZoomUser[]>([]);
  const [recordings, setRecordings] = useState<ZoomRecording[]>([]);
  const [userProfile, setUserProfile] = useState<ZoomUser | null>(null);
  const [loading, setLoading] = useState({
    meetings: false,
    users: false,
    recordings: false,
    profile: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState("all");

  // Form states
  const [meetingForm, setMeetingForm] = useState({
    topic: "",
    type: 2, // Scheduled meeting
    start_time: "",
    duration: 60,
    timezone: "UTC",
    agenda: "",
    password: "",
    settings: {
      host_video: true,
      participant_video: true,
      join_before_host: false,
      mute_upon_entry: true,
      waiting_room: false,
      auto_recording: "none",
    },
  });

  const [userForm, setUserForm] = useState({
    email: "",
    first_name: "",
    last_name: "",
    type: 2, // Licensed user
    role_name: "Member",
    timezone: "UTC",
    enable_cloud_auto_recording: false,
    enable_recording: false,
  });

  const {
    isOpen: isMeetingOpen,
    onOpen: onMeetingOpen,
    onClose: onMeetingClose,
  } = useDisclosure();
  const {
    isOpen: isUserOpen,
    onOpen: onUserOpen,
    onClose: onUserClose,
  } = useDisclosure();

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/zoom/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadUserProfile();
        loadMeetings();
        loadUsers();
        loadRecordings();
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

  // Load Zoom data
  const loadUserProfile = async () => {
    setLoading((prev) => ({ ...prev, profile: true }));
    try {
      const response = await fetch("/api/integrations/zoom/profile", {
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

  const loadMeetings = async () => {
    setLoading((prev) => ({ ...prev, meetings: true }));
    try {
      const response = await fetch("/api/integrations/zoom/meetings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          type: "scheduled",
          page_size: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMeetings(data.data?.meetings || []);
      }
    } catch (error) {
      console.error("Failed to load meetings:", error);
      toast({
        title: "Error",
        description: "Failed to load meetings from Zoom",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, meetings: false }));
    }
  };

  const loadUsers = async () => {
    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/zoom/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          page_size: 100,
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

  const loadRecordings = async () => {
    setLoading((prev) => ({ ...prev, recordings: true }));
    try {
      const response = await fetch("/api/integrations/zoom/recordings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          page_size: 100,
          from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
            .toISOString()
            .split("T")[0],
          to: new Date().toISOString().split("T")[0],
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setRecordings(data.data?.recordings || []);
      }
    } catch (error) {
      console.error("Failed to load recordings:", error);
    } finally {
      setLoading((prev) => ({ ...prev, recordings: false }));
    }
  };

  // Create operations
  const createMeeting = async () => {
    if (!meetingForm.topic) return;

    try {
      const response = await fetch("/api/integrations/zoom/meetings/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          ...meetingForm,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Meeting created successfully",
          status: "success",
          duration: 3000,
        });
        onMeetingClose();
        setMeetingForm({
          topic: "",
          type: 2,
          start_time: "",
          duration: 60,
          timezone: "UTC",
          agenda: "",
          password: "",
          settings: {
            host_video: true,
            participant_video: true,
            join_before_host: false,
            mute_upon_entry: true,
            waiting_room: false,
            auto_recording: "none",
          },
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

  const createUser = async () => {
    if (!userForm.email) return;

    try {
      const response = await fetch("/api/integrations/zoom/users/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          ...userForm,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "User created successfully",
          status: "success",
          duration: 3000,
        });
        onUserClose();
        setUserForm({
          email: "",
          first_name: "",
          last_name: "",
          type: 2,
          role_name: "Member",
          timezone: "UTC",
          enable_cloud_auto_recording: false,
          enable_recording: false,
        });
        loadUsers();
      }
    } catch (error) {
      console.error("Failed to create user:", error);
      toast({
        title: "Error",
        description: "Failed to create user",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredMeetings = meetings.filter(
    (meeting) =>
      meeting.topic.toLowerCase().includes(searchQuery.toLowerCase()) ||
      meeting.agenda?.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredUsers = users.filter(
    (user) =>
      user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.first_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.last_name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredRecordings = recordings.filter((recording) =>
    recording.topic.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // Stats calculations
  const totalMeetings = meetings.length;
  const totalUsers = users.length;
  const totalRecordings = recordings.length;
  const upcomingMeetings = meetings.filter(
    (m) => new Date(m.start_time) > new Date(),
  ).length;
  const activeUsers = users.filter((u) => u.status === "active").length;
  const totalRecordingMinutes = recordings.reduce(
    (sum, r) => sum + r.duration,
    0,
  );

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadUserProfile();
      loadMeetings();
      loadUsers();
      loadRecordings();
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

  const getMeetingTypeColor = (type: number): string => {
    switch (type) {
      case 1:
        return "blue"; // Instant meeting
      case 2:
        return "green"; // Scheduled meeting
      case 3:
        return "orange"; // Recurring meeting with no fixed time
      case 8:
        return "purple"; // Recurring meeting with fixed time
      default:
        return "gray";
    }
  };

  const getMeetingStatusColor = (meeting: ZoomMeeting): string => {
    const now = new Date();
    const startTime = new Date(meeting.start_time);
    const endTime = new Date(
      startTime.getTime() + meeting.duration * 60 * 1000,
    );

    if (now < startTime) return "blue"; // Upcoming
    if (now >= startTime && now <= endTime) return "green"; // In progress
    return "gray"; // Ended
  };

  const getUserTypeColor = (type: number): string => {
    switch (type) {
      case 1:
        return "red"; // Basic
      case 2:
        return "blue"; // Licensed
      case 3:
        return "purple"; // On-prem
      default:
        return "gray";
    }
  };

  const getUserStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case "active":
        return "green";
      case "inactive":
        return "red";
      case "pending":
        return "yellow";
      default:
        return "gray";
    }
  };

  const formatDuration = (minutes: number): string => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
  };

  return (
    <ChakraBox minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={SettingsIcon} w={8} h={8} color="#2D8CFF" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Zoom Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Video conferencing and collaboration platform
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
              <Avatar
                src={userProfile.pic_url}
                name={`${userProfile.first_name} ${userProfile.last_name}`}
              />
              <VStack align="start" spacing={0}>
                <Text fontWeight="bold">
                  {userProfile.first_name} {userProfile.last_name}
                </Text>
                <Text fontSize="sm" color="gray.600">
                  {userProfile.email} • {userProfile.role_name}
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
                  <Heading size="lg">Connect Zoom</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Zoom account to start managing video meetings
                    and recordings
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href = "/api/integrations/zoom/auth/start")
                  }
                >
                  Connect Zoom Account
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
                    <StatLabel>Meetings</StatLabel>
                    <StatNumber>{totalMeetings}</StatNumber>
                    <StatHelpText>{upcomingMeetings} upcoming</StatHelpText>
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
                    <StatLabel>Recordings</StatLabel>
                    <StatNumber>{totalRecordings}</StatNumber>
                    <StatHelpText>
                      {formatDuration(totalRecordingMinutes)}
                    </StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Storage</StatLabel>
                    <StatNumber>2.4GB</StatNumber>
                    <StatHelpText>Used</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Meetings</Tab>
                <Tab>Users</Tab>
                <Tab>Recordings</Tab>
              </TabList>

              <TabPanels>
                {/* Meetings Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Filter by type"
                        value={selectedType}
                        onChange={(e) => setSelectedType(e.target.value)}
                        width="150px"
                      >
                        <option value="all">All Types</option>
                        <option value="1">Instant</option>
                        <option value="2">Scheduled</option>
                        <option value="3">Recurring</option>
                        <option value="8">Fixed Time</option>
                      </Select>
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

                    <Card>
                      <CardBody>
                        <Box overflowX="auto">
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Topic</Th>
                                <Th>Type</Th>
                                <Th>Start Time</Th>
                                <Th>Duration</Th>
                                <Th>Status</Th>
                                <Th>Participants</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.meetings ? (
                                <Tr>
                                  <Td colSpan={7}>
                                    <Spinner size="xl" />
                                  </Td>
                                </Tr>
                              ) : (
                                filteredMeetings.map((meeting) => (
                                  <Tr key={meeting.uuid}>
                                    <Td>
                                      <VStack align="start" spacing={1}>
                                        <Text fontWeight="bold">
                                          {meeting.topic}
                                        </Text>
                                        {meeting.agenda && (
                                          <Text fontSize="sm" color="gray.600">
                                            {meeting.agenda}
                                          </Text>
                                        )}
                                      </VStack>
                                    </Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getMeetingTypeColor(
                                          meeting.type,
                                        )}
                                        size="sm"
                                      >
                                        {meeting.type === 1
                                          ? "Instant"
                                          : meeting.type === 2
                                            ? "Scheduled"
                                            : meeting.type === 3
                                              ? "Recurring"
                                              : "Fixed Time"}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {formatDate(meeting.start_time)}
                                      </Text>
                                      <Text fontSize="xs" color="gray.500">
                                        {meeting.timezone}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {formatDuration(meeting.duration)}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getMeetingStatusColor(
                                          meeting,
                                        )}
                                        size="sm"
                                      >
                                        {new Date() <
                                        new Date(meeting.start_time)
                                          ? "Upcoming"
                                          : new Date() >=
                                                new Date(meeting.start_time) &&
                                              new Date() <=
                                                new Date(
                                                  new Date(
                                                    meeting.start_time,
                                                  ).getTime() +
                                                    meeting.duration *
                                                      60 *
                                                      1000,
                                                )
                                            ? "In Progress"
                                            : "Ended"}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {meeting.participant_count || 0}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <HStack>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          leftIcon={<GenericAvatarIcon />}
                                          onClick={() =>
                                            window.open(
                                              meeting.start_url,
                                              "_blank",
                                            )
                                          }
                                        >
                                          Start
                                        </Button>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          leftIcon={<ExternalLinkIcon />}
                                          onClick={() =>
                                            window.open(
                                              meeting.join_url,
                                              "_blank",
                                            )
                                          }
                                        >
                                          Join
                                        </Button>
                                      </HStack>
                                    </Td>
                                  </Tr>
                                ))
                              )}
                            </Tbody>
                          </Table>
                        </Box>
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
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onUserOpen}
                      >
                        Add User
                      </Button>
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.users ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredUsers.map((user) => (
                          <Card key={user.id}>
                            <CardBody>
                              <HStack spacing={4}>
                                <Avatar
                                  src={user.pic_url}
                                  name={`${user.first_name} ${user.last_name}`}
                                  size="lg"
                                />
                                <VStack align="start" spacing={1} flex={1}>
                                  <Text fontWeight="bold">
                                    {user.first_name} {user.last_name}
                                  </Text>
                                  <Text fontSize="sm" color="gray.600">
                                    {user.email}
                                  </Text>
                                  <HStack spacing={2}>
                                    <Tag
                                      colorScheme={getUserTypeColor(user.type)}
                                      size="sm"
                                    >
                                      {user.type === 1
                                        ? "Basic"
                                        : user.type === 2
                                          ? "Licensed"
                                          : "On-Prem"}
                                    </Tag>
                                    <Tag
                                      colorScheme={getUserStatusColor(
                                        user.status,
                                      )}
                                      size="sm"
                                    >
                                      {user.status}
                                    </Tag>
                                  </HStack>
                                  <Text fontSize="xs" color="gray.500">
                                    {user.role_name} • {user.timezone}
                                  </Text>
                                  <Text fontSize="xs" color="gray.500">
                                    Last login:{" "}
                                    {user.last_login_time
                                      ? formatDate(user.last_login_time)
                                      : "Never"}
                                  </Text>
                                  {user.personal_meeting_url && (
                                    <Link
                                      href={user.personal_meeting_url}
                                      target="_blank"
                                    >
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<GenericAvatarIcon />}
                                      >
                                        PMI
                                      </Button>
                                    </Link>
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

                {/* Recordings Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <InputGroup>
                        <InputLeftElement pointerEvents="none">
                          <SearchIcon color="gray.400" />
                        </InputLeftElement>
                        <Input
                          placeholder="Search recordings..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                      </InputGroup>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.recordings ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredRecordings.map((recording) => (
                          <Card key={recording.uuid}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <Icon
                                  as={GenericAvatarIcon}
                                  w={6}
                                  h={6}
                                  color="#2D8CFF"
                                />
                                <VStack spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <Text fontWeight="bold">
                                      {recording.topic}
                                    </Text>
                                    <HStack>
                                      {recording.password && (
                                        <Tag size="sm" colorScheme="orange">
                                          <LockIcon mr={1} />
                                          Password Protected
                                        </Tag>
                                      )}
                                    </HStack>
                                  </HStack>
                                  <HStack spacing={4}>
                                    <Text fontSize="sm" color="gray.500">
                                      📅 {formatDate(recording.start_time)}
                                    </Text>
                                    <Text fontSize="sm" color="gray.500">
                                      ⏱️ {formatDuration(recording.duration)}
                                    </Text>
                                    <Text fontSize="sm" color="gray.500">
                                      💾 {formatFileSize(recording.total_size)}
                                    </Text>
                                  </HStack>
                                  <HStack wrap="wrap">
                                    {recording.recording_files.map(
                                      (file, index) => (
                                        <Tag
                                          key={index}
                                          size="sm"
                                          colorScheme="gray"
                                        >
                                          {file.file_type.toUpperCase()}(
                                          {formatFileSize(file.file_size)})
                                        </Tag>
                                      ),
                                    )}
                                  </HStack>
                                  <HStack spacing={2}>
                                    {recording.recording_files.map(
                                      (file, index) => (
                                        <Button
                                          key={index}
                                          size="sm"
                                          variant="outline"
                                          leftIcon={<GenericAvatarIcon />}
                                          onClick={() =>
                                            window.open(file.play_url, "_blank")
                                          }
                                        >
                                          Play {file.file_type.toUpperCase()}
                                        </Button>
                                      ),
                                    )}
                                  </HStack>
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create Meeting Modal */}
            <Modal isOpen={isMeetingOpen} onClose={onMeetingClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Schedule Meeting</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Topic</FormLabel>
                      <Input
                        placeholder="Meeting topic"
                        value={meetingForm.topic}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            topic: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Meeting description/agenda"
                        value={meetingForm.agenda}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            agenda: e.target.value,
                          })
                        }
                        rows={3}
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
                        <FormLabel>Duration (minutes)</FormLabel>
                        <NumberInput
                          value={meetingForm.duration}
                          onChange={(value) =>
                            setMeetingForm({
                              ...meetingForm,
                              duration: parseInt(value) || 60,
                            })
                          }
                        >
                          <NumberInputField />
                        </NumberInput>
                      </FormControl>
                    </HStack>

                    <FormControl isRequired>
                      <FormLabel>Timezone</FormLabel>
                      <Select
                        value={meetingForm.timezone}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            timezone: e.target.value,
                          })
                        }
                      >
                        <option value="UTC">UTC</option>
                        <option value="America/New_York">Eastern Time</option>
                        <option value="America/Chicago">Central Time</option>
                        <option value="America/Denver">Mountain Time</option>
                        <option value="America/Los_Angeles">
                          Pacific Time
                        </option>
                      </Select>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Password (optional)</FormLabel>
                      <Input
                        type="password"
                        placeholder="Meeting password"
                        value={meetingForm.password}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            password: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <Text fontWeight="bold">Meeting Settings</Text>
                    <VStack spacing={2} align="stretch">
                      <Checkbox
                        isChecked={meetingForm.settings.host_video}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            settings: {
                              ...meetingForm.settings,
                              host_video: e.target.checked,
                            },
                          })
                        }
                      >
                        Enable host video
                      </Checkbox>
                      <Checkbox
                        isChecked={meetingForm.settings.participant_video}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            settings: {
                              ...meetingForm.settings,
                              participant_video: e.target.checked,
                            },
                          })
                        }
                      >
                        Enable participants video
                      </Checkbox>
                      <Checkbox
                        isChecked={meetingForm.settings.join_before_host}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            settings: {
                              ...meetingForm.settings,
                              join_before_host: e.target.checked,
                            },
                          })
                        }
                      >
                        Allow participants to join before host
                      </Checkbox>
                      <Checkbox
                        isChecked={meetingForm.settings.mute_upon_entry}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            settings: {
                              ...meetingForm.settings,
                              mute_upon_entry: e.target.checked,
                            },
                          })
                        }
                      >
                        Mute participants upon entry
                      </Checkbox>
                      <Checkbox
                        isChecked={meetingForm.settings.waiting_room}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            settings: {
                              ...meetingForm.settings,
                              waiting_room: e.target.checked,
                            },
                          })
                        }
                      >
                        Enable waiting room
                      </Checkbox>
                    </VStack>

                    <FormControl>
                      <FormLabel>Auto Recording</FormLabel>
                      <Select
                        value={meetingForm.settings.auto_recording}
                        onChange={(e) =>
                          setMeetingForm({
                            ...meetingForm,
                            settings: {
                              ...meetingForm.settings,
                              auto_recording: e.target.value,
                            },
                          })
                        }
                      >
                        <option value="none">None</option>
                        <option value="local">Local</option>
                        <option value="cloud">Cloud</option>
                      </Select>
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
                    disabled={!meetingForm.topic}
                  >
                    Schedule Meeting
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create User Modal */}
            <Modal isOpen={isUserOpen} onClose={onUserClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Add User</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Email</FormLabel>
                      <Input
                        type="email"
                        placeholder="user@example.com"
                        value={userForm.email}
                        onChange={(e) =>
                          setUserForm({
                            ...userForm,
                            email: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl isRequired>
                        <FormLabel>First Name</FormLabel>
                        <Input
                          placeholder="First name"
                          value={userForm.first_name}
                          onChange={(e) =>
                            setUserForm({
                              ...userForm,
                              first_name: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                      <FormControl isRequired>
                        <FormLabel>Last Name</FormLabel>
                        <Input
                          placeholder="Last name"
                          value={userForm.last_name}
                          onChange={(e) =>
                            setUserForm({
                              ...userForm,
                              last_name: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl isRequired>
                        <FormLabel>User Type</FormLabel>
                        <Select
                          value={userForm.type}
                          onChange={(e) =>
                            setUserForm({
                              ...userForm,
                              type: parseInt(e.target.value),
                            })
                          }
                        >
                          <option value={1}>Basic</option>
                          <option value={2}>Licensed</option>
                          <option value={3}>On-Prem</option>
                        </Select>
                      </FormControl>

                      <FormControl isRequired>
                        <FormLabel>Role</FormLabel>
                        <Select
                          value={userForm.role_name}
                          onChange={(e) =>
                            setUserForm({
                              ...userForm,
                              role_name: e.target.value,
                            })
                          }
                        >
                          <option value="Member">Member</option>
                          <option value="Admin">Admin</option>
                          <option value="Owner">Owner</option>
                        </Select>
                      </FormControl>
                    </HStack>

                    <FormControl isRequired>
                      <FormLabel>Timezone</FormLabel>
                      <Select
                        value={userForm.timezone}
                        onChange={(e) =>
                          setUserForm({
                            ...userForm,
                            timezone: e.target.value,
                          })
                        }
                      >
                        <option value="UTC">UTC</option>
                        <option value="America/New_York">Eastern Time</option>
                        <option value="America/Chicago">Central Time</option>
                        <option value="America/Denver">Mountain Time</option>
                        <option value="America/Los_Angeles">
                          Pacific Time
                        </option>
                      </Select>
                    </FormControl>

                    <Text fontWeight="bold">User Settings</Text>
                    <VStack spacing={2} align="stretch">
                      <Checkbox
                        isChecked={userForm.enable_cloud_auto_recording}
                        onChange={(e) =>
                          setUserForm({
                            ...userForm,
                            enable_cloud_auto_recording: e.target.checked,
                          })
                        }
                      >
                        Enable cloud auto recording
                      </Checkbox>
                      <Checkbox
                        isChecked={userForm.enable_recording}
                        onChange={(e) =>
                          setUserForm({
                            ...userForm,
                            enable_recording: e.target.checked,
                          })
                        }
                      >
                        Enable recording
                      </Checkbox>
                    </VStack>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onUserClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createUser}
                    disabled={
                      !userForm.email ||
                      !userForm.first_name ||
                      !userForm.last_name
                    }
                  >
                    Add User
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

export default ZoomIntegration;
