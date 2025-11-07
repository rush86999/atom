/**
 * Linear Integration Page
 * Dedicated interface for Linear issue tracking and project management
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
} from "@chakra-ui/icons";

interface LinearIssue {
  id: string;
  title: string;
  description?: string;
  state: string;
  priority: number;
  assignee?: string;
  team: string;
  project?: string;
  cycle?: string;
  dueDate?: string;
  url: string;
  createdAt: string;
  updatedAt: string;
}

interface LinearTeam {
  id: string;
  name: string;
  description?: string;
  key: string;
  memberCount: number;
}

interface LinearProject {
  id: string;
  name: string;
  description?: string;
  state: string;
  progress: number;
  teamId: string;
}

interface LinearCycle {
  id: string;
  name: string;
  number: number;
  startsAt: string;
  endsAt: string;
  progress: number;
  teamId: string;
}

const LinearIntegration: React.FC = () => {
  const [issues, setIssues] = useState<LinearIssue[]>([]);
  const [teams, setTeams] = useState<LinearTeam[]>([]);
  const [projects, setProjects] = useState<LinearProject[]>([]);
  const [cycles, setCycles] = useState<LinearCycle[]>([]);
  const [loading, setLoading] = useState({
    issues: false,
    teams: false,
    projects: false,
    cycles: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTeam, setSelectedTeam] = useState("");
  const [selectedState, setSelectedState] = useState("");
  const [selectedPriority, setSelectedPriority] = useState("");

  const { isOpen, onOpen, onClose } = useDisclosure();
  const [newIssue, setNewIssue] = useState({
    title: "",
    description: "",
    teamId: "",
    priority: 0,
  });

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/linear/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
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

  // Load Linear data
  const loadIssues = async () => {
    setLoading((prev) => ({ ...prev, issues: true }));
    try {
      const response = await fetch("/api/integrations/linear/issues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current", // Will be replaced with actual user ID
          team_id: selectedTeam || undefined,
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setIssues(data.data?.issues || []);
      }
    } catch (error) {
      console.error("Failed to load issues:", error);
      toast({
        title: "Error",
        description: "Failed to load issues from Linear",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, issues: false }));
    }
  };

  const loadTeams = async () => {
    setLoading((prev) => ({ ...prev, teams: true }));
    try {
      const response = await fetch("/api/integrations/linear/teams", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 20,
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

  const loadProjects = async () => {
    setLoading((prev) => ({ ...prev, projects: true }));
    try {
      const response = await fetch("/api/integrations/linear/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          team_id: selectedTeam || undefined,
          limit: 20,
        }),
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

  const loadCycles = async () => {
    setLoading((prev) => ({ ...prev, cycles: true }));
    try {
      const response = await fetch("/api/integrations/linear/cycles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          team_id: selectedTeam || undefined,
          limit: 10,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setCycles(data.data?.cycles || []);
      }
    } catch (error) {
      console.error("Failed to load cycles:", error);
    } finally {
      setLoading((prev) => ({ ...prev, cycles: false }));
    }
  };

  // Create new issue
  const createIssue = async () => {
    try {
      const response = await fetch("/api/integrations/linear/issues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          title: newIssue.title,
          description: newIssue.description,
          team_id: newIssue.teamId,
          priority: newIssue.priority,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Issue created successfully",
          status: "success",
          duration: 3000,
        });
        onClose();
        setNewIssue({ title: "", description: "", teamId: "", priority: 0 });
        loadIssues();
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

  // Filter issues based on search and filters
  const filteredIssues = issues.filter((issue) => {
    const matchesSearch =
      issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTeam = !selectedTeam || issue.team === selectedTeam;
    const matchesState = !selectedState || issue.state === selectedState;
    const matchesPriority =
      !selectedPriority || issue.priority.toString() === selectedPriority;

    return matchesSearch && matchesTeam && matchesState && matchesPriority;
  });

  // Stats calculations
  const totalIssues = issues.length;
  const backlogIssues = issues.filter(
    (issue) => issue.state === "backlog",
  ).length;
  const inProgressIssues = issues.filter(
    (issue) => issue.state === "inProgress",
  ).length;
  const completedIssues = issues.filter(
    (issue) => issue.state === "done",
  ).length;
  const completionRate =
    totalIssues > 0 ? (completedIssues / totalIssues) * 100 : 0;

  useEffect(() => {
    checkConnection();
    if (connected) {
      loadTeams();
    }
  }, [connected]);

  useEffect(() => {
    if (connected && teams.length > 0) {
      loadIssues();
      loadProjects();
      loadCycles();
    }
  }, [connected, teams, selectedTeam]);

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 0:
        return "gray";
      case 1:
        return "blue";
      case 2:
        return "orange";
      case 3:
        return "red";
      case 4:
        return "purple";
      default:
        return "gray";
    }
  };

  const getPriorityLabel = (priority: number) => {
    switch (priority) {
      case 0:
        return "No priority";
      case 1:
        return "Low";
      case 2:
        return "Medium";
      case 3:
        return "High";
      case 4:
        return "Urgent";
      default:
        return "Unknown";
    }
  };

  const getStateColor = (state: string) => {
    switch (state) {
      case "backlog":
        return "gray";
      case "todo":
        return "blue";
      case "inProgress":
        return "orange";
      case "done":
        return "green";
      case "canceled":
        return "red";
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
            <Icon as={CalendarIcon} w={8} h={8} color="blue.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Linear Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Issue tracking and project management
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
                <Icon as={CalendarIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Linear</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Linear account to start managing issues and
                    projects
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() =>
                    (window.location.href = "/api/auth/linear/authorize")
                  }
                >
                  Connect Linear Account
                </Button>
              </VStack>
            </CardBody>
          </Card>
        ) : (
          // Connected State
          <>
            {/* Stats Overview */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Total Issues</StatLabel>
                    <StatNumber>{totalIssues}</StatNumber>
                    <StatHelpText>Across all teams</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>In Progress</StatLabel>
                    <StatNumber>{inProgressIssues}</StatNumber>
                    <StatHelpText>Active work</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Completed</StatLabel>
                    <StatNumber>{completedIssues}</StatNumber>
                    <StatHelpText>Done this cycle</StatHelpText>
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
                <Tab>Issues</Tab>
                <Tab>Teams</Tab>
                <Tab>Projects</Tab>
                <Tab>Cycles</Tab>
              </TabList>

              <TabPanels>
                {/* Issues Tab */}
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
                            placeholder="Search issues..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            leftElement={<SearchIcon />}
                          />
                          <Select
                            placeholder="All Teams"
                            value={selectedTeam}
                            onChange={(e) => setSelectedTeam(e.target.value)}
                          >
                            {teams.map((team) => (
                              <option key={team.id} value={team.id}>
                                {team.name}
                              </option>
                            ))}
                          </Select>
                          <Select
                            placeholder="All States"
                            value={selectedState}
                            onChange={(e) => setSelectedState(e.target.value)}
                          >
                            <option value="backlog">Backlog</option>
                            <option value="todo">Todo</option>
                            <option value="inProgress">In Progress</option>
                            <option value="done">Done</option>
                            <option value="canceled">Canceled</option>
                          </Select>
                          <Select
                            placeholder="All Priorities"
                            value={selectedPriority}
                            onChange={(e) =>
                              setSelectedPriority(e.target.value)
                            }
                          >
                            <option value="0">No Priority</option>
                            <option value="1">Low</option>
                            <option value="2">Medium</option>
                            <option value="3">High</option>
                            <option value="4">Urgent</option>
                          </Select>
                          <Spacer />
                          <Button
                            colorScheme="blue"
                            leftIcon={<AddIcon />}
                            onClick={onOpen}
                          >
                            New Issue
                          </Button>
                        </Stack>
                      </CardBody>
                    </Card>

                    {/* Issues Table */}
                    <Card>
                      <CardBody>
                        {loading.issues ? (
                          <VStack spacing={4} py={8}>
                            <Text>Loading issues...</Text>
                            <Progress size="sm" isIndeterminate width="100%" />
                          </VStack>
                        ) : filteredIssues.length === 0 ? (
                          <VStack spacing={4} py={8}>
                            <Icon
                              as={CalendarIcon}
                              w={12}
                              h={12}
                              color="gray.400"
                            />
                            <Text color="gray.600">No issues found</Text>
                            <Button
                              variant="outline"
                              leftIcon={<AddIcon />}
                              onClick={onOpen}
                            >
                              Create Your First Issue
                            </Button>
                          </VStack>
                        ) : (
                          <Box overflowX="auto">
                            <Table variant="simple">
                              <Thead>
                                <Tr>
                                  <Th>Title</Th>
                                  <Th>State</Th>
                                  <Th>Priority</Th>
                                  <Th>Team</Th>
                                  <Th>Updated</Th>
                                  <Th>Actions</Th>
                                </Tr>
                              </Thead>
                              <Tbody>
                                {filteredIssues.map((issue) => (
                                  <Tr key={issue.id}>
                                    <Td>
                                      <VStack align="start" spacing={1}>
                                        <Text fontWeight="medium">
                                          {issue.title}
                                        </Text>
                                        {issue.description && (
                                          <Text
                                            fontSize="sm"
                                            color="gray.600"
                                            noOfLines={2}
                                          >
                                            {issue.description}
                                          </Text>
                                        )}
                                      </VStack>
                                    </Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getStateColor(issue.state)}
                                        size="sm"
                                      >
                                        <TagLabel>{issue.state}</TagLabel>
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getPriorityColor(
                                          issue.priority,
                                        )}
                                        size="sm"
                                      >
                                        <TagLabel>
                                          {getPriorityLabel(issue.priority)}
                                        </TagLabel>
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{issue.team}</Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {new Date(
                                          issue.updatedAt,
                                        ).toLocaleDateString()}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ExternalLinkIcon />}
                                        onClick={() =>
                                          window.open(issue.url, "_blank")
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
                                  <Text color="gray.600" fontSize="sm">
                                    {team.description}
                                  </Text>
                                  <HStack spacing={2}>
                                    <Badge colorScheme="blue">{team.key}</Badge>
                                    <Badge variant="outline">
                                      {team.memberCount} members
                                    </Badge>
                                  </HStack>
                                </VStack>
                              </CardBody>
                            </Card>
                          ))}
                        </SimpleGrid>
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
                                  <Text color="gray.600" fontSize="sm">
                                    {project.description}
                                  </Text>
                                  <HStack spacing={2}>
                                    <Badge
                                      colorScheme={
                                        project.state === "active"
                                          ? "green"
                                          : "gray"
                                      }
                                    >
                                      {project.state}
                                    </Badge>
                                    <Progress
                                      value={project.progress}
                                      colorScheme="blue"
                                      size="sm"
                                      width="100px"
                                    />
                                    <Text fontSize="sm">
                                      {Math.round(project.progress)}%
                                    </Text>
                                  </HStack>
                                </VStack>
                              </CardBody>
                            </Card>
                          ))}
                        </SimpleGrid>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Cycles Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <SimpleGrid
                          columns={{ base: 1, md: 2, lg: 3 }}
                          spacing={6}
                        >
                          {cycles.map((cycle) => (
                            <Card key={cycle.id} variant="outline">
                              <CardBody>
                                <VStack spacing={3} align="start">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {cycle.name}
                                  </Text>
                                  <Text color="gray.600" fontSize="sm">
                                    Cycle {cycle.number}
                                  </Text>
                                  <VStack
                                    spacing={1}
                                    align="start"
                                    width="100%"
                                  >
                                    <HStack
                                      justify="space-between"
                                      width="100%"
                                    >
                                      <Text fontSize="sm">Progress</Text>
                                      <Text fontSize="sm" fontWeight="bold">
                                        {Math.round(cycle.progress)}%
                                      </Text>
                                    </HStack>
                                    <Progress
                                      value={cycle.progress}
                                      colorScheme="blue"
                                      size="sm"
                                      width="100%"
                                    />
                                    <Text fontSize="xs" color="gray.500">
                                      {new Date(
                                        cycle.startsAt,
                                      ).toLocaleDateString()}{" "}
                                      -{" "}
                                      {new Date(
                                        cycle.endsAt,
                                      ).toLocaleDateString()}
                                    </Text>
                                  </VStack>
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

            {/* Create Issue Modal */}
            <Modal isOpen={isOpen} onClose={onClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create New Issue</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Title</FormLabel>
                      <Input
                        placeholder="Issue title"
                        value={newIssue.title}
                        onChange={(e) =>
                          setNewIssue({ ...newIssue, title: e.target.value })
                        }
                      />
                    </FormControl>
                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Issue description"
                        value={newIssue.description}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            description: e.target.value,
                          })
                        }
                        rows={4}
                      />
                    </FormControl>
                    <FormControl isRequired>
                      <FormLabel>Team</FormLabel>
                      <Select
                        placeholder="Select team"
                        value={newIssue.teamId}
                        onChange={(e) =>
                          setNewIssue({ ...newIssue, teamId: e.target.value })
                        }
                      >
                        {teams.map((team) => (
                          <option key={team.id} value={team.id}>
                            {team.name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                    <FormControl>
                      <FormLabel>Priority</FormLabel>
                      <Select
                        value={newIssue.priority}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            priority: parseInt(e.target.value),
                          })
                        }
                      >
                        <option value={0}>No Priority</option>
                        <option value={1}>Low</option>
                        <option value={2}>Medium</option>
                        <option value={3}>High</option>
                        <option value={4}>Urgent</option>
                      </Select>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createIssue}
                    isDisabled={!newIssue.title || !newIssue.teamId}
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

export default LinearIntegration;
