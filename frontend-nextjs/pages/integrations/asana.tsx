/**
 * Asana Integration Page
 * Complete project management and task tracking interface
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
  StarIcon,
  ViewIcon,
} from "@chakra-ui/icons";

interface AsanaTask {
  id: string;
  name: string;
  description?: string;
  due_on?: string;
  due_at?: string;
  assignee?: {
    id: string;
    name: string;
    email?: string;
  };
  projects: Array<{
    id: string;
    name: string;
  }>;
  workspace: {
    id: string;
    name: string;
  };
  completed: boolean;
  created_at: string;
  modified_at: string;
  permalink_url: string;
  tags: string[];
  custom_fields?: Array<{
    id: string;
    name: string;
    value: any;
  }>;
}

interface AsanaProject {
  id: string;
  name: string;
  description?: string;
  color?: string;
  due_date?: string;
  current_status?: {
    color: string;
    text: string;
  };
  owner?: {
    id: string;
    name: string;
  };
  workspace: {
    id: string;
    name: string;
  };
  team?: {
    id: string;
    name: string;
  };
  created_at: string;
  modified_at: string;
  permalink_url: string;
}

interface AsanaWorkspace {
  id: string;
  name: string;
  is_organization: boolean;
}

interface AsanaUser {
  id: string;
  name: string;
  email?: string;
  photo?: {
    image_21x21?: string;
    image_27x27?: string;
    image_36x36?: string;
    image_60x60?: string;
  };
}

interface AsanaTeam {
  id: string;
  name: string;
  description?: string;
  organization?: {
    id: string;
    name: string;
  };
}

const AsanaIntegration: React.FC = () => {
  const [tasks, setTasks] = useState<AsanaTask[]>([]);
  const [projects, setProjects] = useState<AsanaProject[]>([]);
  const [workspaces, setWorkspaces] = useState<AsanaWorkspace[]>([]);
  const [teams, setTeams] = useState<AsanaTeam[]>([]);
  const [users, setUsers] = useState<AsanaUser[]>([]);
  const [loading, setLoading] = useState({
    tasks: false,
    projects: false,
    workspaces: false,
    teams: false,
    users: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedWorkspace, setSelectedWorkspace] = useState("");
  const [selectedProject, setSelectedProject] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");

  const { isOpen, onOpen, onClose } = useDisclosure();
  const [newTask, setNewTask] = useState({
    name: "",
    description: "",
    due_on: "",
    assignee: "",
    project: "",
  });

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/asana/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadWorkspaces();
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

  // Load Asana data
  const loadWorkspaces = async () => {
    setLoading((prev) => ({ ...prev, workspaces: true }));
    try {
      const response = await fetch("/api/integrations/asana/workspaces", {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });

      if (response.ok) {
        const data = await response.json();
        setWorkspaces(data.data?.workspaces || []);
      }
    } catch (error) {
      console.error("Failed to load workspaces:", error);
    } finally {
      setLoading((prev) => ({ ...prev, workspaces: false }));
    }
  };

  const loadProjects = async () => {
    setLoading((prev) => ({ ...prev, projects: true }));
    try {
      const response = await fetch("/api/integrations/asana/projects", {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });

      if (response.ok) {
        const data = await response.json();
        setProjects(data.data?.projects || []);
      }
    } catch (error) {
      console.error("Failed to load projects:", error);
    } finally {
      setLoading((prev) => ({ ...prev, projects: false }));
    }
  };

  const loadTasks = async () => {
    setLoading((prev) => ({ ...prev, tasks: true }));
    try {
      const response = await fetch("/api/integrations/asana/tasks", {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });

      if (response.ok) {
        const data = await response.json();
        setTasks(data.data?.tasks || []);
      }
    } catch (error) {
      console.error("Failed to load tasks:", error);
      toast({
        title: "Error",
        description: "Failed to load tasks from Asana",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, tasks: false }));
    }
  };

  const loadTeams = async () => {
    setLoading((prev) => ({ ...prev, teams: true }));
    try {
      const response = await fetch("/api/integrations/asana/teams", {
        method: "GET",
        headers: { "Content-Type": "application/json" },
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

  const loadUsers = async () => {
    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/asana/users", {
        method: "GET",
        headers: { "Content-Type": "application/json" },
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

  // Create new task
  const createTask = async () => {
    try {
      const response = await fetch("/api/integrations/asana/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newTask.name,
          description: newTask.description,
          due_on: newTask.due_on || undefined,
          assignee: newTask.assignee || undefined,
          projects: newTask.project ? [newTask.project] : [],
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Task created successfully",
          status: "success",
          duration: 3000,
        });
        onClose();
        setNewTask({
          name: "",
          description: "",
          due_on: "",
          assignee: "",
          project: "",
        });
        loadTasks();
      }
    } catch (error) {
      console.error("Failed to create task:", error);
      toast({
        title: "Error",
        description: "Failed to create task",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter tasks based on search and filters
  const filteredTasks = tasks.filter((task) => {
    const matchesSearch =
      task.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesWorkspace =
      !selectedWorkspace || task.workspace.id === selectedWorkspace;
    const matchesProject =
      !selectedProject || task.projects.some((p) => p.id === selectedProject);
    const matchesStatus =
      !selectedStatus ||
      (selectedStatus === "completed" && task.completed) ||
      (selectedStatus === "incomplete" && !task.completed);

    return matchesSearch && matchesWorkspace && matchesProject && matchesStatus;
  });

  // Stats calculations
  const totalTasks = tasks.length;
  const completedTasks = tasks.filter((task) => task.completed).length;
  const overdueTasks = tasks.filter(
    (task) =>
      task.due_on && new Date(task.due_on) < new Date() && !task.completed,
  ).length;
  const assignedTasks = tasks.filter((task) => task.assignee).length;
  const completionRate =
    totalTasks > 0 ? (completedTasks / totalTasks) * 100 : 0;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadProjects();
      loadTasks();
      loadTeams();
      loadUsers();
    }
  }, [connected]);

  const getStatusColor = (completed: boolean) => {
    return completed ? "green" : "blue";
  };

  const getStatusLabel = (completed: boolean) => {
    return completed ? "Completed" : "In Progress";
  };

  const getDueDateColor = (dueDate?: string, completed?: boolean) => {
    if (completed) return "gray";
    if (!dueDate) return "gray";
    const due = new Date(dueDate);
    const today = new Date();
    if (due < today) return "red";
    if (due < new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000))
      return "orange";
    return "green";
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return "No due date";
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={ViewIcon} w={8} h={8} color="green.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Asana Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Project management and task tracking
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
                <Icon as={ViewIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Asana</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Asana account to manage projects and tasks
                  </Text>
                </VStack>
                <Button
                  colorScheme="green"
                  size="lg"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() =>
                    (window.location.href = "/api/auth/asana/authorize")
                  }
                >
                  Connect Asana Account
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
                    <StatLabel>Total Tasks</StatLabel>
                    <StatNumber>{totalTasks}</StatNumber>
                    <StatHelpText>Across all projects</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Completed</StatLabel>
                    <StatNumber>{completedTasks}</StatNumber>
                    <StatHelpText>Tasks done</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Overdue</StatLabel>
                    <StatNumber>{overdueTasks}</StatNumber>
                    <StatHelpText>Need attention</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Assigned</StatLabel>
                    <StatNumber>{assignedTasks}</StatNumber>
                    <StatHelpText>With assignees</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Completion Rate</StatLabel>
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
                <Tab>Tasks</Tab>
                <Tab>Projects</Tab>
                <Tab>Teams</Tab>
                <Tab>Workspaces</Tab>
              </TabList>

              <TabPanels>
                {/* Tasks Tab */}
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
                            placeholder="Search tasks..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            leftAddon={<SearchIcon />}
                          />
                          <Select
                            placeholder="All Workspaces"
                            value={selectedWorkspace}
                            onChange={(e) =>
                              setSelectedWorkspace(e.target.value)
                            }
                          >
                            {workspaces.map((workspace) => (
                              <option key={workspace.id} value={workspace.id}>
                                {workspace.name}
                              </option>
                            ))}
                          </Select>
                          <Select
                            placeholder="All Projects"
                            value={selectedProject}
                            onChange={(e) => setSelectedProject(e.target.value)}
                          >
                            {projects.map((project) => (
                              <option key={project.id} value={project.id}>
                                {project.name}
                              </option>
                            ))}
                          </Select>
                          <Select
                            placeholder="All Status"
                            value={selectedStatus}
                            onChange={(e) => setSelectedStatus(e.target.value)}
                          >
                            <option value="completed">Completed</option>
                            <option value="incomplete">Incomplete</option>
                          </Select>
                          <Spacer />
                          <Button
                            colorScheme="green"
                            leftIcon={<AddIcon />}
                            onClick={onOpen}
                          >
                            New Task
                          </Button>
                        </Stack>
                      </CardBody>
                    </Card>

                    {/* Tasks Table */}
                    <Card>
                      <CardBody>
                        {loading.tasks ? (
                          <VStack spacing={4} py={8}>
                            <Text>Loading tasks...</Text>
                            <Progress size="sm" isIndeterminate width="100%" />
                          </VStack>
                        ) : filteredTasks.length === 0 ? (
                          <VStack spacing={4} py={8}>
                            <Icon
                              as={ViewIcon}
                              w={12}
                              h={12}
                              color="gray.400"
                            />
                            <Text color="gray.600">No tasks found</Text>
                            <Button
                              variant="outline"
                              leftIcon={<AddIcon />}
                              onClick={onOpen}
                            >
                              Create Your First Task
                            </Button>
                          </VStack>
                        ) : (
                          <Box overflowX="auto">
                            <Table variant="simple">
                              <Thead>
                                <Tr>
                                  <Th>Task Name</Th>
                                  <Th>Projects</Th>
                                  <Th>Assignee</Th>
                                  <Th>Due Date</Th>
                                  <Th>Status</Th>
                                  <Th>Actions</Th>
                                </Tr>
                              </Thead>
                              <Tbody>
                                {filteredTasks.map((task) => (
                                  <Tr key={task.id}>
                                    <Td>
                                      <VStack align="start" spacing={1}>
                                        <Text fontWeight="medium">
                                          {task.name}
                                        </Text>
                                        {task.description && (
                                          <Text
                                            fontSize="sm"
                                            color="gray.600"
                                            noOfLines={2}
                                          >
                                            {task.description}
                                          </Text>
                                        )}
                                      </VStack>
                                    </Td>
                                    <Td>
                                      <VStack align="start" spacing={1}>
                                        {task.projects.map((project) => (
                                          <Badge
                                            key={project.id}
                                            colorScheme="blue"
                                            variant="outline"
                                            size="sm"
                                          >
                                            {project.name}
                                          </Badge>
                                        ))}
                                      </VStack>
                                    </Td>
                                    <Td>
                                      {task.assignee ? (
                                        <Text fontSize="sm">
                                          {task.assignee.name}
                                        </Text>
                                      ) : (
                                        <Text fontSize="sm" color="gray.500">
                                          Unassigned
                                        </Text>
                                      )}
                                    </Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getDueDateColor(
                                          task.due_on,
                                          task.completed,
                                        )}
                                        size="sm"
                                      >
                                        <TagLabel>
                                          {formatDate(task.due_on)}
                                        </TagLabel>
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getStatusColor(
                                          task.completed,
                                        )}
                                        size="sm"
                                      >
                                        <TagLabel>
                                          {getStatusLabel(task.completed)}
                                        </TagLabel>
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ExternalLinkIcon />}
                                        onClick={() =>
                                          window.open(
                                            task.permalink_url,
                                            "_blank",
                                          )
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

                {/* Projects Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <SimpleGrid
                          columns={{ base: 1, md: 2, lg: 3 }}
                          spacing={6}
                        >
                          {projects.map((project) => (
                            <Card key={project.id} variant="outline">
                              <CardBody>
                                <VStack spacing={3} align="start">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {project.name}
                                  </Text>
                                  {project.description && (
                                    <Text color="gray.600" fontSize="sm">
                                      {project.description}
                                    </Text>
                                  )}
                                  <HStack spacing={2}>
                                    {project.current_status && (
                                      <Badge
                                        colorScheme={
                                          project.current_status.color ===
                                          "green"
                                            ? "green"
                                            : project.current_status.color ===
                                                "yellow"
                                              ? "yellow"
                                              : "red"
                                        }
                                      >
                                        {project.current_status.text}
                                      </Badge>
                                    )}
                                    {project.owner && (
                                      <Badge variant="outline">
                                        {project.owner.name}
                                      </Badge>
                                    )}
                                  </HStack>
                                  <Text fontSize="sm" color="gray.500">
                                    Workspace: {project.workspace.name}
                                  </Text>
                                  {project.team && (
                                    <Text fontSize="sm" color="gray.500">
                                      Team: {project.team.name}
                                    </Text>
                                  )}
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    leftIcon={<ExternalLinkIcon />}
                                    onClick={() =>
                                      window.open(
                                        project.permalink_url,
                                        "_blank",
                                      )
                                    }
                                  >
                                    Open in Asana
                                  </Button>
                                </VStack>
                              </CardBody>
                            </Card>
                          ))}
                        </SimpleGrid>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Teams Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <SimpleGrid
                          columns={{ base: 1, md: 2, lg: 3 }}
                          spacing={6}
                        >
                          {teams.map((team) => (
                            <Card key={team.id} variant="outline">
                              <CardBody>
                                <VStack spacing={3} align="start">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {team.name}
                                  </Text>
                                  {team.description && (
                                    <Text color="gray.600" fontSize="sm">
                                      {team.description}
                                    </Text>
                                  )}
                                  {team.organization && (
                                    <Text fontSize="sm" color="gray.500">
                                      Organization: {team.organization.name}
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

                {/* Workspaces Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <SimpleGrid
                          columns={{ base: 1, md: 2, lg: 3 }}
                          spacing={6}
                        >
                          {workspaces.map((workspace) => (
                            <Card key={workspace.id} variant="outline">
                              <CardBody>
                                <VStack spacing={3} align="start">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {workspace.name}
                                  </Text>
                                  <Badge
                                    colorScheme={
                                      workspace.is_organization
                                        ? "purple"
                                        : "blue"
                                    }
                                  >
                                    {workspace.is_organization
                                      ? "Organization"
                                      : "Workspace"}
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
              </TabPanels>
            </Tabs>

            {/* Create Task Modal */}
            <Modal isOpen={isOpen} onClose={onClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create New Task</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Task Name</FormLabel>
                      <Input
                        placeholder="Enter task name"
                        value={newTask.name}
                        onChange={(e) =>
                          setNewTask({ ...newTask, name: e.target.value })
                        }
                      />
                    </FormControl>
                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Task description"
                        value={newTask.description}
                        onChange={(e) =>
                          setNewTask({
                            ...newTask,
                            description: e.target.value,
                          })
                        }
                        rows={3}
                      />
                    </FormControl>
                    <FormControl>
                      <FormLabel>Due Date</FormLabel>
                      <Input
                        type="date"
                        value={newTask.due_on}
                        onChange={(e) =>
                          setNewTask({ ...newTask, due_on: e.target.value })
                        }
                      />
                    </FormControl>
                    <FormControl>
                      <FormLabel>Assignee</FormLabel>
                      <Select
                        placeholder="Select assignee"
                        value={newTask.assignee}
                        onChange={(e) =>
                          setNewTask({ ...newTask, assignee: e.target.value })
                        }
                      >
                        {users.map((user) => (
                          <option key={user.id} value={user.id}>
                            {user.name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                    <FormControl>
                      <FormLabel>Project</FormLabel>
                      <Select
                        placeholder="Select project"
                        value={newTask.project}
                        onChange={(e) =>
                          setNewTask({ ...newTask, project: e.target.value })
                        }
                      >
                        {projects.map((project) => (
                          <option key={project.id} value={project.id}>
                            {project.name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="green"
                    onClick={createTask}
                    isDisabled={!newTask.name}
                  >
                    Create Task
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

export default AsanaIntegration;
