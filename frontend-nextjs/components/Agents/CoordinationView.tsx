import React, { useState, useEffect } from 'react';
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
  Progress,
  Tooltip,
  Center
} from '@chakra-ui/react';
import { AddIcon, EditIcon, DeleteIcon, PlayIcon, StopIcon, SettingsIcon, ViewIcon } from '@chakra-ui/icons';

interface Agent {
  id: string;
  name: string;
  role: string;
  status: 'active' | 'inactive' | 'error';
  capabilities: string[];
  performance: {
    tasksCompleted: number;
    successRate: number;
    avgResponseTime: number;
  };
  currentTask?: Task;
  dependencies: string[];
  resources: string[];
}

interface Task {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  assignedAgent: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  estimatedDuration: number; // in minutes
  dependencies: string[];
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
}

interface CoordinationViewProps {
  agents: Agent[];
  tasks: Task[];
  onTaskCreate?: (task: Task) => void;
  onTaskUpdate?: (taskId: string, updates: Partial<Task>) => void;
  onTaskDelete?: (taskId: string) => void;
  onTaskAssign?: (taskId: string, agentId: string) => void;
  onTaskStart?: (taskId: string) => void;
  onTaskComplete?: (taskId: string) => void;
  showNavigation?: boolean;
  compactView?: boolean;
}

const CoordinationView: React.FC<CoordinationViewProps> = ({
  agents,
  tasks,
  onTaskCreate,
  onTaskUpdate,
  onTaskDelete,
  onTaskAssign,
  onTaskStart,
  onTaskComplete,
  showNavigation = true,
  compactView = false
}) => {
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [view, setView] = useState<'timeline' | 'dependency' | 'status'>('timeline');
  const [loading, setLoading] = useState(false);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  const getStatusColor = (status: Task['status']) => {
    switch (status) {
      case 'completed': return 'green';
      case 'in_progress': return 'blue';
      case 'pending': return 'yellow';
      case 'failed': return 'red';
      default: return 'gray';
    }
  };

  const getPriorityColor = (priority: Task['priority']) => {
    switch (priority) {
      case 'critical': return 'red';
      case 'high': return 'orange';
      case 'medium': return 'yellow';
      case 'low': return 'green';
      default: return 'gray';
    }
  };

  const calculateTaskProgress = (task: Task): number => {
    if (task.status === 'completed') return 100;
    if (task.status === 'pending') return 0;
    if (task.status === 'failed') return 0;

    // For in_progress tasks, calculate based on time elapsed
    if (task.startedAt && task.estimatedDuration > 0) {
      const elapsed = Date.now() - task.startedAt.getTime();
      const progress = Math.min((elapsed / (task.estimatedDuration * 60 * 1000)) * 100, 90);
      return Math.round(progress);
    }

    return 10; // Default progress for in_progress tasks
  };

  const getAgentById = (agentId: string): Agent | undefined => {
    return agents.find(agent => agent.id === agentId);
  };

  const getTaskById = (taskId: string): Task | undefined => {
    return tasks.find(task => task.id === taskId);
  };

  const getBlockedTasks = (): Task[] => {
    return tasks.filter(task => {
      if (task.status !== 'pending') return false;
      return task.dependencies.some(depId => {
        const depTask = getTaskById(depId);
        return depTask && depTask.status !== 'completed';
      });
    });
  };

  const getReadyTasks = (): Task[] => {
    return tasks.filter(task => {
      if (task.status !== 'pending') return false;
      return task.dependencies.every(depId => {
        const depTask = getTaskById(depId);
        return !depTask || depTask.status === 'completed';
      });
    });
  };

  const handleCreateTask = (taskData: Omit<Task, 'id' | 'createdAt'>) => {
    const newTask: Task = {
      ...taskData,
      id: Date.now().toString(),
      createdAt: new Date()
    };
    onTaskCreate?.(newTask);
    toast({
      title: 'Task created',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleUpdateTask = (taskId: string, updates: Partial<Task>) => {
    onTaskUpdate?.(taskId, updates);
    toast({
      title: 'Task updated',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDeleteTask = (taskId: string) => {
    onTaskDelete?.(taskId);
    toast({
      title: 'Task deleted',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleAssignTask = (taskId: string, agentId: string) => {
    onTaskAssign?.(taskId, agentId);
    toast({
      title: 'Task assigned',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleStartTask = (taskId: string) => {
    onTaskStart?.(taskId);
    toast({
      title: 'Task started',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleCompleteTask = (taskId: string) => {
    onTaskComplete?.(taskId);
    toast({
      title: 'Task completed',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const TaskForm: React.FC<{
    task?: Task;
    onSubmit: (data: Omit<Task, 'id' | 'createdAt'>) => void;
    onCancel: () => void;
  }> = ({ task, onSubmit, onCancel }) => {
    const [formData, setFormData] = useState({
      title: task?.title || '',
      description: task?.description || '',
      priority: task?.priority || 'medium',
      estimatedDuration: task?.estimatedDuration || 30,
      assignedAgent: task?.assignedAgent || '',
      dependencies: task?.dependencies?.join(', ') || ''
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit({
        title: formData.title,
        description: formData.description,
        priority: formData.priority as Task['priority'],
        estimatedDuration: formData.estimatedDuration,
        assignedAgent: formData.assignedAgent,
        dependencies: formData.dependencies.split(',').map(id => id.trim()).filter(Boolean),
        status: 'pending'
      });
      onCancel();
    };

    return (
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <FormControl isRequired>
            <FormLabel>Task Title</FormLabel>
            <Input
              value={formData.title}
              onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
              placeholder="Enter task title"
            />
          </FormControl>

          <FormControl isRequired>
            <FormLabel>Description</FormLabel>
            <Textarea
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Describe the task requirements"
              rows={3}
            />
          </FormControl>

          <SimpleGrid columns={2} spacing={4}>
            <FormControl isRequired>
              <FormLabel>Priority</FormLabel>
              <Select
                value={formData.priority}
                onChange={(e) => setFormData(prev => ({ ...prev, priority: e.target.value }))}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </Select>
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Estimated Duration (minutes)</FormLabel>
              <Input
                type="number"
                value={formData.estimatedDuration}
                onChange={(e) => setFormData(prev => ({ ...prev, estimatedDuration: parseInt(e.target.value) }))}
                min="1"
              />
            </FormControl>
          </SimpleGrid>

          <FormControl>
            <FormLabel>Assign to Agent</FormLabel>
            <Select
              value={formData.assignedAgent}
              onChange={(e) => setFormData(prev => ({ ...prev, assignedAgent: e.target.value }))}
              placeholder="Select an agent"
            >
              {agents.map(agent => (
                <option key={agent.id} value={agent.id}>
                  {agent.name} ({agent.role})
                </option>
              ))}
            </Select>
          </FormControl>

          <FormControl>
            <FormLabel>Dependencies</FormLabel>
            <Input
              value={formData.dependencies}
              onChange={(e) => setFormData(prev => ({ ...prev, dependencies: e.target.value }))}
              placeholder="Task IDs separated by commas"
            />
            <Text fontSize="sm" color="gray.600" mt={1}>
              Enter task IDs that must be completed before this task
            </Text>
          </FormControl>

          <HStack width="100%" justifyContent="flex-end" spacing={3}>
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" colorScheme="blue">
              {task ? 'Update Task' : 'Create Task'}
            </Button>
          </HStack>
        </VStack>
      </form>
    );
  };

  if (loading) {
    return (
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Loading coordination view...</Text>
      </Box>
    );
  }

  return (
    <Box p={compactView ? 2 : 6}>
      <VStack spacing={compactView ? 3 : 6} align="stretch">
        {/* Header */}
        {showNavigation && (
          <Flex justify="space-between" align="center">
            <Heading size={compactView ? "md" : "lg"}>Agent Coordination</Heading>
            <HStack spacing={2}>
              <Button
                variant={view === 'timeline' ? 'solid' : 'outline'}
                size="sm"
                onClick={() => setView('timeline')}
              >
                Timeline
              </Button>
              <Button
                variant={view === 'dependency' ? 'solid' : 'outline'}
                size="sm"
                onClick={() => setView('dependency')}
              >
                Dependencies
              </Button>
              <Button
                variant={view === 'status' ? 'solid' : 'outline'}
                size="sm"
                onClick={() => setView('status')}
              >
                Status
              </Button>
              <Button
                leftIcon={<AddIcon />}
                colorScheme="blue"
                size={compactView ? "sm" : "md"}
                onClick={() => {
                  setSelectedTask(null);
                  onOpen();
                }}
              >
                New Task
              </Button>
            </HStack>
          </Flex>
        )}

        {/* Coordination Statistics */}
        {showNavigation && (
          <SimpleGrid columns={4} spacing={4}>
            <Card>
              <CardBody>
                <VStack spacing={1}>
                  <Text fontSize="sm" color="gray.600">Total Tasks</Text>
                  <Heading size="lg">{tasks.length}</Heading>
                </VStack>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <VStack spacing={1}>
                  <Text fontSize="sm" color="gray.600">In Progress</Text>
                  <Heading size="lg" color="blue.500">
                    {tasks.filter(t => t.status === 'in_progress').length}
                  </Heading>
                </VStack>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <VStack spacing={1}>
                  <Text fontSize="sm" color="gray.600">Ready</Text>
                  <Heading size="lg" color="green.500">
                    {getReadyTasks().length}
                  </Heading>
                </VStack>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <VStack spacing={1}>
                  <Text fontSize="sm" color="gray.600">Blocked</Text>
                  <Heading size="lg" color="red.500">
                    {getBlockedTasks().length}
                  </Heading>
                </VStack>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Main Content */}
        {view === 'timeline' && (
          <Card>
            <CardHeader>
              <Heading size={compactView ? "sm" : "md"}>Task Timeline</Heading>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                {tasks.map(task => {
                  const assignedAgent = getAgentById(task.assignedAgent);
                  const progress = calculateTaskProgress(task);

                  return (
                    <Card key={task.id} size="sm">
                      <CardBody>
                        <Flex justify="space-between" align="center">
                          <VStack align="start" spacing={1}>
                            <Heading size="sm">{task.title}</Heading>
                            <Text fontSize="sm" color="gray.600">{task.description}</Text>
                            {assignedAgent && (
                              <Badge colorScheme="blue">
                                {assignedAgent.name} ({assignedAgent.role})
                              </Badge>
                            )}
                          </VStack>

                          <VStack align="end" spacing={2}>
                            <HStack spacing={2}>
                              <Badge colorScheme={getStatusColor(task.status)}>
                                {task.status}
                              </Badge>
                              <Badge colorScheme={getPriorityColor(task.priority)}>
                                {task.priority}
                              </Badge>
                            </HStack>

                            <Progress
                              value={progress}
                              size="sm"
                              width="200px"
                              colorScheme={
                                task.status === 'failed' ? 'red' :
                                task.status === 'completed' ? 'green' : 'blue'
                              }
                            />
                            <Text fontSize="xs">
                              {progress}% • {task.estimatedDuration}min
                            </Text>
                          </VStack>
                        </Flex>
                      </CardBody>
                    </Card>
                  );
                })}
              </VStack>
            </CardBody>
          </Card>
        )}

        {view === 'status' && (
          <SimpleGrid columns={compactView ? 1 : 2} spacing={4}>
            {/* Active Agents */}
            <Card>
              <CardHeader>
                <Heading size={compactView ? "sm" : "md"}>Active Agents</Heading>
              </CardHeader>
              <CardBody>
                <VStack spacing={3} align="stretch">
                  {agents.filter(agent => agent.status === 'active').map(agent => {
                    const currentTask = agent.currentTask ? getTaskById(agent.currentTask.id) : null;

                    return (
                      <Card key={agent.id} size="sm">
                        <CardBody>
                          <Flex justify="space-between" align="center">
                            <VStack align="start" spacing={1}>
                              <Heading size="sm">{agent.name}</Heading>
                              <Badge colorScheme="blue">{agent.role}</Badge>
                              {currentTask && (
                                <Text fontSize="sm" color="gray.600">
                                  Working on: {currentTask.title}
                                </Text>
                              )}
                            </VStack>
                            <VStack align="end" spacing={1}>
                              <Badge colorScheme="green">Active</Badge>
                              <Text fontSize="xs">
                                {agent.performance.tasksCompleted} tasks
                              </Text>
                              <Text fontSize="xs">
                                {agent.performance.successRate}% success
                              </Text>
                            </VStack>
                          </Flex>
                        </CardBody>
                      </Card>
                    );
                  })}
                </VStack>
              </CardBody>
            </Card>

            {/* Task Status Overview */}
            <Card>
              <CardHeader>
                <Heading size={compactView ? "sm" : "md"}>Task Status</Heading>
              </CardHeader>
              <CardBody>
                <VStack spacing={3} align="stretch">
                  {['pending', 'in_progress', 'completed', 'failed'].map(status => {
                    const statusTasks = tasks.filter(t => t.status === status);
                    if (statusTasks.length === 0) return null;

                    return (
                      <Card key={status} size="sm">
                        <CardBody>
                          <Flex justify="space-between" align="center">
                            <VStack align="start" spacing={1}>
                              <Heading size="sm">{statusTasks.length} {status.replace('_', ' ')}</Heading>
                              <Badge colorScheme={getStatusColor(status as Task['status'])}>
                                {status}
                              </Badge>
                            </VStack>
                            <Progress
                              value={(statusTasks.length / tasks.length) * 100}
                              size="sm"
                              colorScheme={getStatusColor(status as Task['status'])}
                              width="100px"
                            />
                          </Flex>
                        </CardBody>
                      </Card>
                    );
                  })}
                </VStack>
              </CardBody>
            </Card>
          </GridItem>
        </Grid>
      </Box>
    </Box>
  );
};

export default CoordinationView;
