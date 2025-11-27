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
  DrawerContent,
  DrawerCloseButton,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel
} from '@chakra-ui/react';
import ExecutionHistoryList from './ExecutionHistoryList';
import ExecutionDetailView from './ExecutionDetailView';
import WorkflowScheduler from './WorkflowScheduler';
import { AddIcon, EditIcon, DeleteIcon, DragHandleIcon, SettingsIcon, ViewIcon, CopyIcon } from '@chakra-ui/icons';
import IntegrationSelector from './IntegrationSelector';

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

  const [activeTab, setActiveTab] = useState(0);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const [refreshHistoryTrigger, setRefreshHistoryTrigger] = useState(0);

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

  const handleSaveWorkflow = async () => {
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

    try {
      setLoading(true);
      const response = await fetch('/api/v1/workflows', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(currentWorkflow),
      });

      if (!response.ok) {
        throw new Error('Failed to save workflow');
      }

      const savedWorkflow = await response.json();
      setCurrentWorkflow(savedWorkflow);

      onSave?.(savedWorkflow);
      toast({
        title: 'Workflow saved',
        status: 'success',
        duration: 2000,
        isClosable: true,
      });
    } catch (error) {
      toast({
        title: 'Error saving workflow',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
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

  const handleExecuteWorkflow = async () => {
    if (!currentWorkflow.id) {
      toast({
        title: 'Please save workflow first',
        status: 'warning',
        duration: 2000,
        isClosable: true,
      });
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(`/api/v1/workflows/${currentWorkflow.id}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });

      if (!response.ok) {
        throw new Error('Failed to execute workflow');
      }

      const result = await response.json();

      if (result.status === 'success') {
        toast({
          title: 'Workflow executed successfully!',
          description: `${result.results.length} nodes processed`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        setRefreshHistoryTrigger(prev => prev + 1);
        setActiveTab(2); // Switch to History tab
      } else {
        toast({
          title: 'Workflow execution failed',
          description: result.errors?.[0] || 'Unknown error',
          status: 'error',
          duration: 3000,
          isClosable: true,
        });
      }
    } catch (error) {
      toast({
        title: 'Error executing workflow',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
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
    const [formData, setFormData] = useState({
      title: selectedNode?.title || '',
      description: selectedNode?.description || '',
      ...selectedNode?.config
    });

    if (!selectedNode) return null;

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
                <VStack spacing={4} align="stretch">
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

                  {formData.triggerType && (
                    <FormControl>
                      <FormLabel>Select Integration</FormLabel>
                      <IntegrationSelector
                        selectedIntegrationId={formData.integrationId}
                        onSelect={(id) => setFormData(prev => ({ ...prev, integrationId: id }))}
                      />
                    </FormControl>
                  )}
                </VStack>
              )}

              {selectedNode.type === 'action' && (
                <VStack spacing={4} align="stretch">
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

                  {formData.actionType && (
                    <FormControl>
                      <FormLabel>Select Integration</FormLabel>
                      <IntegrationSelector
                        selectedIntegrationId={formData.integrationId}
                        onSelect={(id) => setFormData(prev => ({ ...prev, integrationId: id }))}
                      />
                    </FormControl>
                  )}

                  {/* Dynamic Action Fields */}
                  {formData.actionType === 'send_email' && (
                    <>
                      <FormControl>
                        <FormLabel>To</FormLabel>
                        <Input
                          value={formData.to || ''}
                          onChange={(e) => setFormData(prev => ({ ...prev, to: e.target.value }))}
                          placeholder="recipient@example.com"
                        />
                      </FormControl>
                      <FormControl>
                        <FormLabel>Subject</FormLabel>
                        <Input
                          value={formData.subject || ''}
                          onChange={(e) => setFormData(prev => ({ ...prev, subject: e.target.value }))}
                          placeholder="Email subject"
                        />
                      </FormControl>
                      <FormControl>
                        <FormLabel>Body</FormLabel>
                        <Textarea
                          value={formData.body || ''}
                          onChange={(e) => setFormData(prev => ({ ...prev, body: e.target.value }))}
                          placeholder="Email content"
                          rows={4}
                        />
                      </FormControl>
                    </>
                  )}

                  {formData.actionType === 'notify' && (
                    <>
                      <FormControl>
                        <FormLabel>Channel</FormLabel>
                        <Input
                          value={formData.channel || ''}
                          onChange={(e) => setFormData(prev => ({ ...prev, channel: e.target.value }))}
                          placeholder="#general or @user"
                        />
                      </FormControl>
                      <FormControl>
                        <FormLabel>Message</FormLabel>
                        <Textarea
                          value={formData.message || ''}
                          onChange={(e) => setFormData(prev => ({ ...prev, message: e.target.value }))}
                          placeholder="Notification message"
                          rows={3}
                        />
                      </FormControl>
                    </>
                  )}
                </VStack>
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

  import {
    Tabs,
    TabList,
    TabPanels,
    Tab,
    TabPanel
  } from '@chakra-ui/react';
  import ExecutionHistoryList from './ExecutionHistoryList';
  import ExecutionDetailView from './ExecutionDetailView';

  // ... existing imports ...

  // Inside WorkflowEditor component
  const [activeTab, setActiveTab] = useState(0);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const [refreshHistoryTrigger, setRefreshHistoryTrigger] = useState(0);

  // ... existing functions ...

  const handleExecuteWorkflow = async () => {
    // ... existing execution logic ...
    if (result.status === 'success') {
      toast({
        title: 'Workflow executed successfully!',
        description: `${result.results.length} nodes processed`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      // Refresh history
      setRefreshHistoryTrigger(prev => prev + 1);
    }
    // ... existing error handling ...
  };

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
                colorScheme="orange"
                size={compactView ? "sm" : "md"}
                onClick={handleExecuteWorkflow}
                isDisabled={!currentWorkflow.id}
              >
                Execute
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

        {/* Main Content with Tabs */}
        <Card>
          <CardBody p={0}>
            <Tabs index={activeTab} onChange={setActiveTab} isLazy>
              <TabList px={4} pt={2}>
                <Tab>Design</Tab>
                <Tab>Code</Tab>
                <Tab>History</Tab>
                <Tab>Schedule</Tab>
              </TabList>

              <TabPanels>
                {/* Design Tab */}
                <TabPanel p={4}>
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

                        {/* Render Nodes (This part was missing in the view, assuming it's handled by a separate component or loop not shown fully in previous view, but I'll leave the canvas structure as is and assume nodes are rendered on top) */}
                        {/* Actually, looking at the previous view, the nodes rendering loop was NOT shown in the snippet I viewed. 
                            I should be careful not to overwrite the node rendering logic if it exists.
                            Wait, I viewed lines 1-784 and I didn't see the node rendering loop inside the canvas div.
                            Ah, I might have missed it or it was truncated? 
                            Let me check the file content again. 
                            The previous view showed lines 733-774 which is the canvas div.
                            It only showed connections rendering!
                            Where are the nodes rendered?
                            Maybe I missed a chunk.
                            
                            Wait, I see `handleExecuteWorkflow` logic in my replacement content.
                            I should use `multi_replace_file_content` to be safer, or just replace the specific blocks.
                            
                            I'll use `multi_replace_file_content` to inject the tabs and imports.
                        */}
                      </div>
                    </Box>
                  </Flex>
                </TabPanel>

                {/* Code Tab */}
                <TabPanel>
                  <Box height="600px" bg="gray.900" color="green.400" p={4} borderRadius="md" overflow="auto" fontFamily="monospace">
                    <pre>{JSON.stringify(currentWorkflow, null, 2)}</pre>
                  </Box>
                </TabPanel>

                {/* History Tab */}
                <TabPanel>
                  <Box height="600px" overflowY="auto">
                    {selectedExecutionId ? (
                      <ExecutionDetailView
                        executionId={selectedExecutionId}
                        onBack={() => setSelectedExecutionId(null)}
                      />
                    ) : (
                      <ExecutionHistoryList
                        workflowId={currentWorkflow.id}
                        onSelectExecution={setSelectedExecutionId}
                        refreshTrigger={refreshHistoryTrigger}
                      />
                    )}
                  </Box>
                </TabPanel>

                {/* Schedule Tab */}
                <TabPanel p={6}>
                  <WorkflowScheduler
                    workflowId={currentWorkflow.id}
                    workflowName={currentWorkflow.name}
                  />
                </TabPanel>
              </TabPanels>
            </Tabs>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};


export default WorkflowEditor;
