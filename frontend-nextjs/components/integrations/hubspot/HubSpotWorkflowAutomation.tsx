import React, { useState, useCallback } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Card,
  CardBody,
  Button,
  Input,
  Select,
  FormControl,
  FormLabel,
  FormHelperText,
  Switch,
  Badge,
  useColorModeValue,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  SimpleGrid,
  Icon,
  Flex,
  Divider,
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
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Portal,
} from "@chakra-ui/react";
import {
  FiPlus,
  FiPlay,
  FiPause,
  FiEdit,
  FiTrash2,
  FiZap,
  FiClock,
  FiUsers,
  FiMail,
  FiTarget,
} from "react-icons/fi";

export interface WorkflowTrigger {
  id: string;
  name: string;
  type: "lead_score" | "behavior" | "engagement" | "company_size" | "custom";
  condition: string;
  value: any;
  enabled: boolean;
}

export interface WorkflowAction {
  id: string;
  type: "email" | "task" | "notification" | "assignment" | "webhook";
  config: Record<string, any>;
  delay?: number;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  triggers: WorkflowTrigger[];
  actions: WorkflowAction[];
  enabled: boolean;
  lastRun?: string;
  runs: number;
  successRate: number;
}

export interface WorkflowExecution {
  id: string;
  workflowId: string;
  contactId: string;
  status: "running" | "completed" | "failed" | "paused";
  startedAt: string;
  completedAt?: string;
  actionsCompleted: number;
  totalActions: number;
}

interface HubSpotWorkflowAutomationProps {
  workflows?: Workflow[];
  onWorkflowCreate?: (workflow: Omit<Workflow, "id">) => void;
  onWorkflowUpdate?: (workflow: Workflow) => void;
  onWorkflowDelete?: (workflowId: string) => void;
  onWorkflowToggle?: (workflowId: string, enabled: boolean) => void;
}

const HubSpotWorkflowAutomation: React.FC<HubSpotWorkflowAutomationProps> = ({
  workflows = [],
  onWorkflowCreate,
  onWorkflowUpdate,
  onWorkflowDelete,
  onWorkflowToggle,
}) => {
  const [activeTab, setActiveTab] = useState(0);
  const [isCreating, setIsCreating] = useState(false);
  const [newWorkflow, setNewWorkflow] = useState<Omit<Workflow, "id">>({
    name: "",
    description: "",
    triggers: [],
    actions: [],
    enabled: true,
    runs: 0,
    successRate: 100,
  });

  const bgColor = useColorModeValue("white", "gray.800");
  const cardBg = useColorModeValue("gray.50", "gray.700");
  const borderColor = useColorModeValue("gray.200", "gray.600");

  const triggerTypes = [
    { value: "lead_score", label: "Lead Score", icon: FiTarget },
    { value: "behavior", label: "Behavior", icon: FiUsers },
    { value: "engagement", label: "Engagement", icon: FiMail },
    { value: "company_size", label: "Company Size", icon: FiTarget },
    { value: "custom", label: "Custom", icon: FiZap },
  ];

  const actionTypes = [
    { value: "email", label: "Send Email", icon: FiMail },
    { value: "task", label: "Create Task", icon: FiClock },
    { value: "notification", label: "Send Notification", icon: FiUsers },
    { value: "assignment", label: "Assign to Team", icon: FiTarget },
    { value: "webhook", label: "Webhook", icon: FiZap },
  ];

  const handleCreateWorkflow = useCallback(() => {
    if (!newWorkflow.name.trim()) return;

    onWorkflowCreate?.(newWorkflow);
    setNewWorkflow({
      name: "",
      description: "",
      triggers: [],
      actions: [],
      enabled: true,
      runs: 0,
      successRate: 100,
    });
    setIsCreating(false);
  }, [newWorkflow, onWorkflowCreate]);

  const handleAddTrigger = useCallback(
    (trigger: Omit<WorkflowTrigger, "id">) => {
      setNewWorkflow((prev) => ({
        ...prev,
        triggers: [
          ...prev.triggers,
          { ...trigger, id: `trigger-${Date.now()}` },
        ],
      }));
    },
    [],
  );

  const handleAddAction = useCallback((action: Omit<WorkflowAction, "id">) => {
    setNewWorkflow((prev) => ({
      ...prev,
      actions: [...prev.actions, { ...action, id: `action-${Date.now()}` }],
    }));
  }, []);

  const getStatusColor = (enabled: boolean) => {
    return enabled ? "green" : "gray";
  };

  const getSuccessRateColor = (rate: number) => {
    if (rate >= 90) return "green";
    if (rate >= 75) return "yellow";
    if (rate >= 50) return "orange";
    return "red";
  };

  return (
    <VStack spacing={6} align="stretch">
      {/* Header */}
      <HStack justify="space-between">
        <VStack align="start" spacing={1}>
          <Heading size="lg">Workflow Automation</Heading>
          <Text color="gray.600">
            Automate your sales and marketing processes with intelligent
            workflows
          </Text>
        </VStack>
        <Button
          colorScheme="blue"
          leftIcon={<Icon as={FiPlus} />}
          onClick={() => setIsCreating(true)}
        >
          Create Workflow
        </Button>
      </HStack>

      {/* Workflow Creation Modal */}
      {isCreating && (
        <Card bg={bgColor}>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Heading size="md">Create New Workflow</Heading>
                <Button variant="ghost" onClick={() => setIsCreating(false)}>
                  Cancel
                </Button>
              </HStack>

              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                <FormControl>
                  <FormLabel>Workflow Name</FormLabel>
                  <Input
                    value={newWorkflow.name}
                    onChange={(e) =>
                      setNewWorkflow((prev) => ({
                        ...prev,
                        name: e.target.value,
                      }))
                    }
                    placeholder="e.g., Hot Lead Follow-up"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Input
                    value={newWorkflow.description}
                    onChange={(e) =>
                      setNewWorkflow((prev) => ({
                        ...prev,
                        description: e.target.value,
                      }))
                    }
                    placeholder="Describe what this workflow does"
                  />
                </FormControl>
              </SimpleGrid>

              <Divider />

              {/* Triggers Section */}
              <VStack align="stretch" spacing={3}>
                <HStack justify="space-between">
                  <Heading size="sm">Triggers</Heading>
                  <Menu>
                    <MenuButton
                      as={Button}
                      size="sm"
                      leftIcon={<Icon as={FiPlus} />}
                    >
                      Add Trigger
                    </MenuButton>
                    <Portal>
                      <MenuList>
                        {triggerTypes.map((trigger) => (
                          <MenuItem
                            key={trigger.value}
                            icon={<Icon as={trigger.icon} />}
                            onClick={() =>
                              handleAddTrigger({
                                name: `${trigger.label} Trigger`,
                                type: trigger.value as any,
                                condition: "equals",
                                value: "",
                                enabled: true,
                              })
                            }
                          >
                            {trigger.label}
                          </MenuItem>
                        ))}
                      </MenuList>
                    </Portal>
                  </Menu>
                </HStack>

                {newWorkflow.triggers.map((trigger) => (
                  <Card key={trigger.id} bg={cardBg}>
                    <CardBody>
                      <VStack align="stretch" spacing={2}>
                        <HStack justify="space-between">
                          <Text fontWeight="medium">{trigger.name}</Text>
                          <HStack>
                            <Switch
                              size="sm"
                              isChecked={trigger.enabled}
                              onChange={() => {
                                // Toggle trigger enabled state
                              }}
                            />
                            <Button size="sm" variant="ghost" colorScheme="red">
                              <Icon as={FiTrash2} />
                            </Button>
                          </HStack>
                        </HStack>
                        <HStack>
                          <Select size="sm" value={trigger.condition}>
                            <option value="equals">Equals</option>
                            <option value="greater_than">Greater Than</option>
                            <option value="less_than">Less Than</option>
                            <option value="contains">Contains</option>
                          </Select>
                          <Input
                            size="sm"
                            value={trigger.value}
                            onChange={(e) => {
                              // Update trigger value
                            }}
                            placeholder="Value"
                          />
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>
                ))}
              </VStack>

              <Divider />

              {/* Actions Section */}
              <VStack align="stretch" spacing={3}>
                <HStack justify="space-between">
                  <Heading size="sm">Actions</Heading>
                  <Menu>
                    <MenuButton
                      as={Button}
                      size="sm"
                      leftIcon={<Icon as={FiPlus} />}
                    >
                      Add Action
                    </MenuButton>
                    <Portal>
                      <MenuList>
                        {actionTypes.map((action) => (
                          <MenuItem
                            key={action.value}
                            icon={<Icon as={action.icon} />}
                            onClick={() =>
                              handleAddAction({
                                type: action.value as any,
                                config: {},
                                delay: 0,
                              })
                            }
                          >
                            {action.label}
                          </MenuItem>
                        ))}
                      </MenuList>
                    </Portal>
                  </Menu>
                </HStack>

                {newWorkflow.actions.map((action) => (
                  <Card key={action.id} bg={cardBg}>
                    <CardBody>
                      <VStack align="stretch" spacing={2}>
                        <HStack justify="space-between">
                          <Text fontWeight="medium">
                            {
                              actionTypes.find((a) => a.value === action.type)
                                ?.label
                            }
                          </Text>
                          <HStack>
                            <Input
                              size="sm"
                              type="number"
                              value={action.delay || 0}
                              onChange={(e) => {
                                // Update action delay
                              }}
                              placeholder="Delay (minutes)"
                              width="100px"
                            />
                            <Button size="sm" variant="ghost" colorScheme="red">
                              <Icon as={FiTrash2} />
                            </Button>
                          </HStack>
                        </HStack>
                        {/* Action-specific configuration would go here */}
                      </VStack>
                    </CardBody>
                  </Card>
                ))}
              </VStack>

              <HStack justify="end">
                <Button
                  colorScheme="blue"
                  onClick={handleCreateWorkflow}
                  isDisabled={!newWorkflow.name.trim()}
                >
                  Create Workflow
                </Button>
              </HStack>
            </VStack>
          </CardBody>
        </Card>
      )}

      {/* Workflows List */}
      <Tabs variant="enclosed" colorScheme="blue">
        <TabList>
          <Tab>Active Workflows</Tab>
          <Tab>Workflow Analytics</Tab>
          <Tab>Templates</Tab>
        </TabList>

        <TabPanels>
          {/* Active Workflows Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              {workflows.length === 0 ? (
                <Card bg={cardBg}>
                  <CardBody>
                    <VStack spacing={4} align="center">
                      <Icon as={FiZap} boxSize={8} color="gray.400" />
                      <Text textAlign="center" color="gray.600">
                        No workflows created yet. Create your first workflow to
                        automate your processes.
                      </Text>
                      <Button
                        colorScheme="blue"
                        leftIcon={<Icon as={FiPlus} />}
                        onClick={() => setIsCreating(true)}
                      >
                        Create Workflow
                      </Button>
                    </VStack>
                  </CardBody>
                </Card>
              ) : (
                workflows.map((workflow) => (
                  <Card key={workflow.id} bg={bgColor}>
                    <CardBody>
                      <VStack align="stretch" spacing={3}>
                        <HStack justify="space-between">
                          <VStack align="start" spacing={1}>
                            <HStack>
                              <Text fontWeight="semibold">{workflow.name}</Text>
                              <Badge
                                colorScheme={getStatusColor(workflow.enabled)}
                              >
                                {workflow.enabled ? "Active" : "Paused"}
                              </Badge>
                            </HStack>
                            <Text fontSize="sm" color="gray.600">
                              {workflow.description}
                            </Text>
                          </VStack>
                          <HStack>
                            <Button
                              size="sm"
                              variant="ghost"
                              leftIcon={
                                <Icon
                                  as={workflow.enabled ? FiPause : FiPlay}
                                />
                              }
                              onClick={() =>
                                onWorkflowToggle?.(
                                  workflow.id,
                                  !workflow.enabled,
                                )
                              }
                            >
                              {workflow.enabled ? "Pause" : "Resume"}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              leftIcon={<Icon as={FiEdit} />}
                            >
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              colorScheme="red"
                              leftIcon={<Icon as={FiTrash2} />}
                              onClick={() => onWorkflowDelete?.(workflow.id)}
                            >
                              Delete
                            </Button>
                          </HStack>
                        </HStack>

                        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
                          <HStack>
                            <Icon as={FiZap} color="blue.500" />
                            <VStack align="start" spacing={0}>
                              <Text fontSize="sm" color="gray.600">
                                Triggers
                              </Text>
                              <Text fontWeight="medium">
                                {workflow.triggers.length}
                              </Text>
                            </VStack>
                          </HStack>
                          <HStack>
                            <Icon as={FiPlay} color="green.500" />
                            <VStack align="start" spacing={0}>
                              <Text fontSize="sm" color="gray.600">
                                Runs
                              </Text>
                              <Text fontWeight="medium">{workflow.runs}</Text>
                            </VStack>
                          </HStack>
                          <HStack>
                            <Icon as={FiTarget} color="orange.500" />
                            <VStack align="start" spacing={0}>
                              <Text fontSize="sm" color="gray.600">
                                Success Rate
                              </Text>
                              <Badge
                                colorScheme={getSuccessRateColor(
                                  workflow.successRate,
                                )}
                              >
                                {workflow.successRate}%
                              </Badge>
                            </VStack>
                          </HStack>
                        </SimpleGrid>

                        {workflow.lastRun && (
                          <Text fontSize="xs" color="gray.500">
                            Last run:{" "}
                            {new Date(workflow.lastRun).toLocaleString()}
                          </Text>
                        )}
                      </VStack>
                    </CardBody>
                  </Card>
                ))
              )}
            </VStack>
          </TabPanel>

          {/* Analytics Tab */}
          <TabPanel>
            <Card bg={bgColor}>
              <CardBody>
                <VStack spacing={4} align="stretch">
                  <Heading size="md">Workflow Analytics</Heading>
                  <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
                    <Card bg={cardBg}>
                      <CardBody>
                        <VStack spacing={2} align="center">
                          <Text
                            fontSize="2xl"
                            fontWeight="bold"
                            color="blue.500"
                          >
                            {workflows.length}
                          </Text>
                          <Text
                            fontSize="sm"
                            color="gray.600"
                            textAlign="center"
                          >
                            Total Workflows
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                    <Card bg={cardBg}>
                      <CardBody>
                        <VStack spacing={2} align="center">
                          <Text
                            fontSize="2xl"
                            fontWeight="bold"
                            color="green.500"
                          >
                            {workflows.filter((w) => w.enabled).length}
                          </Text>
                          <Text
                            fontSize="sm"
                            color="gray.600"
                            textAlign="center"
                          >
                            Active Workflows
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                    <Card bg={cardBg}>
                      <CardBody>
                        <VStack spacing={2} align="center">
                          <Text
                            fontSize="2xl"
                            fontWeight="bold"
                            color="orange.500"
                          >
                            {workflows.reduce((sum, w) => sum + w.runs, 0)}
                          </Text>
                          <Text
                            fontSize="sm"
                            color="gray.600"
                            textAlign="center"
                          >
                            Total Executions
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                  </SimpleGrid>
                </VStack>
              </CardBody>
            </Card>
          </TabPanel>

          {/* Templates Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              <Alert status="info">
                <AlertIcon />
                <Box>
                  <AlertTitle>Workflow Templates</AlertTitle>
                  <AlertDescription>
                    Pre-built workflow templates to help you get started
                    quickly.
                  </AlertDescription>
                </Box>
              </Alert>

              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                {/* Template cards would go here */}
                <Card
                  bg={cardBg}
                  cursor="pointer"
                  _hover={{ transform: "translateY(-2px)" }}
                >
                  <CardBody>
                    <VStack spacing={3} align="start">
                      <HStack>
                        <Icon as={FiMail} color="blue.500" />
                        <Text fontWeight="semibold">Welcome Sequence</Text>
                      </HStack>
                      <Text fontSize="sm" color="gray.600">
                        Automatically send welcome emails to new contacts
                      </Text>
                      <Button size="sm" colorScheme="blue" variant="outline">
                        Use Template
                      </Button>
                    </VStack>
                  </CardBody>
                </Card>

                <Card
                  bg={cardBg}
                  cursor="pointer"
                  _hover={{ transform: "translateY(-2px)" }}
                >
                  <CardBody>
                    <VStack spacing={3} align="start">
                      <HStack>
                        <Icon as={FiTarget} color="green.500" />
                        <Text fontWeight="semibold">Lead Nurturing</Text>
                      </HStack>
                      <Text fontSize="sm" color="gray.600">
                        Nurture leads with educational content and follow-ups
                      </Text>
                      <Button size="sm" colorScheme="blue" variant="outline">
                        Use Template
                      </Button>
                    </VStack>
                  </CardBody>
                </Card>

                <Card
                  bg={cardBg}
                  cursor="pointer"
                  _hover={{ transform: "translateY(-2px)" }}
                >
                  <CardBody>
                    <VStack spacing={3} align="start">
                      <HStack>
                        <Icon as={FiUsers} color="purple.500" />
                        <Text fontWeight="semibold">Re-engagement</Text>
                      </HStack>
                      <Text fontSize="sm" color="gray.600">
                        Re-engage inactive contacts with targeted campaigns
                      </Text>
                      <Button size="sm" colorScheme="blue" variant="outline">
                        Use Template
                      </Button>
                    </VStack>
                  </CardBody>
                </Card>

                <Card
                  bg={cardBg}
                  cursor="pointer"
                  _hover={{ transform: "translateY(-2px)" }}
                >
                  <CardBody>
                    <VStack spacing={3} align="start">
                      <HStack>
                        <Icon as={FiClock} color="orange.500" />
                        <Text fontWeight="semibold">Task Automation</Text>
                      </HStack>
                      <Text fontSize="sm" color="gray.600">
                        Automatically create tasks for sales team follow-ups
                      </Text>
                      <Button size="sm" colorScheme="blue" variant="outline">
                        Use Template
                      </Button>
                    </VStack>
                  </CardBody>
                </Card>
              </SimpleGrid>
            </VStack>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </VStack>
  );
};

export default HubSpotWorkflowAutomation;
