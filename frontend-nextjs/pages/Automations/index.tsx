import React, { useState, useCallback, useEffect } from "react";
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Button,
  Badge,
  useToast,
  SimpleGrid,
  IconButton,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
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
  Select,
  Switch,
  useDisclosure,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  Grid,
  GridItem,
  Divider,
  Tooltip,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuGroup,
  MenuDivider,
} from "@chakra-ui/react";
import {
  AddIcon,
  CheckIcon,
  TimeIcon,
  SettingsIcon,
  EditIcon,
  DeleteIcon,
  CopyIcon,
  ChevronDownIcon,
  ViewIcon,
  CalendarIcon,
  ChatIcon,
  EmailIcon,
  AttachmentIcon,
  StarIcon,
  WarningIcon,
} from "@chakra-ui/icons";
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MiniMap,
} from "reactflow";
import "reactflow/dist/style.css";

// Types
interface WorkflowTrigger {
  type: "schedule" | "event" | "webhook" | "manual";
  config: {
    schedule?: string;
    eventType?: string;
    webhookUrl?: string;
    conditions?: any[];
  };
}

interface WorkflowAction {
  type:
    | "send_email"
    | "create_task"
    | "update_calendar"
    | "send_message"
    | "webhook_call"
    | "data_transform";
  config: {
    template?: string;
    recipients?: string[];
    taskDetails?: any;
    calendarEvent?: any;
    messageContent?: string;
    webhookEndpoint?: string;
    transformRules?: any[];
  };
}

interface Workflow {
  id: string;
  name: string;
  description: string;
  status: "active" | "paused" | "error" | "draft";
  trigger: WorkflowTrigger;
  actions: WorkflowAction[];
  lastRun: string;
  nextRun: string;
  successCount: number;
  errorCount: number;
  averageDuration: number;
  createdAt: string;
  updatedAt: string;
}

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: "communication" | "productivity" | "finance" | "social" | "custom";
  trigger: WorkflowTrigger;
  actions: WorkflowAction[];
  popularity: number;
}

// Workflow Templates
const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    id: "template-1",
    name: "Meeting Follow-up",
    description:
      "Automatically create tasks and send follow-up emails after meetings",
    category: "productivity",
    trigger: {
      type: "event",
      config: {
        eventType: "meeting_ended",
      },
    },
    actions: [
      {
        type: "create_task",
        config: {
          taskDetails: {
            title: "Meeting Follow-up",
            description: "Follow up on action items from meeting",
          },
        },
      },
      {
        type: "send_email",
        config: {
          template: "meeting_followup",
          recipients: ["attendees"],
        },
      },
    ],
    popularity: 95,
  },
  {
    id: "template-2",
    name: "Daily Digest",
    description: "Send daily summary of important emails and calendar events",
    category: "communication",
    trigger: {
      type: "schedule",
      config: {
        schedule: "0 9 * * *", // 9 AM daily
      },
    },
    actions: [
      {
        type: "send_email",
        config: {
          template: "daily_digest",
          recipients: ["user@example.com"],
        },
      },
    ],
    popularity: 88,
  },
  {
    id: "template-3",
    name: "Expense Tracking",
    description: "Automatically categorize and track expenses from emails",
    category: "finance",
    trigger: {
      type: "event",
      config: {
        eventType: "email_received",
        conditions: [
          { field: "subject", operator: "contains", value: "receipt" },
        ],
      },
    },
    actions: [
      {
        type: "create_task",
        config: {
          taskDetails: {
            title: "Review Expense",
            description: "Categorize and track expense",
          },
        },
      },
    ],
    popularity: 76,
  },
  {
    id: "template-4",
    name: "Social Media Post",
    description: "Automatically share content across social platforms",
    category: "social",
    trigger: {
      type: "manual",
      config: {},
    },
    actions: [
      {
        type: "send_message",
        config: {
          messageContent: "Shared content",
        },
      },
    ],
    popularity: 82,
  },
];

// Initial workflow nodes and edges for visual editor
const initialNodes: Node[] = [
  {
    id: "trigger",
    type: "input",
    position: { x: 100, y: 100 },
    data: { label: "Trigger" },
  },
  {
    id: "action-1",
    position: { x: 300, y: 100 },
    data: { label: "Action 1" },
  },
  {
    id: "action-2",
    position: { x: 500, y: 100 },
    data: { label: "Action 2" },
  },
];

const initialEdges: Edge[] = [
  { id: "e1-2", source: "trigger", target: "action-1" },
  { id: "e2-3", source: "action-1", target: "action-2" },
];

const EnhancedAutomationsPage: React.FC = () => {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalExecutions: 0,
    successfulExecutions: 0,
    failedExecutions: 0,
    averageExecutionTime: 0,
  });

  // Load workflows from API
  useEffect(() => {
    loadWorkflows();
  }, []);

  const loadWorkflows = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/workflows");
      if (response.ok) {
        const data = await response.json();
        if (data.success && data.workflows) {
          setWorkflows(data.workflows);
          // Load stats for each workflow
          await loadWorkflowStats(data.workflows);
        }
      } else {
        toast({
          title: "Failed to load workflows",
          status: "error",
          duration: 3000,
          isClosable: true,
        });
      }
    } catch (error) {
      console.error("Error loading workflows:", error);
      toast({
        title: "Error loading workflows",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const loadWorkflowStats = async (workflows: Workflow[]) => {
    try {
      const statsPromises = workflows.map(async (workflow) => {
        const response = await fetch(`/api/workflows/${workflow.id}/stats`);
        if (response.ok) {
          const data = await response.json();
          return data.success ? data.stats : null;
        }
        return null;
      });

      const statsResults = await Promise.all(statsPromises);
      // Aggregate stats for dashboard
      const aggregatedStats = statsResults.reduce(
        (acc, stat) => {
          if (stat) {
            acc.totalExecutions += stat.total_executions || 0;
            acc.successfulExecutions += stat.successful_executions || 0;
            acc.failedExecutions += stat.failed_executions || 0;
            acc.averageExecutionTime += stat.average_execution_time || 0;
          }
          return acc;
        },
        {
          totalExecutions: 0,
          successfulExecutions: 0,
          failedExecutions: 0,
          averageExecutionTime: 0,
        },
      );

      if (workflows.length > 0) {
        aggregatedStats.averageExecutionTime /= workflows.length;
      }

      setStats(aggregatedStats);
    } catch (error) {
      console.error("Error loading workflow stats:", error);
    }
  };

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [activeTab, setActiveTab] = useState(0);
  const [selectedTemplate, setSelectedTemplate] =
    useState<WorkflowTemplate | null>(null);

  const {
    isOpen: isCreateOpen,
    onOpen: onCreateOpen,
    onClose: onCreateClose,
  } = useDisclosure();

  const {
    isOpen: isEditorOpen,
    onOpen: onEditorOpen,
    onClose: onEditorClose,
  } = useDisclosure();

  const toast = useToast();

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  const handleToggleWorkflow = async (workflowId: string) => {
    try {
      const workflow = workflows.find((wf) => wf.id === workflowId);
      if (!workflow) return;

      const newStatus = workflow.status === "active" ? "paused" : "active";
      const response = await fetch(`/api/workflows/${workflowId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...workflow,
          status: newStatus,
        }),
      });

      if (response.ok) {
        await loadWorkflows(); // Reload to get updated data
        toast({
          title: "Workflow updated",
          status: "success",
          duration: 2000,
          isClosable: true,
        });
      } else {
        throw new Error("Failed to update workflow");
      }
    } catch (error) {
      console.error("Error updating workflow:", error);
      toast({
        title: "Failed to update workflow",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleRunWorkflow = async (workflowId: string) => {
    try {
      const response = await fetch(`/api/workflows/${workflowId}/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        const result = await response.json();
        toast({
          title: "Workflow started",
          description: result.message || "Running workflow in background",
          status: "info",
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error("Failed to execute workflow");
      }
    } catch (error) {
      console.error("Error executing workflow:", error);
      toast({
        title: "Failed to execute workflow",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleCreateFromTemplate = (template: WorkflowTemplate) => {
    setSelectedTemplate(template);
    onCreateOpen();
  };

  const handleSaveWorkflow = async (workflowData: Partial<Workflow>) => {
    try {
      const response = await fetch("/api/workflows", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: workflowData.name || "New Workflow",
          description: workflowData.description || "",
          trigger: workflowData.trigger || { type: "manual", config: {} },
          actions: workflowData.actions || [],
          status: "active",
        }),
      });

      if (response.ok) {
        const result = await response.json();
        await loadWorkflows(); // Reload to get the new workflow
        onCreateClose();
        setSelectedTemplate(null);

        toast({
          title: "Workflow created",
          description: "You can now configure and activate your workflow",
          status: "success",
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error("Failed to create workflow");
      }
    } catch (error) {
      console.error("Error creating workflow:", error);
      toast({
        title: "Failed to create workflow",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "green";
      case "paused":
        return "yellow";
      case "error":
        return "red";
      case "draft":
        return "gray";
      default:
        return "gray";
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleDateString();
  };

  const getSuccessRate = (workflow: Workflow) => {
    const total = workflow.successCount + workflow.errorCount;
    return total > 0 ? (workflow.successCount / total) * 100 : 0;
  };

  return (
    <Box p={8}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between">
          <VStack align="start" spacing={1}>
            <Heading size="xl">Workflow Automations</Heading>
            <Text color="gray.600">
              Create and manage automated workflows across all your connected
              platforms
            </Text>
          </VStack>
          <Button
            leftIcon={<AddIcon />}
            colorScheme="blue"
            onClick={onCreateOpen}
          >
            New Workflow
          </Button>
        </HStack>

        {/* Stats Overview */}
        <SimpleGrid columns={{ base: 1, md: 4 }} spacing={6}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Active Workflows</StatLabel>
                <StatNumber>
                  {workflows.filter((w) => w.status === "active").length}
                </StatNumber>
                <StatHelpText>
                  <StatArrow type="increase" />
                  23.36%
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Total Runs</StatLabel>
                <StatNumber>{stats.totalExecutions}</StatNumber>
                <StatHelpText>All time</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Success Rate</StatLabel>
                <StatNumber>
                  {stats.totalExecutions > 0
                    ? Math.round(
                        (stats.successfulExecutions / stats.totalExecutions) *
                          100,
                      )
                    : 0}
                  %
                </StatNumber>
                <StatHelpText>Average across workflows</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Time Saved</StatLabel>
                <StatNumber>
                  {Math.round(stats.averageExecutionTime / 60)}m
                </StatNumber>
                <StatHelpText>This month</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Main Content Tabs */}
        <Tabs variant="enclosed" onChange={setActiveTab}>
          <TabList>
            <Tab>My Workflows</Tab>
            <Tab>Templates</Tab>
            <Tab>Visual Editor</Tab>
            <Tab>Monitoring</Tab>
          </TabList>

          <TabPanels>
            {/* My Workflows Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                {/* Workflows Grid */}
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {workflows.map((workflow) => (
                    <Card key={workflow.id} variant="outline">
                      <CardHeader>
                        <HStack justify="space-between">
                          <Heading size="md">{workflow.name}</Heading>
                          <Badge colorScheme={getStatusColor(workflow.status)}>
                            {workflow.status}
                          </Badge>
                        </HStack>
                      </CardHeader>
                      <CardBody>
                        <VStack spacing={3} align="stretch">
                          <Text color="gray.600">{workflow.description}</Text>

                          {/* Trigger Info */}
                          <HStack>
                            <Badge variant="outline" colorScheme="blue">
                              {workflow.trigger.type}
                            </Badge>
                            <Text fontSize="sm" color="gray.500">
                              {workflow.trigger.type === "schedule"
                                ? "Scheduled"
                                : "Event-based"}
                            </Text>
                          </HStack>

                          {/* Performance Stats */}
                          <VStack spacing={1} align="start">
                            <Text fontSize="sm" color="gray.500">
                              Actions: {workflow.actions?.length || 0}
                            </Text>
                            <Text fontSize="sm" color="gray.500">
                              Trigger: {workflow.trigger?.type || "Manual"}
                            </Text>
                          </VStack>

                          <VStack spacing={1} align="start">
                            <Text fontSize="sm" color="gray.500">
                              Created: {formatDate(workflow.createdAt)}
                            </Text>
                            <Text fontSize="sm" color="gray.500">
                              Updated: {formatDate(workflow.updatedAt)}
                            </Text>
                          </VStack>
                        </VStack>
                      </CardBody>
                      <CardFooter>
                        <HStack spacing={2} width="full">
                          <Button
                            size="sm"
                            variant={
                              workflow.status === "active" ? "outline" : "solid"
                            }
                            colorScheme={
                              workflow.status === "active" ? "red" : "green"
                            }
                            onClick={() => handleToggleWorkflow(workflow.id)}
                            flex={1}
                            leftIcon={
                              workflow.status === "active" ? (
                                <TimeIcon />
                              ) : (
                                <AddIcon />
                              )
                            }
                          >
                            {workflow.status === "active"
                              ? "Pause"
                              : "Activate"}
                          </Button>
                          <Menu>
                            <MenuButton
                              as={IconButton}
                              size="sm"
                              variant="ghost"
                              icon={<ChevronDownIcon />}
                            />
                            <MenuList>
                              <MenuItem
                                icon={<EditIcon />}
                                onClick={onEditorOpen}
                              >
                                Edit Workflow
                              </MenuItem>
                              <MenuItem
                                icon={<AddIcon />}
                                onClick={() => handleRunWorkflow(workflow.id)}
                              >
                                Run Now
                              </MenuItem>
                              <MenuItem icon={<CopyIcon />}>Duplicate</MenuItem>
                              <MenuDivider />
                              <MenuItem icon={<DeleteIcon />} color="red.500">
                                Delete
                              </MenuItem>
                            </MenuList>
                          </Menu>
                        </HStack>
                      </CardFooter>
                    </Card>
                  ))}
                </SimpleGrid>

                {/* Empty State */}
                {workflows.length === 0 && (
                  <Card>
                    <CardBody>
                      <VStack spacing={4} py={8} textAlign="center">
                        <Heading size="md" color="gray.500">
                          No workflows yet
                        </Heading>
                        <Text color="gray.500">
                          Create your first automation to streamline your
                          workflow
                        </Text>
                        <Button
                          colorScheme="blue"
                          leftIcon={<AddIcon />}
                          onClick={onCreateOpen}
                        >
                          Create Workflow
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Visual Editor Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <HStack justify="space-between">
                  <VStack align="start" spacing={1}>
                    <Heading size="lg">Visual Workflow Editor</Heading>
                    <Text color="gray.600">
                      Drag and drop to create complex automation workflows
                    </Text>
                  </VStack>
                  <HStack>
                    <Button leftIcon={<AddIcon />} variant="outline">
                      Add Trigger
                    </Button>
                    <Button leftIcon={<AddIcon />} variant="outline">
                      Add Action
                    </Button>
                    <Button colorScheme="blue" onClick={onEditorOpen}>
                      Save Workflow
                    </Button>
                  </HStack>
                </HStack>

                <Box
                  h="600px"
                  border="1px"
                  borderColor="gray.200"
                  borderRadius="lg"
                  overflow="hidden"
                >
                  <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    fitView
                  >
                    <Controls />
                    <MiniMap />
                    <Background variant="dots" gap={12} size={1} />
                  </ReactFlow>
                </Box>

                {/* Node Palette */}
                <Card>
                  <CardHeader>
                    <Heading size="md">Available Nodes</Heading>
                  </CardHeader>
                  <CardBody>
                    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
                      <VStack
                        spacing={2}
                        p={3}
                        border="1px"
                        borderColor="gray.200"
                        borderRadius="md"
                      >
                        <CalendarIcon boxSize={6} color="blue.500" />
                        <Text fontSize="sm" fontWeight="medium">
                          Calendar
                        </Text>
                        <Text fontSize="xs" color="gray.500" textAlign="center">
                          Event triggers and actions
                        </Text>
                      </VStack>
                      <VStack
                        spacing={2}
                        p={3}
                        border="1px"
                        borderColor="gray.200"
                        borderRadius="md"
                      >
                        <EmailIcon boxSize={6} color="green.500" />
                        <Text fontSize="sm" fontWeight="medium">
                          Email
                        </Text>
                        <Text fontSize="xs" color="gray.500" textAlign="center">
                          Send and receive emails
                        </Text>
                      </VStack>
                      <VStack
                        spacing={2}
                        p={3}
                        border="1px"
                        borderColor="gray.200"
                        borderRadius="md"
                      >
                        <ChatIcon boxSize={6} color="purple.500" />
                        <Text fontSize="sm" fontWeight="medium">
                          Messages
                        </Text>
                        <Text fontSize="xs" color="gray.500" textAlign="center">
                          Chat and notification actions
                        </Text>
                      </VStack>
                      <VStack
                        spacing={2}
                        p={3}
                        border="1px"
                        borderColor="gray.200"
                        borderRadius="md"
                      >
                        <AttachmentIcon boxSize={6} color="orange.500" />
                        <Text fontSize="sm" fontWeight="medium">
                          Files
                        </Text>
                        <Text fontSize="xs" color="gray.500" textAlign="center">
                          File operations and storage
                        </Text>
                      </VStack>
                    </SimpleGrid>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>

            {/* Templates Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <Heading size="lg">Workflow Templates</Heading>
                <Text color="gray.600">
                  Start with pre-built templates for common automation scenarios
                </Text>

                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {WORKFLOW_TEMPLATES.map((template) => (
                    <Card
                      key={template.id}
                      variant="outline"
                      cursor="pointer"
                      _hover={{ transform: "translateY(-2px)", shadow: "md" }}
                      transition="all 0.2s"
                      onClick={() => handleCreateFromTemplate(template)}
                    >
                      <CardHeader>
                        <HStack justify="space-between">
                          <Heading size="md">{template.name}</Heading>
                          <Badge
                            colorScheme={
                              template.category === "communication"
                                ? "blue"
                                : template.category === "productivity"
                                  ? "green"
                                  : template.category === "finance"
                                    ? "purple"
                                    : template.category === "social"
                                      ? "orange"
                                      : "gray"
                            }
                          >
                            {template.category}
                          </Badge>
                        </HStack>
                      </CardHeader>
                      <CardBody>
                        <VStack spacing={3} align="stretch">
                          <Text color="gray.600">{template.description}</Text>

                          {/* Trigger Preview */}
                          <HStack>
                            <Badge
                              variant="subtle"
                              colorScheme="blue"
                              size="sm"
                            >
                              {template.trigger.type}
                            </Badge>
                            <Text fontSize="sm" color="gray.500">
                              Trigger
                            </Text>
                          </HStack>

                          {/* Actions Preview */}
                          <HStack>
                            <Badge
                              variant="subtle"
                              colorScheme="green"
                              size="sm"
                            >
                              {template.actions.length} actions
                            </Badge>
                            <Text fontSize="sm" color="gray.500">
                              Steps
                            </Text>
                          </HStack>

                          {/* Popularity */}
                          <HStack justify="space-between">
                            <HStack>
                              <StarIcon color="yellow.400" />
                              <Text fontSize="sm" color="gray.500">
                                {template.popularity}% success rate
                              </Text>
                            </HStack>
                            <Button
                              size="sm"
                              colorScheme="blue"
                              variant="ghost"
                            >
                              Use Template
                            </Button>
                          </HStack>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>
              </VStack>
            </TabPanel>

            {/* Monitoring Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <Heading size="lg">Workflow Monitoring</Heading>
                <Text color="gray.600">
                  Monitor the performance and execution of your workflows
                </Text>

                {/* Recent Executions */}
                <Card>
                  <CardHeader>
                    <Heading size="md">Recent Executions</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      {workflows
                        .flatMap((workflow) =>
                          workflow.lastRun
                            ? [
                                {
                                  workflow: workflow.name,
                                  status: "success" as const,
                                  timestamp: workflow.lastRun,
                                  duration: workflow.averageDuration,
                                },
                              ]
                            : [],
                        )
                        .slice(0, 5)
                        .map((execution, index) => (
                          <HStack
                            key={index}
                            justify="space-between"
                            p={3}
                            border="1px"
                            borderColor="gray.200"
                            borderRadius="md"
                          >
                            <VStack align="start" spacing={1}>
                              <Text fontWeight="medium">
                                {execution.workflow}
                              </Text>
                              <Text fontSize="sm" color="gray.500">
                                {formatDate(execution.timestamp)}
                              </Text>
                            </VStack>
                            <HStack>
                              <Badge
                                colorScheme={
                                  execution.status === "success"
                                    ? "green"
                                    : "red"
                                }
                              >
                                {execution.status}
                              </Badge>
                              <Text fontSize="sm" color="gray.500">
                                {execution.duration}s
                              </Text>
                            </HStack>
                          </HStack>
                        ))}
                    </VStack>
                  </CardBody>
                </Card>

                {/* Performance Metrics */}
                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                  <Card>
                    <CardHeader>
                      <Heading size="md">Workflow Health</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={4}>
                        {workflows.map((workflow) => (
                          <Box key={workflow.id} w="full">
                            <HStack justify="space-between" mb={2}>
                              <Text fontSize="sm" fontWeight="medium">
                                {workflow.name}
                              </Text>
                              <Text fontSize="sm" color="gray.500">
                                {Math.round(getSuccessRate(workflow))}%
                              </Text>
                            </HStack>
                            <Progress
                              value={getSuccessRate(workflow)}
                              colorScheme={
                                getSuccessRate(workflow) > 90
                                  ? "green"
                                  : getSuccessRate(workflow) > 70
                                    ? "yellow"
                                    : "red"
                              }
                              size="sm"
                            />
                          </Box>
                        ))}
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader>
                      <Heading size="md">Execution Trends</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={3} align="stretch">
                        <HStack justify="space-between">
                          <Text>Total Executions</Text>
                          <Text fontWeight="bold">
                            {workflows.reduce(
                              (sum, w) => sum + w.successCount + w.errorCount,
                              0,
                            )}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text>Success Rate</Text>
                          <Text fontWeight="bold" color="green.500">
                            {Math.round(
                              workflows.reduce(
                                (sum, w) => sum + getSuccessRate(w),
                                0,
                              ) / (workflows.length || 1),
                            )}
                            %
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text>Average Duration</Text>
                          <Text fontWeight="bold">
                            {Math.round(
                              workflows.reduce(
                                (sum, w) => sum + w.averageDuration,
                                0,
                              ) / (workflows.length || 1),
                            )}
                            s
                          </Text>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>
                </SimpleGrid>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Create Workflow Modal */}
        <Modal isOpen={isCreateOpen} onClose={onCreateClose} size="xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>
              {selectedTemplate
                ? `Create from "${selectedTemplate.name}"`
                : "Create New Workflow"}
            </ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Workflow Name</FormLabel>
                  <Input placeholder="Enter workflow name" />
                </FormControl>
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea placeholder="Describe what this workflow does" />
                </FormControl>
                {selectedTemplate && (
                  <Alert status="info">
                    <AlertIcon />
                    <Box>
                      <AlertTitle>Template Applied</AlertTitle>
                      <AlertDescription>
                        This workflow will start with the "
                        {selectedTemplate.name}" template configuration.
                      </AlertDescription>
                    </Box>
                  </Alert>
                )}
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button variant="ghost" mr={3} onClick={onCreateClose}>
                Cancel
              </Button>
              <Button colorScheme="blue" onClick={() => handleSaveWorkflow({})}>
                Create Workflow
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Workflow Editor Modal */}
        <Modal isOpen={isEditorOpen} onClose={onEditorClose} size="full">
          <ModalOverlay />
          <ModalContent maxW="90vw" h="90vh">
            <ModalHeader>Workflow Editor</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <Text fontWeight="bold">Workflow Configuration</Text>
                <FormControl>
                  <FormLabel>Workflow Name</FormLabel>
                  <Input placeholder="Enter workflow name" />
                </FormControl>
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea placeholder="Describe what this workflow does" />
                </FormControl>
                <FormControl>
                  <FormLabel>Trigger Type</FormLabel>
                  <Select placeholder="Select trigger">
                    <option value="schedule">Scheduled</option>
                    <option value="calendar_event">Calendar Event</option>
                    <option value="new_message">New Message</option>
                    <option value="new_task">New Task</option>
                    <option value="manual">Manual</option>
                  </Select>
                </FormControl>
                <Text fontWeight="bold" mt={4}>
                  Actions
                </Text>
                <Text color="gray.600">
                  Configure actions that will be executed when this workflow
                  runs.
                </Text>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button variant="ghost" mr={3} onClick={onEditorClose}>
                Cancel
              </Button>
              <Button colorScheme="blue">Save Changes</Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default EnhancedAutomationsPage;
