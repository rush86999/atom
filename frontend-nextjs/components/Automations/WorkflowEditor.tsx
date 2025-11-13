import React, { useState, useEffect, useRef } from 'react';
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
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Drawer,
  DrawerBody,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton
} from '@chakra-ui/react';
import { AddIcon, EditIcon, DeleteIcon, DragHandleIcon, SettingsIcon, ViewIcon, CopyIcon } from '@chakra-ui/icons';

interface WorkflowNode {
  id: string;
  type: 'trigger' | 'action' | 'condition' | 'delay' | 'webhook';
  title: string;
  description: string;
  position: { x: number; y: number };
  config: Record<string, any>;
  connections: string[];
}

interface WorkflowConnection {
  id: string;
  source: string;
  target: string;
  condition?: string;
}

interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  version: string;
  nodes: WorkflowNode[];
  connections: WorkflowConnection[];
  triggers: string[];
  enabled: boolean;
  createdAt: Date;
  updatedAt: Date;
}

interface WorkflowEditorProps {
  workflow?: WorkflowDefinition;
  onSave?: (workflow: WorkflowDefinition) => void;
  onTest?: (workflow: WorkflowDefinition) => void;
  onPublish?: (workflow: WorkflowDefinition) => void;
  showNavigation?: boolean;
  compactView?: boolean;
}

const WorkflowEditor: React.FC<WorkflowEditorProps> = ({
  workflow,
  onSave,
  onTest,
  onPublish,
  showNavigation = true,
  compactView = false
}) => {
  const [currentWorkflow, setCurrentWorkflow] = useState<WorkflowDefinition>(workflow || {
    id: '',
    name: '',
    description: '',
    version: '1.0.0',
    nodes: [],
    connections: [],
    triggers: [],
    enabled: false,
    createdAt: new Date(),
    updatedAt: new Date()
  });
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(null);
  const [draggingNode, setDraggingNode] = useState<WorkflowNode | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionSource, setConnectionSource] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'design' | 'code'>('design');
  const [loading, setLoading] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const { isOpen: isNodeModalOpen, onOpen: onNodeModalOpen, onClose: onNodeModalClose } = useDisclosure();
  const { isOpen: isPropertiesOpen, onOpen: onPropertiesOpen, onClose: onPropertiesClose } = useDisclosure();
  const toast = useToast();

  // Available node types
  const nodeTypes = [
    {
      type: 'trigger',
      title: 'Trigger',
      description: 'Start the workflow',
      icon: '⚡',
      color: 'green'
    },
    {
      type: 'action',
      title: 'Action',
      description: 'Perform an action',
      icon: '🛠️',
      color: 'blue'
    },
    {
      type: 'condition',
      title: 'Condition',
      description: 'Check a condition',
      icon: '❓',
      color: 'yellow'
    },
    {
      type: 'delay',
      title: 'Delay',
      description: 'Wait for a period',
      icon: '⏰',
      color: 'orange'
    },
    {
      type: 'webhook',
      title: 'Webhook',
      description: 'Send or receive webhook',
      icon: '🌐',
      color: 'purple'
    }
  ];

  // Available triggers
  const availableTriggers = [
    { id: 'schedule', name: 'Schedule', description: 'Run on a schedule' },
    { id: 'webhook', name: 'Webhook', description: 'Trigger via webhook' },
    { id: 'manual', name: 'Manual', description: 'Run manually' },
    { id: 'email', name: 'Email', description: 'Trigger on email' },
    { id: 'file', name: 'File Change', description: 'Trigger on file change' }
  ];

  // Available actions
  const availableActions = [
    { id: 'send_email', name: 'Send Email', description: 'Send an email' },
    { id: 'create_task', name: 'Create Task', description: 'Create a new task' },
    { id: 'update_record', name: 'Update Record', description: 'Update a database record' },
    { id: 'call_api', name: 'Call API', description: 'Make an API call' },
    { id: 'notify', name: 'Send Notification', description: 'Send a notification' },
    { id: 'transform_data', name: 'Transform Data', description: 'Transform data' }
  ];

  useEffect(() => {
    if (workflow) {
      setCurrentWorkflow(workflow);
    }
  }, [workflow]);

  const handleAddNode = (nodeType: WorkflowNode['type']) => {
    const newNode: WorkflowNode = {
      id: `node_${Date.now()}`,
      type: nodeType,
      title: `${nodeType.charAt(0).toUpperCase() + nodeType.slice(1)} Node`,
      description: `New ${nodeType} node`,
      position: { x: 100, y: 100 },
      config: {},
      connections: []
    };

    setCurrentWorkflow(prev => ({
      ...prev,
      nodes: [...prev.nodes, newNode],
      updatedAt: new Date()
    }));

    setSelectedNode(newNode);
    onNodeModalOpen();
  };

  const handleUpdateNode = (nodeId: string, updates: Partial<WorkflowNode>) => {
    setCurrentWorkflow(prev => ({
      ...prev,
      nodes: prev.nodes.map(node =>
        node.id === nodeId ? { ...node, ...updates, updatedAt: new Date() } : node
      ),
      updatedAt: new Date()
    }));
  };

  const handleDeleteNode = (nodeId: string) => {
    setCurrentWorkflow(prev => ({
      ...prev,
      nodes: prev.nodes.filter(node => node.id !== nodeId),
      connections: prev.connections.filter(conn =>
        conn.source !== nodeId && conn.target !== nodeId
      ),
      updatedAt: new Date()
    }));
    setSelectedNode(null);
  };

  const handleStartConnection = (sourceNodeId: string) => {
    setIsConnecting(true);
    setConnectionSource(sourceNodeId);
  };

  const handleCompleteConnection = (targetNodeId: string) => {
    if (isConnecting && connectionSource && connectionSource !== targetNodeId) {
      const newConnection: WorkflowConnection = {
        id: `conn_${Date.now()}`,
        source: connectionSource,
        target: targetNodeId
      };

      setCurrentWorkflow(prev => ({
        ...prev,
        connections: [...prev.connections, newConnection],
        updatedAt: new Date()
      }));
    }
    setIsConnecting(false);
    setConnectionSource(null);
  };

  const handleDeleteConnection = (connectionId: string) => {
    setCurrentWorkflow(prev => ({
      ...prev,
      connections: prev.connections.filter(conn => conn.id !== connectionId),
      updatedAt: new Date()
    }));
  };

  const handleSaveWorkflow = () => {
    if (!currentWorkflow.name.trim()) {
      toast({
        title: 'Workflow name required',
        status: 'error',
        duration: 2000,
        isClosable: true,
      });
      return;
    }

    if (currentWorkflow.nodes.length === 0) {
      toast({
        title: 'Add at least one node',
        status: 'error',
        duration: 2000,
        isClosable: true,
      });
      return;
    }

    onSave?.(currentWorkflow);
    toast({
      title: 'Workflow saved',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleTestWorkflow = () => {
    onTest?.(currentWorkflow);
    toast({
      title: 'Testing workflow',
      status: 'info',
      duration: 2000,
      isClosable: true,
    });
  };

  const handlePublishWorkflow = () => {
    onPublish?.(currentWorkflow);
    toast({
      title: 'Workflow published',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const getNodeColor = (nodeType: WorkflowNode['type']) => {
    const nodeTypeInfo = nodeTypes.find(nt => nt.type === nodeType);
    return nodeTypeInfo?.color || 'gray';
  };

  const NodePropertiesPanel: React.FC = () => {
    if (!selectedNode) return null;

    const [formData, setFormData] = useState({
      title: selectedNode.title,
      description: selectedNode.description,
      ...selectedNode.config
    });

    const handleSave = () => {
      handleUpdateNode(selectedNode.id, {
        title: formData.title,
        description: formData.description,
        config: formData
      });
      onPropertiesClose();
    };

    return (
      <Drawer isOpen={isPropertiesOpen} placement="right" onClose={onPropertiesClose} size="md">
        <DrawerOverlay />
        <DrawerContent>
          <DrawerCloseButton />
          <DrawerHeader>Node Properties</DrawerHeader>
          <DrawerBody>
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>Title</FormLabel>
                <Input
                  value={formData.title}
                  onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                />
              </FormControl>

              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  rows={3}
                />
              </FormControl>

              {selectedNode.type === 'trigger' && (
                <FormControl>
                  <FormLabel>Trigger Type</FormLabel>
                  <Select
                    value={formData.triggerType || ''}
                    onChange={(e) => setFormData(prev => ({ ...prev, triggerType: e.target.value }))}
                  >
                    <option value="">Select trigger type</option>
                    {availableTriggers.map(trigger => (
                      <option key={trigger.id} value={trigger.id}>
                        {trigger.name}
                      </option>
                    ))}
                  </Select>
                </FormControl>
              )}

              {selectedNode.type === 'action' && (
                <FormControl>
                  <FormLabel>Action Type</FormLabel>
                  <Select
                    value={formData.actionType || ''}
                    onChange={(e) => setFormData(prev => ({ ...prev, actionType: e.target.value }))}
                  >
                    <option value="">Select action type</option>
                    {availableActions.map(action => (
                      <option key={action.id} value={action.id}>
                        {action.name}
                      </option>
                    ))}
                  </Select>
                </FormControl>
              )}

              {selectedNode.type === 'condition' && (
                <FormControl>
                  <FormLabel>Condition Expression</FormLabel>
                  <Textarea
                    value={formData.condition || ''}
                    onChange={(e) => setFormData(prev => ({ ...prev, condition: e.target.value }))}
                    placeholder="e.g., data.value > 100"
                    rows={3}
                  />
                </FormControl>
              )}

              {selectedNode.type === 'delay' && (
                <FormControl>
                  <FormLabel>Delay Duration (seconds)</FormLabel>
                  <Input
                    type="number"
                    value={formData.delay || 0}
                    onChange={(e) => setFormData(prev => ({ ...prev, delay: parseInt(e.target.value) }))}
                    min="0"
                  />
                </FormControl>
              )}

              <HStack spacing={3}>
                <Button variant="outline" onClick={onPropertiesClose}>
                  Cancel
                </Button>
                <Button colorScheme="blue" onClick={handleSave}>
                  Save
                </Button>
              </HStack>
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    );
  };

  if (loading) {
    return (
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Loading workflow editor...</Text>
      </Box>
    );
  }

  return (
    <Box p={compactView ? 2 : 6}>
      <VStack spacing={compactView ? 3 : 6} align="stretch">
        {/* Header */}
        {showNavigation && (
          <Flex justify="space-between" align="center">
            <VStack align="start" spacing={1}>
              <Heading size={compactView ? "md" : "lg"}>Workflow Editor</Heading>
              <Text color="gray.600" fontSize="sm">
                {currentWorkflow.name || 'Untitled Workflow'}
              </Text>
            </VStack>
            <HStack spacing={2}>
              <Button
                variant={viewMode === 'design' ? 'solid' : 'outline'}
                size="sm"
                onClick={() => setViewMode('design')}
              >
                Design
              </Button>
              <Button
                variant={viewMode === 'code' ? 'solid' : 'outline'}
                size="sm"
                onClick={() => setViewMode('code')}
              >
                Code
              </Button>
              <Button
                colorScheme="blue"
                size={compactView ? "sm" : "md"}
                onClick={handleSaveWorkflow}
              >
                Save
              </Button>
              <Button
                colorScheme="green"
                size={compactView ? "sm" : "md"}
                onClick={handleTestWorkflow}
              >
                Test
              </Button>
              <Button
                colorScheme="purple"
                size={compactView ? "sm" : "md"}
                onClick={handlePublishWorkflow}
              >
                Publish
              </Button>
            </HStack>
          </Flex>
        )}

        {/* Workflow Properties */}
        {showNavigation && (
          <Card>
            <CardHeader>
              <Heading size="sm">Workflow Properties</Heading>
            </CardHeader>
            <CardBody>
              <SimpleGrid columns={3} spacing={4}>
                <FormControl>
                  <FormLabel>Name</FormLabel>
                  <Input
                    value={currentWorkflow.name}
                    onChange={(e) => setCurrentWorkflow(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Workflow name"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Input
                    value={currentWorkflow.description}
                    onChange={(e) => setCurrentWorkflow(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Workflow description"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Version</FormLabel>
                  <Input
                    value={currentWorkflow.version}
                    onChange={(e) => setCurrentWorkflow(prev => ({ ...prev, version: e.target.value }))}
                    placeholder="1.0.0"
                  />
                </FormControl>
              </SimpleGrid>
            </CardBody>
          </Card>
        )}

        {/* Main Editor Area */}
        <Card>
          <CardBody>
            <Flex height="600px" gap={4}>
              {/* Node Palette */}
              <Box width="200px" borderRight="1px" borderColor="gray.200" p={4}>
                <VStack spacing={3} align="stretch">
                  <Heading size="sm">Nodes</Heading>
                  {nodeTypes.map(nodeType => (
                    <Card
                      key={nodeType.type}
                      size="sm"
                      cursor="pointer"
                      _hover={{ shadow: 'md' }}
                      onClick={() => handleAddNode(nodeType.type)}
                    >
                      <CardBody>
                        <VStack spacing={1} align="center">
                          <Text fontSize="2xl">{nodeType.icon}</Text>
                          <Text fontWeight="medium" fontSize="sm">{nodeType.title}</Text>
                          <Text fontSize="xs" color="gray.600" textAlign="center">
                            {nodeType.description}
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </VStack>
              </Box>

              {/* Canvas */}
              <Box flex="1" position="relative" bg="gray.50" borderRadius="md" overflow="hidden">
                <div
                  ref={canvasRef}
                  style={{
                    width: '100%',
                    height: '100%',
                    position: 'relative',
                    cursor: isConnecting ? 'crosshair' : 'default'
                  }}
                >
                  {/* Render connections */}
                  {currentWorkflow.connections.map(conn => {
                    const sourceNode = currentWorkflow.nodes.find(n => n.id === conn.source);
                    const targetNode = currentWorkflow.nodes.find(n => n.id === conn.target);

                    if (!sourceNode || !targetNode) return null;

                    return (
                      <svg
                        key={conn.id}
                        style={{
                          position: 'absolute',
                          top: 0,
                          left: 0,
                          width: '100%',
                          height: '100%',
                          pointerEvents: 'none'
                        }}
                      >
                        <line
                          x1={sourceNode.position.x + 50}
                          y1={sourceNode.position.y + 25}
                          x2={targetNode.position.x}
                          y2={targetNode.position.y + 25}
                          stroke="#4299E1"
                          strokeWidth={2}
                          markerEnd="url(#arrowhead)"
                        />
                      </svg>
                    );
                  })}
                </div>
              </div>
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default WorkflowEditor;
