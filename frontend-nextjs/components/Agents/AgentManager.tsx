import React, { useState, useEffect } from "react";
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Card,
  CardHeader,
  CardBody,
  Badge,
  Button,
  IconButton,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  FormControl,
  FormLabel,
  Input,
  Select,
  Textarea,
  Switch,
  Progress,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Alert,
  AlertIcon,
  SimpleGrid,
  Flex,
  Spinner,
  useToast,
} from "@chakra-ui/react";
import { AddIcon, EditIcon, DeleteIcon, SettingsIcon } from "@chakra-ui/icons";
import { TriangleUpIcon, TriangleDownIcon } from "@chakra-ui/icons";

interface Agent {
  id: string;
  name: string;
  role: string;
  status: "active" | "inactive" | "error";
  capabilities: string[];
  performance: {
    tasksCompleted: number;
    successRate: number;
    avgResponseTime: number;
  };
  config: {
    model: string;
    temperature: number;
    maxTokens: number;
  };
}

interface AgentManagerProps {
  onAgentCreate?: (agent: Omit<Agent, "id">) => void;
  onAgentUpdate?: (id: string, updates: Partial<Agent>) => void;
  onAgentDelete?: (id: string) => void;
  onAgentStart?: (id: string) => void;
  onAgentStop?: (id: string) => void;
  initialAgents?: Agent[];
}

const AgentManager: React.FC<AgentManagerProps> = ({
  onAgentCreate,
  onAgentUpdate,
  onAgentDelete,
  onAgentStart,
  onAgentStop,
  initialAgents = [],
}) => {
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  const [newAgent, setNewAgent] = useState({
    name: "",
    role: "",
    capabilities: [] as string[],
    config: {
      model: "gpt-4",
      temperature: 0.7,
      maxTokens: 1000,
    },
  });

  const availableCapabilities = [
    "calendar_management",
    "task_management",
    "email_processing",
    "document_analysis",
    "financial_analysis",
    "social_media",
    "voice_commands",
    "workflow_automation",
  ];

  const handleCreateAgent = async () => {
    if (!newAgent.name.trim() || !newAgent.role.trim()) {
      toast({
        title: "Validation Error",
        description: "Name and role are required",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsLoading(true);
    try {
      const agentData = {
        ...newAgent,
        status: "inactive" as const,
        performance: {
          tasksCompleted: 0,
          successRate: 0,
          avgResponseTime: 0,
        },
      };

      onAgentCreate?.(agentData);

      // Simulate API call
      setTimeout(() => {
        const createdAgent: Agent = {
          id: Date.now().toString(),
          ...agentData,
        };

        setAgents((prev) => [...prev, createdAgent]);
        setNewAgent({
          name: "",
          role: "",
          capabilities: [],
          config: {
            model: "gpt-4",
            temperature: 0.7,
            maxTokens: 1000,
          },
        });
        onClose();

        toast({
          title: "Agent Created",
          description: `${createdAgent.name} has been created successfully`,
          status: "success",
          duration: 3000,
          isClosable: true,
        });
      }, 1000);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create agent",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateAgent = (id: string, updates: Partial<Agent>) => {
    setAgents((prev) =>
      prev.map((agent) => (agent.id === id ? { ...agent, ...updates } : agent)),
    );
    onAgentUpdate?.(id, updates);
  };

  const handleDeleteAgent = (id: string) => {
    setAgents((prev) => prev.filter((agent) => agent.id !== id));
    onAgentDelete?.(id);

    toast({
      title: "Agent Deleted",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleStartAgent = (id: string) => {
    handleUpdateAgent(id, { status: "active" });
    onAgentStart?.(id);

    toast({
      title: "Agent Started",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleStopAgent = (id: string) => {
    handleUpdateAgent(id, { status: "inactive" });
    onAgentStop?.(id);

    toast({
      title: "Agent Stopped",
      status: "info",
      duration: 2000,
      isClosable: true,
    });
  };

  const toggleCapability = (capability: string) => {
    setNewAgent((prev) => ({
      ...prev,
      capabilities: prev.capabilities.includes(capability)
        ? prev.capabilities.filter((c) => c !== capability)
        : [...prev.capabilities, capability],
    }));
  };

  const getStatusColor = (status: Agent["status"]) => {
    switch (status) {
      case "active":
        return "green";
      case "inactive":
        return "gray";
      case "error":
        return "red";
      default:
        return "gray";
    }
  };

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Flex justify="space-between" align="center">
          <VStack align="start" spacing={1}>
            <Heading size="lg">Agent Manager</Heading>
            <Text color="gray.600">Manage and monitor your AI agents</Text>
          </VStack>
          <Button leftIcon={<AddIcon />} colorScheme="blue" onClick={onOpen}>
            Create Agent
          </Button>
        </Flex>

        {/* Agent Grid */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
          {agents.map((agent) => (
            <Card key={agent.id} size="lg">
              <CardHeader>
                <Flex justify="space-between" align="center">
                  <VStack align="start" spacing={1}>
                    <Heading size="md">{agent.name}</Heading>
                    <Text color="gray.600" fontSize="sm">
                      {agent.role}
                    </Text>
                  </VStack>
                  <Badge colorScheme={getStatusColor(agent.status)}>
                    {agent.status}
                  </Badge>
                </Flex>
              </CardHeader>
              <CardBody>
                <VStack spacing={4} align="stretch">
                  {/* Capabilities */}
                  <Box>
                    <Text fontWeight="medium" mb={2}>
                      Capabilities
                    </Text>
                    <HStack spacing={1} flexWrap="wrap">
                      {agent.capabilities.map((capability) => (
                        <Badge key={capability} colorScheme="blue" size="sm">
                          {capability.replace("_", " ")}
                        </Badge>
                      ))}
                    </HStack>
                  </Box>

                  {/* Performance */}
                  <Box>
                    <Text fontWeight="medium" mb={2}>
                      Performance
                    </Text>
                    <VStack spacing={2} align="stretch">
                      <Flex justify="space-between">
                        <Text fontSize="sm">Tasks Completed</Text>
                        <Text fontSize="sm" fontWeight="medium">
                          {agent.performance.tasksCompleted}
                        </Text>
                      </Flex>
                      <Flex justify="space-between">
                        <Text fontSize="sm">Success Rate</Text>
                        <Text fontSize="sm" fontWeight="medium">
                          {agent.performance.successRate}%
                        </Text>
                      </Flex>
                      <Flex justify="space-between">
                        <Text fontSize="sm">Avg Response</Text>
                        <Text fontSize="sm" fontWeight="medium">
                          {agent.performance.avgResponseTime}ms
                        </Text>
                      </Flex>
                    </VStack>
                  </Box>

                  {/* Actions */}
                  <HStack spacing={2}>
                    {agent.status === "active" ? (
                      <IconButton
                        aria-label="Stop agent"
                        icon={<TriangleDownIcon />}
                        colorScheme="red"
                        size="sm"
                        onClick={() => handleStopAgent(agent.id)}
                      />
                    ) : (
                      <IconButton
                        aria-label="Start agent"
                        icon={<TriangleUpIcon />}
                        colorScheme="green"
                        size="sm"
                        onClick={() => handleStartAgent(agent.id)}
                      />
                    )}
                    <IconButton
                      aria-label="Edit agent"
                      icon={<EditIcon />}
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedAgent(agent);
                        onOpen();
                      }}
                    />
                    <IconButton
                      aria-label="Delete agent"
                      icon={<DeleteIcon />}
                      size="sm"
                      variant="ghost"
                      colorScheme="red"
                      onClick={() => handleDeleteAgent(agent.id)}
                    />
                  </HStack>
                </VStack>
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>

        {agents.length === 0 && (
          <Card>
            <CardBody textAlign="center" py={10}>
              <VStack spacing={4}>
                <Heading size="md" color="gray.500">
                  No Agents Created
                </Heading>
                <Text color="gray.600">
                  Create your first agent to get started with multi-agent
                  automation
                </Text>
                <Button
                  leftIcon={<AddIcon />}
                  colorScheme="blue"
                  onClick={onOpen}
                >
                  Create First Agent
                </Button>
              </VStack>
            </CardBody>
          </Card>
        )}
      </VStack>

      {/* Create/Edit Agent Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {selectedAgent ? "Edit Agent" : "Create New Agent"}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            <VStack spacing={4} align="stretch">
              <FormControl isRequired>
                <FormLabel>Agent Name</FormLabel>
                <Input
                  value={newAgent.name}
                  onChange={(e) =>
                    setNewAgent((prev) => ({ ...prev, name: e.target.value }))
                  }
                  placeholder="Enter agent name"
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Role</FormLabel>
                <Input
                  value={newAgent.role}
                  onChange={(e) =>
                    setNewAgent((prev) => ({ ...prev, role: e.target.value }))
                  }
                  placeholder="Enter agent role"
                />
              </FormControl>

              <FormControl>
                <FormLabel>Capabilities</FormLabel>
                <SimpleGrid columns={2} spacing={2}>
                  {availableCapabilities.map((capability) => (
                    <Button
                      key={capability}
                      size="sm"
                      variant={
                        newAgent.capabilities.includes(capability)
                          ? "solid"
                          : "outline"
                      }
                      colorScheme={
                        newAgent.capabilities.includes(capability)
                          ? "blue"
                          : "gray"
                      }
                      onClick={() => toggleCapability(capability)}
                    >
                      {capability.replace("_", " ")}
                    </Button>
                  ))}
                </SimpleGrid>
              </FormControl>

              <FormControl>
                <FormLabel>Model Configuration</FormLabel>
                <VStack spacing={3} align="stretch">
                  <Select
                    value={newAgent.config.model}
                    onChange={(e) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        config: { ...prev.config, model: e.target.value },
                      }))
                    }
                  >
                    <option value="gpt-4">GPT-4</option>
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                    <option value="claude-2">Claude 2</option>
                    <option value="llama-2">Llama 2</option>
                  </Select>

                  <Box>
                    <FormLabel>
                      Temperature: {newAgent.config.temperature}
                    </FormLabel>
                    <Input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={newAgent.config.temperature}
                      onChange={(e) =>
                        setNewAgent((prev) => ({
                          ...prev,
                          config: {
                            ...prev.config,
                            temperature: parseFloat(e.target.value),
                          },
                        }))
                      }
                    />
                  </Box>

                  <Box>
                    <FormLabel>
                      Max Tokens: {newAgent.config.maxTokens}
                    </FormLabel>
                    <Input
                      type="range"
                      min="100"
                      max="4000"
                      step="100"
                      value={newAgent.config.maxTokens}
                      onChange={(e) =>
                        setNewAgent((prev) => ({
                          ...prev,
                          config: {
                            ...prev.config,
                            maxTokens: parseInt(e.target.value),
                          },
                        }))
                      }
                    />
                  </Box>
                </VStack>
              </FormControl>

              <Alert status="info">
                <AlertIcon />
                Agents can be started and stopped as needed. Active agents will
                process tasks automatically.
              </Alert>

              <HStack spacing={3} justify="flex-end">
                <Button variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button
                  colorScheme="blue"
                  onClick={handleCreateAgent}
                  isLoading={isLoading}
                  isDisabled={!newAgent.name.trim() || !newAgent.role.trim()}
                >
                  {selectedAgent ? "Update Agent" : "Create Agent"}
                </Button>
              </HStack>
            </VStack>
          </ModalBody>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default AgentManager;
