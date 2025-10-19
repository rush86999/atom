import React, { useState, useEffect } from "react";
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Grid,
  GridItem,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Button,
  IconButton,
  Badge,
  Spinner,
  useToast,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Input,
  Select,
  FormControl,
  FormLabel,
  FormHelperText,
  Textarea,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Progress,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Code,
  Divider,
  Flex,
  Tooltip,
  Switch,
  Tag,
  TagLabel,
  TagCloseButton,
} from "@chakra-ui/react";
import {
  AddIcon,
  CheckIcon,
  CloseIcon,
  EditIcon,
  DeleteIcon,
  ViewIcon,
  ArrowForwardIcon,
  SettingsIcon,
  CalendarIcon,
  TimeIcon,
  ChatIcon,
  EmailIcon,
  AttachmentIcon,
  DownloadIcon,
  RepeatIcon,
} from "@chakra-ui/icons";

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  steps: WorkflowStep[];
  input_schema: any;
}

interface WorkflowStep {
  id: string;
  type: string;
  service?: string;
  action?: string;
  parameters: Record<string, any>;
  name: string;
}

interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  steps: WorkflowStep[];
  input_schema: any;
  created_at: string;
  updated_at: string;
}

interface WorkflowExecution {
  execution_id: string;
  workflow_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  start_time: string;
  end_time?: string;
  current_step: number;
  total_steps: number;
  trigger_data?: Record<string, any>;
  results?: Record<string, any>;
  errors?: string[];
  has_errors?: boolean;
}

interface ServiceInfo {
  name: string;
  actions: string[];
  description: string;
}

const WorkflowAutomation: React.FC = () => {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [services, setServices] = useState<Record<string, ServiceInfo>>({});
  const [selectedTemplate, setSelectedTemplate] =
    useState<WorkflowTemplate | null>(null);
  const [selectedWorkflow, setSelectedWorkflow] =
    useState<WorkflowDefinition | null>(null);
  const [activeExecution, setActiveExecution] =
    useState<WorkflowExecution | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [activeTab, setActiveTab] = useState(0);

  const {
    isOpen: isTemplateModalOpen,
    onOpen: onTemplateModalOpen,
    onClose: onTemplateModalClose,
  } = useDisclosure();
  const {
    isOpen: isExecutionModalOpen,
    onOpen: onExecutionModalOpen,
    onClose: onExecutionModalClose,
  } = useDisclosure();
  const {
    isOpen: isCreateModalOpen,
    onOpen: onCreateModalOpen,
    onClose: onCreateModalClose,
  } = useDisclosure();

  const toast = useToast();

  // Fetch initial data
  useEffect(() => {
    fetchWorkflowData();
  }, []);

  const fetchWorkflowData = async () => {
    try {
      setLoading(true);
      await Promise.all([
        fetchTemplates(),
        fetchWorkflows(),
        fetchExecutions(),
        fetchServices(),
      ]);
    } catch (error) {
      console.error("Error fetching workflow data:", error);
      toast({
        title: "Error",
        description: "Failed to load workflow data",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchTemplates = async () => {
    const response = await fetch("/api/workflows/templates");
    const data = await response.json();
    if (data.success) {
      setTemplates(data.templates);
    }
  };

  const fetchWorkflows = async () => {
    const response = await fetch("/api/workflows/definitions");
    const data = await response.json();
    if (data.success) {
      setWorkflows(data.workflows);
    }
  };

  const fetchExecutions = async () => {
    const response = await fetch("/api/workflows/executions");
    const data = await response.json();
    if (data.success) {
      setExecutions(data.executions);
    }
  };

  const fetchServices = async () => {
    const response = await fetch("/api/workflows/services");
    const data = await response.json();
    if (data.success) {
      setServices(data.services);
    }
  };

  const handleTemplateSelect = (template: WorkflowTemplate) => {
    setSelectedTemplate(template);
    onTemplateModalOpen();
  };

  const handleWorkflowSelect = (workflow: WorkflowDefinition) => {
    setSelectedWorkflow(workflow);
    onCreateModalOpen();
  };

  const handleExecuteWorkflow = async (
    workflowId: string,
    inputData: Record<string, any> = {},
  ) => {
    try {
      setExecuting(true);
      const response = await fetch("/api/workflows/execute", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          workflow_id: workflowId,
          input: inputData,
        }),
      });

      const data = await response.json();
      if (data.success) {
        toast({
          title: "Workflow Started",
          description: `Execution ${data.execution_id} has started`,
          status: "success",
          duration: 3000,
          isClosable: true,
        });

        // Refresh executions list
        await fetchExecutions();

        // Show execution details
        setActiveExecution(data);
        onExecutionModalOpen();
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error("Error executing workflow:", error);
      toast({
        title: "Error",
        description: "Failed to execute workflow",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setExecuting(false);
    }
  };

  const handleCancelExecution = async (executionId: string) => {
    try {
      const response = await fetch(
        `/api/workflows/executions/${executionId}/cancel`,
        {
          method: "POST",
        },
      );

      const data = await response.json();
      if (data.success) {
        toast({
          title: "Execution Cancelled",
          description: `Execution ${executionId} has been cancelled`,
          status: "info",
          duration: 3000,
          isClosable: true,
        });
        await fetchExecutions();
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error("Error cancelling execution:", error);
      toast({
        title: "Error",
        description: "Failed to cancel execution",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleFormChange = (field: string, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const renderServiceIcon = (service: string) => {
    const iconProps = { boxSize: 4, mr: 2 };
    switch (service) {
      case "calendar":
        return <CalendarIcon {...iconProps} color="blue.500" />;
      case "tasks":
        return <CheckIcon {...iconProps} color="green.500" />;
      case "messages":
        return <ChatIcon {...iconProps} color="purple.500" />;
      case "email":
        return <EmailIcon {...iconProps} color="red.500" />;
      case "documents":
        return <AttachmentIcon {...iconProps} color="orange.500" />;
      case "asana":
        return <ViewIcon {...iconProps} color="teal.500" />;
      case "trello":
        return <ViewIcon {...iconProps} color="blue.500" />;
      case "notion":
        return <ViewIcon {...iconProps} color="gray.500" />;
      case "dropbox":
        return <DownloadIcon {...iconProps} color="blue.500" />;
      default:
        return <SettingsIcon {...iconProps} color="gray.500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "green";
      case "running":
        return "blue";
      case "failed":
        return "red";
      case "cancelled":
        return "orange";
      case "pending":
        return "yellow";
      default:
        return "gray";
    }
  };

  const renderInputField = (field: string, schema: any) => {
    const fieldSchema = schema.properties[field];
    const isRequired = schema.required?.includes(field);

    switch (fieldSchema.type) {
      case "string":
        if (fieldSchema.format === "email") {
          return (
            <FormControl key={field} isRequired={isRequired}>
              <FormLabel>{fieldSchema.title}</FormLabel>
              <Input
                type="email"
                value={formData[field] || ""}
                onChange={(e) => handleFormChange(field, e.target.value)}
                placeholder={fieldSchema.title}
              />
              {fieldSchema.description && (
                <FormHelperText>{fieldSchema.description}</FormHelperText>
              )}
            </FormControl>
          );
        } else if (fieldSchema.format === "date") {
          return (
            <FormControl key={field} isRequired={isRequired}>
              <FormLabel>{fieldSchema.title}</FormLabel>
              <Input
                type="date"
                value={formData[field] || ""}
                onChange={(e) => handleFormChange(field, e.target.value)}
              />
            </FormControl>
          );
        } else {
          return (
            <FormControl key={field} isRequired={isRequired}>
              <FormLabel>{fieldSchema.title}</FormLabel>
              <Input
                type="text"
                value={formData[field] || ""}
                onChange={(e) => handleFormChange(field, e.target.value)}
                placeholder={fieldSchema.title}
              />
              {fieldSchema.description && (
                <FormHelperText>{fieldSchema.description}</FormHelperText>
              )}
            </FormControl>
          );
        }

      case "array":
        return (
          <FormControl key={field} isRequired={isRequired}>
            <FormLabel>{fieldSchema.title}</FormLabel>
            <Textarea
              value={
                Array.isArray(formData[field]) ? formData[field].join(", ") : ""
              }
              onChange={(e) =>
                handleFormChange(
                  field,
                  e.target.value.split(",").map((s) => s.trim()),
                )
              }
              placeholder={`Enter ${fieldSchema.title} separated by commas`}
            />
            <FormHelperText>
              Separate multiple values with commas
            </FormHelperText>
          </FormControl>
        );

      default:
        return (
          <FormControl key={field} isRequired={isRequired}>
            <FormLabel>{fieldSchema.title}</FormLabel>
            <Input
              type="text"
              value={formData[field] || ""}
              onChange={(e) => handleFormChange(field, e.target.value)}
              placeholder={fieldSchema.title}
            />
          </FormControl>
        );
    }
  };

  if (loading) {
    return (
      <Box p={8}>
        <VStack spacing={4} align="center">
          <Spinner size="xl" />
          <Text>Loading workflow automation...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box p={8}>
      {/* Header */}
      <HStack justify="space-between" mb={8}>
        <VStack align="start" spacing={1}>
          <Heading size="xl">Workflow Automation</Heading>
          <Text color="gray.600">
            Automate your tasks and processes across all connected services
          </Text>
        </VStack>
        <Button
          leftIcon={<AddIcon />}
          colorScheme="blue"
          onClick={onCreateModalOpen}
        >
          Create Workflow
        </Button>
      </HStack>

      {/* Main Content */}
      <Tabs variant="enclosed" onChange={setActiveTab}>
        <TabList>
          <Tab>Templates</Tab>
          <Tab>My Workflows</Tab>
          <Tab>Executions</Tab>
          <Tab>Services</Tab>
        </TabList>

        <TabPanels>
          {/* Templates Tab */}
          <TabPanel>
            <Grid
              templateColumns="repeat(auto-fill, minmax(300px, 1fr))"
              gap={6}
            >
              {templates.map((template) => (
                <Card
                  key={template.id}
                  cursor="pointer"
                  _hover={{ shadow: "md" }}
                >
                  <CardHeader>
                    <HStack justify="space-between">
                      <HStack>
                        {renderServiceIcon(template.category)}
                        <Heading size="md">{template.name}</Heading>
                      </HStack>
                      <Badge colorScheme="blue">
                        {template.steps.length} steps
                      </Badge>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    <Text color="gray.600" mb={4}>
                      {template.description}
                    </Text>
                    <VStack align="start" spacing={2}>
                      {template.steps.slice(0, 3).map((step, index) => (
                        <HStack key={step.id} spacing={2}>
                          <Badge size="sm" colorScheme="gray">
                            {index + 1}
                          </Badge>
                          <Text fontSize="sm">{step.name}</Text>
                        </HStack>
                      ))}
                      {template.steps.length > 3 && (
                        <Text fontSize="sm" color="gray.500">
                          +{template.steps.length - 3} more steps
                        </Text>
                      )}
                    </VStack>
                  </CardBody>
                  <CardFooter>
                    <Button
                      size="sm"
                      colorScheme="blue"
                      w="full"
                      onClick={() => handleTemplateSelect(template)}
                    >
                      Use Template
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </Grid>
          </TabPanel>

          {/* My Workflows Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              {workflows.map((workflow) => (
                <Card key={workflow.id}>
                  <CardHeader>
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1}>
                        <Heading size="md">{workflow.name}</Heading>
                        <Text color="gray.600">{workflow.description}</Text>
                      </VStack>
                      <HStack>
                        <Badge colorScheme="green">
                          {workflow.steps_count} steps
                        </Badge>
                        <IconButton
                          aria-label="Edit workflow"
                          icon={<EditIcon />}
                          size="sm"
                          variant="ghost"
                        />
                        <IconButton
                          aria-label="Execute workflow"
                          icon={<ArrowForwardIcon />}
                          size="sm"
                          colorScheme="blue"
                          onClick={() => handleWorkflowSelect(workflow)}
                        />
                      </HStack>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    <Text fontSize="sm" color="gray.500">
                      Created:{" "}
                      {new Date(workflow.created_at).toLocaleDateString()}
                    </Text>
                  </CardBody>
                </Card>
              ))}
              {workflows.length === 0 && (
                <Alert status="info">
                  <AlertIcon />
                  <Box>
                    <AlertTitle>No workflows yet</AlertTitle>
                    <AlertDescription>
                      Create your first workflow using a template or from
                      scratch.
                    </AlertDescription>
                  </Box>
                </Alert>
              )}
            </VStack>
          </TabPanel>

          {/* Executions Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              {executions.map((execution) => (
                <Card key={execution.execution_id}>
                  <CardBody>
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1}>
                        <HStack>
                          <Badge colorScheme={getStatusColor(execution.status)}>
                            {execution.status}
                          </Badge>
                          <Text fontWeight="bold">{execution.workflow_id}</Text>
                        </HStack>
                        <Text fontSize="sm" color="gray.600">
                          Started:{" "}
                          {new Date(execution.start_time).toLocaleString()}
                        </Text>
                        {execution.end_time && (
                          <Text fontSize="sm" color="gray.600">
                            Ended:{" "}
                            {new Date(execution.end_time).toLocaleString()}
                          </Text>
                        )}
                      </VStack>
                      <HStack>
                        <Progress
                          value={
                            (execution.current_step / execution.total_steps) *
                            100
                          }
                          size="sm"
                          width="100px"
                          colorScheme={getStatusColor(execution.status)}
                        />
                        <Text fontSize="sm">
                          {execution.current_step}/{execution.total_steps}
                        </Text>
                        {execution.status === "running" && (
                          <Button
                            size="sm"
                            colorScheme="red"
                            onClick={() =>
                              handleCancelExecution(execution.execution_id)
                            }
                          >
                            Cancel
                          </Button>
                        )}
                        <IconButton
                          aria-label="View execution details"
                          icon={<ViewIcon />}
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setActiveExecution(execution);
                            onExecutionModalOpen();
                          }}
                        />
                      </HStack>
                    </HStack>
                  </CardBody>
                </Card>
              ))}
              {executions.length === 0 && (
                <Alert status="info">
                  <AlertIcon />
                  <Box>
                    <AlertTitle>No executions yet</AlertTitle>
                    <AlertDescription>
                      Execute a workflow to see execution history here.
                    </AlertDescription>
                  </Box>
                </Alert>
              )}
            </VStack>
          </TabPanel>

          {/* Services Tab */}
          <TabPanel>
            <Grid
              templateColumns="repeat(auto-fill, minmax(300px, 1fr))"
              gap={6}
            >
              {Object.entries(services).map(([serviceName, serviceInfo]) => (
                <Card key={serviceName}>
                  <CardHeader>
                    <HStack>
                      {renderServiceIcon(serviceName)}
                      <Heading size="md">{serviceName}</Heading>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    <Text color="gray.600" mb={4}>
                      {serviceInfo.description}
                    </Text>
                    <VStack align="start" spacing={2}>
                      <Text fontWeight="bold">Available Actions:</Text>
                      {serviceInfo.actions.slice(0, 5).map((action) => (
                        <Tag key={action} size="sm" colorScheme="blue">
                          <TagLabel>{action}</TagLabel>
                        </Tag>
                      ))}
                      {serviceInfo.actions.length > 5 && (
                        <Text fontSize="sm" color="gray.500">
                          +{serviceInfo.actions.length - 5} more actions
                        </Text>
                      )}
                    </VStack>
                  </CardBody>
                  <CardFooter>
                    <Badge colorScheme="green">
                      {serviceInfo.actions.length} actions
                    </Badge>
                  </CardFooter>
                </Card>
              ))}
            </Grid>
          </TabPanel>
        </TabPanels>
      </Tabs>

      {/* Template Execution Modal */}
      <Modal
        isOpen={isTemplateModalOpen}
        onClose={onTemplateModalClose}
        size="xl"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Use Template: {selectedTemplate?.name}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedTemplate && (
              <VStack spacing={4} align="stretch">
                <Text>{selectedTemplate.description}</Text>
                <Divider />
                <Text fontWeight="bold">Workflow Steps:</Text>
                <VStack align="start" spacing={2}>
                  {selectedTemplate.steps.map((step, index) => (
                    <HStack key={step.id} spacing={3}>
                      <Badge colorScheme="blue">{index + 1}</Badge>
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="medium">{step.name}</Text>
                        <Text fontSize="sm" color="gray.600">
                          {step.service}.{step.action}
                        </Text>
                      </VStack>
                    </HStack>
                  ))}
                </VStack>
                <Divider />
                <Text fontWeight="bold">Input Parameters:</Text>
                <VStack spacing={3}>
                  {selectedTemplate.input_schema?.properties &&
                    Object.keys(selectedTemplate.input_schema.properties).map(
                      (field) =>
                        renderInputField(field, selectedTemplate.input_schema),
                    )}
                </VStack>
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onTemplateModalClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              isLoading={executing}
              onClick={() => {
                if (selectedTemplate) {
                  handleExecuteWorkflow(selectedTemplate.id, formData);
                  onTemplateModalClose();
                }
              }}
            >
              Execute Workflow
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Workflow Execution Modal */}
      <Modal isOpen={isCreateModalOpen} onClose={onCreateModalClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Execute Workflow: {selectedWorkflow?.name}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedWorkflow && (
              <VStack spacing={4} align="stretch">
                <Text>{selectedWorkflow.description}</Text>
                <Divider />
                <Text fontWeight="bold">Workflow Steps:</Text>
                <VStack align="start" spacing={2}>
                  {selectedWorkflow.steps?.map((step, index) => (
                    <HStack key={step.id} spacing={3}>
                      <Badge colorScheme="blue">{index + 1}</Badge>
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="medium">{step.name}</Text>
                        <Text fontSize="sm" color="gray.600">
                          {step.service}.{step.action}
                        </Text>
                      </VStack>
                    </HStack>
                  ))}
                </VStack>
                <Divider />
                <Text fontWeight="bold">Input Parameters:</Text>
                <VStack spacing={3}>
                  {selectedWorkflow.input_schema?.properties &&
                    Object.keys(selectedWorkflow.input_schema.properties).map(
                      (field) =>
                        renderInputField(field, selectedWorkflow.input_schema),
                    )}
                </VStack>
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onCreateModalClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              isLoading={executing}
              onClick={() => {
                if (selectedWorkflow) {
                  handleExecuteWorkflow(selectedWorkflow.id, formData);
                  onCreateModalClose();
                }
              }}
            >
              Execute Workflow
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Execution Details Modal */}
      <Modal
        isOpen={isExecutionModalOpen}
        onClose={onExecutionModalClose}
        size="2xl"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Execution Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {activeExecution && (
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <VStack align="start" spacing={1}>
                    <Text fontWeight="bold">
                      Execution ID: {activeExecution.execution_id}
                    </Text>
                    <Text>Workflow: {activeExecution.workflow_id}</Text>
                  </VStack>
                  <Badge
                    colorScheme={getStatusColor(activeExecution.status)}
                    size="lg"
                  >
                    {activeExecution.status}
                  </Badge>
                </HStack>

                <Divider />

                <HStack justify="space-between">
                  <Text>
                    Started:{" "}
                    {new Date(activeExecution.start_time).toLocaleString()}
                  </Text>
                  {activeExecution.end_time && (
                    <Text>
                      Ended:{" "}
                      {new Date(activeExecution.end_time).toLocaleString()}
                    </Text>
                  )}
                </HStack>

                <Progress
                  value={
                    (activeExecution.current_step /
                      activeExecution.total_steps) *
                    100
                  }
                  colorScheme={getStatusColor(activeExecution.status)}
                  size="lg"
                  hasStripe={activeExecution.status === "running"}
                  isAnimated={activeExecution.status === "running"}
                />
                <Text textAlign="center">
                  Step {activeExecution.current_step} of{" "}
                  {activeExecution.total_steps}
                </Text>

                {activeExecution.results &&
                  Object.keys(activeExecution.results).length > 0 && (
                    <>
                      <Divider />
                      <Text fontWeight="bold">Step Results:</Text>
                      <Accordion allowMultiple>
                        {Object.entries(activeExecution.results).map(
                          ([stepId, result]) => (
                            <AccordionItem key={stepId}>
                              <h2>
                                <AccordionButton>
                                  <Box flex="1" textAlign="left">
                                    Step: {stepId}
                                  </Box>
                                  <AccordionIcon />
                                </AccordionButton>
                              </h2>
                              <AccordionPanel pb={4}>
                                <Code whiteSpace="pre-wrap" fontSize="sm">
                                  {JSON.stringify(result, null, 2)}
                                </Code>
                              </AccordionPanel>
                            </AccordionItem>
                          ),
                        )}
                      </Accordion>
                    </>
                  )}

                {activeExecution.errors &&
                  activeExecution.errors.length > 0 && (
                    <>
                      <Divider />
                      <Alert status="error">
                        <AlertIcon />
                        <Box>
                          <AlertTitle>Errors</AlertTitle>
                          {activeExecution.errors.map((error, index) => (
                            <AlertDescription key={index}>
                              {error}
                            </AlertDescription>
                          ))}
                        </Box>
                      </Alert>
                    </>
                  )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" onClick={onExecutionModalClose}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default WorkflowAutomation;
