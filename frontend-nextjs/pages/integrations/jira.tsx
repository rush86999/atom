/**
 * Jira Integration Page
 * Complete Jira project management and issue tracking integration
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
  ViewIcon,
  EditIcon,
  DeleteIcon,
  CalendarIcon,
} from "@chakra-ui/icons";

interface JiraProject {
  id: string;
  key: string;
  name: string;
  projectTypeKey: string;
  lead: {
    displayName: string;
    emailAddress: string;
    avatarUrls: {
      "48x48": string;
      "24x24": string;
    };
  };
  url: string;
  description?: string;
  isPrivate: boolean;
  archived: boolean;
  issueTypes: Array<{
    id: string;
    name: string;
    description: string;
    iconUrl: string;
  }>;
}

interface JiraIssue {
  id: string;
  key: string;
  fields: {
    summary: string;
    description?: string;
    status: {
      name: string;
      statusCategory: {
        colorName: string;
      };
    };
    priority: {
      name: string;
      iconUrl: string;
    };
    assignee?: {
      displayName: string;
      emailAddress: string;
      avatarUrls: {
        "48x48": string;
        "24x24": string;
      };
    };
    reporter: {
      displayName: string;
      emailAddress: string;
      avatarUrls: {
        "48x48": string;
        "24x24": string;
      };
    };
    created: string;
    updated: string;
    resolution?: string;
    resolutiondate?: string;
    issuetype: {
      name: string;
      iconUrl: string;
    };
    project: {
      key: string;
      name: string;
    };
    components?: Array<{
      id: string;
      name: string;
    }>;
    fixVersions?: Array<{
      id: string;
      name: string;
    }>;
    labels?: string[];
    timeoriginalestimate?: number;
    timeestimate?: number;
    timespent?: number;
    aggregateprogress?: {
      progress: number;
      total: number;
    };
  };
}

interface JiraUser {
  accountId: string;
  accountType: string;
  active: boolean;
  displayName: string;
  emailAddress?: string;
  avatarUrls: {
    "48x48": string;
    "24x24": string;
    "16x16": string;
  };
  timeZone?: string;
  locale?: string;
}

interface JiraSprint {
  id: number;
  state: string;
  name: string;
  startDate?: string;
  endDate?: string;
  completeDate?: string;
  originBoardId: number;
  goal?: string;
  issues: Array<{
    id: string;
    key: string;
    fields: {
      summary: string;
      status: {
        name: string;
      };
      assignee?: {
        displayName: string;
        avatarUrls: {
          "48x48": string;
        };
      };
    };
  }>;
}

const JiraIntegration: React.FC = () => {
  const [projects, setProjects] = useState<JiraProject[]>([]);
  const [issues, setIssues] = useState<JiraIssue[]>([]);
  const [users, setUsers] = useState<JiraUser[]>([]);
  const [sprints, setSprints] = useState<JiraSprint[]>([]);
  const [userProfile, setUserProfile] = useState<JiraUser | null>(null);
  const [loading, setLoading] = useState({
    projects: false,
    issues: false,
    users: false,
    sprints: false,
    profile: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProject, setSelectedProject] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");
  const [selectedAssignee, setSelectedAssignee] = useState("");

  const {
    isOpen: isIssueOpen,
    onOpen: onIssueOpen,
    onClose: onIssueClose,
  } = useDisclosure();
  const {
    isOpen: isProjectOpen,
    onOpen: onProjectOpen,
    onClose: onProjectClose,
  } = useDisclosure();
  
  const [newIssue, setNewIssue] = useState({
    project: "",
    summary: "",
    description: "",
    issueType: "Story",
    priority: "Medium",
    assignee: "",
  });
  
  const [newProject, setNewProject] = useState({
    name: "",
    key: "",
    description: "",
    type: "Software",
  });

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/jira/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadUserProfile();
        loadProjects();
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
  };

  // Load Jira data
  const loadUserProfile = async () => {
    setLoading((prev) => ({ ...prev, profile: true }));
    try {
      const response = await fetch("/api/integrations/jira/profile", {
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

  const loadProjects = async () => {
    setLoading((prev) => ({ ...prev, projects: true }));
    try {
      const response = await fetch("/api/integrations/jira/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setProjects(data.data?.projects || []);
      }
    } catch (error) {
      console.error("Failed to load projects:", error);
      toast({
        title: "Error",
        description: "Failed to load projects from Jira",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, projects: false }));
    }
  };

  const loadIssues = async () => {
    setLoading((prev) => ({ ...prev, issues: true }));
    try {
      const response = await fetch("/api/integrations/jira/issues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          project: selectedProject,
          status: selectedStatus,
          assignee: selectedAssignee,
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setIssues(data.data?.issues || []);
      }
    } catch (error) {
      console.error("Failed to load issues:", error);
    } finally {
      setLoading((prev) => ({ ...prev, issues: false }));
    }
  };

  const loadUsers = async () => {
    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/jira/users", {
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

  const loadSprints = async (projectId: string) => {
    if (!projectId) return;
    
    setLoading((prev) => ({ ...prev, sprints: true }));
    try {
      const response = await fetch("/api/integrations/jira/sprints", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          project: projectId,
          limit: 20,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setSprints(data.data?.sprints || []);
      }
    } catch (error) {
      console.error("Failed to load sprints:", error);
    } finally {
      setLoading((prev) => ({ ...prev, sprints: false }));
    }
  };

  const createIssue = async () => {
    if (!newIssue.project || !newIssue.summary) return;

    try {
      const response = await fetch("/api/integrations/jira/issues/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          project: newIssue.project,
          summary: newIssue.summary,
          description: newIssue.description,
          issueType: newIssue.issueType,
          priority: newIssue.priority,
          assignee: newIssue.assignee,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Issue created successfully",
          status: "success",
          duration: 3000,
        });
        onIssueClose();
        setNewIssue({
          project: "",
          summary: "",
          description: "",
          issueType: "Story",
          priority: "Medium",
          assignee: "",
        });
        if (newIssue.project === selectedProject) {
          loadIssues();
        }
      }
    } catch (error) {
      console.error("Failed to create issue:", error);
      toast({
        title: "Error",
        description: "Failed to create issue",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredProjects = projects.filter(
    (project) =>
      project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      project.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      project.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredIssues = issues.filter(
    (issue) =>
      issue.fields.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.fields.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.key.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Stats calculations
  const totalProjects = projects.length;
  const activeProjects = projects.filter(p => !p.archived).length;
  const totalIssues = issues.length;
  const openIssues = issues.filter(i => i.fields.status.statusCategory.colorName !== 'done').length;
  const inProgressIssues = issues.filter(i => i.fields.status.statusCategory.colorName === 'in-progress').length;
  const doneIssues = issues.filter(i => i.fields.status.statusCategory.colorName === 'done').length;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadUserProfile();
      loadProjects();
      loadUsers();
    }
  }, [connected]);

  useEffect(() => {
    if (selectedProject) {
      loadIssues();
      loadSprints(selectedProject);
    }
  }, [selectedProject, selectedStatus, selectedAssignee]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const getStatusColor = (statusCategory: string): string => {
    switch (statusCategory?.toLowerCase()) {
      case "blue-gray":
      case "new":
        return "gray";
      case "yellow":
      case "in-progress":
        return "yellow";
      case "green":
      case "done":
        return "green";
      case "red":
      case "undefined":
        return "red";
      default:
        return "gray";
    }
  };

  const getPriorityColor = (priority: string): string => {
    switch (priority?.toLowerCase()) {
      case "highest":
      case "blocker":
        return "red";
      case "high":
      case "critical":
        return "orange";
      case "medium":
        return "yellow";
      case "low":
      case "minor":
        return "blue";
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
            <Icon as={ViewIcon} w={8} h={8} color="#0052CC" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Jira Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Project management and issue tracking platform
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
                src={userProfile.avatarUrls?.["48x48"]}
                name={userProfile.displayName}
              />
              <VStack align="start" spacing={0}>
                <Text fontWeight="bold">{userProfile.displayName}</Text>
                <Text fontSize="sm" color="gray.600">
                  {userProfile.emailAddress}
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
                <Icon as={ViewIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Jira</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Jira instance to start managing projects and issues
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href = "/api/integrations/jira/auth/start")
                  }
                >
                  Connect Jira Account
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
                    <StatLabel>Projects</StatLabel>
                    <StatNumber>{totalProjects}</StatNumber>
                    <StatHelpText>{activeProjects} active</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Total Issues</StatLabel>
                    <StatNumber>{totalIssues}</StatNumber>
                    <StatHelpText>All status</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>In Progress</StatLabel>
                    <StatNumber>{inProgressIssues}</StatNumber>
                    <StatHelpText>Currently being worked</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Completed</StatLabel>
                    <StatNumber>{doneIssues}</StatNumber>
                    <StatHelpText>Done this sprint</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Projects</Tab>
                <Tab>Issues</Tab>
                <Tab>Sprints</Tab>
                <Tab>Team</Tab>
              </TabList>

              <TabPanels>
                {/* Projects Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search projects..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onProjectOpen}
                      >
                        Create Project
                      </Button>
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.projects ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredProjects.map((project) => (
                          <Card
                            key={project.id}
                            cursor="pointer"
                            _hover={{ shadow: "md", transform: "translateY(-2px)" }}
                            transition="all 0.2s"
                            onClick={() => setSelectedProject(project.key)}
                            borderWidth="1px"
                            borderColor={selectedProject === project.key ? "blue.500" : borderColor}
                          >
                            <CardHeader>
                              <VStack align="start" spacing={2}>
                                <HStack justify="space-between" width="100%">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {project.name}
                                  </Text>
                                  <HStack spacing={1}>
                                    {project.isPrivate && (
                                      <Tag colorScheme="gray" size="sm">
                                        Private
                                      </Tag>
                                    )}
                                    {project.archived && (
                                      <Tag colorScheme="red" size="sm">
                                        Archived
                                      </Tag>
                                    )}
                                  </HStack>
                                </HStack>
                                <Text fontSize="sm" color="gray.600">
                                  {project.description}
                                </Text>
                                <Text fontSize="sm" color="blue.600" fontWeight="bold">
                                  {project.key}
                                </Text>
                              </VStack>
                            </CardHeader>
                            <CardBody>
                              <VStack spacing={3} align="stretch">
                                {project.lead && (
                                  <HStack spacing={2}>
                                    <Avatar
                                      src={project.lead.avatarUrls?.["24x24"]}
                                      name={project.lead.displayName}
                                      size="sm"
                                    />
                                    <Text fontSize="sm">
                                      Lead: {project.lead.displayName}
                                    </Text>
                                  </HStack>
                                )}
                                <Text fontSize="xs" color="gray.500">
                                  Type: {project.projectTypeKey}
                                </Text>
                                {project.issueTypes && (
                                  <HStack wrap="wrap">
                                    {project.issueTypes.slice(0, 3).map((type) => (
                                      <Tag key={type.id} size="sm" colorScheme="blue">
                                        {type.name}
                                      </Tag>
                                    ))}
                                  </HStack>
                                )}
                              </VStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                {/* Issues Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Select project"
                        value={selectedProject}
                        onChange={(e) => setSelectedProject(e.target.value)}
                        width="200px"
                      >
                        {projects.map((project) => (
                          <option key={project.id} value={project.key}>
                            {project.name} ({project.key})
                          </option>
                        ))}
                      </Select>
                      <Select
                        placeholder="Status"
                        value={selectedStatus}
                        onChange={(e) => setSelectedStatus(e.target.value)}
                        width="150px"
                      >
                        <option value="">All Status</option>
                        <option value="To Do">To Do</option>
                        <option value="In Progress">In Progress</option>
                        <option value="In Review">In Review</option>
                        <option value="Done">Done</option>
                      </Select>
                      <Select
                        placeholder="Assignee"
                        value={selectedAssignee}
                        onChange={(e) => setSelectedAssignee(e.target.value)}
                        width="200px"
                      >
                        <option value="">All Assignees</option>
                        {users.map((user) => (
                          <option key={user.accountId} value={user.accountId}>
                            {user.displayName}
                          </option>
                        ))}
                      </Select>
                      <Input
                        placeholder="Search issues..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onIssueOpen}
                        disabled={!selectedProject}
                      >
                        Create Issue
                      </Button>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.issues ? (
                        <Spinner size="xl" />
                      ) : selectedProject ? (
                        filteredIssues.map((issue) => (
                          <Card key={issue.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <VStack spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <HStack>
                                      <Text fontWeight="bold" fontSize="lg">
                                        {issue.key}
                                      </Text>
                                      <Text>{issue.fields.summary}</Text>
                                    </HStack>
                                    <Tag
                                      colorScheme={getStatusColor(
                                        issue.fields.status.statusCategory.colorName
                                      )}
                                      size="sm"
                                    >
                                      {issue.fields.status.name}
                                    </Tag>
                                  </HStack>
                                  <HStack spacing={4}>
                                    <Tag colorScheme={getPriorityColor(issue.fields.priority.name)} size="sm">
                                      {issue.fields.priority.name}
                                    </Tag>
                                    <Tag size="sm" colorScheme="purple">
                                      {issue.fields.issuetype.name}
                                    </Tag>
                                  </HStack>
                                  <Text fontSize="sm" color="gray.600">
                                    {issue.fields.description?.substring(0, 200)}
                                    {issue.fields.description && issue.fields.description.length > 200 && "..."}
                                  </Text>
                                  <HStack justify="space-between" width="100%">
                                    <HStack spacing={4}>
                                      <Avatar
                                        src={issue.fields.reporter.avatarUrls?.["24x24"]}
                                        name={issue.fields.reporter.displayName}
                                        size="sm"
                                      />
                                      <Text fontSize="xs" color="gray.500">
                                        Reporter: {issue.fields.reporter.displayName}
                                      </Text>
                                      {issue.fields.assignee && (
                                        <>
                                          <Avatar
                                            src={issue.fields.assignee.avatarUrls?.["24x24"]}
                                            name={issue.fields.assignee.displayName}
                                            size="sm"
                                          />
                                          <Text fontSize="xs" color="gray.500">
                                            Assignee: {issue.fields.assignee.displayName}
                                          </Text>
                                        </>
                                      )}
                                    </HStack>
                                    <Text fontSize="xs" color="gray.500">
                                      {formatDate(issue.fields.created)}
                                    </Text>
                                  </HStack>
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : (
                        <Text color="gray.500" textAlign="center" py={8}>
                          Select a project to view issues
                        </Text>
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Sprints Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Select project"
                        value={selectedProject}
                        onChange={(e) => setSelectedProject(e.target.value)}
                        width="200px"
                      >
                        {projects.map((project) => (
                          <option key={project.id} value={project.key}>
                            {project.name} ({project.key})
                          </option>
                        ))}
                      </Select>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.sprints ? (
                        <Spinner size="xl" />
                      ) : selectedProject ? (
                        sprints.map((sprint) => (
                          <Card key={sprint.id}>
                            <CardBody>
                              <VStack align="start" spacing={3}>
                                <HStack justify="space-between" width="100%">
                                  <Heading size="md">{sprint.name}</Heading>
                                  <Tag colorScheme={sprint.state === 'active' ? 'green' : 'gray'} size="sm">
                                    {sprint.state}
                                  </Tag>
                                </HStack>
                                {sprint.goal && (
                                  <Text color="gray.600">Goal: {sprint.goal}</Text>
                                )}
                                <HStack spacing={4}>
                                  {sprint.startDate && (
                                    <Text fontSize="sm" color="gray.500">
                                      Start: {formatDate(sprint.startDate)}
                                    </Text>
                                  )}
                                  {sprint.endDate && (
                                    <Text fontSize="sm" color="gray.500">
                                      End: {formatDate(sprint.endDate)}
                                    </Text>
                                  )}
                                </HStack>
                                <Text fontSize="sm" fontWeight="bold">
                                  {sprint.issues.length} issues
                                </Text>
                                <VStack spacing={2} width="100%">
                                  {sprint.issues.map((issue) => (
                                    <HStack key={issue.id} p={2} bg="gray.50" borderRadius="md">
                                      <Text fontSize="sm">{issue.key}</Text>
                                      <Text fontSize="sm">{issue.fields.summary}</Text>
                                      {issue.fields.assignee && (
                                        <Avatar
                                          src={issue.fields.assignee.avatarUrls?.["24x24"]}
                                          name={issue.fields.assignee.displayName}
                                          size="xs"
                                        />
                                      )}
                                    </HStack>
                                  ))}
                                </VStack>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : (
                        <Text color="gray.500" textAlign="center" py={8}>
                          Select a project to view sprints
                        </Text>
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Team Tab */}
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

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.users ? (
                        <Spinner size="xl" />
                      ) : (
                        users.filter(user =>
                          user.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          (user.emailAddress && user.emailAddress.toLowerCase().includes(searchQuery.toLowerCase()))
                        ).map((user) => (
                          <Card key={user.accountId}>
                            <CardBody>
                              <HStack spacing={4}>
                                <Avatar
                                  src={user.avatarUrls?.["48x48"]}
                                  name={user.displayName}
                                  size="lg"
                                />
                                <VStack align="start" spacing={1} flex={1}>
                                  <Text fontWeight="bold">{user.displayName}</Text>
                                  {user.emailAddress && (
                                    <Text fontSize="sm" color="gray.600">
                                      {user.emailAddress}
                                    </Text>
                                  )}
                                  <HStack spacing={2}>
                                    <Tag colorScheme={user.active ? "green" : "red"} size="sm">
                                      {user.active ? "Active" : "Inactive"}
                                    </Tag>
                                    <Tag colorScheme="blue" size="sm">
                                      {user.accountType}
                                    </Tag>
                                  </HStack>
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

            {/* Create Issue Modal */}
            <Modal isOpen={isIssueOpen} onClose={onIssueClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Issue</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Project</FormLabel>
                      <Select
                        value={newIssue.project}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            project: e.target.value,
                          })
                        }
                      >
                        <option value="">Select a project</option>
                        {projects.map((project) => (
                          <option key={project.id} value={project.key}>
                            {project.name} ({project.key})
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Summary</FormLabel>
                      <Input
                        placeholder="Issue summary"
                        value={newIssue.summary}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            summary: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Describe the issue..."
                        value={newIssue.description}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            description: e.target.value,
                          })
                        }
                        rows={6}
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Issue Type</FormLabel>
                      <Select
                        value={newIssue.issueType}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            issueType: e.target.value,
                          })
                        }
                      >
                        <option value="Story">Story</option>
                        <option value="Task">Task</option>
                        <option value="Bug">Bug</option>
                        <option value="Epic">Epic</option>
                      </Select>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Priority</FormLabel>
                      <Select
                        value={newIssue.priority}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            priority: e.target.value,
                          })
                        }
                      >
                        <option value="Highest">Highest</option>
                        <option value="High">High</option>
                        <option value="Medium">Medium</option>
                        <option value="Low">Low</option>
                        <option value="Lowest">Lowest</option>
                      </Select>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Assignee</FormLabel>
                      <Select
                        value={newIssue.assignee}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            assignee: e.target.value,
                          })
                        }
                      >
                        <option value="">Unassigned</option>
                        {users.map((user) => (
                          <option key={user.accountId} value={user.accountId}>
                            {user.displayName}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onIssueClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createIssue}
                    disabled={!newIssue.project || !newIssue.summary}
                  >
                    Create Issue
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

export default JiraIntegration;